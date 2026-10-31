"""Reference checks for core/termodinamica/derived_bridge.py (Demo 0.1: FD-1 to FD-4 and F5-C2, 30 October 2026).

Every value is compared with the common layer it wraps, called directly, or with finite differences taken
outside the module:
(a) caloric: pure-species h = -T^2 d(g/T)/dT of the package's g_ig0 and g_L; the partial molar h_i against
    -T^2 d(mu_i/T)/dT of `Sistema.mu`; Euler sum against `Sistema.fase(...).h`; dH/dT against differences
    of H; the formation anchor against `formation_reference`; Delta_r H at 298.15 K (ideal gas) against
    sum nu Hf; the single-phase T reconstruction round trip.
(b) closure: ethanol/water two-phase PH and UV against `Sistema.equilibrio_PH` / `equilibrio_UV`; a
    single-phase subcooled liquid; seeded and unseeded closures agree; an anchored closure has the same T.
(c) indicators: complementarity, event sign across the bubble point (located by bisection on the event
    function), two-liquid water/1-butanol.
(d) draws: material and enthalpy consistency, mass basis, an absent phase, an ambiguous liquid.
Sensitivities: dT/dH of a single liquid against 1/(dH/dT) of the caloric inventory.
Run: python tests/test_derived_thermo_bridge.py
"""
import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import mezclas as mz
from core.reactions import chemical_equilibrium as ce
from core.termodinamica import derived_bridge as b

PKG = "unifac-dortmund-public"
ETOH, H2O, BUOH, ACOH, ETOAC = "64-17-5", "7732-18-5", "71-36-3", "64-19-7", "141-78-6"
EW = [ETOH, H2O]
N_EW = np.array([0.3, 0.7])
P_ATM = 101325.0
H_TWO_PHASE = -2.0e4          # J: ethanol/water at 1 atm, between bubble and dew point
H_LIQUID = -4.4e4             # J: subcooled liquid (about 300 K)


def fd(f, x, h):
    return (-f(x + 2 * h) + 8 * f(x + h) - 8 * f(x - h) + f(x - 2 * h)) / (12 * h)


