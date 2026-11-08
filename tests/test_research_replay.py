"""Replay of research deduction scripts (tools/research/replay_deduction_script.py).

Generic tests (seconds): a single-volume script with a generic component index replays through the blank-Model
authoring path; a refused step is reported with the engine's message and its dependants are skipped; readable
names round-trip; a validation case is evaluated on the deduced equation.

Recorded tests (about 10-15 minutes each): the Demo 0.2 drum and continuous reactor scripts, converted from
tests/demo02_drum.py and tests/demo02_cstr.py, replay to the recorded models: identical journals, assumption
states, workbench operations with input signatures, equation signatures and the source signature pinned by Solve.
"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools' / 'research'))

import replay_deduction_script as rds  # noqa: E402

SCRIPTS = ROOT / 'tools' / 'research' / 'scripts'
MATTER = ['start', 'no_reaction', 'integrate', 'total', 'impermeable_remainder']


def tank(steps, validation=()):
    return {'format': rds.FORMAT, 'version': 1, 'operation': 'test-tank', 'system': {'generic': True},
            'volumes': [{'id': 'tank', 'components': 'generic, i = 1..N'}],
            'streams': [{'id': 'feed', 'volume': 'tank', 'direction': 'inlet'},
                        {'id': 'product', 'volume': 'tank', 'direction': 'outlet'}],
            'fundamentalAssumptions': [{'id': 'A%d' % i, 'family': 'matter', 'volume': 'tank', 'action': a, 'reason': a}
                                       for i, a in enumerate(MATTER, 1)],
            'steps': steps, 'results': [{'id': 'r1', 'fromStep': 's3', 'statement': 'Withdrawn tank balance'}],
            'validation': list(validation)}


WITHDRAWAL = [
    {'id': 's1', 'kind': 'declare_symbol', 'name': 'k', 'unit': '1/s', 'cite': '[R1]'},
    {'id': 's2', 'kind': 'declare_relation', 'relationKind': 'constitutive', 'left': 'q__product__i(t)',
     'right': 'k*m__tank__i(t)', 'reason': 'First-order withdrawal'},
    {'id': 's3', 'kind': 'substitute', 'sources': ['balance:matter.tank:m__tank__i(t)'], 'relation': 's2',
     'symbol': 'q__product__i(t)'},
]


class GenericReplayTests(unittest.TestCase):
    def test_generic_script_replays_through_the_blank_model_path(self):
        case = {'case': 'V1', 'equation': 's3', 'solveFor': 'Derivative(m__tank__i(t), t)',
                'inputs': {'k': 0.5, 'm__tank__i(t)': 2.0, 'q__feed__i(t)': 3.0}, 'expected': 2.0,
                'tolerance': {'relative': 1e-12}}
        out, session = rds.run(tank(WITHDRAWAL, [case]))
        self.assertEqual(session.mode, 'generic')
        self.assertEqual(out['summary']['assumptions'], {'accepted': 5, 'rejected': 0, 'skipped': 0})
        self.assertEqual(out['summary']['steps'], {'accepted': 3, 'rejected': 0, 'skipped': 0})
        self.assertEqual(out['ids'], {'s1': 'operation.1', 's2': 'operation.2', 's3': 'operation.3'})
        # Hashed ids and input signatures come from the engine, never from the script.
        self.assertTrue(rds.HASHED.fullmatch(out['steps'][2]['operation']['symbol']))
        self.assertEqual(len(out['steps'][2]['signatures']), 2)
        self.assertEqual(out['workingEquations'][0]['equation'],
                         'Derivative(m__tank__i(t), t) = -k*m__tank__i(t) + q__feed__i(t)')
        self.assertEqual(out['validation'][0]['status'], 'passed')
        self.assertEqual(out['validation'][0]['computed'], 2.0)

    def test_refused_step_is_located_and_dependants_are_skipped(self):
        steps = WITHDRAWAL + [
            {'id': 's4', 'kind': 'substitute', 'sources': ['s3'], 'relation': 's2', 'symbol': 'q__vent__i(t)'},
            {'id': 's5', 'kind': 'isolate', 'sources': ['s4'], 'symbol': 'k'},
            {'id': 's6', 'kind': 'isolate', 'sources': ['s3'], 'symbol': 'k'},
            {'id': 's7', 'kind': 'zero', 'sources': ['s3'], 'symbol': 'k'}]
        out, _ = rds.run(tank(steps))
        status = {row['id']: row['status'] for row in out['steps']}
        self.assertEqual(status, {'s1': 'accepted', 's2': 'accepted', 's3': 'accepted', 's4': 'rejected',
                                  's5': 'skipped', 's6': 'accepted', 's7': 'rejected'})
        rejected = {f['step']: f['error'] for f in out['findings']}
        self.assertIn("Unknown quantity 'q__vent__i(t)'", rejected['s4'])
        self.assertIn('Close engine names: q__feed__i(t)', rejected['s4'])   # readable suggestions
        self.assertNotRegex(rejected['s7'], rds.HASHED.pattern)       # engine messages are translated to names
        self.assertEqual(out['ids']['s6'], 'operation.4')

    def test_rejected_assumption_is_reported_without_running_the_steps(self):
        script = tank(WITHDRAWAL)
        script['fundamentalAssumptions'].insert(1, {'id': 'A0', 'family': 'matter', 'volume': 'tank', 'action': 'no_such_assumption'})
        out, _ = rds.run(script)
        self.assertEqual(out['assumptions'][1]['status'], 'rejected')
        self.assertTrue(all(row['status'] == 'skipped' for row in out['assumptions'][2:]))
        self.assertTrue(all(row['status'] == 'skipped' for row in out['steps']))
        self.assertEqual(out['findings'][0]['assumption'], 'A0')

    def test_version_zero_spellings_are_read(self):
        script = tank([dict(WITHDRAWAL[0], source='[R1]'), *WITHDRAWAL[1:]])
        script['version'] = 0
        out, _ = rds.run(script)
        self.assertEqual(out['summary']['steps']['accepted'], 3)
        self.assertNotIn('source', out['steps'][0]['operation'])
        self.assertEqual(rds.assumption_action({'id': 'A', 'family': 'momentum', 'flag': 'pressureStress', 'value': True}),
                         {'kind': 'set_assumption', 'name': 'pressureStress', 'value': True})
        self.assertEqual(rds.v0_flag_action('matter', 'sinReaccion', True), {'kind': 'no_reaction'})
        self.assertEqual(rds.v0_flag_action('energy', 'presion_prescrita', True), {'kind': 'prescribed_pressure'})
        self.assertEqual(rds.v0_flag_action('energy', 'no_kinetic', True), {'kind': 'no_kinetic'})
        with self.assertRaises(rds.ScriptError):
            rds.v0_flag_action('energy', 'sinTrabajoEje', True)
        # Version 0 omits the fundamental law; the replay starts it and says so.
        v0 = tank(WITHDRAWAL)
        v0['version'] = 0
        v0['fundamentalAssumptions'] = [{'id': 'A%d' % i, 'family': 'matter', 'volume': 'tank', 'flag': flag, 'value': True}
                                        for i, flag in enumerate(['sinReaccion', 'integrate', 'total', 'restoImpermeable'], 1)]
        out, _ = rds.run(v0)
        self.assertEqual(out['assumptions'][0]['id'], 'A1.start')
        self.assertIn('implied', out['assumptions'][0])
        self.assertEqual(out['summary']['steps']['accepted'], 3)

    def test_names_round_trip_and_ambiguity(self):
        names = rds.Names([('x0123456789', 'T__drum(t)'), ('xabcdefabcd', 'z__drum'), ('xaaaaaaaaaa', 't')], ['UA'])
        text = 'UA*(x0123456789 - xabcdefabcd) + xabcdefabcd*xaaaaaaaaaa'
        readable = names.to_readable_expression(text)
        self.assertEqual(readable, 'UA*(T__drum(t) - z__drum) + z__drum*t')
        self.assertEqual(names.expression(readable), text)
        self.assertEqual(names.quantity('{T__drum(t)}', 'test'), 'x0123456789')
        with self.assertRaises(rds.JournalError):
            names.quantity('T__drm(t)', 'test')

    def test_template_is_a_valid_version_one_script(self):
        template = json.loads((SCRIPTS / '_TEMPLATE.deduction.json').read_text(encoding='utf-8'))
        rds.read_script(template)
        self.assertEqual(template['version'], rds.VERSION)


class RecordedReplayTests(unittest.TestCase):
    """The Demo 0.2 equipment scripts reproduce the recorded models exactly."""

    def check(self, script, fixture):
        path = SCRIPTS / script
        out, session = rds.run(json.loads(path.read_text(encoding='utf-8')), base=path.parent)
        self.assertEqual(out['findings'], [])
        self.assertEqual(out['summary']['steps']['rejected'], 0)
        comparison = rds.compare(session, rds.load_document(fixture, rds.ROOT))
        self.assertTrue(comparison['equal'], comparison)
        self.assertTrue(all(case['status'] == 'passed' for case in out['validation']), out['validation'])
        return out

    def test_drum_script_reproduces_the_recorded_drum(self):
        out = self.check('demo02-drum.deduction.json', 'frontend/testing/demo02/flashDrum.ts')
        self.assertEqual(out['summary']['steps']['accepted'], 116)

    def test_cstr_script_reproduces_the_recorded_reactor(self):
        out = self.check('demo02-cstr.deduction.json', 'frontend/testing/demo02/continuousReactor.ts')
        self.assertEqual(out['summary']['steps']['accepted'], 149)


if __name__ == '__main__':
    unittest.main()
