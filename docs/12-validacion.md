# 12. Validación y límites

[← Unidades](11-unidades.md) · [Índice](README.md)

---

## 12.1 Criterio de validación

Una regla, aplicada en todo el proyecto:

> **Que un método corra no es que funcione.** Se valida contra algo
> independiente: una fórmula cerrada, un balance que debe cerrar, un
> valor de literatura, o una propiedad física que debe cumplirse.

Ejemplos de lo que **no** cuenta como validación:

- "Devuelve un array de la forma correcta."
- "No lanza excepciones."
- "El número parece razonable."

Ejemplos de lo que **sí**:

- El balance de energía global cierra a error relativo $0$.
- El azeótropo etanol/agua aparece en $x = 0.894$ (valor de literatura).
- Ida y vuelta por el reactor recupera la composición a $10^{-12}$.
- Las líneas estequiométricas son **idénticas bit a bit** al script
  original.

---

## 12.2 Qué está verificado

### Termodinámica

| Comprobación | Resultado |
|---|---|
| UNIFAC realmente activo | $\gamma$ se desvía fuerte de 1 en tres sistemas |
| Azeótropo etanol/agua | $x = 0.894$ (literatura: 0.894) |
| Orden de volatilidad | acetona 329 K < metanol 338 K < agua 373 K |
| Van't Hoff, MTBE exotérmica | $K_{eq}$ baja de 72.3 (298 K) a 2.31 (350 K) |
| $y = \alpha x/\sum\alpha x$ ≡ Raoult modificada | error $10^{-16}$ |
| Punto de burbuja sin regresión | benceno/tolueno 50/50 = 365.515693 K, idéntico bit a bit |
| Rocío → burbuja: el líquido de la primera gota devuelve la $P$ | $10^{-9}$ relativo |
| Rocío → burbuja: devuelve el vapor original $y = z$ | $9\times10^{-15}$ |

### Entalpía

Todas contra algo **independiente del módulo** — el $C_p$ y el
$\Delta H_{vap}$ del proveedor, o `quad` sobre ellos.

| Comprobación | Resultado |
|---|---|
| $h_L(T_{ref}) = 0$, también para los puros | exacto |
| $dh/dT = C_p$ del proveedor (250–480 K) | error relativo $\sim 10^{-10}$ |
| Tabulado ≡ `quad` sobre el $C_p$ del proveedor | $10^{-10}$ relativo — **por eso Ponchon-Savarit no cambió ningún número** |
| $h_V - h_L = \sum y_i \Delta H_{vap,i}$ | $10^{-4}$ relativo |
| Mezcla ideal: $h(\mathbf{x}) = \sum x_i h_i$ | exacto |
| Ida y vuelta $T \to h \to T$ (260–500 K) | $10^{-10}$ K |
| $h_L$ estrictamente creciente en $T$ | 400 puntos, incremento mínimo 113 J/mol |
| Forma vectorizada (perfil) ≡ escalar | $10^{-12}$ |
| Fuera de rango | avisa en vez de extrapolar |

### Flash (una etapa MESH)

| Comprobación | Resultado |
|---|---|
| Balance de materia $z = \beta y + (1-\beta)x$ | $0$ a $5\times10^{-17}$ |
| $\sum x = \sum y = 1$ (no impuesto: sale de Rachford-Rice) | $0$ exacto |
| Equilibrio $y_i = K_i x_i$ con $K$ **recalculada** desde cero | $10^{-12}$ |
| $\beta$ monótona creciente con $T$ | de 0.047 a 0.949 |
| Justo sobre la burbuja: $\beta \to 0$, $y \to y_{burbuja}$ | $\beta = 1.6\times10^{-4}$ |
| Justo bajo el rocío: $\beta \to 1$, $x \to x_{rocío}$ | $\beta = 0.99983$ |
| Flash P-H reproduce la entalpía pedida (4 regímenes) | $10^{-11}$ relativo |
| Válvula isentálpica: $h$ se conserva | $10^{-8}$ relativo |
| El calor aportado aparece íntegro en $h$ | 12000.000000 J/mol exacto |
| Ida y vuelta $\beta \to T \to \beta$ | $10^{-10}$ |
| Ternario acetona/metanol/agua | balance y equilibrio cierran (27–34 iteraciones) |

