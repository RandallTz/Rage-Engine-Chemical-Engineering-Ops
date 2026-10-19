# Contrato del modelo común · v0

18 de octubre de 2026. Es la pieza base de [ARQUITECTURA_MOTOR.md](../ARQUITECTURA_MOTOR.md) §4: el único idioma que hablan todos los motores.

La v0 es **una representación, no un motor nuevo**: define el documento, su lector estricto y las relaciones estructurales siempre presentes. Valida que los tres formatos existentes caben en ella sin pérdida. Ninguna pantalla ni ningún solver la consumen todavía.

- **Python, canónico:** `core/modelo/` (`lector.py`, `relaciones.py`, `adaptadores.py`).
- **TypeScript:** `frontend/motores/modelo/` (tipos, lector y adaptador desde hojas del motor).
- **Pruebas:** `tests/validar_modelo_comun.py` y `frontend/verificar_modelo_comun.mjs`.
- **Ejemplos:** `docs/ejemplos/modelo-comun/`.

## 1. Documento

```ts
type Modelo = {
  formato: "rage.modelo"; version: 0;
  id: string; nombre: string;
  componentes: Componente[];                 // identidad química; sin propiedades
  termodinamica: { paquetes: Paquete[] };    // paquetes configurados por id local
  volumenes: Volumen[];                      // regiones con cantidades conservadas
  corrientes: Corriente[];                   // transporte de materia (y su entalpía)
  intercambios: Intercambio[];               // calor entre volúmenes o con el exterior
  datos: Record<string, Dato>;               // todo valor físico, con unidad y origen
  matematico: ModeloMatematico | null;       // ecuaciones explícitas (árbol tipado)
  estudio: Estudio | null;                   // qué cálculo se pide y con qué ajustes
  motores: Record<string, unknown>;          // configuración propia de cada motor, por espacio
  procedencia: Procedencia;                  // de dónde viene este modelo
};
```

### Piezas físicas

- **`Componente`**: `{id: entero, nombre, simbolo, identidadQuimica?: {cas?, proveedorId?}, masaMolar?}`. Igual que en el motor.
- **`Paquete`**: `{id, modelo: {id, version}, datosPuros?}`. `modelo` nombra un paquete publicado por `/motor/termodinamica/capacidades`; `datosPuros` lleva las sustituciones admitidas (v_L, Cp ideal, Psat).
- **`Volumen`**:
  - `id`, `componenteIds`;
  - `balances: {materia, energia, momento}`;
  - `supuestos: {materia: FormulacionMateria, energia: FormulacionEnergia | null}`: los indicadores de reducción del motor, que son la entrada del motor de supuestos;
  - `frontera`: `rigida`, `presion_prescrita`, `sin_relacion` o `malla_1d`;
  - `inicial`: cantidades y energía iniciales por id de dato, o `{tipo: "por_datos"}` cuando las iniciales son datos de campo;
  - **`termodinamica: Cierre`, obligatorio** (§2).
- **`Corriente`**:
  - forma de la revisión 2 del ensamblaje: `id`, `desde`, `hasta` (null = exterior), `componenteIds`, `mecanismo`, `materia`, `estadoExterior?`, `extraccion?`;
  - más `constante?` (puertos del motor TS), base `volumetrica` (dV/dt = Q) y `datoIds` por componente.
- **`Intercambio`**: `{id, desde, hasta, ley: {tipo: "impuesto", potenciaId} | {tipo: "conductancia", conductanciaId, temperaturaExteriorId?}, temperaturaFronteraId?}`.
- **`Dato`**: `{magnitud, funcion: "inicial" | "frontera" | "geometria" | "estudio" | "parametro", declaracion: {texto, unidad}, origen: {propietarioId, ruta}}`. `texto` admite un número o una expresión del motor; la unidad se aplica al resultado.

### Lo demás

- **`ModeloMatematico`**: exactamente el `modelo` del documento v2 de la adimensionalización: `{id, revision, simbolos, funciones, ecuaciones, dominios, condiciones}`, con el árbol `Expresion` de `frontend/app/adimensionalizacion/contrato.ts`. Se valida con `core.adimensionalizacion.lector.leer_modelo(version=2)`. Es `null` cuando las ecuaciones las genera un motor a partir de la estructura (caso del ensamblaje, §3).
- **`Estudio`**:
  - temporal: `tipo: "temporal"`, `tiempoId`, `metodoSolicitado`, `muestras`, `rtol`, `atol: {cantidad, energia?}`;
  - opcionales: `espacial?: {celdas, frontera}` y `cierreMasico?`.
