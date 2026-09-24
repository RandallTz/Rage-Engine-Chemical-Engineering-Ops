# 10. Destilación reactiva

[← Reactor CSTR](09-reactor-cstr.md) · [Índice](README.md) · [Siguiente: Unidades →](11-unidades.md)

---

## 10.1 Qué se está analizando

Este módulo **no dimensiona** una columna reactiva. Analiza la
**topología** del sistema: hacia dónde se mueve la composición cuando
hierve y reacciona a la vez, y qué separaciones son posibles.

Es análisis del *sistema*, no de un *equipo*. Se hace antes de
dimensionar nada.

La razón de ser de la destilación reactiva está en una sola frase: **la
reacción puede borrar una frontera de destilación** que en el sistema
inerte hacía imposible la separación.

---

## 10.2 Los cuatro elementos del mapa

El método original tiene cuatro elementos, y **los cuatro** hacen falta
para que el mapa signifique algo:

| Elemento | Qué es | Hacia dónde apunta |
|---|---|---|
| **Curvas residuales** | Líquido que **queda** al evaporar | Al componente más **pesado** |
| **Líneas de destilación reactiva** | Cascada etapa a etapa que toma el **vapor** | Al más **volátil** |
| **Curva de equilibrio químico** | Donde se cumple $K_{eq}(T)$ | — |
| **Líneas estequiométricas** | Camino por reacción pura, sin separar | Todas hacia el polo $\pi$ |

> **Las curvas residuales y las de destilación van a vértices opuestos, y
> eso es correcto.** Una sigue el líquido residual (se enriquece en lo
> pesado); la otra sigue el vapor (se enriquece en lo volátil). Leerlas
> como si fueran lo mismo es el error de interpretación más fácil de
> cometer con este diagrama.

---

## 10.3 Mapeo continuo: curvas residuales reactivas

La ecuación que se integra, en el espacio real de fracciones molares:

$$
\boxed{\;\frac{d\mathbf{x}}{d\xi} \;=\; \big(\mathbf{x} - \mathbf{y}^*(\mathbf{x},T)\big)
\;+\; Da\,\big(\boldsymbol{\nu} - \nu_{tot}\,\mathbf{x}\big)\,r(\mathbf{x},T)\;}
$$

**Primer término** — destilación: la diferencia entre el líquido y el
vapor en equilibrio. Es la ecuación clásica de curvas residuales.

**Segundo término** — reacción. El factor $(\boldsymbol{\nu} -
\nu_{tot}\mathbf{x})$ es la dirección $\boldsymbol{\nu}$ **proyectada**
sobre el símplex: es lo que mantiene $\sum x_i = 1$ mientras se sigue la
estequiometría.

El **número de Damköhler** $Da$ pesa la reacción contra la evaporación.
Con $Da = 0$ el término químico se anula y queda la curva residual
clásica.

### Conservación de la masa

Sumando la derivada en $i$:

$$
\sum_i \frac{dx_i}{d\xi}
= \underbrace{\left(\sum_i x_i - \sum_i y_i\right)}_{1-1=0}
+ Da\,r\underbrace{\left(\sum_i \nu_i - \nu_{tot}\sum_i x_i\right)}_{\nu_{tot}-\nu_{tot}=0}
= 0
$$

$\sum x_i = 1$ se conserva **analíticamente**. Verificado numéricamente:
la suma de la derivada da $2\times10^{-16}$.

Esto importa porque convierte cualquier desviación apreciable en
**diagnóstico de basura numérica**, no de física.

### La temperatura

$T$ se recalcula en cada paso como la temperatura de burbuja a $P$ fija.
El mapeo continuo es, por tanto, **isobárico**. Verificado:
$P(T_{burb}, \mathbf{x}) = 101325$ Pa con error $\sim10^{-15}$ en cada
punto evaluado.

### Eventos terminales

Una curva termina por tres motivos, y se dice cuál:

1. **Frontera del símplex:** alguna fracción molar llega a $10^{-5}$.
2. **Punto estacionario:** $\|d\mathbf{x}/d\xi\| < 10^{-7}$ — la curva ha
   llegado a su nodo.
3. **Deriva de masa:** $|\sum x_i - 1| > 10^{-4}$ — red de seguridad.

> **El evento (2) hubo que añadirlo y es importante.** Sin él la
> integración seguía hasta el $\xi$ pedido, y al llegar al punto
> estacionario la derivada es $\approx 0$, RK45 agranda el paso sin límite
> y **la solución se desintegra**. Medido: en acetaldehído/etanol/acetal
> la curva llegaba a su nodo en $\xi \approx 2.5$ y para $\xi = 38$ la
> suma había caído de 1.0 a **0.148** — puntos fuera del símplex dibujados
> como si fueran físicos.

### Muestreo

Los puntos se reparten sobre el tramo **realmente integrado**, no sobre el
$\xi$ pedido.

> Con `t_eval` fijo sobre todo el intervalo pasaba algo contraintuitivo:
> como el evento corta la integración enseguida, de los $n$ puntos
> pedidos solo sobrevivían los anteriores al corte. Con
> $\xi_{max} = 40$ y 80 puntos el espaciado es 0.5, así que una curva que
> termina en $\xi = 1.5$ se quedaba con **tres puntos** y se dibujaba como
> un segmento recto. Y **subir $\xi_{max}$ lo empeoraba**. Con
> `dense_output` se integra igual y luego se remuestrea: de 2–4 puntos a
> 80–120 por curva.

---

## 10.4 Mapeo discreto: el método del libro

Alterna dos saltos, etapa a etapa.

### Salto físico (equilibrio)

$$
y_i = \frac{\alpha_i\,x_i}{\sum_j \alpha_j\,x_j}
$$

