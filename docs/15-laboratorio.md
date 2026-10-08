# 15. El laboratorio: de un grafo de piezas a un sistema resuelto

La mesa del laboratorio deja dibujar piezas físicas —alimentación, volumen
de control, fuente de calor, corriente intermedia, salida— y conectarlas.
Hasta ahora el frontend podía **formular** ese montaje: escribir los
balances en LaTeX y marcar qué términos anulaban los supuestos. Pero solo
había adaptadores para dos montajes concretos, un calentador y un CSTR
isotermo, así que **dos volúmenes en serie no se podían resolver**.

Este capítulo documenta el ensamblador que sí los resuelve
(`core/laboratorio.py`), las tres decisiones que le dan forma, y la
estequiometría que se le añadió después (`core/estequiometria.py`).

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

El caso de aceptación (binario, dos volúmenes) produce **20 relaciones**,
de las que **12** cuentan:

| Relación | Tipo | ¿Cuenta? |
|---|---|---|
| `{corriente}:entalpia` ×3 | constitutiva | **sí** (3) |
| `{corriente}:cierre` ×3 | cierre | **sí** (3) |
| `{vol}:materia_especie_{i}` ×2 por volumen | balance | **sí** (4) |
| `{vol}:energia` ×2 | balance | **sí** (2) |
| `{corriente}:condiciones` ×3 | condición | no |
| `{fuente}:convencion` ×2 | convención | no |
| `{vol}:materia_total` ×2 | verificación | no |
| `global:energia` | verificación | no |

Y el conteo cierra:

$$
\mathrm{GL} = \underbrace{12}_{\text{incógnitas}} - \underbrace{12}_{\text{ecuaciones}} = 0
$$

con 20 variables totales y 8 impuestas.

### Dos cosas que el recuento dice y conviene leer despacio

**El balance total de materia NO es independiente.** Es la suma de los
$n$ balances por especie, así que contarlo regalaría una ecuación — el
mismo error que contar la verificación global de energía. Y como suma,
sirve de comprobación: si los $n$ se aplicaron bien, el total cuadra. Su
residuo se mide.

**El cierre de composición cuenta… cuando determina algo.** Con las $n$
fracciones como variables explícitas, el cierre determina la que no se
dio, y entonces es una ecuación. Si se dan las $n$, no calcula nada:
**comprueba**, y entonces no cuenta y su residuo se mide.

El criterio no ha cambiado nunca: **una relación cuenta si y solo si
determina algo.** Lo que cambió al pasar de binario a $n$ especies es que
antes la segunda fracción no era una variable sino una expresión, así que
el cierre no determinaba nada.

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

## 15.9bis Reacción: bruto no es neto

Lo que el contrato del laboratorio pide con más insistencia, y con razón,
porque la respuesta ingenua es incorrecta.

### El caso que lo decide

Una reacción reversible en equilibrio tiene $r^+ = r^- > 0$. La fuente
neta de cada especie es **cero** y, aun así, cada especie se está
produciendo y consumiendo a un ritmo **positivo**. Las moléculas no están
quietas: están yendo y viniendo a la misma velocidad.

De ahí se sigue que **la fuente neta no determina las brutas**. Un neto de
cero es compatible con dos situaciones físicas distintas:

| | $r^+$ | $r^-$ | neto | $G_i$ | $C_i$ |
|---|---|---|---|---|---|
| reacción parada | 0 | 0 | 0 | 0 | 0 |
| equilibrio dinámico | 5 | 5 | 0 | $\|\nu_i\|\cdot 5$ | $\|\nu_i\|\cdot 5$ |

Nada en la tasa neta las distingue. Así que el motor hace tres cosas
distintas según lo que le den:

**1. Con $r^+$ y $r^-$ por separado, las brutas se calculan.**

$$
G_i = \max(\nu_i, 0)\,r^+ + \max(-\nu_i, 0)\,r^-
$$
$$
C_i = \max(-\nu_i, 0)\,r^+ + \max(\nu_i, 0)\,r^-
$$

El evento directo produce lo que tiene $\nu > 0$; el inverso, lo que tiene
$\nu < 0$. Las dos cosas generan, y por eso se suman. Y la diferencia
recupera el neto, $G_i - C_i = \nu_i(r^+ - r^-) = \nu_i \xi$, como debe
ser.

**2. Con solo la tasa neta, las brutas salen `null`.** Con su motivo, y
**nunca** rellenadas con $\max(\text{neto}, 0)$: eso daría cero generación
en una reacción que puede estar funcionando a toda velocidad.

