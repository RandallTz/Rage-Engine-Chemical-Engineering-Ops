"""
Saturacion del agua por IAPWS-IF97 (regiones 1, 2 y 4), para el lado de vapor
de una camara de condensacion cuasiestacionaria.

Fuente: IAPWS R7-97(2012), "Revised Release on the IAPWS Industrial
Formulation 1997 for the Thermodynamic Properties of Water and Steam". Las
ecuaciones las implementa `chemicals.iapws`; aqui solo se combinan:

    T_sat(P), P_sat(T)    region 4 (ecuacion de saturacion explicita)
    h'(P)  = h_1(T_sat, P)  region 1 (liquido) en la saturacion
    h''(P) = h_2(T_sat, P)  region 2 (vapor) en la saturacion

con h = R T tau dgamma/dtau. Referencia IF97: u = s = 0 del liquido saturado
en el punto triple. Las dos entalpias del lado de vapor usan la MISMA
referencia; el calor latente h'' - h' no depende de ella.

Dominio: 611.213 Pa <= P <= P_sat(623.15 K) = 16.529 MPa. Por encima, la
saturacion pasa por la region 3 (no implementada aqui).

La comprobacion contra los valores de verificacion de IF97 (tablas 5, 15, 35
y 36) esta en `verificar()`, y la ejecutan las pruebas.
"""

import chemicals.iapws as _w

R = _w.iapws97_R                 # J/(kg K), el de IF97
M = 18.015268e-3                 # kg/mol (IAPWS)
P_MIN = 611.213                  # Pa, punto triple (IF97)
T_LIMITE_R1_R2 = 623.15          # K: frontera con la region 3
P_MAX = _w.Psat_IAPWS(T_LIMITE_R1_R2)
FORMULACION = "IAPWS-IF97 (R7-97(2012)), regiones 1, 2 y 4, via chemicals.iapws"


def T_sat(P):
    return float(_w.Tsat_IAPWS(P))


def P_sat(T):
    return float(_w.Psat_IAPWS(T))


def _h1(T, P):
    tau, pi = 1386.0 / T, P / 16.53e6
    return R * T * tau * _w.iapws97_dG_dtau_region1(tau, pi)


def _h2(T, P):
    tau, pi = 540.0 / T, P / 1e6
    return R * T * tau * (_w.iapws97_dG0_dtau_region2(tau, pi)
                          + _w.iapws97_dGr_dtau_region2(tau, pi))


def saturacion(P):
    """(T_sat [K], h' [J/mol], h'' [J/mol]) a la presion P [Pa]."""
    if not P_MIN <= P <= P_MAX:
        raise ValueError(f"P = {P:.6g} Pa fuera del dominio [{P_MIN:.6g}, "
                         f"{P_MAX:.6g}] Pa de las regiones 1, 2 y 4 de IF97")
    T = T_sat(P)
    return T, _h1(T, P) * M, _h2(T, P) * M


# Valores de verificacion publicados en IF97 (kJ/kg, MPa, K).
_VERIFICACION = [
    ("tabla 5: h1(300 K, 3 MPa)", lambda: _h1(300.0, 3e6) / 1e3, 0.115331273e3),
    ("tabla 5: h1(300 K, 80 MPa)", lambda: _h1(300.0, 80e6) / 1e3, 0.184142828e3),
    ("tabla 5: h1(500 K, 3 MPa)", lambda: _h1(500.0, 3e6) / 1e3, 0.975542239e3),
    ("tabla 15: h2(300 K, 0.0035 MPa)", lambda: _h2(300.0, 3.5e3) / 1e3, 0.254991145e4),
    ("tabla 15: h2(700 K, 0.0035 MPa)", lambda: _h2(700.0, 3.5e3) / 1e3, 0.333568375e4),
    ("tabla 15: h2(700 K, 30 MPa)", lambda: _h2(700.0, 30e6) / 1e3, 0.263149474e4),
    ("tabla 35: P_sat(300 K)", lambda: P_sat(300.0) / 1e6, 0.353658941e-2),
    ("tabla 35: P_sat(500 K)", lambda: P_sat(500.0) / 1e6, 0.263889776e1),
    ("tabla 35: P_sat(600 K)", lambda: P_sat(600.0) / 1e6, 0.123443146e2),
    ("tabla 36: T_sat(0.1 MPa)", lambda: T_sat(0.1e6), 0.372755919e3),
    ("tabla 36: T_sat(1 MPa)", lambda: T_sat(1e6), 0.453035632e3),
    ("tabla 36: T_sat(10 MPa)", lambda: T_sat(10e6), 0.584149488e3),
]


def verificar():
    """[(caso, calculado, publicado, error relativo)] contra las tablas de IF97."""
    salida = []
    for nombre, f, ref in _VERIFICACION:
        x = float(f())
        salida.append((nombre, x, ref, abs(x - ref) / abs(ref)))
    return salida
