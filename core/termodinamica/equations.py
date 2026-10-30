"""Typed thermodynamic premises and their algebraic consequences.

Constitutive packages are named premises. They are never claimed to follow
from conservation; Legendre identities and caloric inversion are actual graph
operations with shared state identities.
"""
import sympy as sp
from core.mathematics.operators import StateDifferential
from core.modelo.equation_manipulation import EquationGraph
from core.modelo.operation_journal import replay
from . import derivation




def equation_graph(model,owner):
    volume=next(v for v in model['volumenes'] if v['id']==owner)
    entry=model.get('motores',{}).get('thermodynamicDerivation',{}).get('volumes',{}).get(owner)
    state=replay(entry,derivation.fundamental,derivation.normalize)[-1] if entry else derivation.fundamental()
    graph=EquationGraph();units={};prefix='thermodynamics.'+owner+'.';t=sp.Symbol('t',real=True)
    def quantity(name,unit,display=None,constant=False):
        q=sp.Symbol(name+'__'+owner,real=True) if constant else sp.Function(name+'__'+owner)(t)
        units[q]=unit;graph.names[q]=display or name+'(t)';return q
    U=quantity('U','J');H=quantity('H','J');G=quantity('G','J');S=quantity('S','J/K')
    T=quantity('T','K');P=quantity('P','Pa');V=quantity('V','m3')
    components=volume.get('componenteIds') or ['i']
    n=[quantity('n_'+str(i),'mol',r'n_{'+str(i)+'}(t)') for i in components]
    mu=[quantity('mu_'+str(i),'J/mol',r'\mu_{'+str(i)+'}(t)') for i in components]
    coordinates=[U,H,G,S,T,P,V,*n,*mu]
    D=StateDifferential
    def differential(expression):return sp.expand(sum(sp.diff(expression,q)*D(q) for q in coordinates))
    def add(name,left,right,title,rule='definition',inputs=(),conditions=(),kind='definition'):
        key=prefix+name;graph.add(key,left,right,title,rule,tuple(prefix+i for i in inputs),conditions,'thermodynamics',kind=kind);return key
    add('fundamental',D(U),T*D(S)-P*D(V)+sum(a*D(b) for a,b in zip(mu,n)),
        'Fundamental thermodynamic relation · simple compressible system','declared_law',kind='constitutive')
    add('enthalpy',H,U+P*V,'Define enthalpy by a Legendre transformation')
    add('gibbs',G,H-T*S,'Define Gibbs energy by a Legendre transformation')
    graph.transform(prefix+'dH',prefix+'enthalpy',differential,'Differentiate the enthalpy definition','total_differential')
    graph.transform(prefix+'dG-definition',prefix+'gibbs',differential,'Differentiate the Gibbs definition','total_differential')
    graph.substitute(prefix+'dH-reduced',prefix+'dH',{D(U):graph.nodes[prefix+'fundamental'].equation.rhs},
                     'Substitute the fundamental thermodynamic relation',inputs=(prefix+'fundamental',))
    graph.substitute(prefix+'dG',prefix+'dG-definition',{D(H):graph.nodes[prefix+'dH-reduced'].equation.rhs},
                     'Substitute the enthalpy differential and cancel common terms',inputs=(prefix+'dH-reduced',))
    add('extensivity',U,T*S-P*V+sum(a*b for a,b in zip(mu,n)),
        'Apply Euler theorem under extensive homogeneity','euler_homogeneity',('fundamental',),
        ('Simple compressible extensive state; U is homogeneous of degree one in S, V and amounts',),kind='constitutive')
    graph.substitute(prefix+'H-euler',prefix+'enthalpy',{U:graph.nodes[prefix+'extensivity'].equation.rhs},'Use the extensive internal-energy relation',inputs=(prefix+'extensivity',))
    graph.substitute(prefix+'G-euler',prefix+'gibbs',{H:graph.nodes[prefix+'H-euler'].equation.rhs},'Euler identity for Gibbs energy from chemical potentials',inputs=(prefix+'H-euler',))
    graph.transform(prefix+'G-euler-differential',prefix+'G-euler',differential,'Differentiate the extensive Gibbs identity','total_differential')
    eq=graph.nodes[prefix+'G-euler-differential'].equation
    graph.substitute(prefix+'gibbs-duhem-substitution',prefix+'dG',{D(G):eq.rhs},'Equate the two Gibbs differentials',inputs=(prefix+'G-euler-differential',))
    eq=graph.nodes[prefix+'gibbs-duhem-substitution'].equation
    common=sum(a*D(b) for a,b in zip(mu,n))
    add('gibbs-duhem',sp.expand(eq.lhs-common),sp.expand(eq.rhs-common),'Cancel the common composition differential','subtract_from_both_sides',('gibbs-duhem-substitution',))
    final=[prefix+'dG',prefix+'G-euler',prefix+'gibbs-duhem']
    mass=sum((sp.Function('m__'+owner+'__'+str(i))(t) for i in components),sp.S.Zero)
    for item in mass.atoms(sp.Function):units[item]='kg'
    rho=quantity('rho_mean_mixture','kg/m3',r'\bar\rho(t)')
    add('mass-density',mass,rho*V,'Define volume-average mixture density',conditions=('Positive domain volume',))
    mean_u=quantity('u_mean','J/kg',r'\bar u(t)')
    add('specific-inventory',U,mass*mean_u,'Define mass-average specific internal energy',conditions=('Positive total mass',))
    if state['densidadConstante']:
        reference=quantity('rho_reference','kg/m3',r'\rho_*',True)
        add('constant-density',rho,reference,'Declare constant mixture density','assumption',conditions=('Positive reference density',),kind='constraint')
        graph.substitute(prefix+'constant-density-inventory',prefix+'mass-density',{rho:reference},'Apply the declared density closure',inputs=(prefix+'constant-density',))
        graph.isolate(prefix+'volume',prefix+'constant-density-inventory',V,'Recover volume from the same material inventory',('Positive reference density',))
        graph.differentiate(prefix+'volume-rate',prefix+'volume',t,'Differentiate volume without removing the material dynamics')
        final.extend([prefix+'volume',prefix+'volume-rate'])
    if state['modelo']=='u_lineal':
        reference_u=quantity('u_reference','J/kg',r'u_{ref}',True);reference_T=quantity('T_reference','K',r'T_{ref}',True)
        capacity=quantity('caloric_capacity','J/(kg*K)',r'c_u',True)
        add('caloric',mean_u,reference_u+capacity*(T-reference_T),'Declare the linear caloric constitutive law','constitutive_choice',conditions=('Positive caloric coefficient; declared temperature validity interval',),kind='constitutive')
        graph.substitute(prefix+'caloric-inventory',prefix+'specific-inventory',{mean_u:graph.nodes[prefix+'caloric'].equation.rhs},'Substitute the caloric law in the energy inventory',inputs=(prefix+'caloric',))
        graph.isolate(prefix+'temperature',prefix+'caloric-inventory',T,'Isolate temperature from the energy inventory',('Positive total mass and caloric coefficient',))
        final.append(prefix+'temperature')
    if state['monofasico']:
        count=quantity('present_phase_count','1',r'N_{present}')
        final.append(add('single-phase',count,1,'Declare a single present phase','assumption',kind='constraint'))
    if state['sinCambioFase']:
        # The set itself is a condition, not an invented differentiable state.
        count=quantity('phase_membership_indicator','1',r'\mathbf 1_{\mathcal P}(t)')
        initial=quantity('initial_phase_membership_indicator','1',r'\mathbf 1_{\mathcal P}(0)',True)
        final.append(add('fixed-phase-set',count,initial,'Keep the declared initial phase membership','assumption',kind='constraint'))
    selected=state['closure']
    if selected:
        package=selected['model']['id']+' @ '+selected['model']['version']
        potential=sp.Function('G_package__'+owner)(T,P,*n);units[potential]='J'
        graph.names[potential]=r'G_{pkg}(T,P,\mathbf n)'
        add('package-potential',G,potential,'Select constitutive Gibbs potential · '+package,'constitutive_choice',
            conditions=('Package '+selected['packageId']+'; empirical parameters and validity domains remain package data',),kind='constitutive')
        final.append(prefix+'package-potential')
        # Coefficients of the total differential determine conjugate properties.
        add('package-differential',D(G),sum(sp.diff(potential,q)*D(q) for q in [T,P,*n]),
            'Differentiate the selected potential in its independent state arguments','total_differential',('package-potential',),('Differentiable homogeneous phase branch',))
        for name,q,property_,sign in [('entropy',T,S,-1),('volume-property',P,V,1)]+[('chemical-potential-'+str(i),amount,chemical,1) for i,amount,chemical in zip(components,n,mu)]:
            final.append(add(name,property_,sign*sp.diff(potential,q),'Match the '+name+' coefficient of the Gibbs differential','match_differential_coefficients',('dG','package-differential')))
        graph.substitute(prefix+'package-H',prefix+'gibbs',{G:potential,S:-sp.diff(potential,T)},'Substitute the potential and entropy in the Gibbs definition',inputs=(prefix+'package-potential',prefix+'entropy'))
        graph.isolate(prefix+'package-enthalpy',prefix+'package-H',H,'Recover enthalpy from the same potential')
        graph.substitute(prefix+'package-U',prefix+'enthalpy',{H:graph.nodes[prefix+'package-enthalpy'].equation.rhs,V:sp.diff(potential,P)},'Use the same potential for energy and volume',inputs=(prefix+'package-enthalpy',prefix+'volume-property'))
        graph.isolate(prefix+'package-internal-energy',prefix+'package-U',U,'Recover internal energy from enthalpy and volume')
        final.extend([prefix+'package-enthalpy',prefix+'package-internal-energy'])
        k=sp.Symbol('k',integer=True,positive=True);K=sp.Symbol('K__'+owner,integer=True,positive=True)
        units[k]=units[K]='1';graph.names[K]='K'
        amounts=[sp.Function('phase_amount_'+str(i)+'__'+owner)(k,t) for i in components]
        fractions=[sp.Function('phase_composition_'+str(i)+'__'+owner)(k,t) for i in components]
        phase_total=sp.Function('phase_total__'+owner)(k,t);units[phase_total]='mol'
        graph.names[phase_total]=r'n_k'
        for i,amount,fraction in zip(components,amounts,fractions):
            units[amount]='mol';units[fraction]='1';graph.names[amount]=r'n^k_{'+str(i)+'}';graph.names[fraction]=r'x^k_{'+str(i)+'}'
        add('phase-amount',phase_total,sum(amounts),'Define the phase amount from component amounts')
        composition_inputs=[]
        for i,amount,fraction in zip(components,amounts,fractions):
            composition_inputs.append(add('composition-'+str(i),fraction,amount/phase_total,'Define the phase mole fraction',conditions=('Positive phase amount; nonnegative component amounts',)))
        graph.combine(prefix+'composition-sum',composition_inputs,'Sum the component-fraction definitions')
        graph.transform(prefix+'composition-factor',prefix+'composition-sum',sp.factor,'Collect the common phase-amount denominator','factor')
        graph.substitute(prefix+'composition-normalization',prefix+'composition-factor',{sum(amounts):phase_total},'Use the phase amount definition to normalize composition',inputs=(prefix+'phase-amount',))
        final.append(prefix+'composition-normalization')
        for i,amount,fraction in zip(components,n,fractions):
            final.append(add('component-partition-'+str(i),amount,sp.Sum(phase_total*fraction,(k,1,K)),'Partition component amount over candidate phases',conditions=('Nonnegative phase amounts',)))
        for name,inventory,unit in [('energy',U,'J/mol'),('enthalpy',H,'J/mol'),('volume',V,'m3/mol')]:
            property_=sp.Function('phase_'+name+'__'+owner)(k,t);units[property_]=unit
            graph.names[property_]=r'\bar '+{'energy':'u','enthalpy':'h','volume':'v'}[name]+r'_k'
            final.append(add('phase-'+name,inventory,sp.Sum(phase_total*property_,(k,1,K)),'Add extensive '+name+' over phases'))
        # Candidate-phase equilibrium is a constitutive constraint system.
        # Keep the phase label generic: no liquid-liquid/vapor scenario branch.
        for i,chemical in zip(components,mu):
            phase_mu=quantity('mu_phase_'+str(i),'J/mol',r'\mu^k_{'+str(i)+'}')
            final.append(add('phase-equilibrium-'+str(i),phase_mu,chemical,'Equal chemical potentials of present phases','equilibrium_condition',conditions=('Present phases at common temperature and pressure',),kind='constraint'))
        beta=quantity('phase_fraction','1',r'\beta_k');distance=quantity('phase_tangent_distance','J/mol',r'TPD_k')
        final.append(add('phase-stability',beta*distance,0,'Candidate-phase complementarity','equilibrium_condition',conditions=(r'\beta_k\geq0',r'TPD_k\geq0','Finite package candidate-phase search; no universal global-stability claim'),kind='constraint'))
    return graph,final,units
