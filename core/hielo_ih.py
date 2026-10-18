"""
Hielo Ih: ecuacion de estado de IAPWS R10-06(2009), "Revised Release on the
Equation of State 2006 for H2O Ice Ih" (Feistel y Wagner, J. Phys. Chem. Ref.
Data 35, 1021 (2006)). https://www.iapws.org/relguide/Ice-2009.html

La formulacion da la energia de Gibbs especifica g(T, p) [J/kg]:

  g = g0(p) - s0 Tt tau + Tt Re sum_k r_k [ (t_k - tau) ln(t_k - tau) + (t_k + tau) ln(t_k + tau)
                                            - 2 t_k ln t_k - tau^2 / t_k ]

con tau = T/Tt, g0(p) = sum_k g0k (pi - pi0)^k, r_2(p) = sum_k r2k (pi - pi0)^k,
pi = p/pt, pi0 = p0/pt. Las constantes (Tabla 2 de la release) se copian
literalmente. s0 es el valor "IAPWS-95": con el, las referencias del hielo
coinciden con las de IAPWS-95 (u y s del liquido nulos en el punto triple),
de modo que g del hielo y g del agua fluida de core/agua_iapws95.py son
comparables sin ningun desplazamiento.

Validez: 0 < T <= 273.16 K, p <= 210 MPa (hielo Ih estable o metastable
cerca de su region). Fuera no se evalua. verificar() compara con los
valores de comprobacion de la Tabla 6 de la release.
"""

import cmath
import math
from dataclasses import dataclass

TT = 273.16                 # K, punto triple
PT = 611.657                # Pa
P0 = 101325.0               # Pa
T_MAX = TT
P_MAX = 210e6

G0 = (-0.632020233335886e6, 0.655022213658955, -0.189369929326131e-7,
      0.339746123271053e-14, -0.556464869058991e-21)
S0 = -0.332733756492168e4   # J/(kg K), version IAPWS-95
T1 = complex(0.368017112855051e-1, 0.510878114959572e-1)
R1 = complex(0.447050716285388e2, 0.656876847463481e2)
T2 = complex(0.337315741065416, 0.335449415919309)
R2 = (complex(-0.725974574329220e2, -0.781008427112870e2),
      complex(-0.557107698030123e-4, 0.464578634580806e-4),
      complex(0.234801409215913e-10, -0.285651142904972e-10))

FUENTE = ("IAPWS R10-06(2009), Revised Release on the Equation of State 2006 for H2O Ice Ih "
          "(Feistel y Wagner 2006); coeficientes de la Tabla 2, comprobacion con la Tabla 6")


class FueraDeAlcanceHielo(Exception):
    def __init__(self, mensaje):
        super().__init__(mensaje)
        self.mensaje = mensaje


def _derivadas(T, p):
    """g y sus derivadas hasta segundo orden en (T, p), en J/kg, K y Pa."""
    if not (0 < T <= T_MAX * (1 + 1e-12) and 0 < p <= P_MAX):
        raise FueraDeAlcanceHielo(f"Hielo Ih fuera de la validez de R10-06: T = {T:.6g} K, p = {p:.6g} Pa "
                                  f"(0 < T <= {TT} K, p <= {P_MAX:.3g} Pa).")
    tau = T / TT
    pi, pi0 = p / PT, P0 / PT
    dp = pi - pi0
    g0 = sum(G0[k] * dp ** k for k in range(5))
    g0_p = sum(G0[k] * k / PT * dp ** (k - 1) for k in range(1, 5))
    g0_pp = sum(G0[k] * k * (k - 1) / PT ** 2 * dp ** (k - 2) for k in range(2, 5))
    r2 = sum(R2[k] * dp ** k for k in range(3))
    r2_p = sum(R2[k] * k / PT * dp ** (k - 1) for k in range(1, 3))
    r2_pp = R2[2] * 2 / PT ** 2

    def termino(t):
        return ((t - tau) * cmath.log(t - tau) + (t + tau) * cmath.log(t + tau)
                - 2 * t * cmath.log(t) - tau ** 2 / t)

    def termino_tau(t):
        return -cmath.log(t - tau) + cmath.log(t + tau) - 2 * tau / t

    def termino_tautau(t):
        return 1 / (t - tau) + 1 / (t + tau) - 2 / t

    g = g0 - S0 * TT * tau + TT * (R1 * termino(T1) + r2 * termino(T2)).real
    g_T = -S0 + (R1 * termino_tau(T1) + r2 * termino_tau(T2)).real
    g_p = g0_p + TT * (r2_p * termino(T2)).real
    g_TT = (R1 * termino_tautau(T1) + r2 * termino_tautau(T2)).real / TT
    g_Tp = (r2_p * termino_tau(T2)).real
    g_pp = g0_pp + TT * (r2_pp * termino(T2)).real
    return g, g_T, g_p, g_TT, g_Tp, g_pp


