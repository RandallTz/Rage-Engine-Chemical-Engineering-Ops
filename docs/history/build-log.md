> **Este archivo es la BITÁCORA**: qué se construyó, en qué orden, qué se
> rompió y cómo se arregló. Es un registro histórico, se lee de arriba abajo.
>
> Para **la matemática** — qué ecuaciones se resuelven, con qué método, bajo
> qué suposiciones y hasta dónde son válidas — ve a **[`docs/`](../README.md)**.

---

# Fase 1: El Núcleo Termodinámico y Físico (Fundación Universal)

Esta es la base de datos viva. Cualquier motor que construyamos (académico, topológico o MESH) hace sus llamadas aquí.

### ✅ Gestión Dimensional Segura (Completado)
- Librería `pint` instanciada en `config/settings.py` y restringida a la clase `SimuladorColumnaReactiva`.
- El núcleo opera en SI puro (`float`/`NumPy`) a máxima velocidad.

### ✅ Generación Predictiva de Propiedades (Completado)
- `ProveedorTermodinamico` enrutado a `thermo`.
- Extrae $P^{sat}(T)$, $C_p(T)$ y $\Delta H_{vap}(T)$ vectorizados.
- Cálculo de coeficientes de actividad $\boldsymbol{\gamma}$ a través de UNIFAC sin depender de datos experimentales binarios.

### ✅ Equilibrio Líquido-Vapor (ELV) (Completado)
- Clase `CalculadoraELV` encapsulada.
- Búsqueda de raíces para Burbuja-T y cálculo directo para Burbuja-P confirmados y validados contra el azeótropo agua/etanol.

