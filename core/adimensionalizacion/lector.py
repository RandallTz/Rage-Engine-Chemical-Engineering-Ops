"""
Lector estricto del documento v1 de adimensionalizacion.

Replica en el servidor la validacion estructural del lector del cliente
(`frontend/app/adimensionalizacion/documento.ts`): campos exactos,
referencias, identidades unicas, limites de tamano. El nucleo no confia en
que el cliente ya lo haya comprobado. Version o campo desconocido -> se
rechaza (no se migra en silencio).
"""

import json

LIMITE_BYTES = 1_000_000
LIMITE_LISTA = 500
LIMITE_NODOS = 20000
LIMITE_NIVEL = 40
FUNCIONES = ("exp", "log", "sin", "cos", "tan", "tanh", "sinh", "cosh", "atan", "erf", "abs", "min", "max")
# Funciones trascendentes: argumento adimensional y valor adimensional.
TRASCENDENTES = ("exp", "log", "sin", "cos", "tan", "tanh", "sinh", "cosh", "atan", "erf")
ROLES = ("tiempo", "coordenada", "campo", "parametro", "constante")
SIGNOS = ("positivo", "negativo", "cero", "desconocido")
UNIDADES_AFINES = ("°C", "degC", "°F", "degF", "celsius", "fahrenheit")


class ErrorContrato(Exception):
    def __init__(self, ruta, mensaje):
        super().__init__(f"{ruta}: {mensaje}")
        self.ruta = ruta
        self.mensaje = mensaje


def _fallo(ruta, motivo):
    raise ErrorContrato(ruta, motivo)


def _obj(v, ruta):
    if not isinstance(v, dict):
        _fallo(ruta, "se esperaba un objeto")
    return v


def _exacto(v, ruta, claves):
    o = _obj(v, ruta)
    if set(o) != set(claves):
        _fallo(ruta, "campos desconocidos o ausentes")
    return o


def _texto(v, ruta):
    if not isinstance(v, str) or not v.strip() or len(v) > 500:
        _fallo(ruta, "texto requerido (maximo 500 caracteres)")


def _entero(v, ruta, positivo=False):
    if isinstance(v, bool) or not isinstance(v, int) or abs(v) > 2 ** 53 - 1 or (positivo and v <= 0):
        _fallo(ruta, "entero valido requerido")


def _lista(v, ruta):
    if not isinstance(v, list) or len(v) > LIMITE_LISTA:
        _fallo(ruta, "lista requerida (maximo 500 elementos)")
    return v


def _opcion(v, ruta, opciones):
    if isinstance(v, bool) and not any(o is v for o in opciones):
        _fallo(ruta, "valor no admitido")
    if v not in opciones:
        _fallo(ruta, "valor no admitido")


def _dimension(v, ruta):
    if v is None:
        return
    o = _obj(v, ruta)
    if len(o) > 20:
        _fallo(ruta, "demasiadas dimensiones base")
    for k, r in o.items():
        if not isinstance(k, str) or not k[:1].isalpha() or not all(ch.isalnum() or ch == "_" for ch in k) or not k.isascii():
            _fallo(ruta, "base dimensional invalida")
        q = _exacto(r, f"{ruta}.{k}", ["n", "d"])
        _entero(q["n"], ruta)
        _entero(q["d"], ruta, True)


def _claves(v, ruta, obligatorias, opcionales=()):
    """Como _exacto, admitiendo ademas los campos opcionales presentes."""
    o = _obj(v, ruta)
    if not set(obligatorias) <= set(o) or set(o) - set(obligatorias) - set(opcionales):
        _fallo(ruta, "campos desconocidos o ausentes")
    return o


