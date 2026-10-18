"""
Agua pura con hielo Ih, liquido y vapor: equilibrio solido-liquido-vapor.

Cierre: hielo Ih de IAPWS R10-06(2009) (core/hielo_ih.py) y agua fluida de
IAPWS-95 (core/agua_iapws95.py, mismas primitivas auditadas en H1). La
release del hielo fija su s0 para que ambas formulaciones compartan las
referencias de IAPWS-95 (u = s = 0 del liquido en el punto triple), asi que
g del hielo y g del fluido se comparan directamente.

Dominio publicado: T en [200, 300] K, P en [0.1 Pa, 100 MPa].
  * P <= 100 MPa deja fuera los hielos II, III, V... (IAPWS R14-08: el triple
    Ih-III-liquido esta a 208.566 MPa; Ih-II por encima de ~200 MPa). No se
    declaran por extrapolacion.
  * El liquido sobreenfriado solo se considera candidato con T >= 235 K
    (limite de nucleacion homogenea a presion ordinaria): por debajo,
    IAPWS-95 extrapola y no es una fase evaluable. En ese intervalo el hielo
    es la fase estable de todos modos; la verificacion de estabilidad dice
    contra que candidatas se comparo.

Especificaciones:
  TP  fase de menor g entre las candidatas; sobre una curva de coexistencia
      (|P/Pc(T) - 1| <= 1e-6) T y P no determinan el reparto: 'saturacion'.
      En el triple tampoco.
  PH, UP  sobre la secuencia de fases estables al subir T a P fija (h o u
      crecen con T); mesetas en las curvas por palanca. En el triple
      (P = P_triple) una meseta de tres fases con dos ecuaciones no
      determina el reparto: 'saturacion'.
  UV  el estado de equilibrio maximiza S a U, V y masa fijos: se enumeran
      todas las candidatas que cumplen U y V (una fase, dos fases sobre cada
      curva, tres fases en el triple) y se toma la de mayor S; se certifica
      ademas con la prueba de g minima a su T, P.

Todas las magnitudes especificas por kg.
"""

import math
from dataclasses import dataclass, field
from functools import lru_cache

from scipy.optimize import brentq

from core import agua_iapws95 as ag
from core import hielo_ih as hi

T_MIN, T_MAX = 200.0, 300.0
P_MIN, P_MAX = 0.1, 100e6
T_LIQUIDO_MIN = 235.0
TOL_COEX = 1e-6             # |P/Pc - 1| de la curva: T, P no determinan el reparto
TOL_G = 1e-9                # g de la fase estable frente a otras candidatas: (g_b - g_a)/(R T) >= -TOL_G
R = ag.R
FASES = ("solido", "liquido", "vapor")


class FueraDeAlcance(Exception):
    def __init__(self, motivo, mensaje, **datos):
        super().__init__(mensaje)
        self.motivo = motivo
        self.mensaje = mensaje
        self.datos = datos


@dataclass(frozen=True)
class Fase:
    tipo: str           # 'solido' | 'liquido' | 'vapor'
    T: float
    P: float
    g: float
    h: float
    u: float
    v: float
    s: float
    cp: float | None = None


def _fase_hielo(T, P):
    try:
        q = hi.propiedades(T, P)
    except hi.FueraDeAlcanceHielo:
        return None
    return Fase("solido", T, P, q.g, q.h, q.u, q.v, q.s, q.cp)


def _fase_fluida_rho(tipo, T, rho):
    p = ag.propiedades(T, rho)
    if not p.dP_drho_T > 0:
        return None
    return Fase(tipo, T, p.P, p.g, p.h, p.u, p.v, p.s, p.cp)


@lru_cache(maxsize=200000)
def _rho_liquido(T, P):
    if T < T_LIQUIDO_MIN:
        return None
    hi_ = 1300.0
    if ag.presion(T, hi_) < P:
        return None
    lo = 1000.0
    while ag.presion(T, lo) >= P:
        lo -= 5.0
        if ag._dP_drho(T, lo) <= 0 or lo < 700:
            return None             # espinodal antes de bajar a P: no hay raiz liquida
    try:
        return ag.densidad(T, P, lo, hi_)
    except (ag.FueraDeAlcance, ValueError):
        return None


