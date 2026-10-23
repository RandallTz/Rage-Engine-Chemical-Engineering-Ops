# Entrega para Claude: núcleo de adimensionalización

Fecha: 16 de octubre de 2026.

## Encargo

Continúa la herramienta independiente descrita en `docs/history/frontend/plan-nondimensionalization-equations.md`. Ese documento sigue siendo el único plan y registro de avance. Este archivo es un punto de entrada técnico para Claude, solicitado por el usuario; no sustituye el plan ni cambia el roadmap multifísico.

Implementa el núcleo matemático general y sus pruebas, empezando por A0/A1 y la transformación mínima verificable de A2. A3 es obligatorio para entregar varias formas controlables. No modifiques `/motor`, `/laboratorio`, sus ecuaciones, solvers, termodinámica o documentos. No resuelvas las ecuaciones. Sin commit, push ni cambios incidentales de dependencias.

## Lo que ya existe

La página `/adimensionalizacion` es una interfaz de preparación. Permite cargar dos entradas declaradas, editar modelos mediante JSON, escoger qué variables escalar, dar escalas numéricas con unidad o dejarlas libres, duplicar formas, comparar elecciones, deshacer/rehacer, guardar localmente e importar/exportar JSON. LaTeX se genera desde el árbol tipado y se renderiza con el componente KaTeX existente.

El botón Transformar está deshabilitado. No hay análisis dimensional, transformación, resolución de objetivos, grupos calculados ni certificados. No confundas los ejemplos de entrada, las sustituciones mostradas o el documento TeX de referencia con resultados del motor. No hay API provisional.

Archivos relevantes, relativos a `frontend/`:

| Archivo | Responsabilidad |
|---|---|
| `app/adimensionalizacion/contrato.ts` | Propuesta v1: símbolos, dimensiones racionales, AST, ecuaciones, dominios, condiciones, escalas, objetivos, documento y resultado |
| `app/adimensionalizacion/documento.ts` | Lector estructural estricto; referencias; creación de entradas; revisiones y ramas |
| `app/adimensionalizacion/exportar.ts` | Presentación LaTeX y exportación; no usar como motor algebraico |
| `app/adimensionalizacion/Editor.tsx` | Interfaz, historial y almacenamiento local independiente |
| `app/adimensionalizacion/exploracion.ts` | Inventario sintáctico y preparación acotada de solicitudes combinatorias, sin resolverlas |
| `app/adimensionalizacion/ExploracionAutomatica.tsx` | Criterios persistentes, cobertura y revisión/exportación de propuestas sin evaluar |
| `app/adimensionalizacion/estilos.css` | Estilos limitados a la ruta |
| `verificar_adimensionalizacion.mjs` | Pruebas del lector y de la presentación; no aceptación científica |
| `../../../frontend/documentos/adimensionalizacion/main.tex` | Referencia humana de formulaciones del plan; no una implementación |

La clave local es `adimensionalizacion.documento.v1`. Los documentos nuevos no usan el proveedor de simulaciones. La navegación incorpora esta ruta y oculta en ella la barra de la simulación.

## A0: revisar y acordar antes de conectar

### Corrección más reciente: entrada mínima, desarrollo exhaustivo

La interfaz simple se refiere a **introducir la ecuación y pulsar un botón**, no a ocultar el resultado matemático. El producto central es el desglose matemático y algebraico completo de cada formulación. Debe mostrarse debajo de la entrada, en la vista principal, y no dentro de «Avanzado». Solo las preferencias de entrada y detalles técnicos de certificados se mantienen avanzados.

Entregar la traza desde el núcleo, con el orden efectivamente utilizado, sin reconstruir explicaciones genéricas en frontend a partir del resultado final. La propuesta `PasoDesarrollo` permite expresiones o igualdades completas antes/después, regla, justificación, supuestos y objetos afectados. Registrar todas las operaciones necesarias: restricciones dimensionales e inferencia; selección y resolución de mapas/escalas; sustitución de cada término; regla de la cadena para cada derivada; ecuación antes de cancelar factores; extracción/división por factores no nulos; agrupación de coeficientes; definición explícita de grupos; restricciones de normalización y familias libres; simplificación; transformación de dominios y condiciones; y sustitución inversa hasta recuperar el original. No imponer un itinerario fijo si una familia requiere otras operaciones.

Cada cancelación, factorización, desarrollo de producto/suma o cambio de base que altere la representación debe ser rastreable. Mantener separados cambios de variables, identidades algebraicas e hipótesis físicas. Toda división conserva sus condiciones de no nulidad; los signos y dominios necesarios se muestran junto al paso. Una traza faltante o un salto algebraico pendiente se declara incompleto, sin rellenarlo con pasos de ejemplo. Para cambios no lineales, incluir los términos adicionales de la regla de la cadena y su inversa; para funciones opacas no expandir definiciones desconocidas.

