"""Demo 0.3 C2: declared time inputs held as zero-rate pseudo-states.

A time input is a Model quantity that depends on time only; Solve declares it
with the datum of its starting value. Without actions it must reproduce the
scalar datum binding of the same quantity within 10 rtol. Selections without
the key are read and lowered exactly as before. A symbol, a package-closure
pressure and a scaled formulation are located rejections.

References are independent: the heated region is checked against the
hand-integrated T(t) = T0 + P t / (m c); the CSTR variant against the scalar
binding and the shipped fixture. No floating-point hash is committed.
"""
import copy
from pathlib import Path
import sys
import unittest

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from test_control_kernel import Author, OWNER, T, U, Q, MASS, t
from core.compilador.derived import DerivedSystem, LoweringError, resolve_system, source_signature
from core.mathematics.dimensions import catalog
from core.mathematics.session import replay_operations
from core.modelo.derived_execution import read_definition
from core.modelo.equation_workbench import _known_unit, _source_graph, build

POWER, T0, HEAT_CAPACITY, HORIZON, RTOL = 50., 300., 2 * 500., 600., 1e-9


def heated_region():
    """A closed rigid region whose only heat exchange is a declared duty Q_d(t)."""
    author = Author()
    author.append('declare_function', name='heaterDuty', unit='W', dependencies=[author.quantity(t)])
    author.append('declare_symbol', name='heaterPower', unit='W')
    heat = author.append('declare_relation', left=author.quantity(Q), right='heaterDuty', relationKind='constraint',
                         reason='The declared heater duty is the only heat exchange of the region')
    balance = next(key for key in author.selected if key.startswith('energy.' + OWNER + '.')
                   and author.source.nodes[key].equation.lhs == sp.diff(U, t))
    energy = author.append('substitute', sources=[balance], relation=heat, symbol=author.quantity(Q))
    return author, energy


def selection_model(author, energy, inputs=None, parameters=None, scaling=False):
    model = copy.deepcopy(author.model)
    model['motores']['equationWorkbench'] = copy.deepcopy(author.definition)
    replayed = build(model)
    quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    named = lambda name: next(key for key, value in quantities.items() if str(value) == name)
    def datum(key, value, unit, role='parametro'):
        model['datos'][key] = {'magnitud': key, 'funcion': role, 'declaracion': {'texto': str(value), 'unidad': unit},
                               'origen': {'propietarioId': 'estudio', 'ruta': key}}
        return key
    volume = model['volumenes'][0]
    caloric = 'thermodynamics.' + OWNER + '.caloric-inventory'
    mass_row = next(key for key in replayed.selected if isinstance(replayed.graph.nodes[key].equation, sp.Equality)
                    and replayed.graph.nodes[key].equation.lhs == sp.diff(MASS, t))
    selection = {'format': 'rage.derived-execution', 'version': 1, 'sourceSignature': source_signature(model, replayed),
                 'timeId': named('t'), 'states': [{'quantityId': named(str(MASS)), 'equationId': mass_row},
                                                  {'quantityId': named(str(U)), 'equationId': energy}],
                 'parameters': {}, 'initialValues': {named(str(MASS)): volume['inicial']['cantidades']['datoIds']['1'],
                                                     named(str(T)): volume['inicial']['energia']['datoId']},
                 'initialEquations': [caloric], 'reconstructions': [
                     {'quantityId': named(str(T)), 'equationId': caloric},
                     {'quantityId': named('m_total__' + OWNER + '(t)'), 'equationId': 'matter.' + OWNER + '.total-definition'}],
                 'checks': []}
    for prefix, key in [('caloric_capacity', 'cId'), ('T_reference', 'TRefId'), ('u_reference', 'uRefId')]:
        selection['parameters'][named(prefix + '__' + OWNER)] = volume['termodinamica']['parametros'][key]
    duty = datum('solve.heaterDuty', POWER, 'W')
    for name in parameters or ():
        selection['parameters'][name] = duty if name == 'heaterDuty' else datum('solve.' + name, POWER, 'W')
    if inputs:
        selection['timeInputs'] = {name: duty if name == 'heaterDuty' else datum('solve.' + name, POWER, 'W') for name in inputs}
    if scaling:
        selection['scaling'] = {key: datum('scale.' + key, 1, unit) for key, unit in
                                [(selection['timeId'], 's'), (named(str(MASS)), 'kg'), (named(str(U)), 'J')]}
    model['datos'][volume['inicial']['energia']['datoId']]['declaracion']['texto'] = str(T0)
    horizon = datum('solve.finalTime', HORIZON, 's', 'estudio')
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': horizon, 'metodoSolicitado': 'rk45', 'muestras': 61,
                        'rtol': RTOL, 'atol': {'cantidad': 1e-11, 'energia': 1e-6}}
    model['motores']['derivedExecution'] = selection
    return model


