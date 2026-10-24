"""
Binary liquid-liquid coexistence, its critical (fold) point and the liquid-liquid-vapor three-phase point:
a shared operation of a mixture package.

Only the package's public interface is used (core/mezclas.Sistema or any adapter with the same interface):
`mu(tipo, T, P, x, idx)`, `prueba_estabilidad`, `dominio`, `equilibrio_TP`, `fase` and `T_rango`. There is no
activity, vapor-pressure or fugacity formula here: the package's own chemical potentials are the only
equilibrium condition, so any contribution they contain (Poynting, excess terms) enters unchanged.

Coordinates. A slice fixes P ('Txy') or T ('Pxy'); the free condition is q = T / Q_SCALE_T (Txy) or q = ln P
(Pxy), so that one unit of q is comparable with one unit of a logit composition. The two liquids are
xa = sig(za), xb = sig(zb) (mole fraction of species 0), with xa < xb on a published branch.

Binodal: F(q, za, zb) = (mu^L(xa) - mu^L(xb)) / RT = 0 (two equations, three unknowns): a curve, followed by
pseudo-arclength continuation, so a turning point in q is followed rather than declared a failure. The pair
branch ends where the two liquids merge (critical point, the binodal's fold in T), where a vapor phase
lowers the tangent plane (three-phase point), at the package's domain, or on budget.

Critical point: h(x) = (mu_0^L - mu_1^L) / RT = d(g/RT)/dx at fixed T, P; the conditions h'(x) = h''(x) = 0
(spinodal and its extremum) are solved in (q, logit x) with five-point differences of h.

Three-phase point: (q, za, zb, zy) with mu^L(xa) = mu^L(xb) = mu^V(y): four equations, four unknowns; for a
binary at a fixed P (or T) it is an invariant point.
"""

import math

import numpy as np

from core import mezclas as mz

TOL_MU = mz.TOL_MU
TOL_TM = mz.TOL_TM
TOL_NEWTON = 1e-13
Q_SCALE_T = 10.0                 # K per unit of q in a Txy slice
MERGE_GAP = 2e-3                 # |xa - xb| below which the pair branch hands over to the critical point
MIN_GAP = 1e-6                   # distinct liquids


class NoConvergence(Exception):
    def __init__(self, motivo, mensaje):
        super().__init__(mensaje)
        self.motivo = motivo        # 'no_convergente' | 'fuera_de_dominio'
        self.mensaje = mensaje


def _sig(u):
    if u >= 0:
        return 1.0 / (1.0 + math.exp(-u))
    e = math.exp(u) if u > -745 else 0.0
    return e / (1.0 + e)


def _pair(u):
    """(x, 1 - x) from a logit without cancellation in either fraction."""
    return np.array([_sig(u), _sig(-u)])


def _logit(p):
    return math.log(p) - math.log1p(-p)


def TP(cut, fixed, q):
    return (Q_SCALE_T * q, fixed) if cut == "Txy" else (fixed, math.exp(q))


def q_of(cut, T, P):
    return T / Q_SCALE_T if cut == "Txy" else math.log(P)


def _mu(sis, kind, T, P, z):
    return sis.mu(kind, T, P, _pair(z), [0, 1])


def binodal_residual(sis, cut, fixed, v):
    T, P = TP(cut, fixed, v[0])
    sis.dominio(T, P)
    return (_mu(sis, "liquido", T, P, v[1]) - _mu(sis, "liquido", T, P, v[2])) / (mz.R * T)


def three_phase_residual(sis, cut, fixed, v):
    T, P = TP(cut, fixed, v[0])
    sis.dominio(T, P)
    ma = _mu(sis, "liquido", T, P, v[1])
    return np.concatenate([ma - _mu(sis, "liquido", T, P, v[2]), ma - _mu(sis, "vapor", T, P, v[3])]) / (mz.R * T)


def _jacobian(F, v, h=1e-7):
    """Central differences; one-sided next to the package's domain edge (never evaluated outside it)."""
    f0 = F(v)
    J = np.empty((len(f0), len(v)))
    for j in range(len(v)):
        d = np.zeros_like(v)
        d[j] = h
        try:
            fp = F(v + d)
        except mz.FueraDeAlcance:
            fp = None
        try:
            fm = F(v - d)
        except mz.FueraDeAlcance:
            fm = None
        if fp is not None and fm is not None:
            J[:, j] = (fp - fm) / (2 * h)
        elif fp is not None:
            J[:, j] = (fp - f0) / h
        elif fm is not None:
            J[:, j] = (f0 - fm) / h
        else:
            raise mz.FueraDeAlcance("fuera_de_dominio", "no evaluable neighbour inside the domain")
    return J