class Caloric(unittest.TestCase):
    def test_pure_species_consistent_with_potentials(self):
        s = mz.Sistema(PKG, EW)
        T, P = 330.0, P_ATM
        c = b.species_caloric(PKG, EW, T, P)
        g_ig = lambda t: np.array([e.g_ig0(t) for e in s.esp]) / t
        g_L = lambda t: np.array([e.g_L(t, P) for e in s.esp]) / t
        np.testing.assert_allclose(c["h_gas"], -T * T * fd(g_ig, T, 1e-2), rtol=0, atol=1e-5)
        np.testing.assert_allclose(c["h_liquid"], -T * T * fd(g_L, T, 1e-2), rtol=0, atol=1e-5)
        h_L = lambda t: np.array([e.h_L(t, P) for e in s.esp])
        np.testing.assert_allclose(c["dh_liquid_dT"], fd(h_L, T, 1e-3), rtol=1e-8)
        np.testing.assert_allclose(c["du_gas_dT"], np.array(c["dh_gas_dT"]) - mz.R, rtol=1e-14)
        np.testing.assert_allclose(c["u_liquid"], np.array(c["h_liquid"]) - P * s.vL, rtol=1e-14)

    def test_phase_inventory_against_package(self):
        s = mz.Sistema(PKG, EW)
        T, P, n = 330.0, P_ATM, N_EW
        for phase, tipo in (("liquid", "liquido"), ("vapor", "vapor")):
            c = b.phase_caloric(PKG, EW, T, P, n, phase=phase)
            f = s.fase("x", tipo, T, P, n, [0, 1])
            self.assertAlmostEqual(c["H"], n.sum() * f.h, delta=1e-8 * abs(c["H"]))
            self.assertAlmostEqual(c["V"], n.sum() * f.v, delta=1e-14)
            mu_T = lambda t: s.mu(tipo, t, P, n / n.sum(), [0, 1]) / t
            np.testing.assert_allclose(c["h_partial"], -T * T * fd(mu_T, T, 1e-2), rtol=0, atol=1e-4)
            H = lambda t: n.sum() * s.fase("x", tipo, t, P, n, [0, 1]).h
            self.assertAlmostEqual(c["dH_dT"], fd(H, T, 1e-3), delta=1e-6 * abs(c["dH_dT"]))
            self.assertAlmostEqual(c["U"], c["H"] - P * c["V"], delta=1e-9)

    def test_absent_species_has_finite_partial_enthalpy(self):
        c = b.phase_caloric(PKG, EW, 330.0, P_ATM, [0.0, 1.0])
        self.assertTrue(np.all(np.isfinite(c["h_partial"])))
        self.assertAlmostEqual(c["H"], c["h_partial"][1], delta=1e-9)

    def test_anchor_adds_formation_enthalpy(self):
        n = N_EW
        base = b.phase_caloric(PKG, EW, 330.0, P_ATM, n)
        anchored = b.phase_caloric(PKG, EW, 330.0, P_ATM, n, anchor="gas")
        Hf = np.array([ce.formation_reference(c)[0] for c in EW])
        self.assertAlmostEqual(anchored["H"] - base["H"], float(n @ Hf), delta=1e-6)
        self.assertAlmostEqual(anchored["dH_dT"], base["dH_dT"], delta=1e-9 * abs(base["dH_dT"]))

    def test_reaction_enthalpy_at_reference(self):
        # Ideal gas at 298.15 K with the gas anchor: h_i = Hf_i, so Delta_r H = sum nu Hf (Hess).
        r = b.reaction_enthalpy("unifac-original", [ETOH, H2O, ETOAC], [[-2, 1, 0]], 298.15, mz.P0,
                                phase="vapor", check_elements=False)
        Hf = np.array([ce.formation_reference(c)[0] for c in [ETOH, H2O, ETOAC]])
        self.assertAlmostEqual(r["dH"][0], float(np.array([-2, 1, 0]) @ Hf), delta=1e-6)
        with self.assertRaises(b.DerivedThermoError) as ctx:
            b.reaction_enthalpy("unifac-original", [ETOH, H2O, ETOAC], [[-2, 1, 0]], 298.15, mz.P0, phase="vapor")
        self.assertEqual(ctx.exception.code, "ELEMENTS_NOT_CONSERVED")
        # Liquid esterification (liquid-only system, liquid anchor): partial molar Delta_r H equals nu . h_partial.
        ester = [ETOH, ACOH, ETOAC, H2O]
        n = [1.0, 1.0, 0.1, 0.1]
        r = b.reaction_enthalpy(PKG, ester, [[-1, -1, 1, 1]], 340.0, P_ATM, n=n, anchor="liquid", liquid_only=True)
        c = b.phase_caloric(PKG, ester, 340.0, P_ATM, n, anchor="liquid", liquid_only=True)
        self.assertAlmostEqual(r["dH"][0], float(np.array([-1, -1, 1, 1]) @ c["h_partial"]), delta=1e-6)
        self.assertLess(abs(r["dH"][0]), 2.0e4)          # mildly exothermic or thermoneutral, as tabulated

    def test_phase_temperature_round_trip(self):
        n = N_EW
        c = b.phase_caloric(PKG, EW, 320.0, P_ATM, n, anchor="gas")
        r = b.phase_temperature(PKG, EW, n, P_ATM, c["U"], quantity="U", anchor="gas")
        self.assertAlmostEqual(r["T"], 320.0, delta=1e-9)
        self.assertTrue(r["single_phase_stable"])
        hot = b.phase_caloric(PKG, EW, 380.0, P_ATM, n)
        r = b.phase_temperature(PKG, EW, n, P_ATM, hot["H"], quantity="H")
        self.assertAlmostEqual(r["T"], 380.0, delta=1e-9)
        self.assertFalse(r["single_phase_stable"])        # superheated liquid: the vapour trial lowers G


