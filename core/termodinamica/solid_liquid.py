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

Saturated liquid must also be stable (F9-R11). The condition above is necessary, not sufficient: the liquid
of composition x must itself be stable against splitting into other liquids. With the same Lewis-Randall
reference, the liquid's tangent-plane distance of a trial liquid w against x is (g_j^L cancels again)

    tpd(w) = sum_j w_j [ln w_j + ln gamma_j(T, w) - ln x_j - ln gamma_j(T, x)]

and x is stable when tpd(w) >= 0 for every w. Inside a liquid-liquid gap ln a_i(x) is not monotonic, so the
saturation condition can have several roots at one T; the roots with a negative tpd (metastable or inside the
spinodal) are not saturated liquids. For a binary the stable root is unique away from the monotectic, where
two liquids and the solid coexist (S-L1-L2); that three-phase line is not computed here, and a state whose
saturated liquids are all unstable is rejected with the cause `liquid_liquid_instability`.

Latent energy. Crystallizing dn of i from the saturated liquid at constant (T, P) releases

    L_i = hbar_i^L - h_i^S = dh_fus,i(T) + hbar_i^E,    hbar_i^E = -RT^2 (d ln gamma_i / dT)_{P,x}

(h_i^S = h_i^L - dh_fus, hbar_i^L = h_i^L + hbar_i^E). Differentiating the condition along the liquidus gives
the consistency relation the tests check: (d ln a_i / dx)_T dx/dT |_liquidus = L_i / RT^2.

Numerics. The binary solubility is solved in u = ln x_i (F9-R10), so the relative accuracy of x_i is the
same at x_i = 1e-34 as at 0.5; the solvent fraction is -expm1(u), without cancellation near x_i = 1. Every
root of the condition is bracketed on a fixed grid before it is polished, and every root is tested for
liquid stability, so the answer does not depend on which bracket a solver happens to find.

Operations (binary helpers and N-species crystallization temperature):
- `SolidLiquidSystem.from_sistema(sis)` / `.from_unifac(cas, variant)`: liquid model plus solid records.
- `solid_tm(i, T, P, x)`; `liquidus_T(i, x, P)`; `crystallization_T(x, P)` (first solid to appear on cooling).
- `liquid_stability(T, x)`: least tangent-plane distance of the liquid found from 2N trial liquids.
- `solubility(i, T, P)` (binary); `solubility_roots(i, T, P)` (every root with its stability);
  `eutectic(P)` (binary, simple eutectic); `liquidus_curve(P, n)`.
- `latent_heat(i, T, P, x)`; `certify(point)`.

