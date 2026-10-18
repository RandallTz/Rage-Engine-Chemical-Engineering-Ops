"""Pruebas del contrato HTTP sin abrir sockets ni sustituir el núcleo."""
import json
import asyncio
import httpx
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from fastapi import FastAPI
from backend.api_adimensionalizacion import router

app = FastAPI()
app.include_router(router)
async def main():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:

        cap = await client.get("/api/adimensionalizacion/capacidades")
        assert cap.status_code == 200 and "adimensionalizar" in cap.json()["operaciones"]
        assert (await client.post("/api/adimensionalizacion", content=b"{")).status_code == 400
        assert (await client.post("/api/adimensionalizacion", content=b'{"x":NaN}')).status_code == 400
        assert (await client.post("/api/adimensionalizacion", content=b" " * 1_000_001)).status_code == 413
        assert (await client.post("/api/adimensionalizacion", json={})).status_code == 200
        assert (await client.post("/api/adimensionalizacion", json={})).json()["estado"] == "rechazado"
        for nombre in ["automatico", "requiere-datos", "mapa-logaritmico", "mapa-afin-temperatura"]:
            solicitud = json.loads((RAIZ / "docs" / "ejemplos" / f"adimensionalizacion-{nombre}-solicitud.json").read_text(encoding="utf-8"))
            respuesta = await client.post("/api/adimensionalizacion", json=solicitud)
            assert respuesta.status_code == 200
            r = respuesta.json()
            assert r["estado"] == ("requiere_datos" if nombre == "requiere-datos" else "correcto"), r
            if nombre == "automatico":
                assert len(r["formulaciones"]) == 8 and r["cobertura"]["completa"]
                assert all(f["equivalencia"]["estado"] == "demostrada" and f["desarrollo"] for f in r["formulaciones"])
                solicitud["opciones"] = {"presupuesto": 2}
                pagina = (await client.post("/api/adimensionalizacion", json=solicitud)).json()
                assert pagina["estado"] == "correcto" and not pagina["cobertura"]["completa"]
                siguiente = pagina["cobertura"]["siguiente"]
                assert isinstance(siguiente, int) and siguiente > 0
                solicitud["opciones"]["desde"] = siguiente
                continuacion = (await client.post("/api/adimensionalizacion", json=solicitud)).json()
                assert continuacion["estado"] == "correcto" and continuacion["formulaciones"]
                assert continuacion["cobertura"]["desde"] == siguiente
            if nombre == "requiere-datos":
                assert set(r["dimensional"]["faltantes"]) == {"c", "t", "x"}
        print("API adimensionalización: capacidades, JSON, tamaño, rechazos, 8 formulaciones, continuación, datos mínimos y mapas generales correctos.")

asyncio.run(main())
