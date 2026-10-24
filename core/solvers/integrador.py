"""
Integrador temporal genérico con eventos de firma discreta.

El sistema que se integra ofrece:

    rhs(t, y)    -> dy/dt (np.ndarray)
    firma(t, y)  -> valor hashable que describe su régimen discreto
                    (por ejemplo, el conjunto de fases presentes de cada volumen)

y, opcionalmente,

    dominio(t, y) -> valores que deben ser >= 0 (por ejemplo, cantidades que no
                    pueden ser negativas); describir_dominio(k) -> texto
    admite(firma) -> None, o el motivo por el que el modelo no admite ese
                    régimen (un supuesto declarado deja de cumplirse): la
                    trayectoria se detiene en el instante del cambio, con
                    código `politica_incumplida`

y nada más: el integrador no sabe qué significa la firma. Si cambia dentro de
un paso, se localiza el instante por bisección sobre la salida densa, se
re-integra desde el último estado aceptado hasta ese instante con un
integrador nuevo (sin promediar a través de la arista de las propiedades) y
se reinicia ahí. Un `Detencion` lanzado por rhs detiene la trayectoria con
su código (por ejemplo, una fase que se extrae y ya no existe); cualquier
otro error en una etapa se reintenta con un paso menor y, si persiste, también
detiene.

Si un valor de dominio se vuelve negativo dentro de un paso, el instante se
localiza por bisección sobre la salida densa y la trayectoria se DETIENE ahí
(código `agotamiento`): nunca se recorta ni se sigue con valores fuera de
dominio. Un valor nulo en t = 0 con derivada negativa detiene en t = 0.

Métodos: Dormand-Prince 5(4) (scipy RK45, por omisión) o BDF implícito de
orden variable (scipy BDF, para sistemas rígidos), con tolerancias por componente.

Optional shared event protocol:
    event_state(t, y) -> (signature, margins)
Margins have fixed positional identities and contain finite nonnegative scalars
or None when inactive. Their meaning belongs to the system. Probes must preserve
the RHS evaluation context. The solver checks quarter points, retries steep
margin falls, limits the next step by their trend and brackets the first changed
interior check. This is a finite resolution heuristic, not a proof that arbitrary
closed windows are absent. Systems without this hook keep endpoint detection.
"""

from dataclasses import dataclass, field

import numpy as np
from scipy.integrate import BDF, RK45

METODOS = {"RK45": RK45, "BDF": BDF}

# Same dimensionless margin resolution used by the network coordinator. The
# system supplies the physical meaning; this module knows no phases/packages.
MARGIN_FLOOR = 1e-8
MARGIN_RATIO = 0.5
MARGIN_MIN_STEP = 1e-8


def _event_state(system, t, y):
    if not hasattr(system, 'event_state'):
        return system.firma(t, y), ()
    signature, margins = system.event_state(t, y)
    margins = tuple(margins)
    if any(value is not None and (not np.isfinite(value) or value < 0) for value in margins):
        raise ValueError('Event margins must be finite nonnegative scalars or None.')
    return signature, margins


def _falling_margin(samples):
    for (_, previous), (_, current) in zip(samples, samples[1:]):
        if len(previous) != len(current):
            raise ValueError('Event margin identities must remain stable during a run.')
        if any(a is not None and b is not None and a > MARGIN_FLOOR and b < MARGIN_RATIO*a for a, b in zip(previous, current)):
            return True
    return False


def _margin_step(previous, current, maximum, minimum):
    ta, before = previous
    tb, after = current
    step = maximum
    for a, b in zip(before, after):
        if a is not None and b is not None and MARGIN_FLOOR < b < a:
            distance = b*(tb-ta)/(a-b)
            step = min(step, 4*(1-MARGIN_RATIO)*distance*0.75)
    return max(step, minimum)


class Detencion(Exception):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje)
        self.codigo, self.mensaje = codigo, mensaje


@dataclass
class Trayectoria:
    tramos: list = field(default_factory=list)          # (t0, t1, dense_output)
    eventos: list = field(default_factory=list)         # (codigo, t, firma_antes, firma_despues, mensaje)
    t_fin: float = 0.0
    y_fin: np.ndarray = None
    detenida: Detencion = None
    pasos: int = 0
    rechazos: int = 0

    def y(self, t):
        for t0, t1, d in self.tramos:
            if t0 <= t <= t1 + 1e-15 * max(1.0, abs(t1)):
                return d(min(t, t1))
        if self.y_fin is not None and abs(t - self.t_fin) <= 1e-12 * max(1.0, abs(t)):
            return self.y_fin
        raise ValueError(f"t = {t} fuera de la trayectoria [0, {self.t_fin}]")


