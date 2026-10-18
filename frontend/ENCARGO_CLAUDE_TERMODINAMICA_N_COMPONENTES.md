# Encargo para Claude · Termodinámica de N componentes y ensamblaje dinámico

**Estado histórico:** N0–N4 entregados e integrados con los tamaños y datos contrastados. Evidencia: [integración N](INTEGRACION_ENTREGA_N_COMPONENTES.md). La continuidad se mantiene en el [roadmap principal](ROADMAP_MOTOR_MULTIFISICO.md), sin volver a encargar estos hitos.

15 de octubre de 2026.

## 1. Objetivo y responsabilidad

Implementa y contrasta la ampliación del equilibrio de mezclas a más de tres componentes, y comprueba su uso dentro del ensamblaje dinámico de materia y energía de `/motor`.

El objetivo es ampliar el motor común. Los casos concretos son pruebas, nunca ramas del algoritmo por sustancia, equipo, nombre de hoja o número particular de componentes.

Trabaja en núcleo, backend, pruebas y documentación. No edites `frontend/`, `/laboratorio` ni el cambio ajeno de `thermodynamics/proveedor.py`. No hagas commit, push ni despliegue. Conserva los cambios existentes y no uses comandos para restaurar archivos ajenos.

Este documento encarga código, pruebas y entrega de integración. Completa N0 → N4 en orden, sin solicitar confirmaciones rutinarias entre hitos. Cuando un caso no sea físicamente identificable o falten parámetros, entrega el diagnóstico y la evidencia; no inventes la física para completar la tabla.

## 2. Punto de partida: no repetir entregas terminadas

- H1/H3: agua IAPWS-95 y estados TP, PH, UP y UV.
- Ensamblaje dinámico v1/v2: inventarios y energía integrados, presión calculada o prescrita, corrientes internas, contactos térmicos, extracciones por fase y eventos.
- M0–M6 y consolidación: mezclas ideales/NRTL, LL/LLV del paquete agua–butanol, potenciales, procedencia, certificación y catálogo de series.
- D0–D3/D5: diagramas binarios T–xy/P–xy, certificados, huecos y huellas de parámetros.
- D4 del frontend ya está integrado: contratos sincronizados, lector, vistas, marcadores compatibles, caché y exportación. No repetirlo ni dar por vigente el antiguo fallo de copia del contrato.

Lectura mínima:

1. `docs/MOTOR_EQUILIBRIO_MULTIFASICO.md`.
2. `docs/CONSOLIDACION_MULTIFASICA.md`.
3. `docs/MOTOR_ENSAMBLAJE_DINAMICO.md`.
4. `docs/MOTOR_DIAGRAMAS_EQUILIBRIO.md`.
5. `docs/contratos/contratoEnsamblajeV2.ts` y `docs/contratos/contratoDiagramasEquilibrio.ts`.
6. `frontend/INTEGRACION_DIAGRAMAS_EQUILIBRIO.md`, especialmente la preparación general por ID y sus límites físicos.

Límites confirmados al redactar este encargo:

- `core/mezclas.py`: `prueba_estabilidad` tiene caminos de una, dos y tres especies activas; para más rechaza. El refinamiento ternario usa `_softmax3`.
- `backend/motor_ensamblaje_v2.py`: `COMPONENTES_VERIFICADOS = 3`, aplicado por volumen, y `VOLUMENES_VERIFICADOS = 3`.
- `core/mezclas.py`: `MAX_FASES = 3`. El límite de fases es distinto del número de componentes.
- Los paquetes actuales tienen un catálogo finito y parámetros binarios incompletos. El paquete ajustado agua–butanol sigue siendo específico de ese par.
- El vapor de las mezclas actuales es ideal y su dominio llega hasta 5 bar. Esta entrega no cambia ese supuesto.

## 3. Alcance y restricciones

### Incluido

- Algoritmos de estabilidad y reparto con dimensión dependiente del catálogo activo.
- TP y su uso coherente en las inversiones PH/UP/UV y en TV cuando lo requiera la inicialización.
- Operación estática y dinámica para conjuntos mayores de tres especies que tengan todos los datos requeridos y un dominio común.
- Capacidades, presupuestos numéricos, diagnósticos, evidencia y compatibilidad.

### Excluido

- Nuevos modelos de vapor no ideal, altas presiones, región crítica, electrolitos o sólidos de mezclas.
- Reacciones, transferencia selectiva fuera de equilibrio, momento y nuevas dimensiones espaciales.
- Nuevas interfaces o gráficos. Los diagramas T–xy/P–xy siguen siendo cortes binarios.
- Aumentar el límite de volúmenes o prometer un número ilimitado de fases.
- Introducir paquetes o ajustar parámetros para fabricar un caso multicomponente favorable.

