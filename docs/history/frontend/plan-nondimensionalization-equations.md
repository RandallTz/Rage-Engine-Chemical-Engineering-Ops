# Motor independiente de adimensionalización

Fecha: 16 de octubre de 2026.

## 1. Encargo y separación del simulador

Entrega específica solicitada por el usuario. Crear una página independiente, propuesta `/adimensionalizacion`, para transformar ecuaciones y sistemas con distintas elecciones de escalas. No integrar todavía con `/motor` o `/laboratorio`, ni modificar sus ecuaciones, solvers o termodinámica. No resolver las ecuaciones resultantes.

Este documento es el único plan de esta entrega. Registrar aquí sus avances y pendientes, sin generar sucesivos documentos de prioridades. El roadmap multifísico conserva su orden; esta pausa no inicia ni cierra F3.

**Resultado esperado:** ecuación original → transformaciones justificadas → una o varias formulaciones normalizadas, con sus escalas, parámetros adimensionales, restricciones y transformación inversa. Cada formulación se obtiene del mismo modelo original.

No buscar una única forma “correcta”. Permitir escoger qué variables transformar, qué escalas fijar y qué coeficientes normalizar. Las alternativas pueden formar familias infinitas; presentar representantes y libertades restantes, sin prometer enumerarlas todas.

## 2. Qué significa controlar la adimensionalización

| Control | Elección del usuario | Consecuencia que debe mostrar el motor |
|---|---|---|
| Variables | Transformar tiempo, espacio, uno o más campos; conservar otras variables dimensionales | Resultado totalmente adimensional o parcialmente normalizado, identificado sin ambigüedad |
| Escalas | Dar una escala numérica con unidad, una expresión simbólica o dejarla libre | Valor/expresión, dimensiones y restricciones de cada escala |
| Objetivos | Hacer unitario un coeficiente constante, conservarlo como grupo o expresar grupos respecto a otros | Restricciones satisfechas, dependientes, incompatibles y libres |
| Referencias | Elegir una variable, componente o parámetro como referencia | Dependencia explícita de la elección, sin privilegiar una especie |
| Presentación | Factorizar, desarrollar fuentes o conservar una función declarada | Misma transformación con distinto nivel de detalle, no otra física |
| Alternativas | Duplicar una transformación y cambiar una elección | Comparación y mapa reversible entre las formulaciones |

Cambiar unidades no equivale a adimensionalizar. Elegir tiempo difusivo tampoco implica despreciar reacción. Una hipótesis física, un cambio de variables y una simplificación algebraica son operaciones diferentes y deben quedar registradas por separado.

Dividir una ecuación por una escala residual constante y no nula puede hacer unitario su término temporal sin determinar por sí solo la escala de tiempo. Mantener separados el factor global de cada ecuación y las escalas de sus variables; no contar ambas operaciones como elecciones físicas independientes.

## 3. Ejemplo de aceptación de varias formas

Ejemplo de prueba, sin ramas de código asociadas a sus símbolos o cinética:

\[
\partial_t c=D\nabla^2c+k c-a c^2,
\qquad [k]=T^{-1},\quad [a]=[c]^{-1}T^{-1}.
\]

Para D, k y a constantes positivos, una misma ecuación permite, entre otras:

| Elección | Escalas | Ecuación obtenida |
|---|---|---|
| General | x = L ξ, t = t₀ τ, c = C u | ∂τu = (D t₀/L²) ∇ξ²u + (k t₀) u − (a C t₀) u² |
| Tiempo difusivo | t₀ = L²/D; C libre | ∂τu = ∇ξ²u + (k L²/D) u − (a C L²/D) u² |
| Tiempo reactivo | t₀ = 1/k; C libre | ∂τu = (D/(k L²)) ∇ξ²u + u − (a C/k) u² |
| Escala del campo fijada por la cinética | C = k/a, t₀ = 1/k; L libre | ∂τu = (D/(k L²)) ∇ξ²u + u − u² |
| Longitud también seleccionada por los parámetros | L = √(D/k), C = k/a, t₀ = 1/k | ∂τu = ∇ξ²u + u − u²; el tamaño del dominio original permanece en la geometría adimensional |

La última forma no elimina la influencia del tamaño físico: la traslada al dominio y sus condiciones de frontera. Si L se fijó previamente como longitud del equipo, no imponer después L = √(D/k) sin advertir que son restricciones distintas. Si D o k son cero, cambian las transformaciones admisibles; no sustituirlos por un valor pequeño.

Si k es negativo, una escala temporal positiva puede usar 1/|k| y debe conservar el signo en la ecuación. No presentar k t₀ = +1 como posible con k < 0 y t₀ > 0. Si se desconoce el signo, declarar las condiciones o mantener el objetivo pendiente.

## 4. Núcleo matemático

### 4.1 Modelo tipado

Representar, con identidades estables y sin depender del LaTeX:

- Símbolos: campos dependientes, coordenadas, tiempo, parámetros, constantes y funciones declaradas.
- Dimensiones físicas como vectores de exponentes racionales; unidades y conversiones por separado.
- Árbol de expresiones: suma, producto, cociente, potencias, funciones admitidas y llamadas a funciones declaradas.
- Operadores: derivadas temporales/espaciales, gradiente, divergencia y laplaciano, con variables respecto a las que actúan.
- Igualdades o residuos, dominios, condiciones iniciales y condiciones de frontera.
- Declaración de qué símbolos son constantes y de qué variables depende cada coeficiente o función.

Los balances fundamentales son una vía de entrada. También debe poder escribirse directamente una ecuación o sistema con términos definidos por el usuario, sin etiquetar obligatoriamente una expresión como “cinética” o “Turing”.

### 4.2 Análisis dimensional

- Sumar solo cantidades compatibles; distinguir unidades, dimensiones y normalización.
- Inferir dimensiones de parámetros cuando las restricciones las determinen; dejar las indeterminadas como tales.
- Tratar los ceros y las constantes numéricas de forma explícita, sin fabricar unidades para ocultar una suma incorrecta.
- Exigir argumentos adimensionales para exp, log y funciones trigonométricas; comprobar compatibilidad en abs/min/max y funciones por tramos cuando se admitan.
- Para potencias, gestionar exponentes racionales y dominios; un exponente variable debe ser adimensional y requiere una base adimensional en el alcance inicial.
- Una función opaca necesita dimensiones de entrada/salida y dependencias declaradas. Puede mantenerse como función transformada; no expandir una definición que no se conoce.
- Convertir magnitudes afines antes del cálculo: temperatura absoluta y diferencia de temperatura no son intercambiables.

### 4.3 Transformaciones

Primera entrega: escalas constantes, finitas y positivas:

\[
t=t_*\tau,\quad x_j=L_j\xi_j,\quad c_i=C_i u_i.
\]

Aplicar sustitución estructural y regla de la cadena a todos los términos. Para un sistema se comparte el mismo tiempo y dominio espacial; cada campo puede tener escala propia. Una transformación común no permite fijar por separado el tiempo difusivo de cada ecuación salvo que los parámetros lo permitan.

Un coeficiente variable se conserva como función. Por ejemplo:

\[
\nabla\cdot(D(c)\nabla c)
\]

debe transformarse conservando esa estructura. Solo puede extraerse una escala D* si se declara D(c) = D* D̂(u); no sustituir D̂ por 1 ni generar un laplaciano de coeficiente constante sin hipótesis explícita.

Después: transformaciones afines constantes y reversibles, como T = Tref + ΔT* θ. Tref se conserva en las propiedades y condiciones, y ΔT* es una diferencia de temperatura. No tratar °C como una escala multiplicativa de temperatura absoluta.

