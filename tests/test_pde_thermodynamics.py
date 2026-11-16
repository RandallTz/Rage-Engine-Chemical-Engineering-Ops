"""PDE-6: pointwise thermodynamic contract by homogeneity (no discretization).

The volume's own thermodynamic relations, as the thermodynamic producer records
them (Euler relation of the fundamental equation, Gibbs-Duhem, G = sum mu_i n_i),
are carried to every point of a declared spatial domain by the recorded rule
``localize_by_homogeneity``: a symbolic first-order homogeneity check, one
density definition X = V x_v per extensive quantity, one local-equilibrium
restatement per intensive quantity, and an exact division by V.

Independent reference (nothing below uses the kernel to check itself): an
ideal-gas mixture written by hand in density form with mpmath,

    u_v = sum c_i (u0_i + cv_i (T - T0)),
    s_v = sum c_i (s0_i + cv_i ln(T/T0) - R ln(c_i/c0)),
    a_v = u_v - T s_v,  mu_i = d a_v / d c_i (mpmath numerical derivative),
    P = sum c_i R T,

whose Euler relation u_v = T s_v - P + sum mu_i c_i and local Gibbs-Duhem
relation sum c_i d mu_i = -s_v dT + dP (along any spatial direction) hold at
every point; the localized rows are evaluated on arbitrary smooth profiles.
"""
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mpmath as mp
import sympy as sp
from sympy.core.function import AppliedUndef

from core.adimensionalizacion.dimensional import analizar_modelo
from core.mathematics.errors import MathematicsError
from core.mathematics.localization import homogeneity_degree
from core.mathematics.operators import StateDifferential, requires_discretization
from core.modelo.equation_workbench import build
from core.modelo.operation_journal import JournalError
from test_pde_acceptance import Workbench
from test_requires_discretization import fick_model

mp.mp.dps = 30
R = mp.mpf('8.314462618')
X, T_ = sp.symbols('x t', real=True)
EXTENSIVE = ('V__v1(t)', 'U__v1(t)', 'S__v1(t)', 'n_1__v1(t)', 'n_2__v1(t)', 'G__v1(t)')


def localized_model(rows):
    """Fick slab domain plus localizations of the named thermodynamic rows through the workbench API."""
    model, names, _ = fick_model()
    w = Workbench(model, 'matter')
    region = w.append(kind='declare_spatial_domain', sources=['matter.v1.1.operators'], chart='cartesian', coordinates=[names['x']],
                      intervals=[{'lower': '0', 'upper': '1', 'lowerOpen': False, 'upperOpen': False, 'endpointUnit': 'cm'}], parts=[],
                      reason='Binary mixture in a 1 cm slab')
    w.family = 'thermodynamics'
    keys = {}
    for row in rows:
        result = build(w.model)
        ids = w.ids()
        equation = result.graph.nodes[row].equation
        extensive = [ids[name] for name in EXTENSIVE if name != 'V__v1(t)' and equation.has(_quantity(name))]
        keys[row] = w.append(kind='localize_by_homogeneity', sources=[row], domains=[region], symbol=ids['V__v1(t)'], extensive=extensive,
                             reason='Local equilibrium of the mixture at every point of the slab')
    return w, region, keys


def _quantity(name):
    return sp.Function(name.split('(')[0])(T_)


def field(name):
    return sp.Function(name)(X, T_)


# --- Independent ideal-gas mixture in density form ------------------------------------------------

T0, c0 = mp.mpf(298), mp.mpf(40)
U0, CV, S0 = (mp.mpf(-1000), mp.mpf(2500)), (mp.mpf('20.8'), mp.mpf('28.9')), (mp.mpf(150), mp.mpf(190))


def u_v(T, c):
    return sum(ci * (U0[i] + CV[i] * (T - T0)) for i, ci in enumerate(c))


def s_v(T, c):
    return sum(ci * (S0[i] + CV[i] * mp.log(T / T0) - R * mp.log(ci / c0)) for i, ci in enumerate(c))


def a_v(T, c):
    return u_v(T, c) - T * s_v(T, c)


def mu(T, c, i):
    return mp.diff(lambda value: a_v(T, [value if j == i else cj for j, cj in enumerate(c)]), c[i])


def pressure(T, c):
    return sum(c) * R * T


def profile(x):
    """Arbitrary smooth temperature and concentration profiles along the slab (x in m)."""
    return 300 + 4000 * x ** 2, [30 + 200 * x, 12 - 300 * x ** 2]


class LocalizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w, cls.region, cls.keys = localized_model(['thermodynamics.v1.extensivity', 'thermodynamics.v1.gibbs-duhem', 'thermodynamics.v1.G-euler'])
        cls.result = build(cls.w.model)
        cls.graph = cls.result.graph
        # Real report for the frontend reader (frontend/verificar_equation_workbench.mjs).
        target = Path(__file__).resolve().parents[1] / '.tmp' / 'equation-workbench-localization.json'
        target.parent.mkdir(exist_ok=True)
        target.write_text(json.dumps(cls.w.report), encoding='utf8')

    def test_recorded_steps_and_hand_forms(self):
        g = self.graph
        euler, duhem, gibbs = (self.keys[k] for k in ('thermodynamics.v1.extensivity', 'thermodynamics.v1.gibbs-duhem', 'thermodynamics.v1.G-euler'))
        T, P, m1, m2 = field('T__v1'), field('P__v1'), field('mu_1__v1'), field('mu_2__v1')
        u, s, c1, c2, gv = (field(n) for n in ('U_density__v1', 'S_density__v1', 'n_1_density__v1', 'n_2_density__v1', 'G_density__v1'))
        hand = {euler: sp.Eq(u, T * s - P + m1 * c1 + m2 * c2),
                duhem: sp.Eq(c1 * StateDifferential(m1) + c2 * StateDifferential(m2), -s * StateDifferential(T) + StateDifferential(P)),
                gibbs: sp.Eq(gv, m1 * c1 + m2 * c2)}
        for key, expected in hand.items():
            equation = g.nodes[key].equation
            self.assertEqual(sp.expand(equation.lhs - equation.rhs - (expected.lhs - expected.rhs)), 0, key)
            self.assertEqual(g.nodes[key].rule, 'localization_by_homogeneity')
            substituted = g.nodes[key].inputs[0]
            self.assertEqual(g.nodes[substituted].rule, 'substitution')
            self.assertTrue(any('Euler homogeneity of degree 1' in a for a in g.nodes[key].assumptions))
        # Before the division the volume is explicit: U = V u, V = V, n_i = V c_i.
        V = sp.Function('V__v1')(T_)
        before = g.nodes[g.nodes[euler].inputs[0]].equation
        self.assertEqual(sp.expand(before.lhs - before.rhs - V * (u - T * s + P - m1 * c1 - m2 * c2)), 0)
        # One density definition per extensive quantity on the domain, shared by the three localizations.
        definitions = [k for k, n in g.nodes.items() if n.rule == 'density_definition']
        self.assertEqual(sorted(str(g.nodes[k].equation.lhs) for k in definitions),
                         sorted(['G__v1(t)', 'S__v1(t)', 'U__v1(t)', 'n_1__v1(t)', 'n_2__v1(t)']))
        self.assertEqual(self.result.units[c1], '(mol)/(m3)')
        self.assertEqual(self.result.units[s], '(J/K)/(m3)')

    def test_ideal_gas_satisfies_the_localized_euler_and_gibbs_duhem_relations(self):
        g = self.graph
        euler, duhem = g.nodes[self.keys['thermodynamics.v1.extensivity']].equation, g.nodes[self.keys['thermodynamics.v1.gibbs-duhem']].equation
        x0 = mp.mpf('0.004')
        names = {'T__v1': lambda x: profile(x)[0], 'P__v1': lambda x: pressure(*profile(x)),
                 'n_1_density__v1': lambda x: profile(x)[1][0], 'n_2_density__v1': lambda x: profile(x)[1][1],
                 'U_density__v1': lambda x: u_v(*profile(x)), 'S_density__v1': lambda x: s_v(*profile(x)),
                 'mu_1__v1': lambda x: mu(*profile(x), 0), 'mu_2__v1': lambda x: mu(*profile(x), 1)}

        def evaluate(expression, wrong=None):
            values = {**names, **(wrong or {})}
            numbers = {}
            for d in expression.atoms(StateDifferential):  # a differential along the slab direction x
                numbers[d] = sp.Float(str(mp.diff(values[d.args[0].func.__name__], x0)), 30)
            for f in expression.atoms(AppliedUndef):
                if f.func.__name__ in values:
                    numbers[f] = sp.Float(str(values[f.func.__name__](x0)), 30)
            return sp.N(expression.xreplace(numbers), 30)

        scale = abs(evaluate(euler.lhs))
        self.assertLess(abs(evaluate(euler.lhs - euler.rhs)), 1e-20 * scale)
        dscale = abs(evaluate(duhem.lhs))
        self.assertGreater(dscale, 1)
        self.assertLess(abs(evaluate(duhem.lhs - duhem.rhs)), 1e-15 * dscale)
        # Controls: a pressure that is not the ideal-gas one breaks both relations.
        wrong = {'P__v1': lambda x: 1.1 * pressure(*profile(x))}
        self.assertGreater(abs(evaluate(euler.lhs - euler.rhs, wrong)), 1e-3 * scale)
        self.assertGreater(abs(evaluate(duhem.lhs - duhem.rhs, wrong)), 1e-3 * dscale)

    def test_published_with_the_field_model_and_rejected_by_solve(self):
        rows = list(self.keys.values())
        located = [f['equationId'] for f in requires_discretization(self.graph, rows, None)]
        self.assertEqual(sorted(located), sorted(rows))
        spatial = self.w.report['spatial']
        self.assertTrue(set(rows) <= {f['equationId'] for f in spatial['fieldEquations']})
        self.assertIs(self.w.report['execution']['supported'], False)
        # A differential relation has no v2 image: the adapter says so at its row instead of dropping it.
        self.assertEqual([(f['code'], f['equationId']) for f in spatial['adapterFindings']],
                         [('unsupported_operator', self.keys['thermodynamics.v1.gibbs-duhem'])])


