# 3. Termodinámica

[← El solver](02-solver.md) · [Índice](README.md) · [Siguiente: Entalpía →](04-entalpia.md)

---

## 3.1 El proveedor de propiedades

`ProveedorTermodinamico` es el **único punto de contacto** entre el
simulador y los datos termodinámicos externos (la biblioteca `thermo`).
Todo lo que devuelve son `float` o `np.ndarray` en SI.

| Método | Devuelve | Unidad | Fuente |
|--------|----------|--------|--------|
| `presiones_saturacion(T)` | $P_i^{sat}(T)$ | Pa | `Chemical.Psat` |
| `entalpias_vaporizacion(T)` | $\Delta H^{vap}_i(T)$ | J/mol | `Chemical.Hvapm` |
| `capacidades_calorificas_liquido(T)` | $C_{p,i}^L(T)$ | J/(mol·K) | `Chemical.Cplm` |
| `propiedades_caloricas(T)` | $(C_{p,i}^L,\ \Delta H^{vap}_i)$ | — | las dos en una pasada |
| `coeficientes_actividad(T, x)` | $\gamma_i(T,\mathbf{x})$ | — | UNIFAC |
| `entalpias_formacion_liquido()` | $\Delta H_{f,i}^{\circ}$ | J/mol | `Chemical.Hfm` |
| `energias_gibbs_formacion_liquido()` | $\Delta G_{f,i}^{\circ}$ | J/mol | `Chemical.Gfm` |
| `volatilidades_relativas(T, x)` | $\alpha_i$ | — | derivado |

Que el proveedor sea el único acceso a `thermo` importa: cambiar de
modelo de actividad (UNIFAC → NRTL → UNIQUAC) es cambiar **un método**,
no rastrear llamadas por todo el código.

---

## 3.2 Equilibrio líquido-vapor: Raoult modificada

El modelo es la **ley de Raoult modificada**: fase líquida no ideal
(coeficientes de actividad), fase vapor ideal.

$$
\boxed{\;y_i\,P = x_i\,\gamma_i(T,\mathbf{x})\,P_i^{sat}(T)\;}
$$

Los coeficientes de actividad salen de **UNIFAC predictivo puro**, a
partir de los grupos funcionales que `thermo` asigna a cada molécula. No
hay parámetros binarios ajustados: es predictivo, lo que permite meter
cualquier componente sin datos experimentales previos — a cambio de menos
exactitud que un modelo ajustado para ese par concreto.

UNIFAC clásico es función solo de $T$ y composición, no de $P$.

### Comprobación de que los coeficientes están realmente activos

Con $\gamma_i = 1$ (mezcla ideal) no puede haber azeótropos. Medido:

| Sistema | $\gamma$ equimolar a 350 K |
|---|---|
| etanol / agua | 1.231, 1.486 |
| acetona / metanol / agua | 1.415, 1.026, 1.582 |
| isobuteno / metanol / MTBE | 1.545, 1.933, 1.032 |

Y el **azeótropo etanol/agua aparece en $x = 0.894$** ($y - x$ cambia de
signo exactamente ahí), que es el valor de literatura.

---

## 3.3 Puntos de burbuja

### Presión de burbuja (a $T$ fija)

Directa, sin iterar:

$$
P^{burb} = \sum_i x_i\,\gamma_i(T,\mathbf{x})\,P_i^{sat}(T),
\qquad
y_i = \frac{x_i\,\gamma_i\,P_i^{sat}}{P^{burb}}
$$

### Temperatura de burbuja (a $P$ fija)

Requiere encontrar la raíz de

$$
\Phi(T) \;=\; \sum_i x_i\,\gamma_i(T,\mathbf{x})\,P_i^{sat}(T) \;-\; P \;=\; 0
$$

Se resuelve con `brentq`. $\Phi$ es **creciente** en $T$ (a más
temperatura, más presión de vapor), así que el signo en los extremos dice
hacia qué lado está la raíz.

#### El bracket no es fijo

Es un detalle numérico con consecuencias físicas reales. La versión
original usaba un bracket **constante** $[273.15,\ 600]$ K. Eso deja fuera
cualquier mezcla que hierva bajo 0 °C — por ejemplo el **isobuteno, que
hierve a 266 K**. Cualquier composición rica en él fallaba, y el error que
llegaba al usuario era el `f(a) and f(b) must have different signs` de
`scipy`, que no dice nada.

