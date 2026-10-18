# Plan de termodinámica, propiedades y equilibrio del motor

**Referencia histórica de fundamentos.** El [roadmap principal](ROADMAP_MOTOR_MULTIFISICO.md) mantiene las entregas y pendientes actuales. Las indicaciones de “siguiente encargo” de este documento describen su fecha original y no sustituyen el hito que Claude ya tenga en curso.

**Actualización del 15 de octubre de 2026:** H0/H1, H3 y E0–E3 ya están entregados para agua pura. El siguiente encargo autorizado está unificado en [CONTRATO_CLAUDE_MOTOR_EQUILIBRIO_MULTIFASICO.md](CONTRATO_CLAUDE_MOTOR_EQUILIBRIO_MULTIFASICO.md): paquetes, estabilidad, mezclas, acoplamiento y sólidos por hitos. Este plan conserva el fundamento y el estado histórico del 14 de octubre; sus frases sobre capacidades aún ausentes deben leerse con las entregas posteriores.

Fecha: 14 de octubre de 2026. Estado: propuesta de implementación; no es una entrega ni una orden de implementar todos los hitos. Alcance inicial: `/motor`, manteniendo separado el laboratorio. Este documento no cambia código, dependencias, proveedores ni resultados.

## 1. Punto de partida y decisiones centrales

El motor material dispone de catálogo de componentes por ID, cantidades conservadas, corrientes por componente o total/composición y conversión de base con masa molar declarada. Los datos de corriente y su resultado están separados. `reglasEstado` distingue hipótesis de verificación. La energía actual admite un volumen y una especie, con U como estado y una relación manual afín u(T); no verifica fases.

La termodinámica debe aportar relaciones de estado y condiciones de equilibrio al mismo ensamblaje. No sustituye las leyes de conservación ni corrige cantidades para hacer converger un flash. Un flash es el cálculo del estado y reparto entre fases compatibles con las especificaciones termodinámicas elegidas.

Decisiones propuestas:

1. La fase pertenece a un estado de materia. Un componente puede estar presente simultáneamente en líquido y vapor, o en dos líquidos diferentes. El catálogo químico no contiene una fase fija del componente.
2. Separar identidad química, modelos constitutivos, especificaciones del estado y evaluación calculada.
3. Conservar cantidades totales por componente y energía como variables primarias cuando sea adecuado. El reparto entre fases es algebraico bajo equilibrio local. Introducir cantidades por fase como estados diferenciales solo al modelar explícitamente desequilibrio o transporte separado.
4. Un único contrato de propiedades, utilizado por la derivación, el ensamblaje, el solver y los resultados. Las fórmulas mostradas no serán una aproximación distinta de lo evaluado.
5. Mantener el modelo manual existente como referencia verificable y compatible; añadir termodinámica como modelo alternativo explícito.

## 2. Fundamentos que deben estar establecidos

### Conservación, estado y segunda ley

Para un sistema simple compresible en equilibrio, sin términos adicionales de superficie, eléctricos o magnéticos:

$$dU=T\,dS-P\,dV+\sum_i\mu_i\,dn_i,$$
$$H=U+PV,\qquad G=H-TS,\qquad A=U-TS.$$

La primera ley determina cómo cambia U por transferencias. Las relaciones constitutivas determinan qué T, P, V y fases corresponden a esa U y composición. La segunda ley y la estabilidad distinguen el equilibrio físicamente admisible de una raíz matemática o una rama metastable.

La selección del potencial depende de las restricciones: mínimo G para T/P/n fijados; mínimo A para T/V/n; máximo S para U/V/n. No minimizar G indiscriminadamente para cualquier especificación dinámica. Las capacidades son derivadas con restricciones: Cp=(∂H/∂T) a P/n constantes; Cv=(∂U/∂T) a V/n constantes. El coeficiente manual `c_u` actual no se renombrará Cp sin justificar esa equivalencia.

### Equilibrio entre fases

Bajo equilibrio térmico, mecánico y químico entre fases fluidas macroscópicas, sin presión capilar:

$$T^\alpha=T^\beta,\qquad P^\alpha=P^\beta,\qquad \mu_i^\alpha=\mu_i^\beta.$$

Para formulaciones de fugacidad, la última igualdad se expresa mediante fugacidades coherentes de cada especie. Se deben comprobar además cantidades, energía, volumen cuando esté especificado y estabilidad frente a fases alternativas. Un reparto con residuos pequeños no basta para certificar estabilidad. La regla de fases no reemplaza el recuento del sistema completo: no cuenta cantidades extensivas, caudales, condiciones iniciales ni todas las especificaciones del proceso. [MIT: equilibrio multicomponente y regla de fases](https://ocw.mit.edu/courses/3-020-thermodynamics-of-materials-spring-2021/resources/mit3_020s21_lecture_20_1080p_v3_mp4/).

### Reparto de componentes y bases

Para cantidades molares totales y reparto por fase:

$$n_i=\sum_\alpha n_i^\alpha,\quad n^\alpha=\sum_i n_i^\alpha,\quad x_i^\alpha=n_i^\alpha/n^\alpha,$$
$$\beta_\alpha=n^\alpha/n,\qquad z_i=\sum_\alpha\beta_\alpha x_i^\alpha.$$

Cada composición suma uno; cada cantidad y fracción es no negativa. Una fase ausente no tiene una composición física determinada: evitar publicar números arbitrarios como si la tuviese. Se necesita un ID estable de fase, distinto de su tipo: líquido 1 y líquido 2 pueden coexistir.

Separar también fase de régimen: un fluido supercrítico no se describe como una coexistencia líquido/vapor con fracción de vapor. El contrato deberá poder identificar un estado fluido monofásico y su régimen, sin fabricar calidad ni calor latente donde dejan de estar definidos. La selección inicial del dominio puede excluir la región crítica, pero ese límite debe publicarse.

La fracción molar de fase β, la fracción másica χ y la fracción de volumen ε son distintas. Convertirlas con las masas molares y densidades de cada fase; no reutilizar una masa molar global en todas las conversiones. La base de cada propiedad/fracción debe acompañar al valor. La concentración m_i/V, la densidad termodinámica de mezcla y la densidad de fase permanecen distintas.

## 3. El volumen de control define las especificaciones admisibles

Antes de seleccionar propiedades se debe declarar qué geometría y qué restricciones mecánicas tiene el volumen. No imponer a la vez T, P, U, V y todas las cantidades como datos independientes.

| Representación | Cantidades y energía | Restricción | Estado que debe obtenerse |
| --- | --- | --- | --- |
| Recipiente rígido cerrado | n_i y U | V geométrico fijo | T, P y reparto de fases mediante U/V/n |
| Materia a presión exterior prescrita | n_i y U, o coordenada H equivalente | P y relación mecánica de frontera | T, V y fases; trabajo de frontera explícito |
| Corriente de frontera | caudal y composición | T/P, o P/h cuando esté admitido | propiedades y fases del estado transportado |
| Tanque con líquido y espacio de vapor | cantidades totales y energía | volumen total del recipiente, contactos y salidas | volúmenes de fases, T/P y estado extraído |

En el llenado actual, V=m/rho representa el volumen ocupado por el fluido, con frontera móvil. No representa simultáneamente el volumen fijo de un tanque completo. Si se incluye el espacio de vapor, esa geometría y su estado deben entrar en el modelo; no añadirlos como una etiqueta decorativa.

P puede obtenerse de una ecuación de estado sin ejecutar un balance espacial de momento, si se declara equilibrio mecánico uniforme. Eso no calcula pérdidas de carga, velocidades, presión hidrostática distribuida ni la curva de una bomba.

Una sustancia pura en coexistencia líquido/vapor tiene T y P ligados por saturación. T/P no determina por sí solo cuánto líquido y vapor hay. Hace falta una especificación adicional de energía, volumen o fracción. Esta degeneración debe aparecer en el recuento, nunca resolverse eligiendo una fracción por omisión.

## 4. Contrato mínimo de la capa termodinámica

Mantener los tipos actuales y extenderlos con datos opcionales, versionados y separados de los resultados. Definir primero el contrato compartido, sin una jerarquía general de equipos.

**Identidad de componente:** ID interno, CAS o ID de proveedor verificado, masa molar con unidad/fuente y parámetros requeridos por el modelo. Un componente simbólico sigue funcionando en materia y en modelos manuales; pedir propiedades reales requiere identidad o un modelo manual completo.

**Configuración de modelo:** ID/versión de paquete, componentes ordenados por ID, fases candidatas soportadas, parámetros de interacción y su procedencia, referencia de energía/entropía y dominio. No asumir parámetros binarios nulos si faltan: cero debe ser un dato o hipótesis explícita.

**Especificación del estado:** unión excluyente de variables independientes admitidas. Primera etapa T/P/composición; después P/h/composición para corrientes y U/V/n o U/P/n para volúmenes. Propiedades específicas y extensivas tienen nombres/bases distintos. Datos adicionales se comprueban como redundancias o conflictos.

**Evaluación:** T, P, cantidades por fase, composición por fase, fracciones con base, u/h/v/s y derivadas necesarias; origen, modelo, dominio, referencia, firma de entrada, residuos de reconstrucción, resultado de estabilidad y cumplimiento de restricciones. Estado de fallo diferenciado: datos faltantes, combinación no soportada, fuera de dominio, restricción incompatible y no convergencia.

**Política de fase:** separar evaluación automática, restricción solicitada y rama forzada. Una rama forzada puede servir en investigación, pero nunca se certifica estable solo por imponerla. Si solo se buscó una fase restringida, declarar el alcance de la estabilidad: no afirmar estabilidad global frente a fases no examinadas. `fasesPermitidas` no autoriza a ignorar una fase estable incompatible con la hipótesis.

Los supuestos de fase y densidad de `reglasEstado` y los campos energéticos `monofasico`, `sinCambioFase` y `densidadConstante` necesitan una resolución común por propietario. La migración conservará las declaraciones originales y diagnosticará contradicciones; no aplicará un OR entre reglas discrepantes ni creará una segunda fuente de verdad para las mismas restricciones.

**Capacidades:** publicar especificaciones, fases, propiedades, derivadas y dominios efectivamente admitidos. La UI no deduce soporte porque exista un campo de tipo TypeScript.

El proveedor debe ser una evaluación sin efectos sobre el ensamblaje. Su caché y sus conjeturas numéricas pueden mejorar rendimiento; no deben decidir el resultado físico según el orden de llamadas. Claves de caché: especificación completa, composición, modelo/versión, referencias y parámetros. No redondear estados para reutilizar propiedades sin un error controlado.

## 5. Auditoría de modelos y consistencia

El proyecto instala `thermo==0.6.1` y `chemicals==1.5.2`. El adaptador actual construye `Chemical` y exige grupos UNIFAC para todos los componentes. Esa condición es específica del modelo de actividad: no debe impedir consultar agua, gases u otros modelos. Además, sus objetos actualizan T/P internamente; cualquier nuevo adaptador deberá aislar estados para evitar contaminación entre evaluaciones.

La biblioteca `thermo` ofrece modelos de fase y flashes; el adaptador del proyecto no expone necesariamente esas capacidades. Auditar por separado identidad, correlaciones, EOS, actividad, propiedades calóricas, derivadas, estabilidad y especificaciones inversas. No equiparar «la librería lo ofrece» con «el motor lo ha validado». [Interfaces de flash de thermo](https://thermo.readthedocs.io/thermo.flash.html).

Propuesta de familias a evaluar, sin seleccionarlas todas en el primer hito:

| Familia | Uso inicial | Comprobaciones esenciales |
| --- | --- | --- |
| Manual afín u(T) existente | referencia de regresión | mantener resultados e hipótesis actuales |
| Agua pura mediante IAPWS | primer estado real y cambio líquido/vapor | región, saturación, referencias y flashes inversos |
| Gas ideal + líquido/mezcla ideal explícitos | referencias multicomponente sencillas | referencias de fases, calor latente y límites de la aproximación |
| EOS cúbica coherente, por ejemplo PR | fluidos/mezclas adecuados a ese modelo | raíces estables, parámetros binarios y propiedades residuales |
| Modelo de exceso, por ejemplo NRTL/UNIFAC | líquidos no ideales | fugacidades, dependencia T/P pertinente y propiedades de exceso |

Para agua, auditar IAPWS-95 como candidata para una evaluación de estado más general. El módulo `core/vapor_if97.py` actual solo utiliza regiones 1/2/4 en un régimen de condensación acotado; no constituye un flash U/V completo. La formulación IAPWS-95 define propiedades del fluido y equilibrio líquido/vapor dentro de su alcance; no añade por sí sola todos los modelos de hielo. [IAPWS-95](https://iapws.org/technical-guidance/release/IAPWS-95).

Un paquete debe mantener h=u+Pv en base específica coherente, referencias comunes entre fases y consistencia entre propiedades y fugacidades. Para modelos de exceso, comprobar H^E=G^E−T(∂G^E/∂T) a P/composición fijos, y las derivadas requeridas; no sumar Cp de líquidos puros para afirmar una entalpía no ideal de mezcla. El marco de actividad de thermo ofrece propiedades de exceso y derivadas, que requieren adaptar y validar su uso. [thermo.activity](https://thermo.readthedocs.io/thermo.activity.html).

Los overrides manuales se admiten como familias consistentes: Cp(T) debe modificar la integral de h y sus referencias; una correlación de densidad debe ser compatible con el modelo y el tratamiento de presión. Un override aislado puede quedar disponible como propiedad informativa sin sustituir el cierre del solver. Mostrar si el paquete es consistente, una aproximación declarada o incompatible; no certificar un conjunto arbitrario de propiedades.

## 6. Acoplamiento con materia, energía y conexiones

En equilibrio local, conservar n_i y U; reconstruir algebraicamente T/P/fases con las restricciones del volumen. La termodinámica distribuye los mismos totales entre fases: no cambia n_i ni U. La suma de transferencia interna entre fases se cancela en el balance global de cada especie.

Una salida multifásica necesita una relación de extracción: líquido, vapor o arrastre con fracciones declaradas. No usar automáticamente la composición global z en una salida de líquido. El caudal total pertenece a la ley de frontera/flujo; el flash aporta el estado que ese flujo transporta. Una corriente compartida lleva exactamente el mismo flujo de componentes y entalpía a ambos lados, con signos opuestos.

La entalpía del fluido que realmente cruza la frontera debe alimentar energía. El calor latente ya está incorporado en u/h de las fases: no añadir otra fuente ΔHvap para el mismo cambio. En desequilibrio con balances por fase, los términos interfaciales deben conservar globalmente materia y energía, con una convención única para calor, transporte y trabajo.

Para transferencias selectivas/difusivas no basta con usar h de la mezcla donante: harán falta propiedades molares parciales y una definición del flujo energético compatible con el marco de transporte y el trabajo asociado. Se implementarán después del flujo convectivo de equilibrio.

**Cambio necesario respecto a la energía actual:** al permitir densidad variable o cambio de fase, dV/dt no es simplemente (1/rho)dm/dt. Si V=V(U,n,P), su derivada contiene V_U dU/dt, V_n dn/dt y V_P dP/dt. Conservar U y trabajo de frontera P dV/dt puede producir una matriz de coeficientes o un sistema diferencial-algebraico. Otra coordenada admisible bajo presión uniforme es H=U+PV, con dH/dt=J_E+V dP/dt; J_E contiene corrientes, calor y las otras potencias. La elección se documentará y se contrastará contra la primera ley completa, sin conservar la cancelación del modelo de densidad constante fuera de su dominio.

## 7. Hitos y condiciones para avanzar

| Hito | Implementación | Condición de aceptación |
| --- | --- | --- |
| 0. Contrato y auditoría | especificaciones, referencias, capacidades, geometría, límites del proveedor | decisiones físicas escritas; cada propiedad necesaria tiene ruta y fuente |
| 1. Un estado puro monofásico | evaluación T/P de una sustancia; u/h/v/s y estabilidad/restricciones | referencias publicadas, identidades y regresión manual; aún sin cambio de fase dinámico |
| 2. Un volumen monofásico real | inversión U/V o U/P, presión/volumen compatibles y energía con masa variable | conservación, referencias de trayectoria y análisis de trabajo de frontera |
| 3. Equilibrio líquido/vapor puro estático | saturación, fracción de fase y especificaciones inversas | reconstrucción de cantidades/U/V y degeneración T/P diagnosticada |
| 4. Un volumen con cambio de fase | equilibrio algebraico en cada evaluación, aparición/desaparición de fase | trayectoria validada al cruzar saturación; estados aceptados conservativos y estables |
| 5. Mezcla monofásica | propiedades multicomponente y composición variable | términos composicionales, calor de mezcla cuando corresponda, referencias comunes |
| 6. Equilibrio de mezclas | flash T/P y después P/h y U/V; estabilidad y fugacidades | reconstrucción de z, energía, volumen y estabilidad; no forzar una solución VLE si existe LLE |
| 7. Varios volúmenes | corrientes compartidas y extracción de fases | cancelación exacta de transferencias y conservación global; casos genéricos acoplados |
| 8. Extensiones | múltiples líquidos, sólidos, reacción, desequilibrio y transporte espacial | contrato y validación específicos de cada extensión; no heredar soporte por analogía |

Los primeros pasos ejecutables serán 0 y 1. La capacidad de reconocer saturación en la auditoría no implica permitir continuar una dinámica bifásica antes de los hitos 3/4. Si una mezcla puede formar varias fases líquidas y aún no existe su evaluación estable, diagnosticar el alcance o rechazarla; no ocultarla detrás de un flash líquido/vapor.

Reacción necesitará estequiometría, referencias químicas coherentes, potenciales químicos y datos de formación; su calor no se contará dos veces entre entalpías de formación y una fuente independiente. Sólidos necesitarán modelos propios de equilibrio, capacidades, volúmenes y posibles formas cristalinas. Electrolitos/especiación necesitan carga, electroneutralidad y estados estándar adecuados. Capilaridad, nucleación y estados metastables requieren relaciones adicionales. Reservar su extensión conceptual sin introducir campos obligatorios ni prometer que estén resueltos por un paquete fluido.

## 8. Métodos numéricos, ejecución y validación

Mantener la distinción entre estado conservado, incógnitas algebraicas y datos. Un flash convergido no certifica la trayectoria. Escalar residuos de composición, fugacidad, energía y volumen por sus magnitudes; distinguir tolerancia de cantidad, fracción, energía y derivadas. No truncar fracciones negativas o normalizar composiciones para ocultar errores.

Primero probar inversión monofásica y estabilidad con búsquedas acotadas dentro del dominio. Después permitir equilibrio anidado cuando el estado algebraico sea determinable. Si no lo es, ensamblar un sistema DAE/matriz de masa con inicialización consistente y método adecuado; el integrador ODE actual no adquirirá soporte DAE por cambiar el nombre de una variable.

La aparición/desaparición de fases cambia las relaciones activas. Usar conjuntos activos o formulación de complementariedad con tolerancias documentadas, conservación de totales y seguimiento estable de IDs de fases. No evaluar x de una fase con cantidad cero. Cerca de puntos críticos y degeneraciones, tratar la singularidad y el dominio explícitamente. Las derivadas monofásicas no se reutilizan sin validación dentro de una región bifásica. [CoolProp: derivadas y estados de fase](https://coolprop.org/coolprop/HighLevelAPI.html).

La termodinámica se evaluará en cada estado candidato que necesite el solver, no solo para decorar los resultados. Repetir comprobaciones en pasos aceptados y muestras publicadas. Si falla un flash en una etapa, reducir paso o localizar la salida de dominio según el fallo; nunca reutilizar el último estado convergido como si correspondiese al nuevo. Registrar residuos e iteraciones sin llenar la pantalla principal.

La autoridad de propiedades debería quedar en un módulo de backend aislado bajo responsabilidad de Claude, con contrato propio para `/motor`. Primero puede exponerse evaluación estática. La ejecución dinámica posterior debería llamar localmente a ese módulo desde el coordinador numérico, o utilizar un evaluador local completo y validado. No hacer una llamada HTTP por etapa RK/Newton: latencia, cancelación y estados intermedios lo vuelven inadecuado. Preservar la referencia manual en frontend y no reutilizar a ciegas el ensamblador del laboratorio. Definir el lugar definitivo de ejecución antes de integrar propiedades reales con las trayectorias.

Pruebas obligatorias por etapas:

- Valores publicados de agua y otros modelos seleccionados; implementación independiente cuando exista y datos experimentales para validez física. Dos librerías que usan la misma EOS no constituyen dos modelos físicos independientes.
- Identidades h−u−Pv, derivadas, Cp/Cv y consistencia de propiedades de exceso dentro del dominio; límites ideales y simetrías/permutación de componentes.
- Ida y vuelta entre especificaciones compatibles T/P, P/h y U/V; detectar especificaciones dependientes o contradictorias.
- Agua subenfriada, vapor sobrecalentado, saturación y fracciones cercanas a cero/uno; referencias de energía de ambas fases.
- Calentamiento a presión constante con fase latente, recipiente rígido con P variable, llenado/vaciado no isótérmico y enfriamiento con condensación; comparar ecuaciones reducidas justificadas con el residuo completo.
- Mezcla ideal y no ideal; trazas, componentes reordenados, calor de mezcla, puntos de burbuja/rocío y separación líquido/líquido cuando se incorpore.
- Salidas de fase seleccionada y corrientes compartidas: cancelación global de materia/energía, dirección real del donante y referencias energéticas equivalentes.
- Cambio de unidades y referencias, iniciales incompatibles, componentes sin datos, fuera de dominio, fallo de convergencia y solicitud de fase no soportada.
- Segunda ley en referencias donde se disponga de todos los intercambios y temperaturas de frontera; no certificar entropía global sin esos datos.
- Refinamiento temporal y tolerancias de flash, continuidad física en transiciones, jacobianos y límites de régimen; conservar todos los ejemplos materiales/manuales existentes.

## 9. Experiencia de usuario y criterios de finalización

En cada volumen, una sección breve de **Estado y propiedades**: modelo, especificaciones independientes y política de fase. Los componentes se eligen una vez por sistema. En corrientes, mostrar únicamente los datos del estado transportado que falten. El contador debe usar las relaciones del ensamblaje efectivo; un parámetro del paquete no se convierte en incógnita sin una ecuación adicional.

Mostrar T, P, composición y fases calculadas con origen y estado de validación. «Fase calculada», «hipótesis no verificada» y «restricción incompatible» son resultados diferentes. Una petición de cambio de fase permitido tampoco obliga a que aparezcan dos fases.

En la hoja matemática, cada elección agrega sus relaciones y simplificaciones: EOS, energía/volumen, equilibrio de fases y restricciones. Las ecuaciones principales siguen compactas; referencias, propiedades parciales, residuos, Jacobianos y diagnósticos quedan en detalles técnicos. Ninguna propiedad se rellena silenciosamente.

La primera entrega se considerará terminada cuando un estado monofásico puro esté correctamente identificado, evaluado y verificable, con contrato estable y pruebas independientes, sin cambiar los balances anteriores. La entrega de cambio de fase requerirá además reparto estable, energía/volumen reconstruidos y trayectoria conservativa al atravesar las transiciones. No basta con que el formulario admita «líquido» y «vapor».
