"""
Puente entre la API web de flowsheet (schemas.py: OperacionDef,
ResolverFlowsheetRequest) y core/diagrama_flujo.py. Traduce JSON <->
Corriente/DiagramaFlujo -- no repite logica de calculo.

Catalogo de tipos de operacion soportados (v1, los mismos 4 ya
verificados en tests/validar_diagrama_flujo.py y
tests/validar_corriente.py): "columna" (envuelve ColumnaDestilacion via
a_operacion_unitaria), "bomba" (cambia P, sin termodinamica), "mezclador"
(mezclar_corrientes, balance de energia real), "divisor"
(dividir_corriente, reparto ideal de flujo).
"""
import numpy as np

from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.elv import CalculadoraELV
from core.mccabe_thiele import EvaluadorMcCabeThiele, SolucionadorMcCabeThiele
from core.ponchon_savarit import EvaluadorPonchonSavarit, SolucionadorPonchonSavarit
from core.fug import AnalizadorFUG
from core.columna_destilacion import ColumnaDestilacion
from core.corriente import Corriente, mezclar_corrientes, dividir_corriente
from core.diagrama_flujo import DiagramaFlujo, OperacionUnitaria

from backend.schemas import OperacionDef, ResolverFlowsheetRequest, ResolverFlowsheetResponse

_CLAVES_CORRIENTE = {"nombres", "composicion", "flujo_molar", "T", "P"}


def _valor_desde_json(valor):
    if isinstance(valor, dict) and _CLAVES_CORRIENTE <= valor.keys():
        return Corriente(valor["nombres"], valor["composicion"], valor["flujo_molar"], valor["T"], valor["P"])
    return valor


def _valor_a_json(valor):
    if isinstance(valor, Corriente):
        return {
            "nombres": valor.nombres,
            "composicion": [float(x) for x in valor.composicion],
            "flujo_molar": valor.flujo_molar,
            "T": valor.T,
            "P": valor.P,
        }
    if isinstance(valor, np.ndarray):
        return [float(x) for x in valor]
    if isinstance(valor, (np.floating, np.integer)):
        return float(valor)
    return valor


def _operacion_columna(definicion: OperacionDef) -> OperacionUnitaria:
    cfg = definicion.config
    nombres = cfg["nombres"]
    proveedor = ProveedorTermodinamico(nombres)
    calc_elv = CalculadoraELV(proveedor)
    P_sistema = cfg["P_sistema"]
    metodo = cfg["metodo"]
    q = cfg.get("q", 1.0)

    if metodo == "mccabe_thiele":
        evaluador = EvaluadorMcCabeThiele(calc_elv, nombres, P_sistema=P_sistema)
        columna = ColumnaDestilacion("mccabe_thiele", solucionador_mt=SolucionadorMcCabeThiele(evaluador))
    elif metodo == "ponchon_savarit":
        evaluador = EvaluadorPonchonSavarit(calc_elv, nombres, P_sistema=P_sistema)
        columna = ColumnaDestilacion("ponchon_savarit", solucionador_ps=SolucionadorPonchonSavarit(evaluador), q=q)
    elif metodo == "fug":
        if "z_F_fug" not in cfg or cfg.get("indice_LK") is None or cfg.get("indice_HK") is None:
            raise ValueError("Una operacion 'columna' con metodo 'fug' requiere z_F_fug, indice_LK e indice_HK en su config.")
        z_F = np.array(cfg["z_F_fug"], dtype=float)
        analizador = AnalizadorFUG(calc_elv, proveedor, nombres, z_F, q=q, P_sistema=P_sistema,
                                    indice_LK=cfg["indice_LK"], indice_HK=cfg["indice_HK"])
        columna = ColumnaDestilacion("fug", analizador_fug=analizador)
    else:
        raise ValueError(f"metodo de columna desconocido: {metodo!r}")

    return columna.a_operacion_unitaria(
        definicion.nombre,
        variables_entrada_extra=tuple(cfg.get("variables_entrada_extra", ())),
        variables_salida_extra=tuple(cfg.get("variables_salida_extra", ())),
    )


def _operacion_bomba(definicion: OperacionDef) -> OperacionUnitaria:
    def resolver_fn(entrada, factor_P):
        salida = Corriente(entrada.nombres, entrada.composicion, entrada.flujo_molar, entrada.T, entrada.P * factor_P)
        return {"salida": salida}

    return OperacionUnitaria(definicion.nombre, ("entrada", "factor_P"), ("salida",), resolver_fn)


def _operacion_mezclador(definicion: OperacionDef) -> OperacionUnitaria:
    cfg = definicion.config
    proveedor = ProveedorTermodinamico(cfg["nombres"])
    puertos_entrada = tuple(cfg["puertos_entrada"])

    def resolver_fn(**entradas):
        corrientes = [entradas[p] for p in puertos_entrada]
        return {"salida": mezclar_corrientes(corrientes, proveedor)}

    return OperacionUnitaria(definicion.nombre, puertos_entrada, ("salida",), resolver_fn)


def _operacion_divisor(definicion: OperacionDef) -> OperacionUnitaria:
    cfg = definicion.config
    puertos_salida = tuple(cfg["puertos_salida"])
    fracciones = cfg["fracciones"]

    def resolver_fn(entrada):
        return dict(zip(puertos_salida, dividir_corriente(entrada, fracciones)))

    return OperacionUnitaria(definicion.nombre, ("entrada",), puertos_salida, resolver_fn)


_CONSTRUCTORES = {
    "columna": _operacion_columna,
    "bomba": _operacion_bomba,
    "mezclador": _operacion_mezclador,
    "divisor": _operacion_divisor,
}


def resolver_flowsheet(request: ResolverFlowsheetRequest) -> ResolverFlowsheetResponse:
    diagrama = DiagramaFlujo()
    for definicion in request.operaciones:
        constructor = _CONSTRUCTORES.get(definicion.tipo)
        if constructor is None:
            raise ValueError(f"tipo de operacion desconocido: {definicion.tipo!r}")
        diagrama.agregar_operacion(constructor(definicion))

    for conexion in request.conexiones:
        diagrama.conectar(conexion.origen, conexion.puerto_salida, conexion.destino, conexion.puerto_entrada)

    valores_conocidos = {clave: _valor_desde_json(valor) for clave, valor in request.valores_conocidos.items()}

    if request.reciclo is not None:
        conexion_ruptura = (
            request.reciclo.conexion.origen, request.reciclo.conexion.puerto_salida,
            request.reciclo.conexion.destino, request.reciclo.conexion.puerto_entrada,
        )
        valor_inicial = _valor_desde_json(request.reciclo.valor_inicial)
        resultado = diagrama.resolver_con_reciclo(
            conexion_ruptura=conexion_ruptura,
            valor_inicial=valor_inicial,
            tolerancia=request.reciclo.tolerancia,
            max_iteraciones_reciclo=request.reciclo.max_iteraciones,
            **valores_conocidos,
        )
    else:
        resultado = diagrama.resolver(**valores_conocidos)

    pool_json = {clave: _valor_a_json(valor) for clave, valor in resultado["pool"].items() if valor is not None}

    return ResolverFlowsheetResponse(
        completo=resultado["completo"],
        incognitas_restantes=[str(v) for v in resultado["incognitas_restantes"]],
        pool=pool_json,
        convergencia_reciclo=resultado.get("convergencia_reciclo"),
        iteraciones_reciclo=resultado.get("iteraciones_reciclo"),
    )
