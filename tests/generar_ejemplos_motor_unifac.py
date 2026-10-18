"""
Genera docs/ejemplos/motor-unifac/ desde los endpoints reales (GET capacidades de las tres rutas, POST
/motor/termodinamica/evaluar, /motor/ensamblajes/{validar,resolver} y /motor/termodinamica/diagramas/trazar)
con los paquetes unifac-original-public, unifac-dortmund-public y unifac-original-lle-public. Ningun numero
esta escrito a mano. Los rechazos llevan 'rechazo' en el nombre.

Los rechazos por dato ausente (asignacion, interaccion) no se pueden provocar con el catalogo actual, que esta
completo: se SIMULAN en este proceso sustituyendo temporalmente la asignacion o la tabla (monkeypatch), sin
tocar ningun archivo de datos. Sus nombres llevan 'simulado'. El resto son respuestas sin intervencion
(incluido el rechazo REAL del metanol con la tabla LLE, que no tiene el grupo CH3OH).
Despues: node tests/verificar_contrato_unifac.mjs

Ejecutar desde la raiz del proyecto:
    python tests/generar_ejemplos_motor_unifac.py
"""

import asyncio
import contextlib
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
from core import unifac
from solicitudes_v2 import CAS, POL, Red

DESTINO = RAIZ / "docs" / "ejemplos" / "motor-unifac"
PAQ = "unifac-original-public"


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


def comp(nombres):
    return [{"id": k + 1, "nombre": n, "simbolo": n[:2], "identidadQuimica": {"cas": CAS[n]}} for k, n in enumerate(nombres)]


def puntual(sid, nombres, T, P, fr, modelo=PAQ):
    return {"revision": 1, "solicitudId": sid, "propietarioId": "ejemplos", "componentes": comp(nombres),
            "declaracion": {"modelo": {"id": modelo, "version": "1"}, "politica": dict(POL),
                            "especificacion": {"tipo": "TP", "T": {"valor": T, "unidad": "K"},
                                               "P": {"valor": P, "unidad": "Pa"},
                                               "composicion": {"base": "molar",
                                                               "fracciones": {str(k + 1): f for k, f in enumerate(fr)}}}}}


def diagrama(sid, par, corte, modelo=PAQ):
    return {"revision": 1, "solicitudId": sid, "componentes": comp(par), "modelo": {"id": modelo, "version": "1"},
            "componenteEjeId": 1, "corte": corte, "intervaloComposicion": [0.0, 1.0], "resolucion": "exploratoria"}


@contextlib.contextmanager
def sin_asignacion(cas):
    original = unifac.asignacion

    def falsa(c, variante):
        if c == cas:
            raise unifac.FaltaDatoUNIFAC(f"Sin asignacion de grupos UNIFAC ({variante}) para {c} en la base DDBST "
                                         "(SIMULADO en el generador de ejemplos).",
                                         {"tipo": "asignacion_ausente", "cas": c, "variante": variante})
        return original(c, variante)
    unifac.asignacion = falsa
    try:
        yield
    finally:
        unifac.asignacion = original


@contextlib.contextmanager
def sin_interaccion(m, n):
    t = unifac.tablas("original")
    vieja = t["inter"]
    t["inter"] = {k: v for k, v in vieja.items() if k != (m, n)}
    try:
        yield
    finally:
        t["inter"] = vieja


