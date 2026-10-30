"""Nonspatial phase-event publication, work quadrature and adverse regressions.

Numerical fixtures are internal tests, never product templates. Every successful
trajectory must keep the real constitutive/conservation/second-law certificates.
"""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.motor_ensamblaje_v2 import resolver_v2
from core import ensamblaje_red as network

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs/ejemplos/motor-unifac/motor-ensamblaje-v2-resolver-unifac-monofasico-detenido-peticion.json'


def request(package='unifac-original-public'):
    value = json.loads(SOURCE.read_text(encoding='utf-8'))
    value['paquetes'][0]['modelo']['id'] = package
    return value


class ThermodynamicEventTests(unittest.TestCase):
    def test_cached_properties_and_certificates_are_not_trusted(self):
        from core.paquetes_volumen import PaqueteMezcla
        from core.mezclas import FueraDeAlcance
        package=PaqueteMezcla('unifac-original-public',['64-17-5','7732-18-5'])
        state=package.estado('TP',355.,101325.,np.array([.5,.5]))
        enthalpy=state.H
        changed=copy.deepcopy(state)
        changed.fases[0].h+=1e6
        fresh=package.certify_state(changed)
        self.assertAlmostEqual(fresh.H,enthalpy,places=7)
        limiting=copy.deepcopy(state)
        limiting.fases[0].n*=1e-13
        limiting.n=sum(phase.n*phase.x for phase in limiting.fases)
        # Certification preserves the upstream phase set; it never applies an
        # extra amount cutoff or inserts a phase merely to populate an event.
        self.assertEqual(len(package.certify_state(limiting).fases),len(state.fases))
        changed.fases[0].x=np.array([.99,.01])
        changed.verificaciones={key:(0.,value[1],value[2]) for key,value in changed.verificaciones.items()}
        with self.assertRaises(FueraDeAlcance):
            package.certify_state(changed)
        changed.fases[0].x=np.array([1.,0.])
        with np.errstate(all='raise'),self.assertRaises(FueraDeAlcance):
            package.certify_state(changed)

    def check_transition(self, value):
        result = resolver_v2(value)
        self.assertEqual(result['estado'], 'parcial', result)
        output = result['resultados']
        self.assertEqual(output['certificacion']['estado'], 'cumple', output['residuos'])
        self.assertEqual(output['certificacion']['ultimaMuestraCertificada'], len(output['tiempos']) - 1)
        phase = [event for event in output['eventos'] if event['codigo'] in ('aparicion_fase', 'desaparicion_fase', 'sustitucion_fase')]
        self.assertEqual(len(phase), 1, output['eventos'])
        event = phase[0]
        self.assertTrue(event['faseIds'], event)
        self.assertNotEqual(event['faseIdsAntes'], event['faseIdsDespues'])
        self.assertAlmostEqual(event['tiempo'], output['tiempos'][-1])
        self.assertTrue(all(item['maximoEscalado'] <= item['tolerancia'] for item in output['residuos']))
        series = {item['variableId']: item['valores'] for item in output['series']}
        H, U, P, V = [np.array(series['volumen.A.' + name]) for name in ('H', 'U', 'P', 'V')]
        # H is the integrated state, U/V are recovered by a certified flash.
        # Compare within the inversion budget, including extensive scaling.
        np.testing.assert_allclose(U, H - P * V, rtol=1e-10, atol=value['estudio']['atol']['energia'])
        Q = np.array(series['calor.q.Q'])
        np.testing.assert_allclose(H - H[0], Q * np.array(output['tiempos']), rtol=1e-8, atol=1e-7)
        return output

    def test_original_incident_and_existing_packages(self):
        for package in ('nrtl-chemsep', 'mezcla-ideal', 'unifac-original-public', 'unifac-dortmund-public'):
            with self.subTest(package=package):
                self.check_transition(request(package))

    def test_horizon_sampling_and_inventory_scaling(self):
        baseline = self.check_transition(request())
        for scale, horizon, samples in ((.01, 100., 11), (100., 600., 9)):
            value = request()
            # Scale extensive inputs together; intensive state and event time
            # are invariant. Vary output sampling independently.
            for key in value['volumenes'][0]['inicial']['cantidades']['datoIds'].values():
                datum = value['datos'][key]['declaracion']
                datum['texto'] = str(float(datum['texto']) * scale)
            value['datos']['calor.q.Q']['declaracion']['texto'] = str(100 * scale)
            value['datos']['estudio.tf']['declaracion']['texto'] = str(horizon)
            value['estudio']['muestras'] = samples
            value['estudio']['atol']['cantidad'] *= scale
            value['estudio']['atol']['energia'] *= scale
            with self.subTest(scale=scale):
                output = self.check_transition(value)
                self.assertAlmostEqual(output['tiempos'][-1], baseline['tiempos'][-1], delta=1e-4)

    def test_corrupted_auxiliary_work_still_fails(self):
        original = network.muestras
        def corrupted(red, trajectory):
            rows = copy.deepcopy(original(red, trajectory))
            rows[-1][1][network.Sistema(red).i_W] += 1000.
            return rows
        with patch.object(network, 'muestras', side_effect=corrupted):
            result = resolver_v2(request())
        output = result['resultados']
        self.assertEqual(output['certificacion']['estado'], 'no_cumple')
        self.assertGreater(next(item for item in output['residuos'] if item['ecuacionId'] == 'mecanica.A.trabajo')['maximoEscalado'], 1.)

    def test_exact_event_time_replaces_nearby_output_sample(self):
        from types import SimpleNamespace
        red=SimpleNamespace(muestras=3,tf=10.)
        event_time=5.+1e-12
        trajectory=network.Trayectoria(eventos=[('aparicion_fase',event_time,0,'test')],t_fin=10.,y_fin=np.array([10.]))
        trajectory.tramos=[network.Tramo(0.,10.,lambda t:np.array([t]))]
        times=[t for t,_ in network.muestras(red,trajectory)]
        self.assertEqual(times,[0.,event_time,10.])

    def test_cooling_and_lle_table_within_its_domain(self):
        cooling=request()
        cooling['datos']['volumen.A.T0']['declaracion']['texto']='450'
        cooling['datos']['calor.q.Q']['declaracion']['texto']='-100'
        cooling['datos']['calor.q.Tf']['declaracion']['texto']='280'
        self.check_transition(cooling)
        lle=request('unifac-original-lle-public')
        lle['datos']['volumen.A.T0']['declaracion']['texto']='285'
        lle['datos']['volumen.A.P']['declaracion']['texto']='6000'
        self.check_transition(lle)


if __name__ == '__main__':
    unittest.main()
