"""
PSRK (SRK + UNIFAC excess-Gibbs mixing rule), elevated-pressure VLE and binary critical loci (F8b, 6 November 2026).

Package: core/termodinamica/psrk.py and core/termodinamica/psrk_data.py. Every formula is checked numerically:

  - constants and pure limits: SRK Omega_a, Omega_b from the critical conditions against their closed forms;
    the Mathias-Copeman regression against each species' vapour-pressure record; the CO2 alpha against the
    published PSRK constants (Horstmann et al. 2005, as quoted by thermo); the CO2 ancillary equation against
    the Span-Wagner triple point;
  - mixing rule and derivatives: g^E and ln gamma against thermo's UNIFAC with the PSRK table; a and b against
    thermo's PSRK class (independent implementation; its fugacities are not implemented in thermo 0.6.1);
    dF/dn and dF/dV against a complex step of F; Gibbs-Duhem and symmetry of d ln phi/dn;
    d(g^r/RT)/dP = (Z - 1)/P and d(g^r/RT)/dT = -h^r/RT^2;
  - an independent mpmath PSRK (closed-form SRK fugacity coefficients, the alternative form of the
    Staverman-Guggenheim combinatorial, closed-form Omega constants, 30 digits): a CO2 + ethanol bubble point and
    a CO2 + methanol critical point by the Reid-Beegle determinant criteria with mp.diff derivatives;
  - experiment (NIST ThermoML archive, no binary parameter fitted): CO2 + ethanol bubble pressures
    (Sima, Feroiu and Geana, J. Chem. Eng. Data 56 (2011) 5052, doi:10.1021/je2008186), CO2 + methanol and
    CO2 + toluene bubble pressures and vapour compositions (Naidoo, Ramjugernath and Raal, Fluid Phase Equilib.
    269 (2008) 104, doi:10.1016/j.fluid.2008.05.002), and the critical lines of CO2 + methanol (Liu, Qin, Wang,
    Hou and Wang, J. Chem. Eng. Data 48 (2003) 1610, doi:10.1021/je034127q) and CO2 + ethanol (Sima et al. 2011);
  - located rejections outside the coverage of the published parameters.
"""

import math
import os
import sys
import time
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import mpmath as mp  # noqa: E402

from core.termodinamica import psrk, psrk_data  # noqa: E402
from core.termodinamica.cubic_eos import CubicOutOfScope  # noqa: E402

CO2, ETOH, MEOH, TOL, WATER = "124-38-9", "64-17-5", "67-56-1", "108-88-3", "7732-18-5"

# --- experimental data (x_CO2, T / K, P / kPa[, y_CO2]) -----------------------------------------------------------
# All 36 bubble points of the ThermoML file (review R1: no selection).
SIMA_2011_ETOH_BUBBLE = [
    (0.1133, 333.15, 2150), (0.1748, 333.15, 3280), (0.2127, 333.15, 4090), (0.3317, 333.15, 6060),
    (0.387, 333.15, 6830), (0.4303, 333.15, 7590), (0.5004, 333.15, 8600), (0.689, 333.15, 10500),
    (0.079, 343.15, 1440), (0.097, 343.15, 1840), (0.147, 343.15, 2930), (0.201, 343.15, 4080),
    (0.265, 343.15, 5150), (0.309, 343.15, 6200), (0.379, 343.15, 7300), (0.429, 343.15, 8270),
    (0.488, 343.15, 9350),
    (0.0598, 363.15, 1120), (0.1013, 363.15, 1970), (0.14, 363.15, 3180), (0.2, 363.15, 4630),
    (0.257, 363.15, 6010), (0.2727, 363.15, 6270), (0.3426, 363.15, 7820), (0.393, 363.15, 8970),
    (0.4507, 363.15, 10040), (0.4641, 363.15, 10210), (0.498, 363.15, 11050), (0.5554, 363.15, 12120),
    (0.685, 363.15, 13750), (0.77, 363.15, 14150),
    (0.1315, 373.15, 3400), (0.2268, 373.15, 5720), (0.301, 373.15, 7410), (0.3608, 373.15, 8890),
    (0.5468, 373.15, 12360)]
