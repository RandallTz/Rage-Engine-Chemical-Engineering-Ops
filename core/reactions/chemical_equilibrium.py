"""Chemical equilibrium on the common thermodynamic layer (F5, Claude, 30 October 2026).

Chemical potentials come from the package (`core.mezclas.Sistema.mu`: UNIFAC or ideal liquid, ideal gas)
or, for species outside the catalog or above its liquid range, from an ideal-gas phase built from the same
`core.mezclas_datos.Especie` formulas and Poling cp source. There is no separate gamma path.

Formation reference. The package sets h = s = 0 for every pure ideal gas at T0 = 298.15 K, P0 = 1 bar. The
element-referenced potential differs from it by a constant enthalpy and a constant entropy per species:

    mu_i(T, P, x) = mu_i^pkg(T, P, x) + Hf_i - T S0_i          (Hf_i, S0_i: ideal gas at T0, P0)

with the ideal-gas formation enthalpy and absolute entropy of `chemicals.reaction` (Hfg, S0g). Absolute
entropies replace formation entropies because the element terms cancel in every element-balanced reaction.
Hence sum_i nu_i mu_i^0(T) carries the package's own cp integrals (Kirchhoff and the dCp/T entropy integral)
without a second Cp model; the constant-dH van 't Hoff value is reported beside it, never used.

Equilibrium condition, per independent reaction j:   sum_i nu_ij mu_i = 0.
The extent formulation solves it over the independent reactions; the Gibbs-minimisation alternative
minimises G = sum_i n_i mu_i over n >= 0 subject to the reaction invariants B n = B n0 (B spans the null space
of nu, i.e. the element balances when nu spans the null space of the element matrix). `certify` recomputes
the residual from fresh potentials and is the acceptance test of every result.

Units: SI (J/mol, K, Pa, mol).
"""

import math
from fractions import Fraction

import numpy as np
from scipy.optimize import least_squares, minimize

R = 8.314462618         # J/(mol K), the package's constant (core/mezclas_datos.py)
T0 = 298.15
P0 = 1e5

LN_FLOOR = -600.0        # ln n floor inside the minimiser's line search (exp underflow guard only)
TOLERANCE = 1e-9         # max |sum nu mu| / RT accepted as equilibrium


class ChemicalEquilibriumError(Exception):
    def __init__(self, code, message, **detail):
        super().__init__(message)
        self.code, self.message, self.detail = code, message, detail


# --- formation references --------------------------------------------------------------------------------
def formation_reference(cas, source=None):
    """(Hf [J/mol], S0 [J/(mol K)], provenance) of the pure ideal gas at T0, P0 from `chemicals.reaction`.

    `source` names the tabulation: None (the library's first choice), one method name for both, a pair
    (Hf method, S0 method), or a {cas: name or pair} mapping. A named method that lacks the species is an
    error, never a silent fallback."""
    import chemicals
    from chemicals import reaction as rx
    if isinstance(source, dict):
        source = source.get(cas)
    hm, sm = source if isinstance(source, tuple) else (source, source)
    for m, methods in ((hm, rx.Hfg_methods(cas)), (sm, rx.S0g_methods(cas))):
        if m is not None and m not in methods:
            raise ChemicalEquilibriumError("FORMATION_SOURCE_MISSING", f"{m} has no ideal-gas entry for {cas}.",
                                           cas=cas, available=list(methods))
    Hf, S0 = rx.Hfg(cas, method=hm), rx.S0g(cas, method=sm)
    if Hf is None or S0 is None:
        raise ChemicalEquilibriumError("FORMATION_DATA_MISSING",
                                       f"No ideal-gas formation enthalpy or absolute entropy for {cas}.", cas=cas)
    return float(Hf), float(S0), {"Hf": hm or rx.Hfg_methods(cas)[0], "S0": sm or rx.S0g_methods(cas)[0],
                                  "library": f"chemicals {chemicals.__version__}", "state": "ideal gas, 298.15 K, 1 bar"}


def element_matrix(cas_list):
    """Element matrix A [elements x species] from `chemicals` formulas, and the element names."""
    from chemicals.identifiers import search_chemical
    from chemicals.elements import simple_formula_parser
    atoms = [simple_formula_parser(search_chemical(c).formula) for c in cas_list]
    elements = sorted({e for a in atoms for e in a})
    return np.array([[a.get(e, 0) for a in atoms] for e in elements], dtype=float), elements


