"""
Validacion de H3: coexistencia liquido-vapor del agua pura y
especificaciones PH, UP y UV del contrato de revision 1.

Referencias y su relacion fisica:

  * Valores PUBLICADOS de IAPWS R6-95(2018), tabla 8 (saturacion): la
    referencia principal de la coexistencia.
  * IF97 region 4 y regiones 1/2 en la saturacion (core/vapor_if97.py):
    formulacion independiente ajustada a IAPWS-95; detecta errores de
    rama, referencia o unidades, no mide exactitud experimental.
  * `chemicals.iapws.iapws95_saturation`: OTRO resolvedor de Maxwell sobre
    la misma EOS (otro algoritmo, otras semillas). Sirve para construir
    estados bifasicos de prueba sin usar el flash que se esta probando; no
    es una segunda referencia fisica.
  * Ida y vuelta TP -> PH/UP/UV: el estado TP de H1 (otro camino de
    calculo: T y P dadas) debe recuperarse.

Ejecutar desde la raiz del proyecto:
    python tests/validar_motor_termodinamica_h3.py
"""

import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import chemicals.iapws as w

from backend import motor_termodinamica as mt
from core import agua_iapws95 as agua
from core import vapor_if97

FALLOS, CHECKS = [], [0]


def check(cond, mensaje):
    CHECKS[0] += 1
    if not cond:
        FALLOS.append(mensaje)
        print("  FALLO:", mensaje)


def base(especificacion, politica=None, masa_molar=None, cid=1):
    comp = {"id": cid, "nombre": "Agua", "simbolo": "A", "identidadQuimica": {"cas": "7732-18-5"}}
    if masa_molar:
        comp["masaMolar"] = masa_molar
    return {
        "revision": 1, "solicitudId": "h3", "propietarioId": "volumen:v1", "componentes": [comp],
        "declaracion": {"modelo": {"id": "agua-iapws95", "version": "1"}, "especificacion": especificacion,
                        "politica": {"cantidad": "sin_restriccion", "cambioInterno": "permitido",
                                     "evaluacion": "equilibrio_estable", **(politica or {})}},
    }


def q_(x, u):
    return {"valor": x, "unidad": u}


def PH(P, h, **kw):
    return base({"tipo": "PH", "P": q_(P, "Pa"), "h": q_(h, "J/kg"),
                 "composicion": {"base": "molar", "fracciones": {"1": 1}}}, **kw)


def UP(U, P, m=1.0, unidadU="J", base_n="masica", unidad_n="kg", **kw):
    return base({"tipo": "UP", "U": q_(U, unidadU), "P": q_(P, "Pa"),
                 "cantidades": {"base": base_n, "valores": {"1": q_(m, unidad_n)}}}, **kw)


def UV(U, V, m=1.0, unidadU="J", unidadV="m3", base_n="masica", unidad_n="kg", **kw):
    return base({"tipo": "UV", "U": q_(U, unidadU), "V": q_(V, unidadV),
                 "cantidades": {"base": base_n, "valores": {"1": q_(m, unidad_n)}}}, **kw)


def ev(s):
    r = mt.evaluar(s)
    json.dumps(r, allow_nan=False)
    return r


def verif(r):
    return {v["id"]: v for v in r["evaluacion"]["verificaciones"]}


def certificada(r, nombre):
    """Toda verificacion con residuo lo respeta; las obligatorias estan."""
    if r["estado"] != "evaluado":
        check(False, f"{nombre}: {r['estado']} {[d['codigo'] for d in r['diagnosticos']]}")
        return False
    vs = verif(r)
    for v in vs.values():
        check(v["estado"] != "no_cumple" and (v["residuo"] is None or v["residuo"] <= v["tolerancia"]),
              f"{nombre}: verificacion {v['id']} {v['residuo']} > {v['tolerancia']}")
    obligatorias = {"estabilidad", "dominio", "energia", "identidad_h_u_Pv", "identidad_g_h_Ts",
                    "reconstruccion_material", "bases_fase", "unicidad"}
    if len(r["evaluacion"]["fases"]) > 1:
        obligatorias.add("equilibrio")
    check(obligatorias <= set(vs), f"{nombre}: faltan {obligatorias - set(vs)}")
    return True


