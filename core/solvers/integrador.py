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

from contextvars import ContextVar
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
    _check_domain(system, t, y)
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


class DomainViolation(Detencion):
    """A trial point failed a declared nonnegative domain margin."""
    def __init__(self, system, index, t, step=None):
        name = system.describir_dominio(index) if hasattr(system, 'describir_dominio') else f'domain {index}'
        self.index, self.time, self.step = index, float(t), step
        self.variable, self.bound = str(name), 'declared margin >= 0'
        super().__init__('agotamiento', f'{name}: declared margin >= 0 violated at t = {t:.12g}' +
                         (f'; step h = {step:.12g}' if step is not None else ''))


def _check_domain(system, t, y):
    outside = _fuera(system, t, y)
    if outside:
        raise DomainViolation(system, outside[0], t)


def _dense(system, dense):
    def checked(t):
        value = dense(t)
        _check_domain(system, t, value)
        return value
    checked.raw = dense      # the bare interpolant: evaluating it never calls the system (used by previews)
    return checked


@dataclass
class Trayectoria:
    tramos: list = field(default_factory=list)          # (t0, t1, dense_output)
    eventos: list = field(default_factory=list)         # (codigo, t, firma_antes, firma_despues, mensaje)
    t_fin: float = 0.0
    y_fin: np.ndarray = None
    detenida: Detencion = None
    pasos: int = 0
    rechazos: int = 0
    event_contexts: dict = field(default_factory=dict)
    _refine: object = field(default=None, repr=False)

    def y(self, t):
        for index, (t0, t1, d) in enumerate(self.tramos):
            if t0 <= t <= t1 + 1e-15 * max(1.0, abs(t1)):
                try:
                    return d(min(t, t1))
                except DomainViolation as error:
                    if self._refine is None:
                        raise
                    return self._refine(index, t, error)
        if self.y_fin is not None and abs(t - self.t_fin) <= 1e-12 * max(1.0, abs(t)):
            return self.y_fin
        raise ValueError(f"t = {t} fuera de la trayectoria [0, {self.t_fin}]")


def _rk(sistema, t0, y0, tf, rtol, atol, max_step, metodo="RK45", first_step=None, domain_jac=False):
    # first_step skips scipy's initial-step probe, which evaluates the right-hand side one guessed step ahead: after
    # a stop raised beyond the current point that probe could land past the same stop.
    extra = {"first_step": min(first_step, tf - t0)} if first_step is not None and tf - t0 > 0 else {}
    def rhs(t, y):
        _check_domain(sistema, t, y)
        return sistema.rhs(t, y)
    if metodo == 'BDF' and callable(getattr(sistema, 'jacobian', None)):
        def jacobian(t, y):
            _check_domain(sistema, t, y)
            return sistema.jacobian(t, y)
        extra['jac'] = jacobian
    elif metodo == 'BDF' and domain_jac:
        def domain_jacobian(t, y):
            base = rhs(t, y)
            result = np.empty((len(y), len(y)))
            for k in range(len(y)):
                step = np.sqrt(np.finfo(float).eps) * max(abs(y[k]), 1.)
                violated = 0
                for _ in range(20):
                    for sign in (1., -1.):
                        trial = y.copy()
                        trial[k] += sign * step
                        outside = _fuera(sistema, t, trial)
                        if outside:
                            violated = outside[0]
                        if trial[k] == y[k] or outside:
                            continue
                        result[:, k] = (rhs(t, trial) - base) / (trial[k] - y[k])
                        break
                    else:
                        step *= .1
                        continue
                    break
                else:
                    raise DomainViolation(sistema, violated, t)
            return result
        extra['jac'] = domain_jacobian
    try:
        return METODOS[metodo](rhs, t0, np.array(y0, dtype=float), tf, rtol=rtol, atol=atol, max_step=max_step,
                               **extra)
    except Detencion as error:
        if (isinstance(error, DomainViolation) and metodo == 'BDF' and not domain_jac
                and not callable(getattr(sistema, 'jacobian', None)) and error.time == t0):
            return _rk(sistema, t0, y0, tf, rtol, atol, max_step, metodo, first_step, True)
        if first_step is not None:
            raise
        # SciPy's guessed initial Euler probe can leave a physical domain even
        # when the initial state and the actual trajectory are admissible.
        # Revalidate the real initial RHS, then use a tolerance-scaled first
        # step. Ordinary stage rejection/location still governs that step.
        initial = np.asarray(y0,dtype=float)
        rate = np.asarray(rhs(t0,initial),dtype=float)
        moving = np.abs(rate)>0
        scale = np.abs(initial)+np.asarray(atol,dtype=float)/rtol
        times = np.broadcast_to(scale,rate.shape)[moving]/np.abs(rate[moving])
        step = min(max_step,tf-t0,.01*float(np.min(times)) if times.size else tf-t0)
        if not np.isfinite(step) or step<=0 or t0+step==t0:
            raise
        return _rk(sistema,t0,initial,tf,rtol,atol,max_step,metodo,first_step=step)