Quedan fuera de la primera entrega: escalas dependientes de t o x, transformaciones no invertibles, cambio arbitrario de coordenadas, derivadas fraccionarias y normalizaciones por un campo que pueda anularse. Diagnosticar el límite; no devolver una transformación incompleta como si fuese general.

### 4.4 Selección y resolución de escalas

- Conservar las escalas libres cuando el usuario no fije objetivos.
- Permitir fijar dimensiones/valores o expresiones para algunas escalas y resolver las restantes.
- En objetivos monomiales, formular restricciones sobre exponentes y resolver con álgebra racional; usar rango y dependencia, no solo contar restricciones.
- Separar las restricciones dimensionales de las de normalización de coeficientes.
- Distinguir escala determinada, familia de escalas, objetivo redundante y objetivo incompatible; identificar las elecciones responsables.
- Mantener factores de signo y restricciones de no nulidad. La formulación logarítmica solo se usa con cantidades positivas; no aplicar log a un parámetro de signo desconocido.
- Objetivos no monomiales que no soporte el transformador inicial se conservan como pendientes con motivo. No introducir un solver numérico de escalas que seleccione una raíz silenciosamente.

### 4.5 Grupos adimensionales y alternativas

El espacio nulo de la matriz dimensional permite obtener bases de productos adimensionales; una base no es única y sus elementos no tienen por qué ser los grupos más útiles físicamente.

Separar dos operaciones:

1. Encontrar productos adimensionales compatibles con los símbolos declarados.
2. Transformar las ecuaciones y obtener sus coeficientes efectivos, con las escalas elegidas.

Buckingham-Π no sustituye la regla de la cadena, el tratamiento de sumas ni la transformación de fronteras. Mostrar grupos calculados con sus definiciones; usar un nombre convencional solo cuando coincida con su definición.

Generar alternativas bajo un presupuesto explícito. Eliminar duplicados algebraicos simples, pero no declarar equivalencia global si no puede demostrarse. Permitir invertir o cambiar una base de grupos sin perder el mapa hacia las variables originales. No puntuar una forma como “más física” sin un criterio declarado.

### 4.6 Condiciones y verificación

- Transformar también geometría, intervalos temporales, condiciones iniciales y fronteras disponibles.
- Un flujo prescrito y una concentración prescrita tienen transformaciones distintas; preservar el tipo de condición.
- Guardar transformaciones directas e inversas y restricciones de dominio.
- Para cada paso publicar regla aplicada, expresión anterior/posterior y supuesto requerido.
- Comprobar dimensiones y equivalencia mediante sustitución inversa en el alcance algebraico soportado.
- Si la equivalencia simbólica no se puede decidir, publicar “no demostrada”, con comprobaciones numéricas auxiliares separadas; muestrear puntos no constituye una demostración.
- No eliminar términos pequeños automáticamente. Esa reducción sería un análisis asintótico posterior, con una hipótesis adicional.

## 5. Página y experiencia

Una página independiente con documentos guardables. Cada documento contiene un modelo original y varias transformaciones de ese mismo modelo.

**Izquierda:** ecuación original, ecuación transformada y desglose vertical desplegable. Ecuaciones horizontales mientras quepan, con desplazamiento lateral cuando sea necesario.

**Derecha:** tabla compacta de símbolos con dimensión/unidad y escala; selección de objetivos de normalización. Mostrar solo los símbolos presentes. Permitir fijar/liberar una escala y elegir qué variables transformar.

**Comparación:** pestañas o columnas para alternativas, con las diferencias de escalas y grupos. Una transformación parcialmente normalizada se identifica como tal. No convertirla en una ecuación completamente adimensional solo mediante la etiqueta.

**Estado breve:** dimensiones correctas / datos dimensionales pendientes / objetivos incompatibles / transformación verificada. Detalles del rango, restricciones, certificados y errores bajo opciones avanzadas.

Acciones: transformar, duplicar forma, deshacer/rehacer, comparar y exportar. Exportar JSON del modelo/transformación, LaTeX y definiciones de los grupos. Conservar la identidad del original y la trazabilidad de cada rama; no imponer un recorrido de pasos preestablecido.

No añadir resolución, gráficos de soluciones, termodinámica, plantillas de equipos o explicaciones extensas a la vista principal.

## 6. Reutilización y responsabilidades

| Pieza existente | Reutilización | Ampliación necesaria |
|---|---|---|
| `app/motor/expresionesMotor.ts` | Sintaxis segura y expresiones escalares | Árbol de operadores y semántica dimensional; no basta sustituir texto |
| `app/motor/unidadesMotor.ts` | Conversiones compatibles y manejo de temperatura | Álgebra de dimensiones generales, no una lista fija de magnitudes |
| `app/motor/operadores.ts` | Definiciones/presentación de operadores | Representación simbólica transformable; el LaTeX no es la fuente matemática |
| Historiales y presentación de `/motor` | Patrones de deshacer, ramas y renderizado | Documentos independientes y varias transformaciones del mismo original |
| Lectores/verificadores | Validación de contratos y pruebas negativas | Certificados de transformación y equivalencia, separados de validación física del modelo |

Claude: núcleo matemático, reglas, pruebas de transformaciones y contratos canónicos si se expone mediante API. Codex: interfaz, lectores, persistencia y exportaciones. No duplicar el núcleo simbólico en cliente y servidor.

Primero acordar el modelo de datos tipado y su ubicación ejecutable. No crear endpoints provisionales ni un segundo motor científico en el navegador para adelantar la entrega. El frontend puede diseñarse con entradas declaradas, sin publicar resultados simulados como si los hubiese calculado el núcleo.

Los documentos de esta herramienta no son hojas del simulador. Compartir piezas puras cuando proceda, sin migrar documentos existentes ni alterar los cálculos actuales. Sin cambios de dependencias incidentales, commit o push.

## 7. Fases y criterios de salida

| Fase | Entrega | Criterio para avanzar |
|---|---|---|
| A0 | Inventario de piezas reutilizables y contrato de símbolos, ecuaciones, dimensiones, escalas, objetivos y resultados | Dos expresiones distintas usan el mismo esquema; ausencia de escala/dimensión tiene representación explícita; roles y límites acordados |
| A1 | Análisis dimensional y lenguaje inicial | Distingue compatible, incompatible e indeterminado; unidades equivalentes producen el mismo modelo dimensional; rechazos señalan término y símbolo |
| A2 | Transformación por escalas multiplicativas dadas | Derivadas, fuentes, coeficientes variables y condiciones se transforman; inversa recupera el original; normalización parcial explícita |
| A3 | Escalas libres, objetivos y múltiples formulaciones | Obtiene las formas de §3 sin código específico; detecta incompatibilidades y presenta familias cuando faltan elecciones |
| A4 | Sistemas de varios campos y grupos Π alternativos | Escalas de campo independientes, tiempo/espacio comunes; no desaparecen cocientes de difusión; cambio de base trazable |
| A5 | Transformaciones afines constantes y ampliación acotada de expresiones | Desplazamientos y escalas de temperatura correctos; funciones no admitidas producen diagnóstico; signos y dominios conservados |
| A6 | Interfaz completa, persistencia, comparación y exportación | Recorrido sin explicaciones obligatorias; editar el original invalida las transformaciones anteriores; importación valida versión y estructura |

La UI mínima puede avanzar junto con A1/A2 usando el contrato publicado. El cierre de A6 exige todas las verificaciones del núcleo; no adelantar varias pantallas llenas de resultados de ejemplo.

