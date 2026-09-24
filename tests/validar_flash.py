"""
Validacion de core/flash.py y del punto de rocio de CalculadoraELV.

Un flash es el sistema MESH con N=1, asi que estas comprobaciones son la
red de seguridad que despues heredara la columna rigurosa. Todas
contrastan contra algo independiente del propio flash:

  1. Balance de materia: z = beta*y + (1-beta)*x, componente a componente.
  2. Sumatorias: sum x = sum y = 1.
  3. Equilibrio: y_i = K_i x_i con K RECALCULADA desde cero en la x
     convergida (no la K que el lazo dejo guardada).
  4. Rocio contra burbuja: el liquido de la primera gota, metido en
     burbuja_P, tiene que devolver la misma P y la composicion de vapor
     original. Es el cruce de dos rutinas distintas.
  5. Fronteras de fase: justo por dentro de la burbuja beta ~ 0 y el
     vapor tiende a y_burbuja; justo por dentro del rocio beta ~ 1.
  6. Monotonia de beta con T.
  7. Flash P-H: la entalpia del resultado es la pedida.
  8. Valvula isentalpica: h_salida = h_entrada exacto, y vaporiza al bajar P.
  9. Ida y vuelta de la spec de diseno beta -> T -> beta.
 10. Ternario no ideal (acetona/metanol/agua).
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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.elv import CalculadoraELV
from core.flash import EvaluadorFlash

fallos = []


def check(nombre, ok, detalle=""):
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}{(' -- ' + detalle) if detalle else ''}")
    if not ok:
        fallos.append(nombre)


print("=" * 72)
print("VALIDACION: flash liquido-vapor (una etapa MESH)")
print("=" * 72)

prov = ProveedorTermodinamico(["benzene", "toluene"])
elv = CalculadoraELV(prov)
flash = EvaluadorFlash(elv)

P = 101325.0
z = np.array([0.5, 0.5])

T_burb, y_burb = elv.burbuja_T(P, z)
T_roc, x_roc = elv.rocio_T(P, z)
print(f"\nbenceno/tolueno 50/50 a {P:.0f} Pa")
print(f"  T_burbuja = {T_burb:.6f} K   (validado aparte: 365.515693 K)")
print(f"  T_rocio   = {T_roc:.6f} K")
check("0. T_rocio > T_burbuja", T_roc > T_burb, f"{T_roc:.4f} > {T_burb:.4f}")

# ------------------------------------------------------------------ 4
print()
P_roc_calc, x_gota = elv.rocio_P(T_roc, z)
P_vuelta, y_vuelta = elv.burbuja_P(T_roc, x_gota)
check("4. rocio -> burbuja recupera la P", abs(P_vuelta - P) / P < 1e-9,
      f"{P_vuelta:.6f} vs {P:.1f} Pa")
check("4. rocio -> burbuja recupera el vapor y=z", np.max(np.abs(y_vuelta - z)) < 1e-9,
      f"y={y_vuelta}, z={z}, max dif {np.max(np.abs(y_vuelta - z)):.2e}")

# ------------------------------------------------------ 1, 2, 3, 6
print()
betas = []
for T in np.linspace(T_burb + 0.3, T_roc - 0.3, 7):
    r = flash.isotermico(float(T), P, z)
    betas.append(r["beta"])

    recombinado = r["beta"] * r["y"] + (1.0 - r["beta"]) * r["x"]
    err_masa = float(np.max(np.abs(recombinado - z)))

    K_fresca = flash.constantes_equilibrio(r["T"], P, r["x"])
    err_eq = float(np.max(np.abs(r["y"] - K_fresca * r["x"])))

    err_sum = max(abs(np.sum(r["x"]) - 1.0), abs(np.sum(r["y"]) - 1.0))

    ok = err_masa < 1e-12 and err_eq < 1e-9 and err_sum < 1e-12
    check(f"1-3. T={T:6.2f} K  beta={r['beta']:.4f}  ({r['iteraciones']} it)", ok,
          f"masa {err_masa:.2e} | equilibrio {err_eq:.2e} | sumatorias {err_sum:.2e}")

check("6. beta crece monotonamente con T", all(np.diff(betas) > 0),
      f"beta de {betas[0]:.4f} a {betas[-1]:.4f}")

# ------------------------------------------------------------------ 5
print()
r_casi_burbuja = flash.isotermico(T_burb + 1e-3, P, z)
check("5. Justo sobre la burbuja: beta ~ 0", r_casi_burbuja["beta"] < 1e-3,
      f"beta={r_casi_burbuja['beta']:.3e}, fase={r_casi_burbuja['fase']}")
check("5. Justo sobre la burbuja: y -> y_burbuja",
      np.max(np.abs(r_casi_burbuja["y"] - y_burb)) < 1e-3,
      f"y={r_casi_burbuja['y']} vs y_burbuja={y_burb}")

r_casi_rocio = flash.isotermico(T_roc - 1e-3, P, z)
check("5. Justo bajo el rocio: beta ~ 1", r_casi_rocio["beta"] > 1.0 - 1e-3,
      f"beta={r_casi_rocio['beta']:.6f}")
check("5. Justo bajo el rocio: x -> x_rocio",
      np.max(np.abs(r_casi_rocio["x"] - x_roc)) < 1e-3)

r_frio = flash.isotermico(T_burb - 10.0, P, z)
check("5. Bajo la burbuja: todo liquido", r_frio["fase"] == "liquido" and r_frio["beta"] == 0.0)
r_caliente = flash.isotermico(T_roc + 10.0, P, z)
check("5. Sobre el rocio: todo vapor", r_caliente["fase"] == "vapor" and r_caliente["beta"] == 1.0)

# ------------------------------------------------------------------ 7
print()
for h_obj in (flash.entalpia.h_liquido(T_burb, z) + 5000.0,
              flash.entalpia.h_liquido(T_burb, z) + 15000.0,
              flash.entalpia.h_liquido(T_burb, z) - 5000.0,
              flash.entalpia.h_vapor(T_roc, z) + 4000.0):
    r = flash.a_entalpia(P, z, h_obj)
    err = abs(r["h"] - h_obj) / max(1.0, abs(h_obj))
    check(f"7. Flash P-H -> {r['fase']:9s} T={r['T']:7.2f} K beta={r['beta']:.4f}",
          err < 1e-8, f"h obtenida {r['h']:.4f} vs pedida {h_obj:.4f} (err rel {err:.2e})")

# ------------------------------------------------------------------ 8
print()
T_entrada = T_burb - 5.0   # liquido subenfriado a presion alta
P_alta, P_baja = 3.0 * P, 0.4 * P
h_in = flash.entalpia.h_liquido(T_entrada, z)
r_valvula = flash.a_entalpia(P_baja, z, h_in)
check("8. Valvula isentalpica: h se conserva exacto",
      abs(r_valvula["h"] - h_in) / max(1.0, abs(h_in)) < 1e-8,
      f"h_in={h_in:.4f} -> h_out={r_valvula['h']:.4f} J/mol")
check("8. Al expandir, el liquido se vaporiza parcialmente y se enfria",
      r_valvula["beta"] > 0 and r_valvula["T"] < T_entrada,
      f"beta={r_valvula['beta']:.4f}, T {T_entrada:.2f} -> {r_valvula['T']:.2f} K")

r_adiab = flash.con_calor(P, z, T_entrada, Q_por_mol=0.0)
check("8. Flash adiabatico sin calor = flash isentalpico",
      abs(r_adiab["h"] - h_in) / max(1.0, abs(h_in)) < 1e-8)

r_calor = flash.con_calor(P, z, T_entrada, Q_por_mol=12000.0)
check("8. Aportar calor sube T y vaporiza",
      r_calor["T"] > r_adiab["T"] and r_calor["beta"] > r_adiab["beta"],
      f"T {r_adiab['T']:.2f} -> {r_calor['T']:.2f} K, beta {r_adiab['beta']:.4f} -> {r_calor['beta']:.4f}")
check("8. El calor aportado aparece integro en la entalpia",
      abs((r_calor["h"] - r_adiab["h"]) - 12000.0) < 1e-6,
      f"dif h = {r_calor['h'] - r_adiab['h']:.6f} J/mol")

# ------------------------------------------------------------------ 9
print()
for beta_obj in (0.2, 0.5, 0.8):
    r = flash.a_fraccion(P, z, beta_obj)
    r_vuelta = flash.isotermico(r["T"], P, z)
    check(f"9. beta={beta_obj} -> T={r['T']:.4f} K -> beta",
          abs(r_vuelta["beta"] - beta_obj) < 1e-8,
          f"recuperado {r_vuelta['beta']:.10f}")

# ----------------------------------------------------------------- 10
print()
prov3 = ProveedorTermodinamico(["acetone", "methanol", "water"])
elv3 = CalculadoraELV(prov3)
flash3 = EvaluadorFlash(elv3)
z3 = np.array([0.3, 0.3, 0.4])
Tb3, _ = elv3.burbuja_T(P, z3)
Tr3, _ = elv3.rocio_T(P, z3)
print(f"acetona/metanol/agua 30/30/40: T_burbuja={Tb3:.4f} K, T_rocio={Tr3:.4f} K")
check("10. Ternario: T_rocio > T_burbuja", Tr3 > Tb3)

for T in (Tb3 + 2.0, 0.5 * (Tb3 + Tr3), Tr3 - 2.0):
    r = flash3.isotermico(float(T), P, z3)
    err_masa = float(np.max(np.abs(r["beta"] * r["y"] + (1 - r["beta"]) * r["x"] - z3)))
    K_fresca = flash3.constantes_equilibrio(r["T"], P, r["x"])
    err_eq = float(np.max(np.abs(r["y"] - K_fresca * r["x"])))
    check(f"10. Ternario T={T:6.2f} K beta={r['beta']:.4f} ({r['iteraciones']} it)",
          err_masa < 1e-12 and err_eq < 1e-9,
          f"masa {err_masa:.2e} | equilibrio {err_eq:.2e}")

r3 = flash3.a_fraccion(P, z3, 0.45)
check("10. Ternario: spec beta=0.45 converge",
      abs(flash3.isotermico(r3["T"], P, z3)["beta"] - 0.45) < 1e-8,
      f"T={r3['T']:.4f} K, x={np.round(r3['x'],4)}, y={np.round(r3['y'],4)}")
check("10. Ternario: el vapor se enriquece en el mas volatil (acetona)",
      r3["y"][0] > z3[0] > r3["x"][0],
      f"y_acetona={r3['y'][0]:.4f} > z={z3[0]} > x_acetona={r3['x'][0]:.4f}")

print("\n" + "=" * 72)
if fallos:
    print(f"FALLARON {len(fallos)}: " + " | ".join(fallos))
    sys.exit(1)
print("TODO OK")
