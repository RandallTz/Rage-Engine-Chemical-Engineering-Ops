# Auditoría del motor — 11 de octubre de 2026

**Seguimiento tras §25:** los hallazgos A1–A9 de este informe histórico están corregidos. Codex volvió a ejecutar las quince sondas (15/15 cumplen, salida 0) y las 69 comprobaciones de `validar_correcciones_auditoria.py` (todas pasan). El nuevo resultado se guarda en `docs/auditoria_motor_2026_10_11/correcciones_25/evidencias.json`; la evidencia original se conserva. El dictamen y mediciones siguientes describen el estado anterior a la corrección. Las limitaciones de generalización y §25.6 continúan vigentes. Ver `frontend/INTEGRACION_ENTREGA_25.md`.

## Dictamen

El motor tiene acoplamiento físico real en las combinaciones verificadas: no es solo un renderizador de ecuaciones. Sin embargo, **no está listo para presentarse como un ensamblador multifísico general ni para dar por correctas todas las combinaciones que actualmente acepta**.

La batería existente pasa: **37/37 suites del backend, en 466,7 s**, `npm test` y TypeScript del frontend. Las sondas adicionales reproducen **9 incidencias distintas**. Esto no es contradictorio: la batería cubre muchas referencias buenas, pero no estos cruces de condiciones y rutas. De las 15 sondas registradas, 11 señalan incidencias y 4 controles pasan; algunas sondas reproducen el mismo fallo de dos maneras.

Las prioridades son corregir el estacionario que omite intercambios, la compatibilidad de especificaciones con escalas diferentes y las bases cinéticas. Después, cerrar las comprobaciones del dominio inicial y la semántica de las conexiones. No conviene ampliar las combinaciones antes de resolver estos puntos.

## Alcance y método

Se revisaron el ensamblaje y residuo de estudios, sus rutas estacionaria/temporal, energía, reacción, interfaces, pared, vapor, eventos, unidades, recuento, firmas y transferencia. También se revisaron los contratos de laboratorio estacionario, lote/equilibrio, corrientes, orquestación y flowsheets, así como su correspondencia con el frontend.

Se ejecutó la batería completa del repositorio, que incluye termodinámica, flash, separación, reactores y plantas encadenadas. La revisión detallada de acoplamiento se concentró en `core/dinamica.py`, `core/fluidos.py`, `core/cinetica.py`, `core/lote.py`, `core/equilibrio.py`, `core/laboratorio.py` y las fronteras HTTP. La revisión del resto de operaciones combina sus contratos y métodos con sus suites; no constituye una certificación independiente de cada correlación o de cada posible dato de entrada.

Las sondas usan la aplicación ASGI real, sin servidor externo, salvo dos pruebas de las clases públicas Python. Guardan la petición, respuesta, comparación independiente y SHA-256 de las fuentes. No modifican los ejemplos publicados ni el código físico. El script sale con código 1 mientras persistan incidencias: no se deben reinterpretar esos fallos como pruebas aprobadas.

Evidencias:

- `tests/auditoria_motor_acoplado.py`: reproducción ejecutable.
- `docs/auditoria_motor_2026_10_11/evidencias.json`: peticiones, respuestas y mediciones completas.
- `docs/auditoria_motor_2026_10_11/sondas.txt`: registro resumido.
- `docs/auditoria_motor_2026_10_11/suites_backend.txt`: 37 suites.
- `docs/auditoria_motor_2026_10_11/suites_frontend.txt`: pruebas de interfaz y 100 respuestas con recuento.

## Hallazgos reproducidos

P1 significa que debe corregirse antes de confiar en la combinación afectada. P2 significa una validación o limitación de funcionamiento que debe corregirse, aunque no se haya devuelto una solución física aceptada incorrectamente en esa reproducción.

