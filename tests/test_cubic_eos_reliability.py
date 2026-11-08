"""A1 review repairs PR-1..PR-4 (5 November 2026) for the Peng-Robinson mixture package
(core/termodinamica/cubic_flash.py, cubic_critical.py, capa.py).

Independent references, each reached by another path than the code under test:
- Phase identity: the `thermo` package (PR78MIX, Bell et al.) evaluated at the module's compositions; its own
  Venkatarathnam-Oellrich parameter on its own volume roots (PIP_l, PIP_g).
- Critical points: an mpmath (30 digits) Reid-Beegle solver written here, on the molar Helmholtz function of
  Peng-Robinson with van der Waals one-fluid mixing (k_ij = 0), with the published constants
  Omega_a = 0.45723553, Omega_b = 0.07779607 (Peng and Robinson 1976) and the Robinson-Peng (1978) m(omega);
  conditions W = a_vv a_xx - a_vx^2 = 0 and a_vv W_x - a_vx W_v = 0 (Reid and Beegle, AIChE J. 23 (1977) 726),
  derivatives by mpmath's own differentiation. Only the catalog's (T_c, P_c, omega) are shared with the module.
Negative control: each test fails against the delivery before the repair (HEAD 8c07ee5): the liquid-liquid
split is published as vapour + liquid, negative-pressure roots are returned, there is no `kind`, an empty scan
returns [], a flipping eigenvector sign creates false critical points, a liquid-like trial stands for the
vapour candidate, and PH/UV outside the bracket raise scipy's ValueError.
Run: python -m pytest tests/test_cubic_eos_reliability.py
"""
import math
from pathlib import Path
import sys
import unittest
from unittest import mock
import warnings

import mpmath as mp
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.termodinamica import capa
from core.termodinamica import cubic_critical as cc
from core.termodinamica import cubic_flash as cf
from core.termodinamica.cubic_eos import R, CubicOutOfScope, PengRobinsonMixture

warnings.filterwarnings("ignore")
BZ, TO, W, EA, ME = "71-43-2", "108-88-3", "7732-18-5", "141-78-6", "67-56-1"


def thermo_eos(eos, T, P, x):
    from thermo import PR78MIX
    return PR78MIX(Tcs=list(map(float, eos.Tc)), Pcs=list(map(float, eos.Pc)),
                   omegas=list(map(float, eos.omega)), zs=list(map(float, x)), T=T, P=P)


def thermo_pip(eos, T, P, x, Z):
    """thermo's PIP on its own root closest to Z (and the relative distance to that root)."""
    t = thermo_eos(eos, T, P, x)
    roots = [(getattr(t, "Z_l", None), getattr(t, "PIP_l", None)), (getattr(t, "Z_g", None), getattr(t, "PIP_g", None))]
    roots = [(z, p) for z, p in roots if z is not None]
    z, p = min(roots, key=lambda r: abs(r[0] - Z))
    return float(p), abs(z / Z - 1)


class ReidBeegle:
    """mpmath binary critical point, independent of cubic_critical (see the module docstring)."""
    OA, OB = "0.45723552892138218938", "0.07779607390388845597"   # converted at the working precision

    def __init__(self, eos):
        self.Tc = [mp.mpf(float(v)) for v in eos.Tc]
        self.Pc = [mp.mpf(float(v)) for v in eos.Pc]
        self.m = []
        for w in map(float, eos.omega):
            self.m.append(mp.mpf(0.379642 + 1.48503 * w - 0.164423 * w ** 2 + 0.016666 * w ** 3) if w > 0.491
                          else mp.mpf(0.37464 + 1.54226 * w - 0.26992 * w ** 2))
        self.R = mp.mpf(R)

    def a(self, T, v, x):
        R, s2 = self.R, mp.sqrt(2)
        xs = [x, 1 - x]
        OA, OB = mp.mpf(self.OA), mp.mpf(self.OB)
        ai = [OA * R ** 2 * self.Tc[i] ** 2 / self.Pc[i] * (1 + self.m[i] * (1 - mp.sqrt(T / self.Tc[i]))) ** 2
              for i in range(2)]
        bi = [OB * R * self.Tc[i] / self.Pc[i] for i in range(2)]
        am = sum(xs[i] * xs[j] * mp.sqrt(ai[i] * ai[j]) for i in range(2) for j in range(2))
        bm = xs[0] * bi[0] + xs[1] * bi[1]
        Fr = -mp.log(1 - bm / v) - am / (R * T * bm * 2 * s2) * mp.log((v + (1 + s2) * bm) / (v + (1 - s2) * bm))
        return Fr + sum(xs[i] * mp.log(xs[i] / v) for i in range(2))

    def pressure(self, T, v, x):
        return -self.R * T * mp.diff(lambda vv: self.a(T, vv, x), v)

    def solve(self, x1, T0, v0):
        with mp.workdps(30):                       # local precision; the global mpmath context is not changed
            return self._solve(mp.mpf(x1), T0, v0)

    def _solve(self, x1, T0, v0):

        def eqs(T, v):
            d = lambda nv, nx: mp.diff(lambda vv, xx: self.a(T, vv, xx), (v, x1), (nv, nx))
            avv, axx, avx = d(2, 0), d(0, 2), d(1, 1)
            Wv = d(3, 0) * axx + avv * d(1, 2) - 2 * avx * d(2, 1)
            Wx = d(2, 1) * axx + avv * d(0, 3) - 2 * avx * d(1, 2)
            return [avv * axx - avx ** 2, avv * Wx - avx * Wv]
        T, v = mp.findroot(eqs, (mp.mpf(T0), mp.mpf(v0)), tol=mp.mpf(10) ** -20)
        return float(T), float(v), float(self.pressure(T, v, x1))


