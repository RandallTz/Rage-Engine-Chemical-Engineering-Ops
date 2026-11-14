"""C4: step generator, timeline driver and the step-budget stop (kernel-audit finding A-1).

References are analytic: a first-order plant x' = -x + u with u a zero-rate pseudo-state (a held time input) has
x(t) = u + (x0 - u) exp(-(t - t0)) between actions; the budget case is y' = -a (y - 1).
"""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import core.solvers.integrador as integrator
from core.solvers.integrador import DomainViolation, _dense, integrar, pasos
from core.solvers.timeline import TimelineError, TimelineRun, replay


class Plant:
    """x' = -x + u, u' = 0; state [x, u]. Counts every call so a preview can be shown to make none."""
    def __init__(self):
        self.calls = 0

    def rhs(self, t, y):
        self.calls += 1
        return np.array([-y[0] + y[1], 0.])

    def firma(self, t, y):
        self.calls += 1
        return None

    def dominio(self, t, y):
        self.calls += 1
        return [y[0]]

    def describir_dominio(self, k):
        return 'x'


def exact(x0, u, dt):
    return u + (x0 - u) * np.exp(-dt)


def digest(run, count=101):
    trajectory = run.trajectory()
    times = np.linspace(0., run.termination['tEnd'], count)
    return hashlib.sha256(b''.join(trajectory.y(t).tobytes() for t in times)).hexdigest(), trajectory.pasos


OPTIONS = dict(rtol=1e-9, atol=1e-12)


class ExistingTrajectoriesAreUnchanged(unittest.TestCase):
    """Signatures recorded from the integrator before the generator change (git 52e3bda, same machine class)."""
    class Switch:
        def rhs(self, t, y): return np.array([-y[0] + 1., .5 * y[1]])
        def firma(self, t, y): return y[0] > .6
        def dominio(self, t, y): return [y[0], y[1]]
        def describir_dominio(self, k): return 'AB'[k]

    class Linear:
        def rhs(self, t, y): return np.array([-y[0] + y[1], 0.])
        def firma(self, t, y): return None

    @staticmethod
    def signature(tray):
        times = np.linspace(0, tray.t_fin, 57)
        digest = hashlib.sha256(b''.join(tray.y(t).tobytes() for t in times)).hexdigest()[:16]
        return (tray.pasos, tray.rechazos, tray.t_fin.hex(), [float(v).hex() for v in tray.y_fin],
                [(e[0], float(e[1]).hex()) for e in tray.eventos], digest)

    def test_byte_identical_to_the_previous_integrator(self):
        cases = [
            (self.Linear, [1., .5], 6., {}, (37, 0, '0x1.8000000000000p+2', ['0x1.00a2729b33b97p-1', '0x1.0000000000000p-1'], [], 'cc833f7ac02fe592')),
            (self.Linear, [1., .5], 6., {'metodo': 'BDF'}, (97, 0, '0x1.8000000000000p+2', ['0x1.00a272f9818f7p-1', '0x1.0000000000000p-1'], [], '5e0c3996e2ba44d7')),
            (self.Switch, [0., 1.], 3., {'max_step': .3}, (48, 9, '0x1.8000000000000p+1', ['0x1.e6824f21dc406p-1', '0x1.1ed3fe6718f87p+2'], [('cambio_firma', '0x1.d5240f19e6adap-1')], '5545b7c78dc755cc')),
            (self.Switch, [0., 1.], 3., {'metodo': 'BDF', 'rtol': 1e-9}, (127, 0, '0x1.8000000000000p+1', ['0x1.e6824f07346c3p-1', '0x1.1ed3fe7775440p+2'], [('cambio_firma', '0x1.d5240f3b03c39p-1')], '07ddf1f2ca2b9453')),
        ]
        for factory, y0, final, options, expected in cases:
            with self.subTest(system=factory.__name__, options=options):
                self.assertEqual(self.signature(integrar(factory(), y0, final, **options)), expected)

    def test_draining_the_generator_is_integrar(self):
        a = integrar(self.Switch(), [0., 1.], 3., max_step=.3)
        generator = pasos(self.Switch(), [0., 1.], 3., max_step=.3)
        try:
            while True:
                next(generator)
        except StopIteration as stop:
            b = stop.value
        self.assertEqual(self.signature(a), self.signature(b))

    def test_a_longer_horizon_changes_only_the_scales_not_the_domain_of_the_run(self):
        short = integrar(Plant(), [1., .5], 2.)
        stretch = integrar(Plant(), [1., .5], 2., start_time=0., horizon=2.)
        self.assertEqual(self.signature(short), self.signature(stretch))


