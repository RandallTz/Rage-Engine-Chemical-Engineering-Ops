"""Internal M1 acceptance authors; never imported by the product library.

Only premises are declared. The shared journals and mathematical session produce
the balances, caloric rates and temperature derivatives; no final RHS is stored.
"""
import sympy as sp
import copy
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from core.balances import material_derivation as material, energy_derivation as energy
from core.termodinamica import derivation as thermodynamics
from core.modelo import leer_modelo_comun
from core.modelo.operation_journal import replay
from core.modelo.equation_workbench import _source_graph, _known_unit
from core.mathematics.contract import FORMAT
from core.mathematics.dimensions import catalog
from core.mathematics.session import edit_history, replay_operations


THERMAL_REFERENCE = {
    'mass': (2, 3), 'specificCapacity': (500, 1000),
    'initialTemperature': (360, 300), 'referenceTemperature': 300,
    'conductance': 10, 'temperatureInterval': (290, 370),
    'horizon': 600, 'samples': 121,
    'temperatureScale': 60, 'massScale': 5, 'energyScale': 60000, 'heatRateScale': 600,
}


def thermal_source(owners=('region_a', 'region_b')):
    """Author two closed, rigid regions through the physical journal APIs."""
    model = {'formato': 'rage.modelo', 'version': 0, 'id': 'm1-c',
             'nombre': 'M1-C isolated thermal exchange',
             'componentes': [{'id': 1, 'nombre': 'Material', 'simbolo': 'M'}],
             'termodinamica': {'paquetes': []}, 'volumenes': [], 'corrientes': [],
             'intercambios': [], 'datos': {}, 'matematico': None, 'estudio': None,
             'motores': {}, 'procedencia': {'tipo': 'nuevo'}}
    recipes = [
        ('materialDerivation', material, ('start', 'no_reaction', 'fixed_boundary',
                                         'integrate', 'total', 'impermeable_remainder')),
        ('energyDerivation', energy, ('start', 'pressure_stress', 'no_kinetic',
                                     'no_viscous_work', 'no_body_work', 'no_volume_source',
                                     'integrate', 'reynolds', 'total', 'uniform_state')),
        ('thermodynamicDerivation', thermodynamics,
         ('start', 'one_phase', 'no_phase_change', 'linear_caloric')),
    ]
    for key, module, actions in recipes:
        journal = {'format': 'rage.' + {'materialDerivation': 'material',
                   'energyDerivation': 'energy', 'thermodynamicDerivation': 'thermodynamic'}[key]
                   + '-derivation', 'version': 1, 'volumes': {}}
        for owner in owners:
            for action in actions:
                journal = module.edit_journal(journal, owner, {'kind': action})
        model['motores'][key] = journal
    for index, owner in enumerate(owners):
        def datum(name, value, unit, role='parametro'):
            key = owner + '.' + name
            model['datos'][key] = {'magnitud': name, 'funcion': role,
                'declaracion': {'texto': str(value), 'unidad': unit},
                'origen': {'propietarioId': 'volumen:' + owner, 'ruta': name}}
            return key
        thermo_state = replay(model['motores']['thermodynamicDerivation']['volumes'][owner],
                              thermodynamics.fundamental, thermodynamics.normalize)[-1]
        energy_state = replay(model['motores']['energyDerivation']['volumes'][owner],
                              energy.fundamental, energy.normalize)[-1]
        model['volumenes'].append({'id': owner, 'componenteIds': [1],
            'balances': {'materia': True, 'energia': True, 'momento': False},
            'supuestos': {'materia': material.replay_volume(
                model['motores']['materialDerivation']['volumes'][owner])[-1],
                'energia': {**energy_state, **{k: v for k, v in thermo_state.items() if k != 'closure'}}},
            'frontera': {'tipo': 'rigida', 'datoId': datum('volume', 1, 'm3', 'geometria')},
            'inicial': {'cantidades': {'base': 'masica', 'datoIds': {
                '1': datum('mass', THERMAL_REFERENCE['mass'][index], 'kg', 'inicial')}},
                'energia': {'tipo': 'T', 'datoId': datum('temperature',
                    THERMAL_REFERENCE['initialTemperature'][index], 'K', 'inicial')}},
            'termodinamica': {'tipo': 'supuesto', 'supuesto': 'u_lineal',
                'motivo': 'Declared constant caloric coefficient on the frozen temperature interval',
                'parametros': {'cId': datum('capacity', THERMAL_REFERENCE['specificCapacity'][index], 'J/(kg*K)'),
                    'uRefId': datum('referenceEnergy', 0, 'J/kg'),
                    'TRefId': datum('referenceTemperature', 300, 'K'),
                    'TMinId': datum('minimumTemperature', 290, 'K'),
                    'TMaxId': datum('maximumTemperature', 370, 'K')}}})
    return leer_modelo_comun(model)


