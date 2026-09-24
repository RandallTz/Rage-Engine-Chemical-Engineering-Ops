"""
Variables transformadas de Barbosa & Doherty para el analisis topologico
de sistemas reactivos. Reduce en 1 la dimensionalidad del espacio de
composicion eliminando el grado de libertad que introduce la reaccion.

Nota de correccion respecto a la formula dictada: el denominador debe
ser (1 - (nu_tot/nu_k)*x_k), no (1 - nu_tot*x_k). Con la version sin
dividir por nu_k, la suma de los X_i (excluyendo el de referencia k) NO
da 1 salvo que nu_k sea exactamente +1 -- se puede verificar
algebraicamente: sum_i x_i - (x_k/nu_k)*sum_i nu_i = 1 - (nu_tot/nu_k)*x_k,
que es identico al denominador solo en la version corregida, y por eso
la suma se cancela a 1 exactamente para cualquier x, nu, k. La version
literal solo coincide con esta cuando nu_k = 1.

Zona libre de pint: solo floats/np.ndarray en SI.
"""

import numpy as np

_TOLERANCIA_SINGULARIDAD = 1e-12


class EspacioReactivo:
    def __init__(self, nu, k):
        """
        nu : vector estequiometrico (negativo=reactivo, positivo=producto).
        k  : indice (int) del componente de referencia.
        """
        self.nu = np.asarray(nu, dtype=float)
        self.k = int(k)

        self.nu_tot = np.sum(self.nu)
        self.nu_k = self.nu[self.k]

        # razon_nu = nu/nu_k (vector); factor_tot = nu_tot/nu_k (escalar).
        # Ambos se precalculan una sola vez porque no cambian entre llamadas.
        self.razon_nu = self.nu / self.nu_k
        self.factor_tot = self.nu_tot / self.nu_k

    def _denominador(self, x_k):
        denom = 1.0 - self.factor_tot * x_k
        if np.isclose(denom, 0.0, atol=_TOLERANCIA_SINGULARIDAD):
            raise ValueError(
                "Singularidad en la transformacion de Barbosa-Doherty: "
                f"1 - (nu_tot/nu_k)*x_k = 0 para x_k={x_k!r}. "
                "Este punto es un limite estequiometrico asintotico, "
                "no representa un estado fisico valido."
            )
        return denom

    def transformar(self, x):
        """
        Transformacion directa x -> X (o y -> Y, pasando el vapor).
        X[k] siempre da 0 (la dimension eliminada por la reaccion).
        """
        x = np.asarray(x, dtype=float)
        x_k = x[self.k]
        denom = self._denominador(x_k)
        return (x - self.razon_nu * x_k) / denom

    def inversa(self, X, x_k):
        """
        Transformacion inversa parcial (X, x_k) -> x. Requiere conocer
        aparte la fraccion real del componente de referencia, x_k, porque
        la transformacion directa pierde ese grado de libertad.
        """
        X = np.asarray(X, dtype=float)
        denom = self._denominador(x_k)
        return X * denom + self.razon_nu * x_k
