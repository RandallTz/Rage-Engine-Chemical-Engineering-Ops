# 15. El laboratorio: de un grafo de piezas a un sistema resuelto

La mesa del laboratorio deja dibujar piezas físicas —alimentación, volumen
de control, fuente de calor, corriente intermedia, salida— y conectarlas.
Hasta ahora el frontend podía **formular** ese montaje: escribir los
balances en LaTeX y marcar qué términos anulaban los supuestos. Pero solo
había adaptadores para dos montajes concretos, un calentador y un CSTR
isotermo, así que **dos volúmenes en serie no se podían resolver**.

Este capítulo documenta el ensamblador que sí los resuelve
(`core/laboratorio.py`), y las tres decisiones que le dan forma.

El contrato de la API, los códigos de diagnóstico y los ejemplos exactos
están en [`ENTREGA_LABORATORIO_CODEX.md`](ENTREGA_LABORATORIO_CODEX.md).

---

## 15.1 Una corriente intermedia es UN estado, no dos

Es el requisito central, y el que decide la arquitectura.

Si el volumen 1 escribiera su salida en un sitio y el volumen 2 leyera su
entrada de otro, haría falta añadir ecuaciones de igualdad:

$$
F_{sal} = F_{ent}, \quad T_{sal} = T_{ent}, \quad p_{sal} = p_{ent},
\quad x_{sal} = x_{ent}, \quad h_{sal} = h_{ent}
$$

Cinco ecuaciones y cinco incógnitas que **no son incógnitas**. Aquí el
estado **pertenece al bloque corriente**: los dos volúmenes referencian
las mismas variables, así que no hay nada que igualar.

En la respuesta eso se ve directamente — las cinco variables de la
corriente salen con `rol: "compartida"` y cada una cita los dos volúmenes
y las dos conexiones:

```json
{"id": "medio.T", "bloque_ids": ["medio", "cv1", "cv2"],
 "conexion_ids": ["c3", "c4"], "rol": "compartida", "impuesta": true,
 "valor": 310.0}
```

### El rol y la bandera

El contrato pedía tres valores de `rol`: `impuesta`, `calculada` y
`compartida`. No son ortogonales — una variable de corriente intermedia
puede estar impuesta **y** ser compartida — así que hay además una
bandera `impuesta`. El rol dice lo que la distingue en el contrato; la
bandera conserva la otra mitad en vez de obligar al rol a elegir cuál
contar.

---

## 15.2 El LaTeX se genera, nunca se interpreta

El JSON de la mesa trae relaciones en LaTeX para que el usuario las lea.
Son **descriptivas**. El motor ensambla desde los **tipos físicos** de las
piezas y emite su propio LaTeX como salida.

Interpretar la cadena del cliente sería ejecutar lo que un cliente
escribió. Está comprobado en la suite: una petición que incluya una
relación diciendo $\dot Q = 0$ no cambia ni un número.

Cada relación sale con tres campos que, juntos, permiten explicar la
diferencia entre «este término no aplica» y «este término se olvidó»:

| Campo | Qué lleva |
|---|---|
| `latex_general` | La ley completa, antes de los supuestos |
| `latex_activo` | Lo que queda tras aplicarlos |
| `terminos_descartados` | Qué cayó, por qué supuesto, y el motivo |

Para el balance de energía del primer volumen:

$$
\frac{dE_{CV}}{dt} = \dot Q - \dot W_s + \sum_{in} F(h + e_k + e_p)
- \sum_{out} F(h + e_k + e_p)
$$

queda, bajo estacionario + sinTrabajo + sinMovimiento:

$$
\dot Q_3 + F_1 h_1 = F_4 h_4
$$

y los tres términos caídos viajan con el nombre del supuesto que los tiró.

---

## 15.3 El método se declara, no se adorna

Para esta topología el sistema es **triangular**: el estado de salida de
cada volumen depende solo de lo que está aguas arriba. Así que se resuelve
con una **marcha aguas abajo**, y cada volumen es uno de dos casos:

| Modo | Qué se impone | Qué se despeja | Algoritmo |
|---|---|---|---|
| temperatura | $T_{sal}$ | $\dot Q = F(h_{sal} - h_{ent})$ | evaluación directa |
| calor | $\dot Q$ | $h_{sal} = h_{ent} + \dot Q/F$, y $T$ de invertir $h$ | `brentq`, xtol $10^{-10}$ K |

No hay sistema acoplado, no hay Newton y no hay lazo global.

**Declarar «Newton» porque suena a motor sería la misma clase de mentira
que fabricar un residuo.** El contrato lo prohíbe expresamente y tiene
razón: quien lea «Newton, 1 iteración» concluirá cosas falsas sobre el
coste y sobre el condicionamiento del problema.

### Y los dos modos son excluyentes por una razón estructural

El balance de energía del volumen es **una** ecuación con dos incógnitas
posibles: $T_{sal}$ y $\dot Q$. Fijar una determina la otra; fijar las dos
deja la ecuación sobrante y en general violada; no fijar ninguna la deja
indeterminada. No es una regla del adaptador, es aritmética.

---

## 15.4 El recuento: qué es una ecuación y qué no

El caso de aceptación produce **18 relaciones**, de las que solo **9**
cuentan como ecuaciones:

| Relación | Tipo | ¿Cuenta? |
|---|---|---|
| `in:entalpia`, `medio:entalpia`, `out:entalpia` | constitutiva | **sí** (3) |
| `cv1:materia_total`, `cv1:materia_especie`, `cv1:energia` | balance | **sí** (3) |
| `cv2:materia_total`, `cv2:materia_especie`, `cv2:energia` | balance | **sí** (3) |
| `in:condiciones`, `medio:condiciones`, `out:condiciones` | condición | no |
| `heat1:convencion`, `heat2:convencion` | convención | no |
| `in:cierre`, `medio:cierre`, `out:cierre` | cierre | no |
| `global:energia` | verificación | no |

Y el conteo cierra:

$$
\mathrm{GL} = \underbrace{9}_{\text{incógnitas}} - \underbrace{9}_{\text{ecuaciones}} = 0
$$

con 17 variables totales y 8 impuestas.

**Por qué cada exclusión.** El contrato lo pedía sin rodeos —
*«Convenciones de signo y especificaciones de entrada no se cuentan
automáticamente como ecuaciones independientes»*— y es la fuente del error
más común al mostrar grados de libertad:

- **Una especificación es un dato.** Reduce las incógnitas; no aumenta las
  ecuaciones. Contarla las cuenta dos veces y los GL salen negativos en un
  sistema perfectamente planteado.
- **Una convención de signo no es una ecuación.** «$\dot Q > 0$ hacia el
  volumen» define qué significa el número, no lo determina.
- **El cierre de composición se satisface por la parametrización.** El
  estado binario se describe con $x_1$, y $x_2 = 1 - x_1$ por
  construcción. No hay nada que resolver, así que tampoco residuo.
- **La verificación global es combinación lineal de los balances.**
  Contarla regalaría una ecuación.

### Sobre el rango

`rango` es **estructural**, y `rango_origen` dice de dónde sale: el
sistema es triangular por el orden aguas abajo, así que cada ecuación
introduce una variable nueva y ninguna es combinación de las anteriores.
Eso se sigue del **orden**, no de un Jacobiano.

**No se calcula un rango numérico local ni se presenta uno.** El contrato
advierte justo contra eso y con razón: la independencia en un punto no es
la independencia global. Cuando no se puede determinar, es `null`.

---

## 15.5 La fase se determina, no se supone

Cada estado pasa por un flash isotérmico que ubica el punto frente al
punto de burbuja y al de rocío a $(T, p, \mathbf{x})$ (ver
[§5](05-flash.md)), así que la fase sale como **consecuencia** y $\beta$
es el dato que la respalda.

En el caso de aceptación los tres estados son líquido subenfriado — la
burbuja de benceno/tolueno 50/50 a 300 K está en **8894 Pa**, muy por
debajo de 1 atm — pero el motor lo **comprueba**. Y es barato: el caso
líquido se corta en la comprobación de burbuja, una sola llamada a UNIFAC.

