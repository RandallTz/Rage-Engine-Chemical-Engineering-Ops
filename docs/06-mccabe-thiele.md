# 6. McCabe-Thiele

[← Flash](05-flash.md) · [Índice](README.md) · [Siguiente: Ponchon-Savarit →](07-ponchon-savarit.md)

---

## 6.1 Alcance

Método gráfico-numérico para destilación **binaria**. Supone **flujo molar
constante** (CMO, *constant molar overflow*): en cada sección de la columna
los caudales de líquido y vapor no cambian de etapa a etapa.

> El constructor **rechaza** cualquier mezcla que no tenga exactamente 2
> componentes, nombrándolos y proponiendo FUG. Sin esa guarda el fallo
> llegaba disfrazado: el evaluador construía composiciones de 2 elementos
> contra un proveedor de $n$, y lo que veía el usuario era un error de
> punto de burbuja que no mencionaba el problema real.

---

## 6.2 Las variables y la ecuación

El método se trata como **una sola ecuación** sobre un vector de seis
variables:

$$
N \;=\; f(z_F,\ q,\ x_D,\ x_B,\ R)
$$

Según cuál falte, se evalúa directo (*rating*) o se resuelve por
root-finding (*design spec*).

> **Alcance real, verificado antes de programar:** con un solo evaluador
> hay **una** ecuación. Eso resuelve, con cero grados de libertad, el caso
> de exactamente **una** incógnita. Pedir dos a la vez es subdeterminado
> con esta ecuación sola — haría falta acoplar el balance de materia
> global, que en un diagrama sí ocurre (son bloques distintos en el mismo
> pool).

---

## 6.3 La curva de equilibrio

Se precalcula **una vez** barriendo $x_1 \in (0,1)$ y resolviendo
`burbuja_T` en cada punto, y se interpola con un spline **monótono**
(PCHIP):

$$
y^{eq}(x) \;\approx\; \mathrm{PCHIP}\big(\{x^{(k)}, y^{(k)}\}\big)
$$

Se fuerzan los extremos físicos exactos $(0,0)$ y $(1,1)$ para que el
spline no extrapole mal cerca de los componentes puros.

**Por qué PCHIP y no un spline cúbico normal:** PCHIP preserva la
monotonía. Un cúbico puede oscilar entre nodos y producir una curva de
equilibrio que cruza la diagonal donde no debe, inventando azeótropos
inexistentes.

**Por qué precalcular:** el escalonamiento y el solver de grados de
libertad evalúan $y^{eq}(x)$ muchísimas veces, y no se puede pagar un
`burbuja_T` completo (UNIFAC + root-finding anidado) en cada una.

---

## 6.4 Las rectas de operación

### Línea $q$

$$
y \;=\; \frac{q}{q-1}\,x \;-\; \frac{z_F}{q-1}
$$

Con $q = 1$ (líquido saturado) la recta es **vertical** en $x = z_F$ y se
trata como caso aparte para evitar la división por cero.

| $q$ | Estado de la alimentación |
|---|---|
| $> 1$ | Líquido subenfriado |
| $= 1$ | Líquido saturado |
| $0 < q < 1$ | Mezcla líquido-vapor |
| $= 0$ | Vapor saturado |
| $< 0$ | Vapor sobrecalentado |

### Recta de operación de rectificación (ROL)

$$
y \;=\; \frac{R}{R+1}\,x \;+\; \frac{x_D}{R+1}
$$

### Recta de operación de agotamiento (SOL)

No se escribe con su fórmula clásica en términos de $\bar{L}/\bar{V}$;
se construye geométricamente uniendo $(x_B, x_B)$ con la intersección
ROL–línea $q$:

$$
m_{SOL} = \frac{y_{int} - x_B}{x_{int} - x_B},
\qquad
y = m_{SOL}\,(x - x_B) + x_B
$$

Es equivalente y evita tener que calcular $\bar{L}$ y $\bar{V}$ aparte.

### Intersección ROL–$q$ (analítica)

$$
x_{int} = \frac{b_{ROL} - b_q}{m_q - m_{ROL}},
\qquad y_{int} = m_{ROL}\,x_{int} + b_{ROL}
$$

con $m_{ROL} = R/(R+1)$, $b_{ROL} = x_D/(R+1)$, $m_q = q/(q-1)$,
$b_q = -z_F/(q-1)$. Para $q = 1$, $x_{int} = z_F$ directamente.

