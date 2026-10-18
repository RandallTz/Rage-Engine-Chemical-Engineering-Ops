# Plan de implementación: diagramas de equilibrio del motor

**Referencia de aceptación de la entrega de diagramas.** Para estado y continuidad consultar el [roadmap principal](ROADMAP_MOTOR_MULTIFISICO.md); este documento no abre otra fase ni altera el orden del trabajo actual.

Fecha: 15 de octubre de 2026. Estado: **plan de referencia; implementación iniciada y seguida en [INTEGRACION_DIAGRAMAS_EQUILIBRIO.md](INTEGRACION_DIAGRAMAS_EQUILIBRIO.md)**.

Este documento conserva el alcance del trazado en backend y su integración en `/motor`. El usuario pidió planificar la implementación y posteriormente autorizó comenzar, conservando la generalidad del motor. No se encarga modificar `/laboratorio`, reemplazar el solver dinámico ni comenzar otro modelo termodinámico para generar las gráficas.

## 1. Objetivo y límites de esta entrega

Generar diagramas binarios **T–xy a presión fija** y **P–xy a temperatura fija**, usando exactamente el paquete, parámetros, referencias y criterio de estabilidad que evalúan los estados de una hoja. Permitir mostrarlos juntos y situar sobre ellos el estado de una muestra de la simulación.

El trazador será una operación de la capa termodinámica, utilizable también sin una simulación previa. Su entrada no debe requerir tanque, fuente de calor, masa inicial, tiempo de simulación ni identificador de ejemplo. La hoja únicamente suministra el contexto y los marcadores.

Alcance inicial:

- Dos componentes, intercambiables por ID, dentro de las capacidades reales del paquete elegido.
- Coexistencia líquido–vapor estable, ramas y límites de burbuja/rocío.
- Identificación y tratamiento de azeótropos dentro del alcance numérico certificado.
- Detección de competencia de otras fases y representación explícita de las interrupciones que produzcan.
- Dos cortes independientes, con condiciones tomadas de una muestra o declaradas manualmente.
- Ejes de composición en fracción **molar**, con unidades de temperatura y presión seleccionables en presentación.

Quedan para entregas posteriores: superficies 3D, cortes multicomponente, diagramas ternarios, trazado completo de regiones LL/LLV/SLE, región crítica excluida por los paquetes actuales y selección automática de otro paquete. Detectar una región LL/LLV y explicar por qué interrumpe un trazado LV **sí** pertenece a esta entrega; resolver y dibujar su diagrama completo, no.

La limitación binaria es una capacidad declarada del trazador inicial, no una restricción nueva del ensamblaje de materia y energía. Una hoja con tres componentes sigue funcionando como antes. No se elimina ni renormaliza el tercero para aparentar un binario; un sistema de dos componentes distinto requeriría una solicitud independiente y explícita.

## 2. Principios para no sesgar el motor

1. Ninguna rama del algoritmo se selecciona por nombre de hoja, tanque, ejemplo o pareja de sustancias. El trazador se configura con componentes, paquete y corte.
2. Los CAS y parámetros específicos pertenecen a los adaptadores de propiedades. Los casos etanol–agua, benceno–tolueno u otros solo pertenecen al catálogo y a las pruebas.
3. No se añade una segunda implementación de NRTL, Raoult, presiones de vapor, fugacidades o estabilidad en el frontend ni en un módulo de dibujo.
4. No se usa otro proveedor de equilibrio para construir el diagrama de un paquete existente. Un proveedor externo puede servir de contraste independiente en pruebas, con sus diferencias declaradas.
5. El diagrama no modifica hipótesis, cantidades, caudales, restricciones mecánicas ni grados de libertad de la simulación. Sus condiciones de corte son consultas, no especificaciones del modelo dinámico.
6. Un cambio de paquete es explícito y vuelve a validar su dominio y datos. No se cae silenciosamente a mezcla ideal cuando NRTL falla o faltan parámetros.
7. Convergencia, verificación termodinámica, cobertura numérica y evidencia experimental son conceptos separados. Una curva suave no demuestra ninguno de los otros tres.
8. Cada resultado conserva identidad de modelo, datos y método. Una curva calculada con datos anteriores no se presenta como correspondiente al paquete actual.

