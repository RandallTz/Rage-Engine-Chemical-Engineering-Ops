# Design C4: open boundary, water with non-condensable gases and a calculated flow

Assignment: [docs/history/frontend/assignment-claude-consolidation-multiphase-2026-10-15.md](../history/frontend/assignment-claude-consolidation-multiphase-2026-10-15.md) §6. **A design and feasibility document; none of this is implemented or published as a capability.** The current service rejects the fields proposed here (`MOTOR_ENS_CAMPO_NO_ADMITIDO`) and still requires every flow as a datum. Typed draft: `docs/contratos/borradorFronteraAbierta.ts` (it compiles against revision 2; it is not a published revision).

Reference case, without a target solution: 3 L inside, 2 kg of total water, 10 °C, 1 atm initially, dry air 79/21 molar N2/O2, a declared constant net heat. Two closures: sealed and open to the atmosphere.

## 1. Why pure water does not work as a shortcut for the open case

Pure water with liquid and vapor in equilibrium has one intensive degree of freedom (phase rule, F = C − π + 2 = 1): fixing T fixes P = Psat(T). At 10 °C, Psat = 1228.2 Pa (IAPWS-95), not 101 325 Pa. With 2 kg in 3 L the liquid does not fill the vessel, so there is no other mechanism that raises the headspace pressure. The state "pure water, 10 °C, 1 atm, with a vapor space" **does not exist**; imposing P = 1 atm with fixed V and a calculated outlet would have no initial solution (the flow would have to be an inlet of gaseous pure water at 1 atm, which at 10 °C would condense). The solved sealed pure-water sheet (P0 = 1228 Pa) is correct for its idealization, which does not represent closing a pot with air in it.

A different alternative, which is another choice of control volume: the liquid's domain alone, with a free surface at ambient P and the atmosphere outside. Then evaporation to the outside is an interfacial transfer with its own law (diffusion/convection of vapor in air), not a local equilibrium: it is outside this design and must not be simulated with an invented coefficient.

## 2. Proposed package: condensable water + non-condensable gases

Proposed identity: `agua-iapws95-aire-virial` version 1 (provisional name).

### Phases and species

- **Liquid**: pure IAPWS-95 water at the total pressure (it includes the Poynting term naturally). **Declared hypothesis: N2 and O2 insoluble** (dissolution neglected). At 25 °C, with the pure gas at 1 atm, the dissolved mole fraction is ~2.3e-5 (O2) and ~1.2e-5 (N2) by Henry's law; with air, about 5 and 1.3 times less respectively: a negligible effect on energy and volume balances, though not on the water's chemistry (which is not modelled). Henry would be an extension with its own data.
- **Gas**: N2, O2 and H2O(g). No N2/O2 liquids are created and liquid correlations are not extrapolated to 300 K (both are supercritical: Tc = 126.2 K and 154.6 K). Argon is explicitly left out (or added as a third species if standard-composition air is wanted).

### Why the ideal gas is not enough for the vapor

Water's second virial coefficient according to IAPWS-95 (the limit of ∂αʳ/∂δ as δ → 0) gives, at saturation, `Z − 1 ≈ B Psat/(R T)`:

| T | B (cm³/mol) | Z_sat − 1 |
|---|---|---|
| 283.15 K | −1645 | −0.09 % |
| 323.15 K | −832 | −0.38 % |
| 373.15 K | −451 | −1.47 % |
| 393.15 K | −371 | −2.26 % |

In the sealed case the contents go above 100 °C; an ideal vapor would shift the vapor pressure by ~2 % and break the "air → 0" limit against the already verified `agua-iapws95` package. That is why the gas uses a **virial equation truncated at the second coefficient**, thermodynamically consistent:

```
Z = 1 + B_mix(T, y) P/(R T),     B_mix = Σ_i Σ_j y_i y_j B_ij(T)
ln φ_i = (2 Σ_j y_j B_ij − B_mix) P/(R T)
h^res = P (B_mix − T dB_mix/dT),   s^res = −P dB_mix/dT,   v = R T/P + B_mix
```

Every gas property comes from that single function (residual G = B_mix P), as in the current mixtures. B_ww(T) is taken from IAPWS-95 (the same limit as above, with its derivative); B_aa from a reference EOS of dry air or of N2 and O2; the cross B_aw from a primary source (see §6).

### References and potentials

