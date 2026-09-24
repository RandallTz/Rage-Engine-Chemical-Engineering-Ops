"""
Frontera segura del simulador: unico lugar (junto a config/) donde se
manipulan Quantity de pint. Aqui se reciben las unidades del usuario, se
convierten al Sistema Internacional y se extrae su magnitud (float/
np.ndarray) antes de pasarla a thermodynamics/ o core/, que no conocen
pint.
"""

from config.settings import ureg
from thermodynamics.proveedor import ProveedorTermodinamico


class SimuladorColumnaReactiva:
    def __init__(self, nombres_compuestos, T, P):
        """
        nombres_compuestos : lista de nombres reconocidos por 'thermo'.
        T, P                : pint.Quantity (cualquier unidad compatible).
        """
        self.nombres_compuestos = list(nombres_compuestos)

        # T/P de operacion iniciales, ya en SI: quedan aqui para que
        # core/mesh_solver.py las use cuando arranque la trayectoria.
        # ProveedorTermodinamico ya no las recibe en el constructor porque
        # cada metodo pide T_kelvin en el momento del calculo.
        self.T_inicial = self._a_si(T, "kelvin")
        self.P_operacion = self._a_si(P, "pascal")

        self.proveedor = ProveedorTermodinamico(self.nombres_compuestos)

    @staticmethod
    def _a_si(cantidad, unidad_si):
        """
        Convierte una pint.Quantity a la unidad SI indicada y devuelve su
        magnitud (float puro), lista para cruzar hacia core/thermodynamics.
        """
        if not hasattr(cantidad, "to"):
            raise TypeError(
                f"Se esperaba una pint.Quantity, se recibio {type(cantidad)!r}. "
                f"Usa config.settings.ureg para construirla."
            )
        return cantidad.to(unidad_si).magnitude

    def configurar_columna(self, *args, **kwargs):
        """Pendiente: se define junto con las ecuaciones MESH (core/mesh_solver.py)."""
        raise NotImplementedError

    def simular(self, *args, **kwargs):
        """Pendiente: se define junto con las ecuaciones MESH (core/mesh_solver.py)."""
        raise NotImplementedError
