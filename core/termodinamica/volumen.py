"""
Cierre termodinámico de un volumen para las evaluaciones internas del
compilador (muchas por paso): construye el paquete una vez, parte del estado
anterior como semilla y no hace la prueba de estabilidad completa. Las
muestras publicadas se certifican aparte con capa.cierre (todas las
candidatas con su tm).

Devuelve propiedades MOLARES por fase (h, v, M) para que el compilador
evalúe extracciones y corrientes sin conocer el paquete.
"""

from dataclasses import dataclass

import numpy as np

from core import agua_iapws95 as agua
from core import mezclas as mz

from . import capa


@dataclass
class FaseRapida:
    id: str
    tipo: str
    n: float                # mol
    x: np.ndarray           # fracciones molares, orden del volumen
    h: float                # J/mol
    v: float                # m3/mol
    M: float                # kg/mol


@dataclass
class EstadoRapido:
    T: float
    P: float
    V: float
    H: float
    U: float
    fases: list
    nativo: object

    @property
    def firma(self):
        return tuple(sorted(f.id for f in self.fases))


class CierreVolumen:
    def __init__(self, modelo, vid):
        v, paq = capa._volumen(modelo, vid)
        self.vid = vid
        self.ids = list(v["componenteIds"])
        self.candidatas = capa.candidatas(modelo, vid)
        self.agua = paq["modelo"]["id"] == capa.AGUA
        self.sis = None if self.agua else capa._sistema(modelo, v, paq)
        self.M = np.array([agua.M]) if self.agua else np.array(self.sis.M, dtype=float)
        self.semilla = None

    def estado(self, n, espec, a, b, rapido=True):
        n = np.asarray(n, dtype=float)
        if self.agua:
            return self._agua(n, espec, a, b, rapido)
        if rapido and self.semilla is not None and espec in ("PH", "UV", "TP"):
            e = mz.flash_rapido(self.sis, espec, a, b, n, self.semilla)
        elif espec == "PH":
            e = self.sis.equilibrio_PH(a, b, n)
        elif espec == "UV":
            e = self.sis.equilibrio_UV(a, b, n)
        elif espec == "TP":
            e = self.sis.equilibrio_TP(a, b, n)
        elif espec == "TV":
            e = self.sis.equilibrio_TV(a, b, n)
        else:
            raise ValueError(espec)
        self.semilla = e
        ntot = float(n.sum())
        fases = [FaseRapida(f.id, f.tipo, float(f.n), np.asarray(f.x, dtype=float), float(f.h), float(f.v), float(f.M))
                 for f in e.fases if f.n > capa.TOL_PRESENTE * ntot]
        return EstadoRapido(float(e.T), float(e.P), float(e.V), float(e.H), float(e.U), fases, e)

    def _agua(self, n, espec, a, b, rapido):
        m = float(n[0]) * agua.M
        semilla = self.semilla.T if (rapido and self.semilla is not None) else None
        if espec == "PH":
            e = agua.evaluar_PH(a, b / m, certificar=not rapido, T_semilla=semilla)
        elif espec == "UV":
            e = agua.evaluar_UV(a / m, b / m, T_semilla=semilla, certificar=not rapido)
        elif espec == "TP":
            x = agua.evaluar_TP(a, b)
            p = x.propiedades
            fase = FaseRapida("liquido-1" if x.tipo == "liquido" else "vapor-1", x.tipo, float(n[0]), np.array([1.0]),
                              p.h * agua.M, p.v * agua.M, agua.M)
            est = EstadoRapido(a, b, p.v * m, p.h * m, p.u * m, [fase], x)
            self.semilla = est
            return est
        elif espec == "TV":
            e = agua.evaluar_TV(a, b / m)
        else:
            raise ValueError(espec)
        fases = []
        for f in e.fases:
            if f.fraccion > capa.TOL_PRESENTE:
                p = f.propiedades
                fases.append(FaseRapida("liquido-1" if f.tipo == "liquido" else "vapor-1", f.tipo, float(n[0]) * f.fraccion,
                                        np.array([1.0]), p.h * agua.M, p.v * agua.M, agua.M))
        est = EstadoRapido(float(e.T), float(e.P), float(e.v * m), float(e.h * m), float(e.u * m), fases, e)
        self.semilla = est
        return est
