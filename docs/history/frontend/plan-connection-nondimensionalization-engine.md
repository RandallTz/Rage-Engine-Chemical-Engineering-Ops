# Plan de conexión: adimensionalización ↔ motor multifísico

Claude, 18 de octubre de 2026. Propuesta para el usuario y para Codex. **Restricción del encargo: no se modifica el motor (`/motor`, su backend ni sus contratos); solo la herramienta de adimensionalización.** Sin commit ni push.

## 1. Qué es cada pieza hoy

**El motor (`/motor`) tiene dos mitades independientes:**

1. **Hojas de ecuaciones (TypeScript, en el navegador).**
   - El usuario deriva un balance de materia con operaciones sobre una `FormulacionMateria`: formas diferencial, integral o total; indicadores como `sinDifusion`, `sinConveccion` o `estacionario`; puertos y fuentes. Los datos van en `ConfiguracionMotor.datos`: expresiones con unidad por campo (`difusion_<i>`, `velocidad`, `generacion_<i>`, `inicial_<i>`…).
   - `compilarMotor` las resuelve como EDO o como EDP 1D cartesiana: volúmenes finitos, convección upwind y RK45 explícito, con paso limitado por 0.4 Δx/|v| y 0.2 Δx²/D, hasta 160 celdas.
   - Se guardan en `localStorage["rage.motor.hojas.v1"]`.
2. **Ensamblaje termodinámico (Python, `/motor/ensamblajes/*`).**
   - Volúmenes de control con materia y energía, cierres de estado (IAPWS-95, ideal, NRTL, UNIFAC), fases y eventos.
   - Es un sistema DAE de parámetros concentrados resuelto con RK45 explícito.
   - El contrato publica `variables` (con papel y unidad SI) y `ecuaciones` (con familia y LaTeX), pero no un árbol de expresiones.

**La adimensionalización** recibe un modelo tipado (árbol de expresiones con dimensiones) y produce formulaciones exactas y certificadas. Con la operación `estudiar` añade análisis numéricos reales: balanza dominante, malla, rigidez, estabilidad, continuación, simetrías y simulación.

**Conclusión.** El punto de encuentro no son las ecuaciones en LaTeX. Son dos cosas, y ambas se pueden leer sin tocar el motor:

- **la formulación estructurada y los datos de una hoja**, que la adimensionalización puede traducir a su propio árbol;
- **los contratos públicos del ensamblaje** (solicitud y respuesta), cuyas magnitudes dan las escalas de tiempo de cada volumen.

## 2. Qué puede aportar la adimensionalización al motor

| Aporte | Para qué sirve en el motor | Base ya implementada |
|---|---|---|
| Formulación adimensional y grupos de una hoja | Leer qué mecanismo domina (Fo, Pe, Da) con los datos reales | `adimensionalizar`, `estudio.estructura`, `valores` |
| Diagnóstico de malla | El motor usa como máximo 160 celdas: saber antes de resolver si basta para el Péclet de celda y las capas límite | `estudio.escalas` (nodos por Péclet y por longitud interna), `asintotica` |
| Diagnóstico de rigidez | El motor integra con RK45 explícito: estimar cuántos pasos exigirá y si un integrador implícito (F3 del roadmap) es necesario | `estudio.escalas.rigidez` y paso explícito máximo |
| Estados estacionarios y su estabilidad | F3 pide «estado estacionario del mismo residuo; detectar estados no únicos» | `estudio.estabilidad`, `continuacion` |
| Contraste independiente de una solución | F9 pide «contrastes independientes»: resolver la misma hoja con otro método (MOL + BDF) y comparar | `estudio.simulacion` |
| Restitución de unidades | Leer resultados del motor en variables adimensionales y viceversa | `transformaciones` (directa/inversa) |

## 3. Fases propuestas

Cada fase entrega contrato, pruebas y ejemplos, como el resto del proyecto. Ninguna modifica el motor.

### Fase M1 — Importar una hoja de materia del motor (solo lectura)

