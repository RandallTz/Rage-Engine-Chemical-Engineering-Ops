# 14. Trazabilidad: de dónde sale este número

Un número sin procedencia no se puede reproducir ni auditar. En este
simulador eso importa más de lo normal, porque las validaciones comparan
contra valores **exactos**: §12 afirma que benceno/tolueno 50/50 hierve a
365.515693 K *idéntico bit a bit*. Un informe que diga «365.52 K» sin
decir con qué versión del motor y con qué versión de `thermo` se obtuvo no
es un resultado reproducible: es una captura de pantalla.

Este capítulo documenta los tres bloques que la respuesta de
`/diagrama/resolver` añade para contestar tres preguntas distintas:

| Bloque | Pregunta que contesta |
|---|---|
| `calculo` | ¿Con qué motor y sobre qué entradas se calculó esto? |
| `diagnosticos` | ¿Qué le pasa, en forma de **datos** y no de texto? |
| `convergencia` | ¿De dónde sale cada número y cuánto me puedo fiar? |

Los tres son **opcionales y aditivos**: ningún campo anterior cambió, así
que un cliente que no los conozca sigue funcionando igual.

---

## 14.1 `calculo`: con qué se calculó

```json
{
  "identificador": "5f8b2beeb0178bacbc34c30ba83b5e02",
  "instante_utc": "2026-10-06T04:35:41.435+00:00",
  "motor": { "version": "0.15.0", "commit": "f0d61a70…-sucio" },
  "proveedor_termodinamico": {
    "identificador": "unifac_raoult",
    "versiones": { "thermo": "0.6.1", "chemicals": "1.5.2",
                   "fluids": "1.3.1", "numpy": "1.26.4", "scipy": "1.16.2" }
  },
  "huella_entradas": "ba0b7ad73c262427…",
  "algoritmo_huella": "sha256"
}
```

### El commit, y el sufijo `-sucio`

La versión sola no distingue dos estados del árbol de trabajo. El commit
sí, pero **solo si el árbol está limpio**: con cambios sin commitear, un
commit a secas afirmaría que el código es exactamente el de ese commit, y
eso es falso. De ahí el sufijo.

`commit` puede ser `null`, y eso es deliberado. Un despliegue desde un
tarball no tiene `.git`, y el contenedor puede no traer el ejecutable de
`git`. **Inventarse un identificador sería peor que admitir que no se
sabe**, porque un identificador falso se propaga a los informes y nadie lo
cuestiona.

### La versión del proveedor son las de las librerías

Decir «proveedor v1» sería inventar un número que no cambia cuando los
resultados sí. La versión real del proveedor **es** la de `thermo`,
`chemicals` y `fluids`, porque son las que deciden cada propiedad. Esto no
es un detalle administrativo: es la razón de que `requirements.txt` tenga
las versiones fijas, y **ya pasó una vez** — los atributos `Hfl`/`Gfl` de
`thermo` cambiaron río arriba y movieron los números sin que nadie tocara
una línea de este repositorio (registrado en `roadmap.md`).

### La fecha es la del servidor

A propósito. La del cliente no certifica nada: es la hora de un reloj que
el cliente controla.

---

## 14.2 La huella de las entradas

`huella_entradas` es un SHA-256 de las entradas **físicas normalizadas**.
El contrato que establece es:

> Dos peticiones con la misma huella deben dar el mismo resultado. Si dan
> otro, el cambio está en el motor o en sus dependencias.

Y esa es exactamente la distinción que la huella permite hacer, que sin
ella se resuelve discutiendo.

### Qué entra y qué no

| Entra | No entra |
|---|---|
| Los componentes, **en orden** (define cuál es $x_0$) | Las coordenadas de los nodos en el lienzo |
| El modelo termodinámico | Las unidades preferidas para **mostrar** |
| Cada operación: tipo, nombre, corrientes y parámetros | El nombre de la simulación |
| Los valores dados, en SI | |
| Los caudales másicos, que viajan aparte | |
| Las especificaciones de diseño | |

Se construye **a mano, campo por campo**, y no con un volcado automático
del `request`. Es más trabajo y es lo correcto: un volcado automático
metería en la huella cualquier campo nuevo que alguien añada a los
esquemas, incluido uno que no afecte al resultado, y entonces la huella
cambiaría sin que la física cambie — que es justo lo que una huella no
debe hacer.

### Qué se normaliza, y por qué no es cosmético

**Los floats, a 15 cifras significativas.** `repr(0.1 + 0.2)` y
`repr(0.3)` difieren, y sin normalizar dos peticiones idénticas para
cualquier propósito práctico darían huellas distintas. Quince cifras es lo
que un `float64` distingue de verdad; más introduciría ruido de redondeo
*en la huella*.

**Un float que vale un entero se escribe como entero**, para que `3` y
`3.0` no sean dos entradas distintas.

**Los diccionarios se ordenan por clave**; el orden de un diccionario no
es parte de la física. **Las listas conservan el suyo**, porque el de los
componentes define cuál es $x_0$ y el de los coeficientes
estequiométricos va con él.

