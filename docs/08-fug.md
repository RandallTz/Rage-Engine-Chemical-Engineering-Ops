# 8. FUG (Fenske-Underwood-Gilliland)

[← Ponchon-Savarit](07-ponchon-savarit.md) · [Índice](README.md) · [Siguiente: Reactor CSTR →](09-reactor-cstr.md)

---

## 8.1 Qué resuelve

Método de **atajo** (*shortcut*) para destilación **multicomponente**.
Es el único de los tres que funciona con más de dos componentes, y por eso
es el que desbloquea el flowsheet cuando la mezcla crece.

Tres correlaciones encadenadas:

| Paso | Da | Condición |
|---|---|---|
| **Fenske** | $N_{min}$ y el reparto de todos los componentes | Reflujo total |
| **Underwood** | $R_{min}$ | Etapas infinitas |
| **Gilliland** | $N$ real | Interpola entre los dos límites |

---

## 8.2 Diferencia conceptual con los métodos binarios

Esta es la que más confunde al llegar desde McCabe-Thiele:

> En FUG **no se especifican purezas** ($x_D$, $x_B$) sino
> **recuperaciones** de los dos componentes clave.

$$
\text{recuperación}_{LK,D} = \frac{d_{LK}}{F z_{LK}},
\qquad
\text{recuperación}_{HK,B} = \frac{b_{HK}}{F z_{HK}}
$$

Las composiciones de producto son **resultado** del método: el reparto de
los no-clave lo decide Fenske.

### Componentes clave

- **LK** (*light key*): el más pesado de los que se quiere que se vayan
  por el domo.
- **HK** (*heavy key*): el más ligero de los que se quiere que se vayan
  por el fondo.

Los demás se clasifican por punto de ebullición: más ligeros que el LK van
enteros al destilado; más pesados que el HK van enteros al fondo; los
**intermedios** (entre ambos) se reparten y son el caso delicado.

---

## 8.3 Bootstrap de distribución

Fenske necesita un reparto para calcular las temperaturas de domo y fondo,
pero el reparto es lo que se quiere calcular. Se rompe el círculo con una
distribución inicial:

$$
d_i = \begin{cases}
z_i & i \text{ más ligero que LK}\\
z_i\cdot \text{rec}_{LK,D} & i = LK\\
z_i\,(1-\text{rec}_{HK,B}) & i = HK\\
0.5\,z_i & i \text{ intermedio}\\
0 & i \text{ más pesado que HK}
\end{cases}
\qquad b_i = z_i - d_i
$$

El $0.5$ de los intermedios es solo una semilla: Fenske los recalcula
inmediatamente después.

---

## 8.4 Volatilidades relativas

Referidas al **clave pesado**:

$$
\alpha_i(T, \mathbf{x}) = \frac{\gamma_i\,P_i^{sat}}{\gamma_{HK}\,P_{HK}^{sat}}
$$

La presión del sistema se cancela en el cociente.

Se evalúan en **tres puntos** (domo, alimentación, fondo) y se promedian
geométricamente:

$$
\boxed{\;\alpha_{i,avg} = \big[\alpha_i(T_D, \mathbf{x}_D)\cdot
\alpha_i(T_F, \mathbf{z}_F)\cdot
\alpha_i(T_B, \mathbf{x}_B)\big]^{1/3}\;}
$$

La media **geométrica** (no aritmética) es la convención del método: las
volatilidades entran en Fenske dentro de un logaritmo, y la media
geométrica es la que hace consistente esa operación.

---

## 8.5 Fenske: etapas mínimas

A reflujo total:

$$
\boxed{\;N_{min} = \frac{\ln\!\left[\dfrac{d_{LK}}{b_{LK}}\cdot\dfrac{b_{HK}}{d_{HK}}\right]}
{\ln \alpha_{LK,avg}}\;}
$$

### Refinamiento del reparto

Con $N_{min}$ ya conocido, Fenske da el reparto de **todos** los
componentes, no solo de los clave:

$$
\frac{d_i}{b_i} = \frac{d_{LK}}{b_{LK}}
\left(\frac{\alpha_{i,avg}}{\alpha_{LK,avg}}\right)^{N_{min}}
\qquad\Longrightarrow\qquad
d_i = z_i\,\frac{(d_i/b_i)}{1 + (d_i/b_i)}
$$