# Margins that are on their bound (<= 0) at the start of the current step and whose rate is not outward there.
# A trial stage or the endpoint of that step may undershoot such a margin by the cancellation of an explicit
# Runge-Kutta combination (a state exactly on its bound whose true growth is of high order); the undershoot is a
# violation only when the margin is still moving outward at that point (the sign of its derivative decides).
#
# The admission state belongs to one step generator (one run), never to the system or the module: it is the
# active scope while that generator executes a step and is empty otherwise, so interleaved runs of one system
# (a live session and its replay, or a restart) cannot read each other's admitted margins.
class _Admission:
    entry = None            # (frozenset of margin indices, horizon) or None


_ACTIVE = ContextVar('integrator_admission', default=None)


def _scoped(admission, generator):
    """Resume `generator` with `admission` as the active scope; the scope is empty between resumptions."""
    try:
        while True:
            token = _ACTIVE.set(admission)
            try:
                value = next(generator)
            except StopIteration as stop:
                return stop.value
            finally:
                _ACTIVE.reset(token)
            yield value
    finally:
        token = _ACTIVE.set(admission)
        try:
            generator.close()
        finally:
            _ACTIVE.reset(token)
            admission.entry = None


def _rate_not_outward(sistema, t, y, indices, horizon):
    """Indices whose margin does not decrease along the right-hand side at (t, y); [] if it cannot be evaluated."""
    try:
        margins = np.asarray(sistema.dominio(t, y), dtype=float)
        rate = np.asarray(sistema.rhs(t, y), dtype=float)
        predicted = np.asarray(sistema.dominio(t + horizon, y + horizon * rate), dtype=float)
    except Exception:  # noqa: BLE001 - an unevaluable point is not an admissible one
        return []
    return [k for k in indices if np.isfinite(predicted[k]) and predicted[k] >= margins[k]]


def _admit_bound_states(sistema, t, y, horizon_time):
    """Record the margins on their bound at an accepted step start that do not leave it (rate sign)."""
    admission = _ACTIVE.get()
    if admission is not None:
        admission.entry = None
    if not hasattr(sistema, "dominio"):
        return
    margins = sistema.dominio(t, y)
    on_bound = [k for k, v in enumerate(margins) if v <= 0]
    if on_bound:
        horizon = 1e-7 * max(horizon_time, 1e-300)
        keep = _rate_not_outward(sistema, t, y, on_bound, horizon)
        if keep and admission is not None:
            admission.entry = (frozenset(keep), horizon)


def _fuera(sistema, t, y):
    """Índices de dominio con valor negativo, o [] (sin dominio declarado: nunca)."""
    if not hasattr(sistema, "dominio"):
        return []
    d = sistema.dominio(t, y)
    bad = [k for k, v in enumerate(d) if not v >= 0]
    admission = _ACTIVE.get()
    admitted = admission.entry if admission is not None else None
    if bad and admitted:
        keep = [k for k in bad if k in admitted[0]]
        if keep:
            inward = _rate_not_outward(sistema, t, y, keep, admitted[1])
            bad = [k for k in bad if k not in keep or k not in inward]
    return bad


def _detener_dominio(sistema, tray, k, t):
    nombre = sistema.describir_dominio(k) if hasattr(sistema, "describir_dominio") else f"variable {k}"
    tray.detenida = Detencion("agotamiento", f"{nombre} abandonaría su dominio (no negativo) en t = {t:.12g}: la trayectoria se detiene antes")
    tray.eventos.append(("agotamiento", t, None, None, tray.detenida.mensaje))


