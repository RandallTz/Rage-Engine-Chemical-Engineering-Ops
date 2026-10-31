"""Functions in declared relations and chained initialisation (codex-queue item 5; F4 audit FD-6, FD-7).

A single-liquid drum (declared linear caloric law, constant density) with a
Torricelli orifice written with sqrt(...). Its initial enthalpy is reached
from the initial temperature through the separate relations H = U + P V,
U = m u(T) and V = m / rho; no composed H(m, T) relation is authored.
Reference: an independent DOP853 integration of the same premises.
"""
import copy
import math
import unittest

import numpy as np
import sympy as sp
from scipy.integrate import solve_ivp

from m1_acceptance import SharedAuthor, thermal_source
from core.balances import material_derivation as material, energy_derivation as energy
from core.termodinamica import derivation as thermodynamics
from core.modelo import leer_modelo_comun
from core.modelo.operation_journal import replay
from core.modelo.equation_workbench import build
from core.mathematics.dimensions import catalog, parse_expression
from core.mathematics.errors import MathematicsError
from core.compilador.derived import DerivedSystem, LoweringError, resolve_system, source_signature

OWNER = 'drum'
T = sp.Symbol('t', real=True)
DATA = {'rho': 800.0, 'area': 0.5, 'Cd': 0.6, 'orifice': 1e-3, 'g': 9.80665, 'F': 1.5, 'z': 0.3, 'TF': 330.0,
        'Q': 50000.0, 'c': 3000.0, 'uref': 0.0, 'Tref': 300.0, 'P': 101325.0, 'm0': (90.0, 210.0), 'T0': 300.0, 'tf': 600.0}


def _datum(model, key, value, unit, role='parametro'):
    model['datos'][key] = {'magnitud': key, 'funcion': role, 'declaracion': {'texto': repr(float(value)), 'unidad': unit},
                           'origen': {'propietarioId': 'estudio', 'ruta': key}}
    return key


def liquid_drum_source():
    model = thermal_source((OWNER,))
    model.update(id='item5-liquid-drum', nombre='Liquid drum (test)')
    model['componentes'] = [{'id': 1, 'nombre': 'A', 'simbolo': 'A'}, {'id': 2, 'nombre': 'B', 'simbolo': 'B'}]
    volume = model['volumenes'][0]
    volume['componenteIds'] = [1, 2]
    model['datos'][OWNER + '.secondMass'] = copy.deepcopy(model['datos'][OWNER + '.mass'])
    volume['inicial']['cantidades']['datoIds']['2'] = OWNER + '.secondMass'
    for key, value in [('mass', DATA['m0'][0]), ('secondMass', DATA['m0'][1]), ('temperature', DATA['T0']), ('capacity', DATA['c']),
                       ('referenceEnergy', DATA['uref']), ('referenceTemperature', DATA['Tref']), ('minimumTemperature', 290), ('maximumTemperature', 370)]:
        model['datos'][OWNER + '.' + key]['declaracion']['texto'] = str(value)
    journal = {'format': 'rage.material-derivation', 'version': 1, 'volumes': {}}
    for action in ['start', 'no_reaction', 'integrate', 'total', 'impermeable_remainder']:
        journal = material.edit_journal(journal, OWNER, {'kind': action})
    model['motores']['materialDerivation'] = journal
    volume['supuestos']['materia'] = material.replay_volume(journal['volumes'][OWNER])[-1]
    ej = {'format': 'rage.energy-derivation', 'version': 1, 'volumes': {}}
    for action in ('start', 'pressure_stress', 'no_kinetic', 'no_viscous_work', 'no_body_work', 'no_volume_source', 'integrate',
                   'reynolds', 'total', 'enthalpy', 'uniform_state', 'uniform_pressure', 'prescribed_pressure'):
        ej = energy.edit_journal(ej, OWNER, {'kind': action})
    model['motores']['energyDerivation'] = ej
    tj = thermodynamics.edit_journal(model['motores']['thermodynamicDerivation'], OWNER, {'kind': 'constant_density'})
    model['motores']['thermodynamicDerivation'] = tj
    es = replay(ej['volumes'][OWNER], energy.fundamental, energy.normalize)[-1]
    ts = replay(tj['volumes'][OWNER], thermodynamics.fundamental, thermodynamics.normalize)[-1]
    volume['supuestos']['energia'] = {**es, **{k: v for k, v in ts.items() if k != 'closure'}}
    _datum(model, OWNER + '.pressure', DATA['P'], 'Pa', 'frontera')
    volume['frontera'] = {'tipo': 'presion_prescrita', 'presionId': OWNER + '.pressure'}
    model['corrientes'] = [{'id': name, 'desde': None if name == 'feed' else OWNER, 'hasta': OWNER if name == 'feed' else None,
                            'componenteIds': [1, 2], 'mecanismo': 'convectivo', 'constante': False,
                            'materia': {'modo': 'por_componente', 'base': 'masica', 'caudalIds': {}}} for name in ('feed', 'liquid', 'vapour')]
    return leer_modelo_comun(model)


