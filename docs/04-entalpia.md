# 4. Entalpía de corriente

[← Termodinámica](03-termodinamica.md) · [Índice](README.md) · [Siguiente: Flash →](05-flash.md)

---

## 4.1 Por qué esto es un documento aparte

Porque durante buena parte del proyecto **la misma magnitud estuvo
implementada tres veces, con tres convenciones distintas**:

| Dónde | Qué calculaba |
|---|---|
| Ponchon-Savarit | $\int_{T_{ref}}^{T} \sum_i x_i C_{p,i}\,dT'$ con `quad`, una cuadratura por composición |
| Mezclador del flowsheet | $h = \left(\sum_i x_i C_{p,i}(T)\right)(T - T_{ref})$ — **la forma linealizada** |
| McCabe-Thiele | $\Delta H_{vap}$ y $C_p$ combinados a mano dentro de las cargas térmicas |

Las dos primeras no son la misma función salvo que $C_p$ sea constante, y
no lo es: entre 300 K y 380 K el $C_p$ del benceno sube un 15 %.

Mientras cada módulo se validaba por su cuenta eso no se notaba, porque
cada uno era internamente consistente. Se nota **en cuanto se encadenan
equipos**: los balances de energía se pasan la corriente unos a otros, y
dos definiciones distintas de $h$ significan energía que aparece o
desaparece en la frontera entre un equipo y el siguiente.

Hoy hay **una sola** definición, en `thermodynamics/entalpia.py`, y todos
los módulos la usan.

---

## 4.2 El camino termodinámico

Referencia: **componentes puros líquidos a $T_{ref} = 298.15$ K, con
$h_i = 0$.**