Que importa se ve en cuanto se sale de ahí. Con 2 MW en el primer volumen:

| $\dot Q_1$ | $T$ intermedia | fase | $\beta$ |
|---|---|---|---|
| 0.148 MW | 310.0 K | líquido | 0 |
| 1.0 MW | 364.3 K | líquido | 0 |
| 2.0 MW | 367.5 K | **bifásico** | 0.302 |
| 3.0 MW | 369.6 K | **bifásico** | 0.606 |
| 5.0 MW | 434.4 K | vapor | 1 |

Dentro de la laguna, **1 MW más sube la temperatura 2.1 K** porque casi
toda la energía va a calor latente — frente a los ~10 K que costaban
0.15 MW en la zona líquida. Cualquier modelo con $C_p$ constante da aquí
un disparate.

### Y $C_p$ no es constante ni siquiera en el líquido

El caso de aceptación lo enseña sin salir de la fase líquida:

| Tramo | $\dot Q$ |
|---|---|
| 300 → 310 K | 147 842.85 W |
| 310 → 320 K | 150 506.36 W |

El mismo salto de 10 K cuesta un **1.80 % más** en el segundo tramo.

---

## 15.6 Qué NO se infiere

**La ausencia de una pieza no es un supuesto.** Que no haya fuente de
calor dibujada no significa $\dot Q = 0$: significa que el montaje no
declara intercambio térmico, y entonces al balance de energía le falta un
término.

La diferencia se nota en el diagnóstico. Con $\dot Q = 0$ supuesto, un
volumen al que se le pide subir 10 K daría un sistema incompatible sin
explicación. Declarándolo indeterminado, el mensaje dice exactamente qué
falta: *«conecta una fuente de calor o marca el supuesto adiabático»*.

El contrato lo pedía en los dos sentidos, y los dos están:

- fuente conectada **con** supuesto adiabático → `LAB_SUPUESTO_INCOHERENTE`
  (el supuesto anula el término que la pieza existe para aportar);
- ni fuente **ni** adiabático → `LAB_FALTA_ESPECIFICACION`.

---

## 15.7 Lo que se mide y lo que no

Heredado de [§14](14-trazabilidad.md), y con el mismo criterio.

| Situación | `residuo` | Por qué |
|---|---|---|
| $\dot Q$ despejado del balance | `null` | Se satisface por construcción: publicar el redondeo sería presentarlo como convergencia |
| Propagación de $F$ y $x$ | `null` | Fórmula cerrada |
| $h = h(T,p,x)$ | `null` | Evaluación directa |
| Inversión $h(T)$ con $\dot Q$ impuesto | **medido** | `\|h(T_{hallada}) - h^*\|`, relativo a la entalpía molar |
| Cierre global con **dos** volúmenes | **medido** | Comprobación independiente |
| Cierre global con **un** volumen | `null` | Es su propio balance: medirlo sería una tautología |

### El cierre global, y por qué sirve

$$
\sum_j \dot Q_j = F\,(h_{salida} - h_{entrada})
$$

No es una ecuación del sistema —es la **suma** de los balances por
volumen— y por eso mismo es la única comprobación independiente que queda:
si los balances se resolvieron bien, la igualdad tiene que cumplirse. Se
mide, y si excede $10^{-8}$ relativo el estado pasa a `no_convergente` con
un error `LAB_CIERRE_GLOBAL`. En el caso de aceptación da **0.0**.

Con un solo volumen esa igualdad **es** su balance de energía —la ecuación
de la que se despejó $\dot Q$— así que se emite la relación, explicando
por qué, pero no se mide.

### Y lo que se cuenta no son iteraciones

`iteraciones` es siempre `null`, a propósito. Lo que se cuenta en
`inversiones_escalares` son las inversiones realizadas, una por volumen en
modo calor. **No** son iteraciones de `brentq`: el lazo lo lleva `brentq`
dentro del flash y no publica su contador, así que poner ahí el número de
inversiones invitaría a leer «converge en 1 iteración», que es falso.

### La guarda que la medición hace posible

