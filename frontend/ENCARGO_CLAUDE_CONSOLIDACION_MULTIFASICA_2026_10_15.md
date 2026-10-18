# Encargo para Claude: consolidar la entrega multifásica y preparar fronteras reales

15 de octubre de 2026. Encargo del usuario: aprovechar el trabajo en paralelo mientras Codex integra la revisión 2 en la interfaz. **Este es el siguiente encargo de backend; no repetir M0–M6.**

## 0. Coordinación y alcance

- Claude: backend, núcleo físico, pruebas de backend, ejemplos y documentación bajo `docs/`.
- Codex: frontend de `/motor`, adaptadores de hojas, lectores, gráficas y experiencia de usuario.
- No editar `frontend/app/`, los verificadores del frontend, `/laboratorio` ni el cambio ajeno de `thermodynamics/proveedor.py`. No hacer commit, push, checkout, reset ni limpieza de cambios ajenos.
- **Actualización de Codex del 15 de octubre:** los errores iniciales de tipado ya están corregidos. La integración pasa `tsc`, los verificadores y las cuatro hojas resueltas desde UI; la evidencia está en `frontend/INTEGRACION_MULTIFASICA_V2.md`. No modificar los lectores del frontend para acomodar una respuesta; documentar cualquier cambio de contrato. El rechazo de una fracción `1.0000000000000002` se corrigió en el lector con un margen de precisión de máquina, sin cambiar la respuesta del backend.
- `docs/contratos/contratoEnsamblajeV2.ts` es el contrato recibido. Preservar revisión 1 y 2. Una ampliación de metadatos debe ser opcional y aditiva; un cambio de significado necesita documentarse y versionarse explícitamente. No convertir una modificación del protocolo en una migración silenciosa.
- No implementar otra interfaz, un solver de navegador ni casos seleccionados por nombre de equipo.

## 1. Orden de trabajo y entregas

| Prioridad | Entrega | Acción |
| --- | --- | --- |
| C0 | Capacidades coherentes | Corregir y verificar contra implementación y ejemplos |
| C1 | Certificación física de la trayectoria | Separar cálculo realizado de comprobaciones físicas aprobadas |
| C2 | Metadatos de integración | Completar series y referencias de eventos sin alterar GL ni física |
| C3 | Robustez de equilibrio y red | Ampliar controles físicos independientes y negativos |
| C4 | Frontera abierta y gases no condensables | Entregar fundamento y borrador tipado; no implementar apresuradamente nueva física |

Completar C0–C3 con código y pruebas. Continuar con C4 como entrega de diseño revisable. No pedir confirmación rutinaria entre estos trabajos. Si algo no es viable, documentar exactamente qué dato o formulación falta; no inventarlo.

## 2. C0 — Inconsistencias confirmadas en capacidades

### C0.1: agua–butanol aparece como si fuera solución ideal

Reproducción:

```
GET /motor/ensamblajes/capacidades?revision=2
```

En `backend/motor_ensamblaje_v2.py`, `capacidades_v2()` publica la combinación LL/LLV con:

```
publicada: mid == "nrtl-chemsep"
```

Por ello `nrtl-lle-agua-butanol` sale con `publicada: false` y el motivo «la solución ideal no predice separación líquida», mientras la entrega M4 y el ejemplo de decantador demuestran precisamente LL/LLV con ese paquete. Lo comprobé también en el servicio local, no solo leyendo el archivo.

Corregir la matriz para cada paquete y añadir una prueba de coherencia que falle si un ejemplo de una combinación ejecutada contradice sus capacidades. Distinguir alcance del algoritmo, calidad de parámetros VLE/LLE y dominio del ajuste; no anunciar el mismo nivel de evidencia para todos los binarios NRTL.

### C0.2: hielo estático frente a dinámico

En la entrada de `agua-iapws95`, el texto «M5 pendiente: modelo del hielo no integrado» ya es ambiguo/desactualizado. El paquete `agua-iapws95-hielo-ih` sí existe como estático; lo pendiente es su uso dinámico y no debe aparecer como habilitado en los volúmenes.

