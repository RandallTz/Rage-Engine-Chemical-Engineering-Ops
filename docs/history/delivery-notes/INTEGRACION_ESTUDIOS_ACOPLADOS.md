# Estado vigente — revisión 4

Interfaz térmica, auditoría por combinación, procedencia por término y corrección de verificaciones globales entregadas en §16. El contenido anterior se conserva como registro de etapas; sus pendientes sobre estos puntos ya están resueltos. Estado actual: ENTREGA_FRONTEND_INTERFAZ_TERMICA.md. Próxima entrega: ENTREGA_CLAUDE_TRAZABILIDAD_REUTILIZACION.md.

# Integración frontend del contrato de estudios (§13)

Se conectan capacidades, ejemplos, validar y resolver a localhost:8004 (NEXT_PUBLIC_API_URL configurable). Capacidades vienen en la envoltura capacidades, no en la raíz. Estudio.tipo manda; el frontend lo deriva del selector y envía una bandera estacionario coherente.

La mesa conserva EstudioSistema.solicitud con el contrato nuevo. El grafo que se envía se deriva de las piezas/conexiones actuales, no de una topología vieja en el ejemplo. Datos viejos n/T/V se conservan en archivos antiguos y se advierten; no se envían ni se reparte n total. Cargar un ejemplo sustituye el montaje explícitamente. Preparar el montaje existente declara benceno/tolueno y valores visibles de alimentación, sin cierre ni inventarios por omisión. Otras sustancias y unidades se importan desde solicitud avanzada. Se validan forma y tamaño localmente; física y consistencia siguen en backend.

Formulario: tres cierres según capacidades, parámetros excluyentes al cambiar cierre, inventarios por especie con cero explícito/ausencia distinta, tiempo/muestras, integrador/tolerancias y escalones de F o fracciones base. Unidades de los ejemplos/importaciones se preservan; los nuevos parámetros se etiquetan con unidades explícitas. Resolver exige estado valido de exactamente la solicitud actual y capacidad compatible. Cambios invalidan la respuesta; cancelación descarta respuestas tardías. El adaptador térmico anterior y el CSTR no ejecutan solicitudes nuevas.

Resultados: validado no equivale a calculado; parcial es detención por evento y conserva series válidas. null de composición no se representa como cero ni se conecta en el gráfico. Se muestran método/elegido_por, clasificación y conservación; detalles completos de tolerancias, rigidez, tramos, restricciones, entradas, procedencia, estabilidad local y contraste. Variables y ecuaciones vienen del nuevo modelo, con resaltado por IDs. Solicitud y respuesta se descargan separadamente. La solicitud se guarda con la mesa; las respuestas nuevas son de sesión y exportables, no se añaden al cuaderno antiguo de resultados térmicos.

Verificado: contrato y respuesta real resuelto/parcial/valido de los ejemplos, series de longitudes incoherentes rechazadas, persistencia de solicitud, cero inicial y cambio de modo sin mutación. UI: temporal de dos volúmenes con conservación; vaciado con estado parcial alrededor de 50 s; estacionario del mismo montaje. No se habilita transferencia estacionario a temporal.

Pendientes de backend continúan: reacciones por volumen, momento, transferencia validada de estado. La tarea material inicial de INICIO_CLAUDE_MOTOR_ACOPLADO.md ya está implementada; no repetirla. Fuente de verdad: docs/ENTREGA_LABORATORIO_CODEX.md §13 y capacidades del servicio.


## Consulta por pieza y comparación

Inspector unificado de datos/cierre/inventarios, conexiones, variables y ecuaciones de respuesta vigente por pieza. Revisión guiada detecta aislados, cierres no declarados e inventarios por especie ausentes; no certifica cierre matemático. Hasta seis snapshots calculados por sesión (incluye parcial), sin eliminar anteriores al llegar al límite. Exportación de paquete versionado con fecha, nombre, solicitud, respuesta con procedencia y diagrama. Comparación identifica diferencias de solicitud y modelo_id; curvas solo con componente/ID/unidad compatibles y tiempos idénticos. No interpola ni convierte un estacionario en trayectoria. Si hay distintas mallas se muestran muestras finales con tiempos explícitos y se exportan ambos paquetes. La biblioteca local permite guardarlos y recuperarlos explícitamente en localStorage; también se pueden exportar. No se guardan automáticamente.

