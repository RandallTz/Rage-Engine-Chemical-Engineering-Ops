"""
Datos de componente puro para los paquetes de mezcla del motor (M1, M2, M4).

Cada especie se describe por UNA funcion de Gibbs molar por fase, de la que
salen h, s, v y mu por derivacion; no se mezclan h, Cp, densidad y Psat de
fuentes independientes sin esa construccion.

    Gas ideal (referencia de energia y entropia de TODOS los paquetes de
    mezcla: h = 0 y s = 0 del gas ideal puro a T0 = 298.15 K, P0 = 1e5 Pa):
        h_ig(T)    = int_T0^T cp_ig dT
        s_ig(T,P)  = int_T0^T cp_ig/T dT - R ln(P/P0)
        g_ig(T,P)  = h_ig - T s_ig(T,P0) + R T ln(P/P0)

    Liquido puro, definido para que coexista con su gas ideal en Psat(T) y sea
    incompresible de volumen molar v_L constante:
        g_L(T,P)   = g_ig(T,P0) + R T ln(Psat/P0) + v_L (P - Psat)
        s_L        = -dg_L/dT = s_ig(T,P0) - R ln(Psat/P0) - R T Psat'/Psat + v_L Psat'
        h_L        = g_L + T s_L = h_ig - R T^2 Psat'/Psat + v_L (P - Psat) + T v_L Psat'

    de modo que h_ig - h_L en Psat es T (R T/Psat - v_L) Psat': la ecuacion de
    Clapeyron con vapor ideal. El calor de vaporizacion no es un dato aparte.

Limitaciones declaradas: vapor ideal (la capacidad publica P <= 5e5 Pa),
liquido incompresible con v_L de 298.15 K, Psat solo dentro del rango de su
correlacion y por debajo de 0.9 T_c.

Fuentes (todas incluidas en `chemicals`/`thermo`, version auditada en
core/agua_iapws95.VERSION_CHEMICALS_AUDITADA):
  Psat  Wagner (Poling, The Properties of Gases and Liquids 5a ed., tabla A)
        o Wagner (McGarry, Ind. Eng. Chem. Process Des. Dev. 22 (1983) 313)
  cp_ig polinomio de Poling 5a ed., apendice A (50-1000 K)
  v_L   thermo VolumeLiquid a 298.15 K (metodo indicado por especie)
  M     masas molares de thermo (IUPAC)
"""

import math
from dataclasses import dataclass
from functools import lru_cache

import chemicals.heat_capacity as _hc
import chemicals.vapor_pressure as _vp

R = 8.314462618         # J/(mol K), CODATA 2018
T0 = 298.15
P0 = 1e5

# Identidad y procedencia de cada especie: registro unico en core/catalogo.py (F2.1). Aqui solo la vista
# CAS -> (nombre, tabla de Psat, v_L [m3/mol] a 298.15 K, metodo de v_L, M [kg/mol]) que usa _especie().
from core import catalogo as _catalogo

_ESPECIES = {c: (r.nombre, r.psat_tabla, r.vL, r.metodo_vL, r.M) for c, r in _catalogo.REGISTRO.items()}


@dataclass(frozen=True)
class Especie:
    cas: str
    nombre: str
    M: float                # kg/mol
    vL: float               # m3/mol
    fuente_vL: str
    psat_forma: str         # 'WagnerPoling' | 'WagnerMcGarry'
    psat: tuple             # (A, B, C, D, Tc, Pc)
    T_psat: tuple           # (Tmin, Tmax) de la correlacion
    cp: tuple               # (a0..a4) con cp/R = sum a_k T^k
    T_cp: tuple

    @property
    def Tc(self):
        return self.psat[4]

    @property
    def T_rango(self):
        """Rango donde el liquido puro esta definido en este paquete."""
        return (max(self.T_psat[0], self.T_cp[0]), min(self.T_psat[1], self.T_cp[1], 0.9 * self.Tc))

    # --- presion de vapor ---------------------------------------------------
    def _lnPr(self, T):
        A, B, C, D, Tc, Pc = self.psat
        tau = 1.0 - T / Tc
        if self.psat_forma == "WagnerPoling":
            num = A * tau + B * tau ** 1.5 + C * tau ** 2.5 + D * tau ** 5
            dnum = -(A + 1.5 * B * tau ** 0.5 + 2.5 * C * tau ** 1.5 + 5 * D * tau ** 4) / Tc
        else:
            num = A * tau + B * tau ** 1.5 + C * tau ** 3 + D * tau ** 6
            dnum = -(A + 1.5 * B * tau ** 0.5 + 3 * C * tau ** 2 + 6 * D * tau ** 5) / Tc
        # ln(P/Pc) = num * Tc / T
        return num * Tc / T, dnum * Tc / T - num * Tc / T ** 2

    def Psat(self, T):
        return self.psat[5] * math.exp(self._lnPr(T)[0])

    def dlnPsat_dT(self, T):
        return self._lnPr(T)[1]

    # --- gas ideal ---------------------------------------------------------
    def cp_ig(self, T):
        return R * sum(a * T ** k for k, a in enumerate(self.cp))

    def h_ig(self, T):
        return R * sum(a * (T ** (k + 1) - T0 ** (k + 1)) / (k + 1) for k, a in enumerate(self.cp))

    def s_ig0(self, T):
        """s del gas ideal puro a (T, P0)."""
        a = self.cp
        return R * (a[0] * math.log(T / T0) + sum(a[k] * (T ** k - T0 ** k) / k for k in range(1, len(a))))

    def g_ig0(self, T):
        return self.h_ig(T) - T * self.s_ig0(T)

    # --- liquido puro --------------------------------------------------------
    def g_L(self, T, P):
        Ps = self.Psat(T)
        return self.g_ig0(T) + R * T * math.log(Ps / P0) + self.vL * (P - Ps)

    def s_L(self, T, P):
        Ps, dl = self.Psat(T), self.dlnPsat_dT(T)
        return self.s_ig0(T) - R * math.log(Ps / P0) - R * T * dl + self.vL * Ps * dl

    def h_L(self, T, P):
        Ps, dl = self.Psat(T), self.dlnPsat_dT(T)
        return self.h_ig(T) - R * T * T * dl + self.vL * (P - Ps) + T * self.vL * Ps * dl