def author_liquid_drum():
    author = SharedAuthor(liquid_drum_source())
    add, q = author.append, author.quantity
    o = OWNER
    f = lambda name: sp.Function(name)(T)
    m = [f(f'm__{o}__{i}') for i in (1, 2)]
    Tq, V, P, H = f('T__' + o), f('V__' + o), f('P__' + o), f('H__' + o)
    rho, cap = sp.Symbol('rho_reference__' + o, real=True), sp.Symbol('caloric_capacity__' + o, real=True)
    Tr, ur = sp.Symbol('T_reference__' + o, real=True), sp.Symbol('u_reference__' + o, real=True)
    for name, unit in [('feedRate', 'kg/s'), ('feedFraction', '1'), ('feedTemperature', 'K'), ('heatDuty', 'W'), ('drumArea', 'm2'),
                       ('dischargeCoefficient', '1'), ('orificeArea', 'm2'), ('gravity', 'm/s2')]:
        add('declare_symbol', name=name, unit=unit)
    out = {}
    add('declare_function', name='level', unit='m', dependencies=[q(T)])
    out['level'] = author.relation('level', f'{q(V)}/drumArea', 'Vertical cylindrical drum: liquid volume = area * level', kind='definition')
    add('declare_function', name='liquidOutflow', unit='kg/s', dependencies=[q(T)])
    out['orifice'] = author.relation('liquidOutflow', f'{q(rho)}*dischargeCoefficient*orificeArea*sqrt(2*gravity*level)',
                                     'Quasi-steady Torricelli orifice discharge at the floor', kind='constitutive')
    for i, mass in enumerate(m, 1):
        current = next(k for k in author.selected if k.startswith(f'matter.{o}.') and author.source.nodes[k].equation.lhs == sp.diff(mass, T))
        rows = [(author.relation(q(f(f'q__feed__{i}')), 'feedRate*' + ('feedFraction' if i == 1 else '(1-feedFraction)'), 'Prescribed feed'), 'feed'),
                (author.relation(q(f(f'q__liquid__{i}')), f'liquidOutflow*{q(mass)}/({q(m[0])}+{q(m[1])})', 'Well-mixed single liquid donor'), 'liquid'),
                (author.relation(q(f(f'q__vapour__{i}')), '0', 'Subcooled liquid: no vapour outlet flow'), 'vapour')]
        for relation, stream in rows:
            current = author.substitute(current, relation, f(f'q__{stream}__{i}'))
            out[f'{stream}.{i}'] = relation
        out[f'mass.{i}'] = current
    current = next(k for k in author.selected if k.startswith(f'energy.{o}.') and author.source.nodes[k].equation.lhs == sp.diff(H, T))
    for stream in ('feed', 'liquid', 'vapour'):
        for i in (1, 2):
            current = author.substitute(current, out[f'{stream}.{i}'], f(f'q__{stream}__{i}'), 'energy')
    for stream, temperature in [('feed', 'feedTemperature'), ('liquid', q(Tq))]:
        average = f('energy_average_0__' + stream)
        relation = author.relation(q(average), f'{q(ur)}+{q(cap)}*({temperature}-{q(Tr)})+{q(P)}/{q(rho)}',
                                   'Incompressible-liquid stream enthalpy with the declared caloric law', 'energy', 'constitutive')
        current = author.substitute(current, relation, average, 'energy')
    heat = author.relation(q(f('energy_heat_rate__' + o)), 'heatDuty', 'Prescribed heat duty', 'energy')
    out['energy'] = author.substitute(current, heat, f('energy_heat_rate__' + o), 'energy')
    out['internal'] = add('isolate', 'thermodynamics', sources=[f'thermodynamics.{o}.enthalpy'], symbol=q(f('U__' + o)))
    for name, source in [('drumArea', out['level']), ('dischargeCoefficient', out['orifice']), ('orificeArea', out['orifice']), ('gravity', out['orifice'])]:
        add('declare_domain', sources=[source], symbol=name, domain='positive', reason='Positive geometry and discharge coefficient')
    return author, out


