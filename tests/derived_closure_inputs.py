"""Shared-law authors for package closures in derived execution (FD-1 to FD-4).

Fresh test sources, never product-library examples. The drum is built only
through the physical journals and the pinned Model operations of `SharedAuthor`:
no RHS, closure value or caloric constant is written here.
"""
import copy
import math

import numpy as np
import sympy as sp

from m1_acceptance import SharedAuthor, thermal_source
from core.balances import material_derivation as material, energy_derivation as energy
from core.termodinamica import derivation as thermodynamics
from core.modelo import leer_modelo_comun
from core.modelo.operation_journal import replay
from core.modelo.equation_workbench import build
from core.mathematics.dimensions import catalog
from core.compilador.derived import source_signature

OWNER = 'drum'
ETHANOL, WATER = '64-17-5', '7732-18-5'
PACKAGE_ID = 'unifac-dortmund-public'
T = sp.Symbol('t', real=True)

DRUM = {'P': 101325.0, 'm0': (20.0, 80.0), 'T0': 300.0, 'feed': 0.5, 'zF': (0.1, 0.9), 'TF': 330.0, 'PF': 2e5,
        'Q': 2.0e5, 'vent': 0.5, 'area': 0.5, 'Cd': 0.6, 'orifice': 1.5e-3, 'g': 9.80665, 'tf': 400.0}


def _datum(model, key, value, unit, role='parametro'):
    model['datos'][key] = {'magnitud': key, 'funcion': role, 'declaracion': {'texto': repr(float(value)), 'unidad': unit},
                           'origen': {'propietarioId': 'estudio', 'ruta': key}}
    return key


