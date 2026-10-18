# Roadmap del motor multifísico

Fecha de referencia: 16 de octubre de 2026.

**Pausa puntual solicitada por el usuario:** se planifica una herramienta independiente de adimensionalización en [su plan específico](PLAN_ADIMENSIONALIZACION_ECUACIONES.md), preferentemente en otro chat del mismo proyecto. No se integra todavía con el simulador ni cambia el orden o el estado de F3–F10. La entrega tiene alcance propio autorizado; no es otro documento de prioridades para el motor multifísico.

**Plan principal y registro de continuidad. F1 y F2 integrados dentro del alcance publicado. El registro contiene ocho sustancias; UNIFAC-ELL admite siete y mantiene metanol bloqueado por datos. El siguiente punto del plan es F3. Claude continúa el trabajo del plan que ya tiene en curso.** Las incidencias de eventos y dominios pertenecen a F9; no abren otra fase ni sustituyen automáticamente la tarea en curso.

Actualización de coordinación: se retira la indicación anterior de anteponer un encargo nuevo de fiabilidad a F2. La evidencia del fallo NRTL se conserva y su resultado sigue sin certificar. Documentar una incidencia no cambia el orden del plan.

## Documentos de trabajo

| Documento | Para qué sirve |
|---|---|
| [Este roadmap](ROADMAP_MOTOR_MULTIFISICO.md) | Orden, dependencias y criterios de cierre de las fases |
| [Contrato de UNIFAC para Claude](CONTRATO_CLAUDE_UNIFAC_MOTOR.md) | Especificación de F1 ya entregada; referencia histórica de aceptación |
| [Coordinación Claude / Codex](COORDINACION_CLAUDE_CODEX_MOTOR.md) | Responsables, estados, formato de entrega y texto para iniciar el trabajo |

Este plan corresponde al motor independiente `/motor`. El código anterior y `/laboratorio` son antecedentes y referencias; sus capacidades no cuentan automáticamente como implementadas en `/motor`. `roadmap.md` de la raíz sigue siendo una bitácora histórica, no el estado de este plan.

Este documento mantiene el alcance autorizado y las dependencias. No habilita capacidades por sí mismo. Ninguna casilla pendiente se declara hecha por haber escrito su contrato. Los informes de entrega y anexos aportan evidencia a una fase; no son planes alternativos.

## Registro único de avance y continuidad

Actualizar este registro al recibir una entrega. No crear otro tablero con estados distintos en coordinación, informes o contratos.

| ID | Estado verificable | Trabajo siguiente / evidencia |
|---|---|---|
| BASE-N | Integrado dentro del alcance publicado | [Integración N](INTEGRACION_ENTREGA_N_COMPONENTES.md); no se exige repetir la entrega |
| F0-ARR | Arranque concurrente corregido y contrastado en la entrega F1 | [Entrega física](../docs/MOTOR_UNIFAC.md) e [integración](INTEGRACION_UNIFAC.md); F0 completo conserva otras tareas |
| F1A / F1B | Integrados | [Integración UNIFAC](INTEGRACION_UNIFAC.md) |
| F1C | Integrado con cobertura parcial | Siete especies tras añadir acetona en F2; metanol sin asignación, sin aproximaciones |
| F2 | Integrado y comprobado dentro del alcance entregado | [Entrega acumulativa, §11–§15](../docs/MOTOR_CATALOGO_PROPIEDADES.md). Sustituciones de tres datos puros, corrientes con la misma referencia y acetona real. Límites de F2 conservados más abajo |
| F3–F8 | Planificados por dependencias | Mantener orden y alcance de las secciones respectivas |
| F9-R1 | Reproducido; causa documentada por Claude; corrección pendiente | Criterios de fase inconsistentes entre búsqueda y publicación al cambiar la semilla, [entrega §7.1](../docs/MOTOR_UNIFAC.md); [evidencia inicial](qa_fiabilidad_motor_2026_10_16/LEEME.md) |
| F9-R2 | Avisos observados; causa pendiente de diagnóstico | Candidatos fuera del dominio: [anexo técnico](CONTRATO_CLAUDE_FIABILIDAD_EVENTOS_Y_DOMINIOS.md) |
| F9-R3 | Corregida en backend y comprobada por HTTP en F2.3 | Metanol puro con UNIFAC-ELL devuelve `MOTOR_ESTADO_UNIFAC_ASIGNACION_AUSENTE`; no se relaja el lector. Evidencia original conservada |
| F9-R4 | Corregida en backend; nuevos ejemplos leídos y contacto térmico comprobado por HTTP | Inversión PH/UP de especie pura en un paquete de mezcla; fundamento y regresiones físicas en [entrega §14](../docs/MOTOR_CATALOGO_PROPIEDADES.md) |
| F10 | Posterior a validar el motor | Laboratorio permanece fuera del trabajo actual |

**Cierre de backend F1 recibido, 16/10/2026:** Claude confirma las ocho suites del motor con el código final, incluida UNIFAC (136 comprobaciones), y resultados idénticos con la caché de términos dependientes de T. [Entrega acumulativa, §14–§17](../docs/MOTOR_UNIFAC.md). Esta optimización no añade capacidad física ni corrige por sí misma F9-R1/R2/R3. Después se recibió la entrega parcial F2 indicada más abajo; F9-R1/R2 permanecen pendientes.

**Verificación final de integración F1:** uvicorn recargado con el código entregado; 105 comprobaciones de integración HTTP correctas. Comparadas las tres variantes: estados, series, eventos, residuos y certificados idénticos a los ejemplos; en T–xy solo cambia el tiempo de ejecución registrado. [Recepción y evidencia](INTEGRACION_UNIFAC.md). No se editaron módulos físicos ni se cambiaron tolerancias.

