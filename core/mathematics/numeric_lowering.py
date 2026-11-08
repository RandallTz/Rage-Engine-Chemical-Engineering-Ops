"""Numeric lowering of exact expressions: declared exact data must reach numpy as floats.

``sympy.lambdify`` prints an exact Integer or Rational as Python ints. A declared datum with many
digits (for example 0.0007000000000000001) produces integers beyond int64 inside ``sqrt``, ``log``
or fractional powers, and numpy then receives an object array: "loop of ufunc does not support
argument 0 of type int". Replacing those exact numbers by correctly rounded floats before printing
is the same value the evaluation would use anyway; the symbolic derivation is not touched.
"""
import sympy as sp

_INT64 = 2 ** 62


def float_constants(expression):
    """Replace every exact Integer/Rational with a magnitude or denominator beyond a safe int64 by a Float.

    Accepts an expression or a (nested) list/tuple/Matrix of expressions and returns the same shape.
    """
    if isinstance(expression, (list, tuple)):
        return type(expression)(float_constants(e) for e in expression)
    if isinstance(expression, sp.MatrixBase):
        return expression.applyfunc(float_constants)
    if not isinstance(expression, sp.Basic):
        return expression
    replacements = {}
    for number in expression.atoms(sp.Rational):
        if abs(number.p) > _INT64 or number.q > _INT64:
            replacements[number] = sp.Float(number, 17)
    return expression.xreplace(replacements) if replacements else expression


def lambdify_numeric(arguments, expression, *args, **kwargs):
    """``sympy.lambdify`` over ``float_constants(expression)``."""
    return sp.lambdify(arguments, float_constants(expression), *args, **kwargs)
