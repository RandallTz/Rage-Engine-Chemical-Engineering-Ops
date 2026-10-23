# Integración de la consolidación C0–C3 · 15 de octubre de 2026

Se incorporó la entrega `docs/engine/multiphase-consolidation.md` al frontend de `/motor`. El backend local se levantó con los módulos actualizados en el puerto 8004; el frontend, en 3000. No se modificó la física, `/laboratorio` ni `thermodynamics/proveedor.py`. Sin commit ni push.

## Cambios

| Parte | Integración |
| --- | --- |
| Contrato | Copia actualizada de `docs/contratos/contratoEnsamblajeV2.ts`, únicamente adaptando importaciones. Se prueba su igualdad con independencia de los fines de línea. |
| Certificación | El aviso principal usa `resultados.certificacion.estado`. No se deduce aprobación de `estado: resuelto`, de segunda ley ni de residuos. `no_evaluable` tiene texto y aspecto diferentes de `cumple`. |
| Alcance | Detalles técnicos muestra los cuatro aspectos, primera muestra que incumple por aspecto, última muestra aprobada y horizonte de certificación. En gráficos de tiempo se sombrea el intervalo posterior al corte publicado. Se conservan todas las muestras y la exportación original. |
| Series | Unidad, papel, magnitud y procedencia se leen de `catalogoSeries`. El papel aparece en el selector de gráficas y el catálogo completo en Detalles técnicos. Las series derivadas no añaden variables ni ecuaciones al recuento. |
| Eventos | Se leen `faseIdsAntes`, `faseIdsDespues`, `faseIds` y `descripcion`. `sustitucion_fase` se distingue de `cambio_denominacion`; este último se identifica como cambio sin transición de primer orden. |
| Capacidades | Estado → Alcance y evidencia del paquete muestra combinaciones disponibles, nivel de evidencia y los pares publicados correspondientes a los componentes del volumen, con sus fuentes y límites. |
| Potenciales | Con metadatos explícitos se muestran G y A en J, S en J/K y μ en J/mol. Se reconstruyen los totales frente a cantidad, composición y propiedades; no se divide por moles para cambiar la respuesta. |
| Compatibilidad | Las respuestas antiguas sin catálogo/certificado siguen siendo legibles; se identifica la ausencia de metadatos. Si faltan unidades explícitas de G/A/S, se pide volver a resolver para mostrarlos. Se conserva el margen de ocho épsilon para leer las ejecuciones antiguas con fracciones `1.0000000000000002`. |

La certificación se valida como protocolo: estados y referencias de aspectos, alcance e índices, correspondencia entre residuos fallidos y aspectos que incumplen. Un residuo fallido reconocido por el certificado no impide inspeccionar la evidencia. Un certificado que afirma aprobación contradictoria se rechaza. Esto no implementa otro cálculo de certificación física en el cliente.

## Comprobaciones

- `npm run test:consolidacion`: **237 comprobaciones**, usando los ejemplos regenerados y nuevas respuestas reales por HTTP. Incluye controles negativos de unidades, catálogo, IDs, referencias, potenciales totales e índices de certificación.
- `npm run test:multifasico -- --ui`: sigue pasando con la evidencia anterior: **504 comprobaciones**. Conserva la compatibilidad de las ejecuciones guardadas.
- `npm run test:motor-fundamental`, `npm test`, `npx tsc --noEmit` y ESLint en los módulos modificados: pasan.
- `node tests/verificar_contrato_ensamblaje_v2.mjs`: seis pares v2, 36 estados de volumen y siete ejemplos puntuales aceptados; incluye el borrador C4 del backend.

### Pruebas reales adicionales

Se guardan en `qa_multifasico_2026_10_15/consolidacion/`, sin sustituir la evidencia de la entrega anterior:

1. Agua a 350 K, fuente de 1000 W con frontera a 300 K: el backend termina numéricamente (`resuelto`) y publica certificación `no_cumple`. El lector acepta la evidencia y la interfaz presenta el incumplimiento y sombrea el tramo posterior al corte.
2. Mismo sistema sin T de frontera: `resuelto`, certificación `no_evaluable`, sin serie fabricada de generación de entropía.
3. Decantador agua–butanol, extracción del líquido de mayor densidad, 600 s: desaparición a **509.8015378 s**, `faseIdsAntes = [liquido-1, liquido-2]`, `faseIdsDespues = [liquido-2]`. La fase superviviente conserva el ID; la fracción del líquido ausente es cero en presentación y su composición queda ausente.

En navegador se volvió a resolver la hoja `motor-multifasico-v2-1` con el backend actualizado. Se comprobaron potenciales totales, eventos con IDs y catálogo. Después se usó temporalmente T de frontera de 300 K para el control negativo y se retiró esa declaración para comprobar `no_evaluable`; ambas ejecuciones y sus avisos se exportaron desde el panel visible. Finalmente se restauró la declaración original de **600 K**, conservando cantidades, calor, presión y horizonte.

## Archivos principales

- `contratoEnsamblajeV2.ts`, `lectorEnsamblajeV2.ts`, `validarMetadatosRed.ts`: contrato y lectura.
- `metadatosRed.ts`: etiquetas y corte visual a partir del certificado publicado.
- `AvisoCertificacionRed.tsx`, `DetallesRedTermodinamica.tsx`, `AlcancePaqueteRed.tsx`: presentación compacta y detalles.
- `resultadoEnsamblajeV2.ts`, `TableroMotor.tsx`, `ResultadosHoja.tsx`, `EspacioRedTermodinamica.tsx`: integración con las hojas existentes.
- `verificar_consolidacion_multifasica.mjs`: regresión reproducible, añadida a `test:motor-fundamental` y disponible con `test:consolidacion`.

## Lo que sigue pendiente

C4 permanece como diseño: agua + aire, inicialización mediante presión y caudal de venteo obtenido de la restricción mecánica. No se habilitaron esas capacidades. Persisten los límites publicados por Claude: vigilancia puntual de eventos y estabilidad mediante búsqueda con refinamiento, además de los dominios de cada paquete. Esta integración tampoco convierte una certificación de muestras en garantía continua entre ellas.
