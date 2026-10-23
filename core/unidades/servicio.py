"""
Servicio de unidades: una sola interpretación para todo el proyecto.

Dimensión: vector exacto (fracciones) sobre las siete bases SI
    M (kg), L (m), T (s), N (mol), Theta (K), I (A), J (cd).
Conversión: valor_SI = factor * valor + desplazamiento. El desplazamiento
solo es distinto de cero en escalas afines (°C, °F); una unidad afín no
puede multiplicarse por otras (pint lo rechaza y aquí se informa).

La interpretación la hace pint; este módulo solo normaliza las grafías del
proyecto (m3, cm2, ³, ·, °C, "1", "adimensional") y publica el resultado en
una forma estable. No hay tablas de unidades por magnitud.
"""

import functools
import math
import re
from fractions import Fraction

BASES = {"[mass]": "M", "[length]": "L", "[time]": "T", "[substance]": "N", "[temperature]": "Theta",
         "[current]": "I", "[luminosity]": "J"}
ORDEN = ["M", "L", "T", "N", "Theta", "I", "J"]
SIMBOLO_SI = {"M": "kg", "L": "m", "T": "s", "N": "mol", "Theta": "K", "I": "A", "J": "cd"}

_UREG = None
_EXACT_UREG = None


class ErrorUnidad(Exception):
    pass


def _registro():
    global _UREG
    if _UREG is None:
        import pint
        _UREG = pint.UnitRegistry()
    return _UREG


def _d(**k):
    return {b: Fraction(v) for b, v in k.items() if v}


# Catálogo genérico de magnitudes físicas: nombre -> dimensión. Varias magnitudes
# comparten dimensión (presión y densidad de energía); por eso un nombre nunca se
# deduce de una unidad, solo se ofrecen candidatos (magnitudes_de).
MAGNITUDES = {
    "adimensional": {},
    "longitud": _d(L=1), "area": _d(L=2), "volumen": _d(L=3),
    "masa": _d(M=1), "tiempo": _d(T=1), "temperatura": _d(Theta=1), "cantidad": _d(N=1),
    "corriente": _d(I=1), "intensidad_luminosa": _d(J=1),
    "frecuencia": _d(T=-1), "velocidad": _d(L=1, T=-1), "aceleracion": _d(L=1, T=-2),
    "fuerza": _d(M=1, L=1, T=-2), "presion": _d(M=1, L=-1, T=-2), "energia": _d(M=1, L=2, T=-2),
    "potencia": _d(M=1, L=2, T=-3),
    "densidad": _d(M=1, L=-3), "concentracion_molar": _d(N=1, L=-3), "volumen_molar": _d(L=3, N=-1),
    "volumen_especifico": _d(L=3, M=-1), "masa_molar": _d(M=1, N=-1),
    "caudal_masico": _d(M=1, T=-1), "caudal_molar": _d(N=1, T=-1), "caudal_volumetrico": _d(L=3, T=-1),
    "flujo_masico": _d(M=1, L=-2, T=-1), "flujo_molar": _d(N=1, L=-2, T=-1), "flujo_de_calor": _d(M=1, T=-3),
    "tasa_volumetrica_masica": _d(M=1, L=-3, T=-1), "tasa_volumetrica_molar": _d(N=1, L=-3, T=-1),
    "difusividad": _d(L=2, T=-1), "viscosidad_dinamica": _d(M=1, L=-1, T=-1),
    "energia_especifica": _d(L=2, T=-2), "energia_molar": _d(M=1, L=2, T=-2, N=-1),
    "capacidad_calorifica_especifica": _d(L=2, T=-2, Theta=-1), "capacidad_calorifica_molar": _d(M=1, L=2, T=-2, N=-1, Theta=-1),
    "entropia": _d(M=1, L=2, T=-2, Theta=-1),
    "conductancia_termica": _d(M=1, L=2, T=-3, Theta=-1), "conductividad_termica": _d(M=1, L=1, T=-3, Theta=-1),
    "coeficiente_transferencia_calor": _d(M=1, T=-3, Theta=-1),
}

# Unidades SI derivadas con nombre (presentación); el resto se escribe en las bases.
_DERIVADAS = [("W", _d(M=1, L=2, T=-3)), ("J", _d(M=1, L=2, T=-2)), ("Pa", _d(M=1, L=-1, T=-2)),
              ("N", _d(M=1, L=1, T=-2))]


def normalizar(texto):
    """Grafía del proyecto -> texto que pint entiende."""
    if texto is None:
        raise ErrorUnidad("unidad requerida")
    t = str(texto).strip()
    if t in ("", "1", "-", "adimensional", "dimensionless"):
        return "dimensionless"
    t = t.replace("·", "*").replace("×", "*").replace("³", "^3").replace("²", "^2").replace("µ", "u")
    t = t.replace("°C", "degC").replace("ºC", "degC").replace("°F", "degF").replace("ºF", "degF").replace("°", "deg")
    # potencias compactas: m3 -> m**3, cm2 -> cm**2, s-1 -> s**-1 (un símbolo de letras seguido de un entero)
    t = re.sub(r"(?<![A-Za-z0-9_])([A-Za-z]+)(-?\d+)(?![\w.])", r"\1**\2", t)
    return t.replace("^", "**")


