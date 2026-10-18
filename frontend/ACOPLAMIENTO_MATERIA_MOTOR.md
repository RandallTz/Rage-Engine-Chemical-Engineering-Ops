# Ensamblaje de varios volúmenes — referencia independiente de materia

Entrega: 13 de octubre de 2026. Trabajo exclusivo en `/motor`. No se modifica ni se compara el backend de Claude. No se amplían dimensiones ni geometrías espaciales. No hay commit ni push.

## Qué se ha implementado

La hoja puede contener un grafo de volúmenes y corrientes, con una conservación temporal de masa por especie en cada volumen. Las corrientes exteriores tienen un extremo Exterior; una conexión entre volúmenes tiene una identidad compartida Sₖ, con signo negativo en el origen y positivo en el destino. El número de balances es N especies × V volúmenes. El balance global es una comprobación del ensamblaje, no una nueva ecuación independiente.

El compilador no contiene ramas por nombre de experimento, por ser tanque, reactor o por forma de la red. Construye las filas de conservación de los términos estructurados de cada volumen y sus incidencias. Las columnas internas suman cero. Cadenas, bifurcaciones, mezcla y recirculación usan el mismo ensamblaje. Una autocirculación tiene incidencia neta cero, incluso si el caudal es grande.

Cada expresión de corriente por componente se evalúa una sola vez por evaluación conjunta del estado. Ese valor se distribuye mediante la incidencia dispersa. No se resuelve el primer volumen para pasar después su resultado al siguiente: estados, flujos y fuentes se evalúan en el mismo instante y se integran en un único vector, también en circuitos cerrados. El mismo integrador admite RK45 y Euler implícito con Jacobiano completo.

La conexión **no supone** una composición, mezcla perfecta, densidad, ley de descarga, reacción o igualdad de propiedades entre volúmenes. Se dan los flujos por componente como valores o expresiones. Si se desea que una salida siga la composición del donante, esa relación se escribe explícitamente. Las leyes pueden depender del estado del donante, del receptor, de otros volúmenes y del tiempo. No se inventan intercambios brutos a partir de un flujo neto.

## Interfaz y uso

1. Abrir una hoja guardada de materia y elegir **Acoplar varios volúmenes**. Su volumen actual, fronteras y datos se migran al ensamblaje; las antiguas entradas/salidas se convierten en corrientes exteriores. Los alias locales de expresiones de flujo se convierten a identidades de volumen.
2. **+ Volumen** crea una derivación general con los mismos componentes, sin corrientes ni hipótesis copiadas del otro volumen. Elegir Total y aplicar sus propios supuestos en el editor. La familia ejecutable de esta entrega es cantidad de materia temporal.
3. **Corrientes** abre un panel bajo demanda. Seleccionar origen y destino; Exterior representa la alimentación o descarga. Se pueden editar extremos, nombres, declarar constante una corriente o retirarla. Los puertos de las ecuaciones se derivan de estas conexiones, no se mantienen dos listas independientes.
4. Cada volumen se selecciona mediante su pestaña. Tiene nombre, derivación y supuestos propios. Los componentes son identidades compartidas de la hoja: añadir/retirar/renombrar componentes actualiza la lista de los demás volúmenes, conservando sus supuestos. Las referencias de una expresión que deja de ser válida se diagnostican, no se reescriben en silencio.
5. **V como dato** permite declarar el volumen geométrico/función V(t), según la frontera elegida, para usar concentraciones calculadas. No añade una restricción de densidad constante. Una fuente uniforme que necesita V también lo pide explícitamente.
6. **Resolver** muestra los balances de todos los volúmenes, con las identidades compartidas resaltadas, los datos agrupados por volumen/componente y por corriente, unidades, iniciales, horizonte y recuento. Cada corriente compartida se especifica una vez.
7. **Gráficos** usa identidades estables volumen–componente. Permite elegir masas, cantidades globales, concentraciones cuando se conoce V y flujos compartidos. Tabla y CSV conservan esas identidades. En Detalles técnicos están los residuos locales y globales.

