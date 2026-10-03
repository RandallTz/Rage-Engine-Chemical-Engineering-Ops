"""
Equilibrio liquido-liquido (ELL).

Dos fases liquidas en equilibrio cumplen la IGUALDAD DE ACTIVIDADES de
cada componente:

    x_i^I * gamma_i(T, x^I)  =  x_i^II * gamma_i(T, x^II)

mas el balance de materia y las dos sumatorias. Es la misma estructura
que un flash liquido-vapor, con una diferencia que lo cambia todo: aqui
las dos fases se describen con EL MISMO modelo de actividad, asi que

    **la solucion trivial x^I = x^II cumple todas las ecuaciones.**

Siempre. Para cualquier alimento y cualquier temperatura. Un flash L-V no
tiene ese problema porque las dos fases tienen modelos distintos. Por eso
este modulo no se limita a resolver: primero decide si hay dos fases
(analisis de ESTABILIDAD) y solo entonces busca el reparto, arrancando
desde donde la estabilidad dice que hay que arrancar.

EL CONJUNTO DE PARAMETROS, que es la decision mas importante de aqui
----------------------------------------------------------------------
UNIFAC tiene DOS juegos de parametros de interaccion, y no son
intercambiables:

  - el de ELV (`UFIP`), ajustado a datos de equilibrio liquido-vapor;
  - el de ELL (`LLEUFIP`, Magnussen y otros), ajustado a datos de
    equilibrio liquido-liquido.

Usar el de ELV para predecir ELL es un error conocido y sistematico: la
region de inmiscibilidad sale mal, a veces hasta desaparecer. Este modulo
usa el de ELL, y el resto del simulador sigue usando el de ELV para lo
suyo. Son dos modelos, no uno con dos usos.

Y ahi hay una trampa que vale la pena contar, porque el fallo habria sido
silencioso. **Los identificadores de subgrupo NO coinciden entre los dos
juegos.** En el de ELV el 16 es H2O; en el de ELL el 16 es "P2" y el agua
es el 17. El 18 es CH3CO en uno y ACOH en el otro. `thermo` da la
descomposicion de cada molecula en los subgrupos del juego de ELV
(`Chemical.UNIFAC_groups`), asi que pasarla tal cual a las tablas de ELL
calcularia las actividades de MOLECULAS DISTINTAS -- el agua tratada como
"P2" -- y devolveria numeros plausibles y completamente falsos.

Por eso la traduccion va por NOMBRE de grupo y no por numero, y cuando un
grupo no tiene equivalente en el juego de ELL se dice con nombre y
apellido en vez de seguir. De los 113 subgrupos del juego de ELV, 49
tienen equivalente.

LA PRESION no aparece: UNIFAC clasico es funcion de T y composicion
solamente. Mantener las dos fases liquidas es responsabilidad de quien
llama (si la mezcla hierve, esto ya no la describe).

Zona libre de pint: floats y np.ndarray en SI.
"""

import numpy as np
from scipy.optimize import brentq

import thermo.unifac as _uf
from thermo.unifac import UNIFAC

_TOL = 1e-12
# Dos fases cuyas composiciones difieren menos que esto son la MISMA fase:
# es la solucion trivial disfrazada de solucion.
_TOL_TRIVIAL = 1e-4


def _indice_por_nombre():
    """
    Nombre de subgrupo -> identificador en el juego de parametros de ELL.

    Se construye una vez y se cachea en el modulo. El diccionario inverso
    no vale: varios subgrupos pueden compartir nombre, y lo que interesa
    es el primero (son el mismo grupo quimico con distinto reparto).
    """
    if not hasattr(_indice_por_nombre, "_cache"):
        indice = {}
        for identificador, subgrupo in _uf.LLEUFSG.items():
            indice.setdefault(subgrupo.group, identificador)
        _indice_por_nombre._cache = indice
    return _indice_por_nombre._cache


