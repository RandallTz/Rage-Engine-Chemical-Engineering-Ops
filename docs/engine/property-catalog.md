# F2 · Catalog and properties (cumulative delivery)

Delivery of phase F2 of [docs/engine/multiphysics-roadmap.md](multiphysics-roadmap.md), in the format of [docs/history/frontend/coordination-claude-codex-engine.md](../history/frontend/coordination-claude-codex-engine.md). Changes in core, backend, tests, canonical contracts and `docs/`. `frontend/`, `/laboratorio` and `thermodynamics/proveedor.py` were not touched. No commit, push or deployment. No dependency was updated and no datum was modified.

**Reload:** restart the service (`uvicorn backend.main:app`). The new route `GET /motor/catalogo` must respond. The existing capabilities do not change (§5).

## 1. State by milestone

| Milestone | State | Evidence |
|---|---|---|
| F2.1 audit and extensible registry | **Backend verifiable** | Single registry `core/catalogo.py`; identity, pure-component data and package requirements separate (§2–§3) |
| F2.2 properties with unit, source, domain and fingerprint | **Backend verifiable** for the pure-component data of the mixture packages | Published in `GET /motor/catalogo` (§4). The properties derived from the state stay in the evaluation |
| F2.3 admission by data and structured rejections | **Backend verifiable** | A single rule per species; a code of its own per missing datum; **F9-R3 closed** (§3) |
| F2.4 substitution of pure-component data | **Backend verifiable** | v_L, ideal-gas cp and Psat per species, with source and domain, in the three routes; consistent potential; fingerprint; rejections (§11) |
| F2.5 references between packages | **Backend verifiable** | Streams between packages with the same reference accepted and conservative. IAPWS-95 ↔ mixture still rejected, with the figure that justifies it. Formation data audited (§12) |
| F2.6 a real new substance and regression | **Backend verifiable** | Acetone added only through the registry and cross-checked with Tb, ΔHvap and the azeotrope with methanol (§13). Full regression in §10 |
| F9-R4 (new, fixed) | Fixed | PH/UP inversion of a pure species in a mixture package when Tsat(P) falls within the domain (§14) |

## 2. F2.1 · Audit

**Before:**

- The list of species was fixed in `core/mezclas_datos._ESPECIES` and mixed identity (name, M) with the provenance of the data.
- Admission was decided in several places, with different criteria:

| Place | How it decided |
|---|---|
| `core/mezclas.Sistema` | Membership of the list. For NRTL-LLE, membership of the pair. For UNIFAC, the group assignment, **only with 2 or more species** |
| `backend/motor_mezclas.capacidades_mezcla` | Special cases per package (the NRTL-LLE pair, a filter of UNIFAC assignments) |
| `backend/motor_termodinamica` and `backend/motor_diagramas` | Membership of the list or of `componentesCAS` |

That difference produced **F9-R3**: with the UNIFAC LLE table, pure methanol was evaluated even though the capabilities excluded it, because with a single species the group model is not built.

**Now:**

| Piece | File | Content |
|---|---|---|
| Identity | `core/catalogo.REGISTRO` (a `MappingProxyType` of frozen `RegistroSustancia`) | CAS, name, M with its source, the Psat table and v_L with its method |
| Pure-component data | `core/mezclas_datos.especie` (unchanged) and `datos_puros_faltantes(cas)` (new) | Wagner's Psat and Poling's cp, from `chemicals`' pinned tables. They are loaded once, under the F0 lock, and never during a flash |
| Package requirements | `core/catalogo.requisitos(liquido)` and `faltantes(liquido, cas)` | Per species: pure-component data, group assignment of the variant, membership of the NRTL-LLE pair or the IAPWS-95 formulation (water only). Per pair or per group: checked when building the liquid model |
| Admission | A single rule: empty `faltantes(...)` | The `Sistema` applies it (also with one species), as do the capabilities and the catalog |

`Especie` and the values do not change. That is why **the packages' fingerprints are identical** to those published in F1; section 0 of the suite checks it.

## 3. F2.3 · Admission and rejections

