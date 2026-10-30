# Recorrido de Experimentar — 11 de octubre de 2026

## Cambios de interfaz

- Las corrientes calculadas también se pueden seleccionar en Experimentar. Sus variables permanecen en el elemento correspondiente, agrupadas por balance, con la unidad y la marca «Se calcula». Se elimina la pantalla separada de variables calculadas.
- El indicador conserva exclusivamente el recuento del servidor. Al pulsar Falta, aparece una lista a petición del usuario, con las variables y alternativas del contrato. «Alguna» se presenta como elección, sin exigir todos los candidatos. Elegir un pendiente enfoca su campo; los conflictos conservan el acceso directo.
- Un balance general con energía muestra también temperaturas iniciales/de entrada, calor, presión, propiedades e intercambios. Estos campos se enviaban en la petición, pero la vista exclusiva de materia impedía editarlos. La presión ausente permanece como campo sin definir en el tanque térmico; no se fabrica un valor.
- Una resolución fallida abre su diagnóstico. Un resultado parcial muestra el evento, instante, descripción y elemento afectado. Las muestras se leen tal cual del backend, sin extrapolación. Al modificar los datos, la validación nueva no se presenta como resultado calculado.
- Se añade «Calentar con otro circuito»: dos cadenas materiales independientes, unidas por una interfaz térmica. Los parámetros son explícitos y editables; el ejemplo solo se ofrece cuando el servidor anuncia esa combinación. No representa una pared sólida ni vapor.

## Verificación

- `npm test`, TypeScript y ESLint de los componentes modificados.
- `npm run test:experimentar-ui`: renderizado de variables por pieza, elección de uno entre tres datos, lectura de estados completo/parcial/fallido y evento sin muestras, campos energéticos y separación de circuitos.
- `npm run test:escenarios-tanque`, contra el servicio: cinco escenarios con referencias analíticas y el de dos circuitos contra el ejemplo publicado en §24. También comprueba la cancelación de la interfaz y la localización de una propiedad ausente.
- Navegador: retirar el caudal de una mesa de prueba actualiza Falta; la lista abre y enfoca ese campo. Se restauró el valor original. Se comprobó un vaciado con terminación a 100 s y sus gráficas, sin modificar el resultado guardado.

## Límites y coordinación

No se modifica el código del backend ni se certifican como corregidas las incidencias de `docs/AUDITORIA_MOTOR_2026_10_11.md`. La entrega vigente para Claude sigue siendo `CORRECCIONES_AUDITORIA_MOTOR_CLAUDE.md`.

Dato/Calcular permanece restringido a la elegibilidad del catálogo en las combinaciones que admiten esa elección. El frontend no calcula GL ni convierte un campo ausente en cero. «Listo» describe completitud, no garantiza convergencia ni exactitud física.

La edición completa de pared, cámara de vapor y todas las relaciones de §24 sigue pendiente. Estos cambios no habilitan grafos arbitrarios, inversión temporal, momento ni un solver DAE nuevo.