# ----------------------------------------------------------------------
print("1. Coexistencia: valores publicados, IF97, Clapeyron, ajustes")
for T, Ps, rl, rv, hl, hv, sl, sv in agua._TABLA8:
    c = agua.coexistencia(float(T))
    for nombre, x, ref in (("Psat", c.P / 1e6, Ps), ("rho'", c.liquido.rho, rl), ("rho''", c.vapor.rho, rv),
                           ("h'", c.liquido.h / 1e3, hl), ("h''", c.vapor.h / 1e3, hv),
                           ("s'", c.liquido.s / 1e3, sl), ("s''", c.vapor.s / 1e3, sv)):
        check(abs(x - ref) / abs(ref) < 1e-8, f"tabla 8 {nombre}({T} K): {x} frente a {ref}")
peor_T = peor_h = 0.0
for P in [700.0, 1e3, 1e4, 101325.0, 1e6, 5e6, 1e7, 1.6e7]:
    c, res = agua.T_saturacion(P)
    check(res < 1e-12, f"Tsat({P}) residuo {res}")
    T97, hl97, hv97 = vapor_if97.saturacion(P)
    peor_T = max(peor_T, abs(c.T - T97))
    peor_h = max(peor_h, abs(c.liquido.h - hl97 / agua.M), abs(c.vapor.h - hv97 / agua.M))
# Medido: |dTsat| 8 mK, |dh| 0.2 kJ/kg, del orden de la consistencia de IF97
# con IAPWS-95 en la saturacion. Un error de referencia daria kJ/kg.
check(peor_T < 0.02, f"Tsat frente a IF97: {peor_T} K")
check(peor_h < 500.0, f"h', h'' frente a IF97: {peor_h} J/kg")
print(f"   IF97: max |dTsat| {peor_T * 1e3:.1f} mK, max |dh'|,|dh''| {peor_h:.0f} J/kg")
for T in [280.0, 373.15, 500.0, 600.0, 640.0]:
    c = agua.coexistencia(T)
    dT = 1e-4
    pend = (agua.coexistencia(T + dT).P - agua.coexistencia(T - dT).P) / (2 * dT)
    clap = (c.vapor.s - c.liquido.s) / (c.vapor.v - c.liquido.v)
    check(abs(pend - clap) / clap < 1e-6, f"Clapeyron a {T} K: {pend} frente a {clap}")
    check(abs((c.vapor.h - c.liquido.h) - T * (c.vapor.s - c.liquido.s)) / (agua.R * T) < 1e-10,
          f"calor latente h''-h' = T (s''-s') a {T} K")
    sat = agua.saturacion(T)
    check(abs(sat.Psat - c.P) / c.P < 1e-10, f"coexistencia frente a ajuste de ramas H1 a {T} K")
    # Su P sale del lado liquido (rigido): se comparan las densidades.
    P95, rl95, rv95 = w.iapws95_saturation(T, xtol=1e-6)
    check(abs(rv95 - c.vapor.rho) / rv95 < 1e-11 and abs(rl95 - c.liquido.rho) / rl95 < 1e-11,
          f"otro resolvedor de Maxwell a {T} K")
    check(c.residuo < 1e-12, f"residuo de Maxwell a {T} K: {c.residuo}")


# ----------------------------------------------------------------------
print("2. Unicidad: u y h crecientes a lo largo de las isobaras")
peor_u = 1e9
for P in [100, 1e3, 1e4, 1e5, 1e6, 5e6, 1e7, 2e7, 2.5e7, 5e7, 1e8]:
    for i in range(400):
        T = 273.16 + i * (1073.15 - 273.16) / 399
        try:
            e = agua.evaluar_TP(T, P)
        except agua.FueraDeAlcance:
            continue
        p = e.propiedades
        dudT = p.cp - P * p.dP_dT_rho / (p.rho ** 2 * p.dP_drho_T)
        peor_u = min(peor_u, dudT / p.cp)
check(peor_u > 0.7, f"(du/dT)_P / cp minimo {peor_u}")
print(f"   min (du/dT)_P / cp = {peor_u:.3f} (cp > 0 da h creciente)")


