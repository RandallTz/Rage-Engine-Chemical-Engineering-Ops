# Consolidación multifásica (C0–C4) · 15 de octubre de 2026

Respuesta a `frontend/ENCARGO_CLAUDE_CONSOLIDACION_MULTIFASICA_2026_10_15.md` y a los puntos de
`frontend/INTEGRACION_MULTIFASICA_V2.md` («Límites y seguimiento de Claude»). Backend, núcleo, pruebas y
`docs/`; no se tocó `frontend/`, `/laboratorio` ni `thermodynamics/proveedor.py`. Sin commit ni push.

**Recarga:** reiniciar el servicio (`uvicorn backend.main:app`); `backend/main.py` no cambia en esta entrega.

| Parte | Estado | Dónde |
|---|---|---|
| C0 capacidades coherentes | implementado y probado | `capacidades_v2()`; `tests/validar_motor_consolidacion_v2.py` §C0 |
| C1 certificación física | implementado y probado | `resultados.certificacion`; §C1 |
| C2 series y eventos | implementado y probado; tres defectos corregidos (IDs, coste del PH, integrador sin avance) | `resultados.catalogoSeries`, campos de `EventoV2`; §C2 |
| C3 contrastes físicos | implementado y probado; un defecto corregido (fase ausente sin diagnóstico) | §C3 |
| C4 frontera abierta, agua + aire | **solo diseño** (no implementado) | `docs/DISENO_FRONTERA_ABIERTA_AGUA_AIRE.md`, `docs/contratos/borradorFronteraAbierta.ts` |

Todos los campos nuevos son **opcionales y aditivos** en la revisión 2 (`docs/contratos/contratoEnsamblajeV2.ts`).
Ningún campo existente cambia de nombre ni de valor, salvo las dos correcciones documentadas en §5.

## 0. Qué conviene hacer en el frontend

Sugerencias para la integración; no se ha tocado ningún archivo del frontend.

1. **Volver a copiar el contrato**: `frontend/app/motor/contratoEnsamblajeV2.ts` es una copia anterior. Los tipos
   nuevos (`EventoV2`, `SerieCatalogoV2`, `CertificacionV2`, `CombinacionV2`, `EvidenciaV2` y los campos
   opcionales de paquetes y potenciales) están en `docs/contratos/contratoEnsamblajeV2.ts`.
2. **Certificación**: leer `resultados.certificacion.estado` para el aviso de «trayectoria sin certificar», en
   lugar de deducirlo de `segundaLey` o de los residuos. `no_evaluable` no es `cumple`.
   `ultimaMuestraCertificada` y `primeraMuestraNoCumple` marcan hasta dónde mostrar la trayectoria como válida.
   `estado` (resuelto/parcial) sigue siendo solo numérico.
3. **Series**: unidades, magnitud y papel desde `resultados.catalogoSeries`, que cubre todas las series. Las
   de papel `derivada` (masa, S, S_gen) no tienen ecuación en `validacion.ecuaciones`.
4. **Eventos**: `faseIds`, `faseIdsAntes` y `faseIdsDespues` identifican las fases reales. Hay un código nuevo,
   `sustitucion_fase`; `cambio_denominacion` no debe dibujarse como evaporación ni condensación.
5. **Capacidades**: `combinaciones[].id` y `evidencia` permiten distinguir contrastada, cualitativa e imposible
   en el modelo. `pares` dice qué binarios NRTL tienen datos.
6. **Potenciales**: G, A y S son extensivos (`unidades: {mu: 'J/mol', G: 'J', A: 'J', S: 'J/K'}`).
7. **Fracciones**: con una sola fase ahora llegan exactamente a 1. El margen de ocho épsilon del lector ya no
   hace falta para ese caso; si se conserva, no pasa nada.
8. **Ejemplos**: los de `docs/ejemplos/motor-v2/` están regenerados desde los endpoints con todos los campos
   nuevos; el lector v2 de Codex (`npm run test:motor-fundamental`) los acepta.

## 1. C0 — capacidades

`GET /motor/ensamblajes/capacidades?revision=2`, por paquete:

- Cada combinación lleva `id` estable (`una_fase`, `liquido_vapor`, `liquido_liquido`, `solido`,
  `region_critica`, `liquido_rigido_lleno`) y `evidencia`: `contrastada` | `cualitativa` |
  `imposible_en_el_modelo` | `sin_modelo` | `excluida`.
- Cada paquete añade `componentesCAS`, `dominio` (iguales a los de `/motor/termodinamica/capacidades`),
  `limites` y, en NRTL, `pares` con procedencia y evidencia por binario.

