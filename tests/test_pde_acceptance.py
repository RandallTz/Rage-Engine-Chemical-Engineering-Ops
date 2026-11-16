"""PDE-7: acceptance of PDE deduction without spatial execution (Fick, Fourier, Stokes' first problem).

Each problem starts from the local fundamental law of its family, as produced by
that family, and reaches a published spatial model only through recorded
workbench operations: closures, constant-property relations, a typed spatial
domain with oriented boundary parts and typed initial and boundary conditions.
Nothing is discretized or solved (F7): the publication hands the model to
Transform and Solve keeps its located ``requires_discretization`` rejection.

Independent references (nothing below uses the deduction kernel to check itself):

* the recursive mpmath evaluator of the published v2 expression trees
  (``tests/test_spatial_publication.py``), with mpmath numerical derivatives;
* analytic solutions:
  - Fick, two Dirichlet walls: rho = rho_w + A sin(pi x/L) exp(-D pi^2 t/L^2);
  - Fourier, prescribed wall flux q_w at x = 0 and Dirichlet T_e at x = a:
    T = T_e + q_w (a - x)/k + A cos(pi x/(2a)) exp(-alpha pi^2 t/(4 a^2)), alpha = k/(rho c);
  - Stokes' first problem (plate set impulsively in motion at speed U under a
    fluid at rest): v = U erfc(y/(2 sqrt(nu t))), nu = mu/rho, and the finite-gap
    (impulsively started Couette) series
    v = U (1 - y/H) - sum_n 2U/(n pi) sin(n pi y/H) exp(-nu n^2 pi^2 t/H^2);
* the nondimensionalization core's own dimensional analysis (``analizar_modelo``).
"""
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mpmath as mp
import sympy as sp

from core.adimensionalizacion.dimensional import analizar_modelo
from core.balances import momentum_derivation as momentum
from core.mathematics.dimensions import catalog
from core.mathematics.domains import SpatialDomain, admit_coordinate, axis_name, axis_scope, chart_axes
from core.mathematics.errors import MathematicsError
from core.mathematics.operators import requires_discretization
from core.mathematics.publication import spatial_publication
from core.modelo.equation_workbench import _known_unit, build, edit
from test_operator_expansion import heat_pde, source
from test_boundary_conditions import Session, symbols
from test_requires_discretization import fick_model
from test_spatial_publication import by_id, evaluate, residual, slab

mp.mp.dps = 30

STOKES = ('pressureStress', 'newtonian', 'massContinuity', 'constantViscosity', 'divergenceFree',
          'invariantX', 'invariantZ', 'zeroVelocityY', 'zeroVelocityZ', 'negligibleBodyForce')


class Workbench:
    """Edits a common model through the workbench API only (signature-pinned recorded operations)."""

    def __init__(self, model, family):
        self.model, self.family = model, family

    def ids(self):
        result = build(self.model)
        return {str(q): key for key, q in {**catalog(result.graph, result.units), **result.introduced}.items()}

    def append(self, **op):
        report = edit(self.model, {'kind': 'append', 'operation': {'family': self.family, **op}})
        self.model['motores']['equationWorkbench'] = report['definition']
        self.report = report
        return 'operation.' + str(report['definition']['cursor'])

    def publish(self):
        result = build(self.model)
        return result, spatial_publication(result.graph, result.selected, result.units, model_id='acceptance', unit_resolver=_known_unit)


def errors(model):
    return [d for d in analizar_modelo(model)['diagnosticos'] if d['severidad'] == 'error']


