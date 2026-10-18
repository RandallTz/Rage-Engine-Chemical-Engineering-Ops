"""
Diagramas de equilibrio T-xy / P-xy (frontend/PLAN_DIAGRAMAS_EQUILIBRIO_MOTOR.md, D1-D3 y parte fisica de D5).

Referencias independientes del trazador:
  * mezcla ideal: Raoult con Poynting escrito aqui (K_i = Psat_i exp(v_L,i (P - Psat_i)/RT)/P), resuelto con
    brentq; mismas hipotesis que el paquete;
  * extremos puros: saturacion del mismo paquete (T_saturacion/P_saturacion) y puntos de ebullicion normales
    de NIST WebBook (contraste experimental de alcance explicito);
  * azeotropo etanol-agua: condicion alfa = 1 con ln gamma, Psat y Poynting del paquete (otra via que la
    igualdad de mu del trazador) y la literatura (Gmehling et al., Azeotropic Data: 78.15 C, x ~ 0.894). Los
    parametros ChemSep proceden de ajustes a VLE: NO es una validacion predictiva independiente;
  * agua/1-butanol: el encuentro L-L-V frente al punto invariante que resuelve el motor multifasico por otro
    camino (meseta de equilibrio_PH) y el heteroazeotropo de la literatura (93.0 C, tabla de Edinburgh);
  * muestras reales del ensamblaje v2 (calentamiento etanol-agua a P constante) y estados estaticos a T fija.

Ejecutar desde la raiz del proyecto:
    python tests/validar_motor_diagramas_equilibrio.py
"""

import asyncio
import copy
import json
import math
import sys
import time
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass
warnings.filterwarnings("ignore")

import httpx
import numpy as np
from scipy.optimize import brentq

from backend import motor_diagramas as mdg
from backend.main import app
from core import coexistencia_lv as co
from core import diagramas_equilibrio as dg
from core import mezclas as mz

FALLOS, CHECKS = [], [0]
R = mz.R
CAS = {"agua": "7732-18-5", "etanol": "64-17-5", "benceno": "71-43-2", "tolueno": "108-88-3",
       "butanol": "71-36-3", "metanol": "67-56-1", "acetato": "141-78-6"}


def check(cond, mensaje):
    CHECKS[0] += 1
    if not cond:
        FALLOS.append(mensaje)
        print("  FALLO:", mensaje)


def seccion(t):
    print(f"\n{t}")


def sol(par, modelo, corte, eje=1, inter=(0.0, 1.0), perfil="exploratoria", sid="t"):
    return {"revision": 1, "solicitudId": sid,
            "componentes": [{"id": k + 1, "nombre": n, "simbolo": n[:2], "identidadQuimica": {"cas": CAS[n]}}
                            for k, n in enumerate(par)],
            "modelo": {"id": modelo, "version": "1"}, "componenteEjeId": eje, "corte": corte,
            "intervaloComposicion": list(inter), "resolucion": perfil}


def Pc(v, u="Pa"):
    return {"tipo": "Txy", "P": {"valor": v, "unidad": u}}


def Tc(v, u="K"):
    return {"tipo": "Pxy", "T": {"valor": v, "unidad": u}}


def segmentos_ok(r):
    """Ningun segmento cruza un hueco y todo punto de segmento esta certificado."""
    pts = {p["id"]: p for p in r["puntos"]}
    for rama in r["ramas"]:
        for s in rama["segmentos"]:
            a, b = s["xEje"]
            for h in r["cobertura"]["huecos"]:
                ha, hb = h["intervaloXEje"]
                if a < ha + 1e-12 and hb - 1e-12 > a and ha + 1e-12 < b and hb > ha + 1e-9:
                    if max(a, ha) < min(b, hb) - 1e-9:
                        return False
            if any(pts[i]["certificado"]["estado"] != "cumple" for i in s["puntoIds"]):
                return False
    return True