# --- phases -----------------------------------------------------------------------------------------------
class PackagePhase:
    """One phase of a `core.mezclas.Sistema` (tipo 'liquido' or 'vapor') with a constant formation shift.

    anchor='gas' (default): shift from ideal-gas Hfg, S0g; the liquid then inherits the package's ideal-gas +
    Psat route. anchor='liquid': shift so that the package's pure liquid reproduces the tabulated liquid Hfl,
    S0l at T0 (needed when that route is wrong, as for vapour-dimerising acids). Both are constant per species,
    so every package derivative relation is kept; `anchor_gap` reports the difference between them. A system
    holding a liquid-only species (`core.catalogo.REGISTRO_SOLO_LIQUIDO`) requires anchor='liquid': its gas
    anchor would reach the liquid through the invalid monomer ideal-gas route."""

    def __init__(self, sistema, tipo, source=None, anchor="gas"):
        from chemicals import reaction as rx
        from core.catalogo import REGISTRO_SOLO_LIQUIDO
        if tipo == "vapor" and getattr(sistema, "solo_liquido", False):
            raise ChemicalEquilibriumError("LIQUID_ONLY_SYSTEM", "A liquid-only system has no vapour phase.",
                                           cas=list(sistema.cas))
        liquid_only = [c for c in sistema.cas if c in REGISTRO_SOLO_LIQUIDO]
        if anchor != "liquid" and liquid_only:
            raise ChemicalEquilibriumError("LIQUID_ANCHOR_REQUIRED",
                                           f"{', '.join(liquid_only)} is admitted only in the liquid: its formation "
                                           "reference must be the tabulated liquid (anchor='liquid'), not the "
                                           f"ideal gas (anchor={anchor!r}).", cas=liquid_only, anchor=anchor,
                                           native_code="ESPECIE_SOLO_LIQUIDO")
        self.sistema, self.tipo, self.cas, self.anchor = sistema, tipo, tuple(sistema.cas), anchor
        refs = [formation_reference(c, source) for c in self.cas]
        self.Hf = np.array([r[0] for r in refs])
        self.S0 = np.array([r[1] for r in refs])
        gas_shift_T0 = self.Hf - T0 * self.S0
        if anchor == "liquid":
            Hl = np.array([rx.Hfl(c) if rx.Hfl(c) is not None else np.nan for c in self.cas], dtype=float)
            Sl = np.array([rx.S0l(c) if rx.S0l(c) is not None else np.nan for c in self.cas], dtype=float)
            if not np.all(np.isfinite(Hl + Sl)):
                raise ChemicalEquilibriumError("FORMATION_DATA_MISSING", "Liquid Hfl or S0l missing.",
                                               cas=[c for c, v in zip(self.cas, Hl + Sl) if not np.isfinite(v)])
            hL = np.array([e.h_L(T0, P0) for e in sistema.esp])
            sL = np.array([e.s_L(T0, P0) for e in sistema.esp])
            self.Hf, self.S0 = Hl - hL, Sl - sL          # shift: mu = mu_pkg + Hf - T S0, now liquid anchored
            import chemicals
            formation = {c: {"Hf": rx.Hfl_methods(c)[0], "S0": rx.S0l_methods(c)[0],
                             "library": f"chemicals {chemicals.__version__}", "state": "pure liquid, 298.15 K, 1 bar"}
                         for c in self.cas}
        else:
            formation = {c: r[2] for c, r in zip(self.cas, refs)}
        self.anchor_gap = {c: float(v) for c, v in zip(self.cas, (self.Hf - T0 * self.S0) - gas_shift_T0)}
        self.provenance = {"potentials": f"core.mezclas.Sistema('{sistema.paquete.id}').mu('{tipo}')",
                           "formation": formation, "anchor": anchor,
                           "standard_state": ("pure ideal gas at T and P0" if tipo == "vapor" else
                                              "pure liquid at T and P (package g_L)")}

    def mu(self, T, P, n):
        n = np.asarray(n, dtype=float)
        self.sistema.dominio(T, P)
        x = n / n.sum()
        idx = list(range(len(self.cas)))
        return self.sistema.mu(self.tipo, T, P, x, idx) + self.Hf - T * self.S0

    def mu_standard(self, T, P):
        """mu_i^0: pure ideal gas at (T, P0) or pure liquid at (T, P), element referenced."""
        gig, gL = self.sistema._g_puros(T, P)
        return (gig if self.tipo == "vapor" else gL) + self.Hf - T * self.S0

    def stability(self, T, P, n):
        """Tangent-plane test of the package (vapor and liquid trials): min tm < 0 means this single phase is
        not the stable state, so a single-phase chemical equilibrium is only a constrained stationary point.
        A liquid-only system has no vapour model, so only liquid trials run and `vapour_assessed` is False:
        stability against vapour formation is then NOT certified."""
        n = np.asarray(n, dtype=float)
        idx = list(range(len(self.cas)))
        mu = self.sistema.mu(self.tipo, T, P, n / n.sum(), idx)
        vapour = not getattr(self.sistema, "solo_liquido", False)
        trials = self.sistema.prueba_estabilidad(T, P, mu, idx, incluir_vapor=vapour)
        worst = min(trials, key=lambda t: t[2]) if trials else None
        return {"stable": worst is None or worst[2] >= -1e-9, "vapour_assessed": vapour,
                "min_tm": None if worst is None else float(worst[2]),
                "trial_phase": None if worst is None else worst[0],
                "trial_composition": None if worst is None else [float(v) for v in worst[1]]}


