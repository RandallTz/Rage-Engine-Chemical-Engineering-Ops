"""
Phase stability, flashes and saturation points of the Peng-Robinson mixture package (F8b, 5 November 2026).

Both phases are the same function F(T, V, n) of core/termodinamica/cubic_eos.py; they differ only in the volume
root. Every evaluation takes the root of least Gibbs energy for its own composition, so no phase label enters
the physics. Labels are assigned afterwards, phase by phase, by the Venkatarathnam-Oellrich identification
parameter (`PIP > 1` liquid-like) for a single phase. A certified split is published as vapour (less dense) +
liquid (denser), as before, unless it is a liquid-liquid split (A1 review PR-1): both phases liquid-like by PIP AND
the less dense phase itself dense, kappa = v / b <= KAPPA_LL kappa_c (the liquid-liquid density limit of
cubic_critical, kappa_c = Z_c / Omega_b = 3.95). Such a split is rejected with `CubicOutOfScope` (cause
`liquid_liquid_split`): the package has one vapour and one liquid candidate, so a liquid-liquid state is never
published as vapour + liquid. PIP alone is not used for splits because the vapour's PIP passes through 1 near a
gas-liquid critical point (methanol + water 0.3/0.7 at 581.0 K, 15.31-15.35 MPa, 0.5 K below its critical
point: light-phase PIP 1.2-5.1 at kappa = 3.95), where the split is a genuine vapour + liquid (A1 repairs review
R1).

Tangent-plane distance on the layer's scale (per R T and per mole of trial phase, core/termodinamica/capa.py):

    tm(w) = sum_i w_i [ln w_i + ln phi_i(w) - ln z_i - ln phi_i(z)],   sum w_i = 1.

Its minima are located by Michelsen's modified function in log amounts W (stationary points coincide):
tm*(W) = 1 + sum W_i (ln W_i + ln phi_i(W) - d_i - 1), gradient W_i (ln W_i + ln phi_i - d_i). Seeds: Wilson
vapour-like and liquid-like, each pure component, and for a binary a 201-point composition scan with both roots,
so a near-critical minimum is not missed. Each seed: successive substitution, then BFGS with the analytic
gradient. A minimum equal to z (trivial solution) is discarded with the layer's composition rule.

TP flash: if every trial has tm >= -TOL_TM the feed is one phase. Otherwise the trial seeds a two-phase split,
refined by successive substitution with Rachford-Rice and then by Newton on the Gibbs energy in vapour amounts
with the analytic Hessian  H = sum over phases of (delta_ij / n_i - 1 / N + d ln phi_i / dn_j). The result is
certified: fugacity equality (|ln f_i^V - ln f_i^L| <= TOL_MU) and a fresh stability test of the split
(min tm >= -TOL_TM). A third phase is not represented here (two candidates): a split that fails certification is
rejected (`CubicOutOfScope`), never published.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import brentq, minimize

from core.termodinamica.cubic_eos import R, CubicOutOfScope, PengRobinsonMixture

TOL_TM = 1e-9
TOL_MU = 1e-10
TOL_SAME = 1e-5
N_ABSENT = 1e-12


def wilson_lnK(eos, T, P):
    return np.log(eos.Pc / P) + 5.373 * (1 + eos.omega) * (1 - eos.Tc / T)


def _lnphi(eos, T, P, w):
    return eos.phase(T, P, w)["lnphi"]


def tm_value(eos, T, P, w, d):
    w = np.asarray(w, dtype=float)
    w = w / w.sum()
    return float(np.sum(w * (np.log(w) + _lnphi(eos, T, P, w) - d)))


def stability(eos, T, P, z):
    """Local minima of tm for feed z: [(w, tm)], plus d = ln z + ln phi(z)."""
    z = np.asarray(z, dtype=float)
    z = z / z.sum()
    d = np.log(z) + _lnphi(eos, T, P, z)
    nc = len(z)
    lnK = wilson_lnK(eos, T, P)
    seeds = [z * np.exp(lnK), z * np.exp(-lnK)]
    for i in range(nc):
        e = np.full(nc, 1e-3)
        e[i] = 1.0
        seeds.append(e)
    if nc == 2:
        grid = np.linspace(1e-4, 1 - 1e-4, 201)
        best = None
        vals = []
        for a in grid:
            w = np.array([a, 1 - a])
            vals.append(tm_value(eos, T, P, w, d))
        vals = np.array(vals)
        for k in range(1, len(grid) - 1):
            if vals[k] <= vals[k - 1] and vals[k] <= vals[k + 1]:
                seeds.append(np.array([grid[k], 1 - grid[k]]))
    found = []
    for W0 in seeds:
        W = np.asarray(W0, dtype=float)
        W = W / W.sum()
        # successive substitution
        for _ in range(30):
            Wn = np.exp(d - _lnphi(eos, T, P, W / W.sum()))
            if np.max(np.abs(np.log(Wn) - np.log(W))) < 1e-10:
                W = Wn
                break
            W = Wn

        def fun(u):
            Wu = np.exp(u)
            lp = _lnphi(eos, T, P, Wu / Wu.sum())
            g = Wu * (u + lp - d)
            return float(1 + np.sum(Wu * (u + lp - d - 1))), g
        r = minimize(fun, np.log(W), jac=True, method="BFGS", options={"gtol": 1e-12, "maxiter": 400})
        w = np.exp(r.x)
        w = w / w.sum()
        tm = tm_value(eos, T, P, w, d)
        if np.max(np.abs(w - z)) < TOL_SAME:
            continue
        if any(np.max(np.abs(w - f[0])) < TOL_SAME for f in found):
            continue
        found.append((w, tm))
    return found, d


def rachford_rice(z, K):
    f = lambda b: float(np.sum(z * (K - 1) / (1 + b * (K - 1))))
    if not (K.max() > 1 > K.min()):
        raise CubicOutOfScope("Rachford-Rice has no root: all K on one side of 1.", cause="no_rachford_rice_root")
    lo = 1 / (1 - K.max())              # negative-flash window (Whitson and Michelsen 1989)
    hi = 1 / (1 - K.min())
    eps = 1e-12 * (hi - lo)
    return brentq(f, lo + eps, hi - eps, xtol=1e-16, rtol=1e-15, maxiter=500)


def _ln_f(eos, T, P, n):
    N = n.sum()
    x = n / N
    ph = eos.phase(T, P, x)
    return np.log(x) + ph["lnphi"], ph


def split_TP(eos, T, P, z, w_trial):
    """Two-phase split seeded by an unstable trial composition. Returns (beta_V, y, x, phases)."""
    z = np.asarray(z, dtype=float)
    z = z / z.sum()
    lnphi_z = _lnphi(eos, T, P, z)
    K = np.asarray(w_trial) / z
    K = np.where(np.abs(np.log(K)) < 1e-6, np.exp(np.sign(np.log(K) + 1e-30) * 1e-6), K)
    for _ in range(25):
        beta = rachford_rice(z, K)
        x = z / (1 + beta * (K - 1))
        y = K * x
        Kn = np.exp(_lnphi(eos, T, P, x / x.sum()) - _lnphi(eos, T, P, y / y.sum()))
        if np.max(np.abs(np.log(Kn) - np.log(K))) < 1e-8:
            K = Kn
            break
        K = Kn
    beta = rachford_rice(z, K)
    x = z / (1 + beta * (K - 1))
    v = beta * K * x                     # vapour (or second-phase) amounts, total feed 1
    # Newton on G(v) with analytic Hessian and a step cut that keeps every amount positive
    for _ in range(50):
        l = z - v
        lfV, phV = _ln_f(eos, T, P, v)
        lfL, phL = _ln_f(eos, T, P, l)
        g = lfV - lfL
        if np.max(np.abs(g)) < 1e-13:
            break
        HV = np.diag(1 / v) - 1 / v.sum() + eos.dlnphi_dn(T, P, v / v.sum(), phV["Z"]) / v.sum()
        HL = np.diag(1 / l) - 1 / l.sum() + eos.dlnphi_dn(T, P, l / l.sum(), phL["Z"]) / l.sum()
        try:
            dv = np.linalg.solve(HV + HL, -g)
        except np.linalg.LinAlgError:
            raise CubicOutOfScope("Singular two-phase Hessian (critical point of the split).",
                                  cause="singular_split_hessian", T=T, P=P)
        t = 1.0
        while np.any(v + t * dv <= 0) or np.any(z - v - t * dv <= 0):
            t *= 0.5
            if t < 1e-12:
                raise CubicOutOfScope("Two-phase Newton step left the amount simplex.", cause="not_converged",
                                      T=T, P=P)
        v = v + t * dv
    l = z - v
    beta = float(v.sum())
    return beta, v / v.sum(), l / l.sum()


def _kappa_ll():
    """Reduced-volume limit v/b of a dense (liquid-liquid) phase, shared with cubic_critical (PR-2)."""
    from core.termodinamica import cubic_critical
    return cubic_critical.KAPPA_LL * cubic_critical.kappa_c()


def _pip(eos, T, P, x, Z):
    return float(eos.phase_identification(T, Z * R * T / P, x))


def _label_single(eos, T, P, x, Z):
    """Physical label of one phase: Venkatarathnam-Oellrich PIP > 1 liquid-like, otherwise vapour-like."""
    return "liquido" if _pip(eos, T, P, x, Z) > 1 else "vapor"


def flash_TP(eos, T, P, z):
    """Certified TP state: {'phases': [...], 'tm_min', 'mu_residual', 'trials'}."""
    z = np.asarray(z, dtype=float)
    ntot = float(z.sum())
    zn = z / ntot
    trials, d = stability(eos, T, P, zn)
    tm_min = min([t[1] for t in trials], default=math.inf)
    if tm_min >= -TOL_TM:
        ph = eos.phase(T, P, zn)
        props = eos.molar_props(T, P, zn, ph["Z"])
        lab = _label_single(eos, T, P, zn, ph["Z"])
        return {"phases": [dict(kind=lab, n=ntot, x=zn, **props)], "tm_min": tm_min, "mu_residual": 0.0,
                "trials": trials, "d": d}
    w = min(trials, key=lambda t: t[1])[0]
    beta, y, x = split_TP(eos, T, P, zn, w)
    if not (N_ABSENT < beta < 1 - N_ABSENT):
        raise CubicOutOfScope(f"Split collapsed to one phase at T = {T:.6g} K, P = {P:.6g} Pa.",
                              cause="split_collapsed", T=T, P=P)
    pv = eos.phase(T, P, y)
    pl = eos.phase(T, P, x)
    res_mu = float(np.max(np.abs((np.log(y) + pv["lnphi"]) - (np.log(x) + pl["lnphi"]))))
    cert, _ = stability(eos, T, P, x)
    tm_cert = min([t[1] for t in cert if np.max(np.abs(t[0] - y)) > TOL_SAME], default=math.inf)
    if res_mu > TOL_MU or tm_cert < -TOL_TM:
        raise CubicOutOfScope(f"Two-phase state at T = {T:.6g} K, P = {P:.6g} Pa not certified "
                              f"(mu {res_mu:.3g}, tm {tm_cert:.3g}); a third phase is outside this package.",
                              cause="third_phase" if tm_cert < -TOL_TM else "not_certified", T=T, P=P,
                              mu_residual=res_mu, tm=tm_cert)
    a = eos.molar_props(T, P, y, pv["Z"])
    b = eos.molar_props(T, P, x, pl["Z"])
    # Order by density (less dense first). Density alone cannot tell a vapour from the lighter of two liquids
    # (benzene + water at 320 K and 1 bar: PIP 11 and 14, kappa 1.1-1.2), so a split whose phases are both
    # liquid-like AND whose lighter phase is dense is rejected as liquid-liquid (A1 review PR-1; density guard
    # from the A1 repairs review R1, see the module docstring).
    if a["v"] < b["v"]:
        a, b, y, x, beta = b, a, x, y, 1 - beta
    pip = [_pip(eos, T, P, y, a["Z"]), _pip(eos, T, P, x, b["Z"])]
    kappa = [a["v"] / float(np.dot(y, eos.b)), b["v"] / float(np.dot(x, eos.b))]
    if pip[0] > 1 and pip[1] > 1 and kappa[0] <= _kappa_ll():
        raise CubicOutOfScope(
            f"Certified two-phase state at T = {T:.6g} K, P = {P:.6g} Pa is a liquid-liquid split "
            f"(phase-identification parameters {pip[0]:.4g} and {pip[1]:.4g}, > 1 liquid-like; reduced volumes "
            f"v/b = {kappa[0]:.4g} and {kappa[1]:.4g} <= {_kappa_ll():.4g}): this package publishes only vapour + "
            "liquid (candidates vapor-1, liquido-1); a liquid-liquid split needs a second liquid candidate, which "
            "this package does not have.",
            cause="liquid_liquid_split", T=T, P=P, z=zn.tolist(), compositions=[y.tolist(), x.tolist()],
            Z=[a["Z"], b["Z"]], PIP=pip, kappa=kappa)
    return {"phases": [dict(kind="vapor", n=beta * ntot, x=y, **a), dict(kind="liquido", n=(1 - beta) * ntot,
                                                                          x=x, **b)],
            "tm_min": tm_cert, "mu_residual": res_mu, "trials": trials, "d": d}


def _bracketed_root(f, lo, hi, what, state, **kw):
    """brentq on [lo, hi] after checking the bracket; a state outside it is a located CubicOutOfScope
    (cause `outside_bracket`, A1 review PR-4), never scipy's raw ValueError."""
    flo, fhi = f(lo), f(hi)
    if flo == 0.0:
        return lo
    if fhi == 0.0:
        return hi
    if not (math.isfinite(flo) and math.isfinite(fhi)) or flo * fhi > 0.0:
        raise CubicOutOfScope(f"{what}: the specified state lies outside the searched bracket [{lo:.6g}, {hi:.6g}] "
                              f"(residuals {flo:.6g} and {fhi:.6g} at its ends).", cause="outside_bracket",
                              bracket=[lo, hi], residuals=[flo, fhi], **state)
    return brentq(f, lo, hi, **kw)


