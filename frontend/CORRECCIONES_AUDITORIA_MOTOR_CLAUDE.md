# Correcciones del motor tras la auditoría — entrega autosuficiente

**Estado actualizado: cumplido en §25.** Las quince sondas y las 69 regresiones de corrección fueron verificadas por Codex; todas pasan. No repetir estos hitos. Este documento conserva los criterios históricos; el seguimiento está en `INTEGRACION_ENTREGA_25.md` y la ampliación propuesta en `SIGUIENTE_CLAUDE_BASES_DIMENSIONES.md`.

## Contexto vigente

El backend entregó §24, revisiones 10–13, y corrigió `tk.area` en §24.6. Las 37 suites pasan. No hay que repetir esos hitos. El frontend reorganizó supuestos y trazado; la integración completa de piezas nuevas sigue pendiente.

La auditoría está en `docs/AUDITORIA_MOTOR_2026_10_11.md`. Las evidencias completas están en `docs/auditoria_motor_2026_10_11/evidencias.json`. El script `python tests/auditoria_motor_acoplado.py` reproduce nueve incidencias; actualmente devuelve código 1 deliberadamente. No es un fallo de instalación ni una prueba para excluir.

Este documento prepara la siguiente entrega: **corrección de física y validación de combinaciones ya aceptadas**, antes de nuevas ampliaciones. No encarga todavía un solver DAE general ni un rediseño completo. No trabajar en frontend ni en el cambio ajeno de `thermodynamics/proveedor.py`. No hacer commit/push salvo autorización del usuario.

## Orden y criterios de aceptación

### Hito 1 — mismo modelo y datos respetados

1. **A1: estacionario del balance general con intercambios.** `_energia_estacionaria_bg()` ignora las interfaces. La sonda `estacionario_balance_general_con_vapor` devuelve 300 K en vez de 345,827468 K y deja una derivada de energía de 12 616,302 W en el residuo común. Resolver todos los términos del ensamblaje; una ruta especializada solo se usa si es equivalente. Si una combinación sigue sin estar implementada, rechazarla explícitamente y ajustar capacidades; nunca aceptarla suprimiendo sus términos. Comprobar interfaces directas, pared y cámara, con y sin calor exterior. No dar por ejecutado un balance cuyo término no se pudo evaluar.
2. **A2: escalado de la compatibilidad.** En `_analisis_lineal()`, un inventario grande oculta la contradicción de caudales. La sonda `contradiccion_oculta_por_escala_inventario` da 0,0001 mol/s a la entrada y 0,0002 a la salida; se acepta y se modifica la salida dada. Usar escalas por magnitud/variable/ecuación y comprobar los datos originales tras resolver. Cambiar el tamaño de los inventarios no puede convertir una contradicción de caudales en redundancia compatible. Mantener unidades equivalentes y referencias exactas a los datos en conflicto. No describir SVD tolerada como rango aritméticamente exacto.
3. **Comprobación final.** Antes de `resuelto`, evaluar todas las ecuaciones activas, restricciones, dominios y especificaciones originales. Un residuo global nulo o GL = 0 no acredita que se cumplan todos los balances locales. Si algo no se pudo comprobar, declararlo y no certificar resolución completa.

Aceptar este hito contra referencias independientes y sustitución de la solución en el residuo temporal del mismo montaje, no solo contra otra ruta del motor.

### Hito 2 — bases cinéticas por ley

**A3** tiene dos reproducciones:

- Lote: `core/lote.py` calcula actividades con la primera reacción y las reutiliza para todas. Reordenar dos leyes con bases diferentes cambia 2,172841 mol. Cachear por base, composición y T.
- Clase compartida: `ReaccionCinetica.tasas()` entrega las actividades directas a una inversa que declaró otra base. En la sonda `cinetica_inversa_base_distinta`, la tasa inversa correcta es 0,5082597615 mol/s y sale 0,5.

Cada ley respeta su base. Si una combinación no se admite, rechazarla antes del solver, sin sustituir silenciosamente el dato. Mantener las restricciones de la inversa derivada de K. Verificar lote, CSTR y estudios con gamma distinto de 1, permutación de leyes y evaluación independiente de tasas. Los xilenos con gamma = 1 no cubren este fallo.

### Hito 3 — dominio y eventos

