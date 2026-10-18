# Termodinámica de N componentes y ensamblaje dinámico (N0–N4)

Entrega de `frontend/ENCARGO_CLAUDE_TERMODINAMICA_N_COMPONENTES.md`. Núcleo, backend, pruebas y `docs/`. No se tocó
el frontend, `/laboratorio` ni `thermodynamics/proveedor.py`. Sin commit, push ni despliegue.

**Recarga:** reiniciar el servicio (`uvicorn backend.main:app`). Después debe verse en
`GET /motor/ensamblajes/capacidades?revision=2` que `componentesMaximos` vale 7 y que hay un campo nuevo,
`tamanos`. Las rutas no cambian.

## 1. Estado

| Hito | Estado |
|---|---|
| N0 auditoría | hecho (§2) |
| N1 estabilidad y reparto de dimensión general | hecho: Michelsen multisemilla para N ≥ 4, contrastado con las rutas especializadas de N = 2 y 3 |
| N2 inversiones y contrastes estáticos | hecho: ideal con N = 4, 5 y 7 frente a Rachford–Rice; NRTL con N = 4 (L–V y L–L) frente a un solver independiente con `thermo` |
| N3 dinámica | hecho: calentamientos a P prescrita con N = 4 (NRTL), 5 y 7 (ideal); rígido con vapor (N = 4); red de dos volúmenes (N = 5) con especie entrante e inversión de signo; extracción de vapor hasta agotarlo |
| N4 contrato, rendimiento y regresión | hecho (§6–§8) |
| NRTL con 5 o más especies | **bloqueado por datos**: no existe ningún conjunto de 5 especies del catálogo con todos los pares ChemSep (§2.3) |

## 2. N0 · Auditoría

### 2.1 Catálogo, volumen y especies activas

- **Catálogo global**: `solicitud.componentes` (revisión 2). El índice global `gidx` se usa para los
  balances y los residuos `global.materia.<id>`.
- **Componentes de cada volumen**: `volumenes[].componenteIds`. Cada volumen construye su
  `Sistema(paquete, CAS del volumen)`. El límite `componentesMaximos` se aplica por volumen, a componentes
  **declarados**.
- **Especies activas de un estado**: `idx = [i for i in n if n[i] > 0]` dentro de `core/mezclas.py`.
  - Una especie con cantidad exactamente cero sale del problema activo y conserva su ID: x = 0 en todas las fases
    y μ indefinida (`null` en `potenciales`).
  - Una traza positiva nunca se convierte en cero.

### 2.2 Dependencias de dimensión fija encontradas

| Lugar | Antes | Ahora |
|---|---|---|
| `prueba_estabilidad` | ramas para 1, 2 y 3 especies; con más, `no_soportado` | 1 a 3: rutas especializadas sin cambios. ≥ 4: `_estabilidad_general` (§3) |
| `_softmax3` | refinamiento ternario | sin cambios (solo N = 3) |
| `_minimizar_G`, `_pulir`, `flash_rapido/_newton`, `_meseta_general`, `_pulir_invariante` | ya eran de dimensión general | sin cambios de dimensión; `_pulir` ahora usa un Jacobiano desacoplado (§3.3) |
| `MAX_FASES = 3` | al llegar al tope se publicaba un fallo genérico | se mantiene en 3. Si queda una fase competidora sin hueco: rechazo explícito `tope_fases` (§3.4) |
| `COMPONENTES_VERIFICADOS` (ensamblaje v2) | 3 por volumen | 7 por volumen: el catálogo completo de mezclas, con los tamaños contrastados en `tamanos` |
| `VOLUMENES_VERIFICADOS` | 3 | 3 (fuera de alcance) |
| Diagramas | binarios | binarios (sin cambios: límite propio del trazador) |
| Residuos, series, eventos, catálogo de series | por componente y volumen | ya generales |
| Ensamblaje v1 | agua pura | sin cambios |

### 2.3 Pares NRTL y conjuntos completos

Se recorrieron todos los subconjuntos de las 7 especies del catálogo, exigiendo `bij` y `alphaij` de ChemSep
(vía `thermo` IPDB) para cada par. Hay 13 pares con datos. Conjuntos completos:

- **4 especies**: {etanol, benceno, tolueno, metanol} y {agua, etanol, acetato de etilo, metanol}. Se verificaron
  b_ij en ambas direcciones y α simétrica.
