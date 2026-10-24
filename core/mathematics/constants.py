"""Typed SI basis factors for exact constants, independent of physical families."""
import sympy as sp
from core.unidades.servicio import SIMBOLO_SI


class UnitBasis(sp.AtomicExpr):
    """A positive, constant unit magnitude, never an unknown or a plain number."""
    is_positive = True
    is_commutative = True

    def __new__(cls, base):
        base = str(base)
        if base not in SIMBOLO_SI:
            raise ValueError('Unknown SI dimension basis.')
        return sp.AtomicExpr.__new__(cls, sp.core.symbol.Str(base))

    @property
    def base(self):
        return str(self.args[0])

    @property
    def free_symbols(self):
        return set()

    def _eval_derivative(self, symbol):
        return sp.S.Zero

    def _latex(self, printer):
        return r'\mathrm{' + SIMBOLO_SI[self.base] + '}'


def unit_basis(dimension):
    return sp.Mul(*(UnitBasis(base)**sp.Rational(power) for base, power in sorted(dimension.items())))


def si_magnitude(expression):
    """Coordinate projection for domain proofs only; never a graph rewrite."""
    return expression.xreplace({atom:sp.S.One for atom in expression.atoms(UnitBasis)})
