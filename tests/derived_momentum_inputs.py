"""Shared-law author: a heated package drum whose liquid outlet flow comes from the momentum balance.

Fresh test source, never a product-library example (demo-02-momentum). The drum
is the Demo 0.1 package-closure volume with a hydrostatic storage momentum
journal; the liquid leaves through a separate straight hydraulic path whose
momentum journal is reduced from Cauchy conservation. The path density, the
port pressures and the link to the phase donors are recorded relations; the
irreversible loss is the journal's Darcy-Weisbach/local-loss closure, specialised by recorded operations, with a
forward-flow regime.
"""
import copy
import math

import numpy as np
import sympy as sp

from m1_acceptance import SharedAuthor
from core.balances import momentum_derivation as momentum
from core.balances import material_derivation as material, energy_derivation as energy
from core.modelo.operation_journal import replay
from core.modelo import leer_modelo_comun
from core.modelo.equation_workbench import build
from core.mathematics.dimensions import catalog
from core.compilador.derived import source_signature
from derived_closure_inputs import DRUM, ETHANOL, OWNER, PACKAGE_ID, T, WATER, _datum, drum_source

PIPE = 'pipe'
OUTLET = dict(DRUM, length=5.0, pipeArea=7e-4, loss=8.0, floor=0.0, Pout=101325.0, F0=0.4, area=0.5, tf=400.0)

STORAGE_FLAGS = ('pressureStress', 'negligibleConvection', 'negligibleViscousStress', 'zeroLocalAccumulation',
                 'uniformGravity', 'referenceDensity', 'verticalGravity', 'pressureReference')
PATH_ACTIONS = ('pressure_stress', 'integrate', 'fixed_boundary', 'uniform_sections', 'impermeable_wall', 'ports',
                'constant_area', 'reference_density', 'uniform_gravity', 'hydraulic', 'darcy_weisbach')


def outlet_source(data=OUTLET, prepare=None, *, source_factory=drum_source, owner=OWNER):
    """The Demo 0.1 drum plus a hydraulic path for its liquid outlet.

    prepare(model) may add metadata (template record, phase extraction, boundary terms) before reading.
    """
    model = copy.deepcopy(source_factory(data))
    drum = model['volumenes'][0]
    drum['balances']['momento'] = True
    pipe = copy.deepcopy(drum)
    pipe.update(id=PIPE, componenteIds=list(drum['componenteIds']))
    pipe['balances'] = {'materia': False, 'energia': False, 'momento': True}
    pipe['termodinamica'] = {'tipo': 'supuesto', 'supuesto': 'fase_no_evaluada',
                             'motivo': 'The path carries the drawn liquid of the drum; its state is that donor phase (no separate closure)'}
    pipe['frontera'] = {'tipo': 'rigida', 'datoId': _datum(model,'path.volume',data['pipeArea']*data['length'],'m3','frontera')}
    model['volumenes'].append(pipe)
    liquid = next(s for s in model['corrientes'] if s['id'] == 'liquid')
    liquid['hasta'] = PIPE
    model['corrientes'].append({'id': 'discharge', 'desde': PIPE, 'hasta': None, 'componenteIds': list(drum['componenteIds']), 'mecanismo': 'convectivo',
                                'constante': False, 'materia': {'modo': 'por_componente', 'base': 'masica', 'caudalIds': {}}})
    mj = {'format': momentum.FORMAT, 'version': 1, 'volumes': {}}
    mj = momentum.edit_journal(mj, owner, {'kind': 'start'})
    for flag in STORAGE_FLAGS:
        mj = momentum.edit_journal(mj, owner, {'kind': 'set_assumption', 'name': flag, 'value': True})
    mj = momentum.edit_journal(mj, PIPE, {'kind': 'start'})
    for action in PATH_ACTIONS:
        mj = momentum.edit_journal(mj, PIPE, {'kind': action})
    mj = momentum.edit_journal(mj, PIPE, {'kind': 'bind_ports', 'inletStreamId': 'liquid', 'outletStreamId': 'discharge'})
    model['motores']['momentumDerivation'] = mj
    material_journal = model['motores']['materialDerivation']
    for action in ('start','no_reaction','fixed_boundary','integrate','total','impermeable_remainder','no_accumulation'):
        material_journal = material.edit_journal(material_journal,PIPE,{'kind':action})
    model['motores']['materialDerivation'] = material_journal
    pipe['supuestos']['materia'] = material.replay_volume(material_journal['volumes'][PIPE])[-1]
    energy_journal = model['motores']['energyDerivation']
    for action in ('start','pressure_stress','no_kinetic','no_viscous_work','no_body_work','no_volume_source',
                   'integrate','reynolds','total','enthalpy','adiabatic','no_accumulation'):
        energy_journal = energy.edit_journal(energy_journal,PIPE,{'kind':action})
    model['motores']['energyDerivation'] = energy_journal
    pipe['supuestos']['energia'] = replay(energy_journal['volumes'][PIPE],energy.fundamental,energy.normalize)[-1]
    if prepare is not None:
        prepare(model)
    return leer_modelo_comun(model)


