# UNIFAC en el motor (F0, U0–U8)

Entrega de `frontend/CONTRATO_CLAUDE_UNIFAC_MOTOR.md`, con el formato de `frontend/COORDINACION_CLAUDE_CODEX_MOTOR.md`.
Cambios en núcleo, backend, pruebas, contratos canónicos y `docs/`. No se tocó `frontend/`, `/laboratorio` ni
`thermodynamics/proveedor.py`. Sin commit, push ni despliegue. No se actualizó ninguna dependencia ni se modificó
ningún archivo de datos.

**Recarga:** reiniciar el servicio (`uvicorn backend.main:app`). Después, `GET /motor/termodinamica/capacidades`
debe listar `unifac-original-public`, `unifac-dortmund-public` y `unifac-original-lle-public`, y
`GET /motor/ensamblajes/capacidades?revision=2` debe incluir esos tres paquetes con el campo `coberturaGrupos`.
Las rutas no cambian.

## 1. Estado por hito

| Hito | Estado | Evidencia |
|---|---|---|
| F0 arranque concurrente | **Backend verificable** | Fallo reproducido (7 de 8 arranques en frío con hilos) y corregido; 0 fallos en las rondas de la suite (§2) |
| U0 auditoría | **Backend verificable** | Cobertura de las 7 especies y de los 21 pares en ambas variantes; decisiones de datos (§3) |
| U1 adaptador original | **Backend verificable** | ln γ frente a thermo ≤ 3e-15; h^E, s^E, Cp^E; identidades (§4) |
| U2 TP y estabilidad | **Backend verificable** | L–V frente a flash γ–φ independiente con N = 2, 4, 5 y 7; L–L con N = 2 y 4; L–L–V con N = 5 (§5) |
| U3 energía e inversiones | **Backend verificable** | PH/UP/UV con N = 2, 5 y 7; meseta L–L–V; UV del líquido lleno rechazado (§6) |
| U4 dinámica | **Backend verificable** | Calentamiento con N = 2, 4 y 5; rígido; red con inversión y especie entrante; mezcla adiabática; extracción por fase; política monofásica; datos ausentes (§7) |
| U5 API, diagramas y metadatos | **Backend verificable** | Tres rutas, `coberturaGrupos`, códigos propios, huella, concurrencia (§8) |
| U6 Dortmund | **Backend verificable** | Paquete propio; las pruebas U1–U5 repetidas en lo que aplica (§9) |
| U7 tabla dedicada a ELL | **Backend verificable**, con cobertura parcial | 6 de 7 especies. El **metanol queda bloqueado por datos**: la tabla no tiene el grupo CH3OH (§10) |
| U8 entrega | este documento, ejemplos, verificador, benchmark y regresión (§11–§14) | |

Ninguna fila pasa a «Integrado y comprobado»: falta la integración de Codex.

## 2. F0 · Arranque concurrente

**Reproducción.** Con 8 hilos y un proceso recién arrancado, 7 de 8 arranques fallaban. Los errores eran:

- `PiecewiseHeatCapacity ... append`, al cargar perezosamente las tablas de `chemicals`;
- `KeyError: 'ChemSep NRTL'`, al cargar perezosamente la IPDB de `thermo`.

Esos cargadores rellenan variables globales y no son seguros entre hilos.

**Corrección.** Se añadió el cerrojo reentrante `core/mezclas_datos.CARGA_DATOS`. Lo toman:

- `especie(cas)`;
- `parametros_nrtl`;
- `_pares_nrtl` (en las capacidades v2);
- la carga y la consulta de las tablas UNIFAC (`core/unifac.tablas` y `asignacion`).

No cambia ningún valor: solo ordena la primera carga.

**Verificación:**

- tres rondas de 12 hilos sin errores;
- en `tests/validar_motor_unifac.py`, sección 5: proceso nuevo, 12 hilos con 12 mezclas distintas (UNIFAC y NRTL), dos rondas. Los resultados concurrentes son **iguales bit a bit** a los obtenidos aislados en el mismo proceso.

## 3. U0 · Auditoría y decisiones

### 3.1 Datos fijados

| Variante | Ecuaciones | Subgrupos (R, Q) | Interacciones | Asignaciones |
|---|---|---|---|---|
| `original` | Fredenslund, Jones y Prausnitz (1975). Combinatorio de Staverman–Guggenheim con z = 10; Ψ = exp(−a_mn/T) | `UFSG` (thermo 0.6.1) | `UNIFAC original interaction parameters.tsv`, sha256 `2599fa3a…` | DDBST (`DDBST UNIFAC assignments.tsv`, sha256 `2ce711b9…`), modelo `UNIFAC` |
| `dortmund` | Weidlich y Gmehling (1987). Combinatorio con r^(3/4); Ψ = exp(−(a + bT + cT²)/T) | `DOUFSG` | `UNIFAC modified Dortmund interaction parameters.tsv` (DOUFIP2016), sha256 `0826be…` | DDBST, modelo `MODIFIED_UNIFAC` |
| `lle` | Magnussen, Rasmussen y Fredenslund (1981): mismas ecuaciones que la original | `LLEUFSG` | `UNIFAC LLE interaction parameters.tsv` | Traducción de la asignación DDBST original (§10) |

