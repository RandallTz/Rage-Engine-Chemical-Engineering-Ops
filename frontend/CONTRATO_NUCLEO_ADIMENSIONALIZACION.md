# Contrato del núcleo de adimensionalización (A0)

Fecha: 16 de octubre de 2026. Autor: Claude (núcleo). Destinatario: Codex (interfaz, lectores, persistencia).

Este archivo fija el intercambio entre `/adimensionalizacion` y el núcleo científico. El plan y el registro de avance siguen en `PLAN_ADIMENSIONALIZACION_ECUACIONES.md`. **Integración implementada por Codex:** endpoints de §7, lector de respuestas, botón «Adimensionalizar» y documento local v2 con mapas de §8. El núcleo conserva su contrato de documento v1 mediante un adaptador explícito.

## 1. Ubicación única del núcleo

`core/adimensionalizacion/` (Python, en la raíz del repositorio). Es el único lugar con álgebra científica. Usa `fractions` (exacto) y `pint` solo para interpretar unidades. No usa sympy: no figura en `requirements.txt` y no se añadieron dependencias.

| Módulo | Responsabilidad |
|---|---|
| `lector.py` | Lector estricto del documento v1 en el servidor (no confía en el cliente) |
| `dimensional.py` | A1: inferencia racional exacta, compatible/incompatible/indeterminado, unidades |
| `algebra.py` | Forma canónica de expresiones, linealidad de operadores, sustitución estructural |
| `transformacion.py` | A2: sustitución, regla de la cadena, factor global; A3: objetivos por rango exacto |
| `formulacion.py` | Formulación publicada: términos, grupos, restricciones, pasos, certificado |
| `grupos_pi.py` | Espacio nulo racional, bases alternativas, cambio de base |
| `nucleo.py` | `procesar(solicitud) -> resultado` y `capacidades()` |

`core/dimensiones.py` (ensamblaje) no se reutilizó ni se modificó: tipa términos del motor, no este AST. Del cliente no se copia nada: `expresionesMotor.ts`, `unidadesMotor.ts` y `operadores.ts` siguen como estaban.

El cliente valida estructura y presenta árboles; **no** simplifica, no extrae coeficientes y no decide estados de objetivos.

## 2. Solicitudes

```ts
type SolicitudNucleo = {
  formato: "adimensionalizacion.solicitud"; version: 1;
  operacion: "analizar" | "transformar" | "adimensionalizar";
  documento: Documento;            // documento de intercambio v1 o v2 (§13), con `exploracion` opcional
  formaId?: string;                // obligatorio en "transformar"; opcional (forma base) en "adimensionalizar"
  transformaciones?: Transformacion[]; // mapas generales (§10.2); "transformar" y "adimensionalizar"
  opciones?: OpcionesBusqueda;     // solo "adimensionalizar" (§10.1)
};
```

`analizar` no admite campos opcionales.

La exploración usa sin cambios el formato que ya genera `prepararExploracion` (`solicitud_exploracion_adimensional`, versión 1). El núcleo la acepta tal cual, valida `modelo`, `formaBase`, `config` y cada propuesta, y rechaza operaciones distintas de `normalizar_magnitud_coeficiente` con `conservarSigno: true`.

Un campo o una versión desconocidos se rechazan; no hay migración silenciosa.

## 3. Decisiones del contrato (los puntos de A0 de la entrega)

**Dimensiones.** `null` = pendiente (incógnita); `{}` = dimensión uno. Exponentes `{n, d}` reducidos, sin ceros. Los nombres de base son libres: el núcleo no depende de ellos, así que `{L,T,N}` y `{L,T,C}` dan las mismas ecuaciones (está probado). Las unidades se proyectan sobre las bases SI `L, M, T, I, Theta, N, J`. **Temperatura se llama `Theta`** (el lector del cliente no admite `Θ`).

**Ceros y números.** El número `0` es compatible con cualquier dimensión; cualquier otro número es adimensional. `c + 1` con `c` dimensional es incompatible.

**Unidades.** Se interpretan con pint. Si el símbolo no declara dimensión, la unidad la fija (`origen: "unidad"`). Si declara las dos y no coinciden, el error apunta a `simbolos[i].unidad`. Una unidad con desplazamiento (`degC`, `degF`) marca una temperatura **absoluta afín**: se rechaza una escala exclusivamente multiplicativa sobre ella (código `temperatura_afin`), pero se admite un mapa afín con referencia declarada (§10.2). `K` y `delta_degC` sí admiten escala. Una escala `cantidad` exige que la variable use bases SI. El núcleo publica `valorSI` y `unidadSI`.

**Dependencias.** `Simbolo.dependeDe` y `funciones[].dependeDe` (dependencia explícita en t/x además de los argumentos) deciden qué sale de una derivada. Un símbolo no constante sin dependencias declaradas se supone dependiente de todo (no se extrae). `D(c)` se trata como llamada opaca: se transforma como `D(c_ref c_ad)` y su núcleo conserva dimensiones, por lo que la normalización queda `parcial` con motivo `nucleos_dimensionales`. Para extraer una escala `D*` hace falta la declaración de v2 (§8).

**Operadores.** Solo coordenadas cartesianas. `gradiente` de varias coordenadas es vectorial y solo se admite dentro de una `divergencia` con las mismas coordenadas. Un producto admite como máximo un factor vectorial, y una igualdad tiene que ser escalar (si no, código `rango`). Los operadores de una coordenada se conservan como nodos. Los de varias coordenadas se desarrollan en componentes cartesianas cuando alguna coordenada se escala, porque cada coordenada puede tener su propia escala.

**Identidad de términos.** `terminoId = "<ecuacionId>:<ruta>"`, con la misma ruta que `terminosExplorables` (las sumas anidadas se aplanan). Si un sumando sintáctico se desarrolla en varios coeficientes (por ejemplo `k (c - c^2)`), cada parte recibe el sufijo `#1`, `#2`, …, y el id sin sufijo no identifica un coeficiente único. La operación `analizar` publica el catálogo completo. Las condiciones usan `<condicionId>:<ruta>`.

**Objetivos v1.** `Forma.objetivos[].termino` se empareja con un término de la ecuación por estructura canónica, ignorando el factor numérico. `valor` es el valor exigido del **coeficiente efectivo tal como está escrito, con su signo**: para `-a c^2` se pide `-1`. Si se pide `+1` con `a > 0`, el resultado es `incompatible` con código `signo`. En la exploración (`normalizar_magnitud_coeficiente`) se exige magnitud 1 y se conserva el signo.