def leer_documento(dato):
    """Valida un documento v1 o v2 (dict ya decodificado). Devuelve el mismo dict.

    v2 = v1 + campos opcionales: `funciones[].escala`, `condiciones[].ubicacion`,
    `formas[].transformaciones`, `formas[].referencias`,
    `formas[].prioridadEscalas` y `formas[].objetivos[].terminoId` (con
    `termino` opcional). Un documento v1 no admite ninguno de ellos."""
    if len(json.dumps(dato, ensure_ascii=False).encode("utf-8")) > LIMITE_BYTES:
        _fallo("documento", "el documento supera 1 MB")
    claves = ["formato", "version", "id", "nombre", "modelo", "formas", "activaId"]
    if isinstance(dato, dict) and "exploracion" in dato:
        claves.append("exploracion")
    doc = _exacto(dato, "documento", claves)
    _opcion(doc["formato"], "formato", ["adimensionalizacion"])
    _opcion(doc["version"], "version", [1, 2])
    version = doc["version"]
    for k in ("id", "nombre", "activaId"):
        _texto(doc[k], k)
    if "exploracion" in doc:
        leer_config_exploracion(doc["exploracion"], "exploracion")
    modelo = leer_modelo(doc["modelo"], version=version)
    formas = _lista(doc["formas"], "formas")
    ids_formas = _unicos(formas, "formas")
    if doc["activaId"] not in ids_formas:
        _fallo("activaId", "referencia inexistente")
    for i, f in enumerate(formas):
        leer_forma(f, f"formas[{i}]", modelo, ids_formas, version=version)
    for f in formas:
        vistos, actual = set(), f
        while actual is not None:
            if actual["id"] in vistos:
                _fallo("formas", "ciclo de ascendencia")
            vistos.add(actual["id"])
            actual = next((g for g in formas if g["id"] == actual["padreId"]), None) if actual["padreId"] is not None else None
    return doc


def leer_config_exploracion(v, ruta):
    c = _exacto(v, ruta, ["presupuesto", "maxObjetivos", "respetarEscalasFijadas", "incluirGruposPi", "maxExponentePi", "maxDenominadorPi"])
    for campo, maximo in (("presupuesto", 200), ("maxObjetivos", 8), ("maxExponentePi", 12), ("maxDenominadorPi", 12)):
        _entero(c[campo], f"{ruta}.{campo}", True)
        if c[campo] > maximo:
            _fallo(f"{ruta}.{campo}", f"maximo {maximo}")
    for campo in ("respetarEscalasFijadas", "incluirGruposPi"):
        if not isinstance(c[campo], bool):
            _fallo(f"{ruta}.{campo}", "valor no admitido")
    return c


def _unicos(items, ruta):
    ids = []
    for i, v in enumerate(items):
        o = _obj(v, f"{ruta}[{i}]")
        _texto(o.get("id"), f"{ruta}.id")
        ids.append(o["id"])
    if len(set(ids)) != len(ids):
        _fallo(ruta, "identidades duplicadas")
    return set(ids)


