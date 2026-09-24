# 1. Arquitectura

[← Índice](README.md) · [Siguiente: El solver →](02-solver.md)

---

## 1.1 El problema que resuelve esta arquitectura

Un simulador de procesos tiene que responder preguntas en **cualquier
dirección**:

- *"Entra esto, ¿qué sale?"* — simulación directa.
- *"Quiero esta pureza, ¿qué reflujo necesito?"* — diseño inverso.
- *"Conozco los productos, ¿cómo era la alimentación?"* — reconciliación.

Un programa escrito como una secuencia de cálculos (`leer feed → calcular
etapas → calcular productos`) solo sabe responder la primera. Las otras dos
exigen reescribirlo.

La salida a esto es tratar el problema como lo que es: **un sistema de
ecuaciones**. No importa qué variables se conocen; importa que el número
de ecuaciones y de incógnitas cuadre.

---

## 1.2 Las cuatro capas

```
┌─────────────────────────────────────────────────────────┐
│  frontend/  (Next.js + React)                           │
│  Lienzo, paneles, gráficas. Convierte unidades en local │
└────────────────────────┬────────────────────────────────┘
                         │  JSON, todo en SI
┌────────────────────────┴────────────────────────────────┐
│  backend/  (FastAPI)                                    │
│  Validación de forma (Pydantic), rutas HTTP.            │
│  Frontera de UNIDADES: aquí vive pint.                  │
└────────────────────────┬────────────────────────────────┘
                         │  floats y np.ndarray, SI puro
┌────────────────────────┴────────────────────────────────┐
│  core/  — el simulador                                  │
│  Métodos (McCabe-Thiele, Ponchon-Savarit, FUG, CSTR),   │
│  el orquestador de ecuaciones, la topología reactiva.   │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────┴────────────────────────────────┐
│  thermodynamics/  — propiedades                         │
│  Adaptador sobre `thermo`: UNIFAC, Psat, Cp, ΔHvap,     │
│  ΔHf, ΔGf. Único punto de contacto con datos externos.  │
└─────────────────────────────────────────────────────────┘
```

### Regla de oro: `core/` y `thermodynamics/` son SI puro

Dentro del núcleo **no existen las unidades**. Todo es `float` o
`np.ndarray` en SI: mol/s, K, Pa, J/mol, W. No hay objetos con unidades,
no hay conversiones, no hay `pint`.

Esto no es purismo. Es que una conversión de unidades en mitad de un
cálculo es una de las formas más caras de equivocarse, y la única defensa
fiable es que **no pueda haberla**: si el núcleo no sabe de unidades, no
puede convertir mal.

Las unidades viven en la frontera (`config/settings.py`,
`backend/nucleo_unidades.py`) y se documentan en
[§11 Unidades](11-unidades.md).

---

## 1.3 Orientado a ecuaciones, pero por bloques

Hay dos filosofías clásicas para resolver un flowsheet:

| | Secuencial-modular | Orientado a ecuaciones (EO) |
|---|---|---|
| **Idea** | Cada equipo se resuelve entero, en orden aguas abajo | Todas las ecuaciones de la planta en un solo sistema simultáneo |
| **Ventaja** | Cada equipo usa su método más robusto | Resuelve en cualquier dirección; reciclos naturales |
| **Problema** | No resuelve hacia atrás; los reciclos necesitan tratamiento aparte | Un Newton global sobre miles de ecuaciones es frágil y difícil de diagnosticar |

Este simulador usa una **vía intermedia**, que es la decisión de diseño
central del proyecto:

> Cada bloque resuelve **su** ecuación con **su** método, el más robusto
> para esa ecuación concreta. El orquestador solo decide *qué bloque puede
> resolverse ahora* y comparte los resultados en un conjunto de variables
> común.

Es literalmente lo que hace un ingeniero a mano: mira qué ecuación ya
tiene suficientes datos, la resuelve, apunta el resultado, y vuelve a
mirar.

**Lo que se gana:** robustez. McCabe-Thiele se resuelve con `brentq` sobre
un bracket físico; el balance de materia, con `root` sobre un sistema
bilineal de 2×2; Underwood, con `brentq` entre volatilidades adyacentes.
Fundirlos en un Newton global perdería todo eso.

