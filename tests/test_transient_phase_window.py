"""F0-5: a transient phase window shorter than the integrator step must be published as events.

Closed isobaric water-1-butanol volume (Dortmund UNIFAC, 101325 Pa) with a constant imposed duty. The
water-rich solubility of 1-butanol has a minimum of about 0.027865 near 329.6 K, so a feed just above it
crosses a closed liquid-liquid window on heating: L -> LL -> L -> LV. The independent reference locates the
window boundaries along the exact energy trajectory H(t) = H0 + Q t with PH flashes and bisection.
Before the repair, the window was skipped with few output samples (largest step tf / (samples - 1)) and
the trajectory was still certified. Run: python tests/test_transient_phase_window.py (about 2 min).
"""
import json
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.motor_ensamblaje_v2 import resolver_v2
from core import mezclas as mz

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/ejemplos/motor-unifac/motor-ensamblaje-v2-resolver-unifac-monofasico-detenido-peticion.json'
PACKAGE = 'unifac-dortmund-public'
CAS = ['7732-18-5', '71-36-3']
T0, P, Q, TF = 300.0, 101325.0, 100.0, 60.0
NARROW = 0.027865          # window of about 0.64 s
WIDE = 0.0281              # window of about 21.6 s: unchanged by the repair


def request(z_butanol, samples):
    value = json.loads(SOURCE.read_text(encoding='utf-8'))
    value['solicitudId'] = f'f0-5-window-{samples}'
    value['componentes'] = [{'id': 1, 'nombre': 'water', 'simbolo': 'w', 'identidadQuimica': {'cas': CAS[0]}},
                            {'id': 2, 'nombre': '1-butanol', 'simbolo': 'b', 'identidadQuimica': {'cas': CAS[1]}}]
    value['paquetes'][0]['modelo']['id'] = PACKAGE
    volume = value['volumenes'][0]
    volume['politica']['cantidad'] = 'sin_restriccion'
    volume['formulacionEnergia']['monofasico'] = False
    data = value['datos']
    data['volumen.A.n0.1']['declaracion']['texto'] = repr(1 - z_butanol)
    data['volumen.A.n0.2']['declaracion']['texto'] = repr(z_butanol)
    data['volumen.A.T0']['declaracion']['texto'] = repr(T0)
    data['calor.q.Q']['declaracion']['texto'] = repr(Q)
    data['estudio.tf']['declaracion']['texto'] = repr(TF)
    value['estudio']['muestras'] = samples
    return value


def reference_window(z_butanol, tolerance=1e-4):
    """Boundaries of the two-liquid interval of H0 + Q t, from PH flashes only."""
    system = mz.Sistema(PACKAGE, CAS)
    n = np.array([1 - z_butanol, z_butanol])
    H0 = system.equilibrio_TP(T0, P, n).H

    def two_liquids(t):
        state = system.equilibrio_PH(P, H0 + Q * t, n)
        return sorted(f.tipo for f in state.fases) == ['liquido', 'liquido']
    grid = np.linspace(0.0, 40.0, 401)
    inside = [t for t in grid if two_liquids(t)]
    assert inside, 'the reference scan must contain the window'
    edges = []
    for outside, within in ((inside[0] - 0.1, inside[0]), (inside[-1] + 0.1, inside[-1])):
        while abs(within - outside) > tolerance:
            middle = 0.5 * (outside + within)
            if two_liquids(middle):
                within = middle
            else:
                outside = middle
        edges.append(0.5 * (outside + within))
    return edges


class TransientPhaseWindowTests(unittest.TestCase):
    def solve(self, z_butanol, samples):
        result = resolver_v2(request(z_butanol, samples))
        output = result['resultados']
        self.assertEqual(output['certificacion']['estado'], 'cumple', output['residuos'])
        return [(event['codigo'], event['tiempo']) for event in output['eventos']]

    def check_window(self, z_butanol, samples_list):
        start, end = reference_window(z_butanol)
        for samples in samples_list:
            with self.subTest(z=z_butanol, samples=samples):
                events = self.solve(z_butanol, samples)
                codes = [code for code, _ in events]
                self.assertEqual(codes, ['aparicion_fase', 'desaparicion_fase', 'aparicion_fase'], events)
                self.assertAlmostEqual(events[0][1], start, delta=1e-3)
                self.assertAlmostEqual(events[1][1], end, delta=1e-3)

    def test_narrow_window_with_long_steps(self):
        self.check_window(NARROW, (11, 2))

    def test_wide_window_unchanged(self):
        self.check_window(WIDE, (2,))


if __name__ == '__main__':
    unittest.main()
