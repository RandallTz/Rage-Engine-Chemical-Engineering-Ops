# Auditoría de Experimentar · 12 de octubre de 2026

Estado: auditoría y propuesta de reorganización. No se ha cambiado la interfaz ni el motor para producir este informe.

## Diagnóstico

La pantalla mezcla tres tareas que deberían distinguirse: definir el modelo físico, elegir la pregunta del estudio y especificar los datos para resolverlo. El problema principal es esa mezcla, no la cantidad de texto por sí sola. Quitar explicaciones sin corregir las acciones y sus consecuencias dejaría la misma confusión.

Hoy «Elegir datos e incógnitas» puede llevar a sustituir las relaciones físicas de todos los volúmenes. «Definir salida» puede abrir ajustes o asignar un modelo material, según el montaje. «Se calcula» sirve tanto para una incógnita elegida como para una variable determinada por una relación, y aparece incluso antes de saber si la incógnita quedará determinada.

La experiencia cambia entre dos formularios según el cierre de almacenamiento. Así, una misma tarea —dar valores al sistema de ecuaciones— parece funcionar de formas diferentes.

## Alcance y evidencia

- Inspección del flujo visible en la mesa existente «Mi primera mesa», sin editar sus datos, conexiones, relaciones ni tipo de estudio.
- Lectura de los componentes de Experimentar, los adaptadores de campos, la selección de variables y las acciones de configuración.
- Lectura de capacidades del backend local y validación de dos peticiones publicadas. Ambas devuelven `valido`: el estacionario inverso y el tanque térmico con capacidad máxima.
- No se ejecutó una nueva batería de simulaciones. Esta es una auditoría de UX y correspondencia con el contrato; no sustituye la auditoría numérica de física.

Evidencia conservada:

- [Pantalla de valores](C:/Users/randa/Desktop/reactive_distillation/frontend/auditoria_experimentar_2026_10_12/01-valores-salida.png).
- [Pantalla abierta por «Definir salida»](C:/Users/randa/Desktop/reactive_distillation/frontend/auditoria_experimentar_2026_10_12/02-ajustes-salida.png).
- [Capacidades, recuentos y catálogos obtenidos del servicio](C:/Users/randa/Desktop/reactive_distillation/frontend/auditoria_experimentar_2026_10_12/contraste-api.json).

## Hallazgos prioritarios

### 1. Elegir incógnitas se presenta como un cambio de formulario, pero cambia el modelo

**Prioridad alta.** El enlace «Elegir datos e incógnitas» abre `ElegirBalanceGeneral`. Tras aplicar, `activarBalanceGeneral` sustituye los cierres de todos los volúmenes y retira sus parámetros. Hay una revisión antes de aplicar en este camino, pero el nombre de la acción inicial promete otra tarea.

**Decisión:** elegir Dato/Calcular no debe cambiar ninguna ecuación física. Si la relación vigente determina una variable, se muestra como determinada por esa relación. Cambiar la relación es otra acción, identificada como edición del modelo y limitada al bloque correspondiente.

Fuentes: [EstudiosAcoplados.tsx](C:/Users/randa/Desktop/reactive_distillation/frontend/app/laboratorio/EstudiosAcoplados.tsx:103), [ElegirBalanceGeneral.tsx](C:/Users/randa/Desktop/reactive_distillation/frontend/app/laboratorio/ElegirBalanceGeneral.tsx:11), [balanceGeneral.ts](C:/Users/randa/Desktop/reactive_distillation/frontend/app/laboratorio/balanceGeneral.ts:14).

### 2. «Definir salida» tiene consecuencias diferentes según condiciones ocultas

**Prioridad alta.** Su callback puede abrir ajustes, asignar `balance_general` a un volumen nuevo o activar ese cierre en todo el montaje. Estas últimas rutas modifican el modelo directamente. La misma etiqueta no permite anticipar lo que ocurrirá.

Además, en la revisión visual el aviso señala Tanque 2, pero abre una sección con todos los volúmenes empezando por Tanque 1.

**Decisión:** un pendiente debe abrir el campo o la decisión exacta del bloque afectado. La acción no debe escoger una relación física por el usuario. Para una relación ausente: «Definir modelo de Tanque 2». Para un valor ausente: ir directamente a su fila.

Fuentes: [EstudiosAcoplados.tsx](C:/Users/randa/Desktop/reactive_distillation/frontend/app/laboratorio/EstudiosAcoplados.tsx:106), [siguienteDatoEnsayo.ts](C:/Users/randa/Desktop/reactive_distillation/frontend/app/laboratorio/siguienteDatoEnsayo.ts:11).