class _Expresiones:
    def __init__(self, ids, fids, funciones, variables, coordenadas):
        self.ids, self.fids, self.funciones = ids, fids, funciones
        self.variables, self.coordenadas = variables, coordenadas
        self.nodos = 0

    def ref(self, v, ruta, conjunto):
        if not isinstance(v, str) or v not in conjunto:
            _fallo(ruta, "referencia inexistente")

    def leer(self, v, ruta, nivel=0):
        self.nodos += 1
        if self.nodos > LIMITE_NODOS or nivel > LIMITE_NIVEL:
            _fallo(ruta, "expresion demasiado compleja")
        e = _obj(v, ruta)
        t = e.get("tipo")
        sub = lambda x, r: self.leer(x, r, nivel + 1)
        if t == "numero":
            _exacto(e, ruta, ["tipo", "valor"])
            x = e["valor"]
            if isinstance(x, bool) or not isinstance(x, (int, float)) or x != x or x in (float("inf"), float("-inf")):
                _fallo(ruta, "numero finito requerido")
        elif t == "simbolo":
            _exacto(e, ruta, ["tipo", "id"])
            self.ref(e["id"], ruta, self.ids)
        elif t in ("suma", "producto", "funcion", "llamada"):
            claves = {"funcion": ["tipo", "nombre", "argumentos"], "llamada": ["tipo", "funcionId", "argumentos"]}.get(t, ["tipo", "argumentos"])
            _exacto(e, ruta, claves)
            args = _lista(e["argumentos"], ruta + ".argumentos")
            if not args:
                _fallo(ruta, "faltan argumentos")
            if t == "funcion":
                _opcion(e["nombre"], ruta, list(FUNCIONES))
                if e["nombre"] not in ("min", "max") and len(args) != 1:
                    _fallo(ruta, "la funcion necesita un argumento")
            if t == "llamada":
                self.ref(e["funcionId"], ruta, self.fids)
                if len(args) != len(self.funciones[e["funcionId"]]["entradas"]):
                    _fallo(ruta, "aridad de funcion incorrecta")
            for i, a in enumerate(args):
                sub(a, f"{ruta}.argumentos[{i}]")
        elif t == "cociente":
            _exacto(e, ruta, ["tipo", "numerador", "denominador"])
            sub(e["numerador"], ruta + ".numerador")
            sub(e["denominador"], ruta + ".denominador")
        elif t == "potencia":
            _exacto(e, ruta, ["tipo", "base", "exponente"])
            sub(e["base"], ruta + ".base")
            sub(e["exponente"], ruta + ".exponente")
        elif t == "derivada":
            _exacto(e, ruta, ["tipo", "expresion", "respecto", "orden"])
            self.ref(e["respecto"], ruta, self.variables)
            _entero(e["orden"], ruta, True)
            sub(e["expresion"], ruta + ".expresion")
        elif t in ("gradiente", "divergencia", "laplaciano"):
            _exacto(e, ruta, ["tipo", "expresion", "coordenadas"])
            coords = _lista(e["coordenadas"], ruta)
            if not coords:
                _fallo(ruta, "faltan coordenadas")
            for c in coords:
                self.ref(c, ruta, self.coordenadas)
            if len(set(coords)) != len(coords):
                _fallo(ruta, "referencias duplicadas")
            sub(e["expresion"], ruta + ".expresion")
        else:
            _fallo(ruta, "operador no admitido por el contrato v1")

    def igualdad(self, v, ruta):
        o = _exacto(v, ruta, ["id", "izquierda", "derecha"])
        _texto(o["id"], ruta)
        self.leer(o["izquierda"], ruta + ".izquierda")
        self.leer(o["derecha"], ruta + ".derecha")


