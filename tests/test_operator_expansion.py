"""PDE-3: Fourier closure and chart expansion of spatial operators (no discretization).

The transient heat equation is deduced from the local first law produced by the
energy family through recorded operations only: rigid solid at rest, caloric
relation, uniform density, then the new ``declare_fourier_law`` rule and the
ordinary ``substitute``. ``expand_spatial_operators`` then restates the field
in the active coordinates of a declared spatial domain and expands the
divergence by its Lame-factor identity.

Independent references:

* separable analytic solutions of the heat equation, alpha = k/(rho c):
  sin(pi x/a) e^{-alpha pi^2 t/a^2} (slab); sin(pi x/a) sin(pi y/b) e^{...} (plate);
  J0(lambda r) e^{-alpha lambda^2 t} (cylinder); J0(lambda r) sin(mu z) e^{...}
  (finite cylinder); sin(lambda r)/r e^{-alpha lambda^2 t} (sphere);
* second-order Cartesian central finite differences of div(k grad T) at points
  (x, y[, z]) mapped to r, for a radius-dependent conductivity, which checks the
  cylindrical and spherical metric factors without using them.
"""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sympy as sp

from core.mathematics import expansion
from core.mathematics.contract import FORMAT, read_definition
from core.mathematics.errors import MathematicsError
from core.mathematics.operators import BoundaryFlux, Divergence, Gradient, VolumeIntegral, requires_discretization
from test_boundary_conditions import Session, heat_source

X, Y, Z, T_, R = sp.symbols('x y z t r', real=True)
FLUX = 'heat_flux_energy__v1(x, y, z, t)'
TEMPERATURE = 'T(x, y, z, t)'


def source():
    """Energy producer output without any hand-inserted Fourier node."""
    graph, final, owners, units = heat_source()
    del graph.nodes['fourier'], owners['fourier']
    final.remove('fourier')
    units[R] = 'm'
    return graph, final, owners, units


def fourier(session, coefficient='k', reason='Homogeneous isotropic solid'):
    law = session.result().selected[0]
    return session.append(kind='declare_fourier_law', sources=[law], symbol=session.id(FLUX), potential=session.id(TEMPERATURE),
                          coefficient=session.id(coefficient) if coefficient in session.ids() else coefficient,
                          reason=reason)


def heat_pde(session, coefficient='k'):
    """Local first law -> rho c dT/dt = -div(q), q closed by the recorded Fourier rule."""
    s = session
    law = s.result().selected[0]
    closure = fourier(s, coefficient)
    rest = s.append(kind='apply_zero', sources=[law], symbol=s.id('velocity_energy__v1(x, y, z, t)'),
                    reason='Rigid solid at rest: no convective transport and no pressure work')
    s.append(kind='declare_symbol', name='c', unit='J/(kg*K)')
    s.append(kind='declare_symbol', name='T_ref', unit='K')
    caloric = s.append(kind='declare_relation', relationKind='constitutive', left=s.id('u_specific__v1(x, y, z, t)'),
                       right=s.id('c')+'*('+s.id(TEMPERATURE)+'-'+s.id('T_ref')+')',
                       reason='Incompressible solid with constant specific heat capacity')
    heated = s.append(kind='substitute', sources=[rest], relation=caloric, symbol=s.id('u_specific__v1(x, y, z, t)'))
    rigid = s.append(kind='change_dependencies', sources=[heated], symbol=s.id('rho_mixture__v1(x, y, z, t)'), dependencies=[],
                     reason='Uniform and constant solid density')
    pde = s.append(kind='substitute', sources=[rigid], relation=closure, symbol=s.id(FLUX))
    return closure, pde


def domain(session, pde, chart, coordinates, lower='1', upper='10'):
    return session.append(kind='declare_spatial_domain', sources=[pde], chart=chart, coordinates=[session.id(c) for c in coordinates],
                          intervals=[{'lower': lower, 'upper': upper, 'lowerOpen': False, 'upperOpen': False, 'endpointUnit': 'cm'}
                                     for _ in coordinates],
                          parts=[], reason='Solid occupying the declared '+chart+' region')