**Factor global.** Cada igualdad se divide por la magnitud del coeficiente de su lado izquierdo cuando es un único término monomial. Eso se publica aparte (`factorGlobal`) y no es una elección de escala. Por eso un objetivo sobre el término temporal sale `dependiente`. Si el factor contiene un parámetro declarado nulo, no se divide (aviso `sin_factor_global`).

**Signos.** Un parámetro negativo se representa como `-|p|`, así que las escalas resueltas usan `abs(p)` y el signo queda en la ecuación. Signo desconocido: el objetivo queda `pendiente` (`signo_desconocido`). Parámetro nulo: el objetivo es `incompatible` (`parametro_nulo`) y nunca se divide por él. Una escala dada por expresión de signo negativo se rechaza. Si su signo es desconocido, se publica el supuesto `positivo`.

**Condiciones y ubicación.** Se transforman con la misma sustitución y conservan su tipo. El contrato v1 no declara qué extremo del dominio usa una condición de frontera. El núcleo transforma los extremos del dominio y la igualdad, y publica `ubicacion: "frontera del dominio (el contrato v1 no declara el extremo)"`. La ubicación precisa es una ampliación de v2 (§8).

**Vínculo y vigencia.** Cada resultado lleva:

```ts
vinculo: { documentoId: string; modeloId: string; modeloRevision: number; formaId: string;
           eleccion: { escalas: Escala[]; objetivos: Forma["objetivos"]; presentacion: Forma["presentacion"] };
           firma: string /* "sha256:…" del servidor */ }
```

**Regla del cliente:** un resultado está vigente solo si `modeloId` y `modeloRevision` coinciden con el documento y `eleccion` es igual en profundidad a `{escalas, objetivos, presentacion}` de la forma. `formaId` solo no basta. La `firma` es informativa: la calcula el servidor sobre JSON canónico de Python, y el cliente no debe intentar reproducirla, porque el formato de los flotantes difiere entre JavaScript y Python.

**Fallos.** `estado ∈ {"correcto", "rechazado", "no_soportado", "requiere_datos"}`. `requiere_datos` significa que hay dimensiones indeterminadas: `dimensional.faltantes` dice qué preguntar. Si no es `correcto`, el resultado **solo** contiene `vinculo` (si se pudo leer), `diagnosticos` y `dimensional` (si se analizó): nunca ecuaciones, grupos ni certificado. El cliente debe descartar cualquier resultado anterior de esa forma cuyo vínculo ya no coincida.

## 4. Resultado de `analizar`

`dimensional = { estado, simbolos: [{ id, dimension | null, origen: "declarada"|"unidad"|"inferida"|"indeterminada"|"sin_uso", unidad?: {texto, dimension, afin} }], funciones, faltantes: string[] }` y `terminos: [{ id, ecuacionId, lado, ruta, expresion, divididoEn }]`.

**Datos indispensables (para la vista mínima).** Si el estado es `indeterminado`, `faltantes` da un conjunto mínimo de dimensiones que basta declarar para que el núcleo infiera todas las demás. Se prefieren variables (`c`, `t`, `x`) antes que parámetros, y los ceros no cuentan como dato. Ejemplo probado: en `∂c/∂t = D∇²c + kc − ac²` con todo pendiente, `faltantes = ["c", "t", "x"]`; al declarar solo esas tres, `D`, `k`, `a` y `ell` quedan `inferida`. El cliente solo tiene que preguntar por esos símbolos. `transformar` y `adimensionalizar` exigen el estado `compatible`; si no lo es, responden `requiere_datos` con esos `faltantes`.

`diagnosticos: [{ ruta, codigo, severidad: "error"|"aviso", mensaje, simbolos? }]`. Las rutas usan el estilo del lector del cliente (`ecuaciones[0].derecha.argumentos[2]`, `simbolos[3].unidad`, `forma.escalas[1].valor.unidad`). Códigos de A1: `dimension_incompatible`, `dimension_indeterminada`, `rango`, `unidad_no_reconocida`, `unidad_no_comparable`.

## 5. Resultado de `transformar` (estado `correcto`)

| Campo | Contenido |
|---|---|
| `simbolos` | Símbolos **nuevos** (los del modelo se referencian por id). Escala: `{id: "<v>_ref", nombre, rol: "escala", variableId, dimension, estado, valor, cantidad?}`. Variable adimensional: `{id: nuevoNombre, nombre, rol: "variable_adimensional", rolOrigen, variableId, dimension: {}, dependeDe}` |
| `escalas` | `{simboloId, escalaId, estado: "libre"|"dada"|"dada_por_expresion"|"determinada"|"relacionada", valor}`. `relacionada` = determinada en función de escalas libres |
| `libres` | Escalas libres restantes: la formulación es una familia parametrizada por ellas |
| `normalizacion` | `{estado: "completa"|"parcial", motivos: [{codigo: "variables_sin_transformar"|"nucleos_dimensionales"|"grupos_dimensionales", …}]}` |
| `ecuaciones` | `{igualdad, factorGlobal, terminos: [{id, lado, ruta, original, coeficiente, grupoId, nucleo, dimensionNucleo}]}` |
| `dominios` | `{id, variableId (nueva), desde, hasta}` |
| `condiciones` | `{id, tipo, dominioId, ecuacion, factorGlobal, terminos, ubicacion}` |
| `directa` / `inversa` | `v = escala · v'` y `v' = v / escala`, ya con los valores resueltos |
| `grupos` | `{id, definicion, dimension, adimensional, contieneEscalasLibres, usos: [terminoId], interno, inversoDe}`. `interno` = coeficiente dentro de una función o una suma interna (por ejemplo `K/c_ref`) |
| `objetivos` | `{id, terminoId, estado: "satisfecho"|"dependiente"|"incompatible"|"pendiente"|"conservado", codigo?, motivo, responsables?, relacion?, valorObjetivo?, coeficienteFinal?, comprobado?}` |
| `rangoObjetivos` | Rango exacto del sistema de objetivos aplicado |
| `restricciones` | `{id, tipo: "positivo"|"no_nulo"|"signo"|"igualdad", expresion, motivo, signo?, valor?}` |
| `pasos` | `{ambito, regla, antes, despues, supuestos}` con `antes`/`despues` = `{izquierda, derecha}`. Reglas: `sustitucion_de_variables`, `regla_de_la_cadena`, `linealidad_y_agrupacion`, `division_por_factor_global`, `sustitucion_de_escalas_dadas`, `sustitucion_de_escalas_determinadas` |
| `equivalencia` | `{estado: "demostrada"|"no_demostrada", alcance, restricciones: [id], comprobaciones: [{ambito, tipo: "sustitucion_inversa"|"dominio"|"dimensiones"|"objetivo", estado}]}` |
| `terminos` | Catálogo de términos del original (igual que en `analizar`) |