Importación de un paquete o comparación exportada recupera históricos en sesión, valida estructura y evita duplicados/límite excedido; no presenta el resultado importado como solución vigente. Inspector admite selección de piezas con selectores para teclado. Comparación declara versiones y métodos del motor.


## Entrega A: energía integrada

La interfaz consume §14 y las capacidades reales: energía habilitada y fuentes reactivas por volumen deshabilitadas. La configuración explícita conserva modelos ideal_incompresible/proveedor_liquido, parámetros, dominio, presión y almacenamiento energético por volumen. Los ejemplos sirven como inicio; el editor avanzado permite declarar solicitudes completas. U, T, h y Q se muestran como magnitudes diferentes; los resultados parciales conservan el evento y la trayectoria calculada.

La consulta del montaje se divide en Datos, Ecuaciones y Resultados. Las muestras sobre las piezas usan tiempos y valores del backend, sin interpolación. Los paquetes históricos conservan solicitud, respuesta y diagrama; la biblioteca local valida estructura, duplicados, conflictos y límite de seis ensayos sin borrar anteriores.

Pendiente de Claude: entrega B de ENTREGA_ENERGIA_REACTIVA_CLAUDE.md. No repetir A; añadir fuentes reactivas por volumen al sistema acoplado con capacidades, procedencia, conservación y pruebas independientes. Momento y transferencia estacionario → condiciones iniciales siguen pendientes.


## Preparación guiada e intercambio térmico

Tres etapas muestran únicamente Propiedades, Condiciones o Tiempo y método. El inspector distingue inventario, T inicial y U inicial. Cambiar el cierre material conserva los datos energéticos declarados. El selector de condición térmica sustituye T/Q de forma explícita; no crea conexiones, supone propiedades ni calcula magnitudes físicas. Adiabático exige retirar la fuente; Q/T requieren una única fuente. El backend conserva la autoridad sobre compatibilidad, solvencia y solución.

## Revisión física y siguiente etapa

Alcance físico y preparación identifica cierres, inventarios iniciales por especie, T/U y dominio omitidos. No calcula grados de libertad ni certifica DAE o combinaciones. Permite seleccionar piezas para corregir omisiones. Distingue capacidades anunciadas y validación de la solicitud vigente. Las interfaces futuras se explican sin habilitarlas ni enviarlas al motor. La próxima entrega independiente se describe en SIGUIENTE_CLAUDE_CIERRES_TRANSFERENCIA.md, después de cerrar B.

## Seis bases del modelo

Recorrido de consulta reutilizado en biblioteca de fundamentos y preparación física. Cada base presenta ecuación LaTeX, símbolos/unidades, aplicación en el laboratorio, hipótesis y límites. La biblioteca enlaza fundamentos existentes sin duplicar cálculos. Volumen rígido no se confunde con inventario constante; generación/consumo bruto no se deduce del neto; cp/cv y U/h se distinguen; estacionario no implica estabilidad. La entrega siguiente continúa pendiente de finalizar B.


## Entrega B integrada (§15)

Se conservan reacciones por volumen en solicitud, montaje, exportaciones y comparación; el formulario ofrece ejemplos del backend y revisión de definiciones, con edición completa mediante solicitud avanzada. Capacidades reales activan reacción; tasas fijas permanecen rechazadas. Se muestran nuevas series brutas/netas, calor de reacción, procedencia química y conservación elemental/masa/energía completa en la respuesta. La lectura guiada distingue método, restricciones y evidencia; Newton amortiguado y sus arranques/múltiples soluciones quedan en los detalles del estacionario. Referencia sensible con ΔH(298.15 K) explícita: la interfaz no añade Kirchhoff. Transferencia estacionario→temporal, momento y fase siguen fuera de alcance.