def drum_source(data=DRUM, policy=None, journal_extra=(), rigid=False):
    """Two-component drum with a prescribed pressure (or a closed rigid vessel) and a recorded package closure."""
    model = thermal_source((OWNER,))
    model.update(id='fd-package-drum', nombre='Package flash drum (test)')
    model['componentes'] = [{'id': 1, 'nombre': 'ethanol', 'simbolo': 'EtOH', 'identidadQuimica': {'cas': ETHANOL}},
                            {'id': 2, 'nombre': 'water', 'simbolo': 'H2O', 'identidadQuimica': {'cas': WATER}}]
    volume = model['volumenes'][0]
    volume['componenteIds'] = [1, 2]
    model['datos'][OWNER + '.mass2'] = copy.deepcopy(model['datos'][OWNER + '.mass'])
    volume['inicial']['cantidades']['datoIds']['2'] = OWNER + '.mass2'
    model['datos'][OWNER + '.mass']['declaracion']['texto'] = repr(data['m0'][0])
    model['datos'][OWNER + '.mass2']['declaracion']['texto'] = repr(data['m0'][1])
    model['datos'][OWNER + '.temperature']['declaracion']['texto'] = repr(data['T0'])
    model['termodinamica'] = {'paquetes': [{'id': 'pkg', 'modelo': {'id': PACKAGE_ID, 'version': '1'}}]}
    volume['termodinamica'] = {'tipo': 'equilibrio', 'paqueteId': 'pkg', 'politica': policy or
                               {'cantidad': 'sin_restriccion', 'cambioInterno': 'permitido', 'evaluacion': 'equilibrio_estable'}}
    journal = {'format': 'rage.material-derivation', 'version': 1, 'volumes': {}}
    for action in ['start', 'no_reaction'] + (['fixed_boundary'] if rigid else []) + ['integrate', 'total', 'impermeable_remainder']:
        journal = material.edit_journal(journal, OWNER, {'kind': action})
    model['motores']['materialDerivation'] = journal
    volume['supuestos']['materia'] = material.replay_volume(journal['volumes'][OWNER])[-1]
    ej = {'format': 'rage.energy-derivation', 'version': 1, 'volumes': {}}
    for action in ('start', 'pressure_stress', 'no_kinetic', 'no_viscous_work', 'no_body_work', 'no_volume_source',
                   'integrate', 'reynolds', 'total') + (('uniform_state', 'uniform_pressure') if rigid else ('enthalpy', 'uniform_state', 'uniform_pressure', 'prescribed_pressure')):
        ej = energy.edit_journal(ej, OWNER, {'kind': action})
    model['motores']['energyDerivation'] = ej
    tj = {'format': thermodynamics.FORMAT, 'version': 1, 'volumes': {}}
    tj = thermodynamics.edit_journal(tj, OWNER, {'kind': 'start'})
    tj = thermodynamics.edit_journal(tj, OWNER, {'kind': 'select_closure'}, thermodynamics.expected_closure(model, volume))
    for kind in journal_extra:
        tj = thermodynamics.edit_journal(tj, OWNER, {'kind': kind})
    model['motores']['thermodynamicDerivation'] = tj
    es = replay(ej['volumes'][OWNER], energy.fundamental, energy.normalize)[-1]
    ts = replay(tj['volumes'][OWNER], thermodynamics.fundamental, thermodynamics.normalize)[-1]
    volume['supuestos']['energia'] = {**es, **{k: v for k, v in ts.items() if k != 'closure'}}
    if rigid:
        _datum(model, OWNER + '.volume', data['V'], 'm3', 'frontera')
        volume['frontera'] = {'tipo': 'rigida', 'datoId': OWNER + '.volume'}
        model['corrientes'] = []
        return leer_modelo_comun(model)
    _datum(model, OWNER + '.pressure', data['P'], 'Pa', 'frontera')
    volume['frontera'] = {'tipo': 'presion_prescrita', 'presionId': OWNER + '.pressure'}
    _datum(model, 'feed.T', data['TF'], 'K', 'frontera')
    _datum(model, 'feed.P', data['PF'], 'Pa', 'frontera')
    model['corrientes'] = []
    for name in ('feed', 'liquid', 'vapour'):
        stream = {'id': name, 'desde': None if name == 'feed' else OWNER, 'hasta': OWNER if name == 'feed' else None,
                  'componenteIds': [1, 2], 'mecanismo': 'convectivo', 'constante': False,
                  'materia': {'modo': 'por_componente', 'base': 'masica', 'caudalIds': {}}}
        if name == 'feed':
            stream['estadoExterior'] = {'temperaturaId': 'feed.T', 'presion': {'tipo': 'dato', 'datoId': 'feed.P'},
                                        'composicion': {'base': 'molar', 'fracciones': {'1': data['zF'][0], '2': data['zF'][1]}}}
        model['corrientes'].append(stream)
    return leer_modelo_comun(model)


