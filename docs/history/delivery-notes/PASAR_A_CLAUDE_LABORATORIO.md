# Instrucciones para Claude: núcleo granular del laboratorio

Trabaja exclusivamente en el backend. Codex mantiene el frontend. No publiques ni hagas push. Conserva cambios existentes y contratos actuales; no renombres campos usados por /diagrama/resolver. Lee CONTRATO_LABORATORIO_TERMODINAMICA.md como contexto; este documento acota el siguiente cambio.

## Objetivo de esta entrega

Resolver un sistema estacionario de dos volúmenes térmicos conectados por una corriente intermedia con identidad única. Reutiliza el proveedor de propiedades y modelos existentes; no implementes CFD, mallado, columna completa ni un lenguaje que interprete LaTeX. El laboratorio y el flowsheet deben poder consumir el mismo núcleo, conservando adaptadores anteriores.

## Lo que ya preparó el frontend

- Tipos físicos: entrada, salida, corriente (intermedia), recipiente, reactor, calor, trabajo.
- Ediciones por bloque en data.datos: F [mol/s], T [K], p [Pa], x (fracción del primer componente en mezcla binaria), Q [kW]. En el JSON compuesto se llama bloques[].datos.
- Una corriente intermedia tiene puertos de entrada y salida; ambos balances usan el mismo F, T, p, x y h. No dupliques esas incógnitas.
- Supuestos globales: estacionario, adiabatico, sinTrabajo, sinReaccion, sinMovimiento.
- Alternativa térmica modo=temperatura (T impuesta, Q incógnita) o modo=calor (Q impuesto, T incógnita).
- Importación validada, exportación de mesa y de definición compuesta, historial y persistencia local. El cálculo conjunto está bloqueado en la UI; no se conecta automáticamente a un endpoint nuevo.
- Los datos locales de una pieza se preparan para el ensamblador. Los valores del adaptador antiguo proceden de condiciones/especificaciones globales; entrada a 300 K (térmico) o 330 K (CSTR), p=101325 Pa. No uses valores ausentes como ceros ni ignores datos locales contradictorios.

## Contrato de integración propuesto (nuevo, aún no consumido)

POST /laboratorio/validar y POST /laboratorio/resolver, con el objeto modelo del JSON exportado. Puede implementarse un único endpoint con acción explícita si se documenta. Mantén schema_version=1 y devuelve capacidades admitidas. La validación debe funcionar sin ejecutar el solver.

Entrada mínima: version, componentes (identificadores del proveedor), modelo_termodinamico/referencia explícitos o defaults documentados, bloques [{id,tipo,nombre,datos}], conexiones [{id,desde,hacia,tipo}], supuestos, especificaciones por bloque. Las relaciones LaTeX exportadas son descriptivas: ignóralas como entrada ejecutable. El JSON actual no declara componentes ni un catálogo termodinámico elegido: el nuevo contrato debe exigirlos o declarar claramente el preset benceno/tolueno. El frontend se adaptará después.

Acordar especificaciones por bloque como [{bloque_id,variable,valor,unidad}]. No interpretar T de un volumen como T de alimentación. Una especificación pertenece a una variable canónica y puede fijarse una sola vez. Para primera versión, F y x están fijados en la alimentación; T de cada volumen o Q de su fuente son mutuamente excluyentes. p uniforme impuesta. Dos alimentaciones y reacción/trabajo pueden rechazarse con diagnóstico claro en esta entrega.

Respuesta mínima:
- schema_version, modelo_id, calculo {identificador, motor.version}, estado (valido/invalido/resuelto/no_convergente/no_soportado).
- variables [{id,bloque_ids,conexion_ids,simbolo,unidad,rol: impuesta/calculada/compartida,valor|null,procedencia}]. La corriente intermedia debe referenciar un único estado.
- ecuaciones [{id,tipo,origen_bloques,origen_conexiones,variables,latex_general,latex_activo,terminos_descartados,ejecutada,residuo,escala,unidad}]. Residuo nulo si no ejecutada; nunca inventar ceros de éxito.
- diagnosticos [{codigo,severidad,mensaje,bloque_ids,conexion_ids,variable_ids,accion_sugerida}].
- analisis {incognitas,ecuaciones_independientes,rango,grados_libertad,metodo}. Valores desconocidos como null, no conteos de fichas. Distingue análisis estructural y rango numérico local; no asegures independencia global por un Jacobiano en un punto.
- convergencia {metodo,iteraciones,tolerancia,residuo_escalado,convergio} con estados consistentes.

## Caso de aceptación y resultados a verificar

Alimentación benceno/tolueno F=100 mol/s, x_benceno=0.5, T=300 K, p=101325 Pa. Primer volumen T_salida=310 K con Q1 desconocido. Corriente compartida hacia segundo volumen T_salida=320 K con Q2 desconocido. Salida final a la misma presión. Sin reacción, trabajo ni energía cinética/potencial; estacionario, no adiabático. Calor positivo hacia el volumen.

Balances: F se conserva, composición se conserva, Q1=F*(h310-h300), Q2=F*(h320-h310), Q1+Q2=F*(h320-h300). Usa entalpías y estados de fase reales del proveedor; no asumas Cp constante ni fase líquida sin verificar. No fijes números esperados inventados: compara con llamadas independientes al mismo proveedor y referencia.

Segundo caso: sustituye la T del primer volumen por Q1 calculado en el caso anterior; recupera 310 K dentro de la tolerancia acordada. Un cambio de F debe afectar las dos etapas y conservar identidad de la corriente intermedia.

## Pruebas obligatorias

1. Casos de uno y dos volúmenes; continuidad de F,x,T,p,h en corriente compartida y conservación global de energía.
2. Modos T y Q exclusivos: rechazar ambos impuestos, detectar ninguno impuesto, y datos contradictorios sobre la misma variable.
3. IDs duplicados, referencias inexistentes, puertos incompatibles, piezas aisladas, ciclos no soportados, NaN/Inf, fracciones inválidas, unidades incompatibles y modelo/referencia no disponible.
4. No convergencia y estado fuera del dominio: diagnóstico sin resultados presentados como resueltos.
5. Diagnósticos con IDs que existen en la petición; metadatos y ecuaciones ejecutadas correspondan al cálculo real.
6. No regresión de /diagrama/resolver ni del CSTR actual. El CSTR demostrativo mantiene energía desactivada hasta implementar su acoplamiento correctamente.

## Entrega para Codex

Documenta rutas finales, ejemplo exacto de petición/respuesta, defaults, unidades, códigos de diagnóstico, capacidades y pruebas ejecutadas. Guarda ejemplos JSON en backend o docs del backend. No edites archivos del frontend. Codex conectará la UI y mostrará resultados por bloque y sustituciones a partir de esta respuesta. No hace falta migrar todo el simulador en esta entrega.

## Vista compacta y explicación de resolución

El frontend reúne relaciones numeradas en Sistema completo. Debe recibir el nombre real del algoritmo, alcance (algebraico directo, inversión escalar o sistema acoplado), incógnitas, orden de resolución si aplica, tolerancias y convergencia. No reemplaces esto por una etiqueta genérica como Newton si ese algoritmo no se ejecutó. Las relaciones físicas no ejecutadas y convenciones de signo se deben distinguir de las ecuaciones activas del solver. Los avisos montaje/supuestos detectan fuentes conectadas con términos anulados; el backend debe validar esa coherencia y diagnosticar faltas de cierre sin inferir adiabaticidad solamente por ausencia de un bloque visual.
