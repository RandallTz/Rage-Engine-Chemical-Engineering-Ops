"""
Formato común de resultados (core/resultados, docs/contracts/results-format.md).

  1. Ensamblaje v2 del motor -> formato común sin pérdida: mismos tiempos,
     mismos valores, metadatos de cada variable, eventos y residuos.
  2. La simulación del núcleo de adimensionalización publica el formato común:
     la formulación adimensional y las variables originales en SI coinciden
     con sus campos de siempre (campos, fisico).
  3. El lector rechaza formas, ejes y unidades incorrectos.

Ejecutar desde la raíz:  python tests/validar_resultados.py
"""

import copy
import glob
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from core import unidades as un
from core.resultados import ErrorResultados, desde_ensamblaje_v2, leer_resultados
from core.adimensionalizacion import procesar

EJ = RAIZ / "docs" / "ejemplos"
fallos, n = [], [0]


def check(nombre, ok, detalle=""):
    n[0] += 1
    if not ok:
        fallos.append(nombre)
        print(f"[FALLA] {nombre}{(' -- ' + str(detalle)[:300]) if detalle != '' else ''}")


# 1. Ensamblaje v2
for f in sorted(glob.glob(str(EJ / "motor-v2" / "motor-ensamblaje-v2-resolver-*-respuesta.json"))):
    nom = Path(f).name
    r = json.loads(Path(f).read_text(encoding="utf-8"))
    c = desde_ensamblaje_v2(r)
    try:
        leer_resultados(c)
        ok = True
    except ErrorResultados as e:
        ok = str(e)
    check(f"{nom}: conjunto válido", ok is True, ok)
    check(f"{nom}: mismo eje de tiempo", c["ejes"][0]["valores"] == r["resultados"]["tiempos"])
    orig = {s["variableId"]: s for s in r["resultados"]["series"]}
    check(f"{nom}: todas las series, con los mismos valores", len(c["series"]) == len(orig) and all(s["valores"] == orig[s["id"]]["valores"] for s in c["series"]))
    check(f"{nom}: cada serie con su dimensión del servicio de unidades",
          all(s["dimension"] == un.servicio.dimension_json(un.interpretar(s["unidadSI"])["dimension"]) for s in c["series"]))
    meta = {v["id"]: v for v in r["validacion"]["variables"]}
    check(f"{nom}: propietario, componente y fase de cada variable conservados",
          all(s.get("propietarioId") == meta[s["id"]].get("propietarioId") and s.get("componenteId") == meta[s["id"]].get("componenteId") for s in c["series"] if s["id"] in meta))
    check(f"{nom}: eventos y residuos conservados", len(c["eventos"]) == len(r["resultados"]["eventos"]) and len(c["verificaciones"]) == len(r["resultados"]["residuos"]))

# 2. Simulación del núcleo
for nombre in ("estudio-calor",):
    sol = json.loads((EJ / f"adimensionalizacion-{nombre}-solicitud.json").read_text(encoding="utf-8"))
    sol["estudio"]["analisis"] = ["simulacion"]
    sim = procesar(sol)["estudio"]["simulacion"]
    c = sim["resultados"]
    leer_resultados(c)
    ejes = {e["id"]: e for e in c["ejes"]}
    check(f"{nombre}: ejes tau y xi = tiempos y xi de la simulación", ejes["tau"]["valores"] == sim["tiempos"] and ejes["xi"]["valores"] == sim["xi"])
    check(f"{nombre}: ejes físicos t (s) y x (m) = restitución", ejes["t"]["valores"] == sim["fisico"]["tiempo"]["valoresSI"] and ejes["t"]["unidadSI"] == "s"
          and ejes["x"]["valores"] == sim["fisico"]["coordenada"]["valoresSI"] and ejes["x"]["unidadSI"] == "m")
    ser = {s["id"]: s for s in c["series"]}
    check(f"{nombre}: campo adimensional idéntico", ser["c_ad"]["valores"] == sim["campos"]["c_ad"] and ser["c_ad"]["unidadSI"] == "1")
    check(f"{nombre}: campo físico idéntico y con su unidad (mol/m^3)", ser["c"]["valores"] == sim["fisico"]["campos"]["c"] and ser["c"]["unidadSI"] == "mol/m^3"
          and "concentracion_molar" in ser["c"]["magnitudes"])

# 3. Rechazos
base = desde_ensamblaje_v2(json.loads((EJ / "motor-v2" / "motor-ensamblaje-v2-resolver-calentamiento-etanol-agua-respuesta.json").read_text(encoding="utf-8")))
for nombre, cambio, texto in [
    ("forma distinta del eje", lambda c: c["series"][0]["valores"].pop(), "se esperaban"),
    ("eje inexistente", lambda c: c["series"][0].update(ejes=["z"]), "eje inexistente"),
    ("unidad no SI (kJ)", lambda c: c["series"][0].update(unidadSI="kJ"), "no es una unidad SI"),
    ("dimensión que no corresponde a la unidad", lambda c: c["series"][0].update(dimension={"M": {"n": 1, "d": 1}}), "no coincide"),
    ("estado desconocido", lambda c: c.update(estado="casi"), "valor no admitido"),
    ("clave desconocida", lambda c: c.update(extra=1), "campos desconocidos"),
]:
    m = copy.deepcopy(base)
    cambio(m)
    try:
        leer_resultados(m)
        check(f"rechazo: {nombre}", False, "aceptado")
    except ErrorResultados as e:
        check(f"rechazo: {nombre}", texto in str(e), str(e))

print(f"\n{n[0] - len(fallos)} de {n[0]} comprobaciones correctas." if fallos else f"\nFormato de resultados: {n[0]} comprobaciones correctas.")
sys.exit(1 if fallos else 0)