NAIDOO_2008_MEOH = [
    (0.0653, 313.15, 1291, 0.9732), (0.1856, 313.15, 3145, 0.9856), (0.3227, 313.15, 5192, 0.9845),
    (0.4736, 313.15, 6758, 0.9866),
    (0.0469, 363.15, 1569, 0.7991), (0.1138, 363.15, 4021, 0.9132), (0.2389, 363.15, 7689, 0.9362),
    (0.2713, 363.15, 8564, 0.9419),
    (0.0451, 373.15, 2157, 0.8042), (0.1258, 373.15, 5094, 0.9053), (0.2531, 373.15, 9067, 0.9118),
    (0.3611, 373.15, 12068, 0.8927)]
NAIDOO_2008_TOL = [
    (0.1105, 311.15, 1144, 0.9902), (0.2476, 311.15, 2534, 0.9912), (0.4067, 311.15, 3968, 0.9927),
    (0.5665, 311.15, 5225, 0.9945), (0.7848, 311.15, 6644, 0.9939),
    (0.0715, 353.15, 1252, 0.9562), (0.1939, 353.15, 3255, 0.9817), (0.3816, 353.15, 6569, 0.9845),
    (0.4972, 353.15, 8435, 0.9828), (0.6816, 353.15, 10649, 0.9697),
    (0.0986, 391.45, 2064, 0.9285), (0.2382, 391.45, 5240, 0.9541), (0.3997, 391.45, 9439, 0.9485),
    (0.5467, 391.45, 12133, 0.9325)]
# (x_CO2, T_c / K, P_c / kPa)
LIU_2003_MEOH_CRITICAL = [
    (0.072, 507.2, 8800), (0.169, 494.6, 10330), (0.244, 485.4, 11540), (0.327, 473.2, 12840),
    (0.383, 460.5, 14000), (0.446, 451.1, 14740), (0.495, 442.8, 15270), (0.572, 423.9, 16320),
    (0.668, 414.3, 16340), (0.713, 408.2, 16260), (0.786, 384.8, 15760), (0.81, 374.3, 15070),
    (0.862, 354.7, 13750), (0.893, 346.7, 12950), (0.912, 333.3, 11040), (0.965, 313.4, 8290)]
SIMA_2011_ETOH_CRITICAL = [
    (0.8315, 364.15, 13860), (0.838, 361.65, 13700), (0.8401, 355.05, 13110), (0.8409, 348.65, 12540),
    (0.842, 342.65, 12000), (0.8507, 335.65, 11170), (0.892, 330.15, 10450), (0.901, 332.15, 10600),
    (0.908, 325.65, 9840), (0.931, 321.15, 9100)]

KAPPA = dict(kappa_range=(1.12, 12.0), n_scan=60)
_EOS = {}


def eos_of(*cas):
    if cas not in _EOS:
        _EOS[cas] = psrk.PSRKMixture(cas)
    return _EOS[cas]


def bubble_deviations(eos, data):
    """([(x, T, P_exp, P_calc, y_exp, y_calc)], [(T, x, cause, at)]) by continuation along each isotherm."""
    out, rejected = [], []
    for T in sorted({d[1] for d in data}):
        pts = sorted(d for d in data if d[1] == T)
        res, rej = psrk.bubble_isotherm(eos, T, [p[0] for p in pts], j=0)
        for d, r in zip(pts, res):
            out.append((d[0], T, d[2] * 1e3, r["P"], d[3] if len(d) > 3 else None, float(r["y"][0])))
        rejected += [(T, r["x"][0], r["cause"], r["at"]) for r in rej]
    return out, rejected


