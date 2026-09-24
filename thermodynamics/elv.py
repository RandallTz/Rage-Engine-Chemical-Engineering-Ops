import numpy as np
from scipy.optimize import root_scalar

# Rango de busqueda del punto de burbuja. El original era [273.15, 600] K
# y eso dejaba FUERA a cualquier mezcla que hierva bajo 0 degC -- p.ej.
# el isobuteno (Tb = 266 K), con el que los mapas de curvas residuales de
# MTBE fallaban en las esquinas ricas en ese componente. El fallo no se
# veia como "esta mezcla hierve fuera del rango" sino como el
# "f(a) and f(b) must have different signs" crudo de scipy.
_T_MIN = 120.0
_T_MAX = 800.0


class CalculadoraELV:
    def __init__(self, proveedor):
        """
        Recibe una instancia de ProveedorTermodinamico.
        """
        self.proveedor = proveedor

    def burbuja_P(self, T_kelvin, x_mezcla):
        """
        Calcula la presión de burbuja y la composición del vapor a T constante.
        """
        p_sat = self.proveedor.presiones_saturacion(T_kelvin)
        gamma = self.proveedor.coeficientes_actividad(T_kelvin, x_mezcla)

        p_parciales = x_mezcla * gamma * p_sat
        P_burbuja = np.sum(p_parciales)
        y_vapor = p_parciales / P_burbuja

        return P_burbuja, y_vapor

    def rocio_P(self, T_kelvin, y_mezcla, tolerancia=1e-10, max_iteraciones=100):
        """
        Presion de ROCIO a T constante, y la composicion del liquido que
        aparece en la primera gota.

        Es la pareja de burbuja_P, pero NO es simetrica en dificultad. La
        de burbuja es explicita (P = sum x_i gamma_i(T,x) Psat_i: x se
        conoce). La de rocio es implicita:

            1/P = sum_i y_i / (gamma_i(T,x) * Psat_i(T))

        porque gamma depende de la composicion del LIQUIDO, que es justo
        la incognita. Se resuelve por punto fijo arrancando del caso
        ideal (gamma = 1). Converge rapido porque gamma cambia poco entre
        iteraciones comparado con lo que cambia x.

        Hacia falta para el flash: sin rocio no se puede distinguir una
        corriente bifasica de un vapor sobrecalentado.
        """
        y = np.asarray(y_mezcla, dtype=float)
        p_sat = self.proveedor.presiones_saturacion(T_kelvin)

        # Arranque ideal: x_i proporcional a y_i/Psat_i (ley de Raoult).
        x = y / p_sat
        x = x / np.sum(x)
        P = np.nan
        for _ in range(max_iteraciones):
            gamma = self.proveedor.coeficientes_actividad(T_kelvin, x)
            P_nueva = 1.0 / np.sum(y / (gamma * p_sat))
            # Por construccion esta x ya suma 1; se normaliza igual para
            # que el redondeo no vaya acumulando.
            x_nueva = y * P_nueva / (gamma * p_sat)
            x_nueva = x_nueva / np.sum(x_nueva)
            convergio = (abs(P_nueva - P) <= tolerancia * max(1.0, abs(P_nueva))
                         and np.max(np.abs(x_nueva - x)) <= 1e-12)
            P, x = P_nueva, x_nueva
            if convergio:
                return float(P), x
        raise RuntimeError(
            f"La presion de rocio no convergio en {max_iteraciones} iteraciones a "
            f"T={T_kelvin:.2f} K (ultima P={P:.6g} Pa). El punto fijo sobre gamma se "
            "atasca en mezclas muy no ideales cerca de una separacion de fases liquidas, "
            "que UNIFAC en una sola fase no describe."
        )

    def rocio_T(self, P_pascal, y_mezcla, tolerancia=1e-8):
        """
        Temperatura de rocio a P constante. Misma estrategia de bracket
        ensanchable que burbuja_T: P_rocio crece con T, asi que el signo
        del residuo dice hacia donde esta la raiz.
        """
        def residuo(T):
            P_r, _ = self.rocio_P(T, y_mezcla)
            return P_r - P_pascal

        a, b = 273.15, 600.0
        r_a = r_b = None
        for _ in range(8):
            try:
                r_a, r_b = residuo(a), residuo(b)
            except Exception:
                a, b = a + 0.15 * (b - a), b - 0.15 * (b - a)
                continue
            if np.sign(r_a) != np.sign(r_b):
                break
            if r_a > 0:
                a = max(_T_MIN, a - 0.6 * (b - a))
            else:
                b = min(_T_MAX, b + 0.6 * (b - a))
            if a <= _T_MIN and b >= _T_MAX:
                break
        else:
            r_a = r_b = None

        if r_a is None or r_b is None or np.sign(r_a) == np.sign(r_b):
            raise ValueError(
                f"No se encontro temperatura de rocio a {P_pascal:.4g} Pa buscando entre "
                f"{a:.1f} y {b:.1f} K. Igual que en burbuja_T, suele pasar cerca de un "
                "vertice puro que condensa fuera de ese rango o con una presion poco realista."
            )

        sol = root_scalar(residuo, bracket=[a, b], method='brentq', xtol=tolerancia)
        T_rocio = sol.root
        _, x_liquido = self.rocio_P(T_rocio, y_mezcla)
        return T_rocio, x_liquido

    def burbuja_T(self, P_pascal, x_mezcla, T_guess=350.0):
        """
        Temperatura de burbuja y composicion del vapor a P constante.

        El bracket NO es fijo: se parte de un rango usual y se ensancha
        hasta encontrar cambio de signo. Un bracket fijo obliga a conocer
        de antemano por donde hierve la mezcla, que es justo lo que se
        esta calculando -- y cuando no acertaba, el error que llegaba al
        usuario era el de scipy, que no dice nada. Si de verdad no existe
        solucion en un rango fisicamente razonable, se explica POR QUE.
        """
        def residuo_P(T):
            p_sat = self.proveedor.presiones_saturacion(T)
            gamma = self.proveedor.coeficientes_actividad(T, x_mezcla)
            return np.sum(x_mezcla * gamma * p_sat) - P_pascal

        a, b = 273.15, 600.0
        r_a = r_b = None
        for _ in range(8):
            try:
                r_a, r_b = residuo_P(a), residuo_P(b)
            except Exception:
                # Alguna correlacion de 'thermo' se sale de su rango de
                # validez en un extremo: se encoge ese extremo y se sigue.
                a, b = a + 0.15 * (b - a), b - 0.15 * (b - a)
                continue
            if np.sign(r_a) != np.sign(r_b):
                break
            # El residuo crece con T (mas presion de vapor), asi que el
            # signo dice hacia que lado esta la raiz: si en ambos extremos
            # es negativo, la mezcla hierve MAS ARRIBA; si positivo, mas abajo.
            if r_a > 0:
                a = max(_T_MIN, a - 0.6 * (b - a))
            else:
                b = min(_T_MAX, b + 0.6 * (b - a))
            if a <= _T_MIN and b >= _T_MAX:
                break
        else:
            r_a = r_b = None

        if r_a is None or r_b is None or np.sign(r_a) == np.sign(r_b):
            raise ValueError(self._explicar_fallo(P_pascal, x_mezcla, a, b, r_a, r_b))

        sol = root_scalar(residuo_P, bracket=[a, b], method='brentq')
        T_burbuja = sol.root
        _, y_vapor = self.burbuja_P(T_burbuja, x_mezcla)
        return T_burbuja, y_vapor

    def _explicar_fallo(self, P_pascal, x_mezcla, a, b, r_a, r_b):
        """Un motivo fisico en vez del mensaje interno de scipy."""
        nombres = [getattr(c, "name", f"componente {i}")
                   for i, c in enumerate(self.proveedor.componentes)]
        dominante = int(np.argmax(np.asarray(x_mezcla, dtype=float)))
        detalle = ""
        if r_a is not None and r_b is not None:
            if r_a > 0 and r_b > 0:
                detalle = (
                    f" La mezcla ya esta por encima de su punto de burbuja incluso a {a:.1f} K: "
                    "hierve por debajo del rango explorado."
                )
            elif r_a < 0 and r_b < 0:
                detalle = (
                    f" La mezcla todavia no hierve ni a {b:.1f} K: su punto de burbuja queda "
                    "por encima del rango explorado."
                )
        return (
            f"No se encontro temperatura de burbuja a {P_pascal:.4g} Pa para una mezcla "
            f"dominada por {nombres[dominante]} (x={float(np.max(x_mezcla)):.4g}), "
            f"buscando entre {a:.1f} y {b:.1f} K.{detalle} "
            "Suele pasar cerca de un vertice puro cuyo punto de ebullicion cae fuera de "
            "ese rango, o con una presion de operacion poco realista para esta mezcla."
        )
