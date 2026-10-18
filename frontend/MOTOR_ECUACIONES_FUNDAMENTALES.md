# Hoja de derivación de los balances fundamentales

Ruta `/motor`, acceso «Ecuaciones». Versión vigente: 13 de octubre de 2026. Referencia matemática independiente para definir y verificar cómo debe formularse el motor del laboratorio. El objetivo incluye materia, energía y momento; actualmente se implementa materia por componente. No modifica ni ejecuta el laboratorio; la comparación entre ambos queda para después de verificar esta referencia.

## Hojas y resolución independiente — ampliación del 13 de octubre

Por petición posterior del usuario se añadió persistencia y un solver independiente de materia. El flujo es **Hojas → Ecuaciones → Resolver → Gráficos**. No se modificó el laboratorio. El alcance, los métodos numéricos, las pruebas y los límites actuales están en [SOLVER_HOJAS_MOTOR.md](SOLVER_HOJAS_MOTOR.md).

Se ejecutan ecuaciones temporales sin malla y campos 1D cartesianos en malla fija. No existe todavía un compilador multifísico general, ni resolución de energía, momento, 2D/3D, problemas inversos o estados estacionarios de esta hoja. Las coordenadas curvilíneas siguen disponibles para derivar ecuaciones, pero no para esta discretización.

## Interacción vigente

La primera ecuación es Acumulación = Entrada − Salida + Generación − Consumo. Debajo hay una hoja vertical. Solo empieza con la conservación local general, sin simplificaciones. No hay etapas por completar, recetas, escenarios de tanque, metas, cronogramas ni pasos futuros precargados.

Cada operación del usuario añade una fila con la ecuación obtenida, la forma elegida, su unidad y las relaciones nuevas. Las ecuaciones permanecen horizontales mientras caben; se dividen entre términos si se agota el ancho. Las relaciones ya introducidas no se repiten en todas las filas.

«Continuar aquí», «Volver al paso N», Inicio, Deshacer e Ir al paso recuperan la configuración elegida y retiran las filas posteriores de la hoja. × elimina la operación de esa fila y todas sus continuaciones: dependen de esa formulación, por lo que no se rebasa la derivación en silencio. Se restaura el paso anterior. La ecuación de partida no se elimina.

Rehacer conserva temporalmente las filas retiradas en un búfer separado, que no se imprime ni aparece en el selector de pasos. Una nueva operación descarta ese búfer y continúa con numeración consecutiva. Ya no se conservan ramas canceladas en pantalla ni se atenúan sus números. Los índices de los componentes siguen siendo estables y no se reutilizan después de descartar una operación. «Reiniciar» comienza una derivación nueva dentro de la hoja. «Hojas» permite crear documentos independientes, duplicarlos y archivarlos recuperablemente. Las hojas guardadas conservan su historia, supuestos y datos en este navegador; los perfiles calculados se guardan aparte en IndexedDB. No hay exportación/importación de hojas todavía; sí exportación CSV de resultados.

Las operaciones están a la derecha. Se puede cambiar de forma, relaciones y supuestos en cualquier orden. El panel conserva su propia posición mientras la hoja lleva la nueva ecuación a la vista. No hay cálculos ni gráficas de escenarios en esta pantalla.

## Formas de la misma conservación

- **Diferencial**: ∂ρᵢ/∂t = −∇·(ρᵢv) −∇·jᵢ + γᵢ(x,t) − χᵢ(x,t). ρᵢ y las fuentes son campos escalares; los flujos y velocidades son vectoriales.
- **Integral**: d/dt ∫V(t) ρᵢ dV = −∮∂V(t) [ρᵢ(v−v_b)+jᵢ]·n dA + ∫V(t) γᵢ dV − ∫V(t) χᵢ dV. Se conserva el transporte relativo a una frontera móvil. Declarar frontera fija elimina v_b; no viene elegido por omisión.
- **Total**: dmᵢ/dt = Σentradas ṁᵢ,p − Σsalidas ṁᵢ,p − Φᵢ,resto + Gᵢ − Cᵢ. Cada total se define mediante su integral, con la normal exterior y los signos de entrada/salida. Pasar a total no supone mezcla perfecta ni uniformidad local.

