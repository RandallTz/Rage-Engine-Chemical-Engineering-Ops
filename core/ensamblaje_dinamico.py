"""
Coordinador dinamico del motor independiente: un volumen de agua pura con
balances totales de materia y energia y cierre termodinamico IAPWS-95.

Este modulo recibe un problema ya validado y en SI (lo arma
backend/motor_ensamblaje.py a partir de la solicitud) y lo integra. No
conoce hojas, escenarios ni nombres de equipos: solo un volumen, su
frontera mecanica, corrientes con su donante y un calor.

Ecuaciones (flujos orientados por corriente; F > 0 en el sentido declarado
desde -> hasta; s = +1 si la corriente llega al volumen, -1 si sale):

    dm/dt = sum_j s_j F_j
    J_E   = sum_j s_j F_j h_j + Q,   h_j = h del DONANTE segun el signo de
            s_j F_j: exterior (T_ext, P_donante) si entra, el volumen (con
            su politica de extraccion) si sale
    rigido:            V = V_geom, dV/dt = 0,  dU/dt = J_E
                       (m, U) -> u = U/m, v = V/m -> cierre UV -> T, P, fases
    presion prescrita: P = P_ext(t) suave,  coordenada H = U + P V:
                       dH/dt = J_E + V dP/dt
                       (m, H) -> h = H/m -> cierre PH -> T, v, fases
                       V = m v,  U = H - P V (reconstruida, no integrada)

Derivacion de dH/dt: de dU/dt = J_E - P dV/dt y H = U + P V, dH/dt = dU/dt +
P dV/dt + V dP/dt = J_E + V dP/dt. Para comprobar la equivalencia se
integra ademas el trabajo de frontera W = int P dV/dt dt con la derivada
TOTAL de V = m v(h, P):

    dV/dt = v dm/dt + m [ (dv/dh)_P dh/dt + (dv/dP)_h dP/dt ],
    dh/dt = (dH/dt - h dm/dt) / m

con las derivadas de la EOS en una fase y las de la mezcla saturada en
coexistencia; y se publica |U - (U0 + int J_E dt - W)|. Nada de esto usa
dm/dt / rho constante.

Integracion: Dormand-Prince 5(4) (scipy RK45) con tolerancias separadas
por magnitud (masa, energia), paso maximo = intervalo de muestreo, y:

  * eventos de fase: se vigila el conjunto de fases en CADA etapa
    evaluada; si cambia dentro de un paso, se localiza el instante por
    biseccion sobre la salida densa, se re-integra hasta ese instante y se
    reinicia el integrador alli (las propiedades tienen una arista en la
    frontera de saturacion);
  * fallo de flash en una etapa: no se reutilizan propiedades anteriores;
    se repite el paso desde el ultimo estado aceptado con paso menor, y si
    el paso cae por debajo de h_min se detiene con el evento de salida de
    dominio (o agotamiento si la masa se anula);
  * cada muestra publicada se certifica con el flash completo (barrido
    global y estabilidad), via el servicio puntual local.

Las evaluaciones internas de las etapas usan los flashes sin barrido ni
certificacion (core/agua_iapws95.py, certificar=False): la semilla de T solo
acelera la busqueda; la unicidad la garantiza la monotonia de u o h.
"""

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.integrate import RK45

from core import agua_iapws95 as agua


@dataclass
class Funcion:
    """Dato en SI como funcion de t [s]: valor = f(t)*factor + desplazamiento."""
    f: object               # callable t -> valor declarado
    df: object | None       # callable t -> derivada del valor declarado, o None
    factor: float
    desplazamiento: float
    constante: bool

    def __call__(self, t):
        return self.f(t) * self.factor + self.desplazamiento

    def derivada(self, t):
        return 0.0 if self.constante else self.df(t) * self.factor