Un objetivo `incompatible` por sobredeterminación trae `responsables` (todas las elecciones que intervienen) y `relacion: {izquierda, derecha}`: la relación entre datos que haría falta (por ejemplo `D/(k x_ref²) = 1` cuando L se fijó antes). Los objetivos incompatibles o pendientes **no se aplican**, y la formulación publicada sigue certificada.

`presentacion: "factorizada"` agrupa los términos con el mismo coeficiente no numérico. `"desarrollada"` no los agrupa. Es la misma transformación.

### Certificado

`demostrada` significa que, al aplicar la sustitución inversa a **lo publicado** y multiplicar por el factor global, la forma canónica cartesiana coincide con la del original. Esto vale para cada ecuación, condición y dominio. Además, las dimensiones de cada igualdad publicada concuerdan y cada objetivo aplicado vale exactamente lo pedido. La forma canónica solo usa identidades válidas bajo las restricciones publicadas (texto en `equivalencia.alcance`):

- las derivadas se desarrollan con las reglas del producto, de la potencia y de la cadena (exp, log, sin, cos, potencias);
- las derivadas de funciones declaradas, abs, min y max quedan sin desarrollar;
- se usa `log(exp y) = y`, y `exp(log y) = y` solo con `y > 0` según los signos y dominios declarados;
- no se usan otras identidades de exp/log/trig ni el intercambio de derivadas mixtas.

Para decidir si la diferencia es nula, se multiplica por las sumas que aparecen como denominador (no nulas, porque el original divide por ellas) y se desarrolla. Si algo no coincide, el estado es `no_demostrada`. No se muestrean números. Hay una prueba que confirma que el certificado detecta un término perdido.

## 6. Exploración y grupos Π

`operacion: "explorar"` devuelve:

- `evaluaciones: [{propuestaId, estado: "evaluada"|"duplicada"|"no_soportado", formulacionId, objetivos, resumen}]`;
- `formulaciones: [<cuerpo de transformar> + {id: "F<n>", propuestas: [ids]}]`. Una formulación es duplicada de otra si tiene las mismas igualdades, condiciones y dominios en forma canónica, sin importar el orden de los términos;
- `cobertura: {propuestasRecibidas, propuestasEvaluadas, formulacionesDistintas, duplicadas, noSoportadas, agotadoTiempo, siguientePropuesta, …}`. Hay un límite de 60 s; si se agota, `siguientePropuesta` indica dónde continuar y la continuación es reproducible reenviando `propuestas.slice(siguientePropuesta)`;
- `gruposPi` (si `config.incluirGruposPi`): `{cantidades, excluidas: [{id, motivo}], matriz, rango, numeroGrupos, bases: [{id: "B<n>", repetidas, grupos: [{id, exponentes, definicion}], enReferencia}], cobertura: {eleccionesDeRepetidas, revisadas, basesDistintas, omitidasPorCotas, duplicadas, limitadoPorPresupuesto, cotas, nota}}`.

`enReferencia` da las coordenadas racionales de cada grupo en la base `B1`; el núcleo comprueba la reconstrucción antes de publicarla. Un grupo y su inverso cuentan como la misma base. Los grupos de una formulación que no contienen escalas libres llevan `enBasePi`. El inventario Π está separado de los coeficientes efectivos y **no es exhaustivo**: cualquier producto de potencias racionales de una base es otro grupo válido.

## 7. API implementada

- `GET /api/adimensionalizacion/capacidades` → `capacidades()`.
- `POST /api/adimensionalizacion` con el cuerpo `SolicitudNucleo` (cualquiera de sus tres operaciones) o `solicitud_exploracion_adimensional` → `procesar(cuerpo)`. Siempre HTTP 200 con `estado`; HTTP 4xx solo si el cuerpo no es JSON o supera 1 MB.
- `POST /api/adimensionalizacion/dimensiones` recibe una solicitud `analizar` y devuelve el análisis y la auditoría por término de §12. Una operación distinta recibe HTTP 400.

`backend/api_adimensionalizacion.py`, registrado en `backend/main.py`, delega en `procesar` y `capacidades`, con la normalización y política de unidades de §12. El POST limita el cuerpo durante la lectura a 1 000 000 bytes, rechaza JSON inválido o números no JSON con 400 y usa 413 para exceso de tamaño. El cálculo se ejecuta en el pool de trabajo del servidor; las decisiones matemáticas siguen exclusivamente en `core/adimensionalizacion/`.

El cliente consulta capacidades, envía la solicitud y valida la respuesta completa en `app/adimensionalizacion/lecturaNucleo.ts`: versión, estado, vínculo, elecciones, mapas, opciones, referencias de símbolos y coordenadas, árboles, pasos, restricciones, condiciones, dominios y cobertura. No reproduce álgebra ni intenta recalcular la firma de Python. Una respuesta obsoleta no se presenta; editar el documento o el texto invalida la vista calculada. Se admite `requiere_datos` sin formulaciones, mostrando únicamente las unidades indispensables. La continuación reenvía `opciones.desde = cobertura.siguiente` y conserva las páginas recibidas.

La base URL se configura con `NEXT_PUBLIC_ADIMENSIONALIZACION_API_URL`; si no existe, usa `NEXT_PUBLIC_API_URL` y finalmente `http://localhost:8000`. Esto permite levantar el servicio integrado sin reiniciar un backend anterior que todavía no tenga la ruta.

## 8. Documento local v2 y ampliaciones pendientes

**Implementado:** `Documento.version = 2` admite `Forma.transformaciones?: Transformacion[]` con el contrato de §10.2. El lector valida estructura y referencias, admite documentos v1 y la migración explícita conserva identidad, modelo y formas. Persistencia, ramas, importación, JSON y LaTeX conservan los mapas. La interfaz permite declararlos en el JSON avanzado; la prueba de invertibilidad corresponde al núcleo.

