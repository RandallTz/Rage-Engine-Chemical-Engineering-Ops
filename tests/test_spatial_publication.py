"""PDE-4: spatial publication block and graph-to-``matematico`` v2 adapter (no discretization).

The deduced heat-conduction models of PDE-2/PDE-3 are published as models that
require discretization, and translated into the nondimensional ``matematico``
v2 document. Independent references (nothing below uses the kernel):

* a small recursive evaluator of the published expression trees with mpmath,
  whose derivatives are mpmath numerical differentiation of the sub-trees;
* analytic solutions of the heat equation, alpha = k/(rho c):
  T_w + (T_e - T_w) x/a + A sin(pi x/a) exp(-alpha pi^2 t/a^2) (slab, two
  Dirichlet walls); cos(lam x) exp(-alpha lam^2 t) with lam a tan(lam a) = beta
  (insulated left wall, Robin gradient right wall); J0(lam r) exp(-alpha lam^2 t)
  (cylinder); sin(lam r)/r exp(-alpha lam^2 t) (sphere);
* a hand-written div(kappa(r) grad T) for a radius-dependent conductivity;
* the nondimensionalization core's own dimensional analysis (``analizar_modelo``)
  of the published document, which checks every equation and condition for
  dimensional homogeneity independently of the deduction kernel.
"""
import copy
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mpmath as mp
import sympy as sp

from core.adimensionalizacion.dimensional import analizar_modelo
from core.adimensionalizacion.lector import leer_modelo
from core.mathematics.graph import EquationGraph
from core.mathematics.publication import PublicationError, spatial_publication, terminal_rows, to_matematico
from core.modelo.equation_workbench import build, describe, edit
from test_boundary_conditions import Session, symbols
from test_operator_expansion import FLUX, TEMPERATURE, expanded, heat_pde, source
from test_requires_discretization import fick_model

mp.mp.dps = 30


# --- Independent evaluator of the published trees --------------------------------

def evaluate(tree, env, fields):
    """Value of a v2 expression tree. ``env`` maps symbol ids to numbers, ``fields`` field ids to callables
    of their arguments (``dependeDe`` order); derivatives are mpmath numerical differentiation."""
    kind = tree['tipo']
    if kind == 'numero':
        return mp.mpf(tree['valor'])
    if kind == 'simbolo':
        name = tree['id']
        if name in fields:
            function, arguments = fields[name]
            return function(*(env[a] for a in arguments))
        return env[name]
    if kind == 'suma':
        return sum(evaluate(a, env, fields) for a in tree['argumentos'])
    if kind == 'producto':
        result = mp.mpf(1)
        for a in tree['argumentos']:
            result *= evaluate(a, env, fields)
        return result
    if kind == 'cociente':
        return evaluate(tree['numerador'], env, fields) / evaluate(tree['denominador'], env, fields)
    if kind == 'potencia':
        return evaluate(tree['base'], env, fields) ** evaluate(tree['exponente'], env, fields)
    if kind == 'funcion':
        return getattr(mp, {'abs': 'fabs'}.get(tree['nombre'], tree['nombre']))(evaluate(tree['argumentos'][0], env, fields))
    if kind == 'derivada':
        variable = tree['respecto']
        return mp.diff(lambda v: evaluate(tree['expresion'], {**env, variable: v}, fields), env[variable], tree['orden'])
    raise AssertionError('unsupported tree ' + kind)


def residual(equation, env, fields):
    return evaluate(equation['izquierda'], env, fields) - evaluate(equation['derecha'], env, fields)


def by_id(rows, key):
    return next(row for row in rows if row['id'] == key)


def slab(session, pde, upper='10', chart='cartesian'):
    return session.append(kind='declare_spatial_domain', sources=[pde], chart=chart, coordinates=[session.id('x')],
                          intervals=[{'lower': '0', 'upper': upper, 'lowerOpen': False, 'upperOpen': False, 'endpointUnit': 'cm'}],
                          parts=[{'name': 'left', 'coordinate': session.id('x'), 'end': 'lower'},
                                 {'name': 'right', 'coordinate': session.id('x'), 'end': 'upper'}],
                          reason='Plane slab 0 <= x <= 10 cm')