def author_outlet(data=OUTLET, prepare=None, *, source_factory=drum_source, owner=OWNER,
                  vapour=True, heat_builder=None, reactive=False):
    """Feed, vapour vent and heat as in Demo 0.1; the liquid outlet flow is the path momentum state."""
    author = SharedAuthor(outlet_source(data, prepare, source_factory=source_factory, owner=owner))
    add, q = author.append, author.quantity
    o, p = owner, PIPE
    components = next(v['componenteIds'] for v in author.model['volumenes'] if v['id'] == owner)
    f = lambda name: sp.Function(name)(T)
    m = [f(f'm__{o}__{i}') for i in components]
    H = f('H__' + o)
    for name, unit in [('feedRate', 'kg/s'), ('withdrawalCoefficient', '1/s'), ('heatDuty', 'W'), ('crossSectionArea', 'm2'),
                       ('floorElevation', 'm'), ('outletPressure', 'Pa'), ('lossCoefficient', '1'),
                       ('darcyFriction', '1'), ('hydraulicDiameter', 'm')]:
        add('declare_symbol', name=name, unit=unit)
    add('declare_function', name='vapourMolarOutflow', unit='mol/s', dependencies=[q(T)])
    add('declare_function', name='liquidMassFlow', unit='kg/s', dependencies=[q(T)])
    out = {}
    ML, vL = q(f(f'phase_M__{o}__L')), q(f(f'phase_v__{o}__L'))
    if vapour:
        out['vapourOutflow'] = author.relation('vapourMolarOutflow', f"withdrawalCoefficient*{q(f(f'phase_amount__{o}__V'))}",
            'Vapour withdrawal proportional to the vapour holdup', kind='constitutive')
    donors = []
    for i, mass in zip(components, m):
        current = next(k for k in author.selected if k.startswith(f'matter.{o}.') and author.source.nodes[k].equation.lhs == sp.diff(mass, T))
        M = q(sp.Symbol(f'molar_mass_{i}__{o}', real=True))
        feed = author.relation(q(f(f'q__feed__{i}')), f"feedRate*{q(f(f'inlet_mass_fraction_{i}__feed'))}",
            'Prescribed feed rate with the package composition of the declared inlet', kind='constitutive')
        if vapour:
            vapour_row = author.relation(q(f(f'q__vapour__{i}')), f"vapourMolarOutflow*{q(f(f'phase_present__{o}__V'))}*{q(f(f'phase_x_{i}__{o}__V'))}*{M}",
                'Phase donor: the vapour withdrawal draws the vapour phase of this volume (zero when the vapour is absent)', kind='constitutive')
        fraction = f'liquidMassFraction_{i}'
        add('declare_function',name=fraction,unit='1',dependencies=[q(T)])
        mass_basis = author.relation(f'{fraction}*{ML}',f"{q(f(f'phase_x_{i}__{o}__L'))}*{M}",
            'Phase donor: the stream has the liquid phase composition; convert its component mole fraction to mass fraction using the phase mean molar mass',kind='constitutive')
        mass_basis = add('isolate',sources=[mass_basis],symbol=fraction)
        out[f'liquidMassFraction.{i}'] = mass_basis
        transport = author.relation(q(f(f'q__liquid__{i}')),f'liquidMassFlow*{fraction}',
            'Definition of component mass flow for a common convective stream velocity',kind='definition')
        liquid = author.substitute(transport,mass_basis,f(fraction))
        donors.append(liquid)
        out[f'feed.{i}'], out[f'liquid.{i}'] = feed, liquid
        if vapour:
            out[f'vapour.{i}'] = vapour_row
        for relation, stream in [(feed, 'feed'), *([(vapour_row, 'vapour')] if vapour else []), (liquid, 'liquid')]:
            current = author.substitute(current, relation, f(f'q__{stream}__{i}'))
        if reactive:
            for role,stem in [('generation','g'),('consumption','c')]:
                current = author.substitute(current,f'reaction.{o}.{role}.{i}',f(f'{stem}__{o}__{i}'))
        out[f'mass.{i}'] = current
    # Sum of the liquid donors: the mass fractions of the drawn phase add to one through M_L = sum x_i M_i.
    total = add('combine', sources=donors)
    total = author.substitute(total, f'thermodynamics.{o}.phase-molar-mass-L', f(f'phase_M__{o}__L'))
    total = add('factor', sources=[total])
    out['donorTotal'] = total
    split = add('isolate', sources=[total], symbol=q(f('q__liquid__1')))
    rate = add('differentiate', sources=[total], symbol=q(T))
    rate = add('isolate', sources=[rate], symbol=q(sp.diff(f('q__liquid__1'), T)))
    current = next(k for k in author.selected if k.startswith(f'energy.{o}.') and author.source.nodes[k].equation.lhs == sp.diff(H, T))
    for stream in (('feed', 'vapour', 'liquid') if vapour else ('feed','liquid')):
        for i in components:
            current = author.substitute(current, out[f'{stream}.{i}'], f(f'q__{stream}__{i}'), 'energy')
    for stream, right in [('feed', q(f('inlet_specific_enthalpy__feed'))),
                          *([('vapour', f"{q(f(f'phase_h__{o}__V'))}/{q(f(f'phase_M__{o}__V'))}")] if vapour else []),
                          ('liquid', f"{q(f(f'phase_h__{o}__L'))}/{ML}")]:
        average = f('energy_average_0__' + stream)
        if stream == 'liquid':
            add('declare_function','energy',name='liquidMolarEnthalpy',unit='J/mol',dependencies=[q(T)])
            donor = author.relation('liquidMolarEnthalpy',q(f(f'phase_h__{o}__L')),
                'The outgoing material draws the donor liquid phase at its thermodynamic state','energy','constitutive')
            basis = author.relation(f'{q(average)}*{ML}','liquidMolarEnthalpy',
                'Definition of molar enthalpy from mass-specific enthalpy and the mean molar mass','energy','definition')
            basis = author.substitute(basis,donor,f('liquidMolarEnthalpy'),'energy')
            relation = add('isolate','energy',sources=[basis],symbol=q(average))
        else:
            relation = author.relation(q(average), right, 'Stream specific enthalpy from the package (donor phase or declared inlet)', 'energy', 'constitutive')
        out['enthalpy.'+stream] = relation
        current = author.substitute(current, relation, average, 'energy')
    heat = (heat_builder(author, o) if heat_builder else
            author.relation(q(f('energy_heat_rate__' + o)), 'heatDuty', 'Prescribed heat duty', 'energy'))
    out['energy'] = author.substitute(current, heat, f('energy_heat_rate__' + o), 'energy')
    # Storage: hydrostatic pressure of the liquid column at the floor port, referenced to the vapour-space pressure.
    pressure = f'momentum.{o}.storage.pressure'
    z, zr, pr, rho = sp.Symbol('z__' + o, real=True), f('z_r__' + o), f('p_r__' + o), sp.Symbol('rho__' + o, real=True)
    for symbol, right, reason, kind in [
            (z, 'floorElevation', 'The outlet port is at the lowest point of the liquid region', 'definition'),
            (zr, f"floorElevation+{q(f('liquid_volume__' + o))}/crossSectionArea", 'The pressure reference is the liquid free surface of a vertical prismatic liquid region', 'definition'),
            (pr, q(f('P__' + o)), 'The uniform vapour-space pressure of the volume acts on the free surface', 'constitutive'),
            (rho, f'{ML}/{vL}', 'The hydrostatic column is the liquid phase of the package closure', 'constitutive')]:
        relation = author.relation(q(symbol), right, reason, 'momentum', kind)
        if symbol == zr:
            out['surface'] = relation
        pressure = author.substitute(pressure, relation, symbol, 'momentum')
    out['floorPressure'] = pressure
    # RM-5: the drawn liquid must be present (V_L = n_L v_L > 0); a dry-out is a located stop, never an undefined composition.
    add('declare_domain', 'momentum', sources=[pressure], symbol=q(f('liquid_volume__' + o)), domain='positive',
        reason='The drawn liquid phase is present: positive liquid volume')
    field = author.result.graph.nodes[pressure].equation.lhs
    # Path: (L/A) dF/dt = p1 - p2 + rho g (z1 - z2) + drive - loss.
    current = f'momentum.{p}.path.pressure-form'
    current = author.substitute(current, rate, sp.diff(f('q__liquid__1'), T), 'momentum')
    port = f('p1__' + p)
    coupling = author.relation(q(port), q(field), 'Continuous pressure at the shared material port', 'momentum')
    current = author.substitute(current, coupling, port, 'momentum')
    current = author.substitute(current, pressure, field, 'momentum')
    rhop = sp.Symbol('rho__' + p, real=True)
    A, L = sp.Symbol('A__' + p, real=True), sp.Symbol('L__' + p, real=True)
    z1, z2 = sp.Symbol('z1__' + p, real=True), sp.Symbol('z2__' + p, real=True)
    for symbol, right, reason, kind in [
            (f('p2__' + p), 'outletPressure', 'Prescribed exterior pressure at the discharge port', 'constitutive'),
            (f('drive__' + p), '0', 'No applied pressure drive or shaft work on the path', 'constitutive'),
            (f('loss__' + p), f"(darcyFriction*{q(L)}/hydraulicDiameter+lossCoefficient)*liquidMassFlow*(liquidMassFlow^2)^(1/2)/(2*{q(rhop)}*{q(A)}^2)",
             'Darcy-Weisbach and local-loss closure recorded in the path momentum journal: signed irreversible pressure loss', 'constitutive'),
            (sp.Symbol('darcyFriction', real=True), '0', 'No distributed wall friction: the irreversible loss is lumped in the local-loss coefficient', 'constitutive'),
            (rhop, f'{ML}/{vL}', 'The path carries the drawn liquid phase: its reference density is the donor liquid density. '
             'Quasi-constant density: the path mass storage A L |d rho/dt| / F is neglected (monitored below 1e-3)', 'constitutive'),
            (z2, q(z1), 'Horizontal discharge path: equal endpoint elevations', 'definition')]:
        target = q(symbol) if not isinstance(symbol, sp.Symbol) or str(symbol) not in ('darcyFriction',) else 'darcyFriction'
        relation = author.relation(target, right, reason, 'momentum', kind)
        if symbol == f('loss__' + p):
            out['loss'] = relation
        current = author.substitute(current, relation, symbol, 'momentum')
    out['flow'] = add('isolate', 'momentum', sources=[current], symbol=q(sp.diff(f('liquidMassFlow'), T)))
    add('declare_domain', 'momentum', sources=[out['loss']], symbol='liquidMassFlow', domain='positive',
        reason='Forward-flow regime of the loss closure and of the donor orientation')
    for name in ('crossSectionArea', 'lossCoefficient'):
        add('declare_domain', 'momentum', sources=[out['flow']], symbol=name, domain='positive', reason='Positive geometry and loss coefficient')
    for symbol in (A, L):
        add('declare_domain', 'momentum', sources=[out['flow']], symbol=q(symbol), domain='positive', reason='Positive path geometry')
    # The same component laws are reduced with explicit negligible storage.
    # Internal friction converts mechanical energy into thermal energy; it is
    # not an additional boundary heat sink. The first-law reduction retains
    # pressure flow work in enthalpy and neglects kinetic/potential storage.
    out['pathRates'] = []
    for i in components:
        derivative = sp.diff(f(f'm__{p}__{i}'),T)
        balance = next(k for k in author.selected if k.startswith(f'matter.{p}.{i}.')
            and author.source.nodes[k].equation.lhs==derivative and author.source.nodes[k].equation.rhs!=0)
        zero = f'matter.{p}.{i}.stationary'
        out['pathRates'].append((derivative,zero))
        row = author.substitute(balance,zero,derivative)
        row = add('isolate',sources=[row],symbol=q(f(f'q__discharge__{i}')))
        out[f'discharge.{i}'] = author.substitute(row,out[f'liquid.{i}'],f(f'q__liquid__{i}'))
    derivative = sp.diff(f('U__'+p),T)
    balance = next(k for k in author.selected if k.startswith('energy.'+p+'.')
        and author.source.nodes[k].equation.lhs==derivative and author.source.nodes[k].equation.rhs!=0)
    zero = 'energy.'+p+'.zero-total-rate'
    out['pathRates'].append((derivative,zero))
    row = author.substitute(balance,zero,derivative,'energy')
    for i in components:
        for stream in ('liquid','discharge'):
            row = author.substitute(row,out[f'{stream}.{i}'],f(f'q__{stream}__{i}'),'energy')
    row = author.substitute(row,out['enthalpy.liquid'],f('energy_average_0__liquid'),'energy')
    out['enthalpy.discharge'] = add('isolate','energy',sources=[row],symbol=q(f('energy_average_0__discharge')))
    return author, out