class PR1LiquidLiquidSplit(unittest.TestCase):
    def test_benzene_water_320K_is_rejected_not_published_as_vapour(self):
        eos = PengRobinsonMixture((BZ, W))
        with self.assertRaises(CubicOutOfScope) as cm:
            cf.flash_TP(eos, 320.0, 1e5, np.array([0.5, 0.5]))
        d = cm.exception.datos
        self.assertEqual(d["cause"], "liquid_liquid_split")
        # independent: thermo's own PIP on its own roots at the split compositions, both liquid-like
        for x, Z, pip in zip(d["compositions"], d["Z"], d["PIP"]):
            p_ref, dz = thermo_pip(eos, 320.0, 1e5, x, Z)
            self.assertLess(dz, 1e-9)
            self.assertGreater(p_ref, 1.0)
            self.assertLess(abs(pip / p_ref - 1), 1e-5)
        self.assertGreater(d["compositions"][0][0], 0.9)       # benzene-rich liquid, Z = 0.0032
        self.assertLess(d["Z"][0], 0.01)

    def test_layer_reports_the_located_cause(self):
        modelo = {
            "componentes": [{"id": "b", "identidadQuimica": {"cas": BZ}}, {"id": "w", "identidadQuimica": {"cas": W}}],
            "termodinamica": {"paquetes": [{"id": "p", "modelo": {"id": capa.CUBICO}}]},
            "volumenes": [{"id": "v", "componenteIds": ["b", "w"],
                           "termodinamica": {"tipo": "equilibrio", "paqueteId": "p"}}]}
        with self.assertRaises(capa.NoSoportado) as cm:
            capa.cierre(modelo, "v", {"b": 0.5, "w": 0.5}, ("TP", 320.0, 1e5))
        self.assertEqual(cm.exception.datos["cause"], "liquid_liquid_split")
        self.assertEqual(cm.exception.datos["volumenId"], "v")

    def test_vapour_liquid_split_still_published_with_physical_labels(self):
        eos = PengRobinsonMixture((BZ, W))
        st = cf.flash_TP(eos, 350.0, 1e5, np.array([0.5, 0.5]))
        self.assertEqual([p["kind"] for p in st["phases"]], ["vapor", "liquido"])
        pv, _ = thermo_pip(eos, 350.0, 1e5, st["phases"][0]["x"], st["phases"][0]["Z"])
        pl, _ = thermo_pip(eos, 350.0, 1e5, st["phases"][1]["x"], st["phases"][1]["Z"])
        self.assertLess(pv, 1.0)
        self.assertGreater(pl, 1.0)


