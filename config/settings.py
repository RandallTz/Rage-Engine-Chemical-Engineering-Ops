"""
Instancia global de pint y constantes universales.

Este modulo es una de las dos unicas fronteras (junto a api/) donde se
permite trabajar con pint. Cualquier Quantity que entre a core/ o
thermodynamics/ debe haber sido convertida antes a SI y reducida a su
magnitud (float/np.ndarray).
"""

import pint

ureg = pint.UnitRegistry()
Q_ = ureg.Quantity

# Constantes universales, expresadas como Quantity de pint.
R_UNIVERSAL = Q_(8.314462618, "J/(mol*K)")

# Condiciones de referencia estandar.
T_REFERENCIA = Q_(298.15, "K")
P_REFERENCIA = Q_(101325.0, "Pa")