# --- independent mpmath PSRK ---------------------------------------------------------------------------------------
class MpPSRK:
    """PSRK for a binary in mpmath, written from the published equations independently of core/: closed-form SRK
    constants, ln phi_i = (b_i/b)(Z - 1) - ln(Z - B) - abar_i ln(1 + B/Z), UNIFAC with the combinatorial in the
    form 1 - V + ln V - 5 q (1 - V/F + ln(V/F)). Data only (T_c, P_c, Mathias-Copeman constants, PSRK groups and
    table) are taken from the package and from thermo."""

    def __init__(self, eos):
        import thermo.unifac as tu
        mp.mp.dps = 30
        tu.load_unifac_ip()
        c13 = mp.cbrt(2) - 1
        self.oa, self.ob = 1 / (9 * c13), c13 / 3
        self.R = mp.mpf(psrk.R)
        self.Tc = [mp.mpf(float(v)) for v in eos.Tc]
        self.Pc = [mp.mpf(float(v)) for v in eos.Pc]
        self.mc = [[mp.mpf(float(c)) for c in row] for row in eos.mc]
        self.b = [self.ob * self.R * self.Tc[i] / self.Pc[i] for i in range(2)]
        self.A1 = -mp.log(mp.mpf(21) / 11)
        groups = [eos.gE.asignaciones[c] for c in eos.cas]
        self.keys = sorted({k for g in groups for k in g})
        self.nu = [[g.get(k, 0) for k in self.keys] for g in groups]
        self.Rk = [mp.mpf(tu.PSRKSG[k].R) for k in self.keys]
        self.Qk = [mp.mpf(tu.PSRKSG[k].Q) for k in self.keys]
        mg = [tu.PSRKSG[k].main_group_id for k in self.keys]
        self.abc = [[(0, 0, 0) if mg[i] == mg[j] else tuple(mp.mpf(v) for v in tu.PSRKIP[mg[i]][mg[j]])
                     for j in range(len(self.keys))] for i in range(len(self.keys))]

    def alpha_i(self, T, i):
        t = 1 - mp.sqrt(T / self.Tc[i])
        c1, c2, c3 = self.mc[i]
        s = 1 + c1 * t + ((c2 * t ** 2 + c3 * t ** 3) if T < self.Tc[i] else 0)
        return self.oa * self.R ** 2 * self.Tc[i] ** 2 / self.Pc[i] * s ** 2 / (self.b[i] * self.R * T)

    def _lnGamma(self, T, X):
        G = len(self.keys)
        s = mp.fsum(X)
        X = [v / s for v in X]
        sq = mp.fsum(self.Qk[m] * X[m] for m in range(G))
        th = [self.Qk[m] * X[m] / sq for m in range(G)]
        psi = [[mp.exp(-(a + b * T + c * T ** 2) / T) for (a, b, c) in row] for row in self.abc]
        S = [mp.fsum(th[m] * psi[m][k] for m in range(G)) for k in range(G)]
        return [self.Qk[k] * (1 - mp.log(S[k]) - mp.fsum(th[m] * psi[k][m] / S[m] for m in range(G)))
                for k in range(G)]

    def lngamma(self, T, x):
        G = len(self.keys)
        r = [mp.fsum(self.nu[i][k] * self.Rk[k] for k in range(G)) for i in range(2)]
        q = [mp.fsum(self.nu[i][k] * self.Qk[k] for k in range(G)) for i in range(2)]
        sr, sq = mp.fsum(x[i] * r[i] for i in range(2)), mp.fsum(x[i] * q[i] for i in range(2))
        lnG = self._lnGamma(T, [mp.fsum(x[i] * self.nu[i][k] for i in range(2)) for k in range(G)])
        out = []
        for i in range(2):
            V, F = r[i] / sr, q[i] / sq
            comb = 1 - V + mp.log(V) - 5 * q[i] * (1 - V / F + mp.log(V / F))
            lnGi = self._lnGamma(T, [mp.mpf(self.nu[i][k]) for k in range(G)])
            res = mp.fsum(self.nu[i][k] * (lnG[k] - lnGi[k]) for k in range(G) if self.nu[i][k])
            out.append(comb + res)
        return out

    def mix(self, T, x):
        b = mp.fsum(x[i] * self.b[i] for i in range(2))
        lg = self.lngamma(T, x)
        al = [self.alpha_i(T, i) for i in range(2)]
        gE = mp.fsum(x[i] * lg[i] for i in range(2))
        am = mp.fsum(x[i] * al[i] for i in range(2)) + (gE + mp.fsum(x[i] * mp.log(b / self.b[i]) for i in range(2))) / self.A1
        abar = [al[i] + (lg[i] + mp.log(b / self.b[i]) + self.b[i] / b - 1) / self.A1 for i in range(2)]
        return b, am, abar

    def lnphi(self, T, P, x, root):
        b, am, abar = self.mix(T, x)
        B = b * P / (self.R * T)
        A = am * B
        zs = [z.real for z in mp.polyroots([1, -1, A - B - B ** 2, -A * B], maxsteps=200, extraprec=60)
              if abs(z.imag) < mp.mpf(10) ** -20 and z.real > B]
        Z = min(zs) if root == "liquid" else max(zs)
        return [self.b[i] / b * (Z - 1) - mp.log(Z - B) - abar[i] * mp.log(1 + B / Z) for i in range(2)]

    def bubble(self, T, x, P0, y0):
        T, x = mp.mpf(T), [mp.mpf(v) for v in x]

        def res(lnP, y1):
            P = mp.exp(lnP)
            y = [y1, 1 - y1]
            fl, fv = self.lnphi(T, P, x, "liquid"), self.lnphi(T, P, y, "vapor")
            return [mp.log(x[i]) + fl[i] - mp.log(y[i]) - fv[i] for i in range(2)]
        sol = mp.findroot(res, (mp.log(P0), mp.mpf(y0)), tol=mp.mpf(10) ** -24)
        return float(mp.exp(sol[0])), float(sol[1])

    def helmholtz(self, T, v, x1):
        x = [x1, 1 - x1]
        b, am, _ = self.mix(T, x)
        return (-mp.log(1 - b / v) - am * mp.log(1 + b / v)
                + x[0] * mp.log(x[0] / v) + x[1] * mp.log(x[1] / v))

    def critical(self, x1, T0, v0):
        """Reid and Beegle (AIChE J. 23 (1977) 726): W = a_vv a_xx - a_vx^2 = 0 and a_vv W_x - a_vx W_v = 0."""
        x1 = mp.mpf(x1)

        def res(T, lv):
            v = mp.exp(lv)
            f = lambda vv, xx: self.helmholtz(T, vv, xx)
            d = {o: mp.diff(f, (v, x1), o) for o in ((2, 0), (0, 2), (1, 1), (3, 0), (2, 1), (1, 2), (0, 3))}
            W = d[(2, 0)] * d[(0, 2)] - d[(1, 1)] ** 2
            Wv = d[(3, 0)] * d[(0, 2)] + d[(2, 0)] * d[(1, 2)] - 2 * d[(1, 1)] * d[(2, 1)]
            Wx = d[(2, 1)] * d[(0, 2)] + d[(2, 0)] * d[(0, 3)] - 2 * d[(1, 1)] * d[(1, 2)]
            sc = d[(2, 0)] * d[(0, 2)]
            return [W / sc, (d[(2, 0)] * Wx - d[(1, 1)] * Wv) / (sc * d[(0, 2)] / v)]
        T, lv = mp.findroot(res, (mp.mpf(T0), mp.log(v0)), tol=mp.mpf(10) ** -18)
        v = mp.exp(lv)
        b, am, _ = self.mix(T, [x1, 1 - x1])
        P = self.R * T / (v - b) - am * self.R * T * b / (v * (v + b))
        return float(T), float(v), float(P)


