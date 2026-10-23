"""
Prueba de ebullición del agua pura en la capa termodinámica (docs/contracts/thermodynamic-layer.md).

Sistema: 1 mol de agua (paquete agua-iapws95), presión prescrita 101325 Pa,
100 W desde 330 K durante 600 s: líquido, ebullición a T constante, vapor.
Las mismas ecuaciones de principio a fin; el vapor es un resultado.

Referencias, independientes de IAPWS-95 y del flash:
  R1. IAPWS-IF97 (otra formulación; core/vapor_if97.py y chemicals.iapws):
      T_sat(P), h' y h'' (calor latente) y las densidades de saturación.
      tm del vapor ausente en el líquido, con líquido incompresible a T:
        tm = (P - Psat)(1/rho'' - 1/rho') / (R T)
      tm del líquido ausente en el vapor (gas ideal entre P y Psat):
        tm ~ ln(Psat/P) - (Psat - P) / (rho' R T)     (3 %: no idealidad del vapor)
  R2. Valores publicados: T_sat(101325 Pa) = 373.124 K, h_fg = 2256.4 kJ/kg.
  R3. Primera ley a presión constante: H(t) = H(0) + Q t; en la meseta
      beta_vapor(t) = Q (t - t_burbuja) / (m h_fg).

Ejecutar desde la raíz:  python tests/validar_capa_agua.py
"""

import copy
import json
import math
import sys
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import chemicals.iapws as w

from core import agua_iapws95 as agua
from core import vapor_if97 as if97
from core.modelo import a_ensamblaje_v2, leer_modelo_comun, relaciones
from core.termodinamica import NoSoportado, candidatas, cierre, variables
from backend import motor_ensamblaje_v2 as v2

warnings.filterwarnings("ignore", category=RuntimeWarning)
EJ = RAIZ / "docs" / "ejemplos"
P = 101325.0
Q = 100.0
fallos, n = [], [0]


def check(nombre, ok, detalle=""):
    n[0] += 1
    if not ok:
        fallos.append(nombre)
        print(f"[FALLA] {nombre}{(' -- ' + str(detalle)[:500]) if detalle != '' else ''}")


base = json.loads((EJ / "motor-v2" / "motor-ensamblaje-v2-resolver-calentamiento-etanol-agua-peticion.json").read_text(encoding="utf-8"))
vol = base["volumenes"][0]


def dato(mag, fun, texto, unidad, prop):
    return {"magnitud": mag, "funcion": fun, "declaracion": {"texto": texto, "unidad": unidad}, "origen": {"propietarioId": prop, "ruta": "/ebullicion"}}


modelo = {
    "formato": "rage.modelo", "version": 0, "id": "ebullicion-agua", "nombre": "Agua calentada hasta hervir",
    "componentes": [{"id": 1, "nombre": "agua", "simbolo": "W", "identidadQuimica": {"cas": agua.CAS}}],
    "termodinamica": {"paquetes": [{"id": "p", "modelo": {"id": "agua-iapws95", "version": "1"}}]},
    "volumenes": [{"id": "A", "componenteIds": [1], "balances": {"materia": True, "energia": True, "momento": False},
                   "supuestos": {"materia": copy.deepcopy(vol["formulacionMateria"]), "energia": copy.deepcopy(vol["formulacionEnergia"])},
                   "frontera": {"tipo": "presion_prescrita", "presionId": "volumen.A.P"},
                   "inicial": {"cantidades": {"base": "molar", "datoIds": {"1": "volumen.A.n0.1"}}, "energia": {"tipo": "T", "datoId": "volumen.A.T0"}},
                   "termodinamica": {"tipo": "equilibrio", "paqueteId": "p",
                                     "politica": {"cantidad": "sin_restriccion", "cambioInterno": "permitido", "evaluacion": "equilibrio_estable"}}}],
    "corrientes": [],
    "intercambios": [{"id": "q", "desde": None, "hasta": "A", "ley": {"tipo": "impuesto", "potenciaId": "calor.q.Q"}, "temperaturaFronteraId": "calor.q.Tf"}],
    "datos": {"estudio.tf": dato("tiempo", "estudio", "600", "s", "estudio"),
              "volumen.A.n0.1": dato("cantidad", "inicial", "1", "mol", "volumen:A"),
              "volumen.A.T0": dato("temperatura", "inicial", "330", "K", "volumen:A"),
              "volumen.A.P": dato("presion", "frontera", "101325", "Pa", "volumen:A"),
              "calor.q.Q": dato("potencia", "frontera", "100", "W", "calor:q"),
              "calor.q.Tf": dato("temperatura", "frontera", "600", "K", "calor:q")},
    "matematico": None,
    "estudio": {"tipo": "temporal", "tiempoId": "estudio.tf", "metodoSolicitado": "rk45", "muestras": 31, "rtol": 1e-8,
                "atol": {"cantidad": 1e-10, "energia": 1e-6}},
    "motores": {},
    "procedencia": {"tipo": "nuevo", "solicitudId": "ebullicion-agua", "revision": 2},
}
leer_modelo_comun(modelo)
m_kg = agua.M