def expanded(chart, coordinates, coefficient='k', lower='1'):
    s = Session(source())
    if coefficient != 'k':
        s.append(kind='declare_function', name='kappa', unit='W/(m*K)', dependencies=[s.id('r')])
        coefficient = s.id('kappa(r)')
    closure, pde = heat_pde(s, coefficient)
    region = domain(s, pde, chart, coordinates, lower)
    key = s.append(kind='expand_spatial_operators', sources=[pde], domains=[region])
    return s, key


def residual(equation, solution, field):
    """lhs - rhs with the field replaced by an explicit function of its arguments."""
    difference = equation.lhs - equation.rhs
    return difference.replace(lambda n: isinstance(n, sp.core.function.AppliedUndef) and n.func == field,
                              lambda n: solution).doit()


def numeric(expression, points, values):
    return [complex(expression.subs({**values, **point}).evalf(30)) for point in points]


class FourierLawTest(unittest.TestCase):
    def test_fourier_root_is_typed_constitutive_with_provenance_and_conditions(self):
        s = Session(source())
        key = fourier(s)
        result = s.result()
        node = result.graph.nodes[key]
        k = sp.Symbol('k', real=True)
        temperature = sp.Function('T')(X, Y, Z, T_)
        self.assertEqual(node.equation.rhs, -k*Gradient(temperature))
        self.assertEqual(str(node.equation.lhs), FLUX)
        self.assertEqual(node.kind, 'constitutive')
        self.assertFalse(node.dependent)
        self.assertEqual(node.source['citation'][:14], 'J. B. J. Fouri')
        self.assertIn('1822', node.source['citation'])
        self.assertIn(sp.Gt(k, 0, evaluate=False), node.predicates)
        conditions = result.graph.conditions_for(key)
        self.assertIn('Homogeneous isotropic solid', conditions)
        self.assertTrue(any('Dufour' in c for c in conditions))
        self.assertEqual(node.inputs, (result.selected[0],))
        self.assertIn(key, result.selected)
        self.assertTrue(result.requires_lowering)

    def test_dimension_mismatch_is_rejected(self):
        s = Session(source())
        s.append(kind='declare_symbol', name='kwrong', unit='W/(m^2*K)')
        with self.assertRaisesRegex(MathematicsError, 'Fourier law dimensions'):
            fourier(s, 'kwrong')

    def test_flux_must_be_under_a_divergence_of_the_selected_law(self):
        s = Session(source())
        s.append(kind='declare_function', name='qstray', unit='W/m^2', dependencies=[s.id(n) for n in 'xyzt'])
        law = s.result().selected[0]
        with self.assertRaisesRegex(MathematicsError, 'does not occur under a divergence'):
            s.append(kind='declare_fourier_law', sources=[law], symbol=s.id('qstray(x, y, z, t)'), potential=s.id(TEMPERATURE),
                     coefficient=s.id('k'))

    def test_potential_must_be_a_temperature_field(self):
        s = Session(source())
        law = s.result().selected[0]
        with self.assertRaisesRegex(MathematicsError, 'absolute temperature'):
            s.append(kind='declare_fourier_law', sources=[law], symbol=s.id(FLUX), potential=s.id('p__v1(x, y, z, t)'), coefficient=s.id('k'))

    def test_contract_shape(self):
        base = {'kind': 'declare_fourier_law', 'family': 'energy', 'sources': ['a'], 'symbol': 'q', 'potential': 'T', 'coefficient': 'k'}
        definition = lambda op: {'format': FORMAT, 'version': 1, 'operations': [op], 'cursor': 1}  # noqa: E731
        read_definition(definition(base))
        for broken in ({k: v for k, v in base.items() if k != 'coefficient'}, {**base, 'time': 't'}, {**base, 'domains': ['d']},
                       {**base, 'coefficient': ' '}):
            with self.assertRaises(MathematicsError):
                read_definition(definition(broken))
        expand = {'kind': 'expand_spatial_operators', 'family': 'energy', 'sources': ['a'], 'domains': ['d']}
        read_definition(definition(expand))
        for broken in ({**expand, 'domains': ['d', 'e']}, {k: v for k, v in expand.items() if k != 'domains'}, {**expand, 'potential': 'T'}):
            with self.assertRaises(MathematicsError):
                read_definition(definition(broken))


