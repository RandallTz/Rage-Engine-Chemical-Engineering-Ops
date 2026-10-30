# Integración de interfaz térmica — revisión 4

Solo frontend. Sin commit, push ni despliegue; el backend se reinició para cargar los archivos de Claude, sin editarlo.

## Disponible para probar
Laboratorio → Construir un sistema → ejemplo «Interfaz termica entre dos volumenes cerrados» → Cargar → Validar → Resolver.
Propiedades → Intercambio térmico entre volúmenes permite declarar G, añadir o retirar una interfaz. Cero y ausencia son diferentes. La conexión aparece punteada y se conserva al guardar/importar. Datos térmicos externos siguen separados; adiabático exterior permite interfaz interna.
Ecuaciones → Aportaciones al balance muestra signo, LaTeX, variables, pieza/conexión, cancelaciones y residuo evaluado por el motor. Las verificaciones globales no se cuentan como ecuaciones independientes. Resultados permite consultar Q por conexión en muestras reales.

## Límites actuales
Reacción + interfaz no soportada. Dos volúmenes cerrados no tienen estacionario único. Transferencia estacionario → inicial todavía bloqueada. No se añaden solvers frontend.

## Entrega backend siguiente
Leer ENTREGA_CLAUDE_TRAZABILIDAD_REUTILIZACION.md: estado actualizado y hito de transferencia explícita, con aceptación y cola separada.

## Verificación
npm test (incluye los cinco contratos de interfaz), TypeScript, ESLint y build satisfactorios. En navegador: ejemplo cerrado validado/resuelto por el servicio revisión 4; procedencia orientada y cancelación global visibles. Cambiar G bloquea Resolver hasta revalidar, y G = 0 valida como dato explícito.