Mapa por pieza o sistema: clases, variables compartidas, valor declarado y determinada_por; el valor del modelo no se presenta como muestra temporal. Ecuaciones generales/activas, descartes y procedencia por bloques/conexiones/variables se muestran sin analizar LaTeX. Procedencia por término individual pendiente documentada en SIGUIENTE_CLAUDE_CIERRES_TRANSFERENCIA.md.

## Editor visual y consulta por pieza

La etapa Condiciones permite crear, asignar, retirar y editar reacciones por reactor: estequiometría por especie, k/unidad, T_ref/unidad, Ea, base, órdenes y reversibilidad (explícita o desde equilibrio). No se balancea ni se evalúan tasas en local. Crear una definición activa el supuesto reactivo; empezar con coeficientes cero y ley incompleta no habilita cálculo válido. La validación del backend es obligatoria. Otros campos de ley se conservan; solicitudes avanzadas siguen disponibles.

Selección desde ecuaciones resalta conexiones declaradas y piezas; seleccionar no cambia la firma física. Inspector ofrece última muestra real de la pieza con instante explícito. Resultados se agrupan en materia, energía y reacción; contraste de directa/inversa/neta y brutas/netas solo para la misma familia, unidad y muestras del backend, conservando null. No interpola mallas distintas.

Verificación visual: edición de k en ejemplo adiabático → validación → resolución; contraste de tasas; dos conexiones resaltadas; cambio posterior de k invalida la respuesta y deshabilita Resolver. Ancho móvil 390 px sin desbordamiento. Persistencia/cancelación siguen verificadas por las pruebas existentes.

## Reutilización entre módulos y ensayos

Reacciones exporta/prepara una definición versionada en una ranura local mediante acción explícita; si ya existe, exige reemplazo explícito. Incluye identidades, nu, leyes y base global declarada; no transfiere temperaturas, iniciales ni resultados. Laboratorio asigna a reactor elegido, remapea nu por identidad exacta, rechaza especies ausentes e IDs en conflicto. No adopta una base global implícita en leyes; exige declararla en cada una. La asignación requiere nueva validación del motor.

Inspector lateral edita valores existentes de especificaciones, cierre e iniciales con sus unidades; para añadir datos usa preparación completa. Consulta temporal muestra todas las variables de la respuesta en el mismo índice/t real, incluidos ceros y null, sin interpolación. Los IDs de reacción se conservan cuando no coinciden con el bloque propietario.

Ensayos guardados pueden cargarse como preparación nueva: se conservan históricos, se cancela petición anterior y se borra respuesta vigente incluso para una solicitud idéntica. Comparador muestra valores A/B con rutas de datos, diferencias abreviadas cuando alcanza límite, versiones/métodos y compatibilidad de mallas/unidades.

Verificación: editar T inicial desde inspector, validar/resolver, guardar A, recargar como preparación sin habilitar Resolver, editar y guardar B; diferencia inicial 321→322 K. Selector temporal al final mantiene todas las series en un instante. Transferencia desde Reacciones rechaza mezcla incompatible sin sustituciones; pruebas verifican remapeo y preservación de leyes. Siguiente documento: ENTREGA_CLAUDE_TRAZABILIDAD_REUTILIZACION.md; después de la entrega de interfaces en curso.

## Consulta vinculada y navegación
Armar conserva diagrama y consulta lateral; Experimentar reúne datos, validación, resolución y comparación. La conexión seleccionada muestra tipo, orientación y aportaciones estructuradas; cada término abre solo series cuyo ID declara el motor. Sin trayectoria, no se fabrica una curva. Los balances explicativos quedan plegados para montajes con contrato; resultados completos y muestras son consulta desplegable. Comparación distingue uno o varios datos modificados. Auditoría automática de 72 fundamentos y 340 fórmulas; se corrigen etiquetas obsoletas de GΔT, sin afirmar auditoría científica externa. No añade tareas backend ni altera la entrega que Claude está ejecutando.

