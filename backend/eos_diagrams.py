"""
Equilibrium diagrams of the two layer EOS packages (own protocol, revision 1; F8b lane A, 8 November 2026).

Packages: `peng-robinson-vdw1f` (core/termodinamica/cubic_eos.py) and `psrk-unifac` (core/termodinamica/psrk.py).
Operations (all at elevated pressure, nothing outside the packages' declared coverage):

  - saturation_curve: bubble or dew pressure of a fixed overall composition along a temperature grid;
  - isotherm: bubble pressure and vapour composition of a binary along its liquid mole fraction at fixed T;
  - critical_locus: Heidemann-Khalil critical points of a binary along its mole fraction.

The service adds no physics. It validates the request (every known rejection is a structured response with a path,
never a 422), builds the SAME equation of state the layer closure builds (`capa._ecuacion_estado`), calls the
package operations and publishes their certified points. A located failure (`CubicOutOfScope.datos['cause']`) is
published as a rejected point with its cause, never replaced by a neighbouring state. Contract:
frontend/app/motor/eosDiagrams.ts; description: docs/contracts/thermodynamic-layer.md (section "EOS diagrams").
"""

import hashlib
import json
import math
import time

import numpy as np

from backend import motor_termodinamica as mt
from core.termodinamica import capa, cubic_critical as cc, cubic_flash, psrk
from core.termodinamica.cubic_eos import CubicOutOfScope, PengRobinsonMixture

REVISION = 1
PACKAGES = {capa.CUBICO: "1", capa.PSRK: "1"}
OPERATIONS = ("saturation_curve", "isotherm", "critical_locus")
LIMITS = {"saturation_curve": 60, "isotherm": 40, "critical_locus": 15}   # largest `points` per operation
BUDGET_SECONDS = 150.0
PSRK_KAPPA = dict(kappa_range=(1.12, 12.0), n_scan=60)     # the scan window of the F8b PSRK critical-locus tests
FIELDS = {"revision", "requestId", "operation", "package", "components", "points"}
OP_FIELDS = {"saturation_curve": {"composition", "kind", "temperatureRange"},
             "isotherm": {"condition", "fractionRange"},
             "critical_locus": {"fractionRange"}}
STATUS_ORDER = ("invalid", "unsupported", "incomplete")
TOL_CERT = psrk.TOL_CERT


class _PR(PengRobinsonMixture):
    """The layer's Peng-Robinson with the (empty) temperature gate PSRK's certified operations call."""

    def check_temperature(self, T):
        return None


def capabilities():
    return {"revision": REVISION,
            "packages": [{"model": {"id": k, "version": v}} for k, v in PACKAGES.items()],
            "operations": [
                {"id": "saturation_curve", "components": {"min": 2, "max": None}, "limit": LIMITS["saturation_curve"],
                 "publishes": ["bubble or dew pressure and incipient-phase composition with a fugacity certificate"]},
                {"id": "isotherm", "components": {"min": 2, "max": 2}, "limit": LIMITS["isotherm"],
                 "publishes": ["bubble pressure and vapor composition of a binary at fixed T with a certificate"]},
                {"id": "critical_locus", "components": {"min": 2, "max": 2}, "limit": LIMITS["critical_locus"],
                 "publishes": ["critical temperature, pressure and volume of the highest-T root per composition"]}],
            "budgetSeconds": BUDGET_SECONDS,
            "units": {"T": "K", "P": "Pa", "V": "m3/mol"},
            "unsupported": [
                {"element": "pure-data substitutions and binary parameters", "reason": "k_ij = 0 and catalog data only"},
                {"element": "liquid-liquid, three-phase and solid regions", "reason": "two-candidate packages"},
                {"element": "dynamic assembly with these packages",
                 "reason": "the v2 assembly publishes only the mixture packages; layer closures are in /modelo"}]}


class _Reader:
    def __init__(self):
        self.diagnostics = []

    def add(self, status, code, path, message, ids=()):
        self.diagnostics.append({"code": code, "status": status, "path": path, "message": message,
                                 "componentIds": list(ids)})

    def statuses(self):
        return {d["status"] for d in self.diagnostics}


