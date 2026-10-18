"""
Genera docs/ejemplos/motor-diagramas/ llamando a los endpoints reales por la app ASGI
(GET /motor/termodinamica/diagramas/capacidades, POST /motor/termodinamica/diagramas/trazar).
Ningun numero esta escrito a mano. Despues: node tests/verificar_contrato_diagramas.mjs

Ejecutar desde la raiz del proyecto:
    python tests/generar_ejemplos_motor_diagramas.py
"""

import asyncio
import json
import sys
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
warnings.filterwarnings("ignore")

import httpx

from backend.main import app

DESTINO = RAIZ / "docs" / "ejemplos" / "motor-diagramas"
CAS = {"agua": "7732-18-5", "etanol": "64-17-5", "benceno": "71-43-2", "tolueno": "108-88-3", "butanol": "71-36-3",
       "metanol": "67-56-1"}


def pedir(metodo, ruta, cuerpo=None):
    async def hacer():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ejemplos") as c:
            return await c.request(metodo, ruta, json=cuerpo, timeout=1200)
    r = asyncio.run(hacer())
    assert r.status_code == 200, (ruta, r.status_code, r.text[:300])
    return r.json()


def escribir(nombre, datos):
    DESTINO.mkdir(parents=True, exist_ok=True)
    with open(DESTINO / nombre, "w", encoding="utf-8", newline="\n") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1, allow_nan=False)
        f.write("\n")


def sol(sid, par, modelo, corte, eje=1, inter=(0.0, 1.0), perfil="exploratoria", **extra):
    s = {"revision": 1, "solicitudId": sid,
         "componentes": [{"id": k + 1, "nombre": n, "simbolo": n[:2], "identidadQuimica": {"cas": CAS[n]}}
                         for k, n in enumerate(par)],
         "modelo": {"id": modelo, "version": "1"}, "componenteEjeId": eje, "corte": corte,
         "intervaloComposicion": list(inter), "resolucion": perfil}
    s.update(extra)
    return s


P1 = {"tipo": "Txy", "P": {"valor": 101325, "unidad": "Pa"}}
CASOS = [
    ("txy-benceno-tolueno-ideal", sol("ej-bt", ("benceno", "tolueno"), "mezcla-ideal", P1)),
    ("pxy-benceno-tolueno-ideal", sol("ej-bt-p", ("benceno", "tolueno"), "mezcla-ideal",
                                      {"tipo": "Pxy", "T": {"valor": 370, "unidad": "K"}})),
    ("txy-etanol-agua-nrtl", sol("ej-ew", ("etanol", "agua"), "nrtl-chemsep",
                                 {"tipo": "Txy", "P": {"valor": 1.01325, "unidad": "bar"}})),
    ("pxy-etanol-agua-nrtl", sol("ej-ew-p", ("etanol", "agua"), "nrtl-chemsep",
                                 {"tipo": "Pxy", "T": {"valor": 76.85, "unidad": "degC"}})),
    ("txy-metanol-agua-nrtl", sol("ej-mw", ("metanol", "agua"), "nrtl-chemsep", P1)),
    ("txy-agua-butanol-competencia-ll", sol("ej-wb", ("agua", "butanol"), "nrtl-lle-agua-butanol", P1)),
    ("txy-etanol-agua-intervalo-parcial", sol("ej-ew-int", ("etanol", "agua"), "nrtl-chemsep", P1, eje=2,
                                              inter=(0.05, 0.6))),
    ("rechazo-par-sin-parametros", sol("ej-sin-par", ("agua", "benceno"), "nrtl-chemsep", P1)),
    ("rechazo-tres-componentes", {**sol("ej-tres", ("etanol", "agua"), "nrtl-chemsep", P1),
                                  "componentes": [{"id": 1, "nombre": "etanol", "simbolo": "E",
                                                   "identidadQuimica": {"cas": CAS["etanol"]}},
                                                  {"id": 2, "nombre": "agua", "simbolo": "W",
                                                   "identidadQuimica": {"cas": CAS["agua"]}},
                                                  {"id": 3, "nombre": "metanol", "simbolo": "M",
                                                   "identidadQuimica": {"cas": CAS["metanol"]}}]}),
    ("rechazo-presion-fuera-de-dominio", sol("ej-dom", ("etanol", "agua"), "nrtl-chemsep",
                                             {"tipo": "Txy", "P": {"valor": 10, "unidad": "bar"}})),
    ("rechazo-huella-distinta", sol("ej-huella", ("etanol", "agua"), "nrtl-chemsep", P1,
                                    huellaModeloEsperada="sha256:no-coincide")),
]


def main():
    escribir("motor-diagramas-capacidades.json", pedir("GET", "/motor/termodinamica/diagramas/capacidades"))
    for nombre, cuerpo in CASOS:
        r = pedir("POST", "/motor/termodinamica/diagramas/trazar", cuerpo)
        escribir(f"motor-diagramas-{nombre}-peticion.json", cuerpo)
        escribir(f"motor-diagramas-{nombre}-respuesta.json", r)
        print(nombre, r["estado"], len(r["puntos"]), [d["codigo"] for d in r["diagnosticos"]])


if __name__ == "__main__":
    main()
