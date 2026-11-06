"""F9-R13 (5 November 2026 reliability sweep): IAPWS-95 saturation within micro-kelvins of T_c and the exact
critical point, core/agua_iapws95.py.

Defect: `saturacion` accepted the unrefined `chemicals` fits within ~1e-11 K of T_c because the Maxwell residual is
blind where P and g are flat; their density gap followed a log-log slope of 1.0 instead of the coexistence curve,
and the band ~3e-11..3.4e-9 K was rejected between two accepted bands. `evaluar_TV(T_c, 1/rho_c)` and
`propiedades(T_c, rho_c)` raised a raw ZeroDivisionError.

Independent reference (no code of the module or of `chemicals`): the IAPWS-95 residual Helmholtz energy written
here from the coefficient table of IAPWS R6-95(2018), Table 2, evaluated in mpmath (50 digits); its delta
derivatives by mpmath differentiation. The transcription is checked against the R6-95 Table 6 values at 500 K,
838.025 kg/m3. The Maxwell conditions P(rho') = P(rho''), g(rho') = g(rho'') at the module's binary64 T are solved
by Newton in that precision. Facts this reference establishes (5 November 2026):
  * the coexisting density gap follows d ln(rho' - rho'') / d ln(T_c - T) = 0.465 at 1e-3 K, 0.495 at 1e-5 K and
    0.4999 at 1e-8 K (the mean-field exponent 1/2 of this analytic-like EOS), then steepens (0.52 at 3e-10 K,
    0.81 at 3e-11 K) because IAPWS-95's own critical temperature lies about 1.9e-11 K below 647.096 K: min over
    rho of (dP/drho)_T changes sign between T_c - 2e-11 K and T_c - 1.5e-11 K. Closer to 647.096 K there is no
    coexistence in the EOS at all;
  * in binary64 the fits reach a relative density-gap error of about 5e-15 / s, s = rho (dP/drho)_T / Psat,
    from 1e-2 to 1e-7 K (fit breakdown below), so a state is resolvable to SATURATION_GAP_RTOL = 1e-5 only for
    s >= 1e-9, about 1.1e-7 K below T_c.
Also the published IAPWS-95 saturation values of R6-95 Table 8 (275, 450, 625 K).

Negative control: tests 1-4 fail against the code before the repair (commit b6eb986). Test 5 guards the
unchanged results; its negative control is a mutation (SATURATION_MIN_STIFFNESS = 1e-4 rejects T_c - 1e-3 K).
Run from the repository root (about 10 s):
    python tests/test_iapws95_critical_reliability.py
"""
from functools import lru_cache
import math
from pathlib import Path
import sys
import unittest
import warnings

import mpmath as mp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import agua_iapws95 as w

warnings.filterwarnings('ignore')
mp.mp.dps = 50

# ---------------------------------------------------------------- independent IAPWS-95 residual part (R6-95 Table 2)
_POLY = ((1, '-0.5', '0.12533547935523e-1'), (1, '0.875', '0.78957634722828e1'), (1, '1', '-0.87803203303561e1'),
         (2, '0.5', '0.31802509345418'), (2, '0.75', '-0.26145533859358'), (3, '0.375', '-0.78199751687981e-2'),
         (4, '1', '0.88089493102134e-2'))
