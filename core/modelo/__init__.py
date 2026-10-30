"""
Common model v0 (docs/contracts/common-model.md): the single representation
shared by the simulator engines (ARCHITECTURE.md §4).

  lector.leer_modelo_comun(dato)      -> validated dict (or ErrorModelo)
  relaciones.relaciones(modelo)       -> always-present structural relations
  adaptadores.*                       -> round trips with existing formats
"""

from .lector import ErrorModelo, VERSION, leer_modelo_comun
from .relaciones import relaciones
from .adaptadores import (a_documento_adimensional, a_ensamblaje_v2, desde_documento_adimensional,
                          desde_ensamblaje_v2)

__all__ = ["ErrorModelo", "VERSION", "leer_modelo_comun", "relaciones", "desde_documento_adimensional",
           "a_documento_adimensional", "desde_ensamblaje_v2", "a_ensamblaje_v2"]
