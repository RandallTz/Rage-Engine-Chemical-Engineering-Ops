# Motor de equilibrio multifásico y ensamblaje v2 (M0–M6)

Entrega del contrato `frontend/CONTRATO_CLAUDE_MOTOR_EQUILIBRIO_MULTIFASICO.md`. Backend, núcleo,
pruebas y documentación; el frontend no se ha tocado. Sin commit ni push.

**Recarga:** hay que reiniciar el servicio (`uvicorn backend.main:app`). Hay módulos nuevos, una ruta
nueva (`GET /motor/termodinamica/diagrama`) y el despacho por `revision` en `/motor/ensamblajes/*`.
`backend/main.py` solo recibe adiciones.

## 1. Qué cambia para quien integra

| Superficie | Revisión 1 (sin cambios obligatorios) | Ampliación aditiva |
|---|---|---|
| `GET /motor/termodinamica/capacidades` | `agua-iapws95` sigue el primero e igual | + `mezcla-ideal`, `nrtl-chemsep`, `nrtl-lle-agua-butanol`, `agua-iapws95-hielo-ih` |
| `POST /motor/termodinamica/evaluar` | igual para `agua-iapws95` | mismos tipos (`SolicitudEstado`/`RespuestaEstado`) con los modelos nuevos; fases `solido` y dos `liquido` |
| `GET /motor/termodinamica/diagrama` | — | nuevo: diagrama P–T del cierre con hielo |
| `GET /motor/ensamblajes/capacidades` | sin parámetro = revisión 1 idéntica | `?revision=2` → `CapacidadesEnsamblajeV2` |
| `POST /motor/ensamblajes/{validar,resolver}` | cuerpo con `revision: 1` (o sin ella) como antes | cuerpo con `revision: 2` → `SolicitudEnsamblajeV2` |

Tipos de la revisión 2: `docs/contratos/contratoEnsamblajeV2.ts` (importa los tipos de revisión 1 del
frontend; no los modifica). Los ejemplos de `docs/ejemplos/motor-v2/` (`motor-ensamblaje-v2-*` y
`motor-termodinamica-{mezcla,nrtl,lle,hielo}-*`; en un subdirectorio para que los lectores de revisión 1,
que recorren `docs/ejemplos/motor-ensamblaje-*`, sigan viendo solo respuestas de revisión 1) salen de los endpoints
(`python tests/generar_ejemplos_motor_ensamblaje_v2.py`) y se compilan y validan con
`node tests/verificar_contrato_ensamblaje_v2.mjs`.

### M0: incoherencia `presionPrescrita`

En revisión 1 (`backend/motor_ensamblaje.py`), `formulacionEnergia.presionPrescrita` debe concordar con la
frontera; ausente, se conserva el comportamiento v1. Código `MOTOR_ENS_PRESION_PRESCRITA`:
`false` con frontera `presion_prescrita`; `true` con frontera rígida sin `presionRestriccionId`; `true` sin
relación; no booleano → `invalido`. Pruebas en `tests/validar_motor_ensamblaje.py` §12.

## 2. Fundamento: potenciales, referencias y fases

Cada paquete se construye desde una energía de Gibbs explícita por especie y fase; h, s, v, μ salen de esa
función y sus derivadas, nunca de fuentes sueltas.

**Mezclas** (`core/mezclas_datos.py`, `core/mezclas.py`):

- Gas ideal por especie: `h = s = 0` a 298.15 K y P0 = 1e5 Pa, `cp_ig` de Poling (5.ª ed.). Vapor de mezcla
  ideal (válido hasta 5e5 Pa, el dominio publicado).
- Líquido puro: `g_L = g_ig0(T) + R T ln(Psat/P0) + v_L (P − Psat)` con Psat de Wagner (Poling; McGarry para
  algunas) y `v_L` constante de `thermo` a 298.15 K. Así g_L es coherente con Clapeyron: el calor de
  vaporización es el que implica Psat(T), no un dato aparte. Incompresible.
- Exceso: NRTL con `τ_ij = a_ij + b_ij/T`. `h^E = g^E − T ∂g^E/∂T`, `s^E = −∂g^E/∂T`; la derivada en T por
  paso complejo (exacta a precisión de máquina). El calor de mezcla entra en h y s: no se usa γ solo para el
  equilibrio.
