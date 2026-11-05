"""Certified enclosures of the reaction affinities and their Jacobian over a state box (F5, Claude, 5 November 2026).

Contract: docs/engine/codex-queue.md item 4 and the F5 section of docs/engine/multiphysics-roadmap.md.

    reaction_jacobian_bounds(provider, nu, box, *, phase_id, standard_state) -> dict

For reaction rows nu (provider species order, products positive) the dimensionless affinity is

    g_j(T, P, n) = sum_i nu_ij mu_i(T, P, n) / (R T)

with mu_i the provider's element-referenced potential (formation reference included; no reaction heat is ever
added on top of it). The result encloses g, dg/dn [1/mol], dg/dT [1/K] and dg/dP [1/Pa] over the WHOLE box,
not at sampled points.

First provider scope: `IdealGasPhase`. Its potential is, exactly as `IdealGasPhase.mu` evaluates it,

    mu_i = R_d Hp_i(T) - T R_d Sp_i(T) + Hf_i - T S0_i + R T ln(x_i P / P0)
    Hp_i(T) = sum_k a_ik (T^(k+1) - T0^(k+1)) / (k+1)            (Especie.h_ig / R_d)
    Sp_i(T) = a_i0 ln(T/T0) + sum_(k>=1) a_ik (T^k - T0^k) / k    (Especie.s_ig0 / R_d)

(R_d: core.mezclas_datos.R, R: chemical_equilibrium.R; both 8.314462618). Hence, per reaction j, with
Da_k = sum_i nu_ij a_ik, DHf = sum_i nu_ij Hf_i, DS0 = sum_i nu_ij S0_i and Dnu = sum_i nu_ij:

    g      = A(T) + sum_i nu_i ln x_i + Dnu ln(P/P0),   A(T) = (R_d DHp(T) + DHf)/(R T) - (R_d DSp(T) + DS0)/R
    dg/dT  = A'(T) = -(R_d DHp(T) + DHf) / (R T^2)        (Gibbs-Helmholtz: the cp/T terms cancel)
    A''(T) = -R_d Dcp(T) / (R T^2) + 2 (R_d DHp(T) + DHf) / (R T^3),   Dcp(T) = sum_k Da_k T^k
    dg/dn_k = nu_k / n_k - Dnu / N,  N = sum_i n_i
    dg/dP  = Dnu / P

dg/dT therefore includes the derivative of 1/(R T), not only dmu/dT.

Enclosure method. Every quantity is evaluated in mpmath interval arithmetic (directed rounding) at 113 bits:
- T: the box is split into equal pieces; on each piece A and A' are the intersection of the natural interval
  extension and the mean-value form f(m) + f'([t]) ([t] - m); the pieces' hull is returned.
- n: x_i is increasing in n_i and decreasing in every other n_j, so its exact range is
  [lo_i/(lo_i + sum_(j!=i) hi_j), hi_i/(hi_i + sum_(j!=i) lo_j)]; the composition term of g is the intersection
  of sum nu_i ln[x_i] and sum nu_i ln[n_i] - Dnu ln[N]. dg/dn uses [1/n_k] and [1/N].
- P: Dnu ln(P/P0) and Dnu/P are monotone, evaluated at the endpoints.
Endpoints are rounded floor/ceiling to binary64 and then widened by one more ulp (math.nextafter), which
absorbs any error of mpmath's 113-bit elementary functions (far below one binary64 ulp).

Validity proof (each item is checked, never assumed): the provider is a supported type whose phase and
standard state match the request; the T box lies inside every species' Poling cp range; T, P and every n
lower bound are strictly positive; every reaction row conserves the elements EXACTLY (rational arithmetic),
which is the condition under which absolute entropies S0 stand in for formation entropies. A box that fails
any item returns certified False with located diagnostics and null bounds/proof. Malformed input raises
ChemicalEquilibriumError with a code and a path.

Second provider scope (Claude, 5 November 2026): `PackagePhase` with a UNIFAC (original, Dortmund, LLE) or
ideal liquid, standard state pure_liquid_TP, or the package's ideal vapour, standard state ideal_gas_P0. With
phi_i(T) defined in `_PackageStandard` (Psat route, or the tabulated cp_L route of a liquid-only species):

    liquid:  g = sum_i nu_i phi_i(T)/(R T) + P sum_i nu_i v_L,i/(R T) + sum_i nu_i (ln x_i + ln gamma_i(T, x))
    vapour:  g = sum_i nu_i phi_i(T)/(R T) + sum_i nu_i ln x_i + Dnu ln(P/P0)
    dg/dP  = sum nu_i v_L,i/(R T) (liquid, incompressible, no excess volume) or Dnu/P (vapour)

The standard part is enclosed with second-order interval AD in T on the same T pieces; the composition part
with second-order interval AD in (T, n) of UNIFAC in amount form (core/termodinamica/unifac_intervals.py), on
sub-boxes, intersecting natural and mean-value forms of the excess alone plus the exact mixing term and of the
whole composition term. The validity proof adds: a supported liquid model (NRTL is not extended:
PROVIDER_UNSUPPORTED at provider.sistema.liq), T inside the package domain Sistema.T_rango and P inside
[P_MIN, P_MAX] (OUT_OF_DOMAIN at box.T / box.P), and the liquid-only rule: a species of
core.catalogo.REGISTRO_SOLO_LIQUIDO (acetic acid) only in a liquid with anchor='liquid' (LIQUID_ANCHOR_REQUIRED
at provider.anchor). A package fingerprint `activityModel` pins the UNIFAC parameter set (`identidad()`:
variant, table SHA-256, assignments, R/Q, used interactions). No ideal or sampled substitute is ever returned.

The enclosure is of the provider's mathematical function with its data (coefficients, Hf, S0, R, T0, P0)
taken as exact binary64 values; the provider's own floating-point evaluation of mu is a point estimate of it.
"""

