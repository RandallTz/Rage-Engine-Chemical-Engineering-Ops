# Entrega del backend: núcleo granular del laboratorio

Respuesta a `frontend/PASAR_A_CLAUDE_LABORATORIO.md`. Solo backend; ningún
archivo de `frontend/` se ha tocado.

**Lo que hay:** un ensamblador que toma el grafo de piezas de la mesa y
resuelve un sistema estacionario de **dos volúmenes térmicos** unidos por
una corriente intermedia con **identidad única**. Reutiliza el proveedor
de propiedades, el flash y la calculadora de entalpía existentes. Sin
CFD, sin mallado, sin columna completa y sin interpretar LaTeX.

---

## 1. Rutas finales

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/laboratorio/validar` | Ensambla, cuenta y diagnostica **sin ejecutar el solver** |
| `POST` | `/laboratorio/resolver` | Valida y resuelve |
| `POST` | `/laboratorio/calcular` | El endpoint único; `accion: "validar"` o `"resolver"`. **Por omisión valida** |
| `GET` | `/laboratorio/capacidades` | Qué admite el motor, **incluido lo que no** |
| `GET` | `/laboratorio/ejemplos` | Montajes que **son** peticiones válidas de `/resolver` |
| `GET` | `/laboratorio/ejemplos/{id}` | Uno concreto |

Hay tres rutas de cálculo y no una, aunque el contrato permitía una sola.
`/validar` y `/resolver` dicen en la URL lo que hacen, y eso evita el
fallo típico del endpoint único: mandar la acción equivocada y recibir
algo que parece un resultado. `/calcular` existe igualmente.

`schema_version = 1` en la petición y en la respuesta.

### Códigos HTTP

**Un montaje imposible devuelve `200`**, con `estado` y la lista de
diagnósticos. No `4xx`. El motivo es práctico: un `422` de Pydantic no
lleva código estable, ni id de bloque, ni acción sugerida, y con eso no
puedes señalar una ficha en la mesa. El `4xx` queda para una petición que
no tiene la **forma** de un montaje (`componentes` que no es una lista,
más de 16 bloques), que es lo que Pydantic rechaza antes de llegar al
motor.

Consecuencia para ti: **ramifica por `estado`, no por el código HTTP.**

---

## 2. Petición

Los ejemplos exactos están en [`docs/ejemplos/`](ejemplos/), generados
ejecutando el endpoint y no escritos a mano:

| Archivo | Qué muestra |
|---|---|
| `laboratorio-dos-volumenes-temperatura-peticion.json` | El caso de aceptación |
| `laboratorio-dos-volumenes-temperatura-respuesta.json` | Su respuesta completa |
| `laboratorio-dos-volumenes-validar-respuesta.json` | La misma por `/validar` |
| `laboratorio-dos-volumenes-calor-peticion.json` | El modo inverso: Q impuesto |
| `laboratorio-dos-volumenes-bifasico-respuesta.json` | Un caso que sale de la fase líquida |
| `laboratorio-mesa-con-datos-locales-peticion.json` | El montaje tal como lo exportas hoy |
| `laboratorio-incompatible-t-y-q-respuesta.json` | Un rechazo, para probar tu camino de error |
| `laboratorio-capacidades.json` | La respuesta de `/capacidades` |

### Lo mínimo

```json
{
  "version": 1,
  "componentes": ["benzene", "toluene"],
  "modelo_termodinamico": "unifac_raoult",
  "referencia_entalpia": "sensible_liquido_298.15K",
  "presion_sistema": {"valor": 101325.0, "unidad": "Pa"},
  "bloques": [
    {"id": "in",    "tipo": "entrada",    "nombre": "Alimentacion"},
    {"id": "cv1",   "tipo": "recipiente", "nombre": "Primer volumen"},
    {"id": "heat1", "tipo": "calor",      "nombre": "Primer aporte"},
    {"id": "medio", "tipo": "corriente",  "nombre": "Corriente compartida"},
    {"id": "cv2",   "tipo": "recipiente", "nombre": "Segundo volumen"},
    {"id": "heat2", "tipo": "calor",      "nombre": "Segundo aporte"},
    {"id": "out",   "tipo": "salida",     "nombre": "Salida final"}
  ],
  "conexiones": [
    {"id": "c1", "desde": "in",    "hacia": "cv1",   "tipo": "materia"},
    {"id": "c2", "desde": "heat1", "hacia": "cv1",   "tipo": "calor"},
    {"id": "c3", "desde": "cv1",   "hacia": "medio", "tipo": "materia"},
    {"id": "c4", "desde": "medio", "hacia": "cv2",   "tipo": "materia"},
    {"id": "c5", "desde": "heat2", "hacia": "cv2",   "tipo": "calor"},
    {"id": "c6", "desde": "cv2",   "hacia": "out",   "tipo": "materia"}
  ],
  "supuestos": {
    "estacionario": true, "adiabatico": false, "sinTrabajo": true,
    "sinReaccion": true, "sinMovimiento": true
  },
  "especificaciones": [
    {"bloque_id": "in",  "variable": "F", "valor": 100.0,  "unidad": "mol/s"},
    {"bloque_id": "in",  "variable": "T", "valor": 300.0,  "unidad": "K"},
    {"bloque_id": "in",  "variable": "x", "valor": 0.5,    "unidad": "mol/mol"},
    {"bloque_id": "cv1", "variable": "T", "valor": 310.0,  "unidad": "K"},
    {"bloque_id": "cv2", "variable": "T", "valor": 320.0,  "unidad": "K"}
  ]
}
```

### Lo que hay que saber de la petición

**`componentes` exige dos, y el orden importa.** `x` es la fracción del
primero. Tres componentes se rechazan con `LAB_NUMERO_DE_COMPONENTES`.

**`componentes` y `modelo_termodinamico` son obligatorios en la práctica.**
Si omites el modelo se usa `unifac_raoult`, que es el único, y la
respuesta lo declara. La `referencia_entalpia` importa más de lo que
parece: este cálculo **resta** entalpías, y dos estados medidos contra
referencias distintas no se restan.

**La `T` de un volumen es la de su corriente de SALIDA.** No la de la
alimentación. Es la trampa que el contrato subrayaba: interpretarla como
la de entrada convierte el calentamiento en una identidad y Q sale cero.
La `procedencia` de la variable lo dice explícitamente en la respuesta.

**Una variable se fija una sola vez.** Dos especificaciones sobre la
misma variable son un error **también si coinciden**: la segunda no
aporta nada y esconde cuál manda, así que si mañana una cambia el
conflicto aparece sin que nadie haya tocado la que creía que mandaba.

**Las `relaciones` en LaTeX que exportas se ignoran** como entrada
ejecutable, como pedía el contrato. El motor ensambla desde los tipos
físicos y emite su propio LaTeX. Puedes seguir mandándolas; no cambian
nada. Igual que `estado` y `solver`.

**La presión es uniforme.** Un `p` por bloque que no coincida con
`presion_sistema` se rechaza con `LAB_ESPECIFICACION_EXCLUYENTE`.

---

## 3. Unidades

La unidad es **obligatoria** en cada especificación. Sin ella habría que
suponer SI, y un calor en kW tomado por W da un resultado mil veces
menor que parece perfectamente razonable.

| Magnitud | Admitidas | Canónica (la de la respuesta) |
|---|---|---|
| `F` | `mol/s`, `mol/h`, `kmol/h`, `kmol/s` | `mol/s` |
| `T` | `K`, `degC`, `C`, `°C` | `K` |
| `p` | `Pa`, `kPa`, `bar`, `MPa`, `atm` | `Pa` |
| `x` | `mol/mol`, `-`, `fraccion` | `mol/mol` |
| `Q`, `W` | `W`, `J/s`, `kW`, `MW` | `W` |
| `h` | — (siempre resultado) | `J/mol` |

La temperatura es **afín**, no un factor: `degC` lleva desplazamiento y
las demás no. Es el mismo problema que la LMTD destapó en el informe (ver
[§11](11-unidades.md)): tratar una diferencia de temperatura como una
temperatura resta 273.15 donde no toca.

### El aviso que importa: `bloques[].datos`

Se admite, para que puedas llamar al servicio sin reescribir el
exportador primero. Pero sus unidades son **implícitas**, con las que
documenta la mesa:

| Clave | Unidad implícita |
|---|---|
| `F` | `mol/s` |
| `T` | `K` |
| `p` | `Pa` |
| `x` | `mol/mol` |
| **`Q`** | **`kW`** |

**Esa `Q` en kW es el detalle peligroso de toda la entrega.** La misma
letra significa W en una especificación explícita (donde la unidad va
escrita) y kW en un dato local (donde es implícita). Por eso las
especificaciones explícitas son el camino preferente, y por eso la
respuesta dice en `procedencia` de dónde salió cada valor:

```json
"procedencia": "dato local de 'in' (unidad implicita K)"
"procedencia": "especificacion explicita en 'in' (mol/s)"
```

Una clave ausente en `datos` **no vale cero**: la variable sigue siendo
incógnita. Y un dato local que contradiga una especificación explícita
se denuncia con `LAB_ESPECIFICACION_DUPLICADA`; no se resuelve por orden
de llegada.

---

## 4. Respuesta

### Lo primero que hay que leer

```jsonc
{
  "schema_version": 1,
  "estado": "resuelto",
  "modelo_id": "4b8226d0…",   // 64 hex: identifica el MONTAJE
  "calculo": { "identificador": "…", "motor": {"version": "0.15.0", "commit": "…"} },
  "resumen_diagnosticos": { "total": 3, "hay_errores": false, … }
}
```

**`estado`** y **`resumen_diagnosticos.hay_errores`** son las dos
banderas por las que ramificar:

| `estado` | Qué significa | ¿Mostrar números? |
|---|---|---|
| `valido` | `/validar`: el montaje se sostiene. No se calculó nada | No hay números |
| `invalido` | El montaje o los datos están mal | **No** |
| `no_soportado` | El motor no sabe resolver eso, y lo dice en vez de aproximarlo | **No** |
| `no_convergente` | Se calculó y un residuo no cuadró | **No** |
| `resuelto` | Se resolvió | Sí |

Con cualquier estado distinto de `resuelto`, los valores parciales están
en `null` y `convergencia` es `null`. No hay resultados a medias
presentados como resueltos.

**`modelo_id` vs. `calculo.identificador`.** `modelo_id` identifica el
**sistema**: no cambia si renombras una pieza ni si reordenas bloques,
conexiones o especificaciones, y sí cambia si cambias una temperatura
impuesta. `calculo.identificador` identifica **esta ejecución**: dos
llamadas con el mismo montaje tienen el mismo `modelo_id` y distinto
identificador. Para comparar dos ensayos, compara `modelo_id`.

### `variables`

```json
{
  "id": "medio.T",
  "bloque_ids": ["medio", "cv1", "cv2"],
  "conexion_ids": ["c3", "c4"],
  "simbolo": "T_{4}",
  "magnitud": "T",
  "unidad": "K",
  "rol": "compartida",
  "compartida": true,
  "impuesta": true,
  "valor": 310.0,
  "procedencia": "especificacion explicita en 'cv1' (K): temperatura de su corriente de salida ('medio'). No es la temperatura de la alimentacion."
}
```

**La corriente intermedia referencia UN estado.** Las cinco variables de
`medio` (`F`, `T`, `p`, `x`, `h`) salen con `rol: "compartida"`, y cada
una cita los **dos** volúmenes y las **dos** conexiones. No hay dos
estados que haya que igualar; no hay ecuaciones de continuidad porque no
hacen falta.

`rol` lleva los tres valores que pedía el contrato
(`impuesta`/`calculada`/`compartida`) y no son ortogonales, así que hay
además una bandera `impuesta`. Una variable de corriente intermedia puede
estar impuesta o calculada, y en los dos casos su rol es `compartida`: es
lo que la distingue. La bandera conserva la otra mitad de la información
en vez de que el rol tenga que elegir cuál contar.

Los subíndices del `simbolo` identifican **piezas**, no componentes — la
convención que ya usas en la mesa.

### `ecuaciones`

```json
{
  "id": "cv1:energia",
  "tipo": "balance",
  "titulo": "Conservacion de energia · Primer volumen",
  "origen_bloques": ["cv1", "in", "medio", "heat1"],
  "origen_conexiones": ["c1", "c3", "c2"],
  "variables": ["in.F", "in.h", "medio.F", "medio.h", "heat1.Q"],
  "latex_general": "\\frac{dE_{CV}}{dt} = \\dot Q - \\dot W_s + \\sum_{in} F(h + e_k + e_p) - \\sum_{out} F(h + e_k + e_p)",
  "latex_activo": "\\dot Q_{3} + F_{1} h_{1} = F_{4} h_{4}",
  "terminos_descartados": [
    {"termino": "acumulacion", "latex": "\\frac{dE_{CV}}{dt}",
     "supuesto": "estacionario",
     "motivo": "En estado estacionario la energia del volumen no cambia."}
  ],
  "cuenta_como_ecuacion": true,
  "ejecutada": true,
  "residuo": null,
  "metodo": "evaluacion algebraica directa",
  "alcance": "algebraico_directo",
  "nota": "Se despeja Q de la ecuacion, asi que se satisface por construccion: no hay residuo que medir…"
}
```

**`tipo` es lo que separa lo que cuenta de lo que no:**

| `tipo` | `cuenta_como_ecuacion` | Por qué |
|---|---|---|
| `balance` | **sí** | Conservación |
| `constitutiva` | **sí** | `h = h(T,p,x)`: es donde entra el modelo |
| `condicion` | no | Es un **dato**. Reduce incógnitas, no aumenta ecuaciones |
| `convencion` | no | El signo de Q no es una ecuación |
| `cierre` | no | `Σx = 1` se satisface por la parametrización |
| `verificacion` | no | Es combinación lineal de los balances |

El contrato lo pedía sin rodeos y es la fuente del error más común al
mostrar grados de libertad: contar las especificaciones y las
convenciones infla el número de ecuaciones y los GL salen negativos en un
sistema perfectamente planteado.

**`residuo: null` NO es residuo cero.** Significa que no se midió,
porque no había nada que medir. Donde Q se despeja de la ecuación, la
ecuación se satisface por construcción: publicar el error de redondeo
sería presentarlo como una convergencia. Donde sí hay inversión, el
residuo está, con su `escala`.

**`latex_general` / `latex_activo` / `terminos_descartados`** son los tres
juntos lo que permite explicar la diferencia entre «este término no
aplica» y «este término se olvidó». Cada descartado trae el supuesto que
lo tiró y el motivo.

Para la vista compacta, `origen_bloques` y `origen_conexiones` te dan los
participantes de cada relación; solo las corrientes conectadas al volumen
aportan términos.

### `analisis`

```json
{
  "variables_totales": 17, "impuestas": 8, "incognitas": 9,
  "ecuaciones_independientes": 9, "grados_libertad": 0,
  "rango": 9,
  "rango_origen": "estructural: el sistema es triangular por el orden aguas abajo…",
  "metodo": "marcha aguas abajo con evaluacion algebraica directa por volumen; sin iteracion",
  "alcance": "algebraico_directo",
  "orden_resolucion": ["cv1", "cv2"],
  "no_contadas": {"condicion": 3, "convencion": 2, "cierre": 3, "verificacion": 1}
}
```

El recuento del caso de aceptación: 17 variables, 8 impuestas, 9
incógnitas, 9 ecuaciones, **GL = 0**.

**`rango` es ESTRUCTURAL y `rango_origen` dice de dónde sale.** Para esta
topología el sistema es triangular — cada volumen depende solo de lo que
tiene aguas arriba — y de ahí se sigue que las ecuaciones son
independientes, por el orden y no por un Jacobiano. **No se calcula un
rango numérico local ni se presenta uno**, porque la independencia en un
punto no es la independencia global. Si no se puede determinar, es `null`.

**`metodo` es el algoritmo que de verdad corrió.** En `/validar` es
`null`: no se ejecutó ninguno, así que no hay nada que declarar. Nunca
dirá «Newton», porque ningún Newton corre aquí.

| `alcance` | Cuándo | Algoritmo real |
|---|---|---|
| `algebraico_directo` | Todas las T impuestas | `Q = F(h_sal − h_ent)`, una evaluación |
| `inversion_escalar` | Todos los Q impuestos | `brentq` sobre `h(T)`, xtol 1e-10 K |
| `mixto` | Unos y otros | Las dos cosas, por volumen |

### `convergencia`

`null` cuando no se resolvió.

```json
{
  "metodo": "…", "alcance": "algebraico_directo", "itera": false,
  "inversiones_escalares": null,
  "iteraciones": null,
  "motivo_sin_iteraciones": "No hubo lazo: ver 'motivo_sin_convergencia'.",
  "tolerancia": null, "residuo_escalado": null, "escala_residuo": null,
  "convergio": null,
  "motivo_sin_convergencia": "No hubo iteracion: con la temperatura impuesta en cada volumen, el calor se despeja del balance en una sola evaluacion…",
  "cierre_global": {
    "residuo_relativo": 0.0,
    "escala": "relativo al mayor de |suma de Q| y |F dh|",
    "nota": "Comprobacion independiente: no es una ecuacion del sistema, sino la suma de los balances por volumen."
  }
}
```

**`convergio: null` no es `false`.** Significa que no había nada que
converger. Preséntalo como «evaluación directa», no como un fallo.

**`iteraciones` es siempre `null`, y eso es deliberado.** Lo que se cuenta
en `inversiones_escalares` son las inversiones realizadas (una por volumen
en modo Q), **no** iteraciones de `brentq`: el lazo lo lleva `brentq`
dentro del flash y no publica su contador. Poner ahí el número de
inversiones invitaría a leer «converge en 1 iteración», que es falso.

**`cierre_global` es la única comprobación independiente del resultado.**
No es una ecuación del sistema — es la suma de los balances por volumen —
y por eso mismo sirve: si los balances se resolvieron bien, Σ Q tiene que
igualar `F (h_salida − h_entrada)`. Si se pasa de 1e-8, el estado es
`no_convergente` y hay un error `LAB_CIERRE_GLOBAL`. **Con un solo
volumen no se mide**, porque esa igualdad *es* su balance de energía y
medirla daría el redondeo de la ecuación de la que se despejó Q.

### `estados_por_bloque`

```json
"medio": {"F": 100.0, "T": 310.0, "p": 101325.0, "x": 0.5,
          "h": 1749.1074602946055, "fase": "liquido", "beta": 0.0}
