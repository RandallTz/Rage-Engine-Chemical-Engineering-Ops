"""
Compilador del modelo común (ARQUITECTURA_MOTOR.md §5, docs/CORTE_VERTICAL.md):
modelo + datos -> sistema numérico (rhs, firma, estado inicial, observables).

  compilar(modelo)            -> SistemaCompilado
  resolver(modelo)            -> conjunto de resultados (formato común)
"""

from .compilador import NoSoportado, SistemaCompilado, compilar, resolver

__all__ = ["NoSoportado", "SistemaCompilado", "compilar", "resolver"]
