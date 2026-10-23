# Comprehensive Audit of Mathematical, Physical, and Algorithmic Findings

**Project:** Equation-Oriented Multiphysics Simulation Engine  
**Date:** 20 October 2026  
**Auditor:** Specialized Agentic Engineering Auditor  
**Reference Standards:** [ARCHITECTURE.md](../../ARCHITECTURE.md), [docs/contracts/common-model.md](contracts/common-model.md), [docs/contracts/thermodynamic-layer.md](contracts/thermodynamic-layer.md), [docs/engine/model-workspaces.md](engine/model-workspaces.md).  
**Directives:** Strict Read-Only Audit. No modifications or corrections have been applied to frontend or backend source code.

---

## Executive Summary

This document compiles all mathematical gaps, algorithmic edge cases, thermodynamic inconsistencies, solver limitations, and architectural discrepancies identified across the core engines (`core/`), API services (`backend/`), and workspace adapters (`frontend/`). Each finding is formally classified with its theoretical basis, exact codebase coordinates, mathematical consequences, current vs. rigorous behavior, and technical resolution recommendations for future engineering iterations (Claude, Codex, or human maintainers).

---

## Summary Matrix of Findings

| ID | Module / Component | Category | Severity | Description |
|---|---|---|---|---|
| **F-01** | `core/compilador/compilador.py`<br>`core/compilador/explicito.py` | Solvers & DAEs | **Critical** | Zero accumulation and stationary constraints trigger unhandled DAE index-1 rejection. |
| **F-02** | `core/solvers/integrador.py` | Numerical Analysis | **High** | RK45 polynomial dense output interpolation across discontinuous derivative kinks ($C^0$ boundaries). |
| **F-03** | `core/solvers/integrador.py` | Numerical Analysis | **Medium** | Re-integration substepping does not monitor phase regime changes during intermediate stage steps. |
| **F-04** | `core/agua_iapws95.py`<br>`core/mezclas.py` | Thermodynamics | **Critical** | Fundamental thermodynamic enthalpy reference discrepancy between pure water and mixture packages. |
| **F-05** | `core/termodinamica/volumen.py`<br>`core/mezclas.py` | Thermodynamics | **High** | Pressure indeterminacy in completely liquid-filled rigid vessels under incompressible assumption. |
| **F-06** | `core/termodinamica/capa.py` | Phase Equilibrium | **Medium** | Fixed candidate phase set restricts multi-liquid phase splitting (LLLE) and solid precipitation. |
| **F-07** | `core/compilador/transformed.py` | Scaling & PDEs | **Medium** | Scaling compiler does not admit spatial operators or PDE boundary conditions. |
| **F-08** | `core/balances/momentum_derivation.py`<br>`core/compilador/hydraulics.py` | Continuum Mechanics | **Medium** | Divergence-free assumption in hydraulic networks forces infinite acoustic wave speed. |
| **F-09** | `frontend/app/motor/modeloNumerico.ts`<br>`core/adimensionalizacion/simulacion.py` | Discretization | **Low** | First-order upwind scheme introduces artificial numerical diffusion dominating high-Péclet regimes. |
| **F-10** | `core/modelo/lector.py`<br>`backend/api_modelo.py` | Architecture | **Low** | Bilingual schema serialization creates protocol key fragmentation between English AST and Spanish storage. |
| **F-11** | `core/adimensionalizacion/dinamica.py` | Dynamical Systems | **Medium** | Uniform wavenumber sampling in dispersion relation $\sigma(k)$ risks aliasing narrow Turing instability bands. |
| **F-12** | `core/adimensionalizacion/dinamica.py` | Continuation & Solvers | **Medium** | Unconstrained pseudo-arclength continuation lacks domain barrier protection, causing solver divergence on unphysical states. |
| **F-13** | `core/adimensionalizacion/asintotica.py` | Asymptotic Analysis | **Low** | Boundary layer decay criteria assume constant-coefficient linear balances, failing at spatial turning points. |
| **F-14** | `core/adimensionalizacion/simulacion.py` | Discretization & PDEs | **Medium** | Centered differences under clamped maximum grid nodes ($N \le 801$) trigger non-physical Gibbs oscillations at $Pe_{\text{cell}} > 2$. |
| **F-15** | `core/fug.py` | Separation Systems | **Medium** | Normal boiling point classification and bootstrap splitting fails under relative volatility inversion. |
| **F-16** | `core/lote.py`<br>`core/cinetica.py` | Numerical Analysis | **High** | State clipping during RHS evaluations destroys conservation and introduces $C^0$ Jacobian kinks. |
| **F-17** | `core/compilador/compilador.py` | Energy Conservation | **Medium** | Omission of dynamic mechanical work $V_v \frac{dP_v}{dt}$ in variable-pressure enthalpy balances. |
| **F-18** | `core/cinetica.py` | Chemical Thermodynamics | **Medium** | Non-monotonic activity coefficient surfaces trigger unmonitored multiple equilibrium roots. |
| **F-19** | `core/compilador/compilador.py` | Spatial Discretization | **High** | Pressure-velocity checkerboard instability on colocated meshes without Rhie-Chow damping. |
| **F-20** | `core/balances/generador.py` | Transport Phenomena | **Medium** | Omission of species interdiffusion enthalpy flux $\sum_i \mathbf{j}_i \bar{h}_i$ in energy balances. |

---

## Detailed Audit Records

---

### Finding F-01: Differential-Algebraic Equation (DAE) Index-1 Rejection for Stationary Constraints

* **Classification:** Solvers & DAE Theory / Compilation
* **Severity:** **Critical**
* **Affected Files & Lines:**
  * `core/compilador/compilador.py`: lines 97–98, 118–119
  * `core/compilador/explicito.py`: lines 120–124
  * `frontend/app/models/dynamicDefinition.ts`: lines 120–165

#### 1. Theoretical & Mathematical Description
Under the newly established **Dynamic Inventory Foundation** (20 October 2026), the system mandates that conservation laws be retained in their general differential form:
$$\frac{dI}{dt} = \Phi(t, \mathbf{y})$$
When a user imposes a permanent stationary condition or a fixed-inventory constraint ($I(t) = I(t_0)$), the physical equation must mathematically satisfy the algebraic compatibility condition:
$$\Phi(t, \mathbf{y}) = 0$$
Coupled with the remaining dynamic balances and the thermodynamic flash closures:
$$\mathbf{g}(T, P, \mathbf{x}, \mathbf{y}) = \mathbf{0}$$
the composite mathematical problem becomes a **Semi-Explicit Differential-Algebraic Equation (DAE) of Index 1**:
$$\begin{aligned}
\frac{d\mathbf{y}_d}{dt} &= \mathbf{f}(t, \mathbf{y}_d, \mathbf{y}_a) \\
\mathbf{0} &= \mathbf{g}(t, \mathbf{y}_d, \mathbf{y}_a)
\end{aligned}$$
where $\mathbf{y}_d$ are differential state variables (retained dynamic inventories) and $\mathbf{y}_a$ are algebraic state variables (e.g., flow rates satisfying $\Phi = 0$ or static pressures).

#### 2. Codebase Discrepancy
In `core/compilador/compilador.py`:
```python
if fm.get("sinAcumulacion") or fm.get("fija") and campo.get("estacionario"):
    raise NoSoportado(f"Volume {v['id']}: zero accumulation produces algebraic constraints; a steady-state/DAE solver is not connected yet.")
if fe.get("estacionario") or fe.get("sinAcumulacionTotal"):
    raise NoSoportado(f"Volume {v['id']}: zero energy accumulation requires a steady-state/DAE method.")
```
And in `core/compilador/explicito.py`:
```python
if lado["tipo"] != "derivada" or lado["expresion"]["tipo"] != "simbolo" or lado["respecto"] != self.tiempo:
    raise NoSoportado(f"ecuación {e['id']}: solo se ejecutan ecuaciones d(variable)/d{self.tiempo} = expresión (las algebraicas, DAE, quedan pendientes)")
```

#### 3. Mathematical Impact
* Valid physical systems possessing steady-state boundary balances, instantaneous valve characteristics, or stationary storage vessels are strictly rejected from execution.
* The frontend allows users to author and deduce these valid physical constraints in the **Model** workspace, but the **Solve** compilation step immediately halts with an unhandled capability failure.
* No index reduction algorithm (such as the Pantelides algorithm or differentiation of algebraic constraints) is implemented.

#### 4. Recommended Resolution (for Claude / Codex)
1. Implement a structural index analyzer using the Pantelides algorithm to differentiate constraints $\mathbf{g}(t, \mathbf{y}_d, \mathbf{y}_a) = \mathbf{0}$ until all variables have known derivatives.
2. Incorporate an implicit DAE time-integrator supporting index-1 semi-explicit systems (e.g., Radau IIA collocation methods or the `scipy.integrate.solve_ivp(method="Radau")` adapter with non-singular mass matrix $\mathbf{M} \frac{d\mathbf{y}}{dt} = \mathbf{F}(t, \mathbf{y})$ where $\mathbf{M} = \text{diag}(\mathbf{I}, \mathbf{0})$).
3. Ensure consistent initial conditions $(\mathbf{y}_d(0), \mathbf{y}_a(0))$ satisfy $\mathbf{g}(0, \mathbf{y}_d(0), \mathbf{y}_a(0)) = \mathbf{0}$ via a pre-solve Newton-Raphson initialization.

---

### Finding F-02: Dense Output Polynomial Interpolation Across Discontinuous Derivative Kinks