Deshacer ensamblaje recupera hasta 30 cambios de esta sesión de edición, incluyendo datos retirados con conexiones/volúmenes. No se presenta como un archivo histórico completo ni persiste al abandonar esa vista. Los contadores de identidad no retroceden al deshacer; un elemento nuevo no recicla el id de una rama descartada. Las derivaciones por volumen mantienen su historial propio. La topología actual es común a las ecuaciones activas; regresar a una derivación local anterior no cambia las conexiones actuales.

Editar, añadir o quitar elementos invalida los resultados y renueva el tablero. Seleccionar otra pestaña de volumen no altera la firma física ni invalida resultados. El modelo y los datos se guardan como campos aditivos de las hojas actuales. Las hojas anteriores de un volumen continúan usando su compilación previa.

## Datos y expresiones

Ejemplos de identidades: `m_A_v1`, `m_A_v2`, `m_B_v1`, `m_total_v1`. Una fuente local al volumen puede usar `m`, `m_A` o `m_total`; una corriente usa identidades explícitas de los volúmenes. `V_v1`, `rho_A_v1` y `rho_total_v1` solo se habilitan cuando V se declara o es requerido por una fuente uniforme. En expresiones, estados y tiempo están en SI; la unidad seleccionada se aplica al resultado del campo.

No hay valores físicos por omisión. Cero se da explícitamente; una corriente faltante es un dato pendiente y cuenta una vez, aunque aparezca en dos balances. Una inicial por especie y volumen es obligatoria. Las tasas brutas G y C son no negativas; un caudal orientado puede ser negativo y representar intercambio en sentido contrario. El análisis de GL sigue siendo **estructural**, separado de iniciales y horizonte; no es rango numérico general de una DAE.

Se comprueba la compatibilidad de los supuestos locales con el transporte: una corriente no nula no puede introducirse en un volumen que eliminó ese transporte. Identidades de volúmenes, componentes o corrientes duplicadas, extremos inexistentes y componentes incompatibles se rechazan. Datos de campo que desaparecen se retiran; si la expresión de otro campo hacía referencia a ellos, queda inválida hasta corregirla.

La dimensionalidad interna de expresiones libres aún no se certifica. Siguen los límites de funciones y dominios del parser independiente; no se evalúa código JavaScript del usuario. No se localizan automáticamente todas las discontinuidades de una expresión arbitraria. Las tolerancias temporales controlan error local, no una garantía universal de error global.

## Alcance numérico

Acoplamiento de balances temporales de masa total por componente. Por el momento no se acoplan campos espaciales entre dominios ni se ejecuta la sustitución m=ρ̄V como estado volumétrico dentro de la red. Para concentraciones se conserva m como estado y se declara V como dato; ρᵢ=mᵢ/V se calcula. La resolución algebraica/estacionaria y las restricciones sin derivada temporal permanecen fuera de este compilador.

Límites explícitos del cálculo de referencia: hasta 32 volúmenes, 8 componentes por volumen y 128 estados totales; Euler implícito hasta 64 estados. No son limitaciones de una cadena: la topología es genérica y puede tener ramas o ciclos dentro del alcance indicado. No se han añadido energía, momento, hidrodinámica, propiedades ni cierres físicos de equipos.

La prueba del circuito inicialmente vacío en algunos volúmenes descubrió un mal condicionamiento del Newton. Se corrigió el escalado del sistema lineal con un piso relativo al estado conjunto, manteniendo independientes el tamaño de perturbación de cada especie y las tolerancias físicas. No se recortan masas ni se relajan tolerancias para resolver. La regresión anterior de una masa en trazas de 1e−20 kg sigue pasando.