### Plantas encadenadas

Lo que estas comprueban no es ningún método sino **la frontera entre
equipos**: que la corriente que uno entrega sea la que el siguiente
recibe, en materia y en energía.

| Cadena | Comprobación | Resultado |
|---|---|---|
| Intercambiador → válvula → flash | GL = 0 y resuelve entera | ✓ |
| ídem | Balance de materia total y por componente | $10^{-10}$ |
| ídem | **Balance de energía global** | error relativo $1.9\times10^{-12}$ |
| ídem | Cada equipo por separado ($Q$ entregado, isentalpía, adiabaticidad) | $10^{-8}$ J/mol |
| ídem | La válvula enfría al expandir | 434.6 K → 369.6 K, $\beta = 0.368$ |
| Mezclador → intercambiador → flash → divisor → **reciclo** | El lazo se detecta y converge | 49 vueltas a $5\times10^{-13}$ |
| ídem | Balance de materia global (fresca = vapor + purga) | $10^{-10}$ mol/s |
| ídem | **Balance de energía global con lazo** | error relativo $4.2\times10^{-12}$ |
| ídem | Con 0 %, 30 %, 50 %, 70 % y 85 % de recirculación | materia y energía cierran en las cinco |
| Mezclar líquido con vapor | Medir cuánto perdía la definición vieja | 9 032 J/mol (56 %) y 23.8 K |
| ídem | El mezclador del flowsheet da la $T$ con la fase real | 368.130236 K, coincide con el cálculo directo |
| Flash → columna McCabe-Thiele | El líquido del flash **está** en su punto de burbuja | $10^{-9}$ K contra `burbuja_T` |
| ídem | GL = 0, y balances de flash, columna y planta entera | ✓ |

El balance de energía con lazo es la comprobación que **solo pasa si el
mezclador, el intercambiador, el flash y el divisor miden la entalpía con
la misma definición**. Es la razón de existir de
[§4](04-entalpia.md).

### Métodos de separación

| Método | Comprobación | Resultado |
|---|---|---|
| McCabe-Thiele | Diseño inverso $N = 10 \to R = 2.4830 \to N = 10.000000$ | ✓ |
| McCabe-Thiele | Condensador parcial vs. total | diferencia exactamente 1.000000 |
| McCabe-Thiele | $E_{MV}$ decreciente → $N$ creciente | 12.51 → 13.95 → 18.00 → 25.34 |
| Ponchon-Savarit | Balance de energía global | **error relativo 0.000e+00** |
| Ponchon-Savarit | $Q_c/D = (R+1)(H_V-H_L)$ | $10^{-9}$ |
| Ponchon-Savarit | Colinearidad $\Delta_D$–$F$–$\Delta_B$ | pendientes iguales a $10^{-6}$ |
| PS vs. McCabe-Thiele | $N$ comparable escalando sobre el mínimo | razón 1.002–1.033, monótona |
| FUG | Recuperaciones pedidas 0.98 | obtenidas 0.98000 |
| FUG | Balance total y por componente (4 comp.) | cierra |
| FUG | $N > N_{min}$, $R > R_{min}$ | 11.557 > 8.213; 2.0 > 0.616 |

### Reactor

| Comprobación | Resultado |
|---|---|
| $F_{out} = F_{in} + \nu_{tot}\xi$ | ✓ |
| Ida y vuelta (adelante → atrás) | recupera $F$ y $\mathbf{x}$ a $10^{-12}$ |
| Avance deducido desde una pureza | 20.0000000000 (exacto) |
| Conversión | 0.4 exacto |
| Tres entradas a $T$ distintas | GL = 0, balances cierran |
| Avance imposible | rechazado con motivo físico |

#### Balance de energía del reactor