```

**`fase` se DETERMINA, no se supone.** El flash ubica el punto frente al
punto de burbuja y al de rocío a (T, p, x), así que la fase sale como
consecuencia y `beta` es el dato que lo respalda. En el caso de
aceptación los tres estados son líquido subenfriado — la burbuja de
50/50 está a 8894 Pa a 300 K, muy por debajo de 1 atm — pero **el motor
lo comprueba**, no lo da por hecho. El preset `dos-volumenes-bifasico`
sale a 367.5 K con `beta = 0.30`.

---

## 5. Códigos de diagnóstico

Todos llevan prefijo `LAB_`. El **código** es para ramificar y el
**mensaje** para leer: si hay que cambiar un mensaje, el código no se
toca. `accion_sugerida` va separada a propósito — el mensaje dice qué
pasa, la acción dice qué hacer.

**Todos los `bloque_ids`, `conexion_ids` y `variable_ids` que cita un
diagnóstico existen en la petición.** Está comprobado en la suite sobre
siete montajes distintos, incluidos los que fallan.

### Estructura del grafo

| Código | Categoría | Cuándo |
|---|---|---|
| `LAB_ID_DUPLICADO` | datos | Dos bloques o dos conexiones con el mismo id |
| `LAB_REFERENCIA_INEXISTENTE` | datos | Una conexión apunta a un bloque que no existe |
| `LAB_PUERTO_INCOMPATIBLE` | datos | La conexión no representa una entrada ni una salida admitida |
| `LAB_PIEZA_AISLADA` | datos | Una pieza sin conectar |
| `LAB_CICLO` | modelo | Hay un lazo. El mensaje **dice por dónde pasa** |
| `LAB_CORRIENTE_MAL_CONECTADA` | datos | Una corriente intermedia sin exactamente un volumen a cada lado |
| `LAB_VOLUMEN_SIN_ENTRADA` / `LAB_VOLUMEN_SIN_SALIDA` | datos | Un volumen sin corriente de materia a un lado |
| `LAB_TOPOLOGIA_NO_SOPORTADA` | modelo | Más de dos volúmenes, dos alimentaciones, un divisor, un reactor, un tipo de pieza desconocido |

### Especificaciones

| Código | Categoría | Cuándo |
|---|---|---|
| `LAB_ESPECIFICACION_DUPLICADA` | datos | La misma variable fijada dos veces, **también si coinciden** |
| `LAB_ESPECIFICACION_EXCLUYENTE` | datos | T de salida y Q impuestas a la vez; o una p que contradice la uniforme |
| `LAB_FALTA_ESPECIFICACION` | datos | Ni T ni Q impuestas; un valor `null`; un volumen sin intercambio térmico declarado |
| `LAB_VARIABLE_DESCONOCIDA` | datos | Una variable que esa pieza no tiene (`T` en una fuente de calor) |
| `LAB_UNIDAD_INCOMPATIBLE` | datos | Unidad no admitida, o ausente. El mensaje **lista las que sí** |

### Valores

| Código | Categoría | Cuándo |
|---|---|---|
| `LAB_VALOR_NO_FINITO` | datos | NaN o infinito |
| `LAB_FRACCION_INVALIDA` | datos | `x` fuera de [0, 1] |
| `LAB_VALOR_FUERA_DE_DOMINIO` | datos | Caudal, temperatura o presión no positivos |

Sobre NaN: **no puedes mandarlo.** NaN e Infinity no son JSON válido, y
`JSON.stringify` los convierte en `null`. Así que el caso que llega de
verdad es `null`, y sale como `LAB_FALTA_ESPECIFICACION` con el mensaje
«un campo vacío llega como null, y null no es cero». La guarda de
`LAB_VALOR_NO_FINITO` está igualmente, porque un token `NaN` desnudo en
el cuerpo sí lo acepta el parser de Python.

### Supuestos

| Código | Categoría | Cuándo |
|---|---|---|
| `LAB_SUPUESTO_INCOHERENTE` | datos | Fuente de calor conectada **y** supuesto adiabático |
| `LAB_SUPUESTO_NO_SOPORTADO` | modelo | Falta un supuesto, no es booleano, o pide transitorio / reacción / trabajo / cinética |

**Los dos lados de la coherencia.** Una fuente conectada con adiabático
marcado es una contradicción: el supuesto anula el término que la pieza
existe para aportar. Y al revés, **la ausencia de la pieza no significa
Q = 0**: significa que el montaje no declara intercambio térmico, y
entonces el balance de energía le falta un término. Eso sale como
`LAB_FALTA_ESPECIFICACION` con la acción «conecta una fuente de calor o
marca el supuesto adiabático». Son cosas distintas y la diferencia
importa: con Q = 0 supuesto, un volumen al que se le pide subir 10 K
daría un sistema incompatible sin explicación.

### Modelo y resultado

| Código | Categoría | Cuándo |
|---|---|---|
| `LAB_MODELO_NO_DISPONIBLE` | modelo | Modelo o referencia de entalpía que no existe |
| `LAB_COMPONENTE_NO_DISPONIBLE` | modelo | El proveedor no conoce el componente |
| `LAB_NUMERO_DE_COMPONENTES` | modelo | No son dos |
| `LAB_FUERA_DE_DOMINIO_TERMODINAMICO` | **física** | El Q impuesto lleva la entalpía fuera del dominio del modelo |
| `LAB_SIN_CONVERGENCIA` | **numérica** | La inversión h(T) quedó con residuo por encima de 1e-9 |
| `LAB_CIERRE_GLOBAL` | **numérica** | El cierre global no cuadra. Es un fallo del motor, no de los datos |

Las categorías `fisica`, `numerica`, `modelo` y `datos` separan lo que el
usuario puede arreglar de lo que no: `datos` se arregla cambiando un
dato; `fisica` no se arregla iterando más; `modelo` es un límite de la
herramienta; `numerica` es un fallo del algoritmo.

### Informativos

| Código | Cuándo |
|---|---|
| `LAB_INFO_FASE` | La fase y la temperatura de cada salida; y si un Q sale **negativo**, que esa pieza **retira** calor en vez de aportarlo |
| `LAB_INFO_CIERRE_GLOBAL` | El cierre global comprobado, con su residuo |

Severidad `informacion`: no invalidan nada, explican lo que el motor hizo.

---

## 6. Valores por omisión

| Campo | Por omisión | Nota |
|---|---|---|
| `version` | `1` | |
| `modelo_termodinamico` | `"unifac_raoult"` | El único |
| `referencia_entalpia` | `"sensible_liquido_298.15K"` | La única |
| `presion_sistema` | `101325.0 Pa` | Uniforme |
| `especificaciones` | `[]` | Entonces solo valen los `datos` locales |
| `accion` (en `/calcular`) | `"validar"` | El lado seguro: no gasta cálculo si no se lo pidieron |

**Nada se rellena con ceros.** Una clave ausente deja su variable como
incógnita, y si el sistema queda indeterminado se dice.

---

## 7. Capacidades

`GET /laboratorio/capacidades`, y la misma información va embebida en
cada respuesta bajo `capacidades`, para que nunca tengas que hacer dos
llamadas para saber si fiarte de lo que te llegó.

Declara lo admitido **y lo no admitido**, a propósito: un cliente que
solo reciba la lista de lo admitido tiene que adivinar el resto, y
adivinará que algo funciona.

**No soportado en esta entrega:**

- régimen transitorio (`dE/dt`, `dn_i/dt`)
- reacción química en el ensamblador de varios volúmenes
- trabajo de eje
- energías cinética y potencial
- más de una alimentación o más de una salida por volumen
- más de dos volúmenes
- reciclos y ciclos
- caída de presión entre volúmenes (la presión es uniforme)
- mezclas de más de dos componentes
- mallado, CFD y dinámica espacial

El CSTR sigue en `/diagrama/resolver` **con su balance de energía
desactivado**, como estaba. Acoplarlo aquí exige resolver ese balance, no
solo escribirlo, y está comprobado en la suite que esta entrega no lo
activó por el camino.

---

## 8. Lo que está verificado

`tests/validar_laboratorio.py`. **Los números no están escritos a
mano**: se comparan contra llamadas independientes al mismo proveedor
termodinámico. Si copiara la salida del ensamblador como valor esperado,
la prueba bendeciría cualquier error que tuviera.

**Contra el proveedor, por el camino corto:**

- `Q₁ = 147842.851474 W` y `Q₂ = 150506.362426 W` coinciden con
  `F(h₃₁₀−h₃₀₀)` y `F(h₃₂₀−h₃₁₀)` pedidas por separado.
- La `h` de cada estado coincide con la del flash independiente, y la
  **fase** también.

**Identidades que no dependen de ningún dato:**

- `Q₁ + Q₂ = F(h₃₂₀ − h₃₀₀)`, con residuo relativo medido `< 1e-12`.
- Duplicar `F` duplica `Q₁` y `Q₂` exactamente.
- Imponer el `Q₁` calculado recupera **310 K**, con error `0.0 K`.
- El preset de un volumen da el **mismo** `Q` que `/diagrama/resolver`
  para el mismo problema: dos caminos, un número.

**Y un dato que conviene conocer:** `Q₂` es un **1.80 % mayor** que `Q₁`
para el mismo salto de 10 K. Cp crece con T, así que calentar de 310 a
320 cuesta más que de 300 a 310. Si la interfaz muestra un Cp constante
en algún sitio, ahí hay una inconsistencia con lo que el motor calcula.

**El caso bifásico**, que es el que saca al simulador de la fase líquida:
con 2 MW la corriente intermedia sale a 367.5 K con `beta = 0.3018`, y 1
MW más sube la temperatura solo **2.1 K** porque casi todo va a calor
latente — frente a los ~10 K que costaban 0.15 MW en la zona líquida.

Los siete grupos de la suite cubren: uno y dos volúmenes con continuidad
y conservación; los modos excluyentes; los montajes mal formados (ids,
referencias, puertos, aislados, ciclos, null/NaN, fracciones, unidades,
modelo y componentes); el dominio termodinámico sin presentar resultados
a medias; que los ids de los diagnósticos existan y que las ecuaciones
marcadas como ejecutadas correspondan al cálculo real; la no regresión de
`/diagrama/resolver` y del CSTR; y el reenvío de los presets al endpoint.

---

## 9. Lo que te hará falta y no está

- **Caída de presión entre volúmenes.** La presión es uniforme. El
  modelo de caída existe en `/diagrama/resolver` pero no está en el
  ensamblador.
- **Más de dos volúmenes.** El límite es del ensamblador, no de la
  física; la marcha aguas abajo sirve para N.
- **El decantador no está expuesto en ninguna API.** Existe en el motor y
  no se puede pedir por HTTP. Es una laguna anterior a esta entrega.
- **Reactor y reacción.** El CSTR sigue donde estaba, sin balance de
  energía.
- **`iteraciones` reales de `brentq`.** Haría falta exponer el contador
  desde el flash y la calculadora de entalpía, y eso toca física
  validada; no lo he hecho por una métrica.

Detalle técnico completo en [`docs/15-laboratorio.md`](15-laboratorio.md).
