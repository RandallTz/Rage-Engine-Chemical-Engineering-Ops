"""Independent checks of reaction_jacobian_bounds for package phases (F5 liquid bounds, Claude, 5 November 2026).

The reference never reuses the production code (core.unifac, core.mezclas_datos, core.termodinamica):
- UNIFAC is rebuilt in mpmath at 50 digits from thermo's own tables (DOUFSG/DOUFIP2016 for Dortmund, UFSG/UFIP for
  the original, DDBST assignments), in MOLE-FRACTION form as published (Fredenslund et al. 1975; Weidlich and
  Gmehling 1987), not in the module's amount form;
- pure liquids are rebuilt from chemicals' Wagner (Poling/McGarry) Psat rows, the Poling cp/R polynomial and, for
  acetic acid, Perry's DIPPR-100 cp_L, with h and s by QUADRATURE and dlnPsat/dT by mp.diff;
- d ln gamma/dn_k and dC/dn_k by complex-step differentiation of the reference (step 1e-30 at 50 digits);
  dg/dT and dg/dP by 40-digit-plus central mp.diff;
- sampled float values come from the provider (evaluate_reactions on PackagePhase).
Cases: interval-AD rules; interval UNIFAC against the reference at points (value and gradient); esterification
ethanol + acetic acid = ethyl acetate + water (acetic acid liquid only, anchor='liquid') with Dortmund, original
and ideal liquid; point and box enclosures; dense provider sampling; Gibbs-Duhem on the derivative bounds; chemical
energy once; Guerbet 2 ethanol = 1-butanol + water in the package vapour; tightness; rejections; fingerprints.
Run: python tests/test_reaction_jacobian_bounds_liquid.py
"""
import itertools
import math
import sys
import unittest
from pathlib import Path

import mpmath as m
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.mezclas import Sistema
from core.reactions import chemical_equilibrium as ce
from core.reactions import jacobian_bounds as jb
from core.reactions.jacobian_bounds import reaction_jacobian_bounds

ETOH, HAC, ETAC, H2O, BUOH = "64-17-5", "64-19-7", "141-78-6", "7732-18-5", "71-36-3"
EST = [ETOH, HAC, ETAC, H2O]
NU_EST = [[-1, -1, 1, 1]]
LIQ = {"phase_id": "liquido", "standard_state": "pure_liquid_TP"}
VAP = {"phase_id": "vapor", "standard_state": "ideal_gas_P0"}
m.mp.dps = 50                 # comparisons and references at 50 digits (inside() must not round to binary64)
NOISE = m.mpf("1e-30")


def ends(I):
    """Exact endpoints of an mpmath interval as mpf."""
    return m.mp.make_mpf(I._mpi_[0]), m.mp.make_mpf(I._mpi_[1])


def inside(pair, value, slack=NOISE):
    return m.mpf(pair[0]) - slack <= value <= m.mpf(pair[1]) + slack


def ester_phase(package="unifac-dortmund-public"):
    return ce.PackagePhase(Sistema(package, EST, solo_liquido=True), "liquido", anchor="liquid")


