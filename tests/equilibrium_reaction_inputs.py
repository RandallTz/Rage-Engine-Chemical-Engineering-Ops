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


def author(owner='gas'):
    model=thermal_source((owner,));v=model['volumenes'][0]
    model['id']='recorded-gas-reaction';model['componentes']=[{'id':i,'nombre':cas,'simbolo':'C'+str(i),'identidadQuimica':{'cas':cas}} for i,cas in enumerate(SPECIES,1)]
    v['componenteIds']=[1,2,3,4];v['balances']['energia']=False
    v['inicial']['cantidades']['datoIds']={str(i):_datum(model,'mass'+str(i),1,'kg','inicial') for i in range(1,5)}
    journal={'format':'rage.material-derivation','version':1,'volumes':{}}
    for action in ('start','integrate','total','impermeable_remainder','uniform_generation','uniform_consumption'):
        journal=material.edit_journal(journal,owner,{'kind':action})
    model['motores']['materialDerivation']=journal
    v['supuestos']['materia']=material.replay_volume(journal['volumes'][owner])[-1]
    a=SharedAuthor(model);q=a.quantity;t=sp.Symbol('t',real=True)
    def f(name):return sp.Function(name)(t)
    def declare(name,unit):a.append('declare_function',name=name,unit=unit,dependencies=[q(t)]);return f(name)
    b=[declare('conserved'+str(i),'mol') for i in range(3)]
    xi=declare('extent','mol');rate=declare('reactionRate','mol/s')
    a.append('declare_symbol',name='zeroReference',unit='mol')
    a.append('declare_symbol',name='virtualExtent',unit='mol')
    a.append('declare_symbol',name='gasConstant',unit='J/(mol*K)')
    masses=[f('m__'+owner+'__'+str(i)) for i in range(1,5)]
    amounts=[f('n_'+str(i)+'__'+owner) for i in range(1,5)]
    V=f('V__'+owner);balances=[];recon=[]
    for i,(mass,n,nu) in enumerate(zip(masses,amounts,NU),1):
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
    for j,(left,sign) in enumerate([(0,1),(1,1),(2,-1)]):
        relation=a.relation(q(b[j]),q(amounts[left])+('+' if sign==1 else '-')+q(amounts[3]),'Conserved left-nullspace coordinate of stoichiometry',kind='definition')
        definitions.append(relation)
        rhs=balances[3] if sign==1 else a.append('multiply',sources=[balances[3]],right='-1')
        combined=a.append('combine',sources=[balances[left],rhs])
        differentiated=a.append('differentiate',sources=[relation],symbol=q(t))
        zeroed=a.substitute(differentiated,combined,sp.diff(amounts[left],t))
        states.append({'quantityId':q(b[j]),'equationId':zeroed})
    # Extent definition and oriented coordinate reconstructions.
    ext=a.relation(q(amounts[3]),q(xi),'Extent coordinate with zero fourth reference amount',kind='definition')
    a.append('differentiate',sources=[ext],symbol=q(t))
    a.relation(q(rate),q(sp.diff(xi,t)),'Define integrated reaction rate as the time derivative of extent',kind='definition')
    recon.append({'quantityId':q(amounts[3]),'equationId':ext})
    for j,relation in enumerate(definitions):
        replaced=a.substitute(relation,ext,amounts[3]);isolated=a.append('isolate',sources=[replaced],symbol=q(amounts[j]))
        recon.append({'quantityId':q(amounts[j]),'equationId':isolated})
    # Fundamental U -> H -> G is already derived by the common thermo graph.
    current='thermodynamics.'+owner+'.dG'
    for name,reason in [('T','Isothermal virtual composition variation'),('P','Isobaric virtual composition variation'),('G','Stationary Gibbs energy at interior chemical equilibrium')]:
        current=a.append('state_variation',family='thermodynamics',sources=[current],symbol=q(f(name+'__'+owner)),right='0',reason=reason)
    for n,nu in zip(amounts,NU):
        current=a.append('state_variation',family='thermodynamics',sources=[current],symbol=q(n),right=str(nu)+'*virtualExtent',reason='Stoichiometric virtual composition direction; formation reference is included in chemical potentials')
    a.append('declare_domain',family='thermodynamics',sources=[current],symbol='virtualExtent',domain='nonzero',reason='Nonzero virtual stoichiometric displacement for the stationary Gibbs variation')
    current=a.append('divide',family='thermodynamics',sources=[current],right='virtualExtent*gasConstant*'+q(f('T__'+owner)))
    model['motores']['equationWorkbench']=a.definition
    entry={'provider':'ideal_gas','species':SPECIES,'phaseId':'vapor','standardState':'ideal_gas_P0','anchor':'gas',
           'temperatureId':q(f('T__'+owner)),'pressureId':q(f('P__'+owner)),
           'amountIds':[q(n) for n in amounts],'referenceIds':[q(x) for x in b]+['zeroReference'],
           'extentIds':[q(xi)],'reactions':[{'id':'shift','stoichiometry':[str(nu) for nu in NU],'equationId':current}]}
    model['motores']['equilibriumReactions']={'format':'rage.equilibrium-reactions','version':1,'volumes':{owner:entry}}
    def datum(key,value,unit):return _datum(model,key,value,unit)
    parameters={q(f('T__'+owner)):datum('temperature',800,'K'),q(f('P__'+owner)):datum('pressure',1e5,'Pa'),
                'zeroReference':datum('zero',0,'mol'),'gasConstant':datum('R',8.314462618,'J/(mol*K)')}
    parameters.update({'molarMass'+str(i):datum('M'+str(i),mass,'kg/mol') for i,mass in enumerate([.028,.018,.044,.002],1)})
    parameters[q(V)]=v['frontera']['datoId']
    initial={q(x):datum('initial'+str(i),value,'mol') for i,(x,value) in enumerate(zip(b,[2,2,0]))}
    bounds={q(x):{key:datum('b'+str(i)+key,value,'mol') for key,value in [('lowerDataId',base-.01),('upperDataId',base+.01)]} for i,(x,base) in enumerate(zip(b,[2,2,0]))}
    extent={key:datum('extent'+key,value,'mol') for key,value in [('seedDataId',1),('lowerDataId',.5),('upperDataId',1.5),('scaleDataId',1)]}
    model['estudio']={'tipo':'temporal','tiempoId':datum('tf',1,'s'),'muestras':3,'metodoSolicitado':'bdf','rtol':1e-7,'atol':{'cantidad':1e-9,'energia':1e-6}}
    model['motores']['derivedExecution']={'format':'rage.derived-execution','version':4,'sourceSignature':source_signature(model),
        'timeId':q(t),'states':states,'algebraic':[{'quantityId':q(xi),'equationId':current}], 'reconstructions':recon,
        'parameters':parameters,'initialValues':initial,'initialEquations':[],'checks':[],
        'nonlinear':{'variables':{q(xi):extent},'residualScales':{current:datum('affinityScale',1,'1')},'residualTolerance':1e-10,'stepTolerance':1e-10,'maxIterations':30,'maxBacktracks':20},
        'dae':{'stateBounds':bounds,'driftTolerance':1e-9}}
    return leer_modelo_comun(model)
