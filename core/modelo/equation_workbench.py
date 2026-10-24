"""Generic, persisted equation operations in Model. No equipment/scenario branches."""
import copy
import re
import sympy as sp
from .equation_manipulation import EquationGraph,math_latex
from core.mathematics.dimensions import catalog,dimension,parse_expression
from core.mathematics.session import replay_operations,edit_history
from core.mathematics.contract import FORMAT,read_definition as read_operation_definition
from core.mathematics.provenance import input_ids
from .operation_journal import JournalError,keys,replay

SOURCE_REVISION='physical-equation-graphs-8'
FAMILIES=('matter','momentum','energy','thermodynamics')


def _components(state,module):
    """Apply declared coefficient/body-field dependencies to typed Cauchy terms.
    Constant reference density is a substitution, not merely a display label.
    """
    result=module.cartesian_relations(state,material=state['massContinuity']);substitutions={}
    for terms in result:
        for field in set().union(*(e.atoms(sp.Function) for e in terms)):
            if state['referenceDensity'] and field.func.__name__=='rho':substitutions[field]=sp.Symbol('rho',real=True)
            if state['uniformGravity'] and field.func.__name__ in ('b_x','b_y','b_z'):
                axis=field.func.__name__[-1]
                substitutions[field]=(-sp.Symbol('g',real=True) if axis=='z' else sp.S.Zero) if state['verticalGravity'] else sp.Symbol('b_'+axis,real=True)
    return [tuple(e.xreplace(substitutions).doit() for e in terms) for terms in result]


def read_definition(value):
    read_operation_definition(value)
    if any(op['family'] not in FAMILIES for op in value['operations']):
        raise JournalError('Unknown physical equation family in the workspace adapter.')
    return value


def fundamental_report(value,action=None):
    """Unbound laws for a blank Model, without inventing a chemical species,
    a solver-ready common model or a retrospective deduction history.
    """
    if isinstance(value,dict) and type(value.get('version')) is int and value['version'] in (2,3):
        if action is not None and value['version']!=3:raise JournalError('Symbolic equation editing requires version 3.')
        return _unbound_report(value,action)
    if action is not None:raise JournalError('This fundamental preview is read-only.')
    keys(value,['format','version','modelId'])
    if value['format']!='rage.fundamental-equations' or type(value['version']) is not int or value['version']!=1 or not isinstance(value['modelId'],str) or not value['modelId'].strip():raise JournalError('Invalid fundamental-law preview request.')
    from core.balances.material_equations import local_component_law
    from core.balances import momentum_derivation as momentum
    t=sp.Symbol('t',real=True);xyz=sp.symbols('x y z',real=True);args=(*xyz,t)
    rho,j,g,c=(sp.Function(name)(*args) for name in ('rho_i','j_i','g_i','c_i'));v=sp.Symbol('v',real=True)
    graph=EquationGraph({rho:r'\rho_i(\mathbf x,t)',j:r'\mathbf j_i(\mathbf x,t)',g:r'\gamma_i(\mathbf x,t)',c:r'\chi_i(\mathbf x,t)',v:r'\mathbf v'})
    local_component_law(graph,'fundamental.matter',rho,v,j,g,c)
    for axis,(rate,transport,force) in zip('xyz',momentum.cartesian_relations(momentum.fundamental())):graph.add('fundamental.momentum.'+axis,rate+transport,force,'Fundamental Cauchy conservation · '+axis,family='momentum')
    units={rho:'kg/m3',j:'kg/(m2*s)',g:'kg/(m3*s)',c:'kg/(m3*s)'}
    return {'format':'rage.equation-workbench-report','version':1,'modelId':value['modelId'],'draft':True,'findings':[],
            'definition':{'format':FORMAT,'version':1,'operations':[],'cursor':0},
            'equations':[{**row,'ownerId':'unbound','current':True} for row in graph.rows()],
            'quantities':[{'id':id_,'input':'q_'+str(i+1),'latex':math_latex(s,graph.names),'unit':_known_unit(s,units),'coordinate':isinstance(s,sp.Symbol),'name':str(s)} for i,(id_,s) in enumerate(catalog(graph,units).items())],
            'execution':{'supported':False,'reason':'Fundamental laws with an unbound component index i. Declare components in this assumptions panel to instantiate their balances and enable equation operations. No physical species or numerical data has been invented.'}}


