"""Continuous liquid esterification from recorded mass, energy and momentum laws.

Concentration kinetics retain the Demo 0.1 detailed-balance calibration and its
composition/temperature limitations. Version 2 uses the actual dynamic liquid
control volume in both concentrations and integrated reaction sources.
"""
import copy
import json
import sys
from pathlib import Path

import numpy as np
import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tests'))

from core.balances import material_derivation as material, energy_derivation as energy
from core.modelo.operation_journal import replay
from core.modelo.equation_workbench import build
from core.mathematics.dimensions import catalog
from core.compilador.derived import source_signature
from derived_closure_inputs import T, _datum
from derived_reactor_inputs import reactor_model, SPECIES, OWNER
from derived_momentum_inputs import author_outlet, select_outlet, PIPE
from demo01_reactor import DEMO as BATCH, detailed_balance
from demo02_drum import MATERIAL

DEMO = dict(BATCH, feed=1e-3, TF=320., PF=101325., zF=(.5,.5,0.,0.),
            area=.003, pipeArea=1e-6, length=5., loss=8., floor=0.,
            Pout=101325., F0=1e-3, g=9.80665, vent=0., Q=0., tf=60000.)
FIXTURE = ROOT / 'frontend/testing/demo02/continuousReactor.ts'


def demo_data():
    balance = detailed_balance(DEMO)
    return dict(DEMO, kr=balance['kr'], Er=balance['Er'])


def continuous_source(data):
    model = reactor_model(data)
    volume = model['volumenes'][0]
    journal = {'format':'rage.material-derivation','version':1,'volumes':{}}
    for action in ('start','integrate','total','impermeable_remainder','uniform_generation','uniform_consumption'):
        journal = material.edit_journal(journal,OWNER,{'kind':action})
    model['motores']['materialDerivation'] = journal
    volume['supuestos']['materia'] = material.replay_volume(journal['volumes'][OWNER])[-1]
    ej = {'format':'rage.energy-derivation','version':1,'volumes':{}}
    for action in ('start','pressure_stress','no_kinetic','no_viscous_work','no_body_work','no_volume_source',
                   'integrate','reynolds','total','enthalpy','uniform_state','uniform_pressure','prescribed_pressure'):
        ej = energy.edit_journal(ej,OWNER,{'kind':action})
    model['motores']['energyDerivation'] = ej
    from core.termodinamica import derivation as thermo
    tj = model['motores']['thermodynamicDerivation']
    es = replay(ej['volumes'][OWNER],energy.fundamental,energy.normalize)[-1]
    ts = replay(tj['volumes'][OWNER],thermo.fundamental,thermo.normalize)[-1]
    volume['supuestos']['energia'] = {**es,**{k:v for k,v in ts.items() if k!='closure'}}
    volume['frontera'] = {'tipo':'presion_prescrita','presionId':OWNER+'.pressure'}
    from core.mezclas_datos import especie
    mass_ids = {}
    for i,(n,cas) in enumerate(zip(data['n0'],SPECIES),1):
        mass_ids[str(i)] = _datum(model,OWNER+('.mass' if i==1 else '.mass'+str(i)),n*especie(cas).M,'kg','inicial')
    volume['inicial']['cantidades'] = {'base':'masica','datoIds':mass_ids}
    config = model['motores']['kineticReactions']
    config['version'] = 2
    config['volumes'][OWNER].pop('volumeDataId')
    config['volumes'][OWNER]['volumeSource'] = {'kind':'control_volume'}
    _datum(model,'feed.T',data['TF'],'K','frontera')
    _datum(model,'feed.P',data['PF'],'Pa','frontera')
    model['corrientes'] = []
    for name in ('feed','liquid'):
        stream = {'id':name,'desde':None if name=='feed' else OWNER,'hasta':OWNER if name=='feed' else None,
            'componenteIds':[1,2,3,4],'mecanismo':'convectivo','constante':False,
            'materia':{'modo':'por_componente','base':'masica','caudalIds':{}}}
        if name=='feed':
            stream['estadoExterior'] = {'temperaturaId':'feed.T','presion':{'tipo':'dato','datoId':'feed.P'},
                'composicion':{'base':'molar','fracciones':{str(i):z for i,z in enumerate(data['zF'],1)}}}
        else:
            stream['extraccion'] = {OWNER:{'tipo':'fase','fase':'liquido'}}
        model['corrientes'].append(stream)
    return model


