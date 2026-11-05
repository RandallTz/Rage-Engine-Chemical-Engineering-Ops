"""
Solid-liquid equilibrium (SLE) of pure crystalline solids with a liquid mixture (f8b).

Derivation (no final formula is posed). A pure solid i (declared polymorph, core/termodinamica/solid_data.py)
coexists with a liquid of composition x at (T, P) when the chemical potential of i is equal in both phases:

    mu_i^S(T, P) = mu_i^L(T, P, x)

- Liquid side: the package potential, reference the pure liquid of i at (T, P) (Lewis-Randall):
  mu_i^L = g_i^L(T, P) + RT ln(x_i gamma_i(T, x)).
- Solid side: a pure phase, so mu_i^S = g_i^S(T, P). Its reference is the SAME pure liquid:
  g_i^S = g_i^L - dg_fus,i(T, P), with dg_fus integrated from the melting condition, Gibbs-Helmholtz and
  Kirchhoff (solid_data.SolidPure).

Subtracting, g_i^L cancels exactly and the condition is

    ln(x_i gamma_i(T, x)) = -dg_fus,i(T, P) / RT

so the pure-liquid potential is never evaluated below the package's own liquid domain; the state's domain is
the solid record's window and the activity model's range. The same difference defines the solid's
tangent-plane distance against the liquid, on the scale of the layer's `tm` (core/termodinamica/capa.py):

    tm_S,i = (g_i^S - mu_i^L) / RT = -ln(x_i gamma_i) - dg_fus,i / RT

tm_S,i > 0: solid i cannot appear; tm_S,i = 0: saturated (liquidus); tm_S,i < 0: supersaturated.

Latent energy. Crystallizing dn of i from the saturated liquid at constant (T, P) releases

    L_i = hbar_i^L - h_i^S = dh_fus,i(T) + hbar_i^E,    hbar_i^E = -RT^2 (d ln gamma_i / dT)_{P,x}

(h_i^S = h_i^L - dh_fus, hbar_i^L = h_i^L + hbar_i^E). Differentiating the condition along the liquidus gives
the consistency relation the tests check: (d ln a_i / dx)_T dx/dT |_liquidus = L_i / RT^2.

Operations (binary helpers and N-species crystallization temperature):
- `SolidLiquidSystem.from_sistema(sis)` / `.from_unifac(cas, variant)`: liquid model plus solid records.
- `solid_tm(i, T, P, x)`; `liquidus_T(i, x, P)`; `crystallization_T(x, P)` (first solid to appear on cooling).
- `solubility(i, T, P)` (binary); `eutectic(P)` (binary, simple eutectic); `liquidus_curve(P, n)`.
- `latent_heat(i, T, P, x)`; `certify(point)`.
"""

import math

import numpy as np
from scipy.optimize import brentq

from core import mezclas as mz
from core.termodinamica import solid_data

R = mz.R
TOL_TM = 1e-10                 # |tm_S| accepted as saturation
TOL_ROOT = 1e-12


