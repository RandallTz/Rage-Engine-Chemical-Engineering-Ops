# Encargo para Claude: topología, fronteras pendientes y fuentes únicas

Fecha: 12 de octubre de 2026.

**Este es el documento de trabajo para Claude.** Ejecuta los hitos de este documento en orden. El documento `frontend/DECISION_COMPONENTES_PUERTOS_Y_FUENTES.md` aporta contexto; sus fases de UI, bombas y ampliaciones físicas no forman parte de este encargo.

## 1. Objetivo y situación actual

El usuario está construyendo modelos desde volúmenes y conexiones. Crear un volumen ya no crea automáticamente alimentación ni salida. Necesitamos que el backend distinga modelos incompletos, sistemas cerrados y topologías no soportadas, y que una edición conserve el significado de los datos.

Referencia vigente: `docs/ENTREGA_LABORATORIO_CODEX.md`, hasta §26, revisión 14. Ya existen recuento canónico, referencias de campos, ecuaciones parciales, análisis dimensional, bases másica/molar y comprobaciones del dominio. **No volver a implementar estas entregas.** Comprueba el estado real del repositorio antes de modificarlo; puede haber trabajo posterior.

El problema del editor es concreto:

```
Antes:   Alimentación → V1 → Salida
Después: Alimentación → V1 → Corriente compartida → V2 → Salida
```

Codex implementará la inserción y conservará los identificadores de alimentación, V1 y salida. El backend recibe el segundo montaje completo; no recibe instrucciones gráficas ni necesita un endpoint de inserción.

## 2. Responsabilidades y límites

Tu trabajo es backend, pruebas y documentación. Primero reproduce lo que ya funciona. Corrige defectos y añade únicamente el contrato mínimo necesario para distinguir intención de frontera. Si un caso cumple, añade la evidencia sin reescribir su implementación.

No tocar el frontend, sus pruebas JavaScript ni `thermodynamics/proveedor.py`: este último conserva un cambio ajeno. El nuevo apartado de entrega se escribe en `docs/ENTREGA_LABORATORIO_CODEX.md`; los ejemplos ejecutados, en `docs/ejemplos/`.

No hacer commit ni push. No borrar ni revertir cambios previos. Identifica los archivos propios al entregar.

Fuera de alcance:

- interfaz de insertar, arrastrar, agrupar, deshacer/rehacer o representar calor con un marcador;
- bombas, momento, hidráulica, nuevas curvas de equipos o expresiones arbitrarias;
- frontera exterior de temperatura con una ley nueva de transferencia;
- nuevos solvers o ampliación general de ODE/DAE;
- ampliar el número de volúmenes, bifurcaciones, ciclos o combinaciones físicas admitidas;
- hacer resoluble cualquier dibujo inventando cierres, iniciales o propiedades.

## 3. Hito A — validar la inserción sobre las combinaciones existentes

### A1. Una corriente compartida y datos con identidad estable

Prepara peticiones antes y después de la inserción del esquema de §1, con agua pura y `balance_general`, primero material. Usa identificadores estables para alimentación, V1 y salida; identifica V2 y la corriente nueva por separado.

En el montaje después de insertar:

- el catálogo identifica la corriente intermedia como un solo objeto físico;
- su caudal aparece como salida de V1 y entrada de V2, con signos opuestos;
- el caudal no cuenta dos veces como datos independientes;
- el término interior se cancela en el global, desde los términos del ensamblaje;
- los datos de alimentación, V1 y salida siguen ligados a sus identificadores;
- un dato de salida es un dato de la frontera final, no una nueva propiedad de V1;
- no se copian los datos ni las iniciales de V1 para completar V2;
- una referencia a un bloque retirado o desconocido se diagnostica, no se ignora.

El backend no migra por su cuenta una condición de una conexión antigua a otra distinta. Verifica solo la correspondencia de los datos explícitamente enviados. Documenta cuáles se declaran en la corriente, cuáles en el volumen y cuáles en la frontera.

### A2. Recuento y resolución después de editar

Usa esta referencia independiente para el montaje material de dos volúmenes:

