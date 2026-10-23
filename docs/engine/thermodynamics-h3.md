# Thermodynamics of the independent engine — delivery H3

14 October 2026. It answers [docs/history/frontend/contract-claude-thermodynamics-h3.md](../history/frontend/contract-claude-thermodynamics-h3.md). It continues [docs/engine/thermodynamics-h0-h1.md](thermodynamics-h0-h1.md), whose decisions (EOS, units, molar mass, reference, domain, TP stability) still hold.

What it contains: liquid–vapor coexistence of pure water and the **PH, UP and UV** specifications for `agua-iapws95` v`1`, with one or two phases, fractions in the three bases and checks of equilibrium, energy and volume. The HTTP contract is the same: revision 1 and the same routes, with no new fields. `dinamica` stays `false`.

| Piece | File |
| --- | --- |
| Physics | `core/agua_iapws95.py`, section "H3" at the end (what came before does not change) |
| Contract | `backend/motor_termodinamica.py`: reading of `cantidades`, `_evaluada_inversa` |
| H3 tests | `tests/validar_motor_termodinamica_h3.py` (3729 checks) |
| H1 tests | `tests/validar_motor_termodinamica.py` (585; the "PH/UV not supported" cases move to the H3 suite) |
| Examples | `docs/ejemplos/motor-termodinamica-*` (8 new H3 cases) |

## Model version: still `1`

TP states do not change: `evaluar_TP`, the stability, the saturation fits that separate the branches and the H1 checks are the same code. The 9 TP responses of the H1 examples were regenerated and are **byte-for-byte identical**. Two examples change, on purpose:

- `capacidades`: `especificaciones` goes from `["TP"]` to `["TP","PH","UP","UV"]`.
- `saturacion-indeterminada`: the diagnosis adds `alternativas` (PH, UP, UV, already published) and stops saying they are not accepted.

The example `ph-no-soportado` was **removed**: it described a limitation that no longer exists. Extending the specifications does not change the meaning of TP, so there is no version change; the extension is published in `capacidades`, where the client reads it.

## Coexistence

**Equations.** At a given T, T′ = T″ by construction, and P(T,ρ′) = P(T,ρ″) and g(T,ρ′) = g(T,ρ″). They are solved by Newton in (ρ′, ρ″) with an analytical Jacobian: ∂P/∂ρ = (∂P/∂ρ)_T and ∂g/∂ρ = (∂P/∂ρ)_T/ρ at fixed T.

**Seed and branches.** The seed is `chemicals`' fits to the multiple-precision solution: one density on the liquid branch and another on the vapor branch, never in the homogeneous region of the dome. Each step must keep ρ′ > ρc > ρ″; if it leaves its branch, it is rejected. There are no third roots: the homogeneous region between ρ″ and ρ′ is not a candidate phase (H1 explains why the EOS is not physical there).

**Convergence.** It iterates until the residual stops falling (the floating-point limit), with a maximum of 30 iterations; 1 to 3 usually suffice. The residual is published in `equilibrio`:

$$\max\Big(\tfrac{|g'-g''|}{RT},\ \tfrac{|P'-P''|}{\max(P'',\ \rho'(\partial P/\partial\rho)_T')}\Big)\le 10^{-9}$$

The pressure difference is scaled with the liquid's bulk modulus because its pressure is stiff: with ρ′ exact to the last bit, P′ is fixed only to about 1e-7 Pa. That is why Psat is P″, the vapor's, which is well conditioned. Measured: residual ≤ 1e-12 between 273.16 and 643.86 K.

**Tsat(P).** First a bracket is searched with Brent on the monotonic fit Psat(T) in [273.16, 643.86] K. Then it is refined with Newton in T, using the solved coexistence and the Clapeyron slope (s″−s′)/(v″−v′). The residual |Psat(Tsat) − P|/P is published in `presion_saturacion`: measured ≤ 4e-15, tolerance 1e-10.

**Critical limit.** Coexistence is published only with Tsat ≤ 643.86 K = 0.995·Tc, the edge of H1's critical band. There Psat = 21.22 MPa and h″−h′ ≈ 412 kJ/kg, a difference still well conditioned. Above it, the differences between phases tend to zero and the quality becomes ill-conditioned: a PH/UP/UV state that falls there comes out `no_soportado` with `MOTOR_ESTADO_REGION_CRITICA`. No quality is fabricated.

