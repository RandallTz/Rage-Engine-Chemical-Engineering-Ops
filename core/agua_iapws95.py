"""
Agua pura por IAPWS-95, para el motor independiente (/motor).

Fuente: IAPWS R6-95(2018), "Revised Release on the IAPWS Formulation 1995
for the Thermodynamic Properties of Ordinary Water Substance for General
and Scientific Use", y Wagner & Pruss, J. Phys. Chem. Ref. Data 31 (2002)
387-535. La energia de Helmholtz adimensional y sus derivadas las evalua
`chemicals.iapws` (version auditada: VERSION_CHEMICALS_AUDITADA). Este
modulo no usa nada mas de esa libreria: ni su eleccion de fase
(`iapws95_rho` elige rama comparando con su Psat) ni `iapws95_properties`.
Elige la rama, resuelve la densidad y certifica la estabilidad por su
cuenta.

    phi(delta, tau) = phi0 + phir,   delta = rho/rho_c,   tau = T_c/T
    P   = rho R T (1 + delta phir_d)
    u   = R T tau (phi0_t + phir_t)
    h   = u + P/rho
    s   = R [tau (phi0_t + phir_t) - phi0 - phir]
    f   = R T (phi0 + phir)                       (Helmholtz especifica)
    g   = f + P/rho
    cv  = -R tau^2 (phi0_tt + phir_tt)
    cp  = cv + T (dP/dT)_rho^2 / (rho^2 (dP/drho)_T)

Referencia de energia y entropia (la de IAPWS-95): u = 0 y s = 0 del
liquido saturado en el punto triple. Todo es especifico POR KG.

Las funciones son puras: no hay objetos con T/P internos que una
evaluacion pueda dejar cambiados para la siguiente.

Lo que NO es este modulo: no hay hielo (el dominio lo excluye), no hay
flash bifasico (un T/P en saturacion se rechaza como indeterminado) y no
hay especificaciones inversas (PH, UV, UP). Ver
docs/engine/thermodynamics-h0-h1.md.
"""

import math
from dataclasses import dataclass
from functools import lru_cache

import chemicals
import chemicals.iapws as _w
from scipy.optimize import brentq, minimize_scalar

VERSION_CHEMICALS_AUDITADA = "1.5.2"
CAS = "7732-18-5"
FORMULACION = "IAPWS-95 (R6-95(2018); Wagner y Pruss 2002), via chemicals.iapws"

R = _w.iapws95_R                    # 461.51805 J/(kg K)
M = _w.iapws95_MW * 1e-3            # 0.018015268 kg/mol
TC = _w.iapws95_Tc                  # 647.096 K
RHOC = _w.iapws95_rhoc              # 322 kg/m3
PC = _w.iapws95_Pc                  # 22.064e6 Pa
T_TRIPLE = 273.16                   # K

# Dominio publicado: envolvente rectangular en la que se ha verificado el
# modelo. T >= T_TRIPLE y P <= 100 MPa dejan fuera todo hielo estable: la
# fusion del hielo Ih baja de 273.16 K al subir P, y los hielos III, V y VI
# solo son estables por encima de 209.9 MPa (IAPWS R14-08). El limite
# superior de T es el de la region 2 de IF97, para poder contrastar todo el
# dominio con una formulacion independiente.
T_MIN, T_MAX = T_TRIPLE, 1073.15
P_MIN, P_MAX = 100.0, 100e6

# Banda critica excluida: ahi la compresibilidad diverge, la densidad a
# T/P esta mal condicionada y el margen de estabilidad es nulo.
T_CRITICA = (0.995 * TC, 1.005 * TC)
P_CRITICA = (0.95 * PC, 1.05 * PC)

# |P/Psat - 1| <= TOL_SATURACION se trata como un punto de la curva de
# saturacion: T y P no determinan el reparto liquido/vapor.
TOL_SATURACION = 1e-6

# Las ramas candidatas de la busqueda de estabilidad llegan hasta la
# densidad de P = 1 GPa, el limite de validez de IAPWS-95.
P_LIMITE_FORMULACION = 1e9

TOL_ESTABILIDAD = 1e-9      # -min(TPD)/P
TOL_EOS = 1e-12             # |P(T,rho) - P| / max(P, rho (dP/drho)_T)
TOL_SATURACION_MAXWELL = 1e-9
TOL_DERIVADAS = 1e-6        # cp, cv analiticas frente a diferencias centradas
PUNTOS_POR_RAMA = 400


class FueraDeAlcance(Exception):
    """El modelo no puede evaluar este T/P. `motivo` es una de:
    'fuera_de_dominio', 'region_critica', 'saturacion', 'no_convergente',
    'estabilidad_no_certificada'."""

    def __init__(self, motivo, mensaje, **datos):
        super().__init__(mensaje)
        self.motivo = motivo
        self.mensaje = mensaje
        self.datos = datos


@dataclass(frozen=True)
class Propiedades:
    T: float            # K
    rho: float          # kg/m3
    P: float            # Pa, la de la EOS en (T, rho)
    v: float            # m3/kg
    u: float            # J/kg
    h: float            # J/kg
    s: float            # J/(kg K)
    f: float            # J/kg, Helmholtz especifica
    g: float            # J/kg, Gibbs especifica
    cv: float           # J/(kg K)
    cp: float           # J/(kg K)
    w: float            # m/s
    dP_drho_T: float    # Pa m3/kg
    dP_dT_rho: float    # Pa/K


def _phi(T, rho):
    tau, d = TC / T, rho / RHOC
    return (tau, d,
            _w.iapws95_A0(tau, d), _w.iapws95_dA0_dtau(tau, d), _w.iapws95_d2A0_dtau2(tau, d),
            _w.iapws95_Ar(tau, d), _w.iapws95_dAr_ddelta(tau, d), _w.iapws95_d2Ar_ddelta2(tau, d),
            _w.iapws95_dAr_dtau(tau, d), _w.iapws95_d2Ar_dtau2(tau, d),
            _w.iapws95_d2Ar_ddeltadtau(tau, d))


def presion(T, rho):
    d = rho / RHOC
    return rho * R * T * (1.0 + d * _w.iapws95_dAr_ddelta(TC / T, d))


def _dP_drho(T, rho):
    tau, d = TC / T, rho / RHOC
    return R * T * (1.0 + 2.0 * d * _w.iapws95_dAr_ddelta(tau, d)
                    + d * d * _w.iapws95_d2Ar_ddelta2(tau, d))


def helmholtz(T, rho):
    """f(T, rho) [J/kg]."""
    tau, d = TC / T, rho / RHOC
    return R * T * (_w.iapws95_A0(tau, d) + _w.iapws95_Ar(tau, d))


def propiedades(T, rho):
    tau, d, a0, a0t, a0tt, ar, ard, ardd, art, artt, ardt = _phi(T, rho)
    RT = R * T
    P = rho * RT * (1.0 + d * ard)
    u = RT * tau * (a0t + art)
    s = R * (tau * (a0t + art) - a0 - ar)
    f = RT * (a0 + ar)
    v = 1.0 / rho
    cv = -R * tau * tau * (a0tt + artt)
    dP_drho = RT * (1.0 + 2.0 * d * ard + d * d * ardd)
    dP_dT = rho * R * (1.0 + d * ard - d * tau * ardt)
    cp = cv + T * dP_dT * dP_dT / (rho * rho * dP_drho)
    w = math.sqrt(dP_drho * cp / cv) if dP_drho > 0 else float("nan")
    return Propiedades(T=T, rho=rho, P=P, v=v, u=u, h=u + P * v, s=s, f=f,
                       g=f + P * v, cv=cv, cp=cp, w=w,
                       dP_drho_T=dP_drho, dP_dT_rho=dP_dT)