> **Hecha el 18 de octubre de 2026.** Adaptador `app/adimensionalizacion/desdeMotor.ts` (importa en solo lectura funciones puras del motor), pestaña «Del motor» en el cuaderno, comparación con el resultado guardado (`ComparacionMotor.tsx`, `diferenciaMotor.ts`) y opciones `simulacion.periodica` y `simulacion.tFinalSI` en el núcleo (contrato §14). Verificación: `node verificar_importacion_motor.mjs` (117 comprobaciones; evidencias en `docs/ejemplos/importacion-motor-evidencias.json`). Las ocho hojas de prueba se importan, todas sus formulaciones quedan certificadas y la simulación del núcleo coincide con el motor y con la solución analítica (hojas 01–05 a 1e-15; 06 a 6e-7; 08 a 5e-5). En la 07 (convección pura) el núcleo queda a 9e-5 de la analítica y el motor, con *upwind* de primer orden, a 8e-3: la diferencia es del motor, no de la traducción.
>
> Diferencias con lo previsto abajo: la periodicidad sí se admite (opción de simulación, no condición del documento); la dimensión de cada literal la asigna el adaptador a partir de la unidad del dato y el núcleo la vuelve a comprobar; no se traducen todavía `step`, las reglas de estado, la densidad media variable ni los ensamblajes (fase M3).

**Qué.** Sustituye al importador falso. La adimensionalización lee `rage.motor.hojas.v1` (misma página y origen, solo lectura) y convierte la formulación activa más sus datos en un `Documento` v2 con sus valores:

| Hoja del motor | Documento de adimensionalización |
|---|---|
| Componente i, forma diferencial 1D | Campo ρ_i(t, x) |
| Acumulación ∂ρ_i/∂t | Lado izquierdo |
| Convección −∂(v ρ_i)/∂x (si no `sinConveccion`) | Término con el dato `velocidad` |
| Difusión: Fick laplaciano D_i ∇²ρ_i, Fick o flujo j_i | Término con el dato `difusion_<i>` |
| Generación / consumo γ_i, χ_i | Términos con sus expresiones |
| Forma total: dm_i/dt = Σ entradas − Σ salidas − Φ + G − C | EDO por componente |
| Dominio `inicio`, `fin`, tiempo `tiempo` | `dominios` |
| `inicial_<i>` | Condición inicial |
| Frontera `valores` / `sin_flujo` | Condiciones de Dirichlet / flujo nulo ubicadas en cada extremo (v2) |
| Frontera `periodica` | Fuera de alcance: se declara, no se fuerza |
| Expresiones de datos (`expresionesMotor`: número, variable, operación) | Árbol de adimensionalización. Cada constante numérica de una expresión pasa a ser un parámetro con su valor, y su dimensión la infiere el núcleo: un «2·m_A» en kg/s implica 2 s⁻¹. `step` no tiene equivalente: se declara fuera de alcance |
| Unidades de `unidadesMotor.ts` | Unidades interpretadas por pint en el núcleo |

**Cómo, sin tocar el motor:**

- Un adaptador nuevo en la ruta de adimensionalización (`puenteMotor.ts`, reescrito) **importa en modo de solo lectura** las funciones puras del motor que ya construyen los términos, para no duplicar su lógica: `terminosTotalesMateria`, `camposMotor`, `analizarExpresion`.
- Si el usuario prefiere ni siquiera importar módulos del motor, la alternativa es leer solo el JSON guardado y replicar la tabla de arriba. Es más frágil ante cambios del motor.

**Aceptación:**

- Las ocho hojas de `docs/engine/matter-test-sheets.md` se importan; las que el motor resuelve dan formulaciones certificadas.
- Para cada hoja 1D, la simulación del estudio (MOL + BDF) coincide con el `ResultadoMotor` guardado dentro de la tolerancia conjunta de ambos métodos. Es el contraste independiente de F9.
- Lo que no se puede traducir (periodicidad, `step`, forma integral) se declara campo a campo, sin aproximaciones.

### Fase M2 — Preacondicionamiento como diagnóstico (sin cambiar el motor)

**Qué.** Para una hoja importada, la adimensionalización informa:

- el Péclet de celda con las celdas que la hoja tiene configuradas, en sus unidades;
- el número de pasos que exigirían los límites del motor (0.4 Δx/|v| y 0.2 Δx²/D) en el horizonte declarado;
- el cociente de rigidez y la recomendación de integrador.

**Contrato.** Ampliar `estudio.escalas` con un bloque opcional `discretizacionMotor`: `{celdas, dx, pasosEstimados, limitante, pecletCelda}`. Lo calcula el núcleo con los datos de la hoja.

**Aceptación.**