class SolidLiquidSystem:
    def __init__(self, cas, liquid, solids=None, source=""):
        self.cas = tuple(cas)
        self.liquid = liquid
        if solids is None:
            solids = {c: solid_data.REGISTRY[c] for c in self.cas if c in solid_data.REGISTRY}
        self.solids = {self.cas.index(c): s for c, s in solids.items()}
        self.source = source
        self.T_range = getattr(liquid, "rango_T", None)

    @classmethod
    def from_sistema(cls, sis, solids=None):
        """Liquid model of a core/mezclas.Sistema (the common package interface)."""
        return cls(sis.cas, sis.liq, solids, source=f"{sis.paquete.id}: {sis.procedencia}")

    @classmethod
    def from_unifac(cls, cas, variant="original", solids=None):
        """UNIFAC liquid for species with DDBST group assignments, also outside the pure-component catalog."""
        from core import unifac
        return cls(cas, unifac.LiquidoUNIFAC(list(cas), variant), solids, source=f"UNIFAC {variant}")

    # --- domain ----------------------------------------------------------------
    def _solid(self, i):
        if i not in self.solids:
            raise mz.FaltaParametro(f"No solid record for {self.cas[i]}.", (self.cas[i],), codigo="SOLIDO_AUSENTE",
                                    detalle={"tipo": "solido", "cas": self.cas[i]})
        return self.solids[i]

    def window(self, i, P):
        """[T_lo, T_hi] where solid i and the activity model are both defined."""
        s = self._solid(i)
        lo, hi = s.T_min, s.melting_T(P)
        if self.T_range is not None:
            lo, hi = max(lo, self.T_range[0]), min(hi, self.T_range[1])
        return lo, hi

    def _check(self, i, T, P):
        lo, hi = self.window(i, P)
        if not lo - 1e-9 <= T <= hi + 1e-9:
            raise mz.FueraDeAlcance("fuera_de_dominio", f"T = {T:.6g} K outside the SLE window of "
                                    f"{self.cas[i]} [{lo:.6g}, {hi:.6g}] K (solid record and activity model).",
                                    T_fuera=True)

    # --- potentials --------------------------------------------------------------
    def lngamma(self, T, x):
        return np.asarray(self.liquid.lngamma(T, np.asarray(x, float)), float)

    def solid_tm(self, i, T, P, x):
        """(g_i^S - mu_i^L)/RT. +inf when x_i = 0: mu_i^L -> -inf, so a liquid without i dissolves solid i."""
        x = np.asarray(x, float)
        if x[i] <= 0.0:
            return math.inf
        s = self._solid(i)
        return -(math.log(x[i]) + self.lngamma(T, x)[i]) - s.dg_fus(T, P) / (R * T)

    def hbar_E(self, i, T, x):
        """Partial excess enthalpy -RT^2 (d ln gamma_i/dT)_x, central difference (step 1e-4 T)."""
        h = 1e-4 * T
        d = (self.lngamma(T + h, x)[i] - self.lngamma(T - h, x)[i]) / (2 * h)
        return -R * T * T * d

    def latent_heat(self, i, T, P, x):
        """L_i = hbar_i^L - h_i^S = dh_fus,i(T) + dv (P - P_m) + hbar_i^E, J/mol released on crystallization."""
        s = self._solid(i)
        return s.dh_fus(T) + s.dv * (P - s.P_m) + self.hbar_E(i, T, x)

    # --- equilibrium -------------------------------------------------------------
    def liquidus_T(self, i, x, P):
        """T at which solid i saturates the liquid x (tm_S,i = 0); FueraDeAlcance when no root in the window."""
        x = np.asarray(x, float)
        lo, hi = self.window(i, P)
        f = lambda T: self.solid_tm(i, T, P, x)
        flo, fhi = f(lo), f(hi)
        if abs(fhi) <= TOL_TM:
            return hi
        if flo * fhi > 0:
            raise mz.FueraDeAlcance("fuera_de_dominio", f"Solid {self.cas[i]} does not saturate x = "
                                    f"{np.round(x, 6).tolist()} inside its window [{lo:.6g}, {hi:.6g}] K.",
                                    T_fuera=True)
        return brentq(f, lo, hi, xtol=TOL_ROOT * hi, rtol=4 * np.finfo(float).eps, maxiter=200)

    def crystallization_T(self, x, P):
        """First solid to appear on cooling the liquid x: (T, i), the highest liquidus temperature over the
        registered solids present in x. Solids whose liquidus lies below their window are skipped."""
        best = None
        for i in sorted(self.solids):
            if x[i] <= 0.0:
                continue
            try:
                T = self.liquidus_T(i, x, P)
            except mz.FueraDeAlcance:
                continue
            if best is None or T > best[0]:
                best = (T, i)
        if best is None:
            raise mz.FueraDeAlcance("fuera_de_dominio", "No registered solid saturates this liquid in its window.",
                                    T_fuera=True)
        return best

    def _binary(self):
        if len(self.cas) != 2:
            raise ValueError("binary helper called on a system of %d species" % len(self.cas))

    def solubility(self, i, T, P):
        """Binary: mole fraction x_i of the liquid saturated with solid i at (T, P)."""
        self._binary()
        self._check(i, T, P)
        f = lambda xi: self.solid_tm(i, T, P, self._x(i, xi))
        hi = 1.0
        if f(hi) > 0:                                 # T above the melting point (to rounding)
            raise mz.FueraDeAlcance("fuera_de_dominio", "Pure liquid already stable against the solid.",
                                    T_fuera=True)
        lo = 1e-300
        return brentq(f, lo, hi, xtol=1e-15, rtol=4 * np.finfo(float).eps, maxiter=300)

    @staticmethod
    def _x(i, xi):
        x = np.empty(2)
        x[i], x[1 - i] = xi, 1.0 - xi
        return x

    def eutectic(self, P):
        """Binary simple eutectic: (T, x) where both solids saturate the same liquid. Solved as one equation in
        T: x_0(T) from solid 0 plus x_1(T) from solid 1 equals one."""
        self._binary()
        lo = max(self.window(0, P)[0], self.window(1, P)[0])
        hi = min(self.window(0, P)[1], self.window(1, P)[1])
        g = lambda T: self.solubility(0, T, P) + self.solubility(1, T, P) - 1.0
        glo, ghi = g(lo), g(hi)
        if glo * ghi > 0:
            raise mz.FueraDeAlcance("fuera_de_dominio", f"No eutectic in [{lo:.6g}, {hi:.6g}] K.", T_fuera=True)
        T = brentq(g, lo, hi, xtol=TOL_ROOT * hi, rtol=4 * np.finfo(float).eps, maxiter=200)
        x0 = self.solubility(0, T, P)
        return self.certify({"T": T, "P": P, "x": self._x(0, x0), "solids": [0, 1]})

    def liquidus_curve(self, P, n=25):
        """Binary: both liquidus branches from each pure melting point to the eutectic (n points each)."""
        e = self.eutectic(P)
        branches = []
        for i in (0, 1):
            Ts = np.linspace(self.window(i, P)[1], e["T"], n)
            pts = []
            for T in Ts:
                xi = 1.0 if T == Ts[0] else self.solubility(i, T, P)
                pts.append(self.certify({"T": float(T), "P": P, "x": self._x(i, xi), "solids": [i]}))
            branches.append({"solid": i, "cas": self.cas[i], "points": pts})
        return {"eutectic": e, "branches": branches}

    def certify(self, point):
        """Fresh residuals: tm_S = 0 for each declared solid, tm_S >= 0 for every other registered solid
        (no further solid supersaturates the liquid), normalization, window. Adds latent heats."""
        T, P, x = point["T"], point["P"], np.asarray(point["x"], float)
        res = {}
        ok = abs(x.sum() - 1.0) <= 1e-12 and bool(np.all(x >= 0))
        latent = {}
        for i in sorted(self.solids):
            lo, hi = self.window(i, P)
            inside = lo - 1e-9 <= T <= hi + 1e-9
            tm = self.solid_tm(i, T, P, x)
            res[self.cas[i]] = tm
            if i in point["solids"]:
                ok = ok and inside and abs(tm) <= TOL_TM
                latent[self.cas[i]] = self.latent_heat(i, T, P, x)
            elif inside:
                ok = ok and tm >= -TOL_TM
        out = dict(point)
        out["x"] = x
        out["tm_solid"] = res
        out["latent_heat"] = latent
        out["certificate"] = "cumple" if ok else "no_cumple"
        return out