def traducir_grupos(grupos_elv, nombre_componente=""):
    """
    Los subgrupos de una molecula, del juego de ELV al de ELL, POR NOMBRE.

    Es la pieza que evita el fallo silencioso descrito en la cabecera. Si
    algun grupo no existe en el juego de ELL se lanza un error que nombra
    el grupo Y el componente: sin esos dos datos, "no se puede calcular
    ELL" no dice que cambiar.
    """
    indice = _indice_por_nombre()
    traducidos = {}
    faltantes = []
    for identificador, cuenta in dict(grupos_elv).items():
        subgrupo = _uf.UFSG.get(identificador)
        if subgrupo is None:
            faltantes.append(f"subgrupo {identificador} (desconocido)")
            continue
        nuevo = indice.get(subgrupo.group)
        if nuevo is None:
            faltantes.append(subgrupo.group)
            continue
        traducidos[nuevo] = traducidos.get(nuevo, 0) + cuenta
    if faltantes:
        quien = f" de {nombre_componente}" if nombre_componente else ""
        raise ValueError(
            f"El juego de parametros UNIFAC para equilibrio liquido-liquido no tiene "
            f"el/los grupo(s){quien}: {', '.join(faltantes)}. "
            "No es lo mismo que el juego de ELV, que si los tiene: son dos tablas "
            "ajustadas a datos distintos, con 49 de los 113 subgrupos en comun. "
            "Este componente no se puede usar en un calculo de ELL con UNIFAC."
        )
    return traducidos