# --- tests ------------------------------------------------------------------------------------------------------
class ConstantsAndPureLimits(unittest.TestCase):
    def test_srk_constants_from_critical_conditions(self):
        oa, ob, zc = psrk.srk_constants()
        c = 2 ** (1 / 3) - 1
        self.assertAlmostEqual(oa, 1 / (9 * c), delta=1e-14)
        self.assertAlmostEqual(ob, c / 3, delta=1e-15)
        self.assertAlmostEqual(zc, 1 / 3, delta=1e-14)
        self.assertAlmostEqual(psrk.A1, -0.64663, delta=5e-6)          # published rounded value

    def test_co2_ancillary_against_span_wagner(self):
        rec = psrk_data.record(CO2)
        self.assertLess(abs(rec.psat(216.592) / 0.51795e6 - 1), 5e-5)  # triple point
        self.assertLess(abs(rec.psat(273.15) / 3.4851e6 - 1), 5e-5)

    def test_mathias_copeman_reproduces_each_vapour_pressure_record(self):
        limits = {CO2: 0.003, ETOH: 0.006, MEOH: 0.005, TOL: 0.009, WATER: 0.011}
        for cas, lim in limits.items():
            c1, c2, c3, lo, hi, dev = psrk.mathias_copeman(cas)
            rec = psrk_data.record(cas)
            err = max(abs(psrk.pure_saturation(cas, T) / rec.psat(T) - 1) for T in np.linspace(lo, hi, 13))
            self.assertLess(err, lim, cas)
            self.assertLess(dev, 2e-3, cas)

    def test_co2_alpha_against_published_psrk_constants(self):
        c = psrk.mathias_copeman(CO2)
        for T in np.linspace(217.0, 304.0, 12):
            t = 1 - math.sqrt(T / 304.1282)
            ours = (1 + c[0] * t + c[1] * t * t + c[2] * t ** 3) ** 2
            pub = (1 + 0.8252 * t + 0.2515 * t * t - 1.7039 * t ** 3) ** 2
            self.assertLess(abs(ours / pub - 1), 2.5e-3, T)

    def test_pure_component_critical_point_is_the_record(self):
        eos = eos_of(MEOH)
        p = psrk.critical_points(eos, np.array([1.0]))[0]
        self.assertLess(abs(p["T"] / eos.Tc[0] - 1), 1e-9)
        self.assertLess(abs(p["P"] / eos.Pc[0] - 1), 1e-7)


