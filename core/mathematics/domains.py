"""Explicit real-domain premises and conservative polynomial branch admission.

Physics and equipment do not participate in selecting a mathematical branch.
Unknown membership is a finding, never an implicit branch choice.
"""
from dataclasses import dataclass
from functools import lru_cache
import re
import sympy as sp
from .errors import MathematicsError
from .constants import si_magnitude


DOMAIN_SETS={
    'real':sp.S.Reals,
    'positive':sp.Interval.open(0,sp.oo),
    'nonnegative':sp.Interval(0,sp.oo),
    'negative':sp.Interval.open(-sp.oo,0),
    'nonpositive':sp.Interval(-sp.oo,0),
    'nonzero':sp.Union(sp.Interval.open(-sp.oo,0),sp.Interval.open(0,sp.oo)),
    'zero':sp.FiniteSet(0),
}
PREDICATES={name:getattr(sp.Q,name) for name in DOMAIN_SETS}


@lru_cache(maxsize=16384)
def _ask_exact(predicate, assumptions, context):
    # The complete assumption context is part of the proof key. In particular,
    # an answer under `assuming(...)` must never leak into a later request.
    from sympy.assumptions.assume import AssumptionsContext
    return sp.ask(predicate, assumptions, context=AssumptionsContext(context))


def ask_once(predicate, assumptions=True):
    from .preparation import enabled
    if not enabled():
        return sp.ask(predicate, assumptions)
    return _ask_exact(predicate, assumptions, frozenset(sp.assumptions.global_assumptions))


def exact_endpoint(value):
    if isinstance(value,sp.Rational):return value
    if not isinstance(value,str) or len(value)>80 or not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d{1,2})?(?:/[+-]?\d+)?',value.strip()):
        raise MathematicsError('Interval endpoints require finite exact numeric literals or rational numbers.')
    try:result=sp.Rational(value.strip())
    except (ValueError,TypeError,ZeroDivisionError) as error:
        raise MathematicsError('An interval endpoint is not a finite rational number.') from error
    if result.is_finite is not True:raise MathematicsError('Interval endpoints must be finite.')
    return result


@dataclass(frozen=True)
class DomainPremise:
    quantity: object
    domain: str
    lower: object = None
    upper: object = None
    lower_open: bool = False
    upper_open: bool = False
    scale: object = sp.S.One
    explicit_units: bool = False

    def __post_init__(self):
        if not isinstance(self.domain,str) or self.domain not in (*DOMAIN_SETS,'interval') or not isinstance(self.quantity,(sp.Symbol,sp.core.function.AppliedUndef)):
            raise MathematicsError('A domain premise requires a scalar quantity and a supported real domain.')
        if self.domain=='interval':
            if type(self.lower_open) is not bool or type(self.upper_open) is not bool:raise MathematicsError('Interval endpoint openness must be explicit booleans.')
            if self.allowed is sp.S.EmptySet:raise MathematicsError('The declared interval is empty or reversed.')

    @property
    def allowed(self):
        if self.domain=='interval':
            return sp.Interval(exact_endpoint(self.lower),exact_endpoint(self.upper),left_open=self.lower_open,right_open=self.upper_open)
        return DOMAIN_SETS[self.domain]

    @property
    def expression(self):
        return sp.Contains(self.quantity/self.scale if self.explicit_units else self.quantity,self.allowed,evaluate=False)

    @property
    def predicate(self):
        if self.domain!='interval':return PREDICATES[self.domain](self.quantity)
        return sp.And(sp.Q.real(self.quantity),*(predicate(self.quantity) for name,predicate in PREDICATES.items() if self.allowed.is_subset(DOMAIN_SETS[name]) is True))


def validate_domains(premises):
    """Reject empty same-quantity intersections and contradictions with typing."""
    intersections={}
    for premise in premises:
        previous=intersections.get(premise.quantity,sp.S.Reals)
        intersection=sp.Intersection(previous,premise.allowed)
        if intersection is sp.S.EmptySet or ask_once(premise.predicate) is False:
            raise MathematicsError('The declared real domains are contradictory or empty.')
        intersections[premise.quantity]=intersection
    return intersections


