"""
Capa termodinámica del modelo común (ARCHITECTURE.md §3, docs/contracts/thermodynamic-layer.md).

  capa.candidatas(modelo, volumen_id)          -> fases candidatas, siempre las mismas
  capa.variables(modelo)                       -> variables de estado siempre presentes
  capa.cierre(modelo, volumen_id, n, espec)    -> estado con TODAS las fases candidatas
"""

from .capa import NoSoportado, candidatas, cierre, variables

__all__ = ["NoSoportado", "candidatas", "cierre", "variables"]