class FickAcceptanceTest(unittest.TestCase):
    """Matter: the recorded Fick closure of the matter producer's field view, two Dirichlet walls."""

    @classmethod
    def setUpClass(cls):
        model, names, _ = fick_model()
        w = cls.w = Workbench(model, 'matter')
        x = names['x']
        pde = cls.pde = 'matter.v1.1.operators'
        region = w.append(kind='declare_spatial_domain', sources=[pde], chart='cartesian', coordinates=[x],
                          intervals=[{'lower': '0', 'upper': '1', 'lowerOpen': False, 'upperOpen': False, 'endpointUnit': 'cm'}],
                          parts=[{'name': 'left', 'coordinate': x, 'end': 'lower'}, {'name': 'right', 'coordinate': x, 'end': 'upper'}],
                          reason='Diffusion slab 0 <= x <= 1 cm')
        w.append(kind='declare_symbol', name='rho_w', unit='kg/m3')
        w.append(kind='declare_symbol', name='rho_i', unit='kg/m3')
        ids = w.ids()
        field = ids['rho__v1__1(x, t)']
        cls.rows = {
            'left': w.append(kind='declare_condition', conditionKind='dirichlet', sources=[pde], domains=[region], boundary='left',
                             symbol=field, right=ids['rho_w'], reason='Wall held at the equilibrium concentration rho_w'),
            'right': w.append(kind='declare_condition', conditionKind='dirichlet', sources=[pde], domains=[region], boundary='right',
                              symbol=field, right=ids['rho_w'], reason='Wall held at the equilibrium concentration rho_w'),
            'initial': w.append(kind='declare_condition', conditionKind='initial', sources=[pde], domains=[region], symbol=field,
                                time=ids['t'], instant='0', instantUnit='s', right=ids['rho_i'], reason='Uniform initial concentration')}
        cls.result, cls.block = w.publish()

    def test_published_system_is_the_fick_equation_with_its_conditions(self):
        block = self.block
        self.assertEqual(block['adapterFindings'], [])
        self.assertEqual([f['equationId'] for f in block['fieldEquations']], [self.pde])
        self.assertEqual({f['equationId'] for f in block['conditions']}, set(self.rows.values()))
        types = {c['id']: (c['tipo'], c['ubicacion']['extremo']) for c in block['matematico']['condiciones']}
        self.assertEqual(types, {self.rows['left'] + '.condition': ('dirichlet', 'desde'), self.rows['right'] + '.condition': ('dirichlet', 'hasta'),
                                 self.rows['initial'] + '.condition': ('inicial', 'desde')})
        self.assertEqual(errors(block['matematico']), [])

    def test_analytic_profile_satisfies_the_published_model(self):
        model = self.block['matematico']
        L, D, rho_w, A = mp.mpf(1) / 100, mp.mpf('2e-9'), mp.mpf(5), mp.mpf(3)
        profile = lambda x, t: rho_w + A * mp.sin(mp.pi * x / L) * mp.exp(-D * mp.pi ** 2 * t / L ** 2)  # noqa: E731
        fields = {'rho__v1__1': (profile, ['x', 't']), 'D__v1__1': (lambda t: D, ['t'])}
        env = {'rho_w': rho_w, 'rho_i': mp.mpf(8)}
        equation = by_id(model['ecuaciones'], self.pde)
        for x, t in ((L / 3, mp.mpf(10)), (L / 7, mp.mpf(4000)), (0.9 * L, mp.mpf(20000))):
            value = abs(residual(equation, {**env, 'x': x, 't': t}, fields))
            scale = abs(evaluate(equation['izquierda'], {**env, 'x': x, 't': t}, fields))
            self.assertLess(value, 1e-12 * scale)
        for key, point in (('left', 0), ('right', L)):
            condition = by_id(model['condiciones'], self.rows[key] + '.condition')['ecuacion']
            self.assertLess(abs(residual(condition, {**env, 'x': mp.mpf(point), 't': mp.mpf(50)}, fields)), 1e-25)
        # Control: a wrong diffusivity leaves an O(1) relative residual (the check can fail).
        wrong = {**fields, 'D__v1__1': (lambda t: 2 * D, ['t'])}
        self.assertGreater(abs(residual(equation, {**env, 'x': L / 3, 't': mp.mpf(10)}, wrong)),
                           0.5 * abs(evaluate(equation['izquierda'], {**env, 'x': L / 3, 't': mp.mpf(10)}, fields)))
        uniform = {'rho__v1__1': (lambda x, t: mp.mpf(8), ['x', 't'])}
        condition = by_id(model['condiciones'], self.rows['initial'] + '.condition')['ecuacion']
        self.assertLess(abs(residual(condition, {**env, 'x': L / 2, 't': mp.mpf(0)}, uniform)), 1e-25)

    def test_solve_rejects_the_field_equation_with_a_located_reason(self):
        findings = requires_discretization(self.result.graph, [self.pde], None)
        self.assertEqual([(f['equationId'], f['coordinates']) for f in findings], [(self.pde, ['x'])])
        self.assertIn('spatial discretization is deferred (F7)', next(f for f in self.block['findings'] if f['equationId'] == self.pde)['message'])
        self.assertEqual(self.block['solve'], {'accepted': False, 'code': 'requires_discretization'})
        self.assertIs(self.w.report['execution']['supported'], False)