def _unbound_report(value,action=None):
    """Replay actual authoring journals with a generic index, never a fake species.

    Version 1 remains the immutable fundamental-law preview. Version 2 carries
    the physical source so edits, undo and port changes invalidate the request.
    This context is not a common executable model and cannot enter compilation.
    """
    from core.balances import material_derivation as material, momentum_derivation as momentum, energy_derivation as energy
    from core.termodinamica import derivation as thermo
    keys(value,['format','version','modelId','materialJournal','ports']+(['definition'] if value['version']==3 else []),['momentumJournal','energyJournal','thermodynamicJournal'])
    if value['format']!='rage.fundamental-equations' or not isinstance(value['modelId'],str) or not value['modelId'].strip():raise JournalError('Invalid symbolic authoring request.')
    owner='dominio'
    journal={'format':'rage.material-derivation','version':1,'volumes':{owner:value['materialJournal']}}
    material.read_journal(journal)
    state=material.replay_volume(value['materialJournal'])[-1]
    if not isinstance(value['ports'],list) or len(value['ports'])>160:raise JournalError('Invalid symbolic boundaries.')
    streams=[];seen=set()
    for port in value['ports']:
        keys(port,['id','sentido'],['constante'])
        if type(port['id']) is not int or port['id']<1 or port['id'] in seen or port['sentido'] not in ('entrada','salida') or ('constante' in port and type(port['constante']) is not bool):raise JournalError('Invalid or repeated symbolic boundary.')
        seen.add(port['id'])
        streams.append({'id':'puerto.'+str(port['id']),'desde':owner if port['sentido']=='salida' else None,'hasta':owner if port['sentido']=='entrada' else None,'componenteIds':[],**({'constante':port['constante']} if 'constante' in port else {})})
    engines={'materialDerivation':journal}
    if 'momentumJournal' in value:
        momentum.read_journal(value['momentumJournal'])
        if set(value['momentumJournal']['volumes'])-{owner}:raise JournalError('Unknown symbolic momentum region.')
        engines['momentumDerivation']=value['momentumJournal']
    for field,module,namespace in [('energyJournal',energy,'energyDerivation'),('thermodynamicJournal',thermo,'thermodynamicDerivation')]:
        if field in value:
            module.read_journal(value[field])
            if set(value[field]['volumes'])-{owner}:raise JournalError('Unknown symbolic physical region.')
            engines[namespace]=value[field]
    context={'id':value['modelId'],'componentes':[],'volumenes':[{'id':owner,'componenteIds':[],'supuestos':{'materia':state}}],'corrientes':streams,'motores':engines}
    if value['version']==3:
        engines['equationWorkbench']=read_definition(value['definition'])
        return edit(context,action,unbound=True) if action is not None else describe_for_authoring(context,unbound=True)
    graph,final,locations,units=_source_graph(context,unbound=True)
    return {'format':'rage.equation-workbench-report','version':1,'modelId':value['modelId'],'draft':True,
            'definition':{'format':FORMAT,'version':1,'operations':[],'cursor':0},'findings':_source_findings(context),
            'equations':[{**row,'ownerId':locations[row['id']],'current':row['id'] in final} for row in graph.rows()],
            'quantities':[{'id':id_,'input':'q_'+str(i+1),'latex':math_latex(s,graph.names),'unit':_known_unit(s,units),'coordinate':isinstance(s,sp.Symbol),'name':str(s)} for i,(id_,s) in enumerate(catalog(graph,units).items())],
            'execution':{'supported':False,'reason':'Assumptions are applied symbolically to the unbound component index i. Declare physical components before numerical compilation or additional equation operations.'}}


