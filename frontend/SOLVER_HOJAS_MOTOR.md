# Hojas de ecuaciones y solver independiente

Entrega: 13 de octubre de 2026. Alcance exclusivo de `/motor`. El laboratorio, su backend, sus datos y sus simulaciones no se modifican. No hay commit ni push.

Actualización de energía, 14 de octubre: el alcance material descrito aquí se conserva. El primer ensamblaje temporal de materia y energía de un volumen y una especie, su derivación, relación manual u(T), eventos y evidencia están en [FUNDAMENTO_ENERGIA_MOTOR.md](FUNDAMENTO_ENERGIA_MOTOR.md). Los límites históricos de energía indicados más abajo corresponden a la entrega material inicial.

## Uso y pantallas

1. `/motor/hojas`: crear una hoja con nombre, abrir, duplicar, archivar y restaurar. No se cargan escenarios ni propiedades físicas por omisión.
2. `/motor/hojas/[id]`: derivación propia. Cada operación añade una ecuación a la hoja. Guardado automático de los pasos y supuestos; nombre editable. El borrador `/motor` se puede guardar como una hoja independiente.
3. `/motor/hojas/[id]/resolver`: ecuación final, campos por dominio y componente, valores o expresiones con unidad, iniciales, horizonte y botón Resolver. Un contador muestra variables/ecuaciones, GL estructural, datos definidos e iniciales definidas. Método, malla, muestras y tolerancias quedan en Opciones avanzadas.
4. `/motor/hojas/[id]/resultados`: tablero, tabla y detalles técnicos separados. Gráficos de variables elegidas en X y Y, varias curvas y unidades, disposición vertical o en paralelo, arrastre para reordenar, ancho y altura ajustables. En 1D hay perfiles con selector temporal y evolución por celda. CSV con todos los tiempos/celdas.

Los botones de arrastre y altura también admiten flechas del teclado. El tablero vacío tras retirar sus gráficos permanece vacío; no se reconstruye por omisión. Ajustar ejes para una señal casi constante evita amplificar ruido numérico; jamás redondea ni modifica la serie.

## Qué ecuaciones se ejecutan

Se usa la formulación estructurada del último paso, no se interpreta su LaTeX. Los términos totales del compilador son los mismos `terminosTotalesMateria` que utiliza el renderizador: rol, signo, especie, puerto y forma de fuente. Las expresiones de dato se analizan con un AST limitado; no se usa `eval`, `Function` ni ejecución de código del usuario en la aplicación.

- **Total temporal:** dmᵢ/dt = entradas − salidas − Φᵢ,resto + Gᵢ − Cᵢ. Un puerto desconocido no equivale a cero. El complemento conserva su signo exterior. Las fuentes agregadas son kg/s; una tasa declarada uniforme en espacio se multiplica por el volumen declarado. No se usa V=1 implícito.
- **Temporal local:** con invariancia en las tres direcciones cartesianas se integra dρᵢ/dt = γᵢ − χᵢ, en kg/m³. No se cambia densidad por masa ni se inventa un volumen.
- **Relación m=ρ̄V:** si el dominio no es fijo ni la densidad es constante, el usuario elige dar ρ̄(t) o V(t); la otra función se obtiene de la masa integrada. Con volumen fijo se da V y se obtiene ρ̄. Estas funciones no pasan a ser incógnitas sin una ecuación adicional.
- **Ecuación volumétrica final:** si la derivación llega a dV/dt = Q_ent − Q_sal, se integra V, con V inicial y Q en unidades volumétricas. No se pide una densidad cancelada ni se publica una masa sin ella. Si existen fuentes o flujo restante divididos por densidad, esa propiedad sí es obligatoria. La extensión V(0)=0 solo se admite para la ley de flujos sin fuentes de dominio ni intercambio restante; no afirma que la densidad media de un dominio vacío esté definida.
- **1D temporal:** conservación local cartesiana con una dirección activa (x, y o z), invariancia en las otras dos y frontera fija. Convección, flujo difusivo general o Fick, generación y consumo se discretizan en un solo vector de estado de todas las especies y celdas. Las cantidades integradas se expresan por unidad de área (kg/m²), sin inventar sección transversal.

De 1 a 8 especies declaradas en un dominio. Los nombres no aportan propiedades termodinámicas ni masas molares. Una especie completa tiene difusión relativa cero. Para varias especies, la velocidad es media en masa y se exige Σjᵢ=0. Los coeficientes arbitrarios que contradicen esa identidad se rechazan. La forma laplaciana exige densidad total espacialmente uniforme, difusividad espacialmente uniforme y fuentes/velocidad compatibles.

Para evitar perder derivadas de una especie en trazas al restar fracciones próximas a uno, se diferencia la identidad Σwᵢ=1 (o Σρᵢ uniforme): se conservan las derivadas de las especies menores y se elimina la de la especie dominante. No se proyecta ni corrige una masa calculada. Las pruebas invierten el orden de los componentes y contrastan el modo analítico en trazas.