def _empty(rid, operation, status, diagnostics, package=None):
    return {"revision": REVISION, "requestId": rid, "operation": operation, "status": status,
            "identity": {"package": package or {"id": "", "version": ""}, "querySignature": None},
            "points": [], "rejected": [], "diagnostics": diagnostics}


def _quantity(rd, v, path, mag):
    units = mt.UNIDADES[mag]
    if not isinstance(v, dict) or set(v) != {"valor", "unidad"}:
        rd.add("invalid", "EOS_DIAG_INVALID_DATA", path, "Expected {valor, unidad}.")
        return None
    val, unit = v["valor"], v["unidad"]
    if val is None:
        rd.add("incomplete", "EOS_DIAG_INVALID_DATA", path + ".valor", "Unspecified value (null is not zero).")
        return None
    if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(val):
        rd.add("invalid", "EOS_DIAG_INVALID_DATA", path + ".valor", "Non-numeric or non-finite value.")
        return None
    if unit not in units:
        rd.add("invalid", "EOS_DIAG_UNIT", path + ".unidad", f"Unit {unit!r} is not a {mag} unit; use {', '.join(units)}.")
        return None
    f, d = units[unit]
    si = val * f + d
    if not si > 0:
        rd.add("invalid", "EOS_DIAG_INVALID_DATA", path + ".valor", f"{mag} must be positive (absolute).")
        return None
    return si


def _fraction(rd, v, path, lo=0.0, hi=1.0):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo < v < hi:
        rd.add("invalid", "EOS_DIAG_INVALID_DATA", path, f"A mole fraction strictly between {lo:g} and {hi:g}.")
        return None
    return float(v)


