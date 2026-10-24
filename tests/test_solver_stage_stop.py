"""A stop raised while evaluating a trial stage is located, not published at the last accepted point.

Found while retiring the legacy v1 assembly (dec-r5-legacy-v1): withdrawing liquid from a rigid two-phase water
vessel at 0.5 kg/s exhausts the liquid at 7.2715675 s (independent IAPWS-95 UV reference, equal to the frozen
revision-1 result), but the common compiler stopped at 6.5636 s because an RK stage at 7.56 s found no liquid and
the solver ended the trajectory at its last accepted point. Generic reproducer: a store drained at a constant rate
whose evaluation stops below zero. Run: python tests/test_solver_stage_stop.py
"""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.solvers.integrador import Detencion, integrar


class Drained:
    """y' = -1 from y(0) = y0; evaluating y < 0 raises a physical stop (nothing left to withdraw)."""

    def __init__(self, y0):
        self.y0 = y0

    def rhs(self, t, y):
        if y[0] < 0:
            raise Detencion("fase_ausente", "nothing left to withdraw")
        return -np.ones(1)

    def firma(self, t, y):
        return None


class StageStopTests(unittest.TestCase):
    def test_stop_is_located_within_the_step(self):
        for method in ("RK45", "BDF"):
            with self.subTest(method=method):
                tray = integrar(Drained(7.2715674937), [7.2715674937], 20.0, max_step=1.0, metodo=method)
                self.assertIsNotNone(tray.detenida)
                self.assertEqual(tray.detenida.codigo, "fase_ausente")
                self.assertAlmostEqual(tray.t_fin, 7.2715674937, delta=1e-6)

    def test_stop_inside_the_first_step(self):
        tray = integrar(Drained(0.3), [0.3], 20.0, max_step=10.0)
        self.assertEqual(tray.detenida.codigo, "fase_ausente")
        self.assertAlmostEqual(tray.t_fin, 0.3, delta=1e-6)


if __name__ == "__main__":
    unittest.main()
