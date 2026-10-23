"""F9-R2 regression: three-phase invariant points (binary heteroazeotropes) and the invariant polish.

Independent references, computed without the plateau path under test:
- Gibbs phase rule: at fixed P a binary has its L1 L2 V point at a single T. That T is located here by
  bisection on TP flashes only (two liquids below, a vapor above) and compared with the literature
  heteroazeotropes at 101325 Pa (water-1-butanol 365.85 K, water-benzene 342.45 K; UNIFAC is predictive,
  so a 1.5 K band is allowed).
- The chemical potentials of the three published phases are recomputed with Sistema.mu.
- The material balance and the H target are checked against the feed.

Before the fix, a Newton trial in _pulir_invariante could reach logits beyond the float range: np.exp
overflowed and the composition became inf/inf (unhandled overflow and invalid events), although the
point was then discarded. Trials are now rejected before exponentiation. Run from the repository root:
    python tests/test_invariant_point_polish.py
"""
from pathlib import Path
import sys
import unittest
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import mezclas as mz

P = 101325.0
WATER, BUTANOL, BENZENE = '7732-18-5', '71-36-3', '71-43-2'
LITERATURE = {BUTANOL: 365.85, BENZENE: 342.45}


class FloatingPointEvents:
    """Record every unhandled NumPy floating-point event (local errstate blocks still take precedence)."""

    def __enter__(self):
        self.events = []
        self.previous = np.seterr(over='call', invalid='call', divide='call', under='ignore')
        self.callback = np.seterrcall(lambda kind, flag: self.events.append(kind))
        return self

    def __exit__(self, *exc):
        np.seterr(**self.previous)
        np.seterrcall(self.callback)


def phase_kinds(state):
    return sorted(phase.tipo for phase in state.fases)


def invariant_bracket(system, z, guess):
    lo, hi = guess - 25.0, guess + 25.0
    has_vapor = lambda T: 'vapor' in phase_kinds(system.equilibrio_TP(T, P, z))
    assert not has_vapor(lo) and has_vapor(hi)
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        lo, hi = (lo, mid) if has_vapor(mid) else (mid, hi)
    return lo, hi


class InvariantPointPolish(unittest.TestCase):
    def check_heteroazeotrope(self, package, organic):
        system = mz.Sistema(package, [WATER, organic])
        z = np.array([0.7, 0.3])
        lo, hi = invariant_bracket(system, z, LITERATURE[organic])
        self.assertLess(abs(hi - LITERATURE[organic]), 1.5)
        below, above = system.equilibrio_TP(lo, P, z), system.equilibrio_TP(hi, P, z)
        self.assertEqual(phase_kinds(below), ['liquido', 'liquido'])
        H = 0.5 * (below.H + above.H)
        with FloatingPointEvents() as fp:
            state = system.equilibrio_PH(P, H, z)
        self.assertEqual(fp.events, [])
        self.assertEqual(phase_kinds(state), ['liquido', 'liquido', 'vapor'])
        self.assertLessEqual(lo - 1e-9 * lo, state.T)
        self.assertLessEqual(state.T, hi + 1e-9 * hi)
        for key, (residual, tolerance, _) in state.verificaciones.items():
            self.assertTrue(np.isfinite(residual) and residual <= tolerance, key)
        for phase in state.fases:
            self.assertTrue(np.all(np.isfinite(phase.x)) and np.all(phase.x >= 0) and phase.n > 0)
        total = sum(phase.n * np.asarray(phase.x) for phase in state.fases)
        np.testing.assert_allclose(total, z, rtol=0, atol=1e-10)
        self.assertLess(abs(state.H - H), 1e-8 * abs(H))
        idx = [0, 1]
        mus = [np.asarray(system.mu(phase.tipo, state.T, P, np.asarray(phase.x)[idx], idx)) for phase in state.fases]
        spread = max(float(np.max(np.abs(mu - mus[0]))) for mu in mus) / (mz.R * state.T)
        self.assertLess(spread, mz.TOL_MU)
        return system, below, above

    def test_water_butanol_original(self):
        self.check_heteroazeotrope('unifac-original-public', BUTANOL)

    def test_water_butanol_dortmund(self):
        self.check_heteroazeotrope('unifac-dortmund-public', BUTANOL)

    def test_water_benzene_original(self):
        self.check_heteroazeotrope('unifac-original-public', BENZENE)

    def test_out_of_range_trials_are_rejected_without_floating_point_events(self):
        system = mz.Sistema('unifac-original-public', [WATER, BUTANOL])
        # A seed with two vapor phases near the upper T domain edge drives the Newton logits past the
        # float range; before the fix this produced overflow and invalid events in np.exp.
        seed = [('vapor', np.array([0.7, 0.3])), ('vapor', np.array([0.6, 0.4])), ('liquido', np.array([0.98, 0.02]))]
        with FloatingPointEvents() as fp:
            out = mz._pulir_invariante(system, system.T_rango[1] * 0.9999, P, 'T', seed, [0, 1], relative_window=1e-6)
        self.assertIsNone(out)
        self.assertEqual(fp.events, [])

    def test_valid_seed_still_converges(self):
        system = mz.Sistema('unifac-original-public', [WATER, BUTANOL])
        z = np.array([0.7, 0.3])
        lo, hi = invariant_bracket(system, z, LITERATURE[BUTANOL])
        below, above = system.equilibrio_TP(lo, P, z), system.equilibrio_TP(hi, P, z)
        seed = [(f.tipo, np.asarray(f.x, dtype=float)) for f in below.fases] + \
               [(f.tipo, np.asarray(f.x, dtype=float)) for f in above.fases if f.tipo == 'vapor']
        out = mz._pulir_invariante(system, 0.5 * (lo + hi), P, 'T', seed, [0, 1], relative_window=1e-6)
        self.assertIsNotNone(out)
        self.assertLess(abs(out[0] - 0.5 * (lo + hi)), 1e-6 * hi)


if __name__ == '__main__':
    unittest.main()
