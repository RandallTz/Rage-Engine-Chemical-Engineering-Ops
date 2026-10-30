"""
Pseudo-arclength continuation of liquid-vapor coexistence branches (f8b, first extension).

Only the public interface of a mixture package (core/mezclas.Sistema or another adapter with the same interface)
is used: `lv_ln_k(T, P, x, idx)`, `mu(kind, T, P, x, idx)`, `fase(...)`, `prueba_estabilidad(...)`,
`T_saturacion(P, i)`, `P_saturacion(T, i)`, `dominio(T, P)` and `T_rango`. No activity, vapor-pressure or
fugacity formula is written here: the package's own distribution coefficient ln K_i = ln(y_i / x_i) is the
equilibrium condition, and every published point is certified with the package's chemical potentials.

Unknowns for N species, in a scaled vector u of length n = 2N + 2:
    u = (x_0 .. x_{N-1}, ln K_0 .. ln K_{N-1}, W_T ln T, W_P ln P),  y_i = K_i x_i.
Equations (n - 1, so the solutions form a curve):
    ln K_i - lv_ln_k_i(T, P, x) = 0      (N)    equal chemical potentials of every species
    sum x - 1 = 0, sum K x - 1 = 0       (2)    normalization of both phases
    slice specification                  (N - 1)
        'isobaric'   (binary T-xy):   ln P = ln P_fixed
        'isothermal' (binary P-xy):   ln T = ln T_fixed
        'bubble'     (any N, fixed liquid z):  x_i = z_i, i < N - 1   -> curve in (T, P)
        'dew'        (any N, fixed vapor z):   y_i = z_i, i < N - 1   -> curve in (T, P)
Because ln K is finite at x_i = 0, the pure-component ends are regular points of the same system.

Algorithm: tangent predictor (null vector of the Jacobian, oriented by the previous tangent), Newton corrector
on the equations plus the arc-length constraint t . (u - u_pred) = 0, step control by corrector iterations and
the angle between consecutive tangents, and exact ends: when a predictor crosses a bound (x_i >= 0 or the
package domain in T and P) the end point is solved with that bound as the closing equation. Turning points of
T or P along the branch (sign change of d ln T/ds or d ln P/ds; a homogeneous azeotrope on a T-xy or P-xy
branch) are located by a secant on the step length. Every accepted point carries a certificate: equal mu of
every present species, normalization, phase distinction and tangent-plane stability against vapor and liquid
trials; stable and unstable stretches are published separately and their boundaries bisected.
"""

import math
import time

import numpy as np

from core import mezclas as mz

CONTINUATION = {"id": "lv-arclength", "version": "1"}
W_T = 20.0                 # weight of ln T in the arc-length metric (T spans a few percent of itself)
W_P = 1.0                  # weight of ln P
TOL_F = 1e-12              # corrector convergence, max |residual| (ln K in R T units; fractions)
TOL_U = 1e-10              # corrector convergence, max |update| in scaled variables
FD_STEP = 1e-7
DOMAIN_MARGIN = 1e-6        # relative, larger than the finite-difference step in ln T and ln P
PROFILES = {
    "standard": {"id": "standard", "initialStep": 0.02, "maximumStep": 0.05, "minimumStep": 1e-7,
                 "maximumCorrectorIterations": 8, "maximumTangentAngle": 0.15, "maximumPoints": 2000,
                 "timeLimitSeconds": 120.0, "stabilityBisections": 20},
}


class ContinuationError(Exception):
    pass


