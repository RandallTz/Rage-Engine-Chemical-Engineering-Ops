"""Thermodynamic entry points for deduced-model ("derived") execution (Claude, 30 October 2026).

Derived execution lowers the Thermodynamics nodes of a deduced model (caloric inventory, package closure,
phase presence, per-phase streams) by calling these functions. They wrap the common layer and never
reimplement it:

  - potentials, phase properties and flashes: `core.mezclas.Sistema` (`mu`, `fase`, `equilibrio_UV`,
    `equilibrio_PH`, the seeded `flash_rapido`, `prueba_estabilidad`);
  - formation reference: `core.reactions.chemical_equilibrium.PackagePhase` (constant Hf_i - T S0_i shift);
  - candidate phases and the complementarity beta_k >= 0, tm_k >= 0, beta_k tm_k = 0: the rule of
    `core.termodinamica.capa`.

Contract (roadmap F4 "FD" and F5-C2 paragraphs):

  species_caloric(package, species, T, P)              pure-species h, u and dh/dT, du/dT (gas and liquid)
  phase_caloric(package, species, T, P, n, phase)      H, U, V of one phase, dH/dT, dU/dT, partial molar h, u, v
  phase_temperature(package, species, n, P, target)    single-phase T from U or H (temperature reconstruction)
  reaction_enthalpy(package, species, nu, T, P)        Delta_r H and Delta_r U per reaction, formation anchored
  close_state(package, species, n, spec, a, b)         UV or PH closure: phases, amounts, x, v_L, certificate
  closure_sensitivities(package, species, n, spec, a, b)   d(T, P|V, n_k)/d(n, a, b) for an implicit solver
  phase_indicators(state)                              presence, beta_k, tm_k and event functions per candidate
  phase_draw(state, phase, total_outflow)              component flows and enthalpy flow drawn from one phase

Every function is pure: it builds its `Sistema` from (package, species, liquid_only), keeps no module-level
state and caches nothing between calls; a seed is passed in by the caller and only changes the cost. Units
are SI: K, Pa, mol, J, m3, kg, s. Errors are `DerivedThermoError(code, message, detail)`.

Energy reference. anchor=None keeps the package reference (each pure ideal gas has h = s = 0 at 298.15 K,
1 bar). anchor='gas' or 'liquid' adds the constant formation shift of `PackagePhase` (Hf_i of the ideal gas,
or the shift that reproduces the tabulated liquid Hf_i), so that sum_i n_i u_i carries the reaction heat and
an energy balance needs no separate heat-of-reaction source. All energies of one model must use one anchor.
A liquid-only species (acetic acid) admits only anchor='liquid'; 'gas' raises LIQUID_ANCHOR_REQUIRED.
"""

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.optimize import brentq

from core import mezclas as mz

R = mz.R
PACKAGES = ("unifac-original-public", "unifac-dortmund-public")
PACKAGE_ALIASES = {"unifac-original": "unifac-original-public", "unifac-dortmund": "unifac-dortmund-public"}
ANCHORS = (None, "gas", "liquid")
SPECIFICATIONS = ("UV", "PH")
PRESENT_FRACTION = mz.N_AUSENTE      # a phase with n_k / n below this is absent (the package rule)
SAME_TRIAL = 1e-5                     # a trial composition within this of a present phase is that phase
DT_DERIVATIVE = 1e-2                  # K, step of the fourth-order central T differences
DERIVATIVE_METHOD = "fourth-order central differences in T, step 1e-2 K (one-sided second order at a domain edge)"


class DerivedThermoError(Exception):
    """code: UNSUPPORTED_PACKAGE | INVALID_INPUT | PARAMETER_MISSING | LIQUID_ONLY_SYSTEM | OUT_OF_DOMAIN |
    NOT_CONVERGED | UNSUPPORTED_STATE | FORMATION_DATA_MISSING | FORMATION_SOURCE_MISSING |
    ELEMENTS_NOT_CONSERVED | PHASE_AMBIGUOUS. detail carries the native code or reason."""

    def __init__(self, code, message, **detail):
        super().__init__(message)
        self.code, self.message, self.detail = code, message, detail


# --- results ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class PhaseState:
    id: str                 # published package id: 'vapor-1', 'liquido-1', 'liquido-2'
    kind: str               # 'vapor' | 'liquid'
    amount: float           # mol
    beta: float             # amount / total amount
    x: tuple                # mole fractions, species order
    h: float                # J/mol (anchor of the state)
    u: float                # J/mol
    v: float                # m3/mol
    M: float                # kg/mol