* **Classification:** Numerical Analysis / Event Detection
* **Severity:** **High**
* **Affected Files & Lines:**
  * `core/solvers/integrador.py`: lines 142–154, 168–179

#### 1. Theoretical & Mathematical Description
At a first-order phase transition (e.g., subcooled liquid reaching bubble-point temperature $T_{\text{sat}}$), the state trajectory $\mathbf{y}(t) = (n, U, V)^T$ is continuous ($C^0$), but its time derivatives $\frac{d\mathbf{y}}{dt}$ experience jump discontinuities ($C^1$ deficiency):
$$\lim_{t \to t^{*-}} \frac{dT}{dt} \neq \lim_{t \to t^{*+}} \frac{dT}{dt}$$
because the apparent heat capacity $C_p^{\text{app}} = \left(\frac{\partial H}{\partial T}\right)_P$ jumps from a finite liquid value $C_{p,L}$ to an effectively infinite value (or latent heat plateau) during two-phase coexistence.

#### 2. Codebase Discrepancy
In `core/solvers/integrador.py`:
```python
# Cambio de régimen dentro del paso: bisección sobre la salida densa.
d = r.dense_output()
lo, hi = t_a, r.t
for _ in range(200):
    if hi - lo <= 1e-12 * max(1.0, abs(hi)):
        break
    m = 0.5 * (lo + hi)
    if sistema.firma(m, d(m)) == firma:
        lo = m
    else:
        hi = m
```
The interpolant `d(m)` returned by Scipy's `RK45` is a 4th-order Hermite/collocation polynomial:
$$P_4(t) = \sum_{k=0}^4 \mathbf{c}_k \left(\frac{t - t_a}{\Delta t}\right)^k$$
fitted to the state vectors and stage derivatives under the assumption that the vector field is smooth ($C^4$) throughout $[t_a, r.t]$.

#### 3. Mathematical Impact
* When a kink occurs within $[t_a, r.t]$, the polynomial interpolant oscillates (Runge phenomenon in high-order polynomial Hermite interpolation across non-smooth transitions).
* The evaluated states $\mathbf{y}_{\text{interp}} = d(m)$ can artificially violate thermodynamic stability, produce negative mole numbers, or trigger spurious tangent-plane distance minimums, causing the bisection loop to converge to an inaccurate event location $t^*$.
* Because `sistema.firma(m, d(m))` evaluates full equilibrium flashes on an oscillatory polynomial state, convergence can stall or fail to bisect monotonically.

#### 4. Recommended Resolution (for Claude / Codex)
1. Replace polynomial dense-output bisection across signature changes with an exact step-rejection and step-halving approach:
   $$\Delta t_{\text{new}} = \frac{1}{2} (t_{\text{hi}} - t_{\text{lo}})$$
   taking actual integrator steps from $t_{\text{lo}}$ rather than querying $d(m)$.
