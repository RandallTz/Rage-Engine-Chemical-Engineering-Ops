"""
Validacion de PLANTAS ENCADENADAS: varios equipos en serie, con lazo, y
los balances globales cerrados sobre el conjunto.

Un equipo suelto puede estar bien y la planta estar mal. Lo que se prueba
aqui no es ningun metodo en particular sino la FRONTERA entre equipos:
que la corriente que uno entrega sea exactamente la que el siguiente
recibe, en materia Y en energia. Es la comprobacion que no existia
mientras cada modulo se validaba por su cuenta.

Tres cadenas:

  A. Sin lazo: intercambiador -> valvula -> flash.
     Balance de materia y de ENERGIA global, y ademas equipo por equipo.

  B. Con lazo: mezclador -> intercambiador -> flash -> divisor -> reciclo.
     Aqui el balance de energia solo cierra si el mezclador, el
     intercambiador, el flash y el divisor miden la entalpia con la MISMA
     definicion -- que es justo lo que se unifico en
     thermodynamics/entalpia.py.

  C. Flash -> columna McCabe-Thiele con q=1.
     El liquido que sale de un flash esta, por definicion, en su punto de
     burbuja. Si eso es cierto, conectarlo a una columna declarando q=1
     es exacto y no una suposicion. Se comprueba contra burbuja_T.

Ejecutar desde la raiz del proyecto:
    python tests/validar_planta_encadenada.py
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
from thermodynamics.entalpia import entalpia_de
from core.flash import EvaluadorFlash
from core.mccabe_thiele import EvaluadorMcCabeThiele, SolucionadorMcCabeThiele
from core.diagrama_corrientes import DiagramaCorrientes

NOMBRES = ["benzene", "toluene"]
P = 101325.0

fallos = []


def check(nombre, ok, detalle=""):
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}{(' -- ' + detalle) if detalle else ''}")
    if not ok:
        fallos.append(nombre)


PROVEEDOR = ProveedorTermodinamico(NOMBRES)
ELV = CalculadoraELV(PROVEEDOR)
FLASH = EvaluadorFlash(ELV)
ENT = entalpia_de(PROVEEDOR)


def h_de(pool, corriente):
    """Entalpia molar de una corriente del pool, con la fase deducida de (T,P,z)."""
    z = np.array([pool[f"{corriente}.x{i}"] for i in range(2)])
    return FLASH.entalpia_de_corriente(pool[f"{corriente}.T"], pool[f"{corriente}.P"], z)


def caudal_componente(pool, corriente, i):
    return pool[f"{corriente}.F"] * pool[f"{corriente}.x{i}"]


# ======================================================================
print("=" * 74)
print("CADENA A: intercambiador -> valvula -> flash (sin lazo)")
print("=" * 74)

d = DiagramaCorrientes(NOMBRES, proveedor=PROVEEDOR)
for c in ("fresca", "caliente", "expandida", "vapor", "liquido"):
    d.agregar_corriente(c)
d.agregar_intercambiador("E1", "fresca", "caliente", Q_por_mol=18000.0)
d.agregar_valvula("V1", "caliente", "expandida", P_salida=P)
d.agregar_flash("S1", "expandida", "vapor", "liquido", P_operacion=P, Q_por_mol=0.0)

datos_A = {"fresca.F": 100.0, "fresca.T": 330.0, "fresca.P": 6.0 * P, "fresca.x0": 0.45}
gl = d.grados_de_libertad(datos_A)
check("A0. Grados de libertad = 0", gl["grados_de_libertad"] == 0,
      f"incognitas={gl['incognitas']}, ecuaciones={gl['ecuaciones']}, GL={gl['grados_de_libertad']}")

res = d.resolver(**datos_A)
pool = res["pool"]
check("A0. La cadena resuelve entera", res["completo"],
      f"incognitas restantes: {res['incognitas_restantes'][:4]}")

print(f"\n  fresca     F={pool['fresca.F']:8.4f} T={pool['fresca.T']:7.2f} K P={pool['fresca.P']:9.0f} Pa")
print(f"  caliente   F={pool['caliente.F']:8.4f} T={pool['caliente.T']:7.2f} K "
      f"beta={pool['E1.beta_salida']:.4f}  (Q={pool['E1.Q']/1000:.1f} kW)")
print(f"  expandida  F={pool['expandida.F']:8.4f} T={pool['expandida.T']:7.2f} K "
      f"beta={pool['V1.beta_salida']:.4f}  (caida P={pool['V1.caida_P']/1000:.1f} kPa)")
print(f"  vapor      F={pool['vapor.F']:8.4f} T={pool['vapor.T']:7.2f} K y_benceno={pool['vapor.x0']:.4f}")
print(f"  liquido    F={pool['liquido.F']:8.4f} T={pool['liquido.T']:7.2f} K x_benceno={pool['liquido.x0']:.4f}")

# -- materia
total = pool["vapor.F"] + pool["liquido.F"]
check("A1. Balance de materia total", abs(total - 100.0) < 1e-9,
      f"vapor+liquido = {total:.10f} vs fresca = 100.0")
for i, nombre in enumerate(NOMBRES):
    entra = caudal_componente(pool, "fresca", i)
    sale = caudal_componente(pool, "vapor", i) + caudal_componente(pool, "liquido", i)
    check(f"A1. Balance por componente ({nombre})", abs(entra - sale) < 1e-9,
          f"{entra:.10f} vs {sale:.10f} mol/s")

# -- energia global
h_in = h_de(pool, "fresca")
energia_entra = 100.0 * h_in + pool["E1.Q"]
energia_sale = pool["vapor.F"] * h_de(pool, "vapor") + pool["liquido.F"] * h_de(pool, "liquido")
err = abs(energia_entra - energia_sale) / max(1.0, abs(energia_entra))
check("A2. Balance de ENERGIA global", err < 1e-9,
      f"entra {energia_entra:.6f} W, sale {energia_sale:.6f} W, err rel {err:.2e}")

# -- energia equipo por equipo
err_E1 = abs((h_de(pool, "caliente") - h_in) - 18000.0)
check("A3. E1 entrega exactamente el Q pedido", err_E1 < 1e-6,
      f"dh = {h_de(pool, 'caliente') - h_in:.6f} J/mol vs 18000 pedidos")
err_V1 = abs(h_de(pool, "expandida") - h_de(pool, "caliente"))
check("A3. V1 es isentalpica", err_V1 < 1e-6, f"dh = {err_V1:.3e} J/mol")
h_flash = (pool["vapor.F"] * h_de(pool, "vapor") + pool["liquido.F"] * h_de(pool, "liquido")) / 100.0
check("A3. S1 es adiabatico", abs(h_flash - h_de(pool, "expandida")) < 1e-6,
      f"dh = {h_flash - h_de(pool, 'expandida'):.3e} J/mol")

# -- fisica
check("A4. La valvula enfria al expandir",
      pool["expandida.T"] < pool["caliente.T"],
      f"{pool['caliente.T']:.2f} -> {pool['expandida.T']:.2f} K")
check("A4. El vapor se enriquece en el ligero (benceno)",
      pool["vapor.x0"] > 0.45 > pool["liquido.x0"],
      f"y={pool['vapor.x0']:.4f} > z=0.45 > x={pool['liquido.x0']:.4f}")
check("A4. Vapor y liquido salen a la misma T (equilibrio)",
      abs(pool["vapor.T"] - pool["liquido.T"]) < 1e-12)

# -- spec alternativa del intercambiador
d2 = DiagramaCorrientes(NOMBRES, proveedor=PROVEEDOR)
for c in ("f2", "c2"):
    d2.agregar_corriente(c)
d2.agregar_intercambiador("E2", "f2", "c2", T_salida=355.0)
pool2 = d2.resolver(**{"f2.F": 50.0, "f2.T": 330.0, "f2.P": P, "f2.x0": 0.45})["pool"]
Q_directo = ENT.h_liquido(355.0, np.array([0.45, 0.55])) - ENT.h_liquido(330.0, np.array([0.45, 0.55]))
check("A5. Spec por T_salida calcula el Q correcto",
      abs(pool2["E2.Q_por_mol"] - Q_directo) < 1e-6,
      f"{pool2['E2.Q_por_mol']:.6f} vs {Q_directo:.6f} J/mol")

# ======================================================================
print("\n" + "=" * 74)
print("CADENA B: mezclador -> intercambiador -> flash -> divisor -> RECICLO")
print("=" * 74)

FRACCION_RECICLO = 0.7
b = DiagramaCorrientes(NOMBRES, proveedor=PROVEEDOR)
for c in ("fresca", "mezcla", "caliente", "vapor", "fondo", "purga", "reciclo"):
    b.agregar_corriente(c)
b.agregar_mezclador("M1", entradas=["fresca", "reciclo"], salida="mezcla")
b.agregar_intercambiador("E1", "mezcla", "caliente", Q_por_mol=14000.0)
b.agregar_flash("S1", "caliente", "vapor", "fondo", P_operacion=P, Q_por_mol=0.0)
b.agregar_divisor("D1", "fondo", salidas=["purga", "reciclo"],
                  fracciones=[1.0 - FRACCION_RECICLO, FRACCION_RECICLO])

datos_B = {"fresca.F": 100.0, "fresca.T": 320.0, "fresca.P": P, "fresca.x0": 0.45}
cortes = b.detectar_reciclos()
check("B0. El lazo se detecta y se corta", len(cortes) == 1, f"corte en {cortes}")

gl_b = b.grados_de_libertad(datos_B)
check("B0. Grados de libertad = 0", gl_b["grados_de_libertad"] == 0,
      f"incognitas={gl_b['incognitas']}, ecuaciones={gl_b['ecuaciones']}, GL={gl_b['grados_de_libertad']}")

# Tolerancia del lazo APRETADA a proposito. Con la de por defecto (1e-8
# relativo) los balances globales cierran a ~1e-6 mol/s en absoluto, que
# es correcto pero no distingue "converge bien" de "hay una fuga pequena".
# A 1e-12 el residuo del balance tiene que bajar con ella; si no bajara,
# seria una fuga real y no un criterio de parada.
TOL_LAZO = 1e-12
res_b = b.resolver(tolerancia_reciclo=TOL_LAZO, max_ciclos_reciclo=400, **datos_B)
pool_b = res_b["pool"]
info = res_b.get("reciclo") or {}
check("B0. El lazo converge", bool(info.get("convergio")),
      f"{info.get('ciclos')} vueltas, error {info.get('error'):.2e}" if info.get("error") is not None else "")

print(f"\n  fresca   F={pool_b['fresca.F']:8.4f}  T={pool_b['fresca.T']:7.2f} K")
print(f"  reciclo  F={pool_b['reciclo.F']:8.4f}  T={pool_b['reciclo.T']:7.2f} K")
print(f"  mezcla   F={pool_b['mezcla.F']:8.4f}  T={pool_b['mezcla.T']:7.2f} K  x={pool_b['mezcla.x0']:.4f}")
print(f"  caliente F={pool_b['caliente.F']:8.4f}  T={pool_b['caliente.T']:7.2f} K  beta={pool_b['E1.beta_salida']:.4f}")
print(f"  vapor    F={pool_b['vapor.F']:8.4f}  T={pool_b['vapor.T']:7.2f} K  y={pool_b['vapor.x0']:.4f}")
print(f"  purga    F={pool_b['purga.F']:8.4f}  T={pool_b['purga.T']:7.2f} K  x={pool_b['purga.x0']:.4f}")

# -- materia global: lo que entra fresco sale por vapor + purga
salida_total = pool_b["vapor.F"] + pool_b["purga.F"]
check("B1. Balance de materia GLOBAL (fresca = vapor + purga)",
      abs(salida_total - 100.0) < 1e-9,
      f"{salida_total:.10f} vs 100.0 mol/s")
for i, nombre in enumerate(NOMBRES):
    entra = caudal_componente(pool_b, "fresca", i)
    sale = caudal_componente(pool_b, "vapor", i) + caudal_componente(pool_b, "purga", i)
    check(f"B1. Balance global por componente ({nombre})", abs(entra - sale) < 1e-9,
          f"{entra:.10f} vs {sale:.10f} mol/s")

# -- el lazo cierra sobre si mismo
check("B2. El divisor reparte lo que dice su fraccion",
      abs(pool_b["reciclo.F"] - FRACCION_RECICLO * pool_b["fondo.F"]) < 1e-9,
      f"reciclo={pool_b['reciclo.F']:.10f} vs {FRACCION_RECICLO * pool_b['fondo.F']:.10f} mol/s")
check("B2. El mezclador suma fresca + reciclo",
      abs(pool_b["mezcla.F"] - (100.0 + pool_b["reciclo.F"])) < 1e-9,
      f"{pool_b['mezcla.F']:.8f} vs {100.0 + pool_b['reciclo.F']:.8f} mol/s")

# -- energia global: solo cierra si los cuatro equipos usan la misma h
energia_entra_b = 100.0 * h_de(pool_b, "fresca") + pool_b["E1.Q"]
energia_sale_b = (pool_b["vapor.F"] * h_de(pool_b, "vapor")
                  + pool_b["purga.F"] * h_de(pool_b, "purga"))
err_b = abs(energia_entra_b - energia_sale_b) / max(1.0, abs(energia_entra_b))
check("B3. Balance de ENERGIA global con lazo", err_b < 1e-9,
      f"entra {energia_entra_b:.4f} W, sale {energia_sale_b:.4f} W, err rel {err_b:.2e}")

# -- el mezclador, por dentro
h_mezcla_esperada = (100.0 * h_de(pool_b, "fresca")
                     + pool_b["reciclo.F"] * h_de(pool_b, "reciclo")) / pool_b["mezcla.F"]
check("B3. El mezclador es adiabatico (su balance cierra)",
      abs(h_de(pool_b, "mezcla") - h_mezcla_esperada) < 1e-6,
      f"h mezcla {h_de(pool_b, 'mezcla'):.6f} vs esperada {h_mezcla_esperada:.6f} J/mol")

check("B4. El reciclo esta mas caliente que la alimentacion fresca",
      pool_b["reciclo.T"] > pool_b["fresca.T"],
      f"{pool_b['reciclo.T']:.2f} K vs {pool_b['fresca.T']:.2f} K")

# -- con varias fracciones de reciclo
print()
for fraccion in (0.0, 0.3, 0.5, 0.85):
    bb = DiagramaCorrientes(NOMBRES, proveedor=PROVEEDOR)
    for c in ("fresca", "mezcla", "caliente", "vapor", "fondo", "purga", "reciclo"):
        bb.agregar_corriente(c)
    bb.agregar_mezclador("M1", entradas=["fresca", "reciclo"], salida="mezcla")
    bb.agregar_intercambiador("E1", "mezcla", "caliente", Q_por_mol=14000.0)
    bb.agregar_flash("S1", "caliente", "vapor", "fondo", P_operacion=P, Q_por_mol=0.0)
    bb.agregar_divisor("D1", "fondo", salidas=["purga", "reciclo"],
                       fracciones=[1.0 - fraccion, fraccion])
    r = bb.resolver(tolerancia_reciclo=TOL_LAZO, max_ciclos_reciclo=400, **datos_B)
    p = r["pool"]
    inf = r.get("reciclo") or {}
    cerrado = abs(p["vapor.F"] + p["purga.F"] - 100.0) < 1e-9
    e_in = 100.0 * h_de(p, "fresca") + p["E1.Q"]
    e_out = p["vapor.F"] * h_de(p, "vapor") + p["purga.F"] * h_de(p, "purga")
    energia_ok = abs(e_in - e_out) / max(1.0, abs(e_in)) < 1e-9
    check(f"B5. Reciclo {fraccion*100:4.0f} %: materia y energia cierran",
          cerrado and energia_ok,
          f"{inf.get('ciclos', 1)} vueltas, vapor={p['vapor.F']:.4f}, purga={p['purga.F']:.4f} mol/s")

# ======================================================================
print("\n" + "=" * 74)
print("CADENA B-bis: mezclar liquido con VAPOR (por que la fase no se supone)")
print("=" * 74)

# El mezclador es por donde entra un reciclo, y un reciclo puede traer
# vapor. Mientras midio la entalpia como si toda corriente fuera liquida,
# el calor latente que entra con ese vapor se perdia en silencio. Aqui se
# mide cuanto era, comparando las dos definiciones sobre el mismo caso.
z_bis = np.array([0.45, 0.55])
T_liq = 330.0
T_burb_bis, _ = ELV.burbuja_T(P, z_bis)
T_roc_bis, _ = ELV.rocio_T(P, z_bis)
T_vap = T_roc_bis + 5.0           # vapor sobrecalentado, sin ambiguedad
F_liq, F_vap = 100.0, 40.0

# (a) la definicion vieja: todo medido como liquido
h_viejo = (F_liq * ENT.h_liquido(T_liq, z_bis)
           + F_vap * ENT.h_liquido(T_vap, z_bis)) / (F_liq + F_vap)
T_viejo = ENT.T_desde_h_liquido(h_viejo, z_bis)

# (b) la definicion actual: la fase sale de (T, P, z)
h_nuevo = (F_liq * FLASH.entalpia_de_corriente(T_liq, P, z_bis)
           + F_vap * FLASH.entalpia_de_corriente(T_vap, P, z_bis)) / (F_liq + F_vap)
r_bis = FLASH.a_entalpia(P, z_bis, h_nuevo)

print(f"\n  burbuja={T_burb_bis:.2f} K  rocio={T_roc_bis:.2f} K  vapor entra a {T_vap:.2f} K")
print(f"  antes (todo liquido): h={h_viejo:9.1f} J/mol -> T={T_viejo:7.2f} K")
print(f"  ahora (fase real)   : h={h_nuevo:9.1f} J/mol -> T={r_bis['T']:7.2f} K, "
      f"fase={r_bis['fase']}, beta={r_bis['beta']:.4f}")

latente_perdido = h_nuevo - h_viejo
check("Bb1. La definicion vieja perdia el calor latente del vapor",
      latente_perdido > 8000.0,
      f"{latente_perdido:.1f} J/mol de menos ({100*latente_perdido/h_nuevo:.1f} % del total)")
check("Bb2. Y por eso daba una T demasiado BAJA (no alta)",
      T_viejo < r_bis["T"] - 20.0,
      f"{T_viejo:.2f} K frente a {r_bis['T']:.2f} K reales "
      f"({r_bis['T'] - T_viejo:.2f} K de diferencia)")
check("Bb3. La mezcla real es bifasica, no liquida",
      r_bis["fase"] == "bifasico" and 0.0 < r_bis["beta"] < 1.0,
      f"fase={r_bis['fase']}, beta={r_bis['beta']:.4f}")

# Y el mezclador del flowsheet, que ya usa la definicion buena, reproduce (b).
m = DiagramaCorrientes(NOMBRES, proveedor=PROVEEDOR)
for c in ("liq_in", "vap_in", "mezcla_bis"):
    m.agregar_corriente(c)
m.agregar_mezclador("MB", entradas=["liq_in", "vap_in"], salida="mezcla_bis")
pool_m = m.resolver(**{
    "liq_in.F": F_liq, "liq_in.T": T_liq, "liq_in.P": P, "liq_in.x0": 0.45,
    "vap_in.F": F_vap, "vap_in.T": T_vap, "vap_in.P": P, "vap_in.x0": 0.45,
})["pool"]
check("Bb4. El mezclador del flowsheet da la T con la fase real",
      abs(pool_m["mezcla_bis.T"] - r_bis["T"]) < 1e-6,
      f"{pool_m['mezcla_bis.T']:.6f} K vs {r_bis['T']:.6f} K")

# ======================================================================
print("\n" + "=" * 74)
print("CADENA C: flash -> columna McCabe-Thiele (q=1)")
print("=" * 74)

evaluador_mt = EvaluadorMcCabeThiele(ELV, NOMBRES, P_sistema=P)
solucionador_mt = SolucionadorMcCabeThiele(evaluador_mt)

c3 = DiagramaCorrientes(NOMBRES, proveedor=PROVEEDOR)
for c in ("cruda", "gas", "alim", "dest", "fondo"):
    c3.agregar_corriente(c)
c3.agregar_flash("S1", "cruda", "gas", "alim", P_operacion=P, fraccion_vapor=0.30)
c3.agregar_columna_binaria("col1", solucionador_mt, "alim", "dest", "fondo", q_fijo=1.0)

datos_C = {
    "cruda.F": 100.0, "cruda.T": 340.0, "cruda.P": P, "cruda.x0": 0.45,
    "dest.x0": 0.95, "fondo.x0": 0.05, "col1.R": 3.0,
    # col1.q NO se da aqui: lo aporta q_fijo=1.0 del propio equipo.
}
gl_c = c3.grados_de_libertad(datos_C)
res_c = c3.resolver(**datos_C)
pool_c = res_c["pool"]
check("C0. La cadena resuelve entera", res_c["completo"],
      f"restantes={res_c['incognitas_restantes'][:3]}")
check("C0. Grados de libertad = 0 (la columna no re-fija la T del flash)",
      gl_c["grados_de_libertad"] == 0,
      f"incognitas={gl_c['incognitas']}, ecuaciones={gl_c['ecuaciones']}, "
      f"GL={gl_c['grados_de_libertad']}, redundancias={len(gl_c['redundancias'])}")

print(f"\n  cruda  F={pool_c['cruda.F']:8.4f}  -> flash beta={pool_c['S1.beta']:.4f} a T={pool_c['S1.T']:.3f} K")
print(f"  gas    F={pool_c['gas.F']:8.4f}  y={pool_c['gas.x0']:.4f}")
print(f"  alim   F={pool_c['alim.F']:8.4f}  x={pool_c['alim.x0']:.4f}  T={pool_c['alim.T']:.3f} K")
print(f"  dest   F={pool_c['dest.F']:8.4f}  |  fondo F={pool_c['fondo.F']:8.4f}  |  N={pool_c['col1.N']:.4f}")

# La afirmacion que justifica q=1: el liquido del flash esta en su burbuja.
x_alim = np.array([pool_c["alim.x0"], pool_c["alim.x1"]])
T_burbuja_alim, _ = ELV.burbuja_T(P, x_alim)
check("C1. El liquido del flash ESTA en su punto de burbuja (justifica q=1)",
      abs(T_burbuja_alim - pool_c["alim.T"]) < 1e-6,
      f"burbuja_T={T_burbuja_alim:.9f} K vs T del flash={pool_c['alim.T']:.9f} K")

check("C2. Balance del flash", abs(pool_c["gas.F"] + pool_c["alim.F"] - 100.0) < 1e-9)
check("C2. La spec de vaporizacion se cumple", abs(pool_c["S1.beta"] - 0.30) < 1e-8,
      f"beta={pool_c['S1.beta']:.10f}")
check("C3. Balance de la columna", abs(pool_c["dest.F"] + pool_c["fondo.F"] - pool_c["alim.F"]) < 1e-6)
comp_col = abs(pool_c["dest.F"] * 0.95 + pool_c["fondo.F"] * 0.05
               - pool_c["alim.F"] * pool_c["alim.x0"])
check("C3. Balance por componente de la columna", comp_col < 1e-6, f"residuo {comp_col:.3e} mol/s")

# Balance de materia de toda la planta C
sale_c = pool_c["gas.F"] + pool_c["dest.F"] + pool_c["fondo.F"]
check("C4. Balance de materia de la planta entera", abs(sale_c - 100.0) < 1e-6,
      f"{sale_c:.8f} vs 100.0 mol/s")
for i, nombre in enumerate(NOMBRES):
    entra = caudal_componente(pool_c, "cruda", i)
    sale = (caudal_componente(pool_c, "gas", i) + caudal_componente(pool_c, "dest", i)
            + caudal_componente(pool_c, "fondo", i))
    check(f"C4. Planta entera por componente ({nombre})", abs(entra - sale) < 1e-6,
          f"{entra:.8f} vs {sale:.8f} mol/s")

# ======================================================================
print("\n" + "=" * 74)
print("Errores esperados (el simulador tiene que RECHAZARLOS, no adivinar)")
print("=" * 74)

e = DiagramaCorrientes(NOMBRES, proveedor=PROVEEDOR)
for c in ("a", "v", "l", "s"):
    e.agregar_corriente(c)
try:
    e.agregar_flash("X", "a", "v", "l", P_operacion=P, T_operacion=350.0, fraccion_vapor=0.5)
    check("E1. Flash sobre-especificado rechazado", False, "no lanzo error")
except ValueError as err:
    check("E1. Flash sobre-especificado rechazado", "UNA especificacion" in str(err))
try:
    e.agregar_intercambiador("Y", "a", "s")
    check("E2. Intercambiador sin especificacion rechazado", False, "no lanzo error")
except ValueError as err:
    check("E2. Intercambiador sin especificacion rechazado", "exactamente UNA" in str(err))

v = DiagramaCorrientes(NOMBRES, proveedor=PROVEEDOR)
for c in ("a", "s"):
    v.agregar_corriente(c)
v.agregar_valvula("V", "a", "s", P_salida=3.0 * P)
res_v = v.resolver(**{"a.F": 10.0, "a.T": 330.0, "a.P": P, "a.x0": 0.5})
check("E3. Valvula que subiria la presion: se avisa",
      any("no sube la presion" in m for m in res_v["errores_bloque"].values()),
      " | ".join(res_v["errores_bloque"].values())[:110])

sin_prov = DiagramaCorrientes(NOMBRES)
for c in ("a", "v", "l"):
    sin_prov.agregar_corriente(c)
try:
    sin_prov.agregar_flash("Z", "a", "v", "l", P_operacion=P)
    check("E4. Flash sin proveedor termodinamico rechazado", False, "no lanzo error")
except ValueError as err:
    check("E4. Flash sin proveedor termodinamico rechazado", "ProveedorTermodinamico" in str(err))

print("\n" + "=" * 74)
if fallos:
    print(f"FALLARON {len(fallos)}:")
    for f in fallos:
        print("   - " + f)
    sys.exit(1)
print("TODO OK -- las plantas encadenadas cierran en materia y en energia")
