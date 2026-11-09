"""F8b: a dynamic volume of the v2 assembly selects the cubic EOS packages (peng-robinson-vdw1f, psrk-unifac).

The production v2 route (`backend.v2_compatibility.resolve`, the common compiler) closes every evaluation of a
volume by UV (rigid) or PH (prescribed pressure) through `core.termodinamica.eos_package.PaqueteEOS`, which wraps
the same `cubic_flash` operations as the steady layer. References that do not go through the assembly:

  * the steady EOS flash accepted in core/termodinamica (`cubic_flash.flash_TP/PH/UV`, `saturation`), called
    directly on H0 + Q t and U0 + Q t (an imposed duty makes the energy history exact);
  * mass and energy conservation over the run (the vessel is closed);
  * published vapour-liquid points: benzene + toluene at 353.15 K and 69.5 kPa, x_benzene = 0.5 (Lee et al. 2009, the
    point of tests/test_cubic_eos_mixture.py) for Peng-Robinson, and CO2 + ethanol at 333.15 K, x_CO2 = 0.3317,
    6.06 MPa (Sima et al. 2011, the point of tests/test_psrk_mixture.py) for PSRK, and the normal boiling point of
    toluene, 383.78 K (NIST Chemistry WebBook), for a pure vessel.

Located rejections (a species without a record, a pure-data substitution, an unsupported phase set) and the
published capability are checked without running a vessel. Every vessel run takes minutes (each evaluation is a
certified cubic flash); the runs are separate classes so a runner can split them.
"""
import copy
import json
import math
import sys
import unittest
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import v2_compatibility
from backend import motor_ensamblaje_v2 as wire
from core import mezclas as mz
from core import paquetes_volumen as pv
from core.termodinamica import capa, cubic_eos, cubic_flash, psrk
from core.termodinamica.eos_package import PaqueteEOS

SOURCE = ROOT / 'docs/ejemplos/motor-unifac/motor-ensamblaje-v2-resolver-unifac-monofasico-detenido-peticion.json'
BZ, TO, CO2, ETOH = '71-43-2', '108-88-3', '124-38-9', '64-17-5'
PR, PSRK = capa.CUBICO, capa.PSRK
NAMES = {BZ: 'benzene', TO: 'toluene', CO2: 'carbon dioxide', ETOH: 'ethanol', '74-82-8': 'methane'}


def eos_of(package, cas):
    return psrk.PSRKMixture(cas) if package == PSRK else cubic_eos.PengRobinsonMixture(tuple(cas))


def request(package, cas, amounts, T0, Q, tf, samples, P=None, V=None):
    """One closed vessel with an imposed duty. P given: prescribed pressure; V given: rigid."""
    value = json.loads(SOURCE.read_text(encoding='utf-8'))
    value['solicitudId'] = 'f8b-eos-dynamic'
    value['componentes'] = [{'id': i + 1, 'nombre': NAMES[c], 'simbolo': f's{i}', 'identidadQuimica': {'cas': c}}
                            for i, c in enumerate(cas)]
    value['paquetes'][0]['modelo'] = {'id': package, 'version': '1'}
    volume = value['volumenes'][0]
    volume['componenteIds'] = [i + 1 for i in range(len(cas))]
    volume['politica']['cantidad'] = 'sin_restriccion'
    volume['formulacionEnergia']['monofasico'] = False
    volume['inicial']['cantidades']['datoIds'] = {str(i + 1): f'volumen.A.n0.{i + 1}' for i in range(len(cas))}
    data = value['datos']
    template = copy.deepcopy(data['volumen.A.n0.1'])
    for key in [k for k in data if k.startswith('volumen.A.n0.')]:
        del data[key]
    for i, amount in enumerate(amounts):
        row = copy.deepcopy(template)
        row['declaracion']['texto'] = repr(float(amount))
        data[f'volumen.A.n0.{i + 1}'] = row
    data['volumen.A.T0']['declaracion']['texto'] = repr(float(T0))
    data['calor.q.Q']['declaracion']['texto'] = repr(float(Q))
    data['estudio.tf']['declaracion']['texto'] = repr(float(tf))
    if V is not None:
        volume['frontera'] = {'tipo': 'rigida', 'datoId': 'volumen.A.V'}
        volume['formulacionEnergia']['presionUniforme'] = False
        volume['formulacionEnergia']['presionPrescrita'] = False
        volume['formulacionMateria']['fija'] = True
        row = copy.deepcopy(data['volumen.A.P'])
        row['magnitud'], row['funcion'] = 'volumen', 'geometria'
        row['declaracion'] = {'texto': repr(float(V)), 'unidad': 'm3'}
        del data['volumen.A.P']
        data['volumen.A.V'] = row
    else:
        data['volumen.A.P']['declaracion']['texto'] = repr(float(P))
    value['estudio']['muestras'] = samples
    value['estudio']['rtol'] = 1e-6          # the imposed duty makes the energy history exact; fewer steps
    return value