# --- independent mpmath reference -------------------------------------------------------------------------
class Reference:
    """g_j(T, P, n) = sum_i nu_ij mu_i/(R T) of a package phase, rebuilt from the data tables (see module doc)."""

    def __init__(self, phase, nu, dps=50):
        import chemicals.heat_capacity as hc
        import chemicals.vapor_pressure as vp
        from core import catalogo
        self.phase, self.nu, self.dps = phase, [[m.mpf(v) for v in r] for r in nu], dps
        self.cas = list(phase.cas)
        self.vapour = phase.tipo == "vapor"
        self.R, self.T0, self.P0 = m.mpf("8.314462618"), m.mpf("298.15"), m.mpf(100000)
        self.Hf = [m.mpf(float(v)) for v in phase.Hf]
        self.S0 = [m.mpf(float(v)) for v in phase.S0]
        self.vL = [m.mpf(float(e.vL)) for e in phase.sistema.esp]      # registry datum (thermo VolumeLiquid)
        self.cp, self.wagner, self.cpL = [], [], []
        for c in self.cas:
            row = hc.Cp_data_Poling.loc[c]
            self.cp.append([m.mpf(float(row[k])) for k in ("a0", "a1", "a2", "a3", "a4")])
            reg = catalogo.REGISTRO.get(c) or catalogo.REGISTRO_SOLO_LIQUIDO[c]
            table = vp.Psat_data_WagnerPoling if reg.psat_tabla == "WagnerPoling" else vp.Psat_data_WagnerMcGarry
            w = table.loc[c]
            ex = (m.mpf("2.5"), 5) if reg.psat_tabla == "WagnerPoling" else (3, 6)
            self.wagner.append(([m.mpf(float(w[k])) for k in ("A", "B", "C", "D", "Tc", "Pc")], ex))
            if c in catalogo.REGISTRO_SOLO_LIQUIDO:
                p = hc.Cp_data_Perry_Table_153_100.loc[c]
                self.cpL.append([m.mpf(float(p[k])) / 1000 for k in ("A", "B", "C", "D", "E")])
            else:
                self.cpL.append(None)
        liq = phase.sistema.liq
        self.variant = getattr(liq, "variante", None) if not self.vapour else None
        if self.variant:
            self._unifac_tables()

    # pure components
    def ln_psat(self, i, T):
        (A, B, C, D, Tc, Pc), (e3, e4) = self.wagner[i]
        tau = 1 - T / Tc
        return m.log(Pc) + (A * tau + B * tau ** m.mpf("1.5") + C * tau ** e3 + D * tau ** e4) * Tc / T

    def g_ig0(self, i, T):
        a = self.cp[i]
        cp = lambda t: self.R * sum(a[k] * t ** k for k in range(5))
        return m.quad(cp, [self.T0, T]) - T * m.quad(lambda t: cp(t) / t, [self.T0, T])

    def g_L(self, i, T, P):
        if self.cpL[i] is None:
            Ps = m.exp(self.ln_psat(i, T))
            return self.g_ig0(i, T) + self.R * T * m.log(Ps / self.P0) + self.vL[i] * (P - Ps)
        dl = m.diff(lambda t: self.ln_psat(i, t), self.T0)
        Ps0 = m.exp(self.ln_psat(i, self.T0))
        h0 = -self.R * self.T0 ** 2 * dl + self.vL[i] * (self.P0 - Ps0) + self.T0 * self.vL[i] * Ps0 * dl
        s0 = -self.R * m.log(Ps0 / self.P0) - self.R * self.T0 * dl + self.vL[i] * Ps0 * dl
        c = self.cpL[i]
        cp = lambda t: sum(c[k] * t ** k for k in range(5))
        h = h0 + m.quad(cp, [self.T0, T]) + self.vL[i] * (P - self.P0)
        s = s0 + m.quad(lambda t: cp(t) / t, [self.T0, T])
        return h - T * s

    # UNIFAC in mole-fraction form, from thermo's tables
    def _unifac_tables(self):
        import thermo.unifac as tu
        tu.load_unifac_ip()
        tu.load_group_assignments_DDBST()
        if self.variant == "dortmund":
            SG, IP, model = tu.DOUFSG, tu.DOUFIP2016, "MODIFIED_UNIFAC"
        elif self.variant == "original":
            SG, IP, model = tu.UFSG, tu.UFIP, "UNIFAC"
        else:
            raise unittest.SkipTest("reference covers the original and Dortmund tables")
        self.assign = [{int(k): int(v) for k, v in tu.UNIFAC_group_assignment_DDBST(c, model).items()} for c in self.cas]
        self.groups = sorted({k for a in self.assign for k in a})
        self.Rg = {k: m.mpf(float(SG[k].R)) for k in self.groups}
        self.Qg = {k: m.mpf(float(SG[k].Q)) for k in self.groups}
        self.main = {k: int(SG[k].main_group_id) for k in self.groups}
        self.ip = {}
        for a in self.groups:
            for b in self.groups:
                ma, mb = self.main[a], self.main[b]
                if ma == mb:
                    self.ip[(a, b)] = (0, 0, 0)
                else:
                    v = IP[ma][mb]
                    self.ip[(a, b)] = tuple(m.mpf(float(t)) for t in v) if isinstance(v, (tuple, list)) \
                        else (m.mpf(float(v)), 0, 0)

    def _psi(self, a, b, T):
        A, B, C = self.ip[(a, b)]
        return m.exp(-(A + B * T + C * T * T) / T)

    def _lnGamma(self, xg, T):
        """ln Gamma_k for group mole numbers xg {k: amount} (normalised here)."""
        tot = sum(xg.values())
        X = {k: v / tot for k, v in xg.items()}
        sq = sum(self.Qg[k] * X[k] for k in X)
        th = {k: self.Qg[k] * X[k] / sq for k in X}
        S = {k: sum(th[mm] * self._psi(mm, k, T) for mm in X) for k in X}
        return {k: self.Qg[k] * (1 - m.log(S[k]) - sum(th[mm] * self._psi(k, mm, T) / S[mm] for mm in X)) for k in X}

    def lngamma(self, T, n):
        with m.workdps(max(m.mp.dps, self.dps)):
            return self._lngamma(T, n)

    def _lngamma(self, T, n):
        s = len(n)
        if not self.variant:
            return [m.mpf(0)] * s
        N = sum(n)
        x = [v / N for v in n]
        r = [sum(v * self.Rg[k] for k, v in self.assign[i].items()) for i in range(s)]
        q = [sum(v * self.Qg[k] for k, v in self.assign[i].items()) for i in range(s)]
        rx, qx = sum(r[i] * x[i] for i in range(s)), sum(q[i] * x[i] for i in range(s))
        out = []
        if self.variant == "dortmund":
            r34 = [ri ** m.mpf("0.75") for ri in r]
            r34x = sum(r34[i] * x[i] for i in range(s))
            for i in range(s):
                V, Vp, F = r[i] / rx, r34[i] / r34x, q[i] / qx
                out.append(1 - Vp + m.log(Vp) - 5 * q[i] * (1 - V / F + m.log(V / F)))
        else:
            l = [5 * (r[i] - q[i]) - (r[i] - 1) for i in range(s)]
            lx = sum(l[i] * x[i] for i in range(s))
            for i in range(s):
                phx, thph = r[i] / rx, (q[i] / qx) / (r[i] / rx)
                out.append(m.log(phx) + 5 * q[i] * m.log(thph) + l[i] - phx * lx)
        mix = {k: sum(x[i] * self.assign[i].get(k, 0) for i in range(s)) for k in self.groups}
        lnG = self._lnGamma(mix, T)
        for i in range(s):
            pure = self._lnGamma({k: m.mpf(v) for k, v in self.assign[i].items()}, T)
            out[i] += sum(v * (lnG[k] - pure[k]) for k, v in self.assign[i].items())
        return out

    # reaction affinity, split so that complex steps in n never touch the quadratures
    def standard(self, j, T, P):
        with m.workdps(max(m.mp.dps, self.dps)):
            T, P = m.mpf(T), m.mpf(P)
            tot = 0
            for i, v in enumerate(self.nu[j]):
                if v:
                    mu0 = (self.g_ig0(i, T) if self.vapour else self.g_L(i, T, P)) + self.Hf[i] - T * self.S0[i]
                    tot += v * mu0
            out = tot / (self.R * T)
            if self.vapour:
                out += sum(self.nu[j]) * m.log(P / self.P0)
            return out

    def composition(self, j, T, n):
        N = sum(n)
        lg = self.lngamma(T, n)
        return sum(v * (m.log(n[i] / N) + lg[i]) for i, v in enumerate(self.nu[j]) if v)

    def g(self, j, T, P, n):
        with m.workdps(max(m.mp.dps, self.dps)):
            return self.standard(j, T, P) + self.composition(j, m.mpf(T), [m.mpf(v) for v in n])

    def dn(self, j, k, T, P, n, h=m.mpf("1e-30")):
        with m.workdps(self.dps):
            q = [m.mpc(v) for v in n]
            q[k] += m.mpc(0, h)
            return m.im(self.composition(j, m.mpf(T), q)) / h

    def dlngamma_dn(self, T, n, k, h=m.mpf("1e-30")):
        with m.workdps(self.dps):
            q = [m.mpc(v) for v in n]
            q[k] += m.mpc(0, h)
            return [m.im(v) / h for v in self.lngamma(m.mpf(T), q)]

    def dlngamma_dT(self, T, n, h=m.mpf("1e-30")):
        with m.workdps(self.dps):
            return [m.im(v) / h for v in self.lngamma(m.mpc(T, h), [m.mpf(x) for x in n])]

    def dT(self, j, T, P, n):
        with m.workdps(self.dps + 40):
            return m.diff(lambda t: self.g(j, t, P, n), m.mpf(T), h=m.mpf(T) * m.mpf("1e-20"))

    def dP(self, j, T, P, n):
        with m.workdps(self.dps + 40):
            return m.diff(lambda p: self.standard(j, T, p), m.mpf(P), h=m.mpf(P) * m.mpf("1e-20"))


