# Preparación estructural de materia, estado y reglas

2026-10-13. Alcance: `/motor`, referencia independiente. No modifica el laboratorio ni el backend. No implementa propiedades, energía, evaluación de fases o flashes.

## Modelo y compatibilidad

El ensamblaje nuevo usa `version: 2`, `componentes` como catálogo único y `componentesIds` en volúmenes y corrientes. Se siguen leyendo los ensamblajes de versión 1. `normalizarEnsamblaje` adapta sus datos en memoria, sin alterar el original, y el formato nuevo se persiste al guardar. Los historiales conservan sus instantáneas para Deshacer; el ensamblaje actual resuelve las identidades por el catálogo, no por las copias del historial ni por el orden de volúmenes.

`Componente` admite identidad química opcional y masa molar con cantidad, unidad y fuente. Los componentes simbólicos no necesitan estos campos para trabajar en masa. No se consulta ningún proveedor.

Las corrientes conservan ID, nombre, extremos y el indicador existente de caudal constante. Añaden:

- `componentesIds` y `mecanismo: convectivo | selectivo | null`. La ausencia antigua se normaliza a null y conserva los signos originales.
- `datos.materia`: unión excluyente entre tasas por componente y caudal total más composición. Cada especificación declara base másica o molar. La composición numérica debe incluir todos los IDs, sumar uno y tener la misma base que el total.
- `datos.T`, `datos.P` y `datos.fasesPermitidas`: información preparatoria; no se evalúa ni se añade al recuento de datos de materia.
- `resultado`: contrato separado de un estado evaluado. Incluye espacio para T/P, caudales y composición calculados y fases con fracciones, composiciones, origen, validación, modelo y firma del estado. Esta entrega no fabrica estos resultados ni los utiliza como entradas.

Los caudales de la corriente pasan a ser la única especificación persistida. `config.datos` conserva iniciales, geometría y fuentes del volumen. Un adaptador mantiene las claves y la edición actuales; una doble especificación en ambos lugares se rechaza. `ordenDatosLegado` preserva el orden usado por la firma anterior para no invalidar resultados guardados solo por mover campos. El resultado evaluado no participa en la firma de entrada.

Los dos modos de materia alimentan la misma incidencia. El total se evalúa una sola vez y se distribuye por composición. Un dato molar se convierte a masa solo con masas molares declaradas en kg/mol o g/mol y fuente no vacía. Esto es conversión de base, no un cálculo de propiedades. No se corrige ni normaliza la composición silenciosamente.

El mecanismo convectivo exige un sentido común de transporte por componente; el selectivo conserva tasas con signos independientes y no admite normalizar el flujo neto como composición. Null conserva exactamente el comportamiento previo. El solver sigue usando estados másicos y los límites actuales de componentes y volúmenes; no se amplía el problema físico.

## Reglas e hipótesis

`FormulacionMateria.reglasEstado` es opcional y participa en los pasos y Deshacer/Rehacer. Sin él no cambia el comportamiento.

- Fases: cantidad sin restricción o monofásica; cambio interno permitido sin restricción o excluido; evaluación termodinámica solicitada o no.
- Densidades: variable referenciada, fuente dato/propiedades y constancia temporal sin restricción/asumida/a verificar.
- `evaluacionReglas` separa aplicación matemática de verificación. Una solicitud termodinámica se publica como no evaluable, nunca como cumplida. La resolución de materia puede estar lista aunque esa verificación no esté disponible.

El único efecto nuevo ejecutable reutiliza la relación existente de concentración media constante, con IDs `concentracion_media_c<ID>`, fuente dato y constancia asumida, cuando se declara la sustitución masa = concentración media × volumen. Conserva la reducción y la necesidad del dato numérico. Una constancia que necesita propiedades o una densidad no implementada se rechaza como relación ejecutable. Una solicitud de verificar no anula derivadas. No se convierte «sin cambio de fase» en «sin reacción».

`densidadMediaConstante` y `densidadComunPuertos` antiguos se conservan con su significado original; no se reinterpretan como hipótesis termodinámicas de mezcla.

## Variables numéricas

`VariableNumerica` declara ID, propietario, magnitud, unidad, componente/fase opcionales, papel, restricción y tolerancia absoluta. Los compiladores actuales producen descriptores de masas, concentraciones o volumen con restricción no negativa y las tolerancias anteriores.

El integrador utiliza la tolerancia de cada entrada del vector y comprueba agotamiento únicamente en entradas restringidas. Una coordenada libre negativa no detiene la integración. Los sistemas legados sin descriptores conservan la interpretación anterior de cantidades no negativas. Los papeles algebraico/dato quedan representables, pero el integrador ODE rechaza incluirlos directamente en su vector diferencial; no hay solver DAE nuevo.

Las unidades del vector heterogéneo corresponden a sus descriptores. `unidadEstado` sigue siendo el campo legado de los resultados materiales. No se añade un estado energético a los ejemplos ni se calcula U: una prueba numérica sintética comprueba la política de tolerancias y signos con una coordenada libre.

## Responsabilidades y comunicación futura

| Parte | Controla | No debe hacer |
| --- | --- | --- |
| Materia | Conservación, incidencia y contribuciones materiales. | Decidir fases o inventar propiedades. |
| Termodinámica futura | Evaluar estado y propiedades mediante un modelo y referencias explícitos. | Modificar cantidades, caudales o topología para corregir balances. |
| Reglas | Elección, relación matemática aplicable y solicitud de verificación. | Tratar una hipótesis como evidencia física. |
| Coordinador | Especificaciones, variables, ensamblaje y llamadas durante la resolución. | Obtener estado a partir de etiquetas o reutilizar una evaluación obsoleta. |

Los contratos compartidos están en `materiaEstado.ts`. La termodinámica futura importará contratos, no invocará el integrador ni el ensamblador material. El coordinador pasará un estado candidato a esa capa y entregará su evaluación a los balances de materia y energía. Un intercambio iterativo para resolver el sistema no supone una dependencia circular entre módulos.

## Distinción de densidades

- `rho_A_v1` y equivalentes: concentración másica de componente, m_i/V. Se mantienen los alias para compatibilidad; las etiquetas de gráficos lo indican.
- `rho_total_v1`: suma de concentraciones sobre el volumen geométrico declarado. No es una evaluación de una ecuación de estado.
- Densidad de mezcla termodinámica y densidad de fase: futuras propiedades, con modelos, condiciones y dominios propios. No se añaden valores ahora.

## Verificación

`npm run test:preparacion-materia`: 1163 comprobaciones de migración, firmas, trayectorias bit a bit de diez sistemas acoplados, recuentos, catálogo, persistencia, ambos modos y bases de especificación, caudales selectivos, reglas/historial y descriptores numéricos con RK45 y Euler implícito. La batería anterior de `test:motor-fundamental`, TypeScript y ESLint siguen pasando.

En navegador se recargó una hoja existente de cuatro componentes y tres volúmenes: su resultado previo permaneció vigente y volvió a resolver sin modificar sus datos.

Los tipos reservados y los modos de especificación nuevos no añaden paneles termodinámicos ni controles de fases al UI. Quedan pendientes la evaluación física de estado/fases, las propiedades energéticas, su verificación y el acoplamiento energético. No hay commit ni push.