```
F_entrada = 3 mol/s
F_intermedia = 2 mol/s
F_salida = 1 mol/s
n1(0) = 100 mol
n2(0) = 200 mol
t_final = 10 min

n1(t) = 100 + t
n2(t) = 200 + t          (t expresado en segundos)
n1(600) = 700 mol
n2(600) = 800 mol
```

Tras insertar V2, retira su inicial y el caudal de la corriente nueva. `/validar` debe bloquear la resolución y señalar los campos que faltan con referencias utilizables por el frontend. Si el ensamblaje no puede construirse, no inventar números exactos de recuento; conservar el criterio de null/motivo o cota declarada.

Completa ambos datos y comprueba `/resolver` contra la referencia anterior. Ejecuta después otra petición con un valor distinto para demostrar que el cálculo usa la petición nueva. No diseñar un historial en el servidor: la vigencia de las respuestas HTTP en el editor corresponde a Codex.

Verifica también el estacionario directo/inverso existente: especificar solo el caudal final de 36 kmol/h debe determinar los tres caudales en 10 mol/s, siempre que el resto de requisitos esté completo. Mantén los inventarios con datos explícitos donde corresponda; no deducirlos del caudal.

### A3. Conservar ramas y diagnosticar el alcance

Construye una petición donde V1 conserva su salida exterior y además se conecta a V2. Si esa bifurcación no está soportada, debe rechazarse con un diagnóstico de topología que cite las piezas y conexiones implicadas.

No eliminar una rama, no fabricar un reparto de caudal y no resolver una cadena distinta de la petición. No ampliar la bifurcación en esta entrega.

**Entrega A:** tabla de casos reproducidos, defectos corregidos y resultados. Puede ser una entrega de pruebas si el comportamiento ya cumple.

## 4. Hito B — distinguir intención de frontera y ausencia de datos

### B1. Decisión de contrato antes del código

Hoy el motor identifica volúmenes cerrados a partir de la ausencia de corrientes en determinadas combinaciones. Eso no basta para distinguir un volumen recién creado, todavía sin conectar, de un sistema cerrado elegido por el usuario.

Revisa si algún campo público existente permite declarar esta intención inequívocamente. Si no existe, implementa una declaración **opcional, versionada y por volumen** de intención material. Define y documenta su esquema exacto antes de programar; no uses un dato visual del nodo como supuesto físico.

La declaración debe poder expresar:

| Intención | Comportamiento necesario |
|---|---|
| Pendiente de definir | Borrador: no certificarlo como un sistema cerrado ni como listo |
| Cerrado al exterior | Ausencia deliberada de corrientes materiales exteriores; no implica adiabático |
| Abierto con fronteras pendientes | Una frontera prevista aún no conectada o no especificada sigue pendiente; no equivale a caudal cero |

La declaración debe identificar qué frontera está pendiente cuando esa información se conoce. No imponer que todo sistema abierto tenga siempre una entrada y una salida: llenar o vaciar un tanque puede requerir solo una de ellas. **Si ese régimen no está soportado hoy, diagnosticar la limitación; no extenderlo aquí.**

Las interfaces materiales interiores no convierten por sí mismas a un compartimento cerrado al exterior en un sistema abierto al entorno. Declara exactamente qué alcance usa la palabra «cerrado».

### B2. Compatibilidad

- Sin la nueva declaración, las peticiones históricas conservan su comportamiento, resultados y `modelo_id`.
- Si la declaración solo confirma una interpretación física existente, evita alterar la identidad por metadatos redundantes; documenta la regla de normalización.
- Si la intención está pendiente, conserva el borrador y devuelve diagnóstico; no presentarlo como modelo físico resuelto.
- Una declaración de cerrado junto a una alimentación o salida exterior real es una contradicción explícita; no borrar ninguna de las dos partes.
- Ausente, null y cero siguen siendo diferentes: cero declarado con unidad es un dato; null no especifica una frontera.
- Una referencia a un volumen inexistente o una declaración duplicada debe tener un diagnóstico definido, no quedar descartada por el parser.
- Mantén el contrato semántico de errores con códigos y referencias; no trasladar omisiones físicas habituales a un 422 genérico.