def T_de(r, x):
    """T (Txy) o P (Pxy) del punto publicado mas cercano en x del eje."""
    p = min(r["puntos"], key=lambda p: abs(p["xEje"] - x))
    return p


# ======================================================================
seccion("1. Mezcla ideal: Txy y Pxy frente a Raoult con Poynting independiente")
s_bt = mz.Sistema("mezcla-ideal", [CAS["benceno"], CAS["tolueno"]])
esp = s_bt.esp


def K(T, P):
    return [e.Psat(T) * math.exp(e.vL * (P - e.Psat(T)) / (R * T)) / P for e in esp]


P = 101325.0
r = mdg.trazar(sol(("benceno", "tolueno"), "mezcla-ideal", Pc(P)))
check(r["estado"] == "completo" and segmentos_ok(r), f"benceno-tolueno Txy: {r['estado']}")
peorT = peorY = 0.0
for p in r["puntos"]:
    x = p["fases"][0]["composicionMolar"]["1"]
    if 0 < x < 1:
        T = brentq(lambda T: x * K(T, P)[0] + (1 - x) * K(T, P)[1] - 1, 300, 420, xtol=1e-13)
        peorT = max(peorT, abs(T - p["T"]))
        peorY = max(peorY, abs(x * K(T, P)[0] - p["fases"][1]["composicionMolar"]["1"]))
check(peorT < 1e-8 and peorY < 1e-10, f"Txy ideal frente a Raoult+Poynting: dT {peorT:.1e} K, dy {peorY:.1e}")
check(not any(e["tipo"] == "azeotropo" for e in r["puntosEspeciales"]), "ideal: ningun azeotropo fabricado")
T0 = 370.0
r = mdg.trazar(sol(("benceno", "tolueno"), "mezcla-ideal", Tc(T0)))
peorP = 0.0
for p in r["puntos"]:
    x = p["fases"][0]["composicionMolar"]["1"]
    if 0 < x < 1:
        Pb = brentq(lambda P: x * K(T0, P)[0] + (1 - x) * K(T0, P)[1] - 1, 1e4, 4e5, xtol=1e-10)
        peorP = max(peorP, abs(Pb / p["P"] - 1))
check(r["estado"] == "completo" and peorP < 1e-10, f"Pxy ideal frente a Raoult+Poynting: dP/P {peorP:.1e}")

# ======================================================================
seccion("2. Extremos puros: saturacion del mismo paquete y NIST")
NBP = {"benceno": 353.24, "tolueno": 383.75, "etanol": 351.44, "agua": 373.124, "metanol": 337.69}   # NIST WebBook
for par, mod in ((("benceno", "tolueno"), "mezcla-ideal"), (("etanol", "agua"), "nrtl-chemsep"),
                 (("metanol", "agua"), "nrtl-chemsep")):
    r = mdg.trazar(sol(par, mod, Pc(101325.0)))
    s = mz.Sistema(mod, [CAS[n] for n in par])
    ext = {round(e["xEje"]): e for e in r["puntosEspeciales"] if e["tipo"] == "extremo_puro"}
    for k, n in enumerate(par):
        e = ext.get(1 if k == 0 else 0)
        Ts = s.T_saturacion(101325.0, k)
        check(e is not None and abs(e["T"] - Ts) < 1e-9, f"{n} puro: T del extremo = T_saturacion del paquete")
        check(e is not None and abs(e["T"] - NBP[n]) < 0.3, f"{n} puro: {e and e['T']:.3f} K frente a NIST {NBP[n]} K")

# ======================================================================
seccion("3. Generalidad: otro par, inversion de componentes, unidades, cantidad")
r1 = mdg.trazar(sol(("metanol", "agua"), "nrtl-chemsep", Pc(101325.0)))
check(r1["estado"] == "completo" and not any(e["tipo"] == "azeotropo" for e in r1["puntosEspeciales"]),
      "metanol-agua (sin azeotropo en la literatura): completo, ningun azeotropo fabricado")
