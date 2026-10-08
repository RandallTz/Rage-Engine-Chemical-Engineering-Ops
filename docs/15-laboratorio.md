# 15. El laboratorio: de un grafo de piezas a un sistema resuelto

La mesa del laboratorio deja dibujar piezas físicas —alimentación, volumen
de control, fuente de calor, corriente intermedia, salida— y conectarlas.
Hasta ahora el frontend podía **formular** ese montaje: escribir los
balances en LaTeX y marcar qué términos anulaban los supuestos. Pero solo
había adaptadores para dos montajes concretos, un calentador y un CSTR
isotermo, así que **dos volúmenes en serie no se podían resolver**.

Este capítulo documenta el ensamblador que sí los resuelve
(`core/laboratorio.py`), las tres decisiones que le dan forma, la
estequiometría que se le añadió después (`core/estequiometria.py`), la
cinética que rompió su estructura triangular (`core/cinetica.py`), y los
tres servicios que crecieron de ahí: el balanceo exacto
(`core/balanceo.py`), el equilibrio calculado (`core/equilibrio.py`) y el
lote transitorio (`core/lote.py`).

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

## 15.9ter Cinética: cuando la tasa deja de ser un dato

### Lo que se rompe

Con la tasa dada, el avance es un **dato**: el balance por especie se
resuelve hacia delante y el sistema es triangular (§15.3). Con una ley de
velocidad:

$$ \xi_r = r_r(T, \mathbf{x}_{salida}) \qquad \mathbf{x}_{salida} = \mathbf{x}_{salida}(\xi) $$

la tasa depende de la composición de **salida**, que es lo que el balance
calcula. Eso es un sistema implícito.

**La triangularidad se rompe DENTRO de cada volumen, no entre volúmenes.**
La marcha aguas abajo sigue valiendo: la entrada de cada volumen es la
salida del anterior, ya determinada. Es una distinción que la respuesta
declara, porque decir «sistema acoplado» a secas sugeriría que todo el
montaje se resuelve a la vez, y no es así.

Y es el motivo de que la entrega anterior **rechazara** la cinética con un
diagnóstico en vez de aproximarla: resolver un sistema implícito con una
marcha habría dado números, y números de otro problema.

### La ley, con órdenes explícitos

$$ r = k(T)\prod_i a_i^{n_i} $$

**Un orden no es un coeficiente estequiométrico.** La ley sale de un
mecanismo y la estequiometría de un balance, y coinciden solo en una
reacción elemental. Si no se declaran se usa $|\nu|$ de los reactivos
—acción de masas consistente con la estequiometría— y la respuesta **dice
que ese fue el defecto**, para que nadie crea que lo eligió.

Los órdenes **negativos se rechazan**: modelan inhibición y hacen que la
tasa diverja cuando esa especie se agota, así que el motor no puede
garantizar un resultado acotado. Rechazarlo es mejor que devolver un
infinito.

### Arrhenius referenciado, y por qué no es estético

$$ k(T) = k_{ref}\,\exp\!\left[-\frac{E_a}{R}\left(\frac{1}{T}-\frac{1}{T_{ref}}\right)\right] $$

frente a $A\,e^{-E_a/RT}$. En la forma clásica $A$ tiene magnitudes
absurdas ($10^{13}$ y más) y el exponente vale −20 o −40, así que la
expresión **resta números enormes para dar uno pequeño**. En la
referenciada $k_{ref}$ está a escala humana y el exponente ronda cero
cerca de $T_{ref}$. Se admiten las dos —los datos de la literatura vienen
en la clásica— y se declara cuál se usó.

### La base de la actividad, y las unidades de $k$

| Base | $a_i$ |
|---|---|
| `actividad` | $x_i\gamma_i(T,\mathbf{x})$, con UNIFAC |
| `fraccion_molar` | $x_i$ |

Las dos son **adimensionales**, y eso resuelve de un golpe el problema de
que las unidades de $k$ dependan del orden global: **$k$ lleva las
unidades de la tasa y punto**. Su unidad declara además la base
(integrada o volumétrica), igual que en una tasa dada.

La base en concentración **no está**: necesitaría el volumen molar de la
mezcla, que es otra decisión de modelo, y tomarla por cuenta propia sería
elegir un modelo por el usuario.