class AnalyticHeatSolutionTest(unittest.TestCase):
    k, rho, c = sp.symbols('k rho_mixture__v1 c', real=True)

    def check(self, chart, coordinates, solution, points):
        s, key = expanded(chart, coordinates)
        equation = s.result().graph.nodes[key].equation
        self.assertFalse(equation.has(Divergence, Gradient))
        values = {self.k: sp.Rational(3, 2), self.rho: sp.Integer(2), self.c: sp.Rational(7, 4)}
        value = residual(equation, solution.subs(values), sp.Function('T'))
        for number in numeric(value, points, values):
            self.assertLess(abs(number), 1e-20)
        return s, key, equation

    def alpha(self):
        return self.k/(self.rho*self.c)

    def test_cartesian_slab(self):
        a = sp.Rational(1, 10)
        solution = sp.sin(sp.pi*X/a)*sp.exp(-self.alpha()*sp.pi**2*T_/a**2)
        _, _, equation = self.check('cartesian', ['x'], solution, [{X: sp.Rational(1, 37), T_: sp.Rational(1, 300)}, {X: sp.Rational(7, 100), T_: 0}])
        self.assertEqual(equation.rhs, self.k*sp.Derivative(sp.Function('T')(X, T_), (X, 2)))

    def test_cartesian_plate(self):
        a, b = sp.Rational(1, 10), sp.Rational(1, 20)
        solution = sp.sin(sp.pi*X/a)*sp.sin(sp.pi*Y/b)*sp.exp(-self.alpha()*sp.pi**2*(1/a**2+1/b**2)*T_)
        self.check('cartesian', ['x', 'y'], solution, [{X: sp.Rational(1, 37), Y: sp.Rational(1, 53), T_: sp.Rational(1, 900)}])

    def test_cylinder(self):
        lam = sp.Integer(24)
        solution = sp.besselj(0, lam*R)*sp.exp(-self.alpha()*lam**2*T_)
        _, key, equation = self.check('cylindrical', ['r'], solution, [{R: sp.Rational(3, 100), T_: sp.Rational(1, 500)}, {R: sp.Rational(9, 100), T_: 0}])
        self.assertEqual(equation.rhs, self.k*sp.Derivative(R*sp.Derivative(sp.Function('T')(R, T_), R), R)/R)

    def test_finite_cylinder(self):
        lam, mu = sp.Integer(24), sp.Integer(31)
        solution = sp.besselj(0, lam*R)*sp.sin(mu*Z)*sp.exp(-self.alpha()*(lam**2+mu**2)*T_)
        self.check('cylindrical', ['r', 'z'], solution, [{R: sp.Rational(3, 100), Z: sp.Rational(2, 100), T_: sp.Rational(1, 700)}])

    def test_sphere(self):
        lam = sp.Integer(31)
        solution = sp.sin(lam*R)/R*sp.exp(-self.alpha()*lam**2*T_)
        _, _, equation = self.check('spherical', ['r'], solution, [{R: sp.Rational(3, 100), T_: sp.Rational(1, 500)}, {R: sp.Rational(8, 100), T_: 0}])
        self.assertEqual(equation.rhs, self.k*sp.Derivative(R**2*sp.Derivative(sp.Function('T')(R, T_), R), R)/R**2)

    def test_wrong_solution_leaves_a_residual(self):
        # Sanity check of the reference: the cylinder solution does not satisfy the spherical equation.
        lam = sp.Integer(24)
        s, key = expanded('spherical', ['r'])
        equation = s.result().graph.nodes[key].equation
        values = {self.k: sp.Rational(3, 2), self.rho: sp.Integer(2), self.c: sp.Rational(7, 4)}
        wrong = (sp.besselj(0, lam*R)*sp.exp(-self.alpha()*lam**2*T_)).subs(values)
        value = residual(equation, wrong, sp.Function('T'))
        self.assertGreater(abs(numeric(value, [{R: sp.Rational(3, 100), T_: 0}], values)[0]), 1e-3)


