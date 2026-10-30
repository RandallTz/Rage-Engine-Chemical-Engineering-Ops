# Especificaciones flexibles y unidades del laboratorio

Fecha: 11 de octubre de 2026.
Estado: ambos hitos entregados por Claude en §22, revisión 8, e integrados en frontend. Ver INTEGRACION_ENTREGA_22.md. Este documento conserva el contrato de aceptación; no volver a solicitar estos hitos.

## 1. Objetivo y prioridad vigente

El usuario quiere decidir qué variables conoce y cuáles calcula, conservando una interfaz simple. El motor debe resolver las ecuaciones acopladas con esas especificaciones; no basta con cambiar las etiquetas de los campos ni contar ecuaciones. También quiere unidades seleccionables en cada cantidad y resultados comparables en distintas unidades.

El coeficiente `k_salida` corresponde a la relación particular F_sal = k N. No pertenece al balance general y no debe ser requisito para cualquier tanque. No se pide agregar bombas, correlaciones hidráulicas ni expresiones arbitrarias en este hito.

Trabajar exclusivamente en backend, conservando cambios ajenos. No hacer commit ni push. `thermodynamics/proveedor.py` tiene cambios ajenos; no modificarlos para cumplir esta entrega. El frontend se desarrolla por separado y no implementará resolución inversa ni factores de conversión propios.

Esta entrega tiene dos hitos obligatorios, entregables por separado:

1. Registro coherente de unidades y catálogo de variables/especificaciones.
2. Formulación material básica con elección de especificaciones, sin relación de salida introducida por omisión; resolución estacionaria directa/inversa y temporal directa dentro del dominio explícito.

Problemas inversos temporales con objetivos finales son un hito posterior. No se anuncian disponibles por resolver el hito 2.

## 2. Contexto suficiente para un chat nuevo

Leer primero este documento y `docs/ENTREGA_LABORATORIO_CODEX.md` §§16–21. Consultar otras secciones solo cuando se reutilice su física. No repetir entregas anteriores.

Estado documentado: revisión de contrato 7, estudios de 1–8 componentes y montajes limitados. Existen `/laboratorio/estudios/{validar,resolver,transferir,capacidades,ejemplos}`. Hay materia, energía, reacción e interfaces en combinaciones verificadas específicas. Momento y un ensamblador general de DAE arbitrarias no están disponibles. Los estados transferidos son objetos opacos con integridad, huellas y comprobación de vigencia.

Las 31 suites en verde fueron reportadas en la entrega anterior. Volver a ejecutar la batería al entregar; no reutilizar ese resultado como validación de cambios nuevos.

Archivos relevantes:

- `backend/schemas_estudios.py`: forma de las peticiones; actualmente almacenamiento exige un cierre.
- `backend/nucleo_estudios.py`: adaptación, identificadores, huellas y transferencia.
- `core/dinamica.py`: ensamblaje, especificaciones admitidas, cierres e integración conjunta.
- `core/laboratorio.py`: variables y conversiones del laboratorio existente.
- `backend/nucleo_unidades.py` y `config/settings.py`: tabla de unidades generada con el registro Pint existente.
- `backend/main.py`: rutas; ya existe `GET /unidades` para otras partes del producto.
- `tests/validar_estudios*.py` y `docs/ejemplos/`: regresión y pares reales petición/respuesta.

No es necesario leer todo el frontend para implementar este contrato. `SUPUESTOS_POR_VOLUMEN_CLAUDE.md` conserva pendientes más amplios; este documento fija la nueva prioridad. Overrides de propiedades, momento, equipos y otras simplificaciones siguen fuera de alcance.

## 3. Regla fundamental: especificar no es cambiar de física

Separar tres cosas:

1. El modelo físico: balances, propiedades, restricciones, relaciones constitutivas y conexiones.
2. Las especificaciones del estudio: qué variables se fijan y cuáles se buscan.
3. Las condiciones iniciales del temporal y, en otro hito, sus objetivos finales.

Una corriente compartida sigue siendo una sola variable física con usos en ambos sistemas. Especificarla en dos lugares no crea dos variables ni dos grados de libertad. Las verificaciones globales no se cuentan nuevamente como ecuaciones independientes.

Elegir «Calcular» no elimina una relación física existente. Ejemplo: si F_sal = k N está declarada, sigue en el modelo hasta que se retire explícitamente. Tampoco elegir «Dato» habilita automáticamente cualquier variable: el servidor debe declarar qué elecciones admite en cada combinación.

GL = 0 no prueba existencia, independencia ni unicidad. Distinguir recuento estructural, rango cuando se evalúe, restricciones físicas y resultado del solver. No presentar una prueba numérica local de rango como garantía global.

## 4. Hito 1: unidades y catálogo

### 4.1 Una fuente de verdad