def author_thermal(owners=('region_a', 'region_b')):
    """Use the same pinned operations as Model; cache only the immutable source."""
    model = thermal_source(owners)
    source, selected, locations, units = _source_graph(model)
    definition = {'format': FORMAT, 'version': 1, 'operations': [], 'cursor': 0}
    result = replay_operations(source, selected, locations, units, definition,
                               require_same_family=True, unit_resolver=_known_unit)
    outputs = {}

    def quantity(expression):
        return next(key for key, value in {**catalog(result.graph, result.units),
                                          **result.introduced}.items() if value == expression)

    def append(kind, family='energy', **fields):
        nonlocal definition, result
        definition = edit_history(source, selected, locations, units, definition,
            {'kind': 'append', 'operation': {'kind': kind, 'family': family, **fields}},
            require_same_family=True, unit_resolver=_known_unit)
        result = replay_operations(source, selected, locations, units, definition,
                                   require_same_family=True, unit_resolver=_known_unit)
        return 'operation.' + str(definition['cursor'])

    t = sp.Symbol('t', real=True)
    T = [sp.Function('T__' + owner)(t) for owner in owners]
    append('declare_function', name='internalHeat', unit='W', dependencies=[quantity(t)])
    append('declare_symbol', name='conductance', unit='W/K')
    heat_law = append('declare_relation', left='internalHeat',
        right=f'conductance*({quantity(T[0])}-{quantity(T[1])})', relationKind='constitutive',
        reason='Linear heat transfer from the first region to the second; constant conductance')
    append('declare_domain', sources=[heat_law], symbol='conductance', domain='positive',
           reason='Passive thermal connection on the M1-C regular regime')
    for owner, sign in zip(owners, ('-', '')):
        Q = sp.Function('energy_heat_rate__' + owner)(t)
        U = sp.Function('U__' + owner)(t)
        mass = sp.Function('m__' + owner + '__1')(t)
        boundary = append('declare_relation', left=quantity(Q), right=sign + 'internalHeat',
            relationKind='constraint', reason='Exhaustive isolated-pair boundary: this is the only heat exchange')
        balance = next(key for key in selected if key.startswith('energy.' + owner + '.')
                       and source.nodes[key].equation.lhs == sp.diff(U, t))
        coupled = append('substitute', sources=[balance], relation=boundary, symbol=quantity(Q))
        outputs[owner + '.heat'] = coupled
        closed = append('substitute', sources=[coupled], relation=heat_law, symbol='internalHeat')
        outputs[owner + '.energy'] = closed
        caloric = 'thermodynamics.' + owner + '.caloric-inventory'
        for value in (mass, sp.Symbol('caloric_capacity__' + owner, real=True)):
            append('declare_domain', family='thermodynamics', sources=[caloric],
                   symbol=quantity(value), domain='positive',
                   reason='Positive inventory and caloric coefficient in the M1-C regular regime')
        append('declare_domain', family='thermodynamics', sources=[caloric],
               symbol=quantity(sp.Function('T__' + owner)(t)), domain='interval',
               lower='290', upper='370', lowerOpen=False, upperOpen=False, endpointUnit='K',
               reason='Declared caloric validity interval for the frozen M1-C reference')
        rate = append('differentiate', family='thermodynamics', sources=[caloric], symbol=quantity(t))
        mass_balance = next(key for key in selected if key.startswith('matter.' + owner + '.')
                            and source.nodes[key].equation.lhs == sp.diff(mass, t))
        fixed_mass_rate = append('substitute', family='thermodynamics', sources=[rate],
                                relation=mass_balance, symbol=quantity(sp.diff(mass, t)))
        substituted = append('substitute', family='thermodynamics', sources=[fixed_mass_rate],
                             relation=closed, symbol=quantity(sp.diff(U, t)))
        derivative = sp.diff(sp.Function('T__' + owner)(t), t)
        outputs[owner + '.temperature'] = append('isolate', family='thermodynamics',
                                               sources=[substituted], symbol=quantity(derivative))
    outputs['totalEnergy'] = append('combine', sources=[outputs[o + '.heat'] for o in owners])
    model['motores']['equationWorkbench'] = definition
    return leer_modelo_comun(model), result, outputs


