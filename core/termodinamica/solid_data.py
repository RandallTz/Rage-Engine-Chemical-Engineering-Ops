"""
Pure crystalline solids for solid-liquid equilibrium (f8b, SLE).

Each record is one declared polymorph of one pure species. Its Gibbs energy is stated RELATIVE TO THE PURE
LIQUID of the same species at the same (T, P) (the subcooled liquid below the melting point), because that is
the reference of the package's liquid potential mu_i^L = g_i^L(T, P) + RT ln(x_i gamma_i):

    g_i^S(T, P) = g_i^L(T, P) - dg_fus,i(T, P)

dg_fus is not posed; it is integrated from three statements about the pure species:

    (1) melting condition       dg_fus(T_m, P_m) = 0                     (definition of T_m at P_m)
    (2) Gibbs-Helmholtz         d(dg_fus / T)/dT |_P = -dh_fus / T^2
    (3) Kirchhoff, Maxwell      d(dh_fus)/dT |_P = dcp,   d(dg_fus)/dP |_T = dv

With dcp and dv declared constant over the record's window [T_min, T_m]:

    dh_fus(T)    = dh_m + dcp (T - T_m)
    ds_fus(T)    = dh_m / T_m + dcp ln(T / T_m)
    dg_fus(T, P) = dh_fus(T) - T ds_fus(T) + dv (P - P_m)
                 = dh_m (1 - T/T_m) - dcp [T_m - T - T ln(T_m / T)] + dv (P - P_m)

T_min is the lower end of the declared polymorph (a solid-solid transition) or of the constant-dcp window;
below it the record does not apply and callers reject the state (no polymorph is invented).

Values are taken from the NIST Chemistry WebBook (Mask=4 and Mask=6 pages for each CAS, read 5 November
2026); the citation of each number is in `sources`.
"""

import math
import numbers
from dataclasses import dataclass, field


def check_pressure(P, solid=None):
    """Located rejection (cause `invalid_pressure`) of a pressure that is not a finite positive real number.
    Every SLE property depends on P through dg_fus = ... + dv (P - P_m); with dv = 0 a NaN P would otherwise
    propagate silently as NaN (A1 review SLE-1)."""
    try:
        ok = isinstance(P, numbers.Real) and not isinstance(P, bool) and math.isfinite(P) and P > 0.0
    except TypeError:
        ok = False
    if not ok:
        from core.mezclas import FueraDeAlcance
        who = f" (solid {solid.name}, {solid.cas})" if solid is not None else ""
        raise FueraDeAlcance("invalido", f"P = {P!r} Pa is not a finite positive pressure{who}.",
                             cause="invalid_pressure", solid=solid.cas if solid is not None else None, P=P)
    return float(P)


