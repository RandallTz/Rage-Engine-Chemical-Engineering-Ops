"""F8b (8 November 2026): cost of the default UV window search of the cubic EOS layer.

The thermodynamic closure runs a UV flash at every evaluation, and each probe is a certified TP flash (stability
analysis, split, certification: about 0.5 s). The default search was dominated by flash count, so the checks here
count TP flashes (`cubic_flash.flash_TP` calls) as the cost, which does not depend on machine load, and check that
the root is unchanged.

Changes under test (cubic_flash._search_T, _warm_lnP_root, g_at):
- window edges are bisected (N_WINDOW_BISECT per end, 2 flashes or more per step) only when no window brackets the
  root on the grid; before, always (400 of 602 flashes for PSRK CO2 + ethanol at 333 K);
- the inner ln P problem is solved on ln(V(P)/V) (nearly linear in ln P across a two-phase interval, same root) and
  starts from a bracket around the ln P of the nearest temperature already solved.
Independent reference: the `thermo` package (PR78MIX, Bell et al.) evaluates, at the UV root, the volumes of the two
published phases and the fugacity coefficients, so the specified volume and the phase equilibrium are verified outside
the kernel (this module's own TP flash only supplies the specification).
Negative control (8 November 2026, previous search on the same states, TP flashes): PR benzene + toluene at 500 K
232; the same at 420 K (one phase) 278; PR benzene + water at 380 K 839; PSRK CO2 + ethanol at 333 K 602 and at 363 K
641; PSRK methanol + toluene at 480 K 148. Each limit asserted here lies below the previous count.
Run: python -m pytest tests/test_cubic_uv_window_speed.py
"""
import math
from pathlib import Path
import sys
import unittest
import warnings

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.termodinamica import cubic_flash as cf
from core.termodinamica.cubic_eos import R, CubicOutOfScope, PengRobinsonMixture

warnings.filterwarnings("ignore")
BZ, TO, W = "71-43-2", "108-88-3", "7732-18-5"


class counting:
    """Count the TP flashes (and the failed ones) that cubic_flash makes."""

    def __enter__(self):
        self.n = self.failed = 0
        self.orig = cf.flash_TP

        def wrapped(*a, **k):
            self.n += 1
            try:
                return self.orig(*a, **k)
            except CubicOutOfScope:
                self.failed += 1
                raise
        cf.flash_TP = wrapped
        return self

    def __exit__(self, *exc):
        cf.flash_TP = self.orig


def totals(st):
    return tuple(sum(p["n"] * p[k] for p in st["phases"]) for k in ("h", "u", "v"))


class UVWindowSearch(unittest.TestCase):
    def setUp(self):
        self.eos = PengRobinsonMixture((BZ, TO))
        self.z = np.array([0.4, 0.6])
        self.T, self.P = 500.0, 1.5e6
        self.tp = cf.flash_TP(self.eos, self.T, self.P, self.z)
        _, self.U, self.V = totals(self.tp)

    def test_default_uv_root_equals_the_explicit_bracket_and_the_tp_state(self):
        with counting() as c:
            uv = cf.flash_UV(self.eos, self.U, self.V, self.z)
        explicit = cf.flash_UV(self.eos, self.U, self.V, self.z, T_bracket=(450.0, 560.0))
        self.assertLess(abs(uv["T"] - self.T), 1e-7)
        self.assertLess(abs(uv["P"] / self.P - 1), 1e-9)
        self.assertLess(abs(uv["T"] - explicit["T"]), 1e-7)
        self.assertLess(abs(uv["P"] / explicit["P"] - 1), 1e-9)
        self.assertEqual([p["kind"] for p in uv["phases"]], [p["kind"] for p in self.tp["phases"]])
        self.assertLess(c.n, 190, c.n)                  # previous search: 232

    def test_thermo_confirms_the_volume_and_the_phase_equilibrium_at_the_root(self):
        from thermo import PR78MIX
        uv = cf.flash_UV(self.eos, self.U, self.V, self.z)
        T, P = uv["T"], uv["P"]
        lnphi, vol = [], 0.0

        def th(x):
            return PR78MIX(Tcs=list(map(float, self.eos.Tc)), Pcs=list(map(float, self.eos.Pc)),
                           omegas=list(map(float, self.eos.omega)), zs=list(map(float, x)), T=T, P=P)
        for ph in uv["phases"]:
            t = th(ph["x"])
            if ph["kind"] == "vapor":
                v = t.V_g
                lp = np.log(t.phis_g)
            else:
                v = t.V_l
                lp = np.log(t.phis_l)
            self.assertLess(abs(v / ph["v"] - 1), 1e-6)
            vol += ph["n"] * v
            lnphi.append(np.log(np.asarray(ph["x"])) + lp)
        self.assertLess(abs(vol / self.V - 1), 1e-6)                      # the specified volume
        self.assertLess(float(np.max(np.abs(lnphi[0] - lnphi[1]))), 1e-6)  # equal fugacities of both phases

    def test_a_one_phase_state_still_closes(self):
        tp = cf.flash_TP(self.eos, 420.0, 1e6, self.z)
        self.assertEqual(len(tp["phases"]), 1)
        _, U, V = totals(tp)
        with counting() as c:
            uv = cf.flash_UV(self.eos, U, V, self.z)
        self.assertLess(abs(uv["T"] - 420.0), 1e-6)
        self.assertLess(abs(uv["P"] / 1e6 - 1), 1e-8)
        self.assertLess(c.n, 230, c.n)                  # previous search: 278


class LiquidLiquidRobustnessKept(unittest.TestCase):
    """Benzene + water 0.5/0.5 at 1 bar is a certified liquid-liquid split up to about 345 K, so the default UV
    search meets non-evaluable probes on part of its grid; the states above it must still close and a state on the
    liquid-liquid side must stay a located rejection."""

    def setUp(self):
        self.eos = PengRobinsonMixture((BZ, W))
        self.z = np.array([0.5, 0.5])

    def test_state_above_the_liquid_liquid_region_closes(self):
        tp = cf.flash_TP(self.eos, 380.0, 1e5, self.z)
        _, U, V = totals(tp)
        with counting() as c:
            uv = cf.flash_UV(self.eos, U, V, self.z)
        print(f"benzene + water UV: {c.n} TP flashes, {c.failed} non-evaluable")
        self.assertLess(abs(uv["T"] - 380.0), 1e-6)
        self.assertLess(abs(uv["P"] / 1e5 - 1), 1e-8)
        self.assertLess(c.n, 500, c.n)                  # previous search: 839

    def test_liquid_liquid_side_is_a_located_rejection(self):
        tp = cf.flash_TP(self.eos, 380.0, 1e5, self.z)
        _, U, V = totals(tp)
        with self.assertRaises(CubicOutOfScope) as cm:
            cf.flash_UV(self.eos, U - 60000.0, V, self.z)
        self.assertIn(cm.exception.datos["cause"], ("liquid_liquid_split", "third_phase", "outside_bracket"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