---

## 6.5 Reflujo mínimo

El *pinch* está donde la recta de operación toca la curva de equilibrio.
Se localiza como la intersección de la **línea $q$** con la curva de
equilibrio:

$$
y^{eq}(x_{pinch}) = \frac{q}{q-1}\,x_{pinch} - \frac{z_F}{q-1}
$$

resuelto con `brentq` en $(0,1)$. Con $q = 1$, $x_{pinch} = z_F$ directo.

Entonces:

$$
\boxed{\;R_{min} \;=\; \frac{x_D - y_{pinch}}{y_{pinch} - x_{pinch}}\;}
$$

Si $y_{pinch} = x_{pinch}$ (el pinch cae sobre la diagonal, es decir un
azeótropo) $R_{min}$ **no está definido** y se lanza un error explicándolo.

### La guarda $R \le R_{min}$

$$
R \le R_{min} \;\Rightarrow\; \text{etapas infinitas}
$$

Se comprueba **antes** de escalonar. Sin ella, el escalonamiento entra en
un bucle que se atasca y el usuario recibe un error de `brentq` sin
significado.

---

## 6.6 El escalonamiento

Se arranca en $(x_D, x_D)$ —sobre la diagonal, porque con condensador
total $y_D = x_D$— y se alternan dos pasos:

1. **Paso de equilibrio** (horizontal): dado $y$, encontrar el $x$ en
   equilibrio resolviendo $y^{eq}(x) = y$ con `brentq` en $(0, x_{actual})$.
2. **Paso operativo** (vertical): dado $x$, evaluar la recta de operación
   que corresponda.

$$
y_{op}(x) =
\begin{cases}
\dfrac{R}{R+1}x + \dfrac{x_D}{R+1} & x \ge x_{int} \quad (\text{rectificación})\\[2ex]
m_{SOL}\,x + b_{SOL} & x < x_{int} \quad (\text{agotamiento})
\end{cases}
$$

### Etapas fraccionarias

El último escalón casi nunca cae exactamente en $x_B$. Se interpola
linealmente la fracción que de verdad hacía falta:

$$
N = N_{enteras} + \frac{x_{actual} - x_B}{x_{actual} - x_{nuevo}}
$$

Esto es lo que permite el diseño inverso: $N$ tiene que ser una función
**continua** de $R$ para que un root-finder pueda invertirla. Con $N$
entero, la ecuación $N(R) = 10$ sería una escalera y no tendría solución
en general.

---

## 6.7 Eficiencia de Murphree

Con $E_{MV} < 1$ el paso de equilibrio no busca la curva real sino una de
**pseudo-equilibrio**:

$$
y^{pseudo}(x) \;=\; y_{op}(x) \;+\; E_{MV}\,\big[y^{eq}(x) - y_{op}(x)\big]
$$

Con $E_{MV} = 1$ esto se reduce idénticamente a $y^{eq}$.

> **Importante:** la eficiencia afecta **solo al escalonamiento** (etapas
> reales). $R_{min}$ y el pinch siguen usando la curva de equilibrio real:
> la eficiencia de plato no cambia el límite termodinámico de reflujo
> mínimo.

Verificado: $E_{MV} = 1.0 \to N = 12.51$; $0.9 \to 13.95$;
$0.7 \to 18.00$; $0.5 \to 25.34$. Monótono creciente, como debe.

---

## 6.8 Condensador parcial

Un condensador **parcial** es en sí mismo una etapa de equilibrio; uno
total no aporta ninguna. Se implementa sumando 1:

$$
N_{parcial} = N_{total} + 1
$$

La geometría (ROL, SOL, $R_{min}$, escalonamiento) es idéntica: la ROL
siempre cruza la diagonal en el valor de su término independiente, sea ese
valor líquido o vapor.

> **Nota de honestidad, tal como está en el código:** la ubicación gráfica
> exacta del punto $(x_0, y_D)$ dentro del escalonamiento tiene variantes
> según el texto. Se eligió la forma "+1 etapa" por ser la menos propensa
> a un error de índice; si hace falta el detalle gráfico fino, conviene
> confirmarlo con una fuente.

---

## 6.9 Diagnóstico de azeótropos

