"""dec-r5-legacy-v1: the revision-1 assembly is retired and its cases are solved by the common compiler.

1. Parity: each frozen revision-1 resolution (docs/ejemplos/motor-ensamblaje-resolver-*) is translated to revision 2
   (tests/v1_assembly_cases.py) and solved by core.compilador. Resolved cases reproduce the frozen T, P, V, U, H and
   mass within 1e-7 relative and the phase events within 1e-6 s; partial cases stop with the same code and time.
2. The extraction case's stop is also checked against an IAPWS-95 UV reference written independently of both solvers
   (.tmp evidence: liquid exhausted at 7.2715674937 s).
3. Revision 1 is answered with MOTOR_ENS_REVISION_RETIRADA and a capabilities notice that points to revision 2.
Run: python tests/test_retired_v1_assembly.py (about 30 s).
"""
from pathlib import Path
import sys
import unittest
import warnings

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from backend import motor_ensamblaje as me
from v1_assembly_cases import RESOLVE_CASES, frozen, solve_common, to_v2

warnings.filterwarnings('ignore')
M_WATER = 0.018015268            # kg/mol, IAPWS-95: the compiler publishes amounts, revision 1 published masses


def published(result):
    t = np.array(result['ejes'][0]['valores'])
    series = {}
    for s in result['series']:
        key = s['id']
        if key.endswith('.n.1'):
            series['m'] = np.array(s['valores'], float) * M_WATER
        elif key.count('.') == 2:
            series[key.split('.')[-1]] = np.array(s['valores'], float)
    return t, series


class Parity(unittest.TestCase):
    def test_each_frozen_case(self):
        for case in RESOLVE_CASES:
            with self.subTest(case=case):
                request, reference = frozen(case)
                result = solve_common(to_v2(request))
                self.assertEqual(result['estado'], reference['estado'])
                R = reference['resultados']
                events_ref = [(e.get('tipo') or e.get('codigo'), e['tiempo']) for e in R['eventos']]
                events = [(e['codigo'], e['valor']) for e in result['eventos'] if e['codigo'] != 'politica_incumplida']
                self.assertEqual([c for c, _ in events], [c for c, _ in events_ref])
                for (_, a), (_, b) in zip(events, events_ref):
                    self.assertLessEqual(abs(a - b), 1e-6)
                t, series = published(result)
                t_ref = np.array(R['tiempos'])
                self.assertLessEqual(abs(t[-1] - t_ref[-1]), 1e-6)
                ref = {s['variableId'].split('.')[-1] if not s['variableId'].endswith('.m.1') else 'm':
                       np.array(s['valores'], float) for s in R['series'] if s['variableId'].startswith('volumen.')}
                for q in ('m', 'T', 'P', 'V', 'U', 'H'):
                    if q in ref and q in series:
                        both = t_ref <= t[-1]
                        got = np.interp(t_ref[both], t, series[q])
                        scale = float(np.max(np.abs(ref[q])))
                        self.assertLessEqual(float(np.max(np.abs(got - ref[q][both]))) / scale, 1e-7, q)

    def test_liquid_extraction_stop_against_iapws_reference(self):
        request, _ = frozen('extraccion-liquido')
        result = solve_common(to_v2(request))
        self.assertEqual(result['eventos'][-1]['codigo'], 'fase_ausente')
        self.assertAlmostEqual(result['eventos'][-1]['valor'], 7.2715674937, delta=1e-6)


class Retirement(unittest.TestCase):
    def test_revision_1_is_rejected_with_a_structured_notice(self):
        request, _ = frozen('ebullicion-presion-constante')
        for answer in (me.validar(request)[0], me.resolver(request)['validacion']):
            self.assertEqual([d['codigo'] for d in answer['diagnosticos']], ['MOTOR_ENS_REVISION_RETIRADA'])
            self.assertEqual(answer['diagnosticos'][0]['estado'], 'no_soportado')
        self.assertEqual(me.resolver(request)['estado'], 'no_soportado')
        self.assertIsNone(me.validar(request)[1])
        notice = me.capacidades()
        self.assertEqual(notice['estado'], 'retirada')
        self.assertEqual(notice['sustituta']['revision'], 2)

    def test_revision_2_is_still_dispatched(self):
        request, _ = frozen('rigida-calentamiento')
        answer = me.validar(to_v2(request))[0]
        self.assertEqual(answer['revision'], 2)
        self.assertNotIn('MOTOR_ENS_REVISION_RETIRADA', [d['codigo'] for d in answer['diagnosticos']])


if __name__ == '__main__':
    unittest.main()
