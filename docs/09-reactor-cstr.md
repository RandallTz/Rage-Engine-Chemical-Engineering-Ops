# 9. Reactor CSTR

[← FUG](08-fug.md) · [Índice](README.md) · [Siguiente: Destilación reactiva →](10-destilacion-reactiva.md)

---

## 9.1 Qué resuelve

Reactor continuo de tanque agitado en **estado estacionario**, con
mezclado perfecto.

Cumple el mismo estándar que el resto del simulador: **no es
forward-only**. Resuelve en las tres direcciones útiles, y las tres de
forma **exacta** —álgebra, sin iterar—:

| Dirección | Datos | Incógnita |
|---|---|---|
| Adelante | alimentación + avance | salida |
| Atrás | salida + avance | alimentación |
| **Avance** | alimentación + **una** fracción de salida | el avance (y con él, todo lo demás) |

La tercera es la que se usa de verdad: normalmente uno sabe lo que entra y
**qué pureza quiere**, y lo que busca es cuánto tiene que hacer
reaccionar.

---

## 9.2 Balance por componente

$$
\boxed{\;F_{out}\,x_{out,i} \;=\; F_{in}\,x_{in,i} \;+\; \nu_i\,\xi\;}
$$

donde $\xi$ es el **avance de reacción** en mol/s.

### El balance total no se impone aparte

Sumando en $i$ y usando que las fracciones suman 1:

$$
F_{out}\underbrace{\sum_i x_{out,i}}_{=1} = F_{in}\underbrace{\sum_i x_{in,i}}_{=1} + \xi\underbrace{\sum_i \nu_i}_{\nu_{tot}}
\quad\Longrightarrow\quad
F_{out} = F_{in} + \nu_{tot}\,\xi
$$

Sale solo. **Imponerlo aparte sería contar una ecuación de más** y el
medidor de grados de libertad mentiría.

Nótese que $\nu_{tot} \ne 0$ significa que el caudal molar **cambia** al
reaccionar: con $\nu = [-1,-1,+1]$, $\nu_{tot} = -1$ y 100 mol/s con
$\xi = 20$ salen 80 mol/s.

---

## 9.3 Las tres direcciones

### Adelante

$$
F_{out} = F_{in} + \nu_{tot}\,\xi,
\qquad
x_{out,i} = \frac{F_{in}\,x_{in,i} + \nu_i\,\xi}{F_{out}}
$$

### Atrás

La misma ecuación despejada:

$$
F_{in} = F_{out} - \nu_{tot}\,\xi,
\qquad
x_{in,i} = \frac{F_{out}\,x_{out,i} - \nu_i\,\xi}{F_{in}}
$$

Verificado: ida y vuelta recupera caudal y composición a $10^{-12}$.

### Avance desde una fracción de salida

Sustituyendo $F_{out} = F_{in} + \nu_{tot}\xi$ en el balance del
componente $j$:

$$
x_{out,j}\,(F_{in} + \nu_{tot}\,\xi) = F_{in}\,x_{in,j} + \nu_j\,\xi
$$

que es **lineal en $\xi$**:

$$
\boxed{\;\xi = \frac{F_{in}\,(x_{in,j} - x_{out,j})}{x_{out,j}\,\nu_{tot} - \nu_j}\;}
$$

Si el denominador se anula, esa fracción no determina el avance y se pide
la de otro componente (con mensaje explícito, no un fallo mudo).

---

## 9.4 Conversión

Del **reactivo limitante**:

$$
X = \frac{|\nu_{lim}|\,\xi}{F_{in}\,x_{in,lim}}
$$

Si no se dice cuál es el limitante, se toma el reactivo ($\nu_i < 0$) que
se agote antes:

$$
lim = \arg\min_{i:\ \nu_i<0} \frac{F_{in}\,x_{in,i}}{|\nu_i|}
$$

Es invertible: dada $X$ se obtiene $\xi$, que es como se plantea
normalmente un problema de reactores ("quiero 85 % de conversión").

Va en **bloque separado** porque es una *definición*: quien no quiera
razonar en conversión simplemente no la da ni la mira.

---

## 9.5 Cinética

$$
\boxed{\;\xi = V\cdot r(T, \mathbf{x}_{out})\;}
$$

### La composición en la que se evalúa $r$ no es un detalle

