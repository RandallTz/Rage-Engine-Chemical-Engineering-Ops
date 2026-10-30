# Prioridad vigente después de §19

Transferencia material isotérmica entregada e integrada. Siguiente documento: SIGUIENTE_CLAUDE_TRANSFERENCIA_MATERIA_ENERGIA.md. Documentar primero cierre y energía transportada coherentes; entregar A y B por separado. Las prioridades antiguas que aparecen debajo quedan como historial.

# Prioridad vigente después de §18

Reacción + interfaz térmica entregada e integrada. El siguiente documento es SIGUIENTE_CLAUDE_TRANSFERENCIA_MATERIA.md: alcance físico inicial, cierre a V fijo, ley de reparto, ensamblaje y referencias de aceptación. Los hitos de transferencia y firma anteriores quedan entregados; las instrucciones históricas debajo no son tareas pendientes.

# Estado vigente tras §17

El hito de transferencia y la corrección de firma (§17.11) están entregados y verificados desde JavaScript contra el servicio local. INCIDENCIA_TRANSFERENCIA_JSON_CLAUDE.md queda cerrada como registro histórico. No repetir transferencia ni canonicalización. Los estados anteriores deben regenerarse. La cola física sigue pendiente y requiere su propio contrato y validación antes de habilitar capacidades.

# Entrega actualizada — contrato 4 y siguiente hito

## Contexto para un chat nuevo
Simulador de fundamentos de ingeniería química, modelos concentrados. Codex trabaja en frontend; Claude solo backend. No CFD, operaciones completas, commit de cambios ajenos ni publicación. Inspecciona Git: las entregas anteriores siguen sin commit; thermodynamics/proveedor.py es un cambio ajeno.

## Ya entregado: no repetir
Leer docs/ENTREGA_LABORATORIO_CODEX.md §§13–16. Materia, energía, reacción, cinética reutilizada e interfaz térmica sin reacción están disponibles. §16 cerró auditoría por combinación, términos estructurados, cancelaciones y residuo_terminos. La representación global omitía fuentes químicas/molares; ya se corrigió ensamblando términos reales. Adiabático significa sin calor exterior. Dos cerrados se integran conjuntamente; su estacionario se declara indeterminado. Reacción + interfaz permanece rechazada. revision_contrato = 4.

## Integración de Codex
El frontend conserva tipo termica y conductancia en solicitudes, mesa y ensayos. Editor en Propiedades para añadir/retirar interfaces y declarar G con unidad, sin interpretar una omisión como cero. Muestras de Q por conexión, LaTeX recibido, aportaciones por signo/origen, cancelaciones globales y residuo mostrado. Las capacidades combinadas se consultan por fila; resolver requiere validación vigente. Ningún balance, propiedad, integrador o análisis de estabilidad nuevo se ejecuta en el cliente.

## Siguiente hito recomendado: estacionario como condición inicial
Implementar únicamente la transferencia explícita de una solución estacionaria válida al mismo modelo temporal. Revisar primero si existe un contrato parcial. Proponer y documentar la ruta/esquema concreto antes de que Codex lo consuma; no asumir nombres de endpoints desde este documento.

Usar inventarios n_i y energía U calculados, no caudales F ni entalpías de corriente h. Elegir explícitamente una rama si el estacionario tiene varias soluciones. Registrar modelo de origen, estudio, ejecución, rama, referencia energética y transformaciones de unidades. Rechazar resultados obsoletos, especies/modelo/cierre incompatibles y estacionarios indeterminados. Verificar las restricciones del modelo destino antes de integrar; no proyectar ni corregir silenciosamente. Una perturbación posterior cambia las entradas del estudio, no la identidad del estado físico de origen. Distinguir estado inicial tomado del estacionario y escenario perturbado.

### Aceptación independiente
- Sin perturbación, trayectoria permanece en el estacionario con tolerancias declaradas; medir residuos y restricciones además del desplazamiento.
- Escalón material/térmico: respuesta contrastada con referencia analítica o formulación independiente.
- Energía y reacción: iniciales/referencia compatibles y ningún doble conteo químico.
- Múltiples ramas: selección obligatoria, estabilidad local declarada; ninguna selección silenciosa.
- Dos volúmenes cerrados: rechazo de transferencia desde un estacionario indeterminado.
- Cambios de sustancias, cierre, referencia, dominio o modelo invalidan la transferencia con diagnóstico e IDs.
- Capacidades siguen en false hasta estar implementado y verificado. Actualizar combinaciones, códigos, límites, migración y ejemplos generados desde endpoints. Mantener suites previas.

## Cola separada: no implementar todo de una vez
1. Verificar y habilitar reacción + interfaz térmica sobre el mismo sistema, con conservación y referencia independiente; hasta entonces mantener rechazo.
2. Transferencia de materia concentrada: cerrar primero especies, fuerza impulsora, área, coeficiente y equilibrio; no un solver espacial.
3. Momento concentrado, frontera móvil, cambio de fase y control: contratos independientes posteriores.

## Devolución a Codex
Actualizar docs/ENTREGA_LABORATORIO_CODEX.md con esquema exacto y ejemplos. Indicar puntos no realizados. No pedir al frontend convertir estados físicos ni resolver restricciones. No tocar frontend ni enviar mensajes/publicar por cuenta de Codex.
