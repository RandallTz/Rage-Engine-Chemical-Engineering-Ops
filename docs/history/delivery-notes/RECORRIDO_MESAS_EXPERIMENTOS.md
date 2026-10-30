# Mesas, variables y consulta de resultados

Implementación de frontend sobre el contrato actual de estudios. No requiere un nuevo endpoint ni modifica los solvers del backend.

## Recorrido principal

1. **Laboratorio → Abrir una mesa → Crear mesa.** Elegir mesa vacía o un ejemplo de agua. Poner el nombre y abrir. La creación ocupa su propia pantalla; no reemplaza la mesa anterior.
2. **Diagrama.** Seleccionar un sistema o una corriente para introducir sus valores y unidades. Las corrientes del sistema tienen accesos directos desde su panel. Balances, componentes y otros ajustes del sistema están en la sección secundaria **Configurar el sistema**.
3. **Experimentar.** Utiliza las mismas variables. El recuento procede de `/validar`; no se estima un grado de libertad en JavaScript. Los datos pendientes o contradictorios impiden resolver según la respuesta del motor.
4. **Resultados → Montaje.** Un cursor recorre las muestras temporales devueltas por el backend. Todas las piezas muestran valores del mismo instante. Cantidades por especie, temperaturas, caudales y calor conservan sus unidades. No se interpolan estados, no se calculan niveles ni se integra una trayectoria local.
5. **Guardar y reabrir.** La mesa conserva la última solicitud y respuesta calculada, incluso tras recargar. Se identifica como **Última ejecución guardada**, con opción de recalcular.

## Vigencia y persistencia

- Cambiar datos, conexiones, balances, componentes o parámetros distingue el resultado anterior del modelo actual. La consulta histórica usa la solicitud original, no coloca sus números sobre una formulación nueva.
- Cambiar posiciones, nombre de las piezas o distribución de gráficas no invalida la ejecución. El orden de edición de `seleccion_variables.variables` tampoco altera la identidad del problema: esta colección se identifica por `variable_id`.
- La identidad local compara cantidades y unidades declaradas de forma conservadora. No reemplaza `modelo_id`, ni valida firmas de transferencia, ni certifica que una ejecución guardada sigue vigente respecto de una versión nueva del motor.
- Las mesas antiguas, sin ejecución guardada, siguen siendo válidas. Importaciones de ejecuciones incompletas o de respuestas que solo validan se rechazan. Se conserva el límite existente de tamaño del archivo.
- El guardado sigue siendo local al navegador. El menú Archivo permite descargar una copia con montaje, solicitud y ejecución.

## Verificación

Pruebas de código: `npm test`, `npm run test:mesa-recorrido`, TypeScript y ESLint de los archivos modificados. La prueba nueva cubre creación aislada, compatibilidad del documento, recuperación de ejecución, cambios físicos frente a cambios de presentación y lectura de muestras, incluidos cero y ausencia.

Prueba contra la API: `npm run test:escenarios-tanque`. Cinco escenarios contrastados con referencias analíticas independientes; ninguna referencia sale de un solver local de la interfaz.

Comprobado en navegador, en mesas de prueba separadas:

- Crear una mesa vacía, añadir un volumen con sus extremos incorporados y crear otra mesa desde un ejemplo sin sustituir la anterior.
- Editar un caudal en Diagrama y convertir 10 mol/s a 36 kmol/h. Resolver el llenado: 100 → 700 mol en 10 min.
- Retirar el caudal de salida: recuento incompleto, falta al menos un dato y Resolver deshabilitado. Consultar la ejecución anterior con sus datos originales.
- Restaurar ese valor y renombrar el tanque: el resultado físico conserva su vigencia.
- Guardar, reabrir y recargar: recuperar la ejecución identificada como guardada.
- Intercambio térmico: muestra inicial 350/300 K y 5000 W; a 3600 s, 329.395/320.605 K y 878.919 W, leídos de la respuesta.
- Vaciado: resultado parcial, evento a 100 s y última muestra con 0 mol. El cursor no permite avanzar hasta los 150 s pedidos. El motivo completo del evento está en Detalles técnicos; la vista principal muestra el tipo y el instante con unidad.

## Límites que siguen en backend

Los ejemplos ofrecidos siguen siendo los cinco escenarios ya soportados. Llenado/vaciado con energía, circuito caliente independiente, pared con almacenamiento térmico y vapor con condensación permanecen en `SIGUIENTE_CLAUDE_TANQUES_CIRCUITOS_TERMICOS.md`. Esta entrega no los simula por aproximaciones de frontend ni altera la prioridad de ese documento.