### Regla de continuidad

- Claude continúa el hito que ya está ejecutando; Codex integra la última entrega verificable y prepara el siguiente punto que no requiera inventar contrato o física.
- Cada avance se registra con ID de fase/hito, responsable, evidencia y pendiente concreto en este documento. La ubicación de los fundamentos detallados no altera la prioridad.
- Una incidencia transversal se añade a F9 con la operación afectada y su alcance. Solo bloquea la parte que no pueda ejecutarse o certificarse; no reinicia entregas completadas ni detiene automáticamente otra fase.
- Si una incidencia impide cumplir un criterio del hito activo, se corrige dentro de ese hito. Una repriorización más amplia corresponde al usuario, no a la creación de un documento nuevo.
- Una entrega parcial conserva lo comprobado. El siguiente avance parte del pendiente identificado, sin volver a encargar todo el contexto.
- Para cada fase, primero contrato canónico y datos, después lector/UI/servicio, finalmente evidencia y casillas. No crear campos provisionales que el backend aún no publica.

## 1. Base entregada

| Área | Disponible | Límite que permanece |
|---|---|---|
| Materia | Conservación por componente, acumulación, corrientes y volúmenes acoplados | El ensamblaje termodinámico no admite todavía cualquier expresión o cierre posible |
| Energía | U/H, transporte de entalpía, calor, trabajo de frontera, presión prescrita o recipiente rígido | Alcance acotado de geometría, modelos y relaciones admitidas |
| Agua | IAPWS-95, TP/PH/UP/UV y TV donde corresponde, coexistencia L–V | Región crítica excluida; hielo solo en evaluación estática |
| Mezclas | Ideal y NRTL; estabilidad y reparto de dimensión general | Catálogo actual de siete especies; datos NRTL incompletos para muchos conjuntos |
| Dimensión contrastada | Ideal hasta siete especies; NRTL hasta cuatro en conjuntos con datos | Tres fases y tres volúmenes admitidos; no equivalen a límites teóricos de la arquitectura |
| Estados | Fracciones de fase, composiciones, potenciales y procedencia | Propiedades y modelos adicionales requieren datos y contraste propios |
| Diagramas | T–xy y P–xy binarios; P–T del agua con hielo | Sin trazado completo LL/LLV/SLE, pliegues ni cortes N-componentes |
| Resolución | Temporal acoplado dentro de las combinaciones publicadas | Falta resolución general estacionaria, inversa y DAE |
| Verificación | Certificados, conservación y segunda ley cuando es evaluable | Estabilidad por búsqueda finita y vigilancia de fases por puntos del paso |
| UI | Hojas, edición, Deshacer/Rehacer, unidades, recuento y gráficos por variable | Ampliaciones futuras deben mantener el mismo recorrido compacto |
| UNIFAC | Original, Dortmund y tabla ELL en el motor independiente: estado, energía, redes y diagramas | Predicción cualitativa; vapor ideal hasta 5 bar. ELL entre 283.15 y 313.15 K; sin grupo para metanol |
| Momento | Presentación fundamental inicial | Falta ensamblaje y resolución de momento acoplados |

Fuentes del estado actual: [entrega N](../docs/MOTOR_TERMODINAMICA_N_COMPONENTES.md), [integración N](INTEGRACION_ENTREGA_N_COMPONENTES.md), [ensamblaje](../docs/MOTOR_ENSAMBLAJE_DINAMICO.md), [multifásico](../docs/MOTOR_EQUILIBRIO_MULTIFASICO.md), [diagramas](../docs/MOTOR_DIAGRAMAS_EQUILIBRIO.md) y [checklist](CHECKLIST_MOTOR.md).

## 2. Mapa de fases

| Fase | Prioridad | Resultado buscado | Dependencias |
|---|---|---|---|
| F0 | Inmediata | Base reproducible, arranque y contratos fiables | Base actual |
| **F1A** | **Integrada** | **UNIFAC original: estado, energía, dinámica y diagramas** | F0 mínimo y auditoría U0 |
| **F1B** | **Integrada** | **UNIFAC Dortmund como paquete propio** | Interfaz y pruebas de F1A |
| F1C | Integrada con cobertura parcial | Juego específico de UNIFAC para ELL, si resulta útil y verificable | Auditoría de grupos, parámetros y evidencia |
| F2 | Alta | Catálogo extensible y propiedades coherentes, con overrides controlados | F1A; parte documental puede avanzar en paralelo |
| F3 | Alta | Ensamblaje de ecuaciones y resolución estacionaria/inversa/DAE | Base actual; adaptadores de F1/F2 |
| F4 | Alta para equipos reales | Fronteras abiertas, gases no condensables y caudales calculados | F2 y el cierre numérico necesario de F3 |
| F5 | Alta para reactores | Reacción cinética y equilibrio químico con energía coherente | Referencias de formación y datos de F2; F1/F3 |
| F6 | Siguiente | Momento y red hidráulica acoplados a materia/energía | F3; propiedades de transporte y estado |
| F7 | Siguiente | Transferencia fuera del equilibrio y modelo 1D temporal acoplado | F1/F2/F3; F6 cuando se calcule el flujo |
| F8 | Por ramas | EOS de mezclas, sólidos, regiones críticas y diagramas avanzados | Base termodinámica estable y datos por rama |
| F9 | Transversal | Rendimiento, reproducibilidad, incertidumbre y operación fiable | Se exige desde F0; se amplía con cada fase |
| F10 | Después de validar `/motor` | Comparación formal y convergencia con `/laboratorio` | Casos y fundamentos comunes ya cerrados |