| Paquete | una fase | LV | LL/LLV |
|---|---|---|---|
| `agua-iapws95` | contrastada | contrastada | — (sólido: `sin_modelo`, el hielo existe solo estático; crítica: `excluida`) |
| `mezcla-ideal` | contrastada | contrastada | `imposible_en_el_modelo` (g^E = 0), no publicada |
| `nrtl-chemsep` | contrastada | cualitativa (contrastada solo etanol–agua) | cualitativa (parámetros de VLE) |
| `nrtl-lle-agua-butanol` | contrastada | cualitativa (ajuste solo LLE) | **contrastada** (IUPAC SDS-15), publicada |

Pares ChemSep publicados: 13 de los 21 posibles entre las 7 especies; sin parámetros (p. ej. agua–benceno)
no aparecen y su uso devuelve diagnóstico. El texto «M5 pendiente» desaparece; `noSoportado` dice que el hielo
es solo estático. La prueba de coherencia recorre los estados de todos los ejemplos ejecutados y falla si
alguno usa una combinación no publicada de su paquete.

## 2. C1 — certificación física (`resultados.certificacion`)

`estado` (resuelto/parcial) sigue siendo **solo** el resultado numérico. La certificación es aparte:

```ts
type CertificacionV2 = {estado: 'cumple'|'no_cumple'|'no_evaluable'; motivo: string;
  aspectos: {id: 'estados_termodinamicos'|'conservacion'|'cierre_constitutivo'|'segunda_ley';
             estado: 'cumple'|'no_cumple'|'no_evaluable'; motivo: string; referencias: string[];
             primeraMuestraNoCumple: number|null}[];
  alcance: {tInicial: number; tFinal: number; muestras: number; completa: boolean};
  ultimaMuestraCertificada: number|null};
```

- `conservacion`: residuos `global.*`; `cierre_constitutivo`: `estado.*` y `mecanica.*`; `segunda_ley`: la
  verificación existente; `estados_termodinamicos`: toda muestra publicada pasó sus verificaciones (una que no
  pasa detiene la publicación y queda en diagnósticos).
- Global: `no_cumple` si algún aspecto no cumple; si no, `no_evaluable` si alguno no es evaluable (segunda ley
  sin T de frontera); si no, `cumple`. Segunda ley no evaluable **no** se presenta como cumplida ni invalida un
  balance de energía correcto.
- Con `no_cumple` se añade el diagnóstico `MOTOR_ENS_CERTIFICACION_NO_CUMPLE` (estado `invalido`) en
  `validacion.diagnosticos`.
- **No se recorta la trayectoria**: se conserva toda la evidencia; `primeraMuestraNoCumple` (índice en
  `tiempos`) y `ultimaMuestraCertificada` marcan el corte. La interfaz no necesita decidirlo.

Pruebas (§C1): red cerrada nominal → `cumple`; materia corrupta en un volumen → `no_cumple` en
`conservacion` con `global.materia.1`; energía corrupta (1 W espurio) → `global.energia`; 1 kW desde una
frontera a 300 K a agua a 350 K → segunda ley `no_cumple` desde la muestra 1, conservación `cumple`; sin T de
frontera → `no_evaluable`, sin S_gen publicada; la misma red ×1000 en materia, volumen y conductancia → mismos
residuos escalados en orden de magnitud, misma T(t) y la misma corrupción relativa detectada.

## 3. C2 — series, eventos y denominación

**`resultados.catalogoSeries`**: una entrada por serie (`variableId`, `propietarioId`, `unidadSI`, `magnitud`,
`papel`, `variableEnsamblajeId`, `procedencia`). `papel` describe cómo se obtiene el valor:
`estado_integrado`, `algebraica`, `dato`, `integral_auxiliar` (W acumulado) o `derivada` (masa, S, S_gen:
presentación, sin ecuación propia). `variableEnsamblajeId` apunta a `validacion.variables` o es `null`; el
recuento (GL) no cambia. El papel en el recuento sigue estando en `validacion.variables`.

**Eventos** (`EventoV2`): `faseIds` = fases que aparecen o desaparecen (IDs reales del volumen); aditivos
`faseIdsAntes`, `faseIdsDespues`, `descripcion`. Eventos sin volumen (detenciones) siguen con `[]`. Códigos:

- `aparicion_fase`, `desaparicion_fase`;
- `sustitucion_fase` (**nuevo**): mismo número de fases, una desaparece y otra aparece (p. ej. LL → LV en un
  heteroazeótropo). Antes se clasificaba como `cambio_denominacion`, lo que era incorrecto;
- `cambio_denominacion`: solo líquido/vapor ↔ fluido supercrítico; la descripción dice que no es
  evaporación, condensación ni transición de primer orden. Probado con agua a 300 bar cruzando Tc: H = H0 + Q t y
  T monótona, sin meseta.