# --- interval AD rules ------------------------------------------------------------------------------------
class IntervalADRules(unittest.TestCase):
    def test_point_value_gradient_hessian(self):
        from mpmath import iv
        from core.termodinamica import interval_ad as ad
        old = iv.prec
        iv.prec = 113
        try:
            x0, y0 = 1.3, 0.7
            x, y = ad.var(x0, x0, 0), ad.var(y0, y0, 1)
            F = ad.log(x * y + ad.exp(x / y)) * ad.power(y, 1.5) / (x + 2) - ad.power(x, 3) * y
            f = lambda a, b: m.log(a * b + m.exp(a / b)) * b ** m.mpf("1.5") / (a + 2) - a ** 3 * b
            with m.workdps(40):
                x0, y0 = m.mpf(x0), m.mpf(y0)
                ref = {"v": f(x0, y0), (0,): m.diff(f, (x0, y0), (1, 0)), (1,): m.diff(f, (x0, y0), (0, 1)),
                       (0, 0): m.diff(f, (x0, y0), (2, 0)), (0, 1): m.diff(f, (x0, y0), (1, 1)),
                       (1, 1): m.diff(f, (x0, y0), (0, 2))}
            cont = lambda I, v: inside(ends(I), v, m.mpf("1e-25"))
            self.assertTrue(cont(F.v, ref["v"]))
            for k in (0, 1):
                self.assertTrue(cont(F.g[k], ref[(k,)]), k)
            for key in ((0, 0), (0, 1), (1, 1)):
                self.assertTrue(cont(F.h[key], ref[key]), key)
        finally:
            iv.prec = old

    def test_box_encloses_sampled_derivatives(self):
        from mpmath import iv
        from core.termodinamica import interval_ad as ad
        old = iv.prec
        iv.prec = 113
        try:
            x, y = ad.var(1.0, 1.5, 0), ad.var(0.5, 0.9, 1)
            F = ad.log(x * y + ad.exp(x / y)) * ad.power(y, 1.5) / (x + 2)
            f = lambda a, b: m.log(a * b + m.exp(a / b)) * b ** m.mpf("1.5") / (a + 2)
            for a, b in itertools.product(map(m.mpf, np.linspace(1.0, 1.5, 4)), map(m.mpf, np.linspace(0.5, 0.9, 4))):
                self.assertTrue(inside(ends(F.v), f(a, b), 0))
                self.assertTrue(inside(ends(F.g[0]), m.diff(f, (a, b), (1, 0)), m.mpf("1e-12")))
                self.assertTrue(inside(ends(F.h[(0, 1)]), m.diff(f, (a, b), (1, 1)), m.mpf("1e-10")))
        finally:
            iv.prec = old

    def test_domain_violations_raise(self):
        from mpmath import iv
        from core.termodinamica import interval_ad as ad
        with self.assertRaises(ValueError):
            ad.log(ad.var(-1.0, 1.0, 0))
        with self.assertRaises(ValueError):
            ad.const(1) / ad.var(-1.0, 1.0, 0)
        with self.assertRaises(ValueError):
            ad.power(ad.var(-0.1, 1.0, 0), 1.5)
        self.assertEqual(iv.prec, iv.prec)