@lru_cache(maxsize=200000)
def _rho_vapor(T, P):
    rig = P / (R * T)
    lo, hi_ = 0.5 * rig, 2.0 * rig
    if not (ag.presion(T, lo) <= P <= ag.presion(T, hi_)) or ag._dP_drho(T, hi_) <= 0:
        return None
    try:
        return ag.densidad(T, P, lo, hi_)
    except (ag.FueraDeAlcance, ValueError):
        return None


def fase(tipo, T, P):
    """La fase `tipo` a (T, P), o None si no es evaluable (fuera de su validez o sin raiz)."""
    if tipo == "solido":
        return _fase_hielo(T, P)
    rho = _rho_liquido(T, P) if tipo == "liquido" else _rho_vapor(T, P)
    return None if rho is None else _fase_fluida_rho(tipo, T, rho)


def candidatas(T, P):
    return [f for f in (fase(t, T, P) for t in FASES) if f is not None]


# ----------------------------------------------------------------------
# Curvas de coexistencia y punto triple (de la propia formulacion)
# ----------------------------------------------------------------------
def _dg(a, b, T, P):
    fa, fb = fase(a, T, P), fase(b, T, P)
    if fa is None or fb is None:
        return None
    return (fa.g - fb.g) / (R * T)


def _raiz(f, a, b, n=40):
    """Unica raiz de f en [a, b] por barrido (f puede ser None donde una fase no es evaluable) y Brent
    en el primer cambio de signo. None si no hay."""
    xs = [a + (b - a) * k / (n - 1) for k in range(n)]
    prev = None
    for x in xs:
        fx = f(x)
        if fx is None:
            prev = None
            continue
        if fx == 0:
            return x
        if prev is not None and prev[1] * fx < 0:
            return brentq(f, prev[0], x, xtol=1e-300, rtol=1e-15, maxiter=300)
        prev = (x, fx)
    return None


@lru_cache(maxsize=1)
def triple():
    """(T, P) con g_s = g_l = g_v, por Newton 2D desde (273.16 K, 611.657 Pa)."""
    T, P = hi.TT, hi.PT
    for _ in range(30):
        F = [_dg("solido", "liquido", T, P), _dg("solido", "vapor", T, P)]
        if max(abs(F[0]), abs(F[1])) < 1e-15:
            break
        J = [[0.0, 0.0], [0.0, 0.0]]
        # en T, diferencias hacia atras: el hielo no se evalua por encima de 273.16 K (validez de R10-06)
        for j, (dT, dP) in enumerate(((1e-6, 0.0), (0.0, 1e-6 * P))):
            if j == 0:
                Fp, Fm, h = F, [_dg("solido", "liquido", T - dT, P), _dg("solido", "vapor", T - dT, P)], dT
            else:
                Fp = [_dg("solido", "liquido", T, P + dP), _dg("solido", "vapor", T, P + dP)]
                Fm = [_dg("solido", "liquido", T, P - dP), _dg("solido", "vapor", T, P - dP)]
                h = 2 * dP
            J[0][j], J[1][j] = (Fp[0] - Fm[0]) / h, (Fp[1] - Fm[1]) / h
        det = J[0][0] * J[1][1] - J[0][1] * J[1][0]
        T -= (F[0] * J[1][1] - F[1] * J[0][1]) / det
        P -= (J[0][0] * F[1] - J[1][0] * F[0]) / det
    return T, P


@lru_cache(maxsize=20000)
def P_sublimacion(T):
    Ttr, Ptr = triple()
    if not T_MIN <= T <= Ttr:
        return None
    f = lambda q: _dg("solido", "vapor", T, math.exp(q))
    q = _raiz(f, math.log(1e-4), math.log(Ptr * 1.01))
    return None if q is None else math.exp(q)


@lru_cache(maxsize=20000)
def T_sublimacion(P):
    Ttr, Ptr = triple()
    if not P < Ptr:
        return None
    return _raiz(lambda T: _dg("solido", "vapor", T, P), T_MIN, Ttr)


@lru_cache(maxsize=20000)
def T_fusion(P):
    Ttr, Ptr = triple()
    if not Ptr <= P <= P_MAX:
        return None
    if abs(P / Ptr - 1) < 1e-12:
        return Ttr
    return _raiz(lambda T: _dg("solido", "liquido", T, P), 250.0, min(Ttr * (1 + 1e-9), hi.TT))