def slab_model(declare, conditions):
    """Conduction slab with a Fourier closure, expanded in x; ``conditions`` appends the typed conditions."""
    s = Session(source())
    _, pde = heat_pde(s)
    region = slab(s, pde)
    key = s.append(kind='expand_spatial_operators', sources=[pde], domains=[region])
    symbols(s, **declare)
    rows = conditions(s, key, region)
    return s, key, region, rows


class SlabDirichletTest(unittest.TestCase):
    def setUp(self):
        self.s, self.pde, self.region, self.rows = slab_model(
            dict(T_w='K', T_e='K', T_0='K'),
            lambda s, key, region: dict(
                left=s.append(kind='declare_condition', conditionKind='dirichlet', sources=[key], domains=[region], boundary='left',
                              symbol=s.id('T(x, t)'), right=s.id('T_w'), reason='Left wall at T_w'),
                right=s.append(kind='declare_condition', conditionKind='dirichlet', sources=[key], domains=[region], boundary='right',
                               symbol=s.id('T(x, t)'), right=s.id('T_e'), reason='Right wall at T_e'),
                initial=s.append(kind='declare_condition', conditionKind='initial', sources=[key], domains=[region], symbol=s.id('T(x, t)'),
                                 time=s.id('t'), instant='0', instantUnit='s', right=s.id('T_0'), reason='Uniform start')))
        self.result = self.s.result()
        self.block = spatial_publication(self.result.graph, self.result.selected, self.result.units)

    def test_block_requires_discretization_and_names_the_current_system(self):
        block = self.block
        self.assertTrue(block['requiresDiscretization'])
        self.assertEqual(block['handoff'], 'transform')
        self.assertEqual(block['solve'], {'accepted': False, 'code': 'requires_discretization'})
        self.assertEqual([f['equationId'] for f in block['fieldEquations']], [self.pde])
        self.assertEqual({f['equationId'] for f in block['conditions']}, set(self.rows.values()))
        self.assertEqual(block['adapterFindings'], [])
        domain = block['domains'][0]
        self.assertEqual(domain['chart'], 'cartesian')
        self.assertEqual(domain['coordinates'], [{'name': 'x', 'lower': '0', 'upper': '1/10', 'unit': 'm', 'lowerOpen': False, 'upperOpen': False}])
        self.assertEqual([(p['name'], p['point'], p['outwardNormal']) for p in domain['parts']], [('left', '0', -1), ('right', '1/10', 1)])
        # Superseded steps (unexpanded PDE, closure, assumptions) are not part of the published system.
        self.assertEqual(set(terminal_rows(self.result.graph, self.result.selected)), {self.pde, *self.rows.values()})
        for finding in block['findings']:
            self.assertIn('spatial discretization is deferred (F7)', finding['message'])

    def test_document_is_a_valid_v2_model_with_located_conditions(self):
        model = self.block['matematico']
        leer_modelo(json.loads(json.dumps(model)), 'matematico', version=2)
        roles = {s['id']: s['rol'] for s in model['simbolos']}
        self.assertEqual((roles['x'], roles['t'], roles['T']), ('coordenada', 'tiempo', 'campo'))
        self.assertEqual(next(s for s in model['simbolos'] if s['id'] == 'T')['dependeDe'], ['x', 't'])
        self.assertEqual(next(s for s in model['simbolos'] if s['id'] == 'k')['signo'], 'positivo')
        types = {c['id']: (c['tipo'], c['ubicacion']['variableId'], c['ubicacion']['extremo']) for c in model['condiciones']}
        self.assertEqual(types, {self.rows['left'] + '.condition': ('dirichlet', 'x', 'desde'),
                                 self.rows['right'] + '.condition': ('dirichlet', 'x', 'hasta'),
                                 self.rows['initial'] + '.condition': ('inicial', 't', 'desde')})
        x_domain = next(d for d in model['dominios'] if d['variableId'] == 'x')
        # v2 trees have no unit literal: the nonzero end is a declared length parameter whose exact SI value travels in the block.
        self.assertEqual((x_domain['desde'], x_domain['hasta']), ({'tipo': 'numero', 'valor': 0}, {'tipo': 'simbolo', 'id': 'x_upper'}))
        self.assertEqual(self.block['values'], {'x_upper': {'value': '1/10', 'unit': 'm'}})
        upper = next(s for s in model['simbolos'] if s['id'] == 'x_upper')
        self.assertEqual((upper['rol'], upper['dimension'], upper['signo']), ('parametro', {'L': {'n': 1, 'd': 1}}, 'positivo'))
        # The final time is a Solve datum and appears as a declared positive parameter.
        self.assertEqual(next(s for s in model['simbolos'] if s['id'] == 't_end')['signo'], 'positivo')

    def test_dimensional_analysis_of_the_nondimensionalization_core_accepts_the_document(self):
        analysis = analizar_modelo(self.block['matematico'])
        errors = [d for d in analysis['diagnosticos'] if d['severidad'] == 'error']
        self.assertEqual(errors, [])

    def test_analytic_solution_satisfies_the_published_equation_and_conditions(self):
        model = self.block['matematico']
        a, kk, rho, c = mp.mpf(1) / 10, mp.mpf(15), mp.mpf(7800), mp.mpf(460)
        alpha = kk / (rho * c)
        Tw, Te, A = mp.mpf(400), mp.mpf(300), mp.mpf(25)
        T = lambda x, t: Tw + (Te - Tw) * x / a + A * mp.sin(mp.pi * x / a) * mp.exp(-alpha * mp.pi ** 2 * t / a ** 2)  # noqa: E731
        fields = {'T': (T, ['x', 't'])}
        env = {'k': kk, 'rho_mixture__v1': rho, 'c': c, 'T_w': Tw, 'T_e': Te}
        for x, t in ((a / 3, mp.mpf(10)), (a / 7, mp.mpf(200)), (0.8 * a, mp.mpf(1000))):
            self.assertLess(abs(residual(by_id(model['ecuaciones'], self.pde), {**env, 'x': x, 't': t}, fields)), 1e-6)
        # Dirichlet walls: the condition equation is written on the field, located by ubicacion.
        for key, point in ((self.rows['left'], 0), (self.rows['right'], a)):
            equation = by_id(model['condiciones'], key + '.condition')['ecuacion']
            self.assertLess(abs(residual(equation, {**env, 'x': mp.mpf(point), 't': mp.mpf(37)}, fields)), 1e-20)
        # A wrong wall temperature leaves an O(1) residual (the check can fail).
        equation = by_id(model['condiciones'], self.rows['left'] + '.condition')['ecuacion']
        self.assertGreater(abs(residual(equation, {**env, 'T_w': Tw + 5, 'x': mp.mpf(0), 't': mp.mpf(37)}, fields)), 4)
        # Initial condition on a uniform state at the initial instant.
        uniform = {'T': (lambda x, t: mp.mpf(350), ['x', 't'])}
        equation = by_id(model['condiciones'], self.rows['initial'] + '.condition')['ecuacion']
        self.assertLess(abs(residual(equation, {**env, 'T_0': mp.mpf(350), 'x': a / 2, 't': mp.mpf(0)}, uniform)), 1e-20)

    def test_publication_is_replayable_and_follows_undo(self):
        recorded = copy.deepcopy(self.s.definition)
        again = self.s.result(json.loads(json.dumps(recorded)))
        self.assertEqual(json.dumps(spatial_publication(again.graph, again.selected, again.units), sort_keys=True),
                         json.dumps(self.block, sort_keys=True))
        for _ in range(7):  # three conditions, three symbol declarations and the expansion
            self.s.action({'kind': 'undo'})
        undone = self.s.result()
        block = spatial_publication(undone.graph, undone.selected, undone.units)
        # Back at the unexpanded deduction: the field keeps the Cartesian placeholder arguments, which the adapter
        # reports (with the divergence kept as a typed operator) rather than silently restating them.
        self.assertEqual([f['equationId'] for f in block['fieldEquations']], ['operation.8'])
        self.assertEqual(block['fieldEquations'][0]['operators'], ['Divergence', 'Gradient'])
        self.assertEqual(block['conditions'], [])


