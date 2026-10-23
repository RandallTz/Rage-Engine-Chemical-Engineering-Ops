# Preparación de la integración UNIFAC · 16 de octubre de 2026

Estado: **preparación cerrada y entrega integrada. Estado vigente y pruebas reales: [docs/history/frontend/integration-unifac.md](integration-unifac.md).** Este documento conserva la bitácora de preparación; los resultados finales están en ese informe.

Referencia: [coordinación](coordination-claude-codex-engine.md), [contrato físico](contract-claude-unifac-engine.md).

## Hecho mientras Claude trabaja

### Selección explícita de modelo y versión

- Selector reutilizable para red dinámica y consulta puntual, alimentado solo por las capacidades recibidas.
- Etiquetas con versión visible y claves de identidad no ambiguas: ID y versión se consideran juntos.
- Se admiten dos versiones publicadas del mismo modelo sin colisiones de claves ni selección por el primer ID coincidente.
- Un modelo guardado que ya no está publicado permanece visible como `guardado; no publicado`; la selección no se cambia automáticamente ni se convierte en una capacidad disponible.
- Se distingue el catálogo sin cargar de un paquete realmente no publicado.
- Paquetes no disponibles para la operación no pueden elegirse como si lo estuvieran.
- No hay ninguna opción UNIFAC añadida manualmente ni una inferencia de variante por nombre de sustancia.
- Lectores de capacidades detectan duplicados de ID/versión. Los lectores puntual y de diagramas evitan colisiones por concatenación con `:`.

### Resultados, caché y trazabilidad

- Comprobado que cambiar modelo o versión cambia la firma física y caduca el resultado de la hoja.
- Comprobado que cambiar el paquete de A conserva la configuración de B.
- Comprobado que seleccionar el mismo modelo/versión conserva resultados vigentes.
- La caché de diagramas sigue distinguiendo modelo, versión, huella de parámetros y versión del trazador.
- Dentro de **Detalles técnicos → Referencias de certificación** se ve la tabla de paquetes utilizados: volumen, modelo, versión y huella original.
- La tabla usa la solicitud/respuesta guardada de la ejecución, no el catálogo actual. Las respuestas antiguas sin huella muestran `No publicada en esta ejecución`.
- Se usa la etiqueta `Rango publicado del paquete` para no confundir la capacidad general del catálogo con una evaluación del dominio exacto de la mezcla seleccionada.

No se promete detectar un cambio de datos del servidor a igual ID/versión sin recibir una huella actual comparable. El lector de resultados conserva la evidencia de la ejecución original. Las futuras reglas de actualización dependerán del contrato de procedencia/cobertura que publique Claude.

## Verificador de entregas preparado

Archivo: `frontend/verificar_paquetes_entregados.mjs`.

Ejecutar desde `frontend`, con la carpeta y la identidad final publicadas en la entrega. El siguiente comando ya se ejecutó con los datos actuales:

```powershell
node verificar_paquetes_entregados.mjs --directorio ../docs/ejemplos/motor-n-componentes --modelo nrtl-chemsep --version 1
```

Lee capacidades y pares originales `*-peticion.json` / `*-respuesta.json` para:

- consulta de estado;
- validación y resolución v2;
- diagramas de equilibrio.

Usa los lectores actuales, comprueba referencias graficables y preserva todos los documentos originales. El filtro exige modelo y versión juntos; falla si faltan las capacidades o los pares correspondientes. Resume también rechazos y estados de certificación sin reinterpretarlos.

No abre el servicio, no modifica archivos y no repite un flash. No reemplaza las referencias físicas/experimentales ni declara integrado un paquete por haber podido leer sus JSON. Si el contrato cambia, se actualizan primero los tipos/lectores canónicos y las pruebas específicas de los campos nuevos.

Al preparar el verificador aún no existía `docs/ejemplos/motor-unifac/`. La entrega ya fue leída sin correcciones y probada por HTTP/UI; véase el informe final enlazado arriba.

## Verificación realizada

| Comprobación | Resultado |
|---|---|
| `npm run test:preparacion-paquetes` | 34 comprobaciones de identidad, selección, invalidación, caché y procedencia |
| `npm run test:motor-fundamental` | Pasa, incluido el nuevo verificador |
| TypeScript y ESLint de archivos modificados | Pasan |
| Verificador genérico, carpeta N-componentes, NRTL v1 | 20 comprobaciones; 3 estados puntuales, 1 validación y 1 resolución; rechazos conservados |
| Verificador genérico, carpeta de diagramas, NRTL v1 | 19 comprobaciones; 8 diagramas; rechazos conservados |
| Navegador, copia de QA | Selección por versión, otro volumen inalterado, Deshacer y nueva resolución con certificación `cumple` |