**Triple point.** At 273.16 K ice could also coexist, which the model excludes. An inversion that, by rounding, falls one bit below T_MIN is rejected as outside the domain.

## Split between phases

With pure water, q is the vapor mass fraction and equals the molar one:

$$y = (1-q)\,y' + q\,y'' \quad (y = u, h, v, s), \qquad \varepsilon_v = q\,v''/v$$

All phase properties are at the same T and P and with the same IAPWS-95 reference. The latent heat is h″−h′; there is no separate source. The volume fraction differs from q: in the example rigid vessel, q = 0.419 and ε_v = 0.9935.

**Active set.** The problem at the ends is numerical. With q exactly 0 or 1 at the input, the error of Tsat(P), up to ~7e-13 K near 643.86 K, and the rounding of y and v leave spurious fractions between 1e-19 and 1.3e-13 (measured by the suite). The rule is **Q_MIN = 1e-12**, applied on both sides of the plateau:

- a calculated q in [−Q_MIN, Q_MIN] is the boundary q = 0 (and symmetrically at 1);
- at the boundary only the present phase is published;
- traces from 1e-11 up are kept and reconstructed;
- the reconstructed energy and volume are published as residuals (at the boundary, ≤ 1e-12·Δy/(RT)).

No amounts or energy are clipped or renormalized.

**Heat capacities.** With two phases, or with one on the curve (boundary), the `mezcla` does **not** carry cp or cv, because the derivative of the equilibrium state is not that of one phase. Each phase keeps its single-phase cp and cv. A single-phase state off the curve does publish global cp and cv.

## Selection criterion of each specification

**PH: maximum of S at (H, P, n).** For a closed adiabatic system at constant external pressure, H is conserved and dS ≥ 0, so equilibrium maximizes S at (H, P, n). At that maximum the phases share T, P and μ, and the state is stable in G at that (T, P). For a pure substance, the equilibrium h grows with T along the isobar: cp > 0 on the branch, and at Tsat there is a plateau linear in q with h″ > h′. So there is at most one state. The calculation first places h relative to the plateau [h′, h″] and only then solves T with Brent on the corresponding branch.

**UP: no extremum principle.** Fixed U and P are not natural variables: keeping U constant while the boundary does work P dV requires exchanging heat, so no maximum of S is invoked. The specification rebuilds the internal state from conserved U and n with an imposed P. The criterion is internal stability: the state must be stable in G at its own (T, P) and have u = U/m. Uniqueness relies on u growing along the equilibrium isobar:

- in one phase, (∂u/∂T)_P = cp − P(∂v/∂T)_P ≥ 0.75·cp, measured on a grid of 400 × 11 isobars over the whole domain;
- on the plateau, u is linear in q with u″ > u′.

**UV: maximum of S at (U, V, n), in an isolated rigid system.** For a pure substance, a homogeneous state meets the criterion if and only if it is on the concave envelope of s(u, v), which is equivalent to being stable in G at its own (T, P). Inside the dome, the envelope is the mixture of the two saturated phases. It is calculated this way:

- **Candidates:** every root in T of u_cand(T; v) = u. At each T, u_cand is the coexistence mixture if v′ < v < v″, and the homogeneous state ρ = 1/v otherwise. The function is continuous: at the edge of the dome both expressions coincide. **The u and v constraints are solved together**: the q that fixes v is the same one that gives u; there is not one fraction for each.
- **Search:** a grid of 301 temperatures in [273.16, 1073.15] K and Brent at each change of sign. The first root is not simply taken.
- **Selection:** each candidate is certified. If several admissible ones remained, the one with the largest s would be chosen; if their s cannot be told apart (1e-9), the response is `no_convergente` with `MOTOR_ESTADO_AMBIGUO`.
- **Uniqueness:** physically, the equilibrium u at fixed v grows with T (equilibrium cv > 0). In every test there is a single root, also in the density anomaly near 4 °C, where v′(T) is not monotonic: at fixed v, as u rises, one goes from compressed liquid to traces of vapor and back to compressed liquid. What the grid cannot exclude is two roots within the same 2.7 K cell. The physical argument and the test cover it; the `unicidad` check publishes the count.
- **Phase of a homogeneous candidate:** outside the dome, the side of ρc decides it. Comparing with the fits' ρ′ labelled as vapor a liquid right at the boundary, because the fits differ by ~1e-13; it was a defect found by the suite, and it is fixed.
- **Maximum density:** ρ = m/V > 1250 kg/m³, of the order of ρ(273.16 K, 1 GPa), is rejected before evaluating the EOS, because the pressure would leave the domain.