class _Branch:
    """The equations of one slice for one package."""

    def __init__(self, sis, kind, fixed=None, z=None):
        if kind not in ("isobaric", "isothermal", "bubble", "dew"):
            raise ValueError(f"unknown slice kind {kind!r}")
        self.sis, self.kind = sis, kind
        self.N = N = len(sis.esp)
        if kind in ("isobaric", "isothermal") and N != 2:
            raise ValueError("isobaric and isothermal slices are binary; use 'bubble' or 'dew' for N species")
        if kind in ("bubble", "dew"):
            z = np.asarray(z, dtype=float)
            if z.shape != (N,) or np.any(z <= 0) or abs(z.sum() - 1.0) > 1e-12:
                raise ValueError("z must hold N strictly positive mole fractions summing to 1")
        self.fixed, self.z = fixed, z
        self.idx = list(range(N))
        self.n = 2 * N + 2
        self.evaluations = 0
        T_lo, T_hi = sis.T_rango
        # bounds g_k(u) >= 0: mole fractions, then the package domain, kept DOMAIN_MARGIN inside so that the
        # finite-difference Jacobian at a domain end still evaluates inside `dominio`
        m = DOMAIN_MARGIN
        self.bounds = [("x", i) for i in range(N)] + [("T_min", T_lo * (1 + m)), ("T_max", T_hi * (1 - m)),
                                                       ("P_min", mz.P_MIN * (1 + m)), ("P_max", mz.P_MAX * (1 - m))]

    # --- variables ----------------------------------------------------------------------------------------
    def unpack(self, u):
        N = self.N
        x = u[:N]
        lnK = u[N:2 * N]
        return x, lnK, math.exp(u[2 * N] / W_T), math.exp(u[2 * N + 1] / W_P)

    def pack(self, x, lnK, T, P):
        return np.concatenate([np.asarray(x, float), np.asarray(lnK, float), [W_T * math.log(T), W_P * math.log(P)]])

    def bound(self, u, k):
        what, val = self.bounds[k]
        x, _, T, P = self.unpack(u)
        return {"x": lambda: x[val], "T_min": lambda: math.log(T / val), "T_max": lambda: math.log(val / T),
                "P_min": lambda: math.log(P / val), "P_max": lambda: math.log(val / P)}[what]()

    def bound_row(self, k):
        """Gradient of g_k with respect to u (all bounds are linear in u)."""
        what, _ = self.bounds[k]
        row = np.zeros(self.n)
        col = {"x": None, "T_min": (2 * self.N, 1 / W_T), "T_max": (2 * self.N, -1 / W_T),
               "P_min": (2 * self.N + 1, 1 / W_P), "P_max": (2 * self.N + 1, -1 / W_P)}[what]
        if col is None:
            row[self.bounds[k][1]] = 1.0
        else:
            row[col[0]] = col[1]
        return row

    # --- equations ----------------------------------------------------------------------------------------
    def F(self, u):
        N = self.N
        x, lnK, T, P = self.unpack(u)
        if np.any(x < -1e-9) or not np.all(np.isfinite(u)):
            raise ValueError("composition left the simplex")
        self.sis.dominio(T, P)
        self.evaluations += 1
        r = list(lnK - self.sis.lv_ln_k(T, P, x, self.idx))
        K = np.exp(lnK)
        r += [x.sum() - 1.0, (K * x).sum() - 1.0]
        if self.kind == "isobaric":
            r.append(math.log(P / self.fixed))
        elif self.kind == "isothermal":
            r.append(math.log(T / self.fixed))
        elif self.kind == "bubble":
            r += list(x[:N - 1] - self.z[:N - 1])
        else:
            r += list((K * x)[:N - 1] - self.z[:N - 1])
        return np.array(r)

    def J(self, u):
        cols, f0 = [], None
        for j in range(self.n):
            d = np.zeros(self.n)
            d[j] = FD_STEP
            if j < self.N and u[j] < FD_STEP:
                # at a pure end x_j = 0: second-order one-sided difference, the liquid never leaves the simplex
                f0 = self.F(u) if f0 is None else f0
                cols.append((-3 * f0 + 4 * self.F(u + d) - self.F(u + 2 * d)) / (2 * FD_STEP))
            else:
                cols.append((self.F(u + d) - self.F(u - d)) / (2 * FD_STEP))
        return np.column_stack(cols)

    def newton(self, u0, extra_row, extra_value, max_iter):
        """Solve F(u) = 0 and extra_row . u = extra_value from u0. (u, iterations) or None."""
        u = np.array(u0, dtype=float)
        for it in range(1, max_iter + 1):
            try:
                f = np.append(self.F(u), extra_row @ u - extra_value)
                A = np.vstack([self.J(u), extra_row])
                du = np.linalg.solve(A, -f)
            except (mz.FueraDeAlcance, ValueError, FloatingPointError, OverflowError, np.linalg.LinAlgError):
                return None
            u = u + du
            if np.max(np.abs(du)) < TOL_U:
                try:
                    f = np.append(self.F(u), extra_row @ u - extra_value)
                except (mz.FueraDeAlcance, ValueError, FloatingPointError, OverflowError):
                    return None
                if np.max(np.abs(f)) < TOL_F:
                    return u, it
        return None

    def tangent(self, u, previous):
        """Unit tangent at u. With `previous`, the solution of [J; previous] t = e_n (same orientation)."""
        J = self.J(u)
        if previous is None:
            t = np.linalg.svd(J)[2][-1]
        else:
            t = np.linalg.solve(np.vstack([J, previous]), np.eye(self.n)[-1])
        return t / np.linalg.norm(t)


