"""Reference checks for core/reactions/chemical_equilibrium.py (F5 chemical equilibrium, 30 October 2026).

(a) Ammonia synthesis, ideal gas: log10 Kf of 1/2 N2 + 3/2 H2 = NH3 against NIST-JANAF table H-083 (500 K:
    -0.501, 700 K: -2.029) with JANAF formation data, and the extent against the closed-form condition
    K (P/P0)^2 = (2 xi)^2 (4 - 2 xi)^2 / ((1 - xi)(3 - 3 xi)^3) solved by bisection outside the module.
(b) Liquid UNIFAC (package `unifac-dortmund-public`): esterification EtOH + AcOH = EtOAc + H2O against the
    published equimolar conversion of about 2/3 (Berthelot and Pean de Saint-Gilles, 1862), with the liquid
    formation anchor; the package's pure-liquid potential against tabulated liquid formation data; and the
    package stability test flagging the butanol-water split a single-phase equilibrium cannot represent.
(c) Methanol synthesis + water-gas shift: extent and Gibbs minimisation (element constraints) agree.
(d) Rank-deficient set (third reaction = first + second): rank 2, dependent ln K consistent, all certified.
(e) Near the boundary: a nearly exhausted reactant (n ~ 1e-12) against a bisection in ln n, an uncertified
    extent solve raising, an absent inert rejected, and finite dmu/dn for a trace species.
Run: python tests/test_chemical_equilibrium.py
"""
import math
import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.reactions import chemical_equilibrium as ce

N2, H2, NH3 = "7727-37-9", "1333-74-0", "7664-41-7"
CO, CO2, H2O, MEOH = "630-08-0", "124-38-9", "7732-18-5", "67-56-1"
ETOH, BUOH = "64-17-5", "71-36-3"
ACOH, ETOAC = "64-19-7", "141-78-6"


class IdealGasReference(unittest.TestCase):
    def test_ammonia_K_against_janaf(self):
        # NH3 from JANAF; N2 and H2 (Hf = 0) with the NIST WebBook entropies, which are the JANAF values
        gas = ce.IdealGasPhase([N2, H2, NH3], source={NH3: "JANAF", N2: ("CRC", "WEBBOOK"), H2: ("CRC", "WEBBOOK")})
        for T, log10K in ((500.0, -0.501), (700.0, -2.029)):
            lnK = ce.equilibrium_constant(gas, [-0.5, -1.5, 1.0], T, ce.P0)["lnK"]
            self.assertLess(abs(lnK / math.log(10) - log10K), 1e-3, T)     # JANAF prints 3 decimals

    def test_ammonia_extent_against_closed_form(self):
        gas = ce.IdealGasPhase([N2, H2, NH3])
        A, _ = ce.element_matrix(gas.cas)
        T = 700.0
        lnK = ce.equilibrium_constant(gas, [-1, -3, 2], T, ce.P0)["lnK"]
        for P in (1e5, 5e6):
            f = lambda xi: (2 * math.log(2 * xi) + 2 * math.log(4 - 2 * xi) - math.log(1 - xi)
                            - 3 * math.log(3 - 3 * xi) - lnK - 2 * math.log(P / ce.P0))
            xi_ref = brentq(f, 1e-12, 1 - 1e-12, xtol=1e-15)
            out = ce.solve_extents(gas, [[-1, -3, 2]], [1.0, 3.0, 0.0], T, P, A)
            self.assertLess(abs(out["extents"][0] - xi_ref), 1e-11, P)
            self.assertTrue(out["certificate"]["certified"])


class LiquidPackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from core.mezclas import Sistema
        cls.sistema = Sistema("unifac-dortmund-public", [ETOH, BUOH, H2O])
        cls.liquid = ce.PackagePhase(cls.sistema, "liquido")

    def test_pure_liquid_potential_against_tabulated_liquid_formation(self):
        from chemicals import reaction as rx
        g = self.liquid.mu_standard(ce.T0, ce.P0)
        for c, v in zip(self.liquid.cas, g):
            self.assertLess(abs(v - (rx.Hfl(c) - ce.T0 * rx.S0l(c))), 1.5e3, c)   # J/mol; ideal gas + Psat route

    def test_single_liquid_equilibrium_and_stability_flag(self):
        A, _ = ce.element_matrix(self.liquid.cas)
        NU, n0 = [[-2, 1, 1]], [1.0, 0.0, 0.0]
        ext = ce.solve_extents(self.liquid, NU, n0, 320.0, 1e5, A)
        gib = ce.minimise_gibbs(self.liquid, NU, n0, 320.0, 1e5, A)
        self.assertTrue(ext["certificate"]["certified"])
        self.assertTrue(gib["certificate"]["certified"])
        self.assertLess(np.max(np.abs(np.subtract(ext["moles"], gib["moles"]))), 1e-10)
        # recomputed residual: gamma from the package's UNIFAC, not from the solver
        n = np.array(ext["moles"])
        x = n / n.sum()
        lng = self.sistema._lngamma(320.0, x, [0, 1, 2])
        lnK = ce.equilibrium_constant(self.liquid, NU[0], 320.0, 1e5)["lnK"]
        self.assertLess(abs(np.dot(NU[0], np.log(x) + lng) - lnK), 1e-9)
        stab = ext["certificate"]["phase_stability"]
        self.assertFalse(stab["stable"])                  # butanol-water split: a constrained stationary point
        self.assertEqual(stab["trial_phase"], "liquido")


class Esterification(unittest.TestCase):
    """EtOH + AcOH = EtOAc + H2O in the liquid, UNIFAC (Dortmund) activities, liquid formation anchor.

    Reference: Berthelot and Pean de Saint-Gilles (1862), equimolar feed reaches about 2/3 conversion
    (K_x ~ 4) near room temperature. Acetic acid dimerises in the vapour, so the package's ideal-gas + Psat
    pure-liquid route misplaces its g_L by about 4.9 kJ/mol; the gas anchor is shown to fail for that reason."""

    @classmethod
    def setUpClass(cls):
        # Acetic acid is a liquid-only species of core/catalogo.REGISTRO_SOLO_LIQUIDO (dec-f5-acetic-liquid-only):
        # the VLE packages, whose ideal vapour is wrong for a dimerising acid, reject it; a liquid-only system
        # admits it. Its pure data checks are recorded beside the registry entry.
        from core.mezclas import Sistema
        cls.cas = [ETOH, ACOH, ETOAC, H2O]
        cls.sistema = Sistema("unifac-dortmund-public", cls.cas, solo_liquido=True)
        cls.A, _ = ce.element_matrix(cls.cas)

    def test_liquid_anchor_K_from_tabulated_liquid_data(self):
        from chemicals import reaction as rx
        nu = np.array([-1, -1, 1, 1])
        L = ce.PackagePhase(self.sistema, "liquido", anchor="liquid")
        dH = nu @ [rx.Hfl(c) for c in self.cas]
        dS = nu @ [rx.S0l(c) for c in self.cas]
        lnK = ce.equilibrium_constant(L, nu, ce.T0, ce.P0)["lnK"]
        self.assertLess(abs(lnK + (dH - ce.T0 * dS) / (ce.R * ce.T0)), 1e-10)

    def test_equimolar_conversion_against_berthelot(self):
        L = ce.PackagePhase(self.sistema, "liquido", anchor="liquid")
        out = ce.solve_extents(L, [[-1, -1, 1, 1]], [1.0, 1.0, 0.0, 0.0], ce.T0, ce.P0, self.A)
        self.assertTrue(out["certificate"]["certified"])
        self.assertTrue(out["certificate"]["phase_stability"]["stable"])
        self.assertLess(abs(out["extents"][0] - 2.0 / 3.0), 0.02)
        self.assertLess(L.anchor_gap[ACOH], -4e3)        # J/mol: the dimerisation error of the Psat route
        with self.assertRaises(ce.ChemicalEquilibriumError) as x:       # the biased gas route (xi 0.868) is refused
            ce.PackagePhase(self.sistema, "liquido", anchor="gas")
        self.assertEqual(x.exception.code, "LIQUID_ANCHOR_REQUIRED")


