# Evidencia inicial de fiabilidad

16 de octubre de 2026. Backend local en 8004, respuestas HTTP sin correcciones.

| Modelo | Trabajo escalado / límite 1 | Certificación |
|---|---|---|
| NRTL ChemSep | 1.1051195826511973 | no_cumple |
| UNIFAC original | 0.6301143844154167 | cumple |
| Ideal | 0.09442090540460886 | cumple |

Las tres peticiones solo difieren en paquete e ID de correlación; no comparten una temperatura de transición impuesta. Todos los resultados son parciales por la política monofásica.

- `*-peticion.json`: entradas derivadas de la petición monofásica original de Claude.
- `*-validar-respuesta.json`, `*-resolver-respuesta.json`: respuestas originales de las rutas.
- `resumen.json`: certificados, eventos, residuos y contabilidad SI de cada respuesta. No sustituye la certificación física ni observa la cuadratura auxiliar interna.
- `certificacion-nrtl.png`: prueba de la interfaz con una copia independiente de la hoja monofásica, paquete cambiado explícitamente a NRTL. La copia conserva el título heredado del ejemplo UNIFAC; el modelo realmente ejecutado es NRTL, verificable en su solicitud y procedencia.

Prueba visual: hoja `86574cf5-652e-4f0a-9123-836f0c035033`, resultado parcial a 21.6746664 s. `Ver certificación` abre el aspecto fallido; conservación, estados y segunda ley permanecen como `cumple`. Se preservan ambas muestras y el corte original en 0 s. Las hojas anteriores no se modificaron.

Frontend: el aviso usa «verificación no superada» en lugar de atribuir todo `no_cumple` a un «incumplimiento físico». No cambia certificados, residuos, tolerancias, muestras ni ecuaciones.

Verificación ejecutada: 40 comprobaciones del aviso, 237 de consolidación, TypeScript y ESLint sobre el archivo modificado; todos con código 0. Se resolvieron también los tres casos por HTTP y el caso NRTL desde la UI. No se repitió toda la batería física del backend ni se modificó ese backend.

Incidencias F9-R1/R2: [anexo de eventos y dominios](../../docs/history/frontend/contract-claude-reliability-events-and-domains.md). No cambia la tarea en curso de Claude ni la prioridad del [roadmap principal](../../docs/engine/multiphysics-roadmap.md). Avisos numéricos previos: [log preservado](../qa_integracion_unifac_2026_10_16/avisos-backend.txt); su causa sigue pendiente de diagnóstico.

Reproducir desde `frontend`:

```powershell
node auditar_fiabilidad_evento_fase.mjs --servicio
npm run test:certificacion
```

Las reproducciones nuevas se guardan en carpetas nuevas de `.tmp/`; esta evidencia inicial permanece intacta. El test de UI usa estas respuestas históricas para comprobar el tratamiento de un resultado sin certificar; no exige que el servidor siga teniendo el defecto.