N_WINDOW_SCAN = 25       # T grid of the default PH and UV bracket searches
N_WINDOW_BISECT = 20     # bisections per end of an evaluable T window (grid step / 2^20, ~3e-5 K)
N_LL_BISECT = 40         # bisections in ln P towards the non-evaluable high-pressure side of one UV isotherm
N_UV_SCAN, N_UV_BISECT = N_WINDOW_SCAN, N_WINDOW_BISECT     # earlier names (A1 repairs review R3)


def _probe(fn):
    """(fn(), None), or (None, cause) when fn raises a located CubicOutOfScope. A bracket search treats such a
    state as non-evaluable: the package has one vapour and one liquid candidate, so a certified liquid-liquid
    split (`liquid_liquid_split`), a split that a third phase destabilizes (`third_phase`) or a split that does
    not converge cannot be published there. The cause is kept as the label of that side; the published result is
    always a fresh certified flash at the root, never a probe."""
    try:
        return fn(), None
    except CubicOutOfScope as e:
        return None, str(e.datos.get("cause") or "unlocated")


def _windows(side, lo, hi, s_lo, s_hi, what, state):
    """Evaluable temperature windows of a default PH or UV bracket [lo, hi].

    side(T) is 0 when the specified state can be sought at T and otherwise a label: the cause of a non-evaluable
    probe (for example `liquid_liquid_split`), or for UV -1/+1 (the volume needs P below/above the P bracket). The
    sides are taken on an N_WINDOW_SCAN-point grid; every run of grid points with side 0 becomes one window, each
    end refined by N_WINDOW_BISECT bisections against its neighbour. Returns [(T_a, T_b, side below, side above,
    interior grid points)], a neighbour side being None at a bracket end."""
    grid = np.linspace(lo, hi, N_WINDOW_SCAN)
    if s_lo == 0 and s_hi == 0:
        return [(lo, hi, None, None, [float(T) for T in grid[1:-1]])]
    sides = [s_lo] + [side(float(T)) for T in grid[1:-1]] + [s_hi]
    if 0 not in sides:
        causes = [s for s in sides if isinstance(s, str)]
        raise CubicOutOfScope(
            f"{what}: no temperature in [{lo:.6g}, {hi:.6g}] K at which the state is evaluable (sides on a "
            f"{N_WINDOW_SCAN}-point grid: {sides}).",
            cause=causes[0] if causes else "outside_bracket", bracket=[lo, hi], sides=sides, **state)

    def refine(bad, good):
        for _ in range(N_WINDOW_BISECT):
            mid = 0.5 * (bad + good)
            if side(mid) == 0:
                good = mid
            else:
                bad = mid
        return good
    out, k, last = [], 0, len(grid) - 1
    while k <= last:
        if sides[k] != 0:
            k += 1
            continue
        k0 = k
        while k + 1 <= last and sides[k + 1] == 0:
            k += 1
        Ta = float(grid[k0]) if k0 == 0 else refine(float(grid[k0 - 1]), float(grid[k0]))
        Tb = float(grid[k]) if k == last else refine(float(grid[k + 1]), float(grid[k]))
        inside = [float(T) for T in grid[k0:k + 1] if Ta < T < Tb]
        out.append((Ta, Tb, None if k0 == 0 else sides[k0 - 1], None if k == last else sides[k + 1], inside))
        k += 1
    return out


