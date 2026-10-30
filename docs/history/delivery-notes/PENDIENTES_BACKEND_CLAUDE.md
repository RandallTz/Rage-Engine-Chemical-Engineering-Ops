# Siguiente entrega de backend — después de dc6ede0

## Encargo único vigente para Claude

El usuario pidió consolidar el trabajo pendiente en una sola entrega. Usar exclusivamente [CONTRATO_CLAUDE_ENSAMBLAJE_DINAMICO_MOTOR.md](CONTRATO_CLAUDE_ENSAMBLAJE_DINAMICO_MOTOR.md) como encargo actual: E0–E3 forman fases internas del mismo trabajo de ensamblaje y resolución dinámica de un volumen con materia/energía y agua real. Entregar conjuntamente contrato/API, validación/recuento/inicialización, trayectorias, fases/eventos, pruebas, ejemplos y documentación. H0/H1/H3 ya están entregados. Esta indicación sustituye las prioridades históricas de E0 solo que se conservan abajo.

## Motor independiente · 14 de octubre de 2026

Encargo nuevo autorizado: [CONTRATO_CLAUDE_TERMODINAMICA_MOTOR.md](CONTRATO_CLAUDE_TERMODINAMICA_MOTOR.md), que desarrolla [PLAN_TERMODINAMICA_MOTOR.md](PLAN_TERMODINAMICA_MOTOR.md). Claude mantiene la responsabilidad del backend. Primeros hitos: auditoría/contrato y evaluación de estado puro monofásico; después inversión, equilibrio de fases, dinámica y mezclas con sus pruebas. No confundir con una ampliación del laboratorio ni con la cámara de vapor acotada ya entregada allí.

Codex implementó contratos TypeScript, reconstrucción material/energética de respuestas, vigencia por propietario y vista de Estado, con evaluación puntual separada del solver manual. La entrega física del proveedor, las nuevas rutas y el acoplamiento dinámico están pendientes de Claude. Las pruebas frontend utilizan datos sintéticos para validar el protocolo, no certifican propiedades o estabilidad física. El documento queda preparado para entregárselo; no se ha enviado a otro chat.

## Estado actual · 11 de octubre de 2026

**Actualización tras §25:** Claude entregó A1–A9, procedencia y supuestos efectivos. Las quince sondas verificadas por Codex cumplen; la entrega de correcciones deja de estar pendiente. Ver `INTEGRACION_ENTREGA_25.md`. La ampliación propuesta siguiente es `SIGUIENTE_CLAUDE_BASES_DIMENSIONES.md` (base másica, ecuaciones parciales/análisis dimensional y selección flexible por capacidades). El usuario probará primero el sistema actual. No se ha enviado el documento a otro chat.

**Actualización tras §24.6 / revisión 13:** los cuatro hitos de tanques, circuitos térmicos, pared y cámara de vapor están entregados en backend, incluida la corrección del catálogo de área. El texto histórico que los llama próxima prioridad queda sustituido por este estado; no repetirlos.

**Auditoría nueva:** `docs/AUDITORIA_MOTOR_2026_10_11.md` registra nueve incidencias reproducidas pese a 37/37 suites en verde. La siguiente entrega preparada es [CORRECCIONES_AUDITORIA_MOTOR_CLAUDE.md](CORRECCIONES_AUDITORIA_MOTOR_CLAUDE.md): corrección del estacionario acoplado, escalado de especificaciones, bases cinéticas, dominio inicial y conexiones. Es la prioridad recomendada antes de ampliar física. Las reproducciones están en `tests/auditoria_motor_acoplado.py` y `docs/auditoria_motor_2026_10_11/evidencias.json`. No se ha enviado este documento a otro chat ni se han corregido aún esos fallos.

La integración completa del editor con §24 sigue pendiente; `INTEGRACION_ENTREGA_24.md` distingue lo recibido del backend de lo visible en frontend. La cola histórica siguiente se conserva como contexto, no como lista de funciones ya habilitadas.

