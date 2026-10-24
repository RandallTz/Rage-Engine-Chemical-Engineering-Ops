"""M1-C deduction evidence; this is not numerical U1 solver acceptance."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import sympy as sp
from m1_acceptance import author_thermal, THERMAL_REFERENCE
from core.mathematics.dimensions import dimension
from core.mathematics.errors import MathematicsError
from core.modelo import leer_modelo_comun
from core.modelo.equation_workbench import build, describe, describe_for_authoring, edit, ensure_executable, _known_unit
from core.compilador.presentation import formulation_summary


class ThermalAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model, cls.result, cls.outputs = author_thermal()
        cls.t = sp.Symbol('t', real=True)

    def test_frozen_document_replays_through_the_current_shared_author(self):
        saved = json.loads((ROOT / 'tests/reference_data/m1-c.json').read_text(encoding='utf8'))
        self.assertEqual(saved['model'], self.model)
        self.assertEqual(saved['selectedEquations'], self.outputs)
        self.assertEqual(saved['reference'], json.loads(json.dumps(THERMAL_REFERENCE)))
        persisted = json.loads(json.dumps(self.model))
        self.assertEqual(leer_modelo_comun(persisted), self.model)
        rebuilt = build(persisted)
        for key in self.outputs.values():
            self.assertEqual(rebuilt.graph.nodes[key].equation, self.result.graph.nodes[key].equation)
        self.assertTrue(all('sourceSignatures' in op for op in
            self.model['motores']['equationWorkbench']['operations'] if op.get('sources')))

    def test_actual_law_ancestry_dimensions_and_internal_heat_cancellation(self):
        graph = self.result.graph
        def ancestors(key):
            return {key} | set().union(*(ancestors(parent) for parent in graph.nodes[key].inputs))
        for owner in ('region_a', 'region_b'):
            key = self.outputs[owner + '.temperature']
            chain = ancestors(key)
            for required in ('energy.' + owner + '.local',
                             'thermodynamics.' + owner + '.caloric',
                             'thermodynamics.' + owner + '.specific-inventory',
                             'matter.' + owner + '.1.local'):
                self.assertIn(required, chain)
            eq = graph.nodes[key].equation
            self.assertEqual(dimension(eq.lhs, self.result.units, _known_unit), {'Theta': 1, 'T': -1})
            self.assertEqual(dimension(eq.lhs, self.result.units, _known_unit),
                             dimension(eq.rhs, self.result.units, _known_unit))
            self.assertTrue(graph.predicates_for(key))
        total = graph.nodes[self.outputs['totalEnergy']].equation
        self.assertEqual(total.rhs, 0)
        self.assertEqual(total.lhs, sum(sp.diff(sp.Function('U__' + o)(self.t), self.t)
                                      for o in ('region_a', 'region_b')))
        self.assertEqual(graph.nodes['operation.3'].kind, 'constitutive')
        # The cancellation is a consequence, not another ODE state.
        self.assertTrue(graph.nodes[self.outputs['totalEnergy']].dependent)

    def test_analytic_decay_and_energy_reference_with_parameter_variants(self):
        t = self.t
        for masses, capacities, conductance, initial in [
            ((2, 3), (500, 1000), 10, (360, 300)),
            ((4, 2), (800, 600), 7, (300, 340)),
            ((2, 3), (500, 1000), 10, (315, 315)),
        ]:
            C = [sp.Integer(m) * c for m, c in zip(masses, capacities)]
            equilibrium = sum(c * T for c, T in zip(C, initial)) / sum(C)
            delta = (initial[0] - initial[1]) * sp.exp(-conductance * (1/C[0] + 1/C[1]) * t)
            temperatures = [equilibrium + C[1]/sum(C)*delta, equilibrium - C[0]/sum(C)*delta]
            substitutions = {sp.Symbol('conductance', real=True): conductance}
            for index, owner in enumerate(('region_a', 'region_b')):
                substitutions.update({sp.Function('T__' + owner)(t): temperatures[index],
                    sp.Function('m__' + owner + '__1')(t): masses[index],
                    sp.Symbol('caloric_capacity__' + owner, real=True): capacities[index]})
            for index, owner in enumerate(('region_a', 'region_b')):
                eq = self.result.graph.nodes[self.outputs[owner + '.temperature']].equation
                self.assertEqual(sp.simplify(eq.rhs.subs(substitutions) - sp.diff(temperatures[index], t)), 0)
                for instant in (0, 5, 75, 600):
                    self.assertLess(abs(float((eq.rhs.subs(substitutions) -
                        sp.diff(temperatures[index], t)).subs(t, instant))), 1e-12)
            total = sum(c * (temperature - 300) for c, temperature in zip(C, temperatures))
            self.assertEqual(sp.simplify(sp.diff(total, t)), 0)
            self.assertEqual(sp.simplify(total), sum(c*(T-300) for c, T in zip(C, initial)))

    def test_exact_transform_handoff_and_no_numerical_fallback(self):
        report = describe(self.model)
        summary = formulation_summary(self.model)
        rows = [row for family in summary['families'] for volume in family['volumes'] for row in volume['steps']]
        for key in self.outputs.values():
            self.assertIn(next(row for row in report['equations'] if row['id'] == key), rows)
        self.assertFalse(report['execution']['supported'])
        with self.assertRaises(MathematicsError):
            ensure_executable(self.model)
        self.assertEqual(build(self.model).definition, self.result.definition)

    def test_display_rename_does_not_change_physics_or_operation_signatures(self):
        renamed = copy.deepcopy(self.model)
        renamed['nombre'] = 'An arbitrary thermal application'
        renamed['componentes'][0].update(nombre='Another display label', simbolo='X')
        result = build(renamed)
        self.assertEqual(result.definition, self.result.definition)
        for key in self.outputs.values():
            self.assertEqual(result.graph.nodes[key].equation, self.result.graph.nodes[key].equation)

    def test_changed_closure_is_recoverable_and_undo_redo_restores_exact_history(self):
        changed = copy.deepcopy(self.model)
        definition = changed['motores']['equationWorkbench']
        definition['operations'][2]['right'] = '-' + definition['operations'][2]['right']
        original_history = copy.deepcopy(definition)
        report = describe_for_authoring(changed)
        self.assertIn('replay', report)
        self.assertFalse(report['execution']['supported'])
        self.assertEqual(report['definition'], original_history)
        with self.assertRaises(MathematicsError):
            formulation_summary(changed)
        missing = copy.deepcopy(self.model)
        missing['motores']['equationWorkbench']['operations'][2]['left'] = 'conductance'
        with self.assertRaises(MathematicsError):
            build(missing)
        undone = edit(self.model, {'kind': 'undo'})
        restored = copy.deepcopy(self.model)
        restored['motores']['equationWorkbench'] = undone['definition']
        redone = edit(restored, {'kind': 'redo'})
        self.assertEqual(redone['definition'], self.model['motores']['equationWorkbench'])
        self.assertEqual(redone['equations'], describe(self.model)['equations'])


if __name__ == '__main__':
    unittest.main()