## 3. Fundamento físico y significado de los diagramas

Para dos fases de una mezcla no reactiva en equilibrio:

```text
T^L = T^V
P^L = P^V
mu_i^L(T,P,x) = mu_i^V(T,P,y), para cada especie presente
sum_i x_i = sum_i y_i = 1
0 <= x_i,y_i <= 1
```

La igualdad de potenciales químicos —o la de fugacidades de forma equivalente— define candidatos. La prueba de estabilidad determina si la coexistencia publicada es admisible frente a las fases competidoras que el paquete sabe evaluar. Una raíz metastable no se publica como equilibrio estable.

En un binario no reactivo con dos fases, la regla de las fases da dos grados de libertad intensivos. Fijar P deja una curva parametrizable por composición; fijar T deja otra. Fijar simultáneamente T y P determina, en el caso regular, las composiciones coexistentes. La composición global determina entonces el reparto de cantidades, mientras ambas fases estén presentes.

En T–xy, cada punto de coexistencia proporciona **una T, un x y un y a la misma P**. Su proyección `(x,T)` forma la rama de burbuja y `(y,T)` la de rocío. En P–xy se usan `(x,P)` y `(y,P)` a la misma T. Mantener vinculados ambos extremos de cada punto evita emparejar curvas de raíces distintas.

Distinguir siempre:

| Símbolo | Significado | Uso |
|---|---|---|
| `z_i` | Composición global del sistema | Estado de la simulación y regla de la palanca |
| `x_i` | Composición molar del líquido | Eje de composición de la rama líquida |
| `y_i` | Composición molar del vapor | Eje de composición de la rama de vapor |
| `beta` | Fracción molar de vapor del sistema | Cantidades relativas de fases; no es `y_i` |
| `theta_i^alpha` | Fracción del componente i situada en la fase alpha | Gráficas de reparto existentes; no es `x_i` ni `y_i` |

Para una muestra LV compatible: `z_i = (1-beta)x_i + beta y_i`. Cerca de un azeótropo `x≈y`, no dividir por `y-x` para deducir beta: usar las cantidades/facciones de fase que ya publica el estado.

### Fases incipientes: representación propia

Burbuja y rocío son límites donde una fase tiene cantidad tendiendo a cero, pero su composición límite puede estar bien definida. El contrato actual de estados elimina fases ausentes y valida fracciones de fases presentes estrictamente positivas.

Por eso el trazador debe devolver **fases límite de coexistencia**, con composición y certificado, sin inventar una fracción positiva para hacerlas pasar por un `EvaluacionEstado` ordinario. No debilitar el lector actual para admitir fases ficticias de cantidad cero. Tampoco atribuir beta=0.5 a todos los puntos del diagrama: el corte no necesita fijar el reparto.

## 4. Separación de responsabilidades

| Parte | Responsabilidad | Información que no debe modificar |
|---|---|---|
| Paquete termodinámico | Potenciales/fugacidades, propiedades, derivadas, dominio, parámetros, referencias, estabilidad y límites puros disponibles | Cantidades conservadas y datos dinámicos |
| Trazador de equilibrio | Resolver y continuar la coexistencia bajo un corte; construir ramas, puntos y diagnósticos; llamar a la certificación del paquete | Ecuaciones físicas del paquete y leyes de equipos |
| Ensamblador/resolutor dinámico | Conservación, restricciones y evolución; publicar los estados de cada muestra | Resultados del trazado y condiciones elegidas solo para visualizar |
| Servicio HTTP | Validar entradas/unidades, fijar identidad, controlar presupuesto, serializar resultados | Corregir composiciones o rellenar parámetros ausentes |
| Frontend | Selección de contexto, lectura estricta, conversión visual, dibujo, marcadores, caché y persistencia de preferencias | Resolver flashes, detectar fases mediante reglas de dibujo o alterar certificados |

El trazador debe usar operaciones públicas o compartidas del paquete. Si faltan funciones de coexistencia o certificación de fases límite, Claude debe extraer la mínima interfaz compartida y comprobar regresiones. Evitar que el trazador copie fórmulas privadas o que el integrador pase a depender del trazador de diagramas.

