# Termodinámica del motor independiente — entrega H3

14 de octubre de 2026. Responde a `frontend/CONTRATO_CLAUDE_TERMODINAMICA_H3.md`. Continúa [MOTOR_TERMODINAMICA_H0_H1.md](MOTOR_TERMODINAMICA_H0_H1.md), cuyas decisiones (EOS, unidades, masa molar, referencia, dominio, estabilidad TP) siguen vigentes.

Qué hay: coexistencia líquido-vapor del agua pura y las especificaciones **PH, UP y UV** para `agua-iapws95` v`1`, con una o dos fases, fracciones en las tres bases y verificaciones de equilibrio, energía y volumen. El contrato HTTP es el mismo: revisión 1 y las mismas rutas, sin campos nuevos. `dinamica` sigue en `false`.

| Pieza | Archivo |
| --- | --- |
| Física | `core/agua_iapws95.py`, sección «H3» al final (lo anterior no cambia) |
| Contrato | `backend/motor_termodinamica.py`: lectura de `cantidades`, `_evaluada_inversa` |
| Pruebas H3 | `tests/validar_motor_termodinamica_h3.py` (3729 comprobaciones) |
| Pruebas H1 | `tests/validar_motor_termodinamica.py` (585; los casos «PH/UV no soportado» pasan a la suite H3) |
| Ejemplos | `docs/ejemplos/motor-termodinamica-*` (8 nuevos casos H3) |

## Versión del modelo: sigue siendo `1`

Los estados TP no cambian: `evaluar_TP`, la estabilidad, los ajustes de saturación que separan las ramas y las verificaciones de H1 son el mismo código. Las 9 respuestas TP de los ejemplos de H1 se regeneraron y son **idénticas byte a byte**. Cambian dos ejemplos, y es intencionado:

- `capacidades`: `especificaciones` pasa de `["TP"]` a `["TP","PH","UP","UV"]`.
- `saturacion-indeterminada`: el diagnóstico añade `alternativas` (PH, UP, UV, ya publicadas) y deja de decir que no se admiten.

Se ha **retirado** el ejemplo `ph-no-soportado`: describía una limitación que ya no existe. Ampliar especificaciones no cambia el significado de TP, así que no hay cambio de versión; la ampliación se publica en `capacidades`, donde el cliente la lee.

## Coexistencia

**Ecuaciones.** A T dada, T′ = T″ por construcción, y P(T,ρ′) = P(T,ρ″) y g(T,ρ′) = g(T,ρ″). Se resuelven por Newton en (ρ′, ρ″) con jacobiano analítico: ∂P/∂ρ = (∂P/∂ρ)_T y ∂g/∂ρ = (∂P/∂ρ)_T/ρ a T fija.

**Semilla y ramas.** La semilla son los ajustes de `chemicals` a la solución en precisión múltiple: una densidad en la rama líquida y otra en la de vapor, nunca en la región homogénea de la campana. Cada paso debe mantener ρ′ > ρc > ρ″; si sale de su rama, se rechaza. No hay terceras raíces: la región homogénea entre ρ″ y ρ′ no es una fase candidata (H1 explica por qué la EOS no es física ahí).

**Convergencia.** Se itera hasta que el residuo deja de bajar (límite de coma flotante), con un máximo de 30 iteraciones; suelen bastar 1 a 3. El residuo se publica en `equilibrio`:

$$\max\Big(\tfrac{|g'-g''|}{RT},\ \tfrac{|P'-P''|}{\max(P'',\ \rho'(\partial P/\partial\rho)_T')}\Big)\le 10^{-9}$$

La diferencia de presiones se escala con el módulo de compresibilidad del líquido porque su presión es rígida: con ρ′ exacta al último bit, P′ solo se fija a unos 1e-7 Pa. Por eso Psat es P″, la del vapor, que está bien condicionada. Medido: residuo ≤ 1e-12 entre 273.16 y 643.86 K.