# ----------------------------------------------------------------------
print("3. Ida y vuelta TP -> PH, UP, UV")
peor = 0.0
tipos = set()
for T, P in [(298.15, 1e5), (300, 3000), (280, 5e7), (450, 1e6), (450, 9e5), (600, 5e7), (640, 3e7),
             (700, 3e7), (900, 5e7), (1000, 1e6), (900, 2.2e7), (500, 2.1e7), (373.15, 101325), (1073.15, 1e3)]:
    e = agua.evaluar_TP(T, P)
    p = e.propiedades
    tipos.add(e.tipo)
    m = 2.5
    for nombre, s in (("PH", PH(P, p.h)), ("UP", UP(m * p.u, P, m)), ("UV", UV(m * p.u, m * p.v, m))):
        r = ev(s)
        if not certificada(r, f"{nombre} desde TP({T}, {P})"):
            continue
        x = r["evaluacion"]
        f = x["fases"]
        d = max(abs(x["T"] - T) / T, abs(x["P"] - P) / P, abs(f[0]["propiedades"]["v"] - p.v) / p.v,
                abs(x["mezcla"]["h"] - p.h) / (agua.R * T))
        peor = max(peor, d)
        check(len(f) == 1 and f[0]["tipo"] == e.tipo and f[0]["regimen"] == e.regimen,
              f"{nombre} desde TP({T}, {P}): fase {[g['tipo'] for g in f]}")
        check("cp" in x["mezcla"], f"{nombre}: cp de una fase publicado")
check(peor < 1e-9, f"ida y vuelta: diferencia relativa maxima {peor}")
check(tipos == {"liquido", "vapor", "fluido"}, f"familias {tipos}")
print(f"   diferencia relativa maxima {peor:.2e}")


# ----------------------------------------------------------------------
print("4. Coexistencia con distintas q, trazas y extremos")
# 273.16 K exactos (punto triple, donde tambien coexistiria hielo, excluido del
# modelo) queda fuera: ahi la raiz cae por redondeo a uno u otro lado de T_MIN.
for T in [273.2, 280.0, 373.15, 500.0, 625.0, 643.0]:
    # Fracciones interiores: estados construidos con OTRO resolvedor de Maxwell,
    # no con el flash probado. Los extremos q = 0 y 1 exactos solo existen en la
    # coexistencia de este modelo (la otra difiere ~1e-13 y daria trazas reales
    # de ese orden); a 273.16 K, ademas, su P cae por debajo de la del punto
    # triple, donde ya no hay liquido: ese punto se toma solo del modelo.
    c = agua.coexistencia(T)
    P95, rl, rv = w.iapws95_saturation(T, xtol=1e-6)
    pl_o, pv_o = agua.propiedades(T, rl), agua.propiedades(T, rv)
    for q in [0.0, 1e-11, 1e-6, 0.3, 0.5, 0.999999, 1 - 1e-11, 1.0]:
        pl, pv = (c.liquido, c.vapor) if q in (0.0, 1.0) else (pl_o, pv_o)
        y = {k: (1 - q) * getattr(pl, k) + q * getattr(pv, k) for k in ("u", "h", "v", "s")}
        m = 3.0
        for nombre, s in (("PH", PH(pv.P, y["h"])), ("UP", UP(m * y["u"], pv.P, m)),
                          ("UV", UV(m * y["u"], m * y["v"], m))):
            etiqueta = f"{nombre} T={T} q={q}"
            r = ev(s)
            if not certificada(r, etiqueta):
                continue
            x = r["evaluacion"]
            fases = {f["tipo"]: f for f in x["fases"]}
            esperadas = {"liquido"} if q == 0 else {"vapor"} if q == 1 else {"liquido", "vapor"}
            check(set(fases) == esperadas, f"{etiqueta}: fases {set(fases)}")
            check(abs(x["T"] - T) < 1e-8, f"{etiqueta}: T {x['T']}")
            qq = fases["vapor"]["fraccionMasica"] if "vapor" in fases else 0.0
            check(abs(qq - q) <= 1e-12 + 1e-9 * q, f"{etiqueta}: q {qq}")
            if len(fases) == 2:
                fv = fases["vapor"]
                check(fv["fraccionMolar"] == fv["fraccionMasica"], f"{etiqueta}: molar = masica")
                eps = qq * fv["propiedades"]["v"] / x["mezcla"]["v"]
                check(abs(fv["fraccionVolumen"] - eps) <= 1e-12 * max(eps, 1e-300) + 1e-15,
                      f"{etiqueta}: fraccion volumetrica")
                if q <= 0.5:
                    check(fv["fraccionVolumen"] > 1.2 * qq, f"{etiqueta}: la volumetrica no es q")
                check("cp" not in x["mezcla"] and "cv" not in x["mezcla"], f"{etiqueta}: sin cp bifasico")
                check("cp" in fv["propiedades"], f"{etiqueta}: cp de fase presente")
                for k in ("u", "h", "s"):
                    check(abs(x["mezcla"][k] - y[k]) <= 1e-9 * agua.R * T, f"{etiqueta}: {k} reconstruida")
                # v es sensible a q a traves de v'' (206 m3/kg a 273 K): la tolerancia es la de q.
                tol_v = (1e-12 + 1e-9 * q) * (pv.v - pl.v) + 1e-12 * y["v"]
                check(abs(x["mezcla"]["v"] - y["v"]) <= tol_v, f"{etiqueta}: v reconstruido")
            elif q in (0.0, 1.0):
                check("cp" not in x["mezcla"] and "equilibrio" in verif(r),
                      f"{etiqueta}: en la curva, sin cp del estado y con la coexistencia verificada")