`brentq` para cuando la **temperatura** deja de moverse más de su `xtol`,
y eso no es lo mismo que que la **entalpía** haya cuadrado. Donde $h(T)$
es muy empinada —dentro de la laguna, donde 1 MW mueve 2 K— una $T$
correcta hasta $10^{-10}$ K puede dejar un residuo apreciable en $h$.

Por eso el residuo se comprueba contra $10^{-9}$ y, si lo excede, el
estado es `no_convergente`. Medir un residuo y no actuar sobre él es la
mitad del trabajo, y es la mitad que no protege de nada.

---

## 15.8 Unidades: la trampa de la misma letra

La unidad es **obligatoria** en cada especificación. Las tablas completas
están en [la entrega](ENTREGA_LABORATORIO_CODEX.md#3-unidades); aquí el
detalle que importa.

`bloques[].datos` se admite por compatibilidad con lo que la mesa exporta
hoy, y ahí las unidades son **implícitas**, con las que la mesa documenta:
$F$ en mol/s, $T$ en K, $p$ en Pa, $x$ adimensional y **$\dot Q$ en kW**.

Así que la misma letra `Q` significa W en una especificación explícita y
kW en un dato local. Tomar un dato local por watts da un calor **mil veces
menor**, que no se parece a un error: se parece a un resultado. Por eso:

- las especificaciones explícitas son el camino preferente;
- la `procedencia` de cada variable dice si el valor llegó sin unidad
  escrita;
- `capacidades` lo avisa.

La temperatura es **afín**: `degC` lleva desplazamiento y las demás no. Es
el mismo problema que la LMTD destapó (ver [§11](11-unidades.md)).

---

## 15.9 Validar sin resolver

`/laboratorio/validar` ensambla, cuenta y diagnostica **sin llamar al
solver**, como pedía el contrato. Devuelve:

- las variables con su rol y los valores **impuestos**; los calculados en
  `null`;
- las relaciones con `ejecutada: false` y sin residuos — la verdad: no se
  ejecutó nada;
- el análisis estructural completo, con los grados de libertad;
- `convergencia: null` y `analisis.metodo: null`, porque no corrió ningún
  algoritmo y no hay nada que declarar.

El proveedor termodinámico **sí** se construye, porque «este componente no
existe para este modelo» es una validación de datos y no un cálculo.

---

## 15.10 Límites

- **Un reactor, reacción, trabajo de eje o régimen transitorio se
  rechazan** con diagnóstico. El contrato lo permitía en esta entrega, y
  es lo correcto: un montaje que el motor no sabe resolver tiene que
  decirlo en vez de devolver números de otro problema.
- **Dos volúmenes como máximo**, una alimentación, una salida por volumen.
  El límite es del ensamblador, no del método: la marcha aguas abajo sirve
  para $N$.
- **Presión uniforme.** El modelo de caída de presión existe en
  [§12](12-validacion.md) pero no está conectado aquí.
- **Binarios.** $x$ es la fracción del primer componente.
- **Sin reciclos.** Un lazo se detecta y se nombra — el mensaje dice por
  dónde pasa — pero no se resuelve; `/diagrama/resolver` sí los admite
  (ver [§2.7](02-solver.md)).
- **El decantador no está expuesto en ninguna API**, ni aquí ni en el
  diagrama. Existe en el motor y no se puede pedir por HTTP.

---

## 15.11 Qué comprueba la validación

`tests/validar_laboratorio.py`, siete grupos. **Los números no están
escritos a mano**: se comparan contra llamadas independientes al mismo
proveedor. Si copiara la salida del ensamblador como valor esperado, la
prueba bendeciría cualquier error que tuviera, y para siempre.

Lo único que se afirma a priori son las **identidades físicas**, que no
dependen de ningún dato: que $F$ se conserva, que duplicar $F$ duplica
$\dot Q$, que $\dot Q_1 + \dot Q_2 = F\,\Delta h$, y que imponer el
$\dot Q$ calculado recupera la $T$ de la que salió — con error **0.0 K**.

Y una comprobación que cruza los dos servicios: el preset de un volumen
da el **mismo** $\dot Q$ que `/diagrama/resolver` para el mismo problema,
147 842.851474 W por los dos caminos.
