"""
Integrador temporal genérico con eventos de firma discreta.

El sistema que se integra ofrece:

    rhs(t, y)    -> dy/dt (np.ndarray)
    firma(t, y)  -> valor hashable que describe su régimen discreto
                    (por ejemplo, el conjunto de fases presentes de cada volumen)

y nada más: el integrador no sabe qué significa la firma. Si cambia dentro de
un paso, se localiza el instante por bisección sobre la salida densa, se
re-integra desde el último estado aceptado hasta ese instante con un
integrador nuevo (sin promediar a través de la arista de las propiedades) y
se reinicia ahí. Un `Detencion` lanzado por rhs detiene la trayectoria con
su código (por ejemplo, una fase que se extrae y ya no existe); cualquier
otro error en una etapa se reintenta con un paso menor y, si persiste, también
detiene.

Método: Dormand-Prince 5(4) (scipy RK45) con tolerancias por componente.
"""

from dataclasses import dataclass, field

import numpy as np
from scipy.integrate import RK45


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
        if self.tramos and abs(t - self.t_fin) <= 1e-12 * max(1.0, abs(t)):
            return self.y_fin
        raise ValueError(f"t = {t} fuera de la trayectoria [0, {self.t_fin}]")


def _rk(sistema, t0, y0, tf, rtol, atol, max_step):
    return RK45(sistema.rhs, t0, np.array(y0, dtype=float), tf, rtol=rtol, atol=atol, max_step=max_step)


def integrar(sistema, y0, t_final, rtol=1e-8, atol=1e-10, max_step=np.inf, h_min=1e-10, max_pasos=200000):
    tray = Trayectoria()
    t, y = 0.0, np.array(y0, dtype=float)
    try:
        firma = sistema.firma(t, y)
    except Detencion as d:
        tray.detenida, tray.t_fin, tray.y_fin = d, t, y
        tray.eventos.append((d.codigo, t, None, None, d.mensaje))
        return tray
    paso_max = max_step
    r = _rk(sistema, t, y, t_final, rtol, atol, paso_max)
    while r.status == "running" and tray.pasos < max_pasos:
        t_a, y_a = r.t, r.y.copy()
        try:
            r.step()
        except Detencion as d:
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
            r = _rk(sistema, t_a, y_a, t_final, rtol, atol, paso_max)
            continue
        if r.status == "failed":
            tray.detenida = Detencion("no_convergente", "el integrador no pudo avanzar")
            break
        tray.pasos += 1
        paso_max = max_step
        try:
            nueva = sistema.firma(r.t, r.y)
        except Detencion as d:
            tray.detenida = d
            tray.eventos.append((d.codigo, r.t, firma, None, d.mensaje))
            tray.tramos.append((t_a, r.t, r.dense_output()))
            tray.t_fin, tray.y_fin = r.t, r.y.copy()
            return tray
        if nueva == firma:
            tray.tramos.append((t_a, r.t, r.dense_output()))
            continue
        # Cambio de régimen dentro del paso: bisección sobre la salida densa.
        d = r.dense_output()
        lo, hi = t_a, r.t
        for _ in range(200):
            if hi - lo <= 1e-12 * max(1.0, abs(hi)):
                break
            m = 0.5 * (lo + hi)
            if sistema.firma(m, d(m)) == firma:
                lo = m
            else:
                hi = m
        # Re-integración limpia hasta el instante del cambio (lado nuevo) y reinicio.
        sub = _rk(sistema, t_a, y_a, hi, rtol, atol, max_step)
        while sub.status == "running":
            t_s = sub.t
            sub.step()
            tray.tramos.append((t_s, sub.t, sub.dense_output()))
        y_e = sub.y.copy()
        nueva = sistema.firma(hi, y_e)
        tray.eventos.append(("cambio_firma", hi, firma, nueva, ""))
        firma = nueva
        r = _rk(sistema, hi, y_e, t_final, rtol, atol, max_step)
    tray.t_fin, tray.y_fin = r.t, r.y.copy()
    return tray