### ✅ Termodinámica de la Reacción (Completado)
- **Extracción de Energías Estándar**: `ProveedorTermodinamico.entalpias_formacion_liquido()` / `.energias_gibbs_formacion_liquido()`, vía los atributos `Hfm`/`Gfm` de `thermo` (corregido de `Hfl`/`Gfl`, que no existen en la version instalada — verificado contra valores de libro: agua liquida `Hfm=-285825 J/mol`).
- **Calculadora de Equilibrio Químico**: `GestorReaccion.K_eq(T)` — van't Hoff con $\Delta H_{rxn}^\circ$ constante; $\Delta H_{rxn}^\circ$ y $\Delta G_{rxn}^\circ$ se precalculan una vez en el constructor como producto punto $\boldsymbol{\nu}\cdot\Delta\mathbf{H}_f^\circ$ / $\boldsymbol{\nu}\cdot\Delta\mathbf{G}_f^\circ$.
- **Gestor Cinético Vectorizado**: `GestorReaccion.velocidad_reaccion(T, x)` — actividades $a_i=x_i\gamma_i$, productorias directa/inversa resueltas con máscaras booleanas sobre $\boldsymbol{\nu}$ (`nu<0`/`nu>0`) y `np.prod`/`np.power`, sin bucles `for`.
- Validado con el sistema real de síntesis de MTBE (isobutileno + metanol ⇌ MTBE): $\Delta H_{rxn}=-57.6$ kJ/mol, $K_{eq}(298K)=72.3$, $K_{eq}(350K)=2.31$ (decrece con T, consistente con una reacción exotérmica — van't Hoff se comporta como debe).

---

# Fase 2: Motor Topológico (Análisis de Factibilidad)

Evalúa las fronteras de separación y la existencia de azeótropos antes de dimensionar equipos.

### ✅ Topología Física / No Reactiva (Completado)
- `ThermodynamicEngine` adaptado para mapear Curvas Residuales (RCM) en mallas ternarias/cuaternarias usando la Ley de Raoult Modificada con los alfas dinámicos de UNIFAC.

### ✅ Topología Reactiva (Parcialmente Completado)
- **Variables de Barbosa-Doherty**: `core/transformaciones.py`, clase `EspacioReactivo` (`transformar`/`inversa`). Nota: la fórmula dictada tenía el denominador incompleto ($1-\nu_{tot}x_k$ en vez de $1-(\nu_{tot}/\nu_k)x_k$); con la corrección, $\sum X_i$ (excluyendo el componente de referencia $k$) da exactamente 1 para cualquier $x,\nu,k$ — verificado, y es la propiedad que hace útil a la transformación.
- **Mapas de Curvas Residuales Reactivas (RRCM)**: `ThermodynamicEngine.generar_curva_residual_equilibrio` integra en el espacio transformado $X$ con `solve_ivp`, resolviendo la fracción real $x_k$ por equilibrio químico completo ($K_{eq}(T)=\prod a_i^{\nu_i}$) en cada paso (root anidado + punto de burbuja).
- **Extra no planeado — control cinético**: además del límite de equilibrio instantáneo, se agregó una vía completa de control CINÉTICO: el salto discreto (`calculate_chemical_jump`) ahora es un paso de Euler con número de Damköhler ($x_{sig}=x_{cond}+Da\cdot\nu\cdot r$), y `generar_curva_residual_cinetica` integra la misma dinámica en el espacio real $x$ (sin transformar). $Da\to0$ recupera el límite no reactivo; $Da$ grande se acerca al equilibrio instantáneo.
- **Robustez de frontera**: los tres mapeos (discreto, continuo cinético, continuo de equilibrio) compartían el mismo riesgo — una composición inválida rompe las llamadas a `thermo`/UNIFAC a mitad de una integración/iteración. Se resolvió con eventos terminales de `solve_ivp` (más una función de derivada tolerante a evaluaciones de prueba fuera de dominio) en los dos métodos continuos, y una guarda equivalente en el bucle discreto. Verificado forzando los tres casos de falla originales antes de considerarlo cerrado.
- El diagrama ternario (`plot_ternary`) dibuja su curva de equilibrio con $K_{eq}(T)$ real de `GestorReaccion`, no con una constante estática — queda consistente con las trayectorias, que ya usaban la reacción real.
- ✅ **Nodos Azeotrópicos Reactivos**: `core/analisis_nodos.py`, clase `BuscadorAzeotropos` (`scipy.optimize.root`, método `'hybr'`), con dos métodos:
  - `encontrar_azeotropo_cinetico(x_guess, Da)`: resuelve $R(x)=(x-y^*)+Da\cdot r\cdot(\nu-\nu_{tot}x)=0$ eliminando el último componente (dependiente por $\sum x_i=1$). Converge de forma robusta desde 4 puntos de partida y valores de $Da$ distintos (5, 50, 500) al **mismo** azeótropo cinético: $x\approx[0,\,0.31,\,0.69]$, $T\approx324.8K$, residual $<10^{-12}$. Es un azeótropo de frontera: el isobutileno (reactivo limitante) se agota ($x_1\to0$), la reacción se apaga ($r\to0$) y el sistema colapsa al azeótropo físico metanol–MTBE subyacente (confirmado por separado escaneando $P_{burbuja}$ en ese borde binario).
  - `encontrar_azeotropo_equilibrio(X_guess, P_sistema)`: resuelve en el espacio transformado $X$. **Hallazgo de diseño real**: $X$ tiene $n-2$ grados de libertad, no $n-1$ — además de $X_k\equiv0$, se cumple $\sum X_i$ (excluyendo $k$) $=1$ siempre; un root-finder que solo elimina $X_k$ deja una dimensión de más y el solver vaga hacia $X$ que ni siquiera reconstruyen una $x$ que sume 1 (se reprodujo y corrigió). Corregido, el método converge honestamente (se blindó el reporte de convergencia: `scipy` puede marcar `success=True` con residual grande, así que ahora también se exige `residual_max` chico) pero **no encuentra raíz en este sistema**: se escaneó el residuo en todo el segmento transformado (1D, correcto para un sistema ternario con una reacción) y nunca cambia de signo — no existe un azeótropo de equilibrio químico interior para este $K_{eq}(T)$/estequiometría. Consistente con lo anterior: la condición de equilibrio químico completo diverge exactamente donde el reactivo limitante se agota, que es justo donde sí vive el azeótropo cinético.

---

# Fase 3: Motores Académicos y de Atajo (Diseño Simplificado)

Módulos rápidos para estimaciones iniciales y fines educativos. No aplican reacción química, solo separación física.

### ✅ Método de McCabe-Thiele (Completado)
- `core/mccabe_thiele.py` — planteado como **Orientado a Ecuaciones (EO)**, no como script secuencial: `EvaluadorMcCabeThiele.calcular_escalones(z_F,q,x_D,x_B,R) -> N` es el modelo hacia adelante, y `SolucionadorMcCabeThiele.resolver(**kwargs)` decide automáticamente si evalúa directo (todas las variables dadas) o resuelve por `root_scalar` (una variable en `None`, dado `N` objetivo) — modo "rating" vs "design spec", igual que un simulador comercial.
- **Precisión sobre grados de libertad** (encontrada al revisar el planteamiento, antes de programar): `calcular_escalones` es **una sola ecuación** relacionando 6 variables — solo se puede resolver **una** incógnita a la vez con cero grados de libertad. Pedir dos incógnitas simultáneas (p.ej. R y x_B fijando solo N) es subdeterminado con este evaluador solo; necesitaría una ecuación adicional (balance de masa global $F z_F = D x_D + B x_B$), no implementada todavía. `resolver()` lo detecta y lanza un error explicativo en vez de intentarlo silenciosamente.
- Curva de equilibrio $y$-$x$: se precalcula UNA vez vía `CalculadoraELV.burbuja_T` (barrido de composición) y se interpola con spline monótono (`PchipInterpolator`) — evita pagar UNIFAC + root-finding anidado en cada evaluación del escalonamiento o de la búsqueda de grados de libertad.
- Bug real encontrado y corregido antes de dar por buena la primera prueba: el escalonamiento confundía la coordenada X con la Y del punto operativo entre etapas (`y_actual = x_actual` solo es correcto en la primera etapa, donde coinciden por estar sobre la diagonal); con `y_actual` rastreado por separado, `N` decrece monótonamente al alejarse de $R_{min}$ y diverge al acercarse — comportamiento de libro de texto, verificado con benceno/tolueno.
- Validado: `R_min` y conteo de etapas fraccionario correctos; resolver $R$ dado $N=10$ converge y el chequeo directo con ese $R$ reproduce $N=10$ exacto; casos sobre-especificados (consistente/inconsistente) y subdeterminado manejados explícitamente; $q\neq1$ (alimentación parcial o subenfriada) mueve $R_{min}$ en la dirección física correcta.
- Bug real encontrado y corregido en `graficar_diagrama`: la ROL se dibujaba de $(x_D,x_D)$ a $(x_{int},x_{int})$ en vez de $(x_{int},y_{int})$ — el segundo punto caía exactamente sobre la diagonal $y=x$, así que la línea quedaba invisible debajo de ella.
- **Balance de materia global** — `core/balance_materia.py`, clase `BalanceMateriaGlobal` ($F=D+B$, $F z_F=D x_D+B x_B$). Resuelto con `scipy.optimize.root` genérico en vez de derivar a mano las ~15 combinaciones posibles de incógnitas (varias son bilineales, p.ej. $D$ y $x_D$ ambas desconocidas). Es un sistema **separado** del escalonamiento — no resuelve el caso de 2 incógnitas simultáneas dentro de `calcular_escalones` (eso seguiría necesitando una extensión distinta). Hallazgo real: MINPACK/`hybr` puede reportar `success=False` ("not making good progress") con el residuo ya exactamente en cero, porque el sistema es casi lineal y converge en pocos pasos — se corrigió el criterio de convergencia para confiar en el residuo, no en `sol.success`.
- **Condensador parcial** — `calcular_escalones(..., condensador_parcial=True)`. La geometría (R_min, ROL, SOL) no cambia (la ROL siempre cruza la diagonal en su término independiente, sea $x_D$ líquido o $y_D$ vapor); se usó la simplificación estándar de libro (+1 etapa, verificado exactamente) en vez de reescribir el bucle de escalonamiento — la ubicación gráfica exacta del punto del condensador dentro del escalonamiento tiene variantes según el texto, y se dejó marcado explícitamente como el único punto de esta extensión sin verificación completa.
- **Eficiencia de Murphree ($E_{MV}$)** — `calcular_escalones(..., E_MV=1.0)`. El paso físico ya no busca la curva de equilibrio real sino la de pseudo-equilibrio $y_{pseudo}(x)=y_{op}(x)+E_{MV}(y_{eq}(x)-y_{op}(x))$, vía `brentq` (no hubo que cambiar a un método basado en `x0`: el bracket original sigue sirviendo y el costo por paso es prácticamente idéntico — 20 corridas completas en ~8ms vs ~14ms). $R_{min}$/pinch siguen usando la curva de equilibrio real, sin tocar — la eficiencia de plato no cambia el límite termodinámico. Verificado: $E_{MV}=1.0$ reproduce exactamente el resultado anterior; $E_{MV}$ decreciente aumenta $N$ monótonamente y con fuerza (11.97→13.37→17.28→24.29→40.69 etapas al bajar de 1.0 a 0.3), la dirección física correcta.
- **Cargas térmicas** — `EvaluadorMcCabeThiele.calcular_cargas_termicas(D,B,F,z_F,x_D,x_B,R_ext,q,T_reflujo=None)`, bajo CMO (el tratamiento riguroso de entalpía queda para Ponchon-Savarit). $\Delta H_{vap}$/$C_{p,L}$ "de mezcla" son el promedio ponderado por composición de las propiedades puras de `ProveedorTermodinamico` (no hay modelo de entalpía de exceso). Verificado: sin subenfriar, $R_{int}=R_{ext}$ exacto y $Q_c$ coincide con la fórmula simple $D(R+1)\Delta H_{vap,D}$; con 10K de subenfriamiento, $R_{int}>R_{ext}$ y $Q_c$ aumenta, ambos en la dirección física correcta.

### ✅ Método de Ponchon-Savarit (Completado)
- `core/ponchon_savarit.py`, clase `EvaluadorPonchonSavarit` — método riguroso de entalpía-composición, sin la simplificación CMO de McCabe-Thiele. Autocontenido: construye su propia curva $y(x)$ del mismo barrido de `burbuja_T` que ya necesita para $H_L(x)$/$H_V(y)$, sin depender de `EvaluadorMcCabeThiele`.
- **Curvas de entalpía**: $H_L(x)=\sum x_i\int_{T_{ref}}^{T_{burbuja}(x)}C_{p,L,i}\,dT$ (vía `scipy.integrate.quad`, referencia $H_{puro}(298.15K)=0$), $H_V(y)=H_L(y,\text{mismo }T)+\sum y_i\Delta H_{vap,i}(T)$ — ambas evaluadas a la MISMA T de burbuja por cada $x$ (son una línea de reparto real, no curvas independientes). Extremos exactos en los puntos de ebullición puros ($T_b$ de `thermo`, sin pasar por UNIFAC en $x=0$ o $x=1$, que se porta mal ahí). Verificado: $H_V>H_L$ siempre, y $H_V(x)-H_L(x)\approx$ 31-33 kJ/mol en todo el rango — coincide con los $\Delta H_{vap}$ reales de benceno/tolueno. Construcción de 80 puntos: ~0.24s, sin problema de desempeño con `quad`.
- **Cambio de interfaz deliberado** respecto a la directiva: en vez de pedir $D,B,Q_c,Q_R$ por separado, `calcular_escalones` solo pide los cocientes específicos `Qc_D` ($=Q_c/D$) y `QR_B` ($=Q_R/B$) — es lo único que aparece en las fórmulas de los polos ($H_{\Delta D}=H_L(x_D)+Q_c/D$), y evita necesitar flujos absolutos para la geometría del escalonamiento (mismo espíritu que $R$ en McCabe-Thiele, que tampoco necesita $D$ absoluto).
- **Tolerancia de colinealidad corregida**: la directiva pedía `1e-6` absoluto sobre la diferencia de pendientes, pero las entalpías aquí son de orden $10^4$-$10^5$ J/mol — a esa escala, `1e-6` absoluto exige igualdad casi exacta en punto flotante, imposible de cumplir ni con redondeo de spline. Se usó tolerancia **relativa** (`rtol`) en su lugar. Verificado: pasa con polos construidos para ser exactamente colineales, y rechaza correctamente un `Q_R` inconsistente con mensaje claro.
- **Bug real de dirección, encontrado y corregido antes de dar el escalonamiento por bueno**: el criterio de cambio de polo dictado era "cuando la pendiente operativa supere la pendiente global, cambiar a $\Delta_B$" — pero la pendiente empieza muy por ENCIMA de la global (cerca de $x_D$) y decrece monótonamente; con el sentido literal ("supera"), el cambio se disparaba en la primerísima etapa, todavía pegado a $x_D$, físicamente incorrecto. Se verificó trazando $m$ etapa por etapa antes de confiar en el criterio, y se corrigió a "cuando $m$ cae por debajo de la global".
- **Validación cruzada fuerte con McCabe-Thiele**: con benceno/tolueno (casi ideal, CMO es buena aproximación ahí) y $R_{equiv}=Q_c/D/\Delta H_{vap,D}-1$, $N_{Ponchon-Savarit}$ coincide con $N_{McCabe-Thiele}$ dentro de 0.6%-2.5% en tres niveles de reflujo — la composición del escalonamiento es monótona en los tres casos.
- Un `Qc_D` cercano al equivalente de $R_{min}$ produce un *pinch* cerca de $z_F$ (igual que $R<R_{min}$ en McCabe-Thiele): verificado que falla limpio (`RuntimeError` tras el límite de etapas), no con un `brentq` confuso.
- **`SolucionadorPonchonSavarit`** — el mismo patrón EO de grados de libertad que `SolucionadorMcCabeThiele`, cerrado a partir de una observación correcta del usuario ("¿esto no está resolviendo el sistema, solo estás probando valores en un for?"): la primera validación de esta pieza efectivamente solo *barría* valores fijos de `Qc_D` a mano, no resolvía nada — con `q=-0.5` (vapor sobrecalentado) esos valores fijos (calibrados para `q=1`) pinchaban, exponiendo el hueco.
  - Variables del evaluador: `(z_F, x_D, x_B, Qc_D)` — **`QR_B` no es una incógnita independiente**, queda derivado de `Qc_D` por la restricción de colinealidad (`derivar_QR_B`); es la diferencia estructural real frente a McCabe-Thiele, donde las 5 variables sí son libres entre sí.
  - **`calcular_Qc_D_min`** — el equivalente de `R_min`, pero sin fórmula cerrada disponible (el punto de pinch de Ponchon-Savarit no coincide en general con `z_F`, a diferencia de la intersección algebraica simple de la línea $q$ en McCabe-Thiele): se ubica **numéricamente por bisección** sobre éxito/fracaso de `calcular_escalones`. Verificado contra los pinches ya conocidos de memoria (`q=1`→80960, entre el 75000 que pinchaba y el 150000 que funcionaba; `q=-0.5`→166650, entre el 150000 que pinchaba y el 300000 que funcionaba) — coincide exactamente.
  - Verificado: resolver $Qc_D$ dado $N=10$ converge exacto (`N=10.000000`) tanto para `q=1` como para `q=-0.5`; casos de evaluación directa, subdeterminado y sobre-especificado inconsistente manejados igual que en McCabe-Thiele.
  - La validación cruzada contra McCabe-Thiele, reescrita para escalar con `Qc_D_min` en vez de constantes fijas, ahora funciona igual de bien en `q=1` y `q=-0.5` sin pinchar — la causa raíz del bug original quedó resuelta, no parchada.
- **Hallazgo sobre `q` fuera de `[0,1]`**: `H_F_desde_q` es una aproximación lineal (secante entre $H_L(z_F)$ y $H_V(z_F)$) que sigue siendo "matemáticamente" evaluable para cualquier `q`, pero un `q` demasiado alejado de `[0,1]` puede implicar una temperatura de alimentación físicamente imposible. Verificado invirtiendo la integral de `Cp_L`: para benceno/tolueno con $z_F=0.4$, `q=1.5` ya implica `T≈260K` (bajo el punto de fusión del benceno, ~278.5K) y `q=2` implica `T≈133K` (bajo el de ambos componentes puros). No es un bug — ninguno de los dos módulos (McCabe-Thiele ni Ponchon-Savarit) valida esto todavía; queda como mejora posible (rechazar/advertir si la T implícita cae bajo el punto de fusión de la mezcla).

### ✅ Método FUG - Fenske-Underwood-Gilliland (Completado, con una reserva marcada)
- `core/fug.py`, clase `AnalizadorFUG`. Reutiliza `CalculadoraELV`/`ProveedorTermodinamico` **sin modificarlos** — ya eran multicomponente-generales (`coeficientes_actividad` vía UNIFAC y `presiones_saturacion` no tienen ningún supuesto binario hardcodeado); confirma que la arquitectura de esas dos piezas estaba bien pensada desde el principio.
- **Hueco real en la directiva, resuelto con criterio estándar de libro**: para el α promedio de 3 puntos de Fenske hace falta $T_D/T_B$, que a su vez necesitan una composición de producto — pero esa composición es justo lo que el método calcula. Se resolvió con el bootstrap clásico: clasificar componentes por punto de ebullición normal (más ligero/más pesado que las claves), construir una distribución inicial (no-clave 100% a un producto; claves según recuperación especificada), usar esa distribución para $T_D/T_B$, y refinar la distribución **completa** con la propia razón de Fenske una vez que $N_{min}$ está disponible.
- **Caso sharp-split** (claves adyacentes, sistema propano/n-butano/n-pentano/n-hexano): verificado a fondo — recuperaciones exactas (98.00%/98.00%/2.00%/0%), $T_D<T_F<T_B$, $N>N_{min}$ siempre, y $N$ decrece monótonamente al subir $R$ (16.2→8.0 entre $R$=1 y 8).
- **Reserva honesta sobre múltiples raíces de Underwood**: al forzar un caso con claves NO adyacentes (saltando n-pentano a propósito) para poder probar la rama de sistema lineal, dio $R_{min}$ **negativo** — no físico. Se verificó a mano (resolviendo el sistema 2×2 con calculadora) que el código sí resuelve correctamente el sistema que arma — no es un bug de traducción ecuación→código. La conclusión más probable es que elegir claves no adyacentes no es una forma válida de plantear Underwood (los componentes "distribuidos" deberían surgir de forma natural entre claves adyacentes, no forzarse saltando uno). Esta rama queda implementada tal como la pidió la directiva, pero **sin la misma confianza** que el caso sharp-split — usar con precaución caso por caso, no como default.
- **Validación extendida** (`tests/validar_fug.py`, 5 casos adicionales, todos consistentes):
  - Otro par de claves adyacentes (propano/n-butano, no-clave más pesados): balance exacto, recuperaciones exactas — confirma que el método no depende de qué par adyacente se elija.
  - Sensibilidad a la recuperación especificada (90%→99.9% con las mismas claves): $N_{min}$ sube monótonamente (4.09→12.88) y $R_{min}$ también (0.50→0.81), como exige la teoría — a mayor pureza exigida, más etapas y más reflujo mínimo hacen falta.
  - Alimentación con composición muy distinta (un componente dominante al 70%): el bootstrap no se rompe, balance de materia exacto.
  - **Hallazgo que refuerza la reserva anterior**: con las claves adyacentes del caso base (n-butano/n-pentano), NINGÚN componente no-clave cae naturalmente entre sus volatilidades — es decir, para esta serie de alcanos (bastante ideal, el orden de $T_b$ coincide con el de volatilidad) el camino de múltiples raíces de Underwood **nunca se activa solo**. Confirma que el caso de múltiples raíces documentado arriba fue forzado artificialmente (saltando un componente a propósito) y no algo que este sistema produzca de forma natural.
  - Fenske de 2 puntos (domo/fondo, sin alimentación) vs el de 3 puntos que usa `AnalizadorFUG`: diferencia de solo 0.20% en $N_{min}$ para el caso base — el refinamiento de 3 puntos es una corrección menor, no un cambio drástico, lo que da más confianza en que el bootstrap no está introduciendo un sesgo grande.
- **Conectado al Orquestador, con Cargas Térmicas** (`core/orquestador.py`: `bloque_fug`, `bloque_cargas_termicas_fug`; `core/fug.py`: nuevo método `AnalizadorFUG.calcular_cargas_termicas`):
  - `calcular_cargas_termicas` generaliza **exactamente** las mismas fórmulas de `EvaluadorMcCabeThiele.calcular_cargas_termicas` (CMO, sin calor de mezcla) — ahí el promedio ponderado de Hvap/Cp estaba hardcodeado a `[x, 1-x]` (2 componentes); aquí es el mismo producto punto pero con `x_D`/`x_B` de n componentes. No se inventó física nueva, solo se generalizó la ponderación.
  - **Decisión de diseño consultada con el usuario**: en vez de que `bloque_fug` exponga al pool solo escalares (N, R, D, B) dejando las composiciones ocultas dentro del bloque, se optó por **generalizar el pool del Orquestador a variables vectoriales** (`x_D`, `x_B`, `d`, `b` viven en el pool como arrays de n componentes, no como floats).
  - **Hallazgo real al implementarlo**: `Orquestador`/`BloqueEcuaciones` no necesitaron NINGÚN cambio de código para soportar vectores — el bucle de resolución solo compara `pool[v] is None` (identidad), nunca hace aritmética ni evalúa verdad-o-falso sobre el valor en sí, así que ya era agnóstico al tipo. Se verificó corriendo `ejemplo_orquestador.py` end-to-end antes de confiar en esta afirmación (no se asumió).
  - **Detalle de escala que sí importaba y se resolvió explícitamente**: `AnalizadorFUG` trabaja normalizado a F=1 (z_F suma 1), así que su `D`/`B`/`d`/`b` internos son FRACCIONES. El resto del orquestador (`bloque_balance_materia`, `bloque_cargas_termicas`) usa `D`/`B` como flujos molares reales. `bloque_fug` recibe `F` como entrada y escala fracciones a flujos antes de escribir al pool, para que el nombre "D"/"B" signifique lo mismo en todos los bloques.
  - Verificado end-to-end en `ejemplo_orquestador.py` (F=100 mol/s, recuperaciones 98%/98%, R=3.0): $N_{min}$/$R_{min}$/$N$ coinciden exactamente con los de `tests/validar_fug.py`; D+B=100 (cierre de balance); $Q_c$≈3.05 MW, verificado a mano con Hvap ponderado (≈20.3 kJ/mol) dando ≈3.25 MW — mismo orden de magnitud, físicamente razonable para una columna de hidrocarburos ligeros a esa escala.
  - Estos dos bloques nuevos son para un Orquestador **dedicado a FUG** — no se combinan con los bloques binarios (`bloque_mccabe_thiele`/`bloque_ponchon_savarit`/`bloque_balance_materia`) porque ahí `z_F`/`x_D`/`x_B` son floats de un componente, no arrays.

### ✅ `ColumnaDestilacion` - selector de método (Completado)
- `core/columna_destilacion.py`. El usuario pidió que el orquestador "se adapte a la operación que elija" en vez de tener una instancia dedicada por método — pero un `Orquestador` único y compartido entre métodos NO es el camino correcto a largo plazo: el choque de nombres binario-vs-FUG (`z_F`/`x_D`/`x_B` float vs array) es solo el síntoma más visible de un problema más general — **dos columnas del MISMO método** en un futuro flowsheet con operaciones conectadas por flechas también chocarían en nombres como `"D"`/`"R"` si compartieran un pool.
- **Decisión de arquitectura para escalar al flowsheet futuro** (conectar operaciones con flechas, pendiente — ver `Corriente`/Stream en tareas futuras): cada operación unitaria debe ser **autocontenida** — su `Orquestador` interno es un detalle de implementación privado, no algo compartido por nombre con otras columnas. `ColumnaDestilacion(metodo, **solvers)` es el primer paso de ese patrón: una sola fachada (`.resolver(**valores)`) que internamente arma el `Orquestador` correcto (McCabe-Thiele+balance+cargas térmicas, Ponchon-Savarit+balance, o FUG+cargas térmicas FUG) según el método elegido al construirla. Cuando se construya `Corriente`, las conexiones entre columnas se harán pasando esas corrientes explícitas entre instancias de `ColumnaDestilacion`, no fusionando pools.
- No se tocó ningún solver ya verificado (`SolucionadorMcCabeThiele`, `SolucionadorPonchonSavarit`, `AnalizadorFUG`) — es una capa puramente aditiva sobre los bloques existentes.
- Verificado en `ejemplo_columna_destilacion.py`: los 3 métodos (McCabe-Thiele, Ponchon-Savarit, FUG) corridos bajo la misma fachada, con resultados numéricos idénticos a los ya validados por separado (x_B≈0.05/R≈3.06 para McCabe-Thiele; N=9.4349, D=40/B=60 mol/s, Q_c≈3.05 MW para FUG).

---

# Fase 4: Motor Riguroso (Solucionador MESH)

El simulador industrial. Modela el equipo real plato por plato.

### ✅ Andamiaje de Software (Completado)
- Archivo `core/mesh_solver.py` creado.
- Estructura de "Fronteras y Núcleo" lista para recibir los tensores.

### ✅ Camino previo a MESH: entalpía unificada, flash y equipos térmicos (Completado)

Decisión de orden, tomada antes de escribir una sola ecuación MESH: **un flash es literalmente el sistema MESH con $N=1$**, así que resolverlo obliga a fijar ahora todo lo que la columna rigurosa va a necesitar después (cómo se representa $K$, cómo se mide la entalpía de una corriente, qué forma tiene el residuo) pero en un caso de una etapa donde cada número se comprueba a mano. MESH multi-etapa falla de forma silenciosa: si no converge, no se sabe si el problema es el Jacobiano, la inicialización, la entalpía o el $K$. Con el flash se aíslan tres de esas cuatro fuentes antes de tener que mirar la cuarta. Documentado en **[`../04-entalpia.md`](../04-entalpia.md)** y **[`../05-flash.md`](../05-flash.md)**.

**1. La entalpía estaba implementada TRES veces, con convenciones distintas.** Ponchon-Savarit integraba $C_p$ de la mezcla con `quad`; el mezclador del flowsheet usaba la forma LINEALIZADA $h=C_p(T)(T-T_{ref})$, que no es la integral salvo que $C_p$ sea constante (entre 300 K y 380 K el $C_p$ del benceno sube un 15 %); McCabe-Thiele combinaba $\Delta H_{vap}$ y $C_p$ a mano. Mientras cada módulo se validaba por su cuenta no se notaba, porque cada uno era internamente consistente. Se nota en cuanto se encadenan equipos: dos definiciones distintas de $h$ significan energía que aparece o desaparece en la frontera entre un equipo y el siguiente.
  - `thermodynamics/entalpia.py`, clase `CalculadoraEntalpia`. Camino único: $h_L(T,x)=\sum_i x_i\int_{T_{ref}}^{T}C_{p,L,i}dT'$, $h_V(T,y)=h_L(T,y)+\sum_i y_i\Delta H_{vap,i}(T)$, referencia puros líquidos a 298.15 K. Única aproximación: mezcla ideal (no hay $h^E$ en `thermo`).
  - **Tabulación por componente puro, no por mezcla.** Como $C_{p,mezcla}=\sum x_i C_{p,i}$ y $x$ no depende de $T$, la integral de la mezcla es la suma ponderada de las integrales puras. Eso permite tabular $h_i(T)$ una vez y evaluar cualquier composición como producto punto. No se integra numéricamente: se ajusta un spline a $C_{p,i}(T)$ y se usa su **primitiva analítica**. Medido: construir `EvaluadorPonchonSavarit` pasó de ~0.24 s solo en entalpías a **0.121 s en total**.
  - **Sin regresión, verificado antes de conectarlo:** el tabulado coincide con la `quad` anterior a $10^{-10}$ relativo, y por eso Ponchon-Savarit reproduce sus números exactos ($Q_c/D$ mínimo 80960 para $q=1$ y 166650 para $q=-0.5$, razón $N_{PS}/N_{MT}$ entre 1.002 y 1.033) y McCabe-Thiele los suyos ($R_{min}=1.0920$, $N=12.506$, $R=2.4830\to N=10.000000$, condensador parcial $+1.000000$).
  - **Una tabla por proveedor, a propósito** (`entalpia_de`): no es caché, es lo que garantiza que mezclador, columna y flash midan con la misma referencia. Pedir otra $T_{ref}$ sobre un proveedor que ya tiene calculadora **falla** en vez de devolver la cacheada en silencio — devolverla sería peor, porque el que la pidió creería estar usando su referencia y la discrepancia solo aparecería como un balance que no cierra varios equipos más abajo.
  - La inversión $h\to T$ es ahora una raíz exacta (`brentq` sobre $h_L$, estrictamente creciente porque $C_p>0$ se verifica al construir), en vez del punto fijo de 8 pasadas del mezclador, que se cortaba por número de vueltas y no por convergencia. Para el vapor la monotonía **no** está garantizada ($C_{p,V}=C_{p,L}+d\Delta H_{vap}/dT$, segundo término negativo), así que se comprueba en el tramo usado en vez de suponerse.
  - Cambio de fondo en McCabe-Thiele: el término de subenfriamiento era $C_p(T_D)(T_D-T_{reflujo})$, o sea $C_p$ congelado en $T_D$. Ahora es la diferencia real $h_L(T_D)-h_L(T_{reflujo})$, que es la integral entre las dos temperaturas. Coinciden cuando el subenfriamiento es pequeño y se separan cuando es grande, que es justo cuando el término importa.

**2. Punto de ROCÍO, que no existía.** Sin él no se puede distinguir una corriente bifásica de un vapor sobrecalentado. No es simétrico con la burbuja: la de burbuja es explícita ($x$ se conoce), la de rocío es implícita ($1/P=\sum y_i/(\gamma_i(T,x)P_i^{sat})$, con $\gamma$ dependiendo del líquido, que es la incógnita). Se resuelve por punto fijo desde el caso ideal. `CalculadoraELV` gana `rocio_P` y `rocio_T`. **Validación cruzada fuerte, con dos rutinas independientes**: el líquido de la primera gota, metido de vuelta en `burbuja_P`, devuelve la misma $P$ ($10^{-9}$ relativo) y el vapor original $y=z$ ($9\times10^{-15}$).

**3. `core/flash.py`, clase `EvaluadorFlash`** — Rachford-Rice en su forma restada $f(\beta)=\sum z_i(K_i-1)/(1+\beta(K_i-1))=0$, no en la forma $\sum x_i=1$: esta última es casi plana en $\beta$ cuando la separación es fácil y el root-finding se vuelve mal condicionado justo en el caso cómodo. Tres especificaciones, mismo espíritu EO que el resto: `isotermico(T,P)`, `a_entalpia(P,h)`/`con_calor(P,Q)` y `a_fraccion(P,beta)`.
  - **El diagnóstico de fase NO se deja al Rachford-Rice.** $f(0)$ y $f(1)$ necesitan $K$ evaluada en la composición correcta de cada fase, y esa composición es justo lo que todavía no se conoce; usar $z$ en ambos casos da un diagnóstico sesgado cerca de las fronteras. Se hace antes, con burbuja y rocío, que son exactos y ya validados.
  - El flash P-H no busca $T$ a ciegas: ubica primero $T_{burbuja}$ y $T_{rocío}$, con lo que la clasificación de fase sale como **subproducto del propio balance de energía** y no como una comprobación aparte que podría contradecirlo.
  - Verificado: balance de materia $z=\beta y+(1-\beta)x$ a $5\times10^{-17}$; $\sum x=\sum y=1$ **exactas** (no impuestas — se deducen de $f(\beta)=0$ junto con $\sum z=1$, y por eso son un test real del solver); equilibrio $y_i=K_ix_i$ con $K$ recalculada desde cero a $10^{-12}$; $\beta$ monótona con $T$; ida y vuelta $\beta\to T\to\beta$ a $10^{-10}$; ternario acetona/metanol/agua (6 iteraciones el binario, 27-34 el ternario, como corresponde a su no idealidad).

**4. Tres equipos nuevos en el flowsheet: flash, intercambiador y válvula.**
  - **La fase de una corriente no es un dato, es una consecuencia de $(T,P,z)$.** Hasta ahora todo balance de energía suponía líquido porque no había forma de saber otra cosa. `entalpia_de_corriente(T,P,z)` la deduce con un flash isotérmico, y es barata en el caso común: si la corriente es líquido subenfriado, el flash se corta en la comprobación de burbuja, o sea una sola llamada a UNIFAC. Consecuencia de diseño: **una corriente bifásica se describe sin ambigüedad con las variables que ya existen** ($F$, $T$, $P$, $x$) — no hizo falta añadir ninguna variable de fase por corriente ni tocar los grados de libertad.
  - **El mezclador dejó de suponer líquido**, que importa el doble porque es por donde entra un reciclo. **Medido** mezclando 100 mol/s de líquido a 330 K con 40 mol/s de vapor sobrecalentado a 378 K: la definición vieja perdía **9032 J/mol** (el 56 % de la entalpía de la mezcla) y daba **344.30 K en vez de 368.13 K** — 23.8 K, y además declaraba líquida una mezcla que es bifásica ($\beta=0.163$). Nota: la dirección del error es a la BAJA, no al alza; ignorar el calor latente que entra cuenta menos energía de la que hay.
  - El intercambiador calcula su $T$ con el flash P-H, no invirtiendo $h_L$: calentar lo suficiente vaporiza, y con $h_L$ a secas el equipo devolvería una $T$ inventada por encima del punto de burbuja sin avisar.
  - La válvula es isentálpica, no un intercambiador con $Q=0$: lo que cambia es la presión, y ese cambio redistribuye la MISMA entalpía entre calor sensible y latente. Verificado que enfría al expandir (434.6 K → 369.6 K de 6 atm a 1 atm, $\beta=0.368$) sin que nadie le quite energía.

**5. Plantas encadenadas — `tests/validar_planta_encadenada.py`, la suite que faltaba.** Un equipo suelto puede estar bien y la planta estar mal; lo que no se comprobaba nunca era la FRONTERA entre equipos. Tres cadenas: (A) intercambiador→válvula→flash, (B) mezclador→intercambiador→flash→divisor→**reciclo**, (C) flash→columna McCabe-Thiele.
  - Balance de ENERGÍA global: **$1.9\times10^{-12}$ relativo sin lazo y $4.2\times10^{-12}$ con lazo**. El del lazo solo cierra si el mezclador, el intercambiador, el flash y el divisor miden la entalpía con la misma definición — es la razón de ser del punto 1.
  - El lazo converge a $5\times10^{-13}$ en 49 vueltas, y cierra materia y energía con 0 %, 30 %, 50 %, 70 % y 85 % de recirculación.
  - Cadena C: **el líquido que sale de un flash está en su punto de burbuja**, verificado a $10^{-9}$ K contra `burbuja_T`. Eso es lo que hace que conectarlo a una columna con $q=1$ sea exacto y no una suposición.

**Dos defectos reales que solo aparecieron al encadenar** (ninguno se veía con los equipos sueltos):
  - **La columna binaria re-fijaba la T de una alimentación que otro equipo ya había fijado.** La guarda existía para la PRESIÓN (`_presion_fijada`) y también en FUG para su alimentación, pero no en la columna binaria para la T. Meter un flash antes de una columna daba **GL = −1** ("sobran datos") con el diagrama bien planteado. Mismo fallo de familia que ya se había corregido, solo que arreglado en la mitad de los sitios. Corregido de forma simétrica, para la alimentación y para los dos productos.
  - **`q_fijo` se ignoraba en silencio en la rama McCabe-Thiele.** Solo se publicaba al pool en la rama Ponchon-Savarit. Pasar `q_fijo=1.0` a una columna McCabe-Thiele no hacía absolutamente nada: `q` seguía sin determinarse y arrastraba consigo $N$, $Q_c$, $Q_R$ y las temperaturas — con el contador de grados de libertad diciendo GL = 0, o sea el mismo fallo silencioso de siempre (datos "correctos", nada resuelto, ningún motivo). Corregido.

**Lo que queda fuera a propósito:** los tres equipos nuevos **no están expuestos en la interfaz** — `backend/nucleo_diagrama.py` despacha por tipo (columna, reactor_cstr, mezclador, divisor, bomba) y no los conoce, ni hay nodos ni paneles para ellos en el frontend. Son usables desde la API de Python, no desde el navegador.

### ✅ Balance de energía del reactor (Completado)

El reactor era el **único equipo sin balance de energía**: se le daba $T$ y punto. Después de la tanda anterior, mezclador, flash, intercambiador, válvula y columnas ya tenían el suyo, y el CSTR no — un grep de `energia|entalpia|H_rxn|adiabat` sobre `core/reactor_cstr.py` daba **cero coincidencias**. Eso dejaba fuera justo lo que hace interesante a la destilación reactiva: el acoplamiento entre el calor que suelta la reacción y lo que pasa con la separación. Documentado en **[`../09-reactor-cstr.md`](../09-reactor-cstr.md)** §9.7-9.10.

$$F_{in}h(T_{in},x_{in}) + Q = F_{out}h(T_{out},x_{out}) + \xi\,\Delta H_{rxn}^\circ(T_{ref})$$

**El punto fino, y la razón de que este balance no se pudiera escribir bien hasta que la entalpía se unificó.** $h$ mide entalpía SENSIBLE (referencia: puros líquidos a $T_{ref}$, $h_i=0$), no incluye entalpías de formación. Al desarrollar el balance verdadero con $H_i(T)=\Delta H_{f,i}^\circ(T_{ref}) + h_i(T)$, los términos de formación de las especies que no reaccionan se cancelan y queda el de arriba, con $\Delta H_{rxn}$ evaluado **exactamente en esa $T_{ref}$** — no en $T_{out}$.
  - **No es la aproximación "$\Delta H_{rxn}$ constante con T".** La dependencia con T ya está contenida en $F_{out}h(T_{out},x_{out})$, porque ese término incluye $\sum\nu_i h_i(T_{out})$, que es precisamente la corrección de Kirchhoff. Usar $\Delta H_{rxn}(T_{out})$ la contaría DOS veces.
  - Medido, no argumentado: en el reactor adiabático de MTBE ($\xi=12$ mol/s, 330 → 383.45 K) el balance cierra a $1.6\times10^{-9}$ W con $\Delta H_{rxn}^\circ$, y el doble conteo metería **41.31 kW** de error — exactamente $\xi\sum\nu_i[h_i(T_{out})-h_i(T_{ref})]$, comprobado al vatio.
  - Que las dos referencias coincidan (298.15 K en `CalculadoraEntalpia` y en `GestorReaccion`) no se da por hecho: **se comprueba antes de cada balance**. Con otra referencia el error se repartiría en silencio entre $Q$ y $T$ y nadie lo notaría.

**Tres modos, mismo espíritu EO que el resto** (`modo_energia`): `isotermo` (se da T, se calcula el Q que cuesta mantenerla), `adiabatico` ($Q=0$, se calcula T) y `calor_dado`.
  - El modo por defecto es **compatible hacia atrás**: un reactor que antes solo pedía T sigue funcionando igual. Lo que gana es la respuesta a una pregunta que el simulador no podía contestar — **cuánta refrigeración cuesta esa temperatura**. Para MTBE con $\xi=12$ mol/s son **702 kW**, y en una exotérmica ese número suele ser la restricción de diseño real.
  - Sin proveedor termodinámico, el reactor vuelve a ser isotermo con T como dato, exactamente como antes; los otros dos modos se rechazan con motivo en vez de fingir un balance. Verificado: un reactor sin proveedor resuelve igual que siempre y ni siquiera declara la variable Q.

**El caso ACOPLADO (cinética + energía), que es el único que necesita resolverse como sistema.** La cinética necesita T para dar $\xi$ y el balance necesita $\xi$ para dar T: ninguno puede arrancar, y con el motor de punto fijo el síntoma sería "faltan datos", indistinguible de un diagrama mal planteado. Es el mismo problema que un reciclo y se resuelve igual — las dos ecuaciones a la vez, con `scipy.optimize.root`. Un solo bloque SUSTITUYE a los de cinética y energía por separado y aporta las mismas 3 ecuaciones, así que los grados de libertad no cambian.
  - **Los dos residuos se adimensionalizan, y no es cosmético.** Sin normalizar quedan en unidades distintas (mol/s frente a W) y separados por ~$10^6$: `hybr` reparte su esfuerzo según la norma del vector, así que el residuo de materia se vuelve invisible frente al de energía y un criterio de parada único no significa lo mismo para los dos. Se vio como un falso "no convergió" con residuo 2.5e-7 que en realidad era un error relativo de $10^{-11}$ en la energía.
  - **Defecto real encontrado y corregido: el arranque tímido.** La primera versión partía de un único punto "prudente" (1 % del límite estequiométrico, $T=T_{in}$). Con una exotérmica fuerte el estacionario está lejos, `hybr` no lo alcanza, y el método reportaba "no convergió" **cuando sí había solución**. Medido con $A=10^{10}$ y $V=2$ m³: desde el arranque tímido fallaba, y desde 10 de 15 arranques distintos convergía siempre al mismo $\xi=9.4699$ mol/s, $T=372.66$ K. Ahora se prueban varios y **no son arbitrarios**: para cada avance de prueba se calcula la T que le corresponde por balance de energía, o sea que cada arranque ya satisface el residuo energético y al solver solo le queda la cinética. Se barre una curva, no un plano.
  - **Multiplicidad de estados estacionarios**: un CSTR exotérmico puede tener más de uno (ignición/extinción). Si aparece no se elige en silencio — se devuelve el más FRÍO (el que alcanza un arranque en frío, que es lo que físicamente pasa al poner en marcha el equipo) y se listan todos con una bandera `multiplicidad`. Límite anotado: que un estacionario exista no implica que sea ESTABLE; eso necesita el modelo dinámico, que no está.

**Guarda nueva: el tanque no puede estar hirviendo.** Un CSTR de este simulador es un tanque líquido (la cinética usa actividades de fase líquida y la entalpía es $h_L$). Si la T del balance supera el punto de burbuja a la P de operación, el modelo deja de describirlo — el patrón de fallo clásico del proyecto, un número plausible sobre algo imposible. **No es un caso rebuscado**: el propio reactor adiabático de MTBE hierve a 10 atm (383.45 K contra una burbuja de 357.54 K), y hubo que subir la validación a 30 atm para que el modelo fuera válido. Con `exigir_liquido=False` se devuelve el número junto con la T de burbuja, para quien sepa lo que mira.

**Validación cruzada más fuerte, que ata tres piezas independientes** — el balance de energía (que fija T), van't Hoff (que da $K_{eq}$ a esa T) y el término inverso de la cinética. Con V grande $r\to 0$ y la salida tiene que estar en equilibrio químico *a la temperatura que el propio balance produjo*: el cociente $\prod a_i^{\nu_i}/K_{eq}(T)$ va 0.350 → 0.935 → 0.987 para $V$ = 1, 8 y 40 m³. Y explica la forma de la curva: con una exotérmica, subir T BAJA $K_{eq}$, o sea que **el calor que libera la reacción limita su propia conversión** — por eso $\xi$ se satura en ~10.3 mol/s y no sigue creciendo con V.

**Error mío, corregido antes de dejarlo escrito:** la primera versión del test afirmaba que $Q_{endo} = -Q_{exo}$ al invertir el signo de $\Delta H$. Es falso: $Q = [F_{out}h_{out}-F_{in}h_{in}] + \xi\Delta H$, y cambiar el signo de $\Delta H$ solo cambia el segundo término. La identidad que sí se cumple, y que aísla el término de reacción, es $Q_{exo}-Q_{endo} = 2\xi\Delta H_{rxn}$ — verificada exacta ($-1382400.0000$ W).

Suite nueva: `tests/validar_energia_reactor.py` (evaluador + los tres modos en el flowsheet + guardas).

### ⬜ Planteamiento Residual (Pendiente)
- Armado de las grandes matrices tridiagonales para los balances $M$ (Masa), $E$ (Equilibrio), $S$ (Sumatoria) y $H$ (Entalpía).

### ⬜ Acoplamiento Reactivo (Pendiente)
- Inyección de la matriz de generación/consumo cinético en el balance de Masa.
- Inyección del tensor de calor de reacción en el balance de Entalpía.

### ⬜ Algoritmo de Convergencia Numérica (Pendiente)
- Construcción del Jacobiano.
- Implementación de Newton-Raphson multidimensional adaptado a perfiles de columna (o adaptación de un método Inside-Out).

---

# Fase 5: API, Interfaz y Visualización

La cara final del software donde se configura la corrida.

### ✅ API de Recepción (Parcialmente Completado)
- Clase `SimuladorColumnaReactiva` estructurada para recibir configuraciones (Flujo, $T$, $P$) con objetos `pint` y hacer el puente seguro al SI.

### ✅ Orquestador — grados de libertad entre bloques (Parcialmente completado)
- `core/orquestador.py` — nace de una pregunta directa del usuario ("¿tengo la flexibilidad de meter cualquier variable que tenga a mano?") que expuso el límite real: cada `resolver()` (McCabe-Thiele, balance de materia) solo despeja **una** incógnita porque solo aporta **una** ecuación — ninguna cantidad de "flexibilidad de interfaz" cambia eso. Lo que hacía falta no era mejorar un solver, era unir varios en un pool compartido.
- Patrón **secuencial-modular de bloques EO**, no una fusión en un sistema simultáneo: cada bloque (`BalanceMateriaGlobal`, `SolucionadorMcCabeThiele`, envueltos sin modificarlos) sigue resolviendo con su propio método robusto (`root_scalar` con bracket, `root` genérico); el orquestador solo mira cuál bloque ya tiene suficiente información, lo resuelve, actualiza el pool compartido, y repite hasta que no hay más progreso. Se descartó a propósito un solve simultáneo de todo junto — perdería las garantías de convergencia de brackets ya construidas (discutido antes de programar).
- Verificado con el caso real que motivó esto: dar `F, z_F, x_D, x_B, q, N` resuelve `D, B` (balance) y `R` (McCabe-Thiele) en una sola llamada. Prueba más fuerte: dar `D, B` en vez de `F` (invirtiendo el balance) hace que el orquestador derive `x_B` primero y lo use automáticamente para resolver `R` después — acoplamiento real entre bloques resuelto por iteración, no un caso independiente trivial. Un caso genuinamente incompleto reporta exactamente qué falta (`incognitas_restantes`) en vez de fallar o adivinar.
- **`SolucionadorPonchonSavarit` y `calcular_cargas_termicas` conectados como bloques adicionales.** Decisión de diseño: no se combinan entre sí en el mismo orquestador — `calcular_cargas_termicas` es específico de McCabe-Thiele/CMO (usa `R`), y Ponchon-Savarit ya trae su propia contabilidad de energía (`Qc_D`/`QR_B`); conectar ambos contaría la energía dos veces con métodos distintos. Se armaron dos combinaciones: `[Balance + McCabe-Thiele + CargasTérmicas]` y `[Balance + Ponchon-Savarit]`.
- **Hallazgo real que obligó a extender `BloqueEcuaciones`**: `calcular_cargas_termicas` no es invertible como los otros dos bloques — dadas sus 8 entradas calcula sus 6 salidas de una sola vez, no hay forma de "pedirle D dado Q_c". Se agregó `variables_entrada` (subconjunto usado para decidir si el bloque ya puede dispararse) separado de `variables` (el total que actualiza el pool), para que las salidas nunca cuenten como incógnitas que bloqueen el disparo.
- Verificado: `[Balance + McCabe-Thiele + CargasTérmicas]` resuelve `D,B,R,Q_c,Q_R,R_int,V_barra,T_D,T_B` — nueve variables — en una sola llamada, con `R_int=R` (consistente, sin subenfriamiento). `[Balance + Ponchon-Savarit]` resuelve `D,B,Qc_D` igual de bien, con valores idénticos a los ya vistos usando cada solver por separado.
- **`api/simulador_destilacion.py`** — `SimuladorDestilacionBinaria`, la tercera frontera de `pint` del proyecto (junto a `config/settings.py` y `api/simulador.py`). Deliberadamente NO arma el `Orquestador` ni decide qué bloques combinar — lo recibe ya construido; solo resuelve el cruce de unidades de esa llamada a `resolver()`. Variables con dimensión física (`F,D,B,Q_c,Q_R,T_D,T_B`) se dan/devuelven como `pint.Quantity`; las adimensionales (`z_F,x_D,x_B,q,R,N,Qc_D`) pasan como `float` tal cual. Verificado con `F` dado en `kmol/h` (unidad no-SI a propósito): convierte correctamente a `mol/s` internamente, y `D,Q_c,Q_R,T_D` regresan convertibles a `kmol/h`, `kW`, `°C` respectivamente.
- La generalización a multicomponente (variables vectoriales) y un primer selector de "ruta de cálculo" ya se abordaron — ver `ColumnaDestilacion` en Fase 3. Pendiente todavía: extender ese selector a Topología/MESH cuando existan, y la abstracción de `Corriente` (Stream) para conectar columnas por flechas en un flowsheet real.

### ⬜ Motor de Graficación Estructurado (Pendiente)
- Generador de perfiles MESH (Temperatura vs Plato, Composición vs Plato).
- Integración final de los subplots generados en las pruebas.

### ✅ `Corriente` (Stream) - Parte 1: el objeto en sí (Completado)
- `core/corriente.py`, clase `Corriente` (nombres, composición, flujo_molar, T, P) + función `mezclar_corrientes`. Pedido explícito del usuario: que sea **flexible**, no atada a destilación — pensada para conectar cualquier operación futura (columnas, reactores, bombas, mezcladores) sin que ninguna conozca los detalles internos de la otra.
- **Decisión de diseño**: `Corriente` es deliberadamente un contenedor de ESTADO puro, sin `ProveedorTermodinamico` ni lógica de propiedades derivadas — para que una operación tan simple como una bomba ideal (solo cambia P) pueda construir su salida sin ninguna dependencia térmica, mientras que una que sí necesita física real (`mezclar_corrientes`, balance de energía) recibe su propio proveedor por fuera, igual que cualquier otro Evaluador/Solucionador del proyecto.
- **Deliberadamente NO se construyó todavía** el conector de flechas/flowsheet ni se cambió la API de `ColumnaDestilacion` para consumir/producir `Corriente` directamente — eso es la Parte 2 (conectar operaciones), fuera de alcance de este paso a propósito.
- `mezclar_corrientes` generaliza la misma física de `EvaluadorPonchonSavarit._entalpia_liquido` (integral de Cp_L, sin calor de mezcla) a n componentes, resolviendo la T de salida por balance de energía real vía `brentq` — **no** un promedio de T ponderado por flujo (que ignoraría que el Cp difiere entre corrientes).
- **Validado en `tests/validar_corriente.py`** con 4 formas distintas de producir/consumir corrientes, probando la flexibilidad pedida:
  1. Construcción + 6 casos de error (longitud, suma≠1, fracción negativa, flujo/T/P no positivos) — todos rechazados correctamente.
  2. Una "bomba" trivial (1 entrada→1 salida, sin ninguna dependencia termodinámica) — prueba que cualquier código, sin heredar de nada, ya puede hablar en términos de `Corriente`.
  3. Un split real con `AnalizadorFUG` (1 entrada→2 salidas): balance de materia por componente exacto, `D+B=F` exacto.
  4. `mezclar_corrientes` (2 entradas→1 salida): remezclar destilado+fondos recupera el balance de materia de la alimentación original exacto. **Hallazgo esperado y correcto, no un bug**: la T recombinada (356.05K) NO coincide con la T de la alimentación original (335.85K) — físicamente correcto, ya que destilado y fondos salen a T distintas entre sí y de la del feed (305.55K y 380.62K); solo el balance de masa debía cerrar, y cierra.
  5. Balance de energía de la mezcla **recalculado de forma independiente** dentro del propio test (integración de Cp y `brentq` escritos de nuevo ahí, sin llamar a `mezclar_corrientes` internamente) — coincide con diferencia 0.00e+00 K. Caso degenerado (mismas T de entrada) verificado por separado: da la T exacta sin pasar por `brentq`.

### ✅ `DiagramaFlujo` (Stream) - Parte 2: conectar operaciones (Completado)
- `core/diagrama_flujo.py`: `OperacionUnitaria`, `_bloque_cable`, `DiagramaFlujo`. El usuario pidió explícitamente contemplar reciclos **desde ahora**, no como extensión posterior.
- **No se reinventó un motor de resolución nuevo**: cada operación se envuelve como `OperacionUnitaria` (mismo patrón que `BloqueEcuaciones` de `Orquestador`) y cada conexión ("flecha") se traduce a un bloque "cable" — una operación no invertible trivial que copia la clave de salida del origen a la de entrada del destino. El grafo completo (operaciones + cables) se resuelve con un `Orquestador` normal, sin tocar su motor de iteración de punto fijo.
- **Espacio de nombres unificado y calificado**: se simplificó el diseño inicial (que distinguía "puertos" calificados de "parámetros" sin calificar) a que TODAS las variables de una operación — sean `Corriente` o escalares como `R`/recuperaciones — se califican como `"nombre_operacion.variable"`. Evita que dos instancias de la misma operación choquen no solo en sus corrientes sino también en un parámetro compartido.
- **Reciclos via sustitución sucesiva** (`resolver_con_reciclo`): el método estándar de simulación de procesos, elegido explícitamente sobre algo más rápido (Wegstein/aceleración) por consistencia con la filosofía del proyecto (iteración simple y robusta). Mecanismo: se EXCLUYE el cable de la conexión de ruptura del grafo, se alimenta un valor supuesto directo en la entrada que ese cable habría llenado, se resuelve el resto del diagrama, se lee el valor recién calculado en la salida real del origen (que al no estar cableada en este armado, sí se calcula libremente), se compara contra el supuesto, y se repite actualizando el supuesto hasta converger.
- **Validado en `tests/validar_diagrama_flujo.py`** con dos casos deliberadamente separados (para no confundir dos preguntas distintas):
  1. **Cadena real sin reciclo** (columna FUG → bomba, conectadas con `.conectar()`): valores idénticos a los ya validados de FUG (N=9.4349), y la bomba (que solo cambia P) preserva flujo/T/composición correctamente vía el cable, no por coincidencia.
  2. **Reciclo con solución analítica exacta** (mezclador + divisor, composición/T idénticas en todo el lazo a propósito, para aislar la prueba a la convergencia de FLUJO sin mezclarla con la pregunta de balance de energía, ya validada aparte): balance de materia da la forma cerrada $R=F_0(1-f)/f$. Verificado primero que el ciclo **sin romper** correctamente NO converge solo (`completo=False`, el comportamiento correcto sin ayuda); luego que `resolver_con_reciclo`, arrancando de un supuesto deliberadamente malo (flujo=0), converge al valor analítico exacto (42.857143 mol/s) en 17 iteraciones — consistente con la tasa de convergencia geométrica esperada (factor 0.3/iteración) para este sistema lineal, no un número arbitrario.

### ✅ `ColumnaDestilacion.a_operacion_unitaria` (Completado)
- `ColumnaDestilacion` ahora se puede enchufar directo a un `DiagramaFlujo` sin escribir un adaptador a mano cada vez — "F" siempre es una `Corriente` de entrada, "D"/"B" son `Corriente` de salida cuando el método las resuelve; `z_F` se traduce automáticamente (vector completo para `fug`, fracción de `nombres[0]` para binarios).
- **Simplificación deliberada, documentada, no oculta**: `ColumnaDestilacion.resolver()` es flexible en grados de libertad (cualquier variable puede ser la incógnita); una `OperacionUnitaria` de `DiagramaFlujo` es un bloque NO invertible (solo se dispara con TODAS sus entradas dadas). Por eso el llamador debe decir explícitamente, para cada diagrama, cuáles variables extra entran conocidas (`variables_entrada_extra`) y cuáles espera que salgan (`variables_salida_extra`) — la misma elección de grados de libertad de siempre, fijada de antemano.
- **Hallazgo real al probar la rama binaria** (no se había probado hasta ahora, solo FUG): dar solo la `Corriente` de alimentación NO basta para McCabe-Thiele/Ponchon-Savarit — hace falta especificar también la separación deseada (`x_D`/`x_B`) en `variables_entrada_extra`, porque `BalanceMateriaGlobal` necesita exactamente 2 incógnitas conocidas entre `{D,B,x_D,x_B}` para dispararse. No es un bug: el feed solo nunca determina el split de una columna, hace falta decir qué separación se quiere. Verificado que con `x_D,x_B,q,R` dados junto al feed, reproduce exactamente D=38.8889, B=61.1111, N≈10 ya validados antes.
- Verificado en `tests/validar_diagrama_flujo.py`: la cadena columna→bomba se reescribió para usar `a_operacion_unitaria` en vez del adaptador escrito a mano — resultados idénticos.
- **Refactor**: se extrajo `ColumnaDestilacion.resolver_desde_feed(F, **valores_extra)` (traducción Corriente↔pool + diagnóstico completo) como método reutilizable, usado tanto por `a_operacion_unitaria` como por `backend/nucleo.py` (ver abajo) — evita duplicar la lógica de traducción z_F/x_D/x_B en dos sitios.
- **Bug real encontrado y corregido antes de construir la API de flowsheet**: para `fug`, `z_F` NO es una variable de pool de `bloque_fug` — `AnalizadorFUG.reporte_completo` siempre usa `self.z_F`, fijado en el constructor. La primera versión de `resolver_desde_feed` escribía `F.composicion` en `valores["z_F"]` como si fuera a usarse, pero nadie la lee — si la `Corriente` traía una composición DISTINTA a la de construcción, el resultado usaba silenciosamente la de construcción, sin avisar. Verificado pasando una composición deliberadamente distinta y confirmando que el resultado no cambiaba (mismo output exacto que con la composición original). Corregido con lo más seguro dado que generalizar `AnalizadorFUG` a `z_F` dinámico tocaría código ya verificado a fondo: `resolver_desde_feed` ahora **valida y falla alto** (`ValueError` claro) si la composición de la `Corriente` no coincide con la de construcción, en vez de fallar en silencio. Un feed FUG con otra composición necesita su propia instancia de `AnalizadorFUG`.

### ✅ Interfaz web (rebanada mínima): FastAPI + Next.js (Completado)
- El usuario pidió una interfaz **seria, desplegable** (Vercel/similar) con stack moderno (React/Next.js) para poder "ver el software en acción" en vez de solo confiar en scripts de consola — no soy una IA, no puede "visualizar" el código mentalmente.
- **Decisión de arquitectura explícita, consultada y justificada**: Vercel solo (funciones serverless de Python) NO es un buen lugar para este backend — `thermo`/UNIFAC/scipy son pesados e iterativos (recuérdese la sustitución sucesiva de reciclos, root-finding anidado de punto de burbuja), chocando con los límites de tiempo/tamaño de paquete de las funciones serverless. Se separó explícitamente: **frontend Next.js en Vercel** + **backend FastAPI en un host Python dedicado** (Render/Railway/Fly.io — pendiente de elegir cuál al desplegar).
- **`backend/`** (FastAPI): `schemas.py` (Pydantic, frontera HTTP/JSON pura, sin física), `nucleo.py` (construye `ProveedorTermodinamico`/`CalculadoraELV`/evaluador-o-analizador según el método y llama a `ColumnaDestilacion.resolver_desde_feed` — sin duplicar lógica de cálculo), `ejemplos.py` (3 casos preset con los mismos números ya validados en sesiones anteriores, no inventados), `main.py` (rutas: `/salud`, `/ejemplos`, `/columna/resolver`).
- **Alcance deliberadamente mínimo primero** (decisión explícita del usuario): una columna sola vía formulario, NO el editor visual de flowsheet con flechas — eso queda como extensión posterior, para no invertir en UI de arrastrar-y-conectar antes de validar que la base (cálculo expuesto por HTTP, desplegado) funciona bien.
- Con presets para no llenar todo el formulario desde cero, tal como pidió el usuario.
- **Verificado con los 3 métodos reales via HTTP** (servidor `uvicorn` real, no solo TestClient — hubo un choque de versión `httpx`/`starlette` con `TestClient` que se evitó levantando el servidor de verdad): los 3 casos preset (McCabe-Thiele y Ponchon-Savarit benceno/tolueno, FUG alcanos) devuelven exactamente los mismos números ya validados en sesiones anteriores (N≈10, N=9.4349, D/B idénticos) — la capa HTTP no introduce ningún error de traducción.
- **`frontend/`** (Next.js 16 + TypeScript + Tailwind, App Router): una página (`app/page.tsx`) con selector de caso preset, formulario editable (composición, flujo, T/P, parámetros del método), y panel de resultados (escalares + corrientes D/B). `npm run build` compila sin errores de TypeScript. Verificado que el dev server sirve la página (200 OK) y que corre junto al backend real.
- **Limitación honesta, no verificada por mí**: no tengo navegador para probar la interactividad del lado del cliente (fetch al backend, actualización de formulario, botón "Resolver") — solo verifiqué que build/servidor/API funcionan por separado. Queda para que el usuario lo confirme corriendo `npm run dev` + `uvicorn backend.main:app --reload` localmente.
- Pendiente: elegir host real para el backend y desplegar (Render recomendado para empezar); restringir CORS a la URL real de Vercel una vez exista (hoy `allow_origins=["*"]` porque no hay dominio de despliegue todavía); inicializar git (el repo no tiene `.git` todavía, necesario para desplegar en Render/Vercel desde git).

### ✅ API de flowsheet (backend, sin UI de flechas todavía) (Completado)
- El usuario priorizó explícitamente exponer `DiagramaFlujo` vía la API **antes** de desplegar o de construir el editor visual de arrastrar-y-conectar — evita construir UI para algo que el backend todavía no podía resolver de punta a punta.
- **`backend/nucleo_flowsheet.py`** + **`backend/schemas.py`** (`OperacionDef`, `ConexionDef`, `RecicloDef`, `ResolverFlowsheetRequest/Response`): catálogo de 4 tipos de operación (los mismos ya verificados en `tests/validar_diagrama_flujo.py`/`validar_corriente.py`, ningún tipo nuevo sin probar): `columna` (envuelve `ColumnaDestilacion.a_operacion_unitaria`), `bomba`, `mezclador` (`mezclar_corrientes`), `divisor` (`dividir_corriente`). Endpoints: `/flowsheet/ejemplos`, `/flowsheet/resolver`.
- **Bug real encontrado y corregido ANTES de construir esta API** (ver arriba, sección FUG): `resolver_desde_feed` ahora valida que la composición de la `Corriente` de alimentación coincida con la `z_F` de construcción de `AnalizadorFUG` para columnas FUG en el flowsheet — sin esto, un nodo FUG con feed dinámico (de una conexión) habría dado resultados silenciosamente basados en la composición equivocada.
- Serialización JSON↔Python: `Corriente` se serializa/deserializa como dict (`nombres`,`composicion`,`flujo_molar`,`T`,`P`); el resto de los valores del pool (escalares, incluyendo `numpy.floating`) pasan tal cual o se castean a `float` nativo.
- **Verificado con los 2 casos de flowsheet reales via HTTP** (servidor `uvicorn` real): replican EXACTAMENTE `tests/validar_diagrama_flujo.py` — columna FUG→bomba da N=9.4349, R_min=0.7502, bomba duplica P sin alterar flujo/T/composición; mezclador+divisor con reciclo converge a 42.857143 mol/s en 17 iteraciones, producto≈100 — mismos números, la capa HTTP no introduce ningún error.
- Pendiente (documentado, no bloqueante): el frontend Next.js todavía NO tiene una vista para flowsheets (solo columna suelta) — el editor visual de arrastrar-y-conectar (probablemente con React Flow) es la siguiente pieza grande de UI, ahora sí con un backend que puede sostenerla.

### ✅ Editor visual de flowsheet (frontend, primera versión funcional) (Completado)
- `frontend/app/flowsheet/` (`types.ts`, `OperacionNode.tsx`, `page.tsx`), usando `@xyflow/react` (React Flow v12). Botones para agregar los 4 tipos de operación (`columna`, `bomba`, `mezclador`, `divisor`); cada nodo dibuja sus puertos de entrada/salida como *handles* nombrados, conectables arrastrando una flecha real entre ellos. Panel lateral de configuración por nodo, corrientes conocidas para puertos sin flecha, parámetros escalares, selector de conexión de reciclo, y resultado del pool tras resolver.
- **Decisión de alcance deliberada**: en esta versión, solo los puertos de tipo Corriente se conectan con flechas — los parámetros escalares (R, recuperaciones, factor_P, etc.) siempre se escriben a mano en el panel, aunque el backend técnicamente permitiría conectarlos igual (mismo espacio de nombres calificado). Simplifica la UI v1 sin cerrar la puerta a extenderlo después.
- **Hallazgo real de UX, encontrado probando el contrato contra el backend antes de confiar en la UI**: el default inicial de "entrada extra" para una columna (`x_D,x_B,R`) le faltaba `q` para McCabe-Thiele — sin `q`, el bloque queda con 2 incógnitas (`q` y `N`) en vez de 1 y nunca se dispara (`completo=False`, sin error explícito). Verificado reproduciendo el payload exacto que construiría la UI contra `/flowsheet/resolver`: con `q` ausente falla en silencio (`N=None`), con `q` incluido resuelve exacto (`N=9.9999...`). Corregido el default y agregado texto de ayuda en el panel (`PISTAS_POOL_POR_METODO`) que aclara que `q` es variable de pool SOLO en `mccabe_thiele` -- en `ponchon_savarit`/`fug` es un parámetro fijo de construcción, no algo que se da/resuelve en el pool.
- `npm run build` compila sin errores de TypeScript (tuvo que agregarse un índice `Record<string,unknown>` a `DatosNodo` para satisfacer el tipo `Node` de React Flow).
- **Limitación honesta**: no se probó la interactividad real de arrastrar nodos/flechas en un navegador (sin herramienta de automatización de navegador disponible) — solo que el build compila y que el contrato JSON que la UI construye coincide exactamente con lo que el backend espera (verificado replicando ese payload directamente contra el servidor real). La confirmación de que arrastrar/soltar se siente bien queda para que el usuario la haga.

### ✅ Segunda pasada de UI: tema oscuro, menús contextuales, detección de reciclo, modo ELV (Completado)
- **Bug visual real, visto en un screenshot del usuario**: el CSS base de Next cambia `--foreground` según `prefers-color-scheme`, y como su sistema está en modo oscuro, los nodos (que usaban fondos claros `bg-blue-50` etc.) quedaban con texto casi blanco sobre fondo casi blanco — ilegibles. El panel lateral también era invisible (texto oscuro sobre fondo oscuro). Se confirmó que el panel SÍ estaba en el DOM (buscando su texto en el HTML servido) antes de tocar nada: era contraste, no lógica. Corregido fijando tema oscuro explícito en `layout.tsx` y colores explícitos en los nodos, y cambiando el layout del flowsheet de flex a `grid-cols-[1fr_380px]` (determinista).
- **Menú contextual (clic derecho)**: sobre un nodo → duplicar / eliminar; sobre una conexión → marcar-o-quitar reciclo / eliminar conexión. Más tecla `Supr` (deliberadamente NO `Backspace`, para no borrar nodos mientras se escribe en los campos del panel).
- **Detección automática de recirculación** (`frontend/app/flowsheet/grafo.ts`): DFS que devuelve las aristas de retroceso (*back edges*) del grafo dirigido — exactamente las candidatas a romper. Resuelve un problema de UX real: antes, si había un ciclo y no se rompía ninguna conexión, el backend devolvía `completo=false` **sin decir por qué** (ninguna operación del lazo puede dispararse). Ahora se avisa antes de resolver, se sugiere cuál romper, y las conexiones se pintan según su papel (ámbar animada = reciclo roto; roja = ciclo detectado todavía sin romper).
- **Modo Termodinámica / ELV** (`backend/nucleo_elv.py` + `/elv/binario` + `frontend/app/elv/`): barre la composición resolviendo el punto de burbuja completo en cada punto (mismo cálculo que ya hacía `EvaluadorMcCabeThiele` en su constructor, ahora devuelto como datos) y grafica y–x y T–x–y con Recharts. Extremos exactos vía `Tb` puro, no UNIFAC (misma razón ya documentada en `ponchon_savarit.py`).
  - **Validación fuerte, contra literatura**: benceno/tolueno → sin azeótropo (correcto, casi ideal), Tb 353.22 K / 383.75 K. Etanol/agua → azeótropo detectado en **x = 0.8928, T = 351.31 K (78.16 °C)**; el valor de literatura es x ≈ 0.894 a 78.15 °C. Coincidencia a ~0.1% — valida de paso la cadena UNIFAC + punto de burbuja completa.
  - La detección de azeótropo aquí es una interpolación del cruce de y(x) con la diagonal (suficiente para señalarlo en un diagrama); el cálculo riguroso sigue en `core/analisis_nodos.py`, sin exponer.
- **Barra de navegación por modos** (`app/components/NavBar.tsx`): Columna / Flowsheet / Termodinámica, con "Destilación reactiva — pendiente" marcado explícitamente en la barra.
- **Decisión de alcance**: no se expuso destilación reactiva (RCM, azeótropos reactivos) todavía. Existe y está validada en el núcleo (`core/topology.py`, `core/analisis_nodos.py`, Fase 2) pero su superficie de entrada es mucho mayor (estequiometría ν, parámetros de Arrhenius A/Ea, número de Damköhler, componente de referencia k) y `plot_ternary` dibuja con matplotlib en vez de devolver datos — necesita su propio diseño de API, no un endpoint más.

### ✅ Configuración global de componentes (estilo ASPEN) + diagnósticos claros (Completado)
- **Bug de raíz, reportado por el usuario con un screenshot** (`'water' is not in list`): cada nodo del flowsheet Y cada corriente declaraban su PROPIA lista de componentes. Al poner `water,toluene` en la columna pero dejar `n-butane` en la corriente, `Corriente.fraccion(nombres[0])` hacía `["n-butane"].index("water")` → `ValueError` de Python sin ningún contexto. El usuario diagnosticó correctamente la solución: una lista global, definida una vez, como en ASPEN.
- **Arreglo en dos niveles, no solo en la UI**:
  - *Núcleo* (`ColumnaDestilacion.resolver_desde_feed`): valida que los componentes de la corriente coincidan **en contenido y orden** con los de la columna, con un mensaje que explica la causa. Una API puede llamarse mal aunque la UI esté bien; el error tenía que ser claro en el nivel donde ocurre.
  - *Frontend* (`app/components/ConfiguracionProvider.tsx` + `app/configuracion/`): lista global de componentes + modelo termodinámico, persistida en `localStorage`, consumida por todo el flowsheet. Se eliminaron los campos `nombres` de nodos y corrientes: **estructuralmente ya no pueden divergir**.
- **Se eliminó otra fuente del mismo tipo de error**: `z_F_fug` ya no se escribe a mano — se deriva de la corriente de alimentación de esa misma columna. Pedirla por separado era otra vía para que dos composiciones divergieran en silencio.
- **Selector de componentes con validación real** (`/componentes/buscar`, vía `chemicals.search_chemical`): resuelve nombre / fórmula / CAS (acepta "etanol", "C6H6", "64-17-5") y comprueba **dos cosas distintas**: que el compuesto exista, y que tenga **grupos UNIFAC**. Hay compuestos perfectamente reales (amoníaco, CO₂, N₂, H₂) cuyo `UNIFAC_groups` es `None`: sin este chequeo el fallo aparecía mucho después, enterrado en un cálculo de γ. Verificado: water/etanol/C6H6 → aptos; ammonia → encontrado pero no apto, con explicación; xyzabc → no encontrado.
- **Diagnóstico de azeótropo en el escalonamiento** (`EvaluadorMcCabeThiele.azeotropo_entre` + captura del `ValueError` de `brentq`): al probar agua/tolueno, el fallo era `f(a) and f(b) must have different signs` — un mensaje de scipy que no dice nada. La causa real: **hay un azeótropo en x=0.574 entre x_B y x_D**, y ninguna cantidad de etapas o reflujo cruza un azeótropo. Ahora el error lo dice y sugiere qué hacer (quedarse de un lado, o cambiar de técnica). **Doble validación independiente**: el azeótropo detectado por este diagnóstico (0.5742) coincide con el que detecta el endpoint ELV por otro camino (0.5740). Verificado también el caso positivo: agua/tolueno de un solo lado del azeótropo (x_B=0.05 → x_D=0.50) sí resuelve, N=0.908.
- **Diagrama de resultados** (`DiagramaMcCabeThiele`): `/columna/resolver` ahora devuelve los datos de la construcción gráfica (curva de equilibrio, escalonamiento, rectas de operación, línea q) y el frontend la dibuja con Recharts. Son datos, no una imagen — el escalonamiento ya lo calculaba `calcular_escalones`, solo hacía falta devolverlo.
- **Renombrado a "Simulador de Procesos"**: el usuario señaló que el proyecto es de ingeniería química, no solo destilación. El catálogo de operaciones del flowsheet se agrupó por familia (Separación / Mezcla / Transporte) con "Reactor — pendiente" visible, y la extensión está documentada: agregar una operación es una entrada en el catálogo del frontend + un constructor en `_CONSTRUCTORES` (`backend/nucleo_flowsheet.py`); el motor de resolución no cambia.

### ✅ Refactor de fondo: la CORRIENTE como elemento de primera clase (Completado)
- **El problema no era la interfaz.** El usuario pidió poder "introducir CUALQUIER VARIABLE hasta que se cumplan los grados de libertad" y resolver "al revés, teniendo las variables de salida, calcular las de entrada". Con el modelo anterior eso era **imposible por construcción**: un puerto guardaba un objeto `Corriente` ENTERO como valor atómico del pool (o conocías la corriente completa o nada), lo que obligaba a envolver cada operación como bloque **no invertible** ("solo se dispara con TODAS sus entradas dadas"). Ninguna mejora de UI lo habría arreglado.
- **Hallazgo clave que hizo el refactor barato**: la matemática **ya era invertible** — `BalanceMateriaGlobal` resuelve cualquier 2 de 6 variables, `SolucionadorMcCabeThiele` cualquier 1 de 5. La envoltura del flowsheet era la que tiraba esa flexibilidad. **No se reescribió ningún método matemático.**
- **`core/diagrama_corrientes.py`** (nuevo, sustituye a `diagrama_flujo.py` para este uso): cada corriente aporta variables ESCALARES al pool (`s1.F`, `s1.T`, `s1.P`, `s1.x0`…), y cada operación aporta sus bloques ya existentes **renombrados** para apuntar a las variables de sus corrientes.
  - **`renombrar_bloque(bloque, mapa)`** en `core/orquestador.py`: el mecanismo que lo permite. Es una biyección de nombres, así que `puede_resolver` (que cuenta incógnitas) sigue significando lo mismo. Detecta y rechaza mapas que colapsen dos variables en una.
  - **Conectar dos operaciones ya no necesita "cables"**: comparten la misma corriente, o sea literalmente las mismas variables del pool.
  - Bloque de **cierre de composición** por corriente (`Σxᵢ = 1`, invertible): por eso basta dar `x0` en un binario, `x1` sale solo.
- **`BalanceMateriaGlobal` generalizado** de "exactamente 2 incógnitas" a "hasta 2": con 1 incógnita el sistema queda sobre-determinado y se resuelve por mínimos cuadrados **exigiendo residuo cero** (si no lo cumple, los datos son mutuamente inconsistentes — información útil, no un fallo). El camino de 2 incógnitas (ya validado con `hybr`) se dejó intacto a propósito.
- **Relaciones físicas que faltaban** y dejaban variables colgando: P de todas las corrientes de una columna = P de operación (no se modela caída de presión), y T de la alimentación = punto de burbuja **cuando q=1**. Para otros q la relación existe pero necesita entalpías; se deja sin determinar a propósito en vez de inventar un valor.
- **Validado en `tests/validar_diagrama_corrientes.py`** — las cuatro capacidades que el modelo viejo no tenía:
  1. Hacia adelante (alimentación → productos): D=38.8889, B=61.1111, N=10.
  2. **Hacia atrás (productos → alimentación), con las MISMAS ecuaciones y sin declarar nada distinto**: recupera F=100.0000 y z_F=0.4000 exactos.
  3. Direcciones mezcladas (N dado como objetivo, R como incógnita): R=3.059734 vs 3.059738 de referencia.
  4. Diagnóstico con datos insuficientes: señala los bloques bloqueados y **qué variables los desbloquearían**, en vez de devolver un `completo=false` mudo.
- **Interfaz reconstruida** (`app/flowsheet/`): el usuario reportó que el panel lateral único era "muy muy confuso".
  - Una operación **nunca nace suelta**: al agregar una columna se crean y conectan sus tres corrientes (alimentación, destilado, fondos) aunque no haya nada más en el diagrama — así se pueden escribir propiedades desde el primer momento.
  - **Las corrientes son nodos** que muestran sus variables encima, con código de color: verde = dado por ti, azul = calculado, `?` = falta.
  - **Menú por elemento**: al hacer clic en un nodo se abre un panel flotante junto a él (no en la barra lateral) con sus variables; se escribe lo que se conozca y se deja en blanco lo que deba calcularse.
  - **Barra de guía** abajo: cuántas variables faltan y, por cada bloque bloqueado, **qué variables concretas lo desbloquearían**.
- **Regresión conocida y aceptada**: el desgarro de reciclos (sustitución sucesiva) existía en el modelo de cables y **todavía no está reimplementado** en el modelo de corrientes. Un ciclo real hoy termina como bloques bloqueados en el diagnóstico, no como un lazo convergido. Es la siguiente pieza.

### ✅ Verificación real en navegador (cierra un hueco que costó dos bugs)
- **Bug reportado con screenshot: el canvas salía completamente vacío.** React Flow lo decía en su propio log — *"The parent container needs a width and a height"*. Causa: `body` tenía `min-h-full` (altura **mínima**, no definida) y una cadena de `flex-1` no puede resolver `height: 100%` contra eso. Corregido con `h-screen` en `body` (altura definida) + `grid-rows-[1fr_auto]` en el flowsheet, para que la fila del canvas tenga altura definida. La pista clave: **tampoco se veían los controles ni el minimapa**, lo que descartaba "los nodos no se crean" y apuntaba al contenedor.
- **Dos bugs seguidos solo detectables abriendo la página** (panel invisible por contraste, canvas de altura cero) mostraron que "compila sin errores de TypeScript" no verifica nada de lo que el usuario ve. Se instaló `puppeteer-core` (sin descargar navegador: usa el Edge del sistema) y se escribió **`frontend/verificar_ui.mjs`**, que abre la app de verdad y comprueba:
  1. Que el canvas tenga ancho y alto reales (el bug de arriba).
  2. Que agregar una columna cree 4 nodos (operación + 3 corrientes) y 3 aristas.
  3. Que ningún nodo tenga texto del color de su fondo (el bug de contraste).
  4. Que al hacer clic en una corriente se abra su panel de propiedades.
  5. **El flujo completo**: escribir valores en tres nodos distintos, pulsar Resolver, y comprobar que sale "Resuelto por completo" y que los valores calculados aparecen sobre las corrientes.
  6. Que las otras rutas rendericen contenido.
  Además captura pantallazos, que es lo que permitió detectar a ojo tres problemas que ninguna aserción cubría: el panel tapaba el nodo que se editaba, los nombres largos se recortaban (`V_barr…`, `alimenta…`) y el indicador de desarrollo de Next tapaba el botón Resolver.
- Correcciones a partir de esas capturas: panel anclado al **rectángulo del nodo** (a su derecha, o a su izquierda si no cabe) en vez de al punto del clic; nodos de ancho fijo con nombres de puerto abreviados en pantalla (`alim`/`dest`) conservando los nombres reales hacia el backend; controles del canvas movidos arriba a la derecha; `devIndicators: false`.
- **Resultado verificado de punta a punta en navegador**: dando F=100, x=0.40 en la alimentación, x=0.95 y x=0.05 en los productos y q=1, R=3.06 en la columna, el diagrama resuelve completo y muestra sobre las corrientes N=10.000, D=38.889, B=61.111, T_D=354.259 K, T_B=381.540 K — los mismos valores validados en Python. `x toluene = 0.6000` aparece sin haberlo escrito (bloque de cierre de composición).

### ✅ Bug grave: datos incompatibles aceptados en silencio (Corregido)
- **Reportado por el usuario con un screenshot** ("hay cosas que no cuadran aquí"). Sus datos: F=100, z_F=0.5, D=20, x_D=0.8, B=80, x_B=0.1. El balance **total** cierra (100=20+80) pero el de **componente** no: 100×0.5 = 50 frente a 20×0.8 + 80×0.1 = 24 — **26 mol/s de benceno apareciendo de la nada**. El simulador respondía `completo: True`, sin una sola queja.
- **Causa raíz en el orquestador**: el bucle de resolución hace `if len(incognitas) == 0: continue` — los bloques sin incógnitas se saltan porque "no hay nada que resolver". Consecuencia no prevista: si el usuario da **todas** las variables de una ecuación, esa ecuación **nunca se evalúa** y nadie comprueba que los datos la cumplan. Sobre-especificar con números imposibles pasaba desapercibido.
- **`verificar_consistencia(bloques, pool)`** en `core/orquestador.py`: por cada bloque completamente determinado, "olvida" una variable, la recalcula con las demás y la compara con el valor dado. Es genérico — sirve para cualquier bloque, invertible o no, porque reutiliza el propio `resolver_fn` del bloque. Prefiere olvidar una variable de **salida**, para que los bloques no invertibles (que exigen todas sus entradas) también se puedan comprobar.
- Verificado con los datos exactos del usuario: detecta las **tres** ecuaciones violadas (balance de materia, McCabe-Thiele y cargas térmicas) con mensajes concretos del tipo *"diste s1.F=100, pero el resto de los datos implica s1.F=89.6"*. El 89.6 se comprobó a mano: mínimos cuadrados sobre `[F−100, 0.5F−24]` da 1.25F = 112 → F = 89.6. ✓

### ✅ Interfaz: tres modos separados, panel acoplado y reporte (Completado)
- El usuario pidió explícitamente: panel **a un lado** en vez de flotando sobre el diagrama; **flowsheet de resultados separado del editable**, porque la leyenda "dado por ti / calculado" en una sola vista resultaba confusa; una **guía afinada** de qué variables faltan; y un **reporte** de todas las corrientes y equipos.
- **Modos `Editar` / `Resultados` / `Reporte`**, con énfasis invertido a propósito:
  - *Editar*: resalta en **ámbar lo que falta** por introducir (la tarea de ahora); lo ya calculado se atenúa.
  - *Resultados*: resalta en **azul lo calculado** (la información nueva); lo que diste se atenúa porque ya lo conocías.
  - Al pulsar Resolver se pasa solo de `Editar` a `Resultados` — es el cambio de tarea natural.
- **Panel lateral acoplado** (340 px, derecha): editor del elemento seleccionado, o —si no hay nada seleccionado— la guía.
- **Guía afinada**: en vez de listar ecuaciones bloqueadas sin más, cuenta **en cuántas ecuaciones bloqueadas aparece cada variable faltante** y ofrece primero las que desbloquean más ("desbloquea 3"); cada sugerencia es un botón que selecciona ese elemento.
- **Modo Reporte**: tabla de corrientes al estilo de un simulador (una columna por corriente, una fila por variable) + bloque por equipo + lista de ecuaciones violadas, con leyenda de colores.
- Las incompatibilidades se marcan en los tres sitios: barra superior, panel lateral, borde rojo y `⚠` sobre la variable concreta en el nodo, y en rojo en la tabla del reporte.
- **`frontend/verificar_incoherencias.mjs`**: segundo script de navegador que reproduce el caso del usuario end-to-end y comprueba que la UI avisa, nombra la ecuación, marca el nodo y lo refleja en el reporte. **Hallazgo del propio test**: su primera versión daba un falso fallo ("los nodos no se marcan") porque inspeccionaba el color calculado del borde del elemento equivocado; la captura mostró que el nodo **sí** estaba en rojo. Se cambió a buscar el marcador semántico `⚠` en vez de colores — comprobar estilos calculados es frágil.

### ✅ Unidades, grados de libertad en vivo, energía separable y gráficas en el reporte (Completado)
- **Balance de materia y de energía, separables** — el usuario intuyó que algo no cuadraba ahí, y tenía razón: `agregar_columna_binaria` ya tenía el parámetro `con_cargas_termicas`, pero **nunca se expuso**. El balance energético se colaba siempre, inflando las variables que "faltan" y obligando a lidiar con `Q_c`/`Q_R`/`V_barra` aunque solo se quisiera el balance másico. Ahora es una casilla por columna; apagada, esas variables **no existen** en el diagrama (ni se muestran ni cuentan para los grados de libertad).
- **Contador de grados de libertad en tiempo real** (`/diagrama/grados-libertad`, sin resolver nada): `GL = incógnitas − ecuaciones`. Requirió añadir `n_ecuaciones` a `BloqueEcuaciones`, y eso destapó **redundancias reales que yo había introducido**: el bloque de punto de burbuja escribía también `P`, que ya fijaba el bloque de presión de operación — dos ecuaciones para la misma variable. Con ellas, el conteo daba `GL = −3` ("sobran 3 datos") en un caso que resuelve exacto. Eliminadas: ahora da 0 cuando está justo especificado, +1 si falta un dato y −1 si sobra, con y sin balance de energía.
- **Unidades por variable, cambiables en cualquier momento**: el backend genera la tabla con **pint** (`/unidades`) en forma afín `valor_SI = valor·factor + desplazamiento`, y el frontend convierte en local — así no hay ida y vuelta al servidor por cada tecla, pero pint sigue siendo la única fuente de verdad y el núcleo sigue siendo SI puro. El desplazamiento es lo que hace funcionar las temperaturas (verificado: 100 °C → 373.15 K, 212 °F → 373.15 K, 360 kmol/h → 100 mol/s). Flujo molar, temperatura, presión, potencia y energía molar tienen opciones; lo adimensional (fracciones, q, R, N) se marca como tal.
- **Sin corrientes automáticas**: agregar un equipo ya no crea ni conecta sus corrientes — el usuario lo encontró tedioso porque obligaba a borrar las que no quería. Ahora la operación nace sola y las corrientes se agregan y conectan arrastrando.
- **Gráficas dentro del reporte**: construcción de McCabe-Thiele por columna resuelta (el backend la devuelve como datos en `/diagrama/resolver`) más el diagrama ELV del par de componentes.
- **Dos bugs reales que solo destapó la verificación en navegador**:
  1. Las corrientes nuevas se **apilaban unas sobre otras** (30 px de separación para nodos de ~150 px de alto) y además caían **fuera del encuadre** (coordenadas negativas), con lo que sus puertos eran inalcanzables para conectar. Corregido con colocación en rejilla holgada + reencuadre automático al agregar.
  2. **Falso fallo del propio test** (otra vez): el helper de arrastre buscaba `.react-flow__handle-source`, que no existe — React Flow pone la posición en la clase (`handle-left`/`handle-right`) y el papel en una clase suelta (`source`/`target`). El arrastre funcionaba; el test no sabía encontrar los puertos.
- Verificado end-to-end en navegador: agregar columna sola → agregar 3 corrientes → conectarlas arrastrando → cambiar T a °C → escribir datos → `GL = 0 · exactamente especificado` **antes** de resolver → resolver → `T = 95.427 °C` en la corriente (368.577 K convertidos correctamente) → reporte con 2 gráficas.

### ✅ Contradicción aparente en los avisos, y caudales en base másica (Completado)
- **"Faltan 14 variables" junto a "GL = −1 · sobran datos"**, reportado con screenshot. **Los dos números eran correctos**: el usuario había dado `x benceno = 0.5` Y `x tolueno = 0.5` en la misma corriente (el cierre de composición solo necesita una) y además `P` de la alimentación (que la fija la presión de operación de la columna), pero **no** había dado `q` ni `R`. Es decir: especificación **mal distribuida** — sobra en unas ecuaciones y falta en otras. El conteo global de grados de libertad es un agregado y **no puede ver la distribución**; el error fue mío al presentar dos indicadores sueltos que se leían como contradictorios.
- **`DiagramaCorrientes.redundancias()`**: dice DÓNDE sobran datos, ecuación por ecuación. Regla general: una ecuación con *n* variables necesita *n − n_ecuaciones* datos; lo que se dé por encima es redundante (no necesariamente erróneo — se comprobará por consistencia en vez de calcularse). Con los datos del screenshot señala exactamente los dos sitios: `Cierre de composicion (s1)` y `Presion de operacion (s1)`.
- **Un solo mensaje coherente** en la barra (componente `Estado`), que prioriza: incompatibilidades → "datos mal repartidos: sobran N donde no hacen falta y quedan M variables sin determinar" → completo → faltan/sobran. Y el panel lateral lista las ecuaciones con datos de más.
- **Caudales en base másica (kg/h, t/h, lb/h…)**, con una diferencia de fondo que se verificó antes de diseñarla: **kg ↔ mol NO es una conversión afín**. Depende de la masa molar de la MEZCLA, o sea de la composición de cada corriente: 1 kg/s son 11.557 mol/s con x_benceno=0.4 pero 12.577 mol/s con x=0.9. Por eso `aSI`/`desdeSI` aceptan la masa molar y **devuelven `null` cuando hace falta y no se conoce** — mejor no mostrar nada que convertir con una composición inventada; la UI lo dice explícitamente ("en base másica hace falta la composición completa de esta corriente").
- **Bug real encontrado al probarlo**: los componentes **por defecto** (`benzene`, `toluene`) no traían `MW`, solo los agregados desde el buscador — así que la conversión másica quedaba desactivada **en silencio**. Corregido, y añadido un relleno automático: una configuración guardada en `localStorage` antes de que existieran estas unidades tampoco tiene `MW`, así que al cargar se piden al backend las que falten.
- **Verificación numérica, no solo de que "no se queje"** (`frontend/verificar_masa_numerica.mjs`): intercepta lo que el frontend manda al backend. Con benceno/tolueno 50/50 (MW mezcla = 85.125 g/mol), escribir **30645 kg/h** en la interfaz manda **exactamente 100 mol/s** al núcleo. ✓
### ✅ Bug del balance silencioso + caudal másico como variable (Completado)
- **Reportado con screenshot: "el flujo de alimentación no coincide con los flujos de salida".** Tenía razón. Sus datos eran **físicamente imposibles**: con z_F=0.5, x_D=0.8, x_B=0.3, el balance por componente obliga a que B/D = 1.5 en base molar, pero dar 50 kg/h en ambos productos da B/D = 0.92. Las dos ecuaciones piden alimentaciones distintas (1186.55 vs 1329.86 mol/h).
- **El bug era mío, y grave**: al generalizar `BalanceMateriaGlobal` para aceptar 1 incógnita, uso mínimos cuadrados, calculo el residuo, lo guardo en `convergio`… y `bloque_balance_materia` **lo ignoraba**. Devolvía el mejor ajuste (103.4 kg/h) como si fuera una solución, con `inconsistencias: 0`. Un sistema sobre-determinado siempre devuelve *algo* por mínimos cuadrados; si el residuo no es cero, ese algo no cumple **ninguna** de las dos ecuaciones. Corregido: con ≤1 incógnita se exige residuo ≈ 0 (tolerancia relativa a la escala de los caudales) y si no, se lanza un error que dice qué pide cada ecuación.
- **`Orquestador` ahora captura las excepciones por bloque** en vez de abortar toda la resolución: un bloque que no se puede resolver se anota y el resto sigue. Esos errores se reportan como inconsistencias, así que el usuario ve el motivo en vez de un 500.
- **Caudal másico como VARIABLE, no como unidad** (`_bloque_caudal_masico`): el usuario sugirió usar `thermo` para convertir mol↔kg. Se verificó primero por qué es distinto del resto: **no es una conversión afín** — 1 kg/s son 11.557 mol/s con x_benceno=0.4 pero 12.577 con x=0.9, porque depende de la composición de cada corriente. Tratarlo como "unidad de F" obligaba a conocer la composición de antemano y fallaba en silencio si no se conocía. Ahora cada corriente tiene `m` como variable propia ligada por `m = F · MW_mezcla(x)/1000`, con las MW sacadas de `thermo` (`Chemical.MW`) en el backend. Aporta 1 variable y 1 ecuación, así que **no cambia los grados de libertad**, y se resuelve en ambas direcciones: verificado que dar 30.645 kg/h da 0.1 mol/s y que dar 100 mol/s da 30645.05 kg/h.
  - Efecto secundario bueno: el frontend se simplificó — desapareció todo el caso especial de "esta unidad necesita masa molar", y las conversiones volvieron a ser afines puras.
- **Bug de visualización encontrado al probarlo**: `formatear` usaba `toFixed(3)` para todo lo menor de 10000, así que un caudal másico de 0.0085125 kg/s se mostraba como **"0.009"**, perdiendo toda la precisión. Ahora los valores pequeños también usan cifras significativas.
- **Los scripts de navegador atraparon dos falsos fallos propios** (un regex que no cruzaba saltos de línea, y una preferencia de unidad que un bloque anterior del test dejaba guardada en `localStorage`) y uno real (`verificar_incoherencias.mjs` estaba escrito para el flujo antiguo en que las operaciones creaban sus corrientes solas). Los tres corregidos.

### ✅ Corrección: UNA sola variable de caudal, con unidad por corriente (Completado)
- **Error de diseño mío, señalado por el usuario**: al hacer el caudal másico una variable propia (`m`), la interfaz pasó a mostrar `F` **y** `m` en cada corriente. Su objeción es correcta: el caudal es **una sola magnitud física**; expresarlo en moles o en masa es cuestión de la unidad, y la conversión debe ser un detalle interno. Exponer dos variables trasladaba al usuario un problema de implementación.
- **Rehecho**: una sola `F` por corriente. Dar el caudal en masa no es un valor fijo sino una **restricción** — `F · MW_mezcla(x)/1000 = kg/s` — que el backend añade como bloque (`fijar_caudal_masico`). Así sigue siendo la misma variable y la conversión espera, si hace falta, a que se conozca la composición. Cuenta como una ecuación más, o sea exactamente igual que dar el caudal en moles: los grados de libertad no cambian (verificado: GL = 0 en ambos casos).
- **Unidades por corriente**: la preferencia se guarda con la clave completa (`s1.F`) y cae de vuelta al nombre de la variable. Así una corriente puede ir en kg/h y otra en mol/s **a la vez**, que es justo lo que pidió.
- Para MOSTRAR un caudal en masa hace falta la MW de la mezcla: la calcula el backend con las MW de `thermo` y la devuelve por corriente (`masas_molares_mezcla`), así el frontend no tiene que llevar masas molares.
- **Verificado en navegador**: s1 en kg/h y s2 en mol/s simultáneamente; el caudal másico viaja en `caudales_masicos` (kg/s) y **no** como un `s1.F` convertido a ciegas; 30645 kg/h con MW 85.125 g/mol dan 100 mol/s, y con x_D=0.95 / x_B=0.05 el destilado sale 50 mol/s exacto.
- **Bug de proceso, no de código**: la primera pasada del test falló porque parcheé el backend *después* de arrancarlo, así que el servidor seguía sin el campo `magnitud` y el frontend mandaba kg/s como si fueran mol/s. Reiniciar el backend tras tocarlo, antes de dar por buena una verificación.

### ✅ El panel "Dónde sobran datos" no veía lo que se resolvía por caminos indirectos (Corregido)
- **Reportado por el usuario, con razón**: dio F de s1 y F de s3 (en kg/h) más las tres composiciones y R/q de la columna. El sistema decía "sobran datos (GL=-6)" pero el panel solo listaba redundancias inofensivas (dar x0 y x1 a la vez, dar P) — **nunca mencionaba el balance de materia**, que era el bloque real y roto. El usuario no entendía por qué borrar `s2.F` (que ni aparecía en la lista) arreglaba todo.
- **Causa exacta, verificada con los números del caso**: `redundancias()` comparaba contra `valores_dados` (lo que el usuario escribe a mano), pero `s1.F` y `s3.F` no viven ahí — llegan por un camino indirecto (caudal en masa + composición completa, vía el bloque "Caudal másico dado"). Desde el punto de vista de `valores_dados`, el balance de materia parecía **falto** de datos (solo veía 3 composiciones escritas), cuando en realidad estaba **sobrado por 1** (F y B ya resueltos por otro camino, más x_D encima). El número global (GL=-6) siempre fue correcto — el desglose por bloque no.
- **Corregido resolviendo una vez** (el `Orquestador` ya tolera bloques que fallan) y comparando contra el **pool resultante**, no la entrada cruda — así una variable cuenta como "conocida" tanto si el usuario la escribió como si otro bloque ya la determinó.
- **Efecto secundario que casi se cuela**: con esa sola corrección, cada bloque empezaba a contar **su propia salida recién calculada** como si fuera un dato de más — cualquier bloque que terminara de resolverse aparecía como "redundante" (falsos positivos en McCabe-Thiele, punto de burbuja). Se verificó explícitamente antes de dar el fix por bueno, y se corrigió excluyendo, para cada bloque, lo que **él mismo** acaba de resolver (usando `resueltos_por` del resultado) — solo cuenta lo que llega de fuera.
- **Verificado con los números exactos del caso**: el panel ahora muestra `col1: balance de materia — diste s1.F, s3.F, s1.x0, s2.x0, s3.x0 · necesita 4`, señalando el bloque y las variables reales. Sin dar `s2.x0`, el mismo caso resuelve solo (`s2.F = 0.173247 mol/s` por balance), confirmando que ese era el dato de más.

### ✅ Ponchon-Savarit: mensaje críptico de scipy al dar un Qc_D bajo el mínimo (Corregido)
- **Reportado con dos screenshots**: al resolver Ponchon-Savarit sin dar `Qc_D`, el panel avisaba correctamente "sobran 3 datos, quedan 2 sin determinar" (las 3 son dar x0 y x1 a la vez en cada corriente — redundancia real pero inofensiva, como en los casos anteriores; los 2 que faltan eran `Qc_D` y `N`, correcto). Pero al dar `Qc_D=10000 J/mol` para completarlo, el error era `f(a) and f(b) must have different signs` — un mensaje de scipy que no dice nada, la misma clase de bug que ya se había corregido para McCabe-Thiele con `R<=R_min`.
- **Causa verificada con los números exactos**: `calcular_Qc_D_min` (búsqueda por bisección, ya existía) da **Qc_D_min≈60,230 J/mol** para este caso (z_F=0.5, x_D=0.9, x_B=0.1) — el usuario probó 10,000, muy por debajo. `calcular_escalones` no tenía ningún guardia antes de sus llamadas a `brentq`, así que un `Qc_D` insuficiente producía un pinch y el error crudo de scipy escapaba sin traducir.
- **Corregido envolviendo el escalonamiento en un try/except** que, solo si falla, calcula `Qc_D_min` (numéricamente, sin fórmula cerrada — a diferencia de `R_min` en McCabe-Thiele) y da un mensaje claro con el valor real. Verificado: con Qc_D=10000 da *"Qc_D=10000 está por debajo del mínimo requerido (Qc_D_min≈60229.9): produce un pinch..."*; con Qc_D=1.3×Qc_D_min sigue resolviendo normal (N=8.7504).
- **Cuidado real al implementarlo**: `calcular_Qc_D_min` internamente llama a `calcular_escalones` ~60 veces (bisección) para probar factibilidad. Si esas llamadas también dispararan el diagnóstico al fallar, cada una lanzaría su propia búsqueda anidada de `Qc_D_min` — explosión combinatoria. Se añadió un parámetro `_diagnosticar` (default `True`) que `calcular_Qc_D_min` pasa en `False` en sus propias llamadas internas, para que el diagnóstico solo se pague en el camino de error que de verdad lo necesita (el que ve el usuario), no en cada sondeo de la búsqueda.

### ✅ "Todas las variables son adimensionales" (Corregido — causa: backend caído + mal mensaje)
- **Reportado por el usuario**: el panel de la corriente mostraba `F`, `T`, `P` y las composiciones todas etiquetadas **"adim."**, sin selectores de unidad. Nada de esto era un cambio de diseño: **yo maté el backend** en el comando de limpieza del arreglo anterior (`Stop-Process` sobre el puerto 8000) y no lo volví a levantar. Sin `GET /unidades`, `useUnidades` hace `setTabla(null)`, `magnitudesDe()` devuelve `[]` para toda clave y `PanelLateral` caía en su rama `adim.` para **todas** las filas.
- **Verificado**: con el backend arriba otra vez, `/unidades` devuelve la forma correcta (`variables.F == ["flujo_molar","flujo_masico"]`, 9 unidades para F con su `magnitud`) y los selectores vuelven. La suite `verificar_unidades.mjs` pasa entera: s1 en kg/h y s2 en mol/s a la vez, 30645 kg/h → 100 mol/s → destilado 50 mol/s.
- **El bug de verdad no era el servidor caído, sino que la UI mintiera sobre ello**: "adim." es una **afirmación física** (esta variable no tiene unidades) y se estaba usando como comodín para "no tengo la tabla". Un caudal másico presentado como número puro es justo la clase de error silencioso que puede arrastrarse a un cálculo. Corregido distinguiendo los dos casos con el `listo` que `useUnidades` ya exponía: si la tabla no cargó, la fila dice **"¿unidad?"** en ámbar y la barra superior avisa *"sin conexión con el servidor: no se cargaron las unidades"*. `adim.` queda solo para lo que de verdad es adimensional (x, q, R, N).
- **Verificado el modo de fallo, no solo el camino feliz**: test de navegador que aborta únicamente las peticiones a `/unidades` y comprueba que aparece el aviso y el "¿unidad?", y que **no** aparece "adim." en F/T/P.
- **Reincidencia de una lección ya escrita arriba**: "reiniciar el backend tras tocarlo". Ampliada: **no dejar el backend caído al terminar una tarea** — el usuario continúa en la misma UI y hereda un estado roto que no tiene forma de atribuir a la limpieza.

### ✅ Ponchon-Savarit cerrado: balance de energía real + gráfica de etapas (Completado)
- **El checkbox "incluir balance de energía" era decorativo en Ponchon-Savarit**: se dibujaba, pero `con_cargas_termicas` solo se consultaba dentro de la rama de McCabe-Thiele. Encenderlo o apagarlo no cambiaba absolutamente nada.
- **Corregido con un bloque propio** (`bloque_cargas_termicas_ps`), NO reutilizando el de McCabe-Thiele: ese usa R y flujo molar constante, y aquí la energía sale de la propia construcción entálpica, que es la ventaja del método. Da `Q_c = Qc_D·D`, `Q_R = QR_B·B` (con `QR_B` atado a `Qc_D` por la colinealidad de los polos, o sea por el balance global) y recupera el reflujo clásico vía `Qc_D = (R+1)·(H_V(x_D) − H_L(x_D))`, deducido del condensador total.
- **Verificado contra el balance de energía global** `F·H_F + Q_R = D·H_D + B·H_B + Q_c`: cierra con **error relativo 0.000e+00**. Y `Qc_D = (R+1)·(H_V−H_L)` se comprueba aparte, a 1e-9.
- **Efecto colateral que destapó el test**: `col1.q` y `s1.T` quedaban *siempre* "sin determinar" — eran los "2 sin determinar" del screenshot del usuario. Causa: en Ponchon-Savarit `q` se pasaba al solver como parámetro fijo pero **nunca entraba al pool**, así que la T de alimentación nunca se podía calcular en cascada. Publicarlo lo arregla sin mover los grados de libertad (la variable ya estaba declarada por el bloque de T de alimentación; solo le faltaba su ecuación). Ahora `s1.T = 365.52 K`, su punto de burbuja, en vez del 273.15 rancio.
- **Gráfica H–x añadida**: curvas de saturación líquido/vapor, escalera de etapas, rectas de reparto, rectas operativas desde el polo activo, los polos Δ_D/Δ_B y el punto F. Los diagramas viajan ahora como **unión discriminada por `tipo`**, así el frontend elige renderizador por etiqueta en vez de adivinar por qué campos vinieron.
- **Detalle de escala resuelto con un conmutador, no eligiendo por el usuario**: los polos caen en +78 y −57 kJ/mol mientras las curvas viven entre 8 y 48. Verlos completos (la esencia del método) aplasta la zona donde se leen las etapas, así que se puede alternar.

### ✅ Simulaciones guardables; los componentes pasan a vivir dentro de ellas (Completado)
- **Reportado**: "cada vez que cambio de panel se borra la simulación". Era cierto: el lienzo vivía en un `useState` de la página del flowsheet, así que navegar lo destruía.
- **Rehecho**: `SimulacionProvider` sustituye al viejo `ConfiguracionProvider`. Una simulación es un **documento** con nombre, componentes, modelo termodinámico y flowsheet. Se pueden tener varias, cada una con su propia mezcla — que es lo que se pidió ("la opción de componentes seleccionados debe estar dentro de la simulación creada").
- **Migración incluida**: una configuración guardada en el formato viejo se convierte en "Simulación recuperada" en vez de descartarse en silencio, que es lo que más molesta al actualizar.
- Descarga/subida como `.simproc.json`. Al importar **siempre entra como simulación nueva** (id nuevo): subir dos veces el mismo archivo da dos simulaciones, nunca pisa una existente. El JSON se sanea al leerlo: un archivo editado a mano no debe tumbar la aplicación.
- **Los resultados NO se guardan** a propósito: son derivados de los datos y del código de cálculo, así que revivirlos de disco solo serviría para mostrar números viejos como si fueran de la versión actual.
- Plantillas: en blanco, mezcla binaria, y columna ya montada.
- **Verificado en navegador**: crear, pasear por tres paneles, recargar el navegador entero, cambiar entre dos simulaciones con componentes distintos, descargar, volver a subir, y rechazar un JSON cualquiera con mensaje claro.
- **Descarga de gráficas** (PNG) sin dependencias nuevas: recharts pinta SVG real, se serializa y se rasteriza en canvas. Dos detalles que hacían falta: copiar los estilos calculados (Tailwind es hoja externa y el SVG los pierde al salir del documento) y rellenar el fondo (un SVG es transparente, y sobre tema oscuro el resultado sería ilegible).

### ✅ Módulo de termodinámica con menú propio; el motor reactivo llega a la web (Completado)
- El motor topológico ya existía (`core/topology.py`, `core/analisis_nodos.py`) pero **solo sabía dibujarse en matplotlib/plotly de escritorio** (`plt.show()`). Ahora `backend/nucleo_termodinamica.py` usa solo los generadores que devuelven arrays y manda los puntos en JSON; el navegador dibuja con su propio tema. La física no se duplicó.
- Rutas nuevas: `/termodinamica/mapa-residual`, `/termodinamica/azeotropos`, `/termodinamica/reaccion`. La última es barata a propósito: dice si la estequiometría y la cinética tienen sentido **antes** de pagar un mapa entero.
- Frontend: índice en `/termodinamica` (ELV, curvas residuales, destilación reactiva), ternario en **SVG** y cuaternario en **canvas con rotación por arrastre**. **No se añadió Plotly**: son megabytes y trae su propio tema; un triángulo baricéntrico son cuatro líneas de álgebra. Canvas para el tetraedro porque hay que repintar la escena entera en cada fotograma del arrastre.
- **Bug real encontrado por el test, no por inspección**: sin reacción se pasaba `gestor=None`, pero la derivada del núcleo **siempre** llamaba a `gestor_reaccion.velocidad_reaccion`. El docstring prometía desde siempre que "Da→0 recupera el límite no reactivo" y eso **no era ejecutable**: reventaba con AttributeError en cada curva. Las 8 curvas fallaban y el mapa salía vacío sin explicación.
- **Segundo problema, de diseño propio**: el `except Exception` que envolvía cada curva se tragaba la causa. Corregido guardando el motivo del primer fallo y, si no sobrevive ninguna curva, fallando con ese motivo en vez de devolver un mapa vacío.
- **Verificado con física, no con "devuelve arrays"**: semillas reproducibles (rejilla determinista, no `np.random`, si no dos mapas del mismo sistema no se pueden comparar); T de ebullición en el orden correcto (acetona 329 < metanol 338 < agua 373); **8/8 curvas se enriquecen en el componente pesado**, que es lo que debe hacer un residuo; MTBE sale exotérmica y su K_eq **baja** al subir T (van't Hoff).

### ✅ Reactor CSTR, resolviendo en las tres direcciones (Completado)
- Estado estacionario, mismo estándar que el resto: `F_out·x_out_i = F_in·x_in_i + ν_i·ξ`, resuelto de forma **exacta** (álgebra, sin iterar) hacia adelante, hacia atrás, y despejando el avance desde UNA fracción de salida — esta última es la que se usa de verdad ("entra esto, quiero esta pureza, ¿cuánto tengo que hacer reaccionar?").
- El balance total `F_out = F_in + ν_tot·ξ` **no se impone aparte**: sale de sumar los n usando que las fracciones suman 1, cosa que ya garantiza el cierre de composición. Imponerlo contaría una ecuación de más y el contador de grados de libertad mentiría.
- Cinética en bloque separado: `ξ = V·r(T, x_salida)`. **La velocidad se evalúa en la composición de SALIDA**, no en el alimento: en un CSTR el tanque está perfectamente mezclado y su contenido es lo que sale. Evaluarla en el alimento es el error clásico y daría un reactor mucho más chico que el real.
- **Verificado**: ida y vuelta recupera caudal y composición a 1e-12; conversión 40 % con los números esperados; un avance mayor que el reactivo disponible se rechaza con motivo físico; y GL = 0 en el caso bien planteado, GL = −1 al dar una fracción de más (el contador detecta el dato sobrante, que es lo que debe hacer).
- **Bug de UI que encontró el test**: `ξ` se mostraba como **"x NaN"**. `etiquetaVariable` trataba como fracción molar cualquier variable que empezara por "x", y `xi` empieza por x. Corregido exigiendo "x" + dígitos; el mismo cuidado hacía falta al formatear.

### ✅ Punto de burbuja: bracket fijo que dejaba fuera a los componentes ligeros (Corregido)
- Encontrado gracias al aviso de fallos del mapa residual: en el sistema del MTBE, 2 de 8 trayectorias morían con el famoso `f(a) and f(b) must have different signs` de scipy — otra vez el mensaje críptico.
- **Causa concreta**: `burbuja_T` buscaba la raíz en un bracket FIJO `[273.15, 600] K`, y el **isobuteno hierve a 266 K**. Cualquier mezcla rica en él quedaba fuera del rango. Un bracket fijo obliga a saber de antemano por dónde hierve la mezcla, que es justo lo que se está calculando.
- **Corregido ensanchando el bracket automáticamente** (el signo del residuo indica hacia qué lado está la raíz) y, si de verdad no hay solución en un rango físico, explicando **por qué** en vez de dejar escapar el error de scipy.
- **Verificado sin regresión**: isobuteno puro ahora da 266.15 K (su valor real); benceno/tolueno 50/50 sigue dando **365.515693 K, idéntico bit a bit** al valor anterior.

### 🔧 Nota de mantenimiento de los tests
- Las cuatro suites de navegador anteriores a las simulaciones daban por hecho que los componentes eran una preferencia global del navegador. Al pasar a vivir dentro de la simulación, arrancaban sin componentes y fallaban. Se añadió `preparar_simulacion.mjs`, que siembra una simulación con los componentes que pida cada test, para que cada suite siga probando lo suyo y no el arranque en frío.
- Y se corrigió el producto además del test: sin simulación abierta (o sin componentes) el flowsheet dibujaba corrientes **sin composiciones**, mudas, sin decir qué faltaba. Ahora lo avisa en la barra con un enlace a donde se arregla. Misma clase de fallo silencioso que el "adim.".
- `validar_ponchon_savarit.py` esperaba un `RuntimeError` genérico donde ahora se lanza un `ValueError` explicando el pinch. Se actualizó y además se endureció: ahora exige que el mensaje **cite el Qc_D_min concreto**, para que no pueda volver a degradarse a un error mudo.

### ✅ El método topológico original llega entero a la web (Corregido)
- **Reportado**: "algo no se exportó bien… te faltó la otra parte que sí estaba bien hecha… esa matemática incluía líneas estequiométricas, polos, etc." Correcto, y el diagnóstico del usuario era exacto.
- **Qué faltaba**: al llevar el motor a la web yo exporté **solo las curvas residuales continuas**. El método original (`archive/equations.py`, conservado en `core/topology.py`) tiene **cuatro** elementos, y tres se quedaron fuera:
  1. trayectorias reactivas **discretas** (salto físico de equilibrio + salto químico) — el mapeo que dibuja el libro;
  2. **curva de equilibrio químico** (donde se cumple K_eq(T));
  3. **líneas estequiométricas** `x(z) = (x_base + z·ν)/(1 + z·ν_tot)`;
  4. **polo geométrico π = ν/ν_tot**.
- **Causa de que se perdieran**: esa matemática estaba escrita **dentro de `plot_ternary`**, entrelazada con llamadas a matplotlib. Solo existía si se abría una ventana de escritorio, así que no había nada que exportar. Se extrajo **tal cual** a métodos que devuelven datos (`curva_equilibrio_quimico`, `lineas_estequiometricas`, `polo_geometrico`, `trayectorias_reactivas`) y `plot_ternary` pasó a llamarlos: una sola implementación, no dos que puedan desincronizarse.
- **No se reprogramó ninguna ecuación.** Verificado contra el script original: para ν = [-1,-2,1], [-1,-1,3] y [-1,1,0] las 12 líneas estequiométricas salen **idénticas bit a bit** (`rtol=0, atol=0`) y el polo coincide, incluyendo el caso equimolar (ν_tot = 0 → polo al infinito, rectas paralelas, que se informa como tal en vez de inventar un punto).
- El polo suele caer **fuera** del triángulo (con ν = [-1,-1,3] sale en (-1,-1,3)). Se dibuja solo si de verdad entra en el lienzo; si no, se cita en el pie con sus coordenadas y se advierte, en vez de pintarlo en un sitio equivocado.
- El mapa lleva ahora cuatro familias de líneas encima, así que cada una se puede **apagar** para leer las demás.

### ✅ Las curvas residuales salían como segmentos rectos (Corregido)
- **Síntoma que reportó el usuario**: "voy sacando varios diagramas pero todos se ven iguales". Medido: las curvas llegaban con **2 a 4 puntos cada una**.
- **Causa**: `generar_curva_residual_cinetica` pasaba `t_eval = linspace(0, xi_max, n_eval)`, o sea repartía los puntos sobre **todo** el intervalo pedido; pero el evento terminal de frontera del símplex corta la integración enseguida (ξ ≈ 1–3). Con `xi_max = 40` y `n_eval = 80` el espaciado es 0.5, así que una curva que termina en ξ = 1.5 se quedaba con **tres puntos** y se dibujaba como una recta. Subir `xi_max` **empeoraba** el problema en vez de arreglarlo, que es justo lo contrario de lo que parecería.
- **Corregido con `dense_output`**: se integra exactamente igual (misma ODE, mismo evento, misma física) y después se reparten los `n_eval` puntos sobre el tramo **realmente recorrido**. Verificado: de 2–4 puntos a 80–120 por curva, y 8 de 12 curvas terminan ya con un componente > 0.95, o sea **llegando a su nodo**.
- Confirmado de paso que UNIFAC sí estaba activo y no era la causa: los γ se desvían fuerte de 1 y el **azeótropo etanol/agua aparece en x = 0.894**, el valor de literatura.

### ⏳ Pendiente en este frente
- Los **puntos singulares del mapa no reactivo** (nodos estables/inestables y sillas, azeótropos sin reacción) siguen sin detectarse ni marcarse: `BuscadorAzeotropos` solo está enchufado en la página reactiva, donde exige una reacción. Sin ellos el mapa inerte no muestra fronteras de destilación.
- No se colorean las cuencas de atracción, que es lo que haría visibles esas fronteras de un golpe.

### ✅ FUG en el flowsheet: se acabó el atasco con más de 2 componentes (Completado)
- **Reportado**: "si meto 4 componentes, McCabe-Thiele no funciona porque detecta 4". Cierto, y el diagnóstico del usuario también ("esto se resolvería si se agrega el método FUG en el flowsheet").
- **Qué faltaba exactamente**: `core/fug.py` y `bloque_fug` ya resolvían FUG, pero con variables de pool **vectoriales** (`x_D`, `x_B` eran arrays enteros), mientras que `DiagramaCorrientes` usa escalares por corriente (`s2.x0`, `s2.x1`…). Los dos mundos no se tocaban. Se añadieron `_bloque_fug_corrientes` y `_bloque_cargas_fug_corrientes`, que hacen de traductores: leen las fracciones sueltas, arman los vectores, llaman a `AnalizadorFUG` y reparten el resultado otra vez en fracciones sueltas. **No se reescribió la matemática de FUG.**
- `AnalizadorFUG` exige `z_F` COMPLETO en su constructor, pero en este modelo la composición de la alimentación vive en el pool y puede no conocerse al armar el diagrama: por eso el analizador se construye **dentro** del bloque, en tiempo de resolución.
- **El conteo de ecuaciones era el punto delicado**: el bloque escribe *n* fracciones para el destilado y *n* para el fondo, pero cada grupo suma 1 por construcción, así que **dos** de esas escrituras no son independientes — ya las aporta el cierre de composición de cada producto. `n_ecuaciones` las descuenta. Verificado: GL = 0 exacto en un caso de 4 componentes.
- **Verificado con física, no con "corre"**: 4 alcanos C5–C8, claves hexano/heptano al 98 %. Balance total y por componente cierran, las fracciones de cada producto suman 1, las **recuperaciones pedidas se cumplen a 1e-5**, N > N_min y el R dado supera R_min.
- **El error binario ahora es accionable.** Antes el fallo llegaba disfrazado: `EvaluadorMcCabeThiele` construía composiciones de 2 elementos contra un proveedor de *n* y lo que veía el usuario era un error de punto de burbuja que no mencionaba el problema real. Ahora McCabe-Thiele y Ponchon-Savarit **rechazan en su constructor** cualquier mezcla que no sea binaria, nombrando los componentes y proponiendo FUG.
- En la interfaz, los métodos que no aplican salen **deshabilitados diciendo por qué** ("McCabe-Thiele — es un método binario y la simulación tiene 4 componentes"), y una columna nueva arranca en FUG si hay más de 2 componentes. FUG pide **recuperaciones**, no purezas, y trae selectores de clave ligero/pesado.

### ✅ Dos bugs que encontraron las plantillas al armarlas
- **Etapas NEGATIVAS**: la plantilla combinada dio `N = -21.4`. Causa: los componentes clave estaban invertidos (puse LK=metanol y HK=MTBE, pero **el MTBE hierve a 328 K y el metanol a 338 K**, o sea el MTBE es el ligero). Con α_LK < 1, `log(α)` es negativo y N_min sale negativo, arrastrando N. `calcular_etapas_reales` sí comprobaba `R <= R_min`, pero con R_min = −12.7 la comprobación pasaba. **Corregido con una guarda en `preparar_fenske`** que exige α_LK > 1 y, si no, explica que los claves están invertidos citando ambos puntos de ebullición. Una columna con −21 etapas no es un aviso: es basura presentada como resultado.
- **Doble especificación de P y T al encadenar equipos**: una corriente que sale de un reactor y entra en una columna recibía DOS ecuaciones de presión (la del reactor y la de la columna) y dos de temperatura. El medidor decía GL = −2 con el problema bien planteado. Corregido con dos registros (`_presion_fijada`, `_temperatura_fijada`): el segundo equipo no vuelve a fijar lo que ya está fijado.

### ✅ Menú de dos niveles, procesos listos y JSON reutilizable (Completado)
- **Dos niveles de navegación**: arriba el archivador ("Mis simulaciones"), abajo una barra propia de la simulación abierta con Componentes / Flowsheet / Termodinámica / Columna suelta, su nombre editable in situ y el resumen (componentes y equipos). Antes estaba todo en una barra plana y no se distinguía "cambiar de documento" de "moverse dentro del documento".
- **Guardar / Cargar JSON desde dentro de la simulación**, no solo desde el listado. El archivo lleva el flowsheet completo: componentes, nodos, aristas y datos. Verificado: 3 componentes, 6 nodos, 5 aristas y 10 datos en el caso combinado.
- **Cinco procesos ya armados**, agrupados por categoría y marcados con una etiqueta "lista": columna McCabe-Thiele, columna Ponchon-Savarit, columna multicomponente FUG, reactor CSTR y reactor+columna en serie. **Se abren y se pulsa Resolver, sin escribir nada.**
- Esas cinco están verificadas con un test propio (`verificar_plantillas.mjs`) que replica la traducción lienzo→backend y exige **GL = 0 y `completo=true`** en cada una. No es "parecen bien": es que el servidor las resuelve.

### ✅ Líneas rectas en el diagrama (Completado)
- Las conexiones pasan de curvas de Bézier a **trazado ortogonal** (`smoothstep` con `borderRadius: 0`), con punta de flecha. Un diagrama de proceso se lee como un plano: tramos horizontales y verticales con esquinas a escuadra.
- Verificado en el DOM, no a ojo: **0 de 3 aristas** usan comandos de curva (C/S) y todas usan segmentos de recta (L).

### 🔧 Mantenimiento de tests
- La barra de simulación nueva introduce un `input[type=file]` oculto y repite el nombre de la simulación en pantalla. Dos suites daban por hecho que el primer `<input>` era del formulario y que el nombre solo aparecía en la fila de la lista. Ajustadas para filtrar los inputs de archivo y para localizar la fila por los botones que contiene, no por el texto.

### 🔍 Auditoría del motor de resolución — 4 defectos encontrados y corregidos
Pregunta de partida: *"¿se puede agregar operaciones indefinidamente sin que nada se rompa?"* Se midió, no se opinó: cadenas de hasta 120 reactores en serie, en orden favorable y en el peor orden posible.

**Lo que SÍ estaba bien:**
- **Escala**: 120 operaciones (721 bloques, ~1400 variables) resuelven con GL = 0 en 0.08 s. El coste es lineal.
- **Independencia del orden**: el resultado es idéntico con los bloques ordenados aguas arriba→abajo o al revés. El punto fijo converge al mismo sitio.
- **El pool es 100 % escalar**, incluso con FUG. La duda del usuario ("la corriente era escalar, los equipos vectoriales") era legítima: `bloque_fug` en `orquestador.py` SÍ usa vectores, pero ese es el camino antiguo (`core/columna_destilacion.py`, `/flowsheet/resolver`), que la interfaz no usa. El camino del flowsheet (`_bloque_fug_corrientes`) traduce a escalares. Verificado: 0 variables no escalares en el pool.

**Defecto 1 — tope de iteraciones: fallo SILENCIOSO a escala.** El tope era una constante (20 en `Orquestador`, 30 desde `DiagramaCorrientes`). Medido: hacen falta ≈ N+2 pasadas para N operaciones, así que **a partir de ~29 equipos el diagrama se quedaba a medias**. Y el síntoma era indistinguible de "faltan datos": `completo=False`, **cero inconsistencias, cero errores**, y el contador de grados de libertad diciendo **GL = 0 ("exactamente especificado")**. Es decir: se le decía al usuario que sus datos estaban bien, no se resolvía, y no se daba ningún motivo. Corregido calculando el tope como `len(bloques)+2` (cota superior segura para un diagrama sin lazos) **y** devolviendo `agotado_el_tope`, que si se activa se reporta como una inconsistencia explicando que el límite es del solver, no de los datos.

**Defecto 2 — el bucle nunca terminaba antes de tiempo.** `cambio = True` se ponía por el mero hecho de que un bloque CORRIERA, aunque no escribiera nada. Y muchísimos bloques devuelven `{}` cuando todavía no pueden decidir una dirección (el balance del CSTR, el cierre de composición con dos huecos, la cinética sin T). Consecuencia: **toda** resolución agotaba el tope de pasadas aunque llevara rato sin avanzar — trabajo inútil, y además la bandera nueva del defecto 1 daba falsos positivos (marcaba como truncado un diagrama que simplemente estaba incompleto). Corregido: `cambio` solo si de verdad se escribió algo. Ahora un reciclo termina en **2 pasadas** en vez de agotar el tope, y una cadena de 120 equipos usa 123 pasadas (las mínimas), no el máximo.

**Defecto 3 — errores rancios presentados como ecuaciones violadas.** Un bloque puede fallar en una pasada temprana (aún sin datos) y acertar en una posterior; su mensaje viejo quedaba en `errores_bloque` y se reportaba al usuario como una inconsistencia. Corregido descartando el error de cualquier bloque que acabara resolviendo algo. Verificado con un bloque que falla a propósito en su primer intento.

**Defecto 4 — R_min NEGATIVO aceptado.** Underwood puede devolver un reflujo mínimo negativo cuando el corte pedido es muy suave o los claves no son adyacentes. `calcular_etapas_reales` comprobaba `R <= R_min`, pero con R_min = −0.43 esa comprobación pasa tan ricamente y Gilliland devolvía un número de etapas **de aspecto razonable construido sobre un mínimo imposible**. Se destapó armando el caso columna+reactor con recuperaciones del 70 %. Corregido con una guarda que lo rechaza explicando qué significa y qué hacer. El proyecto ya conocía el caso (`validar_fug.py` lo imprimía como curiosidad: *"NEGATIVO, no físico"*) pero lo dejaba pasar; el test se endureció para exigir el rechazo.

**Limitación que sigue en pie: no hay tearing de reciclos.** Un lazo termina limpio (2 pasadas, no se cuelga) pero deja variables sin determinar, y el síntoma vuelve a ser "faltan datos". El motor solo rellena huecos, nunca reescribe, así que un lazo no tiene por dónde empezar.

### ✅ Caso columna + reactor, topología inversa (Completado)
- Ya existía `reactor → columna`. Se añade **`columna → reactor de acabado`**: la columna hace un corte suave (80 % de recuperación), así que el destilado se lleva los **dos reactivos todavía juntos**, y un reactor de acabado convierte lo que queda. Es una configuración real.
- Elegir los números costó dos hallazgos: con recuperaciones del 70 % el R_min salía negativo (defecto 4), y dar T y P de la alimentación sobraba porque con q = 1 la columna ya las determina (su punto de burbuja). Con recuperación 0.80 y R = 1.5: **R_min = 0.483, N_min = 6.92, N = 10.30**, y el reactor de acabado convierte el 30 % restante. GL = 0, `completo=true`, cero inconsistencias.

### 🔍 Segunda auditoría: los arreglos anteriores NO eran generales
El usuario preguntó directamente: *"¿ajustaste todo para resolver específicamente un reactor y columna, o podría estar agregando equipos e igual se resolvería?"*. Se midió con seis topologías que **no** se habían ajustado. **Fallaron las seis.** Tenía razón.

Dos causas, ambas estructurales:

**Defecto 1 — el conteo de ecuaciones se hacía A MANO por bloque.** Cuando un bloque calcula el vector de composición COMPLETO de una corriente, esas *n* escrituras no son *n* ecuaciones independientes sino *n−1*: la enésima ya la aporta el cierre de composición. Eso se había compensado a mano dentro de FUG (literalmente `len(variables_salida) - 2`) y en el CSTR, pero **el mezclador y el divisor nunca se corrigieron**: cualquier diagrama que los usara daba GL negativo estando bien planteado (medido: −2 con un divisor, −5 con seis equipos). Corregido con `_composiciones_dependientes()`, que detecta la situación **estructuralmente** recorriendo las salidas declaradas de cada bloque. El parche manual de FUG se retiró. Ahora cualquier bloque futuro lo hereda sin que haya que acordarse de nada.

**Defecto 2 — el mezclador no tenía balance de energía ni presión.** Solo hacía materia, así que su salida quedaba sin T ni P y paralizaba a todo lo que viniera detrás. Se le añadió un balance adiabático real (Σ F·h(T,x) = F_out·h(T_out,x_out), con Cp de `thermo` e iteración sobre T_out porque Cp depende de T) y P_out = mínimo de las entradas. Esto importa el doble porque **el mezclador es justo por donde entra un reciclo**.

Con los dos arreglos, **6 de 6** topologías pasan: mezclador→reactor, reactor→divisor, columna→divisor, 2 reactores→mezclador→reactor, McCabe-Thiele→divisor, y una cadena de 6 equipos de 4 tipos distintos.

### ✅ Reciclos (recirculación) — implementado con tearing
El motor de punto fijo solo RELLENA huecos y nunca reescribe: eso lo hace inmune a oscilar, pero significa que un lazo no tiene por dónde empezar. El síntoma era "faltan datos", indistinguible de un problema mal planteado.

- **Detección automática de lazos** sobre el grafo operación→operación, que exigió registrar en cada operación qué corrientes consume y cuáles produce, y qué bloques creó.
- **Corte (tearing)** reutilizando `renombrar_bloque`: quien PRODUCE la corriente cortada pasa a escribir en un alias interno (`reciclo#calc`), así que en el diagrama roto nadie escribe `reciclo` y su valor es el supuesto. **No hubo que tocar ni un bloque.**
- **Elección del corte, que resultó no ser trivial.** La primera versión cortaba por frecuencia y eligió `mezcla` (la SALIDA del mezclador, que ya lleva la alimentación fresca): suponerla con F = 0 daba caudal cero al reactor y el avance pedido salía imposible. La heurística correcta es preferir la corriente cuyo CONSUMIDOR tiene además una entrada de fuera del lazo — esa entrada ancla la solución. Con ella se corta `reciclo`, y suponer F = 0 significa "arrancar la planta sin recirculación", que es lo que físicamente pasa.
- **Wegstein** en vez de sustitución sucesiva pura: medido, al 90 % de recirculación pasó de **154 vueltas a 9**, con la misma solución. q acotado a [−8, 0.95] porque extrapolar sin límite dispara el supuesto a caudales negativos en las primeras vueltas.
- **Verificado contra el balance global**, no solo contra la convergencia: con 100 mol/s frescos, ξ = 5 y 80 % de reciclo sale mezcla = 480 = 100 + 380, salida = 475 = 480 − 5, producto = 95, y `fresco − producto = 5 = ξ`. El balance por componente cierra. Converge con 0 %, 30 %, 50 %, 70 % y 90 % de recirculación.
- Si el lazo **no** converge se dice explícitamente, con el error alcanzado, y se avisa de que los valores mostrados son la última iteración y no una solución.

### ✅ Reactor con varias entradas
Un reactor real recibe más de una corriente (fresca + reciclo + inyección). Ahora acepta N, mezclándolas en una corriente interna que reutiliza el mezclador ya probado — incluido su balance de energía — en vez de reimplementar nada. El caso de una sola entrada queda exactamente igual que antes. Las variables internas (marcadas con `#`) no se le enseñan al usuario, que no las ha dibujado. Verificado con tres entradas a T distintas: GL = 0 y los balances por componente cierran sobre la suma de las tres.

**Hueco que destapó:** un CSTR **sin** cinética no propagaba temperatura, así que bloqueaba al equipo siguiente (se vio montando el reciclo: el divisor aguas abajo no podía arrancar). La igualdad "T de salida = T del tanque" estaba dentro del `if con_cinetica`, y un tanque tiene temperatura haya o no cinética.

### ✅ Panel del reactor rehecho
La estequiometría se escribía como una cadena suelta (`-1,-1,1`) en la que había que acordarse del orden de los componentes y del signo, sin forma de comprobar lo escrito sin resolver. Ahora cada componente tiene su fila con **papel** (reactivo / producto / no entra) y **magnitud** separados, la ecuación se ve escrita debajo mientras se edita, y el número de entradas se ajusta con +/−. La reacción aparece además **sobre el propio nodo del reactor** en el diagrama: es lo primero que uno quiere saber de un reactor y antes había que abrir el panel y descifrar coeficientes.

### ✅ Plantilla "Reactor con recirculación"
El lazo clásico: fresco → mezclador → reactor → divisor, con el 80 % de vuelta al mezclador. Resuelve de un clic (GL = 0, corta `reciclo`, converge en 3 vueltas).

### ✅ Las unidades pasan a vivir DENTRO de la simulación (Corregido)
- **Reportado con captura**: la plantilla de reciclo, que pasaba su propio test contra la API, fallaba en el navegador con *"El avance xi=5 deja un caudal de salida no positivo (F_out=-4.36975 mol/s)"*.
- **Causa, confirmada al decimal**: las preferencias de unidad eran GLOBALES del navegador (`localStorage["simulador.unidades"]`, indexadas por nombre de variable). Haber elegido kg/h alguna vez hacía que **cualquier simulación futura** leyera `F` en kg/h — incluidas las plantillas, cuyos valores están escritos en SI. El `"100"` de la plantilla se interpretaba como 100 kg/h; con la MW de la mezcla fresca (44.074 g/mol) eso son **0.63025 mol/s**, y 0.63025 − 5 = **−4.36975**, exactamente el número del error.
- **Corregido moviendo las unidades al documento de la simulación**, igual que se hizo con los componentes. Los números de una simulación no significan nada sin sus unidades, así que las unidades son parte de ella. Las plantillas arrancan sin preferencias, o sea en SI, que es lo único coherente con cómo están escritas.
- **Verificado en navegador**: se elige kg/h en una simulación, se crea otra, y la nueva arranca en mol/s sin contaminarse. La plantilla de reciclo resuelve (`mezcla.F = 480 mol/s`, 100 frescos + 380 reciclados).
- Nota de migración: las preferencias globales viejas se ignoran a propósito. Restaurarlas reintroduciría el fallo.

### ✅ Renombrar cualquier elemento del diagrama (Completado)
- Los nombres automáticos (s1, col1, r1) sirven para empezar, pero un diagrama que se va a leer o compartir necesita nombres con significado.
- Renombrar **no es solo cambiar el id del nodo**: las aristas lo referencian por nombre, y todas las claves del pool (`s1.F`, `s1.x0`…) y de las unidades llevan el nombre delante. Si alguna se quedara con el viejo, el dato existiría pero apuntaría a una corriente inexistente — desaparecería sin decir nada. El renombrado arrastra las cuatro cosas y descarta los resultados anteriores, cuyas claves ya no valen.
- Se valida el nombre (sin puntos, sin duplicados, formato de identificador) **diciendo el motivo** cuando se rechaza.
- **Verificado**: renombrar conserva los datos (F = 100), las 8 aristas del lazo, y el diagrama sigue resolviendo después.

---

# Fase 6: El proyecto como proyecto (Infraestructura)

No es física, pero sin esto lo anterior no se sostiene.

### ✅ Control de versiones (Completado)
- **El proyecto no tenía git.** ~5500 líneas solo en `core/`, más backend, frontend y un `docs/history/build-log.md` de 132 KB que ES el registro histórico — todo en una única copia sin historial. Un `sed` mal puesto se lo llevaba.
- Y hay una razón específica de este proyecto: su criterio de validación se apoya en comparar contra valores anteriores ("idéntico bit a bit", 365.515693 K). **Sin git esa comparación la hacía la memoria**, no una herramienta.
- **El `.gitignore` primero, antes del primer `git add`.** Medido: `frontend/.next` 535 MB y `frontend/node_modules` 530 MB, o sea **más de 1 GB** de artefactos regenerables. Una vez dentro del historial, sacarlos obliga a reescribirlo.
- **Hallazgo al revisar qué entraba**: `archive/` eran 57 de los 58 MB restantes, en tres archivos — `Yaws_Handbook_...xlsx` (12 MB) y dos bases derivadas de él (`.db` 17 MB, `.json` 29 MB). El xlsx es un **libro de referencia comercial**: subirlo a un repositorio público es un problema de derechos de autor, no solo de tamaño. Los tres quedan fuera del historial (siguen en disco, y son regenerables con `archive/etl_yaws.py`); el CÓDIGO de `archive/` sí se versiona, porque es la referencia contra la que se validaron las líneas estequiométricas bit a bit y `core/topology.py` lo cita.
- Resultado: **126 archivos, 1.7 MB**. Dos commits, rama `main`, sin secretos (barrido previo hecho).

### ✅ Versiones de dependencias fijadas (Completado)
- `requirements.txt` eran cuatro nombres sueltos sin versión. Ahora están fijas, con el porqué escrito en el propio archivo.
- **No es higiene teórica: ya mordió una vez.** El roadmap lo registra en la Fase 1 — los atributos `Hfl`/`Gfl` de `thermo` no existían en la versión instalada y hubo que corregir a `Hfm`/`Gfm`. Un cambio de API río arriba que invalidaba en silencio un cálculo termodinámico.
- El argumento de fondo: las validaciones de este proyecto comparan contra valores **exactos**. Ese tipo de test solo significa algo contra una versión fija de `thermo`. Con la versión flotando, el test más fuerte del proyecto se convierte en ruido — un día falla y no se sabe si se rompió algo aquí o cambió una correlación afuera.
- **Hueco real encontrado al fijarlas**: `python-ternary` y `plotly` **faltaban por completo** del `requirements.txt`, y no son opcionales — `core/topology.py` y `core/analisis_nodos.py` las importan al nivel del módulo. Un clon limpio del repositorio no podía ni importar el motor topológico. (Ojo al nombre: se instala como `python-ternary` y se importa como `ternary`.)
- Entorno de referencia anotado: Python 3.12.10, `thermo` 0.6.1, `scipy` 1.16.2, `numpy` 1.26.4.

### ✅ Un comando para correr todo (Completado)
- `run_tests.py`: lanza las 11 suites, muestra tiempos y devuelve **código de salida real** (0/1). Acepta filtro (`python run_tests.py flash`) y `-v`.
- Lo que faltaba no era el contenido de las validaciones, que siempre fue bueno, sino poder lanzarlas todas de una: antes se ejecutaban a mano y se leían con los ojos, así que no existía un "el proyecto está verde" comprobable, solo un "las que miré estaban bien".
- **Fallo real encontrado al montarlo**: en una consola Windows por defecto (cp1252), cualquier suite que imprimiera un símbolo griego moría con `UnicodeEncodeError`. No es que fallara la validación — **no llegaba a ejecutarse**, y solo funcionaba si quien la lanzaba sabía poner `PYTHONIOENCODING=utf-8`. Cada suite se protege ahora por dentro.
- Medido limpio: **11 suites en 60.8 s, todo verde**. (Aviso: una medición anterior daba 5428 s en McCabe-Thiele; era contención entre tres regresiones simultáneas, no una regresión del código. Se volvió a medir en aislamiento: 6.9 s.)

### ✅ README de la raíz (Completado)
- Existía `../README.md` (el índice de la matemática) pero nada en la raíz: la puerta de entrada al repositorio estaba vacía.
- Incluye una sección **"Qué NO hace"** explícita, en la misma línea que `../12-validacion.md`: los límites del simulador son parte de lo que hay que saber antes de usar un número que produce.

### ✅ Repositorio remoto en GitHub (Completado)
- Publicado en `RandallTz/Rage-Engine-Chemical-Engineering-Ops`, rama `main`.
- Se verificó explícitamente antes de empujar que el manual de Yaws y las dos bases derivadas de él quedaban fuera del historial: el repositorio es público.
- Desplegado: backend en Render (`/salud` responde, el azeótropo etanol/agua sale en 0.8926 contra el 0.894 de literatura) y frontend en Vercel.
- Dos tropiezos del despliegue, por si vuelven: Vercel necesita **Root Directory = `frontend`** (la raíz del repo no tiene `package.json`), y el `*.svg` del `.gitignore` se tragaba `frontend/public/`, que al no quedar ningún archivo desaparecía entera del repositorio.

### ⬜ Integración continua (Pendiente)
- Con `run_tests.py` devolviendo código de salida, un workflow de GitHub Actions es casi inmediato. No se ha montado.

---

# Fase 7: De herramienta propia a herramienta de otros (Adopción)

Un cambio de objetivo, no solo de tareas. Hasta aquí el simulador se construyó para ser **correcto**. Esta fase es para que además sea **usable por alguien que no lo escribió**.

El encuadre que la motiva: compitiendo en amplitud de funciones contra DWSIM, ChemSep o Aspen no hay carrera que ganar. Lo que este proyecto tiene y ellos no, todo junto, es: corre en el **navegador** sin instalar nada, **enseña sus grados de libertad**, **enseña sus ecuaciones y sus límites**, y está **en español**. No es "un Aspen pobre": es la herramienta con la que se APRENDE destilación, que es otra categoría.

Nada de esta fase toca una ecuación. Verificado: el frontend no calcula física — ni un `Math.exp`, ni UNIFAC, ni un punto de burbuja. Solo dibuja lo que devuelve el núcleo validado.

### ✅ A1 — Enlace compartible (Completado)
- **El problema**: una simulación vivía en `localStorage` y la única forma de moverla era descargar un `.simproc.json` y mandarlo adjunto. Eso basta para llevártela a otra máquina, pero no para lo que hace falta en un curso: que un profesor mande un enlace con un problema planteado y el alumno lo abra y lo resuelva. Un adjunto se pierde; un enlace se pega donde sea. **Es lo que convierte una herramienta personal en una compartida.**
- `frontend/app/components/enlaceCompartible.ts`. Decisiones:
  - **Va en el FRAGMENTO (`#`), no en la query.** El fragmento no se envía al servidor: el diagrama de nadie acaba en los registros de Vercel ni de Render.
  - **Todo el estado viaja en la URL, sin guardar nada en un servidor.** No hace falta base de datos, funciona con el frontend estático, y el enlace no caduca porque no depende de que conservemos nada.
  - **Se comprime con deflate.** Un flowsheet es JSON con muchas claves repetidas, que es lo que mejor comprime. Medido: una simulación realista de 8 nodos pasa de 2627 caracteres de JSON a un enlace de **802** (31 %).
  - **Viaja SOLO el planteamiento, nunca los resultados.** Quien abra el enlace los recalcula con el mismo núcleo validado. Mandar resultados precocinados permitiría enviar un enlace con cifras que el simulador no produce — justo lo contrario de lo que este proyecto defiende.
  - Lo que llega pasa por el **mismo `sanear()`** que los archivos: un enlace puede venir manipulado y no merece más confianza que un JSON editado a mano.
  - Entra como simulación **nueva** y limpia el fragmento: no pisa trabajo existente ni se duplica al recargar.
- Tope de 8000 caracteres, no por los navegadores sino porque muchos clientes de correo cortan los enlaces largos en silencio — y un enlace cortado es peor que ninguno, porque falla en manos de otro sin que quien lo mandó se entere. Por encima se rechaza explicando y remitiendo al archivo.
- `frontend/verificar_enlace.mjs`: ida y vuelta con acentos, componentes, unidades, diagrama entero y decimales sin redondear; que el id y los resultados NO viajen; seis enlaces corruptos que devuelven `null` sin tumbar nada; y el rechazo por tamaño.
- **Hallazgo al escribir esa última prueba**: repetir 400 nodos iguales NO sirve para ejercitar el tope, porque deflate se come la repetición y caben de sobra (3994 caracteres). Hace falta contenido incompresible. La primera versión del test pasaba por el motivo equivocado.

### ✅ A2 — `docs/` conectado a la aplicación (Completado)
- **El problema**: la parte más valiosa del proyecto —12 documentos con la matemática de cada método y sus límites explícitos— era **invisible desde la aplicación**. Cero enlaces, medido. El usuario veía un número y no tenía forma de saber de dónde salía ni cuándo deja de valer. Eso es exactamente lo contrario de lo que diferencia a este simulador de una caja negra.
- `frontend/app/components/metodos.ts`: catálogo de siete métodos (McCabe-Thiele, Ponchon-Savarit, FUG, flash, CSTR, curvas residuales, ELV) con su resumen, sus suposiciones, sus límites y el documento donde está la deducción. Es **datos, no lógica**: no calcula nada.
- `frontend/app/components/FichaMetodo.tsx`, panel plegable junto a los resultados. Dos decisiones:
  - **Plegado por defecto**: quien ya sabe no quiere leerlo cada vez; quien no, lo tiene a un clic. Lo que no puede pasar es que no esté.
  - **Los LÍMITES van primero**, antes que las suposiciones y en ámbar. Es el orden contrario al habitual y es deliberado: lo que de verdad hace falta saber antes de usar un número es cuándo no vale.
- Colocado en la columna suelta (según el método elegido), el mapa de curvas residuales y la página de ELV.
- Enlaza a `docs/` en vez de duplicar la deducción: dos copias de una ecuación acaban divergiendo, y la del código no es la que se lee.

### ✅ A3 — Portada (Completado)
- **El problema**: la raíz `/` era directamente la herramienta de "columna suelta". Alguien que llegaba por un enlace aterrizaba en un formulario de parámetros sin saber qué era esto ni si podía fiarse. Con A1, llegar de fuera deja de ser la excepción y pasa a ser el caso normal.
- La columna suelta se movió a `/columna` y `/` pasa a ser la portada. Tres cosas, en este orden: qué es y para quién; un clic hasta algo que funciona; y **qué NO hace**.
- Esa tercera sección no es modestia, es lo mismo que hace `../12-validacion.md`: un simulador que no declara sus límites invita a usar un número donde no vale. Declara explícitamente que no hay MESH todavía.
- Cita validaciones **concretas y comprobables** (azeótropo en 0.894, balance con reciclo a 4e-12, líquido del flash en su burbuja a 1e-9) en vez de decir "está validado".

### Verificación de la fase
- `frontend/verificar_portada_y_enlace.mjs`, en Edge real: 25 comprobaciones en verde.
- La importante es la de extremo a extremo del enlace: se crea una simulación desde una plantilla en un contexto de navegador, se genera el fragmento con `CompressionStream` de verdad, y se abre en un **contexto limpio** —que es el escenario real de "se lo mando a alguien que nunca ha entrado"—. Se comprueba que se reconstruye con su nombre, sus 2 componentes y sus 4 nodos, que entra como simulación nueva y que el fragmento se limpia.
- Sin regresiones: `verificar_simulaciones.mjs`, `verificar_topologia.mjs` y `verificar_plantillas.mjs` siguen pasando, y las 11 suites de Python siguen en verde.

### ✅ B1 — Integración continua (Completado)
- `.github/workflows/validacion.yml`: dos trabajos en cada push y cada pull request.
  - **Núcleo**: `python run_tests.py` con `MPLBACKEND=Agg` (mismo ajuste que hizo falta en Render: `core/mccabe_thiele.py` importa matplotlib al cargar el módulo y un runner no tiene pantalla). Devuelve código de salida real, así que una sola comprobación en rojo tumba el trabajo.
  - **Frontend**: `npm ci`, `npm run build` y la ida y vuelta del enlace compartible, que es lógica pura y no necesita navegador.
- Comprobado el comando exacto en local antes de escribirlo: `MPLBACKEND=Agg python run_tests.py` → 11 suites en verde.
- Nota para el futuro: si esto empieza a fallar sin que nadie haya tocado el núcleo, lo primero que hay que mirar es si alguna dependencia se movió. Las versiones están fijas en `requirements.txt` justamente porque varias comprobaciones comparan contra valores exactos.

### ✅ B3 — Los equipos térmicos, visibles desde la interfaz (Completado)
- **El hueco, medido**: el núcleo resolvía 10 tipos de equipo y la interfaz dejaba dibujar 5. El flash, el intercambiador y la válvula estaban construidos y validados desde la Fase 4 pero eran **invisibles** desde la web, igual que los tres modos de energía del reactor.
- Cableado completo: `backend/schemas.py` (tipos y parámetros nuevos), `backend/nucleo_diagrama.py` (despacho), `frontend/app/flowsheet/modelo.ts` (puertos y variables propias), la paleta, el armado de la petición y `PanelLateral.tsx`.
- Los nodos no hubo que tocarlos: `nodos.tsx` ya dibujaba los puertos con `puertosDe()` de forma genérica, así que los equipos nuevos aparecen solos. Buena señal de que esa abstracción estaba bien puesta.
- **Una especificación, nunca dos.** El panel del flash ofrece un SELECTOR (calor dado / temperatura / fracción vaporizada) en vez de tres casillas marcables, y la petición manda solo la elegida. El núcleo rechaza las combinaciones sobre-especificadas a propósito; mandar las tres "por si acaso" convertiría un diagrama válido en un error.
- El flash tiene dos salidas con nombre propio (`vapor` arriba, `liquido` abajo), que NO son intercambiables.
- Plantilla nueva **«Válvula + flash (listo)»**: líquido a presión → intercambiador → válvula → flash adiabático. Resuelve de un clic y reproduce exactamente los números de la cadena en Python (vapor 36.770 / líquido 63.230 mol/s, y la válvula enfría de 434.6 K a 369.6 K).

### ⚠ Defecto encontrado, y estaba YA EN PRODUCCIÓN
Al reiniciar la API con el código actual (hasta entonces había un uvicorn viejo sirviendo código anterior, que es lo que enmascaraba el fallo) las **cuatro plantillas de reactor dejaron de resolver**.

- **Causa**: el balance de energía del reactor, añadido en la Fase 4, se activa por defecto (`modo_energia="isotermo"` más proveedor presente). Y ese balance **necesita la T y la P de la corriente de entrada**: sin ellas, `Q` y `Q_reaccion` se quedan sin determinar para siempre y el diagrama nunca sale "completo". O sea que encender la energía **añade un requisito de datos**, cosa que no se vio al construirlo porque las suites de Python sí daban esos datos.
- **Y debajo había algo peor, que el propio balance destapó**: con la T y la P puestas, el reactor de MTBE de las plantillas sigue fallando a 1 atm — porque **estaría hirviendo**. La guarda `_exigir_liquido` lo rechaza con razón. Las plantillas llevaban modelando un tanque físicamente imposible, y pasaban porque nada lo comprobaba. A 10 atm resuelve y pide **944 kW de refrigeración**.
- **Arreglo**, en dos partes:
  1. `con_balance_energia` en el reactor, igual que ya tenían las columnas, con su casilla en el panel. Un diagrama que solo quiere balances de materia no tiene por qué dar la T de entrada.
  2. Las cuatro plantillas de reactor lo llevan en `false` **explícitamente**, con el motivo escrito al lado. Son demostraciones de balance de materia y así conservan sus números exactos.
- Queda pendiente, y es buen material de clase: una plantilla de reactor a presión realista que SÍ muestre el calor de refrigeración. Ese número (944 kW para mantener 340 K) es justo lo que un simulador sin balance de energía oculta.

### Verificación de B
- 10/10 plantillas en verde, incluida la nueva.
- 11/11 suites de Python.
- Navegador: `verificar_simulaciones`, `verificar_topologia`, `verificar_unidades`, `verificar_portada_y_enlace` y `verificar_enlace`, todas en verde.
- **Nota de mantenimiento**: `verificar_plantillas.mjs` tiene su PROPIA copia del mapeo de puertos y del armado de la petición, duplicando `modelo.ts` y `page.tsx`. Hubo que extenderla a mano para los equipos nuevos, y la primera ejecución falló por eso. Es deuda real: cada equipo nuevo hay que añadirlo en dos sitios y nada avisa si se olvida uno.

### ⬜ B2 — Los 0.1 CPU de Render (Pendiente, decisión del usuario)
- Medido en producción: curva ELV 1.4 s, flowsheet ~10 s, mapa residual **85 s** — unas 14 veces más lento que en local, que es exactamente la firma de una décima de núcleo.
- Subir a 0.5 CPU (7 USD/mes) lo deja en ~17 s y además quita el arranque en frío de un minuto. Cero código.

### ⬜ C — Biblioteca de problemas de libro (Pendiente)
- Casos reconocibles (Seader, Kister, Doherty) con sus valores publicados. Hace tres cosas a la vez: es la **validación contra literatura** que hoy falta —toda la validación actual es consistencia interna, que demuestra coherencia pero no corrección—, es material de clase, y es lo que permite decir "reproduce estos casos publicados".

### ⬜ D — MESH (Pendiente)
- Ver Fase 4. El cimiento está puesto a propósito y, tras C, habría contra qué medirlo.

---

# Fase 8: Más operaciones, y que se combinen

Objetivo fijado explícitamente: **primero la mayor cantidad de operaciones posible, los métodos rigurosos al final** — y con la condición de que se puedan encadenar sin que el solver se atasque. El tamaño a garantizar: ~15 equipos con 2 reciclos. Los valores por defecto, típicos de libro, visibles y editables.

El núcleo pasa de **10 a 14 tipos de equipo**, y los cuatro nuevos están en la interfaz desde el primer día (el hueco núcleo↔interfaz de la Fase 7 no se vuelve a abrir).

### ✅ Separador de componentes (Completado)
- Se dice qué fracción de cada componente sale por cada lado y el equipo reparte. Es el "atajo" universal que tiene todo simulador, y lo que permite montar un diagrama completo **antes** de haber decidido con qué equipo se separa cada cosa.
- **No es física y la ficha lo dice**: nada impide pedir que dos componentes con el mismo punto de ebullición se separen al 99.9 %. No sustituye a una columna cuando la pregunta es si la separación se puede hacer.
- Verificado: balance por componente a $10^{-10}$, recuperaciones respetadas exactamente, separación perfecta da productos puros, y una recuperación fuera de [0,1] se rechaza.

### ✅ Compresor / turbina (Completado)
- El mismo equipo en los dos sentidos: comprimir consume trabajo, expandir lo produce. Relación isentrópica de gas ideal más eficiencia isentrópica.
- **Hizo falta Cp del GAS**, que el proyecto no tenía: hasta ahora solo necesitaba el del líquido, porque las entalpías de vapor se construyen como $h_L + \Delta H_{vap}$ y la derivada de esa suma YA es el $C_p$ del vapor. Lo que no se puede sacar de ahí es $k = C_p/(C_p-R)$ para la relación isentrópica. Nuevos: `capacidades_calorificas_gas` y `exponente_isentropico`.
- El trabajo sale de la entalpía ya validada ($W = F[h_V(T_2)-h_V(T_1)]$), no de una fórmula aparte, así que el compresor mide la energía con la misma regla que el flash y el reactor.
- **El detalle que es el error clásico**: la ineficiencia SIEMPRE deja la salida más caliente que la ideal. Comprimiendo eso significa llegar más caliente (se divide por $\eta$); expandiendo, enfriarse MENOS de lo ideal (se multiplica). Escribirlo con un solo signo da turbinas que enfrían de más. Verificado en los dos sentidos.
- Con $\eta = 1$ la salida es exactamente la isentrópica, y el trabajo crece monótonamente al empeorar la eficiencia.

### ✅ Reactor de equilibrio químico (Completado)
- $\prod_i a_i^{\nu_i} = K_{eq}(T)$, sin cinética y **sin volumen**: el equilibrio no depende del tamaño del tanque. Responde a una pregunta distinta que el CSTR cinético — "por mucho tanque que pongas, no pasas de aquí" frente a "con este tanque llego hasta aquí". Son el límite termodinámico y el práctico, y conviene poder ver los dos.
- Barato porque las dos piezas ya existían: van't Hoff en `GestorReaccion` y $\gamma$ de UNIFAC.
- **Se resuelve en logaritmos**: el productorio de actividades elevadas a $\nu$ recorre varios órdenes de magnitud y multiplicarlo directamente pierde precisión (o desborda) cerca de los extremos, que es justo donde hay que evaluarlo.
- **El bracket admite avance NEGATIVO**, y no es un capricho: si la alimentación ya trae producto por encima del equilibrio —un reciclo que lo devuelve, por ejemplo— la reacción corre al revés. Un bracket que empezara en cero devolvería "no hay equilibrio" sobre un caso normal. Verificado: con 90 % de MTBE en la entrada da $\xi = -57.17$ mol/s.
- Verificado contra van't Hoff: la conversión de equilibrio cae de 86.1 % a 34.6 % entre 320 K y 380 K, y la salida cumple $\prod a_i^{\nu_i} = K_{eq}$ recalculado desde cero a $10^{-8}$.

### ✅ Intercambiador de DOS corrientes (Completado)
- Lo que pierde la caliente lo gana la fría. Frente al intercambiador de una corriente, que recibe un $Q$ de la nada como si existiera un servicio infinito, este **acopla dos puntos del diagrama**: es lo que permite integración energética.
- Tres especificaciones (Q, T de salida caliente, T de salida fría), mutuamente consistentes: verificada la ida y vuelta entre ellas a $10^{-6}$ K.
- **Guarda de segunda ley**: se comprueba que no haya cruce de temperaturas. Sin ella el balance de energía se cumple tan contento con un equipo imposible de construir. Verificado que un cruce se rechaza explicando cuál es la aproximación y dónde.
- Y para el solver es el caso interesante: es el **único equipo cuyas dos entradas pueden venir de ramas distintas** del diagrama.

### ⚠ Dos defectos del SOLVER, encontrados al combinar
Los dos aparecieron montando la planta de prueba, no probando equipos sueltos. Es el patrón de siempre en este proyecto.

**1. La heurística de corte mentía con lazos entrelazados.** `tiene_anclaje_externo` preguntaba si la otra entrada del consumidor venía de fuera **de ese ciclo concreto**. Con varios lazos que comparten equipos, una corriente que viene de OTRO lazo parecía "externa" — pero no es una alimentación fresca. Con ese falso anclaje se elegía cortar `mezcla`, la salida del mezclador, que es justo el corte que el roadmap ya documentaba como el malo: suponerla con F=0 deja sin caudal a todo lo que viene detrás. Síntoma: *"el lazo no se puede cerrar: siguen sin determinarse 11 variables"*, que apunta a datos que faltan cuando no falta ninguno. **Corregido**: se mide contra los equipos de TODOS los ciclos. Ahora corta `reciclo_v` y `reciclo_l`, que es lo correcto.

**2. El supuesto inicial F=0 no vale para un corte que no es un reciclo.** Un intercambiador que precalienta la entrada de un reactor con la salida de ese mismo reactor cierra un lazo entre tres equipos **sin una sola corriente fresca dentro**. Ahí F=0 no significa "arrancar sin recirculación" sino "no circula nada", y todos los equipos del lazo se niegan a calcular. **Corregido**: `_estimacion_inicial` distingue los dos casos y, en el no anclado, supone que circula aproximadamente lo que entra fresco a la planta.

### ⚠ Y una fragilidad general: una rama con caudal CERO atascaba el diagrama
El flash de la planta de prueba vaporizaba toda la corriente ($\beta = 1$), así que su salida líquida salía con F=0; el separador de detrás se negaba a calcular y eso tumbaba el reciclo líquido entero.

Una rama seca es **legítima**: una purga puesta a cero, una separación que se lo lleva todo por un lado, o la primera vuelta de un reciclo. El principio correcto, aplicado ahora a seis equipos (separador, compresor, flash, intercambiador, válvula e intercambiador doble):

> F = 0 significa que no circula materia, **no** que no haya estado. La corriente conserva T, P y composición, las cantidades extensivas valen cero, y aguas abajo se sigue resolviendo.

Lo que sí sigue siendo motivo para no calcular es que la **composición** no se conozca: sin ella no hay nada que propagar.

### Verificación
- `tests/validar_operaciones_nuevas.py`: los cuatro equipos por separado, más dos secciones que son el objetivo real de la fase.
- **Planta combinada**: 10 equipos de 9 tipos distintos y dos reciclos. GL = 0 (108 incógnitas, 108 ecuaciones), los lazos convergen en 68 vueltas a $9\times10^{-11}$, y los balances globales por componente cierran con su término $\nu_i\xi$ a $10^{-5}$ mol/s. La integración energética recupera 686 kW y precalienta de 326.6 K a 337.8 K.
- **Rama seca**: una cadena de cinco equipos alimentada con caudal cero resuelve igual, conservando estado y con las cantidades extensivas a cero.
- Plantilla nueva «Integración energética (listo)», que resuelve de un clic y es la que más estresa al solver.
- Sin regresiones: 12/12 suites de Python, 11/11 plantillas, 5 suites de navegador.

### ✅ Las gráficas ya no abren ventanas (Completado)
- `config/graficos.py` fija el backend `Agg` salvo que se defina `MPLBACKEND`. Los `graficar_*` de `core/` terminan en `plt.show()`, que con un backend interactivo abre una ventana y **bloquea** el proceso: aparecían encima de lo que el usuario estuviera haciendo cada vez que se importaba el módulo o se corría una suite.
- Efecto secundario medido: McCabe-Thiele bajó de 8.5 s a 1.9 s y Ponchon-Savarit de 7.0 s a 3.1 s, porque ya no renderizan ventanas.

### ✅ Reactor de flujo pistón (PFR) (Completado)
- `core/reactor_pfr.py`. La diferencia con el CSTR no es de detalle, es de modelo, y cabe en una línea: $\xi = V\,r(T,x_{salida})$ frente a $d\xi/dV = r(T, x(\xi))$. En un tanque mezclado la reacción ocurre en todo el volumen a la velocidad de la composición de SALIDA, que es la más pobre y por tanto la más lenta; en un tubo la entrada reacciona a la velocidad del alimento.
- **Hereda de `EvaluadorCSTR`**, porque el balance por componente, la conversión y el balance de energía son exactamente los mismos. Un PFR es la misma estequiometría con otra ley de velocidad integrada.
- **Se integra el AVANCE, no los caudales por componente.** Con una sola variable de estado la estequiometría se cumple por construcción en cada paso; integrando $n_i$ por separado los errores del integrador podrían sacar la composición del simplex.
- El límite estequiométrico se vigila con un **evento terminal**, no dejando que el integrador lo cruce: pasado ese punto las actividades no están definidas y lo que devuelva UNIFAC no significa nada. Misma precaución que ya toman las curvas residuales.
- `volumen_desde_avance` también usa un evento terminal en vez de root-finding sobre V: **una sola integración** en lugar de una por iteración, y el volumen sale exacto en el punto del evento.
- Verificado: a igual volumen el PFR convierte más que el CSTR (razón 1.14–1.29), ida y vuelta $V \to \xi \to V$ exacta, y volumen cero da avance cero.
- **La comprobación cruzada que más vale**: con $V$ grande el PFR alcanza $\xi = 27.2532$ mol/s, y el reactor de EQUILIBRIO da 27.2532 por otro camino completamente distinto (van't Hoff en vez de integrar la cinética). Dos módulos, el mismo número.

### ✅ Absorbedor / desorbedor (Kremser) (Completado)
- `core/absorbedor.py`. Abre una familia de equipos que no existía: lavado de gases, absorción, desorción. Es un método de atajo, igual que FUG lo es para destilación.
- **El mismo bloque absorbe y desorbe.** Se escribe la fuerza impulsora como $y_{ent} - K x_{ent}$ y no solo como $y_{ent}$: si el líquido entra más cargado de lo que el equilibrio admite, el transferido sale NEGATIVO y el componente pasa del líquido al gas. Un absorbedor y un stripper son el mismo equipo con el gradiente al revés, y así no hay que escribir dos.
- **Las tres ramas de la fórmula de Kremser, cada una con su problema numérico:**
  - $A = 1$ es $0/0$. Y no es un caso de laboratorio: es donde se diseñan muchas columnas. Se trata aparte con el límite $N/(N+1)$.
  - $A > 1$ con $N$ grande **DESBORDA**: $A^{N+1}$ se va al infinito y da `inf/inf = NaN`. Medido: con $A=2.8$ revienta hacia $N\sim1000$. Se arregla dividiendo arriba y abajo por $A^{N+1}$, que es lo mismo algebraicamente pero hace aparecer $A^{-N}$, que tiende a cero.
  - $A < 1$ con la forma original ya es estable.
- Verificado en los tres regímenes: $A<1$ tiende a $A$ aunque $N\to\infty$ (más etapas no compensan un disolvente insuficiente), $A>1$ tiende a 1 sin desbordar ni con $N=10^5$, y $A=1$ da $N/(N+1)$ exacto.
- Las cotas físicas se comprueban: si Kremser predice transferir más de lo que hay disponible, significa que se está usando fuera de su rango (sistema no diluido) y **se avisa** en vez de recortar en silencio.
- Balance por componente exacto (0.00e+00).

### ⚠ Un error opaco corregido de paso
Al probar el absorbedor con metano como gas portador salió `'NoneType' object has no attribute 'items'`, que no menciona ni el componente culpable ni la causa.

El motivo: **UNIFAC es por contribución de grupos**, y `thermo` no sabe descomponer los gases permanentes (metano, nitrógeno, hidrógeno, aire). `ProveedorTermodinamico` comprueba ahora los grupos al construirse y lo dice con nombre y propuesta. Es una limitación REAL del modelo del proyecto, no un fallo: sin grupos no hay $\gamma$ que calcular.

### Verificación de la tanda
- 12/12 suites de Python (la nueva, `validar_operaciones_nuevas.py`, cubre ya ocho secciones).
- 11/11 plantillas y 5 suites de navegador.
- Los dos equipos nuevos están en la API y en la interfaz desde el primer día.

**El núcleo llega a 14 métodos de equipo** (15 tipos contando los dos modos del reactor): columna binaria, columna FUG, flash, separador, absorbedor, CSTR, reactor de equilibrio, PFR, intercambiador, intercambiador de dos corrientes, válvula, bomba, compresor/turbina, mezclador, divisor.

### ⬜ Y aquí se acaban las operaciones fáciles
Lo que queda **no es "otro equipo más"**, son las piezas de física que faltan disfrazadas de equipos:

- **Extracción líquido-líquido** necesita equilibrio líquido-líquido.
- **Columnas con extracciones laterales y varias alimentaciones** necesitan MESH: los métodos de atajo no las admiten.
- **Destilación azeotrópica y extractiva** necesitan las dos cosas.

Sólidos (cristalizadores, secadores, filtros) quedan fuera a propósito: distribución de tamaño e hidrodinámica son otro proyecto.

Lo siguiente que más multiplica lo ya construido NO es un equipo, y es lo que hace la Fase 9:

- **Especificaciones de diseño a nivel de diagrama** — hoy se puede invertir dentro de un bloque (dar N y obtener R), pero no decir "ajusta el reciclo hasta que el producto salga al 99 %". La arquitectura es inusualmente buena para esto: ya existen el pool, el contador de grados de libertad y la detección de redundancias.
- **Barridos de sensibilidad** — no hay ninguno, y la pregunta real de un alumno no es "¿cuánto da?" sino "¿qué pasa si subo el reflujo?".

---

# Fase 9: De calcular a diseñar

Hasta aquí el simulador contestaba *"con estos datos, ¿cuánto da?"*. Las dos piezas de esta fase contestan las dos preguntas que de verdad se hacen al diseñar: *"¿qué hace falta para conseguir esto?"* y *"¿qué pasa si cambio aquello?"*.

Ninguna de las dos es un equipo. Son las que más multiplican los 14 que ya hay.

### Por qué esta arquitectura lo permitía casi sin esfuerzo
Vale la pena dejarlo escrito, porque explica por qué esto salió barato:

- **El pool es plano y las variables tienen nombre global** (`s1.F`, `col1.R`, `r1.xi`). Una especificación es literalmente un par de nombres. Si cada equipo guardara su propio estado haría falta tubería para cruzar el diagrama.
- **El conteo de grados de libertad ya existía y es estructural.** Una especificación añade una ecuación y el contador lo confirma solo. En un simulador secuencial-modular eso se razona a mano.
- **8 bloques ya son invertibles** (`puede_resolver` admitiendo incógnitas), así que cuando la variable manipulada vive dentro de uno de ellos puede no hacer falta lazo exterior ninguno.
- **El motor de reciclos tiene exactamente esta forma**: suponer, resolver, mirar el error, corregir. Esto reutiliza maquinaria ya validada en vez de inventar otra.
- `verificar_consistencia` ya hacía *"recalcula esta variable desde su bloque y compara"*, que es la evaluación de residuo que una especificación necesita.

### ✅ Especificaciones de diseño (Completado)
- `core/especificaciones.py`. Una especificación es `objetivo == valor` moviendo una variable manipulada, con un rango de búsqueda.
- **El rango no es un detalle de implementación**: casi toda variable de proceso tiene un rango físico (un reflujo no es negativo, una fracción no pasa de 1), y acotar la búsqueda es lo que evita que el solver se vaya a un sitio donde el diagrama ni se puede resolver.
- Una sola especificación se resuelve con `brentq` —sin derivadas, que aquí costarían una resolución completa del diagrama cada una— y varias con `root`.
- **Los residuos de varias especificaciones se ESCALAN por el valor objetivo.** Sin escalar, una sobre una fracción molar (orden 1) y otra sobre un calor (orden 10^6) no pesan lo mismo y el solver sacrifica la primera. Es el mismo problema que ya apareció en el reactor acoplado de la Fase 4.

**Error de contabilidad, encontrado al medirlo.** La primera versión sumaba una ecuación Y una incógnita por especificación, razonando que "se libera la variable manipulada". Falso: esa variable **ya estaba contada** como incógnita, precisamente porque no se da como dato. El contador decía GL = 1 sobre un problema perfectamente cerrado. Lo correcto es que una especificación suma **solo una ecuación**: no reformula el problema, lo CIERRA. Verificado: GL = 1 sin ella, GL = 0 con ella.

**Verificado contra el camino directo**, que es lo único que demuestra que el lazo exterior no miente: pedir N=12 da R=2.241647, y evaluar McCabe-Thiele con ese R devuelve N=12.00000000 sin pasar por el lazo.

**Y el caso que justifica haberlo construido**: objetivo y variable manipulada en equipos distintos, con reciclo en medio. Pedir 0.9055 de MTBE en el producto —que está tras un reactor, un flash y un separador— ajustando la temperatura del reactor da 348.97 K en 12 resoluciones, cada una con sus reciclos convergidos. Error 5.7e-12. Es lo que un simulador secuencial-modular hace con dificultad.

**Mensajes de error en tres niveles**, que resultó valer: al probar un rango hasta 380 K la cadena dijo *especificación falló* → *el diagrama no determina 'producto.x2'* → *h_V(T) deja de crecer cerca de 408.9 K, zona cercana a la crítica*. Cada capa aporta algo. Un primer intento del mensaje mandaba a "buscar datos que faltaran", que es justo donde NO estaba el problema; se corrigió para señalar la causa real (el valor de la manipulada no es viable).

### ✅ Barridos de sensibilidad (Completado)
- `DiagramaCorrientes.barrido(variable, valores, seguir=...)`. No es una herramienta de cálculo sino de comprensión: la pregunta de quien aprende no es *"¿cuánto da?"* sino *"¿qué pasa si subo el reflujo?"*.
- **Un punto que falla NO tumba el barrido**: se anota el motivo y se sigue. Es lo que se quiere al explorar — ver el rango útil con sus bordes, en vez de perder 19 puntos buenos porque el vigésimo pinchaba. Verificado con dos puntos por debajo de R_min.
- El compromiso clásico sale solo: de R=1.6 a R=10, N baja de 19.5 a 7.5 y Q_c sube de 3.1 a 13.2 MW.

### ✅ Las dos cosas en la API (Completado)
- `POST /diagrama/resolver` acepta `especificaciones`; si vienen vacías el camino es el de siempre. `POST /diagrama/grados-libertad` también, para que el aviso en vivo cuente igual que el resultado. Y `POST /diagrama/barrido`, nuevo.
- **La frontera comprueba solo que los nombres existan.** Es el error más fácil de cometer por HTTP y el más opaco si no se detecta ahí: una errata haría que el lazo gastara resoluciones enteras para acabar diciendo que un objetivo *"no se determina"*, que suena a problema de física. El resto lo valida `core.especificaciones`, y duplicarlo crearía dos sitios donde la regla puede divergir.
- **`/diagrama/barrido` hace lo contrario que el resto de la API, a propósito**: un punto que no converge devuelve **200** con el punto marcado y su motivo, no un 422. El borde de la zona viable es parte de lo que se quiere ver. El 422 queda para lo que invalida el barrido entero: variable inexistente, barrer una que también se da como dato, o pasar del tope de 40 puntos — tope que existe porque cada punto es una resolución completa del diagrama.
- Se reporta `evaluaciones`: cuántas resoluciones completas costó el lazo. Es el coste real y no debe ser una sorpresa.

### ⚠ Un defecto real que destapó la suite de la API
`tests/validar_api_especificaciones.py` no duplica la física; comprueba lo único que la frontera puede romper sola. Y en la primera pasada encontró algo que **no estaba en la frontera sino en el núcleo**:

`barrido` trataba "fallar" como una sola cosa —que `resolver` lance una excepción— cuando son dos. La segunda es que **resuelva sin lanzar nada y deje la variable seguida sin determinar**, que es exactamente lo que hace una columna por debajo de su reflujo mínimo: el bloque no revienta, se declara *no disparable*. Ese punto volvía con `_completo = False`, `_error = None` y `N = None`: **se contaba como bueno, y venía vacío.**

Lo interesante es **por qué la suite del núcleo no lo vio**: contaba los fallos por `_completo`, que sí era `False`. La de la API contaba por `_error`, como hace la frontera de verdad, y reportó cuatro puntos resueltos con dos de ellos vacíos.

Corregido en `core/diagrama_corrientes.py`: se comprueba si llegó lo que se pidió seguir (o, sin `seguir`, si el diagrama quedó completo) y el motivo se saca de `errores_bloque`, que ya lo tenía con el número que explica el borde — `R=1.0000 <= R_min=1.1115: requeriría etapas infinitas`. Inventar un mensaje nuevo habría perdido ese $R_{min}$. Y se añadieron cuatro comprobaciones al núcleo para que el agujero no vuelva.

**Y una incompatibilidad de versiones anotada de paso**: `fastapi.testclient.TestClient` no arranca con las versiones fijas del proyecto — el starlette que arrastra fastapi 0.104 le pasa `app=` a `httpx.Client`, y httpx 0.28 quitó ese argumento. La suite monta el cliente sobre `httpx.ASGITransport`, que es lo mismo por debajo y prueba la app real sin abrir puerto. `httpx` pasa a estar fija en `requirements.txt` por derecho propio.

### Verificación
`tests/validar_especificaciones.py`: 21 comprobaciones. Una especificación contra el camino directo, una a través de dos equipos y un reciclo, dos a la vez, cinco casos que deben rechazarse (objetivo = manipulada, rango al revés, manipulada dada como dato, objetivo inalcanzable con el rango que sí se recorre, valor inviable), y los barridos con sus bordes.

`tests/validar_api_especificaciones.py`: 37 comprobaciones sobre la frontera HTTP. La que más vale es la que compara el $R$ del endpoint con el del núcleo **construyendo el diagrama con la misma función que usa la API** — no contra una constante escrita a mano, que se quedaría obsoleta en silencio. Y una que parece tonta y no lo es: que la respuesta serialice a JSON de verdad, porque un `float32` de NumPy pasa los tipos de Pydantic y revienta al serializar.

14/14 suites de Python.

### ✅ La pestaña «Diseño» en la interfaz (Completado)
`frontend/app/flowsheet/Diseno.tsx`. Las dos cosas en la pantalla, no solo en Python.

- **Los desplegables se llenan en local**, con las mismas funciones que usa el panel lateral, en vez de pedir la lista de variables al servidor. Importa porque la lista hace falta **antes** de la primera resolución — que es justo cuando se plantea un objetivo de diseño.
- **La frontera de unidades, con el detalle que es fácil pasar por alto**: el valor pedido está en la unidad del OBJETIVO y el rango en la de la MANIPULADA. Son variables distintas y pueden tener unidades distintas (pedir una temperatura en °C moviendo un caudal en kg/h).
- **La vista avisa antes de gastar una petición** de lo que ya se sabe que está mal, y dice el arreglo. El caso que más desconcierta: la variable manipulada dada también como dato. La especificación la convierte en incógnita, así que las dos cosas a la vez son ambiguas; el botón se queda deshabilitado con el motivo escrito al lado.
- **El resultado se vuelca al estado común**, así que una resolución con especificaciones se puede ver en «Resultados» con sus gráficas como cualquier otra.
- **La gráfica del barrido corta el trazo en los puntos inviables** y los marca con una cruz en el eje, en vez de interpolar por encima. Una línea continua que cruza la zona inviable mentiría sobre justo lo que el barrido sirve para encontrar.
- Se muestra el coste (`Costó 13 resoluciones completas del diagrama`) en lugar de esconderlo.

`frontend/verificar_diseno.mjs`, 27 comprobaciones en navegador. **La que justifica la suite**: que el número de la pantalla sea el del núcleo — se pide N = 12 por la interfaz y se exige que aparezca R = 1.659379, el mismo valor que calcula Python. Un simulador que calcula bien y muestra otra cosa está roto igual.

### ⚠ Dos suites que estaban rojas por motivos viejos
- **`verificar_masa_numerica.mjs` llevaba roto desde que las simulaciones pasaron al almacenamiento del navegador**: entraba directo a `/flowsheet` sin simulación abierta, así que «+ Corriente» no hacía nada, no se mandaba ninguna petición y la suite se quedaba muda. Y además afirmaba un contrato que el proyecto ya había cambiado a propósito: daba por hecho que el navegador convertía kg/h → mol/s y mandaba `valores["s1.F"]`. No lo hace, porque **masa ↔ moles no es una conversión afín** — depende de la composición de esa corriente — así que el caudal másico viaja aparte en `caudales_masicos` [kg/s] y la división es una ECUACIÓN del núcleo. Corregida la suite al contrato real, y **exigiendo ahora los dos números** en vez de uno: 8.5125 kg/s desde el navegador (conversión afín) y 100 mol/s desde el núcleo (la que necesita la MW de la mezcla).
- De paso, un número que explica algo: el núcleo deduce **99.99985** mol/s, no 100.00000. No es un error. Las MW de la interfaz están redondeadas (78.11, 92.14) y el núcleo usa las de `thermo` a propósito, para que el caudal másico sea una variable del sistema y no dependa de que el navegador tenga la MW cacheada.

### Verificación de la tanda
- 14/14 suites de Python.
- 14/14 suites de navegador (una nueva, una resucitada).

### ⬜ Lo que sigue
Con esto, **lo que queda ya no se puede añadir "por los lados"**:

- **Varias reacciones a la vez** ($\nu$ a matriz) — el cambio estructural que falta para destilación reactiva real.
- **MESH** — y con él las columnas de extracciones laterales y varias alimentaciones.
- **Equilibrio líquido-líquido** — y con él la extracción y los sistemas con agua.
- **Fase vapor no ideal** — el compresor supone gas ideal y el reactor de MTBE opera a 5–30 atm, que es donde esa suposición empieza a fallar.

---

# Fase 10: Lo que decía algo falso

Cuatro cosas que no eran huecos de física, sino afirmaciones incorrectas en el producto, en el CI o en el contrato de la API. Se agrupan porque comparten un patrón: **ninguna rompía nada al ejecutarse, y por eso ninguna se había notado.**

### ✅ La interfaz decía «Reactor — pendiente» (Completado)
Con tres reactores en el catálogo (CSTR, equilibrio, PFR). Era una afirmación falsa sobre la propia capacidad del programa, de las peores que puede tener una interfaz: quien la leyera concluiría que el simulador no reacciona.

Se conserva el hueco, porque declarar los límites a la vista es una costumbre que vale, pero diciendo **lo que sí está pendiente y por qué**: «Extracción lateral — necesita MESH». Una columna con extracciones laterales o varias alimentaciones no se puede resolver con métodos de atajo. Lo que falta no es una entrada en el catálogo, es la física.

### ✅ Dos motores igual de visibles, sin decir cuál es el de ahora (Completado)
`/flowsheet/*` usa el modelo ANTIGUO (`core/diagrama_flujo.py`), donde las corrientes no son objetos de primera clase y la información fluye en una sola dirección. `/diagrama/*` lo sustituyó. En `/docs` los dos salían igual, así que cualquiera podía empezar por el equivocado — y **los ejemplos de un modelo no valen en el otro**.

Marcados los tres endpoints con `deprecated=True`, que la documentación automática pinta tachados. **No se borran**: `core/diagrama_flujo.py` sigue teniendo dos consumidores legítimos — `OperacionUnitaria`, que `core/columna_destilacion.py` importa, y `tests/validar_diagrama_flujo.py`, que comprueba los mismos números por otro camino. Borrarlo quitaría esa red.

### ✅ Trece de las catorce suites de navegador no se ejecutaban nunca (Completado)
El CI corría **una**: la única que no necesita navegador. Las otras trece —las que comprueban lo que ninguna suite de Python puede ver, que el número correcto llegue a la pantalla— solo se ejecutaban cuando alguien se acordaba. Tenerlas así es casi lo mismo que no tenerlas.

**Lo que lo impedía era una línea**, repetida catorce veces:

```js
const EDGE = "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe";
```

Ahora la ruta se resuelve en `frontend/navegador.mjs`: `NAVEGADOR_PRUEBAS` si está puesta, y si no la primera de una lista por sistema operativo. El error, cuando no hay ninguno, dice dónde se buscó y cómo arreglarlo — un `Browser was not found at the configured executablePath` con una ruta sola no aclara si falta el navegador o si la ruta está mal escrita.

Con eso, el CI gana un trabajo que levanta la API, compila y sirve el frontend, instala Chromium y corre las catorce. Espera a que cada servidor **responda** en vez de dormir un número inventado de segundos: la primera carga importa `thermo`, que no es rápida.

### ✅ El lanzador leía los resultados con `grep` (Completado)
`frontend/verificar_todo.mjs`, el equivalente de `run_tests.py` para el navegador. Importa por una razón concreta: **cada suite termina con un mensaje distinto** (`TODO OK`, `TODAS LAS PLANTILLAS OK`, `OK: la conversion...`), así que buscar una frase en la salida **da por buena una suite que acaba de reventar con otra frase**. Todas devuelven `process.exit(0|1)` correctamente, así que el código de salida es lo único que hay que mirar.

Además declara qué necesita cada suite —nada, la API, o la API más el frontend más un navegador— y lo comprueba **antes** de correr ninguna. Un servidor caído no es «fallan las suites», es que no se han podido correr, y decirlo así ahorra leer doce rastros de pila idénticos para descubrir que faltaba levantar `uvicorn`.

### ✅ Dieciséis endpoints sin prueba de frontera (Completado)
Solo `/diagrama/*` la tenía. Los demás estaban cubiertos de refilón —las suites de navegador los usan al pasar— pero eso significa que un fallo de frontera se manifestaba como «la gráfica no aparece», a ocho capas de la causa.

`tests/validar_api.py`, 42 comprobaciones. La idea que más rinde: **encadenar en vez de inventar cargas.** Los presets de `/ejemplos` ya SON peticiones válidas de `/columna/resolver`, y los de `/flowsheet/ejemplos` lo son de `/flowsheet/resolver`. La suite los pide y los reenvía. Eso prueba dos endpoints de una vez y, sobre todo, prueba algo que una carga escrita a mano no puede probar: **que el preset que la interfaz le ofrece al usuario de verdad se resuelva.** Un preset roto es un fallo que se encuentra en el primer clic.

Y una comprobación que parece tonta: que cada respuesta serialice con `allow_nan=False`. `json.dumps` acepta NaN por omisión y escribe `NaN`, que **no es JSON válido** y que el `JSON.parse` del navegador rechaza. Un hueco numérico mal gestionado llega hasta ahí con esa cara.

### ⚠ Lo que encontró, y mis propias suposiciones equivocadas
De los cuatro fallos de la primera ejecución, **tres eran de la suite y uno del contrato**:

- **Del contrato:** el campo `requiere_masa_molar` de `/unidades` describía lo contrario de lo que hace. Decía *«si es true, la conversión NO es afín»*, y desde que el caudal másico pasó a ser una ECUACIÓN del diagrama ya nunca es true. La descripción se quedó señalando a un modelo que el proyecto había abandonado a propósito. Corregida para decir que es siempre `false`, por qué, y **qué debe mirar el cliente en su lugar** (`variables["F"]`, donde se ve que F admite base másica).
- **Mías:** el parámetro se llama `q`, no `nombre`; `/elv/binario` devuelve `n_puntos` **interiores** más los dos componentes puros, así que 20 dan 22; y `x = 0.5` no cae en la malla salvo que `n_puntos` sea impar, así que el punto de burbuja del 50/50 hay que interpolarlo (365.5236 interpolado contra 365.5157 exacto — y por eso la tolerancia es 0.1 K y no 1e-9: se comprueba que el endpoint devuelva LA MISMA curva, no que acierte un punto que no calculó).

Y una cuarta suposición mía que resultó enseñar algo: esperaba que buscar un componente inexistente diera 404. Da **200 con `encontrado: false`**, y es deliberado — esto es una BÚSQUEDA, y «no existe» es una respuesta válida que el buscador debe poder mostrar mientras se teclea. Un 404 convertiría cada pulsación en un error. Mejor aún, el endpoint separa dos banderas que son distintas: el metano **se encuentra** (existe, tiene MW) pero **no es apto** (sin grupos UNIFAC no hay γ). Si estuvieran fundidas en una, el usuario elegiría metano y el fallo saldría mucho después, al resolver. Eso ahora está comprobado.

### Verificación de la tanda
- 15/15 suites de Python.
- 14/14 de navegador, y por primera vez **todas** desde un solo comando y desde CI.

---

# Fase 11: Varias reacciones a la vez

El simulador se llama de destilación reactiva y hasta aquí admitía **una** reacción. Casi ningún sistema real tiene una sola, incluido el caso de referencia del propio proyecto:

```
R1:  isobuteno + metanol  →  MTBE          (la que se quiere)
R2:  2 isobuteno          →  diisobuteno   (la que estorba)
```

Las dos consumen isobuteno, y ese acoplamiento —la **selectividad**— no se puede ni plantear con una reacción.

### La decisión de diseño que gobierna todo lo demás
`nu` pasa a admitir un vector (una reacción, como siempre) o una matriz `n_reacciones × n_componentes`. Internamente **siempre** se trabaja con la matriz, así que no hay dos caminos de código que puedan divergir.

Lo importante es qué pasa con los nombres en singular. `dH_rxn`, `K_eq()`, `velocidad_reaccion()` **lanzan error** con varias reacciones en vez de devolver la de la primera o la suma. El motivo:

> Un balance de energía escrito como `xi * dH_rxn` es correcto con una reacción y **silenciosamente falso** con tres. Si devolviera el de la primera, ese balance seguiría corriendo y dando un número plausible construido sobre algo imposible.

Que reviente obliga a usar las versiones en plural, que son las correctas. Es el mismo criterio que gobierna el resto del proyecto, aplicado a una API en vez de a un cálculo.

### ✅ Capa termodinámica (Completado)
- `GestorReaccion` con `A` y `Ea` por reacción (un escalar significa «el mismo para todas», que es lo razonable al tantear).
- `velocidades(T, x)` pide **γ una sola vez** y lo reparte entre todas las reacciones. No es un ahorro menor: UNIFAC es lo más caro de todo el cálculo, y pedirlo por reacción multiplicaría por $n_r$ el coste de cada evaluación — que ocurre dentro de un lazo de Newton, que ocurre dentro del lazo de reciclos.
- `desplazamiento_composicion` y `calor_liberado` viven **aquí y no repetidos en cada reactor**, porque son las dos piezas que cambian de forma al pasar de una reacción a varias: $\nu\,\xi$ se convierte en $NU^T\xi$, y el calor en $\sum_j \xi_j \Delta H_j$. Tenerlas en un solo sitio es lo que evita que un reactor se quede con la versión escalar.

### ✅ Los tres reactores (Completado)
`EvaluadorCSTR` y `EvaluadorPFR` generalizados. Con una reacción se comportan **exactamente** igual que antes: los avances entran y salen como escalares y ningún número validado se mueve.

Tres métodos **no se generalizan sin cambiar de significado**, y eso se dice en vez de disimularlo:

| Método | Por qué cambia |
|---|---|
| `avance_desde_fraccion` | Una fracción de salida determina UN avance. Con $R$ reacciones hacen falta $R$ fracciones, y el sistema pasa a ser lineal de $R\times R$ → `avances_desde_fracciones`, todavía **exacto, sin iterar** |
| `volumen_desde_avance` | Un solo volumen tiene que satisfacer las $R$ ecuaciones cinéticas a la vez, así que un juego cualquiera de avances **no es alcanzable**. Pasa de ser una inversión a ser una **comprobación**: se fija $V$ con una reacción y se verifica que las demás cuadren |
| `_limite_estequiometrico` | Con varias no existe un avance máximo único: cuál es el reactivo que se agota antes depende de cuánto avance cada reacción. El límite es una superficie, no un escalar |

Y dos cosas más que cambian de fondo:

- **El evento terminal del PFR.** Con una reacción basta vigilar un avance; con varias se vigila la **composición**, parando cuando algún componente se queda sin moles. El camino de una reacción conserva su evento de siempre, para que sus números no se muevan por un cambio que no les afecta.
- **El equilibrio simultáneo.** Con una reacción el avance se encierra entre dos límites estequiométricos y `brentq` no puede escaparse. **En $R$ dimensiones no existe el bracket**: la región factible es un politopo y no hay cambio de signo que encerrar. Se resuelve con `root`, en logaritmos, con residuo grande fuera del simplex, varios arranques (uno de ellos con avance **negativo**, para el caso de un reciclo que devuelve producto) y sin confiar en `sol.success`.

### Verificación
`tests/validar_varias_reacciones.py`, 78 comprobaciones. **No hace falta literatura externa para esta capa**, porque hay invariantes que se comprueban contra el caso de una reacción, que ya estaba validado:

- **Partir una reacción en dos mitades idénticas** ($A/2$ cada una) da el mismo resultado que la reacción entera. Es la prueba más fuerte que existe aquí: pasa por la estequiometría matricial, por las productorias por filas, por los arranques del solver y por el balance de energía, y solo sale igual si las cuatro están bien. Verificado en velocidad, calor, composición, volumen, caso acoplado, equilibrio y conversión.
- **Dos reacciones con componentes disjuntos** dan exactamente lo mismo que resueltas por separado. Si las productorias se hicieran sobre la matriz entera en vez de por filas, aquí se vería.
- **Duplicar la estequiometría eleva $K_{eq}$ al cuadrado** (porque $\Delta G$ se duplica) e **invertir la reacción invierte $K$**. Son identidades termodinámicas, no convenciones del código.
- **Dos reacciones opuestas con el mismo avance dan calor cero exacto.**
- Y la comprobación cruzada que más vale: **un tubo muy largo llega al equilibrio simultáneo de las dos reacciones**, $\xi = [8.239583,\ 20.151557]$ por los dos caminos, con diferencia máxima **1.8e-10 mol/s**. Integrar dos EDO acopladas y resolver un sistema $2\times2$ de van't Hoff no comparten ni una línea de código más allá de la estequiometría.

### ⚠ Dos resultados que contradijeron lo que yo esperaba
**El calor.** La dimerización libera **−110.7 kJ/mol**, casi el doble que la reacción principal (−57.6). En un caso con $\xi_1 = 40$ y $\xi_2 = 5$ mol/s, ignorar la secundaria **subestima la refrigeración un 24 %**. Esto no es un detalle académico: la refrigeración suele ser la restricción de diseño.

**La selectividad.** Escribí la comprobación como «la selectividad empeora al subir el volumen» y **falló**. Tiene un **máximo interior** — hay un volumen óptimo — y el mecanismo se verificó en vez de suponerlo:

$$r_1 \propto a_{iso}\,a_{MeOH} \quad\text{(primer orden en isobuteno)}$$
$$r_2 \propto a_{iso}^2 \quad\text{(SEGUNDO orden)}$$

La secundaria retira isobuteno extra, así que $a_{MeOH}/a_{iso}$ **crece** a lo largo del tubo (0.880 → 12.69, comprobado). Y como $r_2$ depende del cuadrado, agotar isobuteno la castiga **más** que a la principal: la selectividad *mejora* al principio. Luego la principal se acerca a su propio equilibrio ($K_1 = 4.14$, modesto) y se frena, mientras la secundaria ($K_2 = 488$) sigue corriendo, y entonces se desploma: de 0.9790 en el óptimo ($V = 3$ m³) a 0.2796 con $V = 10^4$ m³. **Control cinético pasando a control termodinámico**, que es un fenómeno de libro y que con una sola reacción no se puede ni plantear.

Detalle que vale la pena: $a_{MeOH}/a_{iso}$ arranca en **0.880 con alimento 50/50**, no en 1. Los coeficientes de actividad no son 1, y haber razonado sobre fracciones molares en vez de actividades habría dado otra conclusión.

### ✅ Las dos reacciones atraviesan el diagrama (Completado)
No basta con el núcleo: el pool tiene que nombrarlas, el contador de grados de libertad contarlas y el solver resolver con ellas.

- **El nombre en el pool.** Con una reacción sigue siendo `r1.xi`; con varias pasa a `r1.xi0`, `r1.xi1`, con la misma convención que `s1.x0`. Conservar `xi` en el caso de una **no es cosmética**: ese nombre está escrito en las plantillas, los ejemplos, las suites y dentro de cada enlace compartible ya generado. Renombrarlo a `xi0` los rompería todos a la vez, y a cambio de nada.
- Igual con `K_eq` → `K_eq0`, `K_eq1`, y el bloque de equilibrio pasa a aportar **2 ecuaciones por reacción**.
- **La dirección de diseño funciona**, y es la que importa: dadas dos fracciones del producto, salen los dos avances — exacto, sin iterar, porque el sistema sigue siendo lineal (ahora de $R \times R$). Verificado: $\xi = [18.000000000,\ 4.000000000]$.
- **Dar solo la conversión ya no basta**, y se dice: una sola conversión no reparte el consumo del reactivo entre las reacciones que compiten por él. Antes de inventar un reparto —a partes iguales, por ejemplo, que sería una suposición presentada como resultado— se explica qué dar en su lugar.
- **La cinética se niega cuando toca.** Con $\xi = [18, 4]$ el bloque informa: *«con V=4.68 m³ (fijado por la reacción 0) la reacción 1 daría 0.1506 mol/s y se pidió 4»*. Un solo tanque no entrega un juego cualquiera de avances, y el mensaje trae los números.
- El calor sale **mayor** que el de la principal sola: −1.4796 MW frente a −1.0368 MW. Esa diferencia es exactamente la refrigeración que un modelo de una reacción no vería.

**Un límite que ya existía y que conviene no confundir con esto:** la dirección «dados $T$ y $V$, hallar $\xi$» no la resuelve el motor de punto fijo, porque $\xi$ necesita $x_{salida}$ y $x_{salida}$ necesita $\xi$. **Pasa igual con una reacción** —se comprobó— y para eso está `resolver_con_cinetica`, que plantea las dos ecuaciones a la vez. No es una regresión del cambio a varias reacciones.

### ✅ En la API y en la interfaz (Completado)
- `OperacionDiagrama.reacciones` (lista) junto al `reaccion` de siempre. Mandar los dos **se rechaza**: no hay forma de saber cuál gana. Con una sola reacción la petición no cambia ni un byte, así que un diagrama guardado o un enlace compartido sigue funcionando igual.
- **La validación estaba triplicada** —CSTR, reactor de equilibrio y PFR hacían cada uno su copia del mismo chequeo— y con el campo nuevo habrían sido seis copias. Ahora hay una: `_reaccion_de`, que además dice el motivo en los términos de cada equipo (el de equilibrio la necesita para $K_{eq}$, el PFR para tener algo que integrar).
- **El editor del panel** permite añadir y quitar reacciones. La nueva arranca **vacía, no copiando la anterior**: dos reacciones con la misma estequiometría son indistinguibles y el sistema que reparte los avances sale singular. Copiarla parece un atajo amable y lleva derecho a un error que cuesta entender.
- **Arrhenius va DENTRO de cada reacción.** Cada una tiene su propia velocidad, y es justo esa diferencia la que decide la selectividad; tenerlo fuera sugeriría que lo comparten.
- `nu`/`A`/`Ea` se mantienen sincronizados con la primera reacción. Eso es lo que permite abrir un diagrama de varias reacciones en una versión anterior de la interfaz y que al menos la principal siga ahí.

**La regla de nombres está escrita dos veces**, en `clavesAvance` (TypeScript) y `_claves_xi` (Python), y eso es una duplicación real. La alternativa sería pedirle al servidor la lista de variables antes de poder dibujar un reactor, y la interfaz las necesita **antes** de la primera resolución. Se elige duplicar la regla y que una suite de navegador compruebe que las dos coinciden.

### Verificación de la interfaz
`frontend/verificar_varias_reacciones.mjs`, 24 comprobaciones. La que justifica la suite: **el número de la pantalla es el del núcleo**. Se monta el reactor con las dos reacciones por la interfaz y se exige que aparezcan **ξ₀ = 8.240 y ξ₁ = 20.152**, etiquetados como tales y no como dos números sueltos, con sus dos $K_{eq}$ (4.139 y 487.983). Y que la petición mande `reacciones` **sin** mandar también `reaccion`.

Arranca desde un diagrama en el formato ANTIGUO (`nu`/`A`/`Ea`, sin `reacciones`), que es exactamente donde está un diagrama ya guardado, y comprueba que no cambia nada hasta que se añade la segunda.

### ⚠ Tres errores míos en esa suite, y uno que no era mío
- El puerto de entrada se llama `entrada`, no `entrada0`. Con el nombre mal la arista no se mapea, `construirPeticion` lanza *«le faltan corrientes conectadas»* y el `waitForFunction` agotaba **tres minutos sin decir nada**. Se añadió a la espera que también reconozca el error y vuelque lo que hay en pantalla: un timeout ciego es el peor diagnóstico posible.
- `innerText` **aplica `text-transform`**, y la cabecera del panel lleva `uppercase`: llega como «REACCIONES (2)». Las regex sensibles a mayúsculas comparaban contra un texto que el DOM no contiene.
- La interfaz formatea con `formatear`, que redondea a tres decimales, así que hay que buscar `8.240` y no `8.2395`.
- **Y el que no era mío:** las peticiones iban a un **socket huérfano**. Al detener un uvicorn anterior, el puerto 8001 se quedó con dos listeners —el nuevo proceso y el socket del muerto— y las peticiones caían en el viejo, que servía los modelos de Pydantic sin el campo `reacciones`. El síntoma era idéntico a un error de código: el adaptador nuevo respondía con su mensaje nuevo, pero `op.reacciones` llegaba vacío. Se vio al mirar `netstat` y encontrar **dos** líneas en el mismo puerto. Es el segundo puerto que este proyecto pierde así.

### ⬜ Lo que a propósito NO se generaliza
La **transformación de Barbosa-Doherty** (`core/transformaciones.py`) y las curvas residuales reactivas siguen siendo de una sola reacción. Su extensión a varias **no es «el mismo código con un índice más»**: es otra construcción, con un conjunto de componentes de referencia en vez de uno. Se avisa con un error claro en vez de dejar que se use fuera de su rango.

---

# Fase 12: Caída de presión

Hasta aquí la presión se propagaba por igualdad —`P_salida = P_entrada`— en **todos** los equipos salvo la válvula, el compresor y la bomba, que la fijan a propósito. Dos consecuencias, y la segunda es la grave:

1. **Dos equipos en serie salían a la misma presión**, que es físicamente imposible.
2. Un intercambiador podía **esconder que su corriente sale en dos fases**, porque la fracción vaporizada depende mucho de $P$ y se estaba evaluando a la presión equivocada.

### ✅ El modelo (Completado)
`P_{salida} = P_{entrada} - \Delta P`, con $\Delta P$ **parámetro del equipo** y valor por omisión **0**. Con cero es exactamente la ecuación de siempre, así que ningún diagrama guardado ni ningún número validado se mueve.

**Por qué parámetro y no variable del pool.** Como variable sería más elegante —invertible en tres direcciones, como todo lo demás— pero entonces un diagrama que no la diera se quedaría con $P_{salida}$ sin determinar y se paralizaría. Habría que meterle un valor por omisión con su propio bloque, y entonces darla como dato chocaría con ese bloque. Como parámetro, los grados de libertad **no cambian** (sigue siendo una ecuación entre dos presiones) y el caso de siempre no se entera. Y la inversión se conserva igual: de la entrada se deduce la salida y al revés.

### ✅ Dónde aplica, y dónde NO
| Equipo | $\Delta P$ | Por qué |
|---|---|---|
| CSTR, reactor de equilibrio, PFR | `caida_P` | La pérdida en el vaso o a lo largo del lecho |
| Intercambiador | `caida_P` | Fricción del lado del proceso |
| Intercambiador de 2 corrientes | `caida_P_caliente`, `caida_P_frio` | **Dos y no una**: son dos circuitos distintos (tubos y carcasa) con geometrías y caudales distintos. Un número único obligaría a inventar un reparto |
| Absorbedor | `caida_P_gas` | **Solo del lado del gas**: es donde ocurre. El gas sube pagando la fricción del relleno y el líquido baja por gravedad. Un número para los dos lados sugeriría que la pérdida es simétrica |
| Válvula, compresor, bomba | — | Fijan la presión a propósito; una «caída» ahí no significa nada |
| Flash | — | Se le da la presión del tambor directamente |
| Columnas de atajo | — | **Su curva de equilibrio está precalculada a UNA presión.** Un perfil de presión plato a plato necesita MESH: añadir un $\Delta P$ aquí daría un número que el método no respalda |

### El detalle con contenido físico
**El estado de salida se evalúa a la presión de SALIDA**, no a la de entrada. No es un matiz: bajar la presión favorece la vaporización, así que evaluarlo a la presión de entrada **subestimaría el vapor** — y esconder que una corriente sale en dos fases es justo lo que rompe lo que viene detrás.

Medido en un intercambiador de benceno/tolueno a 2 atm con 28 kJ/mol:

| $\Delta P$ | $P_{salida}$ | $T_{salida}$ | $\beta$ |
|---|---|---|---|
| 0 | 2.000 atm | 398.481 K | 0.650986 |
| 0.5 atm | 1.500 atm | 387.667 K | 0.697577 |
| 0.9 atm | 1.100 atm | 376.744 K | 0.741824 |

**9.08 puntos de vaporización** que un modelo sin caída no vería. Y la temperatura de salida baja 21.7 K, que tampoco es despreciable para lo que venga después.

Por eso el campo lleva una **nota al lado** cuando $\Delta P > 0$: sin ella, el resultado se puede leer como un error del simulador cuando es exactamente lo contrario.

### Dónde se rechaza, y cuándo
- **ΔP negativa: al CONSTRUIR el equipo.** Es un error de datos, y descubrirlo en medio de un lazo de reciclos —envuelto en tres capas de *«el bloque no pudo disparar»*— cuesta mucho más que descubrirlo al montar el diagrama.
- **ΔP mayor que la presión disponible: al resolver**, porque depende de la presión de entrada, que es un dato del pool. El mensaje trae **las tres cifras**: *«con una caída de 5.066e+05 Pa la presión de salida sería −3.04e+05 Pa, que no es física. La entrada está a 2.026e+05 Pa»*. Con las tres se ve de un golpe si el error está en la caída o en la alimentación; con una sola hay que ir a buscar las otras.

### Verificación
- `tests/validar_caida_presion.py`, 17 comprobaciones. La primera sección es la que garantiza que nada se mueva: **sin el parámetro y con `caida_P = 0` sale lo mismo, bit a bit**. Después: la caída en las dos direcciones, la acumulación al encadenar tres equipos (3.000 → 2.900 → 2.650 → 2.600 atm), el efecto sobre la vaporización, y los rechazos.
- `frontend/verificar_caida_presion.mjs`, 18 comprobaciones. Mide los tres casos de punta a punta y comprueba que la nota aparece **solo** cuando hay caída: es una explicación, no un aviso.

### ⚠ Dos tropiezos del camino
- La suite de navegador raspaba los números de la pantalla con expresiones regulares y daba `null`: el panel los formatea y los reparte entre dos vistas, así que la primera cifra de seis dígitos que aparece no es necesariamente la que se busca. Reescrita para **leer el pool de la respuesta**, que trae las claves con nombre. Sigue comprobando el camino completo y además dice **qué** variable se mira.
- Y una pérdida de tiempo que conviene anotar: la suite daba β constante en los tres casos porque **el servidor estaba corriendo código viejo** — se había arrancado sin `--reload` y antes de estos cambios. El síntoma era idéntico a «la caída no se aplica». Es el tercer puerto que este proyecto quema por el ciclo de vida de los servidores de desarrollo; la API va ya por el 8003.

---

# Fase 13: Equilibrio líquido-líquido

Abre la familia que faltaba —extracción, decantadores, sistemas con agua— y es la primera pieza de física del proyecto donde **«las ecuaciones cuadran» no demuestra nada**.

### Por qué este equilibrio es distinto de todos los demás
Dos fases líquidas en equilibrio cumplen la igualdad de actividades:

$$x_i^{I}\,\gamma_i(T, \mathbf{x}^{I}) = x_i^{II}\,\gamma_i(T, \mathbf{x}^{II})$$

La estructura es la de un flash líquido-vapor. La diferencia que lo cambia todo:

> Las dos fases se describen con **el mismo** modelo de actividad, así que la solución trivial $\mathbf{x}^{I} = \mathbf{x}^{II}$ cumple todas las ecuaciones. **Siempre.** Para cualquier alimento y cualquier temperatura.

Un flash L-V no tiene ese problema porque sus dos fases tienen modelos distintos. Aquí, un arranque cualquiera converge a la solución trivial con toda probabilidad, y devolvería dos fases idénticas presentándolas como un equilibrio. Por eso el módulo no se limita a resolver: primero decide **si** hay dos fases y luego arranca desde donde esa decisión señala.

### ⚠ La trampa de los dos juegos de parámetros
UNIFAC tiene **dos** juegos de parámetros de interacción, y no son intercambiables:

- `UFIP`, ajustado a datos de equilibrio **líquido-vapor**;
- `LLEUFIP` (Magnussen y otros), ajustado a datos de equilibrio **líquido-líquido**.

Usar el de ELV para predecir ELL es un error conocido y sistemático: la región de inmiscibilidad sale mal, a veces hasta desaparecer. Este módulo usa el de ELL y el resto del simulador sigue con el de ELV para lo suyo. **Son dos modelos, no uno con dos usos.**

Y aquí está lo que convierte eso en una trampa, porque el fallo habría sido silencioso:

| Id de subgrupo | En el juego de ELV | En el juego de ELL |
|---|---|---|
| 16 | **H2O** | P2 |
| 17 | H2CO | **H2O** |
| 18 | CH3CO | ACOH |
| 21 | CH3COO | CHO |

**Los identificadores no coinciden.** `thermo` da la descomposición de cada molécula en los subgrupos del juego de ELV (`Chemical.UNIFAC_groups`), así que pasarla tal cual a las tablas de ELL calcularía las actividades de **moléculas distintas** —el agua tratada como «P2»— y devolvería números plausibles y completamente falsos.

Por eso la traducción va **por nombre de grupo** y no por número, y cuando un grupo no tiene equivalente se dice con nombre y apellido. De los 113 subgrupos del juego de ELV, **49 tienen equivalente**: furfural, por ejemplo, no se puede usar en un cálculo de ELL con UNIFAC, y el error lo dice en vez de calcular con el grupo equivocado.

Medido: para agua/1-butanol a 25 °C y $x_{agua} = 0.1$, $\gamma_{agua}$ sale **3.1289** con los parámetros de ELV y **2.6112** con los de ELL. Un 16.5 % de diferencia sobre el coeficiente que decide si hay separación o no.

### ✅ El módulo (Completado)
`thermodynamics/ell.py`:

- **Análisis de estabilidad** por la distancia al plano tangente de Michelsen. Si existe alguna composición de prueba con $tpd < 0$, la fase única es inestable. Es el criterio correcto y es **independiente** de la igualdad de actividades que resuelve el flash.
- Las composiciones de prueba **no son al azar**: las fases casi puras de cada componente —donde están los extremos de una laguna— y una rejilla sobre la recta que une cada par de componentes puros. Un minimizador general encontraría mínimos espurios cerca de los vértices del simplex, donde los logaritmos divergen.
- **El flash** por sustitución sucesiva sobre $K_i = \gamma_i^{I}/\gamma_i^{II}$ con Rachford-Rice dentro, la misma estructura que `core/flash.py`. Lo que no se parece es el arranque: se parte de la composición que la estabilidad señaló, que es la dirección en la que la mezcla **quiere** separarse.
- Al terminar se comprueba que las dos fases sigan siendo distintas. Dos fases que difieren menos de 1e-4 son la misma, y el «equilibrio» que las separa no significa nada.
- **Convención de orden**: la fase I es la más rica en el componente 0. Sin fijarla, el mismo problema devuelve las fases en un orden u otro según el arranque y comparar dos resultados se vuelve imposible.
- Una sola fase **no es un fallo, es una respuesta**: `flash_LL` devuelve `None`.

### ✅ El decantador (Completado)
`agregar_decantador`: una entrada, dos fases líquidas en equilibrio. De **una etapa a propósito** — una columna de extracción de varias no se resuelve con un método de atajo, necesita el sistema plato a plato.

Cuando no hay separación, toda la alimentación sale por una salida y el equipo declara `separa = 0`, en vez de partirla en dos corrientes idénticas. Sin T de operación, opera a la de la entrada: un sedimentador separa, no calienta.

### Verificación: 40 comprobaciones (32 de ellas **sin literatura externa**)
Las dos que de verdad valen:

**1. La línea de reparto es invariante dentro de la laguna.** En un binario, todas las composiciones globales dentro de la región de inmiscibilidad se separan en **las mismas dos fases**; lo único que cambia es cuánto hay de cada una. Es la propiedad que *define* una línea de reparto, y un flash que convergiera a soluciones triviales o a mínimos espurios daría una línea distinta para cada alimento.

Agua/1-butanol a 25 °C, nueve composiciones globales de 0.55 a 0.95: **dispersión 2.7e-11**. La laguna va de $x_{agua} = 0.533687$ a $0.981454$. Y la regla de la palanca se cumple a **2.8e-16**, que es una comprobación de otra naturaleza — ata el tamaño de las fases a la geometría de la línea sin pasar por el modelo de actividad.

**2. Separarse baja la energía de Gibbs.** El flash resuelve igualdad de actividades, que es la condición de punto *estacionario*. Que ese punto sea un **mínimo** es otra propiedad, calculada por otro camino:

| $z_{agua}$ | $g(z)/RT$ | $g_{2f}/RT$ | $\Delta g$ |
|---|---|---|---|
| 0.55 | −0.258126 | −0.258325 | −2.0e-04 |
| 0.85 | −0.069969 | −0.095381 | −2.5e-02 |
| 0.95 | −0.034401 | −0.041067 | −6.7e-03 |

Siempre negativo, **máximo en el centro de la laguna y tendiendo a cero en los bordes**, que es exactamente cómo debe comportarse. Y los dos criterios —plano tangente y flash— coinciden en las 11 composiciones probadas.

Lo demás: benceno/tolueno no se separa a ninguna composición (y la estabilidad lo dice); agua/benceno se separa con fracciones de orden $10^{-4}$ sin perder precisión ($x_{benceno}$ en agua $= 3.93\times10^{-4}$, $x_{agua}$ en benceno $= 3.00\times10^{-3}$); la solubilidad mutua **crece con la temperatura**, que es el camino hacia la temperatura crítica de la laguna; y el balance de materia global cierra a 1.3e-16.

### ✅ Contra datos experimentales (Completado)
Lo anterior comprueba que el modelo es internamente consistente y termodinámicamente sano. Esta parte comprueba otra cosa, que ninguna de las anteriores puede: **si lo que predice se parece a la realidad.**

Fuente: **Perry's Chemical Engineers' Handbook, tabla 15-8**, «Water + Acetic Acid + Methyl Isobutyl Ketone Equilibrium Data at 25 °C», tomada de Sherwood, Evans y Longcor, *Ind. Eng. Chem.* **31**(9), 1144–1150 (1939). Siete líneas de reparto en porcentaje en peso.

**El binario agua/MIBK a 25 °C** (la primera línea, sin ácido):

| | experimental | predicho | error |
|---|---|---|---|
| MIBK en la fase acuosa | 1.55 % peso | **1.41** | −9 % |
| agua en la fase orgánica | 2.12 % peso | **1.29** | −39 % |

**La razón de reparto del ácido acético** en el ternario:

| AcOH en el refino (% peso) | $K$ experimental | $K$ predicho | error |
|---|---|---|---|
| 2.9 | 0.656 | 0.497 | −24 % |
| 11.7 | 0.761 | 0.565 | −26 % |
| 20.5 | 0.844 | 0.664 | −21 % |
| 26.2 | 0.939 | 0.728 | −23 % |
| 32.8 | 0.939 | 0.778 | −17 % |

### Lo que ese número significa, dicho sin adornos
**UNIFAC-LLE subestima la razón de reparto entre un 17 % y un 26 %**, y lo hace de forma **sistemática**: las cinco predicciones quedan por debajo del dato. La tendencia sí la acierta —$K$ crece con la concentración de ácido en las dos, experimento y modelo—, y eso es lo que decide si un disolvente sirve; la magnitud no basta para dimensionar un equipo.

Y hay un segundo límite, **medido y localizado**: en la última línea de reparto (34.6 % de ácido en el refino) el modelo predice **una sola fase** donde el experimento da dos. Su punto de pliegue queda más adentro que el real, así que el rango de concentración en el que sirve es más estrecho de lo que parece.

### Perry's dice exactamente esto, y conviene citarlo
No es una excusa que me invente: es la advertencia del propio manual, en la sección 15.

> *«an experimentally validated model will be needed because **UNIFAC and other estimation methods are not sufficiently accurate**... binary interaction parameters determined by regression of vapor-liquid equilibrium (VLE) data **cannot be relied upon to accurately model the LLE behavior** for the same system»*

La segunda mitad de esa frase es, palabra por palabra, la razón de que este módulo use el juego de parámetros de ELL y no el de ELV. La primera es el límite que la suite **mide** en vez de suponer: no se comprueba que el modelo acierte, se comprueba **cuánto se desvía**, y ese número queda escrito. Si una versión futura lo mejorara, la comprobación seguiría pasando y el número de la tabla sería el que habría que actualizar.

**Conclusión práctica**, y va al README y a los límites: este ELL sirve para **explorar** —decidir si un disolvente separa, ver cómo se mueve la laguna con la temperatura, entender el reparto— y **no** para dimensionar una columna de extracción sin datos del sistema concreto.

### ⬜ Lo que falta aquí
- **Extracción multietapa**: necesita plato a plato.
- Un **diagrama ternario** de ELL con sus líneas de reparto en la interfaz, que es como de verdad se lee un sistema de extracción.
- Poder **ajustar** los parámetros binarios a datos del sistema, que es lo que Perry's dice que hace falta para diseñar. Hoy el modelo es puramente predictivo: no hay dónde meter un dato experimental.

---

# Fase 14: Sacar los resultados

La tabla de corrientes se podía **leer** pero no sacar. Una herramienta cuyo resultado no puede salir de ella no se usa en un informe: acaba usándose a mano, copiando números de la pantalla — que es exactamente donde se cometen los errores de transcripción que este proyecto se esfuerza en no cometer por dentro.

### ✅ Tres formas, porque sirven para cosas distintas (Completado)
`frontend/app/flowsheet/exportar.ts` y los botones en el informe.

- **Ancho**: la tabla que se tiene delante, una columna por corriente. Es la que se pega en un informe.
- **Largo**: una fila por dato, con su unidad y su estado. Es la que una máquina quiere leer, sin huecos.
- **Portapapeles**: el camino corto, pegar en una hoja de cálculo sin pasar por un fichero en Descargas.

### Dos decisiones que no son obvias
**Se exporta lo que se ve, en las unidades que se ven.** El núcleo trabaja en SI, pero quien pide la tabla la quiere como la tiene delante: si eligió kg/h, el CSV dice kg/h. Exportar SI «porque es lo correcto» obligaría a reconvertir a mano, que es volver al problema.

**El estado de cada valor viaja con el valor.** Un número que diste y uno que calculó el simulador se distinguen en la pantalla por el color, y en una hoja de cálculo se volverían indistinguibles. Van en una columna: `dado`, `calculado`, `sin determinar`, `incompatible`.

Y un detalle que importa más de lo que parece: los números van con `toPrecision(12)`, no con el formato de la pantalla. La pantalla redondea a tres decimales para que se pueda leer; un CSV se lee con una máquina, y redondear ahí perdería precisión que el destino puede necesitar. Comprobado: la tabla muestra `365.516` y el CSV dice `365.515693257`.

Las filas se construyen con **la misma conversión de unidades que la tabla**, no con una paralela. Si se duplicara, la tabla y el CSV podrían decir cosas distintas sobre el mismo número — el peor fallo posible en una herramienta cuyo trabajo es no equivocarse al transcribir.

### ⚠ El defecto que encontró la suite
La primera versión del formato ancho ponía la unidad de la **primera** corriente como etiqueta de toda la fila. Parece razonable hasta que se recuerda que este simulador permite, a propósito, dar `s1.F` en kg/h y `s2.F` en mol/s a la vez.

El resultado era un CSV que decía:

```
F,kg/h,100.000000000,0.163158504297,0.163158504297
```

Los tres números son **correctos** —100 kg/h de benceno/tolueno 50/50 son 0.32632 mol/s, así que cada producto se lleva 0.16316— pero dos de ellos están en mol/s bajo una cabecera que dice kg/h. **Números correctos bajo una cabecera falsa, que es peor que un número mal: un número mal se nota.**

Corregido: si la fila mezcla unidades, la columna dice `varias (en cada celda)` y cada celda carga la suya. Una fila homogénea conserva su columna de unidad y sus celdas puramente numéricas, así que la legibilidad del caso común no se sacrifica por el caso raro.

De paso, **mi propia expectativa en la prueba estaba mal**: esperaba 30645 kg/h, que es el número de otra suite donde ese valor se *daba*. Aquí lo que se daba eran 100 kg/h. El fallo que destapó era real; la razón por la que falló, no.

### Detalles pequeños que habrían dolido después
- `URL.revokeObjectURL` no es opcional: sin él, cada descarga deja el blob entero retenido mientras la pestaña viva.
- `navigator.clipboard` **no existe** en contexto no seguro (http que no sea localhost), que es justo donde puede acabar este simulador si alguien lo sirve en una red interna. Hay respaldo con `execCommand`, y si tampoco funciona el botón lo dice en vez de no hacer nada.
- Las etiquetas llevan el nombre del componente: `x benzene`, no `x0`. Fuera de la aplicación, `x0` no significa nada.

### Verificación
`frontend/verificar_exportar.mjs`, 22 comprobaciones. Las descargas se capturan leyendo el `href` del `<a>` que se crea, en vez de dejar que el navegador escriba un fichero: en headless la carpeta de descargas es un detalle del entorno, y lo que se quiere comprobar es el **contenido**.

17/17 suites de navegador.

---

# Fase 15: Dimensionado — de etapas teóricas a hardware

Hasta aquí el simulador daba etapas teóricas, cargas térmicas y volúmenes de tanque. Nada de eso es un equipo:

- **«12 etapas teóricas» no es una columna.** Falta el diámetro, que es lo que decide si se inunda y la dimensión que manda en el coste.
- **«4.1 MW en el condensador» no es un intercambiador.** Falta el área.

Sin esos dos números no se pueden comparar dos diseños, que es para lo que sirve un simulador.

### Por qué este módulo necesita literatura y el resto del proyecto no tanto
Las correlaciones de aquí **no se derivan de nada**: son ajustes empíricos a datos de plantas. No hay invariante interno que las valide — no se puede comprobar que un diámetro «cierre un balance». La única forma de saber si están bien transcritas es **reproducir un caso resuelto por la fuente**.

Por eso `core/dimensionado.py` cita cada ecuación con su número de Perry's, y por eso no contiene termodinámica: recibe densidades, tensiones superficiales y cargas ya calculadas, y devuelve geometría. Esa separación permite decir **de dónde viene la incertidumbre** de un resultado — del modelo o del ajuste.

### ✅ El diámetro de una columna de platos (Completado)
Correlación de Fair, con la forma algebraica de su gráfica:

$$F_{LG} = \frac{L}{G}\sqrt{\frac{\rho_G}{\rho_L}} \qquad \text{(Perry's 14-89)}$$
$$C_{sbf} = 0.0105 + 8.127\times10^{-4}\,TS^{0.755}\exp\!\left[-1.463\,F_{LG}^{0.842}\right] \qquad \text{(14-90)}$$
$$U_{nf} = C_{sbf}\left(\frac{\sigma}{20}\right)^{0.2}\sqrt{\frac{\rho_L-\rho_G}{\rho_G}} \qquad \text{(14-91)}$$

La 14-90 es de Lygeros y Magoulas, *Hydrocarbon Proc.* **65**(12), 43 (1986). Tener la **ecuación** y no la gráfica es lo que permite calcular sin leer puntos a ojo.

**Tres formas de equivocarse aquí, y las tres se vigilan:**

1. **$L/G$ en base másica, no molar.** El error no revienta: da un diámetro plausible. Por eso los argumentos se llaman `caudal_masico_*` y no `L` y `G`.
2. **El espaciado en milímetros, no en metros.** La correlación está ajustada así, y pasarle 0.5 en vez de 500 daría un número 180 veces menor sin avisar. Lo caza el rango del ajuste (150–900 mm), y el mensaje dice que el problema es que el valor no está respaldado por los datos.
3. **El área NETA no es la sección total.** La correlación usa la neta; confundirlas da una columna un 12 % más estrecha de lo que toca.

### ✅ El área de un intercambiador (Completado)
$A = |Q| / (U \cdot \text{LMTD} \cdot F)$, con dos guardas que importan:

- **Se toma el valor absoluto de $Q$.** El signo dice si calienta o enfría; un área no tiene signo. Sin eso, un condensador ($Q<0$) daría un área negativa — el tipo de número que se cuela en una hoja de cálculo y no se nota.
- **$F \le 1$ siempre.** Un factor mayor que 1 significaría que el equipo aprovecha la diferencia de temperaturas *mejor* que la contracorriente pura, que es el límite.

Y la LMTD tiene sus dos casos degenerados tratados en vez de confiados: un **cruce de temperaturas** da el logaritmo de un cociente negativo (se rechaza nombrando los dos extremos que se cruzan) y **$\Delta T_1 = \Delta T_2$** da 0/0 (se devuelve el límite, que es $\Delta T$).

**Los coeficientes globales vienen con su rango, no como un número suelto.** Es deliberado: el área hereda la incertidumbre del $U$, y presentarla como un valor único sería esconderla. Medido: para un condensador orgánico/agua el rango tabulado va de 280 a 800 W/m²K, y eso son **de 13.95 a 39.85 m² para la misma carga — un factor 2.9 solo por la incertidumbre del coeficiente.**

### Verificación contra Perry's Ejemplo 9
Sección 14, «Flooding of a Distillation Tray»: etilbenceno/estireno en una columna de platos de tamiz de 2.5 m. Perry's publica los **números intermedios**, así que se compara paso a paso y, si uno se desvía, se sabe cuál.

| | Perry's | calculado | |
|---|---|---|---|
| $F_{LG}$ (Eq. 14-89) | 0.021 | **0.020633** | |
| $C_{sbf}$ (leído de la Fig. 14-31) | 0.095 m/s | **0.094340** | −0.7 % |
| $C_{SB}$ corregido por $\sigma$ | 0.0993 | **0.098645** | −0.7 % |
| **factor C de operación** | **0.0756** | **0.075597** | exacto a 4 cifras |

Y un detalle que vale la pena: Perry's concluye *«about 80 percent of flood»*, pero **sus propios números dan 0.0756/0.0993 = 76.1 %**. El valor calculado aquí, 76.64 %, concuerda con su aritmética mejor que con su redondeo — así que la comprobación se escribe contra su aritmética y no contra su frase.

La inversa también cierra: el diámetro necesario al 80 % de inundación sale **2.541 m** frente a los 2.5 m que la columna ya tiene (+1.7 %), coherente con que el ejemplo opere por debajo del 80 % y Perry's diga que *«the proposed column is entirely adequate»*.

### Y se comporta como debe
- **Más espaciado entre platos, columna más estrecha**: de 3.004 m a 300 mm hasta 2.078 m a 900 mm. Es el compromiso clásico — estrecha y alta, o ancha y baja.
- **Vapor más denso, columna más estrecha**: con $\rho_V = 0.481$ hacen falta 2.541 m; con 10 kg/m³, 1.272 m. Por eso **las columnas de vacío son enormes**.
- **Diseñar al 60 % en vez de al 80 %** cuesta un 15.5 % de diámetro, que son un **33 % más de sección**.

### Las propiedades que hacían falta
En `thermodynamics/proveedor.py`, y con sus aproximaciones declaradas:

- **Densidad de la mezcla líquida** por volúmenes aditivos (Amagat). No es exacta: el volumen de exceso puede llegar al 2–3 % en mezclas polares. Se elige así porque la alternativa aportaría una precisión que la correlación de inundación **no puede aprovechar**: ese ajuste tiene su propio ±10 %.
- **Tensión superficial** como media molar, que es grosera — en mezclas con agua cae mucho más rápido de lo que la media sugiere. Pero la correlación la eleva a 0.2, así que un error del 20 % en $\sigma$ se convierte en un **4 % en la velocidad de inundación**, por debajo de la incertidumbre del propio ajuste.
- **Densidad del vapor por gas ideal**, coherente con el resto del simulador. A 1 atm el error es de décimas de porcentaje; **a 10 atm puede ser del 5–10 %, y como el diámetro va con $1/\sqrt{\rho_V}$, eso es un 2–5 % en el diámetro.** Documentado como límite en vez de corregido a medias — y es otra razón para la fase vapor no ideal, que viene después.

### ✅ Conectado al diagrama, la API y la interfaz (Completado)
`con_dimensionado` en la columna binaria (apagado por omisión) y `coeficiente_global_U` en el intercambiador de dos corrientes.

**Apagado por omisión, y eso importa.** El dimensionado es una capa que **consume** el resultado de la columna y no aporta nada a resolverla; encendida siempre, obligaría a tener densidades y tensión superficial para cualquier columna, incluso cuando a nadie le interesa el diámetro. Y se comprobó que **no cambia los grados de libertad**: suma cinco incógnitas y cinco ecuaciones, así que la geometría no es un dato nuevo.

**El diámetro se calcula en LOS DOS EXTREMOS y manda el mayor.** No es prudencia: el caudal de vapor no es el mismo arriba y abajo salvo que $q = 1$,

$$V = (R+1)D \qquad \bar{V} = V + (q-1)F$$

y las propiedades físicas tampoco — arriba está el producto ligero a $T_D$ y abajo el pesado a $T_B$. Medido en benceno/tolueno con $R = 3$:

| | cabeza | cola | manda |
|---|---|---|---|
| $q = 1$ (líquido saturado) | 2.4287 m | **2.7025 m** | la cola |
| $q = 0$ (vapor saturado) | **2.4287 m** | 1.9348 m | la cabeza |

**El extremo crítico cambia de sitio según cómo entre la alimentación**, así que dimensionar por uno solo subdimensionaría la mitad de las veces.

Un detalle que no se podía aproximar: la composición del vapor en el fondo sale del **punto de burbuja de $x_B$**, no de $x_B$. En el rehervidor el vapor está en equilibrio con el líquido del fondo, y en un binario con $\alpha \approx 2.4$ confundirlos cambia la masa molar un 5 %.

**El área, solo en el intercambiador de dos corrientes**, y solo si se da $U$. Es el único que puede tenerla porque es el único que tiene las dos corrientes: el de una sola recibe un $Q$ de la nada, como si hubiera un servicio infinito, y sin la temperatura de ese servicio no hay diferencia media que calcular. Y **sin $U$ no hay área**: inventarle un valor por omisión sería dar como resultado una suposición.

### ⚠ Una distinción que la interfaz tenía mal planteada
La LMTD es una **diferencia** de temperatura, y eso **no es la misma magnitud** que una temperatura. Mapearla a `temperatura` habría hecho que al pedirla en Celsius se le restaran 273.15, y los 28.74 K habrían salido como **−244.4 °C**: un número absurdo presentado con toda naturalidad.

Se añadió la magnitud `temperatura_diferencia` con las unidades delta de `pint`, que tienen el factor pero **no el desplazamiento** — y ahí está exactamente la diferencia:

| | factor | desplazamiento |
|---|---|---|
| `degC` (temperatura) | 1 | **273.15** |
| `delta_degC` (diferencia) | 1 | **0** |

### ⚠ Y una inconsistencia anterior que la geometría hizo visible
La tabla de **corrientes** del informe humanizaba los nombres de variable (`x0` → «x benzene») y la de **equipos** no: mostraba `diametro` y `velocidad_inundacion` en crudo. Llevaba así desde que existe el informe, y solo se notó cuando aparecieron variables cuyo nombre interno es francamente feo. Corregido para las dos.

### Verificación
`tests/validar_dimensionado.py` sube a 46 comprobaciones (las 32 de las correlaciones más las del diagrama) y `frontend/verificar_dimensionado.mjs` añade 20 en navegador — incluida la que ninguna suite de Python puede hacer: que la LMTD se declare como diferencia y no como temperatura.

### ⬜ Lo que falta
- **Platos reales** a partir de las teóricas. La eficiencia de Murphree ya existe en McCabe-Thiele, así que falta la correlación que la estime cuando no se da.
- Columnas de **relleno** (HETP y la correlación de caída de presión de Eckert), que es la otra mitad del mercado.
- **Área del condensador y del rehervidor**: se conocen $Q_c$, $Q_R$ y las temperaturas de la columna, pero no la del servicio (agua de refrigeración, vapor), y sin ella no hay LMTD. Hace falta modelar los servicios.
- Sin costes: un diámetro y un área no son un precio.

---

# Fase 16: Trazabilidad — de dónde sale este número

Pedido en `../../frontend/CONTRATO_BACKEND_TRAZABILIDAD.md`, con una
observación concreta sobre la bomba y tres bloques nuevos de respuesta.
Solo backend.

## ✅ La bomba aceptaba presiones incompatibles, y la causa era general

El caso del contrato: bomba ideal con $P_1 = 101325$ Pa, factor $= 3$ **y**
$P_2 = 100000$ Pa dados a la vez. Tres condiciones sobre dos variables, y
$3 \times 101325 \neq 100000$. El servicio respondía **«resuelto por
completo», sin incidencias**, conservando la presión de salida dada.

**La causa no estaba en la bomba.** Estaba en `verificar_consistencia`,
que comparaba **solo** la variable que había olvidado y hacía `break` en
cuanto una comprobación salía bien, con el razonamiento de que *«una
comprobación por bloque es suficiente»*. Eso vale si cada bloque es una
ecuación, y varios no lo son:

| Bloque | Ecuaciones que empaqueta |
|---|---|
| Bombeo | $n+2$ ($F$, $T$, $P$, composiciones) |
| Mezclador | 5 |
| Divisor | 10 |

La comprobación recaía sobre la igualdad de caudales, salía bien, y **la
ecuación de presión no se evaluaba nunca**.

Ahora se compara todo lo que el bloque devuelve, y se sigue hasta haber
verificado tantas variables distintas como ecuaciones declara. **No cuesta
llamadas extra**: el solver de la bomba ya escribía $P_2 = 303975$ al
olvidar otra variable; simplemente nadie miraba ese valor.

### ⚠ Y un error de signo que esto destapó

La bomba declaraba `n_ecuaciones = 1` (el valor por omisión de un bloque
invertible) mientras imponía $n+2$. Consecuencia: una bomba **exactamente
especificada** reportaba $\mathrm{GL} = +3$ y una **sobreespecificada**
$\mathrm{GL} = +1$. Decía que faltaban datos cuando sobraban — el signo
contrario de la verdad.

El $n+2$ sale de un argumento de rango, no de contar a ojo: hay $2n$
fracciones entre las dos corrientes, el bloque impone $n$ igualdades más
los 2 cierres, y el rango de ese sistema es $n+1$, así que a la bomba le
corresponden $n-1$ composiciones más $F$, $T$ y $P$.

### La política, ahora explícita

El contrato preguntaba si el orquestador debía *omitir* el cierre al estar
dados ambos extremos o *detectar* la incompatibilidad. Se eligió
detectar, y se hizo explícito qué significa cada bandera:

- `completo = true` dice que **todas las variables quedaron
  determinadas**, no que el resultado sea físico.
- La incompatibilidad viaja en su propio campo.
- **`hay_errores` es la bandera que separa «se calculó todo» de «el
  resultado es válido».**

En el caso de la bomba, las dos valen `true` a la vez. Confundirlas era el
fallo.

## ✅ `calculo`: con qué motor y sobre qué entradas

Versión del motor **y commit de git**, con el sufijo `-sucio` cuando el
árbol tiene cambios sin commitear: un commit a secas afirmaría que el
código es exactamente el de ese commit, y con el árbol modificado eso es
falso. `commit` puede ser `null` — un despliegue sin `.git` no lo sabe, y
**inventarse un identificador sería peor que admitirlo**, porque un
identificador falso se propaga a los informes y nadie lo cuestiona.

**La versión del proveedor termodinámico son las versiones de `thermo`,
`chemicals` y `fluids`.** No es un detalle administrativo: es la razón de
que `requirements.txt` las tenga fijas, y ya pasó una vez — los atributos
`Hfl`/`Gfl` de `thermo` cambiaron río arriba y movieron los números sin
que nadie tocara una línea de este repositorio.

### La huella de las entradas, y qué deja fuera

SHA-256 de las entradas **físicas normalizadas**. El contrato que
establece: *dos peticiones con la misma huella deben dar el mismo
resultado; si dan otro, el cambio está en el motor o en sus
dependencias*. Esa distinción, sin huella, se resuelve discutiendo.

Entra lo que cambia el resultado (componentes **en orden**, modelo,
operaciones con sus parámetros, valores en SI, especificaciones). No entra
lo que no (coordenadas de los nodos, unidades de presentación, nombre de
la simulación).

**Se construye a mano, campo por campo, y no con un volcado automático
del `request`.** Es más trabajo y es lo correcto: un volcado automático
metería en la huella cualquier campo nuevo que alguien añada a los
esquemas, y la huella cambiaría sin que la física cambie — justo lo que
una huella no debe hacer.

La normalización no es cosmética. `repr(0.1 + 0.2)` y `repr(0.3)`
difieren, así que sin un formato canónico **dos peticiones idénticas para
cualquier propósito práctico darían huellas distintas**. Quince cifras
significativas (lo que un `float64` distingue), los enteros como enteros
para que `3` y `3.0` no sean dos entradas, diccionarios ordenados, listas
no — el orden de los componentes define cuál es $x_0$.

Y el digest va **completo**: truncarlo a doce caracteres queda más bonito
en un informe y multiplica por mucho la probabilidad de colisión.

## ✅ `diagnosticos`: la categoría no se deduce del texto

Lo que pasaba estaba repartido en cuatro campos y tres formas distintas
(`incognitas_restantes`, `diagnostico`, `inconsistencias`,
`errores_bloque`). Distinguir «faltan datos» de «esto es físicamente
imposible» **exigía buscar subcadenas en castellano**, y eso se rompe la
primera vez que alguien mejora la redacción de un mensaje. Los cuatro
campos se conservan; `diagnosticos` los unifica con código estable,
categoría, severidad, equipo y variables implicadas.

La categoría viene de **dónde se generó** el problema. Para los errores de
bloque, de la propia excepción: `core/errores.py` añade una jerarquía que
hereda de `ValueError` y `RuntimeError`, y ese detalle es lo que permite
que todos los `except ValueError` que ya existían **sigan funcionando sin
tocarlos**.

Lo que nadie clasificó llega como `SIN_CLASIFICAR`, con el tipo de Python
como único dato objetivo. Es una respuesta honesta: adivinar la categoría
buscando «hirviendo» o «no convergió» en el mensaje acierta hasta que
alguien reescribe una frase, **y entonces falla en silencio**.

**La severidad no coincide con la categoría.** Una redundancia es
*advertencia* — los datos de más no son necesariamente erróneos, se
comprobarán por consistencia en vez de calcularse. Una incompatibilidad es
*error*. Y un bloque que no pudo dispararse es *información*: es la
**causa** de las variables sin determinar, no un problema aparte.

Las variables sin determinar se **agrupan por elemento**: quince
diagnósticos idénticos no informan más que uno que diga «a `col1` le
faltan estas quince».

## ✅ `convergencia`: sin residuos fabricados

La parte que el contrato pedía con más insistencia. Cada bloque **declara**
su familia (`algebraico`, `geometrico`, `correlacion`, `iterativo`,
`integracion`) y la declaración se separa en dos mitades: lo que el bloque
*es* (método, tolerancia, **qué mide** el residuo con su escala) y lo que
esta ejecución *midió*.

| Bloque | Familia | Residuo |
|---|---|---|
| `col1: McCabe-Thiele` | geométrico | **ninguno**, con motivo: «se escalona hasta cruzar $x_B$ y se para» |
| `Punto de burbuja (dest)` | iterativo | $\sum y_i - 1$, tolerancia $10^{-9}$ K, `brentq` sobre $T$ |
| `col1: balance de materia` | algebraico | **ninguno**: se cumple por construcción |
| `dec1: equilibrio líquido-líquido` | iterativo | $8.24 \times 10^{-12}$ en 52 iteraciones |

Un residuo de $10^{-11}$ en un flash dice mucho; la *ausencia* de residuo
en una construcción de McCabe-Thiele no dice nada malo — **ahí no hay
residuo que medir, y presentar uno sería inventarlo**. El campo `motivo`
es la mitad útil del descriptor: distingue «no aplica» de «no se midió».

El decantador fuera de la laguna de miscibilidad reporta *«una sola fase
líquida: no hubo reparto que converger»* en vez de un residuo de cero, que
sugeriría la convergencia perfecta de algo que nunca se planteó.

Se reportan **todos** los bloques, también los que no iteran: «este número
sale de una fórmula cerrada» es información, no una ausencia. Y
`ejecutado` distingue «no corrió» de «no hacía falta»: la presión de
operación de la alimentación no se dispara cuando `alim.P` viene dada, y
eso dice que ese número es un **dato** y no un resultado.

## Verificación

`tests/validar_trazabilidad.py`, **49 comprobaciones**, más la sección 5
de `validar_diagrama_corrientes.py` para la bomba. Las tres cosas que
estos bloques pueden hacer mal no se ven mirando un resultado concreto:

- **Una huella que cambie cuando no debería** da una falsa sensación de
  reproducibilidad. Se comprueba contra lo que no cambia la física
  (reordenar corrientes, `3` frente a `3.0`) y contra lo que sí (el factor
  de compresión, quitar un dato, invertir los componentes).
- **Una categoría deducida del texto** funciona hasta que alguien
  reescribe una frase. Se comprueba que un reflujo bajo el mínimo salga
  como `fisica` y no como `datos`.
- **Un residuo fabricado** es una mentira con cara de precisión.

Y una sección que comprueba que **el contrato anterior no se tocó**: los
nueve campos de siempre siguen presentes, los cuatro nuevos son
opcionales, y la respuesta completa serializa a JSON estricto — un
`float32` de NumPy o un `NaN` pasan los tipos de Pydantic y revientan al
serializar. **20/20 suites en 239 s.**

## ⬜ Lo que falta

- **El catálogo versionado de ecuaciones y suposiciones por operación**,
  que el contrato marca explícitamente como opcional posterior. Hoy
  `convergencia` dice *cómo* se resolvió un bloque; no dice *qué ecuación*
  es ni de qué referencia sale.
- **`VERSION_MOTOR` se sube a mano.** El commit desambigua, pero la
  versión semántica depende de que alguien la mueva.
- **El decantador no está expuesto en la API.** Existe en
  `core/diagrama_corrientes.py` y no se puede pedir por HTTP, así que su
  trazabilidad se valida contra el motor. Es una laguna anterior a esta
  fase, pero esta fase la hizo visible.
- **Fase vapor no ideal**, que sigue siendo el límite termodinámico de
  fondo.

---

# Fase 17: El laboratorio deja de reconocer montajes y empieza a resolverlos

Pedido en `../../frontend/PASAR_A_CLAUDE_LABORATORIO.md`. Solo backend.

## El problema

La mesa del laboratorio dejaba dibujar piezas y **formular** el montaje:
escribir los balances en LaTeX y marcar qué términos anulaban los
supuestos. Pero solo había **adaptadores para dos montajes concretos** —un
calentador y un CSTR isotermo— así que dos volúmenes en serie no se podían
resolver, y el frontend tenía que mostrar la formulación sin cálculo.

La diferencia no es de tamaño: reconocer un montaje y resolver un sistema
son dos cosas distintas. Lo segundo exige variables con identidad,
ecuaciones con origen y un recuento de grados de libertad que no se puede
sacar contando fichas en el lienzo.

## ✅ Una corriente intermedia es UN estado, no dos

El requisito central, y el que decide la arquitectura. Si el volumen 1
escribiera su salida en un sitio y el volumen 2 leyera su entrada de otro,
harían falta cinco ecuaciones de igualdad ($F$, $T$, $p$, $x$, $h$) y
cinco incógnitas **que no son incógnitas**.

Aquí el estado **pertenece al bloque corriente**: los dos volúmenes
referencian las mismas variables. En la respuesta salen con
`rol: "compartida"` y cada una cita los dos volúmenes y las dos
conexiones.

## ✅ El método se declara, no se adorna

Para esta topología el sistema es **triangular** —cada volumen depende
solo de lo que tiene aguas arriba— así que se resuelve con una marcha
aguas abajo:

| Modo | Se impone | Se despeja | Algoritmo real |
|---|---|---|---|
| temperatura | $T_{sal}$ | $\dot Q = F(h_{sal}-h_{ent})$ | evaluación directa, sin iteración |
| calor | $\dot Q$ | $h_{sal}=h_{ent}+\dot Q/F$, y $T$ invirtiendo $h$ | `brentq`, xtol $10^{-10}$ K |

**No hay sistema acoplado, no hay Newton y no se declara ninguno.**
Declarar «Newton» porque suena a motor sería la misma clase de mentira que
fabricar un residuo: quien lea «Newton, 1 iteración» concluirá cosas
falsas sobre el coste y el condicionamiento.

Y los dos modos son excluyentes por aritmética, no por capricho del
adaptador: el balance de energía del volumen es **una** ecuación con esas
dos incógnitas.

## ✅ Qué cuenta como ecuación, y qué no

El caso de aceptación produce 18 relaciones y solo **9** cuentan:

| Tipo | Cuenta | Por qué |
|---|---|---|
| balance (6) | **sí** | Conservación |
| constitutiva (3) | **sí** | $h=h(T,p,x)$: donde entra el modelo |
| condición (3) | no | Es un **dato**: reduce incógnitas, no aumenta ecuaciones |
| convención (2) | no | El signo de $\dot Q$ no determina nada |
| cierre (3) | no | $\sum x_i = 1$ se satisface por la parametrización |
| verificación (1) | no | Combinación lineal de los balances |

$$\mathrm{GL} = 9 - 9 = 0$$

Es la fuente del error más común al mostrar grados de libertad: contar las
especificaciones y las convenciones infla las ecuaciones y los GL salen
**negativos en un sistema perfectamente planteado**.

El `rango` que se publica es **estructural**, y `rango_origen` dice de
dónde sale: el sistema es triangular, así que cada ecuación introduce una
variable nueva. No se calcula un Jacobiano ni se presenta su rango como
independencia global — el contrato advertía justo contra eso.

## ✅ Lo que NO se infiere

**La ausencia de una pieza no es un supuesto.** Que no haya fuente de
calor dibujada no significa $\dot Q=0$: significa que al balance de
energía le falta un término. Con $\dot Q=0$ supuesto, un volumen al que se
le pide subir 10 K daría un sistema incompatible sin explicación;
declarándolo indeterminado, el diagnóstico dice qué falta conectar.

Los dos lados están: una fuente conectada **con** adiabático marcado es
`LAB_SUPUESTO_INCOHERENTE`; ni fuente **ni** adiabático es
`LAB_FALTA_ESPECIFICACION`.

## ✅ La fase se determina; Cp no es constante

Cada estado pasa por el flash, que ubica el punto frente al punto de
burbuja y al de rocío. En el caso de aceptación los tres son líquido
subenfriado —la burbuja de 50/50 a 300 K está en 8894 Pa— pero **se
comprueba**, y es barato: el caso líquido se corta en la primera
comprobación.

| $\dot Q_1$ | $T$ intermedia | fase | $\beta$ |
|---|---|---|---|
| 0.148 MW | 310.0 K | líquido | 0 |
| 2.0 MW | 367.5 K | **bifásico** | 0.302 |
| 3.0 MW | 369.6 K | **bifásico** | 0.606 |
| 5.0 MW | 434.4 K | vapor | 1 |

Dentro de la laguna, **1 MW más sube la temperatura 2.1 K** frente a los
~10 K que costaban 0.15 MW en la zona líquida.

Y $C_p$ no es constante ni siquiera en el líquido: el mismo salto de 10 K
cuesta **147842.85 W** de 300 a 310 y **150506.36 W** de 310 a 320, un
1.80 % más.

## ⚠ La trampa de la misma letra

`bloques[].datos` se admite por compatibilidad con lo que la mesa exporta
hoy, y ahí las unidades son **implícitas**: la mesa documenta $\dot Q$ en
**kW**. Así que `Q` significa W en una especificación explícita y kW en un
dato local. Tomar un dato local por watts da un calor mil veces menor, que
no se parece a un error: **se parece a un resultado**.

Por eso la unidad es obligatoria en las especificaciones explícitas, la
`procedencia` de cada variable dice si el valor llegó sin unidad escrita,
y `capacidades` lo avisa.

## ✅ Un montaje imposible devuelve 200

Con `estado` y diagnósticos, no `4xx`. Un 422 de Pydantic no lleva código
estable, ni id de bloque, ni acción sugerida, y con eso la interfaz no
puede señalar una ficha. El 4xx queda para lo que no tiene **forma** de
montaje.

Los diagnósticos llevan prefijo `LAB_` y los **27 códigos declarados se
emiten**: declarar uno que nunca se emite no es inofensivo, porque quien
escriba el cliente le hará una rama que no se ejecutará nunca, y nadie se
enterará de que está mal escrita.

## Verificación

`tests/validar_laboratorio.py`, siete grupos. **Los números no están
escritos a mano**: se comparan contra llamadas independientes al mismo
proveedor. Copiar la salida del ensamblador como valor esperado la
bendeciría para siempre.

Lo único afirmado a priori son las identidades que no dependen de ningún
dato: que $F$ se conserva, que duplicar $F$ duplica $\dot Q$, que
$\dot Q_1+\dot Q_2 = F\,\Delta h$ con residuo medido bajo $10^{-12}$, y
que imponer el $\dot Q$ calculado recupera los 310 K **con error 0.0 K**.

Y una que cruza los dos servicios: el preset de un volumen da el mismo
$\dot Q$ que `/diagrama/resolver`, **147842.851474 W por los dos caminos**.

Los presets de `/laboratorio/ejemplos` **son** peticiones válidas de
`/resolver` y la suite los reenvía — la misma idea que en `validar_api.py`:
un preset roto es un fallo que el usuario encuentra en el primer clic.
Uno de ellos espera `invalido` a propósito, para que la interfaz pueda
probar su camino de error contra un error de verdad.

## ⚠ Dos cosas que esta fase hizo visibles

- **`../02-solver.md` quedó volteado a CRLF** en el commit de
  trazabilidad, porque `io.open(p,'w')` traduce los saltos en Windows. El
  archivo no cambió de contenido, pero ese commit lo registró como una
  reescritura de 918 líneas. Se deja como está: normalizarlo ahora solo
  movería el diff fantasma a otro commit.
- **El decantador sigue sin estar expuesto en ninguna API**, ni aquí ni en
  el diagrama.

## ⬜ Lo que falta

- **Caída de presión entre volúmenes.** La presión es uniforme; el modelo
  existe en `/diagrama/resolver` y no está conectado aquí.
- **Más de dos volúmenes.** El límite es del ensamblador, no del método:
  la marcha aguas abajo sirve para $N$.
- **Reactor y reacción** en el ensamblador. El CSTR sigue donde estaba,
  con su balance de energía desactivado — comprobado que esta entrega no
  lo activó por el camino.
- **Trabajo de eje**: la formulación se muestra, el cálculo necesita un
  modelo de máquina.
- **Reciclos.** Un lazo se detecta y se nombra —el mensaje dice por dónde
  pasa— pero no se resuelve.
- **Las iteraciones reales de `brentq`.** Haría falta exponer el contador
  desde el flash y la calculadora de entalpía, y eso toca física validada;
  no se ha hecho por una métrica.
- **Fase vapor no ideal**, que sigue siendo el límite termodinámico de
  fondo.

---

# Fase 18: El laboratorio aprende química

Pedido en `../../frontend/ENTREGA_FUNDAMENTOS_CLAUDE.md`. Solo backend.

Balances molares por especie y transformación estequiométrica en volúmenes
concentrados, en régimen estacionario y con **tasa especificada**.

## ✅ La precisión que decide el diseño: bruto no es neto

El contrato lo pide con una insistencia que se entiende en cuanto se mira
el caso: una reacción reversible **en equilibrio** tiene $r^+ = r^- > 0$.
La fuente neta de cada especie es **cero** y cada especie se está
produciendo y consumiendo a un ritmo **positivo**. Las moléculas no están
quietas: están yendo y viniendo a la misma velocidad.

Así que la fuente neta **no determina** las brutas. Un neto de cero es
compatible con dos situaciones físicas distintas:

| | $r^+$ | $r^-$ | neto | $G_i$ | $C_i$ |
|---|---|---|---|---|---|
| reacción parada | 0 | 0 | 0 | 0 | 0 |
| equilibrio dinámico | 5 | 5 | 0 | $\|\nu_i\|\cdot 5$ | $\|\nu_i\|\cdot 5$ |

Tres reglas, las tres implementadas:

1. **Con $r^+$ y $r^-$ por separado**, las brutas se calculan: el evento
   directo produce lo que tiene $\nu > 0$ y el inverso lo que tiene
   $\nu < 0$, y las dos cosas generan.
2. **Con solo la tasa neta**, salen `null` con su motivo. **Nunca**
   rellenadas con $\max(\text{neto},0)$, que daría cero generación en una
   reacción funcionando a toda velocidad.
3. **La descomposición del neto** se ofrece aparte y etiquetada. Es el
   signo del neto en dos casillas, **no** el intercambio bruto: en el
   equilibrio da cero en las dos mientras las brutas valen 10 y 5.

Y si **alguna** reacción de un volumen solo trae su neto, las brutas del
volumen entero no están disponibles: $G_i$ es una suma y un término
desconocido hace desconocida la suma. El motivo nombra la culpable.

**$G_i$ y $C_i$ se derivan**, no son variables. Con $n$ especies serían
$2n$ incógnitas nuevas y el problema quedaría indeterminado. Lo mismo con
$F_i = F x_i$.

## ✅ Los balances, en caudales y no en fracciones

$$F_{i,sal} = F_{i,ent} + \sum_r \nu_{ir}\,\xi_r$$

Porque el balance es **lineal en $F_i$ y no en $x_i$**: con reacción el
caudal total cambia, y una ecuación en fracciones arrastraría ese cambio a
todos los términos.

El total sale de la suma y **puede cambiar**. Un caudal molar que cambia
parece un balance roto y no lo es; lo que no cambia nunca es la masa.

**Y el balance total deja de ser una ecuación independiente**: es la suma
de los $n$ por especie, así que contarlo regalaría una ecuación. Pasa a
`verificacion`, con su residuo medido.

## ✅ Conservación: dos comprobaciones, no una

**Antes de resolver**, la estequiometría se valida contra la matriz
elemental que da `thermo`: $A\nu = 0$ y $MW\nu = 0$. Una $\nu$ que no la
cumpla no es una reacción, es un dato mal puesto, y el diagnóstico dice
**qué elemento descuadra y en cuánto**.

**Después**, elementos y masa se **miden** sobre los caudales resueltos.
No es la misma comprobación: aquello verifica que la reacción tenga
sentido, esto que el balance se haya **aplicado** bien. Una reacción bien
balanceada con un balance mal aplicado pasa la primera y falla la segunda.

## ✅ El calor de reacción, sin contarlo dos veces

La referencia de este motor es **sensible**: $h$ no incluye las entalpías
de formación, así que el término va explícito:

$$\dot Q + F_{ent} h_{ent} - F_{sal} h_{sal} - \sum_r \xi_r \Delta H_{rxn,r} = 0$$

**$\Delta H_{rxn}$ se evalúa a la temperatura de REFERENCIA.** No es una
aproximación: toda la dependencia con $T$ ya está en los términos
sensibles, y corregirla aquí con Kirchhoff **sería contarla dos veces**.
Es el error que el contrato pide evitar, visto desde el otro lado.

Y la decisión de sumar el término **cuelga de una tabla de referencias**,
no de que haya reacción, para que añadir una referencia obligue a declarar
si incluye formación. Si la incluyera, el término no aparecería y
figuraría en `terminos_descartados` con ese motivo.

Con $\xi = 0$ el calor de reacción es cero **aunque las brutas sean
positivas**: lo mueve el avance neto.

## ⚠ El cierre global lo detectó solo

La comprobación global estaba escrita para el caso sin reacción:

$$\sum \dot Q = F\,(h_{sal} - h_{ent})$$

y con reacción le faltan dos cosas: que el caudal **cambia** (no hay un
$F$ que multiplique a las dos entalpías) y el calor de reacción. Dos
reactores en serie dieron `no_convergente` porque los números no cuadraban
con una fórmula incompleta. **Para eso se puso la guarda**, en la fase
anterior, con el razonamiento de que medir un residuo y no actuar sobre él
es la mitad que no protege de nada.

La forma correcta sale de sumar los balances por volumen: los estados
intermedios se cancelan —son la **misma** variable— y los términos de
reacción se acumulan.

$$\sum_j \dot Q_j = F_{sal} h_{sal} - F_{ent} h_{ent} + \sum_r \xi_r \Delta H_{rxn,r}$$

## ✅ El método sigue siendo triangular, y eso no es casualidad

**La tasa está especificada**, así que el avance es un dato y no depende
de la composición de salida. El balance por especie sigue siendo
explícito y la marcha aguas abajo sigue valiendo.

Una tasa cinética $r(T, \mathbf{x}_{sal})$ rompería eso: el balance se
volvería implícito y haría falta un solver acoplado. Por eso la cinética
se **rechaza con diagnóstico** en vez de aproximarse, y el CSTR con
cinética sigue en `/diagrama/resolver`.

## ✅ La base de la tasa la declara la unidad

`mol/s` es integrada y `mol/(m3*s)` volumétrica, y no hay forma de
confundirlas leyendo. Es la distinción que el contrato pide explícitamente,
hecha de la forma que **no depende de que nadie rellene un campo `base`**
de acuerdo con la unidad. Una tasa volumétrica sin $V$ no se integra con
1 m³: se diagnostica.

## ⚠ Dos defectos anteriores que la química destapó

Los dos eran invisibles mientras el laboratorio fuera binario:

- **Una fracción molar de cero se rechazaba** como no física. El dominio
  trataba todas las magnitudes igual, y para un caudal está bien —cero no
  es un caudal pequeño, es la ausencia de corriente— pero para una
  fracción es falso. Nadie escribe $x = 0$ en una mezcla de dos; con tres
  especies y una alimentación pura es lo normal.
- **El cierre de composición se evaluaba dos veces** en la corriente de
  entrada, y la segunda vez tomaba la rama de «se dieron las $n$», que
  mide el residuo de la suma. Pero una de esas fracciones se acababa de
  **calcular**, así que medía el residuo de $1-(1-x)$: cero por
  construcción. Es exactamente el error que este módulo denuncia en todos
  los demás sitios, cometido por no distinguir un valor **impuesto** de
  uno **calculado**. La bandera `impuesta` existe justo para eso y ahí no
  se estaba usando.

## El recuento cambió, y los grados de libertad no

Las $n$ fracciones son ahora variables explícitas y el cierre es la
ecuación que determina la que falta. El caso térmico pasa de «17
variables, 9 incógnitas, 9 ecuaciones» a «20, 12, 12», y
$\mathrm{GL} = 0$ en los dos: subieron a la vez una variable y una
ecuación por corriente.

**El criterio no ha cambiado nunca: una relación cuenta si y solo si
determina algo.** El cierre cuenta cuando determina la fracción que falta
y no cuenta si se dan las $n$ —ahí comprueba, y su residuo se mide—.
Antes no contaba porque la segunda fracción de un binario no era una
variable sino una expresión.

## Verificación

`tests/validar_laboratorio.py` sube a **ocho grupos y 230
comprobaciones**. Los números de la reacción tampoco están escritos a
mano: los avances y las fuentes se comparan contra lo que la
estequiometría **obliga**, y la conservación contra la matriz atómica de
`thermo`.

Dos sistemas reales con propiedades completas y balance elemental exacto:

| Caso | $\nu$ | Qué demuestra |
|---|---|---|
| n-butano → isobutano | $[-1,+1]$ | $\Sigma\nu=0$: el caudal molar no cambia |
| diisobutileno → 2 isobuteno | $[+2,-1]$ | $\Sigma\nu=+1$: 100 → **110** mol/s, masa constante |
| 2 isobuteno ⇌ diisobutileno | $[-2,+1]$ | reversible, y el equilibrio con $r^+=r^-$ |

Residuos de elementos y masa por debajo de $10^{-12}$ en todos los casos.
El montaje de dos reactores: 100 → 90 → 75 mol/s, seis variables
compartidas, ningún estado duplicado, y cierre global **0.0** con
$\Sigma\dot Q = -2\,517\,877.48$ W $=$ transporte $249\,622.52$ $+$
reacción $-2\,767\,500.00$.

Más **catorce rechazos** con su código, y los catorce presets de
`/laboratorio/ejemplos` reenviados al endpoint — dos de ellos esperan
`invalido` a propósito, para que la interfaz pueda probar su camino de
error contra un error de verdad. **21/21 suites.**

## ⬜ Lo que falta

- **Cinética y equilibrio químico**, por lo dicho arriba.
- **Entropía, exergía y potenciales químicos**: la siguiente entrega que
  el contrato enumera. Necesita temperaturas de frontera para la segunda
  ley y un ambiente explícito para la exergía.
- **Conducción 1D, difusión binaria y balances de momento**: las otras
  tres, cada una con sus casos analíticos independientes antes de
  conectarse.
- **Caída de presión entre volúmenes**, más de dos volúmenes, reciclos.
- **El decantador sigue sin estar expuesto en ninguna API.**
- **Fase vapor no ideal**, que sigue siendo el límite termodinámico de
  fondo.

---

# Fase 19: Catálogo de sustancias, cinética y energía acoplada

Pedido en `../../frontend/PENDIENTES_BACKEND_CLAUDE.md`, puntos 1, 2 y 5. Solo
backend.

## ✅ Una fórmula no identifica una sustancia

El punto 1 lo decía y no es una precaución teórica:

| Consulta | Resuelve a | $T_b$ |
|---|---|---|
| `C2H6O` | **dimethyl ether** | 248.4 K |
| `ethanol` | ethanol | 351.6 K |

Las dos tienen fórmula C2H6O. **103 K de diferencia** por escribir la
fórmula en vez del nombre, y el cálculo sale perfectamente bien para la
sustancia equivocada — que es el peor fallo posible, porque no se nota.

El índice de fórmulas de `chemicals` asocia cada fórmula a **una** sola
sustancia, así que ya eligió por su cuenta y no sirve para avisar. Se
barre la base entera (76 522 entradas, **8 ms**) y se devuelven los
candidatos. Ocho milisegundos es baratísimo al lado de no poder avisar.

`/laboratorio/sustancias/buscar` declara **cómo** resolvió la consulta, y
`identificacion_fiable` vale `false` cuando fue por fórmula. El id estable
es el **CAS**: el nombre tiene sinónimos y la fórmula es ambigua.

## ✅ Y tener grupos UNIFAC no basta para reaccionar

La segunda mitad del punto 1. Hace falta además la entalpía de formación,
y hay sustancias que tienen lo primero y no lo segundo: el
**diciclopentadieno** tiene UNIFAC y no tiene `Hfm`. Sirve para un ELV y
no para un balance reactivo, y enterarse al resolver —cuando el calor de
reacción sale NaN— es tarde.

Así que las capacidades se declaran **una por una**, con lo que falta en
cada caso: `elv`, `entalpia`, `reaccion`, `equilibrio`. Y se comprueba la
MISMA propiedad que el motor usa luego, no una parecida: comprobar otra
daría un apto que luego falla.

## ✅ Cinética: la tasa deja de ser un dato

El punto 2. Con una ley de acción de masas,

$$ \xi_r = r_r(T, \mathbf{x}_{salida}) \qquad \mathbf{x}_{salida} = \mathbf{x}_{salida}(\xi) $$

la tasa depende de la composición de **salida**, que es lo que el balance
calcula: el sistema se vuelve **implícito**. Es el motivo de que la fase
anterior rechazara la cinética en vez de aproximarla.

**La triangularidad se rompe DENTRO de cada volumen, no entre volúmenes.**
La marcha aguas abajo sigue valiendo, y la respuesta lo declara con esas
palabras: decir «sistema acoplado» a secas sugeriría que todo el montaje
se resuelve a la vez.

**Los órdenes son explícitos.** Un orden no es un coeficiente
estequiométrico: la ley sale de un mecanismo y la estequiometría de un
balance, y coinciden solo en una reacción elemental. Sin declararlos se
usa $|\nu|$ y la respuesta dice que ése fue el defecto. Los negativos se
rechazan: modelan inhibición y hacen que la tasa diverja al agotarse la
especie.

**Arrhenius referenciado**, y no por estética: en la forma clásica $A$
vale $10^{13}$ y el exponente −40, así que la expresión resta números
enormes para dar uno pequeño. Se admiten las dos y se declara cuál se usó.

**Las actividades son adimensionales en las dos bases**, y eso quita de
encima que las unidades de $k$ dependan del orden global: $k$ lleva las
unidades de la tasa y punto.

Y la inversa puede **derivarse del equilibrio**, $k_{inv} = k_{dir}/K_{eq}$,
que es la restricción que impone la termodinámica. Con sus dos avisos
declarados: van't Hoff supone $\Delta H$ constante, y la directa pasa a
usar los exponentes de la estequiometría porque mezclar órdenes libres con
una inversa del equilibrio rompería la razón $K_{eq}$.

## ✅ El modo adiabático era un hueco

El punto 5. `_comprobar_modos` exigía T impuesta **o** Q impuesta, y con
el supuesto adiabático no hay fuente que imponer: la especificación **es**
$\dot Q = 0$. Un volumen adiabático no se podía resolver, y el
diagnóstico decía «no se impuso ni la temperatura ni el calor» — que era
falso.

Es el mismo error que la fase 18 corrigió en el otro sentido —la
**ausencia** de una fuente no es $\dot Q = 0$— cometido al revés: la
**presencia** del supuesto sí es una especificación, y no se estaba
leyendo como tal.

Con cinética, T y avance se cierran **a la vez**: $k(T)$ decide el avance
y el avance decide el calor que decide T. Verificado por dos caminos: la
isomerización adiabática de butano sube de 320 a 369.46 K, imponer esa T
en modo isotermo da el mismo avance (86.0894127745747 frente a
86.08941277457478), y el calor liberado iguala al calentamiento sensible
(**818 710.3 W** por los dos lados).

## ⚠ El mínimo local que no era raíz

La parte que costó, y el síntoma no apuntaba al diagnóstico.

`least_squares` minimiza $\lVert F\rVert^2$, y en un sistema cuadrado eso
**no** es resolver $F = 0$: puede pararse en un mínimo local. Para una
reacción exotérmica con sólo ley directa daba

$$ \xi = -13.3\ \text{mol/s} \qquad T = 307.8\ \text{K} $$

avance **negativo** y temperatura **por debajo** de la entrada. El solver
no estaba roto: hacía su trabajo sobre una función cuyo mínimo local pilló
primero. Desde $(\xi=0, T=T_{ent})$ el residuo de materia vale $-r/F$ y el
de energía cero, así que **bajar** la temperatura reduce la tasa y con
ella el residuo — el gradiente apunta al lado contrario de donde está la
solución de una exotérmica.

Antes de eso, con `root/hybr` —que no acepta límites— el fallo era otro:
con la tasa creciendo como $e^{-E_a/RT}$ el primer paso se iba a
temperaturas sin sentido. **El residuo nunca tuvo nada de malo**; medido
en una rejilla es suave, monótono y tiene solución. Lo que faltaba era
impedir que el solver mirara donde el modelo no existe.

La solución tiene dos mitades y las dos se declaran:

1. **arranque por sustituciones sucesivas**, alternando los dos problemas
   escalares y acotados que sí son robustos (el avance con T fija, y la T
   con el avance fijo);
2. **`least_squares` con `trf` y límites**, con la temperatura acotada al
   dominio de la tabla de entalpía — que no es un número elegido, es
   `CalculadoraEntalpia.T_min/T_max`.

Decir solo «least_squares» ocultaría de dónde salió el punto de partida, y
el punto de partida es la mitad del problema cuando hay mínimos locales.

Y si la solución se queda **en** un límite, `convergio` es `false`: una
solución en la pared no es un estado estacionario, significa que el
sistema pide salirse del dominio del modelo.

## ⚠ Un caso de prueba mal elegido, y lo que enseñó

El primer ejemplo adiabático estaba a 5 bar, y ahí la mezcla **cruza la
frontera de fase** al reaccionar: la presión de burbuja pasa de 456 a 545
kPa y la entalpía da un salto de 18 kJ/mol. El motor lo resuelve igual y
lo reporta, pero no es un ejemplo que se entienda. Los presets van a 20
bar, que es además como se opera la isomerización de butano de verdad y
por el mismo motivo.

## ✅ Tres algoritmos, y por qué son tres

| Situación | Algoritmo | Por qué ése |
|---|---|---|
| una reacción, T impuesta | `brentq` **acotado** | el intervalo estequiométrico garantiza el cambio de signo |
| varias, T impuesta | `root`/`hybr` | no hay intervalo que acote un sistema |
| T incógnita | sustituciones sucesivas **+** `least_squares`/`trf` acotado | ver arriba |

Con varias reacciones **no se imponen límites** a los avances: los de cada
una suponiendo las otras a cero no son conservadores —dos reacciones
pueden consumir el mismo reactivo— así que la factibilidad se **comprueba**
después. Un límite que no limita es peor que no tenerlo, porque invita a
confiar en él.

## ⚠ Y una corrección que el contrato pedía

**Imponer $r^+ = r^-$ no demuestra equilibrio termodinámico.** Describe un
estado estacionario con esas dos tasas, nada más. El preset
`reactor-en-equilibrio` se llama así porque sus tasas son iguales, no
porque el motor haya comprobado un equilibrio — que no lo ha hecho, porque
el equilibrio calculado no está implementado.

## Verificación

`tests/validar_laboratorio.py` sube a **diez grupos y 312
comprobaciones**. Los casos de primer y segundo orden en base de fracción
molar tienen **solución analítica**, así que no hay números escritos a
mano:

| Caso | Analítico | Coincide a |
|---|---|---|
| 1.º orden, $r = kx_A$ | $\xi = kF_{A0}/(F_0+k) = 33.3\overline{3}$ | $10^{-12}$ |
| 2.º orden, $r = kx_A^2$ | raíz de $F_0^2\xi = k(F_{A0}-\xi)^2$ | $10^{-9}$ |
| dos reacciones acopladas | sistema lineal a mano | $10^{-9}$ |

Y se comprueba que **lo declarado es lo que corre**: `brentq` acotado con
una reacción, `hybr` con varias, el arranque **y** el solver en el
acoplado, y los límites de T saliendo de la tabla.

Once rechazos más con su código en la cinética, y los
**veinte presets** de `/laboratorio/ejemplos` reenviados al endpoint.
**21/21 suites.**

## ⬜ Lo que queda de la lista

De los cinco puntos de la próxima prioridad, esta fase cubre **1, 2 y 5**.
No están, y conviene que no se dé por hecho:

- **Punto 3, lote transitorio.** Otro régimen: estado inicial, integración
  ODE en el tiempo, muestreo, tolerancias del integrador, agotamiento y no
  negatividad a lo largo de la trayectoria. `estacionario` sigue siendo
  obligatorio.
- **Punto 4, equilibrio químico calculado.** El motor no obtiene la
  composición de equilibrio a partir de $\Delta G$ y $K$. Lo único de ese
  territorio es `desde_equilibrio`, que usa $K_{eq}$ para una inversa
  **cinética**.
- **Puntos 6 a 10**: entropía y exergía, conducción 1D, difusión, momento,
  más de dos volúmenes, y el decantador expuesto.
- **Los transversales**: expresiones tipadas con comprobación dimensional
  automática, y sensibilidad e incertidumbre.
- **Fase vapor no ideal**, que sigue siendo el límite termodinámico de
  fondo.

---

# Fase 20: Lote transitorio, equilibrio calculado y balanceo exacto

Prioridad vigente de `../../frontend/PENDIENTES_BACKEND_CLAUDE.md`: puntos **3**
y **4**, más la parte de la «migración de exploraciones locales» que
corresponde al balanceo racional y a Hess/Kirchhoff. Solo backend.

## ✅ Balanceo con aritmética EXACTA

$A\nu = 0$ con `fractions.Fraction` y eliminación de Gauss sobre los
racionales, no con floats. La respuesta correcta son enteros pequeños, y
un método numérico los devuelve como `0.9999999999999998`: con SVD hay que
*reconocer* los enteros, y eso es adivinar — `0.333333` puede ser 1/3 o el
redondeo de otra cosa. El residuo elemental sale **exactamente 0**.

Y las tres respuestas posibles importan las tres:

| Dimensión | Qué significa |
|---|---|
| 0 | No hay reacción, y decirlo **es** la respuesta |
| 1 | Una reacción, única salvo escala y signo |
| > 1 | Un **subespacio**: se devuelve la base y no se elige |

El tercero no es raro. `CO/CO₂/H₂/H₂O/CH₄` da **dimensión 2** —
desplazamiento de gas de agua y metanación — y devolver una cualquiera
sería decidir qué química ocurre.

**El signo no lo decide la conservación.** $A\nu = 0$ se cumple igual con
$\nu$ y con $-\nu$, así que o lo dice el usuario o es una convención, y se
declara como tal.

### ⚠ Y exigía grupos UNIFAC sin necesitarlos

El módulo lo decía y el servicio hacía lo contrario: construía un
`ProveedorTermodinamico` completo, que exige UNIFAC, así que **la
combustión del metano fallaba** — el ejemplo canónico de un balanceo.
Balancear es la conservación de los átomos: hace falta saber de qué está
hecha cada especie y nada más. Corregido, con `aptas_para_termodinamica`
avisando de que esa reacción no se puede calcular.

## ✅ Equilibrio químico calculado

El punto 4. $Q_r = K_r(T)$, con $K$ de $\Delta G$ de **formación** y no de
ninguna cinética.

**K por dos rutas y la diferencia medida.** Van't Hoff supone $\Delta H$
constante; la ruta rigurosa usa Kirchhoff para $\Delta H$ y la integral de
$\Delta C_p/T$ para $\Delta S$. Se devuelven las dos: con los xilenos a
400 K difieren un **2.5 %**, y con los butanos $C_p$ pasa de 142 a 211
J/(mol·K) entre 300 y 400 K. La aproximación no es inocua, y ahora no hay
que confiar en que lo sea.

**Un detalle que ahorra una integral:** $\Delta H(T) = \nu\cdot(H_f +
h_{sens}(T))$. Las entalpías sensibles ya llevan dentro la integral de
$\Delta C_p$ que Kirchhoff pide. Es la **misma identidad** que explica por
qué el balance de energía no debe corregir $\Delta H$ con Kirchhoff (fase
18): allí lo contaría dos veces y aquí lo da gratis.

**El criterio de estabilidad es el hessiano, no $\Delta G = 0$.** Cero dice
que es un punto *estacionario* de la energía de Gibbs, no que sea un
mínimo. Se calcula el hessiano por diferencias centradas y se devuelven
los autovalores, que son el criterio y no una etiqueta.

**Las restricciones elementales se cumplen por construcción** —un avance
sobre una ν validada conserva los elementos— y añadirlas como ecuaciones
habría contado dos veces lo mismo. La que sí hay que imponer es la no
negatividad, porque $\ln 0 = -\infty$.

**Y el residuo se mide en $\ln Q - \ln K$.** Con $\Delta G$ de −60 kJ/mol,
$K$ vale $10^{10}$: un residuo $Q - K$ no se puede escalar de forma útil.

## ✅ Lote transitorio

El punto 3. $dn_i/dt = \sum_r \nu_{ir} r_r(T, \mathbf{x}(t))$, integrado
con `solve_ivp`. Usa **las mismas leyes** que el CSTR: la ley es la misma
física en los dos regímenes, y tener dos implementaciones sería tener dos
físicas que se pueden separar.

**El agotamiento se detecta con un EVENTO del integrador**, no mirando si
algún número salió negativo. Un chequeo a posteriori sobre las muestras
**se perdería el cruce si cae entre dos**. El evento lo localiza con la
misma precisión que la trayectoria.

**La no negatividad se comprueba sobre lo DEVUELTO.** Se recorta al
*evaluar* la ley —UNIFAC con fracciones negativas no significa nada— y se
comprueba sobre la trayectoria. Recortar y callarse convertiría un dato
imposible en una curva plausible.

**LSODA por omisión** porque una red con constantes muy distintas es
rígida sin avisar, y LSODA cambia solo. Las tolerancias se declaran y
viajan en la respuesta: una trayectoria sin tolerancia declarada no se
puede reproducir.

## ✅ La verificación: soluciones analíticas

Las redes de primer orden las tienen, y las tres topologías que el
contrato nombra son exactamente ésas. Con los xilenos —o-, m- y p-, todos
C8H10— $\gamma = 1$ **exactamente**, así que la base de actividad correcta
coincide con la ideal y la analítica vale sin aproximar nada.

| Red | Solución | Coincide a |
|---|---|---|
| A → B | $n_A = n_{A0}e^{-kt/N}$ | $10^{-7}$ mol sobre 100 |
| A → B → C | la clásica consecutiva | $10^{-7}$ mol |
| A → B, A → C | $n_A = n_{A0}e^{-(k_1+k_2)t/N}$ | $10^{-7}$ mol |
| A ⇌ B | relajación exponencial | $10^{-6}$ mol |

Y dos consecuencias que no son el valor de una curva: el máximo del
intermedio cae donde el álgebra lo pone, y la selectividad de la paralela
es exactamente $k_1/k_2$. Con los cuatro integradores sale lo mismo.

Del equilibrio: la **razón de actividades en la solución ES K**, pedida al
proveedor por separado, a $10^{-12}$ relativo, con $\Delta G_{rxn}=0$ y
$\sum\nu_i\mu_i=0$. Y Le Chatelier sale solo: siendo exotérmica, K baja de
2.593 a 2.382 al subir de 330 a 400 K.

## ⚠ Y la comprobación cruzada forzó un cambio de resultado

Un lote con cinética termodinámicamente consistente debe converger, cuando
$t\to\infty$, a la composición que calcula el servicio de equilibrio: son
dos caminos sin nada en común, uno integra una ODE y el otro resuelve
$\ln Q = \ln K$.

No coincidían. Con los xilenos a 400 K el lote llegaba a una composición
**0.5 % distinta**, y el motivo era que `desde_equilibrio` usaba **van't
Hoff** (K = 2.441) mientras el servicio de equilibrio usaba la ruta
rigurosa (K = 2.382).

Dos partes del motor contestando cosas distintas a la misma pregunta es
peor que una aproximación declarada, así que `desde_equilibrio` pasó a la
ruta rigurosa. **Ahora coinciden a $5.6\times10^{-17}$.**

Es un cambio de resultado visible: un cálculo guardado con
`desde_equilibrio` da otro número. Está dicho en la entrega.

## ⚠ Dos defectos de la entrega anterior corregidos

- **`codigos.LAB_CAUDAL_NO_FISICO` no existía** (el código se llama
  `CAUDAL_NO_FISICO`, sin prefijo). Un `AttributeError` en el camino de
  error, que es justo donde menos se mira.
- **El arranque del equilibrio caía en el límite** cuando la alimentación
  no traía alguno de los productos: con $n_B = 0$ el avance tiene que ser
  estrictamente positivo, y $\xi = 0$ está exactamente en la frontera.

## Verificación

`tests/validar_laboratorio.py` sube a **trece grupos y 389
comprobaciones**. Treinta pares petición/respuesta en `docs/ejemplos/`,
generados **ejecutando** el endpoint. **21/21 suites.**

## ⬜ Lo que queda

- **Punto 6: entropía, segunda ley y exergía.** Los potenciales químicos
  ya están, con su estado estándar declarado; falta el balance de entropía
  con temperatura de frontera y la exergía con ambiente explícito.
- **Punto 7: conducción 1D** en capas y contactos.
- **Punto 8: difusión y películas.**
- **Punto 9: momento e hidráulica.**
- **Punto 10: más de dos volúmenes**, puertos tipados, y el **decantador
  expuesto** — que sigue sin ruta HTTP desde la fase 17.
- **Los transversales**: expresiones tipadas con comprobación dimensional
  automática, y sensibilidad e incertidumbre.
- **El lote adiabático**, declarado como no soportado.
- **Que `/diagrama/resolver` consuma el mismo ensamblador** que el
  laboratorio. Hoy los módulos de física (`cinetica`, `equilibrio`,
  `lote`, `balanceo`, `estequiometria`) ya están separados de sus
  endpoints y de la UI; lo que falta es que el diagrama los use, y eso es
  una refactorización de lo existente y no una capacidad nueva.
- **Fase vapor no ideal**, que sigue siendo el límite termodinámico de
  fondo.