# --- R1 y R2: saturación y calor latente ---------------------------------------------
Tsat, h_f, h_g = if97.saturacion(P)          # K, J/mol, J/mol
hfg = (h_g - h_f) / if97.M                   # J/kg
check("R2: T_sat(101325 Pa) de IF97 = 373.124 K publicado (2 mK)", abs(Tsat - 373.124) < 2e-3, Tsat)
check("R2: h_fg de IF97 = 2256.4 kJ/kg publicado (1 kJ/kg)", abs(hfg / 1e3 - 2256.4) < 1.0, hfg)


def rho_sat_if97(T):
    Ps = if97.P_sat(T)
    t1, p1 = 1386.0 / T, Ps / 16.53e6
    v_l = w.iapws97_R * T / Ps * p1 * w.iapws97_dG_dpi_region1(t1, p1)
    t2, p2 = 540.0 / T, Ps / 1e6
    v_v = w.iapws97_R * T / Ps * p2 * (1.0 / p2 + w.iapws97_dGr_dpi_region2(t2, p2))
    return Ps, 1 / v_l, 1 / v_v


cand = candidatas(modelo, "A")
check("candidatas fijas del agua pura: vapor y líquido", cand == ["vapor-1", "liquido-1"], cand)
check("las variables del vapor existen desde el líquido", "volumen.A.fase.vapor-1.tm" in variables(modelo))
for T in [330, 340, 350, 360, 365, 370, 372, 373.0, 373.3, 374, 380, 390, 400, 420]:
    e = cierre(modelo, "A", {1: 1.0}, ("TP", float(T), P))
    fv, fl = e["fases"]
    check(f"T={T}: mismas candidatas", [f["id"] for f in e["fases"]] == cand)
    check(f"T={T}: complementariedad", e["complementariedad"] < 1e-12, e["complementariedad"])
    Ps, rl, rv = rho_sat_if97(float(T))
    if T < Tsat:
        ref = (P - Ps) * (1 / rv - 1 / rl) / (agua.R * T)
        check(f"T={T}: líquido; vapor con beta 0 y tm = (P-Psat)(1/rho''-1/rho')/RT de IF97 (1e-3 rel.)",
              not fv["presente"] and fv["beta"] == 0 and abs(fv["tm"] - ref) <= 1e-3 * ref, (fv["tm"], ref))
    else:
        ref = math.log(Ps / P) - (Ps - P) / (rl * agua.R * T)
        check(f"T={T}: vapor; líquido con beta 0 y tm > 0 (aproximación de gas ideal, 3 %)",
              not fl["presente"] and fl["beta"] == 0 and fl["tm"] > 0 and abs(fl["tm"] - ref) <= 0.03 * ref, (fl["tm"], ref))

# --- Trayectoria ------------------------------------------------------------------------
sol = a_ensamblaje_v2(modelo)
val, _ = v2.validar_v2(copy.deepcopy(sol))
check("las relaciones del modelo son las ecuaciones del backend", [(r["id"], r["familia"]) for r in relaciones(modelo)] == [(e["id"], e["familia"]) for e in val["ecuaciones"]])
res = v2.resolver_v2(copy.deepcopy(sol))
res = res[0] if isinstance(res, tuple) else res
check("el motor resuelve la trayectoria", res["estado"] == "resuelto", res.get("estado"))
r = res["resultados"]
t = np.array(r["tiempos"])
serie = {s["variableId"]: np.array(s["valores"]) for s in r["series"]}
H, T_mot = serie["volumen.A.H"], serie["volumen.A.T"]
ev = [(e["codigo"], e["tiempo"], e.get("faseIds")) for e in r["eventos"]]
check("eventos: aparece el vapor y desaparece el líquido", [c for c, _, _ in ev][:2] == ["aparicion_fase", "desaparicion_fase"]
      and ev[0][2] == ["vapor-1"] and ev[1][2] == ["liquido-1"], ev)
check("R3: H(t) = H(0) + Q t", float(np.max(np.abs(H - (H[0] + Q * t)))) < 1e-6 * float(np.max(np.abs(H))), float(np.max(np.abs(H - (H[0] + Q * t)))))
t_ap, t_des = ev[0][1], ev[1][1]
k_ap, k_des = int(np.argmin(np.abs(t - t_ap))), int(np.argmin(np.abs(t - t_des)))
check("R1: hierve a la T_sat de IF97 (5 mK)", abs(T_mot[k_ap] - Tsat) < 5e-3 and abs(T_mot[k_des] - Tsat) < 5e-3, (T_mot[k_ap], T_mot[k_des], Tsat))
check("R1: calor de la meseta = m h_fg de IF97 (1e-3 rel.)", abs(Q * (t_des - t_ap) - m_kg * hfg) <= 1e-3 * m_kg * hfg, (Q * (t_des - t_ap), m_kg * hfg))
traza = []
for k, tk in enumerate(t):
    e = cierre(modelo, "A", {1: float(serie["volumen.A.n.1"][k])}, ("PH", P, float(H[k])))
    fv, fl = e["fases"]
    traza.append({"t": float(tk), "T": e["T"], "presentes": e["presentes"], "betaVapor": fv["beta"], "tmVapor": fv["tm"], "tmLiquido": fl["tm"]})
    check(f"t={tk:.1f} s: mismas candidatas", [f["id"] for f in e["fases"]] == cand)
    check(f"t={tk:.1f} s: T de la capa = T del motor (1e-6 K)", abs(e["T"] - T_mot[k]) < 1e-6, (e["T"], T_mot[k]))
    check(f"t={tk:.1f} s: complementariedad", e["complementariedad"] < 1e-10, e["complementariedad"])
