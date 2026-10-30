# Supuestos por volumen y lectura del modelo — seguimiento

## Estado actual · entrega §22, revisión 8

Unidades/catálogo y especificaciones flexibles materiales ya están entregados e integrados: `INTEGRACION_ENTREGA_22.md`. No repetir los dos hitos de `ENTREGA_CLAUDE_ESPECIFICACIONES_UNIDADES.md`. El balance general permite una especie y uno/dos volúmenes materiales; el temporal exige caudales de frontera. Inversión temporal, otras simplificaciones, `latex_expandido`/`latex_sumatorias`, overrides por especie/propiedad, momento y ampliaciones físicas siguen pendientes.

## Base histórica después de la entrega §21

Leer `docs/ENTREGA_LABORATORIO_CODEX.md` §§16–21 antes de ampliar. Solo backend; conservar cambios ajenos, incluido `thermodynamics/proveedor.py`. Sin commit ni push.

**Ya entregado e integrado en frontend:** términos y cancelaciones globales (§16); transferencia de estacionario y firma JSON (§17); reacción con interfaz térmica (§18); interfaz material isoterma (§19); interfaz material con energía `ideal_volumen_fijo` (§20); una sola especie y selección de balances por volumen (§21). No repetir estos hitos. La revisión de esa entrega era 7; la actual es 8. El registro de integración está en `INTEGRACION_ENTREGAS_20_21.md`.

**Alcance real de §21:**

1. De 1 a 8 componentes, incluidos tanques de agua pura. Con una especie, x=1 proviene del cierre de composición.
2. `balances_por_volumen` sustituye al borrador local al enviar la solicitud. Cada familia admite true/false/null y procedencia. Materia sigue siendo necesaria; momento activo se rechaza. Energía admite todos, ninguno o un prefijo de la cadena. La respuesta distingue pedido, activo y ejecutado.

El frontend muestra pendientes, contradicciones y grados de libertad devueltos por el motor. Desactivar energía no borra temperaturas, fuentes o almacenamiento existentes: los conflictos se muestran para que el usuario los corrija. La ausencia de una relación de salida no es caudal cero.

**Fuera de esta entrega:** proveedor con transferencia selectiva (hito B), momento completo, reacción con interfaz material, más de dos volúmenes, especies personalizadas y overrides mixtos. Son ampliaciones independientes, no requisitos para desbloquear el tanque de agua.

**Situación de §20:** A está cerrado. B sigue bloqueado por propiedades parciales, un cierre de volumen coherente y una referencia independiente; no sustituirlos por propiedades de líquidos puros. Los overrides por especie/propiedad del apartado posterior siguen pendientes y son otro problema: no equivalen a habilitar B.

**Integración de §20 completada:** campos `cv` y `u_referencia` por especie, capacidades por combinación exacta, series E y límite térmico condicionado. No se convierte Cp en Cv ni se calcula energía transportada en el cliente.

**Pendientes para una próxima entrega, aún sin encargar:** otras simplificaciones locales; energía aguas abajo de un volumen sin energía mediante una frontera térmica explícita; `latex_expandido`/`latex_sumatorias`; overrides coherentes por especie/propiedad. Momento, más de dos volúmenes, reacción con interfaz material y proveedor con transferencia selectiva requieren hitos propios. Priorizar y documentar antes de implementar, sin prometer combinaciones por suma de capacidades.

Los apartados siguientes conservan contexto histórico y propuestas futuras. Esta sección prevalece sobre cualquier nota anterior que diga que §20/21 siguen pendientes.

## Implementado en frontend
- Vista detallada / compacta. Compacta conserva títulos y ecuaciones; oculta leyendas y notas.
- Supuestos globales editables; nuevos borradores vacíos comienzan con todas las simplificaciones desactivadas. Mesas guardadas y presets conservan sus decisiones físicas.
- Un borrador general NO acredita que el motor soporte toda su física.
- Adiabaticidad local usa el campo existente `almacenamiento[].energia.adiabatico` cuando existe cierre energético. Se bloquea su edición con T/Q impuestas o fuente exterior conectada. No se transforma una especificación en silencio.
- Fuente térmica exterior bloqueada si el sistema o el cierre destino es adiabático; interfaz interna sigue siendo independiente.

