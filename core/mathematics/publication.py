"""PDE-4: publication of spatial models and the graph-to-``matematico`` adapter.

A model whose selected rows keep spatial terms is published as such: a block
that names the declared domains, the field equations, the typed conditions and
the located ``requires_discretization`` findings, and that is handed to
Transform. Solve rejects it (PDE-0); nothing is discretized here (F7).

The adapter translates the replayed equation graph into the nondimensional
``matematico`` v2 model (symbols, expression trees, domains and located
conditions) that the nondimensionalization core already reads. It performs no
algebra: every expression is a structural image of a graph row, boundary
restrictions become the v2 ``ubicacion`` of the condition, and anything the v2
document cannot express is a located rejection, never a silent drop.
"""
import sympy as sp
from sympy.core.function import AppliedUndef

from .dimensions import dimension
from .errors import MathematicsError
from .operators import (BOUNDARY_OPERATORS, BoundaryFlux, BoundaryTrace, Divergence, Gradient, NormalComponent,
                        NormalDerivative, VolumeIntegral, discretization_message, field_coordinates, is_coordinate,
                        requires_discretization, spatial_content)

FORMAT = 'rage.spatial-publication'
FUNCTIONS = {sp.exp: 'exp', sp.log: 'log', sp.sin: 'sin', sp.cos: 'cos', sp.tan: 'tan', sp.tanh: 'tanh', sp.sinh: 'sinh',
             sp.cosh: 'cosh', sp.atan: 'atan', sp.erf: 'erf', sp.Abs: 'abs'}
FINAL_TIME = 't_end'


class PublicationError(MathematicsError):
    """The graph row cannot be expressed in the v2 document.

    Carries a stable ``code`` and the ``equationId`` of the row (``None`` for model-wide limits);
    ``str(error)`` is the located message. The adapter fails with this error rather than
    publishing a problem different from the equation graph.
    """

    def __init__(self, message, code='unrepresentable', equation_id=None):
        super().__init__(message)
        self.code = code
        self.equation_id = equation_id

    def finding(self):
        return {'code': self.code, 'message': str(self), 'equationId': self.equation_id}


def _number(value):
    value = sp.Rational(repr(float(value))) if value.is_Float else value
    if value.is_Integer:
        return {'tipo': 'numero', 'valor': int(value)}
    if value.is_Rational:
        return {'tipo': 'cociente', 'numerador': {'tipo': 'numero', 'valor': int(value.p)},
                'denominador': {'tipo': 'numero', 'valor': int(value.q)}}
    raise PublicationError('The number ' + str(value) + ' has no exact rational form in the v2 document.', 'inexact_constant')


def _dimension(expression, units):
    try:
        found = dimension(expression, units)
    except MathematicsError:
        return None
    if found is None:
        return None
    return {base: {'n': int(sp.Rational(power).p), 'd': int(sp.Rational(power).q)} for base, power in found.items() if power}


