"""
Three-liquid (L-L-L) regions of a ternary (f8b, second extension).

At fixed T and P a ternary with three coexisting liquids has no degree of freedom (Gibbs: F = C - pi + 2 = 0
with T and P fixed), so the region is a triangle whose vertices are the three liquids. At fixed P the
triangle is a one-parameter family in T that ends where its liquids become identical or unstable, where
the Newton family folds, or where a vapor appears: the L-L-L-V four-phase point (F = 0 at fixed P).

This module extends the shared ternary layer (core/ternary_liquid_liquid.py: coordinates, certificate,
binodal tracer) and the package's own stability test and TP flash. It contains no activity formula: the
package's chemical potentials are the only condition.

- triangle(sis, T, P, xa, xb, xc): the six equalities mu_i^a = mu_i^b = mu_i^c in softmax coordinates,
  solved by the shared damped Newton and certified (equal mu, distinct phases, tangent plane against
  vapor and liquid trials).
- region(sis, T, P): every certified triangle at (T, P). Seeds come from the TP flash on a lattice of
  feeds (a flash that publishes three liquids) and from the ends of the two-liquid branches of the
  ternary tracer that stop because a third liquid lowers their tangent plane. Each side of a triangle is
  the limiting tie line of the adjacent two-liquid region; the region publishes, per side, the branch
  whose end lies on it.
- phase_amounts(tri, z): the lever rule (mass balance of the three liquids); z is inside the region if and
  only if all three amounts are non-negative.
- sweep_temperature(sis, P, tri, T_end): the triangle followed in T at fixed P from a certified triangle,
  with step halving and a located end: a four-phase invariant where a vapor (L-L-L-V) or a fourth liquid
  (L-L-L-L) lowers the tangent plane, solved exactly from the bisected bracket; otherwise no convergence
  (bisected; a fold or a collapse of the family) or the package domain.
"""

import math

import numpy as np

from core import coexistencia_ll as ll
from core import mezclas as mz
from core import ternary_liquid_liquid as tll

IDX = tll.IDX
DUPLICATE = 1e-6                  # max vertex distance at which two triangles are the same
LATTICE = 8
MERGE_GAP = 0.02                  # last-triangle gap below which a lost family is a critical end point


def _vertices_key(xs):
    """Vertices ordered by their dominant species, then by composition (deterministic publication)."""
    return sorted((np.asarray(x, float) for x in xs), key=lambda x: (int(np.argmax(x)), tuple(-x)))


def triangle_residual(sis, T, P, v):
    xa, xb, xc = tll.comp(v[0], v[1]), tll.comp(v[2], v[3]), tll.comp(v[4], v[5])
    ma = tll._mu(sis, T, P, xa)
    return np.concatenate([ma - tll._mu(sis, T, P, xb), ma - tll._mu(sis, T, P, xc)]) / (mz.R * T)


def triangle(sis, T, P, xa, xb, xc):
    """Certified L-L-L triangle from three seed liquids. dict, ll.NoConvergence, or mz.FueraDeAlcance outside
    the package domain (checked here, at the entry point, not only by the callers)."""
    sis.dominio(T, P)
    v, iters = ll._solve(lambda w: triangle_residual(sis, T, P, w),
                         tll.logits(xa) + tll.logits(xb) + tll.logits(xc), "three-liquid triangle")
    xs = _vertices_key([tll.comp(v[0], v[1]), tll.comp(v[2], v[3]), tll.comp(v[4], v[5])])
    cert = tll.certify(sis, T, P, [("liquido", x) for x in xs])
    return {"T": T, "P": P, "liquids": xs, "certificate": cert, "newtonIterations": iters}


def phase_amounts(tri, z):
    """Lever rule: amounts (per mol of feed) of the three liquids that reproduce z. Inside iff all >= 0."""
    A = np.column_stack(tri["liquids"])
    return np.linalg.solve(A, np.asarray(z, float))


def _same(t1, t2):
    return max(float(np.max(np.abs(a - b))) for a, b in zip(t1["liquids"], t2["liquids"])) < DUPLICATE