def leer_modelo(v, ruta="modelo", version=1):
    modelo = _exacto(v, ruta, ["id", "revision", "simbolos", "funciones", "ecuaciones", "dominios", "condiciones"])
    v2 = version >= 2
    _texto(modelo["id"], "modelo.id")
    _entero(modelo["revision"], "modelo.revision", True)
    simbolos = _lista(modelo["simbolos"], "simbolos")
    funciones = _lista(modelo["funciones"], "funciones")
    ids, fids = _unicos(simbolos, "simbolos"), _unicos(funciones, "funciones")
    if ids & fids:
        _fallo("funciones", "identidad compartida con un simbolo")
    roles = {s["id"]: s.get("rol") for s in simbolos}
    variables = {i for i, r in roles.items() if r in ("tiempo", "coordenada")}
    coordenadas = {i for i, r in roles.items() if r == "coordenada"}

    def refs(lista, r, conjunto):
        _lista(lista, r)
        for x in lista:
            if not isinstance(x, str) or x not in conjunto:
                _fallo(r, "referencia inexistente")
        if len(set(lista)) != len(lista):
            _fallo(r, "referencias duplicadas")

    for i, s in enumerate(simbolos):
        r = f"simbolos[{i}]"
        _exacto(s, r, ["id", "nombre", "rol", "dimension", "unidad", "constante", "dependeDe", "signo"])
        _texto(s["nombre"], r)
        _opcion(s["rol"], r, list(ROLES))
        _dimension(s["dimension"], r)
        if s["unidad"] is not None:
            _texto(s["unidad"], r)
        if not isinstance(s["constante"], bool):
            _fallo(r, "valor no admitido")
        refs(s["dependeDe"], r, variables)
        if s["constante"] and s["dependeDe"]:
            _fallo(r, "un simbolo constante no puede depender de variables")
        _opcion(s["signo"], r, list(SIGNOS))
    if sum(1 for s in simbolos if s["rol"] == "tiempo") > 1:
        _fallo("simbolos", "el sistema comparte una sola variable de tiempo")
    adimensionales = set()
    por_id = {s["id"]: s for s in simbolos}
    for i, f in enumerate(funciones):
        r = f"funciones[{i}]"
        _claves(f, r, ["id", "nombre", "entradas", "salida", "dependeDe"], ["escala"] if v2 else [])
        _texto(f["nombre"], r)
        for d in _lista(f["entradas"], r):
            _dimension(d, r)
        _dimension(f["salida"], r)
        refs(f["dependeDe"], r, variables)
        if "escala" in f:
            # v2: f(z) = S * fhat(z/s); S es un parametro constante del modelo.
            re = r + ".escala"
            e = _exacto(f["escala"], re, ["simboloId", "funcionAdimensional"])
            if not isinstance(e["simboloId"], str) or e["simboloId"] not in por_id:
                _fallo(re + ".simboloId", "referencia inexistente")
            sim = por_id[e["simboloId"]]
            if sim["rol"] not in ("parametro", "constante") or not sim["constante"]:
                _fallo(re + ".simboloId", "la escala de una funcion debe ser un parametro constante")
            if sim["signo"] == "cero":
                _fallo(re + ".simboloId", "la escala de una funcion no puede ser nula")
            _texto(e["funcionAdimensional"], re + ".funcionAdimensional")
            fa = e["funcionAdimensional"]
            if fa in ids or fa in fids or fa in adimensionales:
                _fallo(re + ".funcionAdimensional", "identidad ocupada")
            adimensionales.add(fa)
    lector = _Expresiones(ids, fids, {f["id"]: f for f in funciones}, variables, coordenadas)
    ecuaciones = _lista(modelo["ecuaciones"], "ecuaciones")
    _unicos(ecuaciones, "ecuaciones")
    for i, e in enumerate(ecuaciones):
        lector.igualdad(e, f"ecuaciones[{i}]")
    dominios = _lista(modelo["dominios"], "dominios")
    dids = _unicos(dominios, "dominios")
    for i, d in enumerate(dominios):
        r = f"dominios[{i}]"
        _exacto(d, r, ["id", "variableId", "desde", "hasta"])
        lector.ref(d["variableId"], r, variables)
        lector.leer(d["desde"], r)
        lector.leer(d["hasta"], r)
    condiciones = _lista(modelo["condiciones"], "condiciones")
    _unicos(condiciones, "condiciones")
    var_dominio = {d["id"]: d["variableId"] for d in dominios}
    for i, c in enumerate(condiciones):
        r = f"condiciones[{i}]"
        _claves(c, r, ["id", "tipo", "dominioId", "ecuacion"], ["ubicacion"] if v2 else [])
        _opcion(c["tipo"], r, ["inicial", "dirichlet", "flujo", "mixta"])
        lector.ref(c["dominioId"], r, dids)
        lector.igualdad(c["ecuacion"], r)
        if "ubicacion" in c:
            ru = r + ".ubicacion"
            u = _exacto(c["ubicacion"], ru, ["variableId", "extremo"])
            if u["variableId"] != var_dominio[c["dominioId"]]:
                _fallo(ru + ".variableId", "la ubicacion debe usar la variable del dominio de la condicion")
            _opcion(u["extremo"], ru + ".extremo", ["desde", "hasta"])
            rol = roles[u["variableId"]]
            if (c["tipo"] == "inicial") != (rol == "tiempo"):
                _fallo(ru + ".variableId", "una condicion inicial se ubica en el tiempo y una de frontera en una coordenada")
    return modelo


