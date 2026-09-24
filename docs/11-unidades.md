# 11. Unidades

[← Destilación reactiva](10-destilacion-reactiva.md) · [Índice](README.md) · [Siguiente: Validación →](12-validacion.md)

---

## 11.1 El principio

> El núcleo (`core/`, `thermodynamics/`) es **SI puro**. Las unidades
> viven en la frontera.

Una conversión de unidades en mitad de un cálculo es de las formas más
caras de equivocarse, y la única defensa fiable es que **no pueda
haberla**.

---

## 11.2 La tabla afín

Todas las conversiones que el frontend necesita son **afines**:

$$
\boxed{\;\text{valor}_{SI} = \text{valor}\cdot f + d\;}
$$

El desplazamiento $d$ es lo que hace funcionar las temperaturas:

| Unidad | $f$ | $d$ | Comprobación |
|---|---|---|---|
| K | 1 | 0 | — |
| °C | 1 | 273.15 | 100 °C → 373.15 K ✓ |
| °F | 5/9 | 255.372 | 212 °F → 373.15 K ✓ |
| kmol/h | 1/3.6 | 0 | 360 kmol/h → 100 mol/s ✓ |

La tabla **la genera `pint`** en el servidor (`GET /unidades`) y el
frontend la usa para convertir en local. Así no hay una ida y vuelta al
servidor por cada tecla, pero **las conversiones no se escriben a mano en
JavaScript**: `pint` sigue siendo la única fuente de verdad.

Los factores se obtienen midiendo dos puntos:

```
d = Quantity(0.0, símbolo).to(SI).magnitude
f = Quantity(1.0, símbolo).to(SI).magnitude - d
```

---

## 11.3 Magnitudes disponibles

| Magnitud | Unidades ofrecidas (la primera es la del SI) |
|---|---|
| `flujo_molar` | mol/s, kmol/h, mol/h, kmol/s |
| `flujo_masico` | kg/s, kg/h, g/s, t/h, lb/h |
| `temperatura` | K, °C, °F, °R |
| `presion` | Pa, kPa, bar, atm, psi, mmHg |
| `potencia` | W, kW, MW, BTU/h, cal/s |
| `energia_molar` | J/mol, kJ/mol, cal/mol |

Lo que no aparece en el mapa variable→magnitud es **adimensional**
(fracciones molares, $q$, $R$, $N$, conversión) y no ofrece cambio de
unidades.

---

## 11.4 El caudal másico NO es una unidad

Este es el punto conceptual del documento.

Hay **una sola** variable de caudal por corriente: $F$, en mol/s.
Expresarlo en moles o en masa es cuestión de la unidad elegida. Pero la
conversión **no es afín**:

$$
\dot{m} = F\cdot \frac{MW_{mezcla}(\mathbf{x})}{1000}
$$

y $MW_{mezcla} = \sum_i x_i\,MW_i$ **depende de la composición**. Un
kilogramo por segundo son 11.56 mol/s con $x_{benceno} = 0.4$ pero 12.58
con $x = 0.9$.

Por eso un caudal dado en masa **no puede** tratarse como un simple
cambio de unidad: tiene que esperar a conocer la composición.

### La solución: es una ecuación, no una unidad

Dar el caudal en masa añade una **restricción** al sistema:

$$
\boxed{\;F\cdot\frac{\sum_i x_i\,MW_i}{1000} \;=\; \dot{m}_{dado}\;}
$$

Es un bloque más, que se dispara cuando la composición se conoce. Cuenta
como **una ecuación**, exactamente igual que dar el caudal en moles: los
grados de libertad no cambian. Verificado: GL = 0 en ambos casos.

Las masas molares salen de `thermo` (`Chemical.MW`), no del cliente.

### Consecuencia de diseño

El usuario ve **una** `F`. La conversión es un detalle interno.

> Exponer `F` y `m` como dos variables trasladaba al usuario un problema
> de implementación. Fue un error de diseño corregido.

---

## 11.5 Las unidades viven en la simulación

Cada simulación guarda su propio mapa variable→unidad:

```
{ "s1.F": "kg/h", "s2.T": "degC" }
```

La preferencia se guarda con la **clave completa** (`s1.F`), así que cada
corriente puede llevar sus propias unidades: una en kg/h y otra en mol/s
sin que se pisen.

### Por qué está en la simulación y no en el navegador

Era una preferencia **global** del navegador, indexada por nombre de
variable. Eso produjo un fallo real y difícil de ver:

> Haber elegido kg/h una vez hacía que **cualquier simulación futura**
> leyera `F` en kg/h — incluidas las plantillas, cuyos valores están
> escritos en SI. El `"100"` de la plantilla de reciclo se interpretaba
> como 100 kg/h; con la MW de la mezcla fresca (44.074 g/mol) eso son
> **0.63025 mol/s**, y entonces
> $$0.63025 - 5 = -4.36975\ \text{mol/s}$$
> exactamente el caudal negativo que reportaba el error.

**Los números de una simulación no significan nada sin sus unidades**, así
que las unidades son parte del documento. Las plantillas arrancan sin
preferencias, o sea en SI, que es lo único coherente con cómo están
escritas.

> Las preferencias globales viejas se ignoran a propósito. Restaurarlas
> reintroduciría el fallo.

---

## 11.6 Modos de fallo

### Si la tabla no carga

`"adim."` es una **afirmación física**: esta variable no tiene unidades.
Usarlo como comodín para "no tengo la tabla" hacía que un backend caído
disfrazara $F$, $T$ y $P$ de números puros — justo la clase de error
silencioso que puede arrastrarse a un cálculo.

Ahora se distinguen:

- Tabla caída → la fila dice **"¿unidad?"** y la barra avisa de que no se
  cargaron las unidades.
- `adim.` queda solo para lo que de verdad es adimensional.

### Si falta la masa molar

Para **mostrar** un caudal en masa hace falta la MW de la mezcla, que
depende de la composición. La calcula el backend y la devuelve por
corriente; si la composición no se conoce todavía, se dice
(*"para verlo en masa hace falta la composición de esta corriente"*) en
vez de mostrar un valor inventado.

---

## 11.7 El recorrido completo de un dato

```
Usuario escribe "30645" con la unidad kg/h en s1.F
        ↓
Frontend: es flujo_masico → NO se convierte a mol/s a ciegas.
          Se manda aparte:  caudales_masicos = { "s1": 8.5125 }   [kg/s]
        ↓
Backend: añade el bloque  F·MW(x)/1000 = 8.5125
        ↓
Núcleo: resuelve el sistema. Con MW = 85.125 g/mol → F = 100 mol/s
        ↓
Respuesta: pool en SI + masas_molares_mezcla por corriente
        ↓
Frontend: convierte para mostrar, con la MW de ESA corriente
```

Verificado de punta a punta: 30645 kg/h con MW 85.125 g/mol dan 100 mol/s,
y con $x_D = 0.95$ / $x_B = 0.05$ el destilado sale **50.000 mol/s
exacto** — con s1 en kg/h y s2 en mol/s **a la vez**.

---

[← Destilación reactiva](10-destilacion-reactiva.md) · [Índice](README.md) · [Siguiente: Validación →](12-validacion.md)