class _Translator:
    """Structural image of graph expressions; boundary restrictions are recorded, not translated."""

    def __init__(self, equation_id, charts=(), time=None, declared=()):
        self.equation_id = equation_id
        self.charts = charts
        self.time = time
        self.declared = declared
        self.locations = []
        self.kinds = set()
        self.calls = {}
        self.divergence = []

    def fail(self, message, code='unrepresentable'):
        raise PublicationError(self.equation_id + ': ' + message, code, self.equation_id)

    def is_field(self, atom):
        return all(isinstance(a, sp.Symbol) and (a == self.time or is_coordinate(a, self.time, self.declared)) for a in atom.args)

    def symbol(self, name):
        return {'tipo': 'simbolo', 'id': name}

    def tree(self, e):
        if e.is_number:
            if e.is_Rational or e.is_Float:
                return _number(e)
            self.fail('the constant ' + str(e) + ' has no exact rational form in the v2 document.', 'inexact_constant')
        if isinstance(e, sp.Symbol):
            return self.symbol(str(e))
        if isinstance(e, AppliedUndef):
            if self.is_field(e):
                return self.symbol(e.func.__name__)
            self.calls[e.func.__name__] = e
            return {'tipo': 'llamada', 'funcionId': e.func.__name__, 'argumentos': [self.tree(a) for a in e.args]}
        if e.is_Add:
            return {'tipo': 'suma', 'argumentos': [self.tree(a) for a in e.args]}
        if e.is_Mul:
            numerator = [f for f in e.args if not (f.is_Pow and f.exp.is_negative)]
            denominator = [f.base ** (-f.exp) for f in e.args if f.is_Pow and f.exp.is_negative]
            top = self.product(numerator) if numerator else {'tipo': 'numero', 'valor': 1}
            if denominator:
                return {'tipo': 'cociente', 'numerador': top, 'denominador': self.product(denominator)}
            return top
        if e.is_Pow:
            if e.exp.is_negative:
                return {'tipo': 'cociente', 'numerador': {'tipo': 'numero', 'valor': 1}, 'denominador': self.tree(e.base ** (-e.exp))}
            return {'tipo': 'potencia', 'base': self.tree(e.base), 'exponente': self.tree(e.exp)}
        if e.func in FUNCTIONS:
            return {'tipo': 'funcion', 'nombre': FUNCTIONS[e.func], 'argumentos': [self.tree(a) for a in e.args]}
        if isinstance(e, sp.Derivative):
            result = self.tree(e.expr)
            for variable, order in e.variable_count:
                result = {'tipo': 'derivada', 'expresion': result, 'respecto': str(variable), 'orden': int(order)}
            return result
        if isinstance(e, (Divergence, Gradient)):
            inner = e.args[0]
            coordinates = [str(c) for c in spatial_content(inner, None, tuple(a for a in inner.free_symbols if is_coordinate(a)))['coordinates']]
            fields = [c for f in inner.atoms(AppliedUndef) for c in (str(a) for a in field_coordinates(f))]
            ordered = sorted({*coordinates, *fields})
            name = type(e).__name__.lower()
            if not ordered:
                self.fail('the ' + name + ' acts on an expression without spatial coordinates.')
            if not any(chart == 'cartesian' and names == set(ordered) for chart, names in self.charts):
                self.fail('the ' + name + ' over (' + ', '.join(ordered) + ') is published only for a declared Cartesian domain on exactly those coordinates; '
                          'expand the spatial operators in the declared chart (expand_spatial_operators) before publishing.', 'non_cartesian_operator')
            if isinstance(e, Divergence):
                if not inner.has(Gradient):
                    self.fail('the divergence does not act on a gradient flux; close the flux with its recorded constitutive law (declare_fourier_law) before publishing.', 'unclosed_flux')
                self.divergence.append(ordered)
                try:
                    inside = self.tree(inner)
                finally:
                    self.divergence.pop()
            else:
                if not self.divergence or self.divergence[-1] != ordered:
                    self.fail('a gradient is published only inside a divergence over the same coordinates; expand the spatial operators first.', 'unclosed_flux')
                inside = self.tree(inner)
            self.kinds.add(type(e).__name__)
            return {'tipo': 'divergencia' if isinstance(e, Divergence) else 'gradiente', 'expresion': inside, 'coordenadas': ordered}
        if isinstance(e, BoundaryTrace):
            inner, coordinate, point = e.args
            self.locations.append((coordinate, point))
            self.kinds.add('DerivativeTrace' if any(coordinate in d.variables for d in inner.atoms(sp.Derivative)) else 'ValueTrace')
            return self.tree(inner)
        if isinstance(e, NormalDerivative):
            inner, coordinate, point, sign = e.args
            self.locations.append((coordinate, point))
            self.kinds.add('NormalDerivative')
            derivative = {'tipo': 'derivada', 'expresion': self.tree(inner), 'respecto': str(coordinate), 'orden': 1}
            if sign == 1:
                return derivative
            return {'tipo': 'producto', 'argumentos': [{'tipo': 'numero', 'valor': -1}, derivative]}
        if isinstance(e, NormalComponent):
            self.fail('a normal flux component is still untyped; close the flux (substitute its recorded constitutive law and expand the normal derivative) before publishing.', 'untyped_normal_flux')
        if isinstance(e, (VolumeIntegral, BoundaryFlux)):
            self.fail('integral balances are not spatial fields; publish the local form.', 'integral_balance')
        if isinstance(e, sp.Subs):
            self.fail('an unevaluated substitution (Subs) has no v2 image.', 'unevaluated_substitution')
        self.fail('the operator ' + type(e).__name__ + ' has no v2 image.', 'unsupported_operator')

    def product(self, factors):
        if len(factors) == 1:
            return self.tree(factors[0])
        return {'tipo': 'producto', 'argumentos': [self.tree(f) for f in factors]}