import hashlib
import json
import math
from fractions import Fraction

import numpy as np
from mpmath import iv, libmp, mp

from core import mezclas_datos as _md
from core.reactions import chemical_equilibrium as _ce
from core.termodinamica import interval_ad as ad
from core.termodinamica import unifac_intervals

FORMAT = "rage.reaction-jacobian-bounds"
VERSION = 1
PRECISION_BITS = 113
T_PIECES = 64

METHOD = ("mpmath interval arithmetic: natural extension intersected with the mean-value form on "
          f"{T_PIECES} equal temperature pieces (hull returned); exact monotone ranges of x_i, 1/n_k, 1/N and P "
          "terms; composition term as the intersection of the mole-fraction and log-amount forms")
ROUNDING = (f"mpmath interval context at {PRECISION_BITS} bits with directed (floor/ceiling) rounding of every "
            "operation and elementary function; endpoints rounded floor/ceiling to binary64, then widened by one "
            "further binary64 ulp with math.nextafter")


def _err(code, message, path, **detail):
    return _ce.ChemicalEquilibriumError(code, message, path=path, **detail)


# --- input checks (malformed input raises) ---------------------------------------------------------------
def _real(v, path):
    if isinstance(v, bool) or not isinstance(v, (int, float, np.integer, np.floating)):
        raise _err("BOX_TYPE", f"{path} must be a real number, not {type(v).__name__}.", path)
    v = float(v)
    if not math.isfinite(v):
        raise _err("BOX_NONFINITE", f"{path} is not finite.", path)
    return v


def _pair(v, path, *, positive):
    if not isinstance(v, (list, tuple)) or len(v) != 2:
        raise _err("BOX_SHAPE", f"{path} must be a [lower, upper] pair.", path)
    lo, hi = _real(v[0], f"{path}[0]"), _real(v[1], f"{path}[1]")
    if lo > hi:
        raise _err("BOX_UNORDERED", f"{path}: lower bound {lo!r} exceeds upper bound {hi!r}.", path)
    if positive and lo <= 0:
        raise _err("BOX_NONPOSITIVE", f"{path}: lower bound must be strictly positive, got {lo!r}.", f"{path}[0]")
    return lo, hi


def _check_box(box, s):
    if not isinstance(box, dict) or set(box) != {"T", "P", "n"}:
        keys = sorted(box) if isinstance(box, dict) else type(box).__name__
        raise _err("BOX_KEYS", f"box must have exactly the keys T, P, n; got {keys}.", "box")
    T = _pair(box["T"], "box.T", positive=True)
    P = _pair(box["P"], "box.P", positive=True)
    if not isinstance(box["n"], (list, tuple)) or len(box["n"]) != s:
        raise _err("BOX_SHAPE", f"box.n must hold one pair per provider species ({s}).", "box.n")
    n = [_pair(v, f"box.n[{i}]", positive=True) for i, v in enumerate(box["n"])]
    return T, P, n


def _check_nu(nu, s):
    try:
        NU = np.atleast_2d(np.asarray(nu, dtype=float))
    except (TypeError, ValueError) as exc:
        raise _err("NU_TYPE", f"nu is not a numeric matrix: {exc}", "nu")
    if NU.ndim != 2 or NU.shape[1] != s or NU.shape[0] == 0:
        raise _err("NU_SHAPE", f"nu must have reaction rows and {s} species columns (provider order); "
                               f"got shape {NU.shape}.", "nu")
    bad = np.argwhere(~np.isfinite(NU))
    if bad.size:
        j, i = (int(v) for v in bad[0])
        raise _err("NU_NONFINITE", "nu has a non-finite coefficient.", f"nu[{j}][{i}]")
    return NU


def _check_provider(provider, phase_id, standard_state):
    if not isinstance(provider, (_ce.IdealGasPhase, _ce.PackagePhase)):
        raise _err("PROVIDER_TYPE", "provider must be a PackagePhase or IdealGasPhase, not "
                                    f"{type(provider).__name__}.", "provider")
    if phase_id != provider.tipo:
        raise _err("PHASE_MISMATCH", f"Provider phase is {provider.tipo}, not {phase_id}.", "phase_id")
    expected = _ce.STANDARD_STATES[provider.tipo]
    if standard_state != expected:
        raise _err("STANDARD_STATE_MISMATCH", f"{phase_id} uses {expected}, not {standard_state}.",
                   "standard_state")


