"""
Validacion de las especificaciones de diseno y de los barridos.

Lo que se prueba no es "sale un numero" sino que la respuesta inversa
coincide con la directa: si el solver dice que hacen falta R=2.2416 para
N=12, entonces evaluar el metodo con ese R tiene que dar 12 etapas. Es la
unica forma de saber que el lazo exterior no esta mintiendo.

Y la seccion 2 es la que justifica haberlo construido: una especificacion
cuyo OBJETIVO y cuya variable MANIPULADA viven en equipos distintos, con
dos reciclos en medio. Eso es lo que un simulador secuencial-modular hace
con dificultad y lo que aqui sale de orquestar maquinaria que ya existia.

Ejecutar desde la raiz del proyecto:
    python tests/validar_especificaciones.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np

from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.elv import CalculadoraELV
from thermodynamics.reaccion import GestorReaccion
from core.mccabe_thiele import EvaluadorMcCabeThiele, SolucionadorMcCabeThiele
from core.diagrama_corrientes import DiagramaCorrientes
from core.especificaciones import (
    Especificacion, grados_de_libertad_con_especificaciones,
)

fallos = []


def check(nombre, ok, detalle=""):
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}{(' -- ' + detalle) if detalle else ''}")
    if not ok:
        fallos.append(nombre)


BT = ["benzene", "toluene"]
P1 = 101325.0
PROV = ProveedorTermodinamico(BT)
ELV = CalculadoraELV(PROV)
EVAL_MT = EvaluadorMcCabeThiele(ELV, BT, P_sistema=P1)
SOL_MT = SolucionadorMcCabeThiele(EVAL_MT)


def columna():
    d = DiagramaCorrientes(BT, proveedor=PROV)
    for c in ("alim", "dest", "fondo"):
        d.agregar_corriente(c)
    d.agregar_columna_binaria("col1", SOL_MT, "alim", "dest", "fondo", q_fijo=1.0)
    return d


BASE = {"alim.F": 100.0, "alim.x0": 0.40, "dest.x0": 0.95, "fondo.x0": 0.05}

# ======================================================================
print("=" * 74)
print("1. UNA ESPECIFICACIÓN, Y EL CONTEO DE GRADOS DE LIBERTAD")
print("=" * 74)

d = columna()
spec = [Especificacion(objetivo="col1.N", valor=12.0, manipulada="col1.R",
                       minimo=1.6, maximo=20.0)]

sin_spec = d.grados_de_libertad(BASE)["grados_de_libertad"]
con_spec = grados_de_libertad_con_especificaciones(d, BASE, spec)["grados_de_libertad"]
check("1.1 Sin la especificación falta un dato (GL = 1)", sin_spec == 1, f"GL={sin_spec}")
check("1.2 Con ella el problema queda cerrado (GL = 0)", con_spec == 0,
      "la especificación no reformula el problema: lo CIERRA")

res = d.resolver_con_especificaciones(spec, **BASE)
e = res["especificaciones"]["cumplidas"][0]
print(f"\n  R = {e['valor']:.6f}  →  N = {e['obtenido']:.8f}   "
      f"({res['especificaciones']['evaluaciones']} resoluciones del diagrama)")
check("1.3 El objetivo se alcanza", abs(e["error"]) < 1e-6, f"error {e['error']:.2e}")

# LA comprobación: la respuesta inversa contra la directa, por otro camino.
directo = EVAL_MT.calcular_escalones(z_F=0.40, q=1.0, x_D=0.95, x_B=0.05, R=e["valor"])
check("1.4 Evaluar el método con ese R reproduce N = 12",
      abs(directo["N"] - 12.0) < 1e-6,
      f"N directo = {directo['N']:.8f}, sin pasar por el lazo exterior")

# ======================================================================
print("\n" + "=" * 74)
print("2. OBJETIVO Y VARIABLE EN EQUIPOS DISTINTOS, CON DOS RECICLOS EN MEDIO")
print("=" * 74)

MTBE = ["isobutene", "methanol", "mtbe"]
NU = [-1.0, -1.0, 1.0]
PR = 5 * P1
PROV_M = ProveedorTermodinamico(MTBE)
GESTOR = GestorReaccion(PROV_M, np.array(NU), A=1e4, Ea=45000.0)


def planta():
    g = DiagramaCorrientes(MTBE, proveedor=PROV_M)
    for c in ("fresco", "mezcla", "caliente", "crudo", "vapor", "liquido",
              "producto", "cola", "purga", "reciclo"):
        g.agregar_corriente(c)
    g.agregar_mezclador("M1", entradas=["fresco", "reciclo"], salida="mezcla")
    g.agregar_intercambiador("E1", "mezcla", "caliente", T_salida=350.0)
    g.agregar_reactor_cstr("R1", "caliente", "crudo", NU, gestor_reaccion=GESTOR,
                           modo_reaccion="equilibrio", con_balance_energia=False)
    g.agregar_flash("FL1", "crudo", "vapor", "liquido", P_operacion=PR, Q_por_mol=0.0)
    g.agregar_separador("SEP", "liquido", "cola", "producto",
                        recuperaciones=[0.9, 0.9, 0.05])
    g.agregar_divisor("D1", "cola", salidas=["purga", "reciclo"], fracciones=[0.3, 0.7])
    return g


DATOS_P = {"fresco.F": 100.0, "fresco.T": 320.0, "fresco.P": PR,
           "fresco.x0": 0.5, "fresco.x1": 0.5}

# Referencia: qué pureza sale con la T del reactor sin especificar.
g0 = planta()
ref = g0.resolver(**{**DATOS_P, "R1.T": 360.0})
pureza_ref = ref["pool"]["producto.x2"]
print(f"\n  Con R1.T = 360 K: MTBE en el producto = {pureza_ref:.6f}")

OBJETIVO = round(float(pureza_ref) + 0.02, 4)
g = planta()
spec2 = [Especificacion(objetivo="producto.x2", valor=OBJETIVO,
                        manipulada="R1.T", minimo=330.0, maximo=370.0)]
res2 = g.resolver_con_especificaciones(spec2, tolerancia_reciclo=1e-10,
                                       max_ciclos_reciclo=300, **DATOS_P)
e2 = res2["especificaciones"]["cumplidas"][0]
print(f"  Objetivo {OBJETIVO}  →  T del reactor = {e2['valor']:.4f} K, "
      f"obtenido {e2['obtenido']:.6f}")
print(f"  ({res2['especificaciones']['evaluaciones']} resoluciones, cada una con sus reciclos)")

check("2.1 Se alcanza un objetivo que está TRAS dos equipos y un reciclo",
      abs(e2["error"]) < 1e-6, f"error {e2['error']:.2e}")
check("2.2 La variable manipulada quedó dentro de su rango físico",
      330.0 <= e2["valor"] <= 370.0)

# Y vuelta: resolver con esa T, sin especificación, da la misma pureza.
g_v = planta()
vuelta = g_v.resolver(tolerancia_reciclo=1e-10, max_ciclos_reciclo=300,
                      **{**DATOS_P, "R1.T": e2["valor"]})
check("2.3 Resolver con esa T, sin especificación, reproduce la pureza",
      abs(vuelta["pool"]["producto.x2"] - OBJETIVO) < 1e-6,
      f"{vuelta['pool']['producto.x2']:.8f} frente a {OBJETIVO}")

# ======================================================================
print("\n" + "=" * 74)
print("3. DOS ESPECIFICACIONES A LA VEZ")
print("=" * 74)

d3 = DiagramaCorrientes(BT, proveedor=PROV)
for c in ("alim", "dest", "fondo"):
    d3.agregar_corriente(c)
d3.agregar_columna_binaria("col1", SOL_MT, "alim", "dest", "fondo", q_fijo=1.0)

# N etapas moviendo R, y a la vez un caudal de destilado moviendo x_B.
base3 = {"alim.F": 100.0, "alim.x0": 0.40, "dest.x0": 0.95}
specs3 = [
    Especificacion(objetivo="col1.N", valor=11.0, manipulada="col1.R",
                   minimo=1.6, maximo=20.0),
    Especificacion(objetivo="dest.F", valor=36.0, manipulada="fondo.x0",
                   minimo=0.01, maximo=0.20),
]
try:
    res3 = d3.resolver_con_especificaciones(specs3, **base3)
    cumplidas = res3["especificaciones"]["cumplidas"]
    for c_ in cumplidas:
        print(f"  {c_['objetivo']} → {c_['pedido']}  moviendo {c_['manipulada']}"
              f" = {c_['valor']:.6f}   (obtenido {c_['obtenido']:.6f})")
    check("3.1 Las dos se cumplen a la vez",
          all(abs(c_["error"]) < 1e-5 for c_ in cumplidas),
          f"errores: {[f'{c_[chr(101)+chr(114)+chr(114)+chr(111)+chr(114)]:.1e}' for c_ in cumplidas]}")
except ValueError as err:
    check("3.1 Las dos se cumplen a la vez", False, str(err)[:130])

# ======================================================================
print("\n" + "=" * 74)
print("4. LO QUE TIENE QUE RECHAZAR")
print("=" * 74)

try:
    Especificacion(objetivo="col1.R", valor=3.0, manipulada="col1.R",
                   minimo=1.0, maximo=5.0)
    check("4.1 Objetivo = variable manipulada rechazado", False, "no lanzó")
except ValueError as err:
    check("4.1 Objetivo = variable manipulada rechazado", "a la vez" in str(err))

try:
    Especificacion(objetivo="col1.N", valor=10.0, manipulada="col1.R",
                   minimo=9.0, maximo=2.0)
    check("4.2 Rango al revés rechazado", False, "no lanzó")
except ValueError as err:
    check("4.2 Rango al revés rechazado", "al revés" in str(err) or "vacío" in str(err))

d4 = columna()
try:
    d4.resolver_con_especificaciones(
        [Especificacion(objetivo="col1.N", valor=12.0, manipulada="col1.R",
                        minimo=1.6, maximo=20.0)],
        **{**BASE, "col1.R": 3.0},
    )
    check("4.3 Dar la variable manipulada como dato se rechaza", False, "no lanzó")
except ValueError as err:
    check("4.3 Dar la variable manipulada como dato se rechaza",
          "dato Y como variable manipulada" in str(err))

d5 = columna()
try:
    d5.resolver_con_especificaciones(
        [Especificacion(objetivo="col1.N", valor=500.0, manipulada="col1.R",
                        minimo=1.6, maximo=20.0)],
        **BASE,
    )
    check("4.4 Objetivo inalcanzable: se dice el rango que SÍ se recorre", False, "no lanzó")
except ValueError as err:
    check("4.4 Objetivo inalcanzable: se dice el rango que SÍ se recorre",
          "solo recorre" in str(err), str(err)[:110])

d6 = columna()
try:
    d6.resolver_con_especificaciones(
        [Especificacion(objetivo="col1.N", valor=12.0, manipulada="col1.R",
                        minimo=1.0, maximo=20.0)],   # 1.0 está bajo R_min
        **BASE,
    )
    check("4.5 Valor inviable de la manipulada: el mensaje apunta ahí", False, "no lanzó")
except ValueError as err:
    check("4.5 Valor inviable de la manipulada: el mensaje apunta ahí",
          "no sea viable" in str(err), str(err)[:110])

# ======================================================================
print("\n" + "=" * 74)
print("5. BARRIDOS DE SENSIBILIDAD")
print("=" * 74)

d7 = columna()
tabla = d7.barrido("col1.R", [1.6, 2.0, 2.5, 3.0, 4.0, 6.0, 10.0],
                   seguir=["col1.N", "col1.Q_c"], **BASE)
print()
for fila in tabla:
    if fila["_completo"]:
        print(f"  R={fila['col1.R']:5.2f}  N={fila['col1.N']:7.3f}  "
              f"Q_c={fila['col1.Q_c']/1e6:6.3f} MW")
    else:
        print(f"  R={fila['col1.R']:5.2f}  -- {fila['_error'][:60]}")

buenas = [f for f in tabla if f["_completo"]]
check("5.1 El barrido devuelve una fila por valor", len(tabla) == 7)
check("5.2 N decrece monótonamente al subir R",
      all(np.diff([f["col1.N"] for f in buenas]) < 0),
      "más reflujo, menos etapas: el compromiso clásico")
check("5.3 Y Q_c crece: ese es el precio",
      all(np.diff([f["col1.Q_c"] for f in buenas]) > 0),
      f"de {buenas[0]['col1.Q_c']/1e6:.2f} a {buenas[-1]['col1.Q_c']/1e6:.2f} MW")

# Un punto que falla NO debe tumbar el barrido entero.
d8 = columna()
tabla2 = d8.barrido("col1.R", [1.0, 1.2, 2.0, 3.0], seguir=["col1.N"], **BASE)
fallidas = [f for f in tabla2 if not f["_completo"]]
check("5.4 Un punto inviable se anota y el barrido sigue",
      len(fallidas) >= 1 and len(tabla2) == 4,
      f"{len(fallidas)} punto(s) bajo R_min anotados, {4-len(fallidas)} resueltos")

print("\n" + "=" * 74)
if fallos:
    print(f"FALLARON {len(fallos)}:")
    for f in fallos:
        print("   - " + f)
    sys.exit(1)
print("TODO OK")