Estado histórico tras §23 / revisión 9: recuento canónico entregado e integrado en frontend. `ESTADO_MODELO_EXPERIMENTAR.md` queda como contrato histórico cumplido; no repetir ese encargo. Ver `INTEGRACION_ENTREGA_23.md` para la lectura del indicador, referencias y comprobaciones. La corrección de opcionales `null` (§22.7) y los hitos de §22 también están entregados. Las ampliaciones físicas históricas siguientes siguen en cola; requieren priorización y contratos separados, y no se activan con esta integración.

**Seguimiento de §23 cumplido:** §23.7 entrega ids, rutas y bloques para propiedades faltantes e inválidas. Integrado y comprobado en servicio y navegador: Falta abre y enfoca Cp. No repetir este encargo. Ver `INTEGRACION_ENTREGA_23.md`.

**Prioridad histórica ya entregada:** [SIGUIENTE_CLAUDE_TANQUES_CIRCUITOS_TERMICOS.md](SIGUIENTE_CLAUDE_TANQUES_CIRCUITOS_TERMICOS.md). Los hitos A (cantidad variable + energía), B (circuitos materiales independientes unidos térmicamente), C (pared sólida explícita) y D (régimen acotado de condensación) están entregados en §24. Sus límites siguen vigentes; no equivalen a una ampliación multifísica genérica. La prioridad actual recomendada es corregir las incidencias de la auditoría enlazada arriba.


Los dos hitos de `ENTREGA_CLAUDE_ESPECIFICACIONES_UNIDADES.md` están entregados en §22/revisión 8 e integrados en frontend: catálogo de estudios, cantidades normalizadas y balance general con selección Dato/Calcular. Ver `INTEGRACION_ENTREGA_22.md` para experiencia, límites y comprobaciones. No repetir estas tareas. Las listas siguientes conservan contexto histórico; las ampliaciones de física requieren contratos separados.

Actualización dc6ede0: los puntos 1–5 ya están entregados dentro del dominio declarado: lote isotérmico, equilibrio calculado, balanceo racional y propiedades Hess/Kirchhoff. La lista numerada conserva la solicitud histórica; no pedirla otra vez. Prioridad pendiente: áreas 6–10, lote adiabático y transversales. Gibbs y potenciales químicos ya existen para equilibrio; el punto 6 pide ampliar su uso a balances de entropía y exergía.

## Seguimiento anterior: priorización de E0 (sustituida por la entrega única)

H3 recibido e integrado el 14 de octubre de 2026: TP/PH/UP/UV, equilibrio estático de agua, bases de fase y límites. El frontend comprobó ejemplos reales, reconstrucción UV y una consulta bifásica en el navegador. No se solicita repetir H3.

**Siguiente encargo para Claude:** revisar y concretar E0 de [CONTRATO_CLAUDE_ENSAMBLAJE_DINAMICO_MOTOR.md](CONTRATO_CLAUDE_ENSAMBLAJE_DINAMICO_MOTOR.md). Acordar las rutas y el esquema, ensamblar ecuaciones/catálogo/recuento e inicializar sin integración temporal. Después E1/E2 (H2) y E3 (H4). El cliente tiene tipos y adaptador preparados, pero no activa ningún solver real ni sustituye el modelo manual.

### Seguimiento anterior de H3

14 de octubre de 2026. H0/H1 de agua TP recibidos; integración real y contraste de masa molar implementados en frontend. El siguiente encargo está en [CONTRATO_CLAUDE_TERMODINAMICA_H3.md](CONTRATO_CLAUDE_TERMODINAMICA_H3.md): saturación e inversiones PH/UP/UV, sin dinámica ni cambios al laboratorio. H2/H4 requieren primero acordar `validar`/`resolver` del ensamblaje independiente. Los apartados históricos del laboratorio que siguen no sustituyen esta prioridad.

Ya está preparado el siguiente documento para revisar tras H3: [CONTRATO_CLAUDE_ENSAMBLAJE_DINAMICO_MOTOR.md](CONTRATO_CLAUDE_ENSAMBLAJE_DINAMICO_MOTOR.md). E0 confirma esquema/ensamblaje/validación; después E1/E2 añaden dinámica monofásica rígida o a presión prescrita, y E3 cambio de fase. Los tipos/adaptador frontend son preparación; aún no se publican endpoints dinámicos.

