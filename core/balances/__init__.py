"""
Motor de balances (ARCHITECTURE.md §5): de las ecuaciones fundamentales y
los supuestos de cada volumen a las ecuaciones explícitas del modelo común.

  generar(modelo) -> el mismo modelo con `matematico` y `restricciones`

Leyes, variables del Engine y límites: core/balances/generador.py y
docs/engine/balance-engine.md.
"""

from .generador import NoGenerable, generar

__all__ = ["NoGenerable", "generar"]
