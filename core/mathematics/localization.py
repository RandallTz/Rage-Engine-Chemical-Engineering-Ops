"""PDE-6: pointwise thermodynamic contract by homogeneity (16 November 2026).

A volume's thermodynamic relations are written for the whole volume: U, S, V,
n_i, G ... are extensive and T, P, mu_i are intensive functions of time. A field
model needs the same relations at every point of a declared spatial domain.
Local equilibrium makes every material point a simple system in internal
equilibrium; Euler's first-order homogeneity of the fundamental relation then
carries each lumped relation to the point:

1. the relation is checked to be homogeneous of degree k (0 or 1) in the
   declared extensive quantities: replacing every extensive X by lambda X
   multiplies its residual by lambda**k (a symbolic check, never assumed);
2. each extensive X other than the volume is written X = V x_v, with x_v a
   density field on the domain coordinates and time (one recorded definition per
   quantity); each intensive quantity is restated as a field on the same
   coordinates (one recorded local-equilibrium condition per quantity);
3. the substituted relation is divided by V**k (V > 0), which removes V by
   homogeneity; the kernel checks that V is gone and that the division is exact.

Differentials of intensive quantities localize the same way (Gibbs-Duhem). A
differential of an extensive quantity (dU, dG, dn_i) carries a dV term that the
density form does not have, so it is rejected with a located message: localize
the Euler relation and the Gibbs-Duhem relation instead. Nothing here is
evaluated or discretized; Solve keeps its requires_discretization rejection.
"""
import sympy as sp
from sympy.core.function import AppliedUndef

from .errors import MathematicsError
from .operators import StateDifferential, is_coordinate

LOCAL_EQUILIBRIUM = ('Local equilibrium: every material point of the domain is a simple system in internal equilibrium, '
                     'so the volume\'s thermodynamic relations hold pointwise (Prigogine local-equilibrium hypothesis)')


def _name(quantity):
    return quantity.func.__name__ if isinstance(quantity, AppliedUndef) else str(quantity)


def density_name(quantity):
    """n_1__v1 -> n_1_density__v1: the producer's owner scope stays a suffix."""
    base, _, scope = _name(quantity).partition('__')
    return base + '_density' + ('__' + scope if scope else '')


def _lumped(quantity, time):
    """A volume quantity: a constant symbol or a function of time only."""
    if isinstance(quantity, sp.Symbol):
        return quantity != time and not is_coordinate(quantity)
    return isinstance(quantity, AppliedUndef) and all(a == time for a in quantity.args)


def _recorded(graph, rule, lhs, rhs, domain_id):
    """An earlier identity of this rule on the same domain with the same sides, or None."""
    for key, node in graph.nodes.items():
        if node.rule == rule and domain_id in node.inputs and node.equation == sp.Eq(lhs, rhs, evaluate=False):
            return key
    return None


def homogeneity_degree(equation, extensive):
    """Degree k in {1, 0} with residual(lambda X) = lambda**k residual(X), or None."""
    scale = sp.Dummy('lambda', positive=True)
    residual = equation.lhs - equation.rhs
    scaled = residual.xreplace({X: scale * X for X in extensive})
    for degree in (1, 0):
        if sp.simplify(sp.expand(scaled - scale ** degree * residual)) == 0:
            return degree
    return None


