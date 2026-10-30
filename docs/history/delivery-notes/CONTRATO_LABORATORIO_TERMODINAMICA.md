# Contrato de ampliación del laboratorio termodinámico

Entrega propuesta para Claude. Este documento no cambia ni publica el backend. Objetivo: una entrega integrada de servicios compartidos, con pruebas físicas y compatibilidad con el simulador existente. No concentrar todos los modelos en una sola función.

## Inventario revisado

- `/diagrama/resolver`: calentamiento y CSTR ya consumidos por el laboratorio; conservar contrato y comportamiento.
- `/elv/binario`: equilibrio líquido-vapor existente. Reutilizar su núcleo donde corresponda, sin confundir curvas binarias con un flash general.
- `/termodinamica/reaccion`: propiedades estándar de reacción y constantes de equilibrio. `thermodynamics/reaccion.py` usa propiedades de formación y van't Hoff; documentar aproximación de entalpía de reacción y temperatura de referencia. No equivale a resolver composición de equilibrio de una alimentación general.
- `/termodinamica/mapa-residual` y `/termodinamica/azeotropos`: herramientas existentes; mantenerlas. Los mapas reactivos tienen restricciones propias, no extenderlas silenciosamente.
- `thermodynamics/proveedor.py`: Cp, entalpía de vaporización, actividades y propiedades de formación ya disponibles internamente. Exponer solo capacidades validadas para cada modelo, fase y componente. Revisar en particular referencias y datos ausentes.

## Experimentos que debe soportar la base compartida

| Experimento | Especificación independiente | Respuesta requerida |
| --- | --- | --- |
| Propiedades / comparar estados | Componentes ordenados, composición, T y p de A y B; modelo y fases admitidas | Propiedades disponibles, fase, diferencias con referencias compatibles |
| Calor y cambio de fase | Estado inicial, caudal, presión; T final **o** calor suministrado | T, beta molar, x/y, entalpías por fase, balance de energía |
| Entropía | Estados y flujos, intercambios térmicos y temperaturas de frontera | Entropía transferida, generación y términos de balance |
| Potenciales | Estados admisibles y restricciones explicitadas | G/A cuando la base sea compatible; evitar conclusiones universales de estabilidad |
| Mezclas | T,p,x, fase y modelo | Actividad, gamma, fugacidad y potencial químico si disponible, estados estándar |
| Equilibrio químico | Alimentación, estequiometría, T,p y fases admitidas | Composición, avances, Qr, K, ΔrG por reacción, balances y convergencia |
| Exergía física | Estado de corriente y ambiente T0,p0 con misma composición | b física y estado de referencia; destrucción solo con balance de entropía completo |

Los barridos y la comparación A/B deben consumir las mismas funciones. Una comparación conserva condiciones, resultados y referencias de ambos estados; cambiar una entrada vuelve obsoleto el resultado anterior. No calcular diferencias entre referencias incompatibles.

## Contrato común de estado y capacidades

Proponer y documentar las rutas finales en OpenAPI; el frontend se adaptará al contrato verificado. Preferencia: recurso de capacidades y servicios de estado, comparación, proceso térmico, entropía y equilibrio, sobre funciones reutilizables.

Entrada de estado: identificadores y orden de componentes, composición molar normalizada (validación explícita, no corrección silenciosa), T [K], presión absoluta [Pa], modelo y política de fase (`estable` o fase impuesta identificada como tal). La base inicial es molar. Caudal [mol/s] separado de propiedades intensivas.

Salida por propiedad: valor o ausencia explícita, unidad, base, referencia, modelo/fuente, estado de disponibilidad y motivo si falta. Propiedades mínimas a evaluar: u,h,s,g,Cp y volumen molar; a Helmholtz solo si u,s compatibles. No sustituir una propiedad ausente por cero, ni construir g con entalpía sensible y entropía de otro convenio.

Identificar fase y estabilidad/metastabilidad si se puede establecer; distinguir fase impuesta de fase predicha. El recurso de capacidades debe informar por modelo qué cálculos, fases, componentes y rangos están soportados. Si no existe un rango validado, indicarlo expresamente en vez de inventarlo.

## Condiciones científicas y límites

- Referencias: distinguir h sensible, formación y estándar; s absoluta o relativa; T/p estándar y estado estándar de actividad. Diferencias requieren compatibilidad. Gibbs de formación y Gibbs de una mezcla no son intercambiables.
- μ = μ° + RT ln(a): actividades adimensionales y convenio explícito para cada fase. Fugacidad con unidad y normalización; no usar x como actividad en modelos no ideales sin gamma.
- Equilibrio reactivo: validar balance elemental, no negatividad y composición; permitir varias reacciones solo donde el algoritmo lo soporte. K por reacción y temperatura, coherente con ΔrG° y estados estándar. Si se reutiliza van't Hoff con ΔrH constante, declarar esa aproximación. Tratar fronteras de avance y especies ausentes sin fabricar log(0).
- Cambios de fase: reutilizar flash/equilibrio cuando exista; conservar materia y energía. No sumar calor latente dos veces si ya está en las entalpías de fase. La especificación p,h debe invertir un estado de equilibrio, no prolongar un calentador monofásico fuera de rango.
- Entropía estacionaria: separar flujos de entropía, ΣQk/Tb,k y generación. Falta de temperatura de frontera significa resultado insuficiente, no Sgen=0. Convención de calor positiva hacia el sistema documentada.
- Exergía física: misma composición en el estado ambiental; primera versión excluye exergía química, energía cinética y potencial. Solo calcular destrucción desde Sgen válida. Ambiente explícito, sin valores implícitos ocultos.
- No mallado, CFD, geometrías arbitrarias, dinámica espacial ni predicciones cinéticas a partir de K.