base = sol(("etanol", "agua"), "nrtl-chemsep", Pc(101325.0))
a = mdg.trazar(base)
inv = copy.deepcopy(base)
inv["componentes"] = list(reversed(inv["componentes"]))
inv["componenteEjeId"] = 1
b = mdg.trazar(inv)      # mismo eje (etanol, id 1) con el orden de componentes invertido
peor = 0.0
for p in a["puntos"]:
    q = min(b["puntos"], key=lambda q: abs(q["xEje"] - p["xEje"]))
    if abs(q["xEje"] - p["xEje"]) < 1e-12:
        peor = max(peor, abs(q["T"] - p["T"]))
check(peor < 1e-7 and a["identidad"]["firmaConsulta"] == b["identidad"]["firmaConsulta"] and
      a["identidad"]["huellaModelo"] == b["identidad"]["huellaModelo"],
      f"orden de componentes invertido: misma fisica ({peor:.1e} K) y misma firma")
otro = copy.deepcopy(base)
otro["componenteEjeId"] = 2
c = mdg.trazar(otro)
check(a["identidad"]["firmaConsulta"] == c["identidad"]["firmaConsulta"] and
      all(abs(p["fases"][0]["composicionMolar"]["1"] - (1 - p["xEje"])) < 1e-15 for p in c["puntos"]),
      "eje en el otro componente: xEje = 1 - x_etanol y misma firma fisica")
az_a = next(e for e in a["puntosEspeciales"] if e["tipo"] == "azeotropo")
az_c = next(e for e in c["puntosEspeciales"] if e["tipo"] == "azeotropo")
check(abs(az_a["xEje"] + az_c["xEje"] - 1) < 1e-9 and abs(az_a["T"] - az_c["T"]) < 1e-8, "azeotropo invariante al eje")
u = copy.deepcopy(base)
u["corte"] = Pc(1.01325, "bar")
d = mdg.trazar(u)
check(d["identidad"]["firmaConsulta"] == a["identidad"]["firmaConsulta"] and d["condicion"]["corte"] == Pc(1.01325, "bar")
      and abs(d["condicion"]["corteSI"]["P"] - 101325.0) < 1e-9, "1.01325 bar = 101325 Pa: misma firma; corte original intacto")
check("cantidad" not in json.dumps(base) and all(k not in base for k in ("masa", "volumen", "tiempo")),
      "la consulta no lleva cantidad, masa, volumen ni tiempo: el diagrama es intensivo")

# ======================================================================
seccion("4. Azeotropo etanol-agua: refinado x = y, otra via y literatura")
s_ew = mz.Sistema("nrtl-chemsep", [CAS["etanol"], CAS["agua"]])
check(az_a["residuos"][0]["valor"] <= co.TOL_MU and az_a["estabilidad"]["estado"] == "estable" and
      abs(az_a["composiciones"]["liquido-limite"]["1"] - az_a["composiciones"]["vapor-limite"]["1"]) < 1e-12,
      "azeotropo: x = y, igualdad de mu y estabilidad certificadas")


def Kg(T, x1, P=101325.0):
    x = np.array([x1, 1 - x1])
    lg = s_ew.liq.lngamma(T, x)
    return [math.exp(lg[i]) * e.Psat(T) * math.exp(e.vL * (P - e.Psat(T)) / (R * T)) / P for i, e in enumerate(s_ew.esp)]


Tb = lambda x1: brentq(lambda T: x1 * Kg(T, x1)[0] + (1 - x1) * Kg(T, x1)[1] - 1, 330, 380, xtol=1e-13)
xaz = brentq(lambda x1: Kg(Tb(x1), x1)[0] / Kg(Tb(x1), x1)[1] - 1, 0.6, 0.99, xtol=1e-14)
check(abs(az_a["xEje"] - xaz) < 1e-7 and abs(az_a["T"] - Tb(xaz)) < 1e-7,
      f"azeotropo frente a alfa = 1 (otra via): dx {abs(az_a['xEje'] - xaz):.1e}, dT {abs(az_a['T'] - Tb(xaz)):.1e} K")
