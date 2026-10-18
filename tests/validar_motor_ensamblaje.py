"""
Validacion del ensamblaje dinamico del motor independiente (E0-E3).

Referencias independientes del coordinador:
  * soluciones exactas cuando existen: U = U0 + Q t (rigido cerrado),
    H = H0 + Q t y W = P (V - V0) (presion constante), m = m0 + F t;
  * tiempos de ebullicion y secado a P constante desde h' y h'' de la
    coexistencia (calor latente sin fuente adicional);
  * compresion adiabatica cuasiestatica: s constante (segunda ley), que
    no aparece en ninguna ecuacion del coordinador;
  * comprobacion TP de cada muestra: evaluar_TP(T, P) debe devolver u = U/m
    y v = V/m (otro camino que el cierre UV/PH usado al integrar);
  * un RK4 de paso fijo escrito aqui, con los flashes del nucleo, para
    vaciados, inversiones y continuidad de presion.
Las solicitudes reales del frontend estan en tests/fixtures_ensamblaje/
(node tests/generar_solicitudes_ensamblaje.mjs).

Ejecutar desde la raiz del proyecto:
    python tests/validar_motor_ensamblaje.py
"""

import asyncio
import copy
import json
import math
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import httpx

from backend import motor_ensamblaje as me
from backend.main import app
from core import agua_iapws95 as agua

FALLOS, CHECKS = [], [0]


def check(cond, mensaje):
    CHECKS[0] += 1
    if not cond:
        FALLOS.append(mensaje)
        print("  FALLO:", mensaje)


FIX = RAIZ / "tests" / "fixtures_ensamblaje"
PLANTILLA_R = json.loads((FIX / "rigida_cerrada_U0.json").read_text(encoding="utf-8"))["solicitud"]
PLANTILLA_P = json.loads((FIX / "abierta_presion.json").read_text(encoding="utf-8"))["solicitud"]


def dato(mag, texto, unidad, funcion="frontera", prop="volumen:dominio", ruta="/prueba"):
    return {"magnitud": mag, "funcion": funcion, "declaracion": {"texto": str(texto), "unidad": unidad},
            "origen": {"propietarioId": prop, "ruta": ruta}}


def solicitud(frontera="rigida", V=("10", "L"), P=("1", "bar"), m0=("10", "kg"), E0=("U", "1000", "kJ"),
              Q=("1000", "W"), corrientes=(), politica=None, tf=("300", "s"), muestras=21, rtol=1e-8,
              extracciones=None, sid="prueba"):
    """Solicitud con las formulaciones reales de las hojas del frontend."""
    s = copy.deepcopy(PLANTILLA_R if frontera == "rigida" else PLANTILLA_P)
    s["solicitudId"] = sid
    pol = politica or {"cantidad": "sin_restriccion", "cambioInterno": "permitido",
                       "evaluacion": "equilibrio_estable"}
    s["volumen"]["cierre"]["politica"] = pol
    s["volumen"]["formulacionEnergia"]["monofasico"] = pol["cantidad"] == "monofasico"
    s["volumen"]["formulacionEnergia"]["sinCambioFase"] = pol["cambioInterno"] == "prohibido"
    if extracciones:
        s["volumen"]["cierre"]["extracciones"] = extracciones
    datos = {"volumen.dominio.m0.1": dato("masa", *m0, funcion="inicial"),
             "estudio.tfinal": dato("tiempo", *tf, funcion="estudio", prop="estudio")}
    if E0[0] == "U":
        datos["volumen.dominio.U0"] = dato("energia", E0[1], E0[2], funcion="inicial")
        s["volumen"]["inicial"]["energia"] = {"tipo": "U", "datoId": "volumen.dominio.U0"}
    else:
        datos["volumen.dominio.T0"] = dato("temperatura", E0[1], E0[2], funcion="inicial")
        s["volumen"]["inicial"]["energia"] = {"tipo": "T", "datoId": "volumen.dominio.T0"}
    if frontera == "rigida":
        datos["volumen.dominio.V"] = dato("volumen", *V, funcion="geometria")
        s["volumen"]["frontera"] = {"tipo": "rigida", "datoId": "volumen.dominio.V"}
    else:
        datos["volumen.dominio.Pext"] = dato("presion", *P)
        s["volumen"]["frontera"] = {"tipo": "presion_prescrita", "presionId": "volumen.dominio.Pext"}
    if Q is not None:
        datos["volumen.dominio.Q"] = dato("potencia", *Q)
        s["transferencias"] = {"calor": "volumen.dominio.Q"}
        s["volumen"]["formulacionEnergia"]["adiabatico"] = False
    else:
        s["transferencias"] = {}
        s["volumen"]["formulacionEnergia"]["adiabatico"] = True
    cors, puertos = [], []
    for c in corrientes:
        i = c["id"]
        entrada = c["sentido"] == "entrada"
        cor = {"id": i, "desde": None if entrada else "dominio", "hasta": "dominio" if entrada else None,
               "componenteIds": [1], "mecanismo": None,
               "materia": {"modo": "por_componente", "base": c.get("base", "masica"),
                           "caudalIds": {"1": f"corriente.{i}.F.1"}}}
        datos[f"corriente.{i}.F.1"] = dato("caudal_molar" if c.get("base") == "molar" else "caudal",
                                           *c["F"], prop=f"corriente:{i}")
        if "T" in c:
            datos[f"corriente.{i}.Text"] = dato("temperatura", *c["T"], prop=f"corriente:{i}")
            pres = {"tipo": "continuidad", "volumenId": "dominio"} if c.get("P") == "continuidad" else \
                {"tipo": "dato", "datoId": f"corriente.{i}.Pext"}
            if c.get("P") != "continuidad":
                datos[f"corriente.{i}.Pext"] = dato("presion", *c["P"], prop=f"corriente:{i}")
            cor["estadoExterior"] = {"tipo": "TP", "temperaturaId": f"corriente.{i}.Text", "presion": pres}
        if "extraccion" in c:
            cor["extraccion"] = c["extraccion"]
        cors.append(cor)
        puertos.append({"id": i, "sentido": c["sentido"], "constante": True})
    s["corrientes"] = cors
    s["volumen"]["contextoEnergia"]["puertos"] = puertos
    s["datos"] = datos
    s["estudio"]["muestras"] = muestras
    s["estudio"]["rtol"] = rtol
    return s


