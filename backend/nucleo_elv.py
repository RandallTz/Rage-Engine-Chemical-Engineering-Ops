"""
Curvas de equilibrio liquido-vapor para un par BINARIO -- el modo
"termodinamica" de la interfaz. Barre la composicion y resuelve el punto
de burbuja en cada una, que es exactamente lo que ya hace
EvaluadorMcCabeThiele en su constructor; aqui se devuelve como datos
(para graficar en el frontend) en vez de como spline interna.

Los extremos exactos (x=0 y x=1) NO se calculan con burbuja_T/UNIFAC --
se usa el punto de ebullicion normal (Tb) de cada componente puro, por
la misma razon ya documentada en core/ponchon_savarit.py: UNIFAC se
porta mal con una fraccion molar exactamente cero.
"""
import numpy as np

from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.elv import CalculadoraELV

from backend.schemas import ELVBinarioRequest, ELVBinarioResponse, PuntoAzeotropo


def _detectar_azeotropo(x, y, T):
    """
    Azeotropo binario = donde la curva y(x) cruza la diagonal y=x en el
    interior. Se busca un cambio de signo de (y-x) y se interpola
    linealmente entre los dos puntos del barrido -- suficiente para
    senalarlo en un diagrama; el calculo riguroso vive en
    core/analisis_nodos.py.
    """
    diferencia = y - x
    interior = slice(1, -1)
    signos = np.sign(diferencia[interior])
    cambios = np.where(np.diff(signos) != 0)[0]
    if len(cambios) == 0:
        return None

    i = cambios[0] + 1  # indice en el arreglo completo
    d0, d1 = diferencia[i], diferencia[i + 1]
    if d1 == d0:
        fraccion = 0.0
    else:
        fraccion = d0 / (d0 - d1)
    x_az = float(x[i] + fraccion * (x[i + 1] - x[i]))
    T_az = float(T[i] + fraccion * (T[i + 1] - T[i]))
    return PuntoAzeotropo(x=x_az, T=T_az)


def curva_elv_binaria(request: ELVBinarioRequest) -> ELVBinarioResponse:
    if len(request.nombres) != 2:
        raise ValueError(f"El diagrama ELV binario necesita exactamente 2 componentes, se recibieron {len(request.nombres)}.")

    proveedor = ProveedorTermodinamico(request.nombres)
    calc_elv = CalculadoraELV(proveedor)

    n = request.n_puntos
    x_interior = np.linspace(1e-4, 1.0 - 1e-4, n)
    y_interior = np.empty(n)
    T_interior = np.empty(n)
    for i, x1 in enumerate(x_interior):
        T, y_vapor = calc_elv.burbuja_T(request.P, np.array([x1, 1.0 - x1]))
        T_interior[i] = T
        y_interior[i] = y_vapor[0]

    Tb_ligero = float(proveedor.componentes[0].Tb)
    Tb_pesado = float(proveedor.componentes[1].Tb)

    x = np.concatenate([[0.0], x_interior, [1.0]])
    y = np.concatenate([[0.0], y_interior, [1.0]])
    T = np.concatenate([[Tb_pesado], T_interior, [Tb_ligero]])

    return ELVBinarioResponse(
        nombres=request.nombres,
        P=request.P,
        x=[float(v) for v in x],
        y=[float(v) for v in y],
        T=[float(v) for v in T],
        Tb_ligero=Tb_ligero,
        Tb_pesado=Tb_pesado,
        azeotropo=_detectar_azeotropo(x, y, T),
    )
