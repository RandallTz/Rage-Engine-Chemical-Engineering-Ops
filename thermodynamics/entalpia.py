"""
Entalpia de corriente h(T, x, fase) -- UNA sola definicion para todo el
simulador.

Por que existe este modulo: la misma magnitud estaba implementada tres
veces, con convenciones distintas.

  - Ponchon-Savarit integraba Cp de la MEZCLA con quad, por cada
    composicion del barrido (referencia 298.15 K).
  - El mezclador de DiagramaCorrientes usaba la forma LINEALIZADA
    h = Cp(T)*(T - T_ref), que no es la integral salvo que Cp sea
    constante -- entre 300 K y 380 K el Cp del benceno sube ~15 %, asi
    que las dos definiciones no dan el mismo numero.
  - McCabe-Thiele combinaba Hvap y Cp a mano dentro de
    calcular_cargas_termicas.

Mientras cada modulo vive aislado eso no se nota. En cuanto se encadenan
operaciones (mezclador -> flash -> columna) los balances de energia se
pasan la corriente unos a otros, y dos definiciones distintas de h
significan energia que aparece o desaparece en la frontera entre equipos.

Camino termodinamico (el mismo para todos los modulos):

    h_L(T, x) = sum_i x_i * integral_{T_ref}^{T} Cp_{L,i}(T') dT'
    h_V(T, y) = h_L(T, y) + sum_i y_i * DHvap_i(T)

o sea: partir de los componentes puros LIQUIDOS a T_ref con h = 0,
calentarlos hasta T y (para el vapor) vaporizarlos A ESA T. Es un camino
real, no una aproximacion: DHvap se evalua a la misma T a la que se
termino de calentar. La unica aproximacion es la MEZCLA IDEAL -- no hay
entalpia de exceso, porque el proveedor no ofrece un modelo para ella.
Es la misma suposicion que ya hacia todo el proyecto, ahora escrita en
un solo sitio.

Rendimiento: como Cp_mezcla = sum_i x_i Cp_i con x independiente de T, la
integral de la mezcla es la suma ponderada de las integrales PURAS. Eso
permite tabular h_i(T) una vez por componente y despues evaluar cualquier
composicion como un producto punto, sin volver a tocar 'thermo'.

Zona libre de pint: floats/np.ndarray en SI (J/mol, K).
"""

import numpy as np
from scipy.interpolate import CubicSpline
from scipy.optimize import brentq

# Margen fuera del rango tabulado en el que todavia se responde, por
# extrapolacion lineal (ver _h_puros_liquido). Mas alla de esto no se
# inventa un numero: se explica que la corriente esta fuera de rango.
_MARGEN_EXTRAPOLACION = 150.0


