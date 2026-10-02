"""
Validacion de la FRONTERA HTTP de las especificaciones y los barridos.

Por que existe esta suite aparte de validar_especificaciones.py. Esa
comprueba la fisica y el algoritmo; esta comprueba lo unico que la
frontera HTTP puede romper por su cuenta, que no es poco:

  - Que el numero que calcula el nucleo sea el MISMO que sale por el
    endpoint. Se compara contra `core` directamente, no contra una
    constante escrita a mano: una constante se queda obsoleta en silencio
    la primera vez que cambie algo de la termodinamica.
  - Que los errores salgan con el codigo correcto. Y aqui hay una
    decision deliberada que merece prueba: un punto de barrido que no
    converge NO es un 422, vuelve dentro de la respuesta. Si alguien
    "arregla" eso convirtiendolo en error, esta suite falla.
  - Que el conteo de grados de libertad por HTTP cuente las
    especificaciones como UNA ecuacion cada una. Es el error que ya se
    cometio una vez en el nucleo, asi que se vigila tambien aqui.
  - Que la respuesta sea serializable a JSON de verdad. Un `float32` de
    NumPy pasa los tipos de Pydantic y revienta al serializar; es un
    fallo que no se ve llamando a las funciones de Python.

Ejecutar desde la raiz del proyecto:
    python tests/validar_api_especificaciones.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import json

import asyncio

import httpx

from backend.main import app
from backend.schemas import MAX_PUNTOS_BARRIDO

fallos = []


def check(nombre, ok, detalle=""):
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}{(' -- ' + detalle) if detalle else ''}")
    if not ok:
        fallos.append(nombre)


class ClienteASGI:
    """
    Cliente HTTP sincrono contra la app, sin abrir ningun puerto.

    Por que a mano y no `fastapi.testclient.TestClient`: con las versiones
    FIJAS de este proyecto, TestClient no arranca -- el starlette instalado
    (0.27) le pasa `app=` a httpx, y httpx 0.28 quito ese argumento. Y el
    transporte ASGI de httpx solo tiene cara asincrona.

    Asi que se envuelve en `asyncio.run`, que es exactamente lo que hace
    TestClient por dentro. Se prueba la app REAL -- middleware, validacion
    de Pydantic y manejadores de error incluidos -- que es el unico modo de
    que esta suite signifique algo: llamar a las funciones de
    `nucleo_diagrama` directamente no probaria ni un codigo de estado.
    """

    def __init__(self, app, base_url="http://validacion"):
        self.app = app
        self.base_url = base_url

    def post(self, ruta, json=None):
        async def hacer():
            transporte = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transporte,
                                         base_url=self.base_url,
                                         timeout=600.0) as c:
                return await c.post(ruta, json=json)
        return asyncio.run(hacer())


cliente = ClienteASGI(app)

BT = ["benzene", "toluene"]
P1 = 101325.0

# Un diagrama minimo: una columna binaria. Se elige el caso mas simple a
# proposito -- lo que se prueba aqui es la frontera, no la fisica.
COLUMNA = {
    "componentes": BT,
    "corrientes": ["alim", "dest", "fondo"],
    "operaciones": [{
        "tipo": "columna",
        "nombre": "col1",
        "corrientes": {"alimentacion": "alim", "destilado": "dest", "fondos": "fondo"},
        "metodo": "mccabe_thiele",
    }],
}

DATOS_BASE = {
    "alim.F": 100.0, "alim.P": P1, "alim.x0": 0.5,
    "dest.x0": 0.95, "fondo.x0": 0.05,
    "col1.q": 1.0,
}


def cuerpo(**extra):
    cuerpo = {**COLUMNA, "valores": dict(DATOS_BASE)}
    for clave, valor in extra.items():
        if clave == "valores":
            cuerpo["valores"].update(valor)
        else:
            cuerpo[clave] = valor
    return cuerpo


print("\n=== 1. Una especificacion a traves de HTTP ===\n")

# Sin R, el problema esta abierto. Con una especificacion sobre N, cerrado.
# Es el mismo par de comprobaciones que en el nucleo, pero cruzando la
# frontera: si el campo 'especificaciones' no llegara a traducirse, el
# conteo saldria igual en los dos casos y esto lo cazaria.
gl_sin = cliente.post("/diagrama/grados-libertad", json=cuerpo())
check("1.1 /grados-libertad responde 200", gl_sin.status_code == 200,
      f"status {gl_sin.status_code}: {gl_sin.text[:200]}")

spec_N = {
    "objetivo": "col1.N", "valor": 12.0,
    "manipulada": "col1.R", "minimo": 1.6, "maximo": 10.0,
}
gl_con = cliente.post("/diagrama/grados-libertad",
                      json=cuerpo(especificaciones=[spec_N]))

if gl_sin.status_code == 200 and gl_con.status_code == 200:
    a, b = gl_sin.json(), gl_con.json()
    check("1.2 El conteo baja exactamente 1 al anadir una especificacion",
          b["grados_de_libertad"] == a["grados_de_libertad"] - 1,
          f"GL {a['grados_de_libertad']} -> {b['grados_de_libertad']}")
    check("1.3 Y lo hace sumando una ECUACION, no una incognita",
          b["ecuaciones"] == a["ecuaciones"] + 1 and b["incognitas"] == a["incognitas"],
          f"ecuaciones {a['ecuaciones']}->{b['ecuaciones']}, "
          f"incognitas {a['incognitas']}->{b['incognitas']}")
    check("1.4 Se reporta cuantas se contaron", b.get("especificaciones") == 1,
          f"especificaciones = {b.get('especificaciones')}")

r = cliente.post("/diagrama/resolver", json=cuerpo(especificaciones=[spec_N]))
check("1.5 /diagrama/resolver con especificacion responde 200", r.status_code == 200,
      f"status {r.status_code}: {r.text[:300]}")

R_http = None
if r.status_code == 200:
    cuerpo_r = r.json()
    info = cuerpo_r.get("especificaciones")
    check("1.6 La respuesta trae el informe de especificaciones", info is not None)
    if info:
        cumplida = info["cumplidas"][0]
        R_http = cumplida["valor"]
        check("1.7 El objetivo se cumple",
              abs(cumplida["error"]) < 1e-6,
              f"N pedido 12, obtenido {cumplida['obtenido']:.8f}, error {cumplida['error']:.2e}")
        check("1.8 Se reporta el coste real del lazo", info["evaluaciones"] > 1,
              f"{info['evaluaciones']} resoluciones completas del diagrama")
        check("1.9 El R encontrado esta dentro del rango pedido",
              spec_N["minimo"] <= R_http <= spec_N["maximo"], f"R = {R_http:.6f}")
        check("1.10 Y aparece tambien en el pool, no solo en el informe",
              abs(cuerpo_r["pool"].get("col1.R", float("nan")) - R_http) < 1e-12)

    # Un float32 de NumPy pasa Pydantic y revienta aqui. Esta linea es la
    # prueba: si la respuesta no es JSON de verdad, no sirve de nada.
    try:
        json.dumps(cuerpo_r)
        check("1.11 La respuesta completa serializa a JSON", True)
    except (TypeError, ValueError) as e:
        check("1.11 La respuesta completa serializa a JSON", False, str(e)[:120])


print("\n=== 2. El endpoint da el mismo numero que el nucleo ===\n")

# Esta es la comprobacion que de verdad importa de una frontera HTTP: que
# no cambie el resultado. Se calcula con el nucleo directamente y se
# compara, en vez de contra una constante escrita a mano que se quedaria
# obsoleta en silencio.
from backend.nucleo_diagrama import _construir
from backend.schemas import ResolverDiagramaRequest
from core.especificaciones import Especificacion

# Se construye el diagrama con la MISMA funcion que usa la API, y luego se
# llama al nucleo directamente. Asi lo unico que difiere entre los dos
# caminos es la frontera HTTP, que es justo lo que se quiere aislar.
d, _ = _construir(ResolverDiagramaRequest(**cuerpo()))
nucleo = d.resolver_con_especificaciones(
    [Especificacion(objetivo="col1.N", valor=12.0, manipulada="col1.R",
                    minimo=1.6, maximo=10.0)],
    **DATOS_BASE,
)
R_nucleo = nucleo["especificaciones"]["cumplidas"][0]["valor"]

if R_http is not None:
    check("2.1 HTTP y nucleo dan el mismo R", abs(R_http - R_nucleo) < 1e-9,
          f"HTTP {R_http:.9f} vs nucleo {R_nucleo:.9f}")
else:
    check("2.1 HTTP y nucleo dan el mismo R", False, "el endpoint no devolvio R")


print("\n=== 3. Lo que la frontera debe rechazar, y con que codigo ===\n")

casos_422 = [
    ("objetivo inexistente",
     [{**spec_N, "objetivo": "col1.NoExiste"}]),
    ("manipulada inexistente",
     [{**spec_N, "manipulada": "col1.NoExiste"}]),
    ("objetivo = manipulada",
     [{**spec_N, "objetivo": "col1.R"}]),
    ("rango al reves",
     [{**spec_N, "minimo": 10.0, "maximo": 1.6}]),
]
for nombre, specs in casos_422:
    resp = cliente.post("/diagrama/resolver", json=cuerpo(especificaciones=specs))
    check(f"3.x {nombre} -> 422", resp.status_code == 422,
          f"status {resp.status_code}")

# La manipulada dada tambien como dato: ambiguo, y se rechaza. No se
# elige una de las dos interpretaciones en silencio.
resp = cliente.post("/diagrama/resolver",
                    json=cuerpo(valores={"col1.R": 3.0}, especificaciones=[spec_N]))
check("3.5 manipulada dada TAMBIEN como dato -> 422", resp.status_code == 422,
      f"status {resp.status_code}")

# Un rango donde el objetivo no es alcanzable. El mensaje debe decir qué
# intervalo recorre de verdad, que es lo que permite decidir qué hacer.
spec_imposible = {**spec_N, "valor": 200.0}
resp = cliente.post("/diagrama/resolver", json=cuerpo(especificaciones=[spec_imposible]))
ok = resp.status_code == 422
detalle = resp.json().get("detail", "") if ok else resp.text[:150]
check("3.6 objetivo inalcanzable -> 422 con el rango recorrido",
      ok and "solo recorre" in detalle, detalle[:160])


print("\n=== 4. Barridos por HTTP ===\n")

barrido_ok = cliente.post("/diagrama/barrido", json=cuerpo(
    variable="col1.R",
    valores_barrido=[2.0, 3.0, 5.0, 8.0],
    seguir=["col1.N", "col1.Q_c"],
))
check("4.1 /diagrama/barrido responde 200", barrido_ok.status_code == 200,
      f"status {barrido_ok.status_code}: {barrido_ok.text[:300]}")

if barrido_ok.status_code == 200:
    b = barrido_ok.json()
    check("4.2 Vuelven tantos puntos como se pidieron", len(b["puntos"]) == 4,
          f"{len(b['puntos'])} puntos")
    check("4.3 Todos resueltos", b["fallidos"] == 0 and b["resueltos"] == 4,
          f"{b['resueltos']} resueltos, {b['fallidos']} fallidos")
    etapas = [p["pool"].get("col1.N") for p in b["puntos"]]
    check("4.4 Solo vuelve lo pedido en 'seguir'",
          all(set(p["pool"]) <= {"col1.N", "col1.Q_c"} for p in b["puntos"]),
          f"claves: {sorted(set().union(*(set(p['pool']) for p in b['puntos'])))}")
    check("4.5 N decrece al subir R", all(a > c for a, c in zip(etapas, etapas[1:])),
          " > ".join(f"{e:.2f}" for e in etapas))
    check("4.6 El valor barrido vuelve en su propio campo",
          [p["valor"] for p in b["puntos"]] == [2.0, 3.0, 5.0, 8.0])

# La decision deliberada: un punto que no converge NO es un 422. Dos
# valores por debajo del reflujo minimo (R_min = 1.5025 en este caso) y
# dos por encima: deben volver los cuatro, dos con motivo.
barrido_mixto = cliente.post("/diagrama/barrido", json=cuerpo(
    variable="col1.R",
    valores_barrido=[0.5, 1.0, 3.0, 6.0],
    seguir=["col1.N"],
))
check("4.7 Un punto inviable NO convierte el barrido en error",
      barrido_mixto.status_code == 200, f"status {barrido_mixto.status_code}")

if barrido_mixto.status_code == 200:
    b = barrido_mixto.json()
    check("4.8 Vuelven los cuatro puntos, no solo los buenos",
          len(b["puntos"]) == 4, f"{len(b['puntos'])} puntos")
    check("4.9 Los inviables vienen anotados con su motivo",
          b["fallidos"] == 2 and b["resueltos"] == 2,
          f"{b['resueltos']} resueltos, {b['fallidos']} fallidos")
    malos = [p for p in b["puntos"] if p["error"]]
    check("4.10 Y el motivo dice algo util, no solo 'fallo'",
          all(len(p["error"]) > 20 for p in malos),
          malos[0]["error"][:120] if malos else "")
    check("4.11 Los puntos fallidos no se marcan como completos",
          all(not p["completo"] for p in malos))

print("\n=== 5. Lo que SI invalida un barrido entero ===\n")

resp = cliente.post("/diagrama/barrido", json=cuerpo(
    variable="col1.NoExiste", valores_barrido=[1.0, 2.0]))
check("5.1 variable inexistente -> 422", resp.status_code == 422,
      f"status {resp.status_code}")

resp = cliente.post("/diagrama/barrido", json=cuerpo(
    valores={"col1.R": 3.0}, variable="col1.R", valores_barrido=[1.0, 2.0]))
check("5.2 barrer una variable que tambien se da como dato -> 422",
      resp.status_code == 422, f"status {resp.status_code}")

# El tope de puntos lo pone el esquema, asi que es un 422 de Pydantic.
# Existe porque cada punto es una resolucion completa del diagrama: sin
# tope, una peticion de mil puntos ocuparia el servidor durante horas.
resp = cliente.post("/diagrama/barrido", json=cuerpo(
    variable="col1.R", valores_barrido=[1.0 + 0.01 * i for i in range(MAX_PUNTOS_BARRIDO + 1)]))
check(f"5.3 mas de {MAX_PUNTOS_BARRIDO} puntos -> 422", resp.status_code == 422,
      f"status {resp.status_code}")

resp = cliente.post("/diagrama/barrido", json=cuerpo(
    variable="col1.R", valores_barrido=[3.0]))
check("5.4 un barrido de un solo punto no es un barrido -> 422",
      resp.status_code == 422, f"status {resp.status_code}")


print("\n=== 6. Sin especificaciones, nada cambia ===\n")

# Una regresion barata y que vale: el camino de siempre no debe haberse
# movido por haber anadido el campo nuevo.
sin = cliente.post("/diagrama/resolver", json=cuerpo(valores={"col1.R": 3.0}))
check("6.1 El camino de siempre sigue respondiendo 200", sin.status_code == 200,
      f"status {sin.status_code}: {sin.text[:200]}")
if sin.status_code == 200:
    c = sin.json()
    check("6.2 Y no inventa un informe de especificaciones",
          c.get("especificaciones") is None)
    check("6.3 El diagrama se resuelve completo", c["completo"] is True)

gl = cliente.post("/diagrama/grados-libertad", json=cuerpo(valores={"col1.R": 3.0}))
if gl.status_code == 200:
    check("6.4 El conteo sin especificaciones reporta cero",
          gl.json().get("especificaciones") == 0)


print()
if fallos:
    print(f"FALLARON {len(fallos)}: " + ", ".join(fallos))
    sys.exit(1)
print("TODO OK")
