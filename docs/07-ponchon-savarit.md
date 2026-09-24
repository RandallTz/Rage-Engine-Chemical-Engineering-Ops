# 7. Ponchon-Savarit

[← McCabe-Thiele](06-mccabe-thiele.md) · [Índice](README.md) · [Siguiente: FUG →](08-fug.md)

---

## 7.1 Qué aporta sobre McCabe-Thiele

McCabe-Thiele supone **flujo molar constante**. Esa suposición se cae
cuando los calores latentes de los dos componentes difieren
apreciablemente: los caudales cambian de etapa a etapa y las rectas de
operación dejan de ser rectas.

Ponchon-Savarit no supone nada de eso. Trabaja en el plano
**entalpía-composición** $(x, H)$ y la energía entra en la propia
construcción geométrica, no como un cálculo aparte.

El precio: hay que conocer las entalpías, y el diagrama es menos
intuitivo.

> Igual que McCabe-Thiele, **es binario** y el constructor rechaza
> cualquier otra cosa proponiendo FUG.

---

## 7.2 Las dos curvas de saturación

Se precalculan barriendo $x$ y resolviendo `burbuja_T` en cada punto —el
**mismo** barrido para las dos curvas, de modo que $H_L(x)$ y
$H_V(y^{eq}(x))$ estén evaluadas a la misma temperatura de burbuja: son
una línea de reparto **real**, no dos curvas independientes.

$$
H_L(x) = h_L\big(T^{burb}(x),\, \mathbf{x}\big) = \int_{T_{ref}}^{T^{burb}(x)} \sum_i x_i\,C_{p,i}^L\,dT'
$$

$$
H_V(y) = H_L(y) + \sum_i y_i\,\Delta H^{vap}_i
$$

Se interpolan con splines cúbicos. Los extremos ($x = 0$ y $x = 1$) se
calculan **sin pasar por UNIFAC**, evaluando cada componente puro en su
propio punto de ebullición $T_b$: `burbuja_T` se porta mal justo donde una
fracción molar vale cero.

> **De dónde salen ahora estas entalpías.** Ponchon-Savarit tenía su
> propia implementación, que integraba $C_p$ de la mezcla con `quad`, una
> cuadratura por cada punto del barrido. Hoy delega en la calculadora
> compartida ([§4](04-entalpia.md)), que tabula la integral por
> componente puro y resuelve cualquier composición como producto punto.
>
> El camino y la referencia son **idénticos**, y se comprobó que el
> resultado coincide con la `quad` anterior a $10^{-10}$ relativo: los
> números de este método no cambiaron ($Q_c/D$ mínimo sigue siendo
> 80 960 para $q=1$ y 166 650 para $q=-0.5$, y la razón
> $N_{PS}/N_{MT}$ sigue entre 1.002 y 1.033). Lo que cambió es que ahora
> el mezclador, el flash y el intercambiador del flowsheet miden la
> energía con esta misma tabla, así que los balances cierran **entre**
> equipos y no solo dentro de cada uno.
>
> De paso, construir el evaluador pasó de ~0.24 s solo en las entalpías a
> 0.121 s en total.

---

## 7.3 Los polos Δ

Es el concepto central del método. Un **polo** es un punto ficticio del
plano $(x,H)$ que representa el balance de materia *y* energía de una
sección entera de la columna.

### Polo de rectificación

$$
\boxed{\;\Delta_D = \big(x_D,\; H_{\Delta_D}\big), \qquad
H_{\Delta_D} = H_L(x_D) + \frac{Q_c}{D}\;}
$$

### Polo de agotamiento

$$
\boxed{\;\Delta_B = \big(x_B,\; H_{\Delta_B}\big), \qquad
H_{\Delta_B} = H_L(x_B) - \frac{Q_R}{B}\;}
$$

Se abrevian $Q_c/D \equiv$ `Qc_D` y $Q_R/B \equiv$ `QR_B`, ambos en J/mol.

---

## 7.4 La condición de colinearidad

Esta es la ecuación que hace funcionar el método:

$$
\boxed{\;\Delta_D,\quad (z_F, H_F),\quad \Delta_B \quad\text{son COLINEALES}\;}
$$

No es un adorno geométrico: es el **balance de energía global** de la
columna,

