# Un sistema físico, varios estudios — entrega para Claude

Estado: propuesta de contrato; NO es una API implementada. Codex solo modificó frontend.

## Implementado en frontend

La mesa conserva piezas, conexiones y leyes al cambiar entre estacionario y evolución temporal. El selector reemplaza la casilla de estacionariedad en Armar/Formular. Por compatibilidad, supuestos.estacionario sigue siendo la bandera que reciben los adaptadores existentes; no se debe duplicar esta autoridad en el motor nuevo.

DocumentoMesa tiene estudio opcional: {version:1, tiempoFinal:100, iniciales:{cv:{n:100,T:300,V:1}}}. n se declara en mol, T en K, V en m³ y tiempoFinal en segundos. Es preparación declarativa, NO un estado dinámico suficiente. Los datos ausentes se conservan ausentes; n=0 no se convierte en ausencia. Importación valida dominios, IDs de volúmenes y versión. Los documentos antiguos reciben preparación vacía. Guardado, descarga, deshacer y recuperación conservan este objeto. Se bloquea el adaptador estacionario cuando estacionario=false; no se llama al lote como sustituto de un sistema abierto.

## Arquitectura a implementar

1. Definición física común versionada: volúmenes, sustancias con identidad inequívoca, conexiones, modelos constitutivos, reacciones y convenciones de unidades/signos. Separar definición física de especificaciones de cada estudio. Mantener IDs estables y una corriente intermedia con un solo estado.
2. Compilación única de balances de conservación antes de elegir estudio. Materia por especie: dn_i/dt=entradas-salidas+G_i-C_i. Energía: dE/dt=Q-Ws+transporte; la referencia de entalpía determina si la contribución química está incluida. Momento: dP/dt=transporte+fuerzas, solo si hay cierres suficientes. No sumar ecuaciones dimensionalmente diferentes.
3. Modo estacionario: fijar derivadas a cero, conservar almacenamiento en la definición. Modo temporal: conservar derivadas y usar condiciones iniciales. Compartir evaluadores de propiedades, fuentes y residuos. No prometer que todo modelo estacionario puede convertirse en dinámico: exigir los cierres de almacenamiento que le faltan.
4. Detectar ODE frente a DAE según restricciones algebraicas; declarar variables diferenciales/algebraicas, ecuaciones independientes y método realmente empleado. No anunciar un integrador por defecto como si estuviera elegido científicamente. Para DAE, verificar condiciones iniciales consistentes.

## Datos y endpoints propuestos (acordar antes de conectar)

GET capacidades: modos soportados por física/topología, unidades, cierres y dominios. POST validar_estudio: definición física + estudio {tipo:estacionario|temporal, especificaciones, condiciones_iniciales, tiempo, entradas_temporales}; respuesta con datos faltantes, conflictos, clasificación ODE/DAE y diagnósticos por ID. POST resolver_estudio: misma definición validada; devolver procedencia y método, no aceptar LaTeX como instrucciones.

La estructura local n/T/V debe migrar a inventarios por especie con unidades explícitas y cierres de energía: n_i, E/U o T con relación constitutiva coherente, volumen o ley geométrica y presión/densidad cuando corresponda. n total por sí solo no determina composición. Declarar si V es constante o variable. No convertir una T de salida impuesta en T inicial ni una potencia en energía almacenada.

Entradas temporales: primero constantes y cambios escalón con instante y unidad explícitos; no ejecutar expresiones libres del usuario. Extender perfiles después. Validar discontinuidades y dominio en cada tramo.

Resultados temporales: tiempos con unidad, series por variable/ID/unidad, residuos instantáneos e integrados, conservación, eventos de agotamiento/dominio/fase y terminación. Distinguir completado, detenido por evento y fallido. Registrar tolerancias, método, versión y condiciones iniciales utilizadas. Una serie parcial no es éxito total.

## Transferencias entre estudios

Estacionario → temporal: generar un candidato de condición inicial desde el resultado, usando almacenamiento declarado, y validarlo. No usar F como n, ni h como E sin cantidad y convención de energía. Conservar identificador/versión del cálculo origen. Habilitar el botón en frontend únicamente tras este contrato.

Temporal → estacionario: ofrecer contraste con una solución independiente para las mismas entradas finales. No afirmar convergencia porque el gráfico está plano. Evaluar norma escalada de derivadas, residuos, conservación y ventana temporal; distinguir alcanzar un estacionario de demostrar estabilidad.

La estabilidad es una propiedad adicional: análisis local del sistema dinámico, restricciones DAE cuando existan. Un residuo algebraico cero no implica estabilidad, unicidad ni accesibilidad desde cualquier condición inicial.

## Casos de aceptación independientes

- Tanque mezclado sin reacción, V/densidad constantes: solución exponencial de concentración para un escalón; inventario y balance global verificados.
- Dos volúmenes en serie: transporte intermedio cancelado en balance global; retraso físico explicado por inventarios, nunca duplicación de la corriente.
- Volumen térmico con capacidad constante en un caso ideal explícito: exponencial analítica; después proveedor variable y conservación integrada. No imponer Cp constante al motor real.
- Mismo montaje: estacionario independiente coincide con límite dinámico dentro de tolerancias declaradas en un caso estable.
- Cambio de estudio conserva definición/IDs; condiciones iniciales se preservan al volver a estacionario.
- Agotamiento, inventario inicial cero, datos insuficientes, unidades incompatibles, estado inicial DAE inconsistente y salida de dominio producen diagnósticos específicos.
- Reacción reversible: generación y consumo brutos conservan su semántica; neto cero no se confunde con ausencia de reacción.

## Prioridad y límite

Primero tanque material ideal y térmico de un volumen con almacenamiento explícito; luego dos volúmenes, fuentes reactivas y energía acoplada. Sin CFD ni mallado. Momento permanece formulación hasta definir fuerzas, áreas y velocidades. El lote reactivo existente es otro régimen soportado, no prueba de que la mesa abierta sea dinámica.

Pendiente anterior que continúa vigente: asociar definiciones reactivas multicomponente a cada volumen y sustituir el CSTR demostrativo por el adaptador correcto; ver PENDIENTES_BACKEND_CLAUDE.md. No habilitar ejecución arbitraria solo porque el frontend pueda dibujarla.


## Actualización de prioridad: acoplamiento desde el primer caso

La primera aceptación debe incluir DOS volúmenes materiales perfectamente mezclados conectados. Un tanque aislado puede ser una prueba unitaria, pero no completa la entrega. Ambas derivadas se evalúan sobre el estado conjunto del mismo instante; los cierres se ensamblan con los balances. No imponer que todo sea ODE: demostrar reducción válida o declarar restricciones DAE, consistencia y soporte del método. El transporte interno cancela en conservación global aunque siga acoplando las derivadas locales. No integrar tanques aisladamente y transmitir estados finales. Si se usa partición, declarar algoritmo, sincronización y error verificado. La marcha estacionaria existente sigue siendo válida solo en el régimen triangular que admite.