class MultiReaction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gas = ce.IdealGasPhase([CO, CO2, H2, H2O, MEOH])
        cls.A, _ = ce.element_matrix(cls.gas.cas)
        cls.n0 = [1.0, 0.3, 2.5, 0.05, 0.0]

    def test_extent_and_gibbs_minimisation_agree(self):
        NU = [[-1, 0, -2, 0, 1], [1, -1, -1, 1, 0]]
        st = ce.analyse_stoichiometry(NU, self.A)
        self.assertTrue(st["conserves_elements"] and st["spans_element_null_space"])
        ext = ce.solve_extents(self.gas, NU, self.n0, 500.0, 5e6, self.A)
        gib = ce.minimise_gibbs(self.gas, NU, self.n0, 500.0, 5e6, self.A, constraints="elements")
        for out in (ext, gib):
            self.assertTrue(out["certificate"]["certified"])
            self.assertLess(out["certificate"]["element_residual"], 1e-14)
        self.assertLess(np.max(np.abs(np.subtract(ext["moles"], gib["moles"]))), 1e-10)

    def test_rank_deficient_set(self):
        NU = [[-1, 0, -2, 0, 1], [1, -1, -1, 1, 0], [0, -1, -3, 1, 1]]
        st = ce.analyse_stoichiometry(NU, self.A)
        self.assertEqual((st["rank"], st["independent"]), (2, [0, 1]))
        np.testing.assert_allclose(st["dependent"][2], [1.0, 1.0], atol=1e-12)
        lnK = [ce.equilibrium_constant(self.gas, nu, 500.0, 5e6)["lnK"] for nu in NU]
        self.assertLess(abs(lnK[2] - lnK[0] - lnK[1]), 1e-10)
        out = ce.solve_extents(self.gas, NU, self.n0, 500.0, 5e6, self.A)
        self.assertEqual(len(out["certificate"]["reaction_residual"]), 3)
        self.assertTrue(out["certificate"]["certified"])

    def test_unbalanced_reaction_rejected(self):
        with self.assertRaises(ce.ChemicalEquilibriumError) as e:
            ce.solve_extents(self.gas, [[-1, 0, -1, 0, 1]], self.n0, 500.0, 5e6, self.A)
        self.assertEqual(e.exception.code, "ELEMENTS_NOT_CONSERVED")


