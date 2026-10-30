# Estado del modelo en Experimentar

**Estado: entregado en §23 / revisión 9 e integrado en frontend.** El encargo de abajo se conserva como registro histórico. No encarga trabajo nuevo. El indicador lee ahora `recuento` y sus referencias; los límites estructurales y las cotas provienen del servidor. Ver [integración de la entrega 23](INTEGRACION_ENTREGA_23.md).

11 de octubre de 2026. Actualizado tras la revisión §22.7 de Claude. Base vigente: §22 / revisión 8; la corrección de `null` es aditiva y no cambia esa revisión.

## Encargo vigente para Claude

Implementar en backend el recuento canónico y los diagnósticos referenciados descritos en este documento. Esta es la siguiente prioridad: que un experimento pueda completarse y resolverse con un indicador fiable mientras se introducen valores. No es otra revisión de `INTEGRACION_ENTREGA_22.md` ni un encargo para ampliar la física.

Trabajar solo en backend, documentación de entrega y pruebas. Conservar el frontend y los cambios ajenos de `thermodynamics/proveedor.py`. No hacer commit ni push. No repetir los hitos de unidades/selección de variables ni pedir que se vuelva a priorizar la lista histórica de `SUPUESTOS_POR_VOLUMEN_CLAUDE.md` para iniciar este trabajo.

## Punto de partida confirmado por la última entrega

Claude informa 32 suites en verde y 82 comprobaciones en la suite de unidades/especificaciones, incluidas seis nuevas para opcionales `null`. Esta cifra corresponde a su verificación del backend; no a una nueva ejecución desde frontend.

§22.7 corrige `backend/schemas_estudios.py`: `condiciones_iniciales`, `entradas_temporales`, `especificaciones`, `almacenamiento` y `supuestos` admiten `null` como ausencia, igual que la colección vacía correspondiente. Conserva los resultados e identificadores de las formas equivalentes. Si falta información física, la diagnostica el motor con código y pieza; no un 422 anónimo de Pydantic. `null` no es el valor numérico cero.

También quedaron confirmados los 62 ejemplos reenviables a `/validar`, el caso inverso de 36 kmol/h → tres corrientes de 10 mol/s, la retirada del dato → GL real 1 y el temporal de 10 minutos → 700/800 mol. No corregir otra vez estos casos: conservarlos como regresión de esta entrega.

## Experiencia implementada

Una franja discreta permanece visible al recorrer los valores: Variables, Ecuaciones, Datos, Falta y un estado corto. No añade una explicación de grados de libertad ni un nuevo paso de navegación.

La comprobación automática reutiliza la petición que cargaba el catálogo: espera 400 ms después de editar, cancela respuestas anteriores y solo acepta la respuesta para la solicitud actual. Al cambiar un valor, desaparece el recuento anterior mientras se comprueba. Los borradores numéricos incompletos bloquean Resolver, incluso si el último valor enviado era válido. No se resuelve automáticamente.

Resolver se habilita con la confirmación del servidor. Un conflicto señala todos los campos identificados por el motor. Pulsar Falta lleva a los campos pendientes, sucesivamente; pulsar Revisar datos permite recorrer los conflictos. Elegir un campo no cambia su papel Dato/Calcular. Los avisos extensos siguen disponibles bajo petición.

Un dato redundante compatible se presenta como Sobreespecificado, con acceso a sus variables, pero permite resolver si el servidor lo admite. Sobreespecificación y contradicción no son equivalentes.

## Fuentes del recuento y límites actuales

En el estacionario lineal de balance_general se leen las variables de su matriz, las ecuaciones físicas y las especificaciones usadas. Falta sale de `rango.grados_libertad_reales`; no del recuento estructural general ni del número de casillas vacías. Por ejemplo: 5 variables, 2 ecuaciones físicas, 3 datos, Falta 0.

En las otras combinaciones se leen las variables del modelo, las ecuaciones independientes de su clasificación y las cantidades físicas normalizadas aceptadas, incluyendo las iniciales y excluyendo el horizonte y el integrador. Estos datos pueden incluir parámetros y no son necesariamente especificaciones independientes. El frontend no presenta la resta de esos tres números como un rango. Falta muestra el GL declarado por el motor cuando existe.

Si el servidor rechaza antes de construir/clasificar el modelo, Variables, Ecuaciones o Falta pueden aparecer como `—`. Se mantienen su diagnóstico y sus referencias. No se fabrica cero ni se transforma el número de diagnósticos en grados de libertad. La normalización de este recuento para todas las combinaciones queda pendiente en el documento de cola, abajo.

## Trabajo a implementar ahora

Prioridad acotada: metadatos de validación, sin ampliar todavía la física. Incorporar un recuento canónico del problema que se va a resolver, disponible también con datos incompletos. Debe distinguir variables totales, ecuaciones físicas independientes, especificaciones declaradas/independientes, parámetros, condiciones iniciales y restricciones. Declarar explícitamente si el rango es estructural, numérico o no evaluado.

No establecer `faltantes = variables - ecuaciones - casillas llenas`. En ODE/DAE, distinguir falta de iniciales de indeterminación algebraica y de iniciales inconsistentes. Publicar identificadores de variables pendientes, conflictos y redundancias que coincidan con el catálogo, además de las piezas/conexiones afectadas. Si una magnitud no se puede certificar con el montaje incompleto, devolver null y su estado, sin afirmar que basta con GL = 0.

