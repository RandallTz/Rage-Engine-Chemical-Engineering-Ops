# Integración de la entrega E0–E3

14 de octubre de 2026. Solo frontend de `/motor`. No se modifican backend, laboratorio, proveedor ni ejemplos publicados. Sin commit/push.

## Flujo disponible

1. Estado → cierre energético: relación manual o IAPWS-95. La sustitución de u(T) y densidad constante se revisa antes de aplicarla. Sus parámetros siguen guardados, inactivos. Se conserva la identidad química; un componente simbólico necesita identificarse explícitamente.
2. Política de fases compartida por materia, energía y cierre. No se decide una fase por nombre del componente. La elección de fase extraída se pide únicamente cuando puede salir materia y el reparto no está restringido a una fase.
3. Resolver: campos tomados de los datos referenciados por el ensamblaje, con unidad y origen. U(0)/T(0) son alternativas; una consulta estática no aporta valores iniciales. U se interpreta en la referencia del modelo elegido, indicada para IAPWS-95.
4. Validación automática: el backend publica ecuaciones, variables, recuento e inicialización. Un cambio de datos invalida inmediatamente la validación anterior. Las iniciales incompatibles impiden resolver aunque GL sea cero. No se lanza una validación simultánea con una resolución.
5. Resolver vuelve a validar en backend. Peticiones abortadas y respuestas de otra solicitud/modelo o de una hoja modificada no se publican. Se comprueba también que la hoja siga vigente después del guardado en IndexedDB.
6. Resultados: mismo tablero móvil y tabla del motor, series originales en SI por ID del backend; sin alias inventados, integración local ni remuestreo. Detalles técnicos contienen método real, certificados, reparto final, eventos y residuos escalados. No se presentan residuos escalados como errores absolutos en J o kg.

Las rutas de ensamblaje ya respondían al iniciar la comprobación; no fue necesario reiniciar el servicio. La API estática y sus consultas mantienen su función independiente.

## Lectores y alcance

`lectorEnsamblajeTermodinamico.ts` valida identidades de solicitud/modelo, catálogos y referencias a variables/datos, recuento, inicialización y estructura de trayectoria. Reutiliza el lector puntual para verificar cada estado. Comprueba U=m·u, V=m·v, H=U+PV cuando se publica H, T/P, reparto de vapor y series/unidades/horizonte. No certifica por sí mismo la EOS ni la estabilidad global.

Un resultado parcial puede incluir el punto certificado de aparición/desaparición que provoca la detención de una política. La excepción de lectura es solo ese último punto, con un evento y diagnóstico de detención concordantes. No autoriza muestras posteriores fuera de la política.

Se mantienen los límites publicados: agua pura, un volumen, RK45, sin expresiones no suaves, mezclas, reacción, transferencia selectiva ni dinámica de varios volúmenes. El integrador manual conserva su guarda contra un cierre real: el flujo real utiliza las rutas del backend.

## Incidencia inicial y seguimiento

Ver **`INCIDENCIA_CLAUDE_FRACCION_VAPOR_ENSAMBLAJE.md`**. Tres ejemplos publican q=0 para vapor puro aunque la fase certificada tenga fracción másica 1. El frontend rechaza esas respuestas; no las corrige ni oculta el problema. La integración de las rutas no equivale a dar por validada toda su salida física.

Seguimiento del 14 de octubre: los ejemplos actuales del backend ya superan la comprobación de q. La suite ahora exige aceptar los 13 pares originales, sin la corrección sintética temporal de los tres fixtures antiguos. Conserva un control negativo que altera q y debe ser rechazado. Esta comprobación es del contrato y sus identidades, no una auditoría independiente de la EOS ni una afirmación de que se haya recargado el servicio de Claude.

## Verificación

- Batería `test:motor-fundamental`, TypeScript y ESLint.
- Suite `verificar_integracion_ensamblaje.mjs` ampliada: 231 comprobaciones, 13 pares reales aceptados sin modificar, 164 muestras originales verificadas. Incluye edición, fases, presión, persistencia y controles negativos del lector.
- Uso real en una copia: Q vacío → GL=1 y Resolver bloqueado; Q=0 explícito → GL=0. Selección inicial por U, unidades kJ/kW/L/min y resolución con 101 muestras. Tabla de 0 a 300 s, masa 10 kg, U de 1 a 1.3 MJ, T de 297.1023 a 304.4183 K y P de 6.081871 a 10.88594 MPa. Gráficas con IDs reales de T/P y detalle de 101 estados certificados.

Hoja de comprobación creada sin alterar las hojas anteriores: `QA · Agua real · dinámica rígida`. La solicitud visible y su respuesta HTTP se conservaron en `.tmp/solicitud-ui-ensamblaje.json` y `.tmp/respuesta-ui-ensamblaje.json` como evidencia temporal.

## Refinamiento del sistema abierto

