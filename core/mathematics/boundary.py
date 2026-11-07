"""Boundary restriction and typed initial/boundary conditions (PDE-2, 6 November 2026).

Every operation acts on a declared spatial domain (PDE-1) and one of its
oriented boundary parts. Results are recorded relations with their inputs,
before/after expressions, units and conditions; nothing is discretized here.
Solve keeps rejecting these rows with the located requires_discretization
diagnostic (PDE-0), because each contains a traced field.
"""
import sympy as sp
from core.unidades import unidad_SI,exact_conversion,ErrorUnidad
from .errors import MathematicsError as JournalError
from .operators import BoundaryTrace,NormalDerivative,NormalComponent,Gradient,Divergence


def boundary_part(graph,domain_id,name):
    """Located lookup of a declared boundary part: (domain, part, SI point, outward sign)."""
    if domain_id not in graph.spatial_domains:
        raise JournalError('Select a declared spatial domain; '+str(domain_id)+' is not one.')
    domain=graph.spatial_domains[domain_id]
    part=next((p for p in domain.parts if p.name==name),None)
    if part is None:
        declared=', '.join(p.name for p in domain.parts) or 'none'
        raise JournalError('Boundary part '+str(name)+' is not declared on spatial domain '+domain_id+' (declared parts: '+declared+').')
    return domain,part,domain.endpoint(part),sp.Integer(part.sign)


def location(domain_id,part,point):
    return ('Boundary part '+part.name+' of spatial domain '+domain_id+': '+str(part.coordinate)+' = '+str(point)
            +' (SI), outward normal '+('-' if part.sign<0 else '+')+'e_'+str(part.coordinate))


def _si(dimension):
    return unidad_SI({base:power for base,power in (dimension or {}).items() if power}) if dimension else '1'


def _same(expected,actual,what):
    if expected is not None and actual is not None and expected!=actual:
        raise JournalError(what+' has incompatible dimensions: expected '+_si(expected)+', got '+_si(actual)+'.')


def _vector_gradient(expression):
    """A gradient that is a vector term, not one already contracted by a divergence."""
    if isinstance(expression,Divergence):return False
    if isinstance(expression,Gradient):return True
    return any(_vector_gradient(argument) for argument in expression.args if isinstance(argument,sp.Basic))


def restrict_to_boundary(graph,key,source,domain_id,name,form,family):
    """Restrict an equation to a boundary part, by trace or by outward normal component.

    The flux form projects a vector relation on the outward normal: the gradient
    factor becomes the normal derivative, n.grad(u) = du/dn, and the remaining
    scalar factors are traced. Fourier's law restricted to a wall thus becomes
    n.q = -k du/dn there, ready to meet a prescribed flux condition.
    """
    domain,part,point,sign=boundary_part(graph,domain_id,name)
    equation=graph.nodes[source].equation
    if not isinstance(equation,sp.Equality):raise JournalError('Restrict an equation, not a domain condition.')
    coordinate=part.coordinate
    if coordinate not in equation.free_symbols:
        raise JournalError('The selected equation does not depend on '+str(coordinate)+'; its restriction to '+name+' is the equation itself.')
    conditions=[location(domain_id,part,point)]
    if form=='value':
        restrict=lambda side:BoundaryTrace(side,coordinate,point)  # noqa: E731
        title='Restrict the equation to boundary part '+name
    else:
        if not _vector_gradient(equation):
            raise JournalError('Projection on the outward normal of '+name+' needs a vector relation with a gradient (for example a constitutive flux law); the selected equation has none, so its normal component is missing.')
        restrict=lambda side:NormalComponent(side,coordinate,point,sign)  # noqa: E731
        title='Project the relation on the outward normal of boundary part '+name
        conditions.append('Normal derivative defined as n.grad(u) on '+name+'; scalar factors are traced')
    graph.add(key,restrict(equation.lhs),restrict(equation.rhs),title,'boundary_restriction',(source,domain_id),tuple(conditions),family,
              kind=graph.nodes[source].kind)
    return key


