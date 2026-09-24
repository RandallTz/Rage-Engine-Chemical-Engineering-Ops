"""
Flash liquido-vapor: el separador en equilibrio de UNA etapa.

Por que este modulo es la pieza bisagra del proyecto: un flash es,
literalmente, el sistema MESH completo con N=1.

    M :  F z_i = V y_i + L x_i
    E :  y_i = K_i(T, P, x) x_i
    S :  sum_i x_i = sum_i y_i = 1
    H :  F h_F + Q = V h_V(T, y) + L h_L(T, x)

O sea que resolverlo bien obliga a fijar ahora todo lo que la columna
rigurosa va a necesitar despues (como se representa K, como se mide la
entalpia de una corriente, que forma tiene el residuo), pero en un caso
de una sola etapa donde cada numero se puede comprobar a mano.

Las cuatro ecuaciones se reducen a una sola incognita escalar con el
truco clasico de Rachford-Rice. Partiendo de M y E:

    x_i = z_i / (1 + beta (K_i - 1)) ,  y_i = K_i x_i ,  beta = V/F

y la condicion S en su forma restada (sum y_i - sum x_i = 0), que es la
que se porta bien numericamente:

    f(beta) = sum_i  z_i (K_i - 1) / (1 + beta (K_i - 1))  =  0

f es monotona DECRECIENTE en beta dentro de [0,1], asi que tiene a lo
sumo una raiz y brentq la encuentra sin ambiguedad. La forma restada se
usa en vez de "sum x_i = 1" porque esta ultima es casi plana en beta
cuando la separacion es facil, y el root-finding se vuelve mal
condicionado justo en el caso comodo.

K_i = gamma_i(T, x) Psat_i(T) / P -- Raoult modificada, la misma que usa
todo el proyecto. Como gamma depende de x, K depende de la solucion: hay
un lazo externo de sustituciones sucesivas sobre x alrededor del
Rachford-Rice.

Tres especificaciones, el mismo espiritu orientado a ecuaciones que
McCabe-Thiele y Ponchon-Savarit (que variable se da y cual se despeja):

    isotermico(T, P)        -> beta   (el caso base)
    a_entalpia(P, h) / con_calor(P, Q) -> T, beta   (anade la ecuacion H)
    a_fraccion(P, beta)     -> T      (spec de diseno: "quiero vaporizar el 40 %")

Zona libre de pint: floats/np.ndarray en SI.
"""

import numpy as np
from scipy.optimize import brentq

from thermodynamics.entalpia import entalpia_de

_MAX_SUSTITUCIONES = 200