| ID | Prioridad | Hallazgo | Medición |
|---|---|---|---|
| A1 | P1 | Estacionario del balance general omite el calentamiento por vapor | Devuelve 300 K; referencia 345,827468 K; residuo energético 12 616,302 W |
| A2 | P1 | Inventarios grandes ocultan caudales contradictorios | Acepta entrada 0,0001 y salida dada 0,0002 mol/s; sustituye la salida por 0,0001 |
| A3 | P1 | Se reutiliza una base cinética para leyes que declararon otra | Reordenar el lote cambia 2,172841 mol; inversa 0,5 frente a 0,508260 mol/s |
| A4 | P1 | Capacidad ya excedida en la condición inicial | Acepta 0,036364 m³ dentro de un recipiente de 0,025 m³ |
| A5 | P1 | Salida reactiva negativa ya en t = 0 | Publica −900 mol/s en un resultado `parcial` |
| A6 | P1 | El neto de la cámara oculta un contacto fuera del régimen de condensación declarado | Un contacto cede 12 616 W y otro absorbe 11 384 W; devuelve `resuelto` |
| A7 | P2 | Fuente de calor compartida se aplica dos veces | Fuente declarada de 5 kW aplica 10 kW; `/validar` acepta; conservación detiene `/resolver` |
| A8 | P2 | Tope fijo en la ruta heredada de DiagramaFlujo | 30 bloques no terminan con el valor por omisión; sin ese tope, salida exacta 30 |
| A9 | P2 | Corriente acepta estados no finitos | La clase pública acepta NaN en F, T y P |

### A1. El estacionario no siempre resuelve el mismo modelo

Reproducción: `estacionario_balance_general_con_vapor`. Se transforma el ejemplo publicado de tanque abierto calentado por vapor a `balance_general`, con un inventario dado y caudal de salida calculado. No se elimina la conexión térmica ni la cámara. La petición es aceptada y devuelve `resuelto`, sin diagnóstico.

`_resolver_estacionario()` deriva cualquier `balance_general` a `_aplicar_estacionario_lineal()`. `_energia_estacionaria_bg()` calcula `u(T) = u(T_entrada) + Q_exterior/F`, pero no suma las interfaces térmicas. `_llevar_lineal()` omite evaluar términos cuyos valores no tiene. Así puede anunciar una solución sin haber evaluado el término conectado.

Referencia independiente: `0 = F Cp (T_entrada − T) + G (T_sat − T)`, con F = 1 mol/s, Cp = 75,3 J/(mol K), G = 200 W/K. Resulta T = 345,82746826476324 K. El motor devuelve 300 K. Sustituyendo los inventarios, temperatura y caudal que devuelve el estacionario en `_Sistema.evaluar()`, la derivada de U vale 12 616,302013289329 W, no cero. Para esa sustitución se carga el caudal algebraico calculado en el objeto de auditoría; no se cambia el código productivo.

Ubicación: `core/dinamica.py:8045`, `:6969`, `:7086`, `:7174`.

Corrección: el residuo común debe incluir todo el intercambio declarado. Si se conserva una ruta lineal especializada, solo puede usarse cuando represente el ensamblaje completo. Mientras no lo haga, rechazar explícitamente la combinación. Nunca marcar como ejecutado un balance que quedó sin evaluar.

Aceptación: el estacionario anula el residuo temporal completo; al arrancar un temporal desde ese estado, sin perturbaciones y con las mismas fronteras, las derivadas iniciales son nulas dentro de tolerancias dimensionalmente correctas. Aplicarlo a interfaces directas, pared y cámara, con y sin calor exterior.

### A2. La escala mezcla magnitudes y relaja contradicciones

Reproducción: `contradiccion_oculta_por_escala_inventario`. Inventarios de 1 y 2 millones de mol, entrada de 0,0001 mol/s y salida dada de 0,0002 mol/s. Son datos incompatibles en estacionario, independientemente de los inventarios.

En `_analisis_lineal()`, `escala` es el mayor valor de todo el vector b, incluyendo inventarios en mol y caudales en mol/s. El rango aumentado compara `b/escala` con una tolerancia fija. El inventario domina y oculta la diferencia de caudales. La respuesta declara `redundante_compatible`, permite resolver y cambia el caudal de salida dado al de entrada.

Ubicación: `core/dinamica.py:6969`, en `escala`, `rango()` y `consistente()`.

