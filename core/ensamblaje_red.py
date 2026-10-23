"""
Coordinador dinamico de varios volumenes (revision 2 del ensamblaje).

Estado: por volumen v, cantidades n_vi [mol] de sus componentes y su energia
E_v (U_v si es rigido, H_v = U_v + P V_v si tiene presion prescrita). Todo en
SI y base molar. Ecuaciones (B_vs = +1 si la corriente s llega a v, -1 si
sale; flujo positivo en el sentido desde -> hasta):

    dn_vi/dt = sum_s B_vs ndot_s x_si
    dU_v/dt  = sum_s B_vs ndot_s h_s + sum_q B_vq Qdot_q - P_v dV_v/dt
    rigido:   dV/dt = 0                    -> cierre UV del paquete
    presion:  dH_v/dt = J_E,v + V_v dP_v/dt -> cierre PH del paquete

    donante de s: el extremo de origen segun el signo ACTUAL del flujo.
      volumen: composicion y h de la mezcla o de la fase extraida
      exterior: composicion declarada y h del equilibrio a (T_ext, P_donante)
                con el paquete del volumen receptor (misma referencia)

Cancelacion interna por identidad: la tasa de una corriente interna se
calcula UNA vez y se suma en un extremo y se resta en el otro (mismo numero
en coma flotante). Igual para un contacto termico interno.

Integrales auxiliares (y[k] despues de los estados):
  por componente global: materia exterior neta;  energia exterior neta
  (corrientes + calor con el exterior); W_v = int P_v dV_v/dt dt por volumen;
  flujo de entropia exterior int (sum ndot s + Q/T_frontera) dt.

Eventos, reintentos y muestras como core/ensamblaje_dinamico.py (v1):
vigilancia del conjunto de fases de cada volumen en 3 puntos interiores y el
extremo de cada paso aceptado, biseccion, re-integracion hasta el evento y
reinicio; un flash que falla no reutiliza propiedades anteriores. Si el estado
reintegrado no muestra el cambio que la biseccion localizo, el evento se toma
con el estado del interpolante en ese instante (nunca se acepta el paso sin
evento a traves de una transicion localizada; corregido el 18-10-2026).
"""

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.integrate import RK45

from core import mezclas as mz
from core.ensamblaje_dinamico import Funcion, Detencion


@dataclass
class VolumenSI:
    id: str
    paquete: object
    comp: list                  # indices globales de sus componentes
    frontera: str               # 'rigida' | 'presion'
    V: float | None
    P: Funcion | None
    politica: dict
    n0: np.ndarray
    E0: float
    T0: float


@dataclass
class CorrienteRed:
    id: str
    desde: int | None
    hasta: int | None
    comp: list                  # indices globales
    modo: str                   # 'total' | 'por_componente'
    base: str                   # 'masica' | 'molar'
    F: Funcion | None           # total (modo total)
    Fc: dict | None             # comp global -> Funcion (modo por_componente)
    T_ext: Funcion | None = None
    P_ext: Funcion | None = None
    continuidad: int | None = None      # volumen cuya P toma el donante exterior
    x_ext: np.ndarray | None = None     # composicion molar exterior (global)
    extraccion: dict = field(default_factory=dict)   # vol -> ('mezcla_homogenea'|'fase', tipo, criterio)


@dataclass
class IntercambioRed:
    id: str
    desde: int | None
    hasta: int | None
    ley: str                    # 'impuesto' | 'conductancia'
    Q: Funcion | None = None
    G: float | None = None
    T_ext: Funcion | None = None
    T_frontera: Funcion | None = None


@dataclass
class Red:
    volumenes: list
    corrientes: list
    intercambios: list
    M: np.ndarray               # kg/mol por componente global
    tf: float
    muestras: int
    rtol: float
    atol_n: float
    atol_E: float