| Comprobación | Resultado |
|---|---|
| Ida y vuelta isotermo → calor dado | recupera $T$ a $10^{-10}$ K |
| Ida y vuelta adiabático → isotermo | $Q = 1.7\times10^{-9}$ W |
| Con $\xi = 0$ es un intercambiador | $Q = F(h_2 - h_1)$ |
| Exotérmica isoterma (MTBE, $\xi=12$) | $Q = -702.4$ kW de refrigeración |
| Exotérmica adiabática | 330.00 → 383.45 K |
| Endotérmica: $T$ baja y $Q > 0$ | ✓ |
| $Q_{exo} - Q_{endo} = 2\xi\Delta H_{rxn}$ | $-1382400.0000$ W exacto |
| **Cierra con $\Delta H_{rxn}(T_{ref})$** | residuo $1.6\times10^{-9}$ W |
| **Con $\Delta H_{rxn}(T_{out})$ no cerraría** | 41.31 kW, igual al término duplicado al vatio |
| Acoplado cinética+energía: $V$ creciente | $\xi$ y $T$ crecen; residuo $< 10^{-9}$ |
| Acoplado: cinética y balance por separado | reproducen $\xi$ y $T$ a $10^{-9}$ |
| Acoplado, $V$ grande → equilibrio químico | $\prod a^\nu / K_{eq}$: 0.350 → 0.935 → 0.987 |
| Guardas: sin entalpía, sin $\Delta H_{rxn}$, referencias distintas, tanque hirviendo | las cuatro avisan |
| En el flowsheet: los 3 modos, GL = 0 | balance cierra a $0$ y $2\times10^{-9}$ W |
| Compatibilidad: reactor sin proveedor | funciona como antes, sin variable $Q$ |

### Solver

| Comprobación | Resultado |
|---|---|
| Escalabilidad | 120 operaciones (721 bloques) en 0.082 s, GL = 0 |
| Independencia del orden | resultado idéntico con bloques invertidos |
| Seis topologías mezcladas | GL = 0 y resuelven las seis |
| Reciclo: balance global | mezcla 480 = 100 + 380; fresco − producto = $\xi$ |
| Reciclo: varias fracciones | converge con 0 %, 30 %, 50 %, 70 %, 90 % |
| Wegstein | 154 → 9 vueltas al 90 %, misma solución |
| Pool 100 % escalar | 0 variables no escalares, incluso con FUG |

### Destilación reactiva

| Comprobación | Resultado |
|---|---|
| $\sum x = 1$ a lo largo de cada curva | $2\times10^{-16}$ |
| VLE riguroso en cada etapa | $10^{-16}$ contra `burbuja_P` |
| Salto químico ∥ $\nu$ proyectado | $10^{-16}$ |
| Invariante de Barbosa-Doherty | 20 puntos aleatorios |
| $Da = 0$ ≡ caso inerte | idéntico |
| Curvas residuales inertes | 8/8 se enriquecen en el pesado |
| Líneas estequiométricas | **idénticas bit a bit** al script original |

---

## 12.3 Las suites

| Suite | Qué cubre |
|---|---|
| `tests/validar_corriente.py` | Objeto corriente y sus operaciones |
| `tests/validar_diagrama_corrientes.py` | Flowsheet, grados de libertad, redundancias |
| `tests/validar_diagrama_flujo.py` | Modelo antiguo (referencia) |
| `tests/validar_entalpia.py` | $h(T,x)$ contra el proveedor y contra `quad`, inversión $h \to T$ |
| `tests/validar_flash.py` | Rachford-Rice, fronteras de fase, flash P-H, rocío |
| `tests/validar_planta_encadenada.py` | **Cadenas de equipos**: balances globales de materia y energía, con y sin lazo |
| `tests/validar_energia_reactor.py` | Balance de energía del CSTR: los 3 modos, el caso acoplado y las guardas |
| `tests/validar_fug.py` | Fenske, Underwood (una y varias raíces), Gilliland |
| `tests/validar_mccabe_thiele.py` | Escalonamiento, diseño inverso, Murphree, cargas |
| `tests/validar_ponchon_savarit.py` | Polos, colinearidad, $Q_c/D$ mínimo, cruce con MT |
| `tests/validar_termodinamica.py` | ELV, topología reactiva, azeótropos |
| `frontend/verificar_*.mjs` | Interfaz real en navegador (10 suites) |