Verificar la coherencia entre capacidades puntuales, capacidades del ensamblaje y `noSoportado`. Mantener explícitos los límites de vapor ideal de mezclas (5 bar), hielo Ih, zona crítica, especies y pares con datos. Reiniciar el servicio propio si hace falta y comprobar las rutas reales; no terminar procesos de pruebas de otro colaborador.

## 3. C1 — «Resuelto» no debe confundirse con «físicamente certificado»

### Incidencia adicional confirmada durante integración: base de G/A/S

`PotencialesV2` declara `base: molar`, `unidad: J/mol`, pero los valores G/A/S publicados en la red son extensivos (totales). En `motor-ensamblaje-v2-resolver-contacto-dos-aguas`, volumen A, muestra 0, G = -415051.114194, mientras `(h-Ts)*Mmezcla = -747.725706 J/mol`. El cociente es el número de moles de los 10 kg de agua. En el binario acoplado la primera muestra coincide porque N=1 mol; al salir materia, G publicado cambia con N y deja de coincidir con la base molar. Igual para A y S. Corregir contrato/serialización o la base publicada, preservando las propiedades físicas; documentar expresamente unidades de S (J/K total o J/(mol K) molar). El frontend detecta la incoherencia y no presentará esos tres valores como molares hasta que el backend lo resuelva; no dividirá números por su cuenta para maquillar el protocolo. Los μ por especie/fase se tratan por separado.

### Evidencia que requiere una decisión de contrato

Al final de `resolver_v2` se publican residuos y segunda ley, pero el estado superior depende de si la integración se detuvo:

```
estado = parcial si detenida; en otro caso resuelto
```

La prueba de transferencia corrupta de `tests/validar_motor_ensamblaje_v2.py` detecta un residuo global por encima de tolerancia. El resultado puede seguir llevando `resuelto`. Lo mismo necesita aclararse cuando `segundaLey.estado == "no_cumple"`.

Esto no demuestra un error en las ecuaciones nominales; es una ambigüedad entre éxito numérico y certificación física que la interfaz no debe resolver por su cuenta.

### Resultado requerido

1. Mantener separados el resultado numérico, la validez del estado termodinámico, la conservación y la segunda ley.
2. Definir y publicar una certificación global explícita, por ejemplo un campo **opcional y aditivo** con estado `cumple | no_cumple | no_evaluable`, motivos y referencias a residuos/verificaciones. Documentar el esquema exacto antes de usarlo en ejemplos. No renombrar campos existentes por conveniencia.
3. Un incumplimiento comprobado de conservación o estado no puede quedar presentado como trayectoria físicamente válida. Conservar evidencia para diagnóstico sin concederle certificación.
4. Una segunda ley no evaluable por falta de temperatura de frontera no equivale a cumplirla ni invalida automáticamente un balance de energía bien planteado. Si existe un incumplimiento, debe aparecer como tal en la certificación y los diagnósticos.
5. Si se decide cortar antes del primer incumplimiento, definir con precisión el estado parcial, la última muestra admisible y la evidencia descartada. No borrar silenciosamente una muestra y seguir usando los residuos de otra trayectoria.
6. Conservar los ejemplos nominales válidos y los resultados físicos anteriores; no relajar tolerancias para obtener un estado aprobado.

### Pruebas mínimas

- Red cerrada nominal: materia y energía globales correctas, segunda ley evaluable y correcta cuando corresponde.
- Transferencia de materia corrupta: detectada y certificación global no aprobada.
- Transferencia energética corrupta: detectada y certificación global no aprobada.
- Calor entrante desde una frontera más fría, sin trabajo que lo justifique: segunda ley no cumplida, no certificación global aprobada.
- Temperatura de frontera ausente: `no_evaluable`, sin T inventada ni sustitución por T del contenido.
- Comprobar también unidades y escala de residuos al variar órdenes de magnitud de energía y cantidad de materia.

