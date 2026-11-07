"""
PSRK: Soave-Redlich-Kwong with a UNIFAC excess-Gibbs mixing rule (F8b, 6 November 2026).

Why PSRK and not VTPR. Both carry UNIFAC into an equation of state, so equilibria at elevated pressure and with
supercritical gases follow from group contributions instead of fitted binary parameters (the UNIFAC-priority
route to high pressure; NRTL is not extended). PSRK (Holderbaum and Gmehling, Fluid Phase Equilib. 70 (1991)
251; Fischer and Gmehling, Fluid Phase Equilib. 121 (1996) 185; Horstmann, Jabloniec, Krafczyk, Fischer and
Gmehling, Fluid Phase Equilib. 227 (2005) 157) needs only T_c, P_c, a vapour-pressure record and its own UNIFAC
table, which thermo 0.6.1 distributes with the DDBST PSRK group assignments, gas groups (CO2, CH4, N2, H2, ...)
included. VTPR also needs a volume translation and Twu alpha parameters per species that are not in the
repository's data. PSRK is therefore the variant that can be derived here from published data alone.

The single constitutive function. As in core/termodinamica/cubic_eos.py, every property follows from

    F(T, V, n) = A^r / (R T) = -n ln(1 - B/V) - n alpha_m(T, x) ln(1 + B/V),       x = n / n,

the SRK residual Helmholtz function (d1 = 1, d2 = 0 of the generic two-parameter cubic) with B = sum n_i b_i
(linear) and the dimensionless attraction alpha_m = a / (b R T). Its pressure is P = RT/(v - b) - a/(v (v + b)).
Omega_a, Omega_b and Z_c are not posed: they are solved from (dP/dV)_T = (d2P/dV2)_T = 0
(`cubic_eos.critical_constants(1, 0)`; the closed forms 1/(9 (2^(1/3) - 1)) and (2^(1/3) - 1)/3 are checked in
the tests). a_i = Omega_a R^2 T_c,i^2 / P_c,i alpha_i(T), b_i = Omega_b R T_c,i / P_c,i.

Mixing rule (PSRK). At a fixed reduced liquid volume u = v/b the SRK residual Gibbs energy per mole of a pure
fluid is q(alpha) = -1 - ln(u - 1) - alpha ln((u + 1)/u), linear in alpha with slope A1 = -ln((u + 1)/u). PSRK
fixes the zero-pressure reference at u = 1.1 (Holderbaum and Gmehling 1991), so A1 = -ln(2.1/1.1) = -0.6466272
(published rounded as -0.64663; derived here, not posed). Equating g^E of the EOS at that reference,
g^E/RT = q(alpha_m) - sum_i x_i q(alpha_i) - sum_i x_i ln(b / b_i) (the combinatorial-like co-volume term of
MHV1, with b linear in x), to UNIFAC gives

    alpha_m = sum_i x_i alpha_i + (1/A1) [ g^E(T, x)/RT + sum_i x_i ln(b / b_i) ],    alpha_i = a_i / (b_i R T).

g^E is UNIFAC with the PSRK table (original UNIFAC equations, Staverman-Guggenheim combinatorial z = 10,
Psi_mn = exp(-(a_mn + b_mn T + c_mn T^2)/T)), evaluated by the repository's UNIFAC implementation
(core/unifac.LiquidoUNIFAC; only the table differs). It is evaluated at the system T for both phases.

Chain rule (derived here, checked against a complex step of F in the tests). With nalpha = n alpha_m,

    d(n alpha_m)/dn_i = alpha_i + (1/A1) [ ln gamma_i + ln(b/b_i) + b_i/b - 1 ]           (= abar_i),
    dF/dn_i = -ln(1 - B/V) + n b_i/(V - B) - abar_i ln(1 + B/V) - n alpha_m b_i/(V + B),
    dF/dV   = -n B/(V (V - B)) + n alpha_m B/(V (V + B)),
    ln phi_i = dF/dn_i - ln Z,      P = -R T dF/dV + n R T / V.

dF/dT (for h^r) is a complex step of F in T on real states. Every other operation of the cubic package that is
written against F (pressure, the (T, V) Hessian, d ln phi/dn, stability, saturation points, Heidemann-Khalil
critical points) is reused unchanged: `PSRKMixture` supplies the same methods.

Alpha function (Mathias and Copeman, Fluid Phase Equilib. 13 (1983) 91, as in PSRK):

    sqrt(alpha_i) = 1 + c1 t + c2 t^2 + c3 t^3,   t = 1 - sqrt(T/T_c,i),   T < T_c,i,
    sqrt(alpha_i) = 1 + c1 t,                                              T >= T_c,i.

PSRK regresses (c1, c2, c3) on vapour pressures (Horstmann et al. 2005). Here they are re-regressed by the same
method on each species' own vapour-pressure record (core/termodinamica/psrk_data.py), so the package reproduces the
catalog's saturation line; the published PSRK compound constants are not used (for CO2 the regressed alpha agrees
with them within 0.25 %, tested). The regression is linear: at each temperature of the record the attraction alpha*(T) that makes the pure
SRK fluid saturate at Psat(T) is solved exactly (Maxwell, ln phi^L = ln phi^V), and sqrt(alpha*) - 1 is fitted
by least squares in (t, t^2, t^3) on [max(T_min, 0.45 T_c), 0.995 T_c] (48 points). The tests check the fitted
Psat against the record and the CO2 constants against the published PSRK values.

Data provenance. The PSRK group-interaction table is thermo 0.6.1's 'PSRK interaction parameters.tsv' (its
sha256 is recorded in the identity). It was not checked entry by entry against the appendix of Horstmann et al.
2005; the entries used are listed by `PSRKUnifac.interactions_used`, and exchanging the two CO2-OH directions makes
CO2 + ethanol worse (+31 % to +64 %, independent review), which supports the table's orientation.

Declared coverage (rejections are located `CubicOutOfScope`, never defaults):
  - a species without a PSRK pure record (`no_pure_record`) or PSRK group assignment (`missing_group_assignment`);
  - a pair of PSRK main groups without published interaction parameters (`missing_interaction`);
  - a temperature below the alpha regression range of a species subcritical there (`alpha_below_fit_range`);
  - a saturation point that converges to the trivial solution y = x, i.e. beyond the mixture's critical point
    at that T (`trivial_solution`), or whose incipient phase is denser than the feed, i.e. past the critical
    composition of the isotherm (`past_critical_point`), or whose phases differ by less than 1e-3 in mole fraction
    (`near_critical_unresolved`: the bubble and dew branches are not separated there); a saturation point whose
    phases fail the certificate (`not_certified`); a Newton failure from the start and from damped probes
    (`not_converged`, with the probes);
  - a composition with no positive-pressure critical point (`no_critical_point_in_window`, with the dropped
    roots). For CO2 + methanol and CO2 + ethanol the PSRK locus leaving the alcohol is interrupted at
    x_CO2 ~ 0.79-0.89 (methanol) and ~ 0.83-0.85 (ethanol), while the measured lines are continuous.
No volume translation (densities carry the SRK error; equilibria are unchanged by a constant translation in PSRK's
mixing-rule form, which uses b only). k_ij is not used (PSRK is predictive).
"""

