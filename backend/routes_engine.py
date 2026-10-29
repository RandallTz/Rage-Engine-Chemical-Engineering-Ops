"""Model Engine routes (/motor/*), moved unchanged from backend/main.py (cleanup phase 3).

Thermodynamics, catalog, binary diagrams, the water phase diagram and the dynamic assembly.
The Model workbench routes stay in backend/api_modelo.py.
"""
from fastapi import APIRouter
from typing import Any
from fastapi import Body
from backend.motor_termodinamica import (
    capacidades as capacidades_motor_termodinamica,
    evaluar as evaluar_motor_termodinamica,
)
from backend.motor_ensamblaje import (
    _es_revision_2,
    capacidades as capacidades_motor_ensamblaje,
    validar as validar_motor_ensamblaje,
    resolver as resolver_motor_ensamblaje,
)

router = APIRouter()


# --- Motor independiente: termodinamica (contrato revision 1) ---------------
# Ver backend/motor_termodinamica.py y docs/MOTOR_TERMODINAMICA_H0_H1.md.
@router.get("/motor/termodinamica/capacidades",
         summary="Modelos termodinamicos publicados para /motor, con dominio y referencia")
def motor_termodinamica_capacidades():
    return capacidades_motor_termodinamica()


@router.get("/motor/catalogo",
         summary="Sustancias registradas, datos puros con procedencia y admision por paquete y operacion")
def motor_catalogo():
    """F2.1-F2.3: ver backend/motor_catalogo.py y docs/contratos/contratoCatalogo.ts."""
    from backend.motor_catalogo import catalogo_publico
    return catalogo_publico()


@router.get("/motor/termodinamica/diagramas/capacidades",
         summary="Trazado de diagramas binarios T-xy / P-xy: paquetes, perfiles y limites")
def motor_diagramas_capacidades():
    from backend.motor_diagramas import capacidades
    return capacidades()


@router.post("/motor/termodinamica/diagramas/trazar",
          summary="Un corte T-xy o P-xy de un binario con el paquete declarado; sin efectos")
def motor_diagramas_trazar(cuerpo: Any = Body(...)):
    """Todo rechazo conocido es una respuesta del protocolo con diagnosticos y ruta, no un 422."""
    from backend.motor_diagramas import trazar
    return trazar(cuerpo)


@router.get("/motor/termodinamica/diagramas/multicomponent/capabilities",
         summary="Ternary liquid-liquid diagrams and composition-line slices: operations, profiles and packages")
def multicomponent_diagram_capabilities():
    from backend.multicomponent_diagrams import capabilities
    return capabilities()


@router.post("/motor/termodinamica/diagramas/ternary-liquid-liquid",
          summary="Ternary liquid-liquid diagram at fixed T and P with the declared package; no side effects")
def ternary_liquid_liquid_diagram(body: Any = Body(...)):
    """Every known rejection is a protocol response with diagnostics and a path, not a 422."""
    from backend.multicomponent_diagrams import ternary_liquid_liquid
    return ternary_liquid_liquid(body)


@router.post("/motor/termodinamica/diagramas/composition-line",
          summary="Equilibrium along a composition line at fixed T and P, every species kept; no side effects")
def composition_line_diagram(body: Any = Body(...)):
    """Every known rejection is a protocol response with diagnostics and a path, not a 422."""
    from backend.multicomponent_diagrams import composition_line
    return composition_line(body)


@router.get("/motor/termodinamica/diagrama",
         summary="Diagrama P-T del cierre de un modelo con fases solidas (curvas y triple); sin efectos")
def motor_termodinamica_diagrama(modelo: str = "agua-iapws95-hielo-ih", version: str = "1"):
    from backend.motor_hielo import diagrama
    return diagrama(modelo, version)


@router.post("/motor/termodinamica/evaluar",
          summary="Estado de equilibrio estable de una declaracion; sin efectos")
def motor_termodinamica_evaluar(cuerpo: Any = Body(...)):
    """
    Recibe el JSON sin modelo Pydantic a proposito: todo rechazo conocido
    (campo de mas, unidad, dato null, region no soportada) sale como
    respuesta del contrato con diagnosticos y evaluacion null, no como 422.
    """
    return evaluar_motor_termodinamica(cuerpo)

# --- Motor independiente: ensamblaje dinamico (protocolo de ensamblaje, revision 1) ---
# Revision 2 uses the common adapter with explicit server-selected native fallback.
# Revision 1 retired (dec-r5-legacy-v1): backend/motor_ensamblaje.py
# answers it with MOTOR_ENS_REVISION_RETIRADA; docs/engine/dynamic-assembly.md.
@router.get("/motor/ensamblajes/capacidades",
         summary="Alcance verificado del ensamblador dinamico independiente")
def motor_ensamblajes_capacidades(revision: int = 1):
    if revision == 2:
        from backend.v2_dispatch import capabilities
        return capabilities()
    return capacidades_motor_ensamblaje()


@router.post("/motor/ensamblajes/validar",
          summary="Ensamblaje, catalogo, recuento e inicializacion; no integra")
def motor_ensamblajes_validar(cuerpo: Any = Body(...)):
    if _es_revision_2(cuerpo):
        from backend.v2_dispatch import validate
        return validate(cuerpo)
    return validar_motor_ensamblaje(cuerpo)[0]


@router.post("/motor/ensamblajes/resolver",
          summary="Validacion y, si esta lista, trayectoria de materia y energia")
def motor_ensamblajes_resolver(cuerpo: Any = Body(...)):
    if _es_revision_2(cuerpo):
        from backend.v2_dispatch import resolve
        return resolve(cuerpo)
    return resolver_motor_ensamblaje(cuerpo)
