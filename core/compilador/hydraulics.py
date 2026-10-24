"""Compile replayed hydraulic paths and hydrostatic storage boundaries.

Only the declared constant-density, single-component, isothermal approximation
is admitted. This assembles shared incidence/force laws, never example names.
The existing RK45/BDF integrator and common results/units services are reused.
"""
import json
import math
from functools import lru_cache

import numpy as np

from core.balances.hydraulic_definition import read_definition, PATH_DATA, STORAGE_DATA
from core.balances import momentum_derivation as momentum
from core.balances.momentum_reductions import WALL_FLAGS,STORAGE_FLAGS,reduction_graphs
from core.modelo.operation_journal import JournalError, replay
from core.resultados import conjunto, eje, serie, evento
from core.solvers import integrar, Detencion
from core.unidades import compatibles


class AdmissionError(JournalError):
    """Located physical requirements, shared by inspection and compilation."""
    def __init__(self, diagnostics):
        self.diagnostics = diagnostics
        super().__init__('; '.join(f"{item['ownerId']} · {item['family']}: {item['message']}" for item in diagnostics))


def material_requirements(volume, path):
    state = volume['supuestos']['materia']; field = state['campo']
    checks = [
        (state['vista'] == 'cantidad', 'total_form', 'Reduce local conservation to a total control-volume balance.'),
        (not state.get('cantidadVolumen'), 'inventory', 'Retain mass inventory as the state; mean-density substitution is not admitted here.'),
        (state['fija'] == path, 'boundary', 'Declare a fixed boundary for this flow region.' if path else 'Retain the moving liquid inventory boundary.'),
        (state['restoImpermeable'], 'boundary_remainder', 'Close the remaining boundary to material transport.'),
        (not state['sinAcumulacion'] and not field['estacionario'], 'dynamic_inventory', 'Retain the dynamic material law.'),
        (field.get('sinReaccion') or field.get('sinGeneracion'), 'generation', 'Remove generation through a recorded assumption, or use a compiler that supports its law.'),
        (field.get('sinReaccion') or field.get('sinConsumo'), 'consumption', 'Remove consumption through a recorded assumption, or use a compiler that supports its law.'),
        (not volume.get('terminos'), 'unbound_terms', 'Resolve explicit source and boundary terms; this hydraulic specialization cannot ignore them.'),
    ]
    return [{'ownerId':volume['id'], 'family':'matter', 'code':code, 'message':message} for valid,code,message in checks if not valid]


@lru_cache(maxsize=1)
def scalar_functions():
    """Numerical functions from the same symbolic laws published in Model."""
    import sympy as sp
    s,relations,_=momentum.reduced_relations()
    wall=relations['laminarLoss'][1]
    rate=sp.solve(sp.Eq(*relations['inertance']),s['massFlowRate'])[0].subs(s['loss'],wall)
    drop=relations['pressureDrop'][1].subs(s['loss'],wall)
    geometry=[s[k] for k in ['L','A','rho','mu','drive','g','z1','z2']]
    return {
        'inertance':sp.lambdify((s['L'],s['A']),sp.diff(relations['inertance'][0],s['massFlowRate']),'math'),
        'resistance':sp.lambdify((s['L'],s['A'],s['rho'],s['mu']),sp.diff(wall,s['massFlow']),'math'),
        'rate':sp.lambdify((s['p1'],s['p2'],s['massFlow'],*geometry),rate,'math'),
        'drop':sp.lambdify((s['massFlow'],s['massFlowRate'],*geometry),drop,'math'),
    }


def configured(model):
    return model.get('motores',{}).get('hydraulicNetwork') is not None