# --- fingerprints -----------------------------------------------------------------------------------------
def _digest(obj):
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), default=repr)   # float repr round-trips
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fingerprints(provider):
    cas = list(provider.cas)
    formation = {"Hf": [float(v) for v in provider.Hf], "S0": [float(v) for v in provider.S0],
                 "provenance": provider.provenance.get("formation"), "species": cas,
                 "anchor": getattr(provider, "anchor", "gas")}
    if isinstance(provider, _ce.IdealGasPhase):
        package = {"provider": "IdealGasPhase", "species": cas, "R": _ce.R, "R_data": _md.R, "T0": _md.T0,
                   "P0": _ce.P0, "model": "mu_i = g_ig0_i(T) + Hf_i - T S0_i + R T ln(x_i P/P0)"}
        pure = [{"cas": e.cas, "cp_over_R": list(e.cp), "T_cp": list(e.T_cp), "source": "chemicals Poling"}
                for e in provider.especies]
    else:
        from dataclasses import asdict
        from core import mezclas
        sis = provider.sistema
        package = {"provider": "PackagePhase", "package": sis.paquete.id, "package_version": sis.paquete.version,
                   "liquid": sis.paquete.liquido, "tipo": provider.tipo, "anchor": provider.anchor, "species": cas,
                   "liquid_only_system": bool(getattr(sis, "solo_liquido", False)), "R": _ce.R, "R_data": _md.R,
                   "T0": _md.T0, "P0": _md.P0, "P_range": [mezclas.P_MIN, mezclas.P_MAX],
                   "T_range": [float(v) for v in sis.T_rango], "substitutions": sis.sustituciones,
                   "model": "mu_i = Sistema.mu(tipo) + Hf_i - T S0_i"}
        pure = [asdict(e) for e in sis.esp]
        kind = _activity_kind(provider) if provider.tipo == "liquido" else "ideal vapour"
        activity = sis.liq.identidad() if kind == "unifac" else {"model": kind or type(sis.liq).__name__}
        return {"package": _digest(package), "pureData": _digest(pure), "formationReference": _digest(formation),
                "activityModel": _digest(activity)}
    return {"package": _digest(package), "pureData": _digest(pure), "formationReference": _digest(formation)}


# --- interval helpers -------------------------------------------------------------------------------------
def _lo(x):
    return mp.make_mpf(x._mpi_[0])


def _hi(x):
    return mp.make_mpf(x._mpi_[1])


def _I(a, b=None):
    return iv.mpf(a) if b is None else iv.mpf([a, b])


def _meet(x, y):
    lo, hi = max(_lo(x), _lo(y)), min(_hi(x), _hi(y))
    if lo > hi:                                          # two valid enclosures cannot be disjoint
        raise RuntimeError("disjoint enclosures: interval evaluation is inconsistent")
    return iv.mpf([lo, hi])


def _join(x, y):
    return iv.mpf([min(_lo(x), _lo(y)), max(_hi(x), _hi(y))])


def _to_pair(x):
    a = libmp.to_float(x._mpi_[0], rnd="f")
    b = libmp.to_float(x._mpi_[1], rnd="c")
    return [math.nextafter(a, -math.inf), math.nextafter(b, math.inf)]


class _Reaction:
    """Interval forms of A(T), A'(T), A''(T) for one reaction row of an IdealGasPhase."""

    def __init__(self, provider, row):
        a = [e.cp for e in provider.especies]
        K = max(len(c) for c in a)
        self.Da = [sum((_I(float(row[i])) * _I(float(a[i][k])) for i in range(len(row)) if k < len(a[i])),
                       _I(0)) for k in range(K)]
        self.DHf = sum((_I(float(row[i])) * _I(float(provider.Hf[i])) for i in range(len(row))), _I(0))
        self.DS0 = sum((_I(float(row[i])) * _I(float(provider.S0[i])) for i in range(len(row))), _I(0))
        self.Dnu = sum((_I(float(v)) for v in row), _I(0))
        self.R, self.Rd, self.T0 = _I(_ce.R), _I(_md.R), _I(_md.T0)

    def _H(self, t):                                     # R_d DHp(t) + DHf  [J/mol]
        Hp = sum((self.Da[k] * (t ** (k + 1) - self.T0 ** (k + 1)) / (k + 1) for k in range(len(self.Da))), _I(0))
        return self.Rd * Hp + self.DHf

    def _S(self, t):                                     # R_d DSp(t) + DS0  [J/(mol K)]
        Sp = self.Da[0] * iv.log(t / self.T0)
        Sp += sum((self.Da[k] * (t ** k - self.T0 ** k) / k for k in range(1, len(self.Da))), _I(0))
        return self.Rd * Sp + self.DS0

    def _cp(self, t):
        return sum((self.Da[k] * t ** k for k in range(len(self.Da))), _I(0))

    def A(self, t):
        return self._H(t) / (self.R * t) - self._S(t) / self.R

    def dA(self, t):
        return -self._H(t) / (self.R * t ** 2)

    def d2A(self, t):
        return -self.Rd * self._cp(t) / (self.R * t ** 2) + 2 * self._H(t) / (self.R * t ** 3)


def _T_pieces(Tlo, Thi):
    if Tlo == Thi:
        return [(Tlo, Thi)]
    cuts = [Tlo] + [Tlo + (Thi - Tlo) * i / T_PIECES for i in range(1, T_PIECES)] + [Thi]
    return [(cuts[i], cuts[i + 1]) for i in range(T_PIECES)]


def _mean_value(f, df, a, b):
    t = _I(a, b)
    if a == b:
        return f(t)
    m = (a + b) / 2
    return _meet(f(t), f(_I(m)) + df(t) * (t - _I(m)))


