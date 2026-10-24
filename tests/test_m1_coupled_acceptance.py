"""Frozen M1-A/B deduction regression evidence, never U1 acceptance.

Run from the repository root. The audit checks actual-expression commutation on the energy dependency proof
and explicit Cauchy inputs for storage; deferred premises remain visible.
"""
import copy
import json
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import numpy as np
import sympy as sp
from scipy.linalg import expm

from m1_acceptance import author_mixing, author_hydraulic, MIXING_REFERENCE, HYDRAULIC_REFERENCE
from core.balances import energy_derivation as energy, material_derivation as material, momentum_derivation as momentum
from core.balances.material_equations import equation_graph as material_graph
from core.balances.energy_equations import equation_graph as energy_graph
from core.termodinamica import derivation as thermodynamics
from core.termodinamica.equations import equation_graph as thermodynamic_graph
from core.mathematics.dimensions import dimension
from core.mathematics.errors import MathematicsError
from core.modelo import leer_modelo_comun
from core.modelo.equation_workbench import build, describe, describe_for_authoring, edit, ensure_executable, _known_unit, _source_graph
from core.compilador.presentation import formulation_summary


def ancestors(graph, key):
    return {key} | set().union(*(ancestors(graph, parent) for parent in graph.nodes[key].inputs))


class CoupledAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = {}
        for name, author, reference in [('a', author_mixing, MIXING_REFERENCE),
                                         ('b', author_hydraulic, HYDRAULIC_REFERENCE)]:
            print('Authoring M1-' + name.upper() + ' through shared operations', flush=True)
            model, result, outputs = author()
            cls.documents[name] = (model, result, outputs, reference)
        cls.t = sp.Symbol('t', real=True)

    def test_frozen_inputs_are_reproduced_by_shared_authoring(self):
        for name, (model, result, outputs, reference) in self.documents.items():
            with self.subTest(document=name):
                frozen = json.loads((ROOT / f'tests/reference_data/m1-{name}.json').read_text(encoding='utf8'))
                self.assertEqual(frozen, {'version': 1, 'model': model,
                    'selectedEquations': outputs, 'reference': reference})
                self.assertEqual(leer_modelo_comun(json.loads(json.dumps(model))), model)
                rebuilt = build(model)
                for key in outputs.values():
                    self.assertEqual(rebuilt.graph.nodes[key].equation, result.graph.nodes[key].equation)
                for receipt in result.receipts:
                    if receipt.before:
                        self.assertTrue(receipt.input_signatures)
                    self.assertTrue(receipt.after or receipt.declared_quantities)

    def test_mixing_ancestry_and_dependent_total_mass(self):
        _, result, outputs, _ = self.documents['a']
        for index in (1, 2):
            self.assertIn(f'matter.mixture.{index}.local', ancestors(result.graph, outputs[f'mass.{index}']))
        chain = ancestors(result.graph, outputs['temperature'])
        for key in ('energy.mixture.local', 'energy.mixture.enthalpy-definition',
                    'thermodynamics.mixture.caloric', 'thermodynamics.mixture.specific-inventory',
                    'matter.mixture.1.local', 'matter.mixture.2.local'):
            self.assertIn(key, chain)
        total = result.graph.nodes[outputs['totalMass']]
        self.assertTrue(total.dependent)
        self.assertEqual(sp.simplify(total.equation.rhs), 0)
        self.assertEqual(len(total.equation.lhs.atoms(sp.Derivative)), 2)

    def test_mixing_independent_analytic_reference_and_mass_mole_distinction(self):
        _, result, outputs, _ = self.documents['a']
        t = self.t
        # Hand solution: residence time 100 s, final temperature 330 + Q/(F*c).
        decay = sp.exp(-t / 100)
        masses = [7 - 5*decay, 3 + 5*decay]
        temperature = 350 - 50*decay
        substitutions = {
            sp.Function('m__mixture__1')(t): masses[0],
            sp.Function('m__mixture__2')(t): masses[1],
            sp.Function('T__mixture')(t): temperature,
            sp.Symbol('feedRate', real=True): sp.Rational(1, 10),
            sp.Symbol('feedFraction', real=True): sp.Rational(7, 10),
            sp.Symbol('feedTemperature', real=True): 330,
            sp.Symbol('suppliedHeat', real=True): 2000,
            sp.Symbol('specificFlowWork', real=True): 100,
            sp.Symbol('caloric_capacity__mixture', real=True): 1000,
            sp.Symbol('T_reference__mixture', real=True): 300,
            sp.Symbol('u_reference__mixture', real=True): 0,
            sp.Symbol('molarMass1', real=True): sp.Rational(1, 50),
            sp.Symbol('molarMass2', real=True): sp.Rational(1, 20),
        }
        references = {'mass.1': sp.diff(masses[0], t), 'mass.2': sp.diff(masses[1], t),
                      'temperature': sp.diff(temperature, t),
                      'energy': sp.diff(10000*(temperature-300), t)}
        for name, expected in references.items():
            actual = result.graph.nodes[outputs[name]].equation.rhs.subs(substitutions)
            self.assertEqual(sp.simplify(actual - expected), 0)
            for instant in np.linspace(0, 600, 121):
                self.assertLess(abs(float((actual-expected).subs(t, instant))), 1e-10)
        amounts = [result.graph.nodes[outputs[f'amount.{i}']].equation.rhs.subs(substitutions)
                   for i in (1, 2)]
        self.assertEqual(sp.simplify(sum(masses)), 10)
        self.assertEqual(sp.simplify(sp.diff(sum(amounts), t)), sp.Rational(3, 2)*decay)
        self.assertEqual(sum(amounts).subs(t, 0), 260)
        self.assertEqual(sp.simplify(amounts[0]/sum(amounts)).subs(t, 0), sp.Rational(5, 13))

    def test_hydraulic_independent_matrix_reference_cancellation_and_dissipation(self):
        _, result, outputs, ref = self.documents['b']
        area = math.pi * ref['diameter']**2 / 4
        inertance = ref['length'] / area
        resistance = 128*ref['viscosity']*ref['length']/(math.pi*ref['density']*ref['diameter']**4)
        g = ref['gravity']
        matrix = np.array([[0, 0, -1], [0, 0, 1],
            [g/.02/inertance, -g/.02/inertance, -resistance/inertance]])
        fixed = {sp.Symbol(name + '__channel', real=True): value for name, value in
            [('A', area), ('L', 10), ('rho', 1000), ('mu', .05)]}
        for owner in ('upper', 'lower'):
            fixed.update({sp.Symbol('g__'+owner, real=True): g,
                sp.Symbol('A_v__'+owner, real=True): .02,
                sp.Symbol('rho__'+owner, real=True): 1000,
                sp.Function('p_r__'+owner)(self.t): 101325})
        for initial in ([40., 10., 0.], [10., 40., 0.], [25., 25., 0.]):
            for instant in np.linspace(0, 600, 121):
                state = expm(matrix*instant) @ np.array(initial)
                expected = matrix @ state
                values = {**fixed, sp.Function('m__upper__1')(self.t): state[0],
                    sp.Function('m__lower__1')(self.t): state[1],
                    sp.Function('q__s1__1')(self.t): state[2]}
                for index, name in enumerate(('upper.mass', 'lower.mass', 'flow')):
                    actual = float(result.graph.nodes[outputs[name]].equation.rhs.subs(values))
                    self.assertAlmostEqual(actual, expected[index], delta=1e-10)
                self.assertAlmostEqual(sum(state[:2]), 50, delta=1e-9)
                self.assertGreaterEqual(resistance*state[2]**2/ref['density'], 0)
                reynolds = abs(state[2])*ref['diameter']/(ref['viscosity']*area)
                self.assertLess(reynolds, ref['maximumReynolds'])
                self.assertGreater(101325 + g*min(state[:2])/.02, ref['minimumPressure'])
                for index, owner in enumerate(('upper', 'lower')):
                    values[sp.Function('m_total__'+owner)(self.t)] = state[index]
                    pressure = float(result.graph.nodes[outputs[owner+'.pressure']].equation.rhs.subs(values))
                    height = float(result.graph.nodes[outputs[owner+'.height']].equation.rhs.subs(values))
                    self.assertAlmostEqual(pressure, 101325+g*state[index]/.02, delta=1e-8)
                    self.assertAlmostEqual(height, state[index]/20, delta=1e-12)
        self.assertEqual(sp.simplify(result.graph.nodes[outputs['totalMass']].equation.rhs), 0)
        chain = ancestors(result.graph, outputs['flow'])
        self.assertIn('momentum.channel.local.x', chain)
        self.assertIn('momentum.channel.path.inventory-rate', chain)
        self.assertIn('momentum.channel.wall.area-form', chain)

    def test_selected_rate_units_and_validity_are_explicit(self):
        for name, (_, result, outputs, _) in self.documents.items():
            selected = ('mass.1', 'mass.2', 'energy', 'temperature') if name == 'a' else ('upper.mass', 'lower.mass', 'flow')
            for key in selected:
                equation = result.graph.nodes[outputs[key]].equation
                left = dimension(equation.lhs, result.units, _known_unit)
                self.assertIsNotNone(left)
                self.assertEqual(left, dimension(equation.rhs, result.units, _known_unit))
            self.assertTrue(result.graph.domains)
            key = outputs['temperature' if name == 'a' else 'flow']
            self.assertTrue(result.graph.predicates_for(key))

    def test_transform_exact_rows_and_no_older_numerical_fallback(self):
        publications = []
        for model, _, outputs, _ in self.documents.values():
            report = describe(model)
            summary = formulation_summary(model)
            rows = [row for family in summary['families'] for volume in family['volumes'] for row in volume['steps']]
            for key in outputs.values():
                self.assertIn(next(row for row in report['equations'] if row['id'] == key), rows)
            self.assertFalse(report['execution']['supported'])
            with self.assertRaises(MathematicsError):
                ensure_executable(model)
            publications.append(report)
        for name, report in zip(('a', 'b'), publications):
            (ROOT / f'.tmp/m1-{name}-publication.json').write_text(json.dumps(report), encoding='utf8')

    def test_closure_edits_remain_inspectable_and_reject_stale_inputs(self):
        for model, _, _, _ in self.documents.values():
            changed = copy.deepcopy(model)
            definition = changed['motores']['equationWorkbench']
            relation = next(op for op in definition['operations'] if op['kind'] == 'declare_relation')
            relation['right'] = '2*(' + relation['right'] + ')'
            before = copy.deepcopy(definition)
            report = describe_for_authoring(changed)
            self.assertIn('replay', report)
            self.assertEqual(report['definition'], before)
            self.assertFalse(report['execution']['supported'])
            with self.assertRaises(MathematicsError):
                formulation_summary(changed)
            missing = copy.deepcopy(model)
            operations = missing['motores']['equationWorkbench']['operations']
            index = next(i for i, op in enumerate(operations) if op['kind'] == 'declare_relation')
            operations.pop(index)
            missing['motores']['equationWorkbench']['cursor'] -= 1
            recovery = describe_for_authoring(missing)
            self.assertIn('replay', recovery)
            self.assertEqual(recovery['definition'], missing['motores']['equationWorkbench'])
            self.assertFalse(recovery['execution']['supported'])
            with self.assertRaises(MathematicsError):
                ensure_executable(missing)

    def test_undo_redo_and_display_labels_preserve_exact_history(self):
        for model, result, outputs, _ in self.documents.values():
            changed = copy.deepcopy(model)
            changed['motores']['equationWorkbench'] = edit(model, {'kind': 'undo'})['definition']
            self.assertEqual(edit(changed, {'kind': 'redo'})['definition'], result.definition)
            changed = copy.deepcopy(model)
            changed['nombre'] = 'Neutral application label'
            changed['componentes'][0].update(nombre='Neutral material label', simbolo='X')
            rebuilt = build(changed)
            for key in outputs.values():
                self.assertEqual(rebuilt.graph.nodes[key].equation, result.graph.nodes[key].equation)

    def test_used_physical_assumption_removal_blocks_stale_consumers(self):
        for name, (model, _, _, _) in self.documents.items():
            changed = copy.deepcopy(model)
            namespace, owner, flag = ('energyDerivation', 'mixture', 'sinFuenteVolumetrica') if name == 'a' else (
                'momentumDerivation', 'channel', 'noSlipWall')
            operations = changed['motores'][namespace]['volumes'][owner]['operations']
            operations[:] = [op for op in operations if not op['changes'].get(flag)]
            report = describe_for_authoring(changed)
            self.assertIn('replay', report)
            self.assertFalse(report['execution']['supported'])
            self.assertTrue(report['equations'])
            with self.assertRaises(MathematicsError):
                ensure_executable(changed)

    def test_d1_storage_reaches_all_local_cauchy_components_and_wall_is_a_premise(self):
        model = self.documents['b'][0]
        graph = _source_graph(model)[0]
        for owner in ('upper', 'lower'):
            prefix = 'momentum.' + owner + '.'
            chain = ancestors(graph, prefix + 'storage.port-pressure')
            for axis in 'xyz':
                self.assertIn(prefix + 'local.' + axis, chain)
                self.assertIn(prefix + 'local.' + axis + '.zero-rate', chain)
                consequence = graph.nodes[prefix + 'storage.zero-rate.' + axis]
                self.assertEqual(consequence.equation.lhs, 0)
            for axis in 'xy':
                gradient = graph.nodes[prefix + 'storage.horizontal-gradient.' + axis].equation
                self.assertEqual(gradient.rhs, 0)
                self.assertIsInstance(gradient.lhs, sp.Derivative)
            self.assertTrue(graph.nodes[prefix + 'storage.cauchy'].inputs)
            z = sp.Symbol('z__' + owner, real=True)
            p = sp.Function('p__' + owner)(z, self.t)
            force = graph.nodes[prefix + 'storage.force'].equation
            self.assertEqual(force.lhs, 0)
            self.assertEqual(sp.expand(force.rhs + sp.diff(p, z) +
                sp.Symbol('rho__' + owner, real=True)*sp.Symbol('g__' + owner, real=True)), 0)
            changed = copy.deepcopy(model)
            operations = changed['motores']['momentumDerivation']['volumes'][owner]['operations']
            operations[:] = [op for op in operations if not op['changes'].get('zeroLocalAccumulation')]
            with self.assertRaises(MathematicsError):
                _source_graph(changed)
            with self.assertRaises(MathematicsError):
                build(changed)
        wall = graph.nodes['momentum.channel.wall.cauchy']
        self.assertEqual(wall.inputs, ())
        self.assertEqual(wall.kind, 'constitutive')
        self.assertEqual(wall.rule, 'constitutive_premise')
        self.assertIn('not deduced', wall.title)

    def test_d1_energy_pressure_and_kinetic_operations_commute_on_actual_expressions(self):
        from core.balances.energy_equations import linear_operators
        for name in ('a', 'c'):
            model = (self.documents['a'][0] if name == 'a' else json.loads(
                (ROOT / 'tests/reference_data/m1-c.json').read_text(encoding='utf8'))['model'])
            for owner, entry in model['motores']['energyDerivation']['volumes'].items():
                operations = entry['operations']
                pressure = next(i for i, op in enumerate(operations) if op['changes'].get('separarPresion'))
                kinetic = next(i for i, op in enumerate(operations) if op['changes'].get('sinCinetica'))
                self.assertLess(pressure, kinetic)
                graph, _, _ = energy_graph(model, owner)
                base = 'energy.' + owner + '.'
                original = graph.nodes[base + 'specific.1'].equation
                identity = graph.nodes[base + 'stress-definition'].equation
                condition = graph.nodes[base + 'kinetic-condition'].equation
                def apply(eq, mapping):
                    # Two passes distribute divergence and then extract the
                    # scalar sign introduced inside its newly expanded terms.
                    return sp.Eq(linear_operators(linear_operators(eq.lhs.xreplace(mapping))),
                                 linear_operators(linear_operators(eq.rhs.xreplace(mapping))), evaluate=False)
                pressure_first = apply(original, {identity.lhs: identity.rhs})
                kinetic_first = apply(original, {condition.lhs: condition.rhs})
                recorded_order = apply(pressure_first, {condition.lhs: condition.rhs})
                dependency_order = apply(kinetic_first, {identity.lhs: identity.rhs})
                self.assertTrue(pressure_first.has(condition.lhs))
                self.assertFalse(kinetic_first.has(condition.lhs))
                self.assertNotEqual(pressure_first, kinetic_first)
                self.assertEqual(recorded_order, dependency_order)
                proof = next(node.equation for key,node in graph.nodes.items() if key.startswith(base+'stress.'))
                self.assertEqual(recorded_order, apply(proof, {}))
                prefix = copy.deepcopy(model)
                prefix['motores']['energyDerivation']['volumes'][owner]['cursor'] = pressure + 1
                earlier = energy_graph(prefix, owner)[0]
                partial = next(node.equation for key,node in earlier.nodes.items() if key.startswith(base+'stress.'))
                self.assertEqual(apply(partial, {}), pressure_first)
                prefix['motores']['energyDerivation']['volumes'][owner]['cursor'] = kinetic + 1
                later = energy_graph(prefix, owner)[0]
                partial = next(node.equation for key,node in later.nodes.items() if key.startswith(base+'stress.'))
                self.assertEqual(apply(partial, {}), recorded_order)

    def test_every_used_physical_control_has_a_replayed_prefix_audit(self):
        audit = {}
        deferred = []
        models = [item[0] for item in self.documents.values()]
        models.append(json.loads((ROOT / 'tests/reference_data/m1-c.json').read_text(encoding='utf8'))['model'])
        for model in models:
            records = []
            for namespace, module, producer in [
                ('materialDerivation', material, material_graph),
                ('energyDerivation', energy, energy_graph),
                ('thermodynamicDerivation', thermodynamics, thermodynamic_graph),
                ('momentumDerivation', momentum, None),
            ]:
                for owner, entry in model['motores'].get(namespace, {}).get('volumes', {}).items():
                    previous = None
                    for cursor in range(len(entry['operations']) + 1):
                        prefix = copy.deepcopy(model)
                        active = prefix['motores'][namespace]['volumes'][owner]
                        if namespace == 'materialDerivation':
                            # Material's published v1 journal stores the active
                            # prefix directly; unlike the other families it has
                            # no cursor field.
                            active['operations'] = active['operations'][:cursor]
                        else:
                            active['cursor'] = cursor
                        volume = next(v for v in prefix['volumenes'] if v['id'] == owner)
                        if namespace == 'materialDerivation':
                            state = material.replay_volume(active)[-1]
                            volume['supuestos']['materia'] = state
                            graph = producer(prefix, owner, state)[0]
                        elif producer:
                            graph = producer(prefix, owner)[0]
                        else:
                            prefix['volumenes'] = [volume]
                            graph = _source_graph(prefix)[0]
                        current = {key: sp.srepr(node.equation) for key, node in graph.nodes.items()}
                        if previous is not None:
                            operation = entry['operations'][cursor-1]
                            delta = {key: {'before': previous.get(key), 'after': current.get(key)}
                                     for key in sorted(previous.keys() | current.keys())
                                     if previous.get(key) != current.get(key)}
                            if not delta:
                                deferred.append((model['id'],namespace,owner,tuple(operation['changes'])))
                            records.append({'namespace': namespace, 'owner': owner,
                                'operationId': operation['id'], 'changes': operation['changes'],
                                'effect': 'expression_change' if delta else 'deferred_premise',
                                'expressionDelta': delta})
                        previous = current
                    expected_count = len(entry['operations'])
                    self.assertEqual(sum(r['namespace'] == namespace and r['owner'] == owner for r in records), expected_count)
            audit[model['id']] = records
        self.assertEqual({name:len(rows) for name,rows in audit.items()}, {'m1-a':18,'m1-b':60,'m1-c':34})
        self.assertEqual(set(deferred), {
            ('m1-a','materialDerivation','mixture',('fija',)),
            ('m1-c','materialDerivation','region_a',('fija',)),
            ('m1-c','materialDerivation','region_b',('fija',)),
            *(('m1-b','momentumDerivation','channel',(flag,)) for flag in
              ('uniformSections','impermeableWall','constantArea'))})
        # This is measured prefix evidence, not an invented historical graph or
        # a new product capability. Empty deltas remain visible for review.
        (ROOT / '.tmp/m1-physical-prefix-audit.json').write_text(json.dumps(audit, indent=2), encoding='utf8')


if __name__ == '__main__':
    unittest.main()