Las recuperaciones de los dos claves se **fuerzan** a su valor exacto
después, para no arrastrar el pequeño error numérico del logaritmo y la
potencia.

### La guarda $\alpha_{LK} > 1$

$\alpha_{avg}$ está referido al HK, así que $\alpha_{LK,avg}$ es la
volatilidad del ligero respecto del pesado y **debe ser mayor que 1**.

Si no lo es, los claves están invertidos: lo que se llamó "ligero" es en
realidad el menos volátil.

> **Sin esta guarda el fallo era silencioso y grave.** $\ln(\alpha < 1)$
> es negativo, así que $N_{min}$ salía **negativo** y se arrastraba hasta
> un número de etapas negativo. Se destapó con $-21.4$ etapas montando un
> caso isobuteno/metanol/MTBE con LK = metanol y HK = MTBE — **el MTBE
> hierve a 328 K y el metanol a 338 K**, o sea el MTBE es el ligero.
>
> La comprobación posterior `R <= R_min` sí existía, pero con
> $R_{min} = -12.7$ pasaba tan ricamente. Una columna con $-21$ etapas no
> es un aviso: es basura presentada como resultado.

El error ahora nombra ambos componentes con sus puntos de ebullición.

---

## 8.6 Underwood: reflujo mínimo

Dos ecuaciones. La primera localiza las raíces $\theta$:

$$
\boxed{\;\sum_i \frac{\alpha_i\,z_i}{\alpha_i - \theta} \;=\; 1 - q\;}
$$

Se buscan raíces **entre volatilidades adyacentes** de los componentes
distribuidos, con `brentq` sobre cada intervalo
$(\alpha_{inf}(1+\epsilon),\ \alpha_{sup}(1-\epsilon))$.

La segunda da $R_{min}$:

$$
\boxed{\;R_{min} + 1 \;=\; \sum_i \frac{\alpha_i\,x_{D,i}}{\alpha_i - \theta}\;}
$$

### Múltiples raíces

Si hay más de un componente realmente distribuido entre LK y HK, hay más
de una raíz $\theta$, y $R_{min}$ y los $d_i$ de los intermedios se
resuelven **simultáneamente** como un sistema lineal: una ecuación por
raíz.

$$
\begin{pmatrix}
-1 & \frac{\alpha_{m_1}}{\alpha_{m_1}-\theta_1} & \cdots \\
-1 & \frac{\alpha_{m_1}}{\alpha_{m_1}-\theta_2} & \cdots \\
\vdots & & \ddots
\end{pmatrix}
\begin{pmatrix} R_{min} \\ d_{m_1} \\ \vdots \end{pmatrix}
=
\begin{pmatrix} 1 - \sum_{conocidos} \frac{\alpha_i d_i}{\alpha_i - \theta_1} \\ \vdots \end{pmatrix}
$$

> Esta rama es una **extensión avanzada**, menos estándar que el caso de
> una sola raíz. Se verificó con un caso sintético de 2 raíces antes de
> confiar en ella.

### La guarda $R_{min} \ge 0$

Un reflujo mínimo **negativo** no es físico: el mínimo es, como poco,
cero.

Underwood lo puede devolver cuando el corte pedido es tan suave que la
alimentación ya está prácticamente separada respecto de ese par de claves
— ahí la columna casi no necesita sección de rectificación y el método
sale de su rango de validez.

> Importa avisarlo porque el resultado **no parecía roto**: con
> $R_{min} = -0.068$ la comprobación `R <= R_min` pasaba y Gilliland
> devolvía $N = 3.95$, un número de aspecto razonable construido sobre un
> mínimo imposible. Se detectó armando un caso columna+reactor con
> recuperaciones del 70 %.

---

## 8.7 Gilliland: etapas reales

Correlación de **Eduljee (1975)**, la forma analítica de la gráfica
original de Gilliland:

$$
X = \frac{R - R_{min}}{R + 1},
\qquad
Y = 0.75 - 0.75\,X^{0.5668},
\qquad
\boxed{\;N = \frac{N_{min} + Y}{1 - Y}\;}
$$