# ----------------------------------------------------------------------
# Saturacion: separa las dos ramas monofasicas por debajo de T_c
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Saturacion:
    T: float
    Psat: float
    rho_l: float
    rho_v: float
    residuo: float      # residuo de Maxwell, ver saturacion()


@lru_cache(maxsize=20000)        # funcion pura de T: la cache no cambia resultados
def saturacion(T):
    """Psat, rho' y rho'' de IAPWS-95 a T < T_c.

    Los valores salen de los ajustes de `chemicals` a la solucion de las
    condiciones de Maxwell resuelta en precision multiple (error relativo
    < 1e-12 segun la libreria). No se confia en eso: se recalculan las
    condiciones con la EOS y se devuelve el residuo

        max( |g' - g''|/(R T),  |P(rho'') - Psat|/Psat,
             |P(rho') - Psat| / (rho' (dP/drho)_T') )

    El residuo del liquido se escala con su modulo de compresibilidad
    isoterma porque su presion es rigida: un error de 1e-12 en rho' mueve
    P(rho') mucho mas que Psat."""
    if not T < TC:
        raise ValueError("Por encima de T_c no hay saturacion")
    Psat = float(_w.iapws95_Psat(T))
    rl = float(_w.iapws95_rhol_sat(T))
    rv = float(_w.iapws95_rhog_sat(T))
    pl, pv = propiedades(T, rl), propiedades(T, rv)
    residuo = max(abs(pl.g - pv.g) / (R * T),
                  abs(pv.P - Psat) / Psat,
                  abs(pl.P - Psat) / (rl * pl.dP_drho_T))
    return Saturacion(T=T, Psat=Psat, rho_l=rl, rho_v=rv, residuo=residuo)


# ----------------------------------------------------------------------
# Densidad en una rama monofasica
# ----------------------------------------------------------------------
def _densidad_tope(T, rho_inicial, P_objetivo):
    """Una densidad de la rama densa con P(T, rho) >= P_objetivo."""
    rho = rho_inicial
    for _ in range(200):
        if presion(T, rho) >= P_objetivo:
            return rho
        rho += 20.0
    raise FueraDeAlcance("no_convergente",
                         f"No se encontro densidad con P >= {P_objetivo:.6g} Pa a T = {T:.6g} K")


def _densidad_suelo(T, P_objetivo):
    """Una densidad de la rama diluida con P(T, rho) <= P_objetivo."""
    rho = 1e-3 * P_objetivo / (R * T)
    while presion(T, rho) > P_objetivo:
        rho *= 1e-3
    return rho


def ramas(T):
    """Intervalos de densidad [kg/m3] de las ramas monofasicas a T.

    Por debajo de T_c: vapor (0, rho''] y liquido [rho', rho(1 GPa)]. La
    region entre rho'' y rho' queda fuera: ahi IAPWS-95 no representa
    estados homogeneos fisicos (a 300 K y 300 kg/m3 da P ~ -1.5e23 Pa) y
    ningun estado homogeneo de esa region es estable frente a la
    separacion en las dos fases saturadas. Por encima de T_c: una rama.
    """
    if T < TC:
        sat = saturacion(T)
        tope = _densidad_tope(T, sat.rho_l, P_LIMITE_FORMULACION)
        return [("vapor", _densidad_suelo(T, P_MIN) * 1e-3, sat.rho_v),
                ("liquido", sat.rho_l, tope)], sat
    tope = _densidad_tope(T, RHOC, P_LIMITE_FORMULACION)
    return [("fluido", _densidad_suelo(T, P_MIN) * 1e-3, tope)], None


def densidad(T, P, lo, hi):
    """rho en [lo, hi] con P(T, rho) = P; P es creciente en la rama."""
    if not presion(T, lo) <= P <= presion(T, hi):
        raise FueraDeAlcance("no_convergente",
                             f"P = {P:.6g} Pa no esta en la rama [{lo:.6g}, {hi:.6g}] kg/m3 a T = {T:.6g} K")
    rho = brentq(lambda r: presion(T, r) - P, lo, hi, xtol=1e-300, rtol=1e-15, maxiter=500)
    for _ in range(3):      # pulido de Newton, sin salir de la rama
        paso = (presion(T, rho) - P) / _dP_drho(T, rho)
        nuevo = rho - paso
        if not lo <= nuevo <= hi:
            break
        rho = nuevo
    return rho


# ----------------------------------------------------------------------
# Estabilidad de una sustancia pura a T fija
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Estabilidad:
    residuo: float          # max(0, -min TPD) / P
    margen: float | None    # min TPD/P en minimos locales distintos del propio estado
    rho_margen: float | None
    evaluaciones: int
    ramas: tuple            # ((nombre, rho_min, rho_max), ...)


def estabilidad(T, rho_estado, ramas_T):
    """Distancia al plano tangente de una sustancia pura a T fija:

        TPD(rho) = rho [f(T, rho) - g*] + P*,   g* = g(T, rho*), P* = P(T, rho*)

    Es la energia de Helmholtz por volumen menos su tangente en rho*. Un
    estado es estable a (T, P*) si TPD >= 0 para toda densidad candidata:
    una fase de densidad rho con TPD < 0 tendria menor energia de Gibbs a
    la misma T y P. Se usa P* de la EOS, no la P pedida, para que TPD(rho*)
    = 0 exactamente y el error de resolver rho no se confunda con margen.

    Busqueda: PUNTOS_POR_RAMA puntos log-espaciados por rama (incluido
    rho*) y refinamiento acotado de cada minimo local de la malla. Es una
    busqueda en las ramas monofasicas de `ramas()`; no se demuestra un
    minimo global fuera de ellas."""
    pe = propiedades(T, rho_estado)
    g_s, P_s = pe.g, pe.P

    def tpd(r):
        return r * (helmholtz(T, r) - g_s) + P_s

    minimo, evaluaciones = 0.0, 0
    margen, rho_margen = None, None
    for _, lo, hi in ramas_T:
        n = PUNTOS_POR_RAMA
        malla = [math.exp(math.log(lo) + i * (math.log(hi) - math.log(lo)) / n) for i in range(n + 1)]
        if lo <= rho_estado <= hi:
            malla = sorted(set(malla + [rho_estado]))
        valores = [tpd(r) for r in malla]
        evaluaciones += len(malla)
        for i, val in enumerate(valores):
            izq = valores[i - 1] if i > 0 else math.inf
            der = valores[i + 1] if i + 1 < len(valores) else math.inf
            if not (val <= izq and val <= der):
                continue
            a, b = malla[max(i - 1, 0)], malla[min(i + 1, len(malla) - 1)]
            if b > a:
                res = minimize_scalar(tpd, bounds=(a, b), method="bounded",
                                      options={"xatol": 1e-12 * b})
                evaluaciones += int(res.nfev)
                r_min, v_min = (res.x, res.fun) if res.fun < val else (malla[i], val)
            else:
                r_min, v_min = malla[i], val
            minimo = min(minimo, v_min)
            # minimos que no son el propio estado
            if abs(math.log(r_min / rho_estado)) > 1e-3:
                if margen is None or v_min / P_s < margen:
                    margen, rho_margen = v_min / P_s, r_min
    return Estabilidad(residuo=max(0.0, -minimo) / P_s, margen=margen, rho_margen=rho_margen,
                       evaluaciones=evaluaciones, ramas=tuple(ramas_T))