check(abs(az_a["T"] - 351.30) < 0.6 and abs(az_a["xEje"] - 0.894) < 0.04 and az_a["clase"] == "minimo",
      f"azeotropo de T minima {az_a['T'] - 273.15:.2f} C, x {az_a['xEje']:.3f} (lit. 78.15 C, 0.894; parametros de VLE)")
r = mdg.trazar(sol(("etanol", "agua"), "nrtl-chemsep", Tc(350.0)))
azp = [e for e in r["puntosEspeciales"] if e["tipo"] == "azeotropo"]
check(r["estado"] == "completo" and len(azp) == 1 and azp[0]["clase"] == "maximo",
      "Pxy a 350 K: un azeotropo de P maxima (desviacion positiva)")
# burbuja por encima del rocio en P (Pxy) en cada punto regular: P(x) del liquido >= P del vapor en la misma x
check(all(p["certificado"]["estabilidad"]["estado"] == "estable" for p in r["puntos"]), "Pxy: todos los puntos estables")

# ======================================================================
seccion("5. Competencia de otro liquido: agua/1-butanol a 1 atm")
r = mdg.trazar(sol(("agua", "butanol"), "nrtl-lle-agua-butanol", Pc(101325.0), eje=1))
enc = sorted((e for e in r["puntosEspeciales"] if e["tipo"] == "encuentro_otra_fase"), key=lambda e: e["xEje"])
hue = [h for h in r["cobertura"]["huecos"] if h["motivo"] == "sin_lv_estable"]
check(r["estado"] == "parcial" and len(enc) == 2 and len(hue) == 1 and segmentos_ok(r),
      f"rama L-V interrumpida por el segundo liquido: {r['estado']}, {len(enc)} encuentros, huecos {[h['motivo'] for h in r['cobertura']['huecos']]}")
s_wb = mz.Sistema("nrtl-lle-agua-butanol", [CAS["agua"], CAS["butanol"]])
n = np.array([0.75, 0.25])
lo, hi = 360.0, 372.0
for _ in range(50):
    m = 0.5 * (lo + hi)
    if any(f.tipo == "vapor" for f in s_wb.equilibrio_TP(m, 101325.0, n).fases):
        hi = m
    else:
        lo = m
e3 = s_wb.equilibrio_PH(101325.0, 0.5 * (s_wb.equilibrio_TP(lo, 101325.0, n).H + s_wb.equilibrio_TP(hi * (1 + 1e-6), 101325.0, n).H), n)
liqs = sorted(f.x[0] for f in e3.fases if f.tipo == "liquido")
yv = next(f.x[0] for f in e3.fases if f.tipo == "vapor")
if len(enc) == 2:
    check(all(abs(e["T"] - e3.T) < 1e-4 for e in enc), f"T del encuentro {enc[0]['T']:.5f} K = T del LLV del motor "
                                                         f"multifasico {e3.T:.5f} K (otro camino)")
    check(abs(enc[0]["xEje"] - liqs[0]) < 1e-4 and abs(enc[1]["xEje"] - liqs[1]) < 1e-4 and
          abs(enc[0]["composiciones"]["vapor-limite"]["1"] - yv) < 1e-4,
          "composiciones del encuentro = liquidos y vapor del LLV del motor multifasico")
    check(abs(enc[0]["composiciones"]["competidora"]["1"] - liqs[1]) < 1e-4 and
          abs(enc[1]["composiciones"]["competidora"]["1"] - liqs[0]) < 1e-4,
          "la fase competidora identificada es el otro liquido del LLV")
    check(abs(enc[0]["T"] - (93.0 + 273.15)) < 2.0, f"heteroazeotropo {enc[0]['T'] - 273.15:.2f} C (lit. 93.0 C, +-2 K)")
