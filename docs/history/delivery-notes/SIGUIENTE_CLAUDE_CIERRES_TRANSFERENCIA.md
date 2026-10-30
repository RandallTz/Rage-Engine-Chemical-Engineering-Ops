# Estado vigente — revisión 4

Interfaz térmica, auditoría por combinación, procedencia por término y corrección de verificaciones globales entregadas en §16. El contenido anterior se conserva como registro de etapas; sus pendientes sobre estos puntos ya están resueltos. Estado actual: ENTREGA_FRONTEND_INTERFAZ_TERMICA.md. Próxima entrega: ENTREGA_CLAUDE_TRAZABILIDAD_REUTILIZACION.md.

# Siguiente etapa: cierres y transferencia entre volúmenes

## Contexto para un chat nuevo
Proyecto: simulador de fundamentos de ingeniería química. El laboratorio construye modelos concentrados reutilizables; no pretende CFD ni operaciones completas todavía. Frontend en frontend/, backend separado. Trabaja solo en backend; no publiques ni incluyas cambios ajenos. Inspecciona Git antes de editar. Este documento NO interrumpe ni sustituye la entrega B reactiva en curso.

## Puerta de entrada
B ya fue entregada: ver §15. Integración y verificación de Codex en curso. Después de cerrar su aceptación, continuar esta etapa. Referencia B: ENTREGA_ENERGIA_REACTIVA_CLAUDE.md y actualizar docs/ENTREGA_LABORATORIO_CODEX.md. Codex integra y verifica ese contrato. No iniciar esta ampliación mezclándola con B sin cerrar su aceptación. Entrega A material/energética ya está integrada. La revisión del frontend no certifica cierre matemático.

## Lectura mínima
- docs/ENTREGA_LABORATORIO_CODEX.md §§13–14 y la nueva sección de B cuando exista.
- backend/schemas_estudios.py, backend/nucleo_estudios.py, core/dinamica.py, core/fluidos.py y el módulo reactivo vigente.
- tests/validar_estudios.py y tests/validar_estudios_energia.py.
- frontend/INTEGRACION_ESTUDIOS_ACOPLADOS.md para estado de integración; no necesitas historial de chat.

## Auditoría antes de ampliar
Documentar, por combinación real de física, estudio y cierre: estados diferenciales, variables algebraicas, especificaciones admitidas, restricciones, condiciones iniciales necesarias, dominio, método y eventos. No anunciar soporte general de DAE o reacción solo porque existan capacidades individuales.

Mantener cierres explícitos; ausencia no significa cero o un valor supuesto. Separar datos dados, calculados y verificaciones redundantes. Reportar omisiones, contradicciones y limitaciones con IDs de piezas/conexiones/variables. Si se informa un recuento de ecuaciones e incógnitas, explicar si hay comprobación estructural de rango y cuál es su alcance; un recuento no prueba solvencia. No prometer un analizador simbólico universal.

Condiciones iniciales: validar restricciones antes de integrar y declarar correcciones/proyecciones si alguna se implementa; nunca corregir silenciosamente. Transferencia estacionario→temporal es tarea separada: usar n/U resueltos, no F/h, con trazabilidad y verificación de consistencia.

## Primer incremento físico: interfaz térmica
Dos volúmenes rígidos perfectamente mezclados, líquido monofásico, sin reacción para aceptación inicial. Agregar una conexión térmica entre ambos, distinta de la corriente material y de una fuente impuesta. Mantener los dos estados en un sistema simultáneo. Usar una conductancia explícita G [W/K] con Q_12=G(T_1-T_2). Contribuir -Q_12 a U_1 y +Q_12 a U_2, con orientación y signo declarados. No crear inventario ficticio en la conexión ni derivadas duplicadas. Si hay pared con almacenamiento independiente, dejarla fuera del primer incremento; una conductancia concentrada no resuelve el campo térmico de la pared.

Modelo, geometría rígida, propiedades, referencia y dominio continúan explícitos. No extrapolar ni atravesar fase. Compatibilidad con T impuesta, fuentes externas y adiabático debe declararse: adiabático externo no puede interpretarse silenciosamente como prohibición o permiso de intercambio interno. Proponer la semántica exacta y migración antes de cambiar el supuesto existente.