**3. La descomposición del neto se ofrece aparte y etiquetada.** Es el
signo del neto repartido en dos casillas no negativas. Es útil —dice en
qué dirección va la especie— y **no** es el intercambio bruto. En el
equilibrio da cero en las dos mientras las brutas valen 10 y 5.

### Y no son incógnitas libres

$G_i$ y $C_i$ se **derivan** de la estequiometría y de las tasas. Con $n$
especies, declararlas como variables serían $2n$ incógnitas nuevas y el
problema quedaría irremediablemente indeterminado. Se calculan, se
reportan, y no entran en el recuento.

Lo mismo con $F_i = F x_i$: derivado, reportado, no contado. Declararlo
como variable añadiría $n$ incógnitas y $n$ ecuaciones que se cancelan.

### Los balances, en caudales y no en fracciones

$$
F_{i,sal} = F_{i,ent} + \sum_r \nu_{ir}\,\xi_r
$$

Se trabaja con caudales por especie y no con fracciones **porque el
balance es lineal en $F_i$ y no en $x_i$**: con reacción el caudal total
cambia, y una ecuación escrita en fracciones arrastraría ese cambio a
todos los términos.

El total sale de la suma, y **puede cambiar**:

$$
F_{sal} = F_{ent} + \sum_r \left(\sum_i \nu_{ir}\right) \xi_r
$$

Un caudal molar que cambia parece un balance roto y no lo es. Lo que no
cambia nunca es la masa.

### Conservación: dos comprobaciones distintas

**Antes de resolver**, la estequiometría se valida contra la matriz
elemental que `thermo` da por especie:

$$
A \cdot \nu = 0 \qquad MW \cdot \nu = 0
$$

Una $\nu$ que no la cumpla no es una reacción química: es un dato mal
puesto.

**Después de resolver**, elementos y masa se **miden** sobre los caudales
resueltos. No es la misma comprobación: aquello verifica que la reacción
tenga sentido, esto que el balance se haya **aplicado** bien. Una reacción
bien balanceada con un balance mal aplicado pasa la primera y falla la
segunda, y por eso hacen falta las dos.

### El calor de reacción, y el doble conteo

La referencia de este motor es **sensible**: $h$ no incluye las entalpías
de formación. La entalpía absoluta de una corriente es

$$
H = \sum_i F_i \left( h_{f,i}(T_{ref}) + h_{sens,i}(T) \right)
$$

y al restar entrada de salida, los $h_f$ salen multiplicados por
$F_{i,sal} - F_{i,ent} = \sum_r \nu_{ir}\xi_r$, lo que da exactamente
$\sum_r \xi_r \Delta H_{rxn,r}(T_{ref})$. El balance queda:

$$
\dot Q + F_{ent} h_{ent} - F_{sal} h_{sal} - \sum_r \xi_r \Delta H_{rxn,r} = 0
$$

**$\Delta H_{rxn}$ se evalúa a la temperatura de REFERENCIA.** No es una
aproximación: toda la dependencia con $T$ ya está en los términos
sensibles. Corregirlo aquí con Kirchhoff **sería contarlo dos veces** — es
el error que el contrato pide evitar, visto desde el otro lado.

Y la decisión de sumar el término **cuelga de la referencia**, no de que
haya reacción. `REFERENCIAS[...]["incluye_formacion"]` es una tabla, no un
comentario, para que añadir una referencia obligue a declarar en qué lado
cae. Si incluyera formación, el término no aparecería —ya estaría dentro
de $h$— y figuraría en `terminos_descartados` con ese motivo.

Con $\xi = 0$ el calor de reacción es cero **aunque las brutas sean
positivas**: lo mueve el avance neto.

### El cierre global con reacción

$$
\sum_j \dot Q_j = F_{sal} h_{sal} - F_{ent} h_{ent} + \sum_r \xi_r \Delta H_{rxn,r}
$$

Al sumar los balances por volumen, los estados intermedios se cancelan
—son la **misma** variable, por §15.1— pero los términos de reacción se
acumulan. Esta fórmula se escribió primero sin el término de reacción, y
**la guarda del cierre lo detectó**: dos reactores en serie daban
`no_convergente` porque los números no cuadraban con una comprobación
incompleta. Para eso se puso.

### El método sigue siendo triangular

