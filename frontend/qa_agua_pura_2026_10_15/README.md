# Auditoría del recipiente de agua pura — 15/10/2026

Hoja: `faaefe12-08b5-43ed-9a67-388d58d6ce5c`. Se exportó su solicitud/respuesta original desde Detalles técnicos, sin modificar sus datos numéricos. **La hoja actual ya tenía 10 kW**, aunque conservaba «1 kW» en el título; se retiró la potencia del título. Se conservan la masa de 2 kg, volumen rígido de 3 L, T0 = 10 °C y horizonte solicitado de 900 s. No se modificó el backend ni se ejecutó el laboratorio.

## Ecuaciones contrastadas

Sistema cerrado y rígido, sin trabajo mecánico ni reacciones:

```
dm/dt = 0
dU/dt = Q
V = constante
U(t) = U(0) + Q t
V = m sum(beta_f v_f)
U = m sum(beta_f u_f)
sum(beta_f) = 1
```

En coexistencia se contrastó además con IF97:

```
P = Psat(T)
q = (V/m - v_liquido)/(v_vapor - v_liquido)
u = (1-q) u_liquido + q u_vapor
```

Se usaron directamente las derivadas de Gibbs de IF97 en regiones 1/2, Helmholtz en región 3 y saturación en región 4. Estas no llaman al flash UV ni a la implementación IAPWS-95 del motor. Es una referencia de formulación distinta, que comparte datos físicos de referencia con IAPWS-95, **no una validación experimental independiente de ambas formulaciones**.

Fuente: [IAPWS R7-97(2012)](https://www.iapws.org/relguide/IF97-Rev.pdf). El código de referencia está acotado a esta trayectoria densa; no es otro solver general de agua.

## Resultados

`python frontend/qa_agua_pura_2026_10_15/verificar_fisica.py`: **2467 comprobaciones**, incluidos controles negativos que alteran energía, masa, presión y reparto de fases y deben ser detectados.

| Contraste | Hoja actual, 10 kW | Referencia anterior, 1 kW |
| --- | --- | --- |
| Estado | Parcial; alcanza límite de dominio | Resuelto hasta 900 s |
| Muestras originales | 41 | 101 |
| Tiempo final [s] | 337.000617 | 900 |
| T final [°C] | 417.339358 | 117.052110 |
| P absoluta final [bar] | 999.999999 | 1.808190 |
| Máximo error de U−U0−Qt [J] | 4.66e-10 | 1.17e-10 |
| Máxima diferencia relativa de P frente a IF97 | 0.02306 % | 0.00705 % |
| Máxima diferencia de calor acumulado frente a IF97 [J] | 474.36 | 141.84 |
| Máxima diferencia absoluta de fracción vapor frente a IF97 | 1.93e-6 | 4.44e-8 |

La temperatura final a 1 kW reconstruida por inversión independiente de energía IF97 es 117.060353 °C: diferencia de 0.008243 K. A 1 kW, el vapor pesa 0.909864 g pero ocupa el 29.5199 % del volumen. **Fracción másica y volumétrica no son intercambiables.**

Refinamiento en ambos casos: 101 → 201 muestras, rtol 1e-8 → 1e-10 y tolerancias absolutas más estrictas. Coinciden T/P/q en las muestras comunes a la precisión reportada; variación máxima de U a 1 kW: 2.92e-11 J. Los tres eventos de 10 kW mantienen orden e instante a la precisión reportada. Es una trayectoria especialmente sencilla para el integrador: U evoluciona linealmente; esta convergencia no certifica otras ODE/DAE.

Se verificaron también normalización de fases, reconstrucción de volumen y energía a partir de cada fase, no negatividad, certificados publicados, aumento de entropía del contenido y detención antes de publicar estados fuera del dominio.

## Interpretación física y límites

- Al omitir el aire, el equilibrio inicial líquido/vapor a 10 °C tiene P ≈ 1228.2 Pa. Es un recipiente con espacio de vapor inicialmente a baja presión; **no** representa cerrar una olla llena de aire a 1 atm.
- V/m = 0.0015 m³/kg: trayectoria densa. A 10 kW el vapor primero aumenta y después desaparece al expandirse el líquido hasta ocupar el recipiente. La muestra de desaparición a 280.857649 s tiene líquido único, T ≈ 320.171951 °C y P ≈ 113.100106 bar. No significa que desaparezca el líquido ni que todo se haya vuelto vapor.
- A 312.568874 s se cruza la convención de denominación a `fluido` por encima de Tc y Pc. Es un cambio de etiqueta de la fase única, no una discontinuidad de energía ni un calor latente nuevo. Aquí líquido = 0 y vapor = 0; fluido = 1.
- A 337.000617 s se alcanza P = 100 MPa, límite publicado del modelo. El estado es parcial, no una solución de los 900 s. No se extrapola el resto.
- Sin aire, pared, pérdidas térmicas, válvula, fugas ni resistencia mecánica. La conservación y el acuerdo termodinámico son consistentes con **este recipiente ideal**. No certifican la seguridad ni el comportamiento completo de una olla real. 10 kW es un aporte neto muy intenso para 2 kg de contenido; no se ha reducido para conseguir un resultado deseado.

## Gráficas

El catálogo de gráficas y la tabla/CSV ahora incluyen fracción másica líquida, agregada de las fases certificadas. Si se publica fluido o sólido, también se ofrece su fracción. No se usa `1-q` para inferir líquido ni se vuelven a calcular fases en el navegador. Los valores originales del backend y sus certificados no se alteran; las series adicionales se generan solo para presentación. No hace falta volver a resolver resultados ya guardados.

En esta hoja se guardó una gráfica con vapor, líquido y fluido; la potencia y el resultado del usuario permanecieron intactos. En futuras gráficas iniciales de trayectorias con coexistencia se seleccionan las fases juntas.

Verificación de integración: 422 comprobaciones, 13 pares reales y 164 muestras; incluye líquido, vapor único, coexistencia, fluido y persistencia sin alterar series originales. También pasan `npm run test:motor-fundamental`, `npx tsc --noEmit` y ESLint de los módulos modificados.

## Archivos reproducibles

- `respuesta-ui.json`: solicitud/respuesta original de la hoja a 10 kW.
- `respuesta-1kw.json`: solicitud/respuesta del contraste a 1 kW, fuera de la hoja del usuario.
- `verificar_fisica.py`: ecuaciones de referencia, convergencia y controles negativos.
- `evidencias.json`: resultados y máximos medidos, regenerados por la prueba.
