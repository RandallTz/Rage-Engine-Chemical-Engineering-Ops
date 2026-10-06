"""
Validacion de core/diagrama_corrientes.py -- el modelo donde la
corriente es un elemento de primera clase y sus variables son escalares
del pool.

Lo que hay que demostrar aqui, y que el modelo anterior (puerto =
Corriente atomica) NO podia hacer:
    1. Resolver HACIA ADELANTE (alimentacion -> productos).
    2. Resolver HACIA ATRAS (productos -> alimentacion) con las MISMAS
       ecuaciones, sin declarar nada distinto.
    3. Mezclar direcciones: datos sueltos de varias corrientes a la vez.
    4. Que el cierre de composicion evite tener que dar x1 si ya se dio x0.
    5. Que el diagnostico senale donde faltan datos.

Ejecutar desde la raiz del proyecto:
    python tests/validar_diagrama_corrientes.py
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
from core.diagrama_corrientes import DiagramaCorrientes

NOMBRES = ["benzene", "toluene"]
P = 101325.0

# Caso de referencia, ya validado en sesiones anteriores:
#   F=100, z_F=0.40, x_D=0.95, x_B=0.05  ->  D=38.8889, B=61.1111
#   con R=3.0597377228491056  ->  N=10
R_REF = 3.0597377228491056
D_REF, B_REF = 38.888888888888886, 61.111111111111114


def _diagrama():
    proveedor = ProveedorTermodinamico(NOMBRES)
    calc_elv = CalculadoraELV(proveedor)
    evaluador = EvaluadorMcCabeThiele(calc_elv, NOMBRES, P_sistema=P)
    solucionador = SolucionadorMcCabeThiele(evaluador)

    diagrama = DiagramaCorrientes(NOMBRES)
    for s in ("alim", "dest", "fondo"):
        diagrama.agregar_corriente(s)
    diagrama.agregar_columna_binaria("col1", solucionador, "alim", "dest", "fondo")
    return diagrama


def validar_hacia_adelante():
    diagrama = _diagrama()
    resultado = diagrama.resolver(**{
        "alim.F": 100.0, "alim.x0": 0.40,
        "dest.x0": 0.95, "fondo.x0": 0.05,
        "col1.q": 1.0, "col1.R": R_REF,
    })
    pool = resultado["pool"]
    print(f"  dest.F = {pool['dest.F']:.4f}  (esperado {D_REF:.4f})")
    print(f"  fondo.F = {pool['fondo.F']:.4f}  (esperado {B_REF:.4f})")
    print(f"  col1.N = {pool['col1.N']:.4f}  (esperado 10)")
    print(f"  dest.T = {pool['dest.T']:.2f} K   fondo.T = {pool['fondo.T']:.2f} K")
    print(f"  alim.x1 = {pool['alim.x1']:.4f}  (cierre: 1 - 0.40, NO se dio a mano)")
    assert np.isclose(pool["dest.F"], D_REF, atol=1e-4)
    assert np.isclose(pool["fondo.F"], B_REF, atol=1e-4)
    assert np.isclose(pool["col1.N"], 10.0, atol=1e-3)
    assert np.isclose(pool["alim.x1"], 0.60, atol=1e-9)
    return pool


def validar_hacia_atras():
    """Se dan los DOS PRODUCTOS completos y se pide la alimentacion."""
    diagrama = _diagrama()
    resultado = diagrama.resolver(**{
        "dest.F": D_REF, "dest.x0": 0.95,
        "fondo.F": B_REF, "fondo.x0": 0.05,
        "col1.q": 1.0, "col1.R": R_REF,
    })
    pool = resultado["pool"]
    print(f"  alim.F = {pool['alim.F']:.4f}  (esperado 100)")
    print(f"  alim.x0 = {pool['alim.x0']:.4f}  (esperado 0.40)")
    print(f"  col1.N = {pool['col1.N']:.4f}  (esperado 10)")
    assert np.isclose(pool["alim.F"], 100.0, atol=1e-4)
    assert np.isclose(pool["alim.x0"], 0.40, atol=1e-6)
    assert np.isclose(pool["col1.N"], 10.0, atol=1e-3)


def validar_mezclando_direcciones():
    """
    Datos sueltos de corrientes distintas: flujo de la alimentacion,
    pureza de los dos productos, y N como objetivo -- se pide el reflujo.
    Es "diseno inverso": N es dato y R es incognita.
    """
    diagrama = _diagrama()
    resultado = diagrama.resolver(**{
        "alim.F": 100.0, "alim.x0": 0.40,
        "dest.x0": 0.95, "fondo.x0": 0.05,
        "col1.q": 1.0, "col1.N": 10.0,
    })
    pool = resultado["pool"]
    print(f"  col1.R = {pool['col1.R']:.6f}  (esperado {R_REF:.6f})")
    print(f"  dest.F = {pool['dest.F']:.4f}   Q_c = {pool['col1.Q_c']/1e6:.4f} MW")
    assert np.isclose(pool["col1.R"], R_REF, atol=1e-4)
    assert np.isclose(pool["dest.F"], D_REF, atol=1e-4)


def validar_diagnostico_datos_insuficientes():
    """Con muy pocos datos, el diagrama debe decir QUE falta, no fallar en silencio."""
    diagrama = _diagrama()
    resultado = diagrama.resolver(**{"alim.F": 100.0, "alim.x0": 0.40})
    print(f"  completo = {resultado['completo']} (esperado False)")
    bloqueados = [d for d in resultado["diagnostico"] if not d["puede_dispararse"]]
    print(f"  bloques bloqueados: {len(bloqueados)}")
    for d in bloqueados[:3]:
        print(f"    - {d['bloque']}: faltan {d['faltantes_para_disparar'][:4]}")
    assert not resultado["completo"]
    assert bloqueados, "deberia haber al menos un bloque senalado como bloqueado"


def validar_bloque_con_varias_ecuaciones():
    """
    Un bloque NO es una ecuacion, y la verificacion de consistencia tiene
    que comprobarlas TODAS.

    El caso que lo destapo: una bomba ideal a la que se le dan la presion
    de entrada, el factor de compresion Y la presion de salida. Son tres
    condiciones sobre dos variables, y 3 x 101325 no es 100000: son
    incompatibles.

    El simulador respondia "resuelto por completo", sin incidencias, y
    conservaba la presion de salida dada. El motivo no era la bomba sino
    `verificar_consistencia`: comparaba SOLO la variable que habia
    olvidado y paraba en la primera comprobacion que saliera bien. Eso
    vale si cada bloque es una ecuacion, y el de la bomba empaqueta n+2
    (F, T, P y las composiciones): la comprobacion recaia sobre la
    igualdad de caudales, salia bien, y la ecuacion de presion no se
    evaluaba nunca.
    """
    from thermodynamics.proveedor import ProveedorTermodinamico

    nombres = ["benzene", "toluene"]
    proveedor = ProveedorTermodinamico(nombres)
    masas = [float(c.MW) for c in proveedor.componentes]

    def bomba():
        d = DiagramaCorrientes(nombres, masas_molares=masas, proveedor=proveedor)
        for s in ("s1", "s2"):
            d.agregar_corriente(s)
        d.agregar_bomba("b1", "s1", "s2")
        return d

    entrada = {"s1.F": 100.0, "s1.T": 350.0, "s1.P": 101325.0,
               "s1.x0": 0.5, "s1.x1": 0.5, "b1.factor_P": 3.0}

    # --- el caso incompatible
    r = bomba().resolver(**entrada, **{"s2.P": 100000.0})
    print(f"  incompatible: completo={r['completo']}, "
          f"inconsistencias={len(r['inconsistencias'])}")
    assert r["inconsistencias"], (
        "dar s1.P, factor_P y s2.P a la vez es incompatible y tiene que detectarse"
    )
    incidencia = r["inconsistencias"][0]
    assert incidencia["variable"] == "s2.P", incidencia
    assert abs(incidencia["implicado"] - 303975.0) < 1e-6, incidencia
    print(f"    {incidencia['mensaje']}")

    # 'completo' sigue siendo True, y es correcto: significa que todas las
    # variables quedaron determinadas, no que el resultado sea fisico. Por
    # eso la incompatibilidad viaja en su propio campo y no disfrazada de
    # variable sin resolver.
    assert r["completo"], "todas las variables SI quedan determinadas"

    # --- el mismo diagrama con el dato compatible no debe quejarse
    compatible = bomba().resolver(**entrada, **{"s2.P": 303975.0})
    assert not compatible["inconsistencias"], compatible["inconsistencias"]
    print("  compatible (s2.P = 303975): sin incidencias")

    # --- y sin dar s2.P se calcula, como siempre
    abierto = bomba().resolver(**entrada)
    assert abs(abierto["pool"]["s2.P"] - 303975.0) < 1e-9
    assert not abierto["inconsistencias"]
    print(f"  sin dar s2.P: se calcula {abierto['pool']['s2.P']:.0f} Pa")

    # --- el conteo de grados de libertad tambien estaba al reves
    #
    # La bomba es invertible, asi que se quedaba con el valor por omision
    # de 1 ecuacion cuando impone n+2. Con eso, una bomba EXACTAMENTE
    # determinada reportaba GL = +3 ("faltan 3 datos") y la
    # sobre-especificada GL = +1, o sea el signo contrario de la verdad.
    exacta = bomba().grados_de_libertad(
        {"s1.F": 100.0, "s1.T": 350.0, "s1.P": 101325.0,
         "s1.x0": 0.5, "b1.factor_P": 3.0})
    assert exacta["grados_de_libertad"] == 0, exacta
    print(f"  bomba exactamente determinada: GL = {exacta['grados_de_libertad']}")

    sobra = bomba().grados_de_libertad({**entrada, "s2.P": 100000.0})
    assert sobra["grados_de_libertad"] < 0, sobra
    print(f"  bomba sobre-especificada:      GL = {sobra['grados_de_libertad']}")

    # --- y la comprobacion no debe inventar incidencias en los demas
    # equipos, que es el riesgo de mirar todo lo que un bloque devuelve
    d = DiagramaCorrientes(nombres, masas_molares=masas, proveedor=proveedor)
    for s in ("a", "b", "c", "d"):
        d.agregar_corriente(s)
    d.agregar_bomba("b1", "a", "b")
    d.agregar_intercambiador("ic1", "b", "c", Q_por_mol=2000.0)
    d.agregar_valvula("v1", "c", "d", P_salida=150000.0)
    cadena = d.resolver(**{"a.F": 100.0, "a.T": 340.0, "a.P": 101325.0,
                           "a.x0": 0.4, "b1.factor_P": 3.0})
    print(f"  cadena bomba+intercambiador+valvula: completo={cadena['completo']}, "
          f"inconsistencias={len(cadena['inconsistencias'])}")
    assert not cadena["inconsistencias"], cadena["inconsistencias"]


if __name__ == "__main__":
    print("=== 1. Hacia adelante (alimentación -> productos) ===")
    validar_hacia_adelante()

    print("\n=== 2. Hacia atrás (productos -> alimentación), MISMAS ecuaciones ===")
    validar_hacia_atras()

    print("\n=== 3. Mezclando direcciones (N dado, R incógnita) ===")
    validar_mezclando_direcciones()

    print("\n=== 4. Diagnóstico con datos insuficientes ===")
    validar_diagnostico_datos_insuficientes()

    print("\n=== 5. Un bloque no es una ecuación: hay que comprobarlas todas ===")
    validar_bloque_con_varias_ecuaciones()

    print("\nTodas las validaciones de DiagramaCorrientes pasaron.")
