"""Certified extent-box composition through the public chemical API only.

Binary64 endpoints are treated as exact rationals. Each arithmetic result is
rounded outwards before reuse; no sampled derivative establishes admission.
"""
from fractions import Fraction
import math
import numpy as np
import sympy as sp
from core.reactions import chemical_equilibrium as chemistry
from .derived_graph import LoweringError


def reject(code, message, path):
    error = LoweringError(code, message)
    error.diagnostics[0]['path'] = path
    raise error


def outward(value, upper):
    value = Fraction(value)
    try:number = float(value)
    except OverflowError:
        reject('NONFINITE_BOUND', 'Extent interval arithmetic overflowed.', 'equilibriumReactions.bounds')
    if not math.isfinite(number):
        reject('NONFINITE_BOUND', 'Extent interval arithmetic overflowed.', 'equilibriumReactions.bounds')
    exact = Fraction(number)
    if upper and exact < value or not upper and exact > value:
        number = math.nextafter(number, math.inf if upper else -math.inf)
    return number


def pair(values):
    if len(values) != 2 or any(not math.isfinite(float(v)) for v in values) or values[0] > values[1]:
        reject('BOX_UNORDERED', 'Expected finite ordered bounds.', 'equilibriumReactions.bounds')
    return outward(Fraction(values[0]),False),outward(Fraction(values[1]),True)


def add(a, b):
    return outward(Fraction(a[0])+Fraction(b[0]), False), outward(Fraction(a[1])+Fraction(b[1]), True)


def negate(a):
    return -a[1], -a[0]


def multiply(a, b):
    values = [Fraction(x)*Fraction(y) for x in a for y in b]
    return outward(min(values), False), outward(max(values), True)


def divide(a, b):
    if b[0] <= 0 <= b[1]:
        reject('reaction_index_not_certified', 'An interval pivot includes zero.', 'equilibriumReactions.extentJacobian')
    return multiply(a, (outward(1/Fraction(b[1]), False), outward(1/Fraction(b[0]), True)))


def scalar(value):
    value = Fraction(str(value))
    return outward(value, False), outward(value, True)


def nonsingular(matrix):
    """Interval Gaussian elimination: every matrix in the box has nonzero pivots."""
    work = [[pair(v) for v in row] for row in matrix]
    determinant = (1., 1.)
    for k in range(len(work)):
        pivot = next((i for i in range(k,len(work)) if not work[i][k][0] <= 0 <= work[i][k][1]), None)
        if pivot is None:
            reject('reaction_index_not_certified', 'The whole-box extent Jacobian is not proved nonsingular.',
                   'equilibriumReactions.extentJacobian')
        if pivot != k:
            work[k], work[pivot] = work[pivot], work[k]
            determinant = negate(determinant)
        determinant = multiply(determinant, work[k][k])
        for i in range(k+1,len(work)):
            factor = divide(work[i][k], work[k][k])
            for j in range(k+1,len(work)):
                work[i][j] = add(work[i][j], negate(multiply(factor,work[k][j])))
            work[i][k] = (0.,0.)
    return determinant


