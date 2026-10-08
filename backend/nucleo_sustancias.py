"""
Catalogo de sustancias del proveedor: que hay, con que id y para que sirve.

POR QUE NO BASTA CON /componentes/buscar
----------------------------------------
Ese endpoint contesta "existe este compuesto y tiene grupos UNIFAC". Es
suficiente para montar un ELV y no lo es para montar una reaccion, por dos
motivos que el contrato del laboratorio senala:

**1. Una formula NO identifica una sustancia.**

No es una precaucion teorica. `search_chemical("C2H6O")` devuelve
**dimetil eter**, no etanol, y las dos tienen esa formula:

    etanol          CAS 64-17-5   Tb = 351.6 K
    dimetil eter    CAS 115-10-6  Tb = 248.4 K

Son 103 K de diferencia. Quien escriba la formula del etanol esperando
etanol recibe otra sustancia, y el calculo sale perfectamente bien para el
compuesto equivocado. Asi que este modulo dice COMO resolvio la consulta y,
cuando fue por formula, **lista los candidatos** en vez de elegir por su
cuenta.

**2. Tener grupos UNIFAC no basta para reaccionar.**

Hace falta ademas la entalpia de formacion, y hay sustancias que tienen lo
primero y no lo segundo. El diciclopentadieno es el caso que lo destapo:
UNIFAC si, Hfm no. Sirve para un ELV y no para un balance reactivo, y
enterarse de eso al resolver --cuando el calor de reaccion sale NaN-- es
tarde. Aqui se dice antes, por capacidad:

    elv         necesita grupos UNIFAC
    entalpia    necesita Cp y entalpia de vaporizacion
    reaccion    necesita ademas Hfm
    equilibrio  necesita ademas Gfm

LOS IDENTIFICADORES
-------------------
El id estable es el **CAS**. No el nombre comun, que tiene sinonimos y
cambia de un idioma a otro, ni la formula, que es ambigua. Se devuelven
tambien InChIKey y SMILES, que identifican la estructura sin ambiguedad y
sirven para que el cliente guarde la eleccion del usuario sin depender de
como la escribio.

Zona libre de pint: las unidades viajan declaradas en el campo de al lado.
"""

import math

from chemicals.identifiers import pubchem_db, search_chemical
from thermo.chemical import Chemical

# Capacidades que una sustancia puede tener, y de que propiedad dependen.
#
# Estan aqui, juntas, porque la pregunta del cliente no es "existe esta
# sustancia" sino "puedo hacer ESTO con ella", y la respuesta es distinta
# segun el esto.
CAPACIDADES = {
    "elv": {
        "descripcion": "Equilibrio liquido-vapor: puntos de burbuja y rocio, flash.",
        "necesita": ["grupos UNIFAC", "presion de saturacion"],
    },
    "entalpia": {
        "descripcion": "Entalpia sensible h(T, x) y balances de energia sin reaccion.",
        "necesita": ["Cp del liquido", "entalpia de vaporizacion"],
    },
    "reaccion": {
        "descripcion": "Balances con reaccion y calor de reaccion.",
        "necesita": ["entalpia de formacion (Hfm)"],
    },
    "equilibrio": {
        "descripcion": "Constante de equilibrio K(T) y dG de reaccion.",
        "necesita": ["energia de Gibbs de formacion (Gfm)"],
    },
}

# Tope del listado de candidatos de una formula ambigua. Un listado
# enorme no ayuda a elegir; si hay mas, se dice cuantos hay.
MAX_CANDIDATOS = 25


def _finito(valor):
    """True si el valor es un numero utilizable."""
    if valor is None:
        return False
    try:
        return math.isfinite(float(valor))
    except (TypeError, ValueError):
        return False


