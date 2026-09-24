"""
Frontera HTTP del modulo de termodinamica: mapas de curvas residuales
(reactivas y no reactivas) y busqueda de azeotropos.

El nucleo que hay debajo (core/topology.py, core/analisis_nodos.py) se
escribio para ESCRITORIO: sus metodos terminan en plt.show() o
figura.show(). Aqui NO se llama a nada de eso -- se usan solo los
generadores que devuelven arrays (generar_curva_residual_cinetica,
generar_curva_residual_equilibrio, draw_reactive_line) y se mandan los
puntos en JSON, para que el navegador dibuje con su propio tema. Esa es
la unica forma de que la misma fisica sirva en las dos superficies sin
duplicarla.
"""
import re
from collections import Counter

import numpy as np

from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.elv import CalculadoraELV
from thermodynamics.reaccion import GestorReaccion
from core.transformaciones import EspacioReactivo
from core.topology import ThermodynamicEngine
from core.analisis_nodos import BuscadorAzeotropos

from backend.schemas import (
    MapaResidualRequest, MapaResidualResponse, CurvaResidual, PoloGeometrico,
    AzeotroposRequest, AzeotroposResponse, AzeotropoEncontrado,
    PropiedadesReaccionResponse,
)

# Semillas repartidas por el simplex. Se usa una rejilla determinista en
# vez de np.random.dirichlet (que es lo que hace plot_ternary) porque un
# mapa que cambia de dibujo en cada peticion es inservible para
# comparar dos casos -- y ademas impediria verificar nada.
def _semillas_simplex(n_componentes, n_curvas):
    if n_componentes == 3:
        puntos = []
        # Rejilla baricentrica: pasos iguales sobre el triangulo.
        lado = max(int(np.ceil((np.sqrt(8 * n_curvas + 1) - 1) / 2)), 2)
        for i in range(1, lado + 1):
            for j in range(1, lado + 1 - i + 1):
                k = lado + 2 - i - j
                if k < 1:
                    continue
                total = i + j + k
                puntos.append([i / total, j / total, k / total])
        # Mezcla reproducible para que recortar la lista no sesgue una esquina.
        puntos.sort(key=lambda p: (round(p[0], 6), round(p[1], 6)))
        indices = np.linspace(0, len(puntos) - 1, min(n_curvas, len(puntos))).astype(int)
        return [puntos[i] for i in np.unique(indices)]

    generador = np.random.default_rng(12345)  # semilla fija: mapas reproducibles
    crudo = generador.dirichlet(np.ones(n_componentes), size=n_curvas)
    return [list(map(float, p)) for p in crudo]


_PATRON_ATOMO = re.compile(r"([A-Z][a-z]?)(\d*)")


def _atomos(formula):
    cuenta = Counter()
    for elemento, numero in _PATRON_ATOMO.findall(formula or ""):
        if elemento:
            cuenta[elemento] += int(numero or 1)
    return cuenta


def balance_atomico(proveedor, nu):
    """
    Comprueba que sum_i(nu_i * atomos_i) = 0 para cada elemento, o sea que
    la reaccion conserva la materia.

    Esto NO lo verificaba nadie, y es la primera cosa que puede estar mal
    en un mapa reactivo: se acepto sin protestar
    'acetal <-> acetaldehido + etanol' con nu=[1,1,-1], que deja 2 carbonos
    y 4 hidrogenos sin cerrar (faltan un agua y un segundo etanol). Con una
    estequiometria asi, todo lo que se dibuje encima es aritmetica sobre
    una reaccion que no existe.

    Devuelve (cierra, desbalance_por_elemento, desbalance_masa).
    """
    nu = np.asarray(nu, dtype=float)
    desbalance = Counter()
    for coef, comp in zip(nu, proveedor.componentes):
        for elemento, cantidad in _atomos(getattr(comp, "formula", "")).items():
            desbalance[elemento] += coef * cantidad
    desbalance = {e: float(v) for e, v in desbalance.items() if abs(v) > 1e-9}

    masa = float(sum(
        coef * float(getattr(comp, "MW", 0.0) or 0.0)
        for coef, comp in zip(nu, proveedor.componentes)
    ))
    return (not desbalance and abs(masa) < 1e-6), desbalance, masa


def _aviso_balance(proveedor, nu):
    cierra, desbalance, masa = balance_atomico(proveedor, nu)
    if cierra:
        return None
    partes = ", ".join(f"{e}: {v:+g}" for e, v in sorted(desbalance.items()))
    return (
        f"La reaccion NO conserva la materia ({partes or 'masa'}; "
        f"desbalance de masa {masa:+.4g} g/mol). Revisa los coeficientes: "
        "puede que falte un componente de la mezcla, o que un coeficiente "
        "no sea 1. Todo lo que se calcule encima de una estequiometria que "
        "no cierra es aritmetica sobre una reaccion que no existe."
    )


