# Siguiente entrega propuesta: bases de materia y dimensiones

## Punto de partida

§25 corrigió A1–A9 y publicó supuestos efectivos. Codex volvió a ejecutar las quince sondas: todas cumplen, código 0. La evidencia nueva se conserva en `docs/auditoria_motor_2026_10_11/correcciones_25/evidencias.json`, sin sobrescribir la evidencia inicial.

El usuario va a probar el laboratorio actual. Este documento prepara una ampliación; no da por implementados el balance másico, la inversión arbitraria ni la comprobación dimensional completa. El backend conserva el cálculo, conversiones físicas, ensamblaje y recuento. No implementar solvers ni conversiones de mezcla en JavaScript.

## Hito 1: mismo balance en base molar o másica

Definir antes de implementar un contrato versionado para base de entrada y representación de materia. Una preferencia de presentación no cambia la identidad física; las cantidades equivalentes tampoco cambian el modelo. Se puede mantener el estado interno molar si toda conversión y relación sale del mismo ensamblaje.

- Por especie: `m_i = M_i n_i`, `m_dot_i = M_i F_i`, con M en kg/mol, procedencia, identidad química inequívoca y valor finito positivo. Publicar M y sus unidades; no adivinar una masa molar desde una etiqueta visual.
- Para la mezcla: `m_dot = F sum_i(x_i M_i)` y `w_i = x_i M_i / sum_j(x_j M_j)`. Si la composición no está dada, esa conversión requiere una relación acoplada; no convertir kg/s a mol/s con una constante elegida por omisión.
- Iniciales, fronteras, escalones, interfaces, fuentes por especie y resultados comparten la misma base física. La corriente interna sigue siendo una variable compartida, no dos valores dados independientes.
- Con reacción, conservar masa total aunque cambie el total de moles. Convertir las fuentes de cada especie por su M. No eliminar generación/consumo de especies porque el neto másico total sea cero.
- Elegir una base no duplica incógnitas, ecuaciones físicas ni datos independientes. Si se exponen aliases n/m o F/m_dot, declarar la relación y contar su dependencia. Dos declaraciones equivalentes son redundancia compatible; dos incompatibles son conflicto con referencias a ambos datos.
- Inicialmente entregar agua pura y luego mezclas de componentes identificados, por hitos verificados. Anunciar el alcance real en capacidades y en el catálogo de unidades. `kg/h → mol/s` sigue rechazado fuera del contexto necesario; no volverlo un factor universal.

Aceptación: mismo tanque con kg y mol, caudales en kg/h y mol/s, tiempos/unidades equivalentes; misma T y evolución tras convertir en el servidor. Añadir mezcla de masas molares distintas, composición variable, corriente compartida, reacción con Σν distinto de cero, conservación integrada, conflicto entre aliases y GL idénticos en las dos bases. Tolerancias por magnitud; referencias independientes.

## Hito 2: ecuaciones y análisis dimensional desde el ensamblaje

Implementar la propuesta de §25.6 para ecuaciones parciales antes de resolver. Publicar variables, ecuaciones y términos del mismo modelo aunque falten datos, con pendiente y ejecutada false donde corresponda. No devolver una ecuación diferente por carecer de valor numérico.

Para cada ecuación y término publicar información dimensional obtenida de expresiones tipadas del ensamblaje, no de interpretar LaTeX:

- dimensión/unidad del lado izquierdo y de cada término; variables y factores implicados;
- LaTeX con las unidades para colocar junto a la ecuación;
- estado `compatible`, `incompatible` o `no_evaluable`, y motivo preciso cuando no se pueda comprobar;
- origen de cada término, pieza, conexión e ids ya utilizados por el recuento.

Cubrir acumulación de especie, caudal por composición, reacción, energía almacenada, F·h, calor exterior, interfaces, pared, cámara y P·dV/dt. Comprobar diferencias térmicas frente a temperaturas absolutas; un desplazamiento Celsius no se usa como factor de una diferencia. Cero y términos anulados conservan su dimensión. Momento o relaciones sin implementación no figuran como verificados.

Aceptación: todas las ecuaciones ejecutadas dimensionalmente compatibles; casos mal tipados rechazados citando su término; molar/másico consistentes; ecuaciones parciales con datos numéricos ausentes conservan dimensiones conocidas. Un análisis dimensional compatible no demuestra conservación ni exactitud del resultado.

Frontend: un único interruptor, apagado inicialmente. No añadir columnas permanentes al experimento. Codex añadió una lectura de unidades del catálogo, etiquetada como tal; aún no es este análisis completo.

## Hito 3: selección de datos e incógnitas sin rutas ocultas

Revisar qué variables de cada combinación pueden ser dato/calcular y cómo se declaran. No basta con publicar `puede_calcularse` si la ruta no admite que el usuario sustituya su papel.

- Mantener el balance general actual directo/inverso y la selección explícita.
- Proponer separadamente la ampliación a más especies, energía y variables térmicas. Formular qué ecuación/cierre se reemplaza al imponer T, Q, caudal o cantidad, y qué iniciales siguen siendo necesarias en temporal.
- Un parámetro constitutivo no pasa a ser una incógnita identificable sin datos que lo determinen. Un estado dinámico no deja de necesitar inicial consistente por haber elegido Calcular.
- Publicar elegibilidad, limitación, papel seleccionado, referencia de campo y efecto en recuento desde el backend. El frontend no deduce GL contando inputs.
- Probar especificaciones directas/inversas, alternativas, dependencias, contradicciones, redundancia compatible y unidades equivalentes. GL = 0 no sustituye rango/consistencia ni convergencia.

## Prioridad que sigue pendiente de §25

Antes de ampliar regímenes, definir y verificar las desigualdades del dominio a lo largo de la trayectoria, incluida la comprobación de muestras y límites entre eventos. Un control por muestra no garantiza por sí solo lo que ocurre entre muestras. Mantener eventos, iniciales y reinicios coherentes; declarar el alcance sin extrapolar ni corregir silenciosamente resultados.

## Entrega

Mantener pruebas anteriores y agregar referencias nuevas. Documentar contrato, capacidades, unidades, migración y ejemplos generados por endpoints. No tocar frontend ni el cambio ajeno en `thermodynamics/proveedor.py`; no hacer commit/push sin autorización. No implementar todos los hitos como un único cambio genérico.