# ----------------------------------------------------------------------
# Evaluacion T/P
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class EstadoAgua:
    tipo: str               # 'liquido' | 'vapor' | 'fluido'
    regimen: str            # 'ordinario' | 'supercritico'
    propiedades: Propiedades
    P: float                # la P pedida
    residuo_eos: float
    estabilidad: Estabilidad
    saturacion: Saturacion | None
    residuo_derivadas: float


def _derivadas(T, P, rho, rama, p):
    """max |cp - (dh/dT)_P| / cp, |cv - (du/dT)_rho| / cv con diferencias
    centradas de paso 1e-5 T, re-resolviendo rho a T +- dT en la rama del
    mismo nombre. nan si a T +- dT esa rama ya no contiene P."""
    dT = 1e-5 * T
    r_lado = []
    for Tl in (T + dT, T - dT):
        rama_l = [r for r in ramas(Tl)[0] if r[0] == rama]
        if not rama_l:
            return float("nan")
        try:
            r_lado.append(densidad(Tl, P, rama_l[0][1], rama_l[0][2]))
        except FueraDeAlcance:
            return float("nan")
    r_mas, r_menos = r_lado
    cp_fd = (propiedades(T + dT, r_mas).h - propiedades(T - dT, r_menos).h) / (2 * dT)
    cv_fd = (propiedades(T + dT, rho).u - propiedades(T - dT, rho).u) / (2 * dT)
    return max(abs(p.cp - cp_fd) / p.cp, abs(p.cv - cv_fd) / p.cv)


def evaluar_TP(T, P):
    """Estado estable del agua pura a (T [K], P [Pa]), o FueraDeAlcance."""
    if not (T_MIN <= T <= T_MAX and P_MIN <= P <= P_MAX):
        raise FueraDeAlcance(
            "fuera_de_dominio",
            f"T = {T:.6g} K, P = {P:.6g} Pa fuera del dominio verificado "
            f"T en [{T_MIN}, {T_MAX}] K, P en [{P_MIN:.6g}, {P_MAX:.6g}] Pa.",
            T_fuera=not T_MIN <= T <= T_MAX, P_fuera=not P_MIN <= P <= P_MAX)
    if T_CRITICA[0] <= T <= T_CRITICA[1] and P_CRITICA[0] <= P <= P_CRITICA[1]:
        raise FueraDeAlcance(
            "region_critica",
            f"T = {T:.6g} K, P = {P:.6g} Pa esta en la banda critica excluida "
            f"(T en [{T_CRITICA[0]:.6g}, {T_CRITICA[1]:.6g}] K y P en "
            f"[{P_CRITICA[0]:.6g}, {P_CRITICA[1]:.6g}] Pa).")

    ramas_T, sat = ramas(T)
    if sat is not None:
        if abs(P / sat.Psat - 1.0) <= TOL_SATURACION:
            raise FueraDeAlcance(
                "saturacion",
                f"P = {P:.9g} Pa coincide con Psat({T:.6g} K) = {sat.Psat:.9g} Pa "
                f"(|P/Psat - 1| <= {TOL_SATURACION:g}). Liquido y vapor coexisten y "
                "T, P no determinan cuanto hay de cada uno.",
                Psat=sat.Psat)
        nombre = "liquido" if P > sat.Psat else "vapor"
        _, lo, hi = next(r for r in ramas_T if r[0] == nombre)
        tipo, regimen = nombre, "ordinario"
    else:
        nombre, lo, hi = ramas_T[0]
        if P > PC:
            tipo, regimen = "fluido", "supercritico"
        else:
            tipo, regimen = "vapor", "ordinario"

    try:
        rho = densidad(T, P, lo, hi)
    except ValueError as e:
        raise FueraDeAlcance("no_convergente", f"La densidad no convergio: {e}")
    p = propiedades(T, rho)
    residuo_eos = abs(p.P - P) / max(P, rho * p.dP_drho_T)
    est = estabilidad(T, rho, ramas_T)
    if not (residuo_eos <= TOL_EOS and est.residuo <= TOL_ESTABILIDAD
            and p.dP_drho_T > 0 and (sat is None or sat.residuo <= TOL_SATURACION_MAXWELL)):
        raise FueraDeAlcance(
            "estabilidad_no_certificada",
            f"No se pudo certificar el estado: residuo EOS {residuo_eos:.3g}, "
            f"TPD {est.residuo:.3g}, (dP/drho)_T {p.dP_drho_T:.6g}"
            + (f", Maxwell {sat.residuo:.3g}" if sat else "") + ".")
    return EstadoAgua(tipo=tipo, regimen=regimen, propiedades=p, P=P, residuo_eos=residuo_eos,
                      estabilidad=est, saturacion=sat,
                      residuo_derivadas=_derivadas(T, P, rho, nombre, p))


def version_auditada():
    return chemicals.__version__ == VERSION_CHEMICALS_AUDITADA


# ----------------------------------------------------------------------
# Valores de verificacion publicados en IAPWS R6-95(2018)
# ----------------------------------------------------------------------
# Tabla 6: derivadas de phi0 y phir a T = 500 K, rho = 838.025 kg/m3.
_TABLA6 = {
    "phi0": 0.204797733e1, "phi0_t": 0.904611106e1, "phi0_tt": -0.193249185e1,
    "phir": -0.342693206e1, "phir_d": -0.364366650, "phir_dd": 0.856063701,
    "phir_t": -0.581403435e1, "phir_tt": -0.223440737e1, "phir_dt": -0.112176915e1,
}
# Tabla 7: (T K, rho kg/m3) -> P MPa, cv kJ/(kg K), w m/s, s kJ/(kg K)
_TABLA7 = [
    (300, 0.9965560e3, 0.992418352e-1, 0.413018112e1, 0.150151914e4, 0.393062643),
    (300, 0.1005308e4, 0.200022515e2, 0.406798347e1, 0.153492501e4, 0.387405401),
    (300, 0.1188202e4, 0.700004704e3, 0.346135580e1, 0.244357992e4, 0.132609616),
    (500, 0.4350e0, 0.999679423e-1, 0.150817541e1, 0.548314253e3, 0.794488271e1),
    (500, 0.4532e1, 0.999938125e0, 0.166991025e1, 0.535739001e3, 0.682502725e1),
    (500, 0.8380250e3, 0.100003858e2, 0.322106219e1, 0.127128441e4, 0.256690919e1),
    (500, 0.1084564e4, 0.700000405e3, 0.307437693e1, 0.241200877e4, 0.203237509e1),
    (647, 0.358e3, 0.220384756e2, 0.618315728e1, 0.252145078e3, 0.432092307e1),
    (900, 0.241e0, 0.100062559e0, 0.175890657e1, 0.724027147e3, 0.916653194e1),
    (900, 0.5261500e2, 0.200000690e2, 0.193510526e1, 0.698445674e3, 0.659070225e1),
    (900, 0.8707690e3, 0.700000006e3, 0.266422350e1, 0.201933608e4, 0.417223802e1),
]
# Tabla 8: T K -> Psat MPa, rho' rho'' kg/m3, h' h'' kJ/kg, s' s'' kJ/(kg K)
_TABLA8 = [
    (275, 0.698451167e-3, 0.999887406e3, 0.550664919e-2, 0.775972202e1, 0.250428995e4,
     0.283094670e-1, 0.910660121e1),
    (450, 0.932203564, 0.890341250e3, 0.481200360e1, 0.749161585e3, 0.277441078e4,
     0.210865845e1, 0.660921221e1),
    (625, 0.169082693e2, 0.567090385e3, 0.118290280e3, 0.168626976e4, 0.255071625e4,
     0.380194683e1, 0.518506121e1),
]


