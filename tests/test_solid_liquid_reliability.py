"""F9-R10..R14 (5 November 2026 reliability sweep): regressions for core/termodinamica/solid_liquid.py and
solid_data.py.

References are independent of the module's root finders and of its stability test:
- R10: mpmath (40 digits) on the closed van 't Hoff form ln x = -dh/R (1/T - 1/T_m) of an ideal liquid.
- R11: an analytic two-suffix Margules liquid written here (ln gamma_1 = A x_2^2). Its saturation roots are
  solved by mpmath findroot on ln x + A (1 - x)^2 = -dg_fus/RT, and the stability of each root comes from the
  closed-form binodal of the symmetric model, ln(x/(1-x)) = A (2x - 1), and the spinodal x(1-x) = 1/(2A): a
  liquid is stable iff x lies outside [x', 1 - x']. A ternary regular solution is checked against its
  analytic Hessian (indefinite inside the spinodal; globally convex g/RT for small interaction parameters).
- R12: two or three synthetic solids with an ideal liquid whose `rango_T` clips one liquidus; liquidus
  temperatures from the inverse closed form 1/T = 1/T_m - R ln x / dh.
- R14: located rejections and the closed-form melting temperature T_m (1 + dv (P - P_m) / dh_m) (dcp = 0).
Negative control: each test fails against the f8b delivery (commit 76c698e) of the two modules.
Run: python tests/test_solid_liquid_reliability.py
"""
import math
from pathlib import Path
import sys
import unittest

import mpmath as mp
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import mezclas as mz
from core.termodinamica import solid_data as sd
from core.termodinamica.solid_liquid import SolidLiquidSystem

R = mz.R
P = 101325.0
BZ, CY = "71-43-2", "110-82-7"
mp.mp.dps = 40


class Margules2:
    """Two-suffix Margules liquid, g^E/RT = A x1 x2 (analytic, test-owned)."""
    def __init__(self, A):
        self.A = A

    def gE_RT(self, T, x):
        return self.A * x[0] * x[1]

    def lngamma(self, T, x):
        x = np.asarray(x, float)
        return np.array([self.A * x[1] ** 2, self.A * x[0] ** 2])


class Regular3:
    """Ternary regular solution g^E/RT = 1/2 x^T A x (zero diagonal): ln gamma_k = (A x)_k - 1/2 x^T A x."""
    def __init__(self, A):
        self.A = np.asarray(A, float)

    def lngamma(self, T, x):
        x = np.asarray(x, float)
        return self.A @ x - 0.5 * x @ self.A @ x


class ClippedIdeal(mz.LiquidoIdeal):
    def __init__(self, n, rango_T):
        super().__init__(n)
        self.rango_T = rango_T


def van_t_hoff(s, T):
    return mp.exp(-mp.mpf(s.dh_m) / mp.mpf(R) * (1 / mp.mpf(T) - 1 / mp.mpf(s.T_m)))


