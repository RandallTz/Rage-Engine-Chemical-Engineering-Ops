"""Fourier closure and generic spatial-operator expansion (PDE-3, 7 November 2026).

``declare_fourier_law`` closes the conductive heat flux of a local energy law
with Fourier's empirical law q = -k grad T, recorded as a typed constitutive
root with its source, conditions and a dimension check. The user then applies
the ordinary ``substitute`` rule.

``expand_spatial_operators`` turns the coordinate-free operators of a local law
into chart derivatives on a declared spatial domain (PDE-1):

1. each spatial field is restated in the domain's active coordinates, one
   recorded constraint per field (dropped Cartesian axes are invariance
   assumptions; a field on the Cartesian placeholder (x, y, z) in a cylindrical
   or spherical domain is restated through the coordinate map);
2. each divergence of a gradient flux sum_j a_j grad(u_j) is replaced by one
   recorded Lame-factor identity of the orthogonal chart,
   div(a grad u) = (1/H) sum_i d_i(H a / h_i^2 du/dxi_i), H = h_1 h_2 h_3,
   summed over the active coordinates and kept in conservative form.

Vector terms that are not a scalar times a gradient have no typed vector
structure here and are rejected with a located message, as is a gradient left
outside a divergence. Nothing is discretized or solved: the result still
carries spatial derivatives, so Solve keeps its requires_discretization
diagnostic (PDE-0).
"""
import sympy as sp
from core.unidades import unidad_SI
from .errors import MathematicsError as JournalError
from .operators import (Divergence, Gradient, VolumeIntegral, BoundaryFlux, BOUNDARY_OPERATORS,
                        field_coordinates, is_coordinate)
from .domains import scale_factors

FOURIER_SOURCE = {
    'kind': 'empirical constitutive law',
    'citation': 'J. B. J. Fourier, Theorie analytique de la chaleur, Paris, 1822',
    'validRange': 'Isotropic heat conduction, linear in the temperature gradient, in a continuum at local equilibrium; '
                  'positive thermal conductivity (second law); no radiative or Dufour (diffusion-driven) heat flux',
}
PLACEHOLDER = ('x', 'y', 'z')
LABELS = {'cartesian': 'Cartesian', 'cylindrical': 'cylindrical', 'spherical': 'spherical'}


def _si(dimension):
    return unidad_SI({base: power for base, power in (dimension or {}).items() if power}) if dimension else '1'


def _spatial_field(quantity, declared=()):
    return isinstance(quantity, sp.core.function.AppliedUndef) and bool(field_coordinates(quantity, declared=declared))


def _under_divergence(expression, target):
    return any(isinstance(node, Divergence) and node.args[0].has(target) for node in sp.preorder_traversal(expression))


def declare_fourier_law(graph, key, source, flux, temperature, conductivity, units, dimension, family, reasons=()):
    """Record q = -k grad(T) as the conductive flux closure of a local energy law."""
    equation = graph.nodes[source].equation
    if not isinstance(equation, sp.Equality):
        raise JournalError("Declare Fourier's law on a local energy balance, not on a domain condition.")
    if not _spatial_field(flux):
        raise JournalError('The conductive heat flux must be a field of the spatial coordinates.')
    if not _under_divergence(equation, flux):
        raise JournalError('The selected flux ' + str(flux) + ' does not occur under a divergence of the selected local balance; '
                           "Fourier's law closes the conductive flux of a local energy law.")
    if not _spatial_field(temperature) or temperature == flux:
        raise JournalError('The temperature must be a scalar field of the spatial coordinates.')
    if dimension(temperature, units) != {'Theta': 1}:
        raise JournalError('The potential of Fourier conduction is the absolute temperature; select a field declared in kelvin.')
    if conductivity.has(Divergence, Gradient, sp.Derivative, flux) or not conductivity.free_symbols:
        raise JournalError('The thermal conductivity is a scalar material property: a symbol or a function of state, '
                           'without derivatives, operators or the flux itself.')
    if conductivity.is_positive is False or conductivity.is_nonpositive is True:
        raise JournalError('The thermal conductivity must be positive (second law: heat flows down the temperature gradient).')
    q, k, theta = dimension(flux, units), dimension(conductivity, units), dimension(temperature, units)
    if q is None or k is None:raise JournalError('Declare the units of the heat flux and of the thermal conductivity.')
    expected = {base: k.get(base, 0) + theta.get(base, 0) - (1 if base == 'L' else 0) for base in {*k, *theta, 'L'}}
    expected = {base: power for base, power in expected.items() if power}
    if expected != q:
        raise JournalError('Fourier law dimensions: k grad T has ' + _si(expected) + ' but the heat flux has ' + _si(q)
                           + '; the conductivity unit must be the flux unit per temperature gradient (W/(m*K)).')
    conditions = [*reasons,
                  'Isotropic conduction, linear in the temperature gradient (Fourier 1822)',
                  'No radiative or Dufour (diffusion-driven) contribution to the conductive heat flux',
                  str(temperature) + ' is the local equilibrium temperature of the continuum']
    predicates = ()
    if conductivity.is_positive is not True:
        if any(is_coordinate(s) for s in conductivity.free_symbols) or conductivity.atoms(sp.core.function.AppliedUndef):
            conditions.append('Second law: ' + str(conductivity) + ' > 0 throughout the spatial domain')
        else:
            predicates = (sp.Gt(conductivity, 0, evaluate=False),)
    graph.add(key, flux, -conductivity * Gradient(temperature), "Fourier's law of heat conduction", 'fourier_law', (source,),
              tuple(conditions), family, kind='constitutive', predicates=predicates)
    graph.nodes[key].source = dict(FOURIER_SOURCE)
    return key


