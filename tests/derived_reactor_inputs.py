"""Shared-law author of a liquid-only esterification batch reactor (F5-C2, F5-C3, F5-C4).

Fresh test source, never a product-library example. The caloric inventory,
temperature and reaction heat come from the selected package with the
recorded liquid formation reference; no caloric constant is authored.
"""
import copy

import sympy as sp

from m1_acceptance import SharedAuthor, thermal_source
from core.balances import material_derivation as material, energy_derivation as energy
from core.termodinamica import derivation as thermodynamics
from core.modelo import leer_modelo_comun
from core.modelo.operation_journal import replay
from core.modelo.equation_workbench import build
from core.mathematics.dimensions import catalog
from core.compilador.derived import source_signature
from derived_closure_inputs import ETHANOL, WATER, PACKAGE_ID, T, _datum

ACETIC_ACID, ETHYL_ACETATE = '64-19-7', '141-78-6'
SPECIES = (ETHANOL, ACETIC_ACID, ETHYL_ACETATE, WATER)
REACTOR = {'n0': (5.0, 5.0, 0.0, 0.0), 'V': 6.5e-4, 'P': 101325.0, 'T0': 330.0, 'Tj': 330.0, 'UA': 50.0,
           'kf': 2e-5, 'kr': 1e-5, 'E': 0.0, 'Tref': 330.0, 'tf': 3000.0}
ELEMENTS = {'C': (2, 2, 4, 0), 'H': (6, 4, 8, 2), 'O': (1, 2, 2, 1)}
LIQUID_POLICY = {'cantidad': 'monofasico', 'cambioInterno': 'prohibido', 'evaluacion': 'equilibrio_estable', 'tiposPermitidos': ['liquido']}
OWNER = 'cell'


def reactor_model(data=REACTOR, journal_extra=('liquid_only', 'liquid_formation_reference'), policy=LIQUID_POLICY):
    from core.mezclas_datos import especie
    owner = OWNER
    model = thermal_source((owner,))
    model.update(id='f5-package-reactor', nombre='Package esterification reactor (test)')
    names = ('ethanol', 'acetic acid', 'ethyl acetate', 'water')
    model['componentes'] = [{'id': i, 'nombre': name, 'simbolo': 'C%d' % i, 'identidadQuimica': {'cas': cas}}
                            for i, (name, cas) in enumerate(zip(names, SPECIES), 1)]
    volume = model['volumenes'][0]
    volume['componenteIds'] = [1, 2, 3, 4]
    model['termodinamica'] = {'paquetes': [{'id': 'pkg', 'modelo': {'id': PACKAGE_ID, 'version': '1'}}]}
    volume['termodinamica'] = {'tipo': 'equilibrio', 'paqueteId': 'pkg', 'politica': copy.deepcopy(policy)}
    journal = {'format': 'rage.material-derivation', 'version': 1, 'volumes': {}}
    for action in ('start', 'fixed_boundary', 'integrate', 'total', 'impermeable_remainder', 'uniform_generation', 'uniform_consumption'):
        journal = material.edit_journal(journal, owner, {'kind': action})
    model['motores']['materialDerivation'] = journal
    volume['supuestos']['materia'] = material.replay_volume(journal['volumes'][owner])[-1]
    ej = model['motores']['energyDerivation']
    tj = {'format': thermodynamics.FORMAT, 'version': 1, 'volumes': {}}
    tj = thermodynamics.edit_journal(tj, owner, {'kind': 'start'})
    tj = thermodynamics.edit_journal(tj, owner, {'kind': 'select_closure'}, thermodynamics.expected_closure(model, volume))
    for kind in journal_extra:
        tj = thermodynamics.edit_journal(tj, owner, {'kind': kind})
    model['motores']['thermodynamicDerivation'] = tj
    es = replay(ej['volumes'][owner], energy.fundamental, energy.normalize)[-1]
    ts = replay(tj['volumes'][owner], thermodynamics.fundamental, thermodynamics.normalize)[-1]
    volume['supuestos']['energia'] = {**es, **{k: v for k, v in ts.items() if k != 'closure'}}
    datum = lambda key, value, unit, role='parametro': _datum(model, key, value, unit, role)
    volume['inicial']['cantidades'] = {'base': 'molar', 'datoIds': {str(i): datum('initial%d' % i, data['n0'][i - 1], 'mol', 'inicial') for i in (1, 2, 3, 4)}}
    config = {'volumeDataId': datum('reactingVolume', data['V'], 'm3'),
              'molarMassDataIds': {str(i): datum('molarMass%d' % i, especie(cas).M, 'kg/mol') for i, cas in enumerate(SPECIES, 1)},
              'elements': {element: {str(i): count for i, count in enumerate(counts, 1)} for element, counts in ELEMENTS.items()},
              'reactions': [{'id': 'esterification', 'stoichiometry': {'1': '-1', '2': '-1', '3': '1', '4': '1'}, 'orders': {'1': 1, '2': 1},
                             'rateConstantDataId': datum('forwardRate', data['kf'], 'm3/(mol*s)')},
                            {'id': 'hydrolysis', 'stoichiometry': {'1': '1', '2': '1', '3': '-1', '4': '-1'}, 'orders': {'3': 1, '4': 1},
                             'rateConstantDataId': datum('reverseRate', data['kr'], 'm3/(mol*s)')}]}
    if data['E']:
        reference = datum('rateTemperature', data['Tref'], 'K')
        energies = [datum('activation', data['E'], 'J/mol')]
        energies.append(datum('reverseActivation', data['Er'], 'J/mol') if 'Er' in data else energies[0])
        for reaction, energy_id in zip(config['reactions'], energies):
            reaction['arrhenius'] = {'energyDataId': energy_id, 'temperatureDataId': reference}
    model['motores']['kineticReactions'] = {'format': 'rage.kinetic-reactions', 'version': 1, 'volumes': {owner: config}}
    volume['frontera'] = {'tipo': 'rigida', 'datoId': config['volumeDataId']}
    datum(owner + '.pressure', data['P'], 'Pa', 'frontera')
    datum(owner + '.temperature', data['T0'], 'K', 'inicial')
    model['corrientes'] = []
    return leer_modelo_comun(model)