@lru_cache(maxsize=20000)
def P_fusion(T):
    """Inversa de T_fusion en [T_fusion(P_MAX), T_triple]."""
    Ttr, Ptr = triple()
    Tlo = T_fusion(P_MAX)
    if not Tlo <= T <= Ttr:
        return None
    if T >= Ttr:
        return Ptr
    q = _raiz(lambda q: _dg("solido", "liquido", T, math.exp(q)), math.log(Ptr * (1 - 1e-12)), math.log(P_MAX))
    return None if q is None else math.exp(q)


@lru_cache(maxsize=20000)
def T_vaporizacion(P):
    Ttr, Ptr = triple()
    if not P > Ptr:
        return None
    return _raiz(lambda T: _dg("liquido", "vapor", T, P), Ttr, T_MAX)


@lru_cache(maxsize=20000)
def P_vaporizacion(T):
    Ttr, Ptr = triple()
    if not Ttr <= T <= T_MAX:
        return None
    q = _raiz(lambda q: _dg("liquido", "vapor", T, math.exp(q)), math.log(Ptr * 0.99), math.log(1e4))
    return None if q is None else math.exp(q)


def curvas(puntos=60):
    """Diagrama P-T del cierre: curvas de coexistencia muestreadas y punto triple, con las regiones
    no soportadas. Todo sale de las mismas funciones que resuelven los estados."""
    Ttr, Ptr = triple()
    sub = [(T, P_sublimacion(T)) for T in _lin(T_MIN, Ttr, puntos)]
    fus = [(T_fusion(P), P) for P in _geo(Ptr, P_MAX, puntos)]
    vap = [(T, P_vaporizacion(T)) for T in _lin(Ttr, T_MAX, puntos)]
    return {"triple": (Ttr, Ptr), "sublimacion": sub, "fusion": fus, "vaporizacion": vap}


def _lin(a, b, n):
    return [a + (b - a) * k / (n - 1) for k in range(n)]


def _geo(a, b, n):
    return [a * (b / a) ** (k / (n - 1)) for k in range(n)]


# ----------------------------------------------------------------------
# Estados
# ----------------------------------------------------------------------
@dataclass
class Estado:
    especificacion: str
    T: float
    P: float
    fases: list            # [(Fase, fraccion masica)]
    u: float
    h: float
    v: float
    s: float
    estabilidad: dict = field(default_factory=dict)
    residuos: dict = field(default_factory=dict)


def _dominio(T, P, que="El estado"):
    if not (T_MIN <= T <= T_MAX and P_MIN <= P <= P_MAX):
        raise FueraDeAlcance("fuera_de_dominio",
                             f"{que} (T = {T:.6g} K, P = {P:.6g} Pa) cae fuera del dominio T en [{T_MIN}, {T_MAX}] K, "
                             f"P en [{P_MIN:g}, {P_MAX:.3g}] Pa.",
                             T_fuera=not T_MIN <= T <= T_MAX, P_fuera=not P_MIN <= P <= P_MAX)


def _estado(espec, T, P, fases):
    u = sum(f.u * b for f, b in fases)
    h = sum(f.h * b for f, b in fases)
    v = sum(f.v * b for f, b in fases)
    s = sum(f.s * b for f, b in fases)
    return Estado(espec, T, P, fases, u, h, v, s)


def _certificar(e):
    """g minima: ninguna candidata evaluable a (T, P) tiene g menor que las fases presentes; las
    presentes comparten g (coexistencia). Rellena e.estabilidad y e.residuos."""
    cands = candidatas(e.T, e.P)
    RT = R * e.T
    g_ref = min(f.g for f, _ in e.fases)
    tm = min((c.g - g_ref) / RT for c in cands)
    no_ev = [t for t in FASES if t not in {c.tipo for c in cands}]
    e.estabilidad = {"tm_min": tm, "candidatas": [c.tipo for c in cands], "no_evaluables": no_ev,
                     "excluidas_por_curvas": _excluidas_por_curvas(e, no_ev)}
    e.residuos["estabilidad"] = (max(0.0, -tm), TOL_G)
    if len(e.fases) > 1:
        gs = [f.g for f, _ in e.fases]
        e.residuos["equilibrio"] = ((max(gs) - min(gs)) / RT, 1e-10)
    e.residuos["identidad_h_u_Pv"] = (max(abs(f.h - f.u - e.P * f.v) / max(abs(f.h), R * e.T) for f, _ in e.fases),
                                      1e-12)
    e.residuos["identidad_g_h_Ts"] = (max(abs(f.g - f.h + e.T * f.s) / max(abs(f.h), R * e.T) for f, _ in e.fases),
                                      1e-12)
    e.residuos["fracciones"] = (abs(sum(b for _, b in e.fases) - 1.0), 1e-14)
    return e


