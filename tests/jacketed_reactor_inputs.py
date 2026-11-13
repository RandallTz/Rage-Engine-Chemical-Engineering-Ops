"""Dynamic cooling jacket as a service control volume, and the jacketed stirred-tank reactor (F4).

`dec-composable-operations` rules 3 and 4: the jacket is its own control volume
with its own deduction (component mass conservation, the first law and the
thermodynamic closure of the coolant), and it is coupled to the reacting volume
only at the shared wall through one constitutive relation. The same heat
quantity enters both first laws with opposite signs by construction: it is one
declared quantity, partitioned into each volume's boundary heat by recorded
relations, never two independent terms.

Fresh test sources, never product-library examples. Everything below records
premises through the family journals and the shared equation workbench
(`SharedAuthor`); no final balance, closure value or caloric constant is typed.
"""
import copy
import sys
from pathlib import Path

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from core.balances import material_derivation as material, energy_derivation as energy, momentum_derivation as momentum
from core.termodinamica import derivation as thermodynamics
from core.modelo import leer_modelo_comun
from core.modelo.operation_journal import replay
from core.modelo.equation_workbench import build
from core.mathematics.dimensions import catalog
from core.compilador.derived import source_signature
from m1_acceptance import SharedAuthor
from derived_closure_inputs import WATER, PACKAGE_ID, T, _datum
from derived_reactor_inputs import LIQUID_POLICY, OWNER as REACTOR, SPECIES
from derived_momentum_inputs import author_outlet, select_outlet, PIPE, STORAGE_FLAGS
from demo02_drum import MATERIAL
import demo02_cstr

JACKET = 'jacket'
COOLANT_IN, COOLANT_OUT = 'coolantIn', 'coolantOut'

# Service data: water coolant, pumped at a prescribed rate; the jacket is filled and rigid.
SERVICE = {'Pj': 101325.0, 'mj0': 0.2, 'Tj0': 320.0, 'coolantFlow': 2e-3, 'Tin': 320.0, 'Pin': 2e5,
           'UA': 50.0, 'Tprocess': 335.0, 'tf': 600.0}
# Jacketed reactor: the accepted Demo 0.2 continuous reactor data plus the service data.
JACKETED = dict(demo02_cstr.DEMO, **{k: v for k, v in SERVICE.items() if k not in ('Tprocess', 'tf')}, tf=6000.0)


def _journal(model, key, fmt):
    return model['motores'].setdefault(key, {'format': fmt, 'version': 1, 'volumes': {}})


def jacket_shell(data=SERVICE):
    """A document with the coolant species and the package, and no volume yet."""
    return {'formato': 'rage.modelo', 'version': 0, 'id': 'jacket-service', 'nombre': 'Cooling jacket service (test)',
            'componentes': [{'id': 1, 'nombre': 'water', 'simbolo': 'H2O', 'identidadQuimica': {'cas': WATER}}],
            'termodinamica': {'paquetes': [{'id': 'pkg', 'modelo': {'id': PACKAGE_ID, 'version': '1'}}]},
            'volumenes': [], 'corrientes': [], 'intercambios': [], 'datos': {}, 'matematico': None, 'estudio': None,
            'motores': {}, 'procedencia': {'tipo': 'nuevo'}}