class RobinCylinderSphereTest(unittest.TestCase):
    def test_insulated_left_and_robin_right_walls_match_the_eigenfunction(self):
        s, pde, region, rows = slab_model(
            dict(beta='1/m', T_inf='K'),
            lambda s, key, region: dict(
                left=s.append(kind='declare_condition', conditionKind='neumann', sources=[key], domains=[region], boundary='left',
                              symbol=s.id('T(x, t)'), right='0', reason='Insulated wall'),
                right=s.append(kind='declare_condition', conditionKind='robin', sources=[key], domains=[region], boundary='right',
                               symbol=s.id('T(x, t)'), coefficient=s.id('beta'), right=s.id('T_inf'), reason='Newton cooling, beta = h/k')))
        result = s.result()
        block = spatial_publication(result.graph, result.selected, result.units)
        model = block['matematico']
        types = {c['id']: (c['tipo'], c['ubicacion']['extremo']) for c in model['condiciones']}
        self.assertEqual(types, {rows['left'] + '.condition': ('flujo', 'desde'), rows['right'] + '.condition': ('mixta', 'hasta')})
        a, beta = mp.mpf(1) / 10, mp.mpf(30)
        lam = mp.findroot(lambda v: v * mp.tan(v * a) - beta, 8 / a / 3)
        alpha = mp.mpf(15) / (mp.mpf(7800) * mp.mpf(460))
        T = lambda x, t: mp.cos(lam * x) * mp.exp(-alpha * lam ** 2 * t)  # noqa: E731
        fields = {'T': (T, ['x', 't'])}
        env = {'k': mp.mpf(15), 'rho_mixture__v1': mp.mpf(7800), 'c': mp.mpf(460), 'beta': beta, 'T_inf': mp.mpf(0)}
        for t in (mp.mpf(0), mp.mpf(0.7), mp.mpf(30)):
            self.assertLess(abs(residual(by_id(model['condiciones'], rows['left'] + '.condition')['ecuacion'], {**env, 'x': mp.mpf(0), 't': t}, fields)), 1e-18)
            self.assertLess(abs(residual(by_id(model['condiciones'], rows['right'] + '.condition')['ecuacion'], {**env, 'x': a, 't': t}, fields)), 1e-15)
            self.assertLess(abs(residual(by_id(model['ecuaciones'], pde), {**env, 'x': a / 2, 't': t}, fields)), 1e-12)
        # The wrong sign of the Robin law (cooling replaced by heating) is detected.
        wrong = {**env, 'beta': -beta}
        self.assertGreater(abs(residual(by_id(model['condiciones'], rows['right'] + '.condition')['ecuacion'], {**wrong, 'x': a, 't': mp.mpf(0)}, fields)), 1)
        self.assertEqual([d for d in analizar_modelo(model)['diagnosticos'] if d['severidad'] == 'error'], [])

    def test_cylinder_matches_bessel_solution(self):
        s, key = expanded('cylindrical', ['r'])
        result = s.result()
        model = to_matematico(result.graph, [key], result.units)
        leer_modelo(model, 'matematico', version=2)
        lam, alpha = mp.mpf(24), mp.mpf(15) / (mp.mpf(7800) * mp.mpf(460))
        T = lambda r, t: mp.besselj(0, lam * r) * mp.exp(-alpha * lam ** 2 * t)  # noqa: E731
        fields = {'T': (T, ['r', 't'])}
        env = {'k': mp.mpf(15), 'rho_mixture__v1': mp.mpf(7800), 'c': mp.mpf(460)}
        for r, t in ((mp.mpf('0.03'), mp.mpf(5)), (mp.mpf('0.09'), mp.mpf(40))):
            self.assertLess(abs(residual(model['ecuaciones'][0], {**env, 'r': r, 't': t}, fields)), 1e-7)
        wrong = {'T': (lambda r, t: mp.sin(lam * r) / r * mp.exp(-alpha * lam ** 2 * t), ['r', 't'])}
        self.assertGreater(abs(residual(model['ecuaciones'][0], {**env, 'r': mp.mpf('0.03'), 't': mp.mpf(5)}, wrong)), 1e-3)
        self.assertEqual([d for d in analizar_modelo(model)['diagnosticos'] if d['severidad'] == 'error'], [])

    def test_sphere_with_radius_dependent_conductivity_matches_a_hand_divergence(self):
        s, key = expanded('spherical', ['r'], coefficient='kappa')
        result = s.result()
        model = to_matematico(result.graph, [key], result.units)
        leer_modelo(model, 'matematico', version=2)
        kappa = lambda r: 1 + 40 * r ** 2  # noqa: E731
        T = lambda r, t: (r ** 3 - 5 * r ** 2) * mp.exp(-t)  # noqa: E731
        fields = {'T': (T, ['r', 't']), 'kappa': (kappa, ['r'])}
        env = {'rho_mixture__v1': mp.mpf(2), 'c': mp.mpf(3)}
        for r, t in ((mp.mpf('0.4'), mp.mpf(0)), (mp.mpf('1.3'), mp.mpf('0.5'))):
            # Hand form: rho c T_t - (1/r^2) d/dr (r^2 kappa T_r)
            reference = env['rho_mixture__v1'] * env['c'] * mp.diff(lambda tt: T(r, tt), t) \
                - mp.diff(lambda rr: rr ** 2 * kappa(rr) * mp.diff(lambda q: T(q, t), rr), r) / r ** 2
            self.assertLess(abs(residual(model['ecuaciones'][0], {**env, 'r': r, 't': t}, fields) - reference), 1e-12)
        self.assertEqual(next(s for s in model['simbolos'] if s['id'] == 'kappa')['dependeDe'], ['r'])

    def test_sphere_matches_sin_lambda_r_over_r(self):
        s, key = expanded('spherical', ['r'])
        result = s.result()
        model = to_matematico(result.graph, [key], result.units)
        lam, alpha = mp.mpf(31), mp.mpf(15) / (mp.mpf(7800) * mp.mpf(460))
        fields = {'T': (lambda r, t: mp.sin(lam * r) / r * mp.exp(-alpha * lam ** 2 * t), ['r', 't'])}
        env = {'k': mp.mpf(15), 'rho_mixture__v1': mp.mpf(7800), 'c': mp.mpf(460)}
        self.assertLess(abs(residual(model['ecuaciones'][0], {**env, 'r': mp.mpf('0.05'), 't': mp.mpf(3)}, fields)), 1e-6)