class CalculadoraEntalpia:
    """
    Tabula h_i(T) y DHvap_i(T) por componente puro una sola vez y sirve
    la entalpia de cualquier mezcla como producto punto.
    """

    def __init__(self, proveedor, T_ref=298.15, T_min=None, T_max=None, n_nodos=161):
        self.proveedor = proveedor
        self.T_ref = float(T_ref)
        self.n = len(proveedor.componentes)

        criticas = [c.Tc for c in proveedor.componentes if c.Tc]
        # Tope por debajo de la Tc mas baja: ahi DHvap ya va camino de
        # cero y 'thermo' lo devuelve como 0.0 exacto por encima, lo que
        # meteria un codo en la spline. Por debajo de la Tc mas baja la
        # distincion liquido/vapor sigue teniendo sentido para todos.
        tope_critico = 0.98 * min(criticas) if criticas else 550.0
        self.T_max = float(T_max) if T_max is not None else min(550.0, tope_critico)
        self.T_min = float(T_min) if T_min is not None else 200.0
        if self.T_min >= self.T_max:
            raise ValueError(
                f"Rango de tabulacion vacio: T_min={self.T_min:.1f} K >= "
                f"T_max={self.T_max:.1f} K. Con estos componentes el tope util "
                f"es {tope_critico:.1f} K (98 % de la Tc mas baja)."
            )

        malla = np.linspace(self.T_min, self.T_max, int(n_nodos))
        Cp = np.empty((len(malla), self.n))
        Hvap = np.empty((len(malla), self.n))
        for k, T in enumerate(malla):
            Cp[k], Hvap[k] = proveedor.propiedades_caloricas(float(T))

        if not np.all(np.isfinite(Cp)) or np.any(Cp <= 0):
            raise ValueError(
                "El proveedor devolvio un Cp liquido no finito o no positivo dentro "
                f"de [{self.T_min:.1f}, {self.T_max:.1f}] K. Sin un Cp positivo en todo "
                "el rango, h(T) no es monotona y no se puede invertir."
            )

        self._malla = malla
        # Spline vectorial (una columna por componente) y su primitiva
        # EXACTA: integrar la spline es analitico, no hace falta cuadratura.
        self._spl_Cp = CubicSpline(malla, Cp, axis=0)
        self._spl_H = self._spl_Cp.antiderivative()
        self._H_ref = self._spl_H(self.T_ref)
        self._spl_Hvap = CubicSpline(malla, Hvap, axis=0)
        self._Cp_borde = (Cp[0].copy(), Cp[-1].copy())

    # ------------------------------------------------------------------
    def _exigir_en_rango(self, T, magnitud):
        T_arr = np.asarray(T, dtype=float)
        fuera = (T_arr < self.T_min - _MARGEN_EXTRAPOLACION) | \
                (T_arr > self.T_max + _MARGEN_EXTRAPOLACION)
        if np.any(fuera):
            culpable = float(T_arr.ravel()[int(np.argmax(fuera))]) if T_arr.ndim else float(T_arr)
            raise ValueError(
                f"{magnitud} pedida a T={culpable:.2f} K, demasiado lejos del rango "
                f"tabulado [{self.T_min:.1f}, {self.T_max:.1f}] K. Fuera de ese rango las "
                "correlaciones de 'thermo' se extrapolan solas y dejan de ser fiables; "
                "si la corriente de verdad esta ahi, construye la calculadora con "
                "T_min/T_max explicitos."
            )

    def _h_puros_liquido(self, T):
        """
        h_i(T) [J/mol] de cada componente puro liquido, con h_i(T_ref)=0.

        Fuera del rango tabulado se extrapola LINEALMENTE con el Cp del
        borde (o sea, Cp constante). Es la extrapolacion mas tibia
        posible y mantiene h monotona y C1; extrapolar la propia cubica
        se dispara a las pocas decenas de kelvin.
        """
        T = np.asarray(T, dtype=float)
        self._exigir_en_rango(T, "Entalpia de liquido")
        T_dentro = np.clip(T, self.T_min, self.T_max)
        h = self._spl_H(T_dentro) - self._H_ref
        bajo = T < self.T_min
        Cp_borde = np.where(bajo[..., None] if T.ndim else bajo,
                            self._Cp_borde[0], self._Cp_borde[1])
        delta = T - T_dentro
        if T.ndim:
            delta = delta[..., None]
        return h + Cp_borde * delta

    def capacidades_calorificas_liquido(self, T):
        """Cp_L,i(T) [J/(mol K)] tal como lo ve este modulo (spline del tabulado)."""
        T = np.asarray(T, dtype=float)
        self._exigir_en_rango(T, "Cp de liquido")
        return self._spl_Cp(np.clip(T, self.T_min, self.T_max))

    def entalpias_vaporizacion(self, T):
        """DHvap_i(T) [J/mol]. Fuera del rango se congela al valor del borde."""
        T = np.asarray(T, dtype=float)
        self._exigir_en_rango(T, "Entalpia de vaporizacion")
        return self._spl_Hvap(np.clip(T, self.T_min, self.T_max))

    # ------------------------------------------------------------------
    def h_liquido(self, T, x):
        """
        h_L(T, x) [J/mol]. Admite T escalar con x de n componentes, o T de
        m elementos con x de forma (m, n) -- la segunda forma es la que
        hara falta para un perfil de columna.
        """
        x = np.asarray(x, dtype=float)
        h_puros = self._h_puros_liquido(T)
        if h_puros.ndim == 1:
            return float(np.dot(x, h_puros))
        return np.einsum("ki,ki->k", x, h_puros)

    def h_vapor(self, T, y):
        """h_V(T, y) = h_L(T, y) + sum y_i DHvap_i(T) [J/mol]."""
        y = np.asarray(y, dtype=float)
        Hvap = self.entalpias_vaporizacion(T)
        if Hvap.ndim == 1:
            return self.h_liquido(T, y) + float(np.dot(y, Hvap))
        return self.h_liquido(T, y) + np.einsum("ki,ki->k", y, Hvap)

    def h(self, T, composicion, fase="liquido"):
        """Despacho por nombre de fase, para quien lleve la fase como dato."""
        if fase in ("liquido", "L", "l"):
            return self.h_liquido(T, composicion)
        if fase in ("vapor", "V", "v"):
            return self.h_vapor(T, composicion)
        raise ValueError(f"Fase desconocida: {fase!r}. Usa 'liquido' o 'vapor'.")

    def h_corriente(self, T, x, y=None, fraccion_vapor=0.0):
        """
        Entalpia MOLAR de una corriente que puede venir en dos fases:

            h = (1 - beta) * h_L(T, x) + beta * h_V(T, y)

        con beta = V/F. Con beta=0 es liquido puro y con beta=1 vapor
        puro, asi que sirve como unica entrada para cualquier corriente
        del flowsheet sin preguntar antes en que fase viene.
        """
        beta = float(fraccion_vapor)
        if beta <= 0.0:
            return self.h_liquido(T, x)
        if beta >= 1.0:
            return self.h_vapor(T, y if y is not None else x)
        if y is None:
            raise ValueError(
                "Una corriente bifasica necesita tambien la composicion del vapor 'y'."
            )
        return (1.0 - beta) * self.h_liquido(T, x) + beta * self.h_vapor(T, y)

    # ------------------------------------------------------------------
    def T_desde_h_liquido(self, h_objetivo, x):
        """
        Invierte h_L(T, x) = h_objetivo.

        Tiene solucion unica porque Cp > 0 en todo el rango (se verifica
        al construir), asi que h es estrictamente creciente en T. Esto
        sustituye al punto fijo de 8 pasadas que hacia el mezclador:
        aqui la raiz es exacta, no una iteracion que se corta por numero
        de vueltas.
        """
        x = np.asarray(x, dtype=float)
        a = self.T_min - _MARGEN_EXTRAPOLACION
        b = self.T_max + _MARGEN_EXTRAPOLACION
        h_a = self.h_liquido(a, x)
        h_b = self.h_liquido(b, x)
        if not (h_a <= h_objetivo <= h_b):
            raise ValueError(
                f"No hay temperatura de liquido con h={h_objetivo:.4g} J/mol para esta "
                f"composicion: entre {a:.1f} K y {b:.1f} K la entalpia solo recorre "
                f"[{h_a:.4g}, {h_b:.4g}] J/mol. Suele significar que la corriente no es "
                "liquida en ese estado (demasiada energia -> esta vaporizada)."
            )
        return float(brentq(lambda T: self.h_liquido(T, x) - h_objetivo, a, b, xtol=1e-10))

    def T_desde_h_vapor(self, h_objetivo, y, T_min=None):
        """
        Invierte h_V(T, y) = h_objetivo.

        A diferencia del liquido, aqui la monotonia NO esta garantizada
        de antemano: Cp_V = Cp_L + d(DHvap)/dT y el segundo termino es
        negativo (DHvap cae al subir T). Lejos de la critica Cp_L domina
        con holgura -- para benceno a 350 K, 150 frente a -59 J/(mol K) --
        pero cerca de Tc el DHvap se desploma y la suma podria cambiar de
        signo. Se comprueba en el tramo usado en vez de suponerlo.
        """
        y = np.asarray(y, dtype=float)
        a = float(T_min) if T_min is not None else self.T_min
        b = self.T_max
        muestras = np.linspace(a, b, 60)
        h_muestras = np.array([self.h_vapor(float(T), y) for T in muestras])
        if np.any(np.diff(h_muestras) <= 0):
            culpable = muestras[int(np.argmin(np.diff(h_muestras)))]
            raise ValueError(
                f"h_V(T) deja de crecer cerca de {culpable:.1f} K para esta composicion: "
                "el DHvap cae mas rapido de lo que sube el Cp del liquido (zona cercana a la "
                "critica). La inversion h -> T no es unica ahi."
            )
        if not (h_muestras[0] <= h_objetivo <= h_muestras[-1]):
            raise ValueError(
                f"No hay temperatura de vapor con h={h_objetivo:.4g} J/mol para esta "
                f"composicion: entre {a:.1f} K y {b:.1f} K la entalpia solo recorre "
                f"[{h_muestras[0]:.4g}, {h_muestras[-1]:.4g}] J/mol."
            )
        return float(brentq(lambda T: self.h_vapor(T, y) - h_objetivo, a, b, xtol=1e-10))