class IdealGasPhase:
    """Ideal-gas mixture from `Especie.g_ig0` with Poling cp, for species the catalog does not hold."""

    def __init__(self, cas_list, source=None):
        import chemicals.heat_capacity as hc
        from core.mezclas_datos import Especie
        from core.catalogo import REGISTRO_SOLO_LIQUIDO, SOLO_LIQUIDO_MOTIVO
        self.cas = tuple(cas_list)
        self.especies = []
        for c in self.cas:
            if c in REGISTRO_SOLO_LIQUIDO:
                raise ChemicalEquilibriumError("LIQUID_ONLY_SPECIES", f"{c}: {SOLO_LIQUIDO_MOTIVO[c]}", cas=c)
            if c not in hc.Cp_data_Poling.index:
                raise ChemicalEquilibriumError("CP_DATA_MISSING", f"No Poling ideal-gas cp for {c}.", cas=c)
            d = hc.Cp_data_Poling.loc[c]
            self.especies.append(Especie(cas=c, nombre=c, M=float("nan"), vL=float("nan"), fuente_vL="",
                                         psat_forma="", psat=(), T_psat=(),
                                         cp=tuple(float(d[k]) for k in ("a0", "a1", "a2", "a3", "a4")),
                                         T_cp=(float(d.Tmin), float(d.Tmax))))
        self.T_range = (max(e.T_cp[0] for e in self.especies), min(e.T_cp[1] for e in self.especies))
        refs = [formation_reference(c, source) for c in self.cas]
        self.Hf = np.array([r[0] for r in refs])
        self.S0 = np.array([r[1] for r in refs])
        self.tipo = "vapor"
        self.provenance = {"potentials": "core.mezclas_datos.Especie.g_ig0 (Poling cp), ideal gas",
                           "formation": {c: r[2] for c, r in zip(self.cas, refs)},
                           "standard_state": "pure ideal gas at T and P0"}

    def _domain(self, T):
        if not self.T_range[0] <= T <= self.T_range[1]:
            raise ChemicalEquilibriumError("OUT_OF_DOMAIN", f"T = {T:g} K outside the cp range "
                                           f"[{self.T_range[0]:g}, {self.T_range[1]:g}] K.", T=T)

    def mu_standard(self, T, P=None):
        self._domain(T)
        return np.array([e.g_ig0(T) for e in self.especies]) + self.Hf - T * self.S0

    def mu(self, T, P, n):
        n = np.asarray(n, dtype=float)
        with np.errstate(divide="raise"):
            return self.mu_standard(T) + R * T * np.log(n / n.sum() * P / P0)



