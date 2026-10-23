"""
Prueba guía de la capa termodinámica (ARCHITECTURE.md §10, paso 2):
una mezcla en un recipiente que se calienta hasta hervir, con las mismas
ecuaciones de principio a fin y la aparición del vapor como RESULTADO.

Sistema: 1 mol de benceno + tolueno equimolar, solución ideal + vapor ideal
(paquete mezcla-ideal), presión prescrita 101325 Pa, 100 W desde 330 K.

Referencias, independientes del flash y de la prueba de estabilidad:
  R1. Raoult con Poynting en forma cerrada, a partir solo de los datos puros
      del paquete: K_i = Psat_i exp(v_L,i (P - Psat_i) / RT) / P.
      burbuja: sum z_i K_i = 1;  rocío: sum z_i / K_i = 1;
      tm del vapor ausente = -ln sum z_i K_i;  tm del líquido ausente = -ln sum z_i / K_i;
      fracción de vapor por Rachford-Rice.
  R2. Antoine publicado (no los datos del paquete): burbuja y rocío a 1 atm
      dentro de 0.5 K.
  R3. Primera ley a presión constante: H(t) = H(0) + Q t.

Ejecutar desde la raíz:  python tests/validar_capa_termodinamica.py
"""

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

import warnings

import numpy as np
from scipy.optimize import brentq

from core import mezclas_datos as md
from core.modelo import a_ensamblaje_v2, leer_modelo_comun, relaciones
from core.termodinamica import NoSoportado, candidatas, cierre, variables
from backend import motor_ensamblaje_v2 as v2

EJ = RAIZ / "docs" / "ejemplos"
warnings.filterwarnings("ignore", category=RuntimeWarning, module="core.mezclas")
R = md.R
P = 101325.0
Z = np.array([0.5, 0.5])
CAS = ["71-43-2", "108-88-3"]
fallos, n = [], [0]


def check(nombre, ok, detalle=""):
    n[0] += 1
    if not ok:
        fallos.append(nombre)
        print(f"[FALLA] {nombre}{(' -- ' + str(detalle)[:500]) if detalle != '' else ''}")


# --- el modelo común de la prueba guía -------------------------------------------------
base = json.loads((EJ / "motor-v2" / "motor-ensamblaje-v2-resolver-calentamiento-etanol-agua-peticion.json").read_text(encoding="utf-8"))
vol = base["volumenes"][0]


def dato(mag, fun, texto, unidad, prop):
    return {"magnitud": mag, "funcion": fun, "declaracion": {"texto": texto, "unidad": unidad}, "origen": {"propietarioId": prop, "ruta": "/guia"}}


modelo = {
    "formato": "rage.modelo", "version": 0, "id": "guia-calentamiento-benceno-tolueno",
    "nombre": "Mezcla benceno-tolueno calentada hasta hervir",
    "componentes": [{"id": 1, "nombre": "benceno", "simbolo": "B", "identidadQuimica": {"cas": CAS[0]}},
                    {"id": 2, "nombre": "tolueno", "simbolo": "T", "identidadQuimica": {"cas": CAS[1]}}],
    "termodinamica": {"paquetes": [{"id": "p", "modelo": {"id": "mezcla-ideal", "version": "1"}}]},
    "volumenes": [{"id": "A", "componenteIds": [1, 2], "balances": {"materia": True, "energia": True, "momento": False},
                   "supuestos": {"materia": copy.deepcopy(vol["formulacionMateria"]), "energia": copy.deepcopy(vol["formulacionEnergia"])},
                   "frontera": {"tipo": "presion_prescrita", "presionId": "volumen.A.P"},
                   "inicial": {"cantidades": {"base": "molar", "datoIds": {"1": "volumen.A.n0.1", "2": "volumen.A.n0.2"}},
                               "energia": {"tipo": "T", "datoId": "volumen.A.T0"}},
                   "termodinamica": {"tipo": "equilibrio", "paqueteId": "p",
                                     "politica": {"cantidad": "sin_restriccion", "cambioInterno": "permitido", "evaluacion": "equilibrio_estable"}}}],
    "corrientes": [],
    "intercambios": [{"id": "q", "desde": None, "hasta": "A", "ley": {"tipo": "impuesto", "potenciaId": "calor.q.Q"}, "temperaturaFronteraId": "calor.q.Tf"}],
    "datos": {"estudio.tf": dato("tiempo", "estudio", "500", "s", "estudio"),
              "volumen.A.n0.1": dato("cantidad", "inicial", "0.5", "mol", "volumen:A"),
              "volumen.A.n0.2": dato("cantidad", "inicial", "0.5", "mol", "volumen:A"),
              "volumen.A.T0": dato("temperatura", "inicial", "330", "K", "volumen:A"),
              "volumen.A.P": dato("presion", "frontera", "101325", "Pa", "volumen:A"),
              "calor.q.Q": dato("potencia", "frontera", "100", "W", "calor:q"),
              "calor.q.Tf": dato("temperatura", "frontera", "600", "K", "calor:q")},
    "matematico": None,
    "estudio": {"tipo": "temporal", "tiempoId": "estudio.tf", "metodoSolicitado": "rk45", "muestras": 26, "rtol": 1e-8,
                "atol": {"cantidad": 1e-10, "energia": 1e-6}},
    "motores": {},
    "procedencia": {"tipo": "nuevo", "solicitudId": "guia-calentamiento", "revision": 2},
}
leer_modelo_comun(modelo)