## 4. C2 — Series, eventos y sus propietarios

### C2.1: catálogo de series publicadas

En el ejemplo `motor-ensamblaje-v2-resolver-binario-acoplado`, aparecen series como `volumen.A.masa`, `volumen.A.S` y `red.Sgen` que no están necesariamente descritas en `validacion.variables` con su magnitud y procedencia.

La interfaz necesita distinguir estados integrados, variables algebraicas y magnitudes derivadas para mostrar unidades y vínculos correctos. Auditar **todas** las series de los ejemplos.

Propuesta mínima: ampliar metadatos de forma aditiva (por ejemplo un `catalogoSeries`), con ID, propietario, unidad SI, magnitud, papel y procedencia. Puede aprovecharse el catálogo existente si hacerlo no altera el significado del recuento. **No sumar una ecuación o un grado de libertad por cada magnitud de presentación.**

La interfaz no necesita otro catálogo químico duplicado ni fórmulas interpretadas desde LaTeX. Cada ID debe apuntar a una fuente única y estable.

### C2.2: eventos sin IDs de fase

La construcción actual de eventos v2 publica `faseIds: []` para todos los eventos. El campo está tipado, pero no permite identificar qué fase apareció o desapareció.

Para eventos de fase, publicar IDs reales y estables del volumen afectado. Si hace falta distinguir antes/después, añadir campos opcionales con ambos conjuntos. Para un evento sin fase asociada (dominio, agotamiento global, etc.), el array vacío sigue siendo correcto con su motivo.

Mantener la identidad de los dos líquidos por continuidad, no por orden de densidad de la muestra. Añadir pruebas de aparición, desaparición, extracción de una de dos fases líquidas y reordenamiento de densidades. Una fase ausente no tiene composición definida; no publicar composiciones cero como si fueran un estado físico.

### C2.3: clasificación supercrítica

Revisar que un `cambio_denominacion` a `fluido` no se describa como evaporación/condensación o transición de primer orden. Conservar la separación entre tipo de fase, régimen y fracción de fase. No cambiar las propiedades para suavizar la etiqueta.

No se pide modificar el frontend ni diseñar cómo se dibuja la curva: Codex se encarga de esa representación.

## 5. C3 — Consolidación física, sin crear escenarios especiales

No basta con aumentar el número de asserts sobre las mismas fixtures. Añadir contrastes que puedan descubrir errores en el ensamblaje y en el cierre:

1. **Referencias:** invariancia ante desplazamientos coherentes de referencias por especie donde la formulación lo permite. No mezclar IAPWS y referencia gas ideal sin una transformación explícita.
2. **Mezcla y energía:** contrastar el calor de mezcla y sus derivadas con una vía independiente de la función que usa el RHS; verificar también términos composicionales, no solo Cp a composición fija.
3. **Estabilidad:** controles negativos con estados homogéneos inestables/metastables; distintas semillas y búsqueda de fases candidatas. Publicar el alcance numérico explorado. Una malla/refinamiento del plano tangente no es una demostración universal del mínimo global.
4. **Mesetas:** cierres PH/UV en LLV, puntos próximos a burbuja/rocío y límites de cantidad de fase, con reconstrucción de cada componente, energía y volumen.
5. **Red:** invertir corrientes y conectar volúmenes con distinta composición/temperatura; una sola transferencia energética y material con signos opuestos. Dos líquidos no pueden extraerse mediante un índice accidental del optimizador.
6. **Convergencia:** repetir una selección representativa con paso máximo y tolerancias distintos, y comparar trayectoria y tiempos de eventos. Mantener explícito el límite de vigilancia puntual; no llamarla continua.
7. **Límites:** modelo/par binario ausente, presión fuera del dominio de mezclas, presión indeterminada de líquido incompresible, fase ausente, hielo dinámico no admitido y estado inicial incompatible.

