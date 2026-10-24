"""
Ternary liquid-liquid equilibrium at fixed T and P: the binodal with its tie lines, the plait point, the
ends on a binary edge and the liquid-liquid-vapor three-phase triangle. A shared operation of a mixture
package, on the same pseudo-arclength continuation as the binary branches (core/coexistencia_ll.py).

Only the package's public interface is used: `mu(tipo, T, P, x, idx)`, `prueba_estabilidad`, `dominio` and
`equilibrio_TP`. There is no activity formula here; the package's chemical potentials are the only condition.

Coordinates. A liquid composition is x = softmax(z0, z1, 0) (species 0 and 1 against species 2), so every
species stays strictly positive and traces are represented without cancellation. A tie line is
v = (za0, za1, zb0, zb1); F(v) = (mu^L(xa) - mu^L(xb)) / RT = 0 gives three equations in four unknowns, a curve
followed by pseudo-arclength continuation in both directions from a certified-flash seed.

Ends of a binodal branch:
- plait point: the two liquids merge. With h_i = (mu_i - mu_2) / RT (the gradient of g/RT in x0, x1), the
  spinodal is det H = 0 (H = dh/dx) and the critical condition is d/dt [u^T H(x + t u) u] = 0 along the null
  vector u of H; both are solved in (logit x0, logit x1) with central differences of h;
- binary edge: one species vanishes from both liquids; the end is the binary pair of the other two species at
  the same T and P, solved directly;
- three-phase triangle: a vapor trial lowers the tangent plane; (xa, xb, y) is solved from the six mu
  equalities (an invariant at fixed T and P) and certified;
- budget or no convergence, published as such.
"""

import math

import numpy as np

from core import coexistencia_ll as ll
from core import mezclas as mz

IDX = [0, 1, 2]
TOL_MU = mz.TOL_MU
TOL_TM = mz.TOL_TM
MERGE_GAP = 3e-3                  # max |xa - xb| at which a branch hands over to the plait point
EDGE_FRACTION = 1e-9              # a species below this in both liquids: the branch reached a binary edge
PROFILES = {"exploratoria": {"dsMax": 0.25, "lattice": 10}, "refinada": {"dsMax": 0.08, "lattice": 14}}
TRAZADOR = {"id": "trazador-ll-ternario", "version": "1"}


def comp(z0, z1):
    m = max(z0, z1, 0.0)
    e = np.exp(np.array([z0, z1, 0.0]) - m)
    return e / e.sum()


def logits(x):
    x = np.asarray(x, dtype=float)
    return [math.log(x[0]) - math.log(x[2]), math.log(x[1]) - math.log(x[2])]


def _mu(sis, T, P, x, kind="liquido"):
    return sis.mu(kind, T, P, np.asarray(x, dtype=float), IDX)


def binodal_residual(sis, T, P, v):
    xa, xb = comp(v[0], v[1]), comp(v[2], v[3])
    return (_mu(sis, T, P, xa) - _mu(sis, T, P, xb)) / (mz.R * T)


def three_phase_residual(sis, T, P, v):
    xa, xb, y = comp(v[0], v[1]), comp(v[2], v[3]), comp(v[4], v[5])
    ma = _mu(sis, T, P, xa)
    return np.concatenate([ma - _mu(sis, T, P, xb), ma - _mu(sis, T, P, y, "vapor")]) / (mz.R * T)


def certify(sis, T, P, phases):
    """Certificate of a coexistence of phases [(kind, x)] at (T, P): mu equality of every species between all
    phases, normalization, distinct phases and the tangent plane with the common mu."""
    RT = mz.R * T
    mus = [_mu(sis, T, P, x, k) for k, x in phases]
    r_mu = max(float(np.max(np.abs(m - mus[0]))) for m in mus[1:]) / RT
    r_n = max(abs(float(np.sum(x)) - 1.0) for _, x in phases)
    gap = min(float(np.max(np.abs(np.asarray(a) - np.asarray(b))))
              for i, (_, a) in enumerate(phases) for _, b in phases[i + 1:])
    res = [ll._residue("igualdad_mu", r_mu, TOL_MU, "R T"),
           ll._residue("normalizacion", r_n, 1e-14, "1", r_n <= 1e-14 and all(np.all(np.asarray(x) > 0) for _, x in phases)),
           ll._residue("distincion_fases", gap, ll.MIN_GAP, "min max |x_a - x_b| entre fases", gap > ll.MIN_GAP)]
    pr = sis.prueba_estabilidad(T, P, mus[0], IDX, incluir_vapor=True)
    tm_min = min(q[2] for q in pr)
    est = {"estado": "estable" if tm_min >= -TOL_TM else "inestable", "tmMinimo": float(tm_min),
           "tolerancia": TOL_TM, "candidatas": sorted({q[0] for q in pr}), "pruebas": len(pr),
           "metodo": "distancia al plano tangente con la mu comun: vapor por minimo analitico, liquido en la red "
                     "ternaria de 1891 puntos con refinamiento de sus 12 minimos mas bajos (no es una demostracion "
                     "del minimo global)"}
    if tm_min < -TOL_TM:
        q = min(pr, key=lambda q: q[2])
        est["competidora"] = {"tipo": q[0], "composicion": [float(w) for w in q[1]], "tm": float(q[2])}
    ok = all(r["estado"] == "cumple" for r in res) and est["estado"] == "estable"
    return {"estado": "cumple" if ok else "no_cumple", "residuos": res, "estabilidad": est}


