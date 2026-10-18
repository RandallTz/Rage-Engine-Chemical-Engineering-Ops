"""
Dos ejemplos de DEMOSTRACION (no pruebas) para mostrar el motor, como hojas listas para resolver:

  1. Agua / 1-butanol calentada a 1 atm (UNIFAC original): dos liquidos -> heteroazeotropo con tres fases
     (L-L-V, meseta a T constante) -> liquido + vapor -> vapor.
  2. Destilacion diferencial (Rayleigh) etanol-agua (NRTL ChemSep): se calienta y se extrae el vapor; el liquido
     se empobrece en etanol y su temperatura de burbuja sube.

Escribe frontend/app/motor/ejemplosDemostracion.json (lo lee hojasDemostracion.ts) y, como referencia,
docs/ejemplos/demostracion/ con la peticion y la respuesta real de POST /motor/ensamblajes/resolver.

Ejecutar desde la raiz del proyecto:
    python tests/generar_ejemplos_demostracion.py
"""

import asyncio
import json
import sys
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))
warnings.filterwarnings("ignore")

import httpx

from backend.main import app
from solicitudes_v2 import Red

DOCS = RAIZ / "docs" / "ejemplos" / "demostracion"
FRONT = RAIZ / "frontend" / "app" / "motor" / "ejemplosDemostracion.json"


def ejemplos():
    par = ("agua", "butanol")
    yield {"id": "heteroazeotropo-agua-butanol",
           "nombre": "Demostración · Agua y 1-butanol: dos líquidos, heteroazeótropo y vapor",
           "volumen": "Hervidor",
           "solicitud": (Red("demo-heteroazeotropo", par, tf=("520", "s"), muestras=27)
                         .paquete("p", "unifac-original-public")
                         .volumen("A", "p", {"agua": ("0.75", "mol"), "butanol": ("0.25", "mol")}, ("T", "300", "K"),
                                  P=("101325", "Pa"), base="molar")
                         .calor("q", None, "A", Q=("100", "W"), Tfrontera=("700", "K"))).solicitud()}
    par = ("etanol", "agua")
    yield {"id": "rayleigh-etanol-agua",
           "nombre": "Demostración · Destilación diferencial etanol–agua (Rayleigh)",
           "volumen": "Alambique",
           "solicitud": (Red("demo-rayleigh", par, tf=("340", "s"), muestras=35)
                         .paquete("p", "nrtl-chemsep")
                         .volumen("A", "p", {"etanol": ("0.3", "mol"), "agua": ("0.7", "mol")}, ("T", "355", "K"),
                                  P=("101325", "Pa"), base="molar")
                         .calor("q", None, "A", Q=("100", "W"), Tfrontera=("700", "K"))
                         .corriente("d", "A", None, par, ("0.0015", "mol/s"), base="molar",
                                    extraccion={"A": {"tipo": "fase", "fase": "vapor"}})).solicitud()}


def resolver(cuerpo):
    async def hacer():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://demo") as c:
            return await c.post("/motor/ensamblajes/resolver", json=cuerpo, timeout=1800)
    r = asyncio.run(hacer())
    assert r.status_code == 200, r.text[:300]
    return r.json()


def main():
    DOCS.mkdir(parents=True, exist_ok=True)
    salida = []
    for e in ejemplos():
        r = resolver(e["solicitud"])
        res = r.get("resultados") or {}
        assert r["estado"] == "resuelto" and res["certificacion"]["estado"] == "cumple", (e["id"], r["estado"])
        for nombre, datos in (("peticion", e["solicitud"]), ("respuesta", r)):
            with open(DOCS / f"demostracion-{e['id']}-{nombre}.json", "w", encoding="utf-8", newline="\n") as f:
                json.dump(datos, f, ensure_ascii=False, indent=1, allow_nan=False)
                f.write("\n")
        salida.append({"id": e["id"], "nombre": e["nombre"], "volumen": e["volumen"],
                       "fuente": f"docs/ejemplos/demostracion/demostracion-{e['id']}-peticion.json",
                       "solicitud": e["solicitud"]})
        print(e["id"], r["estado"], res["certificacion"]["estado"],
              [(x["codigo"], round(x["tiempo"], 1)) for x in res["eventos"]])
    with open(FRONT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(salida, f, ensure_ascii=False, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main()