### 3. «Se calcula» reúne papeles matemáticos distintos

**Prioridad alta.** Puede significar incógnita del estacionario, variable derivada, estado que evolucionará o valor determinado por una relación. En el balance general estacionario, una variable sin selección explícita se presenta por defecto como Calcular. Sin embargo, por ejemplo, un inventario estacionario puede quedar indeterminado; el motor no fabrica un valor.

El catálogo ya distingue funciones, permisos y motivos. La UI no aprovecha esa distinción de forma uniforme.

**Decisión:** mostrar Dato/Calcular solo cuando ambos papeles estén admitidos. Una variable derivada lleva un estado breve como «Por balance» o «Por relación», con su dependencia disponible al pulsar. Un estado temporal lleva su condición inicial en la fila adecuada. «Calcular» expresa una selección, no una promesa de que el problema ya esté determinado.

Fuentes: [VariablesBalanceGeneral.tsx](C:/Users/randa/Desktop/reactive_distillation/frontend/app/laboratorio/VariablesBalanceGeneral.tsx:22), [VariablesExperimento.tsx](C:/Users/randa/Desktop/reactive_distillation/frontend/app/laboratorio/VariablesExperimento.tsx:33), evidencia del catálogo.

### 4. Elegir el estudio no está integrado con las especificaciones

**Prioridad alta.** Hay controles de estacionario/temporal en Experimentar y en la configuración de Ecuaciones. Experimentar conserva selecciones por tipo; la otra ruta no aplica la misma lógica. No existe una transición única que revise qué datos pasan a ser necesarios, inaplicables o contradictorios.

«Contenido constante» añade otra ambigüedad: fija la cantidad total, pero permite evolución de composición o temperatura. No equivale a un estado estacionario completo.

**Decisión:** una sola operación de cambio de estudio, invocable desde ambas vistas. Conserva los datos y elecciones anteriores; consulta la validación del nuevo estudio. Las condiciones iniciales aparecen únicamente cuando corresponden. Si aparecen nuevos pendientes, se señalan en sus filas. Nunca ajustar los caudales ni borrar valores para convertir un temporal en estacionario.

Fuentes: [EstudiosAcoplados.tsx](C:/Users/randa/Desktop/reactive_distillation/frontend/app/laboratorio/EstudiosAcoplados.tsx:96), [EstudioDelSistema.tsx](C:/Users/randa/Desktop/reactive_distillation/frontend/app/laboratorio/EstudioDelSistema.tsx:5), [balanceGeneral.ts](C:/Users/randa/Desktop/reactive_distillation/frontend/app/laboratorio/balanceGeneral.ts:26).

### 5. La lista de «salida» mezcla restricciones, leyes y datos

**Prioridad alta.** Sus opciones incluyen cantidad constante, una ley proporcional, caudal impuesto y compartimento cerrado con intercambio selectivo. Son decisiones físicas diferentes. La lista se filtra por interfaz material, pero no de forma completa por combinación y estudio.

**Decisión:** declarar la relación física en el modelo; introducir sus valores en Experimentar. El balance general sin ley adicional debe ser una alternativa explícita donde esté admitido. `F = kN` queda disponible como una relación concreta para quien la elija, sin tratarla como requisito genérico para simular acumulación. No añadir equipos para justificarla.

Al cambiar de relación, revisar los parámetros que dejan de intervenir. `configurarSalida` conserva los campos del cierre anterior mediante un spread; podrían quedar ocultos. Esto es un riesgo de transición observado en código, no un fallo físico reproducido en esta auditoría.

Fuentes: [SalidaVolumen.tsx](C:/Users/randa/Desktop/reactive_distillation/frontend/app/laboratorio/SalidaVolumen.tsx:6), [relacionSalida.ts](C:/Users/randa/Desktop/reactive_distillation/frontend/app/laboratorio/relacionSalida.ts:3).

### 6. Hay tres descripciones distintas de las capacidades

**Prioridad alta.** `limiteBalanceGeneral` rechaza energía y calor. La tabla general `cierres_de_almacenamiento.balance_general` también dice `admite_energia: false`. Pero la fila `materia_balance_general+energia` declara la combinación y el endpoint valida el ejemplo térmico publicado.

No implica que se pueda elegir cualquier incógnita térmica: ese problema inverso tiene límites propios. Sí demuestra que un predicado local antiguo o una bandera general no describen toda la capacidad actual.

**Decisión:** resolver primero esta incoherencia entre metadatos y montajes verificados. Los permisos deben depender del montaje y estudio actuales; no habilitar combinaciones simplemente por existir una bandera individual de energía o selección.