Un bracket fijo obliga a saber de antemano por dónde hierve la mezcla, que
es justo lo que se está calculando. Ahora se **ensancha automáticamente**
hasta encontrar cambio de signo, dentro de $[120,\ 800]$ K, y si de verdad
no hay solución se explica por qué:

> *"La mezcla ya está por encima de su punto de burbuja incluso a X K:
> hierve por debajo del rango explorado."*

Verificado sin regresión: benceno/tolueno 50/50 sigue dando **365.515693 K,
idéntico bit a bit** al valor anterior.

---

## 3.4 Volatilidad relativa

$$
\alpha_i \;=\; \frac{\gamma_i\,P_i^{sat}}{\gamma_{ref}\,P_{ref}^{sat}}
$$

La presión del sistema se cancela en el cociente, por eso no aparece.

De aquí sale una forma compacta del equilibrio que se usa en el mapeo
discreto reactivo ([§10.2](10-destilacion-reactiva.md)):

$$
y_i \;=\; \frac{\alpha_i\,x_i}{\sum_j \alpha_j\,x_j}
$$

Esta expresión **no es una aproximación**: sustituyendo
$\alpha_i = \gamma_i P_i^{sat} / (\gamma_{ref} P_{ref}^{sat})$, el factor
de referencia se cancela arriba y abajo y queda exactamente la Raoult
modificada. Comprobado numéricamente contra `burbuja_P`: coinciden a
$10^{-16}$.

---

## 3.5 Puntos de rocío

La pareja del punto de burbuja, pero **no simétrica en dificultad**.

### Presión de rocío (a $T$ fija)

$$
\frac{1}{P} \;=\; \sum_i \frac{y_i}{\gamma_i(T, \mathbf{x})\,P_i^{sat}(T)}
$$

La de burbuja es explícita porque $\mathbf{x}$ se conoce. Esta es
**implícita**: $\gamma$ depende de la composición del *líquido*, que es
justo la incógnita. Se resuelve por punto fijo arrancando del caso ideal
($\gamma = 1$); converge rápido porque $\gamma$ cambia poco entre
iteraciones comparado con lo que cambia $\mathbf{x}$.

### Temperatura de rocío (a $P$ fija)

Misma estrategia de bracket ensanchable que `burbuja_T`: $P_{rocío}$
crece con $T$, así que el signo del residuo dice hacia dónde está la raíz.

### Por qué hacía falta

Sin rocío **no se puede distinguir una corriente bifásica de un vapor
sobrecalentado**, que es la comprobación que necesita el flash
([§5.3](05-flash.md)).

Validación cruzada, fuerte porque usa dos rutinas independientes: el
líquido de la primera gota, metido de vuelta en `burbuja_P`, devuelve la
misma presión (a $10^{-9}$ relativo) y la composición de vapor original
(a $9\times10^{-15}$).

---

## 3.6 Entalpías

> Las entalpías **ya no viven aquí**. Estaban implementadas tres veces
> con convenciones distintas (una de ellas linealizada, que no es lo
> mismo), y eso solo se notaba al encadenar equipos. Ahora hay una sola
> definición, en `thermodynamics/entalpia.py`, con su propio capítulo:
> **[§4 Entalpía](04-entalpia.md)**.

De lo que sigue siendo del proveedor:

| Magnitud | Símbolo | De `thermo` |
|---|---|---|
| Capacidad calorífica del líquido | $C_{p,i}^L(T)$ | `Chemical.Cplm` |
| Entalpía de vaporización | $\Delta H^{vap}_i(T)$ | `Chemical.Hvapm` |

`propiedades_caloricas(T)` devuelve las dos **en una sola pasada**:
pedirlas por separado obliga a `thermo` a recalcular el estado de cada
`Chemical` dos veces a la misma $T$, y la calculadora de entalpía las
tabula sobre la misma malla.

Referencia y camino, resumidos ([§4.2](04-entalpia.md) los desarrolla):

$$
h_L(T, \mathbf{x}) = \sum_i x_i \int_{T_{ref}}^{T} C_{p,i}^L\,dT'
\qquad
h_V(T, \mathbf{y}) = h_L(T, \mathbf{y}) + \sum_i y_i\,\Delta H^{vap}_i(T)
$$

> **Aproximación explícita:** no hay entalpía de exceso. $h$ de mezcla es
> el promedio ponderado de las puras — no hay calor de mezcla. Es la
> aproximación estándar y es consistente con las suposiciones de los
> métodos que la usan.

