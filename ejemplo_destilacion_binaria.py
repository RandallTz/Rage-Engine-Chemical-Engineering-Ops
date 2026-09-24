"""Uso directo: McCabe-Thiele y Ponchon-Savarit, mismo código repetido con distintas variables."""

from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.elv import CalculadoraELV
from core.mccabe_thiele import EvaluadorMcCabeThiele, SolucionadorMcCabeThiele
from core.ponchon_savarit import EvaluadorPonchonSavarit, SolucionadorPonchonSavarit
from core.balance_materia import BalanceMateriaGlobal
from core.orquestador import Orquestador, bloque_balance_materia, bloque_mccabe_thiele

NOMBRES = ["benzene", "toluene"]
P_SISTEMA = 101325.0

proveedor = ProveedorTermodinamico(NOMBRES)
calc_elv = CalculadoraELV(proveedor)

evaluador_mt = EvaluadorMcCabeThiele(calc_elv, NOMBRES, P_sistema=P_SISTEMA)
solucionador_mt = SolucionadorMcCabeThiele(evaluador_mt)

evaluador_ps = EvaluadorPonchonSavarit(calc_elv, NOMBRES, P_sistema=P_SISTEMA)
solucionador_ps = SolucionadorPonchonSavarit(evaluador_ps)


# ============================================================
# McCabe-Thiele -- caso 1
# ============================================================
z_F, q, x_D, x_B, N = 0.40, 1.0, 0.95, 0.05, 10.0
resultado_mt = solucionador_mt.resolver(z_F=z_F, q=q, x_D=x_D, x_B=x_B, N=N)
print(f"McCabe-Thiele: R={resultado_mt['valor_resuelto']:.3f}  N={resultado_mt['N']:.2f}")
evaluador_mt.graficar_diagrama(resultado_mt)

# ============================================================
# McCabe-Thiele -- caso 2 (mismas x_D/x_B, distinto N)
# ============================================================
z_F, q, x_D, x_B, N = 0.40, 1.0, 0.95, 0.05, 15.0
resultado_mt = solucionador_mt.resolver(z_F=z_F, q=q, x_D=x_D, x_B=x_B, N=N)
print(f"McCabe-Thiele: R={resultado_mt['valor_resuelto']:.3f}  N={resultado_mt['N']:.2f}")
evaluador_mt.graficar_diagrama(resultado_mt)

# ============================================================
# McCabe-Thiele -- caso 3 (separación menos exigente)
# ============================================================
z_F, q, x_D, x_B, N = 0.40, 1.0, 0.80, 0.20, 10.0
resultado_mt = solucionador_mt.resolver(z_F=z_F, q=q, x_D=x_D, x_B=x_B, N=N)
print(f"McCabe-Thiele: R={resultado_mt['valor_resuelto']:.3f}  N={resultado_mt['N']:.2f}")
evaluador_mt.graficar_diagrama(resultado_mt)


# ============================================================
# Ponchon-Savarit -- caso 1
# ============================================================
z_F, q, x_D, x_B, N = 0.40, 1.0, 0.95, 0.05, 10.0
resultado_ps = solucionador_ps.resolver(z_F=z_F, x_D=x_D, x_B=x_B, q=q, N=N)
print(f"Ponchon-Savarit: Qc_D={resultado_ps['valor_resuelto']:.1f}  N={resultado_ps['N']:.2f}")
evaluador_ps.graficar_diagrama(resultado_ps)

# ============================================================
# Ponchon-Savarit -- caso 2 (mismas x_D/x_B, distinto N)
# ============================================================
z_F, q, x_D, x_B, N = 0.40, 1.0, 0.95, 0.05, 15.0
resultado_ps = solucionador_ps.resolver(z_F=z_F, x_D=x_D, x_B=x_B, q=q, N=N)
print(f"Ponchon-Savarit: Qc_D={resultado_ps['valor_resuelto']:.1f}  N={resultado_ps['N']:.2f}")
evaluador_ps.graficar_diagrama(resultado_ps)

# ============================================================
# Ponchon-Savarit -- caso 3 (separación menos exigente)
# ============================================================
z_F, q, x_D, x_B, N = 0.40, 1.0, 0.80, 0.20, 10.0
resultado_ps = solucionador_ps.resolver(z_F=z_F, x_D=x_D, x_B=x_B, q=q, N=N)
print(f"Ponchon-Savarit: Qc_D={resultado_ps['valor_resuelto']:.1f}  N={resultado_ps['N']:.2f}")
evaluador_ps.graficar_diagrama(resultado_ps)


# ============================================================
# Orquestador -- doy F, z_F, x_D, x_B, q, N; el resuelve D, B (balance
# de materia) y R (McCabe-Thiele) en una sola llamada.
# ============================================================
orquestador = Orquestador([
    bloque_balance_materia(BalanceMateriaGlobal()),
    bloque_mccabe_thiele(solucionador_mt),
])
resultado = orquestador.resolver(F=100.0, z_F=0.40, x_D=0.95, x_B=0.05, q=1.0, N=10.0)
print(f"Orquestador: D={resultado['pool']['D']:.2f}  B={resultado['pool']['B']:.2f}  "
      f"R={resultado['pool']['R']:.3f}")