def author_reactor(data=REACTOR, **source):
    """Component mass laws reach dn_i/dt = sum_j nu_ij r_j V; the jacket enters the first law; no caloric constant."""
    from core.balances.reaction_equations import declarations
    owner = OWNER
    model = reactor_model(data, **source)
    author = SharedAuthor(model)
    amounts = [sp.Function('amount_%d__%s' % (c, owner))(T) for c in (1, 2, 3, 4)]
    outputs = []
    for c, n in zip(('1', '2', '3', '4'), amounts):
        m = sp.Function('m__' + owner + '__' + c)(T)
        key = next(k for k in author.selected if k.startswith('matter.' + owner + '.' + c + '.') and author.source.nodes[k].equation.lhs == sp.diff(m, T))
        key = author.append('substitute', sources=[key], relation='reaction.' + owner + '.amount.' + c, symbol=author.quantity(m))
        key = author.append('expand', sources=[key])
        for source_kind, stem in [('generation', 'g'), ('consumption', 'c')]:
            key = author.append('substitute', sources=[key], relation='reaction.' + owner + '.' + source_kind + '.' + c,
                                symbol=author.quantity(sp.Function(stem + '__' + owner + '__' + c)(T)))
        key = author.append('isolate', sources=[key], symbol=author.quantity(sp.diff(n, T)))
        outputs.append(key)
    U = sp.Function('U__' + owner)(T)
    for name, unit in [('jacketConductance', 'W/K'), ('jacketTemperature', 'K')]:
        author.append('declare_symbol', family='energy', name=name, unit=unit)
    energy_key = next(k for k in author.selected if k.startswith('energy.' + owner + '.') and author.source.nodes[k].equation.lhs == sp.diff(U, T))
    heat_rate = sp.Function('energy_heat_rate__' + owner)(T)
    jacket = author.relation(author.quantity(heat_rate), f"jacketConductance*(jacketTemperature-{author.quantity(sp.Function('T__' + owner)(T))})",
                             'Jacket heat transfer with a declared overall conductance', 'energy', 'constitutive')
    energy_key = author.substitute(energy_key, jacket, heat_rate, 'energy')
    model, _, _ = author.finish({})
    replayed = build(model)
    quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    qid = lambda q: next(k for k, v in quantities.items() if v == q)
    _, _, bindings, _ = declarations(model, owner)
    selection = {'format': 'rage.derived-execution', 'version': 1, 'sourceSignature': source_signature(model, replayed),
                 'timeId': qid(T), 'states': [{'quantityId': qid(q), 'equationId': k} for q, k in zip(amounts, outputs)],
                 'parameters': {qid(q): d for q, d in bindings.items()},
                 'initialValues': {qid(n): 'initial%d' % i for i, n in enumerate(amounts, 1)}, 'initialEquations': [],
                 'reconstructions': [], 'checks': []}
    selection['states'].append({'quantityId': qid(U), 'equationId': energy_key})
    selection['initialValues'][qid(sp.Function('T__' + owner)(T))] = owner + '.temperature'
    for c in (1, 2, 3, 4):
        selection['reconstructions'].append({'quantityId': qid(sp.Function('n_%d__%s' % (c, owner))(T)), 'equationId': 'thermodynamics.%s.component-amount-%d' % (owner, c)})
    selection['parameters'][qid(sp.Function('P__' + owner)(T))] = owner + '.pressure'
    selection['parameters'][qid(sp.Function('V__' + owner)(T))] = 'reactingVolume'
    selection['parameters'][qid(replayed.introduced['jacketConductance'])] = _datum(model, 'jacket.UA', data['UA'], 'W/K')
    selection['parameters'][qid(replayed.introduced['jacketTemperature'])] = _datum(model, 'jacket.T', data['Tj'], 'K')
    selection['reconstructions'].append({'quantityId': qid(sp.Function('m_total__' + owner)(T)), 'equationId': 'matter.' + owner + '.total-definition'})
    selection['checks'].append({'equationId': 'matter.' + owner + '.total', 'scaleDataId': _datum(model, 'massScale', 1, 'kg')})
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': _datum(model, 'duration', data['tf'], 's', 'estudio'),
                        'metodoSolicitado': 'rk45', 'muestras': 61, 'rtol': 1e-9, 'atol': {'cantidad': 1e-10, 'energia': 1e-4}}
    model['motores']['derivedExecution'] = selection
    return model


