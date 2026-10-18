"""Aceptación del lector dimensional HTTP: términos, unidades y sistemas."""
import asyncio
import json
import sys
from pathlib import Path

import httpx
from fastapi import FastAPI

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from backend.api_adimensionalizacion import router
from backend.dimensiones_adimensionalizacion import auditar_dimensiones
from casos_adimensionalizacion import s, prod, suma, d, lap, igualdad, simbolo, coc, fun


def modelo():
    return {
        "id": "sistema-dos-campos", "revision": 1,
        "simbolos": [simbolo("u", "campo", None, ["t", "x"], unidad="mol/L"),
                     simbolo("v", "campo", None, ["t", "x"], unidad="mol/L"),
                     simbolo("t", "tiempo", None, unidad="s"), simbolo("x", "coordenada", None, unidad="m"),
                     simbolo("D1", "parametro", None), simbolo("D2", "parametro", None), simbolo("k", "parametro", None)],
        "funciones": [], "dominios": [], "condiciones": [],
        "ecuaciones": [igualdad("campo-u", d(s("u"), "t"), suma(prod(s("D1"), lap(s("u"), "x")), prod(s("k"), s("v")))),
                       igualdad("campo-v", d(s("v"), "t"), suma(prod(s("D2"), lap(s("v"), "x")), prod(s("k"), s("u"))))],
    }


def solicitud(m=None, operacion="analizar"):
    return {"formato": "adimensionalizacion.solicitud", "version": 1, "operacion": operacion,
            "documento": {"formato": "adimensionalizacion", "version": 1, "id": "doc-capa", "nombre": "Sistema",
                          "modelo": m or modelo(), "formas": [{"id": "f", "nombre": "Forma", "padreId": None,
                          "modeloRevision": 1, "escalas": [], "objetivos": [], "presentacion": "factorizada"}], "activaId": "f"}}