- **5, 6 o 7 especies**: ninguno. Por ejemplo, agua–benceno, acetato–benceno y butanol con etanol, benceno,
  tolueno o acetato no tienen parámetros.

No se inventaron coeficientes ni se rellenaron con cero. Un conjunto con un par ausente devuelve
`MOTOR_ESTADO_PARAMETRO_AUSENTE` en el servicio puntual o `MOTOR_ENS_PARAMETRO_AUSENTE` (`no_soportado`) en el
ensamblaje.

### 2.4 Dominio común y fases

El dominio es la **intersección** de los rangos de cada especie (Psat, cp, T ≤ 0.9 Tc), nunca la unión:

| Conjunto | T [K] |
|---|---|
| 7 especies (ideal) | 298.0–461.38 |
| {agua, etanol, acetato, metanol} | 298.0–461.38 (el acetato limita a 298 K) |
| {etanol, benceno, tolueno, metanol} | 278.68–461.38 |

P va de 100 Pa a 5 bar (vapor ideal, sin cambios). Fases: líquido y vapor, hasta 3 a la vez. El catálogo no
tiene ningún conjunto con intersección vacía; una T fuera de la intersección (p. ej. 290 K con acetato) se
rechaza aunque otras especies la admitan.

### 2.5 Operaciones identificables

TP, PH y UP siempre que haya dominio. UV y TV solo si hay vapor: el líquido incompresible que llena un
volumen no determina P, y se sigue rechazando con `no_soportado` para cualquier N.

## 3. N1 · Estabilidad y reparto

### 3.1 Fundamento

A T y P dadas, el equilibrio minimiza G = Σ_α Σ_i n_i^α μ_i^α con n_i = Σ_α n_i^α y n_i^α ≥ 0. La estabilidad
de un estado se comprueba con la distancia al plano tangente, con la misma referencia y el mismo paquete:

```
tm(w) = Σ_i w_i [μ_i^prueba(T, P, w) − μ_i^ref] / (R T),   w_i ≥ 0,  Σ w_i = 1
```

### 3.2 Método para N ≥ 4 (`Sistema._estabilidad_general`)

Michelsen, en variables de cantidad W_i:

```
tm*(W) = 1 + Σ_i W_i (ln W_i + ln γ_i(w) − d_i − 1),   d_i = (μ_i^ref − g_L,i)/(R T)
```

Sus puntos estacionarios coinciden con los de tm(w), y tm* < 0 si y solo si tm < 0.

- **Arranques deterministas**:
  - los N vértices puros;
  - la estimación ideal (γ = 1);
  - 2^⌈log₂(8N)⌉ puntos Sobol del símplex (`scipy.stats.qmc`, aleatorización con **semilla fija 12345**).
  - En total: 37 arranques con N = 4 y 72 con N = 7. El coste crece como ~8N, no como una malla tensorial.
- **Sustitución sucesiva** (`ln W_i = d_i − ln γ_i(w)`) de todos los arranques a la vez, con ln γ por lotes.
- **Pulido** de los candidatos distintos con L-BFGS-B en β_i = 2√W_i ≥ 0. W_i = 0 pertenece al dominio, así que las
  **caras y vértices del símplex** se alcanzan y una especie de prueba puede anularse sin evaluar `log 0`.
- **Fase de prueba vapor**: el mínimo analítico de siempre (vapor ideal).

Una búsqueda finita multisemilla **no demuestra el mínimo global**; así lo dicen el método publicado y las
capacidades.

**Contraste con las rutas especializadas** (donde ambas aplican, mismos estados):

| Caso | Especializada | General |
|---|---|---|
| Binario agua/1-butanol, L–L (x = 0.75, 320 K) | tm −3.6595637e-02 | −3.6595637e-02 |
| Binario estable (x = 0.4 y 0.99) | ≥ −1e-16 | ≥ −1e-16 |
| Ternario agua–etanol–acetato, L–L (0.7/0.05/0.25, 300 K) | −1.5652028e-03, misma composición | −1.5652028e-03 |
| Ternarios estables | ≥ −5e-16 | ≥ −9e-17 |

### 3.3 Reparto: Jacobiano desacoplado por fase (corrección)

