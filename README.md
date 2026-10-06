# Simulador de destilación reactiva

Simulador de procesos **orientado a ecuaciones** (EO) para destilación,
reacción y separación líquido-vapor. No es un script que calcula en una
dirección fija: cada equipo aporta ecuaciones a un pool compartido y el
orquestador decide qué se despeja según los datos disponibles, como hace
un simulador comercial.

```
fresca ──► mezclador ──► intercambiador ──► flash ──┬──► vapor
              ▲                                      │
              │                                      └──► líquido ──► divisor ──┬──► purga
              └──────────────── reciclo ─────────────────────────────────────────┘
```

---

## Qué hay dentro

| Capa | Contenido |
|---|---|
| `thermodynamics/` | UNIFAC predictivo vía `thermo`, ELV (puntos de burbuja y de rocío), entalpía unificada $h(T,x,\text{fase})$, equilibrio y cinética de reacción |
| `core/` | McCabe-Thiele, Ponchon-Savarit, FUG, **flash**, CSTR con balance de energía, topología reactiva (RCM/RRCM, azeótropos), orquestador y flowsheet |
| `backend/`, `api/` | FastAPI sobre el núcleo; frontera de unidades con `pint` |
| `frontend/` | Next.js: diagramas McCabe-Thiele, Ponchon-Savarit, ternarios y editor de flowsheet |
| `docs/` | **La matemática**: qué ecuaciones se resuelven, con qué método, bajo qué suposiciones y hasta dónde son válidas |
| `roadmap.md` | **La bitácora**: qué se construyó, qué se rompió y cómo se arregló |

El núcleo opera en **SI puro** (`float`/NumPy). `pint` vive solo en la
frontera, nunca dentro de los bucles numéricos.

---

## Equipos disponibles

**Separación** — columna binaria (McCabe-Thiele / Ponchon-Savarit),
columna multicomponente (FUG), flash L-V, separador de componentes,
absorbedor/desorbedor (Kremser), decantador líquido-líquido.

**Reacción** — CSTR con cinética y balance de energía, reactor de
equilibrio químico, reactor de flujo pistón (PFR).

**Térmicos** — intercambiador de calor, intercambiador de dos corrientes
(integración energética), válvula de expansión isentálpica.

**Transporte y mezcla** — bomba, compresor/turbina, mezclador, divisor.

El flowsheet detecta **reciclos** automáticamente, los corta (*tearing*)
y los converge con Wegstein.

---

## Diseñar, no solo calcular

Lo anterior contesta *"con estos datos, ¿cuánto da?"*. Las dos
herramientas siguientes contestan las preguntas que de verdad se hacen al
diseñar.

**Especificaciones de diseño.** En vez de dar el reflujo y obtener la
pureza, se pide la pureza y el simulador busca el reflujo:

```python
from core.especificaciones import Especificacion

resultado = diagrama.resolver_con_especificaciones(
    [Especificacion(objetivo="producto.x2", valor=0.9055,
                    manipulada="r1.T_salida", minimo=330.0, maximo=370.0)],
    **datos,   # sin r1.T_salida: la especificación la convierte en incógnita
)
```

El objetivo y la variable que se mueve **pueden estar en equipos
distintos, con un reciclo en medio**: cada evaluación resuelve el diagrama
completo, reciclos convergidos. El rango no es decoración — acota la
búsqueda a la zona donde el diagrama se puede resolver.

Y el conteo de grados de libertad lo tiene en cuenta: cada
especificación suma **una ecuación**, así que un problema al que le
faltaba un dato (GL = 1) queda cerrado (GL = 0). La variable manipulada ya
era incógnita; sumarla otra vez es el error fácil de cometer aquí.

**Barridos de sensibilidad.** Mover una variable y ver cómo responde el
resto:

```python
filas = diagrama.barrido("col1.R", [1.6, 2.0, 3.0, 5.0, 10.0],
                         seguir=["col1.N", "col1.Q_c"], **datos)
```