def _root_on_windows(f, f_probe, windows, what, state, **kw):
    """T at which f(T) = 0 on the evaluable windows of _windows.

    f increases with T (H at fixed P, U at fixed V, by positive heat capacities on the stable states), so at most
    one window brackets the root. f_probe(T) is (value, None) or (None, cause). A window end at which the full
    residual is not evaluable (for UV the side test sees only the two P ends) is replaced by the nearest
    evaluable grid point inside the window; when the root lies between that point and the failing one, the edge
    is bisected (N_WINDOW_BISECT). Without a bracketing window, the root lies in a gap or beyond a bracket end and
    the label of that side locates the rejection: its cause (for example `liquid_liquid_split`: the true state is
    a split this package cannot publish), or `outside_bracket` at a bracket end or a -1/+1 side. A single window
    spanning the bracket is the plain search, unchanged."""
    single = len(windows) == 1 and windows[0][2] is None and windows[0][3] is None
    if single and f_probe(windows[0][0])[1] is None and f_probe(windows[0][1])[1] is None:
        return _bracketed_root(f, windows[0][0], windows[0][1], what, state, **kw)

    def edge(bad, good, f_good, bad_label):
        """Bisect between a non-evaluable T and an evaluable one whose residual has the wrong sign for a bracket
        with it; returns (T, f) of an evaluable point across the root, or None with the root on the bad side."""
        for _ in range(N_WINDOW_BISECT):
            mid = 0.5 * (bad + good)
            fm, cause = f_probe(mid)
            if fm is None:
                bad, bad_label = mid, cause
            elif fm * f_good <= 0.0:
                return mid, fm
            else:
                good, f_good = mid, fm
        return None, (bad, bad_label, good, f_good)

    ends = []
    for Ta, Tb, below, above, inside in windows:
        pts = [Ta] + inside + [Tb]
        lo_i, fa, lo_bad = 0, None, None
        while lo_i < len(pts):
            fa, cause = f_probe(pts[lo_i])
            if fa is not None:
                break
            lo_bad = (pts[lo_i], cause)
            lo_i += 1
        if fa is None:                                  # no evaluable point in this window
            continue
        hi_i, fb, hi_bad = len(pts) - 1, None, None
        while hi_i > lo_i:
            fb, cause = f_probe(pts[hi_i])
            if fb is not None:
                break
            hi_bad = (pts[hi_i], cause)
            hi_i -= 1
        if hi_i == lo_i:
            fb = fa
        Tlo, Thi = pts[lo_i], pts[hi_i]
        if fa == 0.0:
            return Tlo
        if fb == 0.0:
            return Thi
        if fa * fb < 0.0:
            return brentq(f, Tlo, Thi, **kw)
        if fa > 0.0 and lo_bad is not None:             # the root may sit between the failing point and Tlo
            T_in, f_in = edge(lo_bad[0], Tlo, fa, lo_bad[1])
            if T_in is not None:
                return brentq(f, T_in, Tlo, **kw)
            Tlo, below, fa = f_in[2], f_in[1], f_in[3]
        if fb < 0.0 and hi_bad is not None:
            T_in, f_in = edge(hi_bad[0], Thi, fb, hi_bad[1])
            if T_in is not None:
                return brentq(f, Thi, T_in, **kw)
            Thi, above, fb = f_in[2], f_in[1], f_in[3]
        ends.append((Tlo, Thi, below, above, fa, fb))
    if not ends:
        raise CubicOutOfScope(f"{what}: the residual is not evaluable at any window point.", cause="not_evaluable",
                              windows=[[w[0], w[1]] for w in windows], **state)
    if ends[0][4] > 0.0:                                # below the first window
        T_edge, label, res = ends[0][0], ends[0][2], ends[0][4]
    elif ends[-1][5] < 0.0:                             # above the last window
        T_edge, label, res = ends[-1][1], ends[-1][3], ends[-1][5]
    else:                                               # in a gap between two windows
        i = next((i for i in range(len(ends) - 1) if ends[i][5] < 0.0 < ends[i + 1][4]), None)
        if i is None:
            raise CubicOutOfScope(f"{what}: residual not monotone across the evaluable windows "
                                  f"{[(e[0], e[1], e[4], e[5]) for e in ends]}.", cause="not_monotone",
                                  windows=[[e[0], e[1]] for e in ends], **state)
        T_edge, label, res = ends[i][1], ends[i][3], ends[i][5]
    cause = label if isinstance(label, str) else "outside_bracket"
    raise CubicOutOfScope(
        f"{what}: the specified state lies beyond the evaluable window edge T = {T_edge:.6g} K (residual "
        f"{res:.6g}), on a side labelled {label!r}, which this package does not publish.",
        cause=cause, T_edge=T_edge, residual=res, windows=[[e[0], e[1]] for e in ends], **state)