# --- interval UNIFAC against the reference at points --------------------------------------------------------
class IntervalUnifacPoints(unittest.TestCase):
    def check(self, package, cas, T, n, solo=False):
        from mpmath import iv
        from core.termodinamica import interval_ad as ad
        from core.termodinamica.unifac_intervals import UnifacIntervalModel
        sis = Sistema(package, cas, solo_liquido=solo)
        phase = ce.PackagePhase(sis, "liquido", anchor="liquid" if solo else "gas")
        ref = Reference(phase, [[0] * len(cas)])
        old = iv.prec
        iv.prec = 113
        try:
            lg = UnifacIntervalModel(sis.liq).lngamma(ad.var(T, T, 0), [ad.var(v, v, k + 1) for k, v in enumerate(n)])
        finally:
            iv.prec = old
        val = ref.lngamma(m.mpf(T), [m.mpf(v) for v in n])
        dT = ref.dlngamma_dT(T, n)
        for i in range(len(cas)):
            self.assertTrue(inside(ends(lg[i].v), val[i], m.mpf("1e-28")), (package, i))
            self.assertTrue(inside(ends(lg[i].g[0]), dT[i], m.mpf("1e-28")), (package, i, "T"))
        for k in range(len(cas)):
            dk = ref.dlngamma_dn(T, n, k)
            for i in range(len(cas)):
                self.assertTrue(inside(ends(lg[i].g[k + 1]), dk[i], m.mpf("1e-28")), (package, i, k))
            # Gibbs-Duhem on the reference itself: sum_i n_i d ln gamma_i / dn_k = 0
            self.assertLess(abs(sum(m.mpf(n[i]) * dk[i] for i in range(len(cas)))), m.mpf("1e-40"))

    def test_esterification_dortmund(self):
        self.check("unifac-dortmund-public", EST, 345.0, [1.0, 0.7, 0.4, 0.9], solo=True)

    def test_esterification_original(self):
        self.check("unifac-original-public", EST, 345.0, [1.0, 0.7, 0.4, 0.9], solo=True)

    def test_dilute_butanol_water_dortmund(self):
        self.check("unifac-dortmund-public", [ETOH, BUOH, H2O], 330.0, [0.05, 1e-6, 2.0])

    def test_against_production_float(self):
        sis = Sistema("unifac-dortmund-public", EST, solo_liquido=True)
        ref = Reference(ce.PackagePhase(sis, "liquido", anchor="liquid"), [[0, 0, 0, 0]])
        n = [0.3, 1.2, 0.8, 0.1]
        val = ref.lngamma(m.mpf(350), [m.mpf(v) for v in n])
        prod = sis.liq.lngamma(350.0, np.array(n) / sum(n))
        for i in range(4):
            self.assertLess(abs(val[i] - prod[i]), 1e-13)