@dataclass(frozen=True)
class PropiedadesHielo:
    T: float
    P: float
    g: float        # J/kg
    v: float        # m3/kg
    rho: float      # kg/m3
    s: float        # J/(kg K)
    h: float        # J/kg
    u: float        # J/kg
    f: float        # J/kg
    cp: float       # J/(kg K)
    alfa: float     # 1/K
    beta: float     # Pa/K, coeficiente de presion
    kappa_T: float  # 1/Pa
    kappa_s: float  # 1/Pa
    derivadas: tuple


def propiedades(T, p):
    g, g_T, g_p, g_TT, g_Tp, g_pp = _derivadas(T, p)
    s = -g_T
    h = g + T * s
    return PropiedadesHielo(
        T=T, P=p, g=g, v=g_p, rho=1 / g_p, s=s, h=h, u=h - p * g_p, f=g - p * g_p, cp=-T * g_TT,
        alfa=g_Tp / g_p, beta=-g_Tp / g_pp, kappa_T=-g_pp / g_p,
        kappa_s=(g_Tp ** 2 - g_TT * g_pp) / (g_p * g_TT), derivadas=(g, g_T, g_p, g_TT, g_Tp, g_pp))


def presion_de_volumen(T, v):
    """p con g_p(T, p) = v (Newton en p; g_pp < 0). None si no hay raiz en (0, P_MAX]."""
    p = P0
    for _ in range(60):
        try:
            _, _, g_p, _, _, g_pp = _derivadas(T, p)
        except FueraDeAlcanceHielo:
            return None
        paso = (g_p - v) / g_pp
        p_n = p - paso
        if not 0 < p_n <= P_MAX:
            p_n = min(max(p_n, 0.5 * p), 0.5 * (p + P_MAX))
            if abs(p_n - p) < 1e-300:
                return None
        if abs(p_n - p) <= 1e-15 * max(abs(p), 1e3):
            p = p_n
            break
        p = p_n
    try:
        if abs(_derivadas(T, p)[2] - v) > 1e-13 * v:
            return None
    except FueraDeAlcanceHielo:
        return None
    return p


# Tabla 6 de R10-06(2009): (T, p) -> valores de comprobacion
TABLA_6 = {
    (273.16, 611.657): dict(
        g=0.611784135, g_p=0.109085812737e-2, g_T=0.122069433940e4, g_pp=-0.128495941571e-12,
        g_Tp=0.174387964700e-6, g_TT=-0.767602985875e1, h=-0.333444253966e6, f=-0.55446875e-1,
        u=-0.333444921197e6, s=-0.122069433940e4, cp=0.209678431622e4, rho=0.916709492200e3,
        alfa=0.159863102566e-3, beta=0.135714764659e7, kappa_T=0.117793449348e-9, kappa_s=0.114161597779e-9),
    (273.152519, 101325.0): dict(
        g=0.10134274069e3, g_p=0.109084388214e-2, g_T=0.122076932550e4, g_pp=-0.128485364928e-12,
        g_Tp=0.174362219972e-6, g_TT=-0.767598233365e1, h=-0.333354873637e6, f=-0.918701567e1,
        u=-0.333465403393e6, s=-0.122076932550e4, cp=0.209671391024e4, rho=0.916721463419e3,
        alfa=0.159841589458e-3, beta=0.135705899321e7, kappa_T=0.117785291765e-9, kappa_s=0.114154442556e-9),
    (100.0, 100e6): dict(
        g=-0.222296513088e6, g_p=0.106193389260e-2, g_T=0.261195122589e4, g_pp=-0.941807981761e-13,
        g_Tp=0.274505162488e-7, g_TT=-0.866333195517e1, h=-0.483491635676e6, f=-0.328489902347e6,
        u=-0.589685024936e6, s=-0.261195122589e4, cp=0.866333195517e3, rho=0.941678203297e3,
        alfa=0.258495528207e-4, beta=0.291466166994e6, kappa_T=0.886880048115e-10, kappa_s=0.886060982687e-10),
}


def verificar():
    """Max error relativo frente a la Tabla 6 (las cifras publicadas son 9-12 significativas; g en el
    triple y f se comparan en absoluto porque son diferencias pequenas de numeros grandes)."""
    peor = 0.0
    detalle = []
    for (T, p), ref in TABLA_6.items():
        q = propiedades(T, p)
        g, g_T, g_p, g_TT, g_Tp, g_pp = q.derivadas
        calc = dict(g=g, g_p=g_p, g_T=g_T, g_pp=g_pp, g_Tp=g_Tp, g_TT=g_TT, h=q.h, f=q.f, u=q.u, s=q.s,
                    cp=q.cp, rho=q.rho, alfa=q.alfa, beta=q.beta, kappa_T=q.kappa_T, kappa_s=q.kappa_s)
        for k, r in ref.items():
            if k in ("g", "f"):
                err = abs(calc[k] - r) / 1e3          # J/kg sobre la escala de h (~1e5): absoluto/1e3
            else:
                err = abs(calc[k] - r) / abs(r)
            detalle.append((T, p, k, calc[k], r, err))
            peor = max(peor, err)
    return peor, detalle
