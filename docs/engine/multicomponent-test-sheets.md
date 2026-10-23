# Multicomponent sheets of the independent engine

2026-10-13. Only `/motor`. No changes in the lab or in Claude's backend.

In `/motor/hojas`, **Añadir ejemplos multicomponente** (add multicomponent examples) adds four complete sheets without overwriting the existing ones. Each sheet keeps its components, volumes, streams, expressions, assumptions and data. The examples are editable documents for the generic assembler; the solver does not recognize or treat their names specially.

| Sheet | Components | Volumes / balances | What to look at |
| --- | --- | --- | --- |
| Series mixing | A, B, C | 2 / 6 | Each inlet, transfer and outlet contributes a different rate per component. At 10 s: v1 = [30, 35, 37.5] kg; v2 = [47.5, 52.5, 60] kg. |
| Selective exchange | A, B, C, D | 2 / 8 | Volumes of 1 and 2 m³. A crosses toward v2; B toward v1. C has equal concentrations and does not cross; D has an explicit zero rate. |
| Conversion and transport | A, B, C, D | 3 / 12 | Mass conversion A → B → C in every volume, with the same laws; D inert. The streams carry all four components. The total mass stays at 3 kg. |
| Eight components and traces | A–H | 2 / 16 | Closed exchange with different rates. Initial amounts from 4 kg down to 1e-8 kg; conservation of each component. |

A–H are symbolic components, with no chemical formulas or `thermo` properties attributed to them. The conversion declares compatible mass rates of generation and consumption; it does not infer molecular stoichiometry, molar masses or reaction energy.

## Equations and solution

Each volume contributes one state and one balance per component. Each stream contributes one rate per component, shared by its two ends, with opposite signs. The data are complete, structural DOF = 0 and every initial condition is declared.

The references are calculated apart from the assembler and the integrator:

- Series: linear increments given by inlet − outlet of each species.
- Selective exchange: `m_A,v1 = 1 + 2 exp(-0.45t)`; `m_B,v1 = 2 - 2 exp(-0.15t)`. The initial total determines the masses of v2. C and D stay constant.
- Conversion: reactive fractions `[exp(-0.1t), 0.1t exp(-0.1t), 1-(1+0.1t)exp(-0.1t)]`, multiplied by the transport weights `[exp(-0.2t), 0.2t exp(-0.2t), 1-(1+0.2t)exp(-0.2t)]` of the three volumes. D keeps 2 kg distributed with the same weights.
- Eight components: `m_i,v1 = m_i,0 (1+exp(-2k_i t))/2`; `m_i,v2 = m_i,0 - m_i,v1`. `k_i` goes from 0.10 to 0.45 s⁻¹. The absolute tolerance declared in this sheet is 1e-16 kg.

## Results

The new multi-species dashboards show every state, grouped by volume with up to four curves per chart. The traces example has eight charts: one per component, comparing the two volumes with a scale of its own. Charts can be edited, moved, enlarged and removed. Dashboards the user already customized are kept.

The table includes every state and the totals. Table, axes and tooltips show small amounts in scientific notation, so trace values are not shown as zero. The axis limits use the real scale of the data to tell a small trajectory apart from relative noise on a constant signal. These decisions only affect presentation; the CSV and the series keep their original numbers.

## Verification

`npm run test:multicomponente-materia`: **13150 checks**, with analytical references at every sample, local/global conservation, one variable per stream and component, pending DOF, eight reordered species, KaTeX rendering, a catalog without duplicates, the table, full chart selection, numbers and axes on traces. The earlier `test:motor-fundamental` battery also passes; TypeScript and ESLint checked.

Browser review: four sheets added to the existing store without replacing documents; the eight-component case solved; sixteen balances and initial conditions visible; table with 1e-4, 1e-6 and 1e-8 kg; eight charts saved; keyboard reordering and the scales of G/H checked. The other three sheets remain ready for the user to press Resolver.

The visual review could be completed in this delivery. There was no comparison against the backend, and geometries, spatial dimensions, energy or momentum were not extended. No commit or push.