Rejections are `FueraDeAlcance` with `datos["cause"]` (and `datos["solid"]` when a solid is involved):
`outside_window`, `invalid_composition`, `invalid_temperature`, `pure_liquid_stable`, `solubility_underflow`,
`liquidus_below_solid_T_min`, `liquidus_below_activity_range`, `liquidus_above_window`,
`liquid_liquid_instability`, `no_saturation_root` and, from `solid_data`, `melting_T_undefined` and
`invalid_pressure` (P not finite and positive, checked before every other use of P). A solid index that is not
a species of the system, or a species without a solid record, is `FaltaParametro` with codigo `SOLIDO_AUSENTE`.
"""

import math

import numpy as np
from scipy.optimize import brentq

from core import mezclas as mz
from core.termodinamica import solid_data

R = mz.R
TOL_TM = 1e-10                 # |tm_S| accepted as saturation
TOL_ROOT = 1e-12
TOL_X = 1e-12                  # |sum x - 1| accepted as normalized
TOL_TPD = 1e-10                # tpd below -TOL_TPD proves the liquid unstable
U_MIN = math.log(1e-300)       # lower end of the solubility search, x_i = 1e-300
# Solubility bracketing grid in u = ln x_i: logarithmic in x below 1e-3, uniform in x above (where a
# liquid-liquid gap puts its roots), the last node exactly x_i = 1.
_U_GRID = np.unique(np.concatenate([np.linspace(U_MIN, math.log(1e-3), 60),
                                    np.log(np.linspace(1e-3, 1.0, 400))]))
_U_GRID[-1] = 0.0
N_T_GRID = 41                  # liquidus_T bracketing grid over the window


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
    def _species_index(self, i):
        """A species index of the system: an integer (not bool) in 0..N-1. Otherwise a located FueraDeAlcance with
        cause `invalid_species_index` (A1 repairs review R2)."""
        if isinstance(i, (int, np.integer)) and not isinstance(i, bool) and 0 <= i < len(self.cas):
            return int(i)
        raise mz.FueraDeAlcance("invalido", f"Species index {i!r} is not a species of this system "
                                f"(0..{len(self.cas) - 1}: {list(self.cas)}).", cause="invalid_species_index",
                                index=repr(i), species=list(self.cas))

    def _solid(self, i):
        """The solid record of species index i. A located FaltaParametro SOLIDO_AUSENTE when the index is not a
        species of the system (A1 review SLE-2: never a raw IndexError) or the species has no solid record."""
        valid = isinstance(i, (int, np.integer)) and not isinstance(i, bool) and 0 <= i < len(self.cas)
        if not valid:
            raise mz.FaltaParametro(f"Solid index {i!r} is not a species of this system (0..{len(self.cas) - 1}: "
                                    f"{list(self.cas)}).", (), codigo="SOLIDO_AUSENTE",
                                    detalle={"tipo": "solido", "cas": None, "indice": repr(i),
                                             "especies": list(self.cas)})
        if i not in self.solids:
            raise mz.FaltaParametro(f"No solid record for {self.cas[i]}.", (self.cas[i],), codigo="SOLIDO_AUSENTE",
                                    detalle={"tipo": "solido", "cas": self.cas[i]})
        return self.solids[i]

    def window(self, i, P):
        """[T_lo, T_hi] where solid i and the activity model are both defined. P is validated first
        (finite, > 0; located cause `invalid_pressure`), also for dv = 0 records (A1 review SLE-1)."""
        s = self._solid(i)
        solid_data.check_pressure(P, s)
        lo, hi = s.T_min, s.melting_T(P)
        if self.T_range is not None:
            lo, hi = max(lo, self.T_range[0]), min(hi, self.T_range[1])
        return lo, hi

    def _check(self, i, T, P):
        self._solid(i)
        if not (math.isfinite(T) and T > 0.0):
            raise mz.FueraDeAlcance("invalido", f"T = {T!r} K is not a positive temperature.", T_fuera=True,
                                    cause="invalid_temperature", solid=self.cas[i])
        lo, hi = self.window(i, P)
        if not lo - 1e-9 <= T <= hi + 1e-9:
            raise mz.FueraDeAlcance("fuera_de_dominio", f"T = {T:.6g} K outside the SLE window of "
                                    f"{self.cas[i]} [{lo:.6g}, {hi:.6g}] K (solid record and activity model).",
                                    T_fuera=True, cause="outside_window", solid=self.cas[i])

    def _composition(self, x):
        x = np.asarray(x, float)
        if x.shape != (len(self.cas),) or not np.all(np.isfinite(x)) or np.any(x < 0.0) \
                or abs(x.sum() - 1.0) > TOL_X:
            raise mz.FueraDeAlcance("invalido", f"x = {x.tolist()} is not {len(self.cas)} non-negative mole "
                                    f"fractions summing to 1 (tolerance {TOL_X:g}).", cause="invalid_composition")
        return x

    # --- potentials --------------------------------------------------------------
    def lngamma(self, T, x):
        return np.asarray(self.liquid.lngamma(T, np.asarray(x, float)), float)

    def solid_tm(self, i, T, P, x):
        """(g_i^S - mu_i^L)/RT. +inf when x_i = 0: mu_i^L -> -inf, so a liquid without i dissolves solid i.
        Rejects (located) an unnormalized or negative x and a T outside the SLE window of solid i (F9-R14)."""
        x = self._composition(x)
        self._check(i, T, P)
        if x[i] <= 0.0:
            return math.inf
        s = self._solid(i)
        return -(math.log(x[i]) + self.lngamma(T, x)[i]) - s.dg_fus(T, P) / (R * T)

    def hbar_E(self, i, T, x):
        """Partial excess enthalpy -RT^2 (d ln gamma_i/dT)_x, central difference (step 1e-4 T). i must be a species
        index of the system (located `invalid_species_index` otherwise; A1 repairs review R2)."""
        i = self._species_index(i)
        h = 1e-4 * T
        d = (self.lngamma(T + h, x)[i] - self.lngamma(T - h, x)[i]) / (2 * h)
        return -R * T * T * d

    def latent_heat(self, i, T, P, x):
        """L_i = hbar_i^L - h_i^S = dh_fus,i(T) + dv (P - P_m) + hbar_i^E, J/mol released on crystallization."""
        s = self._solid(i)
        solid_data.check_pressure(P, s)
        return s.dh_fus(T) + s.dv * (P - s.P_m) + self.hbar_E(i, T, x)

    # --- liquid stability ----------------------------------------------------------
    def liquid_stability(self, T, x, max_iter=500):
        """Least tangent-plane distance of the liquid x at T against trial liquids (Michelsen successive
        substitution ln W_j = ln x_j + ln gamma_j(x) - ln gamma_j(w), w = W / sum W) from 2N starts: each
        present species nearly pure, and the midpoint between x and that corner. Every iterate is a trial
        liquid, so any iterate with tpd < -TOL_TPD proves the instability; tpd >= -TOL_TPD over all iterates
        is the usual numerical verdict of stability, not a proof.
        Returns {"tpd_min", "w", "stable"}."""
        x = np.asarray(x, float)
        idx = np.flatnonzero(x > 0.0)
        m = len(idx)
        if m <= 1:
            return {"tpd_min": 0.0, "w": x.copy(), "stable": True}
        full = np.zeros(len(x))

        def lng(w):
            full[:] = 0.0
            full[idx] = w
            return self.lngamma(T, full)[idx]

        xs = x[idx]
        d = np.log(xs) + lng(xs)
        best_tpd, best_w = 0.0, x.copy()
        starts = []
        for k in range(m):
            c = np.full(m, 1e-6 / (m - 1))
            c[k] = 1.0 - 1e-6
            starts += [c, 0.5 * (c + xs)]
        for w in starts:
            w = w / w.sum()
            for _ in range(max_iter):
                g = lng(w)
                tpd = float(np.sum(w * (np.log(w) + g - d)))
                if tpd < best_tpd:
                    best_tpd = tpd
                    best_w = np.zeros(len(x))
                    best_w[idx] = w
                lnW = d - g
                w_new = np.exp(lnW - lnW.max())
                w_new /= w_new.sum()
                w_new = np.maximum(w_new, 1e-300)
                if np.max(np.abs(np.log(w_new) - np.log(w))) < 1e-11:
                    break
                w = w_new
        return {"tpd_min": best_tpd, "w": best_w, "stable": best_tpd >= -TOL_TPD}

    def _require_stable(self, i, T, x, what):
        st = self.liquid_stability(T, x)
        if not st["stable"]:
            raise mz.FueraDeAlcance(
                "fuera_de_dominio", f"{what}: the liquid x = {np.round(x, 6).tolist()} at T = {T:.6g} K is "
                f"unstable against liquid-liquid splitting (least tangent-plane distance {st['tpd_min']:.3g} at "
                f"w = {np.round(st['w'], 6).tolist()}); it is not a saturated liquid of {self.cas[i]}. The "
                "solid-liquid-liquid (monotectic) state is not computed.", T_fuera=True,
                cause="liquid_liquid_instability", solid=self.cas[i], T=T, tpd_min=st["tpd_min"],
                w=st["w"].tolist())
        return st

    # --- equilibrium -------------------------------------------------------------
    def liquidus_T(self, i, x, P):
        """T at which solid i first saturates the liquid x on cooling: the highest root of tm_S,i(T) = 0 in the
        window, bracketed on a grid of N_T_GRID points, at which the liquid x is stable. FueraDeAlcance (with
        `cause`) when there is no such root in the window or the liquid there is unstable."""
        x = self._composition(x)
        s = self._solid(i)
        lo, hi = self.window(i, P)
        f = lambda T: self.solid_tm(i, T, P, x)
        name = self.cas[i]
        fhi = f(hi)
        if abs(fhi) <= TOL_TM:
            self._require_stable(i, hi, x, f"Liquidus of {name}")
            return hi
        if fhi < 0.0:
            clipped = self.T_range is not None and hi < s.melting_T(P)
            raise mz.FueraDeAlcance(
                "fuera_de_dominio", f"Solid {name} already supersaturates x = {np.round(x, 6).tolist()} at the "
                f"top of its window ({hi:.6g} K, " + ("upper end of the activity model's range" if clipped else
                                                     "its melting temperature") + "): the liquidus lies above.",
                T_fuera=True, cause="liquidus_above_window", solid=name)
        Ts = np.linspace(hi, lo, N_T_GRID)
        Ts[0], Ts[-1] = hi, lo
        prev_T, prev_f = hi, fhi
        for T in Ts[1:]:
            fT = f(T)
            if fT <= 0.0:
                root = T if fT == 0.0 else brentq(f, T, prev_T, xtol=TOL_ROOT * hi,
                                                   rtol=4 * np.finfo(float).eps, maxiter=200)
                self._require_stable(i, root, x, f"Liquidus of {name}")
                return root
            prev_T, prev_f = T, fT
        clipped = lo > s.T_min
        raise mz.FueraDeAlcance(
            "fuera_de_dominio", f"Solid {name} does not saturate x = {np.round(x, 6).tolist()} inside its window "
            f"[{lo:.6g}, {hi:.6g}] K: the liquidus lies below " + (
                "the lower end of the activity model's range" if clipped else f"the solid record's T_min"),
            T_fuera=True, cause="liquidus_below_activity_range" if clipped else "liquidus_below_solid_T_min",
            solid=name)

    def crystallization_T(self, x, P):
        """First solid to appear on cooling the liquid x: (T, i), the highest liquidus temperature over the
        registered solids present in x. A solid is skipped only when its liquidus lies below its own record's
        T_min (it cannot appear in the record's range), or when its saturated liquid is unstable at a
        temperature below the selected one (the liquid x has crystallized before reaching it). Any other failure
        of a present solid raises, naming the solid and the cause (F9-R12). P is validated before any solid is
        tried, so an invalid P is never reported as a liquidus below T_min (A1 review SLE-1)."""
        x = self._composition(x)
        solid_data.check_pressure(P)
        best, unstable = None, []
        for i in sorted(self.solids):
            if x[i] <= 0.0:
                continue
            try:
                T = self.liquidus_T(i, x, P)
            except mz.FueraDeAlcance as e:
                cause = e.datos.get("cause")
                if cause == "liquidus_below_solid_T_min":
                    continue
                if cause == "liquid_liquid_instability":
                    unstable.append((i, e))
                    continue
                raise mz.FueraDeAlcance(e.motivo, f"Crystallization temperature of x = {np.round(x, 6).tolist()} "
                                        f"not determined: solid {self.cas[i]}: {e.mensaje}",
                                        **{**e.datos, "solid": self.cas[i], "cause": cause}) from e
            if best is None or T > best[0]:
                best = (T, i)
        for i, e in unstable:
            if best is None or e.datos["T"] >= best[0]:
                raise mz.FueraDeAlcance(e.motivo, f"Crystallization temperature of x = {np.round(x, 6).tolist()} "
                                        f"not determined: solid {self.cas[i]}: {e.mensaje}",
                                        **{**e.datos, "solid": self.cas[i]}) from e
        if best is None:
            raise mz.FueraDeAlcance("fuera_de_dominio", "No registered solid saturates this liquid in its window "
                                    "(every present solid's liquidus lies below its record's T_min).",
                                    T_fuera=True, cause="liquidus_below_solid_T_min")
        return best

    def _binary(self):
        if len(self.cas) != 2:
            raise ValueError("binary helper called on a system of %d species" % len(self.cas))

    @staticmethod
    def _xu(i, u):
        """Binary composition with ln x_i = u; the solvent fraction -expm1(u) has no cancellation at x_i -> 1."""
        x = np.empty(2)
        x[i], x[1 - i] = math.exp(u), -math.expm1(u)
        return x

    def solubility_roots(self, i, T, P):
        """Binary: every root x_i of tm_S,i(x) = 0 at (T, P), solved in u = ln x_i on [ln 1e-300, 0], with the
        liquid's stability at each root: [{"x", "stable", "tpd_min", "w"}], ascending in x_i."""
        self._binary()
        self._check(i, T, P)
        s = self._solid(i)
        c = s.dg_fus(T, P) / (R * T)
        f = lambda u: -(u + self.lngamma(T, self._xu(i, u))[i]) - c
        if f(0.0) > 0.0:                              # T above the melting point (to rounding)
            raise mz.FueraDeAlcance("fuera_de_dominio", f"Pure liquid {self.cas[i]} already stable against the "
                                    f"solid at T = {T:.6g} K.", T_fuera=True, cause="pure_liquid_stable",
                                    solid=self.cas[i])
        U = _U_GRID
        X = np.empty((len(U), 2))
        X[:, i], X[:, 1 - i] = np.exp(U), -np.expm1(U)
        if hasattr(self.liquid, "lngamma_lote"):
            G = np.asarray(self.liquid.lngamma_lote(T, X), float)[:, i]
        else:
            G = np.array([self.lngamma(T, xx)[i] for xx in X])
        F = -(U + G) - c
        F[-1] = f(0.0)
        roots = []
        for k in range(len(U) - 1):
            if F[k] == 0.0:
                roots.append(float(U[k]))
            elif F[k] * F[k + 1] < 0.0:
                roots.append(brentq(f, U[k], U[k + 1], xtol=1e-15, rtol=4 * np.finfo(float).eps, maxiter=300))
        if F[-1] == 0.0:
            roots.append(0.0)
        if not roots:
            if F[0] < 0.0:
                raise mz.FueraDeAlcance("fuera_de_dominio", f"Solubility of {self.cas[i]} at T = {T:.6g} K is "
                                        "below 1e-300 (outside the representable range).", T_fuera=True,
                                        cause="solubility_underflow", solid=self.cas[i])
            raise mz.FueraDeAlcance("fuera_de_dominio", f"No saturation root for {self.cas[i]} at T = {T:.6g} K "
                                    "was bracketed on the composition grid.", T_fuera=True,
                                    cause="no_saturation_root", solid=self.cas[i])
        out = []
        for u in roots:
            x = self._xu(i, u)
            st = self.liquid_stability(T, x)
            out.append({"x": x[i], "u": u, "stable": st["stable"], "tpd_min": st["tpd_min"], "w": st["w"]})
        return out

    def solubility(self, i, T, P):
        """Binary: mole fraction x_i of the stable liquid saturated with solid i at (T, P). Rejects (cause
        `liquid_liquid_instability`) when no saturated liquid is stable or more than one is (the S-L1-L2
        monotectic, not computed)."""
        roots = self.solubility_roots(i, T, P)
        stable = [r for r in roots if r["stable"]]
        if len(stable) == 1:
            return stable[0]["x"]
        xs = [float(r["x"]) for r in roots]
        tp = [float(r["tpd_min"]) for r in roots]
        raise mz.FueraDeAlcance(
            "fuera_de_dominio", f"Solubility of {self.cas[i]} at T = {T:.6g} K not determined: the saturation "
            f"condition has the roots x = {xs} with least liquid tangent-plane distances {tp}; "
            + ("none is a stable liquid (liquid-liquid gap)." if not stable else
               f"{len(stable)} are stable liquids (solid-liquid-liquid coexistence, not computed)."),
            T_fuera=True, cause="liquid_liquid_instability", solid=self.cas[i], T=T, roots=xs, tpd_min=tp)

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
            raise mz.FueraDeAlcance("fuera_de_dominio", f"No eutectic in [{lo:.6g}, {hi:.6g}] K.", T_fuera=True,
                                    cause="no_saturation_root")
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
        """Fresh residuals: tm_S = 0 for each declared solid, tm_S >= 0 for every other registered solid whose
        window contains T (no further solid supersaturates the liquid), normalization, window, and the
        liquid's own stability (tangent-plane test, F9-R11). Adds latent heats. Every declared solid in
        point["solids"] (a list or tuple) must be a registered solid of the system (`_solid`: FaltaParametro
        SOLIDO_AUSENTE otherwise), so an undeclared index can never yield "cumple" (A1 repairs review R2)."""
        T, P, x = point["T"], point["P"], np.asarray(point["x"], float)
        declared = point["solids"]
        if not isinstance(declared, (list, tuple)):
            raise mz.FueraDeAlcance("invalido", f"point['solids'] = {declared!r} is not a list of solid indices.",
                                    cause="invalid_species_index", index=repr(declared), species=list(self.cas))
        for i in declared:
            self._solid(i)
        declared = {int(i) for i in declared}
        res = {}
        ok = abs(x.sum() - 1.0) <= TOL_X and bool(np.all(x >= 0))
        latent = {}
        for i in sorted(self.solids):
            lo, hi = self.window(i, P)
            inside = lo - 1e-9 <= T <= hi + 1e-9
            tm = self.solid_tm(i, T, P, x) if inside and ok else None
            res[self.cas[i]] = tm
            if i in declared:
                ok = ok and inside and abs(tm) <= TOL_TM
                if ok:
                    latent[self.cas[i]] = self.latent_heat(i, T, P, x)
            elif tm is not None:
                ok = ok and tm >= -TOL_TM
        stab = self.liquid_stability(T, x) if bool(np.all(x >= 0)) else {"tpd_min": None, "w": None,
                                                                          "stable": False}
        ok = ok and stab["stable"]
        out = dict(point)
        out["x"] = x
        out["tm_solid"] = res
        out["latent_heat"] = latent
        out["liquid_stability"] = stab
        out["certificate"] = "cumple" if ok else "no_cumple"
        return out
