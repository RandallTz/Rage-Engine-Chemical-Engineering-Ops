"""
Diagnosticos estructurados: que le pasa a un calculo, en forma de datos.

El problema que resuelve. Hoy la respuesta de `/diagrama/resolver` dice lo
que pasa repartido en cuatro sitios y en tres formas distintas:
`incognitas_restantes` (una lista de nombres), `diagnostico` (que bloque
no pudo dispararse), `inconsistencias` (datos que no cumplen una ecuacion)
y `errores_bloque` (nombre -> texto del error). Un cliente que quiera
distinguir "faltan datos" de "esto es fisicamente imposible" no tiene
forma de hacerlo sin buscar subcadenas en castellano -- y esa
clasificacion se rompe la primera vez que alguien mejora la redaccion de
un mensaje.

Aqui se unifican en UNA lista de diagnosticos, cada uno con:

    codigo     identificador estable, en mayusculas, para ramificar
    categoria  datos / fisica / numerica / modelo / desconocido
    severidad  error / advertencia / informacion
    equipo     la operacion implicada, cuando se sabe
    variables  las claves del pool implicadas
    mensaje    el texto, para leer
    bloque     la ecuacion concreta, cuando aplica

LA CATEGORIA NUNCA SE DEDUCE DEL TEXTO. Viene de donde se genero el
problema: `incognitas_restantes` es falta de especificacion por
construccion, `redundancias` es redundancia por construccion,
`inconsistencias` es datos incompatibles por construccion, y los errores
de bloque traen su categoria desde la excepcion (ver core/errores.py). Lo
que no la trae se marca SIN_CLASIFICAR, que es una respuesta honesta;
adivinarla buscando "hirviendo" o "no convergio" en el mensaje acierta
hasta que alguien reescribe una frase y entonces falla en silencio.

SEVERIDAD, y por que no coincide con la categoria
-------------------------------------------------
No es lo mismo "esto esta mal" que "esto no se pudo calcular". Una
redundancia es una ADVERTENCIA: los datos de mas no son necesariamente
erroneos, se comprobaran por consistencia. Una incompatibilidad es un
ERROR: hay datos que se contradicen. Y una variable sin determinar es un
error del planteamiento, no del calculo.
"""

from core import errores as codigos

# Severidades, como cadenas estables.
ERROR = "error"
ADVERTENCIA = "advertencia"
INFORMACION = "informacion"


def _equipo_de(clave):
    """
    El elemento al que pertenece una variable del pool.

    Las claves son 'elemento.variable', asi que el elemento sale de
    partir por el primer punto. No distingue corriente de equipo -- eso lo
    sabe el cliente, que tiene el diagrama -- pero senalar 'col1' ya es
    mucho mejor que no senalar nada.
    """
    if not isinstance(clave, str) or "." not in clave:
        return None
    return clave.split(".", 1)[0]


def _agrupar_por_equipo(claves):
    """Las variables agrupadas por el elemento al que pertenecen."""
    grupos = {}
    for clave in claves:
        grupos.setdefault(_equipo_de(clave), []).append(clave)
    return grupos


