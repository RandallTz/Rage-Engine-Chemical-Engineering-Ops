"""
Interfaz uniforme de paquetes constitutivos para el coordinador de varios
volumenes (revision 2 del ensamblaje). Todo en base MOLAR y SI:

    paquete.especies              CAS en orden
    paquete.M                     kg/mol por especie
    paquete.estado(espec, a, b, n, semilla, certificar) -> EstadoMezcla
        espec 'UV' (a=U J, b=V m3), 'PH' (a=P, b=H J), 'UP' (a=P, b=U J),
        'TP' (a=T, b=P), 'TV' (a=T, b=V)
    paquete.transporte_TP(T, P, x) -> (h, s) molares del fluido exterior de
        composicion x en equilibrio a (T, P) (donante exterior)

El agua usa IAPWS-95 (core/agua_iapws95.py): sus propiedades por kg se pasan
a molares con M = 18.015268 g/mol; mu del puro es su g molar. Las mezclas usan
core/mezclas.py. Cada paquete conserva su referencia; el ensamblaje no conecta
por corrientes volumenes con referencias distintas.
"""

import math

import numpy as np

from core import agua_iapws95 as agua
from core import mezclas as mz


_CACHE_TP = {}


def _h_TP_agua(T, P):
    """h [J/kg] of exterior water at (T, P): the same branch and checks as the H1 TP evaluation (domain, critical
    band, undetermined saturation). Moved unchanged from the retired core/ensamblaje_dinamico.py (dec-r5-legacy-v1)."""
    clave = (T, P)
    if clave in _CACHE_TP:
        return _CACHE_TP[clave]
    if not (agua.T_MIN <= T <= agua.T_MAX and agua.P_MIN <= P <= agua.P_MAX):
        raise agua.FueraDeAlcance("fuera_de_dominio", f"Donante exterior T = {T:.6g} K, P = {P:.6g} Pa fuera del dominio.")
    if agua.T_CRITICA[0] <= T <= agua.T_CRITICA[1] and agua.P_CRITICA[0] <= P <= agua.P_CRITICA[1]:
        raise agua.FueraDeAlcance("region_critica", f"Donante exterior T = {T:.6g} K, P = {P:.6g} Pa en la banda critica.")
    ramas_T, sat = agua.ramas(T)
    if sat is not None:
        if abs(P / sat.Psat - 1.0) <= agua.TOL_SATURACION:
            raise agua.FueraDeAlcance("saturacion", f"Donante exterior en saturacion a {T:.6g} K: T y P no fijan su h.")
        nombre = "liquido" if P > sat.Psat else "vapor"
    else:
        nombre = "fluido"
    _, lo, hi = next(r for r in ramas_T if r[0] == nombre)
    h = agua.propiedades(T, agua.densidad(T, P, lo, hi)).h
    if len(_CACHE_TP) > 10000:
        _CACHE_TP.clear()
    _CACHE_TP[clave] = h
    return h


class PaqueteNoAplicable(Exception):
    pass


def _fase_agua(f, n_total, P):
    p = f.propiedades
    M = agua.M
    fm = mz.FaseMezcla(id=f"{f.tipo}-1", tipo=f.tipo, n=f.fraccion * n_total, x=np.array([1.0]),
                       h=p.h * M, s=p.s * M, v=p.v * M, g=p.g * M, mu=np.array([p.g * M]), M=M)
    fm._P = P
    fm.regimen = f.regimen
    return fm