class SharedAuthor:
    """A test driver of the same pinned session used by Model, without RHS code."""

    def __init__(self, model):
        self.model = model
        self.source, self.selected, self.locations, self.units = _source_graph(model)
        self.definition = {'format': FORMAT, 'version': 1, 'operations': [], 'cursor': 0}
        self.refresh()

    def refresh(self):
        self.result = replay_operations(self.source, self.selected, self.locations,
            self.units, self.definition, require_same_family=True, unit_resolver=_known_unit)

    def quantity(self, expression):
        return next(key for key, value in {**catalog(self.result.graph, self.result.units),
            **self.result.introduced}.items() if value == expression)

    def append(self, kind, family='matter', **fields):
        self.definition = edit_history(self.source, self.selected, self.locations,
            self.units, self.definition, {'kind': 'append', 'operation': {
                'kind': kind, 'family': family, **fields}},
            require_same_family=True, unit_resolver=_known_unit)
        self.refresh()
        return 'operation.' + str(self.definition['cursor'])

    def relation(self, left, right, reason, family='matter', kind='constraint'):
        return self.append('declare_relation', family, left=left, right=right,
                           relationKind=kind, reason=reason)

    def substitute(self, source, relation, expression, family='matter'):
        return self.append('substitute', family, sources=[source], relation=relation,
                           symbol=self.quantity(expression))

    def finish(self, outputs):
        self.model['motores']['equationWorkbench'] = self.definition
        return leer_modelo_comun(self.model), self.result, outputs


MIXING_REFERENCE = {
    'initialMass': [2, 8], 'molarMass': [0.02, 0.05], 'massFlow': 0.1,
    'feedMassFraction': 0.7, 'specificCapacity': 1000,
    'initialTemperature': 300, 'feedTemperature': 330, 'heatRate': 2000,
    'referenceTemperature': 300, 'specificFlowWork': 100,
    'temperatureInterval': [290, 360], 'horizon': 600, 'samples': 121,
    'massScale': 10, 'moleScale': 500, 'compositionScale': 1,
    'temperatureScale': 50, 'energyScale': 500000,
}


