"""
Reactor de flujo piston (PFR) en estado estacionario.

La diferencia con el CSTR no es de detalle, es de MODELO, y esta en una
sola linea:

    CSTR:  xi_j = V * r_j(T, x_salida)      R ecuaciones algebraicas
    PFR:   d(xi_j)/dV = r_j(T, x(xi))       R ecuaciones diferenciales

Con varias reacciones se integran los R avances A LA VEZ, acoplados por
la composicion: todas ven la misma x(V), y lo que una consume lo deja de
tener la otra. Esa es la razon de que no se pueda integrar cada reaccion
por separado y sumar.

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

Lo que SI cambia de forma al pasar a varias reacciones es el evento que
detiene la integracion. Con una reaccion basta vigilar un avance maximo;
con varias no existe tal numero, porque el reactivo que se agota primero
depende de cuanto haya avanzado CADA reaccion. El evento pasa a vigilar
la composicion directamente: se para cuando algun componente se queda
sin moles. El camino de una sola reaccion se conserva tal cual, con su
evento de siempre, para que los numeros ya validados no se muevan por un
cambio que no les afecta.

Zona libre de pint: floats/np.ndarray en SI.
"""

import numpy as np
from scipy.integrate import solve_ivp

from core.reactor_cstr import EvaluadorCSTR
from core.errores import ErrorFisico, ErrorNumerico
from core import errores

_TOL = 1e-12


