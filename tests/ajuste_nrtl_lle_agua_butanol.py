"""
Ajuste reproducible de parametros NRTL de equilibrio liquido-liquido
agua (1) / 1-butanol (2) a los valores RECOMENDADOS (R) de la evaluacion
critica IUPAC-NIST Solubility Data Series vol. 15, "Alcohols with Water"
(G. T. Hefter, evaluador, 1982; A. F. M. Barton ed., Pergamon 1984),
seccion 1-butanol + agua, solubilidad mutua en g/100 g de disolucion:

  1-butanol en agua (fase acuosa) y agua en 1-butanol (fase organica)

Modelo: tau_ij = a_ij + b_ij / T, G_ij = exp(-alpha tau_ij).
Criterio: las composiciones de las dos fases que PREDICE el modelo
(resolviendo la isoactividad binaria x_i gamma_i iguales en ambas fases)
frente a las medidas, en fraccion masica; minimos cuadrados.

Temperaturas de AJUSTE: 293, 313, 333, 353, 373 K. Temperaturas de
VALIDACION (no usadas en el ajuste): 298, 323, 343, 363 K. El resultado se
copia a core/mezclas.py (NRTL_LLE_AGUA_BUTANOL) con esta procedencia; la
prueba tests/validar_motor_ensamblaje_v2.py vuelve a comparar el flash TP
completo del paquete (con su prueba de estabilidad) con las tablas.

Ejecutar desde la raiz del proyecto:
    python tests/ajuste_nrtl_lle_agua_butanol.py
"""

import math

import numpy as np
from scipy.optimize import fsolve, least_squares

M_AGUA, M_BUOH = 18.01528e-3, 74.1216e-3
# T [K] -> (g butanol / 100 g en fase acuosa, g agua / 100 g en fase organica), valores (R) de SDS-15
DATOS = {
    293: (7.8, 20.0), 298: (7.4, 20.3), 313: (6.6, 21.4), 323: (6.4, 22.4), 333: (6.5, 23.7),
    343: (6.7, 25.2), 353: (7.0, 27.5), 363: (7.7, 30.3), 373: (9.1, 33.8),
}
AJUSTE = (293, 313, 333, 353, 373)
VALIDACION = (298, 323, 343, 363)


def x_agua_de_masa(w_agua):
    na, nb = w_agua / M_AGUA, (1 - w_agua) / M_BUOH
    return na / (na + nb)


def w_agua_de_x(x_agua):
    ma, mb = x_agua * M_AGUA, (1 - x_agua) * M_BUOH
    return ma / (ma + mb)


def fases(T):
    w_bu_aq, w_ag_org = DATOS[T]
    return x_agua_de_masa(1 - w_bu_aq / 100), x_agua_de_masa(w_ag_org / 100)


def lngamma(p, T, x1):
    a12, b12, a21, b21, al = p
    x2 = 1 - x1
    t12, t21 = a12 + b12 / T, a21 + b21 / T
    G12, G21 = math.exp(-al * t12), math.exp(-al * t21)
    l1 = x2 ** 2 * (t21 * (G21 / (x1 + x2 * G21)) ** 2 + t12 * G12 / (x2 + x1 * G12) ** 2)
    l2 = x1 ** 2 * (t12 * (G12 / (x2 + x1 * G12)) ** 2 + t21 * G21 / (x1 + x2 * G21) ** 2)
    return l1, l2


def lle(p, T, sem):
    """(x_agua acuosa, x_agua organica) del modelo por isoactividad, desde la semilla."""
    def lnsig(z):          # ln(1/(1+e^-z)) estable
        return -math.log1p(math.exp(-z)) if z > -30 else z

    def F(z):
        z = [min(max(v, -60.0), 60.0) for v in z]
        xa, xo = 1 / (1 + math.exp(-z[0])), 1 / (1 + math.exp(-z[1]))
        ga, go = lngamma(p, T, xa), lngamma(p, T, xo)
        return [lnsig(z[0]) + ga[0] - lnsig(z[1]) - go[0],
                lnsig(-z[0]) + ga[1] - lnsig(-z[1]) - go[1]]
    z0 = [math.log(sem[0] / (1 - sem[0])), math.log(sem[1] / (1 - sem[1]))]
    # minimos cuadrados acotados en logit desde varias semillas (fsolve fallaba en soluciones existentes)
    for semilla in (z0, [z0[0] + 0.5, z0[1] - 0.5], [z0[0] - 0.5, z0[1] + 0.5], [6.0, 0.0]):
        try:
            r = least_squares(F, semilla, bounds=([-40, -40], [40, 40]), xtol=1e-15, ftol=1e-15, gtol=1e-15)
        except (ValueError, OverflowError, ZeroDivisionError):
            continue
        xa, xo = 1 / (1 + math.exp(-r.x[0])), 1 / (1 + math.exp(-r.x[1]))
        if np.max(np.abs(r.fun)) < 1e-10 and abs(xa - xo) > 1e-3:
            return xa, xo
    return None


def residuos(p, temps):
    r = []
    for T in temps:
        xa, xo = fases(T)
        res = lle(p, T, (xa, xo))
        if res is None:
            r.extend([50.0, 50.0])      # sin separacion liquida: penalizacion fuerte (no plana)
            continue
        r.extend([100 * (w_agua_de_x(res[0]) - w_agua_de_x(xa)), 100 * (w_agua_de_x(res[1]) - w_agua_de_x(xo))])
    return np.array(r)


def ajustar():
    mejor = None
    for p0 in ([3.0275309203536738, 181.97602868831027, 11.653322383367405, -3221.2034578438675, 0.43959571434650646],
               [0.75, 1087.0, 2.66, -914.0, 0.3]):
        r = least_squares(residuos, p0, args=(AJUSTE,), bounds=([-30, -2e4, -30, -2e4, 0.1], [30, 2e4, 30, 2e4, 0.6]),
                          x_scale=[1.0, 300.0, 1.0, 300.0, 0.05], diff_step=1e-6, xtol=1e-14, ftol=1e-14,
                          max_nfev=20000)
        if mejor is None or r.cost < mejor.cost:
            mejor = r
    return mejor.x


if __name__ == "__main__":
    p = ajustar()
    print("parametros (a12, b12, a21, b21, alpha):", [repr(float(v)) for v in p])
    print("ajuste: max |dw| (g/100g) =", float(np.max(np.abs(residuos(p, AJUSTE)))))
    print("validacion (no ajustadas): max |dw| (g/100g) =", float(np.max(np.abs(residuos(p, VALIDACION)))))
