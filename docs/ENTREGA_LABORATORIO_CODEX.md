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