def add_jacket_volume(model, data=SERVICE, owner=JACKET, component=1, package='pkg', momentum_balance=False):
    """Append the jacket control volume, its coolant streams and its three family journals.

    Matter: local component conservation -> integrate (Gauss, Reynolds) -> inventories and
    stream partition -> impermeable remainder; no reaction. Energy: local first law ->
    pressure/viscous split, negligible kinetic, viscous, body and volumetric terms ->
    integrate, Reynolds, total -> enthalpy transport -> uniform state and pressure ->
    prescribed pressure (the pumped loop sets it). Thermodynamics: fundamental relation ->
    the configured package closure -> liquid only -> liquid formation reference. With
    momentum_balance, Cauchy's law is reduced to the hydrostatic storage field (pressure and
    viscous stress split, negligible convection and viscous stress, no local accumulation,
    uniform vertical gravity, reference density, pressure reference): the jacket liquid is at
    rest at the scale of the balance.
    """
    volume = {'id': owner, 'componenteIds': [component], 'balances': {'materia': True, 'energia': True, 'momento': bool(momentum_balance)},
              'supuestos': {},
              'frontera': {'tipo': 'presion_prescrita', 'presionId': _datum(model, owner + '.pressure', data['Pj'], 'Pa', 'frontera')},
              'inicial': {'cantidades': {'base': 'masica', 'datoIds': {str(component): _datum(model, owner + '.mass', data['mj0'], 'kg', 'inicial')}},
                          'energia': {'tipo': 'T', 'datoId': _datum(model, owner + '.temperature', data['Tj0'], 'K', 'inicial')}},
              'termodinamica': {'tipo': 'equilibrio', 'paqueteId': package, 'politica': copy.deepcopy(LIQUID_POLICY)}}
    model['volumenes'].append(volume)
    mj = _journal(model, 'materialDerivation', 'rage.material-derivation')
    for action in ('start', 'no_reaction', 'integrate', 'total', 'impermeable_remainder'):
        mj = material.edit_journal(mj, owner, {'kind': action})
    model['motores']['materialDerivation'] = mj
    volume['supuestos']['materia'] = material.replay_volume(mj['volumes'][owner])[-1]
    ej = _journal(model, 'energyDerivation', 'rage.energy-derivation')
    for action in ('start', 'pressure_stress', 'no_kinetic', 'no_viscous_work', 'no_body_work', 'no_volume_source',
                   'integrate', 'reynolds', 'total', 'enthalpy', 'uniform_state', 'uniform_pressure', 'prescribed_pressure'):
        ej = energy.edit_journal(ej, owner, {'kind': action})
    model['motores']['energyDerivation'] = ej
    tj = _journal(model, 'thermodynamicDerivation', thermodynamics.FORMAT)
    tj = thermodynamics.edit_journal(tj, owner, {'kind': 'start'})
    tj = thermodynamics.edit_journal(tj, owner, {'kind': 'select_closure'}, thermodynamics.expected_closure(model, volume))
    for kind in ('liquid_only', 'liquid_formation_reference'):
        tj = thermodynamics.edit_journal(tj, owner, {'kind': kind})
    model['motores']['thermodynamicDerivation'] = tj
    es = replay(ej['volumes'][owner], energy.fundamental, energy.normalize)[-1]
    ts = replay(tj['volumes'][owner], thermodynamics.fundamental, thermodynamics.normalize)[-1]
    volume['supuestos']['energia'] = {**es, **{k: v for k, v in ts.items() if k != 'closure'}}
    if momentum_balance:
        mo = _journal(model, 'momentumDerivation', momentum.FORMAT)
        mo = momentum.edit_journal(mo, owner, {'kind': 'start'})
        for flag in STORAGE_FLAGS:
            mo = momentum.edit_journal(mo, owner, {'kind': 'set_assumption', 'name': flag, 'value': True})
        model['motores']['momentumDerivation'] = mo
    _datum(model, COOLANT_IN + '.T', data['Tin'], 'K', 'frontera')
    _datum(model, COOLANT_IN + '.P', data['Pin'], 'Pa', 'frontera')
    model['corrientes'].append({'id': COOLANT_IN, 'desde': None, 'hasta': owner, 'componenteIds': [component], 'mecanismo': 'convectivo',
                                'constante': False, 'materia': {'modo': 'por_componente', 'base': 'masica', 'caudalIds': {}},
                                'estadoExterior': {'temperaturaId': COOLANT_IN + '.T', 'presion': {'tipo': 'dato', 'datoId': COOLANT_IN + '.P'},
                                                   'composicion': {'base': 'molar', 'fracciones': {str(component): 1.0}}}})
    model['corrientes'].append({'id': COOLANT_OUT, 'desde': owner, 'hasta': None, 'componenteIds': [component], 'mecanismo': 'convectivo',
                                'constante': False, 'materia': {'modo': 'por_componente', 'base': 'masica', 'caudalIds': {}},
                                'extraccion': {owner: {'tipo': 'fase', 'fase': 'liquido'}}})
    return model