@dataclass(frozen=True)
class ClosureState:
    package: str
    species: tuple
    liquid_only: bool
    anchor: object
    specification: str      # 'UV' | 'PH'
    n: tuple                # mol
    T: float                # K
    P: float                # Pa
    V: float                # m3
    H: float                # J (anchor of the state)
    U: float                # J
    phases: tuple           # PhaseState, present phases only
    liquid_volume: float    # m3, all liquid phases (0 when none)
    liquid_amount: float    # mol
    liquid_molar_volume: object   # m3/mol, V_L / n_L, or None without liquid
    certificate: dict
    fingerprint: str
    native: object = field(default=None, repr=False, compare=False)   # core.mezclas.EstadoMezcla, the next seed

    @property
    def phase_set(self):
        return tuple(sorted(p.id for p in self.phases))


# --- configuration ---------------------------------------------------------------------------------------
def _package_id(package):
    pid = PACKAGE_ALIASES.get(package, package)
    if pid not in PACKAGES:
        raise DerivedThermoError("UNSUPPORTED_PACKAGE", f"Derived execution supports {', '.join(PACKAGES)}; "
                                 f"{package!r} is not one of them.", package=package)
    return pid


def _system(package, species, liquid_only=False):
    pid = _package_id(package)
    try:
        return mz.Sistema(pid, list(species), solo_liquido=liquid_only)
    except mz.FaltaParametro as error:
        raise DerivedThermoError("PARAMETER_MISSING", error.mensaje, native_code=error.codigo,
                                 detail=error.detalle) from error


def _amounts(sistema, n):
    n = np.asarray(n, dtype=float)
    if n.shape != (len(sistema.cas),) or not np.all(np.isfinite(n)) or np.any(n < 0) or not n.sum() > 0:
        raise DerivedThermoError("INVALID_INPUT", "Amounts must be finite, non-negative, one per species and "
                                 "with a positive total.", n=n.tolist())
    return n


def _kind(phase):
    k = {"liquid": "liquido", "liquido": "liquido", "vapor": "vapor", "vapour": "vapor"}.get(phase)
    if k is None:
        raise DerivedThermoError("INVALID_INPUT", f"Phase kind must be 'liquid' or 'vapor', not {phase!r}.")
    return k


def _native(call):
    """Run a package call and translate its expected failures."""
    try:
        return call()
    except mz.FaltaParametro as error:
        code = "LIQUID_ONLY_SYSTEM" if error.codigo == "ESPECIE_SOLO_LIQUIDO" else "PARAMETER_MISSING"
        raise DerivedThermoError(code, error.mensaje, native_code=error.codigo, detail=error.detalle) from error
    except mz.FueraDeAlcance as error:
        code = {"fuera_de_dominio": "OUT_OF_DOMAIN", "no_convergente": "NOT_CONVERGED"}.get(error.motivo,
                                                                                             "UNSUPPORTED_STATE")
        raise DerivedThermoError(code, str(error), native_reason=error.motivo) from error


def _shift(sistema, anchor, formation_source=None):
    """Constant per-species enthalpy shift Hf_i of the anchor (zeros for the package reference)."""
    if anchor not in ANCHORS:
        raise DerivedThermoError("INVALID_INPUT", f"anchor must be one of {ANCHORS}, not {anchor!r}.")
    if anchor is None:
        return np.zeros(len(sistema.cas)), None
    from core.reactions import chemical_equilibrium as ce
    try:
        phase = ce.PackagePhase(sistema, "liquido", source=formation_source, anchor=anchor)
    except ce.ChemicalEquilibriumError as error:
        raise DerivedThermoError(error.code, error.message, **error.detail) from error
    return np.asarray(phase.Hf, dtype=float), phase.provenance["formation"]


def _fingerprint(sistema, anchor, formation_source=None):
    return f"{sistema.huella()}|anchor={anchor}|formation={formation_source!r}"


def _d_dT(f, T, lo, hi, h=DT_DERIVATIVE):
    """d f / dT (f may be vector valued)."""
    if lo <= T - 2 * h and T + 2 * h <= hi:
        return (-f(T + 2 * h) + 8 * f(T + h) - 8 * f(T - h) + f(T - 2 * h)) / (12 * h)
    if T + 2 * h <= hi:
        return (-3 * f(T) + 4 * f(T + h) - f(T + 2 * h)) / (2 * h)
    return (3 * f(T) - 4 * f(T - h) + f(T - 2 * h)) / (2 * h)


