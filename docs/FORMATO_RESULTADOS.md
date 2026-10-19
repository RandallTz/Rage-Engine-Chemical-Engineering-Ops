# Formato común de resultados y motor de gráficas

18 de octubre de 2026. Paso 3 de [ARQUITECTURA_MOTOR.md](../ARQUITECTURA_MOTOR.md) §10. Todo motor de cálculo publica sus resultados en este formato, y el único motor de gráficas los dibuja sin saber de dónde vienen.

## 1. El formato (`rage.resultados`, v0)

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

- **Eje:** una variable independiente cualquiera: tiempo, coordenada, el parámetro de una continuación, un número de onda…
- **Serie:** depende de 0, 1 o 2 ejes. Sus `valores` tienen la forma de esos ejes (el primero es el índice exterior), y `null` significa «no definido», nunca un número inventado.
- **Unidades:** SI, con su dimensión exacta, dadas por el servicio de unidades ([SERVICIO_UNIDADES.md](SERVICIO_UNIDADES.md)).
- **Sin sesgo:** ningún campo sabe de tanques, columnas ni reactores. El origen físico de una serie lo dicen `propietarioId`, `componenteId` y `faseId`, como datos.

**Código**

- Python: `core/resultados/` (`formato.py`: construcción y lector estricto; `adaptadores.py`).
- TypeScript: `frontend/motores/resultados/` (`contrato.ts`, `lector.ts`, `desdeMotor.ts`).

**Quién lo publica hoy**

| Motor | Cómo |
|---|---|
| Simulación del núcleo de adimensionalización | Directamente, en `estudio.simulacion.resultados`: la formulación adimensional (τ, ξ, unidad 1) y las variables originales en SI con su unidad |
| Ensamblaje termodinámico v2 | Adaptador `core.resultados.desde_ensamblaje_v2`, sin pérdida |
| Solver TS del motor | Adaptador `resultadosDesdeMotor`, sin pérdida; las dimensiones las pide al servicio de unidades |

## 2. Motor de gráficas (`frontend/componentes/graficas/`)

- **`datos.ts` (puro):** `datosGrafica(conjunto, especificacion)` produce curvas, y `especificacionesPorOmision(conjunto)` agrupa por dimensión y ejes. La especificación es `{x: {eje} | {serie}, y: [series], fijar?: {eje, indice}}`. Reglas genéricas:
  - una sola dimensión por eje de ordenadas;
  - una serie de dos ejes necesita fijar uno de ellos (perfil en un instante o evolución en un punto);
  - una serie frente a otra vale como diagrama de fases si comparten eje.
- **`Grafica.tsx`:** el único renderizador SVG del proyecto. Lo usan la simulación y la estabilidad de la adimensionalización.
- **`GraficaResultados.tsx`:** une las dos piezas anteriores. Los títulos de los ejes salen de la magnitud y la unidad publicadas, por ejemplo «densidad (kg/m^3)».

El antiguo `GraficoXY.tsx` de la adimensionalización está archivado en `docs/archivo/adimensionalizacion-2026-10-18/`. El tablero del motor (`frontend/app/motor/TableroMotor.tsx`) todavía no se toca: se migrará con el motor.

## 3. Verificación

- `python tests/validar_resultados.py` (34 comprobaciones):
  - los cuatro ensamblajes v2 conservan tiempos, valores, metadatos, eventos y residuos;
  - la simulación del núcleo publica campos y restitución idénticos;
  - seis rechazos del lector.
- `node verificar_resultados_graficas.mjs` (175 comprobaciones):
  - los 8 resultados del solver TS, los 4 del ensamblaje y el del núcleo pasan los lectores TS y Python;
  - se grafican con el mismo código, y cada curva es exactamente la serie;
  - las reglas genéricas se cumplen.