En un CSTR el tanque está **perfectamente mezclado**, así que su contenido
es la corriente de **salida**.

> Evaluar la velocidad en el **alimento** es el error clásico, y daría un
> reactor mucho más chico que el real: la velocidad en el alimento es la
> más alta de todo el reactor. Esa es precisamente la diferencia con un
> reactor de flujo pistón, donde la composición sí varía a lo largo.

Invertible en las dos direcciones que importan:

- $V$ dado $\xi$ → **dimensionar** el tanque.
- $\xi$ dado $V$ → **simular** un tanque que ya existe.

Si $r \approx 0$ en la composición de salida (el sistema ya está en
equilibrio químico ahí), **ningún volumen finito** da ese avance. Se dice
así, en vez de devolver un número enorme.

---

## 9.6 Temperatura y presión

$$
T_{salida} = T_{tanque},
\qquad
P_{salida} = P_{entrada}
$$

La primera no es una suposición adicional: es la **definición** del modelo
de tanque perfectamente mezclado.

> **Hueco corregido:** esta igualdad estaba dentro del `if con_cinetica`,
> así que un reactor **sin** cinética no daba temperatura a su salida y
> paralizaba a todo lo que viniera detrás. Se vio montando un reciclo: el
> divisor aguas abajo no podía arrancar. Un tanque tiene temperatura haya
> o no cinética.

---

## 9.7 Balance de energía

Hasta esta versión el reactor era el **único equipo sin balance de
energía**: se le daba $T$ y punto. Eso deja fuera justo lo que hace
interesante a la destilación reactiva — el acoplamiento entre el calor
que suelta la reacción y lo que pasa con la separación.

$$
\boxed{\;F_{in}\,h(T_{in}, \mathbf{x}_{in}) + Q \;=\; F_{out}\,h(T_{out}, \mathbf{x}_{out}) \;+\; \xi\,\Delta H_{rxn}^{\circ}(T_{ref})\;}
$$

$Q < 0$ significa que hay que **retirar** calor.

### La sutileza: por qué $\Delta H_{rxn}$ va en $T_{ref}$ y no en $T_{out}$

Este es el punto fino de toda la sección, y la razón de que el balance no
se pudiera escribir bien hasta que la entalpía se unificó
([§4](04-entalpia.md)).

$h$ mide entalpía **sensible**, con referencia "componentes puros
líquidos a $T_{ref}$ con $h_i = 0$". **No incluye entalpías de
formación.** Escribiendo la entalpía absoluta como
$H_i(T) = \Delta H_{f,i}^{\circ}(T_{ref}) + h_i(T)$ y metiéndola en el
balance verdadero $\sum_{in} n_i H_i(T_{in}) + Q = \sum_{out} n_i H_i(T_{out})$,
con $n_{i,out} = n_{i,in} + \nu_i \xi$, los términos de formación de las
especies que **no** reaccionan se cancelan y queda exactamente la
ecuación de arriba, con $\Delta H_{rxn}^{\circ}$ evaluado en $T_{ref}$.

Lo importante es lo que eso **no** es:

> No es la aproximación "$\Delta H_{rxn}$ constante con la temperatura".

La dependencia con $T$ del calor de reacción ya está contenida en el
término $F_{out}\,h(T_{out}, \mathbf{x}_{out})$, porque ese término
incluye $\sum_i \nu_i h_i(T_{out})$ — que es precisamente la corrección
de Kirchhoff:

$$
\Delta H_{rxn}(T) = \Delta H_{rxn}^{\circ}(T_{ref}) + \sum_i \nu_i\big[h_i(T) - h_i(T_{ref})\big]
$$

Usar $\Delta H_{rxn}(T_{out})$ contaría esa dependencia **dos veces**.

Medido, para que no sea un argumento de pizarra: en el reactor
adiabático de MTBE de la verificación ($\xi = 12$ mol/s, 330 → 383.45 K),
el balance cierra a $1.6\times10^{-9}$ W con $\Delta H_{rxn}^{\circ}$,
y el doble conteo metería **41.31 kW** de error — exactamente
$\xi\sum_i \nu_i[h_i(T_{out}) - h_i(T_{ref})]$, comprobado al vatio.