def _restatement(field, domain):
    """(restated field, description) in the domain's active coordinates, or None when already there."""
    active = domain.coordinates
    spatial = [a for a in field.args if is_coordinate(a, declared=domain.axes)]
    names = sorted(str(a).split('__')[0] for a in spatial)
    if domain.chart != 'cartesian' and names == sorted(PLACEHOLDER) and all(a in (sp.Symbol(n, real=True) for n in PLACEHOLDER) for a in spatial):
        arguments = []
        for argument in field.args:
            if argument not in spatial:arguments.append(argument)
            elif not any(c in arguments for c in active):arguments.extend(active)
        invariant = [str(axis) for axis in domain.axes if axis not in active]
        text = (str(field) + ' restated in the ' + LABELS[domain.chart] + ' chart through the coordinate map from the Cartesian placeholder (x, y, z)'
                + ('; invariant along ' + ', '.join(invariant) if invariant else ''))
        return field.func(*arguments), text
    outside = [str(a) for a in spatial if a not in domain.axes]
    if outside:
        raise JournalError('Field ' + str(field) + ' depends on ' + ', '.join(outside) + ', outside the ' + LABELS[domain.chart]
                           + ' chart of the spatial domain; only the full Cartesian placeholder (x, y, z) can be restated in another chart.')
    dropped = [a for a in spatial if a not in active]
    if not dropped:return None
    text = (str(field) + ' is invariant along ' + ', '.join(map(str, dropped)) + ' (d/d' + ', d/d'.join(map(str, dropped))
            + ' = 0): its spatial dependence is restricted to the active coordinates ' + ', '.join(map(str, active)))
    return field.func(*(a for a in field.args if a not in dropped)), text


def _gradient_terms(flux, location):
    """Split a flux into (coefficient, potential) pairs a_j grad(u_j); reject untyped vector terms."""
    terms = []
    for term in sp.Add.make_args(sp.expand(flux, deep=False)):
        factors = sp.Mul.make_args(term)
        gradients = [f for f in factors if isinstance(f, Gradient)]
        coefficient = sp.Mul(*(f for f in factors if not isinstance(f, Gradient)))
        if len(gradients) != 1 or coefficient.has(Gradient, Divergence) or gradients[0].args[0].has(Gradient, Divergence):
            raise JournalError('The term ' + str(term) + ' under the divergence ' + location + ' is not a scalar times a gradient; '
                               'it is an untyped vector field. Substitute its constitutive law (or declare it zero) before expanding.')
        terms.append((coefficient, gradients[0].args[0]))
    return terms