def series(r):
    return {x["variableId"]: x["valores"] for x in r["resultados"]["series"]}


def codigos(r):
    v = r.get("validacion", r)
    return {d["codigo"] for d in v["diagnosticos"]}


# ----------------------------------------------------------------------
print("1. Peticion incompleta: ensamblaje y recuento sin integrar ni inventar")
s = solicitud(V=("", "L"))
v, _ = me.validar(s)
check(v["recuento"]["estado"] == "incompleto" and v["recuento"]["datosFaltantes"] == 1, f"recuento {v['recuento']}")
check(any(d["codigo"] == "MOTOR_ENS_DATO_PENDIENTE" and d["variableIds"] == ["volumen.dominio.V"]
          and d["origen"]["ruta"] == "/prueba" for d in v["diagnosticos"]), "dato pendiente con ruta")
check("volumen.dominio.V" in v["recuento"]["motivo"], "el recuento culpa al dato que falta")
check(v["inicializacion"] == {"estado": "pendiente", "variables": {}, "estadoTermodinamico": None},
      "sin inicializacion inventada")
check({e["id"] for e in v["ecuaciones"]} >= {"materia.1", "energia", "estado.u", "estado.v", "estado.reparto"},
      "ecuaciones publicadas antes de resolver")
r = me.resolver(s)
check(r["estado"] == "invalido" and r["resultados"] is None, "resolver no integra una peticion incompleta")
s2 = solicitud()
s2["termodinamica"] = {"resultado": {"T": 900}}
check("MOTOR_ENS_CAMPO_NO_ADMITIDO" in codigos(me.validar(s2)[0]), "no admite una consulta guardada")
s3 = solicitud(Q=None)
s3["volumen"]["formulacionEnergia"]["adiabatico"] = False
check("MOTOR_ENS_Q_PENDIENTE" in codigos(me.validar(s3)[0]), "Q ausente no es cero")


# ----------------------------------------------------------------------
print("2. Rigido cerrado: calentamiento, P variable real")
r = me.resolver(solicitud(muestras=11))
check(r["estado"] == "resuelto", f"estado {r['estado']} {codigos(r)}")
S, ts = series(r), r["resultados"]["tiempos"]
U0 = 1e6
for i, t in enumerate(ts):
    check(abs(S["volumen.dominio.U"][i] - (U0 + 1000 * t)) <= 1e-6 * U0, f"U = U0 + Q t en t={t}")
    T, P = S["volumen.dominio.T"][i], S["volumen.dominio.P"][i]
    p = agua.evaluar_TP(T, P).propiedades
    check(abs(p.v - 0.01 / 10) / 1e-3 < 1e-8 and abs(p.u - S["volumen.dominio.U"][i] / 10) < 1e-6 * abs(p.u) + 1e-3,
          f"comprobacion TP independiente en t={t}: v {p.v}, u {p.u}")
check(S["volumen.dominio.P"][-1] > 1.7 * S["volumen.dominio.P"][0], "la presion sube al calentar a volumen fijo")
check(len(r["resultados"]["estadosTermodinamicos"]) == len(ts), "un estado certificado por muestra")
for x in r["resultados"]["residuos"]:
    check(x["maximoEscalado"] <= x["tolerancia"], f"residuo {x}")


# ----------------------------------------------------------------------
print("3. Inicializacion: U y T, compatibles e incompatibles")
vU, _ = me.validar(solicitud(E0=("U", "1000", "kJ")))
TU = vU["inicializacion"]["variables"]["volumen.dominio.T"]
vT, _ = me.validar(solicitud(E0=("T", TU, "K")))
check(vT["inicializacion"]["estado"] == "compatible"
      and abs(vT["inicializacion"]["variables"]["volumen.dominio.U"] - 1e6) < 1e-3, "T(0) -> TV -> mismo U(0)")
vC, _ = me.validar(solicitud(E0=("T", TU - 273.15, "degC")))
check(abs(vC["inicializacion"]["variables"]["volumen.dominio.U"] - 1e6) < 1e-3, "T(0) en degC")
# monofasico pero el estado inicial es bifasico
v, _ = me.validar(solicitud(V=("1", "m3"), E0=("T", "350", "K"),
                            politica={"cantidad": "monofasico", "cambioInterno": "prohibido",
                                      "evaluacion": "equilibrio_estable"}))
check(v["inicializacion"]["estado"] == "incompatible" and v["inicializacion"]["estadoTermodinamico"] is None,
      f"inicial bifasico con politica monofasica: {v['inicializacion']['estado']}")
