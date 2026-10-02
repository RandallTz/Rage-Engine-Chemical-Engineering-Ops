# 13. Especificaciones de diseño y barridos

[← Validación](12-validacion.md) · [Índice](README.md)

---

## 13.1 La pregunta inversa

Todo lo documentado hasta aquí contesta la misma pregunta:

> Dados estos datos, ¿cuánto da?

Pero al diseñar no se tiene el reflujo: se tiene la pureza que el cliente
pide. La pregunta real es la inversa:

> Quiero que el destilado salga al 99 %. ¿Qué reflujo hace falta?

Dentro de **un** bloque eso ya funcionaba, y no por casualidad: los
bloques del simulador son **invertibles** (§13.3). `SolucionadorMcCabeThiele`
acepta $N$ y devuelve $R$ igual que acepta $R$ y devuelve $N$.

Lo que no había era la versión a nivel de **diagrama**, donde la variable
que se mueve y el objetivo que se persigue están en equipos distintos, con
un reciclo en medio. Eso es lo que hace `core/especificaciones.py`.

---

## 13.2 Qué es, formalmente

Una especificación de diseño es **una ecuación más** en el sistema:

$$y_{\text{objetivo}} - y^{*} = 0$$

donde $y_{\text{objetivo}}$ es una variable cualquiera del pool global
(`producto.x2`, `col1.Q_c`, `s4.T`) y $y^{*}$ el valor pedido. Se resuelve
moviendo una variable manipulada $u$ (`col1.R`, `r1.T_salida`) dentro de un
rango $[u_{\min}, u_{\max}]$.

La función residuo es, literalmente, *resolver el diagrama entero y mirar*:

$$g(u) = \Big[\text{resolver}(\text{datos} \cup \{u\})\Big]_{\text{objetivo}} - y^{*}$$

Cada evaluación de $g$ cuesta **una resolución completa del diagrama**,
reciclos convergidos incluidos. Esa es la razón de que convenga que las
especificaciones sean pocas y los rangos estrechos.

### El rango no es un detalle de implementación

Casi toda variable de proceso tiene un rango físico: un reflujo no es
negativo, una fracción molar no pasa de 1, una temperatura de reactor
líquido no pasa del punto de burbuja de la mezcla. Acotar la búsqueda es lo
que evita que el solver se vaya a un sitio donde el diagrama **no se puede
resolver**, y donde por tanto no hay residuo que medir.

---

## 13.3 Por qué esta arquitectura lo admite casi sin añadir nada

Esto merece quedar escrito, porque explica por qué la pieza salió pequeña:

| Lo que ya existía | Para qué sirve aquí |
|---|---|
| **Pool plano con nombres globales** (`s1.F`, `col1.R`) | Una especificación es literalmente un par de nombres. Si cada equipo guardara su propio estado, haría falta tubería para cruzar el diagrama |
| **Conteo de grados de libertad estructural** ([§2.3](02-solver.md#23-grados-de-libertad)) | El contador confirma solo que el problema queda cerrado, en vez de haberlo de razonar a mano |
| **8 bloques invertibles** (`puede_resolver` admite incógnitas) | Cuando la manipulada vive dentro de uno de ellos, puede no hacer falta lazo exterior ninguno |
| **Motor de reciclos** ([§2.5](02-solver.md)) | Tiene exactamente esta forma: suponer, resolver, mirar el error, corregir |
| **`verificar_consistencia`** | Ya hacía *"recalcula esta variable desde su bloque y compara"*, que es la evaluación de residuo que una especificación necesita |

Un simulador secuencial-modular tiene que construir esta maquinaria aparte,
porque en él el flujo de información va en una sola dirección. Aquí es
orquestación de piezas ya validadas.

---

## 13.4 Grados de libertad: el error fácil de cometer

Cada especificación suma **una ecuación. Y nada más.**

La tentación es sumar también una incógnita, razonando que "se libera la
variable manipulada". **Es falso**, y la primera versión de
`grados_de_libertad_con_especificaciones` lo hacía: esa variable **ya
estaba contada** como incógnita, precisamente porque no se da como dato.
Sumarla otra vez la cuenta dos veces, y el contador anuncia que falta un
dato sobre un problema perfectamente planteado.

Dicho en una frase: **una especificación de diseño no reformula el
problema, lo cierra.**

$$\text{GL} = 1 \;\xrightarrow{\;+\,1\ \text{especificación}\;}\; \text{GL} = 0$$

Comprobado en los dos sentidos: sin la especificación el contador reporta
que falta un dato; con ella, cero.

---

## 13.5 Cómo se resuelven numéricamente

### Una sola: `brentq`

$$u^{*} : g(u^{*}) = 0, \qquad u^{*} \in [u_{\min}, u_{\max}]$$

Se prefiere a un método de Newton por dos razones concretas:

- **No necesita derivadas.** Aquí cada derivada numérica costaría una
  resolución completa del diagrama.
- **Teniendo el cambio de signo, no se puede escapar del rango físico.**
  Newton sí: un paso largo puede saltar a un reflujo negativo, y ahí el
  diagrama no devuelve un número malo, devuelve una excepción.

Antes de iterar se evalúa $g$ en los dos extremos. Si no hay cambio de
signo, el error dice **qué intervalo recorre de verdad el objetivo** en ese
rango, que es lo que permite decidir si hay que ampliar el rango o si el
objetivo no es alcanzable con esa variable.

### Varias a la vez: `root`, con los residuos escalados

$$\mathbf{g}(\mathbf{u}) = \mathbf{0}, \qquad
g_k \;\to\; \frac{g_k}{\max(|y_k^{*}|,\, 10^{-9})}$$

**El escalado no es cosmético.** Una especificación sobre una fracción
molar vive en el orden 1 y otra sobre un calor en el orden $10^6$. Sin
escalar, el solver sacrifica la primera para afinar la segunda, porque la
norma del residuo apenas la nota. Es el mismo problema que ya apareció en
el reactor acoplado ([§9](09-reactor-cstr.md)).

Y, como en el resto del proyecto, **no se confía en `sol.success`**: se
exige que el residuo relativo máximo esté por debajo de $10^{-6}$.

---

## 13.6 Qué pasa cuando no se puede

Un objetivo que no se determina **no se convierte en un residuo
inventado**. Un NaN silencioso aquí haría que el solver vagara sin sentido
y acabara reportando un fallo en el sitio equivocado.

El diagnóstico se da en tres niveles, y los tres aportan. Caso real, al
pedir una conversión con el rango de temperatura del reactor hasta 380 K:

```
la especificación falló
  └─ el diagrama no llega a determinar 'producto.x2'
      └─ h_V(T) deja de crecer cerca de 408.9 K, zona cercana a la crítica
```

La capa de arriba dice qué se intentaba, la de en medio qué variable se
quedó sin valor, y la de abajo **la causa física**: la inversión
$h \to T$ exige monotonía ([§4](04-entalpia.md)), y
$C_{p,V} = C_{p,L} + \mathrm{d}\Delta H_{vap}/\mathrm{d}T$ puede volverse
negativa cerca del punto crítico.

Un primer intento del mensaje intermedio mandaba a *"buscar datos que
faltaran"*, que es justo donde **no** estaba el problema. Se corrigió para
señalar la causa más probable de verdad: que ese valor concreto de la
variable manipulada no sea viable — el caso típico es un reflujo por
debajo del mínimo, donde harían falta infinitas etapas.

---

## 13.7 Barridos de sensibilidad

```python
filas = diagrama.barrido("col1.R", [1.6, 2.0, 3.0, 5.0, 10.0],
                         seguir=["col1.N", "col1.Q_c"], **datos)
```

No es una herramienta de cálculo sino **de comprensión**. La pregunta de
quien aprende no es *"¿cuánto da?"* sino *"¿qué pasa si subo el reflujo?"*,
y hasta ahora eso había que hacerlo a mano, resolviendo una y otra vez y
apuntando los números.

**Un punto que falla no tumba el barrido**: se anota el motivo en
`_error` y se sigue. Es exactamente lo que se quiere al explorar — ver el
rango útil **con sus bordes**, en vez de perder 19 puntos buenos porque el
vigésimo pinchaba por estar bajo $R_{\min}$.

El compromiso clásico de la destilación sale solo, sin haberlo programado:

| $R$ | $N$ | $Q_c$ (MW) |
|---|---|---|
| 1.6 | 19.5 | 3.1 |
| 10.0 | 7.5 | 13.2 |

Más reflujo compra etapas y se paga en servicios. Eso es la curva que todo
curso de separaciones dibuja a mano, aquí calculada con UNIFAC y el
balance de energía real.

---

## 13.8 Suposiciones y límites

- **Coste.** Cada evaluación resuelve el diagrama completo. Un diagrama con
  reciclos lentos y tres especificaciones es caro; el contador
  `evaluaciones` del resultado lo reporta para que no sea una sorpresa.
- **Una sola especificación necesita cambio de signo** en el rango. Si el
  objetivo tiene un extremo interior (pasa por un máximo), `brentq` puede
  no verlo. No se oculta: el error dice qué rango recorre.
- **Varias especificaciones pueden contradecirse.** No se detecta
  *a priori* — se detecta por el residuo, y el mensaje señala las dos
  posibilidades reales: que se contradigan, o que una manipulada no
  influya de verdad sobre su objetivo.
- **No es optimización.** Esto resuelve igualdades, no minimiza nada. No
  hay función objetivo, ni restricciones de desigualdad, ni variables
  discretas.
- **El rango se respeta siempre**, también en el caso de varias: los
  candidatos se acotan antes de resolver. Un `root` sin acotar propondría
  reflujos negativos.

---

## 13.9 Qué está verificado

`tests/validar_especificaciones.py`, 13 comprobaciones:

| Qué | Contra qué |
|---|---|
| El contador de GL | 1 sin la especificación, 0 con ella |
| Una especificación simple | **El camino directo**: pedir $N = 12$ da $R = 2.241647$; evaluar McCabe-Thiele con ese $R$ —sin lazo— devuelve $N = 12.00000000$ |
| Objetivo tras dos equipos y un reciclo | Error $-5.7\times10^{-12}$ en 12 resoluciones, cada una con sus reciclos convergidos |
| Dos especificaciones a la vez | Errores $-7.1\times10^{-12}$ y $1.4\times10^{-14}$ |
| Cinco casos que **deben** rechazarse | Objetivo = manipulada; rango al revés; manipulada dada también como dato; objetivo inalcanzable en el rango; valor inviable |
| Barrido de reflujo | $N$ monótona decreciente, $Q_c$ creciente, y dos puntos bajo $R_{\min}$ anotados sin detener el barrido |

La comprobación que de verdad importa es la segunda: **es la única que
demuestra que el lazo exterior no miente**, porque compara su respuesta con
la del método invertido directamente, que nunca pasa por el lazo.

---

[← Validación](12-validacion.md) · [Índice](README.md)