class FourierAcceptanceTest(unittest.TestCase):
    """Energy: local first law plus the recorded Fourier closure; prescribed wall flux and a Dirichlet wall."""

    @classmethod
    def setUpClass(cls):
        s = cls.s = Session(source())
        _, pde = heat_pde(s)
        region = slab(s, pde)
        key = cls.pde = s.append(kind='expand_spatial_operators', sources=[pde], domains=[region])
        symbols(s, q_w='W/m2', T_e='K', T_0='K')
        cls.rows = {
            'left': s.append(kind='declare_condition', conditionKind='neumann', form='gradient', sources=[key], domains=[region], boundary='left',
                             symbol=s.id('T(x, t)'), right=s.id('q_w') + '/' + s.id('k'), reason='Prescribed heat flux q_w into the slab at x = 0'),
            'right': s.append(kind='declare_condition', conditionKind='dirichlet', sources=[key], domains=[region], boundary='right',
                              symbol=s.id('T(x, t)'), right=s.id('T_e'), reason='Right wall at T_e'),
            'initial': s.append(kind='declare_condition', conditionKind='initial', sources=[key], domains=[region], symbol=s.id('T(x, t)'),
                                time=s.id('t'), instant='0', instantUnit='s', right=s.id('T_0'), reason='Uniform start')}
        result = cls.result = s.result()
        cls.block = spatial_publication(result.graph, result.selected, result.units)

    def test_conditions_keep_their_type(self):
        self.assertEqual(self.block['adapterFindings'], [])
        types = {c['id']: c['tipo'] for c in self.block['matematico']['condiciones']}
        self.assertEqual(types, {self.rows['left'] + '.condition': 'flujo', self.rows['right'] + '.condition': 'dirichlet',
                                 self.rows['initial'] + '.condition': 'inicial'})
        self.assertEqual(errors(self.block['matematico']), [])

    def test_analytic_profile_satisfies_the_published_model(self):
        model = self.block['matematico']
        a, k, rho, c = mp.mpf(1) / 10, mp.mpf(15), mp.mpf(7800), mp.mpf(460)
        alpha = k / (rho * c)
        q_w, T_e, A = mp.mpf(2000), mp.mpf(300), mp.mpf(25)
        T = lambda x, t: T_e + q_w * (a - x) / k + A * mp.cos(mp.pi * x / (2 * a)) * mp.exp(-alpha * mp.pi ** 2 * t / (4 * a ** 2))  # noqa: E731
        fields = {'T': (T, ['x', 't'])}
        env = {'k': k, 'rho_mixture__v1': rho, 'c': c, 'q_w': q_w, 'T_e': T_e, 'T_0': mp.mpf(300)}
        for x, t in ((a / 3, mp.mpf(10)), (a / 7, mp.mpf(200)), (0.8 * a, mp.mpf(1000))):
            self.assertLess(abs(residual(by_id(model['ecuaciones'], self.pde), {**env, 'x': x, 't': t}, fields)), 1e-6)
        for key, point in (('left', 0), ('right', a)):
            condition = by_id(model['condiciones'], self.rows[key] + '.condition')['ecuacion']
            self.assertLess(abs(residual(condition, {**env, 'x': mp.mpf(point), 't': mp.mpf(37)}, fields)), 1e-15)
        # Control: the flux enters the slab; the opposite sign leaves a residual of 2 q_w/k.
        condition = by_id(model['condiciones'], self.rows['left'] + '.condition')['ecuacion']
        self.assertGreater(abs(residual(condition, {**env, 'q_w': -q_w, 'x': mp.mpf(0), 't': mp.mpf(37)}, fields)), q_w / k)


