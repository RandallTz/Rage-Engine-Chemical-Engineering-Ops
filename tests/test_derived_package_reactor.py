"""Package caloric inventory and equilibrium limit of a liquid-only batch reactor (F5-C2, F5-C3, F5-C4).

Fresh shared-law author (tests/derived_reactor_inputs.py); the reference uses a
different caloric route (Gibbs-Helmholtz on the package potentials) and DOP853.
"""
import unittest

import numpy as np

from derived_reactor_inputs import OWNER, REACTOR, SPECIES, author_reactor, reference_reactor
from core.compilador.derived import DerivedSystem, LoweringError, resolve_system


def _series(result):
    return {row['id']: np.array(row['valores']) for row in result['series']}


class PackageReactor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = author_reactor()
        cls.system = DerivedSystem(cls.model)
        cls.result = resolve_system(cls.system)
        cls.times = np.array(cls.result['ejes'][0]['valores'])
        cls.reference, cls.reference_T = reference_reactor(cls.times)

    def test_amounts_energy_and_temperature_against_independent_caloric_route(self):
        self.assertEqual(self.result['estado'], 'resuelto')
        closure = self.system.closures[0]
        self.assertEqual((closure.describe()['mode'], closure.spec, closure.anchor, closure.liquid_only), ('single_phase', 'UV', 'liquid', True))
        values = _series(self.result)
        ids = [row['quantityId'] for row in self.model['motores']['derivedExecution']['states']]
        for index in range(4):
            self.assertLess(np.max(abs(values['campo.' + ids[index]] - self.reference.y[index])), 1e-7)
        self.assertLess(np.max(abs(values['campo.' + ids[4]] - self.reference.y[4])) / abs(self.reference.y[4][0]), 1e-8)
        T = values['closure.' + OWNER + '.' + self.system.ids[closure.T]]
        self.assertLess(np.max(abs(T - self.reference_T)), 1e-5)
        # The reaction heat appears only through the package caloric inventory (no source term): a visible rise.
        self.assertGreater(T.max() - REACTOR['T0'], 1.0)
        # Mass action closed form for K = kf/kr: xi = 5 sqrt(K) / (1 + sqrt(K)).
        K = REACTOR['kf'] / REACTOR['kr']
        self.assertAlmostEqual(values['campo.' + ids[2]][-1], 5 * np.sqrt(K) / (1 + np.sqrt(K)), delta=1e-6)
        checks = {row['id']: row for row in self.result['verificaciones']}
        self.assertLessEqual(checks['thermodynamics.closure.' + OWNER]['valor'], checks['thermodynamics.closure.' + OWNER]['tolerancia'])
        self.assertLess(checks['conservation.matter.' + OWNER + '.total']['valor'], 1e-9)

    def test_reaction_heat_peak_resolved_on_the_first_minute(self):
        # The 3000 s grid samples every 50 s and misses the peak; resolve 0-60 s at 1 s against the reference.
        model = author_reactor(dict(REACTOR, tf=60.0))
        system = DerivedSystem(model)
        result = resolve_system(system)
        self.assertEqual(result['estado'], 'resuelto')
        times = np.array(result['ejes'][0]['valores'])
        self.assertAlmostEqual(times[1] - times[0], 1.0)
        closure = system.closures[0]
        T = _series(result)['closure.' + OWNER + '.' + system.ids[closure.T]]
        _, reference_T = reference_reactor(times)
        self.assertLess(np.max(abs(T - reference_T)), 1e-5)
        peak = int(np.argmax(T))
        self.assertEqual(peak, int(np.argmax(reference_T)))
        self.assertTrue(6.0 <= times[peak] <= 10.0, times[peak])
        self.assertAlmostEqual(T[peak], 337.1757, delta=0.05)
        self.assertLess(T[-1], T[peak])

    def test_equilibrium_limit_row_against_gibbs_minimisation(self):
        from core import mezclas
        from core.reactions import chemical_equilibrium as ce
        row = next(v for v in self.result['verificaciones'] if v['id'] == 'reactions.equilibrium_limit.' + OWNER)
        detail = self.result['procedencia']['reactionEquilibrium'][0]
        phase = ce.PackagePhase(mezclas.Sistema('unifac-dortmund-public', list(SPECIES), solo_liquido=True), 'liquido', anchor='liquid')
        n0 = np.array(REACTOR['n0'])
        A = np.array([[2, 2, 4, 0], [6, 4, 8, 2], [1, 2, 2, 1]], dtype=float)
        gibbs = ce.minimise_gibbs(phase, [[-1, -1, 1, 1]], n0, detail['T'], detail['P'], A)
        np.testing.assert_allclose(detail['equilibriumAmounts'], gibbs['moles'], rtol=0, atol=1e-7)
        expected = np.max(np.abs(np.array(detail['finalAmounts']) - np.array(gibbs['moles']))) / n0.sum()
        self.assertAlmostEqual(row['valor'], expected, delta=1e-7)
        # These rate constants are not in detailed balance with the package K(T): the row reports it.
        self.assertGreater(row['valor'], row['tolerancia'])
        self.assertFalse(detail['kineticStateCertified'])
        # Affinity / RT = -ln K + sum_i nu_i (ln x_i + ln gamma_i), from the package activities directly.
        s = mezclas.Sistema('unifac-dortmund-public', list(SPECIES), solo_liquido=True)
        n = np.array(detail['finalAmounts']); x = n / n.sum()
        lng = np.asarray(s._lngamma(detail['T'], x, list(range(4))), dtype=float)
        nu = np.array([-1, -1, 1, 1])
        self.assertAlmostEqual(detail['affinityRT'][0], -detail['lnK'][0] + float(nu @ (np.log(x) + lng)), delta=1e-6)
        self.assertLess(abs(detail['reactionEnthalpy'][0]), 2e4)