Las identidades sintéticas utilizadas en las pruebas de selección son solo metadata de UI: no contienen estados, propiedades ni una implementación física.

Evidencia visual: `frontend/qa_preparacion_unifac_2026_10_16/paquetes-ejecutados.png`.

## Continuación: acceso al campo señalado por el motor

- `Ir al dato` usa la ruta del diagnóstico, un ID de dato o la asociación explícita `variable.datoId` del catálogo. No interpreta mensajes ni elige el primer dato de un volumen.
- Un diagnóstico sobre `paqueteId` abre el selector del volumen afectado; uno sobre `frontera` abre su relación mecánica.
- Los diagnósticos de identidad de componentes abren el catálogo y el CAS por ID estable. Reordenar componentes no cambia ese destino.
- Una referencia ambigua abre la configuración del propietario identificado; una referencia global sin destino identificable permanece en el diagnóstico técnico, sin inventar un campo.
- Los enlaces validan que elemento y dato sigan existiendo y que el dato pertenezca al propietario indicado.
- Estado, Resolver, Configurar sistema y Asignar valores conservan el elemento seleccionado entre esas dos pantallas. El catálogo no se presenta como una sección vacía del solver.
- La navegación no modifica solicitudes, datos, resultados ni grados de libertad.

Verificador: `npm run test:destinos-red`, **43 comprobaciones** de rutas, catálogo, ambigüedad, referencias retiradas, codificación y enlaces. La prueba usa también el rechazo real de parámetros NRTL ausentes.

Regresión de esta continuación: `npm run test:motor-fundamental` completo con código 0, TypeScript y ESLint de los archivos modificados sin incidencias. Log: `.tmp/destinos-red-regresion-20261016.log`. El primer intento detectó las copias de tipos desactualizadas al aparecer la ampliación canónica; después de sincronizarlas pasó la batería completa sin relajar esa comprobación.

En navegador se borró temporalmente T(0) de B en una copia de QA, se volvió a A y se pulsó `Ir al dato`: abrió B y enfocó su T(0) vacía, también al repetirlo. Se restauró con Deshacer y la nueva resolución volvió a publicar certificación `cumple`. El caso negativo de NRTL abrió su selector de paquete, conservando el rechazo.

Evidencias: `qa_preparacion_unifac_2026_10_16/diagnostico-dato-volumen-b.png` y `diagnostico-paquete.png`.

Archivos: `destinoDiagnosticoRed.ts`, `verificar_destinos_diagnosticos_red.mjs`, integración en el espacio de red, navegación, páginas Estado/Resolver y destinos de foco de los editores. Sin cambios físicos.

### Ampliación canónica recibida durante esta continuación

Se sincronizaron las copias de `contratoEnsamblajeV2.ts`, `contratoDiagramasEquilibrio.ts` y el nuevo `contratoContribucionGrupos.ts` desde `docs/contratos/`, ajustando solamente las rutas de importación locales. Añaden el campo opcional `coberturaGrupos`, la identidad de tablas y asignaciones, variantes y pares dirigidos faltantes.

La sincronización inicial fue solo de tipos. La continuación siguiente prepara lectores y vista; la aceptación de los datos originales sigue pendiente. No se publicaron opciones inventadas ni se reinició el servicio que Claude está desarrollando.

## Continuación: lectores y presentación de cobertura de grupos

Se revisaron la ampliación canónica y el informe de trabajo [docs/engine/unifac.md](../../engine/unifac.md). El frontend reconoce por separado original, Dortmund y tabla ELL. No cambia la variante ni completa datos al encontrar un faltante.