def _read(body, rd):
    rid = body.get("requestId") if isinstance(body, dict) and isinstance(body.get("requestId"), str) else ""
    if not isinstance(body, dict):
        rd.add("invalid", "EOS_DIAG_INVALID_DATA", "", "The body must be an object.")
        return rid, None, None
    op = body.get("operation")
    if op not in OPERATIONS:
        rd.add("invalid", "EOS_DIAG_INVALID_DATA", "operation", f"Operation must be one of {', '.join(OPERATIONS)}.")
        return rid, None, None
    for k in body:
        if k not in FIELDS | OP_FIELDS[op]:
            rd.add("invalid", "EOS_DIAG_INVALID_DATA", k, f"Field not accepted: {k}.")
    for k in ("revision", "requestId", "package", "components", "points") + tuple(sorted(OP_FIELDS[op])):
        if k not in body and not (k == "fractionRange" or k == "kind"):
            rd.add("incomplete", "EOS_DIAG_INVALID_DATA", k, f"Missing {k}.")
    if "revision" in body and (isinstance(body["revision"], bool) or body["revision"] != REVISION):
        rd.add("invalid", "EOS_DIAG_REVISION", "revision", f"Revision {body['revision']!r} is not accepted; this is {REVISION}.")
    if "requestId" in body and (not isinstance(body["requestId"], str) or not body["requestId"]):
        rd.add("invalid", "EOS_DIAG_INVALID_DATA", "requestId", "Empty request identifier.")
    pk = body.get("package")
    pid = None
    if "package" in body:
        if not isinstance(pk, dict) or set(pk) != {"id", "version"}:
            rd.add("invalid", "EOS_DIAG_INVALID_DATA", "package", "Expected {id, version}.")
        elif PACKAGES.get(pk["id"]) != pk["version"]:
            rd.add("unsupported", "EOS_DIAG_PACKAGE", "package",
                   f"Package {pk['id']!r} version {pk['version']!r} is not an EOS diagram package ("
                   f"{', '.join(PACKAGES)}); it is not replaced by another.")
        else:
            pid = pk["id"]
    n_pts = body.get("points")
    if "points" in body and (isinstance(n_pts, bool) or not isinstance(n_pts, int) or not 2 <= n_pts <= LIMITS[op]):
        rd.add("invalid", "EOS_DIAG_INVALID_DATA", "points", f"An integer between 2 and {LIMITS[op]} for this operation.")
        n_pts = None
    comps, ids, cas = body.get("components"), [], []
    if "components" in body:
        if not isinstance(comps, list):
            rd.add("invalid", "EOS_DIAG_INVALID_DATA", "components", "Expected a list.")
            comps = []
        for k, c in enumerate(comps):
            cid = c.get("id") if isinstance(c, dict) else None
            ca = (c.get("identidadQuimica") or {}).get("cas") if isinstance(c, dict) else None
            if isinstance(cid, bool) or not isinstance(cid, int) or cid < 1:
                rd.add("invalid", "EOS_DIAG_INVALID_DATA", f"components.{k}.id", "A positive integer ID is required.")
            elif not isinstance(ca, str) or not mt._cas_valido(ca):
                rd.add("invalid", "EOS_DIAG_INVALID_DATA", f"components.{k}.identidadQuimica.cas",
                       "Chemical identity without a valid CAS: a name does not identify a model.", [cid])
            else:
                ids.append(cid)
                cas.append(ca)
        if len(set(ids)) != len(ids) or len(set(cas)) != len(cas):
            rd.add("invalid", "EOS_DIAG_INVALID_DATA", "components", "Repeated component IDs or substances.")
        lo, hi = (2, None) if op == "saturation_curve" else (2, 2)
        if len(comps) < lo or (hi is not None and len(comps) > hi):
            rd.add("unsupported", "EOS_DIAG_COMPONENTS", "components",
                   f"{op} needs {'at least 2' if hi is None else 'exactly 2'} components; {len(comps)} were declared. "
                   "No component is removed or renormalized.")
    q = {"op": op, "pid": pid, "ids": ids, "cas": cas, "points": n_pts}
    if op == "saturation_curve":
        comp = body.get("composition")
        kind = body.get("kind", "bubble")
        if kind not in ("bubble", "dew"):
            rd.add("invalid", "EOS_DIAG_INVALID_DATA", "kind", "'bubble' or 'dew'.")
        z = None
        if "composition" in body:
            if not isinstance(comp, dict) or sorted(comp) != sorted(str(i) for i in ids):
                rd.add("invalid", "EOS_DIAG_INVALID_DATA", "composition", "One mole fraction per declared component ID.")
            else:
                vals = [_fraction(rd, comp[str(i)], f"composition.{i}") for i in ids]
                if None not in vals:
                    if abs(sum(vals) - 1.0) > 1e-9:
                        rd.add("invalid", "EOS_DIAG_INVALID_DATA", "composition", "Mole fractions must sum to 1 (no renormalization).")
                    else:
                        z = np.array(vals)
        tr = body.get("temperatureRange")
        T0 = T1 = None
        if "temperatureRange" in body:
            if not isinstance(tr, dict) or set(tr) != {"from", "to"}:
                rd.add("invalid", "EOS_DIAG_INVALID_DATA", "temperatureRange", "Expected {from, to}.")
            else:
                T0 = _quantity(rd, tr["from"], "temperatureRange.from", "T")
                T1 = _quantity(rd, tr["to"], "temperatureRange.to", "T")
                if T0 and T1 and not T0 < T1:
                    rd.add("invalid", "EOS_DIAG_INVALID_DATA", "temperatureRange", "'from' must be below 'to'.")
        q.update(kind=kind, z=z, T0=T0, T1=T1)
    else:
        if op == "isotherm":
            cond = body.get("condition")
            T = None
            if "condition" in body:
                if not isinstance(cond, dict) or set(cond) != {"T"}:
                    rd.add("invalid", "EOS_DIAG_INVALID_DATA", "condition", "Expected exactly {T}.")
                else:
                    T = _quantity(rd, cond["T"], "condition.T", "T")
            q["T"] = T
        fr = body.get("fractionRange", [0.02, 0.98] if op == "isotherm" else [0.05, 0.95])
        if (not isinstance(fr, list) or len(fr) != 2 or _fraction(rd, fr[0], "fractionRange.0") is None
                or _fraction(rd, fr[1], "fractionRange.1") is None or not fr[0] < fr[1]):
            if not any(d["path"].startswith("fractionRange") for d in rd.diagnostics):
                rd.add("invalid", "EOS_DIAG_INVALID_DATA", "fractionRange", "Expected [from, to] with from < to.")
        q["fr"] = fr
    return rid, q, op