@dataclass(frozen=True)
class SolidPure:
    cas: str
    name: str
    polymorph: str
    T_m: float                # K, melting temperature at P_m
    P_m: float                # Pa
    dh_m: float               # J/mol, enthalpy of fusion at T_m
    dcp: float                # J/(mol K), cp_L - cp_S, declared constant on [T_min, T_m]
    dv: float                 # m3/mol, v_L - v_S, declared constant
    T_min: float              # K, lower end of the record (polymorph transition or dcp window)
    sources: dict = field(default_factory=dict)

    def dh_fus(self, T):
        return self.dh_m + self.dcp * (T - self.T_m)

    def ds_fus(self, T):
        return self.dh_m / self.T_m + self.dcp * math.log(T / self.T_m)

    def dcp_fus(self, T):
        return self.dcp

    def dg_fus(self, T, P):
        return self.dh_fus(T) - T * self.ds_fus(T) + self.dv * (P - self.P_m)

    def melting_T(self, P):
        """Melting temperature at P: root of dg_fus(T, P) = 0 nearest T_m (T_m itself when dv = 0), by Newton
        from T_m (d(dg_fus)/dT = -ds_fus). Located rejection (F9-R14) when an iterate leaves T > 0 or meets
        ds_fus <= 0, when Newton does not converge in 50 steps, or when the root lies below the record's T_min
        (the record does not apply there). The record declares no pressure range for constant dv.
        P must be a finite positive pressure in every case, also when dv = 0 makes T_m independent of P: a NaN
        or non-positive P is rejected first with the located cause `invalid_pressure` (A1 review SLE-1)."""
        check_pressure(P, self)
        if self.dv == 0.0 or P == self.P_m:
            return self.T_m

        def reject(why):
            from core.mezclas import FueraDeAlcance
            raise FueraDeAlcance("fuera_de_dominio", f"No melting temperature of {self.name} ({self.cas}, "
                                 f"{self.polymorph}) at P = {P:.6g} Pa from its record: {why}.", T_fuera=True,
                                 cause="melting_T_undefined", solid=self.cas, P=P)

        T = self.T_m
        for _ in range(50):
            ds = self.ds_fus(T)
            if not ds > 0.0:
                reject(f"ds_fus = {ds:.6g} J/(mol K) <= 0 at T = {T:.6g} K")
            step = self.dg_fus(T, P) / ds
            T += step
            if not (math.isfinite(T) and T > 0.0):
                reject(f"the Newton iterate left T > 0 (dg_fus = dv (P - P_m) = {self.dv * (P - self.P_m):.6g} "
                       "J/mol cannot be balanced)")
            if abs(step) < 1e-12 * T:
                break
        else:
            reject("Newton on dg_fus did not converge in 50 steps")
        if T < self.T_min:
            reject(f"the root {T:.6g} K lies below the record's T_min = {self.T_min:.6g} K")
        return T

    def pure_properties(self, T, P, g_L, h_L, s_L, cp_L=None):
        """Solid properties from the pure-liquid properties at the same (T, P): g_S = g_L - dg_fus,
        h_S = h_L - dh_fus, s_S = s_L - ds_fus, cp_S = cp_L - dcp (g_S = h_S - T s_S holds when it holds
        for the liquid)."""
        # With dv constant, d(dh)/dP = dv - T d(dv)/dT = dv: the dv (P - P_m) term belongs to h, not to s.
        out = {"g": g_L - self.dg_fus(T, P), "h": h_L - self.dh_fus(T) - self.dv * (P - self.P_m),
               "s": s_L - self.ds_fus(T)}
        if cp_L is not None:
            out["cp"] = cp_L - self.dcp
        return out

    def describe(self):
        return {"cas": self.cas, "name": self.name, "polymorph": self.polymorph, "T_m": self.T_m, "P_m": self.P_m,
                "dh_m": self.dh_m, "dcp": self.dcp, "dv": self.dv, "T_min": self.T_min,
                "sources": dict(self.sources)}


REGISTRY = {
    "71-43-2": SolidPure(
        cas="71-43-2", name="benzene", polymorph="crystal I (orthorhombic; the only form at 0.1 MPa)",
        T_m=278.69, P_m=101325.0, dh_m=9866.3, dcp=13.0, dv=0.0, T_min=200.0,
        sources={
            "T_m, dh_m": "Oliver, Eaton et al. 1948 (NIST WebBook, enthalpy of fusion table): 9.8663 kJ/mol at "
                         "278.69 K",
            "dcp": "cp_L 131.4 J/(mol K) at 287.8 K (Kolosovskii and Udovenko 1934) minus cp_S 118.4 J/(mol K) "
                   "at 273 K (Maass and Walbauer 1925), NIST WebBook; declared constant",
            "dv": "declared 0 (pressure effect on the melting point not modelled)",
            "T_min": "declared lower end of the constant-dcp window",
        }),
    "110-82-7": SolidPure(
        cas="110-82-7", name="cyclohexane", polymorph="crystal I (plastic, cubic), stable 186.1-279.82 K",
        T_m=279.82, P_m=101325.0, dh_m=2676.9, dcp=0.0, dv=0.0, T_min=186.1,
        sources={
            "T_m, dh_m": "Ruehrwein and Huffman 1943 (NIST WebBook, crystal I to liquid): 2.6769 kJ/mol at "
                         "279.82 K",
            "dcp": "declared 0: the NIST WebBook lists no solid cp for cyclohexane",
            "dv": "declared 0",
            "T_min": "crystal II to crystal I transition at 186.1 K (Ruehrwein and Huffman 1943); crystal II is "
                     "not modelled",
        }),
}


def solid(cas):
    """The registered solid of a species; KeyError when there is none (no data are invented)."""
    return REGISTRY[cas]
