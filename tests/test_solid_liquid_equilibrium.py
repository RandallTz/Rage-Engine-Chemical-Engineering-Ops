"""f8b: solid-liquid equilibrium (core/termodinamica/solid_liquid.py, solid_data.py).

Each reference is reached by another path than the module's root finders:
1. Ideal solubility: with an ideal liquid the condition ln x_i = -dg_fus/RT has a closed form. With dcp = 0 it is
   the van 't Hoff law; with dcp != 0 the test integrates Gibbs-Helmholtz numerically from the melting point,
   ln x(T) = int_{T_m}^{T} dh_fus(T') / (R T'^2) dT' (scipy quad), instead of the module's integrated dg_fus.
   The ideal eutectic is solved by plain bisection on the two closed forms.
2. Published data: benzene + cyclohexane, Tsuji, Sue, Hiaki and Itoh, Fluid Phase Equilib. 257 (2007) 183-189
   (NIST ThermoML 10.1016/j.fluid.2007.01.029, records 8 and 9, 101 kPa): both liquidus branches and the
   simple eutectic x_benzene = 0.2709, T = 232.11 K. Activity from UNIFAC (Dortmund and original); fusion data
   from the NIST WebBook (solid_data.py). Ideal solution as a contrast.
3. Latent energy: Gibbs-Helmholtz and Kirchhoff on the solid record (finite differences of dg_fus); the
   latent heat of crystallization L_i = dh_fus + hbar_i^E against hbar_i^E from the liquid's excess enthalpy
   h^E = g^E - T dg^E/dT (complex step, core/mezclas.dgE_dT) and its composition derivative; and the
   liquidus consistency (d ln a_i/dx_i)_T dx_i/dT = L_i / RT^2 from independently solved liquidus points.
Run: python tests/test_solid_liquid_equilibrium.py (a few seconds).
"""
import math
from pathlib import Path
import sys
import unittest

import numpy as np
from scipy.integrate import quad

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import mezclas as mz
from core.termodinamica import solid_data as sd
from core.termodinamica.solid_liquid import SolidLiquidSystem

R = mz.R
P = 101325.0
BZ, CY, TOL = "71-43-2", "110-82-7", "108-88-3"

# Tsuji et al. 2007, verbatim (x = mole fraction of benzene, T in K)
BENZENE_BRANCH = [(0.349, 238.42), (0.4346, 244.53), (0.5192, 250.02), (0.6118, 255.36), (0.7228, 261.88),
                  (0.7296, 262.19), (0.8223, 267.27), (0.9042, 272.5)]
CYCLOHEXANE_BRANCH = [(0.1088, 259.44), (0.1607, 249.06), (0.2121, 240.53)]
EUTECTIC = (0.2709, 232.11)


def bisect(f, a, b, n=200):
    fa = f(a)
    for _ in range(n):
        m = 0.5 * (a + b)
        fm = f(m)
        if fa * fm <= 0:
            b = m
        else:
            a, fa = m, fm
    return 0.5 * (a + b)