# ----------------------------------------------------------------------
class Sistema:
    def __init__(self, red):
        self.red = red
        nv = len(red.volumenes)
        self.offs = []
        k = 0
        for v in red.volumenes:
            self.offs.append(k)
            k += len(v.comp) + 1
        self.n_estados = k
        self.nc = len(red.M)
        # auxiliares: materia exterior (nc), energia exterior (1), W por volumen (nv), entropia exterior (1)
        self.i_mat = k
        self.i_E = k + self.nc
        self.i_W = self.i_E + 1
        self.i_VdP = self.i_W + nv      # int V dP/dt dt por volumen (W por partes: [PV] - int V dP)
        self.i_S = self.i_VdP + nv
        self.n_total = self.i_S + 1
        self.semillas = [None] * nv
        self.semillas_ok = [None] * nv
        self.firmas_tramo = None        # conjunto de fases del tramo que se integra (lo fija el coordinador)
        self.segunda_ley_evaluable = all(
            q.T_frontera is not None or (q.ley == "conductancia" and q.T_ext is not None)
            for q in red.intercambios if q.desde is None or q.hasta is None)

    def n_E(self, y, j):
        o = self.offs[j]
        m = len(self.red.volumenes[j].comp)
        return y[o:o + m], y[o + m]

    def estado_vol(self, t, y, j, certificar=False, semilla="auto"):
        v = self.red.volumenes[j]
        n, E = self.n_E(y, j)
        if np.any(n < 0) or not n.sum() > 0:
            raise mz.FueraDeAlcance("agotamiento", f"El volumen {v.id} se queda sin materia (n = {n}).")
        sem = self.semillas[j] if semilla == "auto" else semilla
        if v.frontera == "rigida":
            return v.paquete.estado("UV", E, v.V, n, semilla=sem, certificar=certificar)
        return v.paquete.estado("PH", v.P(t), E, n, semilla=sem, certificar=certificar)

    def estados(self, t, y, certificar=False):
        return [self.estado_vol(t, y, j, certificar) for j in range(len(self.red.volumenes))]

    # --- transporte -------------------------------------------------------------
    def _extraer(self, c, j, ev):
        """(x global, h, s, M_mix) molares de lo que sale del volumen j."""
        v = self.red.volumenes[j]
        tipo, fase, criterio = c.extraccion.get(j, ("mezcla_homogenea", None, None))
        if tipo == "mezcla_homogenea":
            N = float(np.sum(ev.n))
            x_loc, h, s = ev.n / N, ev.H / N, ev.S / N
        else:
            cand = [f for f in ev.fases if f.tipo == fase]
            if not cand:
                raise Detencion("fase_ausente", f"La corriente {c.id} extrae {fase} del volumen {v.id}, donde no está "
                                f"(fases: {', '.join(f.id for f in ev.fases)}).")
            if len(cand) > 1:
                if criterio is None:
                    raise Detencion("fase_ambigua", f"La corriente {c.id} extrae «{fase}» del volumen {v.id} y hay "
                                    f"{len(cand)} fases de ese tipo: hace falta un criterio (mayor_densidad o "
                                    "menor_densidad).")
                dens = [f.M / f.v for f in cand]
                k = int(np.argmax(dens)) if criterio == "mayor_densidad" else int(np.argmin(dens))
                cand = [cand[k]]
            f = cand[0]
            x_loc, h, s = f.x, f.h, f.s
        x = np.zeros(len(self.red.M))
        x[v.comp] = x_loc
        return x, h, s

    def flujos(self, t, y, evs):
        """[(c, ndot >= 0 en el sentido real, origen (j|None), destino (j|None), x, h, s)]"""
        red = self.red
        sal = []
        for c in red.corrientes:
            if c.modo == "total":
                F = c.F(t)
                signo = 1 if F > 0 else -1 if F < 0 else 0
            else:
                Fs = np.array([c.Fc[i](t) for i in c.comp])
                signo = 1 if np.all(Fs > 0) else -1 if np.all(Fs < 0) else 0
                if signo == 0 and np.any(Fs != 0):
                    raise Detencion("flujos_opuestos", f"La corriente {c.id} tiene caudales por componente de signos "
                                    "opuestos; eso es una transferencia selectiva sin ley energética.")
            if signo == 0:
                sal.append((c, 0.0, None, None, None, 0.0, 0.0))
                continue
            origen, destino = (c.desde, c.hasta) if signo > 0 else (c.hasta, c.desde)
            if origen is not None:
                x, h, s = self._extraer(c, origen, evs[origen])
                M = float(np.sum(x * red.M))
                ndot = abs(F) / M if c.modo == "total" and c.base == "masica" else abs(F) if c.modo == "total" else None
                if ndot is None:      # por_componente desde un volumen de un componente
                    nd = np.abs(Fs) / (red.M[c.comp] if c.base == "masica" else 1.0)
                    ndot = float(nd.sum())
            else:
                # donante exterior
                if c.modo == "total":
                    x = c.x_ext
                    M = float(np.sum(x * red.M))
                    ndot = abs(F) / M if c.base == "masica" else abs(F)
                else:
                    nd = np.abs(Fs) / (red.M[c.comp] if c.base == "masica" else 1.0)
                    ndot = float(nd.sum())
                    x = np.zeros(len(red.M))
                    x[c.comp] = nd / ndot
                vj = destino
                vol = red.volumenes[vj]
                P_d = evs[c.continuidad].P if c.continuidad is not None else c.P_ext(t)
                h, s = vol.paquete.transporte_TP(c.T_ext(t), P_d, x[vol.comp])
            sal.append((c, ndot, origen, destino, x, h, s))
        return sal

    def calores(self, t, evs):
        sal = []
        for q in self.red.intercambios:
            if q.ley == "impuesto":
                Q = q.Q(t)
            else:
                Ta = evs[q.desde].T if q.desde is not None else q.T_ext(t)
                Tb = evs[q.hasta].T if q.hasta is not None else q.T_ext(t)
                Q = q.G * (Ta - Tb)
            sal.append((q, Q))
        return sal

    # --- lado derecho ------------------------------------------------------------
    def __call__(self, t, y):
        red = self.red
        evs = []
        for j in range(len(red.volumenes)):
            ev = self.estado_vol(t, y, j)
            self.semillas[j] = ev
            evs.append(ev)
        dy = np.zeros(self.n_total)
        J = np.zeros(len(red.volumenes))
        for c, ndot, o, d, x, h, s in self.flujos(t, y, evs):
            if ndot == 0.0:
                continue
            tasa = ndot * x                 # mol/s por componente global; UNA vez para ambos extremos
            Edot = ndot * h
            for j, sg in ((o, -1.0), (d, +1.0)):
                if j is None:
                    continue
                vol = red.volumenes[j]
                o_ = self.offs[j]
                dy[o_:o_ + len(vol.comp)] += sg * tasa[vol.comp]
                J[j] += sg * Edot
            if o is None:                   # entra desde el exterior
                dy[self.i_mat:self.i_mat + self.nc] += tasa
                dy[self.i_E] += Edot
                dy[self.i_S] += ndot * s
            if d is None:                   # sale al exterior
                dy[self.i_mat:self.i_mat + self.nc] -= tasa
                dy[self.i_E] -= Edot
                dy[self.i_S] -= ndot * s
        for q, Q in self.calores(t, evs):
            if q.desde is not None:
                J[q.desde] -= Q
            if q.hasta is not None:
                J[q.hasta] += Q
            if q.desde is None or q.hasta is None:
                Q_in = Q if q.desde is None else -Q
                dy[self.i_E] += Q_in
                Tf = q.T_frontera(t) if q.T_frontera is not None else (q.T_ext(t) if q.T_ext is not None else None)
                if Tf is not None:
                    dy[self.i_S] += Q_in / Tf
        for j, vol in enumerate(red.volumenes):
            o_ = self.offs[j]
            m = len(vol.comp)
            if vol.frontera == "rigida":
                dy[o_ + m] = J[j]
            else:
                ev = evs[j]
                dP = vol.P.derivada(t)
                dy[o_ + m] = J[j] + ev.V * dP
                dy[self.i_VdP + j] = ev.V * dP
                dy[self.i_W + j] = ev.P * self._dVdt(t, y, j, dy[o_:o_ + m], dy[o_ + m], dP, ev)
        return dy

    def _dVdt(self, t, y, j, dn, dH, dP, ev):
        """Derivada total de V = V(H, P, n) por diferencia centrada a lo largo de las tasas."""
        vol = self.red.volumenes[j]
        n, H = self.n_E(y, j)
        # Escala del paso: cada especie respecto de su cantidad; una especie con cantidad exactamente cero
        # (entra por una corriente) respecto del total del volumen. Antes se dividia por 1e-30 y el paso
        # quedaba en ~1e-33: la diferencia de V se perdia en el redondeo.
        ref = np.where(n > 0, n, n.sum())
        escala = max(np.max(np.abs(dn) / ref) if np.any(dn) else 0.0,
                     abs(dH) / max(abs(H), mz.R * ev.T * n.sum()), abs(dP) / ev.P, 1e-12)
        eps = 1e-6 / escala
        P = vol.P(t)

        def est_en(k):
            return vol.paquete.estado("PH", P + dP * eps * k, H + dH * eps * k, n + dn * eps * k, semilla=ev)

        def V_en(k):
            return est_en(k).V
        if np.any(n - dn * eps < 0):
            # el paso hacia atras daria una cantidad negativa: diferencia de tres puntos hacia delante
            # (segundo orden, como la centrada)
            return (-3.0 * ev.V + 4.0 * V_en(1) - V_en(2)) / (2 * eps)
        try:
            em, en_ = est_en(1), est_en(-1)
        except mz.FueraDeAlcance:
            return (-3.0 * ev.V + 4.0 * V_en(1) - V_en(2)) / (2 * eps)
        # A menos de eps de una arista de cambio de fase V(H, P, n) tiene un quiebre: la diferencia centrada
        # atribuiria al conjunto actual parte de la derivada del otro (el liquido incompresible "se expandia"
        # con el vapor del punto adelantado). Se usa la diferencia de tres puntos del lado que conserva el
        # conjunto de fases del TRAMO que se integra (el de la ultima etapa del subintegrado hasta t_e ya
        # contiene la fase naciente con ~1e-10 mol, pero el tramo integra el conjunto anterior). Al cruzar la
        # arista el error se compensaba entre ambos lados, pero no en una trayectoria que se detiene en ella
        # (politica monofasica o cambio de fase prohibido).
        f0 = self.firmas_tramo[j] if self.firmas_tramo is not None else firma(ev)
        if firma(em) != f0 or firma(en_) != f0 or firma(ev) != f0:
            for k, e1 in ((-1, en_), (1, em)):
                if firma(e1) != f0 or (k < 0 and np.any(n - 2 * dn * eps < 0)):
                    continue
                try:
                    e2 = est_en(2 * k)
                except mz.FueraDeAlcance:
                    continue
                if firma(e2) == f0:
                    # ev puede estar ya del otro lado (fase naciente ~1e-10 mol): su V es continuo en la arista
                    return k * (-3.0 * ev.V + 4.0 * e1.V - e2.V) / (2 * eps)
        return (em.V - en_.V) / (2 * eps)


