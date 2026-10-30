# Seguimiento de la entrega §24

Entrega backend recibida: hitos A–D, revisiones 10–13. Referencia: `docs/ENTREGA_LABORATORIO_CODEX.md`, §24. La integración de los controles de tanque térmico, circuitos independientes, pared y cámara de vapor en el editor sigue pendiente. No se presentan como funciones ya disponibles en el frontend.

Actualización del recorrido de Experimentar: se integraron los campos energéticos y la presión del balance general, y un ejemplo editable de dos circuitos separados unidos térmicamente. Ver `RECORRIDO_EXPERIMENTAR_2026_10_11.md`. Esto es una integración parcial: el editor completo de pared, cámara y geometría/capacidad del tanque sigue pendiente. Los fallos físicos de la auditoría conservan su entrega de correcciones independiente.

## Ajuste visual realizado

Las conexiones del editor y del montaje de resultados utilizan trazado ortogonal con codos de 90° y una separación inicial de 32 px respecto del puerto. La previsualización durante una conexión también es ortogonal. Se conservan los extremos, puertos, identificadores y datos de las conexiones; no cambia el modelo matemático ni se invalida un resultado por este ajuste de presentación.

TypeScript y ESLint de los dos componentes modificados pasan.

## Incidencia del catálogo resuelta (§24.6)

El backend corrigió la magnitud de `tk.area` a `area` y regeneró los ejemplos. `npm test` vuelve a pasar, incluidos los 100 ejemplos con recuento verificados por el lector del frontend.

La incidencia anterior era `magnitud: null` para esa variable de unidad `m2`. No se debilitó el lector ni se excluyó el ejemplo de la prueba. No cambia la revisión 13 ni los resultados físicos.

## Organización de supuestos

La vista de ecuaciones y la configuración avanzada del diagrama comparten un editor por familia:

- Materia: ausencia de reacción.
- Energía: adiabaticidad exterior, ausencia de trabajo de eje y energías cinética/potencial despreciables.
- Momento: sin simplificaciones configurables en el contrato actual; no se simula una resolución disponible.

Temporal/estacionario aparece como elección común del estudio, separada de las simplificaciones. Quitar simplificaciones conserva esa elección. La lectura detallada de cada volumen repite las familias y distingue el ajuste térmico local de los valores del montaje. Se mantienen los bloqueos por fuentes o especificaciones incompatibles, y no se añaden supuestos al contrato ni solvers en JavaScript.

TypeScript, ESLint y `npm test` pasan. La agrupación se comprobó en el navegador sin modificar los valores del montaje abierto.

## Verificación visual

El laboratorio vuelve a estar disponible en el navegador. Se verificó el trazado ortogonal del editor con corrientes exteriores y compartidas. Se comprobó también la agrupación de supuestos y su resumen por volumen. Capturas: `frontend/preview-conexiones-ortogonales.png` y `frontend/preview-supuestos-por-balance.png`.

## Límites que debe conservar la integración

- La pared y la cámara de vapor todavía no admiten transferencia de estacionario a temporal.
- La cámara representa vapor saturado cuasiestacionario con purgador; no un volumen bifásico transitorio.
- Las combinaciones disponibles se leen de las capacidades del backend.
- Nivel, trabajo de frontera, temperatura de la pared y condensación se leen de los resultados del motor; no se calculan en el frontend.
