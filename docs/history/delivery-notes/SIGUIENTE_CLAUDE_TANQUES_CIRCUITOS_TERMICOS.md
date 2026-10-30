# Siguiente entrega: tanques y circuitos térmicos acoplados

11 de octubre de 2026. Encargo de backend para un chat nuevo de Claude. Prioridad vigente; entregar cada hito por separado, en orden A → B → C → D. No rehacer las entregas anteriores ni abordar bombas u operaciones completas.

## Punto de partida y responsabilidad

Leer `docs/ENTREGA_LABORATORIO_CODEX.md` §§21–23.7 y los contratos/tipos actuales de estudios. El recuento canónico y la referencia exacta de propiedades faltantes están entregados e integrados. No necesitan otro hito.

El usuario quiere construir sistemas conectados, introducir datos, comprobar la completitud y resolver. Las ecuaciones se ensamblan y resuelven en backend; el frontend solo configura, presenta y consulta. Un estado compartido no debe contarse dos veces. Acoplar energía no supone resolver momento si los caudales están especificados como fronteras.

Modificar backend, pruebas y documentación. Dejar el frontend y el cambio previo ajeno de `thermodynamics/proveedor.py` fuera. Sin commit ni push. Mantener resultados e identificadores de solicitudes antiguas salvo una corrección física documentada y probada. No ampliar booleans de capacidad sin auditar la combinación completa.

## Lo que hoy funciona y lo que falta

El frontend ya carga cinco solicitudes reales: llenar/vaciar con `balance_general`; entrada caliente/fría con cantidad constante y energía; dos volúmenes cerrados unidos térmicamente. Las verifica `frontend/verificar_escenarios_tanque.mjs` contra referencias independientes.

Hoy el balance general no incluye energía y los tanques abiertos con energía exigen inventario constante. Una interfaz térmica ya existe entre dos volúmenes cerrados o en la cadena material admitida, pero eso no equivale a dos circuitos de materia independientes. No hay una pared sólida como dominio térmico independiente, ni condensación de vapor. No disfrazar estas ausencias con un coeficiente de salida, un volumen ficticio o un Cp artificial.

## Modelo conceptual que debe poder representar la mesa

La cantidad de agua del tanque es un sistema material y energético. El fluido caliente dentro del serpentín es otro sistema, con sus propias entradas y salidas. La pared de la tubería puede ser un tercer sistema energético cuando interesa su almacenamiento. Si se desprecia su almacenamiento, queda como una relación térmica algebraica entre los fluidos. Elegir esa simplificación explícitamente; no crear siempre tres estados.

```
entrada de agua → tanque → salida de agua
                    ↕ calor
                  pared             (opcional, con almacenamiento propio)
                    ↕ calor
entrada caliente → fluido del serpentín → salida caliente
```

No hay mezcla de los dos circuitos. La geometría del equipo y su icono son una capa futura sobre este modelo semántico. Los primeros hitos son modelos concentrados, no CFD ni discretización espacial de la tubería.

## Hito A — cantidad variable y energía en un tanque abierto

Primer alcance: una especie (agua), mezcla perfecta, líquido incompresible ideal con propiedades manuales explícitas, caudales de entrada/salida impuestos y temperatura uniforme. Sin reacción, interfaces, expresiones arbitrarias, bomba ni problema inverso temporal. Reutilizar el ensamblaje existente y sus contratos donde físicamente sea correcto.

Antes de implementar, documentar el volumen de control y la referencia energética. Un recipiente metálico rígido puede tener un nivel de líquido variable. La capacidad geométrica del recipiente no es el volumen ocupado por el agua. Para densidad molar constante, `V_liquido = n/rho`; una capacidad máxima es un parámetro separado. No reinterpretar silenciosamente el `V` de peticiones antiguas. El nivel `V_liquido/area` solo existe si se declara un área.

Propuesta para este alcance: volumen de control que sigue la superficie del líquido, presión uniforme declarada y trabajo de desplazamiento contra ella explícito. Con `h = u + p/rho`, la formulación consistente es:

```
dn/dt = F_ent - F_sal
dU/dt = F_ent*h_ent - F_sal*h_sal + Q - p*dV_liquido/dt
U = n*u(T), V_liquido = n/rho
```

