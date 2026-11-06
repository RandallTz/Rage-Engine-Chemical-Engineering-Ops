"""Liquid equilibrium-reaction author and independent references (B3, claude-b, 6 November 2026).

The Model is authored by the shared operations in equilibrium_reaction_inputs.author:
mu_i = mu_i*(T,P) + R T log(x_i gamma_i) is a recorded thermodynamic constitutive
relation of the declared package liquid.

The references do not call core.mezclas, core.unifac or core.reactions:
- ln gamma_i: thermo's UNIFAC implementation (thermo.unifac.UNIFAC, its own DDBST
  group assignments and interaction tables; version 0 original, 1 Dortmund).
- mu_i*(T,P): a 50-digit mpmath evaluation of the pure-liquid Gibbs energy written
  here from the published coefficient tuples (Poling ideal-gas cp, Wagner Psat,
  liquid molar volume, DIPPR-100 liquid cp of a liquid-only species) and the
  tabulated liquid formation data of `chemicals` (Hfl, S0l), with the liquid
  formation anchor mu_i*(T0, P0) = Hfl_i - T0 S0l_i and -dmu_i*/dT(T0, P0) = S0l_i.
"""
import mpmath as mp
from chemicals import reaction as rx
from chemicals.identifiers import search_chemical
from thermo import unifac as tu
from core import mezclas_datos as data   # coefficient tuples only (data, not code)
from equilibrium_reaction_inputs import author

ACID, ETHANOL, ACETATE, WATER, ACETONE = '64-19-7', '64-17-5', '141-78-6', '7732-18-5', '67-64-1'
SPECIES = [ACID, ETHANOL, ACETATE, WATER]
NU = [-1, -1, 1, 1]
MOLAR_MASSES = (.06005, .04607, .08811, .01802, .05808)
TEMPERATURE, PRESSURE = 350, 101325
R, T0, P0 = mp.mpf('8.314462618'), mp.mpf('298.15'), mp.mpf(100000)


def esterification(package='unifac-original', form='activity', inert=False, extent_box=(.625, .66), seed=.64):
    """Acetic acid + ethanol = ethyl acetate + water in one liquid at 350 K, 1 atm.

    Liquid formation anchor: acetic acid is a liquid-only species of the catalog."""
    species = SPECIES + ([ACETONE] if inert else [])
    nu = NU + ([0] if inert else [])
    reference = (1, 1, 0, 0) + ((2,) if inert else ())
    return author(owner='liquid', species=species, nu=nu, molar_masses=MOLAR_MASSES[:len(species)],
                  reference=reference, temperature=TEMPERATURE, pressure=PRESSURE, extent_box=extent_box,
                  seed=seed, state_width=1e-3, step_tolerance=1e-13,
                  liquid={'package': package, 'anchor': 'liquid', 'form': form})


# --- independent pure-liquid standard potential ----------------------------------------------------------
def _ideal_gas_g(e, T):
    """g_ig(T, P0) - g_ig(T0, P0) = h - T s with Poling cp/R = sum a_k T^k (zero at T0, P0)."""
    a = [mp.mpf(repr(v)) for v in e.cp]
    h = sum(a[k] * (T**(k + 1) - T0**(k + 1)) / (k + 1) for k in range(len(a)))
    s = a[0] * mp.log(T / T0) + sum(a[k] * (T**k - T0**k) / k for k in range(1, len(a)))
    return R * h - T * R * s


def _ln_psat(e, T):
    A, B, C, D, Tc, Pc = (mp.mpf(repr(v)) for v in e.psat)
    tau = 1 - T / Tc
    third, fourth = (mp.mpf('2.5'), 5) if e.psat_forma == 'WagnerPoling' else (3, 6)
    return mp.log(Pc) + Tc / T * (A * tau + B * tau**mp.mpf('1.5') + C * tau**third + D * tau**fourth)


def _liquid_g(e, T, P):
    """Pure-liquid Gibbs energy through the vapour: ideal gas + R T ln(Psat/P0) + v_L (P - Psat)."""
    vL = mp.mpf(repr(e.vL))
    return _ideal_gas_g(e, T) + R * T * (_ln_psat(e, T) - mp.log(P0)) + vL * (P - mp.e**_ln_psat(e, T))