$$
F\,H_F + Q_R \;=\; D\,H_D + B\,H_B + Q_c
$$

escrito como geometría. Si $Q_c/D$, $Q_R/B$ y $H_F$ no son mutuamente
consistentes con ese balance, los tres puntos no caen en una recta.

### Consecuencia: $Q_R/B$ no es libre

Dado $Q_c/D$, la colinearidad **determina** $Q_R/B$:

$$
m = \frac{H_F - H_{\Delta_D}}{z_F - x_D},
\qquad
H_{\Delta_B} = H_{\Delta_D} + m\,(x_B - x_D),
\qquad
\frac{Q_R}{B} = H_L(x_B) - H_{\Delta_B}
$$

Por eso el grado de libertad del método es **uno solo**: $Q_c/D$, el
análogo de $R$ en McCabe-Thiele.

### Nota sobre la tolerancia

La comprobación de colinearidad usa tolerancia **relativa** (`rtol`,
por defecto $10^{-3}$), no absoluta. Las entalpías aquí son de orden
$10^4$–$10^5$ J/mol, así que las pendientes también: exigir $10^{-6}$
absoluto sería exigir igualdad casi exacta en doble precisión — ni el
redondeo de un spline lo cumple.

---

## 7.5 Entalpía de la alimentación desde $q$

$$
H_F \;=\; H_L(z_F) + (1-q)\,\big[H_V(z_F) - H_L(z_F)\big]
$$

> **Aproximación explícita:** usa $H_V$ evaluada en $z_F$. Rigurosamente
> debería evaluarse en el **punto de rocío** de $z_F$ (temperatura
> distinta a la de burbuja, salvo azeótropo). Si hace falta $H_F$
> riguroso, se pasa directamente en lugar de derivarlo de $q$.
>
> **Nota de estado:** el solver de rocío que faltaba **ya existe**
> (`CalculadoraELV.rocio_T`, [§3.5](03-termodinamica.md)), añadido para el
> flash. Esta aproximación podría eliminarse usándolo, y es una mejora
> pendiente concreta — pero **no se ha hecho ni verificado**, así que la
> fórmula de arriba sigue siendo la que corre.

---

## 7.6 El escalonamiento

Alterna dos pasos, como McCabe-Thiele, pero entre las **dos** curvas de
saturación.

**Punto de partida:** $(x_D,\ H_V(x_D))$ — sobre la curva de **vapor**. El
vapor que sale del primer plato es $y_1 = x_D$ (condensador total). Este
fue un bug corregido: antes se dibujaba $(x_D, H_L(x_D))$, el destilado
líquido, como si fuera el arranque de la cascada.

**Paso de reparto (equilibrio):** dado $y$, encontrar el $x$ en equilibrio
resolviendo $y^{eq}(x) = y$. Une $(x, H_L(x))$ con $(y, H_V(y))$.

**Paso operativo:** recta desde el **polo activo** a través del punto
recién hallado, hasta cortar la otra curva de saturación:

$$
m = \frac{H_{polo} - H_{actual}}{x_{polo} - x_{actual}},
\qquad
\text{resolver } H_V(y) = H_{actual} + m\,(y - x_{actual})
$$

### El cambio de polo

El polo activo pasa de $\Delta_D$ a $\Delta_B$ cuando la pendiente
operativa local **cae por debajo** de la pendiente global
$\Delta_D$–$\Delta_B$:

$$
m_{global} = \frac{H_{\Delta_D} - H_{\Delta_B}}{x_D - x_B},
\qquad
\text{cambiar cuando } m < m_{global}
$$

> El sentido de esta desigualdad se **verificó numéricamente** antes de
> darlo por bueno. La pendiente $m$ arranca muy por encima de $m_{global}$
> (polo $D$, cerca de $x_D$) y decrece etapa a etapa. Con el sentido
> contrario ($>$) el cambio de sección se disparaba en la primerísima
> etapa, todavía pegado a $x_D$, lo cual es físicamente incorrecto.

Las etapas se cuentan fraccionarias truncando exactamente en $x_B$, igual
que en McCabe-Thiele.

---

## 7.7 $Q_c/D$ mínimo

