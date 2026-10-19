"""
Motor de balances (ARQUITECTURA_MOTOR.md §5): de las ecuaciones fundamentales y
los supuestos de cada volumen a las ecuaciones explícitas del modelo común.

  generar(modelo) -> el mismo modelo con `matematico` y `restricciones`

Leyes, variables del Engine y límites: core/balances/generador.py y
docs/MOTOR_BALANCES.md.
"""

from .generador import NoGenerable, generar

__all__ = ["NoGenerable", "generar"]
