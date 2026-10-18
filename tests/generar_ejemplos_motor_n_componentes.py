"""
Genera docs/ejemplos/motor-n-componentes/ desde los endpoints reales (POST /motor/termodinamica/evaluar,
POST /motor/ensamblajes/resolver y validar, GET capacidades). Ningun numero esta escrito a mano.
Despues: node tests/verificar_contrato_ensamblaje_v2.mjs (tambien recorre este directorio).

Ejecutar desde la raiz del proyecto:
    python tests/generar_ejemplos_motor_n_componentes.py
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
from solicitudes_v2 import CAS, POL, Red

DESTINO = RAIZ / "docs" / "ejemplos" / "motor-n-componentes"


def pedir(metodo, ruta, cuerpo=None, params=None):
    async def hacer():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ejemplos") as c:
            return await c.request(metodo, ruta, json=cuerpo, params=params, timeout=2400)
    r = asyncio.run(hacer())
    assert r.status_code == 200, (ruta, r.status_code, r.text[:300])
    return r.json()


def escribir(nombre, datos):
    DESTINO.mkdir(parents=True, exist_ok=True)
    with open(DESTINO / nombre, "w", encoding="utf-8", newline="\n") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1, allow_nan=False)
        f.write("\n")


def puntual(sid, nombres, modelo, T, P, fr):
    return {"revision": 1, "solicitudId": sid, "propietarioId": "ejemplos",
            "componentes": [{"id": k + 1, "nombre": n, "simbolo": n[:2], "identidadQuimica": {"cas": CAS[n]}}
                            for k, n in enumerate(nombres)],
            "declaracion": {"modelo": {"id": modelo, "version": "1"}, "politica": dict(POL),
                            "especificacion": {"tipo": "TP", "T": {"valor": T, "unidad": "K"},
                                               "P": {"valor": P, "unidad": "Pa"},
                                               "composicion": {"base": "molar",
                                                               "fracciones": {str(k + 1): f for k, f in enumerate(fr)}}}}}


N5 = ("benceno", "tolueno", "etanol", "metanol", "agua")
N7 = ("benceno", "tolueno", "etanol", "metanol", "agua", "acetato", "butanol")
NA = ("etanol", "benceno", "tolueno", "metanol")
NB = ("agua", "etanol", "acetato", "metanol")
ESTATICOS = [
    ("termodinamica-ideal-5-lv", puntual("n5", N5, "mezcla-ideal", 355, 101325, [0.2] * 5)),
    ("termodinamica-ideal-7-lv", puntual("n7", N7, "mezcla-ideal", 360, 101325, [round(1 / 7, 15)] * 6 + [1 - 6 * round(1 / 7, 15)])),
    ("termodinamica-nrtl-4-lv", puntual("na", NA, "nrtl-chemsep", 345, 101325, [0.25] * 4)),
    ("termodinamica-nrtl-4-ll", puntual("nb", NB, "nrtl-chemsep", 300, 101325, [0.7, 0.04, 0.24, 0.02])),
    ("termodinamica-nrtl-4-par-ausente", puntual("nx", ("agua", "benceno", "etanol", "metanol"), "nrtl-chemsep", 345,
                                                 101325, [0.25] * 4)),
]


def dinamicos():
    yield "resolver-calentamiento-ideal-5", (
        Red("n5-cal", N5, tf=("300", "s"), muestras=6).paquete("p", "mezcla-ideal")
        .volumen("A", "p", {k: ("0.2", "mol") for k in N5}, ("T", "330", "K"), P=("101325", "Pa"), base="molar")
        .calor("q", None, "A", Q=("100", "W"), Tfrontera=("700", "K"))).solicitud()
    yield "resolver-calentamiento-nrtl-4", (
        Red("n4-cal", NA, tf=("300", "s"), muestras=6).paquete("p", "nrtl-chemsep")
        .volumen("A", "p", {k: ("0.25", "mol") for k in NA}, ("T", "330", "K"), P=("101325", "Pa"), base="molar")
        .calor("q", None, "A", Q=("100", "W"), Tfrontera=("700", "K"))).solicitud()
    yield "resolver-red-ideal-5-especie-entrante", (
        Red("n5-red", N5, tf=("200", "s"), muestras=5).paquete("p", "mezcla-ideal")
        .volumen("A", "p", {"benceno": ("0.3", "mol"), "tolueno": ("0.3", "mol"), "etanol": ("0.2", "mol"),
                            "metanol": ("0.2", "mol"), "agua": ("0", "mol")}, ("T", "340", "K"), P=("101325", "Pa"),
                 base="molar")
        .volumen("B", "p", {"benceno": ("0.1", "mol"), "tolueno": ("0.4", "mol"), "etanol": ("0.1", "mol"),
                            "metanol": ("0.1", "mol"), "agua": ("0.3", "mol")}, ("T", "320", "K"), P=("101325", "Pa"),
                 base="molar")
        .corriente("s", "A", "B", N5, ("-0.001", "mol/s"), base="molar",
                   extraccion={"A": {"tipo": "mezcla_homogenea"}, "B": {"tipo": "mezcla_homogenea"}})
        .calor("c", "A", "B", G=("0.5", "W/K"))).solicitud()
    yield "validar-nrtl-4-par-ausente", (
        Red("n4-par", ("agua", "benceno", "etanol", "metanol"), tf=("10", "s"), muestras=3).paquete("p", "nrtl-chemsep")
        .volumen("A", "p", {k: ("0.25", "mol") for k in ("agua", "benceno", "etanol", "metanol")}, ("T", "330", "K"),
                 P=("101325", "Pa"), base="molar", adiabatico=True)).solicitud()


def main():
    escribir("motor-ensamblaje-v2-capacidades.json", pedir("GET", "/motor/ensamblajes/capacidades", params={"revision": 2}))
    for nombre, cuerpo in ESTATICOS:
        r = pedir("POST", "/motor/termodinamica/evaluar", cuerpo)
        escribir(f"motor-{nombre}-peticion.json", cuerpo)
        escribir(f"motor-{nombre}-respuesta.json", r)
        print(nombre, r["estado"], [d["codigo"] for d in r["diagnosticos"]])
    for nombre, cuerpo in dinamicos():
        ruta = "/motor/ensamblajes/resolver" if nombre.startswith("resolver") else "/motor/ensamblajes/validar"
        r = pedir("POST", ruta, cuerpo)
        escribir(f"motor-ensamblaje-v2-{nombre}-peticion.json", cuerpo)
        escribir(f"motor-ensamblaje-v2-{nombre}-respuesta.json", r)
        print(nombre, r.get("estado", r.get("recuento", {}).get("estado")),
              (r.get("resultados") or {}).get("certificacion", {}).get("estado"))


if __name__ == "__main__":
    main()
