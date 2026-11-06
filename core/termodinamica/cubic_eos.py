"""
Peng-Robinson mixture equation of state from one residual Helmholtz function (F8b, 5 November 2026).

Every property of this package follows from a single function of (T, V, n),

    F(T, V, n) = A^r / (R T)
               = -n ln(1 - B/V) - D(T) / (R T B (d1 - d2)) ln((V + d1 B) / (V + d2 B)),

with n = sum n_i, B = sum n_i b_i (linear in n) and D = sum_ij n_i n_j a_ij(T) (quadratic in n), the
van der Waals one-fluid mixing rules with a_ij = (1 - k_ij) sqrt(a_i a_j). d1 = 1 + sqrt 2 and
d2 = 1 - sqrt 2 select Peng-Robinson. The pure-component constants are not posed: Omega_a, Omega_b and Z_c
are solved here from the critical conditions (dP/dV)_T = (d2P/dV2)_T = 0 at (T_c, P_c) of this same
pressure function (`critical_constants`).

Chain rule (Michelsen and Mollerup, Thermodynamic Models, 2nd ed., ch. 3): write F = -n g(V, B) - (D/T) f(V, B)
with g = ln(1 - B/V) and f = ln((V + d1 B)/(V + d2 B)) / (R B (d1 - d2)). Then

    F_n = -g,   F_B = -n g_B - (D/T) f_B,   F_D = -f/T,   F_V = -n g_V - (D/T) f_V,
    F_T = D f / T^2 - D_T f / T,
    g_V = B / (V (V - B)),   g_B = -1/(V - B),
    f_V = -1 / (R (V + d1 B)(V + d2 B)),   f_B = -(f + V f_V) / B,

    dF/dn_i = F_n + F_B b_i + F_D D_i,      D_i = 2 sum_j n_j a_ij,
    P = -R T F_V + n R T / V,
    ln phi_i = dF/dn_i - ln Z,              Z = P V / (n R T),
    H^r(T, P) = -R T^2 F_T + P V - n R T,   G^r(T, P) / RT = sum n_i ln phi_i,   S^r = (H^r - G^r) / T.

The composition derivative at (T, P) needed by a Newton flash follows from the (T, V) Hessian:

    n d ln phi_i / dn_j |_(T,P) = n F_ij + 1 + (n / R T) (dP/dn_i)(dP/dn_j) / (dP/dV),
    dP/dn_i = -R T F_Vi + R T / V,   dP/dV = -R T F_VV - n R T / V^2.

F_ij and F_Vi are taken here by complex step of the analytic gradient, which is exact to rounding because the
gradient is written in complex-safe arithmetic. The tests check every first derivative against an independent
complex step of F itself, and ln phi against the textbook closed form and the `thermo` package (PRMIX).

Pure-component data come only from the common catalog (core/catalogo via core/mezclas_datos): T_c and P_c of
each species' Wagner vapour-pressure record, and the acentric factor from its definition on that same record,
omega = -log10(Psat(0.7 T_c) / P_c) - 1. The temperature function is Robinson and Peng (1978):
alpha = (1 + m (1 - sqrt(T/T_c)))^2 with m = 0.379642 + 1.48503 w - 0.164423 w^2 + 0.016666 w^3 for w > 0.491 and
the 1976 form m = 0.37464 + 1.54226 w - 0.26992 w^2 otherwise. k_ij defaults to 0 (prediction); a declared
binary record may set it. Ideal-gas parts use the catalog's cp_ig and the shared reference (ideal gas at
298.15 K and 1e5 Pa, h = s = 0), so energies are comparable with every other mixture package.

Declared limits: no volume translation (liquid densities carry the known Peng-Robinson error; phase equilibrium
is unchanged by a constant translation), quadratic mixing only (no association, no excess-Gibbs mixing rule),
so strongly polar or hydrogen-bonded pairs are outside the predictive accuracy of k_ij = 0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np

from core import mezclas_datos as datos

R = datos.R
P0 = datos.P0
SQRT2 = math.sqrt(2.0)
D1 = 1.0 + SQRT2
D2 = 1.0 - SQRT2
CS_H = 1e-30            # complex step


class CubicOutOfScope(Exception):
    """A state or request outside what this package can evaluate; never replaced by a default.

    `datos` locates the rejection when the caller supplies it: `cause` (for example `liquid_liquid_split`,
    `no_critical_point_in_window`, `outside_bracket`) and the state (T, P, z, ...)."""

    def __init__(self, message="", **datos):
        super().__init__(message)
        self.mensaje, self.datos = message, datos


@lru_cache(maxsize=None)
def critical_constants(d1=D1, d2=D2):
    """(Omega_a, Omega_b, Z_c) of the generic two-parameter cubic P = RT/(v-b) - a/((v+d1 b)(v+d2 b)).

    In reduced units (R = T_c = P_c = 1) the critical point requires P(v_c) = 1, P'(v_c) = 0, P''(v_c) = 0.
    Newton on the three conditions with an analytic Jacobian, converged to rounding."""
    def res(x):
        a, b, v = x
        q = (v + d1 * b) * (v + d2 * b)
        qv = 2 * v + (d1 + d2) * b
        p = 1 / (v - b) - a / q
        p1 = -1 / (v - b) ** 2 + a * qv / q ** 2
        p2 = 2 / (v - b) ** 3 + a * (2 / q ** 2 - 2 * qv ** 2 / q ** 3)
        return np.array([p - 1.0, p1, p2])
    x = np.array([0.457, 0.078, 0.307])
    for _ in range(60):
        r = res(x)
        J = np.empty((3, 3))
        for k in range(3):
            xc = x.astype(complex)
            xc[k] += 1j * CS_H

            def resc(z):
                a, b, v = z
                q = (v + d1 * b) * (v + d2 * b)
                qv = 2 * v + (d1 + d2) * b
                return np.array([1 / (v - b) - a / q - 1.0, -1 / (v - b) ** 2 + a * qv / q ** 2,
                                 2 / (v - b) ** 3 + a * (2 / q ** 2 - 2 * qv ** 2 / q ** 3)])
            J[:, k] = resc(xc).imag / CS_H
        dx = np.linalg.solve(J, -r)
        x = x + dx
        if np.max(np.abs(dx)) < 1e-16:
            break
    return float(x[0]), float(x[1]), float(x[2])


def acentric_from_psat(esp):
    """omega by its definition (Pitzer) on the catalog's own vapour-pressure record."""
    return -math.log10(esp.Psat(0.7 * esp.Tc) / esp.psat[5]) - 1.0