F8 no es un bloque monolítico: una necesidad de gases a presión elevada adelanta su rama EOS; una cristalización adelanta su rama sólida. Se documenta el cambio de prioridad sin mezclarlo en el encargo de UNIFAC.

No se fijan semanas ni fechas de terminación sin la auditoría de datos y rendimiento. Cada hito se cierra por evidencia y funcionamiento, no por fecha ni por una gráfica obtenida.

## F0. Consolidación mínima

- [ ] Congelar una línea base reproducible: versiones, capacidades, contratos, ejemplos originales y comandos.
- [x] Revisar y corregir el fallo de arranque `KeyError: 'ChemSep NRTL'`, con solicitudes concurrentes en frío; evidencia en la entrega F1.
- [ ] Verificar que capacidad publicada, parámetros disponibles y estado de inicialización no se contradigan.
- [ ] Mantener separadas completitud estructural, compatibilidad de inicialización y certificación del resultado.
- [ ] Revisar escalas de residuos por magnitud/especie, trazas, ceros y cambios de referencia.
- [ ] Registrar límites de estabilidad y eventos; conservar los resultados parciales originales.

**Salida:** informe breve y regresiones dirigidas de los defectos reproducidos. Se preservan las regresiones existentes. Responsable físico/API: Claude; integración y lectura: Codex.

## F1. UNIFAC prioritario

### F1A. UNIFAC original completo

- [x] U0: auditar variantes, datos, grupos, derivadas y acoplamientos actuales.
- [x] U1: adaptador de energía libre de exceso y actividades, con identidad reproducible.
- [x] U2: estabilidad y reparto TP genéricos, con grupos y parámetros verificados.
- [x] U3: propiedades caloríficas coherentes e inversiones PH/UP/UV/TV identificables.
- [x] U4: dinámica y redes con inventarios y energía conservados.
- [x] U5: rutas, capacidades, huellas y diagramas del mismo paquete.
- [x] U8: entrega física y contratos reproducibles.
- [x] Integración de Codex: selección, evidencia, diagnósticos, lectores, ejemplos y revisión visual.

**Salida:** elegir UNIFAC original en una hoja modifica de forma consistente equilibrio, energía, trayectoria y diagrama. No se limita a calcular gamma en una consulta aislada.

### F1B. Dortmund

- [x] U6: grupo de subgrupos, formulación y tabla de parámetros explícitos y distintos de original.
- [x] Repetir los mismos criterios de coherencia, estabilidad, energía y dinámica.
- [x] Publicar comparación por casos, sin presentar una variante como universalmente superior.

**Salida:** el usuario elige variante; cambiar de variante invalida sus cálculos y cachés anteriores. No hay sustitución automática.

### F1C. Parámetros dedicados a ELL

- [x] U7: auditar cobertura y equivalencia química de los grupos del juego ELL existente.
- [x] Integrar solo si hay datos y evidencia suficientes, con identidad de paquete separada.
- [x] Mantener un único modelo de Gibbs en cada cálculo LLV; nunca resolver LV con una tabla y LL con otra dentro del mismo estado.

**Cierre con alcance acotado:** tabla ELL integrada para sus seis especies admitidas, con metanol bloqueado por falta del subgrupo CH3OH. No se aproxima con otros grupos. El soporte de metanol y la ampliación de datos permanecen pendientes; no se declara cobertura universal de ELL.

Encargo detallado: [contrato de UNIFAC](CONTRATO_CLAUDE_UNIFAC_MOTOR.md).

## F2. Catálogo y propiedades

Secuencia de trabajo dentro de esta fase, sin abrir encargos distintos para cada paso:

| Hito | Claude: entrega física / contrato | Codex: integración | Estado |
|---|---|---|---|
| F2.1 | Auditoría y registro de sustancias extensible; separar identidad, datos puros y cobertura por operación | Leer el catálogo publicado; conservar IDs y componentes simbólicos; no mantener una lista química paralela | Integrado: ocho sustancias publicadas; acetona descubierta sin lista química local |
| F2.2 | Propiedades y correlaciones con unidad, fuente, referencia, dominio y huella | Mostrar datos declarados y realmente usados por separado, con sus fuentes; no deducir admisión por tener grupos | Integrado para Psat, Cp ideal y volumen líquido de los paquetes de mezcla; no sustituye propiedades evaluadas ni la formulación IAPWS |
| F2.3 | Incorporación de especies por datos suficientes, con rechazos estructurados | Selección desde capacidades reales y navegación al dato faltante; no aumentar límites localmente | Integrado por paquete/versión, con acetona real y F9-R3 corregido |
| F2.4 | Overrides coherentes por especie/propiedad y efecto en el potencial o cierre manual | Edición explícita, conservar original y elección; invalidar resultados y caché al cambiar el dato físico | Integrado: volumen líquido, Cp ideal y Psat; fuente obligatoria, originales guardados, restauración y caducidad comprobadas |
| F2.5 | Referencias compatibles entre paquetes y auditoría de datos de formación | Mostrar procedencia de ejecución; no convertir referencias ni corregir energías en el cliente | Integrado: corrientes con la misma referencia; IAPWS ↔ mezcla conserva rechazo material y admite contacto térmico. Datos de formación pendientes de incorporación en F5 |
| F2.6 | Ejemplos y regresión de catálogo, energía, fases y compatibilidad | Lectura estricta, unidades, persistencia, servicio y recorrido visual; actualizar este registro y checklist | Integrado dentro del alcance contrastado; ocho sustancias en catálogo no equivalen a ocho componentes por volumen ni a contraste dinámico de todos los conjuntos NRTL |

### Ejecución de F2 para Claude

