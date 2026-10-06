# 2. El solver

[← Arquitectura](01-arquitectura.md) · [Índice](README.md) · [Siguiente: Termodinámica →](03-termodinamica.md)

---

## 2.1 El objeto central: `BloqueEcuaciones`

Un bloque es **una ecuación o un sistema pequeño de ecuaciones**, con
cuatro datos:

| Campo | Significado |
|-------|-------------|
| `variables` | Todas las variables que toca, entrada y salida |
| `variables_entrada` | Subconjunto cuyas incógnitas deciden **si el bloque puede dispararse** |
| `puede_resolver(k)` | `True` si el bloque sabe resolverse con $k$ incógnitas de entrada |
| `resolver_fn(**conocidos)` | Resuelve y devuelve un diccionario con lo que ha podido calcular |
| `n_ecuaciones` | Cuántas ecuaciones **independientes** aporta (solo para contar grados de libertad) |

### Bloques invertibles vs. no invertibles

La distinción es la clave del diseño.

**Invertible** — cualquiera de sus variables puede ser la incógnita.
`variables_entrada = variables`.

> `BalanceMateriaGlobal`: 2 ecuaciones, 6 variables, resuelve cualquier 1
> o 2 incógnitas. `puede_resolver = lambda k: 1 <= k <= 2`.
>
> `McCabe-Thiele`: 1 ecuación $N = f(z_F, q, x_D, x_B, R)$, 6 variables,
> resuelve cualquier 1 incógnita. `puede_resolver = lambda k: k <= 1`.

**No invertible** — dadas todas sus entradas, calcula todas sus salidas de
una pasada; no hay forma de pedirle el camino contrario.

> `Cargas Térmicas`: dadas $(D, B, F, z_F, x_D, x_B, R, q)$ calcula
> $(Q_c, Q_R, R_{int}, \bar{V}, T_D, T_B)$. No se le puede pedir $D$ dado
> $Q_c$. `puede_resolver = lambda k: k == 0`, contando solo las entradas.

Para un bloque no invertible, **sus salidas nunca cuentan como incógnitas
que bloquean el disparo**. Sin esa distinción, un bloque de este tipo
nunca se dispararía: siempre tendría sus propias salidas como incógnitas.

---

## 2.2 El bucle de punto fijo

```python
mientras (hubo cambio) y (iteraciones < tope):
    para cada bloque:
        si el bloque no tiene incógnitas:  saltar
        si no puede_resolver(incógnitas de entrada):  saltar
        resultado = bloque.resolver_fn(**lo que se sabe)
        escribir en el pool SOLO las variables que estaban vacías
```

Tres propiedades que importan:

**Solo rellena, nunca reescribe.** Si una variable ya tiene valor, ningún
bloque la pisa. Esto hace el bucle **monótono**: el conjunto de variables
conocidas solo crece, así que el bucle no puede oscilar y termina siempre.

**El orden de los bloques no cambia el resultado.** Verificado: una cadena
de 20 reactores da exactamente los mismos números con los bloques
ordenados aguas arriba→abajo que al revés. Lo que sí cambia es cuántas
pasadas hacen falta.

**Un bloque que falla no tumba el diagrama.** Su excepción se anota y se
sigue con los demás; puede que en una pasada posterior ya tenga los datos
que necesitaba.

### El tope de iteraciones

$$
\text{tope} = |\text{bloques}| + 2
$$

No es una constante arbitraria. En el peor orden posible (bloques de aguas
abajo primero) cada pasada propaga **un** bloque, así que una cadena de
$N$ operaciones necesita $\approx N+2$ pasadas. Medido:

| Operaciones | Bloques | Pasadas (orden favorable) | Pasadas (orden adverso) |
|---|---|---|---|
| 10 | 61 | 12 | 13 |
| 30 | 181 | 32 | 33 |
| 120 | 721 | 122 | 123 |

Con el tope fijo anterior (30) **un diagrama de ~29 equipos se quedaba a
medias**, y el síntoma era indistinguible de "faltan datos": `completo =
False`, cero inconsistencias, cero errores, y el contador de grados de
libertad diciendo GL = 0. Se le decía al usuario que sus datos estaban
bien, no se resolvía, y no se daba ningún motivo.

Ahora, si el tope llega a agotarse, se reporta explícitamente diciendo que
el límite es del solver y **no** de los datos.

### El detalle de `cambio`

`cambio = True` solo si el bloque **escribió algo**. Parece trivial y no
lo es: muchísimos bloques devuelven `{}` cuando todavía no pueden decidir
una dirección (el balance del CSTR, el cierre de composición con dos
huecos, la cinética sin temperatura). Marcando `cambio` por el mero hecho
de que el bloque *corriera*, el bucle nunca terminaba antes de tiempo —
agotaba siempre el tope aunque llevara rato sin avanzar.