def jacket_source(data=SERVICE):
    return leer_modelo_comun(add_jacket_volume(jacket_shell(data), data, momentum_balance=True))


def _balance(author, family, owner, quantity):
    """The current source balance of `family` for `owner` whose left side is d quantity/dt."""
    return next(k for k in author.selected if k.startswith(family + '.' + owner + '.')
                and author.source.nodes[k].equation.lhs == sp.diff(quantity, T))


def wall_law(author, hot, cold):
    """One declared wall heat quantity and its constitutive law: wallHeat = wallConductance (T_hot - T_cold).

    hot/cold are quantity ids (an engine temperature or a declared symbol). Positive wallHeat
    flows from the hot side into the cold side; each volume's boundary partition fixes its sign.
    """
    add = author.append
    add('declare_function', 'energy', name='wallHeat', unit='W', dependencies=[author.quantity(T)])
    add('declare_symbol', 'energy', name='wallConductance', unit='W/K')
    law = author.relation('wallHeat', f'wallConductance*({hot}-{cold})',
                          'Conductive shared wall between the two control volumes: the wall is impermeable and rigid (no mass flux and no '
                          'boundary work cross it), its metal capacitance is lumped into the overall conductance, and the heat flux '
                          'integrated over the shared wall follows a linear overall-conductance law', 'energy', 'constitutive')
    add('declare_domain', 'energy', sources=[law], symbol='wallConductance', domain='positive',
        reason='Passive conductive wall: positive overall conductance')
    return law


def reactor_wall_partition(author, owner):
    """Heat builder for `author_outlet`: the reactor's boundary heat is the shared wall only.

    The reactor receives -wallHeat (wallHeat is counted from the reactor into the jacket).
    The constitutive law is substituted later, after the jacket is deduced, so that the
    same declared quantity reaches both balances.
    """
    f = lambda name: sp.Function(name)(T)
    q = author.quantity
    law = wall_law(author, q(f('T__' + owner)), q(f('T__' + JACKET)))
    author.wall_law = law
    return author.relation(q(f('energy_heat_rate__' + owner)), '-wallHeat',
                           'Exhaustive partition of the reactor boundary heat: the shared wall with the jacket is its only conductive part '
                           '(the free surface and the remaining casing are insulated); heat leaving the reactor into the jacket counts negative',
                           'energy', 'constraint')