# Por debajo de Q_MIN la fraccion se trata como frontera (conjunto activo documentado).
c = agua.coexistencia(500.0)
r = ev(PH(c.P, c.liquido.h + 1e-13 * (c.vapor.h - c.liquido.h)))
check(r["estado"] == "evaluado" and len(r["evaluacion"]["fases"]) == 1, "q = 1e-13 < Q_MIN: frontera")
print("   q en {0, 1e-11, 1e-6, 0.3, 0.5, 1-1e-6, 1-1e-11, 1} a 6 temperaturas, PH/UP/UV")


# ----------------------------------------------------------------------
print("5. UV: anomalia de densidad, raices, estabilidad, region critica")
c0, c4 = agua.coexistencia(273.16), agua.coexistencia(277.13)
v_anom = (c0.liquido.v + c4.liquido.v) / 2      # v' no es monotona cerca de 4 C
resultados = []
for u in [c0.liquido.u + 10.0, 5000.0, 12000.0, 20000.0, 40000.0]:
    r = ev(UV(u, v_anom))
    if certificada(r, f"UV anomalia u={u}"):
        vs = verif(r)
        check("1 raíz" in vs["unicidad"]["motivo"], f"UV anomalia u={u}: {vs['unicidad']['motivo']}")
        resultados.append((r["evaluacion"]["T"], len(r["evaluacion"]["fases"])))
check([n for _, n in resultados] == [1, 2, 2, 2, 1], f"anomalia: liquido, coexistencia, liquido {resultados}")
check(all(a[0] < b[0] for a, b in zip(resultados, resultados[1:])), "T creciente con u a v fijo")
# La estabilidad no es una formalidad: un vapor homogeneo dentro de la campana
# (metastable) a la densidad que pediria UV se rechaza.
T = 400.0
c = agua.coexistencia(T)
rho_meta = c.vapor.rho * 1.02
try:
    agua._monofasico("UV", T, rho_meta, "vapor", None, {}, "")
    check(False, "vapor metastable homogeneo aceptado")
except agua.FueraDeAlcance as x:
    check(x.motivo == "estabilidad_no_certificada", f"vapor metastable: {x.motivo}")
# Region critica
for nombre, s in (("UV rho_c", UV(agua.propiedades(646.0, 322.0).u, 1 / 322.0)),
                  ("PH 21.5 MPa", PH(21.5e6, 2.0e6)), ("UP 22.5 MPa", UP(2.0e6, 22.5e6))):
    r = ev(s)
    check(r["estado"] == "no_soportado" and r["evaluacion"] is None
          and r["diagnosticos"][0]["codigo"] == "MOTOR_ESTADO_REGION_CRITICA", f"{nombre}: {r['diagnosticos']}")