- **`motores`**: configuración de cada motor bajo su nombre. Hoy solo `adimensionalizacion: {formas, activaId, exploracion?}`. Un motor nunca escribe fuera de su espacio.
- **`restricciones?`** (opcional, 18 de octubre de 2026): `[{simboloId, tipo: "no_negativo"}]` sobre variables de campo de `matematico`. El cálculo se detiene en el instante en que una lo abandonaría (código `agotamiento`); nunca se recorta. Sin restricción declarada, la ecuación sigue: el dominio es del modelo, no una regla escondida del solver.
- **Valores de `matematico`**: cada parámetro o constante del árbol toma su valor de `datos["matematico.<id>"]` (`funcion: "parametro"`, `origen: {propietarioId: "matematico", ruta: "matematico.simbolos.<id>"}`), en cualquier unidad compatible con la dimensión del símbolo. Antes viajaban en `procedencia.valoresMatematico`, que ya no existe.
- **Motor de balances** (campos opcionales, 18 de octubre de 2026; ver [MOTOR_BALANCES.md](MOTOR_BALANCES.md)):
  - volumen: `terminos` (`"generacion.<id>"`, `"consumo.<id>"`, `"resto.<id>"`, `"calor"`, `"trabajo_viscoso"`, `"fuerzas"`, `"fuente"` → dato);
  - volumen: `volumenDatoId`;
  - volumen: `inicial.energia`, opcional sin balance de energía;
  - cierre supuesto `u_lineal`: `parametros: {cId, uRefId, TRefId, TMinId, TMaxId, rhoId?}`;
  - corriente: `materia.modo = "total_y_composicion"` con `caudalId` y `fracciones`;
  - `restricciones`: además de `{simboloId, tipo}`, la forma `{expresion, tipo: "no_negativo", descripcion}`, una expresión de las variables que debe mantenerse ≥ 0 (dominio de validez de un supuesto).
  - Un modelo con volúmenes de estado supuesto y `matematico: null` lo resuelve `POST /modelo/resolver` generando antes sus ecuaciones con el motor de balances.
- **`observables?`** y **`verificaciones?`** (opcionales, sobre las variables de `matematico`):
  - `observables: [{id, nombre, unidadSI, expresion}]` se publican como series `observable.<id>`;
  - `verificaciones: [{id, descripcion, expresion, escala, tolerancia?}]` se publican en `verificaciones` del resultado, con valor max|expresion| / max|escala| sobre las muestras;
  - el motor de balances genera ambas: temperatura, caudales y entalpías del donante; cierres de presupuesto por estado y globales.
- **`Procedencia`**: `{tipo: "documento_adimensional" | "ensamblaje_v2" | "hoja_motor_materia" | "nuevo", ...}` con los identificadores del origen (`solicitudId`, `hojaId`, `documentoId`), su `version` y lo que no es física pero debe conservarse (`derivacion`, pasos del recorrido).

## 2. La termodinámica siempre presente

Todo volumen declara su cierre. Que no lo declare es un **error de lectura**, no un valor por omisión:

```ts
type Cierre =
  | { tipo: "equilibrio"; paqueteId: string; politica: PoliticaEstado }
  | { tipo: "supuesto"; supuesto: "fase_no_evaluada" | "u_lineal"; motivo: string };
```

- **`equilibrio`**: el estado sale del paquete en cada evaluación, mediante el cierre UV (frontera rígida) o PH (presión prescrita). Las fases se obtienen como resultado, y la que no está presente tiene cantidad cero con las mismas ecuaciones (ver la arquitectura, §3).
- **`supuesto`**: el motor que generó el modelo no evalúa el estado (por ejemplo, el solver de materia del navegador) o usa una relación manual. Queda escrito con su motivo y aparece como relación de familia `estado` marcada `supuesta`, para que la carencia se vea y no se olvide.

`relaciones(modelo)` (`core/modelo/relaciones.py`) genera la lista estructural de relaciones de un modelo físico, siempre la misma para la misma estructura:

| Para | Relaciones (id · familia) |
|---|---|
| volumen con `equilibrio` | `estado.V.energia` · estado (cierre UV o PH), `estado.V.volumen` · estado, `equilibrio.V` · equilibrio; con presión prescrita, además `estado.V.U` · estado y `mecanica.V.trabajo` · mecanica |
| volumen con `supuesto` | `estado.V.supuesto` · estado (supuesta) |
| corriente S | `transferencia.S.composicion`, `transferencia.S.entalpia`, `transferencia.S.caudal` · transferencia |
| intercambio por conductancia Q | `transferencia.calor.Q` · transferencia |
| volumen V, componente i | `materia.V.i` · materia; `energia.V` · energia si el balance de energía está activo |
| red | `global.materia.i` y `global.energia` · verificación |

Para los ensamblajes v2, esta lista coincide uno a uno (id, familia, propietario y orden) con las ecuaciones que publica `/motor/ensamblajes/validar` en todos sus ejemplos. Es la comprobación de que el modelo común describe lo mismo que el backend resuelve.

## 3. Los tres casos de partida

| Caso | Ida | Vuelta | Criterio de «sin pérdida» |
|---|---|---|---|
| Documento de adimensionalización (v1 o v2) | `desde_documento_adimensional` | `a_documento_adimensional` | El documento vuelve idéntico; `matematico` lleva el modelo y `motores.adimensionalizacion`, las formas |
| Solicitud de ensamblaje v2 del motor | `desde_ensamblaje_v2` | `a_ensamblaje_v2` | La solicitud vuelve idéntica, y `relaciones()` coincide con las ecuaciones del backend |
| Hoja de materia del motor (solver TS) | `modeloDesdeHojaMotor` (TS) | `hojaDesdeModelo` (TS) | Formulación activa, componentes y configuración vuelven idénticos. `matematico` contiene las ecuaciones que ejecuta el motor, las mismas que importa la adimensionalización, y el lector Python acepta el modelo |

### Evidencia (18 de octubre de 2026)

- `python tests/validar_modelo_comun.py`: **102 comprobaciones**.
  - Los 20 documentos de ejemplo de la adimensionalización vuelven idénticos.
  - Las 6 solicitudes v2 de ejemplo vuelven idénticas, y sus relaciones coinciden con el ejemplo publicado y con `validar_v2` en vivo.
  - En el calentamiento etanol-agua el vapor aparece y el líquido desaparece con el mismo conjunto de relaciones.
  - Diez rechazos, entre ellos el de un volumen sin cierre termodinámico.
- `node verificar_modelo_comun.mjs` (desde `frontend/`): **117 comprobaciones**.
  - Las 9 hojas de materia del motor, una de ellas incompleta: ida y vuelta exacta, aceptadas por los lectores TS y Python, `matematico` igual a lo que importa la adimensionalización y estado declarado como supuesto.
  - Las 17 solicitudes v2 reales de las hojas multifásicas, de N componentes, UNIFAC y de demostración: ida y vuelta exacta y relaciones iguales a las del backend en vivo.
- Ejemplos: `docs/ejemplos/modelo-comun/`. Los de Python se regeneran con `--regenerar`; el de la hoja lo escribe la verificación de TypeScript.

## 4. Reglas

- Lectura estricta: claves desconocidas, ids repetidos y referencias inexistentes son errores con su ruta (`volumenes[0].termodinamica.paqueteId: referencia inexistente`).
- Unidades: cada `Dato` lleva la suya. El modelo no convierte; convierte el motor de unidades.
- El modelo es **datos**. No contiene funciones, código ni LaTeX como fuente de verdad; las relaciones generadas llevan una descripción legible, no una fórmula que haya que interpretar.
- Versión: un cambio incompatible sube `version`. Un campo nuevo y opcional se añade sin subirla y se documenta aquí.

## 5. Fuera de la v0

- Ecuaciones explícitas (árbol) para los ensamblajes con termodinámica.
- Supuestos como operaciones registradas una a una: hoy viajan como el estado de los indicadores del motor.
- Constitutivas y momento.
- Consumo del modelo por los solvers o la interfaz.

Todo eso corresponde a los pasos 2 a 5 de la arquitectura.