def leer_forma(f, ruta, modelo, ids_formas, version=1):
    v2 = version >= 2
    o = _claves(f, ruta, ["id", "nombre", "padreId", "modeloRevision", "escalas", "objetivos", "presentacion"],
                ["transformaciones", "referencias", "prioridadEscalas"] if v2 else [])
    _texto(o["nombre"], ruta)
    if o["padreId"] is not None and (not isinstance(o["padreId"], str) or o["padreId"] not in ids_formas):
        _fallo(ruta, "referencia inexistente")
    _entero(o["modeloRevision"], ruta, True)
    if o["modeloRevision"] > modelo["revision"]:
        _fallo(ruta, "revision futura")
    _opcion(o["presentacion"], ruta, ["factorizada", "desarrollada"])
    simbolos = {s["id"]: s for s in modelo["simbolos"]}
    roles = {i: s["rol"] for i, s in simbolos.items()}
    variables = {i for i, r in roles.items() if r in ("tiempo", "coordenada")}
    coordenadas = {i for i, r in roles.items() if r == "coordenada"}
    fun = {x["id"]: x for x in modelo["funciones"]}
    lector = _Expresiones(set(simbolos), set(fun), fun, variables, coordenadas)
    vistas = set()
    for j, e in enumerate(_lista(o["escalas"], ruta + ".escalas")):
        r = f"{ruta}.escalas[{j}]"
        _exacto(e, r, ["simboloId", "transformar", "nuevoNombre", "dimension", "valor"])
        lector.ref(e["simboloId"], r, set(simbolos))
        if roles[e["simboloId"]] not in ("campo", "tiempo", "coordenada"):
            _fallo(r, "solo se escalan variables")
        if e["simboloId"] in vistas:
            _fallo(r, "escala duplicada")
        vistas.add(e["simboloId"])
        if not isinstance(e["transformar"], bool):
            _fallo(r, "valor no admitido")
        _texto(e["nuevoNombre"], r)
        _dimension(e["dimension"], r)
        valor = _obj(e["valor"], r + ".valor")
        tipo = valor.get("tipo")
        if tipo == "libre":
            _exacto(valor, r, ["tipo"])
        elif tipo == "cantidad":
            _exacto(valor, r, ["tipo", "valor", "unidad"])
            x = valor["valor"]
            if isinstance(x, bool) or not isinstance(x, (int, float)) or not (0 < x < float("inf")):
                _fallo(r, "escala finita y positiva requerida")
            _texto(valor["unidad"], r)
            if valor["unidad"] in UNIDADES_AFINES:
                _fallo(r, "una temperatura afin no es una escala multiplicativa")
        elif tipo == "expresion":
            _exacto(valor, r, ["tipo", "expresion"])
            lector.leer(valor["expresion"], r)
        else:
            _fallo(r, "tipo de escala no admitido")
    eqids = {e["id"] for e in modelo["ecuaciones"]}
    objetivos = _lista(o["objetivos"], ruta + ".objetivos")
    _unicos(objetivos, ruta)
    for j, t in enumerate(objetivos):
        r = f"{ruta}.objetivos[{j}]"
        if v2:
            # v2: el termino se identifica por terminoId (catalogo de `analizar`);
            # la expresion queda opcional y, si llega, debe designar el mismo.
            _claves(t, r, ["id", "ecuacionId", "valor", "accion"], ["termino", "terminoId"])
            if "termino" not in t and "terminoId" not in t:
                _fallo(r, "se requiere terminoId o termino")
        else:
            _exacto(t, r, ["id", "ecuacionId", "termino", "valor", "accion"])
        lector.ref(t["ecuacionId"], r, eqids)
        if "termino" in t:
            lector.leer(t["termino"], r)
        if "terminoId" in t:
            _id_termino(t["terminoId"], t["ecuacionId"], r + ".terminoId")
        if isinstance(t["valor"], bool) or t["valor"] not in (1, -1):
            _fallo(r, "valor no admitido")
        _opcion(t["accion"], r, ["normalizar", "conservar_grupo"])
    if "transformaciones" in o:
        leer_transformaciones(o["transformaciones"], modelo, ruta + ".transformaciones")
    if "referencias" in o:
        leer_referencias(o["referencias"], modelo, ruta + ".referencias")
    if "prioridadEscalas" in o:
        leer_prioridad(o["prioridadEscalas"], ruta + ".prioridadEscalas")
    return o


def _id_termino(tid, ambito, ruta):
    """`<ecuacionId|condicionId>:<ruta>[#k]`; su existencia la decide el nucleo
    (el catalogo depende de la forma canonica)."""
    _texto(tid, ruta)
    if not tid.startswith(ambito + ":"):
        _fallo(ruta, f"el termino debe pertenecer a '{ambito}'")


def leer_referencias(lista, modelo, ruta):
    """v2: dividir una igualdad por la magnitud del coeficiente de otro termino."""
    lista = _lista(lista, ruta)
    eqids = {e["id"] for e in modelo["ecuaciones"]}
    cids = {c["id"] for c in modelo["condiciones"]}
    vistas = set()
    for i, x in enumerate(lista):
        r = f"{ruta}[{i}]"
        _exacto(x, r, ["ecuacionId", "terminoId"])
        e = x["ecuacionId"]
        if not isinstance(e, str) or e not in eqids | cids:
            _fallo(r + ".ecuacionId", "referencia inexistente")
        if e in eqids and e in cids:
            _fallo(r + ".ecuacionId", "identidad ambigua: es a la vez ecuacion y condicion")
        if e in vistas:
            _fallo(r + ".ecuacionId", "referencia duplicada")
        vistas.add(e)
        _id_termino(x["terminoId"], e, r + ".terminoId")
    return lista