**Las operaciones se ordenan por nombre.** El solver es de punto fijo y
los recorre hasta que nada cambie, así que el orden en que el cliente las
mande no cambia el diagrama — y por tanto no debe cambiar la huella.

### El digest va completo

Truncarlo a doce caracteres queda más bonito en un informe y multiplica
por mucho la probabilidad de colisión. El cliente siempre puede acortarlo
para **mostrarlo**.

### `identificador` vs. `huella_entradas`

Dos ejecuciones de la misma petición tienen **la misma huella** y
**distinto identificador**. La separación es la útil: la huella dice
«mismas entradas» y el identificador dice «esta ejecución concreta».

---

## 14.3 `diagnosticos`: la categoría no sale del texto

Antes, la respuesta decía lo que pasaba repartido en cuatro sitios y en
tres formas distintas: `incognitas_restantes` (una lista de nombres),
`diagnostico` (qué bloque no pudo dispararse), `inconsistencias` (datos
que no cumplen una ecuación) y `errores_bloque` (nombre → texto). Un
cliente que quisiera distinguir «faltan datos» de «esto es físicamente
imposible» **no tenía forma de hacerlo sin buscar subcadenas en
castellano** — y esa clasificación se rompe la primera vez que alguien
mejora la redacción de un mensaje.

Los cuatro campos **se conservan tal cual**. `diagnosticos` los unifica:

```json
{ "codigo": "DATOS_INCOMPATIBLES", "categoria": "datos", "severidad": "error",
  "equipo": "s2", "variables": ["s2.P"], "bloque": "b1: bombeo",
  "mensaje": "diste s2.P=100000, pero el resto de los datos implica s2.P=303975",
  "dado": 100000.0, "implicado": 303975.0 }
```

El **código** es para programar y el **mensaje** para leer. Si hay que
cambiar un mensaje, el código no se toca.

### De dónde viene cada categoría

Nunca del texto. Viene de donde se generó el problema:

| Origen | Categoría | Por qué es estructural |
|---|---|---|
| `incognitas_restantes` | `datos` / `FALTA_ESPECIFICACION` | El solver recorrió todo y no pudo calcularlas |
| `redundancias` | `datos` / `REDUNDANCIA` | Lo dice el conteo de grados de libertad |
| `inconsistencias` | `datos` / `DATOS_INCOMPATIBLES` | Sale de comparar un dato con lo que el resto implica |
| `errores_bloque` | **la de la excepción** | `core/errores.py` |

Las excepciones del motor llevan su categoría y su código **desde el sitio
donde se lanzan** (`core/errores.py`):

```
ErrorSimulador(Exception)
├── ErrorDeDatos   (ValueError)   faltan, sobran o se contradicen
├── ErrorFisico    (ValueError)   el número existe y la situación no
├── ErrorNumerico  (RuntimeError) el planteamiento es correcto y el algoritmo no llegó
└── ErrorDeModelo  (ValueError)   está fuera de lo que este simulador implementa
```

Heredar de `ValueError` y `RuntimeError` es lo que permite que todos los
`except ValueError` que ya existían sigan funcionando sin tocarlos.

Lo que nadie clasificó llega como `SIN_CLASIFICAR`, con el tipo de Python
como único dato objetivo. Es una respuesta honesta: **adivinar la
categoría buscando «hirviendo» o «no convergió» en el mensaje acierta
hasta que alguien reescribe una frase, y entonces falla en silencio.**

### La severidad no coincide con la categoría

No es lo mismo «esto está mal» que «esto no se pudo calcular».

| Caso | Severidad | Razonamiento |
|---|---|---|
| Datos incompatibles | **error** | Hay datos que se contradicen |
| Variables sin determinar | **error** | El planteamiento está incompleto |
| Redundancia | **advertencia** | Los datos de más no son necesariamente erróneos: se comprobarán por consistencia en vez de calcularse |
| Bloque que no pudo dispararse | **información** | Es la **causa** de las variables sin determinar, no un problema aparte |

Las variables sin determinar se **agrupan por elemento**. Con una columna
a medias salen ocho o quince variables sueltas, y quince diagnósticos
idénticos no informan más que uno que diga «a `col1` le faltan estas
quince».

La lista va ordenada por severidad: quien lea el primero ya tiene lo más
grave.

### `completo` y `hay_errores` no son lo mismo

`resumen_diagnosticos.hay_errores` es la bandera que separa **«se calculó
todo»** de **«el resultado es válido»**.

El caso de la bomba lo muestra: `completo = true` (todas las variables
quedaron determinadas) y `hay_errores = true` (los datos se contradicen) a
la vez. Confundirlos es el fallo que este bloque existe para evitar.

---

## 14.4 `convergencia`: sin residuos fabricados

La pregunta «¿cuánto me puedo fiar de este número?» se contesta distinto
según cómo se obtuvo, y **desde fuera no hay forma de saberlo**. Un
residuo de $10^{-11}$ en un flash dice mucho; la *ausencia* de residuo en
una construcción de McCabe-Thiele no dice nada malo — simplemente ahí no
hay residuo que medir, y presentar uno sería inventarlo.

