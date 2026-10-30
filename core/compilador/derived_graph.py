"""Shared replay identities and typed graph data, independent of time integration."""
import hashlib
import json
import sympy as sp
from core import unidades as units
from core.mathematics.dimensions import dimension, parse_expression
from core.modelo.equation_workbench import build, _known_unit, SOURCE_REVISION
from .compilador import NoSoportado


class LoweringError(NoSoportado):
    def __init__(self, code, message, equation_id=None):
        super().__init__(message)
        self.diagnostics = [{'code': code, 'message': message,
                             **({'equationId': equation_id} if equation_id else {})}]


def source_signature(model, replayed=None):
    """Pin mathematical content and unit declarations, independently of labels/data."""
    result = replayed if replayed is not None else build(model)
    payload = [SOURCE_REVISION,
        [(key, sp.srepr(node.equation), node.rule, node.inputs, node.kind,
          node.dependent, sorted(sp.srepr(p) for p in node.predicates))
         for key, node in sorted(result.graph.nodes.items())],
        sorted((sp.srepr(q), unit) for q, unit in result.units.items()),
        result.definition]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


class DerivedGraph:
    def _quantity(self, key):
        if key not in self.quantities:
            raise LoweringError('missing_quantity', 'The selected quantity no longer exists: ' + key)
        return self.quantities[key]

    def _equation(self, key):
        if key not in self.graph.nodes or not isinstance(self.graph.nodes[key].equation, sp.Equality):
            raise LoweringError('missing_equation', 'Select an existing equality from Transform.', key)
        return self.graph.nodes[key]

    def _dim(self, expression):
        return dimension(expression, self.replayed.units, _known_unit) or {}

    def _unit(self, expression):
        return units.unidad_SI(self._dim(expression))

    def _datum(self, key, expected):
        if key not in self.model['datos']:
            raise LoweringError('missing_data', 'Missing numerical datum: ' + key)
        declaration = self.model['datos'][key]['declaracion']
        try:
            conversion = units.exact_conversion(declaration['unidad'])
            if conversion['dimension'] != expected or conversion['afin']:
                raise ValueError('Use a dimension-compatible absolute unit.')
            value = parse_expression(declaration['texto'], {})
            value = value * sp.Rational(conversion['factor']) + sp.Rational(conversion['desplazamiento'])
            if value.is_number is not True or value.is_finite is not True or value.is_real is not True:
                raise ValueError('Use a finite real constant datum.')
            return value
        except (ValueError, units.ErrorUnidad) as error:
            raise LoweringError('invalid_data', key + ': ' + str(error)) from error

    def _expand(self, expression, replacements=None):
        replacements = self.replacements if replacements is None else replacements
        previous = expression
        for _ in range(len(replacements) + 2):
            current = previous.xreplace(replacements)
            if current == previous:
                return current
            previous = current
        raise LoweringError('cyclic_reconstruction', 'Algebraic reconstruction is cyclic; an implicit constraint needs a different compiler.')

