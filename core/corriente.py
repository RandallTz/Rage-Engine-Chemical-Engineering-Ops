"""
Corriente: estado fisico de una corriente de proceso -- composicion,
flujo molar, T, P. Es el "vocabulario comun" pensado para conectar
CUALQUIER operacion unitaria futura (columnas de destilacion, reactores,
bombas, mezcladores, lo que se agregue despues) sin que ninguna necesite
conocer los detalles internos de la otra -- solo necesitan coincidir en
que ambas hablan en terminos de Corriente.

Deliberadamente NO carga un ProveedorTermodinamico ni sabe calcular
propiedades derivadas (entalpia, fase, etc.) -- es un contenedor de
ESTADO, no un evaluador. Una operacion que solo cambia P (una bomba
ideal) puede construir su Corriente de salida sin tocar termodinamica en
absoluto; una que sí necesita derivar algo (mezclar_corrientes, mas
abajo, que necesita un balance de energia real) recibe su propio
proveedor por fuera, igual que cualquier otro Evaluador/Solucionador del
proyecto.

Ahora sí tiene consumidor real: ver core/diagrama_flujo.py (el conector
de flechas/flowsheet). Este modulo sigue siendo solo el estado que viaja
por esas flechas -- no conoce el grafo ni las conexiones.
"""

import math

import numpy as np
from scipy.integrate import quad
from scipy.optimize import brentq


class Corriente:
    def __init__(self, nombres, composicion, flujo_molar, T, P):
        """
        nombres     : lista de n nombres de componentes.
        composicion : vector de n fracciones molares (debe sumar 1).
        flujo_molar : flujo molar TOTAL [mol/tiempo], >= 0.
        T           : temperatura [K], > 0.
        P           : presion [Pa], > 0.
        """
        self.nombres = list(nombres)
        self.composicion = np.asarray(composicion, dtype=float)
        self.flujo_molar = float(flujo_molar)
        self.T = float(T)
        self.P = float(P)

        # Un estado no finito (NaN, inf) pasa las comparaciones '< 0' sin
        # disparar nada: se rechaza antes, porque esta clase viaja entre equipos.
        for nombre, valor in (("flujo_molar", self.flujo_molar), ("T", self.T),
                              ("P", self.P)):
            if not math.isfinite(valor):
                raise ValueError(f"{nombre} tiene que ser finito (se recibio {valor}).")
        if not np.all(np.isfinite(self.composicion)):
            raise ValueError("composicion tiene que ser finita (hay NaN o infinito).")
        if len(self.nombres) != len(self.composicion):
            raise ValueError(
                f"nombres tiene {len(self.nombres)} componentes pero "
                f"composicion tiene {len(self.composicion)}."
            )
        if not np.isclose(self.composicion.sum(), 1.0, atol=1e-6):
            raise ValueError(f"composicion debe sumar 1.0 (suma actual: {self.composicion.sum():.6f}).")
        if np.any(self.composicion < -1e-9):
            raise ValueError("composicion no puede tener fracciones negativas.")
        if self.flujo_molar < 0:
            raise ValueError(f"flujo_molar no puede ser negativo (se recibio {self.flujo_molar}).")
        if self.T <= 0:
            raise ValueError(f"T debe ser positiva en Kelvin (se recibio {self.T}).")
        if self.P <= 0:
            raise ValueError(f"P debe ser positiva en Pascales (se recibio {self.P}).")

    def flujos_por_componente(self):
        """Vector de flujos molares individuales [mol/tiempo]."""
        return self.flujo_molar * self.composicion

    def fraccion(self, nombre):
        """Fraccion molar de un componente por nombre (evita buscar el indice a mano)."""
        return float(self.composicion[self.nombres.index(nombre)])

    @classmethod
    def desde_flujos(cls, nombres, flujos, T, P):
        """Construye a partir de flujos molares individuales (no fracciones) -- flujo_molar y composicion se derivan."""
        flujos = np.asarray(flujos, dtype=float)
        flujo_molar = float(flujos.sum())
        return cls(nombres, flujos / flujo_molar, flujo_molar, T, P)

    def __repr__(self):
        comp = ", ".join(f"{n}={x:.4f}" for n, x in zip(self.nombres, self.composicion))
        return f"Corriente(F={self.flujo_molar:.4f} mol/s, T={self.T:.2f}K, P={self.P:.0f}Pa, [{comp}])"


