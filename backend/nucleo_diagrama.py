"""
Frontera HTTP del modelo con corrientes de primera clase
(core/diagrama_corrientes.py). Sustituye a nucleo_flowsheet.py como
motor del flowsheet: aqui las variables del pool son escalares por
corriente, asi que el cliente puede mandar CUALQUIER subconjunto y el
sistema resuelve en la direccion que haga falta.
"""
import numpy as np

from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.elv import CalculadoraELV
from thermodynamics.reaccion import GestorReaccion
from core.mccabe_thiele import EvaluadorMcCabeThiele, SolucionadorMcCabeThiele
from core.ponchon_savarit import EvaluadorPonchonSavarit, SolucionadorPonchonSavarit
from core.diagrama_corrientes import DiagramaCorrientes

from backend.schemas import (
    ResolverDiagramaRequest, ResolverDiagramaResponse, DiagramaMcCabeThiele,
    DiagramaPonchonSavarit, GradosLibertadRequest, GradosLibertadResponse,
)


def _construir(request):
    """Devuelve el diagrama y, aparte, los evaluadores de cada columna (para graficar despues)."""
    proveedor = ProveedorTermodinamico(request.componentes)
    calc_elv = CalculadoraELV(proveedor)

    # Las masas molares salen de 'thermo' (Chemical.MW), no del cliente:
    # asi el caudal masico es una variable mas del sistema y no depende
    # de que el frontend tenga la MW cacheada.
    masas_molares = [float(c.MW) for c in proveedor.componentes]

    diagrama = DiagramaCorrientes(request.componentes, masas_molares=masas_molares, proveedor=proveedor)
    for corriente in request.corrientes:
        diagrama.agregar_corriente(corriente)
    columnas = {}

    for op in request.operaciones:
        c = op.corrientes
        if op.tipo == "columna":
            metodo = op.metodo or "mccabe_thiele"
            if metodo == "fug":
                # Multicomponente: no hay evaluador binario que construir.
                # Los indices clave son del problema, no incognitas.
                n_comp = len(request.componentes)
                idx_LK = op.indice_LK if op.indice_LK is not None else 0
                idx_HK = op.indice_HK if op.indice_HK is not None else min(1, n_comp - 1)
                diagrama.agregar_columna_fug(
                    op.nombre,
                    alimentacion=c["alimentacion"], destilado=c["destilado"], fondos=c["fondos"],
                    calculadora_elv=calc_elv, proveedor=proveedor,
                    indice_LK=idx_LK, indice_HK=idx_HK,
                    q_fijo=op.q if op.q is not None else 1.0,
                    P_sistema=op.P_sistema,
                    con_cargas_termicas=op.con_balance_energia,
                )
                columnas[op.nombre] = {
                    "evaluador": None, "metodo": metodo, "corrientes": c, "q": op.q,
                }
                continue
            if metodo == "ponchon_savarit":
                evaluador = EvaluadorPonchonSavarit(calc_elv, request.componentes, P_sistema=op.P_sistema)
                solucionador = SolucionadorPonchonSavarit(evaluador)
            else:
                evaluador = EvaluadorMcCabeThiele(calc_elv, request.componentes, P_sistema=op.P_sistema)
                solucionador = SolucionadorMcCabeThiele(evaluador)
            diagrama.agregar_columna_binaria(
                op.nombre, solucionador,
                alimentacion=c["alimentacion"], destilado=c["destilado"], fondos=c["fondos"],
                metodo=metodo, q_fijo=op.q,
                con_cargas_termicas=op.con_balance_energia,
            )
            columnas[op.nombre] = {
                "evaluador": evaluador, "metodo": metodo, "corrientes": c, "q": op.q,
            }
        elif op.tipo == "reactor_cstr":
            if op.reaccion is None:
                raise ValueError(
                    f"{op.nombre}: un reactor necesita una reaccion "
                    "(coeficientes estequiometricos, uno por componente)."
                )
            if len(op.reaccion.nu) != len(request.componentes):
                raise ValueError(
                    f"{op.nombre}: la reaccion trae {len(op.reaccion.nu)} coeficientes y hay "
                    f"{len(request.componentes)} componentes. Debe haber uno por componente, en el mismo orden."
                )
            gestor = GestorReaccion(
                proveedor, np.asarray(op.reaccion.nu, dtype=float),
                A=op.reaccion.A, Ea=op.reaccion.Ea,
            )
            # 'entradas' (lista) es lo normal ahora; 'entrada' se acepta
            # por compatibilidad con diagramas guardados antes.
            entradas = c.get("entradas") or ([c["entrada"]] if c.get("entrada") else [])
            diagrama.agregar_reactor_cstr(
                op.nombre, entrada=None, entradas=entradas, salida=c["salida"],
                nu=op.reaccion.nu, gestor_reaccion=gestor,
                con_cinetica=op.con_cinetica,
                modo_energia=op.modo_energia,
                Q=op.Q if op.modo_energia == "calor_dado" else None,
                con_balance_energia=op.con_balance_energia,
            )
        elif op.tipo == "mezclador":
            diagrama.agregar_mezclador(op.nombre, entradas=c["entradas"], salida=c["salida"])
        elif op.tipo == "divisor":
            diagrama.agregar_divisor(op.nombre, entrada=c["entrada"], salidas=c["salidas"], fracciones=op.fracciones or [])
        elif op.tipo == "bomba":
            diagrama.agregar_bomba(op.nombre, entrada=c["entrada"], salida=c["salida"])
        elif op.tipo == "flash":
            # Exactamente UNA especificacion. Si el cliente no manda
            # ninguna se asume adiabatico, que es el separador tipico
            # detras de una valvula; el nucleo rechaza las combinaciones
            # sobre-especificadas con su propio mensaje.
            diagrama.agregar_flash(
                op.nombre,
                entrada=c["entrada"], vapor=c["vapor"], liquido=c["liquido"],
                P_operacion=op.P_sistema,
                T_operacion=op.T_operacion,
                Q_por_mol=op.Q_por_mol if op.T_operacion is None and op.fraccion_vapor is None else None,
                fraccion_vapor=op.fraccion_vapor,
            )
        elif op.tipo == "intercambiador":
            diagrama.agregar_intercambiador(
                op.nombre, entrada=c["entrada"], salida=c["salida"],
                Q_por_mol=op.Q_por_mol if op.T_salida is None else None,
                T_salida=op.T_salida,
            )
        elif op.tipo == "valvula":
            if op.P_salida is None:
                raise ValueError(
                    f"{op.nombre}: una valvula necesita la presion de salida. "
                    "Es lo unico que la define: la expansion es isentalpica."
                )
            diagrama.agregar_valvula(
                op.nombre, entrada=c["entrada"], salida=c["salida"], P_salida=op.P_salida,
            )
        else:
            raise ValueError(f"tipo de operacion desconocido: {op.tipo!r}")

    for corriente, kg_s in getattr(request, "caudales_masicos", {}).items():
        diagrama.fijar_caudal_masico(corriente, kg_s)

    return diagrama, columnas