Que las dos referencias coincidan ($T_{ref} = 298.15$ K en
`CalculadoraEntalpia`, $T_{std} = 298.15$ K en `GestorReaccion`, que es
donde `thermo` da sus $\Delta H_f$) no es casualidad, pero **tampoco se
da por hecho**: se comprueba antes de cada balance. Si alguien
construyera la calculadora con otra referencia, el error se repartiría
en silencio entre $Q$ y $T$ y nadie lo notaría.

---

## 9.8 Los tres modos

Misma filosofía orientada a ecuaciones que el resto: una ecuación, y se
elige qué se da y qué se despeja.

| `modo_energia` | Se da | Se calcula |
|---|---|---|
| `"isotermo"` (por defecto) | $T$ del tanque | $Q$ que cuesta mantenerla |
| `"adiabatico"` | $Q = 0$ | $T$ que resulta |
| `"calor_dado"` | $Q$ [W] | $T$ que resulta |

El modo por defecto es **compatible hacia atrás**: un reactor que antes
solo pedía $T$ sigue funcionando igual. Lo que gana es la respuesta a una
pregunta que el simulador no podía contestar: *cuánta refrigeración
cuesta esa temperatura*. Para MTBE con $\xi = 12$ mol/s son **702 kW**,
y en una exotérmica ese número suele ser la restricción de diseño real.

Sin proveedor termodinámico no hay entalpías y el reactor vuelve a ser
isotermo con $T$ como dato, exactamente como antes. Los otros dos modos
se **rechazan** con un motivo, en lugar de fingir un balance.

---

## 9.9 El caso acoplado: cinética + energía

Con cinética y sin ser isotermo, las dos ecuaciones se necesitan
mutuamente:

$$
\xi = V\,r(T, \mathbf{x}_{out}) \qquad\text{y}\qquad T = T(\xi)
$$

La cinética necesita $T$ para dar $\xi$; el balance de energía necesita
$\xi$ para dar $T$. **Ninguno de los dos puede arrancar.**