def leer_prioridad(lista, ruta):
    """v2: orden en que se despejan las escalas (ids de variables o de constantes)."""
    lista = _lista(lista, ruta)
    for i, x in enumerate(lista):
        _texto(x, f"{ruta}[{i}]")
    if len(set(lista)) != len(lista):
        _fallo(ruta, "referencias duplicadas")
    return lista


def _sin_operadores(e, ruta):
    """Un mapa de cambio de variable es algebraico: sin derivadas, operadores
    ni funciones declaradas (su inversa no se podria demostrar)."""
    t = e["tipo"]
    if t in ("derivada", "gradiente", "divergencia", "laplaciano", "llamada"):
        _fallo(ruta, "un cambio de variable no admite derivadas, operadores ni funciones declaradas")
    for i, a in enumerate(e.get("argumentos", [])):
        _sin_operadores(a, f"{ruta}.argumentos[{i}]")
    for k in ("numerador", "denominador", "base", "exponente"):
        if k in e:
            _sin_operadores(e[k], f"{ruta}.{k}")


def leer_transformaciones(lista, modelo, ruta="transformaciones"):
    """Mapas declarados v = g(v'), v' = h(v) con sus constantes y dominios."""
    lista = _lista(lista, ruta)
    simbolos = {s["id"]: s for s in modelo["simbolos"]}
    fun = {x["id"]: x for x in modelo["funciones"]}
    vistas, nuevos = set(), set()
    for i, t in enumerate(lista):
        r = f"{ruta}[{i}]"
        _exacto(t, r, ["variableId", "nuevoId", "directa", "inversa", "constantes", "dominio"])
        v = t["variableId"]
        if not isinstance(v, str) or v not in simbolos or simbolos[v]["rol"] not in ("campo", "tiempo", "coordenada"):
            _fallo(r + ".variableId", "solo se transforman variables del modelo")
        if v in vistas:
            _fallo(r + ".variableId", "transformacion duplicada")
        vistas.add(v)
        _texto(t["nuevoId"], r + ".nuevoId")
        if t["nuevoId"] in nuevos:
            _fallo(r + ".nuevoId", "identidades duplicadas")
        nuevos.add(t["nuevoId"])
        ids_c = []
        for k, c in enumerate(_lista(t["constantes"], r + ".constantes")):
            rc = f"{r}.constantes[{k}]"
            _exacto(c, rc, ["id", "nombre", "papel", "dimension", "valor"])
            _texto(c["id"], rc + ".id")
            _texto(c["nombre"], rc + ".nombre")
            _opcion(c["papel"], rc + ".papel", ["escala", "referencia"])
            _dimension(c["dimension"], rc + ".dimension")
            valor = _obj(c["valor"], rc + ".valor")
            tipo = valor.get("tipo")
            if tipo == "libre":
                _exacto(valor, rc + ".valor", ["tipo"])
            elif tipo == "cantidad":
                _exacto(valor, rc + ".valor", ["tipo", "valor", "unidad"])
                x = valor["valor"]
                if isinstance(x, bool) or not isinstance(x, (int, float)) or x != x or x in (float("inf"), float("-inf")):
                    _fallo(rc + ".valor", "numero finito requerido")
                if c["papel"] == "escala" and x <= 0:
                    _fallo(rc + ".valor", "escala finita y positiva requerida")
                _texto(valor["unidad"], rc + ".valor")
            elif tipo != "expresion":
                _fallo(rc + ".valor", "tipo de valor no admitido")
            ids_c.append(c["id"])
        if len(set(ids_c)) != len(ids_c):
            _fallo(r + ".constantes", "identidades duplicadas")
        variables = {i for i, s_ in simbolos.items() if s_["rol"] in ("tiempo", "coordenada")}
        coordenadas = {i for i, s_ in simbolos.items() if s_["rol"] == "coordenada"}
        for k, c in enumerate(t["constantes"]):
            if c["valor"]["tipo"] == "expresion":
                _exacto(c["valor"], f"{r}.constantes[{k}].valor", ["tipo", "expresion"])
                lector = _Expresiones(set(simbolos), set(fun), fun, variables, coordenadas)
                lector.leer(c["valor"]["expresion"], f"{r}.constantes[{k}].valor.expresion")
        ids = set(simbolos) | {t["nuevoId"]} | set(ids_c)
        lector = _Expresiones(ids, set(fun), fun, variables, coordenadas)
        for lado in ("directa", "inversa"):
            lector.leer(t[lado], f"{r}.{lado}")
            _sin_operadores(t[lado], f"{r}.{lado}")
        dom = _exacto(t["dominio"], r + ".dominio", ["original", "nuevo"])
        for lado in ("original", "nuevo"):
            if dom[lado] is not None:
                _opcion(dom[lado], f"{r}.dominio.{lado}", ["positivo", "negativo"])
    return lista