El adaptador `prepararSolicitud` produce una copia de intercambio v1 sin `Forma.transformaciones`, y envía los mapas de la forma activa en `SolicitudNucleo.transformaciones`. La vista principal usa la búsqueda automática sin `formaId`, de modo que el núcleo propone escalas libres y respeta los mapas declarados. Las elecciones manuales de escalas y objetivos solo se respetan al enviar explícitamente `formaId`, como permite el protocolo. Los resultados no se almacenan como una caché vigente al recargar; se recalculan. El desarrollo calculado se exporta aparte como solicitud/respuesta JSON y documento LaTeX completo.

**Implementado en el núcleo (17 de octubre de 2026), pendiente en el cliente:** las cinco ampliaciones de modelo que esta sección dejaba pendientes. El núcleo acepta ahora `documento.version: 2` directamente; la especificación está en §13. Para usarlas, el cliente tiene que actualizar a la vez tipos, lector, entradas, exportación y pruebas. Hasta entonces, el adaptador v1 actual sigue siendo válido y su salida no cambia.

1. `Forma.objetivos[].terminoId`, junto a `termino` o en su lugar.
2. `condiciones[].ubicacion: { variableId; extremo: "desde" | "hasta" }`.
3. `funciones[].escala: { simboloId; funcionAdimensional }`, para declarar `D(c) = D* D̂(u)`.
4. `Forma.referencias: [{ ecuacionId; terminoId }]`, para dividir por un término distinto del izquierdo.
5. `Forma.prioridadEscalas: string[]`, para elegir qué escala se despeja.

Con el documento v2, el núcleo también lee `Forma.transformaciones` tal como lo guarda el cliente, sin pasar por el adaptador.

## 9. Ejemplos canónicos

`docs/ejemplos/adimensionalizacion-<nombre>-{solicitud,resultado}.json`: `automatico`, `requiere-datos`, `mapa-logaritmico`, `mapa-afin-temperatura`, `analizar`, `general`, `tiempo-difusivo`, `tiempo-reactivo`, `campo-cinetico`, `longitud-parametrica`, `condiciones`, `parcial`, `signo-negativo`, `rechazo-suma-incompatible`, `rechazo-forma-desactualizada`, `explorar`, los del documento v2 (§13), `v2-funcion-escalada` y `v2-referencias-ubicacion`, y los de `estudiar` (§14): `estudio-calor`, `estudio-brusselator` y `estudio-pliegues`. Los genera `tests/generar_ejemplos_adimensionalizacion.py`. `tests/validar_adimensionalizacion.py` comprueba que coinciden con el núcleo actual, de modo que un lector del cliente puede probarse contra ellos.

## 10. Entrada simple y familias generales (ampliación del 16 de octubre)

Responde a la «Última corrección del usuario» de la entrega.

### 10.1 `adimensionalizar`: búsqueda automática

Pensada para el botón «Adimensionalizar» de la vista mínima. El cliente envía solo el documento con la ecuación y el núcleo hace el resto:

1. **Analiza** las dimensiones. Si quedan indeterminadas, responde `requiere_datos` con `dimensional.faltantes`, el conjunto mínimo que hay que preguntar (por ejemplo `["c", "t", "x"]`), y no publica formulaciones. Si son incompatibles, responde `rechazado` con la ruta.
2. **Elige los mapas.** Sin `formaId`, transforma todas las variables presentes con escalas libres. Excepciones: las que tienen un mapa declarado en `transformaciones`, y las de unidad con desplazamiento, para las que publica el aviso `requiere_referencia` (no inventa una referencia). Con `formaId`, respeta las escalas y los objetivos de esa forma.
3. **Recorre** todos los subconjuntos **independientes** de coeficientes efectivos normalizables, en orden de tamaño y luego de modelo. Un subconjunto dependiente o incompatible da la misma formulación que uno independiente que también se recorre, así que el recorrido es completo para esta familia. Se excluyen, con motivo, los términos que no dependen de escalas libres (el temporal lo fija el factor global), los de signo desconocido, los nulos y los no monomiales.
4. **Elimina duplicados** demostrables y certifica cada formulación como en `transformar`.

```ts
type OpcionesBusqueda = {             // todas opcionales
  presupuesto?: number;     // 1–2000 formulaciones evaluadas (200)
  maxObjetivos?: number;    // 0–12; por defecto, el número de escalas libres
  desde?: number;           // índice de continuación (0)
  gruposPi?: boolean;       // true
  maxExponentePi?: number; maxDenominadorPi?: number;   // 1–12 (4)
  presentacion?: "factorizada" | "desarrollada";
};
```

El resultado `correcto` contiene:

- `formaBase`;
- `formulaciones`: el cuerpo de `transformar` más `{id, objetivosAplicados, subconjuntos}`;
- `evaluaciones`;
- `gruposPi`;
- `cobertura: {familia, candidatos, excluidos, constantesLibres, maxObjetivos, desde, evaluados, formulacionesDistintas, duplicadas, completa, agotado: null | "presupuesto" | "tiempo" | "enumeracion", siguiente}`.

Para continuar se reenvía con `opciones.desde = cobertura.siguiente`. Ejemplo probado: con `∂c/∂t = D∇²c + kc − ac²` y sin configurar nada salen **8 formulaciones**, recorrido `completa`, que incluyen las cinco del §3 del plan. Cada formulación con escalas libres es una familia infinita parametrizada por ellas (`libres`).

### 10.2 `Transformacion`: mapa general directa/inversa

`Forma.escalas` sigue siendo el caso multiplicativo. Los demás mapas se envían en `transformaciones`. Propuesta para guardarlos en un documento v2: `Forma.transformaciones`, con el mismo tipo.

```ts
type Transformacion = {
  variableId: string;          // campo, tiempo o coordenada del modelo
  nuevoId: string;             // nueva variable (adimensional)
  directa: Expresion;          // v = g(nuevo, constantes, parámetros)
  inversa: Expresion;          // nuevo = h(v, constantes, parámetros)
  constantes: { id: string; nombre: string; papel: "escala" | "referencia";
                dimension: Dimension;   // null = la infiere el núcleo desde g y h
                valor: { tipo: "libre" } | { tipo: "cantidad"; valor: number; unidad: string } | { tipo: "expresion"; expresion: Expresion } }[];
  dominio: { original: "positivo" | "negativo" | null; nuevo: "positivo" | "negativo" | null };
};
```

Reglas:

- **Expresiones de g y h.** Son algebraicas: sin derivadas, operadores ni funciones declaradas.
- **Constantes.** Las escalas son positivas y las referencias pueden tener cualquier signo. Una referencia puede llevar una unidad con desplazamiento (`25 degC` → `298.15 K`); una escala no.
- **Invertibilidad.** No se supone: el núcleo **demuestra** `h(g(w)) = w` y `g(h(v)) = v` en forma canónica con los dominios declarados. Si no puede, responde `rechazado` con `inversa_no_demostrada`. Ejemplos: `c = C u²` sin `nuevo: "positivo"` se rechaza, porque `(u²)^½ = |u|`; con `c, u > 0` se acepta.
- **Familia** (publicada en `transformaciones[].familia`): `multiplicativa` si g′ es constante y g(0) = 0; `afin` si g′ es constante; `no_lineal` en otro caso.
- **Campos no lineales.** Las derivadas se desarrollan con la regla de la cadena, incluidos los términos adicionales. Por ejemplo, con `c = C e^u`, `∂²c/∂x²` da `C e^u ((∂u/∂x)² + ∂²u/∂x²)`.
- **Coordenadas y tiempo no lineales.** Son por coordenada (cartesiana separable): `d/dv = (1/g′) d/dv′`, anidado para órdenes superiores, con la restricción `no_nulo` del jacobiano. Los dominios se transforman con `h`; por ejemplo, `x = L(e^ξ − 1)` lleva `[0, ell]` a `[0, log(1 + ell/L)]`.
- **Dominio declarado.** Se publica como restricción `positivo`/`negativo` y es condición del certificado.
- **Temperaturas con desplazamiento.** Una temperatura en `degC` ya no queda bloqueada: se transforma con un mapa afín `T = T_ref + ΔT θ`.

Las capacidades por familia están en `capacidades().familias`:

- soportadas: multiplicativa, afín, cociente de referencia, no lineal de campo, no lineal de coordenada y grupos Π;
- no soportadas: cambios de coordenadas acoplados o curvilíneos, escalas dependientes de t o x, y selección automática de mapas no lineales (la búsqueda automática usa los mapas multiplicativos o los declarados).

### 10.3 `desarrollo`: traza matemática completa

Cada formulación (de `transformar` y de `adimensionalizar`) incluye `desarrollo: PasoDesarrollo[]`. Usa **exactamente** el tipo propuesto en `contrato.ts`: `{id, operacion, regla, justificacion, antes, despues, supuestos, objetosAfectados}`, con `antes`/`despues` de forma `{tipo: "expresion"}` o `{tipo: "igualdad", igualdad: {id, izquierda, derecha}}`.

Los pasos salen en el orden en que se calculan; no son una explicación reconstruida a partir del resultado final:

1. `analisis_dimensional`: homogeneidad de cada ecuación y dimensiones inferidas (en `justificacion` y `objetosAfectados`).
2. `cambio_variables`: cada mapa y su inversa demostrada, más `regla_cadena` con `∂v/∂v′ = g′` para tiempo y coordenadas.
3. Por cada término: `sustitucion` y `regla_cadena`, y además `factorizacion` (linealidad) o, con mapas no lineales, `regla_cadena` «desarrollo de derivadas» con los términos adicionales.
4. Por igualdad completa:
   - `sustitucion`: la igualdad **antes de cancelar factores**;
   - `regla_cadena`;
   - `agrupacion` por núcleo;
   - `normalizacion`: división por el factor global, con su condición de no nulidad en `supuestos`;
   - `sustitucion` de las escalas dadas.
5. `normalizacion` por objetivo (coeficiente = ±1 antes y con las escalas resueltas sustituidas, estado y responsables). Después, un paso «resolución exacta por rango» por escala despejada y un paso «familia libre» por escala libre.
6. `sustitucion` de las escalas determinadas, `simplificacion` (factorización de presentación) y `agrupacion` con la definición de cada grupo.
7. `geometria_condiciones`: los extremos de cada dominio y los pasos completos de cada condición.
8. `verificacion_inversa`: la publicada frente a `F·h(publicada)` desarrollada, que recupera la original, con el estado de la comparación.

Otras reglas:

- El núcleo no hace hipótesis físicas (nunca desprecia términos), así que no emite `hipotesis_fisica`.
- `desarrolloEstado: {estado: "completo", nota}` declara que la traza recoge todas las operaciones realizadas.
- Todo símbolo de la traza existe en el modelo o en `simbolos` del resultado, y toda variable de derivación es una variable independiente de alguno de los dos. La suite comprueba exactamente eso, como deberá hacerlo el lector del cliente, sobre todos los ejemplos y formulaciones.

### 10.4 Cambios de formato respecto de la versión anterior de este contrato

- Hay un nuevo estado, `requiere_datos`. La operación `transformar` también lo usa en lugar de `rechazado` cuando hay dimensiones indeterminadas.
- El resultado añade `transformaciones` (familia, directa, inversa y dominio por variable).
- `escalas[]` y `simbolos[]` de las escalas añaden `papel: "escala" | "referencia"`.
- Las variables nuevas añaden `signo`.
- `vinculo.eleccion.transformaciones` aparece cuando se envían mapas. En `adimensionalizar`, `vinculo.opciones` acompaña a la firma.

## 11. Reglas de integración de los botones

1. Lector de `adimensionalizacion.resultado` v1: rechazar versiones o formatos desconocidos, verificar que toda referencia de símbolo exista en el modelo o en `simbolos` del resultado, y aplicar la regla de vigencia de §3.
2. Mostrar `estado`, `normalizacion.estado`, `equivalencia.estado` y los estados de los objetivos tal como llegan. La etiqueta «adimensional» se pone solo cuando `normalizacion.estado === "completa"`.
3. Mostrar `rol: "escala"` con subíndice (`t_ref`, `c_ref`). Los ids `<v>_ref` y `nuevoNombre` se reservan: si ya existen en el modelo, el núcleo rechaza con `identidad_ocupada`.
4. No reconstruir coeficientes en el cliente: usar `ecuaciones[].terminos[].coeficiente` y `grupos`.
5. «Adimensionalizar» de la vista mínima: enviar `operacion: "adimensionalizar"` sin escalas. Si llega `requiere_datos`, preguntar solo por `dimensional.faltantes` y reenviar. Si llega `correcto`, mostrar las `formulaciones` con sus `libres` y la `cobertura`; si `cobertura.siguiente` no es nulo, ofrecer «más» con `opciones.desde`.
6. Los mapas afines y no lineales van en `transformaciones` (§10.2). Para guardarlos en el documento hace falta la v2 (`Forma.transformaciones`).

## 12. Capa dimensional de la interfaz y hojas