def verificar():
    """[(caso, calculado, publicado, error relativo)] contra las tablas 6,
    7 y 8 de IAPWS R6-95(2018). Los valores publicados tienen 9 cifras."""
    salida = []
    tau, d = TC / 500.0, 838.025 / RHOC
    calc6 = {
        "phi0": _w.iapws95_A0(tau, d), "phi0_t": _w.iapws95_dA0_dtau(tau, d),
        "phi0_tt": _w.iapws95_d2A0_dtau2(tau, d), "phir": _w.iapws95_Ar(tau, d),
        "phir_d": _w.iapws95_dAr_ddelta(tau, d), "phir_dd": _w.iapws95_d2Ar_ddelta2(tau, d),
        "phir_t": _w.iapws95_dAr_dtau(tau, d), "phir_tt": _w.iapws95_d2Ar_dtau2(tau, d),
        "phir_dt": _w.iapws95_d2Ar_ddeltadtau(tau, d),
    }
    for k, ref in _TABLA6.items():
        salida.append((f"tabla 6: {k}", calc6[k], ref, abs(calc6[k] - ref) / abs(ref)))
    for T, rho, P, cv, w, s in _TABLA7:
        p = propiedades(float(T), rho)
        for nombre, x, ref in (("P", p.P / 1e6, P), ("cv", p.cv / 1e3, cv),
                               ("w", p.w, w), ("s", p.s / 1e3, s)):
            salida.append((f"tabla 7: {nombre}({T} K, {rho} kg/m3)", x, ref, abs(x - ref) / abs(ref)))
    for T, Ps, rl, rv, hl, hv, sl, sv in _TABLA8:
        sat = saturacion(float(T))
        pl, pv = propiedades(float(T), sat.rho_l), propiedades(float(T), sat.rho_v)
        for nombre, x, ref in (("Psat", sat.Psat / 1e6, Ps), ("rho'", sat.rho_l, rl),
                               ("rho''", sat.rho_v, rv), ("h'", pl.h / 1e3, hl),
                               ("h''", pv.h / 1e3, hv), ("s'", pl.s / 1e3, sl),
                               ("s''", pv.s / 1e3, sv)):
            salida.append((f"tabla 8: {nombre}({T} K)", x, ref, abs(x - ref) / abs(ref)))
    return salida


# ======================================================================
# H3: coexistencia liquido-vapor y especificaciones PH, UP, UV
#
# Nada de lo anterior cambia: evaluar_TP, saturacion, ramas y estabilidad
# son las mismas funciones de H1 y los estados TP salen identicos. Lo que
# sigue las usa y anade la coexistencia resuelta y las inversiones.
# ======================================================================

# Coexistencia publicada solo hasta el borde inferior de la banda critica.
# Ahi Psat = 21.22 MPa (> 0.95 Pc) y h'' - h' sigue siendo ~ 500 kJ/kg; por
# encima las diferencias entre fases tienden a cero y la calidad queda mal
# condicionada: esos estados salen como region critica.
T_COEX_MAX = T_CRITICA[0]
TOL_INVERSION = 1e-10           # residuo de energia/volumen reconstruidos
PUNTOS_BARRIDO_UV = 300
# Conjunto activo: una fraccion de fase calculada por debajo de Q_MIN se
# trata como la frontera (fase ausente). Es la resolucion de la inversion,
# no un recorte fisico: con q exactamente 0 o 1 en la entrada, el error de
# Tsat(P) (hasta ~7e-13 K junto a T_COEX_MAX, limite de coma flotante de
# Psat) y el redondeo de y y v dejan q espurias de 1e-19 a 1.3e-13 (medido
# en tests/validar_motor_termodinamica_h3.py, el mayor a 643 K). Q_MIN deja
# un margen de ~8x. Se aplica a los dos lados de la meseta: q calculada en
# [-Q_MIN, Q_MIN] es la frontera q = 0 (y simetrico en 1), con la energia y
# el volumen reconstruidos publicados como residuos. Trazas desde 1e-11 se
# conservan y se reconstruyen.
Q_MIN = 1e-12
TOL_TM = 1e-9                   # -min tm de la coexistencia
RHO_MAX_UV = 1250.0             # ~rho(273.16 K, 1 GPa): mas denso no es agua fluida del dominio


@dataclass(frozen=True)
class EstabilidadCoexistencia:
    residuo: float          # max(0, -min tm)
    evaluaciones: int
    ramas: tuple


def estabilidad_coexistencia(T, c, ramas_T):
    """Estabilidad de la coexistencia de sustancia pura a T: la tangente
    comun por los dos puntos saturados debe quedar por debajo de la energia
    de Helmholtz por volumen en todas las densidades candidatas,

        tm(rho) = [rho (f(T, rho) - g*) + P*] / (rho R T) >= 0,
        g* = g'' , P* = P'' (las del vapor: la presion del liquido es
        rigida y solo se fija a ~rho'(dP/drho)*eps).

    tm es la distancia al plano tangente por unidad de masa de la fase de
    prueba y en unidades de R T (Delta g / R T), la escala adimensional
    habitual (Michelsen). Debe anularse en rho' y rho'' y no ser negativa en
    ninguna otra parte. Misma malla y refinamiento que `estabilidad`."""
    g_s, P_s = c.vapor.g, c.vapor.P

    def tm(r):
        return (r * (helmholtz(T, r) - g_s) + P_s) / (r * R * T)

    minimo, evaluaciones = 0.0, 0
    for _, lo, hi in ramas_T:
        n = PUNTOS_POR_RAMA
        malla = sorted(set([math.exp(math.log(lo) + i * (math.log(hi) - math.log(lo)) / n) for i in range(n + 1)]
                           + [r for r in (c.liquido.rho, c.vapor.rho) if lo <= r <= hi]))
        valores = [tm(r) for r in malla]
        evaluaciones += len(malla)
        for i, val in enumerate(valores):
            izq = valores[i - 1] if i > 0 else math.inf
            der = valores[i + 1] if i + 1 < len(valores) else math.inf
            if not (val <= izq and val <= der):
                continue
            a, b = malla[max(i - 1, 0)], malla[min(i + 1, len(malla) - 1)]
            v_min = val
            if b > a:
                res = minimize_scalar(tm, bounds=(a, b), method="bounded", options={"xatol": 1e-12 * b})
                evaluaciones += int(res.nfev)
                v_min = min(val, res.fun)
            minimo = min(minimo, v_min)
    return EstabilidadCoexistencia(residuo=max(0.0, -minimo), evaluaciones=evaluaciones, ramas=tuple(ramas_T))


@dataclass(frozen=True)
class Coexistencia:
    T: float
    P: float                # Psat = P del vapor (la bien condicionada)
    liquido: Propiedades
    vapor: Propiedades
    residuo: float          # residuo de Maxwell, ver _residuo_maxwell
    iteraciones: int


