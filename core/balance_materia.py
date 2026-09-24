"""
Balance de materia global de una columna de destilacion binaria (no es
especifico de McCabe-Thiele -- lo va a necesitar cualquier metodo:
Ponchon-Savarit, FUG, MESH).

    F = D + B
    F*z_F = D*x_D + B*x_B

Son 2 ecuaciones sobre 6 variables (F, D, B, z_F, x_D, x_B): dadas
exactamente 4, se resuelven las otras 2. Se resuelve con
scipy.optimize.root en vez de derivar a mano las ~15 combinaciones
posibles de incognitas -- varias de esas combinaciones son bilineales
(producto de dos incognitas, p.ej. D y x_D ambas desconocidas), asi que
un solver generico de 2x2 es mas simple y menos propenso a errores que
una formula cerrada por caso.
"""

import numpy as np
from scipy.optimize import root, least_squares

_VARIABLES = ("F", "D", "B", "z_F", "x_D", "x_B")
_TOLERANCIA_RESIDUAL = 1e-9


class BalanceMateriaGlobal:
    def resolver(self, F=None, D=None, B=None, z_F=None, x_D=None, x_B=None, guess=None):
        """
        Acepta 0, 1 o 2 incognitas:
          2 -> sistema exactamente determinado (caso original).
          1 -> SOBRE-determinado (2 ecuaciones, 1 incognita): se resuelve
               por minimos cuadrados y se exige que AMBOS residuos queden
               en cero. Si no quedan, los datos dados son mutuamente
               inconsistentes, y eso es informacion util, no un fallo.
          0 -> solo verificacion de consistencia.
        Admitir 1 incognita es lo que permite que un flowsheet resuelva
        "hacia atras" (dados los productos, hallar la alimentacion) sin
        tener que dar exactamente 4 datos.
        """
        valores = {"F": F, "D": D, "B": B, "z_F": z_F, "x_D": x_D, "x_B": x_B}
        incognitas = [nombre for nombre, v in valores.items() if v is None]

        if len(incognitas) > 2:
            raise ValueError(
                "El balance de materia global es un sistema de 2 ecuaciones "
                f"(F=D+B; F*z_F=D*x_D+B*x_B) sobre {_VARIABLES}: admite hasta 2 "
                f"incognitas, se dieron {len(incognitas)} ({incognitas})."
            )

        def residuo(vec):
            candidatos = dict(valores)
            for nombre, valor in zip(incognitas, np.atleast_1d(vec)):
                candidatos[nombre] = valor
            F_, D_, B_ = candidatos["F"], candidatos["D"], candidatos["B"]
            zF_, xD_, xB_ = candidatos["z_F"], candidatos["x_D"], candidatos["x_B"]
            return [F_ - D_ - B_, F_ * zF_ - D_ * xD_ - B_ * xB_]

        resultado = dict(valores)

        if len(incognitas) == 0:
            residual_max = float(np.max(np.abs(residuo([]))))
            resultado["convergio"] = residual_max < _TOLERANCIA_RESIDUAL
            resultado["residual_max"] = residual_max
            resultado["incognitas"] = ()
            return resultado

        if guess is None:
            guess = self._guess_por_defecto(incognitas, valores)

        if len(incognitas) == 2:
            # Camino original, ya validado -- no se toca.
            sol = root(residuo, guess, method="hybr")
            solucion = np.atleast_1d(sol.x)
            residual_max = float(np.max(np.abs(sol.fun)))
        else:
            sol = least_squares(residuo, guess)
            solucion = np.atleast_1d(sol.x)
            residual_max = float(np.max(np.abs(residuo(solucion))))

        for nombre, valor in zip(incognitas, solucion):
            resultado[nombre] = float(valor)

        # Con 1 incognita el sistema esta SOBRE-determinado (2 ecuaciones,
        # 1 grado de libertad): minimos cuadrados siempre devuelve algo,
        # pero si el residuo no es cero ese "algo" no cumple ninguna de
        # las dos ecuaciones -- es un compromiso, no una solucion.
        # Devolverlo en silencio era un bug real: con D y B dados en
        # cantidades incompatibles con las composiciones, el simulador
        # mostraba una alimentacion inventada y reportaba 0 problemas.
        if len(incognitas) <= 1:
            escala = max(
                abs(resultado[v]) for v in ("F", "D", "B") if resultado[v] is not None
            ) or 1.0
            if residual_max > 1e-7 * escala:
                F_, D_, B_ = resultado["F"], resultado["D"], resultado["B"]
                zF_, xD_, xB_ = resultado["z_F"], resultado["x_D"], resultado["x_B"]
                raise ValueError(
                    "El balance de materia no se puede cumplir con estos datos. "
                    f"F = D + B pide F = {D_ + B_:.6g}, pero F*z_F = D*x_D + B*x_B pide "
                    f"F = {(D_ * xD_ + B_ * xB_) / zF_:.6g} (con z_F={zF_:.6g}, x_D={xD_:.6g}, "
                    f"x_B={xB_:.6g}). Sobra un dato: borra uno de los caudales o revisa las "
                    "composiciones."
                )
        # Ojo: NO se exige sol.success ademas del residual. Se verifico que
        # MINPACK/hybr puede reportar success=False ("not making good
        # progress") con el sistema ya resuelto exactamente (residual~0),
        # porque este balance es lineal/casi-lineal y converge en pocos
        # pasos -- su heuristica de progreso no esta pensada para eso. El
        # residual es la senal confiable aqui.
        resultado["convergio"] = residual_max < _TOLERANCIA_RESIDUAL
        resultado["residual_max"] = residual_max
        resultado["incognitas"] = tuple(incognitas)
        return resultado

    @staticmethod
    def _guess_por_defecto(incognitas, valores):
        F_ref = valores.get("F") or valores.get("D") or valores.get("B") or 100.0
        guess = []
        for var in incognitas:
            guess.append(F_ref * 0.5 if var in ("F", "D", "B") else 0.5)
        return guess