En el total, restricciones locales del campo o estacionariedad local necesitan compatibilidad adicional con los flujos agregados; esta entrega las bloquea antes de integrar. No se ignoran para hacer funcionar un resultado.

## Datos, unidades y completitud

Todos los valores físicos empiezan vacíos. Se requiere un cero explícito para declarar una contribución nula. Los datos constantes marcados en la derivación no aceptan una expresión dependiente de t o del estado. Cada campo admite solo sus dependencias disponibles.

La unidad del campo se convierte a SI. El horizonte acepta s/min/h, las masas kg/g, flujos kg/s o kg/h y otras unidades publicadas en `unidadesMotor.ts`; caudales volumétricos m³/s, L/s, L/min o m³/h. No se convierte masa a moles ni se utiliza thermo.

En expresiones libres, t está en segundos, la coordenada activa en metros, m en kg, rho en kg/m³ y V en m³. La unidad seleccionada se aplica al resultado de la expresión. Por ejemplo, `2*m_A` dado en kg/s representa un coeficiente numérico de 2 s⁻¹. Alias `m_A`, `m_B`, `rho_A`, `rho_B`, `m_total` y `rho_total` permiten acoplar especies; solo están disponibles si se conocen las cantidades necesarias. γ y χ son tasas brutas no negativas; los caudales orientados pueden invertir su sentido con un valor negativo. El usuario es responsable de formular las tasas compatibles con la conservación de su reacción: no se fabrica estequiometría a partir de dos fuentes genéricas.

Se aceptan +, −, *, /, ^, paréntesis, sin, cos, exp, log, sqrt, abs, min, max y step. No existe aún comprobación dimensional interna de constantes y operaciones de una expresión libre. Tampoco se localizan automáticamente todas sus discontinuidades: pulsos o escalones requieren resolución temporal suficiente y un contraste al refinar muestras/tolerancias; no se certifica que una función arbitraria submuestreada se haya capturado.

**GL estructural** cuenta funciones/parámetros requeridos que faltan o son inválidos. Las iniciales y el horizonte se verifican por separado. Las funciones de frontera espacial quedan pendientes hasta elegir su tipo. No es un rango numérico ni una prueba general de independencia para PDE, DAE o sistemas algebraicos. Un formulario completo se compila y se evalúa inicialmente antes de habilitar Resolver; una incompatibilidad se muestra sin ejecutar.

## Métodos y límites numéricos

- ODE: Dormand–Prince RK45 5/4 adaptativo, o Euler implícito adaptativo por comparación de un paso con dos medios pasos.
- Euler implícito: Newton con Jacobiano completo por diferencias finitas, escalado por variable y eliminación con pivoteo. Así se conservan dependencias cruzadas entre especies. La convergencia del residuo se escala con magnitudes físicas y tolerancias, sin un piso arbitrario de 1 kg que oculte trazas.
- PDE 1D: volúmenes finitos conservativos, convección upwind de primer orden y difusión centrada; integración RK45 del sistema semidiscreto. Paso limitado por velocidad y difusión (0.4 Δx/max|v| y 0.2 Δx²/max D), además del error temporal.
- Fronteras: periódicas, valores de reservorio (convección de entrada y difusión; salida upwind), o sin flujo. Datos que contradigan una frontera impermeable se rechazan. Los flujos compartidos entre celdas se cancelan con signos opuestos.

Las tolerancias controlan **error local temporal**, no aseguran el mismo error global ni el error espacial. Euler implícito conserva su orden uno; requiere más pasos para precisión fina. La difusión numérica del upwind se reduce al refinar la malla. No se implementaron BDF/Radau, una discretización implícita espacial, AMR ni un solver tensorial.

Las cantidades y densidades no se recortan a cero para continuar. Un cruce negativo detiene la trayectoria en un estado no negativo por acotación del paso y devuelve `parcial`. Un estado inicialmente vacío con extracción detiene en t=0. Una expresión fuera de su dominio, falta de convergencia o límite de pasos también produce un diagnóstico y evita afirmar que se llegó al horizonte. Máximo 150000 pasos/intentos, 160 celdas, 201 muestras; los límites se pueden revisar en futuras entregas. El integrador cede el hilo también durante intentos rechazados y admite cancelación.

El cierre publicado es cambio de cantidad menos el presupuesto de frontera/fuentes integrado por el mismo método. En 1D el presupuesto se calcula con los flujos extremos y fuentes antes de sumar los estados, para comprobar la cancelación interior. Es una verificación del problema discretizado, no una certificación de cualquier modelo físico del usuario.

No se ejecutan todavía ecuaciones sin derivada temporal, estados estacionarios, problemas inversos, forma integral sin discretización/reducción, 2D/3D, coordenadas curvilíneas, mallas móviles, energía, momento o varios dominios. Se informa el motivo en Resolver. No se transforma una ecuación algebraica en una ODE ni se descartan dimensiones en silencio.

## Persistencia e identidad

Hojas/configuraciones/tableros: localStorage `rage.motor.hojas.v1`. Perfiles numéricos: IndexedDB `rage-motor-resultados`, clave compuesta [hoja, firma]. La firma incorpora formulación, datos numéricos y versión del solver (`motor-independiente-materia-1`); es vigencia local, no autenticación.