from __future__ import annotations

import hashlib
import math
import os
from functools import lru_cache

import numpy as np
from scipy.optimize import brentq

from core import mezclas_datos as datos
from core.termodinamica import psrk_data
from core.termodinamica.cubic_eos import CS_H, R, CubicOutOfScope, PengRobinsonMixture, critical_constants
from core.unifac import FaltaDatoUNIFAC, LiquidoUNIFAC

U_REF = 1.1                      # PSRK zero-pressure reference v/b (Holderbaum and Gmehling 1991)
A1 = -math.log((U_REF + 1.0) / U_REF)     # = -0.6466272, published rounded as -0.64663
SRK_D1, SRK_D2 = 1.0, 0.0
FIT_TR_LO, FIT_TR_HI, FIT_N = 0.45, 0.995, 48
TOL_LNK_TRIVIAL = 1e-6
TOL_CERT = 1e-9
TOL_NEAR_CRITICAL = 1e-3     # |y - x| below which a saturation point is not published

_PSRK_TABLE = {}


# --- the PSRK UNIFAC table on the repository's UNIFAC implementation ------------------------------------------
def psrk_table():
    """PSRK subgroups, interactions (a, b, c) and provenance, loaded once from thermo 0.6.1."""
    if _PSRK_TABLE:
        return _PSRK_TABLE
    with datos.CARGA_DATOS:
        if _PSRK_TABLE:
            return _PSRK_TABLE
        import thermo
        import thermo.unifac as tu
        tu.load_unifac_ip()
        tu.load_group_assignments_DDBST()
        sub = {int(k): (int(g.main_group_id), float(g.R), float(g.Q), str(g.group)) for k, g in tu.PSRKSG.items()}
        inter = {(int(m), int(n)): tuple(float(v) for v in vals) for m, d in tu.PSRKIP.items() for n, vals in d.items()}
        path = os.path.join(os.path.dirname(tu.__file__), "Phase Change", "PSRK interaction parameters.tsv")
        h = hashlib.sha256(open(path, "rb").read()).hexdigest()
        _PSRK_TABLE.update(sub=sub, inter=inter, assign=tu.UNIFAC_group_assignment_DDBST, ident={
            "variante": "psrk",
            "fuente_interacciones": f"thermo {thermo.__version__}: 'PSRK interaction parameters.tsv' (DDBST PSRK, "
                                    "Horstmann et al., Fluid Phase Equilib. 227 (2005) 157)",
            "sha256_interacciones": h,
            "fuente_subgrupos": f"thermo {thermo.__version__}: PSRKSG",
            "fuente_asignaciones": f"thermo {thermo.__version__}: 'DDBST UNIFAC assignments.tsv' (PSRK model)"})
    return _PSRK_TABLE


