"""PDE-2: boundary trace, normal derivative and typed conditions (no discretization).

Two deductions run through the shared recorded operations:

* the 1D transient heat equation in a slab, from the local first law
  produced by the energy family plus a declared Fourier constitutive root,
  closed with Dirichlet, Neumann (flux and gradient forms) and Robin walls and
  an initial condition. Fourier's law restricted to a wall and met with a
  prescribed flux gives the Neumann flux condition -k dT/dx|_L = q_w;
* the matter producer's recorded Fick closure restricted to an impermeable wall
  of the field-view diffusion probe (PDE-0/1), through the workbench API.

Independent references are plain SymPy hand derivations (Subs of derivatives
at the wall coordinate, outward normals written by hand) and an analytic
temperature profile that satisfies the deduced boundary relations.
"""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sympy as sp

from core.balances import energy_derivation as energy
from core.balances.energy_equations import equation_graph as energy_graph
from core.compilador import NoSoportado
from core.compilador.derived import DerivedSystem
from core.mathematics.contract import FORMAT, read_definition
from core.mathematics.dimensions import catalog
from core.mathematics.errors import MathematicsError
from core.mathematics.operators import (BoundaryTrace, Divergence, Gradient, NormalComponent, NormalDerivative,
                                         requires_discretization)
from core.mathematics.session import edit_history, replay_operations
from core.modelo.equation_workbench import build, edit
from test_requires_discretization import dynamic_selection, fick_model

X, Y, Z, T_ = sp.symbols('x y z t', real=True)
L = sp.Rational(1, 10)  # slab thickness, 10 cm in SI
OWNER = 'v1'


def plain(expression):
    """Hand-derivation form: a trace is ordinary evaluation at the wall coordinate."""
    def trace(node):
        inner, coordinate, point = node.args
        return sp.Subs(inner, coordinate, point) if inner.has(sp.Derivative) else inner.subs(coordinate, point)
    return expression.replace(lambda n: isinstance(n, BoundaryTrace), trace)


def residual(equation):
    return plain(equation.lhs - equation.rhs)


# --- Heat-conduction deduction (energy producer + declared Fourier root) --------

def heat_source():
    model = {'volumenes': [{'id': OWNER, 'componenteIds': [1], 'supuestos': {'materia': {'fija': True}}}], 'motores': {}}
    journal = {'format': 'rage.energy-derivation', 'version': 1, 'volumes': {}}
    for action in ('start', 'pressure_stress', 'no_kinetic', 'no_viscous_work', 'no_body_work', 'no_volume_source'):
        journal = energy.edit_journal(journal, OWNER, {'kind': action})
    model['motores']['energyDerivation'] = journal
    graph, final, units = energy_graph(model, OWNER)
    for axis in (X, Y, Z):
        units[axis] = 'm'
    units[T_] = 's'
    temperature = sp.Function('T')(X, Y, Z, T_)
    k = sp.Symbol('k', real=True)
    units[temperature] = 'K'
    units[k] = 'W/(m*K)'
    flux = next(q for q in units if str(q).startswith('heat_flux_energy__'))
    # Empirical constitutive root with provenance. PDE-3 will supply this
    # closure from the energy producer; PDE-2 only needs it to be recorded.
    graph.add('fourier', flux, -k*Gradient(temperature), "Fourier's law of heat conduction", 'declared_law',
              assumptions=('Isotropic conduction, linear in the temperature gradient (Fourier 1822)',), family='energy', kind='constitutive')
    owners = {key: OWNER for key in graph.nodes}
    return graph, [*final, 'fourier'], owners, units


class Session:
    """Records operations through edit_history, so every input is signature-pinned."""

    def __init__(self, source=None):
        self.source = source or heat_source()
        self.definition = {'format': FORMAT, 'version': 1, 'operations': [], 'cursor': 0}

    def result(self, definition=None):
        graph, final, owners, units = self.source
        return replay_operations(graph, final, owners, units, definition or self.definition)

    def ids(self):
        result = self.result()
        return {str(q): key for key, q in {**catalog(result.graph, result.units), **result.introduced}.items()}

    def id(self, name):
        names = self.ids()
        if name not in names:
            raise KeyError(name+' not in '+', '.join(sorted(n for n in names if len(n) < 60)))
        return names[name]

    def action(self, action):
        graph, final, owners, units = self.source
        self.definition = edit_history(graph, final, owners, units, self.definition, action)
        return self.definition

    def append(self, **op):
        op.setdefault('family', 'energy')
        self.action({'kind': 'append', 'operation': op})
        return 'operation.'+str(self.definition['cursor'])

    def equation(self, key):
        return self.result().graph.nodes[key].equation