def pure_liquid_potential(cas, T, P):
    """mu_i*(T, P) [J/mol] with the liquid formation anchor (50 digits)."""
    mp.mp.dps = 50
    e = data.especie(cas)
    T, P = mp.mpf(repr(float(T))), mp.mpf(repr(float(P)))
    Hl, Sl = mp.mpf(repr(rx.Hfl(cas))), mp.mpf(repr(rx.S0l(cas)))
    vL = mp.mpf(repr(e.vL))
    if e.cp_L is not None:
        # Tabulated liquid cp: h = Hl + int cp_L dT + v_L (P - P0), s = Sl + int cp_L/T dT.
        c = [mp.mpf(repr(v)) for v in e.cp_L]
        H = sum(c[k] * (T**(k + 1) - T0**(k + 1)) / (k + 1) for k in range(len(c)))
        S = c[0] * mp.log(T / T0) + sum(c[k] * (T**k - T0**k) / k for k in range(1, len(c)))
        return Hl + H + vL * (P - P0) - T * (Sl + S)
    # Psat route shifted so that h(T0, P0) = Hl and s(T0, P0) = Sl.
    dg = mp.diff(lambda t: _liquid_g(e, t, P0), T0)
    h0, s0 = _liquid_g(e, T0, P0) - T0 * dg, -dg
    return _liquid_g(e, T, P) + (Hl - h0) - T * (Sl - s0)


def ln_k(species, nu, T, P):
    return -mp.fsum(v * pure_liquid_potential(c, T, P) for c, v in zip(species, nu) if v) / (R * mp.mpf(T))


# --- independent activity coefficients -------------------------------------------------------------------
def ln_gamma(species, x, T, variant):
    """thermo's UNIFAC: version 0 (original, UFSG/UFIP) or 1 (Dortmund, DOUFSG/DOUFIP2016)."""
    tu.load_group_assignments_DDBST()
    table = tu.DDBST_UNIFAC_assignments if variant == 'original' else tu.DDBST_MODIFIED_UNIFAC_assignments
    groups = [table[search_chemical(c).InChI_key] for c in species]
    options = ({'version': 0, 'subgroups': tu.UFSG, 'interaction_data': tu.UFIP} if variant == 'original' else
               {'version': 1, 'subgroups': tu.DOUFSG, 'interaction_data': tu.DOUFIP2016})
    model = tu.UNIFAC.from_subgroups(float(T), [float(v) for v in x], groups, **options)
    return [mp.mpf(repr(v)) for v in model.lngammas()]


def reference_extent(species, nu, n0, T, P, variant, guess):
    """Root of sum_i nu_i ln(x_i gamma_i) = ln K in the single extent (variant None: ideal solution)."""
    lnK = ln_k(species, nu, T, P)

    def residual(xi):
        n = [mp.mpf(a) + v * xi for a, v in zip(n0, nu)]
        x = [v / mp.fsum(n) for v in n]
        lg = ln_gamma(species, x, T, variant) if variant else [0] * len(x)
        return mp.fsum(v * (mp.log(xv) + g) for v, xv, g in zip(nu, x, lg) if v) - lnK

    # thermo's ln gamma is binary64, so the attainable residual is ~1e-15, not 50 digits.
    root = mp.findroot(residual, (mp.mpf(guess) - mp.mpf('0.01'), mp.mpf(guess) + mp.mpf('0.01')), solver='secant',
                       tol=mp.mpf('1e-28'), verify=False)
    assert abs(residual(root)) < 1e-13
    return root


# --- B3 part 2: thermally coupled equilibrium (claude-b, 6 November 2026) --------------------------------
# The region's caloric closure is the reaction package (select_closure with the formation reference of the
# declaration anchor); the energy balance is the recorded enthalpy balance of a closed, prescribed-pressure,
# adiabatic region with no volumetric source. T is the closure output T(H, P, n(xi)).
import sympy as _sp
from m1_acceptance import SharedAuthor as _SharedAuthor, thermal_source as _thermal_source
from core.balances import material_derivation as _material, energy_derivation as _energy
from core.termodinamica import derivation as _thermo
from core.modelo import leer_modelo_comun as _read
from core.modelo.operation_journal import replay as _replay
from core.compilador.derived_graph import source_signature as _signature
from derived_closure_inputs import _datum

VAPOUR = ['64-17-5', '108-88-3', '71-36-3', '7732-18-5']   # ethanol, toluene (inert), 1-butanol, water
VAPOUR_NU = [-2, 0, 1, 1]
VAPOUR_REFERENCE = (2, 6, 0, 0)