# --- esterification in the liquid -----------------------------------------------------------------------------
class EsterificationLiquid(unittest.TestCase):
    PACKAGE = "unifac-dortmund-public"
    BOX = {"T": [340.0, 350.0], "P": [1e5, 2e5], "n": [[0.9, 1.1], [0.6, 0.8], [0.3, 0.5], [0.8, 1.0]]}

    @classmethod
    def setUpClass(cls):
        cls.phase = ester_phase(cls.PACKAGE)
        cls.ref = Reference(cls.phase, NU_EST)
        cls.out = reaction_jacobian_bounds(cls.phase, NU_EST, cls.BOX, **LIQ)

    def test_certified_record(self):
        out = self.out
        self.assertTrue(out["certified"], out["diagnostics"])
        self.assertEqual((out["format"], out["version"]), ("rage.reaction-jacobian-bounds", 1))
        self.assertEqual((out["phase_id"], out["standard_state"], out["anchor"]), ("liquido", "pure_liquid_TP", "liquid"))
        self.assertEqual(set(out["fingerprints"]), {"package", "pureData", "formationReference", "activityModel"})
        v = out["proof"]["validity"]
        self.assertEqual(v["liquid_only"], {"species": [HAC], "anchor": "liquid", "tipo": "liquido", "admitted": True})
        self.assertTrue(v["temperature"]["inside"] and v["pressure"]["inside"])
        self.assertTrue(all(r["balanced"] for r in v["elements"]["reactions"]))
        self.assertIn("UNIFAC", v["activity_model"])

    def test_point_box_encloses_reference(self):
        T, P, n = 345.0, 1.5e5, [1.0, 0.7, 0.4, 0.9]
        b = reaction_jacobian_bounds(self.phase, NU_EST, {"T": [T, T], "P": [P, P], "n": [[v, v] for v in n]},
                                     **LIQ)["bounds"]
        g = self.ref.g(0, T, P, n)
        self.assertTrue(m.mpf(b["g"][0][0]) < g < m.mpf(b["g"][0][1]))
        self.assertTrue(inside(b["dg_dT"][0], self.ref.dT(0, T, P, n)))
        self.assertTrue(inside(b["dg_dP"][0], self.ref.dP(0, T, P, n)))
        for k in range(4):
            self.assertTrue(inside(b["dg_dn"][0][k], self.ref.dn(0, k, T, P, n)), k)
        for pair in [b["g"][0], b["dg_dT"][0], b["dg_dP"][0]] + b["dg_dn"][0]:
            self.assertLess(pair[1] - pair[0], 1e-12 * max(1.0, abs(pair[0])))

    def test_box_encloses_reference_at_corners_and_interior(self):
        b = self.out["bounds"]
        box = self.BOX
        corners = list(itertools.product(box["T"], box["P"], *box["n"]))[::7]
        rng = np.random.default_rng(5)
        pts = corners + [tuple(rng.uniform(lo, hi) for lo, hi in [box["T"], box["P"], *box["n"]]) for _ in range(4)]
        for T, P, *n in pts:
            self.assertTrue(inside(b["g"][0], self.ref.g(0, T, P, n)), (T, P, n))
            self.assertTrue(inside(b["dg_dP"][0], self.ref.dP(0, T, P, n)))
            for k in range(4):
                self.assertTrue(inside(b["dg_dn"][0][k], self.ref.dn(0, k, T, P, n)), (k, T, P, n))
        for T, P, *n in pts[:3]:
            self.assertTrue(inside(b["dg_dT"][0], self.ref.dT(0, T, P, n)), (T, P, n))

    def test_dense_provider_samples(self):
        b, rng = self.out["bounds"], np.random.default_rng(2026)
        intervals = [self.BOX["T"], self.BOX["P"], *self.BOX["n"]]
        pts = [tuple(rng.uniform(lo, hi) for lo, hi in intervals) for _ in range(1500)]
        pts += list(itertools.product(*intervals))                          # all 64 corners
        for idx, (T, P, *n) in enumerate(pts):
            st = ce.evaluate_reactions(self.phase, NU_EST, T=T, P=P, n=n, **LIQ)
            g = st["affinity_RT"][0]
            self.assertTrue(b["g"][0][0] <= g <= b["g"][0][1], (T, P, n, g))
            if idx % 10 == 0:                                                # finite-difference derivatives
                J = np.asarray(NU_EST, float) @ np.asarray(st["dmu_dn"]) / (ce.R * T)
                for k in range(4):
                    lo, hi = b["dg_dn"][0][k]
                    tol = 1e-5 * max(abs(lo), abs(hi), 1.0)
                    self.assertTrue(lo - tol <= J[0, k] <= hi + tol, (k, J[0, k]))

    def test_gibbs_duhem_on_derivative_bounds(self):
        from mpmath import iv
        # over the box: for every n in it, sum_k n_k dg/dn_k = 0, so 0 lies in sum_k [n_k] [dg/dn_k]
        b = self.out["bounds"]
        tot = sum((iv.mpf(list(self.BOX["n"][k])) * iv.mpf(b["dg_dn"][0][k]) for k in range(4)), iv.mpf(0))
        self.assertTrue(inside(ends(tot), 0, 0))
        # at a point the sum is zero to the enclosure width
        n = [1.0, 0.7, 0.4, 0.9]
        bp = reaction_jacobian_bounds(self.phase, NU_EST, {"T": [345.0, 345.0], "P": [1e5, 1e5],
                                                           "n": [[v, v] for v in n]}, **LIQ)["bounds"]
        tot = sum((iv.mpf(n[k]) * iv.mpf(bp["dg_dn"][0][k]) for k in range(4)), iv.mpf(0))
        lo, hi = ends(tot)
        self.assertTrue(lo <= 0 <= hi and hi - lo < 1e-13)

    def test_chemical_energy_once(self):
        T, P, n = 345.0, 1e5, [1.0, 0.7, 0.4, 0.9]
        b = reaction_jacobian_bounds(self.phase, NU_EST, {"T": [T, T], "P": [P, P], "n": [[v, v] for v in n]},
                                     **LIQ)["bounds"]
        st = ce.evaluate_reactions(self.phase, NU_EST, T=T, P=P, n=n, **LIQ)
        dH = float(np.asarray(NU_EST[0], float) @ np.asarray(st["h_partial"]))
        mid = -0.5 * sum(b["dg_dT"][0]) * ce.R * T ** 2
        self.assertLess(abs(mid - dH), 1e-5 * max(abs(dH), 1e3))

    def test_small_box_is_tight(self):
        c = [1.0, 0.7, 0.4, 0.9]
        box = {"T": [344.9655, 345.0345], "P": [1e5, 1e5], "n": [[v * 0.999, v * 1.001] for v in c]}
        b = reaction_jacobian_bounds(self.phase, NU_EST, box, **LIQ)["bounds"]
        pts = list(itertools.product(box["T"], *box["n"]))
        gs = [ce.evaluate_reactions(self.phase, NU_EST, T=p[0], P=1e5, n=list(p[1:]), **LIQ)["affinity_RT"][0]
              for p in pts]
        self.assertLess(b["g"][0][1] - b["g"][0][0], 1.1 * (max(gs) - min(gs)))


