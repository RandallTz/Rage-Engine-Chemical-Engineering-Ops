"""
Solvers del motor (ARCHITECTURE.md §5): integran sistemas numéricos sin
saber de física. Ver docs/engine/vertical-slice.md.

  integrador.integrar(sistema, y0, t_final, ...) -> Trayectoria
"""

from .integrador import Detencion, Trayectoria, integrar

__all__ = ["Detencion", "Trayectoria", "integrar"]