def author_jacket(author, owner=JACKET, component=1, process_temperature=None, law=None):
    """Record the jacket's deduction on an author whose source already holds the jacket volume.

    process_temperature: quantity id of the other body's temperature (coupled model) or None
    (standalone service template: a declared port variable `processTemperature`).
    law: the shared wall relation already declared by the reactor side, or None to declare it here.
    Returns the rows of the state equations and of the published intermediates.
    """
    add, q = author.append, author.quantity
    f = lambda name: sp.Function(name)(T)
    j, i = owner, component
    out = {}
    m, H = f(f'm__{j}__{i}'), f('H__' + j)
    M = q(sp.Symbol(f'molar_mass_{i}__{j}', real=True))
    ML = q(f(f'phase_M__{j}__L'))
    # --- matter: prescribed supply, liquid donor return at the supply rate ---------------------------
    add('declare_symbol', name='coolantFlow', unit='kg/s')
    add('declare_function', name='coolantReturnFlow', unit='kg/s', dependencies=[q(T)])
    supply = author.relation(q(f(f'q__{COOLANT_IN}__{i}')), 'coolantFlow',
                             'Prescribed service supply: the coolant pump sets the mass flow entering the jacket', kind='constitutive')
    fraction, mole = 'coolantMassFraction', 'coolantMoleFraction'
    add('declare_function', name=fraction, unit='1', dependencies=[q(T)])
    add('declare_function', name=mole, unit='1', dependencies=[q(T)])
    donor_fraction = author.relation(mole, q(f(f'phase_x_{i}__{j}__L')),
                                     'Phase donor: the return stream has the liquid phase composition of the jacket', kind='constitutive')
    mass_basis = author.relation(f'{fraction}*{ML}', f'{mole}*{M}',
                                 'Definition of mass fraction from mole fraction, component molar mass and the phase mean molar mass', kind='definition')
    mass_basis = author.substitute(mass_basis, donor_fraction, f(mole))
    mass_basis = add('isolate', sources=[mass_basis], symbol=fraction)
    out['coolantMassFraction'] = mass_basis
    transport = author.relation(q(f(f'q__{COOLANT_OUT}__{i}')), f'coolantReturnFlow*{fraction}',
                                'Definition of component mass flow of the return stream for a common convective stream velocity', kind='definition')
    returned = author.relation('coolantReturnFlow', 'coolantFlow',
                               'Filled rigid jacket of a liquid whose molar volume the package takes as constant: the liquid volume cannot '
                               'change, so the return line carries the supply rate', kind='constitutive')
    transport = author.substitute(transport, mass_basis, f(fraction))
    transport = author.substitute(transport, returned, f('coolantReturnFlow'))
    out['return'] = transport
    current = _balance(author, 'matter', j, m)
    current = author.substitute(current, supply, f(f'q__{COOLANT_IN}__{i}'))
    out['jacket.mass'] = author.substitute(current, transport, f(f'q__{COOLANT_OUT}__{i}'))
    # --- energy: stream enthalpies from the package, boundary heat partition ------------------------
    current = _balance(author, 'energy', j, H)
    current = author.substitute(current, supply, f(f'q__{COOLANT_IN}__{i}'), 'energy')
    current = author.substitute(current, transport, f(f'q__{COOLANT_OUT}__{i}'), 'energy')
    inlet = author.relation(q(f('energy_average_0__' + COOLANT_IN)), q(f('inlet_specific_enthalpy__' + COOLANT_IN)),
                            'Inlet stream specific enthalpy at its declared exterior state (package)', 'energy', 'constitutive')
    out['enthalpy.coolantIn'] = inlet
    current = author.substitute(current, inlet, f('energy_average_0__' + COOLANT_IN), 'energy')
    add('declare_function', 'energy', name='coolantMolarEnthalpy', unit='J/mol', dependencies=[q(T)])
    donor = author.relation('coolantMolarEnthalpy', q(f(f'phase_h__{j}__L')),
                            'The return stream draws the jacket liquid at its thermodynamic state (negligible stream kinetic energy; '
                            'the pressure dependence of the liquid enthalpy over the loop pressure change is neglected)', 'energy', 'constitutive')
    average = f('energy_average_0__' + COOLANT_OUT)
    basis = author.relation(f'{q(average)}*{ML}', 'coolantMolarEnthalpy',
                            'Definition of molar enthalpy from mass-specific enthalpy and the mean molar mass', 'energy', 'definition')
    basis = author.substitute(basis, donor, f('coolantMolarEnthalpy'), 'energy')
    outlet = add('isolate', 'energy', sources=[basis], symbol=q(average))
    out['enthalpy.coolantOut'] = outlet
    current = author.substitute(current, outlet, average, 'energy')
    add('declare_function', 'energy', name='ambientHeat', unit='W', dependencies=[q(T)])
    if law is None:
        add('declare_symbol', 'energy', name='processTemperature', unit='K')
        law = wall_law(author, 'processTemperature', q(f('T__' + j)))
    out['wallLaw'] = law
    partition = author.relation(q(f('energy_heat_rate__' + j)), 'wallHeat+ambientHeat',
                                'Partition of the jacket boundary heat into its two conductive parts: the wall shared with the process '
                                'volume (positive into the jacket) and the outer casing', 'energy', 'definition')
    insulated = author.relation('ambientHeat', '0', 'Insulated outer casing: no heat crosses the jacket boundary to the surroundings',
                                'energy', 'constraint')
    current = author.substitute(current, partition, f('energy_heat_rate__' + j), 'energy')
    current = author.substitute(current, insulated, f('ambientHeat'), 'energy')
    out['jacket.heat'] = current
    out['jacket.energy'] = add('substitute', 'energy', sources=[current], relation=law, symbol='wallHeat')
    add('declare_domain', 'energy', sources=[out['jacket.energy']], symbol='coolantFlow', domain='nonnegative',
        reason='Forward service flow: the donor orientation of the return stream')
    return out


