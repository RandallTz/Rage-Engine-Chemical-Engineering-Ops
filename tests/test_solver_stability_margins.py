"""Generic closed regime windows: independent of physical packages."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.solvers.integrador import integrar, METODOS


def full_first_step(system, t, y, final, rtol, atol, maximum, method='RK45'):
    return METODOS[method](system.rhs, t, np.array(y, dtype=float), final,
                          rtol=rtol, atol=atol, max_step=maximum,
                          first_step=min(maximum, final-t))


class Window:
    def __init__(self, left=.43, right=.432):
        self.left, self.right = left, right

    def rhs(self, t, state):
        return np.ones(1)

    def firma(self, t, state):
        return self.left < state[0] < self.right

    def event_state(self, t, state):
        value = state[0]
        if self.firma(t, state):
            return True, (None, min(value-self.left, self.right-value))
        return False, (min(abs(value-self.left), abs(value-self.right))**2, None)


class MarginTests(unittest.TestCase):
    def test_narrow_closed_window_between_all_coarse_checks(self):
        for method in ('RK45', 'BDF'):
            with self.subTest(method=method), patch('core.solvers.integrador._rk', full_first_step):
                result = integrar(Window(), [0.], 1., max_step=1., metodo=method)
            self.assertIsNone(result.detenida)
            events = [row for row in result.eventos if row[0] == 'cambio_firma']
            self.assertEqual(len(events), 2)
            self.assertAlmostEqual(events[0][1], .43, delta=1e-8)
            self.assertAlmostEqual(events[1][1], .432, delta=1e-8)
            self.assertTrue(all(event[2] != event[3] for event in events))
            self.assertGreater(result.rechazos, 0)
            for t in np.linspace(0, 1, 101):
                self.assertAlmostEqual(result.y(t)[0], t, delta=1e-8)

    def test_first_changed_interior_check_brackets_a_window_that_ends_before_step_end(self):
        class Interior(Window):
            def event_state(self, t, state):
                return self.firma(t, state), ()
        with patch('core.solvers.integrador._rk', full_first_step):
            result = integrar(Interior(.2, .3), [0.], 1., max_step=1.)
        self.assertEqual(len(result.eventos), 2)
        self.assertAlmostEqual(result.eventos[0][1], .2, delta=1e-8)
        self.assertAlmostEqual(result.eventos[1][1], .3, delta=1e-8)

    def test_legacy_system_without_margin_hook_keeps_its_existing_protocol(self):
        class Legacy:
            def rhs(self, t, state): return np.ones(1)
            def firma(self, t, state): return None
        result = integrar(Legacy(), [0.], 1.)
        self.assertIsNone(result.detenida)
        self.assertEqual(result.eventos, [])
        self.assertAlmostEqual(result.y_fin[0], 1., delta=1e-12)

    def test_invalid_margin_is_rejected_explicitly(self):
        class Invalid(Window):
            def event_state(self, t, state): return False, (-1.,)
        with self.assertRaisesRegex(ValueError, 'nonnegative'):
            integrar(Invalid(), [0.], 1.)


if __name__ == '__main__':
    unittest.main()
