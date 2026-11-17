"""F5 item 5: the ideal-gas standard potential mu_i0(T) deduced from cp through the shared Model operations.

Per reacting species i the Model records, in the thermodynamics family and on the reduced temperature
tau = T / Tref (dimensionless, so that the entropy integral has a dimensionless logarithm):

    G = H - T S                        definition, pure ideal gas at P0, T = Tref tau
    dg/dtau = dh/dtau - Tref s - Tref tau ds/dtau   differentiate
    dg/dtau = -Tref s                  definition S = -(dG/dT)_P (fundamental dG = -S dT + V dP at constant P0)
    dh/dtau = Tref tau ds/dtau         substitute + isolate: dH = T dS at P0, deduced, not declared
    cp = (dh/dtau) / Tref              definition of the isobaric heat capacity
    cp = R (a0 + a1 T + ... + a4 T^4)  constitutive (published Poling ideal-gas polynomial, recorded data)
    integrate dh/dtau and ds/dtau      integration constants named, then fixed at the formation reference:
    Tref tau = Tref, h(1) = Hf, s(1) = S0   constraint + constitutive reference data
    g = h - Tref tau s                      substitutions
    Tref tau = T                            constraint: evaluate at the region temperature

The chemical potential is then recorded as mu_i = g_i(T/Tref) + R T log(n_i P / (n P0)) and substituted into the
affinity, as the undefined-function form of F5-C1 was. No terminal formula is inserted.
"""
import copy

import sympy as sp

from core.compilador.derived_graph import source_signature
from core.modelo import leer_modelo_comun
from derived_closure_inputs import _datum
from m1_acceptance import SharedAuthor
import equilibrium_reaction_inputs as E

F = 'thermodynamics'
T_REFERENCE = 298.15


def poling(cas):
    import chemicals.heat_capacity as hc
    d = hc.Cp_data_Poling.loc[cas]
    return [float(d[k]) for k in ('a0', 'a1', 'a2', 'a3', 'a4')]


def formation(cas):
    from core.reactions.chemical_equilibrium import formation_reference
    Hf, S0, _ = formation_reference(cas)
    return Hf, S0