La envoltura `backend/dimensiones_adimensionalizacion.py` utiliza `procesar`, `analizar_modelo` y `Analizador` del núcleo existente. No añade un transformador ni reglas dimensionales en JavaScript. Cada sumando debe tener dimensiones compatibles con su igualdad; distintas ecuaciones de un sistema pueden tener dimensiones distintas. Los símbolos comunes se resuelven conjuntamente.

`POST /api/adimensionalizacion/dimensiones` devuelve:

```ts
{
  formato: "adimensionalizacion.dimensiones", version: 1,
  analisis: RespuestaNucleo, // analizar: incluye vínculo, diagnósticos y dimensional
  ecuaciones: [{id, dimension, terminos: [{ruta, lado, expresion, dimension,
    estado: "compatible" | "incompatible" | "pendiente" | "cero", operadores}]}],
  cantidades: [{id, unidadIntroducida, unidadNormalizada, magnitudes: string[]}],
  catalogo: [{id, nombre, unidad}]
}
```

El lector del cliente valida el vínculo y coteja rutas, orden y árboles con los términos de la solicitud. Los estados por término no los calcula el navegador. Las magnitudes se identifican por las dimensiones inferidas, y son candidatas: una dimensión no distingue por sí sola presión de densidad de energía, por ejemplo. El catálogo ofrece declaraciones de unidades comunes; la interpretación real de unidades compuestas usa pint, no una lista cerrada del frontend.

Se normalizan aliases de entrada explícitos, como `Kg` → `kg`, `litros` → `L`, `segundos` → `s`, y notación `m³` → `m^3`. `L` en una unidad significa litro; en una dimensión es la base de longitud. Un identificador `L` en la ecuación sigue siendo un símbolo del usuario. Ninguna unidad o dimensión física se deduce del nombre de un símbolo. Si pint no reconoce una unidad, o esta no es comparable con las bases declaradas, la envoltura publica un rechazo y elimina formulaciones/certificados, aunque el núcleo pudiera inferir dimensiones por otras restricciones. La comprobación acredita homogeneidad dimensional, no demuestra que una ley física sea correcta ni que sus datos numéricos satisfagan la igualdad.

La consulta dinámica espera 450 ms después de una edición y cancela las solicitudes anteriores. La vista presenta rol matemático, unidad introducida, dimensión declarada/inferida, magnitudes compatibles, operadores y compatibilidad por término. Los operadores determinan roles sintácticos; un símbolo aislado a la izquierda de una igualdad algebraica se propone como variable dependiente. La función matemática puede cambiarse explícitamente; la lectura estricta mantiene las restricciones de derivadas y coordenadas.

**Hojas.** `rage.adimensionalizacion.hojas.v1` almacena un cuaderno independiente con hasta 50 hojas. Cada hoja contiene `Documento` v2, borrador de texto (también incompleto), fecha e indicador de archivo. Se admite crear, nombrar, duplicar con identidad independiente, archivar/restaurar e importar/exportar el cuaderno. El documento de la clave anterior se migra a la primera hoja sin borrarlo. No se reutilizan las claves ni las hojas del motor Rage. Los resultados se recalculan, conservando la regla de vigencia existente.

**Resultado.** Tras calcular se abre una vista dedicada dentro de la hoja, con las ecuaciones finales, grupos calculados, escalas libres y condiciones de equivalencia. Se selecciona inicialmente una alternativa con menos escalas libres, y se mantienen todas las alternativas. «Resultado final», «Desarrollo completo» y «Comparar alternativas» separan las lecturas sin reducir la traza. Las relaciones entre ecuaciones vienen de los grupos y las bases Π del núcleo: el cliente no añade razones como D1/D2 por su cuenta.

**Verificación.** `tests/validar_capa_dimensional.py` comprueba unidades equivalentes, aliases, términos con varias variables, funciones/operadores, inferencia, incompatibilidades, bloqueo de unidades inventadas, ecuaciones con dimensiones distintas y un sistema de dos campos con 12 formulaciones certificadas y razón entre difusividades. `frontend/verificar_capa_dimensional.mjs` valida los datos reales, rechazos del lector, LaTeX, migración de hojas, borradores, duplicación independiente, archivo y el caso algebraico. Se conservan las suites anteriores del contrato y del núcleo.

## 13. Documento v2 en el núcleo (17 de octubre de 2026)

El núcleo lee `documento.version ∈ {1, 2}`. Un v2 es un v1 más los campos opcionales de abajo. Un documento v1 que traiga alguno de ellos se rechaza con un error de contrato, y un v2 que no use ninguno da exactamente el mismo resultado que el v1 equivalente; la suite lo comprueba con las cinco formas del §3. El formato del resultado sigue siendo `adimensionalizacion.resultado` v1: los campos de salida nuevos solo aparecen cuando se usa el campo v2 correspondiente. `capacidades()` publica `contratoDocumento: 2`, `versionesDocumento: [1, 2]` y la lista `documentoV2`.

```ts
type ObjetivoV2 = { id; ecuacionId; valor: 1 | -1; accion; terminoId?: string; termino?: Expresion };   // al menos uno de los dos
type FuncionV2 = Funcion & { escala?: { simboloId: string; funcionAdimensional: string } };
type CondicionV2 = Condicion & { ubicacion?: { variableId: string; extremo: "desde" | "hasta" } };
type FormaV2 = Forma & {
  objetivos: ObjetivoV2[];
  transformaciones?: Transformacion[];                 // §10.2
  referencias?: { ecuacionId: string; terminoId: string }[];
  prioridadEscalas?: string[];
};
```

### 13.1 `objetivos[].terminoId`

El objetivo se identifica con el id del catálogo de `analizar` (`<ecuacionId>:<ruta>[#k]`, §3), sin emparejar estructuras. El lector exige que el id empiece por `<ecuacionId>:`. Que el término exista lo decide el núcleo:

- Si no existe, el objetivo queda `pendiente` con código `termino_no_encontrado`. Cuando el sumando se divide en partes, el motivo nombra los `#k`.
- Si llegan `terminoId` y `termino` y designan términos distintos, el objetivo queda `pendiente` con `termino_contradictorio` y no se aplica.

En ambos casos la formulación sigue certificada.

### 13.2 `condiciones[].ubicacion`

`variableId` tiene que ser la variable del dominio `dominioId`. Una condición `inicial` se ubica en el tiempo; `dirichlet`, `flujo` y `mixta`, en una coordenada. La condición transformada añade:

```ts
lugar: { variableId /* nueva */, variableOriginal, extremo, valor: Expresion /* extremo transformado */, original: Expresion }
```

