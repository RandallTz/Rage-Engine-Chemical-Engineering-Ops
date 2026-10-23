# Common results format and charting engine

18 October 2026. Step 3 of [ARCHITECTURE.md](../../ARCHITECTURE.md) §10. Every calculation engine publishes its results in this format, and the single charting engine draws them without knowing where they come from.

## 1. The format (`rage.resultados`, v0)

```ts
{ formato: "rage.resultados", version: 0, id, nombre, modeloId | null,
  estado: "resuelto" | "parcial" | "fallido",
  procedencia: { motor, metodo | null, firma | null, mensaje?, pasos?, rechazos? },
  ejes:   [{ id, nombre, rol: "tiempo" | "coordenada" | "parametro" | "otro", unidadSI, dimension, valores }],
  series: [{ id, nombre, unidadSI, dimension, magnitudes, ejes: [ejeId…], valores,
             propietarioId?, componenteId?, faseId? }],
  eventos: [{ codigo, ejeId, valor, descripcion, propietarioId? }],
  verificaciones: [{ id, valor, tolerancia, descripcion }] }
```

Field names are part of the published JSON format and stay in Spanish ([docs/repository-cleanup/README.md](../repository-cleanup/README.md) §7, D3).

- **Axis (`eje`):** any independent variable: time, a coordinate, the parameter of a continuation, a wave number…
- **Series:** depends on 0, 1 or 2 axes. Its `valores` have the shape of those axes (the first one is the outer index), and `null` means "not defined", never an invented number.
- **Units:** SI, with their exact dimension, given by the units service ([docs/contracts/units-service.md](units-service.md)).
- **No bias:** no field knows about tanks, columns or reactors. The physical origin of a series is stated by `propietarioId`, `componenteId` and `faseId`, as data.

**Code**

- Python: `core/resultados/` (`formato.py`: construction and strict reader; `adaptadores.py`).
- TypeScript: `frontend/motores/resultados/` (`contrato.ts`, `lector.ts`, `desdeMotor.ts`).

**Who publishes it today**

| Engine | How |
|---|---|
| Simulation of the nondimensionalization core | Directly, in `estudio.simulacion.resultados`: the dimensionless formulation (τ, ξ, unit 1) and the original variables in SI with their unit |
| Thermodynamic assembly v2 | Adapter `core.resultados.desde_ensamblaje_v2`, without loss |
| The engine's TS solver | Adapter `resultadosDesdeMotor`, without loss; it asks the units service for the dimensions |
| Common compiler (`POST /modelo/resolver`) | Directly; the Engine's Resolver reads it ([docs/engine/vertical-slice.md](../engine/vertical-slice.md)) |

## 2. Charting engine (`frontend/componentes/graficas/`)

- **`datos.ts` (pure):** `datosGrafica(conjunto, especificacion)` produces curves, and `especificacionesPorOmision(conjunto)` groups by dimension and axes. The specification is `{x: {eje} | {serie}, y: [series], fijar?: {eje, indice}}`. Generic rules:
  - one dimension per y axis;
  - a series of two axes needs one of them fixed (a profile at an instant, or the evolution at a point);
  - one series against another works as a phase diagram if they share an axis.
- **`Grafica.tsx`:** the project's only SVG renderer. Nondimensionalization's simulation and stability views use it.
- **`GraficaResultados.tsx`:** joins the two pieces above. Axis titles come from the published quantity and unit, for example "densidad (kg/m^3)".

The old `GraficoXY.tsx` of nondimensionalization is archived in `docs/history/archive/nondimensionalization-2026-10-18/`. The existing Engine dashboard (`frontend/app/motor/TableroMotor.tsx`) retains its renderer until the common renderer migration. For evaluated-series results, its initial charts now group the actually published variable IDs by group/unit metadata; they do not assume `U`/`T` or another physical family exists. Saved chart specifications remain user preferences. Model source-history navigation preserves those preferences while invalidating scientific execution when required.

## 3. Verification

- `python tests/validar_resultados.py` (34 checks):
  - the four v2 assemblies keep times, values, metadata, events and residuals;
  - the core simulation publishes identical fields and restitution;
  - six reader rejections.
- `node verificar_resultados_graficas.mjs` (175 checks):
  - the TS solver's 8 results, the assembly's 4 and the core's one pass the TS and Python readers;
  - they are drawn with the same code, and each curve is exactly the series;
  - the generic rules hold.