def deduce(a, owner, i, cas, T_region, data, *, omit=None, coefficients=None, Hf=None, S0=None):
    """Append the deduction of g_i(T/Tref) for species index i (1-based) and return that quantity.

    data collects {symbol name: (value, unit)}. omit names one step to leave out (a negative control):
    'entropy' records g = h (no -T s), 'reference' leaves the enthalpy constant at zero."""
    q = a.quantity
    t = sp.Symbol('t', real=True)
    sym = lambda name: sp.Symbol(name, real=True)

    def declare(name, unit, value=None):
        if name not in a.result.introduced.values() and not any(str(v) == name for v in a.result.introduced.values()):
            a.append('declare_symbol', name=name, unit=unit)
        if value is not None:
            data[name] = (value, unit)
        return sym(name)

    tau = declare('reducedTemperature', '1')
    Tr = declare('referenceTemperature', 'K', T_REFERENCE)
    declare('gasConstant', 'J/(mol*K)')
    cp_data = coefficients or poling(cas)
    hf, s0 = formation(cas)
    hf, s0 = (hf if Hf is None else Hf), (s0 if S0 is None else S0)
    Hf_ = declare('formationEnthalpy' + str(i), 'J/mol', hf)
    S0_ = declare('standardEntropy' + str(i), 'J/(mol*K)', s0)
    a_ = [declare('heatCapacityCoefficient%d_%d' % (k, i), ('K^-%d' % k) if k else '1', v) for k, v in enumerate(cp_data)]

    def function(name, unit):
        a.append('declare_function', family=F, name=name + str(i), unit=unit, dependencies=[q(tau)])
        return sp.Function(name + str(i))(tau)

    g, h, s, cp = (function('standardGibbs', 'J/mol'), function('standardEnthalpy', 'J/mol'),
                   function('standardEntropyFunction', 'J/(mol*K)'), function('heatCapacity', 'J/(mol*K)'))
    T, TQ = q(Tr), q(tau)
    rel = lambda left, right, reason, kind: a.relation(left, right, reason, family=F, kind=kind)
    gibbs = rel(q(g), q(h) if omit == 'entropy' else q(h) + '-' + T + '*' + TQ + '*' + q(s),
                'Gibbs energy of the pure ideal gas at P0: G = H - T S, with T = Tref tau', 'definition')
    varied = a.append('differentiate', family=F, sources=[gibbs], symbol=TQ)
    Dg, Dh, Ds = sp.Derivative(g, tau), sp.Derivative(h, tau), sp.Derivative(s, tau)
    if omit != 'entropy':
        # dH = T dS at P0 is deduced: the tau derivative of G = H - T S with S = -(dG/dT)_P.
        entropy_definition = rel(q(Dg), '-' + T + '*' + q(s),
                                 'Entropy S = -(dG/dT)_P, from the fundamental relation dG = -S dT + V dP at the constant '
                                 'standard pressure, with dT = Tref dtau', 'definition')
        fundamental = a.substitute(varied, entropy_definition, Dg, family=F)
        fundamental = a.append('isolate', family=F, sources=[fundamental], symbol=q(Dh))
    capacity = rel(q(cp), q(Dh) + '/' + T, 'Isobaric heat capacity cp = dh/dT, with dT = Tref dtau', 'definition')
    polynomial = rel(q(cp), 'gasConstant*(' + '+'.join(q(c) + ('*(' + T + '*' + TQ + ')^%d' % k if k else '')
                                                       for k, c in enumerate(a_)) + ')',
                     'Published ideal-gas heat capacity polynomial (Poling, chemicals Cp_data_Poling)', 'constitutive')
    dh = a.append('isolate', family=F, sources=[capacity], symbol=q(Dh))
    dh = a.substitute(dh, polynomial, cp, family=F)
    # Constraints are recorded as T = Tref tau (product left side): a bare declared constant on the left would be
    # a compiler replacement, and joined to T(t) it is refused (constant_time_join).
    reference = rel(T + '*' + TQ, T, 'Temperature of the formation reference state: Tref tau = Tref', 'constraint')
    one = sp.Integer(1)

    def integrate(rate, function_at, datum, constant):
        integrated = a.append('integrate', family=F, sources=[rate], symbol=TQ, name=constant + str(i))
        if omit == 'reference' and constant == 'enthalpyConstant':
            zero = rel(q(sym(constant + str(i))), '0', 'Integration constant set to zero', 'constraint')
            return a.substitute(integrated, zero, sym(constant + str(i)), family=F)
        at_reference = a.substitute(integrated, reference, tau, family=F)
        value = rel(q(function_at), q(datum), 'Ideal-gas formation reference datum at 298.15 K and P0', 'constitutive')
        at_reference = a.substitute(at_reference, value, function_at, family=F)
        fixed = a.append('isolate', family=F, sources=[at_reference], symbol=q(sym(constant + str(i))))
        return a.substitute(integrated, fixed, sym(constant + str(i)), family=F)

    enthalpy = integrate(dh, sp.Function('standardEnthalpy' + str(i))(one), Hf_, 'enthalpyConstant')
    enthalpy = a.append('isolate', family=F, sources=[enthalpy], symbol=q(h))
    current = a.substitute(gibbs, enthalpy, h, family=F)
    if omit != 'entropy':
        ds = a.append('isolate', family=F, sources=[fundamental], symbol=q(Ds))
        ds = a.substitute(ds, dh, Dh, family=F)
        entropy = integrate(ds, sp.Function('standardEntropyFunction' + str(i))(one), S0_, 'entropyConstant')
        current = a.substitute(current, entropy, s, family=F)
    region = rel(T + '*' + TQ, q(T_region), 'Temperature of the region state: Tref tau = T', 'constraint')
    current = a.substitute(current, region, tau, family=F)
    return a.result.graph.nodes[current].equation.lhs