def tipo_por_curvas(T, P):
    """Fase estable a (T, P) segun las curvas de coexistencia del propio cierre (fuera de ellas)."""
    Ttr, Ptr = triple()
    if T > Ttr:
        pv = P_vaporizacion(T)
        return "vapor" if pv is not None and P < pv else "liquido"
    ps = P_sublimacion(T)
    if ps is not None and P < ps:
        return "vapor"
    pf = P_fusion(T)
    return "liquido" if pf is not None and P > pf else "solido"


def _excluidas_por_curvas(e, no_ev):
    """Fases no evaluables a (T, P) que las curvas del cierre dejan fuera de la region estable: en una
    fase, si las curvas dan ese mismo tipo; sobre una curva lejos del triple, la tercera fase (el triple
    es el unico punto donde coexiste con las otras dos)."""
    if not no_ev:
        return []
    if len(e.fases) == 1:
        return list(no_ev) if tipo_por_curvas(e.T, e.P) == e.fases[0][0].tipo else []
    if len(e.fases) == 2:
        Ttr, Ptr = triple()
        return [] if abs(e.T / Ttr - 1) < 1e-9 else list(no_ev)
    return []


def _coexistencias_en_T(T, P):
    """Curvas a esta T y su presion (para detectar 'P sobre la curva')."""
    sal = []
    Ttr, Ptr = triple()
    if T <= Ttr:
        ps = P_sublimacion(T)
        if ps is not None:
            sal.append((("solido", "vapor"), ps))
        pf = P_fusion(T)
        if pf is not None:
            sal.append((("solido", "liquido"), pf))
    else:
        pv = P_vaporizacion(T)
        if pv is not None:
            sal.append((("liquido", "vapor"), pv))
    return sal


def evaluar_TP(T, P):
    _dominio(T, P)
    Ttr, Ptr = triple()
    if abs(T / Ttr - 1) <= 1e-9 and abs(P / Ptr - 1) <= TOL_COEX:
        raise FueraDeAlcance("saturacion", f"T = {T:.9g} K, P = {P:.9g} Pa es el punto triple del cierre "
                             f"({Ttr:.9g} K, {Ptr:.9g} Pa): coexisten hielo Ih, líquido y vapor y T, P no "
                             "determinan cuánto hay de cada uno.", triple=True)
    for par, pc in _coexistencias_en_T(T, P):
        if abs(P / pc - 1) <= TOL_COEX:
            raise FueraDeAlcance("saturacion", f"P = {P:.9g} Pa coincide con la curva {par[0]}-{par[1]} a "
                                 f"T = {T:.6g} K (P = {pc:.9g} Pa): las dos fases coexisten y T, P no determinan "
                                 "el reparto.", par=par, Pc=pc)
    cands = candidatas(T, P)
    if not cands:
        raise FueraDeAlcance("no_convergente", f"Ninguna fase evaluable a T = {T:.6g} K, P = {P:.6g} Pa.")
    f = min(cands, key=lambda c: c.g)
    return _certificar(_estado("TP", T, P, [(f, 1.0)]))


def _secuencia_isobara(P):
    """[(tipo, T_lo, T_hi)] de fases estables al subir T a P fija, y las mesetas entre ellas."""
    Ttr, Ptr = triple()
    if abs(P / Ptr - 1) <= TOL_COEX:
        return None
    if P < Ptr:
        Ts = T_sublimacion(P)
        if Ts is None:
            return [("vapor", T_MIN, T_MAX)]
        return [("solido", T_MIN, Ts), ("vapor", Ts, T_MAX)]
    Tm = T_fusion(P)
    tramos = [("solido", T_MIN, Tm)]
    Tb = T_vaporizacion(P)
    if Tb is None or Tb >= T_MAX:
        tramos.append(("liquido", Tm, T_MAX))
    else:
        tramos += [("liquido", Tm, Tb), ("vapor", Tb, T_MAX)]
    return tramos