Respuesta: capacidades por combinación, variables compartidas, ecuaciones y origen de términos, Q_12 con unidad/signo, dominios/tolerancias/método realmente utilizados, conservación global y por volumen, eventos, resultado parcial y versión del modelo. LaTeX se genera; no se interpreta como modelo.

## Aceptación independiente
1. Dos volúmenes cerrados, capacidades térmicas constantes explícitas: diferencia de T decae con tiempo característico 1/[G(1/C1+1/C2)]; temperatura límite (C1*T10+C2*T20)/(C1+C2). Ambas referencias se escriben fuera del motor.
2. G=0: sin intercambio; temperaturas constantes en sistema aislado. T iguales: Q_12=0. Invertir orientación conserva resultados físicos y cambia signo declarado.
3. Energía global conservada e intercambio interno cancelado; comprobar precisión contra analítica además de conservación.
4. Capacidades diferentes y conductancia alta: contraste con métodos adecuados a rigidez y tolerancias declaradas.
5. Corriente material más interfaz térmica: referencia independiente; no sumar dos veces h ni Q.
6. Iniciales incompatibles, G ausente/negativa/no finita, unidades inválidas, referencias a piezas ausentes, dominios/fase: rechazos o eventos con IDs.
7. Mantener todas las suites previas y generar ejemplos petición/respuesta desde endpoints, incluidos rechazos.

## Después, en entregas separadas
- Transferencia de materia entre volúmenes: especies, base, fuerza impulsora, área, coeficientes y relación de equilibrio compatibles; flujo opuesto y conservación elemental/masa. No identificar difusión molecular con cualquier transporte entre bloques.
- Momento concentrado: presión–caudal, pérdidas, geometría y cierres; presión calculada exige grados de libertad y condiciones de contorno. Sin CFD.
- Frontera móvil: trabajo P dV, almacenamiento y presión compatibles.
- Cambio de fase: inventarios por fase y cierre termodinámico; el evento de burbuja actual no basta para continuar una trayectoria bifásica.
- Control y perturbaciones: sensores, acciones y eventos definidos; no esconder discontinuidades en interpolación.

## Entrega a Codex
Actualizar contrato exacto, ejemplos, capacidades combinadas, migración, códigos, límites y pruebas. No pedir al frontend que haga balances, propiedades, integración, análisis de rango o solución local. No implementar las cinco áreas futuras de una vez: primer hito verificable es interfaz térmica.

## Seguimiento: bases de consulta añadidas

Estado: PENDIENTE DE ENTREGA A CLAUDE; B entregada, verificar integración antes de iniciar esta etapa. Frontend incorpora seis bases (volumen/almacenamiento, conservación, propiedades/referencias, cierres/leyes constitutivas, especificaciones/iniciales, acoplamiento/régimen) en biblioteca y preparación. Son contenido explicativo, no formulación ejecutable adicional. La aceptación futura debe vincular cada término y cierre con variables y ecuaciones reales del motor; conservar límites y procedencia por combinación. Fourier, Fick y la interfaz GΔT se consultan pero NO se ejecutan todavía en estudios.


## Procedencia requerida tras la integración de B

La respuesta actual permite mapear clases de variables, valor, determinada_por, conexiones, ecuaciones generales/activas, descartes y origen por piezas. Falta procedencia estructurada por término individual (rol entrada/salida/fuente/cierre, variable, signo y conexión). No inferirla del LaTeX. Añadirla de forma aditiva al ampliar interfaces; probar cancelación de contribuciones internas y que verificaciones no cuentan como ecuaciones independientes. Mantener el recuento y su alcance explícitos.

## Hallazgo de revisión de B

Ejemplo estudio-reaccion-adiabatica: en global:energia, latex_general incluye -ΣξΔH pero latex_activo observado muestra solo transporte de entalpía, con U sensible. Revisar coherencia de la ecuación renderizada con el residuo realmente evaluado y con la referencia (sensible o con formación). No corregir en frontend ni inferir términos analizando LaTeX. La conservación numérica reportada cumple; el hallazgo afecta trazabilidad de la formulación. Añadir comprobación de correspondencia ecuación activa/referencia para montajes reactivos.
