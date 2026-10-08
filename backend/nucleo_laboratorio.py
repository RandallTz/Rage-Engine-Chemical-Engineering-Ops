"""
Frontera de /laboratorio/*: de la peticion HTTP al ensamblador y vuelta.

Igual que `nucleo_diagrama.py`, aqui no hay fisica. Solo tres cosas:

  1. pasar la peticion de Pydantic a diccionarios planos, que es lo que
     `core/laboratorio.py` entiende (el nucleo no importa Pydantic: si
     lo hiciera, no se podria usar desde un script ni desde una prueba
     sin levantar la API)
  2. normalizar las entradas y sacar su huella, para que el resultado sea
     reproducible y auditable (ver docs/14-trazabilidad.md)
  3. envolver el resultado con `calculo`, `modelo_id`, el resumen de
     diagnosticos y las capacidades

NINGUNA EXCEPCION SE ESCAPA
---------------------------
El nucleo ya convierte lo que sabe en diagnosticos. Lo que no sabe -- un
fallo inesperado del proveedor, un desbordamiento -- se captura aqui y
sale tambien como diagnostico, con `estado: "invalido"` y codigo
SIN_CLASIFICAR. Un 500 con un traceback no le sirve a la interfaz: no
puede senalar ninguna pieza con eso, y el usuario ve una pantalla
rota en vez de un problema con nombre.
"""

from core import errores as codigos
from core import laboratorio as lab
from backend import trazabilidad


def _a_diccionario(request):
    """
    La peticion como diccionarios planos, con solo los campos que el
    ensamblador usa.

    Se construye campo por campo y no con un `model_dump()` entero por el
    mismo motivo que la huella del diagrama (ver
    `trazabilidad.entradas_normalizadas`): un volcado automatico arrastra
    cualquier campo nuevo que alguien anada al esquema, incluidos los que
    el motor ignora a proposito -- `relaciones`, `estado`, `solver` -- y
    entonces el nucleo recibe cosas que no le corresponde interpretar.
    """
    return {
        "version": request.version,
        "componentes": list(request.componentes),
        "modelo_termodinamico": request.modelo_termodinamico,
        "referencia_entalpia": request.referencia_entalpia,
        "presion_sistema": (
            {"valor": request.presion_sistema.valor,
             "unidad": request.presion_sistema.unidad}
            if request.presion_sistema is not None else None
        ),
        "bloques": [
            {"id": b.id, "tipo": b.tipo, "nombre": b.nombre,
             # Las claves con valor None se descartan: una clave ausente y
             # una clave en null son lo mismo -- "no hay dato" -- y
             # conservarla obligaria al nucleo a distinguir dos formas de
             # la misma nada.
             "datos": ({k: v for k, v in b.datos.items() if v is not None}
                       if b.datos else None)}
            for b in request.bloques
        ],
        "conexiones": [
            {"id": c.id, "desde": c.desde, "hacia": c.hacia, "tipo": c.tipo}
            for c in request.conexiones
        ],
        "supuestos": dict(request.supuestos or {}),
        "especificaciones": [
            {"bloque_id": e.bloque_id, "variable": e.variable,
             "valor": e.valor, "unidad": e.unidad}
            for e in request.especificaciones
        ],
        "reacciones": [
            {
                "id": r.id,
                "bloque_id": r.bloque_id,
                "nu": list(r.nu),
                # Las tasas llegan como objetos; el nucleo las convierte y
                # decide la base a partir de la unidad.
                **{
                    campo: ({"valor": dato.valor, "unidad": dato.unidad}
                            if dato is not None else None)
                    for campo, dato in (
                        ("tasa", r.tasa), ("tasa_directa", r.tasa_directa),
                        ("tasa_inversa", r.tasa_inversa), ("tasa_neta", r.tasa_neta),
                    )
                },
                # Las leyes de velocidad, cuando la tasa se calcula.
                **{campo: (ley.model_dump(exclude_none=True)
                           if ley is not None else None)
                   for campo, ley in (("ley_directa", r.ley_directa),
                                      ("ley_inversa", r.ley_inversa))},
                # Se pasan a proposito, para que el nucleo los RECHACE con
                # un diagnostico con nombre. Filtrarlos aqui los ignoraria
                # en silencio, y el cliente creeria que se usan.
                "cinetica": r.cinetica,
                "A": r.A,
                "Ea": r.Ea,
            }
            for r in request.reacciones
        ],
    }