Todo procede de los archivos que distribuye `thermo` 0.6.1. Los sha256 completos están en
`coberturaGrupos.datos` y en la huella.

**Uso de `thermo`.** Se leen sus tablas, pero no se usan sus objetos `UNIFAC` para calcular: mutan T y x
internamente y no son seguros entre hilos. La implementación propia (`core/unifac.py`) es vectorizada e
inmutable, y admite T compleja para derivar por paso complejo. La implementación de `thermo` se usa como
**contraste independiente** en las pruebas.

**Datos descartados:**

- `thermo` carga también UNIFAC 2.0 (`UF2IP`), cuyos parámetros proceden de «matrix completion». No se usa,
  como pide el contrato.
- Tampoco se usa UNIFAC para completar pares NRTL ausentes.

### 3.2 Cobertura del catálogo (7 especies)

| Especie | original | dortmund | lle |
|---|---|---|---|
| agua | H2O | H2O | H2O (17) |
| etanol | CH3 + CH2 + OH | CH3 + CH2 + OH(P) | CH3 + CH2 + OH |
| benceno | 6 ACH | 6 ACH | 6 ACH |
| tolueno | 5 ACH + ACCH3 | 5 ACH + ACCH3 | 5 ACH + ACCH3 |
| 1-butanol | CH3 + 3 CH2 + OH | CH3 + 3 CH2 + OH(P) | CH3 + 3 CH2 + OH |
| acetato de etilo | CH3 + CH2 + CH3COO | ídem | CH3 + CH2 + CH3COO (25) |
| metanol | CH3OH | CH3OH | **sin grupo** (§10) |

Entre los grupos principales presentes no falta ninguna interacción dirigida, en ninguna de las tres variantes.
Así, cualquier subconjunto de especies con asignación queda cubierto. Esto se publica como dato y se
comprueba: `coberturaGrupos.interaccionesDirigidasFaltantes` es una lista vacía.

### 3.3 Decisiones

- **IDs de paquete:** `unifac-original-public`, `unifac-dortmund-public` y `unifac-original-lle-public`, versión `1`
  (los propuestos por el contrato). La versión es la del paquete. La edición de los datos va en la huella.
- **Variante, tablas y asignaciones son inseparables.** Cada paquete fija su variante. Las asignaciones de una
  variante no se usan con las tablas de otra.
- **Datos ausentes:** una interacción ausente entre dos grupos principales presentes es un diagnóstico, nunca un
  cero. Dentro de un mismo grupo principal a = 0 por definición del modelo. Un a_mn = 0 publicado en la tabla es un
  dato y se usa como tal (sección 5 de la suite).
- **Evidencia:** L–V y L–L se publican como `cualitativa` en los tres paquetes. Son predicciones por
  contribución de grupos y ningún parámetro se ajustó aquí, aunque algún punto coincida con la literatura.
  Esto se aplica también a la tabla ELL.

## 4. U1 · Adaptador y coherencia local

`core/unifac.LiquidoUNIFAC(cas, variante)`:

- `lngamma`, `lngamma_lote` y `gE_RT` son finitos a dilución infinita (x_i = 0), con lnΓ de los puros
  precalculados;
- `subconjunto(idx)` reutiliza tablas y asignaciones;
- `identidad()` entra en la huella: variante, sha256 de las tablas, asignaciones por CAS ordenadas, R y Q de los
  subgrupos usados y valores de las interacciones usadas.

`core/mezclas.Sistema` integra el adaptador:

- `_modelo_sub` usa `subconjunto` para las especies activas;
- `dgE_dT` (paso complejo) es el mismo que para NRTL;
- con una sola especie se usa el líquido ideal (g^E = 0).

| Prueba | Resultado |
|---|---|
| ln γ frente a `thermo.unifac.UNIFAC.from_subgroups` (mismas tablas), N = 2 a 7, 15 puntos por variante | ≤ 3e-15 (original y Dortmund); 3.8e-15 (LLE, N = 6) |
| h^E por paso complejo frente a `HE()` de thermo | ≤ 1e-8 relativo |
| s^E frente a `SE()` y Cp^E = −T ∂²g^E/∂T² frente a `CpE()` (N = 4) | ≤ 1e-7 y 1e-5 relativo |
| Gibbs–Duhem, N = 7, direcciones aleatorias | < 1e-7 |
| ∂g^E/∂T por paso complejo frente a diferencias centradas | < 1e-6 relativo |
| ln γ_i = 0 en la especie pura; arrays de solo lectura; subconjunto igual a reconstruir | exacto |

## 5. U2 · TP, estabilidad y reparto

Referencia independiente: flash γ–φ por sustitución sucesiva con Rachford–Rice, usando las γ de `thermo` y las
mismas Psat y Poynting del paquete; para L–L, isoactividad con γ de `thermo`. El motor, en cambio, minimiza G y
certifica con la prueba del plano tangente.