def _source_graph(model,*,unbound=False):
    from core.balances.material_equations import equation_graph
    from core.balances import momentum_derivation as momentum
    from core.balances.momentum_reductions import reduction_graphs,canonical_path_graph,connected_storage_reduction
    graph=EquationGraph();final=[];locations={};units={}
    def merge(source,owner,prefix=''):
        for key,node in source.nodes.items():
            id_=prefix+key
            inputs=tuple(prefix+i for i in node.inputs);rule=node.rule
            if key=='path.cauchy' and 'momentum.'+owner+'.local.x' in graph.nodes:
                from core.balances.material_equations import Divergence
                source_id='momentum.'+owner+'.local.x';original=graph.nodes[source_id].equation
                fields={f.func.__name__.split('__')[0]:f for f in node.equation.atoms(sp.Function) if f.func.__module__ is None}
                density=next(s for s in node.equation.free_symbols if str(s)=='rho__'+owner)
                direction=next(s for s in node.equation.free_symbols if str(s)=='s__'+owner)
                replacements={s:direction for s in original.free_symbols if str(s)=='x__'+owner}
                for f in original.atoms(sp.Function):
                    name=f.func.__name__.split('__')[0]
                    if name=='rho':replacements[f]=density
                    elif name=='v_x':replacements[f]=fields['u_local']
                    elif name in ('v_y','v_z','sigma_12','sigma_13'):replacements[f]=sp.S.Zero
                    elif name=='sigma_11':replacements[f]=fields['sigma_local']
                    elif name=='b_x':replacements[f]=fields['b_local']
                projected=sp.Eq(original.lhs.xreplace(replacements).doit(),original.rhs.xreplace(replacements).doit(),evaluate=False)
                expanded=node.equation.replace(lambda n:isinstance(n,Divergence),lambda n:sp.diff(n.args[0],direction)).doit()
                if sp.simplify(projected.lhs-projected.rhs-expanded.lhs+expanded.rhs)!=0:raise JournalError('The path projection does not match its fundamental Cauchy component.')
                bridge=prefix+'path.projection'
                graph.add(bridge,projected.lhs,projected.rhs,'Apply the straight-path field dependencies to Cauchy conservation','field_substitution',(source_id,),
                          ('Axial velocity; no transverse transport or stress gradients; constant reference density; coordinate x renamed s',),family='momentum')
                locations[bridge]=owner;inputs=(bridge,);rule='conservative_operator_rewrite'
            graph.add(id_,node.equation.lhs,node.equation.rhs,node.title,rule,inputs,node.assumptions,node.family,node.kind,node.dependent,predicates=node.predicates)
            locations[id_]=owner
        graph.names.update(source.names)
    for volume in model['volumenes']:
        owner=volume['id'];material,selected,bindings=equation_graph(model,owner,volume['supuestos']['materia'],unbound=unbound)
        merge(material,owner);final.extend(selected)
        for symbol,binding in bindings.items():
            units[symbol]=('kg/m3' if str(symbol.func).startswith('rho') else 'kg') if binding[0] in ('inventory','total_inventory') else 'm3' if binding[0]=='volume' else 'kg/(m3*s)' if binding[0] in ('generation_density','consumption_density') else 'kg/s'
        from core.balances.energy_equations import equation_graph as energy_graph
        from core.termodinamica.equations import equation_graph as thermo_graph
        for producer in (energy_graph,thermo_graph):
            physical,selected,physical_units=producer(model,owner)
            merge(physical,owner);final.extend(selected);units.update(physical_units)
        entry=model['motores'].get('momentumDerivation',{}).get('volumes',{}).get(owner)
        states=replay(entry,momentum.fundamental,momentum.normalize) if entry else [momentum.fundamental()]
        state=states[-1];local=EquationGraph();local_current=[]
        component_relations=[_components(physical,momentum) for physical in states]
        for axis_index,axis in enumerate('xyz'):
            rate,convection,force=component_relations[0][axis_index]
            current='local.'+axis
            local.add(current,rate+convection,force,'Fundamental Cauchy conservation · '+axis+' component',family='momentum')
            for step,physical in enumerate(states[1:],1):
                rate,convection,force=component_relations[step][axis_index]
                equation=sp.Eq(rate+convection,force,evaluate=False)
                if equation!=local.nodes[current].equation:
                    operation=entry['operations'][step-1];key='local.'+axis+'.step-'+str(step)
                    conditions=tuple(momentum.CONTROL_LABELS.get(k,('',k))[1]+(' — enabled' if v else ' — disabled') for k,v in operation['changes'].items() if isinstance(v,bool))
                    local.add(key,equation.lhs,equation.rhs,'Apply physical assumption · '+('; '.join(conditions) or operation['title']),'physical_reduction',(current,),conditions,family='momentum')
                    current=key
            local_current.append(current)
            if state.get('zeroLocalAccumulation'):
                key='local.'+axis+'.zero-rate';local.add(key,rate,0,'Declared local zero-rate condition · '+axis,'assumption',inputs=(current,),family='momentum',kind='constraint');local_current.append(key)
        if state['form'] in ('integral','ports','hydraulic'):
            from core.balances.momentum_transport import extend_transport
            local_current=extend_transport(local,state)
        storage_result=connected_storage_reduction(local,state)
        if storage_result:
            local_current.extend(key for key in ('storage.port-pressure','storage.pressure')
                                 if key in local.nodes and (key!='storage.pressure' or 'storage.port-pressure' not in local.nodes))
        parts=[local]
        if state['form']=='hydraulic':parts.append(canonical_path_graph())
        wall,_,storage,_=reduction_graphs(state);parts.append(wall)
        if storage_result is None:parts.append(storage)
        for part in parts:
            # Symbol identity is scoped by domain; physical coupling must be
            # explicit, never an accidental same spelling in two producers.
            replacements={symbol:sp.Symbol(str(symbol)+'__'+owner,**symbol.assumptions0) for node in part.nodes.values() for symbol in node.equation.free_symbols if str(symbol)!='t'}
            total=next((s for s,b in bindings.items() if b[0]=='total_inventory' and volume['supuestos']['materia']['vista']!='campo'),None)
            inlet=next((s for s in model['corrientes'] if s['id']==state.get('inletStreamId')),None)
            shared_flow=sum((q for q,b in bindings.items() if b[0]=='stream' and inlet and b[1]==inlet['id']),sp.S.Zero)
            for symbol in list(replacements):
                if str(symbol)=='m_v' and total is not None:replacements[symbol]=total
                if str(symbol)=='massFlow' and inlet and shared_flow!=0:replacements[symbol]=shared_flow
                if str(symbol)=='massFlowRate' and inlet and shared_flow!=0:replacements[symbol]=sp.diff(shared_flow,sp.Symbol('t',real=True))
                if str(symbol) in ('p1','p2','drive','loss','p_r','z_r','h','C_p','C_1','C_2'):
                    replacements[symbol]=sp.Function(str(symbol)+'__'+owner)(sp.Symbol('t',real=True))
            # Applied fields need scope too; sharing a spelling never couples
            # two domains. Only shared connection identities do that.
            functions={f.func:sp.Function(f.func.__name__+'__'+owner) for node in part.nodes.values() for f in node.equation.atoms(sp.Function) if f.func.__module__ is None}
            for node in part.nodes.values():
                for f in node.equation.atoms(sp.Function):
                    if f.func not in functions:continue
                    args=[a.xreplace(replacements) for a in f.args]
                    if f.func.__name__ in ('p','u') and sp.Symbol('t',real=True) not in args:args.append(sp.Symbol('t',real=True))
                    flow_stream=inlet if f.func.__name__ in ('m_flow','port_mass_1') else next((s for s in model['corrientes'] if s['id']==state.get('outletStreamId')),None) if f.func.__name__=='port_mass_2' else None
                    bound_flow=sum((q for q,b in bindings.items() if b[0]=='stream' and flow_stream and b[1]==flow_stream['id']),sp.S.Zero)
                    replacements[f]=bound_flow if flow_stream and bound_flow!=0 else functions[f.func](*args)
            scoped=EquationGraph({replacements.get(k,k):v for k,v in part.names.items()})
            for replacement in replacements.values():
                if replacement in graph.names:scoped.names[replacement]=graph.names[replacement]
            for original,replacement in replacements.items():
                if replacement not in scoped.names:
                    display=original
                    if isinstance(original,sp.Function) and original.func.__name__ in ('p','u') and sp.Symbol('t',real=True) not in original.args:display=original.func(*original.args,sp.Symbol('t',real=True))
                    scoped.names[replacement]=math_latex(display,part.names)
            for key,node in part.nodes.items():scoped.add(key,node.equation.lhs.xreplace(replacements),node.equation.rhs.xreplace(replacements),node.title,node.rule,node.inputs,node.assumptions,node.family,node.kind,node.dependent,predicates=tuple(p.xreplace(replacements) for p in node.predicates))
            merge(scoped,owner,'momentum.'+owner+'.')
            if scoped.nodes:
                selected=(local_current if part is local and state['form']!='hydraulic' else [key for key in local_current if key.startswith(('angular.','rotor.'))] if part is local else [next(reversed(scoped.nodes))])
                final.extend('momentum.'+owner+'.'+key for key in selected)
                if 'storage.height' in scoped.nodes:final.append('momentum.'+owner+'.storage.height')
        if state['form']=='hydraulic' and total is not None:
            # A fixed, constant-density path stores a fixed total mass. Derive
            # its compatibility from the same material total, not a second
            # q_in=q_out template or an extra integrated state.
            prefix='momentum.'+owner+'.path.'
            rho,A,L=(sp.Symbol(name+'__'+owner,real=True) for name in ('rho','A','L'))
            graph.add(prefix+'mass-definition',total,rho*A*L,'Evaluate total mass for the fixed uniform section','geometry',assumptions=('Fixed straight geometry; uniform constant density and section',),family='matter',kind='definition')
            graph.differentiate(prefix+'mass-rate',prefix+'mass-definition',sp.Symbol('t',real=True),'Differentiate the fixed geometric mass inventory')
            constraint=graph.nodes[prefix+'mass-rate'].equation
            source='matter.'+owner+'.total'
            graph.substitute(prefix+'mass-compatibility',source,{constraint.lhs:constraint.rhs},'Substitute the fixed geometric inventory rate in total conservation',inputs=(prefix+'mass-rate',))
            graph.nodes[prefix+'mass-compatibility'].kind='constraint';graph.nodes[prefix+'mass-compatibility'].dependent=True
            for key in ('mass-definition','mass-rate','mass-compatibility'):locations[prefix+key]=owner
            final.append(prefix+'mass-compatibility')
    return graph,final,locations,units