def author_drum(data=DRUM, donor_presence=True, vapour=True, **source):
    """Feed, a vapour donor, a liquid donor through an orifice on the liquid level, and a heat duty."""
    author = SharedAuthor(drum_source(data, **source))
    add, q = author.append, author.quantity
    o = OWNER
    f = lambda name: sp.Function(name)(T)
    m = [f(f'm__{o}__{i}') for i in (1, 2)]
    H = f('H__' + o)
    for name, unit in [('feedRate', 'kg/s'), ('ventCoefficient', '1/s'), ('heatDuty', 'W'), ('drumArea', 'm2'),
                       ('dischargeCoefficient', '1'), ('orificeArea', 'm2'), ('gravity', 'm/s2')]:
        add('declare_symbol', name=name, unit=unit)
    for name, unit in [('level', 'm'), ('liquidMolarOutflow', 'mol/s'), ('vapourMolarOutflow', 'mol/s')]:
        add('declare_function', name=name, unit=unit, dependencies=[q(T)])
    out = {}
    VL, vL = q(f('liquid_volume__' + o)), q(f(f'phase_v__{o}__L'))
    out['level'] = author.relation('level', f'{VL}/drumArea',
        'Vertical cylindrical drum with a flat bottom: liquid volume = area * level', kind='definition')
    out['liquidOutflow'] = author.relation('liquidMolarOutflow',
        f'dischargeCoefficient*orificeArea*(2*gravity*level)^(1/2)/{vL}',
        'Quasi-steady orifice discharge of the liquid at the floor, on a molar basis (W/M_L with rho_L = M_L/v_L)', kind='constitutive')
    out['vapourOutflow'] = None if not vapour else author.relation('vapourMolarOutflow', f"ventCoefficient*{q(f(f'phase_amount__{o}__V'))}",
        'Pressure-controlled vent: vapour withdrawn in proportion to the vapour holdup', kind='constitutive')
    for i, mass in enumerate(m, 1):
        current = next(k for k in author.selected if k.startswith(f'matter.{o}.') and author.source.nodes[k].equation.lhs == sp.diff(mass, T))
        M = q(sp.Symbol(f'molar_mass_{i}__{o}', real=True))
        presence = lambda label: (f"*{q(f(f'phase_present__{o}__{label}'))}" if donor_presence else '')
        feed = author.relation(q(f(f'q__feed__{i}')), f"feedRate*{q(f(f'inlet_mass_fraction_{i}__feed'))}",
            'Prescribed feed rate with the package composition of the declared inlet', kind='constitutive')
        if vapour:
            vapour_flow = author.relation(q(f(f'q__vapour__{i}')), f"vapourMolarOutflow{presence('V')}*{q(f(f'phase_x_{i}__{o}__V'))}*{M}",
                'Phase donor: the vent draws the vapour phase of this volume (zero when the vapour is absent)', kind='constitutive')
        else:
            vapour_flow = author.relation(q(f(f'q__vapour__{i}')), '0', 'Declared single liquid: the vent carries nothing')
        liquid = author.relation(q(f(f'q__liquid__{i}')), f"liquidMolarOutflow{presence('L')}*{q(f(f'phase_x_{i}__{o}__L'))}*{M}",
            'Phase donor: the orifice draws the liquid phase of this volume', kind='constitutive')
        out[f'feed.{i}'], out[f'vapour.{i}'], out[f'liquid.{i}'] = feed, vapour_flow, liquid
        for relation, stream in [(feed, 'feed'), (vapour_flow, 'vapour'), (liquid, 'liquid')]:
            current = author.substitute(current, relation, f(f'q__{stream}__{i}'))
        out[f'mass.{i}'] = current
    current = next(k for k in author.selected if k.startswith(f'energy.{o}.') and author.source.nodes[k].equation.lhs == sp.diff(H, T))
    for stream in ('feed', 'vapour', 'liquid'):
        for i in (1, 2):
            current = author.substitute(current, out[f'{stream}.{i}'], f(f'q__{stream}__{i}'), 'energy')
    for stream, right in [('feed', q(f('inlet_specific_enthalpy__feed'))),
                          *([('vapour', f"{q(f(f'phase_h__{o}__V'))}/{q(f(f'phase_M__{o}__V'))}")] if vapour else []),
                          ('liquid', f"{q(f(f'phase_h__{o}__L'))}/{q(f(f'phase_M__{o}__L'))}")]:
        average = f('energy_average_0__' + stream)
        relation = author.relation(q(average), right, 'Stream specific enthalpy from the package (donor phase or declared inlet)', 'energy', 'constitutive')
        current = author.substitute(current, relation, average, 'energy')
    heat = author.relation(q(f('energy_heat_rate__' + o)), 'heatDuty', 'Prescribed heat duty', 'energy')
    out['energy'] = author.substitute(current, heat, f('energy_heat_rate__' + o), 'energy')
    for name, source_key in [('drumArea', out['level']), ('dischargeCoefficient', out['liquidOutflow']),
                             ('orificeArea', out['liquidOutflow']), ('gravity', out['liquidOutflow'])]:
        add('declare_domain', sources=[source_key], symbol=name, domain='positive', reason='Positive geometry and discharge coefficient')
    add('declare_domain', sources=[out['liquidOutflow']], symbol='level', domain='positive', reason='Orifice submerged: positive liquid level')
    return author, out


