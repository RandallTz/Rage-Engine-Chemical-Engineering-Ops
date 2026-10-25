"""F9-R7 / v2 step (c) regression: IAPWS-95 saturation accuracy and one-phase certification just below T_c.

Before the fix, `agua_iapws95.saturacion` used the `chemicals` saturation fits without refinement. Their Maxwell
residual grows towards T_c (about 1.2e-9 at 16 mK below T_c, 1e-6 at 10 microK) and, with the liquid term scaled by
rho' (dP/drho)_T', which vanishes at T_c, exceeded TOL_SATURACION_MAXWELL. Every certified one-phase state with
T just below T_c was then rejected, even at 30 MPa, far from the saturation curve: the common compiler stopped a
supercritical heating run at 647.08 K (MOTOR_ENS_DETENIDO_ESTABILIDAD_NO_CERTIFICADA) that native v2 completes.

Independent references:
  * the Maxwell conditions themselves, recomputed here from `propiedades`: g' = g'' and P' = P'' = Psat, with the
    pressure mismatch scaled by max(Psat, rho' (dP/drho)_T'); below 1e-12 within 16 mK of T_c, where the fits are
    refined, and below TOL_SATURACION_MAXWELL elsewhere, where the fit values are kept unchanged;
  * the crossing time of T_c in the 1 kg, 2 kW, 30 MPa heating control, t = [h(T_c, P) - h(630 K, P)] m / Q, from
    static EOS evaluations only (no integrator), against the common compiler's `cambio_denominacion` event.
Run from the repository root (about 10 s):
    python tests/test_water_saturation_near_critical.py
"""
from pathlib import Path
import sys
import unittest
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from core import agua_iapws95 as w

warnings.filterwarnings('ignore')
GAPS = (5.0, 1.0, 0.1, 0.016, 1e-3, 1e-4, 1e-5)        # T_c - T, K


def maxwell(T, s):
    pl, pv = w.propiedades(T, s.rho_l), w.propiedades(T, s.rho_v)
    return max(abs(pl.g - pv.g) / (w.R * T), abs(pv.P - s.Psat) / s.Psat,
               abs(pl.P - s.Psat) / max(s.Psat, s.rho_l * pl.dP_drho_T))


class WaterSaturationNearCritical(unittest.TestCase):
    def test_saturation_satisfies_maxwell_up_to_the_critical_point(self):
        for gap in GAPS:
            T = w.TC - gap
            s = w.saturacion(T)
            bound = 1e-12 if gap <= 0.016 else w.TOL_SATURACION_MAXWELL     # refined only where the fit fails
            with self.subTest(gap=gap):
                self.assertLessEqual(maxwell(T, s), bound)
                self.assertLessEqual(s.residuo, bound)
                self.assertTrue(s.rho_l > w.RHOC > s.rho_v > 0)

    def test_one_phase_states_at_30_mpa_just_below_tc_are_certified(self):
        P = 30e6
        for gap in GAPS[2:]:
            T = w.TC - gap
            state = w.evaluar_TP(T, P)
            with self.subTest(gap=gap):
                self.assertEqual(state.tipo, 'liquido')
                self.assertLessEqual(state.estabilidad.residuo, w.TOL_ESTABILIDAD)
                self.assertAlmostEqual(state.propiedades.P / P, 1.0, delta=1e-12)

    def test_supercritical_heating_crosses_tc_at_the_static_reference_time(self):
        from solicitudes_v2 import Red
        from core.compilador import resolver
        from core.modelo import desde_ensamblaje_v2
        P = 30e6

        def h(T):
            lo, hi = [r for r in w.ramas(T)[0] if r[0] == ('fluido' if T >= w.TC else 'liquido')][0][1:]
            return w.propiedades(T, w.densidad(T, P, lo, hi)).h
        reference = (h(w.TC) - h(630.0)) * 1.0 / 2000.0
        request = (Red('super', ('agua',), tf=('200', 's'), muestras=5).paquete('w', 'agua-iapws95')
                   .volumen('A', 'w', {'agua': ('1', 'kg')}, ('T', '630', 'K'), P=('300', 'bar'))
                   .calor('q', None, 'A', Q=('2', 'kW'), Tfrontera=('1000', 'K'))).solicitud()
        result = resolver(desde_ensamblaje_v2(request))
        self.assertEqual(result['estado'], 'resuelto')
        events = [(e['codigo'], e['valor']) for e in result['eventos']]
        self.assertEqual([c for c, _ in events], ['cambio_denominacion'])
        self.assertAlmostEqual(events[0][1], reference, delta=1e-6)


if __name__ == '__main__':
    unittest.main(verbosity=2)