def _residuo_maxwell(T, pl, pv):
    """max(|g' - g''|/(R T), |P' - P''| / max(P'', rho' (dP/drho)_T'))

    La diferencia de presiones se escala con el modulo de compresibilidad
    del liquido: con densidades en coma flotante (error relativo ~1e-16)
    la presion del liquido no puede igualarse mejor que ~rho' (dP/drho)
    * 1e-16, que a 300 K son ~1e-7 Pa."""
    return max(abs(pl.g - pv.g) / (R * T),
               abs(pl.P - pv.P) / max(pv.P, pl.rho * pl.dP_drho_T))


@lru_cache(maxsize=20000)        # funcion pura de T: la cache no cambia resultados
def coexistencia(T):
    """Equilibrio liquido-vapor del agua pura a T en [T_TRIPLE, T_COEX_MAX].

    Resuelve P(T, rho') = P(T, rho'') y g(T, rho') = g(T, rho'') por Newton
    en (rho', rho''), con T comun por construccion. Jacobiano analitico:
    dP/drho = (dP/drho)_T y dg/drho = (dP/drho)_T / rho a T fija. Semilla:
    los ajustes de `chemicals` (rama liquida y rama vapor, nunca la region
    homogenea de la campana). Cada paso debe mantener rho' > rho_c > rho''.
    Se itera hasta que el residuo deja de bajar (limite de coma flotante) o
    30 iteraciones; si sale de su rama o el residuo final supera
    TOL_SATURACION_MAXWELL, FueraDeAlcance."""
    if not T_TRIPLE <= T <= T_COEX_MAX:
        raise FueraDeAlcance("region_critica" if T > T_COEX_MAX else "fuera_de_dominio",
                             f"Coexistencia publicada solo para T en [{T_TRIPLE}, {T_COEX_MAX:.6g}] K.")
    sat = saturacion(T)
    rl, rv = sat.rho_l, sat.rho_v
    pl, pv = propiedades(T, rl), propiedades(T, rv)
    residuo = _residuo_maxwell(T, pl, pv)
    it = 0
    while residuo > 0.0 and it < 30:
        it += 1
        a, b = pl.dP_drho_T, -pv.dP_drho_T
        c, d = pl.dP_drho_T / rl, -pv.dP_drho_T / rv
        F1, F2 = pl.P - pv.P, pl.g - pv.g
        det = a * d - b * c
        nl, nv = rl - (F1 * d - b * F2) / det, rv - (a * F2 - c * F1) / det
        if not nl > RHOC > nv > 0:
            raise FueraDeAlcance("no_convergente", f"El Newton de coexistencia salio de sus ramas a T = {T:.6g} K.")
        nuevo = (propiedades(T, nl), propiedades(T, nv))
        r_nuevo = _residuo_maxwell(T, *nuevo)
        if r_nuevo >= residuo:      # limite de coma flotante: no empeorar
            break
        rl, rv, (pl, pv), residuo = nl, nv, nuevo, r_nuevo
    if residuo > TOL_SATURACION_MAXWELL:
        raise FueraDeAlcance("no_convergente", f"Coexistencia sin converger a T = {T:.6g} K (residuo {residuo:.3g}).")
    return Coexistencia(T=T, P=pv.P, liquido=pl, vapor=pv, residuo=residuo, iteraciones=it)


def P_coexistencia_limites():
    return coexistencia(T_TRIPLE).P, coexistencia(T_COEX_MAX).P


def T_saturacion(P):
    """(Coexistencia a Tsat(P), |Psat(Tsat) - P|/P).

    Horquilla: brentq sobre el ajuste monotono Psat(T) en
    [T_TRIPLE, T_COEX_MAX]; despues Newton en T con la coexistencia
    resuelta y la pendiente de Clapeyron dPsat/dT = (s''-s')/(v''-v')."""
    P_min, P_max = P_coexistencia_limites()
    if not P_min <= P <= P_max:
        raise FueraDeAlcance("fuera_de_dominio", f"P = {P:.6g} Pa sin coexistencia publicada.")
    T = brentq(lambda t: _w.iapws95_Psat(t) - P, T_TRIPLE, T_COEX_MAX, xtol=1e-300, rtol=1e-15)
    T = min(max(T, T_TRIPLE), T_COEX_MAX)
    c = coexistencia(T)
    for _ in range(6):
        pendiente = (c.vapor.s - c.liquido.s) / (c.vapor.v - c.liquido.v)
        nuevo = min(max(T - (c.P - P) / pendiente, T_TRIPLE), T_COEX_MAX)
        if nuevo == T:
            break
        c_nuevo = coexistencia(nuevo)
        if abs(c_nuevo.P - P) >= abs(c.P - P):
            break
        T, c = nuevo, c_nuevo
    return c, abs(c.P - P) / P


# ----------------------------------------------------------------------
@dataclass(frozen=True)
class FaseCalculada:
    tipo: str
    regimen: str
    fraccion: float         # masica = molar (sustancia pura)
    propiedades: Propiedades


@dataclass(frozen=True)
class EstadoEquilibrio:
    especificacion: str             # 'PH' | 'UP' | 'UV'
    T: float
    P: float                        # la pedida (PH, UP) o la calculada (UV)
    fases: tuple
    u: float
    h: float
    v: float
    s: float
    cp: float | None                # solo fase unica fuera de la curva de saturacion
    cv: float | None
    coexistencia: Coexistencia | None   # bifasico o en la frontera q = 0, 1
    frontera: bool                  # una fase exactamente en la curva (q = 0 o 1)
    estabilidad: tuple              # Estabilidad por fase
    saturacion_rama: Saturacion | None
    residuos: dict                  # nombre -> residuo adimensional
    residuo_derivadas: float        # nan si no aplica
    unicidad: str                   # descripcion de la busqueda de raices


def _tipo_regimen(nombre, P):
    if nombre != "fluido":
        return nombre, "ordinario"
    return ("fluido", "supercritico") if P > PC else ("vapor", "ordinario")


def _densidad_rama(T, P, nombre):
    """rho en la rama `nombre` a T. Los extremos de las ramas salen de los
    ajustes de saturacion (error ~1e-12 relativo en rho'); junto a la curva
    se admite extender el extremo 1e-7 relativo hacia el lado metastable
    para no perder la raiz por ese error. La estabilidad del resultado se
    certifica despues con la TPD, asi que la extension no cuela estados
    metastables."""
    rs = [r for r in ramas(T)[0] if r[0] == nombre]
    if not rs:
        raise FueraDeAlcance("no_convergente", f"No hay rama {nombre} a T = {T:.6g} K.")
    _, lo, hi = rs[0]
    if nombre == "liquido" and presion(T, lo) > P:
        lo *= 1 - 1e-7
    if nombre == "vapor" and presion(T, hi) < P:
        hi *= 1 + 1e-7
    return densidad(T, P, lo, hi)


def _rama_isobara(T, P, lado):
    return "fluido" if T >= TC else lado


def _dominio(T, P, ruta=""):
    if not (T_MIN <= T <= T_MAX and P_MIN <= P <= P_MAX):
        raise FueraDeAlcance(
            "fuera_de_dominio",
            f"El estado que cumple la especificacion (T = {T:.6g} K, P = {P:.6g} Pa) cae fuera del dominio "
            f"verificado T en [{T_MIN}, {T_MAX}] K, P en [{P_MIN:.6g}, {P_MAX:.6g}] Pa.",
            T_fuera=not T_MIN <= T <= T_MAX, P_fuera=not P_MIN <= P <= P_MAX)
    if T_CRITICA[0] <= T <= T_CRITICA[1] and P_CRITICA[0] <= P <= P_CRITICA[1]:
        raise FueraDeAlcance(
            "region_critica",
            f"El estado que cumple la especificacion (T = {T:.6g} K, P = {P:.6g} Pa) esta en la banda "
            "critica excluida.")