### Primera entrega concreta

**A0 + A1 + transformación mínima verificable de A2:** una ecuación escalar con derivada temporal, difusión y expresión fuente escrita por el usuario; dimensiones declaradas, escalas dadas y resultado con sus pasos. Incluir desde el contrato variables parcialmente transformadas y varias transformaciones guardadas, aunque la selección automática de escalas llegue en A3.

No limitar las estructuras a un componente o a esa ecuación; limitar las capacidades implementadas y publicarlas. A3 es obligatorio para cumplir la petición de varias formas controlables, no una mejora opcional al final.

## 8. Pruebas de aceptación

- [x] Temporal sin espacio: fuente constante, término lineal y término no lineal.
- [x] Difusión con fuente y varias elecciones de tiempo/campo/longitud.
- [x] Dos campos con distintas difusividades; conserva la razón entre ellas cuando corresponde.
- [x] Sistema de tres o más campos, sin algoritmos por número de componentes ni nombres de especie.
- [x] Cinética polinomial, racional y exponencial dimensionalmente válidas, introducidas como expresiones.
- [x] Una cinética de reacción-difusión usada en patrones, exclusivamente como caso de prueba del lenguaje general.
- [ ] Difusividad dependiente del campo; conserva divergencia y todos los términos al expandir, si se solicita. *(Núcleo: la divergencia y `D(c)` se conservan y certifican; falta la expansión a petición.)*
- [x] Condiciones iniciales, Dirichlet, flujo prescrito y condición mixta dentro del alcance declarado.
- [x] Normalización parcial frente a completa; ninguna variable dimensional se etiqueta como adimensional.
- [x] Objetivos compatibles, dependientes e incompatibles, con las mismas ecuaciones originales.
- [x] Coeficiente cero, signo negativo/desconocido y escala singular; sin divisiones inválidas ni escalas negativas ocultas.
- [x] Unidades equivalentes y cambio entre bases dimensionales equivalentes.
- [x] Temperatura absoluta y diferencia de temperatura; transformación afín cuando A5 esté disponible. *(Núcleo: `degC` sigue sin admitir escala multiplicativa; `T = T_ref + ΔT θ` con `T_ref = 25 degC` (298.15 K) se certifica.)*
- [x] Argumentos inválidos de exp/log y sumas con dimensiones incompatibles.
- [x] Parámetros con dimensiones inferibles, indeterminadas y contradictorias.
- [x] Inversa recupera ecuación, condiciones y dominio; muestra las restricciones de la demostración.
- [x] Alternativas distintas no pierden parámetros: pueden trasladarse a grupos o fronteras, no desaparecer.
- [x] Persistencia, edición, ramas, exportación e invalidación; ninguna modificación de hojas del simulador. *(Integración Codex: documentos v1/v2, mapas por forma, resultados ligados a revisión y elecciones, exportación del desarrollo.)*

Las casillas científicas las demuestra la suite del núcleo (`python tests/validar_adimensionalizacion.py`). La integración actual añade lector, API y presentación del desarrollo real en la interfaz; persistencia y edición se verifican con las suites del cliente y el recorrido local descrito al final de §9.

Las muestras numéricas sirven como pruebas auxiliares del transformador, sin integrar ecuaciones ni afirmar que el modelo físico sea adecuado para una aplicación.

## 9. Registro de avance

| Hito | Estado | Evidencia / pendiente |
|---|---|---|
| Plan | En ejecución parcial | Avances registrados en este mismo documento; no se inicia ni cierra F3 |
| A0 | Contrato adoptado por API y lector | `contratoNucleo.ts`, `lecturaNucleo.ts` y `backend/api_adimensionalizacion.py`; valida los 16 pares canónicos. Documento local v2 con adaptador explícito al intercambio v1 |
| A1 | Implementado en el núcleo | `core/adimensionalizacion/dimensional.py`: inferencia racional exacta, compatible/incompatible/indeterminado con rutas, datos indispensables, unidades con pint |
| A2 | Implementado en el alcance declarado | Escalas constantes y positivas, regla de la cadena, operadores cartesianos, `D(c)` conservado, condiciones y dominios, normalización parcial, certificado por sustitución inversa |
| A3 | Implementado para objetivos monomiales | Rango exacto: escalas determinadas, relacionadas y libres; objetivos dependientes, incompatibles con responsables, y pendientes. Las cinco formas de §3 salen del mismo algoritmo. Los objetivos no monomiales quedan pendientes |
| A4 | Alcance del núcleo integrado | Sistemas de N campos con tiempo y espacio comunes; inventario Π con bases alternativas y cambio de base verificado. La interfaz presenta grupos y cobertura, sin afirmar que enumera todos los productos posibles de una base |
| A5 | Implementado en el núcleo para mapas algebraicos | Mapas afines (con referencia, incluida temperatura en `degC`) y no lineales invertibles por variable, con la inversa demostrada y la regla de la cadena desarrollada. No incluye cambios de coordenadas acoplados ni curvilíneos |
| A6 | Integrado para el alcance matemático implementado | Hojas independientes, entrada mínima, capa dimensional dinámica, datos indispensables, cálculo real, resultado final y comparación de formulaciones, desarrollo exhaustivo accesible, cancelación/continuación, vigencia, persistencia v2 y exportaciones JSON/LaTeX. Los mapas generales se declaran en Avanzado; su selección automática sigue pendiente |
| Verificación de contrato | 103 casos de documento y 73 de integración | `verificar_adimensionalizacion.mjs` y `verificar_integracion_adimensionalizacion.mjs`: los 16 pares, 782 pasos reales renderizados, mapas v2, migración, exportación, vínculos y respuestas alteradas rechazadas. No sustituyen la aceptación científica del núcleo |
| Verificación de interfaz | Correcta en navegador local | Ecuación nueva → unidades indispensables → resultado real; ejemplo con D,k,a positivos → 8 formulaciones verificadas → selección de Forma 8 y desarrollo. `adimensionalizacion-integrada-preview.png`. TypeScript y ESLint correctos |

### Implementación Codex del 16 de octubre de 2026

Inventario revisado antes de implementar:

- `app/motor/expresionesMotor.ts`: parser seguro de expresiones escalares con variables por nombre y evaluación numérica. No tiene derivadas ni dimensiones generales; no se extiende ni se copia como núcleo simbólico nuevo.
- `app/motor/unidadesMotor.ts`: catálogo fijo de magnitudes y conversiones con desplazamiento de temperatura. No representa álgebra dimensional racional general; no se usa para certificar las entradas nuevas.
- `app/motor/operadores.ts`: operadores y presentación ligados a coordenadas y opciones del motor actual. Se conserva intacto; el contrato nuevo representa operadores mediante nodos y referencias.
- `core/dimensiones.py`: análisis dimensional existente basado en Pint y expresiones del ensamblaje. Es una posible pieza reutilizable para el responsable del núcleo, pero no transforma el AST propuesto ni prueba equivalencia inversa. No se ha modificado.
- Patrones existentes de historial y renderizado: se mantiene la interacción de deshacer/rehacer y el desplazamiento horizontal de ecuaciones. El documento nuevo tiene su propio historial y clave `adimensionalizacion.documento.v1`; no usa hojas ni documentos del simulador.

