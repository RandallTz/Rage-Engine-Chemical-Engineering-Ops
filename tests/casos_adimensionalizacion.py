"""
Constructores de documentos v1 para las pruebas y los ejemplos canonicos
del nucleo de adimensionalizacion. Solo arman arboles del contrato: no
contienen resultados esperados de la transformacion.
"""

import copy


def s(i):
    return {"tipo": "simbolo", "id": i}


def n(v):
    return {"tipo": "numero", "valor": v}


def suma(*a):
    return {"tipo": "suma", "argumentos": list(a)}


def prod(*a):
    return {"tipo": "producto", "argumentos": list(a)}


def coc(a, b):
    return {"tipo": "cociente", "numerador": a, "denominador": b}


def pot(b, e):
    return {"tipo": "potencia", "base": b, "exponente": e if isinstance(e, dict) else n(e)}


def fun(nombre, *a):
    return {"tipo": "funcion", "nombre": nombre, "argumentos": list(a)}


def llam(f, *a):
    return {"tipo": "llamada", "funcionId": f, "argumentos": list(a)}


def d(e, v, orden=1):
    return {"tipo": "derivada", "expresion": e, "respecto": v, "orden": orden}


def lap(e, *c):
    return {"tipo": "laplaciano", "expresion": e, "coordenadas": list(c)}


def grad(e, *c):
    return {"tipo": "gradiente", "expresion": e, "coordenadas": list(c)}


def div(e, *c):
    return {"tipo": "divergencia", "expresion": e, "coordenadas": list(c)}


def neg(e):
    return prod(n(-1), e)


def dim(**k):
    return {b: {"n": v, "d": 1} for b, v in k.items()}


def simbolo(i, rol, dimension, depende=(), signo=None, unidad=None, constante=None):
    if signo is None:
        signo = "positivo" if rol in ("parametro", "constante") else "desconocido"
    return {"id": i, "nombre": i, "rol": rol, "dimension": dimension, "unidad": unidad,
            "constante": (rol in ("parametro", "constante")) if constante is None else constante,
            "dependeDe": list(depende), "signo": signo}


def igualdad(i, izq, der):
    return {"id": i, "izquierda": izq, "derecha": der}


def escala(v, valor=None, transformar=True, dimension=None):
    return {"simboloId": v, "transformar": transformar, "nuevoNombre": f"{v}_ad", "dimension": dimension,
            "valor": valor or {"tipo": "libre"}}


def cantidad(valor, unidad):
    return {"tipo": "cantidad", "valor": valor, "unidad": unidad}


def expresion(e):
    return {"tipo": "expresion", "expresion": e}


def objetivo(i, ecuacion, termino, valor=1, accion="normalizar"):
    return {"id": i, "ecuacionId": ecuacion, "termino": termino, "valor": valor, "accion": accion}


def documento(simbolos, ecuaciones, escalas, objetivos=(), funciones=(), dominios=(), condiciones=(),
              presentacion="factorizada", revision=1, forma_revision=None):
    forma = {"id": "forma-1", "nombre": "Forma 1", "padreId": None,
             "modeloRevision": revision if forma_revision is None else forma_revision,
             "escalas": list(escalas), "objetivos": list(objetivos), "presentacion": presentacion}
    return {"formato": "adimensionalizacion", "version": 1, "id": "doc-prueba", "nombre": "Prueba",
            "modelo": {"id": "modelo-prueba", "revision": revision, "simbolos": list(simbolos), "funciones": list(funciones),
                       "ecuaciones": list(ecuaciones), "dominios": list(dominios), "condiciones": list(condiciones)},
            "formas": [forma], "activaId": "forma-1"}


def solicitud(doc, operacion="transformar"):
    r = {"formato": "adimensionalizacion.solicitud", "version": 1, "operacion": operacion, "documento": copy.deepcopy(doc)}
    if operacion == "transformar":
        r["formaId"] = doc["activaId"]
    return r


# --- Modelo de aceptacion del plan (seccion 3) ---------------------------------

TERMINO_D = prod(s("D"), lap(s("c"), "x"))
TERMINO_K = prod(s("k"), s("c"))
TERMINO_A = prod(n(-1), s("a"), pot(s("c"), 2))


def reaccion_difusion(signo_k="positivo", signo_D="positivo", dimension_k=None, con_dominio=True):
    simbolos = [simbolo("t", "tiempo", dim(T=1)), simbolo("x", "coordenada", dim(L=1)),
                simbolo("c", "campo", dim(N=1, L=-3), ["t", "x"]),
                simbolo("D", "parametro", dim(L=2, T=-1), signo=signo_D),
                simbolo("k", "parametro", dimension_k if dimension_k is not None else dim(T=-1), signo=signo_k),
                simbolo("a", "parametro", dim(N=-1, L=3, T=-1)),
                simbolo("ell", "parametro", dim(L=1))]
    ec = igualdad("balance", d(s("c"), "t"), suma(TERMINO_D, TERMINO_K, TERMINO_A))
    dominios = [{"id": "intervalo-x", "variableId": "x", "desde": n(0), "hasta": s("ell")}] if con_dominio else []
    return simbolos, [ec], dominios


def forma_seccion3(objetivos, **kw):
    simbolos, ecs, dominios = reaccion_difusion(**kw)
    return documento(simbolos, ecs, [escala("t"), escala("c"), escala("x")], objetivos, dominios=dominios)


OBJ_D = objetivo("difusion", "balance", TERMINO_D, 1)
OBJ_K = objetivo("lineal", "balance", TERMINO_K, 1)
OBJ_A = objetivo("cuadratico", "balance", TERMINO_A, -1)

FORMAS_SECCION3 = {
    "general": [],
    "tiempo-difusivo": [OBJ_D],
    "tiempo-reactivo": [OBJ_K],
    "campo-cinetico": [OBJ_K, OBJ_A],
    "longitud-parametrica": [OBJ_K, OBJ_A, OBJ_D],
}