La consulta determina equilibrio estable dentro del alcance del paquete, incluyendo sus fases competidoras. Una hipótesis de la hoja que prohíbe el cambio de fase no debe eliminar una fase estable del diagrama para hacerlo coincidir con la trayectoria: esa política puede detener la simulación y se muestra aparte.

La interfaz interna debe permitir futuros adaptadores basados en actividad o ecuaciones de estado. No exigir a todos los paquetes que posean `gamma`, `Psat` o una correlación de líquido incompresible: esas son capacidades del adaptador, no el fundamento universal del equilibrio.

## 5. Propuesta de contrato backend/frontend

Congelar el esquema compartido en el primer hito, antes de implementar la vista. El esquema siguiente expresa los campos y su semántica mínima; todavía no es una API desplegada.

### 5.1 Rutas propuestas y compatibilidad

- `GET /motor/termodinamica/diagramas/capacidades`: operaciones de trazado, paquetes y límites.
- `POST /motor/termodinamica/diagramas/trazar`: un corte por petición. El frontend puede pedir T–xy y P–xy en paralelo sin obligar a que ambos tengan éxito.
- Mantener intacta la ruta existente `GET /motor/termodinamica/diagrama`, dedicada al P–T del modelo de agua con hielo.
- Protocolo nuevo de diagramas con `revision: 1`; no incrementar la revisión del ensamblaje ni cambiar su semántica para habilitar una consulta independiente.

La capacidad debe discriminar por paquete/versión, operación, número de componentes, fases, dominio, combinaciones y evidencia. Tener un flash TP no significa automáticamente tener un trazado completo disponible.

### 5.2 Solicitud mínima

```ts
type CorteEquilibrio =
  | {tipo: 'Txy'; P: CantidadEstado}
  | {tipo: 'Pxy'; T: CantidadEstado};

type SolicitudDiagrama = {
  revision: 1;
  solicitudId: string;
  componentes: Componente[]; // exactamente dos, identidades verificables
  modelo: ModeloEstado;    // misma identidad que el volumen consultado
  huellaModeloEsperada?: string; // precondición cuando se compara con un resultado
  componenteEjeId: number; // debe pertenecer al par
  corte: CorteEquilibrio;
  intervaloComposicion: [number, number]; // molar, incluido en [0,1]
  resolucion: 'exploratoria' | 'refinada';
};
```

Reutilizar los tipos de identidad, unidades y componentes ya existentes. La ausencia de T/P no significa cero. Validar unidades compatibles, límites ordenados, valores finitos, IDs únicos, exactamente dos componentes y parámetros disponibles.

Los perfiles de resolución deben publicarse en capacidades con sus tolerancias, límites y presupuesto. Exploratoria/refinada cambian principalmente la densidad y el refinamiento del trazado; ambos deben verificar el equilibrio y la estabilidad de cada punto. No permitir que el frontend elija tolerancias arbitrarias que produzcan un certificado engañoso. Puede haber opciones avanzadas más adelante, sin convertirlas en una condición para utilizar la vista.

El contexto visual —hoja, volumen e instante— permanece en el frontend. Si se añade una referencia de correlación a la petición para trazabilidad, no altera la física ni la clave de caché.

### 5.3 Respuesta mínima

Debe contener, al menos:

| Campo | Contenido y regla |
|---|---|
| Identidad | Revisión, solicitudId, modelo y versión, huella de datos/parámetros y firma de la consulta normalizada |
| Condición | Corte solicitado intacto y normalizado a SI; componentes y componente del eje |
| Estado numérico | `completo`, `parcial`, `incompleto`, `invalido`, `no_soportado` o `no_convergente`, definido sin confundir cobertura con certificación |
| Ramas | IDs propios de esta consulta; tipo LV, segmentos conectados y referencias a puntos, sin saltos implícitos entre segmentos |
| Puntos de coexistencia | ID, T [K], P [Pa], fases límite L/V con composiciones molares por ID y referencias a certificados |
| Certificación de puntos | Residuos, escalas, tolerancias, estabilidad, alcance y motivo de lo no evaluable |
| Puntos especiales | Extremos puros, candidatos/azeótropos refinados, límites de dominio y encuentros con otras fases, con tipo y evidencia |
| Incidencias | Intentos fallidos, intervalo/ubicación, causa, referencias y acción del algoritmo; sin sustituirlos por un punto fabricado |
| Cobertura | Intervalo pedido, porción explorada, tramos publicados, huecos, motivo de finalización y presupuesto consumido |
| Método | Algoritmo de continuación, refinamiento, semillas, pruebas de estabilidad y límites conocidos |
| Evidencia | Nivel publicado del paquete/par y fuentes; independiente del certificado numérico |