def evaluar_isobara(espec, P, y_nombre, y):
    """PH (y_nombre 'h') o UP ('u'), y por kg."""
    if not P_MIN <= P <= P_MAX:
        raise FueraDeAlcance("fuera_de_dominio", f"P = {P:.6g} Pa fuera del dominio [{P_MIN:g}, {P_MAX:.3g}] Pa.",
                             P_fuera=True)
    tramos = _secuencia_isobara(P)
    Ttr, Ptr = triple()
    Y = lambda f: f.h if y_nombre == "h" else f.u
    if tramos is None:
        # en el triple: tres fases, dos ecuaciones (masa y energia)
        fs = [fase(t, Ttr, Ptr) for t in FASES]
        ys = [Y(f) for f in fs]
        if min(ys) < y < max(ys):
            raise FueraDeAlcance("saturacion", f"P = {P:.9g} Pa es la presión del punto triple y {y_nombre} = {y:.9g} "
                                 "J/kg cae entre las del hielo y el vapor: tres fases y dos ecuaciones (masa y "
                                 "energía) no determinan el reparto.", triple=True)
        tramos = ([("solido", T_MIN, Ttr)] if y <= ys[0] else [("vapor", Ttr, T_MAX)])
    for k, (tipo, a, b) in enumerate(tramos):
        fa, fb = fase(tipo, a, P), fase(tipo, b, P)
        if fa is None or fb is None:
            raise FueraDeAlcance("no_convergente", f"La fase {tipo} no es evaluable en el tramo [{a:.6g}, {b:.6g}] K "
                                 f"a P = {P:.6g} Pa.")
        if k == 0 and y < Y(fa):
            raise FueraDeAlcance("fuera_de_dominio", f"{y_nombre} = {y:.9g} J/kg exige T < {T_MIN} K a P = {P:.6g} Pa.",
                                 T_fuera=True)
        if Y(fa) <= y <= Y(fb):
            if y == Y(fa):
                T = a
            elif y == Y(fb):
                T = b
            else:
                T = brentq(lambda T: Y(fase(tipo, T, P)) - y, a, b, xtol=1e-300, rtol=1e-15, maxiter=300)
            e = _estado(espec, T, P, [(fase(tipo, T, P), 1.0)])
            e.residuos["especificacion"] = (abs(Y(e.fases[0][0]) - y) / max(abs(y), R * T), 1e-12)
            return _certificar(e)
        if k + 1 < len(tramos):
            sig = tramos[k + 1][0]
            fc = fase(sig, b, P)
            if Y(fb) < y < Y(fc):
                beta = (y - Y(fb)) / (Y(fc) - Y(fb))
                e = _estado(espec, b, P, [(fb, 1 - beta), (fc, beta)])
                e.residuos["especificacion"] = (abs((Y(fb) * (1 - beta) + Y(fc) * beta) - y) / max(abs(y), R * b), 1e-12)
                return _certificar(e)
    raise FueraDeAlcance("fuera_de_dominio", f"{y_nombre} = {y:.9g} J/kg exige T > {T_MAX} K a P = {P:.6g} Pa.",
                         T_fuera=True)


def evaluar_PH(P, h):
    return evaluar_isobara("PH", P, "h", h)


def evaluar_UP(P, u):
    return evaluar_isobara("UP", P, "u", u)


# ---------------------------- UV ----------------------------
def _raices_en(F, a, b, n=120):
    """Raices de F en [a, b] por barrido y Brent (F puede devolver None fuera de su validez)."""
    xs = _lin(a, b, n)
    vals = [F(x) for x in xs]
    sal = []
    for k in range(n - 1):
        fa, fb = vals[k], vals[k + 1]
        if (fa is None) != (fb is None):
            # borde de validez dentro del intervalo (p. ej. P del hielo que pasa a negativa): se acerca el
            # extremo valido al borde por biseccion para no perder una raiz pegada a el
            xv, xn = (xs[k + 1], xs[k]) if fa is None else (xs[k], xs[k + 1])
            for _ in range(60):
                xm = 0.5 * (xv + xn)
                if F(xm) is None:
                    xn = xm
                else:
                    xv = xm
            fv = F(xv)
            if fa is None:
                xs_k, fa = xv, fv
                xa, xb = xv, xs[k + 1]
            else:
                fb = fv
                xa, xb = xs[k], xv
            if fa * fb < 0:
                try:
                    sal.append(brentq(lambda x: F(x), xa, xb, xtol=1e-300, rtol=1e-15, maxiter=300))
                except (ValueError, TypeError):
                    pass
            elif fv == 0:
                sal.append(xv)
            continue
        if fa is None or fb is None:
            continue
        if fa == 0:
            sal.append(xs[k])
        elif fa * fb < 0:
            try:
                sal.append(brentq(lambda x: F(x), xs[k], xs[k + 1], xtol=1e-300, rtol=1e-15, maxiter=300))
            except (ValueError, TypeError):
                pass
    return sal