Arquitectura general no significa soporte ilimitado. Publica límites operativos y tamaños realmente contrastados, separados de la disponibilidad de datos y de la evidencia experimental.

## 4. N0 · Auditoría de dimensión, datos y contrato

Antes de cambiar el solver, deja documentado:

1. Dónde se distingue catálogo global, componentes de cada volumen y especies activas de cada estado.
2. Todas las dependencias de dimensión fija en estabilidad, reparto, inicialización, inversiones, residuos, series, eventos y adaptadores.
3. Las combinaciones mayores de tres especies que permiten los parámetros ya instalados. En NRTL verifica todos los pares y las direcciones exigidas por el modelo, incluidos alfa y su procedencia.
4. El dominio común y los límites de fases de cada paquete. No uses la unión de dominios para validar una mezcla cuya intersección está vacía.
5. Qué operaciones tienen solución identificable. UV de líquido incompresible no determina P: debe seguir diagnosticándose.
6. El contrato mínimo de capacidades y diagnóstico necesario para comunicar la ampliación.

Conserva las rutas actuales. Prefiere campos opcionales aditivos en los contratos canónicos de `docs/contratos/`; no cambies nombres, unidades ni semántica existente. Si hace falta un cambio incompatible, entrégalo explícitamente versionado, preservando revisiones anteriores.

Capacidades debe distinguir, sin contradecir los campos existentes:

- tamaño admitido y tamaño contrastado, especificando si se cuentan componentes declarados o activos y si el límite es por volumen;
- especies y pares disponibles;
- operaciones y conjuntos de fases admitidos;
- alcance y método de estabilidad;
- presupuesto y límites numéricos;
- nivel de evidencia por paquete/combinación.

No sustituyas `componentesMaximos` por un número grande arbitrario ni por un límite que otro endpoint no respete.

## 5. N1 · Estabilidad y reparto de dimensión general

### Fundamento

Para una mezcla no reactiva a T/P dados, el equilibrio minimiza G sujeto a:

```text
n_i = sum_alpha n_i^alpha
n_i^alpha >= 0
G = sum_alpha sum_i n_i^alpha mu_i^alpha
```

La igualdad de potencial químico se comprueba para componentes presentes en las fases coexistentes correspondientes. Las cantidades o fases ausentes se tratan con las condiciones de optimalidad pertinentes, no evaluando log(0) ni imponiendo una igualdad imposible.

La prueba de distancia al plano tangente debe seguir la misma referencia y el mismo paquete:

```text
TPD(w) = sum_i w_i [mu_i^prueba(T,P,w) - mu_i^referencia] / (R T)
w_i >= 0; sum_i w_i = 1
```

### Implementación requerida

- Parametrización y optimización de dimensión N−1, con tratamiento de vértices, caras y trazas. Una parametrización estrictamente interior no basta para justificar toda la búsqueda.
- Inicializaciones diversas y reproducibles, y estrategia para buscar fases competidoras. Si hay aleatoriedad, publica y fija la semilla en las pruebas.
- No escalar una malla tensorial exhaustiva sin justificar su coste. Elige y documenta una estrategia apropiada al crecimiento de dimensión.
- Conservar las especializaciones existentes solo si son optimizaciones equivalentes del mismo problema; contrastarlas con la ruta general donde ambas apliquen.
- Mantener separados convergencia local, satisfacción de restricciones y búsqueda de estabilidad. Un solver que devuelve éxito no certifica por sí solo el mínimo global.
- Declarar honestamente que una búsqueda finita multisemilla no demuestra un mínimo global. Publicar alcance, presupuesto y residuos; presupuesto agotado no significa estable.
- Retirar únicamente especies exactamente ausentes del problema activo cuando la reducción sea matemáticamente válida. Conservar sus IDs y cantidades cero en la respuesta. No convertir trazas positivas en ceros para pasar a un problema menor.
- Conservar cantidades originales, escalas por magnitud y residuos por componente. No ocultar errores pequeños respecto del total cuando son grandes para una especie traza.
- No recortar cantidades ni renormalizar una respuesta defectuosa para superar la certificación. Las restricciones del algoritmo y la comprobación de la respuesta deben ser independientes.
- No rellenar parámetros faltantes con cero ni sustituir silenciosamente NRTL por mezcla ideal.

Audita el tope de fases: si se encuentra una fase competidora que no cabe en el alcance admitido, diagnostica la limitación. No certifiques el estado actual como estable al alcanzar `MAX_FASES`. No es obligatorio habilitar más fases en esta entrega.

## 6. N2 · Inversiones y comprobaciones físicas estáticas

Propaga el equilibrio general a PH, UP, UV y TV sin implementar un flash distinto para cada ejemplo.