Los puntos fuera de estabilidad/dominio o sin convergencia no entran en un segmento certificado. Pueden conservarse como candidatos en evidencia diagnóstica, claramente separados del conjunto dibujable. Una región sin rama LV estable detectada debe distinguirse de un fallo numérico; el alcance de la búsqueda debe acompañar esa afirmación.

Si el trazador alcanza su presupuesto, devuelve lo calculado como parcial con su motivo. No marca el intervalo entero como cubierto por haber alcanzado un número de puntos. Un resultado completo dentro del método declarado tampoco es una demostración matemática de que no existe otra rama no detectada.

Los IDs de fase límite de un diagrama no se presuponen iguales a los IDs de la trayectoria. La asociación de marcadores se hace por tipo, composición y contexto, conservando los IDs originales de ambos objetos.

La identidad del resultado dinámico también debe permitir saber qué parámetros y versión del núcleo produjo sus estados. Añadir esa procedencia al ensamblaje como metadato compatible, sin cambiar cantidades ni resultados anteriores. Si una ejecución histórica no tiene huella suficiente, mostrar que la coincidencia de datos no puede verificarse y ofrecer volver a resolver; no deducirla solo de un `modelo.id` que podría seguir igual tras actualizar parámetros. Si se declara `huellaModeloEsperada` y no coincide con el backend, rechazar la comparación con diagnóstico explícito.

### 5.4 Diagnósticos previstos

Familias estables y con ruta del campo: revisión inválida, unidades/dato inválido, paquete no disponible, parámetro ausente, número de componentes no soportado, corte fuera de dominio, convergencia fallida, fase competidora, región crítica excluida, rama ambigua y presupuesto agotado.

Conservar las distinciones actuales `no_soportado`, datos incompletos e incompatibilidad. Todos los rechazos conocidos deben ser respuestas estructuradas del protocolo; no un 422 genérico sin ruta.

## 6. Estrategia numérica

### 6.1 Punto de coexistencia

Resolver las condiciones del §3 usando el paquete elegido. Para un T–xy regular, a P y composición líquida dadas, las incógnitas pueden ser T y la composición del vapor. Para P–xy regular, a T y composición líquida dadas, pueden ser P y la composición del vapor. El backend puede cambiar de parametrización cuando la continuación lo necesite.

No imponer `K_i = gamma_i Psat_i/P` de manera universal: un adaptador puede incluir Poynting, vapor no ideal u otra formulación. La operación compartida de potenciales/fugacidades es la autoridad. La versión ideal simplificada sirve como referencia cuando sus hipótesis coinciden exactamente.

Especies que tienden a cero requieren límites puros y expresiones bien definidas. No insertar composiciones mínimas ficticias para evaluar `log(0)` y presentarlas como un extremo exacto. Cuando el límite no se pueda evaluar, terminar con diagnóstico.

### 6.2 Construcción de ramas

1. Determinar el dominio común de propiedades y parámetros para el corte.
2. Obtener semillas desde extremos puros válidos, puntos interiores y/o un estado LV proporcionado únicamente como ayuda numérica. La validez del diagrama no debe depender de tener una trayectoria previa.
3. Continuar las soluciones usando el punto anterior como semilla, con corrección y verificación en cada punto.
4. Refinar donde aumenta la curvatura, aparecen problemas del Jacobiano, cambian fases competidoras o `x-y` se aproxima a cero.
5. Repetir búsquedas con otras semillas y sentido de recorrido para reducir dependencia de la inicialización.
6. Detectar y conservar ramas distintas. En pliegues, usar una parametrización adecuada —por ejemplo, longitud de arco— o detener y declarar el alcance si esa continuación aún no está implementada.
7. Cortar segmentos en fallos, límites o cambio de topología; nunca unirlos para dar apariencia de continuidad.

