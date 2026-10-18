# Comprobación desde la interfaz: materia, energía y fases

14 de octubre de 2026. Cinco hojas aisladas, armadas mediante los controles de `/motor`, resueltas por `/motor/ensamblajes`. No se añadieron ramas de escenarios al motor, correlaciones, flashes ni integradores. No se modificaron backend, `/laboratorio`, proveedor ni hojas previas del usuario.

Los JSON de esta carpeta contienen las solicitudes y respuestas originales que se mostraron en **Detalles técnicos → Solicitud enviada y certificados de muestra**. Los números no se corrigieron ni se regeneraron a mano. El script comprueba el lector real del frontend y referencias algebraicas independientes de la integración. No es una validación independiente de IAPWS-95: las propiedades de los estados puntuales proceden del mismo proveedor.

## Recorridos completados

| Hoja | Definición | Resultado |
| --- | --- | --- |
| [Ebullición a presión constante](http://localhost:3000/motor/hojas/baeb376d-bfde-4b34-8420-95065a8a22a8/resultados) | Cerrado, frontera móvil, 1 kg, 20 °C, 1 bar, Q=10 kW, 5 min | 103 muestras; aparición de vapor a 33.34978575 s; desaparición de líquido a 259.09416238 s; vapor final con q=1 |
| [Cambio de fase prohibido](http://localhost:3000/motor/hojas/9f6bbb86-bbaf-4b58-8f88-35bb3518aa7c/resultados) | Mismos datos; solo cambia la política de transición | Parcial a 33.34978575 s, con diagnóstico y 13 muestras certificadas; no continúa después del evento |
| [Doble potencia](http://localhost:3000/motor/hojas/97996206-86b6-4610-9355-1f18d557bdda/resultados) | Q=20 kW durante 2.5 min; misma energía aportada | Mismo estado final; tiempos de transición exactamente a la mitad, dentro de la tolerancia comprobada |
| [Condensación rígida](http://localhost:3000/motor/hojas/db464272-ca47-4401-86b9-f28f89674205/resultados) | Cerrado, V=1 m³, 2 kg, T0=500 K, Q=−5 kW, 400 s | 102 muestras; aparece líquido a 55.22015524 s; P pasa de 452717.14 a 207323.12 Pa; masa y V constantes |
| [Salida de líquido y calentamiento](http://localhost:3000/motor/hojas/9b807494-6a4b-4447-8309-a303d4e13387/resultados) | Frontera móvil, 1 bar, 1 kg a 20 °C, Q=10 kW, salida de líquido de 0.001 kg/s, 150 s | 102 muestras; masa final 0.85 kg; q final 0.610790735; aparece vapor a 32.79981245 s |

Las hojas se pueden modificar y volver a resolver. Sus títulos y números son datos de comprobación, no modos especiales de cálculo. La prueba a presión constante tiene frontera móvil y libre para expandirse; no representa un tanque rígido ventilado.

## Referencias fundamentales

### Cerrado, presión constante

\[
\frac{dm}{dt}=0,\qquad \frac{dU}{dt}=\dot Q-P\frac{dV}{dt},\qquad H=U+PV
\]

\[
P=\mathrm{cte}\ \Longrightarrow\ H(t)=H_0+\dot Q t
\]

Con las entalpías puntuales de saturación del proveedor, los instantes independientes de la integración son:

\[
t_\ell=\frac{m h_\ell-H_0}{\dot Q},\qquad
t_v=\frac{m h_v-H_0}{\dot Q}
\]

Referencias: 33.34978569 s y 259.09416235 s. La temperatura en coexistencia es 372.75592890 K (99.60592890 °C). Se comprueban la meseta, la regla de la palanca, q=1 en vapor sobrecalentado y la ausencia de Cp/Cv globales ficticios en coexistencia.

También se verifica por separado el trabajo integrado publicado:

\[
U(t)-U_0+W(t)-W_0=\dot Q t
\]

El error máximo observado es 0.02043767 J sobre 3 MJ aportados. No se confunde este error absoluto con los residuos escalados del backend. Para esta comparación se admite el mayor de 100·atol de energía y 100·rtol·máx|H|; el cierre lineal en H se exige dentro de 1e−6 J y da 2.33e−10 J.

### Cerrado, recipiente rígido

\[
\frac{dm}{dt}=0,\quad \frac{dV}{dt}=0,\quad \dot W_b=0,\quad U(t)=U_0+\dot Q t
\]

T, P y el reparto de fases proceden del cierre UV, no de una presión o fase fijadas. Se comprueban masa y V constantes, presión variable, aparición de líquido y cierre de U. El error máximo de U frente a la referencia lineal es 0 J a la precisión publicada.

### Abierto, salida de líquido a presión constante

\[
\frac{dm}{dt}=-F,\qquad \frac{dH}{dt}=\dot Q-F h_\ell
\]

Mientras hay una sola fase líquida, h de salida es la del líquido del volumen:

\[
m(t)=m_0-Ft,\qquad h(t)=h_0+\frac{\dot Q}{F}\ln\frac{m_0}{m(t)}
\]

La entrada en coexistencia y la evolución posterior se obtienen sin aproximar Cp:

\[
t_b=\frac{m_0}{F}\left[1-\exp\left(-\frac{F(h_\ell-h_0)}{\dot Q}\right)\right]
\]

\[
H(t)=m(t)h_\ell+\dot Q(t-t_b),\qquad
q(t)=\frac{\dot Q(t-t_b)}{(h_v-h_\ell)m(t)}\quad (t\ge t_b)
\]

Referencia de aparición: 32.79981237 s. Error máximo de masa: 5.55e−15 kg; de H: 2.33e−9 J. Se comprueba que la corriente transporta h del líquido y no la entalpía de la mezcla bifásica. No se agrega un término extra de calor latente: ya está en h y en el reparto.

## Ejecución y alcance

Desde `frontend`:

```powershell
node qa_cambio_fase_2026_10_14/verificar.mjs
node verificar_integracion_ensamblaje.mjs
npx tsc --noEmit
npx eslint app/motor/resultadoEnsamblaje.ts app/motor/ResultadosHoja.tsx
```

El primer comando reproduce la auditoría de las respuestas capturadas y escribe `evidencias.json`: **1720 comprobaciones**, cinco recorridos y dos controles negativos adicionales que corrompen Q o W. La suite general de integración sigue pasando: 231 comprobaciones sobre los 13 ejemplos originales del backend. TypeScript y ESLint pasan.

La única corrección de producto fue el aviso de detención por cambio de fase prohibido: mensaje breve en resultados, tiempo mostrado una sola vez y diagnóstico original intacto en detalles técnicos, incluidos resultados ya guardados.

Esto verifica estos regímenes de **agua pura, un volumen, equilibrio estable y fronteras admitidas**. No cierra la validación de mezclas, varios volúmenes térmicos, cambio de fase fuera del equilibrio ni momento. La vigilancia de eventos del backend usa tres puntos interiores y el extremo de cada paso; estas pruebas no prueban que se detecte toda excursión arbitrariamente rápida entre esos puntos. El script reproduce las capturas; para comprobar una versión futura del servicio hay que volver a ejecutar las hojas y exportar sus nuevas respuestas.