# --- R1: Raoult con Poynting en forma cerrada ------------------------------------------
esp = [md.especie(c) for c in CAS]


def K(T):
    return np.array([e.Psat(T) * math.exp(e.vL * (P - e.Psat(T)) / (R * T)) / P for e in esp])


T_bur = brentq(lambda T: float(np.sum(Z * K(T))) - 1, 300, 420, xtol=1e-12)
T_roc = brentq(lambda T: float(np.sum(Z / K(T))) - 1, 300, 420, xtol=1e-12)


def beta_rr(T):
    k = K(T)
    return brentq(lambda b: float(np.sum(Z * (k - 1) / (1 + b * (k - 1)))), 1e-14, 1 - 1e-14, xtol=1e-15)


# R2: Antoine (log10 P[mmHg] = A - B / (C + t[°C])), benceno y tolueno, valores de tabla habituales.
ANT = [(6.90565, 1211.033, 220.79), (6.95464, 1344.8, 219.482)]
Pa_mmHg = 101325 / 760


def K_ant(T):
    t = T - 273.15
    return np.array([10 ** (A - B / (C + t)) * Pa_mmHg / P for A, B, C in ANT])


Tb_ant = brentq(lambda T: float(np.sum(Z * K_ant(T))) - 1, 300, 420)
Td_ant = brentq(lambda T: float(np.sum(Z / K_ant(T))) - 1, 300, 420)
check("R2: burbuja del paquete frente a Antoine publicado (0.5 K)", abs(T_bur - Tb_ant) < 0.5, (T_bur, Tb_ant))
check("R2: rocío del paquete frente a Antoine publicado (0.5 K)", abs(T_roc - Td_ant) < 0.5, (T_roc, Td_ant))
print(f"burbuja {T_bur:.4f} K (Antoine {Tb_ant:.4f}) · rocío {T_roc:.4f} K (Antoine {Td_ant:.4f})")