class TraceSolubility(unittest.TestCase):
    """F9-R10: solubility below 1e-13 (absolute xtol of the delivery returned ~8e-16)."""
    s = sd.SolidPure(BZ, "t", "I", 278.69, P, 1e5, 0.0, 0.0, 100.0)

    def system(self):
        return SolidLiquidSystem([BZ, "T"], mz.LiquidoIdeal(2), solids={BZ: self.s})

    def test_against_mpmath(self):
        sle = self.system()
        for T in (150.0, 134.82, 120.0, 105.0, 100.0):
            ref = van_t_hoff(self.s, T)
            x = sle.solubility(0, T, P)
            self.assertLess(abs(mp.mpf(x) / ref - 1), 1e-12, (T, x, ref))
        # the sweep's three values
        for T, ref in ((150.0, 8.320e-17), (120.0, 1.639e-25), (100.0, 3.228e-34)):
            self.assertLess(abs(sle.solubility(0, T, P) / ref - 1), 1e-3)

    def test_liquidus_T_is_the_same_root(self):
        """x ~ 1e-20 and 1e-34: liquidus_T at the returned solubility gives back T (inverse closed form)."""
        sle = self.system()
        for target in (mp.mpf("1e-20"), mp.mpf("1e-34")):
            T = float(1 / (1 / mp.mpf(self.s.T_m) - mp.mpf(R) * mp.log(target) / mp.mpf(self.s.dh_m)))
            if T < self.s.T_min:
                T = self.s.T_min + 1.0
            x = sle.solubility(0, T, P)
            self.assertLess(abs(sle.liquidus_T(0, [x, 1.0 - x], P) - T), 1e-9 * T)
            self.assertEqual(sle.certify({"T": T, "P": P, "x": [x, 1.0 - x], "solids": [0]})["certificate"],
                             "cumple")

    def test_trace_eutectic(self):
        """Eutectic of the low-solubility solid with a second solid: x_0 at the eutectic is ~1e-20; T and x
        against mpmath on the two closed forms."""
        sb = sd.SolidPure(CY, "b", "I", 140.0, P, 2000.0, 0.0, 0.0, 100.0)
        sle = SolidLiquidSystem([BZ, CY], mz.LiquidoIdeal(2), solids={BZ: self.s, CY: sb})
        g = lambda T: van_t_hoff(self.s, T) + van_t_hoff(sb, T) - 1
        Te = mp.findroot(g, (mp.mpf(100.5), mp.mpf(139.9)), solver="anderson")
        e = sle.eutectic(P)
        self.assertEqual(e["certificate"], "cumple")
        self.assertLess(abs(e["T"] - float(Te)), 1e-9)
        x0 = van_t_hoff(self.s, Te)
        self.assertLess(x0, 1e-18)
        self.assertLess(abs(mp.mpf(e["x"][0]) / x0 - 1), 1e-9)


