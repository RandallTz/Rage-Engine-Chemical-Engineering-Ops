# Integración UNIFAC · 16 de octubre de 2026

**Integrados y comprobados:** UNIFAC original, Dortmund y la tabla ELL dentro de las capacidades publicadas. La tabla ELL admite seis especies entre 283.15 y 313.15 K; el metanol queda bloqueado por falta de asignación. Ningún paquete se sustituye por otro automáticamente.

Entrega física: [docs/engine/unifac.md](../../engine/unifac.md). Contratos canónicos: `docs/contratos/`. Preparación y pruebas anteriores: [informe](preparation-integration-unifac.md).

## Recepción del código final de F1

16/10/2026: recibida la confirmación de Claude de las ocho suites físicas con el código final y su caché de términos dependientes de temperatura. Se recargó únicamente el proceso verificado de uvicorn del puerto 8004, con el mismo ejecutable, argumentos y directorio; proceso nuevo 23404. El frontend de 3000 permaneció activo. No se editó el núcleo ni se repitió la batería física que entregó Claude.

Verificación de Codex contra esa instancia: `node verificar_integracion_unifac.mjs --servicio`, **105 comprobaciones**, código 0, además de los lectores de las 53 respuestas originales incluidos en ese comando. Estados y rechazos de catálogo/dominio, red original de cinco especies, Dortmund de cuatro, mezcla ELL y T–xy pasan. Las tres trayectorias publican certificado `cumple`. Log: `.tmp/unifac-final-integracion-20261016.log`; respuestas originales: `.tmp/qa-unifac-servicio/`; comparación exacta con la entrega: `.tmp/unifac-final-comparacion-20261016.json`.

Comparación final: 26 bloques/respuestas idénticos, incluidos tiempos físicos, series, estados, eventos, residuos, certificados y procedencia de las tres redes. En la respuesta completa de T–xy solo difiere `/cobertura/presupuesto/segundos` (0.842 frente a 2.117 s); no difieren sus puntos ni el resto de sus campos. Se conservan ambas respuestas sin corregirlas. El tiempo de cálculo no se trata como resultado físico ni se generaliza como benchmark de todas las mezclas.

F9-R1 permanece abierto: Claude documenta que búsqueda y publicación usan semillas distintas y no deciden igual sobre una fase incipiente de aproximadamente 1e-11 mol. La mayor precisión de evento que probó no está entregada como arreglo; no se reduce la tolerancia ni se declara certificada la trayectoria NRTL afectada. F9-R2 y F9-R3 conservan el alcance registrado en el roadmap.

**Continuidad de backend:** F2.1, siguiendo «Ejecución de F2 para Claude» en el [mismo roadmap](../../engine/multiphysics-roadmap.md). F1 no se vuelve a encargar; esta recepción no abre otro plan.

## Recorrido disponible

- Las tres variantes se eligen explícitamente por ID y versión en los selectores existentes.
- Grupos, cantidades de subgrupo, fuentes y huellas están dentro de **Alcance y evidencia del paquete**; no se añaden a la pantalla principal.
- El catálogo impide nuevas asignaciones de una especie identificada que el paquete no admite. Una especie conocida sin grupo muestra `Sin asignación en esta tabla`. El catálogo global puede conservarla para otros volúmenes o paquetes.
- Los componentes que una hoja ya tenga no se eliminan al cambiar de modelo. Es posible retirarlos o corregir el modelo. Los borradores simbólicos siguen permitidos; su identidad se comprobará al validar.
- Las temperaturas iniciales y presiones de frontera constantes muestran un aviso si salen del rango publicado, con conversión de unidades. No se recortan valores, no se deduce el dominio exacto de una mezcla y no se evalúan localmente trayectorias de expresiones. `/validar` conserva la decisión física y bloquea la resolución si corresponde.
- Faltantes termodinámicos y recuento estructural siguen separados: faltan datos del paquete aunque GL sea cero. No se modifica el recuento ni se fabrica una inicialización.
- La invalidación de resultados conserva la identidad modelo/versión; caché y superposición de diagramas exigen la huella correspondiente. Las huellas de tablas no se confunden con la huella completa del modelo.

## Seis hojas listas para probar

En **Hojas → Añadir pruebas multifásicas** se añaden, sin sobrescribir documentos existentes:

| Hoja | ID |
|---|---|
| Original · calentamiento de dos componentes | `motor-unifac-v1-original-2` |
| Original · calentamiento de cuatro componentes | `motor-unifac-v1-original-4` |
| Original · red de cinco componentes e inversión | `motor-unifac-v1-red-5` |
| Original · detención por política de fase | `motor-unifac-v1-monofasico` |
| Dortmund · calentamiento de cuatro componentes | `motor-unifac-v1-dortmund-4` |
| ELL · mezcla adiabática y separación líquida | `motor-unifac-v1-lle-mezcla` |

Son copias de las solicitudes originales, editables y sin respuestas precargadas. Solo se cambia el ID de correlación de la petición al usarla como configuración. No contienen ramas del motor ni propiedades escritas a mano.

## Verificación

