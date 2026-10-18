"""
Genera docs/ejemplos/motor-catalogo/ desde las rutas reales: GET /motor/catalogo, rechazos de admision por especie
(F9-R3, sustancia no registrada), la acetona (F2.6), corrientes entre paquetes (F2.5) y sustituciones de datos
puros en las tres rutas (F2.4). Ningun numero esta escrito a mano.
Despues: node tests/verificar_contrato_catalogo.mjs

Ejecutar desde la raiz del proyecto:
    python tests/generar_ejemplos_motor_catalogo.py
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

DESTINO = RAIZ / "docs" / "ejemplos" / "motor-catalogo"


def pedir(metodo, ruta, cuerpo=None):
    async def hacer():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ejemplos") as c:
            return await c.request(metodo, ruta, json=cuerpo, timeout=600)
    r = asyncio.run(hacer())
    assert r.status_code == 200, (ruta, r.status_code, r.text[:300])
    return r.json()


def escribir(nombre, datos):
    DESTINO.mkdir(parents=True, exist_ok=True)
    with open(DESTINO / nombre, "w", encoding="utf-8", newline="\n") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1, allow_nan=False)
        f.write("\n")


def puntual(sid, comps, modelo):
    return {"revision": 1, "solicitudId": sid, "propietarioId": "ejemplos",
            "componentes": [{"id": k + 1, "nombre": n, "simbolo": n[:2], "identidadQuimica": {"cas": c}}
                            for k, (n, c) in enumerate(comps)],
            "declaracion": {"modelo": {"id": modelo, "version": "1"}, "politica": dict(POL),
                            "especificacion": {"tipo": "TP", "T": {"valor": 300, "unidad": "K"},
                                               "P": {"valor": 101325, "unidad": "Pa"},
                                               "composicion": {"base": "molar", "fracciones": {
                                                   str(k + 1): 1 / len(comps) for k in range(len(comps))}}}}}


VL = {CAS["etanol"]: {"volumen_liquido": {"valor": 60.0, "unidad": "cm3/mol", "fuente": "ejemplo F2.4 (valor ilustrativo)"}}}


def sust(cuerpo, d):
    cuerpo["declaracion"]["datosPuros"] = d
    return cuerpo


def diagrama(sid, par, modelo, corte, datos=None):
    c = {"revision": 1, "solicitudId": sid,
         "componentes": [{"id": k + 1, "nombre": n, "simbolo": n[:2], "identidadQuimica": {"cas": CAS[n]}}
                         for k, n in enumerate(par)],
         "modelo": {"id": modelo, "version": "1"}, "componenteEjeId": 1, "corte": corte,
         "intervaloComposicion": [0.0, 1.0], "resolucion": "exploratoria"}
    if datos is not None:
        c["datosPuros"] = datos
    return c


def redes():
    par = ("etanol", "agua")
    yield "resolver-corriente-nrtl-a-unifac", (
        Red("f25", par, tf=("200", "s"), muestras=5).paquete("pn", "nrtl-chemsep").paquete("pu", "unifac-original-public")
        .volumen("A", "pn", {"etanol": ("0.7", "mol"), "agua": ("0.3", "mol")}, ("T", "340", "K"), P=("101325", "Pa"),
                 base="molar")
        .volumen("B", "pu", {"etanol": ("0.2", "mol"), "agua": ("0.8", "mol")}, ("T", "320", "K"), P=("101325", "Pa"),
                 base="molar")
        .corriente("s", "A", "B", par, ("0.002", "mol/s"), base="molar", extraccion={"A": {"tipo": "mezcla_homogenea"}})
        .calor("c", "A", "B", G=("0.5", "W/K"))).solicitud()
    yield "validar-rechazo-corriente-iapws-a-mezcla", (
        Red("f25b", ("agua",), tf=("50", "s"), muestras=3).paquete("pa", "agua-iapws95").paquete("pm", "mezcla-ideal")
        .volumen("A", "pa", {"agua": ("1", "mol")}, ("T", "330", "K"), P=("101325", "Pa"), base="molar")
        .volumen("B", "pm", {"agua": ("1", "mol")}, ("T", "320", "K"), P=("101325", "Pa"), base="molar")
        .corriente("s", "A", "B", ("agua",), ("0.001", "mol/s"), base="molar",
                   extraccion={"A": {"tipo": "mezcla_homogenea"}})).solicitud()
    yield "resolver-contacto-iapws-y-mezcla", (
        Red("f25c", ("agua",), tf=("50", "s"), muestras=3).paquete("pa", "agua-iapws95").paquete("pm", "mezcla-ideal")
        .volumen("A", "pa", {"agua": ("1", "mol")}, ("T", "330", "K"), P=("101325", "Pa"), base="molar")
        .volumen("B", "pm", {"agua": ("1", "mol")}, ("T", "320", "K"), P=("101325", "Pa"), base="molar")
        .calor("c", "A", "B", G=("0.5", "W/K"))).solicitud()
    sol = (Red("f24", par, tf=("100", "s"), muestras=3).paquete("p", "nrtl-chemsep")
           .volumen("A", "p", {"etanol": ("0.5", "mol"), "agua": ("0.5", "mol")}, ("T", "330", "K"), P=("101325", "Pa"),
                    base="molar")
           .calor("q", None, "A", Q=("20", "W"), Tfrontera=("700", "K"))).solicitud()
    sol["paquetes"][0]["datosPuros"] = VL
    yield "resolver-sustitucion-vl-etanol", sol
    yield "resolver-acetona-agua-unifac", (
        Red("f26", ("acetona", "agua"), tf=("200", "s"), muestras=5).paquete("p", "unifac-original-public")
        .volumen("A", "p", {"acetona": ("0.5", "mol"), "agua": ("0.5", "mol")}, ("T", "320", "K"), P=("101325", "Pa"),
                 base="molar")
        .calor("q", None, "A", Q=("100", "W"), Tfrontera=("700", "K"))).solicitud()


DIAGRAMAS = [
    ("txy-acetona-metanol-unifac", diagrama("am", ("acetona", "metanol"), "unifac-original-public",
                                            {"tipo": "Txy", "P": {"valor": 101325, "unidad": "Pa"}})),
    ("pxy-etanol-agua-nrtl-sustitucion-vl", diagrama("ds", ("etanol", "agua"), "nrtl-chemsep",
                                                     {"tipo": "Pxy", "T": {"valor": 350, "unidad": "K"}}, VL)),
]


CASOS = [
    ("rechazo-metanol-puro-unifac-ell", puntual("f9r3", [("metanol", CAS["metanol"])], "unifac-original-lle-public")),
    ("rechazo-etanol-puro-nrtl-lle", puntual("lle1", [("etanol", CAS["etanol"])], "nrtl-lle-agua-butanol")),
    ("rechazo-hexano-no-registrado", puntual("hex", [("agua", CAS["agua"]), ("n-hexano", "110-54-3")],
                                             "unifac-original-public")),
    ("acetona-agua-unifac", puntual("ace", [("acetona", CAS["acetona"]), ("agua", CAS["agua"])], "unifac-original-public")),
    ("sustitucion-vl-etanol-nrtl", sust(puntual("svl", [("etanol", CAS["etanol"]), ("agua", CAS["agua"])], "nrtl-chemsep"),
                                        VL)),
    ("rechazo-sustitucion-masa-molar", sust(puntual("smm", [("etanol", CAS["etanol"]), ("agua", CAS["agua"])],
                                                    "nrtl-chemsep"), {CAS["etanol"]: {"masa_molar": {"valor": 0.05}}})),
    ("rechazo-sustitucion-iapws", sust(puntual("siw", [("agua", CAS["agua"])], "agua-iapws95"),
                                       {CAS["agua"]: {"volumen_liquido": {"valor": 18.0, "unidad": "cm3/mol",
                                                                          "fuente": "ejemplo"}}})),
    ("metanol-puro-unifac-original", puntual("met", [("metanol", CAS["metanol"])], "unifac-original-public")),
]


def main():
    escribir("motor-catalogo.json", pedir("GET", "/motor/catalogo"))
    escribir("motor-termodinamica-capacidades.json", pedir("GET", "/motor/termodinamica/capacidades"))
    for nombre, cuerpo in CASOS:
        r = pedir("POST", "/motor/termodinamica/evaluar", cuerpo)
        escribir(f"motor-termodinamica-{nombre}-peticion.json", cuerpo)
        escribir(f"motor-termodinamica-{nombre}-respuesta.json", r)
        print(nombre, r["estado"], [d["codigo"] for d in r["diagnosticos"]])
    for nombre, cuerpo in redes():
        ruta = "/motor/ensamblajes/resolver" if nombre.startswith("resolver") else "/motor/ensamblajes/validar"
        r = pedir("POST", ruta, cuerpo)
        escribir(f"motor-ensamblaje-v2-{nombre}-peticion.json", cuerpo)
        escribir(f"motor-ensamblaje-v2-{nombre}-respuesta.json", r)
        diags = (r.get("validacion") or r).get("diagnosticos", [])
        print(nombre, r.get("estado"), (r.get("resultados") or {}).get("certificacion", {}).get("estado"),
              [d["codigo"] for d in diags][:3])
    for nombre, cuerpo in DIAGRAMAS:
        r = pedir("POST", "/motor/termodinamica/diagramas/trazar", cuerpo)
        escribir(f"motor-diagramas-{nombre}-peticion.json", cuerpo)
        escribir(f"motor-diagramas-{nombre}-respuesta.json", r)
        print(nombre, r["estado"], [q["tipo"] for q in r["puntosEspeciales"]])


if __name__ == "__main__":
    main()