# --- (a) caloric properties ------------------------------------------------------------------------------
def species_caloric(package, species, T, P, *, anchor=None, liquid_only=False, formation_source=None):
    """Pure-species caloric properties at (T, P), consistent with `Sistema.mu` (h = -T^2 d(g/T)/dT of the
    package's g_ig0 and g_L). Returns per-species arrays (species order), J/mol and J/(mol K):
    h_gas, u_gas, dh_gas_dT, du_gas_dT (ideal gas, analytic) and h_liquid, u_liquid, dh_liquid_dT,
    du_liquid_dT (package liquid; constant v_L, so du/dT = dh/dT at fixed P), v_liquid, and the shift."""
    s = _system(package, species, liquid_only)
    _native(lambda: s.dominio(T, P))
    shift, formation = _shift(s, anchor, formation_source)
    lo, hi = s.T_rango
    h_gas = np.array([e.h_ig(T) for e in s.esp]) + shift
    cp_gas = np.array([e.cp_ig(T) for e in s.esp])
    h_liq = np.array([e.h_L(T, P) for e in s.esp]) + shift
    dh_liq = _d_dT(lambda t: np.array([e.h_L(t, P) for e in s.esp]), T, lo, hi)
    vL = np.array(s.vL, dtype=float)
    out = {"species": list(s.cas), "T": T, "P": P, "anchor": anchor, "shift": shift.tolist(),
           "h_liquid": h_liq.tolist(), "u_liquid": (h_liq - P * vL).tolist(),
           "dh_liquid_dT": dh_liq.tolist(), "du_liquid_dT": dh_liq.tolist(), "v_liquid": vL.tolist(),
           "derivatives": {"gas": "analytic cp of the package", "liquid": DERIVATIVE_METHOD},
           "formation": formation, "fingerprint": _fingerprint(s, anchor, formation_source)}
    if not s.solo_liquido:
        out.update(h_gas=h_gas.tolist(), u_gas=(h_gas - R * T).tolist(), dh_gas_dT=cp_gas.tolist(),
                   du_gas_dT=(cp_gas - R).tolist())
    return out


def _phase_props(s, kind, T, P, n, shift):
    """(H, V, partial molar h, partial molar v) of one phase at (T, P, n), anchor applied."""
    N = float(n.sum())
    x = n / N
    idx = list(range(len(n)))
    if kind == "vapor":
        s._exigir_vapor("A vapour caloric evaluation")
        hbar = np.array([e.h_ig(T) for e in s.esp])
        vbar = np.full(len(n), R * T / P)
    else:
        lng = lambda t: np.asarray(s._lngamma(t, x, idx), dtype=float)
        dlng = _d_dT(lng, T, *s.T_rango)
        hbar = np.array([e.h_L(T, P) for e in s.esp]) - R * T * T * dlng
        vbar = np.array(s.vL, dtype=float)
    hbar = hbar + shift
    return float(n @ hbar), float(n @ vbar), hbar, vbar


def phase_caloric(package, species, T, P, n, *, phase="liquid", anchor=None, liquid_only=False,
                  formation_source=None):
    """Caloric inventory of one phase holding n at (T, P): H = sum n_i h_i, U = H - P V, V = sum n_i v_i,
    with the partial molar h_i = -T^2 d(mu_i/T)/dT of `Sistema.mu` (liquid: h_L,i - R T^2 d ln gamma_i/dT,
    finite for absent species; vapour: h_ig,i). dH/dT and dU/dT at fixed P and n. J, m3, J/K, J/mol."""
    s = _system(package, species, liquid_only)
    n = _amounts(s, n)
    kind = _kind(phase)
    _native(lambda: s.dominio(T, P))
    shift, formation = _shift(s, anchor, formation_source)
    H, V, hbar, vbar = _native(lambda: _phase_props(s, kind, T, P, n, shift))
    lo, hi = s.T_rango
    dH = float(_native(lambda: _d_dT(lambda t: _phase_props(s, kind, t, P, n, shift)[0], T, lo, hi)))
    dV = R * float(n.sum()) / P if kind == "vapor" else 0.0
    return {"species": list(s.cas), "phase": "vapor" if kind == "vapor" else "liquid", "T": T, "P": P,
            "n": n.tolist(), "anchor": anchor, "H": H, "U": H - P * V, "V": V, "dH_dT": dH, "dU_dT": dH - P * dV,
            "h_partial": hbar.tolist(), "u_partial": (hbar - P * vbar).tolist(), "v_partial": vbar.tolist(),
            "derivatives": DERIVATIVE_METHOD, "formation": formation,
            "fingerprint": _fingerprint(s, anchor, formation_source)}