def _como_se_resolvio(consulta, metadata):
    """
    Por que camino se identifico la sustancia, y si ese camino es fiable.

    La distincion que importa: un CAS o un InChIKey identifican una
    sustancia y no hay nada que discutir. Una formula NO, y un nombre
    puede ser un sinonimo de otra cosa. El cliente tiene derecho a saber
    cual de los tres casos le toco.
    """
    texto = (consulta or "").strip()
    sin_espacios = texto.replace(" ", "")

    if metadata is None:
        return "no_encontrada", False

    # El CAS que devolvio, comparado con lo que se pidio.
    if sin_espacios == (metadata.CASs or ""):
        return "cas", True
    if texto.upper() == (metadata.InChI_key or "").upper():
        return "inchi_key", True
    if texto == (metadata.smiles or ""):
        return "smiles", True
    if texto.lower() in {(s or "").lower() for s in (metadata.synonyms or [])} \
            or texto.lower() == (metadata.common_name or "").lower() \
            or texto.lower() == (metadata.iupac_name or "").lower():
        return "nombre", True
    # Si coincide con la formula, se resolvio por formula: NO identifica.
    if sin_espacios.upper() == (metadata.formula or "").upper():
        return "formula", False
    return "otro", True


def _candidatos_de_formula(formula, excluir_cas=None):
    """
    Todas las sustancias de la base con esa formula.

    El indice de formulas de 'chemicals' asocia cada formula a UNA
    sustancia, asi que ya eligio por su cuenta y no sirve para esto. Se
    barre la base entera: son 76 000 entradas y cuesta 8 ms, que es
    baratisimo al lado de no poder avisar de una ambiguedad.
    """
    if not formula:
        return [], 0
    pubchem_db.finish_loading()
    objetivo = formula.upper()
    encontrados = []
    for metadata in pubchem_db.CAS_index.values():
        if (metadata.formula or "").upper() != objetivo:
            continue
        if excluir_cas and metadata.CASs == excluir_cas:
            continue
        encontrados.append(metadata)
    total = len(encontrados)
    # Ordenados por masa molar y nombre para que el listado sea estable
    # entre llamadas; el orden del diccionario no es informacion.
    encontrados.sort(key=lambda m: ((m.MW or 0.0), m.common_name or ""))
    return encontrados[:MAX_CANDIDATOS], total


def _resumen(metadata):
    """Lo que identifica una sustancia, sin cargar sus propiedades."""
    return {
        "id": metadata.CASs,
        "cas": metadata.CASs,
        "nombre": metadata.common_name,
        "nombre_iupac": metadata.iupac_name,
        "formula": metadata.formula,
        "masa_molar": metadata.MW,
        "unidad_masa_molar": "g/mol",
        "carga": metadata.charge,
        "smiles": metadata.smiles,
        "inchi_key": metadata.InChI_key,
    }


def _capacidades_de(quimico):
    """
    Que se puede hacer con esta sustancia, y por que no lo demas.

    Se comprueba la MISMA propiedad que el motor usa luego, no una
    parecida: `entalpias_formacion_liquido()` lee `Hfm`, asi que aqui se
    mira `Hfm`. Comprobar otra daria un apto que luego falla.
    """
    grupos = getattr(quimico, "UNIFAC_groups", None)
    tiene_unifac = bool(grupos)
    tiene_hf = _finito(getattr(quimico, "Hfm", None))
    tiene_gf = _finito(getattr(quimico, "Gfm", None))
    tiene_cp = _finito(getattr(quimico, "Cpl", None)) or _finito(
        getattr(quimico, "Cplm", None))
    tiene_hvap = _finito(getattr(quimico, "Hvap", None)) or _finito(
        getattr(quimico, "Hvapm", None))

    def entrada(disponible, faltan):
        return {
            "disponible": bool(disponible),
            "falta": list(faltan) if not disponible else [],
        }

    elv = entrada(tiene_unifac, ["grupos UNIFAC"] if not tiene_unifac else [])
    entalpia = entrada(
        tiene_unifac and tiene_cp,
        [m for m, hay in (("grupos UNIFAC", tiene_unifac),
                          ("Cp del liquido", tiene_cp)) if not hay],
    )
    reaccion = entrada(
        tiene_unifac and tiene_cp and tiene_hf,
        [m for m, hay in (("grupos UNIFAC", tiene_unifac),
                          ("Cp del liquido", tiene_cp),
                          ("entalpia de formacion (Hfm)", tiene_hf)) if not hay],
    )
    equilibrio = entrada(
        reaccion["disponible"] and tiene_gf,
        reaccion["falta"] + ([] if tiene_gf
                             else ["energia de Gibbs de formacion (Gfm)"]),
    )
    return {
        "elv": elv,
        "entalpia": entalpia,
        "reaccion": reaccion,
        "equilibrio": equilibrio,
    }