def mixing_source():
    model = thermal_source(('mixture',))
    model.update(id='m1-a', nombre='M1-A balanced binary mixing and heating')
    model['componentes'] = [
        {'id': i, 'nombre': 'Component ' + str(i), 'simbolo': 'C' + str(i)} for i in (1, 2)]
    volume = model['volumenes'][0]
    volume['componenteIds'] = [1, 2]
    model['datos']['mixture.mass']['declaracion']['texto'] = '2'
    second = copy.deepcopy(model['datos']['mixture.mass'])
    second['declaracion']['texto'] = '8'
    model['datos']['mixture.secondMass'] = second
    volume['inicial']['cantidades']['datoIds']['2'] = 'mixture.secondMass'
    for name, value in [('temperature', 300), ('capacity', 1000), ('maximumTemperature', 360)]:
        model['datos']['mixture.' + name]['declaracion']['texto'] = str(value)
    journal = model['motores']['energyDerivation']
    journal = energy.edit_journal(journal, 'mixture', {'kind': 'enthalpy'})
    model['motores']['energyDerivation'] = journal
    state = replay(journal['volumes']['mixture'], energy.fundamental, energy.normalize)[-1]
    volume['supuestos']['energia'].update(state)
    model['corrientes'] = [
        {'id': name, 'desde': None if name == 'feed' else 'mixture',
         'hasta': 'mixture' if name == 'feed' else None, 'componenteIds': [1, 2],
         'mecanismo': 'convectivo', 'constante': False,
         'materia': {'modo': 'por_componente', 'base': 'masica', 'caudalIds': {}}}
        for name in ('feed', 'outlet')]
    return leer_modelo_comun(model)


def author_mixing():
    author = SharedAuthor(mixing_source())
    add, q = author.append, author.quantity
    t = sp.Symbol('t', real=True)
    m = [sp.Function('m__mixture__' + str(i))(t) for i in (1, 2)]
    total = sum(m)
    T, U = (sp.Function(name + '__mixture')(t) for name in ('T', 'U'))
    capacity = sp.Symbol('caloric_capacity__mixture', real=True)
    reference_T = sp.Symbol('T_reference__mixture', real=True)
    reference_u = sp.Symbol('u_reference__mixture', real=True)
    for name, unit in [('feedRate', 'kg/s'), ('feedFraction', '1'),
                       ('feedTemperature', 'K'), ('suppliedHeat', 'W'),
                       ('specificFlowWork', 'J/kg'), ('molarMass1', 'kg/mol'),
                       ('molarMass2', 'kg/mol')]:
        add('declare_symbol', name=name, unit=unit)
    outputs = {}
    for index, mass in enumerate(m, 1):
        current = next(key for key in author.selected if key.startswith('matter.mixture.')
                       and author.source.nodes[key].equation.lhs == sp.diff(mass, t))
        for stream, right in [('feed', 'feedRate*' + ('feedFraction' if index == 1 else '(1-feedFraction)')),
                              ('outlet', f'feedRate*{q(mass)}/({q(m[0])}+{q(m[1])})')]:
            flow = sp.Function(f'q__{stream}__{index}')(t)
            relation = author.relation(q(flow), right,
                'Balanced boundary mass rate; outlet has the well-mixed inventory composition')
            outputs[f'{stream}.{index}'] = relation
            current = author.substitute(current, relation, flow)
        outputs[f'mass.{index}'] = current
        add('declare_function', name=f'amount{index}', unit='mol', dependencies=[q(t)])
        outputs[f'amount.{index}'] = author.relation(f'amount{index}',
            f'{q(mass)}/molarMass{index}', 'Define amount using the declared component molar mass', kind='definition')
    outputs['totalMass'] = add('combine', sources=[outputs['mass.1'], outputs['mass.2']])
    caloric = 'thermodynamics.mixture.caloric-inventory'
    for expression in [*m, capacity]:
        add('declare_domain', 'thermodynamics', sources=[caloric], symbol=q(expression),
            domain='positive', reason='Positive component inventory and caloric coefficient')
    add('declare_domain', 'thermodynamics', sources=[caloric], symbol=q(T),
        domain='interval', lower='290', upper='360', lowerOpen=False, upperOpen=False,
        endpointUnit='K', reason='Frozen caloric validity interval')
    for name, source in [('molarMass1', outputs['amount.1']), ('molarMass2', outputs['amount.2']),
                         ('feedRate', outputs['feed.1'])]:
        add('declare_domain', sources=[source], symbol=name, domain='positive',
            reason='Positive constitutive datum in the regular reference regime')
    add('declare_domain', sources=[outputs['feed.1']], symbol='feedFraction', domain='interval',
        lower='0', upper='1', lowerOpen=True, upperOpen=True, reason='Binary feed contains both components')
    current = next(key for key in author.selected if key.startswith('energy.mixture.')
                   and author.source.nodes[key].equation.lhs == sp.diff(U, t))
    for stream in ('feed', 'outlet'):
        for index in (1, 2):
            current = author.substitute(current, outputs[f'{stream}.{index}'],
                                       sp.Function(f'q__{stream}__{index}')(t), 'energy')
        average = sp.Function('energy_average_0__' + stream)(t)
        temperature = 'feedTemperature' if stream == 'feed' else q(T)
        relation = author.relation(q(average),
            f'{q(reference_u)}+{q(capacity)}*({temperature}-{q(reference_T)})+specificFlowWork',
            'Declared stream enthalpy closure: common caloric coefficient and equal flow-work offset',
            'energy', 'constitutive')
        current = author.substitute(current, relation, average, 'energy')
    heat = sp.Function('energy_heat_rate__mixture')(t)
    relation = author.relation(q(heat), 'suppliedHeat', 'Prescribed boundary heat input', 'energy')
    outputs['energy'] = author.substitute(current, relation, heat, 'energy')
    rate = add('differentiate', 'thermodynamics', sources=[caloric], symbol=q(t))
    for index, mass in enumerate(m, 1):
        rate = author.substitute(rate, outputs[f'mass.{index}'], sp.diff(mass, t), 'thermodynamics')
    rate = author.substitute(rate, outputs['energy'], sp.diff(U, t), 'thermodynamics')
    outputs['temperature'] = add('isolate', 'thermodynamics', sources=[rate], symbol=q(sp.diff(T, t)))
    return author.finish(outputs)