def _time_symbol(graph, rows, units, time):
    if time is not None:
        return time
    axes = {a for domain in graph.spatial_domains.values() for a in domain.axes}
    candidates = set()
    for row in rows:
        for field in graph.nodes[row].equation.atoms(AppliedUndef):
            for argument in field.args:
                if isinstance(argument, sp.Symbol) and argument not in axes and not is_coordinate(argument) and (_dimension(argument, units) or {}).get('T', {}).get('n') == 1:
                    candidates.add(argument)
    if not candidates:
        # No unit identifies the time: a symbol argument that accompanies a coordinate in a field is the only candidate left.
        for row in rows:
            for field in graph.nodes[row].equation.atoms(AppliedUndef):
                if any(is_coordinate(a, None, axes) for a in field.args):
                    candidates.update(a for a in field.args if isinstance(a, sp.Symbol) and a not in axes and not is_coordinate(a))
    if len(candidates) > 1:
        raise PublicationError('Several time-like arguments occur (' + ', '.join(sorted(map(str, candidates))) + '); select the time symbol.', 'ambiguous_time')
    return next(iter(candidates), None)


def _is_condition(graph, key):
    node = graph.nodes[key]
    return node.rule in ('initial_condition', 'boundary_condition') or any(node.equation.has(op) for op in BOUNDARY_OPERATORS)


def _traced(side):
    """Fields restricted to a boundary on one side of a condition."""
    return {a.func for t in side.atoms(BoundaryTrace, NormalDerivative) for a in t.args[0].atoms(AppliedUndef)}


def _end(domain, coordinate, point):
    interval = domain.interval(coordinate)
    if point == interval.inf:
        return 'desde'
    if point == interval.sup:
        return 'hasta'
    return None