_EXPO = ((1, 1, 4, '-0.66856572307965'), (1, 1, 6, '0.20433810950965'), (1, 1, 12, '-0.66212605039687e-4'),
         (1, 2, 1, '-0.19232721156002'), (1, 2, 5, '-0.25709043003438'), (1, 3, 4, '0.16074868486251'),
         (1, 4, 2, '-0.40092828925807e-1'), (1, 4, 13, '0.39343422603254e-6'), (1, 5, 9, '-0.75941377088144e-5'),
         (1, 7, 3, '0.56250979351888e-3'), (1, 9, 4, '-0.15608652257135e-4'), (1, 10, 11, '0.11537996422951e-8'),
         (1, 11, 4, '0.36582165144204e-6'), (1, 13, 13, '-0.13251180074668e-11'), (1, 15, 1, '-0.62639586912454e-9'),
         (2, 1, 7, '-0.10793600908932'), (2, 2, 1, '0.17611491008752e-1'), (2, 2, 9, '0.22132295167546'),
         (2, 2, 10, '-0.40247669763528'), (2, 3, 10, '0.58083399985759'), (2, 4, 3, '0.49969146990806e-2'),
         (2, 4, 7, '-0.31358700712549e-1'), (2, 4, 10, '-0.74315929710341'), (2, 5, 10, '0.47807329915480'),
         (2, 6, 6, '0.20527940895948e-1'), (2, 6, 10, '-0.13636435110343'), (2, 7, 10, '0.14180634400617e-1'),
         (2, 9, 1, '0.83326504880713e-2'), (2, 9, 2, '-0.29052336009585e-1'), (2, 9, 3, '0.38615085574206e-1'),
         (2, 9, 4, '-0.20393486513704e-1'), (2, 9, 8, '-0.16554050063734e-2'), (2, 10, 6, '0.19955571979541e-2'),
         (2, 10, 9, '0.15870308324157e-3'), (2, 12, 8, '-0.16388568342530e-4'), (3, 3, 16, '0.43613615723811e-1'),
         (3, 4, 22, '0.34994005463765e-1'), (3, 4, 23, '-0.76788197844621e-1'), (3, 5, 23, '0.22446277332006e-1'),
         (4, 14, 10, '-0.62689710414685e-4'), (6, 3, 50, '-0.55711118565645e-9'), (6, 6, 44, '-0.19905718354408'),
         (6, 6, 46, '0.31777497330738'), (6, 6, 50, '-0.11841182425981'))
_GAUSS = ((3, 0, '-0.31306260323435e2', 20, 150, '1.21'), (3, 1, '0.31546140237781e2', 20, 150, '1.21'),
          (3, 4, '-0.25213154341695e4', 20, 250, '1.25'))
_NONAN = (('0.85', '-0.14874640856724', 28, 700), ('0.95', '0.31806110878444', 32, 800))   # a=3.5 B=0.2 A=0.32 beta=0.3
F = mp.mpf
TC, RHOC = F(647.096), F(322)                      # T_c = 647.096 K, rho_c = 322 kg/m3 (R6-95)


def phir(tau, d):
    s = F(0)
    for di, ti, n in _POLY:
        s += F(n) * d ** di * tau ** F(ti)
    for c, di, ti, n in _EXPO:
        s += F(n) * d ** di * tau ** ti * mp.exp(-d ** c)
    for di, ti, n, a, b, g in _GAUSS:
        s += F(n) * d ** di * tau ** ti * mp.exp(-a * (d - 1) ** 2 - b * (tau - F(g)) ** 2)
    for b, n, C, D in _NONAN:
        q = (d - 1) ** 2
        theta = (1 - tau) + F('0.32') * q ** (1 / (2 * F('0.3')))
        delta_ = theta ** 2 + F('0.2') * q ** F('3.5')
        s += F(n) * delta_ ** F(b) * d * mp.exp(-C * q - D * (tau - 1) ** 2)
    return s


def phir_d(tau, d):
    return mp.diff(lambda x: phir(tau, x), d)


def stiffness(tau, d):      # (dP/drho)_T / (R T)
    return 1 + 2 * d * phir_d(tau, d) + d * d * mp.diff(lambda x: phir(tau, x), d, 2)


def pressure(tau, d):       # P / (rho_c R T)
    return d * (1 + d * phir_d(tau, d))


def gibbs(tau, d):          # g / (R T) up to a function of T
    return mp.log(d) + phir(tau, d) + d * phir_d(tau, d)


@lru_cache(maxsize=None)
def reference_coexistence(T, seed):
    """(rho', rho'') of IAPWS-95 at the binary64 temperature T, by Newton from `seed` (delta', delta''); None if
    Newton collapses onto rho_c (no coexistence)."""
    tau = TC / F(T)
    dl, dv = F(seed[0]), F(seed[1])
    for _ in range(40):
        kl, kv = stiffness(tau, dl), stiffness(tau, dv)
        f1, f2 = pressure(tau, dl) - pressure(tau, dv), gibbs(tau, dl) - gibbs(tau, dv)
        a, b, c, d = kl, -kv, kl / dl, -kv / dv
        det = a * d - b * c
        sl, sv = (f1 * d - b * f2) / det, (a * f2 - c * f1) / det
        dl, dv = dl - sl, dv - sv
        if not dl > 1 > dv:
            return None
        if abs(sl) + abs(sv) < F(10) ** -34:
            return dl * RHOC, dv * RHOC
    return None


