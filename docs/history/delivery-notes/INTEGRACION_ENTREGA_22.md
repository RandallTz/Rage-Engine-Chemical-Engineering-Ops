# Integración §22 — especificaciones flexibles y unidades

Fecha: 11 de octubre de 2026. Backend conectado: revisión 8.

## Experiencia principal

Experimentar muestra una lista de variables con nombre del elemento, elección **Dato / Calcular**, valor y unidad. La corriente intermedia aparece una sola vez, marcada como compartida. Las cantidades iniciales se muestran en un grupo separado en el estudio temporal. Las variables derivadas aparecen únicamente al pedirlas.

La elección se habilita según `catalogo_variables` del servidor. Un cambio a Calcular retira la cantidad declarada; volver a Dato deja el campo vacío. No se introduce cero ni se conserva una especificación oculta. Los campos incompletos se mantienen como borradores y bloquean las acciones de cálculo.

Los ejemplos anteriores conservan visibilidad cuando el servidor serializa los campos opcionales como null. En estacionario, las condiciones iniciales null siguen siendo opcionales. Las gráficas esperan dimensiones positivas antes de renderizarse, también cuando se cambia entre vistas.

**Comprobar modelo → Resolver** conserva una sola acción principal. El balance general usa `estacionario_lineal.rango.grados_libertad_reales` para mostrar GL, en lugar del recuento estructural anterior. El cliente no calcula rangos ni decide independencia de ecuaciones. La comprobación deja de ser vigente cuando cambian los datos.

Los resultados estacionarios muestran los tres caudales y las cantidades que devuelve el motor, incluidos los datos. Las advertencias relevantes y los eventos permanecen visibles; los diagnósticos informativos, el catálogo completo y las cantidades normalizadas se consultan en Detalles técnicos.

## Unidades

Se consulta `GET /laboratorio/estudios/unidades`. El adaptador lee `unidad_interna`, factor y desplazamiento publicados; no mantiene una tabla paralela. Los campos ofrecen las unidades de la magnitud admitida. Cambiar la unidad convierte el valor visible conservando la cantidad física, y el servidor recibe valor y unidad explícitos para normalizarlos a SI.

Duración permite s/min/h. Se conserva la diferencia entre temperatura absoluta y diferencia de temperatura. No se ofrecen conversiones masa/moles, volumen/caudal molar o presión relativa/absoluta que requieran otros datos. Un catálogo no disponible conserva la unidad declarada, sin inventar factores.

En las gráficas, convertir unidades afecta solo la presentación. La respuesta, tabla original y estado transferido se conservan intactos. El tablero permite curvas paramétricas, varias Y, ejes según unidad, distribución vertical/paralela, arrastre, tamaño y persistencia.

## Modelo y compatibilidad

El balance general se activa explícitamente desde **Ajustes → Balance y relaciones de salida → Usar balance general**. Antes de aplicar, se muestra qué relaciones y parámetros se retirarán. Los modelos antiguos mantienen su física; no se elimina una relación kN de un montaje existente sin esa acción.

`seleccion_variables` se conserva en solicitudes, guardados, exportación e importación. Las elecciones se recuerdan por tipo de estudio en `EstudioSistema.seleccionesGeneral`; cargar otro montaje reinicia esa memoria. Cambiar a temporal no convierte cantidades estacionarias en condiciones iniciales ni inventa caudales faltantes.

El catálogo se solicita con el montaje real a `/validar`, incluso incompleto. Una respuesta de catálogo no habilita Resolver ni reemplaza el resultado de la comprobación explícita. Las respuestas de montajes anteriores se descartan al cambiar el contexto; una consulta fallida muestra un mensaje breve.

## Límites conservados

- Balance general: una especie, uno o dos volúmenes en serie, solo materia y sin mezclar cierres.
- Estacionario: datos e incógnitas admitidos por el catálogo, con rango calculado por el servidor.
- Temporal: todos los caudales son datos de frontera y las cantidades iniciales deben declararse. Un caudal ausente queda pendiente.
- No se habilitan objetivos finales inversos, expresiones arbitrarias ni transferencia estacionario → temporal del balance general.
- Energía, reacción, interfaces y otros cierres conservan sus contratos existentes. Esta integración no amplía su elegibilidad Dato/Calcular.

Pendientes históricos siguen en `SUPUESTOS_POR_VOLUMEN_CLAUDE.md`. No volver a pedir a Claude los dos hitos de `ENTREGA_CLAUDE_ESPECIFICACIONES_UNIDADES.md`: están entregados en §22.

## Verificación

- `npm test`: 14 scripts de regresión del frontend, completos.
- `npm run test:tablero`: catálogo real, conversiones, curvas, huecos/cero, ejes y persistencia.
- `npm run test:entrega22`: requiere el servicio local; contratos reales, elegibilidad, independencia de snapshots, selección, conservación de configuración por estudio, directo/inverso, rango, indeterminación, contradicción, frontera pendiente, temporal analítico, 600 s frente a 10 min y vaciado parcial.
- TypeScript y ESLint en los archivos modificados.
- Navegador: caso inverso con salida 36 kmol/h → tres corrientes a 10 mol/s; retirar ese dato → GL=1; restaurarlo → GL=0. Temporal F=3/2/1 mol/s, cantidades 100/200 mol y duración 10 min: resultados 700/800 mol, comparados en dos gráficas con s/min.

Las 32 suites de backend son las reportadas por Claude; esta integración no afirma haber vuelto a ejecutarlas. No se modificó código del backend, incluido el proveedor, ni se hizo commit/push.

Evidencia visual: `preview-integracion-22.png` y `preview-resultados-22.png`.
