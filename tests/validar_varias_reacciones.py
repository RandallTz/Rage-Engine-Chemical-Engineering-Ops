"""
Validacion de VARIAS REACCIONES A LA VEZ, capa termodinamica.

Por que esto importa mas que otro equipo. El simulador se llama de
destilacion reactiva y hasta ahora solo admitia UNA reaccion, cuando casi
ningun sistema real tiene una sola. El propio MTBE, que es el caso de
referencia del proyecto, tiene una secundaria documentada: el isobuteno
dimeriza.

    R1:  isobuteno + metanol  ->  MTBE                (la que se quiere)
    R2:  2 isobuteno          ->  diisobuteno         (la que estorba)

Las dos consumen isobuteno, y ese es justo el acoplamiento interesante:
la selectividad. Con una sola reaccion no se puede ni plantear.

Como se valida sin literatura. No hace falta ninguna referencia externa
para esta capa, porque las dos reacciones en paralelo tienen invariantes
que se comprueban contra el caso de UNA reaccion, que ya esta validado:

  1. **Partir una reaccion en dos mitades identicas** (mismo nu, A/2 cada
     una) tiene que dar la misma velocidad total y el mismo avance. Es la
     prueba mas fuerte que existe aqui: si la maquinaria de varias
     reacciones esta mal, este caso NO puede salir igual que el de una.
  2. **Dos reacciones con componentes disjuntos** tienen que dar
     exactamente el mismo resultado que resolverlas por separado. Si se
     contaminan entre si, se ve aqui.
  3. **Duplicar la estequiometria de una reaccion eleva K_eq al
     cuadrado**, porque DeltaG se duplica. Es una identidad
     termodinamica, no una convencion del codigo.
  4. **Los calores se SUMAN con su signo**: con una exotermica y una
     endotermica compensadas, el calor total es cero exacto.

Ejecutar desde la raiz del proyecto:
    python tests/validar_varias_reacciones.py
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

fallos = []


def check(nombre, ok, detalle=""):
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}{(' -- ' + detalle) if detalle else ''}")
    if not ok:
        fallos.append(nombre)


# El sistema real: MTBE con su reaccion secundaria.
MTBE4 = ["isobutene", "methanol", "mtbe", "2,4,4-trimethyl-1-pentene"]
prov4 = ProveedorTermodinamico(MTBE4)

NU_MTBE = [-1.0, -1.0, 1.0, 0.0]      # isobuteno + metanol -> MTBE
NU_DIM = [-2.0, 0.0, 0.0, 1.0]        # 2 isobuteno -> diisobuteno

A1, EA1 = 1.0e4, 45000.0
A2, EA2 = 5.0e3, 60000.0              # la secundaria, mas lenta y mas activada

T = 350.0
X = np.array([0.30, 0.30, 0.30, 0.10])


# ======================================================================
print("\n" + "=" * 74)
print("1. UNA REACCION PARTIDA EN DOS MITADES IDENTICAS")
print("=" * 74)
# ======================================================================
# Si R se parte en dos copias con A/2 cada una, la velocidad total debe
# ser identica a la de la original. Es la comprobacion que de verdad
# ancla todo lo demas: pasa por la matriz, por las productorias por filas
# y por la suma de avances, y solo sale bien si las tres estan bien.

una = GestorReaccion(prov4, NU_MTBE, A1, EA1)
dos_mitades = GestorReaccion(prov4, [NU_MTBE, NU_MTBE], [A1 / 2, A1 / 2], [EA1, EA1])

r_una = una.velocidad_reaccion(T, X)
r_mitades = dos_mitades.velocidades(T, X)

check("1.1 El gestor de una reacción sigue devolviendo un escalar",
      isinstance(r_una, float), f"r = {r_una:.10e}")
check("1.2 El de dos devuelve un valor por reacción",
      r_mitades.shape == (2,), f"formas {r_mitades.shape}")
check("1.3 Las dos mitades suman EXACTAMENTE la velocidad original",
      abs(r_mitades.sum() - r_una) <= 1e-12 * abs(r_una),
      f"{r_mitades.sum():.12e} vs {r_una:.12e}")
check("1.4 Y cada mitad es la mitad",
      abs(r_mitades[0] - r_una / 2) <= 1e-12 * abs(r_una),
      f"{r_mitades[0]:.10e}")

# El calor tambien: media reaccion dos veces es una reaccion entera.
xi = 3.0
check("1.5 El calor de las dos mitades iguala el de la reacción entera",
      abs(dos_mitades.calor_liberado([xi / 2, xi / 2]) - xi * una.dH_rxn) <= 1e-9 * abs(xi * una.dH_rxn),
      f"{dos_mitades.calor_liberado([xi / 2, xi / 2]):.6f} vs {xi * una.dH_rxn:.6f} J/s")

# Y la composicion de salida.
n_in = np.array([10.0, 10.0, 0.0, 0.0])
check("1.6 Y el desplazamiento de composición es el mismo",
      np.allclose(dos_mitades.desplazamiento_composicion(n_in, [xi / 2, xi / 2]),
                  una.desplazamiento_composicion(n_in, [xi]), rtol=0, atol=1e-12))


# ======================================================================
print("\n" + "=" * 74)
print("2. DOS REACCIONES QUE NO SE TOCAN NO SE CONTAMINAN")
print("=" * 74)
# ======================================================================
# Con componentes disjuntos, cada velocidad tiene que salir identica a la
# que daria su reaccion sola. Si las productorias se hicieran sobre la
# matriz entera en vez de por filas, aqui se veria: cada reaccion
# recogeria las actividades de la otra.

CUATRO = ["benzene", "toluene", "n-hexane", "n-heptane"]
prov_d = ProveedorTermodinamico(CUATRO)
NU_A = [-1.0, 1.0, 0.0, 0.0]          # benceno -> tolueno (ficticia, da igual)
NU_B = [0.0, 0.0, -1.0, 1.0]          # hexano -> heptano (ficticia)
X_d = np.array([0.25, 0.25, 0.25, 0.25])

sola_A = GestorReaccion(prov_d, NU_A, 1e3, 40000.0)
sola_B = GestorReaccion(prov_d, NU_B, 7e2, 52000.0)
juntas = GestorReaccion(prov_d, [NU_A, NU_B], [1e3, 7e2], [40000.0, 52000.0])

v = juntas.velocidades(T, X_d)
check("2.1 La primera sale igual que si estuviera sola",
      abs(v[0] - sola_A.velocidad_reaccion(T, X_d)) <= 1e-12 * abs(v[0]),
      f"{v[0]:.12e}")
check("2.2 Y la segunda también",
      abs(v[1] - sola_B.velocidad_reaccion(T, X_d)) <= 1e-12 * abs(v[1]),
      f"{v[1]:.12e}")
check("2.3 Sus K_eq también son independientes",
      np.allclose(juntas.K_eq_de_cada_una(T),
                  [sola_A.K_eq(T), sola_B.K_eq(T)], rtol=1e-13, atol=0))


# ======================================================================
print("\n" + "=" * 74)
print("3. IDENTIDADES TERMODINAMICAS")
print("=" * 74)
# ======================================================================
# Duplicar la estequiometria duplica DeltaG, y K = exp(-DeltaG/RT) se
# eleva al cuadrado. Es termodinamica, no una convencion del codigo: si
# saliera K*2 en vez de K^2, el equilibrio estaria mal planteado.

doble = GestorReaccion(prov4, [2.0 * np.array(NU_MTBE)], A1, EA1)
K1 = float(una.K_eq(T))
K2 = float(doble.K_eq_de_cada_una(T)[0])
check("3.1 Duplicar la estequiometría eleva K_eq al CUADRADO",
      abs(K2 - K1 ** 2) <= 1e-9 * K2, f"K = {K1:.6f}, K_doble = {K2:.6f}, K² = {K1**2:.6f}")
check("3.2 Y duplica ΔH_rxn",
      abs(doble.dH_rxn_de_cada_una[0] - 2 * una.dH_rxn) <= 1e-9 * abs(2 * una.dH_rxn),
      f"{doble.dH_rxn_de_cada_una[0]:.2f} vs {2*una.dH_rxn:.2f} J/mol")

# Invertir una reaccion invierte K y cambia el signo de dH. El equilibrio
# no distingue "sentido": es la misma restriccion escrita al reves.
inversa = GestorReaccion(prov4, [-np.array(NU_MTBE)], A1, EA1)
check("3.3 Invertir la reacción invierte K_eq",
      abs(float(inversa.K_eq_de_cada_una(T)[0]) - 1.0 / K1) <= 1e-9 / K1,
      f"1/K = {1/K1:.6e}")
check("3.4 Y le cambia el signo a ΔH_rxn",
      abs(inversa.dH_rxn_de_cada_una[0] + una.dH_rxn) <= 1e-9 * abs(una.dH_rxn))

# Los calores se SUMAN con su signo: dos reacciones compensadas dan cero
# exacto. Es lo que permite que un reactor con una exotermica y una
# endotermica salga adiabatico de verdad.
par = GestorReaccion(prov4, [NU_MTBE, -np.array(NU_MTBE)], A1, EA1)
check("3.5 Dos reacciones opuestas con el mismo avance dan calor CERO",
      abs(par.calor_liberado([5.0, 5.0])) < 1e-9,
      f"{par.calor_liberado([5.0, 5.0]):.3e} W")
check("3.6 Y con avances distintos, la diferencia exacta",
      abs(par.calor_liberado([5.0, 2.0]) - 3.0 * una.dH_rxn) <= 1e-9 * abs(3.0 * una.dH_rxn),
      f"{par.calor_liberado([5.0, 2.0]):.3f} vs {3.0*una.dH_rxn:.3f} W")


# ======================================================================
print("\n" + "=" * 74)
print("4. EL SISTEMA REAL: MTBE CON SU SECUNDARIA")
print("=" * 74)
# ======================================================================

mtbe = GestorReaccion(prov4, [NU_MTBE, NU_DIM], [A1, A2], [EA1, EA2])
check("4.1 Se construye con dos reacciones y cuatro componentes",
      mtbe.n_reacciones == 2 and mtbe.NU.shape == (2, 4), f"NU {mtbe.NU.shape}")

dH = mtbe.dH_rxn_de_cada_una
check("4.2 Las dos son exotérmicas, como corresponde a una adición",
      dH[0] < 0 and dH[1] < 0,
      f"ΔH₁ = {dH[0]/1000:.1f} kJ/mol, ΔH₂ = {dH[1]/1000:.1f} kJ/mol")

vel = mtbe.velocidades(T, X)
check("4.3 Las dos avanzan hacia los productos a esta composición",
      vel[0] > 0 and vel[1] > 0, f"r₁ = {vel[0]:.4e}, r₂ = {vel[1]:.4e}")

# El acoplamiento: las dos consumen isobuteno. La columna 0 de NU es
# negativa en las dos filas, y el consumo total es la suma -- que es lo
# que hace que la selectividad sea un problema de verdad.
consumo_isobuteno = -mtbe.NU[:, 0]
check("4.4 Las dos compiten por el isobuteno",
      all(consumo_isobuteno > 0),
      f"R1 consume {consumo_isobuteno[0]:.0f}, R2 consume {consumo_isobuteno[1]:.0f} por avance")

n_in = np.array([100.0, 60.0, 0.0, 0.0])
n_out = mtbe.desplazamiento_composicion(n_in, [40.0, 5.0])
check("4.5 El balance por componente sale del producto NUᵗ·ξ",
      np.allclose(n_out, [100 - 40 - 10, 60 - 40, 40, 5], atol=1e-12),
      f"n_salida = {np.round(n_out, 4)}")
# El metanol limita R1 y no interviene en R2: la estequiometria tiene que
# reflejarlo o el reactor podria "producir" MTBE sin metanol.
check("4.6 El metanol solo lo consume R1",
      mtbe.NU[1, 1] == 0.0)

# Y la selectividad, que es la pregunta que estas dos reacciones
# plantean y que con una sola no existe.
xi1, xi2 = 40.0, 5.0
selectividad = xi1 / (xi1 + 2 * xi2)
check("4.7 La selectividad hacia MTBE es calculable y menor que 1",
      0 < selectividad < 1,
      f"{selectividad:.4f} del isobuteno consumido va a MTBE")

# El calor total NO es el de la principal: ignorar la secundaria
# subestimaria la refrigeracion necesaria.
Q_total = mtbe.calor_liberado([xi1, xi2])
Q_solo_principal = xi1 * dH[0]
check("4.8 El calor total excede el de la reacción principal sola",
      abs(Q_total) > abs(Q_solo_principal),
      f"total {Q_total/1e6:.3f} MW vs solo R1 {Q_solo_principal/1e6:.3f} MW "
      f"({100*(abs(Q_total)/abs(Q_solo_principal)-1):.1f}% más)")


# ======================================================================
print("\n" + "=" * 74)
print("5. LO QUE DEBE REVENTAR, Y POR QUE")
print("=" * 74)
# ======================================================================
# La parte mas importante de este diseno. Los nombres en singular NO
# devuelven el de la primera reaccion: lanzan error. Un balance escrito
# como xi*dH_rxn es correcto con una reaccion y silenciosamente FALSO con
# tres, y seguiria corriendo.

for nombre, accion in [
    ("dH_rxn", lambda: mtbe.dH_rxn),
    ("dG_rxn", lambda: mtbe.dG_rxn),
    ("K_eq_std", lambda: mtbe.K_eq_std),
    ("K_eq()", lambda: mtbe.K_eq(T)),
    ("velocidad_reaccion()", lambda: mtbe.velocidad_reaccion(T, X)),
]:
    try:
        accion()
        check(f"5.x '{nombre}' en singular revienta con varias reacciones", False,
              "devolvió un valor en vez de avisar")
    except ValueError as e:
        menciona = "de_cada_una" in str(e) or "velocidades" in str(e)
        check(f"5.x '{nombre}' en singular revienta y dice qué usar", menciona,
              str(e)[:95])

errores = [
    ("nu de 3 dimensiones", lambda: GestorReaccion(prov4, np.zeros((2, 2, 4)) + 1, A1, EA1)),
    ("nu con otro número de componentes",
     lambda: GestorReaccion(prov4, [-1.0, 1.0], A1, EA1)),
    ("una fila de nu toda a cero",
     lambda: GestorReaccion(prov4, [NU_MTBE, [0.0, 0.0, 0.0, 0.0]], A1, EA1)),
    ("3 valores de A para 2 reacciones",
     lambda: GestorReaccion(prov4, [NU_MTBE, NU_DIM], [1.0, 2.0, 3.0], EA1)),
    ("avances de más al desplazar",
     lambda: mtbe.desplazamiento_composicion(n_in, [1.0, 2.0, 3.0])),
    ("avances de menos al dar calor", lambda: mtbe.calor_liberado([1.0])),
]
for nombre, accion in errores:
    try:
        accion()
        check(f"5.y {nombre} -> error", False, "no reventó")
    except ValueError as e:
        check(f"5.y {nombre} -> error", True, str(e)[:80])

# Un escalar para A con varias reacciones SI vale: es lo razonable al
# tantear, y significa "el mismo para todas".
try:
    g = GestorReaccion(prov4, [NU_MTBE, NU_DIM], A1, EA1)
    check("5.z Un A escalar con varias reacciones vale: el mismo para todas",
          np.allclose(g.A, [A1, A1]) and np.allclose(g.Ea, [EA1, EA1]))
except Exception as e:
    check("5.z Un A escalar con varias reacciones vale", False, str(e)[:80])


# ======================================================================
print("\n" + "=" * 74)
print("6. LOS REACTORES CON VARIAS REACCIONES")
print("=" * 74)
# ======================================================================
# La misma idea de la seccion 1, ahora sobre los reactores completos:
# partir una reaccion en dos mitades identicas tiene que dar EL MISMO
# resultado que la reaccion entera. Si la estequiometria matricial, los
# arranques del solver o el balance de energia estuvieran mal, este caso
# no podria salir igual.

from core.flash import EvaluadorFlash
from core.reactor_cstr import EvaluadorCSTR
from core.reactor_pfr import EvaluadorPFR
from thermodynamics.elv import CalculadoraELV

calc4 = CalculadoraELV(prov4)
flash4 = EvaluadorFlash(calc4)

F_IN = 100.0
X_IN = np.array([0.5, 0.5, 0.0, 0.0])      # isobuteno + metanol, sin productos
T_IN = 330.0
# 30 atm y no 10: con la cinetica rapida que hace falta para que el caso
# acoplado tenga una solucion interesante, la adiabatica sube a ~379 K, y a
# 10 atm eso ya estaria hirviendo. El reactor es liquido por construccion
# (la cinetica usa actividades de fase liquida), asi que la presion es
# parte del caso, no un detalle.
P_OP = 30 * 101325.0
# A rapida: con A=1e4 el avance sale ~1e-4 mol/s sobre un alimento de 100,
# o sea que ninguna de estas comprobaciones distinguiria nada.
A_RAPIDA = 1.0e8

una_r = EvaluadorCSTR(NU_MTBE, GestorReaccion(prov4, NU_MTBE, A_RAPIDA, EA1), flash4)
dos_r = EvaluadorCSTR([NU_MTBE, NU_MTBE],
                      GestorReaccion(prov4, [NU_MTBE, NU_MTBE],
                                     [A_RAPIDA / 2, A_RAPIDA / 2], [EA1, EA1]),
                      flash4)

# --- estequiometria
XI = 20.0
F1, x1 = una_r.salida_desde_entrada(F_IN, X_IN, XI)
F2, x2 = dos_r.salida_desde_entrada(F_IN, X_IN, [XI / 2, XI / 2])
check("6.1 La salida de las dos mitades es la de la reacción entera",
      abs(F1 - F2) < 1e-12 and np.allclose(x1, x2, rtol=0, atol=1e-14),
      f"F = {F1:.6f} vs {F2:.6f} mol/s")

# --- ida y vuelta
Fv, xv = dos_r.entrada_desde_salida(F2, x2, [XI / 2, XI / 2])
check("6.2 Y la vuelta recupera el alimento",
      abs(Fv - F_IN) < 1e-9 and np.allclose(xv, X_IN, atol=1e-12),
      f"F_in recuperado = {Fv:.9f}")

# --- avances desde fracciones: R conocidas -> R avances, exacto
# Con dos reacciones identicas no se pueden distinguir (sistema singular),
# que es justo lo que el metodo debe decir. Se usa el sistema REAL.
mtbe_r = EvaluadorCSTR([NU_MTBE, NU_DIM],
                       GestorReaccion(prov4, [NU_MTBE, NU_DIM], [A1, A2], [EA1, EA2]),
                       flash4)
XI_REF = np.array([18.0, 4.0])
F_ref, x_ref = mtbe_r.salida_desde_entrada(F_IN, X_IN, XI_REF)
# El MTBE solo lo hace R1 y el diisobuteno solo R2: son los componentes
# que distinguen una reaccion de la otra.
recuperados = mtbe_r.avances_desde_fracciones(F_IN, X_IN, {2: x_ref[2], 3: x_ref[3]})
check("6.3 Dos fracciones de salida recuperan los dos avances, exacto",
      np.allclose(recuperados, XI_REF, rtol=0, atol=1e-9),
      f"pedidos {XI_REF}, recuperados {np.round(recuperados, 9)}")

try:
    mtbe_r.avances_desde_fracciones(F_IN, X_IN, {2: x_ref[2]})
    check("6.4 Una sola fracción para dos reacciones -> error", False, "no reventó")
except ValueError as e:
    check("6.4 Una sola fracción para dos reacciones -> error", True, str(e)[:85])

try:
    dos_r.avances_desde_fracciones(F_IN, X_IN, {2: x2[2], 0: x2[0]})
    check("6.5 Dos reacciones idénticas no se pueden distinguir -> error", False,
          "no reventó")
except ValueError as e:
    check("6.5 Dos reacciones idénticas no se pueden distinguir -> error",
          "singular" in str(e), str(e)[:85])

try:
    mtbe_r.avance_desde_fraccion(F_IN, X_IN[2], x_ref[2], 2)
    check("6.6 'avance_desde_fraccion' en singular avisa con varias", False, "no reventó")
except ValueError as e:
    check("6.6 'avance_desde_fraccion' en singular avisa con varias",
          "avances_desde_fracciones" in str(e), str(e)[:85])

# --- cinetica
V = 1.5
xi_una = una_r.avance_desde_cinetica(V, 340.0, x1)
xi_dos = dos_r.avance_desde_cinetica(V, 340.0, x1)
check("6.7 La cinética de las dos mitades suma la de la entera",
      abs(float(np.sum(xi_dos)) - xi_una) <= 1e-12 * abs(xi_una),
      f"{float(np.sum(xi_dos)):.10e} vs {xi_una:.10e}")

# El volumen con varias reacciones es una COMPROBACION, no una inversion.
V_una = una_r.volumen_desde_avance(xi_una, 340.0, x1)
V_dos = dos_r.volumen_desde_avance(xi_dos, 340.0, x1, indice=0)
check("6.8 Y el volumen sale el mismo", abs(V_una - V_dos) <= 1e-9 * V_una,
      f"{V_una:.9f} vs {V_dos:.9f} m³")
try:
    dos_r.volumen_desde_avance(xi_dos, 340.0, x1)
    check("6.9 Sin decir qué reacción fija V -> error", False, "no reventó")
except ValueError as e:
    check("6.9 Sin decir qué reacción fija V -> error", "indice" in str(e), str(e)[:85])
try:
    # Avances incompatibles: la cinetica fija su relacion, no se elige.
    dos_r.volumen_desde_avance([xi_dos[0], 5 * xi_dos[1]], 340.0, x1, indice=0)
    check("6.10 Un juego de avances inalcanzable -> error", False, "no reventó")
except ValueError as e:
    check("6.10 Un juego de avances inalcanzable -> error",
          "no es alcanzable" in str(e), str(e)[:90])

# --- energia
Q_una = una_r.calor_necesario(F_IN, X_IN, T_IN, XI, 350.0, P=P_OP)
Q_dos = dos_r.calor_necesario(F_IN, X_IN, T_IN, [XI / 2, XI / 2], 350.0, P=P_OP)
check("6.11 El calor necesario es el mismo",
      abs(Q_una["Q"] - Q_dos["Q"]) <= 1e-9 * abs(Q_una["Q"]),
      f"{Q_una['Q']/1e3:.6f} vs {Q_dos['Q']/1e3:.6f} kW")

T_una = una_r.temperatura_desde_calor(F_IN, X_IN, T_IN, XI, Q=0.0, exigir_liquido=False)
T_dos = dos_r.temperatura_desde_calor(F_IN, X_IN, T_IN, [XI / 2, XI / 2], Q=0.0,
                                      exigir_liquido=False)
check("6.12 Y la temperatura adiabática también",
      abs(T_una["T_salida"] - T_dos["T_salida"]) < 1e-9,
      f"{T_una['T_salida']:.9f} vs {T_dos['T_salida']:.9f} K")

# --- el caso acoplado, que es el que de verdad podria divergir
#
# ADIABATICO (Q=0), que es donde el lazo T -> r -> xi -> T existe de
# verdad. Y con exigir_liquido=True a proposito: si el resultado saliera
# de la zona liquida, la cinetica de actividades no lo describiria y la
# comprobacion no valdria nada -- que las dos vias coincidan en un numero
# sin sentido fisico no demuestra lo que se quiere demostrar.
ac_una = una_r.resolver_con_cinetica(F_IN, X_IN, T_IN, V=0.5, Q=0.0, P=P_OP,
                                     exigir_liquido=True)
ac_dos = dos_r.resolver_con_cinetica(F_IN, X_IN, T_IN, V=0.5, Q=0.0, P=P_OP,
                                     exigir_liquido=True)
check("6.13 El caso ACOPLADO da el mismo avance total",
      abs(float(np.sum(ac_dos["xi"])) - ac_una["xi"]) < 1e-6,
      f"{float(np.sum(ac_dos['xi'])):.8f} vs {ac_una['xi']:.8f} mol/s")
check("6.14 Y la misma temperatura",
      abs(ac_dos["T_salida"] - ac_una["T_salida"]) < 1e-6,
      f"{ac_dos['T_salida']:.6f} vs {ac_una['T_salida']:.6f} K")
check("6.14b Y el punto es físicamente útil, no un cero trivial",
      ac_una["xi"] > 1.0 and ac_una["T_salida"] > T_IN + 10,
      f"ξ = {ac_una['xi']:.4f} mol/s, T sube de {T_IN:.0f} a "
      f"{ac_una['T_salida']:.2f} K (adiabática, exotérmica)")

# --- equilibrio simultaneo
eq_una = una_r.avance_de_equilibrio(F_IN, X_IN, 340.0)
eq_dos = dos_r.avance_de_equilibrio(F_IN, X_IN, 340.0)
check("6.15 El equilibrio simultáneo de dos mitades da el mismo avance total",
      abs(float(np.sum(eq_dos["xi"])) - eq_una["xi"]) < 1e-6,
      f"{float(np.sum(eq_dos['xi'])):.8f} vs {eq_una['xi']:.8f} mol/s")
check("6.16 Y cumple las dos condiciones de equilibrio",
      eq_dos["residual"] < 1e-8, f"residuo relativo {eq_dos['residual']:.2e}")

# --- conversion
X_una, i_una = una_r.conversion(F_IN, X_IN, XI)
X_dos, i_dos = dos_r.conversion(F_IN, X_IN, [XI / 2, XI / 2])
check("6.17 La conversión del limitante es la misma",
      abs(X_una - X_dos) < 1e-12 and i_una == i_dos,
      f"X = {X_una:.9f}, limitante {i_una}")


# ======================================================================
print("\n" + "=" * 74)
print("7. EL PFR CON VARIAS REACCIONES")
print("=" * 74)
# ======================================================================

pfr_una = EvaluadorPFR(NU_MTBE, GestorReaccion(prov4, NU_MTBE, A_RAPIDA, EA1), flash4)
pfr_dos = EvaluadorPFR([NU_MTBE, NU_MTBE],
                       GestorReaccion(prov4, [NU_MTBE, NU_MTBE],
                                      [A_RAPIDA / 2, A_RAPIDA / 2], [EA1, EA1]),
                       flash4)

r_una = pfr_una.avance_desde_volumen(F_IN, X_IN, 340.0, 0.5)
r_dos = pfr_dos.avance_desde_volumen(F_IN, X_IN, 340.0, 0.5)
check("7.1 El PFR partido en dos mitades da el mismo avance total",
      abs(float(np.sum(r_dos["xi"])) - r_una["xi"]) <= 1e-7 * max(abs(r_una["xi"]), 1.0),
      f"{float(np.sum(r_dos['xi'])):.8f} vs {r_una['xi']:.8f} mol/s")
check("7.2 Y las dos mitades avanzan por igual",
      abs(r_dos["xi"][0] - r_dos["xi"][1]) < 1e-9,
      f"{r_dos['xi'][0]:.8f} y {r_dos['xi'][1]:.8f}")

V_ida = pfr_dos.volumen_desde_avance(r_dos["xi"], 340.0, F_in=F_IN, x_in=X_IN, indice=0)
check("7.3 Ida y vuelta V -> ξ -> V", abs(V_ida - 0.5) < 1e-4, f"{V_ida:.8f} m³")

check("7.4 Volumen cero da avance cero",
      np.allclose(np.atleast_1d(pfr_dos.avance_desde_volumen(F_IN, X_IN, 340.0, 0.0)["xi"]), 0.0))

# El sistema real: el PFR con las DOS reacciones de verdad, y el resultado
# mas interesante de toda la suite.
#
# Las dos reacciones compiten por el isobuteno. La deseada es mas rapida;
# la secundaria esta MUCHO mas favorecida termodinamicamente (K = 488
# frente a 4.14 a 340 K). Asi que lo que manda depende del tiempo de
# residencia: a tubo corto gana la rapida (CONTROL CINETICO) y a tubo
# largo gana la favorecida (CONTROL TERMODINAMICO). Ese cruce es un
# fenomeno de libro, y con una sola reaccion NO SE PUEDE ni plantear.
pfr_mtbe = EvaluadorPFR([NU_MTBE, NU_DIM],
                        GestorReaccion(prov4, [NU_MTBE, NU_DIM],
                                       [A_RAPIDA, 2 * A_RAPIDA], [EA1, EA2]),
                        flash4)
mtbe_eq = EvaluadorCSTR([NU_MTBE, NU_DIM],
                        GestorReaccion(prov4, [NU_MTBE, NU_DIM],
                                       [A_RAPIDA, 2 * A_RAPIDA], [EA1, EA2]),
                        flash4)
K_dos = mtbe_eq.gestor_reaccion.K_eq_de_cada_una(340.0)
print(f"     K_eq a 340 K:  R1 (MTBE) = {K_dos[0]:.2f}   "
      f"R2 (dímero) = {K_dos[1]:.2f}  ← la secundaria está mucho más favorecida")

volumenes = (0.2, 1.0, 3.0, 10.0, 100.0, 1e4)
sel, razon_actividades, instantanea = {}, {}, {}
for V_tubo in volumenes:
    res = pfr_mtbe.avance_desde_volumen(F_IN, X_IN, 340.0, V_tubo)
    xi1, xi2 = float(res["xi"][0]), float(res["xi"][1])
    sel[V_tubo] = xi1 / (xi1 + 2 * xi2) if (xi1 + 2 * xi2) > 0 else float("nan")
    _, x_V = pfr_mtbe.salida_desde_entrada(F_IN, X_IN, res["xi"])
    a_V = x_V * prov4.coeficientes_actividad(340.0, x_V)
    razon_actividades[V_tubo] = float(a_V[1] / a_V[0])        # a_metanol / a_isobuteno
    v_V = pfr_mtbe.gestor_reaccion.velocidades(340.0, x_V)
    instantanea[V_tubo] = float(v_V[0] / (v_V[0] + 2 * v_V[1]))
    print(f"     V={V_tubo:>8.3g} m³   ξ₁={xi1:8.4f}   ξ₂={xi2:8.4f}   "
          f"S={sel[V_tubo]:.4f}   S_inst={instantanea[V_tubo]:.4f}   "
          f"a_MeOH/a_iso={razon_actividades[V_tubo]:.4f}")

check("7.5 Las dos reacciones avanzan a la vez en el mismo tubo",
      all(v > 0 for v in sel.values()))

# La selectividad NO cae de forma monotona, y eso no es un defecto: tiene
# un MAXIMO INTERIOR, que es justo el resultado por el que vale la pena
# tener varias reacciones. Hay un volumen optimo.
#
# Esta comprobacion se escribio primero como "la selectividad decrece al
# subir el volumen" y fallo. El mecanismo real, que se verifica mas abajo:
#
#   r1 ∝ a_iso · a_MeOH      (primer orden en isobuteno)
#   r2 ∝ a_iso²              (SEGUNDO orden en isobuteno)
#
# La secundaria consume isobuteno extra, asi que a_iso cae mas rapido que
# a_MeOH. Y como r2 depende del cuadrado, agotar isobuteno la castiga MAS
# que a la principal: la selectividad MEJORA al principio. Luego la
# principal se acerca a su propio equilibrio (K1 = 4.14, modesto) y se
# frena, mientras la secundaria (K2 = 488) sigue corriendo, y entonces la
# selectividad se desploma.
mejor = max(sel, key=lambda v: sel[v])
check("7.6 La selectividad tiene un MÁXIMO interior: hay un volumen óptimo",
      mejor not in (volumenes[0], volumenes[-1]),
      f"máximo en V = {mejor:g} m³ con S = {sel[mejor]:.4f}")
check("7.7 Y se desploma con un tubo muy largo: control cinético → termodinámico",
      sel[1e4] < 0.5 * sel[mejor],
      f"de {sel[mejor]:.4f} en el óptimo a {sel[1e4]:.4f} con V = 10⁴ m³")

# El mecanismo, comprobado y no supuesto: la razon de actividades crece de
# forma monotona porque la secundaria retira isobuteno extra.
razones = [razon_actividades[v] for v in volumenes]
check("7.8 El mecanismo: a_MeOH/a_iso crece monótonamente a lo largo del tubo",
      all(b > a for a, b in zip(razones, razones[1:])),
      " < ".join(f"{r:.4f}" for r in razones))
# Y arranca por debajo de 1 pese a alimentar 50/50: los coeficientes de
# actividad no son 1. Si se hubiera razonado sobre fracciones molares en
# vez de actividades, la conclusion habria sido otra.
check("7.9 Y arranca por debajo de 1 aunque el alimento sea 50/50: γ ≠ 1",
      razones[0] < 1.0,
      f"a_MeOH/a_iso = {razones[0]:.4f} con x iguales — UNIFAC, no idealidad")

# Y la comprobacion cruzada que ya existia con una reaccion, ahora con dos:
# un tubo largo tiene que llegar al mismo sitio que el reactor de
# equilibrio, por un camino completamente distinto -- integrar dos EDO
# acopladas frente a resolver un sistema 2x2 de van't Hoff. No comparten
# ni una linea de codigo mas alla de la estequiometria.
largo = pfr_mtbe.avance_desde_volumen(F_IN, X_IN, 340.0, 1e6)
eq_mtbe = mtbe_eq.avance_de_equilibrio(F_IN, X_IN, 340.0)
xi_pfr = np.atleast_1d(largo["xi"])
xi_eq = np.atleast_1d(eq_mtbe["xi"])
print(f"     PFR muy largo:  ξ = {np.round(xi_pfr, 6)}")
print(f"     equilibrio:     ξ = {np.round(xi_eq, 6)}")
check("7.10 Un tubo muy largo llega al equilibrio de las DOS reacciones",
      np.allclose(xi_pfr, xi_eq, rtol=0, atol=1e-6),
      f"máxima diferencia {np.max(np.abs(xi_pfr - xi_eq)):.2e} mol/s "
      "-- dos matemáticas distintas, el mismo punto")


# ======================================================================
print("\n" + "=" * 74)
print("8. LO QUE NO SE GENERALIZA, Y LO DICE")
print("=" * 74)
# ======================================================================
# Barbosa-Doherty es de UNA reaccion por construccion. Sin esta guarda,
# pasarle una matriz no reventaba: construia un objeto con nan e inf
# dentro (nu/nu_k divide por una fila con ceros) y solo fallaba mucho
# despues con un "truth value of an array is ambiguous", que no dice nada
# del problema real.

from core.transformaciones import EspacioReactivo

try:
    EspacioReactivo([NU_MTBE, NU_DIM], 0)
    check("8.1 Barbosa-Doherty rechaza una matriz de reacciones", False, "no reventó")
except ValueError as e:
    check("8.1 Barbosa-Doherty rechaza una matriz de reacciones",
          "UNA reaccion" in str(e), str(e)[:90])

try:
    espacio = EspacioReactivo(NU_MTBE, 0)
    check("8.2 Y con una sola reacción sigue funcionando igual",
          abs(espacio.nu_k - (-1.0)) < 1e-15 and np.allclose(espacio.nu, NU_MTBE))
except Exception as e:
    check("8.2 Y con una sola reacción sigue funcionando igual", False, str(e)[:80])


# ======================================================================
print("\n" + "=" * 74)
print("9. EL DIAGRAMA COMPLETO CON DOS REACCIONES")
print("=" * 74)
# ======================================================================
# Hasta aqui todo era el nucleo. Esto comprueba que las dos reacciones
# atraviesan el DIAGRAMA: que el pool las nombra, que el contador de
# grados de libertad las cuenta, y que el solver resuelve en las
# direcciones que de verdad se usan.
#
# El nombre en el pool importa mas de lo que parece. Con una reaccion
# sigue siendo `r1.xi`, igual que siempre; con varias pasa a `r1.xi0`,
# `r1.xi1`, con la misma convencion que las fracciones molares. Conservar
# `xi` en el caso de una no es cosmetica: ese nombre esta escrito en las
# plantillas, los ejemplos, las suites y dentro de cada enlace compartible
# que alguien haya generado.

from core.diagrama_corrientes import DiagramaCorrientes

masas = [float(c.MW) for c in prov4.componentes]
G_DOS = GestorReaccion(prov4, [NU_MTBE, NU_DIM], [A_RAPIDA, 2 * A_RAPIDA], [EA1, EA2])
BASE_D = {"alim.F": 100.0, "alim.T": 330.0, "alim.P": 30 * 101325.0,
          "alim.x0": 0.5, "alim.x1": 0.5, "alim.x2": 0.0, "alim.x3": 0.0,
          "r1.T": 340.0}


def diagrama_reactor(**kw):
    d = DiagramaCorrientes(MTBE4, masas_molares=masas, proveedor=prov4)
    d.agregar_corriente("alim")
    d.agregar_corriente("prod")
    d.agregar_reactor_cstr("r1", "alim", "prod", [NU_MTBE, NU_DIM],
                           gestor_reaccion=G_DOS, **kw)
    return d


d_cin = diagrama_reactor(con_cinetica=True, modo_energia="isotermo")
vars_r1 = sorted(v for v in d_cin.todas_las_variables() if v.startswith("r1."))
check("9.1 El pool declara un avance por reacción",
      "r1.xi0" in vars_r1 and "r1.xi1" in vars_r1 and "r1.xi" not in vars_r1,
      ", ".join(vars_r1))

# Y con UNA reaccion el nombre no cambia: `xi`, como siempre.
d_una = DiagramaCorrientes(MTBE4, masas_molares=masas, proveedor=prov4)
d_una.agregar_corriente("alim")
d_una.agregar_corriente("prod")
d_una.agregar_reactor_cstr("r1", "alim", "prod", NU_MTBE,
                           gestor_reaccion=GestorReaccion(prov4, NU_MTBE, A_RAPIDA, EA1),
                           con_cinetica=True, modo_energia="isotermo")
check("9.2 Con una sola reacción el pool sigue diciendo 'r1.xi'",
      "r1.xi" in d_una.todas_las_variables()
      and "r1.xi0" not in d_una.todas_las_variables())

# --- la direccion de SIMULACION: dados los avances, todo lo demas
res = d_cin.resolver(**BASE_D, **{"r1.xi0": 18.0, "r1.xi1": 4.0})
pool = res["pool"]
check("9.3 Dados los dos avances, sale la composición de producto",
      all(pool.get(f"prod.x{i}") is not None for i in range(4)),
      " ".join(f"{pool[f'prod.x{i}']:.5f}" for i in range(4)))
# Balance por componente, comprobado a mano contra la estequiometria.
n_esperado = np.array([100 * 0.5 - 18 - 8, 100 * 0.5 - 18, 18.0, 4.0])
F_esp = float(np.sum(n_esperado))
check("9.4 Y el balance por componente cuadra con NUᵗ·ξ",
      abs(pool["prod.F"] - F_esp) < 1e-9
      and np.allclose([pool[f"prod.x{i}"] for i in range(4)], n_esperado / F_esp, atol=1e-12),
      f"F_prod = {pool['prod.F']:.6f} mol/s (esperado {F_esp:.6f})")
check("9.5 El calor suma las dos reacciones, no solo la principal",
      pool.get("r1.Q") is not None and pool["r1.Q"] < 0,
      f"Q = {pool['r1.Q']/1e6:.4f} MW (hay que refrigerar)")
Q_solo_R1 = 18.0 * float(G_DOS.dH_rxn_de_cada_una[0])
check("9.6 Y es MAYOR en magnitud que el de la principal sola",
      abs(pool["r1.Q_reaccion"]) > abs(Q_solo_R1),
      f"{pool['r1.Q_reaccion']/1e6:.4f} MW frente a {Q_solo_R1/1e6:.4f} MW si se ignorara R2")

# --- la cinetica se NIEGA, y eso es lo correcto: un solo tanque no puede
# entregar un juego cualquiera de avances.
errores = res.get("errores_bloque") or {}
check("9.7 La cinética rechaza un par de avances inalcanzable en un solo tanque",
      any("no es alcanzable" in str(v) for v in errores.values()),
      next((str(v)[:95] for v in errores.values() if "no es alcanzable" in str(v)), ""))

# --- la direccion de DISEÑO: dadas las fracciones de producto, los avances
res_b = d_cin.resolver(**BASE_D, **{"prod.x2": pool["prod.x2"], "prod.x3": pool["prod.x3"]})
pb = res_b["pool"]
check("9.8 Al revés: dos fracciones de producto determinan los dos avances",
      pb.get("r1.xi0") is not None and pb.get("r1.xi1") is not None
      and abs(pb["r1.xi0"] - 18.0) < 1e-9 and abs(pb["r1.xi1"] - 4.0) < 1e-9,
      f"ξ = [{pb['r1.xi0']:.9f}, {pb['r1.xi1']:.9f}] — es la pregunta de diseño real")

# --- dar la conversion NO basta con varias reacciones, y se explica
res_c = d_cin.resolver(**BASE_D, **{"r1.X": 0.52})
errores_c = res_c.get("errores_bloque") or {}
check("9.9 Dar solo la conversión no reparte el consumo, y lo dice",
      any("no determina los avances" in str(v) for v in errores_c.values()),
      next((str(v)[:95] for v in errores_c.values() if "no determina" in str(v)), ""))

# --- modo equilibrio de punta a punta
d_eq = diagrama_reactor(modo_reaccion="equilibrio", modo_energia="isotermo")
res_eq = d_eq.resolver(**BASE_D)
pe = res_eq["pool"]
check("9.10 El modo equilibrio resuelve el diagrama completo",
      res_eq["completo"] is True,
      f"ξ = [{pe['r1.xi0']:.6f}, {pe['r1.xi1']:.6f}]")
check("9.11 Y declara una K_eq por reacción",
      pe.get("r1.K_eq0") is not None and pe.get("r1.K_eq1") is not None,
      f"K = [{pe['r1.K_eq0']:.4f}, {pe['r1.K_eq1']:.4f}]")
# El mismo numero que el nucleo, por el camino del diagrama.
eq_nucleo = mtbe_eq.avance_de_equilibrio(100.0, np.array([0.5, 0.5, 0.0, 0.0]), 340.0)
check("9.12 Y es el MISMO avance que calcula el núcleo directamente",
      np.allclose([pe["r1.xi0"], pe["r1.xi1"]],
                  np.atleast_1d(eq_nucleo["xi"]), rtol=0, atol=1e-9),
      "el diagrama no cambia el número")

# --- grados de libertad: cada reaccion suma su incognita
gl_dos = d_cin.grados_de_libertad(BASE_D)
gl_una = d_una.grados_de_libertad(BASE_D)
check("9.13 El contador ve una incógnita más por reacción",
      gl_dos["incognitas"] == gl_una["incognitas"] + 1,
      f"{gl_una['incognitas']} con una reacción, {gl_dos['incognitas']} con dos")


print("\n" + "=" * 74)
if fallos:
    print(f"FALLARON {len(fallos)}:")
    for f in fallos:
        print("   - " + f)
    sys.exit(1)
print("TODO OK")