# presion dada y T en saturacion: falta la especificacion de reparto
Ts = agua.T_saturacion(1e5)[0].T
v, _ = me.validar(solicitud("presion", P=("100000", "Pa"), E0=("T", repr(Ts), "K"), Q=("0", "W")))
check(v["inicializacion"]["estado"] == "pendiente" and any(
    "SATURACION" in d["codigo"] for d in v["diagnosticos"]), "TP en saturacion: pendiente, sin q inventada")
v, _ = me.validar(solicitud(E0=("U", "-100", "kJ")))
check(v["inicializacion"]["estado"] == "incompatible", "U(0) bajo el punto triple: incompatible")
v, _ = me.validar(solicitud(m0=("0", "kg")))
check(v["inicializacion"]["estado"] == "incompatible" and "MOTOR_ENS_INICIAL_VACIO" in codigos(v),
      "masa inicial nula")


# ----------------------------------------------------------------------
def rk4(fun, y0, tf, n):
    """RK4 de paso fijo de la prueba (independiente del coordinador)."""
    y, t, h = list(y0), 0.0, tf / n
    for _ in range(n):
        k1 = fun(t, y)
        k2 = fun(t + h / 2, [a + h / 2 * b for a, b in zip(y, k1)])
        k3 = fun(t + h / 2, [a + h / 2 * b for a, b in zip(y, k2)])
        k4 = fun(t + h, [a + h * b for a, b in zip(y, k3)])
        y = [a + h / 6 * (b + 2 * c + 2 * d + e) for a, b, c, d, e in zip(y, k1, k2, k3, k4)]
        t += h
    return y


def estado_rigido(V, m, U):
    return agua.evaluar_UV(U / m, V / m, certificar=False)


print("4. Volumen abierto: llenado, vaciado, inversion, continuidad, donantes pendientes")
# llenado rigido: m = m0 + F t, U = U0 + F h_in t exactos
Vg, m0 = 0.2, 150.0
e0 = agua.evaluar_TP(300.0, 5e6).propiedades
m0 = Vg / e0.v * 0.999
U0 = m0 * agua.evaluar_TV(300.0, Vg / m0).u
s = solicitud(V=(repr(Vg), "m3"), m0=(repr(m0), "kg"), E0=("U", repr(U0), "J"), Q=None, tf=("4", "s"),
              corrientes=[{"id": 1, "sentido": "entrada", "F": ("0.5", "kg/s"), "T": ("320", "K"),
                           "P": ("150", "bar")}], muestras=9,
              extracciones={"1": {"tipo": "mezcla_homogenea"}})
r = me.resolver(s)
h_in = agua.evaluar_TP(320.0, 150e5).propiedades.h
if check(r["estado"] in ("resuelto", "parcial"), f"llenado {r['estado']} {codigos(r)}") or True:
    if r["resultados"]:
        S, ts = series(r), r["resultados"]["tiempos"]
        for i, t in enumerate(ts):
            check(abs(S["volumen.dominio.m.1"][i] - (m0 + 0.5 * t)) < 1e-9 * m0, f"llenado m(t={t})")
            check(abs(S["volumen.dominio.U"][i] - (U0 + 0.5 * h_in * t)) < 1e-7 * abs(U0) + 1e-3,
                  f"llenado U(t={t})")
# vaciado rigido por una salida constante (donante = volumen): RK4 independiente
s = solicitud(V=("0.5", "m3"), m0=("400", "kg"), E0=("T", "350", "K"), Q=("20", "kW"), tf=("100", "s"),
              corrientes=[{"id": 2, "sentido": "salida", "F": ("1.5", "kg/s")}], muestras=11,
              extracciones={"2": {"tipo": "mezcla_homogenea"}})
r = me.resolver(s)
check(r["estado"] == "resuelto", f"vaciado {r['estado']} {codigos(r)}")
v0 = r["validacion"]["inicializacion"]["variables"]
U_ini = v0["volumen.dominio.U"]


def f_vaciado(t, y):
    e = estado_rigido(0.5, y[0], y[1])
    return [-1.5, -1.5 * e.h + 2e4]


ref = rk4(f_vaciado, [400.0, U_ini], 100.0, 200)
S = series(r)
check(abs(S["volumen.dominio.m.1"][-1] - ref[0]) < 1e-9 * 400, "vaciado: masa frente a RK4")
check(abs(S["volumen.dominio.U"][-1] - ref[1]) < 1e-6 * abs(ref[1]), f"vaciado: U {S['volumen.dominio.U'][-1]} vs {ref[1]}")
check(any(len(e["fases"]) == 2 for e in r["resultados"]["estadosTermodinamicos"]), "el vaciado llega a coexistencia")
# inversion: entrada con F = 0.8 cos(0.05 t): entra desde el exterior y sale del volumen
s = solicitud(V=("0.5", "m3"), m0=("400", "kg"), E0=("T", "350", "K"), Q=None, tf=("120", "s"),
              corrientes=[{"id": 1, "sentido": "entrada", "F": ("0.8*cos(0.05*t)", "kg/s"), "T": ("300", "K"),
                           "P": ("3", "bar")}], muestras=13,
              extracciones={"1": {"tipo": "mezcla_homogenea"}})
r = me.resolver(s)
check(r["estado"] == "resuelto", f"inversion {r['estado']} {codigos(r)}")
h_ext = agua.evaluar_TP(300.0, 3e5).propiedades.h
U_ini = r["validacion"]["inicializacion"]["variables"]["volumen.dominio.U"]


