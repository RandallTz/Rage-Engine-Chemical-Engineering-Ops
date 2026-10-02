"""
Reactor de flujo piston (PFR) en estado estacionario.

La diferencia con el CSTR no es de detalle, es de MODELO, y esta en una
sola linea:

    CSTR:  xi = V * r(T, x_salida)          una ecuacion algebraica
    PFR:   d(xi)/dV = r(T, x(xi))           una ecuacion diferencial

En un CSTR el contenido esta perfectamente mezclado, asi que la reaccion
ocurre en todo el tanque a la velocidad de la composicion de SALIDA, que
es la mas pobre en reactivo y por tanto la mas lenta. En un PFR la
composicion cambia a lo largo del tubo: la entrada reacciona a la
velocidad del alimento, que es la mas alta.

Consecuencia practica, y es el resultado de libro que sirve de
validacion: para una cinetica de orden positivo y el mismo volumen, el
PFR convierte MAS que el CSTR. Comparar los dos sobre el mismo diagrama
es justo lo que hace falta para elegir reactor.

Hereda de EvaluadorCSTR porque el balance por componente, la conversion y
el balance de energia son EXACTAMENTE los mismos: lo unico que cambia es
como se relaciona el volumen con el avance. Un PFR es la misma
estequiometria con otra ley de velocidad integrada.

Zona libre de pint: floats/np.ndarray en SI.
"""

import numpy as np
from scipy.integrate import solve_ivp

from core.reactor_cstr import EvaluadorCSTR

_TOL = 1e-12


class EvaluadorPFR(EvaluadorCSTR):
    def _limite_estequiometrico(self, F_in, x_in):
        """Avance al que se agota el primer reactivo."""
        x_in = np.asarray(x_in, dtype=float)
        reactivos = np.where(self.nu < 0)[0]
        if len(reactivos) == 0:
            raise ValueError("No hay ningun reactivo (ningun nu negativo).")
        return min(F_in * x_in[i] / abs(self.nu[i]) for i in reactivos)

    def _derivada(self, F_in, x_in, T):
        """
        d(xi)/dV = r(T, x(xi)).

        Se integra el AVANCE y no los caudales por componente a proposito:
        con una sola variable de estado la estequiometria se cumple por
        construccion en cada paso, mientras que integrando n_i por
        separado los errores del integrador podrian sacar la composicion
        del simplex.
        """
        def f(_V, estado):
            xi = float(estado[0])
            try:
                _, x = self.salida_desde_entrada(F_in, x_in, xi)
            except ValueError:
                return [0.0]   # fuera del simplex: la reaccion se para
            return [float(self.gestor_reaccion.velocidad_reaccion(T, x))]
        return f

    def avance_desde_volumen(self, F_in, x_in, T, V, n_perfil=0):
        """
        Integra el tubo entero y devuelve el avance a la salida.

        El limite estequiometrico se vigila con un EVENTO TERMINAL en vez
        de dejar que el integrador lo cruce: pasado ese punto la
        composicion sale del simplex, las actividades dejan de estar
        definidas y lo que devuelva UNIFAC no significa nada. Es la misma
        precaucion que ya toman las curvas residuales de core/topology.py.
        """
        if self.gestor_reaccion is None:
            raise ValueError("El PFR necesita la cinetica (GestorReaccion) para integrarse.")
        x_in = np.asarray(x_in, dtype=float)
        V = float(V)
        if V < 0:
            raise ValueError(f"El volumen de un reactor no puede ser negativo (se dio {V}).")
        if V == 0:
            return {"xi": 0.0, "V": 0.0, "agotado": False, "perfil": None}

        xi_max = self._limite_estequiometrico(F_in, x_in)

        def agotamiento(_V, estado):
            return float(estado[0]) - xi_max * (1.0 - 1e-9)
        agotamiento.terminal = True
        agotamiento.direction = 1.0

        puntos = np.linspace(0.0, V, n_perfil) if n_perfil and n_perfil > 1 else None
        sol = solve_ivp(
            self._derivada(F_in, x_in, T), (0.0, V), [0.0],
            method="LSODA", events=agotamiento, t_eval=puntos,
            rtol=1e-9, atol=1e-12,
        )
        if not sol.success and sol.status != 1:
            raise RuntimeError(
                f"La integracion del PFR fallo a T={T:.2f} K con V={V:.6g} m3: {sol.message}"
            )

        agotado = sol.status == 1
        xi = float(sol.y[0, -1])
        perfil = None
        if puntos is not None and not agotado:
            perfil = {"V": sol.t.tolist(), "xi": sol.y[0].tolist()}
        return {
            "xi": xi, "V": V, "agotado": agotado, "perfil": perfil,
            "V_agotamiento": float(sol.t[-1]) if agotado else None,
        }

    def volumen_desde_avance(self, xi, T, x_out=None, F_in=None, x_in=None):
        """
        Volumen que hace falta para un avance dado.

        OJO a la firma: es distinta de la del CSTR a proposito. Alli el
        volumen sale de una division, V = xi/r, porque la velocidad es la
        misma en todo el tanque y solo depende de la composicion de
        SALIDA. Aqui la velocidad cambia a lo largo del tubo, asi que
        hace falta el ALIMENTO para saber por donde empieza, y el volumen
        se obtiene integrando hasta alcanzar el avance pedido.

        Se resuelve con un evento terminal sobre xi en vez de con un
        root-finding sobre V: una sola integracion en vez de una por
        iteracion, y el volumen sale exacto en el punto del evento.
        """
        if self.gestor_reaccion is None:
            raise ValueError("El PFR necesita la cinetica (GestorReaccion).")
        if F_in is None or x_in is None:
            raise ValueError(
                "El volumen de un PFR depende del ALIMENTO, no solo de la salida: "
                "la velocidad cambia a lo largo del tubo. Pasa F_in y x_in."
            )
        xi = float(xi)
        if xi <= _TOL:
            return 0.0
        x_in = np.asarray(x_in, dtype=float)
        xi_max = self._limite_estequiometrico(F_in, x_in)
        if xi >= xi_max:
            raise ValueError(
                f"El avance pedido ({xi:.6g} mol/s) alcanza o supera el limite "
                f"estequiometrico ({xi_max:.6g} mol/s): haria falta un tubo infinito."
            )

        def alcanzado(_V, estado):
            return float(estado[0]) - xi
        alcanzado.terminal = True
        alcanzado.direction = 1.0

        # Cota superior generosa: se arranca de la estimacion del CSTR
        # (que siempre necesita MAS volumen que el PFR para el mismo
        # avance, porque trabaja a la velocidad mas lenta) y se ensancha
        # si hiciera falta.
        _, x_out_calc = self.salida_desde_entrada(F_in, x_in, xi)
        r_salida = float(self.gestor_reaccion.velocidad_reaccion(T, x_out_calc))
        if abs(r_salida) < _TOL:
            raise ValueError(
                f"La velocidad a T={T:.4g} K en la composicion de salida es practicamente "
                "cero (equilibrio quimico): ningun tubo finito da ese avance."
            )
        V_tope = 4.0 * xi / r_salida
        for _ in range(12):
            sol = solve_ivp(
                self._derivada(F_in, x_in, T), (0.0, V_tope), [0.0],
                method="LSODA", events=alcanzado, rtol=1e-9, atol=1e-12,
            )
            if sol.status == 1:
                return float(sol.t_events[0][0])
            V_tope *= 4.0
        raise RuntimeError(
            f"No se alcanzo el avance {xi:.6g} mol/s ni con V={V_tope:.6g} m3. "
            "Puede que la reaccion este practicamente parada a esa temperatura."
        )