def heat_equation(session):
    """Local first law -> conduction equation rho c dT/dt = -div(-k grad T)."""
    s = session
    law = s.result().selected[0]
    T = 'T(x, y, z, t)'
    v = s.append(kind='apply_zero', sources=[law], symbol=s.id('velocity_energy__v1(x, y, z, t)'),
                 reason='Rigid solid at rest: no convective transport and no pressure work')
    s.append(kind='declare_symbol', name='c', unit='J/(kg*K)')
    s.append(kind='declare_symbol', name='T_ref', unit='K')
    caloric = s.append(kind='declare_relation', relationKind='constitutive',
                       left=s.id('u_specific__v1(x, y, z, t)'), right=s.id('c')+'*('+s.id(T)+'-'+s.id('T_ref')+')',
                       reason='Incompressible solid with constant specific heat capacity')
    heated = s.append(kind='substitute', sources=[v], relation=caloric, symbol=s.id('u_specific__v1(x, y, z, t)'))
    rigid = s.append(kind='change_dependencies', sources=[heated], symbol=s.id('rho_mixture__v1(x, y, z, t)'), dependencies=[],
                     reason='Uniform and constant solid density')
    pde = s.append(kind='substitute', sources=[rigid], relation='fourier', symbol=s.id('heat_flux_energy__v1(x, y, z, t)'))
    return v, pde


def slab_domain(session, pde, parts=(('left', 'lower'), ('right', 'upper')), upper='10'):
    return session.append(kind='declare_spatial_domain', sources=[pde], chart='cartesian', coordinates=[session.id('x')],
                          intervals=[{'lower': '0', 'upper': upper, 'lowerOpen': False, 'upperOpen': False, 'endpointUnit': 'cm'}],
                          parts=[{'name': name, 'coordinate': session.id('x'), 'end': end} for name, end in parts],
                          reason='Plane slab 0 <= x <= 10 cm; walls at both faces')


def symbols(session, **declared):
    for name, unit in declared.items():
        session.append(kind='declare_symbol', name=name, unit=unit)


