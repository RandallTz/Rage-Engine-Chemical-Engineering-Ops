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
# Ver backend/motor_ensamblaje.py y docs/MOTOR_ENSAMBLAJE_DINAMICO.md.
@router.get("/motor/ensamblajes/capacidades",
         summary="Alcance verificado del ensamblador dinamico independiente")
def motor_ensamblajes_capacidades(revision: int = 1):
    if revision == 2:
        from backend.motor_ensamblaje_v2 import capacidades_v2
        return capacidades_v2()
    return capacidades_motor_ensamblaje()


@router.post("/motor/ensamblajes/validar",
          summary="Ensamblaje, catalogo, recuento e inicializacion; no integra")
def motor_ensamblajes_validar(cuerpo: Any = Body(...)):
    return validar_motor_ensamblaje(cuerpo)[0]


@router.post("/motor/ensamblajes/resolver",
          summary="Validacion y, si esta lista, trayectoria de materia y energia")
def motor_ensamblajes_resolver(cuerpo: Any = Body(...)):
    return resolver_motor_ensamblaje(cuerpo)