cands = [c for c in r["candidatosDescartados"] if hue and c["incidenciaId"] in hue[0]["incidenciaIds"]]
check(len(cands) > 5 and all(c["motivo"].startswith("metastable") and
                             hue[0]["intervaloXEje"][0] < c["xEje"] < hue[0]["intervaloXEje"][1] for c in cands),
      f"los {len(cands)} puntos L-V del hueco quedan como candidatos metastables dentro del hueco, nunca en un segmento")
check(any(h["motivo"] == "fuera_de_dominio" for h in r["cobertura"]["huecos"]) and
      any(e["tipo"] == "limite_dominio" and abs(e["T"] - 373.0) < 1e-3 for e in r["puntosEspeciales"]),
      "agua pura hierve por encima del dominio del paquete (373 K): hueco y limite de dominio, sin extrapolar")

# ======================================================================
seccion("6. Trazas, reproducibilidad, presupuesto")
r = mdg.trazar(sol(("etanol", "agua"), "nrtl-chemsep", Pc(101325.0), perfil="refinada"))
xs = sorted(p["xEje"] for p in r["puntos"])
check(xs[0] == 0.0 and 0 < xs[1] < 1e-3 and xs[-1] == 1.0 and xs[-2] > 1 - 1e-3, "refinada: trazas junto a ambos extremos")
rep = r["cobertura"]["reproducibilidad"]
check(rep["puntosComparados"] > 50 and rep["maxDiferenciaCondicion"] < 1e-8 and rep["maxDiferenciaComposicion"] < 1e-10,
      f"dos sentidos de recorrido: {rep}")
orig = dict(dg.PERFILES["exploratoria"])
dg.PERFILES["exploratoria"]["limiteEvaluaciones"] = 40
try:
    rb = mdg.trazar(sol(("etanol", "agua"), "nrtl-chemsep", Pc(101325.0)))
finally:
    dg.PERFILES["exploratoria"].update(orig)
check(rb["estado"] == "parcial" and rb["cobertura"]["finalizacion"] == "presupuesto" and
      any(h["motivo"] == "presupuesto" for h in rb["cobertura"]["huecos"]) and segmentos_ok(rb) and
      all(p["certificado"]["estado"] == "cumple" for p in rb["puntos"]),
      "presupuesto agotado: parcial, hueco 'presupuesto', solo puntos certificados")

# ======================================================================
seccion("7. Certificado: controles negativos")
T, x, y = az_a["T"], 0.5, None
var, y0 = co.resolver_punto(s_ew, "Txy", 101325.0, 0.5, (355.0, 0.6))
c0 = co.certificar(s_ew, "Txy", 101325.0, var, 101325.0, (0.5, 0.5), (y0, 1 - y0))
check(c0["estado"] == "cumple", "punto regular certificado")
c1 = co.certificar(s_ew, "Txy", 101325.0, var, 101325.0, (0.5, 0.5), (y0 + 1e-6, 1 - y0 - 1e-6))
check(c1["estado"] == "no_cumple" and c1["residuos"][0]["estado"] == "no_cumple", "potencial alterado: no cumple")
c2 = co.certificar(s_ew, "Txy", 101325.0, var, 101325.0, (0.5, 0.5), (y0, 1 - y0 + 1e-9))
check(c2["residuos"][1]["estado"] == "no_cumple", "normalizacion alterada: no cumple")
c3 = co.certificar(s_ew, "Txy", 101325.0, var, 101325.0 * (1 + 1e-9), (0.5, 0.5), (y0, 1 - y0))
check(c3["residuos"][2]["estado"] == "no_cumple", "condicion fija alterada (P distinta del corte): no cumple")
v4, y4 = co.resolver_punto(s_wb, "Txy", 101325.0, 0.85, (367.0, 0.8))
c4 = co.certificar(s_wb, "Txy", 101325.0, v4, 101325.0, (0.85, 0.15), (y4, 1 - y4))
check(c4["residuos"][0]["estado"] == "cumple" and c4["estabilidad"]["estado"] == "inestable" and
      c4["estabilidad"]["competidora"]["tipo"] == "liquido", "raiz L-V metastable (zona LL): mu igual pero inestable")

