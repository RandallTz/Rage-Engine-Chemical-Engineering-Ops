# Energía: fundamento y primer ensamblaje

Alcance: referencia independiente `/motor`. No se modifica el laboratorio ni el backend.

## Convenciones

La ecuación local conserva energía interna más cinética: e = u + |v|²/2. El trabajo de fuerzas de volumen se conserva explícito; la energía potencial no se añade simultáneamente, evitando contar gravedad dos veces. El flujo q es energético no convectivo; el primer solver monocomponente no implementa difusión energética de mezclas.

Cada transformación se registra como una operación matemática del usuario: integrar la ecuación local y aplicar Gauss; aplicar Reynolds para una frontera móvil; descomponer sigma = -p I + tau; agrupar u + p/rho en h; particionar la frontera en puertos y superficie restante. No se pasa directamente de una PDE a un tanque.

Para la frontera móvil:

dE/dt = -integral_superficie rho e (v-v_b).n - integral_superficie q.n + integral_superficie (sigma.v).n + integral_volumen rho b.v + integral_volumen r_v.

Al agrupar trabajo de flujo:

dE/dt = suma_entradas mdot (h+ec) - suma_salidas mdot (h+ec) - Phi_resto + Q - W_b + W_tau + W_bvol + R.

W_b = integral_superficie p v_b.n. Con presión uniforme W_b = p dV/dt. Q es positivo hacia el volumen; trabajo de presión es positivo hacia fuera y lleva signo menos. W_tau y W_bvol son potencias hacia el sistema. Una frontera adiabática anula Q total, no impone q=0 en todo el interior.

## Primer contrato ejecutable

Un volumen, una especie, conservación macroscópica temporal, sin fuentes materiales, sin transporte material sin declarar por el resto de la frontera. Acumulación activa, energía cinética despreciable, temperatura y energía específica uniformes, monofásico sin cambio de fase declarados por el usuario. El trabajo viscoso, el trabajo de fuerzas de volumen y el aporte volumétrico pueden retirarse por hipótesis o declararse como potencias integradas. No se deducen campos de esfuerzo ni fuerzas a partir de estas potencias. Estas elecciones no certifican termodinámicamente la fase.

Relación de energía explícita u(T) = u_ref + c_u (T-T_ref), con c_u positivo, unidades, referencia y dominio térmico declarado. U=m u(T). T se obtiene de esta relación; no se sustituye dU/dt por una capacidad fija cuando cambia m.

En un volumen abierto, la densidad de mezcla constante y la presión espacialmente uniforme se deben declarar. h=u+p/rho; V=m/rho; W_b=p dm/dt/rho para una frontera móvil. Una frontera fija con este modelo requiere dm/dt=0 en cada evaluación, nunca se fuerza caudal de salida para conseguirlo. Se conservan los términos completos de transporte y trabajo de frontera. Se puede agrupar u+p/rho en h o mantener transporte interno y trabajo de flujo separados: ambas representaciones usan sus propios términos estructurados, sin contar dos veces el trabajo de flujo.

Cada corriente material se evalúa con el mismo caudal SI que el balance de masa. El compilador material conserva una evaluación común de tasas para el mismo tiempo y estado; energía consume esos valores. El fluido que sale usa T del volumen por la hipótesis uniforme. La entrada usa una T exterior declarada. Un caudal que puede invertir el sentido requiere T exterior también en la frontera nominal de salida; nunca se inventa T de retorno. Una salida de signo constante no requiere temperatura exterior. Se admite la especificación material por componente o total más composición; en este hito hay una sola especie.

Energía sola se admite en un volumen cerrado con masa constante como dato. Materia y energía activas comparten un vector [m,U]. U admite valores negativos por su referencia y tiene tolerancia en J independiente de la de masa. No hay flash ni proveedor, equilibrio de fases, energía multicomponente, varios volúmenes con energía, conducción 1D energética o solver estacionario en este hito.

## Evidencia y responsabilidades

Los términos estructurados del balance total se usan para renderizar y para evaluar el residuo. La relación u(T) evalúa estado, no cambia masas ni caudales. El coordinador obtiene los mismos flujos del compilador material; el integrador conserva presupuestos de masa y energía por separado. Se publican series con su unidad y trazabilidad de términos, datos usados, datos inactivos y fase asumida sin verificación. U es una variable energética con unidad J; nunca un componente químico ficticio.

El recuento estructural incluye estados diferenciales y relaciones algebraicas de T, V (cuando se declara densidad constante) y h de las corrientes. Estas últimas se eliminan explícitamente al evaluar el sistema; no exigen otro integrador ni se cuentan como datos faltantes. Las condiciones iniciales se comprueban por separado. El recuento no certifica un rango numérico general. El usuario elige T(0) o U(0); la alternativa conservada en el banco de datos queda inactiva. Masa inicial positiva y temperatura inicial dentro del dominio se comprueban antes de resolver.