class StokesFirstProblemTest(unittest.TestCase):
    """Momentum: Cauchy's local law, reduced by the momentum family's recorded assumptions, closed in the workbench."""

    @classmethod
    def setUpClass(cls):
        model, _, _ = fick_model()
        model['volumenes'][0]['balances']['momento'] = True
        journal = momentum.edit_journal({'format': momentum.FORMAT, 'version': 1, 'volumes': {}}, 'v1', {'kind': 'start'})
        for name in STOKES:
            journal = momentum.edit_journal(journal, 'v1', {'kind': 'set_assumption', 'name': name, 'value': True})
        model['motores']['momentumDerivation'] = journal
        w = cls.w = Workbench(model, 'momentum')
        cls.reduced = 'momentum.v1.local.x.step-' + str(len(STOKES))
        w.append(kind='declare_symbol', name='rho_0', unit='kg/m3')
        density = w.append(kind='declare_relation', relationKind='constitutive', left=w.ids()['rho__v1(y__v1, t)'], right=w.ids()['rho_0'],
                           reason='Incompressible fluid at a constant reference density')
        constant = w.append(kind='substitute', sources=[cls.reduced], relation=density, symbol=w.ids()['rho__v1(y__v1, t)'])
        w.append(kind='declare_symbol', name='mu_0', unit='Pa*s')
        viscosity = w.append(kind='declare_relation', relationKind='constitutive', left=w.ids()['mu__v1(t)'], right=w.ids()['mu_0'],
                             reason='Constant dynamic viscosity')
        pde = cls.pde = w.append(kind='substitute', sources=[constant], relation=viscosity, symbol=w.ids()['mu__v1(t)'])
        y = w.ids()['y__v1']
        region = w.append(kind='declare_spatial_domain', sources=[pde], chart='cartesian', coordinates=[y],
                          intervals=[{'lower': '0', 'upper': '1', 'lowerOpen': False, 'upperOpen': False, 'endpointUnit': 'cm'}],
                          parts=[{'name': 'plate', 'coordinate': y, 'end': 'lower'}, {'name': 'far', 'coordinate': y, 'end': 'upper'}],
                          reason='Fluid layer 0 <= y <= 1 cm above the plate')
        w.append(kind='declare_symbol', name='U', unit='m/s')
        ids = w.ids()
        v = ids['v_x__v1(y__v1, t)']
        cls.rows = {
            'plate': w.append(kind='declare_condition', conditionKind='dirichlet', sources=[pde], domains=[region], boundary='plate', symbol=v,
                              right=ids['U'], reason='No slip on the plate, set impulsively in motion at speed U'),
            'far': w.append(kind='declare_condition', conditionKind='dirichlet', sources=[pde], domains=[region], boundary='far', symbol=v,
                            right='0', reason='No slip on a fixed wall at y = H'),
            'initial': w.append(kind='declare_condition', conditionKind='initial', sources=[pde], domains=[region], symbol=v, time=ids['t'],
                                instant='0', instantUnit='s', right='0', reason='Fluid initially at rest')}
        cls.result, cls.block = w.publish()
        cls.model = cls.block['matematico']

    def test_deduction_starts_from_cauchy_and_records_every_reduction(self):
        graph = self.result.graph
        chain, key = [], self.reduced
        while key.startswith('momentum.v1.local.x'):
            chain.append(graph.nodes[key].rule)
            key = graph.nodes[key].inputs[0] if graph.nodes[key].inputs else ''
        self.assertEqual(chain[-1], 'declared_law')
        self.assertTrue(all(rule == 'physical_reduction' for rule in chain[:-1]))
        self.assertEqual(graph.nodes['momentum.v1.local.x'].title, 'Fundamental Cauchy conservation · x component')
        y, t = sp.Symbol('y__v1', real=True), sp.Symbol('t', real=True)
        v = sp.Function('v_x__v1')(y, t)
        rho_0, mu_0 = sp.Symbol('rho_0', real=True), sp.Symbol('mu_0', real=True)
        equation = graph.nodes[self.pde].equation
        self.assertEqual(sp.simplify((equation.lhs - equation.rhs) - (rho_0 * sp.Derivative(v, t) - mu_0 * sp.Derivative(v, (y, 2)))), 0)

    def test_published_document_with_dimensions_and_located_conditions(self):
        self.assertEqual(self.block['adapterFindings'], [])
        roles = {s['id']: (s['rol'], s['dimension']) for s in self.model['simbolos']}
        self.assertEqual(roles['y__v1'], ('coordenada', {'L': {'n': 1, 'd': 1}}))
        self.assertEqual(roles['v_x__v1'], ('campo', {'L': {'n': 1, 'd': 1}, 'T': {'n': -1, 'd': 1}}))
        self.assertEqual(roles['t'][0], 'tiempo')
        self.assertEqual(self.block['values'], {'y__v1_upper': {'value': '1/100', 'unit': 'm'}})
        types = {c['id']: (c['tipo'], c['ubicacion']['variableId'], c['ubicacion']['extremo']) for c in self.model['condiciones']}
        self.assertEqual(types, {self.rows['plate'] + '.condition': ('dirichlet', 'y__v1', 'desde'),
                                 self.rows['far'] + '.condition': ('dirichlet', 'y__v1', 'hasta'),
                                 self.rows['initial'] + '.condition': ('inicial', 't', 'desde')})
        self.assertEqual(self.block['domains'][0]['coordinates'][0]['unit'], 'm')
        self.assertEqual(errors(self.model), [])

    def test_erfc_profile_of_stokes_first_problem(self):
        rho, mu, U, H = mp.mpf(1000), mp.mpf('1e-3'), mp.mpf('0.2'), mp.mpf(1) / 100
        nu = mu / rho
        v = lambda y, t: U * mp.erfc(y / (2 * mp.sqrt(nu * t)))  # noqa: E731
        fields = {'v_x__v1': (v, ['y__v1', 't'])}
        env = {'rho_0': rho, 'mu_0': mu, 'U': U}
        equation = by_id(self.model['ecuaciones'], self.pde)
        for y, t in ((mp.mpf('0.0005'), mp.mpf('0.5')), (mp.mpf('0.002'), mp.mpf(3)), (mp.mpf('0.004'), mp.mpf(20))):
            scale = abs(evaluate(equation['izquierda'], {**env, 'y__v1': y, 't': t}, fields))
            self.assertGreater(scale, 1e-6)
            self.assertLess(abs(residual(equation, {**env, 'y__v1': y, 't': t}, fields)), 1e-15 * scale)
        plate = by_id(self.model['condiciones'], self.rows['plate'] + '.condition')['ecuacion']
        self.assertLess(abs(residual(plate, {**env, 'y__v1': mp.mpf(0), 't': mp.mpf(2)}, fields)), 1e-25)
        # The erfc profile is the semi-infinite limit: at y = H the wall condition holds to erfc(H/(2 sqrt(nu t))).
        far = by_id(self.model['condiciones'], self.rows['far'] + '.condition')['ecuacion']
        self.assertLess(abs(residual(far, {**env, 'y__v1': H, 't': mp.mpf(1)}, fields)), 1e-12)
        # Fluid at rest initially: v -> 0 as t -> 0+ at every y > 0.
        initial = by_id(self.model['condiciones'], self.rows['initial'] + '.condition')['ecuacion']
        self.assertLess(abs(residual(initial, {**env, 'y__v1': H / 10, 't': mp.mpf('1e-6')}, fields)), 1e-20)
        # Control: the inviscid-wall sign error (v = U erf) fails the plate condition.
        wrong = {'v_x__v1': (lambda y, t: U * mp.erf(y / (2 * mp.sqrt(nu * t))), ['y__v1', 't'])}
        self.assertGreater(abs(residual(plate, {**env, 'y__v1': mp.mpf(0), 't': mp.mpf(2)}, wrong)), U / 2)

    def test_finite_gap_series_satisfies_the_model_exactly(self):
        rho, mu, U, H = mp.mpf(1000), mp.mpf('1e-3'), mp.mpf('0.2'), mp.mpf(1) / 100
        nu = mu / rho
        terms = 40
        v = lambda y, t: U * (1 - y / H) - sum(2 * U / (n * mp.pi) * mp.sin(n * mp.pi * y / H) * mp.exp(-nu * n ** 2 * mp.pi ** 2 * t / H ** 2)  # noqa: E731
                                               for n in range(1, terms + 1))
        fields = {'v_x__v1': (v, ['y__v1', 't'])}
        env = {'rho_0': rho, 'mu_0': mu, 'U': U}
        equation = by_id(self.model['ecuaciones'], self.pde)
        for y, t in ((H / 4, mp.mpf(5)), (H / 2, mp.mpf(30))):
            scale = abs(evaluate(equation['izquierda'], {**env, 'y__v1': y, 't': t}, fields))
            self.assertLess(abs(residual(equation, {**env, 'y__v1': y, 't': t}, fields)), 1e-12 * scale)
        for key, point in (('plate', 0), ('far', H)):
            condition = by_id(self.model['condiciones'], self.rows[key] + '.condition')['ecuacion']
            self.assertLess(abs(residual(condition, {**env, 'y__v1': point, 't': mp.mpf(5)}, fields)), 1e-25)

    def test_solve_rejects_the_field_equation_with_a_located_reason(self):
        findings = requires_discretization(self.result.graph, [self.pde], None)
        self.assertEqual([(f['equationId'], f['coordinates']) for f in findings], [(self.pde, ['y__v1'])])
        self.assertIn('spatial discretization is deferred (F7)', next(f for f in self.block['findings'] if f['equationId'] == self.pde)['message'])
        self.assertEqual(self.block['solve'], {'accepted': False, 'code': 'requires_discretization'})
        self.assertIs(self.w.report['execution']['supported'], False)