def _diagrama_de_columna(nombre, info, pool, n_puntos_curva=80):
    """
    Construccion grafica de una columna del diagrama. Traduce las
    variables de CORRIENTE del pool global (s1.x0, s2.F...) a los nombres
    que espera el evaluador (z_F, x_D...) y reevalua el escalonamiento --
    barato, porque la curva de equilibrio ya esta precalculada en el
    evaluador. Despacha por metodo: y-x para McCabe-Thiele, H-x para
    Ponchon-Savarit.
    """
    if info["metodo"] == "ponchon_savarit":
        return _diagrama_ponchon_savarit(nombre, info, pool, n_puntos_curva)
    if info["metodo"] != "mccabe_thiele":
        return None

    c = info["corrientes"]
    locales = {
        "z_F": pool.get(f"{c['alimentacion']}.x0"),
        "x_D": pool.get(f"{c['destilado']}.x0"),
        "x_B": pool.get(f"{c['fondos']}.x0"),
        "q": pool.get(f"{nombre}.q"),
        "R": pool.get(f"{nombre}.R"),
    }
    if any(v is None for v in locales.values()):
        return None

    evaluador = info["evaluador"]
    try:
        resultado = evaluador.calcular_escalones(**locales)
    except (ValueError, RuntimeError):
        return None

    x_curva = np.linspace(0.0, 1.0, n_puntos_curva)
    return DiagramaMcCabeThiele(
        x_equilibrio=[float(x) for x in x_curva],
        y_equilibrio=[float(evaluador.y_equilibrio(float(x))) for x in x_curva],
        escalones=[[float(px), float(py)] for px, py in resultado["escalones"]],
        interseccion_rol_q=[float(v) for v in resultado["interseccion_rol_q"]],
        z_F=float(locales["z_F"]), q=float(locales["q"]), x_D=float(locales["x_D"]),
        x_B=float(locales["x_B"]), R=float(locales["R"]),
        R_min=float(resultado["R_min"]), N=float(resultado["N"]),
    )