## Ya entregado (no repetir)
Balances estacionarios por especie, estequiometría arbitraria de tasa especificada, 2–8 componentes, hasta dos volúmenes, fuentes brutas y netas diferenciadas, conservación elemental/masa y energía reactiva con referencia sensible. Cierres explícitos de composición y verificación total sin duplicar independencia.

## Próxima prioridad: reacciones
1. Catálogo HTTP de sustancias del proveedor: ID estable, fórmula, carga si aplica, masa molar y unidad, fases, referencias y modelos soportados. Fórmula escrita por usuario no identifica automáticamente una sustancia.
2. Cinética general y redes: varias reacciones por volumen, leyes de acción de masas y órdenes explícitos, constantes/unidades/base y Arrhenius referenciado. Resolver balances implícitos cuando dependen de la composición de salida; declarar solver real, tolerancias, escalas, restricciones y residuo. Conservar tasas directa/inversa separadas; si solo existe neta, brutas desconocidas.
3. Lote transitorio: estado inicial compatible, volumen/base, integración ODE, tiempo/muestreo, tolerancias, agotamiento y no negatividad. Comparar redes consecutivas, paralelas y reversibles contra soluciones independientes.
4. Equilibrio químico calculado: potencial químico, actividades/fugacidades, estado estándar, K(T)/ΔG, restricciones elementales y criterio de estabilidad. Tasas iguales impuestas no demuestran equilibrio termodinámico.
5. Reactores con energía acoplada: cerrar T y tasas simultáneamente, explicar referencia de formación/sensible sin doble calor; casos isotérmico/adiabático y regresión térmica. CSTR/PFR solo con modelos y supuestos expresamente soportados.

## Siguientes áreas (siguen pendientes)
6. Entropía, Gibbs/potencial químico, segunda ley y exergía: propiedades trazables, temperatura de frontera y ambiente.
7. Conducción 1D estacionaria en capas/contactos con condiciones de frontera; luego capacidad concentrada transitoria. Sin mallado/CFD.
8. Difusión/películas: bases de flujo, propiedades y equilibrio interfacial.
9. Momento e hidráulica: presión no uniforme, tuberías/pérdidas y rangos de correlaciones. Bombas no son prioridad actual.
10. Más de dos volúmenes, puertos/variables tipados para piezas compuestas; exponer decantador existente con contrato y pruebas.

## Pendientes transversales
Expresiones tipadas para comprobar dimensiones automáticamente y origen por término; sensibilidad e incertidumbre sobre ejecuciones válidas, diferenciando error numérico y de modelo. Todas las capacidades nuevas deben anunciar límites y ejemplos reproducibles.

## Integración frontend actual
/laboratorio/reacciones incorpora Motor reactivo: cinco peticiones copiadas de los ejemplos de la entrega, modificación de tasa directa, llamada real a /laboratorio/resolver, fuentes brutas/netas y traza. No hay fallback numérico a respuestas guardadas. La mesa térmica conserva su adaptador binario; el editor local de redes 1:1 sigue independiente. La conexión de un montaje reactivo arbitrario en la mesa requiere todavía editor de especies del proveedor y datos de reacción por instancia; no se presenta como ya terminada.

## Migración de exploraciones locales
Balanceo racional, Hess/Kirchhoff, cinética analítica y redes ideales locales son prototipos educativos explícitos. Para convertirlos en fundamentos reutilizables del simulador, llevar su lógica física a servicios/modelos backend con contrato versionado, casos analíticos y unidades; frontend conserva edición, diagramas, LaTeX y comparación. No mantener dos implementaciones productivas de la misma física ni usar fallback local silencioso si falla el backend. El ensamblador debe ser común al laboratorio y a operaciones compuestas, separado de sus endpoints/UI.

## Borrador de sistema general
El frontend incorpora edición de varias reacciones con coeficientes arbitrarios y especies compartidas por ID local, inspector y matriz. Exporta tipo borrador_estequiometrico_frontend, no una petición de API. Fórmulas sin identidad del proveedor no se validan físicamente. Al entregar el catálogo y el contrato general, mapear explícitamente especies del proveedor, volumen, tasas/base y condiciones; no interpretar este JSON como un sistema ya validado.