El motor de punto fijo del orquestador sólo rellena huecos, así que aquí
se quedaría parado y el síntoma sería *"faltan datos"* —
indistinguible de un diagrama mal planteado. Es el mismo problema que un
reciclo ([§2.7](02-solver.md#27-reciclos-tearing)), y se resuelve igual:
planteando las dos ecuaciones a la vez.

$$
R_1(\xi, T) = \frac{\xi - V\,r(T, \mathbf{x}_{out}(\xi))}{F_{in}},
\qquad
R_2(\xi, T) = \frac{F_{in}h_{in} + Q - F_{out}(\xi)\,h(T, \mathbf{x}_{out}(\xi)) - \xi\,\Delta H_{rxn}^{\circ}}{F_{in}\,|\Delta H_{rxn}^{\circ}|}
$$

Un solo bloque, `_bloque_reactor_acoplado`, **sustituye** a los de
cinética y energía por separado y aporta las mismas 3 ecuaciones, así que
el conteo de grados de libertad no cambia.

### Los dos residuos se adimensionalizan

No es cosmético. Sin normalizar quedan en unidades distintas (mol/s
frente a W) y separados por ~$10^6$ en magnitud: `hybr` reparte su
esfuerzo según la norma del vector, así que el residuo de materia se
vuelve invisible frente al de energía, y un criterio de parada único no
significa lo mismo para los dos. Con ambos adimensionales,
*"residuo $< 10^{-9}$"* quiere decir lo mismo en las dos ecuaciones:
error relativo.

### El arranque tímido era el error

La primera versión partía de un único punto "prudente": 1 % del límite
estequiométrico, $T = T_{in}$. Con una exotérmica fuerte el estacionario
está lejos, `hybr` no lo alcanza, y el método reportaba *"no convergió"*
cuando **sí había solución**.

Medido con $A = 10^{10}$ y $V = 2$ m³: desde el arranque tímido fallaba,
y desde 10 de 15 arranques distintos convergía siempre al mismo
$\xi = 9.4699$ mol/s, $T = 372.66$ K.

Ahora se prueban varios, y **no son arbitrarios**: para cada avance de
prueba se calcula la $T$ que le corresponde *por balance de energía*, o
sea que cada arranque ya satisface $R_2$ y al solver sólo le queda
arreglar la cinética. Se barre una curva, no un plano.

### Multiplicidad de estados estacionarios

Un CSTR exotérmico puede tener **más de un** estado estacionario — el
fenómeno clásico de ignición/extinción. Si aparece, no se elige en
silencio: se devuelve el **más frío** (el que alcanza un arranque en
frío, que es lo que físicamente pasa al poner en marcha el equipo) y se
listan todos en `soluciones`, con la bandera `multiplicidad`.

> **Límite honesto:** que una solución exista y sea estacionaria **no
> significa que sea estable** en la planta real. Este es un modelo
> estacionario y no responde esa pregunta; hace falta el análisis
> dinámico, que no está implementado.

---

## 9.10 El tanque no puede estar hirviendo

Un CSTR de este simulador es un tanque **líquido**: la cinética usa
actividades $a_i = x_i\gamma_i$, que son de fase líquida, y la entalpía
del balance es $h_L$.

Si la $T$ que sale del balance queda por encima del punto de burbuja a la
presión de operación, el tanque estaría hirviendo y el modelo deja de
describirlo. Es exactamente el patrón de fallo que persigue este proyecto
—un número plausible sobre algo físicamente imposible— así que **se
comprueba** en vez de confiar.

No es un caso rebuscado. El propio reactor adiabático de MTBE de la
verificación **hierve a 10 atm**: da 383.45 K contra una burbuja de
357.54 K. A 30 atm la burbuja sube a 413 K y el modelo vuelve a ser
válido. Con `exigir_liquido=False` se devuelve el número igualmente,
junto con la $T$ de burbuja, para quien sepa lo que está mirando.

---

## 9.11 Varias entradas

Un reactor real recibe más de una corriente: alimentación fresca +
reciclo + inyección de reactivo.

Se resuelve **mezclándolas dentro del propio equipo**, en una corriente
interna, reutilizando el mezclador que ya existe y ya está probado —
incluido su balance de energía. Así el reactor no reimplementa nada y el
caso de una sola entrada sigue siendo exactamente el de antes (no pierde
invertibilidad).

La corriente interna se marca con `#` y no se le muestra al usuario, que
no la ha dibujado.

Verificado con tres entradas a temperaturas distintas: GL = 0 y los
balances por componente cierran sobre la suma de las tres.

---

## 9.12 Guardas físicas

$$
F_{out} \le 0 \;\Rightarrow\; \text{avance imposible con este alimento}
$$

$$
x_i < 0 \;\Rightarrow\; \text{"no se puede consumir más de lo que hay"}
$$

Ambas se comprueban y se explican con el componente y el valor concretos,
no con un error genérico.

---

## 9.13 Grados de libertad

Para $n$ componentes, un reactor con cinética aporta:

| Bloque | Ecuaciones |
|---|---|
| Balance por componente | $n$ |
| Conversión (definición) | 1 |
| Cinética | 1 |
| Balance de energía + definición de $Q_{reaccion}$ | 2 |
| $T_{salida} = T_{tanque}$ | 1 |
| $P_{salida} = P_{entrada}$ | 1 |

Variables propias: $\xi$, $X$, $V$, $T$, $Q$, $Q_{reaccion}$.

En el modo **acoplado** (cinética + no isotermo) el bloque conjunto
sustituye a los de cinética y energía, y aporta las mismas 3 ecuaciones
que aportaban entre los dos, así que el conteo no cambia. En los modos
`adiabatico` y `calor_dado`, $Q$ deja de ser variable libre y la aporta
un bloque de valor fijo — es $T$ la que pasa a calcularse.

Verificado: GL = 0 en el caso bien planteado, y **GL = $-1$ al dar una
fracción de más** — el contador detecta el dato sobrante, que es lo que
debe hacer.

---

## 9.14 Verificación

Sistema MTBE, $\nu = [-1, -1, +1]$, 100 mol/s equimolar, $\xi = 20$:

| Comprobación | Resultado |
|---|---|
| $F_{out} = F_{in} + \nu_{tot}\xi$ | 80 mol/s ✓ |
| $\sum x_{out} = 1$ | ✓ |
| Balance de cada componente | cierra ✓ |
| Ida y vuelta (adelante → atrás) | recupera $F$ y $\mathbf{x}$ a $10^{-12}$ ✓ |
| Avance deducido desde $x_{MTBE}$ | 20.0000000000 ✓ |
| Conversión | 0.4 exacto (entran 50, se consumen 20) ✓ |
| Avance mayor que el reactivo disponible | rechazado con motivo físico ✓ |
| Dimensionado: $X = 0.4$ → $\xi$ → $V$ | consistente ✓ |

### Balance de energía

Sistema MTBE a 30 atm, 100 mol/s, $\mathbf{x}_{in} = [0.45, 0.45, 0.10]$,
$T_{in} = 330$ K. $\Delta H_{rxn}^{\circ} = -57.60$ kJ/mol.

| Comprobación | Resultado |
|---|---|
| Ida y vuelta isotermo → calor dado | recupera $T$ a $10^{-10}$ K |
| Ida y vuelta adiabático → isotermo | devuelve $Q = 1.7\times10^{-9}$ W |
| Con $\xi = 0$, el reactor es un intercambiador | $Q$ coincide con $F(h_2-h_1)$ |
| Sin reacción y sin calor, $T$ no cambia | exacto |
| Exotérmica isoterma → hay que refrigerar | $Q = -702.4$ kW |
| Exotérmica adiabática → la $T$ sube | 330.00 → 383.45 K |
| Endotérmica (mismo sistema, $\Delta H$ invertido) | $T$ baja, $Q > 0$ |
| $Q_{exo} - Q_{endo} = 2\xi\Delta H_{rxn}$ | $-1382400.0000$ W exacto |
| Duplicar $Q$ duplica el salto de entalpía | exacto |
| **El balance cierra con $\Delta H_{rxn}(T_{ref})$** | residuo $1.6\times10^{-9}$ W |
| **Usar $\Delta H_{rxn}(T_{out})$ no cerraría** | 41.31 kW de error, igual al término duplicado al vatio |

En el flowsheet, el balance leído del pool cierra a $0$ exacto (isotermo)
y a $2\times10^{-9}$ W (adiabático acoplado).

### Caso acoplado

Con $A = 10^{10}$, $E_a = 60$ kJ/mol, adiabático:

| $V$ [m³] | $\xi$ [mol/s] | $T$ [K] |
|---|---|---|
| 0.5 | 1.369 | 336.37 |
| 1.0 | 7.237 | 362.90 |
| 2.0 | 9.470 | 372.66 |
| 4.0 | 10.049 | 375.15 |

Más volumen → más avance y más temperatura, y la cinética y el balance
evaluados **por separado** reproducen $\xi$ y $T$ a $10^{-9}$.

**La comprobación cruzada más fuerte** ata tres piezas independientes: el
balance de energía (que fija $T$), van't Hoff (que da $K_{eq}$ a esa $T$)
y el término inverso de la cinética. Con $V$ grande, $r \to 0$ y la
salida tiene que estar en equilibrio químico *a la temperatura que el
propio balance produjo*:

| $V$ [m³] | $\prod_i a_i^{\nu_i}$ | $K_{eq}(T)$ | cociente |
|---|---|---|---|
| 1 | 0.40000 | 1.14403 | 0.3496 |
| 8 | 0.54549 | 0.58323 | 0.9353 |
| 40 | 0.55509 | 0.56227 | 0.9872 |

Y eso explica la forma de la tabla anterior: con una exotérmica, subir
$T$ **baja** $K_{eq}$ (van't Hoff), así que **el calor que libera la
reacción limita su propia conversión**. Por eso $\xi$ se satura en
~10.3 mol/s y no sigue creciendo con $V$.

---

## 9.15 Límites

- **Tanque líquido monofásico.** La cinética usa actividades de fase
  líquida. Si el balance da una $T$ por encima del punto de burbuja, se
  rechaza en vez de devolver un número que el modelo no respalda
  ([§9.10](#910-el-tanque-no-puede-estar-hirviendo)).
- **Estacionario, no dinámico.** Que un estado estacionario exista no
  implica que sea **estable**: la multiplicidad se detecta y se reporta,
  pero el análisis de estabilidad necesita el modelo dinámico, que no
  está implementado.
- **Una sola reacción.** No hay reacciones en paralelo ni en serie.
- **Mezclado perfecto.** No hay zonas muertas ni cortocircuitos.
- **Sin caída de presión.**
- **Solo CSTR.** No hay PFR ni reactor batch.

---

[← FUG](08-fug.md) · [Índice](README.md) · [Siguiente: Destilación reactiva →](10-destilacion-reactiva.md)
