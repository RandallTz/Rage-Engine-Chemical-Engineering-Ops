"""PDE-1: typed spatial domain with oriented boundary parts (no discretization).

The domain is declared on a deduced field equation through the recorded
workbench rule `declare_spatial_domain`. Independent checks use plain SymPy
calculus, not the domain's own methods: the slab length equals the integral
of dx, and the outward normals reproduce Gauss's theorem in one dimension.
"""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import sympy as sp

from core.mathematics.contract import read_definition, FORMAT
from core.mathematics.domains import BoundaryPart, DomainPremise, SpatialDomain
from core.mathematics.errors import MathematicsError
from core.mathematics.operators import VolumeIntegral
from core.modelo.equation_workbench import build, edit
from core.compilador.derived import source_signature
from test_requires_discretization import fick_model

X = sp.Symbol('x', real=True)
R = sp.Symbol('r', real=True)
FIELD_ROW = 'matter.v1.1.operators'


def slab(lower='0', upper='1/100', parts=(('left', 'lower'), ('right', 'upper')), **extra):
    return SpatialDomain('cartesian', (X,), (DomainPremise(X, 'interval', lower=lower, upper=upper, **extra),),
                         tuple(BoundaryPart(name, X, end) for name, end in parts))


def operation(names, **changes):
    op = {'kind': 'declare_spatial_domain', 'family': 'matter', 'sources': [FIELD_ROW], 'chart': 'cartesian',
          'coordinates': [names['x']],
          'intervals': [{'lower': '0', 'upper': '1', 'lowerOpen': False, 'upperOpen': False, 'endpointUnit': 'cm'}],
          'parts': [{'name': 'left', 'coordinate': names['x'], 'end': 'lower'},
                    {'name': 'right', 'coordinate': names['x'], 'end': 'upper'}],
          'reason': 'Slab 0 <= x <= 1 cm with two oriented faces'}
    op.update(changes)
    return op


def append(model, op):
    report = edit(model, {'kind': 'append', 'operation': op})
    model['motores']['equationWorkbench'] = report['definition']
    return model


class SpatialDomainTypeTests(unittest.TestCase):
    def test_independent_slab_measure_and_normals(self):
        domain = slab()
        L = sp.Rational(1, 100)
        self.assertEqual(domain.measure(), sp.integrate(1, (X, 0, L)))
        self.assertEqual(domain.measure(), L)
        normals = [domain.normal(part)['x'] for part in domain.parts]
        self.assertEqual(sum(normals), 0)
        # Gauss in 1D, independently: int_a^b f'(x) dx = sum over parts of n_x f(x_part).
        f = sp.exp(3*X) + X**4
        lhs = sp.integrate(sp.diff(f, X), (X, 0, L))
        rhs = sum(domain.normal(p)['x']*f.subs(X, domain.endpoint(p)) for p in domain.parts)
        self.assertEqual(sp.simplify(lhs-rhs), 0)

    def test_cylindrical_metric_is_retained(self):
        shell = SpatialDomain('cylindrical', (R,), (DomainPremise(R, 'interval', lower='1', upper='2'),),
                              (BoundaryPart('inner', R, 'lower'), BoundaryPart('outer', R, 'upper')))
        self.assertEqual(shell.measure(), sp.integrate(R, (R, 1, 2)))
        with self.assertRaisesRegex(MathematicsError, 'axis or centre'):
            SpatialDomain('cylindrical', (R,), (DomainPremise(R, 'interval', lower='0', upper='2'),), (BoundaryPart('axis', R, 'lower'),))

    def test_curvilinear_measure_is_per_unit_inactive_extent(self):
        # Review P2: the measure must not depend on an inactive coordinate.
        sphere = SpatialDomain('spherical', (R,), (DomainPremise(R, 'interval', lower='0', upper='2'),),
                               (BoundaryPart('surface', R, 'upper'),))
        self.assertEqual(sphere.measure(), sp.integrate(R**2, (R, 0, 2)))
        self.assertFalse(sphere.measure().free_symbols)
        Z = sp.Symbol('z', real=True)
        column = SpatialDomain('cylindrical', (Z,), (DomainPremise(Z, 'interval', lower='0', upper='3'),), ())
        self.assertEqual(column.measure(), 3)

    def test_angular_coordinates_are_rejected_with_location(self):
        for chart, name in [('cylindrical', 'phi'), ('spherical', 'theta'), ('spherical', 'phi')]:
            angle = sp.Symbol(name, real=True)
            with self.assertRaisesRegex(MathematicsError, 'Angular coordinate '+name+' cannot be active yet'):
                SpatialDomain(chart, (angle,), (DomainPremise(angle, 'interval', lower='0', upper='1'),), ())

    def test_empty_reversed_and_degenerate_intervals(self):
        with self.assertRaisesRegex(MathematicsError, 'empty or reversed'):
            slab(lower='1', upper='0')
        with self.assertRaisesRegex(MathematicsError, 'empty or reversed'):
            slab(lower='1', upper='1', lower_open=True)
        with self.assertRaisesRegex(MathematicsError, 'single point'):
            slab(lower='1', upper='1')

    def test_overlapping_and_duplicate_parts(self):
        with self.assertRaisesRegex(MathematicsError, 'overlap'):
            slab(parts=(('left', 'lower'), ('wall', 'lower')))
        with self.assertRaisesRegex(MathematicsError, 'distinct'):
            slab(parts=(('face', 'lower'), ('face', 'upper')))

    def test_chart_coordinate_mismatch(self):
        with self.assertRaisesRegex(MathematicsError, 'does not belong to the cartesian chart'):
            SpatialDomain('cartesian', (R,), (DomainPremise(R, 'interval', lower='0', upper='1'),), ())
        with self.assertRaisesRegex(MathematicsError, 'does not belong to the spherical chart'):
            SpatialDomain('spherical', (X,), (DomainPremise(X, 'interval', lower='0', upper='1'),), ())

    def test_volume_integral_binding_is_opt_in(self):
        phi, z, t = sp.symbols('phi z t', real=True)
        field = sp.Function('c')(R, phi, z, t)
        self.assertEqual(VolumeIntegral(field).free_symbols, {R, phi, t})  # historical form, unchanged
        self.assertEqual(VolumeIntegral(field, sp.Tuple(R, phi, z)).free_symbols, {t})