**Continuidad tras el cierre de F2:** F2.1–F2.6 están entregados e integrados dentro de los límites de [la entrega acumulativa](../docs/MOTOR_CATALOGO_PROPIEDADES.md). La acetona ya está en el registro real; su alta simulada pertenecía a la primera entrega. No repetir F2 ni abrir otro encargo para lo ya terminado. Los criterios siguientes se conservan como referencia de aceptación; el trabajo siguiente se ordena por F3 y sus dependencias.

La secuencia aplicada fue F2.1 → F2.2/F2.3 → F2.4/F2.5 → F2.6; la auditoría de referencias condicionó las sustituciones y conexiones admitidas. Otra EOS, reacción, momento y nuevos solvers siguen perteneciendo a sus fases respectivas.

**F2.1 — auditar y centralizar.** Revisar el registro fijo `_ESPECIES` y los potenciales puros de `core/mezclas_datos.py`, su consumo en `core/mezclas.py`, `core/paquetes_volumen.py` y las capacidades de los servicios `backend/motor_*`. Mantener una sola identidad de sustancia y referencias por ID desde volúmenes/corrientes. Separar el registro de datos puros de asignaciones UNIFAC, parámetros NRTL y capacidades del paquete. Una sustancia registrada no queda automáticamente admitida en todas las operaciones. Los componentes simbólicos siguen funcionando en balances que no necesiten propiedades reales.

**F2.2/F2.3 — publicar cobertura ejecutable.** Auditar por paquete/operación qué datos y derivadas necesita el cálculo, de dónde salen y en qué dominio son válidos. Publicar identidad, nombre, unidad, fuente, referencia y huella de los datos usados; registrar los faltantes por sustancia/propiedad/operación. No exigir a IAPWS los campos de una correlación de líquido incompresible ni obligar a todos los modelos a usar grupos. No cargar datos mutables desde un proveedor compartido durante cada flash ni completar ausencias con ceros o sustitutos. Respetar la elección explícita de método cuando haya alternativas.

El contrato canónico debe permitir descubrir y seleccionar las sustancias realmente disponibles y sus operaciones, sin una lista paralela de siete nombres en el frontend. Claude define tipos, rutas y semántica compatibles en `docs/contratos/`; reutiliza los existentes donde basten. Codex no adivina esos campos. Incluir el límite puro y las mezclas en la misma regla de admisión para cerrar la discrepancia F9-R3 como parte de esta auditoría; no ocultarla con un filtro del cliente. No retirar límites de componentes/fases/volúmenes como sustituto de contraste numérico.

**F2.4 — overrides limitados a la física que los soporta.** Distinguir entradas del modelo/correlación de propiedades derivadas del estado. Para cada override admitido conservar original, valor o correlación elegidos, unidad, fuente, referencia y dominio. Demostrar cómo modifica el mismo potencial y sus derivadas; si no puede hacerse con ese paquete, devolver un rechazo con motivo o exigir un cierre manual explícito. No sobrescribir h, Cp, densidad o potencial químico de un estado certificado de forma independiente. Cambiar un dato físico cambia su huella y caduca resultados/caché; no muta globalmente otras hojas ni paquetes.

**F2.5 — referencias y conservación.** Auditar masa molar y referencias de energía/entropía entre paquetes conectables, incluido IAPWS frente a los datos puros de mezcla. Una corriente interna transporta la misma cantidad y energía con signos opuestos; no se recalcula con dos referencias incompatibles a cada lado. Formular una conversión explícita cuando sea válida o rechazar la conexión. No resolver una discrepancia modificando inventarios/caudales ni ajustando silenciosamente una masa molar. Auditar disponibilidad de datos de formación como preparación de F5, sin incorporar reacción en F2.

**Aceptación de F2.6:**

- Incorporar una sustancia adicional por registro de datos completos y trazables, sin rama nueva en flash/ensamblador. Si no hay datos suficientes, entregar el faltante; no inventar parámetros para completar un ejemplo.
- Contrastar propiedades y derivadas con referencias independientes dentro del dominio; comprobar las identidades del potencial y los límites puros. Las comparaciones entre implementaciones con los mismos parámetros no sustituyen evidencia experimental.
- Probar admisión y rechazo coherentes en estado puntual, inversión, dinámica y diagramas según lo que cada operación publique. No anunciar una operación por el hecho de que otra pueda usar la sustancia.
- Probar ceros/trazas, orden de componentes, parámetros/grupos ausentes, unidades equivalentes, concurrencia e inmutabilidad del registro. Conservar tamaños contrastados separados del máximo admitido.
- Probar overrides compatibles e incompatibles, referencias entre paquetes e invalidación de resultados antiguos tras cambiar identidad/datos. Mantener las distinciones concentración de componente / densidad de mezcla / densidad de fase.
- Entregar ejemplos originales y controles negativos, comparación con la base F1 y pruebas de regresión realmente ejecutadas. Un valor cambiado exige explicación física o numérica; no basta una suite en verde.

La matriz de datos, decisiones físicas y resultados se incorpora a la entrega acumulativa de F2 bajo `docs/`; sus enlaces y estado se añaden aquí. No crear otro documento de prioridades o encargo. Los tipos canónicos y carpetas de ejemplos son artefactos de la entrega, no planes alternativos.

La inspección de un campo existente no cierra el hito físico correspondiente. La masa molar usada no se deduce del nombre ni se rellena al editar; procede de la evaluación del paquete. No se anticipan endpoints ni tipos de catálogo hasta que Claude publique el contrato. Mantener los diez requisitos de aceptación siguientes:

**Avance Codex · F2.2, 16/10/2026:** en `Detalles técnicos → Referencias de certificación` se muestran por volumen e ID el CAS/proveedor declarado, el CAS usado, la masa molar declarada con su unidad/fuente y la masa molar realmente utilizada en kg/mol con su fuente. Se leen de la solicitud y primera muestra guardadas, sin consultar el catálogo actual, rellenar datos ni sustituir el modelo. [Código](app/motor/PaquetesEjecutadosRed.tsx), [evidencia visual](qa_integracion_unifac_2026_10_16/procedencia-componentes.png). Pruebas dirigidas: 44 comprobaciones de selección, identidad, caché y procedencia, incluido orden de componentes distinto y ejecución sin datos de evaluación; TypeScript y ESLint correctos. Esto prepara la trazabilidad del catálogo futuro; no implementa nuevas especies, overrides ni propiedades.

Regresión de este avance: `npm run test:motor-fundamental`, código 0; log `.tmp/continuidad-f2-20261016.log`. Se comprobaron también 45 enlaces locales de la documentación de continuidad. No se modificó ni reinició el backend de Claude; no se ejecutó de nuevo su batería física para este cambio de presentación.

**Avance Codex · F2.3/F2.6, 16/10/2026:** la consulta de estado conserva el rechazo estructurado del backend (código, especie, propietario y ruta), en lugar de reemplazarlo por un error local genérico de pertenencia al catálogo. Una respuesta `evaluado` sigue obligada a satisfacer el catálogo y todas las verificaciones del lector. Se mantiene la elección explícita de modelo/versión y la validación local de datos incompletos.

El plazo del cliente para evaluar un estado pasa de 20 a 120 s; capacidades mantiene 20 s. Prueba real con el servicio existente: UV de siete componentes UNIFAC original en 24.03 s, T = 351 K y P ≈ 101325 Pa, a partir de U/V reconstruidos de un estado TP original. Es una prueba de inversión/transporte, no un contraste independiente de la EOS. Se añadió `Cancelar espera` en la consulta, reutilizando el control de operaciones: una respuesta o finalización antigua no puede publicar sobre la siguiente. No anuncia cancelación del cálculo en Python.

Evidencia HTTP: `.tmp/qa-f2-consulta-2026-10-16T12-15-54-305Z/` (entrada y respuesta UV, resumen y rechazo real de metanol en una mezcla ELL). Pruebas dirigidas: `node verificar_contrato_termodinamica.mjs`, incluidos transporte, abortos, diagnósticos originales y guardas; opción `--servicio` para el recorrido UV y rechazo por HTTP. Este avance no publica aún un catálogo extensible ni overrides.

Verificación: regresión `npm run test:motor-fundamental`, código 0 (`.tmp/f2-consultas-regresion-20261016.log`); verificador dirigido actualizado, 281 comprobaciones; TypeScript y ESLint correctos. Consulta de agua también reevaluada en navegador sobre una copia de QA, sin modificar la hoja original. [Evidencia visual](qa_integracion_unifac_2026_10_16/consulta-propiedades-f2.png). La cancelación de transporte y las respuestas tardías se prueban con peticiones de transporte controladas, sin afirmar que se haya cancelado un solver real del backend.

**F9-R3, vinculada a F2.3 — corregida y comprobada:** la evidencia original mostraba metanol puro evaluado pese a estar excluido del catálogo ELL. Se conservan [petición mínima](qa_integracion_unifac_2026_10_16/ell-metanol-puro-peticion.json), [respuesta original](qa_integracion_unifac_2026_10_16/ell-metanol-puro-respuesta.json) y [capacidades originales](qa_integracion_unifac_2026_10_16/capacidades-puntuales-f2.json). Con la entrega F2 y el servicio recargado, la misma combinación devuelve `no_soportado` con `MOTOR_ESTADO_UNIFAC_ASIGNACION_AUSENTE`, coherente con la admisión declarada; el lector acepta el diagnóstico estructurado y conserva su guarda. [Respuesta nueva](qa_integracion_unifac_2026_10_16/catalogo-f2/metanol-ell-rechazo.json). Esto cierra la discrepancia de protocolo, no amplía la cobertura de grupos de la tabla ELL.

**Integración Codex · entrega parcial F2, 16/10/2026:** sincronizado `contratoCatalogo.ts`, lector estricto y `GET /motor/catalogo`. En `Estado → Componentes → + Componente` se busca por nombre/CAS y se elige entre las sustancias admitidas por el paquete y versión de cada volumen seleccionado. Las excluidas muestran el dato y mensaje publicados; también pueden inspeccionarse sus datos puros sin habilitarlas. Nombre y CAS se copian solo al borrador; no se impone masa molar, no se evalúan correlaciones ni se agregan especies al registro del servidor. Se mantienen edición simbólica, IDs existentes, recuento, historial e invalidación de resultados.

Fuentes, unidades, formas, coeficientes, dominios y huellas quedan en `Datos puros`, separados del estado calculado. Los lectores de capacidades de estado/red/diagramas rechazan listas duplicadas o mal tipadas, operaciones desconocidas, rangos no finitos/invertidos y máximos inválidos. Siguen aceptando campos opcionales ausentes en respuestas antiguas, catálogo puntual `null` y tamaños/identidades futuros estructuralmente válidos, sin límite químico local. `MOTOR_ENS_DATO_PURO_AUSENTE` se muestra como falta de datos del paquete, sin fabricar GL.