class AlgebraicPublicationTest(unittest.TestCase):
    def test_algebraic_localizations_publish_a_dimensioned_v2_document(self):
        w, _, keys = localized_model(['thermodynamics.v1.extensivity', 'thermodynamics.v1.G-euler'])
        spatial = w.report['spatial']
        self.assertEqual(spatial['adapterFindings'], [])
        document = spatial['matematico']
        symbols = {s['id']: (s['rol'], s['dimension']) for s in document['simbolos']}
        self.assertEqual(symbols['U_density__v1'], ('campo', {'M': {'n': 1, 'd': 1}, 'L': {'n': -1, 'd': 1}, 'T': {'n': -2, 'd': 1}}))
        self.assertEqual(symbols['n_1_density__v1'], ('campo', {'N': {'n': 1, 'd': 1}, 'L': {'n': -3, 'd': 1}}))
        self.assertEqual(symbols['T__v1'][0], 'campo')
        self.assertEqual([d for d in analizar_modelo(document)['diagnosticos'] if d['severidad'] == 'error'], [])
        self.assertTrue({keys['thermodynamics.v1.extensivity'], keys['thermodynamics.v1.G-euler']} <= {e['id'] for e in document['ecuaciones']})


class RejectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.w, cls.region, _ = localized_model([])
        cls.ids = cls.w.ids()

    def attempt(self, row, extensive, symbol='V__v1(t)'):
        with self.assertRaises((JournalError, MathematicsError)) as raised:
            self.w.append(kind='localize_by_homogeneity', sources=[row], domains=[self.region], symbol=self.ids[symbol],
                          extensive=[self.ids[e] for e in extensive], reason='probe')
        return str(raised.exception)

    def test_differentials_of_extensive_quantities_are_rejected(self):
        message = self.attempt('thermodynamics.v1.dG', ['G__v1(t)', 'S__v1(t)', 'n_1__v1(t)', 'n_2__v1(t)'])
        self.assertIn('differential of an extensive quantity', message)

    def test_an_incomplete_extensive_set_is_not_homogeneous(self):
        message = self.attempt('thermodynamics.v1.G-euler', ['G__v1(t)'])
        self.assertIn('not homogeneous', message)

    def test_a_field_equation_is_not_a_volume_relation(self):
        self.w.family = 'matter'
        try:
            message = self.attempt('matter.v1.1.operators', ['n_1__v1(t)'])
        finally:
            self.w.family = 'thermodynamics'
        self.assertTrue('lumped volume relation' in message or 'must be a volume quantity' in message, message)

    def test_degree_zero_and_degree_one_by_scaling(self):
        U, S, V, n, T = (sp.Function(name)(T_) for name in ('U', 'S', 'V', 'n', 'T'))
        self.assertEqual(homogeneity_degree(sp.Eq(T, U / S), (U, S, V, n)), 0)
        self.assertEqual(homogeneity_degree(sp.Eq(U, T * S), (U, S, V, n)), 1)
        self.assertIsNone(homogeneity_degree(sp.Eq(U, T * S + sp.Symbol('b')), (U, S, V, n)))
        self.assertIsNone(homogeneity_degree(sp.Eq(U * S, T), (U, S, V, n)))


if __name__ == '__main__':
    unittest.main()
