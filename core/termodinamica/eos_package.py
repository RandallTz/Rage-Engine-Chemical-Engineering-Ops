"""Cubic EOS packages (Peng-Robinson, PSRK) as dynamic-volume packages of the common path (F8b, Claude).

`peng-robinson-vdw1f` and `psrk-unifac` already close a volume through the layer (`capa.cierre`, TP/PH/UV). This
module gives the same closures the interface that the common compiler and the network accounting use for every
other mixture package (`core.paquetes_volumen.PaqueteMezcla`): `estado(spec, a, b, n)` returns a
`core.mezclas.EstadoMezcla` with `FaseMezcla` per phase (h, s, v, g, mu, M on the shared ideal-gas reference),
`certify_state` re-certifies a located state, `transporte_TP` gives the molar enthalpy and entropy of a stream.
Nothing is reimplemented: the flashes are `cubic_flash.flash_TP/PH/UV` and the potentials are the EOS's own
`molar_props`. Two specifications that the flash module does not have are solved here from the same TP flash:
TV (rigid vessel at a temperature; ln P root of V(T, P)) and UP (U at a pressure; T root of U(T, P)).

Located rejections, never a fallback to another package: a species without a record, a missing PSRK group or
interaction, a temperature below the alpha regression range, a state outside a light gas's ideal-gas record, a
liquid-liquid split or a third phase (the package has one vapour and one liquid candidate), a root outside the
search window. Each is `core.mezclas.FueraDeAlcance` with the cause in `datos`. Pure-data substitutions are not
admitted (the EOS reads its own records).
"""

import hashlib
import json
import math

import numpy as np
from scipy.optimize import brentq

from core import mezclas as mz
from core import mezclas_datos as datos
from core import paquetes_volumen as pv

from . import cubic_eos, cubic_flash
from .capa import EOS_PAQUETES, PSRK

VERSION = "1"
P_BOUNDS = (1e3, 5e7)           # Pa, the cubic flash's default pressure window
T_BOUNDS = (150.0, 1000.0)      # K, its default temperature window
WARM_DT = 25.0                  # K, half-width of the warm T bracket around the previous state

# causes that are numerical (the search failed) and not a statement that the state is outside the package
_NUMERICAL = {"outside_bracket", "not_converged", "not_monotone", "not_evaluable", "singular_split_hessian",
              "no_rachford_rice_root", "not_certified", "unlocated"}


def es_modelo_eos(modelo):
    return isinstance(modelo, dict) and modelo.get("id") in EOS_PAQUETES and modelo.get("version") == VERSION


def _masa_molar(cas):
    """kg/mol: the catalog record for a catalog species (as every mixture package), else the identifier tables."""
    from core import catalogo
    if cas in catalogo.REGISTRO:
        return datos.especie(cas).M
    from chemicals.identifiers import MW
    return float(MW(cas)) / 1000.0


def _located(error):
    """`mz.FueraDeAlcance` carrying the located cause of a cubic/PSRK rejection."""
    d = dict(getattr(error, "datos", {}) or {})
    cause = str(d.get("cause") or "unlocated")
    motivo = "no_convergente" if cause in _NUMERICAL else "no_soportado"
    return mz.FueraDeAlcance(motivo, str(error), **d)