def region(sis, T, P, lattice=LATTICE, profile="exploratoria", branches=None):
    """Every certified three-liquid triangle at (T, P), with the two-liquid branches that end on its sides."""
    sis.dominio(T, P)
    seeds = []
    for i in range(lattice + 1):
        for j in range(lattice + 1 - i):
            z = 0.02 / 3 + 0.98 * np.array([i, j, lattice - i - j], dtype=float) / lattice
            try:
                e = sis.equilibrio_TP(T, P, z)
            except mz.FueraDeAlcance:
                continue
            liq = [np.asarray(f.x, float)[IDX] for f in e.fases if f.tipo == "liquido"]
            if len(liq) == 3:
                seeds.append(("tp_flash", liq))
    if branches is None:
        branches = tll.trace(sis, T, P, tll.PROFILES[profile])
    for b in branches:
        for end in b.ends:
            comp_ = end.get("competidora") if end.get("tipo") == "inestable" else None
            if comp_ and comp_["tipo"] == "liquido" and b.points:
                last = b.points[0] if end is b.ends[0] else b.points[-1]
                seeds.append(("branch_end", [last["xa"], last["xb"], np.asarray(comp_["composicion"], float)]))
    triangles, failures = [], []
    for origin, liq in seeds:
        try:
            tri = triangle(sis, T, P, *liq)
        except ll.NoConvergence as x:
            failures.append({"origin": origin, "message": x.mensaje})
            continue
        if any(_same(tri, t) for t in triangles):
            continue
        tri["origin"] = origin
        triangles.append(tri)
    certified = [t for t in triangles if t["certificate"]["estado"] == "cumple"]
    for tri in certified:
        tri["sides"] = _sides(tri, branches)
    return {"T": T, "P": P, "triangles": certified,
            "uncertified": [t for t in triangles if t["certificate"]["estado"] != "cumple"],
            "failures": failures, "branches": branches, "seeds": len(seeds)}


def _sides(tri, branches):
    """For each side (pair of liquids) the two-liquid branch end nearest to it and its distance."""
    out = []
    xs = tri["liquids"]
    for i, j in ((0, 1), (0, 2), (1, 2)):
        best = None
        for k, b in enumerate(branches):
            for end_pos, end in ((0, b.ends[0]), (-1, b.ends[-1])):
                if not b.points:
                    continue
                p = b.points[end_pos] if len(b.ends) > 1 else b.points[-1]
                d = min(max(float(np.max(np.abs(p["xa"] - xs[i]))), float(np.max(np.abs(p["xb"] - xs[j])))),
                        max(float(np.max(np.abs(p["xa"] - xs[j]))), float(np.max(np.abs(p["xb"] - xs[i])))))
                if best is None or d < best["distance"]:
                    best = {"branch": k, "end": end.get("tipo"), "distance": d}
        out.append({"liquids": [i, j], "nearestBranchEnd": best})
    return out


def _four_phase(sis, P, tri, y0, kind="vapor"):
    """Four-phase invariant at fixed P from a triangle and the competing trial of `kind`: L-L-L-V (vapor) or
    L-L-L-L (a fourth liquid). Unknowns (three liquids, the fourth phase, T); nine mu equalities."""
    q0 = tri["T"]

    def F(w):
        T = w[8] * q0
        sis.dominio(T, P)                     # an iterate or a root outside the package domain is no solution
        xa, xb, xc, y = (tll.comp(w[2 * k], w[2 * k + 1]) for k in range(4))
        ma = tll._mu(sis, T, P, xa)
        return np.concatenate([ma - tll._mu(sis, T, P, xb), ma - tll._mu(sis, T, P, xc),
                               ma - tll._mu(sis, T, P, y, kind)]) / (mz.R * T)
    w0 = sum((tll.logits(x) for x in tri["liquids"]), []) + tll.logits(np.maximum(y0, 1e-300)) + [1.0]
    w, iters = ll._solve(F, w0, "four-phase point")
    T = w[8] * q0
    xs = _vertices_key([tll.comp(w[2 * k], w[2 * k + 1]) for k in range(3)])
    y = tll.comp(w[6], w[7])
    cert = tll.certify(sis, T, P, [("liquido", x) for x in xs] + [(kind, y)])
    return {"T": T, "P": P, "liquids": xs, "fourthPhase": {"kind": kind, "composition": y}, "certificate": cert,
            "newtonIterations": iters}