def check_medium_domain(flow, rate, inlet_pressure, outlet_pressure, diameter, viscosity, minimum_pressure):
    """Shared validity monitor; it does not supply a momentum RHS."""
    reynolds = 4*abs(flow)/(math.pi*diameter*viscosity)
    if not all(math.isfinite(v) for v in [flow, rate, inlet_pressure, outlet_pressure]) or min(inlet_pressure, outlet_pressure) < minimum_pressure:
        raise Detencion('pressure_domain', 'A static pressure left the declared medium validity domain.')
    if reynolds > 2100:
        raise Detencion('laminar_domain', 'Reynolds number left the admitted laminar wall-closure domain; turbulence is not inferred.')
    return reynolds


def validate_admission(model):
    definition=read_definition(model['motores']['hydraulicNetwork'],model)
    momentum.validate_model_journal(model)
    from core.balances.material_derivation import validate_model_journal as validate_material
    from core.termodinamica.derivation import validate_model_journal as validate_state
    validate_material(model);validate_state(model)
    if len(model['componentes'])!=1 or model['intercambios'] or model.get('matematico') is not None or model['motores'].get('adimensionalizacion'):
        raise JournalError('Reduced hydraulics currently admits one declared component, no heat links, explicit equation override or scaling selection.')
    owners={v['id']:v for v in model['volumenes']}
    issues = [issue for path in (True, False) for entity in definition['paths' if path else 'storages'] for issue in material_requirements(owners[entity['volumeId']], path)]
    if issues: raise AdmissionError(issues)
    journals=model['motores'].get('momentumDerivation',{}).get('volumes',{})
    path_required={'pressureStress','newtonian','massContinuity','constantViscosity','divergenceFree','fixedBoundary','uniformSections','constantArea','referenceDensity','uniformGravity','impermeableWall',*WALL_FLAGS}
    storage_required={'pressureStress','negligibleConvection','negligibleViscousStress','zeroLocalAccumulation','referenceDensity','uniformGravity',*STORAGE_FLAGS}
    issues = []
    for entity in definition['paths']+definition['storages']:
        owner=entity['volumeId'];volume=owners[owner];entry=journals.get(owner)
        def require(valid, family, code, message):
            if not valid: issues.append({'ownerId': owner, 'family': family, 'code': code, 'message': message})
        if entry is None:
            require(False, 'momentum', 'fundamental_history', 'Record the Cauchy reduction in this region; geometry bindings do not provide its equations.')
            continue
        state=replay(entry,momentum.fundamental,momentum.normalize)[-1]
        path=entity in definition['paths'];required=path_required if path else storage_required
        allowed=required if path else required|{'expandCartesian','newtonian','constantViscosity','massContinuity','divergenceFree','uniformGravity'}
        missing=sorted(k for k in required if not state[k])
        for key in missing:
            require(False, 'momentum', key, 'Missing recorded assumption: '+momentum.CONTROL_LABELS.get(key, ('', key))[1]+'.')
        require(not any(state[k] for k in momentum.FLAGS if k not in allowed) and state['form']==('hydraulic' if path else 'local'), 'momentum', 'retained_terms', 'This reduction is outside the admitted hydraulic or hydrostatic scope. Retained terms cannot be ignored.')
        require(volume['balances']['momento'] and not volume['balances']['energia'] and volume['balances']['materia']==(not path), 'momentum', 'balance_ownership', 'Each path retains momentum and fixed full-path mass compatibility; each storage retains matter plus hydrostatic momentum. Energy is externally isothermal, not integrated.')
        thermo=volume['supuestos']['energia'] or {}
        require(volume['termodinamica']['tipo']=='supuesto' and all(thermo.get(k) for k in ['monofasico','sinCambioFase','densidadConstante']), 'thermodynamics', 'medium', 'Declare the single-phase, no-phase-change, constant-density medium through Thermodynamics; no equilibrium package is silently replaced.')
        if path and (state['inletStreamId']!=entity['inletStreamId'] or state['outletStreamId']!=entity['outletStreamId']):
            raise JournalError('The compiled path must use the same ports as its recorded momentum deduction.')
        if volume['inicial'].get('cantidades',{}).get('base')!='masica':raise JournalError('This hydraulic increment uses explicit mass inventories in SI.')
    if issues: raise AdmissionError(issues)
    # Hydraulic unknowns cannot coexist with an independent flow specification.
    for stream in model['corrientes']:
        mat=stream['materia']
        if mat['modo']!='por_componente' or mat['base']!='masica' or mat['caudalIds'] or stream.get('estadoExterior') or stream.get('extraccion'):
            raise JournalError('Hydraulic streams take their flow from the bound momentum role; remove independent stream-flow/phase-extraction specifications explicitly.')
    return definition