## Stability

- **One phase** (PH, UP or UV): the same as TP. Tangent-plane distance at the resulting T, over the single-phase branches, with residual −min TPD/P* ≤ 1e-9.
- **Coexistence:** the common tangent through the two saturated points is checked:

$$tm(\rho) = \frac{\rho\,[f(T,\rho) - g^*] + P^*}{\rho R T} \ge -10^{-9},\qquad g^* = g'',\ P^* = P''$$

  tm is the tangent-plane distance per unit mass of the trial phase, in units of RT (Δg/RT): the usual dimensionless scale. It vanishes at ρ′ and ρ″ and must not be negative at any other density of the branches (400 points per branch plus refinement). H1's TPD/P* scale does not work here: with Psat ~ 1 kPa, the 1e-7 Pa imprecision of P′ would already saturate it. H1 keeps its scale unchanged.
- **It is not a rubber stamp:** the suite forces a metastable homogeneous vapor inside the dome and checks that it is rejected.

## New checks, or checks with another meaning, in PH, UP and UV

| id | Residual | Tolerance |
| --- | --- | --- |
| `estabilidad` | one phase: −min TPD/P*; coexistence: −min tm | 1e-9 |
| `equilibrio` (two phases or boundary) | Maxwell, as above | 1e-9 |
| `presion_saturacion` (PH, UP on the curve) | \|Psat(Tsat) − P\|/P | 1e-10 |
| `energia` | \|reconstructed y − specified\|/(RT), y = h (PH) or u = U/m (UP, UV), with y = Σ w_α y_α | 1e-10 |
| `volumen` (UV) | \|reconstructed v − V/m\|/(V/m) | 1e-10 |
| `ecuacion_estado` (one phase, PH and UP) | as in TP | 1e-12 |
| `identidad_h_u_Pv` | maximum per phase of \|h − u − Pv\|/(RT) with the published P | 1e-9 |
| `identidad_g_h_Ts` | maximum per phase of \|g − (h − Ts)\|/(RT), with g from φ | 1e-12 |
| `reconstruccion_material` | \|Σβ_α − 1\| (one component: x_α = z = 1) | 1e-12 |
| `bases_fase` | max(\|Σw − 1\|, \|Σε − 1\|), with ε_α = w_α v_α/v; the reason gives q and Q_MIN | 1e-12 |
| `unicidad` | null; the reason describes the root search | null |
| `derivadas`, `saturacion` (one phase) | as in TP | — |

`masa_molar`, `politica_fases` and `cambio_interno` work the same as in TP. `cambioInterno: prohibido` is still `no_evaluable` in a point query. No time transition or entropy production is certified.

## Phase policy

The restrictions are checked **after** the equilibrium is calculated:

- `cantidad: monofasico` with a stable two-phase state → `invalido`, `MOTOR_ESTADO_FASE_INCOMPATIBLE`, path `declaracion.politica.cantidad`.
- `tiposPermitidos` that does not include every calculated phase → `invalido`, same error key, path `…tiposPermitidos`.

No metastable branch is forced in order to meet a restriction.

## Amounts and bases

- **Total mass:** on a mass basis, m = Σ m_i; on a molar basis, m = n·M with the model's M (18.015268 g/mol). Both bases rebuild the same state; kg, g, mol and kmol test it, as well as the pair of examples `uv-recipiente-rigido-bifasico` / `-molar`.
- **Scale:** scaling U, V and n together by 1e-3 or 1e3 changes neither T, P nor the fractions.
- **Rejections:** zero or negative total amount, V ≤ 0, units of another family (U in kJ/kg, a molar amount in kg) or fields of another specification come out with their code and path. Amounts and energy are never adjusted to make a flash succeed.
- **Outside the domain:** the path points to the datum that causes it. A T outside goes to `h` (PH) or to `U` (UP, UV); a P outside goes to `P` (PH, UP) or to `V` (UV).

## Evidence

```
python tests/validar_motor_termodinamica_h3.py              # 3729 checks
python tests/validar_motor_termodinamica.py                 # 585 (H0/H1 regression)
python tests/generar_ejemplos_motor_termodinamica.py
node tests/verificar_contrato_motor_termodinamica.mjs       # 35, TS validator on real responses
cd frontend && npm run test:motor-fundamental               # includes verificar_entrega_h0_h1_motor.mjs
```