`ubicacion` deja de ser el texto genérico y pasa a ser, por ejemplo, `"x_ad = ell/(D^0.5*t_ref^0.5) (extremo 'hasta' del dominio intervalo-x)"`. `lugar.valor` es el mismo árbol que el extremo publicado en `dominios`, que ya certifica la comprobación `dominio`. La traza añade un paso `geometria_condiciones` «ubicacion de la condicion» por cada condición ubicada.

### 13.3 `funciones[].escala`: `D(c) = D* D̂(u)`

`simboloId` es un parámetro constante del modelo (no nulo) y `funcionAdimensional` es una identidad nueva, que no puede coincidir con símbolos, funciones ni ids que genere el núcleo. La dimensión se infiere: `[D*] = [salida de D]`, y una contradicción da `dimension_incompatible`.

Al transformar, cada llamada `D(z)`, con sus argumentos ya transformados, se reescribe como `D* D̂(w)`, donde `z = s w`:

- `s` es el producto de las escalas de los mapas que aparecen en el argumento y `w` lo que queda, que debe ser adimensional;
- si el argumento no es un único monomio o `w` conserva dimensión, no se extrae nada (`s = 1`).

**Definición publicada:** `D̂(w) = D(s w) / D*`. Es una definición, no una hipótesis física, y el certificado la invierte antes de la sustitución inversa. Cada entrada de `D` debe recibir la misma `s` en todas sus llamadas; si no, `D̂` no estaría bien definida y el núcleo responde `rechazado` con `escala_funcion_inconsistente`. Si el signo de `D*` es desconocido, se publica la restricción `no_nulo`. `D*` queda en el coeficiente, así que los objetivos A3 lo usan. Por ejemplo, `t_ref = x_ref²/D*`, y la normalización puede ser `completa`.

La formulación añade:

```ts
funcionesAdimensionales: [{ id /* D̂ */, nombre, funcionId /* D */, escalaId /* D* */, entradas: Dimension[], salida: {},
                            dependeDe, argumentos: [{ escala: Expresion /* s, con las escalas resueltas */, extraida: boolean }],
                            definicion: "Dh(w1) = Dc(c_ref w1) / Dstar" }]
```

**Para el lector:** las llamadas a `D̂` que aparecen en ecuaciones y traza se resuelven contra `funcionesAdimensionales`, que dan su aridad, y no contra `modelo.funciones`. La traza añade «escala declarada de funcion» por término y «igualdad completa con la escala declarada de las funciones» por igualdad. `pasos` añade la regla `escala_declarada_de_funciones`.

### 13.4 `Forma.referencias`

Cada igualdad, sea ecuación o condición (`ecuacionId` puede ser el id de una condición), se divide por la magnitud del coeficiente transformado de `terminoId` en lugar del izquierdo. Las reglas:

- Como máximo una referencia por igualdad. Un id que sea a la vez ecuación y condición se rechaza por ambiguo.
- El término tiene que existir (`referencia_no_encontrada`) y su coeficiente debe ser un único monomio (`referencia_no_monomial`).
- Si contiene un parámetro nulo, se responde `referencia_nula`. Una referencia pedida no se relaja en silencio: todos estos casos son `rechazado`.
- Un objetivo sobre el término de referencia sale `dependiente`, igual que el temporal en v1. La búsqueda automática lo excluye de los candidatos.

### 13.5 `Forma.prioridadEscalas`

Ids de variables transformadas (se toman sus escalas) o de constantes de mapas. Se despejan primero, en ese orden; las no listadas siguen el orden de v1 (tiempo, campos, coordenadas). Un id desconocido da `prioridad_desconocida` y un duplicado es un error de contrato. Ejemplo probado: con el objetivo de difusión, sin prioridad sale `t_ref = x_ref²/D` con `x_ref` libre; con `["x"]` sale `x_ref = (D t_ref)^½` con `t_ref` libre.

### 13.6 Elección, vínculo y búsqueda automática

- `vinculo.eleccion` añade `referencias` y `prioridadEscalas` cuando la forma los trae; la regla de vigencia del §3 los incluye, y la firma cambia con ellos.
- `Forma.transformaciones` se usa con `formaId`. Si la forma ya los declara y la solicitud también envía `transformaciones`, es un error de contrato: no hay dos fuentes de mapas.
- Sin `formaId`, `opciones.referencias` y `opciones.prioridadEscalas` (mismo tipo) configuran la forma automática y aparecen en `formaBase`. Con `formaId` son un error de contrato, porque mandan los de la forma.

**Verificación:** 249 comprobaciones en `tests/validar_adimensionalizacion.py`, 48 de ellas nuevas para v2, más los dos ejemplos canónicos nuevos.

## 14. Operación `estudiar` (18 de octubre de 2026)

Analiza **una** formulación con los valores físicos que dé el usuario. Sustituye a los análisis que el navegador fabricaba (auditoría del 18 de octubre). El cliente solo presenta.

```ts
type SolicitudEstudio = SolicitudNucleo & { operacion: "estudiar"; estudio: {
  objetivos?: string[];            // terminoIds de la formulación (sus objetivosAplicados): la reproduce exactamente
  valores?: { simboloId: string; valor: number; unidad?: string | null }[];  // parámetros, constantes y escalas libres
  analisis?: ("estructura" | "sensibilidad" | "valores" | "asintotica" | "escalas" | "simetrias" | "estabilidad" | "continuacion" | "simulacion")[];
  umbralAsintotico?: number;       // (0, 0.5]; por defecto 0.01
  cajaEstados?: number;            // búsqueda de estados homogéneos en [-B, B] o [0, B] según el signo; 10
  estabilidad?: { kMax?: number };
  continuacion?: { parametroId: string; desde: number; hasta: number; unidad?: string; pasosMax?: number };
  simulacion?: { tFinal?: number; muestras?: number; nodos?: number; rtol?: number; atol?: number; verificarMalla?: boolean;
                 fronteras?: { condicionId: string; extremo: "desde" | "hasta" }[];
                 tFinalSI?: number;        // segundos; excluye tFinal. τ final = inversa publicada del mapa del tiempo
                 periodica?: boolean };    // frontera periódica en la coordenada activa; sin condiciones de extremo
} };
```

**Formulación.**

- Sin `formaId`, se usa la forma automática con los objetivos `estudio.objetivos`.
- Con `formaId`, los objetivos de la forma (prefijo `base:`) más los de `estudio.objetivos`.
- Para objetivos y presentación iguales, el resultado es idéntico al de `adimensionalizar`; la suite lo comprueba con las 8 formulaciones del §3.