def integrar(sistema, y0, t_final, rtol=1e-8, atol=1e-10, max_step=np.inf, h_min=1e-10, max_pasos=200000,
             metodo="RK45", *, start_time=0.0, horizon=None):
    """Integrate from `start_time` to `t_final`: drains `pasos` and returns the trajectory.

    `horizon` is the full run length that sets the probe and margin scales (default `t_final`), so a stretch of
    a longer run passes the whole horizon and its numerics do not depend on where the stretch ends."""
    generator = pasos(sistema, y0, t_final, rtol, atol, max_step, h_min, max_pasos, metodo,
                      start_time=start_time, horizon=horizon)
    try:
        while True:
            next(generator)
    except StopIteration as stop:
        return stop.value


def pasos(sistema, y0, t_final, rtol=1e-8, atol=1e-10, max_step=np.inf, h_min=1e-10, max_pasos=200000,
          metodo="RK45", *, start_time=0.0, horizon=None):
    """Step generator. Yields the live `Trayectoria` before each step attempt and once more when the step loop
    has ended (its stop, if any, already set); its accepted segments always end at the last accepted time, so a
    driver may stop at any yield. It owns its admission state and returns the trajectory, which is what
    draining it (`integrar`) gives."""
    return _scoped(_Admission(), _pasos(sistema, y0, t_final, rtol, atol, max_step, h_min, max_pasos, metodo,
                                        start_time, t_final if horizon is None else horizon))


def _pasos(sistema, y0, t_final, rtol, atol, max_step, h_min, max_pasos, metodo, start_time, horizon):
    """Retain the accepted prefix if a system-classified failure escapes a probe/restart."""
    tray = Trayectoria(t_fin=start_time, y_fin=np.array(y0, dtype=float))

    def refine(index, requested, failure):
        start, end, dense = tray.tramos[index]
        initial = np.array(dense(start), dtype=float)
        step = (end-start)/2
        if step < h_min or start + step == start:
            raise DomainViolation(sistema, failure.index, start, end-start)
        # A changed endpoint invalidates every later step and event. Rebuild the
        # entire suffix transactionally, rather than joining incompatible states.
        replacement = integrar(sistema, initial, t_final, rtol, atol, min(max_step, step),
                               h_min, max_pasos, metodo, start_time=start, horizon=horizon)
        try:
            value = replacement.y(requested)
        except ValueError as error:
            raise DomainViolation(sistema, failure.index, replacement.t_fin, step) from error
        old_prefix = tray.tramos[:index]
        tray.tramos = old_prefix + replacement.tramos
        tray.eventos = [event for event in tray.eventos if event[1] <= start] + replacement.eventos
        tray.event_contexts = {t: v for t, v in tray.event_contexts.items() if t <= start}
        tray.event_contexts.update(replacement.event_contexts)
        tray.t_fin, tray.y_fin, tray.detenida = replacement.t_fin, replacement.y_fin, replacement.detenida
        tray.pasos = index + replacement.pasos
        tray.rechazos += replacement.rechazos + 1
        return value

    tray._refine = refine
    try:
        yield from _integrar(sistema, y0, t_final, rtol, atol, max_step, h_min, max_pasos, metodo, tray, start_time, horizon)
    except DomainViolation as error:
        if tray.tramos:
            _, tray.t_fin, dense = tray.tramos[-1]
            tray.y_fin = np.array(dense(tray.t_fin), dtype=float)
        tray.detenida = DomainViolation(sistema, error.index, tray.t_fin, abs(error.time-tray.t_fin))
        tray.eventos.append((tray.detenida.codigo, tray.t_fin, None, None, tray.detenida.mensaje))
    except Exception as error:
        stop = sistema.stop_from_exception(error) if hasattr(sistema, 'stop_from_exception') else None
        if stop is None:
            raise
        if tray.tramos:
            _, tray.t_fin, dense = tray.tramos[-1]
            tray.y_fin = np.array(dense(tray.t_fin), dtype=float)
        tray.eventos = [event for event in tray.eventos if event[1] <= tray.t_fin]
        tray.detenida = stop
        tray.eventos.append((stop.codigo, tray.t_fin, None, None, stop.mensaje))
    return tray