# --- La capa en una malla de temperaturas: mismas candidatas, complementariedad, R1 ------
cand = candidatas(modelo, "A")
check("candidatas fijas por el paquete: vapor y un líquido (una solución ideal no se separa en dos líquidos)", cand == ["vapor-1", "liquido-1"], cand)
var = variables(modelo)
check("las variables del vapor existen aunque el estado sea líquido", "volumen.A.fase.vapor-1.n" in var and "volumen.A.fase.vapor-1.tm" in var)
for T in np.linspace(330, 390, 25):
    e = cierre(modelo, "A", {1: 0.5, 2: 0.5}, ("TP", float(T), P))
    ids = [f["id"] for f in e["fases"]]
    fv, fl = e["fases"][0], e["fases"][1]
    check(f"T={T:.2f}: el estado publica siempre las mismas fases candidatas", ids == cand, ids)
    check(f"T={T:.2f}: complementariedad beta·tm = 0, beta >= 0, tm >= 0", e["complementariedad"] < 1e-9, e["complementariedad"])
    if T < T_bur - 1e-6:
        ref = -math.log(float(np.sum(Z * K(T))))
        check(f"T={T:.2f}: líquido; vapor con beta = 0 y tm = -ln sum zK > 0", not fv["presente"] and fv["beta"] == 0 and abs(fv["tm"] - ref) < 1e-8 and ref > 0, (fv, ref))
    elif T > T_roc + 1e-6:
        ref = -math.log(float(np.sum(Z / K(T))))
        check(f"T={T:.2f}: vapor; líquido con beta = 0 y tm = -ln sum z/K > 0", not fl["presente"] and fl["beta"] == 0 and abs(fl["tm"] - ref) < 1e-6 and ref > 0, (fl, ref))
    else:
        b = beta_rr(float(T))
        check(f"T={T:.2f}: dos fases, beta del vapor = Rachford-Rice ({b:.6f})", fv["presente"] and fl["presente"] and abs(fv["beta"] - b) < 1e-8, (fv["beta"], b))

# --- La trayectoria: el motor resuelve el modelo común; la capa lee cada muestra --------
sol = a_ensamblaje_v2(modelo)
val, _ = v2.validar_v2(copy.deepcopy(sol))
rel = relaciones(modelo)
check("las relaciones del modelo son las ecuaciones del backend", [(r["id"], r["familia"]) for r in rel] == [(e["id"], e["familia"]) for e in val["ecuaciones"]])
res = v2.resolver_v2(copy.deepcopy(sol))
res = res[0] if isinstance(res, tuple) else res
check("el motor resuelve la trayectoria", res["estado"] == "resuelto", res.get("estado"))
r = res["resultados"]
t = np.array(r["tiempos"])
serie = {s["variableId"]: np.array(s["valores"]) for s in r["series"]}
H, T_mot = serie["volumen.A.H"], serie["volumen.A.T"]
ev = [(e["codigo"], e["tiempo"], e.get("faseIds")) for e in r["eventos"]]
check("eventos: aparece el vapor y después desaparece el líquido", [c for c, _, _ in ev][:2] == ["aparicion_fase", "desaparicion_fase"]
      and ev[0][2] == ["vapor-1"] and ev[1][2] == ["liquido-1"], ev)
check("R3: H(t) = H(0) + Q t a presión constante", float(np.max(np.abs(H - (H[0] + 100 * t)))) < 1e-6 * float(np.max(np.abs(H))),
      float(np.max(np.abs(H - (H[0] + 100 * t)))))
traza = []
for k, tk in enumerate(t):
    e = cierre(modelo, "A", {1: float(serie["volumen.A.n.1"][k]), 2: float(serie["volumen.A.n.2"][k])}, ("PH", P, float(H[k])))
    fv = e["fases"][0]
    traza.append({"t": float(tk), "T": e["T"], "presentes": e["presentes"], "betaVapor": fv["beta"], "tmVapor": fv["tm"],
                  "tmLiquido": e["fases"][1]["tm"], "complementariedad": e["complementariedad"]})
    check(f"t={tk:.2f} s: mismas fases candidatas que en t = 0", [f["id"] for f in e["fases"]] == cand)
    check(f"t={tk:.2f} s: T de la capa = T del motor (1e-6 K)", abs(e["T"] - T_mot[k]) < 1e-6, (e["T"], T_mot[k]))
    check(f"t={tk:.2f} s: complementariedad", e["complementariedad"] < 1e-8, e["complementariedad"])
t_ap, t_des = ev[0][1], ev[1][1]
k_ap, k_des = int(np.argmin(np.abs(t - t_ap))), int(np.argmin(np.abs(t - t_des)))
check("R1: la T en que aparece el vapor es la de burbuja (1e-4 K)", abs(T_mot[k_ap] - T_bur) < 1e-4, (T_mot[k_ap], T_bur))
check("R1: la T en que desaparece el líquido es la de rocío (1e-4 K)", abs(T_mot[k_des] - T_roc) < 1e-4, (T_mot[k_des], T_roc))
antes = [x for x in traza if x["t"] < t_ap - 1e-9]
durante = [x for x in traza if t_ap + 1e-9 < x["t"] < t_des - 1e-9]
despues = [x for x in traza if x["t"] > t_des + 1e-9]
check("antes de hervir: beta del vapor = 0 y tm del vapor > 0, que decrece hacia 0",
      antes and all(x["betaVapor"] == 0 and x["tmVapor"] > 0 for x in antes) and all(a["tmVapor"] > b["tmVapor"] for a, b in zip(antes, antes[1:])))
