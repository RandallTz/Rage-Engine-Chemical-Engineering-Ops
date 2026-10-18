"""
Coexistencia liquido-vapor de un binario: operacion compartida del paquete.

Solo usa la interfaz publica de un paquete de mezcla (core/mezclas.Sistema u otro adaptador con la misma
interfaz): `mu(tipo, T, P, x, idx)`, `prueba_estabilidad(T, P, mu_ref, idx, incluir_vapor)`,
`T_saturacion(P, i)`, `P_saturacion(T, i)`, `dominio(T, P)`, `equilibrio_TP(T, P, n)` y `fase(...)`.
No contiene ninguna formula de actividad, presion de vapor ni fugacidad: la igualdad de potenciales
quimicos del paquete es la unica condicion de equilibrio. Un adaptador basado en EOS que exponga `mu` sirve
igual.

Corte 'Txy' (P fija): incognitas T e y para una composicion liquida x dada.
Corte 'Pxy' (T fija): incognitas P e y.
Azeotropo: incognitas (T o P) y x con y = x.

Composiciones en el orden del sistema; un binario: x = (x0, 1 - x0).
"""

import math

import numpy as np

from core import mezclas as mz

TOL_MU = mz.TOL_MU          # max |mu_i^L - mu_i^V| / (R T)
TOL_TM = mz.TOL_TM          # -min tm admitido
TOL_NEWTON = 1e-13


class SinConvergencia(Exception):
    def __init__(self, motivo, mensaje):
        super().__init__(mensaje)
        self.motivo = motivo        # 'no_convergente' | 'fuera_de_dominio'
        self.mensaje = mensaje


def _logit(p):
    return math.log(p / (1.0 - p))


def _sig(u):
    return 1.0 / (1.0 + math.exp(-u)) if u > -700 else 0.0


def _TP(corte, fijo, var):
    return (var, fijo) if corte == "Txy" else (fijo, var)


def residuo(sis, corte, fijo, var, xl, yv):
    """(mu_i^L(x) - mu_i^V(y)) / (R T) para i = 0, 1 (ambas especies presentes)."""
    T, P = _TP(corte, fijo, var)
    sis.dominio(T, P)
    idx = [0, 1]
    mL = sis.mu("liquido", T, P, np.asarray(xl, float), idx)
    mV = sis.mu("vapor", T, P, np.asarray(yv, float), idx)
    return (mL - mV) / (mz.R * T)


def _newton(F, v0, max_iter=40):
    v = np.array(v0, dtype=float)
    f = F(v)
    for _ in range(max_iter):
        if np.max(np.abs(f)) < TOL_NEWTON:
            return v, f
        J = np.empty((len(v), len(v)))
        for j in range(len(v)):
            d = np.zeros_like(v)
            d[j] = 1e-7
            J[:, j] = (F(v + d) - F(v - d)) / 2e-7
        paso = np.linalg.solve(J, -f)
        a = 1.0
        for _ in range(30):
            try:
                fn = F(v + a * paso)
            except (mz.FueraDeAlcance, FloatingPointError, OverflowError, ValueError):
                fn = None
            if fn is not None and np.max(np.abs(fn)) < np.max(np.abs(f)):
                v, f = v + a * paso, fn
                break
            a *= 0.5
        else:
            break
    return v, f


