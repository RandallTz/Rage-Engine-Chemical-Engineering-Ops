# Seguimiento de §25

Las quince sondas de auditoría se ejecutaron sobre las fuentes corregidas y cumplen; salida 0. Evidencia nueva: `docs/auditoria_motor_2026_10_11/correcciones_25/evidencias.json`. Se conserva la evidencia original de los fallos. Las 38 suites completas son el resultado informado por Claude; Codex no ha repetido esa batería completa en esta integración.

También se ejecutó la suite de correcciones de auditoría: 69 comprobaciones aprobadas. `npm test`, TypeScript, ESLint de los componentes cambiados y la prueba de UI pasan.

Se recargó el servicio local para cargar la corrección. El frontend incorpora `balances[].supuestos_efectivos` y muestra la adiabaticidad efectiva; false local no revoca true global. La formulación orientativa también respeta la regla contractual OR.

La vista de ecuaciones puede activar «Ver unidades», tomadas del catálogo/modelo vigente. No calcula dimensiones ni certifica compatibilidad leyendo LaTeX. El análisis por término sigue pendiente de contrato.

Dato/Calcular sigue disponible en el balance general. Para montajes materiales elegibles se añadió acceso visible «Elegir datos e incógnitas», con revisión explícita antes de sustituir relaciones. No se cambia la física automáticamente ni se habilita inversión arbitraria en otras combinaciones.

El usuario probará el laboratorio actual. `SIGUIENTE_CLAUDE_BASES_DIMENSIONES.md` prepara la ampliación de base másica, análisis dimensional y selección flexible; no se ha enviado a otro chat ni se presenta como implementada.
# Seguimiento UI: introducir datos

El formulario conserva el recuento y las referencias del servidor. La acción principal lleva al campo pendiente, abre las alternativas cuando el servidor exige elegir un dato, o permite definir la salida cuando falta esa relación. Al quedar listo, la acción pasa a Resolver. Los campos vacíos muestran «Por llenar» y mantienen su unidad junto al valor. No se añaden valores por omisión ni se cambia la selección Dato/Calcular al navegar.

Verificado en la mesa de agua del navegador: Completar dato selecciona Entrada exterior y enfoca su caudal, sin introducir valores. La prueba `verificar_experimentar_ui.mjs` cubre la elección entre tres caudales, una condición inicial pendiente y la acción final Resolver. Este ajuste no requiere cambios del backend.

