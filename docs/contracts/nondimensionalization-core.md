# Nondimensionalization core contract (A0)

Date: 16 October 2026. Author: Claude (core). Addressed to: Codex (interface, readers, persistence). Translated to English on 19 October 2026; field names, codes and states are those of the published JSON format and stay in Spanish.

This file fixes the exchange between `/adimensionalizacion` and the scientific core. The plan and the progress record are in [docs/history/frontend/plan-nondimensionalization-equations.md](../history/frontend/plan-nondimensionalization-equations.md). **Integration implemented by Codex:** the endpoints of §7, the response reader, the "Adimensionalizar" button and the local v2 document with the maps of §8. The core keeps its v1 document contract through an explicit adapter.

## 1. Single location of the core

`core/adimensionalizacion/` (Python, at the repository root). It is the only place with scientific algebra. It uses `fractions` (exact) and `pint` only to interpret units. It does not use sympy: it is not in `requirements.txt` and no dependencies were added.

| Module | Responsibility |
|---|---|
| `lector.py` | Strict reader of the v1 document on the server (it does not trust the client) |
| `dimensional.py` | A1: exact rational inference, compatible/incompatible/undetermined, units |
| `algebra.py` | Canonical form of expressions, linearity of operators, structural substitution |
| `transformacion.py` | A2: substitution, chain rule, global factor; A3: targets by exact rank |
| `formulacion.py` | Published formulation: terms, groups, constraints, steps, certificate |
| `grupos_pi.py` | Rational null space, alternative bases, change of basis |
| `nucleo.py` | `procesar(solicitud) -> resultado` and `capacidades()` |

`core/dimensiones.py` (assembly) was neither reused nor modified: it types the engine's terms, not this AST. Nothing is copied from the client: `expresionesMotor.ts`, `unidadesMotor.ts` and `operadores.ts` stay as they were.

The client validates structure and presents trees; it does **not** simplify, extract coefficients or decide the states of targets.

## 2. Requests

```ts
type SolicitudNucleo = {
  formato: "adimensionalizacion.solicitud"; version: 1;
  operacion: "analizar" | "transformar" | "adimensionalizar";
  documento: Documento;            // v1 or v2 exchange document (§13), with optional `exploracion`
  formaId?: string;                // required in "transformar"; optional (base form) in "adimensionalizar"
  transformaciones?: Transformacion[]; // general maps (§10.2); "transformar" and "adimensionalizar"
  opciones?: OpcionesBusqueda;     // "adimensionalizar" only (§10.1)
};
```

`analizar` accepts no optional fields.

Exploration uses, unchanged, the format `prepararExploracion` already generates (`solicitud_exploracion_adimensional`, version 1). The core accepts it as is, validates `modelo`, `formaBase`, `config` and each proposal, and rejects operations other than `normalizar_magnitud_coeficiente` with `conservarSigno: true`.

An unknown field or version is rejected; there is no silent migration.

## 3. Decisions of the contract (the A0 points of the delivery)