def thermal_source(owner, species, package, phase, anchor, pressure, *, rigid=False, volume_source=False,
                   formation=True, closure_package=None):
    """Closed region whose recorded closure is the package; controls: rigid (UV), a volumetric energy source
    left in the balance, no formation reference, another closure package."""
    model = _thermal_source((owner,))
    v = model['volumenes'][0]
    model['id'] = 'thermal-equilibrium-reaction'
    model['componentes'] = [{'id': i, 'nombre': c, 'simbolo': 'C' + str(i), 'identidadQuimica': {'cas': c}}
                            for i, c in enumerate(species, 1)]
    v['componenteIds'] = list(range(1, len(species) + 1))
    v['inicial']['cantidades']['datoIds'] = {str(i): _datum(model, 'mass' + str(i), 1, 'kg', 'inicial')
                                             for i in range(1, len(species) + 1)}
    model['termodinamica'] = {'paquetes': [{'id': 'reactionPackage', 'modelo': {'id': package, 'version': '1'}},
                                           {'id': 'otherPackage', 'modelo': {'id': 'unifac-dortmund', 'version': '1'}}]}
    kind = 'liquido' if phase == 'liquid' else 'vapor'
    v['termodinamica'] = {'tipo': 'equilibrio', 'paqueteId': closure_package or 'reactionPackage',
                          'politica': {'cantidad': 'monofasico', 'cambioInterno': 'prohibido',
                                       'evaluacion': 'equilibrio_estable', 'tiposPermitidos': [kind]}}
    journal = {'format': 'rage.material-derivation', 'version': 1, 'volumes': {}}
    for action in ('start',) + (('fixed_boundary',) if rigid else ()) + (
            'integrate', 'total', 'impermeable_remainder', 'uniform_generation', 'uniform_consumption'):
        journal = _material.edit_journal(journal, owner, {'kind': action})
    model['motores']['materialDerivation'] = journal
    v['supuestos']['materia'] = _material.replay_volume(journal['volumes'][owner])[-1]
    actions = ('start', 'pressure_stress', 'no_kinetic', 'no_viscous_work', 'no_body_work') + \
        (() if volume_source else ('no_volume_source',)) + ('integrate', 'reynolds', 'total') + \
        (('uniform_state', 'uniform_pressure') if rigid else ('enthalpy', 'uniform_state', 'uniform_pressure', 'prescribed_pressure'))
    ej = {'format': 'rage.energy-derivation', 'version': 1, 'volumes': {}}
    for action in actions:
        ej = _energy.edit_journal(ej, owner, {'kind': action})
    model['motores']['energyDerivation'] = ej
    tj = {'format': _thermo.FORMAT, 'version': 1, 'volumes': {}}
    tj = _thermo.edit_journal(tj, owner, {'kind': 'start'})
    tj = _thermo.edit_journal(tj, owner, {'kind': 'select_closure'}, _thermo.expected_closure(model, v))
    from core.catalogo import REGISTRO_SOLO_LIQUIDO
    if any(c in REGISTRO_SOLO_LIQUIDO for c in species):
        tj = _thermo.edit_journal(tj, owner, {'kind': 'liquid_only'})
    if formation:
        tj = _thermo.edit_journal(tj, owner, {'kind': 'liquid_formation_reference' if anchor == 'liquid' else 'gas_formation_reference'})
    model['motores']['thermodynamicDerivation'] = tj
    es = _replay(ej['volumes'][owner], _energy.fundamental, _energy.normalize)[-1]
    ts = _replay(tj['volumes'][owner], _thermo.fundamental, _thermo.normalize)[-1]
    v['supuestos']['energia'] = {**es, **{k: val for k, val in ts.items() if k != 'closure'}}
    _datum(model, owner + '.pressure', pressure, 'Pa', 'frontera')
    if rigid:
        _datum(model, owner + '.rigidVolume', 1e-3, 'm3', 'frontera')
        v['frontera'] = {'tipo': 'rigida', 'datoId': owner + '.rigidVolume'}
    else:
        v['frontera'] = {'tipo': 'presion_prescrita', 'presionId': owner + '.pressure'}
    return _read(model)