def select_outlet(author, out, data=OUTLET, method='rk45', *, owner=OWNER):
    model, _, _ = author.finish({})
    model = copy.deepcopy(model)   # each selection owns its document
    replayed = build(model)
    quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
    named = lambda name: next(k for k, v in quantities.items() if str(v) == name)
    o, p = owner, PIPE
    components = next(v['componenteIds'] for v in model['volumenes'] if v['id'] == owner)
    sel = {'format': 'rage.derived-execution', 'version': 1, 'sourceSignature': source_signature(model, replayed),
           'timeId': named('t'), 'states': [], 'parameters': {}, 'initialValues': {}, 'initialEquations': [],
           'reconstructions': [], 'checks': []}
    for i in components:
        key = out[f'mass.{i}']
        sel['states'].append({'quantityId': named(f'm__{o}__{i}(t)'), 'equationId': key})
        sel['initialValues'][named(f'm__{o}__{i}(t)')] = o + ('.mass' if i == 1 else '.mass'+str(i))
        sel['reconstructions'].append({'quantityId': named(f'n_{i}__{o}(t)'), 'equationId': f'thermodynamics.{o}.component-amount-{i}'})
    sel['states'].append({'quantityId': named(f'H__{o}(t)'), 'equationId': out['energy']})
    sel['states'].append({'quantityId': named('liquidMassFlow(t)'), 'equationId': out['flow']})
    sel['initialValues'][named(f'T__{o}(t)')] = o + '.temperature'
    sel['initialValues'][named('liquidMassFlow(t)')] = _datum(model, 'solve.F0', data['F0'], 'kg/s')
    sel['reconstructions'].append({'quantityId': named(f'm_total__{o}(t)'), 'equationId': f'matter.{o}.total-definition'})
    floor = replayed.graph.nodes[out['floorPressure']].equation.lhs
    sel['reconstructions'].append({'quantityId': next(k for k, v in quantities.items() if v == floor), 'equationId': out['floorPressure']})
    for quantity,row in [*out.get('pathRates',[]),
            *[(sp.Function(f'liquidMassFraction_{i}')(T),out[f'liquidMassFraction.{i}']) for i in components],
            *[(sp.Function(f'q__discharge__{i}')(T),out[f'discharge.{i}']) for i in components],
            *[(sp.Function(f'amount_{i}__{o}')(T),out[f'reactionAmount.{i}']) for i in components if f'reactionAmount.{i}' in out],
            (sp.Function('energy_average_0__liquid')(T),out['enthalpy.liquid']),
            (sp.Function('energy_average_0__discharge')(T),out['enthalpy.discharge'])]:
        q_id = next(k for k,v in quantities.items() if v==quantity)
        sel['reconstructions'].append({'quantityId':q_id,'equationId':row})
    for name, key, value, unit in [(f'P__{o}(t)', o + '.pressure', None, None), ('feedRate', 'solve.F', data['feed'], 'kg/s'),
                                   ('withdrawalCoefficient', 'solve.kV', data['vent'], '1/s'), ('heatDuty', 'solve.Q', data['Q'], 'W'),
                                   ('crossSectionArea', 'solve.A', data['area'], 'm2'), ('floorElevation', 'solve.z0', data['floor'], 'm'),
                                   ('outletPressure', 'solve.Pout', data['Pout'], 'Pa'), ('lossCoefficient', 'solve.K', data['loss'], '1'),
                                   ('hydraulicDiameter', 'solve.Dh', math.sqrt(4 * data['pipeArea'] / math.pi), 'm'),
                                   (f'A__{p}', 'solve.pipeArea', data['pipeArea'], 'm2'), (f'L__{p}', 'solve.length', data['length'], 'm'),
                                   (f'g__{o}', 'solve.g', data['g'], 'm/s2'), (f'g__{p}', 'solve.g', None, None)]:
        sel['parameters'][named(name)] = key if value is None else _datum(model, key, value, unit)
    if model['motores'].get('kineticReactions'):
        from core.balances.reaction_equations import declarations
        _, _, bindings, _ = declarations(model, o)
        for quantity, datum in bindings.items():
            sel['parameters'][next(k for k,v in quantities.items() if v == quantity)] = datum
    sel['checks'] = [{'equationId': f'matter.{o}.total', 'scaleDataId': _datum(model, 'scale.mass', 100, 'kg')}]
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': _datum(model, 'solve.tf', data['tf'], 's', 'estudio'),
                        'metodoSolicitado': method, 'muestras': 81, 'rtol': 1e-9, 'atol': {'cantidad': 1e-9, 'energia': 1e-3}}
    model['motores']['derivedExecution'] = sel
    return model


