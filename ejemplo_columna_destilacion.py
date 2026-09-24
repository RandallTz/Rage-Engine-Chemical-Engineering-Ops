"""
ColumnaDestilacion: una misma fachada (.resolver(**valores)), pero el
metodo interno cambia segun lo que le pidas al construirla -- sin que el
llamador arme la lista de bloques a mano ni sepa que hay un Orquestador
adentro.
"""

import numpy as np

from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.elv import CalculadoraELV
from core.mccabe_thiele import EvaluadorMcCabeThiele, SolucionadorMcCabeThiele
from core.ponchon_savarit import EvaluadorPonchonSavarit, SolucionadorPonchonSavarit
from core.fug import AnalizadorFUG
from core.columna_destilacion import ColumnaDestilacion

# ============================================================
# Mismo par binario (benceno/tolueno) resuelto con McCabe-Thiele Y con
# Ponchon-Savarit -- misma fachada ColumnaDestilacion.resolver(...), solo
# cambia el 'metodo' con el que se construyo.
# ============================================================
NOMBRES_BINARIO = ["benzene", "toluene"]
P_SISTEMA = 101325.0

proveedor = ProveedorTermodinamico(NOMBRES_BINARIO)
calc_elv = CalculadoraELV(proveedor)

evaluador_mt = EvaluadorMcCabeThiele(calc_elv, NOMBRES_BINARIO, P_sistema=P_SISTEMA)
solucionador_mt = SolucionadorMcCabeThiele(evaluador_mt)
columna_mt = ColumnaDestilacion("mccabe_thiele", solucionador_mt=solucionador_mt)

resultado_mt = columna_mt.resolver(D=38.8889, B=61.1111, z_F=0.40, x_D=0.95, q=1.0, N=10.0)
print("=== ColumnaDestilacion('mccabe_thiele') ===")
print("  x_B =", resultado_mt["pool"]["x_B"], " <- resuelto por:", resultado_mt["resueltos_por"]["x_B"])
print("  R   =", resultado_mt["pool"]["R"], " <- resuelto por:", resultado_mt["resueltos_por"]["R"])

evaluador_ps = EvaluadorPonchonSavarit(calc_elv, NOMBRES_BINARIO, P_sistema=P_SISTEMA)
solucionador_ps = SolucionadorPonchonSavarit(evaluador_ps)
columna_ps = ColumnaDestilacion("ponchon_savarit", solucionador_ps=solucionador_ps, q=1.0)

resultado_ps = columna_ps.resolver(D=38.8889, B=61.1111, z_F=0.40, x_D=0.95, N=10.0)
print("\n=== ColumnaDestilacion('ponchon_savarit') -- MISMA interfaz, otro metodo ===")
print("  x_B  =", resultado_ps["pool"]["x_B"], " <- resuelto por:", resultado_ps["resueltos_por"]["x_B"])
print("  Qc_D =", resultado_ps["pool"]["Qc_D"], " <- resuelto por:", resultado_ps["resueltos_por"]["Qc_D"])

# ============================================================
# FUG (multicomponente) -- MISMA clase, MISMA interfaz .resolver(**valores),
# ahora con un metodo shortcut multicomponente en vez de un metodo grafico
# binario.
# ============================================================
NOMBRES_FUG = ["propane", "n-butane", "n-pentane", "n-hexane"]
Z_F_FUG = np.array([0.10, 0.30, 0.30, 0.30])
P_SISTEMA_FUG = 101325.0 * 5

proveedor_fug = ProveedorTermodinamico(NOMBRES_FUG)
calc_elv_fug = CalculadoraELV(proveedor_fug)
analizador_fug = AnalizadorFUG(
    calc_elv_fug, proveedor_fug, NOMBRES_FUG, Z_F_FUG, q=1.0,
    P_sistema=P_SISTEMA_FUG, indice_LK=1, indice_HK=2,
)
columna_fug = ColumnaDestilacion("fug", analizador_fug=analizador_fug)

resultado_fug = columna_fug.resolver(recuperacion_LK_D=0.98, recuperacion_HK_B=0.98, R=3.0, F=100.0)
print("\n=== ColumnaDestilacion('fug') -- MISMA clase, metodo multicomponente ===")
print("  N     =", resultado_fug["pool"]["N"])
print("  D, B  =", resultado_fug["pool"]["D"], resultado_fug["pool"]["B"], "mol/s")
print("  Q_c   =", resultado_fug["pool"]["Q_c"], "W  <- resuelto por:", resultado_fug["resueltos_por"]["Q_c"])

print("\nLos tres se llamaron con la MISMA fachada (ColumnaDestilacion.resolver(**valores));")
print("lo que cambio fue el 'metodo' pasado al construir cada instancia.")