Reutilizar el registro Pint existente. Consolidar los criterios de aceptación/conversión de estudios con el catálogo que se publica al cliente. Hoy existen tablas en `core/dinamica.py`, `core/laboratorio.py` y un registro en `/unidades`; no publicar unidades que el endpoint de cálculo rechace ni exigir al frontend otra tabla manual de factores.

Propuesta de ruta: `GET /laboratorio/estudios/unidades`. Puede sustituirse por una ampliación compatible de `/unidades`, documentando la ruta final. Mantener consumidores actuales de `/unidades` intactos.

Por magnitud devolver:

- Identificador estable de magnitud, dimensión y unidad interna SI.
- Unidades aceptadas realmente por el cálculo, con símbolo API y etiqueta humana.
- Factor y desplazamiento cuando la conversión sea afín; aptos para presentación local.
- Distinción entre temperatura absoluta y diferencia de temperatura.
- Información explícita si una transformación necesita composición, masa molar, densidad u otra propiedad. No ofrecerla como conversión afín.
- Revisión del catálogo. Nada de referencias a ecuaciones inferidas desde LaTeX.

Cubrir las cantidades del dominio vigente: tiempo, cantidad de sustancia, caudal molar, fracción molar, volumen, densidad molar, temperatura, presión, energía, energía molar, potencia, capacidad calorífica molar, capacidad térmica y conductancias de las interfaces. Mantener unidades de parámetros explícitos existentes, incluido k, por compatibilidad.

Las peticiones conservan `{valor, unidad}`. El servidor valida dimensionalidad y dominio y normaliza antes de resolver; el núcleo numérico continúa en SI. Conservar procedencia: cantidad declarada y cantidad normalizada, sin sobrecargar el resultado principal.

Un campo vacío es ausente y cero sigue siendo cero. No suponer unidades desconocidas. Fracciones y coeficientes adimensionales también deben indicar su base; un porcentaje solo se admite si su semántica está declarada.

Cambiar una unidad de presentación debe preservar la cantidad física. Ejemplo: 10 min = 600 s. Diferenciar esa operación de escribir un nuevo valor.

kg/h → mol/s requiere masa molar/composición; caudal volumétrico → molar requiere propiedades. No convertirlos por parecido de nombres. °C y Δ°C tienen semánticas diferentes. Presión relativa y absoluta tampoco se sustituyen sin referencia.

### 4.2 Catálogo de variables del montaje

`/validar` debe poder devolver el catálogo útil de un montaje incompleto, aunque su estado no sea `valido`. Puede agregarse una ruta de inspección si la validación actual no puede hacerlo; documentar una única vía para el frontend.

Por variable, propuesta de metadatos añadidos:

```json
{
  "id": "in.F",
  "nombre": "Caudal de entrada",
  "simbolo": "F",
  "magnitud": "flujo_molar",
  "unidad_interna": "mol/s",
  "familia": "materia",
  "bloque_ids": ["in"],
  "conexion_ids": ["c1"],
  "compartida": false,
  "funcion": "especificacion",
  "puede_especificarse": true,
  "puede_calcularse": true,
  "motivo_limitacion": null
}
```

Este ejemplo es una propuesta de esquema, no una respuesta ya disponible. Usar IDs reales del ensamblador. La elegibilidad depende del estudio, las relaciones y la combinación física, no solo del nombre de la variable. Distinguir estado diferencial, algebraica, parámetro, inicial y frontera. `puede_calcularse` significa elección admitida; no garantiza que cualquier combinación de elecciones cierre el sistema.

## 5. Hito 2: balance general y especificaciones flexibles

### 5.1 Alcance mínimo verificable

Usar la topología material de dos volúmenes en serie ya soportada, una especie, mezcla perfecta y sin reacción/energía/momento para las primeras referencias independientes. No ampliar simultáneamente a topologías arbitrarias. Si se amplía a una sola caja, declararlo y verificarlo por separado.

El balance general aporta entrada, salida y acumulación. Un caudal externo puede ser dato de frontera. La salida no exige una bomba ni una ley kN. Si no existe información suficiente para determinar el caudal, la validación debe dejarlo pendiente.

Introducir un modo explícito nuevo, sin cambiar la semántica de cierres existentes. Propuesta mínima: `almacenamiento[].cierre = "balance_general"`. En ese modo no se agrega F_sal = k N ni una restricción N = rho V por omisión. No confundir «no hay relación de salida declarada» con «compartimento cerrado» ni con F = 0.

La geometría, densidad, mezcla perfecta y el almacenamiento energético siguen siendo relaciones físicas separadas. Una propuesta de salida que contradiga un modelo incompresible rígido con cantidad constante se rechaza; no borrar esa restricción para que converja.

### 5.2 Especificaciones por identidad de variable