Un punto que falle **no tumba el barrido**: se anota el motivo y sigue,
que es lo que se quiere al explorar un rango con sus bordes. El
compromiso clásico sale solo: de $R=1.6$ a $R=10$, $N$ baja de 19.5 a 7.5
y $Q_c$ sube de 3.1 a 13.2 MW.

Las dos están también en la API (`POST /diagrama/resolver` acepta
`especificaciones`; `POST /diagrama/barrido` es nuevo) y en la interfaz, en
la pestaña **«Diseño»** del flowsheet. El detalle completo, incluidas las
decisiones que no son obvias, en
[`docs/13-especificaciones.md`](docs/13-especificaciones.md).

---

## Instalación y uso

```bash
pip install -r requirements.txt
python run_tests.py          # las 19 suites del núcleo y la API, ~285 s
```

Y las de la interfaz, que comprueban lo que ninguna suite de Python puede
ver —que el número correcto llegue a la pantalla— necesitan los dos
servidores vivos y un navegador:

```bash
python -m uvicorn backend.main:app --port 8001 --reload   # en una terminal
cd frontend && npm run dev                                 # en otra
cd frontend && node verificar_todo.mjs                     # las 18 suites
```

El lanzador mira el **código de salida** de cada suite, no su salida de
texto: cada una termina con un mensaje distinto, así que buscar «TODO OK»
daba por buena una suite que acababa de reventar con otra frase.

Las versiones de `requirements.txt` están **fijas a propósito**: las
validaciones comparan contra valores exactos (`365.515693 K, idéntico bit
a bit`), y eso solo significa algo contra una versión fija de `thermo`.

Un ejemplo mínimo:

```python
from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.elv import CalculadoraELV
from core.flash import EvaluadorFlash

prov  = ProveedorTermodinamico(["benzene", "toluene"])
flash = EvaluadorFlash(CalculadoraELV(prov))

r = flash.isotermico(T=368.0, P=101325.0, z=[0.5, 0.5])
print(r["beta"], r["x"], r["y"])
```

Ver también `ejemplo_columna_destilacion.py`, `ejemplo_orquestador.py` y
las plantillas de `backend/ejemplos_flowsheet.py`.

---

## Cómo se valida

Una sola regla, aplicada en todo el proyecto:

> **Que un método corra no es que funcione.** Se valida contra algo
> independiente: una fórmula cerrada, un balance que debe cerrar, un
> valor de literatura, o una propiedad física que debe cumplirse.

No cuenta como validación *"devuelve un array de la forma correcta"* ni
*"el número parece razonable"*. Sí cuentan, y son reales:

- El balance de energía de una planta con reciclo cierra a
  $4\times10^{-12}$ relativo.
- El azeótropo etanol/agua aparece en $x = 0.894$ (literatura: 0.894).
- La solubilidad del MIBK en agua a 25 °C sale 1.41 % en peso contra el
  1.55 % de Perry's tabla 15-8, y el reparto del ácido acético se queda
  entre un 17 % y un 26 % corto — **el error está medido y escrito**, no
  escondido tras una tolerancia holgada.
- El líquido que sale de un flash está en su punto de burbuja a
  $10^{-9}$ K, comprobado contra una rutina independiente.
- Un reactor adiabático con volumen grande alcanza el equilibrio químico
  *a la temperatura que el propio balance de energía produjo*
  ($\prod a_i^{\nu_i}/K_{eq} \to 0.987$).
- Una especificación de diseño se comprueba **contra el camino directo**:
  pedir $N = 12$ devuelve $R = 2.241647$, y evaluar McCabe-Thiele con ese
  $R$ —sin pasar por el lazo— devuelve $N = 12.00000000$.
- Una bomba con $P_1 = 101325$, factor $= 3$ y $P_2 = 100000$ dados a la
  vez **se rechaza**: son tres condiciones sobre dos variables y
  $3 \times 101325 \neq 100000$. Antes respondía «resuelto por completo».

El detalle completo, y **los límites**, en
[`docs/12-validacion.md`](docs/12-validacion.md).

---