Fuentes: [balanceGeneral.ts](C:/Users/randa/Desktop/reactive_distillation/frontend/app/laboratorio/balanceGeneral.ts:7), [core/dinamica.py](C:/Users/randa/Desktop/reactive_distillation/core/dinamica.py:10473), evidencia API.

### 7. El contador global y las insignias locales cuentan cosas diferentes

**Prioridad media.** El indicador usa el recuento del servidor; la insignia del bloque cuenta campos locales vacíos. En la pantalla observada aparece Tanque 1 con «2» y Falta «≥ 1». Es legítimo contar magnitudes diferentes, pero visualmente parecen dos versiones del mismo dato.

**Decisión:** el contador de variables, ecuaciones, datos y faltantes sigue siendo canónico y respeta `null` y cotas inferiores. Las insignias de bloque, si se conservan, se llaman campos pendientes y se construyen desde las referencias del backend. Nunca calcular grados de libertad restando campos de un formulario.

Fuentes: [VariablesExperimento.tsx](C:/Users/randa/Desktop/reactive_distillation/frontend/app/laboratorio/VariablesExperimento.tsx:30), [VariablesBalanceGeneral.tsx](C:/Users/randa/Desktop/reactive_distillation/frontend/app/laboratorio/VariablesBalanceGeneral.tsx:8).

### 8. La selección heredada del diagrama puede dejar al usuario sin nada que llenar

**Prioridad alta.** La pantalla observada selecciona la salida del tanque y muestra dos filas «Se calcula». El pendiente real está en otro bloque. Hay que deducir que debe cambiar de pestaña, aunque el objetivo actual sea completar el modelo.

**Decisión:** conservar la selección cuando tenga datos útiles. Si solo tiene variables derivadas y el estudio está incompleto, hacer visible el enlace al pendiente concreto. Un clic en ese pendiente debe seleccionar y enfocar la fila; sin pasar por todos los ajustes.

### 9. Configuración obligatoria y opciones avanzadas están mezcladas

**Prioridad alta.** Ajustes contiene nueve destinos. Ahí viven decisiones obligatorias del modelo junto a integradores, perturbaciones, archivos, ejemplos y revisión técnica. Algo necesario para resolver parece opcional y secundario.

**Decisión:** las decisiones estructurales pertenecen al modelo y sus valores aparecen en la tabla experimental. Avanzadas contiene método, tolerancias y perturbaciones. Archivos y ejemplos conservan sus destinos propios. Un pendiente estructural abre una edición puntual; no obliga a recorrer este menú.

### 10. El catálogo y los formularios no tienen una correspondencia completa

**Prioridad alta para la integración.** Un formulario utiliza `camposExperimento`; otro filtra el catálogo con `.F` y `.n0`. El catálogo del tanque térmico incluye `tk.area` y `tk.capacidad_maxima`, pero esos campos no se generan en `camposExperimento`. Son parámetros opcionales: no hay que exigirlos para resolver. Si están presentes y son inválidos, o el usuario quiere declararlos, debe existir un editor localizable.

También hay campos numéricos con unidad fija en ajustes y con selector de unidad en la tabla experimental. Conviene unificar su edición, evitando dos ubicaciones con comportamiento diferente.

**Decisión:** un adaptador común entre catálogo, rutas y solicitud, con editores tipados para especificaciones, parámetros e iniciales. No generar un formulario genérico a ciegas ni escribir en rutas desconocidas. Un campo sin editor se diagnostica explícitamente; no se ignora.

Fuentes: [camposExperimento.ts](C:/Users/randa/Desktop/reactive_distillation/frontend/app/laboratorio/camposExperimento.ts:1), [VariablesBalanceGeneral.tsx](C:/Users/randa/Desktop/reactive_distillation/frontend/app/laboratorio/VariablesBalanceGeneral.tsx:16), evidencia API.

## Estructura propuesta

### Modelo: Diagrama y Ecuaciones

Define componentes, balances, conexiones y relaciones. Permite cambiar la ecuación que determina la salida o declarar que no se añade una ley de salida. No decide silenciosamente los valores para cerrar el problema.

Experimentar puede abrir una edición puntual del modelo cuando falte una relación, sin obligar a abandonar el contexto. Debe quedar claro que es un cambio de modelo, y qué bloque afecta.

### Experimentar: una tabla y una acción principal

