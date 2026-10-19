# Capa termodinámica del modelo común

18 de octubre de 2026. Es el paso 2 de [ARQUITECTURA_MOTOR.md](../ARQUITECTURA_MOTOR.md) §10. Hace operativo el principio de §3 de la arquitectura: **las relaciones termodinámicas siempre están presentes**.

- Código: `core/termodinamica/capa.py`.
- Pruebas: `tests/validar_capa_termodinamica.py` (mezcla) y `tests/validar_capa_agua.py` (agua pura).
- Ejemplos: `docs/ejemplos/modelo-comun/capa-calentamiento-benceno-tolueno.json` y `capa-ebullicion-agua.json`.

## 1. Qué hace

Para un volumen del modelo común con cierre de equilibrio:

| Función | Devuelve |
|---|---|
| `candidatas(modelo, v)` | El conjunto **fijo** de fases candidatas del paquete: `vapor-1`, `liquido-1` y, con modelos de actividad (NRTL, UNIFAC) y más de un componente, `liquido-2`. Una solución ideal no se separa en dos líquidos, así que no tiene `liquido-2`. El agua pura (`agua-iapws95`) tiene `vapor-1` y `liquido-1` |
| `variables(modelo)` | Las variables de estado de cada volumen: T, P, V y, por cada candidata, su cantidad, su composición y su distancia al plano tangente `tm`. Son las mismas en cualquier estado |
| `cierre(modelo, v, n, ("PH", P, H) \| ("UV", U, V) \| ("TP", T, P))` | El estado con **todas** las candidatas |

Cada candidata del estado que devuelve `cierre` trae:

- `presente`, `n`, `beta`;
- `composicion` (si está) o `composicionIncipiente` (la de la primera burbuja o la primera gota);
- `tm`.

Además el estado trae el residuo de complementariedad.

Por cada fase k se cumple:

    beta_k >= 0,    tm_k >= 0,    beta_k · tm_k = 0

- Un líquido subenfriado tiene `beta_vapor = 0` y `tm_vapor > 0`: las ecuaciones del vapor están y no arrojan nada.
- Al calentarlo, `tm_vapor` baja hasta 0 en el punto de burbuja, y desde ahí `beta_vapor` crece.
- En el rocío ocurre lo mismo con el líquido.

Nunca se cambia de modelo ni se activa un modo. T(H) es continua en la frontera de fase; lo que cambia es su pendiente: la arista de las propiedades, que el integrador trata con un evento.

La capa **no duplica física**:

- el reparto es el de `core/mezclas.Sistema` (minimización de G);
- `tm` es su propia prueba de estabilidad;
- la fase de prueba que coincide con una fase presente se descarta con la misma regla del paquete.

## 2. Prueba guía

Un mol de benceno y tolueno equimolar (paquete `mezcla-ideal`) a 101 325 Pa recibe 100 W desde 330 K durante 500 s.

El motor de ensamblaje resuelve la trayectoria a partir del modelo común, que se le entrega como solicitud v2 mediante `a_ensamblaje_v2`. La capa lee cada muestra.

Hay dos referencias independientes del flash:

- **R1. Raoult con Poynting en forma cerrada**, con solo los datos puros del paquete: K_i = Psat_i·exp(v_L,i·(P − Psat_i)/RT)/P. De ella salen:
  - la burbuja (Σ z_i K_i = 1) y el rocío (Σ z_i/K_i = 1);
  - el `tm` de la fase ausente: −ln Σ z_i K_i para el vapor y −ln Σ z_i/K_i para el líquido;
  - la fracción de vapor, por Rachford-Rice.
- **R2. Antoine publicado**, que no usa los datos del paquete.

Resultados (179 comprobaciones correctas):

| Comprobación | Resultado |
|---|---|
| Burbuja y rocío frente a Antoine | 365,275 K frente a 365,262 K; 371,919 K frente a 371,923 K (tolerancia 0,5 K) |
| Malla de 25 temperaturas entre 330 y 390 K | Mismas candidatas siempre. `tm` de la fase ausente igual a R1 (1e-8). β del vapor igual a Rachford-Rice (1e-8). Complementariedad < 1e-9 |
| Trayectoria | El vapor aparece a la T de burbuja de R1 (1e-4 K) y el líquido desaparece a la de rocío (1e-4 K). H(t) = H(0) + Q t. La T de la capa coincide con la del motor en cada muestra (1e-6 K) |
| Antes, durante y después | Antes: β_vapor = 0, con `tm` positivo y decreciente. Durante: `tm` = 0 y β crece de 0 a 1. Después: solo vapor, con el líquido ausente y `tm` > 0 |
| Fronteras de fase | T(H) continua (salto < 1e-3 K) y cambio de pendiente (arista) en las dos transiciones |
| Estructura | Las relaciones del modelo son las ecuaciones del backend |