El análogo de $R_{min}$. **No tiene fórmula cerrada** —a diferencia de
McCabe-Thiele, donde $R_{min}$ sale de la intersección línea $q$–curva de
equilibrio— así que se localiza **numéricamente por bisección**: se busca
el valor por debajo del cual el escalonamiento hace *pinch*.

### El diagnóstico, y por qué se paga solo cuando hace falta

Si el escalonamiento falla, `brentq` escupe *"f(a) and f(b) must have
different signs"*. Antes de propagarlo se calcula $Q_c/D|_{min}$ y se
informa:

> *"Qc_D=10000 está por debajo del mínimo requerido (Qc_D_min≈60229.9):
> produce un pinch, necesitaría etapas infinitas. Sube Qc_D."*

**El cuidado necesario:** `calcular_Qc_D_min` llama internamente a
`calcular_escalones` unas 60 veces (bisección) para probar factibilidad.
Si esas llamadas también dispararan el diagnóstico al fallar, cada una
lanzaría su propia búsqueda anidada — explosión combinatoria. Por eso
existe el parámetro `_diagnosticar`, que la bisección pone en `False` en
sus propias llamadas: el diagnóstico solo se paga en el camino de error
que de verdad lo necesita.

---

## 7.8 Balance de energía

En Ponchon-Savarit la energía **no se añade aparte**: ya está en la
construcción entálpica. Las relaciones son consecuencia directa de las
definiciones de los polos:

$$
Q_c = \frac{Q_c}{D}\cdot D,
\qquad
Q_R = \frac{Q_R}{B}\cdot B
$$

### Recuperar el reflujo clásico

Conecta el método con $R$ de toda la vida. Con condensador total, el vapor
que llega es $V_1 = D(R+1)$ y se condensa de $H_V(x_D)$ a $H_L(x_D)$:

$$
Q_c = D\,(R+1)\,\big[H_V(x_D) - H_L(x_D)\big]
$$

Dividiendo por $D$:

$$
\boxed{\;\frac{Q_c}{D} = (R+1)\,\big[H_V(x_D) - H_L(x_D)\big]
\quad\Longrightarrow\quad
R = \frac{Q_c/D}{H_V(x_D) - H_L(x_D)} - 1\;}
$$

### Verificación numérica

Con benceno/tolueno, $z_F = 0.5$, $x_D = 0.9$, $x_B = 0.1$, $q = 1$,
$Q_c/D = 70$ kJ/mol:

| Magnitud | Valor |
|---|---|
| $N$ | 10.2919 |
| $R$ deducido | 1.23476 |
| $Q_R/B$ | 70916.4 J/mol |
| $Q_c$ | 3 500 000 W |
| $Q_R$ | 3 545 822 W |

**Balance global:**

$$
F H_F + Q_R = 4\,592\,348.2\ \text{W}
\qquad
D H_D + B H_B + Q_c = 4\,592\,348.2\ \text{W}
$$

Error relativo: **0.000e+00**.

Y $Q_c/D = (R+1)(H_V - H_L)$ se comprueba aparte a $10^{-9}$.

---

## 7.9 La gráfica

El diagrama que se dibuja lleva:

- Las dos curvas de saturación, $H_L(x)$ y $H_V(y)$.
- La escalera de etapas.
- Las **rectas de reparto** (equilibrio): unen cada líquido con su vapor.
- Las **rectas operativas**: del polo activo al punto de cada etapa.
- Los polos $\Delta_D$ y $\Delta_B$, y el punto $F$, unidos por la recta
  que materializa el balance global.

**Detalle de escala:** los polos caen muy lejos de las curvas (en el caso
de arriba, $+78$ y $-57$ kJ/mol contra 8–48). Verlos completos es la
esencia del método pero aplasta la zona donde se leen las etapas, así que
la vista se puede alternar en vez de elegir por el usuario.

---

## 7.10 Límites

- **Binario estricto.**
- $H_F$ derivado de $q$ es aproximado (§7.5).
- Sin entalpía de exceso.
- Requiere $0 < x_B < z_F < x_D < 1$.
- $Q_c/D$ por debajo del mínimo produce pinch — se detecta y se explica.

---

[← McCabe-Thiele](06-mccabe-thiele.md) · [Índice](README.md) · [Siguiente: FUG →](08-fug.md)