def f_inv(t, y):
    F = 0.8 * math.cos(0.05 * t)
    h = h_ext if F > 0 else estado_rigido(0.5, y[0], y[1]).h
    return [F, F * h]


ref = rk4(f_inv, [400.0, U_ini], 120.0, 2400)
S = series(r)
check(abs(S["volumen.dominio.m.1"][-1] - (400 + 0.8 / 0.05 * math.sin(0.05 * 120))) < 1e-8 * 400 * 10,
      "inversion: masa exacta")
check(abs(S["volumen.dominio.U"][-1] - ref[1]) < 2e-6 * abs(ref[1]),
      f"inversion: U frente a RK4 con donante segun el signo ({S['volumen.dominio.U'][-1]} vs {ref[1]})")
hs = S["corriente.1.h"]
Fs = S["corriente.1.F"]
check(all(abs(h - h_ext) < 1e-6 for h, F in zip(hs, Fs) if F > 0) and any(
    abs(h - h_ext) > 1e3 for h, F in zip(hs, Fs) if F < 0), "h donante: exterior al entrar, volumen al salir")
# continuidad de presion: donante a (T_ext, P del volumen). Recipiente lleno de
# liquido comprimido: la presion sube al entrar masa y el donante la sigue.
s = solicitud(V=("0.1", "m3"), m0=("100", "kg"), E0=("T", "300", "K"), Q=None, tf=("10", "s"),
              corrientes=[{"id": 1, "sentido": "entrada", "F": ("0.02", "kg/s"), "T": ("330", "K"),
                           "P": "continuidad"}], muestras=6,
              extracciones={"1": {"tipo": "mezcla_homogenea"}})
r = me.resolver(s)
check(r["estado"] == "resuelto", f"continuidad {r['estado']} {codigos(r)}")
U_ini = r["validacion"]["inicializacion"]["variables"]["volumen.dominio.U"]


def f_cont(t, y):
    e = estado_rigido(0.1, y[0], y[1])
    return [0.02, 0.02 * agua.evaluar_TP(330.0, e.P).propiedades.h]


ref = rk4(f_cont, [100.0, U_ini], 10.0, 100)
check(abs(series(r)["volumen.dominio.U"][-1] - ref[1]) < 1e-6 * abs(ref[1]), "continuidad frente a RK4")
check(series(r)["volumen.dominio.P"][-1] > series(r)["volumen.dominio.P"][0] + 1e6,
      "continuidad: la presion del volumen sube y el donante la sigue")
check(any(e["id"] == "mecanica.continuidad.1" for e in r["validacion"]["ecuaciones"]),
      "continuidad publicada como ecuacion")
# donante que alcanza la saturacion por continuidad: detencion explicita, no h inventada
r = me.resolver(solicitud(V=("0.2", "m3"), m0=("100", "kg"), E0=("T", "300", "K"), Q=None, tf=("10", "s"),
                          corrientes=[{"id": 1, "sentido": "entrada", "F": ("2", "kg/s"), "T": ("330", "K"),
                                       "P": "continuidad"}], muestras=6,
                          extracciones={"1": {"tipo": "mezcla_homogenea"}}))
check(r["estado"] == "parcial" and "MOTOR_ENS_DETENIDO_DONANTE_EN_SATURACION" in codigos(r),
      f"donante en saturacion: {r['estado']} {codigos(r)}")
# frontera faltante: una entrada sin estado exterior
s = solicitud(corrientes=[{"id": 1, "sentido": "entrada", "F": ("1", "kg/s")}])
s["corrientes"][0].pop("estadoExterior", None)
v, _ = me.validar(s)
check(any(d["codigo"] == "MOTOR_ENS_DONANTE_PENDIENTE" and "corriente.1.Text" in d["variableIds"]
          for d in v["diagnosticos"]), "entrada sin donante: pendiente con variables")
s = solicitud(corrientes=[{"id": 2, "sentido": "salida", "F": ("2-t", "kg/s")}],
              extracciones={"2": {"tipo": "mezcla_homogenea"}})
check("MOTOR_ENS_DONANTE_PENDIENTE" in codigos(me.validar(s)[0]), "salida que puede invertir necesita donante")
s = solicitud(corrientes=[{"id": 1, "sentido": "entrada", "F": ("0", "kg/s")}])
check("MOTOR_ENS_DONANTE_PENDIENTE" not in codigos(me.validar(s)[0]), "cero constante no exige donante")


# ----------------------------------------------------------------------
print("5. Presion prescrita: constante, suave, discontinua")
m = 2.0
p0 = agua.evaluar_TP(300.0, 2e5).propiedades
r = me.resolver(solicitud("presion", P=("2", "bar"), m0=(repr(m), "kg"), E0=("T", "300", "K"), Q=("5", "kW"),
                          tf=("60", "s"), muestras=7))
check(r["estado"] == "resuelto", f"P constante {r['estado']} {codigos(r)}")
S = series(r)
H0 = m * p0.h
for i, t in enumerate(r["resultados"]["tiempos"]):
    check(abs(S["volumen.dominio.H"][i] - (H0 + 5000 * t)) < 1e-6 * H0, f"H = H0 + Q t en t={t}")
    check(abs(S["volumen.dominio.W"][i] - 2e5 * (S["volumen.dominio.V"][i] - m * p0.v)) < 1e-6,
          f"W = P (V - V0) en t={t}")
    check(abs(S["volumen.dominio.U"][i] - (S["volumen.dominio.H"][i] - 2e5 * S["volumen.dominio.V"][i])) < 1e-6,
          f"U = H - PV en t={t}")
