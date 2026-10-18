# Ecuaciones activas y condiciones mecánicas

14 de octubre de 2026. Cambios solo en `/motor`; backend y laboratorio sin modificar.

## Presión

`FormulacionEnergia.presionUniforme` significa `p(x,t)=P(t)`. No convierte P en un dato, no fija su valor y no implica constancia temporal.

El campo opcional nuevo `presionPrescrita` expresa `P(t)=P_ext(t)`. Las formulaciones nuevas lo inicializan en false. Elegir presión exterior dada también declara la reducción mecánica uniforme. Retirar esa condición conserva la uniformidad y los valores guardados; la relación mecánica queda pendiente. Una presión prescrita con uniformidad retirada se diagnostica como incompatible con la reducción actual.

Las hojas antiguas sin este campo conservan la interpretación anterior: presión uniforme con puertos o frontera móvil tenía presión dada. La lectura normaliza cada paso y su historial de rehacer sin mutar la hoja ni cambiar su firma guardada. Un false explícito nunca se reemplaza por la interpretación antigua.

El preparador dinámico utiliza la condición explícita para construir `frontera`. El campo nuevo no amplía capacidades ni habilita rutas. En particular, presión uniforme en un dominio rígido no añade automáticamente una presión prescrita al cierre UV. Una condición de presión realmente elegida se conserva como restricción adicional.

## Volumen

- `V_geom`: geometría fija del dominio de integración; dato con unidad.
- `V_ocup`: volumen ocupado por el fluido; en el modelo manual de densidad constante vale `m/rho_*`.
- `V`: volumen del dominio de integración. La reducción manual existente toma `V=V_ocup`; esta igualdad ahora aparece explícitamente.

Con dominio fijo, fluido ocupándolo completamente y densidad constante, la compatibilidad exige `dm/dt=0`. No es una consecuencia de rigidez por sí sola. No se ha añadido un modelo de espacio libre, nivel o capacidad máxima del recipiente; los datos geométricos no se interpretan como propiedades termodinámicas ni como capacidad máxima.

## Ecuaciones finales

`ecuacionesSistemaEnergia.ts` genera las relaciones activas desde la formulación compartida. La vista final y la procedencia del solver consumen esa lista. Se muestran energía almacenada, cierre manual, presión, volumen, entalpía/trabajo de flujo y trabajo de frontera según las elecciones reales. Las definiciones integrales de términos activos quedan en un único desplegable; las de términos eliminados no aparecen en esa lista.

`donanteCorrienteEnergia` comparte la selección del donante entre campos requeridos y representación final. Los caudales constantes conocidos usan directamente T exterior o T del volumen. Los caudales que pueden invertir muestran la condición por signo, sin inventar una temperatura de salida independiente.

Las identidades y consecuencias no equivalen a ecuaciones independientes adicionales. Este cambio no modifica el recuento estructural ni certifica rango, estado de fase o dinámica IAPWS. La consulta termodinámica puntual conserva su separación respecto del cierre manual.

## Verificación

`verificar_relaciones_energia.mjs` cubre migración sin modificación de datos/firma, iniciales y RHS idénticos en hojas antiguas, diferencia entre presión uniforme e impuesta, condición mecánica pendiente, geometría/volumen ocupado, selección del donante, inversión, términos retirados y coincidencia entre representación y procedencia. Se incorpora a `test:motor-fundamental`.

La entrega dinámica de Claude continúa siendo el contrato único `CONTRATO_CLAUDE_ENSAMBLAJE_DINAMICO_MOTOR.md`. No se ha implementado un segundo solver termodinámico ni cambiado su esquema de frontera.