class MixingRuleAndDerivatives(unittest.TestCase):
    def setUp(self):
        self.eos = eos_of(CO2, ETOH)

    def test_unifac_and_attraction_against_thermo(self):
        from thermo.eos_mix import PSRK
        from thermo.unifac import PSRKIP, PSRKSG, UNIFAC
        e = self.eos
        for T, x in ((290.0, [0.3, 0.7]), (300.0, [0.8, 0.2]), (250.0, [0.05, 0.95])):
            ge = UNIFAC.from_subgroups(T=T, xs=x, chemgroups=[{117: 1}, {1: 1, 2: 1, 14: 1}], subgroups=PSRKSG,
                                       interaction_data=PSRKIP, version=0)
            np.testing.assert_allclose(e.gE.lngamma(T, np.array(x)), np.log(ge.gammas()), rtol=0, atol=1e-13)
            ac = [[*e.mc[i][::-1].tolist(), 1.0] for i in range(2)]
            th = PSRK(Tcs=e.Tc.tolist(), Pcs=e.Pc.tolist(), omegas=e.omega.tolist(), zs=x, alpha_coeffs=ac,
                      ge_model=ge, T=T, P=1e6)
            b = float(np.dot(x, e.b))
            self.assertLess(abs(b / th.b - 1), 5e-11)             # thermo's SRK Omega_b is rounded at 2e-11
            a = float(e.alpha_mix(T, np.array(x))) * b * psrk.R * T
            self.assertLess(abs(a / th.a_alpha - 1), 1e-9)

    def test_pure_limit_of_the_mixing_rule(self):
        T = 320.0
        for i in range(2):
            n = np.zeros(2)
            n[i] = 1.0
            self.assertAlmostEqual(float(self.eos.alpha_mix(T, n)), float(self.eos.alpha_pure(T)[i]), delta=1e-13)

    def test_gradient_against_complex_step_of_F(self):
        h = 1e-30
        for T, V, n in ((333.15, 2e-4, [0.3, 0.7]), (400.0, 1e-3, [0.9, 0.1]), (300.0, 7e-5, [0.02, 0.98])):
            n = np.array(n)
            Fni, FV, FT = self.eos.gradient(T, V, n)
            cs = [np.imag(self.eos.F(T, V, n + 1j * h * np.eye(2)[k])) / h for k in range(2)]
            np.testing.assert_allclose(Fni, cs, rtol=1e-13, atol=1e-14)
            self.assertLess(abs(FV / (np.imag(self.eos.F(T, V + 1j * h * V, n)) / (h * V)) - 1), 1e-13)
            dT = 1e-4 * T
            fd = (float(self.eos.F(T + dT, V, n)) - float(self.eos.F(T - dT, V, n))) / (2 * dT)
            self.assertLess(abs(FT / fd - 1), 1e-7)

    def test_consistency_identities(self):
        e = self.eos
        T, P, x = 333.15, 6e6, np.array([0.33, 0.67])
        for root in ("liquid", "vapor"):
            ph = e.phase(T, P, x, root)
            Z = ph["Z"]
            D = e.dlnphi_dn(T, P, x, Z)
            self.assertLess(np.max(np.abs(x @ D)), 1e-12)                       # Gibbs-Duhem
            self.assertLess(np.max(np.abs(D - D.T)), 1e-12)                     # symmetry
            hr, sr, gr = e.residual_TP(T, P, x, Z)

            def g(TT, PP):
                zs = e.z_roots(TT, PP, x)
                ZZ = zs[0] if root == "liquid" else zs[-1]
                return float(np.dot(x, e.ln_phi_Z(TT, PP, x, ZZ)))
            dP = 1e-5 * P
            self.assertLess(abs((g(T, P + dP) - g(T, P - dP)) / (2 * dP) / ((Z - 1) / P) - 1), 1e-7)
            dT = 1e-5 * T
            self.assertLess(abs((g(T + dT, P) - g(T - dT, P)) / (2 * dT) / (-hr / (psrk.R * T * T)) - 1), 1e-6)