def freeze_acceptance_documents():
    """Fresh shared authoring only; never patch signatures in frozen inputs."""
    from time import perf_counter
    from core.modelo.equation_workbench import describe
    root=Path(__file__).resolve().parents[1]
    for name,author,reference in [('a',author_mixing,MIXING_REFERENCE),
                                  ('b',author_hydraulic,HYDRAULIC_REFERENCE),
                                  ('c',author_thermal,THERMAL_REFERENCE)]:
        start=perf_counter()
        model,result,outputs=author()
        document={'version':1,'model':model,'selectedEquations':outputs,'reference':reference}
        (root/f'tests/reference_data/m1-{name}.json').write_text(json.dumps(document,indent=2)+'\n',encoding='utf8')
        publication='thermal' if name=='c' else name
        (root/f'.tmp/m1-{publication}-publication.json').write_text(json.dumps(describe(model)),encoding='utf8')
        print(f'M1-{name.upper()}: {len(result.definition["operations"])} workbench operations; freshly frozen in {perf_counter()-start:.3f} s',flush=True)


HYDRAULIC_REFERENCE = {
    'initialMass': [40, 10], 'initialFlow': 0, 'density': 1000, 'viscosity': 0.05,
    'length': 10, 'diameter': 0.02, 'storageArea': [0.02, 0.02],
    'surfacePressure': 101325, 'gravity': 9.80665, 'temperature': 293.15,
    'minimumPressure': 2500, 'maximumReynolds': 2100,
    'horizon': 600, 'samples': 121, 'massScale': 50, 'flowScale': 0.1,
    'heightScale': 2, 'pressureScale': 20000,
}


def hydraulic_source():
    """Regenerate the existing candidate through its shared frontend journals."""
    root = Path(__file__).resolve().parents[1]
    subprocess.run(['node', 'frontend/verificar_hydraulics.mjs', '--inputs-only'],
                   cwd=root, check=True, capture_output=True, text=True)
    model = json.loads((root / '.tmp/hydraulic-models.json').read_text(encoding='utf8'))[1]
    model.update(id='m1-b', nombre='M1-B coupled inventories and dissipative inertial flow')
    for volume in model['volumenes']:
        volume['termodinamica']['motivo'] = 'Declared isothermal single-phase reference medium; no equilibrium certification'
    return leer_modelo_comun(model)