Ubicación ejecutable actual: `app/adimensionalizacion/contrato.ts` contiene los tipos de intercambio; `documento.ts` valida exclusivamente estructura/referencias y administra documentos; `exportar.ts` presenta el AST original en LaTeX; `Editor.tsx` contiene la interfaz. No hay evaluación científica en estos archivos. El núcleo futuro debe consumir el árbol canónico y publicar su alcance/capacidades antes de conectar el botón Transformar. `ResultadoNucleo` propone los resultados y certificados requeridos; todavía no hay lector de respuestas ni resultados persistidos porque no existe un productor acordado.

`dimension: null` indica dato dimensional pendiente y `{}` indica dimensión uno; ausencia de elección de escala o `valor.tipo: libre` conserva la libertad. Los exponentes se intercambian como racionales `{n, d}` con denominador entero positivo. Las funciones opacas llevan dimensiones de entrada/salida y dependencias declaradas. La validación de esas declaraciones es estructural: incluso `exp(c)` con c dimensional sigue pendiente del análisis A1, nunca se presenta como validada físicamente.

Las entradas temporal y espacial son modelos declarados editables, no resultados calculados ni ramas específicas de transformación. Los símbolos presentes se muestran en tabla; las escalas simbólicas y objetivos se declaran mediante el editor JSON de forma. La edición del original conserva su identidad, incrementa la revisión y deja las formas anteriores desactualizadas; confirmar una revisión no certifica la transformación. La comparación muestra únicamente elecciones guardadas. No se exportan grupos o ecuaciones transformadas inventados. Las conversiones de unidades, inferencia dimensional, transformaciones afines y verificaciones de signos simbólicos siguen pendientes.

Comandos de comprobación ejecutados desde `frontend`: `node verificar_adimensionalizacion.mjs`, `npx tsc --noEmit --incremental false` y `npx eslint app/adimensionalizacion`. La comprobación manual en `http://localhost:3000/adimensionalizacion` verifica carga, fijación de escala, duplicación, comparación y persistencia tras recarga. Se añadió el acceso en navegación y se oculta la barra del documento del simulador en esta ruta; no se modificaron `/motor`, `/laboratorio`, física, solvers, dependencias ni documentos existentes. Sin commit ni push.

**Siguiente entrega necesaria:** acordar el contrato con el responsable Claude y ejecutar A1/A2 en una única ubicación científica, aprovechando piezas puras del backend cuando proceda. Publicar un lector validado de respuestas que enlace la revisión del modelo y todas las elecciones de forma, antes de mostrar ecuaciones transformadas, pasos o certificados. Después, A3 sigue siendo obligatorio. No se da por cerrada A0, la primera entrega concreta ni A6 con esta preparación de interfaz.

### Presentación LaTeX solicitada el 16 de octubre de 2026

Ecuaciones originales, dominios, condiciones, dimensiones, escalas, comparación y objetivos se presentan mediante el componente KaTeX existente `FormulaLatex`, con desplazamiento horizontal. El AST sigue siendo la fuente matemática. El botón «Documento LaTeX» descarga un documento completo con preámbulo, modelo, dimensiones y elecciones de todas las formas; no incluye resultados calculados inexistentes. El documento independiente `../../../frontend/documentos/adimensionalizacion/main.tex` contiene las cinco formulaciones de referencia del plan, regla de la cadena, dominios, condiciones, difusión variable, escalas de varios campos, temperatura afín y signos. Estas referencias no se presentan como cálculos del núcleo pendiente. Se verificaron 46 casos del lector/presentación y ESLint; se comprobó visualmente el renderizado en la ruta local.

La compilación de `../../../frontend/documentos/adimensionalizacion/main.tex` fue correcta con el compilador integrado de la aplicación. La verificación TypeScript completa también pasó.

### Claridad de uso y entrega para Claude

Se preparó `docs/history/frontend/delivery-claude-nondimensionalization.md` por petición expresa del usuario: entrada técnica, estado real, archivos, decisiones de contrato pendientes y criterios de entrega para el núcleo, con mensaje de arranque. No sustituye este plan ni se ha enviado a otro chat automáticamente.

La presentación respeta precedencia, conserva paréntesis necesarios, muestra productos y restas de forma convencional y pone el campo dentro de la derivada. Los cambios afectan solo a la representación del AST: no alteran el modelo ni ejecutan la transformación. Los seis nuevos casos de presentación verifican signos, potencias agrupadas, productos con sumas y ausencia de mutación; total de 52 casos correctos. La interfaz añade una guía breve con accesos directos, una vista de las sustituciones elegidas, estados de escala libre/fijada/dimensional y nombres de acciones más explícitos. La tabla dimensional queda desplegable para dar prioridad a los controles de escala. Se comprobó en navegador el acceso directo a escalas; el cálculo sigue identificado como no disponible.

### Exploración más amplia y automática solicitada por el usuario

La entrada principal incorpora `ExploracionAutomatica.tsx`. `exploracion.ts` prepara solicitudes combinatorias a partir de todos los términos aditivos explícitos de ambos lados del AST, incluidos los temporales, sin preferencia por cinética o especie. Enumera representantes sin objetivos nuevos y subconjuntos de términos hasta una cota y presupuesto explícitos. No desarrolla productos, extrae coeficientes, resuelve objetivos ni calcula dimensiones/grupos. Los objetivos de la solicitud piden normalizar magnitudes de coeficientes efectivos, conservando el signo; el núcleo deberá separar los objetivos dependientes del factor residual global.

El ejemplo con cuatro términos produce 15 propuestas hasta tres objetivos, o 16 hasta cuatro: todas están marcadas «sin evaluar». Esos números cuentan combinaciones sintácticas, no formulaciones admisibles. La UI permite fijar presupuesto, objetivos simultáneos, respeto a escalas fijadas y solicitud de grupos Π con cotas de exponentes/denominadores, inversos y bases alternativas. Las preferencias se conservan en el campo opcional `Documento.exploracion` y se validan al importar; los documentos v1 anteriores siguen admitidos. La solicitud exportada contiene una copia del original y de la forma, criterios, inventario, propuestas y cobertura; no es un documento de resultados ni existe un endpoint conectado.

Se actualizó `docs/history/frontend/delivery-claude-nondimensionalization.md` con esta prioridad: buscar representantes y familias, resolver por rango, mantener signos/ceros/geometría, deduplicar con evidencia y declarar límites/continuación. Se distinguen el presupuesto de preparación actual y los presupuestos científicos que deberá implementar el núcleo. La búsqueda Π y las formulaciones calculadas siguen pendientes; no se ha duplicado el núcleo en el navegador ni se han integrado resultados simulados. Las pruebas de contrato/preparación/presentación suman 75 casos correctos, con TypeScript y ESLint. Verificación manual: el selector hasta cuatro objetivos pasa de 15 a 16 propuestas y la tabla mantiene el estado «Sin evaluar».

### Vista principal mínima y ampliación de familias

El usuario pidió literalmente introducir una ecuación y pulsar «Adimensionalizar», y rechazó el bloque de sustituciones multiplicativas como punto de partida obligatorio. Se retiraron de la vista principal el recorrido, las tablas, escalas, sustituciones, ramas y presupuestos; permanecen dentro de «Avanzado» salvo el bloque «Tus sustituciones», que se eliminó. La vista principal usa `EntradaSimple.tsx`: texto de ecuación o sistema, ayuda de sintaxis desplegable, vista previa LaTeX y un botón.

`entradaEcuaciones.ts` incorpora lectura sintáctica segura de ecuaciones al AST (sin evaluación, transformación o inferencia dimensional): operadores explícitos, expresiones escalares, funciones opacas y sistemas. Conserva declaraciones conocidas; los símbolos nuevos tienen dimensiones pendientes y los nombres de las coordenadas no se interpretan como dimensiones físicas. Hay límites de tamaño/profundidad y errores locales. El texto puede contener relaciones afines, cocientes o funciones no lineales, sin que la lectura certifique su invertibilidad o validez dimensional.

