"""
Puente entre la API web (schemas.py, JSON/HTTP) y el nucleo Python
(core/, thermodynamics/). No repite logica de calculo -- solo construye
los objetos correctos segun el metodo pedido y llama a
ColumnaDestilacion.resolver_desde_feed (core/columna_destilacion.py).
"""
import numpy as np

from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.elv import CalculadoraELV
from core.mccabe_thiele import EvaluadorMcCabeThiele, SolucionadorMcCabeThiele
from core.ponchon_savarit import EvaluadorPonchonSavarit, SolucionadorPonchonSavarit
from core.fug import AnalizadorFUG
from core.columna_destilacion import ColumnaDestilacion
from core.corriente import Corriente

from backend.schemas import (
    ResolverColumnaRequest, ResolverColumnaResponse, CorrienteSalida, DiagramaMcCabeThiele,
)

# Que parametros de 'request.parametros' son variables de POOL (van a
# self.resolver()) vs parametros de CONSTRUCCION (van al evaluador o al
# AnalizadorFUG). 'q' es el ejemplo real de la diferencia: para
# mccabe_thiele es una variable de pool genuina (bloque_mccabe_thiele la
# usa); para ponchon_savarit/fug esta FIJA de antemano (se pasa al
# construir el solver/analizador, bloque_ponchon_savarit/bloque_fug ni
# la tienen en su lista de variables) -- pasarla como variable de pool
# ahi no crashea (Orquestador la ignora si no la usa ningun bloque) pero
# tampoco hace nada, asi que se filtra para que la API sea predecible.
_VARIABLES_POOL = {
    "mccabe_thiele": ("x_D", "x_B", "q", "R", "N"),
    "ponchon_savarit": ("x_D", "x_B", "Qc_D", "N"),
    "fug": ("recuperacion_LK_D", "recuperacion_HK_B", "R"),
}

_VARIABLES_SALIDA_EXTRA = {
    "mccabe_thiele": ("N", "R", "Q_c", "Q_R", "R_int", "V_barra"),
    "ponchon_savarit": ("N", "Qc_D"),
    "fug": ("N", "N_min", "R_min", "R", "Q_c", "Q_R"),
}


def _construir_columna(request: ResolverColumnaRequest, proveedor, calc_elv, z_F):
    P_sistema = request.feed.P

    if request.metodo == "mccabe_thiele":
        evaluador = EvaluadorMcCabeThiele(calc_elv, request.nombres, P_sistema=P_sistema)
        solucionador = SolucionadorMcCabeThiele(evaluador)
        return ColumnaDestilacion("mccabe_thiele", solucionador_mt=solucionador)

    if request.metodo == "ponchon_savarit":
        evaluador = EvaluadorPonchonSavarit(calc_elv, request.nombres, P_sistema=P_sistema)
        solucionador = SolucionadorPonchonSavarit(evaluador)
        q = request.parametros.get("q", 1.0)
        return ColumnaDestilacion("ponchon_savarit", solucionador_ps=solucionador, q=q)

    if request.metodo == "fug":
        if request.indice_LK is None or request.indice_HK is None:
            raise ValueError("El metodo 'fug' requiere indice_LK e indice_HK.")
        q = request.parametros.get("q", 1.0)
        analizador = AnalizadorFUG(
            calc_elv, proveedor, request.nombres, z_F, q=q, P_sistema=P_sistema,
            indice_LK=request.indice_LK, indice_HK=request.indice_HK,
        )
        return ColumnaDestilacion("fug", analizador_fug=analizador)

    raise ValueError(f"metodo desconocido: {request.metodo!r}")


def _corriente_a_schema(corriente):
    if corriente is None:
        return None
    return CorrienteSalida(
        nombres=corriente.nombres,
        composicion=[float(x) for x in corriente.composicion],
        flujo_molar=corriente.flujo_molar,
        T=corriente.T,
        P=corriente.P,
    )


def _diagrama_mccabe_thiele(columna, pool, n_puntos_curva=80):
    """
    Datos (no imagen) para dibujar la construccion de McCabe-Thiele en el
    navegador. Se re-evalua calcular_escalones con los valores ya
    resueltos: es barato (brentq por etapa sobre una spline ya
    precalculada) y evita tener que cablear el escalonamiento a traves
    de todo el Orquestador solo para graficarlo.
    """
    requeridos = ("z_F", "q", "x_D", "x_B", "R")
    if any(pool.get(v) is None for v in requeridos):
        return None

    evaluador = columna._evaluador()
    try:
        resultado = evaluador.calcular_escalones(**{v: pool[v] for v in requeridos})
    except (ValueError, RuntimeError):
        return None

    x_curva = np.linspace(0.0, 1.0, n_puntos_curva)
    y_curva = [float(evaluador.y_equilibrio(float(x))) for x in x_curva]

    return DiagramaMcCabeThiele(
        x_equilibrio=[float(x) for x in x_curva],
        y_equilibrio=y_curva,
        escalones=[[float(px), float(py)] for px, py in resultado["escalones"]],
        interseccion_rol_q=[float(v) for v in resultado["interseccion_rol_q"]],
        z_F=float(pool["z_F"]), q=float(pool["q"]), x_D=float(pool["x_D"]),
        x_B=float(pool["x_B"]), R=float(pool["R"]),
        R_min=float(resultado["R_min"]), N=float(resultado["N"]),
    )


def resolver_columna(request: ResolverColumnaRequest) -> ResolverColumnaResponse:
    proveedor = ProveedorTermodinamico(request.nombres)
    calc_elv = CalculadoraELV(proveedor)

    z_F = np.array(request.feed.composicion, dtype=float)
    if not np.isclose(z_F.sum(), 1.0, atol=1e-6):
        raise ValueError(f"La composicion del feed debe sumar 1.0 (suma actual: {z_F.sum():.6f}).")

    if request.feed.T is not None:
        T_feed = request.feed.T
    else:
        T_feed, _ = calc_elv.burbuja_T(request.feed.P, z_F)

    corriente_feed = Corriente(request.nombres, z_F, request.feed.flujo_molar, T_feed, request.feed.P)

    columna = _construir_columna(request, proveedor, calc_elv, z_F)

    claves_pool_validas = _VARIABLES_POOL[request.metodo]
    valores_extra = {k: v for k, v in request.parametros.items() if k in claves_pool_validas}

    resultado = columna.resolver_desde_feed(corriente_feed, **valores_extra)
    pool = resultado["pool"]

    escalares = {}
    for v in _VARIABLES_SALIDA_EXTRA[request.metodo]:
        valor = pool.get(v)
        if valor is not None and np.isscalar(valor):
            escalares[v] = float(valor)

    diagrama = _diagrama_mccabe_thiele(columna, pool) if request.metodo == "mccabe_thiele" else None

    return ResolverColumnaResponse(
        completo=resultado["completo"],
        incognitas_restantes=[str(v) for v in resultado["incognitas_restantes"]],
        escalares=escalares,
        T_feed_usada=T_feed,
        D=_corriente_a_schema(resultado["corriente_D"]),
        B=_corriente_a_schema(resultado["corriente_B"]),
        diagrama=diagrama,
    )