def psrk_groups(cas):
    """PSRK subgroup counts of a species: declared on its psrk_data record, else the DDBST PSRK assignment."""
    rec = psrk_data.record(cas)
    t = psrk_table()
    if rec.groups is not None:
        groups = dict(rec.groups)
    else:
        with datos.CARGA_DATOS:
            try:
                groups = t["assign"](cas, "PSRK")
            except Exception:
                groups = None
        if not groups:
            raise CubicOutOfScope(f"No PSRK group assignment for {cas} in the DDBST table.",
                                  cause="missing_group_assignment", cas=cas)
    for k in groups:
        if int(k) not in t["sub"]:
            raise CubicOutOfScope(f"PSRK subgroup {k} of {cas} is not in the PSRK table.",
                                  cause="missing_group_assignment", cas=cas, subgroup=int(k))
    return {int(k): int(v) for k, v in groups.items()}


class PSRKUnifac(LiquidoUNIFAC):
    """UNIFAC with the PSRK table. Construction mirrors LiquidoUNIFAC on that table; the evaluation methods
    (Psi, ln Gamma, combinatorial, ln gamma, g^E) are inherited unchanged ('psrk' uses the original-UNIFAC
    combinatorial branch)."""

    def __init__(self, cas, groups):
        t = psrk_table()
        self.variante = "psrk"
        self.rango_T = None
        self.nombre = "UNIFAC PSRK (DDBST published, distributed with thermo)"
        self.cas = tuple(cas)
        self.asignaciones = {c: dict(groups[c]) for c in self.cas}
        grupos = sorted({k for c in self.cas for k in groups[c]})
        self.subgrupos = tuple(grupos)
        G = len(grupos)
        nu = np.zeros((len(self.cas), G))
        for i, c in enumerate(self.cas):
            for k, v in groups[c].items():
                nu[i, grupos.index(k)] = v
        main = [t["sub"][k][0] for k in grupos]
        A, B, C = np.zeros((G, G)), np.zeros((G, G)), np.zeros((G, G))
        used = {}
        for a in range(G):
            for b in range(G):
                m, n = main[a], main[b]
                if m == n:
                    continue
                if (m, n) not in t["inter"]:
                    raise CubicOutOfScope(
                        f"No published PSRK interaction between main groups {m} and {n} "
                        f"(subgroups {grupos[a]} and {grupos[b]}).", cause="missing_interaction",
                        main_groups=[m, n], species=[c for c in self.cas
                                                     if grupos[a] in groups[c] or grupos[b] in groups[c]])
                A[a, b], B[a, b], C[a, b] = t["inter"][(m, n)]
                used[f"{m}-{n}"] = t["inter"][(m, n)]
        self.interactions_used = dict(sorted(used.items()))
        self._main = tuple(main)
        Rk = np.array([t["sub"][k][1] for k in grupos])
        Qk = np.array([t["sub"][k][2] for k in grupos])
        for arr in (nu, Rk, Qk, A, B, C):
            arr.setflags(write=False)
        self._nu, self._R, self._Q, self._A, self._B, self._C = nu, Rk, Qk, A, B, C
        self._r = nu @ Rk
        self._q = nu @ Qk
        self._r.setflags(write=False)
        self._q.setflags(write=False)
        self._cache_T = None

    def identidad(self):
        t = psrk_table()
        return {"variante": "psrk", "datos": t["ident"],
                "asignaciones": {c: {str(g): n for g, n in sorted(self.asignaciones[c].items())} for c in sorted(self.cas)},
                "subgrupos": {str(g): list(t["sub"][g][:3]) for g in self.subgrupos},
                "interacciones": self.interactions_used}

    def subconjunto(self, idx):
        cas = [self.cas[i] for i in idx]
        return PSRKUnifac(cas, {c: self.asignaciones[c] for c in cas})