- Water: the IAPWS-95 reference (u = s = 0 of the liquid at the triple point) in **both** phases. The ideal part of gaseous water comes from IAPWS-95's φ°, so the ideal vapor and the liquid share exactly that reference, with no external cp table.
- N2 and O2: ideal gas with `h = s = 0` at 298.15 K and 1 bar, cp from a primary source (e.g. NASA-7 or the ideal term of its reference EOS).
- Mixing references **per species** is legitimate without reaction (consolidation C3 checks the invariance under per-species shifts). What is not legitimate is connecting, through a stream, a volume of this package with another whose water uses another reference: the conversion would have to be explicit or the connection is rejected, as today (`MOTOR_ENS_REFERENCIAS_INCOMPATIBLES`).
- Water equilibrium: `μ_w^L(T, P) = μ_w^{ig}(T, P0) + R T ln(y_w P φ_w/P0)`. `P_total = Psat(T)` is **not** imposed, and an air partial pressure is not added on top of a pure-water flash.
- Potentials published as in revision 2 (`PotencialesV2`): molar μ in J/mol, one reference per species declared in `referencia`.

### Proposed domain (to be confirmed by the tests)

T from 273.16 to ~450 K; total P ≤ 5 bar (truncated virial: error in the vapor's Z from the third coefficient below ~0.1 % at those pressures, to be checked against IAPWS-95 in the pure-water limit); no ice; no critical region. The vessel's strength limit is **something else**: a datum of the equipment that, if declared, produces an event (`limite_equipo`) without changing the EOS domain.

### Why not use a humid-air formulation directly

IAPWS/TEOS-10 (humid air: dry air from Lemmon et al. 2000 + IAPWS-95 + cross coefficients) is the quality reference and will be used to **cross-check** the package. It treats dry air as a pseudo-component of fixed composition: it does not allow following N2 and O2 separately if they leave in different proportions (that would not happen here without dissolution, but the contract declares them as species). Installing it as a package is possible if "dry air" is accepted as a component with its own identity; it stays as option B in §6.

## 3. Initialization from T0, P0, V, total water and dry proportion

Data: T0, P0, geometric V, n_w (total water), dry fractions (N2:O2). Initialization unknowns: n_air (total dry gas), n_w^L, n_w^G. Equations:

```
n_w^L + n_w^G = n_w                                     (water matter)
V = n_w^L v_L(T0, P0) + (n_air + n_w^G) Z R T0/P0       (volume, the same gas space for every gas)
μ_w^L(T0, P0) = μ_w^G(T0, P0, y_w)                      (water equilibrium)
y_w = n_w^G/(n_air + n_w^G)
```

Three unknowns and three equations (plus the definition of y_w): square. The amounts of N2 and O2 are a **result** of the initialization, not data; U0 is also a result (U0 = U(T0, V, n)). After t = 0, P0 is not imposed in the sealed case: it is only an initial condition. In the contract this needs a different form of initial state (draft: `InicialPorPresionV2`) that says which amounts are calculated; the current form (every amount as a datum) stays valid and is not mixed with the new one in the same volume. If the air amounts and P0 are given at the same time, the problem is overdetermined: it is diagnosed, and one is not picked.

Check of the estimate in the pots document: with an ideal gas and insoluble air, n_air = 0.042493 mol was obtained; with the virial the difference is of order B_mix P0/(R T0) ≈ 1e-3 relative. The package must recalculate it with its own relations; that number is not reused as a datum.

## 4. Sealed closure

```
dn_i/dt = 0        (i = H2O, N2, O2)
dU/dt = Q_net
V = 3 L
(T, P, phases) = the package's UV closure (n_i, U, V)
```

Checks: exact U(t) = U0 + Q t; constant n_i; fixed V; second law with a boundary T if declared. There is no target result: final T, P or vapor fraction are not fixed. The trajectory stops with a diagnosis when it leaves the package's domain (e.g. P > 5 bar); a strength limit of the equipment, if declared, is a separate event.

## 5. Open boundary: fixed V, ambient P and a calculated outlet flow

### Formulation

States: n_i, U. Additional algebraic unknown: F (mol/s, outflow of the donor's **gas phase**, with composition y_i and gas molar enthalpy h_G). Ideal mechanical constraint: P(U, V, n) = P_amb.

```
dn_i/dt = −F y_i
dU/dt = Q_net − F h_G
0 = P(U, V, n) − P_amb
```

The energy carried out is the enthalpy of the extracted gas mixture: the latent heat is already in h_G (the h of water vapor against the h of the liquid) and is not added again.

### Index and reduction

The constraint does not contain F: the system is an **index-2** DAE. Differentiating it once:

```
dP/dt = (∂P/∂U)_{V,n} (Q_net − F h_G) − Σ_i (∂P/∂n_i)_{U,V,n_j} F y_i = 0
F = (∂P/∂U) Q_net / [ (∂P/∂U) h_G + Σ_i (∂P/∂n_i) y_i ]
```

The derivatives are **equilibrium** derivatives (through the phase split, which changes with U and n), not those of a frozen phase: they are obtained from the UV closure by differences or analytically. With an explicit F an ODE in (n, U) remains — a reduction to index 1/ODE — and the constraint is kept with a projection per step (correct U at fixed n so that P = P_amb, or equivalently re-solve F) plus a published residual `mecanica.<v>.presion = max |P − P_amb|/P_amb`. This is preferred to an implicit DAE because the current coordinator is explicit (RK45) and already certifies samples; an index-1 DAE with F as an algebraic variable (BDF/Radau) is the alternative if the projection turned out to be ill-conditioned.

### Sign and regime

- F ≥ 0: gas leaves. If the denominator or the numerator changes sign (e.g. cooling: the pressure tends to fall below P_amb), an **ideal open lid** admits ambient air: it needs `estadoExterior` (T, P, composition of the ambient air) and the donor becomes the surroundings, with their enthalpy. Without a declared external state, inflow is impossible: it stops with a diagnosis (`entrada_sin_estado_exterior`); properties are not copied from the inside.
- Non-return valve: a different regime (F ≥ 0 and P ≥ P_amb complementary): it closes and becomes sealed until P reaches P_amb again. It needs regime-change events; it is declared, not designed in detail.
- Gas depletion (all liquid): impossible here with fixed V while there is air; with air → 0 and liquid filling V, P stops being determined (incompressible liquid) and it stops.

### Consistent initialization

At t = 0, P(U0, V, n0) = P_amb is required: the same initialization as §3 with P0 = P_amb. If the user declares P0 ≠ P_amb for the open boundary, the initial state is inconsistent with the constraint: it is diagnosed (the system does not "jump" to the consistent state without saying so).

### Count

Per volume: states n_i (3) and U; algebraic T, P, split; one more unknown (F) and one more equation (the mechanical constraint). Structural DOF 0 without asking for F as a datum. Today revision 2 rejects "fixed V + prescribed P" because it requires given flows; the design generalizes that guard with the analysis above (rank of the constraint with respect to F: the denominator must not vanish); it does not delete it.

### Future real discharge

A valve or a weighted lid does not guarantee constant P: they need a transport law (F = C_v f(P, P_downstream), mass of the lid, leaks) with its parameters and back pressure. It is another constitutive relation with its own data; the ideal boundary does not replace it.

## 6. Data needed and sources

| Datum | Candidate source | State |
|---|---|---|
| B_ww(T), dB_ww/dT | IAPWS-95 (limit of αʳ) | available in the project |
| cp° and reference of N2, O2 | NASA-7 / Burcat; or the ideal part of Span et al. 2000 (N2) and Schmidt–Wagner 1985 (O2) | to be added |
| B_NN, B_OO, B_NO | Reference EOS of N2, O2 (or the dry air of Lemmon et al. 2000) | to be added |
| B_wN, B_wO (water–gas cross terms) | Harvey and Huang, Int. J. Thermophys. 28 (2007) 556 (ab initio calculation, used by IAPWS for humid air) | to be added |
| Cross-check of the package | IAPWS/TEOS-10 humid air (Feistel et al. 2010; IAPWS "SeaAir"), CoolProp HumidAir | for tests, not for solving |
| Solubility (if added) | Henry constants (IAPWS G7-04, gases in water) | future extension |

Option B: a package with "dry air" as a pseudo-component (Lemmon et al. 2000 + IAPWS-95 + IAPWS cross terms), when it is acceptable to follow the air without separating N2 and O2.

## 7. Test plan (before publishing the capability)

1. Air → 0 limit: the package's Psat against IAPWS-95 (relative residual below the contribution of the omitted third virial, quantified); enthalpy of vaporization.
2. Dry gas: Z, h, s of N2/O2 against their reference EOS at 1–5 bar.
3. Saturated humid air: y_w against IAPWS/TEOS-10 (enhancement factor f(T,P)) between 0 and 100 °C at 1 atm.
4. Identities: h = u + P v, g = h − T s, Gibbs–Duhem in the gas, equilibrium derivatives ∂P/∂U, ∂P/∂n by two paths.
5. Initialization: recover T0, P0, V and n_w; non-negative amounts; overdetermination diagnosed.
6. Sealed: U = U0 + Q t, constant n_i, second law with a boundary T; convergence in tolerance.
7. Open: conservation per species including what leaves; energy with h_G; |P − P_amb| published; F ≥ 0 when heating; reversal with and without an external state; comparison with an independent reduction (integrate with F imposed equal to the calculated one and check that P is held).
8. Negative controls: corrupt h_G (duplicated latent heat) → the energy balance does not comply; remove the air → initialization incompatible with P0 = 1 atm (§1).
9. Comparison of the two closures with the same data except the boundary; no solver branch by name.

## 8. What remains to implement it

The data of §6 with provenance; the package with its tests 1–4; the initial form by pressure; the mechanical constraint with the flow as an unknown in the assembly (count, reduction, projection, residual and regime events); examples generated by endpoints. None of it has been added to the engine in this delivery.