def select(author, out, method='rk45'):
    model, _, _ = author.finish({})
    replayed = build(model)
    quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    named = lambda name: next(k for k, v in quantities.items() if str(v) == name)
    o = OWNER
    sel = {'format': 'rage.derived-execution', 'version': 1, 'sourceSignature': source_signature(model, replayed), 'timeId': named('t'),
           'states': [], 'parameters': {}, 'initialValues': {}, 'initialEquations': [], 'reconstructions': [], 'checks': []}
    for i in (1, 2):
        sel['states'].append({'quantityId': named(f'm__{o}__{i}(t)'), 'equationId': out[f'mass.{i}']})
        sel['initialValues'][named(f'm__{o}__{i}(t)')] = o + ('.mass' if i == 1 else '.secondMass')
    sel['states'].append({'quantityId': named(f'H__{o}(t)'), 'equationId': out['energy']})
    for name, key in [(f'V__{o}(t)', f'thermodynamics.{o}.volume'), (f'U__{o}(t)', out['internal']),
                      (f'T__{o}(t)', f'thermodynamics.{o}.temperature'), ('level(t)', out['level']), (f'm_total__{o}(t)', f'matter.{o}.total-definition')]:
        sel['reconstructions'].append({'quantityId': named(name), 'equationId': key})
    # Separate relations only: the chain V(m), U(m, T), H = U + P V determines the initial enthalpy.
    sel['initialEquations'] = [f'thermodynamics.{o}.enthalpy', f'thermodynamics.{o}.caloric-inventory', f'thermodynamics.{o}.volume']
    sel['initialValues'][named(f'T__{o}(t)')] = o + '.temperature'
    for name, spec in {f'caloric_capacity__{o}': (o + '.capacity',), f'T_reference__{o}': (o + '.referenceTemperature',),
                       f'u_reference__{o}': (o + '.referenceEnergy',), f'rho_reference__{o}': ('rho', DATA['rho'], 'kg/m3'),
                       f'P__{o}(t)': (o + '.pressure',), 'feedRate': ('F', DATA['F'], 'kg/s'), 'feedFraction': ('z', DATA['z'], '1'),
                       'feedTemperature': ('TF', DATA['TF'], 'K'), 'heatDuty': ('Q', DATA['Q'], 'W'), 'drumArea': ('A', DATA['area'], 'm2'),
                       'dischargeCoefficient': ('Cd', DATA['Cd'], '1'), 'orificeArea': ('Ao', DATA['orifice'], 'm2'), 'gravity': ('g', DATA['g'], 'm/s2')}.items():
        sel['parameters'][named(name)] = spec[0] if len(spec) == 1 else _datum(model, 'solve.' + spec[0], *spec[1:])
    sel['checks'] = [{'equationId': f'matter.{o}.total', 'scaleDataId': _datum(model, 'scale.mass', 300, 'kg')}]
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': _datum(model, 'solve.tf', DATA['tf'], 's', 'estudio'), 'metodoSolicitado': method,
                        'muestras': 61, 'rtol': 1e-10, 'atol': {'cantidad': 1e-10, 'energia': 1e-3}}
    model['motores']['derivedExecution'] = sel
    return model