@dataclass
class CorrienteSI:
    id: int
    signo: int                      # +1 llega al volumen, -1 sale de el
    F: Funcion                      # caudal masico [kg/s] en el sentido declarado
    T_ext: Funcion | None = None    # donante exterior
    P_ext: Funcion | None = None
    continuidad: bool = False       # P del donante = P del volumen (ecuacion)
    extraccion: tuple = ("mezcla_homogenea", None)


@dataclass
class Problema:
    frontera: str                   # 'rigida' | 'presion'
    V: float | None
    P: Funcion | None
    Q: Funcion | None
    corrientes: list
    m0: float
    energia0: tuple                 # ('U', U0 J) | ('T', T0 K)
    tf: float
    muestras: int
    rtol: float
    atol_m: float
    atol_E: float
    politica: dict
    certificar: object = None       # callable(t, m, E) -> evaluacion certificada (inyectado por el backend)
    id_volumen: str = "dominio"
    id_componente: int = 1


class Detencion(Exception):
    def __init__(self, codigo, mensaje, t=None):
        super().__init__(mensaje)
        self.codigo, self.mensaje, self.t = codigo, mensaje, t


# ----------------------------------------------------------------------
# Estado del volumen y donantes
# ----------------------------------------------------------------------
@dataclass
class EstadoVolumen:
    T: float
    P: float
    V: float
    m: float
    u: float
    h: float
    v: float
    fases: tuple            # FaseCalculada
    firma: tuple            # tipos de fase presentes (para eventos)
    q: float                # fraccion masica de vapor (0 si no hay)
    nucleo: object          # EstadoEquilibrio


def estado_volumen(prob, t, m, E, semilla=None, certificar=False):
    if not m > 0:
        raise agua.FueraDeAlcance("agotamiento", f"La masa del volumen llega a {m:.6g} kg: no hay estado intensivo.")
    if prob.frontera == "rigida":
        e = agua.evaluar_UV(E / m, prob.V / m, T_semilla=semilla, certificar=certificar)
        V = prob.V
    else:
        e = agua.evaluar_PH(prob.P(t), E / m, certificar=certificar, T_semilla=semilla)
        V = m * e.v
    tipos = tuple(sorted(f.tipo for f in e.fases))
    q = sum(f.fraccion for f in e.fases if f.tipo == "vapor")     # misma definicion que el backend
    return EstadoVolumen(T=e.T, P=e.P, V=V, m=m, u=e.u, h=e.h, v=e.v, fases=e.fases,
                         firma=(len(e.fases),) + tipos, q=q, nucleo=e)


_CACHE_TP = {}


def h_TP(T, P):
    """h del donante exterior a (T, P): misma rama y comprobaciones que el TP
    de H1 (dominio, banda critica, saturacion indeterminada); la TPD completa
    se certifica en las muestras."""
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


def h_extraccion(c, ev):
    tipo, fase = c.extraccion
    if tipo == "mezcla_homogenea":
        return ev.h
    for f in ev.fases:
        if f.tipo == fase:
            return f.propiedades.h
    raise Detencion("fase_ausente",
                    f"La corriente {c.id} extrae la fase {fase}, ausente en el volumen (fases: "
                    f"{', '.join(f.tipo for f in ev.fases)}).")


def flujos(prob, t, ev):
    """[(corriente, tasa masica hacia el volumen, h donante, origen)]."""
    salida = []
    for c in prob.corrientes:
        tasa = c.signo * c.F(t)
        if tasa > 0:
            P_d = ev.P if c.continuidad else c.P_ext(t)
            salida.append((c, tasa, h_TP(c.T_ext(t), P_d), "exterior"))
        elif tasa < 0:
            salida.append((c, tasa, h_extraccion(c, ev), "volumen"))
        else:
            salida.append((c, 0.0, 0.0, "nulo"))
    return salida