def certify(sis, T, P, x, y):
    """Certificate of a published L-V point (T, P, x, y) from the package's mu over the full species set: both
    phases must contain the same species (a species present in only one phase has an unbounded mu gap, so the
    point is rejected, never trimmed), then equal mu of every species, normalization, phase distinction and
    tangent-plane stability (vapor and liquid trials). A species absent from both phases is exactly the
    subsystem without it: its mu is -inf in every phase and in every trial that contains it."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    in_x, in_y = x > 0, y > 0
    r_n = max(abs(float(x.sum()) - 1.0), abs(float(y.sum()) - 1.0), float(max(0.0, -x.min(), -y.min())))
    if np.any(in_x != in_y) or not np.any(in_x):
        only = [int(i) for i in np.flatnonzero(in_x != in_y)]
        return {"state": "failed", "residuals": [
            {"id": "common_support", "value": float(len(only)), "tolerance": 0.0, "scale": "species",
             "passes": False, "species": only,
             "message": "a species is present in one phase and absent from the other: its mu gap is unbounded"},
            {"id": "normalization", "value": r_n, "tolerance": 1e-12, "scale": "1", "passes": r_n <= 1e-12}],
            "stability": {"state": "not_tested"}}
    idx = [int(i) for i in np.flatnonzero(in_x)]
    xs, ys = x[idx], y[idx]
    RT = mz.R * T
    mL = sis.mu("liquido", T, P, xs, idx)
    mV = sis.mu("vapor", T, P, ys, idx)
    r_mu = float(np.max(np.abs(mL - mV)) / RT)
    vL = sis.fase("l", "liquido", T, P, xs, idx).v
    vV = sis.fase("v", "vapor", T, P, ys, idx).v
    r_d = abs(vV - vL) / vV
    trials = sis.prueba_estabilidad(T, P, mL, idx, incluir_vapor=True)
    tm_min = min(q[2] for q in trials)
    residuals = [
        {"id": "common_support", "value": 0.0, "tolerance": 0.0, "scale": "species", "passes": True},
        {"id": "equal_mu", "value": r_mu, "tolerance": mz.TOL_MU, "scale": "R T", "passes": r_mu <= mz.TOL_MU},
        {"id": "normalization", "value": r_n, "tolerance": 1e-12, "scale": "1", "passes": r_n <= 1e-12},
        {"id": "phase_distinction", "value": float(r_d), "tolerance": 1e-3, "scale": "|v_V - v_L| / v_V",
         "passes": r_d > 1e-3},
    ]
    stability = {"state": "stable" if tm_min >= -mz.TOL_TM else "unstable", "tmMinimum": float(tm_min),
                 "tolerance": mz.TOL_TM, "trials": len(trials)}
    if tm_min < -mz.TOL_TM:
        q = min(trials, key=lambda q: q[2])
        w = np.zeros(len(x))
        w[idx] = q[1]
        stability["competitor"] = {"kind": q[0], "composition": [float(v) for v in w], "tm": float(q[2])}
    solved = all(r["passes"] for r in residuals)
    return {"state": "certified" if solved and stability["state"] == "stable" else
            ("unstable" if solved else "failed"), "residuals": residuals, "stability": stability}


def _publish(br, u, t, s, iterations, origin):
    x, lnK, T, P = br.unpack(u)
    x = np.clip(x, 0.0, None)
    y = np.exp(lnK) * x
    point = {"s": float(s), "T": T, "P": P, "x": [float(v) for v in x], "y": [float(v) for v in y],
             "lnK": [float(v) for v in lnK], "origin": origin, "correctorIterations": iterations,
             "tangent": {"dlnT_ds": float(t[2 * br.N] / W_T), "dlnP_ds": float(t[2 * br.N + 1] / W_P)}}
    point["certificate"] = certify(br.sis, T, P, x, y)
    return point


def _start_pure(br, i):
    """Pure-component saturation of species i in the same package, polished on the slice."""
    sis, N = br.sis, br.N
    if br.kind == "isobaric":
        T, P = sis.T_saturacion(br.fixed, i), br.fixed
    else:
        T = br.fixed
        P = sis.P_saturacion(T, i)
    if T is None or P is None:
        raise ContinuationError(f"species {i} does not saturate in the package domain on this slice")
    x = np.eye(N)[i]
    u0 = br.pack(x, sis.lv_ln_k(T, P, x, br.idx), T, P)
    j = 1 - i
    res = br.newton(u0, br.bound_row(j), 0.0, 20)       # closing equation x_j = 0
    if res is None:
        raise ContinuationError("the pure-component end did not converge")
    return res[0], ("x", j)


def _start_envelope(br, T):
    """Bubble or dew point of z at T: successive substitution on the package's ln K, then Newton."""
    sis, z = br.sis, br.z
    P = 101325.0
    for _ in range(200):
        P = min(max(P, mz.P_MIN), mz.P_MAX)
        x = z if br.kind == "bubble" else None
        if br.kind == "bubble":
            K = np.exp(sis.lv_ln_k(T, P, z, br.idx))
            P_new = P * float((K * z).sum())
        else:
            xg = z.copy()
            for _ in range(50):
                K = np.exp(sis.lv_ln_k(T, P, xg, br.idx))
                xn = (z / K) / (z / K).sum()
                if np.max(np.abs(xn - xg)) < 1e-12:
                    break
                xg = xn
            x = xg
            P_new = P / float((z / K).sum())
        if abs(P_new / P - 1.0) < 1e-10:
            break
        P = P_new
    row = np.zeros(br.n)
    row[2 * br.N] = 1.0
    u0 = br.pack(x, np.log(K), T, P)
    res = br.newton(u0, row, W_T * math.log(T), 30)
    if res is None:
        raise ContinuationError(f"no {br.kind} point of z at T = {T:.6g} K in the package domain")
    return res[0], None