# ======================================================================
seccion("8. Rechazos estructurados")
casos = [
    ("tres componentes", lambda s: s["componentes"].append({"id": 3, "nombre": "x", "simbolo": "x",
                                                             "identidadQuimica": {"cas": CAS["metanol"]}}),
     "MOTOR_DIAG_COMPONENTES_NO_SOPORTADO", "no_soportado"),
    ("par sin parametros", lambda s: s["componentes"][1]["identidadQuimica"].update(cas=CAS["benceno"]) or
     s["componentes"][0]["identidadQuimica"].update(cas=CAS["agua"]), "MOTOR_DIAG_PARAMETRO_AUSENTE", "no_soportado"),
    ("paquete de agua pura", lambda s: s.update(modelo={"id": "agua-iapws95", "version": "1"}),
     "MOTOR_DIAG_PAQUETE_NO_DISPONIBLE", "no_soportado"),
    ("P fuera de dominio", lambda s: s.update(corte=Pc(10, "bar")), "MOTOR_DIAG_FUERA_DE_DOMINIO", "no_soportado"),
    ("T fuera de dominio", lambda s: s.update(corte=Tc(150)), "MOTOR_DIAG_FUERA_DE_DOMINIO", "no_soportado"),
    ("unidad incompatible", lambda s: s.update(corte=Pc(1, "MPa")), "MOTOR_DIAG_UNIDAD", "invalido"),
    ("P nula", lambda s: s.update(corte={"tipo": "Txy", "P": {"valor": None, "unidad": "Pa"}}), "MOTOR_DIAG_DATO_INVALIDO", "incompleto"),
    ("intervalo invertido", lambda s: s.update(intervaloComposicion=[0.8, 0.2]), "MOTOR_DIAG_DATO_INVALIDO", "invalido"),
    ("eje ajeno", lambda s: s.update(componenteEjeId=9), "MOTOR_DIAG_DATO_INVALIDO", "invalido"),
    ("revision", lambda s: s.update(revision=2), "MOTOR_DIAG_REVISION", "invalido"),
    ("campo extra", lambda s: s.update(masa=1), "MOTOR_DIAG_DATO_INVALIDO", "invalido"),
    ("huella distinta", lambda s: s.update(huellaModeloEsperada="sha256:0"), "MOTOR_DIAG_HUELLA_DISTINTA", "invalido"),
]
for nombre, mod, codigo, estado in casos:
    s = copy.deepcopy(base)
    mod(s)
    r = mdg.trazar(s)
    check(r["estado"] == estado and any(d["codigo"] == codigo and d["ruta"] for d in r["diagnosticos"]) and not r["puntos"],
          f"{nombre}: {r['estado']} {[d['codigo'] for d in r['diagnosticos']]}")
s = copy.deepcopy(base)
s["huellaModeloEsperada"] = a["identidad"]["huellaModelo"]
check(mdg.trazar(s)["estado"] == "completo", "huella esperada correcta: se traza")


async def http():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://v") as cl:
        cap = (await cl.get("/motor/termodinamica/diagramas/capacidades")).json()
        mal = (await cl.post("/motor/termodinamica/diagramas/trazar", json={"revision": 1})).json()
        viejo = (await cl.get("/motor/termodinamica/diagrama")).json()
        return cap, mal, viejo
cap, mal, viejo = asyncio.run(http())
# UNIFAC (frontend/CONTRATO_CLAUDE_UNIFAC_MOTOR.md) amplia el catalogo de forma aditiva.
check(cap["revision"] == 1 and {p["modelo"]["id"] for p in cap["paquetes"]} == {
          "mezcla-ideal", "nrtl-chemsep", "nrtl-lle-agua-butanol", "unifac-original-public", "unifac-dortmund-public",
          "unifac-original-lle-public"},
      "HTTP capacidades: solo paquetes de mezcla publicados (el agua pura tiene su propia ruta)")
