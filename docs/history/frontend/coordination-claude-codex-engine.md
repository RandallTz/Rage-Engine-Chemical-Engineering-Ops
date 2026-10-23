# Coordinación del motor: Claude y Codex

Actualizado: 16 de octubre de 2026.

## Referencia principal

[docs/engine/multiphysics-roadmap.md](../../engine/multiphysics-roadmap.md) es el único plan y registro de avance: fase, hito, estado, evidencia y siguiente pendiente. Este documento contiene únicamente reglas de colaboración; no mantiene otro tablero ni otro orden de trabajo.

Claude continúa el trabajo del plan que ya tiene en curso. El registro principal distingue los hitos recibidos, integrados y pendientes; no repetir una fase entregada. Las incidencias F9 se vinculan al hito afectado sin cambiar automáticamente la prioridad. No interrumpir una tarea en curso por aparecer un nuevo informe o anexo.

## Responsables

| Área | Responsable | Fuente de verdad |
|---|---|---|
| Conservación, estado, potenciales, propiedades y equilibrio | Claude | Núcleo y pruebas físicas |
| Ensamblaje, inicialización, integradores y eventos | Claude | Ecuaciones ejecutadas y certificados |
| API, capacidades y tipos compartidos | Claude publica; Codex integra | Backend y tipos canónicos en `docs/contratos/` |
| Lectura, adaptación, hojas, unidades visuales y gráficos | Codex | Contratos y respuestas originales |
| Evidencia física y dominios | Claude | Datos, referencias, errores y pruebas |
| Estado de integración y checklist | Codex | Entrega recibida, servicio y comprobación visual |
| Cambio de alcance o prioridad | Usuario | Instrucción explícita y actualización del roadmap |

Se puede leer todo el código pertinente. Claude no edita frontend y Codex no edita el núcleo/backend durante este trabajo paralelo. Mantener `/laboratorio`, `thermodynamics/proveedor.py` y cambios ajenos intactos. Sin commit, push, despliegue ni actualización incidental de dependencias.

La termodinámica evalúa estados y propiedades; no modifica inventarios ni caudales. La UI no ejecuta otro flash ni corrige resultados para que pasen. El coordinador usa esas propiedades en las mismas ecuaciones de conservación.

## Continuar y completar una fase

1. Identificar el hito activo en el roadmap. Si la entrega no permite identificarlo, registrar la incertidumbre; no atribuirle una capacidad nueva.
2. Claude entrega contrato y ejemplos originales antes de que Codex dependa de campos nuevos. Una decisión rutinaria dentro del alcance se resuelve y documenta sin pedir confirmaciones sucesivas.
3. Codex integra lo publicado, conserva compatibilidad y comprueba el recorrido. Puede preparar lectura y presentación de datos existentes mientras espera el contrato siguiente.
4. Registrar evidencia y pendientes en la misma fila/hito del roadmap. Los informes detallados son anexos de esa fila, no un nuevo encargo.
5. Cerrar solo lo contrastado. Una falta de datos bloquea la combinación afectada, sin inventar parámetros y sin volver a empezar lo terminado.
6. Continuar con el siguiente hito previsto. Solo el usuario cambia el orden de fases.

Estados admisibles: **planificado**, **backend en curso**, **backend verificable**, **integración en curso**, **integrado y comprobado**, **bloqueado por datos** y **fuera de alcance**. Declarar el alcance parcial; no usar porcentajes sin base medible.

## Contratos y compatibilidad

- Los esquemas canónicos viven en `docs/contratos/`; sus copias locales deben ser equivalentes salvo imports.
- Reutilizar el protocolo cuando baste. Una ampliación publica semántica, unidad, nullabilidad, procedencia y ejemplos antes de integrarse.
- No crear endpoints o metadatos provisionales en el cliente para adelantar una entrega física.
- Una nueva variante o cambio de datos conserva identidad/versión/huella propias; no hay sustitución automática de modelos.
- Mantener separados completitud estructural, resultado numérico, certificado y evidencia predictiva.
- Un resultado sin certificar conserva sus datos y el corte publicado. Cancelar la espera del cliente no significa cancelar Python.

## Incidencias dentro del plan

Registrar en F9: ID, fase/hito afectado, revisión/huella, petición, respuesta original, esperado/observado, alcance, responsable, estado y prueba. Las evidencias pueden ocupar una carpeta técnica; no requieren un contrato nuevo.

Corregir dentro del hito activo si impide aceptarlo. En otro caso, conservar la limitación y continuar lo independiente. No subir tolerancias, sustituir tablas o modificar respuestas para ocultar un defecto. Una incidencia no redirige todo el roadmap por sí sola.

El documento `docs/history/frontend/contract-claude-reliability-events-and-domains.md` se conserva como **anexo de F9-R1/R2**, no como una orden de parar el trabajo que Claude ya está realizando.

## Entrega verificable

| Dato | Contenido |
|---|---|
| Identificación | Fase/hito, terminado/parcial/bloqueado |
| Física y datos | Fundamento, supuestos, fuentes, dominios y huellas |
| Contrato | Campos/rutas/códigos implementados; propuesta separada de lo ejecutable |
| Evidencia | Referencia independiente o experimental, error y alcance |
| Regresión | Comandos realmente ejecutados, salidas y límites |
| Compatibilidad | Cambios de estados, series, eventos, residuos y parámetros frente a la base anterior |
| Integración | Archivos canónicos y ejemplos para Codex; operación de reinicio si hace falta |
| Continuidad | Pendiente exacto y siguiente hito del mismo roadmap |

Actualizar el informe acumulativo de la fase, en vez de crear un documento de prioridades por cada avance. Conservar informes anteriores como evidencia histórica. Un informe separado solo se justifica por un contrato canónico nuevo o un fundamento extenso que no quepa en el existente; siempre queda enlazado al mismo ID del roadmap.

## Referencias históricas

| Alcance | Especificación / evidencia |
|---|---|
| Agua, energía y ensamblaje inicial | `docs/history/frontend/plan-thermodynamics-engine.md` y entregas H/E en `docs/` |
| Mezclas y multifásico | `docs/history/frontend/contract-claude-engine-equilibrium-multiphase.md`, entrega e integración correspondientes |
| Diagramas | `docs/history/frontend/plan-diagrams-equilibrium-engine.md`, entrega e integración correspondientes |
| N componentes | `docs/history/frontend/assignment-claude-thermodynamics-n-components.md` e `docs/history/frontend/integration-delivery-n-components.md` |
| UNIFAC F1 | `docs/history/frontend/contract-claude-unifac-engine.md`, `docs/engine/unifac.md` e `docs/history/frontend/integration-unifac.md` |

Sus instrucciones sobre “siguiente tarea” se leen con el estado actual del roadmap; no ordenan repetir una entrega.

## Texto de continuidad para Claude

> Continúa el hito del roadmap que ya tienes en curso. Usa `docs/engine/multiphysics-roadmap.md` como plan principal y esta coordinación para las entregas. Registra cada avance y pendiente con su ID de fase. Los informes y las incidencias F9 complementan el plan, no lo reemplazan ni cambian su prioridad. Entrega física, contrato canónico, ejemplos y pruebas para que Codex integre sin inventar capacidades. Mantén los límites de edición y conserva los cambios ajenos. No reinicies fases ya entregadas.

**Continuidad:** seguir el hito activo y las dependencias del mismo roadmap. No necesita otro documento de prioridades ni repetir hitos entregados. Los contratos canónicos y ejemplos de cada ampliación se publican antes de que Codex dependa de ellos. Las incidencias F9 conservan el estado y alcance indicados en el registro principal.
