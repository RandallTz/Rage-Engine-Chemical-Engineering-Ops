# Incidencia: frontera válida rechazada por la guarda de presión

15 de octubre de 2026. Detectada al crear el ejemplo solicitado de agua de 10 a 200 °C.

**Seguimiento:** el usuario autorizó una corrección mínima que no interfiriese con la entrega de Claude. Codex movió únicamente ese `else` al bloque de tipos de frontera; no cambió ecuaciones, contratos ni paquetes. Cinco casos de la corrección candidata pasaron antes de aplicarla: rígida válida, presión prescrita válida, tipo desconocido, flag contradictorio y compatibilidad sin flag. Se reinició únicamente uvicorn del puerto 8004; los procesos de pruebas de Claude quedaron intactos. Mantener esta corrección al continuar la entrega.

En `backend/motor_ensamblaje.py`, alrededor de líneas 398–419, el `else` que diagnostica un tipo de frontera desconocido quedó después de la nueva cadena de comprobaciones de `presionPrescrita`. Por tanto, una frontera rígida válida con `presionPrescrita: false` cae en ese `else` y recibe `MOTOR_ENS_FRONTERA` inválido.

El caso procede de `motor-ensamblaje-resolver-condensacion-rigida-peticion.json`, sustituyendo los datos por masa 1 kg, T0=10 °C, volumen 200 L, calor 2 kW y tiempo 1287.2729020225838 s. `/validar` devuelve recuento `listo`, GL=0, pero `modeloId: null`, inicialización pendiente y el diagnóstico de frontera inválida. El lector frontend lo rechaza; no hay que debilitarlo.

Corrección propuesta: mover el bloque `else: diag(MOTOR_ENS_FRONTERA, ...)` inmediatamente después de `elif tipo_fr == "sin_relacion"`, antes del comentario de la guarda opcional. Retirarlo del final de la cadena de comprobaciones `pp`. Conservar todas las guardas de presión existentes y sus diagnósticos.

No hay cambios de ecuaciones, propiedades, límites, datos, recuento ni algoritmo. Es una corrección de flujo de control. Comprobar frontera rígida válida, presión prescrita válida, tipo desconocido, contradicciones del flag y compatibilidad cuando no se declara.
