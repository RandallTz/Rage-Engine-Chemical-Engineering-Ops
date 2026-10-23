# Encargo de fiabilidad: eventos de fase y dominios numéricos

16 de octubre de 2026 · **Anexo técnico de F9-R1/R2. No cambia la prioridad ni interrumpe la tarea en curso de Claude.** Plan y estado: [roadmap principal](../../engine/multiphysics-roadmap.md).

## Alcance y responsables

Claude: núcleo, integrador, API, pruebas físicas y contratos canónicos si es imprescindible ampliarlos. Codex: lector, interfaz y pruebas de integración. Mantener el motor genérico; no añadir ramas por sustancia, escenario o paquete para lograr que un caso pase. No tocar frontend, laboratorio, `thermodynamics/proveedor.py`, ni cambios ajenos. Sin commit ni push.

Integrar estos criterios en la consolidación F9 del hito que corresponda. No constituyen una fase adicional ni sustituyen el trabajo de catálogo o propiedades que siga el roadmap. Una corrección puede entregarse junto con el hito activo si lo afecta; conservar la evidencia original y registrar el estado en el roadmap, sin abrir otro encargo.

## R1. Trabajo de frontera al detenerse en una transición

Reproducido contra HTTP el 16 de octubre. Peticiones y respuestas originales en `frontend/qa_fiabilidad_motor_2026_10_16/`; resumen en `resumen.json`.

| Paquete v1 | Resultado | Certificación | Residuo `mecanica.A.trabajo` | Tolerancia |
|---|---|---|---|---|
| `nrtl-chemsep` | parcial | no_cumple | 1.1051195826511973 | 1 |
| `unifac-original-public` | parcial | cumple | 0.6301143844154167 | 1 |
| `mezcla-ideal` | parcial | cumple | 0.09442090540460886 | 1 |

Misma declaración física: 0.5 mol de cada especie (etanol/agua), T inicial 330 K, P constante 101325 Pa, Q constante 100 W, frontera térmica a 700 K, política monofásica, horizonte 300 s, seis muestras. Solo cambian identidad del paquete e ID de correlación. Cada modelo tiene su propia temperatura y tiempo de transición; no se espera igualdad entre modelos.

Reproducción, desde `frontend` y con el servicio actualizado en 8004:

```powershell
node auditar_fiabilidad_evento_fase.mjs --servicio
```

El script guarda `/validar` y `/resolver` sin corregir sus respuestas y las pasa por el lector vigente. Cada ejecución crea una captura nueva en `.tmp/qa-fiabilidad-evento-<fechaUTC>/` y muestra su ruta, sin sobrescribir la evidencia inicial. No exige conservar el defecto. Sin `--servicio` solo genera las peticiones.

En NRTL el evento aparece a 21.674666447867764 s; `ultimaMuestraCertificada` es 0. Pasan estados, materia, energía global y segunda ley; falla únicamente el trabajo auxiliar. La contabilidad publicada satisface ΔH = Qt hasta 9.1e-12 J. Esto **no** verifica la cuadratura auxiliar independiente: W publicado y su auxiliar interno deben distinguirse al auditar. Los errores SI completos están en el resumen.

### Trabajo requerido

- Identificar y cuantificar por separado: localización del evento, umbral de presencia de fase, evaluación de derivadas a cada lado, reconstrucción del estado y cuadratura independiente del trabajo.
- Partir de dH/dt = Q + V dP/dt y dU/dt = Q − P dV/dt para el caso cerrado; para la red conservar todos los términos y transferencias compartidas. Una identidad algebraica usada para publicar W no sustituye la verificación independiente de su integración.
- Resolver de forma consistente el estado límite y la semántica del evento. Afinar la localización no puede perder los IDs de fases ni introducir cantidades artificiales para hacer visible una fase.
- No subir tolerancias, cambiar escalas para ocultar el error, reemplazar el auxiliar por la misma identidad que lo contrasta ni rebautizar `no_cumple` como `cumple`.
- Si el contrato no representa correctamente una fase límite de cantidad cero, documentar y proponer una ampliación aditiva con ejemplos antes de depender de ella. No relajar silenciosamente el lector ni inventar una fase presente.
- Mantener detención por política, último estado, motivo, evento y corte de certificación coherentes. No continuar la trayectoria prohibida ni borrar la muestra que descubre un incumplimiento.