| Check | Measured result |
| --- | --- |
| Coexistence against table 8 of IAPWS-95 (Psat, ρ′, ρ″, h′, h″, s′, s″ at 275, 450 and 625 K) | all < 1e-8 relative (the published values have 9 digits) |
| Against IF97, region 4 and regions 1/2 on the curve, from 700 Pa to 16 MPa (an independent formulation fitted to IAPWS-95) | \|ΔTsat\| ≤ 7.6 mK, \|Δh′\|, \|Δh″\| ≤ 196 J/kg |
| Another Maxwell solver (`chemicals.iapws95_saturation`, same EOS, another algorithm) | densities equal to < 1e-11 |
| Clapeyron: dPsat/dT by differences against (s″−s′)/(v″−v′); h″−h′ = T(s″−s′) | < 1e-6 and < 1e-10 |
| Round trip TP → PH, UP and UV in 14 states: liquid, compressed liquid, vapor, gas above Tc, supercritical, next to the critical band and at the edge of the domain | maximum of \|ΔT/T\|, \|ΔP/P\|, \|Δv/v\|, \|Δh\|/(RT) = **2.5e-10**; same phase and regime |
| Coexistence with q ∈ {0, 1e-11, 1e-6, 0.3, 0.5, 1−1e-6, 1−1e-11, 1} at 6 temperatures (273.2 to 643 K), by PH, UP and UV. Interior states are built with the other solver, not with the flash under test | correct phases, q to 1e-12 + 1e-9·q, ε_v = q v″/v, u, h, s and v reconstructed, no global cp |
| UV in the density anomaly | 1 root per case; liquid → traces of vapor → liquid as u rises |
| Rejections (domain for each datum, critical region by PH, UP and UV, amounts, units, policies, molar mass, overspecification) | state, code, path and owner; with `evaluacion: null` even if the earlier evaluation was valid |

Examples generated from the endpoints, with round user numbers:

| Case | Result |
| --- | --- |
| `ph-bifasico-1bar` (1 bar, 1500 kJ/kg) | 99.606 °C, q = 0.4795, ε_v = 0.99933 |
| `ph-vapor-sobrecalentado-10bar` (3000 kJ/kg) | vapor at 276.02 °C |
| `up-liquido-calentado-1bar` (5 kg, 1250 kJ) | liquid at 59.73 °C |
| `uv-recipiente-rigido-bifasico` and `-molar` (10 kg, 1 m³, 15 MJ) | 171.03 °C, 8.1208 bar, q = 0.4193, ε_v = 0.99352 |
| `uv-supercritico` (1 kg, 10 L, 2800 kJ) | supercritical fluid at 472.99 °C and 252.6 bar |
| `uv-monofasico-incompatible` | `invalido`: the stable state has two phases |
| `uv-energia-bajo-el-punto-triple` (−50 kJ/kg) | `no_soportado`: it would require T < 273.16 K (possible ice) |

## For Codex

- `capacidades` publishes `["TP","PH","UP","UV"]`. The interface can offer all four and read `alternativas` in TP saturation.
- `alternativas` has the contract's shape `string[][]`: `[["P","h","composicion"],["U","P","cantidades"],["U","V","cantidades"]]`. They are the fields of each specification, in the order of the contract's table.
- With two phases, `mezcla` carries no `cp` or `cv` and each phase does. The same holds for one phase on the curve (boundary); it is recognized because it carries the `equilibrio` check.
- The phase IDs are `liquido-1` and `vapor-1`, stable between queries.
- `fraccionMolar` = `fraccionMasica` = q. `fraccionVolumen` is different, and in coexistence at low pressure almost all the volume is vapor.
- None of this turns a saved query into an initial condition of a volume, or mixes the IAPWS reference with the manual affine relation u(T).

## Pending

- **Draft of the assembly's `validar`/`resolver` contract**, prior to H2/H4. The assignment places it as a later delivery and it is not in this one.
- Critical region (Tsat > 643.86 K or states in the band), T > 1073.15 K and P > 100 MPa.
- Dynamic H2/H4, mixtures (H5/H6), solids and coexistence with ice at the triple point.
- The derivatives of the two-phase state (equilibrium cp along the plateau, compressibility of the mixture) that H4 will need are not published in revision 1.
