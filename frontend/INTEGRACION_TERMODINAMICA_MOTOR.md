# Integración de estado termodinámico en el motor

14 de octubre de 2026. Codex implementa frontend y contrato; el usuario confirmó que Claude continúa en backend. No se modificaron archivos de backend ni del proveedor para este encargo. No se modifica el laboratorio. Sin commit/push.

## Implementado

- `contratoTermodinamica.ts`: revisión 1, declaraciones excluyentes TP/PH/UV/UP, cantidades/composición por IDs, unidades y valores sin especificar, política de fases, capacidades y resultados.
- `estadoTermodinamicoHoja.ts`: estados por volumen o corriente, catálogo químico compartido, consulta/cierre explícitos y resultados vinculados a la firma de su declaración e identidades. Los resultados no se usan como datos de entrada. Una edición invalida su evaluación; una respuesta tardía no sustituye el estado nuevo. Los resultados guardados se vuelven a validar al leerlos.
- La identidad química se declara sin deducirla del nombre. Cambiar CAS retira una masa molar anterior que ya no tiene identidad válida; no conserva una conversión inconsistente ni cambia cantidades/caudales declarados. Dejar el campo CAS vacío no borra una identidad de proveedor existente. El servicio puede resolver ese ID y contrastar el CAS resultante con los componentes admitidos por el paquete.
- `servicioTermodinamica.ts`: consulta las capacidades del servicio independiente y valida peticiones/respuestas. Rechaza HTML, revisión/modelo/solicitud distintos y datos físicos reconstruidos incompatibles. Sin servicio no inventa propiedades ni utiliza el proveedor del laboratorio como fallback.
- `relacionesTermodinamicas.ts`: relación fundamental, potenciales, reparto material/energético, fracciones por base y restricciones de equilibrio. El potencial de estabilidad mostrado depende de las variables fijadas; no se afirma un mínimo G para una especificación UV.
- `/motor/hojas/[id]/estado`: vista Estado con dueño del estado, componentes, modelo publicado, datos con unidad y restricciones. Las ecuaciones se muestran aparte del formulario. Las fases y propiedades solo aparecen al recibir una evaluación validada; no se asigna una fase al catálogo de componentes.
- La consulta puntual no altera la identidad ni los resultados del solver manual. Si un documento solicita usarla como cierre dinámico, analizar/compilar/resolver lo bloquean explícitamente. El integrador local no ejecuta el modelo manual pretendiendo que usó propiedades reales.

## Qué comprueba el lector

IDs químicos, masa molar/fuente y CAS coherentes; T/P positivos; referencias energéticas; propiedades finitas y v positivo; h=u+Pv de mezcla y fases. U/h/s negativos por referencia son admisibles.

Composiciones suman uno y reconstruyen z_i=sum(beta_alpha x_i_alpha). Las fracciones molares, másicas y de volumen reconstruyen las mismas fases con las masas molares y volúmenes específicos. U/h/v/s globales se reconstruyen con fracciones másicas. Las solicitudes UV/UP además reconstruyen composición y energía total, y UV el volumen. Las fases ausentes no se publican como fases con composición inventada.

La respuesta debe certificar estabilidad con método/alcance y residuos. El lector exige el alcance de fases candidatas publicado por el modelo. Verifica restricciones solicitadas y no permite presentar un estado metastable como estable. No comprueba por sí mismo el algoritmo de estabilidad ni la exactitud experimental de las propiedades; esa responsabilidad es del proveedor y sus pruebas físicas. No utiliza Cp/Cv monofásicos como una capacidad bifásica ficticia.

## Entrega física pendiente

[CONTRATO_CLAUDE_TERMODINAMICA_MOTOR.md](CONTRATO_CLAUDE_TERMODINAMICA_MOTOR.md) especifica el encargo H0–H8, las dos rutas iniciales y las pruebas por hito. La evaluación puntual real, EOS/propiedades, búsqueda estable de fases y ejecución dinámica requieren esa entrega. El formulario puede conservar datos mientras falte servicio; no presenta una solicitud como estado calculado.

La selección geométrica/mecánica y los supuestos efectivos deben incorporarse al ensamblaje dinámico futuro. La página Estado inicial evalúa una consulta independiente de las cantidades y geometría del modelo manual, con esa distinción visible. No copia automáticamente T/P o U/V a las condiciones iniciales del solver. Una comprobación estática de fase no demuestra ausencia de cambio de fase durante una trayectoria.

## Verificación