## Transferencia §17 y bloqueo comprobado
Se conecta /transferir con selección de rama, objeto opaco, lectura n/U/origen, temporal sin iniciales manuales y escalones separados. Contratos y pruebas de conservación del objeto pasan. La integración real falla al validar tras JSON.parse/stringify: el servidor distingue 3887500.0 de 3887500 en la firma. Reproducción y aceptación entregadas en INCIDENCIA_TRANSFERENCIA_JSON_CLAUDE.md. No se añade canonicalización ni firma en cliente; Resolver permanece bloqueado cuando el servidor rechaza.

## Cierre de firma · 2026-10-09
§17.11 verificada con estados nuevos de /transferir y JSON nativo de Node: energía, escalón, reacción y rama encendida pasan /validar y /resolver. Servicio reiniciado sin modificar backend. La UI informa que las firmas anteriores requieren regenerar el estado; no corrige objetos ni firmas. Advertencias de contraste se mantienen aunque la integración termine resuelta. npm test completo pasa.

## §18 · reacción e interfaz térmica
Los editores consultan la fila exacta materia+energia+reaccion+interfaz y el tipo de estudio; una capacidad individual no habilita la combinación. El estacionario de interfaz sin reacción conserva su alcance solo en cadena. Correcciones de redondeo del objeto transferido visibles y preservadas en persistencia. Resultados parciales sin muestras muestran el evento sin fabricar datos ni trayectoria. Tests de cinco contratos nuevos, capacidades, persistencia y parcial sin muestras.

## Próxima entrega estructurada · transferencia de materia
Contrato propuesto en SIGUIENTE_CLAUDE_TRANSFERENCIA_MATERIA.md, pendiente de backend. Primer hito: dos compartimentos diluidos a V fijo, isotermos, sin reacción/energía, una especie transferida y reparto lineal declarado. No reutilizar inventario constante para una transferencia selectiva sin compensación. Sin estado de interfaz. Temporal conjunto y referencia analítica independiente. Estacionario indeterminado sin total conservado; no habilitar transferencia de origen todavía. Consulta de intercambios añadida al frontend como explicación, sin piezas ejecutables ni endpoints inventados. El inspector conserva tipos desconocidos en vez de presentarlos erróneamente como trabajo.

## Consulta compacta y perturbaciones
ResultadosEstudio integra ConsultaVolumen: alcance por IDs declarados, ecuaciones activas numeradas, balances/relaciones/verificaciones diferenciados por metadatos estructurados. No se infiere una ley del LaTeX ni se divide la resolución en piezas. Procedencia, forma general y términos descartados se consultan bajo demanda; variables y curvas conservan IDs del motor. La curva vacía no se representa. EditorPerturbaciones permite elegir especificación F/T/Q/x, declarar instante/valor/unidad heredada explícita y conservar el objeto inicial transferido. No impone perfiles ni simula desde el cliente.
Revisión de navegador: cargar Dos reactores con transporte compartido, validar, resolver, consultar rx1 (cuatro balances), guardar ensayo en sesión. Pruebas automáticas, lint y build pasan. No equivale a una validación independiente del motor físico.

## Vista de experimentación dividida y trazabilidad legible
Montaje de consulta a la izquierda y panel de preparación/resultados a la derecha; diagrama compacto de presentación sin alterar posiciones persistidas. Selección por piezas mediante click o selector de teclado sincroniza alcance de ecuaciones. Consulta separada en ecuaciones, variables y resultados. Nombres derivados de bloque/especie declarados conservan IDs; desconocidos no reciben identidad inventada. Comparación identifica base/variante; reutilizar conserva históricos y prepara nueva solicitud sin respuesta vigente. Diagnósticos ubican piezas declaradas, sin inferir campos ausentes. CSS responsive apila paneles y hace visibles focos de teclado. Verificado cargar, validar, resolver y seleccionar rx1 desde el navegador; no se modificó el motor.

## Reproducibilidad y consulta temporal
Edición numérica con borradores: blanco, signo o exponente incompleto no reemplazan un valor por cero ni se envían. El envío se bloquea ante borradores inválidos en campos declarados; las altas opcionales de nuevas interfaces/escalones no bloquean un estudio que no las usa. Los campos opcionales admiten ausencia explícita. Resumen previo muestra datos declarados y distingue respuesta calculada. ConsultaTemporal conserva muestras exactas para todas las series, eventos y perturbaciones; marcadores de curva solo cuando los instantes están en segundos, sin conversión implícita. Informe HTML imprimible con MathML, ecuaciones/terminos, preparación, resultados originales, advertencias, conservación y procedencia escapada; siempre se etiqueta instantánea histórica. Prueba real: vaciar densidad bloquea enviar; corregirla permite validar y resolver. Pruebas de cero, exponentes, desbordamiento, escape de HTML y MathML añadidas.