class _SistemaEOS:
    """The few `Sistema` attributes that the common evaluation and fingerprint read."""

    def __init__(self, paquete):
        self._p = paquete
        self.cas = paquete.especies
        self.M = paquete.M
        self.T_rango = paquete.T_rango
        self.metodo_estabilidad = (
            f"{paquete.id}: one residual Helmholtz function for both phases (cubic_eos / psrk). Phase identification "
            "by the roots of the cubic; stability by the Michelsen tangent-plane distance from Wilson, pure and "
            "grid seeds with successive substitution and BFGS; the split by Rachford-Rice with Newton on equal "
            "fugacities; certification by equal ln f and a fresh tangent-plane search. At most vapour and one liquid; "
            "a liquid-liquid split or a third phase is a located rejection. Reference: ideal gas h = s = 0 at "
            "298.15 K and 1e5 Pa per species (core.termodinamica.cubic_flash).")

    def dominio(self, T, P):
        self._p._dominio(T, P)

    @staticmethod
    def nombre_de(cas):
        """Name of a species: the catalog record, or the light-gas record of PSRK (CO2 is not a catalog species)."""
        from core import catalogo
        from . import psrk_data
        if cas in catalogo.REGISTRO:
            return datos.especie(cas).nombre
        return psrk_data.LIGHT_GASES[cas].name

    def huella(self):
        return self._p.huella_datos()