class PR2CriticalPoints(unittest.TestCase):
    def test_benzene_water_drops_the_negative_pressure_root(self):
        eos = PengRobinsonMixture((BZ, W))
        cps = cc.critical_points(eos, np.array([0.25, 0.75]))
        self.assertEqual(len(cps), 1)
        c = cps[0]
        self.assertGreater(c["P"], 0.0)
        self.assertEqual(c["kind"], "gas_liquid")
        rb = ReidBeegle(eos)
        T, v, P = rb.solve(0.25, c["T"] * 1.002, c["V"] * 1.01)
        self.assertLess(abs(T - c["T"]), 1e-6)
        self.assertLess(abs(P / c["P"] - 1), 1e-8)
        self.assertEqual([r["reason"] for r in cps.rejected], ["non_positive_pressure"])
        r = cps.rejected[0]
        # independent: the dropped root is a genuine critical root of the EOS, at negative pressure
        T, v, P = rb.solve(0.25, r["T"] * 1.002, r["V"] * 1.01)
        self.assertLess(abs(T - r["T"]), 1e-6)
        self.assertLess(P, 0.0)
        self.assertLess(abs(P / r["P"] - 1), 1e-8)
        print(f"benzene + water 0.25: kept ({c['T']:.6f} K, {c['P'] / 1e6:.6f} MPa, {c['kind']}); "
              f"dropped ({r['T']:.6f} K, {r['P'] / 1e6:.6f} MPa)")

    def test_ethyl_acetate_water_two_roots_classified(self):
        eos = PengRobinsonMixture((EA, W))
        cps = cc.critical_points(eos, np.array([0.25, 0.75]))
        self.assertEqual([c["kind"] for c in cps], ["liquid_liquid", "gas_liquid"])
        rb = ReidBeegle(eos)
        for c in cps:
            T, v, P = rb.solve(0.25, c["T"] * 1.002, c["V"] * 1.01)
            self.assertLess(abs(T - c["T"]), 1e-6)
            self.assertLess(abs(P / c["P"] - 1), 1e-8)
            self.assertGreater(c["P"], 0.0)
        self.assertLess(cps[0]["kappa"], cc.KAPPA_LL * cc.kappa_c())
        self.assertGreater(cps[1]["kappa"], cc.KAPPA_GL * cc.kappa_c())
        print("ethyl acetate + water 0.25:", [(round(c["T"], 4), round(c["P"] / 1e6, 4), c["kind"]) for c in cps])

    def test_empty_scan_is_a_located_result(self):
        eos = PengRobinsonMixture((EA, W))
        with self.assertRaises(CubicOutOfScope) as cm:
            cc.critical_points(eos, np.array([0.15, 0.85]))
        d = cm.exception.datos
        self.assertEqual(d["cause"], "no_critical_point_in_window")
        self.assertEqual(d["window"]["kappa_range"], (1.6, 12.0))


class PR3NullVectorSign(unittest.TestCase):
    def test_eigenvector_sign_flips_do_not_create_critical_points(self):
        eos = PengRobinsonMixture((BZ, TO))
        z = np.array([0.5, 0.5])
        ref = cc.critical_points(eos, z)
        real = np.linalg.eigh
        calls = [0]

        def flipping(a, *args, **kw):
            w, U = real(a, *args, **kw)
            calls[0] += 1
            return w, (-U if calls[0] % 2 else U)
        with mock.patch("numpy.linalg.eigh", flipping):
            got = cc.critical_points(eos, z)
        self.assertEqual(len(ref), 1)
        self.assertEqual(len(got), 1)
        self.assertLess(abs(got[0]["T"] - ref[0]["T"]), 1e-9)
        self.assertLess(abs(got[0]["P"] / ref[0]["P"] - 1), 1e-10)

    def test_orientation_is_deterministic(self):
        u = np.array([0.3, -0.9])
        self.assertTrue(np.array_equal(cc._orient(u), -u))
        self.assertTrue(np.array_equal(cc._orient(-u), -u))
        self.assertTrue(np.array_equal(cc._orient(u, ref=np.array([1.0, 0.0])), u))