class LiquidLiquidGap(unittest.TestCase):
    """F9-R11: saturation across a liquid-liquid gap."""
    A = 2.5

    def system(self, A=None):
        return SolidLiquidSystem([BZ, "X"], Margules2(A or self.A), solids={BZ: sd.REGISTRY[BZ]})

    @staticmethod
    def binodal(A):
        return float(mp.findroot(lambda x: mp.log(x / (1 - x)) + A * (1 - 2 * x), (mp.mpf("0.01"), mp.mpf("0.3")),
                                 solver="anderson"))

    @staticmethod
    def dg_fus_RT(T):
        """Benzene record, closed form dh_m (1 - T/T_m) - dcp [T_m - T - T ln(T_m/T)] (dv = 0), over RT."""
        s = sd.REGISTRY[BZ]
        T, Tm = mp.mpf(T), mp.mpf(s.T_m)
        return (s.dh_m * (1 - T / Tm) - s.dcp * (Tm - T - T * mp.log(Tm / T))) / (mp.mpf(R) * T)

    @classmethod
    def roots(cls, A, T):
        c = cls.dg_fus_RT(T)
        f = lambda x: mp.log(x) + A * (1 - x) ** 2 + c
        grid = [mp.mpf(k) / 2000 for k in range(1, 2000)] + [mp.mpf(1) - mp.mpf("1e-9")]
        out = []
        for a, b in zip(grid[:-1], grid[1:]):
            if f(a) * f(b) < 0:
                out.append(float(mp.findroot(f, (a, b), solver="anderson")))
        return out

    def test_three_roots_stable_one_returned(self):
        xb = self.binodal(self.A)
        spin = 0.5 * (1 - math.sqrt(1 - 2 / self.A))
        self.assertAlmostEqual(xb, 0.1447941082560, places=10)
        for A, T in ((2.5, 275.0), (2.5, 276.0), (3.0, 278.0)):
            ref = self.roots(A, T)
            self.assertEqual(len(ref), 3)
            xb = self.binodal(A)
            stable_ref = [x for x in ref if x < xb or x > 1 - xb]
            self.assertEqual(len(stable_ref), 1)
            sle = self.system(A)
            got = sle.solubility_roots(0, T, P)
            self.assertEqual(len(got), 3)
            for r, x in zip(got, ref):
                self.assertLess(abs(r["x"] - x), 1e-12)
                self.assertEqual(r["stable"], x < xb or x > 1 - xb, (A, T, x))
            self.assertLess(abs(sle.solubility(0, T, P) - stable_ref[0]), 1e-12)
        # the root inside the spinodal and the metastable root are both rejected as liquids
        self.assertTrue(spin > xb)

    def test_no_branch_jump_between_275_and_276_K(self):
        sle = self.system()
        a, b = sle.solubility(0, 275.0, P), sle.solubility(0, 276.0, P)
        self.assertGreater(a, 0.9)
        self.assertGreater(b, a)

    def test_unstable_liquid_not_certified(self):
        sle = self.system()
        with self.assertRaises(mz.FueraDeAlcance) as cm:
            sle.liquidus_T(0, [0.5, 0.5], P)
        self.assertEqual(cm.exception.datos["cause"], "liquid_liquid_instability")
        # x = 0.5 is inside the spinodal: d2(g/RT)/dx2 = 1/(x1 x2) - 2A = -1
        self.assertLess(1 / 0.25 - 2 * self.A, 0)
        T = float(mp.findroot(lambda t: mp.log(mp.mpf(0.5)) + self.A * mp.mpf(0.25) + self.dg_fus_RT(t),
                              (mp.mpf(270), mp.mpf(278)), solver="anderson"))
        p = sle.certify({"T": T, "P": P, "x": [0.5, 0.5], "solids": [0]})
        self.assertLess(abs(p["tm_solid"][BZ]), 1e-10)          # saturation residual alone would pass
        self.assertEqual(p["certificate"], "no_cumple")
        self.assertFalse(p["liquid_stability"]["stable"])
        # the least-tpd trial liquid is the conjugate binodal liquid of the analytic model
        self.assertLess(abs(p["liquid_stability"]["w"][0] - (1 - self.binodal(self.A))), 1e-6)

    def test_metastable_saturated_liquid_not_certified(self):
        """x between binodal and spinodal (saturation root at 275 K, x = 0.1659) is rejected; a stable root
        far from the gap (260 K, single root) is certified."""
        sle = self.system()
        r = sle.solubility_roots(0, 275.0, P)[0]
        self.assertFalse(r["stable"])
        p = sle.certify({"T": 275.0, "P": P, "x": [r["x"], 1 - r["x"]], "solids": [0]})
        self.assertEqual(p["certificate"], "no_cumple")
        x = sle.solubility(0, 260.0, P)
        ref = self.roots(self.A, 260.0)
        self.assertEqual(len(ref), 1)
        self.assertLess(abs(x - ref[0]), 1e-12)
        self.assertEqual(sle.certify({"T": 260.0, "P": P, "x": [x, 1 - x], "solids": [0]})["certificate"],
                         "cumple")

    def test_ternary_stability_generic(self):
        """N = 3: inside the spinodal (analytic Hessian of g/RT indefinite) the liquid is unstable; with small
        interaction parameters g/RT is convex on the simplex and the liquid is stable."""
        A = np.array([[0, 3.0, 0.5], [3.0, 0, 0.5], [0.5, 0.5, 0]])
        sle = SolidLiquidSystem([BZ, "X", "Y"], Regular3(A), solids={BZ: sd.REGISTRY[BZ]})
        x = np.array([0.45, 0.45, 0.10])

        def hessian(x):
            # g/RT in (x1, x2), x3 = 1 - x1 - x2: d2/dxi dxj of sum x ln x + 1/2 x^T A x
            J = np.array([[1, 0], [0, 1], [-1, -1]], float)
            return J.T @ (np.diag(1 / x) + A) @ J
        self.assertLess(np.linalg.eigvalsh(hessian(x)).min(), 0)
        self.assertFalse(sle.liquid_stability(250.0, x)["stable"])
        small = SolidLiquidSystem([BZ, "X", "Y"], Regular3(0.4 * (A > 0)), solids={BZ: sd.REGISTRY[BZ]})
        for y in ([0.45, 0.45, 0.10], [0.1, 0.2, 0.7], [0.8, 0.1, 0.1]):
            st = small.liquid_stability(250.0, np.array(y))
            self.assertTrue(st["stable"])
            self.assertGreater(st["tpd_min"], -1e-12)


