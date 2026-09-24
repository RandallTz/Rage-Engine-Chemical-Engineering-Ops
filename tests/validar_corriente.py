"""
Script de validacion numerica de core/corriente.py (Corriente,
mezclar_corrientes). No es parte de la aplicacion.

Ejecutar desde la raiz del proyecto:
    python tests/validar_corriente.py

Objetivo explicito: probar que Corriente es FLEXIBLE -- no esta atada a
destilacion. Se prueban tres formas distintas de producir/consumir
Corrientes:
    1. Validacion pura (construccion, errores).
    2. Una "bomba" trivial (1 entrada -> 1 salida, sin termodinamica) --
       demuestra que cualquier codigo puede construir una Corriente de
       salida sin heredar de nada ni implementar una interfaz especial.
    3. Un split real de FUG (1 entrada -> 2 salidas, AnalizadorFUG real).
    4. Mezclar_corrientes (N entradas -> 1 salida, balance de energia
       real), incluyendo un recalculo INDEPENDIENTE del balance de
       energia (no solo confiar en la misma funcion que se prueba).
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq

from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.elv import CalculadoraELV
from core.fug import AnalizadorFUG
from core.corriente import Corriente, mezclar_corrientes

NOMBRES = ["propane", "n-butane", "n-pentane", "n-hexane"]
P_SISTEMA = 101325.0 * 5


def validar_construccion_y_errores():
    c = Corriente(NOMBRES, [0.10, 0.30, 0.30, 0.30], flujo_molar=100.0, T=350.0, P=P_SISTEMA)
    assert np.isclose(c.fraccion("n-butane"), 0.30)
    assert np.allclose(c.flujos_por_componente(), [10.0, 30.0, 30.0, 30.0])

    c2 = Corriente.desde_flujos(NOMBRES, [10.0, 30.0, 30.0, 30.0], T=350.0, P=P_SISTEMA)
    assert np.isclose(c2.flujo_molar, 100.0)
    assert np.allclose(c2.composicion, c.composicion)

    casos_invalidos = {
        "longitud no coincide": lambda: Corriente(NOMBRES, [0.5, 0.5], 100.0, 350.0, P_SISTEMA),
        "composicion no suma 1": lambda: Corriente(NOMBRES, [0.5, 0.5, 0.5, 0.5], 100.0, 350.0, P_SISTEMA),
        "fraccion negativa": lambda: Corriente(NOMBRES, [1.2, -0.2, 0.0, 0.0], 100.0, 350.0, P_SISTEMA),
        "flujo negativo": lambda: Corriente(NOMBRES, [0.25] * 4, -1.0, 350.0, P_SISTEMA),
        "T no positiva": lambda: Corriente(NOMBRES, [0.25] * 4, 100.0, 0.0, P_SISTEMA),
        "P no positiva": lambda: Corriente(NOMBRES, [0.25] * 4, 100.0, 350.0, -1.0),
    }
    for nombre_caso, construir in casos_invalidos.items():
        try:
            construir()
            raise AssertionError(f"Caso '{nombre_caso}' debia lanzar ValueError y no lo hizo")
        except ValueError as e:
            print(f"  OK -- '{nombre_caso}' rechazado correctamente: {e}")

    print("Construccion, desde_flujos y validacion de errores: OK")
    return c


def validar_bomba_trivial(corriente_entrada):
    # Una "bomba" ideal no necesita saber nada de termodinamica para
    # producir su Corriente de salida -- ni siquiera necesita una clase
    # propia. Esto es justo la flexibilidad pedida: cualquier operacion,
    # aunque no exista todavia como clase en el proyecto, ya puede hablar
    # en terminos de Corriente.
    P_nueva = corriente_entrada.P * 2.0
    corriente_salida = Corriente(
        corriente_entrada.nombres, corriente_entrada.composicion,
        corriente_entrada.flujo_molar, corriente_entrada.T, P_nueva,
    )
    assert corriente_salida.flujo_molar == corriente_entrada.flujo_molar
    assert np.allclose(corriente_salida.composicion, corriente_entrada.composicion)
    assert corriente_salida.P == 2.0 * corriente_entrada.P
    print(f"Bomba trivial (1 entrada -> 1 salida, sin termodinamica): "
          f"P {corriente_entrada.P:.0f} -> {corriente_salida.P:.0f} Pa. OK")
    return corriente_salida


def validar_split_fug(proveedor, calc_elv):
    z_F = np.array([0.10, 0.30, 0.30, 0.30])
    F = 100.0
    T_F, _ = calc_elv.burbuja_T(P_SISTEMA, z_F)

    corriente_F = Corriente(NOMBRES, z_F, F, T_F, P_SISTEMA)

    analizador = AnalizadorFUG(calc_elv, proveedor, NOMBRES, corriente_F.composicion, q=1.0,
                                P_sistema=P_SISTEMA, indice_LK=1, indice_HK=2)
    reporte = analizador.reporte_completo(recuperacion_LK_D=0.98, recuperacion_HK_B=0.98, R=3.0)

    corriente_D = Corriente(NOMBRES, reporte["x_D"], corriente_F.flujo_molar * reporte["D"],
                             reporte["T_D"], P_SISTEMA)
    corriente_B = Corriente(NOMBRES, reporte["x_B"], corriente_F.flujo_molar * reporte["B"],
                             reporte["T_B"], P_SISTEMA)

    flujos_entrada = corriente_F.flujos_por_componente()
    flujos_salida = corriente_D.flujos_por_componente() + corriente_B.flujos_por_componente()
    balance_ok = np.allclose(flujos_entrada, flujos_salida, atol=1e-6)
    flujo_total_ok = np.isclose(corriente_D.flujo_molar + corriente_B.flujo_molar, corriente_F.flujo_molar)

    print(f"Split real via AnalizadorFUG (1 entrada -> 2 salidas):")
    print(f"  {corriente_F}")
    print(f"  destilado: {corriente_D}")
    print(f"  fondos:    {corriente_B}")
    print(f"  Balance de materia por componente (entrada == D+B): {balance_ok}")
    print(f"  Balance de flujo total (F == D+B): {flujo_total_ok}")
    assert balance_ok and flujo_total_ok
    return corriente_F, corriente_D, corriente_B


def validar_mezcla_recupera_balance(corriente_F, corriente_D, corriente_B, proveedor):
    corriente_recombinada = mezclar_corrientes([corriente_D, corriente_B], proveedor)
    balance_ok = np.allclose(corriente_recombinada.flujos_por_componente(),
                              corriente_F.flujos_por_componente(), atol=1e-6)
    print(f"\nMezclar destilado+fondos de vuelta (2 entradas -> 1 salida):")
    print(f"  {corriente_recombinada}")
    print(f"  Flujos por componente == flujos de la alimentacion original: {balance_ok}")
    assert balance_ok


def validar_energia_mezcla_independiente(proveedor):
    """
    Caso limpio y verificable a mano: DOS corrientes de la MISMA
    composicion (para que la mezcla no cambie x, solo T), distinto flujo
    y distinta T. Se recalcula T_salida de forma INDEPENDIENTE en este
    mismo test (integrando Cp_L y resolviendo con brentq aqui, sin
    llamar a ninguna funcion interna de mezclar_corrientes) y se compara
    contra lo que devuelve la funcion real.
    """
    x = np.array([0.0, 0.5, 0.5, 0.0])  # n-butano/n-pentano 50/50
    F1, T1 = 40.0, 320.0
    F2, T2 = 60.0, 380.0
    c1 = Corriente(NOMBRES, x, F1, T1, P_SISTEMA)
    c2 = Corriente(NOMBRES, x, F2, T2, P_SISTEMA)

    resultado = mezclar_corrientes([c1, c2], proveedor)

    T_ref = 298.15

    def H_L(T):
        integrando = lambda Tp: float(np.dot(x, proveedor.capacidades_calorificas_liquido(Tp)))
        valor, _ = quad(integrando, T_ref, T)
        return valor

    H_entrada_manual = F1 * H_L(T1) + F2 * H_L(T2)
    F_total = F1 + F2

    def residuo_manual(T):
        return F_total * H_L(T) - H_entrada_manual

    T_salida_manual = brentq(residuo_manual, T1, T2)

    diferencia = abs(resultado.T - T_salida_manual)
    print(f"\nBalance de energia de mezcla, recalculado independientemente:")
    print(f"  T_salida (mezclar_corrientes) = {resultado.T:.6f} K")
    print(f"  T_salida (recalculo manual)   = {T_salida_manual:.6f} K")
    print(f"  Diferencia: {diferencia:.2e} K")
    print(f"  T1 < T_salida < T2: {T1 < resultado.T < T2}")
    assert diferencia < 1e-4
    assert T1 < resultado.T < T2
    assert np.allclose(resultado.composicion, x)  # misma composicion en ambas corrientes -> no cambia

    # Caso degenerado: mismas T de entrada -> T_salida debe ser exactamente esa T (sin pasar por brentq).
    c3 = Corriente(NOMBRES, x, 25.0, 340.0, P_SISTEMA)
    c4 = Corriente(NOMBRES, x, 75.0, 340.0, P_SISTEMA)
    resultado_mismo_T = mezclar_corrientes([c3, c4], proveedor)
    print(f"  Caso degenerado (mismas T de entrada): T_salida = {resultado_mismo_T.T:.6f} K (esperado: 340.0)")
    assert np.isclose(resultado_mismo_T.T, 340.0, atol=1e-6)


if __name__ == "__main__":
    print("=== Validación 1: construcción y errores ===")
    corriente_base = validar_construccion_y_errores()

    print("\n=== Validación 2: operación genérica sin termodinámica (bomba) ===")
    validar_bomba_trivial(corriente_base)

    print("\n=== Validación 3: operación real de destilación (split FUG) ===")
    proveedor = ProveedorTermodinamico(NOMBRES)
    calc_elv = CalculadoraELV(proveedor)
    corriente_F, corriente_D, corriente_B = validar_split_fug(proveedor, calc_elv)

    print("\n=== Validación 4: mezclar corrientes (recuperar balance) ===")
    validar_mezcla_recupera_balance(corriente_F, corriente_D, corriente_B, proveedor)

    print("\n=== Validación 5: balance de energía de la mezcla, verificado a mano ===")
    validar_energia_mezcla_independiente(proveedor)

    print("\nTodas las validaciones de Corriente pasaron.")