def flash_PH(eos, P, H, z, T_bracket=None):
    """T from H at fixed P. With an explicit T_bracket, brentq on it. With the default bracket, a temperature
    whose state is not evaluable (for example a certified liquid-liquid split, PSRK CO2 + ethanol at 7 MPa and
    231 K) is a labelled side, not a failure: the evaluable windows of T are located (_windows) and the root is
    sought on them (_root_on_windows). When the specified H lies on such a side the result is the located
    rejection with that cause, never another state. When both default ends are evaluable the search is the
    plain one."""
    z = np.asarray(z, dtype=float)
    memo = {}

    def probe(T):
        if T not in memo:
            memo[T] = _probe(lambda: flash_TP(eos, T, P, z))
        st, cause = memo[T]
        return (None, cause) if st is None else (sum(p["n"] * p["h"] for p in st["phases"]) - H, None)

    def f(T):
        val, cause = probe(T)
        if val is None:
            flash_TP(eos, T, P, z)                      # re-raise the located rejection
        return val
    where = {"P": P, "H": H, "z": z.tolist()}
    if T_bracket is not None:
        T = _bracketed_root(f, T_bracket[0], T_bracket[1], "PH flash (T)", where, xtol=1e-10, rtol=1e-14,
                            maxiter=200)
    else:
        lo, hi = max(eos.T_range[0], 150.0), min(eos.T_range[1], 1000.0)
        side = lambda T: 0 if probe(T)[1] is None else probe(T)[1]
        windows = _windows(side, lo, hi, side(lo), side(hi), "PH flash (T)", where)
        T = _root_on_windows(f, probe, windows, "PH flash (T)", where, xtol=1e-10, rtol=1e-14, maxiter=200)
    st = flash_TP(eos, T, P, z)
    st["T"], st["P"] = T, P
    return st