def reference(times):
    d = DATA
    def temperature(m1, m2, H):
        M = m1 + m2
        return d['Tref'] + ((H - d['P'] * M / d['rho']) / M - d['uref']) / d['c']
    def rhs(t, y):
        m1, m2, H = y; M = m1 + m2
        W = d['rho'] * d['Cd'] * d['orifice'] * math.sqrt(2 * d['g'] * M / d['rho'] / d['area'])
        hF = d['uref'] + d['c'] * (d['TF'] - d['Tref']) + d['P'] / d['rho']
        hL = d['uref'] + d['c'] * (temperature(*y) - d['Tref']) + d['P'] / d['rho']
        return [d['F'] * d['z'] - W * m1 / M, d['F'] * (1 - d['z']) - W * m2 / M, d['F'] * hF - W * hL + d['Q']]
    M0 = sum(d['m0'])
    H0 = M0 * (d['uref'] + d['c'] * (d['T0'] - d['Tref'])) + d['P'] * M0 / d['rho']
    return H0, solve_ivp(rhs, (0, d['tf']), [*d['m0'], H0], method='DOP853', rtol=1e-12, atol=1e-12, t_eval=times)


class ParseFunctions(unittest.TestCase):
    def test_conditions_and_dimensions(self):
        a, b = sp.Symbol('a', real=True), sp.Symbol('b', real=True)
        units = {a: 'm', b: 'm'}
        conditions = []
        self.assertEqual(parse_expression('sqrt(a)', {'a': a, 'b': b}, conditions, units), sp.sqrt(a))
        self.assertIn(sp.Ge(a, 0, evaluate=False), conditions)
        conditions = []
        self.assertEqual(parse_expression('log(a/b)', {'a': a, 'b': b}, conditions, units), sp.log(a / b))
        self.assertIn(sp.Gt(a / b, 0, evaluate=False), conditions)
        self.assertEqual(parse_expression('exp(a/b)', {'a': a, 'b': b}, [], units), sp.exp(a / b))
        for text in ('exp(a)', 'log(b)'):
            with self.assertRaises(MathematicsError):
                parse_expression(text, {'a': a, 'b': b}, [], units)
        with self.assertRaises(MathematicsError):
            parse_expression('sqrt(0-4)', {}, [], {})
        with self.assertRaises(MathematicsError):
            parse_expression('log(0)', {}, [], {})


class LiquidDrum(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.author, cls.out = author_liquid_drum()

    def test_sqrt_orifice_and_chained_initialisation_against_dop853(self):
        for method in ('rk45', 'bdf'):
            with self.subTest(method=method):
                model = select(self.author, self.out, method)
                system = DerivedSystem(model)
                H0, sol = reference(np.linspace(0, DATA['tf'], 61))
                self.assertAlmostEqual(float(system.initial_state[2]), H0, delta=1e-9 * abs(H0))
                result = resolve_system(system)
                self.assertEqual(result['estado'], 'resuelto')
                values = {row['id']: np.array(row['valores']) for row in result['series']}
                ids = [row['quantityId'] for row in model['motores']['derivedExecution']['states']]
                self.assertLess(np.max(abs(values['campo.' + ids[0]] - sol.y[0])), 1e-6)
                self.assertLess(np.max(abs(values['campo.' + ids[1]] - sol.y[1])), 1e-6)
                self.assertLess(np.max(abs(values['campo.' + ids[2]] - sol.y[2])) / np.max(abs(sol.y[2])), 1e-8)
        conditions = [row['latex'] for row in system.report['derivedExecution']['runtimeConditions']]
        self.assertTrue(any('geq 0' in latex or r'\geq 0' in latex for latex in conditions), conditions)

    def test_unsolvable_chain_still_reports_missing_initialisation(self):
        model = select(self.author, self.out)
        model['motores']['derivedExecution']['initialEquations'] = [f'thermodynamics.{OWNER}.enthalpy']
        with self.assertRaises(LoweringError) as caught:
            DerivedSystem(model)
        self.assertIn(caught.exception.diagnostics[0]['code'], ('missing_initialization', 'invalid_initialization'))


if __name__ == '__main__':
    unittest.main()