Corrección: adimensionalizar por variable y por ecuación; comprobar además cada especificación usada contra su valor original con una escala propia de su magnitud. Presentar el rango SVD como numérico con tolerancia, no como aritmética exacta.

Aceptación: multiplicar los inventarios por factores arbitrarios no cambia la compatibilidad de los caudales. Las unidades equivalentes conservan el diagnóstico. Ningún dato impuesto puede modificarse silenciosamente para obtener una solución.

### A3. Las bases de las leyes cinéticas no se respetan siempre

Reproducciones: `lote_bases_orden_0`, `lote_bases_orden_1` y `cinetica_inversa_base_distinta`. Se usan acetato de etilo y ácido butírico, ambos C4H8O2, con leyes declaradas por el cliente. No se pretende afirmar un mecanismo experimental: la prueba comprueba invariancia del modelo ante el orden de sus leyes y la evaluación de cada base declarada.

`core/lote.py:163` obtiene las actividades de la primera reacción y las entrega a todas. Dos reacciones con bases `fraccion_molar` y `actividad` se calculan con la primera base. Reordenarlas cambia la trayectoria en 2,172840652460877 mol sobre 200 mol iniciales. Ambos resultados son `resuelto`.

Además, `ReaccionCinetica.tasas()` reutiliza las actividades directas en la inversa aunque esta haya declarado otra base. Con x = (0,5; 0,5), la inversa de base actividad debe valer 0,5082597615236781 mol/s, pero se evalúa como 0,5. El endpoint acepta la declaración. Este segundo defecto está en la clase cinética compartida, por lo que su corrección debe comprobarse en lote, CSTR y estudios, no solo en lote.

Ubicación: `core/lote.py:156–180`, `core/cinetica.py`, método `ReaccionCinetica.tasas()`.

Corrección: cachear actividades por base, estado y temperatura; cada ley usa su propia base. Si una combinación no tiene semántica admitida, rechazarla antes de resolver. Mantener las condiciones de consistencia termodinámica de las inversas derivadas de K.

Aceptación: permutar reacciones no cambia la trayectoria y cada tasa coincide con la evaluación independiente de su ley declarada, con gamma distinto de 1. Los xilenos con gamma = 1 no detectan este defecto.

### A4. El evento de capacidad no valida el dominio inicial

Reproducción: `capacidad_excedida_en_t0`. El ejemplo de capacidad tiene V_max = 0,025 m³. Se dan 2000 mol con rho = 55 000 mol/m³: V(0) = 0,03636363636 m³. El motor integra y devuelve `resuelto`.

El evento solo busca un cruce dirigido de la capacidad. Si empieza ya al otro lado, no hay tal cruce. No se encontró una comprobación inicial equivalente que bloquee esta condición.

Ubicación: `core/dinamica.py:3443`, `:5554`, evento `lleno` alrededor de `:5714`.

Corrección: validar las desigualdades antes de integrar y antes de publicar un estacionario. Definir explícitamente qué ocurre justo en el límite con una derivada que sale o entra en el dominio.

Aceptación: por encima del máximo se rechaza o se declara fuera de dominio en t = 0 sin una trayectoria válida ficticia; por debajo se conserva el evento analítico existente.

### A5. La salida negativa aparece en una trayectoria declarada válida hasta su evento

Reproducción: `salida_negativa_en_t0`. Reacción de dimerización, tasa de orden cero y cierre de cantidad constante. El cierre produce `F_salida = F_entrada + Σν ξ = −900 mol/s` desde el inicio.

La integración termina por agotamiento a 2,5e−10 s, pero devuelve `parcial` con dos muestras cuyo caudal es −900 mol/s. El evento de caudal busca un cruce; no protege un estado que ya empezó fuera de su dominio. Un caudal negativo aquí no representa automáticamente una corriente inversa: el modelo conserva la orientación y composición de una salida.

Ubicación: `core/dinamica.py:5010`, `:5705`, `:8257`.

Corrección: comprobar los flujos derivados y el dominio completo en el estado inicial y en cada reinicio por escalón. No publicar como tramo físicamente válido muestras que ya incumplen el régimen.