- `μ_i` molar (J/mol); estado estándar común: gas ideal puro a T y P0. Las propiedades publicadas en
  `EvaluacionEstado` siguen siendo específicas másicas, como en revisión 1.
- Referencia publicada: `gas-ideal-298.15K-1bar-h0-s0`. El agua IAPWS-95 usa otra (u = s = 0 del líquido en
  el triple): una corriente entre volúmenes con referencias distintas se rechaza
  (`MOTOR_ENS_REFERENCIAS_INCOMPATIBLES`); no se convierten referencias.

**Hielo** (`core/hielo_ih.py`): energía de Gibbs de IAPWS R10-06(2009) con la constante s0 "IAPWS-95": el
hielo comparte la referencia del fluido sin desplazamiento, así que g del hielo y g de IAPWS-95 se comparan
directamente.

**Fases**: cada fase presente tiene ID (`vapor-1`, `liquido-1`, `liquido-2`, `solido-1`) separado del tipo.
En consultas puntuales los líquidos se numeran por densidad másica decreciente; en una trayectoria los IDs
se mantienen por continuidad de composición, no por reordenar densidades. Una fase ausente no tiene
composición: no se publica y no se le impone igualdad de μ (las especies ausentes llevan `μ = null`).

## 3. Algoritmos de equilibrio

**TP** (`Sistema.equilibrio_TP`): fase única de menor G → prueba de plano tangente (vapor por mínimo
analítico; líquido en malla del simplex con refinamiento) → si algún `tm < −1e-14`, se añade esa fase y se
minimiza G (SLSQP) → pulido Newton en `ln n` con la fase más abundante como resto → se repite (hasta 3
fases). Certificación final: `tm ≥ −1e-9` sobre vapor y líquido con la μ común, `max|μ_i^α − μ_i^β|/(RT) ≤
1e-10`. Si el reparto no converge (p. ej. a 1e-12 K de una frontera la fase nueva quiere anularse), se
descarta y el conjunto anterior se certifica por la prueba de plano tangente. Si nada certifica, la
respuesta es `no_convergente`; nunca se publica una raíz sin certificar.

Robustez añadida en esta entrega: fases que la minimización vacía o lleva a la composición de otra del mismo
tipo se retiran o funden antes de pulir; si con todas las fases no hay solución (tres fases de un binario
fuera de su T invariante) se prueban los subconjuntos y se queda el de menor G que converge.

**PH/UP**: Brent en T sobre la isobara de equilibrio (h y u crecen con T). En un salto (puro, azeótropo
exacto, LLV de un binario) se resuelve la meseta: composiciones de ambos lados del salto, punto invariante
pulido por Newton en (ln T, composiciones) cuando hay C + 1 fases, y cantidades por mínimos cuadrados no
negativos con la restricción de energía. Certificado igual que TP.

**TV/UV**: TV por Brent en ln P (con meseta en P si la hay); UV por búsqueda holgada en T con TV y Newton
exacto en (T, ln P, ln n^α). Un líquido incompresible que llena el volumen no determina P: `no_soportado`.

**Agua con hielo** (`core/agua_slv.py`): TP = fase de menor g; sobre una curva o en el triple, TP no
determina el reparto (`MOTOR_ESTADO_SATURACION_INDETERMINADA`; en el triple la única alternativa es UV).
PH/UP siguen la secuencia de fases estables al subir T, con mesetas por palanca. UV = máximo de S entre
todas las candidatas que cumplen U y V (una fase, dos fases sobre cada curva, triple), certificado además
con g mínima a su T, P. PH en el triple (tres fases, dos ecuaciones) es indeterminado.

## 4. Paquetes, datos y procedencia