---

## 3.7 Termodinámica y cinética de reacción

`GestorReaccion` encapsula tres cosas.

### (A) Propiedades estándar de reacción

Se precalculan una sola vez, como producto punto sobre el vector
estequiométrico:

$$
\Delta H_{rxn}^{\circ} = \sum_i \nu_i\,\Delta H_{f,i}^{\circ},
\qquad
\Delta G_{rxn}^{\circ} = \sum_i \nu_i\,\Delta G_{f,i}^{\circ}
$$

$$
K_{eq}^{\circ} = \exp\!\left(\frac{-\Delta G_{rxn}^{\circ}}{R\,T_{std}}\right),
\qquad T_{std} = 298.15\ \text{K}
$$

### (B) Constante de equilibrio: van't Hoff

$$
\boxed{\;
K_{eq}(T) \;=\; K_{eq}^{\circ}\,
\exp\!\left[\frac{\Delta H_{rxn}^{\circ}}{R}\left(\frac{1}{T_{std}} - \frac{1}{T}\right)\right]
\;}
$$

> **Suposición:** $\Delta H_{rxn}^{\circ}$ constante entre $T_{std}$ y $T$.

Comportamiento que sirve de comprobación: si la reacción es **exotérmica**
($\Delta H < 0$), $K_{eq}$ **disminuye** al subir $T$. Verificado con la
síntesis de MTBE:

$$
\Delta H_{rxn} = -57.6\ \text{kJ/mol} \;\Rightarrow\;
K_{eq}(298) = 72.3 \;>\; K_{eq}(350) = 2.31 \;\checkmark
$$

Esa es exactamente la tensión central de la destilación reactiva: calentar
favorece la separación pero castiga la conversión de equilibrio.

### (C) Velocidad neta de reacción

Arrhenius sobre **actividades**, no sobre concentraciones:

$$
k(T) = A\,\exp\!\left(\frac{-E_a}{R\,T}\right),
\qquad
a_i = x_i\,\gamma_i(T,\mathbf{x})
$$

$$
\boxed{\;
r(T,\mathbf{x}) \;=\; k(T)\left[
\prod_{i:\ \nu_i<0} a_i^{|\nu_i|}
\;-\;
\frac{1}{K_{eq}(T)}\prod_{j:\ \nu_j>0} a_j^{\nu_j}
\right]\;}
$$

El segundo término es la reacción inversa. Cuando el sistema alcanza el
equilibrio químico, el corchete se anula y $r = 0$.

La implementación es vectorizada con máscaras booleanas sobre $\nu$; no
hay bucles.

---

## 3.8 Balance atómico: la primera comprobación

Una estequiometría que no conserva la materia hace que **todo lo que se
calcule encima sea aritmética sobre una reacción que no existe**. Se
comprueba, para cada elemento:

$$
\sum_i \nu_i \cdot (\text{átomos de ese elemento en } i) \;=\; 0
$$

usando las fórmulas moleculares de `thermo`.

**Caso real que lo motivó.** Se aceptó sin protestar
`acetal ⇌ acetaldehído + etanol` con $\nu = [1, 1, -1]$:

```
C: -2      H: -4      O: 0        masa: -28.05 g/mol
```

Faltan C₂H₄. La acetalización real es

$$
\text{acetaldehído} + 2\,\text{etanol} \;\rightleftharpoons\;
\text{acetal} + \text{agua}
$$

que es un sistema de **cuatro** componentes. Con tres no se puede
balancear, y el $\Delta G$ que se calculó sobre esa estequiometría no
significaba nada.

---

## 3.9 Suposiciones y límites

| Suposición | Consecuencia |
|---|---|
| Fase vapor ideal | Mal a presiones altas (> ~10 bar) o cerca del crítico |
| UNIFAC predictivo | Menos exacto que un modelo ajustado para ese par |
| Sin entalpía de exceso | No hay calor de mezcla |
| $\Delta H_{rxn}$ constante con $T$ | Van't Hoff pierde exactitud en rangos amplios |
| Actividades en la cinética | Requiere que el mecanismo sea consistente con eso |
| Sin caída de presión | $P$ uniforme en cada equipo |
| Una sola fase líquida | Sin equilibrio líquido-líquido: un sistema que se separe en dos fases líquidas (agua/hidrocarburo) está fuera de alcance |

---

[← El solver](02-solver.md) · [Índice](README.md) · [Siguiente: Entalpía →](04-entalpia.md)
