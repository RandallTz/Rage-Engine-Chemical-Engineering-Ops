# Integración del catálogo de componentes · preparación de la ampliación N

15 de octubre de 2026. Trabajo de Codex en `/motor`, mientras Claude desarrolla `ENCARGO_CLAUDE_TERMODINAMICA_N_COMPONENTES.md`.

## Cambios disponibles

- Catálogo global separado de la selección de componentes de cada volumen y corriente.
- Alta con nombre, CAS y selección explícita de volúmenes. Se puede preparar un componente solo en el catálogo, sin asignarlo automáticamente.
- El límite que publica el servicio se aplica por volumen, no al número total de especies de circuitos distintos.
- Las corrientes conservan sus selecciones explícitas. Una especie nueva no entra automáticamente en todas las corrientes; las restricciones físicas del transporte siguen comprobándose en el backend.
- Las cantidades iniciales y caudales nuevos quedan vacíos, con la magnitud y unidad de su base. No se sustituyen por cero.
- Al quitar un componente se retiran sus referencias; el mecanismo existente de `cambiarRed` elimina los datos huérfanos. Las otras cantidades, unidades y temperaturas se conservan.
- Las fracciones restantes no se renormalizan. Se muestra la suma y cuántas fracciones faltan; el backend conserva la decisión sobre completitud y validez.
- No se permite dejar un volumen o corriente sin componentes. Para retirar una especie de un volumen que aún la usa en una corriente, se identifica primero esa corriente.
- El contador local `ultimoComponenteId` evita reutilizar IDs retirados. No se envía en la petición física.
- Los cambios invalidan resultados anteriores; la preparación es una edición del documento, sin flash ni propiedades en el navegador.

## Contrato de capacidades en desarrollo

Se sincronizó el campo opcional `tamanos` que Claude añadió a `docs/contratos/contratoEnsamblajeV2.ts`. El lector distingue tamaños admitidos/contrastados y comprueba coherencia con `componentesMaximos`, límite de fases, método y presupuesto.

Las respuestas históricas sin ese campo siguen admitidas. No se fija siete, cuatro ni otro tamaño en el editor: utiliza la capacidad que entregue el servicio en ejecución. La nueva física de Claude no se da por aceptada por copiar el contrato.

## Pruebas ejecutadas

- `npm run test:motor-fundamental`: código 0 después de sincronizar el contrato. Registro en `.tmp/catalogo-red-regresion.log`, desde la raíz del proyecto.
- `node verificar_edicion_componentes_red.mjs --servicio --ui`: **209 comprobaciones**, código 0. Incluye lectura de capacidades, operaciones atómicas, referencias, unidades, ceros explícitos, fracciones ausentes, IDs y respuestas reales.
- TypeScript y ESLint de los archivos modificados: código 0.

La primera ejecución de la regresión detectó la comparación exacta con la copia anterior del contrato, porque Claude acababa de añadir `tamanos`. Se sincronizó sin cambiar el verificador y la ejecución completa posterior pasó. Las ampliaciones finales de controles se comprobaron además con el verificador específico, TypeScript y ESLint.

Los ensayos locales de edición con 1, 2, 3, 4, 5, 8 y 12 componentes comprueban estructura y referencias. **No son flashes ni una validación termodinámica para N>3.**

## Comprobación real en el servicio y el navegador

Se resolvió un catálogo global de cuatro especies con dos por volumen, dentro del alcance del servicio actual:

| Dato | Volumen A | Volumen B |
|---|---|---|
| Componentes | Agua y etanol | Benceno y tolueno |
| Cantidades iniciales | 1 mol de cada especie | 1 mol de cada especie |
| Temperatura inicial | 330 K | 320 K |
| Frontera | Presión prescrita: 101325 Pa | Presión prescrita: 101325 Pa |
| Paquete | `mezcla-ideal`, versión 1 | `mezcla-ideal`, versión 1 |

Contacto térmico entre A y B con G = 0.1 W/K; sin corrientes materiales, horizonte 2 s y tres muestras. Son datos de prueba del ensamblaje común, no un escenario nuevo del solver.

Resultado original del navegador:

- A: 330 → 329.9892135789399 K.
- B: 320 → 320.0069078815406 K.
- Cada cantidad permanece en 1 mol.
- Diferencia de H total respecto de la inicial: 0 J en las tres muestras publicadas.
- Certificación: `cumple`, incluyendo conservación y segunda ley.
- Cada resultado conserva solo sus dos componentes locales, sin incorporar las especies del otro volumen.

Se trabajó sobre una copia creada con el botón Duplicar; las hojas originales no se modificaron. La copia está en `/motor/hojas/a1e138bf-512b-4d24-9881-e3c1c7b361fb`. Su título conserva el del ejemplo original más «copia».

Evidencia en `frontend/qa_catalogo_n_2026_10_15/`: solicitudes/respuestas HTTP y `ejecucion-ui.json`, tomado del panel visible «Solicitud y certificados originales». No se corrigieron respuestas antes de pasarlas por el lector.

## Archivos y coordinación

Nuevos: `componentesRed.ts`, `EditorComponentesRed.tsx`, `componentesRed.module.css`, `verificar_edicion_componentes_red.mjs`, este informe y las evidencias de QA.

Modificados en `frontend/app/motor/`: `redTermodinamica.ts`, `EspacioRedTermodinamica.tsx`, `lectorEnsamblajeV2.ts` y la copia de `contratoEnsamblajeV2.ts`. Se añadió `test:catalogo-red` y se incorporó el verificador a `test:motor-fundamental` en `frontend/package.json`.

No se editaron backend, núcleo físico, laboratorio ni `thermodynamics/proveedor.py`. No se reinició el servicio, no se cambiaron parámetros termodinámicos y no se hizo commit ni push.

## Pendiente de la entrega de Claude

Contrastar los nuevos flashes de más de tres especies por volumen, revisar los tamaños realmente verificados, incorporar sus ejemplos originales y comprobarlos en la interfaz. Este trabajo no marca ese pendiente del checklist como terminado.
