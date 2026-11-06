"""
Mixture gas-liquid critical points of the Peng-Robinson package (F8b, 5 November 2026).

Criterion (Heidemann and Khalil, AIChE J. 26 (1980) 769; algorithm of Michelsen, Fluid Phase Equilib. 4 (1980) 1):
a mixture of amounts n = z (sum 1) at (T, V) is critical when the Helmholtz energy's second-order form at fixed
T and V is singular and its third-order form vanishes along the null direction,

    Q_ij = d2(A / RT) / dn_i dn_j |_(T,V) = delta_ij / n_i + F_ij,        (ideal part + residual Hessian)
    B_ij = sqrt(z_i z_j) Q_ij,   lambda_min(B) = 0,   B u = 0,   dn_i = sqrt(z_i) u_i,  |u| = 1,
    C = sum_ijk d3(A / RT)/dn_i dn_j dn_k dn_i dn_j dn_k = d/ds [dn^T Q(n + s dn) dn]_(s = 0) = 0.

Nothing here is posed for a particular mixture: F_ij is the exact Hessian of the residual Helmholtz function
(core/termodinamica/cubic_eos.py), and C is its directional derivative by a fourth-order central difference
(step 1e-4 in s). The search runs over the reduced volume kappa = V/B: for each kappa the temperature with
lambda_min = 0 is bracketed and solved, and then C(kappa) = 0 is solved. Every sign change of C on the kappa
scan is a critical point (a mixture can have more than one). For a pure component the criterion reduces to
dP/dV = d2P/dV2 = 0, so (T_c, P_c) of the catalog are returned exactly.

Orientation of the null vector (A1 review PR-3). C is odd in u and `eigh` fixes no sign, so u is oriented
deterministically: on the kappa scan by continuity (u_k . u_(k-1) >= 0, the first one with its largest-magnitude
component positive), and inside each bracket against the u of the bracket's left end. A sign change of C that
is not a zero (|C| at the polished root not small against the bracket ends) is not reported as a critical point.

What is returned (A1 review PR-2). The criterion is satisfied by gas-liquid and by liquid-liquid critical points
alike, and in type III systems (e.g. benzene + water, ethyl acetate + water with k_ij = 0) both lie on one
continuous locus, so no pointwise criterion separates them exactly. Every root with P > 0 is returned and
classified by the reduced density of the critical fluid against the pure-component value of this same EOS,
kappa_c = Z_c / Omega_b (3.95; equal for every species because B is linear in n):
    kind = 'gas_liquid'     when kappa >= KAPPA_GL * kappa_c   (gas-liquid roots in the tests: 3.46-4.20),
           'liquid_liquid'  when kappa <= KAPPA_LL * kappa_c   (liquid-liquid roots: 1.62-2.41),
           'unclassified'   between (e.g. ethyl acetate + water, x = 0.05: kappa = 2.88).
This is a density classification of the critical fluid, not a proof of which locus the point belongs to.
Roots with P <= 0 are not critical states of a fluid at positive pressure; they are dropped and listed in
`.rejected` of the returned list. When no root with P > 0 lies in the scanned window, a located
`CubicOutOfScope` (cause `no_critical_point_in_window`, with the window and the rejected roots) is raised
instead of an empty list.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import brentq

from core.termodinamica.cubic_eos import R, CubicOutOfScope, critical_constants

KAPPA_GL = 0.80                 # kappa >= 0.80 kappa_c: gas-liquid (see the module docstring)
KAPPA_LL = 0.65                 # kappa <= 0.65 kappa_c: liquid-liquid
C_ZERO_REL = 1e-6               # |C(root)| / max(|C| at the bracket ends) accepted as a zero, not a jump


class CriticalPointList(list):
    """The accepted critical points (a list, as before) plus `.rejected` (roots with P <= 0 and sign jumps of C
    that are not zeros) and `.window` (the scanned kappa range and its scan size)."""

    def __init__(self, items=(), rejected=(), window=None):
        super().__init__(items)
        self.rejected = list(rejected)
        self.window = window


def kappa_c():
    """Pure-component critical reduced volume V_c / b = Z_c / Omega_b of this EOS."""
    _, ob, zc = critical_constants()
    return zc / ob


def classify(kappa):
    kc = kappa_c()
    if kappa >= KAPPA_GL * kc:
        return "gas_liquid"
    if kappa <= KAPPA_LL * kc:
        return "liquid_liquid"
    return "unclassified"


def q_matrix(eos, T, V, n):
    Fij, _, _ = eos.hessian_TV(T, V, n)
    return Fij + np.diag(1.0 / np.asarray(n, dtype=float))


def _orient(u, ref=None):
    """Deterministic sign of the null vector: u . ref >= 0 against a reference (continuity), otherwise its
    largest-magnitude component positive (A1 review PR-3)."""
    if ref is not None:
        s = float(np.dot(u, ref))
        if s != 0.0:
            return u if s > 0.0 else -u
    k = int(np.argmax(np.abs(u)))
    return u if u[k] >= 0.0 else -u


def _lambda_min(eos, T, V, z, ref=None):
    s = np.sqrt(z)
    Bm = np.outer(s, s) * q_matrix(eos, T, V, z)
    w, U = np.linalg.eigh(Bm)
    return w[0], _orient(U[:, 0], ref)


def _T_spinodal(eos, kappa, z):
    """Highest T at which lambda_min(B) = 0 on the isochore V = kappa B (the stability limit)."""
    B = float(np.dot(z, eos.b))
    V = kappa * B
    Tpc = float(np.dot(z, eos.Tc))
    grid = np.linspace(3.0 * Tpc, 0.3 * Tpc, 271)
    prev = None
    for T in grid:
        lam = _lambda_min(eos, T, V, z)[0]
        if prev is not None and prev[1] > 0 >= lam:
            return brentq(lambda t: _lambda_min(eos, t, V, z)[0], T, prev[0], xtol=1e-12, rtol=1e-15)
        prev = (T, lam)
    return None


def cubic_form(eos, T, V, z, step=1e-4, ref=None, return_u=False):
    """C along dn = sqrt(z) u, with u oriented by `_orient` (against `ref` when given)."""
    _, u = _lambda_min(eos, T, V, z, ref)
    dn = np.sqrt(z) * u

    def q(s):
        n = z + s * dn
        if np.any(n <= 0):
            raise CubicOutOfScope("Cubic-form step leaves the composition simplex.")
        return float(dn @ q_matrix(eos, T, V, n) @ dn)
    h = step
    C = (-q(2 * h) + 8 * q(h) - 8 * q(-h) + q(-2 * h)) / (12 * h)
    return (C, u) if return_u else C


def critical_points(eos, z, kappa_range=(1.6, 12.0), n_scan=89):
    """Critical points of composition z with P > 0: a CriticalPointList of {'T', 'P', 'V' (m3/mol), 'kappa',
    'dn', 'kind'} ('gas_liquid', 'liquid_liquid' or 'unclassified', see the module docstring), with `.rejected`
    and `.window`. Raises CubicOutOfScope (cause `no_critical_point_in_window`) when none is found."""
    z = np.asarray(z, dtype=float)
    z = z / z.sum()
    if np.any(z <= 0):
        raise CubicOutOfScope("Critical points need every listed component present (drop absent ones).")
    B = float(np.dot(z, eos.b))

    def C_of(kappa, ref):
        T = _T_spinodal(eos, kappa, z)
        if T is None:
            return None, None, None
        C, u = cubic_form(eos, T, kappa * B, z, ref=ref, return_u=True)
        return C, T, u
    ks = np.geomspace(kappa_range[0], kappa_range[1], n_scan)
    vals = []
    ref = None
    for k in ks:
        c, T, u = C_of(k, ref)
        vals.append((k, c, u))
        ref = u if u is not None else ref       # continuity orientation along the scan
    out, rejected = [], []
    for (k0, c0, u0), (k1, c1, _) in zip(vals, vals[1:]):
        if c0 is None or c1 is None or c0 * c1 > 0:
            continue
        kc = brentq(lambda k: C_of(k, u0)[0], k0, k1, xtol=1e-12, rtol=1e-14)
        Cc, Tc, u = C_of(kc, u0)
        V = kc * B
        P = float(np.real(eos.pressure(Tc, V, z)))
        point = {"T": Tc, "P": P, "V": V, "kappa": kc, "dn": np.sqrt(z) * u, "kind": classify(kc)}
        if not abs(Cc) <= C_ZERO_REL * max(abs(c0), abs(c1)):
            rejected.append({**point, "reason": "sign_jump_of_C", "C": Cc})
        elif not P > 0.0:
            rejected.append({**point, "reason": "non_positive_pressure"})
        else:
            out.append(point)
    window = {"kappa_range": tuple(kappa_range), "n_scan": n_scan, "T_range_over_Tpc": (0.3, 3.0)}
    if not out:
        raise CubicOutOfScope(
            f"No critical point with P > 0 of z = {np.round(z, 6).tolist()} in the scanned window (kappa = V/B in "
            f"[{kappa_range[0]:g}, {kappa_range[1]:g}], T in [0.3, 3] x the mole-fraction mean T_c)"
            + (f"; rejected roots: {[(round(r['T'], 3), round(r['P'], 1), r['reason']) for r in rejected]}"
               if rejected else "") + ".", cause="no_critical_point_in_window", z=z.tolist(), window=window,
            rejected=rejected)
    return CriticalPointList(out, rejected, window)


def binary_critical_reference(eos, x1, T0, v0, h=None):
    """Independent route for a binary: molar Helmholtz a(T, v, x) and the classical determinant criteria
    W = a_vv a_xx - a_vx^2 = 0 and  a_vv W_x - a_vx W_v = 0 (Reid and Beegle, AIChE J. 23 (1977) 726), with
    every derivative by nested central differences of the molar function a(T, v, x) = A(T, v x, x)/RT per mole
    (ideal part x ln(x/v) + (1-x) ln((1-x)/v) up to terms linear in x). Solved by Newton in (T, v)."""
    def a(T, v, x):
        n = np.array([x, 1 - x])
        F = float(np.real(eos.F(T, v, n)))
        return F + x * math.log(x / v) + (1 - x) * math.log((1 - x) / v)

    def derivs(T, v):
        hv, hx = 1e-4 * v, 1e-4
        def avv(x_, v_=v):
            return (a(T, v_ + hv, x_) - 2 * a(T, v_, x_) + a(T, v_ - hv, x_)) / hv ** 2

        def axx(x_, v_=v):
            return (a(T, v_, x_ + hx) - 2 * a(T, v_, x_) + a(T, v_, x_ - hx)) / hx ** 2

        def avx(x_, v_=v):
            return (a(T, v_ + hv, x_ + hx) - a(T, v_ + hv, x_ - hx) - a(T, v_ - hv, x_ + hx)
                    + a(T, v_ - hv, x_ - hx)) / (4 * hv * hx)

        def W(x_, v_=v):
            return avv(x_, v_) * axx(x_, v_) - avx(x_, v_) ** 2
        Wv = (W(x1, v + 10 * hv) - W(x1, v - 10 * hv)) / (20 * hv)
        Wx = (W(x1 + 10 * hx) - W(x1 - 10 * hx)) / (20 * hx)
        return np.array([W(x1), avv(x1) * Wx - avx(x1) * Wv])
    u = np.array([T0, v0])
    for _ in range(40):
        r = derivs(*u)
        J = np.empty((2, 2))
        for k, d in enumerate((1e-3, 1e-3 * u[1])):
            e = np.zeros(2)
            e[k] = d
            J[:, k] = (derivs(*(u + e)) - derivs(*(u - e))) / (2 * d)
        du = np.linalg.solve(J, -r)
        u = u + du
        if abs(du[0]) < 1e-7 and abs(du[1]) < 1e-10 * u[1]:
            break
    T, v = u
    return {"T": T, "V": v, "P": float(np.real(eos.pressure(T, v, np.array([x1, 1 - x1]))))}