| Situation | Code (prefix `MOTOR_ESTADO_`, `MOTOR_ENS_` or `MOTOR_DIAG_`) | Datum in `faltantes` |
|---|---|---|
| Unregistered CAS (e.g. acetone, which does have DDBST groups: having groups is not enough) | `COMPONENTE_NO_SOPORTADO` | `registro` |
| Registered, but without coefficients in a table | `DATO_PURO_AUSENTE` (**new**) | `presion_vapor`, `cp_gas_ideal`, `masa_molar` or `volumen_liquido` |
| Outside the NRTL-LLE water/butanol pair, **also pure** | `PARAMETRO_AUSENTE` | `parametros_nrtl_lle` |
| Without a group assignment in the UNIFAC variant, **also pure** (methanol with LLE) | `UNIFAC_ASIGNACION_AUSENTE` | `asignacion_grupos_lle` |
| Not water, with IAPWS-95 | `COMPONENTE_NO_SOPORTADO` | `formulacion_iapws95` |
| Missing NRTL pair or group interaction | `PARAMETRO_AUSENTE` / `UNIFAC_INTERACCION_AUSENTE` | Per set: it does not appear in the catalog |

**F9-R3 closed.** Pure methanol with `unifac-original-lle-public` returns `no_soportado` with `MOTOR_ESTADO_UNIFAC_ASIGNACION_AUSENTE`, the same as in a mixture. In the assembly it gives `MOTOR_ENS_UNIFAC_ASIGNACION_AUSENTE`.

**Decision on the pure species.** With g^E = 0 a pure species needs no groups. Even so, the rule requires the package's per-species requirements also in the pure limit, for two reasons:

- the contract asks for one rule for the pure limit and for mixtures;
- a pure volume can receive another species during a trajectory.

Pure methanol is still available with the packages that admit it (ideal, NRTL, original UNIFAC and Dortmund).

## 4. F2.2 · Published catalog (`GET /motor/catalogo`)

Types: `docs/contratos/contratoCatalogo.ts` (`CatalogoMotor`, revision 1). No parameters and no side effects.

