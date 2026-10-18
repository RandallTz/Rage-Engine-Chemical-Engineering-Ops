# Integración multifásica del motor · 15 de octubre de 2026

Actualización posterior: C0–C3 ya se integraron. Ver `INTEGRACION_CONSOLIDACION_MULTIFASICA.md`. Los pendientes de metadatos enumerados al final de este informe describen el estado de la entrega inicial y quedan resueltos por esa consolidación; C4 sigue como diseño.

## Alcance entregado

Las hojas de `/motor` pueden adoptar explícitamente el ensamblaje v2 de Claude: catálogo compartido de componentes, varios volúmenes, corrientes internas o exteriores, extracción por fase y contactos térmicos. Se usan las rutas reales `/motor/ensamblajes/{capacidades,validar,resolver}`. No se implementan flashes ni otro integrador en el navegador.

Las hojas anteriores siguen por su ruta v1. En Estado, **Crear copia para mezclas y volúmenes acoplados** genera otra hoja; conserva la original, sus datos y sus resultados. El cierre manual `u_lineal` no se sustituye silenciosamente: la copia muestra una acción explícita para adoptar el paquete. Una restricción o hipótesis no admitida conserva el diagnóstico del backend.

No se modificaron `/laboratorio`, el backend ni el núcleo físico en esta integración. No hay commit ni push.

## Documento físico y responsabilidades

`HojaMotor.redTermodinamica.solicitud` es el documento físico único de una hoja v2. Los nombres de presentación están aparte, en `nombres`. Las formulaciones y el historial anteriores se conservan como archivo; no aportan un segundo conjunto de valores a una ejecución v2.

- `contratoEnsamblajeV2.ts`: copia del contrato recibido de Claude, con importaciones locales.
- `redTermodinamica.ts`: copia optativa, edición, datos con propietario/ruta, retirada de referencias huérfanas e hipótesis mecánicas coherentes con la frontera elegida.
- `servicioEnsamblajeV2.ts`: transporte y cancelación de espera.
- `lectorEnsamblajeV2.ts`: identidad, recuento, iniciales, unidades de series, muestras, reconstrucción de materia/U/V/H/S, certificados y residuos. Reutiliza el lector puntual. Estas comprobaciones de protocolo no sustituyen una referencia física independiente del proveedor.
- `EspacioRedTermodinamica.tsx`: configuración, ecuaciones y datos; una sección seleccionada a la vez.
- `resultadoEnsamblajeV2.ts`: adaptación de la respuesta original y series de presentación por ID de fase.
- `DetallesRedTermodinamica.tsx`: estados por muestra y volumen, composición por fase, potenciales, estabilidad, eventos y ecuaciones ejecutadas.

La firma física excluye el identificador de petición, la derivación archivada y los nombres de presentación. Editar materia, geometría, frontera, política o datos invalida el resultado; renombrar un elemento conserva la trayectoria. La firma se vuelve a comprobar al recibir y al guardar una respuesta, para descartar ejecuciones que correspondan a una edición anterior.

## Uso

1. **Estado:** componentes/CAS, paquete por volumen, frontera rígida o presión prescrita, cantidades iniciales, políticas de fases, corrientes y calor. Agregar un volumen deja sus datos sin valor; no crea entradas/salidas ni rellena ceros.
2. **Ecuaciones:** LaTeX y procedencia publicados por el ensamblaje del backend, agrupados por propietario. No se deducen ecuaciones leyendo textos o etiquetas de equipos.
3. **Resolver:** datos con unidad, pestaña por volumen/corriente/contacto y recuento del backend en la esquina. Incluye variables, ecuaciones, datos definidos, datos pendientes, GL estructurales e iniciales pendientes. No se calcula GL contando campos vacíos en el frontend.
4. **Gráficos:** tablero existente, con temperatura y presión de los volúmenes; fracciones de cada fase; composición y propiedades específicas por fase disponibles en el selector de variables. Tabla y CSV incluyen estas series.

Las fracciones molar, másica y volumétrica se publican separadas. Dos líquidos mantienen IDs distintos. Una fase ausente tiene fracción cero en su serie de presentación, pero su composición y propiedades quedan ausentes, no se rellenan con cero. Las series originales y certificados no se transforman ni sobrescriben. Los ejes de fracciones/composición de fase van de 0 a 1.

Los datos de caudal son datos de frontera en el alcance temporal actual del backend. Esta integración no anuncia que pueda resolver caudales desconocidos o cualquier problema inverso. El análisis estructural tampoco se presenta como un rango numérico.

## Hojas preparadas y comprobadas desde el navegador

En Hojas → **Añadir pruebas multifásicas**. Solo se añaden IDs ausentes; no se sobrescribe una hoja ya editada.