def series(output, identity):
    return np.array(next(s for s in output['series'] if s['variableId'] == identity)['valores'], dtype=float)


def solve(value):
    result = v2_compatibility.resolve(value)
    assert result['estado'] == 'resuelto', (result['estado'], result['validacion']['diagnosticos'])
    output = result['resultados']
    assert output['certificacion']['estado'] == 'cumple', output['certificacion']
    return result, output


class IsobaricVessel:
    """Mixin: a closed isobaric vessel heated by an imposed duty through its bubble point."""
    package = cas = amounts = P = T0 = Q = tf = None
    samples = 3
    published = None            # (T [K], tolerance [K], source)

    @classmethod
    def setUpClass(cls):
        cls.z = np.asarray(cls.amounts, dtype=float)
        cls.eos = eos_of(cls.package, cls.cas)
        cls.result, cls.out = solve(request(cls.package, cls.cas, cls.amounts, cls.T0, cls.Q, cls.tf, cls.samples,
                                            P=cls.P))
        cls.t = np.array(cls.out['tiempos'], dtype=float)
        cls.H0 = sum(p['n'] * p['h'] for p in cubic_flash.flash_TP(cls.eos, cls.T0, cls.P, cls.z)['phases'])

    def test_closed_vessel_conserves_matter_and_follows_the_imposed_energy(self):
        for i in range(len(self.cas)):
            n = series(self.out, f'volumen.A.n.{i + 1}')
            self.assertLess(float(np.max(np.abs(n - self.z[i]))), 1e-12)
        H = series(self.out, 'volumen.A.H')
        err = np.abs(H - (self.H0 + self.Q * self.t))
        print(f'{self.package}: initial H {abs(H[0] - self.H0):.2e} J, worst |H - (H0 + Q t)| {err.max():.2e} J')
        self.assertLess(abs(H[0] - self.H0), 1e-8 * abs(self.H0))
        self.assertLess(float(err.max()), 1e-6 * abs(self.H0))
        self.assertTrue(np.all(np.abs(series(self.out, 'volumen.A.P') - self.P) < 1e-6))

    def test_states_equal_the_steady_eos_flash(self):
        T = series(self.out, 'volumen.A.T')
        worst = 0.0
        for t, published in zip(self.t, T):
            ref = cubic_flash.flash_PH(self.eos, self.P, self.H0 + self.Q * t, self.z)['T']
            worst = max(worst, abs(published - ref))
        print(f'{self.package}: worst |T - steady PH flash| {worst:.2e} K over {len(self.t)} samples')
        self.assertLess(worst, 1e-6)
        self.assertGreater(T[-1], T[0])

    def test_phase_appearance_is_the_bubble_point_of_the_package_and_of_the_data(self):
        events = [e for e in self.out['eventos'] if e['codigo'] == 'aparicion_fase']
        self.assertEqual(len(events), 1, self.out['eventos'])
        te = events[0]['tiempo']
        T_event = cubic_flash.flash_PH(self.eos, self.P, self.H0 + self.Q * te, self.z)['T']
        T_bubble = cubic_flash.saturation(self.eos, self.z / self.z.sum(), P=self.P, kind='bubble')['T']
        data, tol, source = self.published
        print(f'{self.package}: event at {te:.6f} s, T {T_event:.6f} K; package bubble point {T_bubble:.6f} K; '
              f'published {data} K ({source}); |T_event - bubble| {abs(T_event - T_bubble):.2e} K; '
              f'|T_event - published| {abs(T_event - data):.3f} K')
        self.assertLess(abs(T_event - T_bubble), 1e-5)
        self.assertLess(abs(T_event - data), tol)
        self.assertEqual(self.out['certificacion']['estado'], 'cumple')