# --- seeds -------------------------------------------------------------------------------------------------
def seeds(sis, T, P, lattice=10, spend=lambda n=1: None, exhausted=lambda: False):
    """Tie lines from the package's certified TP flash at interior lattice feeds whose single-liquid reference
    the tangent-plane test finds unstable against another liquid: [v]."""
    out = []
    for i in range(lattice + 1):
        for j in range(lattice + 1 - i):
            if exhausted():
                return out
            # lattice points pulled 2 % inside the simplex, so edge regions are explored with every species present
            z = 0.02 / 3 + 0.98 * np.array([i, j, lattice - i - j], dtype=float) / lattice
            spend()
            pr = sis.prueba_estabilidad(T, P, _mu(sis, T, P, z), IDX, incluir_vapor=False)
            if min(t[2] for t in pr) >= -1e-6:
                continue
            spend(20)
            try:
                e = sis.equilibrio_TP(T, P, z)
            except mz.FueraDeAlcance:
                continue
            liq = [f.x[IDX] for f in e.fases if f.tipo == "liquido"]
            if len(e.fases) == 2 and len(liq) == 2 and np.max(np.abs(liq[0] - liq[1])) > 10 * MERGE_GAP:
                out.append(np.array(logits(liq[0]) + logits(liq[1])))
    return out


# --- plait point -------------------------------------------------------------------------------------------
def _h(sis, T, P, x0, x1):
    m = _mu(sis, T, P, [x0, x1, 1.0 - x0 - x1])
    return np.array([m[0] - m[2], m[1] - m[2]]) / (mz.R * T)


def _hessian(sis, T, P, x, d):
    H = np.empty((2, 2))
    for j in range(2):
        e = np.zeros(2)
        e[j] = d
        H[:, j] = (_h(sis, T, P, *(x + e)) - _h(sis, T, P, *(x - e))) / (2 * d)
    return 0.5 * (H + H.T)


def plait_residual(sis, T, P, w, d=1e-4, t=2e-3):
    """(det H scaled, cubic form along the null vector) at x = softmax(w0, w1, 0)."""
    x3 = comp(w[0], w[1])
    x = x3[:2]
    s = float(np.min(x3))
    d, t = d * s, t * s
    H = _hessian(sis, T, P, x, d)
    vals, vecs = np.linalg.eigh(H)
    u = vecs[:, int(np.argmin(np.abs(vals)))]
    Hp, Hm = _hessian(sis, T, P, x + t * u, d), _hessian(sis, T, P, x - t * u, d)
    cubic = float(u @ ((Hp - Hm) / (2 * t)) @ u)
    scale = float(np.prod(x3))
    return np.array([np.linalg.det(H) * scale, cubic * scale ** 1.5])


def plait_point(sis, T, P, x_guess):
    """x of the plait point near x_guess, and its residual. NoConvergence if not found."""
    F = lambda w: plait_residual(sis, T, P, w)
    try:
        w, f, _ = ll._newton(F, logits(x_guess))
    except (np.linalg.LinAlgError, FloatingPointError, OverflowError, ValueError) as x:
        raise ll.NoConvergence("no_convergente", f"plait point: {x}")
    if not np.max(np.abs(f)) < 1e-6:
        raise ll.NoConvergence("no_convergente", f"plait point: final residual {np.max(np.abs(f)):.2e}")
    return comp(w[0], w[1]), float(np.max(np.abs(f)))