## Requiere backend antes de habilitar más controles locales
1. Contrato explícito por volumen para simplificaciones, herencia global y procedencia (elegido / preset / migrado), sin defaults físicos silenciosos.
2. Validar por volumen contradicciones entre piezas, especificaciones y términos anulados; citar bloque, conexión y supuesto en diagnósticos.
3. Devolver términos generales, eliminados y activos con sus motivos, desde el ensamblaje físico. No interpretar LaTeX.
4. Distinguir aporte no definido, impuesto y anulado. No inferir Q=0 simplemente por ausencia de fuente.
5. Declarar qué combinación general puede resolverse; momento y otras físicas pendientes deben diagnosticarse, sin fingir cálculo.
6. Pruebas: un volumen adiabático y otro con Q; interfaz interna en sistema sin calor exterior; cambio de supuesto invalida resultados/transferencia; compatibilidad de mesas anteriores.

No reemplazar el motor ni implementar estas decisiones numéricas en frontend. Revisar `docs/ENTREGA_LABORATORIO_CODEX.md` y contratos vigentes antes de ampliar.

## Estado de entrega
§20/21 integradas. Las ampliaciones enumeradas arriba siguen pendientes; fusionar Formular con Ecuaciones no las implementa.

## Notación de ecuaciones
Pendiente complementario: declarar `latex_expandido` y `latex_sumatorias` desde los términos estructurados del ensamblador, junto a la identidad de cada término y su símbolo de acumulación. El frontend expande los balances orientativos por conexión. Para las respuestas del motor mantiene su LaTeX original, habitualmente ya expandido; no reconstruye una ecuación a partir de texto LaTeX ni inventa una expansión cuando faltan metadatos.

## Contenedores y selección de balances (actualización UI)
La mesa conecta dos volúmenes creando una corriente intermedia única; conserva el contrato vigente y no duplica estados. Las ecuaciones muestran la corriente compartida y los términos con conexión emitidos por el motor. El panel de propiedades organiza variables y reacciones del volumen.
Cada nodo puede guardar `data.balances` y su procedencia. El adaptador envía la selección mediante `balances_por_volumen`, conservando herencia y omisión de documentos anteriores. El servidor decide compatibilidad y ejecución; ya no existe el bloqueo global anterior del frontend.
Pendientes: selección general de componentes por volumen y simplificaciones locales adicionales. Momento sigue sin resolver. La selección no elimina datos, reacciones ni cierres existentes.

## Modelo visual por contenedores · 10 octubre
El lienzo agrupa entrada exterior → volumen → salida exterior. Una corriente intermedia se proyecta como una línea entre contenedores. Los nodos y conexiones semánticos originales se conservan al guardar y enviar al motor; la proyección no modifica ecuaciones ni IDs. Conectar dos sistemas sustituye los extremos exteriores enfrentados por una corriente compartida, retirando las especificaciones de la alimentación que deja de ser exterior.
La definición de componentes, especificaciones, cierre, propiedades energéticas y reacciones está disponible desde el diagrama. Los grados de libertad y la clasificación de incógnitas provienen de /estudios/validar, nunca de un recuento inventado en el cliente. Los componentes siguen siendo globales (1–8); la selección por volumen usa el contrato limitado de §21.
La vista Experimentar conserva el mismo objeto de solicitud para modificar valores y resolver. Pendientes: elección general dato/incógnita por variable con diagnóstico de rango e independencia, especies personalizadas y más de dos volúmenes. No prometer solvencia porque GL=0.

### Panel directo por balances
La interfaz muestra Componentes (+ Añadir), Materia, Energía y Momento. La cantidad inicial se presenta como n₀ [mol]; no se usa «inventario» como etiqueta de configuración. La selección del cierre material se presenta por comportamiento de la salida. La activación numérica conserva los límites del motor. Agregar componentes mantiene el orden existente, amplía la estequiometría con coeficiente cero para la nueva especie y normaliza el alias binario x a x0; no inventa fracciones, propiedades ni cantidades iniciales. Se bloquea si existe una condición inicial transferida. Los valores calculados y los campos pendientes se distinguen visualmente.


## Componentes y propiedades de la mesa
El frontend consulta /laboratorio/sustancias/buscar y conserva el identificador del candidato elegido; no calcula propiedades químicas. La lista global genera un balance por especie por volumen desde la formulación. Añadir o retirar alinea nu, condiciones iniciales, cp/cv/u_referencia y especificaciones x; retirar especies que participan en una reacción se bloquea. Los modelos energéticos se eligen según la combinación declarada. Una sola especie ya está admitida; las especies personalizadas fuera del catálogo siguen pendientes.