class PengRobinsonBinaryIsobaric(IsobaricVessel, unittest.TestCase):
    package, cas, amounts = PR, [BZ, TO], [0.5, 0.5]
    P, T0, Q, tf = 69.5e3, 349.0, 400.0, 3.0
    published = (353.15, 1.0, 'Lee et al. 2009, x_benzene = 0.5, 69.5 kPa')


class PsrkCo2EthanolIsobaric(IsobaricVessel, unittest.TestCase):
    package, cas, amounts = PSRK, [CO2, ETOH], [0.3317, 0.6683]
    P, T0, Q, tf = 6.06e6, 320.0, 400.0, 8.0
    # PSRK is predictive here and over-predicts this bubble pressure (7.01 MPa at 333.15 K against the measured 6.06 MPa,
    # +16 %, the deviation recorded in tests/test_psrk_mixture.py), which at the measured pressure is a bubble
    # temperature about 12.5 K low. The tolerance states the model's deviation; the exact check is the package's own bubble point.
    published = (333.15, 13.0, 'Sima et al. 2011, x_CO2 = 0.3317, 6.06 MPa (PSRK over-predicts the pressure by 16 %)')


class PengRobinsonPureIsobaric(IsobaricVessel, unittest.TestCase):
    """A pure vessel: the temperature holds on the saturation plateau, which is the normal boiling point."""
    package, cas, amounts = PR, [TO], [1.0]
    P, T0, Q, tf = 101325.0, 380.0, 300.0, 6.0
    published = (383.78, 1.0, 'NIST Chemistry WebBook, normal boiling point of toluene')

    def test_phase_appearance_is_the_bubble_point_of_the_package_and_of_the_data(self):
        events = [e for e in self.out['eventos'] if e['codigo'] == 'aparicion_fase']
        self.assertEqual(len(events), 1, self.out['eventos'])
        Tsat = brentq(lambda T: cubic_flash.pure_saturation(self.eos, 0, T)['P'] - self.P, 300.0, 590.0, xtol=1e-12)
        T = series(self.out, 'volumen.A.T')
        data, tol, source = self.published
        print(f'{self.package}: plateau T {T[-1]:.6f} K; package Tsat(P) {Tsat:.6f} K; published {data} K; '
              f'|T_plateau - Tsat| {abs(T[-1] - Tsat):.2e} K; |Tsat - published| {abs(Tsat - data):.3f} K')
        self.assertLess(abs(T[-1] - Tsat), 1e-6)
        self.assertLess(abs(Tsat - data), tol)


class RigidVessel:
    """Mixin: a closed rigid vessel filled with compressed liquid, heated by an imposed duty (UV closure)."""
    package = cas = amounts = T0 = Q = tf = P_guess = None
    samples = 2

    @classmethod
    def setUpClass(cls):
        cls.z = np.asarray(cls.amounts, dtype=float)
        cls.eos = eos_of(cls.package, cls.cas)
        T0 = cls.T0
        liquid = cubic_flash.flash_TP(cls.eos, T0, cls.P_guess, cls.z)
        assert len(liquid['phases']) == 1
        cls.V = 0.9995 * sum(p['n'] * p['v'] for p in liquid['phases'])        # slightly compressed liquid
        cls.result, cls.out = solve(request(cls.package, cls.cas, cls.amounts, T0, cls.Q, cls.tf, cls.samples, V=cls.V))
        cls.t = np.array(cls.out['tiempos'], dtype=float)
        # independent initial state: the pressure at which the one-phase liquid has volume V at T0
        total = lambda lnP: math.log(sum(p['n'] * p['v'] for p in cubic_flash.flash_TP(cls.eos, T0, math.exp(lnP), cls.z)['phases']) / cls.V)
        cls.P0 = math.exp(brentq(total, math.log(cls.P_guess), math.log(5e7), xtol=1e-14))
        st = cubic_flash.flash_TP(cls.eos, T0, cls.P0, cls.z)
        cls.U0 = sum(p['n'] * p['u'] for p in st['phases'])

    def test_rigid_closed_vessel_conserves_matter_volume_and_energy(self):
        for i in range(len(self.cas)):
            self.assertLess(float(np.max(np.abs(series(self.out, f'volumen.A.n.{i + 1}') - self.z[i]))), 1e-12)
        V = series(self.out, 'volumen.A.V')
        U = series(self.out, 'volumen.A.U')
        err = np.abs(U - (self.U0 + self.Q * self.t))
        print(f'{self.package}: initial P {series(self.out, "volumen.A.P")[0]:.3f} Pa vs {self.P0:.3f} Pa; '
              f'worst |V - V0| {np.max(np.abs(V - self.V)):.2e} m3, worst |U - (U0 + Q t)| {err.max():.2e} J')
        self.assertLess(float(np.max(np.abs(V - self.V))), 1e-12 * self.V)
        self.assertLess(float(err.max()), 1e-6 * abs(self.U0) + 1e-6)
        self.assertLess(abs(series(self.out, 'volumen.A.P')[0] / self.P0 - 1), 1e-7)

    def test_final_state_equals_the_steady_uv_flash(self):
        ref = cubic_flash.flash_UV(self.eos, self.U0 + self.Q * self.t[-1], self.V, self.z)
        T, P = series(self.out, 'volumen.A.T')[-1], series(self.out, 'volumen.A.P')[-1]
        print(f'{self.package}: final T {T:.9f} K, P {P:.3f} Pa; steady UV flash T {ref["T"]:.9f} K, P {ref["P"]:.3f} Pa; '
              f'|dT| {abs(T - ref["T"]):.2e} K, |dP|/P {abs(P / ref["P"] - 1):.2e}')
        self.assertLess(abs(T - ref['T']), 1e-6)
        self.assertLess(abs(P / ref['P'] - 1), 1e-7)
        self.assertGreater(T, self.T0)