def _mole_fractions(n):
    """Exact ranges of x_i over the n box (x_i increases in n_i and decreases in every other n_j)."""
    s = len(n)
    if s == 1:
        return [_I(1)]
    x = []
    for i, (lo, hi) in enumerate(n):
        rest_hi = sum((_I(n[j][1]) for j in range(s) if j != i), _I(0))
        rest_lo = sum((_I(n[j][0]) for j in range(s) if j != i), _I(0))
        xl, xh = _I(lo) / (_I(lo) + rest_hi), _I(hi) / (_I(hi) + rest_lo)
        x.append(iv.mpf([_lo(xl), min(_hi(xh), mp.mpf(1))]))
    return x


def _mixing(row, x, nI, N, Dnu):
    """sum nu_i ln x_i: the intersection of the mole-fraction form and the log-amount form."""
    s = len(row)
    comp_x = sum((_I(float(row[i])) * iv.log(x[i]) for i in range(s) if row[i] != 0), _I(0))
    comp_n = sum((_I(float(row[i])) * iv.log(nI[i]) for i in range(s) if row[i] != 0), _I(0)) - Dnu * iv.log(N)
    return _meet(comp_x, comp_n)


def _enclose(provider, NU, T, P, n):
    s = NU.shape[1]
    nI = [_I(lo, hi) for lo, hi in n]
    N = sum(nI, _I(0))
    x = _mole_fractions(n)
    lnP = iv.log(_I(*P) / _I(_ce.P0))
    pieces = _T_pieces(*T)
    out = {"g": [], "dg_dn": [], "dg_dT": [], "dg_dP": []}
    for row in NU:
        rx = _Reaction(provider, row)
        A = dA = None
        for a, b in pieces:
            Ap = _mean_value(rx.A, rx.dA, a, b)
            dAp = _mean_value(rx.dA, rx.d2A, a, b)
            A, dA = (Ap, dAp) if A is None else (_join(A, Ap), _join(dA, dAp))
        g = A + _mixing(row, x, nI, N, rx.Dnu) + rx.Dnu * lnP
        out["g"].append(_to_pair(g))
        out["dg_dn"].append([_to_pair(_I(float(row[k])) / nI[k] - rx.Dnu / N) for k in range(s)])
        out["dg_dT"].append(_to_pair(dA))
        out["dg_dP"].append(_to_pair(rx.Dnu / _I(*P)))
    return out


# --- package phases ---------------------------------------------------------------------------------------
EXCESS_SUBBOXES = 64        # budget of sub-boxes for the composition (activity) part; see _excess_splits


def _activity_kind(provider):
    """'unifac' | 'ideal' for a supported package liquid, None otherwise (NRTL is not extended)."""
    from core import mezclas, unifac
    liq = provider.sistema.liq
    if isinstance(liq, unifac.LiquidoUNIFAC):
        return "unifac"
    if isinstance(liq, mezclas.LiquidoIdeal):
        return "ideal"
    return None


class _PackageStandard:
    """phi_i(T) = mu_i^0 without its v_L P term, as interval AD objects in T (variable 0):

    liquid, Psat route:  phi = g_ig0 + R T (lnPr + ln(Pc/P0)) - v_L Pc exp(lnPr) + Hf - T S0
    liquid, cp_L route:  phi = h_L* + int_T0^T cp_L dT - v_L P0 - T (s_L* + int_T0^T cp_L/T dT) + Hf - T S0
                         h_L* = -R T0^2 l' + v_L (P0 - Ps0) + T0 v_L Ps0 l',  s_L* = -R ln(Ps0/P0) - R T0 l'
                         + v_L Ps0 l'  (Psat route at T0, P0; l' = dlnPsat/dT at T0)
    vapour:              phi = g_ig0 + Hf - T S0
    g_ig0 = R [sum a_k (T^(k+1) - T0^(k+1))/(k+1)] - T R [a_0 ln(T/T0) + sum_(k>=1) a_k (T^k - T0^k)/k]
    lnPr = num(tau) Tc/T, tau = 1 - T/Tc, num Wagner (Poling 1.5/2.5/5 or McGarry 1.5/3/6 exponents).
    so that mu_i = phi_i(T) + v_L,i P + R T (ln x_i + ln gamma_i) for the liquid (Especie.g_L) and
    mu_i = phi_i(T) + R T ln(x_i P/P0) for the vapour (Sistema.mu)."""

    def __init__(self, provider):
        self.esp = list(provider.sistema.esp)
        self.vapour = provider.tipo == "vapor"
        self.Hf = [float(v) for v in provider.Hf]
        self.S0 = [float(v) for v in provider.S0]

    @staticmethod
    def _H_poly(c, T, T0):
        out = (T - T0).scale(float(c[0]))
        for k in range(1, len(c)):
            out = out + ((ad.power(T, k + 1) - T0 ** (k + 1)) / (k + 1)).scale(float(c[k]))
        return out

    @staticmethod
    def _S_poly(c, T, T0):
        out = ad.log(T / T0, "T/T0").scale(float(c[0]))
        for k in range(1, len(c)):
            out = out + ((ad.power(T, k) - T0 ** k) / k).scale(float(c[k]))
        return out

    @staticmethod
    def _lnPr(e, T):
        A, B, C, D, Tc, _ = (float(v) for v in e.psat)
        tau = 1 - T / _I(Tc)
        if e.psat_forma == "WagnerPoling":
            ex = (2.5, 5)
        else:
            ex = (3, 6)
        num = tau.scale(A) + ad.power(tau, 1.5, "1 - T/Tc").scale(B) + ad.power(tau, ex[0], "1 - T/Tc").scale(C) \
            + ad.power(tau, ex[1], "1 - T/Tc").scale(D)
        return num.scale(_I(Tc)) / T

    def phi(self, i, T):
        e, R, T0, P0 = self.esp[i], _I(_md.R), _I(_md.T0), _I(_md.P0)
        g_ig0 = self._H_poly(e.cp, T, T0).scale(R) - T * self._S_poly(e.cp, T, T0).scale(R)
        shift = -T.scale(_I(self.S0[i])) + _I(self.Hf[i])
        if self.vapour:
            return g_ig0 + shift
        vL, Pc = _I(float(e.vL)), _I(float(e.psat[5]))
        if e.cp_L is None:
            lnPr = self._lnPr(e, T)
            return g_ig0 + (T * (lnPr + iv.log(Pc / P0))).scale(R) - ad.exp(lnPr).scale(vL * Pc) + shift
        lp = self._lnPr(e, ad.var(_md.T0, _md.T0, 0, order=1))
        dl, Ps0 = lp.g[0], Pc * iv.exp(lp.v)
        hLs = -R * T0 * T0 * dl + vL * (P0 - Ps0) + T0 * vL * Ps0 * dl
        sLs = -R * (lp.v + iv.log(Pc / P0)) - R * T0 * dl + vL * Ps0 * dl
        return self._H_poly(e.cp_L, T, T0) + (hLs - vL * P0) - T * (self._S_poly(e.cp_L, T, T0) + sLs) + shift


