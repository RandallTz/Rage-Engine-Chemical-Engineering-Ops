"""Nucleo cientifico de adimensionalizacion (herramienta independiente).

No forma parte del motor del simulador: no lo importa ni lo modifica.
"""

from .nucleo import VERSION_NUCLEO, capacidades, procesar

__all__ = ["VERSION_NUCLEO", "capacidades", "procesar"]