def series(result):
    return {row['id']: np.asarray(row['valores'], dtype=float) for row in result['series']}


def assert_solver_tolerance(reference_system, reference, held, rtol, label=''):
    """Within 10 rtol in the solver's own error weights, |d| <= 10 (rtol |y| + atol).

    A held input enters the error norm, so the step sequence differs from the
    scalar binding (design DR-5); agreement is at solver tolerance, never bit-exact.
    """
    for index, qid in enumerate(reference_system.state_ids):
        expected, actual = reference['campo.' + qid], held['campo.' + qid]
        bound = 10 * (rtol * np.abs(expected) + float(reference_system.numeric.atol[index]))
        excess = np.abs(actual - expected) - bound
        assert float(np.max(excess)) <= 0, (label, qid, float(np.max(np.abs(actual - expected))), float(np.max(bound)))


def rejected(test, code, model):
    with test.assertRaises(LoweringError) as caught:
        DerivedSystem(model)
    test.assertEqual(caught.exception.diagnostics[0]['code'], code, caught.exception.diagnostics)
    return caught.exception.diagnostics[0]


class TimeInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.author, cls.energy = heated_region()

    def test_without_actions_equals_the_scalar_binding_and_the_exact_heating(self):
        runs = {}
        for name, kwargs in [('scalar', {'parameters': ['heaterDuty']}), ('held', {'inputs': ['heaterDuty']})]:
            system = DerivedSystem(selection_model(self.author, self.energy, **kwargs))
            for method in ('RK45', 'BDF'):
                system.method = method; system.model['estudio']['metodoSolicitado'] = method.lower()
                system.report = system._report()
                result = resolve_system(system)
                self.assertEqual(result['estado'], 'resuelto')
                runs[name, method] = (system, result)
        held, _ = runs['held', 'RK45']
        self.assertEqual(held.state_ids[-1], 'heaterDuty')
        self.assertEqual(held.rates[sp.Derivative(held.quantities['heaterDuty'], t)], 0)
        self.assertEqual(held.report['equations'][-1]['id'], 'timeInput.heaterDuty')
        temperature = next(row['quantityId'] for row in held.selection['reconstructions'] if str(held.quantities[row['quantityId']]) == str(T))
        for method in ('RK45', 'BDF'):
            scalar, held_result = series(runs['scalar', method][1]), series(runs['held', method][1])
            times = np.asarray(runs['held', method][1]['ejes'][0]['valores'])
            # Published as an ordinary series, constant without actions.
            np.testing.assert_array_equal(held_result['campo.heaterDuty'], np.full_like(times, POWER))
            assert_solver_tolerance(runs['scalar', method][0], scalar, held_result, RTOL, method)
            exact = T0 + POWER * times / HEAT_CAPACITY
            np.testing.assert_allclose(held_result['observable.' + temperature], exact, rtol=10 * RTOL)

    def test_selections_without_the_key_are_unchanged(self):
        model = selection_model(self.author, self.energy, parameters=['heaterDuty'])
        selection = model['motores']['derivedExecution']
        self.assertIs(read_definition(selection, model), selection)
        system = DerivedSystem(model)
        self.assertEqual(system.state_rows, selection['states'])
        self.assertEqual(system.time_input_quantities, [])
        self.assertEqual(system.state_ids, [row['quantityId'] for row in selection['states']])
        self.assertFalse(any(row['id'].startswith('timeInput.') for row in system.report['equations']))
        self.assertNotIn('timeInputs', system.report['derivedExecution']['selection'])

    def test_reader_rejects_shared_ownership_and_empty_inputs(self):
        model = selection_model(self.author, self.energy, inputs=['heaterDuty'])
        for change in [lambda s: s['parameters'].update(heaterDuty=s['timeInputs']['heaterDuty']),
                       lambda s: s['initialValues'].update(heaterDuty=s['timeInputs']['heaterDuty']),
                       lambda s: s.update(timeInputs={}),
                       lambda s: s['timeInputs'].update(heaterDuty='solve.missing')]:
            bad = copy.deepcopy(model); change(bad['motores']['derivedExecution'])
            with self.assertRaises(ValueError):
                read_definition(bad['motores']['derivedExecution'], bad)

    def test_a_declared_symbol_cannot_be_a_time_input(self):
        row = rejected(self, 'time_input_constant', selection_model(self.author, self.energy, inputs=['heaterPower'], parameters=['heaterDuty']))
        self.assertEqual(row['path'], 'motores.derivedExecution.timeInputs.heaterPower')

    def test_a_scaled_formulation_is_rejected(self):
        rejected(self, 'time_input_scaling', selection_model(self.author, self.energy, inputs=['heaterDuty'], scaling=True))


