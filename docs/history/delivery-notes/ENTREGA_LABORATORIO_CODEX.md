# Entrega del backend: núcleo granular del laboratorio

Respuesta a `frontend/PASAR_A_CLAUDE_LABORATORIO.md`. Solo backend; ningún
archivo de `frontend/` se ha tocado.

**Lo que hay:** un ensamblador que toma el grafo de piezas de la mesa y
resuelve un sistema estacionario de hasta **dos volúmenes** unidos por una
corriente intermedia con **identidad única**, con **balances molares por
especie y transformación estequiométrica**. Reutiliza el proveedor de
propiedades, el flash y la calculadora de entalpía existentes. Sin CFD,
sin mallado, sin columna completa y sin interpretar LaTeX.

> **Cuarta entrega** (lote transitorio, equilibrio químico calculado y
> balanceo exacto), respondiendo a la prioridad vigente de
> `frontend/PENDIENTES_BACKEND_CLAUDE.md`: puntos **3** y **4**, más la
> parte de la «migración de exploraciones locales» que corresponde al
> balanceo racional y a Hess/Kirchhoff.
>
> Lo anterior sigue funcionando y está comprobado. Lo que cambió de forma
> visible está en [§11](#11-qué-cambió-respecto-a-las-entregas-anteriores),
> y **hay un cambio de resultado**: `desde_equilibrio` pasa a usar la K
> rigurosa en vez de van't Hoff.
>
> **Lo que NO está**: las áreas 6–10 y los transversales. Ver
> [§12](#12-lo-que-queda-de-la-lista).

> **Quinta entrega** (estudios sobre un montaje: estacionario y temporal),
> respondiendo a `frontend/INICIO_CLAUDE_MOTOR_ACOPLADO.md` y
> `frontend/CONTRATO_ESTUDIOS_DINAMICOS_CLAUDE.md`. Es un contrato **nuevo**
> en rutas propias, `/laboratorio/estudios/*`: ver
> [§13](#13-estudios-sobre-un-montaje-estacionario-y-temporal). Lo anterior
> no cambia de forma; el único cambio visible fuera de §13 es el texto del
> rechazo de `estacionario: false` en `/laboratorio/resolver`, que ahora
> apunta a la ruta nueva.

> **Sexta entrega** (energía en los estudios), respondiendo a
> `frontend/ENTREGA_ENERGIA_REACTIVA_CLAUDE.md`: **entrega A** (materia +
> energía, sin reacción) en [§14](#14-estudios-con-energía-materia--energía-sin-reacción-entrega-a).
> La **entrega B** (fuentes reactivas por volumen) está en
> [§15](#15-estudios-con-reacción-fuentes-reactivas-por-volumen-entrega-b).
> La transferencia estacionario → temporal **no está**, y `capacidades` lo
> dice.

> **Séptima entrega** (auditoría por combinación, procedencia por término e
> interfaz térmica), respondiendo a
> `frontend/SIGUIENTE_CLAUDE_CIERRES_TRANSFERENCIA.md`: ver
> [§16](#16-auditoría-por-combinación-procedencia-por-término-e-interfaz-térmica).
> Corrige además el hallazgo de la revisión de B (el `latex_activo` de las
> verificaciones globales omitía la fuente química).

> **Octava entrega** (un estacionario como condición inicial de un
> temporal), respondiendo a
> `frontend/ENTREGA_CLAUDE_TRAZABILIDAD_REUTILIZACION.md`: ruta nueva
> `POST /laboratorio/estudios/transferir`, ver
> [§17](#17-un-estacionario-como-condición-inicial-de-un-temporal).
> **Corrección posterior** (§17.11): la firma de `condicion_inicial` es ahora
> estable tras un roundtrip JSON en JavaScript. **Los objetos generados antes
> se rechazan y hay que volver a transferir.** Una
> petición material no cambia de resultado ni de `modelo_id`; los campos
> nuevos de la respuesta están en §14.9.

> **Novena entrega** (reacción + interfaz térmica), respondiendo a
> `frontend/SIGUIENTE_CLAUDE_REACCION_INTERFAZ.md`: la combinación deja de
> rechazarse, verificada; ver [§18](#18-reacción--interfaz-térmica). Incluye
> dos correcciones generales: un evento antes de la primera muestra y un
> cero numérico negativo en la transferencia (ahora una corrección
> **declarada**).

> **Décima entrega** (interfaz de transferencia de materia), respondiendo a
> `frontend/SIGUIENTE_CLAUDE_TRANSFERENCIA_MATERIA.md`: dos compartimentos
> cerrados que intercambian **una** especie, solo estudio temporal; ver
> [§19](#19-interfaz-de-transferencia-de-materia-entre-dos-compartimentos).
> Añade un cierre (`volumen_fijo`) y un tipo de conexión
> (`transferencia_materia`); **no cambia** los cierres existentes ni las
> condiciones del estacionario de ningún montaje anterior.

> **Undécima entrega** (transferencia selectiva de materia + energía),
> respondiendo a `frontend/SIGUIENTE_CLAUDE_TRANSFERENCIA_MATERIA_ENERGIA.md`:
> **hito A completado** (modelo `ideal_volumen_fijo`, energía transportada
> por estado del donante, soluto diluido declarado) y **hito B comprobado y
> no disponible**; ver
> [§20](#20-transferencia-selectiva-de-materia--energía).

> **Duodécima entrega** (una sola especie y balances por volumen),
> respondiendo a `frontend/SUPUESTOS_POR_VOLUMEN_CLAUDE.md`: los estudios
> admiten de 1 a 8 componentes (agua pura sin componente ficticio) y el
> contrato `balances_por_volumen` sustituye a `data.balances`, con
> `balances`, `pendientes` y `contradicciones` en la respuesta; ver
> [§21](#21-una-sola-especie-y-balances-por-volumen).

> **Decimotercera entrega** (unidades y especificaciones flexibles),
> respondiendo a `frontend/ENTREGA_CLAUDE_ESPECIFICACIONES_UNIDADES.md`:
> registro único de unidades en `GET /laboratorio/estudios/unidades`,
> `catalogo_variables` y `cantidades_normalizadas` en cada respuesta, y el
> cierre `balance_general` con `seleccion_variables` (estacionario directo e
> inverso, temporal directo; una especie). Problemas inversos temporales:
> no disponibles. Ver
> [§22](#22-unidades-catálogo-de-variables-y-especificaciones-flexibles).

> **Decimocuarta entrega** (recuento canónico), respondiendo a
> `frontend/ESTADO_MODELO_EXPERIMENTAR.md`: campo `recuento` (versión 1) en
> `/validar` y `/resolver`, con estado de completitud, indicador, desglose y
> referencias estructuradas; sin cambios de física. Ver
> [§23](#23-recuento-canónico-del-problema).

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
| `GET` | `/laboratorio/sustancias/buscar?q=` | Identifica una sustancia **y dice cómo la identificó** |
| `GET` | `/laboratorio/sustancias/catalogo` | Qué identificadores y capacidades admite |
| `POST` | `/laboratorio/balancear` | Las ν que conservan los elementos, en **aritmética exacta** |
| `POST` | `/laboratorio/comprobar-estequiometria` | Juzga una ν dada |
| `POST` | `/laboratorio/equilibrio` | Composición de equilibrio, K(T), μ y estabilidad |
| `POST` | `/laboratorio/lote` | La trayectoria de un lote isotermo |
| `GET` | `/laboratorio/reacciones/capacidades` | Qué admiten esos tres, y qué no |
| `POST` | `/laboratorio/estudios/validar` | Estudio estacionario o temporal: ensambla y clasifica sin resolver ([§13](#13-estudios-sobre-un-montaje-estacionario-y-temporal)) |
| `POST` | `/laboratorio/estudios/resolver` | Lo resuelve sobre el mismo ensamblaje |
| `GET` | `/laboratorio/estudios/capacidades` | Qué estudios, cierres e integradores admite, y qué no |
| `GET` | `/laboratorio/estudios/ejemplos[/{id}]` | Estudios de ejemplo reenviables |
| `POST` | `/laboratorio/estudios/transferir` | El estado de un estacionario como condición inicial de un temporal ([§17](#17-un-estacionario-como-condición-inicial-de-un-temporal)) |

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

Y los reactivos:

| Archivo (`-peticion` / `-respuesta`) | Qué muestra |
|---|---|
| `laboratorio-reactor-isomerizacion-*` | A → B. Consumo y generación iguales al avance; `Σν = 0`, el caudal no cambia |
| `laboratorio-reactor-volumetrico-*` | La misma, con la tasa en `mol/(m3*s)` y `V = 5 m³`. Mismo resultado |
| `laboratorio-reactor-a-dos-b-*` | A → 2B. El caudal molar pasa de 100 a 110 y la masa no se mueve |
| `laboratorio-reactor-reversible-*` | `r⁺ = 2`, `r⁻ = 8`. La inversa intercambia producción y consumo |
| `laboratorio-reactor-en-equilibrio-*` | `r⁺ = r⁻ = 5`: **neto cero y brutas positivas** |
| `laboratorio-reactor-solo-neta-*` | Misma salida, **brutas en `null`** con su motivo |
| `laboratorio-dos-reactores-en-serie-*` | Dos reactores compartiendo la corriente, con el cierre global |
| `laboratorio-estequiometria-invalida-*` | Un rechazo: `ν = [−1, +2]` no conserva los elementos |

Y los cinéticos (isomerización de butano a **20 bar**, para que se quede en
líquido: a 5 bar la mezcla cruza la frontera de fase al reaccionar y la
entalpía da un salto de 18 kJ/mol — el motor lo resuelve igual y lo
reporta, pero un ejemplo que se entienda conviene que no lo haga):

| Archivo (`-peticion` / `-respuesta`) | Qué muestra |
|---|---|
| `laboratorio-cinetica-isoterma-*` | La tasa se calcula; `brentq` acotado por la estequiometría |
| `laboratorio-cinetica-adiabatica-*` | **T y avance cerrados a la vez**; 320 → 369.46 K |
| `laboratorio-cinetica-reversible-*` | Dos leyes, una por sentido: las brutas se conocen |
| `laboratorio-cinetica-desde-equilibrio-*` | `k_inv = k_dir / K_eq(T)`, con sus dos avisos |
| `laboratorio-cinetica-volumetrica-*` | `10 mol/(m³·s) × 5 m³ = 50 mol/s`: idéntico al isotermo |
| `laboratorio-cinetica-orden-negativo-*` | Un rechazo: la tasa divergiría al agotarse la especie |

Y los de esta entrega (xilenos: o-, m- y p-, todos C8H10, con propiedades
completas y **γ = 1 exactamente**, que es lo que permite comprobar contra
el álgebra sin que UNIFAC se interponga):

| Archivo (`-peticion` / `-respuesta`) | Qué muestra |
|---|---|
| `laboratorio-balancear-combustion-*` | CH₄ + 2 O₂ → CO₂ + 2 H₂O, **sin necesitar UNIFAC** |
| `laboratorio-balancear-subespacio-*` | CO/CO₂/H₂/H₂O/CH₄: **dimensión 2**, se devuelve la base |
| `laboratorio-balancear-sin-reaccion-*` | CH₄/N₂: no hay reacción posible, y eso es la respuesta |
| `laboratorio-comprobar-nu-incorrecta-*` | Una ν que descuadra, con qué elemento y en cuánto |
| `laboratorio-equilibrio-una-reaccion-*` | K(T) por las dos rutas, μ y el hessiano |
| `laboratorio-equilibrio-dos-reacciones-*` | Dos reacciones acopladas, hessiano 2×2 |
| `laboratorio-lote-primer-orden-*` | La trayectoria más simple |
| `laboratorio-lote-consecutiva-*` | A → B → C, con el máximo del intermedio |
| `laboratorio-lote-paralela-*` | A → B, A → C, con la selectividad |
| `laboratorio-lote-hacia-el-equilibrio-*` | Cinética consistente: llega al equilibrio calculado |

Y del catálogo:

| Archivo | Qué muestra |
|---|---|
| `laboratorio-sustancia-formula-ambigua.json` | `C2H6O` → dimetil éter, con etanol entre los candidatos |
| `laboratorio-sustancia-por-nombre.json` | La misma consulta bien hecha |
| `laboratorio-sustancia-sin-entalpia-de-formacion.json` | Sirve para ELV y no para reacción |
| `laboratorio-sustancias-catalogo.json`, `laboratorio-reacciones-capacidades.json` | Las capacidades |

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

**`componentes` admite de 2 a 8, y el orden importa.** Las fracciones se
llaman `x0`, `x1`, … `x{n-1}`, en ese orden. **`x` a secas vale como alias
de `x0` solo en binarios**: con tres especies no identifica ninguna, y
aceptarlo obligaría a adivinar.

**Una fracción de cero es válida** y significa que esa especie no está. Lo
digo porque hasta esta entrega se rechazaba: el dominio trataba todas las
magnitudes igual, y para un caudal cero no es un caudal pequeño sino la
ausencia de corriente. Para una fracción molar sí es físico, y con tres
especies y una alimentación pura es lo normal.

**No hace falta dar las n fracciones.** Dando n−1, el cierre determina la
que falta. Dándolas todas, el cierre deja de calcular y **comprueba**: si
no suman 1, es `LAB_DATOS_COMPOSICION_INCOMPATIBLE`.

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
| `V` | `m3`, `L`, `dm3`, `cm3`, `mL` | `m3` |
| `h` | — (siempre resultado) | `J/mol` |
| `F_i` | — (siempre resultado) | `mol/s` |

Y las tasas de reacción, cuya unidad además **declara la base** (ver
[§7bis](#7bis-reacción)).

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
"medio": {
  "F": 100.0, "T": 310.0, "p": 101325.0, "h": 1749.1074602946055,
  "x": 0.5,
  "composicion": [0.5, 0.5],
  "por_especie": [
    {"componente": "benzene", "x": 0.5, "F_i": 50.0, "unidad_F_i": "mol/s"},
    {"componente": "toluene", "x": 0.5, "F_i": 50.0, "unidad_F_i": "mol/s"}
  ],
  "fase": "liquido", "beta": 0.0
}
```

**`x` se conserva por compatibilidad** y es la fracción del primer
componente, igual que antes. Es `null` con tres o más especies: usa
`composicion` o `por_especie`.

**`F_i` es derivado**, `F·x_i`. No es una variable del sistema —declararlo
como tal añadiría n incógnitas y n ecuaciones que se cancelan— pero es lo
que hace falta para comprobar la conservación de elementos y masa.

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

### Reacción y estequiometría

Llevan prefijo `LAB_` como los demás, pero fallan por otro motivo: una
estequiometría que no conserva los elementos no es un error de montaje ni
de unidades, es un dato que no describe ninguna reacción química.

| Código | Categoría | Cuándo |
|---|---|---|
| `LAB_REACCION_EN_NO_REACTOR` | datos | La reacción cuelga de un `recipiente` o de una pieza que no es un volumen |
| `LAB_ESTEQUIOMETRIA_INVALIDA` | datos | `ν` de longitud equivocada, no finita, toda a cero, o sin reactivo y producto a la vez |
| `LAB_ELEMENTOS_NO_CONSERVADOS` | datos | `A·ν ≠ 0`. El mensaje dice **qué elemento descuadra y en cuánto** |
| `LAB_MASA_NO_CONSERVADA` | datos | `MW·ν ≠ 0` |
| `LAB_TASA_AMBIGUA` | datos | Ninguna tasa, varias formas a la vez, o una reversible con solo una de las dos |
| `LAB_TASA_NEGATIVA` | datos | Una tasa **bruta** negativa. Son velocidades; el signo lo lleva `ν` |
| `LAB_FALTA_VOLUMEN_REACTOR` | datos | Base volumétrica sin `V`. **No se supone 1 m³** |
| `LAB_CAUDAL_ESPECIE_NEGATIVO` | **física** | El avance consume más de lo que entra |
| `LAB_CINETICA_NO_SOPORTADA` | modelo | Se pasó `cinetica`, `A` o `Ea` |
| `LAB_SIN_REACCION_DECLARADA` | datos (error) / advertencia | Un reactor sin reacción y sin `sinReaccion` es error; `sinReaccion: false` sin ningún reactor es advertencia |
| `LAB_ENTALPIA_FORMACION_NO_DISPONIBLE` | datos | Falta `Hf` líquida de alguna especie. Suponerla cero convertiría una exotérmica en un calentador neutro |
| `LAB_CONSERVACION_NO_MEDIDA` | **numérica** | Elementos o masa no cuadran sobre los caudales resueltos. Es un fallo del motor, no de los datos |
| `LAB_DATOS_COMPOSICION_INCOMPATIBLE` | datos | Se dieron las n fracciones y no suman 1 |

### Cinética

| Código | Categoría | Cuándo |
|---|---|---|
| `LAB_LEY_INVALIDA` | datos | La ley no es un objeto, falta la constante, `k_ref` sin `T_ref`, `ley_inversa` sin `ley_directa`, o parámetros cinéticos sueltos (`A`/`Ea`/`cinetica`) sin una ley |
| `LAB_ORDEN_INVALIDO` | datos | Órdenes negativos, de longitud equivocada, no finitos, o de una especie que no está en la mezcla |
| `LAB_BASE_ACTIVIDAD_NO_SOPORTADA` | datos | Una base que no es `actividad` ni `fraccion_molar`. La concentración necesitaría el volumen molar de la mezcla |
| `LAB_EQUILIBRIO_NO_UTILIZABLE` | física | `desde_equilibrio` sin las energías de Gibbs de formación, o con un `K_eq` no utilizable |
| `LAB_SIN_CAMBIO_DE_SIGNO` | **numérica** | El residuo no cambia de signo en el intervalo estequiométrico: no hay avance físico que satisfaga la ley |
| `LAB_IMPLICITO_SIN_CONVERGENCIA` | **numérica** | El sistema no convergió, o se quedó en un límite. El mensaje trae el residuo y la tolerancia |

Y `LAB_TASA_AMBIGUA` cubre también dar una ley **y** una tasa a la vez:
una reacción tiene la tasa dada **o** calculada, no las dos.

### Balanceo, equilibrio y lote

| Código | Categoría | Cuándo |
|---|---|---|
| `LAB_SIN_BALANCE_POSIBLE` | modelo | No hay ninguna ν que conserve los elementos entre esas especies |
| `LAB_BALANCEO_NO_UNICO` | modelo (**advertencia**) | Hay varias reacciones independientes: se devuelve la base y no se elige una |
| `LAB_EQUILIBRIO_SIN_CONVERGENCIA` | **numérica** | El equilibrio no convergió; el mensaje trae el residuo y la tolerancia |
| `LAB_EQUILIBRIO_NO_UTILIZABLE` | física | Faltan propiedades de formación, o el hessiano no es definido positivo (**advertencia** en este segundo caso) |
| `LAB_METODO_NO_SOPORTADO` | datos | Un método de integración que no está |
| `LAB_INTEGRACION_FALLIDA` | **numérica** | `solve_ivp` no pudo avanzar |
| `LAB_TRAYECTORIA_NEGATIVA` | **numérica** | La trayectoria devuelta tiene moles negativos |

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

## 7ter. El catálogo de sustancias

`GET /laboratorio/sustancias/buscar?q=...`

Es lo que necesitas para el editor de especies. No sustituye a
`/componentes/buscar` —que contesta «existe y tiene grupos UNIFAC»— sino
que contesta las dos preguntas que esa no cubre.

### Una fórmula NO identifica una sustancia

Y no es una precaución teórica:

| Consulta | Resuelve a | CAS | T de ebullición |
|---|---|---|---|
| `C2H6O` | **dimethyl ether** | 115-10-6 | 248.4 K |
| `ethanol` | ethanol | 64-17-5 | 351.6 K |

Las dos tienen fórmula C2H6O. **103 K de diferencia** por escribir la
fórmula en vez del nombre, y el cálculo sale perfectamente bien para la
sustancia equivocada.

Así que la respuesta trae:

```jsonc
{
  "identificacion": "formula",
  "identificacion_fiable": false,          // ← el campo que hay que mirar
  "sustancia": {"id": "115-10-6", "nombre": "dimethyl ether", …},
  "candidatos": [{"id": "64-17-5", "nombre": "ethanol", …}],
  "candidatos_totales": 1,
  "aviso": "'C2H6O' es una FORMULA, y una formula no identifica una sustancia…"
}
```

| `identificacion` | ¿Identifica? |
|---|---|
| `cas`, `nombre`, `smiles`, `inchi_key` | **sí** |
| `formula` | **no** — mira `candidatos` y pregunta |
| `no_encontrada` | — |

**El id estable es el CAS.** Es lo que conviene guardar: el nombre tiene
sinónimos y cambia de idioma, la fórmula es ambigua.

### Tener grupos UNIFAC no basta para reaccionar

La segunda pregunta. `capacidades` responde una por una, y dice qué falta:

```jsonc
"capacidades": {
  "elv":        {"disponible": true,  "falta": []},
  "entalpia":   {"disponible": true,  "falta": []},
  "reaccion":   {"disponible": false, "falta": ["entalpia de formacion (Hfm)"]},
  "equilibrio": {"disponible": false, "falta": ["entalpia de formacion (Hfm)",
                                                "energia de Gibbs de formacion (Gfm)"]}
}
```

Ese es el **diciclopentadieno** de verdad: tiene grupos UNIFAC, así que
sirve para un ELV, y **no tiene entalpía de formación**, así que no sirve
para un balance reactivo. Si el editor lo ofrece para una reacción, el
error aparece al resolver, con el calor de reacción en NaN. Eso es tarde.

Está comprobado en la suite que el montaje con esa especie se rechaza con
`LAB_ENTALPIA_FORMACION_NO_DISPONIBLE` — el mismo fallo que el catálogo
avisaba antes de calcular.

La respuesta trae además `propiedades` (Tb, Tm, Tc, pc, Hfm, Gfm, cada una
con su unidad y su referencia), `composicion_elemental` (los átomos, que
es lo que valida una ν), `modelos_soportados`, `fases` y `referencias`.

---

## 7bis. Reacción

### Dónde va y qué forma tiene

Una reacción pertenece a un bloque de tipo **`reactor`**. La producción y
la desaparición química pertenecen al volumen donde ocurren: no son
alimentaciones ficticias. Una reacción colgada de un `recipiente` se
rechaza con `LAB_REACCION_EN_NO_REACTOR`.

```json
"reacciones": [
  {"id": "dim", "bloque_id": "rx", "nu": [-2.0, 1.0],
   "tasa_directa": {"valor": 5.0, "unidad": "mol/s"},
   "tasa_inversa": {"valor": 5.0, "unidad": "mol/s"}}
]
```

**`nu` lleva un coeficiente por componente, en el mismo orden, positivo
producto y negativo reactivo.** El signo va en el coeficiente y no en la
tasa, porque un mismo evento produce unos componentes y consume otros.
Las tasas brutas son velocidades: siempre ≥ 0.

### Las tres formas de declarar la tasa, y por qué son tres

| Forma | Reacción | ¿Brutas disponibles? |
|---|---|---|
| `tasa` | irreversible, una dirección | **sí** |
| `tasa_directa` + `tasa_inversa` | reversible | **sí** |
| `tasa_neta` | solo el neto | **no** |

No son tres maneras de escribir lo mismo: la tercera **sabe menos**. Dar
más de una es un error, no una preferencia.

### La precisión que el contrato exige: bruto no es neto

Una reacción reversible en equilibrio tiene `r⁺ = r⁻ > 0`. La fuente neta
de cada especie es **cero** y, aun así, cada especie se está produciendo y
consumiendo a un ritmo **positivo**. Las moléculas no están quietas: están
yendo y viniendo a la misma velocidad.

El preset `reactor-en-equilibrio` lo muestra con `r⁺ = r⁻ = 5 mol/s`:

```json
"por_especie": [
  {"componente": "isobutene",     "nu": -2.0,
   "generacion_bruta": 10.0, "consumo_bruto": 10.0, "fuente_neta": 0.0},
  {"componente": "diisobutylene", "nu":  1.0,
   "generacion_bruta":  5.0, "consumo_bruto":  5.0, "fuente_neta": 0.0}
]
```

De ahí se siguen tres reglas, y las tres están implementadas:

1. **Con `r⁺` y `r⁻` por separado**, las brutas se calculan:
   `G_i = max(ν_i,0)·r⁺ + max(−ν_i,0)·r⁻` y simétrico para `C_i`. El
   evento directo produce lo que tiene ν > 0; el inverso, lo que tiene
   ν < 0. Las dos cosas generan.
2. **Con solo la tasa neta**, `generacion_bruta` y `consumo_bruto` salen
   **`null`** con su motivo. **Nunca se rellenan con `max(neto, 0)`**: eso
   daría cero generación en una reacción que está funcionando a toda
   velocidad. Compara `reactor-en-equilibrio` con `reactor-solo-neta`:
   misma composición de salida, y uno sabe las brutas y el otro no.
3. **La descomposición del neto sí se ofrece**, en
   `descomposicion_neta.aparente_generacion` / `aparente_consumo`, y
   etiquetada como lo que es. Es el signo del neto repartido en dos
   casillas no negativas, **no** el intercambio bruto. En el equilibrio da
   cero en las dos mientras las brutas valen 10 y 5.

**Para la interfaz:** mira `brutas_disponibles` antes que nada. Si es
`false`, muestra «no disponible» y el motivo, no un cero. Un cero ahí
afirma que la reacción está parada cuando puede estar a toda velocidad.

Y en `fuentes_por_volumen`, si **alguna** reacción del volumen solo trae su
tasa neta, las brutas del volumen entero no están disponibles: `G_i` es una
suma y un término desconocido hace desconocida la suma. El motivo nombra la
reacción culpable.

### Las bases: integrada frente a volumétrica

La **unidad** declara la base, que es lo menos ambiguo posible:

| Base | Unidades | Necesita |
|---|---|---|
| integrada | `mol/s`, `mol/h`, `kmol/s`, `kmol/h` | nada |
| volumétrica | `mol/(m3*s)`, `mol/(m3*h)`, `kmol/(m3*s)`, `kmol/(m3*h)`, `mol/(L*s)`, `mol/(dm3*s)`, `mol/(cm3*s)` | `V` del reactor |

Una tasa volumétrica sin `V` **no se supone 1 m³**: se diagnostica con
`LAB_FALTA_VOLUMEN_REACTOR`. `V` se da como especificación sobre el
reactor (`{"bloque_id": "rx", "variable": "V", "valor": 5.0, "unidad":
"m3"}`), y la respuesta dice en `base_tasa`, `unidad_declarada` y
`volumen_m3` qué se usó. El preset `reactor-volumetrico` da exactamente el
mismo resultado que `reactor-isomerizacion`: 4 mol/(m³·s) × 5 m³ = 20
mol/s.

### Conservación

**Antes de resolver**, la estequiometría se valida contra la matriz
elemental que da `thermo`:

$$ A \cdot \nu = 0 \quad\text{y}\quad MW \cdot \nu = 0 $$

Una ν que no la cumpla no es una reacción: es un dato mal puesto, y se
rechaza con `LAB_ELEMENTOS_NO_CONSERVADOS` diciendo **qué elemento
descuadra y en cuánto**.

**Después de resolver**, elementos y masa se **miden** sobre los caudales
resueltos, en `conservacion[bloque_id]`. No es la misma comprobación:
aquello verifica que la reacción tenga sentido, esto que el balance se
haya aplicado bien. Una reacción bien balanceada con un balance mal
aplicado pasa la primera y falla la segunda.

**El caudal molar total PUEDE cambiar.** `Σν` no tiene por qué ser cero, y
`conservacion[...].caudal_molar.cambia` lo dice. El preset
`reactor-a-dos-b` pasa de 100 a 110 mol/s sin mover un gramo de masa. Un
caudal molar que cambia parece un balance roto y no lo es; si la interfaz
avisa de eso, avisará en falso.

### La energía reactiva, y el doble conteo que hay que evitar

La referencia de entalpía de este motor es **sensible**: `h` no incluye
las entalpías de formación. Así que el balance de un volumen reactivo
lleva el calor de reacción **explícito**:

$$ \dot Q + F_{ent} h_{ent} - F_{sal} h_{sal} - \sum_r \dot\xi_r \Delta H_{rxn,r} = 0 $$

Dos cosas que conviene tener claras:

- **`ΔH_rxn` se evalúa a la temperatura de REFERENCIA, no a la del
  volumen.** No es una aproximación: las entalpías sensibles ya se
  encargan de toda la dependencia con T. Corregir `ΔH_rxn` con Kirchhoff
  aquí **sería contarlo dos veces**.
- **La decisión de sumar el término cuelga de la referencia, no de que
  haya reacción.** `capacidades.referencias_entalpia[...].incluye_formacion`
  dice en qué lado está cada una. Si algún día hay una referencia que
  incluya formación, el término **no** aparecerá —ya estaría dentro de
  `h`— y figurará en `terminos_descartados` con ese motivo. Es el error
  que el contrato pide evitar, visto desde los dos lados.

Con `ξ = 0` el calor de reacción es cero **aunque las brutas sean
positivas**: el calor lo mueve el avance neto. El preset
`reactor-en-equilibrio` lo comprueba.

### El cierre global con reacción

$$ \sum_j \dot Q_j = F_{sal} h_{sal} - F_{ent} h_{ent} + \sum_r \dot\xi_r \Delta H_{rxn,r} $$

Al sumar los balances por volumen, los estados intermedios se cancelan
—son la **misma** variable— pero los términos de reacción se acumulan. En
`dos-reactores-en-serie`: ΣQ = −2 517 877.48 W = transporte 249 622.52 +
reacción −2 767 500.00, con residuo medido **0.0**.

### Lo que NO hay

- **Cinética.** La tasa tiene que estar especificada. Una tasa que
  dependa de la composición de salida hace el balance implícito y exige un
  solver acoplado; se rechaza con `LAB_CINETICA_NO_SOPORTADA` en vez de
  ignorarse, y el CSTR con cinética sigue en `/diagrama/resolver`.
- **Equilibrio químico.** El motor no calcula el avance a partir de `K`.
- **`sinReaccion` es ahora un supuesto libre.** En `true` anula a la vez
  producción, consumo y cierres cinéticos, y es incompatible con una
  reacción declarada. En `false` exige que cada reactor declare la suya:
  la ausencia de una reacción declarada no significa que no haya reacción,
  significa que al balance por especie le falta un término. Con `false` y
  ningún reactor, sale una **advertencia** (no un error).

---

## 7quater. Cinética: la tasa se calcula

Hasta ahora la tasa era un dato. Ahora puede ser una **ley de acción de
masas**, y eso cambia la naturaleza del problema.

### Lo que cambia

$$ \xi_r = r_r(T, \mathbf{x}_{salida}) \qquad \mathbf{x}_{salida} = \mathbf{x}_{salida}(\xi) $$

La tasa depende de la composición de **salida**, que es lo que el balance
calcula. El sistema del volumen se vuelve **implícito**. Es el motivo de
que la entrega anterior rechazara la cinética con un diagnóstico: resolver
un sistema implícito con una marcha aguas abajo habría dado números, y
números de otro problema.

**La marcha aguas abajo entre volúmenes sigue valiendo** —la entrada de
cada uno es la salida del anterior, ya determinada— y lo implícito está
**dentro** de cada volumen. `convergencia.metodo` lo dice con esas
palabras.

### La declaración

```json
"reacciones": [
  {"id": "iso", "bloque_id": "rx", "nu": [-1.0, 1.0],
   "ley_directa": {
     "k_ref": {"valor": 50.0, "unidad": "mol/s"},
     "T_ref": {"valor": 320.0, "unidad": "K"},
     "Ea": 50000.0,
     "base_actividad": "actividad",
     "ordenes": {"n-butane": 1.0}
   }}
]
```

$$ r = k(T)\prod_i a_i^{n_i} $$

**Los órdenes son explícitos, y eso importa.** Un orden **no** es un
coeficiente estequiométrico: la ley sale de un mecanismo y la
estequiometría de un balance, y coinciden solo en una reacción elemental.
Si no los declaras se usa |ν| de los reactivos y la respuesta **dice que
ese fue el defecto**, para que nadie crea que lo eligió.

Los órdenes **negativos se rechazan**: modelan inhibición y hacen que la
tasa diverja cuando esa especie se agota, así que el motor no puede
garantizar un resultado acotado.

### Arrhenius: dos formas, y una es mejor

| Forma | Expresión |
|---|---|
| referenciada | $k = k_{ref}\,e^{-\frac{E_a}{R}\left(\frac{1}{T}-\frac{1}{T_{ref}}\right)}$ |
| clásica | $k = A\,e^{-E_a/RT}$ |

La referenciada está mejor condicionada: $A$ tiene magnitudes absurdas
($10^{13}$ y más) y el exponente vale −20 o −40, así que la expresión
resta números enormes para dar uno pequeño. Con `k_ref` el valor está a
escala humana y el exponente ronda cero cerca de `T_ref`. Se admiten las
dos —los datos de la literatura vienen en la clásica— y
`ley_directa.forma` declara cuál se usó. `k_ref` **exige** `T_ref`: una
constante referenciada sin su temperatura no dice a qué temperatura vale.

### La base de la actividad

| Base | $a_i$ |
|---|---|
| `actividad` (por omisión) | $x_i\,\gamma_i(T,\mathbf{x})$, con UNIFAC |
| `fraccion_molar` | $x_i$ |

Las dos son **adimensionales**, y eso quita de encima el problema de que
las unidades de $k$ dependan del orden global: **$k$ lleva las unidades de
la tasa y punto**. Y su unidad declara la base (integrada o volumétrica),
igual que en una tasa dada.

La base en **concentración no está**: necesitaría el volumen molar de la
mezcla, que es otra decisión de modelo. Se rechaza con
`LAB_BASE_ACTIVIDAD_NO_SOPORTADA` y el motivo.

### Reversible: dos leyes, o la del equilibrio

Con `ley_directa` y `ley_inversa`, **las brutas se conocen por
construcción**: cada ley da la velocidad de su sentido por definición.

Y hay un tercer camino, `"ley_inversa": {"desde_equilibrio": true}`:

$$ k_{inv} = \frac{k_{dir}}{K_{eq}(T)} $$

Eso **sí** es termodinámicamente consistente — en el equilibrio $r^+ =
r^-$ obliga a que la razón de las constantes sea $K_{eq}$ — y es el único
modo en que una reversible lo es sin dos juegos de datos cinéticos
independientes. Dos avisos que la respuesta declara:

- $K_{eq}$ sale de **van't Hoff**, que supone $\Delta H_{rxn}$ constante
  con la temperatura. Es una aproximación y lejos de $T_{std}$ se nota.
- Con este modo la ley directa pasa a usar los **exponentes de la
  estequiometría**, porque mezclar órdenes libres con una inversa derivada
  del equilibrio rompería esa consistencia: la razón $r^+/r^-$ dejaría de
  ser $K_{eq}$.

### Y una corrección que el contrato pedía

**Imponer $r^+ = r^-$ no demuestra equilibrio termodinámico.** Describe un
estado estacionario con esas dos tasas, nada más. El equilibrio
termodinámico se calcula de $\Delta G$ y $K$, y eso **no** está en esta
entrega (ver [§12](#12-lo-que-queda-de-la-lista)). El preset
`reactor-en-equilibrio` se llama así porque sus tasas son iguales, no
porque el motor haya comprobado un equilibrio.

---

## 7quinquies. Energía acoplada

### El modo adiabático era un hueco

`/laboratorio/*` exigía temperatura impuesta **o** calor impuesto, y con
el supuesto adiabático no hay fuente de calor que imponer: la
especificación **es** Q = 0, y la temperatura es la incógnita. Un volumen
adiabático no se podía resolver, y el diagnóstico decía «no se impuso ni
la temperatura ni el calor» — que era falso.

Es el mismo error que la entrega anterior corrigió en el otro sentido (la
**ausencia** de una fuente no es Q = 0), cometido al revés: la
**presencia** del supuesto sí es una especificación.

Ahora hay tres modos térmicos, y siguen siendo excluyentes:

| Modo | Se impone | Se calcula |
|---|---|---|
| temperatura | T de salida | Q |
| calor | Q | T |
| **adiabático** | Q = 0, por el supuesto | T |

Marcar `adiabatico` **y** además imponer la temperatura es
`LAB_ESPECIFICACION_EXCLUYENTE`.

### Con cinética, T y avance se cierran a la vez

$k(T)$ decide el avance y el avance decide el calor que decide $T$.
Resolver uno y luego el otro daría la respuesta de otro problema, así que
se resuelven juntos: los avances **más** la temperatura, en un sistema.

El resultado del preset `cinetica-adiabatica` se puede comprobar sin el
motor: la reacción libera $\xi(-\Delta H) = 818\,710$ W y el calentamiento
sensible de 320 a 369.46 K vale lo mismo.

### `convergencia.sistemas_implicitos`

Un sistema **por volumen cinético**, con el algoritmo que de verdad
corrió:

```jsonc
"sistemas_implicitos": [{
  "bloque_id": "rx",
  "metodo": "arranque por sustituciones sucesivas (…12 vuelta(s), convergido), y
             despues scipy.optimize.least_squares con trf …, con limites",
  "alcance": "sistema_acoplado",
  "residuo_escalado": 1.097e-15,
  "tolerancia": 1e-10,
  "evaluaciones_de_funcion": 4,
  "convergio": true,
  "restricciones": ["temperatura en [200.0, 399.7] K, el dominio de la tabla…", …]
}]
```

No se agregan en un solo número: dos volúmenes pueden resolverse con
algoritmos distintos y promediar sus residuos no significaría nada. **Con
la tasa dada la lista está vacía**, porque no hay nada implícito que
resolver.

### Los tres algoritmos, y por qué son tres

| Situación | Algoritmo |
|---|---|
| una reacción, T impuesta | `brentq` sobre el avance, **acotado** por el intervalo estequiométrico |
| varias reacciones, T impuesta | `scipy.optimize.root` con `hybr` sobre el vector de avances |
| T incógnita (adiabático o Q impuesto) | arranque por sustituciones sucesivas, y después `least_squares` con `trf` **y límites** |

**Con una reacción el intervalo garantiza el cambio de signo**: en ξ = 0 el
residuo vale −r (negativo si la reacción avanza) y en el límite el
reactivo se agota, la tasa cae a cero y el residuo vale ξ > 0.

**Con varias no hay intervalo que acote un sistema**, así que la
factibilidad (caudales no negativos) se **comprueba** después en vez de
imponerse. Los límites de cada reacción suponiendo las otras a cero no son
conservadores: dos reacciones pueden consumir el mismo reactivo.

**Con T incógnita hacen falta las dos cosas, y esto conviene entenderlo.**
`least_squares` minimiza $\lVert F\rVert^2$, y en un sistema cuadrado eso
**no** es lo mismo que resolver $F = 0$: puede pararse en un mínimo local
del cuadrado que no es raíz. Pasaba, y se veía en el resultado — para una
reacción exotérmica con sólo ley directa daba avance **negativo** y
temperatura **por debajo** de la entrada. El solver no estaba roto:

> Desde (ξ = 0, T = T_ent) el residuo de materia vale −r/F y el de energía
> vale cero, así que **bajar** la temperatura reduce la tasa y con ella el
> residuo de materia. El gradiente apunta a T menor, que es exactamente al
> lado contrario de donde está la solución de una exotérmica.

Así que se arranca donde arrancaría un ingeniero: alternando los dos
problemas que **sí** se resuelven de forma robusta porque cada uno es
escalar y acotado — el avance con T fija, y la T con el avance fijo — y
después el solver acotado lo pule y **mide** el residuo final. Las dos
cosas se declaran: decir sólo «least_squares» ocultaría de dónde salió el
punto de partida, y el punto de partida es la mitad del problema cuando
hay mínimos locales.

**Y los límites de la temperatura salen de la tabla de entalpía**, no de un
número elegido: es el dominio donde el modelo existe. Dejar que el solver
mirara fuera era lo que hacía que no convergiera — con la tasa creciendo
como $e^{-E_a/RT}$, el primer paso se iba a temperaturas sin sentido y no
volvía.

Si la solución se queda **en** un límite, `convergio` es `false` y el
motivo lo dice: una solución en la pared no es un estado estacionario,
significa que el sistema pide salirse del dominio del modelo.

---

## 7sexies. Balanceo exacto

`POST /laboratorio/balancear`

Resuelve $A\cdot\nu = 0$ con `fractions.Fraction` y eliminación de Gauss
sobre los racionales. **No con floats**: la respuesta correcta son enteros
pequeños, y un método numérico los devuelve como `0.9999999999999998`.
Con aritmética exacta no hay nada que reconocer — y `0.333333` puede ser
1/3 o el redondeo de otra cosa.

```json
{"componentes": ["methane", "oxygen", "carbon dioxide", "water"],
 "reactivos": ["methane", "oxygen"]}
```

```jsonc
"reacciones": [{
  "nu": [-1, -2, 1, 2],
  "nu_por_especie": {"methane": -1, "oxygen": -2, …},
  "orientacion": "orientada con la pista del usuario: methane es reactivo…",
  "residuo_elemental": {"C": 0, "H": 0, "O": 0},   // exactamente cero
  "conserva": true,
  "latex": "\\mathrm{methane} + 2\\,\\mathrm{oxygen} \\longrightarrow …"
}]
```

### Tres respuestas, y las tres importan

| `dimension_del_espacio` | Qué significa |
|---|---|
| **0** | No hay reacción. Estas especies no se combinan conservando los elementos, y decirlo **es** la respuesta. `estado: "invalido"`, `LAB_SIN_BALANCE_POSIBLE` |
| **1** | Una reacción, única salvo escala y signo. El caso que se espera |
| **> 1** | Un **subespacio**. Se devuelve la base entera y sale `LAB_BALANCEO_NO_UNICO` como **advertencia** |

El tercero no es un caso raro: `CO/CO₂/H₂/H₂O/CH₄` da dimensión **2** —
desplazamiento de gas de agua y metanación. Elegir una por ti sería
decidir qué química ocurre.

### El signo no lo decide la conservación

$A\nu = 0$ se cumple igual con $\nu$ y con $-\nu$: la conservación de
elementos no sabe qué es reactivo. Da `reactivos` para orientarla; sin la
pista se orienta por convención y `orientacion` **lo dice**.

### Y no necesita grupos UNIFAC

Balancear **es** la conservación de los átomos: hace falta saber de qué
está hecha cada especie y nada más. Por eso la combustión del metano
funciona aunque el metano no tenga grupos UNIFAC. `aptas_para_termodinamica`
avisa de que esa reacción **no** se puede usar en `/equilibrio` ni en
`/lote`: balancear necesita átomos, calcular necesita además termodinámica.

---

## 7septies. Equilibrio químico calculado

`POST /laboratorio/equilibrio`

### La advertencia que da sentido al servicio

**Imponer $r^+ = r^-$ no demuestra equilibrio termodinámico.** Describe un
estado estacionario con esas dos tasas, nada más — dos constantes
cualesquiera lo producen. El equilibrio exige algo distinto y más fuerte:

$$ Q_r = K_r(T) \qquad\text{equivalentemente}\qquad \Delta G_{rxn} = 0 $$

y $K$ sale de $\Delta G$ de **formación**, no de ninguna cinética. La
respuesta lo lleva escrito en `aviso_tasas`.

### K(T) por dos rutas, y la diferencia medida

| Ruta | Cómo |
|---|---|
| `riguroso` | Kirchhoff para ΔH e integración numérica de ΔCp/T para ΔS |
| `vant_hoff` | Supone ΔH **constante** con T |

Se devuelven **las dos**, y `diferencia_relativa_con_riguroso` la mide.
Con los xilenos a 400 K es del **2.5 %**: la aproximación no es inocua, y
ahora no hay que confiar en que lo sea.

Un detalle que ahorra una integral: **ΔH(T) no hace falta integrarla.**

$$ \Delta H_{rxn}(T) = \nu\cdot\left(H_f + h_{sens}(T)\right) $$

Las entalpías sensibles ya la llevan dentro. Es la misma identidad que
explica por qué el balance de energía **no** debe corregir ΔH con
Kirchhoff (§7bis): ahí lo contaría dos veces, y aquí lo da gratis. La
integral que sí hace falta es la de la **entropía**, ΔCp/T, que no está
tabulada.

### El criterio de estabilidad

$\Delta G = 0$ dice que es un punto **estacionario** de la energía de
Gibbs, **no** que sea un mínimo. Lo decide la segunda derivada:

```jsonc
"estabilidad": {
  "hessiano_de_gibbs": [[148.1, …], …],
  "autovalores": [148.1, 269.1],
  "definido_positivo": true,
  "es_minimo": true
}
```

Se calcula por diferencias finitas y se dan los **autovalores**, que son
el criterio — no una etiqueta. Si no es definido positivo, sale una
advertencia: el punto puede ser una silla o el borde del dominio.

### Potenciales químicos, con estado estándar declarado

$$ \mu_i = \mu_i^0(T) + RT\ln a_i $$

El estado estándar de este motor es el **líquido puro a la T de la mezcla
y la p del sistema**, que es el convenio que corresponde a $a_i = x_i\gamma_i$
con $\gamma\to 1$ cuando $x\to 1$ — lo que UNIFAC da. Decirlo importa: un
μ sin estado estándar declarado no se compara con otro.

En el equilibrio se cumple $\sum_i \nu_i\mu_i = 0$, que es la condición
escrita con potenciales. Está comprobado.

### Las restricciones, y la que no hace falta

**Las elementales se cumplen por construcción**: un avance sobre una ν
validada conserva los elementos. Añadirlas como ecuaciones habría contado
dos veces lo mismo, y la respuesta lo declara en
`convergencia.restricciones`.

**La no negatividad sí hace falta imponerla**, y es la parte delicada:
una especie en cero tiene actividad cero y $\ln 0 = -\infty$. El avance se
acota al interior del simplex estequiométrico y las actividades se
recortan a un suelo relativo, diciendo cuándo se recorta.

**El residuo se mide en $\ln Q - \ln K$, no en $Q - K$.** Con ΔG de
−60 kJ/mol, K vale $10^{10}$: un residuo $Q-K$ no se puede escalar de
forma útil.

---

## 7octies. Lote transitorio

`POST /laboratorio/lote`

$$ \frac{dn_i}{dt} = \sum_r \nu_{ir}\,r_r(T, \mathbf{x}(t)) \qquad n_i(0) = n_{i0} $$

Deja de ser un sistema algebraico y pasa a ser un sistema de ODEs. Usa
**las mismas leyes de velocidad** que el CSTR: la ley es la misma física
en los dos regímenes, y tener dos implementaciones sería tener dos físicas
que se pueden separar.

```json
{"componentes": ["o-xylene", "m-xylene", "p-xylene"],
 "reacciones": [{"id": "om", "nu": [-1.0, 1.0, 0.0],
                 "ley_directa": {"k_ref": {"valor": 0.5, "unidad": "mol/s"},
                                 "T_ref": {"valor": 400.0, "unidad": "K"},
                                 "Ea": 0.0, "ordenes": {"o-xylene": 1.0}}}],
 "estado_inicial": [{"componente": "o-xylene", "valor": 100.0, "unidad": "mol"}],
 "T": {"valor": 400.0, "unidad": "K"},
 "tiempo": {"final": 400.0, "unidad": "s", "muestras": 9}}
```

### El integrador se declara

| Método | Para qué |
|---|---|
| `LSODA` (por omisión) | Detecta la rigidez **solo**, y una red con constantes muy distintas es rígida sin avisar |
| `Radau`, `BDF` | Para quien ya sepa que la suya lo es |
| `RK45` | Rápido si **no** es rígido |

`rtol` y `atol` se declaran y **viajan en la respuesta**: una trayectoria
sin tolerancia declarada no se puede reproducir ni comparar con otra. Por
omisión `rtol = 1e-10` y `atol = 1e-12` por mol total.

`muestras` no cambia la precisión de la integración, solo cuánto se
devuelve de ella.

### El agotamiento se detecta con un EVENTO

```jsonc
"agotamientos": [{"especie": 0, "componente": "o-xylene",
                  "instante": 55.19339009340264, "unidad": "s",
                  "nota": "localizado por un evento del integrador, no mirando
                           las muestras: un cruce entre dos muestras se habría
                           perdido"}]
```

Un chequeo a posteriori sobre los puntos muestreados se perdería el cruce
si cae entre dos muestras. El evento lo localiza con la misma precisión
que la trayectoria.

### La no negatividad se comprueba sobre lo DEVUELTO

Una ley de acción de masas con órdenes positivos la respeta sola —la tasa
cae a cero cuando el reactivo se agota— pero el integrador puede pasarse
por debajo en un paso. Se recorta al **evaluar** la ley, porque UNIFAC con
fracciones negativas no significa nada, y se **comprueba** sobre la
trayectoria devuelta. Recortar y callarse convertiría un dato imposible en
una curva plausible.

### Y la comprobación que cruza los dos servicios

`equilibrio_alcanzado` trae `dG_rxn` en el último punto. Con una cinética
termodinámicamente consistente (`ley_inversa` con `desde_equilibrio`) y
tiempo suficiente, **tiende a cero y la composición final coincide con
`/laboratorio/equilibrio`** — a $5.6\times10^{-17}$ con los xilenos. Son
dos caminos independientes: uno integra una ODE y el otro resuelve
$\ln Q = \ln K$.

Y la mitad negativa, que es la advertencia del contrato **medida**: una
cinética que **no** es consistente para en un estacionario que no es el
equilibrio. Con $k_1/k_2 = 2.5$ frente a $K = 2.38$, la diferencia se ve.

### Lo que NO hace

**Isotermo.** Un lote adiabático añade la ecuación de la energía al
sistema de ODEs, y eso es otra entrega: exige su propia verificación, y
las soluciones analíticas con las que se comprueba ésta son todas
isotermas. Está declarado en
`capacidades.servicios.lote.no_soportado`.

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

Los trece grupos de la suite (**389 comprobaciones**) cubren: uno y dos
volúmenes con continuidad y conservación; los modos excluyentes; los
montajes mal formados (ids, referencias, puertos, aislados, ciclos,
null/NaN, fracciones, unidades, modelo y componentes); el dominio
termodinámico sin presentar resultados a medias; que los ids de los
diagnósticos existan y que las ecuaciones marcadas como ejecutadas
correspondan al cálculo real; la no regresión de `/diagrama/resolver` y
del CSTR; el reenvío de los presets al endpoint; y **la reacción**.

### Y lo que se comprueba de la reacción

También contra lo que la estequiometría **obliga**, no contra números
escritos a mano:

- **A → B** (`n-butano → isobutano`, ν = [−1, +1]): el consumo de A y la
  generación de B son exactamente el avance, 20 mol/s; con `Σν = 0` el
  caudal molar **no** cambia; elementos y masa con residuo `< 1e-12`.
- **A → 2B** (`diisobutileno → 2 isobuteno`, ν = [+2, −1]): el caudal pasa
  de 100 a **110** mol/s con un avance de 10, y la masa no se mueve.
- **Reversible con la inversa dominante** (`r⁺ = 2`, `r⁻ = 8`): avance
  neto −6, y las brutas salen 16/4 para el isobuteno y 2/8 para el dímero
  — la dirección inversa intercambia producción y consumo.
- **Equilibrio** (`r⁺ = r⁻ = 5`): fuente neta **cero** con brutas 10 y 5,
  **positivas**; la composición de salida igual a la de entrada; y el
  calor de reacción cero, porque lo mueve el avance neto.
- **Solo la tasa neta**: brutas en `null` con su motivo, y una reacción
  sin brutas deja al **volumen** sin brutas, nombrando la culpable.
- **Dos reactores compartiendo la corriente**: 100 → 90 → 75 mol/s, seis
  variables compartidas, ningún estado duplicado, y el cierre global con
  el calor de reacción de todo el montaje con residuo **0.0**.
- **Las bases**: 4 mol/(m³·s) × 5 m³ da el mismo resultado que 20 mol/s.
- **Catorce rechazos** con su código: elementos que no cuadran, tasa
  negativa, reversible a medias, dos formas de tasa a la vez, base
  volumétrica sin volumen, un avance que no cabe en la alimentación,
  parámetros cinéticos sueltos, ν sin reactivo y producto, ν de longitud
  equivocada, reacción en un no-reactor, reacción con `sinReaccion`,
  reactor sin reacción declarada, unidad de tasa no admitida y bases
  mezcladas.

### Y lo que se comprueba del lote y del equilibrio

Aquí las **soluciones analíticas** hacen todo el trabajo. Las redes de
primer orden las tienen, y las tres topologías que el contrato nombra son
exactamente ésas:

| Red | Analítico | Coincide a |
|---|---|---|
| A → B | $n_A = n_{A0}e^{-kt/N}$ | $10^{-7}$ mol sobre 100 |
| A → B → C | solución clásica consecutiva | $10^{-7}$ mol |
| A → B, A → C | $n_A = n_{A0}e^{-(k_1+k_2)t/N}$ | $10^{-7}$ mol |
| A ⇌ B | $n_A = n_A^\infty + (n_{A0}-n_A^\infty)e^{-(k_1+k_2)t/N}$ | $10^{-6}$ mol |

Y además: el **máximo del intermedio** de la consecutiva cae donde el
álgebra lo pone, y la **selectividad** de la paralela es exactamente
$k_1/k_2$. Con los cuatro métodos de integración sale lo mismo.

Del **equilibrio**, la comprobación es que la razón de actividades en la
solución **es K**, pedida al proveedor por separado: coincide a
$10^{-12}$ relativo, con $\Delta G_{rxn} = 0$ y
$\sum_i\nu_i\mu_i = 0$. Y Le Chatelier sale solo: siendo exotérmica,
K baja de 2.593 a 2.382 al subir de 330 a 400 K.

ΔH(T) se comprueba contra $\nu\cdot(H_f + h_{sens})$ pedido por separado, y
a la T de referencia es exactamente $\nu\cdot H_f$.

**Y la comprobación que cruza los dos servicios**, que es la más fuerte de
toda la entrega: un lote con cinética termodinámicamente consistente
converge a la **misma** composición que `/laboratorio/equilibrio`, a
$5.6\times10^{-17}$. Integrar una ODE y resolver $\ln Q = \ln K$ son dos
caminos sin nada en común, y coinciden al último bit.

Del **balanceo**: la combustión del metano sale `[-1, -2, 1, 2]`, el
amoniaco `[-1, -3, 2]`, y el subespacio CO/CO₂/H₂/H₂O/CH₄ sale con
dimensión 2 y residuo elemental **exactamente cero**, no $10^{-16}$.

### Y lo que se comprueba de la cinética

Los casos de **primer y segundo orden en base de fracción molar tienen
solución analítica**, así que tampoco hay números escritos a mano — se
comparan contra el álgebra:

| Caso | Analítico | Numérico |
|---|---|---|
| 1.º orden, $r = kx_A$ | $\xi = \dfrac{kF_{A0}}{F_0+k} = 33.3\overline{3}$ | coincide a $10^{-12}$ |
| 2.º orden, $r = kx_A^2$ | raíz de $F_0^2\xi = k(F_{A0}-\xi)^2$ | coincide a $10^{-9}$ |
| dos reacciones acopladas | sistema lineal resuelto a mano | coincide a $10^{-9}$ |

**El adiabático se verifica por dos caminos independientes**: imponer la
temperatura resultante en modo isotermo da el **mismo** avance
(86.0894127745747 frente a 86.08941277457478), y el calor liberado por la
reacción iguala al calentamiento sensible (818 710.3 W por los dos lados).

Y se comprueba que lo declarado es lo que corre: que una reacción isoterma
use `brentq` **acotado**, que varias usen `hybr`, que el acoplado declare
**el arranque y el solver** y no sólo el solver, y que los límites de
temperatura vengan de la tabla de entalpía.

**Once rechazos más** de la cinética, más **nueve** del lote y del
equilibrio. Y del catálogo: que `C2H6O` salga
marcado como no fiable con el etanol entre los candidatos, que nombre, CAS
y SMILES den la misma sustancia, y que el diciclopentadieno salga apto
para ELV y **no** para reacción — el mismo fallo que el motor da luego con
`LAB_ENTALPIA_FORMACION_NO_DISPONIBLE`.

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
- **Cinética y equilibrio químico**, por lo dicho en
  [§7bis](#7bis-reacción).
- **Entropía, exergía, conducción, difusión y momento**: las entregas
  posteriores que el contrato enumera. Ninguna está empezada, y
  `capacidades.no_soportado` las lista para que la interfaz no las ofrezca.

---

## 12. Lo que queda de la lista

De `PENDIENTES_BACKEND_CLAUDE.md`, esta entrega cubre los puntos **1**
(catálogo de sustancias), **2** (cinética general y redes, con el solver
implícito declarado) y **5** (reactores con energía acoplada: isotérmico,
adiabático y con Q impuesto).

Con esta cuarta entrega quedan cubiertos los puntos **3** (lote
transitorio) y **4** (equilibrio químico calculado), y la parte de la
«migración de exploraciones locales» que corresponde al **balanceo
racional** y a **Hess/Kirchhoff** — los dos están ahora en el backend con
contrato, casos analíticos y unidades, y el frontend puede dejar de tener
su propia implementación.

**Lo que NO está, y lo digo para que no se dé por hecho:**

- **Punto 6: entropía, Gibbs/potencial químico, segunda ley y exergía.**
  Los potenciales químicos **sí** están (en `/equilibrio`), con su estado
  estándar declarado. Lo que falta es el balance de entropía con
  temperatura de frontera, y la exergía con ambiente explícito.
- **Punto 7: conducción 1D** en capas y contactos; luego capacidad
  concentrada transitoria.
- **Punto 8: difusión y películas.**
- **Punto 9: momento e hidráulica**, con presión no uniforme.
- **Punto 10: más de dos volúmenes**, puertos tipados, y el **decantador
  expuesto** — que sigue existiendo en el motor sin ruta HTTP.
- **Los transversales**: expresiones tipadas con comprobación dimensional
  automática, y sensibilidad e incertidumbre.
- **El lote adiabático**, que añade la ecuación de la energía al sistema
  de ODEs. Está declarado en `capacidades`.
- **El ensamblador común a laboratorio y operaciones compuestas** que pide
  la sección de migración: hoy `core/laboratorio.py` ya está separado de
  sus endpoints (`backend/nucleo_laboratorio.py`) y de la UI, y
  `core/cinetica.py`, `core/equilibrio.py`, `core/lote.py` y
  `core/balanceo.py` son módulos de física sin nada de HTTP. Lo que falta
  es que `/diagrama/resolver` consuma ese mismo ensamblador, y eso es una
  refactorización de lo existente, no una capacidad nueva.

Del requisito transversal, esta entrega cumple la parte de «todas las
capacidades nuevas deben anunciar límites y ejemplos reproducibles»:
`capacidades` declara lo no soportado servicio por servicio, y los
treinta presets y pares petición/respuesta de `docs/ejemplos/` se generan
**ejecutando** el endpoint.

---

## 11. Qué cambió respecto a las entregas anteriores

Nada del contrato térmico dejó de funcionar, y está comprobado. Pero hay
cuatro cambios **visibles** que conviene mirar antes de conectar:

**1. Los ids de las ecuaciones de materia.** Donde antes había
`{vol}:materia_total` (tipo `balance`) y `{vol}:materia_especie`, ahora hay
**n** relaciones `{vol}:materia_especie_{i}`, una por especie, y
`{vol}:materia_total` pasa a tipo **`verificacion`**.

El motivo: el balance total es la **suma** de los n por especie, así que
contarlo como ecuación independiente regalaría una ecuación — el mismo
error que contar la verificación global de energía. Como suma, sigue
sirviendo de comprobación, y su residuo se mide.

**2. Los recuentos de `analisis`.** Las n fracciones son ahora variables
explícitas (`x0`, `x1`, …) y el cierre es la ecuación que determina la que
falta. El caso de aceptación térmico pasa de «17 variables, 9 incógnitas,
9 ecuaciones» a «20, 12, 12». **`grados_libertad` sigue dando 0**, porque
han subido a la vez una variable y una ecuación por corriente.

**3. El cierre de composición ahora cuenta como ecuación… cuando
determina algo.** Si se dan las n fracciones, no cuenta: comprueba, y su
residuo se mide. El criterio no ha cambiado —**una relación cuenta si y
solo si determina algo**— lo que cambió es que antes la segunda fracción
de un binario no era una variable sino una expresión, así que el cierre no
determinaba nada.

**4. `estados_por_bloque` tiene campos nuevos** (`composicion`,
`por_especie`, `nota_F_i`) y `x` es `null` con tres o más componentes.
Los campos viejos siguen donde estaban.

**5. `base_actividad` es `str` y no un `Literal` en el esquema.** A
propósito: una base desconocida tiene que salir como **diagnóstico** del
núcleo —con su código, su id de bloque y la explicación de por qué la
concentración no está— y no como un 422 de Pydantic, que no lleva nada de
eso. Es el mismo criterio que con el resto de lo semántico.

**6. `convergencia.sistemas_implicitos` es nuevo**, y está vacío cuando no
hay cinética.

**7. El modo adiabático existe.** Antes un volumen adiabático no se podía
resolver; ahora es el tercer modo térmico, y marcarlo **más** imponer la
temperatura es un error.

**8. `desde_equilibrio` CAMBIA DE RESULTADO.** Usaba van't Hoff y ahora
usa la ruta rigurosa (Kirchhoff e integral de ΔCp/T). La respuesta declara
la ruta en `ley_inversa.ruta_de_K`.

No es un ajuste cosmético y conviene saber por qué se hizo: se vio al
cruzar el lote con el servicio de equilibrio. Con los xilenos a 400 K,
van't Hoff da K = 2.441 y la ruta rigurosa K = 2.382, y el lote convergía
a una composición **0.5 % distinta** de la que `/equilibrio` calculaba.
Dos partes del motor contestando cosas distintas a la misma pregunta es
peor que una aproximación declarada. Ahora coinciden a $10^{-17}$.

Si tenías un resultado guardado con `desde_equilibrio`, cambiará.

Y dos defectos que la reacción destapó y que estaban desde la primera
entrega:

- **Una fracción molar de cero se rechazaba** como no física. Invisible
  mientras todo fuera binario.
- **El cierre de composición se evaluaba dos veces** en la corriente de
  entrada, y la segunda vez trataba un valor *calculado* como si fuera
  *dado*, midiendo el residuo de una tautología. La bandera `impuesta`
  existe justo para distinguirlos y ahí no se estaba usando.

Detalle técnico completo en [`docs/15-laboratorio.md`](15-laboratorio.md).

---

## 13. Estudios sobre un montaje: estacionario y temporal

Respuesta a `frontend/INICIO_CLAUDE_MOTOR_ACOPLADO.md` (primera tarea
acotada) y a `frontend/CONTRATO_ESTUDIOS_DINAMICOS_CLAUDE.md`. Solo
backend.

**Lo que hay:** un modelo **material** de uno o dos volúmenes
perfectamente mezclados en serie, unidos por una corriente intermedia sin
almacenamiento, **sin reacción**, con cierres de almacenamiento
explícitos. El **mismo ensamblaje** se resuelve como estudio estacionario
(Newton sobre el residuo) o temporal (`solve_ivp` sobre el estado
conjunto). Validado contra soluciones analíticas independientes con
constantes de tiempo iguales y distintas.

**Lo que NO hay** (y `capacidades` lo dice): energía y almacenamiento
térmico (**ya están: ver [§14](#14-estudios-con-energía-materia--energía-sin-reacción-entrega-a)**), reacción por volumen, momento, transferencia estacionario →
condición inicial, perfiles distintos del escalón, más de dos volúmenes,
densidad dependiente de la composición. El lote reactivo sigue siendo su
propio régimen en `/laboratorio/lote`.

### 13.1 Rutas

| Método | Ruta | Qué hace |
|---|---|---|
| `POST` | `/laboratorio/estudios/validar` | Ensambla, clasifica (ODE/DAE), comprueba cierres, iniciales y entradas. **No resuelve** |
| `POST` | `/laboratorio/estudios/resolver` | Resuelve el estudio pedido |
| `GET` | `/laboratorio/estudios/capacidades` | Qué admite y qué no |
| `GET` | `/laboratorio/estudios/ejemplos` | Peticiones reales de `/resolver` con su `estado_esperado` |
| `GET` | `/laboratorio/estudios/ejemplos/{id}` | Una concreta (404 con la lista si no existe) |

`schema_version = 1` (contrato de estudios, independiente del de
`/laboratorio/*`) y `estudio.version = 1`. Igual que en el laboratorio:
**un estudio imposible devuelve `200`** con `estado` y diagnósticos;
`422` solo para lo que no tiene forma de petición. **Ramifica por
`estado`.**

Por qué rutas propias y no un modo de `/laboratorio/resolver`: la
respuesta es otra (series, eventos, integrador, clasificación ODE/DAE), y
el contrato estacionario térmico sigue intacto.

### 13.2 Petición

La **definición física** (piezas, conexiones, especificaciones de la
alimentación, `almacenamiento`) va separada del **estudio** (la pregunta).
`modelo_id` se calcula solo con la definición física, así que **es el mismo
en estacionario y en temporal**; `estudio_id` identifica la pregunta.

```json
{
  "version": 1,
  "componentes": ["benzene", "toluene"],
  "bloques": [
    {"id": "in",    "tipo": "entrada",    "nombre": "Alimentacion"},
    {"id": "cv1",   "tipo": "recipiente", "nombre": "Primer volumen"},
    {"id": "medio", "tipo": "corriente",  "nombre": "Corriente compartida"},
    {"id": "cv2",   "tipo": "recipiente", "nombre": "Segundo volumen"},
    {"id": "out",   "tipo": "salida",     "nombre": "Salida final"}
  ],
  "conexiones": [
    {"id": "c1", "desde": "in",    "hacia": "cv1"},
    {"id": "c2", "desde": "cv1",   "hacia": "medio"},
    {"id": "c3", "desde": "medio", "hacia": "cv2"},
    {"id": "c4", "desde": "cv2",   "hacia": "out"}
  ],
  "supuestos": {"sinReaccion": true},
  "especificaciones": [
    {"bloque_id": "in", "variable": "F",  "valor": 10.0, "unidad": "mol/s"},
    {"bloque_id": "in", "variable": "x0", "valor": 0.5,  "unidad": "mol/mol"}
  ],
  "almacenamiento": [
    {"bloque_id": "cv1", "cierre": "inventario_constante",
     "V": {"valor": 0.05, "unidad": "m3"},
     "densidad_molar": {"valor": 10000.0, "unidad": "mol/m3"}},
    {"bloque_id": "cv2", "cierre": "inventario_constante",
     "V": {"valor": 0.2, "unidad": "m3"},
     "densidad_molar": {"valor": 10000.0, "unidad": "mol/m3"}}
  ],
  "estudio": {
    "version": 1,
    "tipo": "temporal",
    "condiciones_iniciales": [
      {"bloque_id": "cv1", "componente": "benzene", "magnitud": "n", "valor": 0.0,    "unidad": "mol"},
      {"bloque_id": "cv1", "componente": "toluene", "magnitud": "n", "valor": 500.0,  "unidad": "mol"},
      {"bloque_id": "cv2", "componente": "benzene", "magnitud": "n", "valor": 0.0,    "unidad": "mol"},
      {"bloque_id": "cv2", "componente": "toluene", "magnitud": "n", "valor": 2000.0, "unidad": "mol"}
    ],
    "tiempo": {"final": 600.0, "unidad": "s", "muestras": 61},
    "entradas_temporales": [
      {"bloque_id": "in", "variable": "x0", "forma": "escalon",
       "instante": {"valor": 100.0, "unidad": "s"}, "valor": 0.8, "unidad": "mol/mol"}
    ],
    "integrador": {"metodo": "LSODA", "rtol": 1e-10, "atol_relativo": 1e-12}
  }
}
```

Campo a campo:

| Campo | Obligatorio | Notas |
|---|---|---|
| `componentes` | sí | 2–8, en orden. Se identifican por **CAS** (`identidad_componentes` en la respuesta); una fórmula da advertencia |
| `bloques`, `conexiones` | sí | Una alimentación, uno o dos volúmenes (`recipiente`, o `reactor` con `sinReaccion`), corriente intermedia, salida. `calor`/`trabajo` se admiten y se avisa de que no intervienen |
| `supuestos` | no | `sinReaccion: false` se rechaza. **`estacionario` no manda aquí**: manda `estudio.tipo`; si se contradicen sale advertencia `LAB_DIN_ESTUDIO_INCOHERENTE`, y la bandera no entra en `modelo_id` |
| `especificaciones` | sí | `F` y fracciones de la **alimentación**: los valores **base**, vigentes desde t = 0. Cierre de composición como en §2 (n−1 fracciones, o n que sumen 1). T, p, Q y la T de un volumen se avisan como no usadas (`LAB_DIN_DATO_NO_USADO`) |
| `almacenamiento[]` | sí, uno por volumen | Ver 13.3. **Es definición física**, no estudio |
| `estudio.tipo` | sí | `"estacionario"` o `"temporal"` |
| `estudio.condiciones_iniciales[]` | sí en temporal | `n` **por especie y volumen** con unidad (`mol`, `kmol`, `mmol`). Cero es un dato; la ausencia no es cero. En estacionario se **conservan y no se usan** (advertencia) |
| `estudio.tiempo` | sí en temporal | `final` > 0, `unidad` (`s`, `min`, `h`), `muestras` 2–2000 (por omisión 101). Las series se devuelven **siempre en s** |
| `estudio.entradas_temporales[]` | no | Solo `forma: "escalon"`, solo `F` y `x_i` de la alimentación, instante en (0, final), máximo 32. Un escalón sobre `x_i` solo si esa fracción está en las especificaciones base (si la determina el cierre, no se sabría qué ajustar) |
| `estudio.integrador` | no | `metodo` ∈ LSODA, Radau, BDF, RK45; `rtol` (por omisión 1e-10), `atol_relativo` (1e-12, multiplica la escala de inventario) |

Se ignoran, como en §2: `relaciones` (LaTeX), `estado`, `solver`,
`modelo_termodinamico`, `referencia_entalpia`, `presion_sistema`,
`bloques[].datos` (este último con advertencia).

### 13.3 Cierres de almacenamiento

Un estacionario no necesita saber cuánto cabe en un tanque; un temporal
sí, y tampoco el estacionario de este modelo puede dar los inventarios sin
saberlo. Cada volumen declara **cómo se determina su salida**. Sin cierre:
`LAB_DIN_CIERRE_FALTANTE`, nada se supone.

| `cierre` | Parámetros | Ley | Clase |
|---|---|---|---|
| `inventario_constante` | `V` (m3, L, …), `densidad_molar` (mol/m3, kmol/m3, mol/L) | `Σ n_i = ρV` constante; `F_sal = F_ent` | **DAE de índice 2**, reducida a ODE |
| `salida_lineal` | `k_salida` (1/s, 1/min, 1/h) | `F_sal,i = k n_i` | ODE |
| `salida_impuesta` | `F_salida` (unidades de F) | `F_sal = F_s` | ODE; puede vaciarse (evento) |

En los tres, **mezcla perfecta**: la salida tiene la composición del
inventario. Es una ecuación (`{vol}:mezcla_perfecta_{i}`), no una
identidad.

Parámetros de **otro** cierre en el mismo volumen:
`LAB_ESPECIFICACION_EXCLUYENTE`. `densidad_molar: "proveedor"` (o
cualquier cadena): `LAB_DIN_DAE_NO_SOPORTADA` — la restricción pasaría a
`Σ n_i v̄_i(x,T) = V`, otra DAE que necesita volúmenes molares parciales y
T.

### 13.4 Respuesta

```jsonc
{
  "schema_version": 1,
  "estado": "resuelto",              // valido | invalido | no_soportado | no_convergente | resuelto | parcial
  "terminacion": "completado",       // completado | detenido_por_evento | fallido | null (estacionario)
  "modelo_id": "…",                  // definición física: igual en los dos estudios
  "estudio_id": "…",                 // la pregunta
  "calculo": {…},                    // como en §4
  "estudio": {"version": 1, "tipo": "temporal"},
  "componentes": […], "identidad_componentes": [{"indice", "componente", "cas", "nombre", "formula"}],
  "modelo": {"variables": […], "ecuaciones": […], "clasificacion": {…}},
  "condiciones_iniciales_usadas": {…}, "entradas_usadas": {…},
  "integracion": {…}, "resultados": {…}, "eventos": […],
  "conservacion": {…}, "estacionario": {…}, "contraste_estacionario": {…},
  "constantes_de_tiempo": […],
  "diagnosticos": […], "resumen_diagnosticos": {…}, "capacidades": {…}
}
```

| `estado` | Significa | ¿Series? |
|---|---|---|
| `valido` | `/validar`: se sostiene, no se calculó | No |
| `invalido` / `no_soportado` | Datos mal / límite del motor | No |
| `no_convergente` | Integración fallida, salida de dominio o conservación rota | No |
| `resuelto` | Completado | Sí |
| **`parcial`** | Un evento detuvo la integración antes del horizonte | **Sí, válidas hasta el evento. No es éxito total** |

`parcial` es un valor **nuevo** que `/laboratorio/*` no tenía.

**`modelo.variables[]`**: `id`, `clase` (`diferencial` | `algebraica` |
`entrada` | `parametro`), `magnitud`, `unidad`, `bloque_ids`,
`conexion_ids`, `simbolo`, `compartida`, `valor` (parámetros y entradas
base), `determinada_por` (id de la ecuación que la fija), `componente`
cuando aplica. Ids: `{vol}.n{i}` (mol), `{vol}.N`, `{corriente}.F`,
`{corriente}.x{i}`, `{vol}.V`, `{vol}.densidad_molar`, `{vol}.k_salida`,
`{vol}.F_salida`. Las variables de `medio` salen **una vez**, con
`compartida: true` y los dos volúmenes en `bloque_ids`.

**`modelo.ecuaciones[]`**: como §4 (`id`, `tipo`, `titulo`,
`latex_general`, `latex_activo`, `terminos_descartados`, `origen_*`,
`variables`, `cuenta_como_ecuacion`, `ejecutada`, `residuo`, `nota`) más
`clase` (`diferencial` | `algebraica`). El LaTeX **lo genera el motor**.

| id | `tipo` | ¿Cuenta? |
|---|---|---|
| `{vol}:materia_especie_{i}` | `balance` (diferencial) | sí |
| `{vol}:mezcla_perfecta_{i}` | `constitutiva` | sí |
| `{vol}:restriccion_inventario` | `restriccion` | sí (inventario constante) |
| `{vol}:salida_por_restriccion` | `derivada_de_restriccion` | **no**: es la restricción derivada |
| `{vol}:inventario_total` | `definicion` | sí (inventario variable) |
| `{vol}:cierre_salida` | `constitutiva` (lineal) / `condicion` (impuesta) | sí / no |
| `global:materia_especie_{i}` | `verificacion` | no; se **mide** |

**`modelo.clasificacion`**: `tipo_sistema` (`"ODE"` o
`"DAE_indice_2_reducida_a_ODE"`), `acoplamiento` (siempre monolítico),
`variables_diferenciales`, `variables_algebraicas`, `entradas`,
`parametros`, `ecuaciones_diferenciales`, `ecuaciones_algebraicas`,
`incognitas`, `ecuaciones_independientes`, `grados_libertad`,
`rango_origen` (**estructural**: no se calcula un rango numérico, y contar
ecuaciones no lo certifica), `restricciones[]` (`ecuacion`, `bloque_id`,
`indice: 2`, `variable_que_determina`, `tratamiento`), `reduccion` (texto
con el razonamiento), `no_contadas`, `nota_corriente_intermedia`. El caso
de aceptación: 10 incógnitas, 10 ecuaciones, GL = 0.

**`integracion`** (temporal): `metodo`, `descripcion_metodo`,
**`elegido_por`** (`"omision"` | `"peticion"`), `motivo_eleccion`, `rtol`,
`atol` (`inventarios_mol`, `integrales_de_flujo_mol`, `atol_relativo`,
`escala_inventario_mol`), `dominio_s`, `unidad_tiempo_pedida`, `tramos[]`
(uno por escalón: `desde_s`, `hasta_s`, entradas del tramo,
`evaluaciones_de_funcion`, `evaluaciones_de_jacobiano`,
`estado_integrador`, `mensaje`), **`rigidez`** (autovalores del jacobiano
en t = 0 y `cociente_de_rigidez`), `acoplamiento`, `eventos_vigilados`.

**`resultados`**: `t` (s), `unidad_tiempo: "s"`, `n_muestras`,
`series[]` con `id` de variable, `bloque_id`, `componente`, `magnitud`,
`unidad`, `valores`. Hay serie para cada `{vol}.n{i}`, `{vol}.N`,
`{corriente}.F` y `{corriente}.x{i}`. **Una composición sin caudal es
`null`, no cero** (un volumen vacío en t = 0). Los instantes de los
escalones están siempre entre las muestras, y las entradas son
**continuas por la derecha**: en el instante del escalón ya rige el valor
nuevo.

**`eventos[]`**: `tipo` (`vaciado` | `dominio`), `bloque_id`, `instante`,
`unidad`, `descripcion`. Localizados por evento del integrador, no
mirando las muestras.

**`conservacion`**: `por_volumen[]` (residuo integrado
`n(t) − n(0) − (∫ent − ∫sal)`, y por qué corrientes entra y sale),
`global` (usa **solo** alimentación y salida final: el transporte interno
se cancela), `residuo_instantaneo_max`, `invariantes[]` (la restricción
`Σn = ρV` a lo largo de la trayectoria), `tolerancia`, `cumple`. Ojo con
lo que mide: los métodos usados conservan invariantes lineales, así que
estos residuos comprueban el **ensamblaje** (cada corriente entra en un
balance y sale de otro exactamente una vez), **no** la precisión; la
precisión se comprueba contra las analíticas (13.6).

**`estacionario`** (estudio estacionario): `existe`, `metodo`,
`punto_de_partida` (pesos 1..n, **no** la solución), `iteraciones`
(reales, del Newton propio), `residuo_escalado`, `historial_residuo`,
`tolerancia`, `convergio`, `estados` (por volumen `n`, `N`, `x`; por
corriente `F`, `F_i`, `x`), `conservacion`, `restricciones`,
**`estabilidad`**, `aviso`.

**`estabilidad`**: autovalores del jacobiano **restringido a la variedad
de las restricciones** (el modo normal a `Σn = ρV` es un artefacto de la
reducción, no física), `localmente_estable`,
`constante_de_tiempo_mas_lenta_s` y `alcance`: es estabilidad **lineal
local**. Un residuo cero no implica estabilidad, unicidad ni
accesibilidad.

**`contraste_estacionario`** (temporal → estacionario): un estacionario
**independiente** con las entradas del último tramo, comparado con el
final de la trayectoria: `distancia_escalada`, `derivada_escalada`,
`variacion_ventana_final` (último 10 % del horizonte), `tolerancia`
(1e-6), `alcanzado`, `estabilidad`, `conclusion`. Un gráfico plano no es
convergencia: si no se alcanza sale el informativo
`LAB_DIN_ESTACIONARIO_NO_ALCANZADO`. Con un evento o sin estacionario
único, `evaluado: false` y el motivo.

**`constantes_de_tiempo[]`**: por volumen, `definicion` (`ρV/F_ent`,
`1/k`), `valor_s`, `constante`, `nota`. Con inventario constante aguas
abajo de uno variable, τ cambia en el tiempo y `valor_s` es `null`.

### 13.5 ODE, DAE y lo que se declara

El cierre de inventario constante es la parte delicada. La restricción
`Σ n_i = ρV` **no contiene** la variable que determina (`F_sal`):
derivarla una vez da `F_ent − F_sal = 0`, que sí la determina. Eso es una
DAE semiexplícita de **índice 2** (el producto de las derivadas de la
restricción y del balance respecto de `F_sal` vale `−Σx_i = −1`, no
singular). Se reduce así:

1. `F_sal = F_ent` se elimina de forma explícita → ODE en los `n_i`.
2. En la ODE reducida la composición de salida es `x_i = n_i / (ρV)`, con
   lo que `d(Σn)/dt = F_ent (1 − Σn/ρV)`: la variedad `Σn = ρV` es
   **invariante y atractora** con tasa `F_ent/ρV`.
3. La restricción original se **mide** en toda la trayectoria
   (`conservacion.invariantes`; < 1e-15 en las pruebas).
4. Por eso el estado inicial **tiene que cumplirla**: la reducción pierde
   ese nivel, y un inicial que suma 400 mol con `ρV = 500` es
   `LAB_DIN_INICIAL_INCONSISTENTE`, no una aproximación.

**El integrador por omisión se dice que es por omisión.** LSODA conmuta
solo entre rígido y no rígido, pero elegirlo sin que se pida no es un
análisis: `elegido_por: "omision"` y el `cociente_de_rigidez` medido en
t = 0 para juzgarlo.

**Estado conjunto, sin partición.** Un único `solve_ivp` sobre el vector
con los inventarios de los dos volúmenes; las corrientes se evalúan una
vez por llamada y en orden, de modo que la salida del volumen 1 **es** la
entrada del 2. No se integran tanques por separado ni se pasan estados
finales. Las pruebas lo comprueban por contraste: el tanque 2 integrado
con el estado final del 1 como entrada constante da otra curva.

**Escalones**: el integrador se **reinicia** en cada discontinuidad (un
tramo por escalón). Integrar a través de un salto con paso adaptativo
"funciona casi siempre" y degrada el orden sin avisar.

**Eventos**: vaciado (`Σn = 0` con salida impuesta, terminal → `parcial`)
y salida de dominio (algún `n_i < −1e-9·escala`, terminal →
`no_convergente` con `LAB_DIN_SALIDA_DE_DOMINIO`). Con estos cierres y sin
reacción una especie no se agota en tiempo finito salvo vaciándose el
volumen entero, así que no hay evento de agotamiento por especie: llegará
con las fuentes reactivas.

**Estacionario**: los caudales del estacionario se deciden **por
estructura** antes del Newton. Con salida impuesta, `dN/dt = F_ent − F_s`
no depende del estado: si no es cero, `LAB_DIN_SIN_ESTACIONARIO`; si lo
es, cualquier N vale y es `LAB_DIN_ESTACIONARIO_INDETERMINADO`. El
**mismo** montaje se integra sin problema en el temporal: un modelo
dinámico válido no siempre tiene estacionario, y se dice. Si el jacobiano
saliera singular en otro caso, también es `INDETERMINADO`.

### 13.6 Lo que está verificado

`tests/validar_estudios.py`, **137 comprobaciones**. Los valores
esperados salen de **soluciones analíticas escritas en la suite**, no del
motor:

| Caso | Referencia | Error medido |
|---|---|---|
| Inventario constante, τ = 50 s y 200 s | `u₂ = C e^{−t/τ₁} + (b−C) e^{−t/τ₂}`, `C = aτ₁/(τ₁−τ₂)` | ~1e-11 en x |
| Inventario constante, τ₁ = τ₂ = 100 s | `u₂ = (b + a t/τ) e^{−t/τ}` (caso degenerado) | ~1e-11 |
| Salida lineal, k distintas e iguales, un volumen vacío en t = 0 | las mismas formas sobre `n − n*`, con ganancia `k₁` | ~3e-11 relativo |
| Escalón de composición en t = 100 s | analítica por tramos | 2e-11 |
| Escalón de F y x a la vez (τ pasa a 25 y 100 s) | analítica por tramos | 2e-11 |
| Vaciado con salida impuesta | `t* = N₀/(F_s − F) = 50 s`; `x = x_f − (x_f−x₀)(N/N₀)^{−F/(F−F_s)}` | instante a 2e-14 s; x a 4e-11 |
| Estacionario (inventario constante y salida lineal) | `n = x_f ρV`; `N = F/k` | 1e-9 |
| Autovalores del estacionario | `−F/N₁`, `−F/N₂` | 1e-8 |
| Límite temporal (6000 s) vs estacionario independiente | distancia escalada | 6e-13 |

Y además: los cuatro integradores dan la misma trayectoria (< 1e-6 mol);
el tiempo en minutos da lo mismo que en segundos; conservación integrada
por volumen y global < 1e-13 y residuo instantáneo < 1e-16 en cuatro
montajes; el invariante `Σn = ρV` < 1e-15; misma `modelo_id` e ids en los
dos estudios; Newton itera de verdad (residuo inicial 0.17, dos
iteraciones); **31 rechazos** con su código, comprobando que los ids que
citan existen en la petición; los nueve presets dan su estado esperado; y
`/laboratorio/resolver` no regresa.

### 13.7 Ejemplos ejecutados

En `docs/ejemplos/`, generados por `tests/generar_ejemplos_estudios.py`
**ejecutando** el endpoint (los mismos que sirve
`/laboratorio/estudios/ejemplos`):

| Archivo (`estudio-…-peticion` / `-respuesta`) | Qué muestra |
|---|---|
| `dos-volumenes-tau-distintas` | La aceptación: τ = 50 y 200 s |
| `dos-volumenes-tau-iguales` | τ = 100 s en los dos |
| `dos-volumenes-estacionario` | **El mismo montaje** en estacionario: mismo `modelo_id` |
| `dos-volumenes-limite` | Horizonte largo: `contraste_estacionario.alcanzado: true` |
| `dos-volumenes-escalon` | Escalón de composición, dos tramos |
| `dos-volumenes-salida-lineal` | Inventario variable, cv2 vacío al empezar, Radau pedido |
| `dos-volumenes-vaciado` | Evento de vaciado: `estado: "parcial"` |
| `dos-volumenes-inicial-inconsistente` | Rechazo DAE: el inicial no cumple `ρV` |
| `formato-antiguo` | Rechazo de `{cv: {n, T, V}}` con la migración en el mensaje |

Más `estudio-dos-volumenes-tau-distintas-validar-respuesta.json` (lo que da
`/validar`) y `estudio-capacidades.json`.

### 13.8 Códigos nuevos

| Código | Severidad / categoría | Cuándo |
|---|---|---|
| `LAB_DIN_ESTUDIO_INVALIDO` | error / datos | Falta `estudio`, tipo desconocido o versión no soportada |
| `LAB_DIN_FORMATO_ANTIGUO` | error / datos | `estudio.iniciales` o `tiempoFinal` (preparación local de la mesa) |
| `LAB_DIN_CIERRE_FALTANTE` | error / datos | Un volumen sin `almacenamiento` |
| `LAB_DIN_CIERRE_NO_SOPORTADO` | error / modelo o datos | Cierre desconocido, o almacenamiento en algo que no es un volumen |
| `LAB_DIN_DAE_NO_SOPORTADA` | error / modelo | Densidad dependiente de la composición |
| `LAB_DIN_REACCION_NO_SOPORTADA` | error / modelo | Reacciones declaradas o `sinReaccion: false` |
| `LAB_DIN_CONDICION_INICIAL_FALTANTE` | error / datos | Falta `n` de alguna especie en algún volumen |
| `LAB_DIN_COMPOSICION_INICIAL_INDETERMINADA` | error / datos | Un `n` total sin `componente` |
| `LAB_DIN_INICIAL_INCONSISTENTE` | error / datos | `Σn_i(0) ≠ ρV` con inventario constante |
| `LAB_DIN_INVENTARIO_INICIAL_CERO` | error / datos | Volumen vacío con salida impuesta (`x` = 0/0) |
| `LAB_DIN_ENTRADA_TEMPORAL_INVALIDA` | error / datos | Forma ≠ escalón, variable no admitida, instante fuera de (0, final), duplicado, F = 0 en un tramo, fracción que fija el cierre |
| `LAB_DIN_TIEMPO_INVALIDO` | error / datos | Sin `tiempo`, final ≤ 0, unidad no admitida, muestras fuera de [2, 2000] |
| `LAB_DIN_SIN_ESTACIONARIO` | error / física | Salida impuesta ≠ caudal de entrada |
| `LAB_DIN_ESTACIONARIO_INDETERMINADO` | error / física | Infinitos estacionarios (salida impuesta = entrada, o jacobiano singular) |
| `LAB_DIN_SALIDA_DE_DOMINIO` | error / numérica | Un inventario cruzó por debajo de cero |
| `LAB_DIN_CONSERVACION` | error / numérica | Conservación o invariante fuera de 1e-7: fallo del motor |
| `LAB_DIN_DATO_NO_USADO` | advertencia | T, p, Q, `datos` locales, iniciales en estacionario, T o V iniciales |
| `LAB_DIN_ENERGIA_NO_RESUELTA` | advertencia | Hay fuentes de calor o trabajo y el estudio es solo material |
| `LAB_DIN_ESTUDIO_INCOHERENTE` | advertencia | `supuestos.estacionario` contradice `estudio.tipo` |
| `LAB_DIN_EVENTO` | advertencia / física | La integración se detuvo por un evento (`parcial`) |
| `LAB_DIN_ESTACIONARIO_NO_ALCANZADO` | información / física | El final temporal no es aún el estacionario |

Se reutilizan además `LAB_ID_DUPLICADO`, `LAB_REFERENCIA_INEXISTENTE`,
`LAB_PUERTO_INCOMPATIBLE`, `LAB_PIEZA_AISLADA`, `LAB_CICLO`,
`LAB_TOPOLOGIA_NO_SOPORTADA`, `LAB_CORRIENTE_MAL_CONECTADA`,
`LAB_VOLUMEN_SIN_ENTRADA/SALIDA`, `LAB_ESPECIFICACION_DUPLICADA`,
`LAB_ESPECIFICACION_EXCLUYENTE`, `LAB_FALTA_ESPECIFICACION`,
`LAB_VARIABLE_DESCONOCIDA`, `LAB_UNIDAD_INCOMPATIBLE`,
`LAB_VALOR_NO_FINITO`, `LAB_FRACCION_INVALIDA`,
`LAB_DATOS_COMPOSICION_INCOMPATIBLE`, `LAB_VALOR_FUERA_DE_DOMINIO`,
`LAB_NUMERO_DE_COMPONENTES`, `LAB_COMPONENTE_NO_DISPONIBLE` (también como
advertencia si un componente es una fórmula), `LAB_METODO_NO_SOPORTADO`,
`LAB_INTEGRACION_FALLIDA` y `LAB_SIN_CONVERGENCIA`.

### 13.9 Migración para el frontend

**La preparación local de hoy no es una petición ejecutable, y se rechaza
con nombre.** `DocumentoMesa.estudio = {version: 1, tiempoFinal, iniciales:
{cv: {n, T, V}}}` enviado tal cual da `LAB_DIN_FORMATO_ANTIGUO`. La
correspondencia:

| Hoy (local) | En el contrato | Por qué no es una copia |
|---|---|---|
| `tiempoFinal: 100` | `tiempo: {final: 100, unidad: "s", muestras}` | La unidad es explícita |
| `iniciales.cv.n` (total) | `condiciones_iniciales[]`: un `n` **por especie** y volumen | Un n total no determina la composición. **No repartas el total en partes iguales**: eso es inventar una composición |
| `iniciales.cv.T` | — (advertencia si se manda) | El modelo material no depende de T; será condición inicial con el almacenamiento térmico |
| `iniciales.cv.V` | `almacenamiento[].V` (+ `densidad_molar`) | V es un **parámetro del cierre**, no un estado, y pertenece a la definición física |
| — | `almacenamiento[]` por volumen | No existe hoy en la mesa y es obligatorio: sin cierre no hay ley de salida |
| `supuestos.estacionario` | `estudio.tipo` | Los adaptadores existentes siguen leyendo la bandera; este motor no. Si se contradicen, advertencia, y no entra en `modelo_id` |

Preservar `n = 0` como dato y la ausencia como ausencia (como ya hace la
mesa) es exactamente lo que el motor espera.

Para conectar: habilitar el estudio temporal **solo** cuando
`capacidades.estudios` contenga `"temporal"` y el montaje pase
`/laboratorio/estudios/validar` con `estado: "valido"`. El botón
estacionario → temporal **no** debe habilitarse:
`capacidades.transferencias.estacionario_a_temporal` es `false`.

### 13.10 Cambios respecto a lo anterior

- **Ningún cambio de forma** en `/laboratorio/*`. Solo dos textos en
  `core/laboratorio.py`: la `accion_sugerida` del rechazo de
  `estacionario: false` apunta ahora a `/laboratorio/estudios/resolver`, y
  la entrada de `capacidades.no_soportado` sobre el transitorio dice que lo
  es **en ese endpoint**. El código del diagnóstico no cambia.
- Contrato nuevo con su propio `schema_version`, y un `estado` nuevo
  (`parcial`) que solo existe en él.
- Veintiún códigos nuevos `LAB_DIN_*` en `core/errores.py`.

### 13.11 Siguiente entrega (no mezclada con esta)

Almacenamiento térmico y energía acoplada (T como estado, con su relación
constitutiva); fuentes reactivas multicomponente por volumen, con
generación y consumo brutos (y entonces el evento de agotamiento por
especie); transferencia validada de un estacionario a condición inicial;
perfiles temporales más allá del escalón. El momento sigue en formulación
hasta que haya fuerzas, geometría y cierres.

---

## 14. Estudios con energía: materia + energía, sin reacción (entrega A)

Respuesta a `frontend/ENTREGA_ENERGIA_REACTIVA_CLAUDE.md`, **entrega A**.
Solo backend. **La entrega B (fuentes reactivas por volumen) está en
[§15](#15-estudios-con-reacción-fuentes-reactivas-por-volumen-entrega-b)**;
cuando se escribió esta sección `capacidades.fisica.reaccion` seguía en `false` y
`no_soportado` lo dice. Tampoco la transferencia estacionario → temporal
(`capacidades.transferencias.estacionario_a_temporal: false`).

**Lo que hay:** las mismas rutas de §13 (`/laboratorio/estudios/*`), el
mismo montaje de uno o dos volúmenes en serie, y ahora cada volumen puede
almacenar **energía interna U**. Materia y energía se ensamblan, clasifican
y resuelven **juntas**: un único vector de estado `[n_i de todos los
volúmenes, U de los que la tienen como estado]`, evaluado en el mismo
instante. Estacionario (Newton sobre el mismo residuo) y temporal
(`solve_ivp`) sobre el mismo ensamblaje.

**Compatibilidad:** una petición **material** (sin `modelo_energetico`)
no cambia: mismo resultado, mismos ids, **mismo `modelo_id`**. Todo lo de
§13 sigue valiendo; los cambios visibles están en 14.9.

### 14.1 Cómo se activa: el esquema exacto

La energía es **definición física**, así que va fuera de `estudio`. Tres
piezas, ninguna con valores por omisión de propiedades:

```jsonc
{
  // ... el montaje de §13.2, más:
  "bloques":     [..., {"id": "q1", "tipo": "calor", "nombre": "Calefactor"}],
  "conexiones":  [..., {"id": "cq", "desde": "q1", "hacia": "cv1", "tipo": "calor"}],
  "supuestos":   {"estacionario": false, "adiabatico": false, "sinTrabajo": true,
                  "sinReaccion": true, "sinMovimiento": true},
  "especificaciones": [
    {"bloque_id": "in", "variable": "F",  "valor": 10.0,   "unidad": "mol/s"},
    {"bloque_id": "in", "variable": "x0", "valor": 0.5,    "unidad": "mol/mol"},
    {"bloque_id": "in", "variable": "T",  "valor": 300.0,  "unidad": "K"},   // obligatoria con energía
    {"bloque_id": "q1", "variable": "Q",  "valor": 5000.0, "unidad": "W"}    // o T del volumen, no las dos
  ],

  // 1. El modelo del FLUIDO (uno por petición)
  "modelo_energetico": {
    "tipo": "ideal_incompresible",
    "densidad_molar": {"valor": 10000.0, "unidad": "mol/m3"},
    "cp": [{"componente": "benzene", "valor": 150.0, "unidad": "J/(mol*K)"},
           {"componente": "toluene", "valor": 150.0, "unidad": "J/(mol*K)"}],
    "T_referencia": {"valor": 298.15, "unidad": "K"},
    "dominio_T": {"min": 250.0, "max": 400.0, "unidad": "K"}
  },
  "presion_sistema": {"valor": 101325.0, "unidad": "Pa"},   // opcional; por omisión 101325 Pa, declarado

  // 2. Cómo almacena energía CADA volumen
  "almacenamiento": [
    {"bloque_id": "cv1", "cierre": "inventario_constante",
     "V": {"valor": 0.05, "unidad": "m3"},
     "densidad_molar": {"valor": 10000.0, "unidad": "mol/m3"},
     "energia": {"modelo": "solo_fluido"}},
    {"bloque_id": "cv2", "cierre": "inventario_constante",
     "V": {"valor": 0.2, "unidad": "m3"},
     "densidad_molar": {"valor": 10000.0, "unidad": "mol/m3"},
     "energia": {"modelo": "fluido_y_pared",
                 "capacidad_pared": {"valor": 450000.0, "unidad": "J/K"},
                 "adiabatico": true}}
  ],

  // 3. La energía inicial, en el ESTUDIO (por volumen, sin componente)
  "estudio": {
    "version": 1, "tipo": "temporal",
    "condiciones_iniciales": [
      ...los n_i de §13...,
      {"bloque_id": "cv1", "magnitud": "T", "valor": 300.0, "unidad": "K"},
      {"bloque_id": "cv2", "magnitud": "T", "valor": 300.0, "unidad": "K"}
      // o "magnitud": "U" con unidad J, kJ o MJ; o las dos si son consistentes
    ],
    "tiempo": {"final": 1500.0, "unidad": "s", "muestras": 61},
    "entradas_temporales": [
      {"bloque_id": "in", "variable": "T", "instante": {"valor": 100.0, "unidad": "s"},
       "valor": 320.0, "unidad": "K"},
      {"bloque_id": "q1", "variable": "Q", "instante": {"valor": 300.0, "unidad": "s"},
       "valor": -3000.0, "unidad": "W"}
    ]
  }
}
```

| Campo | Qué es | Reglas |
|---|---|---|
| `modelo_energetico.tipo` | Modelo del fluido | `ideal_incompresible` o `proveedor_liquido` (14.2). Otro: `LAB_DIN_MODELO_ENERGETICO_NO_SOPORTADO` |
| `.densidad_molar` | ρ del fluido | Obligatoria. **Tiene que coincidir** con la del cierre de cada volumen (es el mismo fluido): si no, `LAB_DIN_PROPIEDADES_INCOHERENTES` |
| `.cp[]` | cp por especie | Solo `ideal_incompresible`, **una por especie**, unidades `J/(mol*K)`, `kJ/(kmol*K)`, `J/(kmol*K)`, `kJ/(mol*K)`. Falta una: `LAB_DIN_PROPIEDAD_FALTANTE` |
| `.T_referencia` | Origen común de U y h | Solo `ideal_incompresible`, obligatoria. En `proveedor_liquido` es 298.15 K y declararla es `LAB_ESPECIFICACION_EXCLUYENTE` |
| `.dominio_T` | Intervalo donde el modelo monofásico vale | Obligatorio en los dos. Con el proveedor, dentro de su tabla |
| `presion_sistema` | P uniforme | Entra en h = u + P/ρ. Por omisión 101325 Pa, y la respuesta lo dice (`sistema.p`, `procedencia`) |
| `almacenamiento[].energia.modelo` | Qué almacena energía | `solo_fluido` o `fluido_y_pared` (+ `capacidad_pared` en J/K, kJ/K, MJ/K). Falta con energía: `LAB_DIN_CIERRE_FALTANTE` |
| `almacenamiento[].energia.adiabatico` | Q = 0 en ese volumen | Opcional, booleano. Alternativa por volumen al supuesto global |
| `especificaciones` `in.T` | T de la alimentación | Obligatoria con energía |
| `especificaciones` `{vol}.T` | **T impuesta** del volumen | Define un control: U pasa a algebraica y Q se calcula (14.4) |
| `especificaciones` `{calor}.Q` | Calor impuesto | W, kW, MW, J/s. Positivo hacia el volumen |
| condiciones `T` / `U` | Energía inicial por volumen | Una de las dos; las dos solo si cumplen U = U(n,T). Con T impuesta, ninguna o la misma T |
| escalones `in.T`, `{calor}.Q` | Entradas temporales | Además de F y x. Q solo si su volumen está en modo calor |

Sin `modelo_energetico`, un `almacenamiento[].energia` da advertencia
`LAB_DIN_DATO_NO_USADO` y el estudio es material.

### 14.2 Los dos modelos de fluido

En los dos, **U y h tienen el mismo origen** y se diferencian en el
trabajo de flujo:

$$ U = \sum_i n_i\,u_i(T) + C_w\,(T - T_{ref}) \qquad h_i(T,P) = u_i(T) + P/\rho $$

| | `ideal_incompresible` | `proveedor_liquido` |
|---|---|---|
| $u_i(T)$ | $c_{p,i}\,(T - T_{ref})$, todo declarado | $h_i^{prov}(T) - P/\rho$ |
| $c_{p,i}$ | constante declarada | $c_{p,i}(T)$ del proveedor (spline sobre `thermo`) |
| Origen | $u_i(T_{ref}) = 0$ | $h_i(298.15\,\text{K}) = 0$ del líquido puro |
| Mezcla | ideal | ideal: el proveedor no tiene entalpía de exceso |
| Fase | **supuesta** líquida en el dominio | **comprobada**: $P_{burbuja}(T,x) < P$ en cada estado |
| Inversión U → T | explícita | `brentq` sobre la tabla |
| Para qué | caso de prueba con solución analítica | propiedades reales |

El modelo ideal es un **caso de prueba elegido como tal**, no una
simplificación impuesta al proveedor. La densidad molar es en los dos un
dato declarado (el proveedor no tiene volumen molar), igual para todas
las especies: es lo que significa una densidad molar de mezcla
constante, y es lo que mantiene válida la reducción DAE del inventario
de §13.5.

`respuesta.propiedades` devuelve el modelo usado: tipo, densidad, cp,
referencia, dominio, presión, origen, mezcla y fase.

**Una salvedad que conviene conocer:** con geometría rígida, inventario
constante y ρ uniforme, el trabajo de flujo neto $P/\rho\,(F_{ent} -
F_{sal})$ es cero, así que P **no cambia** T y confundir h con u tampoco
cambiaría el resultado. Se calcula igual, y la suite comprueba
directamente que la h devuelta es u + P/ρ.

### 14.3 Geometría, pared y modos térmicos

**Solo geometría rígida.** La energía exige `inventario_constante`. Con
`salida_lineal` o `salida_impuesta` el volumen cambia, la frontera se
mueve y el balance necesitaría el trabajo de frontera P dV/dt con su
geometría: `LAB_DIN_FRONTERA_MOVIL_NO_SOPORTADA`, no una aproximación.

**La pared** almacena $C_w (T - T_{ref})$ a la temperatura del fluido
(contacto perfecto) y no transporta nada. Es lo que permite constantes de
tiempo térmicas distintas de las materiales.

**Cada volumen cierra su energía de UNA forma:**

| Modo | Se declara | Se calcula | Variables |
|---|---|---|---|
| `calor` | Q en la fuente conectada | T | U diferencial, T algebraica |
| `adiabatico` | supuesto global o `energia.adiabatico` | T | igual; **la ecuación de energía sigue**, solo Q = 0 |
| `temperatura` | T del volumen (y una fuente conectada) | Q | U algebraica, Q algebraica |

| Combinación | Diagnóstico |
|---|---|
| T del volumen **y** Q de su fuente | `LAB_ESPECIFICACION_EXCLUYENTE` |
| T del volumen **y** adiabático | `LAB_ESPECIFICACION_EXCLUYENTE` |
| Fuente conectada **y** adiabático | `LAB_SUPUESTO_INCOHERENTE` |
| Ni fuente, ni T, ni adiabático | `LAB_FALTA_ESPECIFICACION` (la ausencia de fuente no es Q = 0) |
| Fuente sin Q y volumen sin T | `LAB_FALTA_ESPECIFICACION` |
| T impuesta sin fuente que reciba Q | `LAB_FALTA_ESPECIFICACION` |
| Dos fuentes de calor en un volumen | `LAB_TOPOLOGIA_NO_SOPORTADA` |
| Pieza `trabajo` o `sinTrabajo: false` | `LAB_SUPUESTO_NO_SOPORTADO` |
| `sinMovimiento: false` | `LAB_SUPUESTO_NO_SOPORTADO` |

### 14.4 Clasificación: qué es estado y qué no

**T no es variable diferencial.** El estado es (n_i, U); T es algebraica y
la determina el cierre $U = U(n,T)$. Como $\partial U/\partial T = C > 0$,
la relación es de **índice 1** y se invierte de forma única. La respuesta
lo dice en `clasificacion.energia.cierre`.

**Con T impuesta** aparece otra restricción de índice 2, la misma
estructura que el inventario: $U = U(n,T^*)$ no contiene Q, la variable
que determina. Derivada una vez a T constante da
$dU/dt = \sum_i u_i(T^*)\,dn_i/dt$, y el balance despeja Q. U deja de ser
estado. Sale en `clasificacion.restricciones` con
`variable_que_determina: "{calor}.Q"` y `indice: 2`.

`tipo_sistema` sigue siendo `"DAE_indice_2_reducida_a_ODE"` (la energía
exige inventario constante, así que la restricción material está
siempre). `clasificacion.energia` trae `estados`, `cierre`,
`temperatura_impuesta`, `transporte` y `geometria`.

**Variables nuevas** (todas con `clase`, `unidad`, `bloque_ids`,
`determinada_por`):

| id | `clase` |
|---|---|
| `{vol}.U` (J) | `diferencial`; `algebraica` con T impuesta |
| `{vol}.T` (K) | `algebraica` por `{vol}:cierre_energetico`; `entrada` con T impuesta |
| `{corriente}.T` | `entrada` en la alimentación; `algebraica` por `{vol}:mezcla_perfecta_T` en las demás |
| `{corriente}.h` (J/mol) | `algebraica` por `{corriente}:entalpia` |
| `{calor}.Q` (W) | `entrada`; `algebraica` por `{vol}:energia` con T impuesta |
| `{vol}.capacidad_pared` | `parametro` |
| `fluido.densidad_molar`, `fluido.T_referencia`, `fluido.cp{i}`, `sistema.p` | `parametro` (`bloque_ids: []`) |

La corriente intermedia sigue siendo **una** variable: `medio.T` y
`medio.h` salen con `compartida: true` y los dos volúmenes.

**Ecuaciones nuevas:**

| id | `tipo` | ¿Cuenta? |
|---|---|---|
| `{vol}:energia` | `balance` (`diferencial`; `algebraica` con T impuesta) | sí |
| `{vol}:cierre_energetico` | `constitutiva` | sí: determina T (o U) |
| `{vol}:mezcla_perfecta_T` | `constitutiva` | sí |
| `{corriente}:entalpia` | `constitutiva` | sí |
| `{vol}:temperatura_impuesta` | `condicion` | no |
| `{vol}:energia_por_restriccion` | `derivada_de_restriccion` | no |
| `{vol}:adiabatico` | `condicion` | no |
| `global:energia` | `verificacion` | no; se **mide** |

`{vol}:energia` lleva en `terminos_descartados` el trabajo de eje
(`sinTrabajo`), las energías cinética y potencial (`sinMovimiento`), el
trabajo de frontera (`inventario_constante`) y, si es adiabático, el
calor. El caso `energia-tau-distintas`: **19 incógnitas, 19 ecuaciones,
GL = 0**, 6 variables diferenciales (4 n_i y 2 U).

### 14.5 Respuesta: lo que se añade

- **`fisica`**: `["materia"]` o `["materia", "energia"]`.
- **`propiedades`**: el modelo de fluido (14.2), o `null`.
- **`resultados.series`**: además de §13, `{vol}.U` (J), `{vol}.T` (K),
  `{vol}.capacidad_termica` (J/K), `{corriente}.T`, `{corriente}.h` (J/mol)
  y `{calor}.Q` (W) — la Q impuesta o la calculada.
- **`conservacion.energia`**: `por_volumen[]` (residuo integrado
  `U(t) − U(0) − (∫Fh_ent − ∫Fh_sal + ∫Q)`), `global` (usa **solo** la
  alimentación, la salida final y los Q), `residuo_instantaneo_max`, y
  **`transporte_interno`**: la energía que pasó por la corriente
  intermedia, que aparece con signo menos en un volumen y más en el otro.
  La cancelación **se mide**: el balance global no la usa y cierra igual.
  Mide el ensamblaje, no la precisión (§13.4).
- **`condiciones_iniciales_usadas.energia[]`**: por volumen T, U y qué se
  dio (`"T"`, `"U"`, `"T y U"`, `"T impuesta"`).
- **`constantes_de_tiempo[]`**: cada entrada lleva ahora `tipo`
  (`material` o `termica`). La térmica es $\tau_T = C/(F_{sal} c_{p,sal})$
  en el estado inicial, con `constante: false` cuando cambia con la
  composición, con T o con un escalón.
- **`integracion.atol.energias_J`**: el atol de cada U
  (`atol_relativo × max(|U0|, C × 100 K)`); `tramos[]` trae `T_alimentacion`
  y `Q`; `eventos_vigilados` añade el dominio térmico y, con el proveedor,
  la frontera de fase.
- **`estacionario.estados`**: T, U, capacidad y Q por volumen; T y h por
  corriente; Q por fuente. `conservacion.residuo_relativo_energia`.
  `escala_residuo` declara la escala de la energía (F c_p × 1 K).
- **`estacionario.estabilidad`**: autovalores del sistema **acoplado**
  (n, U), restringido a la variedad del inventario, con `acoplado: true`.
  En `energia-estacionario`: −F/N₁, −F/N₂ (materiales) y −1/τ_T1, −1/τ_T2
  (térmicos).
- **`contraste_estacionario`**: además, `distancia_termica_K`,
  `derivada_energia_escalada` y `tolerancia_termica_K` (1e-6 K).

### 14.6 Dominio, fase e inversión

| Situación | Cuándo se detecta | Resultado |
|---|---|---|
| T de un volumen llega a `dominio_T` | evento del integrador | `parcial`, evento `dominio_termico`, advertencia `LAB_DIN_SALIDA_DE_DOMINIO` |
| El contenido llega a su punto de burbuja (proveedor) | evento: $P - P_{burbuja}(T,x) = 0$ | `parcial`, evento `frontera_de_fase`, advertencia `LAB_DIN_FRONTERA_DE_FASE`. **No se continúa** con una extrapolación monofásica |
| Alimentación de un tramo fuera del dominio o no líquida | al validar | `invalido` |
| Estado inicial fuera del dominio o no líquido | al validar | `invalido` |
| T impuesta fuera del dominio | al validar | `invalido` |
| U inicial que ningún líquido alcanza | al validar | `LAB_DIN_INVERSION_U_IMPOSIBLE` |
| U(T) no invertible durante la integración | en el integrador | `no_convergente`, `terminacion: fallido` |
| Estacionario fuera del dominio o no líquido | tras el Newton | `invalido`, estados `null` |

El evento de fase usa $P - P_{burbuja}(T,x)$, una evaluación sin
iteración, en vez de la T de burbuja.

### 14.7 Lo que está verificado

`tests/validar_estudios_energia.py`, **112 comprobaciones**, y
`tests/validar_estudios.py` (las 137 materiales) intacta. Las
referencias **no comparten la formulación del motor**: el motor integra
(n, U) y despeja T; la suite usa soluciones analíticas en T, una ODE
escrita **en temperatura** (derivada a mano, con h = u + Pv y F_ent =
F_sal) y propiedades **sin la spline** del motor.

| Caso | Referencia | Error medido |
|---|---|---|
| Un volumen, escalones de T_in (300→320 K) y de Q (5000→−3000 W), composición cambiando a la vez | $T = T_{ss} + (T_0 - T_{ss})e^{-t/\tau}$ por tramos | 5e-9 K; composición 1e-11 |
| Un volumen, cp distintos (composición y T acopladas) | ODE en T, integrada aparte | 4e-10 K |
| Dos volúmenes, τ_T = 50 y 500 s (pared en cv2) | dos tanques en serie | 7e-10 K |
| Dos volúmenes, τ_T = 200 s en los dos (pared en cv1) | caso degenerado $t\,e^{-t/\tau}$ | 4e-10 K |
| Estacionario | $T_{ss} = T_{in} + Q/(F c_p)$ | 1e-9 K |
| Autovalores del acoplado | −F/N₁, −F/N₂, −1/τ_T1, −1/τ_T2 | 1e-8 |
| Adiabático en su estacionario, 5000 s | T constante | 0.0 K |
| T impuesta 320 K | $Q = F c_p (T^* - T_{in}) = 30$ kW; cv2 exponencial | 1e-6 W; 1e-8 K |
| Proveedor: U en tres muestras | $\sum n_i (h_i - P/\rho)$ con h por **cuadratura** del cp crudo | 3e-10 relativo |
| Proveedor: capacidad | $\sum n_i c_{p,i}$ con cp **sin spline** | 1e-6 relativo |
| Proveedor: T(t) de los dos volúmenes | ODE en T, aparte | 1.4e-9 K |
| Proveedor: estacionario | raíz de $F\,x\cdot(h(T) - h(T_{in})) = Q$ por cuadratura | 1e-9 K |
| Frontera de fase | T de burbuja de la composición del evento, calculada aparte | 0.0 K medido |
| Borde del dominio | $t^* = -\tau \ln\frac{T_{ss} - T_{max}}{T_{ss} - T_0}$ | 5e-9 s |

Y además: energía integrada por volumen y global < 1e-15, residuo
instantáneo < 2e-16; la corriente intermedia transporta energía y el
balance global cierra sin ella; cv2 no se comporta como un tanque aislado
ni con la T final de cv1 como entrada; mismo `modelo_id`, mismos ids y
estabilidad acoplada en el estacionario; contraste alcanzado con
horizonte largo (7e-11 K); **28 rechazos** con su código y con ids que
existen en la petición; los siete presets de energía dan su estado; y una
petición material sigue siendo material.

### 14.8 Ejemplos ejecutados

En `docs/ejemplos/`, generados por `tests/generar_ejemplos_estudios.py`
ejecutando el endpoint (y servidos por `/laboratorio/estudios/ejemplos`):

| Archivo (`estudio-…-peticion` / `-respuesta`) | Qué muestra |
|---|---|
| `energia-tau-distintas` | τ_T = 50 y 500 s; cv2 adiabático con pared |
| `energia-tau-iguales` | τ_T = 200 s en los dos con τ materiales distintas |
| `energia-estacionario` | **El mismo montaje** en estacionario, estabilidad acoplada |
| `energia-temperatura-impuesta` | cv1 a 320 K: U algebraica, Q calculado |
| `energia-proveedor` | cp(T) del proveedor, burbuja vigilada |
| `energia-ebullicion` | Llega a la burbuja: `parcial` con `frontera_de_fase` |
| `energia-sobreespecificada` | Rechazo: T y Q a la vez |

Más `estudio-energia-tau-distintas-validar-respuesta.json` (lo que da
`/validar`: clasificación y recuento sin números). Las respuestas
materiales de §13.7 se han **regenerado**: llevan los campos nuevos de
14.9.

### 14.9 Cambios respecto a §13

**Para una petición material nada cambia de resultado ni de
`modelo_id`.** Sí cambian algunos campos de la respuesta, todos
**aditivos** salvo uno:

| Campo | Cambio |
|---|---|
| `fisica`, `propiedades` | **nuevos** en la raíz |
| `modelo.clasificacion.energia` | **nuevo**; `null` sin energía |
| `constantes_de_tiempo[].tipo` | **nuevo** (`material` / `termica`) |
| `entradas_usadas.tramos[]` | **nuevos** `T`, `unidad_T`, `Q`, `unidad_Q` (`null` sin energía) |
| `entradas_usadas.escalones[]` | **nuevo** `bloque_id` |
| `integracion.tramos[]` | **nuevos** `T_alimentacion`, `Q` |
| `integracion.atol` | **nuevos** `energias_J`, `escala_energia` |
| `conservacion.energia` | **nuevo**; `null` sin energía |
| `estacionario.estabilidad.acoplado` | **nuevo** |
| `condiciones_iniciales_usadas.energia` | **nuevo** |
| **`capacidades.fisica.energia`** | **pasa de `false` a `true`**. Es el único cambio de valor: si el frontend lo usaba para ocultar la energía, ahora debe mirar además `capacidades.energia` |
| `capacidades.energia`, `cierres_de_almacenamiento[].admite_energia`, `tolerancias.contraste_termico_K` | **nuevos** |
| `LAB_DIN_ENERGIA_NO_RESUELTA` | solo cambia la `accion_sugerida` (apunta a `modelo_energetico`) |
| `LAB_DIN_DATO_NO_USADO` | con energía, T de la alimentación, T de un volumen y Q de una fuente **dejan de ser «no usadas»** |

Códigos nuevos (en `core/errores.py`):

| Código | Categoría | Cuándo |
|---|---|---|
| `LAB_DIN_MODELO_ENERGETICO_NO_SOPORTADO` | modelo | `modelo_energetico.tipo` desconocido |
| `LAB_DIN_PROPIEDAD_FALTANTE` | datos | Falta cp de una especie, `T_referencia` o `dominio_T` |
| `LAB_DIN_PROPIEDADES_INCOHERENTES` | datos | Densidad del fluido ≠ densidad del volumen; dominio fuera de la tabla del proveedor |
| `LAB_DIN_FRONTERA_MOVIL_NO_SOPORTADA` | modelo | Energía con inventario variable |
| `LAB_DIN_INVERSION_U_IMPOSIBLE` | física | Ninguna T del líquido da esa U |
| `LAB_DIN_FRONTERA_DE_FASE` | física | Estado no líquido (error al validar; advertencia como evento) |

Y se reutilizan con significado de energía: `LAB_DIN_SALIDA_DE_DOMINIO`
(también como evento térmico), `LAB_DIN_INICIAL_INCONSISTENTE` (T y U
inconsistentes; T inicial ≠ T impuesta), `LAB_DIN_CONDICION_INICIAL_FALTANTE`
(ni T ni U), `LAB_DIN_CIERRE_FALTANTE` (sin `energia` en un volumen),
`LAB_DIN_CIERRE_NO_SOPORTADO` (almacenamiento energético desconocido),
`LAB_ESPECIFICACION_EXCLUYENTE`, `LAB_SUPUESTO_INCOHERENTE`,
`LAB_FALTA_ESPECIFICACION` y `LAB_SUPUESTO_NO_SOPORTADO`.

### 14.10 Migración para el frontend

- Añadir los campos solo **después** de este contrato, y no simular
  energía en local: el motor la resuelve.
- Habilitar la energía cuando `capacidades.fisica.energia` sea `true` y el
  montaje pase `/validar`. Los modelos y almacenamientos admitidos están
  en `capacidades.energia`; los cierres que admiten energía, en
  `cierres_de_almacenamiento[].admite_energia`.
- El selector de modo térmico por volumen tiene tres valores excluyentes
  (calor, adiabático, T impuesta); la tabla de 14.3 es la que hay que
  aplicar al formulario.
- La energía inicial es **T o U**, por volumen, sin `componente`. Con T
  impuesta no hace falta. Una T de salida impuesta no se copia como T
  inicial de otro volumen, ni una potencia como energía.
- No ofrecer el modelo `proveedor_liquido` para especies que el catálogo
  no da aptas para entalpía (`/laboratorio/sustancias/buscar`).
- `parcial` con evento `frontera_de_fase` o `dominio_termico` conserva
  series válidas hasta el evento, como el vaciado.

### 14.11 Lo que no está, y la siguiente entrega

- **Entrega B: fuentes reactivas por volumen.** Hecha después: ver §15. Al
  escribir esta sección no estaba empezada en los
  estudios. Su base ya está: la energía de un volumen usa referencia
  **sensible** (u_i(T_ref) = 0 por especie), así que cuando entre la
  reacción el balance llevará el calor de reacción **explícito** con
  ΔH a la referencia, como en §7bis, y no Kirchhoff (eso lo contaría dos
  veces).
- Transferencia estacionario → temporal.
- Cambio de fase, frontera móvil, trabajo de eje, energías cinética y
  potencial, densidad dependiente de T o x, momento.

---

## 15. Estudios con reacción: fuentes reactivas por volumen (entrega B)

Respuesta a `frontend/ENTREGA_ENERGIA_REACTIVA_CLAUDE.md`, **entrega B**,
sobre la base de §14. Solo backend. Lo que sigue sin estar: la
**transferencia estacionario → temporal** (`capacidades.transferencias.
estacionario_a_temporal: false`) y las **tasas fijas** dentro de un estudio
(siguen en `/laboratorio/resolver`).

**Lo que hay:** cada pieza `reactor` puede llevar una o varias reacciones
con **leyes de velocidad**, en uno o en los dos volúmenes. La fuente de
cada especie, $\sum_r \nu_{ir}(r^+_r - r^-_r)$, se evalúa con la
composición y la temperatura **de ese volumen en ese instante**, dentro del
mismo vector de estado que la materia y la energía. Estacionario y
temporal sobre el mismo ensamblaje.

**No hay un motor cinético nuevo.** Se reutiliza, sin copiarlo:

| Pieza | De dónde sale |
|---|---|
| Ley de velocidad (accion de masas, Arrhenius referenciado, órdenes, bases) | `core/cinetica.py`: la misma que el CSTR estacionario y el lote |
| Lectura de la ley, unidades y base volumétrica | `lab._leer_ley`, el mismo lector que `/laboratorio/resolver` |
| Estequiometría que conserva elementos y masa | `est.validar_estequiometria` contra la matriz elemental de `thermo` |
| ΔH de reacción | `est.entalpias_de_reaccion`: $\nu\cdot H_f$ a 298.15 K |
| K(T) de la inversa del equilibrio | `lab._K_eq_de`: ruta rigurosa, la de `/laboratorio/equilibrio` |

### 15.1 Petición

Las reacciones van en `reacciones[]`, **igual que en `/laboratorio/resolver`**
(§7quater), y pertenecen a la definición física (entran en `modelo_id`):

```json
"supuestos": {"sinReaccion": false, ...},
"bloques": [..., {"id": "rx", "tipo": "reactor", "nombre": "Reactor"}, ...],
"reacciones": [
  {"id": "iso", "bloque_id": "rx", "nu": [-1.0, 1.0],
   "ley_directa": {"k_ref": {"valor": 50.0, "unidad": "mol/s"},
                   "T_ref": {"valor": 320.0, "unidad": "K"},
                   "Ea": 50000.0, "base_actividad": "actividad",
                   "ordenes": {"n-butane": 1.0}},
   "ley_inversa": {"desde_equilibrio": true}}
]
```

| Regla | Si no se cumple |
|---|---|
| Solo en piezas `reactor` | `LAB_REACCION_EN_NO_REACTOR` |
| `sinReaccion: true` con reacciones | `LAB_SUPUESTO_INCOHERENTE` |
| Un `reactor` sin reacción y sin `sinReaccion` | `LAB_SIN_REACCION_DECLARADA` (error); `sinReaccion: false` sin reactores: advertencia |
| **Ley de velocidad obligatoria** (`ley_directa`; `ley_inversa` propia o `{"desde_equilibrio": true}`) | `tasa`/`tasa_directa`/`tasa_inversa`/`tasa_neta`: **`LAB_DIN_TASA_FIJA_NO_SOPORTADA`**; sin ley: `LAB_LEY_INVALIDA` |
| `nu` conserva elementos y masa | `LAB_ELEMENTOS_NO_CONSERVADOS`, `LAB_MASA_NO_CONSERVADA`, `LAB_ESTEQUIOMETRIA_INVALIDA` |
| Órdenes no negativos | `LAB_ORDEN_INVALIDO` |
| Base volumétrica (`mol/(m3*s)`…) solo con `inventario_constante`, que fija V | `LAB_FALTA_VOLUMEN_REACTOR` |
| El id de una reacción no repite otro id ni el de una pieza | `LAB_ID_DUPLICADO` |
| **Sin `modelo_energetico`**: cada reactor necesita su `T` (especificación `{bloque_id: "rx", variable: "T"}`), a la que se evalúa k(T) | `LAB_FALTA_ESPECIFICACION`; y siempre la advertencia `LAB_DIN_ENERGIA_NO_RESUELTA` (el calor que mantiene esa T no se calcula) |
| **Con `modelo_energetico`**: `T_referencia` = 298.15 K y $H_f$ de todas las especies | `LAB_DIN_PROPIEDADES_INCOHERENTES`; `LAB_ENTALPIA_FORMACION_NO_DISPONIBLE` |

Por qué no tasas fijas: una tasa que no depende del estado sigue
consumiendo una especie agotada y produce inventarios negativos. En un
estacionario de `/laboratorio/resolver` es un dato; en un estudio que
evoluciona no describe nada.

Con energía, la temperatura de la cinética es la del volumen (calculada, o
impuesta en modo `temperatura`). Sin energía, el reactor es **isotermo por
declaración**.

### 15.2 Física

**Materia.** $\dfrac{dn_i}{dt} = F_{ent}x_{i,ent} - F_{sal}x_{i,sal} + \sum_r
\nu_{ir}\,\xi_r$, con $\xi_r = r^+_r - r^-_r$. Las brutas salen por
construcción:

$$G_i = \sum_r \big(\max(\nu_{ir},0)\,r^+_r + \max(-\nu_{ir},0)\,r^-_r\big)
\qquad C_i = \sum_r \big(\max(-\nu_{ir},0)\,r^+_r + \max(\nu_{ir},0)\,r^-_r\big)$$

Un neto cero con brutas positivas es **equilibrio dinámico**, no una
reacción parada, y las series lo dejan ver.

**Inventario constante con $\sum\nu \neq 0$.** La restricción $\sum_i n_i =
\rho V$ sigue, así que la salida es
$F_{sal} = F_{ent} + \sum_r (\sum_i \nu_{ir})\,\xi_r$: la reacción cambia
los moles y la restricción los mantiene. Si la reacción consume moles más
deprisa de lo que entran, la salida tendría que ser negativa: evento
`caudal_negativo`.

**Energía: referencia sensible con fuente química explícita.**

$$\frac{dU}{dt} = \dot Q + F_{ent}h_{ent} - F_{sal}h_{sal} - \sum_r \xi_r\,\Delta H_r(298.15\,\text{K})$$

con $U$ y $h$ **sensibles** ($u_i(T_{ref}) = 0$, sin formación) y
$\Delta H_r = \nu_r \cdot H_f$. Es la misma convención que el laboratorio
estacionario (§7bis). **No se corrige $\Delta H$ con Kirchhoff**: las
entalpías sensibles ya llevan la dependencia con T, y corregirla la
contaría dos veces. La transformación entre referencias es exacta: con
$U_{total} = U + \sum_i n_i H_{f,i}$ y $h_i + H_{f,i}$ en las corrientes, la
fuente química desaparece y el balance cierra igual. **Las dos se miden**
(15.4).

**Algoritmo acoplado.** Composición y T entran a la vez en la cinética y en
la energía, en el mismo vector de estado y en la misma evaluación: no hay
«primero la conversión, luego la T».

### 15.3 Lo que se añade a la respuesta

- **`fisica`**: añade `"reaccion"`.
- **`reacciones[]`** (raíz): por reacción, `nu`, `conserva` (elementos y
  masa medidos), `ley_directa` (forma, k_ref, T_ref, Ea, base, órdenes),
  `ordenes_por_omision`, `ley_inversa` (o el origen del equilibrio con su
  ruta de K), `reversible`, `brutas_disponibles` (siempre `true`),
  `volumen_m3`, `temperatura` usada y, con energía, `dH_referencia`
  (J/mol de avance) con su nota.
- **`modelo.variables`**: `{rx}.r_directa`, `{rx}.r_inversa` (si es
  reversible) y `{rx}.avance` (mol/s, algebraicas). **`modelo.ecuaciones`**:
  `{rx}:ley_directa`, `{rx}:ley_inversa` (constitutivas) y `{rx}:avance`
  (definición); el balance por especie lleva el término de avance en
  `latex_activo` y ya no descarta $G_i - C_i$; el de energía lleva
  $-\xi\,\Delta H$; la salida por restricción, el avance si $\sum\nu\neq0$.
  `clasificacion.reaccion` explica fuentes, inventario, referencia y
  rigidez. GL sigue en 0.
- **`resultados.series`**: `{rx}.r_directa`, `{rx}.r_inversa`, `{rx}.avance`;
  por volumen reactivo y especie `{vol}.generacion_bruta{i}`,
  `{vol}.consumo_bruto{i}`, `{vol}.fuente_neta{i}`; con energía
  `{vol}.calor_de_reaccion` (W, $\sum_r \xi_r \Delta H_r$; positivo absorbe).
- **`conservacion`**: por volumen, el residuo de especies incluye
  $\nu\int\xi$ (`reacciones` dice cuáles); **`elementos_y_masa`** (por
  volumen y global, **sin** las integrales de avance —la química los
  conserva por $A\nu = 0$—, y `moles_totales_cambian`); en `energia`,
  `referencia` y **`con_formacion`** (el balance con $H_f$ incluido, sin
  fuente química).
- **`estacionario.estados[vol]`**: `T_reaccion`, `reacciones[]` (r⁺, r⁻,
  avance, K usada), `por_especie[]` (brutas y neta), `calor_de_reaccion`.
  `conservacion.elementos`.
- **`estacionario.metodo`** es ahora **Newton amortiguado** (retroceso). Con
  reacción se prueban **dos arranques** (`arranques[]`: pesos 1..n y la
  composición de la alimentación, con iteraciones y pasos amortiguados), y
  si convergen a sitios distintos, **`estacionarios_distintos[]`** los da a
  todos con su estabilidad (multiplicidad de un reactor exotérmico).
- **`eventos[].componente`**: la especie, en un agotamiento.

### 15.4 Lo que está verificado

`tests/validar_estudios_reaccion.py`, **89 comprobaciones**. Tres clases de
referencia, ninguna del código que se prueba:

**1. El motor existente**, pidiendo `/laboratorio/resolver` en el momento
(no un JSON guardado), con un algoritmo distinto (brentq / least_squares
por volumen frente al Newton sobre el residuo ensamblado):

| Caso | Estudio (estacionario) | Laboratorio |
|---|---|---|
| Isoterma (`cinetica-isoterma`): avance | 46.912093430088305 | 46.912093430088305 |
| — Q calculado | −293 805.46470277995 W | −293 805.46470277995 W |
| Adiabática (`cinetica-adiabatica`): T | 369.46220038601774 K | 369.4622003860177 K |
| Inversa del equilibrio: avance | 44.95319504761247 | 44.953195047612475 |
| Dos reactores (o→m a 390 K, m→p adiabático): avances | 3.3333333333333326 / 0.7624020472549767 | 3.333333333333333 / 0.7624020472549756 |
| — T del segundo | 389.6343391241034 K | 389.6343391241034 K |

Y el temporal llega a cada uno (`contraste_estacionario.alcanzado`).

**2. Analíticas** (xilenos con base de fracción molar, γ = 1; o Ea = 0):

| Caso | Referencia | Error |
|---|---|---|
| o-xileno ⇌ m-xileno, inversa del equilibrio | $x_o = x_{ss} + (1-x_{ss})e^{-(F+k_1+k_2)t/N}$, $k_2 = k_1/K$ con K de `core/equilibrio.py` | 2.6e-11 |
| — en cada instante | $\ln(r^+/r^-) = \ln K - \ln(x_m/x_o)$ | < 1e-9 |
| — con F → 0 | el estacionario es el equilibrio de `/laboratorio/equilibrio` | 1e-7 (= F/(k₁+k₂)) |
| A → 2B con inventario constante | $F_{sal} = F + \xi$; $x_A$ raíz de $kx^2 + (F+k)x - F = 0$ | 2e-16 |
| Orden cero: agotamiento | $t^* = 100\ln(2000/1500)$ s | 7e-8 s |
| Exotérmica adiabática, cp constante, Ea = 0 | $T(t)$ con forzamiento exponencial; $\Delta T = -\Delta H\,\xi/(F c_p)$ | 1.2e-9 K |

**3. Otra formulación de la energía.** La adiabática con propiedades del
proveedor se integra aparte **en temperatura**:
$C\,dT/dt = F\,x_{ent}\cdot(h(T_{ent}) - h(T)) - \xi\,\Delta H_{rxn}(T) + Q$,
con $\Delta H_{rxn}(T)$ **a la T del volumen** sacada de `core/equilibrio.py`
(Kirchhoff). Coincide con el motor —que usa $\Delta H$ a 298.15 K y U
sensible— a **6.6e-9 K**. Es la comprobación de que el calor de reacción
no se cuenta dos veces: con Kirchhoff en la forma en U, o sin él en la
forma en T, no coincidirían. La suite comprueba además que
`dH_referencia` es $\nu\cdot H_f$ leído aparte y que **no** es ΔH a la T
del volumen.

Y además: elementos y masa sin integrales de avance < 2e-14; energía
sensible y con formación < 1e-15; brutas = avance en una irreversible;
r⁺ y r⁻ positivos a la vez en la reversible; cada reactor con su propia
fuente y la corriente intermedia transportando el intermedio; el segundo
reactor responde al primero en el mismo instante; Newton amortiguado con
los arranques declarados; GL = 0; **12 rechazos** con su código; los ocho
presets de reacción dan su estado.

### 15.5 Ejemplos ejecutados

`docs/ejemplos/estudio-…-peticion.json` / `-respuesta.json`, generados
ejecutando el endpoint:

| Ejemplo | Qué muestra |
|---|---|
| `reaccion-isoterma` | Los datos de `cinetica-isoterma`: T impuesta, Q calculado |
| `reaccion-adiabatica` | Los de `cinetica-adiabatica`: T y avance acoplados |
| `reaccion-desde-equilibrio` | Inversa derivada de K(T) |
| `reaccion-reversible-xilenos` | Hacia el equilibrio, sin energía (isotermo declarado) |
| `reaccion-dos-reactores` | Dos reactores, cada uno con su reacción, corriente compartida |
| `reaccion-a-dos-b` | Σν ≠ 0: la salida crece con el avance |
| `reaccion-agotamiento` | Orden cero: evento `agotamiento`, estado `parcial` |
| `reaccion-tasa-fija` | Rechazo: `LAB_DIN_TASA_FIJA_NO_SOPORTADA` |

Y una corrección: **`laboratorio-cinetica-desde-equilibrio-respuesta.json`
estaba desfasado**. Era de antes de que `desde_equilibrio` pasara a la K
rigurosa (§11, punto 8) y traía el avance viejo (44.9532247 en vez de
44.9531950). Está regenerado ejecutando el endpoint. Los otros 19
ejemplos de `/laboratorio/resolver` se han reejecutado y coinciden
exactamente con lo guardado.

### 15.6 Códigos y eventos nuevos

| Código | Severidad / categoría | Cuándo |
|---|---|---|
| `LAB_DIN_TASA_FIJA_NO_SOPORTADA` | error / modelo | Una reacción con tasa fija en un estudio |
| `LAB_DIN_AGOTAMIENTO` | advertencia / física | Evento: una especie consumida llega a cero con una ley que no la frena (orden cero en ella) |
| `LAB_DIN_ESTACIONARIO_INESTABLE` | advertencia / física | El estacionario tiene un autovalor con parte real positiva, o hay varios estacionarios distintos |

Eventos nuevos (terminales, estado `parcial`): **`agotamiento`** (con
`componente`) y **`caudal_negativo`** (advertencia
`LAB_DIN_SALIDA_DE_DOMINIO`). Se reutilizan los códigos de reacción del
laboratorio (`LAB_REACCION_EN_NO_REACTOR`, `LAB_ELEMENTOS_NO_CONSERVADOS`,
`LAB_LEY_INVALIDA`, `LAB_ORDEN_INVALIDO`, `LAB_FALTA_VOLUMEN_REACTOR`,
`LAB_SIN_REACCION_DECLARADA`, `LAB_ENTALPIA_FORMACION_NO_DISPONIBLE`,
`LAB_EQUILIBRIO_NO_UTILIZABLE`). `LAB_DIN_REACCION_NO_SOPORTADA` **ya no se
emite** (se conserva el nombre en `core/errores.py`).

### 15.7 Cambios respecto a §13 y §14

| Cambio | Para el frontend |
|---|---|
| **`capacidades.fisica.reaccion` pasa de `false` a `true`**, y hay un bloque nuevo `capacidades.reaccion` | Habilitar reacciones cuando sea `true` |
| Las reacciones y `sinReaccion: false` **ya no se rechazan** con `LAB_DIN_REACCION_NO_SOPORTADA` | `sinReaccion: false` sin ningún reactor da ahora **advertencia** `LAB_SIN_REACCION_DECLARADA` |
| La T de un `reactor` sin energía se usa (isotermo); antes era «no usada» | Ofrecerla como la T de la cinética |
| `estacionario.metodo` dice «Newton amortiguado»; nuevos `arranques`, `estacionarios_distintos` | Mostrar los arranques y, si los hay, los estacionarios distintos |
| `estacionario.escala_residuo`: el residuo se escala con F **o con las tasas brutas**, la mayor | Solo texto |
| Nuevos `reacciones` (raíz), `clasificacion.reaccion`, series y bloques de conservación de 15.3 | Aditivos |

Para una petición sin reacciones, nada cambia de resultado ni de
`modelo_id`.

### 15.8 Lo que no está

- **Transferencia estacionario → temporal**: no implementada, y
  `capacidades` sigue en `false`. Cuando se haga, el candidato saldrá de
  los inventarios y la U resueltos (no de F ni de h), con su cálculo de
  origen registrado.
- Tasas fijas en estudios; base de actividad en concentración (necesitaría
  el volumen molar de la mezcla, como en §7quater); órdenes negativos.
- Multiplicidad **exhaustiva**: el Newton con dos arranques encuentra hasta
  dos estacionarios y lo dice; no garantiza que no haya más.
- Momento, cambio de fase, frontera móvil con energía, trabajo de eje.

---

## 16. Auditoría por combinación, procedencia por término e interfaz térmica

Respuesta a `frontend/SIGUIENTE_CLAUDE_CIERRES_TRANSFERENCIA.md`. Solo
backend. **Primer hito verificable: la interfaz térmica.** Antes de ella,
lo que pedía la auditoría (combinaciones, procedencia por término) y la
corrección del hallazgo de la revisión de B. **No está** (y `capacidades`
lo dice): transferencia de materia entre volúmenes, momento, frontera
móvil, cambio de fase, control, y la transferencia estacionario → temporal.

`revision_contrato` sube a **4** (en la respuesta y en `capacidades`).
`schema_version` sigue en 1: todo es aditivo, y lo único que cambia de
valor está en 16.8.

### 16.1 La auditoría: qué se admite, por combinación

`capacidades.combinaciones` es ahora **la** declaración de soporte. Las
capacidades individuales (`fisica.energia`, `fisica.reaccion`…) no
implican que cualquier producto de ellas funcione: **lo que no está en una
fila no está soportado.** Cada fila trae `fisica`, `cierres`, `estudios`,
`estados_diferenciales`, `algebraicas`, `especificaciones`, `restricciones`,
`iniciales`, `dominio`, `metodo` (temporal y estacionario), `eventos` y
`no_soportado`. Resumen:

| Combinación | Cierres | Estudios | Estados diferenciales | Algebraicas | Especificaciones | Restricciones | Iniciales | Dominio | Eventos |
|---|---|---|---|---|---|---|---|---|---|
| `materia` | los tres | E, T | n_i | F, x de corrientes; N (inventario variable) | F, x de la alimentación | Σn = ρV (índice 2) | n por especie | n ≥ 0, F > 0 | vaciado, dominio |
| `materia+reaccion` | los tres | E, T | n_i | + r⁺, r⁻, ξ | + T de cada reactor (isotermo) | + F_sal con Σν | n por especie | + F_sal ≥ 0 | + agotamiento, caudal_negativo |
| `materia+energia` | inventario constante | E, T | n_i, U (salvo T impuesta) | T (cierre, índice 1), T y h de corrientes; U y Q con T impuesta | T alim; por volumen **una** de Q, T, adiabático | Σn = ρV; U = U(n,T*) con T impuesta (índice 2 en Q) | n; T o U | dominio_T, líquido (proveedor) | dominio_térmico, frontera_de_fase |
| `materia+energia+reaccion` | inventario constante | E, T | n_i, U | las dos anteriores | las de energía | las de energía + F_sal | n; T o U | ambos | todos los anteriores |
| `materia+energia+interfaz` | inventario constante (los dos) | E (en cadena), T | n_i, U | + Q₁₂ = G(T_desde − T_hacia) | + G por conexión térmica | las de energía | n; T o U | + G ≥ 0 | dominio_térmico, frontera_de_fase |
| `volumenes_cerrados` | inventario constante, sin corrientes | **solo T** | n_i (constantes), U | T, Q₁₂ | por volumen una de Q, T, adiabático (exterior) | Σn = ρV como **verificación** del inicial | n; T o U | los de energía | dominio_térmico, frontera_de_fase |

Método en todas: temporal `solve_ivp` sobre el vector conjunto (LSODA por
omisión, declarado como tal, con el cociente de rigidez; Radau, BDF o RK45
a petición; reinicio en cada escalón). Estacionario: Newton amortiguado
sobre el mismo residuo (con reacción, dos arranques declarados); con
salida impuesta la existencia se decide por estructura; con volúmenes
cerrados es indeterminado.

**Combinaciones rechazadas explícitamente**, con código: reacción e
interfaz en el mismo montaje (`LAB_DIN_INTERFAZ_NO_SOPORTADA`: no se ha
verificado, así que no se anuncia), reacción en un volumen cerrado
(`LAB_TOPOLOGIA_NO_SOPORTADA`: es un lote, `/laboratorio/lote`),
volúmenes cerrados sin energía, interfaz sin energía, energía con
inventario variable (frontera móvil).

**Recuento y su alcance.** `clasificacion.grados_libertad` es un
**recuento**: incógnitas menos ecuaciones que cuentan. `rango_origen`
dice de dónde sale la independencia: es **estructural** (cada ecuación
algebraica que cuenta se resuelve para una variable distinta en orden;
cada balance define la derivada de un estado distinto). No se calcula un
rango numérico, y un recuento GL = 0 **no prueba** que el sistema tenga
solución: lo prueba que el Newton o el integrador la encuentren, con su
residuo medido. No hay ni se promete un analizador simbólico.

### 16.2 Procedencia por término

Cada **balance** (`{vol}:materia_especie_{i}`, `{vol}:energia`) y cada
**verificación global** (`global:materia_especie_{i}`, `global:energia`)
trae, además de lo que ya traía:

```jsonc
"acumulacion": ["cv1.U"],                 // lo que se deriva en el lado izquierdo
"terminos": [
  {"rol": "entrada", "signo": 1,  "latex": "F_{1} h_{1}",
   "variables": ["in.F", "in.h"], "bloque_id": "in", "conexion_id": "c1",
   "coeficiente": null, "clave": "corriente:in", "nota": null},
  {"rol": "salida", "signo": -1, "latex": "F_{4} h_{4}",
   "variables": ["medio.F", "medio.h"], "bloque_id": "medio", "conexion_id": "c2",
   "clave": "corriente:medio", ...},
  {"rol": "calor", "signo": 1, "variables": ["q1.Q"], "conexion_id": "cq",
   "clave": "calor:q1", ...},
  {"rol": "intercambio", "signo": -1, "variables": ["it.Q"], "bloque_id": "cv2",
   "conexion_id": "it", "clave": "interfaz:it", "nota": "sale hacia cv2"},
  {"rol": "fuente_quimica", "signo": -1, "variables": ["iso.avance"],
   "coeficiente": -9510.0, "clave": "reaccion:iso", ...}   // con reacción (ΔH de la isomerización)
],
"residuo_terminos": 0.0
```

| `rol` | Qué es | Valor del término |
|---|---|---|
| `entrada` / `salida` | Una corriente que entra o sale del volumen | F·x_i (materia) o F·h (energía) |
| `fuente` | Una reacción en el balance de una especie | \|ν_i\|·ξ, con el signo de ν_i |
| `calor` | Una fuente de calor externa | Q |
| `intercambio` | Una interfaz térmica | Q₁₂: −1 en `desde`, +1 en `hacia` |
| `fuente_quimica` | El calor de una reacción (referencia sensible) | −ξ·ΔH(298.15 K); `coeficiente` = ΔH |

Valor del término = `signo × coeficiente (1 si es null) × producto de sus
variables`. **El `latex_activo` se genera de esta lista**, así que no puede
divergir de ella.

**Las verificaciones globales se construyen sumando los términos de los
balances por volumen**, agrupados por `clave`: lo que aparece en dos
balances con signos opuestos es interno (corriente intermedia, interfaz) y
pasa a **`cancelaciones`**, con en qué ecuación y con qué signo aparecía;
lo demás queda en sus `terminos` con `ecuacion_origen`. Las verificaciones
**no cuentan** como ecuaciones independientes (`cuenta_como_ecuacion:
false`).

**`residuo_terminos`** es la comprobación de correspondencia: el balance
**tal como se muestra**, evaluado con los valores devueltos (las derivadas
de la acumulación menos la suma de los términos, relativo al mayor
término; el peor de todas las muestras). Si la ecuación renderizada no
correspondiera a lo que el motor integra, no daría cero. En todos los
ejemplos da < 4e-16. En el estudio estacionario se evalúa en la solución.

### 16.3 El hallazgo de la revisión de B, corregido

Tenía razón: en `global:energia` (y en `global:materia_especie_*`, que
tenía el mismo defecto) el `latex_activo` se escribía a mano y **omitía**
la fuente química: el global de energía de `reaccion-adiabatica` mostraba
solo el transporte de entalpía, y el de materia no llevaba Σν·ξ. La
conservación numérica estaba bien (la medía otro código); lo que fallaba
era la trazabilidad de la formulación.

Ahora las dos globales se construyen sumando los balances por volumen
(16.2), y `reaccion-adiabatica` muestra:

```
\frac{d}{dt}\sum_v U_v = F_{1} h_{1} - F_{3} h_{3} - \xi_{iso} \Delta H_{iso}
```

La suite comprueba, para **cada** ejemplo reactivo, que `global:energia`
lleva un término `fuente_quimica` por reacción con signo −1 y
`coeficiente` igual a `reacciones[].dH_referencia`, y que su
`residuo_terminos` es cero.

### 16.4 La interfaz térmica

**Petición.** Una conexión `tipo: "termica"` entre dos volúmenes (ni
materia ni una fuente impuesta), y su conductancia en una lista nueva de
la definición física:

```json
"conexiones": [..., {"id": "it", "desde": "cv1", "hacia": "cv2", "tipo": "termica"}],
"interfaces_termicas": [
  {"conexion_id": "it", "conductancia": {"valor": 50.0, "unidad": "W/K"}}
]
```

| Regla | Si no |
|---|---|
| Une dos volúmenes **distintos** | `LAB_PUERTO_INCOMPATIBLE` |
| Cada conexión térmica tiene su G | `LAB_FALTA_ESPECIFICACION` (sin G no hay ley: no se supone ni 0 ni ∞) |
| G finito y ≥ 0 (G = 0 es un dato: no conduce) | `LAB_VALOR_NO_FINITO`, `LAB_VALOR_FUERA_DE_DOMINIO` |
| Unidad `W/K`, `kW/K`, `MW/K` | `LAB_UNIDAD_INCOMPATIBLE` |
| `conexion_id` existe y es térmica | `LAB_REFERENCIA_INEXISTENTE` |
| Una interfaz por par de volúmenes | `LAB_TOPOLOGIA_NO_SOPORTADA` |
| El id de la conexión no coincide con el de una pieza | `LAB_ID_DUPLICADO` |
| Con `modelo_energetico` | `LAB_DIN_INTERFAZ_NO_SOPORTADA` |
| Sin reacciones en el montaje | `LAB_DIN_INTERFAZ_NO_SOPORTADA` |

**Física.** $\dot Q_{12} = G\,(T_{desde} - T_{hacia})$, positivo de
`desde` a `hacia`. Contribuye $-\dot Q_{12}$ al balance de $U_{desde}$ y
$+\dot Q_{12}$ al de $U_{hacia}$. Es una relación **algebraica** entre las
T de los dos volúmenes, evaluada en el mismo instante y en el mismo
vector de estado: la interfaz **no** tiene inventario, ni derivada, ni
temperatura propia. Invertir la orientación de la conexión invierte el
signo de Q₁₂ y deja las temperaturas iguales (comprobado).

Variables nuevas: `{conexion}.G` (parámetro, W/K) y `{conexion}.Q`
(algebraica, W, `determinada_por: "{conexion}:conductancia"`). Ecuación
nueva: `{conexion}:conductancia` (constitutiva, cuenta). GL sigue en 0.

**La semántica de `adiabatico`, sin cambiar lo existente.** `adiabatico`
(global o de un volumen) significa **sin intercambio con el EXTERIOR**.
Una interfaz es **interna** y se suma aparte: ni la prohíbe ni la
habilita en silencio. Cada volumen sigue necesitando **una** condición
externa (Q de su fuente, T impuesta o adiabático): un volumen cuyo único
intercambio es la interfaz se declara adiabático. Con la T impuesta, el
Q calculado de su fuente incluye lo que entra o sale por la interfaz. Es
una extensión: antes no había interfaces, así que ningún montaje
existente cambia de significado.

**Respuesta.** `interfaces_termicas[]` en la raíz (conexión, desde, hacia,
G, ley, convención); serie `{conexion}.Q` con `conexion_id` y
`convencion`; en el estacionario, `estados[{conexion}].Q`;
`conservacion.energia.interfaces[]` con la energía transferida;
`constantes_de_tiempo[]` con una entrada `tipo: "interfaz"`, $\tau_{12} =
1/[G(1/C_1 + 1/C_2)]$; `clasificacion.interfaces_termicas` con la ley, el
signo y la semántica de adiabático.

### 16.5 Volúmenes cerrados

Un volumen **sin corrientes de materia** (ni entrada ni salida): rígido
(`inventario_constante`), con `modelo_energetico`, y que intercambia
energía por una fuente o por una interfaz. La alimentación pasa a ser
opcional: un montaje puede ser solo dos volúmenes cerrados unidos por una
interfaz.

- Sus $n_i$ son estados con $dn_i/dt = 0$: no cambian. La restricción
  $\sum n_i = \rho V$ es entonces una **verificación** del estado inicial
  (no determina nada) y no cuenta; se comprueba antes de integrar
  (`LAB_DIN_INICIAL_INCONSISTENTE` si no se cumple).
- **Estacionario indeterminado** (`LAB_DIN_ESTACIONARIO_INDETERMINADO`):
  el límite depende del estado inicial —$T_{lim} = (C_1T_1 + C_2T_2)/(C_1 +
  C_2)$ es una conservación, no un balance igualado a cero—. El temporal sí.
- Sin energía: `LAB_TOPOLOGIA_NO_SOPORTADA`. Con una ley de salida:
  `LAB_DIN_CIERRE_NO_SOPORTADO`. Con una reacción:
  `LAB_TOPOLOGIA_NO_SOPORTADA` (es un lote).
- `clasificacion.volumenes_cerrados` los lista; sus balances de materia
  descartan las corrientes con `supuesto: "volumen cerrado"`.

### 16.6 Lo que está verificado

`tests/validar_estudios_interfaz.py`, **65 comprobaciones**. Las referencias
están escritas en la suite:

| Caso | Referencia | Error |
|---|---|---|
| Dos cerrados, C₁ = 75 kJ/K, C₂ = 150 kJ/K, G = 50 W/K | $T_i(t)$ analíticas; τ = 1000 s | 1.5e-9 K |
| G = 10⁶ W/K | $T_{lim} = (C_1T_{10} + C_2T_{20})/(C_1+C_2)$ = 316.667 K | < 1e-8 K |
| C₁/C₂ = 1/100, τ = 0.15 s en 20 s, con Radau, BDF y LSODA | analítica | 1.5e-10, 4.1e-8, 6.9e-10 K |
| Corriente + interfaz (cv1 calentado, cv2 con pared y adiabático) | $T(t)$ por **exponencial de matriz** del sistema lineal en T | 1.3e-9 K |
| La misma, en estacionario | la solución lineal | < 1e-9 K |

Y además: G = 0 deja las T constantes; con T iguales Q₁₂ = 0 exactamente;
invertir la orientación conserva las T a 1e-9 y cambia el signo de Q₁₂;
U₁ + U₂ constante a 1e-12 en el aislado; energía por volumen (con ±∫Q₁₂)
y global (sin ella) < 1e-12; el global con corriente e interfaz conserva
solo alimentación, salida y calor externo, y cancela **una vez** la
corriente intermedia y **una vez** la interfaz; **`residuo_terminos` < 4e-16
en todos los ejemplos** (incluidos los reactivos, con la comprobación de
−ξΔH de 16.3); las verificaciones no cuentan; **17 rechazos** con códigos e
ids que existen en la petición (piezas **y** conexiones); un cerrado
calentado con el proveedor llega a la burbuja como evento `parcial`; los
cinco presets de interfaz dan su estado. Las cuatro suites de estudios
anteriores siguen verdes.

### 16.7 Ejemplos ejecutados

| Ejemplo (`estudio-…-peticion` / `-respuesta`) | Qué muestra |
|---|---|
| `interfaz-dos-cerrados` | Dos cerrados, τ = 1000 s hacia la T ponderada |
| `interfaz-en-cadena` | Corriente e interfaz a la vez: procedencia y cancelaciones |
| `interfaz-rigida` | G = 10⁶ W/K, Radau |
| `interfaz-estacionario` | Rechazo: estacionario de dos cerrados (indeterminado) |
| `interfaz-sin-conductancia` | Rechazo: conexión térmica sin G |

Todos los demás ejemplos de estudios están regenerados: llevan
`revision_contrato`, `terminos`, `cancelaciones` y `residuo_terminos`.

### 16.8 Cambios y migración para el frontend

| Cambio | Para el frontend |
|---|---|
| **`global:energia` y `global:materia_especie_*`**: su `latex_activo` cambia (ahora incluye las fuentes químicas y Σν·ξ) y su `origen_*` y `variables` salen de los términos | Mostrar el LaTeX tal cual; para el detalle, usar `terminos` y `cancelaciones` en vez de analizar el LaTeX |
| `latex_activo` de los balances por volumen: ahora generado de los términos; para los montajes existentes sale **idéntico** | Ninguno |
| Nuevos en cada ecuación: `acumulacion`, `terminos`, `residuo_terminos` (`null` en las que no son balance); en las globales, `cancelaciones` | Aditivos |
| Nuevos en la raíz: `revision_contrato` (4), `interfaces_termicas[]` | Aditivos |
| `capacidades`: `combinaciones` (la tabla de 16.1), `fisica.interfaz_termica`, `fisica.volumenes_cerrados`, `fisica.transferencia_de_materia_entre_volumenes: false`, `interfaces_termicas`, `volumenes_cerrados`, `procedencia_por_termino`, `transferencias.nota_estacionario_a_temporal` | Habilitar por combinación, no por capacidad suelta |
| `clasificacion`: `interfaces_termicas`, `volumenes_cerrados` | Aditivos |
| Una conexión `tipo: "termica"` entre dos volúmenes **ya no** se rechaza como puerto incompatible: es una interfaz (y exige su G) | Ofrecerla solo con energía |
| La alimentación es opcional si todos los volúmenes son cerrados | — |
| Código nuevo: `LAB_DIN_INTERFAZ_NO_SOPORTADA` (interfaz sin energía; interfaz con reacción) | — |

Para una petición sin interfaces ni volúmenes cerrados, **nada cambia de
resultado ni de `modelo_id`**: las interfaces entran en la huella solo si
se declaran.

### 16.9 Lo que no está, y lo siguiente

- **Pared con almacenamiento propio entre los volúmenes**: fuera, como
  pedía el documento. Una conductancia concentrada no resuelve el campo
  térmico de la pared.
- **Reacción con interfaz**: rechazada hasta verificarla.
- **Transferencia estacionario → temporal**: tarea separada, sin empezar;
  `capacidades` sigue en `false`. Cuando se haga saldrá de n y U
  resueltos, no de F ni de h, con su cálculo de origen.
- En entregas separadas, como ordena el documento: transferencia de
  materia entre volúmenes, momento concentrado, frontera móvil, cambio de
  fase, control y perturbaciones.

---

## 17. Un estacionario como condición inicial de un temporal

Respuesta a `frontend/ENTREGA_CLAUDE_TRAZABILIDAD_REUTILIZACION.md`. Solo
backend. Es el único hito de esa entrega: **la transferencia explícita de
una solución estacionaria válida al mismo modelo temporal.** No había
contrato parcial previo; la ruta y el esquema son los de esta sección.
**La cola separada no está hecha**: reacción + interfaz sigue rechazada,
y no se ha empezado la transferencia de materia, momento, frontera móvil,
cambio de fase ni control.

`capacidades.transferencias.estacionario_a_temporal` pasa a **`true`**.
`revision_contrato` sigue en 4: todo es aditivo.

### 17.1 Dos pasos, sin conversión en el cliente

```
1.  POST /laboratorio/estudios/transferir      (el montaje con estudio estacionario)
       -> condicion_inicial   (objeto opaco: inventarios, energías, origen, huellas, firma)

2.  POST /laboratorio/estudios/resolver        (el MISMO montaje con estudio temporal)
       estudio.condicion_inicial_transferida = condicion_inicial   (tal cual)
```

El cliente **no** convierte nada: el objeto del paso 1 va sin tocar al
paso 2. El servidor lo convierte en condiciones iniciales del contrato
(n por especie en mol, U en J) y lo comprueba.

### 17.2 `POST /laboratorio/estudios/transferir`

**Petición:** la misma de `/resolver` (`EstudioRequest`), con
`estudio.tipo = "estacionario"`, más:

```json
"transferencia": {"rama": 1}
```

`rama` es el índice de la rama del estacionario (entero ≥ 0). **Obligatoria
si hay varias**; con una sola, `0` o nada.

**Respuesta (`TransferirResponse`):**

| Campo | Qué es |
|---|---|
| `schema_version`, `revision_contrato`, `estado` | `resuelto` / `invalido` / `no_soportado` / `no_convergente` |
| `modelo_id`, `estudio_id`, `calculo` | Del estacionario de origen |
| **`condicion_inicial`** | El objeto a transferir (17.3), o `null` si no hay |
| `ramas[]` | **Todas** las ramas encontradas: `indice`, `arranque`, `estabilidad_local`, `n` y `T` por volumen, `avance` por reacción. Se devuelven también cuando falta elegir |
| `rama_elegida` | El índice usado |
| `estacionario` | El detalle del estacionario de la rama, como en `/resolver` |
| `diagnosticos`, `resumen_diagnosticos`, `capacidades` | Como siempre |

### 17.3 El objeto `condicion_inicial`

```jsonc
{
  "version": 1,
  "tipo": "estacionario",
  "origen": {
    "modelo_id": "…", "estudio_id": "…",
    "calculo_identificador": "…", "instante_utc": "…",
    "motor": {"version": "0.15.0", "commit": "…"},
    "schema_version": 1, "revision_contrato": 4
  },
  "huellas": {                        // una por ELEMENTO del montaje de origen
    "componentes": "…",
    "bloques": {"cv1": "…", …}, "conexiones": {"c1": "…", …},
    "especificaciones": {"in.F": "…", …}, "almacenamiento": {"cv1": "…", …},
    "reacciones": {"iso": "…"}, "interfaces_termicas": {"it": "…"},
    "modelo_energetico": "…", "presion_sistema": "…", "supuestos": "…"
  },
  "inventarios": [{"bloque_id": "cv1", "componente": "benzene", "magnitud": "n",
                   "valor": 250.0, "unidad": "mol"}, …],
  "energia": [{"bloque_id": "cv1", "magnitud": "U", "valor": 388750.0, "unidad": "J",
               "T": 303.333, "unidad_T": "K", "U_es_estado": true, "nota": "…"}, …],
  "comprobaciones": {
    "residuo_estacionario_escalado": 5.5e-15, "tolerancia_transferencia": 1e-8,
    "restricciones": [{"bloque_id": "cv1", "restriccion": "sum_i n_i = rho V",
                       "residuo_relativo": 0.0}, …],
    "estabilidad_local": {…}
  },
  "rama": {"indice": 0, "de": 1, "arranque": "…", "estabilidad_local": {…}},
  "referencia_energia": "sensible" | "sensible con fuente quimica explicita (dH a 298.15 K)" | null,
  "fluido": {…},                      // el modelo de propiedades usado
  "transformaciones": ["n_i: …", "U: …", "NO se transfieren caudales F ni entalpias de corriente h"],
  "firma": "…"                        // sha256 del objeto canónico, sin la firma
}
```

**Qué se transfiere y qué no.** Los **inventarios** $n_i$ y la **energía
interna** $U$ resueltos de cada volumen, en su referencia. **No** caudales
$F$ ni entalpías de corriente $h$: un caudal no es un inventario y una
entalpía de corriente no es una energía almacenada. $T$ va a título
informativo: el estado es $U$. En un volumen con T impuesta, $U$ es la
del cierre $U(n, T^*)$ y el temporal la comprueba contra $T^*$.

### 17.4 Lo que comprueba el temporal

Con `estudio.condicion_inicial_transferida`, **antes de integrar**:

| Comprobación | Si falla |
|---|---|
| No viene también `condiciones_iniciales` | `LAB_ESPECIFICACION_EXCLUYENTE` |
| `version` 1 y `tipo` estacionario | `LAB_DIN_ESTUDIO_INVALIDO` |
| La **firma** corresponde al contenido (nadie lo editó) | `LAB_DIN_TRANSFERENCIA_ALTERADA` |
| Las **huellas** coinciden con el montaje actual, elemento a elemento | `LAB_DIN_TRANSFERENCIA_INCOMPATIBLE`, **una por parte cambiada**, con las piezas y conexiones en `bloque_ids` / `conexion_ids` |
| El `modelo_id` de origen es el actual | `LAB_DIN_TRANSFERENCIA_INCOMPATIBLE` |
| Las **restricciones del destino**: Σn = ρV, U coherente con T impuesta, dominio y fase | Los códigos de siempre (`LAB_DIN_INICIAL_INCONSISTENTE`, `LAB_DIN_SALIDA_DE_DOMINIO`, `LAB_DIN_FRONTERA_DE_FASE`) |
| El estado **sigue siendo un estacionario del modelo actual** con las entradas base: residuo escalado ≤ 1e-8 | `LAB_DIN_TRANSFERENCIA_OBSOLETA` |

Nada se proyecta ni se corrige: un estado que no cumple se rechaza.

La firma es **integridad, no seguridad**: el algoritmo es público y se
puede volver a firmar. Por eso existe la última comprobación: un objeto
editado y re-firmado con otros números deja de ser un estacionario del
modelo y se rechaza como obsoleto. Lo mismo pasa si el motor cambia y el
estacionario de origen ya no es el suyo.

**Lo que cambia y lo que no.** Las **perturbaciones** se declaran como
`entradas_temporales` (escalones) del estudio temporal: cambian las
entradas, no la identidad del estado de origen. Cambiar el montaje (una
especificación base, un cierre, una propiedad, el dominio, una reacción,
una conexión) es otro modelo y se rechaza. `supuestos.estacionario` no
forma parte de la identidad (no entra en las huellas ni en el `modelo_id`).

**La respuesta del temporal** añade en `condiciones_iniciales_usadas`:

| Campo | Qué es |
|---|---|
| `procedencia` | `"transferida de un estacionario"` o `"declarada"` |
| `origen` | El `origen` del objeto, más `rama`, `firma` y `referencia_energia` |
| `residuo_estacionario_en_t0` | El residuo medido en el estado inicial |
| `escenario` | **`"sin_perturbacion"`** o **`"perturbado"`** |
| `perturbaciones` | Los escalones (instante, pieza, variable, valor), si los hay |

### 17.5 Ramas

El Newton del estacionario prueba ahora, con reacción y energía, **tres
arranques**: composición con pesos 1..n, composición de la alimentación y
uno **caliente** (pesos n..1 y T al 90 % del dominio declarado), porque un
reactor exotérmico puede tener una rama «apagada» y otra «encendida». Si
un arranque no converge, se hace una **continuación pseudo-transitoria**
desde el mismo arranque (50 tiempos de residencia con Radau) y después
Newton; `arranques[].via` dice cuál fue. Todas las ramas convergidas y
distintas salen en `ramas` con su estabilidad local.

- Con varias ramas y sin `transferencia.rama`: `LAB_DIN_RAMA_REQUERIDA`,
  sin condición, **y con las ramas devueltas** para elegir.
- Una `rama` que no existe: `LAB_DIN_RAMA_REQUERIDA`.
- **La búsqueda no es exhaustiva.** La continuación pseudo-transitoria
  solo lleva a ramas **estables**; una rama inestable intermedia solo se
  encuentra si un Newton directo cae en ella. Encontrar dos ramas
  demuestra multiplicidad; encontrar una no demuestra unicidad.

### 17.6 Lo que no se transfiere

| Caso | Diagnóstico |
|---|---|
| Volúmenes cerrados (estacionario indeterminado) | `LAB_DIN_TRANSFERENCIA_NO_POSIBLE` (el mensaje cita `LAB_DIN_ESTACIONARIO_INDETERMINADO`) |
| Salida impuesta ≠ alimentación (sin estacionario) | `LAB_DIN_TRANSFERENCIA_NO_POSIBLE` |
| El Newton no converge | `LAB_DIN_TRANSFERENCIA_NO_POSIBLE` (numérica) |
| La rama no es un estado físico (fuera de dominio, inventario negativo) | `LAB_DIN_TRANSFERENCIA_NO_POSIBLE` (física) |
| La petición no es un estudio estacionario | `LAB_DIN_TRANSFERENCIA_NO_POSIBLE` |

### 17.7 Lo que está verificado

`tests/validar_estudios_transferencia.py`, **43 comprobaciones**:

| Caso | Referencia | Medido |
|---|---|---|
| Energía, dos volúmenes, sin perturbación, 3000 s | se queda en el estacionario | T se mueve 3e-11 K, n 8e-11 mol; residuo en t₀ 5.5e-15 |
| Escalón de T de alimentación desde el estacionario | analítica de dos tanques (τ_T = 50 y 500 s) | 6e-9 K |
| Escalón de composición desde el estacionario | analítica (τ = 50 y 200 s) | 2e-11 |
| Reactor adiabático: U transferida | $\sum n_i (h_i(T) - P/\rho)$ calculada aparte | 2e-16 relativo |
| — sin perturbación | T y avance constantes | 1.6e-11 K |
| — perturbado (T alim 320 → 325 K) | el estacionario de **`/laboratorio/resolver`** para 325 K | 1e-10 K |
| Dos ramas (300.89 K y 458.47 K) | cada una elegida se mantiene | deriva ≤ 1e-13 K |

Y además: la energía con formación cierra (sin doble conteo); el origen
(modelo, estudio, cálculo, motor, revisión), la rama, la referencia y la
firma se devuelven y llegan al temporal; los escenarios sin perturbar y
perturbado se distinguen con el **mismo** origen; dos ramas sin elegir se
rechazan con las ramas devueltas; dos cerrados y un estudio temporal no se
transfieren; **11 rechazos** con su código y, donde aplica, la pieza o la
conexión concreta: V de un volumen, sustancias, dominio, referencia,
especificación base, ley de reacción, conexión térmica añadida, objeto
editado, objeto editado y re-firmado (obsoleto), condiciones duplicadas y
versión desconocida. La bandera `estacionario` no invalida. Las cinco suites
de estudios anteriores siguen verdes.

### 17.8 Ejemplos ejecutados

`docs/ejemplos/estudio-{id}-transferir-peticion.json` /
`-transferir-respuesta.json` y, cuando hay condición,
`-temporal-peticion.json` / `-temporal-respuesta.json`, generados
ejecutando los dos endpoints en cadena:

| `id` | Qué muestra |
|---|---|
| `transferencia-energia` | Energía, dos volúmenes: el temporal se queda |
| `transferencia-escalon` | El mismo origen, escenario perturbado (T alim 300 → 320 K) |
| `transferencia-reaccion` | El reactor adiabático: n y U sensible |
| `transferencia-rama-encendida` | Dos ramas: se elige la 1 (encendida) |
| `transferencia-sin-rama` | Rechazo: dos ramas, ninguna elegida (con `ramas`) |
| `transferencia-cerrados` | Rechazo: estacionario indeterminado |

### 17.9 Cambios y migración

| Cambio | Para el frontend |
|---|---|
| Ruta nueva `POST /laboratorio/estudios/transferir` | El botón estacionario → temporal puede habilitarse cuando `capacidades.transferencias.estacionario_a_temporal` sea `true` y la fila de la combinación lo diga |
| `estudio.condicion_inicial_transferida` (nuevo, opcional) | Guardar el objeto **tal cual** y mandarlo tal cual; no editarlo ni convertirlo |
| `condiciones_iniciales_usadas`: `procedencia`, `origen`, `residuo_estacionario_en_t0`, `escenario`, `perturbaciones` | Aditivos |
| `capacidades.transferencias.estacionario_a_temporal`: **`false` → `true`**, con `nota_estacionario_a_temporal`; cada fila de `combinaciones` lleva `transferencia_estacionario_a_temporal` (sí en todas salvo `volumenes_cerrados`) | Habilitar por fila |
| **Estacionario con reacción y energía: tres arranques** (antes dos), `arranques[].via`, y continuación pseudo-transitoria | Mostrar `via`; puede aparecer una rama que antes no se encontraba |
| `CONDICION_MAXIMA` del Newton: 1e12 → 1e15 (una cinética rígida da cond ~1e13 sin ser singular) | Ninguno |
| El `modelo_id` incluye el tipo de una conexión **solo si es `termica`** (antes, convertir una conexión en interfaz no lo cambiaba) | Los `modelo_id` de montajes sin interfaz no cambian |
| Códigos nuevos: `LAB_DIN_TRANSFERENCIA_NO_POSIBLE`, `LAB_DIN_RAMA_REQUERIDA`, `LAB_DIN_TRANSFERENCIA_ALTERADA`, `LAB_DIN_TRANSFERENCIA_INCOMPATIBLE`, `LAB_DIN_TRANSFERENCIA_OBSOLETA` | — |

### 17.10 Lo que no está

- **La cola separada de la entrega**: reacción + interfaz (sigue rechazada
  con `LAB_DIN_INTERFAZ_NO_SOPORTADA`), transferencia de materia
  concentrada, momento, frontera móvil, cambio de fase y control.
- **Multiplicidad exhaustiva** (17.5).
- **Transferir desde un estacionario con escalones**: el origen es el
  estacionario de las entradas **base**; las perturbaciones van en el
  temporal.
- **Transferir a otro montaje**: por diseño. Un estado es de un modelo, y
  cambiar el modelo invalida la transferencia.


### 17.11 Corrección: la firma sobrevive al roundtrip JSON de un navegador

Respuesta a `frontend/INCIDENCIA_TRANSFERENCIA_JSON_CLAUDE.md`. La
reproducción era correcta: un objeto `condicion_inicial` que JavaScript
pasaba por `JSON.parse` y `JSON.stringify` volvía con
`LAB_DIN_TRANSFERENCIA_ALTERADA` sin que nadie lo hubiera tocado.

**La causa.** `firma()` hacía el sha256 del texto de `json.dumps` **sin
canonicalizar los números**. JavaScript no distingue enteros de reales:
`3887500.0` vuelve como `3887500` y `-0.0` como `0`. Es el mismo número,
pero otro texto y otra firma. Las huellas por elemento canonicalizaban, pero
redondeando a 15 cifras, que tampoco valía: relajaba la detección.

**La corrección.** Una forma canónica **exacta**,
`trazabilidad.canonico_exacto`, para la firma **y** para las huellas por
elemento:

- todo número se lleva a float64, que es lo único que conserva un JSON de
  navegador;
- si es un entero exacto (|v| < 2⁵³) se escribe como entero: `1`, `1.0`,
  `1e0`, y también `-0.0` y `0`, dan el mismo texto;
- si no, con la representación más corta que identifica **ese** float
  (`repr`), la misma que escribe JavaScript y que Python vuelve a leer al
  mismo bit;
- **no se redondea nada**: dos floats distintos nunca dan el mismo texto
  (`0.1 + 0.2` no es `0.3`); un NaN o un infinito no firman.

`modelo_id` y el resto de huellas del motor no cambian: siguen con
`canonico`, porque cambiarlo movería los identificadores de todos los
servicios.

**Lo que no cambia.** Las comprobaciones de 17.4: huellas por elemento
(ahora exactas), restricciones del destino y vigencia del estacionario. La
firma sigue siendo integridad, no autenticación.

**Lo que el frontend no tiene que hacer.** Ni conservar lexemas JSON, ni
convertir números a texto, ni recalcular la firma: el objeto se guarda y
se manda como JavaScript lo serialice.

**Migración.** La firma cambió. Un objeto generado **antes** de esta
corrección (con la firma anterior) se rechaza como
`LAB_DIN_TRANSFERENCIA_ALTERADA`: hay que **volver a pedir
`/laboratorio/estudios/transferir`**. Los ejemplos de `docs/ejemplos/` están
regenerados con la firma nueva. El campo `firma` sigue siendo un sha256
hexadecimal de 64 caracteres; la forma del objeto no cambia.

**Verificado** en `tests/validar_estudios_transferencia_json.py` (**32
comprobaciones**) con **Node real**:

- los dos ejemplos temporales del contrato, leídos tal cual **y** tras
  `JSON.parse`/`JSON.stringify`, dan `valido`;
- para energía, reacción y las dos ramas del reactor con multiplicidad:
  `/transferir` → JavaScript parsea la respuesta, **monta él la petición
  temporal** con la condición tal cual y la serializa → ese texto, enviado
  crudo, da `valido` en `/validar` y `resuelto` en `/resolver`, con
  procedencia transferida y residuo en t₀ < 1e-10;
- sobrevive a guardar y recargar (dos roundtrips), exportar con sangría
  (`JSON.stringify(x, null, 2)`) e importar;
- la detección no se relaja. Editado en JavaScript, se rechaza como
  `ALTERADA`: un inventario multiplicado por (1 + 1e-12), U + 1e-6 J o el
  identificador del cálculo de origen. Alterado y re-firmado sigue siendo
  `OBSOLETA`; el `modelo_id` de origen cambiado y re-firmado,
  `INCOMPATIBLE`;
- los cambios de cierre (V de cv2), sustancias, referencia y especificación
  base, hechos tras el roundtrip, conservan el diagnóstico
  `INCOMPATIBLE` por elemento;
- `F = 10.0` llega como `10` y **no** cuenta como cambio de modelo;
- un objeto con la firma anterior se rechaza (la migración de arriba).

La suite **falla** (no se salta) si `node` no está en el PATH: una prueba
entre lenguajes que se omite en silencio no prueba nada.

---

## 18. Reacción + interfaz térmica

Respuesta a `frontend/SIGUIENTE_CLAUDE_REACCION_INTERFAZ.md`. Solo backend.
**La combinación reacción + interfaz térmica deja de rechazarse**, tras
verificarla sobre el mismo ensamblaje acoplado. No hay motor cinético ni
integrador nuevos: las leyes de `core/cinetica.py`, las propiedades de
`core/fluidos.py`, los términos de §16 y el integrador de siempre.
**No está**: momento, transferencia de materia, frontera móvil, cambio de
fase ni control. `revision_contrato` sigue en 4: todo es aditivo.

### 18.1 Qué cambió en el motor

**Casi nada, y es el resultado esperado.** El ensamblaje ya tenía la forma
correcta:

- calcula las T de **todos** los volúmenes antes de nada;
- las tasas de cada reactor se evalúan con **su** composición y **su** T, y
  Q₁₂ = G(T_desde − T_hacia) con las dos T del mismo instante;
- el balance de energía suma la fuente química (−Σξ·ΔH a 298.15 K) y la
  interfaz (∓Q₁₂) como términos separados.

El único bloqueo era el rechazo explícito con `LAB_DIN_INTERFAZ_NO_SOPORTADA`,
y se ha quitado. Ese código ya solo se emite para una interfaz sin energía.

**Dos correcciones que salieron al verificar** (afectan también a otras
combinaciones):

1. **Un evento antes de la primera muestra rompía la integración.** Si una
   especie que ya está en cero tiene un consumo de orden cero, se agota en
   t = 0⁺; y un calentamiento fuerte puede llegar al borde del dominio antes
   de la primera muestra. `solve_ivp` devuelve entonces `t` e `y` vacíos (y
   como lista), y el motor fallaba con un error de Python en vez de
   devolver `parcial` con el evento. Ahora se normalizan y el resultado es
   el correcto: `parcial`, con el evento y su instante.
2. **La transferencia emitía un cero numérico negativo.** En un estacionario,
   una especie que ni entra ni se forma en un volumen (el p-xileno en el
   primer reactor) queda en −6e-24 mol por el redondeo del Newton, y el
   temporal la rechazaba con razón (un inventario negativo no es un
   inventario). Ahora `/transferir`:
   - transfiere como **0** un inventario negativo de magnitud ≤ 1e-12 × el
     inventario del volumen, y **lo declara** en
     `condicion_inicial.comprobaciones.correcciones_de_redondeo` (pieza,
     especie, valor resuelto, valor transferido, umbral, motivo);
   - **rechaza** cualquier negativo mayor con
     `LAB_DIN_TRANSFERENCIA_NO_POSIBLE`.

   El temporal comprueba después, como siempre, que el estado corregido
   siga siendo un estacionario (vigencia): la corrección no se esconde ni se
   exime de esa comprobación.

### 18.2 La combinación, declarada

`capacidades.combinaciones` tiene una fila nueva,
**`materia+energia+reaccion+interfaz`**:

| Campo | Valor |
|---|---|
| `cierres` | `inventario_constante` en los dos volúmenes, en cadena |
| `estudios` | estacionario y temporal |
| `estados_diferenciales` | `{vol}.n{i}`, `{vol}.U` (salvo T impuesta) |
| `algebraicas` | T de volumen y corrientes, h, r⁺, r⁻, ξ, Q₁₂, y U y Q con T impuesta |
| `especificaciones` | T de alimentación, G por conexión térmica, y por volumen **una** de Q, T o adiabático (al exterior; la interfaz es interna) |
| `restricciones` | Σn = ρV (índice 2) con F_sal = F_ent + Σ(Σν)ξ; U = U(n,T*) con T impuesta |
| `referencia_energia` | sensible con fuente química −Σξ·ΔH(298.15 K); `T_referencia` = 298.15 K obligatoria |
| `evaluacion` | composición, T, tasas y Q₁₂ de los dos volúmenes en el mismo instante y en un único vector de estado |
| `eventos` | agotamiento, caudal_negativo, dominio_termico, frontera_de_fase |
| `transferencia_estacionario_a_temporal` | sí |
| `no_soportado` | volúmenes cerrados con reacción (es un lote), pared con almacenamiento propio, tasas fijas, búsqueda exhaustiva de ramas |

La fila `materia+energia+interfaz` ya no lista la reacción entre lo no
soportado. Un **volumen cerrado con reacción** sigue rechazado
(`LAB_TOPOLOGIA_NO_SOPORTADA`), haya o no interfaz.

El estacionario usa el método de §17.5: Newton amortiguado con tres
arranques (el caliente incluido) y continuación pseudo-transitoria si un
arranque no converge, declarados en `arranques`. Se devuelven todas las
ramas encontradas con su estabilidad local, **sin promesa de
exhaustividad**.

### 18.3 Lo que está verificado

`tests/validar_estudios_reaccion_interfaz.py`, **53 comprobaciones**. El
montaje es de dos reactores de xilenos en cadena: o → m en el primero,
calentado con Q = 20 kW, y m → p en el segundo, adiabático al exterior,
unidos por una interfaz. Hay además uno de craqueo con Σν = +1.

**La referencia independiente** es la misma física escrita **en
temperatura**, derivada a mano en la suite:

$$C_1\frac{dT_1}{dt} = F\,x_{alim}\cdot(h(T_{alim}) - h(T_1)) - \xi_1\,\Delta H_1(T_1) + Q - Q_{12}$$
$$C_2\frac{dT_2}{dt} = F\,x_1\cdot(h(T_1) - h(T_2)) - \xi_2\,\Delta H_2(T_2) + Q_{12}$$

con $\Delta H(T) = \nu\cdot(H_f + h_{sens}(T))$ **a la T de cada volumen**
(Kirchhoff) y las leyes de velocidad escritas aparte. El motor usa U
sensible con ΔH a 298.15 K. Que coincidan es la prueba de que no hay doble
conteo del calor químico ni error de signo en la interfaz.

| Validación del documento | Cómo | Medido |
|---|---|---|
| 1. G = 0 recupera la reacción sin interfaz | las mismas series con y sin la conexión | diferencia **0.0** |
| 1. Reacción desactivada recupera la interfaz | k = 0 frente a recipientes con `sinReaccion` | diferencia **0.0** |
| 2. Orientación invertida | las mismas T y avances; Q₁₂ con el signo cambiado | **0.0**; rx1 pasa a sumar Q₁₂ |
| 3. Formulación independiente | la referencia en T, G = 500 y 5000 W/K | T a **2.3e-9 K**, n a ≤ 3e-8 mol, Q₁₂ = G(T₁−T₂) |
| 3. dH sin doble conteo | `dH_referencia` = ν·H_f leído aparte, y ≠ dH(T) | — |
| 4. Conservación | energía por volumen y global; con formación; elementos y masa sin las integrales de avance | < 1e-12 en los dos montajes |
| 4. Cancelaciones | `global:energia` cancela `corriente:medio` e `interfaz:it`, conserva las dos fuentes químicas y el calor externo | — |
| 4. Moles que cambian | craqueo: F_sal = F_ent + ξ₁ + ξ₂; la masa no cambia | < 1e-9 |
| 5. Rígido (G = 1e7 W/K, cociente de rigidez 2.3e4) | Radau, BDF, LSODA frente a la referencia | 1.3e-11, 3.6e-11, 9.4e-9 K |
| 6. Transferencia sin perturbar | el temporal se queda | T 3.4e-11 K |
| 6. Escalón desde el estacionario (T alim 350 → 360 K) | la referencia en T desde el estado transferido | 1.5e-9 K |
| 6. Node | `JSON.parse`/`stringify` de la transferencia → `valido` y `resuelto` | — |
| 7. Brutas con neto cero | o ⇌ m con la inversa del equilibrio y alimentación lenta: r⁺ = 1.4183, r⁻ = 1.4182, neto 7e-5 | brutas > 0 |
| 7. Agotamiento | orden cero en rx2: evento a mitad de trayectoria **y** en t = 0⁺ | `parcial` en los dos |
| 7. Límite térmico | Q = 500 kW con dominio hasta 380 K: `dominio_termico` | `parcial` |
| 7. Rechazos | interfaz hacia una corriente, sin G, G negativa, reacción en recipiente, reacción en volumen cerrado, adiabático global con camisa, volumen sin condición externa | 7, con piezas y conexiones |

Y `residuo_terminos` < 1e-12 en todos los balances, GL = 0, y los cuatro
presets dan su estado. Las siete suites de estudios anteriores siguen
verdes.

### 18.4 Ejemplos ejecutados

| Ejemplo | Qué muestra |
|---|---|
| `estudio-reaccion-interfaz` | Dos reactores con interfaz, temporal |
| `estudio-reaccion-interfaz-estacionario` | El mismo montaje en estacionario: arranques, ramas, estabilidad |
| `estudio-reaccion-interfaz-craqueo` | Σν = +1 con interfaz: la salida crece, masa y elementos se conservan |
| `estudio-reaccion-interfaz-cerrado` | Rechazo: reacción en un volumen cerrado |
| `estudio-transferencia-reaccion-interfaz-transferir-*` / `-temporal-*` | La transferencia, con la corrección de redondeo declarada |

Todos los demás ejemplos están regenerados (los de transferencia llevan
`correcciones_de_redondeo`, vacío salvo en el nuevo).

### 18.5 Cambios y migración

| Cambio | Para el frontend |
|---|---|
| Reacción + interfaz **ya no** se rechaza con `LAB_DIN_INTERFAZ_NO_SOPORTADA` | Habilitarla cuando exista la fila `materia+energia+reaccion+interfaz` en `capacidades.combinaciones` |
| Fila nueva en `capacidades.combinaciones`; la de `materia+energia+interfaz` ya no excluye la reacción | Leer por fila |
| `condicion_inicial.comprobaciones.correcciones_de_redondeo` (nuevo, lista, normalmente vacía) | Mostrarlo si no está vacío: es una corrección **declarada** |
| Un evento que llega antes de la primera muestra da `parcial` en vez de un error interno | — |

La firma del objeto transferido cubre el campo nuevo, como todo el objeto.
Un objeto transferido **antes** de esta entrega sigue siendo válido: su
firma se calculó sobre su contenido, sin el campo, y no se recalcula con
él. Las peticiones que no combinan reacción e interfaz no cambian de
resultado ni de `modelo_id`.

### 18.6 Lo que no está

- Volúmenes cerrados con reacción (lote): `/laboratorio/lote`.
- Pared con almacenamiento propio entre los volúmenes.
- Búsqueda exhaustiva de ramas del estacionario (§17.5).
- Momento, transferencia de materia, frontera móvil, cambio de fase y control.

---

## 19. Interfaz de transferencia de materia entre dos compartimentos

Respuesta a `frontend/SIGUIENTE_CLAUDE_TRANSFERENCIA_MATERIA.md`. Solo
backend. Es el **primer hito**: dos compartimentos perfectamente mezclados,
de volumen geométrico fijo, **cerrados** al exterior, isotermos, sin
reacción y sin balance de energía, unidos por una interfaz que deja pasar
**una** especie. Los inventarios de los dos lados se resuelven juntos, en
un único vector de estado. `revision_contrato` pasa a **5** (aditiva;
`schema_version` sigue en 1).

**No está**: la entrega B (transporte + energía), la C (reacción +
transporte selectivo), la D (actividad o potencial químico), compartimentos
con corrientes, ni estacionario. Todo eso se rechaza con un código, citando
la pieza y la conexión.

### 19.1 La ley, confirmada

La que proponía el documento, sin cambios:

$$c_{i,1} = \frac{n_{i,1}}{V_1},\qquad c_{i,2} = \frac{n_{i,2}}{V_2},\qquad
\dot n_{i,12} = L\left(c_{i,1} - \frac{c_{i,2}}{H}\right)$$
$$\frac{dn_{i,1}}{dt} = -\dot n_{i,12},\qquad \frac{dn_{i,2}}{dt} = +\dot n_{i,12}$$

| Símbolo | Qué es | Unidad | Dominio |
|---|---|---|---|
| `L` | conductancia material global (puede ser k·A); es una **tasa total**, no un flujo por área | m3/s (también m3/min, m3/h, L/s, L/min, L/h) | L ≥ 0. L = 0 es un dato; la **ausencia** de L es un error |
| `H` | reparto, c₂,eq = H·c₁,eq | `adimensional` o `(mol/m3)/(mol/m3)` | H > 0. **H = 1 también se declara** |
| `c` | concentración | mol/m3 | — |
| `n` | inventario | mol | n ≥ 0 |
| `V` | volumen geométrico del compartimento | unidades de V | V > 0 |
| `ṅ` | tasa de la interfaz | mol/s | positiva de `desde` a `hacia` |

Es una ley fenomenológica de soluto diluido: no sustituye a un cierre
termodinámico de potencial químico. La respuesta lo declara en
`limitaciones`: coeficientes constantes, equilibrio lineal, una especie
por interfaz (sin difusión cruzada ni transferencia multicomponente), sin
ósmosis, sin electromigración, sin cambio de volumen, isoterma.

**Invertir la conexión.** Con esta convención, la misma física con los
extremos cambiados exige **H' = 1/H y L' = L/H**. Invertir la flecha y
conservar L y H describe otra interfaz (otro equilibrio). La suite
comprueba las dos cosas.

### 19.2 El cierre material: `volumen_fijo` (nuevo)

**Sí se añadió un cierre.** `inventario_constante` (Σn = ρV) no sirve: el
intercambio selectivo cambia los moles de cada compartimento y no hay
corriente que compense, así que mantener Σn fijo sería contradictorio. El
cierre nuevo es:

| Cierre | Parámetros | Qué impone |
|---|---|---|
| `volumen_fijo` | `V` | Nada sobre N: **N = Σᵢ nᵢ es una definición** y cambia. V solo sirve para la concentración. No hay densidad molar total |

- Solo vale en un compartimento **cerrado** con una interfaz de materia.
  En cualquier otro volumen se rechaza (`LAB_DIN_CIERRE_NO_SOPORTADO`).
- `inventario_constante` en un compartimento con interfaz de materia se
  rechaza con el mismo código, citando la conexión.
- Las especies que no cruzan quedan constantes por estructura (dn/dt = 0
  exacto), sin restricción añadida, sin corriente compensatoria y sin
  proyectar estados.
- `capacidades.cierres_de_almacenamiento.volumen_fijo.admite_energia` es
  `false`.

Los cierres existentes no cambian.

### 19.3 La petición (aditiva)

Dos cosas nuevas: una conexión con `tipo: "transferencia_materia"` entre los
dos volúmenes y la lista `interfaces_materiales`. Es el ejemplo
`interfaz-material`:

```json
{
  "componentes": ["water", "acetic acid"],
  "bloques": [
    {"id": "cv1", "tipo": "recipiente", "nombre": "Compartimento 1"},
    {"id": "cv2", "tipo": "recipiente", "nombre": "Compartimento 2"}
  ],
  "conexiones": [
    {"id": "im", "desde": "cv1", "hacia": "cv2", "tipo": "transferencia_materia"}
  ],
  "supuestos": {"sinReaccion": true},
  "especificaciones": [],
  "almacenamiento": [
    {"bloque_id": "cv1", "cierre": "volumen_fijo", "V": {"valor": 0.001, "unidad": "m3"}},
    {"bloque_id": "cv2", "cierre": "volumen_fijo", "V": {"valor": 0.002, "unidad": "m3"}}
  ],
  "interfaces_materiales": [
    {"conexion_id": "im", "especie": "acetic acid",
     "conductancia": {"valor": 1e-6, "unidad": "m3/s"},
     "reparto": {"valor": 2.0, "unidad": "adimensional"}}
  ],
  "estudio": {"version": 1, "tipo": "temporal",
              "condiciones_iniciales": [
                {"bloque_id": "cv1", "componente": "water", "magnitud": "n", "valor": 55.0, "unidad": "mol"},
                {"bloque_id": "cv1", "componente": "acetic acid", "magnitud": "n", "valor": 0.1, "unidad": "mol"},
                {"bloque_id": "cv2", "componente": "water", "magnitud": "n", "valor": 110.0, "unidad": "mol"},
                {"bloque_id": "cv2", "componente": "acetic acid", "magnitud": "n", "valor": 0.0, "unidad": "mol"}],
              "tiempo": {"final": 12000.0, "unidad": "s", "muestras": 81}}
}
```

- `especie`: el identificador tal como está en `componentes`, o su CAS
  (`"64-19-7"`). Nunca se deduce del nombre ni de la fórmula: `"C2H4O2"` se
  rechaza.
- Una entrada por conexión. Una segunda entrada para la misma conexión (otra
  especie) se rechaza: en esta entrega no hay transferencia multicomponente.
- Una sola interfaz de materia por par de volúmenes.
- No hay alimentación ni escalones: el estudio es el estado inicial y el
  horizonte.
- Sin `modelo_energetico`: el alcance es isotermo. T no entra en las
  ecuaciones y no se calcula ningún calor. **Este modelo no demuestra
  conservación de energía.**

### 19.4 La respuesta

Campos nuevos o que cambian (todos aditivos):

| Campo | Contenido |
|---|---|
| `fisica` | `["materia", "transferencia_materia"]` |
| `interfaces_materiales[]` | `conexion_id`, `desde`, `hacia`, `componente`, `cas`, `L` + `unidad_L`, `H` + `unidad_H`, `ley`, `convencion`, `equilibrio`, `inversion`, `limitaciones` |
| `modelo.variables` | `{vol}.c{i}` (algebraica, mol/m3) de la especie que cruza; `{conexion}.L` y `{conexion}.H` (parámetros); `{conexion}.tasa` (algebraica, mol/s, con `conexion_ids`); `{vol}.V` (parámetro); `{vol}.N` algebraica (definición) |
| `modelo.ecuaciones` | `{vol}:concentracion_{i}` (c = n/V); `{conexion}:ley_transferencia`; `{vol}:inventario_total` (N = Σn) |
| balances `{vol}:materia_especie_{i}` | término `rol: "transferencia"`: signo −1 en `desde`, +1 en `hacia`, `clave: "transferencia:{conexion}"`, `conexion_id` y `bloque_id` del otro lado. Las especies que no cruzan no tienen términos (`dn/dt = 0`) |
| `global:materia_especie_{i}` | la transferencia aparece en `cancelaciones` y no en `terminos` |
| `modelo.clasificacion` | `tipo_sistema: "ODE"`, GL = 0, `restricciones: []`, y un bloque `interfaces_materiales` con la ley, el signo, el cierre, `isotermo`, `modo_conservado` y `limitaciones` |
| `resultados.series` | `{vol}.c{i}` (mol/m3) de los dos lados y `{conexion}.tasa` (mol/s, con `convencion`) |
| `conservacion.transferencia_materia` | ver §19.6 |
| `constantes_de_tiempo` | una entrada `tipo: "transferencia_materia"` con τ = 1/[L(1/V_desde + 1/(H·V_hacia))], exacta y constante (`null` si L = 0) |
| `contraste_estacionario` | `tipo: "limite_con_total_conservado"`: ver §19.5 |
| `integracion.rigidez.horizonte_en_constantes_rapidas` | **nuevo en todas las respuestas temporales**: t_final × max\|Re λ\|. Con un solo modo el cociente de rigidez es 1, y este número es el que dice cuántos pasos necesitaría un método explícito |
| `integracion.atol` | con interfaz de materia, además `inventarios_por_estado_mol` y `criterio_inventarios` (ver §19.7) |

### 19.5 El estacionario: indeterminado, y el temporal da su límite

**No se cambiaron las condiciones del estacionario** de ningún montaje
anterior. Para esta combinación:

- **Estacionario** → `invalido`, `LAB_DIN_ESTACIONARIO_INDETERMINADO`,
  citando el compartimento y la conexión. Hay una familia de equilibrios
  (cualquier reparto con c_hacia = H·c_desde lo es); cuál se alcanza lo fija
  el total conservado del estado inicial, y sin ese total el motor no elige
  uno. Pasa lo mismo en `/validar`.
- **No se admite un total impuesto** en esta entrega. El documento lo dejaba
  como opción y el primer hito no lo necesita.
- **Transferencia estacionario → temporal**: deshabilitada, porque no hay un
  origen único. `/transferir` responde `invalido` con
  `LAB_DIN_TRANSFERENCIA_NO_POSIBLE`, y la fila de `capacidades` dice
  `"no: ..."`.
- **Temporal**: `contraste_estacionario` compara el final de la trayectoria
  con el límite que fija el total conservado del estado inicial,
  n₁,eq = N·V₁/(V₁ + H·V₂). Ese límite se calcula aparte, no integrando. La
  respuesta trae `limite` (por volumen y especie), `condicion` y
  `alcanzado`, y la `conclusion` advierte que **no** es un estacionario
  único. La clasificación declara el modo conservado (autovalores cero): no
  hay estabilidad asintótica en esas direcciones.

### 19.6 Lo que se mide en la conservación

`conservacion.transferencia_materia`:

| Campo | Qué mide |
|---|---|
| `residuo_especie_global_max` | deriva del total de cada especie |
| `especies_impermeables[]` + `residuo_impermeables_max` | cuánto cambió cada especie que no cruza, en cada compartimento (cero exacto) |
| `elementos_y_masa` | residuo elemental y de masa globales; las fórmulas salen de la identidad por CAS (`chemicals`), sin exigir el proveedor termodinámico |
| `interfaces[]` | lo que cruzó (mol, con signo) por cada conexión |
| `cumple` | todo ≤ 1e-7 |

`conservacion.por_volumen[].residuo_integrado_max` incluye ahora la
integral de la tasa (con `interfaces_materiales` en la entrada).
`residuo_instantaneo_max` se escala con la tasa de la interfaz cuando no
hay alimentación.

**Cierre del ensamblaje ≠ precisión.** Estos residuos dan cero por
construcción: la misma tasa resta en un balance y suma en el otro. La
precisión se mide aparte, contra la solución analítica (§19.8). La suite lo
demuestra: con RK45 y `rtol = 1e-3` la especie sigue conservándose al
redondeo, mientras el error frente a la analítica sube a 8e-4.

### 19.7 Una corrección numérica que salió al verificar

El `atol` de los inventarios se escalaba con el inventario **total** del
montaje. Con un soluto diluido en trazas eso deja el soluto sin precisión:
un atol de ~1e-10 mol sobre 1e-9 mol de soluto daba un **3 %** de error
frente a la analítica. Ahora, **solo cuando hay una interfaz de materia**,
cada especie usa como escala su propio total inicial. El evento de dominio
(n < 0) usa la misma escala. Con eso, el soluto en trazas queda a 2e-11.
Sin interfaz de materia la escala es la de siempre, y **ningún resultado
anterior cambia**.

### 19.8 Lo verificado

`tests/validar_estudios_interfaz_material.py`, **116 comprobaciones**. La
referencia es la solución cerrada escrita en la suite, fuera del motor.

| Validación del documento | Cómo | Medido |
|---|---|---|
| 1. Analítica: inventarios, tasa, τ y límite | serie contra n(t) = n_eq + (n₀ − n_eq)·e^(−t/τ) | 2.0e-11 (rel. a N); τ exacta; límite = n_eq |
| 2. L = 0 | inventarios y tasa | constantes **exactas**; τ = `null` |
| 2. Fuerza impulsora cero con c₁ ≠ c₂ | c₁ = 100 y c₂ = 200 mol/m3 con H = 2 | tasa 0.0; nada cruza |
| 3. Conservación | especie, impermeables, elementos (C, H, O) y masa | 5e-19, **0.0**, 7e-19, 1e-18 |
| 3. Cierre ≠ precisión | RK45 con rtol 1e-3 | conservación al redondeo; error 8e-4 |
| 4. Inversión con H' = 1/H y L' = L/H | trayectoria y tasa | diferencia 0.0; tasa de signo opuesto |
| 4. Inversión conservando L y H | límite | otro (diferencia 0.31 de N) |
| 5. Volúmenes 1:1000, receptor vacío, trazas (1e-9 mol) | contra la analítica | 1.5e-11, 2.0e-11, 2.0e-11 |
| 5. L alta (τ = 0.08 s, 1250 τ en el horizonte) | Radau, BDF, LSODA y RK45 contra la analítica | 2.7e-12, 2.0e-10, 8.7e-12, 5.1e-11 |
| 5. L = 1e-12 (τ ≈ 8e8 s) | contra la analítica | 1.3e-14 |
| 5. Positividad | mínimo de todas las series | ≥ 0 |
| 6. Rechazos | 22 casos más `/transferir`, con pieza y conexión | ver §19.9 |
| 7. Persistencia | JSON de Python y de Node (`JSON.parse`/`stringify`) | mismo `modelo_id` y mismas series; la petición no se muta |
| 7. Identidad por conexión | renombrar `im` → `membrana` | variables `membrana.*` |
| 7. Términos opuestos y cancelación | −tasa en cv1, +tasa en cv2; global sin términos | `residuo_instantaneo_max` = **0.0** exacto |
| Montajes anteriores | `modelo_id` de 4 ejemplos y una condición transferida antigua | idénticos; la condición sigue `resuelto` |

La suite completa de `run_tests.py` está en verde (§19.11).

### 19.9 Códigos

| Situación | Código | Estado |
|---|---|---|
| Interfaz de materia hacia una corriente (u otra pieza que no es volumen) | `LAB_PUERTO_INCOMPATIBLE` | `invalido` |
| Compartimento con corrientes, con energía, con reacción o con interfaz térmica | `LAB_DIN_INTERFAZ_MATERIAL_NO_SOPORTADA` (**nuevo**) | `no_soportado` |
| `inventario_constante` con interfaz de materia; `volumen_fijo` sin interfaz de materia; cierre de salida en un cerrado | `LAB_DIN_CIERRE_NO_SOPORTADO` | `invalido` |
| L o H sin unidad o con una unidad no admitida | `LAB_UNIDAD_INCOMPATIBLE` | `invalido` |
| L ausente; conexión sin declarar en `interfaces_materiales` | `LAB_FALTA_ESPECIFICACION` | `invalido` |
| L < 0, H ≤ 0, V ≤ 0, inicial negativa | `LAB_VALOR_FUERA_DE_DOMINIO` | `invalido` |
| Especie que no está en el montaje (o dada por fórmula) | `LAB_COMPONENTE_NO_DISPONIBLE` | `invalido` |
| Dos especies por la misma interfaz | `LAB_ESPECIFICACION_DUPLICADA` | `invalido` |
| Dos interfaces de materia entre el mismo par | `LAB_TOPOLOGIA_NO_SOPORTADA` | `invalido` |
| Estacionario | `LAB_DIN_ESTACIONARIO_INDETERMINADO` | `invalido` |
| `/transferir` | `LAB_DIN_TRANSFERENCIA_NO_POSIBLE` | `invalido` |

Cada diagnóstico cita en `conexion_ids` la conexión afectada, salvo los que
son solo de un volumen (V ≤ 0, inicial negativa, cierre de salida en un
cerrado).

### 19.10 Identidad, `capacidades` y migración

- **`modelo_id`** incluye el `tipo` de la conexión cuando es `termica` o
  `transferencia_materia`, e `interfaces_materiales` cuando existen. Los
  `modelo_id` de los montajes anteriores **no cambian** (la suite lo
  comprueba). Cambian con L, H, la especie o la orientación.
- **Huellas por elemento** (`condicion_inicial.huellas`): una conexión de
  materia lleva la marca `material` y aparece la parte
  `interfaces_materiales`. Las huellas de antes no cambian, y las
  condiciones transferidas de la entrega anterior siguen siendo válidas.
- **`capacidades`**:
  - fila nueva `materia+interfaz_material`: solo `temporal`, con
    `transferencia_estacionario_a_temporal: "no: ..."`;
  - `fisica.transferencia_de_materia_entre_volumenes: true`;
  - sección `interfaces_materiales` con la declaración, la ley, las
    unidades, la inversión, lo que requiere y las limitaciones;
  - `volumenes_cerrados.requiere` contempla el caso sin energía;
  - `cierres_de_almacenamiento.volumen_fijo`.

  **Ninguna otra fila** habilita la interfaz de materia: no se activa por
  suma de capacidades.
- **Corrección de `capacidades.no_soportado`**: listaba todavía «transferencia
  de estacionario a condición inicial», que existe desde §17. Se ha quitado
  y en su lugar figura «transferencia de materia con energía, reacción o
  corrientes».
- **`revision_contrato` = 5.** Las condiciones transferidas nuevas llevan 5
  en `origen.revision_contrato`. Las antiguas, con 4, siguen valiendo.

| Cambio | Para el frontend |
|---|---|
| Conexión `tipo: "transferencia_materia"` + `interfaces_materiales` | Habilitarlas cuando exista la fila `materia+interfaz_material` en `capacidades.combinaciones`; solo con estudio temporal |
| Cierre `volumen_fijo` | Ofrecerlo solo en compartimentos cerrados con interfaz de materia |
| `interfaces_materiales[]` en la respuesta | Mostrar L, H, la especie y la convención tal como vienen |
| Series `{vol}.c{i}` y `{conexion}.tasa` | Graficarlas por id; no calcular c ni la tasa en el cliente |
| `contraste_estacionario.tipo = "limite_con_total_conservado"` | Mostrar el límite como condicional al estado inicial, no como «el estacionario» |
| `rigidez.horizonte_en_constantes_rapidas` | Opcional: dato para juzgar el integrador |

No se exige al frontend ningún cálculo, elección de integrador ni
corrección física.

### 19.11 Ejemplos ejecutados

Generados ejecutando los endpoints con `tests/generar_ejemplos_estudios.py`
(petición y respuesta en `docs/ejemplos/`):

| Ejemplo | Qué muestra | Estado |
|---|---|---|
| `estudio-interfaz-material` | El montaje de §19.3, 15 τ: límite alcanzado | `resuelto` |
| `estudio-interfaz-material-reparto` | c₂ = H·c₁ al empezar con c₁ ≠ c₂: nada cruza | `resuelto` |
| `estudio-interfaz-material-rigida` | L = 1e-2 m3/s con Radau | `resuelto` |
| `estudio-interfaz-material-estacionario` | Estacionario indeterminado | `invalido` |
| `estudio-interfaz-material-inventario-constante` | Cierre contradictorio | `invalido` |
| `estudio-interfaz-material-energia` | Combinación no verificada | `no_soportado` |
| `estudio-interfaz-material-sin-unidad` | H sin unidad | `invalido` |
| `estudio-transferencia-interfaz-material-transferir-*` | `/transferir` rechazado | `invalido` |

Todos los demás ejemplos están regenerados. Fuera de esta combinación el
cálculo no cambia: lo nuevo en esas respuestas es aditivo
(`revision_contrato: 5`, el `capacidades` ampliado y
`horizonte_en_constantes_rapidas`), y las suites anteriores, que las
comparan con sus soluciones analíticas, siguen en verde.

Suites: `python run_tests.py` → **29 suites en verde**, incluida la nueva.
Dos suites anteriores comprobaban `revision_contrato == 4`; ahora comprueban
`>= 4`.

### 19.12 Lo que no está (entregas posteriores)

- **B**: transporte material + energía, con la entalpía del material
  transferido, su orientación y su referencia; calor sensible y químico sin
  doble conteo.
- **C**: reacción + transporte selectivo, con la cinética acoplada y sus
  restricciones.
- **D**: actividad o potencial químico y equilibrio no ideal con el
  proveedor.
- Compartimentos con corrientes, más de una especie por interfaz, más de dos
  volúmenes, estacionario con total impuesto y la transferencia
  estacionario → temporal para esta combinación.

Cada una necesitará su propia fila en `capacidades`, su contrato y sus
referencias.

---

## 20. Transferencia selectiva de materia + energía

Respuesta a `frontend/SIGUIENTE_CLAUDE_TRANSFERENCIA_MATERIA_ENERGIA.md`.
Solo backend. `revision_contrato` pasa a **6** (aditiva; `schema_version`
sigue en 1).

**Estado de los dos hitos:**

| Hito | Estado |
|---|---|
| **A**: modelo energético sencillo con propiedades declaradas | **completado y verificado** |
| **B**: propiedades del proveedor | **no disponible**: se comprobó qué ofrece el proveedor y falta lo que haría falta (§20.8). Se rechaza con un diagnóstico que dice qué falta, y la capacidad queda en `false` |

La reacción con transferencia de materia sigue rechazada. Ninguna capacidad
se habilita por suma de otras.

### 20.1 La decisión física, antes del código

Las cuatro preguntas del documento, respondidas:

**1. U(n, T), referencia y dominio.**

$$u_i(T) = u_{i,ref} + c_{v,i}\,(T - T_{ref}),\qquad
U_k = \sum_i n_{i,k}\,u_i(T_k) + C_{w,k}\,(T_k - T_{ref})$$

| Qué | Origen |
|---|---|
| `c_v,i` por especie | **declarado**. Capacidad a volumen constante: el compartimento es rígido y lo que se almacena es U |
| `u_ref,i` por especie | **declarada**; un cero también se declara |
| `T_referencia` | **declarada**, común a todas las especies |
| `dominio_T` | **declarado**; sus bordes son evento terminal |
| `C_w` (pared) | opcional, como en §14 |
| T | **calculada** por la inversión explícita de U (índice 1, C > 0) |

No hay densidad: el cierre `volumen_fijo` de §19 no la usa, y no se
impone Σn = ρV.

**2. La energía que transporta la especie.** El cierre elegido es el
**estado del donante**:

$$\dot E_{12} = \dot n_{12}\; u_s(T_{donante}),\qquad T_{donante} =
\begin{cases} T_1 & \dot n_{12} \ge 0 \\ T_2 & \dot n_{12} < 0\end{cases}$$

- E₁₂ se usa **exactamente** como −E₁₂ en el origen y +E₁₂ en el destino.
- Lleva la **misma referencia** u_ref,s que lo almacenado.
- Mezcla ideal: la energía molar parcial es la de la especie pura. Es un
  supuesto declarado (sin energía de exceso), no algo que se deduzca.

**3. Trabajo de flujo, presión y volumen parcial.** Es una aproximación de
**soluto diluido**: el volumen molar parcial de la especie que cruza se
desprecia (v̄ₛ ≈ 0). En consecuencia:

- no hay trabajo de flujo P·v̄ₛ ni cambio de presión;
- hₛ = uₛ, y por eso c_p = c_v para la especie que cruza.

**No es rigurosa, y se declara así** en `propiedades.aproximacion`, en los
`terminos_descartados` del balance de energía y en `capacidades`. Sin ella,
con V fijo y N variable, la presión de un líquido rígido no estaría
definida.

**4. El cierre de volumen.** Es `volumen_fijo` (§19.2), sin cambios: V
geométrico y N libre. No hay corrientes compensatorias, ni expansión, ni
proyección. El modelo `ideal_incompresible` **no** se extiende. Con
interfaz de materia se rechaza, porque exige inventario constante, y su
densidad no se usa como compensación.

**Consecuencias verificables del cierre por donante** (comprobadas en
§20.6):

- **El donante conserva su T.** Pierde la especie a su propia T:
  C·dT/dt = −ṅ·uₛ(T) + ṅ·uₛ(T) = 0.
- **Con T₁ = T₂ ninguna T cambia**, aunque la especie y su energía crucen.
- **El receptor se calienta o se enfría hacia el donante:**
  C₂·dT₂/dt = ṅ·c_v,s·(T₁ − T₂). Es el calor sensible de mezcla, sin
  conducción implícita.
- **No hay intercambio bruto bidireccional.** E₁₂ sale solo del neto: a
  neto cero no se inventan brutas.

**Cruce de signo.** E₁₂ es continua en ṅ = 0 (los dos lados dan 0), y su
derivada salta de uₛ(T₁) a uₛ(T₂) si T₁ ≠ T₂.

- Con L y H constantes, ṅ(t) = ṅ(0)·e^(−t/τ): la tasa **no cambia de
  signo**. El integrador adaptativo no necesita tratar el salto aparte; si
  el flujo empieza en un sentido, sigue en él.
- Un cruce real exigiría L o H dependientes del estado, y eso queda fuera
  de este hito.
- La suite comprueba la continuidad y el salto sobre la evaluación del
  propio motor.

**Conducción térmica.** No hay conducción implícita. Una interfaz térmica
G(T₁ − T₂) es una **conexión separada**, con su propio término Q₁₂, su
propia conexión y su propia cancelación; no se duplica con E₁₂. Es una
combinación verificada propia (fila aparte en `capacidades`).

**Modos térmicos exteriores admitidos:** Q impuesto (fuente de calor) y
adiabático. La **T impuesta se rechaza**: el calor que la mantendría con
transferencia de materia no está formulado ni verificado en este hito.

### 20.2 La petición (aditiva)

El montaje de §19.3, con `modelo_energetico` de tipo nuevo, el
almacenamiento energético de cada compartimento y T inicial. Es el
ejemplo `interfaz-material-con-energia`:

```json
"modelo_energetico": {
  "tipo": "ideal_volumen_fijo",
  "cv": [{"componente": "water", "valor": 75.0, "unidad": "J/(mol*K)"},
         {"componente": "acetic acid", "valor": 120.0, "unidad": "J/(mol*K)"}],
  "u_referencia": [{"componente": "water", "valor": 0.0, "unidad": "J/mol"},
                   {"componente": "acetic acid", "valor": 0.0, "unidad": "J/mol"}],
  "T_referencia": {"valor": 298.15, "unidad": "K"},
  "dominio_T": {"min": 273.15, "max": 373.15, "unidad": "K"}
},
"almacenamiento": [
  {"bloque_id": "cv1", "cierre": "volumen_fijo", "V": {"valor": 0.001, "unidad": "m3"},
   "energia": {"modelo": "solo_fluido", "adiabatico": true}},
  {"bloque_id": "cv2", "cierre": "volumen_fijo", "V": {"valor": 0.002, "unidad": "m3"},
   "energia": {"modelo": "solo_fluido", "adiabatico": true}}
],
"estudio": {"condiciones_iniciales": [ "... n por especie ...",
  {"bloque_id": "cv1", "magnitud": "T", "valor": 340.0, "unidad": "K"},
  {"bloque_id": "cv2", "magnitud": "T", "valor": 300.0, "unidad": "K"}]}
```

- `u_referencia` admite J/mol, kJ/mol, kJ/kmol y J/kmol; `cv`, las unidades
  de c_p de §14.
- Una entrada de `u_referencia` puede llevar su propia `T_referencia`. Si
  difiere de la del modelo, son **referencias mezcladas** y se rechaza.
- `densidad_molar` o `cp` en este modelo se rechazan
  (`LAB_ESPECIFICACION_EXCLUYENTE`).
- `presion_sistema` se dice no usada.
- Calor exterior: una pieza `calor` conectada al compartimento con su `Q`
  especificado, como en §14. Interfaz térmica: una conexión
  `tipo: "termica"` aparte y `interfaces_termicas`, como en §16.

### 20.3 La respuesta

Todo es aditivo. Lo que cambia con este modelo:

| Campo | Contenido |
|---|---|
| `fisica` | `["materia", "energia", "transferencia_materia"]` |
| `propiedades` | `tipo: "ideal_volumen_fijo"`, `cv`, `u_referencia`, `T_referencia`, `dominio_T`, `origen`, `energia_transportada`, `aproximacion`, `mezcla`, `fase`, `densidad` |
| `modelo.variables` | `fluido.cv{i}`, `fluido.u_referencia{i}` y `fluido.T_referencia` (parámetros); `{vol}.U` diferencial; `{vol}.T` algebraica; **`{conexion}.E`** (algebraica, W, con `conexion_ids`). No hay `fluido.densidad_molar` ni `sistema.p` |
| `modelo.ecuaciones` | **`{conexion}:energia_transferida`** (la ley por donante); `{vol}:energia` con término `rol: "transferencia_energia"`, −1 en `desde` y +1 en `hacia`, `clave: "energia_transferida:{conexion}"`; descartado `trabajo_de_flujo_de_la_especie_transferida` |
| `global:energia` | E₁₂ (y Q₁₂ si hay interfaz térmica) en `cancelaciones`; un Q exterior permanece en `terminos` |
| `clasificacion.energia` | además `transporte`, `geometria`, **`ecuacion_en_T`** (con el término composicional Σᵢ uᵢ dnᵢ/dt) y `cruce_de_signo` |
| `resultados.series` | `{vol}.U`, `{vol}.T`, `{vol}.capacidad_termica` y **`{conexion}.E`** (W, con `convencion`), además de las de §19 |
| `conservacion.energia` | por compartimento con la integral de E₁₂; `interfaces[]` con una entrada `tipo: "energia_transportada_por_la_especie"` y su `energia_transferida_J` |
| `contraste_estacionario` | además **`limite_termico`** (§20.5) |

### 20.4 Cierres, estacionario y transferencia de origen

- **Cierre**: `volumen_fijo`, sin cambios (§19.2). `capacidades` lo dice:
  `cierres_de_almacenamiento.volumen_fijo.admite_energia: true` con
  `modelos_energeticos: ["ideal_volumen_fijo"]`.
- **Estacionario**: indeterminado, `LAB_DIN_ESTACIONARIO_INDETERMINADO`.
  Hay una familia fijada por los totales de especie (y por el de energía si
  es adiabático). No se elige total, temperatura ni rama.
- **Transferencia estacionario → temporal**: deshabilitada
  (`LAB_DIN_TRANSFERENCIA_NO_POSIBLE`).
- **No cambian las condiciones del estacionario** de ningún montaje
  anterior.

### 20.5 El límite condicionado del temporal

`contraste_estacionario.tipo = "limite_con_total_conservado"`. El límite
material es el de §19.5. `limite_termico` depende del caso:

| Caso | Límite térmico |
|---|---|
| Hay Q exterior distinto de cero en algún tramo | **ninguno**: `T: null` con el motivo |
| Interfaz térmica G > 0, sin Q | T común: Σₖ Uₖ(n_lim,k, T) = U_total(0), lineal en T |
| Sin interfaz térmica, sin Q | el donante (signo de ṅ(0)) conserva su T, y el receptor recibe la U que falta |
| ṅ(0) = 0 y sin interfaz térmica | la T inicial de cada compartimento |

`alcanzado` exige además que la distancia en T sea ≤ 1e-6 K. Es un límite
**condicionado** a los totales iniciales, no un estacionario único. La
clasificación declara los modos conservados, y no se promete estabilidad
asintótica en ellos.

### 20.6 Lo verificado

`tests/validar_estudios_interfaz_material_energia.py`, **96
comprobaciones**. La referencia es la física escrita **en T**, con el
término composicional

$$C_k\frac{dT_k}{dt} = \frac{dU_k}{dt} - \sum_i u_i(T_k)\frac{dn_{i,k}}{dt}$$

e integrada aparte (Radau, rtol 1e-12, atol por componente). Se comparan
inventarios, T, U y E, no solo el residuo global.

| Validación del documento | Cómo | Medido |
|---|---|---|
| 1. L = 0 adiabático | n, U y T | constantes **exactas** |
| 1. L = 0 con G = 5 W/K | contra la analítica de dos cerrados (τ = 1/[G(1/C₁ + 1/C₂)]) | < 1e-6 K |
| 1. L = 0 con Q = 20 W | U₁ = U₁(0) + Q·t, U₂ constante | < 1e-6 J |
| 2. T común (320 K) | la especie y su energía cruzan | ninguna T cambia (< 1e-9 K) |
| 3. Referencia en T | base, con G, con Q, con pared y c_v distintos | n ≤ 6e-13, T ≤ 1.3e-9 K, U ≤ 3e-11, E ≤ 3e-11 |
| 3. Capacidad fija sin término composicional | la misma U con C(0) fija | **no** reproduce T₂ (0.24 K de error): el término importa |
| 4. Conservación | especie, impermeables, elementos, masa y energía (global y por compartimento) | < 1e-12; impermeables 0.0; instantáneo de energía **0.0** |
| 4. Cierre ≠ precisión | RK45 con rtol 1e-3 | energía cerrada al redondeo; T₂ a 1.2e-2 K de la referencia |
| 5. Offsets por especie (−2.8e5 y −4.8e5 J/mol) | trayectoria | T idéntica (3e-12 K); U cambia en Σnᵢ·Δuᵢ y E en ṅ·Δuₛ |
| 5. Otra T_referencia (350 K) con u_ref coherente | T y U | idénticas |
| 6. Inversión con H' = 1/H y L' = L/H | n, T, tasa y E | n y T iguales (< 1e-8); tasa y E de signo opuesto |
| 6. Inversión sin transformar | T₂ | otra física (> 0.1 K) |
| 7. Flujo de cv2 a cv1 | el donante cv2 | conserva su T; contra la referencia, 6e-11 K |
| 7. Signo de la tasa | serie | no cambia en ninguna trayectoria |
| 7. Cruce por cero | evaluando el motor con ṅ = ±1e-6, ±1e-9, ±1e-12 | E lineal en ṅ y → 0 por los dos lados; E/ṅ = uₛ(T₁) a un lado y uₛ(T₂) al otro |
| 8. Soluto en trazas (1e-9 mol) | referencia en T | T 2e-12 K |
| 8. L = 1e-2 (τ = 0.08 s) | Radau, BDF, LSODA contra la referencia | T ≤ 6.2e-10 K |
| 8. Receptor sin inventario con pared | referencia | 2.7e-10 K |
| 8. Dominio limitado con Q = 2 kW | evento | `dominio_termico`, `parcial` |
| 8. Evento antes de la primera muestra | T₀ al borde | `parcial`, no un fallo |
| 8. Vaciado o agotamiento | el donante tiende a n_eq > 0 y el disolvente no cruza | no alcanzable en este hito (se comprueba) |
| 9. Rechazos | 21 casos más `/transferir` | ver §20.7 |
| 10. Persistencia | Node `JSON.parse`/`stringify`, no mutación | mismo `modelo_id` y mismas series |
| 10. Cancelaciones | global de energía (E₁₂, Q₁₂), Q exterior que permanece, global de materia | correctas; `residuo_terminos` < 1e-12 |
| 10. `modelo_id` anteriores | el isotermo de §19 y 3 de antes | intactos |

### 20.7 Códigos

| Situación | Código | Estado |
|---|---|---|
| `proveedor_liquido` con interfaz de materia (**hito B**) | `LAB_DIN_MODELO_ENERGETICO_NO_SOPORTADO`, con lo que falta en el mensaje | `no_soportado` |
| `ideal_incompresible` con interfaz de materia | `LAB_DIN_MODELO_ENERGETICO_NO_SOPORTADO` | `no_soportado` |
| `ideal_volumen_fijo` en volúmenes con corrientes o inventario constante | `LAB_DIN_MODELO_ENERGETICO_NO_SOPORTADO` | `no_soportado` |
| T impuesta en un compartimento | `LAB_DIN_MODELO_ENERGETICO_NO_SOPORTADO` | `no_soportado` |
| Reacción; interfaz térmica sin energía | `LAB_DIN_INTERFAZ_MATERIAL_NO_SOPORTADA` | `no_soportado` |
| `c_v`, `u_referencia`, `T_referencia` o `dominio_T` ausente | `LAB_DIN_PROPIEDAD_FALTANTE` | `invalido` |
| Referencias mezcladas | `LAB_DIN_PROPIEDADES_INCOHERENTES` | `invalido` |
| `densidad_molar` o `cp` en `ideal_volumen_fijo` | `LAB_ESPECIFICACION_EXCLUYENTE` | `invalido` |
| Unidad ausente o no admitida | `LAB_UNIDAD_INCOMPATIBLE` | `invalido` |
| c_v ≤ 0 | `LAB_VALOR_FUERA_DE_DOMINIO` | `invalido` |
| `inventario_constante` con interfaz de materia | `LAB_DIN_CIERRE_NO_SOPORTADO` (cita la conexión) | `invalido` |
| Sin T inicial; sin modo térmico | `LAB_DIN_CONDICION_INICIAL_FALTANTE`; `LAB_FALTA_ESPECIFICACION` | `invalido` |
| Compartimento sin inventario ni pared (capacidad cero) | `LAB_DIN_INVERSION_U_IMPOSIBLE` (**nuevo control** al leer las iniciales, válido para cualquier volumen con energía) | `invalido` |
| Interfaz hacia una corriente | `LAB_PUERTO_INCOMPATIBLE` | `invalido` |
| Estacionario; `/transferir` | `LAB_DIN_ESTACIONARIO_INDETERMINADO`; `LAB_DIN_TRANSFERENCIA_NO_POSIBLE` | `invalido` |

### 20.8 Hito B: comprobado, no disponible

Lo que tiene el proveedor (`thermodynamics/proveedor.py`):

- c_p de cada **líquido puro**;
- densidad de cada líquido puro (y la de mezcla por Amagat);
- coeficientes de actividad UNIFAC γ(T, x);
- propiedades de formación.

Lo que **no** tiene, y B necesita:

1. **La entalpía (o energía) molar parcial** de la especie que cruza, o la
   de exceso. UNIFAC da γ, pero no hᴱ validada. Sustituirla por la del
   líquido puro sería una aproximación no declarada.
2. **Una relación de volumen coherente** con V fijo y N variable:
   volúmenes molares parciales y una presión. Las densidades de puros más
   Amagat no cierran el sistema con un volumen rígido.
3. **Una referencia independiente** del proveedor con la que validarlo:
   calorimetría o una cuadratura con dominio y fases declarados. Llamar
   dos veces al mismo endpoint no lo es.

Por eso `proveedor_liquido` con interfaz de materia se rechaza con el
diagnóstico que lo enumera, y
`capacidades.interfaces_materiales.hito_B_proveedor` dice
`disponible: false` con esa lista.

### 20.9 Capacidades y migración

- **Filas nuevas** en `capacidades.combinaciones`, las dos solo
  `temporal` y sin transferencia de origen:
  - `materia+energia+interfaz_material`;
  - `materia+energia+interfaz_material+interfaz_termica`.

  Cada una trae `modelo_energetico`, `energia_transportada`,
  `aproximacion`, `contraste`, `limitaciones` y `no_soportado`.
- **Otros cambios en `capacidades`:**
  - `materia+interfaz_material` (isoterma) ya no lista la energía como no
    soportada: remite a su fila;
  - `fisica.transferencia_de_materia_con_energia: true`;
  - `interfaces_materiales.energia` y `interfaces_materiales.hito_B_proveedor`;
  - `modelos_energeticos.ideal_volumen_fijo`.

  Ninguna fila combina interfaz de materia con reacción.
- **`modelo_id`**: los montajes que no piden la física nueva conservan el
  suyo, incluido el isotermo de §19 (comprobado).
- **Un cambio de resultado en §19**: el ejemplo
  `interfaz-material-energia` (con `ideal_incompresible`) sigue siendo
  `no_soportado`, pero su código pasa de
  `LAB_DIN_INTERFAZ_MATERIAL_NO_SOPORTADA` a
  `LAB_DIN_MODELO_ENERGETICO_NO_SOPORTADO`, porque ahora la causa es el
  modelo y no la combinación. La suite de §19 se ajustó a ello.

| Cambio | Para el frontend |
|---|---|
| `modelo_energetico.tipo = "ideal_volumen_fijo"` | Ofrecerlo solo con compartimentos `volumen_fijo` e interfaz de materia, cuando exista la fila en `capacidades` |
| `cv` y `u_referencia` por especie | Pedirlos explícitamente; sin valores por omisión |
| Series `{conexion}.E`, `{vol}.T`, `{vol}.U` | Graficarlas por id; no calcular E, T ni U en el cliente |
| `contraste_estacionario.limite_termico` | Mostrarlo como condicionado a los totales iniciales; `T: null` con su motivo si no hay límite |
| Fila con interfaz térmica | Habilitar la conexión `termica` junto a la material solo con energía |

No se mueve al frontend ningún cálculo de propiedades, de energía
transferida, de estabilidad ni de integración.

### 20.10 Ejemplos ejecutados

| Ejemplo | Qué muestra | Estado |
|---|---|---|
| `estudio-interfaz-material-con-energia` | Adiabático: el donante a 340 K no cambia y el receptor sube hasta el límite | `resuelto` |
| `estudio-interfaz-material-con-energia-e-interfaz-termica` | E₁₂ y Q₁₂ separados; T común final | `resuelto` |
| `estudio-interfaz-material-con-energia-calor` | Q = 50 W: la fuente queda en el global; sin límite térmico | `resuelto` |
| `estudio-interfaz-material-con-energia-temperatura-comun` | T₁ = T₂: nada cambia de T | `resuelto` |
| `estudio-interfaz-material-con-energia-proveedor` | Hito B: rechazo con lo que falta | `no_soportado` |
| `estudio-interfaz-material-energia` | `ideal_incompresible` rechazado (código nuevo) | `no_soportado` |

Todos los demás ejemplos están regenerados.

### 20.11 Lo que no está

- El hito B (§20.8).
- T impuesta con transferencia de materia.
- L o H dependientes de T o del estado, actividades y potenciales
  químicos: un cruce de signo real pertenece ahí.
- Reacción con transferencia de materia, compartimentos con corrientes, más
  de una especie por interfaz y estacionario con totales impuestos.

---

## 21. Una sola especie y balances por volumen

Respuesta a `frontend/SUPUESTOS_POR_VOLUMEN_CLAUDE.md` (prioridad posterior a
§20). Solo backend. Son dos hitos separados y **los dos están completados**.
`revision_contrato` pasa a **7** (aditiva; `schema_version` sigue en 1).

### 21.1 Hito 1: tanques de una sola especie

**Qué cambió:** `/laboratorio/estudios` admite **de 1 a 8 componentes**.
Antes exigía 2. No hay componente ficticio. Se revisaron estas piezas con
n = 1:

- **Cierre de la composición**: con una especie y sin fracciones dadas,
  x = [1].
- **Especificaciones**: `x0` es opcional. Declarar `x0 = 1` da el mismo
  resultado que no declararla. `x0 = 0.9` se rechaza
  (`LAB_DATOS_COMPOSICION_INCOMPATIBLE`) y aparece en `contradicciones`. El
  alias `x` sigue valiendo solo con n = 2.
- **Vector de inventarios**: un n por volumen (`cv1.n0`, `cv2.n0`).
- **Series**: `x0 = 1` exacto en toda corriente con caudal. Una corriente
  sin caudal da `null`, no 0.
- **Energía**: funciona con `ideal_incompresible` (c_p declarado) y con
  `proveedor_liquido` (con la comprobación de fase de siempre).

`capacidades.componentes = {min: 1, max: 8, nota}`, para que la interfaz no
tenga que inferir el rango.

**Verificado** en `tests/validar_estudios_agua_balances.py`, contra
referencias analíticas escritas en la suite:

| Caso | Referencia | Medido |
|---|---|---|
| Dos tanques de agua con salida lineal, vacíos al empezar (k = 0.2 y 0.05 1/s) | N₁ = (F/k₁)(1 − e^(−k₁t)); N₂ de la ODE lineal en serie | 5e-11 y 1e-10 (rel.) |
| Estacionario | N₁ = F/k₁ = 50, N₂ = F/k₂ = 200 | < 1e-9 mol; autovalores −k₁ y −k₂ |
| Transferencia estacionario → temporal | el temporal se queda | < 1e-8 mol |
| Inventario constante | N = ρV, nada cambia | < 1e-9 |
| Energía (ideal, cv1 con 5 kW, τ = 275 s y 1100 s) | T₁ y T₂ de dos tanques en serie | 5e-10 K |
| Energía con el proveedor | conservación y fase | `resuelto`, cumple |
| Cero componentes | — | rechazo |

Las suites multicomponente anteriores siguen en verde. Los `modelo_id` de
los montajes de antes no cambian.

### 21.2 Hito 2: el contrato de selección de balances por volumen

Sustituye al borrador local `data.balances`. Es un campo **nuevo y
opcional** de la petición:

```json
"balances_por_volumen": [
  {"bloque_id": "cv1", "materia": true, "energia": true, "momento": false,
   "procedencia": "elegido"},
  {"bloque_id": "cv2", "materia": true, "energia": false, "momento": false,
   "procedencia": "elegido"}
]
```

| Campo | Valores | Significado |
|---|---|---|
| `materia`, `energia`, `momento` | `true`, `false` o `null` | `null` o ausente **hereda** del montaje: materia sí, energía si hay `modelo_energetico`, momento no |
| `procedencia` | `elegido`, `preset`, `migrado` u omitida (`declarado`) | Se devuelve tal cual. Lo heredado sale como `heredado del montaje` |

Sin el campo, todo se comporta **exactamente** como antes: mismos
resultados y mismo `modelo_id`.

**Qué combinaciones se admiten** (verificadas, nada por suma de
interruptores):

| Selección | Resultado |
|---|---|
| Materia activa en todos los volúmenes | admitido; es la única opción para materia |
| Energía en todos los volúmenes, o en ninguno | admitido; es lo de siempre |
| Energía en un **prefijo** de la cadena (aguas arriba), no en los de aguas abajo | **admitido (nuevo)**; fila `materia+energia_en_prefijo` |
| Momento `false` o `null` | admitido |
| Materia `false` | `LAB_DIN_BALANCE_NO_SOPORTADO`: sin ella n no tiene ley, y la energía, la reacción y las corrientes la necesitan |
| Momento `true` | `LAB_DIN_BALANCE_NO_SOPORTADO`: **no está implementado; no se ejecuta ni se finge** |
| Energía en un volumen aguas abajo de uno sin ella | `LAB_DIN_BALANCE_NO_SOPORTADO`, con la **relación pendiente**: la T y la h de la corriente que entra, citando la conexión. No se suponen |
| Energía `true` sin `modelo_energetico`, o modelo declarado y ningún volumen con energía | `LAB_DIN_BALANCE_INCOHERENTE` |
| Fuente de calor, T especificada o T/U inicial en un volumen sin energía | `LAB_DIN_BALANCE_INCOHERENTE`, citando la pieza y la conexión |
| Volumen sin energía con reacción o con interfaces (térmica o material), en un montaje con energía | `LAB_DIN_BALANCE_NO_SOPORTADO`: faltaría su T |
| Selección sobre algo que no es un volumen, valor no booleano o procedencia desconocida | `LAB_DIN_BALANCE_INCOHERENTE` (o `LAB_REFERENCIA_INEXISTENTE`) |

**El caso nuevo: energía solo aguas arriba.**

- Los volúmenes con energía forman el **subsistema energético**. Su balance
  global sale por la corriente de salida del último de ellos (en el
  ejemplo, `medio`), que queda como término de salida y no se cancela.
- Los volúmenes sin energía son puramente materiales: sin U, sin T, sin
  modo térmico. Admiten cualquier cierre de materia; por ejemplo, salida
  lineal, que con energía sería frontera móvil.
- Desactivar la energía de un volumen **no fija su T**: simplemente no hay
  T. Ninguna ecuación la necesita, porque ese volumen no tiene reacción ni
  interfaces y está aguas abajo.

**Verificado:**

| Caso | Medido |
|---|---|
| cv1 (T, U), corriente intermedia y materia, frente al montaje con energía en los dos | idénticas (2e-11 relativo); cv1 no depende de cv2 |
| T de cv1 frente a la analítica de un tanque (τ = 50 s) | < 1e-8 K |
| Series de energía de cv2 y de la salida final | no existen |
| Ecuaciones `cv2:energia` y `cv2:cierre_energetico` | no existen |
| `global:energia` | entra `in`, sale `medio`, más `Q`; conservación < 1e-12 |
| Estacionario | T₁ = T_alim + Q/(F·c_p); cv2 sin T |
| Transferencia | n de los dos volúmenes, U solo de cv1; el temporal se queda |
| Selección explícita igual a la heredada | mismas series; el `modelo_id` registra la declaración |

### 21.3 Lo que devuelve la respuesta

Tres campos nuevos en `/validar` y `/resolver`:

**`balances`**, uno por volumen:

```json
{"bloque_id": "cv2", "sistema": "abierto", "relacion_de_salida": "inventario_constante",
 "familias": {
   "materia": {"solicitado": true, "activo": true, "procedencia": "elegido",
               "implementado": true, "ejecutado": true,
               "ecuaciones": ["cv2:materia_especie_0", "..."]},
   "energia": {"solicitado": false, "activo": false, "procedencia": "elegido",
               "implementado": true, "ejecutado": false, "ecuaciones": []},
   "momento": {"solicitado": false, "activo": false, "procedencia": "elegido",
               "implementado": false, "ejecutado": false, "ecuaciones": []}}}
```

- **`sistema`**: `"cerrado"` o `"abierto"`. Un sistema cerrado se declara
  como tal.
- **`relacion_de_salida`**: el cierre, `null` si es cerrado, o
  **`"pendiente"`** si falta. La ausencia de una relación de salida **no**
  es caudal cero.
- **`ejecutado`**: solo es `true` cuando la familia se calculó de verdad
  (`resolver` con resultado). En `/validar` es `false` en todas.
- **`ecuaciones`**: los ids de las ecuaciones que aporta la familia.

**`pendientes`**: lo que falta para cerrar el modelo. Recoge el cierre
ausente, especificaciones, iniciales y propiedades ausentes, las
relaciones pendientes de la selección de balances y el estacionario
indeterminado. Cada entrada trae `codigo`, `mensaje`, `accion`,
`bloque_ids`, `conexion_ids` y `variable_ids`.

**`contradicciones`**: lo que se contradice. Recoge especificaciones
excluyentes, supuestos incoherentes, selección incoherente, propiedades
incoherentes, inicial inconsistente, duplicados y composición imposible.
La forma es la misma que en `pendientes`.

Los dos son **extractos** de `diagnosticos`, no diagnósticos nuevos: la
interfaz puede listarlos sin leer mensajes.

**Grados de libertad reales.** `modelo.clasificacion` (GL, incógnitas y
ecuaciones independientes) solo existe cuando el modelo se ensambla. Si
falta algo, la respuesta no inventa un recuento: da `pendientes`.

### 21.4 Capacidades y migración

- `capacidades.componentes`: `{min: 1, max: 8}`.
- `capacidades.balances_por_volumen`: declaración, herencia, procedencias,
  lo admitido, lo no admitido con su código, los campos de la respuesta y
  `momento.implementado: false`.
- Fila nueva `materia+energia_en_prefijo` en `capacidades.combinaciones`
  (estacionario y temporal, con transferencia).
- `modelo_id`: `balances_por_volumen` entra en la huella **solo si se
  declara**, y también en las huellas por elemento de la transferencia.

| Cambio | Para el frontend |
|---|---|
| Una especie | Quitar el bloqueo de 2 componentes; tomar el rango de `capacidades.componentes` |
| `data.balances` → `balances_por_volumen` | Migrar con `procedencia: "migrado"`; enviar `null` para heredar |
| `balances[].familias[].ejecutado` | Mostrar «ejecutado» solo cuando es `true`. Momento nunca lo es |
| `pendientes` y `contradicciones` | Listarlos por pieza y conexión; no recontar GL en el cliente |
| `relacion_de_salida: "pendiente"` | Mostrarla como pendiente, nunca como F = 0 |

### 21.5 Ejemplos ejecutados

| Ejemplo | Estado |
|---|---|
| `estudio-agua-dos-tanques` (salida lineal, vacíos al empezar) | `resuelto` |
| `estudio-agua-dos-tanques-estacionario` | `resuelto` |
| `estudio-agua-dos-tanques-energia` | `resuelto` |
| `estudio-agua-x-distinta-de-uno` | `invalido` |
| `estudio-balances-energia-solo-primero` | `resuelto` |
| `estudio-balances-energia-solo-segundo` (relación pendiente) | `no_soportado` |
| `estudio-balances-momento` | `no_soportado` |
| `estudio-transferencia-agua-*`, `estudio-transferencia-energia-solo-primero-*` | `resuelto` |

`tests/validar_estudios_agua_balances.py`: **62 comprobaciones**. La suite
completa de `run_tests.py` está en verde.

### 21.6 Lo que no está

- Momento (sigue sin implementar: se diagnostica).
- Energía aguas abajo de un volumen sin ella: haría falta declarar la T de
  una corriente intermedia como frontera, y eso no está en el contrato.
- Selección por volumen de otras simplificaciones (supuestos por volumen
  más allá de la energía), `latex_expandido` / `latex_sumatorias`,
  especies personalizadas, overrides de propiedades por especie, más de dos
  volúmenes y el hito B de §20.

---

## 22. Unidades, catálogo de variables y especificaciones flexibles

Respuesta a `frontend/ENTREGA_CLAUDE_ESPECIFICACIONES_UNIDADES.md`. Solo
backend. `revision_contrato` pasa a **8** (aditiva; `schema_version` sigue
en 1).

| Hito | Estado |
|---|---|
| **1**. Registro coherente de unidades y catálogo de variables | **completado** |
| **2**. Balance general con especificaciones flexibles (estacionario directo e inverso, temporal directo) | **completado**, con alcance de **una especie** y sin energía, reacción ni interfaces |
| Problemas inversos temporales con objetivos finales | **no disponible** (se rechaza; `capacidades` lo dice) |

### 22.1 Hito 1: una sola fuente de unidades

**Ruta final:** `GET /laboratorio/estudios/unidades`. `/unidades` no
cambia.

- **La tabla:** `core/unidades_estudios.py` declara, por magnitud, las
  unidades admitidas con factor y desplazamiento exactos
  (`valor_SI = valor·factor + desplazamiento`) y su expresión en Pint.
- **El juez:** al cargar, cada factor y cada desplazamiento se comprueban
  contra el registro Pint del proyecto (`config/settings.py`). Si uno no
  cuadra, el módulo no carga.
- **Coherencia con el laboratorio:** también se comprueba que las tablas
  del laboratorio estacionario (`core/laboratorio.py`) coinciden en las
  magnitudes compartidas.
- **Una sola tabla:** el motor de estudios **convierte con esa misma
  tabla**. Todas sus tablas y conversiones salen ahora del registro, así que
  lo publicado es exactamente lo aceptado.

**Respuesta de la ruta:**

| Campo | Contenido |
|---|---|
| `magnitudes.{id}` | `dimension`, `unidad_interna`, `tipo` (`afin`, `absoluta` o `diferencia`), `base` (fracciones y reparto), `semantica`, `solo_presentacion` y `unidades[]` con `{simbolo, etiqueta, factor, desplazamiento, pint}` |
| `conversiones_no_afines` | kg/h → mol/s (masa molar y composición), caudal volumétrico → molar (densidad), presión relativa → absoluta (referencia), % → fracción, temperatura → diferencia. **Todas `admitida: false`** |
| `campos` | la magnitud de cada campo de la petición |
| `magnitud_de_variable` | la magnitud de cada variable del modelo |
| `porcentaje` | no admitido: su semántica (molar o másica, base) no está declarada |
| `revision_catalogo` | 1 |

**Magnitudes:** tiempo, cantidad_sustancia, flujo_molar, fraccion_molar,
volumen, densidad_molar, temperatura (absoluta), temperatura_diferencia
(solo presentación: ningún campo de entrada la acepta), presion
(absoluta), energia, energia_molar, potencia, capacidad_calorifica_molar,
capacidad_termica, conductancia_termica, conductancia_material,
constante_salida (la k de `salida_lineal`), reparto, tasa_integrada y
tasa_volumetrica.

**Procedencia.** `/validar` y `/resolver` traen `cantidades_normalizadas`:
`[{ruta, variable_id, magnitud, declarado: {valor, unidad}, normalizado:
{valor, unidad}}]`. Lo declarado se conserva intacto.

**Catálogo de variables.** `/validar` y `/resolver` traen
`catalogo_variables`, **también con el montaje incompleto**. En ese caso
sale desde la topología y con `provisional: true`.

```json
{"id": "medio.F", "nombre": "Caudal · corriente medio", "simbolo": "F",
 "magnitud": "flujo_molar", "unidad_interna": "mol/s", "familia": "materia",
 "bloque_ids": ["medio", "cv1", "cv2"], "conexion_ids": ["c2", "c3"],
 "compartida": true, "clase": "algebraica", "funcion": "calculada",
 "puede_especificarse": false, "puede_calcularse": true,
 "motivo_limitacion": "la determina cv1:restriccion_inventario", "provisional": false}
```

- **`funcion`**: `especificacion` (frontera o dato), `incognita`,
  `calculada`, `estado` o `parametro`.
- **Elegibilidad:** depende del cierre y del estudio. Con los cierres
  anteriores, una frontera solo puede ser dato y una algebraica solo puede
  calcularse. Con `balance_general`, F y n son elegibles en estacionario.
  En temporal, F solo puede ser dato y n es estado.
- **`puede_calcularse`** es una elección admitida, **no** una garantía de
  que cualquier combinación de elecciones cierre el sistema.

### 22.2 Hito 2: el balance general y la selección de variables

**Cierre nuevo `balance_general`.** Aporta entrada, salida y acumulación,
**sin** F_sal = k·N ni N = ρV. No tiene parámetros. Los cierres anteriores
no cambian ni se convierten.

- **Contradicción geométrica:** declarar `V` + `densidad_molar` con este
  cierre se rechaza, porque son N = ρV, la restricción del inventario
  constante. **No se borra para aceptarlo.**
- **Otros parámetros:** `k_salida` o `F_salida` también se rechazan
  (`LAB_ESPECIFICACION_EXCLUYENTE`).

**Alcance verificado:**

- una especie;
- uno o dos volúmenes en serie, todos `balance_general`;
- sin energía, reacción, interfaces ni volúmenes cerrados.

Lo demás se rechaza con su código.

**`seleccion_variables`** (campo nuevo, solo con `balance_general`):

```json
"seleccion_variables": {"version": 1, "variables": [
  {"variable_id": "in.F", "modo": "calcular"},
  {"variable_id": "medio.F", "modo": "calcular"},
  {"variable_id": "out.F", "modo": "dato", "cantidad": {"valor": 36, "unidad": "kmol/h"}},
  {"variable_id": "cv1.n0", "modo": "dato", "cantidad": {"valor": 100, "unidad": "mol"}},
  {"variable_id": "cv2.n0", "modo": "dato", "cantidad": {"valor": 200, "unidad": "mol"}}]}
```

- **Variables elegibles:** el `F` de cada corriente y el `n0` de cada
  volumen.
- **`dato`** añade una especificación. **`calcular`** declara una
  incógnita sin inventarle un valor; lo que no es dato ya es incógnita.
- **Duplicados:** la misma variable dos veces, o en `seleccion_variables` y
  en `especificaciones` a la vez, es `LAB_ESPECIFICACION_DUPLICADA`. No se
  elige ni se migra en silencio. La corriente compartida es **una**
  variable.
- **Con otros cierres**, `seleccion_variables` es
  `LAB_DIN_ESPECIFICACION_NO_ADMITIDA`. Esos montajes usan
  `especificaciones`.

**Estacionario: un sistema lineal, no una marcha hacia delante.**

- **Incógnitas:** u = [F de cada corriente, n de cada volumen].
- **Filas:** el balance de cada volumen (F_ent − F_sal = 0) y una fila por
  cada dato.
- **Rango:** se mide por SVD el de A y el de [A | b]. Para un sistema
  lineal es **exacto y global**, no una prueba local.
- **Solución:** con rango completo, `solve` exacto (10 mol/s da 10.0, no
  9.999…).

| Situación | Resultado |
|---|---|
| Rango completo y consistente | `resuelto`; `estacionario.solucion`, `estados` y procedencia (`dato (seleccion_variables)` o `calculado`) |
| rango [A\|b] > rango A | `invalido`, **`LAB_DIN_ESPECIFICACION_CONTRADICTORIA`**, con los datos en conflicto (los que, quitados uno a uno, devuelven la consistencia); va también en `contradicciones` |
| Incógnitas en el núcleo de A | `invalido`, `LAB_DIN_ESTACIONARIO_INDETERMINADO`, con esas variables; `estacionario.determinadas` solo trae las demás. **No se fabrica un valor**; va también en `pendientes` |
| Dato que, quitado, no baja el rango | **`LAB_DIN_ESPECIFICACION_REDUNDANTE`** (advertencia): compatible, pero sin ecuación independiente |

`modelo.clasificacion.estacionario_lineal` declara:

- `incognitas`, `ecuaciones`, `especificaciones_usadas`,
  `incognitas_buscadas` y `calcular_declaradas`;
- los resultados del análisis: `consistente`, `en_conflicto`,
  `indeterminadas`, `redundantes`, `solucion` y `residuo_escalado`;
- **`rango`**: incógnitas, filas, GL estructurales, `rango_A`, GL reales y
  método.

GL = 0 no basta: un recuento cuadrado con filas dependientes se rechaza,
diciendo cuáles quedan indeterminadas.

La estabilidad no se declara: con los caudales fijados, los inventarios son
modos neutros.

**Temporal directo.**

- **Fronteras:** los caudales de **todas** las corrientes son datos. La
  salida impuesta por el usuario es una condición de frontera, no una bomba
  oculta. n va en `condiciones_iniciales`, sin exigir V, densidad ni k.
- **Integración:** los dos volúmenes juntos, con una sola corriente
  intermedia, con el integrador de siempre.
- **Pendientes:** un caudal que falta queda **pendiente**
  (`LAB_FALTA_ESPECIFICACION`, con su variable y sus conexiones), **nunca**
  cero ni una ley generada.
- **Rechazos:** calcular un caudal, o poner n en la selección, es
  `LAB_DIN_ESPECIFICACION_NO_ADMITIDA`.
- **Eventos:** un volumen que se vacía da el evento `vaciado` y `parcial`,
  también en t = 0⁺.
- **Contraste:** no se evalúa, porque el estacionario del balance general
  necesita sus propias especificaciones.

**No disponible, y rechazado (no ignorado):**

- `estudio.objetivos` y `modo: "objetivo"` (problema inverso temporal),
  con `LAB_DIN_ESPECIFICACION_NO_ADMITIDA`;
- expresiones arbitrarias;
- la transferencia estacionario → temporal para esta combinación
  (`LAB_DIN_TRANSFERENCIA_NO_POSIBLE`). Un caudal estacionario calculado no
  se convierte en una ley temporal de salida.

### 22.3 Identidad, capacidades y migración

- **`modelo_id`**: `seleccion_variables` entra **normalizada a SI**, así
  que 36 kmol/h y 10 mol/s dan el mismo `modelo_id`. Un valor distinto lo
  cambia. Las huellas por elemento incluyen cada variable seleccionada. Los
  `modelo_id` de los montajes anteriores no cambian (comprobado en 5
  ejemplos).
- **Normalización:** la firma y las huellas siguen con la normalización
  exacta (10 y 10.000000000000002 difieren). La prueba Python → Node →
  Python pasa.
- **`capacidades`** (revisión 8):
  - fila nueva `materia_balance_general`, con sus especificaciones por
    estudio y lo no soportado;
  - secciones nuevas `unidades`, `catalogo_variables`,
    `seleccion_variables` (con códigos e identidad),
    `problemas_inversos.temporal_con_objetivos_finales: false` y
    `expresiones_arbitrarias: false`;
  - cada cierre declara su `relacion_de_salida`.
- **Códigos nuevos:** `LAB_DIN_ESPECIFICACION_NO_ADMITIDA`,
  `LAB_DIN_ESPECIFICACION_REDUNDANTE` y
  `LAB_DIN_ESPECIFICACION_CONTRADICTORIA`.
- **Sin cambio de resultados:** las peticiones sin campos nuevos dan lo
  mismo que antes. Lo nuevo en sus respuestas es aditivo:
  `catalogo_variables`, `cantidades_normalizadas` y
  `revision_contrato: 8`.

| Cambio | Para el frontend |
|---|---|
| `GET /laboratorio/estudios/unidades` | Única tabla para convertir en local; no mantener otra |
| `catalogo_variables` | La lista «variable / Dato o Calcular / valor / unidad» sale de aquí: mostrar las no editables con su `motivo_limitacion` |
| `cierre: "balance_general"` + `seleccion_variables` | La mesa de un tanque sin k; **no migrar una mesa kN por cuenta propia** (es una elección física del usuario e invalida resultados y transferencias) |
| `estacionario_lineal.rango` | Mostrar GL reales e indeterminadas; no recontar en el cliente |
| `cantidades_normalizadas` | Mostrar lo declarado; convertir ejes con los factores publicados sin tocar el dato |

### 22.4 Lo verificado

`tests/validar_estudios_unidades_especificaciones.py`, **76
comprobaciones**, numeradas como la sección 8 del contrato:

| # | Prueba | Resultado |
|---|---|---|
| 1 | 10 min y 600 s | misma malla de t y mismas series (exacto) |
| 2 | 36 kmol/h y 10 mol/s; mol/s en la entrada y kmol/h en la salida; kmol y mmol | misma trayectoria (< 1e-9); coherentes y redundantes |
| 3 | 25 degC = 298.15 K; 25 delta_degC = 25 K; una diferencia no es una temperatura | igual; misma trayectoria con T_alim en degC o K |
| 4 | F en K, sin unidad, `furlong/s`, kg/h; en `seleccion_variables` | `LAB_UNIDAD_INCOMPATIBLE` citando la variable (y la conexión) |
| 5 | Catálogo = tablas del cálculo, y cada unidad de F, t, V, ρ y n de extremo a extremo | iguales; mismos resultados (< 1e-9) |
| 6 | `null` ≠ 0; F = 0 es dato; no finito; sin redondeo en las huellas | correcto |
| 7 | Procedencia intacta; 600 s → 10 min → 600 s; estado transferido tras un roundtrip JSON | correcto |
| 8 | Estacionario hacia delante (F_ent = 10) y hacia atrás (F_sal = 36 kmol/h) | F = 10 mol/s exacto en las tres corrientes; rango 5/5 |
| 9 | Solo F_ent | n₁ y n₂ indeterminados; sin valor fabricado |
| 10 | Contradicción (10 y 5), redundancia (10 y 10), corriente compartida dos veces, dato en los dos sitios | distinguidos |
| 11 | F = 3, 2, 1 mol/s; n(0) = 100, 200 | n₁ = 100 + t y n₂ = 200 + t (< 1e-9); suma a 2 mol/s; `corriente:medio` cancelada |
| 12 | Sin el caudal intermedio, o sin ningún caudal | pendiente; nunca cero |
| 13 | Vaciado en t = 5 s y en t = 0⁺ | evento `vaciado`, `parcial` |
| 14 | 5 incógnitas, 5 filas, rango 4 | rechazado; cv1.n0 indeterminado |
| 15 | Objetivos, `modo: objetivo`, calcular F en temporal, n en la selección, otro cierre, x0, varias especies, F < 0 | rechazados con su código |
| 16 | V y ρ, k, energía, mezcla de cierres con `balance_general` | rechazados; la restricción no se borra |
| 17 | `modelo_id` anteriores, unidad equivalente, huellas, no mutación, Node, transferencia, procedencia por término, una sola caja | correcto |

La batería completa de `run_tests.py`: **32 suites en verde**.

### 22.5 Ejemplos ejecutados

| Ejemplo | Estado |
|---|---|
| `estudio-unidades.json` (la ruta de unidades) | — |
| `estudio-unidades-tiempo-en-minutos` | `resuelto` |
| `estudio-balance-general-directo` (y su `-validar-respuesta`) | `resuelto` |
| `estudio-balance-general-inverso` | `resuelto` |
| `estudio-balance-general-indeterminado` | `invalido` |
| `estudio-balance-general-redundante` | `resuelto` (con advertencia) |
| `estudio-balance-general-contradictorio` | `invalido` |
| `estudio-balance-general-temporal` | `resuelto` |
| `estudio-balance-general-temporal-sin-frontera` | `invalido` (pendiente) |
| `estudio-balance-general-vaciado` | `parcial` |
| `estudio-balance-general-con-densidad` | `invalido` |

### 22.6 Archivos por hito y lo que no está

**Hito 1:**

- `core/unidades_estudios.py` (nuevo);
- en `core/dinamica.py`, las tablas y la conversión `_conv`, y
  `catalogo_variables`;
- `backend/nucleo_estudios.py` (`unidades_estudios` y
  `cantidades_normalizadas`);
- `backend/main.py` (la ruta);
- `backend/schemas_estudios.py`.

**Hito 2:**

- en `core/dinamica.py`: el cierre `balance_general`, `_leer_seleccion`,
  `_analisis_lineal`, `_aplicar_estacionario_lineal`, el modelo y las
  capacidades;
- `core/errores.py`;
- en `backend/nucleo_estudios.py`: la selección normalizada y las huellas;
- `backend/ejemplos_estudios.py`;
- `tests/validar_estudios_unidades_especificaciones.py`.

**Además**, se ajustaron una comprobación de revisión en
`tests/validar_estudios_agua_balances.py` (`>= 7`) y el generador de
ejemplos.

**No está:**

- problemas inversos temporales;
- balance general con varias especies, energía, reacción o interfaces;
- mezcla con otros cierres;
- transferencia de origen para esta combinación;
- expresiones arbitrarias;
- conversiones no afines (masa, caudal volumétrico, presión relativa).

### 22.7 Revisión de la integración (`frontend/INTEGRACION_ENTREGA_22.md`)

Se comprobó contra el backend lo que la integración da por hecho.

**Lo que ya se cumplía:**

- Los 62 ejemplos, tal como los sirve `/laboratorio/estudios/ejemplos` (con
  los opcionales en `null`), se reenvían a `/validar` sin error.
- Retirar F_sal del caso inverso deja `grados_libertad_reales = 1`.
- El temporal F = 3/2/1 mol/s, n₀ = 100/200 mol, con 10 min, da 700/800 mol.

**Lo que no se cumplía, y se corrigió:** «las condiciones iniciales `null`
siguen siendo opcionales» era falso en el backend. Una lista opcional
enviada como `null` daba **422** de Pydantic, sin código ni pieza.
Afectaba a `estudio.condiciones_iniciales`, `estudio.entradas_temporales`,
`especificaciones`, `almacenamiento` y `supuestos`.

Ahora **`null` es ausente**, igual que `[]` o `{}`:

- mismo resultado, mismo `modelo_id` y mismo `estudio_id`;
- lo que falte lo diagnostica el núcleo con su código y su pieza; por
  ejemplo, `especificaciones: null` da `LAB_FALTA_ESPECIFICACION`.

El cambio es aditivo, sin revisión nueva de contrato: solo acepta una forma
que antes se rechazaba sin diagnóstico. Está en `backend/schemas_estudios.py`
y lo prueban seis comprobaciones nuevas en
`tests/validar_estudios_unidades_especificaciones.py` (82 en total).

**Pendientes:** la integración no encarga trabajo nuevo al backend. Los
pendientes «aún sin encargar» de `SUPUESTOS_POR_VOLUMEN_CLAUDE.md` siguen
sin hacer hasta que se prioricen:

- otras simplificaciones locales;
- una frontera térmica explícita para la energía aguas abajo;
- `latex_expandido` / `latex_sumatorias`;
- overrides por especie o propiedad;
- momento, más de dos volúmenes, reacción con interfaz material y el
  proveedor con transferencia selectiva.

La batería completa de backend se volvió a ejecutar tras este cambio.

---

## 23. Recuento canónico del problema

Respuesta a `frontend/ESTADO_MODELO_EXPERIMENTAR.md`. Solo backend, pruebas y
documentación. **Metadatos de validación: la física no cambia.**
`revision_contrato` pasa a **9**: el campo es aditivo, y la convención es
subir la revisión con cada cambio aditivo del contrato. `schema_version`
sigue en 1.

**Hay que recargar el servicio.** Cambian `core/dinamica.py` y
`backend/schemas_estudios.py`.

### 23.1 Dónde está y de dónde sale

Campo **`recuento`** en las respuestas de `/laboratorio/estudios/validar` y
`/resolver`.

- **Origen:** sale del **mismo ensamblaje** y del mismo análisis que el
  cálculo, y se calcula **antes del solver**. El de `/resolver` es
  idéntico al de `/validar` para la misma petición.
- **Sin cálculo:** no se integra ni se buscan raíces. En el estacionario
  del balance general solo se mide el rango del sistema lineal (SVD).
- **Estudio incompleto:** si la definición física se lee sin errores y solo
  fallan datos del estudio (por ejemplo, una inicial ausente), el modelo se
  ensambla **solo para contar y para el catálogo**. La respuesta sigue sin
  modelo, como antes.
- **Petición que no llega al núcleo** (una condición transferida alterada):
  `recuento` sale `no_evaluable`.

### 23.2 Esquema (versión 1)

Ejemplo real: el balance general inverso sin su único caudal dato.

```json
"recuento": {
  "version": 1,
  "estado_completitud": "incompleto",
  "puede_resolver": false,
  "motivo": "faltan datos o hay datos presentes pero invalidos (ver 'desglose')",
  "origen_analisis": "rango_numerico",
  "ambito": "sistema lineal estacionario del balance general: incognitas = F de cada corriente y n de cada volumen",
  "advertencia": "GL = 0 no prueba existencia, consistencia ni unicidad; ...",
  "indicador": {
    "variables": 5, "ecuaciones_fisicas_independientes": 2, "datos_definidos": 2,
    "especificaciones_independientes": 2, "especificaciones_faltantes": 1,
    "faltantes_es_cota_inferior": false, "motivos_null": {},
    "definiciones": {"variables": "...", "...": "..."}
  },
  "desglose": {
    "especificaciones": {"declaradas": [], "usadas": [], "no_usadas": [], "invalidas": [],
                         "redundantes": [], "en_conflicto": []},
    "parametros": {"requeridos": [], "definidos": [], "faltantes": []},
    "iniciales": {"aplica": false, "requeridas": [], "definidas": [], "faltantes": [],
                  "inconsistentes": [], "invalidas": []},
    "restricciones": [],
    "ecuaciones": {"balances": {"total": 2, "cuentan": 2}, "verificaciones": {"total": 1, "cuentan": 0}},
    "datos_invalidos": []
  },
  "referencias": {
    "pendientes": [{"codigo": "LAB_DIN_ESTACIONARIO_INDETERMINADO", "faltan": 1, "eleccion": "alguna",
                    "variables": [<ref in.F>, <ref medio.F>, <ref out.F>],
                    "nota": "da como dato tantas de estas como 'faltan', ..."}],
    "conflictos": [],
    "redundancias": []
  }
}
```

**Una referencia** (`<ref>`):

```json
{"variable_id": "medio.F", "funcion": "especificacion", "codigo": null,
 "ruta": {"campo": "seleccion_variables.variables", "clave": {"variable_id": "medio.F"}, "indice": 1},
 "bloque_ids": ["medio"], "conexion_ids": ["c2", "c3"]}
```

| Campo | Contenido |
|---|---|
| `variable_id` | el id de `catalogo_variables`; `null` si lo pendiente no es una variable (una relación de salida) |
| `funcion` | `especificacion`, `parametro`, `inicial` o `relacion` |
| `ruta.campo` | dónde va en la petición; ver la tabla siguiente |
| `ruta.clave` | identifica la entrada sin depender del orden |
| `ruta.indice` | su posición si ya existe; `null` si hay que añadirla |

| `ruta.campo` | `ruta.clave` |
|---|---|
| `especificaciones` | `{bloque_id, variable}` |
| `seleccion_variables.variables` | `{variable_id}` |
| `estudio.condiciones_iniciales` | `{bloque_id, componente, magnitud}` (`magnitud` es `"n"` o `"T o U"`) |
| `almacenamiento` | `{bloque_id, parametro}`; `parametro: "cierre"` si falta la relación de salida |
| `interfaces_termicas` o `interfaces_materiales` | `{conexion_id, parametro}` |

### 23.3 Definiciones

**`estado_completitud`** (aparte del estado del cálculo, `resuelto`,
`parcial`, etc.):

| Valor | Significado | `puede_resolver` |
|---|---|---|
| `listo` | nada falta ni sobra | `true` |
| `redundante_compatible` | datos redundantes y compatibles (`LAB_DIN_ESPECIFICACION_REDUNDANTE`) | **`true`**: no bloquean |
| `incompleto` | faltan datos, o hay datos presentes pero inválidos (sin unidad, fuera de dominio, no finitos) | `false` |
| `conflicto` | datos válidos que se contradicen entre sí o con una restricción (incluida una inicial incompatible con N = ρV) | `false` |
| `no_evaluable` | combinación no soportada o topología no construible | `false` |

**`origen_analisis`:**

| Valor | Cuándo | Qué certifica |
|---|---|---|
| `rango_numerico` | estacionario del balance general | rango exacto y **global**, porque el sistema es lineal |
| `estructural` | el resto, con el modelo ensamblado | recuento triangular por construcción; **no** se calcula un rango numérico |
| `no_evaluado` | sin modelo ensamblado | nada |

**`indicador`** (cada número trae su definición en `definiciones`):

| Campo | `rango_numerico` | `estructural` | `no_evaluado` |
|---|---|---|---|
| `variables` | incógnitas de la matriz: F de cada corriente (la compartida, una vez) y n de cada volumen | `clasificacion.incognitas`: diferenciales y algebraicas, sin entradas ni parámetros | `null` con motivo |
| `ecuaciones_fisicas_independientes` | un balance por volumen | `clasificacion.ecuaciones_independientes`. **No** cuentan las verificaciones globales ni las derivadas de restricciones | `null` |
| `datos_definidos` | datos de la selección | especificaciones **usadas**, parámetros definidos e iniciales definidas | lo declarado y válido |
| `especificaciones_independientes` | rango(A) − balances | especificaciones usadas | `null` |
| `especificaciones_faltantes` | **GL reales** (`null` si hay contradicción) | GL estructural más un dato por cada requerido ausente | suma de los pendientes conocidos, o `null` |
| `faltantes_es_cota_inferior` | `false` | `true` si hay errores (un error puede ocultar otros) | `true` |

`variables − ecuaciones − datos` **no** es «lo que falta». Lo que falta es
`especificaciones_faltantes`, y sale del rango o de los requeridos ausentes.

**`desglose`:**

- **`especificaciones`:** separa las declaradas, las usadas, las no usadas,
  las inválidas (presentes pero sin unidad o fuera de dominio, con su
  código y motivo), las redundantes y las que están en conflicto.
- **`parametros`:** los requeridos por cada cierre (V, densidad, k, F_s) y
  por cada interfaz (G, L, H), con los definidos y los que faltan.
- **`iniciales`:** solo en un temporal. Requeridas son n por especie y
  volumen, más T o U en los volúmenes con energía. Separa definidas,
  faltantes, inconsistentes e inválidas.
- **`restricciones`:** las de la clasificación (N = ρV de índice 2, U = U(n, T*)).
- **`ecuaciones`:** por tipo (balances, constitutivas, restricciones,
  especificaciones, verificaciones, derivadas de restricción), con cuántas
  cuentan.

**`referencias`:**

- **`pendientes`:** grupos con `faltan` y `eleccion`:
  - `todas`: cada una es necesaria;
  - `alguna`: elegir `faltan` entre las candidatas, sin imponer dónde;
  - `relacion`: falta una relación, por ejemplo T y h de una entrada.
- **`conflictos`:** todos los datos implicados.
- **`redundancias`:** los datos redundantes.

Todos los `variable_id` están en `catalogo_variables`.

### 23.4 Lo verificado

`tests/validar_estudios_recuento.py`, **55 comprobaciones**, numeradas como
los criterios del documento:

| # | Criterio | Resultado |
|---|---|---|
| 1 | Balance general directo e inverso; retirar el único caudal | mismo análisis (5 / 2 / 3, falta 0); sin caudal, falta 1, `alguna` entre in.F, medio.F y out.F |
| 2 | Inicial ausente frente a incompatible | `incompleto` (cv2.n1, con ruta) frente a `conflicto` (cv1.n0 y cv1.n1, con índice); con el sistema diferencial cerrado **no** se certifica listo |
| 3 | Redundante frente a contradictorio | `redundante_compatible`, se resuelve; `conflicto` con in.F y out.F, y faltantes `null` con motivo |
| 4 | Cuadrado con rango 4 de 5 | `incompleto`; la corriente compartida cuenta una vez; las verificaciones no cuentan |
| 5 | Material, energía (temporal y estacionario), reacción, reacción + interfaz, interfaz térmica, interfaz material, material + energía, agua, balance general temporal | `listo`, falta 0, restricciones e iniciales T reflejadas. Hito B, momento y tasa fija: `no_evaluable`. Estacionario de dos cerrados: `incompleto` |
| 6 | `null` y `[]`, cero explícito, valor `null`, unidades equivalentes, sin unidad | mismo recuento; el cero cuenta; `null` no; sin unidad, «inválida» con su ruta |
| 7 | `/validar` frente a `/resolver` | el mismo recuento en 6 casos; `/validar` no integra ni resuelve; sin cierre, `no_evaluado` con `null` y motivo |
| 8 | Identificadores y regresión | `modelo_id` intactos; un estudio incompleto sigue sin modelo, pero su catálogo ya usa ids reales; los ejemplos servidos traen recuento; transferencia alterada, `no_evaluable` |

Las regresiones de §22.7 (los ejemplos servidos reenviables y los tres
escenarios del navegador) siguen en
`tests/validar_estudios_unidades_especificaciones.py`. Batería completa
(`run_tests.py`): **33 suites en verde**.

### 23.5 Ejemplos ejecutados

Pares de `/validar` generados desde el endpoint (`estudio-recuento-*`):

| Ejemplo | `estado_completitud` |
|---|---|
| `listo` | `listo` |
| `incompleto-sin-caudal` | `incompleto` |
| `incompleto-sin-inicial` | `incompleto` |
| `inicial-incompatible` | `conflicto` |
| `redundante` | `redundante_compatible` |
| `contradictorio` | `conflicto` |
| `no-evaluable` | `no_evaluable` |

Todas las respuestas regeneradas (`estudio-*-respuesta.json`) traen
`recuento`.

### 23.6 Compatibilidad, archivos y límites

**Compatibilidad:**

- Resultados físicos, capacidades de resolución y `modelo_id`: sin cambios.
- Un estudio incompleto sigue devolviendo el modelo vacío.
- Lo único que cambia en esa respuesta: el catálogo usa los ids reales en
  vez del provisional, y aparece `recuento`.
- `null`, `[]` y las unidades equivalentes dan el mismo recuento.

**Archivos tocados:**

- `core/dinamica.py`: `recuento`, `_modelo_para_recuento`, las referencias
  y `capacidades.recuento`;
- `backend/schemas_estudios.py`: el campo `recuento`;
- `backend/nucleo_estudios.py`: el recuento `no_evaluable` en la frontera;
- `tests/validar_estudios_recuento.py` (nuevo);
- `tests/generar_ejemplos_estudios.py`.

**Límites:**

- Fuera del balance general el análisis es **estructural**: no se calcula
  un rango numérico del sistema no lineal.
- Con errores, lo que falta es una **cota inferior**, porque un dato
  inválido o un conflicto puede ocultar otros.
- Sin modelo ensamblado (falta un cierre, la topología no se construye),
  variables y ecuaciones son `null`.
- Parámetros requeridos: solo los de los cierres y las interfaces. Las
  propiedades del modelo energético faltantes aparecen como pendientes por
  su diagnóstico (`LAB_DIN_PROPIEDAD_FALTANTE`), no en
  `desglose.parametros`.
- Sin ampliación física: siguen en cola las simplificaciones por volumen,
  la frontera térmica, `latex_expandido`, las propiedades por especie, el
  momento y el resto.

### 23.7 Seguimiento: referencia de una propiedad faltante

Respuesta al seguimiento acotado anotado en `frontend/PENDIENTES_BACKEND_CLAUDE.md`.

**El caso:** al retirar el `cp` de benzene de
`estudio-energia-estacionario-peticion.json`, `/validar` daba
`LAB_DIN_PROPIEDAD_FALTANTE` con Falta ≥ 1, pero con una referencia vacía:
`variable_id`, `ruta.campo` y `ruta.clave` en `null`, sin piezas ni
conexiones.

**La corrección** cubre todas las propiedades faltantes que se pueden
identificar:

- **Los diagnósticos citan la variable.** Son las de `catalogo_variables`
  con el prefijo `fluido.`:
  - `fluido.cp{i}`, `fluido.cv{i}` y `fluido.u_referencia{i}`, por especie;
  - `fluido.T_referencia`, `fluido.densidad_molar` y `fluido.dominio_T`.

  Citan también los volúmenes afectados (los que tienen energía). Esto
  vale igual para las propiedades **presentes pero inválidas**, como un
  `cp` sin unidad.
- **La referencia del recuento** lleva `funcion: "parametro"` y la ruta
  `modelo_energetico.<propiedad>`:

| Propiedad | `ruta.campo` | `ruta.clave` | `ruta.indice` |
|---|---|---|---|
| `cp`, `cv` o `u_referencia` de una especie | `modelo_energetico.cp` (o `.cv`, `.u_referencia`) | `{"componente": ...}` | su posición si existe; `null` si hay que añadirla |
| `T_referencia`, `densidad_molar` o `dominio_T` | `modelo_energetico.T_referencia` (o `.densidad_molar`, `.dominio_T`) | `null` | `null` |

```json
{"variable_id": "fluido.cp0", "funcion": "parametro",
 "codigo": "LAB_DIN_PROPIEDAD_FALTANTE",
 "ruta": {"campo": "modelo_energetico.cp", "clave": {"componente": "benzene"}, "indice": null},
 "bloque_ids": ["cv1", "cv2"], "conexion_ids": []}
```

- **El catálogo** incluye las propiedades declarables del modelo
  energético según su tipo, con familia `energia`. Si el modelo no se
  ensambló (porque falta la propiedad), salen como `provisional`; con el
  modelo ensamblado, con sus ids reales. Así toda referencia apunta a un id
  del catálogo. Antes, las variables `fluido.*` no aparecían en el
  catálogo.

**Lo que no cambia:** los recuentos (Falta 1 en el caso del documento), los
resultados y los `modelo_id`. `/validar` y `/resolver` devuelven la misma
referencia y el mismo recuento.

**Pruebas:** 11 comprobaciones nuevas en `tests/validar_estudios_recuento.py`
(66 en total):

- falta el `cp` de benzene;
- faltan `T_referencia`, `dominio_T` o `densidad_molar`;
- faltan el `cv` o la `u_referencia` de una especie en `ideal_volumen_fijo`;
- un `cp` presente pero sin unidad, que sale como inválido con su índice;
- el catálogo del montaje completo.

**Ejemplo generado desde el endpoint:**
`estudio-recuento-propiedad-faltante-validar-{peticion,respuesta}.json`.

**Archivos:** `core/dinamica.py` (los diagnósticos de `_leer_energia` y
`_propiedad_por_especie`, `_funcion_de`, `_ruta_de`, `_ref_de_variable` y
`_catalogo_fluido`), `tests/validar_estudios_recuento.py` y
`tests/generar_ejemplos_estudios.py`.

**Revisión del contrato:** sigue en 9. Es una corrección de metadatos sin
campos nuevos en la respuesta: lo único que cambia es que
`catalogo_variables` gana las entradas `fluido.*`. **Hay que recargar el
servicio.**

## 24. Tanques, circuitos térmicos, pared y vapor (hitos A–D)

Respuesta a `frontend/SIGUIENTE_CLAUDE_TANQUES_CIRCUITOS_TERMICOS.md`. Los
cuatro hitos están entregados, cada uno con su revisión del contrato
(`revision_contrato` 10 → 13; `schema_version` no cambia). El hito D se
entrega en un **régimen acotado** (cámara de vapor saturado
cuasiestacionaria), después de la auditoría de viabilidad del §24.4.

| Hito | Revisión | Combinación en `capacidades.combinaciones` | Pruebas |
|---|---|---|---|
| A. Tanque abierto con cantidad variable y energía | 10 | `materia_balance_general+energia` | `tests/validar_estudios_tanque_termico.py` (48) |
| B. Dos circuitos unidos por una interfaz térmica | 11 | `dos_circuitos+energia+interfaz` | `tests/validar_estudios_circuitos.py` (42) |
| C. Pared sólida con o sin almacenamiento | 12 | `pared_solida+energia` | `tests/validar_estudios_pared.py` (73) |
| D. Cámara de vapor saturado (IAPWS-IF97) | 13 | `camara_vapor_saturado+energia` | `tests/validar_estudios_vapor.py` (66) |

**Hay que recargar el servicio.**

### 24.1 Hito A: tanque abierto con cantidad variable y energía

**Petición.** Un volumen con `cierre: "balance_general"` y `energia`
declarada. Los caudales de frontera van en `seleccion_variables` (como en el
§22). Campos nuevos en su entrada de `almacenamiento`, los dos opcionales:

```json
{"bloque_id": "tk", "cierre": "balance_general",
 "energia": {"modelo": "solo_fluido", "adiabatico": false},
 "capacidad_maxima": {"valor": 0.025, "unidad": "m3"},
 "area": {"valor": 0.5, "unidad": "m2"}}
```

- `capacidad_maxima` es el volumen geométrico del recipiente; no es el
  volumen de líquido. Al alcanzarla, la integración se detiene (evento
  `capacidad_maxima`). **No se modela rebose.**
- `area` solo sirve para la serie `nivel`.
- `presion_sistema` es **obligatoria** con energía: el trabajo de
  desplazamiento la usa y no se toma la de omisión. Si falta:
  `LAB_FALTA_ESPECIFICACION` sobre `sistema.p`.
- Modelo energético: solo `ideal_incompresible`.
- Un inventario inicial cero con energía se rechaza
  (`LAB_DIN_INVENTARIO_INICIAL_CERO`): sin líquido no hay T.

**Física.** El volumen de control sigue la superficie del líquido:
`V_liq = n/ρ`. Las ecuaciones son:

- `dn/dt = F_ent − F_sal`
- `dU/dt = F_ent h_ent − F_sal h_sal + Q − P dV_liq/dt`, con `U = n u(T)`

El trabajo de frontera es un término explícito del balance:
`{tk}.W_frontera`, con clave `trabajo_frontera:{tk}`. Las ecuaciones
`{tk}:volumen_liquido` y `{tk}:trabajo_de_frontera` lo calculan.

**Respuesta.**

- Variables nuevas: `{tk}.V_liquido` y `{tk}.W_frontera`. Si se declararon,
  también los parámetros `{tk}.capacidad_maxima` y `{tk}.area`.
- Series: `{tk}.V_liquido`, `{tk}.W_frontera` y `{tk}.nivel` (esta última,
  solo con `area`).
- Eventos:
  - `vaciado`: con energía, se dispara al bajar de 1e-6 veces el
    inventario inicial; más abajo la T del residuo no se resuelve.
  - `capacidad_maxima`.
- Estacionario: con `F_ent = F_sal` y `n` como dato, sale de la energía
  lineal `u(T) = u(T_ent) + Q/F_ent`. Hay dos casos especiales:
  - `F = 0` y `Q = 0`: indeterminado.
  - `F = 0` y `Q ≠ 0`: contradictorio.
- Transferencia estacionario → temporal: **no** (el balance general sigue
  fuera, como en el §22).

**Verificado** contra estas referencias analíticas:

- `n(t)` lineal;
- `T = T_ent + (T0 − T_ent)(n0/n)^(F_ent/(F_ent−F_sal))`;
- la exponencial cuando `F_ent = F_sal`;
- el cerrado con Q;
- una integración aparte escrita en T.

Además:

- el evento de capacidad se dispara en t = 187,5 s;
- la conservación integra el trabajo de frontera.

**Ejemplos:** `estudio-tanque-termico-{llenado,vaciado,capacidad,estacionario,sin-presion}-{peticion,respuesta}.json`.

### 24.2 Hito B: dos circuitos materiales unidos por una interfaz térmica

**Petición.** Dos piezas `entrada`, cada una con su propia cadena
(entrada → volumen → salida). Los circuitos **no comparten corrientes**:
solo los une una conexión `termica` con su G en `interfaces_termicas`.
Cada alimentación lleva su F, x y T en `especificaciones`. Si un circuito
usa balance general, sus caudales van en `seleccion_variables`.

**Combinaciones admitidas:**

- inventario constante en los dos circuitos (estacionario y temporal);
- balance general en uno e inventario constante en el otro (solo
  temporal).

**Se rechazan:**

- más de dos alimentaciones;
- dos circuitos sin energía o con reacción;
- estacionario con balance general;
- mezclar los dos circuitos.

**Respuesta.**

- Las dos alimentaciones son variables de clase `entrada`.
- La conservación global suma las fronteras de cada circuito:
  `conservacion.energia.global.corrientes_usadas` lista los pares de los
  dos.
- La interfaz se cancela una vez en `global:energia`.
- `capacidades.topologia.alimentaciones` pasa a `[1, 2]`.
- La transferencia funciona con inventario constante en los dos circuitos.

**Verificado:**

- `expm` de las dos T, también por tramos con escalones;
- una integración aparte con el tanque de cantidad variable;
- el estacionario igual al límite de `expm`;
- ida y vuelta de la transferencia.

**Ejemplos:** `estudio-circuitos-serpentin{,-llenado,-estacionario}-{peticion,respuesta}.json`.

### 24.3 Hito C: pared sólida

**Petición.** Una pieza nueva `{"id": "pw", "tipo": "pared"}` se une a los
fluidos con conexiones `termica`, una por lado. Cada conexión lleva su G en
`interfaces_termicas`. Se declara en el campo nuevo `paredes`:

```json
"paredes": [
  {"bloque_id": "pw", "almacenamiento": "con_almacenamiento",
   "capacidad": {"valor": 20, "unidad": "kJ/K"}}
]
```

**Cómo declarar la capacidad:**

- `capacidad` (`J/K` o `kJ/K`), **o** `masa` (`kg`, `g`, `t`) junto con
  `calor_especifico` (`J/(kg*K)` o `kJ/(kg*K)`). No las dos
  (`LAB_ESPECIFICACION_EXCLUYENTE`).
- `C_w > 0`.

**Pared sin almacenamiento** (`"almacenamiento": "sin_almacenamiento"`):

- no lleva capacidad ni condición inicial;
- necesita al menos dos interfaces con `ΣG > 0`.

**Condición inicial** de una pared que almacena: T o U en
`estudio.condiciones_iniciales` con `bloque_id` de la pared, igual que un
volumen. Si falta: `LAB_DIN_CONDICION_INICIAL_FALTANTE`, y el recuento cita
`pw.T`.

**Física.**

- Con almacenamiento: `U_w = C_w (T_w − T_ref)`, con el mismo `T_ref` que
  el fluido, y `dU_w/dt = Σ_k G_k (T_k − T_w)`. `U_w` es un estado del
  mismo vector que los fluidos.
- Sin almacenamiento: `0 = Σ_k G_k (T_k − T_w)`, es decir,
  `T_w = Σ G_k T_k / Σ G_k`. Es algebraica y explícita, y con dos
  interfaces equivale a `1/G_eq = 1/G_1 + 1/G_2`.

**Respuesta.**

- Variables:
  - `pw.T` (algebraica);
  - con almacenamiento, además `pw.U` (diferencial) y `pw.capacidad`
    (parámetro; si se dio como m·c, la `nota` lo dice).
- Ecuaciones: `pw:energia` (balance con `terminos[]`) y, con
  almacenamiento, `pw:cierre_energetico`. Sin almacenamiento, `pw:energia`
  es algebraica, con `latex_activo` `0 = …` y `acumulacion: null`.
- `global:energia`:
  - su lado izquierdo pasa a `d/dt(Σ_v U_v + Σ_w U_w)`, **solo cuando hay
    paredes**;
  - cada interfaz fluido–pared se cancela una vez (`cancelaciones`).
- `clasificacion.paredes`: `{con_almacenamiento, sin_almacenamiento, ley,
  algebraica}`.
- Series: `pw.T` y, con almacenamiento, `pw.U`.
- Conservación:
  - `conservacion.energia.por_volumen` gana una entrada por pared, con
    `pared: true`;
  - sin almacenamiento, además `residuo_instantaneo_max` de su suma de
    flujos;
  - `global.paredes` lista las paredes que almacenan.
- Constantes de tiempo: tipo `termica_pared`.
  - Con almacenamiento: `tau_w = C_w / ΣG`.
  - Sin almacenamiento: `G_equivalente_serie_W_K`.
- Estacionario: `estados.pw = {T, U, capacidad_termica, Q_neto, pared:
  true}`.
- `contraste_estacionario` para fluidos **cerrados** con pared y sin calor
  exterior. Es nuevo y de tipo `limite_con_total_conservado`: `T_lim =
  Σ C_k T_k(0) / Σ C_k`, con `capacidades_J_K` y `T_final`. Los cerrados
  **sin** pared no cambian: siguen con `evaluado: false`.
- Transferencia estacionario → temporal con pared:
  `LAB_DIN_TRANSFERENCIA_NO_POSIBLE`. La condición inicial de la pared no
  forma parte del contrato de transferencia; el estacionario sí se
  resuelve.

**Diagnósticos:**

| Caso | Código |
|---|---|
| Pared con pared | `LAB_PUERTO_INCOMPATIBLE` |
| Pared sin energía | `LAB_DIN_INTERFAZ_NO_SOPORTADA` |
| Pared sin declarar | `LAB_FALTA_ESPECIFICACION` |
| T inicial en una pared sin almacenamiento | `LAB_DIN_INICIAL_INCONSISTENTE` |
| Pared algebraica con una sola interfaz | `LAB_DIN_ESPECIFICACION_NO_ADMITIDA` |
| Camino directo en paralelo a la pared | advertencia (es físico, pero suele ser un error de montaje) |

**Recuento y catálogo:**

- `pw.capacidad` es un parámetro con ruta
  `{campo: "paredes", clave: {bloque_id, parametro}, indice}`.
- `pw.T` es una inicial requerida solo si la pared almacena.
- `pw.U` es un estado.

**Verificado:**

- Tres capacidades cerradas (agua caliente | pared | tanque) frente a
  `expm(A t) x0`, con error < 1e-6 K (medido ≈ 3e-9 K). Coincide con LSODA
  y con Radau.
- Límite ponderado exacto.
- La pared algebraica frente a dos capacidades con G en serie, y su T
  frente a `(G_1 T_1 + G_2 T_2)/(G_1+G_2)`.
- `C_w → 0` tiende a la algebraica.
- Masa × calor específico es igual a la capacidad.
- Unidades kJ.
- U inicial en lugar de T.
- Invertir las conexiones da la misma física.
- Dos circuitos abiertos con la pared del serpentín frente a `expm` afín de
  3×3.
- Estacionario igual al límite, y sin almacenamiento igual a con
  almacenamiento.

**Ejemplos:** `estudio-pared-{tres-capacidades,sin-almacenamiento,masa-calor-especifico,serpentin,serpentin-estacionario,sin-temperatura-inicial}-{peticion,respuesta}.json`.

### 24.4 Hito D: vapor y condensación

**Auditoría de viabilidad (primero).**

- **Propiedades.** IAPWS-IF97 (R7-97(2012)), regiones 1, 2 y 4, tal como
  las implementa `chemicals.iapws` (chemicals 1.5.2, ya instalado). El
  módulo `core/vapor_if97.py` las combina en
  `saturacion(P) → (T_sat, h', h'')`, en J/mol con `M = 18.015268 g/mol`.
- **Referencia de las tablas.** Los 12 valores de verificación publicados
  en IF97 (tablas 5, 15, 35 y 36: `h_1`, `h_2`, `P_sat` y `T_sat`) se
  reproducen con un error relativo ≤ 2e-9.
- **Referencia independiente.** Comparado con IAPWS-95 (otra formulación)
  entre 20 kPa y 1 MPa:
  - `T_sat` difiere ≤ 8 mK;
  - `h_fg` difiere ≤ 0,01 %.
  - A 1 atm: `T_sat = 373,124 K` y `h_fg = 2256,5 kJ/kg`.
- **Dominio:** 611,213 Pa ≤ P ≤ 16,529 MPa, es decir, `P_sat(623,15 K)`.
  Por encima, la saturación pasa por la región 3, que no está
  implementada.
- **Conclusión.** Las propiedades bastan para un primer régimen concreto.
  **No** bastan para un volumen bifásico transitorio general. El
  proveedor líquido del motor sigue sin saturación ni entalpías de ambas
  fases, y no se usa aquí.

**Régimen implementado.** Una pieza `{"id": "cv", "tipo": "camara_vapor"}`
representa vapor saturado a P declarada que condensa sobre una superficie.
Es **cuasiestacionaria**: el almacenamiento del lado de vapor se desprecia
explícitamente, y lo dicen `terminos_descartados`. Tiene purgador: entra
vapor saturado y sale solo condensado saturado.

Ecuaciones:

- `0 = F_v − F_c` (`cv:materia`);
- `0 = F_v h'' − F_c h' − Q` (`cv:energia`), donde `Q` es el calor que cede
  por sus interfaces.

Q (que depende de T_sat y de lo que toca) **determina** `F_c = Q/h_fg`: no
se imponen los dos. No es un volumen bifásico transitorio: no tiene
estados.

**Petición.** El campo nuevo es `camaras_vapor`:

```json
"camaras_vapor": [
  {"bloque_id": "cv", "presion": {"valor": 70, "unidad": "kPa"},
   "suministro_maximo": {"valor": 0.15, "unidad": "mol/s"}}
]
```

- `presion` es obligatoria, sin valor por omisión.
- `suministro_maximo` es opcional: es el vapor disponible.
- La cámara se une con conexiones `termica` a un volumen con energía o a
  una pared, y no puede unirse a otra cámara.
- Solo con agua: una especie con CAS 7732-18-5. Otra sustancia:
  `LAB_DIN_MODELO_ENERGETICO_NO_SOPORTADO`.
- El condensado **no** entra a ningún volumen.

**Respuesta.**

- Variables:
  - `cv.p` (parámetro, Pa);
  - `cv.suministro_maximo`, si se declaró;
  - las algebraicas `cv.T` (T_sat), `cv.h_vapor` y `cv.h_liquido` (J/mol,
    referencia IF97: líquido saturado en el punto triple; las dos con la
    misma), `cv.F_vapor` y `cv.F_condensado`.
- Ecuaciones: `cv:saturacion`, `cv:entalpia_vapor`, `cv:entalpia_liquido`,
  `cv:materia` y `cv:energia`. Las dos últimas tienen `terminos[]` y
  `acumulacion: null`.
- `global:energia`:
  - quedan los términos de frontera `F_v h''` y `−F_c h'`;
  - la interfaz con la cámara se cancela;
  - su lado izquierdo no cambia, porque la cámara no almacena.
- `clasificacion.camaras_vapor`: régimen, qué determina, propiedades, fuera
  de régimen y `no_es`.
- Series: `cv.T`, `cv.Q` (positivo si condensa), `cv.F_vapor`,
  `cv.F_condensado` y `cv.condensado_acumulado` (mol). Esta última es una
  cuadratura propia del integrador.
- Conservación:
  - entrada `{bloque_id: "cv", camara_vapor: true, condensado_mol,
    energia_cedida_J, residuo_integrado_max}`, que compara `∫F_c h_fg` con
    `∫Q`: dos cuadraturas distintas;
  - `global.camaras_vapor` lista las cámaras.
- Estacionario (circuitos abiertos): `estados.cv = {T, p, Q, F_vapor,
  F_condensado, F_condensado_kg_s, h_vapor, h_liquido, camara_vapor: true}`.
- `contraste_estacionario` de cerrados con una cámara: `tipo:
  "limite_frontera_termica"`, con `T_lim = T_sat`.
- Transferencia estacionario → temporal con cámara:
  `LAB_DIN_TRANSFERENCIA_NO_POSIBLE`.

**Fuera del régimen validado** (código nuevo `LAB_DIN_FUERA_DE_REGIMEN`).
Los dos eventos son terminales y dejan el estado en `parcial`:

| Evento | Cuándo se dispara |
|---|---|
| `regimen_condensacion` | Q < −ΣG × 1e-6 K: lo que toca la cámara superó T_sat y evaporaría. El margen cubre el redondeo cerca del equilibrio, donde Q → 0⁺. |
| `suministro_de_vapor` | `F_c > suministro_maximo`. |

- Si ya se cumple en t = 0, no se integra nada. El evento lleva `instante:
  0` y la nota "Detectado en el estado inicial".
- Un estacionario fuera de régimen no se presenta:
  `LAB_DIN_FUERA_DE_REGIMEN`, con estado `invalido`.

**Verificado:**

| Caso | Referencia |
|---|---|
| Tanque cerrado | `T_sat − (T_sat−T0) e^{−Gt/C}`; condensado acumulado `C (T−T0)/h_fg` |
| Tanque abierto | Exponencial hacia `(F c_p T_ent + G T_sat)/(F c_p + G)`; estacionario y `F_c` analíticos |
| Pared algebraica | `G_eq` en serie |
| Pared con capacidad | `expm` afín |
| Instante del evento de suministro | Analítico, tras un escalón de F (< 1e-3 s) |
| Instante del evento de régimen | Analítico, con una resistencia que lleva el tanque por encima de T_sat |

En todos los casos de trayectoria, el error es < 1e-6 K (medido ≈ 3e-9 K)
y la conservación global es < 1e-10.

**Ejemplos:** `estudio-vapor-{tanque-cerrado,tanque-abierto,tanque-abierto-estacionario,con-pared,suministro-agotado,deja-de-condensar}-{peticion,respuesta}.json`.

**Sigue sin soportarse (y se rechaza o no se ofrece):**

- volumen bifásico transitorio (estados de masa, U y calidad, con P
  variable);
- vapor sobrecalentado o húmedo a la entrada;
- subenfriamiento del condensado;
- condensado que entra a un volumen (mezclaría la referencia IF97 con la
  del líquido ideal);
- escalones de P;
- incondensables;
- otra sustancia.

### 24.5 Migración para el frontend

- **Piezas nuevas:** `pared` y `camara_vapor`. Solo admiten conexiones
  `termica`, cada una con su G en `interfaces_termicas`.
- **Campos nuevos de la petición:**
  - `paredes[]` y `camaras_vapor[]`;
  - en `almacenamiento[]`, `capacidad_maxima` y `area`.

  Entran en la identidad del modelo (`modelo_id`) y en las huellas por
  parte.
- **Unidades** (`GET /laboratorio/estudios/unidades`): magnitudes nuevas
  `area`, `longitud` (solo presentación), `masa` y `calor_especifico`.
  Rutas nuevas en `campos`:
  - `paredes[].capacidad`, `paredes[].masa`, `paredes[].calor_especifico`;
  - `camaras_vapor[].presion`, `camaras_vapor[].suministro_maximo`;
  - `almacenamiento[].capacidad_maxima`, `almacenamiento[].area`.
- **Recuento:**
  - parámetros con `ruta.campo` igual a `paredes` o `camaras_vapor` (la
    clave de la presión es `{"parametro": "presion"}`);
  - iniciales `pw.T` de las paredes que almacenan.
- **Respuesta:** claves nuevas, todas presentes **solo** cuando el montaje
  tiene la pieza:
  - `clasificacion.paredes` y `clasificacion.camaras_vapor`;
  - `conservacion.energia.global.paredes` y `.camaras_vapor`;
  - entradas de `por_volumen` con `pared` o `camara_vapor`;
  - `estacionario.estados.{pared|camara}`.
- **Capacidades:**
  - las filas nuevas de §24.1–24.4;
  - `fisica.pared_solida: true`;
  - `fisica.condensacion: "cuasiestacionaria (camara_vapor, IAPWS-IF97)"`;
  - `topologia.alimentaciones: [1, 2]`.

  Ninguna bandera habilita otras topologías: lo admitido es lo que está en
  `combinaciones`.

**Compatibilidad:**

- Los `modelo_id` de los montajes anteriores no cambian; se comprueban en
  las cuatro baterías nuevas.
- Resultados físicos anteriores: sin cambios.
- `residuo_terminos` de un balance **sin** acumulación (pared sin
  almacenamiento, cámara) se escala con el mayor flujo de la trayectoria.
  Cerca del equilibrio esos flujos tienden a cero, y el cociente por
  muestra mediría solo el redondeo. En los montajes **con pared**, todas
  sus ecuaciones se escalan así: el global de dos cerrados con una pared
  algebraica se cancela entero, y `Σ dU/dt` es solo el redondeo de
  `Q_1 − Q_2`. Los demás montajes siguen igual.

**Archivos:**

- `core/dinamica.py`;
- `core/vapor_if97.py` (nuevo);
- `core/unidades_estudios.py`;
- `core/errores.py` (`LAB_DIN_FUERA_DE_REGIMEN`);
- `backend/schemas_estudios.py`;
- `backend/nucleo_estudios.py`;
- `backend/ejemplos_estudios.py`;
- `backend/main.py` (ruta de unidades);
- `tests/validar_estudios_{tanque_termico,circuitos,pared,vapor}.py`;
- `docs/ejemplos/estudio-{tanque-termico,circuitos,pared,vapor}-*`.

**Lo que queda fuera de este encargo** (colas históricas sin mezclar):

- transferencia estacionario → temporal con pared o cámara;
- volumen bifásico transitorio;
- momento, overrides por propiedad, `latex_expandido` y el resto de
  colas anteriores.

### 24.6 Seguimiento: magnitud de `tk.area` en el catálogo

Respuesta a `frontend/INTEGRACION_ENTREGA_24.md`.

**El fallo.** En `catalogo_variables`, `tk.area` salía con `magnitud:
null`. La magnitud interna `"A"` no estaba en
`unidades_estudios.MAGNITUD_DE_VARIABLE`.

**La corrección.** `"A"` se asocia a la magnitud `area` (`m2`) y su nombre
de presentación es "Area". En todos los ejemplos era la única variable sin
magnitud.

**Ejemplos regenerados desde el endpoint**, entre ellos
`estudio-tanque-termico-capacidad-respuesta.json`. `npm test` pasa.

**Regresión** en `tests/validar_estudios_tanque_termico.py`: ninguna
variable del catálogo de ningún ejemplo puede quedar sin magnitud.

**Sin cambios:** resultados, `modelo_id` y revisión del contrato (13).

## 25. Correcciones de la auditoría del motor (A1–A9)

Respuesta a `frontend/CORRECCIONES_AUDITORIA_MOTOR_CLAUDE.md` y a la
auditoría `docs/AUDITORIA_MOTOR_2026_10_11.md`. No amplía la física: corrige
el cálculo y la validación de combinaciones que ya se aceptaban.

**Pruebas:**

- La regresión normal es `tests/validar_correcciones_auditoria.py`: 69
  comprobaciones, con referencias escritas en la prueba. La ejecuta
  `run_tests.py`.
- El script de la auditoría (`tests/auditoria_motor_acoplado.py`) sigue
  siendo la comprobación independiente. Sus **15 sondas cumplen** y sale con
  código 0.
- `revision_contrato` sigue en 13: no hay piezas ni campos de petición
  nuevos. **Hay que recargar el servicio.**

### 25.1 Hito 1: mismo modelo y datos respetados

**A1. Estacionario del balance general con intercambios.**

- **Antes:** la energía salía de `u(T) = u(T_ent) + Q/F`, sin las
  interfaces.
- **Ahora:** `_energia_estacionaria_bg` resuelve `0 = dU/dt` del **residuo
  completo** del ensamblaje: corrientes, calor, interfaces directas, paredes
  y cámaras. Es el mismo `_Sistema.evaluar` que integra el temporal.
  - Con los caudales fijados, el residuo es afín en las energías (modelo
    `ideal_incompresible`). Se resuelve una vez, sin iterar.
  - Se clasifica con el rango del jacobiano: núcleo → indeterminadas;
    `[J | f0]` de mayor rango → contradicción.
- **Resultado:** la sonda da 345,827468 K, igual que la referencia, con un
  residuo de 8e-12 W en el mismo ensamblaje.

**Verificado**, cada caso contra
`T = (F c_p T_ent + G T_sat + Q)/(F c_p + G)`:

| Caso | G |
|---|---|
| Cámara directa | G |
| Pared sin almacenamiento | G en serie |
| Pared con almacenamiento | G en serie |
| Cámara con calor exterior | G |

En los cuatro, además:

- el temporal que arranca de ese estacionario, con las mismas fronteras, no
  se mueve (< 1e-8 K);
- todos los balances quedan evaluados.

Ejemplos publicados sin intercambios (T = 360 K): sin cambio numérico.

El balance general con un volumen cerrado vecino ya se rechazaba
(`LAB_DIN_CIERRE_NO_SOPORTADO`), y sigue así.

**A2. Compatibilidad con escalas por magnitud.**

- **La causa:** `_analisis_lineal` usaba como escala el mayor valor de b,
  mezclando mol y mol/s.
- **Ahora:** cada incógnita y cada fila se adimensionalizan con la escala de
  **su** magnitud (`rango.escalas = {F_mol_s, n_mol}`). Tras resolver, cada
  dato original se comprueba contra su valor declarado: ninguno se modifica
  para obtener una solución.
- `rango.metodo` dice ahora "rango NUMERICO con tolerancia, global para este
  sistema; no aritmética exacta".

**Verificado:**

- Inventarios × 1, × 1e4 y × 1e8 dan siempre la contradicción, con `in.F`
  y `out.F` en conflicto.
- `mol/h` y `mol/s` dan el mismo diagnóstico.
- Caudales iguales con inventarios enormes siguen siendo compatibles.

**Comprobación final antes de `resuelto`.**

- **Ruta lineal (balance general).** `estacionario.comprobacion_final =
  {comprobado, no_comprobado, residuo_materia, residuo_energia, fallos}`.
  Sustituye la solución en el residuo completo y comprueba:
  - la materia y la energía de cada volumen y pared;
  - los datos originales;
  - caudales e inventarios ≥ 0;
  - la capacidad;
  - T en el dominio;
  - el régimen de cada contacto de cada cámara y su suministro.

  Si algo falla, el estado es `invalido`, con el código del fallo, y la
  solución no se presenta.
- `residuo_terminos` de **todas** las ecuaciones se evalúa con esa misma
  evaluación. Antes se saltaban los términos sin valor. La verificación
  global de energía lleva ahora su residuo medido; antes era `null`.
- **Ruta de Newton.** Gana `comprobacion_final` con lo comprobado: el
  residuo completo, las restricciones, el dominio y los contactos de las
  cámaras.

### 25.2 Hito 2: bases cinéticas por ley (A3)

`ReaccionCinetica.tasas()` recibe ahora una **caché `{base: a_i}`** de la
misma (T, x). Cada ley (directa e inversa) toma la de **su** base y la
calcula si falta.

- Un array suelto (la forma antigua) se interpreta como la base de la
  directa, y nunca se entrega a una inversa que declaró otra.
- Callers corregidos:
  - el lote (`core/lote.py`), que antes usaba la base de la primera reacción
    para todas;
  - los dos CSTR de `core/cinetica.py`;
  - los estudios (`core/dinamica.py`).
- La inversa derivada de K mantiene sus restricciones.

**Verificado** con acetato de etilo y ácido butírico (γ ≠ 1, comprobado en
la prueba):

- la inversa de base actividad vale exactamente `γ₂ x₂`;
- permutar las leyes no cambia la trayectoria del lote (antes había 2,17 mol
  de diferencia);
- en el CSTR, permutar las leyes solo permuta los avances;
- cada avance coincide con su ley evaluada aparte.

### 25.3 Hito 3: dominio y eventos

**Comprobación inicial.** Ahora existe una comprobación del dominio inicial
(`_dominio_inicial`), que corre en el ensamblaje de todo estudio temporal.
Por eso `/validar` y `/resolver` dicen lo mismo. El motivo: los eventos del
integrador detectan **cruces**, y un estado que ya empieza fuera no cruza
nada.

Comprueba:

- caudales derivados ≥ 0;
- líquido dentro de la capacidad;
- cada contacto de cada cámara;
- el suministro de vapor.

Si algo falla, el estado es `invalido`, sin `resultados`, con el código del
fallo y las piezas y conexiones afectadas.

**Al reiniciar en cada escalón** se repite la comprobación con las entradas
**nuevas**:

- Si falla, se para en el instante del escalón. El evento lleva
  `al_reiniciar: true` y la nota correspondiente.
- La última muestra se presenta con las entradas del tramo anterior.

**Corrección asociada.** Los eventos que evalúan el sistema (caudal
negativo, cámara) usan las entradas del tramo que se integra.

- **Antes:** en el instante final de un tramo veían ya las del siguiente,
  porque las entradas son continuas por la derecha.
- **Consecuencia:** un caudal negativo causado por un escalón aparecía como
  cruce al final del tramo anterior, con una muestra negativa publicada.

**A4. Capacidad.**

| Situación inicial | Resultado |
|---|---|
| Por encima de la capacidad | `invalido` (`LAB_VALOR_FUERA_DE_DOMINIO`) |
| Justo en el límite, llenándose | `invalido` |
| Justo en el límite, vaciándose | `resuelto` |
| Por debajo | el evento analítico de siempre |

**A5. Salida negativa.** Una salida de −900 mol/s desde t = 0 da
`invalido` antes de integrar (`LAB_DIN_SALIDA_DE_DOMINIO`), citando el
reactor y sus conexiones. Un escalón que vuelve negativa la salida para en
el escalón, sin publicar ninguna muestra negativa. Un caudal negativo no se
reinterpreta como corriente invertida.

**A6. Cámara por contacto.**

- El régimen se vigila **por contacto**: un evento por interfaz, con su G en
  el margen. Antes se miraba el neto.
- El evento lleva `conexion_id`.
- El estacionario (por Newton y por la ruta lineal) comprueba cada contacto.
- El suministro agregado se sigue comprobando aparte.
- **No** se amplía el régimen a contactos que evaporan: eso sería otra
  entrega, con su formulación propia.

**A7. Fuente compartida.** Una fuente conectada a más de un volumen se
rechaza en la topología (`LAB_TOPOLOGIA_NO_SOPORTADA`, estado
`no_soportado`), citando todas sus conexiones. Su potencia es un total
único: repartirla necesitaría una ley de reparto, que no se fabrica. La
guarda de conservación de `/resolver` se mantiene.

**Cambio visible.** Un estado inicial fuera de régimen, que antes daba
`parcial` con una muestra (ejemplo: una cámara con el tanque por encima de
T_sat), ahora es `invalido`. `tests/validar_estudios_vapor.py` se actualizó
en ese caso.

### 25.4 Hito 4: rutas públicas y procedencia

**A8.** `DiagramaFlujo.resolver(max_iteraciones=None)` y
`resolver_con_reciclo(max_iteraciones_internas=None)` dejan que el
Orquestador calcule su tope (`len(bloques) + 2`). Un tope pedido
explícitamente se respeta.

- Verificado con 30 bloques, en orden y en orden inverso: salida 30.
- Esto no habilita N volúmenes en `/estudios`.

**A9.** `Corriente` rechaza un F, T o P no finito y una composición no
finita. El flujo cero sigue admitido.

**Procedencia.**
`calculo.proveedor_termodinamico.identificador` describe ahora las
propiedades **usadas**, unidas con " + ":

- el modelo energético declarado;
- el proveedor líquido;
- los coeficientes de actividad UNIFAC, si una ley tiene base `actividad`;
- K_eq(T), si una inversa se deriva del equilibrio;
- IAPWS-IF97, si hay cámaras de vapor.

El estudio solo material sigue siendo
`ninguno (modelo material; densidad declarada)`.

**Supuestos efectivos.** La semántica **no cambia**: `adiabatico` es
`global OR local`. Ahora se publica en `balances[].supuestos_efectivos`:

```json
"supuestos_efectivos": {"adiabatico": {
  "valor": true, "origen": "global",
  "global": true, "local": false,
  "regla": "global OR local: un 'false' local no revoca un 'true' global"}}
```

- `origen` puede ser `global`, `local`, `global y local` o `ninguno`.
- Un `false` local junto a un `true` global da además una advertencia
  (`LAB_DIN_DATO_NO_USADO`): el `false` no se usa.
- No se introduce la herencia triestado. Si se quiere, necesita su propia
  migración.

### 25.5 Lo que cambia en las respuestas publicadas

Se regeneraron los ejemplos desde los endpoints y se compararon con los
anteriores, ignorando identificador e instante del cálculo.

**Ningún resultado numérico cambia:** series, estados, conservación,
instantes de eventos y `modelo_id` son idénticos.

Solo cambian:

- **Campos añadidos:**
  - `balances[].supuestos_efectivos`;
  - `estacionario.comprobacion_final`;
  - `estacionario_lineal.rango.escalas`;
  - `eventos[].conexion_id`.
- **Textos y mediciones:**
  - `estacionario_lineal.rango.metodo` y
    `estacionario_lineal.energia.metodo`;
  - el texto del evento de régimen de la cámara, que ahora cita el
    contacto;
  - el `residuo` medido de `global:energia` en el estacionario del balance
    general (antes `null`);
  - en ese mismo caso, `residuo_terminos` pasa de ≈1e-16 a 0.
- **Firmas de transferencia:** cambian solo porque incluyen el
  identificador del cálculo, que lleva el instante.

**Script de la auditoría.** Su función auxiliar `series()` fallaba cuando
`resultados` es `null`, que es justo lo que ahora devuelve un rechazo.
Se cambió `r.get("resultados", {})` por `(r.get("resultados") or {})` en
dos líneas. El criterio de las sondas no cambia: ya preveía `None`. Las
evidencias de `docs/auditoria_motor_2026_10_11/evidencias.json` no se han
sobrescrito: al ejecutar el script se regeneran.

### 25.6 Límites que siguen

- **Ecuaciones antes de resolver.** El ensamblaje real con datos pendientes
  sigue sin publicarse: un estudio incompleto devuelve el modelo vacío
  (§23.6). Es una ampliación de contrato y queda propuesta así: que
  `/validar` devuelva `modelo.variables` y `modelo.ecuaciones` del
  ensamblaje parcial (el que ya construye `_modelo_para_recuento`), con
  `ejecutada: false` y una marca `pendiente` en los términos sin valor. No
  se ha implementado ni se ha sustituido por ecuaciones orientativas.
- **Comprobación final del temporal.** En el temporal se limita al dominio
  inicial y de cada reinicio, más los eventos y la conservación integrada.
  No hay una comprobación muestra a muestra de todas las desigualdades
  entre eventos.
- **Generalización.** N volúmenes, ramificaciones, lazos y un residuo DAE
  general `R(t, z, dz/dt) = 0` quedan para una entrega con sus propios
  criterios.

**Archivos:**

- `core/dinamica.py`;
- `core/cinetica.py`;
- `core/lote.py`;
- `core/corriente.py`;
- `core/diagrama_flujo.py`;
- `backend/nucleo_estudios.py`;
- `tests/validar_correcciones_auditoria.py` (nuevo);
- `tests/validar_estudios_vapor.py`;
- `tests/auditoria_motor_acoplado.py` (solo la función auxiliar `series`);
- `docs/ejemplos/*` (regenerados).

## 26. Bases de materia, dimensiones, selección de datos y dominio en la trayectoria

Respuesta a `frontend/SIGUIENTE_CLAUDE_BASES_DIMENSIONES.md`. Cada hito se
entregó por separado, sobre el mismo ensamblaje y sin solvers nuevos.

- `revision_contrato` pasa a **14**; `schema_version` no cambia.
- Prueba nueva: `tests/validar_estudios_base_dimensiones.py`, con 55
  comprobaciones.
- **Hay que recargar el servicio.**

### 26.1 Hito 1: el mismo balance en base molar o másica

**Contrato (versión 1).** El estado interno sigue siendo **molar**. La masa
entra por **alias declarados** que el servidor convierte en una
normalización previa (`core/base_materia.py`). Es la misma función para la
identidad del modelo y para el cálculo.

| Dónde | Alias | Conversión | Condición |
|---|---|---|---|
| `especificaciones` de una alimentación | `variable: "m_dot"` (kg/s, kg/h, g/s, t/h) | `F = m_dot / Σ x_i M_i` | La composición de esa corriente está dada (n − 1 fracciones) o hay una sola especie |
| `estudio.condiciones_iniciales` | `magnitud: "m"` con `componente` (kg, g, t) | `n_i = m_i / M_i` | La especie está identificada |
| `estudio.entradas_temporales` | `variable: "m_dot"` | Igual que en especificaciones | La composición es constante (sin escalones de x en esa corriente) |
| `seleccion_variables` | `{s}.m_dot`, `{v}.m{i}` | Igual | Igual |

**Masa molar.** Sale de la identidad química (CAS) con
`chemicals.identifiers`. Se publica en
`base_materia.masas_molares = [{componente, cas, M, unidad: "kg/mol",
procedencia}]`. Nunca se deduce de una etiqueta.

**Una variable, no dos.** Un alias y su variable molar son la misma
variable:

| Caso | Diagnóstico |
|---|---|
| Iguales (tolerancia relativa 1e-9) | `LAB_DIN_ESPECIFICACION_REDUNDANTE`, advertencia citando las dos (`in.F` e `in.m_dot`) |
| Distintos | `LAB_DIN_ESPECIFICACION_CONTRADICTORIA`, citando las dos con su campo e índice |
| Caudal másico de una mezcla sin composición dada | `LAB_DIN_CONVERSION_MASICA_NO_DETERMINADA` (código nuevo) |

No se elige una masa molar por omisión. El campo `F` sigue siendo molar:
`kg/h` en `F` se sigue rechazando (`LAB_UNIDAD_INCOMPATIBLE`).

**Identidad.** El `modelo_id` se calcula sobre la petición ya normalizada.
Los valores convertidos se redondean a 12 cifras significativas (cambio
relativo < 5e-13). Así, el mismo tanque dado en kg y kg/h o en mol y mol/s
tiene el mismo `modelo_id`.

**Presentación.** El campo nuevo de la petición es `base_materia:
{"version": 1, "presentacion": "molar" | "masica"}`.

- Por omisión es `molar`.
- Es solo presentación: no entra en la identidad.

Con `masica`, además de lo molar se publica:

- **Series:**
  - `{v}.m{i}` y `{v}.m_total` (kg);
  - `{s}.m_dot` (kg/s) y `{s}.w{i}` (kg/kg). La corriente intermedia es
    **una** serie compartida;
  - `{v}.fuente_masica{i}` con reacción (kg/s, por especie: no se suprime
    porque el total sea cero);
  - `{interfaz}.tasa_masica`.
- **`conservacion.masa`**, en kg, por volumen y global. Se mide **sin**
  las integrales de avance: la química conserva la masa por
  `Σ_i M_i ν_i = 0`, aunque cambien los moles (`moles_totales_cambian`).
- **Estacionario:** `m`, `m_total`, `m_dot`, `m_dot_i` y `w` en los
  estados.
- **Modelo:**
  - los parámetros `masa_molar.M{i}`;
  - las variables de clase **`alias`** (`{v}.m{i}`, `{s}.m_dot`, con
    `alias_de`);
  - las relaciones `tipo: "relacion_de_base"` (`{v}:masa_{i}`,
    `{s}:caudal_masico`), que **no cuentan** como ecuaciones.

  Los grados de libertad y las incógnitas son idénticos en las dos bases.
- **Respuesta:** `base_materia` siempre: versión, presentación,
  `estado_interno`, masas molares y `conversiones`. Cada conversión lleva
  el campo y el índice de origen, lo declarado, la variable del modelo, el
  valor en SI y la relación.

**Verificado:**

- **Tanque** (balance general con 5 kW) dado en kg, kg/h y g/s: trayectoria
  **idéntica bit a bit** a la molar, el mismo `modelo_id` y los mismos GL.
- **Mezcla de benceno y tolueno** (M distintas) en kg/h y kg:
  - las mismas trayectorias;
  - `w_i = x_i M_i / Σ x_j M_j`;
  - corriente compartida;
  - conservación de masa < 1e-10;
  - un escalón en `m_dot` equivale a un escalón en F.
- **A → 2B:** los moles cambian, la masa se conserva y las fuentes másicas
  por especie suman cero.
- **Masas molares** frente a los pesos atómicos IUPAC.
- **Alias** redundantes y en conflicto, incluido `n` frente a `m` de la
  misma especie.

**Alcance anunciado** en `capacidades.base_materia`: agua pura y mezclas de
especies identificadas, en todas las combinaciones de estudios.

**No:**

- la fracción másica como dato;
- `F_salida` en masa;
- un caudal másico de composición incógnita.

### 26.2 Hito 2: ecuaciones del ensamblaje y análisis dimensional

**Modelo parcial** (la propuesta de §25.6, implementada). Si la física se
lee entera y solo faltan datos del estudio (una inicial, un horizonte),
`/validar` y `/resolver` publican el **mismo ensamblaje** que se
resolvería, con:

- `modelo.parcial = true` y `nota_parcial`;
- todas las ecuaciones con `ejecutada: false`;
- `variables[].pendiente = true` en las variables sin dato (citadas por un
  error, o entradas y parámetros sin valor);
- `ecuaciones[].variables_pendientes` y `terminos[].pendiente`.

El modelo completo lleva `parcial: false`. Si no se puede ensamblar (por
ejemplo, falta un cierre), sigue vacío, como antes.

**Análisis dimensional** (`core/dimensiones.py`). Tipa **expresiones del
ensamblaje**, no el LaTeX:

- **Balances y verificaciones:** desde `terminos[]` y `acumulacion`. Son
  los mismos términos que se evalúan. El coeficiente de un término lleva
  ahora `unidad_coeficiente`: ν es adimensional y ΔH está en J/mol.
- **Constitutivas:** desde una forma tipada que el motor construye con la
  ecuación (`_formas_tipadas`). Cubre:
  - conductancia `Q = G (T₁ − T₂)`;
  - cierre energético `U = Σ n_i u_i(T) + C_w (T − T_ref)`;
  - pared `U_w = C_w (T_w − T_ref)`;
  - entalpía de corriente;
  - mezcla perfecta (x y T);
  - inventario total y concentración;
  - restricción de inventario `Σ n = ρV`;
  - salida lineal `F = kN`;
  - volumen de líquido `n/ρ`;
  - trabajo de frontera `P/ρ (F_ent − F_sal)`;
  - leyes cinéticas (directa, inversa y avance, con la unidad de k
    declarada);
  - ley de transferencia de materia y energía transportada;
  - saturación y entalpías de la cámara;
  - las relaciones de base másica.
- **Unidades:** con pint, en SI. Para mostrarlas se usa la unidad coherente
  (W y no J/s).

Cada ecuación lleva `dimensional`:

```json
{"estado": "compatible" | "incompatible" | "no_evaluable", "motivo": ...,
 "fuente": "terminos tipados del ensamblaje (...)",
 "lado_izquierdo": {"forma": "derivada temporal", "variables": ["tk.U"],
                    "unidad": "J/s", "latex_unidad": ..., "dimension": ...},
 "terminos": [{"indice", "rol", "latex", "bloque_id", "conexion_id", "clave",
               "factores": [{"variable_id", "unidad", "naturaleza"}],
               "unidad", "latex_unidad", "dimension", "estado", "motivo"}],
 "terminos_en_conflicto": [], "unidad_ecuacion": "W", "latex_unidad": "\\mathrm{W}"}
```

El resumen está en `modelo.analisis_dimensional`: `{compatibles,
incompatibles, no_evaluables, nota}`.

**Reglas:**

- Todos los términos y el lado izquierdo deben tener la misma dimensión y
  el mismo factor a SI.
- Una **temperatura absoluta no puede ser factor** de un producto: lo que
  multiplica a una conductancia o a una capacidad es una diferencia, con
  `naturaleza: "temperatura_diferencia"`. Una diferencia entre K y °C no
  se resta.
- Un cero (por ejemplo, la pared sin almacenamiento, `0 = Σ Q`) conserva
  la dimensión de sus términos.
- **`no_evaluable`**, con su motivo, en:
  - las condiciones que fijan un valor (`adiabatico`, `temperatura
    impuesta` y la salida dada);
  - las derivadas de restricciones.

  El momento no figura.
- Una ecuación incompatible es un fallo del motor:
  `LAB_DIN_DIMENSION_INCOMPATIBLE` (código nuevo) y estado `invalido`.

**Verificado:**

- **Todos los ejemplos:** 0 ecuaciones incompatibles y más de 1000
  compatibles. Se comprueban explícitamente:
  - energía del tanque, F·h, interfaz y frontera, en W;
  - cámara, materia en mol/s y energía en W;
  - ξ ΔH en W y ν ξ en mol/s;
  - P dV/dt en W;
  - pared con diferencia de temperaturas;
  - base másica en kg y kg/s.
- **Casos mal tipados**, rechazados citando su término:
  - un término F sin h en un balance de energía (término 1);
  - `Q = G T` (temperatura absoluta como factor);
  - una diferencia K − °C;
  - una variable sin unidad (`no_evaluable`).
- **Modelo parcial:** las mismas ecuaciones que el completo, con sus
  dimensiones.

Un análisis compatible no demuestra conservación ni exactitud: lo dice la
`nota`.

### 26.3 Hito 3: selección de datos e incógnitas

**Publicado desde el backend** en cada entrada de `catalogo_variables`:

| Campo | Contenido |
|---|---|
| `papel_seleccionado` | `especificacion`, `incognita`, `estado`, `calculada`, `parametro` o `alias` |
| `ruta` | `{campo, clave, indice}`: el sitio exacto de la petición donde se da o se elige, el mismo que usa el recuento |
| `efecto_en_recuento` | Texto: un dato resta un grado de libertad; un estado necesita su inicial y no cuenta como especificación; una calculada sobreespecificaría; un alias no cuenta |

El frontend no deduce GL contando entradas: `puede_especificarse`,
`puede_calcularse` y `motivo_limitacion` siguen siendo los del backend.

**Sin cambios** en el balance general directo e inverso ni en la selección
explícita (§22). Ya se prueban especificaciones directas e inversas,
alternativas, dependencias, contradicciones, redundancia compatible y
unidades equivalentes (`validar_estudios_unidades_especificaciones.py`,
`validar_correcciones_auditoria.py`). El rango se declara numérico y GL = 0
no sustituye a la consistencia.

**Propuesta, no implementada:** ampliar la selección a más especies, a la
energía y a las variables térmicas. Para cada imposición:

- **T de un volumen como dato:** reemplaza la ecuación de energía como
  determinante de T. El balance pasa a despejar Q de la fuente (ya existe
  como modo `temperatura`, de índice 2). En temporal, U deja de ser estado
  y su inicial sobra.
- **Q como incógnita:** solo con T dada. Si no, faltaría una ecuación.
- **Caudal de salida como dato** con inventario constante: contradice la
  restricción (F_sal = F_ent + Σν ξ); solo es admisible si lo que se libera
  es la cantidad (balance general).
- **Cantidad como dato en temporal:** no. Es un estado y necesita su
  inicial consistente; elegir «calcular» no lo exime.
- **Parámetros constitutivos** (G, k, L, C_w): no pasan a ser incógnitas
  sin datos que los identifiquen (problema inverso con medidas). No se
  ofrece.
- **Multiespecie en el balance general:** las fracciones de cada corriente
  son incógnitas acopladas con la mezcla perfecta; requiere el análisis
  no lineal (no un rango lineal). Es una entrega propia.

### 26.4 Dominio a lo largo de la trayectoria

`dominio_trayectoria` es un campo nuevo de la respuesta temporal.
Comprueba **cada desigualdad en cada muestra publicada**:

- `n_i ≥ 0` por volumen y especie;
- `F ≥ 0` por corriente;
- T dentro de `[T_min, T_max]`;
- `V_liq ≤ V_max`;
- `Q ≥ −G × 1e-6 K` por contacto de cada cámara;
- `F_c ≤ suministro`.

Cada desigualdad dice qué la vigila **entre muestras**
(`evento_entre_muestras`). Los eventos posibles son `agotamiento`,
`vaciado`, `dominio (inventario)`, `capacidad_maxima`, `dominio_termico`,
`caudal_negativo`, `regimen_condensacion` y `suministro_de_vapor`. Cuando
no hace falta evento, lo dice: por ejemplo, F ≥ 0 por construcción.

Cada desigualdad lleva además su mínimo, la tolerancia, las muestras fuera
y el primer instante en que salió.

Si alguna muestra sale del dominio sin que la haya detenido un evento, la
trayectoria **no se certifica**: estado `no_convergente` y
`LAB_DIN_SALIDA_DE_DOMINIO`. Nada se corrige en silencio.

**Alcance declarado:**

- **Muestras:** la comprobación muestra a muestra cubre lo publicado.
- **Entre muestras:** lo localizan los eventos, por cambio de signo en cada
  paso del integrador.
- **Inicio y reinicios:** los cubre la comprobación previa (§25.3).

En todos los ejemplos temporales, 0 muestras fuera.

### 26.5 Cambios visibles y migración

**Petición:**

- `base_materia` (opcional);
- alias `m_dot` (especificaciones y escalones), `m` (iniciales),
  `{s}.m_dot` y `{v}.m{i}` (selección).

**Unidades** (`/laboratorio/estudios/unidades`):

- magnitudes nuevas `flujo_masico`, `masa_molar` y `fraccion_masica`;
- `masa` amplía su semántica;
- `campos` nuevos para los alias;
- `magnitud_de_variable` gana `m`, `m_dot`, `M` y `w`.

**Respuesta** (todo aditivo):

- `base_materia` y `dominio_trayectoria`;
- `modelo.parcial`, `modelo.analisis_dimensional` y
  `modelo.ecuaciones[].dimensional`;
- `terminos[].unidad_coeficiente`;
- `catalogo_variables[].{papel_seleccionado, ruta, efecto_en_recuento}`;
- con la presentación másica: series y conservación en masa, variables
  `alias` y relaciones `relacion_de_base`.

**Cambio visible.** Un estudio con la física completa y datos del estudio
pendientes ahora publica su modelo parcial; antes era vacío. El estado no
cambia (`invalido`). La comprobación de `tests/validar_estudios_recuento.py`
que fijaba el contrato antiguo se actualizó a este.

**Códigos nuevos:**

- `LAB_DIN_CONVERSION_MASICA_NO_DETERMINADA`;
- `LAB_DIN_DIMENSION_INCOMPATIBLE`.

**Sin cambios:** resultados numéricos, estados, series, eventos y
`modelo_id` de todos los ejemplos. Se regeneraron desde los endpoints y se
compararon. Durante la entrega una inserción mía quitó `T` y `h` de las
corrientes del estacionario por Newton; se detectó en esa comparación, se
corrigió y ahora hay una regresión que lo vigila.

**Ejemplos nuevos:**

- `estudio-base-masica-{tanque,mezcla,reaccion,sin-composicion}`;
- `estudio-modelo-parcial`.

**Interfaz.** Un único interruptor, apagado por omisión, para mostrar
`dimensional`. Es del frontend; el backend lo publica siempre.

**Archivos:**

- `core/base_materia.py` (nuevo);
- `core/dimensiones.py` (nuevo);
- `core/dinamica.py`;
- `core/unidades_estudios.py`;
- `core/errores.py`;
- `backend/nucleo_estudios.py`;
- `backend/schemas_estudios.py`;
- `backend/ejemplos_estudios.py`;
- `tests/validar_estudios_base_dimensiones.py` (nuevo);
- `docs/ejemplos/*`.

## 27. Topología, fronteras pendientes y fuentes únicas

Respuesta a `frontend/ENCARGO_CLAUDE_TOPOLOGIA_FRONTERAS_Y_FUENTES.md`. No
se amplía la física: ni más volúmenes, ni bifurcaciones, ni solvers.

- **Hito A:** se reproduce. Se corrigen tres defectos de referencias y
  queda cubierto por pruebas.
- **Hito B:** añade un campo opcional (`fronteras_materiales`).
- **Hito C:** verifica el comportamiento existente y completa las
  referencias de la fuente.

`revision_contrato` pasa a **15**; `schema_version` no cambia. La prueba
nueva es `tests/validar_topologia_fronteras_fuentes.py` (73 comprobaciones,
por los IDs T1–T5, F1–F5 y Q1–Q6). **Hay que recargar el servicio.**

### 27.1 Hito A: insertar un volumen en una cadena

```
Antes:   in → cv1 → out                       (c1, c2)
Después: in → cv1 → m12 → cv2 → out           (c1, c5, c6, c2)
```

Se conservan `in`, `cv1`, `out` y la conexión `c2`, que ahora llega a
`out` desde `cv2`. `m12`, `cv2`, `c5` y `c6` son nuevos.

**Ya cumplía** (se añade la evidencia, sin reescribir nada):

- `m12.F` es **una** variable compartida (`compartida: true`, con
  `bloque_ids` `[m12, cv1, cv2]` y `conexion_ids` `[c5, c6]`).
- Sale de `cv1` (signo −1) y entra a `cv2` (+1).
- Se cancela en `global:materia_especie_0` (`cancelaciones` con
  `corriente:m12`), desde los términos.
- Cuenta una vez: 3 especificaciones independientes de caudal, no 4.
- `out.F` pertenece a `out` y `cv2` (la frontera final), no a `cv1`.
- **T2:** 700 y 800 mol a 600 s, con un error < 1e-9. Un valor distinto
  (2,5 mol/s) da 400 y 1100 mol. 7200 mol/h equivale a 2 mol/s.
- **T3:** 36 kmol/h en la salida da 10 mol/s en los tres caudales, con los
  inventarios como datos.
- **T1:** sin `m12.F` ni la inicial de `cv2`, el estado es `invalido` y los
  dos pendientes salen con su ruta. No se copia nada de `cv1`.

**Defectos corregidos:**

- **T4.** Un dato sobre un bloque inexistente se diagnosticaba
  (`LAB_REFERENCIA_INEXISTENTE`), pero el recuento lo perdía: estado
  `incompleto` y sin referencias. Ahora `recuento.desglose.datos_invalidos`
  lleva cada dato con su campo, clave e índice exactos. Cubre
  especificaciones, almacenamiento, iniciales, escalones, selección,
  balances, paredes, cámaras y fronteras.
- **T5.** El rechazo de una bifurcación citaba solo el volumen. Ahora cita
  sus vecinos y todas sus conexiones (`cv1`, `in`, `m12`, `out1`; `c1`,
  `c5`, `c7`) y dice que no se elimina una rama ni se fabrica un reparto.
- **Recuento.** El texto de `recuento.advertencia` todavía decía «rango
  exacto y global». Ahora dice «rango numérico con tolerancia», coherente
  con §25.

**Qué sigue valiendo al insertar y qué hay que volver a dar.** El backend
no migra nada: verifica lo que recibe.

| Dato | Dónde se declara | Tras insertar |
|---|---|---|
| F de la alimentación | `in.F` (frontera de entrada) | Sigue valiendo |
| Inicial de V1 | `estudio.condiciones_iniciales` de `cv1` | Sigue valiendo |
| F de la salida | `out.F` (frontera final) | Sigue valiendo, ahora de `cv2` → `out` |
| Cierre de V1 | `almacenamiento` de `cv1` | Sigue valiendo |
| F de la corriente nueva | `m12.F` (corriente compartida) | **Nuevo**: hay que darlo (o calcularlo en estacionario) |
| Inicial y cierre de V2 | `cv2` | **Nuevos**: no se copian de V1 |
| Algo de un bloque retirado | — | `LAB_REFERENCIA_INEXISTENTE`, con su ruta |

### 27.2 Hito B: intención de frontera material

**Ningún campo existente** expresaba la intención:

- `balances_por_volumen` elige familias de balance, no fronteras;
- `balances[].sistema` es una salida inferida.

El campo nuevo es opcional, está versionado y va por volumen:

```json
"fronteras_materiales": {
  "version": 1,
  "volumenes": [
    {"bloque_id": "nuevo", "intencion": "pendiente"},
    {"bloque_id": "cv1",   "intencion": "cerrado"},
    {"bloque_id": "cv2",   "intencion": "abierto", "fronteras_pendientes": ["salida"]}
  ]
}
```

- `intencion`: `pendiente`, `cerrado` o `abierto`. Con `null`, la entrada
  no declara nada y se infiere como siempre.
- `fronteras_pendientes`: solo con `abierto`. Lista de `entrada` y
  `salida`.
- **Alcance de «cerrado»:** sin corrientes de materia con el exterior del
  modelo (entradas, salidas o corrientes). Una interfaz de materia entre
  volúmenes del modelo no lo abre. No implica adiabático ni rígido.

| Caso | Comportamiento | Código |
|---|---|---|
| `pendiente` | Borrador: no es pieza aislada ni cuenta en el número de volúmenes; nunca se interpreta como cerrado ni como listo | `LAB_DIN_FRONTERA_PENDIENTE` (pendiente) |
| `cerrado`, sin corrientes | Igual que la inferencia actual. Ejecutable solo si la combinación lo es y están todos sus datos | — |
| `cerrado`, con corrientes | Contradicción con el volumen y sus conexiones reales; no se borra nada | `LAB_DIN_FRONTERA_CONTRADICTORIA` (conflicto) |
| `abierto`, frontera pendiente sin conectar | Pendiente; no es un caudal cero ni una variable inventada | `LAB_DIN_FRONTERA_PENDIENTE` |
| `abierto`, falta una frontera no declarada pendiente | Régimen de una sola frontera (llenar o vaciar sin la otra) **no soportado** en esta entrega | `LAB_TOPOLOGIA_NO_SOPORTADA` |
| `abierto`, frontera pendiente ya conectada | Advertencia: lo que falte lo dice el recuento | `LAB_DIN_DATO_NO_USADO` |
| `bloque_id` inexistente / no es un volumen / duplicado | Diagnóstico, no lo descarta el parser | `LAB_REFERENCIA_INEXISTENTE` / `LAB_DIN_ESPECIFICACION_NO_ADMITIDA` / `LAB_ESPECIFICACION_DUPLICADA` |
| Valor no admitido o versión ≠ 1 | Diagnóstico | `LAB_DIN_ESPECIFICACION_NO_ADMITIDA` |

**Referencias para Codex.** Cada pendiente o contradicción lleva en el
recuento:

```json
{"variable_id": null, "funcion": "frontera", "codigo": "LAB_DIN_FRONTERA_PENDIENTE",
 "ruta": {"campo": "fronteras_materiales.volumenes",
          "clave": {"bloque_id": "cv2", "frontera": "salida"}, "indice": 0},
 "bloque_ids": ["cv2"], "conexion_ids": []}
```

- La clave es `{bloque_id, intencion}` cuando lo pendiente o contradicho es
  la intención.
- No se inventa un `conexion_id` que no existe ni una variable del
  catálogo.
- Las contradicciones citan las conexiones reales.

**Respuesta.** `fronteras_materiales[]`, siempre, por volumen:

- `intencion_solicitada` (o `null`);
- `interpretacion_efectiva`. Valores posibles:
  - `pendiente (borrador)`;
  - `cerrado (declarado)`;
  - `cerrado (inferido: sin corrientes de materia)`;
  - `abierto (declarado)`;
  - `abierto (inferido: …)`;
  - `abierto con fronteras pendientes`;
  - `abierto: regimen no soportado`;
  - `contradictorio`;
- `fronteras_conectadas: {entrada: [...], salida: [...]}`;
- `fronteras_pendientes`, `contradicciones` y `alcance_cerrado`.

**Reutilizado:**

- `pendientes` y `contradicciones`, porque los dos códigos nuevos están en
  esos conjuntos;
- `recuento`, con su estado (`incompleto`, `conflicto` o `no_evaluable`) y
  sus referencias.

**Compatibilidad e identidad:**

- Sin la declaración, todo sigue igual. Se comprobó que ningún ejemplo
  anterior cambia de estado, series, `modelo_id`, estacionario ni
  diagnósticos.
- La declaración **no entra en `modelo_id`**: o confirma la interpretación
  existente (la física es la misma) o bloquea la resolución.
- Ausente, `null` y cero siguen siendo distintos.
- La ida y vuelta JSON por Node real conserva la identidad y el recuento.

### 27.3 Hito C: una fuente exterior única

**Ruta oficial de Q.** Una pieza `calor` conectada a **un** volumen, más su
especificación `{bloque_id: <fuente>, variable: "Q", valor, unidad}`. Los
escalones van en `entradas_temporales`, sobre la misma fuente. **No existe
una Q local en el volumen**: `{bloque_id: <volumen>, variable: "Q"}` da
`LAB_VARIABLE_DESCONOCIDA`, y no se inventa. Mostrar la fuente junto al
volumen no la duplica, porque es una sola pieza.

**Verificado (comportamiento existente):**

| ID | Caso | Resultado |
|---|---|---|
| Q1 | La misma petición reenviada | Mismo `modelo_id` y recuento. Un solo término `calor:q1` en su volumen y en el global; la misma Q dos veces da `LAB_ESPECIFICACION_DUPLICADA` |
| Q2 | Q `null` / ausente / 0 W | Pendiente `q1.Q` (ruta `especificaciones[3]`) / pendiente que cita `q1.Q` / dato válido |
| Q3 | Adiabático efectivo + fuente / T + Q / energía desactivada | `LAB_SUPUESTO_INCOHERENTE` / `LAB_ESPECIFICACION_EXCLUYENTE` / `LAB_DIN_BALANCE_INCOHERENTE` (§21), sin ejecutar |
| Q4 | Dos fuentes en un volumen / una fuente en dos | `LAB_TOPOLOGIA_NO_SOPORTADA`, sin sumar ni repartir |
| Q5 | Cerrado con Q | `T = T0 + Q t / C`, error < 1e-8 K; con 0,75 kW y 26,85 °C, la misma trayectoria |
| Q5 | Abierto (n = 1000, c_p = 75, F = 10, Q = 750 W) | `T = 301 − e^{−t/100}`, error < 1e-7 K; el estacionario del mismo modelo da 301 K |
| Q6 | Dos cerrados con G y Q exterior en uno | Exponencial de matriz afín, error < 1e-7 K. `interfaz:it` se cancela y queda solo `calor:q`. Por separado: `U_total(t) − U_total(0) = Q t`, términos por volumen con residuo < 1e-9 y citas de piezas y conexiones (`q`, `cq`, `it`) |

**Corregido.** Varios diagnósticos de la fuente no citaban su conexión, o
no citaban la variable:

- Q `null` o inválida;
- Q ausente, que ahora cita además `q1.Q`;
- T + Q;
- dos fuentes en un volumen.

Ahora citan la conexión de la fuente. Las referencias del recuento de una
variable de fuente (`q1.Q`) también llevan esa conexión.

`capacidades.fuentes_exteriores` lo publica:

- la ruta oficial;
- `fuentes_por_volumen: 1` y `destinos_por_fuente: 1`;
- omisiones y exclusiones.

No se anuncian varias fuentes por volumen.

### 27.4 Pruebas, ejemplos y archivos

**Pruebas:**

- Batería completa del backend: **40 suites en verde**.
- `npm test` del frontend, sin tocarlo.
- Las 15 sondas de la auditoría: **cumplen**, con código 0.

**Tolerancias:**

- 1e-9 mol en las trayectorias materiales;
- 1e-7 a 1e-8 K en las térmicas;
- 1e-12 mol/s en el estacionario inverso.

**Ejemplos nuevos** (`docs/ejemplos/estudio-*-{peticion,respuesta}.json`):

- `insercion-antes`, `insercion-incompleta`, `insercion-completa`,
  `insercion-estacionario-inverso` e `insercion-con-rama`;
- `frontera-pendiente`, `frontera-cerrados-declarados`,
  `frontera-abierta-pendiente` y `frontera-contradictoria`;
- `fuente-q-pendiente` y `fuente-tanque`.

**Archivos:**

- `core/dinamica.py`;
- `core/errores.py`;
- `backend/schemas_estudios.py`;
- `backend/nucleo_estudios.py`;
- `backend/ejemplos_estudios.py`;
- `tests/validar_topologia_fronteras_fuentes.py` (nuevo);
- `docs/ejemplos/*`.

**Pendientes reales** (no se declaran hechos):

- **Bifurcación (una salida a dos destinos):** rechazada. Ampliarla
  requiere un reparto declarado y otra entrega.
- **Llenar o vaciar con una sola frontera:** diagnosticado como no
  soportado.
- **Frontera exterior de temperatura:** fuera de alcance.

### 27.5 Seguimiento: convenciones de inserción de la mesa

Respuesta a `frontend/INTEGRACION_INSERCION_MESA.md`. El backend se
verifica con las convenciones que aplica el editor, partiendo de la
solicitud de su mesa de QA (`frontend/qa-insercion-mesa.json`, copiada en
la prueba). No hay cambios de contrato: la revisión sigue en 15.

| ID | Edición del editor | Resultado del backend |
|---|---|---|
| I1 | Insertar sobre `c4` (sale de un volumen): `c4` queda en el tramo **posterior** (`v2 → out`) | Recién insertado: pendientes la relación de salida de `v2` (`LAB_DIN_CIERRE_FALTANTE`, ruta `almacenamiento` con `{bloque_id: v2, parametro: cierre}`) y su inicial (`estudio.condiciones_iniciales`). Al elegir `balance_general`, pasa a pendiente `m1.F`. Completado: 700 / 800 mol a 600 s. `out.F` sigue en `out` (y `v2`) por `c4` |
| I2 | Insertar sobre `c1` (llega de una alimentación): `c1` queda en el tramo **anterior** (`in → v0`) | Pendiente el cierre de `v0`. Completado (50 mol, 2 mol/s): `n0 = 50 + t`, `n1 = 100 + t`. `in.F` alimenta ahora a `v0` |
| I3 | Insertar en la conexión aguas abajo de una corriente compartida (tres volúmenes) | `LAB_TOPOLOGIA_NO_SOPORTADA` (`no_evaluable`), citando los tres volúmenes y **todas** sus conexiones |
| I4 | Conectar dos volúmenes sin borrar sus salidas ni entradas (rama y mezcla) | Un rechazo por cada volumen, con sus conexiones reales; no se borra ninguna |

**Nota para la UI.** Mientras falte el cierre del volumen nuevo, el caudal
de la corriente nueva **no** aparece como pendiente. Depende del cierre:
con `inventario_constante` lo determina la restricción, y con
`balance_general` es un dato. Por eso el recuento declara
`faltantes_es_cota_inferior: true` y lo lista en cuanto se elige el cierre.

**Ajuste.** El rechazo por número de volúmenes cita ahora también las
conexiones materiales de esos volúmenes; antes citaba solo los bloques.

**Disponible para la mesa.** La intención de frontera que el informe da por
pendiente ya está en §27.2 (`fronteras_materiales`). Sirve, por ejemplo,
para marcar como `pendiente` un volumen recién creado que aún no se ha
conectado.

**Pruebas.** Nueve comprobaciones I1–I4 en
`tests/validar_topologia_fronteras_fuentes.py` (82 en total). La batería
completa del backend (40 suites), `npm test` y las 15 sondas pasan. Los
ejemplos regenerados no cambian.

### 27.6 Seguimiento: el modo automático de la mesa

Respuesta a `frontend/INTEGRACION_ENTREGA_27.md`. El editor envía como
`abierto` con `fronteras_pendientes` los volúmenes a medio conectar, y como
`pendiente` los que no tienen corrientes. Dos de esos patrones daban
diagnósticos de más, que tapaban el pendiente preciso.

**Corregido:**

| Patrón | Antes | Ahora |
|---|---|---|
| Volumen sin corrientes, `abierto` con `["entrada", "salida"]` pendientes, junto a una cadena de dos volúmenes | Además de sus dos pendientes, salía como pieza aislada y como tercer volumen (`no_soportado`) | Solo sus dos `LAB_DIN_FRONTERA_PENDIENTE`, con `clave {bloque_id, frontera}`; estado `incompleto` |
| Único volumen del montaje como borrador (`pendiente`, o `abierto` con fronteras pendientes) | Además, `LAB_TOPOLOGIA_NO_SOPORTADA` («hay 0 volúmenes») | Solo sus pendientes |

**Regla.** Un volumen `pendiente`, o `abierto` con fronteras declaradas
pendientes, es un sistema a medio dibujar:

- su diagnóstico es el de su intención o sus fronteras;
- no cuenta como pieza aislada ni en el número de volúmenes;
- no se resuelve hasta completarlo.

`cerrado` sin conexiones sigue siendo un volumen real y no cambia.

**Para la UI:**

- Las respuestas llevan `revision_contrato >= 15` y
  `fronteras_materiales[]`, como exige la comprobación del editor.
- El servicio de `localhost:8004` **hay que recargarlo** para tener §27.

**Pruebas:**

- 4 comprobaciones nuevas en `tests/validar_topologia_fronteras_fuentes.py`
  (86 en total).
- Batería completa del backend: 40 suites en verde.
- `npm test` pasa.
- 15 sondas: cumplen.
- Los ejemplos regenerados no cambian.

Revisión del contrato: sigue en 15. Es una corrección de diagnósticos, sin
campos nuevos.