class WorkbenchRuleTests(unittest.TestCase):
    def setUp(self):
        self.model, self.names, _ = fick_model()

    def test_recorded_rule_with_dimensional_endpoints(self):
        model = append(self.model, operation(self.names))
        result = build(model)
        key = 'operation.1'
        domain = result.graph.spatial_domains[key]
        self.assertEqual(domain.interval(X), sp.Interval(0, sp.Rational(1, 100)))  # 1 cm in SI
        self.assertEqual(result.graph.nodes[key].rule, 'spatial_domain')
        self.assertEqual(result.graph.nodes[key+'.interval.x'].kind, 'constraint')
        self.assertIn(key+'.interval.x', result.graph.domains)
        self.assertTrue(any('outward normal -e_x' in text for text in result.graph.nodes[key].assumptions))
        signatures = model['motores']['equationWorkbench']['operations'][0]['sourceSignatures']
        self.assertEqual(set(signatures), {FIELD_ROW})

    def test_units_are_checked(self):
        with self.assertRaisesRegex(MathematicsError, 'incompatible units'):
            append(self.model, operation(self.names, intervals=[{'lower': '0', 'upper': '1', 'lowerOpen': False, 'upperOpen': False, 'endpointUnit': 's'}]))
        with self.assertRaisesRegex(MathematicsError, 'empty or reversed'):
            append(self.model, operation(self.names, intervals=[{'lower': '2', 'upper': '1', 'lowerOpen': False, 'upperOpen': False, 'endpointUnit': 'cm'}]))
        with self.assertRaisesRegex(MathematicsError, 'overlap'):
            append(self.model, operation(self.names, parts=[{'name': 'a', 'coordinate': self.names['x'], 'end': 'upper'},
                                                            {'name': 'b', 'coordinate': self.names['x'], 'end': 'upper'}]))
        with self.assertRaisesRegex(MathematicsError, 'does not belong'):
            append(self.model, operation(self.names, chart='spherical'))

    def test_undo_redo_replay_with_signatures(self):
        model = append(self.model, operation(self.names))
        recorded = copy.deepcopy(model['motores']['equationWorkbench'])
        signature = source_signature(model)
        undone = edit(model, {'kind': 'undo'})['definition']
        self.assertEqual(undone['cursor'], 0)
        model['motores']['equationWorkbench'] = undone
        self.assertNotIn('operation.1', build(model).graph.spatial_domains)
        self.assertNotEqual(source_signature(model), signature)
        redone = edit(model, {'kind': 'redo'})['definition']
        self.assertEqual(redone, recorded)
        model['motores']['equationWorkbench'] = redone
        self.assertEqual(source_signature(model), signature)
        self.assertIn('operation.1', build(model).graph.spatial_domains)

    def test_volume_integral_binds_declared_axes(self):
        model = append(self.model, operation(self.names))
        model = append(model, {'kind': 'volume_integrate', 'family': 'matter', 'sources': [FIELD_ROW]})
        equation = build(model).graph.nodes['operation.2'].equation
        integrals = [n for n in sp.preorder_traversal(equation) if isinstance(n, VolumeIntegral)]
        self.assertTrue(integrals)
        self.assertTrue(all(len(n.args) == 2 and set(n.args[1]) == set(sp.symbols('x y z', real=True)) for n in integrals))

    def test_volume_integral_without_domain_is_unchanged(self):
        model = append(self.model, {'kind': 'volume_integrate', 'family': 'matter', 'sources': [FIELD_ROW]})
        equation = build(model).graph.nodes['operation.1'].equation
        self.assertTrue(all(len(n.args) == 1 for n in sp.preorder_traversal(equation) if isinstance(n, VolumeIntegral)))

    def test_contract_is_additive(self):
        base = {'format': FORMAT, 'version': 1, 'cursor': 1}
        read_definition({**base, 'operations': [operation(self.names)]})
        with self.assertRaisesRegex(MathematicsError, 'belong only to spatial domain'):
            read_definition({**base, 'operations': [{'kind': 'expand', 'family': 'matter', 'sources': ['a'], 'chart': 'cartesian'}]})
        with self.assertRaisesRegex(MathematicsError, 'exactly one declared spatial domain'):
            read_definition({**base, 'operations': [{'kind': 'volume_integrate', 'family': 'matter', 'sources': ['a'], 'domains': ['b', 'c']}]})


if __name__ == '__main__':
    unittest.main()