# Junto a la banda, fuera de ella, se evalua
r = ev(PH(25e6, 2.5e6))
certificada(r, "PH 25 MPa supercritico junto a la banda")


# ----------------------------------------------------------------------
print("6. Unidades, bases y escala")
c = agua.coexistencia(450.0)
q = 0.25
u = (1 - q) * c.liquido.u + q * c.vapor.u
v = (1 - q) * c.liquido.v + q * c.vapor.v
ref = ev(UV(u * 2, v * 2, 2))["evaluacion"]
n = 2 / agua.M
for nombre, s in (("kJ y L", UV(u * 2 / 1e3, v * 2 * 1e3, 2, unidadU="kJ", unidadV="L")),
                  ("g", UV(u * 2, v * 2, 2000, unidad_n="g")),
                  ("mol", UV(u * 2, v * 2, n, base_n="molar", unidad_n="mol")),
                  ("kmol", UV(u * 2, v * 2, n / 1e3, base_n="molar", unidad_n="kmol")),
                  ("x1000", UV(u * 2000, v * 2000, 2000)), ("x1e-3", UV(u * 2e-3, v * 2e-3, 2e-3))):
    x = ev(s)["evaluacion"]
    check(x is not None and abs(x["T"] - ref["T"]) < 1e-9 and abs(x["P"] - ref["P"]) < 1e-9 * ref["P"]
          and abs(x["fases"][1]["fraccionMasica"] - q) < 1e-12
          and abs(x["fases"][1]["fraccionVolumen"] - ref["fases"][1]["fraccionVolumen"]) < 1e-12,
          f"UV {nombre}")
x = ev(UP(u * 2, c.P, n, base_n="molar", unidad_n="mol",
          masa_molar={"cantidad": {"valor": 18.015268, "unidad": "g/mol"}, "fuente": "IAPWS"}))
check(x["estado"] == "evaluado" and abs(x["evaluacion"]["fases"][1]["fraccionMasica"] - q) < 1e-12
      and "masa_molar" in verif(x), "UP molar con masa molar declarada")
x = ev(base({"tipo": "PH", "P": q_(c.P / 1e5, "bar"), "h": q_(((1 - q) * c.liquido.h + q * c.vapor.h) / 1e3, "kJ/kg"),
             "composicion": {"base": "masica", "fracciones": {"1": 1}}}))
check(x["estado"] == "evaluado" and abs(x["evaluacion"]["fases"][1]["fraccionMasica"] - q) < 1e-10, "PH bar, kJ/kg")