class EsterificationOriginal(EsterificationLiquid):
    PACKAGE = "unifac-original-public"


class EsterificationIdealLiquid(unittest.TestCase):
    def test_point_and_box(self):
        phase = ester_phase("mezcla-ideal")
        ref = Reference(phase, NU_EST)
        box = {"T": [300.0, 380.0], "P": [1e4, 4e5], "n": [[0.5, 1.0], [0.5, 1.0], [0.1, 0.5], [1e-6, 0.5]]}
        out = reaction_jacobian_bounds(phase, NU_EST, box, **LIQ)
        self.assertTrue(out["certified"], out["diagnostics"])
        self.assertIsNone(out["proof"]["excess_pieces"])
        b = out["bounds"]
        for T, P, *n in list(itertools.product(*[box["T"], box["P"], *box["n"]]))[::9]:
            self.assertTrue(inside(b["g"][0], ref.g(0, T, P, n)))
            self.assertTrue(inside(b["dg_dP"][0], ref.dP(0, T, P, n)))
            for k in range(4):
                self.assertTrue(inside(b["dg_dn"][0][k], ref.dn(0, k, T, P, n)))
        self.assertTrue(inside(b["dg_dT"][0], ref.dT(0, 300.0, 1e4, [0.5, 0.5, 0.1, 1e-6])))
        self.assertTrue(inside(b["dg_dT"][0], ref.dT(0, 380.0, 4e5, [1.0, 1.0, 0.5, 0.5])))


