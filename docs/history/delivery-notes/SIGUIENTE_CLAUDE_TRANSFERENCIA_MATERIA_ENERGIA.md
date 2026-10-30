# Transferencia selectiva de materia + energía — entrega registrada

## Estado actualizado tras §20

Hito A completado por Claude: `ideal_volumen_fijo` con `cv` y `u_referencia` por especie, transporte de energía por el donante y conducción térmica separada. Hito B comprobado y no disponible por propiedades y cierres faltantes; conservar el diagnóstico y la capacidad deshabilitada. Contrato documentado: revisión 6. La entrega informa 30 suites en verde; este registro no constituye una nueva ejecución de las pruebas.

Este documento conserva la solicitud original como referencia; no volver a implementarla. La integración frontend de §20 está completada, junto a §21, y documentada en `INTEGRACION_ENTREGAS_20_21.md`. El seguimiento de ampliaciones pendientes está en `SUPUESTOS_POR_VOLUMEN_CLAUDE.md`, sección «Estado vigente después de la entrega §21».

## Solicitud original

## Contexto y prioridad vigente
Claude: solo backend. Codex: solo frontend. Sin commit, push ni publicación; conservar cambios ajenos, incluido thermodynamics/proveedor.py. Inspeccionar Git antes de trabajar. Leer docs/ENTREGA_LABORATORIO_CODEX.md §§15–19. Ya entregados: reacción + interfaz térmica, transferencia de estacionario y su firma JSON, interfaz material isotérmica. No repetirlos. Contrato actual: revisión 5.

Implementar dos hitos independientes. A: un modelo energético sencillo con propiedades declaradas y referencias independientes. B: propiedades del proveedor, solo después de cerrar A y verificar disponibilidad de propiedades necesarias. Reacción queda para otra entrega. No habilitar A+B ni reacción por suma de capacidades.

## Decisión física previa obligatoria
Documentar la formulación elegida antes de ampliar código. Los dos compartimentos cerrados tienen V geométrico fijo y N variable. El cierre volumen_fijo de §19 NO impone rho constante ni sum(n)=rho V. El modelo energético ideal_incompresible anterior exige inventario constante: no extenderlo silenciosamente ni usar su densidad como compensación automática.

Resolver explícitamente estas preguntas:
1. ¿Cuál es U(n,T), su referencia y dominio? ¿Cuáles son las propiedades declaradas por especie y cuáles se calculan?
2. ¿Qué energía transporta la especie y cómo se evalúa a ambos lados? Para soluciones no ideales, una entalpía molar parcial no es automáticamente la entalpía de la especie pura.
3. ¿Qué ocurre con trabajo de flujo, presión y volumen parcial de la especie transferida? Si se desprecia por aproximación de soluto diluido, declararlo y limitarlo; no llamar rigurosa a esa aproximación.
4. ¿Qué cierre permite volúmenes fijos con transferencia selectiva? No introducir corrientes compensatorias, expansión ni proyección silenciosa.

Si el proveedor o los cierres actuales no permiten una formulación coherente, entregar A con alcance más pequeño y explícito, y documentar qué necesita B. No rellenar propiedades ausentes ni mezclar referencias energéticas.

## Hito A: alcance mínimo propuesto
Dos compartimentos bien mezclados y rígidos, sin corrientes exteriores ni reacción; una especie que cruza, soluto diluido con L/H constantes declarados. Temperaturas propias T1,T2 obtenidas de cierres energéticos, no estados diferenciales duplicados si U es el estado. Propiedades térmicas constantes explícitas por especie y referencia común; distinguir capacidades térmicas de cp/cv según el cierre elegido. Un único vector [n_i,1,U1,n_i,2,U2], evaluado al mismo instante.

Mantener la ley material de §19 como aproximación fenomenológica declarada, no presentarla como fuerza impulsora termodinámica general. Una dependencia L(T), H(T), actividades o potenciales químicos pertenece a B o a un hito posterior con datos reales.

Energía de la interfaz: definir una tasa firmada E12 [W], usada exactamente como −E12 en origen y +E12 en destino. Debe derivarse del modelo elegido, no de una expresión LaTeX del cliente. Si se elige una ley de energía transportada por dirección del flujo neto (estado del donante), declarar ese cierre y probar el cruce de signo. NO deducir un intercambio bruto bidireccional a partir de una tasa neta: a neto cero, las transferencias brutas no son identificables sin una ley adicional.