| Paquete | Especies | Datos binarios | Dominio | Operaciones |
|---|---|---|---|---|
| `mezcla-ideal` 1 | agua, etanol, metanol, benceno, tolueno, 1-butanol, acetato de etilo | ninguno (Raoult + Poynting) | T envolvente de las especies (≤ 0.9 Tc), P 100–5e5 Pa | TP, PH, UP, UV (+ TV interno) |
| `nrtl-chemsep` 1 | las mismas | ChemSep NRTL vía `thermo.interaction_parameters.IPDB`; par ausente → `MOTOR_ESTADO_PARAMETRO_AUSENTE` (no se rellena con cero) | ídem | ídem |
| `nrtl-lle-agua-butanol` 1 | agua, 1-butanol | ajuste propio (abajo) | T 293–373 K | ídem |
| `agua-iapws95-hielo-ih` 1 (solo estático) | agua | — | T 200–300 K, P 0.1 Pa–100 MPa | TP, PH, UP, UV |

**LLE agua/1-butanol.** Ningún conjunto de parámetros instalado reproducía la solubilidad mutua; se
ajustó NRTL (`a12 = 3.0275, b12 = 181.98 K, a21 = 11.653, b21 = −3221.2 K, α = 0.4396`) a los valores
recomendados de IUPAC-NIST Solubility Data Series vol. 15 (Hefter, evaluador; 1984) en 293, 313, 333, 353 y
373 K. Validación en 298, 323, 343 y 363 K, no usadas en el ajuste: error máximo 0.49 g/100 g (ajuste
0.60). Reproducible: `python tests/ajuste_nrtl_lle_agua_butanol.py`. El paquete no se ofrece fuera de
293–373 K ni para otras especies.

**Hielo.** IAPWS R10-06(2009) (coeficientes de su Tabla 2, comprobación con su Tabla 6: error máximo
3.8e-10). Las curvas de fusión y sublimación se calculan del propio cierre (g iguales); las ecuaciones de
IAPWS R14-08(2011) se usan solo como contraste independiente.

## 5. Ensamblaje v2

Estado por volumen: cantidades `n_i` (mol) y `U` (rígido) o `H` (presión prescrita, `dH/dt = J_E + V dP/dt`).
El reparto entre fases es algebraico en cada evaluación del lado derecho; no se integran cantidades de fase.

- **Corrientes**: un ID, una transferencia por componente y energía, sumada al receptor y restada al
  donante como el mismo número (cancelación por identidad). Donante según el signo del caudal. Modos
  `total_desde_donante` (composición del donante) y `por_componente`. Extracción por extremo:
  `mezcla_homogenea` o `fase` (`liquido` con dos líquidos exige `criterio`: `mayor_densidad` |
  `menor_densidad`; sin él la detención es `fase_ambigua`). Corriente exterior con `estadoExterior` TP y
  composición propia.
- **Calor**: `impuesto` o `conductancia` (`Q = G (T_a − T_b)`), un valor compartido con signos opuestos en
  contactos internos. Un volumen no adiabático sin intercambio declarado queda `incompleto`
  (`MOTOR_ENS_Q_PENDIENTE`): un calor ausente no es cero.
- **Recuento**: emparejamiento bipartito estructural; los datos pendientes se emparejan al final para
  señalar el origen exacto del pendiente. La relación del donante se divide en
  `transferencia.<s>.composicion` y `.entalpia` (dos incógnitas, dos ecuaciones).
- **Integración**: RK45 con flashes con semilla en las etapas; cada muestra se certifica con la prueba de
  estabilidad completa.

### Eventos (M6)

La vigilancia es **puntual, no continua**: en cada paso aceptado se comprueba el conjunto de fases en 3 puntos
interiores y el extremo; si cambia, bisección del instante, reintegración hasta él y reinicio. Una
transición que aparece y desaparece entre dos puntos vigilados de un mismo paso no se detecta; el paso
máximo limita ese riesgo pero no lo elimina. Las pruebas comparan los tiempos de burbuja y rocío de un
calentamiento cerrado con flashes estáticos independientes: acuerdo < 1e-5 relativo, también con 2
muestras (eventos dentro de un paso).

### Residuos publicados

- `global.materia.<c>`: `max_t |Σ_v n_v,i − n_i(0) − ∫ ṅ_ext,i dt| / (atol + rtol · max Σ n)`, tolerancia 10.
  La escala suma solo cantidades (corregido en esta entrega: antes sumaba también energías).