Por ahora pulsar el botón guarda la ecuación, invalida los objetivos del original editado y comunica que la transformación no se ha calculado por falta de núcleo. No hay una solicitud científica enviada, ni resultados de ejemplo presentados como cálculos. La interfaz principal no exige escalas o JSON para escribir el modelo; el núcleo deberá inferir lo determinable y solicitar solo los datos indispensables faltantes.

La petición funcional posterior amplía el objetivo más allá de las escalas multiplicativas de la primera entrega: familias afines, cocientes de referencia, grupos Π/bases y transformaciones no lineales invertibles dentro de dominios explícitos. No se afirma soporte científico actual para ellas. Se actualizó `docs/history/frontend/delivery-claude-nondimensionalization.md` para acordar mapas directos/inversos generales y capacidades por familia, incluyendo las reglas de cadena y términos adicionales necesarios, conservando dominios/condiciones. La sintaxis de entrada y la presentación no sustituyen esas reglas. Verificación: 103 casos de contrato/preparación/lectura/presentación correctos; revisión de la interfaz mínima en navegador y entrada de `u = (T - Tref)/DT` con vista previa sin sustitución multiplicativa prefijada.

### Implementación Claude del núcleo, 16 de octubre de 2026

**Ubicación única:** `core/adimensionalizacion/` (Python). Usa aritmética exacta con `fractions` y pint para unidades. Sin dependencias nuevas: sympy no está en `requirements.txt` y no se usa. No se modificaron `/motor`, `/laboratorio`, sus ecuaciones, solvers, termodinámica, `core/dimensiones.py` ni el código del cliente. Sin endpoint. Sin commit ni push. El contrato completo está en `docs/contracts/nondimensionalization-core.md`.

**Alcance implementado.**

- A1: dimensiones racionales con incógnitas para `null`. El `0` vale como comodín y los demás números son adimensionales. Se aplican las reglas de exp/log/trig, abs, min/max, potencias y llamadas, y la semántica escalar/vectorial (`rango`). Con todo pendiente, `faltantes` da el conjunto mínimo de dimensiones a pedir, preferentemente de variables. Esto responde a la vista mínima: en el ejemplo de §3 basta declarar `c`, `t` y `x`.
- A2: `v = v_ref · v'` sobre lo que el usuario elija transformar. Regla de la cadena en derivadas y operadores. Los operadores de varias coordenadas con escalas por coordenada se desarrollan en componentes cartesianas. Funciones declaradas y coeficientes variables se conservan. El factor global de cada igualdad se separa de las escalas. Las escalas pueden ser libres, una cantidad con unidad (convertida a SI) o una expresión de parámetros (constante, con su dimensión y signo comprobados). Se transforman dominios y condiciones (inicial, Dirichlet, flujo, mixta) conservando su tipo. Pasos `antes`/`después` en cada regla.
- A3: cada objetivo `|coeficiente efectivo| = 1`, con signo exigido o conservado, es una fila racional sobre log(escalas). Se resuelve con eliminación exacta y orden de pivote publicado: tiempo, campos, coordenadas. Parámetros negativos → `abs(p)` en la escala y el signo en la ecuación. Signo desconocido → pendiente. Parámetro nulo → incompatible, sin dividir por él.
- Exploración: el núcleo acepta la `solicitud_exploracion_adimensional` v1 del cliente, evalúa cada propuesta, elimina duplicados demostrables (igualdades, condiciones y dominios canónicos) y declara cobertura y continuación. Grupos Π: espacio nulo racional, bases alternativas bajo presupuesto y cotas, inversos tratados como el mismo grupo, mapa a la base de referencia verificado.

**Condiciones del certificado.** `demostrada` = la sustitución inversa de lo **publicado**, multiplicada por el factor global, tiene la misma forma canónica cartesiana que el original (ecuaciones, condiciones y dominios). Además las dimensiones de cada igualdad publicada concuerdan y cada objetivo aplicado vale lo pedido.

- Identidades admitidas: conmutatividad, distributividad, `a^p a^q = a^(p+q)`, `(ab)^q = a^q b^q` solo con `q` entero o factores positivos, linealidad de operadores y `d^m(d^n f) = d^(m+n) f`.
- No se usan la regla del producto, identidades de exp/log/trig ni el intercambio de derivadas mixtas. Coordenadas cartesianas.
- Restricciones tipadas: escalas `positivo`, factores `no_nulo`, `signo` declarado usado, `igualdad` de escalas resueltas.
- No se muestrean números. Una prueba confirma que el certificado detecta un término perdido.

**Evidencia.**

- `python tests/validar_adimensionalizacion.py`: 148 comprobaciones correctas, también incluidas en `python run_tests.py`.
- Cobertura de la suite:
  - contrato: rechazos con ruta; vínculo y firma (cambia al cambiar una escala de la misma forma);
  - dimensiones: inferencia, indeterminación y contradicción, datos indispensables, unidades equivalentes, bases `{L,T,N}`/`{L,T,C}` con idéntico resultado;
  - §3: las cinco formas con sus escalas y familias; `L = √(D/k)` trasladando `ell` a la geometría (`ξ ∈ [0, ell√(k/D)]`);
  - objetivos: dependientes, incompatibles con responsables y relación, signos y ceros;
  - modelos: `D(c)`, cinética racional (`K/c_ref` como grupo interno), exponencial, 2D, sistemas de 2 y 4 campos, patrones, condiciones;
  - exploración (15 propuestas → 8 formulaciones distintas y 7 duplicados, todas certificadas) y Π (rango 3, un grupo, dos bases).
- Una prueba aleatoria de 3000 documentos mutados no produjo excepciones ni resultados con ecuaciones tras un fallo.
- Ejemplos canónicos: `docs/ejemplos/adimensionalizacion-*-{solicitud,resultado}.json`, 12 pares regenerables con `python tests/generar_ejemplos_adimensionalizacion.py` y comprobados por la suite.
- El cliente sigue verde: `node verificar_adimensionalizacion.mjs` (103 casos), `npx tsc --noEmit --incremental false` y `npx eslint app/adimensionalizacion`.

**Pendiente.**

- Endpoint (propuesta en §7 del contrato).
- Lector de resultados y conexión del botón (Codex).
- Contrato v2: `terminoId` en objetivos, ubicación de condiciones, escala declarada de funciones, referencias de factor global y prioridad de escalas.
- A5: transformaciones afines y no lineales invertibles pedidas en «Vista principal mínima».
- Objetivos no monomiales.
- Expansión de `div(D(c) grad c)` a petición.
- Escalas dependientes de t/x.
- Coordenadas curvilíneas.

No se marca cerrada ninguna fase de la interfaz (A6).

### Desarrollo matemático y algebraico en la vista principal

El usuario precisó que la entrada simple no debe reducir el contenido del resultado: el objetivo central es ver todo el desglose matemático y algebraico. Se incorporó `DesgloseMatematico.tsx` y la propuesta tipada `PasoDesarrollo`, con expresiones o igualdades completas antes/después, regla, justificación, supuestos y objetos afectados. La traza se muestra abierta en el orden recibido, debajo de la entrada, sin reconstruir pasos en cliente ni imponer una secuencia común a todas las familias. El componente conserva la separación de hipótesis físicas e identidades algebraicas y marca una traza sin pasos como incompleta.