def thermal_author(owner, species, nu, reference, package, phase, anchor, pressure, energy, temperature_box,
                   extent_box, seed, *, energy_width=1., state_width=1e-3, step_tolerance=1e-12, record_box=True,
                   temperature_datum=None, **source):
    """Model -> Transform -> Solve of the coupled region through the shared operations only.

    energy: the initial enthalpy inventory H(0) [J] (the unreacted feed's formation-referenced enthalpy,
    computed by the caller). temperature_box: the recorded validity interval of the closure temperature."""
    count = len(species)
    k = max(i for i, c in enumerate(nu) if c != 0)
    assert reference[k] == 0
    others = [j for j in range(count) if j != k]
    model = thermal_source(owner, species, package, phase, anchor, pressure, **source)
    rigid = source.get('rigid', False)
    a = _SharedAuthor(model); q = a.quantity; t = _sp.Symbol('t', real=True)
    f = lambda name: _sp.Function(name)(t)

    def declare(name, unit):
        a.append('declare_function', name=name, unit=unit, dependencies=[q(t)])
        return f(name)
    b = [declare('conserved' + str(i), 'mol') for i in range(count - 1)]
    xi = declare('extent', 'mol'); rate = declare('reactionRate', 'mol/s')
    for name, unit in [('zeroReference', 'mol'), ('virtualExtent', 'mol'), ('gasConstant', 'J/(mol*K)')]:
        a.append('declare_symbol', name=name, unit=unit)
    masses = [f('m__' + owner + '__' + str(i)) for i in range(1, count + 1)]
    amounts = [f('n_' + str(i) + '__' + owner) for i in range(1, count + 1)]
    V, T, P, H = (f(name + '__' + owner) for name in ('V', 'T', 'P', 'U' if rigid else 'H'))
    balances = []
    for i, (mass, n, coefficient) in enumerate(zip(masses, amounts, nu), 1):
        M = _sp.Symbol('molar_mass_' + str(i) + '__' + owner, real=True)   # the package molar mass
        relation = a.relation(q(mass), q(M) + '*' + q(n), 'Define mass from molar amount and the package molar mass', kind='definition')
        current = next(key for key in a.selected if key.startswith('matter.' + owner + '.') and a.source.nodes[key].equation.lhs == _sp.diff(mass, t))
        current = a.substitute(current, relation, mass)
        for stem, c in [('g', max(coefficient, 0)), ('c', max(-coefficient, 0))]:
            density = f(stem + '__' + owner + '__' + str(i))
            definition = a.relation(q(density), f'{c}*{q(M)}*{q(rate)}/{q(V)}', 'Uniform stoichiometric source density in a closed region', kind='definition')
            current = a.substitute(current, definition, density)
        balances.append(a.append('divide', sources=[current], right=q(M)))
    states, definitions, recon = [], [], []
    for j, left in enumerate(others):
        c = _sp.Rational(-nu[left], nu[k])
        if c == 0:
            relation = a.relation(q(b[j]), q(amounts[left]), 'Conserved coordinate of a species absent from every reaction', kind='definition')
            combined = balances[left]
        else:
            sign = '+' if c > 0 else '-'
            term = q(amounts[k]) if abs(c) == 1 else str(abs(c)) + '*' + q(amounts[k])
            relation = a.relation(q(b[j]), q(amounts[left]) + sign + term, 'Conserved left-nullspace coordinate of stoichiometry', kind='definition')
            rhs = balances[k] if c == 1 else a.append('multiply', sources=[balances[k]], right=str(c))
            combined = a.append('combine', sources=[balances[left], rhs])
        definitions.append(relation)
        differentiated = a.append('differentiate', sources=[relation], symbol=q(t))
        states.append({'quantityId': q(b[j]), 'equationId': a.substitute(differentiated, combined, _sp.diff(amounts[left], t))})
    ext = a.relation(q(amounts[k]), q(xi) if nu[k] == 1 else str(nu[k]) + '*' + q(xi), 'Extent coordinate of the species with zero reference amount', kind='definition')
    a.append('differentiate', sources=[ext], symbol=q(t))
    a.relation(q(rate), q(_sp.diff(xi, t)), 'Define integrated reaction rate as the time derivative of extent', kind='definition')
    recon.append({'quantityId': q(amounts[k]), 'equationId': ext})
    for left, relation in zip(others, definitions):
        replaced = a.substitute(relation, ext, amounts[k]) if nu[left] != 0 else relation
        recon.append({'quantityId': q(amounts[left]), 'equationId': a.append('isolate', sources=[replaced], symbol=q(amounts[left]))})
    # Energy: the recorded enthalpy (or rigid internal-energy) balance with an adiabatic boundary.
    heat = f('energy_heat_rate__' + owner)
    balance = next(key for key in a.selected if key.startswith('energy.' + owner + '.') and a.source.nodes[key].equation.lhs == _sp.diff(H, t))
    adiabatic = a.relation(q(heat), '0', 'Adiabatic boundary: no heat crosses the region boundary', 'energy')
    states.append({'quantityId': q(H), 'equationId': a.substitute(balance, adiabatic, heat, 'energy')})
    if record_box:
        a.append('declare_domain', family='thermodynamics', sources=['thermodynamics.' + owner + '.package-enthalpy'], symbol=q(T),
                 domain='interval', lower=repr(float(temperature_box[0])), upper=repr(float(temperature_box[1])), lowerOpen=False,
                 upperOpen=False, endpointUnit='K', reason='Declared validity interval of the closure temperature')
    # Stationary Gibbs energy at fixed T and P (virtual variation), as in B3 part 1.
    current = 'thermodynamics.' + owner + '.dG'
    for name, reason in [('T', 'Isothermal virtual composition variation'), ('P', 'Isobaric virtual composition variation'),
                         ('G', 'Stationary Gibbs energy at interior chemical equilibrium')]:
        current = a.append('state_variation', family='thermodynamics', sources=[current], symbol=q(f(name + '__' + owner)), right='0', reason=reason)
    for n, coefficient in zip(amounts, nu):
        current = a.append('state_variation', family='thermodynamics', sources=[current], symbol=q(n), right=str(coefficient) + '*virtualExtent',
                           reason='Stoichiometric virtual composition direction; formation reference is included in chemical potentials')
    a.append('declare_domain', family='thermodynamics', sources=[current], symbol='virtualExtent', domain='nonzero',
             reason='Nonzero virtual stoichiometric displacement for the stationary Gibbs variation')
    current = a.append('divide', family='thermodynamics', sources=[current], right='virtualExtent*gasConstant*' + q(T))
    total = '(' + '+'.join(q(n) for n in amounts) + ')'
    if phase != 'liquid':
        a.append('declare_symbol', name='standardPressure', unit='Pa')
    for i, n in enumerate(amounts, 1):
        if nu[i - 1] == 0:
            continue
        mu = f('mu_' + str(i) + '__' + owner)
        if phase == 'liquid':
            standard = declare('pureLiquidPotential' + str(i), 'J/mol')
            gamma = declare('activityCoefficient' + str(i), '1')
            right = q(standard) + '+gasConstant*' + q(T) + '*log(' + q(n) + '*' + q(gamma) + '/' + total + ')'
            reason = 'Liquid mixture chemical potential of the declared package liquid (pure-liquid standard potential, activity coefficient)'
        else:
            standard = declare('standardPotential' + str(i), 'J/mol')
            right = q(standard) + '+gasConstant*' + q(T) + '*log(' + q(n) + '*' + q(P) + '/(' + total + '*standardPressure))'
            reason = 'Ideal-gas mixture chemical potential of the declared package vapour at the standard pressure; formation-anchored'
        relation = a.relation(q(mu), right, reason, family='thermodynamics', kind='constitutive')
        current = a.substitute(current, relation, mu, family='thermodynamics')
    model['motores']['equationWorkbench'] = a.definition
    kind = 'liquido' if phase == 'liquid' else 'vapor'
    entry = {'provider': 'package', 'species': list(species), 'phaseId': kind,
             'standardState': 'pure_liquid_TP' if phase == 'liquid' else 'ideal_gas_P0', 'anchor': anchor, 'packageId': 'reactionPackage',
             'temperatureId': q(T), 'pressureId': q(P), 'amountIds': [q(n) for n in amounts],
             'referenceIds': [q(b[others.index(i)]) if i != k else 'zeroReference' for i in range(count)],
             'extentIds': [q(xi)], 'reactions': [{'id': 'reaction', 'stoichiometry': [str(c) for c in nu], 'equationId': current}]}
    model['motores']['equilibriumReactions'] = {'format': 'rage.equilibrium-reactions', 'version': 1, 'volumes': {owner: entry}}

    def datum(key, value, unit):
        return _datum(model, key, value, unit)
    parameters = {q(P): owner + '.pressure', 'zeroReference': datum('zero', 0, 'mol'), 'gasConstant': datum('R', 8.314462618, 'J/(mol*K)')}
    if phase != 'liquid':
        parameters['standardPressure'] = datum('P0', 1e5, 'Pa')
    if rigid:
        parameters[q(V)] = owner + '.rigidVolume'
    initial = {q(x): datum('initial' + str(i), reference[j], 'mol') for i, (x, j) in enumerate(zip(b, others))}
    if temperature_datum is None:
        initial[q(H)] = datum('initialEnergy', energy, 'J')
    else:
        initial[q(T)] = datum('initialTemperature', temperature_datum, 'K')
    bounds = {q(x): {key: datum('b' + str(i) + key, value, 'mol') for key, value in
                     [('lowerDataId', reference[j] - state_width), ('upperDataId', reference[j] + state_width)]}
              for i, (x, j) in enumerate(zip(b, others))}
    bounds[q(H)] = {key: datum('energy' + key, value, 'J') for key, value in
                    [('lowerDataId', energy - energy_width), ('upperDataId', energy + energy_width)]}
    extent = {key: datum('extent' + key, value, 'mol') for key, value in
              [('seedDataId', seed), ('lowerDataId', extent_box[0]), ('upperDataId', extent_box[1]), ('scaleDataId', 1)]}
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': datum('tf', 1, 's'), 'muestras': 3, 'metodoSolicitado': 'bdf',
                        'rtol': 1e-9, 'atol': {'cantidad': 1e-10, 'energia': 1e-6}}
    model['motores']['derivedExecution'] = {'format': 'rage.derived-execution', 'version': 4, 'sourceSignature': _signature(model),
        'timeId': q(t), 'states': states, 'algebraic': [{'quantityId': q(xi), 'equationId': current}], 'reconstructions': recon,
        'parameters': parameters, 'initialValues': initial, 'initialEquations': [], 'checks': [],
        'nonlinear': {'variables': {q(xi): extent}, 'residualScales': {current: datum('affinityScale', 1, '1')},
                      'residualTolerance': 1e-11, 'stepTolerance': step_tolerance, 'maxIterations': 30, 'maxBacktracks': 20},
        'dae': {'stateBounds': bounds, 'driftTolerance': 1e-9}}
    return _read(model)