def localize_by_homogeneity(graph, key, source, domain_id, volume, extensive, units, unit_of, family, reason):
    """Record the pointwise form of a lumped homogeneous relation on a declared spatial domain.

    Returns (key, created ids, {new density field: unit}). ``unit_of`` resolves a quantity's unit.
    """
    node = graph.nodes[source]
    equation = node.equation
    if not isinstance(equation, sp.Equality):
        raise MathematicsError('Localize a thermodynamic equation, not a domain condition.')
    if domain_id not in graph.spatial_domains:
        raise MathematicsError('Select a declared spatial domain; ' + str(domain_id) + ' is not one.')
    domain = graph.spatial_domains[domain_id]
    # The volume is extensive and is the measure of the densities, whether or not the relation names it.
    extensive = tuple(dict.fromkeys((volume, *extensive)))
    times = {a for q in equation.atoms(AppliedUndef) for a in q.args if isinstance(a, sp.Symbol) and not is_coordinate(a)}
    if any(is_coordinate(a) for q in equation.atoms(AppliedUndef) for a in q.args) or len(times) > 1:
        raise MathematicsError('Localize a lumped volume relation: its quantities depend on time only, not on spatial coordinates.')
    time = next(iter(times), None)
    if time is None:
        raise MathematicsError('The relation has no time-dependent volume quantity to localize.')
    for quantity in extensive:
        if not _lumped(quantity, time) or quantity != volume and not equation.has(quantity):
            raise MathematicsError('The extensive quantity ' + str(quantity) + ' must be a volume quantity that occurs in the selected relation.')
    volume_unit = unit_of(volume)
    if volume_unit is None or volume_unit.replace(' ', '') not in ('m3', 'm^3', 'm**3'):
        raise MathematicsError('The volume must be declared in m3, so each density is per unit volume.')
    differentials = sorted(equation.atoms(StateDifferential), key=sp.default_sort_key)
    for differential in differentials:
        if differential.args[0] in extensive:
            raise MathematicsError('d(' + str(differential.args[0]) + ') is the differential of an extensive quantity: its density form gains a dV term. '
                                   'Localize the Euler relation and the Gibbs-Duhem relation, whose differentials are of intensive quantities only.')
    degree = homogeneity_degree(equation, extensive)
    if degree is None:
        raise MathematicsError('The relation is not homogeneous of degree 0 or 1 in ' + ', '.join(map(str, extensive))
                               + ' (scaling every extensive quantity by lambda does not scale its residual by lambda or 1); '
                               'it cannot hold pointwise by homogeneity. Check the extensive set or the relation.')
    coordinates = tuple(domain.coordinates)
    point = (*coordinates, time)
    taken = {_name(q) for n in graph.nodes.values() if isinstance(n.equation, sp.Basic) for q in n.equation.atoms(sp.Symbol, AppliedUndef)}
    created, densities, replacements = [], {}, {}
    for index, quantity in enumerate(extensive):
        if quantity == volume:
            continue
        unit = unit_of(quantity)
        if unit is None:
            raise MathematicsError('Declare the unit of ' + str(quantity) + ' before forming its density.')
        field = sp.Function(density_name(quantity))(*point)
        reused = _recorded(graph, 'density_definition', quantity, volume * field, domain_id)
        if reused:
            # The same density on the same domain is one field: later localizations reuse its recorded definition.
            created.append(reused)
            replacements[quantity] = volume * field
            continue
        if field.func.__name__ in taken:
            raise MathematicsError('The density name ' + field.func.__name__ + ' is already used.')
        identity = key + '.density.' + str(index + 1)
        graph.add(identity, quantity, volume * field, 'Local density of ' + str(quantity), 'density_definition', (source, domain_id),
                  (str(field) + ' is the amount of ' + str(quantity) + ' per unit volume at each point of ' + domain_id
                   + ' (continuum limit of ' + str(quantity) + '/' + str(volume) + ')',), family, kind='definition')
        created.append(identity)
        densities[field] = '(' + unit + ')/(' + volume_unit + ')'
        replacements[quantity] = volume * field
    intensive = sorted((q for q in equation.atoms(AppliedUndef) if q not in extensive and _lumped(q, time)), key=sp.default_sort_key)
    for index, quantity in enumerate(intensive):
        field = quantity.func(*point)
        reused = _recorded(graph, 'local_equilibrium', quantity, field, domain_id)
        if reused:
            created.append(reused)
            replacements[quantity] = field
            continue
        identity = key + '.field.' + str(index + 1)
        graph.add(identity, quantity, field, 'Restate ' + quantity.func.__name__ + ' as a field on ' + domain_id, 'local_equilibrium', (source, domain_id),
                  (LOCAL_EQUILIBRIUM, quantity.func.__name__ + ' is intensive: its local value at each point replaces the volume value'),
                  family, kind='constraint')
        created.append(identity)
        replacements[quantity] = field
    substituted = key + '.substituted'
    left, right = equation.lhs.xreplace(replacements), equation.rhs.xreplace(replacements)
    graph.add(substituted, left, right, 'Substitute local densities and fields on ' + domain_id, 'substitution', (source, *created), (), family,
              kind=node.kind)
    created.append(substituted)
    factor = volume ** degree
    local_left, local_right = sp.expand(left / factor), sp.expand(right / factor)
    if local_left.has(volume) or local_right.has(volume):
        raise MathematicsError('The volume does not cancel from the localized relation; it is not a pointwise relation.')
    if sp.simplify(sp.expand((local_left - local_right) * factor - (left - right))) != 0:
        raise MathematicsError('The localized relation is not an exact division of the substituted relation.')
    conditions = [reason,
                  'Euler homogeneity of degree ' + str(degree) + ' in ' + ', '.join(map(str, extensive)) + ' (checked by scaling every extensive quantity)',
                  LOCAL_EQUILIBRIUM]
    if degree:
        conditions.append('Divided by ' + str(volume) + ' > 0')
    graph.add(key, local_left, local_right, 'Pointwise form by homogeneity on ' + domain_id, 'localization_by_homogeneity', (substituted,),
              tuple(conditions), family, kind=node.kind)
    return key, tuple(created), densities