def _signature(q, extra):
    data = {"op": q["op"], "package": q["pid"], "cas": q["cas"], "points": q["points"], **extra}
    return "sha256:" + hashlib.sha256(json.dumps(data, sort_keys=True, default=float).encode()).hexdigest()


def _eos(pid, cas):
    if pid == capa.PSRK:
        return capa._ecuacion_estado(pid, tuple(cas))
    return _PR(tuple(cas))


def _located(e):
    d = dict(getattr(e, "datos", {}) or {})
    return {"cause": d.get("cause", "not_converged"), "message": str(e)[:300]}


def _certificate(c):
    return {"fugacity": float(c["fugacity"]), "normalization": float(c["normalization"]),
            "distinction": float(c["distinction"]), "tolerance": TOL_CERT, "status": "pass" if c["ok"] else "fail"}


def _comp(ids, x):
    return {str(i): float(v) for i, v in zip(ids, x)}


def _dew(eos, T, z, guess):
    r = cubic_flash.saturation(eos, z, T=T, kind="dew", guess=guess)
    if np.max(np.abs(r["u"][:-1])) < psrk.TOL_LNK_TRIVIAL:
        raise CubicOutOfScope("Dew-point equations converge only to the trivial solution.", cause="trivial_solution", T=T)
    w = r["w"]
    if float(np.max(np.abs(w - z))) < psrk.TOL_NEAR_CRITICAL:
        raise CubicOutOfScope("Within the unresolved neighbourhood of the critical point.", cause="near_critical_unresolved", T=T)
    cert = psrk.certify_saturation(eos, T, r["P"], w, z)
    if cert["ok"] and not eos.phase(T, r["P"], w, "liquid")["Z"] < eos.phase(T, r["P"], z, "vapor")["Z"]:
        raise CubicOutOfScope("The incipient liquid is not denser than the feed vapor.", cause="past_critical_point", T=T)
    if not cert["ok"]:
        raise CubicOutOfScope("Dew point failed its certificate.", cause="not_certified", T=T)
    return {"T": T, "P": r["P"], "x": w, "y": z, "u": r["u"], "certificate": cert}


def _saturation_curve(q, eos, deadline):
    pts, rej, guess = [], [], None
    Ts = np.linspace(q["T0"], q["T1"], q["points"])
    for T in Ts:
        if time.monotonic() > deadline:
            rej.append({"T": float(T), "cause": "budget_exhausted", "message": "The time budget ended before this point."})
            continue
        try:
            if q["kind"] == "bubble":
                r = psrk.bubble_pressure(eos, float(T), q["z"], guess=guess)
            else:
                eos.check_temperature(float(T))
                r = _dew(eos, float(T), q["z"], guess)
        except (CubicOutOfScope, np.linalg.LinAlgError, ValueError, OverflowError) as e:
            rej.append({"T": float(T), **_located(e)})
            guess = None
            continue
        guess = r["u"]
        pts.append({"T": float(T), "P": float(r["P"]), "liquid": _comp(q["ids"], r["x"]), "vapor": _comp(q["ids"], r["y"]),
                    "certificate": _certificate(r["certificate"])})
    return pts, rej