class PaqueteEOS(pv.PaqueteMezcla):
    """One cubic EOS package over an ordered species list (a drop-in of `PaqueteMezcla`)."""

    def __init__(self, modelo_id, cas, sustituciones=None):
        if modelo_id not in EOS_PAQUETES:
            raise pv.PaqueteNoAplicable(f"{modelo_id!r} is not a cubic EOS package ({', '.join(EOS_PAQUETES)}).")
        if sustituciones:
            raise pv.PaqueteNoAplicable(f"{modelo_id} reads its own pure-component records and does not accept "
                                        "pure-data substitutions.")
        self.id, self.version = modelo_id, VERSION
        self.especies = tuple(cas)
        self.referencia = dict(mz.REFERENCIA)
        self._eos_cache = {}
        self._cache = {}
        self.sistema = None
        full = self._eos(range(len(self.especies)))      # builds (and so validates) the full species set
        self.M = np.array([_masa_molar(c) for c in self.especies], dtype=float)
        lo = max(T_BOUNDS[0], float(full.T_range[0]))
        hi = min(T_BOUNDS[1], float(full.T_range[1]))
        self.T_rango = (lo, hi)
        self.sistema = _SistemaEOS(self)

    # --- construction ------------------------------------------------------------------
    def _eos(self, idx):
        key = tuple(idx)
        if key not in self._eos_cache:
            from core.unifac import FaltaDatoUNIFAC
            from .capa import _ecuacion_estado
            try:
                self._eos_cache[key] = _ecuacion_estado(self.id, tuple(self.especies[i] for i in key))
            except cubic_eos.CubicOutOfScope as e:
                raise pv.PaqueteNoAplicable(f"{self.id}: {e}") from e
            except FaltaDatoUNIFAC as e:
                raise pv.PaqueteNoAplicable(f"{self.id}: {e}") from e
        return self._eos_cache[key]

    def _dominio(self, T, P):
        if not self.T_rango[0] <= T <= self.T_rango[1]:
            raise mz.FueraDeAlcance("fuera_de_dominio", f"T = {T:.6g} K outside the {self.id} window "
                                    f"[{self.T_rango[0]:.6g}, {self.T_rango[1]:.6g}] K (the lower end is the Mathias-Copeman "
                                    "regression range of PSRK, or the ideal-gas cp range of Peng-Robinson).",
                                    T_fuera=True, cause="outside_package_window")
        if not P_BOUNDS[0] <= P <= P_BOUNDS[1]:
            raise mz.FueraDeAlcance("fuera_de_dominio", f"P = {P:.6g} Pa outside the {self.id} window "
                                    f"[{P_BOUNDS[0]:g}, {P_BOUNDS[1]:g}] Pa.", P_fuera=True, cause="outside_package_window")

    def huella_datos(self):
        """Fingerprint of the package, its species records and tolerances (changes if any of them changes)."""
        import dataclasses
        full = self._eos(range(len(self.especies)))
        orden = sorted(range(len(self.especies)), key=lambda k: self.especies[k])
        rec = []
        for k in orden:
            e = full.esp[k]
            rec.append({c: (list(v) if isinstance(v, tuple) else v) for c, v in dataclasses.asdict(e).items()
                        if v is not None and c != "source"})
        extra = {}
        if self.id == PSRK:
            extra = {"mc": np.asarray(full.mc)[orden].tolist(), "Tc": full.Tc[orden].tolist(),
                     "Pc": full.Pc[orden].tolist()}
        else:
            extra = {"Tc": full.Tc[orden].tolist(), "Pc": full.Pc[orden].tolist(), "omega": full.omega[orden].tolist()}
        d = {"paquete": [self.id, self.version], "cas": [self.especies[k] for k in orden], "especies": rec,
             "extra": extra, "referencia": mz.REFERENCIA, "dominio": {"T": list(self.T_rango), "P": list(P_BOUNDS)},
             "tolerancias": {"TOL_TM": cubic_flash.TOL_TM, "TOL_MU": cubic_flash.TOL_MU}}
        return "sha256:" + hashlib.sha256(json.dumps(d, sort_keys=True, default=float).encode()).hexdigest()

    def huella(self):
        return self.huella_datos()

    # --- the state -----------------------------------------------------------------------
    def _build(self, espec, T, P, n, idx, st, anchor=None):
        """EstadoMezcla from a certified cubic flash state `st` over the active species `idx`."""
        nsp = len(self.especies)
        eos = self._eos(idx)
        fases = []
        order = sorted(st["phases"], key=lambda p: (p["kind"] != "vapor", 0))
        nl = 0
        for p in order:
            x_full = np.zeros(nsp)
            x_full[list(idx)] = p["x"]
            mu_full = np.full(nsp, np.nan)
            mu_full[list(idx)] = p["mu"]
            if p["kind"] == "vapor":
                fid = "vapor-1"
            else:
                nl += 1
                fid = f"liquido-{nl}"
            f = mz.FaseMezcla(id=fid, tipo=p["kind"], n=float(p["n"]), x=x_full, h=float(p["h"]), s=float(p["s"]),
                              v=float(p["v"]), g=float(p["g"]), mu=mu_full, M=float(np.sum(x_full * self.M)))
            f._P = P
            fases.append(f)
        e = mz.EstadoMezcla(especificacion=espec, T=float(T), P=float(P), especies=self.especies,
                            n=np.asarray(n, dtype=float), fases=fases)
        res = float(np.max(np.abs(sum(f.n * f.x for f in fases) - n)) / n.sum())
        e.verificaciones["reconstruccion_material"] = (res, 1e-12, "max |sum_a n^a x_i^a - n_i| / n")
        e.verificaciones["equilibrio"] = (float(st["mu_residual"]), cubic_flash.TOL_MU,
                                          "max |ln f_i^V - ln f_i^L| between present phases")
        found = st["tm_min"] is not None and math.isfinite(st["tm_min"])
        # Without another tangent-plane minimum the least value of tm is the trivial one, 0 at the phase itself.
        tm_min = float(st["tm_min"]) if found else 0.0
        e.verificaciones["estabilidad"] = (max(0.0, -tm_min), cubic_flash.TOL_TM,
                                           "-min tm over the non-trivial tangent-plane minima")
        trials = st.get("trials") or []
        kinds = set()
        for w, _ in trials:
            ph = eos.phase(T, P, w)
            kinds.add(cubic_flash._label_single(eos, T, P, w, ph["Z"]))
        e.estabilidad = {"tm_min": tm_min, "pruebas": len(trials),
                         "candidatas": sorted({"vapor", "liquido"} | kinds) if trials else sorted(
                             {f.tipo for f in fases}),
                         "tm_nueva": (tm_min if (len(fases) == 1 and found) else None)}
        return e

    def _active(self, n):
        idx = [i for i in range(len(self.especies)) if n[i] > 0]
        if not idx:
            raise mz.FueraDeAlcance("no_soportado", "The state has no species amount.")
        return idx

    def estado(self, espec, a, b, n, semilla=None, certificar=False):
        n = np.asarray(n, dtype=float)
        if n.shape != (len(self.especies),) or not np.all(np.isfinite(n)) or np.any(n < 0) or not n.sum() > 0:
            raise mz.FueraDeAlcance("no_convergente", "Invalid component inventory.")
        idx = self._active(n)
        eos = self._eos(idx)
        z = n[idx]
        guess = semilla.T if (semilla is not None and getattr(semilla, "T", None)) else None
        try:
            if espec == "TP":
                T, P = float(a), float(b)
                self._dominio(T, P)
                self._check_T(eos, T)
                st = cubic_flash.flash_TP(eos, T, P, z)
            elif espec == "PH":
                P, H = float(a), float(b)
                self._dominio(self.T_rango[0], P)
                st = self._pure_plateau_PH(eos, P, H, z) if len(idx) == 1 else None
                if st is None:
                    st = self._ph_secant(eos, P, H, z, semilla)
                if st is None:
                    st = self._warm(lambda br: cubic_flash.flash_PH(eos, P, H, z, T_bracket=br), guess)
                T = st["T"]
                self._check_T(eos, T)
            elif espec == "UV":
                U, V = float(a), float(b)
                st = self._uv_newton(eos, U, V, z, semilla)
                if st is None:
                    st = self._warm(lambda br: cubic_flash.flash_UV(eos, U, V, z, T_bracket=br), guess)
                T, P = st["T"], st["P"]
                self._check_T(eos, T)
            elif espec == "TV":
                T, V = float(a), float(b)
                self._dominio(T, P_BOUNDS[0])
                self._check_T(eos, T)
                st, P = self._tv(eos, T, V, z)
            elif espec == "UP":
                P, U = float(a), float(b)
                self._dominio(self.T_rango[0], P)
                st, T = self._up(eos, P, U, z)
            else:
                raise ValueError(espec)
        except cubic_eos.CubicOutOfScope as e:
            raise _located(e) from e
        e = self._build(espec, T, P, n, idx, st)
        if len(idx) == 1 and len(e.fases) == 1 and e.estabilidad.get("tm_nueva") is None:
            try:
                e.estabilidad["tm_nueva"] = self._pure_margin(eos, T, P, st)
            except cubic_eos.CubicOutOfScope:
                pass
        self._check_specification(espec, a, b, e)
        self._dominio(e.T, e.P)
        return e

    @staticmethod
    def _check_T(eos, T):
        if hasattr(eos, "check_temperature"):
            eos.check_temperature(T)

    def _warm(self, solve, guess):
        """A narrow T bracket around the previous state first; the default window search when that fails."""
        if guess is not None:
            lo, hi = max(self.T_rango[0], guess - WARM_DT), min(self.T_rango[1], guess + WARM_DT)
            try:
                return solve((lo, hi))
            except cubic_eos.CubicOutOfScope:
                pass
        return solve(None)

    def _pure_saturation_T(self, eos, P):
        """Saturation temperature of a pure species at P (Maxwell construction), or None at or above P_c."""
        if not P < float(eos.Pc[0]):
            return None
        hi = 0.999 * float(eos.Tc[0])
        lo = max(self.T_rango[0], 0.5 * float(eos.Tc[0]))      # the Maxwell Newton is not converged far below T_c
        f = lambda T: cubic_flash.pure_saturation(eos, 0, T)["P"] - P
        try:
            if f(lo) > 0.0 or f(hi) < 0.0:
                return None
            return brentq(f, lo, hi, xtol=1e-12, rtol=1e-14, maxiter=200)
        except cubic_eos.CubicOutOfScope:
            return None

    def _pure_edges(self, eos, P, Tsat):
        """(h_liquid, h_vapour, props_L, props_V) per mole of the saturated pure phases at (Tsat, P)."""
        sat = cubic_flash.pure_saturation(eos, 0, Tsat)
        x = np.array([1.0])
        pl = eos.molar_props(Tsat, P, x, sat["ZL"])
        pv_ = eos.molar_props(Tsat, P, x, sat["ZV"])
        lnphi_gap = abs(float(eos.ln_phi_Z(Tsat, P, x, sat["ZL"])[0] - eos.ln_phi_Z(Tsat, P, x, sat["ZV"])[0]))
        return pl, pv_, lnphi_gap

    def _pure_plateau_PH(self, eos, P, H, z):
        """The pure-component two-phase state at (P, H): T = Tsat(P), vapour fraction from the enthalpy lever
        rule. cubic_flash's TP flash cannot split a pure species (every state at Tsat is one root), so its PH
        search returns a one-phase state on the plateau; the package resolves the plateau itself, from the same
        Maxwell construction as `pure_saturation`. None outside the plateau (the ordinary flash applies)."""
        Tsat = self._pure_saturation_T(eos, P)
        if Tsat is None:
            return None
        n = float(z[0])
        pl, pv_, gap = self._pure_edges(eos, P, Tsat)
        q = (H / n - pl["h"]) / (pv_["h"] - pl["h"])
        if not 1e-12 < q < 1.0 - 1e-12:
            return None
        x = np.array([1.0])
        return {"phases": [dict(kind="vapor", n=n * q, x=x, **pv_), dict(kind="liquido", n=n * (1.0 - q), x=x, **pl)],
                "tm_min": None, "mu_residual": gap, "trials": [], "T": Tsat, "P": P}

    def _pure_margin(self, eos, T, P, st):
        """Positive distance of a one-phase pure state from its saturation enthalpy, per RT: the phase-appearance
        margin the integrator drives to zero (a pure species has no other tangent-plane minimum)."""
        Tsat = self._pure_saturation_T(eos, P)
        if Tsat is None:
            return None
        pl, pv_, _ = self._pure_edges(eos, P, Tsat)
        p = st["phases"][0]
        gap = (pl["h"] - p["h"]) if p["kind"] == "liquido" else (p["h"] - pv_["h"])
        return gap / (cubic_eos.R * T) if gap > 0.0 else None

    def _check_specification(self, espec, a, b, e):
        """No silent wrong state: the published state must meet the specification it was asked for."""
        tol = 1e-8
        if espec == "PH":
            err, ref = abs(e.H - b), max(abs(b), 1.0)
        elif espec == "UV":
            err, ref = max(abs(e.U - a) / max(abs(a), 1.0), abs(e.V - b) / abs(b)), 1.0
        elif espec == "TV":
            err, ref = abs(e.V - b) / abs(b), 1.0
        elif espec == "UP":
            err, ref = abs(e.U - b), max(abs(b), 1.0)
        else:
            return
        if err > tol * ref:
            raise mz.FueraDeAlcance(
                "no_soportado", f"The {espec} specification ({a:.6g}, {b:.6g}) is not met by a state of {self.id} "
                f"(residual {err / ref:.3g} relative): a pure species inside its two-phase region needs a PH "
                "specification in this package.", cause="specification_not_met", especificacion=espec)

    def _ph_secant(self, eos, P, H, z, seed):
        """Warm PH: secant on T from the previous state of the same volume, each step one certified TP flash
        (about half the flashes of the bracketed search). H(T) at fixed P is increasing, so an iterate that
        leaves the temperature window, a non-increasing secant or a rejected probe returns None, and so do a
        pure-component plateau (H jumps at the saturation temperature) and a run that has not converged to
        1e-10 K in 12 steps; the caller then runs the bracketed flash_PH. It never changes what is published,
        only the cost."""
        if seed is None or not getattr(seed, "T", None):
            return None
        scale = max(abs(H), 1.0)
        ntot = float(np.sum(z))

        def residual(T):
            self._check_T(eos, T)
            st = cubic_flash.flash_TP(eos, T, P, z)
            return sum(p["n"] * p["h"] for p in st["phases"]) - H, st

        try:
            T0 = float(seed.T)
            r0, st0 = residual(T0)
            T1 = T0 - r0 / (20.0 * mz.R * ntot)               # first step: a liquid-like heat capacity
            for _ in range(12):
                if not self.T_rango[0] < T1 < self.T_rango[1]:
                    return None
                r1, st1 = residual(T1)
                if abs(T1 - T0) < 1e-10 and abs(r1) < 1e-9 * scale:
                    st1["T"], st1["P"] = T1, P
                    return st1
                slope = (r1 - r0) / (T1 - T0) if T1 != T0 else 0.0
                if not slope > 0.0:
                    return None
                T0, r0 = T1, r1
                T1 = T1 - r1 / slope
            return None
        except (cubic_eos.CubicOutOfScope, ValueError, OverflowError):
            return None

    def _uv_newton(self, eos, U, V, z, seed):
        """Warm UV: damped Newton on (T, ln P) from the previous state of the same volume, with the Jacobian by
        forward differences of the certified TP flash. Returns the certified state at the root, or None when the
        seed is missing, is not single-phase, or the iteration does not converge to 1e-11 in U and V within 8
        steps (a pure-component plateau, a phase change or a rejected probe): the caller then runs the bracketed flash_UV, so this path
        never changes what is published, only the cost."""
        if seed is None or not getattr(seed, "T", None) or len(seed.fases) != 1:
            return None         # two-phase (T, P) is nearly dependent: the Newton path stays linear there
        scale_U = max(abs(U), 1.0)

        def residual(T, lnP):
            st = cubic_flash.flash_TP(eos, T, math.exp(lnP), z)
            u = sum(p["n"] * p["u"] for p in st["phases"])
            v = sum(p["n"] * p["v"] for p in st["phases"])
            return np.array([(u - U) / scale_U, math.log(v / V)]), st

        def jacobian(T, lnP, r):
            hT, hP = 1e-2, 1e-4
            self._check_T(eos, T + hT)
            rT, _ = residual(T + hT, lnP)
            rP, _ = residual(T, lnP + hP)
            return np.column_stack([(rT - r) / hT, (rP - r) / hP])

        try:
            T, lnP = float(seed.T), math.log(float(seed.P))
            r, st = residual(T, lnP)
            for _ in range(8):
                if np.max(np.abs(r)) < 1e-11:
                    break
                dx = np.linalg.solve(jacobian(T, lnP, r), -r)
                step, moved = 1.0, False
                while step > 1e-3:
                    Tn, lnPn = T + step * dx[0], lnP + step * dx[1]
                    if self.T_rango[0] < Tn < self.T_rango[1] and math.log(P_BOUNDS[0]) < lnPn < math.log(P_BOUNDS[1]):
                        self._check_T(eos, Tn)
                        rn, stn = residual(Tn, lnPn)
                        if np.max(np.abs(rn)) < np.max(np.abs(r)):
                            T, lnP, r, st, moved = Tn, lnPn, rn, stn, True
                            break
                    step *= 0.5
                if not moved:
                    return None
            if np.max(np.abs(r)) >= 1e-11:
                return None
        except (cubic_eos.CubicOutOfScope, np.linalg.LinAlgError, ValueError, OverflowError):
            return None
        st["T"], st["P"] = T, math.exp(lnP)
        return st

    def _tv(self, eos, T, V, z):
        """(state, P): ln P root of V(T, P) = V at fixed T (V decreases with P)."""
        lnP = np.linspace(math.log(P_BOUNDS[0]), math.log(P_BOUNDS[1]), 25)
        cache = {}

        def g(x):
            if x not in cache:
                st = cubic_flash.flash_TP(eos, T, math.exp(x), z)
                cache[x] = (math.log(sum(p["n"] * p["v"] for p in st["phases"]) / V), st)
            return cache[x][0]
        prev = None
        for x in lnP:
            val, cause = cubic_flash._probe(lambda: g(x))
            if val is None:
                prev = None
                continue
            if val == 0.0:
                return cache[x][1], math.exp(x)
            if prev is not None and prev[1] * val < 0.0:
                root = brentq(g, prev[0], x, xtol=1e-14, rtol=1e-14, maxiter=200)
                return flash_at(eos, T, math.exp(root), z), math.exp(root)
            prev = (x, val)
        raise cubic_eos.CubicOutOfScope(
            f"TV flash at T = {T:.6g} K: no pressure in [{P_BOUNDS[0]:g}, {P_BOUNDS[1]:g}] Pa gives V = {V:.6g} m3 "
            "on an evaluable state.", cause="outside_bracket", T=T, V=V, z=list(map(float, z)))

    def _up(self, eos, P, U, z):
        """(state, T): T root of U(T, P) = U at fixed P, on the evaluable windows of a temperature grid."""
        lo, hi = max(self.T_rango[0], T_BOUNDS[0]), min(self.T_rango[1], T_BOUNDS[1])
        grid = np.geomspace(lo, hi, 41)
        cache = {}

        def f(T):
            if T not in cache:
                self._check_T(eos, T)
                st = cubic_flash.flash_TP(eos, T, P, z)
                cache[T] = (sum(p["n"] * p["u"] for p in st["phases"]) - U, st)
            return cache[T][0]
        prev = None
        for T in grid:
            val, cause = cubic_flash._probe(lambda: f(float(T)))
            if val is None:
                prev = None
                continue
            if prev is not None and prev[1] * val < 0.0:
                root = brentq(f, prev[0], float(T), xtol=1e-11, rtol=1e-14, maxiter=200)
                return flash_at(eos, root, P, z), root
            prev = (float(T), val)
        raise cubic_eos.CubicOutOfScope(
            f"UP flash at P = {P:.6g} Pa: U = {U:.6g} J is not bracketed by an evaluable state in "
            f"[{lo:.6g}, {hi:.6g}] K.", cause="outside_bracket", P=P, U=U, z=list(map(float, z)))

    # --- the common-path contract -----------------------------------------------------------
    def certify_state(self, state):
        """Fresh certification of a located state without solving its phase amounts again: equal fugacities of
        the present phases and a fresh tangent-plane search from their composition."""
        T, P = state.T, state.P
        self._dominio(T, P)
        n = np.asarray(state.n, dtype=float)
        if tuple(state.especies) != self.especies or not np.all(np.isfinite(n)) or np.any(n < 0) or not n.sum() > 0:
            raise mz.FueraDeAlcance("no_convergente", "Invalid component inventory in the located state.")
        idx = self._active(n)
        eos = self._eos(idx)
        phases = []
        for f in state.fases:
            x = np.asarray(f.x, dtype=float)
            if (f.tipo not in ("liquido", "vapor") or not np.isfinite(f.n) or f.n <= 0 or x.shape != n.shape
                    or not np.all(np.isfinite(x)) or np.any(x < 0) or abs(x.sum() - 1.0) > 1e-12
                    or np.any(x[n == 0] != 0) or np.any(x[idx] <= 0)):
                raise mz.FueraDeAlcance("no_convergente", "Invalid phase amount or composition in the located state.")
            phases.append((f.tipo, f.n, x[idx]))
        if not phases:
            raise mz.FueraDeAlcance("no_convergente", "The located state has no present phase.")
        try:
            out, lnf = [], []
            for tipo, nf, x in phases:
                ph = eos.phase(T, P, x, root="vapor" if tipo == "vapor" else "liquid")
                pr = eos.molar_props(T, P, x, ph["Z"])
                out.append(dict(kind=tipo, n=nf, x=x, **pr))
                lnf.append(np.log(x) + ph["lnphi"])
            res_mu = max((float(np.max(np.abs(l - lnf[0]))) for l in lnf[1:]), default=0.0)
            trials, _ = cubic_flash.stability(eos, T, P, phases[0][2] / phases[0][2].sum())
            fresh = [t for t in trials if all(np.max(np.abs(t[0] - ph[2])) > cubic_flash.TOL_SAME for ph in phases)]
            tm_min = min((t[1] for t in fresh), default=math.inf)
        except cubic_eos.CubicOutOfScope as e:
            raise _located(e) from e
        st = {"phases": out, "tm_min": tm_min, "mu_residual": res_mu, "trials": fresh}
        e = self._build(state.especificacion, T, P, n, idx, st)
        if res_mu > cubic_flash.TOL_MU or tm_min < -cubic_flash.TOL_TM or not (math.isfinite(tm_min) or len(fresh) == 0):
            raise mz.FueraDeAlcance("no_convergente", "The located event state fails fresh thermodynamic "
                                    "certification.")
        return e

    def transporte_TP(self, T, P, x):
        clave = (T, P, tuple(np.round(np.asarray(x, dtype=float), 15)))
        if clave not in self._cache:
            e = self.estado("TP", T, P, np.asarray(x, dtype=float))
            n = float(np.sum(e.n))
            self._cache[clave] = (e.H / n, e.S / n)
            if len(self._cache) > 5000:
                self._cache.clear()
        return self._cache[clave]