def singleton_substitutions(unknown,premises):
    scales={p.quantity:p.scale for p in premises}
    return {quantity:next(iter(allowed))*scales[quantity] for quantity,allowed in validate_domains(premises).items()
            if quantity!=unknown and isinstance(allowed,sp.FiniteSet) and len(allowed)==1}


def _unsatisfiable(expression,parameter):
    """Bounded exact univariate inequality proof; no numeric sampling."""
    if sp.count_ops(expression)>250:return None
    try:
        dnf=sp.to_dnf(sp.to_nnf(expression),simplify=False)
        clauses=dnf.args if isinstance(dnf,sp.Or) else (dnf,)
        if len(clauses)>16:return None
        for clause in clauses:
            if clause is sp.S.false:continue
            constraints=list(clause.args) if isinstance(clause,sp.And) else [clause]
            result=sp.reduce_inequalities(constraints,parameter)
            if result is not sp.S.false:return False
        return True
    except (NotImplementedError,ValueError,TypeError,sp.PolynomialError):
        return None


def membership(candidate,premise,parameter_sets,context):
    # All declared quantities use SI coordinates in the algebra. Unit factors
    # stay in graph expressions; only this membership proof projects to SI.
    candidate=si_magnitude(candidate)
    if premise.domain!='interval':
        known=sp.ask(PREDICATES[premise.domain](candidate),context)
        if known is not None:return known
    contained=premise.allowed.contains(candidate)
    if contained in (sp.S.true,sp.S.false):return bool(contained)
    if sp.ask(sp.Q.real(candidate),context) is not True:return None
    parameters=set(candidate.free_symbols)
    if len(parameters)!=1:return None
    parameter=next(iter(parameters))
    if parameter not in parameter_sets:return None
    allowed=parameter_sets[parameter].as_relational(parameter)
    if _unsatisfiable(sp.And(allowed,sp.Not(contained)),parameter) is True:return True
    if _unsatisfiable(sp.And(allowed,contained),parameter) is True:return False
    return None


def select_polynomial_branch(equation,unknown,premises):
    """Enumerate all degree-one/two roots, then prove domain membership.

    Leading-coefficient degeneracy remains an explicit excluded regime. Real
    parameter domains must settle membership for every candidate; unresolved
    parameter-dependent/coalescing regimes are not silently discarded.
    """
    parameter_sets=validate_domains(premises)
    target_domains=[p for p in premises if p.quantity==unknown]
    if not target_domains:
        raise MathematicsError('Branch selection requires a recorded domain for the selected quantity.')
    context=sp.And(*(p.predicate for p in premises if p.quantity!=unknown))
    target=sp.Dummy('branch_quantity',real=True)
    replacements=singleton_substitutions(unknown,premises)
    residual=(equation.lhs-equation.rhs).xreplace(replacements).xreplace({unknown:target})
    try:polynomial=sp.Poly(residual,target)
    except sp.PolynomialError as error:
        raise MathematicsError('Domain-guided inversion currently supports polynomial equations only.') from error
    if polynomial.degree()<=0:
        if residual==0:raise MathematicsError('This parameter case is an identity; the equation does not determine a unique quantity.')
        if sp.ask(sp.Q.nonzero(residual),context) is True:raise MathematicsError('This parameter case is inconsistent; the equation has no solutions.')
        raise MathematicsError('This parameter case has no target dependence and an unresolved residual constraint.')
    if polynomial.degree() not in (1,2):
        raise MathematicsError('Domain-guided inversion currently supports polynomial degree one or two.')
    if any(sp.ask(sp.Q.real(coefficient),context) is not True for coefficient in polynomial.all_coeffs()):
        raise MathematicsError('Declare sufficient real parameter domains before selecting a polynomial branch.')
    roots=sp.roots(polynomial.as_expr(),target)
    if sum(roots.values())!=polynomial.degree():
        raise MathematicsError('The complete polynomial branch set could not be established.')
    choices=[]
    for candidate in sorted(roots,key=sp.default_sort_key):
        memberships=[membership(candidate,p,parameter_sets,context) for p in target_domains]
        admitted=False if False in memberships else True if all(value is True for value in memberships) else None
        if admitted is None:
            raise MathematicsError('Branch membership is unresolved. Record stronger parameter domains; no branch was selected.')
        choices.append((candidate,admitted))
    accepted=[candidate for candidate,admitted in choices if admitted]
    if len(accepted)!=1:
        raise MathematicsError('The recorded domains admit '+str(len(accepted))+' branches; exactly one is required.')
    solution=accepted[0]
    if solution.has(sp.zoo,sp.nan,sp.oo,-sp.oo):
        raise MathematicsError('The selected branch is not finite.')
    if sp.simplify(residual.subs(target,solution))!=0:
        raise MathematicsError('The selected branch could not be verified against its input polynomial.')
    conditions=[]
    coefficient=polynomial.LC()
    if coefficient.is_nonzero is not True:conditions.append(sp.Ne(coefficient,0,evaluate=False))
    denominator=sp.denom(sp.factor(solution))
    if denominator.is_nonzero is not True:conditions.append(sp.Ne(denominator,0,evaluate=False))
    return solution,tuple(conditions),tuple((sp.Eq(unknown,candidate,evaluate=False),admitted) for candidate,admitted in choices)