- `npm run test:motor-fundamental`: las suites anteriores de materia, energía, acoplamiento, multicomponente, estructura y selección pasan tras los cambios de integración. La nueva suite está añadida al comando.
- `npm run test:termodinamica-motor`: 222 comprobaciones de protocolo, reconstrucción, unidades, restricciones, firmas, propietarios y guardas de ejecución; regresión de energía manual bit a bit. Los estados de prueba son sintéticos y están identificados como tales: no son validación de física termodinámica.
- TypeScript y ESLint pasan en los archivos modificados/nuevos.
- La petición HTTP de comprobación local fue bloqueada por los permisos de socket del entorno; no se verificó la ruta en un navegador. El bloqueo automático de uso del navegador informado anteriormente impide también cerrar la revisión visual. No se afirma verificación visual ni disponibilidad de endpoints que Claude aún no entregó.

## Seguimiento: definición del volumen y revisión visual

La limitación de navegador anterior quedó resuelta. Se verificó la nueva vista Estado: definición mecánica, datos iniciales compactos, datos de corrientes/parámetros bajo petición y enlaces a ecuaciones/campos reales. La consulta de propiedades queda en una pestaña separada. El servicio publicó un modelo de agua en su catálogo; esa observación no certifica todavía su física ni su uso como cierre dinámico.

La entrega está descrita en [DEFINICION_VOLUMEN_CONTROL.md](DEFINICION_VOLUMEN_CONTROL.md). Las selecciones usan las formulaciones existentes, con un único dato geométrico y sin modificar backend. La suite completa del motor, TypeScript, ESLint y las 229 comprobaciones nuevas de volumen pasan.

## Recepción H0/H1: evaluación real de agua

Recibida la entrega descrita en `docs/MOTOR_TERMODINAMICA_H0_H1.md`. Se probaron sus respuestas reales con el lector TypeScript: 21 comprobaciones de la suite de Claude y 34 adicionales en `verificar_entrega_h0_h1_motor.mjs`, incluida persistencia y separación del cálculo manual. Se añadió la suite al comando completo del motor, que pasa, junto con TypeScript y ESLint. No se reran aquí las 42 suites físicas del backend; la validación física publicada pertenece a la entrega de Claude.

El cliente contrasta la masa molar de `agua-iapws95:1` contra 0.018015268 kg/mol (IAPWS G5-01(2020), §3.2), incluso si no se declara en la solicitud y al recuperar resultados guardados. El contraste es específico del modelo/version, no un catálogo químico general ni un cálculo de propiedades en el navegador. Los modelos futuros requieren su propio fundamento de identidad; sus masas no se certifican por este único registro. No se rellenan datos de usuario con valores redondeados ni se eliminan contradicciones declaradas.

La pantalla ofrece solo las especificaciones publicadas. Si una hoja conserva una especificación aún no soportada, informa y bloquea Evaluar hasta cambiarla; no la sustituye automáticamente. Se muestra que la evaluación es una consulta puntual y no un cierre del solver.

Prueba visual con servicio real en la copia «QA · Agua real · consulta H1»: líquido a 25 °C/1 bar, vapor a 100 °C/1.01325 bar y rechazo en la banda crítica. Cambiar el dato o recibir un rechazo retira las propiedades anteriores. La copia queda con la consulta de líquido; las hojas originales no se editaron. Evidencia: `C:/Users/randa/.codex/visualizations/2026/10/05/01a10d5f-1a91-7ad0-b832-8e76aacc9d8e/agua-real-h1.jpg`.

Siguiente encargo: [CONTRATO_CLAUDE_TERMODINAMICA_H3.md](CONTRATO_CLAUDE_TERMODINAMICA_H3.md). Saturación e inversiones estáticas PH/UP/UV primero; contrato del coordinador independiente antes de H2/H4. La consulta real no habilita dinámica termodinámica todavía.

## Preparación del ensamblaje dinámico

Preparado [CONTRATO_CLAUDE_ENSAMBLAJE_DINAMICO_MOTOR.md](CONTRATO_CLAUDE_ENSAMBLAJE_DINAMICO_MOTOR.md) para concretar §C antes de H2/H4. Es un contrato propuesto para revisión E0; todavía no hay llamadas a nuevos endpoints ni cierre dinámico habilitado.