# ----------------------------------------------------------------------
# Resolucion relativa (a tf) con que se localiza un cambio del conjunto de fases (ver integrar).
RES_EVENTO = 1e-12
# Phase-stability margins limit the step (F0-5). The signature is only checked at the quarter points of a
# step, so a phase window shorter than that spacing was skipped. Each margin is a distance to a phase-set
# change: the appearance margin tm_nueva (smallest tm of a trial phase that is not present) and the smallest
# phase fraction. A margin may fall by at most MARGEN_CAIDA between consecutive checks; otherwise the step is
# redone shorter. Margins below MARGEN_MIN are left to the bisection: a window whose margin dips by less than
# about MARGEN_MIN can still be missed (declared resolution).
MARGEN_CAIDA = 0.5
MARGEN_MIN = 1e-8
H_MARGEN_MIN = 1e-8          # relative to tf: the shortest step the margin rule asks for


def firma(ev):
    return (len(ev.fases),) + tuple(sorted(f.tipo for f in ev.fases))


def margenes(ev):
    """(appearance margin, smallest phase fraction) of a state; None where not available or not positive."""
    est = getattr(ev, "estabilidad", None)
    tm = est.get("tm_nueva") if isinstance(est, dict) else None
    tm = float(tm) if tm is not None and math.isfinite(tm) and tm > 0 else None
    beta = None
    if len(ev.fases) > 1:
        cantidades = [f.n for f in ev.fases]
        beta = min(cantidades) / sum(cantidades)
    return tm, beta


