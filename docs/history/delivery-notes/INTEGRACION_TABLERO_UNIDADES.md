# Tablero de resultados y unidades — 11 de octubre de 2026

## Implementado en frontend

- Resultados abre un tablero con gráficas en paralelo o verticales. Añadir y editar abre una vista específica; la selección de variables no ocupa permanentemente el tablero.
- Cada gráfica permite cualquier serie devuelta en X y varias series en Y, incluso tiempo en Y. La lista permite buscar por nombre, sistema, identificador y unidad.
- Reordenación por arrastre del asa o flechas del teclado; duplicar, quitar, cambiar a ancho completo y ajustar la altura por arrastre o teclado.
- Ejes separados por unidad, leyendas y tooltip con unidades. Las curvas conservan el orden y la correspondencia de muestras: no se ordena X, no se interpola ni se rellenan huecos. X ausente interrumpe también Y; cero sigue siendo cero.
- La configuración se guarda en `EstudioSistema.tablero`, separada de `solicitud`. Sobrevive a guardar y exportar/importar la mesa. Cambiar la visualización no cambia el cuerpo enviado al solver ni sus identificadores.
- Campos de cantidades con unidad junto al valor. Cuando el catálogo y las capacidades anuncian una conversión compatible, cambiar de unidad conserva la cantidad física. Un número incompleto bloquea el cambio de unidad.
- En resultados, cambiar unidades transforma solamente las muestras representadas; conserva intacta la respuesta original, la tabla y los objetos transferidos.
- Al convertir los límites de un dominio térmico se convierten ambos extremos, porque comparten una unidad. No se introduce cero para completar valores ausentes.

## Contrato usado y límites actuales

El frontend consulta ahora `GET /laboratorio/estudios/unidades` del servicio configurado para el laboratorio (8004 por omisión). Lee factores y desplazamientos publicados por el motor. Tiempo, cantidades molares, volumen, densidad, energía total y capacidades térmicas están disponibles en el registro ampliado. La duración ya permite s/min/h. No se inventan conversiones que requieren propiedades.

§22 está integrada: Dato / Calcular y resolución estacionaria hacia delante/atrás en el balance general de una especie y uno/dos volúmenes materiales. Los montajes anteriores mantienen su física; cambiar al balance general requiere aplicar explícitamente el cambio. Ver `INTEGRACION_ENTREGA_22.md` para límites, persistencia y verificación. No se habilita inversión temporal.

## Comprobaciones

- `npm test`: batería existente del frontend.
- `npm run test:tablero`: requiere el backend local; comprueba conversiones con su catálogo real, afinidad de temperatura, separación masa/moles, huecos/cero, ejes, orden de muestras, reordenación, persistencia y edición sin mutaciones.
- `npx tsc --noEmit` y ESLint en archivos modificados.
- Navegador real: 10 mol/s → 36 kmol/h, validación GL=0 y resolución; dos tanques en paralelo; una curva paramétrica con unidades distintas en dos ejes; reordenación y conservación del tablero al cambiar de vista.

No se modificó código del backend ni se hizo commit/push.
