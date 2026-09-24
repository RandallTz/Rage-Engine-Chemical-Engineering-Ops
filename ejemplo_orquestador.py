"""
Cómo se conecta el balance de materia con McCabe-Thiele en el orquestador.

Doy D y B (flujos) en vez de F -- el bloque de balance tiene que despejar
x_B primero (con F*z_F=D*x_D+B*x_B), y SOLO DESPUÉS de eso el bloque de
McCabe-Thiele tiene la información que le falta (x_B) para resolver R.
Eso es lo que se ve abajo: x_B queda resuelto por "Balance de Materia
Global", R queda resuelto por "McCabe-Thiele" -- uno le pasó el dato al
otro sin que yo especifique el orden.
"""

import numpy as np

from config.settings import ureg
from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.elv import CalculadoraELV
from core.mccabe_thiele import EvaluadorMcCabeThiele, SolucionadorMcCabeThiele
from core.balance_materia import BalanceMateriaGlobal
from core.orquestador import (
    Orquestador, bloque_balance_materia, bloque_mccabe_thiele, bloque_cargas_termicas,
    bloque_fug, bloque_cargas_termicas_fug,
)
from api.simulador_destilacion import SimuladorDestilacionBinaria
from core.fug import AnalizadorFUG

NOMBRES = ["benzene", "toluene"]
P_SISTEMA = 101325.0

proveedor = ProveedorTermodinamico(NOMBRES)
calc_elv = CalculadoraELV(proveedor)

evaluador_mt = EvaluadorMcCabeThiele(calc_elv, NOMBRES, P_sistema=P_SISTEMA)
solucionador_mt = SolucionadorMcCabeThiele(evaluador_mt)
balance = BalanceMateriaGlobal()

# Cada bloque declara que variables toca y cuantas ecuaciones aporta.
bloque_balance = bloque_balance_materia(balance)
bloque_mt = bloque_mccabe_thiele(solucionador_mt)

orquestador = Orquestador([bloque_balance, bloque_mt])

D = 38.8889
B = 61.1111
z_F = 0.40
x_D = 0.95
q = 1.0
N = 10.0

print("Lo que le doy al orquestador:")
print("  D   =", D)
print("  B   =", B)
print("  z_F =", z_F)
print("  x_D =", x_D)
print("  q   =", q)
print("  N   =", N)
print("  (nota: NO doy F ni x_B -- esos dos faltan)")

resultado = orquestador.resolver(D=D, B=B, z_F=z_F, x_D=x_D, q=q, N=N)

print()
print("Lo que el orquestador resolvió, y quién lo resolvió:")
print("  F   =", resultado["pool"]["F"], "  <-  resuelto por:", resultado["resueltos_por"]["F"])
print("  x_B =", resultado["pool"]["x_B"], "  <-  resuelto por:", resultado["resueltos_por"]["x_B"])
print("  R   =", resultado["pool"]["R"], "  <-  resuelto por:", resultado["resueltos_por"]["R"])

print()
print("¿Quedó completo?", resultado["completo"])


# ============================================================
# Con la frontera de unidades (api/simulador_destilacion.py) -- mismo
# orquestador, pero ahora con Cargas Termicas agregado, y F/D/B/Q_c/Q_R/
# T_D/T_B entrando y saliendo como pint.Quantity en vez de floats SI.
# ============================================================
orquestador_con_energia = Orquestador([
    bloque_balance_materia(BalanceMateriaGlobal()),
    bloque_mccabe_thiele(solucionador_mt),
    bloque_cargas_termicas(evaluador_mt),
])
simulador = SimuladorDestilacionBinaria(orquestador_con_energia)

F = ureg.Quantity(360.0, "kmol/h")  # unidad no-SI a proposito
resultado_u = simulador.resolver(F=F, z_F=0.40, x_D=0.95, x_B=0.05, q=1.0, N=10.0)

print()
print("Con unidades -- di F =", F)
print("  D   =", resultado_u["pool"]["D"].to("kmol/h"))
print("  B   =", resultado_u["pool"]["B"].to("kmol/h"))
print("  R   =", resultado_u["pool"]["R"], "(adimensional)")
print("  Q_c =", resultado_u["pool"]["Q_c"].to("kW"))
print("  Q_R =", resultado_u["pool"]["Q_R"].to("kW"))
print("  T_D =", resultado_u["pool"]["T_D"].to("degC"))


# ============================================================
# FUG (multicomponente) + Cargas Térmicas -- mismo Orquestador, pero
# ahora con variables VECTORIALES en el pool (x_D, x_B, d, b son arrays
# de 4 componentes, no floats). z_F/q/P_sistema/idx_LK/idx_HK quedan
# fijos al construir AnalizadorFUG (igual que 'q' para Ponchon-Savarit);
# lo que entra al orquestador son recuperacion_LK_D, recuperacion_HK_B,
# R y F.
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

orquestador_fug = Orquestador([
    bloque_fug(analizador_fug),
    bloque_cargas_termicas_fug(analizador_fug),
])

resultado_fug = orquestador_fug.resolver(
    recuperacion_LK_D=0.98, recuperacion_HK_B=0.98, R=3.0, F=100.0,
)

print()
print("FUG + Cargas Térmicas -- di F=100 mol/s, recuperaciones 98%/98%, R=3.0")
print("  N_min =", resultado_fug["pool"]["N_min"], "  N =", resultado_fug["pool"]["N"])
print("  R_min =", resultado_fug["pool"]["R_min"])
print("  D =", resultado_fug["pool"]["D"], " mol/s   B =", resultado_fug["pool"]["B"], "mol/s")
print("  x_D =", dict(zip(NOMBRES_FUG, resultado_fug["pool"]["x_D"])))
print("  x_B =", dict(zip(NOMBRES_FUG, resultado_fug["pool"]["x_B"])))
print("  Q_c =", resultado_fug["pool"]["Q_c"], "W   <- resuelto por:", resultado_fug["resueltos_por"]["Q_c"])
print("  Q_R =", resultado_fug["pool"]["Q_R"], "W")
print("¿Quedó completo?", resultado_fug["completo"])
