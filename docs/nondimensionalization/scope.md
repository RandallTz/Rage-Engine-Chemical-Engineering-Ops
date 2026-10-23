# Nondimensionalization: what it does, how it is used and what is left out

State as of 18 October 2026: **module closed within this scope**. Whatever is not listed under "What it does" is not offered, and the interface says so when it comes up; there are no panels that pretend to calculate.

Nondimensionalization is an extension of the engine (`/motor`). It reads the engine's matter sheets without modifying them and shares its look: the notebook imports the engine's CSS modules. Screen and tab names are quoted as the interface shows them (in Spanish).

## What it does

**Core** (`core/adimensionalizacion`, Python, its own exact algebra; pint only for units):

- **Dimensions:** checks the homogeneity of each equation, infers the missing dimensions and asks only for the units that are indispensable.
- **Transformation and search:**
  - multiplicative, affine and declared nonlinear changes of variable, with their inverse;
  - automatic search of every normalization of the family (targets by exact rank);
  - each formulation is certified by back substitution.
- **Groups:** groups of the formulation, the system's Π theorem and alternative bases; complete trace of the algebraic derivation.
- **Document v2:**
  - targets per term and global-factor references;
  - priority of scales;
  - location of the boundary conditions;
  - functions with a declared scale, D(c) = D* D̂(u).
- **Study of a formulation** (operation `estudiar`):
  - physical reading of the groups (Fourier, Péclet, Damköhler…);
  - sensitivity and values in SI;
  - dominant regime with boundary layers;
  - scales, recommended mesh and stiffness;
  - symmetries and reduction by similarity or travelling waves;
  - linear stability σ(k) with Turing and Hopf;
  - continuation with folds;
  - simulation by the method of lines with BDF, in one coordinate or none, with an optional periodic boundary and a final time in seconds, and an exportable Python script.

**Interface** (`frontend/app/adimensionalizacion`):

- **Notebook (since 19 October 2026):** Desde el Engine · Adimensionalizadas · Archivadas · Retiradas (From the Engine · Nondimensionalized · Archived · Retired). Export and import the notebook.
  - **Only entry:** an Engine sheet. Nondimensionalization works only on equations derived from the fundamental ones with assumptions (ARCHITECTURE.md §2, principle 10).
  - Models are no longer written here: "Nueva hoja", the "Catálogo" and "Añadir modelos de partida" are gone.
  - In a derived document the equations are shown read-only, with a link to their Engine sheet. To change them, edit the sheet and import it again.
  - Editing the model as JSON and the location of the conditions are closed. What belongs to nondimensionalization is still worked on: scales, targets, maps, the sign of the variables and studies.
  - **Retired:** when the notebook is opened, or imported, every document without an origin in the Engine (`adim.motor.<id>`) is retired (`hojas.ts`, `retirarEscritas`). It is kept, with its reason and date, so it can be exported; it is not opened for work.
  - `ejemplos.ts` and the `docs/ejemplos/adimensionalizacion-*` files remain as test fixtures of the core and the format; they are not offered in the interface.
- **Sheet**, following the engine's path (← Hojas · Ecuaciones · Formulaciones · Estudio · Desarrollo · Comparar). Each page has a card, a figures panel and one main button:
  - Equations: text, preview, units and "Opciones avanzadas" (search, fixed scales, signs, domains and conditions, JSON, import or export the document);
  - Formulations: dimensionless equations, groups and folded technical details;
  - Study: physical values as engine rows and analysis tabs;
  - Development: the step-by-step trace;
  - Compare: the formulations side by side with your values.
- **Saved results**, as in the engine, in IndexedDB `rage-adimensionalizacion-resultados`. They are reused only if the document and the text did not change; renaming the sheet does not invalidate them.
- **From the engine:** imports a matter sheet (total, local transient or 1D field), preloads its values in SI, simulates up to its final time and gives one figure: the difference from the engine's saved result.
- **Printable report and exports:** LaTeX of the development, JSON, CSV and a Python script.

## What is left out of this scope

It is declared, not approximated.

- **Automatic search:**
  - it does not propose logarithmic or power changes of variable (they are declared by hand in the form);
  - it does not accept non-monomial targets.
- **Geometry and scales:** no coupled curvilinear coordinates, and no scales that depend on t or x.
- **Simulation:**
  - one spatial coordinate;
  - centred differences, which can oscillate with dominant convection if a coarser mesh than recommended is forced;
  - no events: unlike the engine, it does not stop if a field reaches zero;
  - only derivatives of order 1 and 2.
- **Import from the engine:**
  - it does not translate `step`, state rules or a variable mean density;
  - nor energy, multi-volume assemblies or thermodynamics, which belong to the next connection (phase M3).
- **Storage:** studies (simulation plots, continuation) are not saved; they are recalculated. Physical values and formulations are saved.

## Verification

From the root, with `PYTHONIOENCODING=utf-8`:

- `python tests/validar_adimensionalizacion.py`: 264 core checks.
- `python tests/validar_estudio_adimensionalizacion.py`: 63 checks against analytical solutions.
- `python tests/validar_capa_dimensional.py` and `python tests/validar_api_adimensionalizacion.py`.

From `frontend/`:

- `node verificar_adimensionalizacion.mjs` (103), `verificar_integracion_adimensionalizacion.mjs` (79), `verificar_capa_dimensional.mjs` (33), `verificar_estudio_adimensionalizacion.mjs` (66) and `verificar_importacion_motor.mjs` (117; the engine's 8 test sheets against the engine and the analytical solution).
- `npx tsc --noEmit --incremental false` and `npx eslint app/adimensionalizacion`.

## Related documents

- [docs/contracts/nondimensionalization-core.md](../contracts/nondimensionalization-core.md): the core's contract.
- [docs/history/frontend/plan-nondimensionalization-equations.md](../history/frontend/plan-nondimensionalization-equations.md): plan and record.
- [docs/history/frontend/plan-connection-nondimensionalization-engine.md](../history/frontend/plan-connection-nondimensionalization-engine.md): M1 done; M2–M4 pending.
- [docs/nondimensionalization/continuity.md](continuity.md): to pick the work back up.
