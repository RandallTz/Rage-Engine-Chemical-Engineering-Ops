"""
Validacion del balance de energia del CSTR.

    F_in*h(T_in, x_in) + Q = F_out*h(T_out, x_out) + xi*dH_rxn(T_ref)

Lo que se contrasta, todo independiente del propio balance:

  1. Ida y vuelta entre los dos modos: el Q que calcula el modo isotermo,
     devuelto al modo "calor dado", tiene que reproducir la misma T.
  2. Caso degenerado xi=0 (sin reaccion): el reactor se vuelve un
     intercambiador, y su Q tiene que coincidir con la diferencia de
     entalpia calculada aparte.
  3. Q=0 con reaccion nula deja T_out = T_in exacto.
  4. Signo fisico: una exotermica sube T en adiabatico y pide refrigeracion
     (Q<0) en isotermo; una endotermica hace lo contrario.
  5. El calor de reaccion sale con el valor que da GestorReaccion.
  6. Linealidad en Q: duplicar el calor aportado duplica el salto de entalpia.
  7. El termino de reaccion esta en T_ref y NO en T_out: se comprueba
     midiendo que el balance cierra con dH_rxn(298.15) y NO cerraria si se
     usara un dH_rxn "corregido" a T_out (el error que se evita).
  8. Caso acoplado cinetica+energia: los dos residuos son cero, y el
     resultado es consistente con evaluar cinetica y balance por separado.
  9. Guardas: sin entalpia, sin dH_rxn, referencias distintas, y tanque
     hirviendo.

Ejecutar desde la raiz del proyecto:
    python tests/validar_energia_reactor.py
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
from thermodynamics.reaccion import GestorReaccion
from core.flash import EvaluadorFlash
from core.reactor_cstr import EvaluadorCSTR

fallos = []


def check(nombre, ok, detalle=""):
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}{(' -- ' + detalle) if detalle else ''}")
    if not ok:
        fallos.append(nombre)


print("=" * 74)
print("VALIDACION: balance de energia del CSTR")
print("=" * 74)

# Sistema MTBE: isobutileno + metanol -> MTBE. Fuertemente exotermico.
NOMBRES = ["isobutene", "methanol", "mtbe"]
NU = np.array([-1.0, -1.0, 1.0])
# Presion de operacion. NO es un numero de adorno: a 10 atm este mismo
# reactor adiabatico HIERVE (T_adiabatica=383.4 K contra una burbuja de
# 357.5 K), y la guarda _exigir_liquido lo rechaza -- se comprueba abajo,
# en el punto 9. A 30 atm la burbuja sube a 413 K y el tanque se mantiene
# liquido, que es el regimen en el que el modelo es valido.
P = 30.0 * 101325.0

prov = ProveedorTermodinamico(NOMBRES)
elv = CalculadoraELV(prov)
flash = EvaluadorFlash(elv)
# A calibrada para que el caso ACOPLADO tenga conversion significativa:
# con A=1e6 el avance sale ~3e-4 mol/s y el lazo T->r->xi->T no se
# ejercita (T no se mueve), o sea que el test pasaria sin probar nada.
gestor = GestorReaccion(prov, NU, A=1.0e10, Ea=60000.0)
ev = EvaluadorCSTR(NU, gestor_reaccion=gestor, evaluador_flash=flash)

print(f"\ndH_rxn = {gestor.dH_rxn/1000:.2f} kJ/mol (exotermica, valor conocido ~-57.6)")
print(f"T_ref entalpia = {flash.entalpia.T_ref} K   T_std reaccion = {gestor.T_std} K")

F_in = 100.0
x_in = np.array([0.45, 0.45, 0.10])
T_in = 330.0
xi = 12.0

# ------------------------------------------------------------------ 5
print()
Q_rxn = ev.calor_de_reaccion(xi)
check("5. El calor de reaccion es xi*dH_rxn",
      abs(Q_rxn - xi * gestor.dH_rxn) < 1e-9,
      f"{Q_rxn/1000:.2f} kW para xi={xi} mol/s")
check("5. Una exotermica libera calor (signo negativo)", Q_rxn < 0)

# ------------------------------------------------------------------ 4
print()
iso = ev.calor_necesario(F_in, x_in, T_in, xi, T_salida=T_in, P=P)
check("4. Exotermica isoterma: hay que REFRIGERAR (Q < 0)", iso["Q"] < 0,
      f"Q = {iso['Q']/1000:.1f} kW para mantener {T_in:.1f} K")

adia = ev.temperatura_desde_calor(F_in, x_in, T_in, xi, Q=0.0, P=P)
check("4. Exotermica adiabatica: la temperatura SUBE",
      adia["T_salida"] > T_in,
      f"{T_in:.2f} K -> {adia['T_salida']:.2f} K (+{adia['T_salida']-T_in:.2f} K)")

# ------------------------------------------------------------------ 1
print()
vuelta = ev.temperatura_desde_calor(F_in, x_in, T_in, xi, Q=iso["Q"], P=P)
check("1. Ida y vuelta isotermo -> calor dado reproduce la T",
      abs(vuelta["T_salida"] - T_in) < 1e-8,
      f"T recuperada = {vuelta['T_salida']:.10f} K")

iso2 = ev.calor_necesario(F_in, x_in, T_in, xi, T_salida=adia["T_salida"], P=P)
check("1. Ida y vuelta adiabatico -> isotermo devuelve Q = 0",
      abs(iso2["Q"]) < 1e-6,
      f"Q = {iso2['Q']:.6e} W")

# ------------------------------------------------------------------ 2
print()
ev_sin_rxn = EvaluadorCSTR(NU, gestor_reaccion=gestor, evaluador_flash=flash)
sin_avance = ev_sin_rxn.calor_necesario(F_in, x_in, T_in, 0.0, T_salida=T_in + 20.0, P=P)
h1 = flash.entalpia.h_liquido(T_in, x_in)
h2 = flash.entalpia.h_liquido(T_in + 20.0, x_in)
check("2. Con xi=0 el reactor es un intercambiador",
      abs(sin_avance["Q"] - F_in * (h2 - h1)) < 1e-6,
      f"Q = {sin_avance['Q']/1000:.4f} kW vs F*(h2-h1) = {F_in*(h2-h1)/1000:.4f} kW")

# ------------------------------------------------------------------ 3
print()
nulo = ev.temperatura_desde_calor(F_in, x_in, T_in, 0.0, Q=0.0, P=P)
check("3. Sin reaccion y sin calor, T no cambia",
      abs(nulo["T_salida"] - T_in) < 1e-9,
      f"T_salida = {nulo['T_salida']:.12f} K")

# ------------------------------------------------------------------ 6
print()
r1 = ev.temperatura_desde_calor(F_in, x_in, T_in, xi, Q=1.0e5, P=P)
r2 = ev.temperatura_desde_calor(F_in, x_in, T_in, xi, Q=2.0e5, P=P)
r0 = ev.temperatura_desde_calor(F_in, x_in, T_in, xi, Q=0.0, P=P)
salto1 = r1["F_out"] * r1["h_out"] - r0["F_out"] * r0["h_out"]
salto2 = r2["F_out"] * r2["h_out"] - r0["F_out"] * r0["h_out"]
check("6. Duplicar Q duplica el salto de entalpia total",
      abs(salto1 - 1.0e5) < 1e-6 and abs(salto2 - 2.0e5) < 1e-6,
      f"{salto1:.4f} W y {salto2:.4f} W")
check("6. Mas calor, mas temperatura", r0["T_salida"] < r1["T_salida"] < r2["T_salida"],
      f"{r0['T_salida']:.2f} < {r1['T_salida']:.2f} < {r2['T_salida']:.2f} K")

# ------------------------------------------------------------------ 7
print()
# El balance tiene que cerrar con dH_rxn en T_ref. Se comprueba armando
# el residuo a mano con las dos versiones: la correcta y la que seria el
# error clasico (dH_rxn "corregido" a T_out con la ley de Kirchhoff).
res = adia
F_out, x_out = res["F_out"], res["x_out"]
h_in_v = flash.entalpia.h_liquido(T_in, x_in)
h_out_v = flash.entalpia.h_liquido(res["T_salida"], x_out)
residuo_correcto = F_in * h_in_v - F_out * h_out_v - xi * gestor.dH_rxn
check("7. El balance cierra con dH_rxn evaluado en T_ref",
      abs(residuo_correcto) < 1e-6,
      f"residuo = {residuo_correcto:.6e} W")

# Kirchhoff: dH_rxn(T) = dH_rxn(T_ref) + sum(nu_i * [h_i(T) - h_i(T_ref)])
h_puros_T = flash.entalpia._h_puros_liquido(res["T_salida"])
dH_rxn_en_T = gestor.dH_rxn + float(np.dot(NU, h_puros_T))
residuo_doble = F_in * h_in_v - F_out * h_out_v - xi * dH_rxn_en_T
check("7. Usar dH_rxn(T_out) NO cerraria (es el doble conteo que se evita)",
      abs(residuo_doble) > 1.0,
      f"residuo = {residuo_doble:.2f} W, o sea {abs(residuo_doble)/1000:.2f} kW de error")
check("7. Y el error es exactamente xi*sum(nu_i*[h_i(T_out)-h_i(T_ref)])",
      abs(residuo_doble - (-xi * float(np.dot(NU, h_puros_T)))) < 1e-6,
      f"{residuo_doble:.4f} vs {-xi*float(np.dot(NU,h_puros_T)):.4f} W")

# ------------------------------------------------------------------ 8
print()
V = 1.5
aco = ev.resolver_con_cinetica(F_in, x_in, T_in, V, Q=0.0, P=P)
print(f"  Adiabatico con V={V} m3: xi={aco['xi']:.4f} mol/s, "
      f"T={aco['T_salida']:.2f} K (+{aco['T_salida']-T_in:.2f} K), residuo={aco['residual']:.2e}")
check("8. El sistema acoplado converge", aco["residual"] < 1e-9)

xi_cinetica = ev.avance_desde_cinetica(V, aco["T_salida"], aco["x_out"])
check("8. La cinetica evaluada aparte reproduce el avance",
      abs(xi_cinetica - aco["xi"]) < 1e-7,
      f"{xi_cinetica:.10f} vs {aco['xi']:.10f} mol/s")

comprobar = ev.temperatura_desde_calor(F_in, x_in, T_in, aco["xi"], Q=0.0, P=P)
check("8. El balance evaluado aparte reproduce la temperatura",
      abs(comprobar["T_salida"] - aco["T_salida"]) < 1e-9,
      f"{comprobar['T_salida']:.10f} K")

print()
anterior = None
for V_i in (0.5, 1.0, 2.0, 4.0):
    r = ev.resolver_con_cinetica(F_in, x_in, T_in, V_i, Q=0.0, P=P)
    creciente = anterior is None or (r["xi"] > anterior["xi"] and r["T_salida"] > anterior["T_salida"])
    check(f"8. V={V_i} m3 -> xi={r['xi']:.3f} mol/s, T={r['T_salida']:.2f} K",
          r["residual"] < 1e-9 and creciente,
          "mas volumen -> mas avance y mas temperatura")
    anterior = r

# Con calor retirado, el mismo tanque convierte menos (menos T, menos r)
frio = ev.resolver_con_cinetica(F_in, x_in, T_in, 2.0, Q=-3.0e5, P=P)
calido = ev.resolver_con_cinetica(F_in, x_in, T_in, 2.0, Q=0.0, P=P)
check("8. Retirar calor baja la temperatura y el avance",
      frio["T_salida"] < calido["T_salida"] and frio["xi"] < calido["xi"],
      f"T {calido['T_salida']:.2f} -> {frio['T_salida']:.2f} K, "
      f"xi {calido['xi']:.3f} -> {frio['xi']:.3f} mol/s")

# --- 8b. El limite de volumen grande: EQUILIBRIO QUIMICO.
# Esta es la comprobacion mas fuerte del acoplamiento, porque ata tres
# piezas independientes: el balance de energia (que fija T), van't Hoff
# (que da K_eq a esa T) y la cinetica (cuyo termino inverso es el que
# frena la reaccion). Si el reactor es lo bastante grande, r -> 0 y la
# salida tiene que estar en equilibrio quimico A LA TEMPERATURA QUE EL
# PROPIO BALANCE PRODUJO -- no a la de entrada.
#
# Y explica la forma de la curva de arriba: con una exotermica, subir T
# BAJA K_eq (van't Hoff), asi que el calor que libera la reaccion limita
# su propia conversion. Por eso xi se satura en ~10.3 mol/s y no sigue
# creciendo con V.
print()
cocientes = []
for V_i in (1.0, 8.0, 40.0):
    r = ev.resolver_con_cinetica(F_in, x_in, T_in, V_i, Q=0.0, P=P)
    gamma = prov.coeficientes_actividad(r["T_salida"], r["x_out"])
    actividad = r["x_out"] * gamma
    producto = float(np.prod(actividad ** NU))
    K = float(gestor.K_eq(r["T_salida"]))
    cocientes.append(producto / K)
    print(f"  V={V_i:5.1f} m3: xi={r['xi']:7.4f}  T={r['T_salida']:6.2f} K  "
          f"prod(a^nu)={producto:.5f}  K_eq(T)={K:.5f}  cociente={producto/K:.5f}")

check("8b. Con mas volumen, la salida se acerca al equilibrio quimico",
      cocientes[0] < cocientes[1] < cocientes[2],
      f"cociente prod(a^nu)/K_eq: {cocientes[0]:.4f} -> {cocientes[1]:.4f} -> {cocientes[2]:.4f}")
check("8b. Y con V grande practicamente lo alcanza", cocientes[-1] > 0.98,
      f"{cocientes[-1]:.5f} (1.0 seria equilibrio exacto)")
check("8b. K_eq baja al subir T (exotermica): la reaccion limita su propia conversion",
      gestor.K_eq(330.0) > gestor.K_eq(377.0),
      f"K_eq(330 K)={float(gestor.K_eq(330.0)):.4f} > K_eq(377 K)={float(gestor.K_eq(377.0)):.4f}")

# ------------------------------------------------------------------ 9
print()
sin_flash = EvaluadorCSTR(NU, gestor_reaccion=gestor)
try:
    sin_flash.calor_necesario(F_in, x_in, T_in, xi, T_salida=T_in)
    check("9. Sin entalpia, avisa", False, "no lanzo error")
except ValueError as e:
    check("9. Sin entalpia, avisa", "balance de energia" in str(e))

sin_dh = EvaluadorCSTR(NU, evaluador_flash=flash)
try:
    sin_dh.calor_necesario(F_in, x_in, T_in, xi, T_salida=T_in)
    check("9. Sin dH_rxn, avisa", False, "no lanzo error")
except ValueError as e:
    check("9. Sin dH_rxn, avisa", "calor de reaccion" in str(e))

# Referencias distintas: se fabrica un gestor con otro T_std
gestor_raro = GestorReaccion(prov, NU, A=1.0e6, Ea=60000.0, T_std=310.0)
ev_raro = EvaluadorCSTR(NU, gestor_reaccion=gestor_raro, evaluador_flash=flash)
try:
    ev_raro.calor_necesario(F_in, x_in, T_in, xi, T_salida=T_in)
    check("9. Referencias distintas, avisa", False, "no lanzo error")
except ValueError as e:
    check("9. Referencias distintas, avisa", "no coinciden" in str(e), str(e)[:90])

# Tanque hirviendo: a presion atmosferica, la exotermica pasa la burbuja
try:
    ev.temperatura_desde_calor(F_in, x_in, T_in, xi, Q=0.0, P=101325.0)
    check("9. Tanque hirviendo, avisa", False, "no lanzo error")
except ValueError as e:
    check("9. Tanque hirviendo, avisa", "hirviendo" in str(e), str(e)[:100])

permisivo = ev.temperatura_desde_calor(F_in, x_in, T_in, xi, Q=0.0, P=101325.0,
                                       exigir_liquido=False)
check("9. Con exigir_liquido=False devuelve el numero y la T de burbuja",
      permisivo["T_burbuja_salida"] is not None
      and permisivo["T_salida"] > permisivo["T_burbuja_salida"],
      f"T={permisivo['T_salida']:.2f} K > burbuja {permisivo['T_burbuja_salida']:.2f} K")

# ------------------------------------------------------------------
print()
# Endotermica: se invierte el signo de dH_rxn a mano sobre el mismo sistema.
ev_endo = EvaluadorCSTR(NU, gestor_reaccion=gestor, evaluador_flash=flash,
                        dH_rxn=-gestor.dH_rxn)
endo_adia = ev_endo.temperatura_desde_calor(F_in, x_in, T_in, xi, Q=0.0, P=P)
endo_iso = ev_endo.calor_necesario(F_in, x_in, T_in, xi, T_salida=T_in, P=P)
check("Endotermica adiabatica: la temperatura BAJA", endo_adia["T_salida"] < T_in,
      f"{T_in:.2f} K -> {endo_adia['T_salida']:.2f} K")
check("Endotermica isoterma: hay que CALENTAR (Q > 0)", endo_iso["Q"] > 0,
      f"Q = {endo_iso['Q']/1000:.1f} kW")
# OJO: NO es cierto que Q_endo = -Q_exo. Q = [F_out*h_out - F_in*h_in] + xi*dH,
# y cambiar el signo de dH solo cambia el SEGUNDO termino; el primero (calor
# sensible por el cambio de composicion y de T) es el mismo en los dos casos.
# La identidad que si se cumple, y que aisla el termino de reaccion, es:
#     Q_exo - Q_endo = 2*xi*dH_rxn
check("La diferencia exotermica/endotermica aisla 2*xi*dH_rxn",
      abs((iso["Q"] - endo_iso["Q"]) - 2.0 * xi * gestor.dH_rxn) < 1e-6,
      f"{iso['Q'] - endo_iso['Q']:.4f} vs {2.0*xi*gestor.dH_rxn:.4f} W")


# ======================================================================
print("\n" + "=" * 74)
print("EL REACTOR DENTRO DEL FLOWSHEET")
print("=" * 74)

from core.diagrama_corrientes import DiagramaCorrientes


def armar(modo, **kw):
    d = DiagramaCorrientes(NOMBRES, proveedor=prov)
    for c in ("ali", "pro"):
        d.agregar_corriente(c)
    d.agregar_reactor_cstr("R1", "ali", "pro", NU, gestor_reaccion=gestor,
                           modo_energia=modo, **kw)
    return d


BASE = {"ali.F": F_in, "ali.T": T_in, "ali.P": P, "ali.x0": 0.45, "ali.x1": 0.45}


def balance_cierra(pool, tolerancia=1e-6):
    """F_in*h_in + Q = F_out*h_out + xi*dH_rxn, leido del pool."""
    x_in_p = np.array([pool["ali.x0"], pool["ali.x1"], pool["ali.x2"]])
    x_out_p = np.array([pool["pro.x0"], pool["pro.x1"], pool["pro.x2"]])
    h_in_p = flash.entalpia.h_liquido(pool["ali.T"], x_in_p)
    h_out_p = flash.entalpia.h_liquido(pool["pro.T"], x_out_p)
    residuo = (pool["ali.F"] * h_in_p + pool["R1.Q"]
               - pool["pro.F"] * h_out_p - pool["R1.xi"] * gestor.dH_rxn)
    return residuo


# --- isotermo: se da T, se calcula el calor que cuesta
print()
d_iso = armar("isotermo")
datos_iso = {**BASE, "R1.T": T_in, "R1.xi": xi}
gl_iso = d_iso.grados_de_libertad(datos_iso)
res_iso = d_iso.resolver(**datos_iso)
p_iso = res_iso["pool"]
check("F1. Isotermo: GL = 0 y resuelve entero",
      gl_iso["grados_de_libertad"] == 0 and res_iso["completo"],
      f"GL={gl_iso['grados_de_libertad']}, restantes={res_iso['incognitas_restantes'][:3]}")
check("F1. El Q del flowsheet coincide con el del evaluador",
      abs(p_iso["R1.Q"] - iso["Q"]) < 1e-6,
      f"{p_iso['R1.Q']/1000:.4f} kW vs {iso['Q']/1000:.4f} kW")
check("F1. Q < 0: el reactor isotermo necesita REFRIGERACION",
      p_iso["R1.Q"] < 0,
      f"{p_iso['R1.Q']/1000:.1f} kW, un dato que antes el simulador no daba")
check("F1. El balance de energia cierra en el pool",
      abs(balance_cierra(p_iso)) < 1e-6,
      f"residuo = {balance_cierra(p_iso):.3e} W")

# --- adiabatico CON cinetica: el caso acoplado
print()
d_adia = armar("adiabatico")
datos_adia = {**BASE, "R1.V": 2.0}
gl_adia = d_adia.grados_de_libertad(datos_adia)
res_adia = d_adia.resolver(**datos_adia)
p_adia = res_adia["pool"]
check("F2. Adiabatico + cinetica: GL = 0 y resuelve entero",
      gl_adia["grados_de_libertad"] == 0 and res_adia["completo"],
      f"GL={gl_adia['grados_de_libertad']}, restantes={res_adia['incognitas_restantes'][:3]}")
directo = ev.resolver_con_cinetica(F_in, x_in, T_in, 2.0, Q=0.0, P=P)
check("F2. Coincide con el evaluador llamado directamente",
      abs(p_adia["R1.xi"] - directo["xi"]) < 1e-8
      and abs(p_adia["R1.T"] - directo["T_salida"]) < 1e-8,
      f"xi={p_adia['R1.xi']:.6f} mol/s, T={p_adia['R1.T']:.4f} K")
check("F2. La T del tanque se propaga a la corriente de salida",
      abs(p_adia["pro.T"] - p_adia["R1.T"]) < 1e-12)
check("F2. Q = 0 exacto", abs(p_adia["R1.Q"]) < 1e-12)
check("F2. El balance de energia cierra en el pool",
      abs(balance_cierra(p_adia)) < 1e-6,
      f"residuo = {balance_cierra(p_adia):.3e} W")
check("F2. Una exotermica adiabatica calienta la corriente",
      p_adia["pro.T"] > p_adia["ali.T"],
      f"{p_adia['ali.T']:.2f} K -> {p_adia['pro.T']:.2f} K")

# --- adiabatico SIN cinetica: xi dado, no hay acoplamiento
print()
d_sin = DiagramaCorrientes(NOMBRES, proveedor=prov)
for c in ("ali", "pro"):
    d_sin.agregar_corriente(c)
d_sin.agregar_reactor_cstr("R1", "ali", "pro", NU, gestor_reaccion=gestor,
                           con_cinetica=False, modo_energia="adiabatico")
datos_sin = {**BASE, "R1.xi": xi}
gl_sin = d_sin.grados_de_libertad(datos_sin)
res_sin = d_sin.resolver(**datos_sin)
p_sin = res_sin["pool"]
check("F3. Adiabatico sin cinetica: GL = 0 y resuelve",
      gl_sin["grados_de_libertad"] == 0 and res_sin["completo"],
      f"GL={gl_sin['grados_de_libertad']}, T={p_sin.get('R1.T')}")
check("F3. Da la misma T que el evaluador",
      abs(p_sin["R1.T"] - adia["T_salida"]) < 1e-8,
      f"{p_sin['R1.T']:.6f} K vs {adia['T_salida']:.6f} K")

# --- calor dado
print()
d_q = armar("calor_dado", Q=-3.0e5)
datos_q = {**BASE, "R1.V": 2.0}
res_q = d_q.resolver(**datos_q)
p_q = res_q["pool"]
check("F4. Calor dado: resuelve y respeta el Q pedido",
      res_q["completo"] and abs(p_q["R1.Q"] + 3.0e5) < 1e-9,
      f"T={p_q['R1.T']:.2f} K, xi={p_q['R1.xi']:.4f} mol/s")
check("F4. Retirar calor enfria y convierte menos que el adiabatico",
      p_q["R1.T"] < p_adia["R1.T"] and p_q["R1.xi"] < p_adia["R1.xi"],
      f"T {p_adia['R1.T']:.2f} -> {p_q['R1.T']:.2f} K, "
      f"xi {p_adia['R1.xi']:.4f} -> {p_q['R1.xi']:.4f} mol/s")
check("F4. El balance de energia cierra en el pool",
      abs(balance_cierra(p_q)) < 1e-6,
      f"residuo = {balance_cierra(p_q):.3e} W")

# --- compatibilidad hacia atras: un reactor SIN proveedor sigue funcionando
print()
d_viejo = DiagramaCorrientes(NOMBRES)
for c in ("ali", "pro"):
    d_viejo.agregar_corriente(c)
d_viejo.agregar_reactor_cstr("R1", "ali", "pro", NU, gestor_reaccion=gestor)
res_viejo = d_viejo.resolver(**{**BASE, "R1.T": T_in, "R1.xi": xi})
p_viejo = res_viejo["pool"]
check("F5. Sin proveedor, el reactor sigue funcionando como antes",
      abs(p_viejo["pro.F"] - (F_in + sum(NU) * xi)) < 1e-9
      and "R1.Q" not in p_viejo,
      f"pro.F={p_viejo['pro.F']:.4f} mol/s, sin variable Q (no hay balance de energia)")

# --- guardas
print()
try:
    armar("lo_que_sea")
    check("F6. modo_energia desconocido rechazado", False, "no lanzo error")
except ValueError as e:
    check("F6. modo_energia desconocido rechazado", "modo_energia desconocido" in str(e))

try:
    armar("isotermo", Q=-1.0e5)
    check("F6. Dar Q en modo isotermo rechazado", False, "no lanzo error")
except ValueError as e:
    check("F6. Dar Q en modo isotermo rechazado", "es el RESULTADO" in str(e))

try:
    armar("calor_dado")
    check("F6. calor_dado sin Q rechazado", False, "no lanzo error")
except ValueError as e:
    check("F6. calor_dado sin Q rechazado", "necesita Q" in str(e))

d_np = DiagramaCorrientes(NOMBRES)
for c in ("ali", "pro"):
    d_np.agregar_corriente(c)
try:
    d_np.agregar_reactor_cstr("R1", "ali", "pro", NU, gestor_reaccion=gestor,
                              modo_energia="adiabatico")
    check("F6. Adiabatico sin proveedor rechazado", False, "no lanzo error")
except ValueError as e:
    check("F6. Adiabatico sin proveedor rechazado", "balance de energia" in str(e))

print("\n" + "=" * 74)
if fallos:
    print(f"FALLARON {len(fallos)}:")
    for f in fallos:
        print("   - " + f)
    sys.exit(1)
print("TODO OK")