1. Arriba: tipo de estudio y contador compacto.
2. Centro: variables agrupadas por bloque y balance. Cada fila contiene símbolo/nombre, papel, valor y unidad.
3. Temporal: iniciales e intervalo junto a los datos que correspondan. Estacionario: sin pedir iniciales como requisito del cálculo.
4. Resolver: acción estable. Los pendientes se abren desde el contador o desde su marca en la fila. No convertir «Resolver» sucesivamente en cambiar modelo, elegir relación y editar valor.
5. Avanzadas: método, tolerancias y perturbaciones. Dependencias y motivos disponibles al solicitar detalle.

No añadir una pantalla introductoria con teoría de grados de libertad, un asistente largo ni un panel permanente de instrucciones. El orden lo dan las filas, su disponibilidad y la navegación precisa.

La interfaz mantiene la misma forma aunque cambie la matemática. Los papeles permitidos sí cambian con el ensamblaje. Por ejemplo, el motor actual permite calcular un caudal estacionario del balance general, pero exige caudales como datos de frontera en su temporal. La UI debe representar esa diferencia, sin prometer un problema inverso que no está implementado.

### Resultados

Conservar tabla, gráficas y detalles técnicos. La base de presentación molar/másica puede vivir aquí; las unidades de entrada siguen siendo seleccionables por cantidad. Cambiar la presentación no debe parecer un requisito previo para llenar el ensayo.

## Orden de implementación

**A. Corregir significado y estado.** Separar acciones de cambio de modelo de selección Dato/Calcular; centralizar el cambio de estudio; contrastar capacidades; conservar valores y resultados históricos sin reutilizar una validación obsoleta.

**B. Unificar la tabla.** Un adaptador del catálogo y rutas para ambas familias de formulario. Distinguir dato, incógnita, derivada, parámetro e inicial sin añadir explicaciones permanentes. Enfocar pendientes en su bloque/campo; uniformar unidades.

**C. Simplificar navegación.** Una acción principal Resolver, edición estructural puntual y avanzadas realmente avanzadas. Retirar accesos redundantes después de comprobar que toda variable editable tenga un destino.

No ampliar simultáneamente el motor a problemas inversos generales, expresiones arbitrarias o nuevas operaciones. Primero hacer coherente el recorrido de las combinaciones ya verificadas.

## Trabajo acotado para Claude

1. Auditar y corregir las declaraciones de capacidades obsoletas, empezando por `balance_general` con energía y los métodos descritos para su estacionario. No cambiar el resultado físico para que coincida con una descripción antigua.
2. Mantener `catalogo_variables`, `recuento` y referencias como autoridad de papeles y completitud. Confirmar la estabilidad de las rutas para parámetros opcionales como área/capacidad y las restricciones al cambiar estudio.
3. Si se necesita procedencia estructurada de una variable derivada, acordar un campo tipado de ecuación/relación antes de implementar. No interpretar mensajes ni LaTeX para decidir permisos.

La reorganización inicial del frontend puede avanzar con el contrato existente. Este informe no es una autorización para una ampliación física del backend ni sustituye su siguiente encargo.

## Criterios de aceptación

- Estacionario directo e inverso del tanque: misma tabla; elegir un caudal como dato no modifica cierres. Retirarlo muestra el faltante real del servidor.
- Temporal existente con caudales 3/2/1 mol/s, cantidades iniciales 100/200 mol y 600 s: se puede llenar desde la tabla y resolver; referencia publicada 700/800 mol.
- Contenido constante con evolución térmica o composicional: no se presenta como equivalente a estacionario.
- Variable derivada, inicial e incógnita elegida tienen estados visuales distintos. Un inventario indeterminado nunca se anuncia como resultado calculado.
- Volumen nuevo sin relación: el pendiente abre ese volumen; no asigna una ley ni reemplaza relaciones de los otros bloques.
- Cambiar el estudio conserva datos anteriores y permite volver. Datos incompatibles siguen visibles y se señalan; no se corrigen automáticamente.
- Corriente compartida cuenta una sola vez. Insignias locales no simulan el recuento matemático.
- Todos los valores editables tienen unidad; cero y ausente siguen siendo distintos.
- Un parámetro opcional existente e inválido puede localizarse y corregirse. No obligar a introducir área ni capacidad si el montaje no las requiere.
- Una combinación no soportada se informa en el punto de elección, con el motivo disponible; no se habilita por una bandera general.

## Lo que conviene conservar

El recuento canónico, sus límites y referencias; las unidades explícitas; la distinción entre cero y ausente; la identidad única de corrientes compartidas; el mismo modelo acoplado para ambos estudios; y los resultados históricos separados del montaje actual. La reorganización debe hacer accesibles estas bases, sin ocultar restricciones ni añadir supuestos silenciosos.