# --- standalone service template ------------------------------------------------------------------

def jacket_template(owner=JACKET):
    return {'format': 'rage.model-template', 'version': 1, 'id': 'jacket-service', 'templateVersion': '1', 'equipment': True,
            'recipe': {'journals': ['materialDerivation', 'energyDerivation', 'momentumDerivation', 'thermodynamicDerivation', 'equationWorkbench']},
            'ports': [
                {'id': 'supply', 'volumeId': owner, 'direction': 'inlet', 'kind': 'material', 'boundary': {'type': 'stream', 'id': COOLANT_IN},
                 'exteriorState': 'estadoExterior', 'variables': copy.deepcopy(MATERIAL)},
                {'id': 'return', 'volumeId': owner, 'direction': 'outlet', 'kind': 'material', 'boundary': {'type': 'stream', 'id': COOLANT_OUT},
                 'donorPhase': 'liquido', 'variables': copy.deepcopy(MATERIAL)},
                {'id': 'wall', 'volumeId': owner, 'direction': 'inlet', 'kind': 'heat', 'boundary': {'type': 'term', 'id': 'calor'},
                 'variables': {'power': {'unitSI': 'W'}}}]}


def author_jacket_service(data=SERVICE, method='rk45'):
    """The jacket alone: the process-side temperature is the wall port's variable."""
    author = SharedAuthor(jacket_source(data))
    out = author_jacket(author, JACKET, 1, None, None)
    author.model['template'] = jacket_template()
    model, _, _ = author.finish({})
    replayed = build(model)
    quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    named = lambda name: next(k for k, v in quantities.items() if str(v) == name)
    j = JACKET
    sel = {'format': 'rage.derived-execution', 'version': 1, 'sourceSignature': None,
           'timeId': named('t'), 'states': [], 'parameters': {}, 'initialValues': {}, 'initialEquations': [],
           'reconstructions': [], 'checks': []}
    _jacket_selection(sel, model, quantities, out, data, j, 1)
    sel['parameters'][named('processTemperature')] = _datum(model, 'service.Tprocess', data['Tprocess'], 'K')
    sel['checks'] = [{'equationId': f'matter.{j}.total', 'scaleDataId': _datum(model, 'scale.mass', 1, 'kg')}]
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': _datum(model, 'solve.tf', data['tf'], 's', 'estudio'),
                        'metodoSolicitado': method, 'muestras': 61, 'rtol': 1e-9, 'atol': {'cantidad': 1e-9, 'energia': 1e-3}}
    model['motores']['derivedExecution'] = sel
    sel['sourceSignature'] = source_signature(model, replayed)
    return model, out