class LocatedRejectionsTest(unittest.TestCase):
    def test_untyped_normal_flux_is_rejected_at_its_row(self):
        s = Session(source())
        _, pde = heat_pde(s)
        region = slab(s, pde)
        symbols(s, q_w='W/m2')
        flux = [q for q in s.result().units if str(q).startswith('heat_flux_energy__')][0]
        neumann = s.append(kind='declare_condition', conditionKind='neumann', form='flux', sources=[s.result().selected[0]], domains=[region], boundary='right',
                           symbol=s.id(str(flux)), right=s.id('q_w'), reason='Prescribed heat flux')
        result = s.result()
        with self.assertRaisesRegex(PublicationError, neumann + ': a normal flux component is still untyped'):
            to_matematico(result.graph, [neumann], result.units)
        block = spatial_publication(result.graph, result.selected, result.units)
        self.assertIsNone(block['matematico'])
        self.assertIn(neumann, block['adapterFindings'][0]['message'])
        self.assertTrue(block['requiresDiscretization'])

    def test_field_with_two_argument_sets_is_rejected(self):
        s, key = expanded('cartesian', ['x'])
        result = s.result()
        unexpanded = next(r for r in result.selected if r != key and isinstance(result.graph.nodes[r].equation, sp.Equality)
                          and result.graph.nodes[r].equation.has(sp.Function('T')(*sp.symbols('x y z t', real=True))))
        with self.assertRaisesRegex(PublicationError, 'the field T occurs with different arguments'):
            to_matematico(result.graph, [unexpanded, key], result.units)

    def test_row_without_spatial_content_and_nonspatial_graph(self):
        s, key = expanded('cartesian', ['x'])
        result = s.result()
        with self.assertRaisesRegex(PublicationError, 'No selected row has spatial content'):
            to_matematico(result.graph, ['operation.1.missing'], result.units)
        t, k, f = sp.Symbol('t', real=True), sp.Symbol('k', real=True), sp.Function('f')
        graph = EquationGraph()
        graph.add('decay', sp.Derivative(f(t), t), -k * f(t), 'Decay', 'declared_law')
        self.assertIsNone(spatial_publication(graph, ['decay'], {}))

    def test_continuity_is_not_published_yet(self):
        s = Session(source())
        _, pde = heat_pde(s)
        region = slab(s, pde)
        # Hand-built interface relation between two fields: only its translation is exercised.
        T1, T2 = (sp.Function(n)(*sp.symbols('x t', real=True)) for n in ('T1', 'T2'))
        x, t = sp.symbols('x t', real=True)
        from core.mathematics.operators import BoundaryTrace
        result = s.result()
        graph = copy.deepcopy(result.graph)
        graph.add('interface', BoundaryTrace(T1, x, sp.Rational(1, 10)), BoundaryTrace(T2, x, sp.Rational(1, 10)), 'Continuity', 'boundary_condition',
                  (pde, region), ('Perfect contact',), 'energy', kind='constraint')
        with self.assertRaisesRegex(PublicationError, 'continuity across an interface is not published yet'):
            to_matematico(graph, ['interface'], result.units)