# --- pure SRK and the Mathias-Copeman regression ---------------------------------------------------------------
def srk_constants():
    return critical_constants(SRK_D1, SRK_D2)


def _srk_pure_roots(A, B):
    """Real roots Z > B of Z^3 - Z^2 + (A - B - B^2) Z - A B = 0, ascending."""
    r = np.roots([1.0, -1.0, A - B - B * B, -A * B])
    return sorted(float(z.real) for z in r if abs(z.imag) <= 1e-10 * max(1.0, abs(z.real)) and z.real > B)


def _srk_pure_lnphi(Z, A, B):
    return Z - 1.0 - math.log(Z - B) - A / B * math.log(1.0 + B / Z)


def _alpha_at_saturation(Tc, Pc, T, P):
    """alpha such that the pure SRK fluid at (T, P) has equal fugacities on its liquid and vapour roots."""
    oa, ob, zc = srk_constants()
    Bp = ob * (P / Pc) / (T / Tc)
    # A' = alpha * Omega_a (P/Pc)/(T/Tc)^2 ; g(alpha) = ln phi^L - ln phi^V, signed +1/-1 where one root remains
    k = oa * (P / Pc) / (T / Tc) ** 2

    def g(alpha):
        zs = _srk_pure_roots(alpha * k, Bp)
        if len(zs) < 2:
            return 1.0 if zs[-1] > zc else -1.0
        return _srk_pure_lnphi(zs[0], alpha * k, Bp) - _srk_pure_lnphi(zs[-1], alpha * k, Bp)
    lo, hi = 0.2, 20.0
    return brentq(g, lo, hi, xtol=1e-15, rtol=1e-15, maxiter=400)


@lru_cache(maxsize=None)
def mathias_copeman(cas):
    """(c1, c2, c3, T_fit_lo, T_fit_hi, max |ln alpha_fit - ln alpha*|) regressed on the species' record."""
    rec = psrk_data.record(cas)
    lo = max(rec.T_min, FIT_TR_LO * rec.Tc)
    Ts = np.linspace(lo, FIT_TR_HI * rec.Tc, FIT_N)
    y = np.array([math.sqrt(_alpha_at_saturation(rec.Tc, rec.Pc, T, rec.psat(T))) - 1.0 for T in Ts])
    t = 1.0 - np.sqrt(Ts / rec.Tc)
    M = np.column_stack([t, t ** 2, t ** 3])
    c, *_ = np.linalg.lstsq(M, y, rcond=None)
    dev = float(np.max(np.abs(2 * np.log((1 + M @ c) / (1 + y)))))
    return float(c[0]), float(c[1]), float(c[2]), float(lo), float(Ts[-1]), dev


