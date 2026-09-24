"""
Script de validacion visual y numerica de core/mccabe_thiele.py
(EvaluadorMcCabeThiele + SolucionadorMcCabeThiele, planteado Orientado a
Ecuaciones). No es parte de la aplicacion: es para verificar a ojo que la
geometria y el solver de grados de libertad tienen sentido antes de
seguir construyendo sobre esto.

Ejecutar desde la raiz del proyecto:
    python tests/validar_mccabe_thiele.py

Sistema de prueba: benceno(1)/tolueno(2) a 1 atm -- par ideal de libro,
sin azeotropo, para que la geometria del diagrama sea la clasica sin
complicaciones extra.

Validaciones:
    1. Evaluacion directa ("rating"): dado R, calcular N y dibujar el
       diagrama de McCabe-Thiele completo (equilibrio, ROL, SOL, linea q,
       escalones).
    2. Diseno inverso ("design spec"): dado N=10 objetivo, resolver R por
       root-finding, verificar que reevaluando ese R se recupera N=10
       exacto, y ubicarlo sobre la curva de sensibilidad N vs R completa.
    3. Casos limite de grados de libertad: subdeterminado (2 incognitas)
       y sobre-especificado inconsistente -- deben fallar con un mensaje
       claro, no silenciosamente.
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

from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.elv import CalculadoraELV
from core.mccabe_thiele import EvaluadorMcCabeThiele, SolucionadorMcCabeThiele
from core.balance_materia import BalanceMateriaGlobal

NOMBRES = ["benzene", "toluene"]
P_SISTEMA = 101325.0
Z_F, Q, X_D, X_B = 0.40, 1.5, 0.95, 0.05


def _construir_evaluador():
    proveedor = ProveedorTermodinamico(NOMBRES)
    calc_elv = CalculadoraELV(proveedor)
    return EvaluadorMcCabeThiele(calc_elv, NOMBRES, P_sistema=P_SISTEMA)


def validar_evaluacion_directa():
    evaluador = _construir_evaluador()
    R_min = evaluador.calcular_R_min(Z_F, Q, X_D)
    R = R_min * 1.5

    resultado = evaluador.calcular_escalones(Z_F, Q, X_D, X_B, R)
    print(f"R_min = {R_min:.4f}  |  R = {R:.4f} ({R/R_min:.2f}·R_min)  |  N = {resultado['N']:.3f}")

    evaluador.graficar_diagrama(
        resultado,
        titulo=f"Evaluación directa — benceno/tolueno, R={R:.3f}·R_min=1.5",
    )
    return evaluador


def validar_resolver_R_dado_N(evaluador):
    solucionador = SolucionadorMcCabeThiele(evaluador)
    N_objetivo = 10.0

    resultado = solucionador.resolver(z_F=Z_F, q=Q, x_D=X_D, x_B=X_B, N=N_objetivo)
    print(
        f"Diseño inverso: N objetivo={N_objetivo} -> R resuelto={resultado['valor_resuelto']:.4f} "
        f"(convergió={resultado['convergio']})"
    )

    chequeo = evaluador.calcular_escalones(Z_F, Q, X_D, X_B, resultado["valor_resuelto"])
    print(f"Chequeo directo con ese R: N={chequeo['N']:.6f} (debe ser ≈{N_objetivo})")

    evaluador.graficar_diagrama(
        resultado,
        titulo=f"Diseño inverso — R resuelto={resultado['valor_resuelto']:.3f} para N={N_objetivo}",
    )
    evaluador.graficar_N_vs_R(
        Z_F, Q, X_D, X_B,
        R_resuelto=resultado["valor_resuelto"], N_objetivo=resultado["N"],
        titulo="Sensibilidad N vs. R — benceno/tolueno",
    )


def validar_casos_frontera(evaluador):
    solucionador = SolucionadorMcCabeThiele(evaluador)

    try:
        solucionador.resolver(z_F=Z_F, q=Q, x_D=X_D, N=10.0)  # faltan x_B y R
    except ValueError as e:
        print(f"[esperado] subdeterminado -> {e}")

    try:
        solucionador.resolver(z_F=Z_F, q=Q, x_D=X_D, x_B=X_B, R=3.0, N=999.0)
    except ValueError as e:
        print(f"[esperado] sobre-especificado inconsistente -> {e}")


def validar_balance_materia():
    balance = BalanceMateriaGlobal()

    F = 100.0
    resultado = balance.resolver(F=F, z_F=Z_F, x_D=X_D, x_B=X_B)
    print(
        f"F={F} -> D={resultado['D']:.4f}, B={resultado['B']:.4f} "
        f"(convergió={resultado['convergio']}, residual_max={resultado['residual_max']:.2e})"
    )

    # chequeo a mano de la formula clasica D = F*(zF-xB)/(xD-xB)
    D_mano = F * (Z_F - X_B) / (X_D - X_B)
    print(f"Chequeo contra fórmula cerrada: D_mano={D_mano:.4f}")

    # caso no trivial: D,B conocidos (flujos) -> resolver F,x_D
    inverso = balance.resolver(D=resultado["D"], B=resultado["B"], z_F=Z_F, x_B=X_B)
    print(
        f"Inverso (D,B conocidos) -> F={inverso['F']:.4f}, x_D={inverso['x_D']:.4f} "
        f"(debe recuperar F={F}, x_D={X_D})"
    )


def validar_condensador_parcial(evaluador):
    R = evaluador.calcular_R_min(Z_F, Q, X_D) * 1.5

    r_total = evaluador.calcular_escalones(Z_F, Q, X_D, X_B, R, condensador_parcial=False)
    r_parcial = evaluador.calcular_escalones(Z_F, Q, X_D, X_B, R, condensador_parcial=True)
    print(
        f"Condensador total: N={r_total['N']:.4f}  |  "
        f"Condensador parcial: N={r_parcial['N']:.4f}  |  "
        f"diferencia={r_parcial['N'] - r_total['N']:.6f} (debe ser 1.0)"
    )

    evaluador.graficar_diagrama(
        r_parcial,
        titulo=f"Condensador parcial — N={r_parcial['N']:.2f} (incluye la etapa del condensador)",
    )


def validar_eficiencia_murphree(evaluador):
    R = evaluador.calcular_R_min(Z_F, Q, X_D) * 1.5

    r_ideal = evaluador.calcular_escalones(Z_F, Q, X_D, X_B, R, E_MV=1.0)
    print(f"E_MV=1.00 -> N={r_ideal['N']:.4f}")
    for E in (0.9, 0.7, 0.5):
        r = evaluador.calcular_escalones(Z_F, Q, X_D, X_B, R, E_MV=E)
        print(f"E_MV={E:.2f} -> N={r['N']:.4f} (debe ser mayor que con E_MV=1.00)")

    r_070 = evaluador.calcular_escalones(Z_F, Q, X_D, X_B, R, E_MV=0.7)
    evaluador.graficar_diagrama(
        r_070, titulo=f"Eficiencia de Murphree E_MV=0.70 — N={r_070['N']:.2f}"
    )


def validar_cargas_termicas(evaluador):
    R = evaluador.calcular_R_min(Z_F, Q, X_D) * 1.5
    balance = BalanceMateriaGlobal().resolver(F=100.0, z_F=Z_F, x_D=X_D, x_B=X_B)
    D, B, F = balance["D"], balance["B"], 100.0

    sin_subenfriar = evaluador.calcular_cargas_termicas(D, B, F, Z_F, X_D, X_B, R_ext=R, q=Q)
    print(
        f"Sin subenfriar: T_D={sin_subenfriar['T_D']:.2f} K, T_B={sin_subenfriar['T_B']:.2f} K, "
        f"Q_c={sin_subenfriar['Q_c']:.1f}, Q_R={sin_subenfriar['Q_R']:.1f}, "
        f"R_int={sin_subenfriar['R_int']:.4f} (debe ser ≈{R:.4f})"
    )

    subenfriado = evaluador.calcular_cargas_termicas(
        D, B, F, Z_F, X_D, X_B, R_ext=R, q=Q, T_reflujo=sin_subenfriar["T_D"] - 10.0
    )
    print(
        f"Subenfriado 10K: Q_c={subenfriado['Q_c']:.1f} (debe ser mayor), "
        f"R_int={subenfriado['R_int']:.4f} (debe ser mayor que R_ext={R:.4f})"
    )


if __name__ == "__main__":
    print("=== Validación 1: evaluación directa (rating) ===")
    evaluador = validar_evaluacion_directa()

    print("\n=== Validación 2: diseño inverso (design spec) ===")
    validar_resolver_R_dado_N(evaluador)

    print("\n=== Validación 3: casos límite de grados de libertad ===")
    validar_casos_frontera(evaluador)

    print("\n=== Validación 4: balance de materia global y condensador parcial ===")
    validar_balance_materia()
    validar_condensador_parcial(evaluador)

    print("\n=== Validación 5: eficiencia de Murphree y cargas térmicas ===")
    validar_eficiencia_murphree(evaluador)
    validar_cargas_termicas(evaluador)
