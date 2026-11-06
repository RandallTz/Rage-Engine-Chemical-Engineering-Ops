"""Internal ideal-gas equilibrium author using the shared Model operations."""
import copy
import sympy as sp
from m1_acceptance import SharedAuthor,thermal_source
from core.balances import material_derivation as material
from core.compilador.derived_graph import source_signature
from core.modelo import leer_modelo_comun
from derived_closure_inputs import _datum

SPECIES=['630-08-0','7732-18-5','124-38-9','1333-74-0']
NU=[-1,-1,1,1]


def author(owner='gas', record_potential=True, potential_kind='constitutive', species=None, nu=None, molar_masses=(.028,.018,.044,.002),
           reference=(2,2,0,0), temperature=800, pressure=1e5, extent_box=(.5,1.5), seed=1, liquid=None, state_width=.01, step_tolerance=1e-10):
    """Generic in species and one reaction row: the extent species is the last
    one with a nonzero coefficient and zero reference; a zero column is inert.

    liquid: None (ideal gas, F5-C1) or {'package': model id, 'anchor': 'gas'|'liquid',
    'form': 'activity'|'ideal'|'gas'} for a package liquid region (B3). The form
    is what the Model records for mu_i, so a wrong form is a negative control."""
    SPECIES_=list(species or SPECIES);NU_=list(nu or NU);count=len(SPECIES_)
    k=max(i for i,c in enumerate(NU_) if c!=0);assert reference[k]==0
    others=[j for j in range(count) if j!=k]
    model=thermal_source((owner,));v=model['volumenes'][0]
    model['id']='recorded-gas-reaction';model['componentes']=[{'id':i,'nombre':cas,'simbolo':'C'+str(i),'identidadQuimica':{'cas':cas}} for i,cas in enumerate(SPECIES_,1)]
    v['componenteIds']=list(range(1,count+1));v['balances']['energia']=False
    v['inicial']['cantidades']['datoIds']={str(i):_datum(model,'mass'+str(i),1,'kg','inicial') for i in range(1,count+1)}
    journal={'format':'rage.material-derivation','version':1,'volumes':{}}
    for action in ('start','integrate','total','impermeable_remainder','uniform_generation','uniform_consumption'):
        journal=material.edit_journal(journal,owner,{'kind':action})
    model['motores']['materialDerivation']=journal
    v['supuestos']['materia']=material.replay_volume(journal['volumes'][owner])[-1]
    a=SharedAuthor(model);q=a.quantity;t=sp.Symbol('t',real=True)
    def f(name):return sp.Function(name)(t)
    def declare(name,unit):a.append('declare_function',name=name,unit=unit,dependencies=[q(t)]);return f(name)
    b=[declare('conserved'+str(i),'mol') for i in range(count-1)]
    xi=declare('extent','mol');rate=declare('reactionRate','mol/s')
    a.append('declare_symbol',name='zeroReference',unit='mol')
    a.append('declare_symbol',name='virtualExtent',unit='mol')
    a.append('declare_symbol',name='gasConstant',unit='J/(mol*K)')
    masses=[f('m__'+owner+'__'+str(i)) for i in range(1,count+1)]
    amounts=[f('n_'+str(i)+'__'+owner) for i in range(1,count+1)]
    V=f('V__'+owner);balances=[];recon=[]
    for i,(mass,n,nu) in enumerate(zip(masses,amounts,NU_),1):
        a.append('declare_symbol',name='molarMass'+str(i),unit='kg/mol')
        M=sp.Symbol('molarMass'+str(i),real=True)
        relation=a.relation(q(mass),q(M)+'*'+q(n),'Define mass from molar amount and constant molar mass',kind='definition')
        current=next(k for k in a.selected if k.startswith('matter.'+owner+'.') and a.source.nodes[k].equation.lhs==sp.diff(mass,t))
        current=a.substitute(current,relation,mass)
        for stem,coefficient in [('g',max(nu,0)),('c',max(-nu,0))]:
            source=f(stem+'__'+owner+'__'+str(i))
            definition=a.relation(q(source),f'{coefficient}*{q(M)}*{q(rate)}/{q(V)}','Uniform stoichiometric source density in a closed region',kind='definition')
            current=a.substitute(current,definition,source)
        current=a.append('divide',sources=[current],right=q(M))
        balances.append(current)
    # Full left-nullspace coordinates, derived by actual combinations of the
    # fundamental component balances; no independent species is integrated.
    definitions=[];states=[]
    for j,left in enumerate(others):
        c=sp.Rational(-NU_[left],NU_[k])  # b_j = n_left + c n_k; c = 0 for an inert
        if c==0:
            relation=a.relation(q(b[j]),q(amounts[left]),'Conserved coordinate of a species absent from every reaction',kind='definition')
            combined=balances[left]
        else:
            sign='+' if c>0 else '-';term=q(amounts[k]) if abs(c)==1 else str(abs(c))+'*'+q(amounts[k])
            relation=a.relation(q(b[j]),q(amounts[left])+sign+term,'Conserved left-nullspace coordinate of stoichiometry',kind='definition')
            rhs=balances[k] if c==1 else a.append('multiply',sources=[balances[k]],right=str(c))
            combined=a.append('combine',sources=[balances[left],rhs])
        definitions.append(relation)
        differentiated=a.append('differentiate',sources=[relation],symbol=q(t))
        zeroed=a.substitute(differentiated,combined,sp.diff(amounts[left],t))
        states.append({'quantityId':q(b[j]),'equationId':zeroed})
    # Extent definition and oriented coordinate reconstructions.
    ext=a.relation(q(amounts[k]),q(xi) if NU_[k]==1 else str(NU_[k])+'*'+q(xi),'Extent coordinate with zero fourth reference amount' if NU_[k]==1 else 'Extent coordinate of the species with zero reference amount',kind='definition')
    a.append('differentiate',sources=[ext],symbol=q(t))
    a.relation(q(rate),q(sp.diff(xi,t)),'Define integrated reaction rate as the time derivative of extent',kind='definition')
    recon.append({'quantityId':q(amounts[k]),'equationId':ext})
    for left,relation in zip(others,definitions):
        replaced=a.substitute(relation,ext,amounts[k]) if NU_[left]!=0 else relation
        isolated=a.append('isolate',sources=[replaced],symbol=q(amounts[left]))
        recon.append({'quantityId':q(amounts[left]),'equationId':isolated})
    # Fundamental U -> H -> G is already derived by the common thermo graph.
    current='thermodynamics.'+owner+'.dG'
    for name,reason in [('T','Isothermal virtual composition variation'),('P','Isobaric virtual composition variation'),('G','Stationary Gibbs energy at interior chemical equilibrium')]:
        current=a.append('state_variation',family='thermodynamics',sources=[current],symbol=q(f(name+'__'+owner)),right='0',reason=reason)
    for n,nu in zip(amounts,NU_):
        current=a.append('state_variation',family='thermodynamics',sources=[current],symbol=q(n),right=str(nu)+'*virtualExtent',reason='Stoichiometric virtual composition direction; formation reference is included in chemical potentials')
    a.append('declare_domain',family='thermodynamics',sources=[current],symbol='virtualExtent',domain='nonzero',reason='Nonzero virtual stoichiometric displacement for the stationary Gibbs variation')
    current=a.append('divide',family='thermodynamics',sources=[current],right='virtualExtent*gasConstant*'+q(f('T__'+owner)))
    if record_potential and liquid is not None:
        # Liquid package region (B3): mu_i = mu_i*(T,P) + R T log(x_i gamma_i),
        # x_i = n_i/sum_k n_k over every species (inerts included). The
        # pure-liquid standard potential and the activity coefficient are
        # functions of the state named by the declaration's package.
        T,P=q(f('T__'+owner)),q(f('P__'+owner));total='('+'+'.join(q(n) for n in amounts)+')'
        if liquid['form']=='gas':a.append('declare_symbol',name='standardPressure',unit='Pa')
        for i,n in enumerate(amounts,1):
            if NU_[i-1]==0:continue
            standard=declare('pureLiquidPotential'+str(i),'J/mol')
            mu=f('mu_'+str(i)+'__'+owner)
            if liquid['form']=='activity':
                gamma=declare('activityCoefficient'+str(i),'1')
                argument=q(n)+'*'+q(gamma)+'/'+total
            elif liquid['form']=='ideal':
                argument=q(n)+'/'+total
            else:
                argument=q(n)+'*'+P+'/('+total+'*standardPressure)'
            relation=a.relation(q(mu),q(standard)+'+gasConstant*'+T+'*log('+argument+')',
                'Liquid mixture chemical potential: pure-liquid standard potential at the system T and P, mole fraction and activity coefficient of the declared package liquid model',
                family='thermodynamics',kind=potential_kind)
            current=a.substitute(current,relation,mu,family='thermodynamics')
    elif record_potential:
        # Thermodynamic constitutive closure selected by the declaration
        # (ideal_gas, gas anchor, ideal_gas_P0): one generic row per species,
        # substituted into the affinity through the shared operations.
        a.append('declare_symbol',name='standardPressure',unit='Pa')
        T,P=q(f('T__'+owner)),q(f('P__'+owner));total='('+'+'.join(q(n) for n in amounts)+')'
        # Only species in some reaction appear in the affinity (an inert has
        # mu_inert * 0); their potentials are the ones substituted.
        for i,n in enumerate(amounts,1):
            if NU_[i-1]==0:continue
            standard=declare('standardPotential'+str(i),'J/mol')
            mu=f('mu_'+str(i)+'__'+owner)
            relation=a.relation(q(mu),q(standard)+'+gasConstant*'+T+'*log('+q(n)+'*'+P+'/('+total+'*standardPressure))',
                'Ideal-gas mixture chemical potential at the standard pressure; formation-anchored standard potential',
                family='thermodynamics',kind=potential_kind)
            current=a.substitute(current,relation,mu,family='thermodynamics')
    model['motores']['equationWorkbench']=a.definition
    entry={'provider':'ideal_gas','species':SPECIES_,'phaseId':'vapor','standardState':'ideal_gas_P0','anchor':'gas',
           'temperatureId':q(f('T__'+owner)),'pressureId':q(f('P__'+owner)),
           'amountIds':[q(n) for n in amounts],'referenceIds':[q(b[others.index(i)]) if i!=k else 'zeroReference' for i in range(count)],
           'extentIds':[q(xi)],'reactions':[{'id':'shift','stoichiometry':[str(nu) for nu in NU_],'equationId':current}]}
    if liquid is not None:
        model['termodinamica']['paquetes']=[{'id':'reactionLiquid','modelo':{'id':liquid['package'],'version':'1'}}]
        entry.update({'provider':'package','phaseId':'liquido','standardState':'pure_liquid_TP','anchor':liquid['anchor'],'packageId':'reactionLiquid'})
    model['motores']['equilibriumReactions']={'format':'rage.equilibrium-reactions','version':1,'volumes':{owner:entry}}
    def datum(key,value,unit):return _datum(model,key,value,unit)
    parameters={q(f('T__'+owner)):datum('temperature',temperature,'K'),q(f('P__'+owner)):datum('pressure',pressure,'Pa'),
                'zeroReference':datum('zero',0,'mol'),'gasConstant':datum('R',8.314462618,'J/(mol*K)')}
    if record_potential and (liquid is None or liquid['form']=='gas'):parameters['standardPressure']=datum('P0',1e5,'Pa')
    parameters.update({'molarMass'+str(i):datum('M'+str(i),mass,'kg/mol') for i,mass in enumerate(molar_masses,1)})
    parameters[q(V)]=v['frontera']['datoId']
    initial={q(x):datum('initial'+str(i),value,'mol') for i,(x,value) in enumerate(zip(b,[reference[j] for j in others]))}
    bounds={q(x):{key:datum('b'+str(i)+key,value,'mol') for key,value in [('lowerDataId',base-state_width),('upperDataId',base+state_width)]} for i,(x,base) in enumerate(zip(b,[reference[j] for j in others]))}
    extent={key:datum('extent'+key,value,'mol') for key,value in [('seedDataId',seed),('lowerDataId',extent_box[0]),('upperDataId',extent_box[1]),('scaleDataId',1)]}
    model['estudio']={'tipo':'temporal','tiempoId':datum('tf',1,'s'),'muestras':3,'metodoSolicitado':'bdf','rtol':1e-7,'atol':{'cantidad':1e-9,'energia':1e-6}}
    model['motores']['derivedExecution']={'format':'rage.derived-execution','version':4,'sourceSignature':source_signature(model),
        'timeId':q(t),'states':states,'algebraic':[{'quantityId':q(xi),'equationId':current}], 'reconstructions':recon,
        'parameters':parameters,'initialValues':initial,'initialEquations':[],'checks':[],
        'nonlinear':{'variables':{q(xi):extent},'residualScales':{current:datum('affinityScale',1,'1')},'residualTolerance':1e-10,'stepTolerance':step_tolerance,'maxIterations':30,'maxBacktracks':20},
        'dae':{'stateBounds':bounds,'driftTolerance':1e-9}}
    return leer_modelo_comun(model)