class WorkbenchReportTest(unittest.TestCase):
    def test_report_carries_the_block_only_for_spatial_models(self):
        model, names, datum = fick_model()
        report = describe(model)
        # Spatial producer rows without a declared typed domain are not published as a spatial model;
        # Solve still rejects them with the located requires_discretization diagnostic.
        self.assertNotIn('spatial', report)
        x = names['x']
        report = edit(model, {'kind': 'append', 'operation': {
            'family': 'matter', 'kind': 'declare_spatial_domain', 'sources': ['matter.v1.1.operators'], 'chart': 'cartesian', 'coordinates': [x],
            'intervals': [{'lower': '0', 'upper': '1', 'lowerOpen': False, 'upperOpen': False, 'endpointUnit': 'cm'}],
            'parts': [{'name': 'wall', 'coordinate': x, 'end': 'upper'}], 'reason': 'Diffusion slab 0 <= x <= 1 cm'}})
        block = report['spatial']
        self.assertTrue(block['requiresDiscretization'])
        self.assertEqual([f['equationId'] for f in block['fieldEquations']], ['matter.v1.1.operators'])
        self.assertEqual(block['domains'][0]['parts'], [{'name': 'wall', 'coordinate': 'x', 'end': 'upper', 'point': '1/100', 'outwardNormal': 1}])
        self.assertEqual(block['findings'][0]['equationId'], 'matter.v1.1.operators')
        # The unexpanded local form keeps its divergence as a typed v2 operator, or a located adapter finding says why not.
        self.assertTrue(block['matematico'] is not None or block['adapterFindings'])
        self.assertFalse(report['execution']['supported'] and report['spatial']['solve']['accepted'])


if __name__ == '__main__':
    unittest.main()
