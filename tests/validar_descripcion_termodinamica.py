"""
POST /modelo/termodinamica (core/termodinamica/descripcion.py): lo que muestra el panel Termodinámica del
Engine. Para ejemplos publicados de cada familia (mezcla ideal, UNIFAC original y ELL, agua IAPWS-95) y
para modelos con estado supuesto (motor de balances): el cierre declarado, las fases candidatas IGUALES a
las de la capa que usa el compilador, la familia del modelo de estado y las relaciones siempre presentes.
No calcula estados.

Ejecutar desde la raíz:  python tests/validar_descripcion_termodinamica.py
"""

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from fastapi import HTTPException  # noqa: E402

from backend.api_modelo import termodinamica  # noqa: E402
from core.modelo import desde_ensamblaje_v2  # noqa: E402
from core.termodinamica import candidatas  # noqa: E402

EJ = RAIZ / "docs" / "ejemplos"
n, fallos = [0], []


def check(nombre, cond, detalle=""):
    n[0] += 1
    if not cond:
        fallos.append(nombre)
        print(f"FALLO {nombre} {detalle}")


CASOS = [("motor-unifac/motor-ensamblaje-v2-resolver-unifac-calentamiento-2", "actividad", "unifac_original", 3),
         ("motor-unifac/motor-ensamblaje-v2-resolver-unifac-lle-mezcla-agua-butanol", "actividad", "unifac_lle", 3),
         ("motor-n-componentes/motor-ensamblaje-v2-resolver-calentamiento-ideal-5", "ideal", None, 2)]
agua = [EJ / "motor-v2" / "motor-ensamblaje-v2-resolver-contacto-dos-aguas-peticion.json"]
for ruta, fam, liq, ncand in CASOS:
    f = EJ / f"{ruta}-peticion.json"
    if not f.exists():
        alternativas = sorted(f.parent.glob("*ideal*peticion.json"))
        f = alternativas[0] if alternativas else f
    pet = json.loads(f.read_text(encoding="utf-8"))
    d = termodinamica({"solicitudV2": pet})
    m = desde_ensamblaje_v2(pet)
    nom = f.name.replace("-peticion.json", "")
    check(f"{nom}: formato y un volumen descrito por cada volumen del modelo",
          d["formato"] == "rage.modelo.termodinamica" and [v["id"] for v in d["volumenes"]] == [v["id"] for v in m["volumenes"]])
    for v in d["volumenes"]:
        check(f"{nom}/{v['id']}: cierre de equilibrio con su política", v["cierre"]["tipo"] == "equilibrio" and "cantidad" in v["cierre"]["politica"])
        check(f"{nom}/{v['id']}: familia del modelo de estado {fam}", v["modeloEstado"]["familia"] == fam and v["modeloEstado"]["modeloLiquido"] == liq, v["modeloEstado"])
        check(f"{nom}/{v['id']}: fases candidatas iguales a las de la capa ({ncand})", v["candidatas"] == candidatas(m, v["id"]) and len(v["candidatas"]) == ncand, v["candidatas"])
        check(f"{nom}/{v['id']}: relaciones de estado y equilibrio siempre presentes",
              {r["familia"] for r in v["relaciones"]} >= {"estado", "equilibrio"})
for f in agua[:1]:
    d = termodinamica({"solicitudV2": json.loads(f.read_text(encoding="utf-8"))})
    check(f"{f.name}: agua pura con IAPWS-95 y dos candidatas", all(v["modeloEstado"]["familia"] == "iapws95" and v["candidatas"] == ["vapor-1", "liquido-1"] for v in d["volumenes"]), d["volumenes"][0].get("candidatas"))
ej = json.loads((EJ / "modelo-comun" / "balances-llenado-entrada-caliente.json").read_text(encoding="utf-8"))["modelo"]
d = termodinamica({"modelo": ej})
v = d["volumenes"][0]
check("modelo con u(T) supuesta: cierre supuesto con su motivo, sin candidatas ni paquete",
      v["cierre"] == {"tipo": "supuesto", "supuesto": "u_lineal", "motivo": "prueba"} and v["candidatas"] is None and v["modeloEstado"] is None, v["cierre"])
check("modelo con u(T) supuesta: la relación de estado aparece como supuesta", any(r["id"].endswith(".supuesto") for r in v["relaciones"]), v["relaciones"])
try:
    termodinamica({"solicitudV2": {"no": "es una solicitud"}})
    check("solicitud inválida: 422 con motivo", False)
except HTTPException as e:
    check("solicitud inválida: 422 con motivo", e.status_code == 422)
print(f"\n{n[0] - len(fallos)} de {n[0]} comprobaciones correctas." if fallos else f"\nDescripción termodinámica: {n[0]} comprobaciones correctas.")
sys.exit(1 if fallos else 0)