N2 = ("etanol", "agua")
N4 = ("agua", "etanol", "acetato", "metanol")
N5 = ("benceno", "tolueno", "etanol", "metanol", "agua")
N7 = ("benceno", "tolueno", "etanol", "metanol", "agua", "acetato", "butanol")
DO, LE = "unifac-dortmund-public", "unifac-original-lle-public"
PUNTUALES = [
    ("unifac-2-lv", puntual("u2", N2, 355, 101325, [0.5, 0.5]), None),
    ("unifac-2-ll-agua-butanol", puntual("u2b", ("agua", "butanol"), 298.15, 101325, [0.75, 0.25]), None),
    ("unifac-4-ll", puntual("u4", N4, 300, 101325, [0.7, 0.04, 0.24, 0.02]), None),
    ("unifac-5-llv", puntual("u5", N5, 341, 101325, [0.2] * 5), None),
    ("unifac-7-lv", puntual("u7", N7, 351, 101325, [round(1 / 7, 15)] * 6 + [1 - 6 * round(1 / 7, 15)]), None),
    ("unifac-dortmund-4-lv", puntual("d4", N4, 346, 101325, [0.25] * 4, DO), None),
    ("unifac-lle-2-ll-agua-butanol", puntual("l2", ("agua", "butanol"), 298.15, 101325, [0.75, 0.25], LE), None),
    ("unifac-lle-6-ll", puntual("l6", ("agua", "etanol", "benceno", "tolueno", "butanol", "acetato"), 300, 101325,
                                [round(1 / 6, 15)] * 5 + [1 - 5 * round(1 / 6, 15)], LE), None),
    ("rechazo-unifac-lle-metanol-sin-grupo", puntual("lm", ("etanol", "metanol"), 300, 101325, [0.5, 0.5], LE), None),
    ("rechazo-unifac-lle-fuera-de-dominio", puntual("lt", ("agua", "butanol"), 330, 101325, [0.75, 0.25], LE), None),
    ("rechazo-unifac-simulado-asignacion-ausente", puntual("ua", N2, 355, 101325, [0.5, 0.5]),
     lambda: sin_asignacion(CAS["agua"])),
    ("rechazo-unifac-simulado-interaccion-ausente", puntual("ui", N2, 355, 101325, [0.5, 0.5]),
     lambda: sin_interaccion(1, 7)),
]


def dinamicos():
    yield "resolver-unifac-calentamiento-2", (
        Red("u2-cal", N2, tf=("300", "s"), muestras=6).paquete("p", PAQ)
        .volumen("A", "p", {k: ("0.5", "mol") for k in N2}, ("T", "330", "K"), P=("101325", "Pa"), base="molar")
        .calor("q", None, "A", Q=("100", "W"), Tfrontera=("700", "K"))).solicitud(), None
    yield "resolver-unifac-calentamiento-4", (
        Red("u4-cal", N4, tf=("300", "s"), muestras=6).paquete("p", PAQ)
        .volumen("A", "p", {k: ("0.25", "mol") for k in N4}, ("T", "330", "K"), P=("101325", "Pa"), base="molar")
        .calor("q", None, "A", Q=("100", "W"), Tfrontera=("700", "K"))).solicitud(), None
    yield "resolver-unifac-red-5-especie-entrante", (
        Red("u5-red", N5, tf=("200", "s"), muestras=5).paquete("p", PAQ)
        .volumen("A", "p", {"benceno": ("0.3", "mol"), "tolueno": ("0.3", "mol"), "etanol": ("0.2", "mol"),
                            "metanol": ("0.2", "mol"), "agua": ("0", "mol")}, ("T", "335", "K"), P=("101325", "Pa"),
                 base="molar")
        .volumen("B", "p", {"benceno": ("0.1", "mol"), "tolueno": ("0.4", "mol"), "etanol": ("0.1", "mol"),
                            "metanol": ("0.1", "mol"), "agua": ("0.3", "mol")}, ("T", "320", "K"), P=("101325", "Pa"),
                 base="molar")
        .corriente("s", "A", "B", N5, ("-0.001", "mol/s"), base="molar",
                   extraccion={"A": {"tipo": "mezcla_homogenea"}, "B": {"tipo": "mezcla_homogenea"}})
        .calor("c", "A", "B", G=("0.5", "W/K"))).solicitud(), None
    yield "resolver-unifac-monofasico-detenido", (
        Red("u2-mono", N2, tf=("300", "s"), muestras=6).paquete("p", PAQ)
        .volumen("A", "p", {k: ("0.5", "mol") for k in N2}, ("T", "330", "K"), P=("101325", "Pa"), base="molar",
                 politica={"cantidad": "monofasico", "cambioInterno": "permitido", "evaluacion": "equilibrio_estable"})
        .calor("q", None, "A", Q=("100", "W"), Tfrontera=("700", "K"))).solicitud(), None
    yield "resolver-unifac-dortmund-calentamiento-4", (
        Red("d4-cal", N4, tf=("300", "s"), muestras=6).paquete("p", DO)
        .volumen("A", "p", {k: ("0.25", "mol") for k in N4}, ("T", "330", "K"), P=("101325", "Pa"), base="molar")
        .calor("q", None, "A", Q=("100", "W"), Tfrontera=("700", "K"))).solicitud(), None
    yield "resolver-unifac-lle-mezcla-agua-butanol", (
        Red("l2-mez", ("agua", "butanol"), tf=("200", "s"), muestras=5).paquete("p", LE)
        .volumen("A", "p", {"agua": ("1.0", "mol"), "butanol": ("0.001", "mol")}, ("T", "298.15", "K"),
                 P=("101325", "Pa"), base="molar", adiabatico=True)
        .volumen("B", "p", {"agua": ("0.001", "mol"), "butanol": ("0.5", "mol")}, ("T", "298.15", "K"),
                 P=("101325", "Pa"), base="molar", adiabatico=True)
        .corriente("s", "B", "A", ("agua", "butanol"), ("0.001", "mol/s"), base="molar",
                   extraccion={"B": {"tipo": "mezcla_homogenea"}})).solicitud(), None
    yield "validar-rechazo-unifac-simulado-asignacion-ausente", (
        Red("u4-asig", N4, tf=("10", "s"), muestras=3).paquete("p", PAQ)
        .volumen("A", "p", {k: ("0.25", "mol") for k in N4}, ("T", "330", "K"), P=("101325", "Pa"), base="molar",
                 adiabatico=True)).solicitud(), lambda: sin_asignacion(CAS["acetato"])