Mientras no exista núcleo conectado, al pulsar «Adimensionalizar» se muestra un estado pendiente del desarrollo, sin fórmulas intermedias inventadas. La entrega para Claude exige la traza completa de sustitución, regla de la cadena, factorización, cancelaciones justificadas, agrupación, normalización, simplificación, geometría/condiciones e inversa, con exportación de los pasos. La propuesta de contrato sigue pendiente de acuerdo y lectura científica validada.

El usuario confirmó que Claude ya trabaja en el núcleo. Se han detectado archivos de `core/adimensionalizacion` y pruebas en desarrollo; no se han modificado ni se afirma validada o terminada esa entrega. El componente de presentación mantiene compatibilidad con el tipo básico anterior de pasos y admite una extensión opcional `desarrollo` propuesta, que deberá adaptarse al protocolo real al integrar. El avance de esta aclaración corresponde solo al renderizado y no implica que el cálculo esté conectado.

### Ampliación Claude: entrada simple, familias generales y desarrollo completo, 16 de octubre de 2026

Responde a las dos últimas correcciones de `docs/history/frontend/delivery-claude-nondimensionalization.md`: entrada mínima con familias más generales, y desarrollo exhaustivo. El contrato está en `docs/contracts/nondimensionalization-core.md` §10.

**Búsqueda automática (`operacion: "adimensionalizar"`).** Con solo la ecuación, el núcleo:

- analiza las dimensiones y, si faltan datos, responde `requiere_datos` con lo indispensable (por ejemplo `c, t, x`);
- transforma todas las variables con escalas libres;
- recorre todos los subconjuntos **independientes** de coeficientes efectivos normalizables, de modo que el recorrido es completo para esa familia;
- elimina duplicados y certifica cada formulación.

Hay presupuesto, continuación reproducible (`desde`/`siguiente`) y cobertura declarada, con los términos excluidos y su motivo. En el ejemplo de §3 salen 8 formulaciones sin configurar nada, entre ellas las cinco del plan. No inventa referencias: una variable en `degC` produce el aviso `requiere_referencia`.

**Mapas generales.** El contrato `Transformacion` declara la directa `v = g(v′)`, la inversa `v′ = h(v)`, las constantes (escalas o referencias, con dimensión inferida) y los dominios.

- Familias: multiplicativa, afín y no lineal, publicadas por mapa y por capacidad.
- La invertibilidad se **demuestra** componiendo `h∘g` y `g∘h` en forma canónica con los dominios declarados. Por ejemplo, `c = C u²` sin `u > 0` se rechaza, porque `(u²)^½ = |u|`.
- Campos no lineales: la regla de la cadena se desarrolla con todos sus términos (`c = C e^u` da `(∂u/∂ξ)²`).
- Tiempo y coordenadas no lineales, por coordenada: `d/dv = (1/g′) d/dv′`, anidado para órdenes superiores, con la restricción `no_nulo` del jacobiano. Los dominios se transforman con `h`.
- El álgebra gana un modo `expandir` (reglas del producto, de la potencia y de la cadena; `log(exp y) = y`; `exp(log y) = y` solo con `y > 0` declarado). La nulidad se decide multiplicando por los denominadores, que no son nulos porque el original divide por ellos. El texto de `equivalencia.alcance` se actualizó para describir exactamente estas identidades.

**Desarrollo.** Cada formulación publica `desarrollo: PasoDesarrollo[]` con el tipo propuesto por Codex. Los pasos siguen el orden real del cálculo:

1. dimensiones e inferencia;
2. mapas, inversas demostradas y jacobianos;
3. sustitución y regla de la cadena de cada término;
4. la igualdad antes de cancelar factores;
5. la división, con su condición de no nulidad;
6. la agrupación;
7. cada objetivo, cada escala despejada por rango y cada escala libre;
8. la sustitución de escalas;
9. la factorización y la definición de cada grupo;
10. dominios y condiciones;
11. la sustitución inversa hasta recuperar el original.

No se emiten hipótesis físicas. La suite valida el formato y que toda referencia resuelva, como deberá hacerlo el lector.

**Evidencia.**

- `python tests/validar_adimensionalizacion.py`: 199 comprobaciones correctas, también en `python run_tests.py`. Las nuevas cubren mapas log, potencia, afín en `degC`, Arrhenius afín, tiempo logarítmico (incluida una segunda derivada), coordenada `x = L(e^ξ − 1)` con dominio `[0, log(1 + ell/L)]`, inversas falsas o no demostrables rechazadas, A3 sobre mapas no lineales, búsqueda automática completa con continuación, `requiere_datos`, signos desconocidos excluidos, sistemas de dos campos, la traza y la cancelación por denominadores.
- Prueba aleatoria: 2000 mutaciones sobre los 15 tipos de solicitud, sin excepciones.
- 16 pares de ejemplos canónicos (nuevos: `automatico`, `requiere-datos`, `mapa-logaritmico`, `mapa-afin-temperatura`).
- El cliente sigue verde (103 casos, TypeScript y ESLint).
- No se modificó código del cliente, `/motor` ni `/laboratorio`. Sin dependencias nuevas, commit ni push.

**Pendiente.**

- Endpoint (§7 del contrato) y conexión del botón «Adimensionalizar» con lector y validación de vigencia (Codex).
- Contrato v2 del documento (`Forma.transformaciones`, `terminoId`, ubicación de condiciones).
- Selección automática de mapas no lineales: el núcleo no propone log ni potencias por su cuenta.
- Cambios de coordenadas acoplados o curvilíneos, y escalas dependientes de t/x.
- Objetivos no monomiales.

### Integración Codex del núcleo y desarrollo exhaustivo

La entrega de Claude queda conectada mediante `GET /api/adimensionalizacion/capacidades` y `POST /api/adimensionalizacion`. La envoltura HTTP limita el cuerpo a 1 MB y mantiene todo el cálculo científico en `core/adimensionalizacion/`, sin modificarlo. La URL específica `NEXT_PUBLIC_ADIMENSIONALIZACION_API_URL` permite probar el servicio integrado junto a otro backend local ya abierto.

El botón «Adimensionalizar» envía el documento y los mapas declarados de la forma activa, consulta solo las dimensiones indispensables y muestra formulaciones calculadas, escalas libres/determinadas, objetivos, grupos, restricciones, condiciones, dominios y la comprobación inversa. El desarrollo completo aparece abierto en la vista principal, con cada igualdad antes/después, regla, justificación y supuestos recibidos. No se crean pasos ni certificados en el navegador. La búsqueda conserva presupuesto, exclusiones y continuación; la cobertura siempre se limita a la familia que declara el núcleo.

La vigencia compara documento, modelo, revisión, texto actual, elecciones, mapas y opciones; una respuesta tardía o un resultado previo no se presenta sobre una edición nueva. Deshacer/rehacer también renueva la revisión de la vista, evitando recuperar un borrador de texto antiguo al volver a una ecuación anterior. Un signo desconocido se conserva como tal: el ejemplo solo produce las ocho formas cuando las hipótesis positivas de D,k,a están declaradas, no por inferencia del cliente.

Documento v2: `Forma.transformaciones` conserva directa, inversa, constantes y dominios en importación, ramas, almacenamiento local, JSON y LaTeX. Los documentos v1 se migran explícitamente sin alterar el modelo. Para el servidor se genera una copia v1 y se trasladan los mapas al campo previsto en la solicitud. La exportación calculada incluye solicitud/respuesta JSON y un `.tex` con todos los pasos. Los resultados se recalculan después de recargar, en lugar de reactivar certificados almacenados sin comprobar.

**Verificación de integración:**