# --- stoichiometry ----------------------------------------------------------------------------------------
def analyse_stoichiometry(NU, A=None, tol=1e-10):
    """Rank, an independent reaction subset, dependent reactions as combinations, invariants and element check."""
    NU = np.atleast_2d(np.asarray(NU, dtype=float))
    s = np.linalg.svd(NU, compute_uv=False)
    rank = int(np.sum(s > tol * max(1.0, s[0])))
    independent = []
    for j in range(NU.shape[0]):                       # greedy row basis, keeps the declared order
        if np.linalg.matrix_rank(NU[independent + [j]], tol=tol) > len(independent):
            independent.append(j)
    dependent = {}
    for j in range(NU.shape[0]):
        if j not in independent:
            c, *_ = np.linalg.lstsq(NU[independent].T, NU[j], rcond=None)
            dependent[j] = [float(v) for v in c]
    _, sv, Vt = np.linalg.svd(NU[independent])
    B = Vt[rank:]                                       # reaction invariants: B nu^T = 0
    out = {"rank": rank, "reactions": NU.shape[0], "independent": independent, "dependent": dependent,
           "invariants": B}
    if A is not None:
        A = np.asarray(A, dtype=float)
        out["element_residual"] = float(np.max(np.abs(A @ NU.T))) if NU.size else 0.0
        out["conserves_elements"] = out["element_residual"] < 1e-12
        out["spans_element_null_space"] = rank == A.shape[1] - np.linalg.matrix_rank(A)
    return out


# --- equilibrium constant ---------------------------------------------------------------------------------
def equilibrium_constant(phase, nu, T, P):
    """ln K(T) = -sum nu mu_i^0(T) / RT with the package's cp integrals, plus van 't Hoff from T0 for contrast."""
    nu = np.asarray(nu, dtype=float)
    dG = float(nu @ phase.mu_standard(T, P))
    dG0 = float(nu @ phase.mu_standard(T0, P if phase.tipo != "vapor" else P0))
    dH0 = float(nu @ phase.Hf) if phase.tipo == "vapor" else None
    lnK = -dG / (R * T)
    out = {"T": T, "lnK": lnK, "dG": dG, "dG_T0": dG0, "basis": phase.provenance["standard_state"]}
    if dH0 is not None:
        out["lnK_vant_hoff"] = -dG0 / (R * T0) - dH0 / R * (1.0 / T - 1.0 / T0)
    return out


# --- certification ----------------------------------------------------------------------------------------
def certify(phase, NU, n, n0, T, P, A=None):
    """Fresh residuals: |sum nu mu| / RT for EVERY declared reaction, invariants, element balance, n >= 0."""
    NU = np.atleast_2d(np.asarray(NU, dtype=float))
    n, n0 = np.asarray(n, dtype=float), np.asarray(n0, dtype=float)
    mu = phase.mu(T, P, n)                              # recomputed here, never taken from the solver
    affinity = NU @ mu / (R * T)
    st = analyse_stoichiometry(NU, A)
    inv = float(np.max(np.abs(st["invariants"] @ (n - n0)))) if st["invariants"].size else 0.0
    out = {"reaction_residual": [float(v) for v in affinity], "max_reaction_residual": float(np.max(np.abs(affinity))),
           "invariant_residual": inv / max(1.0, float(n0.sum())), "min_moles": float(np.min(n)),
           "tolerance": TOLERANCE}
    if A is not None:
        out["element_residual"] = float(np.max(np.abs(np.asarray(A) @ (n - n0)))) / max(1.0, float(n0.sum()))
    if hasattr(phase, "stability"):
        out["phase_stability"] = phase.stability(T, P, n)
    out["certified"] = (out["max_reaction_residual"] < TOLERANCE and out["min_moles"] > 0
                        and out["invariant_residual"] < 1e-10 and out.get("element_residual", 0.0) < 1e-10)
    return out