def _numero_finito(x, ruta, minimo=None, maximo=None, estricto=True):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or x != x or x in (float("inf"), float("-inf")):
        _fallo(ruta, "numero finito requerido")
    if minimo is not None and (x <= minimo if estricto else x < minimo):
        _fallo(ruta, f"debe ser mayor que {minimo}")
    if maximo is not None and x > maximo:
        _fallo(ruta, f"maximo {maximo}")
    return x


def _entero_rango(x, ruta, minimo, maximo):
    if isinstance(x, bool) or not isinstance(x, int) or not minimo <= x <= maximo:
        _fallo(ruta, f"entero entre {minimo} y {maximo} requerido")
    return x


ANALISIS_ESTUDIO = ("estructura", "sensibilidad", "valores", "asintotica", "escalas", "simetrias",
                    "estabilidad", "continuacion", "simulacion")


def leer_estudio(v, modelo, ruta="estudio"):
    """Opciones de la operacion `estudiar` (todas opcionales salvo lo que pida
    cada analisis)."""
    if v is None:
        return {}
    o = _claves(v, ruta, [], ["objetivos", "valores", "analisis", "umbralAsintotico", "cajaEstados",
                             "estabilidad", "continuacion", "simulacion"])
    if "objetivos" in o:
        for i, t in enumerate(_lista(o["objetivos"], ruta + ".objetivos")):
            _texto(t, f"{ruta}.objetivos[{i}]")
        if len(set(o["objetivos"])) != len(o["objetivos"]):
            _fallo(ruta + ".objetivos", "referencias duplicadas")
    ids = {s["id"] for s in modelo["simbolos"]}
    if "valores" in o:
        vistos = set()
        for i, x in enumerate(_lista(o["valores"], ruta + ".valores")):
            r = f"{ruta}.valores[{i}]"
            _claves(x, r, ["simboloId", "valor"], ["unidad"])
            _texto(x["simboloId"], r + ".simboloId")
            if x["simboloId"] in vistos:
                _fallo(r + ".simboloId", "valor duplicado")
            vistos.add(x["simboloId"])
            _numero_finito(x["valor"], r + ".valor")
            if "unidad" in x and x["unidad"] is not None:
                _texto(x["unidad"], r + ".unidad")
    if "analisis" in o:
        for i, a in enumerate(_lista(o["analisis"], ruta + ".analisis")):
            _opcion(a, f"{ruta}.analisis[{i}]", list(ANALISIS_ESTUDIO))
    if "umbralAsintotico" in o:
        _numero_finito(o["umbralAsintotico"], ruta + ".umbralAsintotico", 0, 0.5)
    if "cajaEstados" in o:
        _numero_finito(o["cajaEstados"], ruta + ".cajaEstados", 0, 1e6)
    if "estabilidad" in o:
        e = _claves(o["estabilidad"], ruta + ".estabilidad", [], ["kMax"])
        if "kMax" in e:
            _numero_finito(e["kMax"], ruta + ".estabilidad.kMax", 0, 1e6)
    if "continuacion" in o:
        rc = ruta + ".continuacion"
        c = _claves(o["continuacion"], rc, ["parametroId", "desde", "hasta"], ["unidad", "pasosMax"])
        if c["parametroId"] not in ids or next(s for s in modelo["simbolos"] if s["id"] == c["parametroId"])["rol"] not in ("parametro", "constante"):
            _fallo(rc + ".parametroId", "debe ser un parametro del modelo")
        _numero_finito(c["desde"], rc + ".desde")
        _numero_finito(c["hasta"], rc + ".hasta")
        if "unidad" in c and c["unidad"] is not None:
            _texto(c["unidad"], rc + ".unidad")
        if "pasosMax" in c:
            _entero_rango(c["pasosMax"], rc + ".pasosMax", 10, 5000)
    if "simulacion" in o:
        rs = ruta + ".simulacion"
        s = _claves(o["simulacion"], rs, [], ["tFinal", "tFinalSI", "muestras", "nodos", "rtol", "atol", "verificarMalla", "fronteras", "periodica"])
        if "tFinal" in s and "tFinalSI" in s:
            _fallo(rs, "declare tFinal (adimensional) o tFinalSI (segundos), no ambos")
        if "tFinal" in s:
            _numero_finito(s["tFinal"], rs + ".tFinal", 0, 1e9)
        if "tFinalSI" in s:
            _numero_finito(s["tFinalSI"], rs + ".tFinalSI", 0, 1e15)
        if "periodica" in s and not isinstance(s["periodica"], bool):
            _fallo(rs + ".periodica", "valor no admitido")
        if "muestras" in s:
            _entero_rango(s["muestras"], rs + ".muestras", 2, 201)
        if "nodos" in s:
            _entero_rango(s["nodos"], rs + ".nodos", 5, 801)
        for k in ("rtol", "atol"):
            if k in s:
                _numero_finito(s[k], f"{rs}.{k}", 0, 0.1)
        if "verificarMalla" in s and not isinstance(s["verificarMalla"], bool):
            _fallo(rs + ".verificarMalla", "valor no admitido")
        if "fronteras" in s:
            cids = {c["id"] for c in modelo["condiciones"]}
            for i, f in enumerate(_lista(s["fronteras"], rs + ".fronteras")):
                rf = f"{rs}.fronteras[{i}]"
                _exacto(f, rf, ["condicionId", "extremo"])
                if f["condicionId"] not in cids:
                    _fallo(rf + ".condicionId", "referencia inexistente")
                _opcion(f["extremo"], rf + ".extremo", ["desde", "hasta"])
    return o