def jacket(author, owner):
    for name,unit in [('jacketConductance','W/K'),('jacketTemperature','K')]:
        author.append('declare_symbol',family='energy',name=name,unit=unit)
    return author.relation(author.quantity(sp.Function('energy_heat_rate__'+owner)(T)),
        'jacketConductance*(jacketTemperature-'+author.quantity(sp.Function('T__'+owner)(T))+')',
        'Uniform external thermal reservoir with a declared overall heat-transfer conductance','energy','constitutive')


def prepare(model, data):
    model['volumenes'][0]['terminos'] = {'calor':_datum(model,'jacket.initialHeat',data['UA']*(data['Tj']-data['T0']),'W','inicial')}
    path = next(v for v in model['volumenes'] if v['id']==PIPE)
    path['termodinamica']['motivo'] = 'The path transports the drawn liquid phase without separate storage or a separate thermodynamic closure.'
    next(s for s in model['corrientes'] if s['id']=='discharge')['extraccion'] = {PIPE:{'tipo':'fase','fase':'liquido'}}


def template():
    return {'format':'rage.model-template','version':1,'id':'demo-02-cstr','templateVersion':'1','equipment':True,
        'recipe':{'journals':['materialDerivation','energyDerivation','momentumDerivation','thermodynamicDerivation','equationWorkbench']},
        'ports':[
            {'id':'feed','volumeId':OWNER,'direction':'inlet','kind':'material','boundary':{'type':'stream','id':'feed'},'exteriorState':'estadoExterior','variables':copy.deepcopy(MATERIAL)},
            {'id':'product','volumeId':PIPE,'direction':'outlet','kind':'material','boundary':{'type':'stream','id':'discharge'},'donorPhase':'liquido','variables':copy.deepcopy(MATERIAL)},
            {'id':'jacket','volumeId':OWNER,'direction':'inlet','kind':'heat','boundary':{'type':'term','id':'calor'},'variables':{'power':{'unitSI':'W'}}}]}


def author_demo_cstr(data=None, method='bdf'):
    data = demo_data() if data is None else data
    author,out = author_outlet(data,prepare=lambda model:prepare(model,data),source_factory=continuous_source,
                              owner=OWNER,vapour=False,heat_builder=jacket,reactive=True)
    for i in (1,2,3,4):
        out[f'reactionAmount.{i}'] = author.append('isolate',sources=[f'reaction.{OWNER}.amount.{i}'],
            symbol=author.quantity(sp.Function(f'amount_{i}__{OWNER}')(T)))
    author.model['template'] = template()
    model = select_outlet(author,out,data,method,owner=OWNER)
    replayed = build(model)
    quantities = {**catalog(replayed.graph,replayed.units),**replayed.introduced}
    selection = model['motores']['derivedExecution']
    for symbol,key,value,unit in [('jacketConductance','jacket.UA',data['UA'],'W/K'),('jacketTemperature','jacket.T',data['Tj'],'K')]:
        qid = next(k for k,v in quantities.items() if v==replayed.introduced[symbol])
        selection['parameters'][qid] = _datum(model,key,value,unit)
    model.update(id='demo-0.2-continuous-reactor',nombre='Demo 0.2 · Continuous jacketed liquid reactor with outlet momentum')
    selection['sourceSignature'] = source_signature(model,replayed)
    return model,out


def frozen_model():
    text = FIXTURE.read_text(encoding='utf-8')
    return json.loads(text[text.index(' = ')+3:text.rindex(';')])