| Prueba | Evidencia |
|---|---|
| Lectura de los 53 JSON originales | 101 comprobaciones; tres capacidades, 12 puntuales, una validación, seis resoluciones y seis diagramas; 47 estados dinámicos originales |
| Certificación de las seis resoluciones originales | Se conserva `cumple`, incluidos el resultado parcial y su evento terminal |
| Verificador específico UNIFAC | 65 comprobaciones adicionales de variantes, tablas, hojas, restricciones y dominio con K/°C/°F |
| Verificador específico con HTTP | 105 comprobaciones; tres estados positivos de 7/4/6 especies; rechazos reales de metanol y dominio ELL; tres redes/trayectorias certificadas; T–xy original |
| Recorrido en navegador | Original de dos componentes resuelto, certificación `cumple`; T–xy y P–xy con 47 puntos cada uno, sin huecos, con marcadores de la trayectoria y huella exigida |
| Controles ELL en navegador | 314 K muestra aviso y rechazo del backend; Deshacer restaura 298.15 K. Metanol no se puede asignar a los volúmenes ELL; se cierra el borrador sin guardarlo |
| Regresión del frontend | `npm run test:motor-fundamental`, código 0, incluidos los nuevos verificadores |
| TypeScript / ESLint | Sin errores en los archivos modificados |

Comandos, desde `frontend`:

```powershell
npm run test:unifac
node verificar_integracion_unifac.mjs --servicio
npm run test:motor-fundamental
npx tsc --noEmit
```

Los casos llamados `simulado` en la entrega solo se leen como evidencia original. No se reproducen contra el servicio real ni se alteran sus tablas para provocarlos.

La prueba HTTP guarda respuestas originales en `.tmp/qa-unifac-servicio/`. Logs: `.tmp/unifac-integracion-http.log` y `.tmp/unifac-regresion-20261016.log`. La comprobación del frontend no repite el flash ni reemplaza los contrastes físicos independientes de Claude.

## Límites que permanecen visibles

- Evidencia predictiva `cualitativa` para L–V y L–L; grupos disponibles o convergencia no equivalen a validación experimental general.
- Catálogo actual: siete especies para original/Dortmund; seis para ELL. La arquitectura y los gráficos no seleccionan ni truncan a dos componentes. El trazador T–xy/P–xy sí es binario por su definición actual.
- Vapor ideal hasta 5 bar; líquido incompresible. ELL solo entre 10 y 40 °C, sin metanol.
- Los tamaños contrastados estáticos y dinámicos se muestran por paquete; no se equiparan al máximo admitido.
- Estabilidad por búsqueda finita y vigilancia de fases por puntos del paso, con el alcance publicado.
- Sigue documentado por Claude el residuo de trabajo de aproximadamente 1.1 frente a tolerancia 1 en el caso NRTL detenido justo en una arista. No se relaja el lector ni se declara certificado un resultado que el backend no certifica.

### Observación numérica para Claude

En el log del servicio durante estas pruebas aparecieron `RuntimeWarning` de división/logaritmo en `core/unifac.py` y de desbordamiento de `exp` en `core/mezclas.py`. Los resultados publicados pasaron el lector estricto y sus certificados; no se recibieron estados con NaN/inf ni rechazos inesperados. No se ha diagnosticado aquí si los avisos corresponden exclusivamente a candidatos descartados durante la búsqueda. Queda para F9 revisar ese tratamiento y documentar qué sucede con esos candidatos, sin limitarse a silenciar los avisos.

Evidencia preservada: `qa_integracion_unifac_2026_10_16/avisos-backend.txt`; log completo en `.tmp/unifac-backend-err.log`. No se modificó el núcleo para ocultarlos.

## Archivos y operación

Nuevos: `alcanceEdicionPaquete.ts`, `hojasPruebaUNIFAC.ts`, `ejemplosUNIFAC.json`, `sincronizar_ejemplos_unifac.mjs`, `verificar_integracion_unifac.mjs` y este informe.

Integración: editores y biblioteca de hojas, scripts, checklist, roadmap y coordinación. Se reutilizan los lectores y la vista de cobertura preparados anteriormente.

Se recargó únicamente uvicorn en `127.0.0.1:8004` con el mismo ejecutable y argumentos para cargar la entrega. Frontend en `localhost:3000`. No se editó backend/core, datos físicos, contratos canónicos, laboratorio ni `thermodynamics/proveedor.py`. Sin commit ni push.

Evidencias visuales en `qa_integracion_unifac_2026_10_16/`: resultados, ambos cortes, fuentes/grupos y controles ELL.

**Continuidad:** F2, catálogo y propiedades con referencias coherentes, según el [roadmap principal](../../engine/multiphysics-roadmap.md). Claude continúa el hito que ya tiene en curso. La fiabilidad de eventos y candidatos fuera del dominio queda registrada en F9-R1/R2; su [anexo técnico](contract-claude-reliability-events-and-domains.md) no cambia el orden del plan. El caso NRTL sigue sin certificar en la reproducción HTTP. La ampliación de evidencia experimental UNIFAC permanece abierta; F3 generalizará después la selección de datos y resolución.