def _propiedades_de(quimico):
    """Las propiedades de referencia, con su unidad al lado."""
    def valor(v):
        return float(v) if _finito(v) else None

    return {
        "T_ebullicion": {"valor": valor(getattr(quimico, "Tb", None)),
                         "unidad": "K"},
        "T_fusion": {"valor": valor(getattr(quimico, "Tm", None)),
                     "unidad": "K"},
        "T_critica": {"valor": valor(getattr(quimico, "Tc", None)),
                      "unidad": "K"},
        "p_critica": {"valor": valor(getattr(quimico, "Pc", None)),
                      "unidad": "Pa"},
        "entalpia_formacion": {
            "valor": valor(getattr(quimico, "Hfm", None)),
            "unidad": "J/mol",
            "referencia": "estado estandar a 298.15 K",
            "nota": "Sin ella no hay calor de reaccion, y suponerla cero "
                    "convertiria una reaccion exotermica en un calentador neutro.",
        },
        "gibbs_formacion": {
            "valor": valor(getattr(quimico, "Gfm", None)),
            "unidad": "J/mol",
            "referencia": "estado estandar a 298.15 K",
            "nota": "Sin ella no hay K(T) ni dG de reaccion.",
        },
    }


def _atomos_de(quimico, metadata):
    """La composicion elemental, que es lo que valida una estequiometria."""
    atomos = getattr(quimico, "atoms", None) or {}
    return {
        "atomos": {str(e): int(n) for e, n in sorted(atomos.items())},
        "nota": "Es lo que valida una estequiometria: A @ nu tiene que ser cero. "
                "Sin composicion elemental no se puede comprobar que una reaccion "
                "sea una reaccion.",
    } if atomos else {
        "atomos": {},
        "nota": "'thermo' no da la composicion elemental de esta sustancia, asi "
                "que su estequiometria no se puede validar.",
    }


def buscar_sustancia(consulta):
    """
    Resuelve una consulta e informa de COMO la resolvio.

    Devuelve siempre `identificacion`, y cuando esa identificacion no
    identifica --el caso de la formula-- devuelve `candidatos` para que
    el cliente pregunte en vez de que el motor adivine.
    """
    texto = (consulta or "").strip()
    if not texto:
        return {
            "consulta": texto,
            "encontrada": False,
            "identificacion": "no_encontrada",
            "identificacion_fiable": False,
            "mensaje": "Escribe un nombre, una formula, un CAS, un SMILES o un "
                       "InChIKey.",
            "candidatos": [],
            "candidatos_totales": 0,
        }

    try:
        metadata = search_chemical(texto)
    except Exception:
        # Puede ser una formula que la base no reconozca tal cual pero de
        # la que SI haya sustancias. Merece intentarlo antes de rendirse.
        candidatos, total = _candidatos_de_formula(texto)
        return {
            "consulta": texto,
            "encontrada": False,
            "identificacion": "no_encontrada",
            "identificacion_fiable": False,
            "mensaje": (
                f"No se identifico ninguna sustancia para {texto!r}. Prueba con el "
                "nombre en ingles, el CAS, el SMILES o el InChIKey."
                + (f" Hay {total} sustancia(s) con esa formula; mira 'candidatos'."
                   if total else "")
            ),
            "candidatos": [_resumen(m) for m in candidatos],
            "candidatos_totales": total,
        }

    identificacion, fiable = _como_se_resolvio(texto, metadata)
    resultado = {
        "consulta": texto,
        "encontrada": True,
        "identificacion": identificacion,
        "identificacion_fiable": fiable,
        "sustancia": _resumen(metadata),
        "candidatos": [],
        "candidatos_totales": 0,
        "mensaje": None,
        "aviso": None,
    }

    # El caso que el contrato subraya. Se listan los OTROS candidatos: el
    # que ya se devolvio no es un candidato, es la respuesta que hay que
    # confirmar.
    if identificacion == "formula":
        candidatos, total = _candidatos_de_formula(
            metadata.formula, excluir_cas=metadata.CASs)
        resultado["candidatos"] = [_resumen(m) for m in candidatos]
        resultado["candidatos_totales"] = total
        resultado["aviso"] = (
            f"{texto!r} es una FORMULA, y una formula no identifica una sustancia. "
            f"Se resolvio a {metadata.common_name!r} (CAS {metadata.CASs})"
            + (f", pero hay {total} sustancia(s) mas con la misma formula."
               if total else ", y es la unica con esa formula en la base.")
            + " Confirma la eleccion con su CAS, su nombre o su SMILES antes de "
            "calcular: dos isomeros pueden diferir en cien grados de temperatura "
            "de ebullicion."
        )

    # Las propiedades, que exigen construir el Chemical.
    try:
        quimico = Chemical(metadata.common_name)
    except Exception as e:
        resultado["capacidades"] = None
        resultado["propiedades"] = None
        resultado["composicion_elemental"] = None
        resultado["mensaje"] = (
            f"Se identifico la sustancia pero no se pudieron cargar sus "
            f"propiedades: {e}"
        )
        return resultado

    resultado["capacidades"] = _capacidades_de(quimico)
    resultado["propiedades"] = _propiedades_de(quimico)
    resultado["composicion_elemental"] = _atomos_de(quimico, metadata)
    resultado["modelos_soportados"] = (
        ["unifac_raoult"] if resultado["capacidades"]["elv"]["disponible"] else []
    )
    resultado["fases"] = (
        ["liquido", "bifasico", "vapor"]
        if resultado["capacidades"]["elv"]["disponible"] else []
    )
    resultado["referencias"] = {
        "entalpia": "sensible_liquido_298.15K",
        "formacion": "estado estandar a 298.15 K (Hfm y Gfm de 'thermo')",
        "nota": "La referencia de entalpia del motor es SENSIBLE: no incluye las "
                "entalpias de formacion, asi que un balance con reaccion lleva el "
                "calor de reaccion explicito. Ver docs/15-laboratorio.md.",
    }

    if not resultado["capacidades"]["elv"]["disponible"]:
        resultado["mensaje"] = (
            f"{metadata.common_name!r} existe, pero no tiene grupos UNIFAC, y el "
            "modelo de este simulador es UNIFAC predictivo. No se puede usar en "
            "ningun calculo."
        )
    elif not resultado["capacidades"]["reaccion"]["disponible"]:
        faltan = ", ".join(resultado["capacidades"]["reaccion"]["falta"])
        resultado["mensaje"] = (
            f"{metadata.common_name!r} sirve para equilibrio liquido-vapor, pero "
            f"NO para reaccion: falta {faltan}. Enterarse de esto al resolver "
            "--cuando el calor de reaccion sale NaN-- es tarde."
        )
    return resultado


