"""Independent regression controls for kernel-audit defects 5 and 6."""
import copy
from fractions import Fraction
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sympy as sp
from core.mathematics import EquationGraph, MathematicsError
from core.mathematics.contract import FORMAT
from core.mathematics.dimensions import catalog
from core.mathematics.session import edit_history, replay_operations
from core.unidades import exact_conversion, ErrorUnidad
from core.modelo import equation_workbench as workbench


class KernelAuditBacklogTests(unittest.TestCase):
    def setUp(self):
        self.a, self.y, self.b = sp.symbols('a y b', real=True)
        self.graph = EquationGraph()
        self.graph.add('root', self.a*self.y, self.a*self.b, 'Abstract law', family='matter')
        self.units = {q: '1' for q in (self.a, self.y, self.b)}
        self.empty = {'format': FORMAT, 'version': 1, 'operations': [], 'cursor': 0}
        self.operation = {'kind': 'isolate', 'family': 'matter', 'sources': ['root'],
                          'symbol': next(k for k, v in catalog(self.graph, self.units).items() if v == self.y)}

    def replay(self, definition):
        return replay_operations(self.graph, ['root'], {'root': 'region'}, self.units, definition)

    def edit(self, definition, kind, operation=None):
        return edit_history(self.graph, ['root'], {'root': 'region'}, self.units, definition,
                            {'kind': kind, **({'operation': operation} if operation else {})})

    def test_irrational_constants_aliases_and_transitive_definitions_reject(self):
        # All mathematical decimal constants in Pint 0.26.1, plus aliases,
        # prefixes, compound units and indirect dependencies on pi/Wien roots.
        for unit in ('degree', 'deg', 'turn', 'arcminute', 'millidegree', 'degree/second',
                     'pi', 'ln10', 'eulers_number', 'tansec', 'wien_x', 'wien_u',
                     'hbar', 'parsec', 'stefan_boltzmann_constant',
                     'wien_wavelength_displacement_law_constant'):
            with self.subTest(unit=unit), self.assertRaises(ErrorUnidad):
                exact_conversion(unit)

    def test_rational_controls_are_exact_and_fahrenheit_stays_affine(self):
        for unit, expected in [('km/hour', Fraction(5,18)), ('inch', Fraction(127,5000)),
                               ('percent', Fraction(1,100)), ('cal', Fraction(523,125)),
                               ('liter', Fraction(1,1000)), ('minute', Fraction(60)),
                               ('rad', Fraction(1))]:
            with self.subTest(unit=unit):
                result = exact_conversion(unit)
                self.assertIsInstance(result['factor'], Fraction)
                self.assertEqual(result['factor'], expected)
                self.assertEqual(result['desplazamiento'], 0)
                self.assertFalse(result['afin'])
        self.assertTrue(exact_conversion('degF')['afin'])

    def test_degree_interval_api_rejection_is_structured(self):
        from backend.api_modelo import equation_workbench
        from fastapi import HTTPException
        draft = {'format': 'rage.fundamental-equations', 'version': 3, 'modelId': 'angle-regression',
                 'materialJournal': {'origin': 'recorded', 'operations': []}, 'ports': [],
                 'definition': copy.deepcopy(self.empty)}
        for operation in (
            {'kind': 'declare_symbol', 'family': 'matter', 'name': 'angle', 'unit': 'rad'},
            {'kind': 'declare_relation', 'family': 'matter', 'left': 'angle', 'right': '0',
             'reason': 'Declared angle reference'},
        ):
            draft['definition'] = equation_workbench({'draft': draft, 'action': {
                'kind': 'append', 'operation': operation}})['definition']
        before = copy.deepcopy(draft)
        with self.assertRaises(HTTPException) as caught:
            equation_workbench({'draft': draft, 'action': {'kind': 'append', 'operation': {
                'kind': 'declare_domain', 'family': 'matter', 'sources': ['operation.2'],
                'symbol': 'angle', 'domain': 'interval', 'reason': 'Declared angle interval',
                'lower': '0', 'upper': '90', 'lowerOpen': False, 'upperOpen': False,
                'endpointUnit': 'degree'}}})
        self.assertEqual(caught.exception.status_code, 422)
        self.assertIn('no supported exact conversion', caught.exception.detail['message'])
        self.assertEqual(draft, before)

    def test_degree_interval_on_radians_is_rejected_atomically(self):
        self.units = {q: 'rad' for q in (self.a, self.y, self.b)}
        self.graph = EquationGraph()
        self.graph.add('root', self.y, self.b, 'Angle relation', family='matter')
        operation = {'kind': 'declare_domain', 'family': 'matter', 'sources': ['root'],
                     'symbol': self.operation['symbol'], 'domain': 'interval', 'reason': 'Angle bounds',
                     'lower': '0', 'upper': '90', 'lowerOpen': False, 'upperOpen': False,
                     'endpointUnit': 'degree'}
        stored = copy.deepcopy(self.empty)
        with self.assertRaisesRegex(MathematicsError, 'no supported exact conversion'):
            self.edit(self.empty, 'append', operation)
        self.assertEqual(self.empty, stored)
        self.assertEqual(list(self.graph.nodes), ['root'])
        # The separate affine rejection remains active, with compatible units.
        self.units = {q: 'K' for q in (self.y, self.b)}
        operation['endpointUnit'] = 'degF'
        with self.assertRaisesRegex(MathematicsError, 'Affine endpoints'):
            self.edit(self.empty, 'append', operation)

    def test_stripped_p3_is_inspection_only_and_receipts_do_not_invent_pinning(self):
        signed = self.edit(self.empty, 'append', self.operation)
        pinned = self.replay(signed).receipts[0]
        self.assertEqual(pinned.signature_status, 'pinned')
        self.assertEqual(pinned.input_signatures, signed['operations'][0]['sourceSignatures'])
        self.assertEqual(pinned.calculated_input_signatures, pinned.input_signatures)
        stripped = copy.deepcopy(signed)
        del stripped['operations'][0]['sourceSignatures']
        self.graph.nodes['root'].equation = sp.Eq(self.a*self.y, 3*self.a*self.b, evaluate=False)
        with self.assertRaisesRegex(MathematicsError, 'same ID'):
            self.replay(signed)
        result = self.replay(stripped)
        self.assertEqual(result.graph.nodes['operation.1'].equation.rhs, 3*self.b)
        self.assertTrue(result.requires_lowering)
        receipt = result.receipts[0]
        self.assertEqual(receipt.signature_status, 'legacy/unsigned')
        self.assertEqual(receipt.input_signatures, {})
        self.assertNotEqual(receipt.calculated_input_signatures, pinned.input_signatures)
        self.assertEqual(result.definition, stripped)
        for signatures in (receipt.input_signatures, receipt.calculated_input_signatures):
            with self.assertRaises(TypeError):
                signatures['root'] = 'fabricated'

    def test_direct_unsigned_save_warns_and_blocks_compilation_until_re_recorded(self):
        # An unconditional expansion used to be executable even when a client
        # saved it directly or removed its signatures. Test the public adapter.
        operation = {'kind': 'expand', 'family': 'matter', 'sources': ['root']}
        definition = {**self.empty, 'operations': [operation], 'cursor': 1}
        model = {'id': 'unsigned-regression', 'motores': {'equationWorkbench': definition}}
        source = (self.graph, ['root'], {'root': 'region'}, self.units)
        with patch.object(workbench, '_source_graph', return_value=source):
            report = workbench.describe(model)
            self.assertFalse(report['execution']['supported'])
            self.assertEqual(report['findings'][0]['ownerId'], 'operation.1')
            self.assertIn('Legacy/unsigned', report['findings'][0]['message'])
            self.assertEqual(report['definition'], definition)
            with self.assertRaisesRegex(MathematicsError, 'Legacy/unsigned'):
                workbench.ensure_executable(model)
            for action in ('undo', 'rewind'):
                recovered = workbench.edit(model, {'kind': action})
                self.assertEqual(recovered['definition']['cursor'], 0)
                self.assertEqual(recovered['definition']['operations'], [operation])
                self.assertTrue(recovered['execution']['supported'])
            model['motores']['equationWorkbench'] = recovered['definition']
            reviewed = workbench.edit(model, {'kind': 'append', 'operation': operation})
            self.assertIn('sourceSignatures', reviewed['definition']['operations'][0])
            model['motores']['equationWorkbench'] = reviewed['definition']
            workbench.ensure_executable(model)
            self.assertFalse(reviewed['findings'])

    def test_unsigned_evidence_cannot_be_laundered_by_a_signed_descendant_or_redo(self):
        operation = {'kind': 'expand', 'family': 'matter', 'sources': ['root']}
        legacy = {**self.empty, 'operations': [operation], 'cursor': 1}
        descendant = self.edit(legacy, 'append', {**operation, 'sources': ['operation.1']})
        result = self.replay(descendant)
        self.assertEqual([r.signature_status for r in result.receipts], ['legacy/unsigned', 'pinned'])
        self.assertTrue(result.requires_lowering)
        self.assertTrue(self.replay(self.edit(self.edit(legacy, 'undo'), 'redo')).requires_lowering)
        self.assertNotIn('sourceSignatures', descendant['operations'][0])

    def test_source_free_declarations_are_not_mislabeled_as_unsigned_inputs(self):
        definition = self.edit(self.empty, 'append', {'kind': 'declare_symbol', 'family': 'matter',
                                                      'name': 'newQuantity', 'unit': 'm'})
        result = self.replay(definition)
        self.assertEqual(result.receipts[0].signature_status, 'not_applicable')
        self.assertFalse(result.requires_lowering)


if __name__ == '__main__':
    unittest.main()