def _newton(F, v0, max_iter=40):
    """Damped Newton with a central-difference Jacobian. Returns (v, f, iterations)."""
    v = np.array(v0, dtype=float)
    f = F(v)
    for k in range(max_iter):
        if np.max(np.abs(f)) < TOL_NEWTON:
            return v, f, k
        paso = np.linalg.solve(_jacobian(F, v), -f)
        a = 1.0
        for _ in range(30):
            try:
                fn = F(v + a * paso)
            except (mz.FueraDeAlcance, FloatingPointError, OverflowError, ValueError):
                fn = None
            if fn is not None and np.all(np.isfinite(fn)) and np.max(np.abs(fn)) < np.max(np.abs(f)):
                v, f = v + a * paso, fn
                break
            a *= 0.5
        else:
            break
    return v, f, max_iter


def _solve(F, v0, what):
    try:
        v, f, k = _newton(F, v0)
    except mz.FueraDeAlcance as x:
        raise NoConvergence("fuera_de_dominio", x.mensaje)
    except (np.linalg.LinAlgError, FloatingPointError, OverflowError, ValueError) as x:
        raise NoConvergence("no_convergente", f"{what}: {x}")
    if not np.max(np.abs(f)) < 1e-11:
        raise NoConvergence("no_convergente", f"{what}: final residual {np.max(np.abs(f)):.2e}")
    return v, k


# --- certification -----------------------------------------------------------------------------------------
def _stability(sis, T, P, mu_ref, present):
    """Tangent-plane test with the common mu; trial phases equal to a present phase are not competitors."""
    pr = sis.prueba_estabilidad(T, P, mu_ref, [0, 1], incluir_vapor=True)
    nuevas = mz._candidatas_nuevas(pr, present)
    tm_min = min(q[2] for q in pr)
    tm_new = min((q[2] for q in nuevas), default=math.inf)
    est = {"estado": "estable" if tm_min >= -TOL_TM else "inestable", "tmMinimo": float(tm_min),
           "tolerancia": TOL_TM, "candidatas": sorted({q[0] for q in pr}), "pruebas": len(pr),
           "metodo": "distancia al plano tangente con la mu comun: vapor por minimo analitico, liquido en malla "
                     "de 1361 puntos en logit con refinamiento de cada minimo local (no es una demostracion del "
                     "minimo global)"}
    if tm_min < -TOL_TM:
        q = min(pr, key=lambda q: q[2])
        est["competidora"] = {"tipo": q[0], "composicion": [float(w) for w in q[1]], "tm": float(q[2])}
    return est, tm_new


def _residue(rid, value, tol, scale, ok=None):
    ok = value <= tol if ok is None else ok
    return {"id": rid, "valor": float(value), "tolerancia": tol, "escala": scale,
            "estado": "cumple" if ok else "no_cumple"}


def certify(sis, cut, fixed, T, P, phases):
    """Certificate of a coexistence point with phases [(kind, composition of species 0 and 1)]: mu equality of
    every species between all phases, normalization, the slice's fixed condition, distinct phases and
    tangent-plane stability with the common mu (vapor and trial liquid)."""
    RT = mz.R * T
    mus = [sis.mu(k, T, P, np.asarray(x, float), [0, 1]) for k, x in phases]
    r_mu = max(float(np.max(np.abs(m - mus[0]))) for m in mus[1:]) / RT
    r_n = max(abs(float(np.sum(x)) - 1.0) for _, x in phases)
    ok_n = r_n <= 1e-14 and all(np.all(np.asarray(x) >= 0) for _, x in phases)
    r_c = abs((P if cut == "Txy" else T) / fixed - 1.0)
    gap = min(float(np.max(np.abs(np.asarray(a) - np.asarray(b))))
              for i, (_, a) in enumerate(phases) for _, b in phases[i + 1:])
    res = [_residue("igualdad_mu", r_mu, TOL_MU, "R T"),
           _residue("normalizacion", r_n, 1e-14, "1", ok_n),
           _residue("condicion_fija", r_c, 1e-14, "relativa al corte"),
           _residue("distincion_fases", gap, MIN_GAP, "min max |x_a - x_b| entre fases", gap > MIN_GAP)]
    est, tm_new = _stability(sis, T, P, mus[0], [(k, np.asarray(x, float)) for k, x in phases])
    ok = all(r["estado"] == "cumple" for r in res) and est["estado"] == "estable"
    return {"estado": "cumple" if ok else "no_cumple", "residuos": res, "estabilidad": est}, tm_new