def phase_temperature(package, species, n, P, target, *, quantity="U", phase="liquid", anchor=None,
                      liquid_only=False, formation_source=None, check_stability=True):
    """T of a single phase with U(T, P, n) (or H) equal to target [J], by Brent's method over the package
    range (dU/dT > 0). This is the reconstruction for a volume whose phase policy is declared single-phase.
    With check_stability, the tangent-plane test of the package reports whether that phase is the stable
    state at the found T ('single_phase_stable'); a False value means the declared policy is violated there."""
    s = _system(package, species, liquid_only)
    n = _amounts(s, n)
    kind = _kind(phase)
    if quantity not in ("U", "H"):
        raise DerivedThermoError("INVALID_INPUT", f"quantity must be 'U' or 'H', not {quantity!r}.")
    _native(lambda: s.dominio(s.T_rango[0], P))
    shift, _ = _shift(s, anchor, formation_source)

    def offset(T):
        H, V, _, _ = _phase_props(s, kind, T, P, n, shift)
        return (H - P * V if quantity == "U" else H) - target
    lo, hi = s.T_rango
    f_lo, f_hi = _native(lambda: (offset(lo), offset(hi)))
    if f_lo > 0 or f_hi < 0:
        raise DerivedThermoError("OUT_OF_DOMAIN", f"No {phase} state with {quantity} = {target:.9g} J at "
                                 f"P = {P:.6g} Pa has T in [{lo:.6g}, {hi:.6g}] K.", native_reason="fuera_de_dominio")
    T = brentq(offset, lo, hi, xtol=1e-12, rtol=4 * np.finfo(float).eps, maxiter=200)
    out = phase_caloric(package, species, T, P, n, phase=phase, anchor=anchor, liquid_only=liquid_only,
                        formation_source=formation_source)
    out["residual"] = abs(offset(T)) / max(abs(target), R * T * float(n.sum()))
    if check_stability:
        idx = [i for i in range(len(n)) if n[i] > 0]
        nz = n[idx]
        mu_ref = _native(lambda: s.mu(kind, T, P, nz / nz.sum(), idx))
        trials = _native(lambda: s.prueba_estabilidad(T, P, mu_ref, idx, incluir_vapor=not s.solo_liquido))
        others = mz._candidatas_nuevas(trials, [(kind, nz / nz.sum())], tol=SAME_TRIAL)
        tm = min((q[2] for q in others), default=math.inf)
        out["single_phase_stable"] = bool(tm >= -mz.TOL_TM)
        out["stability"] = {"min_tm": float(tm), "vapour_assessed": not s.solo_liquido,
                            "trial_phase": min(others, key=lambda q: q[2])[0] if others else None}
    return out


def reaction_enthalpy(package, species, nu, T, P, *, phase="liquid", n=None, anchor="gas", liquid_only=False,
                      formation_source=None, check_elements=True):
    """Delta_r H_j = sum_i nu_ij h_i and Delta_r U_j = sum_i nu_ij u_i [J/mol of extent], formation anchored
    (anchor 'gas' or 'liquid'; the shift of `PackagePhase`). With n, h_i is the partial molar enthalpy in that
    phase mixture; without it, the pure-species value of the phase (pure liquid at T, P or ideal gas). nu has
    one row per reaction, products positive. The same h_i enter `phase_caloric` with the same anchor, so a
    balance that uses it must not add Delta_r H as a source as well."""
    if anchor is None:
        raise DerivedThermoError("INVALID_INPUT", "A reaction enthalpy needs a formation anchor ('gas' or 'liquid').")
    s = _system(package, species, liquid_only)
    kind = _kind(phase)
    NU = np.atleast_2d(np.asarray(nu, dtype=float))
    if NU.shape[1] != len(s.cas):
        raise DerivedThermoError("INVALID_INPUT", "nu needs one column per species.", shape=list(NU.shape))
    elements = None
    if check_elements:
        from core.reactions import chemical_equilibrium as ce
        A, names = ce.element_matrix(list(s.cas))
        residual = float(np.max(np.abs(A @ NU.T)))
        if residual > 1e-12:
            raise DerivedThermoError("ELEMENTS_NOT_CONSERVED", "A reaction does not conserve the elements.",
                                     residual=residual, elements=names)
        elements = {"elements": names, "residual": residual}
    if n is None:
        cal = species_caloric(package, species, T, P, anchor=anchor, liquid_only=liquid_only,
                              formation_source=formation_source)
        key = "gas" if kind == "vapor" else "liquid"
        if f"h_{key}" not in cal:
            raise DerivedThermoError("LIQUID_ONLY_SYSTEM", "A liquid-only system has no vapour enthalpy.")
        h, u, basis = np.array(cal[f"h_{key}"]), np.array(cal[f"u_{key}"]), "pure species"
    else:
        cal = phase_caloric(package, species, T, P, n, phase=phase, anchor=anchor, liquid_only=liquid_only,
                            formation_source=formation_source)
        h, u, basis = np.array(cal["h_partial"]), np.array(cal["u_partial"]), "partial molar in the given mixture"
    return {"species": list(s.cas), "nu": NU.tolist(), "T": T, "P": P, "phase": cal.get("phase", phase),
            "basis": basis, "anchor": anchor, "dH": (NU @ h).tolist(), "dU": (NU @ u).tolist(),
            "h": h.tolist(), "u": u.tolist(), "elements": elements, "formation": cal["formation"],
            "fingerprint": cal["fingerprint"]}