def leer_opciones(v, ruta="opciones", modelo=None):
    """Opciones de la busqueda automatica (todas opcionales). `referencias` y
    `prioridadEscalas` son las de la forma automatica (mismo tipo que en la
    forma v2) y solo se publican en el vinculo si llegan."""
    defecto = {"presupuesto": 200, "maxObjetivos": None, "desde": 0, "gruposPi": True,
               "maxExponentePi": 4, "maxDenominadorPi": 4, "presentacion": "factorizada"}
    if v is None:
        return defecto
    o = _obj(v, ruta)
    if set(o) - set(defecto) - {"referencias", "prioridadEscalas"}:
        _fallo(ruta, "campos desconocidos")
    r = dict(defecto)
    r.update(o)
    if "referencias" in r:
        leer_referencias(r["referencias"], modelo, ruta + ".referencias")
    if "prioridadEscalas" in r:
        leer_prioridad(r["prioridadEscalas"], ruta + ".prioridadEscalas")
    for campo, minimo, maximo in (("presupuesto", 1, 2000), ("desde", 0, 10 ** 9), ("maxExponentePi", 1, 12), ("maxDenominadorPi", 1, 12)):
        x = r[campo]
        if isinstance(x, bool) or not isinstance(x, int) or not minimo <= x <= maximo:
            _fallo(f"{ruta}.{campo}", f"entero entre {minimo} y {maximo} requerido")
    if r["maxObjetivos"] is not None and (isinstance(r["maxObjetivos"], bool) or not isinstance(r["maxObjetivos"], int) or not 0 <= r["maxObjetivos"] <= 12):
        _fallo(f"{ruta}.maxObjetivos", "entero entre 0 y 12 requerido")
    if not isinstance(r["gruposPi"], bool):
        _fallo(f"{ruta}.gruposPi", "valor no admitido")
    _opcion(r["presentacion"], f"{ruta}.presentacion", ["factorizada", "desarrollada"])
    return r