`DesgloseMatematico.tsx` presenta los pasos completos antes/después en LaTeX y conserva su orden, pero todavía recibe `null` porque no existe un productor/lector científico conectado. El bloque se abre en la vista principal al pulsar el botón, con estado pendiente. Actualizar y validar conjuntamente este contrato propuesto al conectar el núcleo. El lector debe comprobar la pertenencia de toda la traza a la solicitud exacta y sus restricciones antes de exponerla como resultado vigente. La traza y sus fórmulas intermedias deben poder exportarse a JSON/LaTeX junto con la formulación final.

El usuario confirmó que Claude ya está trabajando en el núcleo. Los cambios Codex de esta aclaración quedan limitados a presentación y documentación; no se modifica `core/adimensionalizacion`. Se mantiene el tipo básico previo de `ResultadoNucleo.pasos` y se propone `desarrollo?: PasoDesarrollo[]` solo como extensión opcional de presentación. No se exige que el productor actual adopte esa propuesta ni se considera que sea el protocolo real de la implementación en curso. Al integrar, el lector/adaptador deberá usar el contrato real publicado por el núcleo; si solo recibe una traza básica, la UI lo indica y no reconstruye pasos faltantes.

### Última corrección del usuario: entrada simple y familias más generales

El usuario rechazó la complejidad de la UI y que se presentase `t=t*τ`, `x=Lξ`, `c=Cu` como estructura obligatoria. La vista principal ahora contiene solo entrada de ecuación/sistema, vista previa LaTeX y botón «Adimensionalizar». Las escalas, formas guardadas, presupuestos y exportaciones están dentro de «Avanzado». Se retiró el bloque «Tus sustituciones» de la pantalla.

`entradaEcuaciones.ts` traduce texto explícito al AST, sin evaluación ni álgebra científica. Admite operadores `d(c,t)`, `d(c,t,2)`, `lap(c,x,y)`, `grad(c,x)`, `div(f,x)`, fuentes escalares, funciones declaradas, potencias y sistemas por líneas. Las dimensiones nuevas quedan `null`: ni `t` ni otro nombre implica una dimensión. Se conservan declaraciones anteriores compatibles; la lectura de texto no es inferencia dimensional. No se ejecuta código y no se interpreta LaTeX como fuente matemática.

`EntradaSimple.tsx` guarda la ecuación al pulsar el botón y comunica expresamente que no se ha calculado la adimensionalización porque falta el núcleo. La integración debe sustituir ese estado por una solicitud automática real: analizar la ecuación, inferir lo que permita el sistema dimensional, pedir únicamente los datos indispensables que queden indeterminados y producir alternativas. No exigir al usuario configurar escalas o editar JSON para iniciar la búsqueda. Los ajustes avanzados existentes son opcionales.

La petición amplía el alcance funcional objetivo del plan original: además de escalas multiplicativas constantes, considerar transformaciones afines con referencias, cocientes respecto a magnitudes de referencia, grupos Π/cambios de base y cambios no lineales **invertibles en un dominio declarado** cuando exista soporte matemático justificable. Esto no es un permiso para aceptar cambios arbitrarios o no invertibles ni para afirmar que todas esas familias ya están implementadas. Publicar capacidades por familia y diagnosticar las pendientes. Para mapas no lineales, transformar todas las derivadas (incluidos los términos adicionales de orden superior), propiedades, dominios y condiciones; conservar la inversa y sus restricciones. No sustituir el nombre de la variable para simular esa transformación.

Revisar la representación de transformaciones: `Forma.escalas` solo expresa el caso multiplicativo actual. Acordar un contrato de mapa directo/inverso más general antes de conectar familias afines o no lineales. La selección automática no debe quedar limitada por esa estructura heredada ni por las combinaciones de coeficientes del preparador anterior. El método y las familias deben venir del núcleo y sus capacidades, no de ramas por nombres o cinéticas en la UI.

### Petición posterior: ampliar y automatizar la exploración

El usuario pidió evitar una única normalización favorecida y buscar tantas formas/grupos como resulte posible. La prioridad funcional pasa a una exploración automática de representantes y familias, con las decisiones manuales como restricciones opcionales. No reemplazar esta petición por un catálogo de los cinco ejemplos.

Ya existe `app/adimensionalizacion/exploracion.ts`: inventaría términos aditivos explícitos de ambos lados, sin desarrollar productos, y prepara combinaciones de referencias a términos. No resuelve escalas, extrae coeficientes, comprueba dimensiones ni calcula grupos. `ExploracionAutomatica.tsx` muestra/exporta estas propuestas como **sin evaluar**. Los controles y preferencias se guardan opcionalmente en `Documento.exploracion`; los documentos v1 anteriores siguen siendo válidos.