class CrystallizationSkips(unittest.TestCase):
    """F9-R12: only a liquidus below the solid's own T_min may be skipped."""
    sa = sd.SolidPure("A", "a", "I", 300.0, P, 9000.0, 0.0, 0.0, 150.0)
    sb = sd.SolidPure("B", "b", "I", 250.0, P, 9000.0, 0.0, 0.0, 150.0)
    sc = sd.SolidPure("C", "c", "I", 245.0, P, 30000.0, 0.0, 0.0, 150.0)

    @staticmethod
    def liquidus(s, x):
        return 1.0 / (1.0 / s.T_m - R * math.log(x) / s.dh_m)

    def unclipped_reference(self):
        sle = SolidLiquidSystem(["A", "B"], mz.LiquidoIdeal(2), solids={"A": self.sa, "B": self.sb})
        T, i = sle.crystallization_T(np.array([0.8, 0.2]), P)
        self.assertEqual(i, 0)
        self.assertLess(abs(T - self.liquidus(self.sa, 0.8)), 1e-9)

    def test_clipped_liquidus_is_rejected_not_skipped(self):
        self.unclipped_reference()
        x = np.array([0.65, 0.05, 0.30])
        self.assertGreater(self.liquidus(self.sa, 0.65), 240.0)              # A crystallizes first, at 268 K
        self.assertTrue(200.0 < self.liquidus(self.sc, 0.30) < 240.0)          # C's liquidus is inside the clip
        sle = SolidLiquidSystem(["A", "B", "C"], ClippedIdeal(3, (200.0, 240.0)),
                                solids={"A": self.sa, "B": self.sb, "C": self.sc})
        with self.assertRaises(mz.FueraDeAlcance) as cm:
            sle.crystallization_T(x, P)
        self.assertEqual(cm.exception.datos["solid"], "A")
        self.assertEqual(cm.exception.datos["cause"], "liquidus_above_window")
        self.assertIn("A", cm.exception.mensaje)
        # binary of the sweep: clip (200, 240), x = [0.8, 0.2]: located, names A
        sle2 = SolidLiquidSystem(["A", "B"], ClippedIdeal(2, (200.0, 240.0)), solids={"A": self.sa, "B": self.sb})
        with self.assertRaises(mz.FueraDeAlcance) as cm:
            sle2.crystallization_T(np.array([0.8, 0.2]), P)
        self.assertEqual(cm.exception.datos["solid"], "A")

    def test_lower_clip_is_rejected(self):
        """A liquidus between the record's T_min and the activity model's lower range end is not 'below
        T_min': it is rejected, naming the solid."""
        sle = SolidLiquidSystem(["A", "B"], ClippedIdeal(2, (200.0, 400.0)), solids={"A": self.sa, "B": self.sb})
        x = np.array([0.8, 0.2])
        self.assertTrue(150.0 < self.liquidus(self.sb, 0.2) < 200.0)
        with self.assertRaises(mz.FueraDeAlcance) as cm:
            sle.crystallization_T(x, P)
        self.assertEqual(cm.exception.datos["solid"], "B")
        self.assertEqual(cm.exception.datos["cause"], "liquidus_below_activity_range")
        self.below_own_T_min_is_skipped()                     # the one legitimate skip still applies

    def below_own_T_min_is_skipped(self):
        sb = sd.SolidPure("B", "b", "I", 250.0, P, 9000.0, 0.0, 0.0, 200.0)
        sle = SolidLiquidSystem(["A", "B"], mz.LiquidoIdeal(2), solids={"A": self.sa, "B": sb})
        T, i = sle.crystallization_T(np.array([0.8, 0.2]), P)
        self.assertEqual(i, 0)
        self.assertLess(abs(T - self.liquidus(self.sa, 0.8)), 1e-9)