| Hoja | Ensamblaje | Comprobación visible |
| --- | --- | --- |
| `motor-multifasico-v2-1` | Etanol–agua calentado, presión prescrita | 9 muestras, líquido → vapor, dos eventos, T final 396.325 K |
| `motor-multifasico-v2-2` | Dos volúmenes rígidos de agua con contacto térmico | 6 muestras por volumen, T/P y fases de ambos |
| `motor-multifasico-v2-3` | Dos mezclas, corriente interna y contacto térmico | 5 muestras por volumen, conservación global de especies y entalpía |
| `motor-multifasico-v2-4` | Agua–butanol, extracción del líquido de menor densidad | 5 muestras; dos líquidos con composición y fracciones distintas |

Son solicitudes de ejemplo, no ramas especiales del solver. Todas se editan y ejecutan con el mismo contrato.

En el decantador, la muestra final publica fracciones másicas 0.3530911 y 0.6469089. Las fracciones molares son 0.5664459 y 0.4335541; las volumétricas, 0.317776 y 0.682224. Se añadió desde la UI una gráfica de la composición de butanol de ambos líquidos y se comprobó el orden del tablero después de recargar.

Recorridos adicionales:

- Borrar T inicial en el contacto térmico: Falta 1, Iniciales pendientes 1, Resolver deshabilitado. Restaurarla permite resolver.
- Agregar un tercer volumen: cantidades, temperatura y presión vacías. Retirarlo y agregar/retirar un componente deja de nuevo la red lista; no quedan datos de los elementos eliminados.
- Después de resolver el binario, cambiar el caudal de 0.001 a 0.002 mol/s: las gráficas anteriores dejan de mostrarse inmediatamente. El sistema vuelve a validar y resolver con otro `modeloId`. Se conservó esa respuesta y después se restauró el caudal original.
- Recargar resultados recupera la trayectoria desde IndexedDB y la vuelve a validar.

## Corrección de lectura encontrada en una edición real

Con el caudal editado, la respuesta original incluye una fracción másica `1.0000000000000002`. El límite exacto `<= 1` del lector puntual rechazaba toda la trayectoria. Se admite ahora solo un margen de ocho épsilon de máquina por encima de 1; no se recorta ni modifica el valor. La suma de fracciones y las reconstrucciones siguen comprobándose. Un exceso de `1e-8` sigue siendo rechazado.

La petición/respuesta HTTP y la ejecución posterior desde UI están en `qa_multifasico_2026_10_15/binario-editado-*`. La regresión verifica el valor original, la aceptación del redondeo y el rechazo de una desviación mayor.

## Verificación reproducible

Desde `frontend/`:

```
npx tsc --noEmit
npm test
npm run test:motor-fundamental
npm run test:multifasico -- --ui
```

Desde la raíz:

```
node tests/verificar_contrato_ensamblaje_v2.mjs
```

El verificador multifásico cubre respuestas reales, IDs, bases, composición, persistencia, datos corruptos, copias, firmas y la edición con redondeo. Con `--ui`, además lee las cuatro respuestas exportadas desde el panel visible de la interfaz y contrasta conservación global de especies y primera ley donde se dispone de una referencia directa: U global en recipientes rígidos, H global con presión constante y calor impuesto. No llama al solver ni al paquete termodinámico para obtener esas referencias.

Las cuatro ejecuciones originales suman 25 instantes y 36 estados de volumen; la suite ampliada pasa 504 comprobaciones. La evidencia de UI y los certificados originales se conservan en `qa_multifasico_2026_10_15/`.

## Límites y seguimiento de Claude

El encargo está en `ENCARGO_CLAUDE_CONSOLIDACION_MULTIFASICA_2026_10_15.md`. Al integrar se observaron:

- Capacidades LL/LLV incoherentes para el paquete específico agua–butanol.
- G/A/S etiquetados como molares aunque algunos valores son extensivos. La UI no los presenta con unidades molares cuando no reconstruyen esa base; conserva los originales. μ se trata aparte.
- Necesidad de separar finalización del cálculo de certificación física global. El lector rechaza residuos fuera de tolerancia; si el backend publica segunda ley `no_cumple`, se muestra un aviso visible de trayectoria sin certificar.
- Catálogo de series derivadas y referencias de eventos por completar.

Claude está consolidando esos puntos. No se normalizan respuestas ni se fabrican certificados para ocultarlos. Las correcciones nuevas de contrato se incorporarán cuando su entrega esté cerrada.

Esta entrega no añade una pantalla de diagramas P–T del hielo ni habilita hielo dinámico, aire–agua, válvulas o caudales de venteo calculados. Tampoco elimina los límites físicos de los paquetes ni transforma v2 en un solver universal de PDE/DAE.