class HeatSlabTests(unittest.TestCase):
    def setUp(self):
        self.s = Session()
        self.law, self.pde = heat_equation(self.s)
        self.domain = slab_domain(self.s, self.pde)
        self.T = sp.Function('T')(X, Y, Z, T_)
        self.k, self.rho = sp.Symbol('k', real=True), sp.Symbol('rho_mixture__v1', real=True)
        self.c = sp.Symbol('c', real=True)
        self.q = [q for q in self.s.result().units if str(q).startswith('heat_flux_energy__')][0]

    def test_conduction_equation_is_deduced_from_the_first_law(self):
        equation = self.s.equation(self.pde)
        # Interior operators stay unexpanded: linearity of div and its chart
        # expansion are PDE-3 (generic operator expansion), not PDE-2.
        hand = sp.Eq(self.rho*self.c*sp.Derivative(self.T, T_), -Divergence(-self.k*Gradient(self.T)))
        self.assertEqual(sp.simplify(equation.lhs-equation.rhs-(hand.lhs-hand.rhs)), 0)

    def test_neumann_flux_condition_from_fourier_restricted_to_the_wall(self):
        s = self.s
        symbols(s, q_w='W/m2', T_w='K', T_0='K')
        dirichlet = s.append(kind='declare_condition', conditionKind='dirichlet', sources=[self.pde], domains=[self.domain],
                             boundary='left', symbol=s.id('T(x, y, z, t)'), right=s.id('T_w'), reason='Wall held at T_w')
        restricted = s.append(kind='restrict_to_boundary', sources=['fourier'], domains=[self.domain], boundary='right', form='flux')
        neumann = s.append(kind='declare_condition', conditionKind='neumann', form='flux', sources=[self.law], domains=[self.domain],
                           boundary='right', symbol=s.id(str(self.q)), right=s.id('q_w'), reason='Prescribed outward heat flux q_w')
        closed = s.append(kind='substitute', sources=[neumann], relation=restricted, symbol=s.id(str(NormalComponent(self.q, X, L, 1))))
        expanded = s.append(kind='expand_normal_derivative', sources=[closed], domains=[self.domain])
        initial = s.append(kind='declare_condition', conditionKind='initial', sources=[self.pde], domains=[self.domain],
                           symbol=s.id('T(x, y, z, t)'), time=s.id('t'), instant='0', instantUnit='s', right=s.id('T_0'),
                           reason='Uniform initial temperature')
        result = s.result()
        graph = result.graph
        qw, Tw, T0 = (sp.Symbol(n, real=True) for n in ('q_w', 'T_w', 'T_0'))
        # Recorded relations against the hand derivation (outward normal +e_x at x = L).
        self.assertEqual(graph.nodes[restricted].equation, sp.Eq(NormalComponent(self.q, X, L, 1), -self.k*NormalDerivative(self.T, X, L, 1), evaluate=False))
        hand_neumann = -self.k*sp.Subs(sp.Derivative(self.T, X), X, L) - qw
        self.assertEqual(sp.simplify(residual(graph.nodes[expanded].equation)-hand_neumann), 0)
        self.assertEqual(residual(graph.nodes[dirichlet].equation), self.T.subs(X, 0)-Tw)
        self.assertEqual(residual(graph.nodes[initial].equation), self.T.subs(T_, 0)-T0)
        # Analytic steady profile satisfying both walls, checked independently.
        profile = sp.Lambda((X, Y, Z, T_), Tw - qw*X/self.k)
        for key in (dirichlet, expanded):
            self.assertEqual(sp.simplify(residual(graph.nodes[key].equation).replace(self.T.func, profile).doit()), 0)
        # Kinds, dependence and provenance.
        self.assertEqual(graph.nodes[dirichlet].kind, 'constraint')
        self.assertFalse(graph.nodes[dirichlet].dependent)
        self.assertTrue(graph.nodes[expanded].dependent)
        self.assertEqual(graph.nodes[restricted].kind, 'constitutive')
        self.assertIn(self.domain, graph.nodes[restricted].inputs)
        identity = expanded+'.identity.1'
        self.assertEqual(graph.nodes[identity].equation,
                         sp.Eq(NormalDerivative(self.T, X, L, 1), BoundaryTrace(sp.Derivative(self.T, X), X, L), evaluate=False))
        self.assertIn(identity, graph.nodes[expanded].inputs)
        self.assertTrue(any('outward normal +e_x' in text for text in graph.conditions_for(expanded)))
        receipt = result.receipts[-2]
        self.assertEqual(receipt.signature_status, 'pinned')
        self.assertEqual(dict(receipt.before)[closed], graph.nodes[closed].equation)
        op = s.definition['operations'][int(restricted.split('.')[1])-1]
        self.assertEqual(set(op['sourceSignatures']), {'fourier', self.domain})

    def test_robin_walls_and_left_normal_sign(self):
        s = self.s
        symbols(s, h='W/(m2*K)', T_inf='K')
        hand = {}
        for part, point, sign in (('left', 0, -1), ('right', L, 1)):
            restricted = s.append(kind='restrict_to_boundary', sources=['fourier'], domains=[self.domain], boundary=part, form='flux')
            robin = s.append(kind='declare_condition', conditionKind='robin', form='flux', sources=[self.law], domains=[self.domain],
                             boundary=part, symbol=s.id(str(self.q)), potential=s.id('T(x, y, z, t)'), coefficient=s.id('h'),
                             right=s.id('T_inf'), reason='Newton cooling to ambient T_inf')
            closed = s.append(kind='substitute', sources=[robin], relation=restricted, symbol=s.id(str(NormalComponent(self.q, X, point, sign))))
            hand[part] = s.append(kind='expand_normal_derivative', sources=[closed], domains=[self.domain])
        graph = s.result().graph
        h, Tinf = sp.Symbol('h', real=True), sp.Symbol('T_inf', real=True)
        dTdx = lambda p: sp.Subs(sp.Derivative(self.T, X), X, p)  # noqa: E731
        # k T_x(0) = h (T(0) - T_inf) and -k T_x(L) = h (T(L) - T_inf).
        self.assertEqual(sp.simplify(residual(graph.nodes[hand['left']].equation)-(self.k*dTdx(0)-h*(self.T.subs(X, 0)-Tinf))), 0)
        self.assertEqual(sp.simplify(residual(graph.nodes[hand['right']].equation)-(-self.k*dTdx(L)-h*(self.T.subs(X, L)-Tinf))), 0)

    def test_gradient_forms(self):
        s = self.s
        symbols(s, beta='1/m', T_inf='K')
        zero = s.append(kind='declare_condition', conditionKind='neumann', sources=[self.pde], domains=[self.domain], boundary='right',
                        symbol=s.id('T(x, y, z, t)'), right='0', reason='Insulated wall')
        robin = s.append(kind='declare_condition', conditionKind='robin', sources=[self.pde], domains=[self.domain], boundary='left',
                         symbol=s.id('T(x, y, z, t)'), coefficient=s.id('beta'), right=s.id('T_inf'), reason='Biot exchange, beta = h/k')
        insulated = s.append(kind='expand_normal_derivative', sources=[zero], domains=[self.domain])
        exchange = s.append(kind='expand_normal_derivative', sources=[robin], domains=[self.domain])
        graph = s.result().graph
        beta, Tinf = sp.Symbol('beta', real=True), sp.Symbol('T_inf', real=True)
        self.assertEqual(residual(graph.nodes[insulated].equation), sp.Subs(sp.Derivative(self.T, X), X, L))
        self.assertEqual(sp.simplify(residual(graph.nodes[exchange].equation)-(-sp.Subs(sp.Derivative(self.T, X), X, 0)+beta*(self.T.subs(X, 0)-Tinf))), 0)

    def test_dimensional_consistency_and_located_rejections(self):
        s = self.s
        symbols(s, q_bad='W/m', g='K/m', T_w='K')
        common = dict(sources=[self.law], domains=[self.domain], symbol=s.id(str(self.q)), reason='test')
        with self.assertRaisesRegex(MathematicsError, r'prescribed normal flux has incompatible dimensions: expected W/m\^2, got W/m\.'):
            s.append(kind='declare_condition', conditionKind='neumann', form='flux', boundary='right', right=s.id('q_bad'), **common)
        with self.assertRaisesRegex(MathematicsError, 'prescribed boundary value has incompatible dimensions'):
            s.append(kind='declare_condition', conditionKind='dirichlet', sources=[self.pde], domains=[self.domain], boundary='left',
                     symbol=s.id('T(x, y, z, t)'), right=s.id('g'), reason='test')
        with self.assertRaisesRegex(MathematicsError, 'Boundary part top is not declared on spatial domain operation.8 \\(declared parts: left, right\\)'):
            s.append(kind='declare_condition', conditionKind='dirichlet', sources=[self.pde], domains=[self.domain], boundary='top',
                     symbol=s.id('T(x, y, z, t)'), right=s.id('T_w'), reason='test')
        with self.assertRaisesRegex(MathematicsError, 'Boundary part top is not declared'):
            s.append(kind='restrict_to_boundary', sources=['fourier'], domains=[self.domain], boundary='top', form='flux')
        with self.assertRaisesRegex(MathematicsError, 'outward normal is missing'):
            s.append(kind='declare_condition', conditionKind='neumann', right=s.id('g'), sources=[self.pde], domains=[self.domain],
                     symbol=s.id('T(x, y, z, t)'), reason='no part')
        with self.assertRaisesRegex(MathematicsError, 'initial condition restricts the field in time; it has no outward normal'):
            s.append(kind='declare_condition', conditionKind='initial', form='gradient', sources=[self.pde], domains=[self.domain],
                     symbol=s.id('T(x, y, z, t)'), time=s.id('t'), instant='0', right=s.id('T_w'), reason='test')
        with self.assertRaisesRegex(MathematicsError, 'its normal component is missing'):
            s.append(kind='restrict_to_boundary', sources=[self.pde], domains=[self.domain], boundary='right', form='flux')
        with self.assertRaisesRegex(MathematicsError, 'cannot depend on x'):
            s.append(kind='declare_condition', conditionKind='dirichlet', sources=[self.pde], domains=[self.domain], boundary='left',
                     symbol=s.id('T(x, y, z, t)'), right=s.id('T_w')+'+'+s.id('x')+'*'+s.id('g'), reason='test')
        with self.assertRaisesRegex(MathematicsError, 'not a declared spatial domain|is not one'):
            s.append(kind='declare_condition', conditionKind='dirichlet', sources=[self.pde], domains=['fourier'], boundary='left',
                     symbol=s.id('T(x, y, z, t)'), right=s.id('T_w'), reason='test')
        with self.assertRaisesRegex(MathematicsError, 'Robin coefficient has incompatible dimensions'):
            s.append(kind='declare_condition', conditionKind='robin', sources=[self.pde], domains=[self.domain], boundary='left',
                     symbol=s.id('T(x, y, z, t)'), coefficient=s.id('T_w'), right=s.id('T_w'), reason='test')

    def test_undo_redo_and_invalidation_by_domain_or_part_change(self):
        s = self.s
        symbols(s, T_w='K')
        dirichlet = s.append(kind='declare_condition', conditionKind='dirichlet', sources=[self.pde], domains=[self.domain], boundary='right',
                             symbol=s.id('T(x, y, z, t)'), right=s.id('T_w'), reason='Wall held at T_w')
        restricted = s.append(kind='restrict_to_boundary', sources=['fourier'], domains=[self.domain], boundary='right', form='flux')
        recorded = copy.deepcopy(s.definition)
        s.action({'kind': 'undo'})
        self.assertNotIn(restricted, s.result().graph.nodes)
        s.action({'kind': 'undo'})
        self.assertNotIn(dirichlet, s.result().graph.nodes)
        s.action({'kind': 'redo'});s.action({'kind': 'redo'})
        self.assertEqual(s.definition, recorded)
        self.assertEqual(s.result().graph.nodes[dirichlet].equation.lhs, BoundaryTrace(self.T, X, L))
        index = int(self.domain.split('.')[1])-1
        for change, message in [(lambda op: op['intervals'][0].update(upper='20'), 'changed behind the same ID'),
                                (lambda op: op['parts'][1].update(name='outer'), 'changed behind the same ID'),
                                (lambda op: op['parts'].reverse() or op['parts'][0].update(end='upper') or op['parts'][1].update(end='lower'), 'changed behind the same ID')]:
            changed = copy.deepcopy(recorded)
            change(changed['operations'][index])
            with self.assertRaisesRegex(MathematicsError, message):
                self.s.result(changed)
        # Without pinned signatures (legacy), a renamed part is still a located rejection.
        legacy = copy.deepcopy(recorded)
        for op in legacy['operations']:
            op.pop('sourceSignatures', None)
        legacy['operations'][index]['parts'][1]['name'] = 'outer'
        with self.assertRaisesRegex(MathematicsError, 'Boundary part right is not declared on spatial domain '+self.domain):
            self.s.result(legacy)
        legacy['operations'][index]['parts'][1]['name'] = 'right'
        legacy['operations'][index]['intervals'][0]['upper'] = '20'
        moved = self.s.result(legacy).graph.nodes[dirichlet].equation
        self.assertEqual(moved.lhs, BoundaryTrace(self.T, X, sp.Rational(1, 5)))

    def test_boundary_rows_require_discretization(self):
        s = self.s
        symbols(s, T_w='K')
        dirichlet = s.append(kind='declare_condition', conditionKind='dirichlet', sources=[self.pde], domains=[self.domain], boundary='left',
                             symbol=s.id('T(x, y, z, t)'), right=s.id('T_w'), reason='Wall held at T_w')
        findings = requires_discretization(s.result().graph, [dirichlet], T_)
        self.assertEqual(findings[0]['equationId'], dirichlet)
        self.assertIn('BoundaryTrace', findings[0]['operators'])
        self.assertEqual(findings[0]['fields'], ['T(x, y, z, t)'])