No suponer que T(x) o P(x) son monótonas, que hay un único azeótropo ni que ambos extremos puros están dentro del dominio. Poder producir una rama parcial bien verificada es preferible a completar la curva por extrapolación.

### 6.3 Azeótropos y fases competidoras

- Un candidato azeotrópico exige coincidencia de composiciones `x≈y` a T y P comunes y equilibrio de potenciales. Refinarlo y publicar residuos; no identificarlo solo por el cruce visual de dos líneas.
- Comprobar también mínimos de `|x-y|`, no únicamente cambios de signo que podrían perder un contacto tangente.
- Los extremos puros no se etiquetan como azeótropos de mezcla.
- Distinguir el azeótropo LV homogéneo de un encuentro LLV. En el segundo, identificar los líquidos competidores o declarar el evento y el límite del trazador LV.
- No restringir artificialmente la prueba de estabilidad a L/V para ocultar un segundo líquido permitido por el paquete.
- No presentar coincidencia de composiciones como prueba suficiente de criticidad. Un punto crítico requiere condiciones y un paquete capaces de evaluarlo; lo excluido sigue excluido.

### 6.4 Certificación

Cada punto publicado debe comprobar: unidades y dominio, normalización y positividad, T/P comunes, equilibrio químico de cada componente, identificación de fases y estabilidad frente al alcance declarado. Publicar los residuos con su escala física; no mezclar cantidades de energía y composición en una escala única que oculte errores.

Verificar el comportamiento de burbuja/rocío desde el lado apropiado mediante pruebas locales cuando sea evaluable. En un punto regular, la fase incipiente debe ser coherente con el flash cercano; en puros y azeótropos la degeneración se trata expresamente.

La certificación vale en puntos calculados y verificaciones adicionales indicadas. Una línea entre puntos es interpolación visual y no una certificación continua. No usar suavizado que invente sobrepasos en composición o atraviese regiones excluidas.

## 7. Relación con simulaciones donde cambian T y P

Cada muestra seleccionada aporta `T_k`, `P_k`, `z_k` y sus fases efectivas. Se generan dos consultas:

- T–xy con `P = P_k`.
- P–xy con `T = T_k`.

Mostrar sobre ambos el mismo estado: composiciones de las fases presentes, composición global diferenciada y, cuando sea LV, el segmento de unión correspondiente. No deducir una composición de fase ausente a partir del reparto ni dibujar un vapor ficticio en una muestra líquida monofásica.

Si solo hay líquido o vapor, se puede situar su composición real como estado monofásico; no afirmar que ese punto está en una curva de coexistencia. Si hay LL/LLV u otra topología no representable en la vista inicial, mostrar el estado y su limitación sin reducirlo a un único líquido.

Con T y P variables, las muestras sucesivas pertenecen a cortes diferentes. Por defecto se superpone **solo el instante seleccionado**. La trayectoria completa solo se superpone en un corte fijo cuando todas las muestras incluidas comparten la condición correspondiente dentro de tolerancia declarada. Si no, usar cortes actualizados o una futura superficie; no mezclar puntos de diferentes presiones en un T–xy de referencia única como si validaran esa curva.

Una referencia manual desvincula únicamente ese panel del instante. La etiqueta visible debe decir la T/P del corte y si proviene de la muestra o de un valor manual. El marcador del estado se compara con el corte solo si sus condiciones coinciden; en otro caso se avisa de la diferencia y se evita dibujar una falsa unión de equilibrio.

La comparación con la simulación reutiliza los resultados originales: no cambia la energía, no ajusta el calor ni fuerza la trayectoria a encajar en el diagrama.

## 8. Interfaz, rendimiento y persistencia

### 8.1 Vista mínima

Dentro de resultados de `/motor`, añadir una pestaña opcional **Equilibrio**. No cargar el cálculo al entrar en la pantalla principal de gráficas.

