"""Independent checks of core/reactions/jacobian_bounds.reaction_jacobian_bounds (F5, Claude, 5 November 2026).

The reference never reuses the module's closed forms or its Gibbs-Helmholtz derivative:
- g_j = sum_i nu_ij mu_i / (R T) is rebuilt in mpmath at 40-50 digits from the Poling cp/R coefficients by
  QUADRATURE (h = int cp dT, s = int cp/T dT from T0), the formation data and R T ln(x_i P/P0);
- dg/dT, dg/dn_k and dg/dP are mpmath numerical derivatives (mp.diff) of that same function;
- sampled float values come from the provider itself (IdealGasPhase.mu through evaluate_reactions).
Cases: (a) analytic ammonia synthesis at a point and over a box; (b) methanol synthesis + water-gas shift
(a Dnu = 0 row) under dense random sampling plus every box corner; (c) outward rounding of singleton boxes
and of the binary64 conversion; (d) trace inventories; (e) rejections and located uncertified results;
(f) chemical energy once: -R T^2 dg/dT against sum nu_i h_i of evaluate_reactions; (g) fingerprints.
Run: python tests/test_reaction_jacobian_bounds.py
"""
import itertools
import math
import sys
import unittest
from fractions import Fraction
from pathlib import Path

import mpmath as m
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.reactions import chemical_equilibrium as ce
from core.reactions import jacobian_bounds as jb
from core.reactions.jacobian_bounds import reaction_jacobian_bounds

N2, H2, NH3 = "7727-37-9", "1333-74-0", "7664-41-7"
CO, CO2, H2O, MEOH = "630-08-0", "124-38-9", "7732-18-5", "67-56-1"
VAP = {"phase_id": "vapor", "standard_state": "ideal_gas_P0"}


class Reference:
    """g(T, P, n) of an IdealGasPhase in mpmath by quadrature; derivatives by mp.diff."""

    def __init__(self, gas, nu, dps=40):
        self.gas, self.nu, self.dps = gas, [list(map(float, r)) for r in nu], dps

    def _mu(self, i, T, P, n):
        R, T0, P0 = m.mpf(ce.R), m.mpf(298.15), m.mpf(1e5)
        a = [m.mpf(c) for c in self.gas.especies[i].cp]
        cp = lambda t: R * sum(a[k] * t ** k for k in range(len(a)))
        h = m.quad(cp, [T0, T])
        s = m.quad(lambda t: cp(t) / t, [T0, T])
        N = sum(n)
        return h - T * s + m.mpf(self.gas.Hf[i]) - T * m.mpf(self.gas.S0[i]) + R * T * m.log(n[i] / N * P / P0)

    def g(self, j, T, P, n):
        with m.workdps(max(m.mp.dps, self.dps)):           # never lower the caller's (mp.diff's) precision
            T, P, n = m.mpf(T), m.mpf(P), [m.mpf(v) for v in n]
            return sum(self.nu[j][i] * self._mu(i, T, P, n) for i in range(len(n)) if self.nu[j][i]) \
                / (m.mpf(ce.R) * T)

    def _diff(self, f, x):
        # central difference with a relative step 1e-20 at dps + 40: truncation ~1e-40, rounding ~1e-(dps)
        with m.workdps(self.dps + 40):
            x = m.mpf(x)
            return m.diff(f, x, h=abs(x) * m.mpf("1e-20"))

    def dT(self, j, T, P, n):
        return self._diff(lambda t: self.g(j, t, P, n), T)

    def dP(self, j, T, P, n):
        return self._diff(lambda p: self.g(j, T, p, n), P)

    def dn(self, j, k, T, P, n):
        def f(v):
            q = [m.mpf(x) for x in n]
            q[k] = v
            return self.g(j, T, P, q)
        return self._diff(f, n[k])


REF_NOISE = m.mpf("1e-30")   # absolute rounding floor of the mp.diff reference (about 1e-56 at dps + 40)


def inside(pair, value, slack=REF_NOISE):
    """value (an mpmath reference) inside the binary64 pair, up to the reference's own noise floor; it matters
    only for exactly-zero entries such as dg/dP of a Dnu = 0 row, whose enclosure is a few subnormals wide."""
    lo, hi = pair
    return m.mpf(lo) - slack <= value <= m.mpf(hi) + slack