# --- conservation rows that keep the trace species ------------------------------------------------------
def reduce_conservation(B, n):
    """(B', M) with B' = M B, the same row space as B, Gauss-Jordan reduced with the most abundant species as pivots.

    Each abundant species then appears in a single row, and the remaining rows involve only less abundant species.
    The ratio of two trace species (H2 and O2 of a nearly complete H2 + 1/2 O2 -> H2O) is then a row without
    cancellation (n_H2 - 2 n_O2), where the original element rows reach it only through 2 - n_H2O, an O(1) number
    that carries a trace amount of 1e-12 with a relative resolution of 1e-4."""
    B = np.array(B, dtype=float)
    M = np.eye(B.shape[0])
    used = set()
    for r in range(B.shape[0]):
        best = None
        for c in np.argsort(-np.asarray(n, dtype=float)):
            if int(c) in used:
                continue
            col = np.abs(B[r:, c])
            if col.max() > 1e-12 * max(1.0, np.abs(B).max()):
                best = (int(c), r + int(np.argmax(col)))
                break
        if best is None:
            break
        c, k = best
        used.add(c)
        B[[r, k]], M[[r, k]] = B[[k, r]], M[[k, r]]
        M[r], B[r] = M[r] / B[r, c], B[r] / B[r, c]
        for i in range(B.shape[0]):
            if i != r and B[i, c] != 0.0:
                M[i], B[i] = M[i] - B[i, c] * M[r], B[i] - B[i, c] * B[r]
    # Stoichiometric coefficients and element counts are small rationals; the float invariants carry noise of a few
    # ulps (-1.9999999999999996 for -2), which makes B n0 differ from its exact value by 4e-16 and shifts a trace
    # row by that amount. Entries within 1e-12 of a fraction with denominator <= 1000 are snapped to it.
    for idx, x in np.ndenumerate(B):
        q = float(Fraction(float(x)).limit_denominator(1000))
        if x != q and abs(x - q) <= 1e-12 * max(1.0, abs(x)):
            B[idx] = q
    return B, M


def row_magnitude(B, n):
    """Size of the amounts each conservation row involves, sum_i |B_ri| n_i. Since B n = B n0 at a solution, it is
    also the size of the row's right-hand side: the residual of a row divided by it is relative to the species the
    row involves, so a trace row is converged to trace accuracy."""
    return np.maximum(np.abs(B) @ np.asarray(n, dtype=float), 1e-300)


# --- extent formulation -----------------------------------------------------------------------------------
def solve_extents(phase, NU, n0, T, P, A=None, xi0=None):
    """Extents of the independent reactions from sum_i nu_ij mu_i / RT = 0, with n kept strictly positive."""
    NU = np.atleast_2d(np.asarray(NU, dtype=float))
    n0 = np.asarray(n0, dtype=float)
    st = analyse_stoichiometry(NU, A)
    if A is not None and not st["conserves_elements"]:
        raise ChemicalEquilibriumError("ELEMENTS_NOT_CONSERVED", "A reaction does not conserve the elements.",
                                       residual=st["element_residual"])
    _absent_inerts(NU, n0, list(phase.cas))
    NI = NU[st["independent"]]
    scale = float(n0.sum())

    def moles(xi):
        return n0 + NI.T @ xi

    xi = np.zeros(len(NI)) if xi0 is None else np.asarray(xi0, dtype=float)
    if np.any(moles(xi) <= 0):                           # start inside: shift toward the products present
        xi = _interior_start(NI, n0)
    # Damped Newton in z = ln n on the affinities of the independent reactions plus the reaction
    # invariants B (n - n0) = 0. Amounts are carried directly, so a nearly exhausted reactant keeps its
    # relative precision (n0 + nu xi would lose it to cancellation) and every iterate stays positive.
    Binv = st["invariants"]
    z = np.log(moles(xi))

    def rows(z):
        """Invariant rows reduced on the current amounts, and the size of their terms (see reduce_conservation)."""
        Br, _ = reduce_conservation(Binv, np.exp(z))
        return Br, row_magnitude(Br, np.exp(z))

    def F(z, Br, mag):
        n = np.exp(z)
        # B n - B n0, not B (n - n0): subtracting a feed of order one from a trace amount first would round the
        # trace amount to the resolution of the feed (2e-16), which is a relative 1e-4 at 1e-12 mol
        return np.concatenate([NI @ phase.mu(T, P, n) / (R * T), (Br @ n - Br @ n0) / mag])

    Br, mag = rows(z)
    f = F(z, Br, mag)
    for it in range(500):
        if np.max(np.abs(f)) < 1e-14:
            break
        n = np.exp(z)
        Jz = np.vstack([NI @ _dmu_dn(phase, T, P, n) * n / (R * T), (Br * n) / mag[:, None]])
        dz = np.linalg.lstsq(Jz, -f, rcond=None)[0]
        alpha = min(1.0, 5.0 / max(float(np.max(np.abs(dz))), 1e-300))   # at most a factor e^5 per step
        while True:
            trial = z + alpha * dz
            f_trial = F(trial, Br, mag)
            if np.linalg.norm(f_trial) < (1 - 1e-4 * alpha) * np.linalg.norm(f) or alpha < 1e-12:
                break
            alpha *= 0.5
        step = float(np.max(np.abs(trial - z)))
        z = trial
        Br, mag = rows(z)
        f = F(z, Br, mag)
        if step < 1e-15:
            break
    xi = np.linalg.lstsq(NI.T, np.exp(z) - n0, rcond=None)[0]
    n = np.exp(z)
    cert = certify(phase, NU, n, n0, T, P, A)
    if not cert["certified"]:
        raise ChemicalEquilibriumError("NOT_CERTIFIED", "The extent solve ended at a state that fails the "
                                       "recomputed certificate.", certificate=cert, moles=n.tolist())
    return {"extents": [float(v) for v in xi], "moles": [float(v) for v in n], "stoichiometry": st,
            "certificate": cert, "iterations": it, "method": "extent, damped Newton in ln n on affinities and reaction invariants"}