`prepararExploracion` exporta un formato separado `solicitud_exploracion_adimensional`, versión 1, con copia del modelo, forma base, configuración, términos con rutas, propuestas y cobertura. No existe endpoint ni lector de resultados para este formato. **Revisar y acordar este contrato antes de conectarlo.**

Cada operación `normalizar_magnitud_coeficiente` significa buscar magnitud unitaria del **coeficiente efectivo** asociado al término después de transformar; no imponer que el campo, una derivada o el término completo valgan uno. Debe conservarse su signo. El núcleo debe identificar esos coeficientes y separar la normalización residual global: objetivos temporales pueden resultar dependientes de ella, no nuevas elecciones físicas. Ceros, signos desconocidos y objetivos no monomiales pueden resultar incompatibles, condicionales o pendientes. La preparación no decide ninguno de esos estados.

La preparación actual incluye el representante sin objetivos nuevos y todos los subconjuntos hasta `maxObjetivos` (1–8), mientras alcance el presupuesto (1–200). Su orden es explícito: cantidad de objetivos y orden del modelo; no se puntúa una forma como más física. `combinacionesEnAlcance` cuenta exactamente las combinaciones sintácticas mediante enteros arbitrarios; no cuenta formulaciones válidas, familias distintas ni grupos. El ejemplo con cuatro términos da 15 propuestas hasta tres objetivos o 16 hasta cuatro; aún no son resultados científicos.

Los valores iniciales favorecen la cobertura más amplia admitida por esta preparación: presupuesto 200 y hasta ocho objetivos nuevos. Las preferencias ya guardadas por el usuario se conservan.

Por defecto se respetan las escalas fijadas. Si se desactiva esa opción, se liberan las escalas de variables activas en la copia de la solicitud, sin cambiar el documento. Se conserva la selección de variables a transformar y los objetivos manuales base. El límite de objetivos cuenta solo los nuevos; no se recorren todavía subconjuntos de variables ni se expanden productos distributivamente.

La configuración puede pedir grupos Π, inversos y cambios de base, con cotas de exponente y denominador explícitas. Esto es un **encargo al núcleo**, no un cálculo ejecutado por el cliente. Implementar la matriz dimensional y su espacio nulo con aritmética racional; separar el inventario Π de los coeficientes efectivos de las ecuaciones. Mostrar bases alternativas, definiciones y mapas entre ellas sin afirmar exhaustividad de una familia infinita.

El núcleo debe ampliar la exploración con presupuesto de intentos/tiempo/resultados distinto cuando proceda, continuación reproducible, cobertura explícita, restricciones de signo, análisis de rango/dependencia, familias libres y eliminación de duplicados demostrables. No relajar restricciones fijadas silenciosamente ni ocultar casos omitidos/no soportados. Comparar como conjuntos y bajo permutaciones/renombrado de símbolos y ecuaciones; evitar referencias físicas preseleccionadas. Emitir resultados con geometría, condiciones y equivalencia inversa, no solo grupos o ecuaciones aisladas. Las pruebas deben incluir objetivos temporales redundantes, difusividades distintas, coeficientes cero/negativos, familias y presupuestos agotados.

### Contrato científico pendiente

La ubicación actual del contrato es ejecutable en TypeScript, pero es una **propuesta**, no un protocolo científico cerrado. Elige una única ubicación del núcleo científico, preferentemente junto a las piezas Python existentes si su reutilización resulta adecuada. El cliente puede seguir validando contratos y presentando árboles; no debe duplicar el álgebra científica del servidor.

Revisa al menos estas decisiones del esquema:

- `dimension: null` significa pendiente; `{}` significa dimensión uno. Los exponentes son `{n, d}` con enteros seguros y denominador positivo. La reducción canónica, el cambio de base y la inferencia quedan por definir en el núcleo.
- Las unidades son textos declarados; todavía no hay normalización ni comprobación de compatibilidad con las dimensiones. Separar temperatura absoluta de diferencias de temperatura y aplicar conversiones afines antes de escalas multiplicativas.
- `Simbolo.dependeDe` referencia tiempo/coordenadas. Las funciones opacas tienen entradas/salida dimensionales y dependencias; revisar si hace falta una declaración adicional explícita de dependencia en campos para coeficientes como `D(c)`.
- La geometría actual declara intervalos por variable. Las condiciones conservan tipo y una igualdad, pero falta una ubicación de frontera/instante suficientemente precisa para una transformación general. Ampliar el contrato antes de afirmar cobertura de condiciones.
- Los operadores incluyen derivada, gradiente, divergencia y laplaciano. Hacer explícita la restricción cartesiana y la semántica escalar/vectorial soportada. No tratar coordenadas curvilíneas como cartesianas por omisión.
- `Forma.objetivos.termino` contiene una expresión, pero todavía no identifica de manera canónica un coeficiente efectivo. Acordar identificadores de términos/coeficientes para que el cliente pueda seleccionar objetivos sin reconstruir álgebra.
- `ResultadoNucleo` no tiene un lector conectado. Debe vincular un resultado a la identidad/revisión del original **y a todas las elecciones de la forma**, mediante una firma canónica o revisión de la solicitud. `formaId` solo no detecta cambios de escalas en una forma existente.
- Las restricciones deben tener una semántica comprobable (positividad, no nulidad, dominio, igualdad), no solo una expresión y un motivo en texto. Publicar el alcance y los límites del certificado de equivalencia.
- Acordar capacidades y diagnósticos antes de añadir una API real. Un fallo/no soportado no puede incluir un resultado anterior como si fuera vigente. Si cambia la versión del contrato, migrar o rechazar explícitamente el documento.