**Lo que se pierde, y no se oculta:** si dos bloques quedan acoplados de
forma que *ninguno* es resoluble por sí solo, esto no lo resuelve — lo
reporta como incógnitas restantes. Es una frontera real del método, no un
fallo. La única excepción son los reciclos, que sí tienen tratamiento
propio ([§2.7](02-solver.md#27-reciclos-tearing)).

---

## 1.4 La corriente como elemento de primera clase

La decisión estructural de la que cuelga todo lo demás.

En el modelo anterior (`core/diagrama_flujo.py`, conservado como
referencia) un puerto guardaba **un objeto `Corriente` entero** como valor
atómico. O conocías la corriente completa, o no conocías nada. Eso
obligaba a envolver cada operación como un bloque no invertible, y hacía
imposible dar "cualquier subconjunto de variables".

En el modelo actual (`core/diagrama_corrientes.py`), cada corriente aporta
**variables escalares** al conjunto compartido:

$$
\texttt{s1.F},\quad \texttt{s1.T},\quad \texttt{s1.P},\quad
\texttt{s1.x0},\ \texttt{s1.x1},\ \dots,\ \texttt{s1.x}_{n-1}
$$

Y cada operación aporta sus ecuaciones **ya existentes**, renombradas para
apuntar a las variables de las corrientes que toca.

### Consecuencia: conectar equipos no necesita "cables"

Si la columna `col1` produce el destilado `s2` y el reactor `r1` consume
`s2`, los dos bloques **comparten literalmente las mismas variables**
`s2.F`, `s2.x0`, … No hay que transportar nada: la información fluye en
cualquier dirección con el mismo bucle de punto fijo.

### Consecuencia: la invertibilidad ya estaba, solo se desperdiciaba

`BalanceMateriaGlobal` siempre supo resolver cualquier 2 de sus 6
variables. `SolucionadorMcCabeThiele` siempre supo resolver cualquier 1 de
sus 5. Lo que impedía usarlo era la envoltura, no la matemática. **No se
reescribió ningún método** para conseguir la resolución bidireccional.

---

## 1.5 El mecanismo de renombrado

`renombrar_bloque(bloque, mapa)` devuelve el mismo bloque con sus
variables internas apuntando a variables globales:

```
{ "F": "s1.F", "z_F": "s1.x0", "D": "s2.F", "x_D": "s2.x0", ... }
```

El renombrado es una **biyección**, así que `puede_resolver` —que cuenta
incógnitas— sigue significando exactamente lo mismo. El solver de la
operación no se entera de nada.

Esta función, escrita para conectar operaciones a corrientes, resultó ser
exactamente lo que hacía falta años después para implementar el corte de
reciclos ([§2.7](02-solver.md#27-reciclos-tearing)): allí se usa para que
quien *produce* la corriente cortada escriba en un alias interno. **No
hubo que tocar ni un bloque.**

---

## 1.6 Dónde vive cada cosa

| Módulo | Contenido | Documentado en |
|--------|-----------|----------------|
| `core/orquestador.py` | `BloqueEcuaciones`, `Orquestador`, renombrado, verificación de consistencia, fábricas de bloques | [§2](02-solver.md) |
| `core/diagrama_corrientes.py` | El flowsheet: corrientes, operaciones, grados de libertad, reciclos | [§2](02-solver.md) |
| `core/balance_materia.py` | $F = D+B$, $Fz_F = Dx_D + Bx_B$ | [§2.2](02-solver.md) |
| `core/mccabe_thiele.py` | Método binario y–x | [§6](06-mccabe-thiele.md) |
| `core/ponchon_savarit.py` | Método binario entálpico | [§7](07-ponchon-savarit.md) |
| `core/fug.py` | Fenske-Underwood-Gilliland multicomponente | [§8](08-fug.md) |
| `core/flash.py` | Flash L-V: Rachford-Rice, P-H, spec de vaporización | [§5](05-flash.md) |
| `core/reactor_cstr.py` | Reactor continuo de tanque agitado | [§9](09-reactor-cstr.md) |
| `core/topology.py` | Motor topológico reactivo | [§10](10-destilacion-reactiva.md) |
| `core/transformaciones.py` | Espacio transformado de Barbosa-Doherty | [§10.4](10-destilacion-reactiva.md) |
| `core/analisis_nodos.py` | Búsqueda de azeótropos reactivos | [§10.6](10-destilacion-reactiva.md) |
| `thermodynamics/proveedor.py` | Adaptador sobre `thermo` | [§3.1](03-termodinamica.md) |
| `thermodynamics/elv.py` | Puntos de burbuja y de rocío | [§3.3](03-termodinamica.md), [§3.5](03-termodinamica.md) |
| `thermodynamics/entalpia.py` | $h_L$, $h_V$ tabuladas e inversión $h \to T$ | [§4](04-entalpia.md) |
| `thermodynamics/reaccion.py` | $K_{eq}(T)$, $r(T,x)$ | [§3.7](03-termodinamica.md) |

---

## 1.7 Qué NO hay en esta arquitectura

Declarado explícitamente para que nadie lo busque:

- **No hay caída de presión** en ningún equipo. $P_{salida} = P_{entrada}$
  (o la de operación del equipo).
- **No hay dinámica.** Todo es estado estacionario.
- **No hay dimensionado ni costes.** Se calculan etapas teóricas y cargas
  térmicas, no una columna comprable.
- **No hay modelo de entalpía de exceso.** Las entalpías de mezcla son
  promedios ponderados de las puras (sin calor de mezcla), consistente con
  las suposiciones de los métodos que las usan.

---

[← Índice](README.md) · [Siguiente: El solver →](02-solver.md)