**Tsat(P).** Primero se busca una horquilla con Brent sobre el ajuste monótono Psat(T) en [273.16, 643.86] K. Después se afina con Newton en T, usando la coexistencia resuelta y la pendiente de Clapeyron (s″−s′)/(v″−v′). El residuo |Psat(Tsat) − P|/P se publica en `presion_saturacion`: medido ≤ 4e-15, tolerancia 1e-10.

**Límite crítico.** La coexistencia se publica solo con Tsat ≤ 643.86 K = 0.995·Tc, el borde de la banda crítica de H1. Ahí Psat = 21.22 MPa y h″−h′ ≈ 412 kJ/kg, una diferencia todavía bien condicionada. Por encima, las diferencias entre fases tienden a cero y la calidad queda mal condicionada: un estado PH/UP/UV que caiga ahí sale `no_soportado` con `MOTOR_ESTADO_REGION_CRITICA`. No se fabrica una calidad.

**Punto triple.** A 273.16 K podría coexistir también el hielo, que el modelo excluye. Una inversión que, por redondeo, caiga un bit por debajo de T_MIN se rechaza como fuera de dominio.

## Reparto entre fases

Con agua pura, q es la fracción másica de vapor y coincide con la molar:

$$y = (1-q)\,y' + q\,y'' \quad (y = u, h, v, s), \qquad \varepsilon_v = q\,v''/v$$

Todas las propiedades de fase están a la misma T y P y con la misma referencia IAPWS-95. El calor latente es h″−h′; no hay ninguna fuente aparte. La fracción volumétrica difiere de q: en el recipiente rígido de ejemplo, q = 0.419 y ε_v = 0.9935.

**Conjunto activo.** El problema de los extremos es numérico. Con q exactamente 0 o 1 en la entrada, el error de Tsat(P), de hasta ~7e-13 K junto a 643.86 K, y el redondeo de y y v dejan fracciones espurias de entre 1e-19 y 1.3e-13 (lo midió la suite). La regla es **Q_MIN = 1e-12**, aplicada a los dos lados de la meseta:

- una q calculada en [−Q_MIN, Q_MIN] es la frontera q = 0 (y simétrico en 1);
- en la frontera se publica solo la fase presente;
- trazas a partir de 1e-11 se conservan y se reconstruyen;
- la energía y el volumen reconstruidos se publican como residuos (en la frontera, ≤ 1e-12·Δy/(RT)).

No hay recorte ni renormalización de cantidades ni de energía.

**Capacidades caloríficas.** Con dos fases, o con una sola sobre la curva (frontera), la `mezcla` **no** lleva cp ni cv, porque la derivada del estado de equilibrio no es la de una fase. Cada fase conserva sus cp y cv monofásicos. Un estado de una fase fuera de la curva sí publica cp y cv globales.

## Criterio de selección de cada especificación

**PH: máximo de S a (H, P, n).** Para un sistema cerrado, adiabático y a presión exterior constante, H se conserva y dS ≥ 0, así que el equilibrio maximiza S a (H, P, n). En ese máximo las fases comparten T, P y μ, y el estado es estable en G a esa (T, P). Para una sustancia pura, h de equilibrio crece con T a lo largo de la isobara: cp > 0 en la rama, y en Tsat hay una meseta lineal en q con h″ > h′. Por eso existe a lo sumo un estado. El cálculo ubica primero h respecto de la meseta [h′, h″] y solo después resuelve T con Brent en la rama que corresponde.

**UP: sin principio de extremo.** U y P fijos no son variables naturales: mantener U constante mientras la frontera hace trabajo P dV exige intercambiar calor, así que no se invoca ningún máximo de S. La especificación reconstruye el estado interno a partir de U y n conservados con una P impuesta. El criterio es la estabilidad interna: el estado debe ser estable en G a su propia (T, P) y tener u = U/m. La unicidad se apoya en que u crece a lo largo de la isobara de equilibrio:

- en una fase, (∂u/∂T)_P = cp − P(∂v/∂T)_P ≥ 0.75·cp, medido en una malla de 400 × 11 isobaras de todo el dominio;
- en la meseta, u es lineal en q con u″ > u′.

**UV: máximo de S a (U, V, n), en sistema aislado y rígido.** Para una sustancia pura, un estado homogéneo cumple el criterio si y solo si está en la envolvente cóncava de s(u, v), lo que equivale a ser estable en G a su propia (T, P). Dentro de la campana, la envolvente es la mezcla de las dos fases saturadas. Así se calcula:

- **Candidatos:** todas las raíces en T de u_cand(T; v) = u. A cada T, u_cand es la mezcla de coexistencia si v′ < v < v″, y el estado homogéneo ρ = 1/v en caso contrario. La función es continua: en el borde de la campana ambas expresiones coinciden. **Las restricciones de u y v se resuelven a la vez**: la q que fija v es la misma que da u, no hay una fracción para cada una.
- **Búsqueda:** una malla de 301 temperaturas en [273.16, 1073.15] K y Brent en cada cambio de signo. No se toma la primera raíz.
- **Selección:** cada candidato se certifica. Si quedaran varios admisibles se elegiría el de mayor s; si sus s no se distinguen (1e-9), la respuesta es `no_convergente` con `MOTOR_ESTADO_AMBIGUO`.
- **Unicidad:** físicamente, u de equilibrio a v fijo crece con T (cv de equilibrio > 0). En todas las pruebas hay una sola raíz, también en la anomalía de densidad cerca de 4 °C, donde v′(T) no es monótona: a v fijo, al subir u, se pasa de líquido comprimido a trazas de vapor y de nuevo a líquido comprimido. Lo que la malla no puede excluir son dos raíces dentro de una misma celda de 2.7 K. El argumento físico y la prueba lo cubren; la verificación `unicidad` publica el recuento.
- **Fase de un candidato homogéneo:** fuera de la campana, la decide el lado de ρc. Comparar con la ρ′ de los ajustes etiquetaba como vapor un líquido justo en la frontera, porque los ajustes difieren ~1e-13; fue un defecto encontrado por la suite y está corregido.
- **Densidad máxima:** ρ = m/V > 1250 kg/m³, del orden de ρ(273.16 K, 1 GPa), se rechaza antes de evaluar la EOS, porque la presión saldría del dominio.

## Estabilidad

- **Una fase** (PH, UP o UV): igual que TP. Distancia al plano tangente a la T resultante, sobre las ramas monofásicas, con residuo −min TPD/P* ≤ 1e-9.
- **Coexistencia:** se comprueba la tangente común por los dos puntos saturados:

$$tm(\rho) = \frac{\rho\,[f(T,\rho) - g^*] + P^*}{\rho R T} \ge -10^{-9},\qquad g^* = g'',\ P^* = P''$$

  tm es la distancia al plano tangente por unidad de masa de la fase de prueba, en unidades de RT (Δg/RT): la escala adimensional habitual. Se anula en ρ′ y ρ″ y no debe ser negativa en ninguna otra densidad de las ramas (400 puntos por rama más refinamiento). La escala TPD/P* de H1 no sirve aquí: con Psat ~ 1 kPa, la imprecisión de 1e-7 Pa de P′ ya la saturaría. H1 conserva su escala sin cambios.
- **No es un sello:** la suite fuerza un vapor homogéneo metastable dentro de la campana y comprueba que se rechaza.

## Verificaciones nuevas o con otro significado en PH, UP y UV

