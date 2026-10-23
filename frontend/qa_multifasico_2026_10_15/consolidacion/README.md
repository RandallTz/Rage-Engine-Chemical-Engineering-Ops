# Evidencia de consolidación C0–C3

15 de octubre de 2026. Las respuestas de la entrega anterior permanecen en el directorio padre.

- `capacidades.json`: GET real al backend actualizado.
- `no-cumple-*` y `no-evaluable-*`: solicitudes y respuestas por HTTP, agua pura rígida con calor impuesto; misma física y distintos datos de temperatura de frontera.
- `liquido-superviviente-*`: solicitud y respuesta por HTTP del decantador hasta 600 s, extrayendo el líquido de mayor densidad. Desaparece `liquido-1` a 509.8015378 s; `liquido-2` conserva su ID.
- `calentamiento-ui.json`: exportación del panel visible Solicitud y certificados originales, después de resolver desde UI con la consolidación cargada.
- `no-cumple-ui.json`: misma hoja etanol–agua, temporalmente con frontera a 300 K frente a sistema inicialmente a 330 K y calor entrante. La ejecución termina numéricamente pero no cumple segunda ley; se comprobó aviso y sombreado, sin recortar la evidencia.
- `no-evaluable-ui.json`: misma hoja, retirando la temperatura de frontera. La interfaz muestra no evaluable, no aprobación. Después se restauró el valor original de 600 K y se volvió a resolver.
- `regresion-motor.log` y `regresion-general.log`: ejecuciones completas de `npm run test:motor-fundamental` y `npm test`, ambas con código 0.

Verificador reproducible desde `frontend/`:

```
npm run test:consolidacion
```

237 comprobaciones de lectura e integración. Incluye certificados reales que cumplen, incumplen o no pueden evaluarse; catálogo completo, unidades y papeles; eventos; identidad del líquido superviviente; datos históricos; y controles sintéticos de metadatos corruptos. Los controles sintéticos están identificados en el script y no se presentan como nuevas validaciones físicas del proveedor.

Informe: `../../../docs/history/frontend/integration-consolidation-multiphase.md`.