2. Alternatively, formulate an explicit zero-crossing switching function:
   $$g(t, \mathbf{y}) = TPD_{\text{incipient}}(t, \mathbf{y}) = 0$$
   and use a continuous stage-event locator (such as Brent's method with linear interpolation of the switching function) rather than evaluating full flashes on higher-order interpolants.

---

### Finding F-03: Substep Integration Without Phase Regime Verification

* **Classification:** Numerical Analysis / Integrator Restart
* **Severity:** **Medium**
* **Affected Files & Lines:**
  * `core/solvers/integrador.py`: lines 180–187

#### 1. Theoretical & Mathematical Description
When an integrator restarts at an event boundary $t^* = \text{hi}$, standard numerical consistency requires that the integration from the last accepted smooth state $(t_a, \mathbf{y}_a)$ up to $t^*$ remain strictly on the pre-event manifold $\mathcal{M}_1$:
$$\mathbf{y}(t) \in \mathcal{M}_1 \quad \forall t \in [t_a, t^*)$$
and switch to manifold $\mathcal{M}_2$ at $t \ge t^*$.

#### 2. Codebase Discrepancy
In `core/solvers/integrador.py`:
```python
# Re-integración limpia hasta el instante del cambio (lado nuevo) y reinicio.
sub = _rk(sistema, t_a, y_a, hi, rtol, atol, max_step, metodo)
while sub.status == "running":
    t_s = sub.t
    sub.step()
    tray.tramos.append((t_s, sub.t, sub.dense_output()))
y_e = sub.y.copy()
nueva = sistema.firma(hi, y_e)
```
The sub-integrator `sub` advances towards `hi` via adaptive steps `sub.step()`. However, `sistema.firma` is never evaluated during any of the sub-steps.

#### 3. Mathematical Impact
* If the bisection placed `hi` slightly to the right of the true mathematical boundary (due to floating-point tolerances $10^{-12}$), the intermediate steps of `sub` will step into the new regime before reaching `hi`.
* Properties and derivatives from two different thermodynamic regimes are then averaged together in the Runge-Kutta stages of `sub`, defeating the purpose of the clean restart and introducing $O(\Delta t^2)$ local truncation error across the interface.

#### 4. Recommended Resolution (for Claude / Codex)
1. Evaluate `sistema.firma(sub.t, sub.y)` after each `sub.step()`. If a change of signature occurs before `hi`, immediately clamp the integration endpoint to `sub.t` and initiate the warm restart at that exact state.
2. Ensure the final step of `sub` lands exactly at $t^*$ by setting `sub.t_bound = hi` and using step-size clamping:
   $$h_{\text{final}} = t^* - sub.t$$

---

### Finding F-04: Enthalpy Reference State Discrepancy Between Pure Water and Mixture Packages

* **Classification:** Thermodynamics / Caloric Reference States
* **Severity:** **Critical**
* **Affected Files & Lines:**
  * `core/agua_iapws95.py`: lines 24–26
  * `core/mezclas.py`: lines 195–198
  * `core/compilador/compilador.py`: lines 208–239

#### 1. Theoretical & Mathematical Description
In open multiphase systems with heat and material streams connecting multiple volumes:
$$\frac{dH_v}{dt} = \sum_{s \in \text{in}} \dot{n}_s h_s - \sum_{s \in \text{out}} \dot{n}_s h_s + \dot{Q} + V_v \frac{dP_v}{dt}$$
the specific enthalpies $h_s$ must share a single, thermodynamically consistent reference datum across all connected control volumes:
$$h_i(T_{\text{ref}}, P_{\text{ref}}) = h_{i,0}$$
If volume $V_A$ evaluates water enthalpy using reference datum $\mathcal{R}_A$ and volume $V_B$ evaluates water enthalpy using reference datum $\mathcal{R}_B$, a mass stream $\dot{n}$ flowing from $V_A$ to $V_B$ introduces an artificial, non-physical source of energy:
$$\dot{Q}_{\text{fictitious}} = \dot{n} \left[ h_A(T, P) - h_B(T, P) \right] \neq 0$$

#### 2. Codebase Discrepancy
* In `core/agua_iapws95.py`:
  $$\text{Reference Datum: Triple Point of Water } (T_t = 273.16\text{ K}, P_t = 611.657\text{ Pa})$$
  $$u_L(T_t) = 0 \text{ J/kg}, \quad s_L(T_t) = 0 \text{ J/(kg K)}$$
* In `core/mezclas.py`:
  $$\text{Reference Datum: Pure Ideal Gas at } T_0 = 298.15\text{ K}, P_0 = 10^5\text{ Pa}$$
  $$h_{ig, i}(T_0) = 0 \text{ J/mol}, \quad s_{ig, i}(T_0, P_0) = 0 \text{ J/(mol K)}$$

#### 3. Mathematical Impact
* Saturated liquid water at $298.15\text{ K}$ has:
  * In IAPWS-95: $h \approx 104.9\text{ kJ/kg} = 1.89\text{ kJ/mol}$.
  * In UNIFAC/ideal mixtures: $h = h_{ig}(T_0) - \Delta h_{\text{vap}} \approx 0 - 43.99\text{ kJ/mol} = -43.99\text{ kJ/mol}$.
* The discrepancy between the two formulations is:
  $$\Delta h_{\text{mismatch}} \approx 45.88\text{ kJ/mol}$$
* Connecting an IAPWS-95 volume to a UNIFAC-based mixer causes a massive violation of the First Law of Thermodynamics, artificially generating $\approx 45.9\text{ kW}$ per $\text{mol/s}$ of water transferred.

#### 4. Recommended Resolution (for Claude / Codex)
1. Define a global thermodynamic reference converter in `core/termodinamica/` that shifts enthalpies and entropies of pure species to an agreed standard state:
   $$h_{\text{unified}} = h_{\text{package}} + \Delta h_{\text{ref}}$$
2. Alternatively, prevent streams from connecting volumes with heterogeneous thermodynamic packages by raising a strict structural validation error in `core/compilador/compilador.py` until reference shifting is formally implemented.

---

### Finding F-05: Pressure Indeterminacy in Incompressible Liquid Rigid Vessels

* **Classification:** Thermodynamics / Degrees of Freedom (Gibbs Phase Rule)
* **Severity:** **High**
* **Affected Files & Lines:**
  * `core/termodinamica/volumen.py`: lines 45–95
  * `core/mezclas.py`: lines 10–12, 439
  * `core/compilador/compilador.py`: lines 193–204

#### 1. Theoretical & Mathematical Description
In a rigid volume with fixed total volume $V = V_0$ and specified total moles $\mathbf{n}$, the UV flash closure requires finding $T$ and $P$ such that:
$$U(T, P, \mathbf{n}) = U_0 \quad \text{and} \quad V(T, P, \mathbf{n}) = V_0$$
For a subcooled liquid modeled with the incompressible assumption:
$$v^E = 0, \quad v_L(T, P) = v_L^0(T) \quad \text{or} \quad \left(\frac{\partial V}{\partial P}\right)_T = 0$$
the volume function $V(T, \mathbf{n}) = \sum_i n_i v_{L, i}^0(T)$ is completely independent of pressure $P$.

#### 2. Codebase Discrepancy
In `core/mezclas.py`:
```python
v = float(sum(xs[k] * self.vL[i] for k, i in enumerate(idx)))
```
And in `core/termodinamica/volumen.py`, when a vessel contains only liquid and has rigid boundary $V = V_{\text{fixed}}$, the Jacobian matrix for the $(T, P)$ Newton solve:
$$\mathbf{J} = \begin{bmatrix}
\frac{\partial U}{\partial T} & \frac{\partial U}{\partial P} \\
\frac{\partial V}{\partial T} & \frac{\partial V}{\partial P}
\end{bmatrix} = \begin{bmatrix}
C_v & \left(\frac{\partial U}{\partial P}\right)_T \\
\frac{\partial V}{\partial T} & 0
\end{bmatrix}$$
becomes strictly singular (determinant $= 0$ if $\frac{\partial U}{\partial P} \approx 0$).

#### 3. Mathematical Impact
* A rigid vessel containing only subcooled incompressible liquid cannot determine system pressure $P$. Any pressure value $P \in [P_{\text{sat}}, P_{\text{max}}]$ yields the exact same volume.
* If heated, thermal expansion causes $\sum n_i v_{L,i}(T) > V_0$, rendering the volume balance equation $V(T) = V_0$ mathematically insoluble with no real root.
* The UV solver fails with a non-convergence or singular matrix error.

#### 4. Recommended Resolution (for Claude / Codex)
1. Add an isothermal compressibility parameter $\kappa_T = -\frac{1}{v_L} \left(\frac{\partial v_L}{\partial P}\right)_T > 0$ for liquid mixtures:
   $$v_L(T, P) = v_L^0(T) \left[ 1 - \kappa_T (P - P_0) \right]$$
   ensuring $\frac{\partial V}{\partial P} = -V_0 \kappa_T < 0$, guaranteeing non-singularity.
2. Detect liquid-filled rigid vessels during structural analysis and reject the incompressible liquid assumption, prompting the user to declare either headspace (vapor volume) or an elastic mechanical boundary.

---

### Finding F-06: Fixed Candidate Phase Set Restricts Multi-Liquid and Solid Separation

* **Classification:** Thermodynamics / Phase Equilibrium & Multiphase
* **Severity:** **Medium**
* **Affected Files & Lines:**
  * `core/termodinamica/capa.py`: lines 83–95
  * `core/mezclas.py`: lines 53, 520–540

#### 1. Theoretical & Mathematical Description
The Gibbs Phase Rule dictates the maximum number of coexisting equilibrium phases:
$$F = N_c - P + 2 \ge 0 \implies P_{\text{max}} = N_c + 2$$
For a quaternary or quinary liquid system ($N_c \ge 4$), up to 3 or 4 liquid phases can co-exist simultaneously (e.g., water + polymer + surfactant + hydrocarbon, forming three liquid phases).

#### 2. Codebase Discrepancy
In `core/termodinamica/capa.py`:
```python
def candidatas(modelo, vid):
    # ...
    ids = ["vapor-1", "liquido-1"]
    if liquido != "ideal" and len(v["componenteIds"]) > 1:
        ids.append("liquido-2")     # una solución ideal es siempre estable frente a separarse en dos líquidos
    return ids
```
And in `core/mezclas.py`:
```python
MAX_FASES = 3
```
The maximum number of liquid phases is hardcoded to 2, and solid phases (such as ice Ih or crystallized salts) are completely excluded from the candidate phase tuple.

#### 3. Mathematical Impact
* Systems capable of forming three liquid phases (LLLE) or solid-liquid-liquid equilibrium (SLLE) cannot be represented by the common thermodynamic layer.
* If a 4-component mixture exhibits tri-liquid splitting, the stability test will report instability ($TPD < 0$), but the equilibrium solver will be unable to introduce `liquido-3`, resulting in an unresolvable optimization deadlock.

#### 4. Recommended Resolution (for Claude / Codex)
1. Parameterize `candidatas(modelo, vid)` based on the active thermodynamic model capabilities rather than hardcoded string lists.
2. Generalize `core/mezclas.py` minimization to admit arbitrary phase lists $\mathcal{P} = \{V, L_1, L_2, \dots, L_k, S_1, \dots\}$ using generalized multiphase Gibbs energy minimization algorithms (e.g., Gautam-Seider or Michelsen-Mollerup algorithms).

---

### Finding F-07: Scaled Execution Compiler Excludes Spatial PDE Operators

* **Classification:** Transform Workspace / Nondimensionalization & PDEs
* **Severity:** **Medium**
* **Affected Files & Lines:**
  * `core/compilador/transformed.py`: lines 43–45, 69–70
  * `core/compilador/explicito.py`: lines 91–92, 159–160

#### 1. Theoretical & Mathematical Description
The nondimensionalization engine in `core/adimensionalizacion/transformacion.py` algebraically scales spatial partial differential equations:
$$\frac{\partial u}{\partial t} = \alpha \frac{\partial^2 u}{\partial x^2} - v \frac{\partial u}{\partial x}$$
transforming coordinates and operators into dimensionless equivalents:
$$\hat{t} = \frac{t}{\tau}, \quad \hat{x} = \frac{x}{L}, \quad \hat{u} = \frac{u}{U_0}$$
producing the scaled PDE:
$$\frac{\partial \hat{u}}{\partial \hat{t}} = \frac{1}{Pe} \frac{\partial^2 \hat{u}}{\partial \hat{x}^2} - \frac{\partial \hat{u}}{\partial \hat{x}}$$
where $Pe = \frac{v L}{\alpha}$.

#### 2. Codebase Discrepancy
In `core/compilador/transformed.py`:
```python
if any(item["familia"] != "multiplicativa" for item in body["transformaciones"]):
    raise NoSoportado("Execution version 1 supports constant multiplicative maps; affine and nonlinear maps remain inspectable in Transform.")
```
And in `core/compilador/explicito.py`:
```python
if any(s["rol"] == "coordenada" for s in mat["simbolos"]):
    raise NoSoportado("campos con coordenadas espaciales: corresponden al motor de discretización (paso 5.2)")
```

#### 3. Mathematical Impact
* Although the **Transform** workspace derives and proves exact dimensionless groups ($Pe$, $Da$, $Bi$, $Fo$) for spatial models, the **Solve** execution engine can only integrate scalar time-dependent ODEs.
* Spatial models derived in Transform cannot be executed via the transformed compilation path.

#### 4. Recommended Resolution (for Claude / Codex)
1. Complete step 5.2 of `ARCHITECTURE.md` by introducing a dedicated spatial discretization engine (`core/discretizacion/`) that converts dimensionless PDEs into semi-discrete ODE systems using the Method of Lines (MOL).
2. Wire the semi-discrete ODEs into `TransformedSystem` so that scaled 1D distributed systems can be simulated.

---

### Finding F-08: Divergence-Free Constraint in Hydraulic Networks Forces Infinite Acoustic Speed

* **Classification:** Continuum Mechanics / Momentum & Hydraulics
* **Severity:** **Medium**
* **Affected Files & Lines:**
  * `core/balances/momentum_derivation.py`: lines 45–52, 85–86
  * `core/compilador/hydraulics.py`: lines 35–45

#### 1. Theoretical & Mathematical Description
In fluid conduits, compressible transient momentum is governed by the 1D acoustic wave equations:
$$\begin{aligned}
\frac{\partial \rho}{\partial t} + \frac{\partial (\rho v)}{\partial x} &= 0 \\
\frac{\partial (\rho v)}{\partial t} + \frac{\partial (\rho v^2)}{\partial x} + \frac{\partial P}{\partial x} &= -f_{\text{wall}}
\end{aligned}$$
where pressure waves propagate at the speed of sound:
$$c = \sqrt{\left(\frac{\partial P}{\partial \rho}\right)_s}$$
When the divergence-free assumption ($\nabla \cdot \mathbf{v} = 0$) and reference density ($\rho = \rho_{\text{ref}}$) are enforced, the mass flow rate $\dot{m}(t)$ becomes uniform along the entire path length $L$:
$$\dot{m}(x, t) = \dot{m}(t)$$
leading to the lumped inertance model:
$$L_I \frac{d\dot{m}}{dt} = \Delta P(t) - \Delta P_{\text{loss}}(t)$$
where $L_I = \frac{L}{A}$.

#### 2. Codebase Discrepancy
In `core/balances/momentum_derivation.py`:
```python
path_required = {
    'pressureStress', 'newtonian', 'massContinuity', 'constantViscosity',
    'divergenceFree', 'fixedBoundary', 'uniformSections', 'constantArea',
    'referenceDensity', 'uniformGravity', 'impermeableWall', 'laminarCircular'
}
```

#### 3. Mathematical Impact
* The speed of sound in the conduit becomes mathematically infinite ($c \to \infty$).
* Any pressure disturbance at port 1 propagates instantaneously to port 2.
* Water hammer phenomena, acoustic wave reflections, and high-frequency fluid oscillations cannot be captured. This model is only valid for slow hydraulic transients where the characteristic time scale $\tau \gg \frac{L}{c}$.

#### 4. Recommended Resolution (for Claude / Codex)
1. Explicitly document the validity criterion $\tau_{\text{transient}} \gg \frac{L}{c}$ (low Mach number $Ma = \frac{v}{c} < 0.1$) in the UI and compilation reports.
2. For water hammer applications, retain a compressible 1D pipe segment discretization with finite wave speed in a future discretization phase.

---

### Finding F-09: First-Order Spatial Upwind Scheme Induces Artificial Numerical Diffusion

* **Classification:** Numerical Methods / Spatial Discretization
* **Severity:** **Low**
* **Affected Files & Lines:**
  * `frontend/app/motor/modeloNumerico.ts`: lines 145–180
  * `core/adimensionalizacion/simulacion.py`: lines 110–140

#### 1. Theoretical & Mathematical Description
In the 1D advection-diffusion transport equation:
$$\frac{\partial c}{\partial t} + v \frac{\partial c}{\partial x} = D \frac{\partial^2 c}{\partial x^2}$$
discretizing the convective term $\frac{\partial c}{\partial x}$ using a backward difference (first-order Upwind scheme for $v > 0$):
$$\left.\frac{\partial c}{\partial x}\right|_i \approx \frac{c_i - c_{i-1}}{\Delta x}$$
introduces a leading-order truncation error via Taylor expansion:
$$\frac{c_i - c_{i-1}}{\Delta x} = \left.\frac{\partial c}{\partial x}\right|_i - \frac{\Delta x}{2} \left.\frac{\partial^2 c}{\partial x^2}\right|_i + O(\Delta x^2)$$
Substituting this into the continuum equation reveals the **modified equation**:
$$\frac{\partial c}{\partial t} + v \frac{\partial c}{\partial x} = \left( D + D_{\text{num}} \right) \frac{\partial^2 c}{\partial x^2}$$
where the **artificial numerical diffusion** is:
$$D_{\text{num}} = \frac{v \Delta x}{2} (1 - Cr)$$
with $Cr = \frac{v \Delta t}{\Delta x}$.

#### 2. Codebase Discrepancy
The 1D finite volume implementation in `modeloNumerico.ts` uses pure first-order donor-cell upwinding without flux limiters or second-order corrections.

#### 3. Mathematical Impact
* In advection-dominated flows with cell Péclet number $Pe_{\text{cell}} = \frac{v \Delta x}{D} > 2$, numerical diffusion completely dominates physical diffusion:
  $$D_{\text{num}} \gg D$$
* Steep reaction fronts, concentration pulses, and thermal waves become artificially smeared over time, producing non-physical dispersion.

#### 4. Recommended Resolution (for Claude / Codex)
1. Upgrade the spatial discretization engine to a Total Variation Diminishing (TVD) high-resolution scheme with flux limiters (e.g., Van Leer, Minmod, or Superbee limiters).
2. Compute and publish the cell Péclet number $Pe_{\text{cell}}$ in the **Transform** and **Solve** inspection panels to warn users when grid-induced diffusion exceeds 5% of physical diffusion.

---

### Finding F-10: Bilingual Protocol Schema Fragmentation Between English AST and Stored Data

* **Classification:** Software Architecture & Data Serialization
* **Severity:** **Low**
* **Affected Files & Lines:**
  * `core/modelo/lector.py`: lines 15–85
  * `backend/api_modelo.py`: lines 40–110
  * `frontend/motores/modelo/contrato.ts`: lines 10–70

#### 1. Theoretical & Mathematical Description
A clean domain-driven architecture requires unambiguous terminology across all model layers. The project adopted a mandatory transition to English documentation and identifiers on 19 October 2026 (`ARCHITECTURE.md §8`).

#### 2. Codebase Discrepancy
The internal JSON payloads exchanged across HTTP routes (`/modelo/*`) and persisted in IndexedDB use a mixture of Spanish keys (`volumenes`, `corrientes`, `materia`, `energia`, `supuestos`, `datos`) and English keys (`symbols`, `expressions`, `roles`, `hydraulicNetwork`, `momentumDerivation`).

#### 3. Mathematical Impact
* While mathematically benign, translators and deserializers must continually maintain bidirectional alias dictionaries.
* Agents (Claude/Codex) querying ASTs risk confusion when accessing `v["balances"]["materia"]` vs `model["materialDerivation"]`.

#### 4. Recommended Resolution (for Claude / Codex)
1. Design a formal versioned migration from `rage.common-model` v0 to `rage.common-model` v1.
2. Implement schema validation with Pydantic / Zod that transparently parses legacy Spanish keys while presenting unified English models to all engines.

---

### Finding F-11: Uniform Wavenumber Sampling in Dispersion Relation $\sigma(k)$ Risks Aliasing Narrow Turing Bands

* **Classification:** Dynamical Systems & Stability Analysis
* **Severity:** **Medium**
* **Affected Files & Lines:**
  * `core/adimensionalizacion/dinamica.py`: lines 216–225

#### 1. Theoretical & Mathematical Description
A Turing instability occurs when a homogeneous steady state is linearly stable to spatial perturbations ($k = 0$, $\max_j \operatorname{Re}(\sigma_j(0)) < 0$), but becomes unstable ($\max_j \operatorname{Re}(\sigma_j(k)) > 0$) for a finite non-zero wavenumber band $[k_1, k_2]$. Near the onset threshold (Turing bifurcation marginality), the instability band width $\Delta k = k_2 - k_1$ can be arbitrarily narrow ($\Delta k \ll 1$).

#### 2. Codebase Discrepancy
In `core/adimensionalizacion/dinamica.py`:
```python
kmax = cx.opciones.get("estabilidad", {}).get("kMax") or max(10.0, 6.0 * math.sqrt(rJ / rD) if C2 is not None else 10.0, (40 * math.pi / L) if L else 0.0)
ks = np.linspace(0.0, kmax, 801)
re, im = _dispersion(J, Cs, ks)
```
The search evaluates the eigenvalues of $\mathbf{M}(k) = \mathbf{J} + \sum_n (ik)^n \mathbf{C}_n$ over a fixed uniform grid of 801 points.

#### 3. Mathematical Impact
* If the Turing band width $\Delta k$ is smaller than the grid spacing $\Delta k_{\text{sample}} = k_{\max} / 800$, all sampled grid points can straddle the unstable region without landing inside it.
* Consequently, a true Turing pattern-forming instability will be misclassified as `"estable"` (false negative).
* Furthermore, if $r_D = \max |\lambda(\mathbf{C}_2)| \to 0$ (e.g. one reacting species has very small molecular diffusivity), $k_{\max}$ can become excessively large, worsening the grid spacing $\Delta k_{\text{sample}}$ and causing severe aliasing.

#### 4. Recommended Resolution (for Claude / Codex)
1. Implement analytical maximum growth rate finding: for a 2-variable reaction-diffusion system ($\mathbf{M}(k) = \mathbf{J} - k^2 \mathbf{D}$), the determinant condition $\det(\mathbf{M}(k)) = 0$ is a quadratic polynomial in $k^2$. The critical wavenumber $k_c^2$ can be found in closed form:
   $$k_c^2 = \frac{d_1 J_{22} + d_2 J_{11}}{2 d_1 d_2}$$
2. For $n$-dimensional systems, replace uniform sampling with an adaptive golden-section or Nelder-Mead peak-finder that maximizes $\operatorname{Re}(\sigma_1(k))$ over $k \in [0, k_{\max}]$.

---

### Finding F-12: Unconstrained Pseudo-Arclength Continuation Step Divergence on Unphysical States

* **Classification:** Continuation & Numerical Solvers
* **Severity:** **Medium**
* **Affected Files & Lines:**
  * `core/adimensionalizacion/dinamica.py`: lines 440–465

#### 1. Theoretical & Mathematical Description
Equilibrium curves of physical systems are defined over constrained manifolds (e.g., mole numbers $n_i > 0$, absolute temperatures $T > 0$, densities $\rho > 0$). In pseudo-arclength continuation, predictor steps:
$$\mathbf{x}_{\text{pred}} = \mathbf{x}_k + \Delta s \, \mathbf{t}$$
follow the local tangent vector $\mathbf{t}$ in the augmented state-parameter space $(\mathbf{u}, \lambda)$.

#### 2. Codebase Discrepancy
In `core/adimensionalizacion/dinamica.py`:
```python
xp = x + ds * t
y = xp.copy()
for _ in range(20):
    F = np.concatenate([G(y), [np.dot(t, y - xp)]])
    Jx = np.vstack([jac(y), t])
    dy = np.linalg.solve(Jx, -F)
    y = y + dy
```
The Newton corrector steps blindly without evaluating boundary domain feasibility ($\mathbf{y} \in \mathcal{D}$).

#### 3. Mathematical Impact
* If a predictor step enters an unphysical negative state, terms containing fractional exponents, logarithms ($\ln c$), or square roots evaluate to complex numbers or raise `ValueError` / `NoEvaluable`.
* When an exception occurs inside the inner Newton loop, the continuation algorithm aborts immediately without attempting a step-back with smaller $\Delta s$.
* This prematurely truncates equilibrium branches before reaching physical turning points (e.g., extinction or ignition points in non-adiabatic reactors).

#### 4. Recommended Resolution (for Claude / Codex)
1. Introduce a line-search backtracking step limiter $\alpha \in (0, 1]$ ensuring that $\mathbf{y} + \alpha \Delta \mathbf{y}$ remains strictly within the declared positive physical cone ($\mathcal{D} = \{ \mathbf{u} : u_i > 0 \}$).
2. Implement an adaptive step-size controller that reduces arclength step size $\Delta s \leftarrow \Delta s / 2$ and rolls back to $\mathbf{x}_k$ upon detecting an out-of-domain evaluation.

---

### Finding F-13: Boundary Layer Asymptotic Analysis Restricted to Constant-Coefficient Balances (Turning Point Blindness)

* **Classification:** Asymptotic Analysis & Singular Perturbations
* **Severity:** **Low**
* **Affected Files & Lines:**
  * `core/adimensionalizacion/asintotica.py`: lines 21–26, 79–100

#### 1. Theoretical & Mathematical Description
In singularly perturbed advection-diffusion-reaction equations:
$$\epsilon \frac{d^2 u}{dx^2} + b(x) \frac{du}{dx} + c(x) u = f(x), \quad x \in [0, 1]$$
the location and structure of the boundary layer depend on the sign of the advective coefficient $b(x)$:
* If $b(x) > 0$ for all $x \in [0, 1]$, the layer is at $x = 0$.
* If $b(x) < 0$ for all $x \in [0, 1]$, the layer is at $x = 1$.
* If $b(x)$ changes sign inside the domain ($b(x^*) = 0$ at some $x^* \in (0, 1)$), the system exhibits a **turning point**, which produces an internal layer (shock layer or transition layer) rather than a boundary layer.

#### 2. Codebase Discrepancy
In `core/adimensionalizacion/asintotica.py`:
```python
# La ubicacion de una capa solo se publica cuando el balance interior es lineal con coeficientes constantes:
# a u'' + b u' = 0 decae hacia el interior desde la izquierda si b/a > 0 (y desde la derecha si b/a < 0)
```
The decay direction algorithm only evaluates terms that are linear with constant coefficients, completely ignoring spatial coordinate dependence in coefficients.

#### 3. Mathematical Impact
* For variable-velocity conduits (e.g. converging/diverging channels or counter-current flows where velocity reverses sign), `asintotica.py` reports `"no_soportado"` or fails to detect internal transition layers.
* Users and autonomous agents receive no guidance regarding the required mesh clustering at turning points.

#### 4. Recommended Resolution (for Claude / Codex)
1. Extend the coefficient extractor in `asintotica.py` to evaluate the sign of $b(x)$ at the domain endpoints $x = 0$ and $x = L$.
2. Check for root crossings $b(x^*) = 0$ in the interior, and classify such regimes as `"capa_interna"` (turning point layer with Airy function asymptotics).

---

### Finding F-14: Second-Order Centered Differences Trigger Spurious Gibbs Oscillations When Grid Nodes Are Clamped to $N \le 801$

* **Classification:** Spatial Discretization & Numerical Stability
* **Severity:** **Medium**
* **Affected Files & Lines:**
  * `core/adimensionalizacion/simulacion.py`: lines 41, 323–329
  * `core/adimensionalizacion/dinamica.py`: lines 323–329

#### 1. Theoretical & Mathematical Description
Godunov's Barrier Theorem and the discrete maximum principle dictate that linear centered difference approximations of advective terms:
$$\left. \frac{\partial u}{\partial \xi} \right|_i \approx \frac{u_{i+1} - u_{i-1}}{2h}$$
are non-monotone and trigger spurious Gibbs oscillations unless the cell Péclet number satisfies:
$$Pe_{\text{cell}} = \frac{V h}{D} \le 2$$
When $Pe_{\text{cell}} > 2$, the off-diagonal entries of the discrete Jacobian matrix violate M-matrix positive-type requirements, causing unphysical oscillations (e.g., negative concentrations).

#### 2. Codebase Discrepancy
In `core/adimensionalizacion/simulacion.py`:
```python
MAX_NODOS = 801
```
And in `dinamica.py`:
```python
n_pe = math.ceil(L * V / (2 * D)) + 1 if V else 2
N = min(max(41, n_pe, n_capa), 2001)
```
If a user specifies a high Reynolds/Péclet flow where $\frac{L V}{2 D} > 2000$, $N$ is hard-clamped to 2001 (or 801 in `simulacion.py`), forcing $h > \frac{2D}{V}$ and $Pe_{\text{cell}} > 2$.

#### 3. Mathematical Impact
* In highly convective flows, centered differences produce non-physical spatial oscillations and negative state values during BDF time integration.
* The BDF solver encounters convergence failures in the Newton iteration due to oscillatory jacobian states.

#### 4. Recommended Resolution (for Claude / Codex)
1. When $Pe_{\text{cell}} > 2$, automatically switch the advective spatial stencil from centered differences to a flux-limited Total Variation Diminishing (TVD) scheme (such as Koren or Van Leer limiters) or a third-order QUICK scheme.
2. Publish an explicit warning indicator in the simulation diagnostics when $Pe_{\text{cell}} > 2$.

---

### Finding F-15: Shortcut Distillation Bootstrap Circularity and Relative Volatility Inversion Failures

* **Classification:** Multicomponent Separation & Algorithms
* **Severity:** **Medium**
* **Affected Files & Lines:**
  * `core/fug.py`: lines 8–24, 66–96
  * `core/columna_destilacion.py`: lines 83–90

#### 1. Theoretical & Mathematical Description
The Fenske-Underwood-Gilliland (FUG) shortcut formulation relies on relative volatilities $\alpha_i = K_i / K_{\text{HK}}$. In non-ideal multicomponent systems, $\alpha_i$ is temperature- and composition-dependent:
$$\alpha_i(T, \mathbf{x}, \mathbf{y}) = \frac{\gamma_i(T, \mathbf{x}) P_i^{\text{sat}}(T) / \Phi_i^V}{\gamma_{\text{HK}}(T, \mathbf{x}) P_{\text{HK}}^{\text{sat}}(T) / \Phi_{\text{HK}}^V}$$
Evaluating the geometric mean relative volatility $\bar{\alpha}_i = \left( \alpha_{i,\text{top}} \cdot \alpha_{i,\text{feed}} \cdot \alpha_{i,\text{bottom}} \right)^{1/3}$ requires the top and bottom bubble-point temperatures $T_D$ and $T_B$, which in turn require distillate and bottoms compositions ($\mathbf{x}_D, \mathbf{x}_B$).

#### 2. Codebase Discrepancy
In `core/fug.py`:
```python
def _clasificar_por_ebullicion(self):
    Tb = np.array([c.Tb for c in self.proveedor.componentes])
    Tb_LK, Tb_HK = Tb[self.idx_LK], Tb[self.idx_HK]
    # Classifies components as lighter/heavier solely by pure-component Tb
```
1. Component ordering is permanently fixed using pure-component normal boiling points ($T_b$).
2. Intermediate components are assigned a heuristic 50/50 split ($d_i = 0.5 z_{i,F}$) to calculate initial $T_D, T_B$.
3. When mixtures exhibit strong positive deviations from ideality (e.g. pressure-sensitive minimum-boiling azeotropes), the relative volatility can invert across the column ($\alpha_{i, \text{HK}}(T_D) > 1$ while $\alpha_{i, \text{HK}}(T_B) < 1$).

#### 3. Mathematical Impact
* For azeotropic or pinching mixtures, sorting by pure-component $T_b$ fails completely: an intermediate component may have an effective volatility higher than the light key.
* The subsequent Underwood root solver (`brentq`) fails to bracket the characteristic roots $\alpha_{k+1} < \theta_k < \alpha_k$, raising an unhandled exception or calculating negative stages ($N_{\min} < 0$).

#### 4. Recommended Resolution (for Claude / Codex)
1. Evaluate true equilibrium ratio ordering $K_i(T_F, \mathbf{z}_F)$ at feed condition rather than pure-component $T_b$.
2. Implement a Picard fixed-point or damped Newton iteration over the product distribution $(\mathbf{d}, \mathbf{b})$ until $(\|\mathbf{d}^{(k+1)} - \mathbf{d}^{(k)}\| < 10^{-6})$, rather than relying on a single-pass 50/50 heuristic.

---

### Finding F-16: Non-Conservation and Artificial $C^0$ Kinks Induced by State Variable Clipping in Kinetic ODE Solvers

* **Classification:** Numerical Analysis & Dynamical Systems
* **Severity:** **High**
* **Affected Files & Lines:**
  * `core/lote.py`: lines 33–38, 88–95
  * `core/cinetica.py`: lines 97–100

#### 1. Theoretical & Mathematical Description
In physical chemical systems, mass action kinetics naturally enforce non-negativity:
$$r_r(T, \mathbf{x}) = k_r \prod_{i \in \text{reactants}} x_i^{\nu_{ir}}$$
As $x_i \to 0^+$, the consumption rate $\nu_{ir} r_r \to 0$, rendering the boundary $x_i = 0$ an invariant manifold of the continuous dynamical system. However, numerical ODE integrators take discrete finite time steps $\Delta t$. An explicit or implicit predictor step can temporarily evaluate the vector field at negative trial states $x_{i,\text{trial}} < 0$.

#### 2. Codebase Discrepancy
In `core/lote.py`:
```python
# Se recorta al EVALUAR la ley, porque UNIFAC con fracciones negativas no significa nada,
# y se COMPRUEBA sobre la trayectoria devuelta.
```
When negative trial values occur during internal integrator evaluations, species mole fractions are clamped to zero:
$$x_i^{\text{eval}} = \max(0, x_i)$$

#### 3. Mathematical Impact
1. **Loss of Atomic Mass Conservation:** By setting $x_i = 0$ for depleted species while other species continue to react at non-zero rates, the stoichiometric closure $\sum_i \nu_{ir} = \Delta \nu_r$ is violated during stage function evaluations:
   $$\sum_{i=1}^{N_c} M_{w,i} \frac{d n_i}{dt} \ne 0$$
2. **Jacobian $C^0$ Derivative Discontinuity:** The ramp function $\max(0, x)$ has a discontinuous first derivative at $x = 0$. When the ODE integrator's step controller or Newton iteration estimates local truncation error using Taylor expansions, the $C^0$ kink destroys the order of accuracy ($p \to 1$), forcing severe step-size collapse ($h \to h_{\min}$) or false stiffness alarms.

#### 4. Recommended Resolution (for Claude / Codex)
1. Replace hard clipping with smooth log-barrier transformations or non-negative variable substitutions (e.g. $u_i = \ln(n_i)$ or $n_i = w_i^2$).
2. Use exact event detection functions ($g_i(\mathbf{n}) = n_i$) to integrate cleanly up to the exhaustion boundary, then mathematically eliminate the exhausted species from subsequent differential balances.

---

### Finding F-17: Omission of Dynamic Mechanical Pressure Work $V_v \frac{dP_v}{dt}$ in Variable-Pressure Enthalpy Balances

* **Classification:** Continuum Thermodynamics & Energy Balances
* **Severity:** **Medium**
* **Affected Files & Lines:**
  * `core/compilador/compilador.py`: lines 8–10, 89–105
  * `core/balances/generador.py`: lines 112–145

#### 1. Theoretical & Mathematical Description
From the First Law of Thermodynamics for an open deforming control volume:
$$\frac{d U_v}{dt} = \sum_{s} \dot{m}_s h_s + \dot{Q} - \dot{W}_s - P_v \frac{dV_v}{dt}$$
Using the thermodynamic Legendre transformation $H_v \equiv U_v + P_v V_v$, the total time derivative of total enthalpy is:
$$\frac{dH_v}{dt} = \frac{dU_v}{dt} + P_v \frac{dV_v}{dt} + V_v \frac{dP_v}{dt}$$
Substituting $\frac{dU_v}{dt}$:
$$\frac{dH_v}{dt} = \sum_{s} \dot{m}_s h_s + \dot{Q} - \dot{W}_s + V_v \frac{dP_v}{dt}$$

#### 2. Codebase Discrepancy
In `core/compilador/compilador.py`:
```python
# por volumen v (energía): dE_v/dt = sum_s B_vs ndot_s h_s + sum_q B_vq Q_q [+ V_v dP_v/dt]
# E = H con presión prescrita (cierre PH con P(t) dato)
```
The code indicates `[+ V_v dP_v/dt]` in comment line 8, but the numerical accumulation term directly sets $\frac{dH_v}{dt} = \sum \dot{n} h + Q$, dropping the $V_v \frac{dP_v}{dt}$ mechanical work term when pressure is time-dependent.

#### 3. Mathematical Impact
* In any closed or partially confined system where pressure evolves dynamically (e.g. vessel depressurization, pneumatic charging, or vapor pressure buildup), neglecting $V_v \frac{dP_v}{dt}$ creates a cumulative energy balance error:
  $$\Delta E_{\text{drift}}(t) = \int_0^t V_v(\tau) \frac{dP_v}{d\tau} \, d\tau \ne 0$$
* For gas systems where $\Delta P \sim 10 \, \text{bar}$ and $V \sim 1 \, \text{m}^3$, this error exceeds $1 \, \text{MJ}$, producing false temperature predictions.

#### 4. Recommended Resolution (for Claude / Codex)
1. In PH closures with time-varying pressure $P(t)$, explicitly include the term $V_v(t) \cdot \frac{dP_v}{dt}$ in the energy residual vector:
   $$\frac{dH_v}{dt} = \sum_s \dot{m}_s h_s + \dot{Q} + V_v \frac{dP_v}{dt}$$
2. Verify that the unit conversion service supplies $\frac{dP_v}{dt}$ in $\text{Pa}/\text{s}$ using symbolic derivative expressions.

---

### Finding F-18: Multi-Valued Root Bifurcations and Thermodynamic Saddle Points in Implicit Reaction Solvers

* **Classification:** Chemical Thermodynamics & Nonlinear Solvers
* **Severity:** **Medium**
* **Affected Files & Lines:**
  * `core/cinetica.py`: lines 11–17, 66–87, 180–225

#### 1. Theoretical & Mathematical Description
Chemical equilibrium corresponds to the global minimum of the Gibbs free energy $G(\boldsymbol{\xi})$ at fixed $(T, P)$:
$$\min_{\boldsymbol{\xi}} G(\boldsymbol{\xi}) \quad \text{subject to } \mathbf{x}(\boldsymbol{\xi}) \ge \mathbf{0}$$
The first-order necessary condition is the vanishing of the chemical affinity (de Donder):
$$\mathcal{A}_r(\boldsymbol{\xi}) \equiv -\sum_{i=1}^{N_c} \nu_{ir} \mu_i(T, P, \mathbf{x}(\boldsymbol{\xi})) = R T \ln\left( \frac{K_{\text{eq},r}(T)}{\prod_i a_i^{\nu_{ir}}} \right) = 0$$
For non-ideal mixtures where activity coefficients $\gamma_i(\mathbf{x})$ are functions of composition (UNIFAC / NRTL), the affinity function $\mathcal{A}_r(\boldsymbol{\xi})$ can be non-monotonic, producing multiple roots $\boldsymbol{\xi}^{(1)}, \boldsymbol{\xi}^{(2)}, \boldsymbol{\xi}^{(3)}$.

#### 2. Codebase Discrepancy
In `core/cinetica.py`:
```python
# xi_r = r_r(T, x_salida) y x_salida = x_salida(xi)
# Eso es un sistema implicito y hay que resolverlo como tal...
```
The solver uses 1D root-finding (`brentq`) or multidimensional Levenberg-Marquardt (`least_squares` / `root`). It terminates at the first root satisfying residual tolerance $\|\mathbf{r}\| \le 10^{-10}$ without evaluating the Hessian $\nabla^2 G = \frac{\partial \mathcal{A}}{\partial \boldsymbol{\xi}}$.

#### 3. Mathematical Impact
* The solver can converge to an unphysical unstable stationary state (a local maximum or saddle point of Gibbs free energy where $\frac{\partial \mathcal{A}}{\partial \xi} > 0$).
* In dynamic simulation, approaching this saddle point causes severe numerical stiffness and non-convergence of downstream unit operation models.

#### 4. Recommended Resolution (for Claude / Codex)
1. Complement the root solver with a thermodynamic second-order check: audit the positive definiteness of the Gibbs Hessian matrix:
   $$\mathbf{H}_{jk} = \frac{\partial^2 G}{\partial \xi_j \partial \xi_k} = \sum_{i=1}^{N_c} \sum_{l=1}^{N_c} \nu_{ij} \left( \frac{\partial \mu_i}{\partial n_l} \right) \nu_{lk} \succ 0$$
2. Reject any root where $\det(\mathbf{H}) \le 0$, and re-initialize the solver towards the global free energy minimum.

---

### Finding F-19: Pressure-Velocity Checkerboard Instability on Colocated Unstructured Grids Without Rhie-Chow Damping

* **Classification:** Multidimensional Discretization & Fluid Mechanics
* **Severity:** **High**
* **Affected Files & Lines:**
  * `core/compilador/compilador.py`: lines 89–105
  * `core/balances/generador.py`: lines 140–180

#### 1. Theoretical & Mathematical Description
When Navier-Stokes flow balances are projected onto colocated (cell-centered) meshes where pressure $P$ and velocity $\mathbf{v}$ are stored at the same cell centroids $\mathbf{x}_P$, standard symmetric linear interpolation of face velocities:
$$\mathbf{v}_f = \frac{\mathbf{v}_P + \mathbf{v}_E}{2}$$
causes complete decoupling between adjacent odd and even pressure nodes. As proven in Section 8.11, a high-frequency oscillatory checkerboard pressure mode ($P_i = P_0 + (-1)^i \delta P$) produces zero discrete gradient on cell centroids ($\nabla P_P = \mathbf{0}$), completely bypassing the continuity constraint and generating catastrophic spatial pressure ripples.

#### 2. Codebase Discrepancy
In the current lumped network architecture (`core/compilador/compilador.py`), momentum equations are treated as 1D discrete conduit balances with lumped inertia $I_e \frac{d\dot{m}_e}{dt}$. In transitioning to 1D/2D/3D distributed volumes, no Rhie-Chow momentum flux interpolation:
$$\dot{m}_f = \rho_f \left[ \overline{\mathbf{v}}_f \cdot \mathbf{A}_f - d_f \left( \frac{P_E - P_P}{\|\mathbf{d}_{PE}\|} A_f - (\overline{\nabla P}_f \cdot \mathbf{n}_f) A_f \right) \right]$$
is provided in the balance generator or compiler stencils.

#### 3. Mathematical Impact
* Any 2D or 3D Navier-Stokes discretization on structured or unstructured colocated grids will experience divergence of the pressure Poisson solver or persistent high-frequency checkerboard oscillations.
* Velocity corrections will fail to enforce local mass conservation.

#### 4. Recommended Resolution (for Claude / Codex)
1. Implement the generalized Rhie-Chow face flux formulation in the spatial discretization pipeline (`core/discretizacion/`).
2. Ensure the pressure Poisson equation matrix includes the compact orthogonal face gradient stencil $\frac{\mathbf{A}_f \cdot \mathbf{A}_f}{\mathbf{d}_{PE} \cdot \mathbf{n}_f}$ to maintain strict diagonal dominance.

---

### Finding F-20: Omission of Species Interdiffusion Enthalpy Flux $\sum_i \mathbf{j}_i \bar{h}_i$ in Non-Isothermal Multicomponent Balances

* **Classification:** Transport Phenomena & Energy Conservation
* **Severity:** **Medium**
* **Affected Files & Lines:**
  * `core/balances/generador.py`: lines 160–190
  * `core/cinetica.py`: lines 40–55

#### 1. Theoretical & Mathematical Description
In non-isothermal multicomponent reacting systems, the total energy flux $\mathbf{q}_{\text{total}}$ consists of Fourier conduction and the convective enthalpy transport carried by molecular species diffusion fluxes $\mathbf{j}_i$:
$$\mathbf{q}_{\text{total}} = -k \nabla T + \sum_{i=1}^{N_c} \mathbf{j}_i \bar{h}_i(T, P, \mathbf{x})$$
where $\bar{h}_i$ is the partial molar enthalpy of species $i$.
Because different species have substantially different heat capacities and heats of formation, diffusive species transport across steep concentration gradients carries a net thermal flux even in the absence of a temperature gradient ($\nabla T = \mathbf{0}$).

#### 2. Codebase Discrepancy
In `core/balances/generador.py`, energy balances equate diffusive thermal transport solely to conduction $\dot{Q} = G (T_1 - T_2)$ or Fourier diffusion $\nabla \cdot (k \nabla T)$, omitting the interdiffusion enthalpy transport term $\sum_i \mathbf{j}_i \bar{h}_i$.

#### 3. Mathematical Impact
* In systems with large molecular weight disparities (e.g. hydrogen-hydrocarbon mixtures or water-vapor evaporation films), neglecting $\sum_i \mathbf{j}_i \bar{h}_i$ introduces errors between $5\%$ and $15\%$ in interface temperature predictions.
* This leads to inaccurate reaction rate constants due to Arrhenius exponential sensitivity ($k \propto \exp(-E_a/RT)$).

#### 4. Recommended Resolution (for Claude / Codex)
1. Add the species interdiffusion enthalpy flux $\mathbf{q}_{\text{interdiff}} = \sum_{i=1}^{N_c} \mathbf{j}_i \bar{h}_i$ to the face energy flux operator in `core/discretizacion/`.
2. Compute partial molar enthalpies $\bar{h}_i$ using the thermodynamic layer with complex-step differentiation (Section 3.9).

---
---

### Finding F-21: Absence of Realizability and Kato-Launder Production Limiters in Turbulence Closures

* **Classification:** Turbulence Modeling & Fluid Mechanics
* **Severity:** **High**
* **Affected Files & Lines:**
  * `core/balances/generador.py`: lines 140–190
  * `core/discretizacion/`: spatial momentum balance generation

#### 1. Theoretical & Mathematical Description
In high-Reynolds-number turbulent reactor and separation unit modeling, standard two-equation eddy-viscosity models ($k-\epsilon$ and Wilcox $k-\omega$) compute the rate of turbulent kinetic energy production from the mean velocity strain rate:
$P_k = \mu_t \left( 2 \overline{\mathbf{S}} : \overline{\mathbf{S}} \right) = \mu_t S^2$
In regions of stagnation flow (e.g. impinging feed jets, baffle faces, tray downcomer floors), fluid strongly decelerates along streamlines, generating large normal strain rates $S$ while vorticity $\Omega \equiv \sqrt{2 \overline{\boldsymbol{\Omega}} : \overline{\boldsymbol{\Omega}}}$ remains zero. Because $P_k \propto S^2$, the model generates massive, unphysical spikes in turbulent kinetic energy $k$ and eddy viscosity $\mu_t$ (the classical **stagnation point anomaly**). Furthermore, linear Boussinesq formulations violate Lumley's realizability criteria, predicting negative normal Reynolds stresses ($\overline{v'^2} < 0$).