def _package_standard(provider, NU, T):
    """Hull over T pieces of meet(natural, mean-value) for A_j = sum_i nu_ij phi_i/(R T) and dA_j/dT."""
    forms = _PackageStandard(provider)
    s, R = NU.shape[1], _I(_ce.R)
    used = [i for i in range(s) if np.any(NU[:, i] != 0)]

    def rows(t, order):
        tt = ad.var(t[0], t[1], 0, order=order)
        phi = {i: forms.phi(i, tt) for i in used}
        out = []
        for row in NU:
            terms = [phi[i].scale(_I(float(row[i]))) for i in used if row[i] != 0]
            tot = sum(terms[1:], terms[0]) if terms else ad.const(0, order)
            out.append(tot / tt.scale(R))
        return out

    A = [None] * len(NU)
    dA = [None] * len(NU)
    for a, b in _T_pieces(*T):
        box = rows((a, b), 2)
        if a == b:
            vals = [(f.v, f.g.get(0, _I(0))) for f in box]
        else:
            m = (a + b) / 2
            mid = rows((m, m), 1)
            t = _I(a, b) - _I(m)
            vals = [(_meet(f.v, fm.v + f.g.get(0, _I(0)) * t),
                     _meet(f.g.get(0, _I(0)), fm.g.get(0, _I(0)) + f.h.get((0, 0), _I(0)) * t))
                    for f, fm in zip(box, mid)]
        for j, (v, d) in enumerate(vals):
            A[j] = v if A[j] is None else _join(A[j], v)
            dA[j] = d if dA[j] is None else _join(dA[j], d)
    return A, dA


def _excess_splits(widths, gradient_size, budget):
    """Per-dimension piece counts: repeatedly halve the dimension with the largest estimated contribution
    |dE/dv| * width / pieces while the product of counts stays within the budget (deterministic)."""
    counts = [1] * len(widths)
    est = [g * w for g, w in zip(gradient_size, widths)]
    while True:
        k = max(range(len(est)), key=lambda v: est[v])
        if est[k] <= 0:
            break
        total = 1
        for c in counts:
            total *= c
        if total // counts[k] * (counts[k] * 2) > budget:
            break
        counts[k] *= 2
        est[k] /= 2
    return counts


def _grid(lo, hi, count):
    if count == 1 or lo == hi:
        return [(lo, hi)]
    cuts = [lo] + [lo + (hi - lo) * i / count for i in range(1, count)] + [hi]
    return [(cuts[i], cuts[i + 1]) for i in range(count)]


