# Resolver tras editar un montaje

Se reprodujo el fallo en una mesa de dos tanques. Una conexión creada por React Flow concatenaba los identificadores de los bloques y los puertos móviles; excedía los 120 caracteres aceptados por el servidor y producía un 422. El formulario lo presentaba como falta de conexión y dejaba de mostrar el catálogo.

Las conexiones nuevas reciben UUID propios. Las conexiones antiguas demasiado largas se reasignan una sola vez en el editor, conservando extremos, puertos y referencias de interfaces. La ejecución histórica se conserva intacta.

Al construir la petición se retiran las especificaciones, selecciones, iniciales, perturbaciones, reacciones y relaciones de almacenamiento que pertenecían a piezas eliminadas. Las referencias desconocidas introducidas manualmente siguen llegando al servidor para su diagnóstico. La ejecución anterior permite identificar los datos huérfanos en mesas guardadas antes de esta corrección.

Los cambios de la petición cancelan un cálculo en curso y vuelven a la vista de valores. Un volumen nuevo conserva sus datos sin declarar: en un montaje de balance general aparece la acción explícita para definir sus caudales. No se asignan caudales ni cantidades iniciales por omisión.

Verificación: `node verificar_edicion_mesa.mjs --api` ejecutó resolver → retirar volumen → resolver → añadir volumen con un puerto móvil → validar pendientes → completar datos → resolver. Las cantidades finales coinciden con las referencias analíticas. En el navegador, la mesa original recuperó su catálogo y su recuento, manteniendo 50 mol/s de entrada, 500 mol iniciales y 45 s de duración. Los valores del tanque añadido permanecieron pendientes.

No requiere una entrega nueva del backend.