# --- binary edge -------------------------------------------------------------------------------------------
def edge_pair(sis, T, P, k, xa, xb):
    """Binary pair of the two species other than k at (T, P), from the branch's last pair. (xa, xb) full."""
    keep = [i for i in IDX if i != k]

    def F(v):
        a, b = ll._pair(v[0]), ll._pair(v[1])
        return (sis.mu("liquido", T, P, a, keep) - sis.mu("liquido", T, P, b, keep)) / (mz.R * T)
    ra = xa[keep[0]] / (xa[keep[0]] + xa[keep[1]])
    rb = xb[keep[0]] / (xb[keep[0]] + xb[keep[1]])
    v, _ = ll._solve(F, [ll._logit(ra), ll._logit(rb)], "binary edge")
    out = []
    for u in v:
        x = np.zeros(3)
        x[keep] = ll._pair(u)
        out.append(x)
    return out


# --- three-phase triangle ----------------------------------------------------------------------------------
def three_phase(sis, T, P, xa, xb, y):
    v, _ = ll._solve(lambda w: three_phase_residual(sis, T, P, w), logits(xa) + logits(xb) + logits(y),
                     "three-phase triangle")
    return comp(v[0], v[1]), comp(v[2], v[3]), comp(v[4], v[5])


# --- continuation ------------------------------------------------------------------------------------------
def _tangent(sis, T, P, v, prev=None):
    J = ll._jacobian(lambda w: binodal_residual(sis, T, P, w), v)
    t = np.linalg.svd(J)[2][-1]
    if prev is not None and float(t @ prev) < 0:
        t = -t
    return t


def _accept(sis, T, P, v, origen):
    xa, xb = comp(v[0], v[1]), comp(v[2], v[3])
    return {"v": v.copy(), "xa": xa, "xb": xb, "cert": certify(sis, T, P, [("liquido", xa), ("liquido", xb)]),
            "origen": origen}


def _walk(sis, T, P, v0, t, profile, spend, exhausted, max_points):
    ds_max, ds_min = profile["dsMax"], 1e-6
    ds = 0.25 * ds_max
    v, pts, last = v0.copy(), [], None
    prev_diff = comp(v0[0], v0[1]) - comp(v0[2], v0[3])
    while len(pts) < max_points:
        if exhausted():
            return pts, {"tipo": "presupuesto"}
        spend()
        pred = v + ds * t

        def G(w):
            return np.concatenate([binodal_residual(sis, T, P, w), [float(t @ (w - v)) - ds]])
        try:
            w, iters = ll._solve(G, pred, "ternary binodal")
        except ll.NoConvergence as x:
            if ds > ds_min:
                ds *= 0.5
                continue
            return pts, {"tipo": x.motivo, "mensaje": x.mensaje}
        xa, xb = comp(w[0], w[1]), comp(w[2], w[3])
        if float(np.max(np.abs(xa - xb))) < MERGE_GAP:
            return pts, _plait_end(sis, T, P, xa, xb)
        if float((xa - xb) @ prev_diff) <= 0:
            # the liquids exchanged their sides: the step went through the plait point
            if ds > ds_min:
                ds *= 0.5
                continue
            return pts, _plait_end(sis, T, P, xa, xb)
        edge = [k for k in IDX if max(xa[k], xb[k]) < EDGE_FRACTION]
        if edge:
            return pts, _edge_end(sis, T, P, edge[0], xa, xb)
        p = _accept(sis, T, P, w, "continuacion")
        if p["cert"]["estado"] != "cumple":
            est = p["cert"]["estabilidad"]
            if est["estado"] == "inestable" and ds > 16 * ds_min:
                ds *= 0.5
                continue
            comp_ = est.get("competidora")
            if comp_ and comp_["tipo"] == "vapor":
                return pts, _three_phase_end(sis, T, P, last or _accept(sis, T, P, v, "continuacion"),
                                             comp_["composicion"])
            return pts, {"tipo": "inestable", "mensaje": "another phase lowers the tangent plane", "competidora": comp_}
        t = _tangent(sis, T, P, w, t)
        v = w
        prev_diff = xa - xb
        pts.append(p)
        last = p
        if iters <= 4:
            ds = min(1.5 * ds, ds_max)
    return pts, {"tipo": "presupuesto", "mensaje": "point limit of the branch"}


