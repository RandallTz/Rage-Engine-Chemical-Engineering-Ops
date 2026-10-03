"""
Tabla de unidades generada con pint, para que el frontend pueda
convertir en local sin una ida y vuelta al servidor por cada tecla,
pero SIN que las conversiones se escriban a mano en JavaScript: pint
sigue siendo la unica fuente de verdad.

Forma afin:   valor_SI = valor * factor + desplazamiento
El desplazamiento es lo que hace que funcionen las temperaturas
(degC -> K es +273.15; degF -> K es factor 5/9 y desplazamiento
255.372). Verificado: 100 degC -> 373.15 K, 212 degF -> 373.15 K,
360 kmol/h -> 100 mol/s.

El nucleo sigue siendo SI puro: esto vive en la frontera, igual que
config/settings.py y api/simulador_destilacion.py.
"""
from config.settings import ureg

from backend.schemas import Magnitud, UnidadInfo, TablaUnidades

# Que unidades se ofrecen por magnitud. La primera de cada lista es la
# del SI y la que usa el nucleo.
_CANDIDATAS = {
    "flujo_molar": ["mol/s", "kmol/h", "mol/h", "kmol/s"],
    "temperatura": ["K", "degC", "degF", "degR"],
    "presion": ["Pa", "kPa", "bar", "atm", "psi", "mmHg"],
    "potencia": ["W", "kW", "MW", "BTU/h", "cal/s"],
    "energia_molar": ["J/mol", "kJ/mol", "cal/mol"],
    "flujo_masico": ["kg/s", "kg/h", "g/s", "t/h", "lb/h"],
    # Dimensionado: geometria. Van aqui y no como adimensionales porque un
    # diametro en pulgadas y un area en pies cuadrados son lo que pide
    # media industria, y convertirlos a mano es justo el tipo de paso
    # donde se cuelan los errores.
    "longitud": ["m", "cm", "mm", "in", "ft"],
    "area": ["m**2", "cm**2", "ft**2", "in**2"],
    "velocidad": ["m/s", "cm/s", "ft/s", "ft/min"],
    "coef_transferencia": ["W/(m**2*K)", "kW/(m**2*K)", "BTU/(h*ft**2*degR)"],
    # Una DIFERENCIA de temperatura NO es una temperatura, y la distincion
    # no es pedante: convertir 28.74 K a grados Celsius como si fuera una
    # temperatura daria -244.4 C, que es un numero absurdo presentado con
    # toda naturalidad. Las unidades delta de pint tienen el factor pero
    # no el desplazamiento, que es exactamente la diferencia.
    "temperatura_diferencia": ["K", "delta_degC", "delta_degF"],
}

# Ya ninguna magnitud necesita masa molar para convertirse: el paso de
# masa a moles dejo de ser una "unidad" y es una ECUACION del diagrama
# (ver _bloque_caudal_masico en core/diagrama_corrientes.py). Aqui todas
# las conversiones vuelven a ser afines.
_REQUIEREN_MASA_MOLAR = set()

# Nombre legible de cada unidad (pint acepta el simbolo; esto es para la UI).
_ETIQUETAS = {
    "degC": "°C", "degF": "°F", "degR": "°R",
    "delta_degC": "ΔC", "delta_degF": "ΔF",
    "m**2": "m²", "cm**2": "cm²", "ft**2": "ft²", "in**2": "in²",
    "W/(m**2*K)": "W/m²K", "kW/(m**2*K)": "kW/m²K",
    "BTU/(h*ft**2*degR)": "BTU/h·ft²·°R",
    "mol/s": "mol/s", "kmol/h": "kmol/h", "mol/h": "mol/h", "kmol/s": "kmol/s",
    "BTU/h": "BTU/h", "cal/s": "cal/s", "cal/mol": "cal/mol",
    "kg/s": "kg/s", "kg/h": "kg/h", "g/s": "g/s", "t/h": "t/h", "lb/h": "lb/h",
}

# Que magnitud tiene cada variable. Lo que no aparezca es adimensional
# (fracciones molares, q, R, N, R_int) y no ofrece cambio de unidades.
MAGNITUD_POR_VARIABLE = {
    # --- dimensionado
    "diametro": ["longitud"],
    "diametro_cabeza": ["longitud"],
    "diametro_cola": ["longitud"],
    "area_total": ["area"],
    "area": ["area"],
    "velocidad_inundacion": ["velocidad"],
    "lmtd": ["temperatura_diferencia"],
    # El caudal es UNA sola variable; que se exprese en moles o en masa
    # es cosa de la unidad elegida. La conversion a masa necesita la
    # composicion de la corriente, asi que el cliente manda los caudales
    # masicos aparte (ver caudales_masicos en el request).
    "F": ["flujo_molar", "flujo_masico"],
    "V_barra": ["flujo_molar"],
    "T": ["temperatura"],
    "T_D": ["temperatura"],
    "T_B": ["temperatura"],
    "P": ["presion"],
    "Q_c": ["potencia"],
    "Q_R": ["potencia"],
    "Qc_D": ["energia_molar"],
    "QR_B": ["energia_molar"],
}


def _afin(simbolo, si):
    """factor y desplazamiento tales que valor_SI = valor*factor + desplazamiento."""
    cero = ureg.Quantity(0.0, simbolo).to(si).magnitude
    uno = ureg.Quantity(1.0, simbolo).to(si).magnitude
    return uno - cero, cero


def tabla_unidades() -> TablaUnidades:
    magnitudes = {}
    for magnitud, simbolos in _CANDIDATAS.items():
        si = simbolos[0]
        requiere_mw = magnitud in _REQUIEREN_MASA_MOLAR
        unidades = []
        for simbolo in simbolos:
            try:
                factor, desplazamiento = _afin(simbolo, si)
            except Exception:
                continue  # unidad no reconocida por esta version de pint; se omite
            unidades.append(
                UnidadInfo(
                    simbolo=simbolo,
                    etiqueta=_ETIQUETAS.get(simbolo, simbolo),
                    magnitud=magnitud,
                    factor=factor,
                    desplazamiento=desplazamiento,
                    requiere_masa_molar=requiere_mw,
                )
            )
        magnitudes[magnitud] = Magnitud(si=si, unidades=unidades, requiere_masa_molar=requiere_mw)

    return TablaUnidades(magnitudes=magnitudes, variables=MAGNITUD_POR_VARIABLE)