def _construir_motor(request):
    """Arma el motor topologico con la reaccion del request (o sin ella)."""
    proveedor = ProveedorTermodinamico(request.componentes)
    calc_elv = CalculadoraELV(proveedor)
    n = len(request.componentes)

    rx = request.reaccion
    if rx is None:
        # Sin reaccion: nu=0 hace que el termino quimico se anule solo, y
        # entonces dx/dxi = x - y* es exactamente la curva residual
        # clasica. Asi el mismo motor sirve para los dos casos en vez de
        # tener dos rutas de codigo que se puedan desincronizar.
        nu = np.zeros(n)
        gestor = None
        espacio = None
    else:
        if len(rx.nu) != n:
            raise ValueError(
                f"El vector estequiometrico tiene {len(rx.nu)} coeficientes y hay "
                f"{n} componentes: deben coincidir y en el mismo orden."
            )
        if all(abs(v) < 1e-12 for v in rx.nu):
            raise ValueError("El vector estequiometrico es todo ceros: eso no es una reaccion.")
        nu = np.asarray(rx.nu, dtype=float)
        gestor = GestorReaccion(proveedor, nu, A=rx.A, Ea=rx.Ea)
        espacio = EspacioReactivo(nu, rx.componente_referencia)

    motor = ThermodynamicEngine(
        nu=nu, proveedor=proveedor, K_R=1.0,
        gestor_reaccion=gestor, calculadora_elv=calc_elv,
        espacio_reactivo=espacio, Da=request.Da,
    )
    return motor, proveedor, calc_elv, gestor, espacio


def mapa_residual(request: MapaResidualRequest) -> MapaResidualResponse:
    """
    Mapa de curvas residuales. Con reaccion=None sale el mapa clasico
    (dx/dxi = x - y*); con reaccion y Da>0, el reactivo bajo control
    cinetico. Cada curva se integra por separado y una que falle no
    tumba el mapa entero: se omite y se informa cuantas se perdieron.
    """
    motor, proveedor, calc_elv, gestor, _ = _construir_motor(request)
    n = len(request.componentes)
    sin_reaccion = request.reaccion is None or request.Da == 0.0

    semillas = _semillas_simplex(n, request.n_curvas)
    curvas, fallidas = [], 0
    # Se guarda POR QUE fallo la primera curva. Sin esto, un fallo
    # sistematico (p.ej. un componente que UNIFAC no sabe describir) se
    # veia como un mapa vacio sin ninguna explicacion -- se comprobo:
    # con gestor=None todas las curvas reventaban en silencio y el mapa
    # salia vacio como si el sistema no tuviera topologia.
    motivo_fallo = None

    for x0 in semillas:
        try:
            xi, trayectoria = motor.generar_curva_residual_cinetica(
                x_inicial=np.asarray(x0, dtype=float),
                T_inicial=350.0,
                Da=0.0 if sin_reaccion else request.Da,
                t_span=(0.0, request.xi_max),
                P_sistema=request.P_sistema,
                n_eval=request.n_puntos,
            )
        except Exception as e:
            fallidas += 1
            if motivo_fallo is None:
                motivo_fallo = f"{type(e).__name__}: {e}"
            continue
        if trayectoria.shape[0] < 2:
            fallidas += 1
            if motivo_fallo is None:
                motivo_fallo = "la integracion se detuvo en el primer paso (composicion inicial en la frontera del simplex)"
            continue
        curvas.append(
            CurvaResidual(
                inicio=[float(v) for v in x0],
                puntos=[[float(v) for v in fila] for fila in trayectoria],
                xi=[float(v) for v in xi],
            )
        )

    # Temperaturas de los vertices: son los puntos de ebullicion puros y
    # sirven para rotular el diagrama (que vertice es el ligero).
    T_vertices = []
    for i in range(n):
        x_puro = np.full(n, 1e-9)
        x_puro[i] = 1.0 - 1e-9 * (n - 1)
        try:
            T, _ = calc_elv.burbuja_T(request.P_sistema, x_puro)
            T_vertices.append(float(T))
        except Exception:
            T_vertices.append(None)

    if not curvas:
        raise ValueError(
            "No se pudo integrar ninguna curva residual para este sistema"
            + (f". Primer fallo: {motivo_fallo}" if motivo_fallo else ".")
        )

    # Los tres elementos que enmarcan el mapa en el metodo original. Sin
    # ellos solo se ve un abanico de trayectorias: son el polo, las rectas
    # de reaccion pura y la curva de equilibrio quimico los que dicen HACIA
    # DONDE empuja la reaccion y donde deja de empujar. Solo existen si hay
    # reaccion; en un mapa inerte no tienen sentido.
    trayectorias, curva_eq, lineas_est, polo = [], [], [], None
    if n == 3 and request.reaccion is not None:
        T_ref = request.T_referencia
        try:
            polo = PoloGeometrico(**motor.polo_geometrico())
            lineas_est = motor.lineas_estequiometricas()
        except Exception:
            pass
        try:
            curva_eq = motor.curva_equilibrio_quimico(T_ref)
        except Exception:
            curva_eq = []
        if request.incluir_trayectorias_discretas:
            try:
                trayectorias = motor.trayectorias_reactivas(semillas, T_ref, max_etapas=request.max_etapas)
            except Exception:
                trayectorias = []

    return MapaResidualResponse(
        componentes=request.componentes,
        curvas=curvas,
        trayectorias_reactivas=trayectorias,
        curva_equilibrio_quimico=curva_eq,
        lineas_estequiometricas=lineas_est,
        polo=polo,
        curvas_fallidas=fallidas,
        motivo_fallos=motivo_fallo,
        T_vertices=T_vertices,
        aviso_balance=(_aviso_balance(proveedor, request.reaccion.nu)
                       if request.reaccion is not None else None),
        es_reactivo=not sin_reaccion,
        Da=0.0 if sin_reaccion else request.Da,
        P_sistema=request.P_sistema,
    )