UNIT_NAMES={'rho':'kg/m3','mu':'Pa*s','L':'m','A':'m2','D':'m','g':'m/s2','z1':'m','z2':'m','massFlow':'kg/s','massFlowRate':'kg/s2','p1':'Pa','p2':'Pa','drive':'Pa','loss':'Pa','r':'m','R':'m','z':'m','z_r':'m','z_0':'m','z_surface':'m','z_floor':'m','h':'m','A_v':'m2','m_v':'kg','p_r':'Pa','p_surface':'Pa','Q':'m3/s','t':'s','v':'m/s','v_b':'m/s'}


def _known_unit(expression,units):
    if expression in units:return units[expression]
    if not isinstance(expression,(sp.Symbol,sp.core.function.AppliedUndef)):return None
    # A field keeps its unit when the chain rule evaluates it at a dummy
    # argument. Match its scoped function identity, never just a display name.
    if isinstance(expression,sp.core.function.AppliedUndef):
        for quantity,unit in units.items():
            if isinstance(quantity,sp.core.function.AppliedUndef) and quantity.func==expression.func:return unit
    name=str(expression.func) if isinstance(expression,sp.Function) else str(expression)
    name=name.split('__')[0]
    if name.startswith(('basis_','blade_angle')):return '1'
    if name.startswith('boundary_v_') or name.startswith(('port_velocity_','tangential_velocity_')) or name=='meridional_velocity':return 'm/s'
    if name.startswith('I_'):return 'kg*m/s'
    if name=='I':return 'kg*m/s'
    if name in ('F_body','F_wall'):return 'N'
    if name in ('c_1','c_2'):return 'm/s'
    if name in ('local_rate','convection','viscous_force','pressure_gradient','viscous_stress_divergence'):return 'N/m3'
    if name.startswith(('wall_force_','port_shear_','body_force_')):return 'N'
    if name.startswith('oriented_area_') or name=='annular_area':return 'm2'
    if name.startswith('port_mass_'):return 'kg/s'
    if name in ('r1','r2','outlet_width'):return 'm'
    if name in ('fluid_angular_momentum','rotor_angular_momentum'):return 'kg*m2/s'
    if name in ('fluid_torque','other_torque','motor_torque','bearing_torque','rotor_energy'):return 'J'
    if name=='J':return 'kg*m2'
    if name=='omega':return '1/s'
    if name=='shaft_power':return 'W'
    if name=='specific_shaft_transfer':return 'J/kg'
    if isinstance(expression,sp.Function) and name in ('g','c'):return 'kg/(m3*s)'
    if name in ('x','y','s'):return 'm'
    if name=='p' or name=='C_p' or re.fullmatch(r'(sigma|tau)_\d\d',name):return 'Pa'
    if re.fullmatch(r'v_[xyz]',name) or name in ('C_1','C_2'):return 'm/s'
    if re.fullmatch(r'b_[xyz]',name) or name in ('profile_acceleration','convective_acceleration','body_acceleration'):return 'm/s2'
    if name=='lambda':return 'Pa*s'
    if name.startswith('velocity_'):return 'm/s'
    if name.startswith('flux_'):return 'kg/(m2*s)'
    if name in ('theta','phi'):return '1'
    if name=='rho_mixture':return 'kg/m3'
    if name=='A_port':return 'm2'
    if name=='normal_flux':return 'kg/(m2*s)'
    if name=='D' and isinstance(expression,sp.Function):return 'm2/s'
    if name in UNIT_NAMES:return UNIT_NAMES[name]
    return {'m':'kg','rho':'kg/m3','rho_mean':'kg/m3','V':'m3','Q':'m3/s','j':'kg/(m2*s)','g':'kg/(m3*s)','c':'kg/(m3*s)','G':'kg/s','C':'kg/s','Phi':'kg/s','q':'kg/s','u':'m/s','u_local':'m/s','sigma_local':'Pa','b_local':'m/s2'}.get(name)


