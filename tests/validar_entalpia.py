"""
Validacion de thermodynamics/entalpia.py.

Criterio del proyecto: que corra no es que funcione. Cada comprobacion
contrasta contra algo INDEPENDIENTE del propio modulo:

  1. h(T_ref) = 0 exacto (definicion de la referencia).
  2. dh/dT = Cp, por diferencias finitas contra el Cp del PROVEEDOR
     (no contra la spline interna: si la tabulacion estuviera mal, esta
     comprobacion lo veria).
  3. La integral tabulada coincide con quad sobre el Cp del proveedor
     -- es exactamente el calculo que hacia Ponchon-Savarit antes.
  4. h_V - h_L = sum y_i DHvap_i, contra el DHvap del proveedor.
  5. Aditividad: h de una mezcla = suma ponderada de los puros (mezcla ideal).
  6. Ida y vuelta T -> h -> T.
  7. Monotonia estricta en T.
  8. Forma vectorizada (perfil de columna) identica a la escalar.
"""

import sys, os

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

import numpy as np
from scipy.integrate import quad

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.entalpia import CalculadoraEntalpia, entalpia_de

fallos = []


def check(nombre, ok, detalle=""):
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}{(' -- ' + detalle) if detalle else ''}")
    if not ok:
        fallos.append(nombre)


print("=" * 70)
print("VALIDACION: entalpia unificada h(T, x, fase)")
print("=" * 70)

prov = ProveedorTermodinamico(["benzene", "toluene"])
ent = CalculadoraEntalpia(prov)
print(f"\nRango tabulado: [{ent.T_min:.1f}, {ent.T_max:.1f}] K, T_ref={ent.T_ref} K")

x = np.array([0.4, 0.6])

# ---------------------------------------------------------------- 1
h_ref = ent.h_liquido(ent.T_ref, x)
check("1. h_L(T_ref, x) = 0", abs(h_ref) < 1e-9, f"h={h_ref:.3e} J/mol")

for x_puro in (np.array([1.0, 0.0]), np.array([0.0, 1.0])):
    hp = ent.h_liquido(ent.T_ref, x_puro)
    check(f"   h_L(T_ref) = 0 tambien para el puro {x_puro}", abs(hp) < 1e-9)

# ---------------------------------------------------------------- 2
print()
for T in (250.0, 300.0, 350.0, 400.0, 480.0):
    dT = 1e-3
    dh_dT = (ent.h_liquido(T + dT, x) - ent.h_liquido(T - dT, x)) / (2 * dT)
    Cp_prov = float(np.dot(x, prov.capacidades_calorificas_liquido(T)))
    err = abs(dh_dT - Cp_prov) / Cp_prov
    check(f"2. dh/dT = Cp del proveedor a {T:.0f} K", err < 1e-4,
          f"{dh_dT:.4f} vs {Cp_prov:.4f} J/(mol K), err rel {err:.2e}")

# ---------------------------------------------------------------- 3
print()
for T in (320.0, 365.5, 450.0):
    integrando = lambda Tp: float(np.dot(x, prov.capacidades_calorificas_liquido(Tp)))
    h_quad, _ = quad(integrando, ent.T_ref, T)
    h_tab = ent.h_liquido(T, x)
    err = abs(h_tab - h_quad) / abs(h_quad)
    check(f"3. Tabulado = quad sobre el proveedor a {T:.1f} K", err < 1e-5,
          f"{h_tab:.2f} vs {h_quad:.2f} J/mol, err rel {err:.2e}")

# ---------------------------------------------------------------- 4
print()
for T in (300.0, 365.0, 450.0):
    y = np.array([0.7, 0.3])
    salto = ent.h_vapor(T, y) - ent.h_liquido(T, y)
    esperado = float(np.dot(y, prov.entalpias_vaporizacion(T)))
    err = abs(salto - esperado) / esperado
    check(f"4. h_V - h_L = sum y_i DHvap_i a {T:.0f} K", err < 1e-4,
          f"{salto:.1f} vs {esperado:.1f} J/mol")

# ---------------------------------------------------------------- 5
print()
T = 350.0
h_mezcla = ent.h_liquido(T, x)
h_suma = x[0] * ent.h_liquido(T, np.array([1.0, 0.0])) + \
         x[1] * ent.h_liquido(T, np.array([0.0, 1.0]))
