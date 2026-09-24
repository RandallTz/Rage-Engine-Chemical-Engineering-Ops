"""Script de ejecucion del usuario. Esqueleto pendiente de revision."""

from config.settings import ureg
from api.simulador import SimuladorColumnaReactiva

if __name__ == "__main__":
    simulador = SimuladorColumnaReactiva(
        nombres_compuestos=["water", "ethanol"],
        T=ureg.Quantity(350.0, "kelvin"),
        P=ureg.Quantity(1.0, "atm"),
    )