class OwnerScopedChartTest(unittest.TestCase):
    """A chart takes the owner scope of its coordinates; scopes never mix and axes keep their meaning."""

    def test_scoped_axes_and_rejections(self):
        y = sp.Symbol('y__v1', real=True)
        admit_coordinate('cartesian', y)
        self.assertEqual((axis_name(y), axis_scope(y)), ('y', '__v1'))
        self.assertEqual(chart_axes('cartesian', '__v1'), sp.symbols('x__v1 y__v1 z__v1', real=True))
        for wrong in (sp.Symbol('r__v1', real=True), sp.Symbol('y__v1'), sp.Symbol('phi__v1', real=True)):
            with self.assertRaises(MathematicsError):
                admit_coordinate('cylindrical' if str(wrong) == 'phi__v1' else 'cartesian', wrong)
        from core.mathematics.domains import DomainPremise
        x = sp.Symbol('x', real=True)
        intervals = tuple(DomainPremise(c, 'interval', lower='0', upper='1', explicit_units=True) for c in (x, y))
        with self.assertRaises(MathematicsError):
            SpatialDomain('cartesian', (x, y), intervals, ())
        domain = SpatialDomain('cartesian', (y,), intervals[1:], ())
        self.assertEqual(domain.axes, chart_axes('cartesian', '__v1'))


if __name__ == '__main__':
    unittest.main()
