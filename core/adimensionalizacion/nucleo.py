"""
Punto de entrada del nucleo: solicitud JSON -> resultado JSON.

Operaciones (formato 'adimensionalizacion.solicitud', version 1; el documento
puede ser v1 o v2, ver lector.leer_documento):
  - analizar:    A1 + inventario de terminos con identificadores estables.
  - transformar: A2 + A3 para una forma del documento.
Y la solicitud de exploracion del cliente ('solicitud_exploracion_adimensional',
version 1): evalua cada propuesta con el mismo algoritmo, elimina
duplicados demostrables y publica grupos Pi.

Un resultado se vincula al modelo (id + revision) y a TODAS las elecciones
de la forma (`vinculo.eleccion` + `vinculo.firma`). Un rechazo o un caso no
soportado nunca incluye ecuaciones: no hay resultado anterior que pueda
pasar por vigente.
"""

import copy
import hashlib
import json
import time

from . import algebra as A
from .dimensional import analizar_modelo
from .formulacion import formular, huella
from .grupos_pi import expresar_en_referencia, grupos_pi
from .lector import (ErrorContrato, leer_config_exploracion, leer_documento, leer_estudio, leer_forma, leer_modelo,
                     leer_opciones, leer_transformaciones)
from .racional import SistemaRacional
from .transformacion import Preparado, Rechazo

VERSION_NUCLEO = "1.0.0"
FORMATO_SOLICITUD = "adimensionalizacion.solicitud"
FORMATO_EXPLORACION = "solicitud_exploracion_adimensional"
FORMATO_RESULTADO = "adimensionalizacion.resultado"
LIMITE_SEGUNDOS_EXPLORACION = 60.0


def capacidades():
    return {
        "formato": "adimensionalizacion.capacidades", "version": 1, "nucleo": VERSION_NUCLEO,
        "contratoDocumento": 2, "versionesDocumento": [1, 2],
        "operaciones": ["analizar", "transformar", "adimensionalizar", "explorar", "estudiar"],
        "estudios": ["estructura", "sensibilidad", "valores", "asintotica", "escalas", "simetrias", "estabilidad", "continuacion", "simulacion"],
        "estados": ["correcto", "rechazado", "no_soportado", "requiere_datos"],
        "familias": [
            {"familia": "multiplicativa", "estado": "soportada", "forma": "v = S v'", "notas": "escalas libres, con unidad o por expresion; objetivos A3"},
            {"familia": "afin", "estado": "soportada", "forma": "v = R + S v'", "notas": "referencia R (puede llevar unidad con desplazamiento, p. ej. degC) y escala S; obligatoria para temperaturas absolutas con desplazamiento"},
            {"familia": "cociente_de_referencia", "estado": "soportada", "forma": "v = p v' con p un parametro", "notas": "caso multiplicativo con escala dada por expresion"},
            {"familia": "no_lineal_de_campo", "estado": "soportada", "forma": "c = g(u), u = h(c)", "notas": "g, h algebraicas (potencias, exp, log, trig); h(g(u)) = u y g(h(c)) = c se demuestran con los dominios declarados; derivadas desarrolladas con la regla de la cadena (terminos adicionales incluidos)"},
            {"familia": "no_lineal_de_coordenada", "estado": "soportada", "forma": "x = g(xi) por coordenada", "notas": "cartesiana y separable; d/dx = (1/g'(xi)) d/dxi anidado para ordenes superiores; jacobiano no nulo publicado como restriccion"},
            {"familia": "grupos_pi", "estado": "soportada", "notas": "espacio nulo racional, bases alternativas y cambio de base"},
            {"familia": "cambio_de_coordenadas_acoplado", "estado": "no_soportada", "notas": "x' = f(x, y), coordenadas curvilineas: requiere metrica"},
            {"familia": "escalas_dependientes_de_t_o_x", "estado": "no_soportada"},
            {"familia": "seleccion_automatica_de_mapas_no_lineales", "estado": "no_soportada", "notas": "la busqueda automatica usa mapas multiplicativos (o los declarados); no propone log/potencias por su cuenta"},
        ],
        "soportado": [
            "dimensiones racionales con inferencia exacta; estados compatible/incompatible/indeterminado",
            "unidades interpretadas con pint (bases L, M, T, I, Theta, N, J); temperatura con desplazamiento marcada como afin",
            "escalas multiplicativas constantes y positivas: libres, cantidad con unidad o expresion de parametros",
            "regla de la cadena en derivadas temporales/espaciales; gradiente, divergencia y laplaciano cartesianos",
            "operadores de varias coordenadas con escalas por coordenada (desarrollo en componentes cartesianas)",
            "funciones declaradas y coeficientes variables conservados sin desarrollar",
            "factor global por igualdad separado de las escalas",
            "objetivos monomiales |coeficiente| = 1 con signo exigido o conservado; rango y dependencia exactos",
            "escalas determinadas, relacionadas y libres (familias); objetivos dependientes, incompatibles y pendientes con responsables",
            "dominios y condiciones (inicial, dirichlet, flujo, mixta) transformados con la misma sustitucion",
            "certificado por sustitucion inversa de lo publicado",
            "grupos Pi por espacio nulo racional, bases alternativas con cotas y cambio de base verificado",
        ],
        "documentoV2": [
            "formas[].objetivos[].terminoId (termino opcional; si llegan ambos deben coincidir)",
            "condiciones[].ubicacion: {variableId, extremo: desde|hasta}",
            "funciones[].escala: {simboloId, funcionAdimensional} -> f(z) = S fhat(w), fhat(w) = f(s w)/S",
            "formas[].referencias: [{ecuacionId, terminoId}] -> factor global de otro termino",
            "formas[].prioridadEscalas: variables o constantes que se despejan primero",
            "formas[].transformaciones: mapas guardados en la forma",
        ],
        "noSoportado": [
            "escalas dependientes de t o x, cambios de coordenadas, coordenadas curvilineas",
            "objetivos no monomiales (sumas de coeficientes); quedan pendientes",
            "extraccion de una escala de una funcion declarada (D(c) = D* Dhat(u)) sin declaracion explicita (v2: funciones[].escala)",
            "ecuaciones vectoriales y gradientes de varias coordenadas fuera de una divergencia",
            "ubicacion precisa del extremo de una condicion en documentos v1 (v2: condiciones[].ubicacion)",
        ],
        "alcanceEquivalencia": "ver transformacion.ALCANCE_EQUIVALENCIA",
    }