DIAGRAMAS = [
    ("txy-etanol-agua-unifac", diagrama("dt", N2, {"tipo": "Txy", "P": {"valor": 101325, "unidad": "Pa"}}), None),
    ("pxy-etanol-agua-unifac", diagrama("dp", N2, {"tipo": "Pxy", "T": {"valor": 350, "unidad": "K"}}), None),
    ("txy-agua-butanol-unifac", diagrama("db", ("agua", "butanol"), {"tipo": "Txy", "P": {"valor": 101325, "unidad": "Pa"}}),
     None),
    ("txy-etanol-agua-unifac-dortmund", diagrama("dd", N2, {"tipo": "Txy", "P": {"valor": 101325, "unidad": "Pa"}}, DO),
     None),
    ("pxy-etanol-agua-unifac-lle", diagrama("dl", N2, {"tipo": "Pxy", "T": {"valor": 298.15, "unidad": "K"}}, LE), None),
    ("rechazo-unifac-simulado-interaccion-ausente",
     diagrama("dx", N2, {"tipo": "Txy", "P": {"valor": 101325, "unidad": "Pa"}}), lambda: sin_interaccion(7, 1)),
]


def main():
    escribir("motor-termodinamica-capacidades.json", pedir("GET", "/motor/termodinamica/capacidades"))
    escribir("motor-ensamblaje-v2-capacidades.json", pedir("GET", "/motor/ensamblajes/capacidades", params={"revision": 2}))
    escribir("motor-diagramas-capacidades.json", pedir("GET", "/motor/termodinamica/diagramas/capacidades"))
    for nombre, cuerpo, ctx in PUNTUALES:
        with (ctx() if ctx else contextlib.nullcontext()):
            r = pedir("POST", "/motor/termodinamica/evaluar", cuerpo)
        escribir(f"motor-termodinamica-{nombre}-peticion.json", cuerpo)
        escribir(f"motor-termodinamica-{nombre}-respuesta.json", r)
        print(nombre, r["estado"], [d["codigo"] for d in r["diagnosticos"]])
    for nombre, cuerpo, ctx in dinamicos():
        ruta = "/motor/ensamblajes/resolver" if nombre.startswith("resolver") else "/motor/ensamblajes/validar"
        with (ctx() if ctx else contextlib.nullcontext()):
            r = pedir("POST", ruta, cuerpo)
        escribir(f"motor-ensamblaje-v2-{nombre}-peticion.json", cuerpo)
        escribir(f"motor-ensamblaje-v2-{nombre}-respuesta.json", r)
        diags = (r.get("validacion") or r).get("diagnosticos", [])
        print(nombre, r.get("estado", r.get("recuento", {}).get("estado")),
              (r.get("resultados") or {}).get("certificacion", {}).get("estado"), [d["codigo"] for d in diags][:4])
    for nombre, cuerpo, ctx in DIAGRAMAS:
        with (ctx() if ctx else contextlib.nullcontext()):
            r = pedir("POST", "/motor/termodinamica/diagramas/trazar", cuerpo)
        escribir(f"motor-diagramas-{nombre}-peticion.json", cuerpo)
        escribir(f"motor-diagramas-{nombre}-respuesta.json", r)
        print(nombre, r["estado"], [p["tipo"] for p in r["puntosEspeciales"]], [d["codigo"] for d in r["diagnosticos"]][:4])


if __name__ == "__main__":
    main()
