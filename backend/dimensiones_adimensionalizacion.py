"""Lectura dimensional para la interfaz; reutiliza el analizador científico único.

No deduce unidades a partir de nombres ni introduce reglas algebraicas nuevas.
Las etiquetas de magnitud son candidatas por dimensión, no pruebas de identidad física.
"""
import copy
import re

from core.adimensionalizacion import procesar
from core.adimensionalizacion.dimensional import (
    Analizador, analizar_modelo, dim_a_json, interpretar_unidad,
)
from core.adimensionalizacion.lector import leer_documento


MAGNITUDES = [
    ("tiempo", "Tiempo", "s"), ("longitud", "Longitud", "m"),
    ("masa", "Masa", "kg"), ("cantidad", "Cantidad de sustancia", "mol"),
    ("temperatura", "Temperatura", "K"), ("volumen", "Volumen", "L"),
    ("area", "Área", "m^2"), ("concentracion", "Concentración molar", "mol/L"),
    ("densidad", "Densidad de masa / concentración másica", "kg/m^3"),
    ("difusividad", "Difusividad / viscosidad cinemática", "m^2/s"),
    ("velocidad", "Velocidad", "m/s"), ("presion", "Presión / densidad de energía", "Pa"),
    ("energia", "Energía / trabajo", "J"), ("potencia", "Potencia", "W"),
    ("caudal", "Caudal volumétrico", "L/s"), ("frecuencia", "Frecuencia / tasa", "1/s"),
    ("adimensional", "Cantidad adimensional", "1"),
]
ALIAS = {"Kg": "kg", "KG": "kg", "litro": "L", "litros": "L", "litre": "L",
         "seg": "s", "segundo": "s", "segundos": "s", "moles": "mol",
         "gramo": "g", "gramos": "g", "kelvin": "K", "°C": "degC", "°F": "degF"}


def normalizar_unidad(texto):
    texto = texto.strip().replace("·", "*").replace("³", "^3").replace("²", "^2")
    return re.sub(r"[A-Za-z°]+", lambda m: ALIAS.get(m[0], m[0]), texto)


def normalizar_solicitud(solicitud):
    s = copy.deepcopy(solicitud)
    if not isinstance(s, dict):
        return s
    modelo = s.get("documento", {}).get("modelo", {}) if isinstance(s.get("documento"), dict) else s.get("modelo", {})
    if isinstance(modelo, dict) and isinstance(modelo.get("simbolos"), list):
        for simbolo in modelo["simbolos"]:
            if isinstance(simbolo, dict) and isinstance(simbolo.get("unidad"), str):
                simbolo["unidad"] = normalizar_unidad(simbolo["unidad"])
    return s


def procesar_seguro(solicitud):
    """Una unidad no interpretable nunca permite publicar una formulación."""
    r = procesar(normalizar_solicitud(solicitud))
    inseguros = [d for d in r["diagnosticos"] if d["codigo"] in ("unidad_no_reconocida", "unidad_no_comparable")]
    if inseguros:
        r = {k: v for k, v in r.items() if k in ("formato", "version", "operacion", "nucleo", "vinculo", "dimensional", "diagnosticos")}
        r["estado"] = "rechazado"
        r["diagnosticos"] = [{**d, "severidad": "error"} if d in inseguros else d for d in r["diagnosticos"]]
    return r


def _terminos(e, ruta):
    if e["tipo"] == "suma":
        return [t for i, a in enumerate(e["argumentos"]) for t in _terminos(a, f"{ruta}.argumentos[{i}]")]
    return [(e, ruta)]


def _operadores(e):
    tipos = {"derivada", "gradiente", "divergencia", "laplaciano", "funcion", "llamada"}
    encontrados = [{"tipo": e["tipo"], **({"respecto": e["respecto"], "orden": e["orden"]} if e["tipo"] == "derivada" else {}),
                    **({"coordenadas": e["coordenadas"]} if "coordenadas" in e else {}),
                    **({"nombre": e.get("nombre", e.get("funcionId"))} if e["tipo"] in ("funcion", "llamada") else {})}] if e["tipo"] in tipos else []
    hijos = e.get("argumentos", []) + [e[k] for k in ("expresion", "numerador", "denominador", "base", "exponente") if k in e]
    return encontrados + [op for hijo in hijos for op in _operadores(hijo)]


def auditar_dimensiones(solicitud):
    normalizada = normalizar_solicitud(solicitud)
    r = procesar_seguro(normalizada)
    salida = {"formato": "adimensionalizacion.dimensiones", "version": 1, "analisis": r,
              "ecuaciones": [], "cantidades": [],
              "catalogo": [{"id": i, "nombre": n, "unidad": u} for i, n, u in MAGNITUDES]}
    # Solo se recorre un AST que el contrato científico ya ha leído.
    if not isinstance(normalizada, dict) or normalizada.get("operacion") != "analizar" or "dimensional" not in r:
        return salida
    documento = leer_documento(normalizada["documento"])
    modelo = documento["modelo"]
    an = analizar_modelo(modelo)
    funciones = {fid: {"entradas": f["entradas_finales"], "salida": f["salida_final"]} for fid, f in an["funciones_dim"].items()}
    simbolos = {sid: {"dimension": d, "rol": None} for sid, d in an["dimensiones"].items()}

    def evaluar(e):
        lector = Analizador(simbolos, funciones)
        d, rango = lector.expresion(e, "expresion")
        errores = any(x["severidad"] == "error" for x in lector.diagnosticos)
        return lector.dimension(d), errores, rango

    for i, eq in enumerate(modelo["ecuaciones"]):
        di, _, _ = evaluar(eq["izquierda"])
        dd, _, _ = evaluar(eq["derecha"])
        esperada = di if di is not None else dd
        terminos = []
        for lado in ("izquierda", "derecha"):
            for e, ruta in _terminos(eq[lado], f"ecuaciones[{i}].{lado}"):
                d, error, rango = evaluar(e)
                cero = e == {"tipo": "numero", "valor": 0}
                estado = "incompatible" if error or (d is not None and esperada is not None and d != esperada) or rango is not None else (
                    "cero" if cero else "pendiente" if d is None or esperada is None else "compatible")
                terminos.append({"ruta": ruta, "lado": lado, "expresion": e, "dimension": dim_a_json(d),
                                 "estado": estado, "operadores": _operadores(e)})
        salida["ecuaciones"].append({"id": eq["id"], "dimension": dim_a_json(esperada), "terminos": terminos})
    for s in modelo["simbolos"]:
        d = an["dimensiones"][s["id"]]
        candidatas = [i for i, _, u in MAGNITUDES if d is not None and interpretar_unidad(u)["dimension"] == d]
        original = next(x for x in solicitud["documento"]["modelo"]["simbolos"] if x["id"] == s["id"])
        salida["cantidades"].append({"id": s["id"], "unidadIntroducida": original["unidad"], "unidadNormalizada": s["unidad"],
                                     "magnitudes": candidatas})
    return salida