async def main():
    app = FastAPI(); app.include_router(router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as c:
        a = solicitud()
        resp = await c.post("/api/adimensionalizacion/dimensiones", json=a)
        assert resp.status_code == 200
        r = resp.json()
        assert r["analisis"]["dimensional"]["estado"] == "compatible"
        assert len(r["ecuaciones"]) == 2
        assert all(t["estado"] == "compatible" for eq in r["ecuaciones"] for t in eq["terminos"])
        assert all(eq["dimension"] == {"L": {"n": -3, "d": 1}, "N": {"n": 1, "d": 1}, "T": {"n": -1, "d": 1}} for eq in r["ecuaciones"])
        assert "concentracion" in next(q for q in r["cantidades"] if q["id"] == "u")["magnitudes"]
        assert "difusividad" in next(q for q in r["cantidades"] if q["id"] == "D1")["magnitudes"]
        assert {o["tipo"] for eq in r["ecuaciones"] for t in eq["terminos"] for o in t["operadores"]} == {"derivada", "laplaciano"}

        # Las ecuaciones pueden tener dimensiones diferentes: la exigencia es por igualdad.
        heterogeneo = modelo()
        heterogeneo["simbolos"] = [simbolo("A", "parametro", None, unidad="Kg"), simbolo("B", "parametro", None, unidad="g"),
                                    simbolo("V", "parametro", None, unidad="L"), simbolo("W", "parametro", None, unidad="m^3")]
        heterogeneo["ecuaciones"] = [igualdad("masa", s("A"), s("B")), igualdad("volumen", s("V"), s("W"))]
        rr = auditar_dimensiones(solicitud(heterogeneo))
        assert rr["analisis"]["dimensional"]["estado"] == "compatible"
        assert rr["ecuaciones"][0]["dimension"] != rr["ecuaciones"][1]["dimension"]
        assert rr["cantidades"][0]["unidadNormalizada"] == "kg" and "masa" in rr["cantidades"][0]["magnitudes"]
        assert "volumen" in rr["cantidades"][2]["magnitudes"]

        varios = modelo()
        varios["simbolos"] = [simbolo("masa", "parametro", None, unidad="kg"), simbolo("tiempo", "tiempo", None, unidad="s"),
                              simbolo("rho", "parametro", None, unidad="kg/m^3"), simbolo("vol", "parametro", None, unidad="litros"),
                              simbolo("coef", "parametro", None)]
        varios["ecuaciones"] = [igualdad("termino-compuesto", coc(s("masa"), s("tiempo")), prod(s("rho"), s("vol"), s("coef")))]
        rv = auditar_dimensiones(solicitud(varios))
        assert all(t["estado"] == "compatible" for t in rv["ecuaciones"][0]["terminos"])
        assert next(s for s in rv["analisis"]["dimensional"]["simbolos"] if s["id"] == "coef")["dimension"] == {"T": {"n": -1, "d": 1}}

        exponencial = modelo()
        exponencial["simbolos"] = [simbolo("u", "campo", None, ["t"], unidad="mol/L"), simbolo("t", "tiempo", None, unidad="s"),
                                   simbolo("a", "parametro", None, unidad="mol/L"), simbolo("k", "parametro", None, unidad="mol/(L*s)")]
        exponencial["ecuaciones"] = [igualdad("exponencial", d(s("u"), "t"), prod(s("k"), fun("exp", coc(s("u"), s("a")))))]
        re = auditar_dimensiones(solicitud(exponencial))
        assert re["analisis"]["dimensional"]["estado"] == "compatible"
        assert any(o.get("nombre") == "exp" for t in re["ecuaciones"][0]["terminos"] for o in t["operadores"])
        exponencial["simbolos"][2]["unidad"] = "s"
        assert auditar_dimensiones(solicitud(exponencial))["analisis"]["dimensional"]["estado"] == "incompatible"

        algebraico = modelo()
        algebraico["simbolos"] = [simbolo("V", "campo", None, unidad="L"), simbolo("masa", "parametro", None, unidad="kg"), simbolo("rho", "parametro", None)]
        algebraico["ecuaciones"] = [igualdad("algebraica", s("V"), coc(s("masa"), s("rho")))]
        ra = auditar_dimensiones(solicitud(algebraico))
        assert ra["analisis"]["dimensional"]["estado"] == "compatible"
        assert "densidad" in next(c for c in ra["cantidades"] if c["id"] == "rho")["magnitudes"]
        ca = (await c.post("/api/adimensionalizacion", json=solicitud(algebraico, "adimensionalizar"))).json()
        assert ca["estado"] == "correcto" and all(f["equivalencia"]["estado"] == "demostrada" for f in ca["formulaciones"])

        # Un coeficiente con unidad errónea marca el término exacto y bloquea resultados.
        malo = modelo(); next(s for s in malo["simbolos"] if s["id"] == "D2")["unidad"] = "kg"
        mal = auditar_dimensiones(solicitud(malo))
        assert mal["analisis"]["dimensional"]["estado"] == "incompatible"
        assert any(t["estado"] == "incompatible" for t in mal["ecuaciones"][1]["terminos"])
        calculo = (await c.post("/api/adimensionalizacion", json=solicitud(malo, "adimensionalizar"))).json()
        assert calculo["estado"] == "rechazado" and "formulaciones" not in calculo

        desconocida = modelo(); next(s for s in desconocida["simbolos"] if s["id"] == "D2")["unidad"] = "unidad_inventada"
        rechazo = (await c.post("/api/adimensionalizacion", json=solicitud(desconocida, "adimensionalizar"))).json()
        assert rechazo["estado"] == "rechazado" and "formulaciones" not in rechazo
        assert any(d["codigo"] == "unidad_no_reconocida" and d["severidad"] == "error" for d in rechazo["diagnosticos"])

        indeterminado = modelo()
        for sim in indeterminado["simbolos"]: sim["unidad"] = None
        ri = auditar_dimensiones(solicitud(indeterminado))
        assert ri["analisis"]["dimensional"]["estado"] == "indeterminado"
        assert all(t["estado"] == "pendiente" for e in ri["ecuaciones"] for t in e["terminos"])

        # La relación entre difusividades debe salir del sistema, no añadirse en cliente.
        calculo = (await c.post("/api/adimensionalizacion", json=solicitud(operacion="adimensionalizar"))).json()
        assert calculo["estado"] == "correcto" and all(len(f["ecuaciones"]) == 2 and f["equivalencia"]["estado"] == "demostrada" for f in calculo["formulaciones"])
        def ids(e):
            if e.get("tipo") == "simbolo": return {e["id"]}
            return set().union(*(ids(x) for x in e.values() if isinstance(x, dict)), *(ids(a) for a in e.get("argumentos", [])))
        assert any(ids(g["definicion"]) == {"D1", "D2"} for base in calculo["gruposPi"]["bases"] for g in base["grupos"])
        assert any(ids(g["definicion"]) == {"D1", "D2"} for f in calculo["formulaciones"] for g in f["grupos"])
        assert (await c.post("/api/adimensionalizacion/dimensiones", json={})).status_code == 400

        # Par verificable para el lector del cliente, incluido el resultado del sistema.
        destino = RAIZ / ".tmp" / "capa-dimensional"
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "auditoria.json").write_text(json.dumps({"solicitud": a, "respuesta": r}, ensure_ascii=False), encoding="utf-8")
        (RAIZ / "docs" / "ejemplos" / "adimensionalizacion-auditoria-dimensional.json").write_text(
            json.dumps({"solicitud": a, "respuesta": r}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (destino / "sistema.json").write_text(json.dumps({"solicitud": solicitud(operacion="adimensionalizar"), "respuesta": calculo}, ensure_ascii=False), encoding="utf-8")
        print(f"Capa dimensional correcta: unidades, alias, términos, operadores, rechazo, sistemas y razón D1/D2 en {len(calculo['formulaciones'])} formulaciones.")


if __name__ == "__main__": asyncio.run(main())