$$h_L(T, \mathbf{x}) = \sum_i x_i \int_{T_{ref}}^{T} C_{p,L,i}(T')\,dT'$$

$$h_V(T, \mathbf{y}) = h_L(T, \mathbf{y}) + \sum_i y_i \Delta H_{vap,i}(T)$$

Leído como un camino: se parte de los componentes puros líquidos a
$T_{ref}$, se calientan hasta $T$, y —para el vapor— se vaporizan **a esa
misma $T$**.

Esto **no es una aproximación**. Es un camino real, y $\Delta H_{vap}$ se
evalúa a la temperatura a la que se terminó de calentar, no a la de
ebullición normal. Como la entalpía es función de estado, el camino
elegido no afecta a ninguna *diferencia* de entalpía, que es lo único que
entra en un balance.

Para una corriente que viene en dos fases, con $\beta = V/F$:

$$h = (1-\beta)\,h_L(T, \mathbf{x}) + \beta\,h_V(T, \mathbf{y})$$

### La única aproximación: mezcla ideal

No hay entalpía de exceso. $h$ de una mezcla es la suma ponderada de las
entalpías de los puros:

$$h_L(T, \mathbf{x}) = \sum_i x_i\, h_{L,i}(T)$$

Es decir, **mezclar no libera ni absorbe calor**. `thermo` no ofrece un
modelo de $h^E$, así que la alternativa a esta suposición no es un modelo
mejor sino ningún modelo. Es la misma suposición que ya hacía todo el
proyecto; lo que cambió es que ahora está escrita en un solo sitio y
documentada.

Consecuencia práctica: en sistemas muy no ideales (agua/etanol,
agua/acetona), el calor de mezcla real puede ser del orden de cientos de
J/mol. Frente a un $\Delta H_{vap}$ de ~30–40 kJ/mol es pequeño, pero no
es cero, y en un balance que solo mueve calor sensible puede llegar a
importar.

---

## 4.3 Por qué se tabula por componente puro

Como $C_{p,\text{mezcla}} = \sum_i x_i C_{p,i}$ y $\mathbf{x}$ **no
depende de $T$**, la integral de la mezcla es la suma ponderada de las
integrales puras:

$$\int_{T_{ref}}^{T} \sum_i x_i C_{p,i}\,dT' = \sum_i x_i \int_{T_{ref}}^{T} C_{p,i}\,dT'$$

Eso permite tabular $h_i(T)$ **una sola vez por componente** y después
evaluar cualquier composición como un producto punto, sin volver a tocar
`thermo`.

La implementación no integra numéricamente: ajusta un spline cúbico a
$C_{p,i}(T)$ sobre 161 nodos y usa su **primitiva analítica**
(`CubicSpline.antiderivative()`).

Medido: Ponchon-Savarit pasó de ~0.24 s solo en construir sus entalpías a
0.121 s la construcción completa del evaluador.

---

## 4.4 Rango de validez y qué pasa fuera

| | Valor por defecto | Por qué |
|---|---|---|
| $T_{min}$ | 200 K | Por debajo, las correlaciones de $C_p$ líquido de `thermo` están muy por debajo del punto de fusión de casi todo |
| $T_{max}$ | $\min(550\text{ K},\ 0.98\,T_c^{min})$ | Por encima de la $T_c$ más baja, `thermo` devuelve $\Delta H_{vap} = 0$ exacto, lo que metería un codo en el spline |

Fuera del rango tabulado, y solo hasta 150 K más allá, se **extrapola
linealmente** con el $C_p$ del borde (o sea, $C_p$ constante). Es la
extrapolación más tibia posible y mantiene $h$ monótona y $C^1$;
extrapolar la propia cúbica se dispara a las pocas decenas de kelvin.

Más allá de ese margen **no se inventa un número**: se lanza un error que
dice cuál era el rango y sugiere construir la calculadora con
`T_min`/`T_max` explícitos.

---

## 4.5 La inversión $h \to T$

Muchos equipos plantean el balance al revés: se conoce la entalpía de
salida y hace falta la temperatura (mezclador adiabático,
intercambiador con $Q$ dado, válvula).

**Para líquido** la inversión es única: $C_p > 0$ en todo el rango —se
verifica al construir la tabla— así que $h_L$ es estrictamente creciente
en $T$ y `brentq` encuentra la raíz sin ambigüedad.

Esto sustituyó al punto fijo de 8 pasadas que hacía el mezclador, que se
cortaba por número de vueltas y no por convergencia.

**Para vapor la monotonía no está garantizada** y por eso se comprueba en
vez de suponerse:

$$C_{p,V} = C_{p,L} + \frac{d(\Delta H_{vap})}{dT}$$

y el segundo término es negativo, porque $\Delta H_{vap}$ cae al subir
$T$. Lejos de la crítica $C_{p,L}$ domina con holgura —para benceno a
350 K, 150 frente a $-59$ J/(mol·K)— pero cerca de $T_c$ el
$\Delta H_{vap}$ se desploma y la suma podría cambiar de signo.
`T_desde_h_vapor` muestrea el tramo y **falla explicando** si $h_V(T)$
deja de crecer, en vez de devolver una de dos raíces al azar.

---

## 4.6 Una tabla por proveedor, a propósito

`entalpia_de(proveedor)` memoriza la calculadora en el propio
`ProveedorTermodinamico`. No es solo caché: es **lo que garantiza que el
mezclador, la columna y el flash de un mismo diagrama midan la energía
con la misma tabla y la misma referencia**. Dos tablas construidas por
separado con rangos distintos darían $h$ ligeramente distintas y los
balances entre equipos dejarían de cerrar exactamente.

Si alguien pide una $T_{ref}$ distinta sobre un proveedor que ya tiene
calculadora, **falla**. Devolver la cacheada en silencio sería peor: el
que la pidió creería estar trabajando con su referencia y no lo estaría,
y la discrepancia solo aparecería como un balance que no cierra varios
equipos más abajo.

---

## 4.7 Qué está verificado

Ver [Validación](12-validacion.md) para la tabla completa. En resumen,
`tests/validar_entalpia.py` contrasta contra cosas **independientes del
propio módulo**:

- $dh/dT = C_p$ por diferencias finitas contra el $C_p$ **del proveedor**,
  no contra el spline interno — error relativo $\sim 10^{-10}$.
- La integral tabulada coincide con `quad` sobre el $C_p$ del proveedor
  (el cálculo exacto que hacía Ponchon-Savarit) a $10^{-10}$ relativo.
  Por eso sustituirlo **no cambió ningún número** de Ponchon-Savarit.
- $h_V - h_L = \sum y_i \Delta H_{vap,i}$ contra el $\Delta H_{vap}$ del
  proveedor.
- $h(T_{ref}) = 0$ exacto, incluidos los componentes puros.
- Ida y vuelta $T \to h \to T$ a $10^{-8}$ K.

---

[← Termodinámica](03-termodinamica.md) · [Índice](README.md) · [Siguiente: Flash →](05-flash.md)