def _jacket_selection(sel, model, quantities, out, data, j, i):
    named = lambda name: next(k for k, v in quantities.items() if str(v) == name)
    sel['states'].append({'quantityId': named(f'm__{j}__{i}(t)'), 'equationId': out['jacket.mass']})
    sel['initialValues'][named(f'm__{j}__{i}(t)')] = j + '.mass'
    sel['reconstructions'].append({'quantityId': named(f'n_{i}__{j}(t)'), 'equationId': f'thermodynamics.{j}.component-amount-{i}'})
    sel['states'].append({'quantityId': named(f'H__{j}(t)'), 'equationId': out['jacket.energy']})
    sel['initialValues'][named(f'T__{j}(t)')] = j + '.temperature'
    for name, key in [(f'm_total__{j}(t)', f'matter.{j}.total-definition'), ('coolantMassFraction(t)', out['coolantMassFraction']),
                      (f'q__{COOLANT_OUT}__{i}(t)', out['return']), ('energy_average_0__' + COOLANT_OUT + '(t)', out['enthalpy.coolantOut']),
                      ('wallHeat(t)', out['wallLaw'])]:
        sel['reconstructions'].append({'quantityId': named(name), 'equationId': key})
    sel['parameters'][named(f'P__{j}(t)')] = j + '.pressure'
    sel['parameters'][named('coolantFlow')] = _datum(model, 'service.flow', data['coolantFlow'], 'kg/s')
    sel['parameters'][named('wallConductance')] = _datum(model, 'service.UA', data['UA'], 'W/K')


# --- jacketed reactor: the accepted Demo 0.2 reactor plus the jacket volume --------------------------

def jacketed_source(data=JACKETED):
    """The continuous reactor source with the jacket volume added (water is component 4)."""
    return add_jacket_volume(demo02_cstr.continuous_source(data), data, JACKET, 4)


def jacketed_template():
    template = demo02_cstr.template()
    template.update(id='demo-02-jacketed-cstr', templateVersion='1')
    template['ports'] = [p for p in template['ports'] if p['kind'] == 'material'] + [
        {'id': 'supply', 'volumeId': JACKET, 'direction': 'inlet', 'kind': 'material', 'boundary': {'type': 'stream', 'id': COOLANT_IN},
         'exteriorState': 'estadoExterior', 'variables': copy.deepcopy(MATERIAL)},
        {'id': 'return', 'volumeId': JACKET, 'direction': 'outlet', 'kind': 'material', 'boundary': {'type': 'stream', 'id': COOLANT_OUT},
         'donorPhase': 'liquido', 'variables': copy.deepcopy(MATERIAL)}]
    return template


def author_jacketed_reactor(data=None, method='bdf'):
    data = dict(JACKETED, **demo02_cstr.demo_data()) if data is None else data
    author, out = author_outlet(data, prepare=lambda model: demo02_cstr.prepare(model, data), source_factory=jacketed_source,
                                owner=REACTOR, vapour=False, heat_builder=reactor_wall_partition, reactive=True)
    out['reactor.heat'] = out['energy']
    out['energy'] = author.append('substitute', 'energy', sources=[out['energy']], relation=author.wall_law, symbol='wallHeat')
    for i in (1, 2, 3, 4):
        out[f'reactionAmount.{i}'] = author.append('isolate', sources=[f'reaction.{REACTOR}.amount.{i}'],
                                                  symbol=author.quantity(sp.Function(f'amount_{i}__{REACTOR}')(T)))
    demo02_cstr.record_premises(author, out)
    out.update(author_jacket(author, JACKET, 4, None, author.wall_law))
    # Total energy of the pair: the shared wall heat cancels by construction (one quantity, opposite signs).
    out['totalEnergy'] = author.append('combine', 'energy', sources=[out['reactor.heat'], out['jacket.heat']])
    author.model['template'] = jacketed_template()
    model = select_outlet(author, out, data, method, owner=REACTOR)
    replayed = build(model)
    quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    sel = model['motores']['derivedExecution']
    _jacket_selection(sel, model, quantities, out, data, JACKET, 4)
    sel['checks'].append({'equationId': f'matter.{JACKET}.total', 'scaleDataId': _datum(model, 'scale.jacketMass', 1, 'kg')})
    model.update(id='demo-0.2-jacketed-reactor', nombre='Jacketed continuous liquid reactor: reacting volume and cooling jacket')
    sel['sourceSignature'] = source_signature(model, replayed)
    return model, out