class InputHygiene(unittest.TestCase):
    """F9-R14: located rejections instead of numbers or raw exceptions."""
    def setUp(self):
        self.sle = SolidLiquidSystem([BZ, CY], mz.LiquidoIdeal(2))

    def cause(self, fn, *a):
        with self.assertRaises(mz.FueraDeAlcance) as cm:
            fn(*a)
        return cm.exception.datos.get("cause")

    def test_solid_tm_rejections(self):
        tm = self.sle.solid_tm
        self.assertEqual(self.cause(tm, 0, 250.0, P, [0.6, 0.6]), "invalid_composition")
        self.assertEqual(self.cause(tm, 0, 250.0, P, [1.2, -0.2]), "invalid_composition")
        self.assertEqual(self.cause(tm, 1, 250.0, P, [1.2, -0.2]), "invalid_composition")
        self.assertEqual(self.cause(tm, 0, 0.0, P, [0.5, 0.5]), "invalid_temperature")
        self.assertEqual(self.cause(tm, 0, -5.0, P, [0.5, 0.5]), "invalid_temperature")
        self.assertEqual(self.cause(tm, 0, 400.0, P, [0.5, 0.5]), "outside_window")
        self.assertEqual(self.cause(tm, 0, 150.0, P, [0.5, 0.5]), "outside_window")
        s = sd.REGISTRY[BZ]
        T = 250.0
        self.assertAlmostEqual(tm(0, T, P, [0.5, 0.5]), -math.log(0.5) - s.dg_fus(T, P) / (R * T), delta=1e-14)

    def test_melting_T(self):
        neg = sd.SolidPure(BZ, "t", "I", 278.69, P, 9866.3, 0.0, -1e-5, 100.0)
        with self.assertRaises(mz.FueraDeAlcance) as cm:
            neg.melting_T(1e10)
        self.assertEqual(cm.exception.datos["cause"], "melting_T_undefined")
        self.assertEqual(self.cause(SolidLiquidSystem([BZ, CY], mz.LiquidoIdeal(2), solids={BZ: neg}).solid_tm,
                                    0, 250.0, 1e10, [0.5, 0.5]), "melting_T_undefined")
        for dv, Pp in ((-1e-5, 1e8), (2e-6, 5e7), (2e-6, 1e9)):
            s = sd.SolidPure(BZ, "t", "I", 278.69, P, 9866.3, 0.0, dv, 100.0)
            ref = s.T_m * (1 + dv * (Pp - P) / s.dh_m)
            self.assertLess(abs(s.melting_T(Pp) - ref), 1e-9)
        # root below the record's T_min
        lowroot = sd.SolidPure(BZ, "t", "I", 278.69, P, 9866.3, 0.0, -1e-5, 260.0)
        with self.assertRaises(mz.FueraDeAlcance):
            lowroot.melting_T(1e8)


