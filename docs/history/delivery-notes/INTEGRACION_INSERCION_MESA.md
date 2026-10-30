# Inserción de sistemas y conexiones sin pérdida de fronteras

Fecha: 12 de octubre de 2026. Cambios de frontend realizados mientras Claude ejecuta `ENCARGO_CLAUDE_TOPOLOGIA_FRONTERAS_Y_FUENTES.md`.

## Entregado

Al seleccionar una corriente material aparece una barra contextual con **Insertar sistema**, **Datos** y cerrar. El panel derecho no se abre automáticamente para esas corrientes. Para calor, trabajo e interfaces se conserva su consulta habitual; no se ofrece insertar un dominio material en ellas.

Insertar divide una conexión material en una cadena con un volumen nuevo y una corriente compartida. La alimentación, salida, volúmenes y fuentes existentes mantienen sus identificadores y datos. La conexión anterior conserva su identificador: si sale de un volumen, queda en el tramo posterior al nuevo volumen; si llega desde una alimentación o corriente, queda en el tramo anterior. El puerto que permanece sobre el elemento original se conserva; el nuevo volumen utiliza sus propios puertos.

No se copian propiedades, cierre, supuestos locales ni iniciales del antiguo volumen al nuevo. Las especies proceden del montaje existente. El usuario completa los nuevos datos mediante los controles actuales y vuelve a validar. Los resultados anteriores quedan como ejecución histórica y no se publican como validación vigente de la topología nueva.

Para una corriente compartida proyectada como una sola línea, la inserción actúa sobre su conexión física aguas abajo. La corriente original mantiene su identidad y sus datos; la nueva queda pendiente.

Conectar dos volúmenes añade una corriente compartida y **ya no borra las salidas del primero ni las entradas del segundo**, ni sus especificaciones. Si el dibujo resultante tiene ramas no admitidas, corresponde al backend rechazarlas. No se amplió la capacidad física.

La operación de inserción se aplica en un único evento de React y funciona con el historial actual de la mesa. Deshacer/rehacer se comprobó en el navegador, sin introducir otro historial.

Se corrigió también «Ordenar piezas»: la separación vertical considera la altura declarada del volumen o una separación suficiente para su tamaño habitual; dos volúmenes aislados grandes ya no usan filas fijas de 130 px.

## Alcance de esta primera interacción

- Se inserta desde el botón contextual, no mediante soltar una pieza sobre una línea.
- Se admiten conexiones materiales ordinarias entre frontera/corriente y volumen. Las interfaces térmicas y selectivas se excluyen.
- Sigue el límite actual del editor de ocho nodos internos: una inserción requiere espacio para dos nodos. No se amplió ese límite durante esta entrega.
- Las ramas existentes se conservan. La capacidad de resolverlas depende de la combinación publicada por el servicio.
- La intención de frontera de §27 está integrada en la entrega posterior: ver `INTEGRACION_ENTREGA_27.md`.
- La representación compacta de fuentes de calor sigue como siguiente trabajo de UI.
- El reposicionamiento abre espacio en la rama material aguas abajo; no es un algoritmo global de enrutamiento con evitación de todos los obstáculos.

## Verificación

Pasaron `npm test`, TypeScript (`npx tsc --noEmit`) y ESLint sobre los tres archivos de aplicación modificados/nuevos. La suite `verificar_insercion_mesa.mjs` está incluida en `npm test` y puede ejecutarse con `npm run test:insercion`.

La suite comprueba conservación de identificadores, datos de fronteras y fuentes, selección de variables, iniciales originales, puertos, ausencia de copias físicas al volumen nuevo, petición original intacta, corriente compartida proyectada, conexión no destructiva, rechazo de interfaces para inserción y ordenación con una altura declarada de 800 px.

Prueba real en navegador, en mesa independiente **UI · inserción conservando fronteras**:

1. Importar tanque material con alimentación 3 mol/s, salida 1 mol/s y cantidad inicial 100 mol.
2. Seleccionar su conexión de salida e insertar un volumen.
3. Deshacer una vez: vuelve el montaje inicial. Rehacer: aparecen el mismo volumen y corriente nuevos, con las fronteras originales.
4. Ir a Experimentar: el volumen nuevo tiene su relación de salida pendiente, cantidad inicial vacía y corriente compartida aún sin definir. Los datos originales siguen visibles.
5. Elegir balance general para el volumen nuevo, declarar 2 mol/s en la corriente compartida, 200 mol al inicio del nuevo tanque y duración 600 s.
6. El backend declara listo y resuelve. En la última muestra: primer tanque 700 mol, segundo 800 mol. Coincide con `n1=100+t`, `n2=200+t`.
7. Volver a Mis mesas y reabrir: se conserva la cadena y la ejecución de 600 s.

Esta es una ejecución del servicio desde la UI, además de las pruebas locales; no se ejecutó la batería completa del backend ni se reinició el servicio mientras Claude trabajaba.

Evidencias: `preview-insertar-corriente.jpg` y `preview-insercion-resuelta.jpg`. El archivo `qa-insercion-mesa.json` es el montaje inicial de esta prueba de UI, derivado de un ejemplo publicado; no pretende ser un ejemplo nuevo generado por el endpoint.

## Archivos

- `app/laboratorio/editarTopologiaMesa.ts`: operaciones puras de inserción, conexión y ordenación.
- `app/laboratorio/AccionesCorriente.tsx` y `accionesCorriente.css`: barra contextual.
- `app/laboratorio/ConstructorSistema.tsx`: integración de operaciones, selección y vigencia visual.
- `verificar_insercion_mesa.mjs` y `package.json`: regresión incorporada a la batería del frontend.

No se modificó backend ni `thermodynamics/proveedor.py`. Sin commit ni push.