def entradas_normalizadas(peticion):
    """
    Las entradas que definen el MONTAJE, en forma canonica.

    Entra lo que cambia el sistema; no entra lo que no. Las relaciones en
    LaTeX quedan fuera porque son descriptivas: si el frontend mejora la
    redaccion de una formula, el montaje es el mismo y la huella no debe
    moverse.

    Bloques, conexiones y especificaciones se ORDENAN por id. El orden en
    que el cliente dibuje las piezas no cambia el sistema -- el orden de
    resolucion lo decide el motor recorriendo el grafo desde la
    alimentacion -- asi que tampoco debe cambiar la huella.
    """
    canonico = trazabilidad.canonico
    bloques = sorted(
        ({"id": b["id"], "tipo": b["tipo"],
          "datos": canonico(b["datos"]) if b["datos"] else None}
         for b in peticion["bloques"]),
        key=lambda b: b["id"],
    )
    conexiones = sorted(
        ({"id": c["id"], "desde": c["desde"], "hacia": c["hacia"]}
         for c in peticion["conexiones"]),
        key=lambda c: c["id"],
    )
    especificaciones = sorted(
        ({"bloque_id": e["bloque_id"], "variable": e["variable"],
          "valor": canonico(e["valor"]), "unidad": e["unidad"]}
         for e in peticion["especificaciones"]),
        key=lambda e: (e["bloque_id"], e["variable"]),
    )
    # Las reacciones SI entran en la huella: cambiar un coeficiente
    # estequiometrico o una tasa cambia el sistema. Se ordenan por id por
    # el mismo motivo que los bloques -- el orden en que el cliente las
    # mande no cambia la quimica -- pero `nu` conserva el suyo, que es el
    # de los componentes.
    reacciones = sorted(
        (
            {
                "id": r["id"], "bloque_id": r["bloque_id"],
                "nu": canonico(list(r["nu"])),
                **{campo: canonico(r.get(campo))
                   for campo in ("tasa", "tasa_directa", "tasa_inversa",
                                 "tasa_neta", "ley_directa", "ley_inversa")},
            }
            for r in peticion.get("reacciones") or []
        ),
        key=lambda r: r["id"],
    )
    return {
        # El orden de los componentes SI importa: define cual es x.
        "componentes": list(peticion["componentes"]),
        "modelo": peticion.get("modelo_termodinamico") or lab.MODELO_POR_OMISION,
        "referencia": peticion.get("referencia_entalpia") or lab.REFERENCIA_POR_OMISION,
        "presion_sistema": canonico(peticion.get("presion_sistema")),
        "bloques": bloques,
        "conexiones": conexiones,
        "supuestos": canonico(peticion.get("supuestos")),
        "especificaciones": especificaciones,
        "reacciones": reacciones,
        # El nombre del bloque NO entra: cambiar la etiqueta de una pieza
        # no cambia el sistema. Tampoco entran las relaciones en LaTeX.
    }


def _resumen(diagnosticos):
    """
    El recuento por severidad y categoria, con la bandera que importa.

    `hay_errores` separa "se calculo" de "el resultado es valido", igual
    que en /diagrama/resolver. Aqui hace falta por el mismo motivo: un
    montaje puede dar estado 'resuelto' y traer advertencias, y el cliente
    tiene que poder decidir si ensena los numeros sin recorrer la lista.
    """
    por_severidad, por_categoria = {}, {}
    for d in diagnosticos:
        por_severidad[d["severidad"]] = por_severidad.get(d["severidad"], 0) + 1
        por_categoria[d["categoria"]] = por_categoria.get(d["categoria"], 0) + 1
    return {
        "total": len(diagnosticos),
        "por_severidad": por_severidad,
        "por_categoria": por_categoria,
        "hay_errores": any(d["severidad"] == "error" for d in diagnosticos),
    }