# --- independent references -----------------------------------------------------------------------

def water_enthalpy_functions(P):
    """Liquid water specific enthalpy from the package chemical potential (Gibbs-Helmholtz), per kg, and its inverse."""
    from core import mezclas
    from core.reactions.chemical_equilibrium import PackagePhase
    from scipy.optimize import brentq
    phase = PackagePhase(mezclas.Sistema(PACKAGE_ID, [WATER], solo_liquido=True), 'liquido', anchor='liquid')
    M = float(phase.sistema.M[0])
    one = np.array([1.0])

    def enthalpy(temperature, pressure=P):   # J/kg; the inlet is evaluated at its own declared pressure, as the engine does
        delta = 1e-3
        mu = phase.mu(temperature, pressure, one)[0]
        derivative = (phase.mu(temperature + delta, pressure, one)[0] - phase.mu(temperature - delta, pressure, one)[0]) / (2 * delta)
        return float(mu - temperature * derivative) / M

    low, high = phase.sistema.T_rango

    def temperature(h):
        return brentq(lambda t: enthalpy(t) - h, low + .002, high - .002, xtol=1e-10)
    return enthalpy, temperature, M


def reference_jacket_service(times, data=SERVICE):
    """DOP853 of the jacket alone against a prescribed process temperature, calling the package directly."""
    from scipy.integrate import solve_ivp
    enthalpy, temperature, _ = water_enthalpy_functions(data['Pj'])
    h_in = enthalpy(data['Tin'], data['Pin'])

    def rhs(t, y):
        m, H = y
        Tj = temperature(H / m)
        return [0.0, data['coolantFlow'] * (h_in - H / m) + data['UA'] * (data['Tprocess'] - Tj)]
    y0 = [data['mj0'], data['mj0'] * enthalpy(data['Tj0'])]
    sol = solve_ivp(rhs, (0, float(times[-1])), y0, method='DOP853', rtol=1e-11, atol=[1e-13, 1e-6], t_eval=times)
    return sol, np.array([temperature(H / m) for m, H in sol.y.T])


def steady_jacket_service(data=SERVICE):
    """Steady jacket temperature from the stream enthalpies and the wall law (brentq, no integration)."""
    from scipy.optimize import brentq
    enthalpy, _, _ = water_enthalpy_functions(data['Pj'])
    h_in = enthalpy(data['Tin'], data['Pin'])
    g = lambda Tj: data['coolantFlow'] * (h_in - enthalpy(Tj)) + data['UA'] * (data['Tprocess'] - Tj)
    return brentq(g, min(data['Tin'], data['Tprocess']) - 1, max(data['Tin'], data['Tprocess']) + 1, xtol=1e-11)


