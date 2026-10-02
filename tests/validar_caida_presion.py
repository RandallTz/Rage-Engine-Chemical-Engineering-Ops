"""
Validacion de la CAIDA DE PRESION en los equipos.

Por que esto era un hueco y no un refinamiento. Hasta aqui la presion se
propagaba por igualdad: `P_salida = P_entrada` en todos los equipos salvo
la valvula, el compresor y la bomba, que la fijan a proposito. Eso
significaba que **dos columnas en serie salian con presiones fisicamente
imposibles**, y que un intercambiador podia esconder que su corriente sale
en dos fases -- porque la fraccion vaporizada depende mucho de P y se
estaba evaluando a la presion equivocada.

Lo que se comprueba:

  1. Que con caida_P = 0 NADA cambia. Es el valor por omision, y la
     comprobacion existe porque es lo que garantiza que ningun diagrama
     guardado ni ningun numero ya validado se mueva.
  2. Que la presion baje exactamente lo pedido, y en las DOS direcciones
     (deducir la salida desde la entrada y la entrada desde la salida).
  3. Que las caidas se ACUMULEN al encadenar equipos, que es el caso por
     el que esto hacia falta.
  4. Que el estado de salida de un intercambiador se evalue a la presion
     de SALIDA. Es la parte con contenido fisico: evaluarlo a la de
     entrada subestima el vapor, y esconder que una corriente sale en dos
     fases es lo que rompe lo que viene detras.
  5. Que una caida imposible se rechace al CONSTRUIR, no a mitad de un
     lazo de reciclos.

Ejecutar desde la raiz del proyecto:
    python tests/validar_caida_presion.py
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
from thermodynamics.reaccion import GestorReaccion
from core.diagrama_corrientes import DiagramaCorrientes

fallos = []


def check(nombre, ok, detalle=""):
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}{(' -- ' + detalle) if detalle else ''}")
    if not ok:
        fallos.append(nombre)


BT = ["benzene", "toluene"]
prov = ProveedorTermodinamico(BT)
MASAS = [float(c.MW) for c in prov.componentes]
P1 = 101325.0
ATM = 101325.0


def diagrama():
    d = DiagramaCorrientes(BT, masas_molares=MASAS, proveedor=prov)
    return d


# ======================================================================
print("\n" + "=" * 74)
print("1. CON CAIDA CERO, NADA CAMBIA")
print("=" * 74)
# ======================================================================
# El valor por omision. Esta seccion es la que garantiza que todo lo que
# ya estaba validado siga igual.

base = {"s1.F": 100.0, "s1.T": 350.0, "s1.P": 2 * ATM, "s1.x0": 0.4, "s1.x1": 0.6}

d = diagrama()
for s in ("s1", "s2"):
    d.agregar_corriente(s)
d.agregar_intercambiador("ic1", "s1", "s2", Q_por_mol=5000.0)
sin = d.resolver(**base)

d = diagrama()
for s in ("s1", "s2"):
    d.agregar_corriente(s)
d.agregar_intercambiador("ic1", "s1", "s2", Q_por_mol=5000.0, caida_P=0.0)
cero = d.resolver(**base)

check("1.1 Sin el parámetro y con caida_P = 0 sale lo MISMO",
      sin["completo"] and cero["completo"]
      and abs(sin["pool"]["s2.P"] - cero["pool"]["s2.P"]) == 0.0
      and abs(sin["pool"]["s2.T"] - cero["pool"]["s2.T"]) == 0.0,
      f"P = {cero['pool']['s2.P']:.4f} Pa, T = {cero['pool']['s2.T']:.9f} K")
check("1.2 Y la presión de salida es la de entrada",
      cero["pool"]["s2.P"] == base["s1.P"], f"{cero['pool']['s2.P']:.1f} Pa")

T_sin_caida = cero["pool"]["s2.T"]
beta_sin_caida = cero["pool"]["ic1.beta_salida"]


# ======================================================================
print("\n" + "=" * 74)
print("2. LA PRESION BAJA LO PEDIDO, EN LAS DOS DIRECCIONES")
print("=" * 74)
# ======================================================================

DP = 0.3 * ATM

d = diagrama()
for s in ("s1", "s2"):
    d.agregar_corriente(s)
d.agregar_intercambiador("ic1", "s1", "s2", Q_por_mol=5000.0, caida_P=DP)
con = d.resolver(**base)
check("2.1 La salida sale a P_entrada − ΔP",
      abs(con["pool"]["s2.P"] - (base["s1.P"] - DP)) < 1e-9,
      f"{base['s1.P']/ATM:.3f} atm → {con['pool']['s2.P']/ATM:.3f} atm "
      f"(ΔP = {DP/ATM:.3f} atm)")

# Hacia ATRAS: dada la salida, se deduce la entrada. No es un adorno --
# es la direccion que se usa al diseñar ("necesito el producto a 1 atm:
# a que presion tengo que alimentar").
d = diagrama()
for s in ("s1", "s2"):
    d.agregar_corriente(s)
d.agregar_reactor_cstr("r1", "s1", "s2", [-1.0, 1.0], caida_P=DP,
                       con_cinetica=False, con_balance_energia=False)
atras = d.resolver(**{"s2.P": ATM, "s1.F": 100.0, "s1.x0": 0.4, "s1.x1": 0.6,
                      "r1.xi": 10.0, "r1.T": 350.0})
check("2.2 Y al revés: dada la salida, se deduce la entrada",
      atras["pool"].get("s1.P") is not None
      and abs(atras["pool"]["s1.P"] - (ATM + DP)) < 1e-9,
      f"salida a 1.000 atm → entrada a {atras['pool']['s1.P']/ATM:.3f} atm")


# ======================================================================
print("\n" + "=" * 74)
print("3. LAS CAIDAS SE ACUMULAN AL ENCADENAR")
print("=" * 74)
# ======================================================================
# El caso por el que esto hacia falta. Antes, tres equipos en serie
# dejaban las tres corrientes a la MISMA presion.

d = diagrama()
for s in ("s1", "s2", "s3", "s4"):
    d.agregar_corriente(s)
d.agregar_intercambiador("ic1", "s1", "s2", Q_por_mol=2000.0, caida_P=0.1 * ATM)
d.agregar_reactor_cstr("r1", "s2", "s3", [-1.0, 1.0], caida_P=0.25 * ATM,
                       con_cinetica=False, con_balance_energia=False)
d.agregar_intercambiador("ic2", "s3", "s4", Q_por_mol=-2000.0, caida_P=0.05 * ATM)
cadena = d.resolver(**{"s1.F": 100.0, "s1.T": 340.0, "s1.P": 3 * ATM,
                       "s1.x0": 0.4, "s1.x1": 0.6, "r1.xi": 5.0, "r1.T": 345.0})
presiones = [cadena["pool"].get(f"s{i}.P") for i in range(1, 5)]
print("     " + "  →  ".join(
    f"{p/ATM:.3f} atm" if p is not None else "?" for p in presiones))
check("3.1 Cada equipo resta la suya",
      all(p is not None for p in presiones)
      and abs(presiones[3] - (3 * ATM - 0.4 * ATM)) < 1e-9,
      f"de {presiones[0]/ATM:.3f} a {presiones[3]/ATM:.3f} atm; "
      f"total {(presiones[0]-presiones[3])/ATM:.3f} atm")
check("3.2 Y la presión decrece monótonamente a lo largo de la cadena",
      all(a > b for a, b in zip(presiones, presiones[1:])))


# ======================================================================
print("\n" + "=" * 74)
print("4. EL ESTADO DE SALIDA SE EVALUA A LA PRESION DE SALIDA")
print("=" * 74)
# ======================================================================
# La parte con contenido fisico. Bajar la presion favorece la
# vaporizacion, asi que un intercambiador con caida tiene que dar MAS
# vapor (o igual) que el mismo sin caida -- nunca menos. Evaluar el
# estado de salida a la presion de ENTRADA lo subestimaria, y esconder
# que una corriente sale en dos fases es lo que rompe lo que viene
# detras.

# Se calienta hasta cerca de la ebullicion, que es donde la presion decide.
calor = {"s1.F": 100.0, "s1.T": 350.0, "s1.P": 2 * ATM, "s1.x0": 0.4, "s1.x1": 0.6}
resultados = {}
for dP in (0.0, 0.5 * ATM, 0.9 * ATM):
    d = diagrama()
    for s in ("s1", "s2"):
        d.agregar_corriente(s)
    d.agregar_intercambiador("ic1", "s1", "s2", Q_por_mol=28000.0, caida_P=dP)
    r = d.resolver(**calor)
    resultados[dP] = (r["pool"]["s2.P"], r["pool"]["s2.T"], r["pool"]["ic1.beta_salida"])
    print(f"     ΔP = {dP/ATM:.2f} atm   P_sal = {resultados[dP][0]/ATM:.3f} atm   "
          f"T = {resultados[dP][1]:.3f} K   β = {resultados[dP][2]:.6f}")

betas = [resultados[k][2] for k in sorted(resultados)]
check("4.1 Más caída, más vapor (o igual): nunca menos",
      all(b >= a - 1e-12 for a, b in zip(betas, betas[1:])),
      " ≤ ".join(f"{b:.6f}" for b in betas))
check("4.2 Y la temperatura de salida CAMBIA con la caída",
      abs(resultados[0.9 * ATM][1] - resultados[0.0][1]) > 1e-6,
      f"{resultados[0.0][1]:.4f} K sin caída, "
      f"{resultados[0.9*ATM][1]:.4f} K con 0.9 atm")
check("4.3 La diferencia es real, no redondeo",
      betas[-1] - betas[0] > 1e-4,
      f"β pasa de {betas[0]:.6f} a {betas[-1]:.6f}: "
      f"{100*(betas[-1]-betas[0]):.2f} puntos de vaporización que un modelo "
      "sin caída no vería")


# ======================================================================
print("\n" + "=" * 74)
print("5. LO QUE DEBE RECHAZARSE, Y CUANDO")
print("=" * 74)
# ======================================================================
# Al CONSTRUIR, no al resolver: un valor negativo es un error de datos, y
# descubrirlo dentro de un lazo de reciclos -- envuelto en tres capas de
# "el bloque no pudo disparar" -- cuesta mucho mas.

negativos = [
    ("intercambiador", lambda d: d.agregar_intercambiador(
        "ic1", "s1", "s2", Q_por_mol=1000.0, caida_P=-1000.0)),
    ("reactor", lambda d: d.agregar_reactor_cstr(
        "r1", "s1", "s2", [-1.0, 1.0], caida_P=-1.0,
        con_cinetica=False, con_balance_energia=False)),
]
for nombre, montar in negativos:
    d = diagrama()
    for s in ("s1", "s2"):
        d.agregar_corriente(s)
    try:
        montar(d)
        check(f"5.x ΔP negativa en un {nombre} -> error al construir", False, "no reventó")
    except ValueError as e:
        check(f"5.x ΔP negativa en un {nombre} -> error al construir",
              "negativa" in str(e), str(e)[:95])

# Una caida mayor que la presion disponible: la salida saldria a presion
# negativa. Eso solo se puede saber al RESOLVER, porque depende de la
# presion de entrada, que es un dato del pool.
d = diagrama()
for s in ("s1", "s2"):
    d.agregar_corriente(s)
d.agregar_intercambiador("ic1", "s1", "s2", Q_por_mol=1000.0, caida_P=5 * ATM)
r = d.resolver(**{"s1.F": 100.0, "s1.T": 350.0, "s1.P": 2 * ATM,
                  "s1.x0": 0.4, "s1.x1": 0.6})
errores = [str(v) for v in (r.get("errores_bloque") or {}).values()]
check("5.3 Una caída mayor que la presión disponible se explica al resolver",
      any("no es fisica" in e or "no es física" in e for e in errores),
      (errores[0][:110] if errores else "no hubo error"))
# Las TRES cifras: cuanto se pedia caer, a cuanto saldria, y de cuanto se
# partia. Con las tres se ve de un golpe si el error esta en la caida o en
# la presion de alimentacion; con una sola hay que ir a buscar las otras.
# (La primera version de esta comprobacion buscaba la cadena "202650" y
# fallo: el mensaje formatea con %.4g y escribe 2.026e+05.)
check("5.4 Y el mensaje trae las TRES presiones, no solo 'error'",
      any(all(t in e for t in ("caida de", "salida seria", "entrada esta a"))
          for e in errores),
      (errores[0][:150] if errores else ""))


# ======================================================================
print("\n" + "=" * 74)
print("6. DOS LADOS, DOS CAIDAS")
print("=" * 74)
# ======================================================================
# El intercambiador de dos corrientes son dos circuitos distintos --
# tubos y carcasa-- con geometrias y caudales distintos. Un numero unico
# obligaria a inventar un reparto.

d = diagrama()
for s in ("cal_in", "cal_out", "fri_in", "fri_out"):
    d.agregar_corriente(s)
d.agregar_intercambiador_doble(
    "ic", caliente_entrada="cal_in", caliente_salida="cal_out",
    frio_entrada="fri_in", frio_salida="fri_out",
    T_salida_caliente=360.0,
    caida_P_caliente=0.2 * ATM, caida_P_frio=0.05 * ATM,
)
dos = d.resolver(**{
    "cal_in.F": 100.0, "cal_in.T": 380.0, "cal_in.P": 3 * ATM,
    "cal_in.x0": 0.5, "cal_in.x1": 0.5,
    "fri_in.F": 120.0, "fri_in.T": 320.0, "fri_in.P": 2 * ATM,
    "fri_in.x0": 0.5, "fri_in.x1": 0.5,
})
check("6.1 Cada lado pierde la suya, y no la del otro",
      abs(dos["pool"]["cal_out.P"] - (3 * ATM - 0.2 * ATM)) < 1e-9
      and abs(dos["pool"]["fri_out.P"] - (2 * ATM - 0.05 * ATM)) < 1e-9,
      f"caliente {3:.1f}→{dos['pool']['cal_out.P']/ATM:.3f} atm, "
      f"frío {2:.1f}→{dos['pool']['fri_out.P']/ATM:.3f} atm")
check("6.2 Y el balance de energía sigue cuadrando",
      dos["completo"] is True and dos["pool"].get("ic.Q") is not None,
      f"Q = {dos['pool']['ic.Q']/1e3:.3f} kW")

for nombre, kw in [("lado caliente", {"caida_P_caliente": -1.0}),
                   ("lado frío", {"caida_P_frio": -1.0})]:
    d = diagrama()
    for s in ("cal_in", "cal_out", "fri_in", "fri_out"):
        d.agregar_corriente(s)
    try:
        d.agregar_intercambiador_doble(
            "ic", caliente_entrada="cal_in", caliente_salida="cal_out",
            frio_entrada="fri_in", frio_salida="fri_out",
            T_salida_caliente=360.0, **kw)
        check(f"6.x ΔP negativa en el {nombre} -> error", False, "no reventó")
    except ValueError as e:
        check(f"6.x ΔP negativa en el {nombre} -> error",
              "negativa" in str(e), str(e)[:90])


print("\n" + "=" * 74)
if fallos:
    print(f"FALLARON {len(fallos)}:")
    for f in fallos:
        print("   - " + f)
    sys.exit(1)
print("TODO OK")