- **`sustancias[]`**:
  - `id` = CAS, `nombre`, `masaMolar` {valor, unidad, fuente};
  - `datosPuros`:
    - `estado` (`completos` | `incompletos`) and `faltantes`;
    - `propiedades`: `presion_vapor` (form, coefficients, unit Pa, source, domain in T), `cp_gas_ideal` (coefficients, J/(mol K), source, domain) and `volumen_liquido` (value, m3/mol, condition, source);
    - `dominioLiquido` and `huella` (sha256 of the pure-component data used, which are part of the package's fingerprint).
  - A reader can reproduce the Psat and cp used from the published coefficients; this is checked to 1e-12.
- **`paquetes[]`**:
  - `modelo`, `nombre`;
  - `requisitos` {`porEspecie`, `porPar`, `porGrupo`};
  - `operaciones`:
    - `estado.especificaciones`;
    - `ensamblaje.disponible` (and `coberturaGrupos` if the v2 route publishes it);
    - `diagramas`: {disponible, operaciones};
  - `especies[]`: one entry per substance, in the catalog's order, with `admitida` and `faltantes` {dato, codigo, mensaje}. An admitted species also carries `dominio` {T, motivo}: the temperature range [K] where this package evaluates it. It is the runtime's own domain for that species alone: the intersection of its vapor-pressure and ideal-gas Cp ranges, T <= 0.9 Tc and the package's parameter-table interval (UNIFAC-LLE 283.15–313.15 K, NRTL-LLE 293–373 K). For IAPWS-95 packages it is the model domain. A mixture is evaluated only inside the intersection of its species' ranges.
  - `dominio` {T, P, motivo} (additive, F0-2, 22 October 2026): the envelope of the admitted species' ranges and the state route's pressure range. It equals the domain in `/motor/termodinamica/capacidades`. It is not the domain of a given system.
- **`regla`**: the admission semantics in text.
- **`noDisponible`**: adding substances from the request, overrides (F2.4) and alignment of references (F2.5).

**Consistency checked.** The admitted species of each package are exactly the `componentesCAS` of the three routes: state, assembly v2 and diagrams. Building the catalog checks it with an `assert`, and the suite repeats it per route and pure species against the `Sistema`.

The admitted and cross-checked sizes, the state domains and the evidence stay in each route's capabilities; the catalog does not duplicate them.

## 5. Published changes

| Element | Change |
|---|---|
| Capabilities of state, assembly v2 and diagrams | None. F1's `motor-termodinamica-capacidades.json` was compared with the new response: identical |
| Package fingerprints | None |
| Rejections that change | A pure species without the package's requirement. Before: methanol with LLE `evaluado` and ethanol with NRTL-LLE `PARAMETRO_AUSENTE`. Now: a rejection with the code of §3 in every package |
| New route | `GET /motor/catalogo` |
| New code | `DATO_PURO_AUSENTE` |

## 6. F2.5 · Initial audit of references (the F2.1 version; final result in §12)

- **Mixture packages:** they all share the reference `gas-ideal-298.15K-1bar-h0-s0` per species, and the molar mass comes from the same registry.
- **IAPWS-95 water:** it uses `iapws95-u0-s0-liquido-saturado-punto-triple`.
- **Streams:** assembly v2 rejects **any** stream between volumes with different packages (`MOTOR_ENS_REFERENCIAS_INCOMPATIBLES`). It is safe, but more restrictive than necessary. Between two mixture packages (for example NRTL and UNIFAC) the per-species reference is the same and the transported enthalpy would be consistent.
- **Next step of F2.5:**
  - accept streams between packages with an identical reference;
  - formulate an explicit IAPWS ↔ 298.15 K ideal-gas conversion for water, or keep the rejection;
  - show conservation in both cases.
- **Formation data** (preparation for F5): they are not in the registry. `chemicals` has Hf°(g) and S°(g) for the 7 species (`chemicals.reaction.Hfg` and `S0g`; for example water −241 822 J/mol and 188.8 J/(mol K)). Their source and their consistency with the packages' reference still have to be audited before using them.

## 7. Evidence

`python tests/validar_motor_catalogo.py`, 87 checks. Sections:

- **0. Registry.** Read-only and a frozen dataclass. The fingerprints of three packages and the point capabilities are identical to those published in F1.
- **1. Single rule.**
  - Admitted = `componentesCAS` of the three routes for the 8 packages.
  - The `Sistema` of each pure species is built or rejected as the catalog says, with the same code (6 mixture packages × 7 species = 42 combinations).
  - F9-R3 in state and in assembly; pure ethanol with NRTL-LLE; acetone in state and diagrams.
- **2. Extensibility (simulated within the test's process).**
  - Acetone, registered with data from the same tables and v_L from `thermo` (HEOS_FIT), is admitted in ideal and UNIFAC, not in NRTL-LLE or IAPWS-95.
  - Water–acetone with original UNIFAC gives a certified TP **without new code**.
  - A registered substance without tables gives `DATO_PURO_AUSENTE` per property in the `Sistema` and in the service.
  - The registry is restored at the end.
- **3. Content and independent cross-check.**
  - The published coefficients reproduce the Psat and cp used.
  - Water's Psat (Wagner–McGarry) against IAPWS-95, from 280 K to 0.9·Tc: < 0.2 %.
  - Normal boiling temperature against the NIST Chemistry WebBook:

    | Species | Calculated (K) | Literature (K) | Difference (K) |
    |---|---|---|---|
    | water | 373.16 | 373.12 | +0.04 |
    | ethanol | 351.44 | 351.39 | +0.05 |
    | benzene | 353.24 | 353.24 | 0.00 |
    | toluene | 383.79 | 383.75 | +0.04 |
    | 1-butanol | 390.88 | 390.88 | 0.00 |
    | ethyl acetate | 350.22 | 350.26 | −0.04 |
    | methanol | 337.69 | 337.85 | −0.16 |

- **4. Concurrency and HTTP.** 8 cold threads build the same catalog; the HTTP route matches the function; the response is a copy.

**Examples:** `docs/ejemplos/motor-catalogo/` (`python tests/generar_ejemplos_motor_catalogo.py`):

- the catalog;
- the point capabilities;
- three rejections: F9-R3, pure ethanol with NRTL-LLE and unregistered acetone;
- pure methanol with original UNIFAC, evaluated.

**Verifier:** `node tests/verificar_contrato_catalogo.mjs`. It does:

- compilation of the types with negative controls;
- a single identity;
- one entry per substance in each package;
- admitted ⇔ without missing items;
- admitted = point `componentesCAS`;
- rejections with their code.

## 8. Files

**New:**

- `core/catalogo.py`
- `backend/motor_catalogo.py`
- `docs/contratos/contratoCatalogo.ts`
- `docs/ejemplos/motor-catalogo/` (32 JSON after F2.6)
- `tests/validar_motor_catalogo.py`
- `tests/generar_ejemplos_motor_catalogo.py`
- `tests/verificar_contrato_catalogo.mjs`
- this document

**Modified:**

| File | Change |
|---|---|
| `core/mezclas_datos.py` | View of the registry and `datos_puros_faltantes` |
| `core/mezclas.py` | The `Sistema` applies the single rule and gives the codes `COMPONENTE_NO_SOPORTADO` and `DATO_PURO_AUSENTE` |
| `backend/motor_mezclas.py` | Capabilities from the rule; the special cases were removed |
| `backend/main.py` | Route `GET /motor/catalogo`, added bytewise and respecting the line endings |

## 9. Work for Codex (F2.1–F2.3; F2.4–F2.6 is at the end of §15)

1. Synchronize `contratoCatalogo.ts`.
2. Discover substances and packages from `GET /motor/catalogo`, without a chemical list of its own. Keep symbolic components for balances without properties.
3. When choosing a package, offer only the species with `admitida`, and limit temperatures to the intersection of the chosen species' `dominio.T`; a state outside it is rejected with `MOTOR_ESTADO_FUERA_DE_DOMINIO`. For the others, show the `dato` and the `mensaje` of the missing item (e.g. "sin grupo CH3OH en la tabla ELL"). This also applies with a single component (F9-R3).
4. Show the pure-component properties (source, unit, domain, fingerprint) in details, separate from the properties of the evaluated state.
5. Treat `DATO_PURO_AUSENTE` as a missing datum, like `PARAMETRO_AUSENTE` and `UNIFAC_*`.
6. The reader's guard for pure methanol with LLE can stay. The backend now returns the structured rejection, so a local exception is not needed.

## 10. Regression run

Run on 16 October 2026 with the final code; the Python suites in parallel:

| Command | Result | Exit |
|---|---|---|
| `python tests/validar_motor_catalogo.py` | OK, 87 | 0 |
| `python tests/validar_motor_unifac.py` | OK, 136 | 0 |
| `python tests/validar_motor_termodinamica.py` | OK, 585 | 0 |
| `python tests/validar_motor_termodinamica_h3.py` | OK, 3729 | 0 |
| `python tests/validar_motor_ensamblaje.py` | OK, 245 | 0 |
| `python tests/validar_motor_ensamblaje_v2.py` | OK, 114 | 0 |
| `python tests/validar_motor_consolidacion_v2.py` | OK, 128 | 0 |
| `python tests/validar_motor_n_componentes.py` | OK, 82 | 0 |
| `python tests/validar_motor_diagramas_equilibrio.py` | OK, 78 | 0 |
| `node tests/verificar_contrato_catalogo.mjs` | OK: 7 substances, 8 packages, 4 cases | 0 |
| `node tests/verificar_contrato_unifac.mjs` | OK | 0 |
| `node tests/verificar_contrato_ensamblaje_v2.mjs` | OK | 0 |
| `node tests/verificar_contrato_diagramas.mjs` | OK | 0 |
| `node tests/verificar_contrato_motor_termodinamica.mjs` | OK | 0 |
| `node tests/verificar_contrato_ensamblaje.mjs` | OK | 0 |
| `npm run test:motor-fundamental` (in `frontend/`) | OK | 0 |

The examples of earlier deliveries were not regenerated: the capabilities and fingerprints do not change (§5), and the verifiers pass with them.

*(The table above belongs to the F2.1 delivery. The F2.4–F2.6 regression is in §15.)*

## 11. F2.4 · Substitution of pure-component data

**What is substituted and why only that.** Each species of a mixture package is described by a single Gibbs function per phase, built from three inputs: Psat (Wagner), the ideal-gas cp (Poling) and v_L (`core/mezclas_datos`). h, s, μ, the liquid's cp, the density and the heat of vaporization are **derived** from those inputs. That is why only those three inputs can be substituted, and the substitution changes the same potential with all its derivatives.

| Property (`datosPuros[cas]`) | Fields | Check on reading |
|---|---|---|
| `volumen_liquido` | `valor`, `unidad` (m3/mol, cm3/mol, L/mol), `fuente` | > 0 |
| `cp_gas_ideal` | `coeficientes` {a0..a4} of cp/R, `dominio.T`, `fuente` | cp > 0 at 201 points of the domain |
| `presion_vapor` | `forma` (WagnerPoling \| WagnerMcGarry), `coeficientes` {A, B, C, D, Tc, Pc}, `dominio.T`, `fuente` | Tc > 0, Pc > 0, Tmax ≤ Tc; ln P finite, strictly increasing and ≤ ln Pc at 201 points |

The pure liquid's T domain (`T_rango`) is recalculated with the substituted domains.

**Rejections.**

- `*_SUSTITUCION_NO_ADMITIDA` (`no_soportado`), in three cases:
  - `masa_molar`: it is identity, and changing it would alter the inventories;
  - any property of the state: h, s, μ, the liquid's cp, density;
  - any substitution in IAPWS-95: it is a complete formulation.
- `*_SUSTITUCION_INVALIDA` (`invalido`): missing source, invalid unit or domain, cp ≤ 0, a non-physical Psat, a CAS foreign to the request or an unknown field.
- They all carry a path: `declaracion.datosPuros.<cas>.<propiedad>[.campo]` in the point service, and the JSON path in assembly and diagrams.

**Where it is declared.**

| Route | Field |
|---|---|
| Point state | `declaracion.datosPuros` |
| Assembly v2 | `paquetes[].datosPuros`; each volume applies those of its species |
| Diagrams | `datosPuros` |

Types: `SustitucionDatosPuros` in `docs/contratos/contratoCatalogo.ts`. `PaqueteV2.datosPuros?` and `SolicitudDiagrama.datosPuros?` are additive.

**Fingerprint and expiry.**

- The substitution, with its source, goes into the package's fingerprint: the same value with another source gives another fingerprint.
- Without a substitution, the fingerprint is exactly the usual one.
- The substitution does not alter the registry or the global cache: it is applied on a copy of `Especie` in that `Sistema`.
- No echo of the substitutions is published: the request is their record and the fingerprint (`huellaModelo`, `procedenciaModelo[].huella`) their proof.

**Consistency checked** (catalog suite, section 7):

| Substitution | Check |
|---|---|
| v_L | the phase's v changes by exactly x_i·Δv_L; ∂g/∂P = v; g = h − T s |
| cp_ig ×1.1 | the vapor's ∂h/∂T = the new cp, to 1e-7 |
| Psat (A ×1.02) | Clapeyron h_ig − h_L = T(RT/Psat − v_L)·Psat' holds with the new Psat; ethanol's Tb goes from 351.44 K to 353.45 K and the TP at Tb' + 0.01 K is vapor |

In diagrams, the pure end is the new Psat; in assembly, V(0) includes the substituted v_L and the trajectory is certified.

## 12. F2.5 · References between packages and conservation

- **Between mixture packages:** they all use `gas-ideal-298.15K-1bar-h0-s0` per species and the same M from the registry.
  - A stream between volumes with different packages is accepted if `referencia.id` matches.
  - Published capability: `corrientes.entrePaquetes = "misma_referencia"`, additive and typed.
  - Evidence: an NRTL ChemSep → original UNIFAC network (stream and thermal contact), with matter per species < 1e-12, energy and second law certified.
- **IAPWS-95 water ↔ mixture:** water's h_mixture − h_IAPWS goes from −46 296 to −45 586 J/mol between 280 and 500 K and between 1 and 5 bar. It varies by ~710 J/mol because the models differ (incompressible liquid and ideal vapor against IAPWS-95).
  - No constant converts one reference into the other while conserving energy. The stream is still rejected with `MOTOR_ENS_REFERENCIAS_INCOMPATIBLES`, and the message names both references.
  - **Thermal contact** is accepted, because heat does not depend on the reference, and it is certified.
- **Formation data (preparation for F5):** `chemicals.reaction.Hfg/S0g` has Hf°(g) and S°(g) at 298.15 K and 1 bar for the 8 species. That is the same state reference as the mixture packages', and the zero (h = s = 0 of the ideal gas) would be replaced by Hf° and S° per species. They are not added in F2: their source per species still has to be audited and cross-checked before F5.

## 13. F2.6 · Acetone (67-64-1) added through the registry

**Data**, from the same tables and versions as the 7 base species:

| Datum | Value | Source |
|---|---|---|
| Psat | Poling's Wagner (`chemicals` 1.5.2), 178.45–508.1 K | `chemicals` |
| cp_ig | Poling's polynomial, 200–1000 K | `chemicals` |
| v_L | 7.4014e-5 m3/mol | `thermo` 0.6.1, VolumeLiquid HEOS_FIT at 298.15 K, the same method as most |
| M | 58.07914 g/mol | `thermo` |
| UNIFAC groups | CH3 + CH3CO | DDBST original and Dortmund; in the LLE table, translated with identical R and Q |

**Without new code.** It is admitted in ideal, NRTL ChemSep and the three UNIFAC variants, and not in NRTL-LLE or IAPWS-95. The NRTL pairs with data resolve themselves. With acetone there are 5 complete NRTL sets of 4 species and 1 of 5 (previously 2 and 0). **They have no dynamic cross-check of their own**: `tamanos.contrastados` does not change.

**Independent cross-check.**

| Quantity | Literature | Engine |
|---|---|---|
| Tb at 1 atm | 329.22 K | 329.22 K |
| ΔHvap at Tb (CRC) | 29.10 kJ/mol | 30.70 kJ/mol (+5.5 %) |
| Acetone–methanol azeotrope at 1 atm (Horsley, *Azeotropic Data*) | 55.5 °C, x_acetone ≈ 0.80 | original UNIFAC 55.22 °C / 0.781; Dortmund 55.28 / 0.787; NRTL ChemSep 55.36 / 0.791 |
| Acetone–water heating with UNIFAC (dynamics) | — | bubble point detected and trajectory certified |

**ΔHvap at Tb for the 8 species** (CRC Handbook):

| Species | Engine (kJ/mol) | Literature (kJ/mol) | Difference |
|---|---|---|---|
| water | 41.31 | 40.65 | +1.6 % |
| ethanol | 40.48 | 38.56 | +5.0 % |
| benzene | 31.84 | 30.72 | +3.6 % |
| toluene | 34.63 | 33.18 | +4.4 % |
| 1-butanol | 44.89 | 43.29 | +3.7 % |
| ethyl acetate | 33.44 | 31.94 | +4.7 % |
| methanol | 37.25 | 35.21 | +5.8 % |
| acetone | 30.70 | 29.10 | +5.5 % |

It is a **systematic bias** of the already declared ideal-vapor model: Clapeyron with Z = 1 overestimates Δv, and therefore ΔH, when the real vapor at 1 atm has Z ≈ 0.95–0.98. It is not an error in acetone's data. It is published in the evidence; correcting it needs a non-ideal vapor (F8, EOS).

**Note on the v_L.** The registry's v_L are literals fixed at registration; they are not recalculated at start-up. For example, `thermo` 0.6.1 gives 1.80686e-5 m3/mol for water today against the registered 1.80683e-5. Recalculating them would change the fingerprints without an intended physical change.

## 14. F9-R4 · PH/UP inversion of a pure species in a mixture package (fixed)

**Finding.** When testing the IAPWS/mixture contact, this rejection appeared: `Componente puro en saturación a 373.161 K: T y P no determinan el reparto` (pure component at saturation at 373.161 K: T and P do not determine the split).

**Cause.** The isobaric search of a pure species puts the end of the interval at Tsat(P)·(1 ∓ 1e-9). But the pure TP rejects as ambiguous the band |P/Psat − 1| ≤ 1e-6, which in T is ~8e-8 relative. The end fell inside the band, and so did `_TP_seguro`'s retry at 1e-12.

**Scope.** Any PH/UP of a pure species in a mixture package with Tsat(P) in the domain. No test covered it.

**Fix** (`core/mezclas`). Within the isobaric search of a pure species, the side of Tsat is already known: liquid below and vapor above. That phase is evaluated (`_puro_TP(..., lado=)`) instead of rejecting. The direct TP still rejects the ambiguity.

**Verification:**

- PH of pure water (ideal) at 320, 373, 373.16 and 380 K recovers T and the phase;
- a state 1.9e-6 K below Tsat, inside the band, is solved;
- the IAPWS/mixture contact is certified.

## 15. F2.4–F2.6 regression

Run on 16 October 2026 with the final core; the Python suites in parallel:

| Command | Result | Exit |
|---|---|---|
| `python tests/validar_motor_catalogo.py` (sections 0–7) | OK, 126 | 0 |
| `python tests/validar_motor_unifac.py` | OK, 136 (coverage of 8 species; the case "with groups and without pure-component data" becomes n-hexane) | 0 |
| `python tests/validar_motor_n_componentes.py` | OK, 82 (the N0 audit stays on the 7 species of its delivery and reports the new NRTL sets with acetone) | 0 |
| `python tests/validar_motor_termodinamica.py` / `_h3.py` | OK, 585 / 3729 | 0 |
| `python tests/validar_motor_ensamblaje.py` / `_v2.py` / `consolidacion_v2.py` | OK, 245 / 114 / 128 | 0 |
| `python tests/validar_motor_diagramas_equilibrio.py` | OK, 78 | 0 |
| `node tests/verificar_contrato_catalogo.mjs` | OK: 8 substances, 8 packages, 8 point cases, 7 assemblies and diagrams | 0 |
| `node tests/verificar_contrato_{unifac,ensamblaje_v2,diagramas,motor_termodinamica,ensamblaje}.mjs` | OK | 0 |
| `npm run test:motor-fundamental` (in `frontend/`) | **Fails in `verificar_consolidacion_multifasica.mjs`**: "Contract copy is current" | 1 |

I ran separately the frontend verifiers that follow in the chain. Four fail, and **none is physical**:

| Verifier | Reason |
|---|---|
| `verificar_consolidacion_multifasica`, `verificar_diagramas_equilibrio`, `verificar_cobertura_grupos`, `verificar_catalogo_motor` | They compare their copy of the contract with the canonical one, which changed: `entrePaquetes`, `datosPuros`, `SustitucionDatosPuros` |
| `verificar_integracion_unifac` | It has 6 species pinned in the LLE table; with acetone there are 7. Methanol stays excluded |

The rest pass.

**Regenerated examples** (root, `motor-v2/`, `motor-n-componentes/`, `motor-diagramas/`, `motor-unifac/`, `motor-catalogo/`), compared number by number with the F2.1 copy, ignoring `tmMinimo` and the wall time:

- **States, trajectories and diagrams:** no numerical change at all.
- **Capabilities:** only additive changes:
  - acetone in the `componentesCAS` of the packages that admit it;
  - 5 more NRTL pairs in `pares`; the list changes order because it is walked in the registry's order;
  - `corrientes.entrePaquetes`;
  - the group coverage with 8 species.
- **Catalog:** 8 substances.
- **`motor-catalogo/`:** the rejection of unregistered acetone becomes that of n-hexane, and there are 12 new F2.4–F2.6 cases (24 files).

### Work for Codex (F2.4–F2.6)

1. Synchronize the copies of `contratoEnsamblajeV2.ts`, `contratoDiagramasEquilibrio.ts` and `contratoCatalogo.ts`, and update in `verificar_integracion_unifac` the count of the LLE table (7 species, methanol excluded).
2. Offer acetone from the catalog. No list of its own is needed: it arrives in `GET /motor/catalogo`.
3. Editing `datosPuros` (F2.4), in details and not on the main screen:
   - only `volumen_liquido`, `cp_gas_ideal` and `presion_vapor`, with the source required;
   - keep the original value and the user's choice;
   - show the `SUSTITUCION_*` rejections with their path;
   - after substituting, invalidate results and cache **by fingerprint**: the fingerprint changes with the datum and with the source;
   - the substitutions of an assembly package travel in `paquetes[].datosPuros` and apply to all its volumes.
4. Network: a stream between volumes with different mixture packages is now accepted (`entrePaquetes = "misma_referencia"`). Between IAPWS-95 water and a mixture, only thermal contact; the stream is rejected with `MOTOR_ENS_REFERENCIAS_INCOMPATIBLES`.
5. Record **F9-R4** (§14) as fixed.

### Limits that remain

- The substitutions are only of pure-component data of mixture packages. They do not include NRTL or UNIFAC parameters.
- There is no adding of substances from the request: the registry belongs to the server.
- Formation data are audited but not added (F5).
- The ideal vapor overestimates ΔHvap by 2 to 6 % at Tb (§13).
- The new NRTL sets with acetone have no dynamic cross-check of their own.
