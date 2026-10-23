"""
Script de validacion visual y numerica de toda la Fase 2: el puente
predictivo (ProveedorTermodinamico + CalculadoraELV, thermo/UNIFAC), la
termodinamica de reaccion (GestorReaccion), la transformacion de
Barbosa-Doherty (EspacioReactivo) y el motor topologico completo
(ThermodynamicEngine en core/topology.py, con sus tres formas de trazar
la reactividad: salto discreto, curva continua cinetica y curva continua
de equilibrio). No es parte de la aplicacion: es una comprobacion manual
de que todo produce sentido fisico.

Ejecutar desde la raiz del proyecto:
    python tests/validar_termodinamica.py

Validacion 1 (ELV): sistema binario water(1)/ethanol(2) via
CalculadoraELV (Ley de Raoult Modificada, thermodynamics/elv.py).
    - P-x-y a T = 350 K:      CalculadoraELV.burbuja_P por punto.
    - T-x-y a P = 101325 Pa:  CalculadoraELV.burbuja_T por punto.

Validacion 2 (topologia): sistema reactivo real de 3 componentes
(sintesis de MTBE: isobutileno + metanol <-> MTBE):
    - Mapa ternario del salto discreto (multiples trayectorias + curva
      de equilibrio quimico de referencia), como antes.
    - Comparacion Da moderado vs Da grande en el salto discreto, para
      visualizar la guarda de frontera del simplex agregada en
      draw_reactive_line (con Da grande se ve la trayectoria detenerse
      antes de completar las etapas).
    - Curva residual continua bajo control CINETICO
      (generar_curva_residual_cinetica), con un t_span deliberadamente
      largo para que el evento terminal de scipy la corte justo en el
      limite del simplex, en vez de reventar.
    - Curva residual continua bajo EQUILIBRIO QUIMICO
      (generar_curva_residual_equilibrio), en el espacio transformado de
      Barbosa-Doherty, con el mismo tipo de corte por evento terminal
      cerca de un vertice.

Regla de vectorizacion: la matematica termodinamica en si (dentro de
CalculadoraELV, GestorReaccion, EspacioReactivo) es producto de Hadamard
/ suma de numpy, sin bucles. Los unicos bucles que aparecen aqui recorren
el vector global de x1 (porque UNIFAC.from_subgroups solo acepta una
composicion a la vez) o la malla/etapas de las trayectorias topologicas,
tal como permite la directiva original.
"""

import sys

# Las suites imprimen simbolos griegos y flechas. En una consola Windows
# por defecto (cp1252) eso lanza UnicodeEncodeError y la validacion ni
# siquiera llega a correr -- no falla: NO SE EJECUTA, que es peor. Se
# arregla aqui dentro para que el script funcione solo, sin depender de
# que quien lo lance sepa poner PYTHONIOENCODING.
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

from pathlib import Path

# Permite ejecutar este script directamente ("python tests/archivo.py")
# sin depender de que la raiz del proyecto ya este en sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
# Backend sin ventana por defecto (ver config/graficos.py): los
# graficar_* de aqui terminan en plt.show(), y eso bloqueaba el
# proceso con una ventana cada vez que se importaba el modulo.
import config.graficos  # noqa: F401  -- debe ir ANTES que pyplot
import matplotlib.pyplot as plt

from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.elv import CalculadoraELV
from thermodynamics.reaccion import GestorReaccion
from core.transformaciones import EspacioReactivo
from core.topology import ThermodynamicEngine
from core.analisis_nodos import BuscadorAzeotropos

N_PUNTOS = 41
T_ISOTERMA = 350.0      # K, para el diagrama P-x-y
P_ISOBARA = 101325.0    # Pa, para el diagrama T-x-y