def _composition(model, NU, T, n):
    """C_j = sum_i nu_ij (ln x_i + ln gamma_i) over the box, with its T and n gradient (variable 0 = T, k + 1 =
    n_k). On each sub-box two enclosures are intersected: (a) the mixing term's exact form plus the excess
    E_j = sum nu ln gamma, and (b) C_j taken whole, so that the partial cancellation of ln x_i and ln gamma_i is
    kept. Each of E and C is itself meet(natural, mean-value) for the value and the gradient, with the Hessian
    enclosure in the gradient's mean-value form. The hull over the sub-boxes is returned."""
    import itertools
    s = len(n)
    dims = [tuple(T)] + [tuple(p) for p in n]

    def evaluate(box, order):
        Tt = ad.var(box[0][0], box[0][1], 0, order=order)
        nn = [ad.var(box[k + 1][0], box[k + 1][1], k + 1, order=order) for k in range(s)]
        lg = model.lngamma(Tt, nn)
        lnN = ad.log(sum(nn[1:], nn[0]), "total amount")
        out = []
        for row in NU:
            ex = [lg[i].scale(_I(float(row[i]))) for i in range(s) if row[i] != 0]
            E = sum(ex[1:], ex[0]) if ex else ad.const(0, order)
            mix = [(ad.log(nn[i], "amount") - lnN).scale(_I(float(row[i]))) for i in range(s) if row[i] != 0]
            out.append((E, E + (sum(mix[1:], mix[0]) if mix else ad.const(0, order))))
        return out

    def centred(F, Fm, delta):
        val = Fm.v
        for v in range(s + 1):
            if v in F.g:
                val = val + F.g[v] * delta[v]
        grad = []
        for v in range(s + 1):
            mv = Fm.g.get(v, _I(0))
            for w in range(s + 1):
                key = (v, w) if v <= w else (w, v)
                if key in F.h:
                    mv = mv + F.h[key] * delta[w]
            grad.append(_meet(F.g.get(v, _I(0)), mv))
        return _meet(F.v, val), grad

    whole = evaluate(dims, 2)
    size = [max((float(max(abs(_lo(C.g[v])), abs(_hi(C.g[v])))) if v in C.g else 0.0) for _, C in whole)
            for v in range(s + 1)]
    widths = [float(b - a) for a, b in dims]
    counts = _excess_splits(widths, size, EXCESS_SUBBOXES)
    acc = None
    for sub in itertools.product(*[_grid(a, b, c) for (a, b), c in zip(dims, counts)]):
        box = evaluate(list(sub), 2) if counts != [1] * (s + 1) else whole
        mid_pt = [(a + b) / 2 for a, b in sub]
        mid = evaluate([(m, m) for m in mid_pt], 1)
        delta = [_I(a, b) - _I(m) for (a, b), m in zip(sub, mid_pt)]
        sub_n = [list(p) for p in sub[1:]]
        nI = [_I(lo, hi) for lo, hi in sub_n]
        N = sum(nI, _I(0))
        x = _mole_fractions(sub_n)
        res = []
        for row, (E, C), (Em, Cm) in zip(NU, box, mid):
            Dnu = sum((_I(float(v)) for v in row), _I(0))
            e_val, e_grad = centred(E, Em, delta)
            c_val, c_grad = centred(C, Cm, delta)
            val = _meet(c_val, e_val + _mixing(row, x, nI, N, Dnu))
            grad = [_meet(c_grad[0], e_grad[0])]
            grad += [_meet(c_grad[k + 1], e_grad[k + 1] + _I(float(row[k])) / nI[k] - Dnu / N) for k in range(s)]
            res.append((val, grad))
        acc = res if acc is None else [(_join(a[0], b[0]), [_join(x_, y) for x_, y in zip(a[1], b[1])])
                                       for a, b in zip(acc, res)]
    return acc, counts


def _enclose_package(provider, NU, T, P, n):
    s = NU.shape[1]
    nI = [_I(lo, hi) for lo, hi in n]
    N = sum(nI, _I(0))
    x = _mole_fractions(n)
    TI, PI, R = _I(*T), _I(*P), _I(_ce.R)
    A, dA = _package_standard(provider, NU, T)
    vapour = provider.tipo == "vapor"
    composition, counts = None, None
    if not vapour and _activity_kind(provider) == "unifac":
        model = provider.sistema._modelo_sub(list(range(s)))
        composition, counts = _composition(unifac_intervals.UnifacIntervalModel(model), NU, T, n)
    out = {"g": [], "dg_dn": [], "dg_dT": [], "dg_dP": []}
    for j, row in enumerate(NU):
        Dnu = sum((_I(float(v)) for v in row), _I(0))
        dT = dA[j]
        if composition is None:
            g = A[j] + _mixing(row, x, nI, N, Dnu)
            dn = [_I(float(row[k])) / nI[k] - Dnu / N for k in range(s)]
        else:
            val, grad = composition[j]
            g, dT = A[j] + val, dT + grad[0]
            dn = grad[1:]
        if vapour:
            g = g + Dnu * iv.log(PI / _I(_ce.P0))
            dP = Dnu / PI
        else:
            c = sum((_I(float(row[i])) * _I(float(provider.sistema.esp[i].vL)) for i in range(s) if row[i] != 0),
                    _I(0))
            g = g + PI * c / (R * TI)
            dT = dT - PI * c / (R * TI * TI)
            dP = c / (R * TI)
        out["g"].append(_to_pair(g))
        out["dg_dn"].append([_to_pair(v) for v in dn])
        out["dg_dT"].append(_to_pair(dT))
        out["dg_dP"].append(_to_pair(dP))
    return out, counts