### A6. Comprobar solo la suma del calor de la cámara no comprueba todos sus contactos

Reproducción: `vapor_contactos_opuestos`. Una cámara a 70 kPa se conecta a dos depósitos, a 300 y 420 K, con el dominio ideal declarado hasta 450 K. Un contacto cede 12 616,302 W; el otro absorbe 11 383,698 W. La suma es positiva y el motor devuelve `resuelto`.

El régimen entregado exige detenerse cuando el contacto necesitaría evaporación. El evento actual usa Q total de la cámara; el lado frío oculta el lado más caliente que T_sat. Esto no demuestra imposibilidad de construir otro modelo con flujos locales opuestos: demuestra que se aceptó algo fuera del régimen de condensación acotado que se anunció y verificó.

Ubicación: `core/dinamica.py:4937`, evaluación de cámaras al final de `evaluar()`, y eventos en `integrar()`.

Corrección: vigilar el régimen por contacto, con orientación y G adecuados, o formular y validar explícitamente un régimen ampliado. El límite de suministro agregado debe mantenerse como comprobación adicional.

### A7. Una fuente compartida se duplica y el rechazo llega demasiado tarde

Reproducciones: `fuente_compartida_validar` y `fuente_compartida`. Una fuente q1 de 5000 W se conecta a dos volúmenes. `/validar` responde `valido`; `evaluar()` aplica 5000 W en cada uno. La potencia exterior total aplicada pasa a 10 000 W.

La conservación integrada detecta el defecto y `/resolver` responde `no_convergente`, con `LAB_DIN_CONSERVACION`. Esta guarda funciona y evitó una solución aceptada en la reproducción. Pero el origen es topológico/semántico, no una elección mala de integrador. El identificador de la fuente no puede representar a la vez una potencia total única y dos aportes completos independientes.

Ubicación: `core/dinamica.py:979`, construcción de `fuentes_de` y `_conexion_de_fuente`; `_Sistema.evaluar()` y lista `calores`.

Corrección: una fuente total tiene un único destino hasta que exista una ley de reparto, o cada conexión tiene su propia variable y potencia declarada. Rechazar la ambigüedad en ensamblaje, citando ambas conexiones.

### A8. El límite de iteraciones heredado impide escalar cadenas

Reproducción: `cadena_30_bloques_heredada`. Treinta operaciones escalares, cada una incrementa su entrada en 1. El resultado esperado es 30. El método por omisión termina incompleto, sin salida final; pasando `max_iteraciones=None` termina completo y devuelve 30.

`Orquestador` ya calcula un límite en función del número de bloques. `DiagramaFlujo.resolver(max_iteraciones=20)` lo sobrescribe. Es una ruta heredada, separada del motor de estudios; no implica que la mesa admita treinta volúmenes.

Ubicación: `core/diagrama_flujo.py:144` y parámetro `max_iteraciones_internas=20` del reciclo.

Corrección: propagar el valor por omisión dinámico y conservar un límite explícito si el cliente lo pide. Verificar cadenas en ambos órdenes y reciclos.

### A9. Estado no finito en la clase pública Corriente

Reproducción: `corriente_estados_no_finitos`. `Corriente` acepta NaN en F, T y P porque las comparaciones `< 0` y `<= 0` no rechazan NaN. Es una reproducción de la API Python, no una afirmación de que todos los endpoints HTTP acepten esos valores.

Ubicación: `core/corriente.py:37–57`.

Corrección: validación finita de todos los escalares y composición antes de construir el estado compartido. No confiar exclusivamente en la validación de una interfaz particular, porque esta clase se utiliza al conectar operaciones.

## Correspondencia entre frontend y motor

Estas observaciones se verificaron por lectura de código; no se cuentan como sondas físicas aprobadas o fallidas:

1. **Dos fuentes de ecuaciones.** `VistaEcuaciones` usa `BalancePorVolumen` antes de obtener respuesta vigente y `modelo.ecuaciones` después. La primera es orientativa y no incluye necesariamente las relaciones y términos nuevos de pared, vapor o trabajo de frontera. La representación debe salir del mismo ensamblaje del backend incluso cuando falten datos para resolver. La etiqueta de formulación orientativa es útil, pero no elimina la discrepancia.
2. **Adiabaticidad global/local diferente.** El backend aplica `global true OR local true` (`core/dinamica.py:2826`). El frontend usa la bandera local cuando existe almacenamiento (`SupuestosModelo.tsx:66` y `VistaEcuaciones`). Con global true y local false o ausente, puede mostrar calor exterior no anulado cuando el motor aplica adiabaticidad. En el contrato actual, false local no revoca true global. Debe mostrarse esa semántica efectiva o definirse un contrato de herencia explícito; no cambiarla solo en JavaScript.
3. **Procedencia térmica mal etiquetada.** `backend/nucleo_estudios.py:349` construye `calculo` con identificador fijo `ninguno (modelo material; densidad declarada)`, también en solicitudes con energía, vapor o proveedor. Las versiones están registradas, pero el identificador describe incorrectamente qué se utilizó. No modifica la física, sí perjudica la trazabilidad.

La agrupación visual de supuestos no constituye ampliación de sus capacidades. Un término conservado en una ecuación orientativa tampoco acredita que el motor pueda resolverlo.

## Qué está correctamente construido

- El temporal ensambla inventarios, energías y paredes con almacenamiento en un vector común. Calcula temperaturas antes de las interfaces y tasas; no integra cada tanque y pasa una trayectoria precalculada al siguiente.
- Una corriente material compartida se utiliza como el mismo estado, con signos opuestos. Las interfaces materiales y térmicas usan un único flujo orientado en ambos lados.
- Las reacciones conservan elementos por estequiometría validada. Generación y consumo brutos son distintos del neto; equilibrio dinámico no se convierte en reacción detenida.
- En las rutas reactivas verificadas, la energía sensible y la fuente química se separan para evitar doble conteo. Se rechaza una referencia sensible distinta de 298,15 K cuando se usan entalpías de formación de esa referencia.
- Los cierres de energía distinguen h transportada de U almacenada. El trabajo de frontera está presente en el tanque que sigue el nivel del líquido.
- La pared sin almacenamiento usa una relación algebraica y no inventa un estado dinámico. La sonda de control sigue resolviendo y conservando correctamente.
- El cambio de referencia de 298,15 a 310 K, sin reacción, conserva T en el tanque de control con diferencia de 1,43e−10 K.
- Las discontinuidades conocidas se resuelven por tramos. Las restricciones iniciales de cantidad constante, firmas de transferencia, cambios de modelo y unidades tienen pruebas específicas que pasan.
- Las unidades se normalizan en la frontera. Las conversiones que necesitan composición, densidad o masa molar no se ofrecen como simples factores.

Estos puntos son fortalezas reales. No neutralizan los hallazgos A1–A9 ni garantizan combinaciones fuera del alcance publicado.

## Flexibilidad: objetivo frente a implementación actual

El modelo fundamental debe expresar conservación, relaciones constitutivas, restricciones, condiciones de frontera y condiciones iniciales. No todas las ecuaciones son diferenciales: una pared sin almacenamiento, una ley de equilibrio y el cierre U(n,T) pueden ser algebraicos. El estacionario sustituye las derivadas por cero en **el mismo modelo**, conserva sus conexiones y restricciones y debe comprobar el residuo completo. No se puede eliminar un intercambio porque se tomó una ruta de solución distinta.

Que exista una raíz estacionaria no implica que el temporal llegue a ella: puede ser inestable, haber varias raíces o no existir estacionario. La estabilidad disponible es local; buscar varios arranques no certifica haber encontrado todas las ramas.

La implementación actual sigue especializada:

| Capa | Lo que realmente permite | Lo que no debe prometer |
|---|---|---|
| Estudios | Uno o dos volúmenes, combinaciones explícitas, un vector acoplado | Grafo arbitrario de balances y cierres |
| Balances por volumen | Materia activa; energía en combinaciones admitidas | Elegir cualquier subconjunto y resolver sin relaciones sustitutas |
| Resolución temporal | ODE y restricciones concretas reducidas a ODE | Solver DAE implícito general |
| Especificaciones | Dato/calcular flexible en el balance general; otras rutas especializadas | Resolver cualquier variable hacia cualquier dirección solo por GL = 0 |
| Transporte espacial | Modelos concentrados y conductancias globales | Integración general de Fick/Fourier/Navier–Stokes con malla |
| Termodinámica | Modelos declarados, mezcla calorífica ideal, UNIFAC/Raoult e IF97 acotado | EOS general, entalpías parciales de exceso o bifásico transitorio |
| Flowsheets | Orquestación de operaciones y rutas particulares de inversión/reciclo | El mismo solver dinámico global de estudios para todos los equipos |
| Separación | Flash y métodos de columna implementados | Columna MESH rigurosa de muchas etapas: `mesh_solver.py` sigue sin implementar |

`solve_ivp` integra ODE explícitas; los métodos implícitos BDF/Radau de esa interfaz no convierten por sí solos una DAE arbitraria en ODE. Su documentación también advierte que los eventos buscan cambios de signo por paso, por lo que son imprescindibles las comprobaciones iniciales y de reinicio. [SciPy 1.16.2](https://docs.scipy.org/doc/scipy-1.16.2/reference/generated/scipy.integrate.solve_ivp.html).

Para problemas DAE generales, una interfaz residual `R(t,z,dz/dt)=0` y condiciones iniciales consistentes constituyen una base más amplia; la reducción explícita actual puede conservarse cuando se pueda justificar. La elección de un solver y la reducción de índice necesitan un contrato y pruebas propios. [Documentación matemática de IDA](https://sundials.readthedocs.io/en/latest/ida/Mathematics_link.html).

IF97 aporta propiedades dentro de regiones y dominios definidos; no aporta por sí sola las ecuaciones de almacenamiento, caudal o eventos de una cámara bifásica. El régimen acotado actual debe conservar esa distinción. [Publicación oficial IAPWS](https://iapws.org/technical-guidance/release/IF97-Rev).

## Secuencia recomendada

1. Corregir A1–A7 y convertir las reproducciones en pruebas de regresión de la batería normal. Corregir A8–A9 en sus rutas públicas. Resolver también la semántica efectiva de supuestos y la procedencia.
2. Hacer obligatoria una comprobación final independiente: todos los balances y relaciones activos evaluados; todos los datos impuestos respetados; restricciones, dominio y eventos verificados. Conservation global y GL = 0 no sustituyen esa comprobación.
3. Publicar el ensamblaje del backend antes de resolver: variables y unidades, ecuaciones, términos, conexiones, supuestos efectivos, dominios, restricciones y referencias de datos pendientes. La interfaz consume ese ensamblaje; no vuelve a formular otra física.
4. Separar la descripción de bloques del algoritmo de solución. Componer el grafo completo y su residuo antes de elegir Newton, una ruta lineal exacta en su alcance, ODE reducida o DAE. Mantener optimizaciones especializadas cuando sean equivalentes al residuo completo.
5. Generalizar por aceptación, no por número de presets: tres y N volúmenes, conexiones múltiples, mezclas/repartos, ramas y lazos. Cada ampliación requiere unidades y estados compatibles, iniciales consistentes y pruebas de permutación, escalado, inversión de conexiones, conservación y estacionario frente a temporal.

No se propone refactorizar todo el proyecto de golpe ni introducir más opciones en pantalla. La flexibilidad que falta corresponde al ensamblaje y a la resolución del backend. La interfaz debe permitir editar el modelo y sus datos con una experiencia uniforme, y mostrar únicamente las capacidades que el backend realmente puede cumplir.

## Estado de esta entrega

Se añadieron la auditoría, evidencias y script. **No se corrigió el código físico**, no se modificó `thermodynamics/proveedor.py` y no se hizo commit ni push. Los fallos permanecen reproducibles para que la siguiente entrega los corrija con pruebas explícitas, sin alterar o excluir las referencias existentes.

Esta auditoría documenta la implementación y las reproducciones examinadas; no es una demostración universal de corrección para todo sistema imaginable ni una certificación de operación industrial.