Verifica las restricciones originales tras cada inversión, incluyendo mesetas cuando existan. U/H, volumen y composición deben corresponder a un único reparto de fases. No resuelvas energía con una fracción y volumen con otra.

Pruebas mínimas:

| Grupo | Casos requeridos | Referencia o criterio |
|---|---|---|
| Mezcla ideal | 4 y 5 especies; mayor conjunto disponible con dominio común | Solver independiente de Raoult + Poynting y Rachford–Rice, donde corresponda |
| NRTL | Al menos un conjunto de 4 especies con parámetros completos, si existe | Otra implementación/solver contrastable, con iguales parámetros y referencia |
| Ausencias | Catálogo grande con especies exactamente cero; reducción equivalente | Mismo estado físico sin perder IDs |
| Trazas | Varias escalas de fracción e inventario | Residuo por especie y límites de precisión medidos |
| Permutaciones | Reordenar IDs y catálogo, manteniendo identidades | Mismo equilibrio y propiedades extensivas coherentes |
| Estabilidad | Semillas de fase y composiciones distintas; candidatos metastables | Recuperar el mismo mínimo encontrado o diagnosticar ambigüedad/falta de certificación |
| Inversiones | TP → PH/UP/UV → estado, cuando sea identificable | Restricciones originales y equilibrio; el viaje de ida/vuelta no es por sí solo referencia independiente |
| Negativos | Parámetro ausente, dominio vacío, presupuesto agotado y tope de fases | Rechazo estructurado, nunca un estado estable ficticio |

Si no existe ningún conjunto NRTL de cuatro especies con datos completos, documenta la búsqueda y el bloqueo exacto. No inventes coeficientes ni presentes una referencia ideal como validación NRTL. Los datos sintéticos pueden comprobar el algoritmo y casos negativos, identificados expresamente; no habilitan capacidad predictiva para sustancias reales.

Contrasta también identidades termodinámicas y derivadas pertinentes: Gibbs–Duhem, coherencia de G/H/S y entalpías parciales o de exceso. Usa comprobaciones independientes del camino que produce el resultado y escalas adecuadas cerca de cancelaciones. Mantén las referencias energéticas comunes.

Para cualquier literatura o dato adicional, usa fuentes primarias, conserva procedencia, condiciones y unidades. Separa evidencia experimental, contraste de formulación, referencia numérica independiente y coherencia interna. No llames validación predictiva a reproducir datos empleados en ajustar los parámetros.

## 7. N3 · Acoplamiento dinámico del mismo modelo

El coordinador conserva las cantidades y U/H; la termodinámica reconstruye el estado sin alterar cantidades ni caudales. Usa una sola trayectoria para los volúmenes conectados.

Casos mínimos con más de tres componentes admitidos por el paquete:

1. Volumen cerrado calentado, presión prescrita y transición LV: H(t)=H(0)+Q t cuando no haya otros aportes.
2. Recipiente rígido con al menos una fase que permita identificar la presión: U(t)=U(0)+Q t y V constante. No forzar una solución del líquido incompresible lleno.
3. Dos volúmenes conectados, con alimentación o extracción y un contacto térmico: cancelación exacta de términos internos en las ecuaciones globales.
4. Extracción por fase con cambio de composición global; fase ausente y evento terminal.
5. Cambio del conjunto de especies activas por alimentación: un componente inicialmente cero entra sin perder identidad ni recibir inventario ficticio.

En cada caso comprobar:

- conservación por especie y energía con integrales de los flujos de frontera;
- uso del donante correcto en cada corriente y ante inversión de signo;
- reconstrucción de inventarios por fase, masa, U/H/V y propiedades;
- dominio y certificación de cada muestra, con los mismos criterios del servicio puntual;
- estabilidad, igualdad de potenciales y persistencia de IDs de fase;
- sensibilidad a tolerancias, paso máximo y muestreo;
- instantes de eventos frente a una referencia independiente cuando sea posible;
- segunda ley cuando se dispone de las temperaturas de frontera necesarias; si no, `no_evaluable`.

No impongas de antemano temperatura, presión, título ni instante de ebullición para conseguir una trayectoria esperada. Respeta las restricciones realmente declaradas. No amplíes la afirmación de vigilancia de eventos a continua: la limitación actual debe seguir explícita si no se ha resuelto.

## 8. N4 · Contrato, rendimiento y regresión

### Compatibilidad