### La inversa, y la consistencia termodinámica

Con dos leyes, las brutas se conocen por construcción. Y hay un tercer
camino:

$$ k_{inv} = \frac{k_{dir}}{K_{eq}(T)} $$

Eso **sí** es termodinámicamente consistente: en el equilibrio $r^+ = r^-$
obliga a que la razón de las constantes sea $K_{eq}$, y ésa es la
restricción que impone la termodinámica. Es el único modo en que una
reversible lo es sin dos juegos de datos cinéticos independientes.

Con dos avisos que la respuesta declara:

- $K_{eq}$ sale de **van't Hoff**, que supone $\Delta H_{rxn}$ constante
  con la temperatura. Reutiliza
  [`thermodynamics/reaccion.py`](09-reactor-cstr.md) en vez de reescribirlo.
- La ley directa pasa a usar los **exponentes de la estequiometría**,
  porque mezclar órdenes libres con una inversa derivada del equilibrio
  rompería la consistencia: la razón $r^+/r^-$ dejaría de ser $K_{eq}$.

### Y la corrección que el contrato pedía

**Imponer $r^+ = r^-$ no demuestra equilibrio termodinámico.** Describe un
estado estacionario con esas dos tasas, nada más. El equilibrio se calcula
de $\Delta G$ y $K$, y eso no está implementado. El preset
`reactor-en-equilibrio` se llama así porque sus tasas son iguales, no
porque el motor haya comprobado un equilibrio.

---

## 15.9quater Energía acoplada, y un hueco que tenía

### El modo adiabático no existía

`_comprobar_modos` exigía temperatura impuesta **o** calor impuesto, y con
el supuesto adiabático no hay fuente que imponer: la especificación **es**
$\dot Q = 0$, y la temperatura es la incógnita. Un volumen adiabático no
se podía resolver, y el diagnóstico decía «no se impuso ni la temperatura
ni el calor» — que era falso.

Es el mismo error que §15.6 corrige en el otro sentido —la **ausencia** de
una fuente no es $\dot Q = 0$— cometido al revés: **la presencia del
supuesto sí es una especificación**, y no se estaba leyendo como tal.

Ahora hay tres modos, y siguen siendo excluyentes por la misma razón
estructural de §15.3:

| Modo | Se impone | Se calcula |
|---|---|---|
| temperatura | $T_{sal}$ | $\dot Q$ |
| calor | $\dot Q$ | $T$ |
| **adiabático** | $\dot Q = 0$, por el supuesto | $T$ |

### Con cinética, T y avance se cierran juntos

$k(T)$ decide el avance y el avance decide el calor que decide $T$.
Resolver uno y luego el otro daría la respuesta de otro problema.

Verificado por dos caminos independientes en la isomerización de butano
adiabática (320 K de entrada, 20 bar):

- imponer la $T$ resultante en modo isotermo da el **mismo** avance:
  86.0894127745747 frente a 86.08941277457478;
- el calor liberado iguala al calentamiento sensible: **818 710.3 W** por
  los dos lados.

---

## 15.9quinquies Los tres algoritmos, y por qué son tres

| Situación | Algoritmo | Por qué ése |
|---|---|---|
| una reacción, $T$ impuesta | `brentq` **acotado** | el intervalo estequiométrico garantiza el cambio de signo |
| varias reacciones, $T$ impuesta | `root`/`hybr` | no hay intervalo que acote un sistema |
| $T$ incógnita | sustituciones sucesivas **y** `least_squares`/`trf` con límites | `least_squares` solo se para donde el cuadrado tiene un mínimo, y ése puede no ser raíz |

### El cambio de signo, con una reacción

En $\xi = 0$ el residuo vale $-r$ (negativo si la reacción avanza) y en el
límite estequiométrico el reactivo se agota, la tasa cae a cero y el
residuo vale $\xi > 0$. Así que hay raíz en el intervalo **físico**, y
`brentq` la encuentra sin ambigüedad. Si no hay cambio de signo, no es un
fallo del solver: es que la ley y la alimentación no se encuentran, y el
diagnóstico lo dice con los dos extremos.

### Por qué con varias no se imponen límites