def _diagrama_ponchon_savarit(nombre, info, pool, n_puntos_curva=80):
    """
    Construccion entalpia-composicion. Se reevalua el escalonamiento con
    _diagnosticar=False a proposito: aqui ya sabemos que la columna
    resolvio (el pool trae su N), y si por alguna razon fallara NO
    queremos pagar la busqueda numerica de Qc_D_min solo para dibujar --
    el mensaje de error util ya lo dio el solver en su momento.
    """
    c = info["corrientes"]
    locales = {
        "z_F": pool.get(f"{c['alimentacion']}.x0"),
        "x_D": pool.get(f"{c['destilado']}.x0"),
        "x_B": pool.get(f"{c['fondos']}.x0"),
        "Qc_D": pool.get(f"{nombre}.Qc_D"),
    }
    if any(v is None for v in locales.values()):
        return None

    evaluador = info["evaluador"]
    q = info.get("q")
    try:
        H_F = evaluador.H_F_desde_q(locales["z_F"], q)
        QR_B = evaluador.derivar_QR_B(
            locales["z_F"], locales["x_D"], locales["x_B"], locales["Qc_D"], H_F
        )
        resultado = evaluador.calcular_escalones(
            **locales, QR_B=QR_B, H_F=H_F, _diagnosticar=False
        )
    except (ValueError, RuntimeError):
        return None

    # Qc_D_min es informativo (el equivalente de R_min en la grafica de
    # McCabe-Thiele). Cuesta una biseccion, asi que si no sale no se
    # rompe el dibujo: se manda None y el frontend simplemente no lo cita.
    try:
        Qc_D_min = float(evaluador.calcular_Qc_D_min(
            locales["z_F"], locales["x_D"], locales["x_B"], H_F
        ))
    except (ValueError, RuntimeError):
        Qc_D_min = None

    x_curva = np.linspace(1e-4, 1.0 - 1e-4, n_puntos_curva)
    polos = resultado["polos"]
    return DiagramaPonchonSavarit(
        x_saturacion=[float(x) for x in x_curva],
        H_liquido=[float(evaluador.H_L(float(x))) for x in x_curva],
        H_vapor=[float(evaluador.H_V(float(x))) for x in x_curva],
        escalera=[[float(px), float(py)] for px, py in resultado["puntos"]],
        tie_lines=[[float(v) for v in t] for t in resultado["tie_lines"]],
        lineas_operativas=[[float(v) for v in l] for l in resultado["lineas_operativas"]],
        x_delta_D=float(polos["x_delta_D"]), H_delta_D=float(polos["H_delta_D"]),
        x_delta_B=float(polos["x_delta_B"]), H_delta_B=float(polos["H_delta_B"]),
        z_F=float(locales["z_F"]), H_F=float(polos["H_F"]),
        x_D=float(locales["x_D"]), x_B=float(locales["x_B"]),
        Qc_D=float(locales["Qc_D"]), QR_B=float(QR_B),
        Qc_D_min=Qc_D_min, N=float(resultado["N"]),
    )


def resolver_diagrama(request: ResolverDiagramaRequest) -> ResolverDiagramaResponse:
    diagrama, columnas = _construir(request)
    resultado = diagrama.resolver(**request.valores)

    pool = {}
    for clave, valor in resultado["pool"].items():
        if valor is None:
            continue
        pool[clave] = float(valor) if isinstance(valor, (int, float, np.floating, np.integer)) else valor

    diagramas = {}
    for nombre, info in columnas.items():
        grafica = _diagrama_de_columna(nombre, info, pool)
        if grafica is not None:
            diagramas[nombre] = grafica

    return ResolverDiagramaResponse(
        completo=resultado["completo"],
        pool=pool,
        incognitas_restantes=sorted(str(v) for v in resultado["incognitas_restantes"]),
        resueltos_por={str(k): str(v) for k, v in resultado["resueltos_por"].items()},
        diagnostico=resultado["diagnostico"],
        inconsistencias=resultado["inconsistencias"],
        variables=diagrama.todas_las_variables(),
        diagramas=diagramas,
        masas_molares_mezcla=diagrama.masas_molares_de_mezcla(resultado["pool"]),
        reciclo=resultado.get("reciclo"),
    )


def grados_libertad(request: GradosLibertadRequest) -> GradosLibertadResponse:
    """
    Conteo en vivo sin resolver nada -- lo bastante barato como para
    llamarlo mientras el usuario escribe. Construir el diagrama cuesta
    lo que cuesta precalcular la curva de equilibrio de cada columna,
    asi que el frontend debe llamarlo con retardo, no en cada tecla.
    """
    diagrama, _ = _construir(request)
    return GradosLibertadResponse(**diagrama.grados_de_libertad(request.valores))