class AnalyticAmmonia(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gas = ce.IdealGasPhase([N2, H2, NH3])
        cls.nu = [[-1, -3, 2]]
        cls.ref = Reference(cls.gas, cls.nu, dps=50)

    def test_point_box_encloses_high_precision_values(self):
        T, P, n = 700.0, 5e6, [1.0, 3.0, 0.1]
        box = {"T": [T, T], "P": [P, P], "n": [[v, v] for v in n]}
        out = reaction_jacobian_bounds(self.gas, self.nu, box, **VAP)
        self.assertTrue(out["certified"], out["diagnostics"])
        b = out["bounds"]
        self.assertTrue(inside(b["g"][0], self.ref.g(0, T, P, n)))
        self.assertTrue(inside(b["dg_dT"][0], self.ref.dT(0, T, P, n)))
        self.assertTrue(inside(b["dg_dP"][0], self.ref.dP(0, T, P, n)))
        for k in range(3):
            self.assertTrue(inside(b["dg_dn"][0][k], self.ref.dn(0, k, T, P, n)), k)
        # point boxes are tight: a few ulps
        for pair in [b["g"][0], b["dg_dT"][0], b["dg_dP"][0]] + b["dg_dn"][0]:
            self.assertLess(pair[1] - pair[0], 1e-12 * max(1.0, abs(pair[0])))

    def test_closed_form_derivatives_by_hand(self):
        # dg/dn_k = nu_k/n_k - Dnu/N and dg/dP = Dnu/P, written here independently of the module
        n, P = [1.0, 3.0, 0.1], 2e5
        box = {"T": [650.0, 650.0], "P": [P, P], "n": [[v, v] for v in n]}
        b = reaction_jacobian_bounds(self.gas, self.nu, box, **VAP)["bounds"]
        N = Fraction(1) + Fraction(3) + Fraction(0.1)
        for k, nuk in enumerate([-1, -3, 2]):
            exact = Fraction(nuk) / Fraction(n[k]) - Fraction(-2) / N
            self.assertTrue(Fraction(b["dg_dn"][0][k][0]) < exact < Fraction(b["dg_dn"][0][k][1]), k)
        self.assertTrue(Fraction(b["dg_dP"][0][0]) < Fraction(-2) / Fraction(P) < Fraction(b["dg_dP"][0][1]))

    def test_box_encloses_corners_and_interior(self):
        box = {"T": [600.0, 750.0], "P": [1e5, 5e6], "n": [[0.5, 1.0], [1.0, 3.0], [0.05, 1.0]]}
        out = reaction_jacobian_bounds(self.gas, self.nu, box, **VAP)
        b = out["bounds"]
        pts = list(itertools.product(box["T"], box["P"], *box["n"]))
        rng = np.random.default_rng(7)
        pts += [tuple(rng.uniform(lo, hi) for lo, hi in [box["T"], box["P"], *box["n"]]) for _ in range(8)]
        for T, P, *n in pts:
            self.assertTrue(inside(b["g"][0], self.ref.g(0, T, P, n)), (T, P, n))
            self.assertTrue(inside(b["dg_dT"][0], self.ref.dT(0, T, P, n)), (T, P, n))
            self.assertTrue(inside(b["dg_dP"][0], self.ref.dP(0, T, P, n)), (T, P, n))
            for k in range(3):
                self.assertTrue(inside(b["dg_dn"][0][k], self.ref.dn(0, k, T, P, n)), (k, T, P, n))

    def test_result_record(self):
        box = {"T": [600.0, 610.0], "P": [1e5, 1e5], "n": [[1, 1], [3, 3], [0.1, 0.2]]}
        out = reaction_jacobian_bounds(self.gas, self.nu, box, **VAP)
        self.assertEqual((out["format"], out["version"]), ("rage.reaction-jacobian-bounds", 1))
        self.assertEqual(out["species"], [N2, H2, NH3])
        self.assertEqual(out["nu"], [[-1.0, -3.0, 2.0]])
        self.assertEqual((out["phase_id"], out["standard_state"], out["anchor"]), ("vapor", "ideal_gas_P0", "gas"))
        self.assertEqual(set(out["fingerprints"]), {"package", "pureData", "formationReference"})
        self.assertEqual(set(out["proof"]), {"method", "rounding", "assumptions", "validity", "precision_bits",
                                             "temperature_pieces"})
        self.assertEqual(out["diagnostics"], [])
        self.assertTrue(all(r["balanced"] for r in out["proof"]["validity"]["elements"]["reactions"]))


class DenseSamplingMethanol(unittest.TestCase):
    """Methanol synthesis and water-gas shift (Dnu = 0): every provider sample inside the enclosure."""

    @classmethod
    def setUpClass(cls):
        cls.gas = ce.IdealGasPhase([CO, CO2, H2, H2O, MEOH])
        cls.nu = [[-1, 0, -2, 0, 1], [-1, 1, 1, -1, 0]]
        cls.box = {"T": [480.0, 560.0], "P": [2e6, 8e6],
                   "n": [[0.2, 1.0], [0.05, 0.4], [1.0, 3.0], [0.01, 0.3], [0.02, 0.5]]}
        cls.out = reaction_jacobian_bounds(cls.gas, cls.nu, cls.box, **VAP)
        cls.ref = Reference(cls.gas, cls.nu, dps=30)

    def test_certified(self):
        self.assertTrue(self.out["certified"], self.out["diagnostics"])

    def test_dense_provider_samples(self):
        b, rng = self.out["bounds"], np.random.default_rng(2026)
        intervals = [self.box["T"], self.box["P"], *self.box["n"]]
        pts = [tuple(rng.uniform(lo, hi) for lo, hi in intervals) for _ in range(3000)]
        pts += list(itertools.product(*intervals))                       # all 128 corners
        for T, P, *n in pts:
            st = ce.evaluate_reactions(self.gas, self.nu, T=T, P=P, n=n, **VAP)
            for j, g in enumerate(st["affinity_RT"]):
                self.assertTrue(b["g"][j][0] <= g <= b["g"][j][1], (j, T, P, n, g, b["g"][j]))
            # derivatives: the provider's own finite differences (point estimates) must also fall inside
            J = np.asarray(st["nu"]) @ np.asarray(st["dmu_dn"]) / (ce.R * T)
            for j in range(2):
                for k in range(5):
                    lo, hi = b["dg_dn"][j][k]
                    tol = 1e-5 * max(abs(lo), abs(hi), 1.0 / sum(n))     # finite-difference noise allowance
                    self.assertTrue(lo - tol <= J[j, k] <= hi + tol, (j, k, J[j, k]))

    def test_derivative_samples_against_independent_reference(self):
        b, rng = self.out["bounds"], np.random.default_rng(11)
        intervals = [self.box["T"], self.box["P"], *self.box["n"]]
        pts = [tuple(rng.uniform(lo, hi) for lo, hi in intervals) for _ in range(6)]
        pts += [tuple(c) for c in itertools.product(*intervals)][::37]
        for T, P, *n in pts:
            for j in range(2):
                self.assertTrue(inside(b["dg_dT"][j], self.ref.dT(j, T, P, n)), (j, T))
                self.assertTrue(inside(b["dg_dP"][j], self.ref.dP(j, T, P, n)), (j, P))
                for k in range(5):
                    self.assertTrue(inside(b["dg_dn"][j][k], self.ref.dn(j, k, T, P, n)), (j, k))

    def test_zero_dnu_row_has_no_pressure_dependence(self):
        lo, hi = self.out["bounds"]["dg_dP"][1]
        self.assertTrue(lo <= 0.0 <= hi and hi - lo < 1e-300)

    def test_chemical_energy_once(self):
        # -R T^2 dg/dT = Delta H(T) = sum nu_i h_i with h_i (formation included once) from evaluate_reactions
        T, P, n = 520.0, 4e6, [0.6, 0.2, 2.0, 0.1, 0.3]
        box = {"T": [T, T], "P": [P, P], "n": [[v, v] for v in n]}
        b = reaction_jacobian_bounds(self.gas, self.nu, box, **VAP)["bounds"]
        st = ce.evaluate_reactions(self.gas, self.nu, T=T, P=P, n=n, **VAP)
        dH = np.asarray(self.nu, dtype=float) @ np.asarray(st["h_partial"])
        for j in range(2):
            mid = -0.5 * sum(b["dg_dT"][j]) * ce.R * T ** 2
            self.assertLess(abs(mid - dH[j]), 1e-6 * abs(dH[j]), j)   # central-difference h_i in the provider


class OutwardRounding(unittest.TestCase):
    def test_conversion_is_directed_and_widened(self):
        from mpmath import iv
        old = iv.prec
        iv.prec = 113
        try:
            x = iv.mpf(1) / iv.mpf(3)
            lo, hi = jb._to_pair(x)
        finally:
            iv.prec = old
        third = Fraction(1, 3)
        self.assertTrue(Fraction(lo) < third < Fraction(hi))
        # floor and ceiling of an inexact value are adjacent doubles; one ulp more on each side: three ulps
        self.assertEqual(math.nextafter(math.nextafter(math.nextafter(lo, math.inf), math.inf), math.inf), hi)
        lo1, hi1 = jb._to_pair(iv.mpf(0.5))                             # exact value: one ulp each side
        self.assertEqual((math.nextafter(lo1, math.inf), math.nextafter(hi1, -math.inf)), (0.5, 0.5))

    def test_singleton_pairs_strictly_contain_reference(self):
        gas = ce.IdealGasPhase([N2, H2, NH3])
        ref = Reference(gas, [[-1, -3, 2]], dps=50)
        for T, P, n in ((300.0, 1e5, [1.0, 3.0, 1e-3]), (900.0, 3e7, [2.0, 1.0, 5.0])):
            box = {"T": [T, T], "P": [P, P], "n": [[v, v] for v in n]}
            b = reaction_jacobian_bounds(gas, [[-1, -3, 2]], box, **VAP)["bounds"]
            g = ref.g(0, T, P, n)
            self.assertTrue(m.mpf(b["g"][0][0]) < g < m.mpf(b["g"][0][1]))
            self.assertTrue(m.mpf(b["dg_dT"][0][0]) < ref.dT(0, T, P, n) < m.mpf(b["dg_dT"][0][1]))


class TraceAndRejection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gas = ce.IdealGasPhase([N2, H2, NH3])
        cls.nu = [[-1, -3, 2]]
        cls.box = {"T": [600.0, 700.0], "P": [1e5, 1e6], "n": [[0.5, 1.0], [1.0, 3.0], [0.1, 1.0]]}

    def call(self, **change):
        box = {**self.box, **change}
        return reaction_jacobian_bounds(self.gas, self.nu, box, **VAP)

    def test_trace_inventory_certified_and_enclosing(self):
        ref = Reference(self.gas, self.nu, dps=50)
        out = self.call(n=[[1.0, 1.0], [3.0, 3.0], [1e-14, 1e-12]])
        self.assertTrue(out["certified"])
        for nk in (1e-14, 3e-13, 1e-12):
            n = [1.0, 3.0, nk]
            self.assertTrue(inside(out["bounds"]["g"][0], ref.g(0, 650.0, 3e5, n)))
            self.assertTrue(inside(out["bounds"]["dg_dn"][0][2], ref.dn(0, 2, 650.0, 3e5, n)))

    def test_underflowing_trace_is_located_not_approximated(self):
        out = self.call(n=[[1.0, 1.0], [3.0, 3.0], [1e-320, 1e-300]])
        self.assertFalse(out["certified"])
        self.assertIsNone(out["bounds"])
        self.assertIsNone(out["proof"])
        self.assertIn(("NONFINITE_BOUND", "bounds.dg_dn[0][2]"),
                      [(d["code"], d["path"]) for d in out["diagnostics"]])

    def test_temperature_outside_cp_range_uncertified(self):
        out = self.call(T=[600.0, 2500.0])
        self.assertFalse(out["certified"])
        self.assertIsNone(out["bounds"])
        self.assertTrue(out["diagnostics"] and all(d["code"] == "OUT_OF_DOMAIN" and d["path"] == "box.T"
                                                   for d in out["diagnostics"]))

    def test_unbalanced_row_uncertified(self):
        out = reaction_jacobian_bounds(self.gas, [[-1, -3, 2], [-1, -2, 2]], self.box, **VAP)
        self.assertFalse(out["certified"])
        self.assertEqual([(d["code"], d["path"]) for d in out["diagnostics"]],
                         [("FORMATION_REFERENCE_INVALID", "nu[1]")])

    def test_package_phase_reported_unsupported(self):
        from core.mezclas import Sistema
        phase = ce.PackagePhase(Sistema("unifac-dortmund-public", ["64-17-5", "71-36-3", H2O]), "liquido")
        box = {"T": [340.0, 341.0], "P": [1e5, 1e5], "n": [[1, 1], [1, 1], [1, 1]]}
        out = reaction_jacobian_bounds(phase, [[0, 0, 0]], box, phase_id="liquido", standard_state="pure_liquid_TP")
        self.assertFalse(out["certified"])
        self.assertEqual([d["code"] for d in out["diagnostics"]], ["PROVIDER_UNSUPPORTED"])
        self.assertEqual(out["anchor"], "gas")
        self.assertEqual(set(out["fingerprints"]), {"package", "pureData", "formationReference"})

    def assertRejects(self, code, path, fn):
        with self.assertRaises(ce.ChemicalEquilibriumError) as cm:
            fn()
        self.assertEqual((cm.exception.code, cm.exception.detail.get("path")), (code, path))

    def test_malformed_input_rejected(self):
        R = lambda **kw: (lambda: reaction_jacobian_bounds(self.gas, kw.pop("nu", self.nu),
                                                           kw.pop("box", self.box), **{**VAP, **kw}))
        self.assertRejects("PHASE_MISMATCH", "phase_id", R(phase_id="liquido"))
        self.assertRejects("STANDARD_STATE_MISMATCH", "standard_state", R(standard_state="pure_liquid_TP"))
        self.assertRejects("NU_SHAPE", "nu", R(nu=[[-1, -3]]))
        self.assertRejects("NU_NONFINITE", "nu[0][1]", R(nu=[[-1, float("nan"), 2]]))
        self.assertRejects("BOX_KEYS", "box", R(box={"T": [600, 700], "P": [1e5, 1e5]}))
        self.assertRejects("BOX_KEYS", "box", R(box={**self.box, "V": [1, 2]}))
        self.assertRejects("BOX_UNORDERED", "box.T", R(box={**self.box, "T": [700, 600]}))
        self.assertRejects("BOX_NONPOSITIVE", "box.P[0]", R(box={**self.box, "P": [0.0, 1e5]}))
        self.assertRejects("BOX_NONPOSITIVE", "box.n[2][0]",
                           R(box={**self.box, "n": [[0.5, 1], [1, 3], [0.0, 1]]}))
        self.assertRejects("BOX_NONFINITE", "box.T[1]", R(box={**self.box, "T": [600, math.inf]}))
        self.assertRejects("BOX_SHAPE", "box.n", R(box={**self.box, "n": [[0.5, 1], [1, 3]]}))
        self.assertRejects("BOX_SHAPE", "box.n[0]", R(box={**self.box, "n": [[0.5], [1, 3], [1, 2]]}))
        self.assertRejects("BOX_TYPE", "box.T[0]", R(box={**self.box, "T": [True, 700]}))
        self.assertRejects("PROVIDER_TYPE", "provider",
                           lambda: reaction_jacobian_bounds(object(), self.nu, self.box, **VAP))

    def test_fingerprints_pin_references(self):
        again = reaction_jacobian_bounds(ce.IdealGasPhase([N2, H2, NH3]), self.nu, self.box, **VAP)
        base = self.call()
        self.assertEqual(base["fingerprints"], again["fingerprints"])
        janaf = ce.IdealGasPhase([N2, H2, NH3], source={NH3: "JANAF", N2: ("CRC", "WEBBOOK"),
                                                          H2: ("CRC", "WEBBOOK")})
        other = reaction_jacobian_bounds(janaf, self.nu, self.box, **VAP)
        self.assertNotEqual(base["fingerprints"]["formationReference"], other["fingerprints"]["formationReference"])
        self.assertEqual(base["fingerprints"]["pureData"], other["fingerprints"]["pureData"])

    def test_narrow_box_is_tight(self):
        out = self.call(T=[650.0, 650.01], P=[2e5, 2e5], n=[[1.0, 1.0], [3.0, 3.0], [0.1, 0.1]])
        lo, hi = out["bounds"]["g"][0]
        dlo, dhi = out["bounds"]["dg_dT"][0]
        self.assertLess(hi - lo, 1e-3 * 1.01)          # |dg/dT| ~ 0.03 1/K over 0.01 K, with headroom
        self.assertLess(dhi - dlo, 1e-6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