Las suites de navegador usan `puppeteer-core` contra el Edge del sistema:
**no comprueban que el componente renderice, sino que el número correcto
llegue a la pantalla**.

### Cómo se lanzan

```bash
python run_tests.py          # todas, ~60 s, código de salida 0 o 1
python run_tests.py flash    # solo las que casen con el filtro
python run_tests.py -v       # con la salida completa de cada una
```

Antes había que lanzarlas **una a una y leerlas con los ojos**, y nada
garantizaba que no se hubiera olvidado ninguna. Eso significa que no
existía un *"el proyecto está verde"* comprobable, solo un *"las que miré
estaban bien"*. `run_tests.py` devuelve un código de salida real, que es
lo que hace falta para engancharlo a un hook de pre-commit o a CI.

> **Fallo encontrado al montarlo:** en una consola Windows por defecto
> (cp1252), cualquier suite que imprimiera un símbolo griego moría con
> `UnicodeEncodeError`. No es que fallara la validación: **no llegaba a
> ejecutarse**, que es peor — y solo funcionaba si quien la lanzaba sabía
> poner `PYTHONIOENCODING=utf-8`. Cada suite se protege ahora por dentro.

---

## 12.4 Límites del simulador

Esta sección es tan importante como el resto del documento.

### Físicos

| Límite | Consecuencia |
|---|---|
| **Sin caída de presión** | $P$ uniforme en cada equipo |
| **Sin dinámica** | Solo estado estacionario |
| **Reactor líquido monofásico** | La cinética usa actividades de fase líquida; si el balance da una $T$ sobre la burbuja, se rechaza |
| **Sin estabilidad dinámica** | La multiplicidad de estados estacionarios del CSTR se detecta y se reporta, pero saber cuál es estable necesita el modelo dinámico |
| **Una sola reacción** | No hay reacciones en paralelo ni en serie |
| **Fase vapor ideal** | Mal a $P$ alta o cerca del crítico |
| **Sin entalpía de exceso** | No hay calor de mezcla |
| **Sin dimensionado ni costes** | Etapas teóricas, no una columna comprable |

### Del solver

| Límite | Consecuencia |
|---|---|
| **Acoplamiento sin lazo** | Si dos bloques se acoplan y ninguno resuelve solo, se reporta como incógnitas |
| **Reciclos anidados** | Soportados por la detección, **no verificados** |
| **Consistencia dentro del lazo** | Datos incompatibles en un reciclo dan no-convergencia, no un mensaje claro |
| **Divisor sin balance de energía propio** | Reparte $T$ y $P$ (correcto para split ideal), no estresado |
| **La fase de una corriente no se valida contra quien la recibe** | Un flash puede mandar vapor a una columna que espera líquido: el resultado será incoherente y nadie avisa ([§5.7](05-flash.md)) |

### De los métodos

| Método | Límite |
|---|---|
| McCabe-Thiele | Binario; CMO; no cruza azeótropos |
| Ponchon-Savarit | Binario; $H_F$ desde $q$ es aproximado |
| FUG | Gilliland es empírica (±10–20 %); no detecta azeótropos; $\alpha$ promediada |
| Flash | Sustituciones sucesivas, no Newton: se atasca (diciéndolo) en mezclas muy no ideales; sin equilibrio líquido-líquido |
| CSTR | Mezclado perfecto; una sola reacción; solo CSTR (no PFR ni batch); estacionario |
| Topología reactiva | Mapeo discreto isotermo; una reacción; el mapa inerte no marca puntos singulares |

### Equipos que no existen

- PFR, reactor batch
- Columna de absorción / extracción
- Compresor, turbina
- Columna rigurosa MESH (solo existe el andamiaje)

Ya implementados y validados: **flash**, **intercambiador de calor** y
**válvula de expansión** ([§5](05-flash.md)).

---

## 12.5 Patrón de fallos recurrente