def flash_UV(eos, U, V, z, T_bracket=None, P_bracket=(1e3, 5e7)):
    """Rigid vessel: nested, P(T) from the volume at each T, then T from U. Two-phase V(P) is monotone.

    Inner problem at each T: ln P with V(P) = V on P_bracket. V decreases with P, so the residual at the two P
    ends tells whether that T is too low (V(P_min) < V), too high (V(P_max) > V) or evaluable. A non-evaluable
    state at P_max (typically a certified liquid-liquid split of compressed liquids) is a labelled side, not a
    failure: ln P is bisected towards it until an evaluable P with V(P) <= V brackets the root; when none is found
    in N_LL_BISECT bisections the volume is reached only on the non-evaluable side and that T takes its label (a
    non-evaluable state at P_min labels the T directly).

    With an explicit T_bracket the outer search is brentq on it (located `outside_bracket` when U is outside).
    With the default bracket (A1 repairs review R3), the outer search first finds the windows of T on a grid
    (_windows) and then the root on them (_root_on_windows); a U that lies on a non-evaluable side is the located
    rejection with its cause. When both default ends are evaluable the window is the default bracket itself, so
    the result equals the plain search."""
    z = np.asarray(z, dtype=float)
    lnPa, lnPb = math.log(P_bracket[0]), math.log(P_bracket[1])
    flashes, inner, outer = {}, {}, {}

    def tp(T, lnP):
        if (T, lnP) not in flashes:
            flashes[(T, lnP)] = flash_TP(eos, T, math.exp(lnP), z)
        return flashes[(T, lnP)]

    def g_at(T):
        return lambda lnP: sum(p["n"] * p["v"] for p in tp(T, lnP)["phases"]) - V

    def inner_side(T):
        """(side, ln P bracket, ln P of the non-evaluable side) of the inner problem at T."""
        if T in inner:
            return inner[T]
        g = g_at(T)
        ga, cause_a = _probe(lambda: g(lnPa))
        gb, cause_b = (None, None) if ga is None else _probe(lambda: g(lnPb))
        for gv in (ga, gb):
            if gv is not None and not math.isfinite(gv):
                raise CubicOutOfScope(f"UV flash: non-finite volume residual at T = {T:.6g} K.",
                                      cause="outside_bracket", T=T, U=U, V=V, z=z.tolist())
        if ga is None:
            res = (cause_a, None, lnPa)
        elif gb is not None:
            s = -1 if (ga < 0.0 and gb < 0.0) else 1 if (ga > 0.0 and gb > 0.0) else 0
            res = (s, (lnPa, lnPb), None)
        elif ga < 0.0:
            res = (-1, None, None)
        else:
            l, h, res = lnPa, lnPb, None
            for _ in range(N_LL_BISECT):
                m = 0.5 * (l + h)
                gm, cm = _probe(lambda: g(m))
                if gm is None:
                    h, cause_b = m, cm
                elif gm <= 0.0:
                    res = (0, (l, m), h)
                    break
                else:
                    l = m
            if res is None:
                res = (cause_b, None, h)
        inner[T] = res
        return res

    def at_T(T):
        s, br, ln_bad = inner_side(T)
        where = {"T": T, "V": V, "z": z.tolist()}
        if isinstance(s, str):
            raise CubicOutOfScope(
                f"UV flash at T = {T:.6g} K: V = {V:.6g} m3 is reached only on the non-evaluable side ({s}, near "
                f"P = {math.exp(ln_bad):.6g} Pa), which this package does not publish.",
                cause=s, P_side=math.exp(ln_bad), **where)
        if br is None:                                  # V(P_min) < V with a non-evaluable state at P_max
            raise CubicOutOfScope(f"UV flash (ln P at T = {T:.6g} K): V = {V:.6g} m3 needs P below "
                                  f"{P_bracket[0]:.6g} Pa.", cause="outside_bracket", **where)
        lnP = _bracketed_root(g_at(T), br[0], br[1], f"UV flash (ln P at T = {T:.6g} K)", where,
                              xtol=1e-13, maxiter=200)
        return tp(T, lnP), math.exp(lnP)

    def f(T):
        st, P = at_T(T)
        return sum(p["n"] * p["u"] for p in st["phases"]) - U

    def probe(T):
        if T not in outer:
            outer[T] = _probe(lambda: f(T))
        return outer[T]
    where = {"U": U, "V": V, "z": z.tolist()}
    if T_bracket is not None:
        T = _bracketed_root(f, T_bracket[0], T_bracket[1], "UV flash (T)", where, xtol=1e-10, rtol=1e-14,
                            maxiter=200)
    else:
        lo, hi = max(eos.T_range[0], 150.0), min(eos.T_range[1], 1000.0)
        side = lambda T: inner_side(T)[0]
        windows = _windows(side, lo, hi, side(lo), side(hi), "UV flash (T)", {**where, "P_bracket": list(P_bracket)})
        T = _root_on_windows(f, probe, windows, "UV flash (T)", where, xtol=1e-10, rtol=1e-14, maxiter=200)
    st, P = at_T(T)
    st["T"], st["P"] = T, P
    return st