def _rk(sistema, t0, y0, tf, rtol, atol, max_step, metodo="RK45", first_step=None):
    # first_step skips scipy's initial-step probe, which evaluates the right-hand side one guessed step ahead: after
    # a stop raised beyond the current point that probe could land past the same stop.
    extra = {"first_step": min(first_step, tf - t0)} if first_step is not None and tf - t0 > 0 else {}
    return METODOS[metodo](sistema.rhs, t0, np.array(y0, dtype=float), tf, rtol=rtol, atol=atol, max_step=max_step,
                           **extra)


def _fuera(sistema, t, y):
    """Índices de dominio con valor negativo, o [] (sin dominio declarado: nunca)."""
    if not hasattr(sistema, "dominio"):
        return []
    d = sistema.dominio(t, y)
    return [k for k, v in enumerate(d) if not v >= 0]


def _detener_dominio(sistema, tray, k, t):
    nombre = sistema.describir_dominio(k) if hasattr(sistema, "describir_dominio") else f"variable {k}"
    tray.detenida = Detencion("agotamiento", f"{nombre} abandonaría su dominio (no negativo) en t = {t:.12g}: la trayectoria se detiene antes")
    tray.eventos.append(("agotamiento", t, None, None, tray.detenida.mensaje))


def integrar(sistema, y0, t_final, rtol=1e-8, atol=1e-10, max_step=np.inf, h_min=1e-10, max_pasos=200000, metodo="RK45"):
    if metodo not in METODOS:
        raise ValueError(f"método no admitido: {metodo}")
    tray = Trayectoria()
    t, y = 0.0, np.array(y0, dtype=float)
    try:
        firma, initial_margins = _event_state(sistema, t, y)
    except Detencion as d:
        tray.detenida, tray.t_fin, tray.y_fin = d, t, y
        tray.eventos.append((d.codigo, t, None, None, d.mensaje))
        return tray
    if hasattr(sistema, "dominio"):
        d0 = sistema.dominio(t, y)
        if any(v < 0 for v in d0):
            raise ValueError("estado inicial fuera de dominio")
        nulos = [k for k, v in enumerate(d0) if v == 0]
        if nulos:
            f0 = np.asarray(sistema.rhs(t, y), dtype=float)
            h = 1e-7 * max(t_final, 1e-300)
            d1 = sistema.dominio(t + h, y + h * f0)
            for k in nulos:
                if d1[k] < 0:
                    _detener_dominio(sistema, tray, k, t)
                    tray.t_fin, tray.y_fin = t, y
                    return tray
    paso_max = max_step
    margin_min_step = max(h_min, MARGIN_MIN_STEP*t_final)
    current_margins = initial_margins
    r = _rk(sistema, t, y, t_final, rtol, atol, paso_max, metodo)
    while r.status == "running" and tray.pasos < max_pasos:
        t_a, y_a = r.t, r.y.copy()
        try:
            r.step()
        except Detencion as d:
            # A trial stage can lie beyond a physical stop (e.g. a withdrawn phase already exhausted) while the
            # accepted point t_a is far before it. Shorten the step, as for any failed stage evaluation, so the
            # stop is located to within h_min instead of being published at the last accepted point.
            h_try = getattr(r, "h_abs", None)
            h_try = min(paso_max, h_try if h_try is not None and np.isfinite(h_try) and h_try > 0 else t_final)
            if h_try / 4 >= h_min:
                tray.rechazos += 1
                paso_max = h_try / 4
                r = _rk(sistema, t_a, y_a, t_final, rtol, atol, paso_max, metodo, first_step=paso_max)
                continue
            tray.detenida = d
            tray.eventos.append((d.codigo, t_a, firma, None, d.mensaje))
            tray.t_fin, tray.y_fin = t_a, y_a
            return tray
        except Exception as e:          # noqa: BLE001 - una etapa fuera de dominio: paso menor
            tray.rechazos += 1
            paso_max = min(paso_max, max(r.step_size if np.isfinite(r.step_size) else t_final, h_min)) / 4
            if paso_max < h_min:
                tray.detenida = Detencion("no_convergente", f"una evaluación falla con paso {paso_max:.3g}: {e}")
                tray.eventos.append(("no_convergente", t_a, firma, None, str(e)))
                tray.t_fin, tray.y_fin = t_a, y_a
                return tray
            r = _rk(sistema, t_a, y_a, t_final, rtol, atol, paso_max, metodo)
            continue
        if r.status == "failed":
            tray.detenida = Detencion("no_convergente", "el integrador no pudo avanzar")
            break
        tray.pasos += 1
        paso_max = max_step
        fuera = _fuera(sistema, r.t, r.y)
        if fuera:
            # Primer instante en que algún valor de dominio se vuelve negativo.
            d = r.dense_output()
            lo, hi = t_a, r.t
            for _ in range(200):
                if hi - lo <= 1e-14 * max(1.0, abs(hi)):
                    break
                m = 0.5 * (lo + hi)
                if _fuera(sistema, m, d(m)):
                    hi = m
                else:
                    lo = m
            k = _fuera(sistema, hi, d(hi))
            tray.tramos.append((t_a, lo, d))
            tray.t_fin, tray.y_fin = lo, d(lo)
            _detener_dominio(sistema, tray, (k or fuera)[0], lo)
            return tray
        try:
            dense = r.dense_output()
            checks = [t_a+(r.t-t_a)*k/4 for k in (1, 2, 3, 4)] if hasattr(sistema, 'event_state') else [r.t]
            samples = [(t_a, current_margins)]
            changed_at = None
            for probe in checks:
                nueva, margins = _event_state(sistema, probe, r.y if probe == r.t else dense(probe))
                if nueva != firma:
                    changed_at = probe
                    break
                samples.append((probe, margins))
        except Detencion as d:
            tray.detenida = d
            tray.eventos.append((d.codigo, r.t, firma, None, d.mensaje))
            tray.tramos.append((t_a, r.t, r.dense_output()))
            tray.t_fin, tray.y_fin = r.t, r.y.copy()
            return tray
        if changed_at is None:
            if _falling_margin(samples) and r.t-t_a > margin_min_step:
                tray.rechazos += 1
                paso_max = max((r.t-t_a)/4, margin_min_step)
                r = _rk(sistema, t_a, y_a, t_final, rtol, atol, paso_max, metodo)
                continue
            tray.tramos.append((t_a, r.t, r.dense_output()))
            current_margins = samples[-1][1]
            if len(samples) > 1:
                paso_max = _margin_step(samples[-2], samples[-1], max_step, margin_min_step)
                r.max_step = min(max_step, paso_max)
            continue
        # Cambio de régimen dentro del paso: bisección sobre la salida densa.
        d = r.dense_output()
        # Bracket the first changed interior check, not the entire accepted
        # step: a closed regime window may already have ended at r.t.
        lo, hi = samples[-1][0], changed_at
        for _ in range(200):
            if hi - lo <= 1e-12 * max(1.0, abs(hi)):
                break
            m = 0.5 * (lo + hi)
            if _event_state(sistema, m, d(m))[0] == firma:
                lo = m
            else:
                hi = m
        # Re-integración limpia hasta el instante del cambio (lado nuevo) y reinicio.
        sub = _rk(sistema, t_a, y_a, hi, rtol, atol, max_step, metodo)
        while sub.status == "running":
            t_s = sub.t
            sub.step()
            tray.tramos.append((t_s, sub.t, sub.dense_output()))
        y_e = sub.y.copy()
        nueva, current_margins = _event_state(sistema, hi, y_e)
        if nueva == firma:
            # Reintegrated dynamics can move the crossing relative to dense
            # output. Retry without publishing a fictitious no-change event.
            tray.tramos = [segment for segment in tray.tramos if segment[0] < t_a]
            tray.rechazos += 1
            r = _rk(sistema, t_a, y_a, t_final, rtol, atol, max((hi-t_a)/4, h_min), metodo)
            current_margins = _event_state(sistema, t_a, y_a)[1]
            continue
        tray.eventos.append(("cambio_firma", hi, firma, nueva, ""))
        motivo = sistema.admite(nueva) if hasattr(sistema, "admite") else None
        if motivo:
            tray.detenida = Detencion("politica_incumplida", motivo)
            tray.eventos.append(("politica_incumplida", hi, nueva, None, motivo))
            tray.t_fin, tray.y_fin = hi, y_e
            return tray
        firma = nueva
        r = _rk(sistema, hi, y_e, t_final, rtol, atol, max_step, metodo)
    tray.t_fin, tray.y_fin = r.t, r.y.copy()
    return tray
