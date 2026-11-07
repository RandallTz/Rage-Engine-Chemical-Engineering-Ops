"""Shared symbolic calculus operators; no physical-law or equipment selection."""
import sympy as sp


class Divergence(sp.Function):
    nargs=1
    @classmethod
    def eval(cls,expression):
        if expression==0:return sp.S.Zero
    def _latex(self,printer):return r'\nabla\!\cdot\left('+printer._print(self.args[0])+r'\right)'


class Gradient(sp.Function):
    nargs=1
    @classmethod
    def eval(cls,expression):
        if expression.is_number:return sp.S.Zero
    def _latex(self,printer):return r'\nabla\left('+printer._print(self.args[0])+r'\right)'


class VolumeIntegral(sp.Function):
    """Volume integral of a local density.

    The one-argument form keeps its historical binding of the coordinate
    names x, y, z and s. When a spatial domain is declared (PDE-1), the
    second argument is the tuple of chart axes the integral binds; only
    those coordinates are then removed from the free symbols.
    """
    nargs=(1,2)
    @property
    def free_symbols(self):
        # Integration binds spatial coordinates. The resulting inventory has
        # time dependence, rather than the local field's spatial arguments.
        if len(self.args)==2:return self.args[0].free_symbols-set(self.args[1])
        return {s for s in self.args[0].free_symbols if str(s) not in ('x','y','z','s')}
    def _eval_derivative(self,symbol):
        return sp.Derivative(self,symbol,evaluate=False)
    def _latex(self,printer):return r'\int_{V(t)} '+printer._print(self.args[0])+r'\,dV'
    @classmethod
    def eval(cls,expression,bound=None):
        extra=() if bound is None else (bound,)
        if bound is not None and (not isinstance(bound,sp.Tuple) or not bound or any(not isinstance(a,sp.Symbol) for a in bound)):
            raise TypeError('A volume integral binds a nonempty tuple of coordinate symbols.')
        if expression==0:return sp.S.Zero
        if expression.is_Add:return sp.Add(*(cls(term,*extra) for term in expression.args))
        coefficient,rest=expression.as_coeff_Mul()
        if coefficient!=1:return coefficient*cls(rest,*extra)


class BoundaryFlux(sp.Function):
    nargs=1
    def _latex(self,printer):return r'\oint_{\partial V(t)} \left('+printer._print(self.args[0])+r'\right)\!\cdot\mathbf n\,dA'
    @classmethod
    def eval(cls,expression):
        if expression==0:return sp.S.Zero
        if expression.is_Add:return sp.Add(*(cls(term) for term in expression.args))
        coefficient,rest=expression.as_coeff_Mul()
        if coefficient!=1:return coefficient*cls(rest)


class StateDifferential(sp.Function):
    nargs=1
    def _latex(self,printer):return r'\mathrm d\!\left('+printer._print(self.args[0])+r'\right)'



# --- Boundary restriction operators (PDE-2, 6 November 2026) -------------------
# A boundary part of a declared spatial domain (PDE-1) is the level set
# coordinate = point (SI) with an outward unit normal sign*e_coordinate. These
# operators restrict expressions to that set; they never discretize. They are
# pointwise, so they distribute over sums and products, pass through factors
# independent of the restricted coordinate, and commute with derivatives along
# the other coordinates.

def _boundary_arguments(coordinate,point,sign=None):
    if not isinstance(coordinate,sp.Symbol):raise TypeError('A boundary restriction binds one coordinate symbol.')
    point=sp.sympify(point)
    if not point.is_number or point.is_real is not True:raise TypeError('A boundary restriction needs a real numeric SI coordinate value.')
    if sign is not None and sign not in (sp.S.One,sp.S.NegativeOne):raise TypeError('The outward normal sign is +1 or -1.')


def _depends_on(expression,coordinate):
    return coordinate in expression.free_symbols