def _isotherm(q, eos, deadline):
    lo, hi = q["fr"]
    xs = np.linspace(lo, hi, q["points"])
    pts, rej = [], []
    if time.monotonic() > deadline:
        return pts, [{"x": float(x), "cause": "budget_exhausted", "message": "The time budget ended."} for x in xs]
    try:
        eos.check_temperature(q["T"])
        good, bad = psrk.bubble_isotherm(eos, q["T"], list(xs), j=0)
    except (CubicOutOfScope, np.linalg.LinAlgError, ValueError, OverflowError) as e:
        return pts, [{"x": float(x), **_located(e)} for x in xs]
    for r in good:
        pts.append({"T": float(q["T"]), "P": float(r["P"]), "liquid": _comp(q["ids"], r["x"]), "vapor": _comp(q["ids"], r["y"]),
                    "certificate": _certificate(r["certificate"])})
    for b in bad:
        rej.append({"x": float(b["x"][0]), "cause": b["cause"], "message": str(b.get("message", ""))[:300]})
    return pts, rej


def _critical_locus(q, pid, eos, deadline):
    lo, hi = q["fr"]
    xs = np.linspace(lo, hi, q["points"])
    pts, rej = [], []
    for x in xs:
        if time.monotonic() > deadline:
            rej.append({"x": float(x), "cause": "budget_exhausted", "message": "The time budget ended before this point."})
            continue
        z = np.array([x, 1.0 - x])
        try:
            roots = psrk.critical_points(eos, z, **PSRK_KAPPA) if pid == capa.PSRK else cc.critical_points(eos, z)
        except (CubicOutOfScope, np.linalg.LinAlgError, ValueError, OverflowError) as e:
            rej.append({"x": float(x), **_located(e)})
            continue
        p = max(roots, key=lambda r: r["T"])
        pts.append({"x": float(x), "composition": _comp(q["ids"], z), "T": float(p["T"]), "P": float(p["P"]),
                    "V": float(p["V"]), "kappa": float(p["kappa"]), "kind": p["kind"], "roots": len(roots)})
    return pts, rej


def compute(body):
    rd = _Reader()
    rid, q, op = _read(body, rd)
    if q is None or rd.statuses() & set(STATUS_ORDER):
        st = next(s for s in STATUS_ORDER if s in rd.statuses())
        pkg = {"id": q["pid"], "version": PACKAGES[q["pid"]]} if q and q["pid"] else None
        return _empty(rid, op or "", st, rd.diagnostics, pkg)
    pkg = {"id": q["pid"], "version": PACKAGES[q["pid"]]}
    try:
        eos = _eos(q["pid"], q["cas"])
    except Exception as e:     # missing catalog / UNIFAC / PSRK record: a located rejection with its own text
        rd.add("unsupported", "EOS_DIAG_NO_DATA", "components", f"{q['pid']} cannot be built for these species: {e}", q["ids"])
        return _empty(rid, op, "unsupported", rd.diagnostics, pkg)
    deadline = time.monotonic() + BUDGET_SECONDS
    t0 = time.monotonic()
    if op == "saturation_curve":
        pts, rej = _saturation_curve(q, eos, deadline)
        extra = {"kind": q["kind"], "z": q["z"].tolist(), "T": [q["T0"], q["T1"]]}
    elif op == "isotherm":
        pts, rej = _isotherm(q, eos, deadline)
        extra = {"T": q["T"], "fr": q["fr"]}
    else:
        pts, rej = _critical_locus(q, q["pid"], eos, deadline)
        extra = {"fr": q["fr"]}
    status = "ok" if pts and not rej else ("partial" if pts else "no_points")
    if rej:
        rd.add("incomplete" if pts else "unsupported", "EOS_DIAG_REJECTED_POINTS", "points",
               f"{len(rej)} requested point(s) are located rejections with their cause (see `rejected`).")
    return {"revision": REVISION, "requestId": rid, "operation": op, "status": status,
            "identity": {"package": pkg, "querySignature": _signature(q, extra),
                         "components": [{"id": i, "cas": c} for i, c in zip(q["ids"], q["cas"])]},
            "units": {"T": "K", "P": "Pa", "V": "m3/mol"}, "points": pts, "rejected": rej,
            "budget": {"seconds": round(time.monotonic() - t0, 3), "limitSeconds": BUDGET_SECONDS},
            "diagnostics": rd.diagnostics}
