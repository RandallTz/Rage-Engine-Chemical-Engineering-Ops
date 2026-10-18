"""
Validacion de la termodinamica del motor independiente: hitos H0/H1
(agua pura, evaluacion T/P) y contrato de revision 1.

Que se comprueba y contra que:

  * Valores PUBLICADOS de IAPWS R6-95(2018), tablas 6, 7 y 8. Es la
    referencia principal: no depende de esta implementacion.
  * IF97 (IAPWS R7-97(2012)) como formulacion INDEPENDIENTE: es otra
    ecuacion, ajustada a IAPWS-95, con regiones y forma funcional
    propias. Coincidir con ella no es una segunda medida experimental,
    pero un error de rama, de unidades o de referencia la separaria mucho
    mas que su diferencia documentada con IAPWS-95.
  * Identidades y derivadas de la propia EOS (h = u + Pv, g = h - Ts,
    relacion de Maxwell, cp y cv frente a diferencias finitas).
  * Que la estabilidad DETECTA estados metastables (si no los detectara,
    certificar seria una formalidad).
  * Contrato: cada rechazo con su estado, codigo, ruta y evaluacion null;
    unidades; ceros y nulls; ecos de IDs; aislamiento entre peticiones;
    frontera HTTP serializable.

Ejecutar desde la raiz del proyecto:
    python tests/validar_motor_termodinamica.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import asyncio

import chemicals.iapws as w
import httpx

from backend.main import app
from backend import motor_termodinamica as mt
from core import agua_iapws95 as agua

FALLOS = []
CHECKS = [0]


def check(cond, mensaje):
    CHECKS[0] += 1
    if not cond:
        FALLOS.append(mensaje)
        print("  FALLO:", mensaje)


def solicitud(T=(25, "degC"), P=(1, "bar"), **cambios):
    s = {
        "revision": 1, "solicitudId": "prueba-1", "propietarioId": "volumen:v1",
        "componentes": [{"id": 1, "nombre": "Agua", "simbolo": "A", "identidadQuimica": {"cas": "7732-18-5"}}],
        "declaracion": {
            "modelo": {"id": "agua-iapws95", "version": "1"},
            "especificacion": {"tipo": "TP", "T": {"valor": T[0], "unidad": T[1]},
                               "P": {"valor": P[0], "unidad": P[1]},
                               "composicion": {"base": "molar", "fracciones": {"1": 1}}},
            "politica": {"cantidad": "sin_restriccion", "cambioInterno": "permitido",
                         "evaluacion": "equilibrio_estable"},
        },
    }
    for ruta, valor in cambios.items():
        destino, claves = s, ruta.split("__")
        for k in claves[:-1]:
            destino = destino[int(k)] if isinstance(destino, list) else destino[k]
        if valor is _BORRAR:
            del destino[claves[-1]]
        elif isinstance(destino, list):
            destino[int(claves[-1])] = valor
        else:
            destino[claves[-1]] = valor
    return s


_BORRAR = object()


def rechazo(r, estado, codigo, ruta=None):
    ok = (r["estado"] == estado and r["evaluacion"] is None and r["diagnosticos"]
          and any(d["codigo"] == codigo and (ruta is None or d["ruta"] == ruta) for d in r["diagnosticos"]))
    return bool(ok)


# ----------------------------------------------------------------------
print("1. Valores publicados de IAPWS-95 (tablas 6, 7, 8)")
filas = agua.verificar()
for nombre, x, ref, err in filas:
    check(err <= 1e-8, f"{nombre}: {x!r} frente a {ref!r} (error {err:.2e})")
print(f"   {len(filas)} valores, error relativo maximo {max(f[3] for f in filas):.2e}")
check(agua.version_auditada(), "chemicals no es la version auditada")


# ----------------------------------------------------------------------
print("2. Contraste con IF97 (formulacion independiente)")
R97 = w.iapws97_R


def if97(T, P):
    reg = w.iapws97_identify_region_TP(T, P)
    if reg == 1:
        tau, pi = 1386.0 / T, P / 16.53e6
        g, gt, gp = (w.iapws97_G_region1(tau, pi), w.iapws97_dG_dtau_region1(tau, pi),
                     w.iapws97_dG_dpi_region1(tau, pi))
        return reg, R97 * T * pi * gp / P, R97 * T * tau * gt, R97 * (tau * gt - g)
    if reg == 2:
        tau, pi = 540.0 / T, P / 1e6
        g = w.iapws97_G0_region2(tau, pi) + w.iapws97_Gr_region2(tau, pi)
        gt = w.iapws97_dG0_dtau_region2(tau, pi) + w.iapws97_dGr_dtau_region2(tau, pi)
        gp = 1.0 / pi + w.iapws97_dGr_dpi_region2(tau, pi)
        return reg, R97 * T * pi * gp / P, R97 * T * tau * gt, R97 * (tau * gt - g)
    if reg == 3:
        rho = w.iapws97_region3_rho(T, P)
        tau, d = 647.096 / T, rho / 322.0
        f, ft, fd = (w.iapws97_A_region3(tau, d), w.iapws97_dA_dtau_region3(tau, d),
                     w.iapws97_dA_ddelta_region3(tau, d))
        return reg, 1 / rho, R97 * T * (tau * ft + d * fd), R97 * (tau * ft - f)
    return reg, None, None, None


# La implementacion de IF97 se comprueba contra sus propios valores
# publicados (tabla 33, region 3; las regiones 1, 2 y 4 ya las verifica
# core/vapor_if97.verificar()).
for T, rho, P, h in [(650, 500, 0.255837018e2, 0.186343019e4), (650, 200, 0.222930643e2, 0.237512401e4),
                     (750, 500, 0.783095639e2, 0.225868845e4)]:
    tau, d = 647.096 / T, rho / 322.0
    fd, ft = w.iapws97_dA_ddelta_region3(tau, d), w.iapws97_dA_dtau_region3(tau, d)
    check(abs(rho * R97 * T * d * fd / 1e6 - P) / P < 1e-8, f"IF97 tabla 33 P({T}, {rho})")
    check(abs(R97 * T * (tau * ft + d * fd) / 1e3 - h) / h < 1e-8, f"IF97 tabla 33 h({T}, {rho})")

peor = {"v": 0.0, "h": 0.0, "s": 0.0}
n_if97 = 0
tipos_vistos = set()
for T in [273.16, 280, 300, 350, 373.15, 400, 450, 500, 550, 600, 625, 640, 660, 700, 800, 900, 1073.15]:
    for P in [100, 1e3, 1e4, 101325, 1e6, 5e6, 1e7, 2e7, 3e7, 5e7, 1e8]:
        try:
            e = agua.evaluar_TP(T, P)
        except agua.FueraDeAlcance as x:
            check(x.motivo in ("saturacion", "region_critica"), f"rechazo inesperado {x.motivo} en {T}, {P}")
            continue
        reg, v, h, s = if97(T, P)
        check(v is not None, f"IF97 sin region en {T}, {P}")
        if v is None:
            continue
        n_if97 += 1
        tipos_vistos.add(e.tipo)
        p = e.propiedades
        peor["v"] = max(peor["v"], abs(p.v - v) / v)
        peor["h"] = max(peor["h"], abs(p.h - h))
        peor["s"] = max(peor["s"], abs(p.s - s))
        # La fase: IF97 region 1 es liquido, region 2 vapor (o gas por encima de T_c).
        if reg == 1:
            check(e.tipo == "liquido", f"IF97 region 1 pero {e.tipo} en {T} K, {P} Pa")
        if reg == 2 and T < agua.TC:
            check(e.tipo == "vapor", f"IF97 region 2 pero {e.tipo} en {T} K, {P} Pa")
# Tolerancias: el doble, aproximadamente, de la mayor diferencia medida en
# esta malla (dv/v 4.9e-4, dh 0.51 kJ/kg, ds 0.83 J/(kg K)), que son del
# orden de la consistencia que IF97 declara con IAPWS-95. Un error de rama
# daria dv/v ~ 1 y uno de referencia o de unidades, dh de kJ/kg o mas.
check(peor["v"] < 1e-3, f"dv/v frente a IF97 = {peor['v']:.3g}")
check(peor["h"] < 1.0e3, f"dh frente a IF97 = {peor['h']:.3g} J/kg")
check(peor["s"] < 2.0, f"ds frente a IF97 = {peor['s']:.3g} J/(kg K)")
check(tipos_vistos == {"liquido", "vapor", "fluido"}, f"tipos cubiertos: {tipos_vistos}")
print(f"   {n_if97} estados; max |dv/v| {peor['v']:.2e}, |dh| {peor['h']:.0f} J/kg, |ds| {peor['s']:.2f} J/(kg K)")


# ----------------------------------------------------------------------
print("3. Identidades y derivadas de la EOS")
for T, P in [(298.15, 1e5), (300, 3000), (500, 2e7), (700, 3e7), (1000, 1e6), (273.16, 1e8)]:
    e = agua.evaluar_TP(T, P)
    p = e.propiedades
    RT = agua.R * T
    check(abs(p.h - p.u - p.P * p.v) / RT < 1e-13, f"h = u + Pv en {T}, {P}")
    check(abs(p.g - (p.h - T * p.s)) / RT < 1e-12, f"g = h - Ts en {T}, {P}")
    check(e.residuo_derivadas < agua.TOL_DERIVADAS, f"cp/cv frente a diferencias en {T}, {P}")
    # Maxwell: (ds/drho)_T = -(dP/dT)_rho / rho^2
    dr = 1e-6 * p.rho
    ds_dr = (agua.propiedades(T, p.rho + dr).s - agua.propiedades(T, p.rho - dr).s) / (2 * dr)
    check(abs(ds_dr + p.dP_dT_rho / p.rho ** 2) <= 1e-6 * abs(p.dP_dT_rho / p.rho ** 2),
          f"relacion de Maxwell en {T}, {P}")
    check(p.cp > p.cv > 0 and p.dP_drho_T > 0, f"cp > cv > 0 y estabilidad mecanica en {T}, {P}")
    # (ds/dT)_P = cp/T, por diferencias
    dT = 1e-5 * T
    rama = [r for r in agua.ramas(T)[0] if r[0] in (e.tipo, "fluido")][0]
    s_mas = agua.propiedades(T + dT, agua.densidad(T + dT, P, rama[1], rama[2])).s
    s_menos = agua.propiedades(T - dT, agua.densidad(T - dT, P, rama[1], rama[2])).s
    check(abs((s_mas - s_menos) / (2 * dT) - p.cp / T) < 1e-6 * p.cp / T, f"(ds/dT)_P = cp/T en {T}, {P}")


# ----------------------------------------------------------------------
print("4. La estabilidad detecta metastables y la saturacion es indeterminada")
for T in (300.0, 450.0, 600.0):
    ramas_T, sat = agua.ramas(T)
    # liquido sobrecalentado: rama liquida por debajo de Psat
    rho_meta = agua.densidad(T, 0.9 * sat.Psat, sat.rho_l * 0.97, sat.rho_l)
    est = agua.estabilidad(T, rho_meta, ramas_T + [("metastable", sat.rho_l * 0.97, sat.rho_l)])
    check(est.residuo > 1e-6, f"liquido metastable a {T} K no detectado (residuo {est.residuo:.2e})")
    # vapor subenfriado
    rho_v = agua.densidad(T, 1.05 * sat.Psat, sat.rho_v, sat.rho_v * 1.2)
    est = agua.estabilidad(T, rho_v, ramas_T)
    check(est.residuo > 1e-6, f"vapor metastable a {T} K no detectado (residuo {est.residuo:.2e})")
    for f in (1.0, 1 + 5e-7, 1 - 5e-7):
        try:
            agua.evaluar_TP(T, sat.Psat * f)
            check(False, f"T/P en saturacion a {T} K evaluado")
        except agua.FueraDeAlcance as x:
            check(x.motivo == "saturacion", f"motivo de saturacion a {T} K: {x.motivo}")
    for f, tipo in ((1 + 3e-6, "liquido"), (1 - 3e-6, "vapor")):
        e = agua.evaluar_TP(T, sat.Psat * f)
        check(e.tipo == tipo and e.estabilidad.residuo <= agua.TOL_ESTABILIDAD,
              f"a {f} Psat({T}) se esperaba {tipo} estable")

# Aislamiento: el orden de las evaluaciones no cambia nada
a1 = mt.evaluar(solicitud())
mt.evaluar(solicitud(T=(500, "K"), P=(5, "kPa")))
a2 = mt.evaluar(solicitud())
check(json.dumps(a1, sort_keys=True) == json.dumps(a2, sort_keys=True), "la evaluacion depende del orden")


# ----------------------------------------------------------------------
print("5. Contrato: estados evaluados")
r = mt.evaluar(solicitud())
check(r["estado"] == "evaluado" and r["solicitudId"] == "prueba-1" and r["revision"] == 1, "eco y estado")
ev = r["evaluacion"]
check(ev["T"] == 298.15 and ev["P"] == 1e5, "T y P normalizadas a K y Pa")
check(ev["fases"][0]["tipo"] == "liquido" and ev["fases"][0]["id"] == "liquido-1", "fase liquida")
check(abs(1 / ev["mezcla"]["v"] - 997.047) < 1e-3, f"densidad a 25 C y 1 bar: {1 / ev['mezcla']['v']}")
ids = {v["id"]: v for v in ev["verificaciones"]}
check({"estabilidad", "dominio", "ecuacion_estado", "identidad_h_u_Pv", "derivadas",
       "saturacion", "reconstruccion_material"} <= set(ids), f"verificaciones: {sorted(ids)}")
for v in ev["verificaciones"]:
    check(v["estado"] != "cumple" or v["residuo"] is None or v["residuo"] <= v["tolerancia"],
          f"verificacion {v['id']} con residuo mayor que tolerancia")
check(ev["componentes"][0] == {"id": 1, "cas": "7732-18-5", "masaMolarKgMol": 0.018015268,
                               "fuente": mt.FUENTE_MASA_MOLAR}, "componente con masa molar del modelo")
check(ev["estabilidad"]["alcance"] == ["liquido", "vapor", "fluido"], "alcance de estabilidad")

# Unidades de T y P: el mismo estado
base = mt.evaluar(solicitud(T=(350, "K"), P=(2, "bar")))["evaluacion"]
for T, P in [((76.85, "degC"), (200, "kPa")), ((170.33, "degF"), (2e5, "Pa"))]:
    otro = mt.evaluar(solicitud(T=T, P=P))["evaluacion"]
    check(abs(otro["T"] - base["T"]) < 1e-9 and abs(otro["mezcla"]["h"] - base["mezcla"]["h"]) < 1e-6 * abs(base["mezcla"]["h"]),
          f"unidades {T}, {P}")

# Base masica, ID distinto de 1 y masa molar coincidente
s = solicitud()
s["componentes"][0]["id"] = 7
s["componentes"][0]["masaMolar"] = {"cantidad": {"valor": 18.015268, "unidad": "g/mol"}, "fuente": "IAPWS"}
s["declaracion"]["especificacion"]["composicion"] = {"base": "masica", "fracciones": {"7": 1}}
r = mt.evaluar(s)
check(r["estado"] == "evaluado" and r["evaluacion"]["composicionMolar"] == {"7": 1.0}
      and r["evaluacion"]["componentes"][0]["id"] == 7, "ID 7 y base masica")
check(any(v["id"] == "masa_molar" for v in r["evaluacion"]["verificaciones"]), "verificacion de masa molar")

# Vapor, supercritico, gas por encima de Tc
for T, P, tipo, regimen in [(400, 1e4, "vapor", "ordinario"), (900, 50e6, "fluido", "supercritico"),
                            (900, 1e6, "vapor", "ordinario"), (600, 50e6, "liquido", "ordinario")]:
    r = mt.evaluar(solicitud(T=(T, "K"), P=(P, "Pa")))
    f = r["evaluacion"]["fases"][0]
    check((f["tipo"], f["regimen"]) == (tipo, regimen), f"{T} K, {P} Pa: {f['tipo']} {f['regimen']}")
    check(r["evaluacion"]["mezcla"].get("cp") is not None, "cp publicado en una fase")
check(not any(v["id"] == "saturacion" for v in mt.evaluar(solicitud(T=(900, "K"), P=(1e6, "Pa")))["evaluacion"]["verificaciones"]),
      "sin verificacion de saturacion por encima de Tc")

# Politicas
r = mt.evaluar(solicitud(declaracion__politica__cantidad="monofasico"))
check(r["estado"] == "evaluado" and any(v["id"] == "politica_fases" for v in r["evaluacion"]["verificaciones"]),
      "monofasico compatible")
r = mt.evaluar(solicitud(declaracion__politica__cambioInterno="prohibido"))
cambio = [v for v in r["evaluacion"]["verificaciones"] if v["id"] == "cambio_interno"]
check(cambio and cambio[0]["estado"] == "no_evaluable" and cambio[0]["residuo"] is None, "cambio interno no evaluable")
r = mt.evaluar(solicitud(declaracion__politica__tiposPermitidos=["liquido"]))
check(r["estado"] == "evaluado", "tipo permitido compatible")


# ----------------------------------------------------------------------
print("6. Contrato: rechazos con diagnostico")
casos = [
    ("saturacion 100 C", solicitud(T=(373.15, "K"), P=(agua.saturacion(373.15).Psat, "Pa")),
     "incompleto", "MOTOR_ESTADO_SATURACION_INDETERMINADA", "declaracion.especificacion"),
    ("fase incompatible", solicitud(declaracion__politica__tiposPermitidos=["vapor"]),
     "invalido", "MOTOR_ESTADO_FASE_INCOMPATIBLE", "declaracion.politica.tiposPermitidos"),
    ("solo solido permitido", solicitud(declaracion__politica__tiposPermitidos=["solido"]),
     "invalido", "MOTOR_ESTADO_FASE_INCOMPATIBLE", None),
    ("region critica", solicitud(T=(647, "K"), P=(220, "bar")),
     "no_soportado", "MOTOR_ESTADO_REGION_CRITICA", None),
    ("hielo / bajo el punto triple", solicitud(T=(-5, "degC")),
     "no_soportado", "MOTOR_ESTADO_FUERA_DE_DOMINIO", "declaracion.especificacion.T"),
    ("P sobre el dominio", solicitud(P=(2000, "bar")),
     "no_soportado", "MOTOR_ESTADO_FUERA_DE_DOMINIO", "declaracion.especificacion.P"),
    ("T null", solicitud(T=(None, "K")),
     "incompleto", "MOTOR_ESTADO_DATO_SIN_DECLARAR", "declaracion.especificacion.T"),
    ("unidad", solicitud(P=(1, "atm")),
     "invalido", "MOTOR_ESTADO_UNIDAD_INCOMPATIBLE", "declaracion.especificacion.P"),
    ("T absoluta negativa", solicitud(T=(-300, "degC")),
     "invalido", "MOTOR_ESTADO_FUERA_DE_MAGNITUD", "declaracion.especificacion.T"),
    ("T no finita", solicitud(T=(float("inf"), "K")),
     "invalido", "MOTOR_ESTADO_DATO_INVALIDO", "declaracion.especificacion.T"),
    ("sobreespecificado", solicitud(declaracion__especificacion__h={"valor": 100, "unidad": "kJ/kg"}),
     "invalido", "MOTOR_ESTADO_SOBREESPECIFICADO", "declaracion.especificacion.h"),
    ("campo de mas", solicitud(extra=1), "invalido", "MOTOR_ESTADO_CAMPO_NO_ADMITIDO", "extra"),
    ("revision", solicitud(revision=2), "invalido", "MOTOR_ESTADO_REVISION", "revision"),
    ("modelo desconocido", solicitud(declaracion__modelo={"id": "peng-robinson", "version": "1"}),
     "no_soportado", "MOTOR_ESTADO_MODELO_NO_PUBLICADO", "declaracion.modelo"),
    ("version distinta", solicitud(declaracion__modelo={"id": "agua-iapws95", "version": "2"}),
     "no_soportado", "MOTOR_ESTADO_MODELO_NO_PUBLICADO", "declaracion.modelo"),
    ("sin identidad", solicitud(componentes__0__identidadQuimica=_BORRAR),
     "incompleto", "MOTOR_ESTADO_IDENTIDAD_SIN_DECLARAR", "componentes.1.identidadQuimica"),
    ("CAS con digito de control erroneo", solicitud(componentes__0__identidadQuimica={"cas": "7732-18-4"}),
     "invalido", "MOTOR_ESTADO_CAS_INVALIDO", "componentes.1.identidadQuimica.cas"),
    ("etanol", solicitud(componentes__0__identidadQuimica={"cas": "64-17-5"}),
     "no_soportado", "MOTOR_ESTADO_COMPONENTE_NO_SOPORTADO", "componentes.1.identidadQuimica.cas"),
    ("proveedorId", solicitud(componentes__0__identidadQuimica={"cas": "7732-18-5", "proveedorId": "x:agua"}),
     "no_soportado", "MOTOR_ESTADO_IDENTIDAD_NO_VERIFICABLE", "componentes.1.identidadQuimica.proveedorId"),
    ("masa molar contradictoria",
     solicitud(componentes__0__masaMolar={"cantidad": {"valor": 18.0, "unidad": "g/mol"}, "fuente": "redondeo"}),
     "invalido", "MOTOR_ESTADO_MASA_MOLAR_CONTRADICTORIA", "componentes.1.masaMolar.cantidad"),
    ("composicion que no suma 1",
     solicitud(declaracion__especificacion__composicion={"base": "molar", "fracciones": {"1": 0.9}}),
     "invalido", "MOTOR_ESTADO_COMPOSICION_NO_NORMALIZADA", "declaracion.especificacion.composicion.fracciones"),
    ("fraccion null",
     solicitud(declaracion__especificacion__composicion={"base": "molar", "fracciones": {"1": None}}),
     "incompleto", "MOTOR_ESTADO_DATO_SIN_DECLARAR", "declaracion.especificacion.composicion.fracciones.1"),
    ("UV con cantidad cero total",
     solicitud(declaracion__especificacion={"tipo": "UV", "U": {"valor": 1, "unidad": "kJ"},
                                            "V": {"valor": 1, "unidad": "L"},
                                            "cantidades": {"base": "masica", "valores": {"1": {"valor": 0, "unidad": "kg"}}}}),
     "invalido", "MOTOR_ESTADO_FUERA_DE_MAGNITUD", "declaracion.especificacion.cantidades.valores"),
    ("tipo desconocido", solicitud(declaracion__especificacion={"tipo": "TV"}),
     "invalido", "MOTOR_ESTADO_ESPECIFICACION_DESCONOCIDA", "declaracion.especificacion.tipo"),
    ("politica invalida", solicitud(declaracion__politica__evaluacion="rama_forzada"),
     "invalido", "MOTOR_ESTADO_POLITICA_INVALIDA", "declaracion.politica.evaluacion"),
]
dos = solicitud()
dos["componentes"].append({"id": 2, "nombre": "Agua otra vez", "simbolo": "W", "identidadQuimica": {"cas": "7732-18-5"}})
dos["declaracion"]["especificacion"]["composicion"]["fracciones"] = {"1": 0.5, "2": 0.5}
casos.append(("misma sustancia dos veces", dos, "invalido", "MOTOR_ESTADO_IDENTIDAD_DUPLICADA", None))
mezcla = solicitud()
mezcla["componentes"].append({"id": 2, "nombre": "Etanol", "simbolo": "E", "identidadQuimica": {"cas": "64-17-5"}})
mezcla["declaracion"]["especificacion"]["composicion"]["fracciones"] = {"1": 1, "2": 0}
casos.append(("especie ausente con cero explicito sigue sin modelo", mezcla, "no_soportado",
              "MOTOR_ESTADO_COMPONENTE_NO_SOPORTADO", "componentes.2.identidadQuimica.cas"))
falta = solicitud()
del falta["declaracion"]["especificacion"]["composicion"]["fracciones"]["1"]
casos.append(("componente sin fraccion", falta, "incompleto", "MOTOR_ESTADO_DATO_SIN_DECLARAR",
              "declaracion.especificacion.composicion.fracciones.1"))
casos.append(("cuerpo no objeto", [1, 2], "invalido", "MOTOR_ESTADO_FORMA_INVALIDA", ""))

for nombre, s, estado, codigo, ruta in casos:
    r = mt.evaluar(s)
    check(rechazo(r, estado, codigo, ruta), f"{nombre}: {r['estado']} {[(d['codigo'], d['ruta']) for d in r['diagnosticos']]}")
    check(all(d["propietarioId"] == (s.get("propietarioId", "") if isinstance(s, dict) else "")
              for d in r["diagnosticos"]), f"{nombre}: propietario en diagnosticos")
    check(r["solicitudId"] == (s.get("solicitudId", "") if isinstance(s, dict) else ""), f"{nombre}: eco del id")
sat = mt.evaluar(casos[0][1])
check(sat["diagnosticos"][0].get("alternativas") == mt.ALTERNATIVAS_SATURACION,
      "la saturacion TP ofrece PH, UP y UV, ya publicadas (H3)")


# ----------------------------------------------------------------------
print("7. Frontera HTTP")


class ClienteASGI:
    """Cliente sincrono sin abrir puerto; `TestClient` no arranca con las
    versiones fijas del proyecto (ver tests/validar_api.py)."""

    def _pedir(self, metodo, ruta, **kw):
        async def hacer():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                         base_url="http://validacion") as c:
                return await c.request(metodo, ruta, **kw)
        return asyncio.run(hacer())

    def get(self, ruta):
        return self._pedir("GET", ruta)

    def post(self, ruta, json=None):
        return self._pedir("POST", ruta, json=json)


cliente = ClienteASGI()
cap = cliente.get("/motor/termodinamica/capacidades")
check(cap.status_code == 200, "capacidades HTTP 200")
c = cap.json()
# M1/M2: los paquetes de mezcla se publican de forma aditiva; el agua sigue siendo el primero e igual.
check(c["revision"] == 1 and [x["id"] for x in c["modelos"]] == ["agua-iapws95", "mezcla-ideal", "nrtl-chemsep",
                                                                "nrtl-lle-agua-butanol", "unifac-original-public",
                                                                "unifac-dortmund-public", "unifac-original-lle-public",
                                                                "agua-iapws95-hielo-ih"]
      and all(x["dinamica"] is False for x in c["modelos"]), "capacidades")
m = c["modelos"][0]
check(m["especificaciones"] == ["TP", "PH", "UP", "UV"] and m["componentesCAS"] == ["7732-18-5"],
      "TP, PH, UP, UV y solo agua")
check(m["dominio"] == {"T": [273.16, 1073.15], "P": [100.0, 1e8]}, f"dominio {m['dominio']}")
for s in [solicitud(), casos[0][1], solicitud(extra=1)]:
    h = cliente.post("/motor/termodinamica/evaluar", json=s)
    check(h.status_code == 200 and h.headers["content-type"].startswith("application/json"), "evaluar HTTP 200")
    check(json.loads(h.text) == json.loads(json.dumps(mt.evaluar(s), allow_nan=False)), "JSON sin NaN e igual")
# null: el eco conserva evaluacion null y residuo null como null
h = cliente.post("/motor/termodinamica/evaluar", json=casos[0][1]).json()
check("evaluacion" in h and h["evaluacion"] is None, "evaluacion null presente en el rechazo")
h = cliente.post("/motor/termodinamica/evaluar", json=solicitud()).json()
dom = [v for v in h["evaluacion"]["verificaciones"] if v["id"] == "dominio"][0]
check("residuo" in dom and dom["residuo"] is None, "residuo null presente")
check("cp" in h["evaluacion"]["mezcla"], "cp en fase unica")


print()
if FALLOS:
    print(f"{len(FALLOS)} FALLOS de {CHECKS[0]} comprobaciones")
    sys.exit(1)
print(f"OK: {CHECKS[0]} comprobaciones")
