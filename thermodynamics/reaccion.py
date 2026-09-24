"""
Termodinamica y cinetica de la reaccion, vectorizada con numpy.

GestorReaccion encapsula: (A) las propiedades estandar de reaccion
(precalculadas una vez, producto punto nu*Hf y nu*Gf), (B) la constante
de equilibrio K_eq(T) via van't Hoff, y (C) la velocidad neta de
reaccion r(T, x) via Arrhenius + actividades (x*gamma). No usa bucles
for para la matematica: las productorias estequiometricas se resuelven
con mascaras booleanas sobre nu y np.prod/np.power.
"""

import numpy as np

R_UNIVERSAL = 8.31446   # J/(mol*K)
T_STD = 298.15          # K


class GestorReaccion:
    def __init__(self, proveedor, nu, A, Ea, T_std=T_STD, R=R_UNIVERSAL):
        """
        proveedor : ProveedorTermodinamico ya construido con los mismos
                    componentes (mismo orden) que 'nu'.
        nu        : vector estequiometrico (negativo=reactivo, positivo=producto).
        A, Ea     : parametros de Arrhenius (A en las mismas unidades que
                    r; Ea en J/mol).
        """
        self.proveedor = proveedor
        self.nu = np.asarray(nu, dtype=float)
        self.A = float(A)
        self.Ea = float(Ea)
        self.T_std = float(T_std)
        self.R = float(R)

        # mascaras booleanas: evitan cualquier bucle for en las productorias
        self._mask_reactivos = self.nu < 0
        self._mask_productos = self.nu > 0
        self._exp_reactivos = np.where(self._mask_reactivos, -self.nu, 0.0)
        self._exp_productos = np.where(self._mask_productos, self.nu, 0.0)

        # A. Propiedades estandar de reaccion (precalculo, producto punto)
        Hf = self.proveedor.entalpias_formacion_liquido()
        Gf = self.proveedor.energias_gibbs_formacion_liquido()

        self.dH_rxn = np.dot(self.nu, Hf)   # J/mol
        self.dG_rxn = np.dot(self.nu, Gf)   # J/mol

        self.K_eq_std = np.exp(-self.dG_rxn / (self.R * self.T_std))

    def K_eq(self, T_kelvin):
        """
        B. Constante de equilibrio K_eq(T) via van't Hoff, asumiendo
        DeltaH_rxn° constante entre T_std y T.
        """
        return self.K_eq_std * np.exp(
            (self.dH_rxn / self.R) * (1.0 / self.T_std - 1.0 / T_kelvin)
        )

    def velocidad_reaccion(self, T_kelvin, x_mezcla):
        """
        C. Velocidad neta de reaccion r(T, x):
            k(T) = A * exp(-Ea / (R*T))
            a    = x * gamma(T, x)
            r    = k(T) * ( prod_reactivos a_i^|nu_i| - (1/K_eq(T)) * prod_productos a_j^nu_j )
        """
        x_mezcla = np.asarray(x_mezcla, dtype=float)

        k = self.A * np.exp(-self.Ea / (self.R * T_kelvin))

        gamma = self.proveedor.coeficientes_actividad(T_kelvin, x_mezcla)
        actividades = x_mezcla * gamma

        termino_directo = np.prod(np.power(actividades, self._exp_reactivos))
        termino_inverso = np.prod(np.power(actividades, self._exp_productos))

        return k * (termino_directo - termino_inverso / self.K_eq(T_kelvin))