## Prioridad: origen de propiedades por componente y por propiedad
La UI de componentes ahora guarda en `estudio.propiedadesComponentes` un borrador local `{[identificador]: {origen: 'thermo'|'manual', cp?: number}}`. No se envía como si el motor lo aceptara. Cp manual es J/(mol*K), sin conversión silenciosa ni referencia energética implícita. Si todos son manuales se adapta a `ideal_incompresible`; si todos son thermo se adapta a `proveedor_liquido`. Las selecciones mixtas bloquean validar/resolver. Implementar en backend el contrato de propiedades por especie/propiedad, priorización explícita de overrides y procedencia; mantener referencia de entalpía y coherencia entre Cp(T), h(T), U y energía de reacción. No rellenar Cp de thermo con una muestra constante para fingir mezcla de proveedores. Declarar propiedades admitidas, unidades, dominio, capacidades y rechazar overrides incompatibles. Pruebas: combinación Cp manual de A + Cp(T) thermo de B, integración independiente y conservación energética sin doble conteo. El borrador local debe migrarse al contrato validado antes de habilitar cálculos mixtos.
Temperatura, presión, almacenamiento y condiciones del estudio quedan en Experimentar, no en el editor de componentes.


La identidad visual (nombre + CAS + fórmula) se guarda en estudio.identidadesComponentes, separada del identificador de la especie. Las propiedades de referencia devueltas por /laboratorio/sustancias/buscar (ΔHf°, ΔGf°, Tb, Tm, Tc, Pc) se consultan desde el editor sin alterarlas; valores nulos siguen sin dato. h(T) se presenta como propiedad calculada, no constante. Extender overrides por propiedad requiere distinguir condiciones/referencia/fase y coherencia termodinámica; no equiparar h(T) con ΔHf°.


### Separación de relación de salida y valores del ensayo
UX: la elección del cierre material se configura explícitamente en Experimentar y se consulta en Ecuaciones. Diagrama mantiene variables y resumen de la relación. No cambia el contrato, ni introduce una ley hidráulica. Cambiar de relación no convierte números ni crea parámetros/condiciones iniciales por omisión; los valores ya declarados se conservan y la respuesta anterior pierde vigencia. Inventario constante, salida lineal, salida impuesta y volumen fijo mantienen sus nombres técnicos en la petición y sus significados previos.


### UI de Experimentar: valores, comprobación y resolución (10/10/2026)

La vista principal muestra campos de la solicitud por elemento y balance, con símbolo, nombre y unidad. Parámetros de fluido e interfaces declaradas tienen pestañas propias. Los campos omitidos se conservan omitidos y un cero escrito sigue siendo cero. La cuenta de valores pendientes es solo una ayuda de edición: los grados de libertad, incógnitas y ecuaciones independientes se muestran exclusivamente desde `modelo.clasificacion` de la respuesta vigente. Resolver requiere estado `valido` del endpoint `/validar`; cualquier cambio de solicitud invalida esa autorización visual. Método, perturbaciones, cinética, cambios de relaciones físicas, transferencias, importación e historial quedan en Opciones avanzadas. No cambia el contrato ni añade una tarea de backend.


### Contexto histórico: corrección del bloqueo anterior (10/10/2026)

El aviso «Activa los tres balances» era un bloqueo excesivo del frontend, no una limitación del acoplamiento. Se reemplazó por una comprobación compartida entre Diagrama y Experimentar que conserva la solicitud sin modificarla. Los estudios solo materiales pueden validarse con energía y momento desactivados. No se elimina un modelo térmico ni se simula la supresión de un balance material para sortear el contrato. El motor sigue decidiendo las combinaciones y los grados de libertad.

La petición de admitir una sola especie quedó cumplida en §21: capacidades declara 1–8, x=1 se obtiene del cierre y existen referencias analíticas de agua pura. No requiere otro cambio de backend.

La selección física limitada por volumen quedó cumplida en §21 y conectada en frontend. Momento activo sigue produciendo un diagnóstico; no es un solver general de ODE/DAE arbitrarias.

El texto de valores completos también se corrigió: una relación de salida ausente ahora se muestra como pendiente. Una lista de valores numéricos rellena no demuestra que el modelo esté cerrado.