# ----------------------------------------------------------------------
print("7. Rechazos")
casos = [
    ("UV u bajo: hielo posible", UV(-5e4, 1e-3), "no_soportado", "MOTOR_ESTADO_FUERA_DE_DOMINIO", "declaracion.especificacion.U"),
    ("UV demasiado denso", UV(1e5, 1e-4), "no_soportado", "MOTOR_ESTADO_FUERA_DE_DOMINIO", "declaracion.especificacion.V"),
    ("UV P sobre el dominio", UV(agua.evaluar_TP(400, 9e7).propiedades.u, 1 / 1060.0), "no_soportado",
     "MOTOR_ESTADO_FUERA_DE_DOMINIO", "declaracion.especificacion.V"),
    ("UP U muy alta", UP(1e8, 1e5), "no_soportado", "MOTOR_ESTADO_FUERA_DE_DOMINIO", "declaracion.especificacion.U"),
    ("PH h bajo", PH(1e5, -1e5), "no_soportado", "MOTOR_ESTADO_FUERA_DE_DOMINIO", "declaracion.especificacion.h"),
    ("PH P alta", PH(2e8, 1e5), "no_soportado", "MOTOR_ESTADO_FUERA_DE_DOMINIO", "declaracion.especificacion.P"),
    ("UV masa cero", UV(1e5, 1e-3, 0.0), "invalido", "MOTOR_ESTADO_FUERA_DE_MAGNITUD", "declaracion.especificacion.cantidades.valores"),
    ("UV masa negativa", UV(1e5, 1e-3, -1.0), "invalido", "MOTOR_ESTADO_FUERA_DE_MAGNITUD", "declaracion.especificacion.cantidades.valores.1"),
    ("UV V cero", UV(1e5, 0.0), "invalido", "MOTOR_ESTADO_FUERA_DE_MAGNITUD", "declaracion.especificacion.V"),
    ("U en kJ/kg", UV(1e5, 1e-3, unidadU="kJ/kg"), "invalido", "MOTOR_ESTADO_UNIDAD_INCOMPATIBLE", "declaracion.especificacion.U"),
    ("cantidad molar en kg", UV(1e5, 1e-3, base_n="molar"), "invalido", "MOTOR_ESTADO_UNIDAD_INCOMPATIBLE", "declaracion.especificacion.cantidades.valores.1"),
    ("U null", UV(None, 1e-3), "incompleto", "MOTOR_ESTADO_DATO_SIN_DECLARAR", "declaracion.especificacion.U"),
    ("monofasico con dos fases", UV(u, v, politica={"cantidad": "monofasico"}), "invalido",
     "MOTOR_ESTADO_FASE_INCOMPATIBLE", "declaracion.politica.cantidad"),
    ("solo liquido con dos fases", PH(c.P, (c.liquido.h + c.vapor.h) / 2, politica={"tiposPermitidos": ["liquido"]}),
     "invalido", "MOTOR_ESTADO_FASE_INCOMPATIBLE", "declaracion.politica.tiposPermitidos"),
    ("masa molar contradictoria", UP(1e5, 1e5, 1.0, base_n="molar", unidad_n="mol",
                                     masa_molar={"cantidad": {"valor": 18.0, "unidad": "g/mol"}, "fuente": "x"}),
     "invalido", "MOTOR_ESTADO_MASA_MOLAR_CONTRADICTORIA", "componentes.1.masaMolar.cantidad"),
    ("UV con composicion", base({"tipo": "UV", "U": q_(1, "J"), "V": q_(1, "L"),
                                 "cantidades": {"base": "masica", "valores": {"1": q_(1, "kg")}},
                                 "composicion": {"base": "molar", "fracciones": {"1": 1}}}),
     "invalido", "MOTOR_ESTADO_SOBREESPECIFICADO", "declaracion.especificacion.composicion"),
]
for nombre, s, estado, codigo, ruta in casos:
    bueno = ev(PH(1e5, 1e5))                       # una evaluacion valida antes: no se recicla
    r = ev(s)
    ok = (r["estado"] == estado and r["evaluacion"] is None and bueno["evaluacion"] is not None
          and any(d["codigo"] == codigo and d["ruta"] == ruta and d["propietarioId"] == "volumen:v1"
                  for d in r["diagnosticos"]))
    check(ok, f"{nombre}: {r['estado']} {[(d['codigo'], d['ruta']) for d in r['diagnosticos']]}")
r = ev(base({"tipo": "TP", "T": q_(450.0, "K"), "P": q_(agua.saturacion(450.0).Psat, "Pa"),
             "composicion": {"base": "molar", "fracciones": {"1": 1}}}))
check(r["estado"] == "incompleto" and r["diagnosticos"][0].get("alternativas") == mt.ALTERNATIVAS_SATURACION,
      "TP en saturacion: incompleto con alternativas PH, UP, UV")
cap = mt.capacidades()["modelos"][0]
check(cap["especificaciones"] == ["TP", "PH", "UP", "UV"] and cap["dinamica"] is False, "capacidades H3")
for alt in mt.ALTERNATIVAS_SATURACION:
    tipo = {("P", "h", "composicion"): "PH", ("U", "P", "cantidades"): "UP", ("U", "V", "cantidades"): "UV"}[tuple(alt)]
    check(tipo in cap["especificaciones"], f"alternativa {alt} publicada")


print()
if FALLOS:
    print(f"{len(FALLOS)} FALLOS de {CHECKS[0]} comprobaciones")
    sys.exit(1)
print(f"OK: {CHECKS[0]} comprobaciones")
