# Servicio único de unidades

18 de octubre de 2026. Paso 3 de [ARQUITECTURA_MOTOR.md](../ARQUITECTURA_MOTOR.md) §10. Es el único lugar del proyecto que interpreta una unidad.

- **Código:** `core/unidades/`.
- **HTTP:**
  - `GET /unidades/capacidades`: el catálogo de magnitudes;
  - `POST /unidades/interpretar` con `{unidades: [texto…]}`, hasta 500 unidades.
- **Pruebas:** `tests/validar_unidades.py` (264) y `frontend/verificar_unidades_motor.mjs` (235).

## 1. Qué publica

`interpretar(unidad)` devuelve:

| Campo | Contenido |
|---|---|
| `dimension` | Exponentes exactos (fracciones) sobre M, L, T, N, Theta, I, J |
| `factor`, `desplazamiento` | valor_SI = factor · valor + desplazamiento. El desplazamiento solo es distinto de cero en escalas afines (°C, °F); `degC/s` es una tasa (= K/s) sin desplazamiento |
| `unidadSI` | Texto canónico: W, J, Pa, N; J/mol, J/(kg*K), W/K; o las bases (kg/s, mol/m^3, m^2/s) |
| `magnitudes` | Los nombres del catálogo con esa dimensión |

También expone `a_SI`, `desde_SI`, `compatibles` y `magnitudes_de`.

La interpretación la hace pint. El servicio solo normaliza las grafías del proyecto:

- potencias compactas: `m3`, `cm2`, `s-1`;
- superíndices `³` y `²`, y el punto medio `·`;
- `°C` y `°F`;
- unidad adimensional escrita como `1`, `-`, `adimensional` o texto vacío.

## 2. Sin sesgo hacia ninguna operación

- Las magnitudes se definen **solo por su dimensión**: masa, caudal molar, capacidad calorífica específica, conductancia térmica, tasa volumétrica… Ninguna está atada a un equipo o a un tipo de operación.
- **No hay listas cerradas** de unidades por magnitud: cualquier unidad con la dimensión correcta vale (psi, BTU/lb, gal/min, cP, Btu/(h·ft·°R)…).
- Varias magnitudes pueden compartir dimensión: la presión y la densidad de energía, por ejemplo. Por eso el nombre de una magnitud nunca se deduce de una unidad; solo se ofrecen candidatos.

## 3. Equivalencia con los sistemas que sustituye

| Sistema | Dónde | Resultado |
|---|---|---|
| Tabla del motor (TS) | `frontend/app/motor/unidadesMotor.ts` | Las 47 unidades de sus 18 magnitudes dan la misma conversión (1e-12) y la misma dimensión |
| Tabla del backend del motor | `backend/motor_ensamblaje.UNIDADES`, más las ampliaciones de la revisión 2 | Mismo factor, mismo desplazamiento, misma dimensión y misma unidad SI |
| Adimensionalización | `core/adimensionalizacion/dimensional.interpretar_unidad` | Misma dimensión y mismo factor en una muestra de 36 unidades |
| Laboratorio | `core/dimensiones._cantidad` | Mismo factor |

Los cuatro siguen existiendo: el motor y el laboratorio no se modifican sin encargo. La equivalencia comprobada permite sustituirlos por el servicio cuando se migre cada motor (paso 5).