class Closure(unittest.TestCase):
    def test_two_phase_PH_and_UV_against_package(self):
        s = mz.Sistema(PKG, EW)
        e = s.equilibrio_PH(P_ATM, H_TWO_PHASE, N_EW)
        st = b.close_state(PKG, EW, N_EW, "PH", P_ATM, H_TWO_PHASE)
        self.assertEqual(st.phase_set, ("liquido-1", "vapor-1"))
        self.assertAlmostEqual(st.T, e.T, delta=1e-9)
        amounts = {f.id: f.n for f in e.fases}
        for p in st.phases:
            self.assertAlmostEqual(p.amount, amounts[p.id], delta=1e-10)
        self.assertTrue(st.certificate["certified"])
        liq = next(p for p in st.phases if p.kind == "liquid")
        self.assertAlmostEqual(st.liquid_molar_volume, liq.v, delta=1e-18)
        self.assertAlmostEqual(st.liquid_volume, liq.amount * liq.v, delta=1e-18)
        np.testing.assert_allclose(sum(p.amount * np.array(p.x) for p in st.phases), N_EW, atol=1e-12)
        uv = b.close_state(PKG, EW, N_EW, "UV", st.U, st.V)
        e_uv = s.equilibrio_UV(st.U, st.V, N_EW)
        self.assertAlmostEqual(uv.T, e_uv.T, delta=1e-8)
        self.assertAlmostEqual(uv.T, st.T, delta=1e-6)
        self.assertAlmostEqual(uv.P, P_ATM, delta=1e-4)

    def test_single_phase_liquid(self):
        s = mz.Sistema(PKG, EW)
        st = b.close_state(PKG, EW, N_EW, "PH", P_ATM, H_LIQUID)
        e = s.equilibrio_PH(P_ATM, H_LIQUID, N_EW)
        self.assertEqual(st.phase_set, ("liquido-1",))
        self.assertAlmostEqual(st.T, e.T, delta=1e-9)
        self.assertAlmostEqual(st.liquid_amount, 1.0, delta=1e-12)
        c = b.phase_caloric(PKG, EW, st.T, P_ATM, N_EW)
        self.assertAlmostEqual(c["H"], H_LIQUID, delta=1e-6)

    def test_seeded_and_anchored_agree(self):
        st = b.close_state(PKG, EW, N_EW, "UV", *self._uv())
        target = (st.U + 50.0, st.V)
        cold = b.close_state(PKG, EW, N_EW, "UV", *target)
        warm = b.close_state(PKG, EW, N_EW, "UV", *target, seed=st)
        self.assertAlmostEqual(cold.T, warm.T, delta=1e-8)
        self.assertAlmostEqual(cold.P, warm.P, delta=1e-8 * cold.P)
        Hf = np.array([ce.formation_reference(c)[0] for c in EW])
        anchored = b.close_state(PKG, EW, N_EW, "UV", target[0] + float(N_EW @ Hf), target[1], anchor="gas")
        self.assertAlmostEqual(anchored.T, cold.T, delta=1e-8)
        self.assertAlmostEqual(anchored.U - cold.U, float(N_EW @ Hf), delta=1e-6)

    def _uv(self):
        st = b.close_state(PKG, EW, N_EW, "PH", P_ATM, H_TWO_PHASE)
        return st.U, st.V

    def test_sensitivity_single_liquid(self):
        sens = b.closure_sensitivities(PKG, EW, N_EW, "PH", P_ATM, H_LIQUID)
        self.assertFalse(sens["phase_set_changed"])
        J = np.array(sens["jacobian"])
        c = b.phase_caloric(PKG, EW, sens["state"].T, P_ATM, N_EW)
        col_H = sens["inputs"].index("H")
        self.assertAlmostEqual(J[0, col_H], 1.0 / c["dH_dT"], delta=1e-6 / c["dH_dT"])
        # dT/dn_i at fixed H: -h_i / (dH/dT)
        for i in range(2):
            self.assertAlmostEqual(J[0, i], -c["h_partial"][i] / c["dH_dT"], delta=1e-5 * abs(c["h_partial"][i] / c["dH_dT"]))

    def test_errors(self):
        for call, code in ((lambda: b.close_state("nrtl-chemsep", EW, N_EW, "PH", P_ATM, 0.0), "UNSUPPORTED_PACKAGE"),
                           (lambda: b.close_state(PKG, EW, [-1.0, 1.0], "PH", P_ATM, 0.0), "INVALID_INPUT"),
                           (lambda: b.close_state(PKG, EW, N_EW, "TP", 300.0, P_ATM), "INVALID_INPUT"),
                           (lambda: b.close_state(PKG, EW, N_EW, "PH", P_ATM, 1e9), "OUT_OF_DOMAIN"),
                           (lambda: b.close_state(PKG, [ETOH, ACOH], [1.0, 1.0], "PH", P_ATM, 0.0), "PARAMETER_MISSING"),
                           (lambda: b.close_state(PKG, [ETOH, ACOH], [1.0, 1.0], "PH", P_ATM, 0.0, liquid_only=True),
                            "LIQUID_ONLY_SYSTEM")):
            with self.assertRaises(b.DerivedThermoError) as ctx:
                call()
            self.assertEqual(ctx.exception.code, code)