## De dónde sale cada número

Cada respuesta de `/diagrama/resolver` puede decir con qué se calculó, qué
le pasa y cuánto se puede fiar uno de ella:

- **`calculo`** — versión del motor y commit de git (con sufijo `-sucio`
  si el árbol tenía cambios), versiones de `thermo`/`chemicals`/`fluids`
  —que son la versión *real* del proveedor termodinámico— y una **huella
  SHA-256 determinista de las entradas físicas**. Dos peticiones con la
  misma huella deben dar el mismo resultado; si dan otro, el cambio está
  en el motor o en sus dependencias.
- **`diagnosticos`** — las incidencias con **código estable**, categoría
  (datos / física / numérica / modelo) y severidad. La categoría viene de
  donde se generó el problema, **nunca de buscar palabras en el mensaje**.
  Y `hay_errores` separa «se calculó todo» de «el resultado es válido»:
  no son lo mismo.
- **`convergencia`** — por bloque, el método, la tolerancia y el residuo
  **cuando el algoritmo de verdad evalúa uno**. Una construcción de
  McCabe-Thiele no trae residuo y dice por qué; inventarle uno sería una
  mentira con cara de precisión.

Los tres son opcionales y aditivos. Detalle en
[`docs/14-trazabilidad.md`](docs/14-trazabilidad.md).

---

## Qué NO hace

Esto es tan importante como lo anterior y está documentado equipo por
equipo:

- **Sin columna rigurosa MESH todavía** — solo el andamiaje.
- Sin dinámica: todo es estado estacionario.
- **Equilibrio líquido-líquido: sirve para explorar, no para dimensionar.**
  Medido contra Perry's tabla 15-8 (agua/ácido acético/MIBK a 25 °C),
  UNIFAC-LLE subestima la razón de reparto entre un 17 % y un 26 %, de
  forma sistemática, y su punto de pliegue queda más adentro que el real.
  Acierta la tendencia, que es lo que decide si un disolvente sirve; la
  magnitud no basta para dimensionar. Perry's lo dice igual: «UNIFAC and
  other estimation methods are not sufficiently accurate». Sin extracción
  multietapa (necesita plato a plato) y sin forma de ajustar los
  parámetros binarios a datos del sistema.
- Caída de presión **por equipo**, no un perfil interno: una columna de
  atajo no puede llevarlo (su curva de equilibrio está precalculada a una
  sola presión).
- **Dimensionado parcial**: diámetro de columna de platos por la
  correlación de Fair (los dos extremos, manda el mayor) y área del
  intercambiador de dos corrientes por U·A·LMTD, validados contra el
  Ejemplo 9 de Perry's. Sin platos reales desde las teóricas, sin columnas
  de relleno, sin área de condensador ni rehervidor (haría falta modelar
  los servicios para tener su temperatura), y **sin costes** — un diámetro
  y un área no son un precio.

---

## Compartir una simulación

Cada simulación cabe dentro de un enlace. «Copiar enlace» en la lista de
simulaciones genera una URL que lleva el diagrama entero —componentes,
unidades, equipos y datos— y que se abre en cualquier navegador sin
instalar ni registrar nada.

Detalles que importan:

- Va en el **fragmento** (`#`) de la URL, así que no se envía al servidor
  ni aparece en sus registros.
- **No viajan los resultados, solo el planteamiento.** Quien abra el
  enlace los recalcula con el mismo núcleo validado — un enlace no puede
  transportar cifras que el simulador no produzca.
- No hay base de datos detrás: el enlace no caduca porque no depende de
  que se conserve nada.
- Un diagrama que no quepa (8000 caracteres) se rechaza explicándolo y
  remite al archivo `.simproc.json`.

---

## Documentación

Empezar por [`docs/README.md`](docs/README.md). Los documentos se leen en
orden y cada uno enlaza al siguiente.

La matemática va en Markdown con LaTeX, versionada junto al código y
actualizada en el mismo commit que el cambio que la motiva — que es la
única forma de que no se quede obsoleta.