def _package_validity(provider, NU, T, P, n):
    from core import catalogo, mezclas
    diagnostics, proof = [], {}
    sis = provider.sistema
    kind = _activity_kind(provider)
    if provider.tipo == "liquido" and kind is None:
        diagnostics.append({"code": "PROVIDER_UNSUPPORTED", "path": "provider.sistema.liq",
                            "message": f"The liquid model {type(sis.liq).__name__} of {sis.paquete.id} is not "
                                       "enclosed (UNIFAC and the ideal liquid are; NRTL is not extended). No ideal "
                                       "or sampled substitute is returned."})
        return diagnostics, proof
    proof["activity_model"] = ("ideal vapour" if provider.tipo == "vapor" else
                               f"UNIFAC {sis.liq.variante}" if kind == "unifac" else "ideal liquid (ln gamma = 0)")
    lo, hi = sis.T_rango
    inside = lo <= T[0] and T[1] <= hi
    proof["temperature"] = {"box": list(T), "package_range": [float(lo), float(hi)], "inside": inside,
                            "species": [{"cas": e.cas, "range": [float(v) for v in e.T_rango]} for e in sis.esp]}
    if not inside:
        diagnostics.append({"code": "OUT_OF_DOMAIN", "path": "box.T",
                            "message": f"T box [{T[0]:g}, {T[1]:g}] K leaves the package domain [{lo:g}, {hi:g}] K "
                                       "(Psat and cp ranges, T < 0.9 Tc, liquid cp ranges and the UNIFAC table "
                                       "range)."})
    p_inside = mezclas.P_MIN <= P[0] and P[1] <= mezclas.P_MAX
    proof["pressure"] = {"box": list(P), "package_range": [mezclas.P_MIN, mezclas.P_MAX], "inside": p_inside}
    if not p_inside:
        diagnostics.append({"code": "OUT_OF_DOMAIN", "path": "box.P",
                            "message": f"P box [{P[0]:g}, {P[1]:g}] Pa leaves the package domain "
                                       f"[{mezclas.P_MIN:g}, {mezclas.P_MAX:g}] Pa."})
    liquid_only = [c for c in provider.cas if c in catalogo.REGISTRO_SOLO_LIQUIDO]
    rule_ok = not liquid_only or (provider.anchor == "liquid" and provider.tipo == "liquido")
    proof["liquid_only"] = {"species": liquid_only, "anchor": provider.anchor, "tipo": provider.tipo,
                            "admitted": rule_ok}
    if not rule_ok:
        diagnostics.append({"code": "LIQUID_ANCHOR_REQUIRED", "path": "provider.anchor",
                            "message": f"{', '.join(liquid_only)} is admitted only in a liquid phase anchored to the "
                                       "tabulated liquid (anchor='liquid')."})
    proof["positivity"] = {"T_lower": T[0], "P_lower": P[0], "n_lower_min": min(lo for lo, _ in n),
                           "all_strictly_positive": True}
    _element_validity(provider, NU, diagnostics, proof)
    return diagnostics, proof


# --- validity proof ---------------------------------------------------------------------------------------
def _element_validity(provider, NU, diagnostics, proof):
    try:
        A, elements = _ce.element_matrix(provider.cas)
    except Exception as exc:                              # formula lookup unavailable: cannot prove the reference
        diagnostics.append({"code": "ELEMENTS_UNAVAILABLE", "path": "provider",
                            "message": f"Element formulas unavailable, the formation reference cannot be "
                                       f"verified: {exc}"})
        return
    rows = []
    for j, row in enumerate(NU):
        residual = {el: sum(Fraction(int(A[e, i])) * Fraction(float(row[i])) for i in range(len(row)))
                    for e, el in enumerate(elements)}
        bad = {el: str(v) for el, v in residual.items() if v != 0}
        rows.append({"row": j, "balanced": not bad})
        if bad:
            diagnostics.append({"code": "FORMATION_REFERENCE_INVALID", "path": f"nu[{j}]",
                                "message": "The reaction does not conserve the elements exactly (rational "
                                           f"residual {bad}); absolute entropies then do not cancel the element "
                                           "terms. Use exactly representable balanced coefficients."})
    proof["elements"] = {"elements": elements, "reactions": rows, "arithmetic": "exact rational"}


def _validity(provider, NU, T, P, n):
    diagnostics, proof = [], {}
    species = []
    for i, e in enumerate(provider.especies):
        inside = e.T_cp[0] <= T[0] and T[1] <= e.T_cp[1]
        species.append({"cas": e.cas, "cp_range": [float(e.T_cp[0]), float(e.T_cp[1])], "inside": inside})
        if not inside:
            diagnostics.append({"code": "OUT_OF_DOMAIN", "path": "box.T",
                                "message": f"T box [{T[0]:g}, {T[1]:g}] K leaves the Poling cp range "
                                           f"[{e.T_cp[0]:g}, {e.T_cp[1]:g}] K of {e.cas} (species {i})."})
    proof["temperature"] = {"box": list(T), "species": species}
    proof["positivity"] = {"T_lower": T[0], "P_lower": P[0], "n_lower_min": min(lo for lo, _ in n),
                           "all_strictly_positive": True}
    _element_validity(provider, NU, diagnostics, proof)
    return diagnostics, proof


ASSUMPTIONS = (
    "Provider function: IdealGasPhase, a single ideal-gas phase at any P; condensation and phase stability are "
    "outside the provider's function and are not assessed by this enclosure.",
    "Provider data (Poling cp/R coefficients, Hf, S0, R, T0, P0) are taken as exact binary64 values.",
    "mu includes the formation reference (Hf - T S0); no reaction heat is added; g and dg/dT carry it once.",
    "Absolute entropies stand in for formation entropies only for exactly element-balanced rows (checked).",
    "mpmath 113-bit directed interval arithmetic errs by far less than one binary64 ulp; the extra ulp of "
    "widening covers it.",
)