def _dimension(expression,units):
    return dimension(expression,units,_known_unit)


def _parse(text,quantities,conditions=None,units=None):
    return parse_expression(text,quantities,conditions,units,_known_unit)


def build(model,definition=None,*,unbound=False):
    definition=definition or model.get('motores',{}).get('equationWorkbench') or {'format':FORMAT,'version':1,'operations':[],'cursor':0}
    read_definition(definition)
    graph,final,locations,units=_source_graph(model,unbound=unbound)
    return replay_operations(graph,final,locations,units,definition,require_same_family=True,unit_resolver=_known_unit)


def _source_findings(model):
    findings=[]
    from core.balances import momentum_derivation as momentum
    for owner,entry in model['motores'].get('momentumDerivation',{}).get('volumes',{}).items():
        state=replay(entry,momentum.fundamental,momentum.normalize)[-1]
        if state['losslessPassage']:
            findings.append({'ownerId':owner,'family':'energy','message':'The typed angular and rotor graph is connected. The lossless passage pressure-recovery proof still needs its first-law coupling; no terminal pressure-rise formula is inserted into this graph.'})
        elif any(state[key] for key in ('adiabaticPassage','zeroPassageEnergyAccumulation')):
            findings.append({'ownerId':owner,'family':'energy','message':'Passage heat/storage conditions need an explicit connection to the first-law inventory and shaft-work boundary. Angular conservation alone cannot supply that energy relation.'})
        if state['form'] in ('ports','hydraulic') and (not state.get('inletStreamId') or not state.get('outletStreamId')):
            findings.append({'ownerId':owner,'family':'momentum','message':'Port averages are symbolic. Bind both ports to common material streams before claiming material/momentum flow coupling.'})
        if state['darcyWeisbach']:
            findings.append({'ownerId':owner,'family':'momentum','message':'The general Darcy wall-loss constitutive graph is not lowered here. The admitted numerical specialization requires the individually derived laminar circular wall closure.'})
    return findings


