# Auditoría y consolidación del laboratorio

Fecha: 8 de octubre de 2026. Cambios locales, sin backend, commit ni despliegue.

## Resultado

Se revisaron los recorridos de fundamentos y reacciones, adaptación de petición/respuesta, recuperación de ensayos, cancelación, comparación y exportación. La suite existente también verifica historial del flowsheet, versiones, integridad, ecuaciones y formulaciones. No es una certificación científica del motor ni una auditoría exhaustiva de todas las operaciones.

## Hallazgos corregidos

| Prioridad | Problema | Corrección y evidencia |
|---|---|---|
| Alta | Importación avanzada solo comprobaba que existieran algunas listas; elementos null o vectores incompletos podían romper el render | Validación estructural antes de cambiar estado: IDs, vectores, inventarios, unidades que la UI muestra y campos del integrador. Prueba con JSON inválido en navegador: rechazo sin pérdida del sistema |
| Alta | Tiempo e integrador por defecto se mostraban pero podían faltar en la petición | Materializar exactamente los valores visibles cuando se construye la petición de lote; no modificar el borrador |
| Alta | Inventarios omitidos aparecían como cero sin quedar explícitos en la petición | Completar inventarios mostrados como cero por identidad de especie. No convertir cantidades en caudales |
| Alta | Respuestas parcialmente validadas podían romper tablas, series o propiedades | Guardas de contrato antes de mostrar resultados; rechazar series con longitudes incompatibles y propiedades mal formadas |
| Alta | Una pestaña podía sobrescribir un cuaderno cambiado desde otra | Comprobar el contenido leído antes de guardar; rechazar conflicto y exigir recargar el cuaderno. Prueba con almacenamiento simulado |
| Media | Ensayos duplicados, fechas inválidas y otro origen se aceptaban en el cuaderno | Validación común; preservar almacenamiento inválido sin sobrescribirlo |
| Media | Selector de base parecía modificar las leyes del lote | Texto y etiqueta distinguen base del equilibrio de las bases de cada ley cinética; no reinterpretar constantes |
| Media | Páginas del laboratorio anidaban main y repetían workspace | Un único main en layout, regiones identificadas en páginas. DOM comprobado: un main, ningún ID duplicado; enlace de salto enfoca workspace |
| Media | Descargas liberaban el Blob inmediatamente tras click | Utilidad compartida con enlace conectado al DOM y liberación diferida para cuaderno, informe e investigación actual |

## Verificación

- npm test: suite completa, más regresiones de auditoría/importación, respuestas, defaults y conflictos entre pestañas.
- TypeScript y compilación de producción; lint.
- Navegador: importación inválida rechazada; sistema permanece disponible.
- Vista de 390 × 844: editor de balance sin desbordamiento horizontal del main, controles con nombre; cero errores LaTeX en el recorrido inspeccionado.
- Navegación por teclado: enlace de salto enfoca el main.
- Viewport temporal restaurado al finalizar.

## Límites y trabajo pendiente

- No se añadieron solvers, propiedades, transporte, exergía ni operaciones nuevas. La física y sus dominios siguen siendo responsabilidad del backend.
- No se afirma cumplimiento completo de WCAG; queda una revisión con lector de pantalla y contraste exhaustivo. El flowsheet completo no se ensayó en móvil durante esta entrega.
- El catálogo HTTP ofrece búsqueda por consulta; no se inventa autocompletado parcial ni traducción de nombres. Los nombres del proveedor pueden estar en inglés.
- Importaciones con otras unidades se rechazan explícitamente en esta UI, en lugar de mostrarlas como mol/K/s. Una futura conversión debe quedar trazada.
- Cuaderno limitado a 12 ensayos: se bloquea guardar y se avisa. Se eliminó el desplazamiento automático del ensayo más antiguo; ninguno se borra por guardar. Queda diseñar gestión explícita de archivos/exportaciones.
- Referencia de comparación: sesión actual; guardar la investigación conserva parámetros y ejecución, pero no restaura automáticamente esa referencia.
- Informe HTML incluye resumen y datos originales; descarga visual extremo a extremo pendiente en un navegador convencional. El navegador integrado no confirmó el evento de descarga en la revisión anterior.
- Falta traza tipada de ecuaciones generadas por los servicios de lote/equilibrio para sustituir explicaciones generales. No se simula esa traza en frontend.

La próxima ampliación de física debe seguir CONSOLIDACION_FUNDAMENTOS_CLAUDE.md y no duplicar modelos en el navegador.