# --- independent coupled references (mpmath; thermo UNIFAC for the excess) ---------------------------------
def pure_liquid_enthalpy(cas, T, P):
    """h_i*(T, P) = mu_i* - T dmu_i*/dT [J/mol] in mpmath (no binary64 rounding of T), liquid formation anchor:
    cp_L route Hl + int cp_L dT + v_L (P - P0); Psat route g_L - T g_L' shifted so that h(T0, P0) = Hl."""
    mp.mp.dps = 50
    e = data.especie(cas)
    T, P = mp.mpf(T), mp.mpf(repr(float(P)))
    Hl, vL = mp.mpf(repr(rx.Hfl(cas))), mp.mpf(repr(e.vL))
    if e.cp_L is not None:
        c = [mp.mpf(repr(v)) for v in e.cp_L]
        return Hl + mp.fsum(c[k] * (T**(k + 1) - T0**(k + 1)) / (k + 1) for k in range(len(c))) + vL * (P - P0)
    def h(t, p):
        return _liquid_g(e, t, p) - t * mp.diff(lambda u: _liquid_g(e, u, p), t)
    return h(T, P) + (Hl - h(T0, P0))


def liquid_enthalpy(species, n, T, P, variant):
    """H = sum n_i h_i*(T,P) + H^E [J]: h_i* from pure_liquid_enthalpy and H^E = N * thermo UNIFAC HE()."""
    mp.mp.dps = 50
    pure = mp.fsum(mp.mpf(repr(float(v))) * pure_liquid_enthalpy(c, mp.mpf(repr(float(T))), P) for c, v in zip(species, n))
    tu.load_group_assignments_DDBST()
    table = tu.DDBST_UNIFAC_assignments if variant == 'original' else tu.DDBST_MODIFIED_UNIFAC_assignments
    groups = [table[search_chemical(c).InChI_key] for c in species]
    options = ({'version': 0, 'subgroups': tu.UFSG, 'interaction_data': tu.UFIP} if variant == 'original' else
               {'version': 1, 'subgroups': tu.DOUFSG, 'interaction_data': tu.DOUFIP2016})
    N = sum(float(v) for v in n)
    excess = tu.UNIFAC.from_subgroups(float(T), [float(v) / N for v in n], groups, **options).HE()
    return pure + mp.mpf(repr(float(N * excess)))