class Indicators(unittest.TestCase):
    def test_complementarity_and_signs(self):
        for H, present in ((H_TWO_PHASE, {"vapor-1", "liquido-1"}), (H_LIQUID, {"liquido-1"})):
            st = b.close_state(PKG, EW, N_EW, "PH", P_ATM, H)
            ind = b.phase_indicators(st)
            self.assertLess(ind["complementarity"], 1e-8)
            for row in ind["phases"]:
                self.assertEqual(row["present"], row["phase"] in present)
                if row["event"] is not None:
                    self.assertEqual(row["event"] > 0, row["present"])

    def test_bubble_point_event(self):
        # The vapour event function changes sign once between the liquid and two-phase states; its root is the
        # bubble point: there the liquid is the whole inventory and the TP flash reports a vapour trace at most.
        def g(H):
            st = b.close_state(PKG, EW, N_EW, "PH", P_ATM, H)
            return next(r["event"] for r in b.phase_indicators(st)["phases"] if r["phase"] == "vapor-1")
        self.assertLess(g(H_LIQUID), 0)
        self.assertGreater(g(H_TWO_PHASE), 0)
        Hb = brentq(g, H_LIQUID, H_TWO_PHASE, xtol=1e-3)
        st = b.close_state(PKG, EW, N_EW, "PH", P_ATM, Hb)
        s = mz.Sistema(PKG, EW)
        # Bubble point of the package: the liquid of feed composition has the vapour trial at tm = 0.
        mu = s.mu("liquido", st.T, P_ATM, N_EW, [0, 1])
        tm_vapor = s.prueba_estabilidad(st.T, P_ATM, mu, [0, 1])[0][2]
        self.assertLess(abs(tm_vapor), 1e-6)

    def test_two_liquids(self):
        sp = [H2O, BUOH]
        n = np.array([0.7, 0.3])
        e = mz.Sistema(PKG, sp).equilibrio_TP(300.0, P_ATM, n)
        st = b.close_state(PKG, sp, n, "PH", P_ATM, e.H)
        self.assertEqual(st.phase_set, ("liquido-1", "liquido-2"))
        ind = b.phase_indicators(st)
        rows = {r["phase"]: r for r in ind["phases"]}
        self.assertLess(rows["vapor-1"]["event"], 0)
        self.assertGreater(rows["liquido-2"]["event"], 0)
        with self.assertRaises(b.DerivedThermoError) as ctx:
            b.phase_draw(st, "liquid", 1.0)
        self.assertEqual(ctx.exception.code, "PHASE_AMBIGUOUS")
        heavy = b.phase_draw(st, "liquid", 1.0, selection="higher_density")
        self.assertEqual(heavy["phases"], ["liquido-1"])
        both = b.phase_draw(st, "liquid", 1.0, selection="combined")
        np.testing.assert_allclose(both["x"], n / n.sum(), atol=1e-12)