class IndependentMpmathPSRK(unittest.TestCase):
    def test_bubble_point_against_mpmath(self):
        eos = eos_of(CO2, ETOH)
        x = np.array([0.3317, 0.6683])
        p = psrk.bubble_pressure(eos, 333.15, x)
        P_mp, y_mp = MpPSRK(eos).bubble(333.15, x, p["P"] * 1.01, float(p["y"][0]) * 0.999)
        self.assertLess(abs(p["P"] / P_mp - 1), 1e-10)
        self.assertLess(abs(float(p["y"][0]) - y_mp), 1e-10)
        self.assertLess(p["certificate"]["fugacity"], 1e-10)

    def test_critical_point_against_mpmath_reid_beegle(self):
        eos = eos_of(CO2, MEOH)
        pts = psrk.critical_points(eos, np.array([0.3, 0.7]), **KAPPA)
        self.assertEqual(len(pts), 1)
        p = pts[0]
        T_mp, v_mp, P_mp = MpPSRK(eos).critical(0.3, p["T"] * 1.002, p["V"] * 1.01)
        self.assertLess(abs(p["T"] - T_mp), 1e-6)
        self.assertLess(abs(p["P"] / P_mp - 1), 1e-7)
        self.assertLess(abs(p["V"] / v_mp - 1), 1e-6)