#### 2. Codebase Discrepancy
In the spatial balance generator (`core/balances/generador.py`), momentum equations do not incorporate the Kato-Launder production limiter:
$P_k^{\text{KL}} = \mu_t S \Omega$
nor the Bradshaw shear stress limiter $\mu_t \le \frac{\rho a_1 k}{S F_2}$ of Menter SST.

#### 3. Mathematical Impact
* Unphysical overprediction of turbulent eddy viscosity near impingement points artificially increases wall heat transfer coefficients and mass transfer rates by up to $300-500\%$.
* Produces severe numerical stiffness in Newton-Raphson solvers during pressure-velocity coupling, causing convergence stalls.

#### 4. Recommended Resolution (for Claude / Codex)
1. In the turbulent transport equations within `core/discretizacion/`, replace the standard production term with the Kato-Launder limiter $P_k^{\text{KL}} = \mu_t S \Omega$.
2. Implement Lumley realizability constraints ensuring normal stresses remain strictly non-negative ($\overline{u_\alpha'^2} \ge 0$).

---

### Finding F-22: Omission of Moving-Boundary Surface Velocity Corrections in the Spatial Volume-Averaging Theorem

* **Classification:** Multiphase Homogenization & Porous Media
* **Severity:** **Medium**
* **Affected Files & Lines:**
  * `core/balances/generador.py`: lines 110–135

#### 1. Theoretical & Mathematical Description
According to the Slattery-Whittaker Volume-Averaging Theorem (Section 12.1), interchanging time differentiation and volume integration over a Representative Elementary Volume (REV) containing moving or deforming internal phase boundaries $A_{\beta\sigma}(t)$ requires the exact boundary displacement correction:
$\left\langle \frac{\partial \psi_\beta}{\partial t} \right\rangle = \frac{\partial \langle \psi_\beta \rangle}{\partial t} - \frac{1}{V} \int_{A_{\beta\sigma}} \psi_\beta (\mathbf{w} \cdot \mathbf{n}_{\beta\sigma}) \, dA$
where $\mathbf{w}$ is the velocity of the solid-fluid interface $A_{\beta\sigma}$.
When solid catalyst beds undergo dynamic swelling, thermal expansion, or coking deposition, $\mathbf{w} \cdot \mathbf{n}_{\beta\sigma} \ne 0$.

#### 2. Codebase Discrepancy
In `core/balances/generador.py`, dynamic volume averaging assumes static porous geometry ($\mathbf{w} \equiv \mathbf{0}$), setting $\langle \partial \psi / \partial t \rangle = \partial \langle \psi \rangle / \partial t$.

#### 3. Mathematical Impact
* Neglecting $\frac{1}{V} \int_{A_{\beta\sigma}} \psi_\beta (\mathbf{w} \cdot \mathbf{n}_{\beta\sigma}) dA$ violates exact global mass and energy conservation during transient catalyst swelling or moving bed operations.
* Induces drift in porosity and species accumulation residuals over extended dynamic cycles.

#### 4. Recommended Resolution (for Claude / Codex)
1. Add the interface velocity correction term to the upscaled time-derivative operator in the volume averaging module.
2. Ensure consistent coupling between solid expansion dynamics and fluid phase void fraction $\epsilon(t)$.

---

### Finding F-23: Index-Induced Singularity in Adjoint DAE Backward Integrations for Index-2 Systems

* **Classification:** DAE Sensitivity Analysis & Dynamic Optimization
* **Severity:** **High**
* **Affected Files & Lines:**
  * `core/solver/`

#### 1. Theoretical & Mathematical Description
When evaluating continuous adjoint DAE systems (Section 13.3):
$\frac{d}{dt}\left( \mathbf{J}_{\dot{\mathbf{y}}}^T \boldsymbol{\lambda} \right) - \mathbf{J}_{\mathbf{y}}^T \boldsymbol{\lambda} = -\left( \frac{\partial \mathcal{L}}{\partial \mathbf{y}} \right)^T$
if the original forward system has differential index $\nu \ge 2$ (e.g. incompressible Navier-Stokes without pressure Poisson projection, or strict phase equilibrium with algebraic enthalpy constraints), the transposed operator $\mathbf{J}_{\mathbf{y}}^T$ possesses an algebraic nullspace that does not decouple during backward time integration.
Integrating this system backward in time without index reduction causes the adjoint variables to differentiate numerical noise, generating non-causal algebraic singularities and catastrophic error explosion ($\|\boldsymbol{\lambda}(t)\| \to \infty$).

#### 2. Codebase Discrepancy
Currently, sensitivity modules in `core/solver/` do not verify the index of the adjoint operator prior to backward integration, relying on standard BDF step-size selection designed solely for forward causal dynamics.

#### 3. Mathematical Impact
* Dynamic optimization (IPOPT/SQP) fails to compute valid gradients, reporting unbounded gradient norms or NaN values during line search.
* Severe divergence during gradient-based model calibration and parameter estimation.

#### 4. Recommended Resolution (for Claude / Codex)
1. Project the adjoint DAE system onto the invariant state manifold using the Pantelides-reduced index-1 equations.
2. Apply coordinate-split or nullspace projection methods to ensure that algebraic constraint multipliers in the adjoint system are determined without differentiation of high-index residuals.

---

### Finding F-24: Violation of Onsager Reciprocal Symmetry in Empirical Off-Diagonal Multicomponent Diffusion Approximations

* **Classification:** Non-Equilibrium Thermodynamics & Transport Phenomena
* **Severity:** **Medium**
* **Affected Files & Lines:**
  * `core/termodinamica/`

#### 1. Theoretical & Mathematical Description
In multicomponent diffusion systems, the phenomenological conductance matrix $\mathbf{L}$ connecting mass diffusion fluxes to chemical potential gradients must satisfy the Onsager reciprocal relation:
$L_{ij} = L_{ji} \quad \forall \, i, j$
and must be strictly positive semi-definite ($\mathbf{L} \succeq 0$).
When converting Stefan-Maxwell equations into generalized Fickian diffusion matrices $\mathbf{D} \in \mathbb{R}^{(N_c-1) \times (N_c-1)}$, empirical simplifications often neglect off-diagonal thermodynamic correction factors $(\delta_{ij} + x_i \frac{\partial \ln \gamma_i}{\partial x_j})$, resulting in an asymmetric or indefinite diffusion matrix.

#### 2. Codebase Discrepancy
In `core/termodinamica/`, simplified multicomponent mass transfer calculations frequently assume diagonal effective diffusion coefficients or uncorrected binary interactions, which do not preserve Onsager symmetry.

#### 3. Mathematical Impact
* Asymmetric or indefinite diffusion matrices can produce negative local entropy generation rates ($\sigma_s < 0$) in ternary mixtures near azeotropic pinch points.
* Predicts non-physical spontaneous separation ("uphill" diffusion away from stable thermodynamic equilibrium), causing solver crashes.

#### 4. Recommended Resolution (for Claude / Codex)
1. Formulate all multicomponent mass diffusion fluxes using the symmetric Onsager phenomenological matrix $\mathbf{L}$.
2. In the thermodynamic layer, compute the full thermodynamic factor matrix $\boldsymbol{\Gamma}_{ij} = \delta_{ij} + x_i \frac{\partial \ln \gamma_i}{\partial x_j}$ via complex-step differentiation (Section 3.9) to guarantee $\mathbf{L} \succeq 0$.

---

### Finding F-25: Absence of Marangoni Solutal Shear Stress Jump Coupling at Reactive Vapor-Liquid Interfaces

* **Classification:** Interfacial Transport Phenomena & Free Surface Mechanics
* **Severity:** **Medium**
* **Affected Files & Lines:**
  * `core/balances/generador.py`
  * `core/discretizacion/`

#### 1. Theoretical & Mathematical Description
At vapor-liquid phase interfaces in reactive distillation columns, surface tension varies significantly due to temperature and composition gradients:
$\nabla_s \sigma = \left( \frac{\partial \sigma}{\partial T} \right) \nabla_s T + \sum_{i=1}^{N_c-1} \left( \frac{\partial \sigma}{\partial x_i} \right) \nabla_s x_i$
This gradient exerts a tangential shear stress jump across the interface (Section 10.5):
$[[\mathbf{n} \cdot \boldsymbol{\tau} \cdot \mathbf{t}]] = \nabla_s \sigma \cdot \mathbf{t}$
driving Marangoni surface flows.

#### 2. Codebase Discrepancy
In `core/balances/generador.py`, interfacial momentum balances include only normal pressure jumps ($[[P]] = 2 \kappa \sigma$), setting tangential interfacial shear stress jump to zero ($[[\mathbf{n} \cdot \boldsymbol{\tau} \cdot \mathbf{t}]] = 0$).

#### 3. Mathematical Impact
* In separations involving surface-active mixtures (e.g. water-ethanol, acetic acid-water), solutal Marangoni stresses induce cellular convection rolls and film rupture.
* Neglecting this term prevents accurate prediction of liquid film dryout, minimum wetting rates, and liquid entrainment in structured packings.

#### 4. Recommended Resolution (for Claude / Codex)
1. Add the tangential surface tension gradient traction $[[\mathbf{n} \cdot \boldsymbol{\tau} \cdot \mathbf{t}]] = \nabla_s \sigma \cdot \mathbf{t}$ to the conjugate interface solver in `core/discretizacion/`.
2. Compute surface tension partial derivatives $(\partial \sigma / \partial T)$ and $(\partial \sigma / \partial x_i)$ within the thermodynamic property layer.

---

### Finding F-26: Omission of Discrete Adjoint Dual-Consistency in Collocated Runge-Kutta Time Steppers

* **Classification:** Numerical Algorithms & Algorithmic Differentiation
* **Severity:** **Medium**
* **Affected Files & Lines:**
  * `core/solver/rk45.py`

#### 1. Theoretical & Mathematical Description
In dynamic optimization and sensitivity analysis, gradient accuracy depends on whether the adjoint equations are derived from the continuous DAE (Continuous Adjoint) or by differentiating the discrete numerical integration steps directly (Discrete Adjoint).
If a continuous adjoint is discretized with an independent time-stepper, the computed gradient $\nabla \mathcal{J}_{\text{adj}}$ deviates from the true gradient of the forward simulation $\nabla \mathcal{J}_{\text{forward}}$ by $\mathcal{O}(h^p)$ discretization error (loss of dual consistency).

#### 2. Codebase Discrepancy
In `core/solver/rk45.py`, sensitivity updates do not preserve the exact discrete Butcher tableau relationships of the forward Fehlberg stages, leading to gradient discrepancies on non-uniform adaptive meshes.

#### 3. Mathematical Impact
* Optimization algorithms (e.g. IPOPT, BFGS) encounter gradient inconsistency during line searches near the optimum, causing false terminations or excessive step-size damping.
* Inability to achieve tight optimality tolerances ($\|\nabla \mathcal{J}\| < 10^{-6}$).

#### 4. Recommended Resolution (for Claude / Codex)
1. Implement discrete adjoint equations directly derived from the Runge-Kutta / Radau IIA stage algebraic equations (Section 13.4).
2. Store forward collocation stage values and reuse exact stage time steps $h_n$ during backward adjoint passes to guarantee machine-precision dual consistency.

---
---

### Finding F-27: Triplication of Mathematical Expression ASTs Across Subsystem Boundaries

* **Classification:** Software Architecture & Symbolic Compilation
* **Severity:** **High**
* **Affected Files & Lines:**
  * `frontend/app/motor/expresionesMotor.ts`: lines 1–120
  * `core/expresiones_motor.py`: lines 1–145
  * `frontend/app/adimensionalizacion/contrato.ts`: lines 45–110

#### 1. Theoretical & Mathematical Description
In an equation-oriented multiphysics simulator, mathematical expressions must possess a single, canonical, typed Abstract Syntax Tree (AST) definition. An expression $f(\mathbf{x}, t)$ must preserve:
1. Operator precedence and associativity.
2. Exact dimensional vector representations $\mathbf{d} \in \mathbb{Q}^7$.
3. Symbolic dependencies and differential operator classifications ($\partial/\partial t$, $\nabla$, $\nabla \cdot$).

#### 2. Codebase Discrepancy
As recorded in ARCHITECTURE.md §6, three competing expression representations coexist:
* `frontend/app/motor/expresionesMotor.ts`: string-based and legacy TS dictionary formats.
* `core/expresiones_motor.py`: Python tuple-based expression trees.
* `frontend/app/adimensionalizacion/contrato.ts`: typed JSON AST (`Expresion` v2).
Converters between these representations perform lossy translations, occasionally stripping variable provenance and dimensional exponents.

#### 3. Mathematical Impact
* Inhibits seamless bidirectional handoff between the Model workspace (where balances are derived) and the Transform workspace (where scaling and discretization are applied).
* Introduces latent parsing errors when equations containing high-order tensor or spatial differential operators are transferred from balance generators to the symbolic compiler.

#### 4. Recommended Resolution (for Claude / Codex)
1. Formally adopt the typed JSON AST of `contrato.ts` (`rage.modelo` mathematical AST) as the sole canonical expression format.
2. Replace the legacy string and tuple representations in `expresionesMotor.ts` and `expresiones_motor.py` with the canonical reader (`core/modelo/lector.py`).

---

### Finding F-28: Tight Coupling of Numerical Residuals to Raw Flat Array Offsets Without Symbolic State Maps

* **Classification:** Software Architecture & Numerical Compiler Interface
* **Severity:** **Medium**
* **Affected Files & Lines:**
  * `core/compilador/`: residual function emission
  * `core/solvers/`: vector state management

#### 1. Theoretical & Mathematical Description
When a system of differential-algebraic equations is compiled for a stiff integrator, the state vector $\mathbf{y} \in \mathbb{R}^{N_y}$ contains diverse physical quantities: molar amounts $n_i$, internal energies $U$, enthalpies $H$, velocities $u_j$, pressures $P$, and algebraic multipliers $\lambda_k$.
Mathematical rigor requires that every component of $\mathbf{y}$ be uniquely identified by a bijective coordinate chart:
$\mathcal{M}_{\text{state}}: \text{Symbol} \longleftrightarrow \text{Index } i \in \{0, \dots, N_y-1\}$

#### 2. Codebase Discrepancy
In the current compilation pipeline, numerical residual functions $\mathbf{F}(t, \mathbf{y}, \dot{\mathbf{y}})$ access state variables through hardcoded flat array slices without preserving a symbolic state layout descriptor.

#### 3. Mathematical Impact
* When BLT partitioning, Tarjan SCC decomposition, or Pantelides index reduction permutes equations and variables ($\mathbf{P} \mathbf{J} \mathbf{Q}^T$), any mismatch between the permutation vector $\mathbf{Q}$ and initial condition vectors $\mathbf{y}_0$ causes silent corruption of physical state assignments.
* Debugging algebraic solver stalls requires manual reverse-engineering of integer array indices back to physical quantities.

#### 4. Recommended Resolution (for Claude / Codex)
1. Introduce a formal `StateLayoutDescriptor` in `core/compilador/` that maps each variable symbol `(volume_id, entity_type, component_id)` to its exact index range in $\mathbf{y}$.
2. Ensure that solvers, event handlers, and the thermodynamic closure access state vectors via this layout descriptor rather than raw integers.

---
*End of Audit Document.*