Unidades: temperaturas absolutas K/°C/°F con desplazamiento; J/kJ, J/kg o kJ/kg, J/(kg K) o kJ/(kg K), W/kW y Pa/kPa/bar. Las expresiones energéticas reciben t [s], m [kg], U [J], T [K] y, cuando están disponibles, V [m³] y rho [kg/m³]. La unidad elegida convierte el resultado. Se admite calor o potencia como función del estado; no hay certificación dimensional de los coeficientes internos de expresiones libres. Las expresiones de caudal conservan las dependencias materiales actuales: no aceptan todavía retroalimentación de T.

Los límites térmicos se vigilan mediante eventos tanto con RK45 como con Euler implícito. Un cruce detiene la trayectoria en el último estado válido y publica resultado parcial; un estado inicial fuera del dominio se rechaza. La ley u(T) puede evaluarse en etapas de prueba externas al dominio para localizar el evento, sin publicar esas etapas como estados válidos. Un volumen inicialmente vacío no tiene T definida desde U/m. El vaciado completo es singular para esta representación; no se continúa como si hubiese fluido ni se certifica un régimen posterior al agotamiento.

La biblioteca ofrece seis documentos editables mediante «Añadir pruebas · materia + energía»: calentamiento cerrado, enfriamiento con Q(T), entrada caliente a cantidad constante, llenado con calor, vaciado con entrada fría y llenado con entrada caliente sin calor externo. Son datos e hipótesis de prueba, no ramas especiales del compilador. Todas las hojas empiezan desde la ecuación local; la selección de forma total conserva los pasos intermedios de Gauss y Reynolds. Deshacer retira físicamente los pasos y Rehacer los recupera. Un cambio de topología necesita actualizar explícitamente el contexto de la derivación energética antes de ejecutar.

El sexto documento (`motor-prueba-energia-v1-6`) empieza con 100 kg a 293.15 K, recibe 2 kg/s a 333.15 K y descarga 1 kg/s. A los 100 s tiene 200 kg, 323.15 K y 0.2 m³. Su referencia es m(t)=100+t y T(t)=333.15−40[100/(100+t)]²; utiliza la misma relación manual c_u=4000 J/(kg K), rho=1000 kg/m³ y p=100000 Pa que los otros fluidos de prueba. Las gráficas iniciales de este documento muestran masa y temperatura en paralelo. Añadirlo conserva los documentos existentes, incluso si el usuario los modificó.

La pantalla Resolver presenta ahora las ecuaciones finales en una sección propia, con rótulos de materia/energía, acentos de cada familia y una relación de estado de menor jerarquía visual. Los símbolos permanecen neutros y las ecuaciones se mantienen horizontales hasta que su longitud exige envolver términos. Es una modificación de presentación: se conserva el LaTeX generado a partir de las mismas formulaciones estructuradas.

## Verificación de esta entrega

- `npm run test:motor-fundamental`: pasan todas las suites de materia y la suite energética. Los casos anteriores de materia mantienen sus resultados.
- `verificar_energia_motor.mjs`: incluye renderizado simbólico, persistencia y validación; el número de comprobaciones no representa experimentos físicos independientes.
- Seis referencias analíticas de m(t)/T(t), RK45 y Euler implícito. Con rtol=1e-9, error máximo de temperatura de RK45 ≤3.4e-11 K y de Euler implícito ≤2.1e-4 K; el segundo método conserva su orden uno.
- Referencia no lineal independiente escrita en T e integrada con RK4; regla del producto, conservación, cambios de referencia energética, U negativa, presión y unidades equivalentes.
- Equivalencia entre transporte mediante h y mediante u más trabajo de flujo; inversión de orientación con estado del donante correcto; adaptadores de corrientes sin duplicación de temperatura; rechazo de presión incompatible.
- Eventos térmicos, incluida salida de régimen en t=0, referencias independientes de Gauss/Reynolds, selección de balances y conservación del catálogo químico.
- TypeScript y ESLint pasan.

La navegación inicial, la ecuación local y la incorporación de los cinco documentos se comprobaron en el navegador. La revisión automática bloqueó después las acciones del navegador por límite de uso de la herramienta; queda pendiente la verificación visual final del recorrido completo de una hoja energética y sus resultados. La resolución de los cinco casos sí se verificó por código.

Referencias físicas: [MIT, Control volume form of the conservation laws](https://web.mit.edu/16.unified/www/FALL/thermodynamics/notes/node19.html), para la primera ley, trabajo de flujo y entalpía; [COMSOL, Conservation of Energy](https://www.comsol.com/multiphysics/heat-transfer-conservation-of-energy), para la ecuación local y los términos de esfuerzos y flujo energético.