### Pruebas de cierre

- Caso NRTL reproducido: certificado correcto con tolerancias actuales, evento identificado y trabajo independiente dentro de su límite. Controles ideal y las tres variantes UNIFAC dentro de sus dominios.
- Variar horizonte/intervalo de muestreo, potencia, escala de inventarios y tolerancias; publicar errores absolutos y escalados y su evolución al refinar. Un defecto de localización no debe quedar escondido por el muestreo.
- Aparición, desaparición y sustitución de fase donde sean admisibles, con política permitida/prohibida y cantidades incipientes; casos de enfriamiento además de calentamiento.
- Mantener presión suave, frontera rígida y redes con transferencias internas. No añadir saltos físicos que el contrato no soporte.
- Un control negativo debe seguir produciendo `no_cumple` cuando se corrompa deliberadamente la verificación de trabajo.

## R2. Candidatos fuera del dominio durante la búsqueda

Evidencia previa: `frontend/qa_integracion_unifac_2026_10_16/avisos-backend.txt`. Se observaron desbordamientos de `exp` en `core/mezclas.py` y divisiones/logaritmos inválidos en `core/unifac.py`. Los estados publicados pasaron el lector y sus certificados. **No está demostrado todavía** si todos los avisos corresponden a candidatos descartados.

### Trabajo requerido

- Reproducir por operación/paquete y guardar trazas con contexto suficiente para distinguir candidato exploratorio, estado aceptado e inicialización.
- Comprobar finitud y dominio antes de normalizar, dividir o tomar logaritmos; tratar ceros/trazas con límites matemáticos correctos. Evaluar una parametrización numéricamente estable cuando corresponda.
- Rechazar o retroceder ante candidatos inválidos de forma controlada. Si agota la búsqueda, devolver el diagnóstico estructurado apropiado con origen; no certificar un estado inválido.
- No aplicar supresión global de warnings, NaN→0, recortes arbitrarios de composiciones, sustitución de tablas ni relleno de interacciones ausentes. Un cero de interacción declarado es un dato, distinto de uno ausente.
- Un manejo local de error numérico solo es válido si descarta explícitamente el candidato, queda cubierto por prueba y conserva un diagnóstico cuando el cálculo no puede completarse.
- Contrastar ceros iniciales y especies entrantes, trazas, extremos puros, fases incipientes, LL/LLV y llamadas concurrentes con asignaciones distintas, según dominio publicado. Separar pruebas de candidatos forzadamente inválidos de pruebas físicas nominales.

## Entrega y aceptación

- Informe `docs/MOTOR_FIABILIDAD_EVENTOS_Y_DOMINIOS.md`: causa demostrada, solución general, error antes/después, límites pendientes y tiempos medidos.
- Casos originales regenerados desde endpoints en carpeta propia; no sobrescribir la evidencia inicial de Codex.
- Nuevas regresiones físicas y controles negativos; todas las suites del motor y verificadores TS pertinentes, incluido `npm run test:motor-fundamental`.
- Comparar ejemplos previos: series, eventos, residuos, certificados, huellas y diagnósticos. Justificar cada cambio físico; separar redondeo. No basta decir que la suite pasa.
- Documentar qué módulos históricos están afectados y ejecutar su regresión correspondiente. Enumerar lo ejecutado y lo no ejecutado.
- Contratos sin cambios si ya bastan; si cambian, publicar semántica, tipos y ejemplos canónicos para Codex. No modificar su copia desde Claude.
- Indicar reinicio necesario y comprobación de carga. La interfaz seguirá mostrando cualquier `no_cumple`; estas tareas no están cerradas por escribir este encargo.