def saturation(eos, z, T=None, P=None, kind="bubble", guess=None):
    """Bubble or dew point (incipient phase composition w) at given T (solve P) or given P (solve T).

    Equations: ln w_i + ln phi_i(w) = ln z_i + ln phi_i(z) and sum w_i = 1, solved by Newton on (ln K, ln P or
    ln T) with complex-step-free finite differences of the residual (the unknowns are only nc + 1)."""
    z = np.asarray(z, dtype=float)
    z = z / z.sum()
    # The feed on its liquid-side root for a bubble point (vapour-side for a dew point), the incipient phase on
    # the other; with a single real root both are that root. Near the critical point the trivial solution w = z
    # is avoided by continuation from a converged guess (`saturation_curve`).
    root_z = "liquid" if kind == "bubble" else "vapor"
    root_w = "vapor" if kind == "bubble" else "liquid"
    sgn = 1.0 if kind == "bubble" else -1.0

    def resid(u):
        lnK, s = u[:-1], u[-1]
        TT = math.exp(s) if T is None else T
        PP = math.exp(s) if P is None else P
        w = z * np.exp(sgn * lnK)
        lpz = eos.phase(TT, PP, z, root_z)["lnphi"]
        lpw = eos.phase(TT, PP, w / w.sum(), root_w)["lnphi"]
        r = sgn * lnK + lpw - lpz
        return np.append(r, math.log(w.sum()))
    if guess is None:
        if T is None:
            TT = float(np.dot(z, eos.Tc)) * 0.7
            s0 = math.log(TT)
        else:
            s0 = math.log(float(np.dot(z, eos.Pc * np.exp(5.373 * (1 + eos.omega) * (1 - eos.Tc / T)))))
        lnK0 = wilson_lnK(eos, T if T is not None else math.exp(s0), P if P is not None else math.exp(s0))
        u = np.append(lnK0, s0)
    else:
        u = np.asarray(guess, dtype=float)
    for _ in range(100):
        r = resid(u)
        if np.max(np.abs(r)) < 1e-13:
            break
        J = np.empty((len(u), len(u)))
        for k in range(len(u)):
            du = np.zeros_like(u)
            du[k] = 1e-7
            J[:, k] = (resid(u + du) - resid(u - du)) / 2e-7
        step = np.linalg.solve(J, -r)
        mx = np.max(np.abs(step))
        u = u + (step if mx < 0.5 else step * 0.5 / mx)
    else:
        raise CubicOutOfScope("Saturation point did not converge.")
    lnK, s = u[:-1], u[-1]
    w = z * np.exp(sgn * lnK)
    return {"T": math.exp(s) if T is None else T, "P": math.exp(s) if P is None else P, "w": w / w.sum(), "u": u}