class ContinuousReactorTimeInputTests(unittest.TestCase):
    """The accepted Demo 0.2 CSTR (version 1, package closure, kinetics)."""

    @classmethod
    def setUpClass(cls):
        from demo02_cstr import frozen_model
        cls.frozen = frozen_model()
        replayed = build(cls.frozen)
        quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
        old = next(k for k, v in quantities.items() if v == replayed.introduced['jacketTemperature'] and k != 'jacketTemperature')
        time_id = next(k for k, v in quantities.items() if str(v) == 't')
        # Replay the recorded history with the jacket temperature declared as a
        # quantity of time instead of a constant; every later operation is the
        # recorded one, and each is re-pinned to its replayed input equations.
        definition = copy.deepcopy(cls.frozen['motores']['equationWorkbench'])
        for op in definition['operations']:
            op.pop('sourceSignatures', None)
            if op.get('name') == 'jacketTemperature':
                op.update(kind='declare_function', dependencies=[time_id])
        source, selected, locations, units = _source_graph(cls.frozen)
        unsigned = replay_operations(source, selected, locations, units, definition, require_same_family=True, unit_resolver=_known_unit)
        for op, receipt in zip(definition['operations'], unsigned.receipts):
            if receipt.calculated_input_signatures:
                op['sourceSignatures'] = dict(receipt.calculated_input_signatures)
        variant = copy.deepcopy(cls.frozen); variant['motores']['equationWorkbench'] = definition
        replayed = build(variant)
        quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
        cls.jacket = next(k for k, v in quantities.items() if v == replayed.introduced['jacketTemperature'] and k != 'jacketTemperature')
        cls.pressure = next(k for k, v in quantities.items() if str(v) == 'P__cell(t)')
        selection = variant['motores']['derivedExecution']
        cls.data = selection['parameters'].pop(old)
        selection['sourceSignature'] = source_signature(variant, replayed)
        cls.variant = variant

    def model(self, held):
        model = copy.deepcopy(self.variant)
        selection = model['motores']['derivedExecution']
        if held:
            selection['timeInputs'] = {self.jacket: self.data}
        else:
            selection['parameters'][self.jacket] = self.data
        return model

    def test_cstr_accepts_a_held_jacket_temperature(self):
        runs = {}
        for name, model in [('frozen', self.frozen), ('scalar', self.model(False)), ('held', self.model(True))]:
            system = DerivedSystem(copy.deepcopy(model))
            result = resolve_system(system)
            self.assertEqual(result['estado'], 'resuelto')
            runs[name] = (system, series(result))
        system, held = runs['held']
        self.assertEqual(system.state_ids[-1], self.jacket)
        np.testing.assert_array_equal(held['campo.' + self.jacket], np.full_like(held['campo.' + self.jacket], 340.))
        rtol = self.frozen['estudio']['rtol']
        # The re-recorded variant with a scalar datum reproduces the shipped model
        # (equal equations; compared at round-off, not bit for bit).
        frozen = runs['frozen'][1]
        for key, values in runs['scalar'][1].items():
            scale = float(np.nanmax(np.abs(values))) if np.isfinite(values).any() else 0.
            np.testing.assert_allclose(values, frozen[key], rtol=1e-12, atol=1e-12 * scale, equal_nan=True, err_msg=key)
        for reference in ('scalar', 'frozen'):
            assert_solver_tolerance(runs[reference][0], runs[reference][1], held, rtol, reference)

    def test_closure_pressure_cannot_be_a_time_input(self):
        model = self.model(False)
        selection = model['motores']['derivedExecution']
        selection['timeInputs'] = {self.pressure: selection['parameters'].pop(self.pressure)}
        rejected(self, 'time_input_closure', model)

    def test_a_constant_of_the_cstr_cannot_be_a_time_input(self):
        model = copy.deepcopy(self.frozen)
        selection = model['motores']['derivedExecution']
        feed = next(k for k, v in selection['parameters'].items() if v == 'solve.F')
        selection['timeInputs'] = {feed: selection['parameters'].pop(feed)}
        rejected(self, 'time_input_constant', model)