def _plait_end(sis, T, P, xa, xb):
    try:
        x, res = plait_point(sis, T, P, 0.5 * (xa + xb))
    except ll.NoConvergence as e:
        return {"tipo": "no_convergente", "mensaje": f"plait point not located: {e.mensaje}"}
    pr = sis.prueba_estabilidad(T, P, _mu(sis, T, P, x), IDX, incluir_vapor=True)
    tm_new = min((q[2] for q in mz._candidatas_nuevas(pr, [("liquido", x)], tol=1e-3)), default=math.inf)
    return {"tipo": "pliegue", "x": x, "residuo": res, "tmOtraFase": float(tm_new),
            "estable": tm_new >= -TOL_TM, "ultimoPar": (xa, xb)}


def _edge_end(sis, T, P, k, xa, xb):
    try:
        a, b = edge_pair(sis, T, P, k, xa, xb)
    except ll.NoConvergence as e:
        return {"tipo": "no_convergente", "mensaje": f"binary edge not solved: {e.mensaje}"}
    keep = [i for i in IDX if i != k]
    cert, _ = ll.certify(_Binary(sis, keep), "Txy", P, T, P, [("liquido", a[keep]), ("liquido", b[keep])])
    return {"tipo": "borde_binario", "especieAusente": k, "xa": a, "xb": b, "cert": cert,
            "ultimoPar": (xa, xb)}


def _three_phase_end(sis, T, P, last, y0):
    try:
        xa, xb, y = three_phase(sis, T, P, last["xa"], last["xb"], np.maximum(np.asarray(y0, float), 1e-300))
    except ll.NoConvergence as e:
        return {"tipo": "no_convergente", "mensaje": f"three-phase triangle not solved: {e.mensaje}"}
    return {"tipo": "tres_fases", "xa": xa, "xb": xb, "y": y,
            "cert": certify(sis, T, P, [("liquido", xa), ("liquido", xb), ("vapor", y)])}


class _Binary:
    """The package restricted to two of its species, with the binary interface core/coexistencia_ll uses."""

    def __init__(self, sis, keep):
        self.sis, self.keep = sis, keep
        self.T_rango = sis.T_rango

    def mu(self, kind, T, P, x, idx):
        return self.sis.mu(kind, T, P, x, [self.keep[i] for i in idx])

    def dominio(self, T, P):
        return self.sis.dominio(T, P)

    def prueba_estabilidad(self, T, P, mu_ref, idx, incluir_vapor=True):
        return self.sis.prueba_estabilidad(T, P, mu_ref, [self.keep[i] for i in idx], incluir_vapor=incluir_vapor)


class Branch:
    def __init__(self):
        self.points, self.ends = [], []


def trace_branch(sis, T, P, seed, profile, spend, exhausted, max_points=600):
    branch = Branch()
    try:
        # the seed is a certified flash; one Newton at fixed za0 settles it on the package's binodal exactly
        def F(w):
            return binodal_residual(sis, T, P, np.array([seed[0], *w]))
        w, _ = ll._solve(F, seed[1:], "ternary seed")
    except ll.NoConvergence as x:
        branch.ends.append({"tipo": x.motivo, "mensaje": x.mensaje})
        return branch
    v0 = np.array([seed[0], *w])
    first = _accept(sis, T, P, v0, "semilla_por_flash")
    if first["cert"]["estado"] != "cumple":
        branch.ends.append({"tipo": "inestable", "mensaje": "the flash seed's tie line is not stable"})
        return branch
    t0 = _tangent(sis, T, P, v0)
    halves = [_walk(sis, T, P, v0, s * t0, profile, spend, exhausted, max_points // 2) for s in (1.0, -1.0)]
    (up, end_up), (dn, end_dn) = halves
    branch.points = list(reversed(dn)) + [first] + up
    branch.ends = [end_dn, end_up]
    return branch


def _covers(branch, seed):
    xa, xb = comp(seed[0], seed[1]), comp(seed[2], seed[3])
    for p in branch.points:
        for a, b in ((p["xa"], p["xb"]), (p["xb"], p["xa"])):
            if np.max(np.abs(a - xa)) < 0.03 and np.max(np.abs(b - xb)) < 0.03:
                return True
    return False


def trace(sis, T, P, profile, spend=lambda n=1: None, exhausted=lambda: False):
    """Every liquid-liquid branch of a ternary at (T, P). Returns a list of Branch."""
    sis.dominio(T, P)
    branches = []
    for s in seeds(sis, T, P, profile["lattice"], spend, exhausted):
        if exhausted():
            break
        if any(_covers(b, s) for b in branches):
            continue
        b = trace_branch(sis, T, P, s, profile, spend, exhausted)
        if b.points:
            branches.append(b)
    return branches