| Caso (1 atm) | Resultado |
|---|---|
| etanol–agua a 352 y 355 K | L–V frente a la referencia a 1e-8 en β, x e y; los estados monofásicos coinciden |
| N = 4 (benceno, tolueno, etanol, metanol) a 346 K; N = 5 a 344 K; N = 7 a 351 K, equimolares | L–V a 1e-8 |
| N = 5 (benceno, tolueno, etanol, metanol, agua) a 341 K | **L–L–V** certificado (tm y μ ≤ tolerancias) |
| agua/1-butanol a 293–353 K | L–L frente a isoactividad a 1e-8 |
| N = 4 (agua, etanol, acetato, metanol), 300 K, z = (0.7, 0.04, 0.24, 0.02) | L–L frente a isoactividad a 1e-8 |
| Ausencias, trazas (1e-6, 1e-9, 1e-12), escala (1e-6 y 1e6), 3 permutaciones, semillas de flash | igual que con NRTL: mismo estado y misma huella; reconstrucción por especie < 1e-9 relativa |
| Estabilidad general (N ≥ 4) | determinista con la semilla fija; el homogéneo L–L se rechaza con tm < 0 |
| Tope de fases y T fuera del dominio común | rechazos `tope_fases` y `fuera_de_dominio` |

**Contraste experimental (predicción, sin ajuste).** Solubilidad mutua de agua/1-butanol en g/100 g (butanol en
la fase acuosa / agua en la fase orgánica) frente a IUPAC-NIST SDS vol. 15:

| T (K) | IUPAC | original | Dortmund | LLE |
|---|---|---|---|---|
| 293.15 | 7.8 / 20.0 | 7.33 / 20.56 | 11.19 / 11.67 | 6.92 / 21.62 |
| 298.15 | 7.4 / 20.3 | 7.62 / 20.69 | 11.01 / 11.82 | 7.21 / 21.76 |
| 313.15 | 6.6 / 21.4 | 8.49 / 21.12 | 10.67 / 12.50 | 8.12 / 22.21 |
| 323.15 | 6.4 / 22.4 | 9.10 / 21.43 | 10.57 / 13.12 | fuera del dominio |
| 353.15 | 7.0 / 27.5 | 10.93 / 22.42 | 10.77 / 15.81 | fuera del dominio |

- La **original** acierta a 293–298 K, con un error inferior a 0.6 g/100 g, y empeora con T.
- La **Dortmund** acerca demasiado las fases.
- La **tabla ELL** no mejora este par.

Se publica tal cual; no se reajusta nada.

### 5.1 Corrección compartida: reintento del TP junto a un punto invariante

Al barrer agua/butanol con UNIFAC original apareció una franja de unos 1e-6 K, justo por encima del
heteroazeótropo (366.1793 K a 1 atm con z = 0.75), en la que `equilibrio_TP` no certificaba (tm = −3.8e-8). La
secuencia de adición de fases arrancaba desde el vapor y se quedaba en V + L_org: la fase de prueba acuosa tenía
un tm del orden de 1e-8 y la minimización de 3 fases la anulaba.

Ahora, **solo si la certificación falla**, se repite la secuencia desde las demás fases únicas candidatas y se
acepta únicamente un estado certificado. Con esto la franja queda resuelta: L–L hasta T_het y V–L desde ahí. El
camino normal no cambia: certifica al primer intento y da los mismos números (§13).

### 5.2 Corrección compartida: semillas del reparto cuando la fase nueva es incipiente

Caso: tabla ELL, N = 6 equimolar a 300 K. La prueba de estabilidad daba tm = −0.012, pero `_minimizar_G`
volvía a la solución trivial, en la que la fase nueva se funde con la existente. El reparto de equilibrio es
pequeño (la fase acuosa ocupa el 0.5 % del inventario) y la semilla del 10 % lo sobredimensiona.

Ahora, **solo si el primer intento colapsa**, se reintenta con la fase nueva ya formada:

- fracciones β = 1e-3, 1e-4, 0.05, 0.2 y 0.5 del inventario, con la composición de prueba;
- sin superar el 90 % de la fase donante.

El caso queda certificado (tm y μ ≈ 3e-15) y coincide con la isoactividad independiente. El camino normal no
cambia.

## 6. U3 · Energía e inversiones

| Prueba | Resultado |
|---|---|
| g = h − T s = Σ x μ (N = 4) | < 1e-9 relativo |
| Entalpías parciales molares frente a h_i − R T² ∂ln γ_i/∂T (diferencias de H·n) | < 1e-6 relativo |
| h^E, s^E y Cp^E de la fase frente a thermo | ver §4 |
| PH, UP y UV con N = 2 (355 K), 5 (341 K, L–L–V) y 7 (351 K) | T < 1e-6 K; H, V y composición de un único reparto; mismo conjunto de fases |
| agua/butanol PH entre 360 y 380 K (meseta del heteroazeótropo) | H exacta y estado estable |
| UV del líquido incompresible lleno (N = 5) | rechazo `no_soportado`: la presión no es identificable |

El calor de mezcla entra una sola vez: está en h de la fase (h_i^puro + h^E).