Las tres formas son operaciones disponibles, no un recorrido obligatorio. Escoger Total directamente añade solo esa fila; sus definiciones permiten ver la relación con el campo sin fabricar pasos que el usuario no realizó.

## Componentes y variables por ubicación

«Componentes», al principio del panel derecho, permite añadir, renombrar y quitar especies. Sin componentes declarados, i es una plantilla genérica. Al añadir N componentes se muestran N conservaciones simultáneas en cada fila nueva, en cualquiera de las tres formas. Los símbolos A, B, etc. son identidades de la hoja, no nombres químicos ni CAS; S27 y posteriores se muestran como índices completos. Los nombres se editan al salir del campo, sin añadir una fila por pulsación.

Renombrar conserva el índice. Quitar no renumera los restantes ni modifica filas pasadas. Continuar desde una fila anterior recupera sus componentes. Un índice retirado no se recicla en otra especie, incluso al reemplazar pasos cancelados. El catálogo usa los componentes del paso seleccionado.

V es el dominio de la mezcla, compartido por todas las especies. mᵢ es su masa contenida y ρᵢ es masa de la especie por volumen de mezcla, no la densidad del compuesto puro. No se inventan Vᵢ aditivos. Para una mezcla real, asignar volúmenes por especie requiere relaciones adicionales, como volúmenes molares parciales; véase [IUPAC, magnitud molar parcial](https://goldbook.iupac.org/terms/view/P04418).

Las definiciones de mezcla son m=Σmᵢ, ρ=Σρᵢ y wᵢ=ρᵢ/ρ, con Σwᵢ=1 para la lista completa de especies y ρ>0. Los caudales de mezcla son la suma de sus caudales por especie. No se añade un balance total redundante como ecuación independiente. La convención de velocidad es media en masa, así que Σjᵢ=0. Con una sola especie jᵢ=0 y wᵢ=1 por identidad. La relación aparece explícita y su término se elimina en las tres formas; «Difusión» queda desactivada con el motivo breve «Cero · una sola especie». La plantilla i, sin una lista completa declarada, no supone fluido puro. Fick escalar por especie no sustituye un cierre multicomponente compatible: coeficientes arbitrarios independientes pueden contradecir Σjᵢ=0. La hoja conserva esta restricción. El solver acotado verifica la suma de flujos durante sus evaluaciones y rechaza coeficientes incompatibles; no certifica un cierre multicomponente general.

Las operaciones del panel son comunes a los componentes. Las tasas γᵢ y χᵢ siguen siendo independientes por especie; no se añade una cinética, estequiometría ni una reacción por seleccionar generación. No se han implementado todavía hipótesis diferentes por especie ni integración con un catálogo termodinámico para esta hoja.

«Variables» en la barra lleva a dos columnas: **Volumen de control** (volumen compartido, masa por especie, concentraciones, fuentes y transporte interno) y **Corrientes y frontera** (caudal de mezcla y por especie, composición de cada puerto, áreas e intercambio fuera de los puertos). Las unidades y descripciones cortas permanecen visibles. La geometría y los operadores tienen un grupo separado. Es un catálogo simbólico, no un formulario de especificaciones numéricas. La composición de una corriente no se iguala automáticamente a la del volumen: esa igualdad requiere una relación o supuesto adicional.

## Fuentes locales y agregadas

Generación y consumo se activan/desactivan por separado. Son fuentes brutas: no se fabrican separando el signo de una fuente neta. Ambas pueden ser positivas con neto nulo.

Gᵢ(t) = ∫V γᵢ(x,t) dV y Cᵢ(t) = ∫V χᵢ(x,t) dV. Que Gᵢ sea una función escalar del tiempo no significa que γᵢ tenga el mismo valor en todos los puntos. Solo declarar uniformidad espacial permite sacar la tasa de la integral y escribir γᵢ(t)V(t). No se supone uniformidad temporal. Generación y consumo tienen hipótesis independientes.

Las restricciones de dependencia espacial se aplican a los campos independientes y componentes físicos de v y j general, no a los factores métricos. Con todas las direcciones invariantes, también se deduce uniformidad de las fuentes escalares del dominio regular. Fick produce un j derivado: no se impone invariancia adicional sobre sus componentes por confusión con el flujo general.

Referencia: [COMSOL, ecuaciones de difusión y conservación por especie](https://www.comsol.com/multiphysics/diffusion-equation).

## Geometría y leyes constitutivas

Cartesianas (x,y,z), cilíndricas (r,φ,z) y esféricas (r,θ,φ) mantienen tres dimensiones. θ es colatitud, φ azimut. Los diagramas muestran coordenadas; no eligen una geometría física o una malla.

Los operadores proceden de factores métricos ortogonales h_a. Divergencia: 1/H·∂a(H/h_a·F_a). Difusión escalar: 1/H·∂a(H/h_a²·κ·∂a f). Conservar componentes radiales constantes en coordenadas curvas no anula su divergencia: permanecen F_r/r o 2F_r/r y las contribuciones polares pertinentes. Se imprime el elemento de volumen correspondiente al usar la forma integral o coordenadas curvilíneas.

Relaciones difusivas: flujo general sin ley; Fick escalar jᵢ=−ρDᵢ∇wᵢ; Fick con ρ y D uniformes en espacio, que permite Dᵢ∇²ρᵢ. El modelo de Fick escalar no certifica una mezcla multicomponente concentrada. Las expresiones en el origen/polos requieren límites regulares.

Cambiar coordenadas con restricciones activas permite revisar su retirada. Independencia en x no se convierte automáticamente en independencia en r.

## Fronteras y flujos

Los puertos se añaden como flujos variables en el tiempo, sin caudal por omisión. Cada puerto puede declararse constante después. El caudal total se define por la integral del transporte relativo a través de su superficie. Si se declara flujo normal uniforme, la relación local divide el caudal por el área; no se deduce esa distribución de un caudal total.

Φᵢ,resto es el intercambio por toda la parte de la frontera que queda fuera de los puertos declarados, incluidas corrientes aún no clasificadas. Es positivo hacia fuera y negativo hacia dentro; por eso aparece restando en el balance. Puede representar, por ejemplo, paso de materia por una membrana. No es un caudal de una tubería ni una tasa de reacción. Una pared impermeable aporta cero. La ayuda breve de Fronteras explica el término sin añadir párrafos al lado de las ecuaciones. Se elimina solo al declarar explícitamente «Resto de la frontera sin flujo». Un tanque con solo tuberías es una elección de fronteras, no una formulación fija del editor. Los puertos deben particionar superficies sin solaparse cuando se definan dominios geométricos reales; la hoja actual no certifica esa topología.

No se añade una fuente volumétrica para representar otra vez una entrada por frontera. La partición se compone de los puertos declarados más su complemento, sin solapamiento. Una familia sin puertos no añade otra sumatoria desconocida encima de Φ: ese intercambio ya pertenece al complemento. Sin ningún puerto, Φ cubre toda la frontera. Declarar entonces ese complemento impermeable da un dominio cerrado. Sin esa declaración, el flujo sigue desconocido. No se imponen caudales cero por omisión.

## Cantidad, densidad media y volumen

La relación genérica es mᵢ = ρ̄ᵢ V, con ρ̄ᵢ = (1/V)∫Vρᵢ dV y V>0. No está vinculada a una receta de líquido puro ni a ausencia de reacción. La regla del producto conserva ρ̄ᵢ dV/dt + V dρ̄ᵢ/dt. Declarar densidad media constante solo elimina su derivada temporal: no hace uniforme el campo local.

Con un dominio fijo se elimina dV/dt, pero puede quedar V dρ̄ᵢ/dt. Con dominio fijo y densidad media constante la acumulación total se anula; permanecen las restricciones sobre flujos y fuentes.

Convertir a caudales volumétricos requiere la elección explícita «Puertos convectivos, densidad común»: jᵢ·n=0 en los puertos, ρᵢ,p=ρ̄ᵢ>0 y ṁᵢ,p=ρ̄ᵢQ_p. Se divide también cada fuente agregada y el flujo restante por ρ̄ᵢ, conservando las unidades. No se aplica esa conversión a un intercambio difusivo sin declararlo.

No hay escenarios separados de llenado y vaciado. Para una sola especie, fronteras cerradas salvo sus puertos, fuentes nulas y las relaciones pertinentes, la misma conservación puede reducirse a dV/dt = Q_entrada − Q_salida. Un recipiente rígido y un dominio de líquido con superficie libre móvil son conceptos distintos.

## Estructura y continuidad hacia multifísica

- `operadores.ts`: operadores de transporte, fuentes independientes, geometría y notación de fronteras.
- `recorridoMateria.ts`: formulación estructurada, formas diferencial/integral/total, relaciones y pasos con origen, operación y estado resultante.
- `catalogoMateria.ts` y `VariablesMateria.tsx`: variables, unidades y ubicación por dominio/corriente.
- `GestorComponentesMateria.tsx`: altas, retirada y nombres con identidad estable.
- `ProgresoMateria.tsx`: hoja vertical que imprime ecuaciones y relaciones de cada operación.
- `MateriaFundamental.tsx`: controles de las operaciones, sin presets ni lógica de un escenario concreto.
- `FormulaMateria.tsx`: renderizado horizontal con saltos por ancho disponible; no modifica el renderizador común del resto del proyecto.

Los pasos y sus operaciones son datos estructurados, separados del texto de sus títulos. Para extender a energía/momento y acoplar sistemas hay que agregar familias de conservación, dominios/variables con dimensiones, leyes constitutivas y puertos compartidos. El ensamblaje debe conservar una sola referencia de flujo en los dos lados de la conexión. Ese trabajo debe aportar ecuaciones diferenciales y algebraicas coherentes, no unir textos LaTeX.

Esta referencia no es un CAS arbitrario ni un compilador multifísico general: implementa las transformaciones enumeradas para materia. No sustituye fórmulas escritas libremente ni deduce cualquier identidad simbólica. No discretiza ni resuelve PDE/DAE, calcula rango o grados de libertad, valida una geometría real o modifica el backend. Se mantiene separada la formulación, el cierre numérico y la resolución.

## Verificación

`npm run test:motor-fundamental` ejecuta las referencias analíticas de operadores en tres coordenadas y la prueba de la hoja. Cubre orden libre de operaciones, retirada de pasos cancelados y recuperación con Rehacer, fuentes locales sin uniformidad implícita, generación/consumo independientes, transporte en frontera móvil, resto de superficie, regla del producto, conversión dimensional de fuentes y 288 combinaciones de formas/coordenadas/restricciones/fuentes renderizadas por KaTeX. También se comprueban 54 configuraciones con dos componentes (tres formas, tres coordenadas, tres relaciones difusivas y dos modos de expansión), su conservación independiente, relaciones de mezcla, signos de Φ, agrupación de variables, identidad al renombrar/retirar/sustituir pasos y 27 especies renderizadas. TypeScript y ESLint completan las comprobaciones. La revisión en navegador prueba añadir, renombrar, retirar, recuperar una fila anterior y consultar el catálogo. El backend y la resolución no se modifican.


## Antecedente: plan anterior a la incorporación del solver

Este plan corresponde al hito anterior, cuando se solicitó todavía no resolver. La ampliación actual se describe arriba y en SOLVER_HOJAS_MOTOR.md. Sigue pendiente el árbol general de operadores y el ensamblador multifísico; los términos totales estructurados y las expresiones numéricas sí se compilan para los alcances verificados.

La hoja genera expresiones LaTeX desde una configuración estructurada. La cadena matemática aún no es un árbol de expresiones tipadas, ni se envía al ensamblaje numérico del laboratorio. El backend del laboratorio ya tiene un ensamblaje de estados, términos y residuos para las combinaciones verificadas; esa implementación no convierte automáticamente la derivación de /motor en modelos ejecutables. No debe presentarse como un único motor conectado todavía.

El siguiente trabajo debe ampliar la representación matemática, sin añadir más controles o escenarios:

1. **Expresiones tipadas.** Variables con id, especie, dominio, dimensión física y dependencia espacial/temporal; nodos de suma, producto, derivada, gradiente, divergencia, integral y ecuación. El LaTeX se genera de estos objetos y deja de ser la representación principal. Las transformaciones dejan constancia de sus condiciones de validez.
2. **Dominios y puertos.** Una variable puede pertenecer a un campo interior o a una frontera. Una conexión identifica un mismo flujo entre dos dominios y sus signos opuestos; no copia dos variables independientes. Una corriente impuesta es un dato de frontera y una generación es una fuente interior.
3. **Relaciones y supuestos.** Los balances conservan su forma general; las relaciones constitutivas añaden ecuaciones y los supuestos transforman términos explícitamente. Integrar conserva la geometría y las fuentes variables; sacar una tasa de la integral necesita uniformidad. No se presupone mezcla perfecta.
4. **Ensamblaje auditable.** Recoger ecuaciones, identidades compartidas, variables y cierres en un único sistema. Publicar procedencia, dimensiones y relaciones pendientes. Diferenciar ecuaciones independientes de verificaciones globales. Un campo diferencial local necesita discretización para un residuo numérico finito; no simular que ya existe un sistema matricial solo por imprimir nabla.

El orden acordado es: **un volumen / un componente para materia**, luego formulación de energía y momento en ese mismo dominio, antes de ampliar componentes o acoplar volúmenes. La auditoría de materia está en `AUDITORIA_UN_VOLUMEN_MATERIA.md`; no equivale a haber terminado un compilador general. La representación de expresiones y transformaciones debe construirse y comprobarse primero en ese dominio único. Solo después se verificará el acoplamiento: dos volúmenes, N especies declaradas y una corriente compartida deben producir 2N balances y una sola identidad de flujo por especie. La misma identidad aparece restando en uno y sumando en el otro; se cancela al sumar los balances. Los datos y leyes siguen pendientes si no se declararon. Probar primero la forma total y su cancelación facilita verificar el ensamblaje, pero no impone un escenario de tanque al modelo ni sustituye la representación diferencial/integral. En aquel hito no se añadió solver. La petición posterior autoriza la resolución independiente y acotada documentada en SOLVER_HOJAS_MOTOR.md. No se añade cinética, hipótesis física ni propiedad por omisión.


### Auditoría de materia: un volumen / un componente

Se añadió `verificar_un_volumen_materia.mjs`, incluido en `npm run test:motor-fundamental`. Comprueba 147 condiciones y 66 contrastes independientes, con error relativo máximo 3.32e-11 en referencias analíticas y diferencias centrales. Los términos totales que consume el renderizador llevan rol, signo, componente, puerto, forma de fuente y LaTeX; las referencias verifican sus signos y transformaciones sin importar o invocar el laboratorio. No son aún un árbol matemático general ni un integrador.

Correcciones: difusión de especie pura eliminada por identidad; partición de frontera sin doble conteo; transporte nulo simplificado coherentemente; catálogo sin corrientes ficticias. Los cargadores de pruebas ahora preservan iteración de Set al transpilar, de modo que se comprueban también las relaciones que antes podían quedar omitidas en esas pruebas. Consulte el informe para casos, condiciones y límites.