Con una fase diminuta (p. ej. 3.7e-9 mol de vapor a 1e-12 K de la burbuja con 5 especies), la diferencia
finita global de 1e-7 en ln n mueve la fase resto menos que el ruido de redondeo de su μ. La dirección de la
cantidad total queda dominada por ruido y el Newton se estancaba en residuo 5.7e-10, por encima de la
tolerancia de 1e-10. El TP terminaba en `no_convergente`.

Ahora `_jacobiano_reparto` deriva cada fase solo respecto de sus cantidades. La fase resto se deriva respecto
de las suyas, con un paso proporcional a su cantidad, y ambas se combinan por la regla de la cadena. El mismo
caso converge con residuo 1.2e-15 y una cantidad de vapor que coincide con Rachford–Rice exacto
(3.7346256e-9 frente a 3.7346264e-9 mol).

### 3.4 Tope de fases

Si el estado ya tiene `MAX_FASES` fases y la prueba de estabilidad encuentra una fase que baja el plano
tangente, el estado **no** se publica como estable. Se rechaza así:

- `FueraDeAlcance('no_soportado', tope_fases=True)` en el núcleo;
- `MOTOR_ESTADO_TOPE_FASES` en el servicio puntual;
- detención `tope_fases` (`MOTOR_ENS_DETENIDO_TOPE_FASES`) en el ensamblaje.

## 4. N2 · Inversiones

PH, UP, UV y TV ya usaban el mismo TP, y por tanto la misma estabilidad y el mismo reparto. Tras cada inversión
se comprueban T, H, V y la composición de **un único reparto de fases**.

Se corrigió un defecto de UV. La búsqueda en T evaluaba primero el techo del dominio: con 7 especies (461 K) y V
fijo la presión supera los 5 bar, y la excepción abortaba todo. Ahora se acota la búsqueda a la T más alta
evaluable, como ya se hacía en el extremo frío. Si la U pedida queda por encima, se responde con
`fuera_de_dominio` y `P_fuera`.

## 5. Evidencia

| Tipo | Caso | Resultado |
|---|---|---|
| Referencia numérica independiente | Ideal N = 4, 5 y 7, tres composiciones Dirichlet cada uno, frente a Raoult + Poynting + Rachford–Rice escrito en la prueba | β y composiciones < 1e-9 |
| Otra implementación con iguales parámetros | NRTL N = 4 {etanol, benceno, tolueno, metanol} (345 y 350 K) y {agua, etanol, acetato, metanol} (345 K), L–V, frente a un flash γ-φ por sustitución sucesiva + Rachford–Rice con `thermo.nrtl.NRTL` | β, x e y < 1e-8 |
| Otra implementación con iguales parámetros | NRTL N = 4 L–L {agua, etanol, acetato, metanol} a 300 K (0.7/0.04/0.24/0.02), frente a isoactividad independiente con `thermo` | composiciones y reparto < 1e-8 |
| Coherencia interna | Gibbs–Duhem N = 4 en direcciones aleatorias (< 1e-7); g = h − Ts = Σ x μ; entalpías parciales molares frente a h_i − R T² ∂ln γ_i/∂T (< 1e-6) | cumple |
| Evidencia experimental | **ninguna nueva** | Los parámetros ChemSep vienen de ajustes binarios de VLE; las mezclas de 4 especies son predicciones del modelo (evidencia `cualitativa`). En particular, la separación L–L predicha para agua–acetato está lejos de la solubilidad experimental (la fase acuosa real tiene ~98 % de agua) |

**Controles y propiedades** (`tests/validar_motor_n_componentes.py`):
- **Ausencias**: catálogo de 7 especies con 3 exactamente a cero, frente al sistema reducido de 4: mismo estado (G a 1e-9), x = 0 y μ indefinida en las ausentes, IDs conservados.
- **Trazas** de 1e-6, 1e-9 y 1e-12: reconstrucción **por especie** relativa a su propio inventario < 1e-9; igualdad de μ ≤ 1e-10.
- **Extensividad**: ×1e-6, ×1 y ×1e6.
- **Permutaciones** de especies: mismo equilibrio y misma huella.
- **Semillas** de fase y composición distintas en el flash con semilla: el mismo mínimo que el flash completo.
- **Determinismo** de la estabilidad general con la semilla fija.
- **Negativos**:
  - par ausente;
  - T fuera de la intersección de dominios;
  - tope de fases forzado (`MAX_FASES = 1`) en el núcleo y en el servicio puntual;
  - UV de líquido lleno.