## §19 integrada
Tipo transferencia_materia e interfaces_materiales preservados por adaptador, mesa, ensayos y exportaciones. Editor de especie/L/H sin valores físicos por omisión, capacidad exacta materia+interfaz_material temporal, cierre volumen_fijo disponible en compartimentos conectados. Inventarios cambian, V fija sin densidad impuesta. Energía, reacción e interfaz térmica no habilitadas en esta combinación; estado transferido desde estacionario deshabilitado. Concentraciones/tasa, constantes de tiempo, conservación, límite y nuevo indicador de horizonte rápido visibles desde respuesta. Reparto límite no presentado como estacionario único. Pruebas de siete contratos (sin unidad rechazado estructuralmente), persistencia y adaptación. Servicio local reiniciado; casos válidos resueltos y rechazos esperados comprobados.

## Recorridos de investigación y siguiente entrega
Tres rutas basadas en ejemplos obtenidos del servicio: reaccion-interfaz, interfaz-material y energia-estacionario (requiere transferencia explícita y escalón posterior). Plan de pregunta/predicción/cambio/conclusión separado del modelo físico y persistido opcionalmente en paquetes; importaciones anteriores sin plan compatibles. Comparación e informe HTML incluyen el plan histórico. Ningún parámetro se modifica automáticamente al proponer una variante. Pendiente backend: SIGUIENTE_CLAUDE_TRANSFERENCIA_MATERIA_ENERGIA.md, hitos A propiedades declaradas y B proveedor. No habilitado en frontend.

## Revisión de interacción mientras se amplía transferencia material + energía

- Validar, resolver y obtener/aplicar un estado transferido quedan bloqueados con borradores numéricos incompletos. El valor previo no se envía como si fuera el texto visible.
- La guía de avance respeta ese bloqueo; el aviso explica cómo continuar.
- Una respuesta parcial sin muestras no ofrece un deslizador ni intenta formatear valores inexistentes.
- Nueva consulta de dependencias por variable: utiliza exclusivamente variables, acumulación y términos declarados por el motor. No infiere causalidad ni clasifica DAE.
- Texto del alcance incluye la transferencia selectiva disponible; la explicación de transferencia no disponible distingue esta combinación de otras.

Verificación: pruebas completas de frontend, lint y compilación. Las pruebas existentes cubren persistencia de interfaces, estado transferido, planes de investigación y resultados históricos.

Seguimiento: quedan por revisar los editores numéricos antiguos fuera del preparador acoplado y hacer una revisión visual específica de teclado y pantalla estrecha. No se declara completada esa auditoría. Claude continúa con SIGUIENTE_CLAUDE_TRANSFERENCIA_MATERIA_ENERGIA.md; estos cambios no requieren ampliar el contrato.

## Recorrido de una pieza a un sistema multifísico

Se mantienen seis pasos sin refactorizar el motor: definición de sistema/componentes, balances por especie y física, propiedades, cierres/conexiones, ensamblaje global y estudio/método. El ejemplo didáctico de mezcla perfecta varía 2–4 etiquetas de especie y 1–2 volúmenes; escribe balances simbólicos, no resuelve ni transmite una petición. Distingue balance total derivado, restricciones e incógnitas independientes.

El diagrama de Experimentar ahora identifica almacenamiento y especies declaradas, distingue tipos de intercambio y permite consultar ecuaciones por pieza o conexión. Se utilizan exclusivamente origen_bloques, origen_conexiones, términos y variables de una respuesta vigente del motor. Ausencia de metadatos se muestra como ausencia; el dibujo no genera ecuaciones.