def catalogo_sustancias():
    """
    Que admite el catalogo y como se pregunta, sin preguntar nada.

    Declara las capacidades y de que propiedad depende cada una, para que
    el editor de especies del frontend pueda explicar por que una
    sustancia no sirve en vez de limitarse a no ofrecerla.
    """
    return {
        "identificadores_admitidos": [
            {"tipo": "cas", "identifica": True,
             "ejemplo": "64-17-5",
             "nota": "El id estable. Es lo que conviene guardar."},
            {"tipo": "nombre", "identifica": True,
             "ejemplo": "ethanol",
             "nota": "En ingles. Los sinonimos tambien valen."},
            {"tipo": "smiles", "identifica": True, "ejemplo": "CCO",
             "nota": "Identifica la estructura."},
            {"tipo": "inchi_key", "identifica": True,
             "ejemplo": "LFQSCWFLJHTTHZ-UHFFFAOYSA-N",
             "nota": "Identifica la estructura."},
            {"tipo": "formula", "identifica": False, "ejemplo": "C2H6O",
             "nota": "NO identifica una sustancia. 'C2H6O' resuelve a dimetil "
                     "eter y el etanol tiene la misma formula; hierven a 248 K y "
                     "a 352 K. La respuesta lo avisa y lista los candidatos."},
        ],
        "capacidades": dict(CAPACIDADES),
        "id_estable": "cas",
        "max_candidatos": MAX_CANDIDATOS,
        "modelos": ["unifac_raoult"],
        "referencias": {
            "entalpia": "sensible_liquido_298.15K",
            "formacion": "estado estandar a 298.15 K",
        },
        "nota": "Una sustancia puede tener grupos UNIFAC y no tener entalpia de "
                "formacion: sirve para un ELV y no para un balance reactivo. El "
                "diciclopentadieno es ese caso. Por eso las capacidades se "
                "declaran una por una y no como un unico 'apto'.",
    }