## 7. U4 · Dinámica

Mismo `Sistema` y mismo coordinador que con ideal y NRTL. No hay ninguna rama por paquete.

| Caso | Resultado |
|---|---|
| Calentamiento a P prescrita (100 W) con N = 2, 4 y 5 | H = H0 + Q t; burbuja frente al flash estático a 1e-5 relativo; certificado; `procedenciaModelo` con la huella UNIFAC |
| Rígido L–V con N = 4 | U = U0 + Q t, V constante, certificado |
| Dos volúmenes con N = 5: corriente con caudal negativo (el donante es B), contacto térmico, agua que entra en A desde cero | conservación por especie < 1e-10; composición del donante conservada; segunda ley cumplida |
| Mezcla adiabática isobara etanol/agua | H total constante; el calor de mezcla cambia T; S_gen ≥ 0 |
| Extracción de vapor hasta agotarlo | detención terminal `fase_ausente` |
| Política monofásica | detención en la burbuja (`MOTOR_ENS_DETENIDO_CAMBIO_FASE_PROHIBIDO`), vapor naciente < 1e-8 y trayectoria **certificada** (ver §7.1) |
| Asignación ausente simulada | `MOTOR_ENS_UNIFAC_ASIGNACION_AUSENTE`, sin resultados |

### 7.1 Corrección compartida: dV/dt en una arista de cambio de fase

Con la política monofásica, las trayectorias que se detenían en la burbuja salían «no certificadas», también
con ideal y NRTL (el defecto ya existía): `mecanica.A.trabajo` daba 726 frente a una tolerancia de 1.

**Causa.** El trabajo se integra con dV/dt calculado por diferencia centrada de V(H, P, n). A menos de ε de la
arista, V(t + ε) ya contiene vapor, y el líquido incompresible parecía expandirse. Cuando la trayectoria cruza la
arista, ese error se compensaba con la franja del otro lado; cuando se detiene en ella, no.

**Corrección** (`core/ensamblaje_red._dVdt`). Si alguno de los puntos de la diferencia tiene otro conjunto de
fases que el del **tramo que se integra** (`firmas_tramo`), se usa la diferencia de tres puntos del lado que
conserva ese conjunto.

| Paquete | Residuo antes | Residuo ahora |
|---|---|---|
| ideal | 726 | certifica |
| UNIFAC | 726 | certifica |
| NRTL | 726 | ~1.1, todavía por encima de la tolerancia de 1 |

**Lo que queda.** El residuo restante es P·Δv·n de la fase naciente entre la arista real y t_e. La localización
tiene una resolución de 1e-9·tf (`core/ensamblaje_red.RES_EVENTO`).

**Intento de afinarla a 1e-12·tf.** Con NRTL sí baja el residuo a 0.06. Pero la muestra publicada en t_e queda
a veces sin la fase naciente (unos 1e-11 mol) y el evento sale sin `faseIds`. Pasa al cruzar la arista y, con
ideal y UNIFAC, también al detenerse en ella.

**Causa medida.** La bisección y la publicación evalúan el mismo y con el mismo flash sembrado, pero con semillas
distintas (estado al inicio del paso frente a muestra anterior). Para fases nacientes de ese tamaño no deciden
igual. Se revirtió a 1e-9. Un arreglo correcto exige que la bisección use el mismo criterio que la publicación.

Se documenta como límite (§15).

## 8. U5 · API, diagramas y metadatos

### 8.1 Rutas y campos

No hay rutas nuevas. Todo es aditivo.

- **`GET /motor/termodinamica/capacidades`**: tres modelos más, con `componentesCAS` igual a las especies con
  asignación en esa variante. El paquete LLE publica `dominio.T = [283.15, 313.15]`.
- **`GET /motor/ensamblajes/capacidades?revision=2`**:
  - los tres paquetes, con combinaciones L–V y L–L `cualitativa`;
  - **sin `pares`**: no se publican pares moleculares porque el modelo no los usa;
  - con **`coberturaGrupos`**, de tipo `CoberturaGrupos` (`docs/contratos/contratoContribucionGrupos.ts`):
    variante, datos con sha256, subgrupos por especie (id, nombre, grupo principal, cuenta, procedencia),
    `especiesSinAsignacion` e `interaccionesDirigidasFaltantes`;
  - `tamanos.contrastados` con los tamaños realmente probados por paquete.
- **`GET /motor/termodinamica/diagramas/capacidades`**: los mismos paquetes, con `pares: null` y la misma
  `coberturaGrupos`.
- **Respuestas de evaluación, ensamblaje y diagramas**: sin campos nuevos. La huella del modelo
  (`huellaModelo`, `procedenciaModelo[].huella`) incluye la identidad UNIFAC.

### 8.2 Diagnósticos de datos ausentes

