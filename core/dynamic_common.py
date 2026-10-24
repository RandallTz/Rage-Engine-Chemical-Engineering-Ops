"""
Types shared by the dynamic assembly paths (core/ensamblaje_red.py, backend/motor_ensamblaje.py and
backend/motor_ensamblaje_v2.py). They lived in the legacy single-volume assembly core/ensamblaje_dinamico.py,
retired by the user decision dec-r5-legacy-v1 (23 October 2026); their behavior is unchanged.
"""

from dataclasses import dataclass


@dataclass
class Funcion:
    """SI datum as a function of t [s]: value = f(t)*factor + desplazamiento."""
    f: object               # callable t -> declared value
    df: object | None       # callable t -> derivative of the declared value, or None
    factor: float
    desplazamiento: float
    constante: bool

    def __call__(self, t):
        return self.f(t) * self.factor + self.desplazamiento

    def derivada(self, t):
        return 0.0 if self.constante else self.df(t) * self.factor


class Detencion(Exception):
    """A physical or certification stop of a trajectory at time t."""

    def __init__(self, codigo, mensaje, t=None):
        super().__init__(mensaje)
        self.codigo, self.mensaje, self.t = codigo, mensaje, t