No requiere una entrega adicional de backend. Persisten sus límites: momento no habilitado, componentes/fases y topologías dentro del contrato existente; la explicación general no habilita combinaciones arbitrarias ni un solver DAE universal.
## Recorrido continuo: una historia y un mismo montaje

La vista guiada utiliza ahora un único recipiente con A/B y seis acciones progresivas: inventarios, transporte, transformación interna, energía/propiedades, segundo recipiente y estudio temporal/estacionario. El diagrama es seleccionable con ratón y teclado y destaca el mismo término en la ecuación. Los contenidos amplios quedan en «Ver la formulación» y «Profundizar». La pregunta sobre A → B da retroalimentación sin bloquear el avance.

La reacción es ilustrativa (A/B con igual masa molar) y solo ocurre en el primer recipiente. U y h usan una referencia química compatible: el ejemplo no añade calor de reacción duplicado. No se calculan estados ni se genera una petición ejecutable. Las combinaciones numéricas siguen bajo el contrato del motor.

Se verifica LaTeX para todas las combinaciones simbólicas, signos de reacción, identidad de la corriente interna y energía. La lectura móvil apila los recipientes y la navegación de pasos lleva el foco al título. La biblioteca conserva su estado al volver desde el recorrido.

### Recorrido de fundamentos: lectura vinculada y salto al cálculo (2026-10-09)

- Navegar por los seis pasos conserva las piezas elegidas y el régimen. Se eliminó la incorporación implícita de piezas al saltar de paso. Conectar un segundo recipiente añade explícitamente la cadena de alimentación/salida; retirar el flujo retira también esa conexión.
- Cada acción conserva una instantánea antes/después del balance del primer recipiente, con especie y familia de balance. La comparación no es un resultado numérico.
- Vista conjunta de diagrama y balances en escritorio; selector Sistema/Balance en móvil. Consulta accesible de símbolos con significado, unidad y selección de su origen.
- Lista de preparación dependiente de las piezas activas; no calcula rango ni certifica grados de libertad.
- El caso numérico separado usa GET /laboratorio/estudios/ejemplos/dos-volumenes-tau-distintas. Se envía su petición sin transformar A/B ni alterar la mesa. POST /validar precede a POST /resolver; abortar o salir cancela la petición. Diagnósticos, método, eventos y respuesta completa se conservan.
- Las series medio.x0 y out.x0 son las composiciones de salida del caso real. Por su supuesto explícito de mezcla perfecta representan las composiciones de los recipientes; no se recalculan inventarios o composiciones en frontend.
- El caso se mantiene al cambiar de paso durante la sesión. Su descarga conserva petición y respuesta. No se modificó el backend ni se añadió un solver local.

### Simplificación del recorrido guiado (2026-10-09)

Sustituye la presentación anterior: seis círculos marcan el paso actual y los pasos visitados (no certifican aprendizaje). La vista principal contiene un título, una instrucción, el dibujo, una sola idea y la navegación. Se retiraron de esa vista las filas de supuestos, el mapa físico, las unidades, las comparaciones y los requisitos. Se conservan bajo una consulta opcional que se cierra al cambiar de paso. El primer dibujo usa A/B y «componentes»; el término técnico inventario se explica únicamente al consultar las ecuaciones. El caso numérico final aparece solo al solicitarlo. No cambia la formulación ni los endpoints.

### Balances visibles y bloque fundamental (2026-10-09)

El inicio parte de acumulación = entrada − salida + generación − consumo y distingue su interpretación para especie, energía y momento. Se incorpora anatomía de variables, balances, relaciones, acumulación y puertos. Las tres familias de ecuaciones y sus leyendas permanecen visibles, con A/B simultáneos. En el inicio se muestran formas locales y relaciones de Fick, Fourier y fluido newtoniano; después, materia/energía usan los balances integrales de los recipientes y momento conserva su referencia conceptual. Fick se declara como cierre constitutivo, no ley de conservación. Navier–Stokes declara fluido newtoniano incompresible con rho/mu constantes; no se habilita CFD o un solver de momento. El balance energético persiste cuando Q externo es cero. Las condiciones profundas y referencias documentales quedan en desplegables. No cambia el contrato del motor.