class Actions(unittest.TestCase):
    def run_case(self, method, edges, **extra):
        run = TimelineRun(Plant(), [1., .5], 12., metodo=method, **OPTIONS, **extra)
        return run

    def test_an_action_lands_exactly_at_t_star_by_truncation(self):
        for method in ('RK45', 'BDF'):
            with self.subTest(method=method):
                run = self.run_case(method, None, max_step=.5)
                run.advance(3.37)
                action = run.apply({1: 2.})
                self.assertEqual(action.t, 3.37)
                run.advance(8.123)
                run.apply({1: -0.0 + 1.})
                run.advance(12.)
                self.assertEqual(run.termination, {'reason': 'completed', 'tEnd': 12.})
                trajectory = run.trajectory()
                # The tramo that holds an action ends exactly at the recorded float, and the next one starts there.
                ends = [t1 for _, t1, _ in trajectory.tramos]
                starts = [t0 for t0, _, _ in trajectory.tramos]
                for t in (3.37, 8.123):
                    self.assertIn(t, ends)
                    self.assertIn(t, starts)
                left = exact(1., .5, 3.37)
                self.assertAlmostEqual(run.jumps[0][1][0], left, delta=1e-7)
                self.assertEqual(run.jumps[0][2][1], 2.)
                mid = exact(left, 2., 8.123 - 3.37)
                end = exact(mid, 1., 12. - 8.123)
                self.assertAlmostEqual(trajectory.y(12.)[0], end, delta=2e-7)
                self.assertAlmostEqual(trajectory.y(8.123)[0], mid, delta=2e-7)
                # Jump sampled on both sides of the same instant.
                before, after = run.preview([3.37], 'left')[0], run.preview([3.37], 'right')[0]
                self.assertEqual((before[1], after[1]), (.5, 2.))
                self.assertEqual(before[0], after[0])

    def test_two_actions_at_the_same_instant_share_one_truncation(self):
        run = TimelineRun(Plant(), [1., .5], 4., **OPTIONS)
        run.advance(1.5)
        run.apply({1: 2.})
        run.apply({0: 3.})
        run.advance(4.)
        self.assertEqual([a.seq for a in run.actions], [1, 2])
        right = run.preview([1.5], 'right')[0]
        self.assertEqual((right[0], right[1]), (3., 2.))
        self.assertAlmostEqual(run.trajectory().y(4.)[0], exact(3., 2., 2.5), delta=2e-7)

    def test_scheduled_actions_use_the_same_rule(self):
        from core.solvers.timeline import make_action
        scheduled = [make_action(2.5, {1: 2.}, 'scheduled'), make_action(7.25, {1: 1.}, 'scheduled')]
        run = TimelineRun(Plant(), [1., .5], 10., scheduled=scheduled, **OPTIONS)
        run.advance(10.)
        self.assertEqual([(a.t, a.origin) for a in run.actions], [(2.5, 'scheduled'), (7.25, 'scheduled')])
        x1 = exact(1., .5, 2.5)
        x2 = exact(x1, 2., 4.75)
        self.assertAlmostEqual(run.trajectory().y(10.)[0], exact(x2, 1., 2.75), delta=2e-7)

    def test_rejected_actions_change_nothing(self):
        run = TimelineRun(Plant(), [1., .5], 4., **OPTIONS)
        run.advance(1.)
        for bad in ({7: 1.}, {}):
            with self.assertRaises(TimelineError):
                run.apply(bad)
        # x < 0 leaves the declared domain: the restart is refused and the run continues unchanged.
        with self.assertRaises(TimelineError) as caught:
            run.apply({0: -1.})
        self.assertEqual(caught.exception.code, 'state_outside_domain')
        self.assertEqual(run.actions, [])
        run.advance(4.)
        self.assertAlmostEqual(run.trajectory().y(4.)[0], exact(1., .5, 4.), delta=2e-7)
        with self.assertRaises(TimelineError) as caught:
            run.apply({1: 1.})
        self.assertEqual(caught.exception.code, 'run_finished')

    def test_operator_stop_publishes_a_partial_timeline(self):
        run = TimelineRun(Plant(), [1., .5], 10., **OPTIONS)
        run.advance(2.2)
        run.apply({1: 2.})
        run.advance(5.5)
        run.stop()
        self.assertEqual(run.termination, {'reason': 'operator_stop', 'tEnd': 5.5})
        trajectory = run.trajectory()
        self.assertEqual(trajectory.t_fin, 5.5)
        self.assertAlmostEqual(trajectory.y(5.5)[0], exact(exact(1., .5, 2.2), 2., 3.3), delta=2e-7)
        self.assertIsNone(trajectory.detenida)