def sweep_temperature(sis, P, tri, T_end, dT=2.0, min_dT=1e-6, bisections=40):
    """Follow a certified triangle in T at fixed P toward T_end. Returns (triangles, end). Every published
    triangle carries a certificate computed for it; the seed's own certificate is never carried over, and a seed
    that does not certify (or lies outside the package domain) ends the sweep before any step."""
    try:
        sis.dominio(tri["T"], P)
        seed_cert = tll.certify(sis, tri["T"], P, [("liquido", np.asarray(x, float)) for x in tri["liquids"]])
    except mz.FueraDeAlcance as x:
        return [], {"kind": "domain_limit", "message": x.mensaje, "T": tri["T"]}
    tri = dict(tri, P=P, liquids=[np.asarray(x, float) for x in tri["liquids"]], certificate=seed_cert)
    if seed_cert["estado"] != "cumple":
        return [tri], {"kind": "seed_not_certified", "T": tri["T"]}
    out = [tri]
    sign = 1.0 if T_end > tri["T"] else -1.0
    step = abs(dT)
    cur = tri
    while True:
        if abs(T_end - cur["T"]) < 1e-12:
            return out, {"kind": "requested_limit", "T": cur["T"]}
        Tn = cur["T"] + sign * min(step, abs(T_end - cur["T"]))
        state, new = _try(sis, Tn, P, cur)
        if state == "certified":
            out.append(new)
            cur = new
            step = min(2 * step, abs(dT))
            continue
        if step > min_dT:
            # locate the end by bisection between the last certified triangle and the failing T
            lo, hi, bad = cur, Tn, (state, new)
            for _ in range(bisections):
                Tm = 0.5 * (lo["T"] + hi)
                s_m, n_m = _try(sis, Tm, P, lo)
                if s_m == "certified":
                    lo = n_m
                else:
                    hi, bad = Tm, (s_m, n_m)
                if abs(hi - lo["T"]) < min_dT:
                    break
            if lo is not cur:
                out.append(lo)
            state, new = bad
            cur = lo
        comp_ = (new or {}).get("certificate", {}).get("estabilidad", {}).get("competidora") if new else None
        if state == "uncertified" and comp_:
            # a vapor (L-L-L-V) or a fourth liquid (L-L-L-L) lowers the tangent plane: the invariant at fixed P
            try:
                fp = _four_phase(sis, P, cur, np.asarray(comp_["composicion"], float), comp_["tipo"])
                return out, {"kind": "four_phase_point", "point": fp}
            except ll.NoConvergence as x:
                return out, {"kind": "four_phase_point_not_solved", "message": x.mensaje, "T": cur["T"],
                             "competitor": comp_}
        gaps = [(float(np.max(np.abs(cur["liquids"][i] - cur["liquids"][j]))), [i, j]) for i, j in ((0, 1), (0, 2), (1, 2))]
        gap, pair = min(gaps)
        if (state == "no_convergence" or _merged_liquids(state, new)) and gap < MERGE_GAP:
            # two liquids of the family merge: a critical end point (L=L critical with the third liquid present);
            # published as a bracket, the critical condition itself is not solved here
            return out, {"kind": "critical_end_point_bracket", "lastCertifiedT": cur["T"], "mergingLiquids": pair,
                         "gap": gap, "bracket": abs(hi - cur["T"]) if step > min_dT else None}
        return out, {"kind": "certification_lost" if state == "uncertified" else state,
                     "lastCertifiedT": cur["T"], "bracket": abs(hi - cur["T"]) if step > min_dT else None,
                     "competitor": comp_}


def _merged_liquids(state, new):
    """True when a triangle failed certification only because two of its liquids are no longer distinct: the
    chemical potentials still agree and no other phase lowers the tangent plane, so the loss is the collapse of the
    family onto a critical end point. Within round-off of that point the Newton step may either fail to converge or
    return the collapsed triangle, so which of the two states is reported depends on the BLAS kernel; both are the
    same event and must be classified alike."""
    if state != "uncertified" or not new:
        return False
    cert = new["certificate"]
    failed = {r["id"] for r in cert["residuos"] if r["estado"] != "cumple"}
    return failed == {"distincion_fases"} and cert["estabilidad"]["estado"] == "estable"


def _try(sis, T, P, seed):
    try:
        sis.dominio(T, P)
        new = triangle(sis, T, P, *seed["liquids"])
    except mz.FueraDeAlcance:
        return "domain_limit", None
    except ll.NoConvergence:
        return "no_convergence", None
    jump = max(float(np.max(np.abs(a - b))) for a, b in zip(new["liquids"], seed["liquids"]))
    if jump > 0.1:                       # the Newton left the family (e.g. collapsed onto another solution)
        return "no_convergence", None
    return ("certified" if new["certificate"]["estado"] == "cumple" else "uncertified"), new
