# Integración N0–N4 · 16 de octubre de 2026

Entrega del backend revisada: `docs/engine/thermodynamics-n-components.md` y ejemplos originales de `docs/ejemplos/motor-n-componentes/`.

## Integrado

- Capacidades v2 con `componentesMaximos: 7` y `tamanos`. El límite es por volumen, no por catálogo global.
- Alcance y evidencia: dentro del desplegable existente del paquete se muestran por separado dimensión admitida, tamaños contrastados en estado y trayectoria, número máximo de fases y presupuesto/método de estabilidad.
- Se conserva la lectura de capacidades anteriores que no publican `tamanos`.
- El editor usa las capacidades recibidas, sin fijar siete en el motor de presentación ni imponer un número de componentes a las ecuaciones.
- El checklist reconoce el alcance entregado: ideal hasta siete especies y NRTL hasta cuatro en los conjuntos con datos. NRTL con cinco o más especies sigue pendiente por parámetros completos y evidencia.
- Nuevas hojas editables, añadidas con el botón existente **Añadir pruebas multifásicas**. La operación no sobrescribe hojas guardadas ni sus resultados.

| Hoja | Procedencia |
|---|---|
| Mezcla ideal · Calentamiento de 5 componentes | Solicitud original de Claude |
| NRTL · Calentamiento de 4 componentes | Solicitud original de Claude |
| Red · 5 componentes con especie entrante | Solicitud original de Claude |
| Diagnóstico · NRTL con parámetro ausente | Solicitud negativa original de Claude |
| Mezcla ideal · Calentamiento de 7 componentes | Solicitud adicional: datos de calor/frontera del ideal de cinco, catálogo de siete publicado, inventario equimolar de un mol total |

Las hojas contienen solo declaraciones de entrada. No incorporan estados precalculados, propiedades ni un solver específico por ejemplo. Todas usan los mismos endpoints de validación y resolución del ensamblaje.

`sincronizar_ejemplos_n_componentes.mjs` permite regenerar o comprobar la correspondencia de las entradas locales con esas fuentes.

## Corrección de la separación entre recuento y física

El ejemplo de parámetro NRTL ausente publica `recuento.estado: listo`, GL = 0 e inicialización pendiente, junto con `MOTOR_ENS_PARAMETRO_AUSENTE`. Es un cierre estructural completo, pero el paquete carece de datos para evaluar la física.

Antes el lector rechazaba esa respuesta por exigir inicialización compatible para cualquier recuento `listo`. También el botón Resolver se habilitaba atendiendo solo al recuento.

Ahora:

- se conserva el recuento canónico, sin falsificar datos faltantes ni GL;
- una inicialización pendiente con recuento listo exige un diagnóstico de rechazo válido;
- se muestra **Modelo no disponible** y el mensaje original, una sola vez;
- Resolver exige además inicialización compatible y ausencia de diagnósticos bloqueantes;
- una trayectoria publicada sigue exigiendo inicialización compatible y todos los certificados originales;
- el control negativo ofrece revisar la configuración, en lugar de enfocar un inventario que ya estaba definido.

No se suponen parámetros, no se cambia automáticamente de paquete ni se relaja la validación de resultados.

## Pruebas

- `node verificar_entrega_n_componentes.mjs`: 693 comprobaciones sobre capacidades, respuestas reales, inicialización, componentes ausentes, series, reparto y reconstrucción por especie, gráficos y controles negativos; 24 estados por volumen originales.
- `node verificar_entrega_n_componentes.mjs --ui`: 1007 comprobaciones al incorporar la respuesta original exportada del navegador; 31 estados por volumen.
- `--servicio`: se comprobó el servicio en ejecución y se resolvió la entrada adicional de siete componentes, con certificación `cumple`. Evidencias en `frontend/qa_n_componentes_2026_10_16/`.
- `npm run test:motor-fundamental`, TypeScript y ESLint de los archivos modificados: pasan.
- El nuevo verificador forma parte de `test:motor-fundamental`; acceso directo `npm run test:entrega-n`.

Estos son controles de integración: verifican que el frontend conserva y presenta la respuesta física, sin repetir el flash. Los contrastes contra Rachford–Rice, otra implementación de NRTL y referencias físicas son los del backend, documentados por Claude. No se confunde la coincidencia numérica con evidencia experimental nueva.

### Navegador

- Se añadieron las cinco hojas mediante el botón existente, preservando las hojas anteriores.
- El control negativo muestra GL = 0 y `Modelo no disponible`, con el par ausente original; Resolver permanece deshabilitado.
- El calentamiento ideal de siete componentes se resolvió desde la interfaz durante 300 s y publicó siete muestras, incluido el evento de fase. Certificación `cumple`, con materia, energía, cierre y segunda ley comprobados por el backend.
- Resultado final: T = 365.2491 K y P = 101325 Pa; fracción másica de vapor ≈ 0.6640463. Es el resultado del modelo ideal con la frontera prescrita de ese ejemplo, no una predicción general para cualquier equipo o mezcla.
- El botón Reparto por componente creó siete gráficos, uno por especie. La tabla conserva las composiciones de las dos fases y el reparto de cada especie.
- `ideal-7-ejecucion-ui.json` contiene la solicitud y respuesta originales, sin correcciones. Capturas: `ideal-7-resultados-ui.png` y `parametro-ausente-ui.png`.
- El servicio ya publicaba `componentesMaximos: 7` y `tamanos`; no fue necesario interrumpirlo ni reiniciarlo otra vez.

## Límites conservados

- NRTL con cinco o más especies: sin conjunto completo de pares en el catálogo actual.
- Las predicciones NRTL de cuatro especies son cualitativas; el reparto L–L agua–acetato no es una predicción experimentalmente contrastada de solubilidad.
- Máximo tres fases simultáneas y tres volúmenes.
- Vapor ideal hasta cinco bar, dominio común de las especies, líquido incompresible y exclusión crítica.
- Búsqueda de estabilidad finita, sin demostración de mínimo global; vigilancia de eventos por puntos dentro del paso.
- Diagramas T–xy/P–xy binarios. La presentación de equilibrio no elimina especies para fabricar un corte binario.

## Archivos y coordinación

Nuevos: `app/motor/estadoResolucionRed.ts`, `hojasPruebaNComponentes.ts`, `ejemplosNComponentes.json`, `sincronizar_ejemplos_n_componentes.mjs`, `verificar_entrega_n_componentes.mjs`, este informe y evidencias.

Integración en `AlcancePaqueteRed.tsx`, `BibliotecaHojas.tsx`, `EspacioRedTermodinamica.tsx`, `lectorEnsamblajeV2.ts`, `app/checklist/datos.ts`, `docs/engine/engine-checklist.md` y `package.json`.

La copia local del contrato ya estaba sincronizada con `tamanos`; no se cambió el contrato canónico. Backend, núcleo, `/laboratorio` y `thermodynamics/proveedor.py` sin editar. Sin commit ni push.