class PaqueteAgua:
    def huella(self):
        return _huella_agua()

    id, version = "agua-iapws95", "1"
    referencia = {"id": "iapws95-u0-s0-liquido-saturado-punto-triple",
                  "descripcion": "IAPWS-95: u = 0 y s = 0 del líquido saturado en el punto triple."}

    def __init__(self, cas):
        if list(cas) != [agua.CAS]:
            raise PaqueteNoAplicable("El paquete agua-iapws95 describe solo agua pura.")
        self.especies = (agua.CAS,)
        self.M = np.array([agua.M])
        self.T_rango = (agua.T_MIN, agua.T_MAX)

    def _envolver(self, e, n_total, espec, P_de=None):
        if isinstance(e, agua.EstadoAgua):
            f = agua.FaseCalculada(e.tipo, e.regimen, 1.0, e.propiedades)
            fases = [_fase_agua(f, n_total, e.P)]
            T, P = e.propiedades.T, e.P
            est_res = e.estabilidad.residuo
            eq = 0.0
        else:
            fases = [_fase_agua(f, n_total, e.P) for f in e.fases]
            T, P = e.T, e.P
            est_res = e.estabilidad[0].residuo if e.estabilidad else None
            eq = e.coexistencia.residuo if e.coexistencia is not None else 0.0
        out = mz.EstadoMezcla(especificacion=espec, T=T, P=P, especies=self.especies, n=np.array([n_total]),
                              fases=fases)
        out.verificaciones["reconstruccion_material"] = (abs(sum(f.n for f in fases) - n_total) / n_total, 1e-12,
                                                         "sum de fases frente a n")
        out.verificaciones["equilibrio"] = (eq, agua.TOL_SATURACION_MAXWELL, "Maxwell (IAPWS-95)")
        out.verificaciones["estabilidad"] = ((est_res if est_res is not None else math.nan), 1e-9,
                                             "TPD de sustancia pura sobre las ramas de IAPWS-95"
                                             if est_res is not None else "no certificada (evaluación interna)")
        out.estabilidad = {"tm_min": -est_res if est_res is not None else None, "pruebas": None,
                           "candidatas": ["liquido", "vapor", "fluido"]}
        out.nucleo = e
        return out

    def estado(self, espec, a, b, n, semilla=None, certificar=False):
        n_total = float(np.sum(n))
        m = n_total * agua.M
        Ts = semilla.T if semilla is not None else None
        try:
            if espec == "UV":
                e = agua.evaluar_UV(a / m, b / m, T_semilla=Ts, certificar=certificar)
            elif espec == "PH":
                e = agua.evaluar_PH(a, b / m, certificar=certificar, T_semilla=Ts)
            elif espec == "UP":
                e = agua.evaluar_UP(a, b / m, certificar=certificar)
            elif espec == "TP":
                e = agua.evaluar_TP(a, b)
            elif espec == "TV":
                e = agua.evaluar_TV(a, b / m)
            else:
                raise ValueError(espec)
        except agua.FueraDeAlcance as x:
            raise mz.FueraDeAlcance(x.motivo, x.mensaje, **x.datos)
        return self._envolver(e, n_total, espec)

    def transporte_TP(self, T, P, x):
        """(h, s) molares del agua exterior a (T, P)."""
        try:
            h = _h_TP_agua(T, P)
            e = agua.evaluar_TP(T, P)
        except agua.FueraDeAlcance as x_:
            raise mz.FueraDeAlcance(x_.motivo, x_.mensaje, **x_.datos)
        return h * agua.M, e.propiedades.s * agua.M


def _huella_agua():
    """Huella del cierre del agua: formulacion y version auditada de la libreria que la evalua."""
    import hashlib
    import json
    datos = {"formulacion": agua.FORMULACION, "chemicals": agua.VERSION_CHEMICALS_AUDITADA, "cas": agua.CAS,
             "dominio": [agua.T_MIN, agua.T_MAX, agua.P_MIN, agua.P_MAX]}
    return "sha256:" + hashlib.sha256(json.dumps(datos, sort_keys=True).encode()).hexdigest()


