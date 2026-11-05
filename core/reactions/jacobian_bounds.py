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
ChemicalEquilibriumError with a code and a path. PackagePhase providers are reported unsupported in this
version: no ideal-gas or sampled substitute is ever returned for a real-package request.

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
        package = {"provider": "PackagePhase", "package": provider.sistema.paquete.id, "tipo": provider.tipo,
                   "anchor": provider.anchor, "species": cas}
        pure = [asdict(e) for e in provider.sistema.esp]
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


def _enclose(provider, NU, T, P, n):
    s = NU.shape[1]
    nI = [_I(lo, hi) for lo, hi in n]
    N = sum(nI, _I(0))
    if s == 1:
        x = [_I(1)]
    else:
        x = []
        for i, (lo, hi) in enumerate(n):
            rest_hi = sum((_I(n[j][1]) for j in range(s) if j != i), _I(0))
            rest_lo = sum((_I(n[j][0]) for j in range(s) if j != i), _I(0))
            xl, xh = _I(lo) / (_I(lo) + rest_hi), _I(hi) / (_I(hi) + rest_lo)
            x.append(iv.mpf([_lo(xl), min(_hi(xh), mp.mpf(1))]))
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
        comp_x = sum((_I(float(row[i])) * iv.log(x[i]) for i in range(s) if row[i] != 0), _I(0))
        comp_n = sum((_I(float(row[i])) * iv.log(nI[i]) for i in range(s) if row[i] != 0), _I(0)) \
            - rx.Dnu * iv.log(N)
        g = A + _meet(comp_x, comp_n) + rx.Dnu * lnP
        out["g"].append(_to_pair(g))
        out["dg_dn"].append([_to_pair(_I(float(row[k])) / nI[k] - rx.Dnu / N) for k in range(s)])
        out["dg_dT"].append(_to_pair(dA))
        out["dg_dP"].append(_to_pair(rx.Dnu / _I(*P)))
    return out


# --- validity proof ---------------------------------------------------------------------------------------
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
    try:
        A, elements = _ce.element_matrix(provider.cas)
    except Exception as exc:                              # formula lookup unavailable: cannot prove the reference
        diagnostics.append({"code": "ELEMENTS_UNAVAILABLE", "path": "provider",
                            "message": f"Element formulas unavailable, the formation reference cannot be "
                                       f"verified: {exc}"})
        return diagnostics, proof
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
    if not isinstance(provider, _ce.IdealGasPhase):
        result["diagnostics"].append({
            "code": "PROVIDER_UNSUPPORTED", "path": "provider",
            "message": "Certified bounds cover IdealGasPhase only in version 1; PackagePhase "
                       f"({provider.sistema.paquete.id}, {provider.tipo}) is not enclosed and no ideal-gas or "
                       "sampled substitute is returned."})
        return result
    diagnostics, validity = _validity(provider, NU, T, P, n)
    if diagnostics:
        result["diagnostics"] = diagnostics
        return result
    old = iv.prec
    iv.prec = PRECISION_BITS
    try:
        bounds = _enclose(provider, NU, T, P, n)
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
    result.update(certified=True, bounds=bounds,
                  proof={"method": METHOD, "rounding": ROUNDING, "assumptions": list(ASSUMPTIONS),
                         "validity": validity, "precision_bits": PRECISION_BITS, "temperature_pieces": T_PIECES})
    return result
