"""
Compilador del modelo común (ARCHITECTURE.md §5, docs/engine/vertical-slice.md):
modelo + datos -> sistema numérico (rhs, firma, estado inicial, observables).

  compilar(modelo)            -> SistemaCompilado (entrada estructural)
  SistemaExplicito(modelo)    -> sistema de las ecuaciones escritas (matematico)
  resolver(modelo)            -> conjunto de resultados (formato común), por la
                                 entrada que corresponda
"""

from .compilador import NoSoportado, SistemaCompilado, compilar, resolver
from .explicito import SistemaExplicito, es_explicito, resolver_explicito

__all__ = ["NoSoportado", "SistemaCompilado", "SistemaExplicito", "compilar", "es_explicito", "resolver", "resolver_explicito"]