def _envolver(resultado, calculo, modelo_id):
    resultado = dict(resultado)
    resultado["modelo_id"] = modelo_id
    resultado["calculo"] = calculo
    resultado["resumen_diagnosticos"] = _resumen(resultado["diagnosticos"])
    resultado["capacidades"] = lab.capacidades()
    return resultado


def _ejecutar(request, accion):
    """
    El camino comun de /validar y /resolver.

    El bloque `calculo` se construye ANTES de llamar al nucleo, igual que
    en el diagrama: asi el instante es el del inicio y la huella esta
    tomada sobre lo que de verdad se va a resolver.
    """
    peticion = _a_diccionario(request)
    entradas = entradas_normalizadas(peticion)
    modelo_id = trazabilidad.huella(entradas)
    calculo = trazabilidad.construir_calculo_desde(
        entradas,
        modelo_termodinamico=peticion.get("modelo_termodinamico")
        or lab.MODELO_POR_OMISION,
    )

    try:
        resultado = (lab.resolver(peticion) if accion == "resolver"
                     else lab.validar(peticion))
    except Exception as e:
        # El nucleo ya convierte en diagnostico lo que sabe clasificar.
        # Esto es la red para lo que no: sale como diagnostico y no como
        # 500, porque un traceback no permite senalar ninguna pieza.
        clasificado = codigos.clasificar(e)
        resultado = {
            "schema_version": lab.SCHEMA_VERSION,
            "estado": "invalido",
            "componentes": list(peticion["componentes"]),
            "modelo_termodinamico": peticion.get("modelo_termodinamico")
            or lab.MODELO_POR_OMISION,
            "referencia_entalpia": peticion.get("referencia_entalpia")
            or lab.REFERENCIA_POR_OMISION,
            "presion_sistema": lab.PRESION_POR_OMISION,
            "variables": [],
            "ecuaciones": [],
            "diagnosticos": [{
                "codigo": clasificado.get("codigo", codigos.SIN_CLASIFICAR),
                "severidad": "error",
                "categoria": clasificado.get("categoria", "desconocido"),
                "mensaje": f"El montaje no se pudo procesar: {e}",
                "accion_sugerida": "Revisa la peticion. Si el montaje parece "
                                   "correcto, es un fallo del motor y conviene "
                                   "informarlo con el modelo_id.",
                "bloque_ids": [], "conexion_ids": [], "variable_ids": [],
            }],
            "analisis": {
                "variables_totales": 0, "impuestas": 0, "incognitas": 0,
                "ecuaciones_independientes": 0, "grados_libertad": 0,
                "rango": None,
                "rango_origen": "no se determina: el montaje no llego a ensamblarse.",
                "metodo": None, "alcance": None, "orden_resolucion": [],
                "no_contadas": {}, "nota_no_contadas": "",
            },
            "convergencia": None,
            "estados_por_bloque": {},
            "reacciones": [],
            "fuentes_por_volumen": {},
            "conservacion": {},
        }

    return _envolver(resultado, calculo, modelo_id)


def validar_laboratorio(request):
    """Valida el montaje sin ejecutar el solver."""
    return _ejecutar(request, "validar")


def resolver_laboratorio(request):
    """Valida y resuelve."""
    return _ejecutar(request, "resolver")


def calcular_laboratorio(request):
    """
    El endpoint unico con accion explicita, que el contrato permite.

    Por omision valida, no resuelve: el lado seguro es el que no gasta
    tiempo de calculo si el cliente se olvido de decir que queria.
    """
    return _ejecutar(request, "resolver" if request.accion == "resolver" else "validar")


def capacidades_laboratorio():
    """Las capacidades solas, sin mandar un montaje."""
    return {
        "schema_version": lab.SCHEMA_VERSION,
        "motor": {
            "version": trazabilidad.VERSION_MOTOR,
            "commit": trazabilidad._commit_git(),
        },
        "capacidades": lab.capacidades(),
    }