class FiniteDifferenceMetricTest(unittest.TestCase):
    """The expanded operator with k = kappa(r) against Cartesian central differences of div(k grad T)."""

    kappa = sp.Lambda(R, 1+40*R**2)
    temperature = sp.Lambda(R, R**3-5*R**2)  # a constant offset only adds round-off

    def operator(self, chart):
        s, key = expanded(chart, ['r'], coefficient='kappa')
        equation = s.result().graph.nodes[key].equation
        self.assertTrue(equation.rhs.has(sp.Function('kappa')(R)))
        rhs = equation.rhs.replace(lambda n: isinstance(n, sp.core.function.AppliedUndef) and n.func == sp.Function('kappa'),
                                   lambda n: self.kappa(n.args[0]))
        rhs = rhs.replace(lambda n: isinstance(n, sp.core.function.AppliedUndef) and n.func == sp.Function('T'),
                          lambda n: self.temperature(n.args[0]))
        return sp.lambdify(R, rhs.doit())

    def finite_difference(self, point, step=1e-4):
        k = sp.lambdify(R, self.kappa(R));T = sp.lambdify(R, self.temperature(R))
        radius = lambda p: sum(v*v for v in p)**0.5  # noqa: E731
        total = 0.0
        for axis in range(len(point)):
            def shifted(delta):
                p = list(point);p[axis] += delta;return p
            east = k(radius(shifted(step/2)))*(T(radius(shifted(step)))-T(radius(point)))
            west = k(radius(shifted(-step/2)))*(T(radius(point))-T(radius(shifted(-step))))
            total += (east-west)/step**2
        return total, radius(point)

    def test_cylindrical_metric(self):
        expanded_operator = self.operator('cylindrical')
        for point in ((0.03, 0.04), (0.05, -0.02), (-0.07, 0.01)):
            reference, r = self.finite_difference(point)
            self.assertAlmostEqual(expanded_operator(r)/reference, 1.0, places=5)

    def test_metric_term_is_resolved_by_the_reference(self):
        # Control: the Cartesian-looking operator d/dr(k dT/dr), without the 1/r metric term, misses the reference.
        flat = sp.lambdify(R, sp.diff(self.kappa(R)*sp.diff(self.temperature(R), R), R))
        reference, r = self.finite_difference((0.03, 0.04))
        self.assertGreater(abs(flat(r)/reference-1.0), 1e-2)

    def test_spherical_metric(self):
        expanded_operator = self.operator('spherical')
        for point in ((0.03, 0.04, 0.02), (0.05, -0.02, 0.06)):
            reference, r = self.finite_difference(point)
            self.assertAlmostEqual(expanded_operator(r)/reference, 1.0, places=5)

    def test_variable_conductivity_keeps_conservative_form_and_records_the_positive_premise_in_prose(self):
        s, key = expanded('cylindrical', ['r'], coefficient='kappa')
        graph = s.result().graph
        kappa = sp.Function('kappa')(R)
        temperature = sp.Function('T')(R, T_)
        self.assertEqual(graph.nodes[key].equation.rhs, sp.Derivative(R*kappa*sp.Derivative(temperature, R), R)/R)
        self.assertTrue(any('kappa(r) > 0' in condition for condition in graph.conditions_for(key)))


class ExpansionRecordTest(unittest.TestCase):
    def test_records_restatement_identity_and_conditions(self):
        s, key = expanded('cylindrical', ['r'])
        graph = s.result().graph
        restatement = graph.nodes[key+'.chart.1']
        self.assertEqual(restatement.kind, 'constraint')
        self.assertEqual(restatement.equation.rhs, sp.Function('T')(R, T_))
        self.assertIn('invariant along phi, z', restatement.assumptions[0])
        identity = graph.nodes[key+'.identity.1']
        self.assertEqual(identity.kind, 'definition')
        self.assertIsInstance(identity.equation.lhs, Divergence)
        self.assertIn(sp.Ne(R, 0, evaluate=False), graph.predicates_for(key))
        self.assertTrue(any('singular' in condition for condition in graph.conditions_for(key)))
        self.assertEqual(set(graph.nodes[key].inputs), {key+'.chart', key+'.identity.1'})
        self.assertTrue(graph.nodes[key].dependent)

    def test_expanded_row_still_requires_discretization(self):
        s, key = expanded('cartesian', ['x'])
        findings = requires_discretization(s.result().graph, [key])
        self.assertEqual(findings[0]['coordinates'], ['x'])
        self.assertEqual(findings[0]['operators'], [])

    def test_undo_redo_and_signature_pinning(self):
        s, key = expanded('cartesian', ['x'])
        cursor = s.definition['cursor']
        s.action({'kind': 'undo'})
        self.assertNotIn(key, s.result().graph.nodes)
        s.action({'kind': 'redo'})
        self.assertEqual(s.definition['cursor'], cursor)
        self.assertIn(key, s.result().graph.nodes)
        self.assertEqual(set(s.definition['operations'][-1]['sourceSignatures']), {*s.definition['operations'][-1]['sources'],
                                                                                    *s.definition['operations'][-1]['domains']})

    def test_new_fourier_law_feeds_the_pde2_boundary_projection(self):
        s = Session(source())
        closure, pde = heat_pde(s)
        region = domain(s, pde, 'cartesian', ['x'], lower='0')
        s.append(kind='declare_spatial_domain', sources=[closure], chart='cartesian', coordinates=[s.id('x')],
                 intervals=[{'lower': '0', 'upper': '10', 'lowerOpen': False, 'upperOpen': False, 'endpointUnit': 'cm'}],
                 parts=[{'name': 'wall', 'coordinate': s.id('x'), 'end': 'upper'}], reason='Wall at x = 10 cm')
        wall_domain = 'operation.'+str(s.definition['cursor'])
        projected = s.append(kind='restrict_to_boundary', sources=[closure], domains=[wall_domain], boundary='wall', form='flux')
        self.assertIn('NormalDerivative', sp.srepr(s.equation(projected)))
        self.assertIn(region, s.result().graph.spatial_domains)


