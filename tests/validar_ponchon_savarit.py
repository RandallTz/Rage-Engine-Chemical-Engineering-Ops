"""
Script de validacion visual y numerica de core/ponchon_savarit.py
(EvaluadorPonchonSavarit: curvas H_L(x)/H_V(y) rigurosas, polos Delta_D/
Delta_B, y el escalonamiento por interseccion recta-curva; y
SolucionadorPonchonSavarit: el solver de grados de libertad EO, igual
patron que SolucionadorMcCabeThiele). No es parte de la aplicacion.

Ejecutar desde la raiz del proyecto:
    python tests/validar_ponchon_savarit.py

Sistema de prueba: benceno(1)/tolueno(2) a 1 atm -- el mismo que
McCabe-Thiele, a proposito: al ser un par casi ideal (CMO es buena
aproximacion ahi), N de Ponchon-Savarit deberia salir MUY cercano al N
de McCabe-Thiele con el R equivalente (Qc_D/Hvap_D - 1) -- es la
validacion cruzada mas fuerte que se puede hacer sin datos externos.

Hallazgos reales durante la construccion (documentados aqui y en
docs/history/build-log.md):
    - La tolerancia de colinealidad de los polos (1e-6 ABSOLUTO, pedida
      originalmente) esta mal calibrada: las entalpias aqui son de orden
      10^4-10^5 J/mol, asi que se uso una tolerancia RELATIVA en su lugar.
    - El criterio de cambio de polo (Delta_D -> Delta_B) tiene el sentido
      opuesto al que se penso originalmente: la pendiente operativa
      empieza muy por encima de la pendiente global y DECRECE; el cambio
      ocurre cuando cae por debajo, no cuando la supera.
    - No existe formula cerrada para el Qc_D minimo (equivalente a R_min)
      como en McCabe-Thiele -- se ubica NUMERICAMENTE por biseccion sobre
      exito/fracaso de calcular_escalones (calcular_Qc_D_min).
    - El primer intento de "validar el escalonamiento" fue solo probar
      valores de Qc_D a mano en un for -- NO es resolver el sistema. Con
      q=-0.5 (vapor sobrecalentado) esos valores fijos pinchaban porque
      estaban calibrados para q=1. La correccion real fue construir
      SolucionadorPonchonSavarit y escalar el barrido con Qc_D_min, no
      subir un numero a ojo.
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
from core.ponchon_savarit import EvaluadorPonchonSavarit, SolucionadorPonchonSavarit
from core.mccabe_thiele import EvaluadorMcCabeThiele

NOMBRES = ["benzene", "toluene"]
P_SISTEMA = 101325.0
Z_F, Q, X_D, X_B = 0.40, -1.0, 0.95, 0.05


def _construir_evaluadores():
    proveedor = ProveedorTermodinamico(NOMBRES)
    calc_elv = CalculadoraELV(proveedor)
    ev_ps = EvaluadorPonchonSavarit(calc_elv, NOMBRES, P_sistema=P_SISTEMA, n_puntos_curva=80)
    ev_mt = EvaluadorMcCabeThiele(calc_elv, NOMBRES, P_sistema=P_SISTEMA)
    return ev_ps, ev_mt


def validar_curvas_entalpia(ev_ps):
    print(f"H_L(0)={ev_ps.H_L(0.0):.1f}  H_L(1)={ev_ps.H_L(1.0):.1f}  (tolueno/benceno puros, J/mol)")
    for x in (0.1, 0.4, 0.7, 0.9):
        print(f"  x={x}: H_L={ev_ps.H_L(x):.1f}  H_V={ev_ps.H_V(x):.1f}  "
              f"(H_V-H_L={ev_ps.H_V(x) - ev_ps.H_L(x):.1f}, debe ser ~30-33 kJ/mol)")


def validar_polos_y_colinealidad(ev_ps):
    Qc_D = 300000.0
    H_F = ev_ps.H_F_desde_q(Z_F, Q)
    QR_B = ev_ps.derivar_QR_B(Z_F, X_D, X_B, Qc_D, H_F)
    polos = ev_ps.calcular_polos(Z_F, X_D, X_B, Qc_D, QR_B, H_F=H_F)
    print(f"Polos consistentes: H_Δ_D={polos['H_delta_D']:.1f}  H_Δ_B={polos['H_delta_B']:.1f}  "
          f"(Δ_D debe quedar ARRIBA de H_L(x_D)={ev_ps.H_L(X_D):.1f}; "
          f"Δ_B debe quedar ABAJO de H_L(x_B)={ev_ps.H_L(X_B):.1f})")

    try:
        ev_ps.calcular_polos(Z_F, X_D, X_B, Qc_D, QR_B * 3.0, H_F=H_F)
        print("[ERROR] debió fallar por no-colinealidad y no falló")
    except ValueError as e:
        print(f"[esperado] Q_R inconsistente rechazado -> {str(e)[:100]}...")


def validar_Qc_D_min(ev_ps):
    """El equivalente de R_min -- sin formula cerrada, se ubica por biseccion."""
    for q in (1.0, -0.5):
        H_F = ev_ps.H_F_desde_q(Z_F, q)
        Qc_D_min = ev_ps.calcular_Qc_D_min(Z_F, X_D, X_B, H_F)
        print(f"q={q:>5}: Qc_D_min={Qc_D_min:.1f}")

        QR_B_bajo = ev_ps.derivar_QR_B(Z_F, X_D, X_B, Qc_D_min * 0.9, H_F)
        try:
            ev_ps.calcular_escalones(Z_F, X_D, X_B, Qc_D_min * 0.9, QR_B_bajo, H_F=H_F)
            print("  [ERROR] 0.9*Qc_D_min debió pinchar y no lo hizo")
        except ValueError as e:
            # Antes esto escapaba como RuntimeError generico (o peor, como
            # el "f(a) and f(b) must have different signs" de scipy) y el
            # test solo comprobaba que reventara. Ahora se exige ademas
            # que el mensaje DIGA por que: que el Qc_D esta bajo el minimo.
            mensaje = str(e)
            assert "minimo" in mensaje and "pinch" in mensaje, (
                f"el fallo por pinch deberia explicarse, y dice: {mensaje!r}"
            )
            assert f"{Qc_D_min:.6g}" in mensaje, (
                "el mensaje deberia citar el Qc_D_min concreto para que sea accionable"
            )
            print(f"  [esperado] 0.9*Qc_D_min pincha, y lo explica: {mensaje[:88]}...")

        QR_B_alto = ev_ps.derivar_QR_B(Z_F, X_D, X_B, Qc_D_min * 1.1, H_F)
        r = ev_ps.calcular_escalones(Z_F, X_D, X_B, Qc_D_min * 1.1, QR_B_alto, H_F=H_F)
        print(f"  [esperado] 1.1*Qc_D_min converge, N={r['N']:.2f} (grande, cerca del pinch)")


def validar_solucionador_grados_libertad(solver, ev_ps, ev_mt):
    """Esto es lo que faltaba: RESOLVER el sistema, no probar valores a mano."""
    resultados = []
    for q in (1.0, -0.5):
        r = solver.resolver(z_F=Z_F, x_D=X_D, x_B=X_B, q=q, N=10.0)
        print(
            f"q={q:>5}: Qc_D resuelto={r['valor_resuelto']:.1f}  "
            f"N verificado={r['N']:.6f}  convergió={r['convergio']}"
        )
        resultados.append(r)

    r_directo = solver.resolver(z_F=Z_F, x_D=X_D, x_B=X_B, Qc_D=300000.0, q=Q)
    print(f"Evaluación directa: modo={r_directo['modo']}  N={r_directo['N']:.4f}")

    try:
        solver.resolver(z_F=Z_F, x_D=X_D, q=Q, N=10.0)  # faltan x_B y Qc_D
        print("[ERROR] debió ser subdeterminado y no lo fue")
    except ValueError as e:
        print(f"[esperado] subdeterminado -> {str(e)[:90]}...")

    try:
        solver.resolver(z_F=Z_F, x_D=X_D, x_B=X_B, Qc_D=300000.0, q=Q, N=999.0)
        print("[ERROR] debió ser inconsistente y no lo fue")
    except ValueError as e:
        print(f"[esperado] sobre-especificado inconsistente -> {str(e)[:90]}...")

    return resultados[0]  # q=1.0, para graficar


def validar_cruce_mccabe_escalado_con_Qc_D_min(ev_ps, ev_mt):
    """
    Barrido de verificacion cruzada, pero ahora escalado con Qc_D_min en
    vez de constantes fijas a ojo -- por eso funciona igual de bien para
    q=1 que para q=-0.5, sin pinchar.
    """
    for q in (1.0, -0.5):
        H_F = ev_ps.H_F_desde_q(Z_F, q)
        Qc_D_min = ev_ps.calcular_Qc_D_min(Z_F, X_D, X_B, H_F)
        for factor in (1.5, 3.0, 6.0):
            Qc_D = Qc_D_min * factor
            QR_B = ev_ps.derivar_QR_B(Z_F, X_D, X_B, Qc_D, H_F)
            resultado = ev_ps.calcular_escalones(Z_F, X_D, X_B, Qc_D, QR_B, H_F=H_F)

            xs_equilibrio = resultado["puntos"][1::2, 0]
            monotono = bool(np.all(np.diff(xs_equilibrio) <= 1e-9))

            Hvap_D_aprox = ev_ps.H_V(X_D) - ev_ps.H_L(X_D)
            R_equiv = Qc_D / Hvap_D_aprox - 1.0
            r_mt = ev_mt.calcular_escalones(Z_F, q, X_D, X_B, R_equiv)

            print(
                f"q={q:>5}  {factor:.1f}×Qc_D_min={Qc_D:>9.0f}  N_PS={resultado['N']:.4f}  "
                f"N_MT(R={R_equiv:.2f})={r_mt['N']:.4f}  "
                f"razón={resultado['N']/r_mt['N']:.3f}  monótono={monotono}"
            )


if __name__ == "__main__":
    ev_ps, ev_mt = _construir_evaluadores()
    solver_ps = SolucionadorPonchonSavarit(ev_ps)

    print("=== Validación 1: curvas de entalpía H_L(x), H_V(y) ===")
    validar_curvas_entalpia(ev_ps)

    print("\n=== Validación 2: polos Δ_D/Δ_B y aserción de colinealidad ===")
    validar_polos_y_colinealidad(ev_ps)

    print("\n=== Validación 3: Qc_D_min (equivalente de R_min, sin fórmula cerrada) ===")
    validar_Qc_D_min(ev_ps)

    print("\n=== Validación 4: SolucionadorPonchonSavarit — resolver de verdad, no barrer a mano ===")
    resultado_para_graficar = validar_solucionador_grados_libertad(solver_ps, ev_ps, ev_mt)

    print("\n=== Validación 5: validación cruzada con McCabe-Thiele (escalada con Qc_D_min) ===")
    validar_cruce_mccabe_escalado_con_Qc_D_min(ev_ps, ev_mt)

    ev_ps.graficar_diagrama(
        resultado_para_graficar,
        titulo=f"Ponchon-Savarit — benceno/tolueno, N={resultado_para_graficar['N']:.2f}",
    )