def certify_extent(provider, nu, reference_box, extent_box, temperature, pressure, *, phase_id, standard_state,
                   _depth=0, _budget=None):
    # Shared closed split faces give an exact cover, with no omitted slivers.
    # Exhaustion is a rejection, never permission to use an uncertified leaf.
    if _budget is None:
        _budget = [4096]
    _budget[0] -= 1
    if _budget[0] < 0:
        reject('reaction_index_not_certified', 'Extent subdivision exhausted its 4096-box budget.', 'equilibriumReactions.extentJacobian')
    # Freeze this compiler increment's reviewed provider scope even while the
    # independent package team extends its public bounds implementation.
    if not isinstance(provider,chemistry.IdealGasPhase):
        reject('PROVIDER_UNSUPPORTED','This compiler increment admits certified IdealGasPhase extent blocks only.','equilibriumReactions.provider')
    rows = sp.Matrix([[sp.Rational(str(v)) for v in row] for row in nu])
    if any(not v.is_finite or sp.Rational(float(v))!=v for v in rows):
        reject('reaction_coefficient_not_representable','The public provider accepts binary64 coefficients; this exact rational cannot be transported without changing its value.','equilibriumReactions.stoichiometry')
    independent = list(rows.T.rref()[1])
    if not independent or len(extent_box) != len(independent) or len(reference_box) != rows.cols:
        reject('reaction_partition_invalid', 'Use one extent per independent reaction column.', 'equilibriumReactions.extents')
    N = rows[independent,:].T
    nbox = []
    for i, reference in enumerate(reference_box):
        value = pair(reference)
        for j, extent in enumerate(extent_box):
            value = add(value, multiply(scalar(N[i,j]),pair(extent)))
        nbox.append(list(value))
    box = {'T':list(pair(temperature)), 'P':list(pair(pressure)), 'n':nbox}
    try:
        bounds = chemistry.reaction_jacobian_bounds(provider, np.asarray(rows,dtype=float), box,
            phase_id=phase_id, standard_state=standard_state)
    except chemistry.ChemicalEquilibriumError as error:
        reject(error.code, str(error), 'equilibriumReactions.'+error.detail.get('path','provider'))
    if bounds.get('certified') is not True:
        diagnostic = bounds['diagnostics'][0]
        reject(diagnostic['code'],diagnostic['message'],'equilibriumReactions.'+diagnostic['path'])
    jacobian = []
    for row in independent:
        cells = []
        for j in range(N.cols):
            value = (0.,0.)
            for i in range(N.rows):
                value = add(value,multiply(pair(bounds['bounds']['dg_dn'][row][i]),scalar(N[i,j])))
            cells.append(list(value))
        jacobian.append(cells)
    try:
        determinant = nonsingular(jacobian)
    except LoweringError as error:
        if error.diagnostics[0]['code'] != 'reaction_index_not_certified':
            raise
        if _depth >= 20:
            reject('reaction_index_not_certified', 'Extent subdivision reached its depth limit 20 without proving every leaf '
                   'nonsingular; leaf box '+str([list(pair(p)) for p in extent_box])+'.', 'equilibriumReactions.extentJacobian')
        # Longest relative width, stable index tie-break, hence reproducible.
        widths = [(float(p[1])-float(p[0]))/max(1.,abs(float(p[0])),abs(float(p[1]))) for p in extent_box]
        axis = max(range(len(widths)), key=widths.__getitem__)
        lo, hi = pair(extent_box[axis])
        midpoint = lo/2 + hi/2
        if not lo < midpoint < hi:
            raise
        children = []
        for endpoints in ((lo,midpoint),(midpoint,hi)):
            child = [list(pair(p)) for p in extent_box]
            child[axis] = list(endpoints)
            children.append(certify_extent(provider,nu,reference_box,child,temperature,pressure,
                phase_id=phase_id,standard_state=standard_state,_depth=_depth+1,_budget=_budget))
        determinant = (min(c['determinantBounds'][0] for c in children),max(c['determinantBounds'][1] for c in children))
        # Publish enclosures of the certified leaves, not the failed coarse hull.
        jacobian = [[[min(c['jacobianBounds'][i][j][0] for c in children),
                      max(c['jacobianBounds'][i][j][1] for c in children)]
                     for j in range(N.cols)] for i in range(N.cols)]
        return {'format':'rage.reaction-extent-proof','version':1,'certified':True,'index':1,
                'independent':independent,'N':[[str(v) for v in row] for row in N.tolist()],
                'referenceBox':[list(pair(p)) for p in reference_box],
                'extentBox':[list(pair(p)) for p in extent_box], 'provider':bounds,
                'jacobianBounds':jacobian,'determinantBounds':list(determinant),
                'split':{'axis':axis,'point':midpoint,'children':children},
                'method':'Adaptive closed binary64-box bisection; every leaf has certified outward interval composition and nonzero Gaussian pivots. The split tree covers the declared box.'}
    return {'format':'rage.reaction-extent-proof','version':1,'certified':True,'index':1,
            'independent':independent,'N':[[str(v) for v in row] for row in N.tolist()],
            'referenceBox':[list(pair(p)) for p in reference_box],
            'extentBox':[list(pair(p)) for p in extent_box], 'provider':bounds,
            'jacobianBounds':jacobian,'determinantBounds':list(determinant),
            'method':'Outward binary64-box interval composition dg/dxi=(dg/dn)N and interval Gaussian elimination.'}