def _monofasico(espec, T, rho, nombre, P_espec, residuos, unicidad, certificar=True):
    """Certifica un estado de una fase en (T, rho) como en H1 (TPD sobre las
    ramas a T) y lo empaqueta. certificar=False omite la TPD y el contraste
    de derivadas (evaluaciones internas del integrador, ver
    core/ensamblaje_dinamico.py); el dominio se comprueba siempre."""
    p = propiedades(T, rho)
    P = P_espec if P_espec is not None else p.P
    _dominio(T, P)
    if not certificar:
        tipo, regimen = _tipo_regimen(nombre, P)
        return EstadoEquilibrio(
            especificacion=espec, T=T, P=P, fases=(FaseCalculada(tipo, regimen, 1.0, p),),
            u=p.u, h=p.h, v=p.v, s=p.s, cp=p.cp, cv=p.cv, coexistencia=None, frontera=False,
            estabilidad=(), saturacion_rama=None, residuos=dict(residuos),
            residuo_derivadas=float("nan"), unicidad=unicidad)
    ramas_T, sat = ramas(T)
    est = estabilidad(T, rho, ramas_T)
    if not (est.residuo <= TOL_ESTABILIDAD and p.dP_drho_T > 0
            and (sat is None or sat.residuo <= TOL_SATURACION_MAXWELL)):
        raise FueraDeAlcance(
            "estabilidad_no_certificada",
            f"El estado de una fase a T = {T:.6g} K, rho = {rho:.9g} kg/m3 no es estable (TPD {est.residuo:.3g}).")
    tipo, regimen = _tipo_regimen(nombre, P)
    residuos = dict(residuos)
    if P_espec is not None:
        residuos["ecuacion_estado"] = abs(p.P - P_espec) / max(P_espec, rho * p.dP_drho_T)
    return EstadoEquilibrio(
        especificacion=espec, T=T, P=P, fases=(FaseCalculada(tipo, regimen, 1.0, p),),
        u=p.u, h=p.h, v=p.v, s=p.s, cp=p.cp, cv=p.cv, coexistencia=None, frontera=False,
        estabilidad=(est,), saturacion_rama=sat, residuos=residuos,
        residuo_derivadas=_derivadas(T, P, rho, nombre, p), unicidad=unicidad)


def _bifasico(espec, c, q, P_espec, objetivo, unicidad, certificar=True):
    """Coexistencia a c.T con fraccion masica de vapor q en [0, 1]. Con q
    exactamente 0 o 1 se publica solo la fase presente (en la frontera). Los
    residuos de `objetivo` (nombre -> (calculado, pedido, escala)) se
    evaluan sobre la mezcla reconstruida."""
    _dominio(c.T, c.P)
    if q < Q_MIN:
        q = 0.0
    elif q > 1.0 - Q_MIN:
        q = 1.0
    fases = [FaseCalculada(tipo, "ordinario", frac, p)
             for tipo, frac, p in (("liquido", 1.0 - q, c.liquido), ("vapor", q, c.vapor)) if frac > 0.0]
    ests = []
    if certificar:
        ramas_T, _ = ramas(c.T)
        est = estabilidad_coexistencia(c.T, c, ramas_T)
        if est.residuo > TOL_TM:
            raise FueraDeAlcance("estabilidad_no_certificada",
                                 f"La coexistencia a T = {c.T:.6g} K no es estable (tm {est.residuo:.3g}).")
        ests = [est]
    mezcla = {k: sum(f.fraccion * getattr(f.propiedades, k) for f in fases) for k in ("u", "h", "v", "s")}
    if len(fases) == 1:     # en la frontera: las propiedades son las de esa fase, sin redondeo
        mezcla = {k: getattr(fases[0].propiedades, k) for k in ("u", "h", "v", "s")}
    residuos = {"equilibrio": c.residuo}
    if P_espec is not None:
        residuos["presion_saturacion"] = abs(c.P - P_espec) / P_espec
    for nombre, (calc, pedido, escala) in objetivo(mezcla).items():
        residuos[nombre] = abs(calc - pedido) / escala
    return EstadoEquilibrio(
        especificacion=espec, T=c.T, P=P_espec if P_espec is not None else c.P, fases=tuple(fases),
        u=mezcla["u"], h=mezcla["h"], v=mezcla["v"], s=mezcla["s"], cp=None, cv=None,
        coexistencia=c, frontera=len(fases) == 1, estabilidad=tuple(ests), saturacion_rama=None,
        residuos=residuos, residuo_derivadas=float("nan"), unicidad=unicidad)


def _resolver_T_isobara(P, y_nombre, y, T_lo, T_hi, lado, y_lo=None, y_hi=None, T_semilla=None):
    """T en [T_lo, T_hi] con y(T, P) = y en la rama `lado` (o 'fluido' por
    encima de T_c). y(T) es estrictamente creciente a P fija: (dh/dT)_P = cp
    > 0 y (du/dT)_P = cp - P (dv/dT)_P >= 0.75 cp en todo el dominio (malla
    de 400 x 11 en tests/validar_motor_termodinamica_h3.py), asi que la raiz
    es unica si existe. y_lo / y_hi sustituyen el valor en un extremo que
    esta sobre la curva de saturacion."""
    def f(T):
        if T == T_lo and y_lo is not None:
            return y_lo - y
        if T == T_hi and y_hi is not None:
            return y_hi - y
        rho = _densidad_rama(T, P, _rama_isobara(T, P, lado))
        return getattr(propiedades(T, rho), y_nombre) - y
    if T_semilla is not None and T_lo < T_semilla < T_hi:
        # horquilla local alrededor de la semilla (solo acelera: la raiz es unica)
        paso = max(0.05, 1e-3 * T_semilla)
        a = b = T_semilla
        fa = fb = f(T_semilla)
        for _ in range(40):
            if fa <= 0 <= fb:
                if fa == 0:
                    return a
                if fb == 0:
                    return b
                return brentq(f, a, b, xtol=1e-300, rtol=1e-15, maxiter=500)
            if fa > 0:
                b, fb, a = a, fa, max(T_lo, a - paso)
                fa = f(a)
                if a == T_lo and fa > 0:
                    break
            else:
                a, fa, b = b, fb, min(T_hi, b + paso)
                fb = f(b)
                if b == T_hi and fb < 0:
                    break
            paso *= 2.0
    f_lo, f_hi = f(T_lo), f(T_hi)
    if f_lo > 0 or f_hi < 0:
        raise FueraDeAlcance(
            "fuera_de_dominio",
            f"Ningun estado con {y_nombre} = {y:.9g} J/kg a P = {P:.6g} Pa tiene T en "
            f"[{T_lo:.6g}, {T_hi:.6g}] K; el que cumple la especificacion queda fuera del dominio verificado.",
            T_fuera=True)
    if f_lo == 0:
        return T_lo
    if f_hi == 0:
        return T_hi
    return brentq(f, T_lo, T_hi, xtol=1e-300, rtol=1e-15, maxiter=500)