def entalpia_de(proveedor, **kwargs):
    """
    Devuelve LA calculadora de entalpia de este proveedor, creandola la
    primera vez y reutilizandola despues.

    Que sea una por proveedor no es solo cache: es lo que garantiza que
    el mezclador, la columna y el flash de un mismo diagrama usen la
    misma tabla y la misma referencia. Dos tablas construidas por
    separado con rangos distintos darian h ligeramente distintas y los
    balances entre equipos dejarian de cerrar exactamente.
    """
    existente = getattr(proveedor, "_calculadora_entalpia", None)
    if existente is None:
        existente = CalculadoraEntalpia(proveedor, **kwargs)
        proveedor._calculadora_entalpia = existente
        return existente

    # Si alguien pide OTRA referencia sobre el mismo proveedor, devolver
    # la cacheada en silencio seria peor que fallar: el que la pidio
    # creeria estar trabajando con su T_ref y no lo estaria, y la
    # discrepancia solo se veria como un balance de energia que no cierra
    # varios equipos mas abajo.
    T_ref_pedida = kwargs.get("T_ref")
    if T_ref_pedida is not None and abs(float(T_ref_pedida) - existente.T_ref) > 1e-12:
        raise ValueError(
            f"Este proveedor ya tiene una calculadora de entalpia con "
            f"T_ref={existente.T_ref} K y se pidio T_ref={float(T_ref_pedida)} K. "
            "Todos los equipos de un mismo diagrama deben compartir la referencia; "
            "para otra referencia, usa otro ProveedorTermodinamico."
        )
    return existente