class EvaluadorFlash:
    def __init__(self, calculadora_elv, P_sistema=101325.0):
        self.calculadora_elv = calculadora_elv
        self.proveedor = calculadora_elv.proveedor
        self.entalpia = entalpia_de(self.proveedor)
        self.P_sistema = float(P_sistema)
        self.n = len(self.proveedor.componentes)

    # ------------------------------------------------------------------
    def constantes_equilibrio(self, T, P, x):
        """K_i = gamma_i(T,x) Psat_i(T) / P."""
        gamma = self.proveedor.coeficientes_actividad(T, x)
        p_sat = self.proveedor.presiones_saturacion(T)
        return gamma * p_sat / P

    @staticmethod
    def _rachford_rice(z, K):
        """
        Raiz de f(beta) en [0,1]. Devuelve tambien f(0) y f(1), que son
        el diagnostico de fase: f(0) <= 0 significa que ni la primera
        burbuja se forma (liquido subenfriado) y f(1) >= 0 que ni la
        primera gota condensa (vapor sobrecalentado).
        """
        def f(beta):
            return float(np.sum(z * (K - 1.0) / (1.0 + beta * (K - 1.0))))

        f0, f1 = f(0.0), f(1.0)
        if f0 <= 0.0:
            return 0.0, f0, f1
        if f1 >= 0.0:
            return 1.0, f0, f1
        return float(brentq(f, 0.0, 1.0, xtol=1e-14, rtol=1e-15)), f0, f1

    def _bifasico(self, T, P, z, tolerancia=1e-10, x_inicial=None):
        """
        Lazo de sustituciones sucesivas sobre x. Se entra aqui ya sabiendo
        que el punto es bifasico (lo decide isotermico con burbuja/rocio),
        asi que este metodo no repite esa comprobacion -- importa porque
        el flash adiabatico lo llama decenas de veces y el punto de rocio
        es la parte cara.
        """
        z = np.asarray(z, dtype=float)
        x = np.asarray(x_inicial, dtype=float).copy() if x_inicial is not None else z.copy()
        beta = 0.5
        for iteracion in range(1, _MAX_SUSTITUCIONES + 1):
            K = self.constantes_equilibrio(T, P, x)
            beta, _, _ = self._rachford_rice(z, K)
            # Con beta en la raiz, sum(x) = 1 y sum(y) = 1 salen EXACTAS
            # (se deducen de f(beta)=0 mas sum(z)=1); se normaliza solo
            # para que el redondeo no vaya acumulando a lo largo del lazo.
            x_nueva = z / (1.0 + beta * (K - 1.0))
            x_nueva = x_nueva / np.sum(x_nueva)
            desviacion = float(np.max(np.abs(x_nueva - x)))
            x = x_nueva
            if desviacion <= tolerancia:
                y = K * x
                return x, y / np.sum(y), beta, K, iteracion

        raise RuntimeError(
            f"El flash bifasico no convergio en {_MAX_SUSTITUCIONES} sustituciones a "
            f"T={T:.2f} K, P={P:.4g} Pa (ultimo cambio en x: {desviacion:.2e}). Las "
            "sustituciones sucesivas sobre gamma se atascan en mezclas muy no ideales; "
            "en ese caso hace falta un metodo de Newton sobre (x, beta), no implementado."
        )

    # ------------------------------------------------------------------
    def isotermico(self, T, P=None, z=None, tolerancia=1e-10):
        """
        Flash a T y P dadas. Devuelve composiciones, beta = V/F y la
        entalpia de cada fase.

        El diagnostico de fase NO se deja al Rachford-Rice: se hace antes,
        con el punto de burbuja y el de rocio, que son calculos exactos y
        ya validados. La razon es que f(0) y f(1) necesitan K evaluada en
        la composicion correcta de cada fase, y esa composicion es justo
        lo que todavia no se conoce -- usar z en ambos casos da un
        diagnostico sesgado cerca de las fronteras. Con burbuja/rocio la
        frontera queda donde de verdad esta:

            P >= P_burbuja(T, z)  ->  todo liquido
            P <= P_rocio(T, z)    ->  todo vapor
        """
        P = self.P_sistema if P is None else float(P)
        z = np.asarray(z, dtype=float)
        if abs(np.sum(z) - 1.0) > 1e-8:
            raise ValueError(f"La composicion de alimentacion debe sumar 1.0 (suma {np.sum(z):.6g}).")

        P_burbuja, y_burbuja = self.calculadora_elv.burbuja_P(T, z)
        if P >= P_burbuja:
            return self._resultado(T, P, z, z, y_burbuja, 0.0, None, "liquido",
                                   P_burbuja, None, 0)

        P_rocio, x_rocio = self.calculadora_elv.rocio_P(T, z)
        if P <= P_rocio:
            return self._resultado(T, P, z, x_rocio, z, 1.0, None, "vapor",
                                   P_burbuja, P_rocio, 0)

        x, y, beta, K, iteraciones = self._bifasico(T, P, z, tolerancia)
        return self._resultado(T, P, z, x, y, beta, K, "bifasico",
                               P_burbuja, P_rocio, iteraciones)

    def _resultado(self, T, P, z, x, y, beta, K, fase, P_burbuja, P_rocio, iteraciones):
        h_L = self.entalpia.h_liquido(T, x)
        h_V = self.entalpia.h_vapor(T, y)
        return {
            "T": float(T), "P": float(P), "z": np.asarray(z, dtype=float),
            "x": np.asarray(x, dtype=float), "y": np.asarray(y, dtype=float),
            "beta": float(beta), "fase": fase, "K": K,
            "h_L": h_L, "h_V": h_V,
            # Entalpia MOLAR de la corriente entera (la que entra en el
            # balance de energia del equipo siguiente).
            "h": (1.0 - beta) * h_L + beta * h_V,
            "P_burbuja": P_burbuja, "P_rocio": P_rocio,
            "iteraciones": iteraciones,
        }

    def entalpia_de_corriente(self, T, P, z, tolerancia=1e-10):
        """
        Entalpia molar de una corriente en (T, P, z), SIN que haya que
        declarar en que fase viene.

        Esto cierra un agujero real del flowsheet. Hasta ahora cada
        balance de energia suponia liquido (h_liquido) porque no habia
        forma de saber otra cosa: la fase no es un dato que lleven las
        corrientes, es una CONSECUENCIA de (T, P, z). Un flash isotermico
        la deduce, y de paso da la entalpia correcta en los tres casos.

        Barato en el caso comun: si la corriente es liquido subenfriado,
        isotermico() se corta en la comprobacion de burbuja, o sea una
        sola llamada a UNIFAC. Solo las corrientes de verdad bifasicas
        pagan el lazo completo.
        """
        return self.isotermico(T, P, z, tolerancia)["h"]

    # ------------------------------------------------------------------
    def a_entalpia(self, P, z, h_objetivo, tolerancia=1e-10):
        """
        Flash P-H: dada la presion y la entalpia molar de la corriente,
        encuentra T (y con ella beta). Es el flash que resuelve una
        valvula (isentalpico) o un tanque adiabatico.

        La T no se busca a ciegas en todo el rango: primero se ubican las
        dos fronteras de fase a esa P, que ademas son baratas comparadas
        con un barrido de flashes completos.

            h <= h_L(T_burbuja)  ->  liquido subenfriado, T de h_L directo
            h >= h_V(T_rocio)    ->  vapor sobrecalentado, T de h_V directo
            en medio              ->  bifasico, T entre T_burbuja y T_rocio

        Ademas de ser mas rapido, esto da la clasificacion de fase como
        SUBPRODUCTO del propio balance de energia, no como una
        comprobacion aparte que podria contradecirlo.
        """
        P = float(P)
        z = np.asarray(z, dtype=float)
        h_objetivo = float(h_objetivo)

        T_burbuja, _ = self.calculadora_elv.burbuja_T(P, z)
        h_liquido_saturado = self.entalpia.h_liquido(T_burbuja, z)
        if h_objetivo <= h_liquido_saturado:
            T = self.entalpia.T_desde_h_liquido(h_objetivo, z)
            return self.isotermico(T, P, z, tolerancia)

        T_rocio, _ = self.calculadora_elv.rocio_T(P, z)
        h_vapor_saturado = self.entalpia.h_vapor(T_rocio, z)
        if h_objetivo >= h_vapor_saturado:
            T = self.entalpia.T_desde_h_vapor(h_objetivo, z, T_min=T_rocio)
            return self.isotermico(T, P, z, tolerancia)

        # Zona bifasica. h crece con T aqui tambien (se vaporiza mas), y
        # los dos extremos ya estan acotados por construccion.
        def residuo(T):
            x, y, beta, _, _ = self._bifasico(T, P, z, tolerancia)
            h = (1.0 - beta) * self.entalpia.h_liquido(T, x) + beta * self.entalpia.h_vapor(T, y)
            return h - h_objetivo

        T = float(brentq(residuo, T_burbuja, T_rocio, xtol=1e-9))
        return self.isotermico(T, P, z, tolerancia)

    def con_calor(self, P, z, T_entrada, Q_por_mol=0.0, tolerancia=1e-10,
                  P_entrada=None):
        """
        Flash adiabatico (Q=0) o con aporte/retirada de calor.

        Q_por_mol es Q/F [J/mol de alimentacion], no Q absoluto: igual que
        Ponchon-Savarit pide Qc/D en vez de Qc, porque el estado de salida
        solo depende del calor ESPECIFICO. El Q absoluto se recupera
        multiplicando por F, y eso lo hace quien conoce F (el flowsheet).

        P_entrada: presion de la corriente que ENTRA, que puede no ser la
        del recipiente (es justo el caso de una valvula). Si se da, la
        entalpia de entrada se mide con su fase real; si no, se supone
        que entra a la misma P del flash.
        """
        z = np.asarray(z, dtype=float)
        h_entrada = self.entalpia_de_corriente(
            T_entrada, P if P_entrada is None else P_entrada, z, tolerancia
        )
        resultado = self.a_entalpia(P, z, h_entrada + float(Q_por_mol), tolerancia)
        resultado["h_entrada"] = h_entrada
        resultado["Q_por_mol"] = float(Q_por_mol)
        return resultado

    # ------------------------------------------------------------------
    def a_fraccion(self, P, z, beta_objetivo, tolerancia=1e-10):
        """
        Spec de diseno: "quiero vaporizar esta fraccion, a que T tengo que
        operar y cuanto calor cuesta". La incognita es T y la ecuacion
        extra es beta = beta_objetivo.

        beta crece monotonamente con T a P fija (mas temperatura, mas
        vapor), y beta=0 en la burbuja y beta=1 en el rocio, asi que
        [T_burbuja, T_rocio] es un bracket valido por construccion.
        """
        P = float(P)
        z = np.asarray(z, dtype=float)
        beta_objetivo = float(beta_objetivo)
        if not (0.0 < beta_objetivo < 1.0):
            raise ValueError(
                f"beta_objetivo debe estar estrictamente entre 0 y 1 (se dio {beta_objetivo}). "
                "beta=0 es el punto de burbuja y beta=1 el de rocio: para esos usa "
                "CalculadoraELV.burbuja_T / rocio_T, que los dan directamente."
            )

        T_burbuja, _ = self.calculadora_elv.burbuja_T(P, z)
        T_rocio, _ = self.calculadora_elv.rocio_T(P, z)

        def residuo(T):
            _, _, beta, _, _ = self._bifasico(T, P, z, tolerancia)
            return beta - beta_objetivo

        T = float(brentq(residuo, T_burbuja, T_rocio, xtol=1e-9))
        resultado = self.isotermico(T, P, z, tolerancia)
        resultado["T_burbuja"] = T_burbuja
        resultado["T_rocio"] = T_rocio
        return resultado