Y eso no es casualidad: **la tasa está especificada**, así que el avance
es un dato y no depende de la composición de salida. El balance por
especie sigue siendo explícito y la marcha aguas abajo sigue valiendo.

Una tasa cinética $r(T, \mathbf{x}_{sal})$ rompería eso: el balance se
volvería implícito y haría falta un solver acoplado. Por eso la cinética
se rechaza con diagnóstico en vez de aproximarse — declarar «Newton»
cuando lo que corre es una marcha sería la mentira de §15.3, y resolver un
sistema implícito con una marcha sería peor.

### Las bases, y por qué la unidad las declara

| Base | Unidad | Avance |
|---|---|---|
| integrada | `mol/s` | $\xi = r$ |
| volumétrica | `mol/(m3*s)` | $\xi = r \cdot V$ |

**La unidad declara la base.** Es lo menos ambiguo posible y no depende de
que nadie rellene un campo `base` de forma coherente con ella. Una tasa
volumétrica sin $V$ no se integra con 1 m³: se diagnostica.

---

## 15.10 Límites

- **Trabajo de eje y régimen transitorio se rechazan** con diagnóstico.
  Un montaje que el motor no sabe resolver tiene que decirlo en vez de
  devolver números de otro problema.
- **La cinética y el equilibrio químico, también.** La tasa tiene que
  estar especificada; ver §15.9bis.
- **Dos volúmenes como máximo**, una alimentación, una salida por volumen.
  El límite es del ensamblador, no del método: la marcha aguas abajo sirve
  para $N$.
- **Presión uniforme.** El modelo de caída de presión existe en
  [§12](12-validacion.md) pero no está conectado aquí.
- **De 2 a 8 componentes.** Las fracciones se llaman `x0`…`x{n-1}`; `x` a
  secas vale como alias de `x0` solo en binarios.
- **Sin reciclos.** Un lazo se detecta y se nombra — el mensaje dice por
  dónde pasa — pero no se resuelve; `/diagrama/resolver` sí los admite
  (ver [§2.7](02-solver.md)).
- **El decantador no está expuesto en ninguna API**, ni aquí ni en el
  diagrama. Existe en el motor y no se puede pedir por HTTP.

---

## 15.11 Qué comprueba la validación

`tests/validar_laboratorio.py`, ocho grupos y **230 comprobaciones**. **Los números no están
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

De la reacción, lo mismo: los avances y las fuentes se comparan contra lo
que la estequiometría **obliga** —$\nu_i$ por el avance— y la conservación
contra la matriz atómica de `thermo`. Dos sistemas reales con propiedades
completas y balance elemental exacto:

| Caso | $\nu$ | Qué demuestra |
|---|---|---|
| `n-butano → isobutano` | $[-1, +1]$ | $\Sigma\nu = 0$: el caudal molar no cambia |
| `diisobutileno → 2\,isobuteno` | $[+2, -1]$ | $\Sigma\nu = +1$: 100 → **110** mol/s, masa constante |
| `2\,isobuteno \rightleftharpoons diisobutileno` | $[-2, +1]$ | reversible, y el equilibrio con $r^+ = r^-$ |

Los residuos de elementos y masa quedan por debajo de $10^{-12}$ en todos
los casos, y el cierre global del montaje de dos reactores da **0.0**:
$\Sigma \dot Q = -2\,517\,877.48$ W $=$ transporte $249\,622.52$ $+$
reacción $-2\,767\,500.00$.

### Dos defectos que la reacción destapó

Los dos estaban desde la primera entrega y los dos eran invisibles
mientras el laboratorio fuera binario:

- **Una fracción molar de cero se rechazaba** como no física. `DOMINIO`
  usaba un único criterio para todas las magnitudes, y para un caudal está
  bien —cero no es un caudal pequeño, es la ausencia de corriente— pero
  para una fracción es falso. Nadie escribe $x = 0$ en una mezcla de dos;
  con tres especies y una alimentación pura, es lo normal.
- **El cierre de composición se evaluaba dos veces** en la corriente de
  entrada, y la segunda vez tomaba la rama de «se dieron las $n$», que
  **mide** el residuo de la suma. Pero una de esas fracciones se acababa
  de *calcular*, así que medía el residuo de $1 - (1 - x)$: cero por
  construcción. Es exactamente el error que este módulo denuncia en todos
  los demás sitios, cometido por no distinguir un valor **impuesto** de
  uno **calculado**. La bandera `impuesta` existe justo para eso y ahí no
  se estaba usando.