check(mal["estado"] == "incompleto" and mal["diagnosticos"], "HTTP: un cuerpo incompleto es respuesta del protocolo, no 422")
check(viejo["estado"] == "evaluado", "la ruta P-T del hielo sigue intacta")

# ======================================================================
seccion("9. Muestras reales: ensamblaje v2 a P constante y estados estaticos a T fija")
ej = json.loads((RAIZ / "docs" / "ejemplos" / "motor-v2" /
                 "motor-ensamblaje-v2-resolver-calentamiento-etanol-agua-respuesta.json").read_text(encoding="utf-8"))
n_lv = 0
for m in ej["resultados"]["estados"]["A"]:
    ev = m["evaluacion"]
    fs = {f["tipo"]: f for f in ev["fases"]}
    if set(fs) != {"liquido", "vapor"}:
        continue
    n_lv += 1
    x1 = fs["liquido"]["composicionMolar"]["1"]
    y1 = fs["vapor"]["composicionMolar"]["1"]
    Tb_, yb = co.resolver_punto(s_ew, "Txy", ev["P"], x1, (ev["T"], y1))
    check(abs(Tb_ - ev["T"]) < 1e-6 and abs(yb - y1) < 1e-7, f"muestra LV t: (T, x, y) sobre su T-xy (dT {abs(Tb_ - ev['T']):.1e})")
    beta = fs["vapor"]["fraccionMolar"]
    z1 = ev["composicionMolar"]["1"]
    check(abs((1 - beta) * x1 + beta * y1 - z1) < 1e-9, "regla de la palanca con beta publicado")
check(n_lv >= 3, f"{n_lv} muestras LV comparadas")
huella_ens = next(p["huella"] for p in ej["resultados"].get("procedenciaModelo", [])) if ej["resultados"].get("procedenciaModelo") else None
check(huella_ens == a["identidad"]["huellaModelo"], "huella del ensamblaje = huella del diagrama: comparacion verificable")
T0 = 350.0
z = np.array([0.4, 0.6])
rP = mdg.trazar(sol(("etanol", "agua"), "nrtl-chemsep", Tc(T0)))
pb = T_de(rP, 0.4)
for Pq in (0.5 * (60000 + 70000), 65000.0):
    e = s_ew.equilibrio_TP(T0, Pq, z)
    if len(e.fases) == 2:
        fl = next(f for f in e.fases if f.tipo == "liquido")
        fv = next(f for f in e.fases if f.tipo == "vapor")
        Pb_, yb = co.resolver_punto(s_ew, "Pxy", T0, fl.x[0], (Pq, fv.x[0]))
        check(abs(Pb_ / Pq - 1) < 1e-9 and abs(yb - fv.x[0]) < 1e-9, f"estado estatico LV a {T0} K, {Pq:.0f} Pa sobre su P-xy")

# ======================================================================
seccion("10. Coste (exploratoria / refinada)")
for par, mod, corte in ((("benceno", "tolueno"), "mezcla-ideal", Pc(101325.0)), (("etanol", "agua"), "nrtl-chemsep", Pc(101325.0)),
                        (("agua", "butanol"), "nrtl-lle-agua-butanol", Pc(101325.0))):
    for perfil in ("exploratoria", "refinada"):
        t0 = time.perf_counter()
        r = mdg.trazar(sol(par, mod, corte, perfil=perfil))
        dt = time.perf_counter() - t0
        print(f"  {'-'.join(par)} {perfil}: {dt:.2f} s, {len(r['puntos'])} puntos, "
              f"{r['cobertura']['presupuesto']['evaluaciones']} evaluaciones, {r['estado']}")
        check(r["cobertura"]["finalizacion"] == "recorrido_completo", f"{'-'.join(par)} {perfil}: recorrido completo")

print(f"\n{'OK' if not FALLOS else 'FALLOS: ' + str(len(FALLOS))}: {CHECKS[0]} comprobaciones")
sys.exit(1 if FALLOS else 0)