def expand_normal_derivative(graph,key,source,domain_id,family):
    """Replace each du/dn by its chart form, recording one identity per derivative.

    In an orthogonal chart n = sign e_c on a part c = point, so
    du/dn = sign (1/h_c) du/dc there; h_c = 1 for every admitted coordinate.
    """
    from .domains import scale_factors
    equation=graph.nodes[source].equation
    if not isinstance(equation,sp.Equality):raise JournalError('Expand an equation, not a domain condition.')
    if domain_id not in graph.spatial_domains:raise JournalError('Select a declared spatial domain; '+str(domain_id)+' is not one.')
    domain=graph.spatial_domains[domain_id]
    targets=sorted({node for node in sp.preorder_traversal(equation) if isinstance(node,NormalDerivative)},key=sp.default_sort_key)
    if not targets:raise JournalError('Select an equation that contains a normal derivative on a boundary part.')
    identities=[];replacements={}
    for index,target in enumerate(targets):
        field,coordinate,point,sign=target.args
        part=next((p for p in domain.parts if p.coordinate==coordinate and domain.endpoint(p)==point and p.sign==sign),None)
        if part is None:
            raise JournalError('The normal derivative at '+str(coordinate)+' = '+str(point)+' does not lie on a boundary part of spatial domain '+domain_id+'. Select the domain it was restricted on.')
        scale=BoundaryTrace(scale_factors(domain.chart)[domain.axes.index(coordinate)],coordinate,point)
        chart=sign/scale*BoundaryTrace(sp.Derivative(field,coordinate),coordinate,point)
        identity=key+'.identity.'+str(index+1)
        graph.add(identity,target,chart,'Outward normal derivative in the '+domain.chart+' chart','normal_derivative_identity',(domain_id,),
                  (location(domain_id,part,point),'Orthogonal chart: du/dn = n_c (1/h_c) du/dc with h_'+str(coordinate)+' = '+str(scale)),family,kind='definition')
        identities.append(identity);replacements[target]=chart
    graph.substitute(key,source,replacements,'Substitute the chart form of each normal derivative',inputs=tuple(identities))
    return key,tuple(identities)


def _field(quantities,identity,coordinate,what):
    if identity not in quantities:raise JournalError('Select a current quantity for the '+what+'.')
    field=quantities[identity]
    if not isinstance(field,sp.core.function.AppliedUndef) or coordinate not in field.args:
        raise JournalError('The '+what+' must be a field depending on '+str(coordinate)+'.')
    return field