- Suite científica de Claude: `python tests/validar_adimensionalizacion.py`, correcta.
- Cliente: 103 comprobaciones de documento y 73 de integración; 16 pares canónicos, 782 pasos reales renderizados por KaTeX sin errores y respuestas alteradas rechazadas.
- API: capacidades, JSON inválido/NaN, límite de tamaño, rechazos, ocho formulaciones, continuación, datos mínimos y mapas logarítmico/afín.
- TypeScript sin emisión y ESLint de `app/adimensionalizacion`, correctos.
- Navegador local: ecuación nueva `d(y,s)=beta*y`, solicitud únicamente de unidades de `y,s`, cálculo real; después ejemplo de difusión con D,k,a positivos, ocho alternativas y selección de Forma 8.
- El documento LaTeX exportado para Forma 8 contiene sus 30 pasos y compila correctamente con el compilador integrado.

**Pendientes de alcance:** generación automática de mapas no lineales, coordenadas acopladas/curvilíneas, escalas variables, objetivos no monomiales y las ampliaciones de modelo enumeradas en §8 del contrato (ubicación de fronteras, escala de funciones, referencias y prioridades). La versión local 2 no activa esas ampliaciones. No se añadieron dependencias, commits ni push.

Los apartados anteriores de este registro conservan la situación de sus entregas originales; las menciones históricas a «sin endpoint» o «núcleo pendiente» quedan superadas por esta integración.

### Capa dimensional, sistemas y cuaderno de hojas

**Decisión matemática.** La homogeneidad exige dimensiones iguales entre los sumandos y ambos miembros de cada igualdad; no exige la misma dimensión para todas las ecuaciones de un sistema. Los nombres no determinan magnitudes físicas y los datos insuficientes deben permanecer pendientes. Las dimensiones de los parámetros compartidos y sus grupos se resuelven sobre el sistema completo.

**Implementación.** La interfaz incorpora una capa dimensional visible: unidades editables, identificación de magnitudes compatibles (concentración, volumen, masa, tiempo, difusión, etc.), roles matemáticos corregibles y operadores detectados. Las consultas dinámicas al endpoint `/api/adimensionalizacion/dimensiones` muestran el análisis real por término y se invalidan al editar. La unidad se interpreta con el registro de pint del núcleo, con aliases de entrada explícitos y notación de potencias. Las unidades no reconocidas o no comparables bloquean cualquier resultado publicado. No se modificó `core/adimensionalizacion/` ni se creó álgebra dimensional en cliente.

El cuaderno ofrece hojas independientes, nombres, duplicación, archivo recuperable, selección, exportación/importación y migración del documento anterior. También conserva los borradores aún no calculados o sintácticamente incompletos. El almacenamiento está aislado de las hojas del motor Rage. Cada hoja admite una ecuación o un sistema; no se crea una hoja por ecuación de un mismo sistema.

El cálculo abre una vista dedicada de **resultado final**, con todas las igualdades, grupos y escalas. Se mantienen accesos al desarrollo completo y la comparación de alternativas. La selección inicial corresponde a una alternativa con menos escalas libres, sin quitar las demás ni imponer signos. El ejemplo editable de dos campos permite comprobar relaciones entre ecuaciones; no incorpora fórmulas de resultado precalculadas.

**Evidencia.**

- Nueva prueba API `python tests/validar_capa_dimensional.py`: términos con varias variables, unidades equivalentes, `Kg`, `L`, `mol/L`, detección de magnitudes y operadores, ecuaciones con dimensiones distintas, datos pendientes, incompatibilidad y unidades inventadas bloqueadas. Un sistema de dos campos produce 12 formulaciones, todas certificadas, y grupos D1/D2 o su inverso calculados por el núcleo.
- `node verificar_capa_dimensional.mjs`: 32 comprobaciones de auditoría real, lector estricto, LaTeX, documento v1 migrado a hoja v2, aislamiento de identidades, borradores, archivo recuperable y roles en igualdades algebraicas. Las 103 de documento y 73 de integración anteriores siguen correctas.
- Navegador: una difusividad declarada en `Kg` marca incompatibilidad; al eliminarla se recupera la inferencia. Un borrador sobrevive al cambio entre hojas y la recarga. La hoja de prueba se archiva sin borrar sus datos.
- TypeScript y ESLint de la ruta correctos. No hay dependencias nuevas, cambios en las hojas del simulador, commit ni push.

El contrato actualizado de esta capa, la política de unidades y el formato del cuaderno quedan descritos en §12 de `docs/contracts/nondimensionalization-core.md`. La compatibilidad dimensional no se presenta como prueba de validez física del modelo ni como conversión numérica de parámetros no declarados.

### Contrato v2 del documento en el núcleo (Claude), 17 de octubre de 2026

El núcleo acepta `documento.version: 2`, es decir, el v2 local del cliente más las cinco ampliaciones pendientes del §8 del contrato. La especificación completa está en el §13 del contrato. Un v1 conserva exactamente su salida: los 16 ejemplos anteriores no cambiaron, y un v1 con campos de v2 se rechaza.

- **`objetivos[].terminoId`:** identifica el coeficiente por el catálogo de `analizar`. Un id inexistente o contradictorio con `termino` deja el objetivo `pendiente`, con su código.
- **`condiciones[].ubicacion`:** la condición publica `lugar`, con la variable nueva, el extremo y su valor transformado, y un paso de traza.
- **`funciones[].escala`:** `D(c) = D* D̂(u)`, con `D̂(w) = D(c_ref w)/D*` publicada en `funcionesAdimensionales`. `[D*]` se infiere de la salida de `D`; el certificado deshace la definición antes de la sustitución inversa; `D*` entra en A3 (`t_ref = x_ref²/D*`), y la normalización de `div(D(c) grad c)` pasa de `parcial` a `completa`. Si las escalas de una misma entrada difieren entre llamadas, se rechaza.
- **`Forma.referencias`:** el factor global sale del término indicado, también en condiciones. Una referencia inválida se rechaza: no se relaja.
- **`Forma.prioridadEscalas`:** decide qué escala se despeja. Por ejemplo, con `["x"]`, `x_ref = (D t_ref)^½` y `t_ref` libre.
- **`Forma.transformaciones`:** el núcleo la lee directamente; si la solicitud trae otra lista a la vez, es un error de contrato.
- **Búsqueda automática:** admite `opciones.referencias` y `opciones.prioridadEscalas`.

**Evidencia.**

- `python tests/validar_adimensionalizacion.py`: 249 comprobaciones correctas (48 nuevas de v2 y 2 ejemplos canónicos nuevos, `v2-funcion-escalada` y `v2-referencias-ubicacion`).
- `python tests/validar_capa_dimensional.py`, correcta.
- Prueba aleatoria de 2000 mutaciones sobre solicitudes v2: sin errores internos.
- Cliente sin cambios y verde: 103 de documento, 73 de integración, 32 de la capa dimensional, TypeScript y ESLint.

No se modificó código del cliente, `/motor`, `/laboratorio` ni dependencias. Sin commit ni push.

**Pendiente (Codex).** Para enviar v2 sin el adaptador hay que actualizar tipos, lector del documento, entradas y exportación con los campos nuevos. En el lector de resultados (§13.3), las llamadas a `D̂` se resuelven contra `funcionesAdimensionales`, y `condiciones[].lugar` es opcional. El adaptador v1 actual sigue funcionando sin cambios.

### Auditoría del frontend y estudios reales (Claude), 17–18 de octubre de 2026