**IDs de líquidos**: continuidad por composición con asignación de menor distancia total (antes era voraz y,
al quedar un solo líquido, volvía a tomar el ID del paquete). Un líquido que aparece recibe un número nunca
usado antes en el volumen. Probado: al agotar por extracción la fase densa (`liquido-1`), la orgánica conserva
`liquido-2` aunque sea la única; un segundo líquido que aparece al alimentar agua recibe un ID nuevo; una fase
ausente no se publica.

## 4. C3 — contrastes físicos

| Contraste | Resultado |
|---|---|
| Referencias desplazadas por especie (h, s del gas ideal de etanol y agua) | T(t) idéntica; H y S se desplazan exactamente Σ n_i Δh_i = 864.6 J y Σ n_i Δs_i = 5 J/K; eventos dentro de la tolerancia de la bisección (1.5e-7 s) |
| h^E del cierre frente a −R T² Σ x_i ∂ln γ_i/∂T | acuerdo < 1e-5 relativo |
| Entalpías parciales molares (∂(n h)/∂n_i) frente a h_i° − R T² ∂ln γ_i/∂T | < 1e-6 relativo |
| Líquido sobrecalentado homogéneo | rechazado por la prueba de vapor (tm < 0) |
| Flash TP con 4 semillas distintas (LL, LV, otra composición) | mismo mínimo de G que el flash completo |
| Meseta LLV en PH con fracción 1e-6, 0.5 y 1 − 1e-6 | componentes, energía y volumen reconstruidos |
| Burbuja ± 1e-9 relativo | certificada a ambos lados |
| Corriente con caudal negativo | el donante pasa a ser B y conserva su composición; una transferencia con signos opuestos |
| rtol 1e-6 / 3 muestras frente a 1e-10 / 10 muestras | eventos y T final coinciden |
| Límites | par sin parámetros, P = 10 bar, líquido que llena un rígido, 150 K y extracción de una fase ausente: rechazados con diagnóstico |

**Defectos encontrados y corregidos** (cada uno con su regresión):

1. Extraer vapor de un volumen sin vapor terminaba en `no_convergente` con `MOTOR_ENS_MUESTRA_NO_CERTIFICADA`,
   sin decir por qué. Ahora es `invalido` con `MOTOR_ENS_DETENIDO_FASE_AUSENTE` (§C3).
2. IDs de líquidos: con menos líquidos que IDs previos, la asignación solo consideraba los primeros IDs, y la
   fase orgánica superviviente heredaba `liquido-1` tras agotarse la acuosa (§C2, decantador).
3. Coste: al bisecar la aparición de un segundo líquido, el respaldo del flash PH buscaba T en todo el dominio
   con un TP completo por paso; la aparición LL al alimentar agua no terminaba en más de 30 min. Ahora
   `equilibrio_PH/UP` aceptan la semilla del integrador: intervalo local que se ensancha ×4 hasta encerrar la
   raíz y TP con semilla en cada evaluación (con caída al TP completo). Raíz, certificación y mesetas son las
   mismas: el caso tarda 3.6 s y los ejemplos regenerados no cambian más allá de lo indicado en §5.
4. Integrador sin avance en una frontera de fases: la vigilancia veía el cambio de conjunto de fases en el
   interpolante del paso y la bisección lo situaba en t_e, pero el estado reintegrado hasta t_e aún no había
   cambiado (difieren en ~rtol justo en la frontera). No se registraba evento, se reiniciaba en t_e y se volvía
   a detectar lo mismo indefinidamente: el decantador que agota la fase densa no terminaba (> 35 min). Ahora,
   si en t_e el estado reintegrado no cambia, se avanza con pasos que se duplican desde la resolución de la
   bisección hasta el primer instante en que cambia (o se acepta el paso sin evento si no cambia en todo él).
   El decantador termina en 13 s con el evento en el mismo instante (509.801 s) y certificación `cumple`.

El límite de la vigilancia de eventos sigue siendo explícito en `metodo`: puntual (3 puntos interiores y el
extremo de cada paso), no continua.

## 5. Correcciones de valores publicados (comparadas con los ejemplos anteriores)

Se regeneraron los ejemplos de `docs/ejemplos/motor-v2/` y se compararon campo a campo con la versión anterior:

- Tras los cambios de C0–C2: series, tiempos, eventos y estados **idénticos** (diferencia relativa 0); solo
  cambian los residuos escalados de energía (punto siguiente a este grupo).
