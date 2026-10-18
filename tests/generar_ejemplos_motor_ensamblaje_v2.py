"""
Genera docs/ejemplos/motor-v2/ (motor-ensamblaje-v2-* y motor-termodinamica-{mezcla,nrtl,lle,hielo}-*)
llamando a los endpoints reales por la app ASGI. Ningun numero esta escrito a mano.

Despues, `node tests/verificar_contrato_ensamblaje_v2.mjs` compila cada par contra
docs/contratos/contratoEnsamblajeV2.ts y pasa cada estado termodinamico publicado por
validarRespuestaEstado del contrato puntual del frontend.

Ejecutar desde la raiz del proyecto:
    python tests/generar_ejemplos_motor_ensamblaje_v2.py
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

# Subdirectorio propio: los lectores de la revision 1 recorren docs/ejemplos/motor-ensamblaje-* y deben
# seguir viendo solo respuestas de la revision 1.
DESTINO = RAIZ / "docs" / "ejemplos" / "motor-v2"
CAPACIDADES_TERMO = RAIZ / "docs" / "ejemplos" / "motor-termodinamica-capacidades.json"


def pedir(metodo, ruta, cuerpo=None, params=None):
    async def hacer():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ejemplos") as c:
            return await c.request(metodo, ruta, json=cuerpo, params=params, timeout=1200)
    r = asyncio.run(hacer())
    assert r.status_code == 200, (ruta, r.status_code, r.text[:300])
    return r.json()


def escribir(nombre, datos):
    DESTINO.mkdir(exist_ok=True)
    with open(nombre if isinstance(nombre, Path) else DESTINO / nombre, "w", encoding="utf-8", newline="\n") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1, allow_nan=False)
        f.write("\n")


def casos_v2():
    yield "resolver-calentamiento-etanol-agua", "/motor/ensamblajes/resolver", (
        Red("v2-calentamiento", ("etanol", "agua"), tf=("450", "s"), muestras=7)
        .paquete("p", "nrtl-chemsep")
        .volumen("A", "p", {"etanol": ("0.4", "mol"), "agua": ("0.6", "mol")}, ("T", "330", "K"), P=("101325", "Pa"),
                 base="molar")
        .calor("q", None, "A", Q=("100", "W"), Tfrontera=("600", "K"))).solicitud()
    yield "resolver-contacto-dos-aguas", "/motor/ensamblajes/resolver", (
        Red("v2-contacto", ("agua",), tf=("2000", "s"), muestras=6)
        .paquete("w", "agua-iapws95")
        .volumen("A", "w", {"agua": ("10", "kg")}, ("T", "350", "K"), V=("0.0105", "m3"))
        .volumen("B", "w", {"agua": ("5", "kg")}, ("T", "300", "K"), V=("0.0052", "m3"))
        .calor("c", "A", "B", G=("200", "W/K"))).solicitud()
    yield "resolver-binario-acoplado", "/motor/ensamblajes/resolver", (
        Red("v2-acoplado", ("etanol", "agua"), tf=("200", "s"), muestras=5)
        .paquete("p", "nrtl-chemsep")
        .volumen("A", "p", {"etanol": ("0.3", "mol"), "agua": ("0.7", "mol")}, ("T", "340", "K"), P=("101325", "Pa"),
                 base="molar")
        .volumen("B", "p", {"etanol": ("0.1", "mol"), "agua": ("0.9", "mol")}, ("T", "300", "K"), P=("101325", "Pa"),
                 base="molar")
        .corriente("s", "A", "B", ("etanol", "agua"), ("0.001", "mol/s"), base="molar",
                   extraccion={"A": {"tipo": "mezcla_homogenea"}})
        .calor("c", "A", "B", G=("0.5", "W/K"))).solicitud()
    yield "resolver-decantador-agua-butanol", "/motor/ensamblajes/resolver", (
        Red("v2-decantador", ("agua", "butanol"), tf=("100", "s"), muestras=5)
        .paquete("p", "nrtl-lle-agua-butanol")
        .volumen("D", "p", {"agua": ("0.75", "mol"), "butanol": ("0.25", "mol")}, ("T", "300", "K"),
                 P=("101325", "Pa"), base="molar", adiabatico=True)
        .corriente("o", "D", None, ("agua", "butanol"), ("0.001", "mol/s"), base="molar",
                   extraccion={"D": {"tipo": "fase", "fase": "liquido", "criterio": "menor_densidad"}})).solicitud()
    yield "validar-decantador-sin-criterio", "/motor/ensamblajes/validar", (
        Red("v2-decantador-ambiguo", ("agua", "butanol"), tf=("100", "s"), muestras=5)
        .paquete("p", "nrtl-lle-agua-butanol")
        .volumen("D", "p", {"agua": ("0.75", "mol"), "butanol": ("0.25", "mol")}, ("T", "300", "K"),
                 P=("101325", "Pa"), base="molar", adiabatico=True)
        .corriente("o", "D", None, ("agua", "butanol"), ("0.001", "mol/s"), base="molar")).solicitud()
    yield "validar-calor-pendiente", "/motor/ensamblajes/validar", (
        Red("v2-calor-pendiente", ("agua",), tf=("10", "s"), muestras=3)
        .paquete("w", "agua-iapws95")
        .volumen("A", "w", {"agua": ("1", "kg")}, ("T", "300", "K"), V=("0.0011", "m3"))).solicitud()


def estatica(sid, modelo, componentes, espec):
    return {"revision": 1, "solicitudId": sid, "propietarioId": "ejemplos",
            "componentes": [{"id": i + 1, "nombre": n, "simbolo": n[:2], "identidadQuimica": {"cas": CAS[n]}}
                            for i, n in enumerate(componentes)],
            "declaracion": {"modelo": {"id": modelo, "version": "1"}, "politica": dict(POL), "especificacion": espec}}


def q(v, u):
    return {"valor": v, "unidad": u}


def casos_estaticos():
    yield "mezcla-ideal-tp-bifasico", estatica("ej-ideal", "mezcla-ideal", ("benceno", "tolueno"), {
        "tipo": "TP", "T": q(372, "K"), "P": q(101325, "Pa"),
        "composicion": {"base": "molar", "fracciones": {"1": 0.4, "2": 0.6}}})
    yield "nrtl-etanol-agua-ph", estatica("ej-nrtl", "nrtl-chemsep", ("etanol", "agua"), {
        "tipo": "PH", "P": q(101325, "Pa"), "h": q(-1.0e6, "J/kg"),
        "composicion": {"base": "molar", "fracciones": {"1": 0.4, "2": 0.6}}})
    yield "lle-agua-butanol-tp", estatica("ej-lle", "nrtl-lle-agua-butanol", ("agua", "butanol"), {
        "tipo": "TP", "T": q(25, "degC"), "P": q(1, "bar"),
        "composicion": {"base": "molar", "fracciones": {"1": 0.75, "2": 0.25}}})
    yield "hielo-tp", estatica("ej-hielo-tp", "agua-iapws95-hielo-ih", ("agua",), {
        "tipo": "TP", "T": q(-10, "degC"), "P": q(1, "bar"), "composicion": {"base": "molar", "fracciones": {"1": 1}}})
    yield "hielo-ph-fusion", estatica("ej-hielo-ph", "agua-iapws95-hielo-ih", ("agua",), {
        "tipo": "PH", "P": q(101325, "Pa"), "h": q(-200, "kJ/kg"),
        "composicion": {"base": "molar", "fracciones": {"1": 1}}})
    yield "hielo-uv-triple", estatica("ej-hielo-uv", "agua-iapws95-hielo-ih", ("agua",), {
        "tipo": "UV", "U": q(-100, "kJ"), "V": q(1, "m3"),
        "cantidades": {"base": "masica", "valores": {"1": q(1, "kg")}}})
    yield "hielo-tp-triple-indeterminado", estatica("ej-hielo-triple", "agua-iapws95-hielo-ih", ("agua",), {
        "tipo": "TP", "T": q(273.16, "K"), "P": q(611.6547710077494, "Pa"),
        "composicion": {"base": "molar", "fracciones": {"1": 1}}})


def main():
    escribir("motor-ensamblaje-v2-capacidades.json", pedir("GET", "/motor/ensamblajes/capacidades", params={"revision": 2}))
    # el catalogo puntual es el mismo endpoint de la revision 1 (ahora con los modelos aditivos)
    escribir(CAPACIDADES_TERMO, pedir("GET", "/motor/termodinamica/capacidades"))
    escribir("motor-termodinamica-diagrama-hielo.json", pedir("GET", "/motor/termodinamica/diagrama"))
    for nombre, ruta, cuerpo in casos_v2():
        r = pedir("POST", ruta, cuerpo)
        escribir(f"motor-ensamblaje-v2-{nombre}-peticion.json", cuerpo)
        escribir(f"motor-ensamblaje-v2-{nombre}-respuesta.json", r)
        print(nombre, r.get("estado", r.get("recuento", {}).get("estado")))
    for nombre, cuerpo in casos_estaticos():
        r = pedir("POST", "/motor/termodinamica/evaluar", cuerpo)
        escribir(f"motor-termodinamica-{nombre}-peticion.json", cuerpo)
        escribir(f"motor-termodinamica-{nombre}-respuesta.json", r)
        print(nombre, r["estado"])


if __name__ == "__main__":
    main()