class FickWallTests(unittest.TestCase):
    """Recorded producer closure (matter Fick law) restricted through the workbench API."""
    ROW = 'matter.v1.1.operators'

    def setUp(self):
        self.model, self.names, self.datum = fick_model()

    def append(self, op):
        report = edit(self.model, {'kind': 'append', 'operation': {'family': 'matter', **op}})
        self.model['motores']['equationWorkbench'] = report['definition']
        return report

    def ids(self):
        result = build(self.model)
        return {str(q): key for key, q in {**catalog(result.graph, result.units), **result.introduced}.items()}

    def test_impermeable_wall_from_the_recorded_fick_closure(self):
        x = self.names['x']
        self.append({'kind': 'declare_spatial_domain', 'sources': [self.ROW], 'chart': 'cartesian', 'coordinates': [x],
                     'intervals': [{'lower': '0', 'upper': '1', 'lowerOpen': False, 'upperOpen': False, 'endpointUnit': 'cm'}],
                     'parts': [{'name': 'inlet', 'coordinate': x, 'end': 'lower'}, {'name': 'wall', 'coordinate': x, 'end': 'upper'}],
                     'reason': 'Diffusion slab 0 <= x <= 1 cm'})
        self.append({'kind': 'restrict_to_boundary', 'sources': ['matter.v1.1.fick'], 'domains': ['operation.1'], 'boundary': 'wall', 'form': 'flux'})
        rho = sp.Function('rho__v1__1')(X, Y, Z, T_)
        j = sp.Function('j__v1__1')(X, Y, Z, T_)
        D = sp.Function('D__v1__1')(T_)
        W = sp.Rational(1, 100)
        self.append({'kind': 'declare_condition', 'conditionKind': 'neumann', 'form': 'flux', 'sources': ['matter.v1.1.local'],
                     'domains': ['operation.1'], 'boundary': 'wall', 'symbol': self.ids()[str(j)], 'right': '0',
                     'reason': 'Impermeable wall: no component flux through it'})
        self.append({'kind': 'substitute', 'sources': ['operation.3'], 'relation': 'operation.2', 'symbol': self.ids()[str(NormalComponent(j, X, W, 1))]})
        report = self.append({'kind': 'expand_normal_derivative', 'sources': ['operation.4'], 'domains': ['operation.1']})
        graph = build(self.model).graph
        self.assertEqual(graph.nodes['operation.2'].equation, sp.Eq(NormalComponent(j, X, W, 1), -D*NormalDerivative(rho, X, W, 1), evaluate=False))
        hand = -D*sp.Subs(sp.Derivative(rho, X), X, W)
        self.assertEqual(sp.simplify(residual(graph.nodes['operation.5'].equation)-hand), 0)
        rows = {row['id']: row for row in report['equations']}
        self.assertEqual(rows['operation.5']['derivation']['rule'], 'substitution')
        self.assertIn(r'\right|_{x=\frac{1}{100}}', rows['operation.5']['latex'])
        self.assertFalse(report['execution']['supported'])

    def test_execution_still_rejects_with_located_reason(self):
        x = self.names['x']
        self.append({'kind': 'declare_spatial_domain', 'sources': [self.ROW], 'chart': 'cartesian', 'coordinates': [x],
                     'intervals': [{'lower': '0', 'upper': '1', 'lowerOpen': False, 'upperOpen': False, 'endpointUnit': 'cm'}],
                     'parts': [{'name': 'wall', 'coordinate': x, 'end': 'upper'}], 'reason': 'slab'})
        self.append({'kind': 'restrict_to_boundary', 'sources': ['matter.v1.1.fick'], 'domains': ['operation.1'], 'boundary': 'wall', 'form': 'flux'})
        model = dynamic_selection(self.model, self.names, self.datum)
        with self.assertRaises(NoSoportado) as caught:
            DerivedSystem(model)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'requires_discretization')
        self.assertEqual(caught.exception.diagnostics[0]['equationId'], self.ROW)
        finding = requires_discretization(build(model).graph, ['operation.2'], T_)[0]
        self.assertEqual((finding['equationId'], finding['coordinates']), ('operation.2', ['x', 'y', 'z']))
        self.assertIn('NormalDerivative', finding['operators'])

    def test_contract_is_additive(self):
        base = {'format': FORMAT, 'version': 1, 'cursor': 1}
        op = {'kind': 'declare_condition', 'family': 'matter', 'sources': ['a'], 'domains': ['d'], 'conditionKind': 'dirichlet',
              'boundary': 'wall', 'symbol': 's', 'right': '0', 'reason': 'r'}
        read_definition({**base, 'operations': [op]})
        for bad, message in [({**op, 'conditionKind': 'periodic'}, 'Classify the condition'),
                             ({**op, 'time': 't'}, 'does not belong to a dirichlet'),
                             ({**op, 'form': 'flux'}, 'does not accept the flux form'),
                             ({**op, 'conditionKind': 'continuity'}, 'neighbouring boundary part'),
                             ({**op, 'conditionKind': 'robin'}, 'exchange coefficient'),
                             ({'kind': 'expand', 'family': 'matter', 'sources': ['a'], 'boundary': 'wall'}, 'belong only to boundary'),
                             ({'kind': 'expand', 'family': 'matter', 'sources': ['a'], 'conditionKind': 'initial'}, 'belong only to typed condition'),
                             ({'kind': 'restrict_to_boundary', 'family': 'matter', 'sources': ['a'], 'domains': ['d'], 'boundary': 'w', 'form': 'trace'}, 'by value'),
                             ({'kind': 'expand_normal_derivative', 'family': 'matter', 'sources': ['a'], 'domains': ['d', 'e']}, 'exactly one declared spatial domain')]:
            with self.assertRaisesRegex(MathematicsError, message):
                read_definition({**base, 'operations': [bad]})