- Tras la búsqueda PH con semilla (defecto 3): solo el calentamiento etanol–agua cambia. Los instantes de
  evento se mueven 5e-11 s y 7e-8 s (tolerancia de la bisección 4.5e-7 s); las series, como mucho 2.5e-7
  relativo (U y W en la muestra del evento); el resto son residuos y tm de orden 1e-16. Los demás ejemplos solo
  ganan el campo `potenciales.unidades`.
- Tras corregir el integrador (defecto 4): todos los ejemplos **idénticos** a la versión anterior.
- `residuos[].maximoEscalado` de `global.energia` y `estado.<v>.energia`: cambian (≈ −11 % en el
  calentamiento) porque la escala de energía pasa de `max|ΣU|` a `max(|ΣU|, |∫E_ext|, |ΣW|)`. |U| depende del
  cero de la referencia y puede pasar por 0; la escala nueva no. Las tolerancias no cambian.
- Antes, en esta misma serie de entregas, la escala de `global.materia.*` sumaba también energías del vector
  de estado (la hacía insensible); ya está corregido y documentado.
- **Fracciones de fase** (incidencia de Codex, `binario-editado`): con una sola fase se publica exactamente 1
  (identidad) en lugar de un cociente que podía dar `1.0000000000000002`. Reproducido con la petición de Codex:
  máximo 1.0. El lector no necesita margen para este caso.
- **`PotencialesV2`** (incidencia de Codex): `base: 'molar'` y `unidad: 'J/mol'` se refieren solo a μ. G, A y
  S han sido siempre extensivos del volumen (J, J, J/K); se añade `unidades: {mu, G, A, S}` y un erratum en el
  tipo. Los valores no cambian.

## 6. C4 — diseño (no implementado)

Ver `docs/DISENO_FRONTERA_ABIERTA_AGUA_AIRE.md`: por qué el agua pura a 10 °C no puede estar a 1 atm con
espacio de vapor; paquete propuesto (IAPWS-95 para el agua en ambas fases, gas con virial truncado, aire
insoluble declarado) y por qué el gas ideal no basta (Z_sat − 1 de −1.5 % a 100 °C); inicialización por P0 que
calcula el aire; hermético; frontera abierta como DAE de índice 2 con F explícito tras derivar la restricción,
proyección y residuo `mecanica.<v>.presion`; régimen de inversión; datos necesarios con fuentes; plan de
pruebas. El borrador tipado compila contra la revisión 2 y su petición de ejemplo
(`docs/ejemplos/borrador-frontera-abierta/olla-abierta-peticion.json`) **es rechazada** por el servicio actual,
comprobado en §C0.

## 7. Pruebas

| Prueba | Resultado |
|---|---|
| `python tests/validar_motor_consolidacion_v2.py` | OK: C0 56, C1 14, C2 31, C3 27 |
| `python tests/validar_motor_ensamblaje_v2.py` | OK, 114 |
| H1 / H3 / ensamblaje v1 | OK, 585 / 3729 / 245 |
| `node tests/verificar_contrato_ensamblaje_v2.mjs` (incluye el borrador C4) | OK |
| `node tests/verificar_contrato_ensamblaje.mjs`, `verificar_contrato_motor_termodinamica.mjs` | OK |
| `npm run test:motor-fundamental` (frontend, sin modificar; incluye el lector v2 de Codex) | OK |

No se afirma regresión completa del frontend mientras su integración siga en curso (`npm test` y `tsc` son de
Codex).

## 8. Archivos tocados

`backend/motor_ensamblaje_v2.py`, `backend/motor_mezclas.py`, `core/ensamblaje_red.py` (clasificación de eventos y avance en fronteras), `core/mezclas.py` (PH/UP con semilla),
`docs/contratos/contratoEnsamblajeV2.ts`, `tests/validar_motor_consolidacion_v2.py` (nuevo),
`tests/verificar_contrato_ensamblaje_v2.mjs`, `docs/ejemplos/motor-v2/*` (regenerados),
`docs/ejemplos/motor-termodinamica-capacidades.json` (regenerado, sin cambios), `docs/CONSOLIDACION_MULTIFASICA.md`,
`docs/DISENO_FRONTERA_ABIERTA_AGUA_AIRE.md`, `docs/contratos/borradorFronteraAbierta.ts`,
`docs/ejemplos/borrador-frontera-abierta/olla-abierta-peticion.json`.

## 9. Incidencias que quedan

- Burbuja/rocío casi azeotrópicos a ~1e-12 K: el motor puede negarse a certificar (`no_convergente`).
- La prueba de estabilidad es una malla con refinamiento, no una demostración del mínimo global; publica las
  candidatas exploradas y el número de pruebas.
- Vigilancia de eventos puntual: una transición que aparece y desaparece entre dos puntos vigilados de un paso
  no se detecta.
- C4 entero (paquete agua + aire, inicial por presión, caudal por restricción).