class LiquidLiquidEvents(unittest.TestCase):
    """Regressions of the independent review (30 October 2026, `.tmp/claude-bridge-review/review_lle_events.py`):
    water/1-butanol at 300 K, 1 atm, binodals near x_BuOH 0.029 and 0.643 (UNIFAC Dortmund)."""
    SP = [H2O, BUOH]

    def _march(self, zs, track=True):
        s = mz.Sistema(PKG, self.SP)
        out, prev = [], None
        for z in zs:
            n = np.array([1 - z, z])
            st = b.close_state(PKG, self.SP, n, "PH", P_ATM, s.equilibrio_TP(300.0, P_ATM, n).H)
            ind = b.phase_indicators(st, previous=prev if track else None)
            prev = ind
            out.append((st, ind, {r["phase"]: r["event"] for r in ind["phases"]}))
        return out

    def test_D1_second_liquid_appearance_is_a_sign_change(self):
        # Before the repair liquido-2 had event None up to 0.0288: the package leaves that minimum unrefined.
        (st0, _, before), (st1, _, after) = self._march([0.0288, 0.0295])
        self.assertEqual(st0.phase_set, ("liquido-1",))
        self.assertEqual(st1.phase_set, ("liquido-1", "liquido-2"))
        self.assertIsNotNone(before["liquido-2"])
        self.assertLess(before["liquido-2"], 0)
        self.assertGreater(after["liquido-2"], 0)
        # The margin is a refined local tangent-plane minimum near the conjugate liquid (binodal x_BuOH 0.643),
        # checked outside the module: tm at the trial equals the reported value and is lower than its neighbours.
        row = next(r for r in self._march([0.0288])[0][1]["phases"] if r["phase"] == "liquido-2")
        self.assertAlmostEqual(row["incipient_x"][1], 0.643, delta=5e-3)
        s = mz.Sistema(PKG, self.SP)
        mu = s.mu("liquido", st0.T, P_ATM, np.array([1 - 0.0288, 0.0288]), [0, 1])
        tm = lambda w: s._tm_liquido(st0.T, P_ATM, [1 - w, w], mu, [0, 1])
        w = row["incipient_x"][1]
        self.assertAlmostEqual(tm(w), row["tm"], delta=1e-12)
        self.assertLess(row["tm"], min(tm(w - 1e-3), tm(w + 1e-3)))

    def test_D2_dense_liquid_disappearance_keeps_its_label(self):
        # Before the repair the remaining liquid was renamed liquido-1 and no event crossed zero.
        (st0, ind0, before), (st1, ind1, after) = self._march([0.642, 0.645])
        self.assertEqual(st1.phase_set, ("liquido-1",))
        self.assertGreater(before["liquido-1"], 0)
        self.assertLess(after["liquido-1"], 0)                 # the water-rich liquid disappeared
        self.assertAlmostEqual(after["liquido-2"], 1.0, delta=1e-12)
        self.assertEqual(ind1["labels"], {"vapor-1": None, "liquido-1": None, "liquido-2": "liquido-1"})
        # A stream bound to the butanol-rich liquid keeps drawing it; the vanished liquid draws nothing.
        rich = b.phase_draw(st1, "liquido-2", 1.0, indicators=ind1)
        self.assertTrue(rich["present"])
        self.assertAlmostEqual(rich["x"][1], 0.645, delta=1e-12)
        self.assertFalse(b.phase_draw(st1, "liquido-1", 1.0, indicators=ind1)["present"])
        # Untracked, the closure's own density labels remain (documented behaviour).
        untracked = self._march([0.645], track=False)[0][2]
        self.assertAlmostEqual(untracked["liquido-1"], 1.0, delta=1e-12)

    def test_events_change_sign_once_across_each_binodal(self):
        for zs, label in (((0.025, 0.028, 0.0288, 0.0295, 0.031), "liquido-2"),
                          ((0.62, 0.64, 0.642, 0.645, 0.65), "liquido-1")):
            values = [ev[label] for _, _, ev in self._march(zs)]
            self.assertTrue(all(v is not None for v in values), values)
            signs = [v > 0 for v in values]
            self.assertEqual(sum(a != c for a, c in zip(signs, signs[1:])), 1, values)


class Draws(unittest.TestCase):
    def test_draw_consistency(self):
        st = b.close_state(PKG, EW, N_EW, "PH", P_ATM, H_TWO_PHASE)
        vap = next(p for p in st.phases if p.kind == "vapor")
        d = b.phase_draw(st, "vapor", 0.2)
        np.testing.assert_allclose(d["component_molar_flows"], 0.2 * np.array(vap.x), rtol=1e-14)
        self.assertAlmostEqual(d["enthalpy_flow"], 0.2 * vap.h, delta=1e-9)
        m = b.phase_draw(st, "vapor-1", d["mass_flow"], basis="mass")
        np.testing.assert_allclose(m["component_molar_flows"], d["component_molar_flows"], rtol=1e-12)
        self.assertAlmostEqual(sum(m["component_mass_flows"]), d["mass_flow"], delta=1e-15)

    def test_absent_phase_draws_nothing(self):
        st = b.close_state(PKG, EW, N_EW, "PH", P_ATM, H_LIQUID)
        d = b.phase_draw(st, "vapor", 0.5)
        self.assertFalse(d["present"])
        self.assertEqual(d["component_molar_flows"], [0.0, 0.0])
        self.assertEqual(d["enthalpy_flow"], 0.0)
        with self.assertRaises(b.DerivedThermoError):
            b.phase_draw(st, "vapor", -1.0)


if __name__ == "__main__":
    unittest.main()