| id | Residuo | Tolerancia |
| --- | --- | --- |
| `estabilidad` | una fase: −min TPD/P*; coexistencia: −min tm | 1e-9 |
| `equilibrio` (dos fases o frontera) | Maxwell, como arriba | 1e-9 |
| `presion_saturacion` (PH, UP en la curva) | \|Psat(Tsat) − P\|/P | 1e-10 |
| `energia` | \|y reconstruida − especificada\|/(RT), y = h (PH) o u = U/m (UP, UV), con y = Σ w_α y_α | 1e-10 |
| `volumen` (UV) | \|v reconstruido − V/m\|/(V/m) | 1e-10 |
| `ecuacion_estado` (una fase, PH y UP) | como en TP | 1e-12 |
| `identidad_h_u_Pv` | máximo por fase de \|h − u − Pv\|/(RT) con la P publicada | 1e-9 |
| `identidad_g_h_Ts` | máximo por fase de \|g − (h − Ts)\|/(RT), con g desde φ | 1e-12 |
| `reconstruccion_material` | \|Σβ_α − 1\| (un componente: x_α = z = 1) | 1e-12 |
| `bases_fase` | max(\|Σw − 1\|, \|Σε − 1\|), con ε_α = w_α v_α/v; el motivo da q y Q_MIN | 1e-12 |
| `unicidad` | null; el motivo describe la búsqueda de raíces | null |
| `derivadas`, `saturacion` (una fase) | como en TP | — |

`masa_molar`, `politica_fases` y `cambio_interno` funcionan igual que en TP. `cambioInterno: prohibido` sigue siendo `no_evaluable` en una consulta puntual. No se certifica ninguna transición temporal ni producción de entropía.

## Política de fase

Las restricciones se comprueban **después** de calcular el equilibrio:

- `cantidad: monofasico` con un estado estable bifásico → `invalido`, `MOTOR_ESTADO_FASE_INCOMPATIBLE`, ruta `declaracion.politica.cantidad`.
- `tiposPermitidos` que no incluye todas las fases calculadas → `invalido`, misma clave de error, ruta `…tiposPermitidos`.

No se fuerza ninguna rama metastable para cumplir una restricción.

## Cantidades y bases

- **Masa total:** en base másica, m = Σ m_i; en base molar, m = n·M con la M del modelo (18.015268 g/mol). Las dos bases reconstruyen el mismo estado; lo prueban kg, g, mol y kmol, además del par de ejemplos `uv-recipiente-rigido-bifasico` / `-molar`.
- **Escala:** escalar U, V y n juntos por 1e-3 o 1e3 no cambia T, P ni las fracciones.
- **Rechazos:** cantidad total nula o negativa, V ≤ 0, unidades de otra familia (U en kJ/kg, cantidad molar en kg) o campos de otra especificación salen con su código y ruta. Las cantidades y la energía nunca se ajustan para lograr un flash.
- **Fuera de dominio:** la ruta apunta al dato que lo provoca. Una T fuera va a `h` (PH) o a `U` (UP, UV); una P fuera va a `P` (PH, UP) o a `V` (UV).

## Evidencia

```
python tests/validar_motor_termodinamica_h3.py              # 3729 comprobaciones
python tests/validar_motor_termodinamica.py                 # 585 (regresión H0/H1)
python tests/generar_ejemplos_motor_termodinamica.py
node tests/verificar_contrato_motor_termodinamica.mjs       # 35, validador TS sobre respuestas reales
cd frontend && npm run test:motor-fundamental               # incluye verificar_entrega_h0_h1_motor.mjs
```