El agotamiento de un volumen detiene el cálculo conjunto y devuelve `parcial`; no se continúa la otra parte como si la conexión siguiera suministrando materia. Los eventos y restricciones siguen los límites ya documentados del solver independiente. El presupuesto global se integra por separado a partir de corrientes exteriores, Φ_restante y fuentes. No se construye simplemente sumando los residuos publicados.

## Sistemas preparados para probar

En la biblioteca, **Añadir pruebas de acoplamiento** crea seis hojas editables sin sobrescribir las existentes. Ese catálogo es una colección de documentos, no código especial del solver. Los casos están completos para pulsar Resolver.

| Sistema | Referencia / resultado esperado |
| --- | --- |
| Dos tanques en serie | m₁=100+t y m₂=200+t; a 600 s: 700 y 800 kg |
| Cadena de tres con expresiones | Con z=0.1t: e⁻ᶻ, ze⁻ᶻ y z²e⁻ᶻ/2; a 20 s: 0.135335283, 0.270670566 y 0.270670566 kg |
| División y reunión de corrientes | A 60 s: 100, 50, 60 y 40 kg, en cuatro volúmenes |
| Recirculación cerrada | Tres capacidades que intercambian masa; total 3 kg; referencia con exponencial y seno/coseno, aproximándose a 1 kg por volumen |
| Intercambio selectivo de A | A₁=(1+e⁻⁰·⁴ᵗ)/2, A₂=(1−e⁻⁰·⁴ᵗ)/2; B permanece en 2 y 3 kg |
| Conversión y transporte acoplados | Consumo de A y generación de B en v1, transporte de ambas especies a v2; total A+B=1 kg |

Las leyes lineales de salida de algunos casos son **expresiones explícitas elegidas para la referencia**; no se imponen por ser un tanque ni se introducen coeficientes de descarga en todos los volúmenes.

## Verificación

`npm run test:acoplamiento-materia`: **3726 comprobaciones**, referencias analíticas en todas las muestras de los seis sistemas, cancelación de columnas internas, presupuestos globales, orientación invertida, especies/nodos reordenados, unidades equivalentes, ley no lineal, concentración con volúmenes distintos, fuente uniforme, agotamiento del donante, autocirculación, migración y catálogo de gráficos. Se renderizan las ecuaciones con KaTeX, sin fallback.

Además pasan las pruebas anteriores de operadores, derivación, un volumen, solver y ocho hojas sencillas; se incluyen todos los scripts en `npm run test:motor-fundamental`. TypeScript y ESLint se verifican aparte.

**Revisión visual pendiente:** el acceso a localhost por la herramienta de navegador fue rechazado automáticamente por un límite de uso. No se sustituyó por otra vía de control del navegador ni se cargaron las nuevas hojas en su almacenamiento. El usuario debe recargar Hojas y pulsar Añadir pruebas de acoplamiento para incorporarlas. La comprobación matemática y del catálogo no depende de esa herramienta.

## Archivos

- `ensamblajeMateria.ts`: modelo de dominios/corrientes, migración, términos, incidencia, campos, compilación y ecuaciones.
- `modeloHojaMotor.ts`: entrada única para analizar, firmar, compilar y resolver una hoja simple o acoplada.
- `integracionMotor.ts`: integración genérica del estado conjunto y presupuestos locales/globales.
- `EditorEnsamblajeMateria.tsx`, `HojaGuardada`, `ResolverHoja`: edición de la estructura y supuestos, campos y resolución.
- `datosGraficasEnsamblaje.ts`, `datosGraficasMotor`, `ResultadosHoja`, `TableroMotor`: identidad y visualización de los resultados.
- `hojasPruebaAcoplamiento.ts`, `verificar_acoplamiento_materia.mjs`: documentos de prueba y referencias independientes.

No se han cambiado rutas, algoritmos ni contratos del backend del laboratorio. La comparación con Claude queda para una entrega futura, cuando el usuario lo solicite.