def coupled_liquid_reference(species, nu, n0, H0, P, variant, guess):
    """(xi, T) solving {sum_i nu_i ln(x_i gamma_i) = ln K(T), H(T, n(xi)) = H0}: for each T the extent is the
    equilibrium root (reference_extent), and T is the secant root of H(T, n(xi(T))) - H0. thermo's ln gamma and
    H^E are binary64, so the attainable accuracy is about 1e-12 relative, not 50 digits."""
    def extent(T):
        return reference_extent(species, nu, n0, T, P, variant, guess[0])

    def energy(T):
        xi = extent(T)
        n = [mp.mpf(a) + v * xi for a, v in zip(n0, nu)]
        return (liquid_enthalpy(species, n, T, P, variant) - mp.mpf(repr(float(H0)))) / 1000
    T = mp.findroot(energy, (mp.mpf(guess[1]) - 1, mp.mpf(guess[1]) + 1), solver='secant', tol=mp.mpf('1e-26'), verify=False)
    return extent(T), T


def _poling(cas):
    return [mp.mpf(repr(v)) for v in data.especie(cas).cp]


def gas_enthalpy_molar(cas, T):
    """Hfg_i + R int_T0^T cp/R dT (Poling cp/R from the coefficient tuple) [J/mol]."""
    a = _poling(cas)
    return mp.mpf(repr(rx.Hfg(cas))) + R * mp.fsum(a[k] * (T**(k + 1) - T0**(k + 1)) / (k + 1) for k in range(len(a)))


