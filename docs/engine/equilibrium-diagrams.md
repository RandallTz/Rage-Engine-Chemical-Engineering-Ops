# The engine's T–xy / P–xy equilibrium diagrams (D0–D3 and the physics part of D5)

Backend implementation of [docs/history/frontend/plan-diagrams-equilibrium-engine.md](../history/frontend/plan-diagrams-equilibrium-engine.md). D4 (reading and view) and the integration belong to Codex. The frontend, `/laboratorio` and `thermodynamics/proveedor.py` were not touched. No commit or push. **Reload:** restart the service (`uvicorn backend.main:app`); `backend/main.py` only receives the two new routes (additive).

## 1. What the frontend has to do

1. **Synchronize the copy of the v2 contract.** `docs/contratos/contratoEnsamblajeV2.ts` gained the optional field `resultados.procedenciaModelo`. The verifier `frontend/verificar_consolidacion_multifasica.mjs` requires the copy in `frontend/app/motor/` to be identical, and today it fails only because of that. With the copy synchronized (tested on a temporary copy of the frontend, outside the repository) it passes its 237 checks. The other 20 verifiers of `npm run test:motor-fundamental` pass unchanged.
2. **Copy the new contract** `docs/contratos/contratoDiagramasEquilibrio.ts`, with the same equality check.
3. Read the diagrams with `GET /motor/termodinamica/diagramas/capacidades` and `POST /motor/termodinamica/diagramas/trazar`, one slice per request (T–xy and P–xy in parallel, each with its own success or failure).
4. Compare a diagram with a trajectory only if `respuesta.identidad.huellaModelo` equals the `huella` of the volume's package in `resultados.procedenciaModelo`. Old runs without `procedenciaModelo` do not allow checking the match: offer to solve again. `huellaModeloEsperada` can also be sent; if it does not match, the response is `invalido` with `MOTOR_DIAG_HUELLA_DISTINTA`.

## 2. Contract (D0)

`docs/contratos/contratoDiagramasEquilibrio.ts`, revision 1, independent of the assembly. The existing route `GET /motor/termodinamica/diagrama` (P–T of water with ice) does not change.

**Request** (`SolicitudDiagrama`): exactly two components with CAS, `modelo` (the same package as the volume; it is never replaced), `componenteEjeId`, `corte` (`{tipo: 'Txy', P}` or `{tipo: 'Pxy', T}` with units: P in Pa, kPa or bar; T in K, degC or degF), `intervaloComposicion` (mole fraction of the axis component, within [0, 1]), `resolucion` (`exploratoria` | `refinada`) and, optionally, `huellaModeloEsperada`. No tank, mass, time or example: the diagram is an intensive query. Extra fields are rejected.

**Response** (`RespuestaDiagrama`):