- Lector común para capacidades v2 y de diagramas: tipo y variante, coincidencia de variante con sus datos, fuentes no vacías, formato SHA-256, asignaciones, cuentas enteras positivas e identidad coherente de subgrupos.
- Rechaza especies duplicadas, asignadas y no asignadas simultáneamente, grupos desconocidos en una interacción faltante, duplicados dirigidos e interacciones internas de un mismo grupo principal como faltantes.
- Los sentidos `m → n` y `n → m` se conservan por separado. El resumen toma únicamente los grupos de los componentes elegidos y no añade ni elimina componentes del ensamblaje.
- `componentesCAS` es la lista **admitida** del paquete y coincide con las especies asignadas. `especiesSinAsignacion` puede enumerar especies conocidas que quedan fuera de esa lista; se muestran como `Sin asignación en esta tabla`, no se convierten en capacidades admitidas.
- La metadata UNIFAC no se admite como si fueran parámetros moleculares NRTL. Los lectores respetan `pares` ausente en v2 y `null` en diagramas. Los demás paquetes no necesitan grupos.
- La evidencia L–V/L–L declarada por estos paquetes permanece `cualitativa`; disponer de grupos no la eleva a `contrastada`.
- Subgrupos, cuentas, fuentes y huellas se renderizan dentro de **Alcance y evidencia del paquete**, cerrado por defecto. En Equilibrio se integran en el apartado existente **Referencias y resolución**.
- Los rechazos de asignación, subgrupo o interacción UNIFAC ausente, y el parámetro NRTL ausente, muestran `Faltan datos del paquete`. Conservan íntegro el recuento del servidor: GL = 0 puede coexistir con un bloqueo termodinámico y no se habilita Resolver.

Las huellas se comprueban como metadata publicada: formato y coherencia. El navegador no vuelve a calcular el hash de los archivos del proveedor. No se calculan actividades, equilibrio, estabilidad ni propiedades en esta capa.

### Verificación de esta continuación

- `npm run test:cobertura-grupos`: **101 comprobaciones** de metadata, controles negativos, variantes, cobertura parcial, presentación y separación de datos termodinámicos/recuento estructural. Sus asignaciones sintéticas son exclusivas del verificador; no se instalan en la app ni se envían al motor.
- Con `--capacidades .tmp/capacidades-cobertura-grupos-servicio.json`: **102 comprobaciones**, incluida la lectura de las capacidades actuales por HTTP. El servidor consultado aún publica agua, ideal y los dos NRTL; no se presenta esto como prueba de UNIFAC real.
- Regresión N-componentes: 693 comprobaciones con los estados originales; se actualizó únicamente la expectativa de la etiqueta del diagnóstico de datos ausentes.
- TypeScript, ESLint y regresión completa del motor: verificados al cerrar esta continuación. Log: `.tmp/cobertura-grupos-regresion-20261016.log`.

Nuevos archivos: `coberturaGrupos.ts`, `CoberturaGruposPaquete.tsx`, `coberturaGrupos.module.css`, `verificar_cobertura_grupos.mjs`. Integración en los dos lectores, panel de alcance, Equilibrio y estado de resolución. Sin edición del backend, de sus datos, del laboratorio o de las ecuaciones físicas.

Esos pendientes de aceptación se cerraron con los ejemplos originales, el recorrido HTTP/UI, las restricciones de nuevas asignaciones y el aviso de dominio descritos en el informe final. Los datos existentes de una hoja nunca se eliminarán ni sustituirán automáticamente por incompatibilidad con un paquete.

## Cierre de la preparación

- [x] Identidades definitivas y variantes que realmente publique el servicio.
- [x] Copia local de los tipos canónicos de cobertura de grupos publicados durante la preparación.
- [x] Lectores y vista de cobertura preparados contra el esquema canónico, con controles negativos.
- [x] Aceptación de esos lectores contra las respuestas originales de la entrega.
- [x] Procedencia por variante y huellas reproducibles con esos datos.
- [x] Capacidades puntuales, dinámicas y de diagramas actualizadas.
- [x] Ejemplos reales positivos y negativos de UNIFAC original.
- [x] Contrastes físicos y caloríficos de la misma variante/datos.
- [x] Integración y prueba real UNIFAC de extremo a extremo.
- [x] Dortmund y juego ELL, cada uno según su entrega y evidencia.

No se alteró el contrato canónico ni se inventó una ampliación JSON para adelantarse al backend. El checklist refleja el alcance integrado, con los límites de datos y evidencia publicados.

## Archivos

Nuevos: `modelosTermodinamicos.ts`, `SelectorModeloTermodinamico.tsx`, `PaquetesEjecutadosRed.tsx`, `verificar_preparacion_paquetes.mjs`, `verificar_paquetes_entregados.mjs`, este informe y evidencia visual.

Integración: `EspacioRedTermodinamica.tsx`, `EditorEstadoTermodinamico.tsx`, `DetallesRedTermodinamica.tsx`, `AlcancePaqueteRed.tsx`, lectores de capacidades, `contratoTermodinamica.ts` (solo validador), CSS y scripts de `package.json`.

Backend, núcleo físico, laboratorio y `thermodynamics/proveedor.py` sin editar. Durante la preparación no se reinició el backend; la recarga para la aceptación final está documentada en el informe de integración. No se cambiaron sus dependencias. Sin commit ni push.