def _dmu_dn(phase, T, P, n):
    """dmu_i/dn_k: central differences with a step proportional to n_k, which resolves the ln n_k term of
    mu_k and keeps both sides positive. For a trace species that step is too small for the other rows
    (smooth in n_k on the scale of the total), so those take a three-point forward step of 1e-5 n_total."""
    J = np.empty((n.size, n.size))
    N = float(n.sum())
    for k in range(n.size):
        step = 1e-6 * n[k]
        e = np.zeros(n.size); e[k] = step
        J[:, k] = (phase.mu(T, P, n + e) - phase.mu(T, P, n - e)) / (2 * step)
        if n[k] < 1e-3 * N:
            H = 1e-5 * N
            e = np.zeros(n.size); e[k] = H
            far = (-3 * phase.mu(T, P, n) + 4 * phase.mu(T, P, n + e) - phase.mu(T, P, n + 2 * e)) / (2 * H)
            own = J[k, k]
            J[:, k] = far
            J[k, k] = own
    return J


def _absent_inerts(NU, n0, cas):
    """Species with zero feed that no reaction produces or consumes: a single phase cannot hold them at n > 0."""
    idle = [cas[i] for i in range(len(n0)) if n0[i] <= 0 and not np.any(NU[:, i])]
    if idle:
        raise ChemicalEquilibriumError("ABSENT_INERT_SPECIES", "Species with zero feed that no reaction "
                                       "touches must be removed from the phase: " + ", ".join(idle) + ".",
                                       species=idle)


def _interior_start(NI, n0):
    """A strictly feasible extent: maximise min_i n_i by a small linear search over the reaction directions."""
    from scipy.optimize import linprog
    r, s = NI.shape
    # variables (xi, t): maximise t subject to n0 + NI^T xi >= t
    c = np.zeros(r + 1); c[-1] = -1.0
    A_ub = np.hstack([-NI.T, np.ones((s, 1))])
    res = linprog(c, A_ub=A_ub, b_ub=n0, bounds=[(None, None)] * r + [(None, n0.sum())], method="highs")
    if not res.success or res.x[-1] <= 0:
        raise ChemicalEquilibriumError("NO_INTERIOR", "The feed leaves no strictly positive composition.")
    return res.x[:-1] * 0.5                              # halfway: still interior, away from the max-min point