Cada bloque **declara** su familia. No se adivina:

| Familia | Itera | Qué significa |
|---|---|---|
| `algebraico` | no | Fórmula cerrada: se cumple por construcción |
| `geometrico` | no | Construcción gráfica (McCabe-Thiele, Ponchon-Savarit) |
| `correlacion` | no | Ajuste empírico con un rango de validez |
| `iterativo` | sí | Hay un lazo con criterio de parada |
| `integracion` | sí | Integración numérica de un sistema de ODEs |

Y la declaración se separa en dos mitades:

- **`metodo`**: lo que el bloque *es*. El método concreto (`brentq`,
  `hybr`, `LSODA`), la tolerancia, y **qué mide** el residuo con sus
  unidades o su escala. Sin esto último, un número como `2.4e-11` no se
  puede interpretar.
- **`medido`**: lo que esta ejecución midió **de verdad**. Es `null`
  cuando el bloque no itera, y **eso no es residuo cero: es que no hay
  residuo que medir**.

### Tres ejemplos del mismo diagrama

Una columna binaria por McCabe-Thiele produce doce bloques. Tres de ellos:

```
col1: McCabe-Thiele      geometrico  itera=false  residuo=null
    motivo: "es una construccion geometrica: se escalona hasta cruzar x_B
             y se para. No hay residuo que medir."

Punto de burbuja (dest)  iterativo   itera=true
    metodo: "brentq sobre T"   tolerancia: "1e-9 K en la temperatura"
    residuo: "suma de y_i menos 1, adimensional"

col1: balance de materia algebraico  itera=false  medido=null
```

El campo `motivo` es la mitad útil del descriptor: distingue **«no
aplica»** de **«no se midió»**.

### El que sí mide: el decantador

```json
{ "convergio": true, "residuo": 8.244e-12,
  "escala_residuo": "diferencia relativa de actividades entre las dos fases liquidas",
  "iteraciones": 52, "distancia_plano_tangente": -0.038 }
```

Fuera de la laguna de miscibilidad, el mismo bloque reporta:

```json
{ "convergio": true,
  "nota": "una sola fase liquida: no hubo reparto que converger" }
```

En vez de un residuo de cero, que sugeriría una convergencia perfecta de
algo que nunca se planteó.

### Se reportan todos los bloques, también los que no iteran

«Este número sale de una fórmula cerrada» es **información**, no una
ausencia.

Y `ejecutado` distingue «no corrió» de «no hacía falta que corriera»: en
el ejemplo anterior, `Presion de operacion (alim)` no se dispara porque
`alim.P` venía dada, y el solver solo rellena huecos. Eso dice que ese
número es un **dato** y no un resultado.

---

## 14.5 Qué comprueba la validación

`tests/validar_trazabilidad.py`, 49 comprobaciones. Las tres cosas que
estos bloques pueden hacer mal **no se ven mirando un resultado
concreto**, y por eso tienen suite propia:

**Una huella que cambie cuando no debería** (o que no cambie cuando sí) es
peor que no tener huella: da una falsa sensación de reproducibilidad. Se
comprueba contra reordenamientos que **no** cambian la física (el orden de
las corrientes, `3` frente a `3.0`) y contra cambios que **sí** (el factor
de compresión, quitar un dato, invertir los componentes).

**Una categoría deducida del texto** funciona hasta que alguien reescribe
una frase. Se comprueba que un reflujo bajo el mínimo salga como
`fisica`/`FISICA_REFLUJO_BAJO_MINIMO` y no como `datos`, que las
redundancias sean advertencia, y que un diagrama bien planteado no
invente diagnósticos de error.

**Un residuo fabricado** es una mentira con cara de precisión. Se
comprueba que McCabe-Thiele se declare geométrico sin residuo y **con
motivo**, que un balance algebraico no traiga `medido`, y que el
decantador sí traiga el suyo con su escala.

Más una sección 5 que comprueba que el contrato anterior no se tocó: los
nueve campos de siempre siguen presentes, los cuatro nuevos son
opcionales en el esquema, y la respuesta completa serializa a JSON
estricto — un `float32` de NumPy o un `NaN` pasan los tipos de Pydantic y
revientan al serializar.

---

## 14.6 Límites

- **`VERSION_MOTOR` se sube a mano.** El commit desambigua, pero la
  versión semántica depende de que alguien la mueva cuando cambia algo
  que puede mover un número.
- **El catálogo de ecuaciones por operación no existe todavía.** Hoy
  `convergencia` dice *cómo* se resolvió un bloque; no dice *qué ecuación*
  es ni de qué referencia sale. El contrato lo marca como opcional
  posterior.
- **La huella no cubre el entorno completo.** Cubre las entradas y las
  versiones de las librerías que deciden los números, no la versión de
  Python ni la arquitectura de la CPU. Dos máquinas con las mismas
  versiones pueden diferir en el último bit de un `float64`; las
  validaciones de §12 que comparan bit a bit lo hacen en una sola máquina.