# --- seeds -------------------------------------------------------------------------------------------------
def seeds(sis, cut, fixed, n_q=24, n_x=13, spend=lambda n=1: None, exhausted=lambda: False):
    """Liquid-liquid pairs from the package's certified TP flash on a grid of the free condition: [(q, za, zb)].
    Only a liquid reference that the tangent-plane test finds unstable against another liquid is flashed. The
    seeds are starting points; every published point is solved and certified afterwards."""
    if cut == "Txy":
        lo, hi = sis.T_rango
        qs = np.linspace(lo + 1e-3 * (hi - lo), hi - 1e-3 * (hi - lo), n_q) / Q_SCALE_T
    else:
        qs = np.linspace(math.log(mz.P_MAX), math.log(mz.P_MIN), max(6, n_q // 2))
    xs = list(np.linspace(0.02, 0.98, n_x))
    out = []
    for q in qs:
        if exhausted():
            break
        T, P = TP(cut, fixed, q)
        try:
            sis.dominio(T, P)
        except mz.FueraDeAlcance:
            continue
        found = False
        for x in xs:
            z = np.array([x, 1.0 - x])
            spend()
            pr = sis.prueba_estabilidad(T, P, sis.mu("liquido", T, P, z, [0, 1]), [0, 1], incluir_vapor=False)
            if min(t[2] for t in pr) >= -1e-6:
                continue
            spend(10)
            try:
                e = sis.equilibrio_TP(T, P, z)
            except mz.FueraDeAlcance:
                continue
            liq = sorted(float(f.x[0]) for f in e.fases if f.tipo == "liquido")
            if len(liq) == 2 and len(e.fases) == 2 and liq[1] - liq[0] > 10 * MERGE_GAP:
                out.append((float(q), _logit(liq[0]), _logit(liq[1])))
                found = True
                break
        if not found and out and out[-1] is not None:
            out.append(None)                     # separator between LL regions along q
    return [s for s in out if s is not None]


# --- critical point ----------------------------------------------------------------------------------------
def _h(sis, T, P, x):
    m = sis.mu("liquido", T, P, np.array([x, 1.0 - x]), [0, 1])
    return (m[0] - m[1]) / (mz.R * T)


def critical_residual(sis, cut, fixed, v, d=2e-3):
    """(x(1-x) h'(x), [x(1-x)]^2 h''(x)) at q = v[0], x = sig(v[1]) by five-point differences."""
    T, P = TP(cut, fixed, v[0])
    sis.dominio(T, P)
    x = _sig(v[1])
    s = x * (1.0 - x)
    dd = d * s
    hs = [_h(sis, T, P, x + k * dd) for k in (-2, -1, 0, 1, 2)]
    h1 = (hs[0] - 8 * hs[1] + 8 * hs[3] - hs[4]) / (12 * dd)
    h2 = (-hs[0] + 16 * hs[1] - 30 * hs[2] + 16 * hs[3] - hs[4]) / (12 * dd * dd)
    return np.array([s * h1, s * s * h2])


def critical_point(sis, cut, fixed, q0, x0):
    """(q, x) of the liquid-liquid critical point near (q0, x0). NoConvergence if not found."""
    F = lambda v: critical_residual(sis, cut, fixed, v)
    try:
        v, f, _ = _newton(F, [q0, _logit(x0)])
    except mz.FueraDeAlcance as x:
        raise NoConvergence("fuera_de_dominio", x.mensaje)
    except (np.linalg.LinAlgError, FloatingPointError, OverflowError, ValueError) as x:
        raise NoConvergence("no_convergente", f"critical point: {x}")
    if not np.max(np.abs(f)) < 1e-8:
        raise NoConvergence("no_convergente", f"critical point: final residual {np.max(np.abs(f)):.2e}")
    return float(v[0]), _sig(v[1]), float(np.max(np.abs(f)))


# --- three-phase point -------------------------------------------------------------------------------------
def three_phase_point(sis, cut, fixed, q0, xa, xb, y):
    v, _ = _solve(lambda v: three_phase_residual(sis, cut, fixed, v),
                  [q0, _logit(xa), _logit(xb), _logit(min(max(y, 1e-300), 1 - 1e-16))], "three-phase point")
    return float(v[0]), _sig(v[1]), _sig(v[2]), _sig(v[3])


# --- pseudo-arclength continuation of the binodal ----------------------------------------------------------
def _tangent(sis, cut, fixed, v, prev=None):
    J = _jacobian(lambda w: binodal_residual(sis, cut, fixed, w), v)
    t = np.linalg.svd(J)[2][-1]
    if prev is not None and float(t @ prev) < 0:
        t = -t
    return t


def _corrector(sis, cut, fixed, v_pred, v_prev, t, ds):
    def G(w):
        return np.concatenate([binodal_residual(sis, cut, fixed, w), [float(t @ (w - v_prev)) - ds]])
    return _solve(G, v_pred, "binodal")


class Branch:
    """Certified pairs along one binodal branch, in continuation order, and how each end finished."""

    def __init__(self):
        self.points = []                 # dicts: q, T, P, xa, xb, cert, origen
        self.ends = []                   # dicts: tipo ('critico' | 'tres_fases' | 'dominio' | 'no_convergente' |
                                         # 'presupuesto' | 'inestable'), plus data


def trace_branch(sis, cut, fixed, seed, profile, spend, exhausted, max_points=400):
    """Both directions from a seed (q, za, zb). Returns a Branch."""
    branch = Branch()
    try:
        v0, _ = _solve(lambda w: binodal_residual(sis, cut, fixed, np.array([seed[0], w[0], w[1]])),
                       [seed[1], seed[2]], "binodal seed")
    except NoConvergence as x:
        branch.ends.append({"tipo": x.motivo, "mensaje": x.mensaje})
        return branch
    v0 = np.array([seed[0], *v0])
    if v0[1] > v0[2]:
        v0 = v0[[0, 2, 1]]
    first = _accept(sis, cut, fixed, v0, "semilla_por_flash")
    if first is None or first["cert"]["estado"] != "cumple":
        branch.ends.append({"tipo": "inestable", "mensaje": "the flash seed's pair is not stable"})
        return branch
    sides = []
    for sign in (+1.0, -1.0):
        t = _tangent(sis, cut, fixed, v0)
        if t[0] * sign < 0 or (abs(t[0]) < 1e-12 and sign < 0):
            t = -t
        sides.append(_walk(sis, cut, fixed, v0, t, profile, spend, exhausted, max_points // 2))
    (pts_up, end_up), (pts_dn, end_dn) = sides
    branch.points = list(reversed(pts_dn)) + [first] + pts_up
    branch.ends = [end_dn, end_up]
    return branch


def _accept(sis, cut, fixed, v, origen):
    T, P = TP(cut, fixed, v[0])
    xa, xb = _pair(v[1]), _pair(v[2])
    cert, tm_new = certify(sis, cut, fixed, T, P, [("liquido", xa), ("liquido", xb)])
    return {"q": float(v[0]), "T": T, "P": P, "xa": float(xa[0]), "xb": float(xb[0]), "v": v.copy(),
            "cert": cert, "tmNueva": tm_new, "origen": origen}


def _walk(sis, cut, fixed, v0, t, profile, spend, exhausted, max_points):
    """One direction of pseudo-arclength continuation. Returns (points, end)."""
    ds_max = profile["dsMax"]
    ds_min = 1e-6
    ds = 0.25 * ds_max
    v, pts = v0.copy(), []
    last_good = None
    while len(pts) < max_points:
        if exhausted():
            return pts, {"tipo": "presupuesto"}
        spend()
        pred = v + ds * t
        try:
            w, iters = _corrector(sis, cut, fixed, pred, v, t, ds)
        except NoConvergence as x:
            if ds > ds_min:
                ds *= 0.5
                continue
            return pts, {"tipo": x.motivo, "mensaje": x.mensaje, "ultimo": last_good}
        if w[1] > w[2]:
            # the two logits crossed: the step went through the critical point
            if ds > ds_min:
                ds *= 0.5
                continue
            return pts, _critical_end(sis, cut, fixed, v, last_good)
        gap = _sig(w[2]) - _sig(w[1])
        if gap < MERGE_GAP:
            return pts, _critical_end(sis, cut, fixed, w, last_good)
        p = _accept(sis, cut, fixed, w, "continuacion")
        if p["cert"]["estado"] != "cumple":
            if p["cert"]["estabilidad"]["estado"] == "inestable" and ds > ds_min * 16:
                ds *= 0.5                      # approach the boundary before handing over
                continue
            comp = p["cert"]["estabilidad"].get("competidora")
            if comp and comp["tipo"] == "vapor":
                return pts, _three_phase_end(sis, cut, fixed, v if last_good is None else last_good["v"],
                                             comp["composicion"][0], last_good)
            return pts, {"tipo": "inestable", "mensaje": "another phase lowers the tangent plane",
                         "competidora": comp, "ultimo": last_good}
        t = _tangent(sis, cut, fixed, w, t)
        v = w
        pts.append(p)
        last_good = p
        if iters <= 4:
            ds = min(ds * 1.5, ds_max)
    return pts, {"tipo": "presupuesto", "mensaje": "point limit of the branch"}


def _critical_end(sis, cut, fixed, v, last_good):
    x0 = 0.5 * (_sig(v[1]) + _sig(v[2]))
    try:
        q, x, res = critical_point(sis, cut, fixed, float(v[0]), x0)
    except NoConvergence as e:
        return {"tipo": "no_convergente", "mensaje": f"critical point not located: {e.mensaje}", "ultimo": last_good}
    T, P = TP(cut, fixed, q)
    z = np.array([x, 1.0 - x])
    est, _ = _stability(sis, T, P, sis.mu("liquido", T, P, z, [0, 1]), [("liquido", z)])
    return {"tipo": "critico", "q": q, "T": T, "P": P, "x": x, "residuo": res, "estabilidad": est,
            "ultimo": last_good}


def _three_phase_end(sis, cut, fixed, v, y0, last_good):
    try:
        q, xa, xb, y = three_phase_point(sis, cut, fixed, float(v[0]), _sig(v[1]), _sig(v[2]), y0)
    except NoConvergence as e:
        return {"tipo": "no_convergente", "mensaje": f"three-phase point not located: {e.mensaje}",
                "ultimo": last_good}
    T, P = TP(cut, fixed, q)
    cert, _ = certify(sis, cut, fixed, T, P, [("liquido", _pair(_logit(xa))), ("liquido", _pair(_logit(xb))),
                                              ("vapor", _pair(_logit(y)))])
    return {"tipo": "tres_fases", "q": q, "T": T, "P": P, "xa": xa, "xb": xb, "y": y, "cert": cert,
            "ultimo": last_good}


PROFILES = {"exploratoria": {"dsMax": 0.25}, "refinada": {"dsMax": 0.08}}


def trace(sis, cut, fixed, profile, spend=lambda n=1: None, exhausted=lambda: False):
    """Every liquid-liquid branch of a binary slice: seeds by certified flash, then continuation of each branch
    not yet covered. Returns a list of Branch."""
    branches = []
    for s in seeds(sis, cut, fixed, spend=spend, exhausted=exhausted):
        if exhausted():
            break
        if any(_covers(b, s) for b in branches):
            continue
        b = trace_branch(sis, cut, fixed, s, profile, spend, exhausted)
        if b.points:
            branches.append(b)
    return branches


def _covers(branch, seed):
    q, xa, xb = seed[0], _sig(seed[1]), _sig(seed[2])
    qs = [p["q"] for p in branch.points]
    if not qs or not min(qs) - 1e-9 <= q <= max(qs) + 1e-9:
        return False
    near = min(branch.points, key=lambda p: abs(p["q"] - q))
    return abs(near["xa"] - xa) < 0.05 and abs(near["xb"] - xb) < 0.05


TRAZADOR = {"id": "trazador-ll-binario", "version": "1"}