# --- the mixture ----------------------------------------------------------------------------------------------
class PSRKMixture(PengRobinsonMixture):
    """PSRK over an ordered list of species with PSRK records. Reuses the generic cubic-package methods
    (ln_phi_Z, phase, hessian_TV, dlnphi_dn, residual_TP, phase_identification) of PengRobinsonMixture,
    which are written against F and its gradient only; z_roots, F and gradient are the SRK/PSRK ones."""

    def __init__(self, cas):
        self.cas = tuple(cas)
        self.nc = len(self.cas)
        self.records = [psrk_data.record(c) for c in self.cas]
        self.Tc = np.array([r.Tc for r in self.records])
        self.Pc = np.array([r.Pc for r in self.records])
        self.omega = np.array([-math.log10(r.psat(0.7 * r.Tc) / r.Pc) - 1.0 for r in self.records])
        mc = [mathias_copeman(c) for c in self.cas]
        self.mc = np.array([m[:3] for m in mc])
        self.T_fit_lo = np.array([m[3] for m in mc])
        oa, ob, self.Zc = srk_constants()
        self.ac = oa * R ** 2 * self.Tc ** 2 / self.Pc
        self.b = ob * R * self.Tc / self.Pc
        self.kij = np.zeros((self.nc, self.nc))
        self.gE = PSRKUnifac(self.cas, {c: psrk_groups(c) for c in self.cas})
        # ideal-gas part: the catalog species' own record, or the light gas's caloric record (psrk_data)
        self.esp = [datos.especie(c) if c not in psrk_data.LIGHT_GASES else psrk_data.ideal_gas_record(c)
                    for c in self.cas]
        self.T_range = (float(np.max(self.T_fit_lo)), math.inf)

    # --- temperature functions -------------------------------------------------
    def alpha_pure(self, T):
        """alpha_i = a_i / (b_i R T), complex-safe in T."""
        t = 1.0 - np.sqrt(T / self.Tc)
        c1, c2, c3 = self.mc[:, 0], self.mc[:, 1], self.mc[:, 2]
        sub = np.real(T) < self.Tc
        s = 1.0 + c1 * t + np.where(sub, c2 * t ** 2 + c3 * t ** 3, 0.0)
        return self.ac * s ** 2 / (self.b * R * T)

    def alpha_mix(self, T, n):
        n = np.asarray(n)
        ntot = np.sum(n)
        x = n / ntot
        b = np.dot(x, self.b)
        return np.dot(x, self.alpha_pure(T)) + (self.gE.gE_RT(T, x) + np.dot(x, np.log(b / self.b))) / A1

    def a_matrix(self, T):                       # not used by PSRK (no quadratic mixing)
        raise CubicOutOfScope("PSRK has no a_ij matrix: the attraction comes from the g^E mixing rule.")

    def check_temperature(self, T):
        """Reject T below the alpha regression range of a species that is subcritical at T."""
        bad = [(self.cas[i], float(self.T_fit_lo[i])) for i in range(self.nc) if T < self.T_fit_lo[i]]
        if bad:
            raise CubicOutOfScope(
                f"T = {T:.6g} K is below the Mathias-Copeman regression range of " + ", ".join(
                    f"{c} (from {t:.6g} K)" for c, t in bad) + ".", cause="alpha_below_fit_range", T=T,
                species=[c for c, _ in bad], T_fit_lo=[t for _, t in bad])

    # --- the residual Helmholtz function --------------------------------------
    def F(self, T, V, n):
        n = np.asarray(n)
        ntot = np.sum(n)
        B = np.dot(n, self.b)
        return -ntot * np.log(1 - B / V) - ntot * self.alpha_mix(T, n) * np.log(1 + B / V)

    def gradient(self, T, V, n):
        """(F_n_i, F_V, F_T); complex-safe in V and n. F_T (complex step of F in T) is returned for real states
        only, NaN otherwise (it is not needed by the composition/volume Hessian)."""
        n = np.asarray(n)
        ntot = np.sum(n)
        x = n / ntot
        B = np.dot(n, self.b)
        b = B / ntot
        ai = self.alpha_pure(T)
        lng = self.gE.lngamma(T, x)
        am = np.dot(x, ai) + (np.sum(x * lng) + np.dot(x, np.log(b / self.b))) / A1
        abar = ai + (lng + np.log(b / self.b) + self.b / b - 1.0) / A1
        Fni = -np.log(1 - B / V) + ntot * self.b / (V - B) - abar * np.log(1 + B / V) - ntot * am * self.b / (V + B)
        FV = -ntot * B / (V * (V - B)) + ntot * am * B / (V * (V + B))
        if np.iscomplexobj(n) or np.iscomplexobj(V) or isinstance(V, complex):
            FT = np.nan
        else:
            FT = float(np.imag(self.F(T + 1j * CS_H * T, V, n)) / (CS_H * T))
        return Fni, FV, FT

    def z_roots(self, T, P, x):
        x = np.asarray(x, dtype=float)
        x = x / x.sum()
        Bm = float(np.dot(x, self.b)) * P / (R * T)
        Am = float(np.real(self.alpha_mix(T, x))) * Bm
        coef = np.array([1.0, -1.0, Am - Bm - Bm * Bm, -Am * Bm])
        out = []
        for z in sorted(float(r.real) for r in np.roots(coef)
                        if abs(r.imag) <= 1e-9 * max(1.0, abs(r.real)) and r.real > Bm):
            for _ in range(8):
                fz, dz = np.polyval(coef, z), np.polyval(np.polyder(coef), z)
                if dz == 0:
                    break
                step = fz / dz
                z -= step
                if abs(step) < 1e-15 * z:
                    break
            if z > Bm and not any(abs(z - o) < 1e-10 * z for o in out):
                out.append(z)
        if not out:
            raise CubicOutOfScope(f"No volume root above the co-volume at T = {T:.6g} K, P = {P:.6g} Pa.")
        return out

    def molar_props(self, T, P, x, Z):
        out = [e.cas for e in self.esp if isinstance(e, psrk_data.IdealGasRecord)
               and not e.T_cp[0] <= float(np.real(T)) <= e.T_cp[1]]
        if out:
            raise CubicOutOfScope(f"T = {float(np.real(T)):.6g} K is outside the ideal-gas cp record of {out}.",
                                  cause="outside_ideal_gas_range", T=float(np.real(T)), species=out)
        return super().molar_props(T, P, x, Z)