Si el escalonamiento se atasca, `brentq` dice *"f(a) and f(b) must have
different signs"*, que no explica nada. La causa habitual es un azeótropo
entre $x_B$ y $x_D$.

Antes de propagar el error se busca el cruce de $y^{eq}(x)$ con la
diagonal en ese intervalo, y si existe se informa:

> *"Separación imposible por destilación simple: hay un azeótropo en
> x=0.8940, entre x_B=0.05 y x_D=0.95. Ninguna cantidad de etapas ni de
> reflujo cruza un azeótropo — hay que quedarse de un solo lado de él, o
> cambiar de técnica (destilación extractiva, azeotrópica, cambio de
> presión)."*

El azeótropo se localiza por cambio de signo de $y^{eq}(x) - x$ sobre una
malla, con interpolación lineal en el intervalo donde cambia.

---

## 6.10 Cargas térmicas (CMO)

Consistentes con las suposiciones del propio método; el tratamiento
riguroso con entalpías se deja para
[Ponchon-Savarit](07-ponchon-savarit.md).

Llamando $\lambda$ al **calor que hay que quitar de más por devolver el
reflujo frío** —la entalpía que le falta al líquido para estar en su
burbuja—:

$$
\lambda \;=\; h_L(T_D, x_D) \;-\; h_L(T_{reflujo}, x_D)
$$

$$
Q_c \;=\; D\,(R+1)\,\big[\Delta H^{vap}_D + \lambda\big]
$$

$$
R_{int} \;=\; R\left[1 + \frac{\lambda}{\Delta H^{vap}_D}\right]
$$

$$
\bar{V} \;=\; D\,(R_{int}+1) \;-\; F\,(1-q)
$$

$$
Q_R \;=\; \bar{V}\,\Delta H^{vap}_B
$$

$T_D$ y $T_B$ son los puntos de burbuja de $x_D$ y $x_B$ a la presión de
operación. Si $T_{reflujo}$ no se da, se asume reflujo **saturado**
($T_{reflujo} = T_D$), con lo que $\lambda = 0$ y los términos de
subenfriamiento se anulan.

> **Cambio respecto a la versión anterior.** El término de subenfriamiento
> era $C_{p,D}(T_D - T_{reflujo})$, o sea $C_p$ **congelado en $T_D$**.
> Ahora es la diferencia real de entalpía, que es la integral de $C_p$
> entre las dos temperaturas ([§4](04-entalpia.md)). Coinciden cuando el
> subenfriamiento es pequeño y se separan cuando es grande — justo cuando
> el término importa.

$\Delta H^{vap}$ "de mezcla" sigue siendo el promedio ponderado por
composición de las propiedades puras, y se obtiene como
$h_V(T, x) - h_L(T, x)$ de la calculadora compartida, no del proveedor
directamente: así esta fórmula y la del flash miden lo mismo.

Verificado: subenfriar 10 K aumenta $Q_c$ y hace $R_{int} > R_{ext}$, como
debe.

---

## 6.11 Verificación

| Comprobación | Resultado |
|---|---|
| Diseño inverso: $N$ objetivo 10 → $R$ resuelto | 2.4830; recalcular $N$ con ese $R$ da 10.000000 |
| Balance de materia: $F=100$, $z_F$, $x_D$, $x_B$ → $D$, $B$ | 38.8889 / 61.1111, coincide con la fórmula cerrada |
| Inverso ($D$, $B$ conocidos) → $F$, $x_D$ | recupera 100.0 y 0.95 |
| Condensador parcial vs. total | diferencia exactamente 1.000000 |
| $N$ vs. $R$ | decrece monótonamente y se aplana hacia el reflujo total |
| Caso subdeterminado (2 incógnitas) | se rechaza explicando por qué |
| Caso sobre-especificado inconsistente | se detecta y se cuantifica |

---

## 6.12 Límites

- **Binario estricto.** Con $n \ne 2$ se rechaza en el constructor.
- **CMO.** Si los calores latentes de los dos componentes difieren mucho,
  las rectas de operación no son rectas. Ahí toca Ponchon-Savarit.
- **No cruza azeótropos.** Es una limitación física, no del programa.
- Requiere $0 < x_B < z_F < x_D < 1$.

---

[← Flash](05-flash.md) · [Índice](README.md) · [Siguiente: Ponchon-Savarit →](07-ponchon-savarit.md)