def author_hydraulic():
    author = SharedAuthor(hydraulic_source())
    add, q = author.append, author.quantity
    t = sp.Symbol('t', real=True)
    outputs = {}
    path = 'momentum.channel.path.pressure-form'
    current = author.substitute(path, 'momentum.channel.wall.area-form',
                                sp.Function('loss__channel')(t), 'momentum')
    for index, owner in enumerate(('upper', 'lower'), 1):
        pressure = 'momentum.' + owner + '.storage.port-pressure'
        z, floor = (sp.Symbol(name + '__' + owner, real=True) for name in ('z', 'z_0'))
        boundary = author.relation(q(z), q(floor), 'The material port is at the storage floor', 'momentum')
        pressure = author.substitute(pressure, boundary, z, 'momentum')
        pressure = author.substitute(pressure, 'matter.' + owner + '.total-definition',
            sp.Function('m_total__' + owner)(t), 'momentum')
        outputs[owner + '.pressure'] = pressure
        port = sp.Function('p' + str(index) + '__channel')(t)
        field = author.result.graph.nodes[pressure].equation.lhs
        coupling = author.relation(q(port), q(field), 'Continuous pressure at the shared material port', 'momentum')
        current = author.substitute(current, coupling, port, 'momentum')
        current = author.substitute(current, pressure, field, 'momentum')
        outputs[owner + '.mass'] = next(key for key in author.selected
            if key.startswith('matter.' + owner + '.') and author.source.nodes[key].equation.lhs
            == sp.diff(sp.Function('m__' + owner + '__1')(t), t))
        outputs[owner + '.height'] = 'momentum.' + owner + '.storage.height'
    for name in ('drive',):
        field = sp.Function(name + '__channel')(t)
        boundary = author.relation(q(field), '0', 'No applied pressure drive', 'momentum')
        current = author.substitute(current, boundary, field, 'momentum')
    z1, z2 = (sp.Symbol(name + '__channel', real=True) for name in ('z1', 'z2'))
    level = author.relation(q(z2), q(z1), 'Equal path endpoint elevations', 'momentum')
    current = author.substitute(current, level, z2, 'momentum')
    flow = sp.Function('q__s1__1')(t)
    outputs['flow'] = add('isolate', 'momentum', sources=[current], symbol=q(sp.diff(flow, t)))
    compatibility = 'momentum.channel.path.mass-compatibility'
    # Fixed path storage derives equal inlet/outlet flow from component conservation.
    continuity = add('isolate', sources=[compatibility], symbol=q(sp.Function('q__s2__1')(t)))
    outputs['lower.mass'] = author.substitute(outputs['lower.mass'], continuity, sp.Function('q__s2__1')(t))
    outputs['totalMass'] = add('combine', sources=[outputs['upper.mass'], outputs['lower.mass']])
    for owner, names in [('channel', ('A', 'L', 'rho', 'mu')),
                         ('upper', ('A_v', 'rho', 'g')), ('lower', ('A_v', 'rho', 'g'))]:
        for name in names:
            source = outputs['flow'] if owner == 'channel' else outputs[owner + '.pressure']
            expression = sp.Symbol(name + '__' + owner, real=True)
            # Density canceled from pressure but remains in the height definition.
            if name == 'rho' and owner != 'channel':
                source = outputs[owner + '.height']
            add('declare_domain', author.result.graph.nodes[source].family, sources=[source], symbol=q(expression),
                domain='positive', reason='Positive geometry and passive reference-medium coefficients')
    return author.finish(outputs)


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Freshly author and freeze the internal M1 acceptance inputs.')
    parser.add_argument('--freeze',action='store_true',help='Rebuild all three documents through shared operations and publish their graphs')
    if not parser.parse_args().freeze:
        parser.error('Use --freeze to explicitly regenerate the internal acceptance inputs.')
    freeze_acceptance_documents()