def _firma(*partes):
    texto = json.dumps(partes, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return "sha256:" + hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _base(operacion, estado, vinculo=None, diagnosticos=None):
    return {"formato": FORMATO_RESULTADO, "version": 1, "operacion": operacion, "estado": estado,
            "nucleo": VERSION_NUCLEO, "vinculo": vinculo, "diagnosticos": diagnosticos or []}


def _eleccion(forma, transformaciones=()):
    r = {"escalas": copy.deepcopy(forma["escalas"]), "objetivos": copy.deepcopy(forma["objetivos"]),
         "presentacion": forma["presentacion"]}
    if transformaciones:
        r["transformaciones"] = copy.deepcopy(list(transformaciones))
    for campo in ("referencias", "prioridadEscalas"):
        if campo in forma:
            r[campo] = copy.deepcopy(forma[campo])
    return r


def _dimensional(an):
    return {"estado": an["estado"], "simbolos": an["simbolos"], "funciones": an["funciones"], "faltantes": an["faltantes"]}


def _forma_vacia(forma_id="analisis"):
    return {"id": forma_id, "nombre": "analisis", "padreId": None, "modeloRevision": 1, "escalas": [], "objetivos": [], "presentacion": "desarrollada"}


def _catalogo(prep):
    return [{"id": t["id"], "ecuacionId": t["ecuacionId"], "lado": t["lado"], "ruta": t["ruta"],
             "expresion": t["original"], "divididoEn": t["dividido_en"]} for t in prep.terminos.values()]


def procesar(solicitud):
    """Solicitud (dict) -> resultado (dict). Nunca lanza por datos invalidos.

    Un fallo inesperado del nucleo se publica como 'error_interno', sin
    ecuaciones: nunca se convierte en un resultado aparentemente valido."""
    try:
        return _procesar(solicitud)
    except Exception as e:  # red de seguridad: el contrato exige no lanzar
        operacion = solicitud.get("operacion") if isinstance(solicitud, dict) and isinstance(solicitud.get("operacion"), str) else "desconocida"
        return _base(operacion, "rechazado", diagnosticos=[{"ruta": "nucleo", "codigo": "error_interno", "severidad": "error",
                                                           "mensaje": f"fallo interno del nucleo ({type(e).__name__}); el resultado no es valido"}])


def _procesar(solicitud):
    if not isinstance(solicitud, dict):
        return _base("desconocida", "rechazado", diagnosticos=[{"ruta": "solicitud", "codigo": "contrato", "severidad": "error", "mensaje": "se esperaba un objeto"}])
    if solicitud.get("formato") == FORMATO_EXPLORACION:
        return _explorar(solicitud)
    operacion = solicitud.get("operacion") if isinstance(solicitud.get("operacion"), str) else "desconocida"
    try:
        obligatorias = {"formato", "version", "operacion", "documento"}
        opcionales = {"transformar": {"formaId", "transformaciones"}, "adimensionalizar": {"formaId", "transformaciones", "opciones"},
                      "estudiar": {"formaId", "transformaciones", "opciones", "estudio"}}.get(operacion, set())
        if not obligatorias <= set(solicitud) or set(solicitud) - obligatorias - opcionales:
            raise ErrorContrato("solicitud", "campos desconocidos o ausentes")
        if operacion == "transformar" and "formaId" not in solicitud:
            raise ErrorContrato("solicitud.formaId", "obligatorio en transformar")
        if solicitud["formato"] != FORMATO_SOLICITUD or solicitud["version"] != 1 or isinstance(solicitud["version"], bool):
            raise ErrorContrato("solicitud", "formato o version no admitidos")
        if operacion not in ("analizar", "transformar", "adimensionalizar", "estudiar"):
            raise ErrorContrato("solicitud.operacion", "operacion no admitida")
        doc = leer_documento(copy.deepcopy(solicitud["documento"]))
        transformaciones = leer_transformaciones(copy.deepcopy(solicitud.get("transformaciones", [])), doc["modelo"])
        opciones = leer_opciones(copy.deepcopy(solicitud.get("opciones")), modelo=doc["modelo"])
        estudio = leer_estudio(copy.deepcopy(solicitud.get("estudio")), doc["modelo"]) if operacion == "estudiar" else None
        if "formaId" in solicitud and not any(f["id"] == solicitud["formaId"] for f in doc["formas"]):
            raise ErrorContrato("formaId", "referencia inexistente")
        if "formaId" in solicitud:
            forma_pedida = next(f for f in doc["formas"] if f["id"] == solicitud["formaId"])
            if "transformaciones" in forma_pedida:
                # v2: la forma guarda sus mapas; no se admite una segunda fuente.
                if transformaciones:
                    raise ErrorContrato("transformaciones", "la forma ya declara sus transformaciones; no las repita en la solicitud")
                transformaciones = copy.deepcopy(forma_pedida["transformaciones"])
            for campo in ("referencias", "prioridadEscalas"):
                if campo in opciones:
                    raise ErrorContrato(f"opciones.{campo}", "con formaId se usan las de la forma")
    except ErrorContrato as e:
        return _base(operacion, "rechazado", diagnosticos=[{"ruta": e.ruta, "codigo": "contrato", "severidad": "error", "mensaje": e.mensaje}])
    modelo = doc["modelo"]
    an = analizar_modelo(modelo)
    if operacion == "analizar":
        vinculo = {"documentoId": doc["id"], "modeloId": modelo["id"], "modeloRevision": modelo["revision"], "firma": _firma(modelo)}
        r = _base("analizar", "correcto", vinculo, an["diagnosticos"])
        r["dimensional"] = _dimensional(an)
        try:
            r["terminos"] = _catalogo(Preparado(modelo, _forma_vacia(), an))
        except (A.ErrorAlgebraico, A.NoSoportado, Rechazo) as e:
            r["terminos"] = []
            r["diagnosticos"].append({"ruta": "modelo", "codigo": getattr(e, "codigo", "no_analizable"), "severidad": "aviso", "mensaje": getattr(e, "mensaje", str(e))})
        return r
    if operacion == "adimensionalizar":
        return _adimensionalizar(doc, an, solicitud.get("formaId"), transformaciones, opciones)
    if operacion == "estudiar":
        return _estudiar(doc, an, solicitud.get("formaId"), transformaciones, opciones, estudio or {})
    forma = next(f for f in doc["formas"] if f["id"] == solicitud["formaId"])
    eleccion = _eleccion(forma, transformaciones)
    vinculo = {"documentoId": doc["id"], "modeloId": modelo["id"], "modeloRevision": modelo["revision"], "formaId": forma["id"],
               "eleccion": eleccion, "firma": _firma(modelo, eleccion)}
    return _transformar(modelo, forma, an, vinculo, operacion="transformar", transformaciones=transformaciones)


def _bloqueo_dimensional(an):
    if an["estado"] == "incompatible" or an["errores_rango"]:
        return "rechazado", an["diagnosticos"]
    if an["estado"] == "indeterminado":
        return "requiere_datos", an["diagnosticos"] + [{"ruta": "modelo", "codigo": "dimensiones_pendientes", "severidad": "error", "simbolos": an["faltantes"],
                                                         "mensaje": "faltan dimensiones: declare las de " + ", ".join(an["faltantes"]) + " (el resto se infiere)"}]
    return None


def _objetivos_forma(prep, forma, prefijo=""):
    objetivos = []
    for o in forma["objetivos"]:
        tid, motivo, codigo = _termino_objetivo(prep, o)
        if o["accion"] == "conservar_grupo":
            objetivos.append({"id": prefijo + o["id"], "terminoId": tid, "modo": "conservar"})
            continue
        obj = {"id": prefijo + o["id"], "terminoId": tid, "motivo": motivo, "modo": "valor", "valor": o["valor"]}
        if codigo:
            obj["codigo"] = codigo
        objetivos.append(obj)
    return objetivos


def _termino_objetivo(prep, o):
    """(terminoId, motivo, codigo) del objetivo. v2: `terminoId` manda; si
    tambien llega `termino`, ambos deben designar el mismo coeficiente."""
    if "terminoId" not in o:
        tid, motivo = prep.buscar_termino(o["ecuacionId"], o["termino"])
        return tid, motivo, None
    tid = o["terminoId"]
    if tid not in prep.terminos:
        return None, _motivo_termino(prep, tid), "termino_no_encontrado"
    if "termino" in o:
        otro, _ = prep.buscar_termino(o["ecuacionId"], o["termino"])
        if otro != tid:
            return None, f"terminoId '{tid}' y la expresion del objetivo designan terminos distintos", "termino_contradictorio"
    return tid, None, None


def _transformar(modelo, forma, an, vinculo, operacion, transformaciones=()):
    bloqueo = _bloqueo_dimensional(an)
    if bloqueo:
        r = _base(operacion, bloqueo[0], vinculo, bloqueo[1])
        r["dimensional"] = _dimensional(an)
        return r
    if forma["modeloRevision"] != modelo["revision"]:
        r = _base(operacion, "rechazado", vinculo, [{"ruta": "forma.modeloRevision", "codigo": "forma_desactualizada", "severidad": "error",
                                                    "mensaje": "la forma se definio para otra revision del modelo; revisela antes de transformar"}])
        r["dimensional"] = _dimensional(an)
        return r
    try:
        prep = Preparado(modelo, forma, an, list(transformaciones))
        cuerpo = formular(prep, _objetivos_forma(prep, forma), forma["presentacion"])
    except Rechazo as e:
        r = _base(operacion, e.estado, vinculo, an["diagnosticos"] + e.diagnosticos)
        r["dimensional"] = _dimensional(an)
        return r
    except A.NoSoportado as e:
        r = _base(operacion, "no_soportado", vinculo, an["diagnosticos"] + [{"ruta": "modelo", "codigo": e.codigo, "severidad": "error", "mensaje": e.mensaje}])
        r["dimensional"] = _dimensional(an)
        return r
    except A.ErrorAlgebraico as e:
        r = _base(operacion, "rechazado", vinculo, an["diagnosticos"] + [{"ruta": "modelo", "codigo": e.codigo, "severidad": "error", "mensaje": e.mensaje}])
        r["dimensional"] = _dimensional(an)
        return r
    r = _base(operacion, "correcto", vinculo, an["diagnosticos"] + prep.diagnosticos)
    r["dimensional"] = _dimensional(an)
    r["terminos"] = _catalogo(prep)
    r.update(cuerpo)
    return r


def _explorar(sol):
    operacion = "explorar"
    try:
        claves = {"formato", "version", "documentoId", "modelo", "formaBase", "config", "terminos", "propuestas", "cobertura", "politica"}
        if set(sol) != claves:
            raise ErrorContrato("solicitud", "campos desconocidos o ausentes")
        if sol["version"] != 1 or isinstance(sol["version"], bool):
            raise ErrorContrato("solicitud.version", "version no admitida")
        modelo = leer_modelo(copy.deepcopy(sol["modelo"]))
        forma = copy.deepcopy(sol["formaBase"])
        ids_formas = {forma.get("id")} | ({forma["padreId"]} if isinstance(forma, dict) and isinstance(forma.get("padreId"), str) else set())
        leer_forma(forma, "formaBase", modelo, ids_formas)
        config = leer_config_exploracion(sol["config"], "config")
        propuestas = sol["propuestas"]
        if not isinstance(propuestas, list) or len(propuestas) > 200:
            raise ErrorContrato("propuestas", "lista requerida (maximo 200)")
        for i, p in enumerate(propuestas):
            if not isinstance(p, dict) or set(p) != {"id", "estado", "objetivos"} or not isinstance(p["objetivos"], list):
                raise ErrorContrato(f"propuestas[{i}]", "campos desconocidos o ausentes")
            for j, o in enumerate(p["objetivos"]):
                if not isinstance(o, dict) or set(o) != {"terminoId", "operacion", "conservarSigno"} or o["operacion"] != "normalizar_magnitud_coeficiente" or o["conservarSigno"] is not True:
                    raise ErrorContrato(f"propuestas[{i}].objetivos[{j}]", "objetivo no admitido")
    except ErrorContrato as e:
        return _base(operacion, "rechazado", diagnosticos=[{"ruta": e.ruta, "codigo": "contrato", "severidad": "error", "mensaje": e.mensaje}])
    forma["modeloRevision"] = forma["modeloRevision"]
    vinculo = {"documentoId": sol["documentoId"], "modeloId": modelo["id"], "modeloRevision": modelo["revision"], "formaId": forma["id"],
               "eleccion": _eleccion(forma), "firma": _firma(modelo, _eleccion(forma), config, propuestas)}
    an = analizar_modelo(modelo)
    bloqueo = _bloqueo_dimensional(an)
    if bloqueo:
        r = _base(operacion, bloqueo[0], vinculo, bloqueo[1])
        r["dimensional"] = _dimensional(an)
        return r
    try:
        prep = Preparado(modelo, forma, an)
    except Rechazo as e:
        r = _base(operacion, e.estado, vinculo, an["diagnosticos"] + e.diagnosticos)
        r["dimensional"] = _dimensional(an)
        return r
    except (A.NoSoportado, A.ErrorAlgebraico) as e:
        r = _base(operacion, "no_soportado" if isinstance(e, A.NoSoportado) else "rechazado", vinculo,
                  an["diagnosticos"] + [{"ruta": "modelo", "codigo": e.codigo, "severidad": "error", "mensaje": e.mensaje}])
        r["dimensional"] = _dimensional(an)
        return r
    base = _objetivos_forma(prep, forma, prefijo="base:")
    inicio = time.monotonic()
    formulaciones, por_huella, evaluaciones = [], {}, []
    siguiente = None
    for i, p in enumerate(propuestas):
        if time.monotonic() - inicio > LIMITE_SEGUNDOS_EXPLORACION:
            siguiente = i
            break
        objetivos = base + [{"id": f"{p['id']}:{k + 1}", "terminoId": o["terminoId"] if o["terminoId"] in prep.terminos else None,
                             "motivo": None if o["terminoId"] in prep.terminos else _motivo_termino(prep, o["terminoId"]),
                             "modo": "magnitud"} for k, o in enumerate(p["objetivos"])]
        try:
            f = formular(prep, objetivos, forma["presentacion"])
        except (A.NoSoportado, A.ErrorAlgebraico) as e:
            evaluaciones.append({"propuestaId": p["id"], "estado": "no_soportado", "motivo": e.mensaje})
            continue
        resumen = {}
        for est in f["objetivos"]:
            resumen[est["estado"]] = resumen.get(est["estado"], 0) + 1
        clave = huella(f)
        if clave in por_huella:
            fid = por_huella[clave]
            formulaciones[int(fid[1:]) - 1]["propuestas"].append(p["id"])
            evaluaciones.append({"propuestaId": p["id"], "estado": "duplicada", "formulacionId": fid, "objetivos": f["objetivos"], "resumen": resumen})
            continue
        fid = f"F{len(formulaciones) + 1}"
        por_huella[clave] = fid
        f["id"] = fid
        f["propuestas"] = [p["id"]]
        formulaciones.append(f)
        evaluaciones.append({"propuestaId": p["id"], "estado": "evaluada", "formulacionId": fid, "objetivos": f["objetivos"], "resumen": resumen})
    r = _base(operacion, "correcto", vinculo, an["diagnosticos"] + prep.diagnosticos)
    r["dimensional"] = _dimensional(an)
    r["terminos"] = _catalogo(prep)
    r["evaluaciones"] = evaluaciones
    r["formulaciones"] = formulaciones
    r["cobertura"] = {
        "propuestasRecibidas": len(propuestas), "propuestasEvaluadas": len(evaluaciones),
        "formulacionesDistintas": len(formulaciones),
        "duplicadas": sum(1 for e in evaluaciones if e["estado"] == "duplicada"),
        "noSoportadas": sum(1 for e in evaluaciones if e["estado"] == "no_soportado"),
        "agotadoTiempo": siguiente is not None, "siguientePropuesta": siguiente,
        "criterioDuplicado": "mismas igualdades, condiciones y dominios publicados en forma canonica (independiente del orden de terminos)",
        "nota": "las propuestas se evaluan tal como llegan; la cobertura de la familia de formulaciones no es exhaustiva",
    }
    if config["incluirGruposPi"]:
        pi, libres_ref = grupos_pi(modelo, an, config["maxExponentePi"], config["maxDenominadorPi"], presupuesto=config["presupuesto"])
        ref_ids = [g["id"] for g in pi["bases"][0]["grupos"]] if pi["bases"] else []
        for f in formulaciones:
            for g in f["grupos"]:
                if g["contieneEscalasLibres"] or not ref_ids:
                    continue
                P = A.canonica(g["definicion"], prep.ctx_t)
                e = expresar_en_referencia(P, pi["cantidades"], libres_ref, ref_ids)
                if e is not None:
                    g["enBasePi"] = e[0]
        r["gruposPi"] = pi
    return r


def _motivo_termino(prep, tid):
    if isinstance(tid, str) and any(t.startswith(tid + "#") for t in prep.terminos):
        return "el termino sintactico se desarrolla en varios terminos con coeficientes distintos; elija uno de " + ", ".join(t for t in prep.terminos if t.startswith(tid + "#"))
    return "termino no encontrado"


# --- Busqueda automatica ------------------------------------------------------

LIMITE_SUBCONJUNTOS = 200_000


def _forma_automatica(modelo, an, transformaciones, presentacion):
    """Transforma todas las variables presentes con escalas libres, salvo las
    que tienen un mapa declarado o una unidad con desplazamiento (que exige
    una referencia que el nucleo no inventa)."""
    usados = {s["id"] for s in an["simbolos"] if s["origen"] != "sin_uso"}
    ocupados = {s["id"] for s in modelo["simbolos"]} | {f["id"] for f in modelo["funciones"]}
    ocupados |= {t["nuevoId"] for t in transformaciones} | {c["id"] for t in transformaciones for c in t["constantes"]}
    declaradas = {t["variableId"] for t in transformaciones}
    escalas, avisos = [], []
    for s in modelo["simbolos"]:
        if s["rol"] not in ("campo", "tiempo", "coordenada") or s["id"] not in usados or s["id"] in declaradas:
            continue
        u = an["unidades"].get(s["id"])
        if u and u["afin"]:
            avisos.append({"ruta": f"simbolos.{s['id']}", "codigo": "requiere_referencia", "severidad": "aviso",
                           "mensaje": f"{s['id']} tiene una unidad con desplazamiento: declare un mapa afin con su referencia; se conserva dimensional"})
            continue
        nuevo, k = f"{s['id']}_ad", 2
        while nuevo in ocupados or f"{s['id']}_ref" in ocupados:
            nuevo, k = f"{s['id']}_ad{k}", k + 1
            if f"{s['id']}_ref" in ocupados:
                break
        ocupados.add(nuevo)
        escalas.append({"simboloId": s["id"], "transformar": True, "nuevoNombre": nuevo, "dimension": None, "valor": {"tipo": "libre"}})
    forma = {"id": "automatica", "nombre": "Busqueda automatica", "padreId": None, "modeloRevision": modelo["revision"],
             "escalas": escalas, "objetivos": [], "presentacion": presentacion}
    return forma, avisos


def _candidatos(prep):
    """Coeficientes efectivos que pueden normalizarse: un solo termino tras
    transformar, monomial, con alguna constante libre y signo conocido."""
    libres = {e["id"] for e in prep.escalas if e["tipo"] == "libre"}
    candidatos, excluidos = [], []
    for t in prep.terminos.values():
        if len(t["partes_F"]) != 1:
            excluidos.append({"terminoId": t["id"], "motivo": "se desarrolla en varios terminos"})
            continue
        u = t["partes_F"][0][1].monomio_unico()
        if u is None:
            excluidos.append({"terminoId": t["id"], "motivo": "coeficiente no monomial"})
            continue
        from .dimensional import dimension_de, limpiar
        dc = dimension_de(A.ast(t["partes_F"][0][1]), prep.dims_t, prep.funciones_dim)
        if dc is None or limpiar(dc):
            excluidos.append({"terminoId": t["id"], "motivo": "coeficiente dimensional (el nucleo del termino conserva dimensiones)"})
            continue
        fila, problema = {}, None
        for a, e in u[1]:
            if a[0] == "s" and a[1] in libres:
                fila[a[1]] = e
            elif a[0] == "s" and prep.ctx_t.signo(a[1]) == "cero":
                problema = f"{a[1]} declarado nulo"
            elif not A.atomo_positivo(a, prep.ctx_t):
                problema = f"signo no declarado de {a[1] if a[0] == 's' else 'un factor'}"
        if problema:
            excluidos.append({"terminoId": t["id"], "motivo": problema})
        elif not fila:
            excluidos.append({"terminoId": t["id"], "motivo": "no depende de ninguna escala libre (fijado por el factor global o por escalas dadas)"})
        else:
            candidatos.append((t["id"], fila))
    return candidatos, excluidos, libres


def _adimensionalizar(doc, an, forma_id, transformaciones, opciones):
    operacion = "adimensionalizar"
    modelo = doc["modelo"]
    avisos = []
    if forma_id is not None:
        forma = next(f for f in doc["formas"] if f["id"] == forma_id)
    else:
        forma, avisos = _forma_automatica(modelo, an, transformaciones, opciones["presentacion"])
        for campo in ("referencias", "prioridadEscalas"):
            if campo in opciones:
                forma[campo] = copy.deepcopy(opciones[campo])
    eleccion = _eleccion(forma, transformaciones)
    vinculo = {"documentoId": doc["id"], "modeloId": modelo["id"], "modeloRevision": modelo["revision"], "formaId": forma_id,
               "eleccion": eleccion, "opciones": opciones, "firma": _firma(modelo, eleccion, opciones)}
    bloqueo = _bloqueo_dimensional(an)
    if bloqueo:
        r = _base(operacion, bloqueo[0], vinculo, bloqueo[1])
        r["dimensional"] = _dimensional(an)
        return r
    if forma["modeloRevision"] != modelo["revision"]:
        return _base(operacion, "rechazado", vinculo, [{"ruta": "forma.modeloRevision", "codigo": "forma_desactualizada", "severidad": "error",
                                                        "mensaje": "la forma base se definio para otra revision del modelo"}])
    try:
        prep = Preparado(modelo, forma, an, list(transformaciones))
    except Rechazo as e:
        r = _base(operacion, e.estado, vinculo, an["diagnosticos"] + e.diagnosticos)
        r["dimensional"] = _dimensional(an)
        return r
    except (A.NoSoportado, A.ErrorAlgebraico) as e:
        r = _base(operacion, "no_soportado" if isinstance(e, A.NoSoportado) else "rechazado", vinculo,
                  an["diagnosticos"] + [{"ruta": "modelo", "codigo": e.codigo, "severidad": "error", "mensaje": e.mensaje}])
        r["dimensional"] = _dimensional(an)
        return r
    base = _objetivos_forma(prep, forma, prefijo="base:")
    candidatos, excluidos, libres = _candidatos(prep)
    maximo = len(libres) if opciones["maxObjetivos"] is None else min(opciones["maxObjetivos"], len(libres))
    # Solo subconjuntos independientes: un objetivo dependiente o incompatible
    # no se aplica, asi que su formulacion es la de un subconjunto
    # independiente que tambien se recorre. El recorrido es completo para
    # esta familia y su orden (tamano, orden del modelo) es reproducible.
    import itertools
    inicio = time.monotonic()
    formulaciones, por_huella, evaluaciones = [], {}, []
    indice, revisados, siguiente, agotado = -1, 0, None, None
    for k in range(0, maximo + 1):
        for comb in itertools.combinations(range(len(candidatos)), k):
            revisados += 1
            if revisados > LIMITE_SUBCONJUNTOS:
                agotado = "enumeracion"
                break
            sistema = SistemaRacional()
            if any(sistema.agregar(candidatos[i][1], {}, i)[0] != "independiente" for i in comb):
                continue
            indice += 1
            if indice < opciones["desde"]:
                continue
            if len(evaluaciones) >= opciones["presupuesto"]:
                siguiente, agotado = indice, "presupuesto"
                break
            if time.monotonic() - inicio > LIMITE_SEGUNDOS_EXPLORACION:
                siguiente, agotado = indice, "tiempo"
                break
            tids = [candidatos[i][0] for i in comb]
            objetivos = base + [{"id": f"auto:{tid}", "terminoId": tid, "modo": "magnitud"} for tid in tids]
            f = formular(prep, objetivos, forma["presentacion"])
            clave = huella(f)
            if clave in por_huella:
                fid = por_huella[clave]
                formulaciones[int(fid[1:]) - 1]["subconjuntos"].append(tids)
                evaluaciones.append({"indice": indice, "terminos": tids, "estado": "duplicada", "formulacionId": fid})
                continue
            fid = f"F{len(formulaciones) + 1}"
            por_huella[clave] = fid
            f["id"], f["objetivosAplicados"], f["subconjuntos"] = fid, tids, [tids]
            formulaciones.append(f)
            evaluaciones.append({"indice": indice, "terminos": tids, "estado": "evaluada", "formulacionId": fid})
        if agotado:
            break
    r = _base(operacion, "correcto", vinculo, an["diagnosticos"] + avisos + prep.diagnosticos)
    r["dimensional"] = _dimensional(an)
    r["terminos"] = _catalogo(prep)
    r["formaBase"] = forma
    r["formulaciones"] = formulaciones
    r["evaluaciones"] = evaluaciones
    r["cobertura"] = {
        "familia": "objetivos |coeficiente efectivo| = 1 con signo conservado, sobre los mapas de la forma base",
        "candidatos": [c[0] for c in candidatos], "excluidos": excluidos,
        "constantesLibres": sorted(libres), "maxObjetivos": maximo,
        "desde": opciones["desde"], "evaluados": len(evaluaciones),
        "formulacionesDistintas": len(formulaciones), "duplicadas": sum(1 for e in evaluaciones if e["estado"] == "duplicada"),
        "completa": agotado is None and opciones["desde"] == 0,
        "agotado": agotado, "siguiente": siguiente,
        "criterioDuplicado": "mismas igualdades, condiciones y dominios publicados en forma canonica",
        "nota": "completa para esta familia de objetivos; cada formulacion con escalas libres es una familia infinita parametrizada por ellas",
    }
    if opciones["gruposPi"]:
        pi, libres_ref = grupos_pi(modelo, an, opciones["maxExponentePi"], opciones["maxDenominadorPi"])
        ref_ids = [g["id"] for g in pi["bases"][0]["grupos"]] if pi["bases"] else []
        for f in formulaciones:
            for g in f["grupos"]:
                if g["contieneEscalasLibres"] or not ref_ids:
                    continue
                e = expresar_en_referencia(A.canonica(g["definicion"], prep.ctx_t), pi["cantidades"], libres_ref, ref_ids)
                if e is not None:
                    g["enBasePi"] = e[0]
        r["gruposPi"] = pi
    return r


# --- Estudio de una formulacion --------------------------------------------------

def _estudiar(doc, an, forma_id, transformaciones, opciones, estudio):
    """Formulacion (de una forma o de la busqueda automatica con los
    objetivos indicados) + analisis de estudio.py con los valores dados."""
    from .estudio import estudiar as estudiar_formulacion
    operacion = "estudiar"
    modelo = doc["modelo"]
    if forma_id is not None:
        forma = next(f for f in doc["formas"] if f["id"] == forma_id)
        avisos = []
    else:
        forma, avisos = _forma_automatica(modelo, an, transformaciones, opciones["presentacion"])
        for campo in ("referencias", "prioridadEscalas"):
            if campo in opciones:
                forma[campo] = copy.deepcopy(opciones[campo])
    eleccion = _eleccion(forma, transformaciones)
    vinculo = {"documentoId": doc["id"], "modeloId": modelo["id"], "modeloRevision": modelo["revision"], "formaId": forma_id,
               "eleccion": eleccion, "estudio": estudio, "firma": _firma(modelo, eleccion, opciones, estudio)}
    bloqueo = _bloqueo_dimensional(an)
    if bloqueo:
        r = _base(operacion, bloqueo[0], vinculo, bloqueo[1])
        r["dimensional"] = _dimensional(an)
        return r
    if forma["modeloRevision"] != modelo["revision"]:
        return _base(operacion, "rechazado", vinculo, [{"ruta": "forma.modeloRevision", "codigo": "forma_desactualizada", "severidad": "error",
                                                        "mensaje": "la forma se definio para otra revision del modelo"}])
    try:
        prep = Preparado(modelo, forma, an, list(transformaciones))
        # Mismos objetivos que la busqueda automatica: los de la forma (base:) y
        # los de la formulacion elegida (auto:), para reproducirla exactamente.
        objetivos = _objetivos_forma(prep, forma, prefijo="base:")
        for tid in estudio.get("objetivos", []):
            objetivos.append({"id": f"auto:{tid}", "terminoId": tid if tid in prep.terminos else None,
                              "motivo": None if tid in prep.terminos else _motivo_termino(prep, tid), "modo": "magnitud"})
        cuerpo = formular(prep, objetivos, forma["presentacion"])
    except Rechazo as e:
        r = _base(operacion, e.estado, vinculo, an["diagnosticos"] + e.diagnosticos)
        r["dimensional"] = _dimensional(an)
        return r
    except (A.NoSoportado, A.ErrorAlgebraico) as e:
        r = _base(operacion, "no_soportado" if isinstance(e, A.NoSoportado) else "rechazado", vinculo,
                  an["diagnosticos"] + [{"ruta": "modelo", "codigo": e.codigo, "severidad": "error", "mensaje": e.mensaje}])
        r["dimensional"] = _dimensional(an)
        return r
    resultados, diags = estudiar_formulacion(prep, cuerpo, estudio)
    errores = [d for d in diags if d["severidad"] == "error"]
    if errores:
        r = _base(operacion, "rechazado", vinculo, an["diagnosticos"] + diags)
        r["dimensional"] = _dimensional(an)
        return r
    r = _base(operacion, "correcto", vinculo, an["diagnosticos"] + avisos + prep.diagnosticos + diags)
    r["dimensional"] = _dimensional(an)
    r["terminos"] = _catalogo(prep)
    r["formaBase"] = forma
    r["formulacion"] = cuerpo
    r["estudio"] = resultados
    return r