Propuesta de campo optativo para nuevas peticiones:

```json
{
  "seleccion_variables": {
    "version": 1,
    "variables": [
      {"variable_id": "in.F", "modo": "calcular"},
      {"variable_id": "out.F", "modo": "dato", "cantidad": {"valor": 36, "unidad": "kmol/h"}}
    ]
  }
}
```

Es un fragmento ilustrativo, no una petición completa ni un resultado esperado para todo montaje. El resto de especificaciones necesarias debe acompañarlo. Si se elige otra forma final, mantener esta semántica y publicar ejemplos completos.

- Dato añade una especificación al sistema; Calcular identifica una incógnita, sin inventar un valor inicial numérico.
- Resolver no depende de una dirección rígida del diagrama. Ensamblar el sistema reducido con las especificaciones elegidas.
- No interpretar texto ni LaTeX como instrucciones de cálculo.
- IDs inexistentes, elecciones no admitidas y duplicados producen diagnósticos por variable/pieza/conexión.
- No admitir simultáneamente una especificación antigua y nueva de la misma variable en silencio. Definir rechazo o migración explícita.
- No ocultar una especificación sobrante porque no se usa. Explicar redundancia, incompatibilidad o falta de soporte.
- El catálogo completo permanece visible aunque una variable no sea editable.

### 5.3 Estacionario

Resolver el residuo acoplado con las especificaciones activas, usando un método apropiado y declarado. Un sistema lineal puede resolverse como tal; los casos no lineales deben informar el método real, arranques, límites, tolerancias y convergencia. No forzar una marcha hacia delante cuando una especificación aguas abajo determina una entrada.

Referencia mínima: dos tanques de agua, n1 y n2 fijados explícitamente y sin ley kN. Al imponer F_ent = 10 mol/s se obtiene F_intermedia = F_sal = 10 mol/s. Al imponer F_sal = 36 kmol/h se obtienen los mismos caudales hacia atrás. Las cantidades fijadas eliminan la indeterminación de almacenamiento; no deben deducirse de esos caudales.

Si n1/n2 no están determinados por especificaciones o relaciones, decir que sus valores estacionarios son indeterminados. No fabricarlos para devolver GL=0. Si entrada y salida impuestas son incompatibles con estacionario, rechazar. Cuando coincidan, distinguir especificación redundante de ecuación independiente.

### 5.4 Temporal directo

Admitir caudales de frontera declarados y cantidades iniciales por especie sin exigir k. Integrar ambos volúmenes juntos, con una sola corriente intermedia. Un caudal de salida impuesto por el usuario es una condición de frontera, no una aproximación oculta a una bomba.

Referencia material: F_ent = 3, F_intermedia = 2, F_sal = 1 mol/s y n1(0)=100, n2(0)=200 mol. Entonces n1(t)=100+t y n2(t)=200+t; la suma crece a 2 mol/s. Usar horizonte dentro del dominio declarado. No introducir V o densidad constantes innecesarios para esta referencia en cantidades molares.

No deducir F_intermedia o una función de salida arbitraria solo de condiciones iniciales y duración: si falta una frontera o relación, el problema permanece incompleto. Reutilizar eventos de agotamiento, restricciones, conservación y resultados parciales.

### 5.5 Límites e integración con capacidades

Declarar las combinaciones soportadas y, por combinación, las variables que pueden fijarse/calcularse. La selección flexible para materia no habilita automáticamente inversión termoquímica, reacción, interfaces, momento o DAE arbitrarias.

Las iniciales del temporal se mantienen distintas de las especificaciones estacionarias. Calcular un parámetro a partir de n(t_final) o T(t_final) requiere un problema inverso y otra validación. Por ahora, capacidades debe anunciarlo no disponible y explicarlo; no ignorar un objetivo enviado.

Expresiones nuevas arbitrarias quedan para una entrega posterior con parser seguro, símbolos tipados, unidades, dominios e independencia. No usar `eval` ni el LaTeX del cliente como motor de expresiones.

## 6. Respuesta y comportamiento para el frontend

Mantener `pendientes` y `contradicciones` con `variable_ids`, `bloque_ids`, `conexion_ids` y acción sugerida. Además del recuento GL, declarar qué especificaciones se usaron, qué incógnitas se buscaron y qué relaciones aportaron independencia. Si no se calculó rango, decirlo.

Todas las ecuaciones mostradas deben corresponder al sistema ejecutado; sus términos mantienen procedencia y residuos. No duplicar balances globales ni estados de la corriente compartida.

La UI mostrará una lista compacta variable / Dato o Calcular / valor / unidad. No necesita conocer la lista de entradas del solver ni convertir la física. El tablero de gráficas operará sobre las series devueltas; no requiere un endpoint que calcule gráficas.