# --- Typed spatial domain (PDE-1, 5 November 2026) -------------------------------
# A spatial domain is a chart, its active coordinates, one bounded interval per
# active coordinate and named boundary parts with an outward orientation. It
# carries no mesh and no discretization: Transform/Solve consume it later (F7).
#
# Validated scope (review P2, 6 November 2026): Cartesian x, y, z; cylindrical
# r and z; spherical r. Angular coordinates (phi, theta) cannot be active yet:
# exact multiples of pi as endpoints and the angular boundary/periodicity rules
# are deferred, and their declaration is rejected with a located message.

CHARTS={
    # Orthogonal charts; axis names match the matter producer's expansion.
    'cartesian':('x','y','z'),
    'cylindrical':('r','phi','z'),
    'spherical':('r','theta','phi'),
}
ANGULAR={'phi','theta'}
PART_NAME=re.compile(r'[A-Za-z][A-Za-z0-9_]{0,40}')


def chart_axes(chart):
    if chart not in CHARTS:raise MathematicsError('Select a supported orthogonal chart: cartesian, cylindrical or spherical.')
    return tuple(sp.Symbol(name,real=True) for name in CHARTS[chart])


def scale_factors(chart,axes=None):
    """Lamé factors h_i of the orthogonal chart (same metric as the matter producer)."""
    axes=axes or chart_axes(chart)
    if chart=='cartesian':return (sp.S.One,)*3
    if chart=='cylindrical':return (sp.S.One,axes[0],sp.S.One)
    return (sp.S.One,axes[0],axes[0]*sp.sin(axes[1]))


def admit_coordinate(chart,coordinate):
    """Located rejection of coordinates outside the chart or the validated scope."""
    axes={str(a):a for a in chart_axes(chart)}
    if not isinstance(coordinate,sp.Symbol) or axes.get(str(coordinate))!=coordinate:
        raise MathematicsError('Coordinate '+str(coordinate)+' does not belong to the '+chart+' chart ('+', '.join(axes)+').')
    if str(coordinate) in ANGULAR:
        raise MathematicsError('Angular coordinate '+str(coordinate)+' cannot be active yet: exact pi endpoints and angular boundary parts are deferred. Declare r'+(' and z' if chart=='cylindrical' else '')+' only.')


@dataclass(frozen=True)
class BoundaryPart:
    name: str
    coordinate: object
    end: str

    def __post_init__(self):
        if not isinstance(self.name,str) or not PART_NAME.fullmatch(self.name):
            raise MathematicsError('Name each boundary part with a short identifier.')
        if self.end not in ('lower','upper'):raise MathematicsError('A boundary part lies at the lower or upper end of one coordinate interval.')

    @property
    def sign(self):
        """Outward normal component along the coordinate's unit vector."""
        return -1 if self.end=='lower' else 1


