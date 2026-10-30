# Integración de la entrega 23: recuento canónico

11 de octubre de 2026. Servicio local recargado y verificado en revisión 9. Backend de referencia: §23 de docs/ENTREGA_LABORATORIO_CODEX.md.

## Experiencia

Experimentar conserva un indicador compacto: Variables, Ecuaciones, Datos y Falta. Cada número viene directamente de recuento.indicador; no se calcula Falta restando otros números ni contando casillas.

- Listo y redundante_compatible permiten Resolver, sujeto a datos numéricos válidos, capacidades y una comprobación vigente.
- Incompleto, conflicto y no_evaluable bloquean Resolver. Falta cero por sí solo no autoriza resolver.
- Un número desconocido se muestra como —. Una cota inferior se muestra como ≥ n, incluso cuando n es cero. Los motivos de null están disponibles al pasar sobre el dato.
- Si falta alguno de varios datos posibles, se marcan como candidatos y el enlace recorre esas variables; no se presentan todas como obligatorias ni se elige una automáticamente.
- Los conflictos marcan los campos asociados; los redundantes compatibles conservan la opción de resolver.
- Al editar se retira el recuento anterior hasta recibir la comprobación de esa solicitud. Los borradores numéricos inválidos bloquean el envío.

El panel del contenedor también usa Falta y la misma cota; no etiqueta este número como grados de libertad, pues puede incluir iniciales, parámetros o relaciones pendientes.

## Contrato y referencias

recuentoEstudio.ts define y valida la forma del objeto y sus referencias. Una respuesta con revisión 9 o superior debe incluir un recuento válido. Se conserva la compatibilidad con revisiones anteriores mediante el adaptador existente.

estadoModelo.ts lee la completitud independientemente del estado del cálculo. Las rutas estructuradas del contrato tienen prioridad sobre la correspondencia antigua por identificadores: selección de variables, especificaciones, condiciones iniciales por especie, almacenamiento e interfaces. No se analizan mensajes ni LaTeX para encontrar campos.

Los enlaces abren el elemento y enfocan el campo editable. Los campos de propiedades e intercambios también pueden abrir su pestaña. Una relación pendiente asociada únicamente a una conexión abre los ajustes de interfaces, sin inventar un valor ni tratarla como cero.

El objeto completo, sus definiciones, origen del análisis y desglose quedan en Resultados → Detalles técnicos → Recuento y referencias del problema. El indicador no presenta ese contenido en la pantalla principal.

## Verificación

- npm test: batería completa del frontend, incluido test:estado-modelo. El adaptador acepta las 80 respuestas de estudios con recuento presentes en docs/ejemplos.
- npm run test:recuento-servicio: los siete escenarios canónicos contra /validar y /resolver del servicio activo; los recuentos coinciden entre ambas rutas.
- npm run test:entrega22 y npm run test:recorrido-agua: recorrido directo/inverso, unidades, conservación del contrato anterior y resultados analíticos del tanque.
- TypeScript y ESLint de los archivos modificados: sin errores.
- Navegador, mesa independiente de prueba: elección de uno entre tres caudales; conflicto 10/5 con los dos campos marcados; redundancia compatible 10/10 que permite resolver; solución estacionaria con las tres corrientes a 10 mol/s; una interfaz sin conductancia abre sus ajustes; condición inicial pendiente selecciona su volumen y campo.

No se volvió a ejecutar la batería de 33 suites del backend: esa validación es la reportada por Claude. Las comprobaciones anteriores son de esta integración.

## Límites y cola

No se cambió código ni resultados físicos del backend. Fuera del balance general, el recuento sigue siendo estructural; la interfaz conserva esa limitación y no declara rango numérico.

Las propiedades por especie, otras simplificaciones, la frontera térmica explícita, LaTeX expandido del motor, momento y las ampliaciones topológicas/físicas siguen en PENDIENTES_BACKEND_CLAUDE.md. Esta entrega no las encarga ni habilita.

El seguimiento de propiedades faltantes quedó resuelto en §23.7 e integrado tras recargar el servicio. Las rutas `modelo_energetico.cp`, `cv`, `u_referencia`, `T_referencia`, `densidad_molar` y `dominio_T` se corresponden con sus campos visibles; las propiedades por especie conservan el componente. El catálogo contiene sus ids reales/provisionales. No se interpreta el mensaje del diagnóstico ni se infiere una propiedad ausente como cero.

Comprobación contra servicio: quitar Cp de benzene devuelve el mismo recuento y referencia en `/validar` y `/resolver`, y el adaptador encuentra su campo. En navegador, retirar Cp de Agua, cambiar a Tanque y pulsar Falta abre Propiedades y enfoca Cp; Resolver permanece bloqueado. Restaurarlo recupera el modelo completo.

La lectura Detallada de Ecuaciones comparte el catálogo de la validación vigente. Sus variables editables abren el campo correspondiente de Experimentar; las calculadas permiten consultar el resultado cuando existe. Los caudales del balance general respetan la selección Dato/Calcular y la unidad declarada. La validación automática no sustituye un resultado resuelto vigente.

Los nuevos escenarios y el siguiente encargo físico están documentados en `ESCENARIOS_AGUA_VALIDACION.md` y `SIGUIENTE_CLAUDE_TANQUES_CIRCUITOS_TERMICOS.md`.
