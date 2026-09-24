"""
Frontera segura para el Orquestador de destilacion binaria (balance de
materia + McCabe-Thiele/Ponchon-Savarit + cargas termicas). Es la
tercera frontera de pint del proyecto (junto a config/settings.py y
api/simulador.py) -- Orquestador, y todos los bloques que conecta, no
conocen pint: trabajan en floats/SI puros.

Deliberadamente NO construye el Evaluador/Solucionador/Orquestador --
los recibe ya armados. Quien decide que bloques combinar (McCabe-Thiele
vs Ponchon-Savarit, con o sin cargas termicas) sigue siendo quien arma
el Orquestador (ver ejemplo_destilacion_binaria.py); esta clase solo
resuelve el cruce de unidades para esa llamada, sin opinar sobre la
composicion de bloques.
"""

from config.settings import ureg


class SimuladorDestilacionBinaria:
    # Unidades SI de las variables del pool que SI tienen dimension
    # fisica. z_F, x_D, x_B, q, R, N, Qc_D, QR_B son adimensionales o ya
    # estan en base molar especifica (J/mol) -- se pasan/devuelven como
    # float tal cual, sin pasar por pint.
    _UNIDADES_SI = {
        "F": "mol/s", "D": "mol/s", "B": "mol/s",
        "Q_c": "watt", "Q_R": "watt",
        "T_D": "kelvin", "T_B": "kelvin", "T_reflujo": "kelvin",
    }

    def __init__(self, orquestador):
        """orquestador: instancia de Orquestador (core/orquestador.py), ya armada con sus bloques."""
        self.orquestador = orquestador

    @staticmethod
    def _a_si(cantidad, unidad_si):
        if not hasattr(cantidad, "to"):
            raise TypeError(
                f"Se esperaba una pint.Quantity para esta variable, se "
                f"recibio {type(cantidad)!r}. Usa config.settings.ureg "
                "para construirla."
            )
        return cantidad.to(unidad_si).magnitude

    def resolver(self, **valores):
        """
        Mismos nombres de variable que Orquestador.resolver. Las que
        tienen unidad fisica (ver _UNIDADES_SI) se esperan como
        pint.Quantity; el resto (adimensionales) se pasan como float
        directo. Devuelve el mismo dict que Orquestador.resolver, pero
        con esas mismas variables convertidas de vuelta a pint.Quantity
        dentro de 'pool'.
        """
        valores_si = {}
        for nombre, valor in valores.items():
            if valor is None:
                continue
            unidad = self._UNIDADES_SI.get(nombre)
            valores_si[nombre] = self._a_si(valor, unidad) if unidad else valor

        resultado = self.orquestador.resolver(**valores_si)

        pool_con_unidades = dict(resultado["pool"])
        for nombre, unidad in self._UNIDADES_SI.items():
            valor_si = pool_con_unidades.get(nombre)
            if valor_si is not None:
                pool_con_unidades[nombre] = ureg.Quantity(valor_si, unidad)

        resultado_con_unidades = dict(resultado)
        resultado_con_unidades["pool"] = pool_con_unidades
        return resultado_con_unidades