def validar_elv():
    proveedor = ProveedorTermodinamico(["water", "ethanol"])
    calculadora = CalculadoraELV(proveedor)

    x1 = np.linspace(0.0, 1.0, N_PUNTOS)
    x_matriz = np.column_stack([x1, 1.0 - x1])  # shape (N, 2)

    # ---- gamma(T=350K, x) para cada x1 ------------------------------------
    gammas_350K = np.array([
        proveedor.coeficientes_actividad(T_ISOTERMA, fila) for fila in x_matriz
    ])  # shape (N, 2)

    # ---- P-x-y a T constante, via CalculadoraELV.burbuja_P -----------------
    P_burbuja = np.empty(N_PUNTOS)
    y1_pxy = np.empty(N_PUNTOS)
    for i, fila in enumerate(x_matriz):  # bucle permitido: recorre x1 global
        P_burbuja[i], y_vapor = calculadora.burbuja_P(T_ISOTERMA, fila)
        y1_pxy[i] = y_vapor[0]

    # ---- T-x-y a P constante, via CalculadoraELV.burbuja_T ------------------
    T_burbuja = np.empty(N_PUNTOS)
    y1_txy = np.empty(N_PUNTOS)
    for i, fila in enumerate(x_matriz):  # bucle permitido: recorre x1 global
        T_burbuja[i], y_vapor = calculadora.burbuja_T(P_ISOBARA, fila)
        y1_txy[i] = y_vapor[0]

    # ---- figura: 3 subplots ------------------------------------------------
    fig, ejes = plt.subplots(1, 3, figsize=(16, 5))

    ejes[0].plot(x1, gammas_350K[:, 0], label=r"$\gamma_{agua}$")
    ejes[0].plot(x1, gammas_350K[:, 1], label=r"$\gamma_{etanol}$")
    ejes[0].set_xlabel("x1 (agua)")
    ejes[0].set_ylabel("Coeficiente de actividad")
    ejes[0].set_title(f"UNIFAC: γ vs x1 @ {T_ISOTERMA:.0f} K")
    ejes[0].legend()
    ejes[0].grid(alpha=0.3)

    ejes[1].plot(x1, P_burbuja, "o-", label="Burbuja (líquido, x1)")
    ejes[1].plot(y1_pxy, P_burbuja, "s-", label="Rocío (vapor, y1)")
    ejes[1].set_xlabel("x1, y1 (agua)")
    ejes[1].set_ylabel("P [Pa]")
    ejes[1].set_title(f"Diagrama P-x-y @ {T_ISOTERMA:.0f} K")
    ejes[1].legend()
    ejes[1].grid(alpha=0.3)

    ejes[2].plot(x1, T_burbuja, "o-", label="Burbuja (líquido, x1)")
    ejes[2].plot(y1_txy, T_burbuja, "s-", label="Rocío (vapor, y1)")
    ejes[2].set_xlabel("x1, y1 (agua)")
    ejes[2].set_ylabel("T [K]")
    ejes[2].set_title(f"Diagrama T-x-y @ {P_ISOBARA/1000:.1f} kPa")
    ejes[2].legend()
    ejes[2].grid(alpha=0.3)

    fig.suptitle("Validación ELV predictiva — water(1)/ethanol(2) vía UNIFAC")
    fig.tight_layout()
    plt.show()