def _entalpia_liquido_molar(proveedor, composicion, T, T_ref=298.15):
    """
    H_L(T,x) = suma_i x_i * integral(Cp_L,i, T_ref, T) [J/mol] -- misma
    formula y mismo camino de integracion que
    EvaluadorPonchonSavarit._entalpia_liquido (core/ponchon_savarit.py).
    Se reescribe aqui suelta (en vez de importar esa clase) porque
    EvaluadorPonchonSavarit esta acoplada a un sistema BINARIO
    (precalcula splines y usa nombres[0]/nombres[1] en su constructor) y
    esto necesita funcionar para cualquier n de componentes, sin pagar
    el costo de precalcular curvas de equilibrio que aqui no hacen falta.
    """
    integrando = lambda Tp: float(np.dot(composicion, proveedor.capacidades_calorificas_liquido(Tp)))
    valor, _ = quad(integrando, T_ref, T)
    return valor


def mezclar_corrientes(corrientes, proveedor, T_ref=298.15):
    """
    Mezcla N corrientes LIQUIDAS (mismo P; esto NO valida que el
    resultado siga siendo una sola fase liquida a la T de salida -- no
    hace flash) en una sola, vía balance de materia exacto + balance de
    ENERGIA real -- no un promedio de T ponderado por flujo, que
    ignoraria que el Cp difiere entre corrientes:

        suma_k F_k * H_L(T_k, x_k) = F_total * H_L(T_salida, x_mezcla)

    T_salida se resuelve con brentq. El bracket [T_min, T_max] de las
    corrientes de entrada es valido porque, sin calor de mezcla (misma
    aproximacion ideal usada en todo el proyecto) y con Cp_L>0, H_L(T,x)
    es creciente en T -- la T de una mezcla adiabatica sin reaccion
    siempre cae en ese rango.
    """
    if len(corrientes) < 2:
        raise ValueError("Se necesitan al menos 2 corrientes para mezclar.")

    nombres = corrientes[0].nombres
    for c in corrientes[1:]:
        if c.nombres != nombres:
            raise ValueError("Todas las corrientes deben tener los mismos componentes en el mismo orden.")

    F_total = sum(c.flujo_molar for c in corrientes)
    flujos_totales = sum(c.flujos_por_componente() for c in corrientes)
    composicion_mezcla = flujos_totales / F_total

    H_entrada = sum(
        c.flujo_molar * _entalpia_liquido_molar(proveedor, c.composicion, c.T, T_ref)
        for c in corrientes
    )

    def residuo(T):
        return F_total * _entalpia_liquido_molar(proveedor, composicion_mezcla, T, T_ref) - H_entrada

    T_min = min(c.T for c in corrientes)
    T_max = max(c.T for c in corrientes)

    if np.isclose(T_min, T_max):
        T_salida = T_min  # todas las corrientes ya estan a la misma T -- no hace falta resolver nada
    else:
        T_salida = brentq(residuo, T_min - 1.0, T_max + 1.0)

    P_salida = corrientes[0].P
    return Corriente(nombres, composicion_mezcla, F_total, T_salida, P_salida)


def dividir_corriente(corriente, fracciones):
    """
    Contraparte de mezclar_corrientes: reparte UNA corriente en N, misma
    composicion/T/P en todas (un divisor ideal no cambia estado
    intensivo, solo reparte flujo) -- no hace falta ningun balance de
    energia porque no hay mezcla de estados distintos.

    fracciones: iterable de fracciones de flujo, debe sumar 1.0.
    """
    fracciones = np.asarray(fracciones, dtype=float)
    if not np.isclose(fracciones.sum(), 1.0, atol=1e-6):
        raise ValueError(f"Las fracciones deben sumar 1.0 (suma actual: {fracciones.sum():.6f}).")
    if np.any(fracciones < 0):
        raise ValueError("Las fracciones no pueden ser negativas.")
    return [
        Corriente(corriente.nombres, corriente.composicion, f * corriente.flujo_molar, corriente.T, corriente.P)
        for f in fracciones
    ]
