# Incidencia de integración: fracción de vapor fuera de coexistencia

14 de octubre de 2026. Reproducida sobre los ejemplos reales entregados de E0–E3. Backend sin modificar por Codex.

**Estado: resuelta y seguimiento cerrado.** Claude unificó q en inicialización y series como suma de las fracciones másicas de las fases vapor. La convención para fluido supercrítico está en `docs/engine/dynamic-assembly.md`. Codex retiró la rama temporal y las correcciones sintéticas de `verificar_integracion_ensamblaje.mjs`. Verificación actual: **231 comprobaciones; 13 pares reales aceptados sin modificar; 164 muestras originales verificadas**. También se mantiene un control negativo que corrompe q y debe ser rechazado. Lo que sigue conserva el diagnóstico original de la incidencia.

## Contradicción original

El catálogo publica `volumen.<id>.q` con magnitud `fraccion_masica_vapor`. En estados de vapor puro, la evaluación certificada tiene una fase vapor con `fraccionMasica=1`, pero la variable inicial y/o la serie q publican 0.

En `backend/motor_ensamblaje.py`, tanto la inicialización como las filas de resultados asignan q=1 para una fase vapor únicamente si hay una verificación `equilibrio`. Un vapor sobrecalentado monofásico no lleva esa verificación, por lo que se publica q=0.

Si q significa fracción másica de vapor, debe ser la suma de las fracciones másicas de las fases vapor presentes, también fuera de saturación. Si pretende significar exclusivamente título dentro de la campana, no puede publicarse un cero fuera de ella como si fuera una fracción de vapor: necesitaría otra semántica explícita y un contrato que represente su ausencia. Acordar y documentar la semántica; para conservar el catálogo actual, la primera alternativa es la corrección mínima.

## Reproducción original

| Ejemplo | Inicial contradictoria | Muestras contradictorias |
|---|---|---|
| `resolver-condensacion-rigida` | Sí: vapor puro, fracción 1, q=0 | 3 |
| `resolver-presion-suave-adiabatica` | Sí: vapor puro, fracción 1, q=0 | 21 |
| `resolver-ebullicion-presion-constante` | No | 6 al terminar en vapor puro |

Los nombres corresponden a `docs/ejemplos/motor-ensamblaje-<ejemplo>-peticion.json` y `-respuesta.json`. Ejemplo concreto: en la inicial de condensación rígida, `fases[0].tipo='vapor'`, `fraccionMasica=1`, mientras `inicializacion.variables['volumen.dominio.q']=0`.

## Comprobaciones solicitadas al backend (entregadas)

1. Unificar el cálculo y significado de q en inicialización y resultados. No cambiar cantidades, estados, energías, integrador ni propiedades.
2. Añadir una regresión que compare q con el reparto de fases publicado en **cada muestra**, incluido vapor sobrecalentado, líquido, bifásico y puntos de entrada/salida de coexistencia. Definir explícitamente la convención para `fluido` supercrítico.
3. Regenerar los ejemplos afectados desde los endpoints y comprobar que solo cambia q donde corresponda.
4. Mantener los eventos y los resultados parciales. El último punto certificado de aparición de fase que detiene una política es una frontera de evento, no una autorización para seguir integrando fuera de esa política.

## Comportamiento inicial del frontend

El lector `app/motor/lectorEnsamblajeTermodinamico.ts` comprueba q contra las fracciones de fase. Rechaza las tres respuestas inconsistentes, sin corregirlas ni dibujar la serie errónea. Los demás ejemplos siguen probándose.

Durante el diagnóstico, `verificar_integracion_ensamblaje.mjs` registraba estos tres rechazos explícitos y usaba copias sintéticas **solo dentro de la prueba** para comprobar el resto del lector y adaptador. Esa rama ya fue eliminada: actualmente se leen y verifican las respuestas originales sin reparar ningún número. Una regresión de q vuelve a hacer fallar la suite.