def _margen_cae(serie):
    """True when a margin above MARGEN_MIN falls below MARGEN_CAIDA times itself between two checks."""
    for previo, actual in zip(serie, serie[1:]):
        for mp, ma in zip(previo, actual):
            for a, b in zip(mp, ma):
                if a is not None and b is not None and a > MARGEN_MIN and b < MARGEN_CAIDA * a:
                    return True
    return False


def _paso_por_margen(t3, fila3, t4, fila4, h_max, h_min):
    """Largest next step whose quarter spacing keeps each falling margin within MARGEN_CAIDA (linear trend)."""
    paso = h_max
    for mp, ma in zip(fila3, fila4):
        for a, b in zip(mp, ma):
            if a is not None and b is not None and MARGEN_MIN < b < a:
                distancia = b * (t4 - t3) / (a - b)
                paso = min(paso, 4 * (1 - MARGEN_CAIDA) * distancia * 0.75)
    return max(paso, h_min)


def clasificar_evento(antes, despues):
    """Codigo del cambio de conjunto de fases entre dos firmas (n, tipos ordenados).
    cambio_denominacion SOLO cuando el unico cambio es vapor/liquido <-> fluido (regimen supercritico):
    propiedades continuas, no es una transicion de primer orden. Con el mismo numero de fases y otro cambio
    de tipos (p. ej. liquido+liquido -> liquido+vapor) una fase desaparece y otra aparece: sustitucion_fase."""
    if despues[0] > antes[0]:
        return "aparicion_fase"
    if despues[0] < antes[0]:
        return "desaparicion_fase"
    a, d = list(antes[1:]), list(despues[1:])
    for t in list(a):
        if t in d:
            a.remove(t)
            d.remove(t)
    pares = list(zip(sorted(a), sorted(d)))
    if a and all("fluido" in par and set(par) <= {"fluido", "vapor", "liquido"} for par in pares):
        return "cambio_denominacion"
    return "sustitucion_fase"