- `global.energia`: U de los estados certificados frente a `∫ E_ext dt − Σ W_v`, con `W_v = [P V] − ∫ V dP`.
- `mecanica.<v>.trabajo`: el trabajo integrado `∫ P dV/dt` (dV/dt por diferencia centrada) frente al trabajo
  por partes; tolerancia 1e-5 relativa (acuerdo medido ~2e-6).
- `estado.<v>.energia` y `estado.<v>.volumen`.

### Segunda ley (M6)

`S_gen(t) = Σ_v S_v(t) − S(0) − ∫ (Σ ṅ s + Q/T_frontera)_ext dt` en las muestras certificadas: debe ser ≥ 0 y
no decreciente. Cada intercambio exterior necesita `temperaturaFronteraId`; si falta, `no_evaluable` (no se
sustituye por la T del fluido). Separado de la estabilidad local/global y de los residuos de balance. Las
pruebas incluyen un control negativo: calor de una frontera a 400 K entrando a un vapor que la supera
(462 K) → `no_cumple`.

## 6. Matriz de capacidades por hito

| Hito | Publicado | Verificación principal (`tests/validar_motor_ensamblaje_v2.py`) |
|---|---|---|
| M0 | guarda `presionPrescrita`; revisión 2 tipada y aditiva | §0; v1 §12 |
| M1 | mezcla ideal TP/PH/UP/UV, potenciales, estabilidad | §1: K = Psat e^{v_L(P−Psat)/RT}/P < 1e-9; puro = especie ausente; trazas; orden; extensividad; `dH = ∫T dS` |
| M2 | NRTL ChemSep; energía con h^E; dinámica de un volumen | §2: thermo.nrtl 1e-12; Gibbs–Duhem; h^E; azeótropo etanol–agua 78.07 °C, x = 0.881 (lit. 78.15 °C, 0.894); §3 eventos y H = H0 + Q t |
| M3 | varios volúmenes, corrientes internas, contacto | §4: U total constante y S creciente; m = m0 ∓ F t; control negativo de materia; binario acoplado |
| M4 | LL y LLV (agua/1-butanol), decantador | §5: IUPAC (ajuste y validación); heteroazeótropo 94.13 °C (lit. 93.0 °C, ±2 K); homogéneo rechazado por tm; meseta LLV por PH y UV; IDs continuos; extracción de la fase orgánica |
| M5 | hielo Ih estático, SL/SV/triple, diagrama | §6: Tabla 6; R14-08 (sublimación ≤ 6.5e-5, fusión ≤ 2.5e-5 relativo); triple 273.16 K, 611.6548 Pa; fusión normal 273.152519 K; calor de fusión 333.43 kJ/kg; UV en el triple |
| M6 | eventos puntuales documentados; segunda ley | §3: eventos con 2 muestras; `no_evaluable` sin T de frontera; control negativo |

No soportado (publicado en `noSoportado` o rechazado con diagnóstico): transferencia selectiva, reacción,
electrolitos, membranas, nucleación, capilaridad, momento; corrientes entre paquetes de referencia
distinta; presión con escalones; hielo en volúmenes dinámicos; sólidos en mezclas (solubilidad, SLE,
eutécticos y soluciones sólidas necesitan paquetes y datos propios); hielos II, III, V… (P > 100 MPa).

## 7. Qué puede verificar el lector sin repetir la EOS

- `validarRespuestaEstado` del frontend ya cubre: reconstrucción de composición, propiedades y bases de
  fracción (β, χ, ε), `h = u + Pv`, especificaciones respetadas, alcance de estabilidad frente a la
  capacidad, residuos ≤ tolerancia. Todos los estados de los ejemplos v2 (36 por volumen y 7 puntuales) lo
  pasan sin modificar el lector.
- Con las series v2: `Σ_v n_v,i` frente a las corrientes exteriores; `U_A + U_B` en un contacto aislado;
  `red.Sgen` monótona; continuidad de IDs de fase; que los eventos coinciden con cambios en `fases`.