check("durante la ebullición: tm del vapor = 0 y beta crece de 0 a 1",
      durante and all(x["tmVapor"] == 0 and 0 < x["betaVapor"] < 1 for x in durante) and all(a["betaVapor"] < b["betaVapor"] for a, b in zip(durante, durante[1:])))
check("después: solo vapor; el líquido con beta = 0 y tm > 0", despues and all(x["presentes"] == ["vapor-1"] and x["tmLiquido"] > 0 for x in despues))
check("T(t) creciente", all(y > x for x, y in zip(T_mot, T_mot[1:])))
# En cada frontera de fase, T(H) es continua y su pendiente cambia (la arista): las ecuaciones no cambian,
# cambia la respuesta de las propiedades. Se evalúa la capa a H_evento -+ dH.
dH = 0.05
for nombre, kk in (("aparición del vapor", k_ap), ("desaparición del líquido", k_des)):
    nk = {1: float(serie["volumen.A.n.1"][kk]), 2: float(serie["volumen.A.n.2"][kk])}
    Ts = [cierre(modelo, "A", nk, ("PH", P, float(H[kk]) + d))["T"] for d in (-2 * dH, -dH, dH, 2 * dH)]
    salto = abs(Ts[2] - Ts[1])
    pend_a, pend_d = (Ts[1] - Ts[0]) / dH, (Ts[3] - Ts[2]) / dH
    check(f"{nombre}: T(H) continua (|T(H+dH) - T(H-dH)| < 1e-3 K)", salto < 1e-3, salto)
    check(f"{nombre}: arista: la pendiente dT/dH cambia (cociente > 2)", max(pend_a, pend_d) / min(pend_a, pend_d) > 2, (pend_a, pend_d))

# --- Lo que la capa todavía no envuelve se dice ----------------------------------------
agua = copy.deepcopy(modelo)
agua["termodinamica"]["paquetes"][0]["modelo"] = {"id": "agua-iapws95", "version": "1"}
try:
    candidatas(agua, "A")
    check("agua-iapws95 aplicado a benceno y tolueno: rechazado (describe agua pura)", False)
except NoSoportado as x:
    check("agua-iapws95 aplicado a benceno y tolueno: rechazado (describe agua pura)", "agua pura" in str(x))
sup = copy.deepcopy(modelo)
sup["volumenes"][0]["termodinamica"] = {"tipo": "supuesto", "supuesto": "fase_no_evaluada", "motivo": "prueba"}
try:
    cierre(sup, "A", {1: 0.5, 2: 0.5}, ("TP", 330.0, P))
    check("volumen con estado supuesto: sin cierre que evaluar", False)
except NoSoportado:
    check("volumen con estado supuesto: sin cierre que evaluar", True)

# --- Ejemplo canónico --------------------------------------------------------------------
salida = EJ / "modelo-comun" / "capa-calentamiento-benceno-tolueno.json"
texto = json.dumps({"modelo": modelo, "referencias": {"T_burbuja_K": T_bur, "T_rocio_K": T_roc, "T_burbuja_Antoine_K": Tb_ant, "T_rocio_Antoine_K": Td_ant},
                    "eventos": [{"codigo": c, "tiempo": tt, "faseIds": f} for c, tt, f in ev], "traza": traza},
                   ensure_ascii=False, indent=1) + "\n"
salida.write_text(texto, encoding="utf-8")

print(f"\n{n[0] - len(fallos)} de {n[0]} comprobaciones correctas." if fallos else f"\nCapa termodinámica: {n[0]} comprobaciones correctas.")
sys.exit(1 if fallos else 0)