# --- operations -------------------------------------------------------------------------------------------------
def pure_saturation(cas, T):
    """Saturation pressure of one species in PSRK (pure SRK with its Mathias-Copeman alpha), T < T_c."""
    rec = psrk_data.record(cas)
    if not T < rec.Tc:
        raise CubicOutOfScope("No saturation above the critical temperature.", cause="supercritical", T=T)
    c1, c2, c3, *_ = mathias_copeman(cas)
    t = 1.0 - math.sqrt(T / rec.Tc)
    alpha = (1.0 + c1 * t + c2 * t * t + c3 * t ** 3) ** 2
    oa, ob, zc = srk_constants()

    def g(lnP):
        P = math.exp(lnP)
        A = alpha * oa * (P / rec.Pc) / (T / rec.Tc) ** 2
        B = ob * (P / rec.Pc) / (T / rec.Tc)
        zs = _srk_pure_roots(A, B)
        if len(zs) < 2:
            return -1.0 if zs[-1] > zc else 1.0
        return _srk_pure_lnphi(zs[-1], A, B) - _srk_pure_lnphi(zs[0], A, B)
    P0 = rec.psat(T) if T >= rec.T_min else rec.Pc * math.exp(5.373 * (1 + 0.2) * (1 - rec.Tc / T))
    lnP = brentq(g, math.log(P0) - 2.0, math.log(min(P0 * 7.4, rec.Pc * 1.05)), xtol=1e-15, rtol=1e-15)
    return math.exp(lnP)


def certify_saturation(eos, T, P, x, y):
    """Fugacity equality of the two published phases on their own roots, normalization and distinction."""
    lx = np.log(x) + eos.phase(T, P, x, "liquid")["lnphi"]
    ly = np.log(y) + eos.phase(T, P, y, "vapor")["lnphi"]
    res = {"fugacity": float(np.max(np.abs(lx - ly))), "normalization": abs(float(np.sum(y)) - 1.0),
           "distinction": float(np.max(np.abs(np.asarray(x) - np.asarray(y))))}
    res["ok"] = res["fugacity"] <= TOL_CERT and res["normalization"] <= 1e-12 and res["distinction"] > 1e-6
    return res


PROBE_LNK_SCALES = (0.3, 0.1, 0.01)


def _wilson_guess(eos, T, x):
    from core.termodinamica.cubic_flash import wilson_lnK
    P0 = float(np.dot(x, eos.Pc * np.exp(5.373 * (1 + eos.omega) * (1 - eos.Tc / T))))
    return np.append(wilson_lnK(eos, T, P0), math.log(P0))