class BoundaryTrace(sp.Function):
    """Restriction of a scalar expression to coordinate = point.

    A field u(x,t) traced on x = 0 is kept as the typed operator, not as u(0,t),
    so the restricted field keeps its identity for substitution and detection.
    The same operator restricts in time for initial conditions.
    """
    nargs=3

    @classmethod
    def eval(cls,expression,coordinate,point):
        _boundary_arguments(coordinate,point)
        if not _depends_on(expression,coordinate):return expression
        if expression==coordinate:return point
        if expression.is_Add:return sp.Add(*(cls(term,coordinate,point) for term in expression.args))
        if expression.is_Mul:return sp.Mul(*(cls(term,coordinate,point) for term in expression.args))
        if expression.is_Pow and not _depends_on(expression.exp,coordinate):return cls(expression.base,coordinate,point)**expression.exp
        if expression.func in (sp.exp,sp.log,sp.sin,sp.cos,sp.tan,sp.Abs):
            return expression.func(*(cls(argument,coordinate,point) for argument in expression.args))
        return None

    @property
    def free_symbols(self):
        expression,coordinate,point=self.args
        return (expression.free_symbols-{coordinate})|point.free_symbols

    def _eval_derivative(self,symbol):
        expression,coordinate,point=self.args
        if symbol==coordinate:return sp.S.Zero
        return type(self)(sp.diff(expression,symbol),coordinate,point)

    def _latex(self,printer):
        expression,coordinate,point=self.args
        return r'\left.'+printer._print(expression)+r'\right|_{'+printer._print(coordinate)+'='+printer._print(point)+'}'


class NormalDerivative(sp.Function):
    """Outward normal derivative n.grad(u) on the boundary part coordinate = point.

    Arguments: field, coordinate, point (SI) and the outward normal sign. Only
    factors independent of the coordinate leave the operator; its expansion
    in the chart is a separate recorded identity (expand_normal_derivative).
    """
    nargs=4

    @classmethod
    def eval(cls,expression,coordinate,point,sign):
        _boundary_arguments(coordinate,point,sign)
        if not _depends_on(expression,coordinate):return sp.S.Zero
        if expression.is_Add:return sp.Add(*(cls(term,coordinate,point,sign) for term in expression.args))
        if expression.is_Mul:
            constant,dependent=expression.as_independent(coordinate,as_Add=False)
            if constant!=1:return constant*cls(dependent,coordinate,point,sign)
        return None

    @property
    def free_symbols(self):
        expression,coordinate,point,sign=self.args
        return (expression.free_symbols-{coordinate})|point.free_symbols

    def _eval_derivative(self,symbol):
        expression,coordinate,point,sign=self.args
        if symbol==coordinate:return sp.S.Zero
        return type(self)(sp.diff(expression,symbol),coordinate,point,sign)

    def _latex(self,printer):
        expression,coordinate,point,sign=self.args
        return r'\left.\frac{\partial '+printer.parenthesize(expression,1000)+r'}{\partial n}\right|_{'+printer._print(coordinate)+'='+printer._print(point)+'}'


class NormalComponent(sp.Function):
    """Outward normal component n.v of a vector expression on a boundary part.

    n.(a grad u) = trace(a) du/dn: the gradient factor is the vector and the
    other factors are traced scalars. A vector quantity without a gradient (a
    flux field) keeps its typed normal component for later substitution.
    """
    nargs=4

    @classmethod
    def eval(cls,expression,coordinate,point,sign):
        _boundary_arguments(coordinate,point,sign)
        if expression==0:return sp.S.Zero
        if expression.is_Add:return sp.Add(*(cls(term,coordinate,point,sign) for term in expression.args))
        if isinstance(expression,Gradient):return NormalDerivative(expression.args[0],coordinate,point,sign)
        if expression.is_Mul:
            gradients=[factor for factor in expression.args if isinstance(factor,Gradient)]
            if len(gradients)==1:
                scalar=sp.Mul(*(factor for factor in expression.args if factor is not gradients[0]))
                return BoundaryTrace(scalar,coordinate,point)*NormalDerivative(gradients[0].args[0],coordinate,point,sign)
            constant,dependent=expression.as_independent(coordinate,as_Add=False)
            if constant!=1 and not gradients:return constant*cls(dependent,coordinate,point,sign)
        return None

    @property
    def free_symbols(self):
        expression,coordinate,point,sign=self.args
        return (expression.free_symbols-{coordinate})|point.free_symbols

    def _eval_derivative(self,symbol):
        expression,coordinate,point,sign=self.args
        if symbol==coordinate:return sp.S.Zero
        return type(self)(sp.diff(expression,symbol),coordinate,point,sign)

    def _latex(self,printer):
        expression,coordinate,point,sign=self.args
        return r'\left.\mathbf n\cdot'+printer.parenthesize(expression,1000)+r'\right|_{'+printer._print(coordinate)+'='+printer._print(point)+'}'