class IdealSolubility(unittest.TestCase):
    def test_van_t_hoff_closed_form(self):
        s0 = sd.SolidPure("71-43-2", "test", "I", 278.69, P, 9866.3, 0.0, 0.0, 150.0)
        sle = SolidLiquidSystem([BZ, TOL], mz.LiquidoIdeal(2), solids={BZ: s0})
        worst = 0.0
        for T in np.linspace(180.0, 278.0, 15):
            x = sle.solubility(0, T, P)
            ref = math.exp(-s0.dh_m / R * (1 / T - 1 / s0.T_m))
            worst = max(worst, abs(x - ref) / ref)
        self.assertLess(worst, 1e-12)

    def test_gibbs_helmholtz_quadrature_with_dcp(self):
        s0 = sd.REGISTRY[BZ]                                  # dcp = 13 J/(mol K)
        sle = SolidLiquidSystem([BZ, TOL], mz.LiquidoIdeal(2), solids={BZ: s0})
        worst = 0.0
        for T in np.linspace(205.0, 278.0, 12):
            lnx = quad(lambda t: (s0.dh_m + s0.dcp * (t - s0.T_m)) / (R * t * t), s0.T_m, T,
                       epsabs=1e-13, epsrel=1e-13, limit=200)[0]
            worst = max(worst, abs(math.log(sle.solubility(0, T, P)) - lnx))
        self.assertLess(worst, 1e-11)

    def test_liquidus_and_common_package(self):
        """from_sistema on the catalog's ideal package: liquidus temperature against the inverse closed form."""
        s0 = sd.SolidPure("71-43-2", "test", "I", 278.69, P, 9866.3, 0.0, 0.0, 150.0)
        sle = SolidLiquidSystem.from_sistema(mz.Sistema("mezcla-ideal", [BZ, TOL]), solids={BZ: s0})
        for xb in (0.2, 0.5, 0.9, 1.0):
            ref = 1.0 / (1.0 / s0.T_m - R * math.log(xb) / s0.dh_m)
            self.assertAlmostEqual(sle.liquidus_T(0, [xb, 1 - xb], P), ref, delta=1e-9)

    def test_ideal_eutectic_by_bisection(self):
        sa = sd.SolidPure(BZ, "a", "I", 278.69, P, 9866.3, 0.0, 0.0, 150.0)
        sb = sd.SolidPure(CY, "b", "I", 279.82, P, 2676.9, 0.0, 0.0, 150.0)
        sle = SolidLiquidSystem([BZ, CY], mz.LiquidoIdeal(2), solids={BZ: sa, CY: sb})
        xa = lambda T: math.exp(-sa.dh_m / R * (1 / T - 1 / sa.T_m))
        xb = lambda T: math.exp(-sb.dh_m / R * (1 / T - 1 / sb.T_m))
        Te = bisect(lambda T: xa(T) + xb(T) - 1, 150.0, 278.69)
        e = sle.eutectic(P)
        self.assertEqual(e["certificate"], "cumple")
        self.assertLess(abs(e["T"] - Te), 1e-9)
        self.assertLess(abs(e["x"][0] - xa(Te)), 1e-12)


class BenzeneCyclohexaneData(unittest.TestCase):
    def check(self, variant, tol_bz, tol_cy, tol_Te, tol_xe):
        sle = SolidLiquidSystem.from_unifac([BZ, CY], variant)
        dev_bz = [sle.liquidus_T(0, [x, 1 - x], P) - T for x, T in BENZENE_BRANCH]
        dev_cy = [sle.liquidus_T(1, [x, 1 - x], P) - T for x, T in CYCLOHEXANE_BRANCH]
        e = sle.eutectic(P)
        print(f"\n  UNIFAC {variant}: benzene branch max |dT| {max(map(abs, dev_bz)):.2f} K, cyclohexane branch "
              f"{max(map(abs, dev_cy)):.2f} K; eutectic {e['T']:.2f} K, x_bz {e['x'][0]:.4f} "
              f"(data {EUTECTIC[1]} K, {EUTECTIC[0]})")
        self.assertEqual(e["certificate"], "cumple")
        self.assertLess(max(map(abs, dev_bz)), tol_bz)
        self.assertLess(max(map(abs, dev_cy)), tol_cy)
        self.assertLess(abs(e["T"] - EUTECTIC[1]), tol_Te)
        self.assertLess(abs(e["x"][0] - EUTECTIC[0]), tol_xe)
        return dev_cy

    def test_dortmund(self):
        self.check("dortmund", 1.5, 4.0, 2.0, 0.03)

    def test_original_beats_ideal(self):
        dev_cy = self.check("original", 6.0, 6.0, 9.0, 0.02)
        ideal = SolidLiquidSystem([BZ, CY], mz.LiquidoIdeal(2))
        dev_id = [ideal.liquidus_T(1, [x, 1 - x], P) - T for x, T in CYCLOHEXANE_BRANCH]
        print(f"  ideal solution, cyclohexane branch max |dT| {max(map(abs, dev_id)):.2f} K")
        self.assertGreater(max(map(abs, dev_id)), max(map(abs, dev_cy)) + 2.0)

    def test_curve_certified_and_domain(self):
        sle = SolidLiquidSystem.from_unifac([BZ, CY], "dortmund")
        c = sle.liquidus_curve(P, 12)
        for b in c["branches"]:
            self.assertEqual(b["points"][0]["T"], sd.REGISTRY[b["cas"]].T_m)
            for p in b["points"]:
                self.assertEqual(p["certificate"], "cumple", p)
        # below the cyclohexane I -> II transition the record does not apply
        with self.assertRaises(mz.FueraDeAlcance):
            sle.solubility(1, 180.0, P)
        # a perturbed point is rejected by a fresh certificate
        e = dict(c["eutectic"])
        e["x"] = e["x"] + np.array([1e-4, -1e-4])
        self.assertEqual(sle.certify(e)["certificate"], "no_cumple")
        # x_bz = 0.6 at 250 K lies below the benzene liquidus (about 255 K): benzene is supersaturated
        p = sle.certify({"T": 250.0, "P": P, "x": np.array([0.6, 0.4]), "solids": []})
        self.assertLess(p["tm_solid"][BZ], 0.0)
        self.assertEqual(p["certificate"], "no_cumple")

    def test_ternary_crystallization_temperature(self):
        """N species: the first solid on cooling has tm = 0 and every other registered solid tm >= 0."""
        sle = SolidLiquidSystem.from_unifac([BZ, CY, TOL], "dortmund")
        for x in ([0.6, 0.2, 0.2], [0.1, 0.6, 0.3], [0.3, 0.3, 0.4]):
            T, i = sle.crystallization_T(np.array(x), P)
            self.assertLess(abs(sle.solid_tm(i, T, P, x)), 1e-10)
            for j in sle.solids:
                if j != i:
                    self.assertGreater(sle.solid_tm(j, T, P, x), 0.0)