def dv_derivadas(prob, t, ev):
    """((dv/dh)_P, (dv/dP)_h) del estado del volumen a presion prescrita."""
    e = ev.nucleo
    if e.coexistencia is None or len(e.fases) == 1 and not e.frontera:
        p = e.fases[0].propiedades
        dvdT_P = p.dP_dT_rho / (p.rho ** 2 * p.dP_drho_T)
        dvdP_T = -1.0 / (p.rho ** 2 * p.dP_drho_T)
        dhdP_T = p.v - p.T * dvdT_P
        return dvdT_P / p.cp, dvdP_T - dvdT_P * dhdP_T / p.cp
    c = e.coexistencia
    dv_dh = (c.vapor.v - c.liquido.v) / (c.vapor.h - c.liquido.h)
    if prob.P.constante:
        return dv_dh, 0.0
    dP = 1e-6 * ev.P
    vm = agua.evaluar_PH(ev.P + dP, ev.h, certificar=False).v
    vn = agua.evaluar_PH(ev.P - dP, ev.h, certificar=False).v
    return dv_dh, (vm - vn) / (2 * dP)


# ----------------------------------------------------------------------
# Lado derecho
# ----------------------------------------------------------------------
class Sistema:
    """y = [m, E, E_in, W]: E = U (rigida) o H (presion); E_in = int J_E dt;
    W = int P dV/dt dt (solo presion prescrita)."""

    def __init__(self, prob):
        self.prob = prob
        self.semilla = None
        self.firmas = []
        self.vigilar = True

    def estado(self, t, y, certificar=False):
        return estado_volumen(self.prob, t, y[0], y[1], self.semilla, certificar)

    def __call__(self, t, y):
        prob = self.prob
        ev = self.estado(t, y)
        self.semilla = ev.T
        if self.vigilar:
            self.firmas.append(ev.firma)
        fl = flujos(prob, t, ev)
        dm = sum(tasa for _, tasa, _, _ in fl)
        JE = sum(tasa * h for _, tasa, h, _ in fl) + (prob.Q(t) if prob.Q is not None else 0.0)
        if prob.frontera == "rigida":
            return np.array([dm, JE, JE, 0.0])
        dP = prob.P.derivada(t)
        dH = JE + ev.V * dP
        dh = (dH - ev.h * dm) / ev.m
        vh, vP = dv_derivadas(prob, t, ev)
        dV = ev.v * dm + ev.m * (vh * dh + vP * dP)
        return np.array([dm, dH, JE, ev.P * dV])


# ----------------------------------------------------------------------
# Integracion con eventos
# ----------------------------------------------------------------------
@dataclass
class Tramo:
    t0: float
    t1: float
    interp: object          # salida densa del paso, o None para un punto


@dataclass
class Trayectoria:
    tramos: list = field(default_factory=list)
    eventos: list = field(default_factory=list)      # (codigo, t, mensaje)
    t_fin: float = 0.0
    y_fin: object = None
    detenida: Detencion | None = None
    pasos: int = 0
    rechazos_dominio: int = 0
    evaluaciones: int = 0

    def y(self, t):
        for tr in self.tramos:
            if tr.t0 <= t <= tr.t1 and tr.interp is not None:
                return tr.interp(t)
        if abs(t - self.t_fin) <= 1e-12 * max(1.0, abs(t)):
            return self.y_fin
        raise ValueError(f"t = {t} fuera de la trayectoria integrada")


def _prohibido(prob, firma_ini, firma):
    """Motivo si el cambio de fases viola la politica, o None."""
    pol = prob.politica
    if pol.get("cambioInterno") == "prohibido":
        return "cambioInterno: prohibido y el conjunto de fases cambia durante la trayectoria"
    if pol.get("cantidad") == "monofasico" and firma[0] > 1:
        return "politica monofasica y aparece una segunda fase"
    permitidos = pol.get("tiposPermitidos")
    if permitidos is not None and any(tp not in permitidos for tp in firma[1:]):
        return f"aparece una fase fuera de tiposPermitidos ({', '.join(permitidos)})"
    return None