# --- Gibbs minimisation -----------------------------------------------------------------------------------
def minimise_gibbs(phase, NU, n0, T, P, A=None, constraints="reactions"):
    """min G/RT over ln n subject to B n = B n0 (B: reaction invariants, or the element matrix with
    constraints='elements'). Independent of the extent formulation and of the reaction basis chosen."""
    n0 = np.asarray(n0, dtype=float)
    _absent_inerts(np.atleast_2d(np.asarray(NU, dtype=float)), n0, list(phase.cas))
    if constraints == "elements":
        Bm = np.asarray(A, dtype=float)
    else:
        Bm = analyse_stoichiometry(NU, A)["invariants"]
    b = Bm @ n0
    start = n0 + 1e-3 * n0.sum()                         # positive start; equality restored by the solver
    scale = float(n0.sum())

    def G(z):
        n = np.exp(np.maximum(z, LN_FLOOR))
        mu = phase.mu(T, P, n)
        return float(n @ mu) / (R * T * scale), n * mu / (R * T * scale)

    cons = {"type": "eq", "fun": lambda z: (Bm @ np.exp(z) - b) / scale,
            "jac": lambda z: Bm * np.exp(z) / scale}
    upper = math.log(10.0 * scale * max(1.0, float(np.max(np.abs(Bm)))))
    sol = minimize(G, np.log(start), jac=True, constraints=[cons], method="SLSQP",
                   bounds=[(LN_FLOOR, upper)] * len(n0), options={"ftol": 1e-16, "maxiter": 2000})
    # Polish on the stationarity conditions of the same Lagrangian, mu_i / RT = sum_k lambda_k B_ki and
    # B n = b: still the Gibbs formulation (element or invariant potentials), no reaction basis enters.
    z = sol.x
    # The conservation rows are reduced on the amounts of the SLSQP solution (abundant species as pivots) and each
    # divided by the size of its terms, so the polish converges a trace species to trace accuracy; with the original
    # rows scaled by the total moles, a 1e-12 mol species was left wrong by 1e-4 to 1e-1 relative, by amounts that
    # depended on the round-off of the platform (F9, test_nearly_exhausted_reactant). The multipliers are mapped back
    # to the rows of Bm: Bred = M Bm, so lambda = M^T lambda_red.
    Br, M = reduce_conservation(Bm, np.exp(z))
    br = Br @ n0
    mag = row_magnitude(Br, np.exp(z))
    lam, *_ = np.linalg.lstsq(Br.T, phase.mu(T, P, np.exp(z)) / (R * T), rcond=None)
    m = len(z)

    def kkt(v):
        n = np.exp(v[:m])
        return np.concatenate([phase.mu(T, P, n) / (R * T) - Br.T @ v[m:], (Br @ n - br) / mag])

    pol = least_squares(kkt, np.concatenate([z, lam]), method="lm", xtol=1e-15, ftol=1e-15, gtol=1e-15)
    n = np.exp(pol.x[:m])
    return {"moles": [float(v) for v in n], "optimizer": str(sol.message), "constraints": constraints,
            "lagrange_multipliers": [float(v) for v in M.T @ pol.x[m:]],
            "certificate": certify(phase, NU, n, n0, T, P, A),
            "method": "Gibbs minimisation (SLSQP over ln n, then Newton on its stationarity conditions)"}


# --- facade agreed with the Model/compiler side (F5 roadmap proposal) -------------------------------------
STANDARD_STATES = {"vapor": "ideal_gas_P0", "liquido": "pure_liquid_TP"}