class PengRobinsonRigid(RigidVessel, unittest.TestCase):
    package, cas, amounts = PR, [BZ, TO], [0.5, 0.5]
    T0, Q, tf, P_guess = 340.0, 300.0, 1.0, 1.0e5


class PsrkRigid(RigidVessel, unittest.TestCase):
    package, cas, amounts = PSRK, [BZ, TO], [0.5, 0.5]
    T0, Q, tf, P_guess = 340.0, 300.0, 1.0, 1.0e5


class LocatedRejections(unittest.TestCase):
    """No silent fallback to another package: each unsupported case stops with its cause."""

    def test_species_without_a_record_is_not_applicable(self):
        with self.assertRaises(pv.PaqueteNoAplicable) as cm:
            PaqueteEOS(PSRK, [CO2, '74-82-8'])
        self.assertIn('74-82-8', str(cm.exception))

    def test_pure_data_substitutions_are_refused(self):
        with self.assertRaises(pv.PaqueteNoAplicable):
            PaqueteEOS(PR, [BZ, TO], {'x': 1})

    def test_the_wire_validation_names_the_package_and_the_cause(self):
        value = request(PSRK, [CO2, '74-82-8'], [0.5, 0.5], 300.0, 100.0, 1.0, 2, P=1e6)
        validation, _ = wire.validar_v2(value)
        codes = {d['codigo'] for d in validation['diagnosticos']}
        self.assertIn('MOTOR_ENS_PAQUETE_NO_APLICABLE', codes, validation['diagnosticos'])

    def test_a_liquid_liquid_state_is_a_located_rejection(self):
        eos = psrk.PSRKMixture((CO2, ETOH))
        package = PaqueteEOS(PSRK, [CO2, ETOH])
        T, x = 333.15, np.array([0.3317, 0.6683])
        bub = psrk.bubble_pressure(eos, T, x)
        z = (x + bub['y']) / 2
        tp = package.estado('TP', T, bub['P'], z)
        with self.assertRaises(mz.FueraDeAlcance) as cm:
            package.estado('PH', bub['P'], tp.H - 8000.0 * float(z.sum()), z)
        self.assertEqual(cm.exception.datos['cause'], 'liquid_liquid_split')
        self.assertEqual(cm.exception.motivo, 'no_soportado')

    def test_a_temperature_below_the_alpha_range_is_a_located_rejection(self):
        package = PaqueteEOS(PSRK, [CO2, TO])
        with self.assertRaises(mz.FueraDeAlcance) as cm:
            package.estado('TP', 250.0, 1e6, np.array([0.2, 0.8]))
        self.assertEqual(cm.exception.datos['cause'], 'outside_package_window')
        self.assertIn('Mathias-Copeman', str(cm.exception))
        with self.assertRaises(mz.FueraDeAlcance) as cm:                       # and a pressure outside the window
            package.estado('TP', 320.0, 1e9, np.array([0.2, 0.8]))
        self.assertEqual(cm.exception.datos['cause'], 'outside_package_window')

    def test_liquid_only_species_are_refused_by_the_common_admission(self):
        from core.compilador.admission import validate
        from core.modelo import desde_ensamblaje_v2
        value = request(PR, [BZ, TO], [0.5, 0.5], 340.0, 100.0, 1.0, 2, P=1e5)
        # a liquid-only phase set is a mixture-package feature
        model = desde_ensamblaje_v2(value)
        model['volumenes'][0]['supuestos']['energia']['soloLiquido'] = True
        from core.compilador.compilador import AdmissionError
        with self.assertRaises(AdmissionError) as cm:
            validate(model)
        self.assertTrue(any('liquid-only' in row['message'] for row in cm.exception.diagnostics), cm.exception.diagnostics)