def _unsigned_findings(definition):
    """Publish missing historical evidence without modifying persisted records."""
    return [{'ownerId':'operation.'+str(index+1),'family':op['family'],
             'message':'Legacy/unsigned operation: no recorded input signatures. Current replay is inspection only; source changes cannot be verified. Compilation is blocked. Undo/Rewind and record the operation again to pin reviewed inputs.'}
            for index,op in enumerate(definition['operations'][:definition['cursor']])
            if input_ids(op) and 'sourceSignatures' not in op]


def describe(model,definition=None,*,unbound=False):
    graph,final,locations,units,definition,blocking,introduced=build(model,definition,unbound=unbound)
    quantities={**catalog(graph,units),**introduced}
    unsigned=_unsigned_findings(definition)
    return {'format':'rage.equation-workbench-report','version':1,'modelId':model['id'],'definition':definition,'findings':_source_findings(model)+unsigned,**({'draft':True} if unbound else {}),
            'equations':[{**row,'ownerId':locations.get(row['id'],'system'),'current':row['id'] in final} for row in graph.rows()],
            'quantities':[{'id':id_,'input':'q_'+str(index+1),'latex':math_latex(s,graph.names),'unit':_known_unit(s,units),'coordinate':isinstance(s,sp.Symbol),'name':str(s)} for index,(id_,s) in enumerate(quantities.items())],
            'execution':{'supported':not (blocking or unbound),'reason':unsigned[0]['message'] if unsigned else 'Symbolic authoring with the unbound component index i. Operations can be recorded; physical components and supported numerical lowering are required before Solve.' if unbound else 'Derived consequences retain their physical premises.' if not blocking else 'A new physical condition or relation is recorded. General constraint/closure compilation is a Model capability finding; Solve cannot silently run the earlier system.'}}