class ContinuityTests(unittest.TestCase):
    def test_two_layer_interface(self):
        s = Session()
        law, pde = heat_equation(s)
        first = slab_domain(s, pde, parts=(('a_left', 'lower'), ('a_right', 'upper')), upper='10')
        T2 = sp.Function('T2')(X, Y, Z, T_)
        s.append(kind='declare_function', name='T2', unit='K', dependencies=[s.id('x'), s.id('y'), s.id('z'), s.id('t')])
        second = s.append(kind='declare_spatial_domain', sources=[pde], chart='cartesian', coordinates=[s.id('x')],
                          intervals=[{'lower': '10', 'upper': '30', 'lowerOpen': False, 'upperOpen': False, 'endpointUnit': 'cm'}],
                          parts=[{'name': 'b_left', 'coordinate': s.id('x'), 'end': 'lower'}], reason='Second layer 10 <= x <= 30 cm')
        value = s.append(kind='declare_condition', conditionKind='continuity', sources=[pde], domains=[first, second], boundary='a_right',
                         neighborBoundary='b_left', symbol=s.id('T(x, y, z, t)'), neighborSymbol=s.id('T2(x, y, z, t)'),
                         reason='Perfect thermal contact')
        result = s.result()
        self.assertEqual(result.graph.nodes[value].equation, sp.Eq(BoundaryTrace(sp.Function('T')(X, Y, Z, T_), X, L), BoundaryTrace(T2, X, L), evaluate=False))
        s.append(kind='declare_function', name='q2', unit='W/m2', dependencies=[s.id('x'), s.id('y'), s.id('z'), s.id('t')])
        q = [q for q in result.units if str(q).startswith('heat_flux_energy__')][0]
        flux = s.append(kind='declare_condition', conditionKind='continuity', form='flux', sources=[law], domains=[first, second],
                        boundary='a_right', neighborBoundary='b_left', symbol=s.id(str(q)), neighborSymbol=s.id('q2(x, y, z, t)'),
                        reason='No interfacial heat storage or source')
        q2 = sp.Function('q2')(X, Y, Z, T_)
        # n_a.q + n_b.q2 = 0 with n_a = +e_x and n_b = -e_x: q_x = q2_x at the interface.
        self.assertEqual(s.result().graph.nodes[flux].equation, sp.Eq(NormalComponent(q, X, L, 1), -NormalComponent(q2, X, L, -1), evaluate=False))
        with self.assertRaisesRegex(MathematicsError, 'neighbouring field has incompatible dimensions'):
            s.append(kind='declare_condition', conditionKind='continuity', sources=[pde], domains=[first, second], boundary='a_right',
                     neighborBoundary='b_left', symbol=s.id('T(x, y, z, t)'), neighborSymbol=s.id('q2(x, y, z, t)'), reason='test')
        with self.assertRaisesRegex(MathematicsError, 'do not coincide with opposite outward normals'):
            s.append(kind='declare_condition', conditionKind='continuity', sources=[pde], domains=[first, second], boundary='a_left',
                     neighborBoundary='b_left', symbol=s.id('T(x, y, z, t)'), neighborSymbol=s.id('T2(x, y, z, t)'), reason='test')


if __name__ == '__main__':
    unittest.main()
