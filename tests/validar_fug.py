"""
Script de validacion numerica de core/fug.py (AnalizadorFUG: Fenske-
Underwood-Gilliland para destilacion multicomponente). No es parte de
la aplicacion.

Ejecutar desde la raiz del proyecto:
    python tests/validar_fug.py

Sistema de prueba: propano/n-butano/n-pentano/n-hexano a 5 atm -- una
serie de alcanos, ejemplo clasico de FUG.

Hallazgos reales durante la construccion (documentados aqui y en
roadmap.md):
    - Hueco de la directiva resuelto con bootstrap estandar: T_D/T_B
      (necesarios para el alfa promedio de 3 puntos) necesitan una
      composicion de producto que todavia no existe -- se construye una
      distribucion inicial (no-clave 100% a un producto, claves segun
      recuperacion especificada) y se refina con la propia formula de
      Fenske una vez que N_min esta disponible.
    - Caso sharp-split (claves adyacentes en volatilidad, propano y
      hexano NO distribuyen): verificado exhaustivamente, resultados
      fisicamente coherentes (recuperaciones exactas, N>N_min, T
      creciente de domo a fondo).
    - Caso de multiples raices de Underwood (forzando LK/HK NO
      adyacentes, saltando n-pentano a proposito): dio R_min NEGATIVO.
      Se verifico a mano (resolviendo el sistema 2x2 con calculadora)
      que el codigo SI resuelve correctamente el sistema que arma --
      no es un bug de traduccion ecuacion->codigo. Pero el resultado no
      es fisico, lo que sugiere que elegir claves no adyacentes
      (saltandose un componente) no es una forma valida de plantear
      Underwood -- las "raices multiples" deberian surgir de forma
      natural (un componente que realmente distribuye entre claves
      ADYACENTES), no forzarse. Se deja usar esta rama con precaucion,
      caso por caso, no como default de confianza ciega.
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

NOMBRES = ["propane", "n-butane", "n-pentane", "n-hexane"]
P_SISTEMA = 101325.0 * 5
Z_F = np.array([0.10, 0.30, 0.30, 0.30])
Q = 1.0


def _construir_analizador(idx_LK, idx_HK):
    proveedor = ProveedorTermodinamico(NOMBRES)
    calc_elv = CalculadoraELV(proveedor)
    return AnalizadorFUG(calc_elv, proveedor, NOMBRES, Z_F, Q, P_SISTEMA, idx_LK, idx_HK)


def validar_sharp_split():
    analizador = _construir_analizador(idx_LK=1, idx_HK=2)  # n-butano / n-pentano (adyacentes)
    reporte = analizador.reporte_completo(recuperacion_LK_D=0.98, recuperacion_HK_B=0.98, R=3.0)

    print(f"N_min={reporte['N_min']:.4f}  R_min={reporte['R_min']:.4f}  "
          f"N(R=3.0)={reporte['N']:.4f}  theta={reporte['theta']}")
    print(f"T_D={reporte['T_D']:.2f} K < T_F={reporte['T_F']:.2f} K < T_B={reporte['T_B']:.2f} K "
          f"(orden esperado: {reporte['T_D'] < reporte['T_F'] < reporte['T_B']})")

    print("Distribución (recuperación clave debe ser 98% exacto):")
    for i, nombre in enumerate(NOMBRES):
        recuperacion_D = reporte["d"][i] / Z_F[i]
        print(f"  {nombre:12s}  d={reporte['d'][i]:.4f}  b={reporte['b'][i]:.4f}  "
              f"recuperación en D={recuperacion_D:.4f}")

    print("Sensibilidad N vs R (debe decrecer monótonamente, R>R_min siempre):")
    for R in (1.0, 2.0, 4.0, 8.0):
        print(f"  R={R:.1f}  N={analizador.calcular_etapas_reales(R, reporte['R_min']):.3f}")

    return reporte


def validar_multiples_raices():
    # LK=n-butano, HK=n-hexano -- salta n-pentano a proposito, para forzar
    # el camino de multiples raices y poder inspeccionarlo.
    analizador = _construir_analizador(idx_LK=1, idx_HK=3)

    # Este caso da un R_min NEGATIVO (claves no adyacentes, camino de
    # multiples raices). Antes el test solo lo IMPRIMIA como curiosidad y
    # reporte_completo seguia adelante, devolviendo un numero de etapas
    # calculado sobre un minimo imposible -- un resultado de aspecto
    # razonable construido sobre basura. Ahora se exige que el metodo lo
    # RECHACE y que el mensaje diga por que.
    fenske = analizador.preparar_fenske(recuperacion_LK_D=0.98, recuperacion_HK_B=0.98)
    underwood = analizador.resolver_underwood()
    print(f"theta (2 raíces esperadas) = {underwood['theta']}")
    print(f"R_min = {underwood['R_min']:.4f}  <-- NEGATIVO, no físico")
    assert underwood["R_min"] < 0, "este caso deberia seguir dando R_min negativo"

    try:
        analizador.reporte_completo(recuperacion_LK_D=0.98, recuperacion_HK_B=0.98, R=3.0)
        raise AssertionError("reporte_completo deberia rechazar un R_min negativo")
    except ValueError as e:
        mensaje = str(e)
        assert "negativo" in mensaje and "no es fisico" in mensaje, mensaje
        print(f"[esperado] se rechaza con motivo: {mensaje[:100]}...")

    # El balance de materia de Fenske si debe cerrar aunque Underwood falle.
    balance_ok = np.allclose(fenske["d"] + fenske["b"], Z_F)
    print(f"Balance de materia por componente (d+b == z_F): {balance_ok}")
    assert balance_ok


def validar_otro_par_de_claves():
    """LK=propano, HK=n-butano -- otro par adyacente; ahora n-pentano y n-hexano son 'no clave' pesados."""
    analizador = _construir_analizador(idx_LK=0, idx_HK=1)
    reporte = analizador.reporte_completo(recuperacion_LK_D=0.97, recuperacion_HK_B=0.97, R=2.5)

    print(f"N_min={reporte['N_min']:.4f}  R_min={reporte['R_min']:.4f}  N(R=2.5)={reporte['N']:.4f}")
    for i, nombre in enumerate(NOMBRES):
        recuperacion_D = reporte["d"][i] / Z_F[i]
        print(f"  {nombre:12s}  recuperación en D={recuperacion_D:.4f}")
    balance_ok = np.allclose(reporte["d"] + reporte["b"], Z_F)
    print(f"Balance de materia: {balance_ok}")


def validar_sensibilidad_recuperaciones():
    """Mismo par de claves, recuperaciones más laxas vs más estrictas -- N_min y R_min deben subir con la exigencia."""
    analizador = _construir_analizador(idx_LK=1, idx_HK=2)
    anterior_N_min = 0.0
    for recuperacion in (0.90, 0.95, 0.99, 0.999):
        reporte = analizador.reporte_completo(
            recuperacion_LK_D=recuperacion, recuperacion_HK_B=recuperacion, R=3.0
        )
        sube = reporte["N_min"] > anterior_N_min
        print(f"  recuperación={recuperacion:.3f}  N_min={reporte['N_min']:.4f}  "
              f"R_min={reporte['R_min']:.4f}  (N_min sube respecto a la anterior: {sube})")
        anterior_N_min = reporte["N_min"]


def validar_composicion_distinta():
    """Alimentación muy distinta (un componente dominante) -- confirma que el bootstrap no se rompe."""
    proveedor = ProveedorTermodinamico(NOMBRES)
    calc_elv = CalculadoraELV(proveedor)
    z_F_alt = np.array([0.05, 0.70, 0.20, 0.05])
    analizador = AnalizadorFUG(calc_elv, proveedor, NOMBRES, z_F_alt, Q, P_SISTEMA, indice_LK=1, indice_HK=2)
    reporte = analizador.reporte_completo(recuperacion_LK_D=0.98, recuperacion_HK_B=0.98, R=3.0)

    print(f"N_min={reporte['N_min']:.4f}  R_min={reporte['R_min']:.4f}")
    balance_ok = np.allclose(reporte["d"] + reporte["b"], z_F_alt)
    print(f"Balance de materia: {balance_ok}  (D+B={reporte['D'] + reporte['B']:.6f}, debe ser 1.0)")


def validar_multiraiz_natural():
    """
    Con claves ADYACENTES, revisa si algún componente no-clave cae
    naturalmente entre alpha_HK y alpha_LK (lo que activaría el camino
    de múltiples raíces SIN forzar nada). Para esta serie de alcanos,
    bastante ideal, se espera que NO ocurra (el orden de Tb coincide con
    el de volatilidad) -- este test lo confirma en vez de asumirlo.
    """
    analizador = _construir_analizador(idx_LK=1, idx_HK=2)
    analizador.preparar_fenske(recuperacion_LK_D=0.98, recuperacion_HK_B=0.98)
    distribuidos = [NOMBRES[i] for i in analizador._componentes_distribuidos_para_underwood()]
    print(f"Componentes distribuidos con claves adyacentes: {distribuidos}")
    print("(se esperan solo las 2 claves -- si aparece alguno más, hay multirraíz NATURAL aquí)")


def validar_fenske_2puntos_vs_3puntos():
    """
    Chequeo cruzado: Fenske con promedio de 2 puntos (domo/fondo, sin
    alimentación) vs el de 3 puntos que usa AnalizadorFUG -- deben ser
    parecidos (mismo orden de magnitud) pero no idénticos.
    """
    analizador = _construir_analizador(idx_LK=1, idx_HK=2)
    reporte = analizador.reporte_completo(recuperacion_LK_D=0.98, recuperacion_HK_B=0.98, R=3.0)

    alpha_D = analizador._alpha_relativo(reporte["T_D"], reporte["x_D"])
    alpha_B = analizador._alpha_relativo(reporte["T_B"], reporte["x_B"])
    alpha_avg_2pt = np.sqrt(alpha_D * alpha_B)

    d0, b0 = analizador._distribucion_inicial(0.98, 0.98)
    N_min_2pt = np.log(
        (d0[analizador.idx_LK] / b0[analizador.idx_LK]) * (b0[analizador.idx_HK] / d0[analizador.idx_HK])
    ) / np.log(alpha_avg_2pt[analizador.idx_LK])

    diferencia_pct = abs(reporte["N_min"] - N_min_2pt) / reporte["N_min"] * 100
    print(f"N_min (3 puntos: domo/alim/fondo) = {reporte['N_min']:.4f}")
    print(f"N_min (2 puntos: domo/fondo)      = {N_min_2pt:.4f}")
    print(f"Diferencia relativa: {diferencia_pct:.2f}%  (se espera pequeña, mismo orden de magnitud)")


if __name__ == "__main__":
    print("=== Validación 1: caso sharp-split (claves adyacentes) ===")
    validar_sharp_split()

    print("\n=== Validación 2: múltiples raíces de Underwood (claves NO adyacentes, caso límite) ===")
    validar_multiples_raices()

    print("\n=== Validación 3: otro par de claves adyacentes (propano/n-butano) ===")
    validar_otro_par_de_claves()

    print("\n=== Validación 4: sensibilidad a la recuperación especificada ===")
    validar_sensibilidad_recuperaciones()

    print("\n=== Validación 5: alimentación con composición distinta ===")
    validar_composicion_distinta()

    print("\n=== Validación 6: ¿surge multirraíz de forma natural con claves adyacentes? ===")
    validar_multiraiz_natural()

    print("\n=== Validación 7: Fenske con 2 puntos vs 3 puntos ===")
    validar_fenske_2puntos_vs_3puntos()