@dataclass(frozen=True)
class SpatialDomain:
    chart: str
    coordinates: tuple
    intervals: tuple
    parts: tuple

    def __post_init__(self):
        if not self.coordinates or len(self.coordinates)>3 or len(set(self.coordinates))!=len(self.coordinates):
            raise MathematicsError('Select one to three distinct active coordinates.')
        for coordinate in self.coordinates:admit_coordinate(self.chart,coordinate)
        if len(self.intervals)!=len(self.coordinates):raise MathematicsError('Declare exactly one interval per active coordinate.')
        for coordinate,premise in zip(self.coordinates,self.intervals):
            if not isinstance(premise,DomainPremise) or premise.domain!='interval' or premise.quantity!=coordinate:
                raise MathematicsError('Each active coordinate needs its own bounded interval.')
            allowed=premise.allowed
            if not isinstance(allowed,sp.Interval) or allowed.measure.is_positive is not True:
                raise MathematicsError('The interval of '+str(coordinate)+' is empty, reversed or a single point.')
            if str(coordinate)=='r' and allowed.inf.is_negative:
                raise MathematicsError('A radial coordinate interval must be nonnegative.')
        names=[part.name for part in self.parts]
        if len(set(names))!=len(names):raise MathematicsError('Boundary part names must be distinct.')
        locations=set()
        for part in self.parts:
            if not isinstance(part,BoundaryPart) or part.coordinate not in self.coordinates:
                raise MathematicsError('Boundary part '+str(getattr(part,'name',part))+' must lie on an active coordinate of this domain.')
            location=(part.coordinate,part.end)
            if location in locations:raise MathematicsError('Boundary parts overlap at '+str(part.coordinate)+' '+part.end+' end; declare one part per end.')
            locations.add(location)
            if str(part.coordinate)=='r' and part.end=='lower' and self.endpoint(part)==0:
                raise MathematicsError('r = 0 is the coordinate axis or centre, not a boundary part.')

    @property
    def axes(self):
        """All chart axes; a volume integral binds every one of them."""
        return chart_axes(self.chart)

    def interval(self,coordinate):
        return self.intervals[self.coordinates.index(coordinate)].allowed

    def endpoint(self,part):
        """SI coordinate value of a boundary part."""
        allowed=self.interval(part.coordinate)
        return allowed.inf if part.end=='lower' else allowed.sup

    def normal(self,part):
        """Outward unit normal as components along the chart's unit vectors."""
        return {str(axis):(part.sign if axis==part.coordinate else 0) for axis in self.axes}

    def measure(self):
        """Measure of the domain per unit of the inactive coordinates (SI).

        dV is factored as (active density) x (inactive measure): a slab gives
        its length per unit cross-section, a cylindrical shell int r dr per
        radian and unit length (or int dz per unit cross-section when only z is
        active), a spherical shell int r^2 dr per steradian. The result never
        depends on an inactive coordinate.
        """
        active={str(c) for c in self.coordinates}
        r=self.axes[0]
        integrand={'cartesian':sp.S.One,
                   'cylindrical':r if 'r' in active else sp.S.One,
                   'spherical':r**2}[self.chart]
        for coordinate in self.coordinates:
            allowed=self.interval(coordinate)
            integrand=sp.integrate(integrand,(coordinate,allowed.inf,allowed.sup))
        return sp.simplify(integrand)

    @property
    def expression(self):
        return sp.And(*(premise.expression for premise in self.intervals),evaluate=False)

    def describe(self):
        labels={'cartesian':'Cartesian','cylindrical':'cylindrical','spherical':'spherical'}
        text=['Orthogonal '+labels[self.chart]+' chart; active coordinates '+', '.join(map(str,self.coordinates))]
        for part in self.parts:
            text.append('Boundary part '+part.name+': '+str(part.coordinate)+' = '+str(self.endpoint(part))+' (SI), outward normal '+('-' if part.sign<0 else '+')+'e_'+str(part.coordinate))
        return tuple(text)