No introducir conducción térmica implícita. Si se incluye una interfaz térmica G(T1−T2), que sea una conexión separada explícita y una combinación verificada propia; separar calor interno de energía transportada con la especie. No duplicar ambos términos. Q exterior impuesto/adiabático: admitir solo los modos que se hayan formulado y comprobado, sin valores por omisión. T impuesta requiere contabilizar el calor que la mantiene, no simplemente sobreescribir T.

## Ensamblaje y metadatos
- Cada balance devuelve terminos[], signo, variables, pieza y conexión. La ecuación y su evaluación salen del mismo ensamblaje.
- Global de materia cancela la tasa interna; global de energía cancela E12 (y Q12 si esa combinación está soportada). Las fuentes externas permanecen.
- Declarar unidades, referencias, parámetros, dominio, tolerancias, restricciones, método real y eventos de agotamiento/límite térmico.
- En la ecuación escrita en T, conservar la contribución debida a dn_i/dt: dU/dt = (partial U/partial T)_n dT/dt + sum_i(partial U/partial n_i)_T dn_i/dt. No verificar temperatura con una capacidad fija que ignore inventarios variables.
- Capacidad por combinación exacta; revisión de contrato y migración explícitas. Mantener resultados e identificadores anteriores intactos si el montaje no solicita nueva física.
- Guardas con diagnósticos por pieza y conexión. No extrapolar propiedades ni ocultar un cierre incompatible.

## Estacionario y transferencia de origen
Los compartimentos cerrados conservan totales de especies; si son adiabáticos, también el total energético. Hay familias de estados estacionarios. Mantener la transferencia estacionario → temporal deshabilitada para la nueva combinación hasta definir un origen único y restricciones explícitas. No elegir totales, temperatura límite ni rama por omisión.

El temporal puede comparar su final con un límite determinado por los totales iniciales, cuando ese límite se derive y se verifique de forma independiente. Etiquetarlo como límite condicionado, no estacionario único. No prometer estabilidad asintótica en los modos conservados.

## Aceptación independiente de A
1. L=0 conserva especies por volumen y recupera el subsistema térmico realmente declarado; si no hay calor, U permanece constante.
2. Caso inicialmente a temperatura común: demostrar el comportamiento esperado según la energía transportada y el cierre elegido, sin imponer T para ocultar errores.
3. Referencia escrita en T con término composicional, integrada aparte, contra el motor en U. Inventarios, temperatura y energía comparados, no solo residuo global.
4. Conservación de especies, impermeables, elementos, masa y energía. Mostrar por separado precisión y cierre del ensamblaje.
5. Cambio coherente de referencia energética no altera la trayectoria física; probar offsets específicos por especie, no solo un cero global.
6. Inversión material equivalente con H'=1/H, L'=L/H, energía y signo coherentes. También probar inversión sin transformar parámetros como física distinta.
7. Flujo en ambos sentidos y cruce por cero: no inventar brutas; comprobar continuidad o declarar las discontinuidades del cierre elegido y el tratamiento numérico.
8. Soluto en trazas, capacidades térmicas distintas, L alta, dominio limitado, vaciado/agotamiento y evento antes de primera muestra.
9. Rechazos de unidades, referencias mezcladas, propiedades ausentes, cierre inventario_constante, reacción, proveedor no disponible y topologías no admitidas.
10. JSON real de Node, persistencia, modelo_id, términos y cancelaciones; regresión de todas las suites existentes.

## Hito B: proveedor
Precisar si el proveedor puede dar U(n,T), derivados/entalpías parciales y una relación de volumen consistente para el alcance. No reemplazar propiedades de mezcla por propiedades puras sin aproximación explícita. Comprobar fase, dominio, disponibilidad por sustancia y referencia. Si falta una propiedad, devolver diagnóstico específico y dejar esa capacidad deshabilitada.

Validar B contra caminos independientes del proveedor: referencia/calorimetría o cuadratura con dominio declarado, fases y referencias. No considerar un endpoint llamado dos veces como referencia independiente. No combinar reacción antes de esta validación.

## Entrega a Codex
Sección nueva en entrega principal: decisión física, esquema exacto, cierres, códigos, campos, capacidades por combinación, migración y límites. Generar ejemplos ejecutando endpoints. Indicar si se completó A y si B está realmente disponible. Ningún cálculo de propiedades, energía de transferencia, estabilidad o integración se mueve al frontend.