- Alcance de estabilidad del hielo: una fase no evaluable a esa T, P (hielo sobre 273.16 K, vapor sin raíz,
  líquido bajo 235 K) solo figura en `alcance` si las curvas del mismo cierre la dejan fuera de la región
  estable; el `motivo` de la verificación lo dice.

## 8. Límites conocidos

- Burbuja o rocío a ~1e-12 K y composición casi azeotrópica: el reparto es degenerado (x ≈ y) y el motor
  puede negarse a certificar (`no_convergente`) en lugar de publicar un estado dudoso.
- Heteroazeótropo agua/1-butanol ~1.1 K por encima de la literatura: el ajuste es solo de LLE; el VLE usa
  los mismos parámetros.
- UV de mezclas: ~0.5–6 s por estado (Newton con búsqueda previa); TP 4–7 ms con semilla.
- Hielo: solo estático; T 200–300 K; el líquido sobreenfriado solo es candidato con T ≥ 235 K.
- Vapor ideal: P ≤ 5e5 Pa en mezclas.

## 9. Pruebas y resultados

| Prueba | Resultado |
|---|---|
| `python tests/validar_motor_ensamblaje_v2.py` (secciones 0–6) | OK, 114 comprobaciones |
| `python tests/validar_motor_termodinamica.py` (H1) | OK, 585 (catálogo actualizado con los modelos aditivos) |
| `python tests/validar_motor_termodinamica_h3.py` (H3) | OK, 3729 |
| `python tests/validar_motor_ensamblaje.py` (v1) | OK, 245 |
| `node tests/verificar_contrato_ensamblaje_v2.mjs` | OK: 6 pares compilados; 36 estados por volumen y 7 puntuales validados |
| `node tests/verificar_contrato_ensamblaje.mjs` (v1) | OK: 13 pares, 175 estados (ejemplos v1 sin cambios) |
| `node tests/verificar_contrato_motor_termodinamica.mjs` | OK |
| `npm run test:motor-fundamental` (frontend, sin modificar) | OK |

## 10. Archivos

Nuevos: `core/mezclas.py`, `core/mezclas_datos.py`, `core/paquetes_volumen.py`, `core/ensamblaje_red.py`,
`core/hielo_ih.py`, `core/agua_slv.py`, `backend/motor_mezclas.py`, `backend/motor_ensamblaje_v2.py`,
`backend/motor_hielo.py`, `docs/contratos/contratoEnsamblajeV2.ts`, `tests/solicitudes_v2.py`,
`tests/ajuste_nrtl_lle_agua_butanol.py`, `tests/validar_motor_ensamblaje_v2.py`,
`tests/generar_ejemplos_motor_ensamblaje_v2.py`, `tests/verificar_contrato_ensamblaje_v2.mjs`, ejemplos.
Modificados (aditivo): `backend/main.py`, `backend/motor_termodinamica.py`, `backend/motor_ensamblaje.py`,
`tests/validar_motor_termodinamica.py` (catálogo con los modelos nuevos), `tests/validar_motor_ensamblaje.py`.

## Fuentes

- IAPWS R6-95(2018), IAPWS-95.
- IAPWS R10-06(2009), Revised Release on the Equation of State 2006 for H2O Ice Ih — https://www.iapws.org/relguide/Ice-Rev2009.pdf
- IAPWS R14-08(2011), Revised Release on the Pressure along the Melting and Sublimation Curves of Ordinary Water Substance — https://www.iapws.org/relguide/MeltSub.html
- IUPAC-NIST Solubility Data Series vol. 15, Alcohols with Water (Barton ed., Hefter evaluador; Pergamon 1984), 1-butanol + agua.
- Tabla de azeótropos heterogéneos (Universidad de Edinburgh) — https://homepages.ed.ac.uk/jwp/Chemeng/azeotrope/hetero.html — agua/1-butanol 93.0 °C.
- Gmehling et al., Azeotropic Data: etanol/agua 78.15 °C, x_EtOH ≈ 0.894 a 1 atm.
- ChemSep NRTL vía `thermo` (Caleb Bell), `thermo.interaction_parameters.IPDB`; `thermo.nrtl` como contraste.
- B. E. Poling, J. M. Prausnitz, J. P. O'Connell, The Properties of Gases and Liquids, 5.ª ed.
