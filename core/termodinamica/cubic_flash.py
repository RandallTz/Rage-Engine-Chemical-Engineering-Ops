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
        raise CubicOutOfScope("Rachford-Rice has no root: all K on one side of 1.")
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
            raise CubicOutOfScope("Singular two-phase Hessian (critical point of the split).")
        t = 1.0
        while np.any(v + t * dv <= 0) or np.any(z - v - t * dv <= 0):
            t *= 0.5
            if t < 1e-12:
                raise CubicOutOfScope("Two-phase Newton step left the amount simplex.")
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
        raise CubicOutOfScope(f"Split collapsed to one phase at T = {T:.6g} K, P = {P:.6g} Pa.")
    pv = eos.phase(T, P, y)
    pl = eos.phase(T, P, x)
    res_mu = float(np.max(np.abs((np.log(y) + pv["lnphi"]) - (np.log(x) + pl["lnphi"]))))
    cert, _ = stability(eos, T, P, x)
    tm_cert = min([t[1] for t in cert if np.max(np.abs(t[0] - y)) > TOL_SAME], default=math.inf)
    if res_mu > TOL_MU or tm_cert < -TOL_TM:
        raise CubicOutOfScope(f"Two-phase state at T = {T:.6g} K, P = {P:.6g} Pa not certified "
                              f"(mu {res_mu:.3g}, tm {tm_cert:.3g}); a third phase is outside this package.")
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


def _uv_T_window(g_at, lnPa, lnPb, lo, hi, state):
    """[T_a, T_b] inside [lo, hi] at which the inner ln P problem of a UV flash has a root (see flash_UV)."""
    def side(T):
        g = g_at(T)
        ga, gb = g(lnPa), g(lnPb)
        if not (math.isfinite(ga) and math.isfinite(gb)):
            raise CubicOutOfScope(f"UV flash: non-finite volume residual at T = {T:.6g} K.", cause="outside_bracket",
                                  T=T, **state)
        if ga < 0.0 and gb < 0.0:
            return -1                    # V(P_min) < V: the state needs P < P_min, T too low
        if ga > 0.0 and gb > 0.0:
            return 1                     # V(P_max) > V: the state needs P > P_max, T too high
        return 0
    s_lo, s_hi = side(lo), side(hi)
    if s_lo == 0 and s_hi == 0:
        return lo, hi
    grid = np.linspace(lo, hi, N_UV_SCAN)
    sides = [s_lo] + [side(T) for T in grid[1:-1]] + [s_hi]
    ev = [k for k, s in enumerate(sides) if s == 0]
    if not ev:
        raise CubicOutOfScope(
            f"UV flash: no temperature in [{lo:.6g}, {hi:.6g}] K at which V = {state['V']:.6g} m3 is reached with P in "
            f"[{math.exp(lnPa):.6g}, {math.exp(lnPb):.6g}] Pa (sides on a {N_UV_SCAN}-point grid: {sides}).",
            cause="outside_bracket", bracket=[lo, hi], sides=sides, **state)

    def refine(bad, good):
        for _ in range(N_UV_BISECT):
            mid = 0.5 * (bad + good)
            if side(mid) == 0:
                good = mid
            else:
                bad = mid
        return good
    ka, kb = ev[0], ev[-1]
    Ta = float(grid[ka]) if ka == 0 else refine(float(grid[ka - 1]), float(grid[ka]))
    Tb = float(grid[kb]) if kb == len(grid) - 1 else refine(float(grid[kb + 1]), float(grid[kb]))
    return Ta, Tb


def flash_PH(eos, P, H, z, T_bracket=None):
    z = np.asarray(z, dtype=float)
    lo, hi = T_bracket or (max(eos.T_range[0], 150.0), min(eos.T_range[1], 1000.0))
    f = lambda T: sum(p["n"] * p["h"] for p in flash_TP(eos, T, P, z)["phases"]) - H
    T = _bracketed_root(f, lo, hi, "PH flash (T)", {"P": P, "H": H, "z": z.tolist()},
                        xtol=1e-10, rtol=1e-14, maxiter=200)
    st = flash_TP(eos, T, P, z)
    st["T"], st["P"] = T, P
    return st


N_UV_SCAN = 25           # T grid of the default UV bracket search
N_UV_BISECT = 20         # bisections per end of the evaluable T window (grid step / 2^20, ~3e-5 K)


def flash_UV(eos, U, V, z, T_bracket=None, P_bracket=(1e3, 5e7)):
    """Rigid vessel: nested, P(T) from the volume at each T, then T from U. Two-phase V(P) is monotone.

    With an explicit T_bracket the outer search is brentq on it (located `outside_bracket` when U is outside).
    With the default bracket (A1 repairs review R3), the outer search first finds the window of T at which the
    volume V is reachable with P inside P_bracket: on an isochore P(T) increases with T, so at each T the inner
    residual V(P) - V at the two P ends tells whether that T is too low (V(P_min) < V), too high (V(P_max) > V)
    or evaluable. The evaluable window is located on a grid of N_UV_SCAN temperatures and its ends are refined by
    bisection; brentq in T then runs inside that window. When both default ends are evaluable the window is the
    default bracket itself, so the result equals the plain search."""
    z = np.asarray(z, dtype=float)
    lnPa, lnPb = math.log(P_bracket[0]), math.log(P_bracket[1])

    def g_at(T):
        return lambda lnP: sum(p["n"] * p["v"] for p in flash_TP(eos, T, math.exp(lnP), z)["phases"]) - V

    def at_T(T):
        g = g_at(T)
        lnP = _bracketed_root(g, lnPa, lnPb, f"UV flash (ln P at T = {T:.6g} K)", {"T": T, "V": V, "z": z.tolist()},
                              xtol=1e-13, maxiter=200)
        return flash_TP(eos, T, math.exp(lnP), z), math.exp(lnP)

    def f(T):
        st, P = at_T(T)
        return sum(p["n"] * p["u"] for p in st["phases"]) - U
    if T_bracket is not None:
        lo, hi = T_bracket
    else:
        lo, hi = _uv_T_window(g_at, lnPa, lnPb, max(eos.T_range[0], 150.0), min(eos.T_range[1], 1000.0),
                              {"U": U, "V": V, "z": z.tolist(), "P_bracket": list(P_bracket)})
    T = _bracketed_root(f, lo, hi, "UV flash (T)", {"U": U, "V": V, "z": z.tolist()},
                        xtol=1e-10, rtol=1e-14, maxiter=200)
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