def trace(sis, kind, fixed=None, z=None, start=None, profile_id="standard"):
    """Trace one L-V branch by pseudo-arclength continuation.

    kind 'isobaric' (fixed = P, Pa) or 'isothermal' (fixed = T, K): binary branch from the pure end of species
    `start` (default 0) to the other end. kind 'bubble' or 'dew' (z, N species): the (T, P) envelope from
    T = `start` (default the lower domain limit plus 1 K) upward until the package domain ends it."""
    prof = PROFILES[profile_id]
    br = _Branch(sis, kind, fixed, z)
    t0 = time.perf_counter()
    if kind in ("isobaric", "isothermal"):
        i = 0 if start is None else int(start)
        u, active = _start_pure(br, i)
        t = br.tangent(u, None)
        if t[i] > 0:                     # leave the pure end of species i: x_i decreases
            t = -t
    else:
        T0 = sis.T_rango[0] + 1.0 if start is None else float(start)
        u, active = _start_envelope(br, T0)
        t = br.tangent(u, None)
        if t[2 * br.N] < 0:              # T increases
            t = -t
    points = [_publish(br, u, t, 0.0, 0, "pure_end" if active else "envelope_start")]
    s, h = 0.0, prof["initialStep"]
    end, turning, changes = None, [], []
    tracked = [(2 * br.N, "temperature"), (2 * br.N + 1, "pressure")]
    tracked = [c for c in tracked if not (kind == "isobaric" and c[1] == "pressure")
               and not (kind == "isothermal" and c[1] == "temperature")]

    def correct(u_from, t_from, step):
        pred = u_from + step * t_from
        return br.newton(pred, t_from, t_from @ pred, prof["maximumCorrectorIterations"])

    def events(u_old, t_old, u_new, t_new, step, s_old, p_old, p_new):
        """The checks every accepted step runs, the closing step to a pure or domain end included: a sign change
        of d ln T/ds or d ln P/ds is a turning point, located on the step (or published as an unlocated bracket),
        and a change of certificate state is bisected."""
        for col, name in tracked:
            if t_old[col] * t_new[col] < 0:
                kind_tp = "maximum" if t_old[col] > 0 else "minimum"
                tp = _locate_turning(br, u_old, t_old, step, col, correct)
                if tp is not None:
                    u_tp, t_tp, h_tp = tp
                    p_tp = _publish(br, u_tp, t_tp, s_old + h_tp, 0, "turning_point")
                    p_tp["turningPoint"] = {"variable": name, "kind": kind_tp, "located": True}
                else:
                    # not located inside the step: publish the bracket end with the smaller tangent component
                    near = p_old if abs(t_old[col]) <= abs(t_new[col]) else p_new
                    p_tp = dict(near, origin="turning_point_bracket")
                    p_tp["turningPoint"] = {"variable": name, "kind": kind_tp, "located": False,
                                            "bracket": [p_old["s"], p_new["s"]]}
                turning.append(p_tp)
        if (p_old["certificate"]["state"] == "certified") != (p_new["certificate"]["state"] == "certified"):
            changes.append(_locate_stability_change(br, u_old, t_old, step, correct, p_old, p_new, s_old, prof))

    while end is None:
        if len(points) >= prof["maximumPoints"] or time.perf_counter() - t0 > prof["timeLimitSeconds"]:
            end = {"kind": "budget", "message": "point or time budget exhausted"}
            break
        if h < prof["minimumStep"]:
            end = {"kind": "no_convergence", "message": f"step below {prof['minimumStep']:g} without convergence"}
            break
        pred = u + h * t
        crossing = [(k, h * br.bound(u, k) / (br.bound(u, k) - br.bound(pred, k)))
                    for k in range(len(br.bounds))
                    if br.bounds[k] != active and br.bound(pred, k) < 0 <= br.bound(u, k)]
        if crossing:
            k, hb = min(crossing, key=lambda c: c[1])
            row = br.bound_row(k)           # closing equation g_k(u) = 0 (g_k is linear in u)
            res = br.newton(u + hb * t, row, row @ u - br.bound(u, k), prof["maximumCorrectorIterations"] + 4)
            if res is not None and t @ (res[0] - u) > 0 and \
                    all(br.bound(res[0], q) >= -1e-12 for q in range(len(br.bounds)) if q != k):
                u_end = res[0]
                t_end = br.tangent(u_end, t)
                step = float(t @ (u_end - u))      # the arc-length step that lands on the end (same corrector)
                what = br.bounds[k][0]
                origin = "pure_end" if what == "x" else "domain_limit"
                p_end = _publish(br, u_end, t_end, s + step, res[1], origin)
                events(u, t, u_end, t_end, step, s, points[-1], p_end)
                s += step
                points.append(p_end)
                end = {"kind": "pure_component" if what == "x" else "domain_limit", "bound": what,
                       "message": (f"species {br.bounds[k][1]} vanishes: pure-component saturation" if what == "x"
                                   else f"package domain limit {what} = {br.bounds[k][1]:.6g}")}
                break
            h = 0.5 * min(h, hb)
            continue
        res = correct(u, t, h)
        if res is None:
            h *= 0.5
            continue
        u_new, its = res
        try:
            t_new = br.tangent(u_new, t)
        except (mz.FueraDeAlcance, ValueError, FloatingPointError, np.linalg.LinAlgError):
            h *= 0.5
            continue
        if math.acos(min(1.0, max(-1.0, float(t @ t_new)))) > prof["maximumTangentAngle"]:
            h *= 0.5
            continue
        p = _publish(br, u_new, t_new, s + h, its, "continuation")
        events(u, t, u_new, t_new, h, s, points[-1], p)
        s += h
        points.append(p)
        u, t = u_new, t_new
        active = None
        h = min(1.5 * h, prof["maximumStep"]) if its <= 3 else (0.7 * h if its >= 6 else h)

    all_points = sorted(points + turning, key=lambda q: q["s"])
    return {"continuation": CONTINUATION, "profile": prof,
            "slice": {"kind": kind, "fixed": fixed, "z": None if z is None else [float(v) for v in z],
                      "species": list(sis.cas)},
            "points": all_points, "turningPoints": turning, "stabilityChanges": changes, "end": end,
            "budget": {"points": len(all_points), "evaluations": br.evaluations,
                       "seconds": round(time.perf_counter() - t0, 3)}}