class HydraulicSystem:
    def __init__(self,model):
        from .compilador import _Dato, NoSoportado
        self.model=model;self.definition=validate_admission(model);self.fields=[];self.rows=[]
        self.data_fields={};self.parameters={}
        def datum(id_,unit,label,variable=False):
            if id_ not in model['datos']:raise NoSoportado('Missing hydraulic datum: '+id_)
            source=model['datos'][id_]
            if not compatibles(source['declaracion']['unidad'],unit):raise NoSoportado(f'{id_}: expected dimension {unit}.')
            value=_Dato(source,id_)
            if not variable and value.derivada is not None:raise NoSoportado(f'{id_}: this geometric/property approximation must be constant in time.')
            if not math.isfinite(value(0)):raise NoSoportado('Nonfinite datum: '+id_)
            self.data_fields[id_]={'id':id_,'label':label,'unit':unit,'role':'time_function' if variable else 'constant'}
            if not variable:self.parameters[id_]=(value(0),unit)
            return value if variable else value(0)
        self.datum=datum;d=self.definition;medium=d['medium']
        self.rho=datum(medium['densityId'],'kg/m3','Reference density')
        self.mu=datum(medium['viscosityId'],'Pa*s','Dynamic viscosity')
        self.temperature=datum(medium['temperatureId'],'K','Externally maintained temperature')
        self.pmin=datum(medium['minimumPressureId'],'Pa','Minimum valid absolute pressure')
        self.g=datum(d['gravityId'],'m/s2','Gravity magnitude')
        if min(self.rho,self.mu,self.temperature,self.pmin,self.g)<=0:raise NoSoportado('Medium values and gravity must be positive.')
        self.storages={};self.paths=[];self.y0=[]
        volumes={v['id']:v for v in model['volumenes']};component=str(model['componentes'][0]['id'])
        def state(id_,label,unit,initial,diagnostic=False):
            index=len(self.y0);self.y0.append(float(initial));self.fields.append({'id':id_,'label':label,'unit':unit,'index':index,'diagnostic':diagnostic});return index
        for storage in d['storages']:
            owner=storage['volumeId'];area=datum(storage['areaId'],'m2',owner+' · free-surface area')
            p=datum(storage['surfacePressureId'],'Pa',owner+' · surface absolute pressure',True)
            z=datum(storage['floorElevationId'],'m',owner+' · floor elevation')
            initial=datum(volumes[owner]['inicial']['cantidades']['datoIds'][component],'kg',owner+' · initial inventory')
            if area<=0 or initial<=0:raise NoSoportado('Storage area and initial inventory must be positive.')
            index=state('volume.'+owner+'.mass',owner+' · mass inventory','kg',initial)
            journal=model['motores']['momentumDerivation']['volumes'][owner]
            effective=replay(journal,momentum.fundamental,momentum.normalize)[-1]
            _,_,graph,relations=reduction_graphs(effective)
            import sympy as sp
            s,_,_=momentum.reduced_relations()
            port_z,surface_z,floor_z,height,section,mass,surface_p=relations['symbols']
            pressure_function=sp.lambdify((mass,section,s['rho'],s['g'],floor_z,port_z,surface_p),relations['pressure'].rhs,'math')
            height_function=sp.lambdify((mass,section,s['rho']),relations['height'].rhs,'math')
            self.storages[owner]={'index':index,'area':area,'surface':p,'floor':z,'pressure':pressure_function,'height':height_function}
            from core.balances.material_equations import equation_graph
            material,final,bindings=equation_graph(model,owner,volumes[owner]['supuestos']['materia'])
            balance_id=next(id_ for id_ in final if material.nodes[id_].kind=='balance' and not material.nodes[id_].dependent)
            conservation=material.nodes[balance_id].equation
            unknown=next(q for q,binding in bindings.items() if binding[0]=='inventory')
            derivative=sp.diff(unknown,sp.Symbol('t',real=True))
            rates=sp.solve(conservation,derivative)
            if len(rates)!=1:raise NoSoportado('The derived material graph does not determine an explicit inventory rate.')
            self.storages[owner]['materialGraph']=(rates[0],bindings)
            self.rows.append({'id':balance_id,'family':'Matter','latex':next(row['latex'] for row in material.rows() if row['id']==balance_id)})
            self.rows.extend({'id':owner+'.'+row['id'],'family':row['family'].title(),'latex':row['latex']} for row in graph.rows() if row['id'] in ('storage.port-pressure','storage.inventory-integral','storage.height'))
        for path in d['paths']:
            owner=path['volumeId'];values={k:datum(path[k],unit,owner+' · '+k.removesuffix('Id')) for k,unit in PATH_DATA.items()}
            L,A,D=values['lengthId'],values['areaId'],values['diameterId']
            if min(L,A,D)<=0 or not math.isclose(A,math.pi*D*D/4,rel_tol=1e-8):raise NoSoportado('The declared circular diameter and area must agree, with positive dimensions.')
            expected_mass=self.rho*A*L
            declared_mass=datum(volumes[owner]['inicial']['cantidades']['datoIds'][component],'kg',owner+' · full-path mass')
            if not math.isclose(expected_mass,declared_mass,rel_tol=1e-8):raise NoSoportado('Fixed full-path inventory must agree with density and geometry.')
            laws=scalar_functions()
            item={**path,**values,'inertance':laws['inertance'](L,A),'resistance':laws['resistance'](L,A,self.rho,self.mu),'initialMass':declared_mass}
            item['lawArguments']=(L,A,self.rho,self.mu,values['driveId'],self.g,values['inletElevationId'],values['outletElevationId'])
            if path['flow']['kind']=='dynamic':
                initial=datum(path['flow']['initialId'],'kg/s',owner+' · initial mass flow')
                item['index']=state('path.'+owner+'.flow',owner+' · mass flow','kg/s',initial)
            else:
                item['imposed']=datum(path['flow']['datumId'],'kg/s',owner+' · imposed mass flow',True)
                if 'step' in json.dumps(item['imposed'].arbol):raise NoSoportado('An imposed flow must be differentiable; a jump would require an impulse pressure model.')
            item['transferred']=state('path.'+owner+'.transferred_mass',owner+' · transferred mass diagnostic','kg',0,True)
            item['impulse']=state('path.'+owner+'.pressure_impulse',owner+' · net pressure impulse diagnostic','Pa*s',0,True)
            for end in ['inletPressure','outletPressure']:
                if path[end]['kind']=='datum':item[end+'Value']=datum(path[end]['datumId'],'Pa',owner+' · '+end,True)
            self.paths.append(item)
        for storage in self.storages.values():
            expression,bindings=storage.pop('materialGraph');substitutions={};arguments=[]
            import sympy as sp
            for index,path in enumerate(self.paths):
                q=sp.Symbol('path_flow_'+str(index),real=True);arguments.append(q)
                for field,binding in bindings.items():
                    if binding[0]=='stream' and binding[1] in (path['inletStreamId'],path['outletStreamId']):substitutions[field]=q
            expression=expression.xreplace(substitutions)
            if expression.atoms(sp.Function) or expression.free_symbols-set(arguments):raise NoSoportado('The derived material graph retains an unbound source or boundary quantity.')
            storage['rate']=sp.lambdify(arguments,expression,'math')
        est=model['estudio']
        if not est or est['tipo']!='temporal':raise NoSoportado('Reduced hydraulics requires a time study.')
        self.tf=datum(est['tiempoId'],'s','Final time')
        from .compilador import temporal_method
        self.method=temporal_method(est['metodoSolicitado'])
        if self.method is None or self.tf<=0 or not 2<=est['muestras']<=2001 or est['rtol']<=0 or est['atol']['cantidad']<=0:raise NoSoportado('Invalid hydraulic time study.')
        self.atol=np.full(len(self.y0),est['atol']['cantidad'])
        self.initial=np.array(self.y0)
        try:self.evaluate(0,self.initial)
        except Detencion as error:raise NoSoportado('Invalid initial hydraulic state: '+error.mensaje) from error

    def pressure(self,path,end,t,y):
        boundary=path[end]
        if boundary['kind']=='recover':return None
        if boundary['kind']=='datum':return path[end+'Value'](t)
        storage=self.storages[boundary['volumeId']]
        z=path['inletElevationId' if end=='inletPressure' else 'outletElevationId']
        return storage['pressure'](y[storage['index']],storage['area'],self.rho,self.g,storage['floor'],z,storage['surface'](t))

    def evaluate(self,t,y,check=True):
        values=[]
        for path in self.paths:
            flow=y[path['index']] if 'index' in path else path['imposed'](t)
            loss=path['resistance']*flow;gravity=self.rho*self.g*(path['outletElevationId']-path['inletElevationId'])
            pin=self.pressure(path,'inletPressure',t,y);pout=self.pressure(path,'outletPressure',t,y)
            if 'index' in path:rate=scalar_functions()['rate'](pin,pout,flow,*path['lawArguments'])
            else:
                rate=path['imposed'].d_dt(t)
                delta=scalar_functions()['drop'](flow,rate,*path['lawArguments'])
                if pin is None:pin=pout+delta
                else:pout=pin-delta
            reynolds=check_medium_domain(flow,rate,pin,pout,path['diameterId'],self.mu,self.pmin) if check else 4*abs(flow)/(math.pi*path['diameterId']*self.mu)
            values.append({'flow':flow,'rate':rate,'inlet':pin,'outlet':pout,'drop':pin-pout,'viscous':loss,'inertial':path['inertance']*rate,'gravity':gravity,'reynolds':reynolds,'dissipation':loss*flow/self.rho})
        return values

    def inicial(self):return self.initial.copy()
    def firma(self,t,y):return None
    def dominio(self,t,y):return np.array([y[s['index']] for s in self.storages.values()])
    def describir_dominio(self,k):return 'Nonnegative stored mass · '+list(self.storages)[k]

    def rhs(self,t,y):
        dy=np.zeros(len(y))
        values=self.evaluate(t,y)
        for path,value in zip(self.paths,values):
            if 'index' in path:dy[path['index']]=value['rate']
            dy[path['transferred']]=value['flow']
            dy[path['impulse']]=value['inertial']
        for storage in self.storages.values():dy[storage['index']]=storage['rate'](*(value['flow'] for value in values))
        return dy

    def report(self):
        source=self.model;est=source['estudio']
        equations=list(self.rows)
        for path in self.paths:
            development=momentum.describe_volume(source['motores']['momentumDerivation'],path['volumeId'],source)
            equations.extend({'id':path['volumeId']+'.'+row['id'],'family':'Momentum','latex':row['latex']} for row in development['finalSteps'])
            if 'imposed' in path:equations.append({'id':path['volumeId']+'.flow-boundary','family':'Momentum','latex':r'\dot m(t)=\dot m_{\mathrm{boundary}}(t)'})
        from core.balances.material_derivation import validate_model_journal as validate_material
        from core.termodinamica.derivation import validate_model_journal as validate_state
        from core.modelo.equation_workbench import attach_report
        from .transformed import _signature
        report={'format':'rage.compilation','version':1,'formulation':'physical','sourceModelId':source['id'],'sourceRevision':None,'signature':_signature(source),'method':self.method,'closureStrategy':'declared_assumption',
            'materialDerivation':validate_material(source),'thermodynamicDerivation':validate_state(source),'momentumDerivation':momentum.validate_model_journal(source),
            'variables':[{'id':f['id'],'sourceId':f['id'],'role':'differential','unit':f['unit'],'physicalUnit':f['unit'],'scaleSI':1,'absoluteTolerance':float(self.atol[f['index']])} for f in self.fields if not f['diagnostic']],
            'equations':[],'systemEquations':equations,'domains':[],'conditions':[],'direct':[],'inverse':[],'eliminatedVariables':[],
            'auxiliaryStates':2*len(self.paths),'auxiliaryPurpose':'Transferred mass and pressure impulse independently integrated as conservation diagnostics. A prescribed-flow model integrates these diagnostics, not an invented hydraulic state.',
            'time':{'id':'t','sourceId':'t','scaleSI':1,'finalTime':self.tf,'physicalFinalTime':self.tf},
            'parameters':[{'id':id_,'value':value,'unit':unit} for id_,(value,unit) in self.parameters.items()],
            'matrix':'RK45 evaluates the assembled incidence/force RHS; BDF estimates its time-step Jacobian numerically. Recovered pressure is eliminated using the known flow derivative.',
            'limits':'Single-component assumed isothermal constant-density medium; quasi-steady laminar circular wall closure. No energy/equilibrium certification, turbulence, cavitation, water hammer or spatial pressure mesh.',
            'strategy':{'methods':[{'id':m,'available':True,'reason':'Existing shared '+m+' time integrator.'} for m in ['RK45','BDF']],
                'scope':'The same laws are assembled from path roles and oriented streams. A prescribed flow recovers one pressure; a dynamic flow requires two independent pressure closures. No example-specific equation or pressure trajectory is stored.',
                'steps':[{'id':'deduce','title':'Replay and admit the physical deductions','description':'Validate Cauchy reductions, dynamic matter, the shared assumed medium, geometry, boundary roles and units. Unsupported terms block execution.','latex':r'\frac LA\frac{d\dot m}{dt}=p_1-p_2+\Delta p_{\mathrm{drive}}-\Delta p_{\mathrm{loss}}-\rho g\Delta z'},
                    {'id':'assemble','title':'Couple inventories and pressure at the same time step','description':'Evaluate the matter graph and the integrated momentum relations shown above. The same material inventories determine the generic reference coordinates and absolute pressures.','latex':r'\dot{\mathbf y}=\mathbf f(t,\mathbf y)'},
                    {'id':'advance','title':'Advance retained states and reconstruct pressure','description':'Use the selected RK45/BDF integrator. A known flow derivative recovers the missing pressure without replacing the momentum law by a steady law. Stop on depleted inventories, invalid pressure or loss of laminar validity.','latex':r'\dot{\mathbf y}=\mathbf f(t,\mathbf y),\quad\Delta p=\Delta p_{\mathrm{inertia}}+\Delta p_{\mathrm{wall}}+\Delta p_{\mathrm{gravity}}-\Delta p_{\mathrm{drive}}'},
                    {'id':'verify','title':'Verify mass, pressure impulse and dissipation','description':'Conservation diagnostics do not constitute thermodynamic phase or energy certification.','latex':r'\Delta m_v-\sum_s B_{vs}\int\dot m_sdt=0,\quad\frac LA\Delta\dot m-\int\Delta p_{\mathrm{inertia}}dt=0,\quad\Delta p_{\mathrm{wall}}Q\geq0'}]}}
        return attach_report(report,source,force=True)