Editar ecuaciones, volver a un paso o cambiar datos invalida resultados. Al cambiar la formulación se retiran campos numéricos que desaparecen o cambian de magnitud, evitando reutilizar kg/s como L/s o datos de un puerto retirado. Duplicar conserva pasos/datos/tablero, pero obliga a calcular de nuevo. Si una edición cambia la variable de estado entre masa, densidad o volumen, o pasa entre un campo y una ODE, el tablero se reinicia para esa nueva representación; no se conservan gráficos de una variable que dejó de resolverse. Los resultados solo se publican si la firma sigue vigente antes y después del guardado asíncrono; no sobrescriben un cálculo de otra formulación concurrente. Las hojas corruptas no se sustituyen por una biblioteca vacía en silencio. El guardado es local al navegador, sin sincronización en servidor ni exportación/importación de hojas todavía.

## Verificación

`npm run test:motor-fundamental` incluye las pruebas de operadores, derivación y auditoría de un dominio, más `verificar_solver_motor.mjs` con **335 comprobaciones nuevas**:

- solución lineal temporal, unidades equivalentes bit a bit, balance de presupuesto y vaciado/evento inicial;
- ecuación volumétrica directa y selección ρ(t)/V(t), sin fabricar propiedades;
- cinética rígida por ambos métodos y conversión A→B acoplada contra la analítica;
- masa de 1e-20 kg en una ley no lineal implícita, para verificar escalado;
- advección periódica contra la traslación analítica y refinamiento 20/40/80 celdas (errores medios 0.04168 / 0.02215 / 0.01142);
- difusión frente al modo propio semidiscreto, mezcla con trazas, orden de componentes y rechazo de coeficientes incompatibles;
- fuentes locales acopladas en 1D, presupuesto de frontera sin flujo y rechazo de velocidad incompatible;
- dimensiones/hipótesis no admitidas, expresiones seguras, unidades incompatibles y desbordamiento numérico;
- catálogo de gráficos con los mismos alias, masa no inventada, ejes sin modificación de datos, independencia de hojas, duplicación y archivado recuperable.

Además: TypeScript y ESLint del apartado. QA en navegador: flujo hoja→solver→resultados, 100 kg + (10800 kg/h − 2 kg/s) durante 10 min = 700 kg; hoja 1D periódica; duplicación y cambio a dV/dt=Q₁−Q₂ con 100 L y 3−2 L/s, que da 0.7 m³ a 10 min sin pedir densidad; recarga con resultados de IndexedDB; selección de ejes, reordenación por arrastre y teclado, altura y tiempo del perfil persistentes. Las hojas de QA se archivan recuperablemente al terminar y no son presets del motor.

## Archivos y continuidad

Compilación: `modeloNumerico.ts`, `expresionesMotor.ts`, `unidadesMotor.ts`. Métodos: `integracionMotor.ts`. Documentos/resultados: `hojasMotor.ts`, `resultadosMotor.ts`, `useHojasMotor.ts`. UI: `BibliotecaHojas`, `BarraHojaMotor`, `HojaGuardada`, `ResolverHoja`, `ResultadosHoja`, `TableroMotor` y `datosGraficasMotor`; rutas separadas y CSS local. No hay dependencia ni llamada a APIs del laboratorio.

El siguiente trabajo matemático sigue siendo completar energía y momento en este mismo apartado y ampliar expresiones/transformaciones con dimensiones y condiciones de validez. La comparación con el laboratorio deberá hacerse después con referencias independientes, sin confundir este compilador acotado con un ensamblador multifísico universal.

Referencias de métodos (no bibliotecas invocadas): [SciPy, RK45 y selección de métodos de integración](https://docs.scipy.org/doc/scipy/reference/generated/scipy.integrate.solve_ivp.html) y [Clawpack, advección conservativa 1D](https://www.clawpack.org/gallery/pyclaw/gallery/advection_1d.html). La implementación numérica de esta entrega es propia en TypeScript.

## Hojas preparadas para comprobación manual

Por petición posterior del usuario se añadieron ocho hojas editables y completas, sin modificar el solver ni crear casos especiales en él. Consulte [HOJAS_PRUEBA_MATERIA.md](HOJAS_PRUEBA_MATERIA.md) para datos, referencias, límites y resultados. Se añaden explícitamente desde la biblioteca; no se cargan escenarios por omisión en una hoja nueva.

## Ampliación: ensamblaje de varios volúmenes

La referencia ya admite redes de balances temporales de masa, con corrientes compartidas, fuentes y leyes declaradas. Las menciones anteriores a varios dominios como pendientes describen el alcance inicial. No se acoplan todavía campos espaciales o estados volumétricos dentro de la red. Consulte [ACOPLAMIENTO_MATERIA_MOTOR.md](ACOPLAMIENTO_MATERIA_MOTOR.md) para contrato, ejemplos, pruebas y límites. No se ha comparado ni modificado el backend.
