"""Demo 0.3 C6: saturating min/max branches are regime events of the derived signature.

The loop is the C1 PI loop on the temperature of one closed rigid region, authored
from the energy law through the shared pinned operations (`tests/test_control_kernel.py`),
with a valve `min(max(u_c, u_min), u_max)`. With u_max = 0.2 the valve starts saturated;
while it is saturated the hand-derived trajectory is

    T = T0 + P u_max t/(m c),  I = (r - T0) t - P u_max t^2/(2 m c),
    u_c = K_c (r - T + I/tau_I) = 0.5 - 1e-4 t^2,

so the valve leaves saturation at t* = sqrt(3000) s, with du_c/dt = -2e-4 t*. Acceptance
(roadmap Demo 0.3, DR-6), asserted literally for RK45 and BDF at rtol 1e-6, 1e-8 and 1e-10:
|t_e - t*| <= 10 rtol |u_c| / |du_c/dt|, and the event sits on the run's own crossing. The
C6 review (C6-R1) showed that bisecting on one accepted step's interpolant missed this bound;
the integrator now places a regime change on reintegrated endpoints (`_refine_change`).
"""
import copy
import math
from pathlib import Path
import sys
import unittest

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from test_control_kernel import HEAT_CAPACITY, LOOP, T0, author_pid, lowered_model
from core.compilador.derived import DerivedSystem, LoweringError, resolve_system
from core.solvers import integrar
from core.solvers.timeline import TimelineRun

U_MAX, U_MIN = 0.2, -0.1
SATURATED = {'commandMax': (U_MAX, '1'), 'commandMin': (U_MIN, '1')}
RTOL = 1e-10


def exit_time():
    """Root of u_c(t) = u_max on the saturated arc, and the slope of u_c there."""
    gain, setpoint, integral_time = LOOP['gain'][0], LOOP['setpoint'][0], LOOP['integralTime'][0]
    rise = LOOP['heaterPower'][0] * U_MAX / HEAT_CAPACITY             # K/s while saturated
    # u_c = K_c (r - T0 - a t + ((r - T0) t - a t^2/2)/tau_I) = u_max, a quadratic in t.
    c2 = -gain * rise / (2 * integral_time)
    c1 = gain * (-rise + (setpoint - T0) / integral_time)
    c0 = gain * (setpoint - T0) - U_MAX
    roots = [r.real for r in np.roots([c2, c1, c0]) if abs(r.imag) == 0 and r.real > 0]
    t_exit = min(roots)
    return t_exit, 2 * c2 * t_exit + c1


def run(system, method='RK45'):
    study = system.model['estudio']
    return integrar(system, system.initial(), system.tf, rtol=study['rtol'], atol=system.numeric.atol,
                    max_step=system.tf / (study['muestras'] - 1), metodo=method)


def regime_changes(trajectory):
    return [(t, before, after) for code, t, before, after, _ in trajectory.eventos if code == 'cambio_firma']


def own_crossing(system, trajectory, t, regime=0, half_width=1.):
    """Crossing of the two arguments of one regime on the run's own dense output, bisected near t."""
    f = system.regimes[regime]['evaluate']
    g = lambda s: f[0](s, trajectory.y(s)) - f[1](s, trajectory.y(s))
    lo, hi = max(0., t - half_width), t + half_width
    assert np.sign(g(lo)) != np.sign(g(hi)), (g(lo), g(hi))
    for _ in range(200):
        m = 0.5 * (lo + hi)
        if np.sign(g(m)) == np.sign(g(lo)):
            lo = m
        else:
            hi = m
    return 0.5 * (lo + hi)


class RegimeEventTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.author, cls.rows = author_pid()
        cls.model = lowered_model(cls.author, cls.rows, SATURATED)
        cls.model['estudio']['rtol'] = RTOL
        cls.system = DerivedSystem(copy.deepcopy(cls.model))
        cls.integral = cls.system.states.index(cls.system.quantities['integral'])

    def test_min_and_max_nodes_are_signature_entries(self):
        system = self.system
        self.assertEqual([r['function'] for r in system.regimes], ['min', 'max'])
        self.assertEqual([r['id'] for r in system.regimes], ['regime.1', 'regime.2'])
        self.assertTrue(all(r['equationIds'] == [self.rows['energy']] for r in system.regimes))
        signature, margins = system.event_state(0., system.initial())
        self.assertEqual(signature, system.firma(0., system.initial()))
        # Saturated at the upper limit: the min selects u_max; the max selects u_c (above u_min).
        upper = system.regimes[0]['arguments'][signature[0][2]]
        self.assertIn('commandMax', upper.replace('{', '').replace('}', '').replace('\\', ''))
        self.assertEqual(len(margins), 2)
        # min gap: u_c = 0.5 against u_max = 0.2 over |0.5|; max gap: 0.5 against -0.1 over |0.5|.
        self.assertAlmostEqual(margins[0], 0.3 / 0.5, delta=1e-12)
        self.assertAlmostEqual(margins[1], 0.6 / 0.5, delta=1e-12)

    def test_exit_from_saturation_is_located_within_the_slope_tied_bound(self):
        """DR-6, literal: |t_e - t*| <= 10 rtol |u_c| / |du_c/dt| for RK45 and BDF at rtol 1e-6, 1e-8, 1e-10.

        C6-R1 (review): before the repair the change was bisected on one accepted step's interpolant and
        missed this bound by 1.7 to 4.1 times; the event must also sit on the run's own crossing.
        """
        t_exit, slope = exit_time()
        self.assertAlmostEqual(t_exit, math.sqrt(3000), delta=1e-9)
        self.assertAlmostEqual(slope, -2e-4 * math.sqrt(3000), delta=1e-12)
        for rtol in (1e-6, 1e-8, 1e-10):
            model = copy.deepcopy(self.model)
            model['estudio']['rtol'] = rtol
            literal = 10 * rtol * U_MAX / abs(slope)
            for method in ('RK45', 'BDF'):
                with self.subTest(rtol=rtol, method=method):
                    system = DerivedSystem(copy.deepcopy(model))
                    trajectory = run(system, method)
                    changes = regime_changes(trajectory)
                    self.assertTrue(changes)
                    t, before, after = changes[0]
                    self.assertEqual([entry[1] for entry in before if entry not in after], ['regime.1'])
                    self.assertLessEqual(abs(t - t_exit), literal, (t, t_exit, literal))
                    own = own_crossing(system, trajectory, t)
                    self.assertLessEqual(abs(t - own), 1e-2 * literal, (t, own))
                    print(f'C6 exit {method} rtol {rtol:g}: |dt| = {abs(t - t_exit):.3g} s, '
                          f'literal 10 rtol |u_c|/|du_c/dt| = {literal:.3g} s, |t - own crossing| = {abs(t - own):.3g} s')

    def test_lower_limit_entry_sits_on_the_trajectory_crossing(self):
        """C6-R1 second case: the unsaturated loop (u_min = 0, u_max = 1) enters its lower limit.

        Reference: x = T - r, I; x' = a (-x + I/tau_I), I' = -x, a = P K_c/(m c); u_c = K_c (-x + I/tau_I)
        has its first zero at t_ref by the matrix exponential. The literal DR-6 bound degenerates (u_c = 0
        there), so the event is checked against the run's own crossing and the reference within the
        global state error of the run (RK45 6e-9 s, BDF 3.6e-7 s measured at rtol 1e-10).
        """
        from scipy.linalg import expm
        from scipy.optimize import brentq
        gain, tau, power = LOOP['gain'][0], LOOP['integralTime'][0], LOOP['heaterPower'][0]
        a = power * gain / HEAT_CAPACITY
        matrix = np.array([[-a, a / tau], [-1., 0.]])
        z0 = np.array([T0 - LOOP['setpoint'][0], 0.])
        u_c = lambda t: gain * np.array([-1., 1 / tau]) @ (expm(matrix * t) @ z0)
        t_ref = brentq(u_c, 1., 200.)
        model = lowered_model(self.author, self.rows, {'commandMax': (1, '1'), 'commandMin': (0, '1')})
        model['estudio']['rtol'] = RTOL
        for method, tolerance in (('RK45', 1e-7), ('BDF', 1e-6)):
            with self.subTest(method=method):
                system = DerivedSystem(copy.deepcopy(model))
                trajectory = run(system, method)
                t = regime_changes(trajectory)[0][0]
                own = own_crossing(system, trajectory, t, regime=1)
                self.assertLessEqual(abs(t - own), 1e-9, (t, own))
                self.assertLessEqual(abs(t - t_ref), tolerance, (t, t_ref))

    def test_regime_change_is_published_as_an_event(self):
        system = DerivedSystem(copy.deepcopy(self.model))
        result = resolve_system(system)
        self.assertEqual(result['estado'], 'resuelto')
        events = [e for e in result['eventos'] if e['codigo'] == 'regime_change']
        self.assertTrue(events)
        self.assertEqual(events[0]['propietarioId'], 'regime:regime.1')
        self.assertLessEqual(abs(events[0]['valor'] - exit_time()[0]), 1e-6)
        self.assertFalse(any(e['codigo'] == 'cambio_firma' for e in result['eventos']))
        regimes = result['procedencia']['regimes']
        self.assertEqual([r['id'] for r in regimes], ['regime.1', 'regime.2'])
        self.assertTrue(all('evaluate' not in r for r in regimes))
        self.assertEqual([r['initialBranch'] for r in regimes], [s[2] for s in system.firma(0., system.initial())])
        # The compilation report is unchanged in shape: no regime key is added there.
        self.assertNotIn('regimes', result['procedencia']['compilation']['derivedExecution'])

    def test_every_located_change_flips_the_active_branch_of_the_lowered_rhs(self):
        system = DerivedSystem(copy.deepcopy(self.model))
        trajectory = run(system)
        for t, before, after in regime_changes(trajectory):
            state = trajectory.y(t)
            self.assertEqual(system.firma(t, state), after)
            for (_, key, left), (_, _, right) in zip(before, after):
                if left != right:
                    regime = next(r for r in system.regimes if r['id'] == key)
                    values = [f(t, state) for f in regime['evaluate']]
                    self.assertLessEqual(abs(values[left] - values[right]), 1e-6 * max(1., max(map(abs, values))))

    def test_restart_that_changes_the_regime_rebaselines_without_an_event(self):
        system = DerivedSystem(copy.deepcopy(self.model))
        timeline = TimelineRun(system, system.initial(), system.tf, rtol=RTOL, atol=system.numeric.atol,
                               max_step=system.tf / 120, metodo='RK45')
        timeline.advance(20.)
        left = timeline.preview([20.])[0]
        saturated = system.firma(20., left)
        # At T(20) = 324 K, I = -600 K s gives u_c = K_c (6 - 12) = -0.3 < u_min: the operator action moves
        # the valve from the upper to the lower limit. Then u_c' = K_c (-P u_min/(m c) + e/tau_I) = 0.05 (0.1 + 0.12) > 0,
        # so the valve leaves the lower limit about 18 s later: a located event of the new segment.
        timeline.apply({self.integral: -600.})
        # The jump recorded by the driver: the state after the action restarts the step generator.
        t_action, before_jump, right = timeline.jumps[-1]
        self.assertEqual((t_action, list(before_jump)), (20., list(left)))
        self.assertEqual(right[self.integral], -600.)
        lower = system.firma(20., right)
        self.assertEqual([entry[1] for entry in saturated if entry not in lower], ['regime.1', 'regime.2'])
        timeline.advance(system.tf)
        trajectory = timeline.trajectory()
        changes = regime_changes(trajectory)
        self.assertFalse(any(t == 20. for t, _, _ in changes))
        later = [row for row in changes if row[0] > 20.]
        self.assertTrue(later)
        # The first change after the restart starts from the re-baselined signature and is the exit of
        # the inner max from u_min, located where u_c = u_min on the new segment.
        t_exit, before, after = later[0]
        self.assertEqual(before, lower)
        self.assertEqual([entry[1] for entry in before if entry not in after], ['regime.2'])
        self.assertTrue(20. < t_exit < 60., t_exit)
        state = trajectory.y(t_exit)
        self.assertLessEqual(abs(system.regimes[1]['evaluate'][0](t_exit, state) - system.regimes[1]['evaluate'][1](t_exit, state)), 1e-6)

    def test_models_without_min_or_max_attach_no_regime_protocol(self):
        # The C2 heated region (same energy law, a declared duty, no min/max) keeps the earlier protocol:
        # no regime entry, no event_state hook (so the integrator keeps endpoint detection) and no
        # published regime key.
        from test_time_inputs import heated_region, selection_model
        author, energy = heated_region()
        system = DerivedSystem(selection_model(author, energy, parameters=['heaterDuty']))
        self.assertEqual(system.regimes, [])
        self.assertFalse(hasattr(system, 'event_state'))
        self.assertIsNone(system.firma(0., system.initial()))
        result = resolve_system(system)
        self.assertNotIn('regimes', result['procedencia'])
        self.assertFalse(any(e['codigo'] == 'regime_change' for e in result['eventos']))

    def test_scaled_formulation_with_min_max_is_rejected(self):
        model = copy.deepcopy(self.model)
        selection = model['motores']['derivedExecution']
        scaling = {}
        for key in [selection['timeId'], *(row['quantityId'] for row in selection['states'])]:
            q = self.system.quantities[key]
            unit = self.system._unit(q)
            model['datos']['scale.' + key] = {'magnitud': key, 'funcion': 'parametro', 'declaracion': {'texto': '1', 'unidad': unit},
                                              'origen': {'propietarioId': 'estudio', 'ruta': 'scale.' + key}}
            scaling[key] = 'scale.' + key
        selection['scaling'] = scaling
        with self.assertRaises(LoweringError) as caught:
            DerivedSystem(model)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'regime_scaling', caught.exception.diagnostics)