Pruebas dirigidas: `verificar_preparacion_paquetes.mjs`, 204 comprobaciones con ocho catálogos reales; `verificar_catalogo_motor.mjs`, 66 comprobaciones de lector/admisión/edición/transporte y 77 con `--servicio`. El recorrido HTTP compara las ocho admisiones publicadas y el rechazo puro F9-R3. [Catálogo original leído por HTTP](qa_integracion_unifac_2026_10_16/catalogo-f2/catalogo.json). Navegador: búsqueda/Enter sin alta accidental, exclusión de metanol ELL, consulta de fuentes, alta de etanol y deshacer en una copia de QA, sin editar la hoja original. [Evidencia visual](qa_integracion_unifac_2026_10_16/catalogo-f2-datos-puros.png). No se modifica el núcleo ni se repite su prueba física mediante algoritmos del cliente.

Regresión de la integración: `npm run test:motor-fundamental`, código 0, incluido el nuevo verificador del catálogo (`.tmp/f2-catalogo-integrado-20261016.log`); TypeScript y ESLint correctos. Backend recargado el 16/10/2026 a las 07:05, PID 34016, con el comando anterior; frontend continúa en el puerto 3000. La entrega física y las pruebas de Claude están en su informe acumulativo; esta integración no declara implementados overrides, alineación entre referencias ni altas reales adicionales.

**Cierre de integración F2.4–F2.6, 16/10/2026:** recibidas las secciones 11–15 de la entrega acumulativa y sincronizados los tres contratos canónicos. La acetona se descubre desde el registro de ocho sustancias; la tabla ELL publica siete admitidas y sigue excluyendo metanol. No se aumentan por ello los máximos de componentes/fases/volúmenes ni los tamaños realmente contrastados.

`Estado → Propiedades del paquete` permite sustituir por especie v_L, Cp ideal y Psat, conservando el resto del paquete. Se edita dentro de detalles, con fuente obligatoria y dominios de las correlaciones en K; Tc/Pc llevan K/Pa. El registro no cambia: se guarda una copia de sus valores al crear las sustituciones y cada propiedad puede volver al registro. En una red se indica qué volúmenes comparten el paquete. Cambiar de modelo conserva las elecciones para que el backend las acepte o rechace; IAPWS no habilita edición de estos datos.

Las sustituciones se envían en consulta puntual y `paquetes[].datosPuros`; la muestra ejecutada transporta al diagrama solo las de sus componentes, junto con la huella real. Cambiar valores o fuente caduca estado, resultado y caché; la clave del diagrama incluye también la declaración de sustituciones. Las referencias técnicas muestran la petición usada. El dominio térmico estático describe el paquete base: con una correlación sustituida se comprueban sus intervalos declarados y se exige la verificación `dominio` del backend; P, identidad, referencia, conservación y estabilidad conservan sus comprobaciones. No se evalúan correlaciones ni flashes en el cliente.

Redes por HTTP: NRTL → UNIFAC con corriente y calor, contacto térmico IAPWS/mezcla y red con v_L sustituido resueltas y certificadas; corriente material IAPWS/mezcla rechazada. También se comprobó el diagrama P–xy sustituido y el diagnóstico/ruta de una fuente ausente. Un recuento estructural listo con diagnóstico y modelo no construido se muestra como bloqueado; nunca habilita Resolver por GL = 0. [Evidencia HTTP original](qa_integracion_unifac_2026_10_16/f2-cierre/catalogo.json), [control negativo](qa_integracion_unifac_2026_10_16/f2-cierre/fuente-ausente-respuesta.json), [sustitución y original en UI](qa_integracion_unifac_2026_10_16/f2-sustitucion-aplicada.png). Se usaron copias de QA y se restauraron las sustituciones ilustrativas al terminar.

Verificación: `npm run test:motor-fundamental` código 0 (`.tmp/f2-cierre-integracion-20261016.log`), incluidos 142 controles del catálogo; 178 con `verificar_catalogo_motor.mjs --servicio` (`.tmp/f2-final-http-20261016.log`); TypeScript y ESLint correctos. Fuente obligatoria, aplicar, cambiar paquete, conservar original, deshacer y restaurar comprobados en navegador. Una consulta puntual con Cp declarado fue evaluada por el backend y su resultado desapareció al restaurar el registro. Backend recargado con el código final; no se editaron núcleo, backend, laboratorio ni dependencias.

**Límites al cerrar F2:** sustituciones solo de tres entradas puras de paquetes de mezcla; no de masa molar, propiedades derivadas, IAPWS, parámetros NRTL ni UNIFAC. IAPWS ↔ mezcla mantiene rechazo de corriente material; no se fabrica una conversión. Datos de formación no incorporados (F5), vapor no ideal pendiente (F8), sesgo de ΔHvap de la entrega declarado (1.6–5.8 % en las ocho especies), nuevos conjuntos NRTL con acetona sin contraste dinámico propio. F9-R1/R2 siguen abiertos; F9-R4 pertenece al arreglo físico documentado por Claude y no se atribuye a esta integración.

- [x] Sustituir la dependencia de un catálogo físico fijo de siete especies por un registro extensible, con admisión por datos requeridos; acetona incorporada por registro.
- [x] Separar identidad de sustancia, datos puros, grupos, pares, fases posibles y capacidad del paquete.
- [x] Mantener componentes simbólicos para balances sin termodinámica; exigir identidad solo cuando la física la necesite.
- [x] Definir cobertura por operación: tener grupos UNIFAC no garantiza Psat, entalpía, derivadas o dominio suficientes.
- [x] Incorporar nuevas especies con procedencia y rangos de validez, sin aumentar límites numéricos como sustituto de pruebas: acetona real.
- [x] Diseñar overrides por especie y propiedad; conservar dato original, fuente, unidad y elección del usuario.
- [x] Sustituir entradas del potencial de forma coherente; Cp líquido y densidad son derivados y no se parchean aisladamente.
- [x] Diferenciar concentración de componente, densidad de mezcla y densidad de fase.
- [x] Definir referencias entre paquetes conectados: misma referencia admitida; IAPWS ↔ mezcla mantiene rechazo material explícito.
- [x] Auditar disponibilidad de datos de formación antes de incorporar reacción; incorporación y contraste por especie quedan en F5.