def integrar(prob, y0, T0):
    sis = Sistema(prob)
    sis.semilla = T0
    tray = Trayectoria()
    atol = np.array([prob.atol_m, prob.atol_E, prob.atol_E, prob.atol_E])
    h_max = prob.tf / max(prob.muestras - 1, 1)
    h_min = 1e-10 * prob.tf
    t, y = 0.0, np.array(y0, dtype=float)
    ev0 = sis.estado(t, y)
    firma = ev0.firma
    firma_ini = firma
    paso_max = h_max
    try:
        h_extraccion_todas(prob, 0.0, ev0)       # la relacion de transporte debe cumplirse ya en t = 0
    except Detencion as x:
        x.t = 0.0
        tray.detenida = x
        tray.eventos.append((x.codigo, 0.0, x.mensaje))
        tray.t_fin, tray.y_fin = 0.0, y
        return tray
    while t < prob.tf:
        try:
            solver = RK45(sis, t, y, prob.tf, rtol=prob.rtol, atol=atol, max_step=paso_max,
                          first_step=min(paso_max, prob.tf - t))
        except (agua.FueraDeAlcance, Detencion) as x:
            codigo = x.codigo if isinstance(x, Detencion) else (
                "agotamiento" if x.motivo == "agotamiento" else
                "donante_en_saturacion" if x.motivo == "saturacion" else "salida_dominio")
            tray.detenida = Detencion(codigo, getattr(x, "mensaje", str(x)), t)
            tray.eventos.append((codigo, t, tray.detenida.mensaje))
            tray.t_fin, tray.y_fin = t, y
            return tray
        reiniciar = False
        while solver.status == "running":
            t_a, y_a, semilla_a = solver.t, solver.y.copy(), sis.semilla
            sis.firmas = []
            try:
                solver.step()
            except (agua.FueraDeAlcance, Detencion) as x:
                # fallo en una etapa: no se reutiliza nada; paso menor desde el ultimo aceptado
                tray.rechazos_dominio += 1
                t, y, sis.semilla = t_a, y_a, semilla_a
                paso_max = (solver.step_size or paso_max) / 4 if solver.step_size else paso_max / 4
                if paso_max < h_min:
                    motivo = getattr(x, "motivo", "")
                    codigo = (x.codigo if isinstance(x, Detencion) else
                              "agotamiento" if motivo == "agotamiento" else
                              "donante_en_saturacion" if motivo == "saturacion" else "salida_dominio")
                    tray.detenida = Detencion(codigo, x.mensaje if hasattr(x, "mensaje") else str(x), t_a)
                    tray.eventos.append((codigo, t_a, tray.detenida.mensaje))
                    tray.t_fin, tray.y_fin = t_a, y_a
                    return tray
                reiniciar = True
                break
            if solver.status == "failed":
                tray.detenida = Detencion("no_convergente", "El integrador no pudo avanzar.", t_a)
                tray.t_fin, tray.y_fin = t_a, y_a
                return tray
            tray.pasos += 1
            interp = solver.dense_output()
            t_b, y_b = solver.t, solver.y.copy()
            # Vigilancia de fases sobre el paso ACEPTADO: tres puntos interiores de
            # la salida densa y el extremo (las etapas de intentos rechazados no
            # pertenecen a la trayectoria). El paso no supera el intervalo de muestreo.
            firmas = set()
            for tm in [t_a + (t_b - t_a) * k / 4 for k in (1, 2, 3)] + [t_b]:
                try:
                    firmas.add(sis.estado(tm, interp(tm) if tm < t_b else y_b).firma)
                except agua.FueraDeAlcance:
                    firmas.add(None)
            sis.semilla = semilla_a if None in firmas else sis.semilla
            if firmas != {firma}:
                # cambio de fases en el paso: localizar, re-integrar hasta alli y reiniciar
                lo, hi = t_a, t_b
                while hi - lo > max(1e-9 * prob.tf, 1e-12):
                    mid = 0.5 * (lo + hi)
                    try:
                        f_mid = sis.estado(mid, interp(mid)).firma
                    except agua.FueraDeAlcance:
                        f_mid = None
                    if f_mid == firma:
                        lo = mid
                    else:
                        hi = mid
                t_e = hi
                sis.vigilar, sis.semilla = False, semilla_a
                sub = (RK45(sis, t_a, y_a, t_e, rtol=prob.rtol, atol=atol, max_step=paso_max,
                            first_step=min(t_e - t_a, paso_max)) if t_e > t_a else None)
                while sub is not None and sub.status == "running":
                    s_a = sub.t
                    try:
                        sub.step()
                    except (agua.FueraDeAlcance, Detencion):
                        sub = None
                        break
                    tray.tramos.append(Tramo(s_a, sub.t, sub.dense_output()))
                sis.vigilar = True
                if sub is None:     # borde en el inicio del paso, o no se llega a el
                    t_e = t_a
                    y_e = y_a
                else:
                    y_e = sub.y.copy()
                try:
                    nueva = sis.estado(t_e, y_e).firma
                except agua.FueraDeAlcance as x:
                    tray.detenida = Detencion("salida_dominio", x.mensaje, t_e)
                    tray.eventos.append(("salida_dominio", t_e, x.mensaje))
                    tray.t_fin, tray.y_fin = t_e, y_e
                    return tray
                codigo = ("aparicion_fase" if nueva[0] > firma[0] else
                          "desaparicion_fase" if nueva[0] < firma[0] else "cambio_denominacion")
                if codigo == "cambio_denominacion":
                    # liquido <-> fluido <-> vapor sin coexistencia: no hay fase nueva ni
                    # transicion de primer orden; solo tiposPermitidos puede prohibirlo.
                    permitidos = prob.politica.get("tiposPermitidos")
                    motivo = (f"aparece el tipo {nueva[1:]} fuera de tiposPermitidos" if permitidos
                              and any(tp not in permitidos for tp in nueva[1:]) else None)
                else:
                    motivo = _prohibido(prob, firma_ini, nueva)
                tray.eventos.append((codigo, t_e, f"fases {firma[1:]} -> {nueva[1:]}"))
                if motivo:
                    tray.detenida = Detencion("cambio_fase_prohibido", motivo, t_e)
                    tray.t_fin, tray.y_fin = t_e, y_e
                    return tray
                try:
                    sis.estado(t_e, y_e)
                    h_extraccion_todas(prob, t_e, sis.estado(t_e, y_e))
                except Detencion as x:
                    tray.detenida = x
                    x.t = t_e
                    tray.eventos.append((x.codigo, t_e, x.mensaje))
                    tray.t_fin, tray.y_fin = t_e, y_e
                    return tray
                t, y, firma = t_e, y_e, nueva
                tray.tramos.append(Tramo(t_e, t_e, None))
                reiniciar = True
                break
            tray.tramos.append(Tramo(t_a, t_b, interp))
            t, y = t_b, y_b
            paso_max = h_max
        if not reiniciar:
            break
    tray.t_fin, tray.y_fin = t, y
    tray.evaluaciones = 0
    return tray


def h_extraccion_todas(prob, t, ev):
    """Comprueba que toda corriente que extrae en t encuentra su fase."""
    for c in prob.corrientes:
        if c.signo * c.F(t) < 0:
            h_extraccion(c, ev)


def muestras(prob, tray):
    """Tiempos de muestreo (uniformes en [0, tf], recortados a lo integrado,
    mas el instante de cada evento y el de detencion) y sus y."""
    n = prob.muestras
    ts = [prob.tf * k / (n - 1) for k in range(n)]
    ts = [t for t in ts if t <= tray.t_fin * (1 + 1e-15)]
    for _, t_e, _ in tray.eventos:
        if t_e <= tray.t_fin and all(abs(t_e - t) > 1e-12 * prob.tf for t in ts):
            ts.append(t_e)
    if tray.detenida is not None and all(abs(tray.t_fin - t) > 1e-12 * prob.tf for t in ts):
        ts.append(tray.t_fin)
    ts.sort()
    return [(t, np.array(tray.y(min(t, tray.t_fin)), dtype=float)) for t in ts]