def resolver_punto(sis, corte, fijo, x0, semilla):
    """Punto regular de coexistencia con x = (x0, 1-x0), 0 < x0 < 1. semilla = (var, y0).
    Devuelve (var, y0). SinConvergencia si no converge o sale del dominio."""
    xl = (x0, 1.0 - x0)

    def F(v):
        y0 = _sig(v[1])
        if not 0.0 < y0 < 1.0:
            raise ValueError("y fuera de (0, 1)")
        return residuo(sis, corte, fijo, math.exp(v[0]), xl, (y0, 1.0 - y0))
    var0, y00 = semilla
    y00 = min(max(y00, 1e-300), 1 - 1e-16)
    try:
        v, f = _newton(F, [math.log(var0), _logit(y00)])
    except mz.FueraDeAlcance as x:
        raise SinConvergencia("fuera_de_dominio", x.mensaje)
    except (np.linalg.LinAlgError, FloatingPointError, OverflowError, ValueError) as x:
        raise SinConvergencia("no_convergente", f"Newton: {x}")
    if not np.max(np.abs(f)) < 1e-11:
        raise SinConvergencia("no_convergente", f"residuo final {np.max(np.abs(f)):.2e}")
    return math.exp(v[0]), _sig(v[1])


def resolver_azeotropo(sis, corte, fijo, semilla):
    """Azeotropo (x = y): semilla = (var, x0). Devuelve (var, x0)."""
    def F(v):
        x0 = _sig(v[1])
        if not 0.0 < x0 < 1.0:
            raise ValueError("x fuera de (0, 1)")
        c = (x0, 1.0 - x0)
        return residuo(sis, corte, fijo, math.exp(v[0]), c, c)
    try:
        v, f = _newton(F, [math.log(semilla[0]), _logit(semilla[1])])
    except mz.FueraDeAlcance as x:
        raise SinConvergencia("fuera_de_dominio", x.mensaje)
    except (np.linalg.LinAlgError, FloatingPointError, OverflowError, ValueError) as x:
        raise SinConvergencia("no_convergente", f"Newton: {x}")
    if not np.max(np.abs(f)) < 1e-11:
        raise SinConvergencia("no_convergente", f"residuo final {np.max(np.abs(f)):.2e}")
    return math.exp(v[0]), _sig(v[1])


def extremo_puro(sis, corte, fijo, i):
    """Saturacion del componente puro i en el MISMO paquete: T (Txy) o P (Pxy). None si no existe en el
    dominio."""
    try:
        if corte == "Txy":
            return sis.T_saturacion(fijo, i)
        T = fijo
        P = sis.P_saturacion(T, i)
        sis.dominio(T, P)
        return P
    except (mz.FueraDeAlcance, ValueError):
        return None


def semilla_por_flash(sis, corte, fijo, x0, iteraciones=45):
    """Semilla generica por el flash TP certificado del paquete: la T (o P) donde aparece vapor para la
    composicion global x, por biseccion, y la composicion del vapor justo despues. None si no la hay en el
    dominio. Solo es un punto de partida: el punto se resuelve y certifica despues.
    Si no hay cambio de fase dentro del dominio, lanza SinConvergencia('fuera_de_dominio'): la burbuja de esa
    composicion cae fuera del dominio del paquete (no es un fallo numerico)."""
    n = np.array([x0, 1.0 - x0])
    if corte == "Txy":
        lo, hi = sis.T_rango
        conv = lambda q: q
    else:
        lo, hi = math.log(mz.P_MIN), math.log(mz.P_MAX)
        conv = math.exp

    def hay_vapor(q):
        T, P = _TP(corte, fijo, conv(q))
        e = sis.equilibrio_TP(T, P, n)
        return any(f.tipo == "vapor" for f in e.fases), e
    try:
        v_lo, _ = hay_vapor(lo)
        v_hi, _ = hay_vapor(hi)
    except mz.FueraDeAlcance:
        return None
    # Txy: vapor a T alta; Pxy: vapor a P baja. Sin cambio dentro del dominio: la coexistencia esta fuera.
    if (corte == "Txy" and (v_lo or not v_hi)) or (corte == "Pxy" and (v_hi or not v_lo)):
        lado = ("por encima de" if not v_hi else "por debajo de") if corte == "Txy" else \
            ("por debajo de" if not v_lo else "por encima de")
        raise SinConvergencia("fuera_de_dominio", f"para x0 = {x0:.6g} la coexistencia L-V queda {lado} el "
                              f"dominio del paquete en {'T' if corte == 'Txy' else 'P'}")
    for _ in range(iteraciones):
        m = 0.5 * (lo + hi)
        try:
            v, _ = hay_vapor(m)
        except mz.FueraDeAlcance:
            return None
        if (v and corte == "Txy") or (not v and corte == "Pxy"):
            hi = m
        else:
            lo = m
    q = hi if corte == "Txy" else lo
    try:
        _, e = hay_vapor(q)
    except mz.FueraDeAlcance:
        return None
    fv = next((f for f in e.fases if f.tipo == "vapor"), None)
    if fv is None:
        return None
    return conv(q), float(fv.x[0])