Elementos visibles:

- Volumen, cuando haya más de uno.
- Instante seleccionado, con su T y P y unidades.
- Dos paneles T–xy / P–xy, en paralelo en escritorio y apilados en pantalla estrecha.
- Condición de referencia de cada panel y acción **Calcular / Actualizar**.
- Componente del eje identificado por nombre; se puede invertir la especie del eje sin resolver otra física.

Mostrar únicamente avisos relevantes de parcialidad, falta de soporte o cambio de referencia. Método, fuentes, residuos, cobertura y evidencia completa quedan en detalles. Respetar los colores y estilos existentes; no añadir texto educativo permanente ni nuevos menús de configuración en Resolver.

### 8.2 Actualización y coste

- Primera entrega: cálculo bajo demanda de ambos paneles, con estados de carga y error independientes.
- Mover el tiempo actualiza la selección; el cálculo pesado se solicita al confirmar/soltar o con Actualizar, según las mediciones de coste. No solicitar un diagrama completo por cada evento de arrastre.
- Reutilizar semillas entre cortes cercanos sin saltarse verificaciones. No memorizar un estado válido como certificado de otro distinto.
- AbortController y control de generación en frontend: una respuesta de una selección anterior no reemplaza los datos de la selección actual.
- Presupuesto acotado de evaluaciones/tiempo en backend y comprobación cooperativa entre puntos. No asumir que abortar HTTP detiene por sí solo el cálculo Python.
- Empezar con peticiones acotadas y la infraestructura existente. Introducir trabajos persistentes o progreso en streaming solo si los benchmarks muestran que hace falta; evitar una plataforma de tareas nueva para dos diagramas.

Medir cada paquete en cortes fáciles, cerca de azeótropos y frente a competencia LL. Registrar coste por punto, total, caché fría/caliente y comportamiento al agotar presupuesto. No prometer actualización fluida hasta medirla.

### 8.3 Caché y firma

Clave física: paquete/versión/huella de parámetros y referencias, identidades verificadas de componentes, corte normalizado, intervalo, perfil numérico y versión del trazador. No incluir tiempo de muestra, nombre de hoja ni colores. Condiciones equivalentes en unidades distintas deben reutilizar el cálculo cuando su normalización sea equivalente; no redondear condiciones físicas distintas para hacerlas coincidir.

Cambiar el componente del eje puede transformar `x→1-x`, `y→1-y` conservando las parejas de coexistencia, orden de rama y etiquetas; no debe forzar otro flash.

Preferencias y selección se guardan fuera de la firma física del ensamblaje. Los diagramas voluminosos pueden usar la infraestructura de resultados en IndexedDB con límite de retención; no crecer indefinidamente en localStorage. Debe seguir siendo posible leer hojas y resultados históricos sin estos campos.

### 8.4 Exportación

CSV: rama, segmento, punto, T [K], P [Pa], composiciones L/V por componente, estado de verificación. JSON: consulta, identidad, puntos, certificados, incidencias y procedencia originales. No exportar valores interpolados como si fueran puntos certificados. Mostrar las unidades de presentación sin perder el SI original.

## 9. Hitos y responsables

| Hito | Responsable | Entrega | Condición para continuar |
|---|---|---|---|
| D0 · Contrato y capacidades | Claude + revisión de integración Codex | Tipo TS compartido y esquemas backend, estados/diagnósticos, presupuestos, huella de modelo y semántica de fases límite | Compilan peticiones/respuestas y controles negativos; capacidades no prometen trazado aún no implementado |
| D1 · Punto y continuación | Claude | Operación compartida de coexistencia; trazador de ambos cortes con certificados, ramas y segmentos | Referencias ideales/puras, inversión de componentes y estabilidad pasan; ninguna fórmula duplicada |
| D2 · Singularidades y cobertura | Claude | Azeótropos, competencia LL/LLV, extremos fuera de dominio, semillas alternativas y finalización parcial | Pruebas de fallos y degeneración; no se publican uniones falsas ni raíces sin verificar |
| D3 · Servicio y evidencias | Claude | Rutas, ejemplos generados, benchmark, límites publicados y guía de integración | Validadores Python→TS con respuestas reales; regresión física y compatibilidad |
| D4 · Lectura y vista | Codex | Lector estricto, dos paneles, selección de muestra, marcadores, unidades, caché y exportación | Pruebas de respuestas corruptas y obsoletas; revisión visual y persistencia sin cambiar la física |
| D5 · Validación de extremo a extremo | Claude física / Codex integración | Contrastes independientes y muestras reales; comparación con datos experimentales de alcance explícito | Criterios del §10 cumplidos y límites documentados |

