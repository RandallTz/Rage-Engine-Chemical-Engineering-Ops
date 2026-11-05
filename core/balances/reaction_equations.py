"""Declared stoichiometric definitions and kinetic constitutive roots.

Only source definitions live here. The existing fundamental conservation graph
and recorded workbench substitutions supply the component balance equations.
Formation energies remain in the separately authored thermodynamic relations.
"""
import sympy as sp
from core.modelo.equation_manipulation import EquationGraph
from core.modelo.reaction_definition import read_definition, coefficient
from core.mathematics.constants import unit_basis
from core.unidades import interpretar


def declarations(model, owner):
    config = model.get('motores', {}).get('kineticReactions')
    graph = EquationGraph(); units = {}; bindings = {}; source_ids = []
    if config is None or owner not in config['volumes']:
        return graph, units, bindings, source_ids
    read_definition(config, model)
    entry = config['volumes'][owner]
    t = sp.Symbol('t', real=True)
    prefix = 'reaction.'+owner+'.'
    def quantity(name, unit, data=None, dynamic=False):
        q = sp.Function(name+'__'+owner)(t) if dynamic else sp.Symbol(name+'__'+owner, real=True)
        units[q] = unit
        if data is not None: bindings[q] = data
        return q
    V = (sp.Symbol('V__'+owner, positive=True) if config['version'] == 1
         else sp.Function('V__'+owner)(t))
    units[V] = 'm3'
    if config['version'] == 1:
        bindings[V] = entry['volumeDataId']
    T = sp.Function('T__'+owner)(t); units[T] = 'K'
    masses = {}; amounts = {}; concentrations = {}; rates = {}
    for c, data in entry['molarMassDataIds'].items():
        M = quantity('molar_mass_'+c, 'kg/mol', data); masses[c] = M
        m = sp.Function('m__'+owner+'__'+c)(t); units[m] = 'kg'
        n = quantity('amount_'+c, 'mol', dynamic=True); amounts[c] = n
        concentration = quantity('concentration_'+c, 'mol/m3', dynamic=True); concentrations[c] = concentration
        graph.add(prefix+'amount.'+c, m, M*n, 'Define molar amount from component mass', 'definition',
                  assumptions=('Constant positive molar mass; nonnegative component amount',), family='matter', kind='definition', predicates=(sp.Gt(M, 0), sp.Ge(n, 0)))
        graph.add(prefix+'concentration.'+c, concentration, n/V, 'Define molar concentration', 'definition',
                  family='matter', kind='definition', predicates=(sp.Gt(V, 0), sp.Ge(n, 0)))
    for reaction in entry['reactions']:
        rid = reaction['id']; order = sum(reaction['orders'].values())
        element_ids = []
        for element, row in entry['elements'].items():
            key = prefix+'element.'+element+'.'+rid
            # Preserve the declared coefficients in the typed root, even
            # when their exact sum is zero. Source signatures then also pin
            # elemental/charge premises rather than only the kinetic formula.
            # Unevaluated zero products can produce inconsistent SymPy
            # assumptions; absent elements contribute no term to this sum.
            terms = [sp.Mul(sp.Integer(row[c]), coefficient(reaction['stoichiometry'][c]), evaluate=False) for c in masses if row[c] != 0]
            graph.add(key, sp.Add(*terms, evaluate=False), 0, 'Declared '+element+' conservation', 'declared_condition',
                      family='matter', kind='constraint')
            element_ids.append(key)
        mass_residual = sum(masses[c]*coefficient(reaction['stoichiometry'][c]) for c in masses)
        graph.add(prefix+'mass-conservation.'+rid, mass_residual, 0, 'Stoichiometry preserves total mass', 'declared_condition',
                  inputs=tuple(prefix+'amount.'+c for c in masses), family='matter', kind='constraint')
        k = quantity('rate_constant_'+rid, f'(mol/m3)^{1-order}/s', reaction['rateConstantDataId'])
        r = quantity('rate_'+rid, 'mol/(m3*s)', dynamic=True); rates[rid] = r
        expression = k*sp.prod(concentrations[c]**power for c, power in reaction['orders'].items())
        predicates = [sp.Ge(k, 0), sp.Eq(mass_residual, 0, evaluate=False)]
        if 'arrhenius' in reaction:
            a = reaction['arrhenius']
            E = quantity('activation_energy_'+rid, 'J/mol', a['energyDataId'])
            Tref = quantity('rate_reference_temperature_'+rid, 'K', a['temperatureDataId'])
            R = sp.Rational('8.31446261815324')*unit_basis(interpretar('J/(mol*K)')['dimension'])
            expression *= sp.exp(-E/R*(1/T-1/Tref))
            predicates.extend((sp.Gt(T, 0), sp.Gt(Tref, 0)))
        graph.add(prefix+'kinetics.'+rid, r, expression, 'Declare concentration-based kinetic law', 'constitutive_relation',
                  inputs=tuple(element_ids)+tuple(prefix+'concentration.'+c for c in reaction['orders']),
                  assumptions=('Forward volumetric molar rate; reverse laws are separate reactions',),
                  family='matter', kind='constitutive', predicates=tuple(predicates))
    for c in amounts:
        for name, sign, stem in [('generation', 1, 'g'), ('consumption', -1, 'c')]:
            source = sp.Function(stem+'__'+owner+'__'+c)(t); units[source] = 'kg/(m3*s)'
            expression = masses[c]*sum(max(sign*coefficient(r['stoichiometry'][c]), 0)*rates[r['id']] for r in entry['reactions'])
            key = prefix+name+'.'+c
            graph.add(key, source, expression, 'Define stoichiometric '+name+' density', 'definition',
                      inputs=tuple(prefix+'kinetics.'+r['id'] for r in entry['reactions'])+(prefix+'amount.'+c,),
                      assumptions=('Spatially uniform reaction rates in the declared reacting volume',), family='matter', kind='definition')
            source_ids.append(key)
    return graph, units, bindings, source_ids
