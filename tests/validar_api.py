"""
Validacion de la FRONTERA HTTP del resto de la API.

Por que existe. Hasta ahora solo `/diagrama/*` tenia prueba de frontera
(tests/validar_api_especificaciones.py). Los otros dieciseis endpoints
estaban cubiertos indirectamente —las suites de navegador los usan al
pasar— pero eso significa que un fallo en la frontera se manifestaba como
"la grafica no aparece", a ocho capas de distancia de la causa.

Lo que se comprueba aqui es solo lo que la frontera puede romper por su
cuenta, y en esa lista hay una idea que vale mas que las demas:

  **Encadenar en vez de inventar cargas.** Los presets de `/ejemplos` ya
  SON peticiones validas de `/columna/resolver`, y los de
  `/flowsheet/ejemplos` lo son de `/flowsheet/resolver`. Asi que la suite
  los pide y los reenvia. Eso prueba dos endpoints de una, y ademas prueba
  algo que una carga escrita a mano no puede probar: que el preset que la
  interfaz le ofrece al usuario de verdad se pueda resolver. Un preset
  roto es un fallo que el usuario encuentra en el primer clic.

Y una que parece tonta y no lo es: que cada respuesta serialice a JSON. Un
`float32` o un `nan` de NumPy pasan los tipos de Pydantic y revientan (o
producen JSON invalido) al serializar, y eso no se ve llamando a las
funciones de Python.

Ejecutar desde la raiz del proyecto:
    python tests/validar_api.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import asyncio
import json
import math

import httpx

from backend.main import app

fallos = []


def check(nombre, ok, detalle=""):
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}{(' -- ' + detalle) if detalle else ''}")
    if not ok:
        fallos.append(nombre)


class ClienteASGI:
    """
    Cliente sincrono contra la app, sin abrir puerto. Ver el comentario
    extenso en tests/validar_api_especificaciones.py: `TestClient` no
    arranca con las versiones fijas de este proyecto.
    """

    def __init__(self, app, base_url="http://validacion"):
        self.app, self.base_url = app, base_url

    def _pedir(self, metodo, ruta, **kw):
        async def hacer():
            transporte = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transporte, base_url=self.base_url,
                                         timeout=600.0) as c:
                return await c.request(metodo, ruta, **kw)
        return asyncio.run(hacer())

    def get(self, ruta, **kw):
        return self._pedir("GET", ruta, **kw)

    def post(self, ruta, json=None):
        return self._pedir("POST", ruta, json=json)


cliente = ClienteASGI(app)


def json_valido(cuerpo):
    """
    JSON de verdad, no "Python lo serializo".

    `allow_nan=False` es el punto: `json.dumps` acepta NaN e Infinity por
    omision y escribe `NaN`, que **no es JSON valido** y que
    `JSON.parse` del navegador rechaza. Un hueco numerico mal gestionado
    llega hasta aqui con esa cara.
    """
    try:
        json.dumps(cuerpo, allow_nan=False)
        return True, ""
    except (TypeError, ValueError) as e:
        return False, str(e)[:140]


# ======================================================================
print("\n=== 1. Lo que no necesita cuerpo ===\n")
# ======================================================================

r = cliente.get("/salud")
check("1.1 /salud responde 200", r.status_code == 200, r.text[:80])

r = cliente.get("/modelos-termodinamicos")
check("1.2 /modelos-termodinamicos devuelve al menos uno",
      r.status_code == 200 and len(r.json()) >= 1,
      f"{len(r.json()) if r.status_code == 200 else '?'} modelo(s)")

r = cliente.get("/unidades")
if r.status_code == 200:
    tabla = r.json()
    check("1.3 /unidades trae magnitudes y el mapa de variables",
          bool(tabla.get("magnitudes")) and bool(tabla.get("variables")),
          f"{len(tabla['magnitudes'])} magnitudes, {len(tabla['variables'])} variables")
    # La tabla la genera pint. Una conversion afin cuyo desplazamiento se
    # perdiera daria temperaturas 273 K equivocadas en toda la interfaz,
    # asi que se comprueba el caso con desplazamiento.
    temps = tabla["magnitudes"].get("temperatura", {}).get("unidades", [])
    celsius = next((u for u in temps if "C" in u["simbolo"]), None)
    check("1.4 La conversión de °C lleva su desplazamiento, no solo el factor",
          celsius is not None and abs(celsius["desplazamiento"] - 273.15) < 1e-9,
          f"{celsius['simbolo']}: factor {celsius['factor']}, desplazamiento {celsius['desplazamiento']}"
          if celsius else "no hay unidad de °C")
    # TODAS las unidades que esta tabla ofrece tienen que ser afines, porque
    # el cliente las aplica en local sin saber nada de composiciones. Si
    # alguna dejara de serlo, convertiria mal en silencio.
    #
    # La primera version de esta comprobacion exigia justo lo CONTRARIO --
    # que hubiera unidades marcadas como no afines -- porque se fio de la
    # descripcion del campo, que se habia quedado obsoleta. El caudal masico
    # dejo de ser una unidad de F y paso a ser una ecuacion del diagrama.
    no_afines = [u["simbolo"] for m in tabla["magnitudes"].values()
                 for u in m["unidades"] if u.get("requiere_masa_molar")]
    check("1.5 Todas las unidades ofrecidas son afines", not no_afines,
          ", ".join(no_afines) or "ninguna necesita masa molar")
    # Y el caudal sigue admitiendo las dos bases: es lo que el cliente mira
    # para saber que F se puede dar en masa.
    magnitudes_de_F = tabla["variables"].get("F", [])
    check("1.5b Y F admite base molar Y másica",
          set(magnitudes_de_F) == {"flujo_molar", "flujo_masico"},
          ", ".join(magnitudes_de_F))
else:
    check("1.3 /unidades responde 200", False, f"status {r.status_code}")

# El parametro se llama "q", no "nombre": resuelve nombre, formula o CAS.
r = cliente.get("/componentes/buscar", params={"q": "benzene"})
if r.status_code == 200:
    c = r.json()
    check("1.6 /componentes/buscar encuentra el benceno",
          abs(c["MW"] - 78.11) < 0.05, f"MW = {c['MW']}")
else:
    check("1.6 /componentes/buscar encuentra el benceno", False, f"status {r.status_code}")

# Un componente inventado devuelve 200 con `encontrado: false`, no un 404,
# y eso es deliberado: esto es una BUSQUEDA, y "no existe" es una respuesta
# valida que el buscador de la interfaz tiene que poder mostrar mientras se
# teclea. Un 404 obligaria a tratar cada pulsacion como un error.
r = cliente.get("/componentes/buscar", params={"q": "noexisteestecomponente"})
if r.status_code == 200:
    c = r.json()
    check("1.7 Un componente inexistente se responde, no se trata como error",
          c["encontrado"] is False and c["MW"] is None)
    check("1.8 Y el mensaje dice qué probar en su lugar",
          "inglés" in c["mensaje"] or "CAS" in c["mensaje"], c["mensaje"][:110])
else:
    check("1.7 Un componente inexistente se responde, no se trata como error",
          False, f"status {r.status_code}")

# La distincion que de verdad importa de este endpoint, y la que evita el
# error opaco que ya aparecio una vez con el metano: "existe" y "se puede
# usar" NO son lo mismo. El metano existe en 'thermo' y tiene MW, pero no
# tiene grupos UNIFAC, asi que no sirve con el unico modelo implementado.
# Si estas dos banderas se confundieran en una, el usuario elegiria metano
# y el fallo saldria mucho despues, al resolver.
r = cliente.get("/componentes/buscar", params={"q": "methane"})
if r.status_code == 200:
    c = r.json()
    check("1.9 El metano se ENCUENTRA (existe y tiene MW)",
          c["encontrado"] is True and c["MW"] is not None, f"MW = {c['MW']}")
    check("1.10 Pero se marca como NO apto: sin grupos UNIFAC no hay γ",
          c["apto_unifac"] is False)
    check("1.11 Y el mensaje explica por qué, nombrando el modelo",
          "UNIFAC" in c["mensaje"], c["mensaje"][:110])
else:
    check("1.9 El metano se ENCUENTRA (existe y tiene MW)", False,
          f"status {r.status_code}")


# ======================================================================
print("\n=== 2. Los presets se pueden resolver (encadenados) ===\n")
# ======================================================================

r = cliente.get("/ejemplos")
presets = r.json() if r.status_code == 200 else []
check("2.1 /ejemplos devuelve la lista", r.status_code == 200 and len(presets) >= 1,
      f"{len(presets)} preset(s)")

for preset in presets:
    # Primero por su id, que es como lo pide la interfaz.
    uno = cliente.get(f"/ejemplos/{preset['id']}")
    if uno.status_code != 200:
        check(f"2.x preset '{preset['id']}' se puede pedir por id", False,
              f"status {uno.status_code}")
        continue
    p = uno.json()
    peticion = {
        "metodo": p["metodo"], "nombres": p["nombres"], "feed": p["feed"],
        "parametros": p["parametros"],
        "indice_LK": p.get("indice_LK"), "indice_HK": p.get("indice_HK"),
    }
    resp = cliente.post("/columna/resolver", json=peticion)
    ok = resp.status_code == 200
    detalle = f"status {resp.status_code}"
    if ok:
        cuerpo = resp.json()
        bien, motivo = json_valido(cuerpo)
        ok = bien
        detalle = f"N = {cuerpo.get('N')}" if bien else f"JSON inválido: {motivo}"
    else:
        detalle += f": {resp.text[:140]}"
    check(f"2.x el preset '{preset['id']}' se resuelve y serializa", ok, detalle)

r = cliente.get("/ejemplos/noexiste")
check("2.5 Un preset inexistente da 404", r.status_code == 404, f"status {r.status_code}")


# ======================================================================
print("\n=== 3. El motor antiguo sigue funcionando, y está marcado ===\n")
# ======================================================================

# No se borra: core/diagrama_flujo.py sigue siendo una comprobacion cruzada
# contra los mismos numeros por otro camino. Pero no puede estar tan
# visible como el de ahora sin decir cual es cual.
spec = cliente.get("/openapi.json").json()
obsoletos = {
    ruta for ruta, ops in spec["paths"].items()
    for op in ops.values() if op.get("deprecated")
}
check("3.1 Los tres endpoints del modelo antiguo están marcados como obsoletos",
      obsoletos == {"/flowsheet/ejemplos", "/flowsheet/ejemplos/{ejemplo_id}",
                    "/flowsheet/resolver"},
      ", ".join(sorted(obsoletos)) or "ninguno")
check("3.2 Y /diagrama/* NO lo está",
      not any(r.startswith("/diagrama") for r in obsoletos))

r = cliente.get("/flowsheet/ejemplos")
ejemplos_fs = r.json() if r.status_code == 200 else []
check("3.3 Marcado como obsoleto NO es lo mismo que roto",
      r.status_code == 200 and len(ejemplos_fs) >= 1, f"{len(ejemplos_fs)} ejemplo(s)")

for ej in ejemplos_fs:
    resp = cliente.post("/flowsheet/resolver", json=ej["definicion"])
    ok = resp.status_code == 200
    detalle = f"status {resp.status_code}"
    if ok:
        bien, motivo = json_valido(resp.json())
        ok = bien
        detalle = "resuelto" if bien else f"JSON inválido: {motivo}"
    else:
        detalle += f": {resp.text[:140]}"
    check(f"3.x el ejemplo antiguo '{ej['id']}' se resuelve", ok, detalle)


# ======================================================================
print("\n=== 4. Termodinámica: los endpoints caros ===\n")
# ======================================================================

r = cliente.post("/elv/binario", json={"nombres": ["benzene", "toluene"],
                                       "P": 101325.0, "n_puntos": 20})
if r.status_code == 200:
    elv = r.json()
    bien, motivo = json_valido(elv)
    check("4.1 /elv/binario serializa", bien, motivo)
    xs = elv.get("x") or []
    Ts = elv.get("T") or []
    # 22 y no 20: `n_puntos` son los puntos INTERIORES, y el endpoint anade
    # los dos componentes puros (x=0 y x=1) con su temperatura de ebullicion.
    # Es deliberado, y es lo que hace que la curva llegue a los bordes.
    check("4.2 Devuelve los puntos interiores pedidos más los dos puros",
          len(xs) == 22 and xs[0] == 0.0 and xs[-1] == 1.0,
          f"{len(xs)} puntos, de x={xs[0]} a x={xs[-1]}" if xs else "sin puntos")
    check("4.3 Los extremos son las temperaturas de ebullición de los puros",
          len(Ts) == 22 and abs(Ts[0] - 383.75) < 1.0 and abs(Ts[-1] - 353.22) < 1.0,
          f"tolueno puro {Ts[0]:.2f} K, benceno puro {Ts[-1]:.2f} K" if Ts else "")
    # El valor que ancla este endpoint: benceno/tolueno 50/50 hierve a
    # 365.5157 K, el numero que el proyecto compara bit a bit en otras
    # suites. x = 0.5 NO cae en la malla salvo que n_puntos sea impar, asi
    # que se interpola entre los dos puntos que lo rodean -- y por eso la
    # tolerancia es 0.1 K y no 1e-9: lo que se comprueba es que el endpoint
    # devuelva LA MISMA curva, no que acierte un punto que no calculo.
    if len(xs) == len(Ts) and len(xs) > 2:
        i = next(k for k in range(1, len(xs)) if xs[k] >= 0.5)
        peso = (0.5 - xs[i - 1]) / (xs[i] - xs[i - 1])
        T_medio = Ts[i - 1] + peso * (Ts[i] - Ts[i - 1])
        check("4.4 Y la curva pasa por el punto de burbuja del 50/50",
              abs(T_medio - 365.5157) < 0.1,
              f"interpolado {T_medio:.4f} K (esperado 365.5157)")
    check("4.5 La curva de burbuja decrece al enriquecer en el ligero",
          all(a >= b - 1e-9 for a, b in zip(Ts, Ts[1:])),
          f"de {Ts[0]:.2f} a {Ts[-1]:.2f} K" if Ts else "")
else:
    check("4.1 /elv/binario responde 200", False, f"status {r.status_code}: {r.text[:140]}")

# Un binario necesita DOS componentes. Pedirlo con tres es el error de uso
# mas probable, y debe decirlo en vez de reventar.
r = cliente.post("/elv/binario", json={"nombres": ["benzene", "toluene", "n-hexane"]})
check("4.6 Un 'binario' con tres componentes se rechaza con 4xx",
      400 <= r.status_code < 500, f"status {r.status_code}")

MTBE = ["isobutene", "methanol", "mtbe"]
REACCION = {"nu": [-1.0, -1.0, 1.0], "A": 1e4, "Ea": 45000.0, "componente_referencia": 0}

r = cliente.post("/termodinamica/reaccion",
                 json={"componentes": MTBE, "reaccion": REACCION, "T_referencia": 350.0})
if r.status_code == 200:
    props = r.json()
    bien, motivo = json_valido(props)
    check("4.7 /termodinamica/reaccion serializa", bien, motivo)
    check("4.8 Trae la constante de equilibrio y es positiva",
          any(isinstance(v, (int, float)) and v > 0
              for k, v in props.items() if "eq" in k.lower()),
          ", ".join(f"{k}={v}" for k, v in props.items()
                    if isinstance(v, (int, float)))[:120])
else:
    check("4.7 /termodinamica/reaccion responde 200", False,
          f"status {r.status_code}: {r.text[:140]}")

# El mapa residual es el endpoint MAS caro del proyecto (85 s con la malla
# por omision, medido). Aqui se pide la malla mas pequena posible: lo que
# se prueba es la frontera, no el coste.
r = cliente.post("/termodinamica/mapa-residual",
                 json={"componentes": MTBE, "n_curvas": 3, "n_puntos": 20,
                       "max_etapas": 10, "incluir_trayectorias_discretas": False})
if r.status_code == 200:
    mapa = r.json()
    bien, motivo = json_valido(mapa)
    check("4.9 /termodinamica/mapa-residual serializa", bien, motivo)
    curvas = mapa.get("curvas") or []
    check("4.10 Devuelve las curvas pedidas", len(curvas) == 3, f"{len(curvas)} curva(s)")
    # Una curva residual vive en el simplex. Si alguna composicion sale de
    # ahi, lo que se dibuje encima no significa nada -- y es un fallo que
    # "devuelve un array de la forma correcta" no vería.
    fuera = 0
    for c in curvas:
        for punto in (c.get("x") or c.get("puntos") or []):
            if isinstance(punto, (list, tuple)):
                s = sum(punto)
                if any(v < -1e-6 or v > 1 + 1e-6 for v in punto) or abs(s - 1) > 1e-4:
                    fuera += 1
    check("4.11 Todas las composiciones están DENTRO del simplex",
          fuera == 0, f"{fuera} punto(s) fuera")
else:
    check("4.9 /termodinamica/mapa-residual responde 200", False,
          f"status {r.status_code}: {r.text[:140]}")

r = cliente.post("/termodinamica/azeotropos",
                 json={"componentes": MTBE, "reaccion": REACCION,
                       "modo": "equilibrio", "n_semillas": 4})
if r.status_code == 200:
    az = r.json()
    bien, motivo = json_valido(az)
    check("4.12 /termodinamica/azeotropos serializa", bien, motivo)
    encontrados = az.get("azeotropos") or []
    check("4.13 La respuesta tiene forma de lista (cero es un resultado válido)",
          isinstance(encontrados, list), f"{len(encontrados)} encontrado(s)")
    hay_nan = any(
        isinstance(v, float) and math.isnan(v)
        for a in encontrados if isinstance(a, dict)
        for v in a.values() if isinstance(v, float)
    )
    check("4.14 Y ningún azeótropo trae NaN dentro", not hay_nan)
else:
    check("4.12 /termodinamica/azeotropos responde 200", False,
          f"status {r.status_code}: {r.text[:140]}")


# ======================================================================
print("\n=== 5. Lo que debe rechazarse ===\n")
# ======================================================================

casos = [
    ("componente inexistente en /elv/binario", "/elv/binario",
     {"nombres": ["benzene", "noexisteestecomponente"]}),
    ("nu de otro tamaño que los componentes", "/termodinamica/reaccion",
     {"componentes": MTBE, "reaccion": {**REACCION, "nu": [-1.0, 1.0]}}),
    ("cuerpo vacío en /columna/resolver", "/columna/resolver", {}),
    ("método inexistente en /columna/resolver", "/columna/resolver",
     {"metodo": "inventado", "nombres": ["benzene", "toluene"],
      "feed": {"composicion": [0.5, 0.5], "flujo_molar": 100.0, "P": 101325.0},
      "parametros": {}}),
]
for nombre, ruta, cuerpo in casos:
    resp = cliente.post(ruta, json=cuerpo)
    check(f"5.x {nombre} -> 4xx", 400 <= resp.status_code < 500,
          f"status {resp.status_code}")

# Un gas permanente no tiene grupos UNIFAC, y eso es una limitacion REAL
# del modelo. Lo que no puede es salir como un 500 opaco.
r = cliente.post("/elv/binario", json={"nombres": ["methane", "toluene"]})
ok = 400 <= r.status_code < 500
detalle = r.json().get("detail", "")[:170] if ok else f"status {r.status_code}: {r.text[:120]}"
check("5.5 Un componente sin grupos UNIFAC se explica, no da 500", ok, detalle)
if ok:
    check("5.6 Y el mensaje nombra al componente culpable",
          "methane" in detalle.lower(), detalle[:120])


print()
if fallos:
    print(f"FALLARON {len(fallos)}:")
    for f in fallos:
        print("   - " + f)
    sys.exit(1)
print("TODO OK")