def to_matematico(graph, rows, units, time=None, model_id='spatial-model', revision=1, values=None):
    """v2 ``matematico`` model for the selected spatial rows (field equations and conditions).

    Raises ``PublicationError`` located at the offending row. Rows without
    spatial content are ignored: they stay with the nonspatial path.

    The v2 document has no unit literals, so a nonzero domain endpoint becomes a
    declared constant parameter of the coordinate's dimension (``x_upper``);
    its exact SI value is written into ``values`` (when given) as
    ``{symbol: {'value': exact string, 'unit': unit}}``.
    """
    values = {} if values is None else values
    declared = tuple(a for domain in graph.spatial_domains.values() for a in domain.axes)
    chosen = [r for r in rows if r in graph.nodes and isinstance(graph.nodes[r].equation, sp.Equality)]
    spatial = [r for r in chosen if (lambda c: bool(c['coordinates'] or c['operators']))(spatial_content(graph.nodes[r].equation, time, declared))]
    if not spatial:
        raise PublicationError('No selected row has spatial content; nothing to publish.', 'no_spatial_content')
    time = _time_symbol(graph, spatial, units, time)
    fields, parameters, coordinates, calls = {}, {}, {}, {}
    probe = _Translator('', (), time, declared)
    for row in spatial:
        for atom in graph.nodes[row].equation.atoms(AppliedUndef):
            name = atom.func.__name__
            if not probe.is_field(atom):
                if name in fields or (name in calls and len(calls[name].args) != len(atom.args)):
                    raise PublicationError(row + ': the name ' + name + ' is used both as a field and as a function, or with different numbers of arguments.', 'name_clash', row)
                calls[name] = calls.get(name, atom)
                continue
            if name in calls:
                raise PublicationError(row + ': the name ' + name + ' is used both as a field and as a function.', 'name_clash', row)
            if name in fields and fields[name].args != atom.args:
                raise PublicationError(row + ': the field ' + name + ' occurs with different arguments (' + str(fields[name]) + ' and ' + str(atom) + '); restate it on one set of coordinates first.', 'field_arguments', row)
            fields[name] = atom
        equation = graph.nodes[row].equation
        for symbol in equation.free_symbols:
            if symbol == time:
                continue
            if is_coordinate(symbol, time, declared):
                coordinates[str(symbol)] = symbol
        for atom in equation.atoms(AppliedUndef):
            for argument in atom.args if probe.is_field(atom) else ():
                if isinstance(argument, sp.Symbol) and argument != time and is_coordinate(argument, time, declared):
                    coordinates[str(argument)] = argument
        for atom in equation.atoms(BoundaryTrace, NormalDerivative):
            if isinstance(atom.args[1], sp.Symbol) and atom.args[1] != time:
                coordinates[str(atom.args[1])] = atom.args[1]
        for symbol in equation.free_symbols:
            if symbol != time and str(symbol) not in coordinates and not is_coordinate(symbol, time, declared):
                parameters[str(symbol)] = symbol
    for atom in (*fields.values(), *calls.values()):
        if atom.func.__name__ in parameters:
            raise PublicationError('The name ' + atom.func.__name__ + ' is both a field or function and a parameter.', 'name_clash')
    positive = set()
    for node in graph.nodes.values():
        for predicate in node.predicates:
            if isinstance(predicate, sp.StrictGreaterThan) and predicate.rhs == 0 and isinstance(predicate.lhs, sp.Symbol):
                positive.add(str(predicate.lhs))
    variables = {**coordinates, **({str(time): time} if time is not None else {})}
    symbols = []
    for name, symbol in variables.items():
        symbols.append({'id': name, 'nombre': name, 'rol': 'tiempo' if symbol == time else 'coordenada', 'dimension': _dimension(symbol, units),
                        'unidad': units.get(symbol), 'constante': False, 'dependeDe': [], 'signo': 'desconocido'})
    for name, atom in fields.items():
        arguments = [str(a) for a in atom.args if str(a) in variables]
        symbols.append({'id': name, 'nombre': name, 'rol': 'campo', 'dimension': _dimension(atom, units), 'unidad': units.get(atom),
                        'constante': False, 'dependeDe': arguments, 'signo': 'positivo' if name in positive else 'desconocido'})
    for name, symbol in parameters.items():
        symbols.append({'id': name, 'nombre': name, 'rol': 'parametro', 'dimension': _dimension(symbol, units), 'unidad': units.get(symbol),
                        'constante': True, 'dependeDe': [], 'signo': 'positivo' if name in positive else 'desconocido'})
    identifiers = {s['id'] for s in symbols}
    functions = []
    for name, atom in calls.items():
        if name in identifiers:
            raise PublicationError('The name ' + name + ' is both a function and a symbol.', 'name_clash')
        inputs = [_dimension(a, units) for a in atom.args]
        output = _dimension(atom, units)
        if output is None or any(d is None for d in inputs):
            raise PublicationError('The function ' + str(atom) + ' has no known dimension for its arguments or its value; declare their units.', 'unknown_dimension')
        functions.append({'id': name, 'nombre': name, 'entradas': inputs, 'salida': output, 'dependeDe': []})
    domains = []
    domain_of = {}
    endpoint_symbols = []

    def endpoint(coordinate, end, value):
        if value == 0:
            return {'tipo': 'numero', 'valor': 0}
        name = str(coordinate) + '_' + end
        if name in identifiers or name in values:
            raise PublicationError('The endpoint name ' + name + ' is already used; several domains on one coordinate (composite media) are not published yet.', 'composite_media')
        values[name] = {'value': str(value), 'unit': units.get(coordinate)}
        endpoint_symbols.append({'id': name, 'nombre': name, 'rol': 'parametro', 'dimension': _dimension(coordinate, units), 'unidad': units.get(coordinate),
                                 'constante': True, 'dependeDe': [], 'signo': 'positivo' if value > 0 else 'desconocido'})
        return {'tipo': 'simbolo', 'id': name}
    for domain_id, domain in graph.spatial_domains.items():
        for coordinate in domain.coordinates:
            if str(coordinate) not in coordinates:
                continue
            if coordinate in domain_of:
                raise PublicationError('The coordinate ' + str(coordinate) + ' belongs to the domains ' + domain_of[coordinate][0].rsplit('.', 1)[0] + ' and ' + domain_id
                                       + '; several domains on one coordinate (composite media) are not published yet.', 'composite_media')
            key = domain_id + '.' + str(coordinate)
            interval = domain.interval(coordinate)
            domains.append({'id': key, 'variableId': str(coordinate), 'desde': endpoint(coordinate, 'lower', interval.inf), 'hasta': endpoint(coordinate, 'upper', interval.sup)})
            domain_of[coordinate] = (key, domain)
    equations, conditions = [], []
    time_domain = None
    charts = [(domain.chart, {str(c) for c in domain.coordinates}) for domain in graph.spatial_domains.values()]
    for row in spatial:
        translator = _Translator(row, charts, time, declared)
        node = graph.nodes[row]
        sides = {'id': row, 'izquierda': translator.tree(node.equation.lhs), 'derecha': translator.tree(node.equation.rhs)}
        if not _is_condition(graph, row):
            if translator.locations:
                raise PublicationError(row + ': a boundary restriction occurs outside a declared condition.', 'boundary_outside_condition', row)
            equations.append(sides)
            continue
        if not translator.locations:
            raise PublicationError(row + ': a condition without a boundary restriction cannot be located.', 'condition_unlocated', row)
        located = set(translator.locations)
        if len(located) != 1:
            raise PublicationError(row + ': the condition mixes several boundary locations (' + ', '.join(str(c) + '=' + str(p) for c, p in sorted(located, key=str)) + ').', 'condition_mixed_locations', row)
        coordinate, point = next(iter(located))
        left, right = _traced(node.equation.lhs), _traced(node.equation.rhs)
        if left and right and not (left & right):
            raise PublicationError(row + ': continuity across an interface (traces of different fields on both sides) is not published yet (composite media).', 'composite_media', row)
        if coordinate == time:
            if time_domain is None:
                time_domain = {'id': 'time', 'variableId': str(time), 'desde': endpoint(time, 'start', point), 'hasta': translator.symbol(FINAL_TIME)}
                time_point = point
                domains.append(time_domain)
            elif point != time_point:
                raise PublicationError(row + ': initial conditions at different instants share one time domain.', 'initial_instants', row)
            kind, domain_key, end = 'inicial', 'time', 'desde'
        else:
            if coordinate not in domain_of:
                raise PublicationError(row + ': the boundary coordinate ' + str(coordinate) + ' has no declared spatial domain.', 'no_domain', row)
            domain_key, domain = domain_of[coordinate]
            end = _end(domain, coordinate, point)
            if end is None:
                raise PublicationError(row + ': the boundary location ' + str(coordinate) + ' = ' + str(point) + ' is not an end of its declared interval.', 'boundary_not_end', row)
            if translator.kinds & {'NormalDerivative', 'DerivativeTrace'}:
                kind = 'mixta' if 'ValueTrace' in translator.kinds else 'flujo'
            else:
                kind = 'dirichlet'
        conditions.append({'id': row + '.condition', 'tipo': kind, 'dominioId': domain_key, 'ecuacion': sides,
                           'ubicacion': {'variableId': str(coordinate), 'extremo': end}})
    if time_domain is not None:
        if FINAL_TIME in identifiers:
            raise PublicationError('The name ' + FINAL_TIME + ' is reserved for the final time of the time domain.', 'reserved_name')
        symbols.append({'id': FINAL_TIME, 'nombre': FINAL_TIME, 'rol': 'parametro', 'dimension': {'T': {'n': 1, 'd': 1}}, 'unidad': 's',
                        'constante': True, 'dependeDe': [], 'signo': 'positivo'})
    symbols.extend(endpoint_symbols)
    model = {'id': model_id, 'revision': revision, 'simbolos': symbols, 'funciones': functions, 'ecuaciones': equations, 'dominios': domains, 'condiciones': conditions}
    from core.adimensionalizacion.lector import ErrorContrato, leer_modelo
    try:
        leer_modelo(model, 'matematico', version=2)
    except ErrorContrato as error:
        raise PublicationError('The translated model is not a valid v2 document: ' + str(error), 'invalid_v2') from error
    return model