def bubble_pressure(eos, T, x, guess=None):
    """Bubble pressure and incipient vapour of liquid x at T, certified. guess: (ln K, ln P) from a neighbour.

    Located failures (A1-style review R2). When Newton fails from the supplied (or Wilson) start, the same equations
    are probed from that start with ln K damped by PROBE_LNK_SCALES at the same ln P. A probe that converges is
    classified exactly like a direct solution: y = x is `trivial_solution` (the only root found is the trivial one,
    as past the mixture critical point; this is not a pointwise proof that no non-trivial root exists), a denser
    incipient phase is `past_critical_point`, and a certified non-trivial root is returned. Only when every probe
    also fails is the cause `not_converged`, with the probes listed."""
    from core.termodinamica.cubic_flash import saturation
    eos.check_temperature(T)
    x = np.asarray(x, dtype=float)
    x = x / x.sum()
    failures = (CubicOutOfScope, np.linalg.LinAlgError, ValueError, OverflowError)
    try:
        r = saturation(eos, x, T=T, kind="bubble", guess=guess)
    except failures as e:
        base = np.asarray(guess, dtype=float) if guess is not None else _wilson_guess(eos, T, x)
        r, probes = None, []
        for s in PROBE_LNK_SCALES:
            g = np.append(s * base[:-1], base[-1])
            try:
                r = saturation(eos, x, T=T, kind="bubble", guess=g)
                probes.append({"scale": s, "converged": True})
                break
            except failures as e2:
                probes.append({"scale": s, "converged": False, "error": str(e2)[:120]})
        if r is None:
            raise CubicOutOfScope(f"Bubble point of x = {x.tolist()} at {T} K did not converge from the start or from "
                                  f"the damped probes: {e}", cause="not_converged", T=T, x=x.tolist(), probes=probes)
    if np.max(np.abs(r["u"][:-1])) < TOL_LNK_TRIVIAL:
        raise CubicOutOfScope(f"The bubble-point equations for x = {np.round(x, 6).tolist()} at {T} K converge only to "
                              "the trivial solution y = x, as for a state past the mixture critical point at this "
                              "temperature.", cause="trivial_solution", T=T, x=x.tolist(), P=r["P"])
    dist = float(np.max(np.abs(r["w"] - x)))
    if dist < TOL_NEAR_CRITICAL:
        # Within 1e-3 in composition of the critical point the equations also have non-trivial roots on one
        # common volume branch, and this solver cannot tell the bubble branch from the dew branch (CO2 + methanol
        # at 373.15 K, x = 0.71: |y - x| = 4e-5 with T above that composition's critical temperature).
        raise CubicOutOfScope(f"The bubble-point solution for x = {np.round(x, 6).tolist()} at {T} K has "
                              f"|y - x| = {dist:.2e} < {TOL_NEAR_CRITICAL:g}: the state is within the unresolved "
                              "neighbourhood of the isotherm's critical point.", cause="near_critical_unresolved",
                              T=T, x=x.tolist(), P=r["P"], distinction=dist)
    cert = certify_saturation(eos, T, r["P"], x, r["w"])
    # A bubble point's incipient phase is the less dense one. Past the critical composition of an isotherm the
    # same equations still have a non-trivial root in which the incipient phase is the denser (the dew branch of
    # a neighbouring feed); it is not a bubble point of x and is rejected, never relabelled.
    Zx = eos.phase(T, r["P"], x, "liquid")["Z"]
    Zy = eos.phase(T, r["P"], r["w"], "vapor")["Z"]
    cert["density_order"] = float(Zy - Zx)
    if cert["ok"] and not Zy > Zx:
        raise CubicOutOfScope(f"At {T} K the solution for x = {np.round(x, 6).tolist()} has an incipient phase denser "
                              "than the feed: the composition lies past the critical point of this isotherm.",
                              cause="past_critical_point", T=T, x=x.tolist(), P=r["P"], certificate=cert)
    if not cert["ok"]:
        raise CubicOutOfScope("Bubble point failed its certificate.", cause="not_certified", T=T, x=x.tolist(),
                              certificate=cert)
    return {"T": T, "P": r["P"], "x": x, "y": r["w"], "u": r["u"], "certificate": cert}


ISO_STEP_MAX = 0.02          # largest continuation step in x_j
ISO_STEP_FRACTION = 0.5      # step <= this fraction of the current |y_j - x_j|
ISO_STEP_MIN = 1e-4