# compresion adiabatica cuasiestatica con P(t) suave: s constante (segunda ley, reversible)
for P_txt, etiqueta in (("1e5 + 4e5*t/100", "rampa"), ("3e5 + 2e5*sin(0.05*t)", "seno")):
    r = me.resolver(solicitud("presion", P=(P_txt, "Pa"), m0=("1", "kg"), E0=("T", "500", "K"), Q=None,
                              tf=("100", "s"), muestras=11, rtol=1e-10))
    check(r["estado"] == "resuelto", f"{etiqueta}: {r['estado']} {codigos(r)}")
    sm = [e["mezcla"]["s"] for e in r["resultados"]["estadosTermodinamicos"]]
    check(max(sm) - min(sm) < 1e-5, f"{etiqueta}: entropia constante en compresion adiabatica ({max(sm) - min(sm):.2e})")
    res = {x["ecuacionId"]: x for x in r["resultados"]["residuos"]}
    check(res["energia"]["maximoEscalado"] <= res["energia"]["tolerancia"],
          f"{etiqueta}: forma en U (trabajo P dV con derivada total) = forma en H: {res['energia']}")
r = me.validar(solicitud("presion", P=("1e5 + 1e5*step(t-10)", "Pa"), Q=("0", "W")))[0]
check("MOTOR_ENS_NO_SUAVE" in codigos(r), "presion con escalon: no soportada sin regla de salto")


# ----------------------------------------------------------------------
print("6. Restricciones, duplicados, unidades y bases")
s = solicitud()
s["volumen"]["formulacionEnergia"]["modelo"] = "u_lineal"
check("MOTOR_ENS_DOS_CIERRES" in codigos(me.validar(s)[0]), "u(T) manual + EOS")
s = solicitud()
s["volumen"]["frontera"]["presionRestriccionId"] = "volumen.dominio.Pr"
s["datos"]["volumen.dominio.Pr"] = dato("presion", "1", "bar")
v = me.validar(s)[0]
check(v["recuento"]["estado"] == "conflicto" and any(
    d["codigo"] == "MOTOR_ENS_SOBREDETERMINADO" and "volumen.dominio.Pr" in d["variableIds"]
    for d in v["diagnosticos"]), "P adicional en rigido: conflicto con referencia")
s = solicitud()
s["volumen"]["formulacionEnergia"]["densidadConstante"] = True
check("MOTOR_ENS_DENSIDAD" in codigos(me.validar(s)[0]), "densidad constante incompatible con la EOS")
s = solicitud()
s["volumen"]["formulacionEnergia"]["monofasico"] = True
check("MOTOR_ENS_POLITICA" in codigos(me.validar(s)[0]), "politicas de fase discrepantes")
s = solicitud(corrientes=[{"id": 1, "sentido": "entrada", "F": ("1", "kg/s"), "T": ("300", "K"),
                           "P": "continuidad"}], extracciones={"1": {"tipo": "mezcla_homogenea"}})
s["corrientes"][0]["estadoExterior"]["presion"]["restriccionAdicionalId"] = "corriente.1.Pext"
s["datos"]["corriente.1.Pext"] = dato("presion", "2", "bar")
check("MOTOR_ENS_P_DUPLICADA" in codigos(me.validar(s)[0]), "continuidad + dato de presion")
s = solicitud()
s["componentes"][0]["masaMolar"] = {"cantidad": {"valor": 18.0, "unidad": "g/mol"}, "fuente": "x"}
check("MOTOR_ENS_MASA_MOLAR_CONTRADICTORIA" in codigos(me.validar(s)[0]), "masa molar contradictoria conservada")
s = solicitud(V=("10", "kg"))
check("MOTOR_ENS_UNIDAD" in codigos(me.validar(s)[0]), "unidad incompatible")
a = me.validar(solicitud(V=("10", "L"), E0=("U", "1000", "kJ"), sid="a"))[0]
b = me.validar(solicitud(V=("0.01", "m3"), E0=("U", "1e6", "J"), sid="b"))[0]
c = me.validar(solicitud(V=("0.01", "m3"), E0=("U", "1e6", "J"), Q=("2000", "W"), sid="c"))[0]
check(a["modeloId"] == b["modeloId"] != c["modeloId"], "identidad: unidades equivalentes iguales, Q distinto cambia")
sb = solicitud(sid="d")
sb["derivacion"] = {"materia": [{"titulo": "otro titulo", "ecuaciones": []}], "energia": []}
check(me.validar(sb)[0]["modeloId"] == a["modeloId"], "titulos de la derivacion no son identidad fisica")
# caudal molar con composicion masica: misma fisica que el caudal masico equivalente
F_kg = 0.5
s_kg = solicitud(V=("0.2", "m3"), m0=("150", "kg"), E0=("T", "300", "K"), Q=None, tf=("4", "s"), muestras=3,
                 corrientes=[{"id": 1, "sentido": "entrada", "F": (repr(F_kg), "kg/s"), "T": ("320", "K"),
                              "P": ("150", "bar")}])
s_mol = copy.deepcopy(s_kg)
s_mol["corrientes"][0]["materia"] = {"modo": "total_y_composicion", "base": "molar", "caudalId": "corriente.1.F.1",
                                     "composicion": {"base": "masica", "fracciones": {"1": 1}}}
