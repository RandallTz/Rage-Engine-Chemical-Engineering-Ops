# Pruebas de aceptación: olla con tapa y recipiente hermético

15 de octubre de 2026. Solicitud del usuario: plantear una olla de cocina con agua y fuente constante, observar la respuesta del motor sin escoger cantidades, geometría o tiempo para alcanzar un estado final deseado. El usuario pidió expresamente ambos cierres.

## Actualización: el usuario pidió usar solo agua

**Auditoría posterior:** el usuario cambió el aporte de la hoja hermética a 10 kW. Se conservaron sus datos; el título actual es «Agua pura · Recipiente hermético». Su resultado actual es parcial por límite de 100 MPa, no el resultado de 1 kW descrito a continuación. Los dos casos se contrastaron en [qa_agua_pura_2026_10_15/README.md](qa_agua_pura_2026_10_15/README.md), con evidencias y script reproducible. También se añadió al tablero la fracción líquida a partir de las fases certificadas.

Las mismas dos hojas se cambiaron explícitamente a **agua pura**, retirando N2 y O2 del catálogo mediante la UI. Los apartados agua–aire posteriores se conservan como requisitos futuros, no como descripción de la composición actual.

- **Agua pura · Recipiente hermético · 1 kW**: 2 kg, 3 L rígidos, T0 = 10 °C, calor neto constante de 1 kW, 15 min. Cierre IAPWS-95, sin presión prescrita ni salida. Validado con GL estructural 0 y resuelto desde la UI: 101 muestras, t = 0 a 900 s.
- **Agua pura · Tapa normal · Salida pendiente**: mismo único componente y datos térmicos/geométricos, con salida y presión ambiente de 1.01325 bar. Se mantiene pendiente porque el solver exige caudal dado; no se ha fabricado un caudal ni sustituido el volumen rígido por un pistón. Se seleccionó expresamente el cierre IAPWS-95, sin recurrir al modelo lineal. La UI oculta todavía la elección de fase de salida mientras el caudal está en blanco.

Extremos publicados en la tabla del recipiente hermético:

| Dato | Inicial | A los 900 s |
| --- | --- | --- |
| Masa total de agua [kg] | 2 | 2 |
| U [J], redondeo de la tabla | 84062.11 | 984062.1 |
| T [K] | 283.15 | 390.2021 |
| P absoluta [Pa] | 1228.199 | 180819 |
| V [m³] | 0.003 | 0.003 |
| Fracción másica de vapor | 4.70032e-6 | 4.549322e-4 |

No se fijó temperatura final ni presión final. La presión inicial baja es consecuencia de agua pura líquido–vapor a 10 °C sin aire, no una inicialización a 1 atm. El líquido sigue presente al final; unos 0.91 g están en fase vapor. Esta idealización no representa cerrar una olla con aire a presión ambiente.

En la hoja abierta, agua pura en equilibrio a 10 °C con espacio de vapor de 1 L tampoco es compatible con vapor a 1 atm: no basta con añadir la operación de salida calculada. El futuro modelo debe declarar una inicialización/frontera coherente (por ejemplo, dominio del líquido con superficie libre y atmósfera exterior, o recuperar el gas no condensable). No cambiar silenciosamente los datos iniciales para evitar esta incompatibilidad.

## Preparación anterior: agua y aire (histórico)

Se crearon dos hojas independientes en el navegador. Son **borradores no resueltos**, no simulaciones físicas completadas:

- [Olla · Tapa normal y salida libre · Borrador](http://localhost:3000/motor/hojas/dc6b5810-d38d-478a-8113-5a2b8f8b0425/resolver).
- [Olla · Recipiente hermético · Borrador](http://localhost:3000/motor/hojas/faaefe12-08b5-43ed-9a67-388d58d6ce5c/resolver).

El solver/frontend v1 no admite todavía este ensamblaje. Se conserva su bloqueo; no se quitaron componentes ni se escogió agua pura para obtener curvas. El cierre IAPWS-95 que heredan las copias no es un paquete de mezcla agua–aire y se sustituirá cuando exista uno verificado. No ejecutar un fallback manual ni presentar sus valores como solución de estas ollas.

La entrega v2 en desarrollo añade mezclas, pero los datos actuales de `core/mezclas_datos.py` no incluyen nitrógeno ni oxígeno. Una sonda de la API puntual con el paquete `mezcla-ideal` y los tres CAS devuelve `no_soportado`, con `MOTOR_ESTADO_COMPONENTE_NO_SOPORTADO` para 7727-37-9 y 7782-44-7. Es una comprobación de disponibilidad, no el cálculo del sistema. No interpretar las fracciones usadas por una sonda como composición global de la olla.

## Datos comunes elegidos

| Dato | Declaración |
| --- | --- |
| Volumen interior total | 3 L |
| Cantidad total inicial de agua | 2 kg, aproximadamente 2 L de líquido |
| Temperatura inicial de referencia | 10 °C, conservada de la petición anterior |
| Presión ambiente de referencia | 1.01325 bar absoluta, asumida; sustituible por la local |
| Aire | Modelo inicial de aire seco 79 % molar N2 / 21 % molar O2; se omite argón de forma explícita |
| Masa inicial de N2 | 0.94039 g, estimación de inicialización |
| Masa inicial de O2 | 0.285541 g, estimación de inicialización |
| Aporte neto al contenido | 1 kW constante |
| Horizonte | 15 min, sin condición sobre el resultado final |

Estos números son un punto de partida de escala doméstica, no valores calibrados para acabar en vapor ni a 200 °C. En ambas hojas están guardados 2 kg de agua, 3 L, 10 °C, 0.94039 g de N2, 0.285541 g de O2, 1 kW y 15 min. En la olla normal está además declarada la presión ambiente. El recipiente hermético no lleva una presión prescrita durante la evolución. Las masas de aire se han calculado como estimaciones externas de inicialización; no son resultados de un flash agua–aire certificado.

### Cálculo reproducible de las cantidades de aire

Con R = 8.314462618 J/(mol K), T0 = 283.15 K y P0 = 101325 Pa: se obtiene el volumen específico del líquido con `evaluar_TP(T0, P0).propiedades.v` y la presión/densidad del vapor saturado con `coexistencia(T0)` de `core/agua_iapws95.py`. Se supone aire ideal insoluble y vapor de agua a saturación, sin correcciones de fugacidad de la mezcla. No se ha añadido un modelo termodinámico al motor.

```
V_g = (V - m_agua_total v_liquido) / (1 - rho_vapor v_liquido)
n_aire = (P0 - P_sat) V_g / (R T0)
m_N2 = 0.79 n_aire (0.0280134 kg/mol)
m_O2 = 0.21 n_aire (0.0319988 kg/mol)
```

Resultados antes de redondear: P_sat = 1228.198930688 Pa; V_g = 0.999414167614 L; agua vapor inicial estimada = 0.009401541052 g; n_aire = 0.0424927608421 mol; m_N2 = 0.940389698194 g; m_O2 = 0.285540644683 g. El vapor ya forma parte de los 2 kg de agua, no se añade como otro componente. El paquete futuro deberá recalcular el estado inicial con sus propias relaciones y comprobar la compatibilidad de estas estimaciones con P0; no se garantiza aquí una presión exacta de mezcla.

La masa total de agua incluye el agua que el equilibrio reparta como vapor inicial. No fijar a la vez 2 kg de líquido y 2 kg de agua total si hay vapor. El volumen inicial de aire/vapor es el que queda después del volumen líquido calculado, no 3 L adicionales.

Primera idealización: contenido en equilibrio térmico/fásico local, sin almacenamiento de la pared ni pérdidas térmicas. **1 kW es potencia neta entregada al contenido**, no potencia nominal de un quemador real. No afirmar fidelidad completa de cocina. Añadir pared/pérdidas posteriormente con sus propias relaciones y parámetros, sin inventar coeficientes.

## Inicialización requerida, común

Especificar T0, P0 ambiente, V interior, cantidad total de agua y proporción seca N2/O2. Resolver cantidades de aire y reparto inicial agua líquida/vapor de forma compatible con ese estado.

- La P0 del hermético es una condición de inicialización, no una presión impuesta para t > 0.
- En el flujo futuro por T0/P0/V, la masa inicial de aire será resultado de esta inicialización; si el contrato solo acepta cantidades de todas las especies dadas, esa operación necesita una ampliación explícita. En los borradores actuales se han introducido las estimaciones anteriores como datos, sin imponer simultáneamente P0 como una restricción adicional del hermético.
- No eliminar el aire, ponerlo a cero ni sustituir P0 por Psat del agua pura para que se pueda resolver.
- El agua vapor y los gases comparten la fase gaseosa. No modelar tres gases ocupando tres volúmenes de cabeza completos e independientes.
- Bajo una primera aproximación declarada de gases ideales/aire insoluble, P_total ≈ P_aire + P_vapor y el equilibrio del agua se relaciona con su fugacidad/actividad, no con imponer P_total = Psat(T). El paquete elegido debe construir de forma coherente energía, volumen, entropía y potenciales, con sus referencias.
- No crear líquidos de N2/O2 mediante extrapolación de correlaciones de componentes condensables fuera de su dominio. La omisión de su disolución en agua debe figurar como hipótesis; Henry u otro modelo sería una ampliación posterior.

## Caso A — Recipiente hermético

Dominio rígido cerrado al intercambio de materia, sin válvula ni rotura modeladas:

```
dn_i/dt = 0                          i = H2O, N2, O2
dU/dt = Q_neta
V = 3 L
T, P, cantidades y composiciones de fase = cierre(U, V, n_i)
```

No fijar T_final, P_final, fracción de vapor ni tiempo de vaporización. No garantizar que desaparezca el líquido. El gas se calienta, el agua puede evaporarse y el reparto afecta a la presión total.

Sin modelo de resistencia de tapa/pared, el cálculo describe un recipiente ideal que conserva su cierre; no predice cuándo una olla real perdería estanqueidad, se deformaría o abriría. Al alcanzar límites del paquete o del modelo, detener y diagnosticar; no extender la curva mediante extrapolación silenciosa.

## Caso B — Olla con tapa normal

Primera aproximación de salida libre de resistencia despreciable: presión próxima a P_ambiente. El dominio interior continúa siendo rígido; puede salir fase gaseosa, incluyendo aire y vapor de agua.

```
dn_i/dt = -F_salida y_i,gas
dU/dt = Q_neta - F_salida h_molar,gas
V = 3 L
P = P_ambiente
F_salida = incógnita del ensamblaje, con composición del donante
```

El caudal se determina junto con los balances y la restricción mecánica; no introducir un dato arbitrario de evaporación o un coeficiente k para conseguir acumulación/desacumulación. La energía transportada contiene la entalpía de la mezcla gaseosa extraída; no añadir calor latente de nuevo.

**V fija + P prescrita no es por sí sola una contradicción universal.** Puede cerrar un sistema abierto si el caudal es una incógnita adicional. La guarda actual que rechaza ese par refleja el alcance de la primera entrega, que exige todos los caudales como datos; debe generalizarse con análisis del ensamblaje y de su rango/inicialización, sin simplemente borrar la guarda.

Mantener gas/agua y restricciones al cambiar la representación numérica. Elegir ODE reducida o DAE según la formulación, con inicialización consistente. La regla de fase no sustituye este análisis.

La salida será de gas. Si hacen falta capacidades de entrada al invertir flujo, pedir estado/composición del ambiente y utilizar el donante correcto; no copiar propiedades del interior. No asignar extracción de una fase por nombre de componente.

Para una tapa con resistencia finita, movimiento o fugas pequeñas debe declararse una relación de transporte/mecánica adicional y sus parámetros. Esta prueba empieza por la frontera ideal abierta a la atmósfera, no por una ley hidráulica inventada.

## Qué falta en el motor, de forma verificable

1. Paquete agua–aire no condensable con referencias, dominio y validación propios; la existencia de un modelo genérico de mezclas no aporta sus parámetros.
2. Inicialización por presión inicial del espacio de cabeza, calculando la cantidad de aire sin sobredeterminar U/T/V/cantidades.
3. Salida de gas calculada al imponer la restricción mecánica, en vez de todos los caudales obligatorios como datos.
4. Integración del contrato nuevo en frontend y lectura de sus capacidades reales. El frontend actual usa el protocolo v1; no hay que anunciar v2 completo por existir archivos de backend en desarrollo.

## Criterios de aceptación para Claude

- Mismos datos de entrada en los dos casos, salvo la frontera material/mecánica. Sin rama del solver seleccionada por el nombre «olla».
- Publicar todas las ecuaciones y restricciones efectivas y el recuento del mismo ensamblaje. Diferenciar datos de resultados de inicialización.
- Hermético: conservar cada especie y verificar U(t)=U0+Q t; V fijo; P/T/fases calculadas. No prometer fase final concreta.
- Tapa normal: caudal calculado; conservar cada especie local/global incluyendo lo que sale; presupuesto de energía con entalpía del gas, presión ambiente compatible y volumen fijo.
- Inicialización: recuperar P0 y T0 declaradas y cantidades no negativas, usando el mismo espacio gaseoso; no ignorar la presión del aire.
- Comparaciones independientes a baja temperatura para aire/gas ideal y para agua de referencia; evolución hacia el límite con aire tendiendo a cero solo cuando los datos y el dominio permitan verificarlo. No reducir el aire de entrada a cero para pasar la prueba.
- Convergencia de paso/tolerancia, eventos de agotamiento/dominio y ausencia de fases, derivadas composicionales y controles negativos.
- No pedir al usuario un caudal de vapor que el modelo está encargado de calcular. No enseñar resultados predeterminados ni valores tomados del ejemplo anterior.
- Presentar temperatura, presión total, masas de agua líquida/vapor, cantidad de aire en el recipiente y caudal gaseoso calculado. Los gráficos salen del estado resuelto, sin filtros que fuercen mesetas o aumentos.

## Fuentes para decidir el paquete

[IAPWS, humid air in equilibrium with liquid water](https://www.iapws.org/relguide/SeaAir.pdf) y [documentación oficial de propiedades de aire húmedo de CoolProp](https://coolprop.org/fluid_properties/HumidAir.html) distinguen la mezcla aire/vapor del agua pura y las restricciones de equilibrio. Son referencias para auditar modelos y dominios; no prueban que sus operaciones estén instaladas o integradas en este proyecto ni que un evaluador de aire húmedo resuelva por sí solo una olla con líquido y dinámica.
