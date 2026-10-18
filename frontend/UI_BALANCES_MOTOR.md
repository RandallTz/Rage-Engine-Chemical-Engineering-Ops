# Un sistema, tres balances

Cada hoja es un sistema con un único ID, catálogo de componentes, topología, datos y resultados. La biblioteca muestra sistemas; los tres paneles animados están dentro de cada hoja.

- `vistaBalance` controla únicamente qué ecuaciones se consultan y el acento verde, rojo o azul. No crea hojas ni cambia la firma del cálculo.
- `balances` controla qué familias participan en la resolución. Sus switches son independientes de la vista. Cambiar la selección invalida la referencia del resultado, conservando datos, componentes, pasos, corrientes y gráficos.
- Materia conserva sus derivaciones, acoplamiento y solver actuales. Energía tiene un desglose propio guardado en `energia.historial`, con ecuación local, Gauss, Reynolds, puertos y supuestos. Su primer solver admite un volumen y un componente, temporal, con relación manual u(T); los requisitos y límites están en [FUNDAMENTO_ENERGIA_MOTOR.md](FUNDAMENTO_ENERGIA_MOTOR.md). Momento conserva su vista fundamental en `supuestosBalances` y aún no se ejecuta. Una familia activa no se omite silenciosamente si su formulación no está soportada.
- Las hojas antiguas heredan materia activa, energía y momento inactivos. Su firma y sus resultados no cambian. Las antiguas rutas de categorías redirigen a la biblioteca común.
- La selección se aplica al sistema completo de la hoja (incluidos sus volúmenes acoplados). No añade selecciones distintas por volumen. Materia y energía comparten [m,U] en el primer alcance energético; varios volúmenes con energía siguen pendientes.

No se modifica el laboratorio ni el backend. Los supuestos energéticos aplicados y los términos ejecutados quedan en la trazabilidad del resultado. La fase permanece asumida sin verificación termodinámica. Momento continúa como referencia simbólica.

Verificación: `npm run test:motor-fundamental`, TypeScript, ESLint y navegación visual de una misma hoja entre los tres balances. `verificar_seleccion_balances.mjs` comprueba las ocho selecciones posibles en todos los ejemplos, guardas de compilación y resolución, persistencia, preservación de datos y equivalencia numérica material.