### B3. Respuesta y recuento

Expón la intención solicitada, la interpretación efectiva y sus pendientes o contradicciones. Reutiliza `balances`, `pendientes`, `contradicciones`, `catalogo_variables` y `recuento` donde su significado corresponda. Añade campos solo cuando el contrato actual no pueda representar la distinción.

Cada pendiente debe referenciar el volumen y la ruta exacta que falta. Si falta una conexión, no inventar un `conexion_id` que todavía no existe: utiliza el volumen y la referencia de frontera declarada. Tampoco fabricar una variable del catálogo si no se puede identificar todavía.

No asumir que declarar «cerrado» vuelve ejecutable cualquier combinación: aún deben cumplirse el cierre, las iniciales, el dominio y las capacidades publicadas. El estado de completitud debe reflejar esa diferencia.

**Entrega B:** esquema documentado, capacidades, compatibilidad y ejemplos que distingan pendiente/cerrado/abierto incompleto/contradictorio. Sigue la convención vigente de revisión del contrato para campos aditivos.

## 5. Hito C — fuente exterior única y conservación

### C1. La representación gráfica no crea otra fuente

La futura UI permitirá editar calor desde el tanque o seleccionar un marcador junto a él. Ambos accesos enviarán la misma pieza `calor`, la misma conexión y la misma especificación Q. El backend no puede averiguar desde cuál control gráfico se editó: **no crear un contrato de UI para ello**.

Demuestra que reenviar la misma petición da el mismo modelo y recuento. Una fuente añade una sola aportación exterior de energía. No sumar dos veces Q porque también se muestra junto al volumen.

Si una cantidad Q ya puede declararse mediante varias rutas públicas, enumera esas rutas y comprueba su exclusión, redundancia o conflicto según el contrato. Si no existe una ruta local Q en el volumen, dilo y no la inventes. El frontend reutilizará la ruta oficial de la fuente.

### C2. Omisiones y contradicciones

Comprueba con referencias exactas:

- fuente conectada con Q ausente o null: pendiente, nunca Q = 0;
- Q = 0 con unidad: dato explícito válido dentro de un montaje completo;
- fuente exterior junto a adiabático efectivo: contradicción conforme al contrato;
- fuente exterior en un volumen con energía desactivada: diagnóstico conforme a §21, sin ejecutar un término que se haya omitido;
- T impuesta al volumen y Q impuesto: exclusión existente respetada;
- dos fuentes en un volumen o una fuente compartida por varios volúmenes: mantener el alcance actual y diagnosticarlo sin sumar ni repartir en silencio.

No anunciar «varias fuentes independientes admitidas» si hoy se rechazan dos fuentes por volumen. Esta entrega verifica el comportamiento existente, no amplía esa capacidad.

### C3. Referencias físicas independientes

Selecciona un montaje de agua con energía que ya esté soportado. Cuando sea posible usar un dominio cerrado con capacidad constante C y Q impuesto, la referencia es:

```
T(t) = T0 + Q·t/C
```

Si la topología exige dos dominios, reutiliza una combinación cerrada admitida y desacóplalos con G = 0 declarado, o usa esta referencia de un tanque perfectamente mezclado a cantidad constante:

```
n = 1000 mol; cp = 75 J/(mol·K)
F_entrada = F_salida = 10 mol/s
T_entrada = T0 = 300 K; Q = 750 W
C = n·cp; tau = n/F = 100 s
T(t) = 301 - exp(-t/100) K
```

Completa presión, propiedades, cierres y dominio con datos explícitos de la combinación elegida. No omitir trabajo de frontera donde el modelo lo necesita. Si utilizas la segunda referencia, prueba también el estacionario T = 301 K sobre el mismo modelo.

Para el contacto interno, utiliza dos dominios cerrados con capacidades constantes y un Q12 = G(T1 - T2). Comprueba temperaturas contra la solución analítica o exponencial de matriz escrita fuera del motor, y la cancelación de Q12 en el global. Añade una fuente exterior a uno de los dominios y verifica que en el balance global permanece solo su aportación, además de las otras fronteras realmente presentes.