# --- (b) state closure -----------------------------------------------------------------------------------
def close_state(package, species, n, spec, a, b, *, anchor=None, seed=None, liquid_only=False,
                formation_source=None):
    """Equilibrium state of a volume: spec 'UV' with (a, b) = (U [J], V [m3]) for a rigid volume, or 'PH'
    with (a, b) = (P [Pa], H [J]) for a prescribed pressure. U and H are in the anchor's reference. seed: a
    previous ClosureState of the same package and species (the integrator's last state); it only starts the
    package's seeded Newton (`flash_rapido`, which ends with the full stability test) and never fixes a
    property. Returns a ClosureState with the present phases, their amounts, compositions and molar h, u, v,
    the liquid volume and molar volume, and a certificate of fresh package verifications."""
    if spec not in SPECIFICATIONS:
        raise DerivedThermoError("INVALID_INPUT", f"spec must be one of {SPECIFICATIONS}, not {spec!r}.")
    s = _system(package, species, liquid_only)
    n = _amounts(s, n)
    shift, _ = _shift(s, anchor, formation_source)
    E_shift = float(n @ shift)
    if spec == "UV":
        args = (a - E_shift, b)
    else:
        args = (a, b - E_shift)
    native_seed = None
    if seed is not None:
        if not isinstance(seed, ClosureState) or seed.package != s.paquete.id or seed.species != s.cas:
            raise DerivedThermoError("INVALID_INPUT", "The seed must be a ClosureState of the same package and species.")
        native_seed = seed.native

    def solve():
        if native_seed is not None:
            return s.flash_rapido(spec, args[0], args[1], n, native_seed)
        return s.equilibrio_UV(*args, n) if spec == "UV" else s.equilibrio_PH(*args, n)
    e = _native(solve)
    return _wrap(s, e, spec, n, anchor, shift, formation_source)


def _wrap(s, e, spec, n, anchor, shift, formation_source):
    N = float(n.sum())
    phases = []
    for f in e.fases:
        if not f.n > PRESENT_FRACTION * N:
            continue
        x = np.asarray(f.x, dtype=float)
        h = float(f.h + x @ shift)
        phases.append(PhaseState(id=f.id, kind="vapor" if f.tipo == "vapor" else "liquid", amount=float(f.n),
                                 beta=float(f.n) / N, x=tuple(float(v) for v in x), h=h, u=h - e.P * float(f.v),
                                 v=float(f.v), M=float(f.M)))
    liquids = [p for p in phases if p.kind == "liquid"]
    VL = float(sum(p.amount * p.v for p in liquids))
    nL = float(sum(p.amount for p in liquids))
    checks = {k: {"residual": float(r), "tolerance": float(t), "passed": bool(r <= t), "description": d}
              for k, (r, t, d) in e.verificaciones.items()}
    certificate = {"checks": checks, "certified": all(c["passed"] for c in checks.values()),
                   "min_tm": (e.estabilidad or {}).get("tm_min"), "appearance_margin": (e.estabilidad or {}).get("tm_nueva")}
    E_shift = float(n @ shift)
    return ClosureState(package=s.paquete.id, species=s.cas, liquid_only=s.solo_liquido, anchor=anchor,
                        specification=spec, n=tuple(float(v) for v in n), T=float(e.T), P=float(e.P),
                        V=float(e.V), H=float(e.H) + E_shift, U=float(e.U) + E_shift, phases=tuple(phases),
                        liquid_volume=VL, liquid_amount=nL, liquid_molar_volume=VL / nL if nL > 0 else None,
                        certificate=certificate, fingerprint=_fingerprint(s, anchor, formation_source), native=e)