def _evaluar_isobara(espec, P, y_nombre, y, certificar=True, T_semilla=None):
    """PH (y = h) o UP (y = u = U/m) a P prescrita.

    Criterio: el estado de equilibrio es el estable en G a su propia (T, P)
    cuya propiedad y coincide con la pedida. A lo largo de la isobara de
    equilibrio y(T) es creciente: monofasica por debajo de Tsat, meseta
    lineal en q a Tsat (y' <= y <= y''), monofasica por encima. Por eso hay
    a lo sumo un estado: primero se ubica y respecto de la meseta y solo
    despues se resuelve T en la rama que corresponde."""
    if not P_MIN <= P <= P_MAX:
        raise FueraDeAlcance("fuera_de_dominio", f"P = {P:.6g} Pa fuera del dominio verificado.", P_fuera=True)
    P_min_coex, P_max_coex = P_coexistencia_limites()

    def objetivo(m):
        return {"energia": (m[y_nombre], y, R * T_ref[0])}
    T_ref = [None]
    unicidad = (f"{y_nombre}(T) creciente a P fija ((∂{y_nombre}/∂T)_P > 0 en la rama y meseta lineal en q a "
                "Tsat): a lo sumo un estado; se ubica primero respecto de la meseta y luego se resuelve T por "
                "Brent en una horquilla con cambio de signo.")

    def mono(T, lado):
        rho = _densidad_rama(T, P, _rama_isobara(T, P, lado))
        p = propiedades(T, rho)
        return _monofasico(espec, T, rho, _rama_isobara(T, P, lado), P,
                           {"energia": abs(getattr(p, y_nombre) - y) / (R * T)}, unicidad, certificar)

    if P_min_coex <= P <= P_max_coex:
        c, res_T = T_saturacion(P)
        T_ref[0] = c.T
        yl, yv = getattr(c.liquido, y_nombre), getattr(c.vapor, y_nombre)
        q = (y - yl) / (yv - yl)
        if -Q_MIN <= q <= 1.0 + Q_MIN:      # conjunto activo simetrico, ver Q_MIN
            e = _bifasico(espec, c, min(max(q, 0.0), 1.0), P, objetivo, unicidad, certificar)
            e.residuos["presion_saturacion"] = res_T
            return e
        if y < yl:
            return mono(_resolver_T_isobara(P, y_nombre, y, T_MIN, c.T, "liquido", y_hi=yl, T_semilla=T_semilla), "liquido")
        return mono(_resolver_T_isobara(P, y_nombre, y, c.T, T_MAX, "vapor", y_lo=yv, T_semilla=T_semilla), "vapor")
    if P < P_min_coex:      # por debajo del punto triple: solo vapor con T >= T_TRIPLE
        return mono(_resolver_T_isobara(P, y_nombre, y, T_MIN, T_MAX, "vapor", T_semilla=T_semilla), "vapor")
    # P > Psat(T_COEX_MAX): sin coexistencia publicada
    lado = "liquido"
    if P_CRITICA[0] <= P <= P_CRITICA[1]:
        y_c0 = getattr(propiedades(T_CRITICA[0], _densidad_rama(T_CRITICA[0], P, "liquido")), y_nombre)
        y_c1 = getattr(propiedades(T_CRITICA[1], _densidad_rama(T_CRITICA[1], P, "fluido")), y_nombre)
        if y <= y_c0:
            return mono(_resolver_T_isobara(P, y_nombre, y, T_MIN, T_CRITICA[0], lado, T_semilla=T_semilla), lado)
        if y >= y_c1:
            return mono(_resolver_T_isobara(P, y_nombre, y, T_CRITICA[1], T_MAX, lado, T_semilla=T_semilla), lado)
        raise FueraDeAlcance(
            "region_critica",
            f"A P = {P:.6g} Pa, {y_nombre} = {y:.9g} J/kg corresponde a un estado de la banda critica "
            f"(T en [{T_CRITICA[0]:.6g}, {T_CRITICA[1]:.6g}] K), excluida.")
    return mono(_resolver_T_isobara(P, y_nombre, y, T_MIN, T_MAX, lado, T_semilla=T_semilla), lado)


def evaluar_PH(P, h, certificar=True, T_semilla=None):
    """Agua pura a (P [Pa], h [J/kg]). T_semilla solo acelera la busqueda."""
    return _evaluar_isobara("PH", P, "h", h, certificar, T_semilla)


def evaluar_UP(P, u, certificar=True):
    """Agua pura a (P [Pa], u = U/m [J/kg])."""
    return _evaluar_isobara("UP", P, "u", u, certificar)


def _u_candidato_UV(T, v):
    """u del candidato de equilibrio a (T, v): mezcla de coexistencia si v
    cae entre v' y v'' a esa T; si no, el estado homogeneo rho = 1/v (que
    entonces esta en una rama monofasica). Continua en T: en el borde de la
    campana las dos expresiones coinciden. Para T en (T_COEX_MAX, T_c) la
    campana se toma de los ajustes: solo sirve para clasificar, y cualquier
    raiz ahi es region critica."""
    if T < TC:
        if T <= T_COEX_MAX:
            c = coexistencia(T)
            pl, pv = c.liquido, c.vapor
        else:
            sat = saturacion(T)
            pl, pv = propiedades(T, sat.rho_l), propiedades(T, sat.rho_v)
        if pl.v < v < pv.v:
            q = (v - pl.v) / (pv.v - pl.v)
            return pl.u + q * (pv.u - pl.u)
    if T == TC and 1.0 / v == RHOC:     # singularidad delta = tau = 1 de phir
        T = TC * (1 + 1e-12)
    return propiedades(T, 1.0 / v).u