def select_drum(author, out, data=DRUM, method='rk45'):
    model, result, _ = author.finish({})
    replayed = build(model)
    quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    named = lambda name: next(k for k, v in quantities.items() if str(v) == name)
    o = OWNER
    sel = {'format': 'rage.derived-execution', 'version': 1, 'sourceSignature': source_signature(model, replayed),
           'timeId': named('t'), 'states': [], 'parameters': {}, 'initialValues': {}, 'initialEquations': [],
           'reconstructions': [], 'checks': []}
    for i, key in zip((1, 2), (out['mass.1'], out['mass.2'])):
        sel['states'].append({'quantityId': named(f'm__{o}__{i}(t)'), 'equationId': key})
        sel['initialValues'][named(f'm__{o}__{i}(t)')] = o + ('.mass' if i == 1 else '.mass2')
        sel['reconstructions'].append({'quantityId': named(f'n_{i}__{o}(t)'), 'equationId': f'thermodynamics.{o}.component-amount-{i}'})
    sel['states'].append({'quantityId': named(f'H__{o}(t)'), 'equationId': out['energy']})
    sel['initialValues'][named(f'T__{o}(t)')] = o + '.temperature'
    for name, key in [('level(t)', out['level']), (f'm_total__{o}(t)', f'matter.{o}.total-definition')]:
        sel['reconstructions'].append({'quantityId': named(name), 'equationId': key})
    for name, key, value, unit in [(f'P__{o}(t)', o + '.pressure', None, None), ('feedRate', 'solve.F', data['feed'], 'kg/s'),
                                   ('ventCoefficient', 'solve.kV', data['vent'], '1/s'), ('heatDuty', 'solve.Q', data['Q'], 'W'),
                                   ('drumArea', 'solve.A', data['area'], 'm2'), ('dischargeCoefficient', 'solve.Cd', data['Cd'], '1'),
                                   ('orificeArea', 'solve.Ao', data['orifice'], 'm2'), ('gravity', 'solve.g', data['g'], 'm/s2')]:
        sel['parameters'][named(name)] = key if value is None else _datum(model, key, value, unit)
    sel['checks'] = [{'equationId': f'matter.{o}.total', 'scaleDataId': _datum(model, 'scale.mass', 100, 'kg')}]
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': _datum(model, 'solve.tf', data['tf'], 's', 'estudio'),
                        'metodoSolicitado': method, 'muestras': 81, 'rtol': 1e-9, 'atol': {'cantidad': 1e-9, 'energia': 1e-3}}
    model['motores']['derivedExecution'] = sel
    return model


def reference_drum(times, data=DRUM):
    """Independent DOP853 integration that calls core.mezclas directly (no bridge, no graph)."""
    from scipy.integrate import solve_ivp
    from core import mezclas
    s = mezclas.Sistema(PACKAGE_ID, [ETHANOL, WATER])
    M = np.asarray(s.M, dtype=float)
    zF = np.asarray(data['zF'])
    hF = s.equilibrio_TP(data['TF'], data['PF'], zF).H
    hF_mass = hF / float(zF @ M)
    wF = zF * M / float(zF @ M)
    seed = {'state': None}

    def closure(y):
        n = np.asarray(y[:2]) / M
        e = s.equilibrio_PH(data['P'], y[2], n)
        return n, e

    def rhs(t, y):
        n, e = closure(y)
        q = np.zeros(2); Hs = 0.0
        for phase in e.fases:
            if not phase.n > mezclas.N_AUSENTE * n.sum():
                continue
            x = np.asarray(phase.x)
            if phase.tipo == 'vapor':
                F = data['vent'] * phase.n
            else:
                level = phase.n * phase.v / data['area']
                F = data['Cd'] * data['orifice'] * math.sqrt(2 * data['g'] * level) / phase.v
            q += F * x * M
            Hs += F * phase.h
        dm = data['feed'] * wF - q
        dH = data['feed'] * hF_mass - Hs + data['Q']
        return [*dm, dH]

    n0 = np.asarray(data['m0']) / M
    H0 = s.equilibrio_TP(data['T0'], data['P'], n0).H
    sol = solve_ivp(rhs, (0, times[-1]), [*data['m0'], H0], method='DOP853', rtol=1e-10, atol=[1e-10, 1e-10, 1e-4], t_eval=times)
    temperatures = [closure(y)[1].T for y in sol.y.T]
    return sol, np.asarray(temperatures)