Los límites de cada reacción suponiendo las otras a cero **no son
conservadores**: dos reacciones pueden consumir el mismo reactivo. Así que
la factibilidad se **comprueba** después en vez de imponerse, y la
respuesta lo declara como restricción. Un límite que no limita es peor que
no tenerlo, porque invita a confiar en él.

### El mínimo local que no era raíz

Esta es la parte que conviene leer despacio, porque el síntoma no apuntaba
al diagnóstico.

`least_squares` minimiza $\lVert F\rVert^2$. En un sistema cuadrado eso
**no** es lo mismo que resolver $F = 0$: puede pararse en un mínimo local
del cuadrado. Y pasaba. Para una reacción exotérmica con sólo ley directa
el resultado era:

$$ \xi = -13.3\ \text{mol/s} \qquad T = 307.8\ \text{K} $$

Avance **negativo** y temperatura **por debajo** de la entrada. Físicamente
imposible, y el solver no estaba roto: estaba haciendo su trabajo sobre una
función cuyo mínimo local pilló primero.

El motivo está en la dirección de descenso desde $(\xi = 0, T = T_{ent})$.
Ahí el residuo de materia vale $-r/F$ y el de energía vale cero, así que
**bajar** la temperatura reduce la tasa y con ella el residuo de materia:

$$ \frac{\partial}{\partial T}\tfrac12\lVert F\rVert^2 \;=\; \underbrace{F_{mat}}_{<0}\cdot\underbrace{\frac{\partial F_{mat}}{\partial T}}_{<0} \;>\; 0 $$

El gradiente apunta a $T$ **menor**, que es exactamente al lado contrario
de donde está la solución de una exotérmica.

Antes de eso, con `root`/`hybr` —que no acepta límites— el fallo era otro:
con la tasa creciendo como $e^{-E_a/RT}$, el primer paso se iba a
temperaturas sin sentido y desde allí no volvía. El residuo no tenía nada
de malo; medido en una rejilla es suave, monótono y tiene solución. Lo que
faltaba era **impedir que el solver mirara donde el modelo no existe**.

### La solución: arrancar donde arrancaría un ingeniero

Sustituciones sucesivas, alternando los dos problemas que **sí** se
resuelven de forma robusta porque cada uno es escalar y acotado:

1. con $T$ fija, el avance (`brentq`, con cambio de signo garantizado);
2. con el avance fijo, la $T$ (`brentq` sobre el dominio de la tabla de
   entalpía, invirtiendo el balance de energía).

Eso converge en pocas vueltas y deja el punto cerca. Después
`least_squares` **acotado** lo pule y **mide** el residuo final.

**Las dos cosas se declaran.** Decir solo «least_squares» ocultaría de
dónde salió el punto de partida, y el punto de partida es la mitad del
problema cuando hay mínimos locales.

### Los límites, y de dónde salen

La temperatura se acota al **dominio de la tabla de entalpía** —para
butano, 200–399.7 K— que es donde el modelo existe. No es un número
elegido: es `CalculadoraEntalpia.T_min/T_max`.

Y si la solución se queda **en** un límite, `convergio` es `false`: una
solución en la pared no es un estado estacionario, significa que el
sistema pide salirse del dominio del modelo. Detectarlo y decirlo es la
diferencia entre un resultado y un número.

---

## 15.9sexies El catálogo de sustancias

Dos preguntas que `/componentes/buscar` no contestaba.

### Una fórmula no identifica una sustancia

| Consulta | Resuelve a | $T_b$ |
|---|---|---|
| `C2H6O` | **dimethyl ether** | 248.4 K |
| `ethanol` | ethanol | 351.6 K |

Las dos tienen fórmula C2H6O: **103 K de diferencia** por escribir la
fórmula. Y el cálculo sale perfectamente bien para la sustancia
equivocada, que es lo peor que puede pasar.

El índice de fórmulas de `chemicals` asocia cada fórmula a **una** sola
sustancia, así que ya eligió por su cuenta y no sirve para avisar. Se
barre la base entera —76 522 entradas, 8 ms— y se devuelven los
candidatos. Ocho milisegundos es baratísimo al lado de no poder avisar.