class EvaluadorPFR(EvaluadorCSTR):
    def _limite_estequiometrico(self, F_in, x_in):
        """
        Avance al que se agota el primer reactivo. Solo con UNA reaccion.

        Con varias no existe este numero: cual es el reactivo que se agota
        primero depende de cuanto haya avanzado cada reaccion, asi que el
        limite es una superficie en el espacio de avances y no un escalar.
        Ahi se vigila la composicion con `_moles_restantes`.
        """
        if not self.una_sola:
            raise ValueError(
                f"Con {self.n_reacciones} reacciones no hay un avance maximo unico: "
                "el reactivo que se agota antes depende de cuanto avance cada una. "
                "El limite se vigila sobre la composicion, no sobre el avance."
            )
        x_in = np.asarray(x_in, dtype=float)
        reactivos = np.where(self.nu < 0)[0]
        if len(reactivos) == 0:
            raise ValueError("No hay ningun reactivo (ningun nu negativo).")
        return min(F_in * x_in[i] / abs(self.nu[i]) for i in reactivos)

    def _moles_restantes(self, F_in, x_in, xi):
        """
        Los moles que quedan del componente mas escaso, para el evento
        terminal con varias reacciones. Negativo = ya se paso.
        """
        n = F_in * np.asarray(x_in, dtype=float) + self.NU.T @ np.atleast_1d(xi)
        return float(np.min(n))

    def _derivada(self, F_in, x_in, T):
        """
        d(xi_j)/dV = r_j(T, x(xi)), para cada reaccion.

        Se integra el AVANCE y no los caudales por componente a proposito:
        con los avances como variables de estado la estequiometria se
        cumple por construccion en cada paso, mientras que integrando n_i
        por separado los errores del integrador podrian sacar la
        composicion del simplex. Con varias reacciones el argumento es
        aun mas fuerte: hay R avances frente a n_componentes caudales, y R
        suele ser mucho menor.

        gamma se calcula UNA vez por paso y lo comparten todas las
        reacciones (lo hace GestorReaccion.velocidades), que es lo que
        evita multiplicar por R el coste de cada paso del integrador.
        """
        ceros = np.zeros(self.n_reacciones)

        def f(_V, estado):
            xi = np.asarray(estado, dtype=float)
            try:
                _, x = self.salida_desde_entrada(F_in, x_in, xi)
            except ValueError:
                return ceros   # fuera del simplex: la reaccion se para
            return self.gestor_reaccion.velocidades(T, x)
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
            return {"xi": self._escalar_si_una(np.zeros(self.n_reacciones)),
                    "V": 0.0, "agotado": False, "perfil": None}

        if self.una_sola:
            # El evento de siempre, sobre el avance: se conserva tal cual
            # para que los numeros ya validados no se muevan.
            xi_max = self._limite_estequiometrico(F_in, x_in)

            def agotamiento(_V, estado):
                return float(estado[0]) - xi_max * (1.0 - 1e-9)
            agotamiento.direction = 1.0
        else:
            # Con varias reacciones se vigila la COMPOSICION: el evento
            # salta cuando al componente mas escaso le queda una fraccion
            # despreciable del alimento. No hay un avance maximo que
            # vigilar porque cual sea el reactivo critico depende de cuanto
            # haya avanzado cada reaccion.
            umbral = 1e-9 * F_in

            def agotamiento(_V, estado):
                return self._moles_restantes(F_in, x_in, estado) - umbral
            agotamiento.direction = -1.0
        agotamiento.terminal = True

        puntos = np.linspace(0.0, V, n_perfil) if n_perfil and n_perfil > 1 else None
        sol = solve_ivp(
            self._derivada(F_in, x_in, T), (0.0, V),
            np.zeros(self.n_reacciones),
            method="LSODA", events=agotamiento, t_eval=puntos,
            rtol=1e-9, atol=1e-12,
        )
        if not sol.success and sol.status != 1:
            raise ErrorNumerico(
                f"La integracion del PFR fallo a T={T:.2f} K con V={V:.6g} m3: {sol.message}",
                codigo=errores.INTEGRACION_FALLIDA,
            )

        agotado = sol.status == 1
        xi = np.asarray(sol.y[:, -1], dtype=float)
        perfil = None
        if puntos is not None and not agotado:
            perfil = {"V": sol.t.tolist(),
                      "xi": (sol.y[0].tolist() if self.una_sola else sol.y.tolist())}
        return {
            "xi": self._escalar_si_una(xi), "V": V, "agotado": agotado, "perfil": perfil,
            "V_agotamiento": float(sol.t[-1]) if agotado else None,
        }

    def volumen_desde_avance(self, xi, T, x_out=None, F_in=None, x_in=None,
                             indice=None, tolerancia=1e-6):
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
        v = self._vector_xi(xi)
        x_in = np.asarray(x_in, dtype=float)

        # Con varias reacciones, como en el CSTR, un solo volumen no puede
        # dar un juego cualquiera de avances: el tubo entrega los R a la
        # vez. Se integra hasta que la reaccion elegida alcanza SU avance y
        # se comprueba que las demas cuadren.
        if self.una_sola:
            indice = 0
        elif indice is None:
            raise ValueError(
                f"Con {self.n_reacciones} reacciones hay que decir cual fija el volumen "
                "('indice'): el tubo entrega los avances de todas a la vez, asi que no "
                "cualquier juego de avances es alcanzable."
            )
        indice = int(indice)
        objetivo = float(v[indice])
        if objetivo <= _TOL:
            return 0.0

        if self.una_sola:
            xi_max = self._limite_estequiometrico(F_in, x_in)
            if objetivo >= xi_max:
                raise ErrorFisico(
                    f"El avance pedido ({objetivo:.6g} mol/s) alcanza o supera el limite "
                    f"estequiometrico ({xi_max:.6g} mol/s): haria falta un tubo infinito.",
                    codigo=errores.LIMITE_ESTEQUIOMETRICO,
                )

        def alcanzado(_V, estado):
            return float(np.atleast_1d(estado)[indice]) - objetivo
        alcanzado.terminal = True
        alcanzado.direction = 1.0

        # Cota superior generosa: se arranca de la estimacion del CSTR
        # (que siempre necesita MAS volumen que el PFR para el mismo
        # avance, porque trabaja a la velocidad mas lenta) y se ensancha
        # si hiciera falta.
        _, x_out_calc = self.salida_desde_entrada(F_in, x_in, v)
        r_salida = self.gestor_reaccion.velocidades(T, x_out_calc)
        if abs(float(r_salida[indice])) < _TOL:
            raise ValueError(
                f"La velocidad de la reaccion {indice} a T={T:.4g} K en la composicion de "
                "salida es practicamente cero (equilibrio quimico): ningun tubo finito da "
                "ese avance."
            )
        V_tope = 4.0 * objetivo / float(r_salida[indice])
        for _ in range(12):
            sol = solve_ivp(
                self._derivada(F_in, x_in, T), (0.0, V_tope),
                np.zeros(self.n_reacciones),
                method="LSODA", events=alcanzado, rtol=1e-9, atol=1e-12,
            )
            if sol.status == 1:
                V = float(sol.t_events[0][0])
                if self.una_sola:
                    return V
                # Los avances que SI entrega ese tubo, frente a los pedidos.
                alcanzados = np.asarray(sol.y_events[0][0], dtype=float)
                escala = max(float(np.max(np.abs(v))), _TOL)
                desviacion = np.abs(alcanzados - v) / escala
                peor = int(np.argmax(desviacion))
                if desviacion[peor] > tolerancia:
                    raise ValueError(
                        f"Con V={V:.6g} m3 (el que la reaccion {indice} necesita) la "
                        f"reaccion {peor} llega a {alcanzados[peor]:.6g} mol/s y se pidio "
                        f"{v[peor]:.6g} mol/s ({100*desviacion[peor]:.2f} % de diferencia). "
                        "Ese juego de avances no es alcanzable en un solo tubo a esa "
                        "temperatura: la relacion entre avances la fija la cinetica, no se "
                        "puede elegir."
                    )
                return V
            V_tope *= 4.0
        raise RuntimeError(
            f"No se alcanzo el avance {objetivo:.6g} mol/s de la reaccion {indice} ni con "
            f"V={V_tope:.6g} m3. Puede que la reaccion este practicamente parada a esa "
            "temperatura."
        )
