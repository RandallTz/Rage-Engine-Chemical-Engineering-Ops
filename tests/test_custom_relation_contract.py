"""Sourced constitutive relation and typed-domain replay regressions."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sympy as sp
from core.agua_iapws95 import saturacion
from core.mathematics import EquationGraph, MathematicsError
from core.mathematics.contract import FORMAT, read_definition
from core.mathematics.dimensions import catalog
from core.mathematics.session import edit_history, replay_operations


class CustomRelationContractTests(unittest.TestCase):
    def setUp(self):
        self.p, self.pref, self.t, self.a, self.b, self.c = sp.symbols('p pref T A B C', real=True)
        self.graph = EquationGraph()
        self.graph.add('temperature', self.t, self.t, 'Temperature identity', family='thermodynamics', kind='definition')
        self.units = {self.p: 'Pa', self.pref: 'Pa', self.t: 'K', self.a: '1', self.b: 'K', self.c: 'K'}
        self.definition = {'format': FORMAT, 'version': 1, 'operations': [], 'cursor': 0}
        self.source = {'kind': 'literature', 'citation': 'Bridgeman and Aldrich (1964), NIST Chemistry WebBook',
                       'url': 'https://webbook.nist.gov/cgi/cbook.cgi?ID=C7732185&Type=ANTOINE',
                       'table': 'Antoine Equation Parameters', 'validRange': '273 to 303 K'}

    def action(self, kind, operation=None):
        self.definition = edit_history(self.graph, ['temperature'], {'temperature': 'water'}, self.units,
                                       self.definition, {'kind': kind, **({'operation': operation} if operation else {})})
        return self.replay()

    def replay(self, definition=None):
        return replay_operations(self.graph, ['temperature'], {'temperature': 'water'}, self.units,
                                 definition if definition is not None else self.definition)

    def author(self):
        names = {v: k for k, v in catalog(self.graph, self.units).items()}
        identity = names[self.t]
        self.names = names
        self.action('append', {'kind': 'declare_domain', 'family': 'thermodynamics', 'sources': ['temperature'],
                               'symbol': identity, 'domain': 'interval', 'lower': '273', 'upper': '303',
                               'lowerOpen': False, 'upperOpen': False, 'endpointUnit': 'K', 'reason': 'NIST range'})
        return self.action('append', {'kind': 'declare_relation', 'family': 'thermodynamics', 'left': names[self.p],
                                     'right': f'{names[self.pref]}*exp(log(10)*({names[self.a]}-{names[self.b]}/({names[self.t]}+{names[self.c]})))', 'reason': 'Empirical vapour pressure',
                                     'relationKind': 'constitutive', 'source': self.source, 'domains': ['operation.1']})

    def test_water_antoine_against_iapws95(self):
        result = self.author()
        node = result.graph.nodes['operation.2']
        self.assertEqual(node.source, self.source)
        self.assertEqual(node.inputs, ('operation.1',))
        self.assertTrue(result.requires_lowering)
        self.assertTrue(any(isinstance(p, sp.Contains) for p in node.predicates))
        expression = node.equation.rhs.subs({self.pref: 100000, self.a: sp.Rational('5.40221'),
                                             self.b: sp.Rational('1838.675'), self.c: sp.Rational('-31.737')})
        errors = [abs(float(expression.subs(self.t, sp.Rational(i, 10))) / saturacion(i/10).Psat - 1)
                  for i in range(2730, 3031)]
        # A fitted Antoine curve is not IAPWS-95: 0.15% bounds the observed
        # independent 0.1 K grid discrepancy, including both stated endpoints.
        self.assertLess(max(errors), 0.0015)

    def test_rejects_invalid_domain_and_units(self):
        self.author()
        bad = copy.deepcopy(self.definition)
        bad['operations'][0]['endpointUnit'] = 'Pa'
        with self.assertRaisesRegex(MathematicsError, 'incompatible dimensions'):
            self.replay(bad)
        bad = copy.deepcopy(self.definition)
        bad['operations'][1]['right'] += '+'+self.names[self.t]
        with self.assertRaisesRegex(MathematicsError, 'incompatible dimensions'):
            self.replay(bad)
        bad = copy.deepcopy(self.definition)
        bad['operations'][1]['left'] = self.names[self.pref]
        bad['operations'][1]['right'] = self.names[self.p]
        with self.assertRaisesRegex(MathematicsError, 'quantity must occur'):
            self.replay(bad)
        bad = copy.deepcopy(self.definition)
        del bad['operations'][1]['source']['citation']
        with self.assertRaisesRegex(MathematicsError, 'Relation source'):
            read_definition(bad)
        bad = copy.deepcopy(self.definition)
        bad['operations'][1]['domains'] = ['temperature']
        bad['operations'][1].pop('sourceSignatures')
        with self.assertRaisesRegex(MathematicsError, 'recorded typed domain'):
            self.replay(bad)
        bad = copy.deepcopy(self.definition)
        bad['operations'][0]['lowerOpen'] = 'false'
        with self.assertRaises(MathematicsError):
            read_definition(bad)

    def test_source_and_domain_invalidate_consumers_and_undo_redo(self):
        self.author()
        self.action('append', {'kind': 'expand', 'family': 'thermodynamics', 'sources': ['operation.2']})
        before = copy.deepcopy(self.definition)
        for changed in ('source', 'domain'):
            stale = copy.deepcopy(before)
            if changed == 'source': stale['operations'][1]['source']['citation'] = 'Changed source'
            else: stale['operations'][0]['upper'] = '302'
            with self.subTest(changed=changed), self.assertRaisesRegex(MathematicsError, 'changed behind the same ID'):
                self.replay(stale)
        self.action('undo')
        self.action('undo')
        self.assertNotIn('operation.2', self.replay().graph.nodes)
        restored = self.action('redo')
        self.assertEqual(restored.graph.nodes['operation.2'].source, self.source)
        self.action('redo')
        self.assertEqual(self.definition, before)

    def test_legacy_relation_stays_valid(self):
        read_definition({'format': FORMAT, 'version': 1, 'cursor': 1, 'operations': [
            {'kind': 'declare_relation', 'family': 'thermodynamics', 'left': 'p', 'right': 'pref', 'reason': 'Legacy'}]})


if __name__ == '__main__':
    unittest.main()