class ElevatedPressureVLEAgainstExperiment(unittest.TestCase):
    """PSRK is predictive here (no k_ij, no fitted binary parameter): deviations are the model's, recorded."""

    def _check(self, cas, data, aard_max, max_max, y_max=None, rejected=()):
        devs, rej = bubble_deviations(eos_of(CO2, cas), data)
        self.assertEqual([(T, x, c) for T, x, c, _ in rej], list(rejected))
        self.assertEqual(len(devs) + len(rej), len(data))
        rel = [d[3] / d[2] - 1 for d in devs]
        aard = float(np.mean(np.abs(rel)))
        self.assertLess(aard, aard_max)
        self.assertLess(float(np.max(np.abs(rel))), max_max)
        for d in devs:
            self.assertGreater(d[3], 1e6)                       # elevated pressure: every point above 1 MPa
        if y_max is not None:
            dy = max(abs(d[5] - d[4]) for d in devs)
            self.assertLess(dy, y_max)
        return aard, rel

    def test_co2_methanol(self):
        aard, _ = self._check(MEOH, NAIDOO_2008_MEOH, 0.05, 0.14, y_max=0.04)
        self.assertGreater(aard, 0.03)

    def test_co2_toluene(self):
        aard, _ = self._check(TOL, NAIDOO_2008_TOL, 0.055, 0.15, y_max=0.03)
        self.assertGreater(aard, 0.04)

    def test_co2_ethanol_is_overpredicted_by_psrk(self):
        # Located finding over all 36 measured points: 35 are published and every one is over-predicted, +9.7 % to
        # +64.7 % (AARD 21.8 %); x = 0.77 at 363.15 K (14.15 MPa measured) lies in PSRK's unresolved near-critical
        # neighbourhood (|y - x| < 1e-3 from x = 0.767) and is a located rejection.
        aard, rel = self._check(ETOH, SIMA_2011_ETOH_BUBBLE, 0.225, 0.66,
                                rejected=[(363.15, 0.77, "near_critical_unresolved")])
        self.assertGreater(aard, 0.21)
        self.assertGreater(min(rel), 0.09)
        self.assertGreater(max(rel), 0.64)


class CriticalLociAgainstExperiment(unittest.TestCase):
    """Heidemann-Khalil critical points of the PSRK F (verified above against mpmath) against measured lines."""

    def _locus(self, cas, data):
        loc, rej = psrk.critical_locus(eos_of(CO2, cas), [d[0] for d in data], **KAPPA)
        ref = {d[0]: d for d in data}
        return [(x1, p["T"] - ref[x1][1], p["P"] / (ref[x1][2] * 1e3) - 1, p) for x1, p, _ in loc], rej

    def test_co2_methanol_alcohol_branch(self):
        # Liu et al. 2003, x_CO2 <= 0.5: PSRK over-predicts T_c by 0.3-9 K and P_c by 6-21 %.
        sel = [d for d in LIU_2003_MEOH_CRITICAL if d[0] in (0.072, 0.169, 0.327, 0.495)]
        loc, rej = self._locus(MEOH, sel)
        self.assertEqual(rej, [])
        for x1, dT, dP, _ in loc:
            self.assertTrue(0.0 < dT < 10.0, (x1, dT))
            self.assertTrue(0.05 < dP < 0.22, (x1, dP))

    def test_co2_methanol_co2_end_and_interrupted_locus(self):
        sel = [d for d in LIU_2003_MEOH_CRITICAL if d[0] in (0.81, 0.965)]
        loc, rej = self._locus(MEOH, sel)
        self.assertEqual([x for x, *_ in loc], [0.965])
        self.assertLess(abs(loc[0][1]), 4.0)                     # 3.2 K
        self.assertLess(abs(loc[0][2]), 0.05)                    # 3.0 %
        # measured 374.3 K, 15.07 MPa; PSRK's only root is at negative pressure: located rejection
        self.assertEqual(len(rej), 1)
        self.assertEqual((rej[0]["x1"], rej[0]["cause"]), (0.81, "no_critical_point_in_window"))
        self.assertEqual([r["reason"] for r in rej[0]["rejected"]], ["non_positive_pressure"])

    def test_co2_ethanol_co2_rich_branch(self):
        # Sima et al. 2011: x_CO2 0.892-0.931 within 7 K and 10 %; 0.8315-0.8507 has no PSRK critical point.
        sel = [d for d in SIMA_2011_ETOH_CRITICAL if d[0] in (0.8315, 0.892, 0.931)]
        loc, rej = self._locus(ETOH, sel)
        self.assertEqual([x for x, *_ in loc], [0.892, 0.931])
        for x1, dT, dP, _ in loc:
            self.assertLess(abs(dT), 7.5, x1)
            self.assertLess(abs(dP), 0.10, x1)
        self.assertEqual([(r["x1"], r["cause"]) for r in rej], [(0.8315, "no_critical_point_in_window")])

    def test_isotherm_end_brackets_the_critical_locus(self):
        # The 373.15 K bubble isotherm of CO2 + methanol ends where the critical locus crosses 373.15 K.
        eos = eos_of(CO2, MEOH)
        pts, rej = psrk.bubble_isotherm(eos, 373.15, np.linspace(0.36, 0.74, 39))
        x_last, x_rej, at = pts[-1]["x"][0], rej[0]["x"][0], rej[0]["at"]
        self.assertEqual(rej[0]["cause"], "near_critical_unresolved")
        self.assertGreater(float(pts[-1]["y"][0]), x_last + psrk.TOL_NEAR_CRITICAL)
        Tl = psrk.critical_points(eos, np.array([x_last, 1 - x_last]), **KAPPA)[0]["T"]
        Tr = psrk.critical_points(eos, np.array([x_rej, 1 - x_rej]), **KAPPA)[0]["T"]
        self.assertTrue(Tr < 373.15 < Tl, (x_last, Tl, x_rej, Tr))
        # the trace stops where the critical locus, interpolated linearly in x, crosses 373.15 K (x_c = 0.70866)
        x_c = x_last + (x_rej - x_last) * (Tl - 373.15) / (Tl - Tr)
        self.assertLess(abs(at - x_c), 1e-3, (at, x_c))


