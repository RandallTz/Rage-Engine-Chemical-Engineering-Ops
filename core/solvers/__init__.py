"""
Solvers del motor (ARQUITECTURA_MOTOR.md §5): integran sistemas numéricos sin
saber de física. Ver docs/CORTE_VERTICAL.md.

  integrador.integrar(sistema, y0, t_final, ...) -> Trayectoria
"""

from .integrador import Detencion, Trayectoria, integrar

__all__ = ["Detencion", "Trayectoria", "integrar"]