Casi todos los defectos encontrados en este proyecto pertenecen a **una
sola familia**:

> Un resultado numéricamente plausible construido sobre algo físicamente
> imposible, presentado sin aviso.

Ejemplos, todos reales:

| Síntoma visible | Causa | Cómo se detectó |
|---|---|---|
| $N = -21.4$ etapas | Claves invertidos → $\ln(\alpha<1) < 0$ → $N_{min} < 0$ | Armando un caso combinado |
| $N = 3.95$ "razonable" | $R_{min} = -0.068$, la guarda `R <= R_min` pasaba | Recuperaciones del 70 % |
| Mapa vacío sin motivo | `gestor=None` reventaba cada curva; el `except` se lo tragaba | Test de física, no de forma |
| Curvas como segmentos rectos | Muestreo sobre el $\xi$ pedido, no el integrado | Medir puntos por curva |
| $\sum x$ llegaba a 14.6 | RK45 se desintegra en el punto estacionario | Comprobar el invariante |
| "Resuelto por completo" con balance violado por 26 mol/s | El bucle salta bloques sin incógnitas | Caso construido a mano |
| Caudal negativo en una plantilla | Unidad global contaminada: 100 kg/h ≠ 100 mol/s | Reproducir el número del error |
| Todo "adim." | Backend caído; `adim.` usado como comodín | Distinguir los dos casos |
| GL = −5 con seis equipos | Conteo de composiciones hecho a mano por bloque | Probar topologías no ajustadas |
| Diagrama a medias sin motivo | Tope de iteraciones fijo (30) con 29 equipos | Medir pasadas vs. tamaño |
| GL = −1 al meter un flash antes de una columna | La columna re-fijaba la $T$ de una alimentación que el flash ya había fijado. La guarda existía para la **presión** y para FUG, pero no para la $T$ de la columna binaria | Encadenar dos equipos que nunca se habían tocado |
| `q_fijo=1.0` no hacía nada | Solo se publicaba en la rama Ponchon-Savarit; en McCabe-Thiele se ignoraba en silencio y arrastraba consigo $N$, $Q_c$, $Q_R$ y las temperaturas — con el contador diciendo GL = 0 | Igual: encadenar flash → columna |
| El reactor acoplado decía "no convergió" habiendo solución | Un único arranque tímido (1 % del límite estequiométrico, $T=T_{in}$) no alcanza el estacionario de una exotérmica fuerte. Desde 10 de 15 arranques distintos converge siempre al mismo punto | Probar el mismo caso desde varios puntos de partida |
| Mezclar líquido con vapor daba 344.3 K en vez de 368.1 K | El mezclador medía $h$ como si toda corriente fuera líquida: se perdían 9 032 J/mol de calor latente (56 % de la entalpía de la mezcla) y la mezcla se declaraba líquida siendo bifásica | Unificar la entalpía y comparar las dos definiciones sobre un caso con vapor |

**La lección operativa:** el error más peligroso no es el que hace fallar
el programa, sino el que devuelve un número que parece bien. La defensa es
comprobar **invariantes físicos** (balances que deben cerrar, sumas que
deben dar 1, signos que no pueden ser negativos), no la ausencia de
excepciones.

---

## 12.6 Cómo añadir un método nuevo

Para mantener la coherencia del sistema:

1. **Escribir el evaluador en SI puro**, en `core/`, sin unidades y sin
   saber nada del flowsheet.
2. **Envolverlo como `BloqueEcuaciones`**, declarando honestamente
   `variables_entrada` y `n_ecuaciones`. Si es invertible, decirlo; si no,
   también.
3. **Guardas físicas en el propio evaluador**, con mensajes que digan qué
   hacer — no solo qué falló.
4. **Conectarlo al diagrama** renombrando sus variables a las de las
   corrientes. El descuento por composiciones dependientes es
   automático ([§2.3](02-solver.md#23-grados-de-libertad)).
5. **Validar contra un invariante**, no contra "corre".
6. **Documentarlo aquí**, incluyendo sus límites.

---

[← Unidades](11-unidades.md) · [Índice](README.md)
