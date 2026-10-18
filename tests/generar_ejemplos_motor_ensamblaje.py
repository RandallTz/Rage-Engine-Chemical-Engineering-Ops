"""
Genera docs/ejemplos/motor-ensamblaje-* llamando a los endpoints reales
(/motor/ensamblajes/capacidades, /validar y /resolver) por la app ASGI.
Ningun numero esta escrito a mano. Las peticiones parten de las
formulaciones reales que prepara el frontend (tests/fixtures_ensamblaje/).

Despues, `node tests/verificar_contrato_ensamblaje.mjs` compila cada par
contra los tipos de frontend/app/motor/contratoEnsamblajeTermodinamico.ts.

Ejecutar desde la raiz del proyecto:
    python tests/generar_ejemplos_motor_ensamblaje.py
"""

import asyncio
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))

import httpx

from backend.main import app

_src = (RAIZ / "tests" / "validar_motor_ensamblaje.py").read_text(encoding="utf-8")
_ns = {"__file__": str(RAIZ / "tests" / "validar_motor_ensamblaje.py"), "__name__": "plantillas"}
exec(_src.split('print("1. Peticion')[0], _ns)        # solicitud(), dato(): constructores de la suite
solicitud = _ns["solicitud"]
DESTINO = RAIZ / "docs" / "ejemplos"
FIX = RAIZ / "tests" / "fixtures_ensamblaje"


def pedir(metodo, ruta, cuerpo=None):
    async def hacer():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ejemplos") as c:
            return await c.request(metodo, ruta, json=cuerpo, timeout=600)
    r = asyncio.run(hacer())
    assert r.status_code == 200, (ruta, r.status_code, r.text[:300])
    return r.json()


def escribir(nombre, datos):
    with open(DESTINO / nombre, "w", encoding="utf-8", newline="\n") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1, allow_nan=False)
        f.write("\n")


def fixture(n):
    return json.loads((FIX / f"{n}.json").read_text(encoding="utf-8"))["solicitud"]


def con_muestras(s, n):
    s["estudio"]["muestras"] = n
    return s


CASOS = [
    # (nombre, ruta, peticion)
    ("validar-incompleto", "validar", solicitud(V=("", "L"), sid="validar-incompleto")),
    ("validar-conflicto-dos-cierres", "validar", fixture("dos_cierres")),
    ("validar-conflicto-P-rigida", "validar", fixture("rigida_con_P")),
    ("validar-inicial-T-rigida", "validar", fixture("rigida_cerrada_T0")),
    ("resolver-rigida-calentamiento", "resolver", con_muestras(fixture("rigida_cerrada_U0"), 21)),
    ("resolver-abierta-presion-constante", "resolver", con_muestras(fixture("abierta_presion"), 21)),
    ("resolver-llenado-rigido", "resolver", solicitud(
        V=("0.1", "m3"), m0=("100", "kg"), E0=("T", "300", "K"), Q=None, tf=("10", "s"), muestras=11,
        corrientes=[{"id": 1, "sentido": "entrada", "F": ("0.02", "kg/s"), "T": ("330", "K"), "P": "continuidad"}],
        extracciones={"1": {"tipo": "mezcla_homogenea"}}, sid="llenado")),
    ("resolver-vaciado-con-ebullicion", "resolver", solicitud(
        V=("0.5", "m3"), m0=("400", "kg"), E0=("T", "350", "K"), Q=("20", "kW"), tf=("100", "s"), muestras=21,
        corrientes=[{"id": 2, "sentido": "salida", "F": ("1.5", "kg/s")}],
        extracciones={"2": {"tipo": "mezcla_homogenea"}}, sid="vaciado")),
    ("resolver-presion-suave-adiabatica", "resolver", solicitud(
        "presion", P=("3e5 + 2e5*sin(0.05*t)", "Pa"), m0=("1", "kg"), E0=("T", "500", "K"), Q=None,
        tf=("100", "s"), muestras=21, rtol=1e-10, sid="presion-suave")),
    ("resolver-ebullicion-presion-constante", "resolver", solicitud(
        "presion", P=("1", "bar"), m0=("1", "kg"), E0=("T", "293.15", "K"), Q=("10", "kW"), tf=("300", "s"),
        muestras=31, sid="ebullicion")),
    ("resolver-condensacion-rigida", "resolver", solicitud(
        V=("1", "m3"), m0=("2", "kg"), E0=("T", "500", "K"), Q=("-5", "kW"), tf=("400", "s"), muestras=21,
        sid="condensacion")),
    ("resolver-extraccion-liquido", "resolver", solicitud(
        V=("1", "m3"), m0=("5", "kg"), E0=("T", "400", "K"), Q=None, tf=("20", "s"), muestras=21,
        corrientes=[{"id": 2, "sentido": "salida", "F": ("0.5", "kg/s"),
                     "extraccion": {"tipo": "fase", "fase": "liquido"}}], sid="extraccion-liquido")),
    ("resolver-cambio-fase-prohibido", "resolver", solicitud(
        "presion", P=("1", "bar"), m0=("1", "kg"), E0=("T", "293.15", "K"), Q=("10", "kW"), tf=("300", "s"),
        muestras=31, politica={"cantidad": "monofasico", "cambioInterno": "prohibido",
                               "evaluacion": "equilibrio_estable"}, sid="prohibido")),
]


def main():
    escribir("motor-ensamblaje-capacidades.json", pedir("GET", "/motor/ensamblajes/capacidades"))
    for nombre, ruta, s in CASOS:
        r = pedir("POST", f"/motor/ensamblajes/{ruta}", s)
        estado = r["estado"] if ruta == "resolver" else r["recuento"]["estado"]
        print(f"  {nombre}: {estado}")
        escribir(f"motor-ensamblaje-{nombre}-peticion.json", s)
        escribir(f"motor-ensamblaje-{nombre}-respuesta.json", r)


if __name__ == "__main__":
    main()