El lector actual rechaza versiones/campos desconocidos. Toda ampliación del esquema requiere actualizar tipos, lector, entradas, exportación y pruebas de contrato de manera coordinada; no enviar silenciosamente campos adicionales.

## Primera entrega científica

1. Consumir el AST y comprobar compatibilidad dimensional, incompatibilidad e indeterminación. No evaluar LaTeX ni usar sustitución de texto. Inferir dimensiones cuando sean determinables y publicar rutas precisas en diagnósticos.
2. Transformar una ecuación escalar con derivada temporal, difusión y fuente introducida por el usuario, con escalas constantes dadas, finitas y positivas. Conservar variables no transformadas y etiquetar la normalización parcial.
3. Aplicar regla de la cadena en toda la expresión, preservar coeficientes variables y funciones opacas y transformar la geometría/condiciones dentro del alcance declarado. Rechazar explícitamente lo que quede fuera.
4. Guardar directa/inversa, restricciones y pasos antes/después. Verificar recuperación por sustitución inversa dentro del alcance algebraico. Si no se demuestra, declarar «no demostrada»; muestrear números no es demostrar.
5. Publicar pruebas positivas y negativas y un resultado canónico que el lector de frontend pueda verificar. Mantener la interfaz sin resultados simulados hasta disponer de esa entrega.

Después, implementar A3 con restricciones monomiales y álgebra racional de rango/dependencia: escalas determinadas, familias, redundancias e incompatibilidades. No seleccionar raíces numéricas silenciosamente. Obtener las cinco formas del §3 del plan con el mismo algoritmo, sin ramas por símbolos, nombres de especies o número de campos.

## Reutilización que conviene evaluar

En la raíz del repositorio, `core/dimensiones.py` contiene análisis con Pint para expresiones del ensamblaje. Su dominio de entrada no coincide todavía con este AST. Reutiliza piezas puras cuando proceda; no cambies el comportamiento del ensamblaje para adaptarlo a esta herramienta.

En frontend, `app/motor/expresionesMotor.ts` tiene un parser escalar seguro, pero carece de derivadas y dimensiones generales. `unidadesMotor.ts` usa un catálogo fijo y `operadores.ts` presenta operadores del motor actual. Se inventariaron; no se copiaron como segundo núcleo simbólico.

## Verificación y entrega

Desde `frontend/`, ejecutar:

```text
node verificar_adimensionalizacion.mjs
npx tsc --noEmit --incremental false
npx eslint app/adimensionalizacion
```

Añadir y ejecutar las pruebas científicas del núcleo en su ubicación elegida. Cubrir los casos del §8 del plan, empezando por los criterios de la primera entrega: fuentes constante/lineal/no lineal; escalas parciales; unidades equivalentes; sumas incompatibles; exp/log dimensionales; signos cero/negativo/desconocido; coeficiente variable y equivalencia inversa. Para A3, demostrar las cinco formulaciones, objetivos redundantes/incompatibles y familias libres sin dividir por parámetros nulos.

Registrar en el plan el alcance implementado, comandos y evidencias, capacidades pendientes y condiciones del certificado. No marcar A0/A1/A2/A3/A6 completos por la existencia de la interfaz. Entregar los archivos de contrato y resultados canónicos necesarios para integrar el botón Transformar y sus lectores.

## Mensaje de arranque listo para usar

> Lee `docs/history/frontend/delivery-claude-nondimensionalization.md` y `docs/history/frontend/plan-nondimensionalization-equations.md`. Implementa tu parte del núcleo científico independiente. Empieza revisando y cerrando el contrato A0, después A1 y la transformación mínima verificable de A2; continúa hacia A3 para obtener varias formas controlables. La UI de preparación ya existe, pero no hay cálculos integrados. No dupliques el núcleo en el navegador ni modifiques `/motor`, `/laboratorio` o el roadmap multifísico. Registra avances en el plan existente y entrega pruebas y resultados canónicos verificables antes de conectar la interfaz. Sin commit ni push.