El **id estable es el CAS**: el nombre tiene sinónimos y la fórmula es
ambigua.

### Tener grupos UNIFAC no basta para reaccionar

Hace falta además la entalpía de formación, y hay sustancias que tienen lo
primero y no lo segundo. El **diciclopentadieno** es el caso que lo
destapó: UNIFAC sí, `Hfm` no. Sirve para un ELV y no para un balance
reactivo, y enterarse al resolver —cuando el calor de reacción sale NaN—
es tarde.

Así que las capacidades se declaran una por una, con lo que falta en cada
caso:

| Capacidad | Necesita |
|---|---|
| `elv` | grupos UNIFAC |
| `entalpia` | + $C_p$ del líquido |
| `reaccion` | + entalpía de formación |
| `equilibrio` | + energía de Gibbs de formación |

Y se comprueba **la misma propiedad que el motor usa luego**, no una
parecida: `entalpias_formacion_liquido()` lee `Hfm`, así que el catálogo
mira `Hfm`. Comprobar otra daría un apto que luego falla.

---

## 15.9septies Balanceo exacto, y por qué exacto

$A\cdot\nu = 0$ resuelto con `fractions.Fraction` y eliminación de Gauss
sobre los racionales.

**Por qué no numérico.** La respuesta correcta son enteros pequeños, y un
método numérico los devuelve como `0.9999999999999998`. Con SVD se obtiene
una base del espacio nulo en floats y luego hay que *reconocer* los
enteros, que es adivinar: `0.333333` puede ser 1/3 o el redondeo de otra
cosa. Con `Fraction` no hay nada que reconocer — los coeficientes **son**
racionales, y se escalan al mínimo entero multiplicando por el mcm de los
denominadores y dividiendo por el mcd de los numeradores.

El residuo elemental sale **exactamente 0**, no $10^{-16}$.

### Las tres respuestas, y las tres importan

| Dimensión del espacio nulo | Qué significa |
|---|---|
| 0 | No hay reacción. Estas especies no se combinan conservando los elementos, y decirlo **es** la respuesta |
| 1 | Una reacción, única salvo escala y signo |
| > 1 | Un **subespacio**: la conservación no determina una reacción. Se devuelve la base entera |

El tercero no es raro: `CO/CO₂/H₂/H₂O/CH₄` da **dimensión 2** —
desplazamiento de gas de agua y metanación. Devolver una cualquiera sería
elegir qué química ocurre.

### El signo no lo decide la conservación

$A\nu = 0$ se cumple igual con $\nu$ y con $-\nu$: la conservación de
elementos no sabe qué es reactivo. Se admite una pista y, sin ella, se
orienta por convención y **se dice que es una convención**. Suponer una
dirección en silencio es cómo una reacción sale escrita al revés sin que
nadie se entere.

### Y no necesita el proveedor

Balancear **es** la conservación de los átomos: hace falta la composición
elemental y nada más. El servicio construía un `ProveedorTermodinamico`
completo, que exige grupos UNIFAC, y eso excluía la combustión del
metano — el ejemplo canónico de un balanceo. Ahora los átomos se resuelven
por el camino corto y el proveedor se deja para quien lo necesita, con
`aptas_para_termodinamica` avisando de que esa reacción no se puede
calcular.

---

## 15.9octies Equilibrio químico calculado

### La advertencia que da sentido al módulo

**Imponer $r^+ = r^-$ no demuestra equilibrio termodinámico.** Describe un
estado estacionario con esas dos tasas, nada más: dos constantes
cinéticas cualesquiera lo producen. El equilibrio exige

$$ Q_r = K_r(T) \qquad\Longleftrightarrow\qquad \Delta G_{rxn} = 0 $$

y $K$ sale de $\Delta G$ de **formación**, no de ninguna cinética.

Está medido en la suite por los dos lados: una cinética consistente
(`desde_equilibrio`) llega al equilibrio calculado, y una que no lo es
para en otro sitio — $k_1/k_2 = 2.5$ frente a $K = 2.38$.

### K(T): dos rutas y la diferencia medida