def describe_for_authoring(model,definition=None,*,unbound=False):
    """Keep valid source mathematics visible after an upstream edit.

    This is a read-only recovery report, never a repaired executable model.
    The full saved journal survives, and compilation still replays strictly.
    """
    stored=read_definition(definition if definition is not None else model.get('motores',{}).get('equationWorkbench') or {'format':FORMAT,'version':1,'operations':[],'cursor':0})
    try:return describe(model,stored,unbound=unbound)
    except JournalError as error:
        if not stored['cursor']:raise
        message=str(error)
    low,high=0,stored['cursor']
    report=describe(model,{**stored,'cursor':0},unbound=unbound)
    while low+1<high:
        middle=(low+high)//2
        try:
            candidate=describe(model,{**stored,'cursor':middle},unbound=unbound)
        except JournalError:high=middle
        else:low=middle;report=candidate
    report['definition']=copy.deepcopy(stored)
    report['findings']=_source_findings(model)+_unsigned_findings(stored)
    report['replay']={'completed':low,'failedOperation':low+1,'message':message}
    report['execution']={'supported':False,'reason':'An additional equation operation no longer matches its source. Review or undo it before solving. No saved operations were deleted.'}
    return report


def edit(model,action,*,unbound=False):
    definition=copy.deepcopy(model.get('motores',{}).get('equationWorkbench') or {'format':FORMAT,'version':1,'operations':[],'cursor':0})
    keys(action,['kind'],['operation'])
    if action['kind']=='append':
        if 'operation' not in action:raise JournalError('An equation operation is required.')
        operation=copy.deepcopy(action['operation'])
        read_operation_definition({'format':FORMAT,'version':1,'operations':[operation],'cursor':1})
        if operation.get('kind') in ('declare_relation','multiply','divide'):
            aliases={q['input']:q['id'] for q in describe(model,definition,unbound=unbound)['quantities']}
            for side in ('left','right'):
                if isinstance(operation.get(side),str):operation[side]=re.sub(r'\b[A-Za-z][A-Za-z0-9_]*\b',lambda match:aliases.get(match[0],match[0]),operation[side])
        action={**action,'operation':operation}
    graph,final,locations,units=_source_graph(model,unbound=unbound)
    definition=edit_history(graph,final,locations,units,definition,action,require_same_family=True,unit_resolver=_known_unit)
    return describe_for_authoring(model,definition,unbound=unbound) if action['kind'] in ('undo','rewind') else describe(model,definition,unbound=unbound)


def ensure_executable(model):
    definition=model.get('motores',{}).get('equationWorkbench')
    if definition and definition['cursor']:
        read_definition(definition)
        unsigned=_unsigned_findings(definition)
        if unsigned:raise JournalError(unsigned[0]['message'])
        _,_,_,_,_,blocking,_=build(model,definition)
        if blocking:raise JournalError('The deduced system contains a new workbench constraint, relation or validity condition. Its numerical enforcement is not connected; the old model will not be substituted. Review Model or undo the operation.')


def attach_report(report,model,force=False):
    """Carry the same replayed consequences into Solve/Results without
    pretending a dependent consequence adds an independent state equation.
    """
    definition=model.get('motores',{}).get('equationWorkbench')
    recorded=any(model.get('motores',{}).get(key) for key in ('materialDerivation','energyDerivation','thermodynamicDerivation','momentumDerivation'))
    if not force and not recorded and (not definition or not definition['cursor']):return report
    ensure_executable(model)
    development=describe(model)
    result={**report,'equationWorkbench':development}
    if force:
        result['systemEquations']=[{'id':row['id'],'family':row['family'].capitalize(),'latex':row['latex']} for row in development['equations'] if row['current'] and not row['id'].startswith('operation.')]
        result['systemEquations'].extend(row for row in report.get('systemEquations',[]) if row['id'].endswith('.flow-boundary'))
    return result