check("5. Mezcla ideal: h(x) = sum x_i h_i", abs(h_mezcla - h_suma) < 1e-9,
      f"{h_mezcla:.6f} vs {h_suma:.6f} J/mol")

# ---------------------------------------------------------------- 6
print()
for T_original in (260.0, 330.0, 420.0, 500.0):
    h_obj = ent.h_liquido(T_original, x)
    T_recuperada = ent.T_desde_h_liquido(h_obj, x)
    check(f"6. T -> h -> T desde {T_original:.0f} K",
          abs(T_recuperada - T_original) < 1e-8,
          f"recuperada {T_recuperada:.10f} K")

# ---------------------------------------------------------------- 7
print()
Ts = np.linspace(ent.T_min, ent.T_max, 400)
hs = np.array([ent.h_liquido(t, x) for t in Ts])
check("7. h_L estrictamente creciente en T", np.all(np.diff(hs) > 0),
      f"minimo incremento {np.min(np.diff(hs)):.4f} J/mol")

# ---------------------------------------------------------------- 8
print()
T_perfil = np.array([320.0, 350.0, 380.0])
x_perfil = np.array([[0.9, 0.1], [0.5, 0.5], [0.1, 0.9]])
h_vec = ent.h_liquido(T_perfil, x_perfil)
h_esc = np.array([ent.h_liquido(T_perfil[k], x_perfil[k]) for k in range(3)])
check("8. Forma vectorizada = escalar (liquido)", np.allclose(h_vec, h_esc, rtol=0, atol=1e-10),
      f"max dif {np.max(np.abs(h_vec - h_esc)):.2e}")
hv_vec = ent.h_vapor(T_perfil, x_perfil)
hv_esc = np.array([ent.h_vapor(T_perfil[k], x_perfil[k]) for k in range(3)])
check("8. Forma vectorizada = escalar (vapor)", np.allclose(hv_vec, hv_esc, rtol=0, atol=1e-10))

# ---------------------------------------------------------------- 9
print()
beta = 0.35
xL, yV = np.array([0.3, 0.7]), np.array([0.6, 0.4])
h_bi = ent.h_corriente(350.0, xL, yV, fraccion_vapor=beta)
h_manual = (1 - beta) * ent.h_liquido(350.0, xL) + beta * ent.h_vapor(350.0, yV)
check("9. Corriente bifasica = combinacion lineal", abs(h_bi - h_manual) < 1e-12)
check("9. beta=0 cae en h_L", abs(ent.h_corriente(350.0, xL, yV, 0.0) - ent.h_liquido(350.0, xL)) < 1e-12)
check("9. beta=1 cae en h_V", abs(ent.h_corriente(350.0, xL, yV, 1.0) - ent.h_vapor(350.0, yV)) < 1e-12)

# --------------------------------------------------------------- 10
print()
otra = entalpia_de(prov)
check("10. entalpia_de() reutiliza la MISMA instancia", entalpia_de(prov) is otra)

try:
    ent.h_liquido(1200.0, x)
    check("10. Fuera de rango avisa en vez de extrapolar", False, "no lanzo error")
except ValueError as e:
    check("10. Fuera de rango avisa en vez de extrapolar", "rango tabulado" in str(e))

# --------------------------------------------------------------- 11
print()
prov3 = ProveedorTermodinamico(["acetone", "methanol", "water"])
ent3 = CalculadoraEntalpia(prov3)
x3 = np.array([0.2, 0.3, 0.5])
T3 = 340.0
dT = 1e-3
dh_dT3 = (ent3.h_liquido(T3 + dT, x3) - ent3.h_liquido(T3 - dT, x3)) / (2 * dT)
Cp3 = float(np.dot(x3, prov3.capacidades_calorificas_liquido(T3)))
check("11. Ternario: dh/dT = Cp", abs(dh_dT3 - Cp3) / Cp3 < 1e-4,
      f"{dh_dT3:.4f} vs {Cp3:.4f}")
check("11. Ternario: h(T_ref)=0", abs(ent3.h_liquido(ent3.T_ref, x3)) < 1e-9)

print("\n" + "=" * 70)
if fallos:
    print(f"FALLARON {len(fallos)}: " + ", ".join(fallos))
    sys.exit(1)
print("TODO OK")