$$ \text{van't Hoff:}\quad K(T) = K(T_{ref})\exp\!\left[-\frac{\Delta H(T_{ref})}{R}\left(\frac1T-\frac1{T_{ref}}\right)\right] $$

supone $\Delta H$ **constante** con la temperatura. La ruta rigurosa:

$$ \Delta H(T) = \Delta H(T_{ref}) + \int \Delta C_p\,dT \qquad \Delta S(T) = \Delta S(T_{ref}) + \int \frac{\Delta C_p}{T}\,dT $$
$$ \Delta G(T) = \Delta H(T) - T\,\Delta S(T) \qquad K = e^{-\Delta G(T)/RT} $$

Se devuelven **las dos**, con la diferencia relativa medida. Con los
xilenos a 400 K es del **2.5 %**, y con los butanos el $C_p$ pasa de 142 a
211 J/(mol·K) entre 300 y 400 K: la aproximación no es inocua.

### Un detalle que ahorra una integral

$\Delta H(T)$ **no hace falta integrarla**:

$$ \Delta H_{rxn}(T) = \nu\cdot\left(H_f + h_{sens}(T)\right) $$

Las entalpías sensibles del motor ya la llevan dentro, porque
$\nu\cdot h_{sens}(T)$ es exactamente la integral de $\Delta C_p$ que
Kirchhoff pide. Es la **misma identidad** que explica por qué el balance de
energía no debe corregir $\Delta H$ con Kirchhoff (§15.9bis): allí lo
contaría dos veces, y aquí lo da gratis.

La integral que sí hace falta es la de la **entropía**, $\Delta C_p/T$,
que no está tabulada.

### El criterio de estabilidad

$\Delta G = 0$ dice que es un punto **estacionario** de la energía de
Gibbs, no que sea un **mínimo**. Lo decide la segunda derivada: el
hessiano de $G$ respecto de los avances tiene que ser definido positivo.

Se calcula por diferencias finitas centradas y se devuelven los
**autovalores**, que son el criterio — no una etiqueta. Solo hace falta
derivar la parte de mezcla, $RT\sum n_i\ln a_i$, porque la estándar es
lineal en los avances y no aporta al hessiano.

### Las restricciones, y la que no hace falta

**Las elementales se cumplen por construcción**: un avance sobre una ν
validada conserva los elementos. Añadirlas como ecuaciones habría contado
dos veces lo mismo, y la respuesta lo declara.

**La no negatividad sí hace falta**, y es la parte delicada: una especie en
cero tiene actividad cero y $\ln 0 = -\infty$. El avance se acota al
interior del simplex estequiométrico y las actividades se recortan a un
suelo relativo, **diciendo cuándo se recorta** — porque recortar significa
que el equilibrio empuja a agotar esa especie.

**Y el residuo se mide en $\ln Q - \ln K$.** Con $\Delta G$ de −60 kJ/mol,
$K$ vale $10^{10}$: un residuo $Q - K$ no se puede escalar de forma útil.

---

## 15.9nonies Lote transitorio

$$ \frac{dn_i}{dt} = \sum_r \nu_{ir}\,r_r(T,\mathbf{x}(t)) \qquad n_i(0)=n_{i0} $$

Deja de ser un sistema algebraico —implícito o no— y pasa a ser un sistema
de ODEs. Usa **las mismas leyes de velocidad** que el CSTR: la ley es la
misma física en los dos regímenes, y tener dos implementaciones sería
tener dos físicas que se pueden separar.

### Las cuatro cosas que el contrato pedía

**Estado inicial compatible.** Moles no negativos que sumen algo. Una base
volumétrica necesita el volumen, y si no se da **no se supone 1 m³**.

**Tolerancias declaradas.** `rtol` y `atol` viajan en la respuesta: una
trayectoria sin tolerancia declarada no se puede reproducir ni comparar.

**Agotamiento por EVENTO.** No se detecta mirando si algún número salió
negativo: se detecta con un evento del integrador, que localiza el instante
del cruce con la misma precisión que la trayectoria. Un chequeo a
posteriori sobre los puntos muestreados **se perdería el cruce si cae
entre dos muestras**.

**No negatividad comprobada sobre lo devuelto.** Una ley con órdenes
positivos la respeta sola —la tasa cae a cero cuando el reactivo se
agota— pero el integrador puede pasarse por debajo en un paso. Se recorta
al **evaluar** la ley, porque UNIFAC con fracciones negativas no significa
nada, y se **comprueba** sobre la trayectoria devuelta. Recortar y callarse
convertiría un dato imposible en una curva plausible.

### El integrador, y por qué LSODA por omisión

Una red con constantes muy distintas es **rígida sin avisar**, y LSODA
cambia solo entre no rígido y rígido. `Radau` y `BDF` están para quien ya
sepa que la suya lo es; `RK45` es más rápido si no lo es.

### La verificación: soluciones analíticas

Las redes de **primer orden** las tienen, y las tres topologías que el
contrato nombra son exactamente ésas. Con los xilenos $\gamma = 1$
exactamente, así que la base de actividad correcta coincide con la ideal y
la analítica vale sin aproximar nada.

| Red | Solución | Coincide a |
|---|---|---|
| A → B | $n_A = n_{A0}e^{-kt/N}$ | $10^{-7}$ mol sobre 100 |
| A → B → C | la clásica consecutiva | $10^{-7}$ mol |
| A → B, A → C | $n_A = n_{A0}e^{-(k_1+k_2)t/N}$ | $10^{-7}$ mol |
| A ⇌ B | relajación exponencial a $n_A^\infty$ | $10^{-6}$ mol |

Y dos consecuencias que no son el valor de una curva: el **máximo del
intermedio** cae donde el álgebra lo pone, y la **selectividad** de la
paralela es exactamente $k_1/k_2$.

### Y la comprobación que cruza los dos servicios

Un lote con cinética termodinámicamente consistente converge, cuando
$t\to\infty$, a la **misma** composición que el servicio de equilibrio.
Son dos caminos sin nada en común —uno integra una ODE, el otro resuelve
$\ln Q = \ln K$— y coinciden a $5.6\times10^{-17}$.

Esa coincidencia obligó a un cambio: `desde_equilibrio` usaba van't Hoff y
el lote convergía a una composición **0.5 % distinta** de la que el
equilibrio calculaba. Dos partes del motor contestando cosas distintas a
la misma pregunta es peor que una aproximación declarada, así que
`desde_equilibrio` pasó a la ruta rigurosa.

---

## 15.10 Límites

- **Trabajo de eje y régimen transitorio se rechazan** con diagnóstico.
  Un montaje que el motor no sabe resolver tiene que decirlo en vez de
  devolver números de otro problema.
- **El equilibrio en el ENSAMBLADOR.** `/laboratorio/resolver` no busca
  la composición de equilibrio de un volumen: para eso está
  `/laboratorio/equilibrio` (§15.9octies), que es un servicio aparte.
- **El lote ADIABÁTICO.** El isotermo sí está (§15.9nonies); el adiabático
  añade la ecuación de la energía al sistema de ODEs, y las soluciones
  analíticas con las que se comprueba el isotermo son todas isotermas.
- **El régimen transitorio en el ENSAMBLADOR.** `/laboratorio/resolver`
  sigue exigiendo `estacionario`; el transitorio vive en
  `/laboratorio/lote`, que es un servicio aparte con su propio contrato.
- **Mezclar en un mismo volumen reacciones de tasa dada con reacciones
  cinéticas.** Las primeras se propagan y las segundas exigen resolver un
  sistema; combinarlas necesita un solver que incluya las dos.
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

`tests/validar_laboratorio.py`, trece grupos y **389 comprobaciones**. **Los números no están
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

### Y de la cinética

Los casos de primer y segundo orden en base de fracción molar tienen
**solución analítica**, así que tampoco hay números escritos a mano:

| Caso | Analítico |
|---|---|
| 1.º orden | $\xi = \dfrac{k F_{A0}}{F_0 + k} = 33.3\overline{3}$ |
| 2.º orden | raíz de $F_0^2\xi = k(F_{A0}-\xi)^2$ |
| dos reacciones acopladas | sistema lineal resuelto a mano |

Los tres coinciden a $10^{-9}$ o mejor. Y se comprueba que **lo declarado
es lo que corre**: que una reacción isoterma use `brentq` acotado, que
varias usen `hybr`, que el acoplado declare el arranque **y** el solver, y
que los límites de temperatura vengan de la tabla de entalpía.

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