antes = [x for x in traza if x["t"] < t_ap - 1e-9]
durante = [x for x in traza if t_ap + 1e-9 < x["t"] < t_des - 1e-9]
despues = [x for x in traza if x["t"] > t_des + 1e-9]
check("antes: líquido; vapor con beta 0 y tm > 0 decreciente", antes and all(x["betaVapor"] == 0 and x["tmVapor"] > 0 for x in antes)
      and all(a["tmVapor"] > b["tmVapor"] for a, b in zip(antes, antes[1:])))
check("meseta: T constante (1e-6 K) mientras hierve", durante and max(x["T"] for x in durante) - min(x["T"] for x in durante) < 1e-6,
      [x["T"] for x in durante][:3])
check("R3: en la meseta beta_vapor = Q (t - t_burbuja) / (m h_fg) de IF97 (1e-3)",
      all(abs(x["betaVapor"] - Q * (x["t"] - t_ap) / (m_kg * hfg)) < 1e-3 for x in durante),
      [(x["betaVapor"], Q * (x["t"] - t_ap) / (m_kg * hfg)) for x in durante][:3])
sub = [x for x in despues if x["T"] < agua.TC]
sobre = [x for x in despues if x["T"] >= agua.TC]
check("después, por debajo de T_c: solo vapor; líquido con beta 0 y tm > 0 creciente",
      sub and all(x["presentes"] == ["vapor-1"] and x["tmLiquido"] > 0 for x in sub) and all(b["tmLiquido"] > a["tmLiquido"] for a, b in zip(sub, sub[1:])))
check("por encima de T_c: una sola rama de fluido; el líquido no puede aparecer (tm = None, beta = 0)",
      all(x["presentes"] == ["vapor-1"] and x["tmLiquido"] is None for x in sobre), [(x["T"], x["tmLiquido"]) for x in sobre])
# Fronteras: T(H) continua; la pendiente pasa de 1/(m cp) a 0 y de 0 a 1/(m cp,v).
dH = 0.05
for nombre, kk, lado in (("burbuja", k_ap, "antes"), ("rocío", k_des, "despues")):
    Ts = [cierre(modelo, "A", {1: 1.0}, ("PH", P, float(H[kk]) + d))["T"] for d in (-2 * dH, -dH, dH, 2 * dH)]
    fino = [cierre(modelo, "A", {1: 1.0}, ("PH", P, float(H[kk]) + d))["T"] for d in (-dH / 10, dH / 10)]
    s1, s2 = abs(Ts[2] - Ts[1]), abs(fino[1] - fino[0])
    check(f"{nombre}: T(H) continua: la diferencia a ambos lados tiende a 0 con dH (proporcional, sin salto)",
          s2 < s1 / 5 and s2 < 2e-4, (s1, s2))
    meseta, fuera = ((Ts[3] - Ts[2]) / dH, (Ts[1] - Ts[0]) / dH) if lado == "antes" else ((Ts[1] - Ts[0]) / dH, (Ts[3] - Ts[2]) / dH)
    check(f"{nombre}: arista: pendiente nula en la meseta y positiva fuera", abs(meseta) < 1e-9 and fuera > 1e-3, (meseta, fuera))

# --- Límites declarados ---------------------------------------------------------------
con_etanol = copy.deepcopy(modelo)
con_etanol["componentes"].append({"id": 2, "nombre": "etanol", "simbolo": "E", "identidadQuimica": {"cas": "64-17-5"}})
con_etanol["volumenes"][0]["componenteIds"] = [1, 2]
try:
    candidatas(con_etanol, "A")
    check("agua-iapws95 con otra especie: rechazado con motivo", False)
except NoSoportado as x:
    check("agua-iapws95 con otra especie: rechazado con motivo", "agua pura" in str(x))

salida = EJ / "modelo-comun" / "capa-ebullicion-agua.json"
salida.write_text(json.dumps({"modelo": modelo, "referencias": {"T_sat_IF97_K": Tsat, "h_fg_IF97_J_kg": hfg},
                              "eventos": [{"codigo": c, "tiempo": tt, "faseIds": f} for c, tt, f in ev], "traza": traza},
                             ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"T_sat {Tsat:.4f} K · h_fg {hfg / 1e3:.2f} kJ/kg · burbuja t = {t_ap:.2f} s · rocío t = {t_des:.2f} s")
print(f"\n{n[0] - len(fallos)} de {n[0]} comprobaciones correctas." if fallos else f"\nEbullición del agua: {n[0]} comprobaciones correctas.")
sys.exit(1 if fallos else 0)