| Situación | Puntual | Ensamblaje | Diagramas |
|---|---|---|---|
| Especie sin asignación de grupos en la variante | `MOTOR_ESTADO_UNIFAC_ASIGNACION_AUSENTE` | `MOTOR_ENS_UNIFAC_ASIGNACION_AUSENTE` | `MOTOR_DIAG_UNIFAC_ASIGNACION_AUSENTE` |
| Subgrupo asignado que no existe en la tabla | `MOTOR_ESTADO_UNIFAC_GRUPO_DESCONOCIDO` | `MOTOR_ENS_…` | `MOTOR_DIAG_…` |
| Interacción dirigida ausente | `MOTOR_ESTADO_UNIFAC_INTERACCION_AUSENTE` | `MOTOR_ENS_…` | `MOTOR_DIAG_…` |

Los tres son `no_soportado`, sin estado ni resultados. El mensaje nombra especie, subgrupo o grupos principales.
`PARAMETRO_AUSENTE` se conserva para NRTL. Una especie con grupos pero sin datos puros (p. ej. la acetona, que
tiene asignación DDBST) se rechaza igual que antes: no hay Psat ni cp.

### 8.3 Huella

La huella cambia si cambian:

- el sha256 de una tabla;
- un valor de interacción usado;
- la variante.

No cambia con:

- el orden de las especies;
- los nombres o símbolos de los componentes;
- las unidades de la petición (P en bar frente a Pa).

Todo esto se comprueba en las secciones 0 y 5 de la suite.

### 8.4 Diagramas (Txy de etanol–agua a 1 atm)

| Paquete | Azeótropo | Literatura | Extremos puros |
|---|---|---|---|
| original | 78.04 °C, x = 0.896 | 78.15 °C, x = 0.894 | 100.01 °C y 78.29 °C (Psat del catálogo) |
| Dortmund | 78.13 °C, x = 0.899 | 78.15 °C, x = 0.894 | 100.01 °C y 78.29 °C |

## 9. U6 · Dortmund

Paquete `unifac-dortmund-public` con sus propias asignaciones (alcoholes primarios con OH(P)) y su tabla DOUFIP2016.

**Pruebas repetidas de U1 a U5:**

- adaptador frente a thermo (`version=1`), 2.1e-15;
- L–V con N = 2, 4 y 7 frente al flash independiente;
- L–L de agua/butanol frente a isoactividad;
- diagrama con azeótropo;
- servicio puntual con N = 4;
- calentamientos con N = 2 y 4, certificados;
- huella distinta de la original con las mismas especies.

**Comparación con la original sobre los mismos datos declarados:**

- azeótropo: §8.4;
- ELL de agua/butanol: §5. La Dortmund predice mucho peor este par. No sustituye a la original ni la cambia.

## 10. U7 · Tabla dedicada a ELL (Magnussen et al., 1981)

**Auditoría.**

- `thermo` distribuye la tabla de subgrupos `LLEUFSG` y las interacciones `UNIFAC LLE interaction parameters.tsv`
  (Magnussen, Rasmussen y Fredenslund, *Ind. Eng. Chem. Process Des. Dev.* 20 (1981) 331, doi:10.1021/i200013a024).
- **No hay asignaciones DDBST para esta tabla**, y su numeración de subgrupos es distinta: H2O es el 16 en la
  original y el 17 en la LLE; el 15 es CH3OH en la original y P1 (1-propanol) en la LLE.

**Decisión: traducción genérica, no por mezcla.** Cada subgrupo de la asignación DDBST original se sustituye por el
**único** subgrupo LLE con el mismo nombre y los mismos R y Q, es decir, la misma definición química. Si no existe o
no es único, no hay asignación.

**Resultado:**

- 6 de 7 especies traducidas;
- **metanol bloqueado por datos**: la tabla LLE no tiene el grupo CH3OH, y no se aproxima como CH3 + OH;
- ninguna interacción ausente entre los grupos de las 6 especies.

**Dominio.** La tabla se ajustó con datos de ELL entre 10 y 40 °C. El paquete declara T ∈ [283.15, 313.15] K como
dominio, por el mismo mecanismo que el paquete NRTL-LLE. Fuera de ese intervalo responde `fuera_de_dominio`.

| Prueba | Resultado |
|---|---|
| ln γ frente a thermo con `LLEUFSG`/`LLEUFIP`, N = 6 | 3.8e-15 |
| agua/butanol a 293, 298 y 313 K | L–L frente a isoactividad a 1e-8; frente a IUPAC, §5 |
| N = 4 (agua, etanol, acetato, butanol) a 300 K | L–L frente a isoactividad |
| N = 6 equimolar a 300 K | fase acuosa incipiente (0.5 %), certificada (§5.2) |
| L–V en el dominio: Pxy de etanol–agua a 298.15 K | completo; entre 3 y 8 % por debajo de la original; **sin el azeótropo** que predicen la original (x = 0.969) y NRTL (x = 0.890) |
| Dinámica: butanol que entra en agua a 298 K (adiabático, P constante) | aparece el segundo líquido; H constante; certificada |
| Metanol | `MOTOR_ESTADO_UNIFAC_ASIGNACION_AUSENTE` (rechazo real, sin simular) |

**Límites.**