class LiquidOnlyAdmission(unittest.TestCase):
    def test_acetic_acid_without_liquid_only_assumption_is_rejected(self):
        with self.assertRaises(LoweringError) as caught:
            DerivedSystem(author_reactor(journal_extra=('liquid_formation_reference',)))
        row = caught.exception.diagnostics[0]
        self.assertEqual(row['code'], 'liquid_only_species')
        self.assertEqual((row['detail']['tipo'], row['detail']['nativeCode']), ('fase_vapor', 'ESPECIE_SOLO_LIQUIDO'))

    def test_gas_formation_reference_is_refused_for_liquid_only_species(self):
        with self.assertRaises(LoweringError) as caught:
            DerivedSystem(author_reactor(journal_extra=('liquid_only', 'gas_formation_reference')))
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'closure_liquid_anchor_required')

    def test_reacting_package_volume_needs_a_formation_reference(self):
        with self.assertRaises(LoweringError) as caught:
            DerivedSystem(author_reactor(journal_extra=('liquid_only',)))
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'formation_reference_required')


class CompiledAdmission(unittest.TestCase):
    """F5-C4 on the compiled flash path: VLE rejects acetic acid; liquid-only admits it but not a flash."""

    def _codes(self, extra):
        from core.compilador import admission
        from core.compilador.compilador import AdmissionError
        from derived_reactor_inputs import reactor_model
        with self.assertRaises(AdmissionError) as caught:
            admission.validate(reactor_model(journal_extra=extra), initialization=False)
        return {(row['code'], row['nativeCode']) for row in caught.exception.diagnostics}

    def test_vapour_liquid_model_still_rejects_acetic_acid(self):
        self.assertIn(('unsupported_package', 'MOTOR_ENS_ESPECIE_SOLO_LIQUIDO'), self._codes(('liquid_formation_reference',)))

    def test_liquid_only_model_admits_the_species_and_rejects_the_flash(self):
        codes = self._codes(('liquid_only', 'liquid_formation_reference'))
        self.assertIn(('liquid_only_vapour_operation', 'MOTOR_ENS_ESPECIE_SOLO_LIQUIDO'), codes)
        self.assertNotIn(('unsupported_package', 'MOTOR_ENS_ESPECIE_SOLO_LIQUIDO'), codes)

    def test_liquid_only_requires_the_single_liquid_policy(self):
        from core.mathematics.errors import MathematicsError
        from derived_reactor_inputs import reactor_model
        policy = {'cantidad': 'sin_restriccion', 'cambioInterno': 'permitido', 'evaluacion': 'equilibrio_estable'}
        with self.assertRaises(MathematicsError):
            reactor_model(journal_extra=('liquid_only',), policy=policy)


if __name__ == '__main__':
    unittest.main()