## 6. N3 · Dinámica

Mismo coordinador: estados n_i y U/H, con la termodinámica reconstruyendo el estado sin tocar cantidades ni
caudales. Casos (`tests/validar_motor_n_componentes.py` §N3):

1. **Calentamiento a P prescrita** con N = 5 (ideal), 4 (NRTL) y 7 (ideal):
   - H = H0 + Q t;
   - cada especie constante;
   - instante de burbuja frente a un flash estático independiente < 1e-5 relativo, con `faseIds = ['vapor-1']`;
   - certificación `cumple`.
2. **Rígido con vapor** (N = 4 NRTL): U = U0 + Q t, V constante y certificado.
3. **Dos volúmenes** (N = 5 ideal) con corriente de caudal negativo y contacto térmico:
   - conservación por especie;
   - donante B con su composición;
   - el agua entra en A desde cero, sin inventario ficticio y con su ID conservado;
   - segunda ley `cumple`.
4. **Extracción de vapor** de un volumen L–V adiabático: la composición global cambia; al agotarse el vapor se
   produce el evento `desaparicion_fase` y la detención `MOTOR_ENS_DETENIDO_FASE_AUSENTE`.
5. **Sensibilidad**: rtol 1e-6 con 3 muestras frente a 1e-10 con 9 muestras; los eventos coinciden < 1e-5 relativo.

**Defecto encontrado en el caso 3** (lo detectó la certificación C1 al regenerar el ejemplo): la derivada
total de V para el trabajo de frontera dividía la tasa de cada especie por su cantidad. Con el agua a cero eso
es /1e-30, y el paso quedaba en ~1e-33, perdido en el redondeo: residuo `mecanica.A.trabajo` 22 frente a
tolerancia 1. Ahora una especie a cero se escala con la cantidad total del volumen. Si el paso hacia atrás daría
una cantidad negativa, se usa una diferencia de tres puntos hacia delante, también de segundo orden. El residuo
pasa a 1.8e-5 y la red se certifica.

La vigilancia de eventos sigue siendo **puntual** (3 puntos interiores y el extremo de cada paso), no continua.

## 7. Contrato (aditivo)

- `CapacidadesEnsamblajeV2.componentesMaximos`: **7** (componentes declarados por volumen; antes 3). No cambia de
  nombre ni de unidad; su valor refleja lo que el ensamblaje acepta y prueba.
- `CapacidadesEnsamblajeV2.tamanos?` (nuevo, opcional):

```ts
tamanos?: {cuenta: string; componentesMaximosPorVolumen: number; fasesMaximas: number;
  contrastados: Record<string, {estatico: number[]; dinamico: number[]}>;
  estabilidad: Record<string, string>; presupuesto: string};
```

  Valores publicados: `contrastados` = mezcla-ideal estático [2, 3, 4, 5, 7], dinámico [2, 4, 5, 7];
  nrtl-chemsep estático [2, 3, 4], dinámico [2, 4]; nrtl-lle-agua-butanol [2]; agua-iapws95 [1].
- Códigos nuevos: `MOTOR_ESTADO_TOPE_FASES` (servicio puntual) y la detención `tope_fases`
  (`MOTOR_ENS_DETENIDO_TOPE_FASES`).
- El servicio puntual de mezclas ya aceptaba cualquier número de componentes; ahora el núcleo los resuelve. Los
  diagramas siguen siendo binarios.
- **Huellas**: no cambian por orden de componentes (probado con permutaciones), nombres ni unidades. La
  configuración numérica (semilla 12345, número de arranques) va en el método publicado, no en la huella física.

**Para el frontend:** la copia `frontend/app/motor/contratoEnsamblajeV2.ts` ya es idéntica al contrato canónico,
campo `tamanos` incluido. Se comprobó con `diff` al cerrar: Codex la sincronizó durante esta entrega, y el
verificador de copia de `npm run test:motor-fundamental` pasa.

## 8. Rendimiento (`python tests/benchmark_n_componentes.py`)

Semilla de la estabilidad general: 12345. Tolerancias: |Δμ|/RT ≤ 1e-10, tm ≥ −1e-9. Tiempos en este equipo,
mínimo de tres repeticiones; «fría» = `Sistema` nuevo sin cachés.

**Rutas especializada y general, donde ambas aplican (mismo estado):**