def deduce_terminal(a, owner, i, cas, T_region, data, **_):
    """Review probe (16 November 2026): h_i(tau) and s_i(tau) declared directly as the closed-form cp integrals,
    G = H - T S, two substitutions and the region constraint. No cp relation, differentiation or integration is
    recorded, so the result is not deduced from cp and must be rejected (reaction_standard_potential_not_deduced)."""
    q = a.quantity
    sym = lambda name: sp.Symbol(name, real=True)

    def declare(name, unit, value=None):
        if not any(str(v) == name for v in a.result.introduced.values()):
            a.append('declare_symbol', name=name, unit=unit)
        if value is not None:
            data[name] = (value, unit)
        return sym(name)
    tau = declare('reducedTemperature', '1')
    Tr = declare('referenceTemperature', 'K', T_REFERENCE)
    declare('gasConstant', 'J/(mol*K)')
    hf, s0 = formation(cas)
    Hf_ = declare('hf' + str(i), 'J/mol', hf)
    S0_ = declare('sf' + str(i), 'J/(mol*K)', s0)
    a_ = [declare('c%d_%d' % (k, i), ('K^-%d' % k) if k else '1', v) for k, v in enumerate(poling(cas))]
    a.append('declare_function', family=F, name='standardGibbs' + str(i), unit='J/mol', dependencies=[q(tau)])
    g = sp.Function('standardGibbs' + str(i))(tau)
    T, TQ = q(Tr), q(tau)
    Tt = '(' + T + '*' + TQ + ')'
    h = '+'.join('%s*(%s^%d-%s^%d)/%d' % (q(c), Tt, k + 1, T, k + 1, k + 1) for k, c in enumerate(a_))
    s = q(a_[0]) + '*log(' + TQ + ')+' + '+'.join('%s*(%s^%d-%s^%d)/%d' % (q(c), Tt, k, T, k, k) for k, c in enumerate(a_) if k)
    for name, unit in (('standardEnthalpy', 'J/mol'), ('standardEntropyFunction', 'J/(mol*K)')):
        a.append('declare_function', family=F, name=name + str(i), unit=unit, dependencies=[q(tau)])
    hfun, sfun = sp.Function('standardEnthalpy' + str(i))(tau), sp.Function('standardEntropyFunction' + str(i))(tau)
    texts = {'h': q(Hf_) + '+gasConstant*(' + h + ')', 's': q(S0_) + '+gasConstant*(' + s + ')'}
    gibbs = a.relation(q(g), q(hfun) + '-' + Tt + '*' + q(sfun), 'G = H - T S (reviewer bypass probe)', family=F, kind='definition')
    hrel = a.relation(q(hfun), texts['h'], 'Terminal enthalpy, no cp or integration recorded (reviewer bypass probe)', family=F, kind='constitutive')
    srel = a.relation(q(sfun), texts['s'], 'Terminal entropy, no cp or integration recorded (reviewer bypass probe)', family=F, kind='constitutive')
    final = a.substitute(gibbs, hrel, hfun, family=F)
    final = a.substitute(final, srel, sfun, family=F)
    region = a.relation(T + '*' + TQ, q(T_region), 'Temperature of the region state: Tref tau = T', family=F, kind='constraint')
    current = a.substitute(final, region, tau, family=F)
    return a.result.graph.nodes[current].equation.lhs


def deduced_author(owner='gas', deduced=(1,), omit=None, override=None, terminal=False, **kwargs):
    """The F5-C1 ideal-gas region (tests/equilibrium_reaction_inputs.py) whose mu_i0(T) is deduced from cp.

    deduced: the 1-based species whose standard potential is deduced; the others keep the F5-C1 undefined
    standard-potential function of time (each shared-author operation replays the whole history, so a deduction
    costs minutes per species). override: {species index: dict(coefficients=..., Hf=..., S0=...)}."""
    model = E.author(owner, record_potential=False, **kwargs)
    model = copy.deepcopy(model)
    entry = model['motores']['equilibriumReactions']['volumes'][owner]
    selection = model['motores']['derivedExecution']
    a = SharedAuthor(model)
    a.definition = copy.deepcopy(model['motores']['equationWorkbench'])
    a.refresh()
    q = a.quantity
    t = sp.Symbol('t', real=True)
    f = lambda name: sp.Function(name)(t)
    T, P = f('T__' + owner), f('P__' + owner)
    amounts = [f('n_' + str(i) + '__' + owner) for i in range(1, len(entry['species']) + 1)]
    total = '(' + '+'.join(q(n) for n in amounts) + ')'
    a.append('declare_symbol', name='standardPressure', unit='Pa')
    data = {'standardPressure': (1e5, 'Pa')}
    current = entry['reactions'][0]['equationId']
    nu = [int(v) for v in entry['reactions'][0]['stoichiometry']]
    for i, (cas, n) in enumerate(zip(entry['species'], amounts), 1):
        if nu[i - 1] == 0:
            continue
        if i in deduced:
            standard = (deduce_terminal if terminal else deduce)(a, owner, i, cas, T, data, omit=omit, **(override or {}).get(i, {}))
        else:
            a.append('declare_function', name='standardPotential' + str(i), unit='J/mol', dependencies=[q(t)])
            standard = f('standardPotential' + str(i))
        mu = f('mu_' + str(i) + '__' + owner)
        relation = a.relation(q(mu), q(standard) + '+gasConstant*' + q(T) + '*log(' + q(n) + '*' + q(P) + '/(' + total + '*standardPressure))',
                              'Ideal-gas mixture chemical potential at the standard pressure; standard potential deduced from cp',
                              family=F, kind='constitutive')
        current = a.substitute(current, relation, mu, family=F)
    old = entry['reactions'][0]['equationId']
    entry['reactions'][0]['equationId'] = current
    selection['algebraic'][0]['equationId'] = current
    selection['nonlinear']['residualScales'] = {current: selection['nonlinear']['residualScales'][old]}
    for name, (value, unit) in data.items():
        selection['parameters'][name] = _datum(model, 'standard.' + name, value, unit)
    model['motores']['equationWorkbench'] = a.definition
    selection['sourceSignature'] = source_signature(model)
    return leer_modelo_comun(model)