class PaqueteMezcla:
    def huella(self):
        return self.sistema.huella()

    def __init__(self, modelo_id, cas, sustituciones=None):
        self.sistema = mz.Sistema(modelo_id, cas, sustituciones)
        self.id, self.version = modelo_id, mz.PAQUETES[modelo_id].version
        self.referencia = dict(mz.REFERENCIA)
        self.especies = tuple(cas)
        self.M = self.sistema.M
        self.T_rango = self.sistema.T_rango
        self._cache = {}

    def estado(self, espec, a, b, n, semilla=None, certificar=False):
        s = self.sistema
        n = np.asarray(n, dtype=float)
        if semilla is not None:
            return s.flash_rapido(espec, a, b, n, semilla)       # incluye la prueba de estabilidad completa
        if espec == "TP":
            return s.equilibrio_TP(a, b, n)
        if espec == "PH":
            return s.equilibrio_PH(a, b, n)
        if espec == "UP":
            return s.equilibrio_UP(a, b, n)
        if espec == "UV":
            return s.equilibrio_UV(a, b, n)
        if espec == "TV":
            return s.equilibrio_TV(a, b, n)
        raise ValueError(espec)

    def certify_state(self, state):
        """Recheck a located state without solving its phase amounts again.

        Properties, chemical potentials, material reconstruction and the full
        stability search are evaluated afresh. Cached certificate values are
        never trusted. This keeps the exact limiting state rather than a second
        Newton solve whose rounding can erase an incipient phase.
        Phase selection remains upstream: no extra amount cutoff is applied.
        """
        system = self.sistema
        system.dominio(state.T, state.P)
        n = np.asarray(state.n, dtype=float)
        if tuple(state.especies) != tuple(system.cas) or not np.all(np.isfinite(n)) or np.any(n < 0) or not n.sum() > 0:
            raise mz.FueraDeAlcance('no_convergente', 'Invalid component inventory in the located state.')
        active = np.flatnonzero(n > 0).tolist()
        phases = []
        for phase in state.fases:
            x = np.asarray(phase.x, dtype=float)
            if (phase.tipo not in ('liquido', 'vapor') or not np.isfinite(phase.n) or phase.n <= 0
                    or x.shape != n.shape or not np.all(np.isfinite(x)) or np.any(x < 0)
                    or abs(x.sum() - 1.) > 1e-12 or np.any(x[n == 0] != 0) or np.any(x[active] <= 0)):
                raise mz.FueraDeAlcance('no_convergente', 'Invalid phase amount or composition in the located state.')
            phases.append((phase.tipo, phase.n * x[active]))
        if not phases:
            raise mz.FueraDeAlcance('no_convergente', 'The located state has no present phase.')
        result = system._empaquetar(state.especificacion, state.T, state.P, n, active, phases)
        reference = system._mu_comun(state.T, state.P, phases, active)
        trials = system.prueba_estabilidad(state.T, state.P, reference, active, incluir_vapor=True)
        minimum = min(trial[2] for trial in trials)
        result.verificaciones['equilibrio'] = (system._residuo_mu(result, active), mz.TOL_MU, 'Fresh chemical-potential equality at the located event state')
        result.verificaciones['estabilidad'] = (max(0., -minimum), mz.TOL_TM, 'Fresh full stability search at the located event state')
        result.estabilidad = {'tm_min': minimum, 'pruebas': len(trials), 'candidatas': sorted({trial[0] for trial in trials})}
        if not np.isfinite(minimum) or any(not np.isfinite(value[0]) or value[0] > value[1] for value in result.verificaciones.values()):
            raise mz.FueraDeAlcance('no_convergente', 'The located event state fails fresh thermodynamic certification.')
        return result

    def transporte_TP(self, T, P, x):
        clave = (T, P, tuple(np.round(np.asarray(x, dtype=float), 15)))
        if clave not in self._cache:
            e = self.sistema.equilibrio_TP(T, P, np.asarray(x, dtype=float))
            n = float(np.sum(e.n))
            self._cache[clave] = (e.H / n, e.S / n)
            if len(self._cache) > 5000:
                self._cache.clear()
        return self._cache[clave]


def crear(modelo, cas, sustituciones=None):
    if modelo == {"id": "agua-iapws95", "version": "1"}:
        if sustituciones:
            raise PaqueteNoAplicable("IAPWS-95 es una formulacion completa sin datos sustituibles.")
        return PaqueteAgua(cas)
    if modelo.get("id") in mz.PAQUETES and modelo.get("version") == mz.PAQUETES[modelo["id"]].version:
        return PaqueteMezcla(modelo["id"], cas, sustituciones)
    raise PaqueteNoAplicable(f"Modelo {modelo!r} no publicado.")