def _locate_turning(br, u, t, h, col, correct):
    """Step length in (0, h) where the tracked tangent component vanishes (Illinois secant)."""
    def g(step):
        res = correct(u, t, step)
        if res is None:
            return None
        tt = br.tangent(res[0], t)
        return tt[col], res[0], tt
    a, fa = 0.0, t[col]
    gb = g(h)
    if gb is None:
        return None
    b, fb = h, gb[0]
    side = 0
    best = (b, gb)
    for _ in range(60):
        c = b - fb * (b - a) / (fb - fa)
        gc = g(c)
        if gc is None:
            return None
        fc = gc[0]
        best = (c, gc)
        if abs(fc) < 1e-13 or abs(b - a) < 1e-14:
            break
        if fc * fb < 0:
            a, fa = b, fb
            side_new = 0
        else:
            side_new = 1
            if side == 1:
                fa *= 0.5
        b, fb = c, fc
        side = side_new
    step, (_, u_tp, t_tp) = best
    return u_tp, t_tp, step


def _locate_stability_change(br, u, t, h, correct, prev, nxt, s0, prof):
    """Bisect the step length between a certified and an uncertified point; publish the bracket."""
    lo, hi = 0.0, h
    first_certified = prev["certificate"]["state"] == "certified"
    near, far = prev, nxt                    # near keeps the state of prev, far the state of nxt
    for _ in range(prof["stabilityBisections"]):
        m = 0.5 * (lo + hi)
        res = correct(u, t, m)
        if res is None:
            break
        pm = _publish(br, res[0], br.tangent(res[0], t), s0 + m, res[1], "stability_boundary")
        if (pm["certificate"]["state"] == "certified") == first_certified:
            lo, near = m, pm
        else:
            hi, far = m, pm
    last_good, last_bad = (near, far) if first_certified else (far, near)
    return {"certifiedSide": last_good, "uncertifiedSide": last_bad,
            "competitor": last_bad["certificate"]["stability"].get("competitor"),
            "bracketArcLength": float(hi - lo)}