| Field | Content |
|---|---|
| `estado` | `completo` (the whole interval covered by certified segments, or explored with no stable L–V), `parcial` (there are gaps because of domain, convergence or budget), `no_convergente` (no point), `invalido`, `incompleto`, `no_soportado` |
| `identidad` | model, `huellaModelo` (the package's data and parameters), `firmaConsulta` (physical key: package, fingerprint, species, slice in SI, interval in the component with the lowest CAS, profile and tracer version; it does **not** include the axis component or the units), tracer version |
| `condicion` | the original slice intact and `corteSI`, components with CAS, axis, interval, profile |
| `puntos` | `PuntoCoexistencia`: T [K], P [Pa], `xEje`, two **limiting phases** (`liquido-limite`, `vapor-limite`) with molar composition by ID, `certificado` and `origen` |
| `ramas` | one branch `lv-1` with segments of consecutive certified points; no segment crosses a gap |
| `puntosEspeciales` | `extremo_puro`, `azeotropo` (refined x = y, with `clase` minimo/maximo/tangente), `encuentro_otra_fase` (L–V boundary with the competing phase identified) and `limite_dominio` |
| `candidatosDescartados` | solutions that did not pass certification (e.g. metastable L–V in an LL zone): diagnosis only, **not drawn** |
| `incidencias`, `cobertura` | gaps with a reason (`sin_lv_estable`, `fuera_de_dominio`, `no_convergente`, `presupuesto`), published stretches, budget used, and reproducibility between the two directions of travel |
| `evidencia` | level of the pair or the package (see §5), independent of the numerical certificate |
| `diagnosticos` | `MOTOR_DIAG_*` with a path; also warnings (`aviso`) in responses with points |

**Limiting phases.** Bubble and dew points are limits with phase amount → 0, so they are not `FaseEvaluada`: they carry no phase fractions and the state reader is not weakened to admit them. The diagram does not fix β.

**Diagnostics** (stable, with a path): `MOTOR_DIAG_REVISION`, `MOTOR_DIAG_DATO_INVALIDO`, `MOTOR_DIAG_UNIDAD`, `MOTOR_DIAG_PAQUETE_NO_DISPONIBLE`, `MOTOR_DIAG_PARAMETRO_AUSENTE`, `MOTOR_DIAG_COMPONENTES_NO_SOPORTADO`, `MOTOR_DIAG_COMPONENTE_NO_SOPORTADO`, `MOTOR_DIAG_FUERA_DE_DOMINIO`, `MOTOR_DIAG_NO_CONVERGENTE`, `MOTOR_DIAG_FASE_COMPETIDORA`, `MOTOR_DIAG_PRESUPUESTO`, `MOTOR_DIAG_HUELLA_DISTINTA`. Reserved in the contract but not used yet: `MOTOR_DIAG_REGION_CRITICA` (the package's domain excludes the critical region) and `MOTOR_DIAG_RAMA_AMBIGUA` (discrepancies between directions of travel are published as an incident `rama_ambigua`). Every known rejection is a protocol response with status `200`, not a 422.

## 3. Foundation and shared operation (D1)

`core/coexistencia_lv.py` is the shared operation. It uses only the package's public interface: `mu(tipo, T, P, x, idx)`, `prueba_estabilidad`, `T_saturacion`/`P_saturacion`, `dominio`, `equilibrio_TP` and `fase`. It contains no activity, vapor-pressure or fugacity formula: the equilibrium condition is the package's own `μ_i^L(T, P, x) = μ_i^V(T, P, y)`, so Poynting and any other contribution enter because they are in μ. `K = γ Psat/P` is not imposed. An EOS-based adapter that exposes `mu` works the same.

- Regular point (T–xy): Newton in `(ln T, logit y)` at fixed P and x; P–xy: `(ln P, logit y)` at fixed T.
- Azeotrope: Newton in `(ln T or ln P, logit x)` with y = x.
- Pure end: saturation of the component in the SAME package (`T_saturacion`/`P_saturacion`). `log 0` is not evaluated and no fictitious minimum composition is inserted.
- Generic seed: the package's certified TP flash, by bisection on the T (or P) at which vapor appears. If there is no phase change within the domain, it is declared outside the domain and not taken as a numerical failure.
- **Certificate per point**:
  - `igualdad_mu`: |Δμ|/RT ≤ 1e-10 for each species present;
  - `normalizacion`;
  - `condicion_fija`: the point's P equal to the slice's (T–xy), or T equal to the slice's (P–xy);
  - `distincion_fases`: difference in molar volume between L and V;
  - tangent-plane stability with the common μ against vapor (analytical minimum) and a trial liquid (grid of 1361 points with refinement). The refined grid does not prove the global minimum, and the certificate says so.

`core/diagramas_equilibrio.py` is the tracer. The continuation variable is the liquid's x on a Chebyshev grid, travelled in both directions:

- the previous point serves as the seed and the step is subdivided if Newton fails; if it still fails, the flash seed is used;
- it refines where T, ln P or the vapor composition jump;
- the stable/unstable and domain boundaries are located by bisection (14 steps);
- azeotropes are searched by change of sign **or** a minimum of |y − x|, so as not to lose tangent contacts.

The lines between points are visual interpolation; segments never cross a gap. There is no code branch per package, species or example.

**Fingerprint**: `Sistema.huella()` (`core/mezclas.py`) is a sha256 of package and version, CAS, each species' data (Psat, cp, v_L, M, ranges, sources), liquid model with its binary parameters, provenance, reference, domain and tolerances. It does not depend on the order of the components and changes if any datum changes even though `modelo.id` stays the same. Water (`agua-iapws95`) has its own fingerprint (formulation and audited version).

## 4. Capabilities implemented (explicit list)

| Capability | State |
|---|---|
| T–xy at fixed P and P–xy at fixed T, two components | implemented |
| Packages `mezcla-ideal`, `nrtl-chemsep` (pairs with parameters), `nrtl-lle-agua-butanol` | implemented |
| Pure ends from the same package's saturation | implemented |
| Homogeneous azeotropes (crossing and tangent contact), minimum/maximum class | implemented |
| Detection of competition from another liquid, located boundary and identified competing phase | implemented |
| L–L branches, L–L critical point (the binodal's fold) and L–L–V three-phase point, in `liquidoLiquido` (F8, §6b) | implemented |
| Domain limits by bisection, without extrapolating | implemented |
| Partial composition interval, axis on either component | implemented |
| Published reproducibility between directions of travel | implemented |
| Budget of evaluations and time with a partial result | implemented |
| Model fingerprint in diagrams and in the v2 assembly's `procedenciaModelo` | implemented |
| Profiles `exploratoria` (41 base points) and `refinada` (121), published in capabilities | implemented |

Profiles: `saltoMaximoT` [K] (T–xy) and `saltoMaximoLnP` (P–xy) trigger refinement. A flash seed counts as 45 evaluations. The certification tolerances are the same in both profiles and the frontend cannot choose them.

## 5. Evidence

`evidencia.nivel` comes from the v2 capabilities. Ethanol–water is `contrastada` (azeotrope); the other ChemSep pairs, `cualitativa`. Ideal mixture: `contrastada` against its analytical expression. Water/1-butanol: L–V `cualitativa` (the fit is for LLE). The evidence level is independent of each point's numerical certificate.

## 6. Physics tests (D5) — `python tests/validar_motor_diagramas_equilibrio.py`: 78 checks OK

| Case | Result |
|---|---|
| Ideal benzene–toluene T–xy against Raoult + Poynting solved separately | dT < 1e-8 K, dy < 1e-10 |
| Ideal P–xy at 370 K | dP/P < 1e-10 |
| Pure ends against the package's saturation | identical (< 1e-9 K) |
| Pure ends against NIST (benzene, toluene, ethanol, water, methanol) | < 0.3 K |
| Methanol–water (no azeotrope in the literature) | complete, no azeotrope fabricated |
| Component order reversed | same physics (< 1e-7 K) and same signature |
| Axis on the other component | xEje = 1 − x, same signature, azeotrope invariant |
| 1.01325 bar against 101325 Pa | same signature; original slice kept |
| Ethanol–water azeotrope against α = 1 with ln γ, Psat and Poynting (another path) | dx < 1e-7, dT < 1e-7 K |
| Azeotrope against the literature (78.15 °C, x 0.894) | 78.07 °C, x 0.881, minimum of T. The ChemSep parameters come from fits to VLE: it is **not** an independent predictive validation |
| Ethanol–water P–xy at 350 K | one maximum-P azeotrope |
| Water/1-butanol at 1 atm | L–V branch interrupted between x = 0.6583 and 0.9789. The meetings at 367.2839 K match (< 1e-4) the L–L–V that the multiphase engine solves by another path (plateau of `equilibrio_PH`). The competing phase is the other liquid. Heteroazeotrope 94.13 °C against 93.0 °C in the literature (± 2 K) |
| Pure water above the package's ceiling (373 K) | gap `fuera_de_dominio` and `limite_dominio`, without extrapolating |
| Traces next to x = 0 and 1 (refined) | points < 1e-3 from both ends |
| Two directions of travel | differences < 1e-8 K and < 1e-10 in y |
| Budget exhausted | `parcial`, gap `presupuesto`, only certified points |
| Negative controls of the certificate | potential, normalization and fixed condition altered → `no_cumple`; L–V root in an LL zone → equal μ but `inestable`, liquid competitor |
| 12 structured rejections | three components, pair without parameters, pure water, P or T outside the domain, unit, null datum, interval, axis, revision, extra field, fingerprint |
| Real LV samples from the v2 assembly (heating at constant P) | (T, x, y) on their T–xy (dT < 1e-6 K) and the lever rule with the published β (< 1e-9) |
| Fingerprint of the assembly against that of the diagram | equal |
| Static L–V states at fixed T | on their P–xy (< 1e-9). The assembly has no dynamic isothermal case: it is declared as such |

Measured cost (this machine, cold):

| System | exploratoria | refinada |
|---|---|---|
| benzene–toluene | 0.6 s, 41 points | 0.7 s, 137 points |
| ethanol–water | 0.6 s, 47 points | 1.0 s, 142 points |
| water–butanol (LL competition) | 1.4 s, 18 points | 2.2 s, 48 points |

Others: `node tests/verificar_contrato_diagramas.mjs` compiles the 11 example pairs against the contract, with negative controls, and checks each response's invariants (285 points). The examples are in `docs/ejemplos/motor-diagramas/` and are generated with `python tests/generar_ejemplos_motor_diagramas.py`.

## 6b. Liquid–liquid and three-phase points (F8, 23 October 2026)

`core/coexistencia_ll.py` is the shared operation; like the L–V one it uses only the package's public interface and
contains no activity formula. The response gains the optional block `liquidoLiquido` (contract type
`LiquidoLiquidoDiagrama`, additive in revision 1: a revision-1 reader ignores it, and `frontend/verificar_diagramas_equilibrio.mjs`
passes unchanged). Drawing it in the interface is D4 work (Codex).

- **Seeds.** On a grid of the free condition (24 temperatures in Txy, 12 pressures in Pxy), a single-liquid reference
  at 13 compositions is tested with the tangent plane; only where another liquid lowers it is the package's certified
  TP flash run, and a two-liquid result becomes a seed. A seed on an already traced branch is skipped, so separate
  L–L regions give separate branches.
- **Continuation.** Pseudo-arclength in (q, logit x_a, logit x_b), q = T/10 K (Txy) or ln P (Pxy), on
  μ_i^L(x_a) = μ_i^L(x_b), in both directions with tangent orientation kept; a turning point of the free condition is
  followed, not declared. Steps halve on a failed corrector and grow after fast ones (`dsMax` 0.25 exploratory,
  0.08 refined). Every pair is certified: μ equality ≤ 1e-10 RT, normalization, fixed condition, distinct liquids and
  the tangent plane with the common μ against vapor and liquid trials.
- **Ends.** (1) Critical point: when the liquids come within 2e-3, h' = h'' = 0 with h = (μ_0 − μ_1)/RT of one liquid
  (five-point differences) is solved in (q, logit x): the binodal's fold, published as `critico_ll` with its residual
  and stability. (2) Three-phase point: when a vapor trial lowers the tangent plane, (q, x_a, x_b, y) is solved from
  the four μ equalities and certified as `tres_fases`. (3) The package's domain (`limite_dominio`). (4) Budget or no
  convergence, as incidences; the branch is published up to its last certified pair, never extrapolated.
- **Pxy.** g^E does not depend on P and the pure-liquid Poynting terms cancel between two liquids, so a Pxy branch is
  vertical; it ends at the three-phase pressure.

Evidence, `python tests/test_diagram_liquid_liquid.py` (7 tests): a two-suffix Margules liquid reproduces its analytic
binodal (ln((1−x)/x) = (a/T)(1−2x), x_b = 1 − x_a, residual ≤ 1e-10) and its critical point T = a/2, x = 1/2 within
1e-6; water–1-butanol (NRTL-LLE) pairs equal the package's TP flash within 1e-7; its three-phase point, 367.283865 K at
1 atm, equals the L–V tracer's meeting within 1e-4 K and the earlier multiphase plateau (367.2839 K), with two liquids
just below and vapor just above; a Pxy slice at 360 K gives P* = 77,345 Pa and the Txy slice at P* returns 360 K within
1e-6; a miscible pair has no branch; the axis on the other component mirrors every pair. Probes (`.tmp/claude-f8/`):
UNIFAC original and Dortmund water–1-butanol (three-phase 366.18 K and 365.89 K), water–benzene (342.33 K; water-rich
liquid with 1.75e-3 benzene) and water–ethyl acetate, Txy and Pxy, both profiles: every pair certified, 0.8–4.2 s.

## 7. Pending limits

- Binaries only. A three-component sheet receives `MOTOR_DIAG_COMPONENTES_NO_SOPORTADO`; no component is removed or renormalized.
- L–L branches and L–L–V points are binary only; SLE regions are not plotted.
- The L–V continuation is in the liquid's x; a fold in x would show up as a declared failure or gap. The L–L branch uses arc length, and a binary pair branch turns only at its critical point, where it ends.
- Stability is a grid test with refinement, not a proof of the global minimum.
- Critical region: excluded by the packages (T ≤ 0.9 Tc), never extrapolated. Ideal vapor up to 5 bar.
- `agua-iapws95` and ice are single-component: their diagram is P–T (the existing route).
- There are no persistent jobs or streamed progress: the measured slices take under 3 s. The budget is cooperative between points; aborting the HTTP request does not stop the calculation in progress.
- D4 (reader, view, markers, cache, export) and end-to-end validation with the interface belong to Codex.

## 8. Files

New: `core/coexistencia_lv.py`, `core/diagramas_equilibrio.py`, `backend/motor_diagramas.py`, `docs/contratos/contratoDiagramasEquilibrio.ts`, `tests/validar_motor_diagramas_equilibrio.py`, `tests/generar_ejemplos_motor_diagramas.py`, `tests/verificar_contrato_diagramas.mjs`, `docs/ejemplos/motor-diagramas/*`, this document.

Modified (additive): `backend/main.py` (2 routes), `core/mezclas.py` (`Sistema.huella`), `core/paquetes_volumen.py` (the packages' `huella`), `backend/motor_ensamblaje_v2.py` (`resultados.procedenciaModelo`), `docs/contratos/contratoEnsamblajeV2.ts` (type of `procedenciaModelo`), `docs/ejemplos/motor-v2/*` (regenerated: they only gain `procedenciaModelo`).