---

## 2.3 Grados de libertad

$$
\mathrm{GL} = (\text{incógnitas}) - (\text{ecuaciones})
$$

- $\mathrm{GL} > 0$: faltan datos.
- $\mathrm{GL} = 0$: exactamente especificado.
- $\mathrm{GL} < 0$: sobran datos (hay que comprobar que sean compatibles).

Es un conteo **estático**, sin resolver nada, lo bastante barato para
llamarlo mientras el usuario escribe.

### El descuento por composiciones dependientes

Aquí está la sutileza que más problemas ha dado.

Cada corriente aporta un bloque de **cierre de composición**:

$$
\sum_{i=0}^{n-1} x_i = 1
$$

Si además un bloque calcula el vector de composición **completo** de esa
corriente (las $n$ fracciones como salida), esas $n$ escrituras **no son
$n$ ecuaciones independientes sino $n-1$**: las fracciones que produce ya
suman 1 por construcción, y esa ecuación ya la aporta el cierre. Contar
las $n$ sería contarla dos veces.

Durante mucho tiempo esto se compensó **a mano** dentro de cada bloque
(en FUG estaba escrito literalmente `n_ecuaciones = len(variables_salida) - 2`).
Funcionaba solo en los bloques que alguien había revisado: el mezclador y
el divisor nunca se corrigieron, y **cualquier diagrama que los usara
reportaba GL negativo estando bien planteado** (medido: $-2$ con un
divisor, $-5$ con seis equipos).

Ahora el descuento es **estructural**: se recorren las salidas declaradas
de cada bloque y, por cada corriente cuyo vector de composición completo
esté entre ellas, se resta 1.

$$
\text{ecuaciones} = \sum_b n_{ec}(b) \;-\; \#\{(b, s) : \{s.x_0,\dots,s.x_{n-1}\} \subseteq \mathrm{salidas}(b)\}
$$

Cualquier bloque futuro lo hereda sin que haya que acordarse de nada.

### Los registros de presión y temperatura

Una corriente que **sale** de un equipo y **entra** en otro puede recibir
dos ecuaciones para la misma variable: el reactor fija la $P$ de su salida
y la columna vuelve a fijar la $P$ de su alimentación. El contador decía
GL negativo con el problema bien planteado.

`DiagramaCorrientes` lleva dos registros, `_presion_fijada` y
`_temperatura_fijada`: el segundo equipo no vuelve a poner una ecuación
sobre lo que ya está fijado.

---

## 2.4 Redundancias: *dónde* sobran los datos

El GL global es un agregado y **no ve la distribución**. Se puede tener
$\mathrm{GL} < 0$ y a la vez variables sin determinar, porque los datos de
más están en una ecuación y los que faltan hacen falta en otra.

Por cada bloque:

$$
\text{sobran}(b) = \#\{\text{variables conocidas de } b\} - \big(|{\rm variables}(b)| - n_{ec}(b)\big)
$$

Dos detalles que costaron encontrarse:

**Se compara contra el pool resuelto, no contra los datos crudos.** Una
variable cuenta como conocida tanto si el usuario la escribió como si otro
bloque ya la determinó. Sin esto, un caudal dado en masa (que llega por un
camino indirecto) era invisible y el balance de materia parecía *falto* de
datos cuando estaba *sobrado*.

**Un bloque no cuenta su propia salida como dato de más.** Si se contara,
cualquier bloque que terminara de resolverse aparecería como redundante.
Se excluye usando `resueltos_por`.

---

## 2.5 Verificación de consistencia