def _frac(x):
    return Fraction(x) if not isinstance(x, float) else Fraction(x).limit_denominator(1000)


@functools.lru_cache(maxsize=4096)
def interpretar(unidad):
    """{'unidad', 'normalizada', 'dimension' (bases -> Fraction), 'factor', 'desplazamiento', 'afin'}."""
    norm = normalizar(unidad)
    try:
        u = _registro()
        q = u.Quantity(1.0, norm)
    except Exception as e:      # noqa: BLE001 - pint lanza varios tipos
        raise ErrorUnidad(f"unidad no reconocida: {unidad!r}") from e
    dim = {}
    for base, exp in dict(q.dimensionality).items():
        if base not in BASES:
            raise ErrorUnidad(f"dimensión fuera de las bases SI en {unidad!r}: {base}")
        dim[BASES[base]] = _frac(exp)
    dim = {k: v for k, v in dim.items() if v}
    afin = not q._is_multiplicative
    if afin:
        cero = u.Quantity(0.0, norm).to_base_units().magnitude
        uno = u.Quantity(1.0, norm).to_base_units().magnitude
        factor, desp = float(uno - cero), float(cero)
    else:
        factor, desp = float(q.to_base_units().magnitude), 0.0
    return {"unidad": unidad, "normalizada": norm, "dimension": dim, "factor": factor, "desplazamiento": desp, "afin": afin}


def a_SI(valor, unidad):
    i = interpretar(unidad)
    return i["factor"] * valor + i["desplazamiento"]


@functools.lru_cache(maxsize=4096)
def exact_conversion(unit):
    """Rational SI conversion from the same Pint definitions, without float rounding.

    Catalog definitions are authoritative; this does not certify empirical
    constants in that catalog. Nonrational conversions remain unsupported.
    """
    global _EXACT_UREG
    specification = interpretar(unit)
    try:
        if _EXACT_UREG is None:
            import pint
            _EXACT_UREG = pint.UnitRegistry(non_int_type=Fraction)
        zero = _EXACT_UREG.Quantity(Fraction(0), normalizar(unit)).to_base_units().magnitude
        one = _EXACT_UREG.Quantity(Fraction(1), normalizar(unit)).to_base_units().magnitude
        if not all(isinstance(value, (int, Fraction)) for value in (zero, one)):
            raise ValueError('Conversion is not rational.')
        factor, offset = Fraction(one - zero), Fraction(zero)
        if factor <= 0:
            raise ValueError('Conversion must be order preserving.')
    except Exception as error:
        raise ErrorUnidad('Exact rational unit conversion is unavailable for this unit.') from error
    return {**specification, 'factor':factor, 'desplazamiento':offset}


def desde_SI(valor, unidad):
    i = interpretar(unidad)
    return (valor - i["desplazamiento"]) / i["factor"]


def compatibles(u1, u2):
    return interpretar(u1)["dimension"] == interpretar(u2)["dimension"]


def dimension_texto(dim):
    partes = [k if v == 1 else f"{k}^{v}" for k in ORDEN for v in [dim.get(k, 0)] if v]
    return " ".join(partes) or "1"


def unidad_SI(dim):
    """Texto canónico SI de una dimensión.

    Una derivada con nombre si coincide exacta (W, J, Pa, N); una derivada
    dividida por bases si el resto solo tiene exponentes negativos (J/mol,
    J/(kg*K), W/K, Pa/s); si no, las bases (kg/s, mol/m^3, m^2/s)."""
    dim = {k: Fraction(v) for k, v in dim.items() if v}
    if not dim:
        return "1"
    for nombre, d in _DERIVADAS:
        if dim == d:
            return nombre
    for nombre, d in _DERIVADAS:
        resto = {k: dim.get(k, Fraction(0)) - d.get(k, Fraction(0)) for k in set(dim) | set(d)}
        resto = {k: v for k, v in resto.items() if v}
        if resto and all(v < 0 for v in resto.values()):
            return f"{nombre}/{_texto({k: -v for k, v in resto.items()})}"
    num = {k: v for k, v in dim.items() if v > 0}
    den = {k: -v for k, v in dim.items() if v < 0}
    if not den:
        return _texto(num, parentesis=False)
    return f"{_texto(num, parentesis=False) if num else '1'}/{_texto(den)}"


def _texto(d, parentesis=True):
    partes = []
    for k in ORDEN:
        v = d.get(k, 0)
        if v:
            partes.append(SIMBOLO_SI[k] if v == 1 else f"{SIMBOLO_SI[k]}^{v.numerator if v.denominator == 1 else f'({v})'}")
    if len(partes) > 1 and parentesis:
        return "(" + "*".join(partes) + ")"
    return "*".join(partes)


def dimension_de_magnitud(nombre):
    if nombre not in MAGNITUDES:
        raise ErrorUnidad(f"magnitud desconocida: {nombre!r}")
    return dict(MAGNITUDES[nombre])


def magnitudes_de(dim):
    dim = {k: Fraction(v) for k, v in dim.items() if v}
    return [n for n, d in MAGNITUDES.items() if d == dim]


def dimension_json(dim):
    return {k: {"n": v.numerator, "d": v.denominator} for k, v in sorted(dim.items()) if v}


def finito(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)