Con Cp y densidad constantes debe recuperar `n*Cp*dT/dt = F_ent*Cp*(T_ent-T) + Q`. Comprobar esta reducción, sin ejecutar la ecuación reducida en el cliente. Si se elige el volumen de control fijo de todo el recipiente en lugar de este, formular también el espacio de gas y el trabajo correspondiente; no mezclar ambas formulaciones ni contar dos veces trabajo de flujo y de frontera.

Admitir adiabático al exterior o Q declarado, con unidades. Definir y diagnosticar las especificaciones incompatibles. No deducir caudales a partir de un coeficiente ni introducir por omisión densidad, presión, Cp o temperatura. El catálogo y el recuento deben decir qué es dato, estado, parámetro o cantidad derivada.

Definir antes de escribir código la política de tanque inicialmente vacío: sin pared ni energía almacenada, su temperatura no está definida. El primer alcance puede exigir cantidad inicial positiva, con diagnóstico explícito para cero. Un vaciado debe terminar como `parcial`; no conservar agua ficticia ni dividir por un epsilon. Si se declara capacidad máxima, detener al alcanzarla o implementar un rebose explícito en otra entrega; no fabricar automáticamente un caudal de rebose. Conservar eventos de dominio térmico, incluso antes de la primera muestra.

El estacionario procede de las mismas ecuaciones con derivadas cero. `F_ent = F_sal` no determina por sí solo la cantidad de agua. Si falta una especificación que la determine, devolver indeterminación/recuento real, sin asignarle un valor.

### Referencias independientes obligatorias de A

Escribirlas en la prueba, sin importar residuos del motor:

- `n(t)=n0+(F_ent-F_sal)t`, para llenado y vaciado con ambos caudales positivos.
- Adiabático, caudales distintos: `T=T_ent+(T0-T_ent)*(n0/n)^(F_ent/(F_ent-F_sal))` mientras n>0.
- Caudales iguales: `T=T_ent+(T0-T_ent)*exp(-F_ent*t/n0)`; debe coincidir con el tanque energético actual.
- Sin entrada ni Q, vaciar mantiene T constante hasta el evento.
- Q constante y entrada positiva: sustituir T_ent por `T_ent+Q/(F_ent*Cp)` en la solución anterior.
- Tanque cerrado con Q constante: `T=T0+Q*t/(n0*Cp)`.
- Contraste con una integración independiente escrita en T, conservación integrada y cambio de referencia energética por especie. Este último no debe cambiar la trayectoria de T.
- Unidades equivalentes, trazas/tolerancias si procede, eventos tempranos, signos y peticiones anteriores sin cambios.

## Hito B — circuito de agua caliente separado del tanque

Depende de A para el tanque que se llena o vacía mientras se calienta. Empezar por agua líquida en ambos circuitos, sin ebullición. Admitir dos subgrafos materiales independientes, unidos por una interfaz térmica `Q=G*(T_caliente-T_tanque)`; no exigir una corriente intermedia que mezcle sus aguas. Los estados de ambos circuitos se evalúan juntos en el mismo instante.

La interfaz no almacena energía: aporta -Q y +Q y se cancela globalmente una vez. Cada circuito conserva sus fronteras materiales y térmicas. Adiabático significa sin calor al exterior; no elimina esta conexión interna. Mantener el significado y unidades de G existentes.

Verificar G=0 (circuitos independientes), temperaturas iguales (Q=0), orientación invertida, conservación global y ausencia de doble entalpía transportada. Para cantidades constantes, usar una exponencial de matriz de la formulación independiente en T. Para cantidad variable, integrar aparte la referencia en T con el término composicional correcto. Verificar rigidez y métodos admitidos, escalones, unidades, recuento y diagnósticos que identifiquen la conexión afectada.

## Hito C — pared sólida con almacenamiento explícito

Depende de B. Añadir un dominio térmico sólido concentrado con capacidad térmica declarada (o masa y calor específico con unidades), estado U_pared o T_pared y relación constitutiva. No simularlo como recipiente de fluido con una especie ficticia o un inventario casi cero. Masa constante de la pared es un parámetro; no requiere una ecuación material diferencial artificial.

Conectar fluido caliente ↔ pared ↔ agua del tanque mediante dos conductancias declaradas. La pared recibe y entrega calor y conserva su propia energía. No mantener en paralelo la interfaz directa anterior salvo que el usuario declare físicamente otra ruta de calor. Ampliar topología/límites solo para las combinaciones auditadas, incluyendo número de dominios térmicos y catálogo por tipo.