def validar_topologia():
    # Sistema real de 3 componentes (no ficticio): sintesis de MTBE,
    # isobutileno + metanol <-> MTBE. nu no es equimolar (nu_tot = -1),
    # asi que ademas ejercita la rama no-equimolar de ThermodynamicEngine.
    #
    # K_R (equilibrio ESTATICO) queda solo como reliquia del diseño
    # original -- plot_ternary YA NO lo usa para su curva de equilibrio.
    # A/Ea (cineticos, ILUSTRATIVOS) tampoco son datos de literatura
    # verificados -- reemplazar cuando se tengan valores reales.
    nombres = ["isobutylene", "methanol", "mtbe"]
    nu = [-1.0, -1.0, 3.0]
    x0 = np.array([0.34, 0.33, 0.33])

    proveedor = ProveedorTermodinamico(nombres)
    calc_elv = CalculadoraELV(proveedor)
    gestor = GestorReaccion(proveedor, nu, A=1.0e6, Ea=6.0e4)
    espacio = EspacioReactivo(nu, k=0)

    motor = ThermodynamicEngine(
        nu=nu, proveedor=proveedor, K_R=4.0, gestor_reaccion=gestor,
        calculadora_elv=calc_elv, espacio_reactivo=espacio, Da=5.0,
    )
    motor.print_topology()

    # ---- Mapa ternario (salto discreto, multiples trayectorias + curva
    # de equilibrio quimico de referencia) ------------------------------
    # NUEVO: la curva negra de equilibrio ahora se calcula con
    # gestor_reaccion.K_eq(T_actual) (Gibbs de formacion reales via
    # 'thermo'), no con el K_R estatico -- queda consistente con las
    # trayectorias azules, que ya usaban la reaccion real.
    print(
        f"Curva de equilibrio quimico: K_eq({T_ISOTERMA:.0f} K) = "
        f"{gestor.K_eq(T_ISOTERMA):.4g}  (antes se dibujaba con K_R "
        f"estatico = {motor.K_R:.4g})"
    )
    motor.plot_ternary(T_actual=T_ISOTERMA, n_puntos=50, max_etapas=200)

    # ---- Figura nueva: los tres mapeos agregados en esta fase -----------
    fig, ejes = plt.subplots(2, 2, figsize=(14, 10))
    colores = ["tab:blue", "tab:orange", "tab:green"]

    # (a) salto discreto: Da moderado vs Da grande, para ver la guarda de
    # frontera del simplex en accion (Da=500 debe cortar la trayectoria
    # mucho antes de las 30 etapas).
    motor_agresivo = ThermodynamicEngine(
        nu=nu, proveedor=proveedor, K_R=4.0, gestor_reaccion=gestor,
        calculadora_elv=calc_elv, espacio_reactivo=espacio, Da=500.0,
    )
    traj_moderado = motor.draw_reactive_line(x_inicial=x0, T_actual=T_ISOTERMA, max_etapas=30)
    traj_agresivo = motor_agresivo.draw_reactive_line(x_inicial=x0, T_actual=T_ISOTERMA, max_etapas=30)

    ax = ejes[0, 0]
    for i, nombre in enumerate(nombres):
        ax.plot(traj_moderado[:, i], "o-", color=colores[i], label=f"{nombre} (Da=5)")
        ax.plot(traj_agresivo[:, i], "x--", color=colores[i], alpha=0.6, label=f"{nombre} (Da=500)")
    ax.set_xlabel("etapa")
    ax.set_ylabel("fracción molar")
    ax.set_title("Salto discreto cinético: Da moderado vs Da grande\n(Da=500 dispara la guarda de frontera del símplex)")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    # (b) curva continua bajo control CINETICO -- t_span largo a proposito
    # para que el evento terminal de scipy la corte en el limite del
    # simplex en vez de que burbuja_T reviente.
    xi_cin, traj_cinetica = motor.generar_curva_residual_cinetica(
        x_inicial=x0, T_inicial=T_ISOTERMA, Da=5.0, t_span=(0.0, 2.0), n_eval=200
    )
    ax = ejes[0, 1]
    for i, nombre in enumerate(nombres):
        ax.plot(xi_cin, traj_cinetica[:, i], color=colores[i], label=nombre)
    ax.axvline(xi_cin[-1], color="red", linestyle=":", alpha=0.7,
               label=f"evento @ ξ={xi_cin[-1]:.3f}")
    ax.set_xlabel("ξ")
    ax.set_ylabel("fracción molar (x)")
    ax.set_title("Curva residual continua — control CINÉTICO\n(se detiene sola en el límite del símplex)")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    # (c) curva continua de EQUILIBRIO QUIMICO, en el espacio transformado
    # X de Barbosa-Doherty -- t_span largo a proposito para que el evento
    # terminal la corte cerca de un vertice en vez de lanzar RuntimeError.
    X0 = espacio.transformar(x0)
    xi_eq, traj_equilibrio = motor.generar_curva_residual_equilibrio(
        X_inicial=X0, P_sistema=P_ISOBARA, t_span=(0.0, 5.0), n_eval=100
    )
    ax = ejes[1, 0]
    for i, nombre in enumerate(nombres):
        ax.plot(xi_eq, traj_equilibrio[:, i], color=colores[i], label=f"X_{nombre}")
    ax.axvline(xi_eq[-1], color="red", linestyle=":", alpha=0.7,
               label=f"evento @ ξ'={xi_eq[-1]:.3f}")
    ax.set_xlabel("ξ'")
    ax.set_ylabel("composición transformada (X)")
    ax.set_title("Curva residual continua — EQUILIBRIO QUÍMICO\n(espacio de Barbosa-Doherty; X del componente de referencia ≡ 0)")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    # (d) comparacion cualitativa cinetico vs equilibrio para el MTBE
    # (ojo: una curva esta en espacio real x, la otra en espacio
    # transformado X -- no son la misma escala, es solo para comparar
    # la forma/tendencia de ambos mapeos continuos en una sola vista).
    ax = ejes[1, 1]
    ax.plot(xi_cin, traj_cinetica[:, 2], color="tab:green", label="MTBE, x real (control cinético)")
    ax.plot(xi_eq, traj_equilibrio[:, 2], color="tab:green", linestyle="--",
            label="X_MTBE, espacio transformado (equilibrio)")
    ax.set_xlabel("ξ / ξ'")
    ax.set_ylabel("fracción (x) o composición transformada (X) de MTBE")
    ax.set_title("Comparación cualitativa: cinético vs equilibrio")
    ax.legend(fontsize=7)
    ax.grid(alpha=0.3)

    fig.suptitle("Validación topológica — sistema MTBE (isobutileno + metanol ⇌ MTBE)")
    fig.tight_layout()
    plt.show()


