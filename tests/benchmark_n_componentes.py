"""
Benchmark de la ampliacion a N componentes (docs/MOTOR_TERMODINAMICA_N_COMPONENTES.md, N4).

  * N = 2 y 3: prueba de estabilidad especializada (malla) frente a la general (Michelsen), mismos estados;
  * N = 4, 5 y 7: TP una fase, TP L-V, TP junto a la burbuja (+1e-6 K), PH, UV, con evaluaciones de la
    prueba de estabilidad, cache fria (Sistema nuevo) y caliente (misma llamada repetida), y pico de memoria.
Semilla de la estabilidad general: 12345 (fija). Tolerancias: TOL_MU 1e-10, TOL_TM 1e-9.

Ejecutar desde la raiz del proyecto:
    python tests/benchmark_n_componentes.py
"""

import sys
import time
import tracemalloc
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
warnings.filterwarnings("ignore")

import numpy as np

from core import mezclas as mz

CAS = {"agua": "7732-18-5", "etanol": "64-17-5", "benceno": "71-43-2", "tolueno": "108-88-3", "butanol": "71-36-3",
       "metanol": "67-56-1", "acetato": "141-78-6"}
TODAS = [CAS[k] for k in ("benceno", "tolueno", "etanol", "metanol", "agua", "acetato", "butanol")]


def cronometro(f, rep=3):
    ts = []
    for _ in range(rep):
        t = time.perf_counter()
        r = f()
        ts.append(time.perf_counter() - t)
    return r, min(ts)


def main():
    P = 101325.0
    print("1. Estabilidad especializada frente a general (mismo estado de referencia)")
    for paq, cas, T, x in (("nrtl-lle-agua-butanol", [CAS["agua"], CAS["butanol"]], 320.0, [0.75, 0.25]),
                           ("nrtl-chemsep", [CAS["agua"], CAS["etanol"], CAS["acetato"]], 300.0, [0.7, 0.05, 0.25])):
        s = mz.Sistema(paq, cas)
        idx = list(range(len(cas)))
        mu = s.mu("liquido", T, 1e5, np.array(x), idx)
        (pa, ta) = cronometro(lambda: s.prueba_estabilidad(T, 1e5, mu, idx, False))
        (pb, tb) = cronometro(lambda: s._estabilidad_general(T, 1e5, mu, idx))
        print(f"   N={len(cas)}: especializada {ta * 1e3:.1f} ms (min tm {min(q[2] for q in pa):.4e}); general "
              f"{tb * 1e3:.1f} ms (min tm {min(q[2] for q in pb):.4e}, "
              f"{s._ultima_estabilidad_general['arranques']} arranques)")
    print("2. Estados de N = 4, 5 y 7 componentes")
    for paq, cas, T1, T2 in (("nrtl-chemsep", [CAS[k] for k in ("etanol", "benceno", "tolueno", "metanol")], 330.0, 345.0),
                             ("mezcla-ideal", TODAS[:4], 330.0, 352.0), ("mezcla-ideal", TODAS[:5], 330.0, 355.0),
                             ("mezcla-ideal", TODAS, 330.0, 360.0)):
        z = np.ones(len(cas)) / len(cas)
        tracemalloc.start()
        t = time.perf_counter()
        s = mz.Sistema(paq, cas)
        e1 = s.equilibrio_TP(T1, P, z)
        frio = time.perf_counter() - t
        _, pico = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        (_, t1) = cronometro(lambda: s.equilibrio_TP(T1, P, z))
        (e2, t2) = cronometro(lambda: s.equilibrio_TP(T2, P, z))
        lo, hi = T1, T2
        for _ in range(50):
            m = 0.5 * (lo + hi)
            if any(f.tipo == "vapor" for f in s.equilibrio_TP(m, P, z).fases):
                hi = m
            else:
                lo = m
        (eb, tbur) = cronometro(lambda: s.equilibrio_TP(hi * (1 + 1e-6), P, z))
        (eph, tph) = cronometro(lambda: s.equilibrio_PH(P, e2.H, z), rep=1)
        (euv, tuv) = cronometro(lambda: s.equilibrio_UV(e2.U, e2.V, z), rep=1)
        print(f"   {paq} N={len(cas)}: TP una fase {t1 * 1e3:.0f} ms (fria {frio * 1e3:.0f} ms, pico "
              f"{pico / 1e6:.1f} MB); TP L-V {t2 * 1e3:.0f} ms; junto a la burbuja {tbur * 1e3:.0f} ms "
              f"({len(eb.fases)} fases); PH {tph:.2f} s; UV {tuv:.2f} s; pruebas de estabilidad del TP L-V "
              f"{e2.estabilidad.get('pruebas')}")


if __name__ == "__main__":
    main()