- Resolver empieza por los datos, separados en Volumen y una pestaña por corriente. Ecuaciones y variables calculadas están disponibles en un único desplegable. Los enlaces de variables usan la incidencia publicada por backend; no atribuyen a una variable algebraica una ecuación determinante única.
- En el volumen se distinguen iniciales, presión impuesta y calor. En las corrientes, el sentido indicado es el positivo de referencia; el signo real puede invertirlo. Primero se introduce el caudal, después se muestran los datos exteriores si el flujo puede entrar. La extracción de fase solo se solicita cuando procede.
- Presión exterior: Valor propio o Igual al volumen. Al activar continuidad, el dato propio se conserva en `HojaMotor.presionesExterioresInactivas`, fuera de la petición y de la firma física. Al volver a Valor propio se recupera exactamente texto/unidad, nunca una presión calculada. No se cambia el contrato del backend.
- Una expresión explícita F(t) retira la hipótesis previa de caudal constante en el historial. No se impone constancia al escribir un número ni se derivan leyes de salida.
- Editar las fronteras de un cierre dinámico conserva sus declaraciones y actualiza el contexto de la misma primera ley, con un paso auditable. No añade hipótesis. Las hojas anteriores con contexto desactualizado tienen una acción Actualizar ecuaciones. Las combinaciones fuera del alcance siguen siendo rechazadas.
- Los cambios invalidan resultados y validaciones anteriores. Una corriente nueva queda sin caudal; no se le asigna cero. Quitarla la retira del ensamblaje activo y elimina sus declaraciones asociadas, para que un puerto posterior que reutilice su identificador legado no herede silenciosamente sus valores. Las declaraciones de corrientes que siguen presentes se conservan.

Verificación en navegador, hoja aislada `QA · Agua real · sistema abierto editable` (`ddf63966-638c-4d7a-9a02-985971f200ee`):

| Edición sobre el mismo volumen a presión prescrita | Resultado observado |
| --- | --- |
| m0=100 kg; entrada 3 kg/s a 313.15 K; salida 2 kg/s; Q=8 kW; 120 s | m final 220 kg; T final 311.8494 K |
| Cambiar salida a 4 kg/s y horizonte a 40 s | m final 60 kg; T final 309.3291 K |
| Cambiar salida a 2 cos(t/10) kg/s, estado exterior a 293.15 K y continuidad | m final 235.136 kg a 40 s; caudal final negativo |
| Agregar otra salida de 0.5 kg/s | m final 215.136 kg a 40 s; iniciales y calor conservados |

El resultado antiguo dejó de mostrarse inmediatamente al agregar la corriente. Su nuevo campo apareció mediante Ir al dato pendiente. Se comprobó también la restauración de 2 bar propios al alternar continuidad, la eliminación de la tercera corriente y su revalidación. Las hojas del usuario y `/laboratorio` no se modificaron. Estos recorridos prueban la integración; no sustituyen las referencias físicas independientes de Claude.

## Comprobación posterior de cambio de fase

Ver [el informe y las referencias fundamentales](qa_cambio_fase_2026_10_14/README.md). Cinco hojas resueltas desde la interfaz cubren ebullición isobárica, política de transición prohibida, doble potencia con igual calor total, condensación rígida y calentamiento con salida de líquido. Se conservan las respuestas originales y un script reproducible con 1720 comprobaciones, incluidas referencias analíticas de materia y primera ley. No se implementó termodinámica adicional. La única corrección de presentación es el aviso breve de detención; el diagnóstico original queda intacto.

## Preparación del equilibrio integrado · 15 de octubre

`estructuraTermodinamica.ts` deriva un grafo de conservación de las declaraciones: una transferencia por corriente/componente y una de energía, signos opuestos por extremo, contactos térmicos y trabajo de frontera. La suma de balances retira exactamente las transferencias internas. Se comprueba con redes de varios volúmenes/componentes, ramas y ciclos, incluyendo valores negativos de transferencia. Es estructura simbólica: no calcula propiedades, rango ni capacidad numérica del backend.

La preparación v1 devuelve esa estructura local por separado; la petición HTTP no contiene campos nuevos. El solver sigue usando exclusivamente el ensamblaje ejecutable del backend. En Ecuaciones y variables calculadas hay una sección opcional Fundamentos del cierre y conexiones. Distingue el marco de potenciales, equilibrio y estabilidad de los residuos realmente ejecutados. No añade esos fundamentos al recuento.

Las relaciones incorporan potencial químico y fugacidad con referencia común. TP representa mínimo de G a cantidades fijadas; UV máximo de S a U/V/cantidades fijadas; PH/UP reconstrucción energética y estabilidad a T/P obtenidas, sin atribuir un mínimo de G a restricciones incorrectas. Fases por determinar no equivale a soporte dinámico de mezclas o sólidos.

El encargo siguiente de backend está en [CONTRATO_CLAUDE_MOTOR_EQUILIBRIO_MULTIFASICO.md](CONTRATO_CLAUDE_MOTOR_EQUILIBRIO_MULTIFASICO.md). La presente preparación no implementa sus hitos M0–M6 ni cambia las capacidades v1. Verificación estructural: `node verificar_estructura_termodinamica.mjs`.
