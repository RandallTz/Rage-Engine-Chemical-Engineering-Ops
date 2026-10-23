# Retirado de /adimensionalizacion el 18 de octubre de 2026

- `ExploracionAutomatica.tsx`: preparador combinatorio que exportaba propuestas sintácticas de objetivos sin evaluarlas. Quedó superado por la búsqueda del núcleo, que recorre los subconjuntos independientes y certifica cada formulación. Sus ajustes útiles (presupuesto y grupos Π) siguen en «Opciones avanzadas → Búsqueda de formulaciones». La lógica `app/adimensionalizacion/exploracion.ts` se conserva porque la usan la validación de configuración y `verificar_adimensionalizacion.mjs`.

No se borró: se movió aquí para poder consultarlo.
