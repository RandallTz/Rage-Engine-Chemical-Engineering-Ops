"""
Common-model compiler (ARCHITECTURE.md §5, docs/engine/vertical-slice.md):
model + data -> numerical system (rhs, signature, initial state, observables).

  compilar(modelo)            -> SistemaCompilado (structural entry point)
  SistemaExplicito(modelo)    -> system of authored equations (matematico)
  resolver(modelo)            -> common-format result set through the
                                 applicable entry point
"""

from .compilador import NoSoportado, SistemaCompilado, compilar, resolver
from .explicito import SistemaExplicito, es_explicito, resolver_explicito

__all__ = ["NoSoportado", "SistemaCompilado", "SistemaExplicito", "compilar", "es_explicito", "resolver", "resolver_explicito"]