def train_model(source, count):
    model = copy.deepcopy(source)
    model.update(id='demo-0.2-reactor-train',nombre='Demo 0.2 · Indexed continuous liquid reactor train')
    _datum(model,'solve.stageCount',count,'1','estudio')
    model['indexSet'] = {'format':'rage.index-set','version':1,'id':'reactorTrain','index':'j',
        'countDataId':'solve.stageCount','templates':{'generic':copy.deepcopy(source)},'genericStage':'generic','variants':[],
        'connections':[{'outlet':'product','inlet':'feed','offset':1}],
        'exposures':[{'id':'feed','port':'feed','at':'first'},{'id':'product','port':'product','at':'last'},
                     {'id':'jacket','port':'jacket','at':'each'}]}
    return model


def reference_functions(data=None):
    """Independent liquid caloric route: chemical potentials and a T difference.

    No compiled expression, closure bridge or model RHS is used. Formation
    energy enters H once, as in the independent Demo 0.1 reference.
    """
    from core import mezclas
    from core.reactions.chemical_equilibrium import PackagePhase
    from derived_closure_inputs import PACKAGE_ID
    from scipy.optimize import brentq
    data = demo_data() if data is None else data
    phase = PackagePhase(mezclas.Sistema(PACKAGE_ID,list(SPECIES),solo_liquido=True),'liquido',anchor='liquid')
    masses = np.asarray(phase.sistema.M,dtype=float)
    molar_volumes = np.asarray([e.vL for e in phase.sistema.esp])

    def enthalpy(temperature, amounts):
        amounts = np.asarray(amounts)
        present = amounts>0
        trace = np.where(present,amounts,1e-30)
        delta = 1e-3
        mu = phase.mu(temperature,data['P'],trace)
        derivative = (phase.mu(temperature+delta,data['P'],trace)-phase.mu(temperature-delta,data['P'],trace))/(2*delta)
        return float(amounts[present] @ (mu-temperature*derivative)[present])

    def temperature(inventory, amounts):
        low,high = phase.sistema.T_rango
        return brentq(lambda t:enthalpy(t,amounts)-inventory,low+.002,high-.002,xtol=1e-10)
    temperature.bounds = (phase.sistema.T_rango[0]+.002,phase.sistema.T_rango[1]-.002)

    def rate(temperature, amounts):
        volume = float(np.asarray(amounts) @ molar_volumes)
        concentration = np.asarray(amounts)/volume
        arrhenius = lambda e:np.exp(-e/8.31446261815324*(1/temperature-1/data['Tref']))
        return (data['kf']*arrhenius(data['E'])*concentration[0]*concentration[1]
                -data['kr']*arrhenius(data['Er'])*concentration[2]*concentration[3])*volume

    return data,masses,molar_volumes,enthalpy,temperature,rate


def reference_train(times, count=1, data=None):
    """Independent DOP853 for a cascade of the same physical control volume."""
    from scipy.integrate import solve_ivp
    data,masses,volumes,enthalpy,temperature,rate = reference_functions(data)
    feed = np.asarray(data['zF']);feed_mass = float(feed@masses)
    feed_molar = data['feed']*feed/feed_mass
    feed_energy = data['feed']*enthalpy(data['TF'],feed)/feed_mass
    nu = np.array([-1.,-1.,1.,1.])
    def rhs(time, values):
        inlet,inlet_energy = feed_molar,feed_energy
        derivatives = []
        for row in np.asarray(values).reshape(count,6):
            n,H,flow = row[:4],row[4],row[5]
            mass = float(n@masses);volume = float(n@volumes);rho = mass/volume
            temp = temperature(H,n)
            outlet = flow*n/mass;outlet_energy = flow*H/mass
            pressure = data['P']+mass*data['g']/data['area']
            loss = data['loss']*flow*abs(flow)/(2*rho*data['pipeArea']**2)
            derivatives.extend([*(inlet-outlet+nu*rate(temp,n)),
                inlet_energy-outlet_energy+data['UA']*(data['Tj']-temp),
                data['pipeArea']/data['length']*(pressure-data['Pout']-loss)])
            inlet,inlet_energy = outlet,outlet_energy
        return derivatives
    initial = [*data['n0'],enthalpy(data['T0'],data['n0']),data['F0']]*count
    solution = solve_ivp(rhs,(0,float(times[-1])),initial,method='DOP853',t_eval=times,
        rtol=2e-10,atol=[1e-11]*4+[1e-6,1e-12] if count==1 else ([1e-11]*4+[1e-6,1e-12])*count)
    return solution,np.asarray([[temperature(row[4],row[:4]) for row in y.reshape(count,6)] for y in solution.y.T])