- No hay contraste experimental de L–V dentro del dominio.
- El paquete no se usa para «corregir» el reparto de otro paquete: cada estado usa una sola tabla en todas sus
  fases, L–L–V incluido.

## 11. Contrato

- **Nuevo** `docs/contratos/contratoContribucionGrupos.ts`, con los tipos `CoberturaGrupos`,
  `DatosContribucionGrupos`, `VarianteUNIFAC` y `CodigoDatoAusente`. Es específico de la familia UNIFAC: los demás
  paquetes no publican este campo.
- `contratoEnsamblajeV2.ts`: `paquetes[].coberturaGrupos?` (aditivo, sin revisión nueva).
- `contratoDiagramasEquilibrio.ts`: `paquetes[].coberturaGrupos?`. Se precisa que `pares: null` también corresponde
  a un paquete de contribución de grupos.

**Implementado y publicado:** todo lo anterior. **Propuesto y no implementado:** nada.

## 12. Ejemplos y verificador

`docs/ejemplos/motor-unifac/` lo genera `python tests/generar_ejemplos_motor_unifac.py` desde las rutas reales
(ASGI). Contiene:

- **capacidades** de las tres rutas;
- **puntuales:**
  - original: L–V con N = 2, L–L de agua/butanol, L–L con N = 4, L–L–V con N = 5, L–V con N = 7;
  - Dortmund: N = 4;
  - LLE: N = 2 y N = 6;
- **ensamblajes:**
  - calentamiento con N = 2 y N = 4;
  - red con N = 5 y especie entrante;
  - política monofásica detenida;
  - Dortmund con N = 4;
  - mezcla LLE de agua y butanol;
- **diagramas:** Txy y Pxy de etanol–agua; Txy de agua–butanol; Txy Dortmund; Pxy LLE;
- **rechazos** (con `rechazo` en el nombre):
  - reales: metanol con la tabla LLE; T fuera del dominio LLE;
  - **simulados** (con `simulado` en el nombre): asignación ausente e interacción ausente. El catálogo está completo
    y no hay ningún caso real; se provocan en el proceso del generador sustituyendo temporalmente la asignación o
    la tabla, sin tocar archivos de datos.

`node tests/verificar_contrato_unifac.mjs`:

- compila todos los ejemplos contra los tipos canónicos, con controles negativos;
- pasa cada estado (puntual y por volumen y muestra) por `validarRespuestaEstado` del frontend;
- comprueba que la cobertura es la misma en las dos rutas, que `componentesCAS` coincide con las especies
  asignadas, el dominio LLE, la evidencia `cualitativa`, los códigos de rechazo y la huella en `procedenciaModelo`.

## 13. Cambios publicados y comparación con los ejemplos anteriores

Se copió `docs/ejemplos/` antes de los cambios y se regeneró con los cuatro generadores del motor:

- `generar_ejemplos_motor_termodinamica`;
- `generar_ejemplos_motor_ensamblaje_v2`;
- `generar_ejemplos_motor_n_componentes`;
- `generar_ejemplos_motor_diagramas`.

Después se compararon número a número.

**Capacidades.** Solo hay cambios aditivos:

- 3 paquetes más en v2, en diagramas y en el servicio puntual;
- `tamanos.contrastados` para ellos.

En `motor-termodinamica-capacidades.json`, los modelos UNIFAC se insertan antes de `agua-iapws95-hielo-ih`,
que pasa de la posición 4 a la 7. Un lector que busque por `id` no se ve afectado.

**Estados puntuales y diagramas.** Sin cambios numéricos, salvo:

- `tmMinimo` en el orden de 1e-16 a 1e-15 (redondeo del certificado, siempre muy por debajo de TOL_TM);
- `cobertura.presupuesto.segundos` (tiempo de pared).

**Trayectorias que cruzan una arista de fase.** Solo cambian por la corrección de §7.1:

| Ejemplo | Trabajo W al final | Residuo `mecanica.A.trabajo` | Resto de series | Eventos |
|---|---|---|---|---|
| v2: calentamiento etanol–agua | 3291.7467 → 3291.7532 J (2e-6 relativo) | 0.198 → 0.0023 | ≤ 5e-7 relativo | se desplazan ≤ 2e-7 s |
| N: NRTL con 4 especies | 2246.47328 → 2246.47317 J | 0.029 → 0.011 | ≤ 2e-7 relativo | ≤ 2e-7 s |
| N: ideal con 5 especies | 2150.12465 → 2150.12461 J | 0.026 → 9.5e-5 | ≤ 2e-7 relativo | ≤ 2e-7 s |

Los residuos de energía siguen varios órdenes por debajo de su tolerancia: el mayor es 1.4e-5 frente a 10, en NRTL
con 4 especies, antes 3.4e-7.

Las otras dos correcciones compartidas (§5.1 y §5.2) solo actúan cuando el primer intento no certifica y no
cambian ningún ejemplo.

## 14. Rendimiento

`python tests/benchmark_unifac.py`. Equipo: AMD64 Family 25 Model 120, Python 3.12.10, numpy 1.26.4. Mediana
de 5 repeticiones (3 en PH y UV), a 1 atm, con 1 mol equimolar (salvo el L–L con N = 4: z = 0.7/0.04/0.24/0.02 a
300 K).