BOUNDARY_OPERATORS=(BoundaryTrace,NormalDerivative,NormalComponent)


# --- Spatial content detection (PDE-0, 5 November 2026) -------------------------
# A field equation keeps spatial coordinates as arguments, derivatives with
# respect to them, or unexpanded divergence/gradient operators. Integrated
# operators (volume integrals, boundary fluxes) bind their coordinates and are
# not spatial content. Detection is purely structural; it never discretizes.

def is_coordinate(symbol,time=None,declared=()):
    """A spatial coordinate: a chart axis name, the path coordinate s, or a declared axis.

    Names may carry the producers' owner suffix (x__v1). Scalar quantities such
    as a temperature T or a parameter alpha are never coordinates, even when a
    declared function depends on them (review P1, 6 November 2026).
    """
    if not isinstance(symbol,sp.Symbol) or symbol==time:return False
    if symbol in declared:return True
    from .domains import CHARTS
    return str(symbol).split('__')[0] in {*(axis for axes in CHARTS.values() for axis in axes),'s'}


def field_coordinates(quantity,time=None,declared=()):
    """Spatial coordinates among a field's arguments (never the selected time)."""
    if not isinstance(quantity,sp.core.function.AppliedUndef):return ()
    return tuple(a for a in quantity.args if is_coordinate(a,time,declared))


def spatial_content(expression,time=None,declared=()):
    """Fields, coordinates and operators that require spatial discretization."""
    fields={};coordinates=set();operators=set();derivatives=False
    def visit(node):
        nonlocal derivatives
        if isinstance(node,(VolumeIntegral,BoundaryFlux)):return
        if isinstance(node,(Divergence,Gradient,*BOUNDARY_OPERATORS)):operators.add(type(node).__name__)
        if isinstance(node,sp.Derivative):
            spatial=[v for v,_ in node.variable_count if is_coordinate(v,time,declared)]
            if spatial:derivatives=True;coordinates.update(spatial)
        found=field_coordinates(node,time,declared)
        if found:fields[node]=found;coordinates.update(found)
        for argument in node.args:
            if isinstance(argument,sp.Basic):visit(argument)
    visit(expression)
    return {'fields':tuple(sorted(fields,key=sp.default_sort_key)),
            'coordinates':tuple(sorted(coordinates,key=sp.default_sort_key)),
            'operators':tuple(sorted(operators)),'derivatives':derivatives}


def requires_discretization(graph,rows,time=None):
    """Located findings for selected rows whose equations are spatial.

    ``rows`` are equation identities of the selected formulation. Each finding
    names the row, its spatial coordinates, fields and unexpanded operators.
    Rows absent from the graph are left to the caller's own admission checks.
    """
    declared=tuple(axis for domain in getattr(graph,'spatial_domains',{}).values() for axis in domain.axes)
    findings=[]
    for equation_id in rows:
        node=graph.nodes.get(equation_id)
        if node is None or not isinstance(node.equation,sp.Equality):continue
        content=spatial_content(node.equation,time,declared)
        if content['coordinates'] or content['operators']:
            findings.append({'equationId':equation_id,
                             'coordinates':[str(c) for c in content['coordinates']],
                             'fields':[str(f) for f in content['fields']],
                             'operators':list(content['operators'])})
    return findings


def discretization_message(finding):
    subject=', '.join(finding.get('fields') or [])
    coordinates=', '.join(finding.get('coordinates') or [])
    operators=', '.join(finding.get('operators') or [])
    text=(subject or 'The selected equation')+(' depend on ' if len(finding.get('fields') or [])>1 else ' depends on ')+(coordinates or 'a spatial chart')
    if operators:text+=' through unexpanded '+operators
    return text+'; spatial discretization is deferred (F7). Solve executes time-only states; select Transform rows without spatial fields.'