def evaluar_UV(u, v, T_semilla=None, certificar=True):
    """Agua pura a (u = U/m [J/kg], v = V/m [m3/kg]).

    Criterio: maximo de S a U, V, n fijos. Para una sustancia pura un estado
    homogeneo lo cumple si y solo si esta en la envolvente concava de
    s(u, v), lo que equivale a ser estable en G a su propia (T, P) (TPD >= 0
    a esa T); la mezcla de las dos fases saturadas es la envolvente dentro
    de la campana. Candidatos: todas las raices en T de u_candidato(T; v) =
    u, buscadas con una malla de PUNTOS_BARRIDO_UV temperaturas en
    [T_MIN, T_MAX] y Brent en cada cambio de signo (no la primera raiz).
    Cada candidato se certifica; si quedan varios admisibles se elige el de
    mayor s y, si sus s no se distinguen, se declara ambiguo.

    T_semilla (solo evaluaciones internas del integrador): se busca primero
    una horquilla con cambio de signo alrededor de la semilla, ampliandola
    geometricamente. La semilla no fija propiedades: u_candidato(T; v) es
    creciente en T (cv de equilibrio > 0), asi que la raiz de una horquilla
    es la unica; las muestras publicadas usan el barrido global. Si no hay
    horquilla, se hace el barrido global."""
    if not (0 < v and 1.0 / v <= RHO_MAX_UV):
        raise FueraDeAlcance(
            "fuera_de_dominio",
            f"v = {v:.6g} m3/kg (rho = {1 / v:.6g} kg/m3) es mas denso que el agua fluida del dominio "
            f"(rho <= {RHO_MAX_UV} kg/m3, del orden de rho(273.16 K, 1 GPa)); la presion superaria el dominio.",
            P_fuera=True)
    raices_locales = _raiz_local_UV(u, v, T_semilla) if T_semilla is not None else None
    if raices_locales is not None:
        T_malla, g = [T_MIN, T_MAX], [-1.0, 1.0]
    else:
        T_malla = sorted(set([T_MIN + i * (T_MAX - T_MIN) / PUNTOS_BARRIDO_UV
                              for i in range(PUNTOS_BARRIDO_UV + 1)] + [T_COEX_MAX]))
        g = [_u_candidato_UV(T, v) - u for T in T_malla]
    if g[0] > 0:
        raise FueraDeAlcance(
            "fuera_de_dominio",
            f"u = {u:.9g} J/kg con v = {v:.9g} m3/kg exige T < {T_MIN} K: posible hielo, fuera del dominio.",
            T_fuera=True)
    if g[-1] < 0:
        raise FueraDeAlcance("fuera_de_dominio",
                             f"u = {u:.9g} J/kg con v = {v:.9g} m3/kg exige T > {T_MAX} K.", T_fuera=True)
    raices = [] if raices_locales is None else raices_locales
    for i in range(len(T_malla) - 1 if raices_locales is None else 0):
        if g[i] == 0:
            raices.append(T_malla[i])
        elif g[i] < 0 < g[i + 1]:
            raices.append(brentq(lambda T: _u_candidato_UV(T, v) - u, T_malla[i], T_malla[i + 1],
                                 xtol=1e-300, rtol=1e-15, maxiter=500))
        elif g[i] > 0 > g[i + 1]:
            raices.append(brentq(lambda T: _u_candidato_UV(T, v) - u, T_malla[i], T_malla[i + 1],
                                 xtol=1e-300, rtol=1e-15, maxiter=500))
    if g[-1] == 0 and raices_locales is None:
        raices.append(T_malla[-1])
    unicidad = ("Raíz local en una horquilla alrededor de la semilla (evaluación interna, sin barrido)."
                if raices_locales is not None else None) or (f"Barrido de u_candidato(T; v) en {len(T_malla)} temperaturas de [{T_MIN}, {T_MAX}] K y Brent en "
                f"cada cambio de signo: {len(raices)} raíz(ces).")

    def objetivo(m):
        return {"energia": (m["u"], u, R * T_ref[0]), "volumen": (m["v"], v, v)}
    T_ref = [None]
    candidatos, rechazos = [], []
    for T in raices:
        T_ref[0] = T
        try:
            if T <= T_COEX_MAX:
                c = coexistencia(T)
                q = (v - c.liquido.v) / (c.vapor.v - c.liquido.v)
                if -Q_MIN <= q <= 1.0 + Q_MIN:      # conjunto activo simetrico, ver Q_MIN
                    candidatos.append(_bifasico("UV", c, min(max(q, 0.0), 1.0), None, objetivo, unicidad,
                                                certificar))
                    continue
            elif T < TC:
                sat = saturacion(T)
                if 1 / sat.rho_l < v < 1 / sat.rho_v:
                    raise FueraDeAlcance("region_critica",
                                         f"Coexistencia a T = {T:.6g} K, en la banda critica excluida.")
            # Fuera de la campana la rama la decide el lado de rho_c (no los
            # ajustes de rho', que junto a la frontera difieren ~1e-13).
            rho = 1.0 / v
            nombre = "fluido" if T >= TC else ("liquido" if rho > RHOC else "vapor")
            p = propiedades(T, rho)
            candidatos.append(_monofasico(
                "UV", T, rho, nombre, None,
                {"energia": abs(p.u - u) / (R * T), "volumen": abs(p.v - v) / v}, unicidad, certificar))
        except FueraDeAlcance as x:
            rechazos.append(x)
    if not candidatos:
        if rechazos:
            raise rechazos[0]
        raise FueraDeAlcance("no_convergente", "Ninguna raiz de u(T; v) = u.")
    if len(candidatos) > 1:
        candidatos.sort(key=lambda e: -e.s)
        if candidatos[0].s - candidatos[1].s <= 1e-9 * max(1.0, abs(candidatos[0].s)):
            raise FueraDeAlcance("ambiguo", f"{len(candidatos)} estados admisibles con la misma entropia.")
        mejor = candidatos[0]
        return EstadoEquilibrio(**{**mejor.__dict__, "unicidad": unicidad + (
            f" {len(candidatos)} admisibles; se elige el de mayor s (máximo de S a U, V, n).")})
    return candidatos[0]


def _raiz_local_UV(u, v, T_semilla):
    """[T] con u_candidato(T; v) = u en una horquilla alrededor de T_semilla,
    o None si no se encuentra (entonces se usa el barrido global)."""
    T0 = min(max(T_semilla, T_MIN), T_MAX)
    try:
        g0 = _u_candidato_UV(T0, v) - u
        if g0 == 0:
            return [T0]
        paso = max(0.05, 1e-3 * T0)
        for _ in range(40):
            T1 = min(max(T0 - paso if g0 > 0 else T0 + paso, T_MIN), T_MAX)
            g1 = _u_candidato_UV(T1, v) - u
            if g1 == 0:
                return [T1]
            if (g0 < 0) != (g1 < 0):
                a, b = sorted((T0, T1))
                return [brentq(lambda T: _u_candidato_UV(T, v) - u, a, b, xtol=1e-300, rtol=1e-15, maxiter=500)]
            if T1 in (T_MIN, T_MAX):
                return None
            T0, g0, paso = T1, g1, paso * 2.0
    except (FueraDeAlcance, ValueError, ZeroDivisionError, OverflowError):
        return None
    return None


def evaluar_TV(T, v):
    """Agua pura a (T [K], v = V/m [m3/kg]): inicializacion de un volumen
    rigido con T(0). No se publica en la API puntual.

    Criterio: minimo de A a (T, V, n). Para una sustancia pura, a T fija el
    estado homogeneo lo cumple si y solo si es estable en G a su propia P
    (la TPD a T es la misma prueba de envolvente convexa de a(rho)); dentro
    de la campana el minimo es la mezcla de las dos fases saturadas con la
    regla de la palanca en v. No hay busqueda de raices en T: T es dato."""
    if not T_MIN <= T <= T_MAX:
        raise FueraDeAlcance("fuera_de_dominio", f"T = {T:.6g} K fuera del dominio verificado.", T_fuera=True)
    if not (0 < v and 1.0 / v <= RHO_MAX_UV):
        raise FueraDeAlcance("fuera_de_dominio", f"v = {v:.6g} m3/kg mas denso que el dominio.", P_fuera=True)
    unicidad = "T dada: la palanca en v (dentro de la campana) o la densidad 1/v (fuera) fijan el estado sin raíces."
    if T <= T_COEX_MAX:
        c = coexistencia(T)
        q = (v - c.liquido.v) / (c.vapor.v - c.liquido.v)
        if -Q_MIN <= q <= 1.0 + Q_MIN:
            def objetivo(m):
                return {"volumen": (m["v"], v, v)}
            return _bifasico("TV", c, min(max(q, 0.0), 1.0), None, objetivo, unicidad)
    elif T < TC:
        sat = saturacion(T)
        if 1 / sat.rho_l < v < 1 / sat.rho_v:
            raise FueraDeAlcance("region_critica", f"Coexistencia a T = {T:.6g} K, en la banda critica excluida.")
    rho = 1.0 / v
    nombre = "fluido" if T >= TC else ("liquido" if rho > RHOC else "vapor")
    return _monofasico("TV", T, rho, nombre, None, {"volumen": 0.0}, unicidad)