def sequential_steady_reference(count, data=None):
    """Independent scalar reaction/energy balances, solved stage by stage.

    The equal reactant feed and equimolar stoichiometry preserve the mean molar
    mass. Momentum sets each holdup; no compiled steady residual is reused.
    """
    from scipy.optimize import brentq
    data,masses,volumes,enthalpy,temperature,rate = reference_functions(data)
    incoming = np.asarray(data['zF']);flow = data['feed']
    molar_mass = float(incoming@masses)
    incoming_h = enthalpy(data['TF'],incoming)/molar_mass
    rows = []
    for _ in range(count):
        def state(conversion):
            composition = np.asarray([(1-conversion)/2]*2+[conversion/2]*2)
            rho = molar_mass/float(composition@volumes)
            mass = data['area']/data['g']*(data['Pout']-data['P']+
                data['loss']*flow**2/(2*rho*data['pipeArea']**2))
            amounts = mass*composition/molar_mass
            temp = brentq(lambda t:flow*(incoming_h-enthalpy(t,composition)/molar_mass)+data['UA']*(data['Tj']-t),
                          *temperature.bounds,xtol=1e-9)
            return amounts,temp
        def balance(conversion):
            amounts,temp = state(conversion)
            return flow/molar_mass*(incoming[0]-(1-conversion)/2)-rate(temp,amounts)
        conversion = brentq(balance,1-2*incoming[0],1-1e-10,xtol=1e-11)
        amounts,temp = state(conversion)
        inventory = enthalpy(temp,amounts)
        rows.append({'conversion':conversion,'temperature':temp,'amounts':amounts,'enthalpy':inventory,'flow':flow})
        incoming = amounts/sum(amounts)
        incoming_h = inventory/float(amounts@masses)
    return rows


def plug_flow_reference(count, data=None):
    """Independent ideal differential-contact limit, reference only.

    The coordinate measures copies of the same local holdup/thermal-contact
    specification. This is not a spatial Model implementation or a second
    production deduction. Increasing n also increases total contact/holdup.
    """
    from scipy.integrate import solve_ivp
    from scipy.optimize import brentq
    data,masses,volumes,enthalpy,temperature,rate = reference_functions(data)
    feed=np.asarray(data['zF']);mean_mass=float(feed@masses);flow=data['feed']
    def rhs(coordinate,values):
        conversion,specific_h=values
        composition=np.array([(1-conversion)/2]*2+[conversion/2]*2)
        temp=brentq(lambda t:enthalpy(t,composition)/mean_mass-specific_h,*temperature.bounds,xtol=1e-9)
        density=mean_mass/float(composition@volumes)
        mass=data['area']/data['g']*(data['Pout']-data['P']+data['loss']*flow**2/(2*density*data['pipeArea']**2))
        amounts=mass*composition/mean_mass
        return [2*rate(temp,amounts)*mean_mass/flow,data['UA']*(data['Tj']-temp)/flow]
    result=solve_ivp(rhs,(0,count),[0.,enthalpy(data['TF'],feed)/mean_mass],method='DOP853',rtol=1e-10,atol=[1e-12,1e-5])
    if not result.success:raise RuntimeError(result.message)
    return float(result.y[0,-1])


if __name__=='__main__':
    model,_ = author_demo_cstr()
    text = '/** Generated by tests/demo02_cstr.py --write through shared recorded operations. */\nexport const DEMO02_CSTR = '+json.dumps(model,indent=1,ensure_ascii=False,sort_keys=True)+';\n'
    if '--write' in sys.argv:
        FIXTURE.write_text(text,encoding='utf-8',newline='\n')
    else:
        sys.stdout.buffer.write(text.encode('utf-8'))