**Valores.**

- Se convierten a SI con pint y se comprueba que su dimensión sea la del símbolo (`dimension_incompatible`).
- Un valor sin unidad usa la unidad declarada del símbolo.
- Un signo contradictorio con el declarado es `signo_contradictorio`, y un valor para una variable es `valor_no_admitido`. Los dos son rechazos.
- Las escalas determinadas se evalúan con sus expresiones; lo que falte se lista en `faltan`, nombrando los parámetros que hay detrás.

**Respuesta.**

```ts
{ formato: "adimensionalizacion.resultado", version: 1, operacion: "estudiar", estado, nucleo, diagnosticos,
  vinculo: { documentoId, modeloId, modeloRevision, formaId, eleccion, estudio /* eco exacto */, firma },
  dimensional, terminos, formaBase, formulacion /* cuerpo de transformar */, estudio: { [análisis]: { estado, motivo, … } } }
```

Cada análisis publica `estado ∈ {calculado, requiere_datos, no_aplicable, no_soportado, no_convergente}` y `motivo`, que describe el método usado:

| Análisis | Método y salida |
|---|---|
| `estructura` | Clasificación de cada término por sus operadores en la forma canónica cartesiana: acumulación, difusión, convección, reacción (`lineal`), fuente; en condiciones, flujo, valor o dato. Cada grupo se lee como el cociente de su término entre el de referencia (factor global) y, como `equivalentes`, entre los demás términos de coeficiente ±1. `nombreClasico` solo aparece si el par de tipos lo determina (Fourier, Péclet, Damköhler I/II, Biot…). `normalizados` lista los términos fijados por los objetivos. |
| `sensibilidad` | Exponente racional de cada símbolo en cada grupo monomial: d ln G / d ln p. Separa las escalas libres. |
| `valores` | Escalas, grupos y coeficientes en SI; `dispersionLog10` por ecuación. |
| `asintotica` | Envolvente de Kruskal de \|coef\| δ^(−orden), en espacio y en tiempo. Da los términos dominantes y los despreciables (umbral relativo), la ecuación `reducida`, la perturbación singular (`condicionesPerdidas`, `espesor`, balance interior) y la `ubicacion` de la capa (solo si el balance interior es lineal con coeficientes constantes). También la capa inicial. |
| `escalas` | Linealización exacta (paso complejo) en un estado de referencia: el homogéneo estable, si existe. Publica difusividad y velocidad efectivas, tiempos, longitudes internas, nodos (Péclet de celda ≤ 2 y 10 nodos por longitud interna), paso explícito máximo por mecanismo y cociente de rigidez del operador semidiscreto. |
| `simetrias` | Dilataciones (espacio nulo racional de los pesos de cada monomial), traslaciones y reducciones: semejanza η = ξ τ^(−q), u = τ^p F(η) y onda viajera z = ξ − c τ. La EDO se publica solo si todos los monomios quedan con la misma potencia de τ; si no, `no_demostrada`. |
| `estabilidad` | Estados homogéneos por búsqueda finita en la caja (publicada). Para cada uno: jacobiano, autovalores y, por coordenada, σ(k) = autovalores de J + Σ (ik)ⁿ Cₙ, con clase `estable` / `turing` / `onda` / `inestable_homogenea` / `oscilatoria_homogenea`, k crítico, banda y modos de Neumann admisibles. Un continuo de equilibrios se declara (`continuo`, `notaContinuo`) y se analiza un representante. |
| `continuacion` | Longitud de arco de F(u; p) = 0 desde los estados en el valor dado. Pliegues refinados por Newton sobre F = 0, F_u v = 0; Hopf por cruce de un par complejo, con su frecuencia. Ramas con estabilidad por punto. |
| `simulacion` | Método de líneas en una coordenada (o EDO): diferencias centradas de segundo orden, condiciones ubicadas (v2 o `simulacion.fronteras`) resueltas en cada evaluación (Dirichlet fuera del estado; flujo y Robin con nodo fantasma) e integración BDF con dispersión del jacobiano. Publica `tiempos`, `xi` y `campos` (adimensionales); `fisico` (restitución SI con los mapas); `verificacionMalla` (diferencia con 2N − 1 nodos); y `codigoPython`, un script autónomo con la misma discretización. Con `periodica` usa N nodos en [a, b) (b se identifica con a), rechaza condiciones de extremo declaradas, verifica con 2N nodos y publica `metodo.frontera = "periodica"`. Con `tFinalSI` el tiempo final se da en segundos y el núcleo lo convierte con la inversa del mapa del tiempo (si el tiempo no se transforma, τ = t). Además publica `resultados`: la misma trayectoria en el formato común (`docs/FORMATO_RESULTADOS.md`), con la formulación adimensional y, si las escalas tienen valor, las variables originales en SI. |

**Límites declarados.**

- Las funciones declaradas sin definición no se evalúan numéricamente.
- Simulación en una coordenada, con derivadas de orden ≤ 2 y sin derivadas mixtas tiempo-espacio; la frontera periódica no está soportada.
- La dispersión se calcula para un dominio infinito, más los modos de Neumann del finito.
- La búsqueda de estados es finita.
- Nada de esto certifica la validez física del modelo.

**Funciones ampliadas.** tan, tanh, sinh, cosh, atan y erf se admiten en todo el núcleo:

- argumento adimensional;
- derivadas con regla de la cadena (erf queda sin desarrollar);
- evaluación numérica.

El texto de `equivalencia.alcance` se actualizó.

**Corrección del 18 de octubre.** Una suma interna ya adimensional (1 + K c) dejó de ceder escalas: c_ref (K u + 1/c_ref) dejaba un núcleo dimensional. Además, un objetivo sobre un coeficiente dimensional queda `pendiente` (`coeficiente_dimensional`). Antes, 38 formulaciones de tres ejemplos del catálogo salían «no demostradas»; ahora se demuestran todas.

**Verificación.**

- `tests/validar_estudio_adimensionalizacion.py`: 55 comprobaciones contra soluciones analíticas.
- Ejemplos canónicos `estudio-calor`, `estudio-brusselator` y `estudio-pliegues`, comprobados por la suite del núcleo.
- `frontend/verificar_estudio_adimensionalizacion.mjs`: 66 comprobaciones del lector y la presentación. Una prueba aleatoria de 2000 mutaciones sobre solicitudes v2 no produjo errores internos ni resultados fallidos con ecuaciones.
