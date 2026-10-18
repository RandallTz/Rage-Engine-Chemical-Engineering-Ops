"""
Genera docs/ejemplos/motor-termodinamica-* ejecutando los endpoints reales
(/motor/termodinamica/capacidades y /evaluar) a traves de la app ASGI.
Ningun numero de esos archivos esta escrito a mano.

Despues, `node tests/verificar_contrato_motor_termodinamica.mjs` pasa cada
par peticion/respuesta por el validador TypeScript del contrato
(frontend/app/motor/contratoTermodinamica.ts).

Ejecutar desde la raiz del proyecto:
    python tests/generar_ejemplos_motor_termodinamica.py
"""

import asyncio
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import httpx

from backend.main import app
from core import agua_iapws95 as agua

DESTINO = RAIZ / "docs" / "ejemplos"


def pedir(metodo, ruta, cuerpo=None):
    async def hacer():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ejemplos") as c:
            return await c.request(metodo, ruta, json=cuerpo)
    r = asyncio.run(hacer())
    assert r.status_code == 200, (ruta, r.status_code, r.text)
    return r.json()


def peticion(caso, T, P, politica=None, especificacion=None):
    return {
        "revision": 1, "solicitudId": f"ejemplo-{caso}", "propietarioId": "volumen:deposito",
        "componentes": [{"id": 1, "nombre": "Agua", "simbolo": "A", "identidadQuimica": {"cas": agua.CAS}}],
        "declaracion": {
            "modelo": {"id": "agua-iapws95", "version": "1"},
            "especificacion": especificacion or {
                "tipo": "TP", "T": {"valor": T[0], "unidad": T[1]}, "P": {"valor": P[0], "unidad": P[1]},
                "composicion": {"base": "molar", "fracciones": {"1": 1}}},
            "politica": {"cantidad": "sin_restriccion", "cambioInterno": "permitido",
                         "evaluacion": "equilibrio_estable", **(politica or {})},
        },
    }


CASOS = {
    # evaluados
    "liquido-25C-1bar": peticion("liquido-25C-1bar", (25, "degC"), (1, "bar")),
    "vapor-100C-1atm": peticion("vapor-100C-1atm", (100, "degC"), (101.325, "kPa")),
    "liquido-comprimido-600K-50MPa": peticion("liquido-comprimido-600K-50MPa", (600, "K"), (500, "bar"),
                                              {"cantidad": "monofasico", "tiposPermitidos": ["liquido"]}),
    "supercritico-900K-50MPa": peticion("supercritico-900K-50MPa", (900, "K"), (500, "bar")),
    # rechazos
    "saturacion-indeterminada": peticion("saturacion-indeterminada", (450, "K"),
                                         (agua.saturacion(450.0).Psat, "Pa")),
    "fase-incompatible": peticion("fase-incompatible", (25, "degC"), (1, "bar"), {"tiposPermitidos": ["vapor"]}),
    "region-critica": peticion("region-critica", (647, "K"), (220, "bar")),
    # H3: especificaciones inversas, con numeros redondos de usuario
    "ph-bifasico-1bar": peticion("ph-bifasico-1bar", None, None, especificacion={
        "tipo": "PH", "P": {"valor": 1, "unidad": "bar"}, "h": {"valor": 1500, "unidad": "kJ/kg"},
        "composicion": {"base": "molar", "fracciones": {"1": 1}}}),
    "ph-vapor-sobrecalentado-10bar": peticion("ph-vapor-sobrecalentado-10bar", None, None, especificacion={
        "tipo": "PH", "P": {"valor": 10, "unidad": "bar"}, "h": {"valor": 3000, "unidad": "kJ/kg"},
        "composicion": {"base": "masica", "fracciones": {"1": 1}}}),
    "up-liquido-calentado-1bar": peticion("up-liquido-calentado-1bar", None, None, especificacion={
        "tipo": "UP", "U": {"valor": 1250, "unidad": "kJ"}, "P": {"valor": 1, "unidad": "bar"},
        "cantidades": {"base": "masica", "valores": {"1": {"valor": 5, "unidad": "kg"}}}}),
    "uv-recipiente-rigido-bifasico": peticion("uv-recipiente-rigido-bifasico", None, None, especificacion={
        "tipo": "UV", "U": {"valor": 15000, "unidad": "kJ"}, "V": {"valor": 1, "unidad": "m3"},
        "cantidades": {"base": "masica", "valores": {"1": {"valor": 10, "unidad": "kg"}}}}),
    "uv-recipiente-rigido-molar": peticion("uv-recipiente-rigido-molar", None, None, especificacion={
        "tipo": "UV", "U": {"valor": 15000, "unidad": "kJ"}, "V": {"valor": 1000, "unidad": "L"},
        "cantidades": {"base": "molar", "valores": {"1": {"valor": 10 / 0.018015268 / 1000, "unidad": "kmol"}}}}),
    "uv-supercritico": peticion("uv-supercritico", None, None, especificacion={
        "tipo": "UV", "U": {"valor": 2800, "unidad": "kJ"}, "V": {"valor": 10, "unidad": "L"},
        "cantidades": {"base": "masica", "valores": {"1": {"valor": 1, "unidad": "kg"}}}}),
    "uv-monofasico-incompatible": peticion("uv-monofasico-incompatible", None, None, {"cantidad": "monofasico"},
                                           especificacion={
        "tipo": "UV", "U": {"valor": 15000, "unidad": "kJ"}, "V": {"valor": 1, "unidad": "m3"},
        "cantidades": {"base": "masica", "valores": {"1": {"valor": 10, "unidad": "kg"}}}}),
    "uv-energia-bajo-el-punto-triple": peticion("uv-energia-bajo-el-punto-triple", None, None, especificacion={
        "tipo": "UV", "U": {"valor": -50, "unidad": "kJ"}, "V": {"valor": 1, "unidad": "L"},
        "cantidades": {"base": "masica", "valores": {"1": {"valor": 1, "unidad": "kg"}}}}),
}


def escribir(nombre, datos):
    ruta = DESTINO / nombre
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write("\n")
    print("  escrito", ruta.relative_to(RAIZ))


def main():
    escribir("motor-termodinamica-capacidades.json", pedir("GET", "/motor/termodinamica/capacidades"))
    for caso, s in CASOS.items():
        r = pedir("POST", "/motor/termodinamica/evaluar", s)
        print(f"  {caso}: {r['estado']}")
        escribir(f"motor-termodinamica-{caso}-peticion.json", s)
        escribir(f"motor-termodinamica-{caso}-respuesta.json", r)


if __name__ == "__main__":
    main()