def reference_jacketed(times, data=None):
    """Independent LSODA integration of the reactor (Demo 0.2 route) coupled to the jacket.

    Reactor: amounts, H, outlet flow as in demo02_cstr.reference_train (count 1); the jacket
    heat UA (T_j - T) replaces the prescribed-jacket term. Jacket: mass and H, water enthalpy
    from the package chemical potential; T_j by inversion.
    """
    from scipy.integrate import solve_ivp
    data = dict(JACKETED, **demo02_cstr.demo_data()) if data is None else data
    _, masses, volumes, enthalpy, temperature, rate = demo02_cstr.reference_functions(data)
    hj, Tj_of, _ = water_enthalpy_functions(data['Pj'])
    h_in = hj(data['Tin'], data['Pin'])
    feed = np.asarray(data['zF']); feed_mass = float(feed @ masses)
    feed_molar = data['feed'] * feed / feed_mass
    feed_energy = data['feed'] * enthalpy(data['TF'], feed) / feed_mass
    nu = np.array([-1., -1., 1., 1.])

    def rhs(t, y):
        n, H, flow, mj, Hj = y[:4], y[4], y[5], y[6], y[7]
        mass = float(n @ masses); volume = float(n @ volumes); rho = mass / volume
        temp = temperature(H, n); Tj = Tj_of(Hj / mj)
        outlet = flow * n / mass; outlet_energy = flow * H / mass
        pressure = data['P'] + mass * data['g'] / data['area']
        loss = data['loss'] * flow * abs(flow) / (2 * rho * data['pipeArea'] ** 2)
        wall = data['UA'] * (temp - Tj)
        return [*(feed_molar - outlet + nu * rate(temp, n)), feed_energy - outlet_energy - wall,
                data['pipeArea'] / data['length'] * (pressure - data['Pout'] - loss),
                0.0, data['coolantFlow'] * (h_in - Hj / mj) + wall]
    initial = [*data['n0'], enthalpy(data['T0'], np.asarray(data['n0'])), data['F0'], data['mj0'], data['mj0'] * hj(data['Tj0'])]
    sol = solve_ivp(rhs, (0, float(times[-1])), initial, method='LSODA', t_eval=times, rtol=1e-10,
                    atol=[1e-11] * 4 + [1e-6, 1e-12, 1e-13, 1e-6])
    T = np.array([temperature(y[4], y[:4]) for y in sol.y.T]); Tj = np.array([Tj_of(y[7] / y[6]) for y in sol.y.T])
    return sol, T, Tj


def steady_jacketed(data=None, guess=None):
    """Stationary balances of both volumes solved together: amounts, T, outlet flow and T_j (hybr root)."""
    from scipy.optimize import root
    data = dict(JACKETED, **demo02_cstr.demo_data()) if data is None else data
    _, masses, volumes, enthalpy, temperature, rate = demo02_cstr.reference_functions(data)
    hj, _, _ = water_enthalpy_functions(data['Pj'])
    h_in = hj(data['Tin'], data['Pin'])
    feed = np.asarray(data['zF']); feed_mass = float(feed @ masses)
    feed_molar = data['feed'] * feed / feed_mass
    feed_energy = data['feed'] * enthalpy(data['TF'], feed) / feed_mass
    nu = np.array([-1., -1., 1., 1.])
    scale = np.array([1., 1., 1., 1., 300., 1e-3, 300.])

    def residual(x):
        n, temp, flow, Tj = x[:4] * scale[:4], x[4] * scale[4], x[5] * scale[5], x[6] * scale[6]
        mass = float(n @ masses); rho = mass / float(n @ volumes); H = enthalpy(temp, n)
        wall = data['UA'] * (temp - Tj)
        loss = data['loss'] * flow * abs(flow) / (2 * rho * data['pipeArea'] ** 2)
        return [*((feed_molar - flow * n / mass + nu * rate(temp, n)) / feed_molar.sum()),
                (feed_energy - flow * H / mass - wall) / data['UA'] / 10.,
                (data['P'] + mass * data['g'] / data['area'] - data['Pout'] - loss) / 1e3,
                (data['coolantFlow'] * (h_in - hj(Tj)) + wall) / (data['UA'] + data['coolantFlow'] * 4180.) / 10.]   # scaled by the jacket's thermal sensitivity
    if guess is None:
        row = demo02_cstr.sequential_steady_reference(1, dict(data, Tj=data['Tin']))[0]
        guess = [*row['amounts'], row['temperature'], row['flow'], data['Tin']]
    solution = root(residual, np.asarray(guess) / scale, method='hybr', options={'xtol': 1e-13})
    if not solution.success:
        raise RuntimeError(solution.message)
    v = solution.x * scale
    return {'amounts': v[:4], 'temperature': v[4], 'flow': v[5], 'jacketTemperature': v[6],
            'conversion': 1 - 2 * v[0] / sum(v[:4]), 'residual': float(np.max(np.abs(residual(solution.x))))}