def pure_saturation(eos, i, T):
    """Saturation pressure of species i alone (Maxwell: ln phi^L = ln phi^V on the two roots), T < T_c,i.
    Newton in ln P with the exact derivative d(ln phi^L - ln phi^V)/d ln P = Z^L - Z^V."""
    from core.termodinamica.cubic_eos import PengRobinsonMixture
    sub = eos if eos.nc == 1 else PengRobinsonMixture((eos.cas[i],))
    if not T < sub.Tc[0]:
        raise CubicOutOfScope("No saturation above the critical temperature.")
    x = np.array([1.0])
    P = float(sub.Pc[0] * math.exp(5.373 * (1 + sub.omega[0]) * (1 - sub.Tc[0] / T)))
    for _ in range(200):
        zs = sub.z_roots(T, P, x)
        if len(zs) < 2:
            # one root: move toward the side where the missing root lives
            P = P * (1.02 if zs[0] > sub.Zc else 0.98)
            continue
        ZL, ZV = zs[0], zs[-1]
        r = sub.ln_phi_Z(T, P, x, ZL)[0] - sub.ln_phi_Z(T, P, x, ZV)[0]
        step = -r / (ZL - ZV)
        P *= math.exp(max(-0.5, min(0.5, step)))
        if abs(step) < 1e-14:
            return {"P": P, "ZL": ZL, "ZV": ZV}
    raise CubicOutOfScope(f"Pure saturation of {sub.cas[0]} at T = {T:.6g} K did not converge.")


def saturation_curve(eos, z, T_list, kind="bubble"):
    """Bubble or dew pressures along increasing T by natural-parameter continuation with linear extrapolation of
    (ln K, ln P); the first point starts from Wilson. Stops (returns what it has) when the curve approaches the
    trivial solution (max |ln K| < 1e-6) or Newton fails."""
    out, us = [], []
    for T in T_list:
        if len(us) >= 2:
            t0, t1 = out[-2]["T"], out[-1]["T"]
            g = us[-1] + (us[-1] - us[-2]) * (T - t1) / (t1 - t0)
        elif us:
            g = us[-1]
        else:
            g = None
        try:
            r = saturation(eos, z, T=T, kind=kind, guess=g)
        except (CubicOutOfScope, np.linalg.LinAlgError):
            break
        if np.max(np.abs(r["u"][:-1])) < 1e-6:
            break
        out.append(r)
        us.append(r["u"])
    return out