def reference_gap(T, s):
    ref = reference_coexistence(T, (s.rho_l / 322.0, s.rho_v / 322.0))
    return None if ref is None else ref[0] - ref[1]


def eos_has_coexistence(T):
    """min over delta of (dP/drho)_T < 0 near rho_c (the minimum lies at delta - 1 ~ -1.8e-9 for these T)."""
    tau = TC / F(T)
    k = lambda x: stiffness(tau, x)
    x = mp.findroot(lambda y: mp.diff(k, y), F(1) - F('1.8e-9'))
    return k(x) < 0


def accepted(T):
    try:
        return w.saturacion(T)
    except ValueError as error:        # SaturationNotResolvable is a ValueError, as the old rejection was
        return error


GAPS_FAR = (1e-3, 1e-4, 1e-5, 1e-6, 3e-7, 2e-7, 1.2e-7)
GAPS_NEAR = tuple(10.0 ** (-8 - 0.5 * i) for i in range(9))          # 1e-8 .. 1e-12 K
SCAN = tuple(10.0 ** (-1 - 0.1 * i) for i in range(121))             # 1e-1 .. 1e-13 K, log-spaced


class Iapws95CriticalReliability(unittest.TestCase):
    def test_0_reference_transcription_matches_r6_95_table_6(self):
        tau, d = TC / 500, F('838.025') / RHOC
        self.assertAlmostEqual(float(phir(tau, d)), -0.342693206e1, delta=5e-9)
        self.assertAlmostEqual(float(phir_d(tau, d)), -0.364366650, delta=5e-10)
        self.assertAlmostEqual(float(mp.diff(lambda x: phir(tau, x), d, 2)), 0.856063701, delta=5e-10)

    def test_1_density_gap_follows_the_iapws95_coexistence_curve(self):
        """Every accepted state has rho' - rho'' within SATURATION_GAP_RTOL of the reference, and the local log-log
        slope between accepted states matches the reference slope (no slope-1.0 fit band)."""
        previous = None
        n_accepted = 0
        for gap in GAPS_FAR + GAPS_NEAR:
            T = w.TC - gap
            s = accepted(T)
            if isinstance(s, Exception):
                continue
            n_accepted += 1
            with self.subTest(gap=gap):
                if gap < 1e-8:
                    self.assertTrue(eos_has_coexistence(T),
                                    f"accepted saturation at T_c - {gap:g} K, where IAPWS-95 has no coexistence")
                ref = reference_gap(T, s)
                self.assertIsNotNone(ref, f"no reference coexistence near the accepted state at T_c - {gap:g} K")
                self.assertLessEqual(abs((s.rho_l - s.rho_v) / float(ref) - 1), w.SATURATION_GAP_RTOL)
                if previous is not None:
                    g0, d0, r0 = previous
                    slope = math.log((s.rho_l - s.rho_v) / d0) / math.log(gap / g0)
                    slope_ref = float(mp.log(ref / r0) / mp.log(F(gap) / F(g0)))
                    self.assertAlmostEqual(slope, slope_ref, delta=1e-3)
                    self.assertTrue(0.46 < slope_ref < 0.501, slope_ref)
                previous = (gap, s.rho_l - s.rho_v, ref)
        self.assertEqual(n_accepted, len(GAPS_FAR))         # resolvable states are not over-rejected

    def test_2_saturation_is_monotone_and_resolvability_contiguous(self):
        """Accepted gaps form one band ending before T_c; Psat, rho'' rise and rho' falls with T; every rejection is
        located (motivo region_critica)."""
        rows, rejected_at = [], None
        for gap in SCAN:
            T = w.TC - gap
            s = accepted(T)
            if isinstance(s, Exception):
                rejected_at = rejected_at or gap
                with self.subTest(gap=gap):
                    self.assertIsInstance(s, w.FueraDeAlcance)
                    self.assertEqual(s.motivo, 'region_critica')
                continue
            with self.subTest(gap=gap):
                self.assertIsNone(rejected_at, f"accepted at T_c - {gap:g} K after a rejection at {rejected_at} K")
            rows.append((T, s))
        self.assertGreaterEqual(len(rows), 60)          # 1e-1 .. 1.26e-7 K
        for (T0, a), (T1, b) in zip(rows, rows[1:]):
            with self.subTest(T=T1):
                self.assertTrue(T1 > T0 and b.Psat > a.Psat and b.rho_l < a.rho_l and b.rho_v > a.rho_v)

    def test_3_accepted_states_satisfy_maxwell_in_extended_precision(self):
        """P' = P'' and g' = g'' at the returned binary64 densities, evaluated in mpmath and scaled by the loop's own
        pressure scale (dP/drho)_T' (rho' - rho''); the binary64 residual alone (~1e-14) is no evidence."""
        for gap in GAPS_FAR + GAPS_NEAR:
            T = w.TC - gap
            s = accepted(T)
            if isinstance(s, Exception):
                continue
            tau, dl, dv = TC / F(T), F(s.rho_l) / RHOC, F(s.rho_v) / RHOC
            scale = abs(stiffness(tau, dl)) * (dl - dv)
            with self.subTest(gap=gap):
                self.assertLessEqual(s.residuo, 1e-12)
                self.assertLessEqual(float(abs(pressure(tau, dl) - pressure(tau, dv)) / scale),
                                     w.SATURATION_GAP_RTOL)
                self.assertLessEqual(float(abs(gibbs(tau, dl) - gibbs(tau, dv)) / scale),
                                     w.SATURATION_GAP_RTOL)

    def test_4_exact_critical_point_is_a_located_rejection(self):
        for call in (lambda: w.evaluar_TV(w.TC, 1.0 / w.RHOC), lambda: w.propiedades(w.TC, w.RHOC),
                     lambda: w.helmholtz(w.TC, w.RHOC)):
            with self.subTest(call=call):
                with self.assertRaises(w.FueraDeAlcance) as ctx:
                    call()
                self.assertEqual(ctx.exception.motivo, 'region_critica')

    def test_5_results_unchanged_away_from_tc(self):
        # (T_c - T [K], Psat [Pa], rho' [kg/m3], rho'' [kg/m3]) from the module before the repair (commit b6eb986)
        before = (
            (0.001, 22063732.706674796, 327.17546284904034, 316.79670148305576),
            (0.003, 22063198.197395917, 330.6864892313741, 313.23083083412945),
            (0.01, 22061328.13184618, 337.04410422786054, 306.796585037732),
            (0.016, 22059725.96214699, 340.387972615003, 303.4596095608764),
            (0.1, 22037341.324302144, 357.8218479778801, 286.0266564404064),
            (1.0, 21800025.45627908, 400.26211077782915, 245.82476606641157),
            (3.235, 21223498.958236553, 442.6109903235877, 209.3787026024497),
            (10.0, 19572581.579462573, 503.1498247024317, 160.9336961866752),
            (50.0, 11886096.036937943, 657.0805642304682, 69.21687240434058),
            (197.096, 932203.5636282371, 890.3412497616774, 4.812003601256671),
            (372.096, 698.4511667008939, 999.8874061198472, 0.005506649185041187),
        )
        for gap, P, rl, rv in before:
            s = w.saturacion(w.TC - gap)
            with self.subTest(gap=gap):
                for new, old in ((s.Psat, P), (s.rho_l, rl), (s.rho_v, rv)):
                    self.assertLessEqual(abs(new / old - 1), 1e-12)
        # IAPWS R6-95(2018) Table 8: T [K], Psat [MPa], rho' and rho'' [kg/m3], 9 significant digits
        for T, P, rl, rv in ((275.0, 0.698451167e-3, 999.887406, 0.550664919e-2),
                             (450.0, 0.932203564, 890.341250, 4.81200360),
                             (625.0, 16.9082693, 567.090385, 118.290280)):
            s = w.saturacion(T)
            with self.subTest(T=T):
                for new, pub in ((s.Psat / 1e6, P), (s.rho_l, rl), (s.rho_v, rv)):
                    self.assertLessEqual(abs(new / pub - 1), 5e-9)


if __name__ == '__main__':
    unittest.main(verbosity=2)