def construir(resultado, conteo_gl=None):
    """
    La lista de diagnosticos a partir de lo que `resolver()` devolvio.

    `conteo_gl` es lo que devuelve `grados_de_libertad()`, para poder
    reportar las redundancias. Es opcional porque calcularlo cuesta una
    resolucion extra, y quien no la quiera recibe el resto igual.

    El orden no es alfabetico ni de descubrimiento: primero los errores,
    luego las advertencias, luego la informacion. Quien lea el primero ya
    tiene lo mas grave.
    """
    diagnosticos = []

    # ------------------------------------------------------------------
    # 1. Datos que se contradicen. Categoria por construccion: estos
    #    salen de verificar_consistencia, que compara un dato con lo que
    #    el resto de los datos implica.
    # ------------------------------------------------------------------
    for inc in resultado.get("inconsistencias") or []:
        variable = inc.get("variable")
        diagnosticos.append({
            "codigo": codigos.DATOS_INCOMPATIBLES,
            "categoria": "datos",
            "severidad": ERROR,
            "equipo": _equipo_de(variable),
            "variables": [variable] if variable else [],
            "bloque": inc.get("bloque"),
            "mensaje": inc.get("mensaje"),
            # Los dos numeros que no cuadran, para que el cliente pueda
            # mostrarlos sin volver a parsear el mensaje.
            "dado": inc.get("dado"),
            "implicado": inc.get("implicado"),
        })

    # ------------------------------------------------------------------
    # 2. Bloques que fallaron. La categoria viene de la EXCEPCION, no del
    #    texto: core/errores.py distingue fisica, numerica, datos y
    #    modelo, y lo que nadie clasifico llega como SIN_CLASIFICAR.
    # ------------------------------------------------------------------
    clasificados = resultado.get("errores_clasificados") or {}
    for nombre, mensaje in (resultado.get("errores_bloque") or {}).items():
        datos = clasificados.get(nombre) or {}
        categoria = datos.get("categoria", "desconocido")
        diagnosticos.append({
            "codigo": datos.get("codigo", codigos.SIN_CLASIFICAR),
            "categoria": categoria,
            # Un bloque que no pudo resolverse es un error, tambien cuando
            # la causa es fisica: el calculo no salio.
            "severidad": ERROR,
            "equipo": datos.get("equipo") or nombre.split(":")[0] or None,
            "variables": datos.get("variables") or [],
            "bloque": nombre,
            "mensaje": datos.get("mensaje") or mensaje,
            # Solo presente cuando no hubo categoria: es el unico dato
            # objetivo que queda, y ayuda a quien tenga que anadirla.
            "tipo_python": datos.get("tipo_python"),
        })

    # ------------------------------------------------------------------
    # 3. Variables sin determinar. Falta de especificacion por
    #    construccion: el solver recorrio todo y no pudo calcularlas.
    #
    #    Se agrupan POR ELEMENTO en vez de emitir una por variable. Con
    #    una columna a medias salen quince variables sueltas, y quince
    #    diagnosticos identicos no informan mas que uno que diga "a col1
    #    le faltan estas quince".
    # ------------------------------------------------------------------
    restantes = [str(v) for v in (resultado.get("incognitas_restantes") or [])]
    if restantes:
        for equipo, claves in sorted(_agrupar_por_equipo(restantes).items(),
                                     key=lambda par: (par[0] or "")):
            diagnosticos.append({
                "codigo": codigos.FALTA_ESPECIFICACION,
                "categoria": "datos",
                "severidad": ERROR,
                "equipo": equipo,
                "variables": sorted(claves),
                "bloque": None,
                "mensaje": (
                    f"{equipo}: quedan {len(claves)} variable(s) sin determinar "
                    f"({', '.join(sorted(claves)[:4])}"
                    + (", ..." if len(claves) > 4 else "") + ")."
                ),
            })

    # ------------------------------------------------------------------
    # 4. Bloques que no llegaron a dispararse, y QUE les faltaba. Esto no
    #    es un problema aparte del anterior: es su causa, y por eso va
    #    como informacion y no como error. Decir "falta s1.T" es util;
    #    decir ademas "por eso el balance de col1 no pudo arrancar" es lo
    #    que permite arreglarlo.
    # ------------------------------------------------------------------
    for informe in resultado.get("diagnostico") or []:
        if informe.get("puede_dispararse"):
            continue
        faltantes = [str(v) for v in (informe.get("faltantes_para_disparar") or [])]
        if not faltantes:
            continue
        diagnosticos.append({
            "codigo": codigos.FALTA_ESPECIFICACION,
            "categoria": "datos",
            "severidad": INFORMACION,
            "equipo": (informe.get("bloque") or "").split(":")[0] or None,
            "variables": faltantes,
            "bloque": informe.get("bloque"),
            "mensaje": (
                f"{informe.get('bloque')} no pudo dispararse: le faltan "
                f"{', '.join(faltantes[:4])}"
                + (", ..." if len(faltantes) > 4 else "") + "."
            ),
        })

    # ------------------------------------------------------------------
    # 5. Redundancias. ADVERTENCIA y no error: los datos de mas no son
    #    necesariamente erroneos -- se comprobaran por consistencia en vez
    #    de calcularse. Si ademas se contradicen, aparecen tambien en el
    #    punto 1, con severidad de error.
    # ------------------------------------------------------------------
    for red in ((conteo_gl or {}).get("redundancias") or []):
        dados = [str(v) for v in (red.get("dados") or [])]
        diagnosticos.append({
            "codigo": codigos.REDUNDANCIA,
            "categoria": "datos",
            "severidad": ADVERTENCIA,
            "equipo": _equipo_de(dados[0]) if dados else None,
            "variables": dados,
            "bloque": red.get("bloque"),
            "mensaje": (
                f"{red.get('bloque')}: sobran {red.get('sobran')} dato(s). "
                f"Se dieron {len(dados)} y la ecuacion necesita "
                f"{red.get('necesarios')}; los de mas se comprobaran por "
                "consistencia en vez de calcularse."
            ),
        })

    # ------------------------------------------------------------------
    # 6. El reciclo, cuando lo hay. Que convergio es informacion; que NO
    #    convergio es un fallo numerico, y distinguirlo importa: un
    #    reciclo sin converger da numeros que parecen resultados.
    # ------------------------------------------------------------------
    reciclo = resultado.get("reciclo")
    if reciclo:
        convergio = bool(reciclo.get("convergio"))
        diagnosticos.append({
            "codigo": (codigos.RECICLO_SIN_CONVERGENCIA if not convergio
                       else "INFO_RECICLO_CONVERGIO"),
            "categoria": "numerica" if not convergio else "informacion",
            "severidad": ERROR if not convergio else INFORMACION,
            "equipo": None,
            "variables": [str(c) for c in (reciclo.get("cortes") or [])],
            "bloque": None,
            "mensaje": (
                reciclo.get("mensaje")
                or (f"El reciclo convergio en {reciclo.get('ciclos')} ciclo(s) "
                    f"con error {reciclo.get('error')}."
                    if convergio else
                    f"El reciclo NO convergio en {reciclo.get('ciclos')} ciclo(s); "
                    f"ultimo error {reciclo.get('error')} frente a una tolerancia de "
                    f"{reciclo.get('tolerancia')}.")
            ),
        })

    # ------------------------------------------------------------------
    # 7. El tope de pasadas agotado. Es un fallo numerico y hay que
    #    decirlo: antes era indistinguible de "faltan datos", con
    #    completo=False, cero incidencias y GL=0. Se le decia al usuario
    #    que sus datos estaban bien y no se resolvia.
    # ------------------------------------------------------------------
    if resultado.get("agotado_el_tope"):
        diagnosticos.append({
            "codigo": codigos.SIN_CONVERGENCIA,
            "categoria": "numerica",
            "severidad": ERROR,
            "equipo": None,
            "variables": [],
            "bloque": None,
            "mensaje": (
                f"El bucle de resolucion agoto su tope de {resultado.get('iteraciones')} "
                "pasadas sin dejar de avanzar. El resultado puede estar a medias: no es "
                "lo mismo que faltar datos."
            ),
        })

    orden = {ERROR: 0, ADVERTENCIA: 1, INFORMACION: 2}
    diagnosticos.sort(key=lambda d: (orden.get(d["severidad"], 3), d["codigo"]))
    return diagnosticos


def resumen(diagnosticos):
    """
    El recuento por severidad y por categoria.

    Permite a un cliente decidir que mostrar sin recorrer la lista, y
    sobre todo permite contestar la pregunta del contrato: un resultado
    con `completo = true` y errores en la lista NO esta validado.
    """
    por_severidad = {}
    por_categoria = {}
    for d in diagnosticos:
        por_severidad[d["severidad"]] = por_severidad.get(d["severidad"], 0) + 1
        por_categoria[d["categoria"]] = por_categoria.get(d["categoria"], 0) + 1
    return {
        "total": len(diagnosticos),
        "por_severidad": por_severidad,
        "por_categoria": por_categoria,
        # La bandera que el contrato pide explicitamente. `completo` dice
        # que todas las variables quedaron determinadas; esto dice si hay
        # algo que invalide el resultado. No son lo mismo y confundirlos
        # es el fallo que el contrato quiere evitar.
        "hay_errores": any(d["severidad"] == ERROR for d in diagnosticos),
    }