PACKAGE_METHOD = (
    "mpmath interval arithmetic. Standard part sum nu_i phi_i(T)/(R T) by second-order interval automatic "
    f"differentiation in T: natural extension intersected with the mean-value form on {T_PIECES} equal T pieces "
    "(hull returned). Liquid pressure term P sum nu_i v_L,i/(R T) and its derivatives from single-occurrence "
    "monotone forms. Mixing term as in the ideal-gas scope. Excess term sum nu_i ln gamma_i (UNIFAC in amount "
    "form, core/termodinamica/unifac_intervals.py) by second-order interval automatic differentiation in (T, n): "
    "on each sub-box the natural extensions of value and gradient are intersected with their mean-value forms "
    "(gradient and Hessian enclosures over the sub-box, point evaluation at its binary64 midpoint), for the "
    "excess alone (then added to the exact mixing term) and for the whole composition term "
    "sum nu_i (ln x_i + ln gamma_i), and the two results are intersected; at most "
    f"{EXCESS_SUBBOXES} sub-boxes, split along the dimensions with the largest |dE/dv| width estimate; hull "
    "returned. The standard, pressure and composition parts are enclosed separately and summed.")

PACKAGE_ASSUMPTIONS = (
    "Provider function: PackagePhase, the package's mu as core.mezclas.Sistema.mu evaluates it plus the constant "
    "formation shift Hf - T S0 of the provider's anchor; liquid: incompressible pure liquids of constant v_L and no "
    "excess volume (dmu/dP = v_L), Psat route or, for liquid-only species, the tabulated cp_L route; vapour: ideal "
    "gas. Phase stability is outside the provider's function and is not assessed by this enclosure.",
    "Provider data (Poling cp/R, Wagner Psat coefficients, v_L, liquid cp_L, UNIFAC R, Q, assignments and "
    "interaction coefficients, Hf, S0, R, T0, P0) are taken as exact binary64 values; derived constants (r_i, q_i, "
    "r_i^(3/4), h_L* and s_L* at T0) are recomputed in interval arithmetic.",
    "mu includes the formation reference (Hf - T S0); no reaction heat is added; g and dg/dT carry it once.",
    "Absolute entropies stand in for formation entropies only for exactly element-balanced rows (checked).",
    "A species admitted only in the liquid must be in a liquid phase with anchor='liquid' (checked).",
    "mpmath 113-bit directed interval arithmetic errs by far less than one binary64 ulp; the extra ulp of "
    "widening covers it.",
)


def reaction_jacobian_bounds(provider, nu, box, *, phase_id, standard_state):
    """Versioned, outward-rounded enclosures of g, dg/dn, dg/dT and dg/dP over the whole box (module docstring).

    nu: reaction rows x provider species, products positive. box: {"T":[lo,hi], "P":[lo,hi],
    "n":[[lo,hi], ...]} in K, Pa, mol, provider species order; singleton intervals allowed. Malformed input
    raises ChemicalEquilibriumError(code, message, path=...). Uncertifiable boxes or providers return
    certified False, bounds and proof None, and located diagnostics."""
    _check_provider(provider, phase_id, standard_state)
    s = len(provider.cas)
    NU = _check_nu(nu, s)
    T, P, n = _check_box(box, s)
    result = {"format": FORMAT, "version": VERSION, "certified": False, "species": list(provider.cas),
              "nu": NU.tolist(), "phase_id": phase_id, "standard_state": standard_state,
              "anchor": getattr(provider, "anchor", "gas"),
              "box": {"T": list(T), "P": list(P), "n": [list(p) for p in n]},
              "fingerprints": _fingerprints(provider), "bounds": None, "proof": None, "diagnostics": []}
    package = not isinstance(provider, _ce.IdealGasPhase)
    diagnostics, validity = (_package_validity if package else _validity)(provider, NU, T, P, n)
    if diagnostics:
        result["diagnostics"] = diagnostics
        return result
    old = iv.prec
    iv.prec = PRECISION_BITS
    counts = None
    try:
        if package:
            bounds, counts = _enclose_package(provider, NU, T, P, n)
        else:
            bounds = _enclose(provider, NU, T, P, n)
    except ValueError as exc:                            # an interval argument left its function's domain
        result["diagnostics"].append({"code": "ENCLOSURE_DOMAIN", "path": "box",
                                      "message": f"The interval evaluation left a function's domain: {exc}"})
        return result
    finally:
        iv.prec = old
    for key, rows in bounds.items():
        for j, row in enumerate(rows):
            cells = row if key == "dg_dn" else [row]
            for k, pair in enumerate(cells):
                if not all(math.isfinite(v) for v in pair):
                    path = f"bounds.{key}[{j}][{k}]" if key == "dg_dn" else f"bounds.{key}[{j}]"
                    result["diagnostics"].append({"code": "NONFINITE_BOUND", "path": path,
                                                  "message": "The enclosure is not finite in binary64 "
                                                             "(for example, a trace amount near underflow)."})
    if result["diagnostics"]:
        return result
    proof = {"method": PACKAGE_METHOD if package else METHOD, "rounding": ROUNDING,
             "assumptions": list(PACKAGE_ASSUMPTIONS if package else ASSUMPTIONS), "validity": validity,
             "precision_bits": PRECISION_BITS, "temperature_pieces": T_PIECES}
    if package:
        proof["excess_pieces"] = None if counts is None else {"T": counts[0], "n": counts[1:]}
    result.update(certified=True, bounds=bounds, proof=proof)
    return result