class PackageContract(unittest.TestCase):
    """The package interface the common compiler and the accounting use."""

    def test_capability_lists_both_packages_for_dynamic_volumes(self):
        caps = wire.capacidades_v2()
        listed = {p['modelo']['id']: p for p in caps['paquetesEos']}
        self.assertEqual(set(listed), {PR, PSRK})
        for entry in listed.values():
            self.assertTrue(entry['dinamica'])
            self.assertEqual(entry['modelo']['version'], '1')
            self.assertEqual(entry['operaciones'], ['TP', 'PH', 'UP', 'UV', 'TV'])
            self.assertFalse(next(c for c in entry['combinaciones'] if c['id'] == 'liquido_liquido')['publicada'])
        self.assertNotIn(PR, {p['modelo']['id'] for p in caps['paquetes']})          # the published list is unchanged
        self.assertIn(CO2, listed[PSRK]['componentesCAS'])

    def test_package_states_equal_the_steady_flash_and_publish_h_s_g_mu_consistently(self):
        for package in (PR, PSRK):
            p = PaqueteEOS(package, [BZ, TO])
            z = np.array([0.5, 0.5])
            e = p.estado('TP', 340.0, 1e5, z)
            ref = cubic_flash.flash_TP(eos_of(package, [BZ, TO]), 340.0, 1e5, z)
            self.assertEqual([f.id for f in e.fases], ['liquido-1'])
            self.assertLess(abs(e.H - sum(q['n'] * q['h'] for q in ref['phases'])), 1e-9)
            f = e.fases[0]
            self.assertLess(abs(f.g - (f.h - 340.0 * f.s)), 1e-8)            # g = h - T s on the shared reference
            self.assertLess(abs(f.g - float(np.dot(f.x, f.mu))), 1e-8)
            # every specification inverts the same state
            for spec, a, b in (('PH', 1e5, e.H), ('UV', e.U, e.V), ('TV', 340.0, e.V), ('UP', 1e5, e.U)):
                s = p.estado(spec, a, b, z)
                self.assertLess(abs(s.T - 340.0), 1e-6, spec)
                self.assertLess(abs(s.P / 1e5 - 1), 1e-6, spec)
            # a located state re-certifies without solving again
            c = p.certify_state(e)
            self.assertEqual([f.id for f in c.fases], ['liquido-1'])
            self.assertLess(abs(c.H - e.H), 1e-9)

    def test_two_phase_state_certification_and_signature(self):
        p = PaqueteEOS(PR, [BZ, TO])
        z = np.array([0.5, 0.5])
        eos = eos_of(PR, [BZ, TO])
        bub = cubic_flash.saturation(eos, z, P=69.5e3, kind='bubble')
        dew = cubic_flash.saturation(eos, z, P=69.5e3, kind='dew')
        T = 0.5 * (bub['T'] + dew['T'])
        e = p.estado('TP', T, 69.5e3, z)
        self.assertEqual([f.id for f in e.fases], ['vapor-1', 'liquido-1'])
        c = p.certify_state(e)
        self.assertEqual([f.id for f in c.fases], ['vapor-1', 'liquido-1'])
        self.assertLess(c.verificaciones['equilibrio'][0], cubic_flash.TOL_MU)
        self.assertEqual(p.estado('PH', 69.5e3, e.H, z).T, p.estado('PH', 69.5e3, e.H, z).T)
        self.assertLess(abs(p.estado('PH', 69.5e3, e.H, z).T - T), 1e-7)
        self.assertLess(abs(e.verificaciones['reconstruccion_material'][0]), 1e-12)


if __name__ == '__main__':
    unittest.main()