def declare_condition(graph,key,op,quantities,units,parse,dimension,family):
    """Typed initial, Dirichlet, Neumann, Robin or continuity condition as a recorded relation."""
    kind=op['conditionKind'];form=op.get('form',{'neumann':'gradient','robin':'gradient'}.get(kind,'value'))
    source=op['sources'][0];domains=op['domains']
    for domain_id in domains:
        if domain_id not in graph.spatial_domains:raise JournalError('Select a declared spatial domain; '+domain_id+' is not one.')
    reasons=[op['reason']]
    def value(text,what,expected,forbidden=()):
        expression=parse(text,quantities,reasons,units)
        for symbol in forbidden:
            if symbol in expression.free_symbols:raise JournalError('The '+what+' cannot depend on '+str(symbol)+', the restricted coordinate.')
        _same(expected,dimension(expression,units),'The '+what)
        return expression
    def occurs(field):
        if not graph.nodes[source].equation.has(field):
            raise JournalError('The selected field '+str(field)+' does not occur in the selected equation; select the field equation this condition closes.')
    if kind=='initial':
        domain=graph.spatial_domains[domains[0]]
        if op['time'] not in quantities or not isinstance(quantities[op['time']],sp.Symbol):raise JournalError('Select the independent time coordinate of the initial condition.')
        time=quantities[op['time']]
        if time in domain.coordinates:raise JournalError('An initial condition restricts time; '+str(time)+' is a spatial coordinate of '+domains[0]+'.')
        _same({'T':1},dimension(time,units),'The time coordinate')
        field=_field(quantities,op['symbol'],time,'initial field');occurs(field)
        from .domains import exact_endpoint
        factor=sp.S.One
        if 'instantUnit' in op:
            try:conversion=exact_conversion(op['instantUnit'])
            except ErrorUnidad as error:raise JournalError('The instant unit has no supported exact conversion: '+str(error)) from error
            if conversion['afin'] or conversion['dimension']!={'T':1}:raise JournalError('The initial instant needs a time unit.')
            factor=sp.Rational(conversion['factor'])
        try:instant=exact_endpoint(op['instant'])*factor
        except JournalError:raise
        except Exception as error:raise JournalError('The initial instant: '+str(error)) from error
        prescribed=value(op['right'],'initial value',dimension(field,units),(time,))
        graph.add(key,BoundaryTrace(field,time,instant),prescribed,'Initial condition','initial_condition',(source,*domains),
                  (*reasons,'At '+str(time)+' = '+str(instant)+' (SI), at every point of spatial domain '+domains[0]),family,kind='constraint')
        return key
    domain,part,point,sign=boundary_part(graph,domains[0],op['boundary'])
    coordinate=part.coordinate
    field=_field(quantities,op['symbol'],coordinate,'boundary field');occurs(field)
    where=location(domains[0],part,point)
    u=dimension(field,units)
    gradient=None if u is None else {k:v for k,v in {**u,'L':u.get('L',0)-1}.items() if v}
    if kind=='dirichlet':
        left,right=BoundaryTrace(field,coordinate,point),value(op['right'],'prescribed boundary value',u,(coordinate,))
        title='Dirichlet condition on '+part.name
    elif kind=='neumann':
        if form=='gradient':
            left,right=NormalDerivative(field,coordinate,point,sign),value(op['right'],'prescribed normal derivative',gradient,(coordinate,))
        else:
            left,right=NormalComponent(field,coordinate,point,sign),value(op['right'],'prescribed normal flux',u,(coordinate,))
        title='Neumann condition on '+part.name
    elif kind=='robin':
        if form=='gradient':
            reference=value(op['right'],'reference value',u,(coordinate,))
            inverse_length=None if u is None else {'L':-1}
            coefficient=value(op['coefficient'],'Robin coefficient',inverse_length,(coordinate,))
            left,right=NormalDerivative(field,coordinate,point,sign),-coefficient*(BoundaryTrace(field,coordinate,point)-reference)
        else:
            potential=_field(quantities,op['potential'],coordinate,'Robin potential field')
            p=dimension(potential,units)
            reference=value(op['right'],'reference value',p,(coordinate,))
            ratio=None if u is None or p is None else {k:v for k,v in {b:u.get(b,0)-p.get(b,0) for b in {*u,*p}}.items() if v}
            coefficient=value(op['coefficient'],'Robin coefficient',ratio,(coordinate,))
            left,right=NormalComponent(field,coordinate,point,sign),coefficient*(BoundaryTrace(potential,coordinate,point)-reference)
        title='Robin condition on '+part.name
    else:
        neighbor_domain,neighbor,neighbor_point,neighbor_sign=boundary_part(graph,domains[1],op['neighborBoundary'])
        if neighbor.coordinate!=coordinate or neighbor_point!=point or neighbor_sign!=-sign:
            raise JournalError('Boundary parts '+part.name+' and '+neighbor.name+' do not coincide with opposite outward normals; continuity needs one shared interface.')
        other=_field(quantities,op['neighborSymbol'],coordinate,'neighbouring field')
        _same(u,dimension(other,units),'The neighbouring field')
        if form=='value':
            left,right=BoundaryTrace(field,coordinate,point),BoundaryTrace(other,coordinate,point)
            title='Continuity of value across '+part.name+' / '+neighbor.name
        else:
            left,right=NormalComponent(field,coordinate,point,sign),-NormalComponent(other,coordinate,point,neighbor_sign)
            title='Continuity of normal flux across '+part.name+' / '+neighbor.name
        where=where+'; '+location(domains[1],neighbor,neighbor_point)
    graph.add(key,left,right,title,'boundary_condition',(source,*domains),(*reasons,where),family,kind='constraint')
    return key