**Salida:** incorporar una sustancia no exige agregar casos especiales al ensamblador. Un dato ausente identifica especie, propiedad y ruta. Los cambios de datos alteran la huella física.

## F3. Motor de ecuaciones y métodos de resolución

- [ ] Hacer explícita la representación tipada de variables, ecuaciones, unidades, dominios y procedencia; reutilizar lo actual antes de diseñar una nueva capa.
- [ ] Conectar la derivación fundamental y sus hipótesis con los términos realmente ejecutados, evitando un sistema de ecuaciones para mostrar y otro para resolver.
- [ ] Ampliar el recuento estructural con rango/Jacobiano y dependencias cuando proceda; nunca reemplazarlo por una resta de contadores.
- [ ] Inicialización consistente de restricciones algebraicas y estados diferenciales.
- [ ] Estado estacionario del mismo residuo físico, anulando la acumulación bajo sus hipótesis; detectar estados no únicos.
- [ ] Permitir elegir datos e incógnitas sin confundir parámetros del modelo con variables libres.
- [ ] Especificaciones inversas: caudal, calor, inventario u objetivo final, solo con ecuaciones y datos suficientes.
- [ ] Solvers no lineales y DAE/ODE rígidas según el sistema obtenido; mantener explícito qué es admitido y qué se diagnostica.
- [ ] Expresiones adicionales con AST seguro, análisis dimensional, derivadas y restricciones de dominio.
- [ ] Distinguir solución, consistencia física y validez predictiva del paquete.

**Salida:** un conjunto definido de ecuaciones puede resolverse hacia delante o atrás sin crear un “escenario” distinto en el motor. UI: datos, incógnitas, contador y Resolver; detalles numéricos fuera del recorrido principal.

## F4. Fronteras y equipos reales

- [ ] Paquetes para condensables + gases no condensables, parametrizados por especies y leyes; agua + aire será un caso de validación, no la arquitectura.
- [ ] Solubilidad/Henry cuando se modele; insolubilidad solo como hipótesis explícita y con dominio.
- [ ] Elegir formulación del gas según el régimen y los datos; UNIFAC no resuelve esta parte por sí solo.
- [ ] Frontera abierta con presión exterior y caudal obtenido por una relación física o restricción declarada.
- [ ] Entrada, salida, inversión, extracción por fase y desaparición de fase con el donante correcto.
- [ ] Separar dominio termodinámico de límites del recipiente: capacidad, presión admisible, alivio, deformación o detención.
- [ ] Pérdidas térmicas y almacenamiento de pared mediante piezas y leyes declaradas; sin coeficientes implícitos.
- [ ] Bombas, válvulas y equipos como volúmenes/relaciones de frontera según el nivel de detalle; no sumar energía o momento dos veces.
- [ ] Caudales múltiples, ramificación, mezcla y redes mayores: ampliar topología y resolverla, no solo retirar el límite de tres volúmenes.

**Salida:** una olla ventilada y un recipiente hermético se distinguen por sus fronteras y ecuaciones. No se ajusta el modelo para obtener una presión o temperatura esperada.

Antecedente, todavía de diseño: [frontera abierta con gas no condensable](../docs/DISENO_FRONTERA_ABIERTA_AGUA_AIRE.md). Sus nombres de paquete y alcance propuestos no son capacidades publicadas ni una decisión universal.

## F5. Reactores: cinética y equilibrio químico

- [ ] Catálogo de reacciones, estequiometría y conservación elemental/carga cuando corresponda.
- [ ] Referencias de formación consistentes en potenciales, entalpías y constantes de equilibrio.
- [ ] Leyes cinéticas con bases y unidades declaradas: actividad, concentración, presión/fugacidad u otra base admitida.
- [ ] Actividades/fugacidades del paquete elegido; uso de fase y estado estándar correctos.
- [ ] Compatibilidad entre constante cinética directa/inversa y equilibrio cuando la ley la exija.
- [ ] Energía química incluida una sola vez: referencias de formación o fuente equivalente formulada y demostrada.
- [ ] Acoplamiento con acumulación, calor, corrientes, cambios de fase y volumen/presión.
- [ ] Equilibrio químico y de fases simultáneo, con conservación elemental y estabilidad dentro del alcance publicado.
- [ ] Rigidez, agotamiento y cambios de régimen; comparación con referencias analíticas o independientes.

**Salida:** un reactor es una composición de balances, relaciones constitutivas y reacciones. Los módulos reactivos anteriores son referencias a auditar, no una integración automática.

## F6. Momento y red hidráulica

- [ ] Partir de conservación de momento y de sus reducciones documentadas.
- [ ] Relacionar presión, elevación, velocidad, fricción y fuerzas con geometría y condiciones de frontera.
- [ ] Densidad, viscosidad y otras propiedades con fuente y dominio; evitar correlaciones fuera del régimen.
- [ ] Bombas, válvulas y trabajo de eje con convención de signos única.
- [ ] Disipación y trabajo mecánico coherentes con energía, sin doble conteo.
- [ ] Inicializar y resolver simultáneamente flujos y presiones; detectar restricciones incompatibles.
- [ ] Definir el alcance monofásico antes de ampliar a deslizamiento o hidráulica bifásica.

**Salida:** activar momento introduce ecuaciones y propiedades reales. Desactivarlo conserva los cierres de caudal declarados y sus limitaciones.

