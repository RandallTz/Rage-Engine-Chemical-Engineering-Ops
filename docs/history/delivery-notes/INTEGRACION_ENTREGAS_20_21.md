# Integración frontend de §20 y §21

Fecha: 10 de octubre de 2026. Contrato backend documentado: revisión 7. No se modificó el backend, no se hizo commit ni push. Los cambios ajenos permanecen intactos.

## Comportamiento disponible

- Estudios con 1–8 componentes, consultando el rango del servicio. Agua pura conserva un solo componente y el cierre x=1 del motor.
- Interruptores del diagrama enviados como `balances_por_volumen`, con procedencia e herencia. No se borra configuración al desactivar una familia.
- La interfaz distingue solicitado, activo y ejecutado mediante la respuesta vigente del servidor. Activar momento no afirma que se resuelve.
- Energía solo en el primer volumen no exige T inicial ni presenta U/T calculadas en el segundo. Valores térmicos existentes allí permanecen editables para corregir contradicciones.
- `pendientes` y `contradicciones` aparecen junto a la comprobación. GL se lee de la clasificación del motor; Resolver requiere validación vigente y válida.
- `ideal_volumen_fijo`: Cv y energía de referencia explícitas por especie, temperatura de referencia y dominio. Un campo vacío permanece omitido; un cero escrito se conserva. No se convierte Cp en Cv.
- Transferencia selectiva con energía y conducción térmica habilitada solo por su combinación exacta en capacidades. Resultados muestran E transportada y el límite térmico condicionado calculados por backend.
- Los documentos antiguos sin selección conservan su omisión. El borrador local `data.balances` se migra al enviar; los estados transferidos siguen siendo objetos opacos.

## Límites vigentes

Materia desactivada y momento activo siguen rechazados. Energía aguas abajo de un volumen sin energía necesita una frontera térmica que aún no existe. Transferencia selectiva con proveedor o reacción sigue fuera de las combinaciones admitidas. No se habilitó un ensamblador general de ODE/DAE ni topologías arbitrarias.

Las condiciones térmicas y los datos contradictorios no se eliminan en silencio. La selección de energía no crea propiedades, cantidades iniciales ni fuentes por omisión.

## Verificación realizada

- `npm test`: batería completa del frontend, incluida `verificar_entregas_20_21.mjs`.
- `npx tsc --noEmit`: comprobación de tipos.
- ESLint sobre archivos modificados de laboratorio.
- `node verificar_entregas_20_21.mjs --api`: agua pura, prefijo energético y transferencia selectiva con energía validados y resueltos con el servicio local; rechazos de momento y energía solo aguas abajo comprobados.
- Navegador: agua pura con GL=0 y resolución; momento rechazado y Resolver deshabilitado; segundo volumen sin campos térmicos en el prefijo energético; u_referencia ausente rechazada y cero explícito aceptado; serie E y límite térmico visibles.

Las 31 suites del backend son el resultado comunicado por Claude, no una ejecución de esa batería en esta integración.

## Seguimiento para Claude

No repetir §20/21. El documento `SUPUESTOS_POR_VOLUMEN_CLAUDE.md` conserva la cola: otras simplificaciones locales, frontera térmica aguas abajo, formas LaTeX estructuradas y overrides termodinámicamente coherentes por propiedad. Ninguna de estas ampliaciones se presenta como ya resuelta en el cliente.

## Revisión de experiencia de Experimentar

La vista principal indica el tipo de ensayo vigente. «Cambiar» abre una vista dedicada con dos preguntas: estado estacionario o evolución en el tiempo. Cambiar de estudio conserva la solicitud y sus valores; no transfiere por sí solo un estacionario a condición inicial. Esa operación mantiene su flujo explícito del servidor.

Los ajustes tienen una vista propia con categorías; ya no forman una lista de desplegables bajo los valores. Los resultados separan gráfica, tabla, ecuaciones y detalles técnicos. La tabla estacionaria lee `estacionario.estados`, conserva ceros y omisiones, y no confunde los parámetros dados con las incógnitas calculadas. Se verificaron ambas resoluciones en el navegador y el regreso entre estudios.

Este cambio de UI no requiere una nueva entrega de backend ni modifica el contrato numérico.

### Reducción de carga visual · 11 de octubre de 2026

- Valores: solo elementos con campos editables o una relación de salida pendiente. Las corrientes calculadas permanecen en «Ver variables calculadas», con su origen, sin ocupar pestañas de entrada de datos. Las ecuaciones no pierden variables ni términos.
- Resolución: una acción principal cambia de «Comprobar modelo» a «Resolver» al recibir una validación válida y vigente. GL proviene exclusivamente del backend. Editar datos deja sin vigencia la validación anterior. El recuento de ecuaciones se consulta bajo demanda.
- Diagnósticos: el primer aviso queda visible, con acceso al resto; no se eliminan pendientes ni contradicciones. Se priorizan contradicciones y pendientes sobre avisos generales.
- Resultados: la gráfica o los valores calculados aparecen primero. Método, conservación y descarga de la respuesta completa están en Detalles técnicos. Los eventos de terminación parcial siguen visibles. Las etiquetas de gráfica y tabla usan nombres de variables y elementos.
- Verificación: TypeScript, ESLint y batería frontend en verde. Navegador con backend real: validación de agua pura, invalidación al editar duración, restauración del dato, resolución temporal, acceso a variables calculadas y evidencia técnica.

La cola en `SUPUESTOS_POR_VOLUMEN_CLAUDE.md` sigue pendiente y no se amplió en esta revisión de UI.