class Replay(unittest.TestCase):
    def live(self, method, edges_a, edges_b):
        """The same timeline reached with different client edges (pace) must give the same numbers."""
        run = TimelineRun(Plant(), [1., .5], 12., metodo=method, max_step=.6, **OPTIONS)
        for t in edges_a:
            run.advance(t)
        run.apply({1: 2.})
        for t in edges_b[:-1]:
            run.advance(t)
        run.apply({1: .75})
        run.advance(edges_b[-1])
        return run

    def test_live_run_and_replay_are_bit_identical_and_independent_of_pace(self):
        for method in ('RK45', 'BDF'):
            with self.subTest(method=method):
                fine = self.live(method, [.1 * k for k in range(1, 34)] + [3.37], [3.4 + .25 * k for k in range(1, 32)] + [12.])
                self.assertEqual(fine.termination['reason'], 'completed')
                coarse = self.live(method, [3.37], [8.123, 12.])
                self.assertEqual(fine.record()['actions'][0]['t'], 3.37)
                # Different second action instants: compare the shared first part through the record, then replay each.
                for run in (fine, coarse):
                    record = json.loads(json.dumps(run.record()))
                    again = replay(Plant(), [1., .5], 12., record, metodo=method, max_step=.6, **OPTIONS)
                    self.assertEqual(digest(run), digest(again))
                    self.assertEqual(run.record(), again.record())
                    self.assertEqual(run.termination, again.termination)

    def test_pace_only_changes_where_the_client_looks(self):
        a = self.live('BDF', [3.37], [8.123, 12.])
        b = self.live('BDF', [3.37], [4., 5., 6., 7., 8.123, 12.])
        self.assertEqual(digest(a), digest(b))

    def test_replay_of_an_operator_stop(self):
        run = TimelineRun(Plant(), [1., .5], 10., **OPTIONS)
        run.advance(2.2)
        run.apply({1: 2.})
        run.advance(5.5)
        run.stop()
        again = replay(Plant(), [1., .5], 10., run.record(), **OPTIONS)
        self.assertEqual(digest(run), digest(again))
        self.assertEqual(again.termination, run.termination)