1. **A4: capacidad inicial.** Rechazar o declarar fuera de régimen en t = 0 un inventario que ya supera `capacidad_maxima`; no esperar un cruce que nunca ocurrirá. La sonda acepta 0,036364 m³ en un recipiente de 0,025 m³. Comprobar inicial por debajo, justo en el límite y por encima, con derivadas hacia dentro y hacia fuera; también el estacionario si declara capacidad.
2. **A5: salida inicial negativa.** El cierre reactivo produce −900 mol/s desde t = 0 y se publica en un resultado `parcial`. Validar caudales derivados y el dominio completo antes de integrar y al reiniciar en cada escalón. No presentar un tramo físicamente válido si ya empieza fuera del régimen. No reinterpretar automáticamente un caudal negativo como una corriente invertida.
3. **A6: cámara con contactos opuestos.** La cámara puede ceder calor al frío y absorberlo del caliente, manteniendo neto positivo. El régimen actual prohíbe el contacto que necesitaría evaporación. Comprobar cada contacto orientado, además de suministro agregado. Si se desea ampliar a ese régimen, hacerlo en otra entrega con formulación y referencias; no ampliar el alcance implícitamente para hacer pasar la sonda.
4. **A7: fuente compartida.** `/validar` acepta una fuente de 5 kW conectada a dos volúmenes y el residuo aplica 10 kW. La conservación de `/resolver` la detiene; esa guarda debe conservarse, pero el fallo se debe diagnosticar antes de integrar. Una potencia total única necesita destino único o una ley de reparto explícita. No fabricar el reparto y no reutilizar el mismo identificador para dos potencias independientes. Citar todas las conexiones afectadas.

Estas comprobaciones son generales del dominio y de la identidad de flujos, no reglas para reconocer nombres de ejemplos.

### Hito 4 — rutas públicas y procedencia

1. **A8: DiagramaFlujo heredado.** `resolver(max_iteraciones=20)` sobrescribe el límite dinámico del Orquestador. Treinta bloques terminan incompletos; con `None`, dan salida 30. Propagar el valor por omisión apropiado, manteniendo límites pedidos explícitamente y comprobando el límite interno del reciclo. Esta corrección no habilita N volúmenes en `/estudios`.
2. **A9: Corriente pública.** Rechazar NaN/infinito en F/T/P y composición en la clase Python, sin depender de un validador HTTP. Mantener los dominios y las pruebas de flujos cero.
3. **Procedencia.** `_ejecutar()` de estudios etiqueta el proveedor como `ninguno (modelo material; densidad declarada)` incluso con energía/proveedor/vapor. Emitir una procedencia correspondiente a las propiedades realmente usadas.
4. **Supuestos efectivos.** El contrato actual aplica adiabático global OR local. Documentarlo y devolver/identificar el valor efectivo y su origen para que el frontend no trate local false como una revocación del global true. Si se amplía a herencia triestado, definir la migración y validarla; no cambiar de semántica silenciosamente en una corrección.

## Entrega y pruebas

- Convertir los casos corregidos en regresiones normales ejecutadas por `python run_tests.py`; mantener el script de auditoría como comprobación independiente.
- Correr batería completa de backend, sondas y pruebas del frontend. No excluir ejemplos ni relajar lectores para obtener verde.
- Mantener correspondencia `/validar`–`/resolver`, ids de variables, unidades y referencias por pieza/conexión. Si corregir un cálculo cambia un resultado anterior, explicarlo y regenerar ese ejemplo ejecutando su endpoint.
- Actualizar `docs/ENTREGA_LABORATORIO_CODEX.md` con cada corrección, límites restantes y cambios visibles. Conservar identidades físicas cuando el modelo no cambie; distinguir una corrección del algoritmo de un cambio de montaje.
- La sección de ecuaciones debe poder recibir el ensamblaje real antes de resolver, incluso con datos pendientes. Preparar este contrato por separado si requiere una ampliación: no implementarlo en JavaScript ni incluir ecuaciones orientativas como ejecutadas.

## Después de corregir

La dirección propuesta es un ensamblaje común de variables, balances, constitutivas, restricciones, dominios y puertos, con un residuo global `R(t,z,dz/dt)=0`. Temporal y estacionario operan sobre ese mismo modelo. ODE reducida sigue siendo válida para las restricciones que se puedan eliminar correctamente; no hay que introducir un solver DAE para cada caso por obligación.

Generalizar N volúmenes, ramificaciones, lazos y especificaciones arbitrarias requiere una entrega y criterios propios después de estos hitos. El objetivo es composición de piezas con un método adecuado; los presets serán ejemplos de entrada, no la arquitectura del motor.