## Trazabilidad y errores

Conservar metadatos de ejecución, huella de entradas, versión del motor/proveedor y diagnósticos estructurados. Para solvers: estado, algoritmo, tolerancias, iteraciones, residuales realmente medidos y motivo de fallo. Para evaluación directa no inventar convergencia ni residual cero. Separar advertencia de aproximación, dato faltante, incompatibilidad y fallo numérico.

Resultados de barrido independientes por punto: conservar puntos válidos y fallos identificados. Si se añade endpoint de barrido, limitar cantidad y coste. Cálculos bajo demanda, no en cada pulsación.

## Validación requerida antes de integrar

1. Estado A=B produce diferencias cero dentro de tolerancia; el cambio de base se realiza explícitamente.
2. G=H−TS y A=U−TS solo con referencias y bases compatibles; ausencia de datos no produce valores finitos falsos.
3. Calentamiento monofásico conserva Q=FΔh; duplicar F duplica Q para iguales estados. Inversión p,h reproduce el estado térmico admitido.
4. Caso bifásico verifica beta en [0,1], balances globales y por componente, y consistencia energética. No afirmar ausencia de fases adicionales si el modelo no las busca.
5. Equilibrio reactivo conserva elementos; en equilibrio interior satisface Qr≈K y ΔrG≈0. Verificar también límites de avance y componentes con actividad nula.
6. Balance de entropía con frontera conocida: casos reversibles y transferencia irreversible verificables. Faltantes devuelven diagnóstico; no recortar Sgen negativo para ocultar error.
7. Exergía física nula en su estado ambiental y destrucción T0·Sgen; no etiquetarla como exergía total.
8. Regresión de endpoints existentes, CSTR, calentador, flowsheet y trazabilidad.

## Integración frontend posterior

La UI ya incluye una entrada guiada, ruta de fundamentos y fichas de experimentos previstos. Calentamiento y reactor siguen operativos. Los nuevos módulos numéricos se habilitarán según capacidades reales; no muestran resultados inventados. Luego se implementarán selector común de mezcla/modelo, editor de estados A/B, barridos, comparación y transferencia explícita de un estado entre módulos, conservando su procedencia. No transferir automáticamente estados a procesos guardados.

## Constructor de sistemas del frontend

La mesa de experimentación permite hasta ocho piezas (alimentación, salida, volumen de control, reactor, fuente de calor y trabajo de eje). Se formula un sistema pequeño: acumulación, transporte de materia, reacción, calor y trabajo con supuestos explícitos. Las combinaciones no admitidas se muestran como formulación sin cálculo. No activar un cálculo por la mera presencia de piezas.

Adaptadores numéricos actuales: calentamiento y CSTR isotermo de temperatura/conversión impuestas. El CSTR no resuelve el balance energético que se consulta en la formulación. Para ampliar: informar capacidades de topología y supuestos del motor, variables requeridas y ecuaciones efectivamente ejecutadas. No resolver automáticamente todas las conexiones dibujadas como un flowsheet de proceso.

El cuaderno guarda condiciones, grafo, supuestos, predicción y resultados por ensayo. Retomar condiciones exige calcular de nuevo. No trasladar resultados históricos a otro módulo como si fueran vigentes.

## Procedencia de ecuaciones y especificaciones por bloque

El inspector del frontend agrupa balances, condiciones y relaciones constitutivas. Los balances explícitos se construyen solo con corrientes conectadas al volumen de control y muestran los bloques participantes. Las corrientes aisladas no deben aportar términos. Convenciones de signo y especificaciones de entrada no se cuentan automáticamente como ecuaciones independientes.

Para mostrar el sistema realmente ejecutado, devolver por relación: identificador estable, bloque propietario, bloques/variables participantes, tipo (balance/condición/constitutiva), expresión y símbolos/unidades, estado activo y supuesto que la modifica, método/proveedor que la evalúa y si fue ejecutada en el cálculo. Diferenciar condiciones impuestas de incógnitas. Grados de libertad e independencia requieren análisis del motor; no inferirlos del número de fichas del frontend. El CSTR actual no ejecuta su balance de energía.


## Definición granular preparada en el frontend

La mesa exporta un JSON versionado con bloques (id, tipo, nombre), conexiones (id, desde, hacia, tipo: materia/calor/trabajo), supuestos y especificaciones. La frontera de un bloque compuesto enumera entradas y salidas. Guardar una definición permite recuperar el montaje en esta sesión; no equivale a instanciar y resolver varias unidades compuestas.

Caso de aceptación: alimentación benceno/tolueno a 300 K, 101325 Pa → volumen de control con fuente de calor → salida. F y composición impuestas. Alternativas excluyentes: T de salida impuesta y Q incógnita; Q impuesto y T de salida incógnita. El adaptador existente admite ambas. Las propiedades deben usar el mismo modelo y referencia.

El JSON contiene relaciones LaTeX para consulta. El motor debe ensamblar a partir de tipos físicos, variables con identidad y leyes; nunca interpretar el LaTeX como código. Debe devolver variables impuestas/calculadas/compartidas, relaciones realmente ejecutadas con origen, validación de unidades, independencia y grados de libertad, y diagnósticos vinculados a bloques y conexiones. Las corrientes de materia comparten F,T,p,x,h; los enlaces de calor y trabajo comparten Q y W con signo explícito.

La UI diferencia términos eliminados por supuestos, incompatibilidad con el adaptador y problemas de valores. El diagnóstico estructural completo y la solución de bloques compuestos requieren backend. No inventar grados de libertad contando fichas. Comparar ensayos conserva condiciones, supuestos, topología y resultados; la formulación simbólica se reconstruye con el catálogo frontend actual y no constituye una traza histórica del solver.