class GuerbetVapour(unittest.TestCase):
    """2 ethanol = 1-butanol + water in the package's ideal vapour (Dnu = 0) and in its UNIFAC liquid."""

    def test_vapour_point_and_box(self):
        phase = ce.PackagePhase(Sistema("unifac-dortmund-public", [ETOH, BUOH, H2O]), "vapor")
        ref = Reference(phase, [[-2, 1, 1]])
        box = {"T": [360.0, 400.0], "P": [5e4, 3e5], "n": [[0.5, 1.0], [0.01, 0.2], [0.05, 0.3]]}
        out = reaction_jacobian_bounds(phase, [[-2, 1, 1]], box, **VAP)
        self.assertTrue(out["certified"], out["diagnostics"])
        self.assertEqual(out["proof"]["validity"]["activity_model"], "ideal vapour")
        b = out["bounds"]
        for T, P, *n in list(itertools.product(*[box["T"], box["P"], *box["n"]]))[::5]:
            self.assertTrue(inside(b["g"][0], ref.g(0, T, P, n)))
            for k in range(3):
                self.assertTrue(inside(b["dg_dn"][0][k], ref.dn(0, k, T, P, n)))
        self.assertTrue(inside(b["dg_dT"][0], ref.dT(0, 380.0, 1e5, [0.7, 0.1, 0.2])))
        lo, hi = b["dg_dP"][0]
        self.assertTrue(lo <= 0.0 <= hi and hi - lo < 1e-300)

    def test_liquid_trace_butanol(self):
        phase = ce.PackagePhase(Sistema("unifac-dortmund-public", [ETOH, BUOH, H2O]), "liquido")
        ref = Reference(phase, [[-2, 1, 1]])
        box = {"T": [330.0, 331.0], "P": [1e5, 1e5], "n": [[1.0, 1.01], [1e-9, 1e-8], [0.5, 0.51]]}
        out = reaction_jacobian_bounds(phase, [[-2, 1, 1]], box, **LIQ)
        self.assertTrue(out["certified"], out["diagnostics"])
        b = out["bounds"]
        for T, P, *n in itertools.product(*[box["T"], box["P"], *box["n"]]):
            self.assertTrue(inside(b["g"][0], ref.g(0, T, P, n)))
            for k in range(3):
                self.assertTrue(inside(b["dg_dn"][0][k], ref.dn(0, k, T, P, n)), k)