def certificar(sis, corte, fijo, T, P, xl, yv, idx=(0, 1)):
    """Certificado de un punto de coexistencia publicado en (T, P) con fases limite L (xl) y V (yv): igualdad de
    mu de cada especie presente, normalizacion, condicion fija del corte (P = fijo en Txy, T = fijo en Pxy),
    distincion de fases y estabilidad (plano tangente con la mu comun frente a vapor y liquido de prueba)."""
    idx = list(idx)
    xl = np.asarray(xl, float)
    yv = np.asarray(yv, float)
    xs, ys = xl[idx], yv[idx]
    RT = mz.R * T
    res = []
    mL = sis.mu("liquido", T, P, xs, idx)
    mV = sis.mu("vapor", T, P, ys, idx)
    r_mu = float(np.max(np.abs(mL - mV)) / RT)
    res.append({"id": "igualdad_mu", "valor": r_mu, "tolerancia": TOL_MU, "escala": "R T",
                "estado": "cumple" if r_mu <= TOL_MU else "no_cumple"})
    r_n = max(abs(float(xl.sum()) - 1.0), abs(float(yv.sum()) - 1.0))
    ok_n = r_n <= 1e-14 and np.all(xl >= 0) and np.all(yv >= 0)
    res.append({"id": "normalizacion", "valor": r_n, "tolerancia": 1e-14, "escala": "1",
                "estado": "cumple" if ok_n else "no_cumple"})
    r_c = abs((P if corte == "Txy" else T) / fijo - 1.0)
    res.append({"id": "condicion_fija", "valor": float(r_c), "tolerancia": 1e-14, "escala": "relativa al corte",
                "estado": "cumple" if r_c <= 1e-14 else "no_cumple"})
    vL = sis.fase("l", "liquido", T, P, xs, idx).v
    vV = sis.fase("v", "vapor", T, P, ys, idx).v
    r_d = abs(vV - vL) / vV
    res.append({"id": "distincion_fases", "valor": float(r_d), "tolerancia": 1e-3, "escala": "|v_V - v_L|/v_V",
                "estado": "cumple" if r_d > 1e-3 else "no_cumple"})
    pr = sis.prueba_estabilidad(T, P, mL, idx, incluir_vapor=True)
    tm_min = min(q[2] for q in pr)
    est = {"estado": "estable" if tm_min >= -TOL_TM else "inestable", "tmMinimo": float(tm_min),
           "tolerancia": TOL_TM, "candidatas": sorted({q[0] for q in pr}), "pruebas": len(pr),
           "metodo": "distancia al plano tangente con la mu comun: vapor por minimo analitico, liquido en malla "
                     "de 1361 puntos en logit con refinamiento de cada minimo local (no es una demostracion del "
                     "minimo global)"}
    if tm_min < -TOL_TM:
        q = min(pr, key=lambda q: q[2])
        w = np.zeros(len(xl))
        w[idx] = q[1]
        est["competidora"] = {"tipo": q[0], "composicion": [float(v) for v in w], "tm": float(q[2])}
    ok = all(r["estado"] == "cumple" for r in res) and est["estado"] == "estable"
    return {"estado": "cumple" if ok else "no_cumple", "residuos": res, "estabilidad": est}
