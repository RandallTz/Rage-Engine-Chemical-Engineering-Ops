# Evidencia de integración multifásica · 15 de octubre de 2026

Los archivos `*-ui.json` se exportaron leyendo el contenido visible de **Detalles técnicos → Solicitud y certificados originales**, después de resolver cada hoja desde el navegador. No se inyectaron resultados en el almacenamiento de la aplicación.

| Evidencia | Hoja | Resultado |
| --- | --- | --- |
| `calentamiento-ui.json` | `motor-multifasico-v2-1` | 9 instantes, 1 volumen, etanol–agua, cambio líquido/vapor |
| `contacto-ui.json` | `motor-multifasico-v2-2` | 6 instantes, 2 volúmenes rígidos de agua |
| `binario-ui.json` | `motor-multifasico-v2-3` | 5 instantes, 2 volúmenes, corriente interna de 0.001 mol/s |
| `decantador-ui.json` | `motor-multifasico-v2-4` | 5 instantes, 2 fases líquidas, extracción selectiva |
| `binario-editado-ui.json` | La misma hoja v2-3, editada después de resolver | 0.002 mol/s; otro modeloId; finales 0.6 y 1.4 mol |

`binario-editado-peticion.json` y `binario-editado-respuesta.json` reproducen por HTTP local el rechazo inicialmente observado en el lector del frontend. En A, muestra 2, `fraccionMasica` vale `1.0000000000000002`. La respuesta original se conserva intacta. El lector admite ahora el redondeo de máquina; una fracción que excede 1 en `1e-8` sigue siendo rechazada.

Después se restauró el caudal original de 0.001 mol/s y se resolvió otra vez desde UI. El cambio de dato retiró inmediatamente las gráficas anteriores; las iniciales y el resto de declaraciones permanecieron.

Reproducción, desde `frontend/`:

```
npm run test:multifasico -- --ui
```

Se comprueban contratos, reconstrucciones, conservación global de especies en redes cerradas y primera ley (U global para frontera rígida; H global a presión constante; calor impuesto constante cuando corresponde), sin invocar de nuevo la ecuación de estado o el solver como referencia. Los cuatro casos originales incluyen 25 instantes y 36 estados de volumen. No equivalen a una validación experimental de los paquetes.

`regresion-motor.log` contiene la salida de `npm run test:motor-fundamental` con código 0. También pasaron `npm test`, TypeScript, ESLint en los módulos modificados y el verificador TS de los seis pares v2 de Claude.

Otros recorridos observados: inicial ausente → Falta 1 y Resolver deshabilitado; volumen nuevo sin valores; agregar/retirar volumen y componente → red de nuevo lista; recarga de resultados; composición de butanol por cada líquido; movimiento de gráficas y persistencia del orden.

El informe de alcance y los límites del contrato están en `../../docs/history/frontend/integration-multiphase-v2.md`.
