"""
Busqueda y validacion de componentes -- el paso previo tipo ASPEN:
primero defines con que compuestos trabajas, despues armas el flowsheet.

Dos validaciones DISTINTAS, y la segunda es la que de verdad importa:
  1. Que el nombre se resuelva a un compuesto real (search_chemical
     acepta nombre comun, formula o CAS).
  2. Que ese compuesto tenga GRUPOS UNIFAC. Hay compuestos perfectamente
     reales (amoniaco, CO2, N2, H2) que existen en la base de datos pero
     cuyo UNIFAC_groups es None -- con el modelo actual (Raoult
     modificada + UNIFAC) no se pueden usar, y sin este chequeo el
     fallo aparece mucho despues, enterrado en un calculo de gamma.
"""
from chemicals.identifiers import search_chemical
from thermo.chemical import Chemical

from backend.schemas import ComponenteInfo, ModeloTermodinamico

# Unico modelo implementado hoy. Se expone como lista (en vez de
# hardcodearlo en la UI) para que agregar NRTL/Peng-Robinson despues sea
# agregar una entrada aqui y una rama en ProveedorTermodinamico, sin
# tocar el frontend.
MODELOS = [
    ModeloTermodinamico(
        id="unifac_raoult",
        nombre="Raoult modificada + UNIFAC",
        descripcion=(
            "gamma_i predictivo por contribucion de grupos (UNIFAC), presiones de saturacion de "
            "'thermo'. No necesita datos binarios ajustados, pero exige que todos los componentes "
            "tengan grupos UNIFAC definidos. Fase vapor ideal."
        ),
        disponible=True,
    ),
]


def buscar_componente(consulta: str) -> ComponenteInfo:
    consulta = consulta.strip()
    if not consulta:
        return ComponenteInfo(consulta=consulta, encontrado=False, mensaje="Escribe un nombre, fórmula o CAS.")

    try:
        metadata = search_chemical(consulta)
    except Exception:
        return ComponenteInfo(
            consulta=consulta,
            encontrado=False,
            mensaje=f"No se encontró ningún compuesto para '{consulta}'. Prueba con el nombre en inglés, la fórmula o el CAS.",
        )

    nombre = metadata.common_name
    try:
        quimico = Chemical(nombre)
        grupos = quimico.UNIFAC_groups
        Tb = quimico.Tb
    except Exception as e:
        return ComponenteInfo(
            consulta=consulta,
            encontrado=True,
            nombre=nombre,
            formula=metadata.formula,
            MW=metadata.MW,
            CAS=metadata.CASs,
            apto_unifac=False,
            mensaje=f"Se identificó el compuesto pero no se pudieron cargar sus propiedades: {e}",
        )

    apto = grupos is not None and len(grupos) > 0
    return ComponenteInfo(
        consulta=consulta,
        encontrado=True,
        nombre=nombre,
        formula=metadata.formula,
        MW=metadata.MW,
        CAS=metadata.CASs,
        Tb=Tb,
        apto_unifac=apto,
        mensaje=None if apto else (
            "Este compuesto no tiene grupos UNIFAC definidos, así que no se puede usar con el modelo "
            "Raoult modificada + UNIFAC (es el único implementado hoy)."
        ),
    )