class ExpansionRejectionTest(unittest.TestCase):
    def session(self):
        s = Session(source())
        closure, pde = heat_pde(s)
        return s, closure, pde

    def test_untyped_vector_flux_is_rejected(self):
        s = Session(source())
        law = s.result().selected[0]
        region = domain(s, law, 'cartesian', ['x'])
        with self.assertRaisesRegex(MathematicsError, 'untyped vector field'):
            s.append(kind='expand_spatial_operators', sources=[law], domains=[region])

    def test_equation_without_divergence_is_rejected(self):
        s, closure, pde = self.session()
        region = domain(s, pde, 'cartesian', ['x'])
        with self.assertRaisesRegex(MathematicsError, 'no divergence'):
            s.append(kind='expand_spatial_operators', sources=[closure], domains=[region])

    def direct(self, lhs, rhs, chart='cartesian', coordinates=('x',)):
        s, closure, pde = self.session()
        region = domain(s, pde, chart, list(coordinates))
        graph = copy.deepcopy(s.result().graph)
        graph.add('probe', lhs, rhs, 'Probe', 'declared_law', family='energy', kind='balance')
        return lambda: expansion.expand_spatial_operators(graph, 'probe.expanded', 'probe', region, 'energy')

    def test_gradient_outside_a_divergence_is_rejected(self):
        T = sp.Function('T')(X, Y, Z, T_);q = sp.Function('heat_flux_energy__v1')(X, Y, Z, T_)
        with self.assertRaisesRegex(MathematicsError, 'outside a divergence'):
            self.direct(Divergence(q)+Gradient(T), 0)()

    def test_nested_divergence_is_rejected(self):
        T = sp.Function('T')(X, Y, Z, T_)
        with self.assertRaisesRegex(MathematicsError, 'Nested divergences'):
            self.direct(Divergence(Divergence(Gradient(T))*Gradient(T)), 0)()

    def test_integral_form_is_rejected(self):
        T = sp.Function('T')(X, Y, Z, T_)
        with self.assertRaisesRegex(MathematicsError, 'local differential form'):
            self.direct(VolumeIntegral(T)+Divergence(Gradient(T)), 0)()

    def test_field_outside_the_chart_is_rejected(self):
        partial = sp.Function('T')(X, T_)
        with self.assertRaisesRegex(MathematicsError, 'outside the cylindrical chart'):
            self.direct(Divergence(Gradient(partial)), 0, 'cylindrical', ('r',))()

    def test_derivative_along_an_inactive_coordinate_is_rejected(self):
        T = sp.Function('T')(X, Y, Z, T_)
        with self.assertRaisesRegex(MathematicsError, 'not an active coordinate'):
            self.direct(sp.Derivative(T, Y)+Divergence(Gradient(T)), 0)()

    def test_explicit_inactive_coordinate_is_rejected(self):
        T = sp.Function('T')(X, Y, Z, T_)
        with self.assertRaisesRegex(MathematicsError, 'occurs explicitly'):
            self.direct(Divergence(Y*Gradient(T)), 0)()


if __name__ == '__main__':
    unittest.main()