def _integrar(sistema, y0, t_final, rtol, atol, max_step, h_min, max_pasos, metodo, tray, start_time=0.0, horizon=None):
    horizon = t_final if horizon is None else horizon
    if metodo not in METODOS:
        raise ValueError(f"método no admitido: {metodo}")
    t, y = float(start_time), np.array(y0, dtype=float)
    if _fuera(sistema, t, y):
        raise ValueError('Initial state is outside its declared domain.')
    if hasattr(sistema, "validate_accepted"):
        sistema.validate_accepted(t, y)
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
            h = 1e-7 * max(horizon, 1e-300)
            d1 = sistema.dominio(t + h, y + h * f0)
            for k in nulos:
                if d1[k] < 0:
                    _detener_dominio(sistema, tray, k, t)
                    tray.t_fin, tray.y_fin = t, y
                    return tray
    _admit_bound_states(sistema, t, y, horizon)
    paso_max = max_step
    margin_min_step = max(h_min, MARGIN_MIN_STEP*horizon)
    current_margins = initial_margins
    r = _rk(sistema, t, y, t_final, rtol, atol, paso_max, metodo)
    while r.status == "running" and tray.pasos < max_pasos:
        yield tray
        t_a, y_a = r.t, r.y.copy()
        _admit_bound_states(sistema, t_a, y_a, horizon)
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
            if isinstance(d, DomainViolation):
                d = DomainViolation(sistema, d.index, t_a, h_try)
            tray.detenida = d
            tray.eventos.append((d.codigo, t_a, firma, None, d.mensaje))
            tray.t_fin, tray.y_fin = t_a, y_a
            return tray
        except Exception as e:          # noqa: BLE001 - una etapa fuera de dominio: paso menor
            tray.rechazos += 1
            step_size = r.step_size
            paso_max = min(paso_max, max(step_size if step_size is not None and np.isfinite(step_size) else r.h_abs, h_min)) / 4
            if paso_max < h_min:
                tray.detenida = Detencion("no_convergente", f"una evaluación falla con paso {paso_max:.3g}: {e}")
                tray.eventos.append(("no_convergente", t_a, firma, None, str(e)))
                tray.t_fin, tray.y_fin = t_a, y_a
                return tray
            r = _rk(sistema, t_a, y_a, t_final, rtol, atol, paso_max, metodo, first_step=paso_max)
            continue
        if r.status == "failed":
            tray.detenida = Detencion("no_convergente", "el integrador no pudo avanzar")
            break
        # Check the accepted endpoint before any model validation or event call.
        if _fuera(sistema, r.t, r.y):
            tray.rechazos += 1
            paso_max = (r.t - t_a) / 4
            if paso_max < h_min:
                k = _fuera(sistema, r.t, r.y)[0]
                tray.detenida = DomainViolation(sistema, k, t_a, r.t - t_a)
                tray.eventos.append((tray.detenida.codigo, t_a, firma, None, tray.detenida.mensaje))
                tray.t_fin, tray.y_fin = t_a, y_a
                return tray
            r = _rk(sistema, t_a, y_a, t_final, rtol, atol, paso_max, metodo, first_step=paso_max)
            continue
        if hasattr(sistema, "validate_accepted"):
            sistema.validate_accepted(r.t, r.y)
        tray.pasos += 1
        paso_max = max_step
        if hasattr(sistema, 'dominio'):
            margins = sistema.dominio(r.t, r.y)
            zeros = [k for k, value in enumerate(margins) if value == 0]
            if zeros:
                rate = np.asarray(sistema.rhs(r.t, r.y), dtype=float)
                probe_h = 1e-7 * max(horizon, 1e-300)
                predicted = sistema.dominio(r.t + probe_h, r.y + probe_h * rate)
                outward = next((k for k in zeros if predicted[k] < 0), None)
                if outward is not None:
                    tray.tramos.append((t_a, r.t, _dense(sistema, r.dense_output())))
                    tray.t_fin, tray.y_fin = r.t, r.y.copy()
                    _detener_dominio(sistema, tray, outward, r.t)
                    return tray
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
            tray.tramos.append((t_a, lo, _dense(sistema, d)))
            tray.t_fin, tray.y_fin = lo, d(lo)
            _detener_dominio(sistema, tray, (k or fuera)[0], lo)
            return tray
        try:
            dense = _dense(sistema, r.dense_output())
            checks = [t_a+(r.t-t_a)*k/4 for k in (1, 2, 3, 4)] if hasattr(sistema, 'event_state') else [r.t]
            samples = [(t_a, current_margins)]
            changed_at = None
            for probe in checks:
                nueva, margins = _event_state(sistema, probe, r.y if probe == r.t else dense(probe))
                if nueva != firma:
                    changed_at = probe
                    break
                samples.append((probe, margins))
        except DomainViolation as d:
            tray.rechazos += 1
            paso_max = (r.t - t_a) / 4
            if paso_max < h_min:
                tray.detenida = DomainViolation(sistema, d.index, t_a, r.t-t_a)
                tray.eventos.append((tray.detenida.codigo, t_a, firma, None, tray.detenida.mensaje))
                tray.t_fin, tray.y_fin = t_a, y_a
                return tray
            r = _rk(sistema, t_a, y_a, t_final, rtol, atol, paso_max, metodo, first_step=paso_max)
            continue
        except Detencion as d:
            tray.detenida = d
            tray.eventos.append((d.codigo, r.t, firma, None, d.mensaje))
            tray.tramos.append((t_a, r.t, _dense(sistema, r.dense_output())))
            tray.t_fin, tray.y_fin = r.t, r.y.copy()
            return tray
        if changed_at is None:
            if _falling_margin(samples) and r.t-t_a > margin_min_step:
                tray.rechazos += 1
                paso_max = max((r.t-t_a)/4, margin_min_step)
                r = _rk(sistema, t_a, y_a, t_final, rtol, atol, paso_max, metodo)
                continue
            tray.tramos.append((t_a, r.t, _dense(sistema, r.dense_output())))
            current_margins = samples[-1][1]
            if len(samples) > 1:
                paso_max = _margin_step(samples[-2], samples[-1], max_step, margin_min_step)
                r.max_step = min(max_step, paso_max)
            continue
        # Cambio de régimen dentro del paso: bisección sobre la salida densa.
        d = _dense(sistema, r.dense_output())
        # Bracket the first changed interior check, not the entire accepted
        # step: a closed regime window may already have ended at r.t.
        try:
            lo, hi = samples[-1][0], changed_at
            for _ in range(200):
                if hi - lo <= 1e-12 * max(1.0, abs(hi)):
                    break
                m = 0.5 * (lo + hi)
                if _event_state(sistema, m, d(m))[0] == firma:
                    lo = m
                else:
                    hi = m
            # Keep reintegration segments private until the event is verified.
            sub = _rk(sistema, t_a, y_a, hi, rtol, atol, max_step, metodo)
            pending = []
            while sub.status == "running":
                t_s = sub.t
                sub.step()
                if sub.status == 'failed':
                    raise Detencion('no_convergente', 'Event reintegration failed.')
                pending.append((t_s, sub.t, _dense(sistema, sub.dense_output())))
            y_e = sub.y.copy()
            nueva, next_margins = _event_state(sistema, hi, y_e)
        except DomainViolation as error:
            tray.rechazos += 1
            attempted = r.t - t_a
            paso_max = attempted / 4
            if paso_max < h_min or t_a + paso_max == t_a:
                tray.detenida = DomainViolation(sistema, error.index, t_a, attempted)
                tray.eventos.append((tray.detenida.codigo, t_a, firma, None, tray.detenida.mensaje))
                tray.t_fin, tray.y_fin = t_a, y_a
                return tray
            r = _rk(sistema, t_a, y_a, t_final, rtol, atol, paso_max, metodo, first_step=paso_max)
            continue
        if nueva == firma:
            # Reintegrated dynamics can move the crossing relative to dense
            # output. Retry without publishing a fictitious no-change event.
            tray.rechazos += 1
            r = _rk(sistema, t_a, y_a, t_final, rtol, atol, max((hi-t_a)/4, h_min), metodo)
            current_margins = _event_state(sistema, t_a, y_a)[1]
            continue
        tray.tramos.extend(pending)
        current_margins = next_margins
        tray.eventos.append(("cambio_firma", hi, firma, nueva, ""))
        if hasattr(sistema, 'capture_event_context'):
            tray.event_contexts[hi] = sistema.capture_event_context(hi, y_e)
        motivo = sistema.admite(nueva) if hasattr(sistema, "admite") else None
        if motivo:
            tray.detenida = Detencion("politica_incumplida", motivo)
            tray.eventos.append(("politica_incumplida", hi, nueva, None, motivo))
            tray.t_fin, tray.y_fin = hi, y_e
            return tray
        firma = nueva
        r = _rk(sistema, hi, y_e, t_final, rtol, atol, max_step, metodo)
    if tray.detenida is None and r.status == "running":
        # The step budget ended the loop before t_final: a truncated run is a stop, never a completed one.
        tray.detenida = Detencion("max_pasos", f"The step budget max_pasos = {max_pasos} was exhausted at t = {r.t:.12g} "
                                  f"before reaching t = {t_final:.12g}; the trajectory is partial.")
        tray.eventos.append(("max_pasos", r.t, firma, None, tray.detenida.mensaje))
    tray.t_fin, tray.y_fin = r.t, r.y.copy()
    yield tray
    return tray