def flash_at(eos, T, P, z):
    """The certified TP state at the located root (fresh flash, never a probe) with its T and P."""
    st = cubic_flash.flash_TP(eos, T, P, z)
    st["T"], st["P"] = T, P
    return st


def capacidades():
    """Additive capability entries (`paquetesEos` of the v2 assembly capabilities): the EOS packages a dynamic
    volume may select. The species list is the set that has a pure-component record; a species or a pair
    without the data the package needs is a located rejection when the volume's package is built."""
    from core import catalogo
    from . import psrk_data
    catalog = sorted(catalogo.REGISTRO)
    light = sorted(psrk_data.LIGHT_GASES)
    comb = [
        {"id": "una_fase", "nombre": "one phase (liquid-like or vapour-like root)", "publicada": True,
         "evidencia": "contrastada", "motivo": "TP/PH/UV closures equal the layer closures of the same package"},
        {"id": "liquido_vapor", "nombre": "liquid-vapour", "publicada": True, "evidencia": "cualitativa",
         "motivo": "certified by equal fugacities and tangent-plane stability; parameters are not fitted to the "
                   "system (k_ij = 0 for Peng-Robinson; PSRK as published)"},
        {"id": "liquido_liquido", "nombre": "liquid-liquid and three-phase states", "publicada": False,
         "evidencia": "sin_modelo", "motivo": "the package has one vapour and one liquid candidate: such a state is "
                                              "a located rejection, never published as another phase set"},
        {"id": "solido", "nombre": "solid", "publicada": False, "evidencia": "sin_modelo",
         "motivo": "no solid model in the EOS packages"}]
    limits = ["a certified liquid-liquid split or third phase stops the run with a located cause",
              "PSRK: T not below the Mathias-Copeman regression range of a subcritical species; light gases only "
              "within their ideal-gas cp record (CO2 50-1000 K)",
              "liquid-only species (acetic acid) are not admitted: the EOS has no liquid-only phase set",
              "pure-data substitutions are not accepted: the packages read their own records"]
    out = []
    for pid in EOS_PAQUETES:
        out.append({"modelo": {"id": pid, "version": VERSION}, "operaciones": ["TP", "PH", "UP", "UV", "TV"],
                    "fases": ["liquido", "vapor"], "combinaciones": [dict(c) for c in comb], "dinamica": True,
                    "componentesCAS": sorted(set(catalog) | (set(light) if pid == PSRK else set())),
                    "dominio": {"T": [T_BOUNDS[0], T_BOUNDS[1]], "P": [P_BOUNDS[0], P_BOUNDS[1]]},
                    "limites": list(limits)})
    return out