def bubble_isotherm(eos, T, x_list, j=0):
    """Bubble pressures at T along increasing mole fractions x_j in x_list (binary), by natural-parameter
    continuation in x_j from the first point. Returns (points, rejected); rejected lists the located failures.

    Between requested compositions the trace advances by internal steps no larger than ISO_STEP_MAX and
    ISO_STEP_FRACTION |y_j - x_j| of the last accepted point (not below ISO_STEP_MIN). Near the isotherm's critical
    composition y -> x, so the steps shrink and the trace cannot jump past the critical point onto a near-trivial
    root (review R1/R2: a 0.085 step on CO2 + ethanol at 363.15 K accepted x = 0.77, |y - x| = 5e-5, although the
    critical composition lies between 0.76 and 0.77). Internal points only seed the next guess; only requested
    compositions are published. The trace does not jump over a failure: later compositions are listed as rejected
    with the cause of the first one, and `at` gives the internal composition where it failed."""
    pts, rej, guess, stop, last = [], [], None, None, None
    for xj in x_list:
        x = np.empty(eos.nc)
        x[j] = xj
        x[1 - j] = 1.0 - xj
        if stop is not None:
            rej.append({"x": x.tolist(), "cause": stop[0], "at": stop[1]})
            continue
        try:
            cur = last["x"][j] if last is not None else xj
            while last is not None and cur < xj:
                d = abs(float(last["y"][j] - last["x"][j]))
                step = min(ISO_STEP_MAX, max(ISO_STEP_MIN, ISO_STEP_FRACTION * d), xj - cur)
                cur = cur + step if xj - cur - step > 1e-12 else xj
                xi = np.empty(eos.nc)
                xi[j] = cur
                xi[1 - j] = 1.0 - cur
                try:
                    last = bubble_pressure(eos, T, xi, guess=guess)
                except CubicOutOfScope as e:
                    e.datos["at"] = cur
                    raise
                guess = last["u"]
            if last is None:
                last = bubble_pressure(eos, T, x, guess=guess)
                guess = last["u"]
        except CubicOutOfScope as e:
            at = e.datos.get("at", xj)
            stop = (e.datos.get("cause", "not_converged"), at)
            rej.append({"x": x.tolist(), "cause": stop[0], "at": at, "message": str(e)})
            continue
        pts.append(last)
    return pts, rej


def kappa_c():
    _, ob, zc = srk_constants()
    return zc / ob


def critical_points(eos, z, **kw):
    """Heidemann-Khalil critical points of composition z (cubic_critical.critical_points on the PSRK F), with
    the density classification on the SRK kappa_c = Z_c / Omega_b and the alpha-range gate."""
    from core.termodinamica import cubic_critical as cc
    pts = cc.critical_points(eos, z, **kw)
    kc = kappa_c()

    def kind(k):
        return "gas_liquid" if k >= cc.KAPPA_GL * kc else ("liquid_liquid" if k <= cc.KAPPA_LL * kc else "unclassified")
    keep, rejected = [], list(pts.rejected)
    for p in pts:
        p["kind"] = kind(p["kappa"])
        try:
            eos.check_temperature(p["T"])
        except CubicOutOfScope:
            rejected.append({**p, "reason": "alpha_below_fit_range"})
            continue
        keep.append(p)
    for p in rejected:
        p["kind"] = kind(p["kappa"])
    if not keep:
        raise CubicOutOfScope(f"No critical point of z = {np.round(z, 6).tolist()} inside the package coverage.",
                              cause="no_critical_point_in_window", rejected=rejected, window=pts.window)
    return cc.CriticalPointList(keep, rejected, pts.window)


def critical_locus(eos, x1_list, **kw):
    """Critical points of a binary along the mole fraction of species 0: [(x1, point, all_points)], rejected.

    `point` is the root of highest T at that composition (the continuation of the locus that leaves the heavier
    component's critical point). Its `kind` is the density label only: PSRK places high-pressure gas-liquid
    critical points of CO2 + alcohols at kappa = V/B of 2-3 (2.1-3.7 for CO2 + methanol), inside the labels
    calibrated for Peng-Robinson type III systems, so the label is reported, never used to drop a root.
    Compositions with no positive-pressure root are listed in `rejected` with the dropped roots."""
    out, rej = [], []
    for x1 in x1_list:
        try:
            pts = critical_points(eos, np.array([x1, 1.0 - x1]), **kw)
        except CubicOutOfScope as e:
            rej.append({"x1": x1, "cause": e.datos.get("cause"), "rejected": e.datos.get("rejected", [])})
            continue
        out.append((x1, max(pts, key=lambda p: p["T"]), list(pts)))
    return out, rej