def resolve(model):
    system=HydraulicSystem(model);est=model['estudio'];y0=system.inicial()
    system.evaluate(0,y0)
    trajectory=integrar(system,y0,system.tf,rtol=est['rtol'],atol=system.atol,max_step=system.tf/(est['muestras']-1),metodo=system.method)
    accepted=[float(segment[1]) for segment in trajectory.tramos]
    if len(accepted)>8000:accepted=[accepted[int(i)] for i in np.linspace(0,len(accepted)-1,8000)]
    times=sorted(set(float(t) for t in np.linspace(0,system.tf,est['muestras']) if t<=trajectory.t_fin)|set(accepted)|{float(trajectory.t_fin)})
    rows=[trajectory.y(t) for t in times];evaluations=[system.evaluate(t,y,check=False) for t,y in zip(times,rows)]
    series=[serie(f['id'],f['label'],f['unit'],['t'],[float(y[f['index']]) for y in rows],propietarioId='hydraulics') for f in system.fields]
    mass_error=0.;impulse_error=0.
    for owner,storage in system.storages.items():
        heights=[float(storage['height'](y[storage['index']],storage['area'],system.rho)) for y in rows]
        series.append(serie('volume.'+owner+'.height',owner+' · liquid height','m',['t'],heights,propietarioId='volume:'+owner))
        for y in rows:
            transferred=0
            for path in system.paths:
                for end,sign in [('inletPressure',-1),('outletPressure',1)]:
                    if path[end]['kind']=='storage' and path[end]['volumeId']==owner:transferred+=sign*y[path['transferred']]
            mass_error=max(mass_error,abs(y[storage['index']]-y0[storage['index']]-transferred)/max(y0[storage['index']],1))
    for index,path in enumerate(system.paths):
        for key,unit in [('flow','kg/s'),('inlet','Pa'),('outlet','Pa'),('drop','Pa'),('viscous','Pa'),('inertial','Pa'),('gravity','Pa'),('reynolds','1'),('dissipation','W')]:
            if key=='flow' and 'index' in path:continue
            series.append(serie('path.'+path['volumeId']+'.'+key,path['volumeId']+' · '+key,unit,['t'],[float(v[index][key]) for v in evaluations],propietarioId='path:'+path['volumeId']))
        initial=system.evaluate(0,y0,check=False)[index]['flow']
        for y,v in zip(rows,evaluations):
            delta=path['inertance']*(v[index]['flow']-initial)
            impulse_error=max(impulse_error,abs(delta-y[path['impulse']])/max(abs(delta),1))
    verifications=[{'id':'mass_conservation','valor':mass_error,'tolerancia':1e-7,'descripcion':'Stored mass change minus integrated oriented transport.'},
        {'id':'momentum_impulse','valor':impulse_error,'tolerancia':1e-6,'descripcion':'Momentum change minus integrated net force impulse.'}]
    powers=[v['dissipation'] for row in evaluations for v in row]
    verifications.append({'id':'wall_dissipation','valor':max(0,-min(powers))/max(1,max(abs(p) for p in powers)),'tolerancia':1e-12,'descripcion':'Nonnegative internal mechanical dissipation from the declared wall law.'})
    events=[evento(code,'t',float(t),message) for code,t,_a,_b,message in trajectory.eventos]
    return conjunto(model['id'],model['nombre'],'parcial' if trajectory.detenida else 'resuelto',{'motor':'rage.compilador.hydraulics','metodo':system.method,'firma':None,'pasos':trajectory.pasos,'rechazos':trajectory.rechazos,'compilation':system.report(),'mensaje':trajectory.detenida.mensaje if trajectory.detenida else 'Assumed-medium hydraulic trajectory; energy and equilibrium are not certified.'},[eje('t','Time','tiempo','s',times)],series,events,verifications,modeloId=model['id'])