El servidor debe poder devolver resultados en SI con unidad por serie. La UI podrá representarlos con conversiones afines publicadas. No alterar el dato histórico ni la condición transferida para cambiar la unidad de un eje.

## 7. Compatibilidad e integridad

Peticiones antiguas sin campos nuevos conservan resultados y modelo_id dentro de tolerancias justificadas. `salida_lineal`, `salida_impuesta`, `inventario_constante` y `volumen_fijo` no se convierten silenciosamente al modo nuevo.

La UI no migrará una mesa kN por su cuenta. Una migración física es una elección del usuario que debe invalidar validaciones/resultados/transferencias previos.

Definir cómo las nuevas especificaciones participan en IDs, huellas y transferencia. Cambiar una cantidad física o relación debe detectarse por elemento. Una unidad equivalente no debe tratarse como cambio físico en el contrato nuevo; conservar unidades declaradas como procedencia. Mantener normalización numérica exacta y prueba real Python → Node → Python. Si cambia la firma o la identidad de documentos nuevos, versionarla y explicar la migración; no relajar la comprobación ni tocar objetos opacos desde el cliente.

La transferencia de estacionario a temporal solo se anuncia en las combinaciones verificadas. Un flujo estacionario calculado no se convierte automáticamente en una nueva ley temporal de salida.

## 8. Pruebas de aceptación

Hito 1:

1. 10 min y 600 s producen la misma trayectoria y horizonte físico.
2. mol/s y kmol/h en diferentes fronteras se convierten coherentemente.
3. 25 °C y 298.15 K equivalen; una diferencia de 25 K no se convierte como temperatura absoluta.
4. Unidades dimensionalmente incompatibles, ausentes o desconocidas tienen diagnóstico con variable.
5. El catálogo ofrece exactamente lo que el cálculo acepta en cada magnitud/combinación.
6. Cero, omisiones y números no finitos se distinguen; no se redondean cantidades físicas para firmar.
7. Conversión de representación ida/vuelta no altera el dato histórico ni un estado transferido.

Hito 2:

8. Estacionario hacia delante y hacia atrás del caso de §5.3 coinciden contra el balance escrito fuera del motor, sin k.
9. Estacionario con cantidades indeterminadas no fabrica un valor ni una falsa independencia.
10. Datos redundantes y contradictorios se distinguen, incluidos dos intentos de fijar la corriente compartida.
11. Temporal de §5.4 coincide con la analítica por volumen y global; intercambio interno se cancela.
12. Retirar una frontera requerida deja pendiente, nunca caudal cero ni una ley generada.
13. Especie agotada devuelve evento/parcial, incluidos eventos anteriores a la primera muestra.
14. Modelo con cuenta cuadrada pero dependencia entre ecuaciones no se acepta solo por GL=0.
15. Objetivo temporal inverso aún no admitido y elecciones fuera del dominio se rechazan explícitamente.
16. Una condición energética/geométrica contradictoria no se borra para aceptar el balance general.
17. Regresión de montajes existentes, procedencia por término, balances por volumen e integridad entre lenguajes.

Usar referencias analíticas o formulaciones independientes. Conservación y residuo pequeño comprueban el ensamblaje; no sustituyen la referencia de precisión. Declarar límites y métodos reales, incluyendo ramas no garantizadas si aplica.

## 9. Entrega esperada

- Actualizar `docs/ENTREGA_LABORATORIO_CODEX.md` con ruta final, esquemas reales, capacidades, códigos, unidades, semántica, métodos, límites y migración.
- Generar ejemplos completos ejecutando los endpoints, incluidos fallos: unidades, tanque sin k, especificación inversa, indeterminación, redundancia y contradicción.
- Entregar resultados de pruebas y archivos tocados por hito; declarar claramente lo que no quedó disponible.
- No modificar frontend ni pedir que implemente soluciones físicas provisionales.

### Mensaje para pegar en un chat nuevo de Claude

Lee `frontend/ENTREGA_CLAUDE_ESPECIFICACIONES_UNIDADES.md`. Es la siguiente entrega propuesta del laboratorio, sobre el contrato de revisión 7. Revisa `docs/ENTREGA_LABORATORIO_CODEX.md` §§16–21 y trabaja solo en backend. Implementa primero el hito 1 de unidades/catálogo y después el hito 2 de especificaciones flexibles materiales, con los casos analíticos definidos; entrega cada hito verificable por separado. No agregues bombas, coeficientes de salida por omisión, expresiones arbitrarias ni un problema inverso temporal sin contrato. Conserva montajes anteriores, procedencia, transferencia y cambios ajenos, incluido `thermodynamics/proveedor.py`; no hagas commit ni push. Documenta el contrato final y genera ejemplos desde endpoints. Declara cualquier límite real en capacidades y diagnósticos.