def closure_sensitivities(package, species, n, spec, a, b, *, anchor=None, seed=None, liquid_only=False,
                          formation_source=None, relative_step=1e-6):
    """Central-difference derivatives of the closure outputs with respect to its inputs (n_i, a, b), for an
    implicit integrator's Jacobian. Outputs: T, the conjugate of the specification (P for UV, V for PH) and
    each present phase's amount. Each perturbed closure is seeded with the base state. 'phase_set_changed'
    is True when a perturbation crosses a phase boundary; those columns are then one-sided limits mixed
    across the boundary and must not be trusted."""
    base = close_state(package, species, n, spec, a, b, anchor=anchor, seed=seed, liquid_only=liquid_only,
                       formation_source=formation_source)
    n = np.asarray(n, dtype=float)
    inputs = [("n", i) for i in range(len(n))] + [("a", None), ("b", None)]
    conj = "P" if spec == "UV" else "V"
    ids = [p.id for p in base.phases]

    def outputs(st):
        amounts = {p.id: p.amount for p in st.phases}
        return np.array([st.T, getattr(st, conj)] + [amounts.get(k, 0.0) for k in ids])
    J = np.empty((2 + len(ids), len(inputs)))
    changed = False
    for col, (name, i) in enumerate(inputs):
        if name == "n":
            step = relative_step * max(n[i], 1e-3 * n.sum())
        elif (name, spec) in (("a", "UV"), ("b", "PH")):           # energy
            step = relative_step * max(abs(a if name == "a" else b), R * base.T * n.sum())
        else:                                                         # V of UV, P of PH
            step = relative_step * abs(b if name == "b" else a)
        cols = []
        for sign in (1.0, -1.0):
            nn, aa, bb = n.copy(), a, b
            if name == "n":
                nn[i] = n[i] + sign * step
                if nn[i] < 0:
                    nn[i] = 0.0
            elif name == "a":
                aa = a + sign * step
            else:
                bb = b + sign * step
            st = close_state(package, species, nn, spec, aa, bb, anchor=anchor, seed=base, liquid_only=liquid_only,
                             formation_source=formation_source)
            changed = changed or st.phase_set != base.phase_set
            cols.append((outputs(st), (nn[i] - n[i]) if name == "n" else sign * step))
        J[:, col] = (cols[0][0] - cols[1][0]) / (cols[0][1] - cols[1][1])
    labels_in = [f"n[{i}]" for i in range(len(n))] + (["U", "V"] if spec == "UV" else ["P", "H"])
    return {"state": base, "outputs": ["T", conj] + [f"amount[{k}]" for k in ids], "inputs": labels_in,
            "jacobian": J.tolist(), "phase_set_changed": changed,
            "method": f"central differences, relative step {relative_step:g}, seeded with the base state"}


# --- (c) phase presence and events -----------------------------------------------------------------------
def _candidates(s, n):
    active = int(np.sum(np.asarray(n) > 0))
    ids = ["vapor-1", "liquido-1"] if not s.solo_liquido else ["liquido-1"]
    if not isinstance(s.liq, mz.LiquidoIdeal) and active > 1:
        ids.append("liquido-2")
    return ids


def _refined_hidden_minima(s, T, P, mu_ref, idx):
    """Liquid trial minima that the package's binary test leaves unrefined (grid minima with tm >= 1e-4,
    kept for its appearance margin), refined here within their grid cell. Near a binodal, on the single-liquid
    side, the conjugate liquid is such a minimum: without it the absent liquid has no margin and its
    appearance is never a sign change. Grid points at the logit edge (a fraction below 1e-12) are flat
    plateaus of roundoff, not minima, and are dropped; the package refines the genuine edge minima itself."""
    if len(idx) != 2:
        return []
    from scipy.optimize import minimize_scalar
    out = []
    for kind_, w, tm in s.__dict__.get("_minimos_sin_refinar", []):
        w = np.asarray(w, dtype=float)
        if kind_ != "liquido" or w.min() < 1e-12:
            continue
        u0 = math.log(w[0] / w[1])
        pair = lambda uu: [1 / (1 + math.exp(-uu)), 1 / (1 + math.exp(uu))]
        r = minimize_scalar(lambda uu: s._tm_liquido(T, P, pair(uu), mu_ref, idx), bounds=(u0 - 0.06, u0 + 0.06),
                            method="bounded", options={"xatol": 1e-12})
        out.append(("liquido", np.array(pair(r.x)), float(r.fun)) if r.fun <= tm else ("liquido", w, float(tm)))
    return out