- `contratoEnsamblajeTermodinamico.ts`: petición/respuestas y catálogo/recuento. Conservación y estado termodinámico separados; una geometría o estado exterior referencia el dato único.
- `prepararEnsamblajeTermodinamico.ts`: adaptador puro de un volumen desde las formulaciones efectivas y sus datos, sin editar la hoja, consultar propiedades o integrar. Preserva bases de caudal/composición por separado, trazabilidad, condiciones iniciales y rutas. No importa resultados de consultas ni parámetros inactivos del modelo afín.
- `cierresDinamicos` opcional: selección explícita de modelo/política y relaciones de transporte. No guarda otro banco de valores. Ausente conserva comportamiento e identidad anteriores; presente bloquea analizar/compilar/resolver por la vía manual hasta tener el coordinador.
- Presión de corriente como dato propio o continuidad explícita; nunca se copia automáticamente la presión del tanque. Contradicciones de cierre, densidad, políticas, presión adicional en un rígido, duplicados y falta de extracción bifásica quedan visibles en preparación.
- La preparación no entrega recuento/GL ni afirma estado listo. Esa certificación pertenece al ensamblaje del backend. Formas/regímenes fuera del primer hito se diagnostican; no se omiten otros volúmenes.

Pruebas: la suite completa del motor pasa. `verificar_preparacion_ensamblaje_termodinamico.mjs`: 40 comprobaciones de estructura, fuente única, presión, donantes, bases, historia, persistencia e incompatibilidades; ninguna se presenta como prueba de dinámica real. TypeScript y ESLint se verifican con los archivos nuevos/modificados. No se modifican pantallas, backend o laboratorio en este encargo.

## Recepción H3

Recibida la entrega de `docs/MOTOR_TERMODINAMICA_H3.md`: mismo protocolo y modelo, ahora TP/PH/UP/UV. Sus 15 pares de ejemplos pasan el lector TypeScript. Las 35 comprobaciones de la suite de Claude y las 67 nuevas de `verificar_entrega_h3_motor.mjs` pasan; la suite completa del motor sigue pasando. Las pruebas físicas del backend son responsabilidad de la entrega de Claude; no se presentan los tests del lector como auditoría independiente de la EOS.

El lector rechaza también Cp/Cv globales para el agua sobre saturación cuando solo se publica una fase en el extremo (verificación `equilibrio`). Conserva Cp/Cv de cada fase. No se agregan capacidades o calor latente calculados en frontend.

La selección de especificación conserva los datos comunes, evita borrar datos al pulsar el tipo activo y mantiene composición 1 al volver de UV/UP a TP/PH para una especie. No copia T/P del resultado calculado ni inventa composiciones para mezclas. La lista local de diagnósticos ya no se etiqueta como un número de datos faltantes; ese número podía contar dos diagnósticos del mismo campo.

Consulta real en la hoja independiente «QA · Agua real · UV bifásico H3», ID `4d607dac-5b74-4842-8f43-3a7854b08126`: 10 kg, 1 m³ y 15000 kJ. Dos fases, T≈444.179 K y P≈812082 Pa; vapor con fracción másica≈0.419307 y volumétrica≈0.993522. Se comprobó cambio UV→PH con composición 1 y P pendiente, y que pulsar UV activo no retira el resultado. Las hojas originales no se editaron.

Evidencia visual guardada en `C:/Users/randa/.codex/visualizations/2026/10/05/01a10d5f-1a91-7ad0-b832-8e76aacc9d8e/agua-bifasica-h3.jpg`. TypeScript y ESLint sin errores. La consulta final queda guardada como UV; al abrir Estado de nuevo, entrar en «Consultar propiedades» para ver sus resultados.

H3 cierra la entrega estática solicitada, dentro del dominio declarado. La prioridad siguiente queda en E0 del contrato de ensamblaje, antes de H2/H4. `dinamica:false` sigue respetado; una consulta bifásica guardada no habilita Resolver con propiedades reales.

## Consolidación solicitada por el usuario

Los dos enlaces de ensamblaje entregados al usuario eran el mismo archivo. Se consolidó [CONTRATO_CLAUDE_ENSAMBLAJE_DINAMICO_MOTOR.md](CONTRATO_CLAUDE_ENSAMBLAJE_DINAMICO_MOTOR.md) como un único encargo activo de E0–E3: preparación/contrato, validación/recuento/inicialización y resolución dinámica rígida, a presión prescrita y con tratamiento de fases. Su orden interno conserva las comprobaciones físicas, pero ya no pide una entrega aislada de E0 ni nuevas autorizaciones entre fases. Las menciones anteriores a E0 como siguiente entrega son seguimiento histórico sustituido. Esta actualización es documental; no habilita todavía nuevos endpoints ni cambia código o capacidades.
