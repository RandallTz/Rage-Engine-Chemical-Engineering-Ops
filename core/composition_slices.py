"""
Multicomponent composition-line slice at fixed T and P: the equilibrium phases of every feed on the segment
z(l) = (1 - l) zA + l zB, l in [0, 1], for any number of species, with the phase boundaries located.

Every species is kept: the feed is never renormalized onto fewer species, and a species absent from both end
feeds is rejected rather than dropped. Each feed is closed by the package's certified TP equilibrium; along
the line the previous state seeds the next one (`flash_rapido`, a Newton on the previous phase set followed by
the full stability test, which falls back to the full TP operation when the phase set changes), so the slice
is a continuation in l. Where the phase set changes between neighbours, the boundary l* is located by
bisection; at a boundary one phase appears with zero amount and its composition is the other end of a tie
line (or a triangle side) through z(l*).
"""

import math

import numpy as np

from core import mezclas as mz

PROFILES = {"exploratoria": {"puntosBase": 41, "biseccion": 30}, "refinada": {"puntosBase": 121, "biseccion": 40}}
TRAZADOR = {"id": "corte-linea-composicion", "version": "1"}


class SliceRejected(Exception):
    def __init__(self, motivo, mensaje):
        super().__init__(mensaje)
        self.motivo, self.mensaje = motivo, mensaje


def _signature(state):
    return tuple(sorted(f.tipo for f in state.fases))


def _row(l, z, state):
    certified = all(r <= t for r, t, _ in state.verificaciones.values())
    total = sum(f.n for f in state.fases)
    return {"l": float(l), "z": [float(v) for v in z], "T": float(state.T), "P": float(state.P),
            "fases": [{"tipo": f.tipo, "fraccion": float(f.n / total), "x": [float(v) for v in f.x]}
                      for f in sorted(state.fases, key=lambda f: (f.tipo, float(f.x[0])))],
            "firma": list(_signature(state)), "certificado": certified,
            "verificaciones": {k: [float(r), float(t)] for k, (r, t, _) in state.verificaciones.items()},
            "tmMinimo": float(state.estabilidad.get("tm_min", math.nan))}


def trace(sis, T, P, zA, zB, profile, spend=lambda n=1: None, exhausted=lambda: False):
    """Rows along the line, boundaries between phase sets, and how the walk finished."""
    zA, zB = np.asarray(zA, dtype=float), np.asarray(zB, dtype=float)
    n = len(sis.cas)
    for name, z in (("zA", zA), ("zB", zB)):
        if z.shape != (n,) or not np.all(np.isfinite(z)) or np.any(z < 0) or abs(z.sum() - 1) > 1e-12:
            raise SliceRejected("invalido", f"{name}: {n} non-negative mole fractions that sum to 1")
    if np.any(zA + zB <= 0):
        raise SliceRejected("no_soportado", "a species is absent from both ends; it is not dropped silently: "
                                            "declare a slice of the other species instead")
    sis.dominio(T, P)
    base = profile["puntosBase"]
    k = np.arange(base)
    ls = list(0.5 * (1 - np.cos(np.pi * k / (base - 1))))
    feed = lambda l: (1 - l) * zA + l * zB
    states = {}
    previous = [None]

    def close(l):
        spend()
        z = feed(l)
        try:
            e = (sis.flash_rapido("TP", T, P, z, previous[0]) if previous[0] is not None and
                 np.all(z > 0) == np.all(previous[0].n > 0) else sis.equilibrio_TP(T, P, z))
        except mz.FueraDeAlcance as x:
            return None, x
        return e, None

    rows, failures = {}, []
    for l in ls:
        if exhausted():
            break
        e, err = close(l)
        if e is None:
            failures.append({"l": float(l), "motivo": err.motivo, "mensaje": str(err)[:300]})
            continue
        previous[0] = e
        states[l] = e
        rows[l] = _row(l, feed(l), e)
    boundaries = []
    done = sorted(states)
    for a, b in zip(done, done[1:]):
        if _signature(states[a]) == _signature(states[b]) or exhausted():
            continue
        lo, hi, s_lo, s_hi = a, b, states[a], states[b]
        for _ in range(profile["biseccion"]):
            if exhausted():
                break
            m = 0.5 * (lo + hi)
            previous[0] = s_lo
            e, _ = close(m)
            if e is None:
                break
            if _signature(e) == _signature(s_lo):
                lo, s_lo = m, e
            elif _signature(e) == _signature(s_hi):
                hi, s_hi = m, e
            else:
                rows[m] = _row(m, feed(m), e)     # a third phase set inside the interval: kept, then bisected
                hi, s_hi = m, e
        boundaries.append({"l": [float(lo), float(hi)], "antes": _row(lo, feed(lo), s_lo),
                           "despues": _row(hi, feed(hi), s_hi)})
    return {"filas": [rows[l] for l in sorted(rows)], "fronteras": boundaries, "fallos": failures,
            "finalizacion": "presupuesto" if exhausted() else "recorrido_completo"}