class TimeInputActionAdmissionTests(unittest.TestCase):
    """C2-N4: an action's new time-input value is checked against its index-one box before the restart."""

    def test_out_of_box_action_is_rejected_and_the_run_is_unchanged(self):
        import test_f3_index1_dae as dae
        from test_f3_nonlinear_algebraic import thermal_case
        from test_time_inputs import bound_input, with_held_input
        from core.solvers.timeline import TimelineError
        store = {}
        def held_case(owners=('domain_one', 'domain_two')):
            model, author = thermal_case(owners)
            _, held, store['qid'] = with_held_input(model, author)
            return held, author
        original = dae.thermal_case
        dae.thermal_case = held_case
        try:
            held = dae.dae_case()
        finally:
            dae.thermal_case = original
        qid = store['qid']
        system = DerivedSystem(bound_input(held, qid, 0, 1000))
        index = system.state_ids.index(qid)
        run = TimelineRun(system, system.initial(), system.tf, rtol=held['estudio']['rtol'], atol=system.numeric.atol, metodo='BDF')
        run.advance(system.tf / 4)
        before = (len(run.jumps), run.edge, run.finished)
        with self.assertRaises(TimelineError) as caught:
            run.apply({index: 2000.})
        self.assertEqual(caught.exception.code, 'state_outside_domain')
        self.assertIn(qid, caught.exception.message)
        self.assertIn('motores.derivedExecution.timeInputs.' + qid, caught.exception.message)
        self.assertEqual((len(run.jumps), run.edge, run.finished), before)
        # A value inside the box is then admitted and the run continues past the edge.
        run.apply({index: 500.})
        self.assertEqual(run.jumps[-1][2][index], 500.)
        self.assertTrue(run.advance(system.tf / 2))


if __name__ == '__main__':
    unittest.main()