def phase_indicators(state, previous=None):
    """Presence and margins of every candidate phase of the closure state (vapor-1, liquido-1 and, for an
    activity model with two or more species, liquido-2), from a fresh tangent-plane test of the package at
    the state's T, P with the potential of a present phase.

    Per candidate: present, beta (n_k / n), tm (0 when present; the smallest new trial minimum of that kind
    when absent), x (present composition) or incipient_x (trial composition), package_id (the closure's id
    of the present phase, None when absent) and the event function

        g_k = beta_k - tm_k      (continuous; g_k > 0 present, g_k < 0 absent, g_k = 0 at the boundary)

    It is the complementarity beta_k >= 0, tm_k >= 0, beta_k tm_k = 0 in one signed number. An ODE event
    locator watches g_k: a rising zero crossing (direction +1) is the appearance of k (tm_k -> 0), a falling
    one (direction -1) its disappearance (beta_k -> 0). Absent liquid candidates take the distinct liquid trial
    minima, including the binary minima the package leaves unrefined, in increasing tm.

    g_k None: the tangent-plane distance has no local minimum of that kind besides the present phases, so
    no margin exists at this state. This does NOT prove that the phase cannot appear before the next step: far
    from a miscibility gap the second well of tm can be absent and form later (water/1-butanol, UNIFAC
    Dortmund, 300 K: none at x_BuOH = 0.02, tm = 0.0027 at 0.0288, binodal at 0.029). A locator must also
    treat a change of the closure's phase_set between accepted steps as an event, and locate it by bisection
    on the closure.

    Liquid identity. The closure names liquids by density (liquido-1 the densest), so when the dense liquid
    disappears the remaining one is renamed and no event crosses zero. Pass the previous step's indicators
    as `previous`: liquid labels then follow composition continuity (present x and incipient_x matched to the
    previous rows), so each label keeps one physical liquid and its g_k crosses zero. Without `previous` the
    labels are the closure's. Use the returned 'labels' (label -> package_id) in `phase_draw(...,
    indicators=...)` so a stream keeps drawing from the same liquid. 'complementarity' is max |beta tm|,
    -beta, -tm over the candidates."""
    if not isinstance(state, ClosureState) or state.native is None:
        raise DerivedThermoError("INVALID_INPUT", "phase_indicators needs a ClosureState from close_state.")
    if previous is not None and (not isinstance(previous, dict) or "phases" not in previous
                                 or previous.get("fingerprint") != state.fingerprint):
        raise DerivedThermoError("INVALID_INPUT", "previous must be a phase_indicators result of the same package, "
                                 "species and anchor.")
    s = _system(state.package, state.species, state.liquid_only)
    e = state.native
    n = np.asarray(state.n, dtype=float)
    idx = [i for i in range(len(n)) if n[i] > 0]
    present = {p.id: p for p in state.phases}
    ref = next(f for f in e.fases if f.id in present)
    mu_ref = ref.mu[idx]
    trials = _native(lambda: s.prueba_estabilidad(state.T, state.P, mu_ref, idx, incluir_vapor=not s.solo_liquido))
    trials = trials + _native(lambda: _refined_hidden_minima(s, state.T, state.P, mu_ref, idx))
    new = mz._candidatas_nuevas(trials, [(f.tipo, np.asarray(f.x)[idx]) for f in e.fases if f.id in present],
                                tol=SAME_TRIAL)
    distinct = {"vapor": [], "liquido": []}
    for kind_, w, tm in sorted(new, key=lambda q: q[2]):
        if not any(np.max(np.abs(np.asarray(w) - v)) < SAME_TRIAL for v, _ in distinct[kind_]):
            distinct[kind_].append((np.asarray(w), float(tm)))

    def full(w):
        x = np.zeros(len(n))
        x[idx] = w
        return x.tolist()

    def present_row(p):
        return {"kind": p.kind, "present": True, "beta": p.beta, "tm": 0.0, "event": p.beta, "x": list(p.x),
                "incipient_x": None, "package_id": p.id}

    def absent_row(kind, w_tm):
        if w_tm is None:
            return {"kind": kind, "present": False, "beta": 0.0, "tm": None, "event": None, "x": None,
                    "incipient_x": None, "package_id": None}
        return {"kind": kind, "present": False, "beta": 0.0, "tm": w_tm[1], "event": -w_tm[1], "x": None,
                "incipient_x": full(w_tm[0]), "package_id": None}

    candidates = _candidates(s, n)
    rows = {}
    if "vapor-1" in candidates:
        rows["vapor-1"] = (present_row(present["vapor-1"]) if "vapor-1" in present else
                           absent_row("vapor", distinct["vapor"][0] if distinct["vapor"] else None))
    liquids = [present_row(p) for p in state.phases if p.kind == "liquid"]
    labels = [k for k in candidates if k.startswith("liquido")]
    while len(labels) < len(liquids):
        labels.append(f"liquido-{len(labels) + 1}")
    pool = distinct["liquido"][:]
    while len(liquids) < len(labels):
        liquids.append(absent_row("liquid", pool.pop(0) if pool else None))
    order = list(range(len(labels)))
    if previous is not None:
        before = {r["phase"]: (r["x"] or r["incipient_x"]) for r in previous["phases"]}

        def cost(perm):
            total = 0.0
            for label, j in zip(labels, perm):
                a, c = before.get(label), liquids[j]["x"] or liquids[j]["incipient_x"]
                total += 0.5 if a is None or c is None else float(np.max(np.abs(np.asarray(a) - np.asarray(c))))
            return total
        import itertools
        best = cost(order)
        for perm in itertools.permutations(order):
            c = cost(list(perm))
            if c < best - 1e-12:
                order, best = list(perm), c
    for label, j in zip(labels, order):
        rows[label] = liquids[j]
    out, residual = [], 0.0
    for k in ["vapor-1"] * ("vapor-1" in rows) + labels:
        row = {"phase": k, **rows[k]}
        if row["tm"] is not None:
            residual = max(residual, abs(row["beta"] * row["tm"]), -row["beta"], -row["tm"])
        out.append(row)
    return {"T": state.T, "P": state.P, "phases": out, "complementarity": residual,
            "labels": {r["phase"]: r["package_id"] for r in out}, "tracked": previous is not None,
            "event_functions": [{"phase": r["phase"], "value": r["event"], "appearance_direction": 1,
                                 "disappearance_direction": -1} for r in out],
            "fingerprint": state.fingerprint}


