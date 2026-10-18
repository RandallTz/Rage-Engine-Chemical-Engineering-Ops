"""
Corte vertical (ARQUITECTURA_MOTOR.md §10, paso 4; docs/CORTE_VERTICAL.md).

    modelo común -> relaciones -> capa termodinámica -> compilador -> solver propio
                 -> resultados en el formato común

El MISMO código, sin ramas por caso, resuelve:

  1. La prueba guía: benceno + tolueno (solución ideal) calentados hasta
     evaporarse. Contra Raoult en forma cerrada (burbuja y rocío), la primera
     ley H = H0 + Q t y el motor de ensamblaje existente, en vivo.
  2. Agua pura (IAPWS-95) que hierve. Contra IF97 (T_sat, h_fg) y el motor.
  3. Los cuatro ensamblajes de ejemplo del motor (dos volúmenes con corriente y
     conductancia; dos aguas rígidas, cierre UV; decantador agua-butanol que
     extrae una fase líquida por densidad; etanol-agua NRTL que hierve), contra
     sus respuestas publicadas.

En todos: conservación global, complementariedad y TODAS las fases
candidatas publicadas en cada muestra. Y una comprobación estática: el
compilador, el solver y la capa no mencionan equipos ni operaciones.

Ejecutar desde la raíz:  python tests/validar_corte_vertical.py   (~1 min)
"""

import copy
import glob
import json
import math
import re
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
from scipy.optimize import brentq

from core import mezclas_datos as md
from core import vapor_if97 as if97
from core import agua_iapws95 as agua
from core.compilador import NoSoportado, compilar, resolver
from core.modelo import a_ensamblaje_v2, desde_ensamblaje_v2
from core.resultados import leer_resultados
from core.termodinamica import candidatas
from backend import motor_ensamblaje_v2 as v2

warnings.filterwarnings("ignore", category=RuntimeWarning)
EJ = RAIZ / "docs" / "ejemplos"
fallos, n = [], [0]


def check(nombre, ok, detalle=""):
    n[0] += 1
    if not ok:
        fallos.append(nombre)
        print(f"[FALLA] {nombre}{(' -- ' + str(detalle)[:400]) if detalle != '' else ''}")


def series(c):
    return {s["id"]: s for s in c["series"]}


def comparar(nombre, c, pub, rel=1e-7):
    """Series de estado de nuestro resultado frente a una respuesta del motor (sus tiempos)."""
    S, P = series(c), {s["variableId"]: s for s in pub["series"]}
    tt, tp = np.array(c["ejes"][0]["valores"]), np.array(pub["tiempos"])
    peor, cual = 0.0, None
    for k, s in P.items():
        if k in S and re.search(r"\.(n\.\d+|T|H|U)$", k):
            a = np.interp(tp, tt, np.array(S[k]["valores"], dtype=float))
            b = np.array(s["valores"], dtype=float)
            d = float(np.max(np.abs(a - b)) / max(float(np.max(np.abs(b))), 1e-300))
            if d > peor:
                peor, cual = d, k
    check(f"{nombre}: estado igual al del motor existente ({rel:g} relativo)", peor < rel, (cual, peor))
    ev_c = [(e["codigo"], e["valor"]) for e in c["eventos"] if "fase" in e["codigo"]]
    ev_p = [(e["codigo"], e["tiempo"]) for e in pub["eventos"] if "fase" in e["codigo"]]
    check(f"{nombre}: mismos eventos de fase y en el mismo instante (1e-6 s)",
          [a for a, _ in ev_c] == [a for a, _ in ev_p] and all(abs(x - y) < 1e-6 for (_, x), (_, y) in zip(ev_c, ev_p)), (ev_c, ev_p))