- Las peticiones y resultados históricos siguen siendo legibles. No hacen falta campos nuevos obligatorios para volver a resolverlos.
- Mantén la semántica de certificación, `no_evaluable`, residuos, unidades SI, catálogo de series y procedencia.
- Las huellas identifican modelo, datos, parámetros y referencias. No alterarlas por orden de componentes, nombres visuales o unidades equivalentes. Una modificación física se versiona y documenta; la configuración numérica se identifica por separado.
- Conserva los IDs históricos salvo un cambio justificado. Si un número publicado cambia, entrega el caso, antes/después, causa y evidencia; no regeneres ejemplos silenciosamente para hacer desaparecer una regresión.
- Revisa las capacidades y diagnósticos en servicio puntual y ensamblaje. Mantén separados los límites de diagramas binarios y de mezcla dinámica.

### Rendimiento

Mide el código anterior y el nuevo donde ambos apliquen, y casos nuevos de 4, 5 y el mayor conjunto disponible: una fase, LV y cercanía a fronteras. Publica tiempos, evaluaciones, convergencia, memoria relevante, semilla y tolerancias. Incluye trayectoria completa, no solo flash TP.

Establece un presupuesto acotado y una salida estructurada al agotarlo. Las semillas y cachés no deben saltarse la certificación ni reutilizar estados de otra composición, referencia o huella. Comprueba caché fría/caliente y entradas modificadas. No retires controles físicos para cumplir un tiempo de interfaz.

### Regresión requerida

- Nueva suite física dedicada, por ejemplo `tests/validar_motor_n_componentes.py`, y ejemplos reales generados desde endpoints.
- Suites existentes de H1, H3, ensamblaje v1/v2, consolidación y diagramas; batería histórica `tests/validar_*.py`.
- Verificadores de contratos TypeScript existentes y nuevos pares reales contra los tipos canónicos.
- `npm run test:motor-fundamental` en `frontend`, sin editar ni debilitar sus lectores o verificadores.
- Rechazos con código, propietario, componente y ruta identificables, incluidos los errores de forma; no un 422 genérico para fallos conocidos del contrato.

Si añades campos al contrato canónico y el único fallo del frontend es la comparación exacta con su copia anterior, identifica ese fallo por separado. Puedes contrastar la sincronización en una copia temporal aislada para demostrar la causa, sin editar el frontend compartido. Informa ambas ejecuciones: no declares verde la copia original hasta que Codex la sincronice.

Los ensayos actuales del frontend con 5, 8 y 12 componentes son comprobaciones algebraicas de lectura/reconstrucción. No contarlos como validación termodinámica de esta entrega.

## 9. Criterios de aceptación

- [ ] N0 identifica límites de dimensión, fases, parámetros y dominio antes de ampliar capacidades.
- [ ] Existe un camino de estabilidad y reparto de dimensión general; no se ha limitado el cambio a subir una constante.
- [ ] El paquete ideal resuelve y contrasta conjuntos reales de 4 y 5 componentes con dominio común.
- [ ] Se contrasta un conjunto NRTL de más de tres componentes o se acredita qué parámetros impiden hacerlo.
- [ ] PH/UP/UV y la inicialización usan la misma física, con rechazos cuando el problema no sea identificable.
- [ ] Los casos dinámicos de N3 conservan especie por especie y energía.
- [ ] Ausencias, trazas, permutaciones, escalado, semillas y controles negativos pasan con tolerancias justificadas.
- [ ] El tope de fases y el agotamiento de presupuesto nunca se publican como prueba de estabilidad.
- [ ] Capacidades y evidencia describen exactamente el soporte entregado.
- [ ] Regresión, contratos y ejemplos pasan sin debilitar pruebas existentes.
- [ ] La documentación permite integrar la ampliación sin cálculos termodinámicos en el frontend.

## 10. Entrega final para Codex y el usuario

Escribe `docs/MOTOR_TERMODINAMICA_N_COMPONENTES.md` con:

1. Estado de N0–N4 y cualquier subcaso bloqueado, sin declarar completo lo que no se haya contrastado.
2. Fundamento, método de estabilidad/reparto y tratamiento de fronteras del simplex.
3. Paquetes, conjuntos de especies probados, parámetros, dominios y límites operativos.
4. Evidencia separada por tipo de referencia, resultados cuantitativos y controles negativos.
5. Esquemas exactos de campos aditivos, códigos y guía de integración; actualizar los contratos canónicos cuando corresponda.
6. Benchmarks, tolerancias y limitaciones que permanecen.
7. Archivos tocados, comandos realmente ejecutados y códigos de salida.
8. Ejemplos generados desde endpoints y comparación con los anteriores.
9. Si hace falta reiniciar el servicio y qué capacidades nuevas deben verse después.

No marques el checklist del frontend como terminado. Codex actualizará sus elementos tras revisar esta entrega e integrar los ejemplos reales. La ampliación de N no equivale a haber implementado termodinámica universal, altas presiones o más fases.
