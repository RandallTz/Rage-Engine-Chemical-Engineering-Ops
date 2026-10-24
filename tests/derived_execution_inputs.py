"""Numerical bindings to frozen M1 graphs; no new physical equations or RHS."""
import copy
import json
from pathlib import Path

import sympy as sp

from core.compilador.derived import source_signature
from core.mathematics.dimensions import catalog
from core.modelo.equation_workbench import build

ROOT = Path(__file__).resolve().parents[1]


def fixture(name, method='rk45'):
    document = json.loads((ROOT / f'tests/reference_data/m1-{name}.json').read_text(encoding='utf8'))
    model = copy.deepcopy(document['model']); reference = document['reference']
    replayed = build(model)
    quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    def quantity(expression):
        return next(key for key, value in quantities.items() if value == expression)
    def named(name):
        return next(key for key, value in quantities.items() if str(value) == name)
    def datum(key, value, unit, role='parametro'):
        model['datos'][key] = {'magnitud': key, 'funcion': role,
            'declaracion': {'texto': str(value), 'unidad': unit},
            'origen': {'propietarioId': 'estudio', 'ruta': key}}
        return key
    selection = {'format': 'rage.derived-execution', 'version': 1,
        'sourceSignature': source_signature(model, replayed), 'timeId': named('t'),
        'states': [], 'parameters': {}, 'initialValues': {}, 'initialEquations': [],
        'reconstructions': [], 'checks': []}
    def state(key, initial_data=None):
        expression = replayed.graph.nodes[key].equation.lhs.expr
        qid = quantity(expression)
        selection['states'].append({'quantityId': qid, 'equationId': key})
        if initial_data:
            selection['initialValues'][qid] = initial_data
    def parameter(name, data):
        selection['parameters'][named(name)] = data
    def reconstruct(name, key):
        selection['reconstructions'].append({'quantityId': named(name), 'equationId': key})
    def total(owner):
        reconstruct('m_total__'+owner+'(t)', 'matter.'+owner+'.total-definition')
    t = sp.Symbol('t', real=True)
    if name in ('a', 'c'):
        owners = ('mixture',) if name == 'a' else ('region_a', 'region_b')
        for owner in owners:
            volume = next(v for v in model['volumenes'] if v['id'] == owner)
            for component in volume['componenteIds']:
                mass = sp.Function('m__'+owner+'__'+str(component))(t)
                key = document['selectedEquations']['mass.'+str(component)] if name == 'a' else next(
                    key for key in reversed(replayed.selected) if isinstance(replayed.graph.nodes[key].equation, sp.Equality)
                    and replayed.graph.nodes[key].equation.lhs == sp.diff(mass, t))
                state(key, volume['inicial']['cantidades']['datoIds'][str(component)])
            state(document['selectedEquations']['energy' if name == 'a' else owner+'.energy'])
            caloric = 'thermodynamics.'+owner+'.caloric-inventory'
            reconstruct('T__'+owner+'(t)', caloric)
            total(owner)
            selection['initialEquations'].append(caloric)
            selection['initialValues'][named('T__'+owner+'(t)')] = volume['inicial']['energia']['datoId']
            for prefix, key in [('caloric_capacity', 'cId'), ('T_reference', 'TRefId'), ('u_reference', 'uRefId')]:
                parameter(prefix+'__'+owner, volume['termodinamica']['parametros'][key])
        if name == 'a':
            for key, value, unit in [('feedRate', reference['massFlow'], 'kg/s'),
                ('feedFraction', reference['feedMassFraction'], '1'), ('feedTemperature', reference['feedTemperature'], 'K'),
                ('suppliedHeat', reference['heatRate'], 'W'), ('specificFlowWork', reference['specificFlowWork'], 'J/kg'),
                ('molarMass1', reference['molarMass'][0], 'kg/mol'), ('molarMass2', reference['molarMass'][1], 'kg/mol')]:
                parameter(key, datum('solve.'+key, value, unit))
            for index in (1, 2):
                reconstruct('amount'+str(index)+'(t)', document['selectedEquations']['amount.'+str(index)])
            selection['checks'] = [{'equationId': document['selectedEquations']['totalMass'],
                'scaleDataId': datum('scale.mass', reference['massScale'], 'kg')},
                {'equationId': document['selectedEquations']['energy'],
                 'scaleDataId': datum('scale.energy', reference['energyScale'], 'J')}]
        else:
            parameter('conductance', datum('solve.conductance', reference['conductance'], 'W/K'))
            selection['checks'] = [{'equationId': document['selectedEquations']['totalEnergy'],
                'scaleDataId': datum('scale.energy', reference['energyScale'], 'J')}]
    else:
        outputs = document['selectedEquations']
        for owner in ('upper', 'lower'):
            state(outputs[owner+'.mass'], owner+'__inicial_1')
            total(owner)
            for field, data in [('A_v', owner+'Area'), ('rho', 'density'), ('g', 'gravity')]:
                parameter(field+'__'+owner, data)
            parameter('p_r__'+owner+'(t)', owner+'Surface')
            parameter('z_0__'+owner, owner+'Floor')
            pressure = replayed.graph.nodes[outputs[owner+'.pressure']].equation.lhs
            selection['reconstructions'].append({'quantityId': quantity(pressure), 'equationId': outputs[owner+'.pressure']})
            reconstruct('h__'+owner+'(t)', outputs[owner+'.height'])
        state(outputs['flow'], 'initialFlow')
        for field, data in [('A', 'area'), ('L', 'length'), ('rho', 'density'), ('mu', 'viscosity')]:
            parameter(field+'__channel', data)
        parameter('R__channel', datum('solve.radius', reference['diameter']/2, 'm'))
        parameter('z1__channel', 'inletElevation')
        parameter('z2__channel', 'outletElevation')
        parameter('drive__channel(t)', 'drive')
        reconstruct('q__s2__1(t)', 'operation.19')
        reconstruct('m_total__channel(t)', 'momentum.channel.path.mass-definition')
        reconstruct('m__channel__1(t)', 'matter.channel.total-definition')
        selection['initialValues'][named('m__channel__1(t)')] = 'channel__inicial_1'
        selection['checks'] = [{'equationId': outputs['totalMass'],
            'scaleDataId': datum('scale.mass', reference['massScale'], 'kg')}]
    horizon = datum('solve.finalTime', reference['horizon'], 's', 'estudio')
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': horizon, 'metodoSolicitado': method,
        'muestras': reference['samples'], 'rtol': 1e-9, 'atol': {'cantidad': 1e-11, 'energia': 1e-6}}
    model['motores']['derivedExecution'] = selection
    return model, document, replayed