def comunes(nombre, modelo, c):
    leer_resultados(c)
    check(f"{nombre}: resultado válido en el formato común", True)
    ver = {v["id"]: v["valor"] for v in c["verificaciones"]}
    check(f"{nombre}: conservación global de materia (1e-12)", ver["conservacion.materia"] < 1e-12, ver["conservacion.materia"])
    check(f"{nombre}: conservación global de energía (1e-12)", ver["conservacion.energia"] < 1e-12, ver["conservacion.energia"])
    check(f"{nombre}: complementariedad beta·tm en todas las muestras (1e-8)", ver["complementariedad"] < 1e-8, ver["complementariedad"])
    S = series(c)
    nt = len(c["ejes"][0]["valores"])
    for v in modelo["volumenes"]:
        for k in candidatas(modelo, v["id"]):
            b = S.get(f"volumen.{v['id']}.fase.{k}.beta")
            check(f"{nombre}: la candidata {v['id']}/{k} se publica en todas las muestras", b is not None and len(b["valores"]) == nt
                  and all(x is not None and x >= 0 for x in b["valores"]))


# --- 1. Prueba guía: benceno + tolueno -------------------------------------------------
guia = json.loads((EJ / "modelo-comun" / "capa-calentamiento-benceno-tolueno.json").read_text(encoding="utf-8"))["modelo"]
c1 = resolver(copy.deepcopy(guia))
comunes("guía", guia, c1)
pub1 = v2.resolver_v2(a_ensamblaje_v2(copy.deepcopy(guia)))
pub1 = (pub1[0] if isinstance(pub1, tuple) else pub1)["resultados"]
comparar("guía", c1, pub1)
P, Z = 101325.0, np.array([0.5, 0.5])
esp = [md.especie(cs) for cs in ("71-43-2", "108-88-3")]
K = lambda T: np.array([e.Psat(T) * math.exp(e.vL * (P - e.Psat(T)) / (md.R * T)) / P for e in esp])
T_bur = brentq(lambda T: float(np.sum(Z * K(T))) - 1, 300, 420, xtol=1e-12)
T_roc = brentq(lambda T: float(np.sum(Z / K(T))) - 1, 300, 420, xtol=1e-12)
S1 = series(c1)
t1 = np.array(c1["ejes"][0]["valores"])
T1 = np.array(S1["volumen.A.T"]["valores"])
ev = {e["codigo"]: e["valor"] for e in c1["eventos"]}
check("guía: aparece el vapor a la T de burbuja de Raoult (1e-4 K)", abs(float(T1[np.argmin(np.abs(t1 - ev["aparicion_fase"]))]) - T_bur) < 1e-4)
check("guía: desaparece el líquido a la T de rocío de Raoult (1e-4 K)", abs(float(T1[np.argmin(np.abs(t1 - ev["desaparicion_fase"]))]) - T_roc) < 1e-4)
H1 = np.array(S1["volumen.A.H"]["valores"])
check("guía: H(t) = H(0) + Q t (primera ley a P constante)", float(np.max(np.abs(H1 - H1[0] - 100 * t1))) < 1e-6 * float(np.max(np.abs(H1))))
bv, tmv = S1["volumen.A.fase.vapor-1.beta"]["valores"], S1["volumen.A.fase.vapor-1.tm"]["valores"]
antes = [i for i, t in enumerate(t1) if t < ev["aparicion_fase"] - 1e-9]
check("guía: antes de hervir el vapor está, con beta 0 y tm > 0 (las ecuaciones no cambian)", antes and all(bv[i] == 0 and tmv[i] > 0 for i in antes))