| Comprobación | Resultado medido |
| --- | --- |
| Coexistencia frente a la tabla 8 de IAPWS-95 (Psat, ρ′, ρ″, h′, h″, s′, s″ a 275, 450 y 625 K) | todas < 1e-8 relativo (los valores publicados tienen 9 cifras) |
| Frente a IF97, región 4 y regiones 1/2 en la curva, de 700 Pa a 16 MPa (formulación independiente ajustada a IAPWS-95) | \|ΔTsat\| ≤ 7.6 mK, \|Δh′\|, \|Δh″\| ≤ 196 J/kg |
| Otro resolvedor de Maxwell (`chemicals.iapws95_saturation`, misma EOS, otro algoritmo) | densidades iguales a < 1e-11 |
| Clapeyron: dPsat/dT por diferencias frente a (s″−s′)/(v″−v′); h″−h′ = T(s″−s′) | < 1e-6 y < 1e-10 |
| Ida y vuelta TP → PH, UP y UV en 14 estados: líquido, líquido comprimido, vapor, gas por encima de Tc, supercrítico, junto a la banda crítica y en el borde del dominio | máximo de \|ΔT/T\|, \|ΔP/P\|, \|Δv/v\|, \|Δh\|/(RT) = **2.5e-10**; misma fase y régimen |
| Coexistencia con q ∈ {0, 1e-11, 1e-6, 0.3, 0.5, 1−1e-6, 1−1e-11, 1} a 6 temperaturas (273.2 a 643 K), por PH, UP y UV. Los estados interiores se construyen con el otro resolvedor, no con el flash probado | fases correctas, q a 1e-12 + 1e-9·q, ε_v = q v″/v, u, h, s y v reconstruidos, sin cp global |
| UV en la anomalía de densidad | 1 raíz por caso; líquido → trazas de vapor → líquido al subir u |
| Rechazos (dominio por cada dato, región crítica por PH, UP y UV, cantidades, unidades, políticas, masa molar, sobreespecificación) | estado, código, ruta y propietario; con `evaluacion: null` aunque la evaluación anterior fuera válida |

Ejemplos generados desde los endpoints, con números redondos de usuario:

| Caso | Resultado |
| --- | --- |
| `ph-bifasico-1bar` (1 bar, 1500 kJ/kg) | 99.606 °C, q = 0.4795, ε_v = 0.99933 |
| `ph-vapor-sobrecalentado-10bar` (3000 kJ/kg) | vapor a 276.02 °C |
| `up-liquido-calentado-1bar` (5 kg, 1250 kJ) | líquido a 59.73 °C |
| `uv-recipiente-rigido-bifasico` y `-molar` (10 kg, 1 m³, 15 MJ) | 171.03 °C, 8.1208 bar, q = 0.4193, ε_v = 0.99352 |
| `uv-supercritico` (1 kg, 10 L, 2800 kJ) | fluido supercrítico a 472.99 °C y 252.6 bar |
| `uv-monofasico-incompatible` | `invalido`: el estado estable tiene dos fases |
| `uv-energia-bajo-el-punto-triple` (−50 kJ/kg) | `no_soportado`: exigiría T < 273.16 K (posible hielo) |

## Para Codex

- `capacidades` publica `["TP","PH","UP","UV"]`. La interfaz puede ofrecer las cuatro y leer `alternativas` en la saturación TP.
- `alternativas` tiene la forma `string[][]` del contrato: `[["P","h","composicion"],["U","P","cantidades"],["U","V","cantidades"]]`. Son los campos de cada especificación, en el orden de la tabla del contrato.
- En dos fases, `mezcla` no trae `cp` ni `cv` y cada fase sí los trae. Lo mismo vale para una fase sobre la curva (frontera); se reconoce porque trae la verificación `equilibrio`.
- Los IDs de fase son `liquido-1` y `vapor-1`, estables entre consultas.
- `fraccionMolar` = `fraccionMasica` = q. `fraccionVolumen` es distinta, y en coexistencia a baja presión casi todo el volumen es vapor.
- Nada de esto convierte una consulta guardada en condición inicial de un volumen, ni mezcla la referencia IAPWS con la relación afín manual u(T).

## Pendiente

- **Borrador del contrato `validar`/`resolver`** del ensamblaje, previo a H2/H4. El encargo lo sitúa como entrega posterior y no está en esta.
- Región crítica (Tsat > 643.86 K o estados de la banda), T > 1073.15 K y P > 100 MPa.
- H2/H4 dinámicos, mezclas (H5/H6), sólidos y la coexistencia con hielo en el punto triple.
- Las derivadas del estado bifásico (cp de equilibrio a lo largo de la meseta, compresibilidad de la mezcla) que necesitará H4 no se publican en revisión 1.