**Arranque en frío** (importar, cargar las tablas UNIFAC y hacer el primer TP etanol–agua): 1.77 s.

| Paquete | N | Fases | TP (s) | Estabilidad (s) | PH (s) | UV (s) |
|---|---|---|---|---|---|---|
| UNIFAC original | 2 | V+L | 0.016 | 0.005 | 0.19 | 2.1 |
| NRTL | 2 | V+L | 0.009 | 0.002 | 0.09 | 1.0 |
| UNIFAC original | 4 | L+L | 0.058 | 0.008 | — | — |
| NRTL | 4 | L+L | 0.31 | 0.12 | — | — |
| UNIFAC original | 4 | V+L | 0.031 | 0.008 | 0.40 | 3.2 |
| NRTL | 4 | V+L | 0.025 | 0.007 | 0.24 | 2.2 |
| UNIFAC original | 5 | V+L+L | 0.23 | 0.012 | 2.2 | 25 |
| UNIFAC original | 7 | V+L | 0.058 | 0.24 | 2.2 | 33 |
| UNIFAC Dortmund | 7 | V+L | 0.045 | 0.018 | 1.8 | 21 |

**Trayectoria** (calentamiento de 100 W desde 330 K, 300 s, 6 muestras, rtol 1e-8):

| Paquete | N = 2 | N = 4 |
|---|---|---|
| UNIFAC | 27 s | 34 s |
| NRTL | 8.5 s | 23 s |

UV es la operación cara: anida TV y TP. Con N = 5 y 7 tarda de 20 a 33 s por estado.

**Después del benchmark** se añadió una caché del último T real en `LiquidoUNIFAC`: Ψ(T) y lnΓ de los puros solo
dependen de T. La caché no se usa con T compleja. Efectos:

- resultados idénticos bit a bit;
- ln γ con N = 7: de ~55 µs a 27 µs por llamada;
- trayectoria de calentamiento etanol–agua perfilada: de 22 s a 18.9 s.

**Por qué UNIFAC tarda unas 3 veces más que NRTL en trayectorias:**

- el coste de ln γ: ~175 000 evaluaciones por trayectoria;
- unos 180 de los ~1 100 Newton sembrados no convergen y caen al flash completo.

Se probó el método de la cuerda en ese Newton (reutilizar el Jacobiano). Solo ganaba un 5 % y cambiaba los
números en el último bit, así que se descartó.

## 15. Límites (qué no debe leerse como capacidad general)

- **Evidencia.** Las tres variantes son predicciones. `cualitativa` no significa «validada». Los errores medidos
  están en §5, §8.4 y §10.
- **Rango del contraste.** El contraste experimental se limita al azeótropo de etanol–agua y al ELL de
  agua/butanol. Para el resto de combinaciones solo hay contraste numérico, frente a otra implementación con
  las mismas tablas.
- **Vapor ideal y líquido incompresible**, igual que en los demás paquetes de mezcla. P ≤ 5 bar.
- **Tamaños contrastados** (`tamanos.contrastados`):

  | Paquete | Estático | Dinámico |
  |---|---|---|
  | original | 2, 3, 4, 5, 7 | 2, 4, 5 |
  | Dortmund | 2, 3, 4, 5, 7 | 2, 4 |
  | LLE | 2, 4, 6 | 2 |

- **Tabla LLE:** solo entre 10 y 40 °C. Metanol bloqueado.
- **Residuo de trabajo con NRTL** en una trayectoria detenida en la arista: queda en ~1.1 frente a 1 (§7.1).
- **Diagramas:** binarios y L–V. El L–L se identifica como encuentro de otra fase, pero no se traza.

## 16. Regresión, comparación de ejemplos y rendimiento

Ejecutado desde la raíz el 16 de octubre de 2026, después de todos los cambios:

| Comando | Resultado | Salida | Tiempo |
|---|---|---|---|
| `python tests/validar_motor_unifac.py` | OK, 136 | 0 | 613 s |
| `python tests/validar_motor_termodinamica.py` | OK, 585 | 0 | 7 s |
| `python tests/validar_motor_termodinamica_h3.py` | OK, 3729 | 0 | 26 s |
| `python tests/validar_motor_ensamblaje.py` | OK, 245 | 0 | 99 s |
| `python tests/validar_motor_ensamblaje_v2.py` | OK, 114 | 0 | 126 s |
| `python tests/validar_motor_consolidacion_v2.py` | OK, 128 | 0 | 133 s |
| `python tests/validar_motor_n_componentes.py` | OK, 82 | 0 | 267 s |
| `python tests/validar_motor_diagramas_equilibrio.py` | OK, 78 | 0 | 31 s |
| `node tests/verificar_contrato_unifac.mjs` | OK: 7 ensamblajes (47 estados), 12 puntuales, 6 diagramas | 0 | |
| `node tests/verificar_contrato_ensamblaje_v2.mjs` | OK: 10 pares, 60 estados, 12 puntuales | 0 | |
| `node tests/verificar_contrato_diagramas.mjs` | OK: 11 pares, 285 puntos | 0 | |
| `node tests/verificar_contrato_motor_termodinamica.mjs` | OK, 35 | 0 | |
| `node tests/verificar_contrato_ensamblaje.mjs` | OK: 13 pares, 175 estados | 0 | |
| `npm run test:motor-fundamental` (en `frontend/`) | OK; la salida incluye «101 comprobaciones de cobertura de grupos» del lector que ya preparó Codex | 0 | |