class LatentEnergy(unittest.TestCase):
    def test_gibbs_helmholtz_kirchhoff(self):
        for s in sd.REGISTRY.values():
            self.assertEqual(s.dg_fus(s.T_m, s.P_m), 0.0)
            for T in np.linspace(s.T_min + 1, s.T_m, 6):
                h = 1e-3
                d = ((s.dg_fus(T + h, P) / (T + h)) - (s.dg_fus(T - h, P) / (T - h))) / (2 * h)
                self.assertLess(abs(-T * T * d - s.dh_fus(T)) / s.dh_m, 1e-7)
                ds = -(s.dg_fus(T + h, P) - s.dg_fus(T - h, P)) / (2 * h)
                self.assertLess(abs(ds - s.ds_fus(T)) / s.ds_fus(s.T_m), 1e-7)
                dcp = (s.dh_fus(T + h) - s.dh_fus(T - h)) / (2 * h)
                self.assertLess(abs(dcp - s.dcp), 1e-6)

    def test_solid_from_package_liquid(self):
        """At the melting point the package's pure liquid and the solid record give h_L - h_S = dh_m and equal
        g (melting condition); g_S = h_S - T s_S."""
        e = mz.Sistema("mezcla-ideal", [BZ, TOL]).esp[0]
        s = sd.REGISTRY[BZ]
        T = s.T_m
        sol = s.pure_properties(T, P, e.g_L(T, P), e.h_L(T, P), e.s_L(T, P))
        self.assertAlmostEqual(e.h_L(T, P) - sol["h"], s.dh_m, delta=1e-9)
        self.assertAlmostEqual(sol["g"], e.g_L(T, P), delta=1e-9)
        self.assertLess(abs(sol["g"] - (sol["h"] - T * sol["s"])), 1e-7)

    def test_crystallization_heat_and_liquidus_slope(self):
        sle = SolidLiquidSystem.from_unifac([BZ, CY], "dortmund")
        liq = sle.liquid

        def hE(T, x1):
            x = np.array([x1, 1 - x1])
            return R * T * float(np.real(liq.gE_RT(T, x))) - T * mz.dgE_dT(liq, T, x)

        worst_hbar, worst_slope = 0.0, 0.0
        for i, T in ((0, 255.0), (0, 270.0), (1, 250.0), (1, 240.0)):
            xi = sle.solubility(i, T, P)
            x1 = xi if i == 0 else 1 - xi                   # mole fraction of species 0
            d = 1e-5
            dhE = (hE(T, x1 + d) - hE(T, x1 - d)) / (2 * d)
            hbar = hE(T, x1) + (1 - x1) * dhE if i == 0 else hE(T, x1) - x1 * dhE
            L = sle.latent_heat(i, T, P, sle._x(i, xi))
            ref = sd.REGISTRY[sle.cas[i]].dh_fus(T) + hbar
            worst_hbar = max(worst_hbar, abs(L - ref) / ref)
            # liquidus consistency: (d ln a_i / dx_i)_T * dx_i/dT = L_i / RT^2
            dT = 1e-3
            dxdT = (sle.solubility(i, T + dT, P) - sle.solubility(i, T - dT, P)) / (2 * dT)
            lna = lambda z: math.log(z) + sle.lngamma(T, sle._x(i, z))[i]
            dlna = (lna(xi + d) - lna(xi - d)) / (2 * d)
            worst_slope = max(worst_slope, abs(dlna * dxdT * R * T * T - L) / L)
        print(f"\n  latent heat vs h^E route {worst_hbar:.1e}; liquidus slope consistency {worst_slope:.1e}")
        self.assertLess(worst_hbar, 1e-6)
        self.assertLess(worst_slope, 1e-5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
