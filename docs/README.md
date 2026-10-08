# Documentación técnica del simulador

Esta carpeta documenta **la matemática** que hay detrás del simulador: qué
ecuaciones se resuelven, con qué método, bajo qué suposiciones y hasta
dónde son válidas.

No es un manual de uso ni una referencia de la API. Es el documento al que
hay que ir para responder *"¿de dónde sale este número?"* y, sobre todo,
*"¿cuándo NO debo fiarme de él?"*.

---

## Por qué Markdown y no LaTeX

Las fórmulas van en LaTeX (`$...$` y `$$...$$`), pero el documento es
Markdown por tres razones prácticas:

- Se versiona y se *diffea* junto al código, en el mismo repositorio.
- Se lee directamente en el editor y en GitHub, sin compilar nada.
- Se actualiza en el mismo commit que el cambio de código que lo motiva,
  que es la única forma de que no se quede obsoleto.

Si en algún momento hace falta un PDF, `pandoc` convierte estos archivos
sin tocarlos.

---

## Índice

| # | Documento | Contenido |
|---|-----------|-----------|
| 1 | [Arquitectura](01-arquitectura.md) | Capas del sistema, núcleo en SI puro, frontera de unidades, filosofía orientada a ecuaciones |
| 2 | [El solver](02-solver.md) | Bloques de ecuaciones, punto fijo, grados de libertad, redundancias, consistencia, **reciclos y tearing** |
| 3 | [Termodinámica](03-termodinamica.md) | UNIFAC, Raoult modificada, puntos de burbuja y de rocío, equilibrio y cinética de reacción |
| 4 | [Entalpía](04-entalpia.md) | $h(T,x,\text{fase})$: una sola definición para todo el simulador, tabulación, inversión $h \to T$ |
| 5 | [Flash y equipos térmicos](05-flash.md) | Rachford-Rice, diagnóstico de fase, flash P-H, **intercambiador y válvula** |
| 6 | [McCabe-Thiele](06-mccabe-thiele.md) | Construcción y–x, reflujo mínimo, eficiencia de Murphree, cargas térmicas por CMO |
| 7 | [Ponchon-Savarit](07-ponchon-savarit.md) | Diagrama entalpía-composición, polos Δ, colinearidad, $Q_c/D$ mínimo |
| 8 | [FUG](08-fug.md) | Fenske, Underwood, Gilliland para mezclas multicomponente |
| 9 | [Reactor CSTR](09-reactor-cstr.md) | Balance por componente, avance de reacción, cinética, dimensionado |
| 10 | [Destilación reactiva](10-destilacion-reactiva.md) | Curvas residuales, mapeo discreto, transformación de Barbosa-Doherty, azeótropos reactivos |
| 11 | [Unidades](11-unidades.md) | Tabla afín generada con `pint`, y por qué el caudal másico **no** es una unidad |
| 12 | [Validación y límites](12-validacion.md) | Qué está comprobado, contra qué, y qué **no** hace el simulador |
| 13 | [Especificaciones de diseño y barridos](13-especificaciones.md) | La pregunta inversa: pedir el resultado y obtener el dato. Grados de libertad con especificaciones, barridos de sensibilidad |
| 14 | [Trazabilidad](14-trazabilidad.md) | De dónde sale este número: versión del motor y del proveedor, huella determinista de las entradas, diagnósticos con código estable, y **por qué no se fabrican residuos** |
| 15 | [El laboratorio](15-laboratorio.md) | De un grafo de piezas a un sistema resuelto: identidad única de la corriente intermedia, qué cuenta como ecuación y qué no, cinética con el solver implícito declarado, lote transitorio y equilibrio calculado, y **por qué la fuente neta no determina la generación bruta** |

Y, fuera de la numeración, el contrato de la API del laboratorio para quien conecte la interfaz: [ENTREGA_LABORATORIO_CODEX.md](ENTREGA_LABORATORIO_CODEX.md). Los ejemplos exactos de petición y respuesta están en [ejemplos/](ejemplos/), **generados ejecutando el endpoint** y no escritos a mano: uno copiado a mano se queda obsoleto en silencio.

---

## Convenciones de notación

Salvo que se diga lo contrario, todo está en **unidades SI**.

| Símbolo | Significado | Unidad |
|---------|-------------|--------|
| $F, D, B$ | Caudal molar de alimentación, destilado, fondos | mol/s |
| $z_i, x_i, y_i$ | Fracción molar del componente $i$ en alimentación, líquido, vapor | — |
| $n$ | Número de componentes | — |
| $T, P$ | Temperatura, presión | K, Pa |
| $\gamma_i$ | Coeficiente de actividad del componente $i$ | — |
| $P_i^{sat}$ | Presión de vapor del componente puro $i$ | Pa |
| $\alpha_{ij}$ | Volatilidad relativa de $i$ respecto de $j$ | — |
| $q$ | Condición térmica de la alimentación | — |
| $R$ | Relación de reflujo externa, $L_0/D$ | — |
| $N$ | Número de etapas teóricas | — |
| $H_L, H_V$ | Entalpía molar de líquido y vapor saturados | J/mol |
| $h_L, h_V$ | Entalpía molar de corriente, referencia puros líquidos a 298.15 K | J/mol |
| $\beta$ | Fracción vaporizada de una corriente, $V/F$ | — |
| $K_i$ | Constante de equilibrio del componente $i$, $y_i/x_i$ | — |
| $Q_c, Q_R$ | Carga térmica de condensador y rehervidor | W |
| $\nu_i$ | Coeficiente estequiométrico del componente $i$ | — |
| $\xi$ | Avance de reacción | mol/s |
| $Da$ | Número de Damköhler | — |

**Convención de signos estequiométricos:** $\nu_i < 0$ para reactivos,
$\nu_i > 0$ para productos, y $\nu_{tot} = \sum_i \nu_i$.

**Convención de componentes:** el índice 0 es, por convención, el
componente *ligero* en los métodos binarios. En un diagrama, la corriente
`s1` aporta al sistema las variables escalares `s1.F`, `s1.T`, `s1.P`,
`s1.x0`, …, `s1.x{n-1}`.

---

## Cómo está escrito

Cada documento sigue el mismo patrón:

1. **Qué resuelve** y con qué variables.
2. **Las ecuaciones**, con su origen.
3. **Cómo se resuelven numéricamente** (qué algoritmo, qué bracket, qué
   tolerancia) — porque en un simulador el método numérico *es* parte del
   resultado.
4. **Suposiciones y límites**, explícitos. Esta sección no es opcional:
   la mayoría de los errores de un simulador no son de programación sino
   de usar un método fuera de su rango.
5. **Qué está verificado y contra qué.**

Cuando algo es una aproximación, se dice que lo es. Cuando algo se
descubrió estando mal, queda anotado en [`roadmap.md`](../roadmap.md) con
el número que lo destapó.