# F0 (arranque concurrente): las tablas de chemicals/thermo se cargan perezosamente en variables globales y
# sus cargadores NO son seguros entre hilos (dos peticiones simultaneas en frio dejaban tablas a medio construir:
# "PiecewiseHeatCapacity ... append", "KeyError: 'ChemSep NRTL'"). Todo acceso de este proyecto a datos
# externos con carga perezosa pasa por este cerrojo reentrante. No cambia ningun valor.
import threading

CARGA_DATOS = threading.RLock()


@lru_cache(maxsize=None)
def especie(cas):
    with CARGA_DATOS:
        return _especie(cas)


def _especie(cas):
    if cas not in _ESPECIES:
        raise KeyError(cas)
    nombre, tabla, vL, metodo, M = _ESPECIES[cas]
    if tabla == "WagnerPoling":
        r = _vp.Psat_data_WagnerPoling.loc[cas]
        T_psat = (float(r.Tmin), float(r.Tmax))
    else:
        r = _vp.Psat_data_WagnerMcGarry.loc[cas]
        T_psat = (float(r.Tmin), float(r.Tc))
    c = _hc.Cp_data_Poling.loc[cas]
    return Especie(cas=cas, nombre=nombre, M=M, vL=vL, fuente_vL=f"thermo VolumeLiquid {metodo} a 298.15 K",
                   psat_forma=tabla, psat=(float(r.A), float(r.B), float(r.C), float(r.D), float(r.Tc), float(r.Pc)),
                   T_psat=T_psat, cp=tuple(float(c[k]) for k in ("a0", "a1", "a2", "a3", "a4")),
                   T_cp=(float(c.Tmin), float(c.Tmax)))


def especies_disponibles():
    return list(_ESPECIES)


@lru_cache(maxsize=None)
def _faltantes_puros(cas):
    if cas not in _ESPECIES:
        return (("registro", "sustancia no registrada"),)
    nombre, tabla, vL, metodo, M = _ESPECIES[cas]
    sal = []
    if not (M > 0):
        sal.append(("masa_molar", "masa molar no positiva en el registro"))
    if not (vL > 0):
        sal.append(("volumen_liquido", "v_L no positivo en el registro"))
    with CARGA_DATOS:
        t = _vp.Psat_data_WagnerPoling if tabla == "WagnerPoling" else _vp.Psat_data_WagnerMcGarry
        if cas not in t.index:
            sal.append(("presion_vapor", f"sin coeficientes en la tabla {tabla} de chemicals"))
        if cas not in _hc.Cp_data_Poling.index:
            sal.append(("cp_gas_ideal", "sin polinomio en la tabla de Poling (chemicals)"))
    return tuple(sal)


def datos_puros_faltantes(cas):
    """[(dato, motivo)] de los datos puros que faltan para construir Especie(cas); vacio si estan todos."""
    return list(_faltantes_puros(cas))


def fuente_psat(e):
    return ("Wagner, Poling et al., The Properties of Gases and Liquids, 5a ed." if e.psat_forma == "WagnerPoling"
            else "Wagner, McGarry, Ind. Eng. Chem. Process Des. Dev. 22 (1983) 313")
