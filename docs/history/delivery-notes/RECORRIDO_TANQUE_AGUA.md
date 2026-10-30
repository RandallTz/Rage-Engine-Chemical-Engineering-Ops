# Recorrido de un tanque de agua

Implementado en el frontend el 11 de octubre de 2026. No cambia el motor ni el contrato pendiente `ESTADO_MODELO_EXPERIMENTAR.md` que está trabajando Claude.

## Recorrido verificado en el navegador

1. Mis mesas → Crear mesa → añadir un volumen de control.
2. Componentes → buscar `water` en thermo → añadir agua (CAS 7732-18-5).
3. Experimentar → Definir caudales. Esta acción explícita activa el balance general, sin introducir números ni una ley de salida.
4. Entrada: 10 mol/s. Salida: 9 mol/s. Cantidad inicial: 100 mol. Duración: 10 min.
5. El servicio valida el modelo; el indicador muestra Falta = 0 y habilita Resolver.
6. Resolver devuelve 700 mol a los 600 s. La tabla permite consultar esa muestra final.
7. Volver a Mis mesas y abrirla conserva nombre, componente, valores y unidades. Resolver de nuevo reproduce el resultado.

La mesa de comprobación se llama `Tanque de agua · recorrido de prueba`. Se verificó también el estacionario con entrada como dato, salida como incógnita y cantidad presente especificada: devuelve salida = 10 mol/s, distinguiendo Dato y Calculado.

## Cambios de experiencia

- Seleccionar una pieza en el diagrama selecciona sus variables. Enfocar una variable selecciona la pieza; las corrientes resaltan su conexión.
- El panel del diagrama y Experimentar leen y editan la misma selección de caudales del balance general, sin crear especificaciones duplicadas.
- El panel del tanque lee el recuento real del sistema lineal, igual que Experimentar, y muestra los caudales calculados desde los estados devueltos.
- Los compuestos conservan su nombre confirmado en campos, gráficas y tablas. El identificador químico sigue siendo el mismo.
- Los resultados estacionarios muestran elemento, variable, origen, valor y unidad. Seleccionar el elemento permite ubicarlo.
- Los avisos del resultado se consultan en Detalles técnicos, con contador visible. Los errores y eventos de parada permanecen visibles en la vista principal.
- Cambiar datos señala que el resultado anterior está desactualizado; no se presenta como una respuesta vigente.
- Abrir otra mesa, o recuperar una, reinicia la sesión de resultados. Se conservan los datos del modelo; los resultados se vuelven a calcular.
- Guardar conserva los puertos dinámicos de las conexiones y las selecciones Dato/Calcular. La protección durante la carga de una mesa incluye su estudio completo.
- La tabla temporal tiene páginas de 100 muestras, incluido el extremo final. Solo se redondea su presentación; la respuesta y las exportaciones conservan los valores originales.

## Verificación

- TypeScript y ESLint de los componentes modificados: correctos.
- Batería frontend `npm test` y `npm run test:estado-modelo`: correctas.
- `npm run test:recorrido-agua`: referencia analítica, equivalencia 10 min/600 s y 36 kmol/h/10 mol/s, persistencia, puertos, identidad de componente y clasificación Dato/Calculado contra el servicio activo.
- Comprobación manual en navegador: creación, configuración, resolución, selección cruzada, aviso de resultado obsoleto, guardado/reapertura y muestra final.

## Límites conservados

El acceso directo a Definir caudales se ofrece únicamente si no hay un cierre existente y el montaje satisface el alcance publicado del balance general. Una relación ya declarada se revisa antes de sustituirla. Se mantienen los límites del backend: una especie, uno o dos volúmenes y materia sin energía ni reacción para ese cierre. Los caudales temporales son datos de frontera; no se habilita un problema inverso temporal.

El recuento y la habilitación de Resolver dependen de la validación del servicio. Este trabajo no implementa ni simula el contrato nuevo de recuento que está en curso en el backend.