El bucle **salta los bloques sin incógnitas** ("no hay nada que
resolver"). Consecuencia: si el usuario da *todas* las variables de una
ecuación, esa ecuación nunca se evalúa y nadie se entera de que los datos
no la cumplen.

Caso real que lo destapó: $F=100$, $z_F=0.5$, $D=20$, $x_D=0.8$, $B=80$,
$x_B=0.1$ cierra el balance total ($100 = 20+80$) pero **viola el de
componente por 26 mol/s** — y el simulador reportaba "resuelto por
completo".

El método es genérico y reutiliza el propio solver del bloque: por cada
bloque completo se *olvida* una variable, se recalcula con las demás, y se
compara.

$$
\frac{|v_{dado} - v_{recalculado}|}{\max(|v_{dado}|, |v_{recalc}|, 1)} > \varepsilon
\quad\Rightarrow\quad \text{inconsistencia}
$$

con $\varepsilon = 10^{-6}$. Se prefiere olvidar una variable de **salida**,
para que los bloques no invertibles también se puedan comprobar.

### Un bloque no es una ecuación

Durante un tiempo esta verificación comparaba **solo** la variable
olvidada y paraba en cuanto una comprobación salía bien, con el
razonamiento de que *«una comprobación por bloque es suficiente»*. Eso
vale si cada bloque es una ecuación, y **varios no lo son**:

| Bloque | Ecuaciones que empaqueta |
|---|---|
| Bombeo | $n+2$ ($F$, $T$, $P$ y las composiciones) |
| Mezclador | 5 |
| Divisor | 10 |

Caso real: una bomba ideal con $P_1 = 101325$, factor $= 3$ **y**
$P_2 = 100000$ dados a la vez. Tres condiciones sobre dos variables, y
$3 \times 101325 \neq 100000$. La comprobación recaía sobre la igualdad de
caudales, salía bien, y **la ecuación de presión no se evaluaba nunca**:
el servicio respondía «resuelto por completo», sin incidencias,
conservando la presión de salida dada.

Ahora se compara **todo lo que el bloque devuelve** y se sigue hasta
haber verificado tantas variables distintas como ecuaciones declara el
bloque. No cuesta llamadas extra: el solver de la bomba ya escribía
$P_2 = 303975$ al olvidar otra variable; simplemente nadie miraba ese
valor.

Esto expuso un segundo error, de signo. La bomba declaraba
`n_ecuaciones = 1` mientras imponía $n+2$, así que una bomba exactamente
especificada reportaba $\mathrm{GL} = +3$ y una sobreespecificada
$\mathrm{GL} = +1$: **decía que faltaban datos cuando sobraban.**

### Una incompatibilidad no hace `completo = false`

La política es explícita: `completo` dice que **todas las variables
quedaron determinadas**, no que el resultado sea físico. Un diagrama
puede quedar completo y a la vez tener datos que se contradicen, y en
ese caso la incompatibilidad viaja en su propio campo
(`inconsistencias`, y en `diagnosticos` con severidad de error). La
bandera que separa «se calculó todo» de «el resultado es válido» es
`resumen_diagnosticos.hay_errores` — ver [§14.3](14-trazabilidad.md).

---

## 2.6 Errores rancios

Un bloque puede fallar en una pasada temprana (todavía sin datos) y
acertar en una posterior. Su mensaje viejo quedaba registrado y se
reportaba al usuario como una ecuación violada.

Se descarta el error de cualquier bloque que acabara resolviendo algo: si
resolvió, su error ya no describe el estado final.

---

## 2.7 Reciclos (tearing)

### El problema

El bucle de punto fijo solo rellena huecos y nunca reescribe. Eso lo hace
inmune a oscilar, pero significa que **un lazo no tiene por dónde
empezar**: cada corriente del lazo espera a la anterior y ninguna arranca.

El síntoma era "faltan datos", indistinguible de un problema mal
planteado.

### La solución: cortar

Es la técnica estándar. Se elige una corriente del lazo, se **supone**, se
resuelve el diagrama entero como si fuera abierto, y se compara el valor
que sale por el otro extremo con el supuesto. Se repite hasta que
coincidan.

```
fresco ──→ [mez1] ──→ [r1] ──→ [div1] ──┬──→ producto
              ↑                          │
              └────── reciclo ───────────┘
                         ✂ corte
```

Formalmente, si $\mathbf{s}$ es el vector de variables de la corriente
cortada y $g(\mathbf{s})$ es el resultado de resolver el diagrama abierto
partiendo de ese supuesto, se busca el punto fijo

$$
\mathbf{s}^{*} = g(\mathbf{s}^{*})
$$

### Cómo se implementa el corte

Redirigiendo las **salidas** de quien produce la corriente cortada hacia
un alias interno:

$$
\texttt{reciclo.F} \;\longrightarrow\; \texttt{reciclo\#calc.F}
$$

Así, en el diagrama roto **nadie escribe** `reciclo`, y su valor es el
supuesto. Se reutiliza `renombrar_bloque`, el mismo mecanismo con el que
las operaciones ya apuntan a las corrientes: **no hubo que tocar ningún
bloque**.

Las variables con `#` son maquinaria interna y no se le muestran al
usuario, que no las ha dibujado.

### Detección de lazos

Se construye el grafo operación→operación ($A$ precede a $B$ si una salida
de $A$ es entrada de $B$) y se buscan ciclos por DFS. Por cada ciclo se
corta **una** corriente.

### Elección del corte: no es indiferente

Matemáticamente da igual qué corriente del lazo se corte. **Numéricamente
no.**

La primera implementación elegía por frecuencia y escogió `mezcla` — la
*salida* del mezclador, que ya lleva la alimentación fresca. Suponerla con
$F = 0$ daba caudal cero al reactor, y el avance pedido resultaba
imposible.

El criterio correcto:

> Preferir la corriente cuyo **consumidor** recibe además algo de **fuera
> del lazo**.

Esa entrada externa ancla la solución. Con ella se corta `reciclo`, y
suponer $F = 0$ significa *"arrancar la planta sin recirculación"* — que
es físicamente lo que pasa.

### Estimación inicial

$$
F = 0, \qquad x_i = \tfrac{1}{n}, \qquad
T = \max_j T_j, \qquad P = \max_j P_j
$$

$F = 0$ es el punto de partida más seguro: no inventa materia que no
existe. La presión **no** puede ser 0 porque el mezclador toma el mínimo
de sus entradas y arruinaría el resultado.

### Aceleración de Wegstein

La sustitución sucesiva pura ($\mathbf{s} \leftarrow g(\mathbf{s})$)
converge, pero despacio cuando el reciclo es grande. Wegstein extrapola a
partir de las dos últimas iteraciones:

$$
s = \frac{g_k - g_{k-1}}{x_k - x_{k-1}}, \qquad
q = \frac{s}{s-1}, \qquad
x_{k+1} = q\,x_k + (1-q)\,g_k
$$

$q$ se acota a $[-8,\ 0.95]$: la extrapolación sin límites dispara el
supuesto fuera de lo físico (caudales negativos) en las primeras vueltas,
cuando todavía no hay una pendiente fiable.

Medido, en una planta con reactor y recirculación:

| Fracción reciclada | Sustitución sucesiva | Wegstein |
|---|---|---|
| 30 % | 17 vueltas | 3 |
| 50 % | 27 | 3 |
| 70 % | 50 | 3 |
| **90 %** | **154** | **9** |

Misma solución en ambos casos; solo cambia la velocidad.

### Criterio de convergencia

$$
\max_k \frac{|g_k - s_k|}{\max(|g_k|, 1)} < \text{tol}, \qquad \text{tol} = 10^{-8}
$$

Si el lazo **no** converge, se dice explícitamente, con el error
alcanzado, y se avisa de que los valores mostrados son la última iteración
y **no una solución**.

### Verificación

No basta con que converja: tiene que converger a la solución correcta. El
balance global de una planta con reciclo tiene respuesta cerrada.

Con 100 mol/s frescos, $\xi = 5$ mol/s, $\nu_{tot} = -1$ y 80 % de
recirculación:

| | Valor | Comprobación |
|---|---|---|
| `mezcla.F` | 480 | $= 100 + 380$ ✓ |
| `salida_r.F` | 475 | $= 480 - 5$ ✓ |
| `producto.F` | 95 | $0.2 \times 475$ ✓ |
| `reciclo.F` | 380 | $0.8 \times 475$ ✓ |
| `fresco − producto` | 5 | $= \xi$ ✓ |

Y el balance por componente $F z_i + \nu_i \xi = D x_i$ cierra para los
tres componentes.

---

## 2.8 Escalabilidad

Medido con cadenas de reactores en serie, en el peor orden de bloques:

| Operaciones | Bloques | Variables | GL | Completo | Tiempo |
|---|---|---|---|---|---|
| 10 | 61 | ~120 | 0 | ✓ | 0.002 s |
| 30 | 181 | ~360 | 0 | ✓ | 0.008 s |
| 60 | 361 | ~720 | 0 | ✓ | 0.033 s |
| 120 | 721 | ~1440 | 0 | ✓ | 0.082 s |

El coste es **lineal** en el número de operaciones.

### Generalidad, comprobada con topologías mezcladas

| Topología | GL | Resuelve |
|---|---|---|
| mezclador → reactor | 0 | ✓ |
| reactor → divisor (purga) | 0 | ✓ |
| columna → divisor | 0 | ✓ |
| 2 reactores → mezclador → reactor | 0 | ✓ |
| McCabe-Thiele → divisor (binario) | 0 | ✓ |
| reactor/divisor/mezclador/columna/reactor/divisor | 0 | ✓ |

---

## 2.9 Límites conocidos del solver

- **Acoplamiento entre bloques sin lazo.** Si dos bloques quedan
  acoplados de forma que ninguno es resoluble por sí solo, se reporta
  como incógnitas restantes. No hay resolución simultánea global.
- **Reciclos anidados** (un lazo dentro de otro): la detección los
  soporta, pero solo se ha verificado el caso de un lazo.
- **No hay verificación de consistencia sobre el lazo cerrado**: si los
  datos dentro de un reciclo son incompatibles, el síntoma es no
  convergencia, no un mensaje claro.
- **El tipo del valor en el pool es opaco.** El bucle solo compara
  `pool[v] is None`, nunca hace aritmética sobre el valor, así que una
  variable puede ser `float` o `np.ndarray` sin que el orquestador lo
  sepa. Es lo que permitió meter FUG (vectorial) sin tocar el motor —
  aunque en `DiagramaCorrientes` el pool es 100 % escalar.

---

[← Arquitectura](01-arquitectura.md) · [Índice](README.md) · [Siguiente: Termodinámica →](03-termodinamica.md)