class PR4CandidatesAndBrackets(unittest.TestCase):
    MODEL = staticmethod(lambda a, b: {
        "componentes": [{"id": "a", "identidadQuimica": {"cas": a}}, {"id": "b", "identidadQuimica": {"cas": b}}],
        "termodinamica": {"paquetes": [{"id": "p", "modelo": {"id": capa.CUBICO}}]},
        "volumenes": [{"id": "v", "componenteIds": ["a", "b"],
                       "termodinamica": {"tipo": "equilibrio", "paqueteId": "p"}}]})

    def test_liquid_like_trial_never_stands_for_the_vapour(self):
        # water with 2e-6 benzene at 320 K, 1 bar: one liquid; its only tangent-plane minimum is a benzene-rich
        # LIQUID (thermo PIP > 1), so the vapour candidate has no trial of its kind
        eos = PengRobinsonMixture((BZ, W))
        z = np.array([2e-6, 1 - 2e-6])
        st = cf.flash_TP(eos, 320.0, 1e5, z)
        self.assertEqual(len(st["trials"]), 1)
        w = st["trials"][0][0]
        p_ref, _ = thermo_pip(eos, 320.0, 1e5, w, eos.phase(320.0, 1e5, w)["Z"])
        self.assertGreater(p_ref, 1.0)
        out = capa.cierre(self.MODEL(BZ, W), "v", {"a": z[0], "b": z[1]}, ("TP", 320.0, 1e5))
        self.assertEqual(out["presentes"], ["liquido-1"])
        vap = next(f for f in out["fases"] if f["id"] == "vapor-1")
        self.assertIsNone(vap["tm"])
        self.assertIsNone(vap["composicionIncipiente"])

    def test_vapour_candidate_gets_a_vapour_like_trial(self):
        eos = PengRobinsonMixture((BZ, TO))
        out = capa.cierre(self.MODEL(BZ, TO), "v", {"a": 0.5, "b": 0.5}, ("TP", 500.0, 1.65e6))
        vap = next(f for f in out["fases"] if f["id"] == "vapor-1")
        self.assertGreater(vap["tm"], 0.0)
        w = np.array([vap["composicionIncipiente"]["a"], vap["composicionIncipiente"]["b"]])
        p_ref, _ = thermo_pip(eos, 500.0, 1.65e6, w, eos.phase(500.0, 1.65e6, w)["Z"])
        self.assertLess(p_ref, 1.0)

    def test_ph_uv_outside_bracket_are_located(self):
        eos = PengRobinsonMixture((BZ, TO))
        z = np.array([0.5, 0.5])
        with self.assertRaises(CubicOutOfScope) as cm:
            cf.flash_PH(eos, 1e5, 1e9, z)
        self.assertEqual(cm.exception.datos["cause"], "outside_bracket")
        with self.assertRaises(CubicOutOfScope) as cm:
            cf.flash_UV(eos, 1e9, 1.0, z)
        self.assertEqual(cm.exception.datos["cause"], "outside_bracket")
        with self.assertRaises(capa.NoSoportado) as cm:
            capa.cierre(self.MODEL(BZ, TO), "v", {"a": 0.5, "b": 0.5}, ("PH", 1e5, 1e9))
        self.assertEqual(cm.exception.datos["cause"], "outside_bracket")


class R1NearCriticalVapourLiquid(unittest.TestCase):
    """A1 repairs review R1 (6 November 2026): 0.5 K below the gas-liquid critical point of methanol + water
    0.3/0.7, the vapour's PIP has passed through 1 (thermo confirms 1.19 at 15.31 MPa), but the light phase has
    kappa = v/b = 3.95, the critical density, not a liquid density. The split is a genuine vapour + liquid and
    must stay published. Negative control: the first PR-1 repair (PIP only) raised liquid_liquid_split."""

    def test_split_below_the_critical_point_stays_vapour_liquid(self):
        eos = PengRobinsonMixture((ME, W))
        z = np.array([0.3, 0.7])
        rb = ReidBeegle(eos)
        Tc, vc, Pc = rb.solve(0.3, 581.5 * 1.002, 3.95 * float(z @ eos.b) * 1.01)
        self.assertGreater(Tc, 581.0)                     # the state is below its gas-liquid critical point
        self.assertLess(Tc - 581.0, 1.0)
        light_pips = []
        for P in (15.31e6, 15.32e6, 15.33e6, 15.35e6):
            st = cf.flash_TP(eos, 581.0, P, z)
            self.assertEqual([p["kind"] for p in st["phases"]], ["vapor", "liquido"])
            vap = st["phases"][0]
            pip, dz = thermo_pip(eos, 581.0, P, vap["x"], vap["Z"])
            self.assertLess(dz, 1e-9)
            light_pips.append(pip)
            t = thermo_eos(eos, 581.0, P, vap["x"])
            self.assertGreater(vap["v"] / float(t.b), cc.KAPPA_LL * cc.kappa_c())   # thermo's own b_mix
        self.assertGreater(max(light_pips), 1.0)          # PIP alone would have called it liquid
        print(f"methanol + water 0.3 at 581.0 K: critical point {Tc:.4f} K, {Pc / 1e6:.4f} MPa; "
              f"light-phase PIP {min(light_pips):.3f}-{max(light_pips):.3f}")

    def test_benzene_water_stays_liquid_liquid_with_dense_light_phase(self):
        eos = PengRobinsonMixture((BZ, W))
        with self.assertRaises(CubicOutOfScope) as cm:
            cf.flash_TP(eos, 320.0, 1e5, np.array([0.5, 0.5]))
        self.assertEqual(cm.exception.datos["cause"], "liquid_liquid_split")
        self.assertLess(max(cm.exception.datos["kappa"]), cc.KAPPA_LL * cc.kappa_c())