No utilizar conservación como única prueba de precisión. Comprueba por separado la trayectoria, los términos por volumen, las cancelaciones y el balance integrado. La fuente exterior y el contacto interno deben citar sus piezas y conexiones.

## 6. Casos mínimos de aceptación

| ID | Caso | Criterio |
|---|---|---|
| T1 | Cadena después de insertar, incompleta | No resoluble; pendientes de V2 y corriente identificados |
| T2 | Cadena completa 3/2/1 mol/s | 700/800 mol a 600 s; corriente compartida contada una vez |
| T3 | Estacionario hacia atrás | 36 kmol/h en salida determina tres caudales de 10 mol/s |
| T4 | Dato vinculado a un bloque inexistente | Diagnóstico con referencia; ningún descarte silencioso |
| T5 | Salida exterior más rama a V2 | Rechazo de topología actual con todas las referencias relevantes |
| F1 | Volumen declarado pendiente, sin corrientes | No convertirlo en cerrado ni certificar listo |
| F2 | Cerrado explícito, combinación admitida | Ejecuta solo con todos sus datos; sin corrientes ficticias |
| F3 | Abierto con frontera aún pendiente | Diagnóstico de frontera; ningún caudal cero implícito |
| F4 | Cerrado explícito más corriente exterior | Contradicción ligada al volumen y conexión reales |
| F5 | Peticiones antiguas sin declaración nueva | Resultados e identidades previos conservados |
| Q1 | Misma fuente, misma petición reenviada | Mismo recuento y modelo; un solo término Q |
| Q2 | Q null frente a Q = 0 con unidad | Pendiente frente a dato explícito |
| Q3 | Adiabático/T impuesta/energía desactivada | Contradicciones o límites existentes conservados |
| Q4 | Fuente duplicada o compartida | Rechazo conforme a capacidades; ninguna distribución implícita |
| Q5 | Tanque con Q constante | Trayectoria contra referencia independiente |
| Q6 | Fuente exterior más contacto interno | Q12 se cancela; Q exterior permanece una sola vez |

En casos evaluables, `/validar` y `/resolver` deben coincidir en recuento y referencias de la misma petición. `/validar` no integra ni busca raíces. Mantén la precisión declarada del análisis estructural y del rango numérico; no presentar todos los recuentos como rango exacto.

Comprueba unidades equivalentes en al menos un caso material y uno térmico, y una ida y vuelta JSON mediante Node real para el nuevo campo opcional. No introducir una firma nueva ni cambiar el contrato de transferencia salvo que un defecto reproducido lo exija y quede documentado.

## 7. Pruebas, documentación y cierre

Añade una suite específica del encargo, organizada por los IDs anteriores. Las referencias físicas deben estar escritas fuera del motor. Conserva las suites anteriores y ejecuta la batería completa al final; ejecuta las sondas de auditoría si modificas ensamblaje, términos, dominio o topología que ellas cubran.

Genera pares de petición/respuesta ejecutando los endpoints. Incluye ejemplos de validación incompleta, frontera explícita, contradicción y resolución correcta. Para las regresiones, registra los cambios esperados frente a los defectos y las identidades que deben conservarse; no exigir un mismo `modelo_id` después de cambiar realmente la física o topología.

La nueva sección de `docs/ENTREGA_LABORATORIO_CODEX.md` debe incluir:

1. esquema exacto de cualquier campo nuevo y sus valores admitidos;
2. rutas, códigos y referencias para que Codex encuentre cada pendiente;
3. comportamiento de omisión/null/cero y compatibilidad histórica;
4. capacidades y limitaciones por combinación;
5. ruta oficial para declarar Q y relación con la fuente conectada;
6. qué datos permanecen válidos al insertar un volumen y qué debe volver a especificarse;
7. pruebas ejecutadas, tolerancias, ejemplos y archivos propios;
8. cualquier pendiente real, sin declarar terminado un caso que solo se haya propuesto.

Empieza por reproducir el Hito A. Continúa con B y C dentro de este alcance, sin esperar otra autorización. Si un problema exige ampliar la física fuera del alcance, conserva su diagnóstico explícito y documenta esa ampliación como pendiente independiente.