# --- (d) per-phase draw ----------------------------------------------------------------------------------
def phase_draw(state, phase, total_outflow, *, basis="molar", selection=None, indicators=None):
    """Component flows drawn from one phase of the closure state: q_i = F x_i^k (mol/s), F = total_outflow on
    a molar basis or W / M^k on a mass basis (kg/s), with the enthalpy flow F h^k [W] in the state's anchor.
    phase: 'vapor', 'liquid' or a phase id ('vapor-1', 'liquido-1', 'liquido-2'; 'liquid-1', 'liquid-2' are
    accepted). With two liquids, 'liquid' needs selection 'higher_density', 'lower_density' or 'combined'
    (the liquids mixed); otherwise PHASE_AMBIGUOUS. An absent phase is not an error: every flow is zero and
    present is False (the presence predicate beta_k > 0 of the FD-2 donor). total_outflow >= 0.
    indicators: a phase_indicators result of this state; a liquid id is then its tracked label (resolved
    through indicators["labels"]), so the stream follows one physical liquid across a relabelling."""
    if not isinstance(state, ClosureState):
        raise DerivedThermoError("INVALID_INPUT", "phase_draw needs a ClosureState from close_state.")
    if basis not in ("molar", "mass"):
        raise DerivedThermoError("INVALID_INPUT", f"basis must be 'molar' or 'mass', not {basis!r}.")
    if not (np.isfinite(total_outflow) and total_outflow >= 0):
        raise DerivedThermoError("INVALID_INPUT", "total_outflow must be finite and non-negative (donor sign).")
    label = {"liquid-1": "liquido-1", "liquid-2": "liquido-2", "vapour": "vapor"}.get(phase, phase)
    tracked = None
    if indicators is not None and label in indicators.get("labels", {}):
        if indicators.get("fingerprint") != state.fingerprint:
            raise DerivedThermoError("INVALID_INPUT", "indicators belong to another package, species or anchor.")
        tracked = indicators["labels"][label]
    if label in ("vapor", "liquid"):
        kind = label
        chosen = [p for p in state.phases if p.kind == kind]
        if len(chosen) > 1:
            if selection in ("higher_density", "lower_density"):
                chosen = [sorted(chosen, key=lambda p: p.M / p.v, reverse=selection == "higher_density")[0]]
            elif selection != "combined":
                raise DerivedThermoError("PHASE_AMBIGUOUS", f"There are {len(chosen)} {kind} phases; declare "
                                         "selection 'higher_density', 'lower_density' or 'combined'.",
                                         phases=[p.id for p in chosen])
    elif label in ("vapor-1", "liquido-1", "liquido-2"):
        kind = "vapor" if label == "vapor-1" else "liquid"
        target = label if indicators is None or label not in indicators.get("labels", {}) else tracked
        chosen = [p for p in state.phases if p.id == target]
    else:
        raise DerivedThermoError("INVALID_INPUT", f"Unknown phase {phase!r}.")
    nc = len(state.species)
    if not chosen:
        return {"phase": label, "present": False, "molar_flow": 0.0, "mass_flow": 0.0,
                "component_molar_flows": [0.0] * nc, "component_mass_flows": [0.0] * nc, "x": None,
                "molar_enthalpy": None, "enthalpy_flow": 0.0, "molar_mass": None, "phases": []}
    amount = sum(p.amount for p in chosen)
    x = sum(p.amount * np.asarray(p.x) for p in chosen) / amount
    h = sum(p.amount * p.h for p in chosen) / amount
    M_i = _molar_masses(state)
    M = float(x @ M_i)
    F = float(total_outflow) if basis == "molar" else float(total_outflow) / M
    q = F * x
    return {"phase": label, "present": True, "molar_flow": F, "mass_flow": F * M,
            "component_molar_flows": q.tolist(), "component_mass_flows": (q * M_i).tolist(), "x": x.tolist(),
            "molar_enthalpy": float(h), "enthalpy_flow": F * float(h), "molar_mass": M,
            "phases": [p.id for p in chosen]}


def _molar_masses(state):
    return np.asarray(_system(state.package, state.species, state.liquid_only).M, dtype=float)