def reference_reactor(times, data=REACTOR):
    """Independent DOP853 batch integration.

    The caloric inventory is H = sum_i n_i (mu_i - T dmu_i/dT) from the package chemical potentials of
    core.reactions.chemical_equilibrium.PackagePhase (liquid formation anchor), by a second-order central
    difference in T, and U = H - P sum_i n_i v_L,i: a different route from the bridge's partial-molar sum.
    """
    import numpy as np
    from scipy.integrate import solve_ivp
    from scipy.optimize import brentq
    from core import mezclas
    from core.reactions.chemical_equilibrium import PackagePhase
    phase = PackagePhase(mezclas.Sistema(PACKAGE_ID, list(SPECIES), solo_liquido=True), 'liquido', anchor='liquid')
    vL = np.array([e.vL for e in phase.sistema.esp])
    P = data['P']

    def internal_energy(T, n):
        dT = 1e-3
        present = n > 0   # an absent species contributes nothing; evaluate it at a 1e-30 mol trace (finite ln x)
        trace = np.where(present, n, 1e-30)
        mu = phase.mu(T, P, trace)
        dmu = (phase.mu(T + dT, P, trace) - phase.mu(T - dT, P, trace)) / (2 * dT)
        h = mu - T * dmu
        return float(n[present] @ h[present]) - P * float(n @ vL)

    def temperature(U, n):
        lo, hi = phase.sistema.T_rango   # the central difference needs T +- 1e-3 K inside the domain
        return brentq(lambda T: internal_energy(T, n) - U, lo + 2e-3, hi - 2e-3, xtol=1e-11, rtol=1e-15)

    def rhs(t, y):
        n, U = np.asarray(y[:4]), y[4]
        T = temperature(U, n)
        c = n / data['V']
        arrhenius = lambda E: np.exp(-E / 8.314462618 * (1 / T - 1 / data['Tref'])) if data['E'] else 1.0
        r = data['kf'] * arrhenius(data['E']) * c[0] * c[1] - data['kr'] * arrhenius(data.get('Er', data['E'])) * c[2] * c[3]
        return [*(np.array([-1, -1, 1, 1]) * r * data['V']), data['UA'] * (data['Tj'] - T)]

    n0 = np.asarray(data['n0'], dtype=float)
    U0 = internal_energy(data['T0'], n0)
    sol = solve_ivp(rhs, (0, times[-1]), [*n0, U0], method='DOP853', rtol=1e-11, atol=[1e-12] * 4 + [1e-6], t_eval=times)
    return sol, np.array([temperature(y[4], np.asarray(y[:4])) for y in sol.y.T])