class A1PressureAndIndex(unittest.TestCase):
    """A1 review SLE-1 and SLE-2 (5 November 2026). Both registered solids have dv = 0, so melting_T returned
    T_m before any pressure check and dg_fus = 0 * (P - P_m) turned a NaN P into NaN. Negative control: against
    the delivery before the repair, solid_tm returns NaN or a number for NaN and negative P, liquidus_T reports
    the false cause liquidus_below_solid_T_min, crystallization_T silently skips every solid, and an index
    outside the system raises IndexError."""
    BAD_P = (float("nan"), -1e5, 0.0, float("inf"), -float("inf"))

    def setUp(self):
        self.sle = SolidLiquidSystem([BZ, CY], mz.LiquidoIdeal(2))

    def cause(self, fn, *a):
        with self.assertRaises(mz.FueraDeAlcance) as cm:
            fn(*a)
        return cm.exception.datos.get("cause")

    def test_invalid_pressure_is_located_everywhere(self):
        s = self.sle
        for Pb in self.BAD_P:
            with self.subTest(P=Pb):
                self.assertEqual(self.cause(sd.REGISTRY[BZ].melting_T, Pb), "invalid_pressure")
                self.assertEqual(self.cause(s.solid_tm, 0, 250.0, Pb, [0.5, 0.5]), "invalid_pressure")
                self.assertEqual(self.cause(s.solubility, 0, 250.0, Pb), "invalid_pressure")
                self.assertEqual(self.cause(s.solubility_roots, 1, 250.0, Pb), "invalid_pressure")
                self.assertEqual(self.cause(s.liquidus_T, 0, [0.5, 0.5], Pb), "invalid_pressure")
                self.assertEqual(self.cause(s.crystallization_T, [0.5, 0.5], Pb), "invalid_pressure")
                self.assertEqual(self.cause(s.latent_heat, 0, 250.0, Pb, [0.5, 0.5]), "invalid_pressure")
                self.assertEqual(self.cause(s.eutectic, Pb), "invalid_pressure")
        # a dv != 0 record is rejected for the same cause, before Newton
        dv = sd.SolidPure(BZ, "t", "I", 278.69, P, 9866.3, 0.0, 2e-6, 100.0)
        self.assertEqual(self.cause(dv.melting_T, float("nan")), "invalid_pressure")
        # a valid P keeps the verified values (closed form with dcp = 0 for cyclohexane, ideal liquid)
        T = 250.0
        c = sd.REGISTRY[CY]
        self.assertAlmostEqual(s.solid_tm(1, T, P, [0.5, 0.5]),
                               -math.log(0.5) - c.dh_m * (1 - T / c.T_m) / (R * T), delta=1e-14)

    def test_crystallization_with_nan_pressure_is_not_skipped(self):
        with self.assertRaises(mz.FueraDeAlcance) as cm:
            self.sle.crystallization_T([0.5, 0.5], float("nan"))
        self.assertEqual(cm.exception.datos["cause"], "invalid_pressure")
        self.assertNotIn("T_min", cm.exception.mensaje)

    def test_solid_index_outside_the_system(self):
        for i in (2, 5, -1, 1.0, True):
            for call in (lambda: self.sle.solid_tm(i, 250.0, P, [0.5, 0.5]),
                         lambda: self.sle.liquidus_T(i, [0.5, 0.5], P),
                         lambda: self.sle.window(i, P),
                         lambda: self.sle.latent_heat(i, 250.0, P, [0.5, 0.5])):
                with self.subTest(i=i):
                    with self.assertRaises(mz.FaltaParametro) as cm:
                        call()
                    self.assertEqual(cm.exception.codigo, "SOLIDO_AUSENTE")
                    self.assertEqual(cm.exception.detalle["especies"], [BZ, CY])
        # a species of the system without a solid record keeps its own located message
        only_bz = SolidLiquidSystem([BZ, CY], mz.LiquidoIdeal(2), solids={BZ: sd.REGISTRY[BZ]})
        with self.assertRaises(mz.FaltaParametro) as cm:
            only_bz.solid_tm(1, 250.0, P, [0.5, 0.5])
        self.assertEqual((cm.exception.codigo, cm.exception.detalle["cas"]), ("SOLIDO_AUSENTE", CY))


    def test_certify_and_hbar_E_validate_indices(self):
        """A1 repairs review R2: certify accepted undeclared solids ([7] gave "cumple" for an unsaturated liquid)
        and hbar_E took -1 as species 1. Negative control: both fail before the repair."""
        point = {"T": 250.0, "P": P, "x": [0.5, 0.5]}
        for bad in ([7], [True], [-1], [1.0], [None], ["0"], [0, 2]):
            with self.subTest(solids=bad):
                with self.assertRaises(mz.FaltaParametro) as cm:
                    self.sle.certify({**point, "solids": bad})
                self.assertEqual(cm.exception.codigo, "SOLIDO_AUSENTE")
        for bad in (7, None, "0"):
            with self.subTest(solids=bad):
                self.assertEqual(self.cause(self.sle.certify, {**point, "solids": bad}), "invalid_species_index")
        self.assertEqual(self.sle.certify({**point, "solids": [0]})["certificate"], "no_cumple")
        for bad in (-1, True, None, 2, 1.0, "0"):
            with self.subTest(i=bad):
                self.assertEqual(self.cause(self.sle.hbar_E, bad, 250.0, [0.5, 0.5]), "invalid_species_index")
        self.assertEqual(self.sle.hbar_E(1, 250.0, [0.5, 0.5]), 0.0)     # ideal liquid: no excess enthalpy


if __name__ == "__main__":
    unittest.main(verbosity=2)
