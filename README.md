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

Columna binaria (McCabe-Thiele / Ponchon-Savarit) · columna
multicomponente (FUG) · **flash** L-V · **intercambiador de calor** ·
**válvula** de expansión isentálpica · reactor **CSTR** con balance de
energía · mezclador · divisor · bomba.

El flowsheet detecta **reciclos** automáticamente, los corta (*tearing*)
y los converge con Wegstein.

---

## Instalación y uso

```bash
pip install -r requirements.txt
python run_tests.py          # las 11 suites de validación, ~60 s
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
- Los equipos térmicos nuevos (flash, intercambiador, válvula) están en
  el núcleo y la API de Python, **aún no en la interfaz web**: el núcleo
  resuelve 10 tipos de equipo y la interfaz deja dibujar 5.

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