def with_held_input(model, author):
    """Append heldInput(t) through the shared session and declare it a time input.

    Returns the model without the key (same history) and the one with it, so the
    only difference between the two runs is the declaration in Solve.
    """
    author.append('declare_function', family='thermodynamics', name='heldInput', unit='W', dependencies=[author.quantity(t)])
    model = copy.deepcopy(model); model['motores']['equationWorkbench'] = copy.deepcopy(author.definition)
    replayed = build(model)
    model['motores']['derivedExecution']['sourceSignature'] = source_signature(model, replayed)
    names = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    qid = next(k for k, v in names.items() if str(v) == 'heldInput(t)')
    model['datos']['solve.held'] = {'magnitud': 'solve.held', 'funcion': 'parametro', 'declaracion': {'texto': '250', 'unidad': 'W'},
                                    'origen': {'propietarioId': 'estudio', 'ruta': 'solve.held'}}
    held = copy.deepcopy(model); held['motores']['derivedExecution']['timeInputs'] = {qid: 'solve.held'}
    return model, held, qid


def bound_input(model, qid, lower=0, upper=1000):
    for key, value in [('lowerDataId', lower), ('upperDataId', upper)]:
        model['datos']['dae.input.' + key] = {'magnitud': 'dae.input.' + key, 'funcion': 'parametro',
            'declaracion': {'texto': str(value), 'unidad': 'W'}, 'origen': {'propietarioId': 'estudio', 'ruta': 'dae.input.' + key}}
    model['motores']['derivedExecution']['dae']['stateBounds'][qid] = {'lowerDataId': 'dae.input.lowerDataId', 'upperDataId': 'dae.input.upperDataId'}
    return model


class BlockVersionTimeInputTests(unittest.TestCase):
    """C2-R1, C2-R2 and C2-N1: one held input on selection versions 2, 3 and 4."""

    def compare(self, base, held, qid):
        reference = DerivedSystem(copy.deepcopy(base)); expected = resolve_system(reference)
        system = DerivedSystem(copy.deepcopy(held)); result = resolve_system(system)
        self.assertEqual((expected['estado'], result['estado']), ('resuelto', 'resuelto'))
        self.assertEqual(system.state_ids[-1], qid)
        self.assertEqual(system.size, reference.size + 1)
        values = series(result)
        np.testing.assert_array_equal(values['campo.' + qid], np.full_like(values['campo.' + qid], 250.))
        assert_solver_tolerance(reference, series(expected), values, held['estudio']['rtol'])
        # Only the held series is added.
        self.assertEqual(set(values) - set(series(expected)), {'campo.' + qid})
        return system

    def test_version_2_affine_block(self):
        from test_f3_affine_algebraic import thermal_case
        model, author = thermal_case()
        self.assertEqual(model['motores']['derivedExecution']['version'], 2)
        system = self.compare(*with_held_input(model, author))
        self.assertEqual(len(system.runtime_rates), system.size)
        self.assertEqual(system.report['equations'][-1]['id'], 'timeInput.' + system.state_ids[-1])

    def test_version_3_nonlinear_block(self):
        from test_f3_nonlinear_algebraic import thermal_case
        model, author = thermal_case()
        self.assertEqual(model['motores']['derivedExecution']['version'], 3)
        self.compare(*with_held_input(model, author))

    def test_version_4_index_one_dae(self):
        import test_f3_index1_dae as dae
        from test_f3_nonlinear_algebraic import thermal_case
        store = {}
        def held_case(owners=('domain_one', 'domain_two')):
            model, author = thermal_case(owners)
            base, held, store['qid'] = with_held_input(model, author)
            return held, author
        base = dae.dae_case()
        original = dae.thermal_case
        dae.thermal_case = held_case
        try:
            held = dae.dae_case()
        finally:
            dae.thermal_case = original
        qid = store['qid']
        selection = held['motores']['derivedExecution']
        self.assertEqual(selection['version'], 4)
        # The reader requires a bound for the input: the certificate must cover
        # every value an action may give it, not only the starting datum.
        with self.assertRaises(ValueError):
            read_definition(selection, held)
        bound_input(held, qid)
        self.assertIs(read_definition(selection, held), selection)
        system = self.compare(base, held, qid)
        self.assertEqual(system.dae.proof['timeInputBounds'], {qid: ['0', '1000']})
        # A held value outside its declared box is a located domain failure.
        outside = bound_input(copy.deepcopy(held), qid, 0, 100)
        with self.assertRaises(LoweringError) as caught:
            DerivedSystem(outside)
        self.assertEqual(caught.exception.diagnostics[0]['code'], 'dae_domain', caught.exception.diagnostics)


if __name__ == '__main__':
    unittest.main()