Es una **correlación empírica**, no una deducción. Su exactitud típica es
de $\pm$10–20 % en $N$. Para diseño final se usa un método riguroso
(MESH); FUG sirve para dimensionar rápido y para el arranque de uno
riguroso.

---

## 8.8 Cargas térmicas

Mismas fórmulas que McCabe-Thiele pero generalizadas a $n$ componentes:
donde allí hay un vector `[x, 1-x]` hardcodeado, aquí es el mismo producto
punto con $\mathbf{x}_D$ y $\mathbf{x}_B$ completos.

$$
\Delta H^{vap}_D = \sum_i x_{D,i}\,\Delta H^{vap}_i(T_D),
\qquad
C_{p,D} = \sum_i x_{D,i}\,C^L_{p,i}(T_D)
$$

$$
Q_c = D(R+1)\big[\Delta H^{vap}_D + C_{p,D}(T_D - T_{reflujo})\big],
\qquad
Q_R = \bar{V}\,\Delta H^{vap}_B
$$

---

## 8.9 Integración en el flowsheet

Aquí hubo trabajo de adaptación real.

**El problema:** `AnalizadorFUG` usa variables **vectoriales**
($\mathbf{x}_D$, $\mathbf{x}_B$, $\mathbf{d}$, $\mathbf{b}$ son arrays),
mientras que `DiagramaCorrientes` usa **escalares** por corriente
(`s2.x0`, `s2.x1`, …). Los dos mundos no se tocaban.

**La solución:** dos bloques traductores que leen las fracciones sueltas,
arman los vectores, llaman a `AnalizadorFUG` y reparten el resultado otra
vez en fracciones sueltas. **No se reescribió la matemática de FUG.**

**Detalle que obliga a construir el analizador dentro del bloque:**
`AnalizadorFUG` exige $\mathbf{z}_F$ **completo** en su constructor, pero
en este modelo la composición de la alimentación vive en el pool y puede
no conocerse cuando se arma el diagrama. Por eso el analizador se
construye en tiempo de resolución.

**Conteo de ecuaciones:** el bloque escribe $n$ fracciones para el
destilado y $n$ para el fondo, pero cada grupo suma 1 por construcción.
Ese descuento lo hace ahora el diagrama de forma estructural
([§2.3](02-solver.md#23-grados-de-libertad)); antes estaba escrito a mano
aquí y por eso solo estaba bien en este bloque.

### Variables que aporta al pool

$$
R,\quad \text{rec}_{LK,D},\quad \text{rec}_{HK,B}
\quad\big|\quad
N,\ N_{min},\ R_{min},\ \theta,\ Q_c,\ Q_R,\ R_{int},\ \bar{V},\ T_{reflujo}
$$

$\theta$ se publica como escalar: cuando hay varias raíces se guarda la
primera, que es la que usa el método para $R_{min}$.

---

## 8.10 Verificación

Cuatro alcanos (C5–C8) equimolares, claves hexano/heptano al 98 %,
$R = 2$:

| Comprobación | Resultado |
|---|---|
| Grados de libertad | GL = 0 exacto |
| Balance total | $F = D + B$ ✓ |
| Balance por componente | cierra para los cuatro ✓ |
| $\sum x_i$ de cada producto | 1.00000000 ✓ |
| Recuperación LK pedida 0.98 | obtenida 0.98000 ✓ |
| Recuperación HK pedida 0.98 | obtenida 0.98000 ✓ |
| $N > N_{min}$ | 11.557 > 8.213 ✓ |
| $R > R_{min}$ | 2.0 > 0.616 ✓ |
| Cargas térmicas | positivas ✓ |

---

## 8.11 Límites

- **Gilliland es empírica.** ±10–20 % en $N$.
- **$\alpha$ promedio de tres puntos** supone que la volatilidad relativa
  no varía salvajemente a lo largo de la columna. Falla con sistemas muy
  no ideales.
- **No detecta azeótropos.** FUG no sabe que existen.
- **Los claves deben elegirse bien**: adyacentes en volatilidad y con
  $\alpha_{LK} > 1$. Ambas cosas se comprueban ahora.
- **No da perfil de etapas**, solo el número total.

---

[← Ponchon-Savarit](07-ponchon-savarit.md) · [Índice](README.md) · [Siguiente: Reactor CSTR →](09-reactor-cstr.md)