VESSEL = {'V': 0.15, 'm0': (20.0, 80.0), 'T0': 340.0, 'Q': 2.0e5, 'tf': 100.0}


def author_vessel(data=VESSEL):
    """Closed rigid vessel heated at a constant duty: the package UV closure sets T and the vapour pressure."""
    author = SharedAuthor(drum_source(data, rigid=True))
    o = OWNER
    f = lambda name: sp.Function(name)(T)
    author.append('declare_symbol', name='heatDuty', unit='W')
    U = f('U__' + o)
    current = next(k for k in author.selected if k.startswith(f'energy.{o}.') and author.source.nodes[k].equation.lhs == sp.diff(U, T))
    heat = author.relation(author.quantity(f('energy_heat_rate__' + o)), 'heatDuty', 'Prescribed heat duty', 'energy')
    out = {'energy': author.substitute(current, heat, f('energy_heat_rate__' + o), 'energy')}
    for i in (1, 2):
        out[f'mass.{i}'] = next(k for k in author.selected if k.startswith(f'matter.{o}.') and author.source.nodes[k].equation.lhs == sp.diff(f(f'm__{o}__{i}'), T))
    return author, out


def select_vessel(author, out, data=VESSEL, method='rk45'):
    model, result, _ = author.finish({})
    replayed = build(model)
    quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    named = lambda name: next(k for k, v in quantities.items() if str(v) == name)
    o = OWNER
    sel = {'format': 'rage.derived-execution', 'version': 1, 'sourceSignature': source_signature(model, replayed),
           'timeId': named('t'), 'states': [], 'parameters': {}, 'initialValues': {}, 'initialEquations': [],
           'reconstructions': [], 'checks': []}
    for i in (1, 2):
        sel['states'].append({'quantityId': named(f'm__{o}__{i}(t)'), 'equationId': out[f'mass.{i}']})
        sel['initialValues'][named(f'm__{o}__{i}(t)')] = o + ('.mass' if i == 1 else '.mass2')
        sel['reconstructions'].append({'quantityId': named(f'n_{i}__{o}(t)'), 'equationId': f'thermodynamics.{o}.component-amount-{i}'})
    sel['states'].append({'quantityId': named(f'U__{o}(t)'), 'equationId': out['energy']})
    sel['initialValues'][named(f'T__{o}(t)')] = o + '.temperature'
    sel['parameters'][named(f'V__{o}(t)')] = o + '.volume'
    sel['parameters'][named('heatDuty')] = _datum(model, 'solve.Q', data['Q'], 'W')
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': _datum(model, 'solve.tf', data['tf'], 's', 'estudio'),
                        'metodoSolicitado': method, 'muestras': 61, 'rtol': 1e-9, 'atol': {'cantidad': 1e-9, 'energia': 1e-3}}
    model['motores']['derivedExecution'] = sel
    return model


def reference_vessel(times, data=VESSEL):
    """Closed form in time (dU/dt = Q) with core.mezclas.equilibrio_UV called directly at each sample."""
    from core import mezclas
    from scipy.optimize import brentq
    s = mezclas.Sistema(PACKAGE_ID, [ETHANOL, WATER])
    n = np.asarray(data['m0']) / np.asarray(s.M, dtype=float)
    U0 = brentq(lambda U: s.equilibrio_UV(U, data['V'], n).T - data['T0'], -2.0e8, -1.9e8, xtol=1e-6, rtol=1e-15)  # two-phase bracket around 340 K
    states = [s.equilibrio_UV(U0 + data['Q'] * t, data['V'], n) for t in times]
    return U0, states
