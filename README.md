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
absorbedor/desorbedor (Kremser).

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

---

## Instalación y uso

```bash
pip install -r requirements.txt
python run_tests.py          # las 13 suites de validación, ~280 s
```

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
- El líquido que sale de un flash está en su punto de burbuja a
  $10^{-9}$ K, comprobado contra una rutina independiente.
- Un reactor adiabático con volumen grande alcanza el equilibrio químico
  *a la temperatura que el propio balance de energía produjo*
  ($\prod a_i^{\nu_i}/K_{eq} \to 0.987$).
- Una especificación de diseño se comprueba **contra el camino directo**:
  pedir $N = 12$ devuelve $R = 2.241647$, y evaluar McCabe-Thiele con ese
  $R$ —sin pasar por el lazo— devuelve $N = 12.00000000$.

El detalle completo, y **los límites**, en
[`docs/12-validacion.md`](docs/12-validacion.md).

---

## Qué NO hace

Esto es tan importante como lo anterior y está documentado equipo por
equipo:

- **Sin columna rigurosa MESH todavía** — solo el andamiaje.
- Sin dinámica: todo es estado estacionario.
- Una sola reacción; sin equilibrio líquido-líquido; sin caída de presión.
- Sin dimensionado ni costes: etapas teóricas, no una columna comprable.
- Sin dimensionado de equipos reales: el reactor da volumen de tanque,
  pero no hay diámetros de columna, platos ni intercambiadores.

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