s_mol["datos"]["corriente.1.F.1"] = dato("caudal_molar", repr(F_kg / agua.M), "mol/s", prop="corriente:1")
ra, rb = me.resolver(s_kg), me.resolver(s_mol)
check(ra["estado"] == rb["estado"] == "resuelto"
      and abs(series(ra)["volumen.dominio.U"][-1] - series(rb)["volumen.dominio.U"][-1]) < 1e-6,
      "caudal molar + composicion masica = caudal masico (masa molar del modelo)")


# ----------------------------------------------------------------------
print("7. Metodo, tolerancias y convergencia")
s = solicitud()
s["estudio"]["metodoSolicitado"] = "euler_implicito"
check("MOTOR_ENS_METODO" in codigos(me.validar(s)[0]), "metodo no verificado")
finales = []
for rtol in (1e-5, 1e-7, 1e-9, 1e-11):
    r = me.resolver(solicitud(V=("0.5", "m3"), m0=("400", "kg"), E0=("T", "350", "K"), Q=("20", "kW"),
                              tf=("100", "s"), corrientes=[{"id": 2, "sentido": "salida", "F": ("1.5", "kg/s")}],
                              muestras=3, rtol=rtol, extracciones={"2": {"tipo": "mezcla_homogenea"}}))
    finales.append(series(r)["volumen.dominio.U"][-1])
errs = [abs(f - finales[-1]) for f in finales[:-1]]
check(errs[0] > errs[1] > errs[2] and errs[2] < 1e-6 * abs(finales[-1]), f"convergencia con rtol: {errs}")


# ----------------------------------------------------------------------
print("8. H4: cambio de fase, eventos, extraccion por fase")
m, Q = 1.0, 1e4
h0 = agua.evaluar_TP(293.15, 1e5).propiedades.h
c, _ = agua.T_saturacion(1e5)
r = me.resolver(solicitud("presion", P=("1", "bar"), m0=("1", "kg"), E0=("T", "293.15", "K"), Q=(repr(Q), "W"),
                          tf=("300", "s"), muestras=31))
check(r["estado"] == "resuelto", f"ebullicion {r['estado']} {codigos(r)}")
ev = {e["codigo"]: e["tiempo"] for e in r["resultados"]["eventos"]}
t_eb, t_seco = m * (c.liquido.h - h0) / Q, m * (c.vapor.h - h0) / Q
check(abs(ev.get("aparicion_fase", 0) - t_eb) < 1e-6 * t_eb, f"aparicion de vapor en {ev.get('aparicion_fase')} vs {t_eb}")
check(abs(ev.get("desaparicion_fase", 0) - t_seco) < 1e-6 * t_seco, f"secado en {ev.get('desaparicion_fase')} vs {t_seco}")
S, ts = series(r), r["resultados"]["tiempos"]
meseta = [S["volumen.dominio.T"][i] for i, t in enumerate(ts) if t_eb < t < t_seco]
check(meseta and max(abs(T - c.T) for T in meseta) < 1e-8, "T = Tsat durante la ebullicion")
check(all(abs(S["volumen.dominio.H"][i] - (m * h0 + Q * t)) < 1e-6 * m * c.vapor.h for i, t in enumerate(ts)),
      "H = H0 + Q t: el calor latente no se cuenta dos veces")
# condensacion en recipiente rigido: inicio cuando u alcanza u''(T*) con v''(T*) = V/m
Vg, m = 1.0, 2.0
from scipy.optimize import brentq
T_star = brentq(lambda T: agua.coexistencia(T).vapor.v - Vg / m, 300, 600)
u_star = agua.coexistencia(T_star).vapor.u
r = me.resolver(solicitud(V=(repr(Vg), "m3"), m0=(repr(m), "kg"), E0=("T", "500", "K"), Q=("-5", "kW"),
                          tf=("400", "s"), muestras=21))
U_ini = r["validacion"]["inicializacion"]["variables"]["volumen.dominio.U"]
t_cond = (m * u_star - U_ini) / -5000
ev = {e["codigo"]: e["tiempo"] for e in r["resultados"]["eventos"]}
check(r["estado"] == "resuelto" and abs(ev.get("aparicion_fase", -1) - t_cond) < 1e-6 * t_cond,
      f"condensacion en {ev.get('aparicion_fase')} vs {t_cond}")
# politica monofasica: se detiene en el evento, con muestras certificadas hasta alli
r = me.resolver(solicitud("presion", P=("1", "bar"), m0=("1", "kg"), E0=("T", "293.15", "K"), Q=(repr(1e4), "W"),
                          tf=("300", "s"), muestras=31, politica={"cantidad": "monofasico", "cambioInterno": "prohibido",
                                                                  "evaluacion": "equilibrio_estable"}))
check(r["estado"] == "parcial" and max(r["resultados"]["tiempos"]) <= t_eb * (1 + 1e-6)
      and "MOTOR_ENS_DETENIDO_CAMBIO_FASE_PROHIBIDO" in codigos(r), "cambio de fase prohibido: parcial en el evento")
# extraccion por fase frente a mezcla homogenea en coexistencia
base_x = dict(V=("1", "m3"), m0=("100", "kg"), E0=("T", "400", "K"), Q=None, tf=("20", "s"), muestras=5)
rl = me.resolver(solicitud(**base_x, corrientes=[{"id": 2, "sentido": "salida", "F": ("1", "kg/s"),
                                                  "extraccion": {"tipo": "fase", "fase": "liquido"}}]))
