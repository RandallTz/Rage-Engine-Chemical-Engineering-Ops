"""
Servicio único de unidades y dimensiones (ARCHITECTURE.md §5, docs/contracts/units-service.md).

  interpretar(unidad)          -> dimensión exacta, factor y desplazamiento a SI
  a_SI(valor, unidad) / desde_SI(valor_SI, unidad)
  compatibles(u1, u2)          -> misma dimensión
  unidad_SI(dimension)         -> texto canónico de la unidad SI
  magnitudes_de(dimension)     -> nombres de magnitud con esa dimensión (catálogo genérico)
  MAGNITUDES                   -> catálogo: nombre -> dimensión

Las magnitudes se definen SOLO por su dimensión: ninguna está atada a un
tipo de operación o equipo, y cualquier unidad con la dimensión correcta es
válida (no hay listas cerradas de unidades por magnitud).
"""

from .servicio import (MAGNITUDES, BASES, ErrorUnidad, a_SI, compatibles, desde_SI, dimension_de_magnitud,
                       dimension_texto, interpretar, magnitudes_de, normalizar, unidad_SI, exact_conversion)

__all__ = ["MAGNITUDES", "BASES", "ErrorUnidad", "a_SI", "compatibles", "desde_SI", "dimension_de_magnitud",
           "dimension_texto", "interpretar", "magnitudes_de", "normalizar", "unidad_SI", "exact_conversion"]