class PreviewAndAdmission(unittest.TestCase):
    def test_preview_never_calls_the_system(self):
        system = Plant()
        run = TimelineRun(system, [1., .5], 8., **OPTIONS)
        run.advance(3.)
        run.apply({1: 2.})
        run.advance(5.)
        calls = system.calls
        rows = run.preview([0., 1., 3., 4.2, 5.])
        self.assertEqual(system.calls, calls)
        self.assertAlmostEqual(rows[1][0], exact(1., .5, 1.), delta=2e-7)
        with self.assertRaises(TimelineError):
            run.preview([7.])
        # The preview did not change what the run goes on to compute.
        reference = TimelineRun(Plant(), [1., .5], 8., **OPTIONS)
        reference.advance(3.)
        reference.apply({1: 2.})
        reference.advance(8.)
        run.advance(8.)
        self.assertEqual(digest(run), digest(reference))

    class Chain:
        """Margins that start on their bound and do not leave it: the case the admission state exists for."""
        def __init__(self, n): self.n = n
        def dominio(self, t, y): return list(y)
        def describir_dominio(self, k): return f'c{k}'
        def firma(self, t, y): return None
        def rhs(self, t, y):
            rate = np.empty(self.n)
            rate[0], rate[1:] = 1., y[:-1]
            return rate

    def test_admission_state_is_scoped_to_its_generator(self):
        system = self.Chain(5)
        starts = ([0.] * 5, [.5, 0., 0., 0., 0.])
        sequential = [integrar(system, y0, 2., rtol=1e-9, atol=1e-12) for y0 in starts]
        generators = [pasos(system, y0, 2., 1e-9, 1e-12) for y0 in starts]
        finals = [None, None]
        active = [True, True]
        while any(active):
            for k, generator in enumerate(generators):
                if not active[k]:
                    continue
                try:
                    next(generator)
                except StopIteration as stop:
                    finals[k], active[k] = stop.value, False
                # Between resumptions nothing is admitted: the scope is the generator's, not the module's.
                self.assertIsNone(integrator._ACTIVE.get())
        for a, b in zip(sequential, finals):
            self.assertIsNone(b.detenida)
            self.assertEqual(a.pasos, b.pasos)
            np.testing.assert_array_equal(a.y_fin, b.y_fin)

    def test_a_discarded_generator_leaves_no_admission_behind(self):
        generator = pasos(self.Chain(3), [0.] * 3, 2.)
        next(generator), next(generator)
        generator.close()
        self.assertIsNone(integrator._ACTIVE.get())


