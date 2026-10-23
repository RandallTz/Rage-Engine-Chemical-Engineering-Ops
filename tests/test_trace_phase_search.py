"""F0-3 / F0-4 regression: ternary phase search with species traces down to 1e-300.

F0-3: the three-species liquid stability search used unbounded logits; past about 745 a trial composition
underflowed to an exact zero and log(0) escaped as FloatingPointError from equilibrio_PH.
F0-4: benzene-water with a 1e-300 ethanol trace was rejected as not certified, although the same feed with a
1e-100 trace or an exact zero splits and certifies: the seed left the trace at the minimizer's lower bound and
its log/exp round trip decoded the dependent phase as negative.

Independent references (not computed by the routine under test):
- the trace-free (exact zero) state, solved by the binary path;
- infinite dilution: the trace's partition coefficient x_i^a / x_i^b is the same at 1e-100 and 1e-300;
- PH at the enthalpy of a TP state must return that TP state.
Tolerances are the engine's own (TOL_MU, TOL_TM); none is relaxed. Run from the repository root:
    python tests/test_trace_phase_search.py
"""
from pathlib import Path
import sys
import unittest
import warnings
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings('ignore')
from core import mezclas as mz

P = 101325.0
BENZENE, WATER, ETHANOL = '71-43-2', '7732-18-5', '64-17-5'


def certified(test, state):
    for key, (residual, tolerance, _) in state.verificaciones.items():
        test.assertTrue(np.isfinite(residual) and residual <= tolerance, f'{key}: {residual} > {tolerance}')
    for phase in state.fases:
        test.assertTrue(np.all(np.isfinite(phase.x)) and np.all(np.asarray(phase.x) >= 0) and phase.n > 0)


class TracePhaseSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.system = mz.Sistema('unifac-original-public', [BENZENE, WATER, ETHANOL])

    def test_f0_3_ph_with_water_trace_returns_the_tp_state(self):
        for trace in (1e-9, 1e-300):
            with self.subTest(trace=trace):
                n = np.array([1.0, trace, 1.0])
                tp = self.system.equilibrio_TP(345.0, P, n)
                ph = self.system.equilibrio_PH(P, tp.H, n)       # raised FloatingPointError before the fix
                certified(self, ph)
                self.assertAlmostEqual(ph.T, 345.0, delta=1e-6)
                self.assertEqual(sorted(f.tipo for f in ph.fases), sorted(f.tipo for f in tp.fases))
                self.assertLess(abs(ph.H - tp.H), 1e-8 * abs(tp.H))

    def test_f0_4_liquid_liquid_split_with_ethanol_trace(self):
        for T, kinds in ((300.0, ['liquido', 'liquido']), (345.0, ['liquido', 'vapor'])):
            reference = self.system.equilibrio_TP(T, P, np.array([1.0, 1.0, 0.0]))
            ratios = {}
            for trace in (1e-100, 1e-300):
                with self.subTest(T=T, trace=trace):
                    n = np.array([1.0, 1.0, trace])
                    state = self.system.equilibrio_TP(T, P, n)     # rejected (tm < 0) before the fix
                    certified(self, state)
                    self.assertEqual(sorted(f.tipo for f in state.fases), kinds)
                    by_kind = lambda s: sorted(s.fases, key=lambda f: (f.tipo, -f.x[0]))
                    for phase, ref in zip(by_kind(state), by_kind(reference)):
                        self.assertAlmostEqual(phase.n, ref.n, delta=1e-9)
                        np.testing.assert_allclose(phase.x[:2] / phase.x[:2].sum(), ref.x[:2] / ref.x[:2].sum(), atol=1e-9)
                    total = sum(f.n * f.x[2] for f in state.fases)
                    self.assertLess(abs(total - trace) / trace, 1e-12)
                    a, b = by_kind(state)
                    ratios[trace] = a.x[2] / b.x[2]
            self.assertLess(abs(ratios[1e-300] / ratios[1e-100] - 1), 1e-6)

    def test_f0_4_ph_with_ethanol_trace_and_domain_edge(self):
        # The isobaric search also evaluates TP at the lower bracket edge (278.68 K, benzene's P_sat bound),
        # where the minimizer leaves the trace at an exact zero in one phase.
        n = np.array([1.0, 1.0, 1e-300])
        edge = self.system.equilibrio_TP(self.system.T_rango[0], P, n)
        certified(self, edge)
        self.assertEqual(sorted(f.tipo for f in edge.fases), ['liquido', 'liquido'])
        for T in (300.0, 345.0):
            with self.subTest(T=T):
                tp = self.system.equilibrio_TP(T, P, n)
                ph = self.system.equilibrio_PH(P, tp.H, n)
                certified(self, ph)
                self.assertAlmostEqual(ph.T, T, delta=1e-6)
                self.assertEqual(sorted(f.tipo for f in ph.fases), sorted(f.tipo for f in tp.fases))


if __name__ == '__main__':
    unittest.main()