def m_of_omega(w):
    if w > 0.491:
        return 0.379642 + 1.48503 * w - 0.164423 * w ** 2 + 0.016666 * w ** 3
    return 0.37464 + 1.54226 * w - 0.26992 * w ** 2


@dataclass
class PengRobinsonMixture:
    """Peng-Robinson with van der Waals one-fluid mixing over an ordered list of catalog species."""
    cas: tuple
    kij: np.ndarray = None
    Tc: np.ndarray = field(init=False)
    Pc: np.ndarray = field(init=False)
    omega: np.ndarray = field(init=False)

    def __post_init__(self):
        from core import catalogo
        self.cas = tuple(self.cas)
        faltan = [c for c in self.cas if c not in catalogo.REGISTRO]
        if faltan:
            raise CubicOutOfScope(f"No pure-component vapour-liquid record for {', '.join(faltan)} in the catalog.")
        self.esp = [datos.especie(c) for c in self.cas]
        self.nc = len(self.cas)
        self.Tc = np.array([e.Tc for e in self.esp], dtype=float)
        self.Pc = np.array([e.psat[5] for e in self.esp], dtype=float)
        self.omega = np.array([acentric_from_psat(e) for e in self.esp])
        self.m = np.array([m_of_omega(w) for w in self.omega])
        oa, ob, self.Zc = critical_constants()
        self.ac = oa * R ** 2 * self.Tc ** 2 / self.Pc
        self.b = ob * R * self.Tc / self.Pc
        k = np.zeros((self.nc, self.nc)) if self.kij is None else np.asarray(self.kij, dtype=float)
        if k.shape != (self.nc, self.nc) or not np.allclose(k, k.T) or np.any(np.diag(k) != 0):
            raise CubicOutOfScope("k_ij must be a symmetric matrix with a zero diagonal.")
        self.kij = k
        # cp_ig polynomials are valid on their own range; the EOS itself has no upper temperature bound.
        self.T_range = (max(e.T_cp[0] for e in self.esp), min(e.T_cp[1] for e in self.esp))

    # --- temperature functions -------------------------------------------------
    def a_pure(self, T):
        """(a_i, da_i/dT) of the Robinson-Peng alpha function."""
        sr = np.sqrt(T / self.Tc)
        s = 1.0 + self.m * (1.0 - sr)
        a = self.ac * s ** 2
        da = self.ac * 2 * s * (-self.m * 0.5 / np.sqrt(T * self.Tc))
        return a, da

    def a_matrix(self, T):
        a, da = self.a_pure(T)
        sq = np.sqrt(np.outer(a, a))
        A = (1 - self.kij) * sq
        dA = (1 - self.kij) * (np.outer(da, a) + np.outer(a, da)) / (2 * sq)
        return A, dA

    # --- the residual Helmholtz function and its analytic gradient --------------
    def F(self, T, V, n):
        """A^r / (R T); complex-safe in T, V and n."""
        a = self.ac * (1.0 + self.m * (1.0 - np.sqrt(T / self.Tc))) ** 2
        A = (1 - self.kij) * np.sqrt(np.outer(a, a))
        n = np.asarray(n)
        ntot = np.sum(n)
        B = np.dot(n, self.b)
        D = n @ A @ n
        return -ntot * np.log(1 - B / V) - D / (R * T * B * (D1 - D2)) * np.log((V + D1 * B) / (V + D2 * B))

    def _parts(self, T, V, n):
        A, dA = self.a_matrix(T)
        n = np.asarray(n)
        ntot = np.sum(n)
        B = np.dot(n, self.b)
        Di = 2 * (A @ n)
        D = 0.5 * np.dot(n, Di)
        DT = n @ dA @ n
        g = np.log(1 - B / V)
        f = np.log((V + D1 * B) / (V + D2 * B)) / (R * B * (D1 - D2))
        gV = B / (V * (V - B))
        gB = -1 / (V - B)
        fV = -1 / (R * (V + D1 * B) * (V + D2 * B))
        fB = -(f + V * fV) / B
        return dict(ntot=ntot, B=B, D=D, Di=Di, DT=DT, g=g, f=f, gV=gV, gB=gB, fV=fV, fB=fB)

    def gradient(self, T, V, n):
        """(F_n_i, F_V, F_T) from the chain rule; complex-safe in V and n."""
        p = self._parts(T, V, n)
        Fn = -p["g"]
        FB = -p["ntot"] * p["gB"] - p["D"] / T * p["fB"]
        FD = -p["f"] / T
        Fni = Fn + FB * self.b + FD * p["Di"]
        FV = -p["ntot"] * p["gV"] - p["D"] / T * p["fV"]
        FT = p["D"] * p["f"] / T ** 2 - p["DT"] * p["f"] / T
        return Fni, FV, FT

    def pressure(self, T, V, n):
        _, FV, _ = self.gradient(T, V, n)
        return -R * T * FV + np.sum(n) * R * T / V

    def hessian_TV(self, T, V, n):
        """(F_ij, F_Vi, F_VV) at fixed T by complex step of the analytic gradient (exact to rounding)."""
        n = np.asarray(n, dtype=float)
        nc = len(n)
        Fij = np.empty((nc, nc))
        FVi = np.empty(nc)
        for j in range(nc):
            nn = n.astype(complex)
            nn[j] += 1j * CS_H
            gi, gv, _ = self.gradient(T, V, nn)
            Fij[:, j] = gi.imag / CS_H
            FVi[j] = gv.imag / CS_H
        gi, gv, _ = self.gradient(T, V + 1j * CS_H * V, n)
        FVV = gv.imag / (CS_H * V)
        return Fij, FVi, FVV

    # --- volume roots at (T, P) ------------------------------------------------
    def z_roots(self, T, P, x):
        """Real compressibility roots Z > B' of the cubic for composition x, ascending, Newton-polished."""
        x = np.asarray(x, dtype=float)
        A_, _ = self.a_matrix(T)
        Am = (x @ A_ @ x) * P / (R * T) ** 2
        Bm = np.dot(x, self.b) * P / (R * T)
        # (Z - B)(Z + d1 B)(Z + d2 B) = (Z + d1 B)(Z + d2 B) - A (Z - B), expanded by polynomial products
        q = np.polymul([1, D1 * Bm], [1, D2 * Bm])
        lhs = np.polymul([1, -Bm], q)
        rhs = np.polyadd(q, np.polymul([-Am], [1, -Bm]))
        coef = np.polysub(lhs, rhs)
        r = np.roots(coef)
        zs = sorted(float(z.real) for z in r if abs(z.imag) <= 1e-9 * max(1.0, abs(z.real)) and z.real > Bm)
        out = []
        for z in zs:
            for _ in range(8):
                fz = np.polyval(coef, z)
                dz = np.polyval(np.polyder(coef), z)
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

    def ln_phi_Z(self, T, P, x, Z):
        x = np.asarray(x, dtype=float)
        V = Z * R * T / P            # per mole of phase (n = x, sum 1)
        Fni, _, _ = self.gradient(T, V, x)
        return Fni - math.log(Z)

    def phase(self, T, P, x, root="stable"):
        """Fugacity coefficients and the root used. root: 'stable' (minimum G^r), 'liquid' or 'vapor'."""
        x = np.asarray(x, dtype=float)
        x = x / x.sum()
        zs = self.z_roots(T, P, x)
        if root == "liquid":
            cand = [zs[0]]
        elif root == "vapor":
            cand = [zs[-1]]
        else:
            cand = zs
        best = None
        for Z in cand:
            lnphi = self.ln_phi_Z(T, P, x, Z)
            gr = float(np.dot(x, lnphi))
            if best is None or gr < best[0]:
                best = (gr, Z, lnphi)
        return {"Z": best[1], "lnphi": best[2], "gr_RT": best[0], "roots": zs}

    def dlnphi_dn(self, T, P, n, Z):
        """d ln phi_i / dn_j at fixed (T, P) for the phase with amounts n and root Z."""
        n = np.asarray(n, dtype=float)
        ntot = n.sum()
        V = Z * ntot * R * T / P
        Fij, FVi, FVV = self.hessian_TV(T, V, n)
        dPdn = -R * T * FVi + R * T / V
        dPdV = -R * T * FVV - ntot * R * T / V ** 2
        return Fij + 1.0 / ntot + np.outer(dPdn, dPdn) / (R * T * dPdV)

    # --- caloric properties relative to the shared ideal-gas reference ----------
    def residual_TP(self, T, P, x, Z):
        """(h^r, s^r, g^r) per mole of phase at (T, P)."""
        x = np.asarray(x, dtype=float)
        V = Z * R * T / P
        Fni, _, FT = self.gradient(T, V, x)
        gr = R * T * float(np.dot(x, Fni - math.log(Z)))
        hr = float(-R * T ** 2 * FT + P * V - R * T)
        return hr, (hr - gr) / T, gr

    def molar_props(self, T, P, x, Z):
        """h, s, g, v and mu_i per mole of phase, on the reference of every mixture package."""
        x = np.asarray(x, dtype=float)
        hr, sr, gr = self.residual_TP(T, P, x, Z)
        lnphi = self.ln_phi_Z(T, P, x, Z)
        hig = np.array([e.h_ig(T) for e in self.esp])
        sig = np.array([e.s_ig0(T) for e in self.esp])
        gig = np.array([e.g_ig0(T) for e in self.esp])
        with np.errstate(divide="ignore", invalid="ignore"):
            lnxp = np.where(x > 0, np.log(np.where(x > 0, x, 1.0) * P / P0), -np.inf)
        mu = gig + R * T * (lnxp + lnphi)
        xs = x[x > 0]
        h = float(np.dot(x, hig) + hr)
        s = float(np.dot(x, sig) - R * np.sum(xs * np.log(xs * P / P0)) + sr)
        g = h - T * s
        v = Z * R * T / P
        return {"h": h, "s": s, "g": g, "v": v, "mu": mu, "Z": Z, "u": h - P * v}

    def phase_identification(self, T, V, n):
        """Venkatarathnam-Oellrich phase identification parameter, Fluid Phase Equilib. 301 (2011) 225:
        PIP = V [ (d2P/dT dV)/(dP/dT) - (d2P/dV2)/(dP/dV) ]; PIP > 1 liquid-like, < 1 vapour-like. Central
        differences of the analytic pressure (step 1e-5 relative)."""
        def Pf(t, v):
            return float(np.real(self.pressure(t, v, n)))
        hT, hV = 1e-5 * T, 1e-5 * V
        PT = (Pf(T + hT, V) - Pf(T - hT, V)) / (2 * hT)
        PV = (Pf(T, V + hV) - Pf(T, V - hV)) / (2 * hV)
        PVV = (Pf(T, V + hV) - 2 * Pf(T, V) + Pf(T, V - hV)) / hV ** 2
        PTV = (Pf(T + hT, V + hV) - Pf(T + hT, V - hV) - Pf(T - hT, V + hV) + Pf(T - hT, V - hV)) / (4 * hT * hV)
        return V * (PTV / PT - PVV / PV)
