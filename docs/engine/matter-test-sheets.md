# Matter test sheets ready to solve

13 October 2026. Eight editable `/motor` documents, loaded explicitly from "Añadir hojas de prueba · materia" (add test sheets · matter). The backend and the lab are not modified. They are independent references for cross-checking the engine later, not scenarios built into the numerical compiler.

In `/motor/hojas`, each card has "Resolver →". It leads to the complete form; pressing Resolver is enough. They all start with structural DOF 0, complete initial values, and declared units, horizon and boundary conditions. The new sheets contain no precalculated results: the current equation is run. The derivation and the assumptions can be reviewed or changed from Equations.

| Sheet | Data | Expected reference |
| --- | --- | --- |
| 01 · Tank that fills | m₀=100 kg; inlet 3 kg/s; outlet 2 kg/s; 10 min | m(t)=100+t; final 700 kg |
| 02 · Tank that drains | m₀=100 kg; inlet 1 kg/s; outlet 3 kg/s; 30 s | m(t)=100−2t; final 40 kg |
| 03 · Filling in litres | V₀=100 L; inlet 3 L/s; outlet 1 L/s; 5 min | V(t)=0.1+0.002t m³; final 700 L = 0.7 m³ |
| 04 · Equal inlets and outlets | m₀=100 kg; inlet and outlet 2 kg/s; 10 min | m=100 kg along the whole trajectory |
| 05 · Draining until empty | m₀=100 kg; outlet 2 kg/s; requested horizon 120 s | Empties at 50 s; `parcial` is the correct result, not a failure |
| 06 · Conversion of A into B | A₀=1 kg; B₀=0 kg; consumption of A and generation of B = 0.2 m_A kg/s; 20 s | A=e^(−0.2t); B=1−A; final 0.0183156389 / 0.9816843611 kg; total 1 kg |
| 07 · Transport by convection · 1D | x∈[0,1] m; ρ₀=2+0.3 sin(2πx) kg/m³; v=1 m/s; periodic ends; 0.25 s | ρ(x,t)=2+0.3 sin[2π(x−t)]; amount per area 2 kg/m² |
| 08 · Diffusion of two components · 1D | x∈[0,1] m; ρ_A₀=0.5+0.1 sin(2πx); ρ_B₀=1−ρ_A₀; D_A=D_B=0.05 m²/s; periodic ends; 0.5 s | ρ_A=0.5+0.1 e^(−4π²Dt) sin(2πx), ρ_B=1−ρ_A; spatial total 1 kg/m³ |

(The sheets themselves keep their Spanish names, for example "01 · Tanque que se llena".) In the table's formulas, t is in seconds and x in metres; the written coefficients carry the corresponding units. A and B are generic species with a conversion that conserves mass. No properties of real chemical compounds are attributed to them. Generation/consumption is formulated explicitly through coupled expressions, without fabricating a kinetics by choosing a type of equipment.

Sheet 04 keeps the time derivative and obtains dm/dt=0 from its data. It does not use the option to remove accumulation or the steady-state solver (still pending here). Sheet 03 is derived from m=ρ̄V, constant mean density and convective ports with a common density. The density cancels in the final equation, and no value for it is asked for or invented.

Sheets 07 and 08 use 80 cells and RK45 with a CFL limit. The continuous reference does not match the discretization exactly: upwind introduces numerical diffusion, and centred diffusion slightly modifies the rate of the sinusoidal mode. The charts of both sheets are set up to show the evolution in the central cell and the spatial profiles at the same time; in diffusion, A and B appear together.

## Independent check

`npm run test:hojas-materia` runs the eight equations and compares each trajectory with the table's references. It is also part of `npm run test:motor-fundamental`.

- **9190 checks**, including every relevant sample/cell, completeness, active data, non-negative amounts and conservation.
- Filling/draining: maximum absolute error 5.69e−13 kg.
- Volume: maximum error 1.12e−16 m³.
- Constant amount: exact.
- Depletion: t=49.999999999999815 s, with no negative values published.
- A→B: maximum error 1.13e−11 kg; total mass conserved.
- Convection: maximum mean error 0.011423 kg/m³ against the continuous translation; budget −2.17e−18 kg/m².
- Diffusion: maximum error 1.890e−5 kg/m³ against the continuous field; sum of densities and budgets correct.

Browser QA: the eight sheets have Resolver enabled, DOF 0, complete values and initial values. They were added to the user's browser, keeping their earlier and archived documents. The form and the library are reviewed without overloading the screen with explanations.

## Persistence and files

`app/motor/hojasPruebaMateria.ts` only builds documents through the editor's existing operations. There are no branches by name/scenario in the solver. Each sheet is editable, duplicable and archivable. Stable, versioned test IDs: adding the batch again does not duplicate, overwrite or unarchive an edited variant. The batch is saved once and keeps every other sheet.

Original changes: the document generator, additive batch saving in `hojasMotor.ts`, library entries, local styles and `verificar_hojas_prueba_materia.mjs`. The original `BibliotecaHojas.tsx` frontend has since been removed: all templates now enter through `ModelLibrary.tsx` and the shared `ModelWorksheet.tsx`, with assumptions on the right. Numerical methods, backend and lab were not changed by the template work; no commit or push.
