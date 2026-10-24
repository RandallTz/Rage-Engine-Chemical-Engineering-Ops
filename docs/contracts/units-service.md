# The single units service

18 October 2026. Step 3 of [ARCHITECTURE.md](../../ARCHITECTURE.md) §10. It is the only place in the project that interprets a unit.

- **Code:** `core/unidades/`.
- **HTTP:**
  - `GET /unidades/capacidades`: the catalog of quantities;
  - `POST /unidades/interpretar` with `{unidades: [text…]}`, up to 500 units.
- **Tests:** `tests/validar_unidades.py` (264) and `frontend/verificar_unidades_motor.mjs` (235).

## 1. What it publishes

`interpretar(unidad)` returns:

| Field | Content |
|---|---|
| `dimension` | Exact exponents (fractions) over M, L, T, N, Theta, I, J |
| `factor`, `desplazamiento` | value_SI = factor · value + offset. The offset is non-zero only on affine scales (°C, °F); `degC/s` is a rate (= K/s) with no offset |
| `unidadSI` | Canonical text: W, J, Pa, N; J/mol, J/(kg*K), W/K; or the base units (kg/s, mol/m^3, m^2/s) |
| `magnitudes` | The catalog names with that dimension |

It also exposes `a_SI`, `desde_SI`, `compatibles` and `magnitudes_de`.

`exact_conversion(unit)` is the Python mathematical-authoring adapter. It returns the same dimensional metadata with rational `Fraction` factor/offset from a Fraction-configured Pint registry using the same definitions and normalization. It never converts rounded float factors into exact proof premises; nonrational or nonpositive conversion factors are rejected. Before reducing to SI it traverses Pint's canonical definition dependencies, including aliases and prefixes, rejecting the mathematical decimal constants `pi`, `tansec`, `ln10`, `eulers_number`, `wien_x` and `wien_u`, as well as nonrational scales. A decimal approximation in a Fraction registry is not an exact rational proof. Rejection uses `ErrorUnidad`, propagated by interval authoring as its existing structured operation error. A radian quantity with endpoints `[0,90] degree` is rejected; no symbolic pi or approximation is inserted. Rational controls remain `km/hour = 5/18`, `inch = 127/5000`, `percent = 1/100`, `cal = 523/125`, `liter = 1/1000` and `minute = 60`. `degF` still reports an affine conversion and interval authoring rejects it. Existing float APIs and HTTP responses remain unchanged. Exactness follows the catalog definitions, not an independent certification of empirical unit constants. Model currently accepts multiplicative absolute endpoint units only; affine reference operations remain pending.

pint does the interpretation. The service only normalizes the project's spellings:

- compact powers: `m3`, `cm2`, `s-1`;
- the superscripts `³` and `²`, and the middle dot `·`;
- `°C` and `°F`;
- a dimensionless unit written as `1`, `-`, `adimensional` or empty text.

## 2. No bias toward any operation

- Quantities are defined **only by their dimension**: mass, molar flow, specific heat capacity, thermal conductance, volumetric rate… None is tied to a piece of equipment or a type of operation.
- **There are no closed lists** of units per quantity: any unit with the right dimension is valid (psi, BTU/lb, gal/min, cP, Btu/(h·ft·°R)…).
- Several quantities can share a dimension: pressure and energy density, for example. That is why the name of a quantity is never deduced from a unit; only candidates are offered.

## 3. Equivalence with the systems it replaces

| System | Where | Result |
|---|---|---|
| The engine's table (TS) | `frontend/app/motor/unidadesMotor.ts` | The 47 units of its 18 quantities give the same conversion (1e-12) and the same dimension |
| The engine backend's table | `backend/motor_ensamblaje.UNIDADES`, plus the revision-2 extensions | Same factor, same offset, same dimension and same SI unit |
| Nondimensionalization | `core/adimensionalizacion/dimensional.interpretar_unidad` | Same dimension and same factor on a sample of 36 units |
| Lab | `core/dimensiones._cantidad` | Same factor |

All four still exist: the engine and the lab are not modified without an explicit request. The checked equivalence allows them to be replaced by the service when each engine migrates (step 5).