Si una sonda revela un defecto, dejar reproducción mínima y corregirlo con regresión específica. Conservar resultados previos e informar qué números cambiaron y por qué. No ocultar diferencias regenerando fixtures sin compararlas.

## 6. C4 — Diseño de frontera abierta: agua + aire y caudal desconocido

**Esta parte es diseño y auditoría de viabilidad, no autorización para introducir deprisa una EOS, una válvula o un modelo de reactor completo.** Entregar un documento separado bajo `docs/`, con fundamento, esquema tipado propuesto, datos necesarios y plan de pruebas.

Motivo: el contrato anterior contiene una aceptación de agua con aire y una salida calculada que M0–M6 no cubre. Ver `frontend/PRUEBAS_OLLAS_SIN_RESULTADO_IMPUESTO.md`. La versión actual de las hojas fue cambiada expresamente por el usuario a agua pura; los casos agua–aire de ese documento son ahora una ampliación futura, no la composición de la hoja actual.

### Preguntas que debe resolver el diseño

- ¿Qué paquete coherente representa agua condensable y gases no condensables N2/O2, sin extrapolar correlaciones de líquido de N2/O2 a 300 K? Declarar disolución despreciada u otro tratamiento y su dominio.
- ¿Qué potenciales/referencias aportan energía, entropía, volumen y potencial químico de cada especie/fase? No sumar una presión parcial de aire sobre un flash de agua pura sin revisar todas las relaciones.
- ¿Cómo se inicializa desde T0, P0 total, V geométrico, cantidad de agua y proporción de aire seco, calculando el aire y el reparto de agua sin duplicar cantidades ni sobredeterminar U/T/P/V?
- ¿Cómo se admite un caudal de salida como incógnita del MISMO ensamblaje, en lugar de dato obligado? No reintroducir F=kN ni otro coeficiente para producir un resultado.
- En una frontera ideal abierta a la atmósfera: V fijo + P ambiente + salida desconocida. Formular balances por componente y U con entalpía de la fase gaseosa donante; no añadir calor latente dos veces. Determinar si hace falta DAE, reducción ODE o cambio de régimen y cómo se inicializa consistentemente.
- En el caso hermético: misma mezcla, V fijo, ninguna salida; P calculada. El límite de resistencia del equipo es distinto del dominio de la EOS.
- Para una descarga real futura: distinguir presión prescrita ideal de una ley de transporte con conductancia/capacidad y contrapresión. Una válvula no garantiza P exactamente constante. No se encarga aquí dimensionarla ni simular roturas.

Caso de diseño de referencia, sin solución objetivo: 3 L totales, 2 kg de agua total, 10 °C, 1 atm inicial, 79/21 molar N2/O2 secos, calor neto constante declarado. Comparar cierre hermético y frontera abierta. No elegir tiempo, masa, volumen o caudal para forzar una temperatura o fracción final.

También documentar por qué agua pura líquido/vapor a 10 °C con espacio gaseoso **no** tiene presión inicial de 1 atm: no usar ese estado incompatible como atajo del caso abierto. Si se propone un dominio solo del líquido con superficie libre, declarar que es otra elección de volumen de control.

## 7. Entregable final para Codex

- Resumen C0–C4: implementado / solo diseño / pendiente, con rutas y revisión reales.
- Tipos y campos aditivos exactos, ejemplos de solicitudes/respuestas generados por endpoints.
- Resultado de las pruebas, diferencias de fixtures y controles negativos; no afirmar regresión frontend completa mientras la integración concurrente siga sin terminar.
- Lista de archivos tocados y confirmación de que no se modificó el frontend, `/laboratorio` ni `thermodynamics/proveedor.py`.
- Incidencias restantes y sus reproducciones, especialmente lo que no puede certificar el algoritmo.

El objetivo inmediato es que Codex pueda integrar v2 sin inventar capacidades, certificaciones, nombres físicos ni relaciones de cierre en el cliente.
