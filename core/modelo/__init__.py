"""
Modelo común v0 (docs/contracts/common-model.md): la representación única que
comparten los motores del simulador (ARCHITECTURE.md §4).

  lector.leer_modelo_comun(dato)      -> dict validado (o ErrorModelo)
  relaciones.relaciones(modelo)       -> relaciones estructurales siempre presentes
  adaptadores.*                       -> ida y vuelta con los formatos existentes
"""

from .lector import ErrorModelo, VERSION, leer_modelo_comun
from .relaciones import relaciones
from .adaptadores import (a_documento_adimensional, a_ensamblaje_v2, desde_documento_adimensional,
                          desde_ensamblaje_v2)

__all__ = ["ErrorModelo", "VERSION", "leer_modelo_comun", "relaciones", "desde_documento_adimensional",
           "a_documento_adimensional", "desde_ensamblaje_v2", "a_ensamblaje_v2"]