def evaluate_reactions(provider, nu, *, T, P, n, phase_id, standard_state):
    """State of the declared reactions at a supplied inventory; it never equilibrates and never clips.

    provider: a PackagePhase or IdealGasPhase (its formation anchor fixes the reference). phase_id must be
    the provider's phase ('liquido' | 'vapor'); standard_state must be the one that phase implies. Ordering
    is the provider's species order; nu has one row per reaction, products positive. SI throughout.
    Returns ln a_i = (mu_i - mu_i^0)/RT, ln K_j, mu_i (element referenced), the affinity sum nu mu / RT,
    partial molar h_i = mu_i - T dmu_i/dT and u_i = h_i - P v_i, dmu_i/dn_k, and validity."""
    if phase_id != provider.tipo:
        raise ChemicalEquilibriumError("PHASE_MISMATCH", f"Provider phase is {provider.tipo}, not {phase_id}.")
    if standard_state != STANDARD_STATES[provider.tipo]:
        raise ChemicalEquilibriumError("STANDARD_STATE_MISMATCH",
                                       f"{phase_id} uses {STANDARD_STATES[provider.tipo]}, not {standard_state}.")
    NU = np.atleast_2d(np.asarray(nu, dtype=float))
    n = np.asarray(n, dtype=float)
    validity = {"positive_amounts": bool(np.all(n > 0)), "domain": True, "message": ""}
    if not validity["positive_amounts"]:
        validity["message"] = "An amount is zero or negative: ln a_i is not finite; nothing is clipped."
        return {"valid": False, "validity": validity, "T": T, "P": P, "n": n.tolist(), "nu": NU.tolist()}
    try:
        mu = provider.mu(T, P, n)
    except Exception as exc:                            # package domain (FueraDeAlcance) or cp range
        validity.update(domain=False, message=str(exc))
        return {"valid": False, "validity": validity, "T": T, "P": P, "n": n.tolist(), "nu": NU.tolist()}
    RT = R * T
    mu0 = provider.mu_standard(T, P)
    dT = 1e-3
    dmu_dT = (provider.mu(T + dT, P, n) - provider.mu(T - dT, P, n)) / (2 * dT)
    h = mu - T * dmu_dT
    if provider.tipo == "vapor":
        v = np.full(n.size, RT / P)
    else:
        v = np.array([e.vL for e in provider.sistema.esp])  # package liquid: v = sum x_i vL_i, no excess volume
    J = _dmu_dn(provider, T, P, n)
    if not (np.all(np.isfinite(J)) and np.all(np.isfinite(dmu_dT))):
        validity.update(domain=False, message="A derivative of mu is not finite at this inventory.")
        return {"valid": False, "validity": validity, "T": T, "P": P, "n": n.tolist(), "nu": NU.tolist()}
    lnK = -(NU @ mu0) / RT
    return {"valid": True, "validity": validity, "T": T, "P": P, "n": n.tolist(), "nu": NU.tolist(),
            "species": list(provider.cas), "phase_id": phase_id, "standard_state": standard_state,
            "anchor": getattr(provider, "anchor", "gas"), "provenance": provider.provenance,
            "ln_a": ((mu - mu0) / RT).tolist(), "lnK": lnK.tolist(), "mu": mu.tolist(),
            "affinity_RT": (NU @ mu / RT).tolist(), "h_partial": h.tolist(), "u_partial": (h - P * v).tolist(),
            "dmu_dn": J.tolist(),
            "derivatives": "dmu/dT and dmu/dn by central differences (dT = 1e-3 K, dn_k = 1e-6 n_k; other rows of a trace column 1e-5 n_total forward)",
            "energy_reference": "mu, h and u include the formation reference: an energy balance written with "
                                "these h must not add a separate heat of reaction",
            "_provider": provider}


def certify_reactions(state, *, tolerances=None, n0=None, A=None):
    """mu residuals recomputed from the state's provider (never from the state's own numbers), conservation
    against n0 (reaction invariants, and elements when A is given) and phase stability, kept apart from any
    solver convergence flag."""
    if not state.get("valid"):
        return {"certified": False, "reason": state["validity"]["message"]}
    tol = {"affinity": TOLERANCE, "conservation": 1e-10}
    tol.update(tolerances or {})
    n = np.asarray(state["n"], dtype=float)
    out = certify(state["_provider"], state["nu"], n, n if n0 is None else n0, state["T"], state["P"], A)
    out["tolerances"] = tol
    out["certified"] = (out["max_reaction_residual"] < tol["affinity"] and out["min_moles"] > 0
                        and (n0 is None or out["invariant_residual"] < tol["conservation"])
                        and out.get("element_residual", 0.0) < tol["conservation"])
    out["conservation_checked"] = n0 is not None
    return out


def reaction_jacobian_bounds(provider, nu, box, *, phase_id, standard_state):
    """Certified enclosures of g, dg/dn, dg/dT and dg/dP over a state box (F5, 5 November 2026). Defined in
    core/reactions/jacobian_bounds.py (imported here lazily: that module uses the phase classes above)."""
    from core.reactions.jacobian_bounds import reaction_jacobian_bounds as bounds
    return bounds(provider, nu, box, phase_id=phase_id, standard_state=standard_state)


def heat_capacity_bounds(provider, box, *, phase_id, standard_state):
    """Certified enclosure of C_p = -T d2G/dT2 at fixed P and n over a state box, with a positivity proof (B3
    part 2, thermal coupling, 6 November 2026). Defined in core/reactions/jacobian_bounds.py."""
    from core.reactions.jacobian_bounds import heat_capacity_bounds as bounds
    return bounds(provider, box, phase_id=phase_id, standard_state=standard_state)