def _prohibido(pol, nueva):
    if pol.get("cambioInterno") == "prohibido":
        return "cambioInterno: prohibido y el conjunto de fases cambia"
    if pol.get("cantidad") == "monofasico" and nueva[0] > 1:
        return "política monofásica y aparece otra fase"
    tp = pol.get("tiposPermitidos")
    if tp is not None and any(x not in tp for x in nueva[1:]):
        return f"aparece una fase fuera de tiposPermitidos ({', '.join(tp)})"
    return None


@dataclass
class Tramo:
    t0: float
    t1: float
    interp: object


@dataclass
class Trayectoria:
    tramos: list = field(default_factory=list)
    eventos: list = field(default_factory=list)      # (codigo, t, volumen_idx|None, mensaje)
    t_fin: float = 0.0
    y_fin: object = None
    detenida: Detencion | None = None
    pasos: int = 0
    reintentos: int = 0
    # Frozen numerical context of located phase events. Publication must start
    # from the state used to locate the event, rather than an unrelated sample.
    phase_event_states: dict = field(default_factory=dict)

    def y(self, t):
        if t == self.t_fin and self.y_fin is not None:
            return self.y_fin
        for tr in self.tramos:
            if tr.t0 <= t <= tr.t1 and tr.interp is not None:
                return tr.interp(t)
        if abs(t - self.t_fin) <= 1e-12 * max(1.0, abs(t)):
            return self.y_fin
        raise ValueError(f"t = {t} fuera de lo integrado")


def _codigo(x):
    if isinstance(x, Detencion):
        return x.codigo
    m = getattr(x, "motivo", "")
    if getattr(x, "datos", {}).get("tope_fases"):
        return "tope_fases"
    return {"agotamiento": "agotamiento", "saturacion": "donante_en_saturacion"}.get(m, "salida_dominio")