class LocatedRejections(unittest.TestCase):
    def test_species_without_record(self):
        with self.assertRaises(CubicOutOfScope) as cm:
            psrk.PSRKMixture((CO2, "74-82-8"))
        self.assertEqual(cm.exception.datos["cause"], "no_pure_record")

    def test_missing_psrk_interaction(self):
        with self.assertRaises(CubicOutOfScope) as cm:
            psrk.PSRKUnifac(("g", "a"), {"g": {117: 1}, "a": {28: 1}})          # CO2 with CH3NH2
        self.assertEqual(cm.exception.datos["cause"], "missing_interaction")
        self.assertEqual(sorted(cm.exception.datos["main_groups"]), [14, 56])

    def test_temperature_below_alpha_regression(self):
        eos = eos_of(CO2, TOL)
        with self.assertRaises(CubicOutOfScope) as cm:
            psrk.bubble_pressure(eos, 250.0, np.array([0.2, 0.8]))
        self.assertEqual(cm.exception.datos["cause"], "alpha_below_fit_range")
        self.assertEqual(cm.exception.datos["species"], [TOL])

    def test_supercritical_state_has_no_bubble_point(self):
        eos = eos_of(CO2, MEOH)
        with self.assertRaises(CubicOutOfScope) as cm:          # T above the whole critical locus at x = 0.3
            psrk.bubble_pressure(eos, 500.0, np.array([0.3, 0.7]))
        # Newton fails from Wilson and from every damped probe: located `not_converged` with the probes listed
        self.assertEqual(cm.exception.datos["cause"], "not_converged")
        self.assertEqual([p["scale"] for p in cm.exception.datos["probes"]], list(psrk.PROBE_LNK_SCALES))
        self.assertFalse(any(p["converged"] for p in cm.exception.datos["probes"]))

    def test_caloric_properties_need_an_ideal_gas_record(self):
        eos = eos_of(CO2, ETOH)
        x = np.array([0.5, 0.5])
        with self.assertRaises(CubicOutOfScope) as cm:
            eos.molar_props(320.0, 5e6, x, eos.phase(320.0, 5e6, x)["Z"])
        self.assertEqual(cm.exception.datos["cause"], "no_ideal_gas_record")


if __name__ == "__main__":
    unittest.main()