def validar_azeotropos():
    # Mismo sistema MTBE. Se reutiliza un motor con Da=5 solo para pintar
    # trayectorias de fondo (contexto visual); la busqueda de azeotropos
    # en si no depende de ThermodynamicEngine, solo de CalculadoraELV,
    # GestorReaccion y EspacioReactivo.
    nombres = ["isobutylene", "methanol", "mtbe"]
    nu = [-1.0, -1.0, 1.0]
    x0 = np.array([0.30, 0.30, 0.40])

    proveedor = ProveedorTermodinamico(nombres)
    calc_elv = CalculadoraELV(proveedor)
    gestor = GestorReaccion(proveedor, nu, A=1.0e6, Ea=6.0e4)
    espacio = EspacioReactivo(nu, k=0)
    buscador = BuscadorAzeotropos(calc_elv, gestor, espacio)

    motor = ThermodynamicEngine(
        nu=nu, proveedor=proveedor, K_R=4.0, gestor_reaccion=gestor,
        calculadora_elv=calc_elv, espacio_reactivo=espacio, Da=5.0,
    )

    # (a) azeotropo CINETICO -- converge de forma robusta (ver docs/history/build-log.md)
    r_cinetico = buscador.encontrar_azeotropo_cinetico(x_guess=x0, Da=5.0)
    r_cinetico["etiqueta"] = "Azeótropo cinético (Da=5)"
    print(
        f"Azeótropo cinético: x={np.round(r_cinetico['x'], 4)}  "
        f"T={r_cinetico['T']:.1f} K  convergió={r_cinetico['convergio']}  "
        f"residual_max={r_cinetico['residual_max']:.2e}"
    )

    # (b) busqueda de equilibrio quimico -- se muestra aunque NO convergio,
    # a proposito: es un resultado real (no existe raiz interior para este
    # K_eq/estequiometria, ver docs/history/build-log.md), no un error a esconder.
    X0 = espacio.transformar(x0)
    r_equilibrio = buscador.encontrar_azeotropo_equilibrio(X_guess=X0, P_sistema=P_ISOBARA)
    r_equilibrio["etiqueta"] = "Búsqueda equilibrio químico"
    print(
        f"Búsqueda de equilibrio: convergió={r_equilibrio['convergio']}  "
        f"residual_max={r_equilibrio['residual_max']:.4g}  "
        "(no convergio es el resultado esperado para este sistema -- ver docs/history/build-log.md)"
    )

    buscador.graficar_azeotropos(
        resultados=[r_cinetico, r_equilibrio],
        nombres_componentes=nombres,
        motor=motor, T_actual=T_ISOTERMA, n_puntos=150, max_etapas=150,
        titulo="Nodos Azeotrópicos — sistema MTBE",
    )


if __name__ == "__main__":
    print("=== Validación 1: Equilibrio Líquido-Vapor (ELV) ===")
    validar_elv()

    print("=== Validación 2: Motor topológico reactivo ===")
    validar_topologia()

    print("=== Validación 3: Nodos azeotrópicos reactivos ===")
    validar_azeotropos()