def _candidatas_UV(u, v):
    cands = []
    Ttr, Ptr = triple()
    # una fase solida: P de v a cada T
    def F_s(T):
        P = hi.presion_de_volumen(T, v)
        if P is None or not P_MIN <= P <= P_MAX:
            return None
        return hi.propiedades(T, P).u - u
    for T in _raices_en(F_s, T_MIN, Ttr):
        P = hi.presion_de_volumen(T, v)
        cands.append(_estado("UV", T, P, [(fase("solido", T, P), 1.0)]))
    # una fase fluida: (T, rho = 1/v)
    rho = 1.0 / v
    def F_f(T):
        p = ag.propiedades(T, rho)
        if not (p.dP_drho_T > 0 and P_MIN <= p.P <= P_MAX):
            return None
        return p.u - u
    for T in _raices_en(F_f, T_LIQUIDO_MIN if rho > 300 else T_MIN, T_MAX):
        tipo = "liquido" if rho > 300 else "vapor"
        f = _fase_fluida_rho(tipo, T, rho)
        if f is not None and P_MIN <= f.P <= P_MAX:
            # la fase debe ser la de su rama a (T, P): la raiz de densidad de esa rama es rho
            r2 = _rho_liquido(T, f.P) if tipo == "liquido" else _rho_vapor(T, f.P)
            if r2 is not None and abs(r2 / rho - 1) < 1e-9:
                cands.append(_estado("UV", T, f.P, [(f, 1.0)]))
    # dos fases sobre cada curva, parametrizadas por T
    curvas_ = (("solido", "vapor", P_sublimacion, T_MIN, Ttr),
               ("solido", "liquido", P_fusion, T_fusion(P_MAX), Ttr),
               ("liquido", "vapor", P_vaporizacion, Ttr, T_MAX))
    for a, b, Pc, Tlo, Thi in curvas_:
        def par(T):
            P = Pc(T)
            if P is None or not P_MIN <= P <= P_MAX:
                return None
            fa, fb = fase(a, T, P), fase(b, T, P)
            if fa is None or fb is None:
                return None
            beta = (v - fa.v) / (fb.v - fa.v)
            return P, fa, fb, beta

        def F_c(T):
            q = par(T)
            if q is None or not 0.0 <= q[3] <= 1.0:
                return None
            P, fa, fb, beta = q
            return fa.u * (1 - beta) + fb.u * beta - u
        for T in _raices_en(F_c, Tlo * (1 + 1e-12), Thi * (1 - 1e-12)):
            P, fa, fb, beta = par(T)
            cands.append(_estado("UV", T, P, [(fa, 1 - beta), (fb, beta)]))
    # tres fases en el triple: masa, U y V determinan el reparto (si es positivo)
    fs = [fase(t, Ttr, Ptr) for t in FASES]
    A = [[1.0, 1.0, 1.0], [f.u for f in fs], [f.v for f in fs]]
    bvec = [1.0, u, v]
    import numpy as np
    try:
        betas = np.linalg.solve(np.array(A), np.array(bvec))
        if all(x >= 0 for x in betas):
            cands.append(_estado("UV", Ttr, Ptr, [(f, float(x)) for f, x in zip(fs, betas) if x > 0]))
    except np.linalg.LinAlgError:
        pass
    return cands


def evaluar_UV(u, v):
    if not v > 0:
        raise FueraDeAlcance("invalido", "El volumen especifico debe ser positivo.")
    cands = _candidatas_UV(u, v)
    if not cands:
        raise FueraDeAlcance("fuera_de_dominio", f"Ningún estado del dominio (T en [{T_MIN}, {T_MAX}] K, P en "
                             f"[{P_MIN:g}, {P_MAX:.3g}] Pa) tiene u = {u:.9g} J/kg y v = {v:.9g} m3/kg.")
    e = max(cands, key=lambda c: c.s)
    e.residuos["especificacion"] = (max(abs(e.u - u) / max(abs(u), R * e.T), abs(e.v - v) / v), 1e-12)
    e.residuos["maxima_entropia"] = (0.0, 0.0)
    e.estabilidad_candidatas_UV = [(len(c.fases), c.T, c.s) for c in cands]
    return _certificar(e)