rv = me.resolver(solicitud(**base_x, corrientes=[{"id": 2, "sentido": "salida", "F": ("1", "kg/s"),
                                                  "extraccion": {"tipo": "fase", "fase": "vapor"}}]))
rh = me.resolver(solicitud(**base_x, corrientes=[{"id": 2, "sentido": "salida", "F": ("1", "kg/s"),
                                                  "extraccion": {"tipo": "mezcla_homogenea"}}]))
e0 = rl["resultados"]["estadosTermodinamicos"][0]
hl = next(f for f in e0["fases"] if f["tipo"] == "liquido")["propiedades"]["h"]
hv = next(f for f in e0["fases"] if f["tipo"] == "vapor")["propiedades"]["h"]
check(abs(series(rl)["corriente.2.h"][0] - hl) < 1e-6 and abs(series(rv)["corriente.2.h"][0] - hv) < 1e-6
      and abs(series(rh)["corriente.2.h"][0] - e0["mezcla"]["h"]) < 1e-6, "h extraida: liquido, vapor, mezcla")
Ul, Uv, Uh = (series(x)["volumen.dominio.U"][-1] for x in (rl, rv, rh))
check(Uv < Uh < Ul, "extraer vapor saca mas energia que la mezcla, y esta mas que el liquido")
# fase ausente: extraer vapor de un liquido comprimido
r = me.resolver(solicitud(V=("0.01", "m3"), m0=("10", "kg"), E0=("U", "1000", "kJ"), Q=None, tf=("2", "s"),
                          corrientes=[{"id": 2, "sentido": "salida", "F": ("0.1", "kg/s"),
                                       "extraccion": {"tipo": "fase", "fase": "vapor"}}]))
check(r["estado"] == "parcial" and "MOTOR_ENS_DETENIDO_FASE_AUSENTE" in codigos(r)
      and r["resultados"]["tiempos"] == [0.0], f"fase ausente en t=0: {r['estado']} {codigos(r)}")
# el liquido extraido se agota durante la trayectoria: evento y detencion, sin h inventada
r = me.resolver(solicitud(V=("1", "m3"), m0=("5", "kg"), E0=("T", "400", "K"), Q=None, tf=("20", "s"), muestras=21,
                          corrientes=[{"id": 2, "sentido": "salida", "F": ("0.5", "kg/s"),
                                       "extraccion": {"tipo": "fase", "fase": "liquido"}}]))
cods = [e["codigo"] for e in r["resultados"]["eventos"]]
check(r["estado"] == "parcial" and "fase_ausente" in cods and "MOTOR_ENS_DETENIDO_FASE_AUSENTE" in codigos(r),
      f"liquido agotado durante la trayectoria: {r['estado']} {cods} {codigos(r)}")
# El agotamiento se detecta cuando una etapa necesita la fase y ya no existe; el paso se
# reduce hasta 1e-10 tf. El ultimo estado certificado conserva solo una traza de liquido.
ultimo = r["resultados"]["estadosTermodinamicos"][-1]
liq = sum(f["fraccionMasica"] for f in ultimo["fases"] if f["tipo"] == "liquido")
check(liq < 1e-6 and 0 < r["resultados"]["tiempos"][-1] < 20, f"al detenerse queda una traza de liquido {liq:.2e}")


# ----------------------------------------------------------------------
print("9. Dominio y agotamiento durante la trayectoria")
r = me.resolver(solicitud(Q=("200", "kW"), tf=("300", "s"), muestras=31))
check(r["estado"] == "parcial" and any(e["codigo"] == "salida_dominio" for e in r["resultados"]["eventos"])
      and max(series(r)["volumen.dominio.P"]) <= 1e8, "calentamiento rigido hasta P > 100 MPa: parcial")
r = me.resolver(solicitud(V=("1", "m3"), m0=("5", "kg"), E0=("T", "400", "K"), Q=None, tf=("10", "s"), muestras=11,
                          corrientes=[{"id": 2, "sentido": "salida", "F": ("1", "kg/s")}],
                          extracciones={"2": {"tipo": "mezcla_homogenea"}}))
check(r["estado"] == "parcial" and min(series(r)["volumen.dominio.m.1"]) > 0
      and all(e["mezcla"] for e in r["resultados"]["estadosTermodinamicos"]), "vaciado hasta agotar: parcial")
r = me.resolver(solicitud(E0=("U", "-100", "kJ")))
check(r["estado"] == "invalido" and r["resultados"] is None, "estado inicial invalido: no integra")


# ----------------------------------------------------------------------
print("10. Frontera HTTP y solicitudes reales del frontend")


def pedir(metodo, ruta, cuerpo=None):
    async def hacer():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://v") as cl:
            return await cl.request(metodo, ruta, json=cuerpo)
    return asyncio.run(hacer())


cap = pedir("GET", "/motor/ensamblajes/capacidades")
check(cap.status_code == 200 and cap.json()["fronteras"] == ["rigida", "presion_prescrita"], "capacidades")
for n in ("rigida_cerrada_U0", "rigida_cerrada_T0", "abierta_presion", "dos_cierres", "rigida_con_P"):
    s = json.loads((FIX / f"{n}.json").read_text(encoding="utf-8"))["solicitud"]
    h = pedir("POST", "/motor/ensamblajes/validar", s)
    check(h.status_code == 200 and h.json()["solicitudId"] == s["solicitudId"], f"{n}: validar HTTP")
    json.dumps(h.json(), allow_nan=False)