class StepBudget(unittest.TestCase):
    """A-1: a run that exhausts max_pasos is a stop, never a completed run."""
    class Relax:
        a = 1e4
        def rhs(self, t, y): return np.array([-self.a * (y[0] - 1.)])
        def firma(self, t, y): return None

    def test_exhausted_budget_is_a_reported_stop(self):
        result = integrar(self.Relax(), [0.], 10., rtol=1e-6, atol=1e-9, max_pasos=500)
        self.assertEqual(result.pasos, 500)
        self.assertIsNotNone(result.detenida)
        self.assertEqual(result.detenida.codigo, 'max_pasos')
        self.assertLess(result.t_fin, 10.)
        # explicit RK45 stability limit: h <= ~3.3/a, so 500 steps cover about 0.165 s
        self.assertAlmostEqual(result.t_fin, 500 * 3.3 / self.Relax.a, delta=.02)
        self.assertEqual(result.eventos[-1][0], 'max_pasos')
        self.assertEqual(result.eventos[-1][1], result.t_fin)
        self.assertAlmostEqual(result.y_fin[0], 1 - np.exp(-self.Relax.a * result.t_fin), delta=1e-5)
        self.assertEqual(result.tramos[-1][1], result.t_fin)

    def test_a_run_that_finishes_inside_the_budget_is_unchanged(self):
        done = integrar(self.Relax(), [0.], .05, rtol=1e-6, atol=1e-9, max_pasos=500)
        self.assertIsNone(done.detenida)
        self.assertEqual(done.t_fin, .05)
        exact_budget = integrar(self.Relax(), [0.], .05, rtol=1e-6, atol=1e-9, max_pasos=done.pasos)
        self.assertIsNone(exact_budget.detenida)
        self.assertEqual(exact_budget.t_fin, .05)
        short = integrar(self.Relax(), [0.], .05, rtol=1e-6, atol=1e-9, max_pasos=done.pasos - 1)
        self.assertEqual(short.detenida.codigo, 'max_pasos')

    def test_the_stiff_method_completes_the_same_problem(self):
        result = integrar(self.Relax(), [0.], 10., rtol=1e-6, atol=1e-9, max_pasos=500, metodo='BDF')
        self.assertIsNone(result.detenida)
        self.assertEqual(result.t_fin, 10.)

    def test_the_timeline_budget_is_cumulative_and_reports_solver_stop(self):
        run = TimelineRun(self.Relax(), [0.], 10., rtol=1e-6, atol=1e-9, max_pasos=500)
        self.assertFalse(run.advance(10.))
        self.assertEqual(run.termination['reason'], 'solver_stop')
        trajectory = run.trajectory()
        self.assertEqual(trajectory.detenida.codigo, 'max_pasos')
        self.assertEqual(run.termination['tEnd'], trajectory.t_fin)
        # An action cannot be applied once the budget has ended the run.
        with self.assertRaises(TimelineError):
            run.apply({0: 0.})

    def test_publishers_report_a_truncated_run_as_partial(self):
        from core.compilador import explicito
        path = ROOT / 'docs/ejemplos/modelo-comun/explicito-agotamiento.json'
        model = json.loads(path.read_text(encoding='utf-8'))['modelo']
        model['datos']['estudio.tf']['declaracion'].update(texto='1', unidad='s')
        model['estudio']['muestras'] = 21
        full = explicito.resolver_explicito(copy.deepcopy(model))
        self.assertEqual(full['estado'], 'resuelto')
        with patch.object(explicito, 'integrar', lambda *a, **k: integrar(*a, **{**k, 'max_pasos': 3})):
            truncated = explicito.resolver_explicito(copy.deepcopy(model))
        self.assertEqual(truncated['estado'], 'parcial')
        self.assertIn('max_pasos', truncated['procedencia']['mensaje'])
        self.assertTrue(any(event['codigo'] == 'max_pasos' for event in truncated['eventos']))
        times = next(axis['valores'] for axis in truncated['ejes'] if axis['rol'] == 'tiempo')
        self.assertLess(times[-1], 1.)


class RefineReplaysTheTimeline(unittest.TestCase):
    def test_a_bad_interpolant_after_an_action_is_rebuilt_with_the_action(self):
        system = Plant()
        run = TimelineRun(system, [1., .5], 8., max_step=.4, **OPTIONS)
        run.advance(2.5)
        run.apply({1: 2.})
        run.advance(8.)
        trajectory = run.trajectory()
        index = next(i for i, (t0, t1, _) in enumerate(trajectory.tramos) if t0 >= 5.)
        start, end, original = trajectory.tramos[index]

        def defective(t):
            return np.array([-1., 2.]) if start < t < end else original(t)
        trajectory.tramos[index] = (start, end, _dense(system, defective))
        sample = trajectory.y((start + end) / 2)
        self.assertGreaterEqual(sample[0], 0.)
        self.assertGreater(trajectory.rechazos, 0)
        # The suffix kept the held input of the action (u = 2): a rebuild without it would drift towards u = .5.
        x_half = exact(exact(1., .5, 2.5), 2., 5.5)
        self.assertAlmostEqual(trajectory.y(8.)[0], x_half, delta=2e-6)
        self.assertEqual(trajectory.y(8.)[1], 2.)
        self.assertEqual(trajectory.y(7.9)[1], 2.)

    def test_a_refinement_that_cannot_be_replayed_stops(self):
        system = Plant()
        run = TimelineRun(system, [1., .5], 4., max_step=.4, h_min=.5, **OPTIONS)
        run.advance(1.)
        run.apply({1: 2.})
        run.advance(4.)
        trajectory = run.trajectory()
        index = len(trajectory.tramos) - 1
        start, end, original = trajectory.tramos[index]
        trajectory.tramos[index] = (start, end, _dense(system, lambda t: np.array([-1., 2.]) if start < t < end else original(t)))
        with self.assertRaises(DomainViolation):
            trajectory.y((start + end) / 2)


if __name__ == '__main__':
    unittest.main()
