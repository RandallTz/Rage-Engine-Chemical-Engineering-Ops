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

    def test_generic_energy_stream_terms_are_not_shadowed_by_component_flows(self):
        """The steady enthalpy balance of a generic volume is solved for an outlet temperature.

        Without declared species, the material balance carries the component flow (engine index None, read i)
        and the enthalpy balance carries the stream's total flow (engine stand-in index i, read sum): two
        engine identities. Before the naming rule both read as q__feed__i(t) and the first shadowed the second.
        """
        energy = ['start', 'pressure_stress', 'no_kinetic', 'no_viscous_work', 'no_body_work', 'no_volume_source',
                  'integrate', 'reynolds', 'total', 'enthalpy', 'uniform_state', 'uniform_pressure', 'prescribed_pressure']
        script = tank([
            {'id': 's1', 'family': 'energy', 'kind': 'declare_symbol', 'name': 'cp', 'unit': 'J/(kg*K)'},
            {'id': 's2', 'family': 'energy', 'kind': 'declare_symbol', 'name': 'Tref', 'unit': 'K'},
            {'id': 's3', 'family': 'energy', 'kind': 'declare_function', 'name': 'T_out', 'unit': 'K', 'dependencies': ['t']},
            {'id': 's4', 'family': 'energy', 'kind': 'declare_relation', 'relationKind': 'constitutive',
             'left': 'energy_average_0__product(t)', 'right': 'cp*(T_out - Tref)', 'reason': 'Constant heat capacity'},
            {'id': 's5', 'family': 'energy', 'kind': 'substitute', 'sources': ['balance:energy.tank:H__tank(t)'],
             'relation': 's4', 'symbol': 'energy_average_0__product(t)'}],
            [{'case': 'V1', 'equation': 's5', 'solveFor': 'T_out(t)',
              'inputs': {'Derivative(H__tank(t), t)': 0, 'Derivative(P__tank(t), t)': 0, 'V__tank(t)': 1.0,
                         'q__feed__sum(t)': 2.0, 'q__product__sum(t)': 2.0, 'energy_average_0__feed(t)': 1.0e5,
                         'energy_heat_rate__tank(t)': 5.0e4, 'cp': 4000.0, 'Tref': 298.15},
              'expected': 298.15 + (2.0 * 1.0e5 + 5.0e4) / (4000.0 * 2.0), 'tolerance': {'relative': 1e-12}}])
        script['fundamentalAssumptions'] += [{'id': 'E%d' % i, 'family': 'energy', 'volume': 'tank', 'action': a}
                                             for i, a in enumerate(energy, 1)]
        script['results'] = [{'id': 'r1', 'fromStep': 's5', 'statement': 'Steady enthalpy balance'}]
        out, session = rds.run(script)
        self.assertEqual(out['summary']['steps'], {'accepted': 5, 'rejected': 0, 'skipped': 0})
        self.assertIn('q__feed__sum(t)', out['workingEquations'][0]['equation'])
        self.assertEqual(out['validation'][0]['status'], 'passed', out['validation'])
        self.assertAlmostEqual(out['validation'][0]['computed'], 329.4, places=9)
        names = rds.Names.from_report(session.report(), session.aliases)
        self.assertEqual(names.ambiguous, {})
        self.assertNotEqual(names.quantity('q__feed__i(t)', 'test'), names.quantity('q__feed__sum(t)', 'test'))
        self.assertEqual(names.engine[names.quantity('q__feed__sum(t)', 'test')], 'q__puerto.1__i(t)')
        self.assertEqual(names.engine[names.quantity('q__feed__i(t)', 'test')], 'q__puerto.1__None(t)')

    def test_an_alias_never_shadows_another_quantity(self):
        alias = [(rds.re.compile(r'__None(?![A-Za-z0-9])'), '__k'), (rds.re.compile(r'__j(?![A-Za-z0-9])'), '__k')]
        names = rds.Names([('x0000000001', 'q__s__None(t)'), ('x0000000002', 'q__s__j(t)')], [], alias)
        self.assertEqual(names.ambiguous, {'q__s__k(t)': ['q__s__None(t)', 'q__s__j(t)']})
        self.assertEqual(names.quantity('q__s__None(t)', 'test'), 'x0000000001')   # both keep their engine spelling
        self.assertEqual(names.quantity('q__s__j(t)', 'test'), 'x0000000002')
        with self.assertRaisesRegex(rds.JournalError, 'Ambiguous'):
            names.quantity('q__s__k(t)', 'test')

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


class RecordedValidationTests(unittest.TestCase):
    """The validation cases of the Demo 0.2 scripts, evaluated on the recorded models (about a minute).

    RecordedReplayTests proves the replay rebuilds these models exactly; here step sN is operation.N.
    """

    class Recorded:
        mode = 'document'

        def __init__(self, fixture):
            from core.modelo.equation_workbench import build, describe
            self.model = rds.load_document(fixture, rds.ROOT)
            self.build = lambda: build(self.model)
            self.names = rds.Names.from_report(describe(self.model))

    def check(self, script, fixture):
        recorded = self.Recorded(fixture)
        script = json.loads((SCRIPTS / script).read_text(encoding='utf-8'))
        ids = {step['id']: 'operation.%d' % i for i, step in enumerate(script['steps'], 1)}
        results = [rds.validate(case, recorded, ids, recorded.names) for case in script['validation']]
        self.assertTrue(results and all(r['status'] == 'passed' for r in results), results)
        return {r['case']: r for r in results}

    def test_drum_cases(self):
        self.check('demo02-drum.deduction.json', 'frontend/testing/demo02/flashDrum.ts')

    def test_cstr_cases_include_the_steady_temperature(self):
        results = self.check('demo02-cstr.deduction.json', 'frontend/testing/demo02/continuousReactor.ts')
        self.assertAlmostEqual(results['V2']['computed'], 330.16702725114015, places=9)


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
