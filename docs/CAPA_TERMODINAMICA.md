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

## 4. Límites
- **Sólidos:** ningún paquete dinámico los tiene.
- **Volumen con estado supuesto:** no tiene cierre que evaluar (`NoSoportado`). Es el caso de las hojas del solver TS.
- **Solver:** la trayectoria la integra todavía el motor de ensamblaje existente (camino B). El compilador y los solvers propios del modelo común son el paso 4.
