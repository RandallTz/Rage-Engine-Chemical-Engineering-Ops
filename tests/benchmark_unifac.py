"""
Benchmark de UNIFAC en el motor (docs/history/frontend/contract-claude-unifac-engine.md, U8): arranque en frio, TP, PH, UV,
estabilidad y trayectoria, por N y conjunto de fases, frente a NRTL e ideal en los mismos estados cuando hay
parametros. Tiempos de pared en el equipo que lo ejecuta (mediana de las repeticiones indicadas).

Ejecutar desde la raiz del proyecto:
    python tests/benchmark_unifac.py
"""

import json
import platform
import statistics
import subprocess
import sys
import time
import warnings
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "tests"))
warnings.filterwarnings("ignore")

import numpy as np

from backend import motor_ensamblaje as me
from core import mezclas as mz
from solicitudes_v2 import CAS, Red

P = 101325.0
TODAS = [CAS[k] for k in ("benceno", "tolueno", "etanol", "metanol", "agua", "acetato", "butanol")]
N4 = [CAS[k] for k in ("agua", "etanol", "acetato", "metanol")]


def medir(f, rep=5):
    ts = []
    for _ in range(rep):
        t0 = time.perf_counter()
        r = f()
        ts.append(time.perf_counter() - t0)
    return statistics.median(ts), r


def fila(*c):
    print(" | ".join(str(x) for x in c))


print(f"equipo: {platform.processor() or platform.machine()}, Python {platform.python_version()}, numpy {np.__version__}")
codigo = ("import time; t0 = time.perf_counter(); import sys; sys.path.insert(0, '.'); from core import mezclas as mz; "
          "s = mz.Sistema('unifac-original-public', ['64-17-5', '7732-18-5']); "
          "s.equilibrio_TP(355.0, 101325.0, [0.5, 0.5]); print(time.perf_counter() - t0)")
frio = [float(subprocess.run([sys.executable, "-c", codigo], cwd=str(RAIZ), capture_output=True, text=True).stdout.split()[-1])
        for _ in range(3)]
print(f"arranque en frio (import + tablas UNIFAC + primer TP etanol-agua): mediana {statistics.median(frio):.2f} s de 3")

print("\n| operacion | paquete | N | fases | mediana (s) |")
print("|---|---|---|---|---|")
casos = [("unifac-original-public", [CAS["etanol"], CAS["agua"]], 355.0), ("nrtl-chemsep", [CAS["etanol"], CAS["agua"]], 355.0),
         ("unifac-original-public", N4, 300.0), ("nrtl-chemsep", N4, 300.0),
         ("unifac-original-public", N4, 346.0), ("nrtl-chemsep", N4, 346.0),
         ("unifac-original-public", TODAS[:5], 341.0), ("unifac-original-public", TODAS, 351.0),
         ("mezcla-ideal", TODAS, 351.0), ("unifac-dortmund-public", TODAS, 351.0)]
for paq, S, T in casos:
    s = mz.Sistema(paq, S)
    z = np.ones(len(S)) / len(S) if T != 300.0 else np.array([0.7, 0.04, 0.24, 0.02])
    t, e = medir(lambda: s.equilibrio_TP(T, P, z))
    fila("", "TP", paq, len(S), "+".join(f.tipo[0].upper() for f in e.fases), f"{t:.3f} |")
    mu = s.mu("liquido", T, P, z, list(range(len(S))))
    t, _ = medir(lambda: s.prueba_estabilidad(T, P, mu, list(range(len(S))), True))
    fila("", "estabilidad (liquido de prueba + vapor)", paq, len(S), "-", f"{t:.3f} |")
    if T != 300.0:
        t, _ = medir(lambda: s.equilibrio_PH(P, e.H, z), rep=3)
        fila("", "PH", paq, len(S), "+".join(f.tipo[0].upper() for f in e.fases), f"{t:.3f} |")
        if any(f.tipo == "vapor" for f in e.fases):
            t, _ = medir(lambda: s.equilibrio_UV(e.U, e.V, z), rep=3)
            fila("", "UV", paq, len(S), "+".join(f.tipo[0].upper() for f in e.fases), f"{t:.3f} |")

print("\n| trayectoria (calentamiento 100 W, 330 K, 300 s, 6 muestras, rtol 1e-8) | paquete | N | s | eventos |")
print("|---|---|---|---|---|")
for paq, par in (("unifac-original-public", ("etanol", "agua")), ("nrtl-chemsep", ("etanol", "agua")),
                 ("unifac-original-public", ("agua", "etanol", "acetato", "metanol")),
                 ("nrtl-chemsep", ("agua", "etanol", "acetato", "metanol"))):
    n0 = {k: (str(round(1.0 / len(par), 12)), "mol") for k in par}
    red = (Red("b", par, tf=("300", "s"), muestras=6).paquete("p", paq)
           .volumen("A", "p", n0, ("T", "330", "K"), P=("101325", "Pa"), base="molar")
           .calor("q", None, "A", Q=("100", "W"), Tfrontera=("700", "K")))
    t0 = time.perf_counter()
    r = me.resolver(red.solicitud())
    dt = time.perf_counter() - t0
    fila("", "", paq, len(par), f"{dt:.1f}", f"{[e['codigo'] for e in (r['resultados'] or {}).get('eventos', [])]} |")