| N | especializada | general (arranques) | min tm (ambas) |
|---|---|---|---|
| 2 (agua/1-butanol, L–L) | 6.8 ms | 22.9 ms (19) | −3.6596e-02 |
| 3 (agua–etanol–acetato, L–L) | 105.5 ms | 72.4 ms (36) | −1.5652e-03 |

Se conservan las rutas especializadas para N = 2 y 3: son el mismo problema y dan el mismo mínimo. La general
solo se usa para N ≥ 4.

**Estados:**

| Paquete, N | TP una fase (fría) | TP L–V | TP a +1e-6 K de la burbuja | PH | UV | memoria pico |
|---|---|---|---|---|---|---|
| NRTL, 4 | 47 ms (124 ms) | 23 ms | 61 ms | 0.47 s | 6.8 s | 0.1 MB |
| ideal, 4 | 3 ms (11 ms) | 10 ms | 35 ms | 0.10 s | 1.8 s | < 0.1 MB |
| ideal, 5 | 3 ms (14 ms) | 15 ms | 36 ms | 0.12 s | 2.2 s | < 0.1 MB |
| ideal, 7 | 5 ms (17 ms) | 19 ms | 47 ms | 0.15 s | 1.8 s | 0.1 MB |

Antes de vectorizar la sustitución sucesiva, UV con NRTL de 4 especies tardaba **31–35 s**: 329 pruebas de
estabilidad generales de ~0.1 s cada una. Ahora, 6.8 s.

**Trayectorias completas** (calentamiento a P prescrita, 300 s, 7 muestras, rtol 1e-8):

| Caso | tiempo | pasos |
|---|---|---|
| ideal, N = 5 | 21.6 s | 24 |
| NRTL, N = 4 | 36.3 s | 19 |
| ideal, N = 7 | 29.9 s | 22 |

Presupuesto por estado: 3 fases como máximo y N + 1 + 2^⌈log₂(8N)⌉ arranques de estabilidad. Las cachés
(`_g_puros` por (T, P) y submodelos por conjunto de especies activas) son funciones puras de cada `Sistema`, que
está ligado a una huella. Una semilla de flash solo es punto de partida y todo estado pasa la prueba de
estabilidad completa.

## 9. Pruebas, ejemplos y archivos

**Comandos ejecutados y códigos de salida** (estado final del código):

| Comando | Resultado |
|---|---|
| `python tests/validar_motor_n_componentes.py` | 0 · OK, 82 comprobaciones (N0–N2: 61; N3: 21, repetido tras la última corrección) |
| `python tests/validar_motor_ensamblaje_v2.py` | 0 · OK, 114 (la comprobación de `componentesMaximos` pasa de 3 a 7: cambio deliberado de capacidad) |
| `python tests/validar_motor_consolidacion_v2.py 0 1 2 3` | 0 · OK, 56 / 14 / 31 / 27 |
| `python tests/validar_motor_diagramas_equilibrio.py` | 0 · OK, 78 |
| `python tests/validar_motor_ensamblaje.py` (v1) | 0 · OK, 245 |
| `python tests/validar_motor_termodinamica.py` (H1) | 0 · OK, 585 |
| `python tests/validar_motor_termodinamica_h3.py` (H3) | 0 · OK, 3729 |
| batería histórica `tests/validar_*.py` (40 suites) | 0 en las 40 |
| `node tests/verificar_contrato_ensamblaje_v2.mjs` | 0 · 10 pares v2 compilados (incluye `motor-n-componentes`), 60 estados por volumen y 12 ejemplos puntuales por el validador del frontend |
| `node tests/verificar_contrato_ensamblaje.mjs` | 0 · 13 pares, 175 estados |
| `node tests/verificar_contrato_diagramas.mjs` | 0 · 11 pares, 285 puntos |
| `node tests/verificar_contrato_motor_termodinamica.mjs` | 0 |
| `npm run test:motor-fundamental` (frontend, sin modificar) | 0 · los 24 verificadores pasan en la copia original del frontend |

Los ensayos del frontend con 5, 8 y 12 componentes son comprobaciones algebraicas de lectura: no cuentan
como validación termodinámica de esta entrega.

### 9.1 Batería histórica

Las 40 suites `tests/validar_*.py` que no son del motor terminan con código 0 con el código final.

### 9.2 Ejemplos generados desde endpoints