h = pedir("POST", "/motor/ensamblajes/resolver",
          json.loads((FIX / "rigida_cerrada_U0.json").read_text(encoding="utf-8"))["solicitud"])
check(h.status_code == 200 and h.json()["estado"] == "resuelto", "resolver HTTP con la hoja real")
json.dumps(h.json(), allow_nan=False)
check(pedir("POST", "/motor/ensamblajes/validar", [1]).json()["recuento"]["estado"] == "no_evaluable",
      "cuerpo no objeto")

print("12. Guarda presionPrescrita (M0)")
for frontera, pp, esperado in (("presion", True, False), ("presion", False, True), ("rigida", False, False),
                               ("rigida", True, True), ("presion", None, False), ("rigida", None, False)):
    s = solicitud(frontera, Q=("0", "W"))
    if pp is None:
        s["volumen"]["formulacionEnergia"].pop("presionPrescrita", None)
    else:
        s["volumen"]["formulacionEnergia"]["presionPrescrita"] = pp
    hay = "MOTOR_ENS_PRESION_PRESCRITA" in codigos(me.validar(s)[0])
    check(hay == esperado, f"presionPrescrita={pp} con frontera {frontera}: conflicto={hay}")

print("11. Fraccion de vapor q frente a las fases publicadas (incidencia de integracion)")
# Convencion: q = suma de fraccionMasica de las fases de tipo 'vapor' presentes, dentro o
# fuera de la campana; un fluido supercritico no es vapor (q = 0). Misma definicion que
# frontend/app/motor/lectorEnsamblajeTermodinamico.ts.


def q_fases(e):
    return sum(f["fraccionMasica"] for f in e["fases"] if f["tipo"] == "vapor")


def comprobar_q(r, nombre, tipos_esperados):
    ini = r["validacion"]["inicializacion"]
    check(abs(ini["variables"]["volumen.dominio.q"] - q_fases(ini["estadoTermodinamico"])) <= 1e-12,
          f"{nombre}: q inicial {ini['variables']['volumen.dominio.q']} frente a las fases")
    qs = series(r)["volumen.dominio.q"]
    vistos = set()
    for k, e in enumerate(r["resultados"]["estadosTermodinamicos"]):
        vistos |= {f["tipo"] for f in e["fases"]}
        vistos.add(len(e["fases"]))
        check(abs(qs[k] - q_fases(e)) <= 1e-12, f"{nombre}: q[{k}] = {qs[k]} frente a las fases {q_fases(e)}")
    check(tipos_esperados <= vistos, f"{nombre}: cubre {tipos_esperados}, visto {vistos}")


comprobar_q(me.resolver(solicitud("presion", P=("1", "bar"), m0=("1", "kg"), E0=("T", "293.15", "K"),
                                  Q=("10", "kW"), tf=("300", "s"), muestras=31)),
            "ebullicion (liquido -> coexistencia -> vapor sobrecalentado)", {"liquido", "vapor", 1, 2})
comprobar_q(me.resolver(solicitud(V=("1", "m3"), m0=("2", "kg"), E0=("T", "500", "K"), Q=("-5", "kW"),
                                  tf=("400", "s"), muestras=21)),
            "condensacion (vapor sobrecalentado -> coexistencia)", {"vapor", 1, 2})
comprobar_q(me.resolver(solicitud("presion", P=("3e5 + 2e5*sin(0.05*t)", "Pa"), m0=("1", "kg"),
                                  E0=("T", "500", "K"), Q=None, tf=("100", "s"), muestras=11, rtol=1e-10)),
            "vapor sobrecalentado", {"vapor", 1})
comprobar_q(me.resolver(solicitud(muestras=6)), "liquido comprimido", {"liquido", 1})
# T > Tc y P > Pc: fluido. (Por encima de Tc con P <= Pc la convencion de H1 lo llama vapor, q = 1.)
r = me.resolver(solicitud(V=("10", "L"), m0=("3", "kg"), E0=("T", "750", "K"), Q=("1", "kW"), tf=("60", "s"),
                          muestras=6))
comprobar_q(r, "fluido supercritico", {"fluido", 1})
check(all(q == 0.0 for q, e in zip(series(r)["volumen.dominio.q"], r["resultados"]["estadosTermodinamicos"])
          if e["fases"][0]["tipo"] == "fluido") and r["resultados"]["estadosTermodinamicos"][0]["fases"][0]["regimen"]
      == "supercritico", "fluido supercritico: q = 0 por convencion")
# frontera de evento con politica: la ultima muestra es el borde certificado, sin seguir integrando
r = me.resolver(solicitud("presion", P=("1", "bar"), m0=("1", "kg"), E0=("T", "293.15", "K"), Q=("10", "kW"),
                          tf=("300", "s"), muestras=31, politica={"cantidad": "monofasico",
                                                                  "cambioInterno": "prohibido",
                                                                  "evaluacion": "equilibrio_estable"}))
comprobar_q(r, "cambio prohibido", {"liquido", 1})
check(r["estado"] == "parcial" and r["resultados"]["tiempos"][-1] == r["resultados"]["eventos"][-1]["tiempo"],
      "la ultima muestra es el instante del evento que detiene la politica")

print()
if FALLOS:
    print(f"{len(FALLOS)} FALLOS de {CHECKS[0]} comprobaciones")
    sys.exit(1)
print(f"OK: {CHECKS[0]} comprobaciones")