def integrar(red, y0):
    sis = Sistema(red)
    tray = Trayectoria()
    nv = len(red.volumenes)
    atol = np.full(sis.n_total, red.atol_E)
    for j, v in enumerate(red.volumenes):
        atol[sis.offs[j]:sis.offs[j] + len(v.comp)] = red.atol_n
    atol[sis.i_mat:sis.i_mat + sis.nc] = red.atol_n
    h_max = red.tf / max(red.muestras - 1, 1)
    h_min = 1e-10 * red.tf
    t, y = 0.0, np.array(y0, dtype=float)
    evs = sis.estados(t, y)
    sis.semillas = list(evs)
    firmas = [firma(e) for e in evs]
    marg_a = [margenes(e) for e in evs]      # margins of the state at the start of the current step
    h_margen = max(H_MARGEN_MIN * red.tf, h_min)
    sis.firmas_tramo = firmas           # la misma lista: se actualiza en cada evento
    try:
        sis.flujos(0.0, y, evs)
    except (Detencion, mz.FueraDeAlcance) as x:
        tray.detenida = x if isinstance(x, Detencion) else Detencion(_codigo(x), x.mensaje, 0.0)
        tray.detenida.t = 0.0
        tray.eventos.append((tray.detenida.codigo, 0.0, None, tray.detenida.mensaje))
        tray.t_fin, tray.y_fin = 0.0, y
        return tray
    paso_max = h_max
    while t < red.tf:
        try:
            solver = RK45(sis, t, y, red.tf, rtol=red.rtol, atol=atol, max_step=paso_max,
                          first_step=min(paso_max, red.tf - t))
        except (Detencion, mz.FueraDeAlcance) as x:
            tray.detenida = Detencion(_codigo(x), getattr(x, "mensaje", str(x)), t)
            tray.eventos.append((tray.detenida.codigo, t, None, tray.detenida.mensaje))
            tray.t_fin, tray.y_fin = t, y
            return tray
        reiniciar = False
        while solver.status == "running":
            t_a, y_a, sem_a = solver.t, solver.y.copy(), list(sis.semillas)
            try:
                solver.step()
            except (Detencion, mz.FueraDeAlcance) as x:
                tray.reintentos += 1
                t, y, sis.semillas = t_a, y_a, sem_a
                paso_max = (solver.step_size or paso_max) / 4
                if paso_max < h_min:
                    tray.detenida = Detencion(_codigo(x), getattr(x, "mensaje", str(x)), t_a)
                    tray.eventos.append((tray.detenida.codigo, t_a, None, tray.detenida.mensaje))
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
            sem_b = list(sis.semillas)
            cambios = set()
            t_cambio = None
            revisiones = []                 # (t, margins per volume) at each check point without a change
            for tm in [t_a + (t_b - t_a) * k / 4 for k in (1, 2, 3)] + [t_b]:
                yy = interp(tm) if tm < t_b else y_b
                fila = []
                for j in range(nv):
                    try:
                        e = sis.estado_vol(tm, yy, j, semilla=sem_a[j])
                        f = firma(e)
                        fila.append(margenes(e))
                    except mz.FueraDeAlcance:
                        f = None
                    if f != firmas[j]:
                        cambios.add(j)
                if cambios:
                    # The bisection brackets [t_a, first changed check]: the phase set may return to the
                    # original one before t_b (a closed window), where the predicate is false again.
                    t_cambio = tm
                    break
                revisiones.append((tm, fila))
            sis.semillas = sem_b
            if not cambios and _margen_cae([marg_a] + [fila for _, fila in revisiones]) and t_b - t_a > h_margen:
                # A margin fell too fast for the check spacing: a phase window could lie between two checks.
                tray.reintentos += 1
                t, y, sis.semillas = t_a, y_a, sem_a
                paso_max = max((t_b - t_a) / 4, h_margen)
                reiniciar = True
                break
            if cambios:
                def cambia(tm):
                    yy = interp(tm)
                    for j in range(nv):
                        try:
                            if firma(sis.estado_vol(tm, yy, j, semilla=sem_a[j])) != firmas[j]:
                                return True
                        except mz.FueraDeAlcance:
                            return True
                    return False
                lo, hi = t_a, t_cambio
                # Refine the boundary without changing phase-presence or
                # certificate tolerances. Preserve this exact flash context
                # below so publication cannot lose an incipient phase by
                # starting Newton from a different sample's phase set.
                while hi - lo > max(RES_EVENTO * red.tf, 1e-12):
                    mid = 0.5 * (lo + hi)
                    if cambia(mid):
                        hi = mid
                    else:
                        lo = mid
                t_e = hi
                t_biseccion = hi
                sis.semillas = list(sem_a)
                sub = (RK45(sis, t_a, y_a, t_e, rtol=red.rtol, atol=atol, max_step=paso_max,
                            first_step=min(t_e - t_a, paso_max)) if t_e > t_a else None)
                while sub is not None and sub.status == "running":
                    s_a = sub.t
                    try:
                        sub.step()
                    except (Detencion, mz.FueraDeAlcance):
                        sub = None
                        break
                    tray.tramos.append(Tramo(s_a, sub.t, sub.dense_output()))
                y_e = sub.y.copy() if sub is not None else y_a
                if sub is None:
                    t_e = t_a
                try:
                    nuevos = [sis.estado_vol(t_e, y_e, j, semilla=sem_a[j]) for j in range(nv)]
                except mz.FueraDeAlcance as x:
                    tray.detenida = Detencion(_codigo(x), x.mensaje, t_e)
                    tray.eventos.append((tray.detenida.codigo, t_e, None, x.mensaje))
                    tray.t_fin, tray.y_fin = t_e, y_e
                    return tray
                if all(firma(nuevos[j]) == firmas[j] for j in range(nv)):
                    # El interpolante del paso cambia de conjunto de fases en t_e, pero el estado reintegrado
                    # hasta t_e todavia no (difieren en ~rtol justo en la frontera). Sin esto el integrador
                    # reiniciaba en t_e y volvia a detectar lo mismo sin avanzar. Se avanza con pasos que se
                    # duplican (desde la resolucion de la biseccion) hasta el primer instante en que el estado
                    # reintegrado cambia; si no cambia en todo el paso, el paso se acepta sin evento.
                    paso_e = max(RES_EVENTO * red.tf, 1e-12)
                    hallado = False
                    t_c = t_e
                    while t_c < t_b:
                        t_c = min(t_b, t_c + paso_e)
                        paso_e *= 2
                        sis.semillas = list(sem_a)
                        sub2 = RK45(sis, t_a, y_a, t_c, rtol=red.rtol, atol=atol, max_step=paso_max,
                                    first_step=min(t_c - t_a, paso_max))
                        tramos2 = []
                        try:
                            while sub2.status == "running":
                                s_a2 = sub2.t
                                sub2.step()
                                tramos2.append(Tramo(s_a2, sub2.t, sub2.dense_output()))
                            y_c = sub2.y.copy()
                            cand = [sis.estado_vol(t_c, y_c, j, semilla=sem_a[j]) for j in range(nv)]
                        except (Detencion, mz.FueraDeAlcance):
                            break
                        if any(firma(cand[j]) != firmas[j] for j in range(nv)):
                            # se sustituyen los tramos del primer subintegrado por los de este
                            while tray.tramos and tray.tramos[-1].t0 >= t_a and tray.tramos[-1].interp is not None:
                                tray.tramos.pop()
                            tray.tramos.extend(tramos2)
                            t_e, y_e, nuevos, hallado = t_c, y_c, cand, True
                            break
                    if not hallado:
                        # La busqueda no encontro el cambio en el estado reintegrado (o un subintegrado fallo al
                        # cruzar la arista). Antes se aceptaba entonces el paso ENTERO sin evento y la fase nueva
                        # no se publicaba hasta pasos despues: en la red de 5 especies UNIFAC la segunda fase
                        # liquida salia 28 s tarde (141,41 s frente al limite de estabilidad independiente,
                        # 113,586 s; hallado el 18-10-2026, tests/validar_capa_unifac.py). La biseccion ya
                        # demostro que el estado del interpolante cambia de conjunto de fases en t_biseccion: el
                        # evento se toma ahi, con ese estado (error ~rtol, como cualquier punto de la salida densa).
                        y_c = interp(t_biseccion)
                        try:
                            cand = [sis.estado_vol(t_biseccion, y_c, j, semilla=sem_a[j]) for j in range(nv)]
                        except mz.FueraDeAlcance:
                            cand = None
                        if cand is not None and any(firma(cand[j]) != firmas[j] for j in range(nv)):
                            while tray.tramos and tray.tramos[-1].t0 >= t_a and tray.tramos[-1].interp is not None:
                                tray.tramos.pop()
                            tray.tramos.append(Tramo(t_a, t_biseccion, interp))
                            t_e, y_e, nuevos, hallado = t_biseccion, y_c, cand, True
                    if not hallado:
                        sis.semillas = sem_b
                        tray.tramos.append(Tramo(t_a, t_b, interp))
                        t, y = t_b, y_b
                        try:
                            marg_a = [margenes(sis.estado_vol(t_b, y_b, j, semilla=sem_b[j])) for j in range(nv)]
                        except mz.FueraDeAlcance:
                            pass
                        paso_max = h_max
                        solver.max_step = paso_max
                        continue
                tray.phase_event_states[t_e] = tuple(nuevos)
                detener = None
                for j in range(nv):
                    nueva = firma(nuevos[j])
                    if nueva == firmas[j]:
                        continue
                    codigo = clasificar_evento(firmas[j], nueva)
                    tray.eventos.append((codigo, t_e, j, f"fases {firmas[j][1:]} -> {nueva[1:]}"))
                    pol = red.volumenes[j].politica
                    motivo = (_prohibido(pol, nueva) if codigo != "cambio_denominacion" else
                              (f"tipo fuera de tiposPermitidos" if pol.get("tiposPermitidos") and any(
                                  x not in pol["tiposPermitidos"] for x in nueva[1:]) else None))
                    if motivo and detener is None:
                        detener = Detencion("cambio_fase_prohibido", f"Volumen {red.volumenes[j].id}: {motivo}", t_e)
                    firmas[j] = nueva
                sis.semillas = nuevos
                marg_a = [margenes(e) for e in nuevos]
                if detener is None:
                    try:
                        sis.flujos(t_e, y_e, nuevos)
                    except Detencion as x:
                        detener = x
                        detener.t = t_e
                        tray.eventos.append((x.codigo, t_e, None, x.mensaje))
                if detener is not None:
                    tray.detenida = detener
                    tray.t_fin, tray.y_fin = t_e, y_e
                    return tray
                t, y = t_e, y_e
                tray.tramos.append(Tramo(t_e, t_e, None))
                reiniciar = True
                break
            tray.tramos.append(Tramo(t_a, t_b, interp))
            t, y = t_b, y_b
            t3, fila3 = revisiones[-2] if len(revisiones) > 1 else (t_a, marg_a)
            t4, marg_a = revisiones[-1]
            # The running solver reads max_step at every step, so the margin cap applies to the next one.
            paso_max = _paso_por_margen(t3, fila3, t4, marg_a, h_max, h_margen)
            solver.max_step = paso_max
        if not reiniciar:
            break
    tray.t_fin, tray.y_fin = t, y
    return tray


def muestras(red, tray):
    n = red.muestras
    ts = [red.tf * k / (n - 1) for k in range(n)]
    ts = [t for t in ts if t <= tray.t_fin * (1 + 1e-15)]
    for _, t_e, _, _ in tray.eventos:
        if t_e <= tray.t_fin:
            # Keep the located event itself when it nearly coincides with a
            # requested output time; its frozen flash context uses this key.
            ts = [t for t in ts if abs(t_e - t) > 1e-12 * red.tf]
            ts.append(t_e)
    if tray.detenida is not None and all(abs(tray.t_fin - t) > 1e-12 * red.tf for t in ts):
        ts.append(tray.t_fin)
    ts.sort()
    return [(t, np.array(tray.y(min(t, tray.t_fin)), dtype=float)) for t in ts]