class RejectionsAndFingerprints(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.phase = ester_phase()
        cls.box = {"T": [340.0, 341.0], "P": [1e5, 1e5], "n": [[1, 1.01], [0.7, 0.71], [0.4, 0.41], [0.9, 0.91]]}

    def located(self, out):
        self.assertFalse(out["certified"])
        self.assertIsNone(out["bounds"])
        self.assertIsNone(out["proof"])
        return [(d["code"], d["path"]) for d in out["diagnostics"]]

    def test_temperature_and_pressure_outside_package_domain(self):
        out = reaction_jacobian_bounds(self.phase, NU_EST, {**self.box, "T": [380.0, 395.0]}, **LIQ)
        self.assertEqual(self.located(out), [("OUT_OF_DOMAIN", "box.T")])        # acetic acid cp_L ends at 391.05 K
        out = reaction_jacobian_bounds(self.phase, NU_EST, {**self.box, "P": [1e5, 6e5]}, **LIQ)
        self.assertEqual(self.located(out), [("OUT_OF_DOMAIN", "box.P")])

    def test_liquid_only_rule(self):
        with self.assertRaises(ce.ChemicalEquilibriumError) as cm:
            ce.PackagePhase(Sistema("unifac-dortmund-public", EST, solo_liquido=True), "liquido")
        self.assertEqual(cm.exception.code, "LIQUID_ANCHOR_REQUIRED")
        tampered = ester_phase()
        tampered.anchor = "gas"                                   # the proof re-checks the rule, never assumes it
        out = reaction_jacobian_bounds(tampered, NU_EST, self.box, **LIQ)
        self.assertEqual(self.located(out), [("LIQUID_ANCHOR_REQUIRED", "provider.anchor")])

    def test_unbalanced_row(self):
        out = reaction_jacobian_bounds(self.phase, [[-1, -1, 1, 1], [-1, -1, 1, 2]], self.box, **LIQ)
        self.assertEqual(self.located(out), [("FORMATION_REFERENCE_INVALID", "nu[1]")])

    def test_nrtl_not_extended(self):
        phase = ce.PackagePhase(Sistema("nrtl-chemsep", [ETOH, H2O]), "liquido")
        out = reaction_jacobian_bounds(phase, [[0, 0]], {"T": [340.0, 341.0], "P": [1e5, 1e5],
                                                         "n": [[1, 1], [1, 1]]}, **LIQ)
        self.assertEqual(self.located(out), [("PROVIDER_UNSUPPORTED", "provider.sistema.liq")])

    def test_mismatched_state_rejected(self):
        with self.assertRaises(ce.ChemicalEquilibriumError) as cm:
            reaction_jacobian_bounds(self.phase, NU_EST, self.box, phase_id="liquido", standard_state="ideal_gas_P0")
        self.assertEqual((cm.exception.code, cm.exception.detail.get("path")), ("STANDARD_STATE_MISMATCH",
                                                                                "standard_state"))

    def test_fingerprints_pin_the_unifac_parameter_set(self):
        a = reaction_jacobian_bounds(self.phase, NU_EST, self.box, **LIQ)["fingerprints"]
        b = reaction_jacobian_bounds(ester_phase(), NU_EST, self.box, **LIQ)["fingerprints"]
        c = reaction_jacobian_bounds(ester_phase("unifac-original-public"), NU_EST, self.box, **LIQ)["fingerprints"]
        d = reaction_jacobian_bounds(ester_phase("mezcla-ideal"), NU_EST, self.box, **LIQ)["fingerprints"]
        self.assertEqual(a, b)
        self.assertNotEqual(a["activityModel"], c["activityModel"])
        self.assertNotEqual(a["activityModel"], d["activityModel"])
        self.assertNotEqual(a["package"], c["package"])
        self.assertEqual(a["pureData"], c["pureData"])
        self.assertEqual(a["formationReference"], c["formationReference"])

    def test_liquid_anchor_reproduces_tabulated_liquid_formation(self):
        from chemicals import reaction as rx
        ref = Reference(self.phase, [[0, 0, 0, 0]])
        for i, c in enumerate(EST):
            mu0 = ref.g_L(i, ref.T0, ref.P0) + ref.Hf[i] - ref.T0 * ref.S0[i]
            target = m.mpf(rx.Hfl(c)) - ref.T0 * m.mpf(rx.S0l(c))
            self.assertLess(abs(mu0 - target), 1e-9 * abs(target), c)


if __name__ == "__main__":
    unittest.main(verbosity=2)