def expand_spatial_operators(graph, key, source, domain_id, family):
    """Restate fields in the chart and expand each divergence of a gradient flux by its Lame-factor identity."""
    equation = graph.nodes[source].equation
    if not isinstance(equation, sp.Equality):raise JournalError('Expand an equation, not a domain condition.')
    if domain_id not in graph.spatial_domains:raise JournalError('Select a declared spatial domain; ' + str(domain_id) + ' is not one.')
    domain = graph.spatial_domains[domain_id]
    active = set(domain.coordinates)
    chart = LABELS[domain.chart]
    if equation.has(VolumeIntegral, BoundaryFlux):
        raise JournalError('Expand the local differential form of the law: volume integrals and boundary fluxes are not pointwise operators. Apply Gauss and localize first.')
    if equation.has(*BOUNDARY_OPERATORS):
        raise JournalError('Boundary relations are expanded by expand_normal_derivative, not by the interior operator expansion.')
    if not equation.atoms(Divergence):
        raise JournalError('The selected equation has no divergence to expand on spatial domain ' + domain_id + '.')
    for derivative in sorted(equation.atoms(sp.Derivative), key=sp.default_sort_key):
        for variable, _ in derivative.variable_count:
            if is_coordinate(variable, declared=domain.axes) and variable not in active:
                raise JournalError('The derivative ' + str(derivative) + ' is taken along ' + str(variable) + ', which is not an active coordinate of '
                                   + domain_id + '; restating the field would silently delete it. Declare that coordinate active or record its zero first.')
    created = []
    restated = {}
    fields = sorted({f for f in equation.atoms(sp.core.function.AppliedUndef) if field_coordinates(f, declared=domain.axes)}, key=sp.default_sort_key)
    for field in fields:
        restatement = _restatement(field, domain)
        if restatement is None:continue
        new, text = restatement
        identity = key + '.chart.' + str(len(created) + 1)
        graph.add(identity, field, new, 'Restate ' + str(field.func) + ' in the active coordinates of ' + domain_id, 'chart_restatement', (domain_id,),
                  (text,), family, kind='constraint')
        created.append(identity);restated[field] = new
    current = source
    if restated:
        current = key + '.chart'
        graph.substitute(current, source, restated, 'Restate each field in the ' + chart + ' chart of ' + domain_id, inputs=tuple(created))
    equation = graph.nodes[current].equation
    stray = [str(s) for s in equation.free_symbols if is_coordinate(s, declared=domain.axes) and s not in active]
    if stray:
        raise JournalError('Coordinate ' + ', '.join(sorted(stray)) + ' occurs explicitly but is not active on ' + domain_id
                           + '; the equation cannot be restated in the active coordinates.')
    targets = sorted(equation.atoms(Divergence), key=sp.default_sort_key)
    dummies = {target: sp.Dummy() for target in targets}
    if equation.xreplace(dummies).has(Gradient):
        raise JournalError('A gradient occurs outside a divergence; a vector equation is not expanded here. Project it on a normal (restrict_to_boundary) or contract it first.')
    h = scale_factors(domain.chart)
    H = sp.Mul(*h)
    factors = ', '.join('h_' + str(axis) + ' = ' + str(factor) for axis, factor in zip(domain.axes, h))
    replacements = {}
    for index, target in enumerate(targets):
        if target.args[0].has(Divergence):raise JournalError('Nested divergences are not expanded; expand the inner flux first.')
        expansion = sp.S.Zero
        for coefficient, potential in _gradient_terms(target.args[0], 'in ' + str(target)):
            for axis, scale in zip(domain.axes, h):
                if axis not in active:continue
                component = sp.diff(potential, axis)
                if component == 0:continue
                outside, inside = (H * coefficient / scale**2 * component).as_independent(axis, as_Add=False)
                expansion += outside / H * sp.Derivative(inside, axis)
        conditions = ['Orthogonal ' + chart + ' chart with Lame factors ' + factors + ', H = ' + str(H)
                      + ': div(a grad u) = (1/H) sum_i d/dxi_i(H a/h_i^2 du/dxi_i) over the active coordinates ' + ', '.join(map(str, domain.coordinates)),
                      'Fields twice continuously differentiable in the interior of ' + domain_id]
        if domain.chart != 'cartesian':
            conditions.append('Valid away from r = 0, where the ' + chart + ' chart is singular (axis or centre)')
        identity = key + '.identity.' + str(index + 1)
        graph.add(identity, target, expansion, 'Expand the divergence of a gradient flux in the ' + chart + ' chart', 'operator_identity', (domain_id,),
                  tuple(conditions), family, kind='definition')
        created.append(identity);replacements[target] = expansion
    graph.substitute(key, current, replacements, 'Substitute the ' + chart + ' expansion of each divergence',
                     inputs=tuple(c for c in created if '.identity.' in c))
    if restated:created.append(current)
    return key, tuple(created)