Validar el sistema cerrado de tres capacidades contra exponencial de matriz y su temperatura límite ponderada. Verificar signos, cancelaciones, orientaciones, dominio, rigidez, energía almacenada en la pared y el arranque consistente. Una pared sin almacenamiento debe ser una opción algebraica explícita y recuperar la conductancia en serie `1/G_eq=1/G1+1/G2`; no introducir C=0 en una ODE singular y esperar que el integrador la resuelva.

## Hito D — vapor y condensación, primero viabilidad física

Depende de B/C según la representación de pared elegida. Auditar primero propiedades disponibles y una referencia independiente. El proveedor líquido actual no demuestra disponibilidad de saturación y entalpías de ambas fases. No sustituir condensación por agua caliente, un Cp grande o una fuente Q sin balance material del lado vapor.

Definir un primer régimen concreto y sus grados de libertad antes de implementar: por ejemplo, lado de vapor saturado cuasiestacionario a presión declarada, con entrada de vapor y salida de condensado y almacenamiento despreciado explícitamente. Ese régimen no debe anunciarse como volumen bifásico transitorio general. No imponer independientemente calor transferido y tasa de condensación cuando una determina la otra. No condensar más vapor del disponible.

Si se pretende un dominio bifásico dinámico, definir estados, presión, volumen, masa, calidad, cierres y restricciones consistentes; no tratarlos a todos como especificaciones independientes. Declarar eventos al abandonar el régimen validado. Referencias de h líquida/vapor y calor latente deben ser compatibles entre almacenamiento, corrientes y frontera.

Una fuente primaria posible para agua/vapor es [IAPWS-IF97](https://iapws.org/technical-guidance/release/IF97-Rev), que define propiedades y equilibrio de fases dentro de su dominio. Esto es una referencia a evaluar, no autorización para inventar capacidades de la biblioteca actual. Si no hay propiedades ni referencia suficientes, entregar el diagnóstico de viabilidad y qué falta; mantener D deshabilitado.

## Contrato transversal y aceptación por hito

1. Proponer el esquema exacto antes de implementar; preservar nombres semánticos y unidades. El cliente no convierte n en U, no calcula caudales y no selecciona un solver físicamente distinto.
2. `catalogo_variables` y `recuento` salen del mismo ensamblaje que se resuelve; `/validar` no integra ni busca raíces. Pendientes/conflictos identifican variable, ruta y piezas/conexiones; propiedades también. `/resolver` devuelve el mismo recuento.
3. Mostrar balances construidos desde `terminos[]`, comprobar `residuo_terminos`, y registrar cancelaciones internas. No editar a mano el LaTeX global. No deducir intercambios brutos de tasas netas.
4. Capacidades por combinación real: estados, algebraicas, restricciones, especificaciones, iniciales, dominio, métodos, eventos, límites y transferencias. Una combinación no verificada sigue rechazada con motivo. La ampliación no habilita otras topologías por coincidencia de flags.
5. Transferencia estacionario→temporal solo cuando exista estacionario determinado y se haya verificado la misma física. Mantener objeto firmado, huellas, vigencia, restricciones e ida y vuelta JSON por Node. Un estacionario indeterminado no se transfiere.
6. Publicar ejemplos generados desde endpoints: llenado/vaciado térmico; circuito independiente; pared; vapor, según el hito efectivamente terminado. Compararlos con referencias externas al ensamblaje y ejecutar regresión completa. Documentar método, tolerancias, eventos, resultados y limitaciones.
7. Añadir la siguiente sección de `docs/ENTREGA_LABORATORIO_CODEX.md` con migración y campos exactos para frontend. Informar cada hito entregado y los restantes. Mantener las otras colas históricas (momento, overrides por propiedad, LaTeX expandido, etc.) sin mezclarlas con este encargo.

## Experiencia de usuario que esta física debe permitir

Diagrama define sistemas, componentes y conexiones. Ecuaciones muestra el mismo modelo y permite localizar sus variables. Experimentar asigna datos y deja un indicador compacto de completitud más Resolver. Resultados permite comparar cantidades y temperaturas. Métodos, restricciones y procedencia detallada quedan en Detalles técnicos. Un preset declara sus valores de ejemplo, no los convierte en valores por omisión de cualquier modelo nuevo.