class NearBoundary(unittest.TestCase):
    """Review findings F5-EQ-1 and F5-EQ-2 (30 October 2026)."""

    def test_nearly_exhausted_reactant(self):
        # H2 + 1/2 O2 = H2O, 600 K, 1 bar, stoichiometric feed: n_H2 from ln K by bisection in ln n_H2
        O2 = "7782-44-7"
        gas = ce.IdealGasPhase([H2, O2, H2O])
        A, _ = ce.element_matrix(gas.cas)
        lnK = ce.equilibrium_constant(gas, [-1, -0.5, 1], 600.0, ce.P0)["lnK"]
        f = lambda le: (math.log(2 - math.exp(le)) - le - 0.5 * (le - math.log(2))
                        + 0.5 * math.log(2 + math.exp(le) / 2) - lnK)
        ref = math.exp(brentq(f, -200, math.log(1.999), xtol=1e-14))
        ext = ce.solve_extents(gas, [[-1, -0.5, 1]], [2.0, 1.0, 0.0], 600.0, ce.P0, A)
        gib = ce.minimise_gibbs(gas, [[-1, -0.5, 1]], [2.0, 1.0, 0.0], 600.0, ce.P0, A, constraints="elements")
        for out in (ext, gib):
            self.assertTrue(out["certificate"]["certified"])
            self.assertLess(abs(out["moles"][0] / ref - 1), 1e-3)   # n_H2O = 2 fixes n_H2 to ~1e-16 absolute
        self.assertLess(abs(ext["moles"][0] - gib["moles"][0]), 1e-15)

    def test_uncertified_extent_solve_raises(self):
        gas = ce.IdealGasPhase([N2, H2, NH3])
        A, _ = ce.element_matrix(gas.cas)
        saved = ce.TOLERANCE
        ce.TOLERANCE = 0.0                               # nothing can pass: the solver must not return silently
        try:
            with self.assertRaises(ce.ChemicalEquilibriumError) as e:
                ce.solve_extents(gas, [[-1, -3, 2]], [1.0, 3.0, 0.0], 700.0, 1e5, A)
            self.assertEqual(e.exception.code, "NOT_CERTIFIED")
        finally:
            ce.TOLERANCE = saved

    def test_absent_inert_species_rejected(self):
        gas = ce.IdealGasPhase([CO, H2, MEOH, CO2])
        A, _ = ce.element_matrix(gas.cas)
        for fn in (ce.solve_extents, ce.minimise_gibbs):
            with self.assertRaises(ce.ChemicalEquilibriumError) as e:
                fn(gas, [[-1, -2, 1, 0]], [1.0, 2.0, 0.0, 0.0], 500.0, 5e6, A)
            self.assertEqual(e.exception.code, "ABSENT_INERT_SPECIES")

    def test_derivatives_finite_for_trace_species(self):
        gas = ce.IdealGasPhase([N2, H2, NH3])
        n = np.array([1.0, 3.0, 1e-8])
        st = ce.evaluate_reactions(gas, [[-1, -3, 2]], T=700.0, P=1e5, n=n, phase_id="vapor",
                                   standard_state="ideal_gas_P0")
        self.assertTrue(st["valid"])
        exact = ce.R * 700.0 * (np.diag(1 / n) - 1 / n.sum())     # ideal gas: RT (delta_ik / n_i - 1 / N)
        np.testing.assert_allclose(st["dmu_dn"], exact, rtol=1e-6, atol=1e-6 * ce.R * 700.0)


class Facade(unittest.TestCase):
    def test_state_certificate_and_reaction_enthalpy(self):
        gas = ce.IdealGasPhase([N2, H2, NH3])
        A, _ = ce.element_matrix(gas.cas)
        eq = ce.solve_extents(gas, [[-1, -3, 2]], [1.0, 3.0, 0.0], 700.0, 5e6, A)
        st = ce.evaluate_reactions(gas, [[-1, -3, 2]], T=700.0, P=5e6, n=eq["moles"], phase_id="vapor",
                                   standard_state="ideal_gas_P0")
        cert = ce.certify_reactions(st, n0=[1.0, 3.0, 0.0], A=A)
        self.assertTrue(cert["certified"] and cert["conservation_checked"])
        # ideal gas: sum nu h_i = 2 Hf(NH3) + package sensible terms; at T0 exactly the formation value
        s0 = ce.evaluate_reactions(gas, [[-1, -3, 2]], T=ce.T0, P=ce.P0, n=[1.0, 3.0, 0.5], phase_id="vapor",
                                   standard_state="ideal_gas_P0")
        self.assertLess(abs(np.dot([-1, -3, 2], s0["h_partial"]) - 2 * gas.Hf[2]), 1e-3)   # J/mol, FD error

    def test_no_clipping_and_phase_checks(self):
        gas = ce.IdealGasPhase([N2, H2, NH3])
        st = ce.evaluate_reactions(gas, [[-1, -3, 2]], T=700.0, P=1e5, n=[1.0, 3.0, 0.0], phase_id="vapor",
                                   standard_state="ideal_gas_P0")
        self.assertFalse(st["valid"])
        self.assertFalse(ce.certify_reactions(st)["certified"])
        with self.assertRaises(ce.ChemicalEquilibriumError):
            ce.evaluate_reactions(gas, [[-1, -3, 2]], T=700.0, P=1e5, n=[1, 3, 1], phase_id="liquido",
                                  standard_state="pure_liquid_TP")


if __name__ == "__main__":
    unittest.main(verbosity=2)
