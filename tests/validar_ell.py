"""
Validacion del EQUILIBRIO LIQUIDO-LIQUIDO.

Lo que hace este equilibrio distinto de todos los demas del simulador: la
solucion TRIVIAL x^I = x^II cumple todas las ecuaciones, siempre, para
cualquier alimento y cualquier temperatura. Las dos fases se describen con
el mismo modelo de actividad. Asi que "las ecuaciones cuadran" no
demuestra nada aqui, y la validacion tiene que mirar otras cosas.

Las dos que mas valen, y ninguna necesita literatura externa:

  1. **La linea de reparto es INVARIANTE dentro de la laguna.** En un
     binario, todas las composiciones globales que caen dentro de la
     region de inmiscibilidad se separan en LAS MISMAS DOS FASES; lo
     unico que cambia es cuanto hay de cada una. Es la propiedad que
     define una linea de reparto, y un flash que convergiera a soluciones
     triviales o a minimos espureos NO la cumpliria.

  2. **La energia de Gibbs de las dos fases es MENOR que la de una sola.**
     El flash resuelve igualdad de actividades, que es la condicion de
     punto estacionario. Que ese punto sea un MINIMO es una propiedad
     distinta, calculada por otro camino. Comparar las dos cosas es lo
     unico que separa "cuadra" de "es fisico".

Y la tercera, la regla de la palanca, que ata el tamano de las fases a la
geometria de la linea de reparto sin pasar por el modelo de actividad.

Ejecutar desde la raiz del proyecto:
    python tests/validar_ell.py
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

import thermo.unifac as _uf

from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.ell import CalculadoraELL, traducir_grupos

fallos = []


def check(nombre, ok, detalle=""):
    print(f"[{'OK ' if ok else 'FALLA'}] {nombre}{(' -- ' + detalle) if detalle else ''}")
    if not ok:
        fallos.append(nombre)


T25 = 298.15


# ======================================================================
print("\n" + "=" * 74)
print("1. LA TRAMPA DE LOS DOS JUEGOS DE PARAMETROS")
print("=" * 74)
# ======================================================================
# UNIFAC tiene dos juegos de parametros de interaccion, uno ajustado a
# datos de ELV y otro a datos de ELL, y NO son intercambiables. Lo que
# convierte eso en una trampa es que los identificadores de subgrupo
# tampoco coinciden: pasar la descomposicion de una molecula de un juego
# al otro tal cual calcularia las actividades de OTRA molecula, y
# devolveria numeros plausibles y falsos.

check("1.1 El id 16 NO es el mismo grupo en los dos juegos",
      _uf.UFSG[16].group != _uf.LLEUFSG[16].group,
      f"en ELV es '{_uf.UFSG[16].group}', en ELL es '{_uf.LLEUFSG[16].group}'")
check("1.2 El agua es el 16 en ELV y el 17 en ELL",
      _uf.UFSG[16].group == "H2O" and _uf.LLEUFSG[17].group == "H2O")

# Por eso la traduccion va por NOMBRE.
agua = ProveedorTermodinamico(["water"]).grupos_unifac[0]
check("1.3 La traducción convierte {16: 1} en {17: 1}",
      traducir_grupos(agua) == {17: 1}, f"{agua} → {traducir_grupos(agua)}")

# Y un grupo sin equivalente se rechaza con nombre y apellido, en vez de
# calcular con el grupo equivocado.
try:
    traducir_grupos(ProveedorTermodinamico(["furfural"]).grupos_unifac[0], "furfural")
    check("1.4 Un grupo sin equivalente en el juego de ELL se rechaza", False, "no reventó")
except ValueError as e:
    check("1.4 Un grupo sin equivalente en el juego de ELL se rechaza",
          "FURFURAL" in str(e) and "furfural" in str(e), str(e)[:105])

# Los dos juegos dan gamma distintos: si dieran lo mismo, todo esto seria
# ceremonia.
from thermo.unifac import UNIFAC
buoh = ProveedorTermodinamico(["1-butanol"]).grupos_unifac[0]
x = [0.1, 0.9]
g_elv = UNIFAC.from_subgroups(T=T25, xs=x, chemgroups=[agua, buoh]).gammas()
g_ell = UNIFAC.from_subgroups(
    T=T25, xs=x, chemgroups=[traducir_grupos(agua), traducir_grupos(buoh)],
    subgroups=_uf.LLEUFSG, interaction_data=_uf.LLEUFIP, version=0).gammas()
check("1.5 Y los dos juegos dan γ apreciablemente distintos",
      abs(g_elv[0] - g_ell[0]) / g_elv[0] > 0.05,
      f"γ_agua = {g_elv[0]:.4f} con los de ELV, {g_ell[0]:.4f} con los de ELL "
      f"({100*abs(g_elv[0]-g_ell[0])/g_elv[0]:.1f} % de diferencia)")


# ======================================================================
print("\n" + "=" * 74)
print("2. UNA MEZCLA MISCIBLE DA UNA SOLA FASE")
print("=" * 74)
# ======================================================================
# Lo primero que tiene que hacer bien: NO inventar una separacion donde no
# la hay. Un flash L-L mal arrancado devuelve dos fases casi identicas y
# las presenta como equilibrio.

ell_bt = CalculadoraELL(ProveedorTermodinamico(["benzene", "toluene"]))
miscibles = [ell_bt.flash_LL(T25, [f, 1 - f]) for f in (0.1, 0.3, 0.5, 0.7, 0.9)]
check("2.1 Benceno/tolueno no se separa a ninguna composición",
      all(r is None for r in miscibles), "5 composiciones probadas")
inest, _, tpd = ell_bt.es_inestable(T25, [0.5, 0.5])
check("2.2 Y el análisis de estabilidad lo dice: ningún plano tangente negativo",
      not inest and tpd > -1e-8, f"tpd mínima = {tpd:.3e}")


# ======================================================================
print("\n" + "=" * 74)
print("3. LA LINEA DE REPARTO ES INVARIANTE DENTRO DE LA LAGUNA")
print("=" * 74)
# ======================================================================
# La comprobacion mas fuerte de toda la suite. En un binario, TODAS las
# composiciones globales dentro de la region de inmiscibilidad se separan
# en las MISMAS dos fases; lo unico que cambia es cuanto hay de cada una.
#
# Un flash que convergiera a la solucion trivial, o a un minimo espureo
# cerca de un vertice del simplex, daria una "linea de reparto" distinta
# para cada alimento. Esta comprobacion lo cazaria de inmediato.

ell_wb = CalculadoraELL(ProveedorTermodinamico(["water", "1-butanol"]))
dentro = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
reparto = {}
for z0 in dentro:
    r = ell_wb.flash_LL(T25, [z0, 1 - z0])
    reparto[z0] = r

check("3.1 Todas las composiciones de la laguna se separan",
      all(r is not None for r in reparto.values()),
      f"{sum(1 for r in reparto.values() if r)} de {len(dentro)}")

if all(r is not None for r in reparto.values()):
    x_I = np.array([reparto[z]["x_I"] for z in dentro])
    x_II = np.array([reparto[z]["x_II"] for z in dentro])
    dispersion = max(float(np.max(np.abs(x_I - x_I[0]))),
                     float(np.max(np.abs(x_II - x_II[0]))))
    print(f"     fase I : x_agua = {x_I[0][0]:.6f}   (BuOH {x_I[0][1]:.6f})")
    print(f"     fase II: x_agua = {x_II[0][0]:.6f}   (BuOH {x_II[0][1]:.6f})")
    check("3.2 Y en las MISMAS dos fases, con independencia del alimento",
          dispersion < 1e-9,
          f"dispersión máxima entre los 9 resultados: {dispersion:.2e}")

    # La regla de la palanca: el tamano de las fases sale de la geometria
    # de la linea de reparto, sin pasar por el modelo de actividad. Es una
    # comprobacion de otra naturaleza que la igualdad de actividades.
    peores = []
    for z0 in dentro:
        r = reparto[z0]
        esperado = (r["x_I"][0] - z0) / (r["x_I"][0] - r["x_II"][0])
        peores.append(abs(r["fraccion_II"] - esperado))
    check("3.3 La regla de la palanca se cumple exacta",
          max(peores) < 1e-9, f"error máximo {max(peores):.2e}")

    # Igualdad de actividades: es LO QUE SE RESUELVE, asi que es necesaria
    # pero no suficiente. Se comprueba igual, porque un residuo grande
    # significaria que ni eso.
    check("3.4 Las actividades de cada componente son iguales en las dos fases",
          all(r["residual_actividades"] < 1e-9 for r in reparto.values()),
          f"residuo relativo máximo "
          f"{max(r['residual_actividades'] for r in reparto.values()):.2e}")

    # Fuera de la laguna, una sola fase. El borde no se impone: sale.
    fuera = [0.40, 0.50, 0.99]
    check("3.5 Y fuera de la laguna vuelve a haber una sola fase",
          all(ell_wb.flash_LL(T25, [z0, 1 - z0]) is None for z0 in fuera),
          f"z_agua = {fuera} (la laguna va de {x_II[0][0]:.4f} a {x_I[0][0]:.4f})")


# ======================================================================
print("\n" + "=" * 74)
print("4. LAS DOS FASES BAJAN LA ENERGIA DE GIBBS")
print("=" * 74)
# ======================================================================
# La comprobacion INDEPENDIENTE. El flash resuelve igualdad de
# actividades, que es la condicion de punto estacionario; que ese punto
# sea un MINIMO es otra propiedad, y se calcula por otro camino:
#
#     g_dos_fases / RT = (1-beta) g(x^I) + beta g(x^II)
#
# tiene que ser MENOR que g(z) de la fase unica. Si no lo fuera, el flash
# habria encontrado una solucion matematica sin sentido fisico.

print(f"     {'z_agua':>8} {'g(z)/RT':>12} {'g_2fases/RT':>14} {'Δg':>12}")
mejoras = []
for z0 in dentro:
    r = reparto[z0]
    g_una = ell_wb.gibbs_de_mezcla(T25, [z0, 1 - z0])
    g_dos = ((1 - r["fraccion_II"]) * ell_wb.gibbs_de_mezcla(T25, r["x_I"])
             + r["fraccion_II"] * ell_wb.gibbs_de_mezcla(T25, r["x_II"]))
    mejoras.append(g_una - g_dos)
    print(f"     {z0:>8.2f} {g_una:>12.6f} {g_dos:>14.6f} {g_dos-g_una:>12.3e}")

check("4.1 Separarse SIEMPRE baja la energía de Gibbs",
      all(m > 0 for m in mejoras),
      f"la menor mejora es {min(mejoras):.3e} (en el borde de la laguna, donde debe tender a 0)")
check("4.2 Y la mejora es máxima en el centro de la laguna, no en los bordes",
      mejoras[0] < max(mejoras) and mejoras[-1] < max(mejoras),
      f"bordes {mejoras[0]:.3e} y {mejoras[-1]:.3e}, máximo {max(mejoras):.3e}")

# Coherencia entre los dos criterios: el plano tangente dice "se separa" y
# el flash lo encuentra. Son dos cuentas distintas sobre la misma fisica.
coherentes = 0
for z0 in dentro + [0.40, 0.50]:
    inest, _, _ = ell_wb.es_inestable(T25, [z0, 1 - z0])
    separa = ell_wb.flash_LL(T25, [z0, 1 - z0]) is not None
    if inest == separa:
        coherentes += 1
check("4.3 El criterio del plano tangente y el flash coinciden siempre",
      coherentes == len(dentro) + 2, f"{coherentes} de {len(dentro) + 2} composiciones")


# ======================================================================
print("\n" + "=" * 74)
print("5. AGUA / BENCENO: DOS LIQUIDOS CASI INMISCIBLES")
print("=" * 74)
# ======================================================================
# Un caso cualitativamente distinto al anterior: ahi las fases eran
# mutuamente solubles al 2 % y al 47 %; aqui la inmiscibilidad es casi
# total, y el flash tiene que sobrevivir a fracciones molares de 1e-4 sin
# perder precision ni caer en la solucion trivial.

ell_wbz = CalculadoraELL(ProveedorTermodinamico(["water", "benzene"]))
r = ell_wbz.flash_LL(T25, [0.5, 0.5])
check("5.1 Agua/benceno se separa", r is not None)
if r:
    print(f"     fase acuosa:   x_benceno = {r['x_I'][1]:.6e}")
    print(f"     fase orgánica: x_agua    = {r['x_II'][0]:.6e}")
    check("5.2 Y la inmiscibilidad es casi total, con fracciones de orden 1e-3",
          r["x_I"][1] < 1e-2 and r["x_II"][0] < 1e-2,
          f"x_benceno en agua {r['x_I'][1]:.3e}, x_agua en benceno {r['x_II'][0]:.3e}")
    check("5.3 Sin perder precisión en las actividades",
          r["residual_actividades"] < 1e-9, f"residuo {r['residual_actividades']:.2e}")
    check("5.4 Y las dos fases son de verdad distintas, no la solución trivial",
          float(np.max(np.abs(r["x_I"] - r["x_II"]))) > 0.9,
          f"diferencia máxima {float(np.max(np.abs(r['x_I'] - r['x_II']))):.4f}")

    # La solubilidad mutua CRECE con la temperatura: es el camino hacia la
    # temperatura critica de la laguna. Es una tendencia, no un numero de
    # literatura, y como tal se comprueba.
    solub = {}
    for T in (298.15, 320.0, 350.0, 380.0):
        rt = ell_wbz.flash_LL(T, [0.5, 0.5])
        solub[T] = (rt["x_I"][1], rt["x_II"][0]) if rt else None
    validas = [T for T in solub if solub[T]]
    print("     " + "   ".join(
        f"T={T:.0f}: {solub[T][0]:.2e}/{solub[T][1]:.2e}" for T in validas))
    check("5.5 La solubilidad mutua crece con la temperatura",
          all(solub[b][0] > solub[a][0] and solub[b][1] > solub[a][1]
              for a, b in zip(validas, validas[1:])),
          "las dos fases se acercan: es el camino hacia la temperatura crítica")


# ======================================================================
print("\n" + "=" * 74)
print("6. EL ORDEN DE LAS FASES ES ESTABLE")
print("=" * 74)
# ======================================================================
# Sin una convencion, el mismo problema devuelve las dos fases en un orden
# u otro segun por donde arranque el flash, y comparar dos resultados se
# vuelve imposible. La convencion: la fase I es la mas rica en el
# componente 0.

ordenes = []
for z0 in (0.60, 0.75, 0.90):
    r = ell_wb.flash_LL(T25, [z0, 1 - z0])
    ordenes.append(r["x_I"][0] > r["x_II"][0])
check("6.1 La fase I es siempre la más rica en el componente 0",
      all(ordenes), f"{sum(ordenes)} de {len(ordenes)}")

# Y el balance de materia global cierra, que es lo minimo exigible.
peor_balance = 0.0
for z0 in dentro:
    r = reparto[z0]
    z_reconstruido = ((1 - r["fraccion_II"]) * r["x_I"]
                      + r["fraccion_II"] * r["x_II"])
    peor_balance = max(peor_balance,
                       float(np.max(np.abs(z_reconstruido - np.array([z0, 1 - z0])))))
check("6.2 El balance de materia global cierra",
      peor_balance < 1e-12, f"error máximo {peor_balance:.2e}")


# ======================================================================
print("\n" + "=" * 74)
print("7. EL DECANTADOR EN UN DIAGRAMA")
print("=" * 74)
# ======================================================================
# El equipo que abre la familia de la extraccion. De UNA etapa a
# proposito: una columna de extraccion de varias etapas no se resuelve con
# un metodo de atajo.

from core.diagrama_corrientes import DiagramaCorrientes

prov_wb = ProveedorTermodinamico(["water", "1-butanol"])
masas = [float(c.MW) for c in prov_wb.componentes]


def diagrama_decantador(**kw):
    d = DiagramaCorrientes(["water", "1-butanol"], masas_molares=masas, proveedor=prov_wb)
    for s in ("alim", "org", "acu"):
        d.agregar_corriente(s)
    d.agregar_decantador("dec1", "alim", fase_ligera="org", fase_pesada="acu", **kw)
    return d


d_dec = diagrama_decantador()
check("7.1 El decantador declara sus variables",
      {"dec1.T", "dec1.fraccion", "dec1.separa"}
      <= set(d_dec.todas_las_variables()),
      ", ".join(sorted(v for v in d_dec.todas_las_variables() if v.startswith("dec1."))))

ALIM = {"alim.F": 100.0, "alim.T": T25, "alim.P": 101325.0}

# --- dentro de la laguna: separa
dentro_dec = d_dec.resolver(**ALIM, **{"alim.x0": 0.75, "alim.x1": 0.25})
pd_ = dentro_dec["pool"]
check("7.2 Dentro de la laguna, el diagrama resuelve y separa",
      dentro_dec["completo"] and pd_["dec1.separa"] == 1.0,
      f"F_org = {pd_['org.F']:.4f}, F_acu = {pd_['acu.F']:.4f} mol/s")
check("7.3 Y las dos fases son las de la línea de reparto",
      abs(pd_["acu.x0"] - 0.981454) < 1e-5 and abs(pd_["org.x0"] - 0.533687) < 1e-5,
      f"acuosa x_agua = {pd_['acu.x0']:.6f}, orgánica x_agua = {pd_['org.x0']:.6f}")

# El balance por componente, comprobado contra el alimento y no contra el
# propio equipo: es la unica forma de que signifique algo.
peor = 0.0
for i in range(2):
    total = pd_["acu.F"] * pd_[f"acu.x{i}"] + pd_["org.F"] * pd_[f"org.x{i}"]
    esperado = 100.0 * (0.75 if i == 0 else 0.25)
    peor = max(peor, abs(total - esperado))
check("7.4 El balance por componente cierra contra la alimentación",
      peor < 1e-9, f"error máximo {peor:.2e} mol/s")

# --- fuera de la laguna: UNA fase, y lo dice
fuera_dec = d_dec.resolver(**ALIM, **{"alim.x0": 0.40, "alim.x1": 0.60})
pf_ = fuera_dec["pool"]
check("7.5 Fuera de la laguna sale una sola fase, y el equipo lo declara",
      fuera_dec["completo"] and pf_["dec1.separa"] == 0.0 and pf_["org.F"] == 0.0,
      f"separa = {pf_['dec1.separa']}, F_org = {pf_['org.F']}")
check("7.6 Y toda la alimentación sale por una salida, sin inventar dos fases iguales",
      abs(pf_["acu.F"] - 100.0) < 1e-12
      and abs(pf_["acu.x0"] - 0.40) < 1e-12,
      "la composición sale intacta, que es lo correcto: no hubo separación")

# --- la temperatura: un sedimentador separa, no calienta
check("7.7 Sin T de operación, opera a la de la entrada",
      abs(pd_["dec1.T"] - T25) < 1e-12 and abs(pd_["org.T"] - T25) < 1e-12,
      f"T = {pd_['dec1.T']:.4f} K")

d_frio = diagrama_decantador(T_operacion=283.15)
r_frio = d_frio.resolver(**ALIM, **{"alim.x0": 0.75, "alim.x1": 0.25})
pfr_ = r_frio["pool"]
check("7.8 Con T de operación distinta, la laguna se ensancha al enfriar",
      pfr_["dec1.separa"] == 1.0 and pfr_["org.x0"] < pd_["org.x0"],
      f"a {T25:.2f} K la orgánica tiene x_agua = {pd_['org.x0']:.6f}; "
      f"a 283.15 K, {pfr_['org.x0']:.6f}")

# --- la caida de presion tambien aplica aqui
d_dp = diagrama_decantador(caida_P=5000.0)
r_dp = d_dp.resolver(**ALIM, **{"alim.x0": 0.75, "alim.x1": 0.25})
check("7.9 Y la caída de presión se resta en las dos salidas",
      abs(r_dp["pool"]["org.P"] - (101325.0 - 5000.0)) < 1e-9
      and abs(r_dp["pool"]["acu.P"] - (101325.0 - 5000.0)) < 1e-9,
      f"{r_dp['pool']['org.P']:.1f} Pa")

# --- y lo que debe rechazarse: un decantador sin proveedor no tiene
# coeficientes de actividad, asi que no hay equilibrio que resolver.
try:
    sin_prov = DiagramaCorrientes(["water", "1-butanol"], masas_molares=masas)
    for s in ("alim", "org", "acu"):
        sin_prov.agregar_corriente(s)
    sin_prov.agregar_decantador("dec1", "alim", fase_ligera="org", fase_pesada="acu")
    check("7.10 Un decantador sin proveedor termodinámico se rechaza", False, "no reventó")
except ValueError as e:
    check("7.10 Un decantador sin proveedor termodinámico se rechaza",
          "actividad" in str(e), str(e)[:100])


print("\n" + "=" * 74)
if fallos:
    print(f"FALLARON {len(fallos)}:")
    for f in fallos:
        print("   - " + f)
    sys.exit(1)
print("TODO OK")