ANCHORING_RULES = ('initial_condition', 'boundary_condition', 'spatial_domain')
SKIPPED_RULES = ('assumption', 'spatial_domain', 'spatial_interval', 'domain_declaration')


def _consumed_by(graph, rows):
    """Nodes that the given rows consume.

    A declared condition or domain names the field equation it closes as an anchor, which does not consume it.
    Auxiliary nodes (chart restatements, identities) are not selected rows, so ancestry is followed through them.
    """
    consumed, pending = set(), [i for r in rows if r in graph.nodes and graph.nodes[r].rule not in ANCHORING_RULES for i in graph.nodes[r].inputs]
    while pending:
        key = pending.pop()
        if key in consumed or key not in graph.nodes:
            continue
        consumed.add(key)
        if graph.nodes[key].rule not in ANCHORING_RULES:
            pending.extend(graph.nodes[key].inputs)
    return consumed


def terminal_rows(graph, rows):
    """Current equations of a replayed selection: rows no later selected row consumed.

    ``selected`` keeps every recorded step; the published system is what is left
    once each substitution, restriction and expansion has consumed its inputs.
    Assumption, domain and other non-condition constraint rows are not equations
    of the system and are skipped.
    """
    consumed = _consumed_by(graph, rows)
    return [r for r in rows if r in graph.nodes and r not in consumed and isinstance(graph.nodes[r].equation, sp.Equality)
            and graph.nodes[r].rule not in SKIPPED_RULES
            and (graph.nodes[r].kind != 'constraint' or _is_condition(graph, r))]