Claude trabaja en backend, núcleo, pruebas físicas y documentación del servicio. Codex trabaja en frontend, lectores, integración y pruebas de experiencia. No modificar `/laboratorio`, el cambio ajeno de `thermodynamics/proveedor.py`, ni descartar cambios de otros colaboradores. Sin commit/push durante esta entrega salvo instrucción posterior del usuario.

La implementación de D1–D3 puede publicar un trazado parcial si documenta su alcance; eso no permite declarar completado D5. No delegar validación física al aspecto visual ni contabilizar un ejemplo bonito como prueba de generalidad.

## 10. Matriz de aceptación

| Caso | Qué debe demostrar |
|---|---|
| Paquete ideal, dos componentes con límites regulares | T–xy/P–xy contra ecuaciones independientes con exactamente las mismas hipótesis; incluir Poynting si el paquete lo usa |
| Extremos puros | Coinciden con saturación del mismo paquete donde exista; un extremo excluido deja una rama parcial explicada |
| Dos pares diferentes dentro de capacidades | Cambiar componentes no exige modificar el algoritmo; no hay condiciones por nombre de sustancia en el trazador |
| Invertir orden/IDs de componentes | Misma física, composiciones transformadas y procedencia intacta |
| Escalado de cantidad total | El equilibrio intensivo y el diagrama no dependen de masa inicial o tamaño del volumen |
| Unidades equivalentes | Mismo resultado normalizado y clave física compatible; Celsius/bar se muestran sin alterar cálculos |
| Mezcla no ideal con azeótropo | Raíz refinada x=y, igualdad de potenciales y comparación con evidencia de origen conocido |
| Sin azeótropo en el alcance contrastado | El algoritmo no fabrica un cruce en los extremos ni por interpolación |
| Posibles múltiples raíces/pliegues | Se conservan ramas o se declara el límite de continuación; no se toma la primera raíz sin comprobar |
| Competencia de otro líquido | Estabilidad lo detecta y el trazado LV deja el tramo correspondiente sin falsificar una mezcla homogénea |
| Traza y límites x=0/1 | Sin logaritmos artificiales, renormalización ocultada ni fases de cantidad positiva inventadas |
| Parámetros ausentes | Diagnóstico por par/variable; sin caída a ideal |
| Dominio/criticidad excluidos | Terminación y huecos explícitos, no extrapolación |
| Varias semillas y sentidos | Reproducibilidad dentro de tolerancia o ambigüedad documentada |
| Control negativo de certificado | Alterar potencial, normalización, condición fija o fase competidora invalida el punto; el lector rechaza una afirmación falsa de cumplimiento |
| Trazado interrumpido | Conserva puntos certificados; estado parcial, cobertura y motivo correctos; ningún segmento cruza el hueco |
| Simulación LV a P constante | Pares (T,x,y) sobre su T–xy y regla de la palanca consistente con beta publicado |
| Simulación LV a T constante | Pares (P,x,y) sobre su P–xy cuando el ensamblaje soporte ese caso; en otro caso usar estados estáticos y declarar la cobertura pendiente |
| Trayectoria con T y P variables | Dos cortes correspondientes a cada instante; ninguna superposición engañosa de la trayectoria completa |
| Estado monofásico o LL/LLV | Marcadores acordes a las fases reales, sin atribuir un y o un x inexistente |
| Referencia manual distinta de la muestra | Diferencia visible; sin falsa comparación de equilibrio |
| Cambio de paquete | Caché/resultados de diagrama se invalidan por firma; datos originales de la hoja intactos |
| Solicitudes solapadas | Una respuesta antigua no sustituye el corte actual; cancelar/agotarse no bloquea posteriores consultas |
| Hoja de tres componentes | Vista binaria explica falta de soporte; no borra ni renormaliza el tercero |
| Exportación y recarga | Puntos/certificados/IDs preservados, preferencias recuperadas y firma dinámica sin cambios |

