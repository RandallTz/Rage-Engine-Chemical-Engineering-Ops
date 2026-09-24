"""
Script de validacion numerica de core/diagrama_flujo.py (DiagramaFlujo,
OperacionUnitaria). No es parte de la aplicacion.

Ejecutar desde la raiz del proyecto:
    python tests/validar_diagrama_flujo.py

Dos casos, deliberadamente separados para no confundir dos preguntas
distintas:
    1. SIN reciclo: una cadena real con termodinamica de verdad
       (columna FUG -> bomba), conectada con .conectar() -- prueba que
       el "cable" propaga valores entre operaciones de verdad.
    2. CON reciclo: un lazo sintetico (mezclador + divisor, ambos
       triviales a proposito) cuya solucion tiene forma cerrada exacta
       -- prueba resolver_con_reciclo() contra un numero que se puede
       verificar a mano, sin mezclar esa pregunta con la termodinamica
       del caso 1.
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
from core.fug import AnalizadorFUG
from core.corriente import Corriente, mezclar_corrientes, dividir_corriente
from core.diagrama_flujo import DiagramaFlujo, OperacionUnitaria
from core.columna_destilacion import ColumnaDestilacion

NOMBRES_FUG = ["propane", "n-butane", "n-pentane", "n-hexane"]
P_SISTEMA_FUG = 101325.0 * 5


def validar_cadena_sin_reciclo():
    z_F = np.array([0.10, 0.30, 0.30, 0.30])
    proveedor = ProveedorTermodinamico(NOMBRES_FUG)
    calc_elv = CalculadoraELV(proveedor)
    T_F, _ = calc_elv.burbuja_T(P_SISTEMA_FUG, z_F)
    corriente_F = Corriente(NOMBRES_FUG, z_F, 100.0, T_F, P_SISTEMA_FUG)

    analizador = AnalizadorFUG(calc_elv, proveedor, NOMBRES_FUG, z_F, q=1.0,
                                P_sistema=P_SISTEMA_FUG, indice_LK=1, indice_HK=2)

    # ColumnaDestilacion.a_operacion_unitaria en vez de un adaptador
    # escrito a mano -- misma columna, misma clase, ahora enchufable
    # directo a un DiagramaFlujo.
    columna_destilacion = ColumnaDestilacion("fug", analizador_fug=analizador)
    columna = columna_destilacion.a_operacion_unitaria(
        "columna",
        variables_entrada_extra=("recuperacion_LK_D", "recuperacion_HK_B", "R"),
        variables_salida_extra=("N", "R_min"),
    )

    def resolver_bomba(entrada, factor_P):
        salida = Corriente(entrada.nombres, entrada.composicion, entrada.flujo_molar,
                            entrada.T, entrada.P * factor_P)
        return {"salida": salida}

    bomba = OperacionUnitaria(
        "bomba", variables_entrada=("entrada", "factor_P"), variables_salida=("salida",),
        resolver_fn=resolver_bomba,
    )

    diagrama = DiagramaFlujo()
    diagrama.agregar_operacion(columna)
    diagrama.agregar_operacion(bomba)
    diagrama.conectar("columna", "D", "bomba", "entrada")

    resultado = diagrama.resolver(
        **{
            "columna.F": corriente_F,
            "columna.recuperacion_LK_D": 0.98,
            "columna.recuperacion_HK_B": 0.98,
            "columna.R": 3.0,
            "bomba.factor_P": 2.0,
        }
    )

    corriente_D = resultado["pool"]["columna.D"]
    corriente_bombeada = resultado["pool"]["bomba.salida"]

    print(f"Cadena columna->bomba (sin reciclo), resuelta en una sola llamada:")
    print(f"  N = {resultado['pool']['columna.N']:.4f}  (resuelto por: {resultado['resueltos_por']['columna.N']})")
    print(f"  columna.D       = {corriente_D}")
    print(f"  bomba.salida    = {corriente_bombeada}  <- resuelto por: {resultado['resueltos_por']['bomba.salida']}")

    mismo_flujo = np.isclose(corriente_bombeada.flujo_molar, corriente_D.flujo_molar)
    mismo_T = np.isclose(corriente_bombeada.T, corriente_D.T)
    P_correcta = np.isclose(corriente_bombeada.P, corriente_D.P * 2.0)
    composicion_igual = np.allclose(corriente_bombeada.composicion, corriente_D.composicion)
    print(f"  Bomba preservo flujo/T/composicion y solo cambio P (x2): "
          f"{mismo_flujo and mismo_T and P_correcta and composicion_igual}")
    print(f"  Completo: {resultado['completo']}")

    assert mismo_flujo and mismo_T and P_correcta and composicion_igual
    assert resultado["completo"]
    # Los valores de la columna deben coincidir exactamente con los ya
    # validados en tests/validar_fug.py para el mismo caso (mismo z_F,
    # recuperaciones, R).
    assert np.isclose(resultado["pool"]["columna.N"], 9.434906966491038, atol=1e-6)


def validar_reciclo_con_forma_cerrada():
    """
    Mezclador (alimentacion fresca + reciclo) -> Divisor (producto 70%,
    reciclo 30%) -> el reciclo vuelve al mezclador. Composicion/T
    identicas en todo el lazo (deliberado: aisla la prueba a la
    CONVERGENCIA de flujo, sin mezclar con la pregunta de balance de
    energia -- eso ya se valido aparte en tests/validar_corriente.py).

    Balance de materia analitico (F0=alimentacion fresca, f=fraccion a
    producto, R=reciclo en estado estacionario):
        R = (1-f) * (F0 + R)  =>  R = F0*(1-f)/f
    Con F0=100, f=0.7: R = 100*0.3/0.7 = 42.857142857... , Producto=F0=100.
    """
    NOMBRES = ["n-butane"]
    proveedor = ProveedorTermodinamico(NOMBRES)
    F0 = 100.0
    T_COMUN = 350.0
    P_COMUN = 101325.0
    FRACCION_PRODUCTO = 0.7

    corriente_fresca = Corriente(NOMBRES, [1.0], F0, T_COMUN, P_COMUN)

    def resolver_mezclador(fresca, reciclo):
        return {"salida": mezclar_corrientes([fresca, reciclo], proveedor)}

    def resolver_divisor(entrada):
        producto, reciclo = dividir_corriente(entrada, [FRACCION_PRODUCTO, 1.0 - FRACCION_PRODUCTO])
        return {"producto": producto, "reciclo": reciclo}

    mezclador = OperacionUnitaria(
        "mezclador", variables_entrada=("fresca", "reciclo"), variables_salida=("salida",),
        resolver_fn=resolver_mezclador,
    )
    divisor = OperacionUnitaria(
        "divisor", variables_entrada=("entrada",), variables_salida=("producto", "reciclo"),
        resolver_fn=resolver_divisor,
    )

    diagrama = DiagramaFlujo()
    diagrama.agregar_operacion(mezclador)
    diagrama.agregar_operacion(divisor)
    diagrama.conectar("mezclador", "salida", "divisor", "entrada")
    conexion_reciclo = ("divisor", "reciclo", "mezclador", "reciclo")
    diagrama.conectar(*conexion_reciclo)

    # Primero: SIN romper el reciclo, confirmar que de verdad queda
    # bloqueado (ninguna operacion puede dispararse -- ciclo real).
    resultado_sin_romper = diagrama.resolver(**{"mezclador.fresca": corriente_fresca})
    print(f"Sin romper el reciclo -- ¿queda completo? {resultado_sin_romper['completo']} "
          f"(debe ser False: es un ciclo real, no deberia poder resolverse solo)")
    assert not resultado_sin_romper["completo"]

    valor_inicial = Corriente(NOMBRES, [1.0], 0.0, T_COMUN, P_COMUN)  # supuesto deliberadamente malo (flujo 0)
    resultado = diagrama.resolver_con_reciclo(
        conexion_ruptura=conexion_reciclo, valor_inicial=valor_inicial, tolerancia=1e-8,
        **{"mezclador.fresca": corriente_fresca},
    )

    reciclo_convergido = resultado["pool"]["divisor.reciclo"]
    producto_final = resultado["pool"]["divisor.producto"]

    R_analitico = F0 * (1.0 - FRACCION_PRODUCTO) / FRACCION_PRODUCTO

    print(f"\nCon sustitucion sucesiva (supuesto inicial deliberadamente malo: flujo=0):")
    print(f"  Convergio: {resultado['convergencia_reciclo']} en {resultado['iteraciones_reciclo']} iteraciones")
    print(f"  Reciclo convergido = {reciclo_convergido.flujo_molar:.6f} mol/s  (analitico: {R_analitico:.6f})")
    print(f"  Producto final     = {producto_final.flujo_molar:.6f} mol/s  (analitico: {F0:.6f}, == alimentacion fresca)")

    assert resultado["convergencia_reciclo"]
    assert np.isclose(reciclo_convergido.flujo_molar, R_analitico, atol=1e-4)
    assert np.isclose(producto_final.flujo_molar, F0, atol=1e-4)
    # Balance de materia global: todo lo que entra (fresca) debe salir (producto), nada se acumula.
    assert np.isclose(producto_final.flujo_molar, corriente_fresca.flujo_molar, atol=1e-4)


if __name__ == "__main__":
    print("=== Validación 1: cadena real sin reciclo (columna FUG -> bomba) ===")
    validar_cadena_sin_reciclo()

    print("\n=== Validación 2: reciclo con solución analítica exacta (mezclador + divisor) ===")
    validar_reciclo_con_forma_cerrada()

    print("\nTodas las validaciones de DiagramaFlujo pasaron.")