El usuario pidió auditar el frontend que dejó Gemini y hacer reales sus ideas. Informe completo: [docs/history/frontend/audit-nondimensionalization-2026-10-18.md](audit-nondimensionalization-2026-10-18.md).

**Diagnóstico.** La mayoría de los análisis que `ARQUITECTURA_INTEGRACION_MULTIFISICA.md` daba por certificados no se calculaban a partir del modelo:

- regímenes, capa límite y clasificación decidían por subcadenas del id de grupo (`G1`, `G2`…);
- la estabilidad usaba un jacobiano fijo;
- la auditoría de malla, Pe y Da inventados;
- las fronteras eran ficticias y las simetrías de Lie se afirmaban siempre;
- el simulador integraba otra ecuación y ocultaba la divergencia;
- el código exportado y el paquete de publicación eran fijos.

Se retiraron 23 módulos, archivados en `docs/archivo/adimensionalizacion-gemini-2026-10-17/`.

**Implementado.**

- Operación `estudiar` del núcleo (contrato §14), con nueve análisis reales:
  - estructura y lectura de grupos;
  - sensibilidad exacta y valores en SI;
  - balanza dominante de Kruskal con capas límite;
  - escalas, malla y rigidez;
  - simetrías con reducción comprobada a EDO;
  - estabilidad lineal con σ(k), y continuación con pliegues y Hopf;
  - simulación por método de líneas (BDF) de las ecuaciones del usuario, con script de Python exportable.
- Interfaz reescrita: pestañas Resultado, Estudio, Desarrollo y Comparar; informe imprimible solo con lo calculado; cuaderno sin pérdida de datos; tema único.

**Correcciones del núcleo y del cliente.**

- Una suma interna adimensional ya no cede escalas (38 formulaciones «no demostradas» pasan a demostradas).
- Funciones tan, tanh, sinh, cosh, atan y erf en el núcleo.
- El lector de ecuaciones conserva los símbolos de condiciones y dominio.
- 3 ejemplos del catálogo corregidos.

**Evidencia.**

- Python: 264 comprobaciones del núcleo, 55 de estudio contra soluciones analíticas, más las suites dimensional y de API.
- Cliente: 103 + 79 + 33 + 66 comprobaciones, TypeScript y ESLint sin errores.
- Los 21 ejemplos del catálogo calculan con todas sus formulaciones demostradas.
- Recorrido en el navegador con el backend actualizado.

**Pendiente.**

- Reiniciar los backends del usuario (8004/8005).
- Conexión con el motor: [docs/history/frontend/plan-connection-nondimensionalization-engine.md](plan-connection-nondimensionalization-engine.md), fases M1–M4; M1–M3 no modifican el motor.

### Fase M1: hojas de materia del motor (Claude), 18 de octubre de 2026

El motor es el fundamento y la adimensionalización su extensión: ahora lee sus hojas sin modificarlas.

- **Adaptador** `desdeMotor.ts`: hoja de materia → documento v2 con valores en SI. Importa en solo lectura funciones puras del motor (`analizarMotor`, `terminosTotalesMateria`, `analizarExpresion`, `factorUnidad`, `firmaHoja`). Cada literal de una expresión con dimensión es un parámetro con la dimensión que exige la unidad del dato; el núcleo la vuelve a comprobar. Formas: total (masa o volumen), local temporal y campo 1D con convección, difusión (laplaciano, Fick o flujo), fuentes y fronteras de valores, sin flujo o periódicas.
- **Núcleo:** `simulacion.periodica` y `simulacion.tFinalSI` (contrato §14). El tiempo físico se convierte con la inversa publicada del mapa; el cliente no hace álgebra.
- **Interfaz con la estética del motor:** el cuaderno usa `trabajoMotor.module.css` y el tema `balances.module.css` del motor (importados, no copiados). Pestañas Mis hojas · Del motor · Catálogo · Archivadas; la hoja abre con la barra del motor. La simulación de una hoja importada arranca en segundos y con la frontera de la hoja, y muestra una sola cifra: su diferencia con el resultado guardado del motor (solo si la firma de la hoja no cambió). Barra de 28 botones del editor sustituida por «Insertar operador» plegado.
- **Evidencia:** `node verificar_importacion_motor.mjs`, 117 comprobaciones sobre las ocho hojas de prueba del motor (motor, núcleo y solución analítica); estudio 63 (8 nuevas de frontera periódica y `tFinalSI`); núcleo 264; cliente 103 + 79 + 33 + 66; TypeScript y ESLint limpios. Recorrido en el navegador: hoja 08 importada, adimensionalizada, simulada y comparada (0,049 % frente al motor).
- **Hallazgo:** en la hoja 07 (convección pura) el *upwind* de primer orden del motor se separa 8e-3 de la solución exacta y el núcleo 9e-5. No se tocó el motor; queda como dato para la fase M2.

### Cierre del módulo (Claude), 18 de octubre de 2026

El usuario pidió terminar la adimensionalización antes de acoplarla al motor. Alcance cerrado y lo que queda fuera: [docs/nondimensionalization/scope.md](../../nondimensionalization/scope.md).

- La hoja sigue el recorrido del motor: ← Hojas · Ecuaciones · Formulaciones · Estudio · Desarrollo · Comparar. Cada página tiene tarjeta, panel con cifras y botón principal, y usa los módulos CSS del motor.
- Los detalles técnicos y las opciones avanzadas quedan plegados.
- Resultados guardados en IndexedDB (`resultadosAdim.ts`), como el motor; renombrar la hoja no los invalida.
- «Opciones avanzadas» depuradas: búsqueda, escalas fijadas, signos, dominios y condiciones, JSON, importar y exportar. Se retiraron los botones que reemplazaban la hoja con ejemplos y el preparador combinatorio, superado por la búsqueda del núcleo; queda archivado en `docs/archivo/adimensionalizacion-2026-10-18/`.
- Evidencia: las mismas suites en verde (núcleo 264, estudio 63, cliente 103 + 79 + 33 + 66, importación 117, TypeScript y ESLint). Recorrido en el navegador: importar, adimensionalizar, estudiar, simular y comparar con el motor; hoja nueva con unidades pedidas por el núcleo; recarga con el resultado recuperado; 375 px sin desbordamiento.

## 10. Continuidad en otro chat

Conviene un chat separado dentro del mismo proyecto para mantener independientes esta entrega y el roadmap multifísico. Esto no requiere copiar todo el historial ni reiniciar la arquitectura del simulador.

Para retomar el núcleo (Claude) en una sesión nueva, el punto de entrada es `docs/nondimensionalization/continuity.md`: estado, archivos, reglas, pendientes y trampas conocidas. El mensaje de arranque vigente está en ese archivo. El mensaje original de esta sección pedía empezar por A0/A1 y quedó superado: A0–A3, A5 para mapas algebraicos, la búsqueda automática y la traza ya están en el núcleo (ver «Implementación Claude» y «Ampliación Claude» en §9).

## 11. Referencias matemáticas

- [MIT, The Buckingham Pi Theorem in Dimensional Analysis](https://ocw.mit.edu/courses/2-25-advanced-fluid-mechanics-fall-2013/c0a4521f55e9191d557c167e99e97469_MIT2_25F13_The_Buckingham.pdf): matriz dimensional, rango y no unicidad de los grupos.
- [University of Washington, Nondimensionalization of Reaction Diffusion](https://faculty.washington.edu/finlayso/ebook/reaction/rxndiff/nondim.htm): escalas características y cocientes entre tiempos de reacción y difusión en un caso con propiedades constantes. Referencia de contraste, no estructura fija del motor.