def scoped_rows(graph, rows):
    """Current equations among ``rows`` that are tied to a declared spatial domain.

    A replayed graph also carries the producers' laws of every family and volume;
    only what the user closed with a typed domain belongs to the spatial model:
    the terminal descendants of a domain (expansions, conditions) and the equation
    a domain was declared on when no descendant has superseded it, even if other
    families went on to consume it.
    """
    sources = [source for domain in graph.spatial_domains for interval in graph.nodes[domain].inputs for source in graph.nodes[interval].inputs]
    memo = {}

    def reaches(key):
        if key in memo:
            return memo[key]
        memo[key] = False
        memo[key] = key in graph.spatial_domains or any(reaches(i) for i in graph.nodes[key].inputs if i in graph.nodes)
        return memo[key]
    terminal = terminal_rows(graph, rows)
    descendants = [r for r in terminal if reaches(r)]
    superseded = _consumed_by(graph, descendants)
    anchors = [r for r in rows if r in sources and r in graph.nodes and isinstance(graph.nodes[r].equation, sp.Equality)
               and graph.nodes[r].rule not in SKIPPED_RULES and r not in superseded and r not in descendants]
    return [r for r in rows if r in descendants or r in anchors]


def spatial_publication(graph, rows, units, time=None, model_id='spatial-model'):
    """Publication block of the current equations among ``rows``, or ``None`` when none is spatial.

    A model is published as spatial once it declares a typed spatial domain; the
    block covers the current equations tied to that domain (``terminal_rows`` and
    ``scoped_rows``). Spatial rows without a declared domain stay with Solve's
    located ``requires_discretization`` rejection.

    The block never raises for an unsupported v2 image: it carries the located
    adapter findings and ``matematico: None`` instead, so a published workbench
    report is never lost to an adapter limit.
    """
    if not graph.spatial_domains:
        return None
    findings = requires_discretization(graph, scoped_rows(graph, rows), time)
    if not findings:
        return None
    spatial_ids = [f['equationId'] for f in findings]
    domains = []
    for domain_id, domain in graph.spatial_domains.items():
        domains.append({
            'id': domain_id, 'chart': domain.chart,
            'coordinates': [{'name': str(c), 'lower': str(domain.interval(c).inf), 'upper': str(domain.interval(c).sup), 'unit': 'm' if str(c) != 'phi' else 'rad',
                             'lowerOpen': bool(domain.interval(c).left_open), 'upperOpen': bool(domain.interval(c).right_open)} for c in domain.coordinates],
            'parts': [{'name': p.name, 'coordinate': str(p.coordinate), 'end': p.end, 'point': str(domain.endpoint(p)), 'outwardNormal': p.sign} for p in domain.parts]})
    block = {'format': FORMAT, 'version': 1, 'requiresDiscretization': True, 'handoff': 'transform',
             'solve': {'accepted': False, 'code': 'requires_discretization'},
             'domains': domains,
             'fieldEquations': [f for f in findings if not _is_condition(graph, f['equationId'])],
             'conditions': [f for f in findings if _is_condition(graph, f['equationId'])],
             'findings': [{**f, 'message': discretization_message(f)} for f in findings]}
    values = {}
    try:
        block['matematico'] = to_matematico(graph, spatial_ids, units, time, model_id, values=values)
        block['adapterFindings'] = []
    except PublicationError as error:
        block['matematico'] = None
        block['adapterFindings'] = [error.finding()]
    block['values'] = values
    return block