- En las hojas de prueba, `pasosEstimados` acota los pasos reales del `ResultadoMotor` guardado: mismo orden de magnitud, documentando la diferencia por el control de error de RK45.
- Una hoja con Pe de celda > 2 se señala, y al refinar la malla en el motor el aviso desaparece.

### Fase M3 — Volúmenes de control del ensamblaje termodinámico

**Qué.** A partir de una `SolicitudEnsamblajeV2` guardada en una hoja (`ResultadoMotor.ensamblajeV2`), construir el modelo concentrado por volumen:

- materia: dn_i/dt = Σ s_j F_j x_ij;
- energía: dH/dt = Σ s_j F_j h_j + Q + V dP/dt;
- los cierres termodinámicos como funciones declaradas (opacas; el núcleo no las desarrolla).

Con la respuesta (series en SI) se evalúan los grupos **a lo largo de la trayectoria**:

- tiempo de residencia n/F;
- tiempo térmico H/Q;
- números de Damköhler cuando haya reacción (F5);
- cociente entre la escala más rápida y la más lenta.

**Límite honesto.** Las propiedades h(T,P,x) no se pueden evaluar sin el servidor del motor. La adimensionalización trabaja con lo que la respuesta publica (series de T, P, n, H, F) y no recalcula termodinámica.

**Aceptación.**

- En `motor-ensamblaje-v2-resolver-*`, las escalas de tiempo calculadas coinciden con cocientes evaluados a mano sobre las series publicadas.
- Ninguna magnitud se inventa: un dato que no está en la respuesta se declara faltante.

### Fase M4 — Integración en el motor (requiere el visto bueno del usuario y cambios del motor)

Fuera del alcance actual, porque exige modificar el motor. Se documenta como propuesta para quien lleve F3 y F7:

- que el motor ofrezca «Abrir en adimensionalización» desde una hoja: solo un enlace con el id de hoja;
- que su solver acepte escalas de variables (`atol` por variable, ya contemplado en F0: «revisar escalas de residuos por magnitud/especie») usando las escalas publicadas por la formulación elegida;
- que el integrador implícito de F3 use el diagnóstico de rigidez de M2.

## 4. Sobre las propuestas de Gemini (`ARQUITECTURA_INTEGRACION_MULTIFISICA.md` §5)

| Propuesta | Valoración |
|---|---|
| C1: el backend calcula la transformación | **Sí**: es el diseño actual (núcleo único en Python). El cliente no hace álgebra. |
| C2: elegir la «forma óptima» minimizando max Π − min Π | **Mal planteada.** Los Π de una formulación no son comparables así, y elegir es decisión del usuario. Lo que sí se publica es la dispersión de magnitudes de los coeficientes por ecuación y los términos dominantes, para que el usuario elija la forma que deja en 1 los términos que dominan en su régimen. |
| C3: propagar restricciones al motor para abortar | Las restricciones ya se publican tipadas (`positivo`, `no_nulo`, `igualdad`). Usarlas dentro del motor es M4. |
| C4: correlaciones de transporte (Wilke-Chang…) | No corresponde a la adimensionalización: es catálogo y propiedades (F2/F6 del roadmap del motor). |
| X1: malla por Péclet de celda | El diagnóstico ya está implementado (`escalas.malla`). Aplicarlo en el motor es M4. |
| X2: cambio automático de integrador | Diagnóstico listo (`escalas.rigidez`). La decisión es de F3 del motor. |
| X3: búferes `Float64Array` | Rendimiento del motor; no afecta a esta herramienta. |
| X4: backends FEM y PINN | Fuera de alcance; no hay base verificable. |
| Contrato `EstadoResolucionMultifisica` | Prematuro. Mezcla configuración del solver, datos y formulación en un solo objeto. Se propone en su lugar el adaptador de M1 (hoja → `Documento` + valores) y el bloque `discretizacionMotor` de M2, sobre contratos ya existentes. |

## 5. Lo que necesito del usuario

1. ~~Prioridad~~: el usuario dejó elegir; se hizo M1 primero.
2. ~~Importar funciones del motor~~: se importan en solo lectura (funciones puras y `trabajoMotor.module.css` para la estética).
3. **Reiniciar los backends en 8004 y 8005**, que corren sin recarga y todavía no tienen `estudiar`.
4. Para M4, en su momento: autorizar cambios en el motor y quién los hace (Codex o Claude), según `docs/history/frontend/coordination-claude-codex-engine.md`.