class CalculadoraELL:
    """
    Equilibrio liquido-liquido con UNIFAC y el juego de parametros de ELL.

    Se construye con el mismo ProveedorTermodinamico que el resto del
    simulador, de donde saca los nombres y la descomposicion en grupos,
    pero NO reutiliza su calculo de gamma: ese usa los parametros de ELV.
    """

    def __init__(self, proveedor):
        self.proveedor = proveedor
        self.n = len(proveedor.componentes)
        nombres = [getattr(c, "name", f"componente {i}")
                   for i, c in enumerate(proveedor.componentes)]
        self.grupos = [
            traducir_grupos(g, nombre)
            for g, nombre in zip(proveedor.grupos_unifac, nombres)
        ]
        self.nombres = nombres

    # ------------------------------------------------------------------
    def coeficientes_actividad(self, T, x):
        """
        gamma_i(T, x) con los parametros de ELL.

        Las composiciones se normalizan y se acotan por abajo: UNIFAC
        evalua logaritmos de fraccion molar, y una fraccion exactamente
        cero -- que aparece constantemente al tantear fases casi puras --
        da -inf en vez de un numero.
        """
        x = np.asarray(x, dtype=float)
        x = np.clip(x, 1e-300, None)
        x = x / float(np.sum(x))
        modelo = UNIFAC.from_subgroups(
            T=float(T), xs=x.tolist(), chemgroups=self.grupos,
            subgroups=_uf.LLEUFSG, interaction_data=_uf.LLEUFIP, version=0,
        )
        return np.asarray(modelo.gammas(), dtype=float)

    def actividades(self, T, x):
        x = np.asarray(x, dtype=float)
        x = x / float(np.sum(x))
        return x * self.coeficientes_actividad(T, x)

    def gibbs_de_mezcla(self, T, x):
        """
        g^mez / RT = sum_i x_i * ln(x_i * gamma_i), adimensional.

        Existe para COMPROBAR el flash por otro camino. El flash resuelve
        igualdad de actividades, que es la condicion de punto
        estacionario; que ese punto sea un MINIMO de Gibbs es una
        propiedad distinta, y es la que de verdad dice que las dos fases
        son estables. Comparar las dos cosas es lo unico que distingue
        "las ecuaciones cuadran" de "la respuesta es fisica".
        """
        x = np.asarray(x, dtype=float)
        x = x / float(np.sum(x))
        a = np.clip(x * self.coeficientes_actividad(T, x), 1e-300, None)
        return float(np.sum(x * np.log(a)))

    # ------------------------------------------------------------------
    def distancia_plano_tangente(self, T, z, w):
        """
        Distancia al plano tangente de Michelsen, entre una composicion de
        prueba `w` y el alimento `z`:

            tpd(w) = sum_i w_i * [ ln(w_i gamma_i(w)) - ln(z_i gamma_i(z)) ]

        Si existe ALGUNA composicion w con tpd(w) < 0, la fase unica de
        composicion z es inestable: separandose baja la energia de Gibbs.
        Es el criterio correcto, y es independiente de la igualdad de
        actividades que resuelve el flash.
        """
        z = np.asarray(z, dtype=float)
        z = z / float(np.sum(z))
        w = np.asarray(w, dtype=float)
        w = np.clip(w, 1e-300, None)
        w = w / float(np.sum(w))
        ln_a_z = np.log(np.clip(z * self.coeficientes_actividad(T, z), 1e-300, None))
        ln_a_w = np.log(np.clip(w * self.coeficientes_actividad(T, w), 1e-300, None))
        return float(np.sum(w * (ln_a_w - ln_a_z)))

    def es_inestable(self, T, z, n_pruebas=9):
        """
        ¿Se separa en dos fases el alimento z a la temperatura T?

        Se buscan composiciones de prueba con distancia al plano tangente
        negativa. Las candidatas NO son al azar: se prueban las fases
        casi puras de cada componente -- que es donde estan los extremos
        de una region de inmiscibilidad -- y, en un binario, una rejilla
        a lo largo de la composicion. Un minimizador general encontraria
        minimos espureos cerca de los vertices del simplex, donde los
        logaritmos divergen.

        Devuelve (inestable, w_minima, tpd_minima). `w_minima` es el mejor
        arranque posible para el flash: no es un arranque cualquiera, es
        la direccion en la que la mezcla de verdad quiere separarse.
        """
        z = np.asarray(z, dtype=float)
        z = z / float(np.sum(z))
        candidatas = []

        # Casi puras: el borde de la region de inmiscibilidad.
        for i in range(self.n):
            w = np.full(self.n, 1e-3 / max(self.n - 1, 1))
            w[i] = 1.0 - 1e-3
            candidatas.append(w)

        # Y una rejilla sobre la direccion dominante. En un binario es la
        # composicion entera; con mas componentes, la recta que une cada
        # par de componentes puros, que es donde aparecen las lagunas.
        for i in range(self.n):
            for j in range(i + 1, self.n):
                for frac in np.linspace(0.05, 0.95, n_pruebas):
                    w = np.full(self.n, 1e-6)
                    w[i] = frac
                    w[j] = 1.0 - frac
                    candidatas.append(w)

        mejor_w, mejor_tpd = None, np.inf
        for w in candidatas:
            try:
                tpd = self.distancia_plano_tangente(T, z, w)
            except Exception:
                continue
            if np.isfinite(tpd) and tpd < mejor_tpd:
                mejor_tpd, mejor_w = tpd, np.asarray(w, dtype=float)

        # El umbral no es cero exacto a proposito: tpd(z) = 0 por
        # construccion, y el ruido numerico alrededor de esa raiz daria
        # "inestable" en mezclas perfectamente miscibles.
        inestable = bool(mejor_tpd < -1e-8)
        return inestable, mejor_w, float(mejor_tpd)

    # ------------------------------------------------------------------
    def flash_LL(self, T, z, max_iteraciones=400, tolerancia=1e-11):
        """
        Reparto en dos fases liquidas a T y composicion global z.

        Se resuelve por sustitucion sucesiva sobre los coeficientes de
        reparto K_i = gamma_i^I / gamma_i^II, con Rachford-Rice dentro
        para el tamano de las fases -- la misma estructura que el flash
        liquido-vapor, que ya esta en core/flash.py:

            x_i^I  = z_i / (1 - beta + beta*K_i)
            x_i^II = K_i * x_i^I
            sum_i z_i (K_i - 1) / (1 + beta (K_i - 1)) = 0

        Lo que NO se parece al flash L-V es el arranque. Aqui la solucion
        trivial x^I = x^II cumple todas las ecuaciones siempre, asi que un
        arranque cualquiera converge a ella con toda probabilidad. Se
        arranca desde la composicion que el analisis de estabilidad
        senala, que es la direccion en la que la mezcla quiere separarse,
        y al terminar se comprueba que las dos fases sigan siendo
        distintas.

        Devuelve None si la mezcla es estable: una sola fase liquida no es
        un fallo, es una respuesta.
        """
        z = np.asarray(z, dtype=float)
        z = z / float(np.sum(z))
        T = float(T)

        inestable, w0, tpd = self.es_inestable(T, z)
        if not inestable:
            return None

        # Arranque: una fase es el alimento, la otra la composicion que la
        # estabilidad senalo. De ahi sale el primer juego de K.
        x_I = z.copy()
        x_II = np.clip(w0, 1e-12, None)
        x_II = x_II / float(np.sum(x_II))

        beta = 0.5
        for iteracion in range(max_iteraciones):
            g_I = self.coeficientes_actividad(T, x_I)
            g_II = self.coeficientes_actividad(T, x_II)
            K = g_I / g_II
            if not np.all(np.isfinite(K)) or np.any(K <= 0):
                raise ValueError(
                    f"Los coeficientes de reparto salieron no fisicos a T={T:.2f} K "
                    f"(K={np.array2string(K, precision=4)}). Revisa la composicion global."
                )

            beta = self._rachford_rice(z, K, beta)
            denominador = 1.0 - beta + beta * K
            nuevo_I = z / denominador
            nuevo_II = K * nuevo_I
            nuevo_I = nuevo_I / float(np.sum(nuevo_I))
            nuevo_II = nuevo_II / float(np.sum(nuevo_II))

            cambio = max(float(np.max(np.abs(nuevo_I - x_I))),
                         float(np.max(np.abs(nuevo_II - x_II))))
            x_I, x_II = nuevo_I, nuevo_II
            if cambio < tolerancia:
                break
        else:
            raise RuntimeError(
                f"El flash liquido-liquido no convergio en {max_iteraciones} iteraciones a "
                f"T={T:.2f} K (ultimo cambio {cambio:.3e}). La sustitucion sucesiva se "
                "vuelve muy lenta cerca de la temperatura critica de la laguna, donde las "
                "dos fases se parecen cada vez mas."
            )

        # La comprobacion que impide devolver la solucion trivial. Dos
        # fases que se parecen tanto son la MISMA, y el "equilibrio" que
        # las separa no significa nada.
        if float(np.max(np.abs(x_I - x_II))) < _TOL_TRIVIAL:
            return None
        if not (0.0 < beta < 1.0):
            return None

        a_I = x_I * self.coeficientes_actividad(T, x_I)
        a_II = x_II * self.coeficientes_actividad(T, x_II)
        residual = float(np.max(np.abs(a_I - a_II) / np.maximum(np.abs(a_I), 1e-300)))

        # Por convencion, la fase I es la mas rica en el componente 0. Sin
        # fijarla, el mismo problema devuelve las dos fases en un orden u
        # otro segun el arranque, y comparar dos resultados se vuelve
        # imposible.
        if x_II[0] > x_I[0]:
            x_I, x_II = x_II, x_I
            beta = 1.0 - beta

        return {
            "x_I": x_I, "x_II": x_II,
            "fraccion_II": float(beta),
            "fraccion_I": float(1.0 - beta),
            "T": T, "z": z,
            "residual_actividades": residual,
            "tpd": tpd,
            "iteraciones": iteracion + 1,
        }

    # ------------------------------------------------------------------
    @staticmethod
    def _rachford_rice(z, K, beta_previo=0.5):
        """
        El tamano de las fases, dada la reparticion K.

        La funcion es monotona en beta, asi que tiene como mucho una raiz
        y `brentq` la encuentra sin ambiguedad. El intervalo se acota a los
        limites de NEGATIVE FLASH clasicos para que ningun denominador
        1 + beta(K-1) se anule dentro: fuera de ellos la funcion tiene
        polos y el root-finding salta de rama.
        """
        z = np.asarray(z, dtype=float)
        K = np.asarray(K, dtype=float)

        def f(beta):
            return float(np.sum(z * (K - 1.0) / (1.0 + beta * (K - 1.0))))

        # Si no cambia de signo en (0,1), el reparto K no admite dos fases
        # con este alimento: se devuelve el extremo mas cercano en vez de
        # reventar, y de eso ya se encarga el lazo de arriba al comprobar
        # que las fases sigan siendo distintas.
        f0, f1 = f(1e-12), f(1.0 - 1e-12)
        if f0 * f1 > 0:
            return 0.0 if abs(f0) < abs(f1) else 1.0
        return float(brentq(f, 1e-12, 1.0 - 1e-12, xtol=1e-14, rtol=1e-15))