La misma semántica debe servir a las familias soportadas del ensamblador. Esto no habilita sistemas arbitrarios, tensores, PDE, expresiones libres ni un solver DAE genérico. Conservar el contrato existente. Añadir un objeto versionado de recuento en las respuestas de `/validar` y `/resolver`, obtenido del mismo ensamblaje y análisis; el frontend conectará sus campos después de recibir la entrega.

### Contenido mínimo del contrato nuevo

- Estado de completitud: incompleto, listo, redundante compatible, conflicto o no evaluable. Mantener separado el estado del cálculo (`resuelto`, `parcial`, etc.) y declarar si se puede solicitar resolución. Datos redundantes compatibles no bloquean por sí solos.
- Recuentos para el indicador: variables del problema, ecuaciones físicas independientes, datos definidos y especificaciones independientes que faltan. Cada campo numérico debe tener una definición explícita y su ámbito; si no es determinable, devolver `null` con motivo. No mezclar el total del catálogo con las incógnitas de una matriz diferente.
- Desglose de especificaciones declaradas e independientes, parámetros requeridos/definidos, iniciales requeridas/definidas y restricciones. Separar datos faltantes de datos presentes pero incompatibles, fuera de dominio o sin unidad.
- Origen del análisis: estructural, rango numérico o no evaluado. Un rango numérico local no garantiza unicidad global; GL cero tampoco garantiza consistencia o existencia. Diferenciar ecuaciones de balances, relaciones constitutivas, especificaciones y verificaciones redundantes.
- Referencias de pendientes, conflictos y redundancias: IDs de variables del catálogo, piezas y conexiones. Para iniciales y parámetros, publicar una referencia estructurada de su función y ruta en la petición; no obligar al cliente a interpretar mensajes o índices de una lista para encontrar un campo.

Claude puede definir los nombres concretos del objeto y campos siguiendo las convenciones del backend, pero debe entregar su esquema exacto y ejemplos. No hace falta una aprobación adicional para implementar este alcance. Documentar cualquier diferencia justificada respecto al contenido mínimo, sin fabricar un recuento que el análisis no permite certificar.

### Límites y prioridad de los otros pendientes

No implementar en esta entrega otras simplificaciones por volumen, frontera térmica aguas abajo, `latex_expandido`/`latex_sumatorias`, propiedades por especie o por propiedad, momento, más de dos volúmenes, reacción con interfaz material ni propiedades del proveedor para transferencia selectiva. Permanecen en cola; sus restricciones actuales deben seguir apareciendo como diagnósticos y no como modelos listos para resolver.

Una validación parcial del montaje puede publicar el catálogo y los recuentos que conozca, aunque falte una especificación. Si faltan la topología, una relación constitutiva u otros elementos necesarios para construir el sistema, declarar qué análisis queda pendiente. No añadir relaciones o valores por omisión para obtener un número.

No cambiar resultados físicos, capacidades de resolución ni identificadores de modelos existentes solo por añadir estos metadatos. Conservar la equivalencia entre unidades y entre opcionales ausentes, `null` y colecciones vacías conforme a §22.7.

### Criterios de aceptación y entregable

1. Directo e inverso del balance general: mismo análisis del problema; al retirar el único caudal especificado, indicar una especificación independiente faltante y ofrecer referencias a las variables elegibles, sin imponer dónde dar el dato.
2. Inicial ausente e inicial incompatible en temporal: estados distintos y referencias precisas. No certificar que está listo solo porque el sistema diferencial está cerrado.
3. Datos redundantes compatibles frente a contradictorios: permitir la resolución de los primeros cuando el motor la admita; señalar todos los datos en conflicto de los segundos.
4. Recuento cuadrado con rango deficiente: no declarar listo. No contar la corriente compartida dos veces ni sumar verificaciones globales como ecuaciones independientes.
5. Combinaciones actualmente soportadas: material, energía, reacción e interfaces dentro de sus límites. El análisis debe reflejar restricciones y condiciones iniciales; no habilitar combinaciones que las capacidades rechazan.
6. Datos ausentes, `null`, cero explícito, unidades equivalentes y entradas sin unidad: conservar la semántica de §22.7 y del registro de unidades. Un cero válido cuenta como dato; un ausente no.
7. Recuento disponible en `/validar` antes de ejecutar el solver, con los campos no evaluables identificados; `/resolver` conserva un análisis coherente de la misma petición. No ejecutar integración ni búsqueda completa de raíces para contar datos.
8. Resultados e identificadores anteriores intactos. Añadir pruebas de estas condiciones y ejecutar la batería del backend; conservar regresiones de los 62 ejemplos y los tres escenarios confirmados en §22.7.

Entregar una nueva sección de `docs/ENTREGA_LABORATORIO_CODEX.md` con esquema exacto, definiciones de cada recuento, códigos/referencias, límites, compatibilidad, pruebas y archivos tocados. Añadir pares petición/respuesta de casos listos, incompletos, iniciales incompatibles, redundantes y contradictorios generados desde los endpoints. Indicar si requiere recargar el servicio y si cambia la revisión del contrato según la convención existente. No escribir respuestas de ejemplo a mano.

## Verificación

`npm run test:estado-modelo`: referencias reales del backend para estado, recuento, rango deficiente, conflicto, redundancia, iniciales y correspondencia de campos. `npm test`, `npm run test:entrega22`, TypeScript y ESLint de los archivos modificados. Pruebas visuales en una mesa de prueba independiente: comprobación automática, Resolver, navegación a pendientes, conflicto con ambos caudales marcados y borrador numérico incompleto.

La integración frontend descrita arriba no modifica el backend ni ejecuta un solver en el navegador. El siguiente encargo de este documento sí corresponde al backend. No hacer commit ni push.