def reference_outlet(times, data=OUTLET):
    """Independent DOP853 integration calling core.mezclas directly (no bridge, no graph)."""
    from scipy.integrate import solve_ivp
    from core import mezclas
    s = mezclas.Sistema(PACKAGE_ID, [ETHANOL, WATER])
    M = np.asarray(s.M, dtype=float)
    zF = np.asarray(data['zF'])
    hF_mass = s.equilibrio_TP(data['TF'], data['PF'], zF).H / float(zF @ M)
    wF = zF * M / float(zF @ M)

    def state(y):
        return s.equilibrio_PH(data['P'], y[2], np.asarray(y[:2]) / M)

    def rhs(t, y):
        e = state(y); F = y[3]
        q = np.zeros(2); Hs = 0.0
        liquid = next(ph for ph in e.fases if ph.tipo != 'vapor')
        for phase in e.fases:
            if not phase.n > mezclas.N_AUSENTE * float(np.sum(y[:2] / M)):
                continue
            x = np.asarray(phase.x)
            if phase.tipo == 'vapor':
                Fv = data['vent'] * phase.n
                q += Fv * x * M; Hs += Fv * phase.h
            else:
                w = x * M / phase.M
                q += F * w; Hs += F * phase.h / phase.M
        rho = liquid.M / liquid.v
        level = liquid.n * liquid.v / data['area']
        p1 = data['P'] + rho * data['g'] * level
        loss = data['loss'] * F**2 / (2 * rho * data['pipeArea']**2)
        dF = data['pipeArea'] / data['length'] * (p1 - data['Pout'] - loss)
        return [*(data['feed'] * wF - q), data['feed'] * hF_mass - Hs + data['Q'], dF]

    n0 = np.asarray(data['m0']) / M
    H0 = s.equilibrio_TP(data['T0'], data['P'], n0).H
    sol = solve_ivp(rhs, (0, times[-1]), [*data['m0'], H0, data['F0']], method='DOP853', rtol=1e-10,
                    atol=[1e-10, 1e-10, 1e-4, 1e-10], t_eval=times)
    return sol, np.array([state(y).T for y in sol.y.T])