## Integración de 2e1153d
La sección Cinética y energía · backend permite configurar un volumen estacionario, especies por CAS confirmado, varias reacciones provenientes del editor general, órdenes explícitos, Arrhenius referenciado, actividades o fracciones molares, tasas integradas/volumétricas y modos T/Q/adiabático. Construye una petición por tipos físicos; no ejecuta ecuaciones en el navegador. Permite validar antes de resolver, conserva petición/respuesta y muestra avance, fase, métodos y convergencia originales. La inversa explícita admite órdenes, Ea y T_ref independientes, con base común; la UI admite Arrhenius clásico y referenciado. El ensamblaje de dos volúmenes cinéticos sigue como ampliación de interfaz, no como capacidad pendiente del backend.

verificar_entrega_acoplada.mjs: pruebas optativas contra servicio vivo de ambigüedad/identidad, primer orden analítico y equivalencia adiabática/isotérmica. No se añade a npm test porque necesita servicio local activo.

## Integración de dc6ede0
Balanceo principal conectado a /laboratorio/balancear, con toda la base si la dimensión supera uno. Lote y equilibrio usan servicios reales: inventarios en mol, tiempo, integrador y tolerancias; comparación independiente con equilibrio, curvas y detalles del método/conservación. Energía muestra Hess en referencia y Kirchhoff riguroso frente a van’t Hoff del proveedor. No se interpreta LaTeX ni se ejecuta un fallback físico local. Los cuadernos conservan la ejecución original y recuperar restaura solo parámetros. Desde_equilibrio usa ahora K riguroso: los históricos anteriores siguen originales, con aviso de cambio.

Pendiente de interfaz (no de backend): montar dos volúmenes cinéticos desde el editor. Lote adiabático sigue sin soporte; los servicios de lote de esta entrega son isotérmicos. Las exploraciones analíticas locales anteriores quedan etiquetadas como referencia.

Verificación optativa: node verificar_migracion_reacciones.mjs contra servicio local activo; balance único, dimensión dos y contraste lote/equilibrio con propiedades rigurosas.

## Consolidación antes de ampliar operaciones
La prioridad de arquitectura y criterios de aceptación está en CONSOLIDACION_FUNDAMENTOS_CLAUDE.md. Auditar reutilización del motor y traza de los servicios antes de implementar áreas nuevas. No duplicar solvers en frontend.


## Mesa por volumen y definición reactiva reutilizable

El frontend permite consultar por volumen balances de materia, energía y momento sobre las mismas conexiones. La corriente intermedia se identifica como un estado compartido con signo opuesto en ambos volúmenes. Las expresiones explicativas no se presentan como ecuaciones ejecutadas. Momento sigue siendo consulta; no hay cálculo local de fuerzas ni velocidades.

Pendiente de integración: un contrato de asociación de una definición reactiva (IDs del proveedor, matriz estequiométrica y leyes) a cada volumen de la mesa, con alimentación multicomponente y salida compartida. La mesa todavía conserva el adaptador CSTR demostrativo: no sustituir sus sustancias por una reacción arbitraria ni mostrar sus resultados como si correspondieran a ella. La investigación reactiva independiente sí envía sus leyes al motor existente.

Para extender momento, declarar capacidades, áreas, velocidades, fuerzas y cierres antes de habilitar cálculo. No interpretar el supuesto de cambios de energía cinética/potencial despreciables como ausencia de fuerzas.


## Estudios estacionarios y temporales
Contrato y criterios de aceptación: [CONTRATO_ESTUDIOS_DINAMICOS_CLAUDE.md](CONTRATO_ESTUDIOS_DINAMICOS_CLAUDE.md). La mesa temporal está preparada para formulación/persistencia; ejecución y transferencia de estados pendientes de motor.


## Prioridad vigente después de estudios materiales
La primera entrega material acoplada está implementada e integrada. La siguiente entrega autosuficiente es ENTREGA_ENERGIA_REACTIVA_CLAUDE.md: hito A energía dinámica acoplada, hito B fuentes reactivas reutilizando el motor existente. No repetir la tarea inicial ni habilitar transferencias pendientes.