def buscar_azeotropos(request: AzeotroposRequest) -> AzeotroposResponse:
    """
    Barrido de semillas sobre el simplex con BuscadorAzeotropos. Se
    reportan solo las raices que de verdad convergieron y se deduplican
    (varias semillas caen en el mismo azeotropo, que es lo esperable).
    """
    motor, proveedor, calc_elv, gestor, espacio = _construir_motor(request)
    n = len(request.componentes)

    if gestor is None or espacio is None:
        raise ValueError(
            "La busqueda de azeotropos REACTIVOS necesita una reaccion definida "
            "(vector estequiometrico y parametros de Arrhenius)."
        )

    buscador = BuscadorAzeotropos(calc_elv, gestor, espacio)
    encontrados = []

    for x0 in _semillas_simplex(n, request.n_semillas):
        try:
            if request.modo == "equilibrio":
                X0 = espacio.transformar(np.asarray(x0, dtype=float))
                res = buscador.encontrar_azeotropo_equilibrio(X0, request.P_sistema)
            else:
                # OJO al orden de los argumentos: la firma es
                # (x_guess, Da, P_sistema), no (x_guess, P_sistema, Da).
                res = buscador.encontrar_azeotropo_cinetico(
                    np.asarray(x0, dtype=float), request.Da, request.P_sistema
                )
        except Exception:
            continue
        if not res or not res.get("convergio") or res.get("x") is None:
            continue

        x = [float(v) for v in np.asarray(res["x"], dtype=float)]
        if any(v < -1e-6 or v > 1.0 + 1e-6 for v in x):
            continue  # raiz matematica fuera del simplex: no es un estado fisico
        # Ceros numericos negativos ("-0.0000" en pantalla) son ruido del
        # solver, no una composicion negativa: se recortan.
        x = [0.0 if abs(v) < 1e-9 else min(v, 1.0) for v in x]

        # Un VERTICE PURO no es un azeotropo. Es raiz trivial del sistema:
        # con un solo componente y* = x exactamente, y ademas la velocidad
        # de reaccion se anula porque falta algun reactivo, asi que el
        # residuo completo da cero. Matematicamente valido, fisicamente
        # es un NODO del mapa (el punto de ebullicion del compuesto puro),
        # y presentarlo como azeotropo enganaba: en el sistema
        # acetaldehido/etanol/acetal se reportaba "azeotropo 2" en
        # x=(1,0,0) a 293.4 K, que es simplemente acetaldehido hirviendo.
        if max(x) > 1.0 - 1e-3:
            continue

        # Deduplicado: distintas semillas caen en el mismo punto.
        if any(np.allclose(x, otro.x, atol=1e-4) for otro in encontrados):
            continue
        encontrados.append(
            AzeotropoEncontrado(
                x=x,
                T=float(res["T"]) if res.get("T") is not None else None,
                residual=float(res.get("residual_max") or 0.0),
                desde=[float(v) for v in x0],
            )
        )

    return AzeotroposResponse(
        componentes=request.componentes,
        modo=request.modo,
        azeotropos=encontrados,
        semillas_probadas=request.n_semillas,
    )


def propiedades_reaccion(request) -> PropiedadesReaccionResponse:
    """
    Lo que la reaccion implica antes de integrar nada: entalpia y Gibbs
    estandar, K_eq a la T pedida y la velocidad neta en una composicion
    de prueba. Sirve para darse cuenta de que una estequiometria esta mal
    escrita SIN esperar a que un mapa entero salga vacio.
    """
    motor, proveedor, calc_elv, gestor, _ = _construir_motor(request)
    if gestor is None:
        raise ValueError("Hace falta definir la reaccion.")

    n = len(request.componentes)
    x_prueba = np.full(n, 1.0 / n)
    T = request.T_referencia
    try:
        r = float(gestor.velocidad_reaccion(T, x_prueba))
    except Exception:
        r = None

    return PropiedadesReaccionResponse(
        aviso_balance=_aviso_balance(proveedor, request.reaccion.nu),
        dH_rxn=float(gestor.dH_rxn),
        dG_rxn=float(gestor.dG_rxn),
        K_eq_std=float(gestor.K_eq_std),
        K_eq=float(gestor.K_eq(T)),
        T_referencia=T,
        velocidad_equimolar=r,
        exotermica=bool(gestor.dH_rxn < 0),
    )