# --- 2. Agua pura ------------------------------------------------------------------------
agua_m = json.loads((EJ / "modelo-comun" / "capa-ebullicion-agua.json").read_text(encoding="utf-8"))["modelo"]
c2 = resolver(copy.deepcopy(agua_m))
comunes("agua", agua_m, c2)
pub2 = v2.resolver_v2(a_ensamblaje_v2(copy.deepcopy(agua_m)))
pub2 = (pub2[0] if isinstance(pub2, tuple) else pub2)["resultados"]
comparar("agua", c2, pub2)
Tsat, hf, hg = if97.saturacion(101325.0)
ev2 = {e["codigo"]: e["valor"] for e in c2["eventos"]}
S2 = series(c2)
t2, T2 = np.array(c2["ejes"][0]["valores"]), np.array(S2["volumen.A.T"]["valores"])
check("agua: hierve a la T_sat de IF97 (5 mK)", abs(float(T2[np.argmin(np.abs(t2 - ev2["aparicion_fase"]))]) - Tsat) < 5e-3)
check("agua: calor de la meseta = n h_fg de IF97 (1e-3)", abs(100 * (ev2["desaparicion_fase"] - ev2["aparicion_fase"]) - (hg - hf)) < 1e-3 * (hg - hf),
      (100 * (ev2["desaparicion_fase"] - ev2["aparicion_fase"]), hg - hf))

# --- 3. Los ensamblajes de ejemplo del motor -------------------------------------------
for f in sorted(glob.glob(str(EJ / "motor-v2" / "motor-ensamblaje-v2-resolver-*-peticion.json"))):
    nom = Path(f).name.replace("motor-ensamblaje-v2-resolver-", "").replace("-peticion.json", "")
    m = desde_ensamblaje_v2(json.loads(Path(f).read_text(encoding="utf-8")))
    c = resolver(copy.deepcopy(m))
    comunes(nom, m, c)
    comparar(nom, c, json.loads(Path(f.replace("peticion", "respuesta")).read_text(encoding="utf-8"))["resultados"])

# --- Lo que no se ejecuta se dice --------------------------------------------------------
reac = copy.deepcopy(guia)
reac["volumenes"][0]["supuestos"]["materia"]["campo"]["sinReaccion"] = False
try:
    compilar(reac)
    check("fuentes materiales (reacción): no soportadas todavía, con motivo", False)
except NoSoportado as e:
    check("fuentes materiales (reacción): no soportadas todavía, con motivo", "constitutivas" in str(e))
sup = copy.deepcopy(guia)
sup["volumenes"][0]["termodinamica"] = {"tipo": "supuesto", "supuesto": "fase_no_evaluada", "motivo": "prueba"}
try:
    compilar(sup)
    check("volumen con estado supuesto: el compilador exige el cierre de equilibrio", False)
except NoSoportado as e:
    check("volumen con estado supuesto: el compilador exige el cierre de equilibrio", "supuesto" in str(e))

# --- Sin sesgo hacia ninguna operación (comprobación estática) --------------------------
PROHIBIDAS = re.compile(r"\b(tanque|columna|reactor|destilaci|evaporador|caldera|intercambiador|decantador|condensador|hervidor|"
                        r"benceno|tolueno|etanol|butanol|metanol|acetona)\b", re.IGNORECASE)
for ruta in ["core/compilador/compilador.py", "core/solvers/integrador.py", "core/termodinamica/capa.py", "core/termodinamica/volumen.py",
             "core/modelo/relaciones.py", "core/resultados/formato.py", "core/unidades/servicio.py"]:
    codigo = "\n".join(l for l in (RAIZ / ruta).read_text(encoding="utf-8").splitlines() if not l.strip().startswith("#"))
    codigo = re.sub(r'"""[\s\S]*?"""', "", codigo)
    hallado = sorted(set(m.group(0).lower() for m in PROHIBIDAS.finditer(codigo)))
    check(f"{ruta}: ningún equipo, operación ni sustancia en el código", not hallado, hallado)

salida = EJ / "modelo-comun" / "corte-vertical-benceno-tolueno-resultados.json"
salida.write_text(json.dumps(c1, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"\n{n[0] - len(fallos)} de {n[0]} comprobaciones correctas." if fallos else f"\nCorte vertical: {n[0]} comprobaciones correctas.")
sys.exit(1 if fallos else 0)