## 3. Agua pura (IAPWS-95)

La capa envuelve `core/agua_iapws95.py` sin modificarlo: sus evaluaciones PH, UV y TP y su propia prueba de estabilidad.

Para una sustancia pura, la fase ausente no tiene composición que optimizar. Su `tm` es la distancia al plano tangente de Helmholtz a T fija sobre la otra rama de la EOS, en su mínimo ρ_m, por RT y por masa de la fase de prueba:

    tm = TPD(ρ_m) / (ρ_m R T)

Es la misma escala que en las mezclas y se reduce a (g_k(T, P) − g*)/RT cuando la rama tiene raíz a la P del estado.

Por encima de T_c solo hay una rama de fluido: el líquido no puede aparecer y su `tm` es `None`, con β = 0.

**Prueba de ebullición** (`tests/validar_capa_agua.py`, 161 comprobaciones). Un mol de agua a 101 325 Pa recibe 100 W desde 330 K durante 600 s. Las referencias salen de IAPWS-IF97, otra formulación, y de tablas publicadas:

| Comprobación | Resultado |
|---|---|
| T_sat y h_fg de IF97 frente a lo publicado | 373,1243 K (373,124 K); 2256,54 kJ/kg (2256,4) |
| `tm` del vapor ausente en el líquido, de 330 K a T_sat | Igual a (P − Psat)(1/ρ'' − 1/ρ')/RT con las densidades de IF97 (1e-3 relativo) |
| `tm` del líquido ausente en el vapor | Positivo y creciente, dentro del 3 % de la aproximación de gas ideal |
| Trayectoria | Hierve a la T_sat de IF97 (5 mK). Calor de la meseta Q·Δt = m·h_fg (1e-3). T constante en la meseta (1e-6 K). β_vapor = Q(t − t_b)/(m·h_fg) (1e-3). H(t) = H(0) + Q t. La T de la capa coincide con la del motor (1e-6 K) |
| Fronteras | T(H) continua y pendiente nula en la meseta. Por encima de T_c el líquido figura como candidata que no puede aparecer |

## 4. UNIFAC (bloque A de ARQUITECTURA_MOTOR.md §10, 18 de octubre de 2026)

Los tres paquetes UNIFAC (`unifac-original-public`, `unifac-dortmund-public`, `unifac-original-lle-public`) pasan por la capa y por el compilador común sin ninguna rama propia. Prueba: `python tests/validar_capa_unifac.py` (82 comprobaciones, ~5 min). Usa las siete solicitudes dinámicas UNIFAC publicadas por el motor (`docs/ejemplos/motor-unifac/`), llevadas al modelo común.

| Caso | Paquete | Contra el motor existente | Contra una referencia independiente (UNIFAC de `thermo`, otra implementación) |
|---|---|---|---|
| Etanol-agua calentado hasta hervir | original | estado 1e-8; evento en el mismo instante | el vapor aparece a la T de burbuja γ-φ (1e-4 K) |
| Agua, etanol, acetato de etilo, metanol calentados | original | ídem | ídem |
| Las mismas cuatro especies | Dortmund | ídem | ídem |
| Agua con entrada de butanol a 298 K | ELL | ídem | la segunda fase líquida aparece cuando la carga llega a la binodal por isoactividad (1e-8 en fracción molar), con la fase conjugada (1e-5) |
| Etanol-agua con política «monofásico» | original | se detiene en el instante del motor (1e-6 s) | — |
| Red de dos volúmenes, cinco especies, agua que entra en A | original | estado igual hasta la aparición | la segunda fase líquida aparece donde el plano tangente LL cruza cero: 113,58602 s frente a la referencia, entre 113,5860 y 113,5861 s |

En todos los casos:

- las tres candidatas (vapor-1, liquido-1, liquido-2) se publican en cada muestra, con β = 0 antes de aparecer;
- la conservación global de materia y energía queda por debajo de 1e-12;
- la complementariedad β·tm queda por debajo de 1e-8.

**Hallazgo y corrección.** Esta prueba descubrió que, en la red de cinco especies, el motor existente publicaba la segunda fase líquida a 141,41 s, 28 s tarde. Tras localizarla, aceptaba el paso entero sin evento cuando no la reencontraba en el estado reintegrado. Se corrigió el 18 de octubre de 2026 (`core/ensamblaje_red.py`); ahora el motor y el compilador común coinciden con el límite independiente. Detalle en `frontend/MAPA_MOTOR.md` §6.

**Política de fases.** `politica.cantidad = "monofasico"`, `cambioInterno = "prohibido"` y `tiposPermitidos` son supuestos declarados. El compilador detiene el cálculo en el instante en que el conjunto de fases los incumple (evento `politica_incumplida`) y rechaza un estado inicial que ya los incumple.

**Rendimiento.** La red de cinco especies tarda ~255 s en el compilador común. Es un pendiente de pulido de la termodinámica: los flashes rápidos con semilla se repiten en cada etapa.

## 4 bis. Panel Termodinámica de la hoja (18 de octubre de 2026)

Toda hoja del Engine muestra cuatro paneles: Materia, Energía, Momento y **Termodinámica**. La termodinámica no se activa ni se desactiva: es el cierre de estado de cada volumen, «siempre presente». Su vista (`frontend/app/motor/TermodinamicaHoja.tsx`) muestra:

1. **Relaciones siempre presentes:**
   - relación fundamental;
   - cierre de estado UV o PH, según la frontera;
   - reparto entre las fases candidatas;
   - propiedades de la mezcla;
   - equilibrio entre las fases presentes;
   - estabilidad por plano tangente;
   - complementariedad β·tm = 0.
2. **El cierre de cada volumen**, que publica el servidor en `POST /modelo/termodinamica` (`core/termodinamica/descripcion.py`, sin calcular estados):
   - el paquete y su política de fases, o el supuesto con su motivo;
   - las fases candidatas, las mismas que usa la capa;
   - la familia del modelo de estado, con sus ecuaciones: ideal (Raoult con Poynting), actividad (γ_i con UNIFAC o NRTL) o IAPWS-95 (Helmholtz);
   - las relaciones que ensambla el Engine.
3. **Los supuestos termodinámicos posibles**, con su efecto sobre las ecuaciones, en qué volúmenes están activos y dónde se declaran:
   - equilibrio con un paquete;
   - solución ideal;
   - coeficientes de actividad;
   - vapor ideal;
   - líquido incompresible;
   - restringir a una fase;
   - prohibir cambio de fase;
   - u(T) lineal;
   - estado no evaluado.

**La vista es una derivación** (19 de octubre de 2026, principio 10 de la arquitectura):

- Empieza en las relaciones termodinámicas fundamentales (paso 01). Cada supuesto de estado es un paso con su relación, con deshacer y rehacer: una fase, sin cambio de fase, densidad constante, u(T) lineal.
- Esos supuestos se declaran **solo aquí**: `frontend/app/motor/recorridoTermodinamico.ts`, guardado en `recorridoTermodinamico` de la hoja. La derivación de energía conserva únicamente sus pasos y usa la formulación efectiva (`formulacionEnergiaHoja` añade los supuestos termodinámicos).
- Con un cierre real (IAPWS-95, elegido en Estado), «una fase» y «sin cambio de fase» son su política de fases.
- Las hojas guardadas antes se migran al leerlas (`migrarTermoHoja`): los pasos termodinámicos de su derivación de energía pasan, en orden y con sus relaciones, a la termodinámica. La formulación efectiva no cambia; la firma sí, así que conviene volver a resolver.

Las hojas de red termodinámica (los ejemplos multifásicos, UNIFAC y de N componentes) ya no abren otra página: muestran los mismos paneles. Materia y energía presentan las ecuaciones que ensambla el Engine para la red; los interruptores informan («Lo fija la red»).

Prueba: `python tests/validar_descripcion_termodinamica.py` (23): ideal, UNIFAC original y ELL, agua IAPWS-95 y un volumen con u(T) supuesta; las candidatas son iguales a las de la capa.

## 5. Límites
- **Sólidos:** ningún paquete dinámico los tiene.
- **Volumen con estado supuesto:** no tiene cierre que evaluar (`NoSoportado`). Es el caso de las hojas del solver TS.
- **Solver:** desde el paso 4 la trayectoria la integra el compilador común (`core/compilador`, `core/solvers`, [CORTE_VERTICAL.md](CORTE_VERTICAL.md)); el motor de ensamblaje existente (camino B) queda como referencia de comparación.