## F7. Transporte y resolución espacial

- [ ] Acoplar el transporte de materia 1D actual con energía y propiedades locales.
- [ ] Separar equilibrio local de transferencia finita entre fases: cada uno requiere ecuaciones distintas.
- [ ] Difusión/convección/conducción, condiciones iniciales y de frontera explícitas.
- [ ] Transferencia selectiva por potencial químico u otra ley declarada, con energía transportada coherente.
- [ ] Interfaz, pared y fase con almacenamiento propio solo cuando el modelo lo represente.
- [ ] Malla conservativa, convergencia espacial/temporal, positividad y segunda ley cuando sea aplicable.
- [ ] Geometrías y dimensiones adicionales como ampliaciones posteriores; no se implementan durante UNIFAC.

**Salida prioritaria:** tiempo y 1D + tiempo. 2D/3D se mantienen como ramas futuras, sin retrasar la validación de un volumen o una dimensión.

## F8. Ampliaciones termodinámicas y diagramas

| Rama | Trabajo pendiente | Requisito de cierre |
|---|---|---|
| EOS de mezclas | Vapor no ideal, líquido compresible, reglas de mezcla y parámetros | Propiedades y equilibrio derivados del mismo potencial; raíces y estabilidad contrastadas |
| Alta presión / crítica | Dominios y métodos adecuados, derivadas difíciles y continuidad | No extrapolar el gas ideal o un modelo de actividad de baja presión |
| Sólidos | Datos de sólidos, fusión, polimorfos, SLE y dinámica del hielo | Equilibrio y energía latente coherentes; ningún reparto trifásico inventado |
| LL / LLV | Trazado completo de ramas y encuentros multifásicos | Certificación de todas las fases competidoras del paquete |
| Continuación | Pliegues, longitud de arco y bifurcaciones | Huecos explícitos, convergencia y presupuesto medido |
| N componentes | Cortes ternarios/multicomponente y superficies | Se especifica el corte y se conservan todos los componentes |
| Datos especiales | Electrolitos, asociación, polímeros u otros sistemas | Paquete específico y datos propios; UNIFAC convencional no se presenta como universal |

Los diagramas son cortes de un modelo, no nuevas leyes físicas ni cálculos que gobiernen la trayectoria. Dos paquetes diferentes no se comparan como si tuvieran una misma huella.

## F9. Calidad transversal y uso fiable

Incidencias abiertas ligadas al plan, con evidencia preservada: F9-R1 (trabajo al detener una fase) y F9-R2 (candidatos fuera del dominio). F9-R3 quedó corregida y comprobada en F2.3; su evidencia histórica se conserva. El [anexo técnico de R1/R2](CONTRATO_CLAUDE_FIABILIDAD_EVENTOS_Y_DOMINIOS.md) detalla reproducción y aceptación; no constituye una nueva prioridad. No relajar tolerancias ni certificar resultados fallidos para continuar otra fase.

- [ ] Contrastes independientes y experimentales por propiedad/régimen, separados de comprobaciones internas.
- [ ] Reproducibilidad de datos, parámetros, versiones, semillas, referencias y unidades.
- [ ] Casos adversos: ceros, trazas, permutaciones, escalado, parámetros ausentes, dominio, fases límite y múltiples soluciones.
- [ ] Localización de eventos y control entre muestras acordes al integrador; declarar límites restantes.
- [ ] Benchmarks con escalado en especies, fases, volúmenes y muestras; presupuestos explícitos.
- [ ] Inicialización y acceso a datos seguros bajo concurrencia; cachés ligadas a huellas e inmutabilidad.
- [ ] Trabajos largos, progreso y cancelación real del servidor cuando se implemente; no confundirla con cancelar la espera del cliente.
- [ ] Persistencia/importación/exportación y migración compatible de hojas; resultados caducados no reutilizados.
- [ ] Sensibilidad e incertidumbre de datos/parámetros; no presentar cifras de redondeo como precisión experimental.
- [ ] Pruebas en navegador, accesibilidad y UX compacta con unidades en todas las entradas relevantes.
- [ ] Empaquetado o despliegue reproducible después de cerrar el alcance físico ofrecido.

## F10. Comparación con laboratorio

- [ ] Definir casos comunes, unidades, referencias y supuestos equivalentes.
- [ ] Comparar ecuaciones ensambladas antes de comparar curvas.
- [ ] Identificar diferencias de física frente a diferencias numéricas o de presentación.
- [ ] Elaborar migración o reutilización solo con evidencia y alcance acordados.
- [ ] Mantener `/laboratorio` intacto mientras no exista ese encargo concreto.

## 3. Criterio de terminado para cualquier fase

- [ ] Fundamento y supuestos documentados.
- [ ] Capacidad y dominio publicados con fidelidad.
- [ ] Datos y procedencia reproducibles.
- [ ] Pruebas positivas, negativas y referencias independientes.
- [ ] Compatibilidad con resultados anteriores, o cambios explicados numéricamente.
- [ ] Contrato y ejemplos reales entregados por Claude.
- [ ] Lector, UI, unidades y resultados integrados y comprobados por Codex.
- [ ] Límites visibles en el lugar correspondiente, sin sobrecargar el flujo normal.
- [ ] Estado actualizado con enlace a la evidencia.

**Continuidad desde lo ya entregado:** F1 integrado → F2 por hitos → F3; F4–F8 según sus dependencias y F9 transversal. Claude continúa su tarea actual del plan; Codex integra la entrega disponible. No se reabre F1 ni se abren a la vez reacción, EOS de alta presión y nuevos solvers físicos por escribir un informe.