class R3DefaultBracketUV(unittest.TestCase):
    """A1 repairs review R3: the layer calls flash_UV with its default brackets. At 150 K the inner ln P problem
    has no root, so every ordinary benzene + toluene state failed. Negative control: the delivery before this
    repair raises outside_bracket ("ln P at T = 150 K"), and HEAD a raw ValueError."""
    MODEL = staticmethod(PR4CandidatesAndBrackets.MODEL)

    def test_layer_uv_recovers_tp_states(self):
        eos = PengRobinsonMixture((BZ, TO))
        modelo = self.MODEL(BZ, TO)
        n = {"a": 0.5, "b": 0.5}
        for T, P, present in ((370.0, 1e5, ["vapor-1", "liquido-1"]), (300.0, 1e5, ["liquido-1"])):
            tp = capa.cierre(modelo, "v", n, ("TP", T, P))
            self.assertEqual(sorted(tp["presentes"]), sorted(present))
            uv = capa.cierre(modelo, "v", n, ("UV", tp["U"], tp["V"]))
            self.assertLess(abs(uv["T"] - T), 1e-6)
            self.assertLess(abs(uv["P"] / P - 1), 1e-8)
            self.assertEqual(sorted(uv["presentes"]), sorted(present))


class LiquidLiquidBracketEnds(unittest.TestCase):
    """F8b (7 November 2026): the default PH window treats a bracket end whose state is a certified liquid-liquid
    split as a non-evaluable side, not a failure. Benzene + water 0.5/0.5 at 1 bar is a liquid-liquid split
    from the bracket's low end (150 K) up to its heteroazeotrope near 345 K. Negative control: before the repair
    the default PH raised liquid_liquid_split at 150 K for every state. Where the specified enthalpy lies on the
    liquid-liquid side the true state is that split, and it stays a located rejection."""

    def setUp(self):
        self.eos = PengRobinsonMixture((BZ, W))
        self.z = np.array([0.5, 0.5])

    def test_ph_recovers_the_tp_state_above_the_liquid_liquid_region(self):
        for T in (350.0, 380.0):
            tp = cf.flash_TP(self.eos, T, 1e5, self.z)
            H = sum(p["n"] * p["h"] for p in tp["phases"])
            ph = cf.flash_PH(self.eos, 1e5, H, self.z)
            self.assertLess(abs(ph["T"] - T), 1e-9)
            self.assertEqual([p["kind"] for p in ph["phases"]], [p["kind"] for p in tp["phases"]])
            for a, b in zip(ph["phases"], tp["phases"]):
                self.assertLess(float(np.max(np.abs(a["x"] - b["x"]))), 1e-9)

    def test_enthalpy_on_the_liquid_liquid_side_is_rejected(self):
        tp = cf.flash_TP(self.eos, 350.0, 1e5, self.z)
        H = sum(p["n"] * p["h"] for p in tp["phases"]) - 40000.0
        with self.assertRaises(CubicOutOfScope) as cm:
            cf.flash_PH(self.eos, 1e5, H, self.z)
        d = cm.exception.datos
        self.assertEqual(d["cause"], "liquid_liquid_split")
        self.assertTrue(340.0 < d["T_edge"] < 346.0)
        # Just below the edge the TP flash finds a vapour + liquid split that a liquid destabilizes (third_phase);
        # further down it certifies the liquid-liquid split. Neither is published.
        with self.assertRaises(CubicOutOfScope) as cm:
            cf.flash_TP(self.eos, d["T_edge"] - 1e-3, 1e5, self.z)
        self.assertIn(cm.exception.datos["cause"], ("third_phase", "liquid_liquid_split"))
        with self.assertRaises(CubicOutOfScope) as cm:
            cf.flash_TP(self.eos, 340.0, 1e5, self.z)
        self.assertEqual(cm.exception.datos["cause"], "liquid_liquid_split")


if __name__ == "__main__":
    unittest.main(verbosity=2)