Las pruebas experimentales deben citar presión/temperatura, base de composición, incertidumbre, parámetros usados y si los datos fueron usados para ajustar el modelo. Comparar con el mismo conjunto empleado para ajustar parámetros no se presenta como validación predictiva independiente. No elegir tolerancias después de observar el resultado.

La coincidencia del diagrama con la trayectoria comprueba coherencia de integración y cierre compartido. No es una validación independiente de la ecuación de estado: ambos pueden compartir un defecto. Mantener referencias analíticas, implementación independiente y datos experimentales como niveles complementarios.

## 11. Archivos previstos y entrega verificable

Nombres orientativos, a adaptar a la estructura existente sin crear capas redundantes:

- Backend: módulo de servicio de diagramas; operaciones compartidas de coexistencia/trazado en núcleo; adiciones de rutas a `backend/main.py`.
- Contrato canónico: `docs/contratos/contratoDiagramasEquilibrio.ts`, copiado al frontend con control de igualdad y prueba Python→TypeScript.
- Backend QA: `tests/validar_motor_diagramas_equilibrio.py`, ejemplos reales bajo `docs/ejemplos/motor-diagramas/` y guía de fundamentos/códigos/capacidades.
- Frontend: lector y servicio de diagramas, vista opcional de equilibrio, componentes de cada corte, configuración visual y caché separadas de la solicitud dinámica.
- Frontend QA: verificador de contrato/invariantes, integración con muestras reales, pruebas de firma/caché y evidencia visual en escritorio/pantalla estrecha.

Antes de cerrar: ejecutar las nuevas suites físicas, las regresiones pertinentes de estado y ensamblaje, los verificadores TS de contratos existentes y nuevos, `npm run test:motor-fundamental`, TypeScript y lint de los archivos modificados. La entrega debe distinguir pruebas pasadas de pendientes, aportar comandos reproducibles y no afirmar una batería ejecutada que se haya interrumpido.

No exigir pruebas de módulos ajenos por cada cambio cosmético posterior. Si una corrección cambia física compartida, ampliar regresión según el alcance real.

## 12. Orden práctico y criterio de terminado

Primero contrato y capacidades; después coexistencia y trazado físico verificado; luego servicio y evidencia; por último vista e integración dinámica. No comenzar una superficie 3D para compensar que falte cerrar una rama o una prueba de estabilidad.

Se considera terminada esta entrega cuando el usuario puede abrir una hoja binaria compatible, calcular ambos cortes, identificar el paquete y las condiciones, seleccionar una muestra y entender qué fases/composiciones compara; cuando resultados parciales y límites no se ocultan; y cuando existen pruebas que demuestran que cambiar sustancias o paquete compatible no obliga a cambiar el trazador.

El estado de D0–D5 se registra en el informe de integración enlazado al principio. Este documento conserva el plan de referencia; no envía instrucciones automáticamente a otra conversación.

## 13. Fuentes y punto de partida

- Proyecto: `docs/MOTOR_EQUILIBRIO_MULTIFASICO.md`, `docs/CONSOLIDACION_MULTIFASICA.md`, los contratos de estado y ensamblaje v2 y `frontend/REVISION_NRTL_Y_REPARTO_COMPONENTES.md`.
- [Thermo — Flash calculations](https://thermo.readthedocs.io/thermo.flash.html): distingue operaciones de T–xy a P fija y P–xy a T fija. Se usa como referencia de semántica e interfaz, no como reemplazo del flash del paquete actual.
- [NIST teqp — Phase equilibria](https://pages.nist.gov/teqp-docs/en/main/algorithms/VLE.html): formulación por coexistencia y estrategias de continuación de isotermas/isobaras. Orienta el diseño numérico; no obliga a añadir la dependencia ni a adoptar sus ecuaciones de estado.