def gas_potential(cas, T, P, x):
    """Ideal-gas mu_i = h_i - T s_i with s_i = S0g_i + R int cp/(R T) dT - R ln(x_i P/P0) [J/mol]."""
    a = _poling(cas)
    s = mp.mpf(repr(rx.S0g(cas))) + R * (a[0] * mp.log(T / T0) + mp.fsum(a[k] * (T**k - T0**k) / k for k in range(1, len(a))))
    return gas_enthalpy_molar(cas, T) - T * s + R * T * mp.log(x * P / P0)


def gas_enthalpy(species, n, T):
    mp.mp.dps = 50
    T = mp.mpf(repr(float(T)))
    return mp.fsum(mp.mpf(repr(float(v))) * gas_enthalpy_molar(c, T) for c, v in zip(species, n))


def coupled_gas_reference(species, nu, n0, H0, P, guess):
    """(xi, T) solving {sum_i nu_i mu_i = 0, sum_i n_i h_i(T) = H0} for the ideal-gas mixture (50 digits).

    Inner: for each T, the extent is the bracketed root of the affinity, which is strictly increasing in xi for an
    ideal gas, over the open interval where every amount is positive. Outer: secant root of H(T, n(xi(T))) - H0."""
    mp.mp.dps = 50
    nu_ = [mp.mpf(v) for v in nu]
    P = mp.mpf(repr(float(P)))
    n0_ = [mp.mpf(a) for a in n0]
    lo = max([-a / v for a, v in zip(n0_, nu_) if v > 0] or [mp.mpf('-1e3')])
    hi = min([-a / v for a, v in zip(n0_, nu_) if v < 0] or [mp.mpf('1e3')])

    def amounts(xi):
        return [a + v * xi for a, v in zip(n0_, nu_)]

    def affinity(xi, T):
        n = amounts(xi)
        N = mp.fsum(n)
        return mp.fsum(v * gas_potential(c, T, P, m / N) for c, v, m in zip(species, nu_, n) if v) / (R * T)

    def extent(T):
        width = hi - lo
        return mp.findroot(lambda xi: affinity(xi, T), (lo + width * mp.mpf('1e-30'), hi - width * mp.mpf('1e-30')),
                           solver='anderson', tol=mp.mpf('1e-80'), verify=False, maxsteps=400)

    def energy(T):
        return (mp.fsum(m * gas_enthalpy_molar(c, T) for c, m in zip(species, amounts(extent(T)))) - mp.mpf(repr(float(H0)))) / 1000
    T = mp.findroot(energy, (mp.mpf(guess[1]) - 1, mp.mpf(guess[1]) + 1), solver='secant', tol=mp.mpf('1e-60'), verify=False)
    xi = extent(T)
    assert abs(affinity(xi, T)) < mp.mpf('1e-35') and abs(energy(T)) < mp.mpf('1e-30')
    return xi, T
