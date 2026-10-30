# Integración de §27: fronteras materiales e inserción

12 de octubre de 2026. Trabajo de frontend; backend y `thermodynamics/proveedor.py` intactos. Sin commit ni push.

## Interacción

El panel del volumen tiene un control compacto «Intercambio de materia»: **Por definir / Abierto / Cerrado**. Cerrado se refiere solo a materia; no implica adiabático.

Los volúmenes nuevos guardan `data.fronteraMaterial: "automatica"` como metadato del editor. Sin corrientes se envían como borradores pendientes. Con corrientes ordinarias se declaran abiertos; una entrada o salida aún no dibujada se declara en `fronteras_pendientes`. Al completar las conexiones desaparece ese pendiente. Al retirar todas las corrientes vuelven a borrador, nunca a cerrado implícito.

Una elección explícita del usuario reemplaza ese modo automático. Declarar cerrado con corrientes conserva el dibujo y se envía al servidor para diagnosticar la contradicción. Calor, trabajo e interfaces selectivas no se cuentan como corrientes ordinarias. El control no agrega conexiones ni elimina datos.

Las mesas anteriores sin declaración mantienen la inferencia histórica. Las declaraciones importadas se conservan. Guardar, importar y reabrir conservan tanto el contrato como la elección del editor. Solo se depuran referencias a piezas realmente eliminadas; una referencia desconocida sigue llegando al servidor.

## Contrato y navegación

`solicitudDesdeMesa` envía `fronteras_materiales`, versión 1, según §27.2. El catálogo, los valores y el recuento siguen perteneciendo al servidor. No se inventan variables de frontera ni un caudal cero.

Los pendientes con ruta `fronteras_materiales.volumenes` se identifican como «Intercambio de materia». Su acción desde Experimentar vuelve al diagrama y abre el panel del volumen correspondiente. Los enlaces a datos numéricos continúan usando sus campos específicos.

La corriente nueva no se muestra como pendiente antes de elegir la relación de salida: el recuento del servidor mantiene su cota inferior. No se amplían los límites de dos volúmenes ni se habilitan ramas.

## Servicio anterior

En la prueba visual, el servicio de localhost:8004 aún devolvía el comportamiento anterior para el borrador aislado. Ahora, cuando la mesa envía una declaración, la UI exige una respuesta con revisión ≥ 15 y `fronteras_materiales[]`. Si no la recibe, muestra «Recarga el backend con la entrega 27» y descarta esa validación.

No se reinició el servicio durante esta integración. Hasta recargarlo, la navegación de pendientes de §27 y la resolución con esas declaraciones no están verificadas de extremo a extremo en el navegador.

## Verificación

- `npm test` pasa, incluida `verificar_fronteras_mesa.mjs` (`npm run test:fronteras`).
- `npx tsc --noEmit` pasa.
- ESLint pasa sobre los archivos de aplicación modificados.
- Pruebas: transición borrador → una frontera → dos fronteras; retirada; cerrado elegido con corrientes intactas; calor e interfaz excluidos; mesas antiguas; importación de declaraciones; persistencia; referencias eliminadas frente a desconocidas; ejemplos canónicos de §27; rechazo de respuestas del servicio antiguo.
- Navegador: mesa aislada **UI · fronteras explícitas · entrega 27**; volumen nuevo por definir; abierto muestra entrada y salida pendientes; cerrado se conserva al volver a Mis mesas y reabrir; aviso real de servicio anterior.
- No se ejecutó la batería completa del backend. Una comprobación adicional en proceso no se completó y fue detenida; no se usa como evidencia de aprobación.

Evidencia: `preview-fronteras-entrega27.jpg`.

## Siguiente trabajo

La fuente térmica compacta sigue pendiente: debe representar la misma pieza `calor` y su conexión actuales, con una sola Q. Esta entrega integra fronteras y no cambia esa representación.