**Dimensions.** `null` = pending (unknown); `{}` = dimension one. Exponents `{n, d}` reduced, without zeros. Base names are free: the core does not depend on them, so `{L,T,N}` and `{L,T,C}` give the same equations (tested). Units are projected onto the SI bases `L, M, T, I, Theta, N, J`. **Temperature is called `Theta`** (the client's reader does not accept `Θ`).

**Zeros and numbers.** The number `0` is compatible with any dimension; any other number is dimensionless. `c + 1` with a dimensional `c` is incompatible.

**Units.** They are interpreted with pint. If the symbol does not declare a dimension, the unit fixes it (`origen: "unidad"`). If it declares both and they do not match, the error points to `simbolos[i].unidad`. A unit with an offset (`degC`, `degF`) marks an **affine absolute** temperature: a purely multiplicative scale on it is rejected (code `temperatura_afin`), but an affine map with a declared reference is accepted (§10.2). `K` and `delta_degC` do accept a scale. A `cantidad` scale requires the variable to use SI bases. The core publishes `valorSI` and `unidadSI`.

**Dependencies.** `Simbolo.dependeDe` and `funciones[].dependeDe` (explicit dependence on t/x besides the arguments) decide what comes out of a derivative. A non-constant symbol without declared dependencies is assumed to depend on everything (it is not extracted). `D(c)` is treated as an opaque call: it is transformed as `D(c_ref c_ad)` and its kernel keeps dimensions, so the normalization stays `parcial` with reason `nucleos_dimensionales`. To extract a scale `D*`, the v2 declaration is needed (§8).

**Operators.** Cartesian coordinates only. A `gradiente` of several coordinates is a vector and is accepted only inside a `divergencia` with the same coordinates. A product accepts at most one vector factor, and an equality must be scalar (otherwise, code `rango`). Single-coordinate operators are kept as nodes. Multi-coordinate ones are expanded into Cartesian components when some coordinate is scaled, because each coordinate can have its own scale.

**Identity of terms.** `terminoId = "<ecuacionId>:<ruta>"`, with the same path as `terminosExplorables` (nested sums are flattened). If a syntactic summand expands into several coefficients (for example `k (c - c^2)`), each part receives the suffix `#1`, `#2`, …, and the id without a suffix does not identify a single coefficient. The `analizar` operation publishes the complete catalog. Conditions use `<condicionId>:<ruta>`.

**v1 targets.** `Forma.objetivos[].termino` is matched with a term of the equation by canonical structure, ignoring the numerical factor. `valor` is the required value of the **effective coefficient as written, with its sign**: for `-a c^2`, `-1` is asked for. If `+1` is asked for with `a > 0`, the result is `incompatible` with code `signo`. In exploration (`normalizar_magnitud_coeficiente`) magnitude 1 is required and the sign is kept.

**Global factor.** Each equality is divided by the magnitude of the coefficient of its left side when that is a single monomial term. That is published separately (`factorGlobal`) and is not a choice of scale. That is why a target on the time term comes out `dependiente`. If the factor contains a parameter declared null, it is not divided (warning `sin_factor_global`).

**Signs.** A negative parameter is represented as `-|p|`, so the resolved scales use `abs(p)` and the sign stays in the equation. Unknown sign: the target stays `pendiente` (`signo_desconocido`). Null parameter: the target is `incompatible` (`parametro_nulo`) and it is never divided by. A scale given by an expression of negative sign is rejected. If its sign is unknown, the assumption `positivo` is published.

**Conditions and location.** They are transformed with the same substitution and keep their type. The v1 contract does not declare which end of the domain a boundary condition uses. The core transforms the domain's ends and the equality, and publishes `ubicacion: "frontera del dominio (el contrato v1 no declara el extremo)"`. The precise location is a v2 extension (§8).

**Link and validity.** Each result carries:

```ts
vinculo: { documentoId: string; modeloId: string; modeloRevision: number; formaId: string;
           eleccion: { escalas: Escala[]; objetivos: Forma["objetivos"]; presentacion: Forma["presentacion"] };
           firma: string /* "sha256:…" from the server */ }
```

**Client rule:** a result is valid only if `modeloId` and `modeloRevision` match the document and `eleccion` is deeply equal to the form's `{escalas, objetivos, presentacion}`. `formaId` alone is not enough. The `firma` is informative: the server calculates it over Python's canonical JSON, and the client must not try to reproduce it, because the formatting of floats differs between JavaScript and Python.

**Failures.** `estado ∈ {"correcto", "rechazado", "no_soportado", "requiere_datos"}`. `requiere_datos` means there are undetermined dimensions: `dimensional.faltantes` says what to ask. If it is not `correcto`, the result contains **only** `vinculo` (if it could be read), `diagnosticos` and `dimensional` (if it was analysed): never equations, groups or a certificate. The client must discard any earlier result of that form whose link no longer matches.

## 4. Result of `analizar`

`dimensional = { estado, simbolos: [{ id, dimension | null, origen: "declarada"|"unidad"|"inferida"|"indeterminada"|"sin_uso", unidad?: {texto, dimension, afin} }], funciones, faltantes: string[] }` and `terminos: [{ id, ecuacionId, lado, ruta, expresion, divididoEn }]`.

**Indispensable data (for the minimal view).** If the state is `indeterminado`, `faltantes` gives a minimal set of dimensions that it is enough to declare for the core to infer all the others. Variables (`c`, `t`, `x`) are preferred over parameters, and zeros do not count as data. Tested example: in `∂c/∂t = D∇²c + kc − ac²` with everything pending, `faltantes = ["c", "t", "x"]`; on declaring only those three, `D`, `k`, `a` and `ell` become `inferida`. The client only has to ask for those symbols. `transformar` and `adimensionalizar` require the state `compatible`; if it is not, they answer `requiere_datos` with those `faltantes`.

`diagnosticos: [{ ruta, codigo, severidad: "error"|"aviso", mensaje, simbolos? }]`. Paths use the style of the client's reader (`ecuaciones[0].derecha.argumentos[2]`, `simbolos[3].unidad`, `forma.escalas[1].valor.unidad`). A1 codes: `dimension_incompatible`, `dimension_indeterminada`, `rango`, `unidad_no_reconocida`, `unidad_no_comparable`.

## 5. Result of `transformar` (state `correcto`)

| Field | Content |
|---|---|
| `simbolos` | **New** symbols (the model's are referenced by id). Scale: `{id: "<v>_ref", nombre, rol: "escala", variableId, dimension, estado, valor, cantidad?}`. Dimensionless variable: `{id: nuevoNombre, nombre, rol: "variable_adimensional", rolOrigen, variableId, dimension: {}, dependeDe}` |
| `escalas` | `{simboloId, escalaId, estado: "libre"|"dada"|"dada_por_expresion"|"determinada"|"relacionada", valor}`. `relacionada` = determined as a function of free scales |
| `libres` | Remaining free scales: the formulation is a family parametrized by them |
| `normalizacion` | `{estado: "completa"|"parcial", motivos: [{codigo: "variables_sin_transformar"|"nucleos_dimensionales"|"grupos_dimensionales", …}]}` |
| `ecuaciones` | `{igualdad, factorGlobal, terminos: [{id, lado, ruta, original, coeficiente, grupoId, nucleo, dimensionNucleo}]}` |
| `dominios` | `{id, variableId (new), desde, hasta}` |
| `condiciones` | `{id, tipo, dominioId, ecuacion, factorGlobal, terminos, ubicacion}` |
| `directa` / `inversa` | `v = scale · v'` and `v' = v / scale`, with the values already resolved |
| `grupos` | `{id, definicion, dimension, adimensional, contieneEscalasLibres, usos: [terminoId], interno, inversoDe}`. `interno` = a coefficient inside a function or an internal sum (for example `K/c_ref`) |
| `objetivos` | `{id, terminoId, estado: "satisfecho"|"dependiente"|"incompatible"|"pendiente"|"conservado", codigo?, motivo, responsables?, relacion?, valorObjetivo?, coeficienteFinal?, comprobado?}` |
| `rangoObjetivos` | Exact rank of the system of targets applied |
| `restricciones` | `{id, tipo: "positivo"|"no_nulo"|"signo"|"igualdad", expresion, motivo, signo?, valor?}` |
| `pasos` | `{ambito, regla, antes, despues, supuestos}` with `antes`/`despues` = `{izquierda, derecha}`. Rules: `sustitucion_de_variables`, `regla_de_la_cadena`, `linealidad_y_agrupacion`, `division_por_factor_global`, `sustitucion_de_escalas_dadas`, `sustitucion_de_escalas_determinadas` |
| `equivalencia` | `{estado: "demostrada"|"no_demostrada", alcance, restricciones: [id], comprobaciones: [{ambito, tipo: "sustitucion_inversa"|"dominio"|"dimensiones"|"objetivo", estado}]}` |
| `terminos` | Catalog of the original's terms (the same as in `analizar`) |

A target `incompatible` by overdetermination carries `responsables` (every choice involved) and `relacion: {izquierda, derecha}`: the relation between data that would be needed (for example `D/(k x_ref²) = 1` when L was fixed before). Incompatible or pending targets are **not applied**, and the published formulation stays certified.

`presentacion: "factorizada"` groups the terms with the same non-numerical coefficient. `"desarrollada"` does not group them. It is the same transformation.

### Certificate

`demostrada` means that, applying the inverse substitution to **what is published** and multiplying by the global factor, the Cartesian canonical form coincides with the original's. This holds for each equation, condition and domain. In addition, the dimensions of each published equality agree and each applied target equals exactly what was asked for. The canonical form uses only identities valid under the published constraints (text in `equivalencia.alcance`):

- derivatives are expanded with the product, power and chain rules (exp, log, sin, cos, powers);
- the derivatives of declared functions, abs, min and max stay unexpanded;
- `log(exp y) = y` is used, and `exp(log y) = y` only with `y > 0` according to the declared signs and domains;
- no other exp/log/trig identities are used, nor the exchange of mixed derivatives.

To decide whether the difference is zero, it is multiplied by the sums that appear as denominators (non-zero, because the original divides by them) and expanded. If something does not match, the state is `no_demostrada`. No numbers are sampled. A test confirms that the certificate detects a lost term.

## 6. Exploration and Π groups

`operacion: "explorar"` returns:

- `evaluaciones: [{propuestaId, estado: "evaluada"|"duplicada"|"no_soportado", formulacionId, objetivos, resumen}]`;
- `formulaciones: [<body of transformar> + {id: "F<n>", propuestas: [ids]}]`. A formulation duplicates another if it has the same equalities, conditions and domains in canonical form, regardless of the order of the terms;
- `cobertura: {propuestasRecibidas, propuestasEvaluadas, formulacionesDistintas, duplicadas, noSoportadas, agotadoTiempo, siguientePropuesta, …}`. There is a limit of 60 s; if it runs out, `siguientePropuesta` says where to continue, and the continuation is reproducible by resending `propuestas.slice(siguientePropuesta)`;
- `gruposPi` (if `config.incluirGruposPi`): `{cantidades, excluidas: [{id, motivo}], matriz, rango, numeroGrupos, bases: [{id: "B<n>", repetidas, grupos: [{id, exponentes, definicion}], enReferencia}], cobertura: {eleccionesDeRepetidas, revisadas, basesDistintas, omitidasPorCotas, duplicadas, limitadoPorPresupuesto, cotas, nota}}`.

`enReferencia` gives the rational coordinates of each group in the basis `B1`; the core checks the reconstruction before publishing it. A group and its inverse count as the same basis. The groups of a formulation that contain no free scales carry `enBasePi`. The Π inventory is separate from the effective coefficients and is **not exhaustive**: any product of rational powers of a basis is another valid group.

## 7. Implemented API

- `GET /api/adimensionalizacion/capacidades` → `capacidades()`.
- `POST /api/adimensionalizacion` with the body `SolicitudNucleo` (any of its three operations) or `solicitud_exploracion_adimensional` → `procesar(cuerpo)`. Always HTTP 200 with `estado`; HTTP 4xx only if the body is not JSON or exceeds 1 MB.
- `POST /api/adimensionalizacion/dimensiones` receives an `analizar` request and returns the analysis and the per-term audit of §12. Another operation receives HTTP 400.

`backend/api_adimensionalizacion.py`, registered in `backend/main.py`, delegates to `procesar` and `capacidades`, with the unit normalization and policy of §12. The POST limits the body to 1 000 000 bytes while reading, rejects invalid JSON or non-JSON numbers with 400 and uses 413 for an oversized body. The calculation runs in the server's worker pool; the mathematical decisions stay exclusively in `core/adimensionalizacion/`.

The client queries capabilities, sends the request and validates the complete response in `app/adimensionalizacion/lecturaNucleo.ts`: version, state, link, choices, maps, options, references to symbols and coordinates, trees, steps, constraints, conditions, domains and coverage. It does not reproduce algebra or try to recalculate Python's signature. A stale response is not presented; editing the document or the text invalidates the calculated view. `requiere_datos` without formulations is accepted, showing only the indispensable units. The continuation resends `opciones.desde = cobertura.siguiente` and keeps the pages received.

The base URL is configured with `NEXT_PUBLIC_ADIMENSIONALIZACION_API_URL`; if it does not exist, it uses `NEXT_PUBLIC_API_URL` and finally `http://localhost:8000`. This allows starting the integrated service without restarting an earlier backend that does not have the route yet.

## 8. Local v2 document and pending extensions

**Implemented:** `Documento.version = 2` accepts `Forma.transformaciones?: Transformacion[]` with the contract of §10.2. The reader validates structure and references, accepts v1 documents, and the explicit migration keeps identity, model and forms. Persistence, branches, import, JSON and LaTeX keep the maps. The interface allows declaring them in the advanced JSON; the invertibility proof belongs to the core.

The `prepararSolicitud` adapter produces a v1 exchange copy without `Forma.transformaciones`, and sends the active form's maps in `SolicitudNucleo.transformaciones`. The main view uses the automatic search without `formaId`, so the core proposes free scales and respects the declared maps. Manual choices of scales and targets are respected only when `formaId` is sent explicitly, as the protocol allows. Results are not stored as a valid cache on reload; they are recalculated. The calculated development is exported separately as a JSON request/response and a complete LaTeX document.

**Implemented in the core (17 October 2026), pending in the client:** the five model extensions this section left pending. The core now accepts `documento.version: 2` directly; the specification is in §13. To use them, the client has to update types, reader, inputs, export and tests together. Until then, the current v1 adapter stays valid and its output does not change.

1. `Forma.objetivos[].terminoId`, together with `termino` or instead of it.
2. `condiciones[].ubicacion: { variableId; extremo: "desde" | "hasta" }`.
3. `funciones[].escala: { simboloId; funcionAdimensional }`, to declare `D(c) = D* D̂(u)`.
4. `Forma.referencias: [{ ecuacionId; terminoId }]`, to divide by a term other than the left one.
5. `Forma.prioridadEscalas: string[]`, to choose which scale is solved for.

With the v2 document, the core also reads `Forma.transformaciones` as the client stores it, without going through the adapter.

(Since 19 October 2026 the notebook only works on documents imported from an Engine sheet; see [docs/nondimensionalization/scope.md](../nondimensionalization/scope.md).)

## 9. Canonical examples

`docs/ejemplos/adimensionalizacion-<name>-{solicitud,resultado}.json`: `automatico`, `requiere-datos`, `mapa-logaritmico`, `mapa-afin-temperatura`, `analizar`, `general`, `tiempo-difusivo`, `tiempo-reactivo`, `campo-cinetico`, `longitud-parametrica`, `condiciones`, `parcial`, `signo-negativo`, `rechazo-suma-incompatible`, `rechazo-forma-desactualizada`, `explorar`, those of the v2 document (§13), `v2-funcion-escalada` and `v2-referencias-ubicacion`, and those of `estudiar` (§14): `estudio-calor`, `estudio-brusselator` and `estudio-pliegues`. They are generated by `tests/generar_ejemplos_adimensionalizacion.py`. `tests/validar_adimensionalizacion.py` checks that they match the current core, so a client reader can be tested against them.

## 10. Simple input and general families (extension of 16 October)

It answers the "Última corrección del usuario" (latest correction from the user) of the delivery.

### 10.1 `adimensionalizar`: automatic search

Designed for the "Adimensionalizar" button of the minimal view. The client sends only the document with the equation and the core does the rest:

1. **It analyses** the dimensions. If they stay undetermined, it answers `requiere_datos` with `dimensional.faltantes`, the minimal set to ask about (for example `["c", "t", "x"]`), and publishes no formulations. If they are incompatible, it answers `rechazado` with the path.
2. **It chooses the maps.** Without `formaId`, it transforms every variable present with free scales. Exceptions: those with a map declared in `transformaciones`, and those with an offset unit, for which it publishes the warning `requiere_referencia` (it does not invent a reference). With `formaId`, it respects that form's scales and targets.
3. **It goes through** every **independent** subset of normalizable effective coefficients, in order of size and then of model. A dependent or incompatible subset gives the same formulation as an independent one that is also gone through, so the search is complete for this family. With a reason, it excludes the terms that do not depend on free scales (the global factor fixes the time term), those of unknown sign, the null ones and the non-monomial ones.
4. **It removes provable duplicates** and certifies each formulation as in `transformar`.

```ts
type OpcionesBusqueda = {             // all optional
  presupuesto?: number;     // 1–2000 formulations evaluated (200)
  maxObjetivos?: number;    // 0–12; by default, the number of free scales
  desde?: number;           // continuation index (0)
  gruposPi?: boolean;       // true
  maxExponentePi?: number; maxDenominadorPi?: number;   // 1–12 (4)
  presentacion?: "factorizada" | "desarrollada";
};
```

The `correcto` result contains:

- `formaBase`;
- `formulaciones`: the body of `transformar` plus `{id, objetivosAplicados, subconjuntos}`;
- `evaluaciones`;
- `gruposPi`;
- `cobertura: {familia, candidatos, excluidos, constantesLibres, maxObjetivos, desde, evaluados, formulacionesDistintas, duplicadas, completa, agotado: null | "presupuesto" | "tiempo" | "enumeracion", siguiente}`.

To continue, resend with `opciones.desde = cobertura.siguiente`. Tested example: with `∂c/∂t = D∇²c + kc − ac²` and nothing configured, **8 formulations** come out, search `completa`, including the five of §3 of the plan. Each formulation with free scales is an infinite family parametrized by them (`libres`).

### 10.2 `Transformacion`: a general direct/inverse map

`Forma.escalas` stays the multiplicative case. The other maps are sent in `transformaciones`. Proposal for storing them in a v2 document: `Forma.transformaciones`, with the same type.

```ts
type Transformacion = {
  variableId: string;          // field, time or coordinate of the model
  nuevoId: string;             // new (dimensionless) variable
  directa: Expresion;          // v = g(new, constants, parameters)
  inversa: Expresion;          // new = h(v, constants, parameters)
  constantes: { id: string; nombre: string; papel: "escala" | "referencia";
                dimension: Dimension;   // null = the core infers it from g and h
                valor: { tipo: "libre" } | { tipo: "cantidad"; valor: number; unidad: string } | { tipo: "expresion"; expresion: Expresion } }[];
  dominio: { original: "positivo" | "negativo" | null; nuevo: "positivo" | "negativo" | null };
};
```

Rules:

- **The expressions g and h.** They are algebraic: no derivatives, operators or declared functions.
- **Constants.** Scales are positive and references can have any sign. A reference can carry a unit with an offset (`25 degC` → `298.15 K`); a scale cannot.
- **Invertibility.** It is not assumed: the core **proves** `h(g(w)) = w` and `g(h(v)) = v` in canonical form with the declared domains. If it cannot, it answers `rechazado` with `inversa_no_demostrada`. Examples: `c = C u²` without `nuevo: "positivo"` is rejected, because `(u²)^½ = |u|`; with `c, u > 0` it is accepted.
- **Family** (published in `transformaciones[].familia`): `multiplicativa` if g′ is constant and g(0) = 0; `afin` if g′ is constant; `no_lineal` otherwise.
- **Nonlinear fields.** Derivatives are expanded with the chain rule, including the additional terms. For example, with `c = C e^u`, `∂²c/∂x²` gives `C e^u ((∂u/∂x)² + ∂²u/∂x²)`.
- **Nonlinear coordinates and time.** They are per coordinate (separable Cartesian): `d/dv = (1/g′) d/dv′`, nested for higher orders, with the `no_nulo` constraint on the Jacobian. Domains are transformed with `h`; for example, `x = L(e^ξ − 1)` takes `[0, ell]` to `[0, log(1 + ell/L)]`.
- **Declared domain.** It is published as a `positivo`/`negativo` constraint and is a condition of the certificate.
- **Temperatures with an offset.** A temperature in `degC` is no longer blocked: it is transformed with an affine map `T = T_ref + ΔT θ`.

The capabilities per family are in `capacidades().familias`:

- supported: multiplicative, affine, reference quotient, nonlinear field, nonlinear coordinate and Π groups;
- not supported: coupled or curvilinear changes of coordinates, scales that depend on t or x, and automatic selection of nonlinear maps (the automatic search uses the multiplicative or the declared maps).

### 10.3 `desarrollo`: the complete mathematical trace

Each formulation (of `transformar` and of `adimensionalizar`) includes `desarrollo: PasoDesarrollo[]`. It uses **exactly** the type proposed in `contrato.ts`: `{id, operacion, regla, justificacion, antes, despues, supuestos, objetosAfectados}`, with `antes`/`despues` of the form `{tipo: "expresion"}` or `{tipo: "igualdad", igualdad: {id, izquierda, derecha}}`.

The steps come out in the order in which they are calculated; they are not an explanation reconstructed from the final result:

1. `analisis_dimensional`: homogeneity of each equation and inferred dimensions (in `justificacion` and `objetosAfectados`).
2. `cambio_variables`: each map and its proven inverse, plus `regla_cadena` with `∂v/∂v′ = g′` for time and coordinates.
3. For each term: `sustitucion` and `regla_cadena`, plus `factorizacion` (linearity) or, with nonlinear maps, `regla_cadena` "desarrollo de derivadas" with the additional terms.
4. For each complete equality:
   - `sustitucion`: the equality **before cancelling factors**;
   - `regla_cadena`;
   - `agrupacion` by kernel;
   - `normalizacion`: division by the global factor, with its non-zero condition in `supuestos`;
   - `sustitucion` of the given scales.
5. `normalizacion` per target (coefficient = ±1 before and with the resolved scales substituted, state and responsible choices). Then a step "resolución exacta por rango" per scale solved for and a step "familia libre" per free scale.
6. `sustitucion` of the determined scales, `simplificacion` (presentation factorization) and `agrupacion` with the definition of each group.
7. `geometria_condiciones`: the ends of each domain and the complete steps of each condition.
8. `verificacion_inversa`: the published form against the expanded `F·h(published)`, which recovers the original, with the state of the comparison.

Other rules:

- The core makes no physical hypotheses (it never neglects terms), so it does not emit `hipotesis_fisica`.
- `desarrolloEstado: {estado: "completo", nota}` declares that the trace records every operation performed.
- Every symbol of the trace exists in the model or in the result's `simbolos`, and every differentiation variable is an independent variable of one of the two. The suite checks exactly that, as the client's reader will have to, on every example and formulation.

### 10.4 Format changes with respect to the earlier version of this contract

- There is a new state, `requiere_datos`. The `transformar` operation also uses it instead of `rechazado` when there are undetermined dimensions.
- The result adds `transformaciones` (family, direct, inverse and domain per variable).
- `escalas[]` and the scales' `simbolos[]` add `papel: "escala" | "referencia"`.
- The new variables add `signo`.
- `vinculo.eleccion.transformaciones` appears when maps are sent. In `adimensionalizar`, `vinculo.opciones` comes with the signature.

## 11. Integration rules for the buttons

1. Reader of `adimensionalizacion.resultado` v1: reject unknown versions or formats, check that every symbol reference exists in the model or in the result's `simbolos`, and apply the validity rule of §3.
2. Show `estado`, `normalizacion.estado`, `equivalencia.estado` and the states of the targets as they arrive. The label "adimensional" is shown only when `normalizacion.estado === "completa"`.
3. Show `rol: "escala"` with a subscript (`t_ref`, `c_ref`). The ids `<v>_ref` and `nuevoNombre` are reserved: if they already exist in the model, the core rejects with `identidad_ocupada`.
4. Do not rebuild coefficients in the client: use `ecuaciones[].terminos[].coeficiente` and `grupos`.
5. "Adimensionalizar" of the minimal view: send `operacion: "adimensionalizar"` without scales. If `requiere_datos` arrives, ask only for `dimensional.faltantes` and resend. If `correcto` arrives, show the `formulaciones` with their `libres` and the `cobertura`; if `cobertura.siguiente` is not null, offer "more" with `opciones.desde`.
6. Affine and nonlinear maps go in `transformaciones` (§10.2). Storing them in the document needs v2 (`Forma.transformaciones`).

## 12. The interface's dimensional layer and sheets

The wrapper `backend/dimensiones_adimensionalizacion.py` uses the existing core's `procesar`, `analizar_modelo` and `Analizador`. It adds no transformer or dimensional rules in JavaScript. Each summand must have dimensions compatible with its equality; different equations of a system can have different dimensions. Common symbols are resolved jointly.

`POST /api/adimensionalizacion/dimensiones` returns:

```ts
{
  formato: "adimensionalizacion.dimensiones", version: 1,
  analisis: RespuestaNucleo, // analizar: includes link, diagnostics and dimensional
  ecuaciones: [{id, dimension, terminos: [{ruta, lado, expresion, dimension,
    estado: "compatible" | "incompatible" | "pendiente" | "cero", operadores}]}],
  cantidades: [{id, unidadIntroducida, unidadNormalizada, magnitudes: string[]}],
  catalogo: [{id, nombre, unidad}]
}
```

The client's reader validates the link and checks paths, order and trees against the request's terms. The browser does not calculate the per-term states. Quantities are identified by the inferred dimensions, and they are candidates: a dimension by itself does not tell pressure from energy density, for example. The catalog offers declarations of common units; the real interpretation of compound units uses pint, not a closed frontend list.

Explicit input aliases are normalized, such as `Kg` → `kg`, `litros` → `L`, `segundos` → `s`, and the notation `m³` → `m^3`. `L` in a unit means litre; in a dimension it is the length base. An identifier `L` in the equation is still a user symbol. No physical unit or dimension is deduced from a symbol's name. If pint does not recognize a unit, or it is not comparable with the declared bases, the wrapper publishes a rejection and removes formulations/certificates, even if the core could infer dimensions from other constraints. The check certifies dimensional homogeneity; it does not show that a physical law is correct or that its numerical data satisfy the equality.

The dynamic query waits 450 ms after an edit and cancels the earlier requests. The view presents mathematical role, entered unit, declared/inferred dimension, compatible quantities, operators and compatibility per term. Operators determine syntactic roles; an isolated symbol on the left of an algebraic equality is proposed as the dependent variable. The mathematical function can be changed explicitly; strict reading keeps the constraints on derivatives and coordinates.

**Sheets.** `rage.adimensionalizacion.hojas.v1` stores an independent notebook of up to 50 sheets. Each sheet contains a v2 `Documento`, a text draft (also incomplete), a date and an archive flag. Creating, naming, duplicating with an independent identity, archiving/restoring and importing/exporting the notebook are supported. The document of the earlier key is migrated to the first sheet without deleting it. The Rage engine's keys and sheets are not reused. Results are recalculated, keeping the existing validity rule. (Since 19 October 2026: the notebook's only entry is importing an Engine sheet, and hand-written documents are retired: [docs/nondimensionalization/scope.md](../nondimensionalization/scope.md).)

**Result.** After calculating, a dedicated view opens within the sheet, with the final equations, calculated groups, free scales and equivalence conditions. An alternative with fewer free scales is selected initially, and all the alternatives are kept. "Resultado final", "Desarrollo completo" and "Comparar alternativas" separate the readings without shortening the trace. The relations between equations come from the core's groups and Π bases: the client does not add ratios like D1/D2 on its own.

**Verification.** `tests/validar_capa_dimensional.py` checks equivalent units, aliases, terms with several variables, functions/operators, inference, incompatibilities, blocking of invented units, equations with different dimensions and a two-field system with 12 certified formulations and a ratio between diffusivities. `frontend/verificar_capa_dimensional.mjs` validates the real data, the reader's rejections, LaTeX, sheet migration, drafts, independent duplication, archiving and the algebraic case. The earlier suites of the contract and the core are kept.

## 13. Document v2 in the core (17 October 2026)

The core reads `documento.version ∈ {1, 2}`. A v2 is a v1 plus the optional fields below. A v1 document that carries any of them is rejected with a contract error, and a v2 that uses none gives exactly the same result as the equivalent v1; the suite checks it with the five forms of §3. The result format is still `adimensionalizacion.resultado` v1: the new output fields appear only when the corresponding v2 field is used. `capacidades()` publishes `contratoDocumento: 2`, `versionesDocumento: [1, 2]` and the list `documentoV2`.

```ts
type ObjetivoV2 = { id; ecuacionId; valor: 1 | -1; accion; terminoId?: string; termino?: Expresion };   // at least one of the two
type FuncionV2 = Funcion & { escala?: { simboloId: string; funcionAdimensional: string } };
type CondicionV2 = Condicion & { ubicacion?: { variableId: string; extremo: "desde" | "hasta" } };
type FormaV2 = Forma & {
  objetivos: ObjetivoV2[];
  transformaciones?: Transformacion[];                 // §10.2
  referencias?: { ecuacionId: string; terminoId: string }[];
  prioridadEscalas?: string[];
};
```

### 13.1 `objetivos[].terminoId`

The target is identified by the id from the `analizar` catalog (`<ecuacionId>:<ruta>[#k]`, §3), without matching structures. The reader requires the id to start with `<ecuacionId>:`. Whether the term exists is decided by the core:

- If it does not exist, the target stays `pendiente` with code `termino_no_encontrado`. When the summand is split into parts, the reason names the `#k`.
- If `terminoId` and `termino` both arrive and designate different terms, the target stays `pendiente` with `termino_contradictorio` and is not applied.

In both cases the formulation stays certified.

### 13.2 `condiciones[].ubicacion`

`variableId` must be the variable of the domain `dominioId`. An `inicial` condition is located in time; `dirichlet`, `flujo` and `mixta`, in a coordinate. The transformed condition adds:

```ts
lugar: { variableId /* new */, variableOriginal, extremo, valor: Expresion /* transformed end */, original: Expresion }
```

`ubicacion` stops being the generic text and becomes, for example, `"x_ad = ell/(D^0.5*t_ref^0.5) (extremo 'hasta' del dominio intervalo-x)"`. `lugar.valor` is the same tree as the end published in `dominios`, which the `dominio` check already certifies. The trace adds a `geometria_condiciones` step "ubicacion de la condicion" for each located condition.

### 13.3 `funciones[].escala`: `D(c) = D* D̂(u)`

`simboloId` is a constant (non-null) parameter of the model and `funcionAdimensional` is a new identity, which cannot coincide with symbols, functions or ids the core generates. The dimension is inferred: `[D*] = [output of D]`, and a contradiction gives `dimension_incompatible`.

When transforming, each call `D(z)`, with its arguments already transformed, is rewritten as `D* D̂(w)`, where `z = s w`:

- `s` is the product of the scales of the maps that appear in the argument and `w` what remains, which must be dimensionless;
- if the argument is not a single monomial or `w` keeps a dimension, nothing is extracted (`s = 1`).

**Published definition:** `D̂(w) = D(s w) / D*`. It is a definition, not a physical hypothesis, and the certificate inverts it before the inverse substitution. Each input of `D` must receive the same `s` in all its calls; otherwise `D̂` would not be well defined and the core answers `rechazado` with `escala_funcion_inconsistente`. If the sign of `D*` is unknown, the constraint `no_nulo` is published. `D*` stays in the coefficient, so the A3 targets use it. For example, `t_ref = x_ref²/D*`, and the normalization can be `completa`.

The formulation adds:

```ts
funcionesAdimensionales: [{ id /* D̂ */, nombre, funcionId /* D */, escalaId /* D* */, entradas: Dimension[], salida: {},
                            dependeDe, argumentos: [{ escala: Expresion /* s, with the resolved scales */, extraida: boolean }],
                            definicion: "Dh(w1) = Dc(c_ref w1) / Dstar" }]
```

**For the reader:** the calls to `D̂` that appear in equations and trace are resolved against `funcionesAdimensionales`, which give their arity, and not against `modelo.funciones`. The trace adds "escala declarada de funcion" per term and "igualdad completa con la escala declarada de las funciones" per equality. `pasos` adds the rule `escala_declarada_de_funciones`.

### 13.4 `Forma.referencias`

Each equality, equation or condition (`ecuacionId` can be a condition's id), is divided by the magnitude of the transformed coefficient of `terminoId` instead of the left one. The rules:

- At most one reference per equality. An id that is both an equation and a condition is rejected as ambiguous.
- The term must exist (`referencia_no_encontrada`) and its coefficient must be a single monomial (`referencia_no_monomial`).
- If it contains a null parameter, the answer is `referencia_nula`. A requested reference is never silently relaxed: all these cases are `rechazado`.
- A target on the reference term comes out `dependiente`, like the time term in v1. The automatic search excludes it from the candidates.

### 13.5 `Forma.prioridadEscalas`

Ids of transformed variables (their scales are taken) or of map constants. They are solved for first, in that order; those not listed follow the v1 order (time, fields, coordinates). An unknown id gives `prioridad_desconocida` and a duplicate is a contract error. Tested example: with the diffusion target, without priority `t_ref = x_ref²/D` comes out with `x_ref` free; with `["x"]`, `x_ref = (D t_ref)^½` comes out with `t_ref` free.

### 13.6 Choice, link and automatic search

- `vinculo.eleccion` adds `referencias` and `prioridadEscalas` when the form carries them; the validity rule of §3 includes them, and the signature changes with them.
- `Forma.transformaciones` is used with `formaId`. If the form already declares them and the request also sends `transformaciones`, it is a contract error: there are not two sources of maps.
- Without `formaId`, `opciones.referencias` and `opciones.prioridadEscalas` (same type) configure the automatic form and appear in `formaBase`. With `formaId` they are a contract error, because the form's own values govern.

**Verification:** 249 checks in `tests/validar_adimensionalizacion.py`, 48 of them new for v2, plus the two new canonical examples.

## 14. The `estudiar` operation (18 October 2026)

It analyses **one** formulation with the physical values the user gives. It replaces the analyses the browser used to fabricate (audit of 18 October). The client only presents.

```ts
type SolicitudEstudio = SolicitudNucleo & { operacion: "estudiar"; estudio: {
  objetivos?: string[];            // terminoIds of the formulation (its objetivosAplicados): it reproduces it exactly
  valores?: { simboloId: string; valor: number; unidad?: string | null }[];  // parameters, constants and free scales
  analisis?: ("estructura" | "sensibilidad" | "valores" | "asintotica" | "escalas" | "simetrias" | "estabilidad" | "continuacion" | "simulacion")[];
  umbralAsintotico?: number;       // (0, 0.5]; by default 0.01
  cajaEstados?: number;            // search for homogeneous states in [-B, B] or [0, B] according to the sign; 10
  estabilidad?: { kMax?: number };
  continuacion?: { parametroId: string; desde: number; hasta: number; unidad?: string; pasosMax?: number };
  simulacion?: { tFinal?: number; muestras?: number; nodos?: number; rtol?: number; atol?: number; verificarMalla?: boolean;
                 fronteras?: { condicionId: string; extremo: "desde" | "hasta" }[];
                 tFinalSI?: number;        // seconds; excludes tFinal. Final τ = the published inverse of the time map
                 periodica?: boolean };    // periodic boundary in the active coordinate; without end conditions
} };
```

**Formulation.**

- Without `formaId`, the automatic form is used with the targets `estudio.objetivos`.
- With `formaId`, the form's targets (prefix `base:`) plus those of `estudio.objetivos`.
- For equal targets and presentation, the result is identical to that of `adimensionalizar`; the suite checks it with the 8 formulations of §3.

**Values.**

- They are converted to SI with pint and their dimension is checked to be the symbol's (`dimension_incompatible`).
- A value without a unit uses the symbol's declared unit.
- A sign contradicting the declared one is `signo_contradictorio`, and a value for a variable is `valor_no_admitido`. Both are rejections.
- The determined scales are evaluated with their expressions; whatever is missing is listed in `faltan`, naming the parameters behind it.

**Response.**

```ts
{ formato: "adimensionalizacion.resultado", version: 1, operacion: "estudiar", estado, nucleo, diagnosticos,
  vinculo: { documentoId, modeloId, modeloRevision, formaId, eleccion, estudio /* exact echo */, firma },
  dimensional, terminos, formaBase, formulacion /* body of transformar */, estudio: { [analysis]: { estado, motivo, … } } }
```

Each analysis publishes `estado ∈ {calculado, requiere_datos, no_aplicable, no_soportado, no_convergente}` and `motivo`, which describes the method used:

| Analysis | Method and output |
|---|---|
| `estructura` | Classification of each term by its operators in the Cartesian canonical form: accumulation, diffusion, convection, reaction (`lineal`), source; in conditions, flux, value or datum. Each group is read as the quotient of its term over the reference term (global factor) and, as `equivalentes`, over the other terms with coefficient ±1. `nombreClasico` appears only if the pair of types determines it (Fourier, Péclet, Damköhler I/II, Biot…). `normalizados` lists the terms fixed by the targets. |
| `sensibilidad` | Rational exponent of each symbol in each monomial group: d ln G / d ln p. It separates the free scales. |
| `valores` | Scales, groups and coefficients in SI; `dispersionLog10` per equation. |
| `asintotica` | Kruskal envelope of \|coef\| δ^(−order), in space and in time. It gives the dominant and negligible terms (relative threshold), the `reducida` equation, the singular perturbation (`condicionesPerdidas`, `espesor`, interior balance) and the `ubicacion` of the layer (only if the interior balance is linear with constant coefficients). Also the initial layer. |
| `escalas` | Exact linearization (complex step) at a reference state: the stable homogeneous one, if it exists. It publishes effective diffusivity and velocity, times, internal lengths, nodes (cell Péclet ≤ 2 and 10 nodes per internal length), maximum explicit step per mechanism and the stiffness ratio of the semi-discrete operator. |
| `simetrias` | Dilations (rational null space of each monomial's weights), translations and reductions: similarity η = ξ τ^(−q), u = τ^p F(η) and travelling wave z = ξ − c τ. The ODE is published only if every monomial ends up with the same power of τ; otherwise, `no_demostrada`. |
| `estabilidad` | Homogeneous states by a finite search in the box (published). For each one: Jacobian, eigenvalues and, per coordinate, σ(k) = eigenvalues of J + Σ (ik)ⁿ Cₙ, with class `estable` / `turing` / `onda` / `inestable_homogenea` / `oscilatoria_homogenea`, critical k, band and admissible Neumann modes. A continuum of equilibria is declared (`continuo`, `notaContinuo`) and a representative is analysed. |
| `continuacion` | Arc length of F(u; p) = 0 from the states at the given value. Folds refined by Newton on F = 0, F_u v = 0; Hopf by the crossing of a complex pair, with its frequency. Branches with stability per point. |
| `simulacion` | Method of lines in one coordinate (or an ODE): second-order centred differences, located conditions (v2 or `simulacion.fronteras`) solved at each evaluation (Dirichlet outside the state; flux and Robin with a ghost node) and BDF integration with the Jacobian's sparsity. It publishes `tiempos`, `xi` and `campos` (dimensionless); `fisico` (SI restitution with the maps); `verificacionMalla` (difference with 2N − 1 nodes); and `codigoPython`, a standalone script with the same discretization. With `periodica` it uses N nodes in [a, b) (b is identified with a), rejects declared end conditions, verifies with 2N nodes and publishes `metodo.frontera = "periodica"`. With `tFinalSI` the final time is given in seconds and the core converts it with the inverse of the time map (if time is not transformed, τ = t). It also publishes `resultados`: the same trajectory in the common format ([docs/contracts/results-format.md](results-format.md)), with the dimensionless formulation and, if the scales have values, the original variables in SI. |

**Declared limits.**

- Declared functions without a definition are not evaluated numerically.
- Simulation in one coordinate, with derivatives of order ≤ 2 and without mixed time-space derivatives. (The original text said the periodic boundary was not supported; `periodica`, described in the table above, was added later.)
- The dispersion is calculated for an infinite domain, plus the Neumann modes of the finite one.
- The search for states is finite.
- None of this certifies the physical validity of the model.

**Extended functions.** tan, tanh, sinh, cosh, atan and erf are accepted throughout the core:

- dimensionless argument;
- derivatives with the chain rule (erf stays unexpanded);
- numerical evaluation.

The text of `equivalencia.alcance` was updated.

**Fix of 18 October.** An internal sum that is already dimensionless (1 + K c) no longer gives up scales: c_ref (K u + 1/c_ref) left a dimensional kernel. In addition, a target on a dimensional coefficient stays `pendiente` (`coeficiente_dimensional`). Before, 38 formulations of three catalog examples came out "no demostradas"; now all of them are proven.

**Verification.**

- `tests/validar_estudio_adimensionalizacion.py`: 55 checks against analytical solutions.
- Canonical examples `estudio-calor`, `estudio-brusselator` and `estudio-pliegues`, checked by the core's suite.
- `frontend/verificar_estudio_adimensionalizacion.mjs`: 66 checks of the reader and the presentation. A random test of 2000 mutations on v2 requests produced no internal errors and no failed results with equations.