Las suites de Python se ejecutaron en paralelo con el código final, que ya incluye la caché por T. Los verificadores
TS y npm usan los ejemplos regenerados, que el código final reproduce: la caché da resultados idénticos bit a bit.

**Nota sobre dos fallos ya corregidos.** En una ejecución anterior, los rechazos simulados de asignación ausente y de grupo
desconocido llegaban al trazador de diagramas con `MOTOR_DIAG_COMPONENTE_NO_SOPORTADO` en vez del código UNIFAC.
El motivo es que las capacidades ya filtran `componentesCAS` por asignación (§10). Corrección en
`backend/motor_diagramas.py`: en un paquete de contribución de grupos, si una especie está en el catálogo, el
rechazo se deja al `Sistema`, que da el código preciso. Después se repitieron la sección 5 y la suite de
diagramas (arriba).

Las 40 suites históricas (`tests/validar_*.py` fuera de `validar_motor_*`) no se repitieron. Ninguna importa
`core/mezclas`, `core/unifac`, `core/ensamblaje_red` ni los servicios `backend/motor_*`. Esto se comprobó con
grep. Las que importan `backend.main` solo ven rutas añadidas en sesiones anteriores, sin cambios en esta.

### Manifiesto de archivos

**Nuevos:**

- `core/unifac.py`
- `docs/contratos/contratoContribucionGrupos.ts`
- `docs/MOTOR_UNIFAC.md`
- `docs/ejemplos/motor-unifac/` (53 JSON)
- `tests/validar_motor_unifac.py`
- `tests/generar_ejemplos_motor_unifac.py`
- `tests/verificar_contrato_unifac.mjs`
- `tests/benchmark_unifac.py`

**Modificados:**

| Archivo | Cambio |
|---|---|
| `core/mezclas.py` | Paquetes UNIFAC, `FaltaParametro.codigo`, cerrojo F0, reintento del TP (§5.1), semillas del reparto (§5.2), huella, dominio LLE |
| `core/mezclas_datos.py` | Cerrojo F0 |
| `core/ensamblaje_red.py` | dV/dt lateral (§7.1) |
| `backend/motor_mezclas.py` | Modelos, códigos, dominio y especies por variante |
| `backend/motor_ensamblaje_v2.py` | Evidencia, `coberturaGrupos`, tamaños, códigos, cerrojo |
| `backend/motor_diagramas.py` | `coberturaGrupos`, códigos, pertenencia en paquetes de grupos |
| `docs/contratos/contratoEnsamblajeV2.ts` | `coberturaGrupos?` |
| `docs/contratos/contratoDiagramasEquilibrio.ts` | `coberturaGrupos?` |
| `tests/validar_motor_termodinamica.py`, `tests/validar_motor_ensamblaje_v2.py`, `tests/validar_motor_diagramas_equilibrio.py` | Lista de modelos publicados ampliada con los tres paquetes |
| `docs/ejemplos/` (raíz, `motor-v2/`, `motor-n-componentes/`, `motor-diagramas/`) | Regenerados (§13) |

`backend/main.py` no se modificó en esta entrega. Su diff frente a `main` es de las rutas de diagramas añadidas en
la entrega anterior.

## 17. Trabajo para Codex

1. Sincronizar la copia de `contratoContribucionGrupos.ts` y los campos `coberturaGrupos?` de los contratos de
   ensamblaje v2 y diagramas.
2. Lectura estricta:
   - `coberturaGrupos` solo puede aparecer en paquetes `unifac-*`;
   - `pares` es `undefined` en v2 y `null` en diagramas para esos paquetes;
   - la evidencia L–V y L–L es `cualitativa`.
3. Mostrar los grupos y los datos (sha256, fuente) en los detalles del paquete, no en la pantalla principal. Una
   especie de `especiesSinAsignacion` no se ofrece con ese paquete; el metanol con LLE debe verse como «sin grupo
   en la tabla», no como un error genérico.
4. Selección explícita de variante. La caché y los marcadores de diagrama se invalidan por huella, nunca por ID.
5. Diagnósticos `*_UNIFAC_ASIGNACION_AUSENTE`, `*_UNIFAC_GRUPO_DESCONOCIDO` y `*_UNIFAC_INTERACCION_AUSENTE` como
   dato ausente, separados del recuento de variables.
6. Dominio del paquete LLE: 283.15–313.15 K. No ofrecer T fuera de ese intervalo con ese paquete.
7. Verificador de integración con `docs/ejemplos/motor-unifac/`. Los ejemplos `simulado` no se pueden reproducir
   contra el servicio real.