`docs/ejemplos/motor-n-componentes/` (`python tests/generar_ejemplos_motor_n_componentes.py`), en un directorio
propio para no alterar lo que leen los verificadores de revisión 1 ni los de Codex:

- Servicio puntual:
  - ideal con 5 y 7 especies (L–V);
  - NRTL con 4 especies en L–V y en L–L;
  - NRTL con un par ausente (`MOTOR_ESTADO_PARAMETRO_AUSENTE`).
- Ensamblaje v2:
  - calentamiento ideal con 5 especies y NRTL con 4 (ambos `cumple`);
  - red de 5 especies con especie entrante (`cumple`);
  - validación con un par ausente (`MOTOR_ENS_PARAMETRO_AUSENTE`, `no_soportado`; el recuento estructural
    sigue `listo` y la resolución se rechaza).

**Comparación con los ejemplos anteriores:**

- `docs/ejemplos/motor-v2/`:
  - Capacidades: `componentesMaximos` pasa de 3 a 7 y aparece `tamanos` (deliberado).
  - Decantador agua–butanol: solo cambian residuos y tm en el orden de 1e-16 y `global.energia` escalado
    (2.05e-8 → 1.60e-8, tolerancia 10), por el Jacobiano desacoplado del reparto. Series, tiempos y eventos,
    idénticos.
  - Resto de ejemplos: idénticos.
- `docs/ejemplos/motor-n-componentes/`, red con especie entrante:
  - Antes de la corrección de la derivada de V, la certificación salía `no_cumple` (`mecanica.A.trabajo` 22).
  - Después, `cumple`: W de A cambia un 9.5e-4 relativo (antes era erróneo) y el resto de series cambia
    ≤ 7.6e-9 relativo (control de paso, rtol 1e-8).
  - Los demás ejemplos N, idénticos.

### 9.3 Archivos tocados

- **Núcleo**:
  - `core/mezclas.py`: `_estabilidad_general`, tope de fases, `_jacobiano_reparto`, búsqueda en T de UV acotada en
    el extremo caliente;
  - `core/ensamblaje_red.py`: escala y diferencia hacia delante en `_dVdt`; detención `tope_fases`.
- **Backend**:
  - `backend/motor_ensamblaje_v2.py`: `componentesMaximos` 7 y `tamanos`;
  - `backend/motor_mezclas.py`: `MOTOR_ESTADO_TOPE_FASES`.
- **Contrato**: `docs/contratos/contratoEnsamblajeV2.ts` (`tamanos?`; documentación de `componentesMaximos`).
- **Pruebas**:
  - nuevos: `tests/validar_motor_n_componentes.py`, `tests/benchmark_n_componentes.py`,
    `tests/generar_ejemplos_motor_n_componentes.py`;
  - modificados: `tests/verificar_contrato_ensamblaje_v2.mjs` (recorre también `motor-n-componentes`) y
    `tests/validar_motor_ensamblaje_v2.py` (`componentesMaximos` 7).
- **Ejemplos**: `docs/ejemplos/motor-n-componentes/*` (nuevos); `docs/ejemplos/motor-v2/*` (regenerados).
- **Documentación**: este documento.

## 10. Límites que permanecen

- **NRTL con 5 o más especies**: sin datos (§2.3). No se inventan parámetros.
- **Evidencia**: las mezclas de 4 especies son predicciones de parámetros binarios de VLE, sin contraste
  experimental (`cualitativa`). La separación L–L predicha para agua–acetato no reproduce la solubilidad real.
- **Estabilidad**: búsqueda finita multisemilla, no una demostración del mínimo global.
- **Fases**: 3 como máximo. Un estado que necesitaría una cuarta se rechaza (`tope_fases`), nunca se publica como
  estable.
- **Dominio**: vapor ideal hasta 5 bar, líquido incompresible, sin región crítica; dominio común = intersección.
- **Rendimiento**: UV con NRTL de 4 especies, ~7 s por estado; trayectorias de 20–40 s.
- **Eventos**: vigilancia puntual. Cuando la propia extracción hace desaparecer la fase extraída, el evento
  terminal es la detención `fase_ausente`, sin un `desaparicion_fase` separado: ningún paso puede cruzar esa
  frontera. La última muestra queda con la fase residual (8e-11 en el caso probado).
- **Diagramas**: siguen siendo binarios. **Volúmenes**: 3.
- La ampliación de N no implica termodinámica universal, altas presiones ni más fases.
