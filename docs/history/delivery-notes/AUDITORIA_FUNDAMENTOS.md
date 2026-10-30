# Estado vigente — revisión 4

Interfaz térmica, auditoría por combinación, procedencia por término y corrección de verificaciones globales entregadas en §16. El contenido anterior se conserva como registro de etapas; sus pendientes sobre estos puntos ya están resueltos. Estado actual: ENTREGA_FRONTEND_INTERFAZ_TERMICA.md. Próxima entrega: ENTREGA_CLAUDE_TRAZABILIDAD_REUTILIZACION.md.

# Auditoría de fundamentos y entrega B

## Alcance verificado
Biblioteca existente y seis bases del modelo: comprobación automatizada de IDs únicos, dependencias existentes, unidades y límites presentes, y renderizado LaTeX estricto. Esto verifica integridad editorial y representación, no demuestra corrección física universal ni precisión del solver.

## Correcciones de contenido
- Referencia de propiedades distingue cp constante declarado en ideal_incompresible de cp(T) del proveedor.
- La marcha triangular describe el ensayo térmico estacionario sin reacción; los estudios acoplados usan su método declarado, no se etiquetan como brentq por analogía.
- Capacidades de energía y cinética incorporan estudios reactivos de §15, distinguiéndolos del contrato de lote.
- Preparación no exige T/U inicial adicional cuando T del volumen está impuesta; el motor verifica los datos iniciales que sí se declaren.
- Referencia energética sensible de B: fuente química explícita con ΔH de referencia, sin añadir Kirchhoff desde UI; conservación con formación disponible como evidencia del motor.

## Límites del análisis
No se afirma soporte universal de DAE ni independencia de ecuaciones por contar incógnitas. Las capacidades se interpretan por ruta y montaje validado. Las leyes de Fourier/Fick siguen explicativas. El mapa conserva origen por piezas y conexiones; atribución por término requiere contrato aditivo del backend y no se infiere de cadenas LaTeX.

## Siguiente etapa pendiente
B entregada e integrada; verificar aceptación de usuario antes de pasar SIGUIENTE_CLAUDE_CIERRES_TRANSFERENCIA.md. No iniciar momento, fase ni transferencia como solvers locales. La próxima ampliación propuesta es interfaz térmica concentrada, con referencia analítica independiente.

## Hallazgo de revisión de B

Ejemplo estudio-reaccion-adiabatica: en global:energia, latex_general incluye -ΣξΔH pero latex_activo observado muestra solo transporte de entalpía, con U sensible. Revisar coherencia de la ecuación renderizada con el residuo realmente evaluado y con la referencia (sensible o con formación). No corregir en frontend ni inferir términos analizando LaTeX. La conservación numérica reportada cumple; el hallazgo afecta trazabilidad de la formulación. Añadir comprobación de correspondencia ecuación activa/referencia para montajes reactivos.