con $\alpha$ dinámico (UNIFAC + $P^{sat}$). Como se demuestra en
[§3.4](03-termodinamica.md#34-volatilidad-relativa), esto **es** la Raoult
modificada, no una aproximación. Verificado contra `burbuja_P` a
$10^{-16}$.

### Salto químico (Euler cinético)

$$
\mathbf{x}_{sig} = \frac{\mathbf{x}_{cond} + Da\,\boldsymbol{\nu}\,r}{1 + Da\,\nu_{tot}\,r}
$$

Desarrollando para $Da\,\nu_{tot}\,r$ pequeño:

$$
\mathbf{x}_{sig} \approx \mathbf{x}_{cond} + Da\,r\,(\boldsymbol{\nu} - \nu_{tot}\,\mathbf{x}_{cond})
$$

que es **exactamente** el término químico de la ODE continua. La
normalización no es un arreglo cosmético: es lo que proyecta la dirección
estequiométrica sobre el símplex. Verificado a $10^{-16}$.

### Isotermo, no isobárico

$T$ se fija una vez y **no se recalcula** a lo largo de la trayectoria.

> Es como está diseñado el método discreto original, pero tiene
> consecuencias que hay que saber leer: medido en isobutileno/metanol/MTBE,
> la presión de burbuja real varía un **36 %** a lo largo de una
> trayectoria a $T$ constante. Las líneas violetas del mapa **no
> representan una columna a presión constante**, sino una cascada de
> flashes a temperatura constante. El VLE en cada etapa sí es riguroso.

---

## 10.5 Líneas estequiométricas y el polo

### Las rectas de reacción pura

Desde una base sobre una arista, avanzando el grado de avance $z$:

$$
\boxed{\;\mathbf{x}(z) = \frac{\mathbf{x}_{base} + z\,\boldsymbol{\nu}}{1 + z\,\nu_{tot}}\;}
$$

conservando solo los tramos dentro del símplex. Son las trayectorias que
seguiría la composición por reacción **pura**, sin separar nada.

### El polo geométrico

$$
\boxed{\;\boldsymbol{\pi} = \frac{\boldsymbol{\nu}}{\nu_{tot}}\;}
$$

**Todas** las rectas estequiométricas pasan por él: reaccionar mueve la
composición a lo largo de la recta que une el punto con el polo.

### El caso equimolar

Si $\nu_{tot} = 0$ el polo se va al **infinito** y las rectas salen
**paralelas**. Es un caso topológicamente distinto, y se informa como tal
en vez de devolver un punto inventado.

### El polo casi siempre cae fuera

Con $\nu = [-1,-1,3]$, $\pi = (-1,-1,3)$: fuera del triángulo. Se dibuja
solo si de verdad cae en el lienzo; si no, se cita con sus coordenadas y
se advierte. Dibujarlo dentro sería mentir.

---

## 10.6 Curva de equilibrio químico

Lugar geométrico donde se cumple:

$$
\prod_{j:\ \nu_j>0} x_j^{\nu_j} \;-\; K_{eq}(T)\prod_{i:\ \nu_i<0} x_i^{|\nu_i|} \;=\; 0
$$

Se barre la fracción de un componente y se resuelve la del segundo con
`fsolve`, conservando solo las soluciones dentro del símplex.

Usa $K_{eq}(T)$ **real** (Gibbs de formación vía `thermo`), consistente
con las trayectorias, que ya usan la reacción real.

---

## 10.7 El espacio transformado de Barbosa-Doherty

La reacción introduce un grado de libertad que se puede **eliminar**
cambiando de variables. Con un componente de referencia $k$:

$$
\boxed{\;X_i = \frac{x_i - \dfrac{\nu_i}{\nu_k}\,x_k}
{1 - \dfrac{\nu_{tot}}{\nu_k}\,x_k}\;}
$$

Propiedades:

- $X_k \equiv 0$ por construcción (la dimensión eliminada).
- $\sum_{i \ne k} X_i = 1$ **exactamente**, para cualquier $\mathbf{x}$
  físico.

En este espacio, el equilibrio químico se cumple automáticamente y la
destilación reactiva se lee como una destilación normal con $n-1$
componentes.

### Corrección respecto de la fórmula dictada

> El denominador debe ser $1 - (\nu_{tot}/\nu_k)\,x_k$, **no**
> $1 - \nu_{tot}\,x_k$. Se puede verificar algebraicamente:
> $$\sum_i x_i - \frac{x_k}{\nu_k}\sum_i \nu_i = 1 - \frac{\nu_{tot}}{\nu_k}x_k$$
> que es idéntico al denominador solo en la versión corregida — y por eso
> la suma se cancela a 1 exactamente para cualquier $\mathbf{x}$,
> $\boldsymbol{\nu}$ y $k$. La versión literal solo coincide cuando
> $\nu_k = 1$.

Verificado en 20 puntos aleatorios: $X_k = 0$ y $\sum X = 1$.

### La transformación inversa

$$
x_i = X_i\left(1 - \frac{\nu_{tot}}{\nu_k}x_k\right) + \frac{\nu_i}{\nu_k}x_k
$$

Es **parcial**: requiere conocer aparte $x_k$, porque la transformación
directa pierde ese grado de libertad. Recuperarlo exige resolver el
equilibrio químico completo, lo que hace de la integración en el espacio
transformado una **raíz anidada dentro de otra raíz dentro de cada paso
del integrador** — cara y frágil.

### Singularidad

Si $1 - (\nu_{tot}/\nu_k)x_k = 0$ el punto es un **límite estequiométrico
asintótico**, no un estado físico válido. Se lanza un error diciéndolo.

---

## 10.8 Azeótropos reactivos

### Cinético

$$
\mathcal{R}(\mathbf{x}) = (\mathbf{x} - \mathbf{y}^*) + Da\,r\,(\boldsymbol{\nu} - \nu_{tot}\mathbf{x}) = \mathbf{0}
$$

Se elimina el último componente (las fracciones son linealmente
dependientes por $\sum x_i = 1$) y se resuelve con `root`.

### De equilibrio químico

En el espacio transformado:

$$
\mathbf{X} - \mathbf{Y}^*(\mathbf{X}) = \mathbf{0}
$$

$\mathbf{X}$ tiene $n-2$ grados de libertad, no $n-1$: además de
$X_k \equiv 0$, se cumple $\sum_{i\ne k} X_i = 1$. Un root-finder que solo
elimine $X_k$ puede vagar por $\mathbf{X}$ que no respetan esa suma, y
entonces la inversa reconstruye un $\mathbf{x}$ que ni siquiera suma 1 —
**se reprodujo ese fallo** antes de corregirlo. Por eso se elimina una
componente adicional.

### Convergencia real, no la de `scipy`

`sol.success` de `scipy` **no** garantiza residuo pequeño: puede terminar
por `xtol` con el residuo todavía grande. Se exige además
$\|\mathcal{R}\|_\infty < 10^{-6}$.

### Un vértice puro NO es un azeótropo

Filtro necesario. En un vértice puro $\mathbf{y}^* = \mathbf{x}$
exactamente, y además la velocidad de reacción se anula porque falta algún
reactivo: el residuo completo da cero. **Es raíz trivial.**

> Se reportaba *"azeótropo 2"* en $x = (1, 0, 0)$ a 293.4 K, que es
> simplemente acetaldehído hirviendo. Matemáticamente válido, físicamente
> es un **nodo** del mapa, y presentarlo como azeótropo engañaba.

Se descartan las raíces con $\max_i x_i > 1 - 10^{-3}$, y los ceros
numéricos negativos (`-0.0000`) se recortan.

---

## 10.9 Reproducibilidad de los mapas

Las semillas usan una **rejilla baricéntrica determinista**, no
`np.random.dirichlet`.

Un mapa que cambia de dibujo en cada petición es inservible para comparar
dos casos — y además impediría verificar nada.

---

## 10.10 Verificación

| Comprobación | Resultado |
|---|---|
| Semillas reproducibles | el mismo mapa dos veces da lo mismo ✓ |
| $\sum x = 1$ a lo largo de cada curva | $2\times10^{-16}$ ✓ |
| $x_i \ge 0$ | ✓ |
| VLE riguroso en cada etapa | error $10^{-16}$ contra `burbuja_P` ✓ |
| $\sum y = 1$, $y_i \ge 0$ | ✓ |
| Salto químico ∥ $\nu$ proyectado | $10^{-16}$ ✓ |
| Invariante de Barbosa-Doherty | 20 puntos aleatorios ✓ |
| $Da = 0$ reproduce el caso inerte | idéntico ✓ |
| Continuidad en $Da$ | sin saltos (barrido fino 4→10) ✓ |
| T de ebullición de los puros | acetona 329 < metanol 338 < agua 373 ✓ |
| Curvas residuales inertes | **8/8** se enriquecen en el pesado ✓ |
| Líneas estequiométricas vs. script original | **idénticas bit a bit** ($rtol=0$, $atol=0$) ✓ |
| Azeótropos detectados | ninguno es vértice puro ✓ |

---

## 10.11 Límites

- **El mapa NO reactivo no detecta sus puntos singulares.** El buscador de
  azeótropos solo está enchufado en la página reactiva, donde exige una
  reacción. Sin ellos, un mapa inerte no muestra fronteras de destilación.
- **No se colorean las cuencas de atracción**, que es lo que haría
  visibles esas fronteras de un golpe.
- **El mapeo discreto es isotermo** (§10.4).
- **Una sola reacción.**
- La integración en el espacio transformado (equilibrio químico) es
  **cara y frágil**: raíz anidada en raíz, y puede no encontrar bracket
  para todo sistema.

---

[← Reactor CSTR](09-reactor-cstr.md) · [Índice](README.md) · [Siguiente: Unidades →](11-unidades.md)
