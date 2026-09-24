# 5. Flash y equipos térmicos

[← Entalpía](04-entalpia.md) · [Índice](README.md) · [Siguiente: McCabe-Thiele →](06-mccabe-thiele.md)

---

## 5.1 Un flash es una etapa MESH

Esta es la razón de que el flash exista antes que la columna rigurosa. Un
separador líquido-vapor en equilibrio **es, literalmente, el sistema MESH
completo con $N = 1$**:

| | Ecuación |
|---|---|
| **M** (materia) | $F z_i = V y_i + L x_i$ |
| **E** (equilibrio) | $y_i = K_i(T, P, \mathbf{x})\, x_i$ |
| **S** (sumatorias) | $\sum_i x_i = \sum_i y_i = 1$ |
| **H** (energía) | $F h_F + Q = V\, h_V(T, \mathbf{y}) + L\, h_L(T, \mathbf{x})$ |

Resolverlo bien obliga a fijar **ahora** todo lo que la columna rigurosa
va a necesitar después —cómo se representa $K$, cómo se mide la entalpía
de una corriente, qué forma tiene el residuo— pero en un caso de una sola
etapa donde cada número se puede comprobar a mano.

---

## 5.2 Rachford-Rice: de cuatro ecuaciones a una incógnita escalar

Partiendo de **M** y **E**, con $\beta = V/F$:

$$x_i = \frac{z_i}{1 + \beta(K_i - 1)}, \qquad y_i = K_i x_i$$

y aplicando **S** en su forma **restada**, $\sum y_i - \sum x_i = 0$:

$$\boxed{\;f(\beta) = \sum_i \frac{z_i (K_i - 1)}{1 + \beta(K_i - 1)} = 0\;}$$

### Por qué la forma restada y no $\sum x_i = 1$

Porque $\sum x_i = 1$ es **casi plana en $\beta$** cuando la separación es
fácil, y el root-finding se vuelve mal condicionado justo en el caso
cómodo. $f(\beta)$ en cambio es **monótona decreciente** en $[0,1]$, así
que tiene a lo sumo una raíz y `brentq` la encuentra sin ambigüedad.

### Propiedad que se usa como comprobación

Con $\beta$ en la raíz, $\sum x_i = 1$ y $\sum y_i = 1$ salen **exactas**,
no aproximadas. Se deducen de $f(\beta) = 0$ junto con $\sum z_i = 1$:

$$1 = \sum_i z_i = \sum_i x_i \big(1 + \beta(K_i-1)\big) = \sum_i x_i + \beta\Big(\sum_i y_i - \sum_i x_i\Big) = \sum_i x_i$$

Por eso las sumatorias son un test real del solver, no una normalización
que se impone a mano.

### El lazo externo sobre $\gamma$

$K_i = \gamma_i(T, \mathbf{x})\, P_i^{sat}(T) / P$ — la Raoult modificada
de siempre ([Termodinámica](03-termodinamica.md)). Como $\gamma$ depende
de $\mathbf{x}$, $K$ depende de la solución: hay **sustituciones
sucesivas** sobre $\mathbf{x}$ alrededor del Rachford-Rice.

Medido: benceno/tolueno converge en **6 iteraciones**;
acetona/metanol/agua, bastante menos ideal, en **27–34**.

---

## 5.3 El diagnóstico de fase NO se deja al Rachford-Rice

Es tentador decidir la fase con $f(0)$ y $f(1)$: si $f(0) \le 0$ no se
forma ni la primera burbuja, si $f(1) \ge 0$ no condensa ni la primera
gota. **Pero esos dos valores necesitan $K$ evaluada en la composición
correcta de cada fase, y esa composición es justo lo que todavía no se
conoce.** Usar $\mathbf{z}$ en ambos casos da un diagnóstico sesgado
cerca de las fronteras.

Aquí la frontera se pone donde de verdad está, con cálculos exactos ya
validados por separado:

$$P \ge P_{burbuja}(T, \mathbf{z}) \;\Rightarrow\; \text{todo líquido}$$
$$P \le P_{roc\text{í}o}(T, \mathbf{z}) \;\Rightarrow\; \text{todo vapor}$$

### El punto de rocío hubo que añadirlo

No existía. Y no es simétrico con el de burbuja: la burbuja es
**explícita** ($P = \sum x_i \gamma_i(T,\mathbf{x}) P_i^{sat}$, porque
$\mathbf{x}$ se conoce), mientras que el rocío es **implícito**:

$$\frac{1}{P} = \sum_i \frac{y_i}{\gamma_i(T, \mathbf{x})\, P_i^{sat}(T)}$$

porque $\gamma$ depende de la composición del **líquido**, que es la
incógnita. Se resuelve por punto fijo arrancando del caso ideal
($\gamma = 1$).

`CalculadoraELV` gana así `rocio_P` y `rocio_T`, con la misma estrategia
de bracket ensanchable que `burbuja_T`.

---

## 5.4 Las tres especificaciones

Mismo espíritu orientado a ecuaciones que McCabe-Thiele y
Ponchon-Savarit: qué variable se da y cuál se despeja.

| Método | Se da | Se despeja |
|---|---|---|
| `isotermico(T, P)` | $T$, $P$ | $\beta$, $\mathbf{x}$, $\mathbf{y}$, y el $Q$ que cuesta |
| `a_entalpia(P, h)` / `con_calor(P, Q)` | $P$ y la ecuación **H** | $T$ y $\beta$ |
| `a_fraccion(P, \beta)` | $P$, $\beta$ | $T$ y $Q$ — spec de diseño |

### El flash P-H no busca $T$ a ciegas

Primero ubica las dos fronteras de fase a esa $P$, que además son baratas
comparadas con un barrido de flashes completos:

$$h \le h_L(T_{burbuja}) \;\Rightarrow\; \text{líquido subenfriado},\ T \text{ de } h_L \text{ directo}$$
$$h \ge h_V(T_{roc\text{í}o}) \;\Rightarrow\; \text{vapor sobrecalentado},\ T \text{ de } h_V \text{ directo}$$
$$\text{en medio} \;\Rightarrow\; \text{bifásico},\ T \in [T_{burbuja}, T_{roc\text{í}o}]$$

Además de ser más rápido, esto da la **clasificación de fase como
subproducto del propio balance de energía**, no como una comprobación
aparte que podría contradecirlo.

Para `a_fraccion` el bracket $[T_{burbuja}, T_{roc\text{í}o}]$ es válido
por construcción: $\beta = 0$ en la burbuja, $\beta = 1$ en el rocío, y
$\beta$ crece monótonamente entre las dos.

---

## 5.5 Los tres equipos del flowsheet

### Flash (`agregar_flash`)

Parte una corriente en dos: vapor y líquido, **a la misma $T$ y $P$**
(están en equilibrio, no es una suposición sino la definición del
equipo). Acepta exactamente una de las tres specs; sin ninguna, es
adiabático.

### Intercambiador (`agregar_intercambiador`)

Cambia la entalpía sin tocar caudal, composición ni presión. Dos specs:
dar $Q$ y obtener $T$, o dar $T$ y obtener $Q$.

El cálculo de $T$ pasa por el **flash P-H**, no por invertir $h_L$:
calentar lo suficiente **vaporiza**, y esa es justo la situación en la
que un "calentador" se vuelve un vaporizador parcial. Con $h_L$ a secas
el equipo devolvería una $T$ inventada por encima del punto de burbuja,
sin avisar de nada.

### Válvula (`agregar_valvula`)

Expansión **isentálpica**: $h_{salida} = h_{entrada}$, exacto.

No es un intercambiador con $Q = 0$. Aquí lo que cambia es la **presión**,
y es ese cambio el que redistribuye la misma entalpía entre calor
sensible y calor latente. Un líquido que cruza una válvula se vaporiza en
parte y, como el calor latente sale de la propia corriente, **se enfría**
sin que nadie le quite energía. Medido en
`tests/validar_planta_encadenada.py`: 434.6 K → 369.6 K al expandir de
6 atm a 1 atm, con $\beta = 0.368$.

---

## 5.6 La fase no es un dato, es una consecuencia

Decisión de diseño que afecta a todo el flowsheet.

Hasta ahora cada balance de energía **suponía líquido**, porque no había
forma de saber otra cosa: la fase no es un campo que lleven las
corrientes. Pero no hace falta que lo sea — la fase es una **consecuencia
de $(T, P, \mathbf{z})$**, y un flash isotérmico la deduce.

`EvaluadorFlash.entalpia_de_corriente(T, P, z)` devuelve la entalpía
correcta en los tres casos, y es **barata en el caso común**: si la
corriente es líquido subenfriado, el flash se corta en la comprobación de
burbuja, o sea una sola llamada a UNIFAC.

Dos consecuencias:

1. **Una corriente bifásica se describe sin ambigüedad con las variables
   que ya existen** ($F$, $T$, $P$, $\mathbf{x}$). No hizo falta añadir
   ninguna variable de fase por corriente, ni tocar los grados de
   libertad.
2. **El mezclador dejó de suponer líquido.** Importa el doble porque el
   mezclador es por donde entra un reciclo, y un reciclo puede traer
   vapor: antes su calor latente se ignoraba en silencio, o sea que se
   contaba **menos** energía de la que entraba y la $T$ de mezcla salía
   demasiado **baja**.

   Medido, mezclando 100 mol/s de líquido a 330 K con 40 mol/s de vapor
   sobrecalentado a 378 K:

   | | $h$ de la mezcla | $T$ de salida | Fase |
   |---|---|---|---|
   | Antes (todo líquido) | 7 081.6 J/mol | 344.30 K | líquida (supuesta) |
   | Ahora (fase deducida) | 16 113.7 J/mol | 368.13 K | bifásica, $\beta = 0.163$ |

   Faltaban **9 032 J/mol**, el 56 % de la entalpía real de la mezcla, y
   **23.8 K** en la temperatura — además de declarar líquida una
   corriente que no lo es.

---

## 5.7 Límites conocidos

**Un equipo que sí supone una fase concreta no valida la que recibe.** Una
columna binaria interpreta su alimentación según la $q$ que se le haya
dado. Si un flash le manda vapor a una columna con $q = 1$, el resultado
será incoherente y **nadie avisará**. La conexión que sí es exacta es la
inversa, y es la que se valida: el **líquido** de un flash está por
definición en su punto de burbuja, o sea $q = 1$ exactamente
(comprobado contra `burbuja_T` a $10^{-9}$ K).

**Sustituciones sucesivas, no Newton.** El lazo sobre $\gamma$ se atasca
en mezclas muy no ideales cerca de una separación de fases líquidas —que
UNIFAC en una sola fase tampoco describe—. En ese caso el flash **falla
diciéndolo**, no devuelve un número malo. Un método de Newton sobre
$(\mathbf{x}, \beta)$ resolvería más casos y no está implementado.

**Sin equilibrio líquido-líquido.** Solo hay una fase líquida. Un sistema
que se separe en dos (agua/hidrocarburo) está fuera de alcance.

**Sin caída de presión** en ningún equipo, igual que en el resto del
proyecto.

---

[← Entalpía](04-entalpia.md) · [Índice](README.md) · [Siguiente: McCabe-Thiele →](06-mccabe-thiele.md)
