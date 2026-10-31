"""Recorded thermodynamic assumptions and explicit equilibrium-package selection."""
import copy
from core.modelo.operation_journal import JournalError, keys, read_operations, replay, evidence, edit
FORMAT="rage.thermodynamic-derivation"

def fundamental():
    return {"monofasico":False,"sinCambioFase":False,"densidadConstante":False,"modelo":"sin_declarar","closure":None}

# Additive assumptions (30 October 2026): present in a state only once recorded,
# so earlier journals and documents replay byte-identically.
OPTIONAL={"soloLiquido":False,"referenciaFormacion":None}

def closure(value):
    keys(value,["packageId","model","policy"])
    keys(value["model"],["id","version"])
    if any(not isinstance(item,str) or not item.strip() for item in [value["packageId"],*value["model"].values()]):
        raise JournalError("A configured package identity and version are required.")
    policy=value["policy"]
    keys(policy,["cantidad","cambioInterno","evaluacion"],["tiposPermitidos"])
    if policy["cantidad"] not in ("sin_restriccion","monofasico") or policy["cambioInterno"] not in ("permitido","prohibido") or policy["evaluacion"]!="equilibrio_estable":
        raise JournalError("Unsupported phase policy.")
    if "tiposPermitidos" in policy and (not isinstance(policy["tiposPermitidos"],list) or not policy["tiposPermitidos"] or any(not isinstance(item,str) or item not in ("vapor","liquido","solido") for item in policy["tiposPermitidos"]) or len(set(policy["tiposPermitidos"]))!=len(policy["tiposPermitidos"])):
        raise JournalError("Invalid permitted phase types.")

def changes(value):
    keys(value,[],{**fundamental(),**OPTIONAL})
    if not value:raise JournalError("Thermodynamic operation changes are required.")
    for key,item in value.items():
        if key=="closure":
            if item is not None:closure(item)
        elif key=="modelo":
            if item not in ("sin_declarar","u_lineal"):raise JournalError("Unknown declared caloric relation.")
        elif key=="referenciaFormacion":
            if item not in (None,"gas","liquido"):raise JournalError("Unknown formation reference.")
        elif type(item) is not bool:raise JournalError("Thermodynamic assumptions must be booleans.")

def normalize(value):
    changes(value)
    state={**fundamental(),**copy.deepcopy(value)}
    bound=state["closure"]
    if bound is not None:
        if state["modelo"]!="sin_declarar" or state["densidadConstante"]:raise JournalError("A package closure conflicts with a manual caloric/density closure.")
        if state["monofasico"]!=(bound["policy"]["cantidad"]=="monofasico") or state["sinCambioFase"]!=(bound["policy"]["cambioInterno"]=="prohibido"):raise JournalError("The recorded phase policy differs from the thermodynamic assumptions.")
        if state.get("soloLiquido") and (bound["policy"]["cantidad"]!="monofasico" or bound["policy"].get("tiposPermitidos")!=["liquido"]):raise JournalError("A liquid-only phase set requires the single-phase policy restricted to liquid.")
    if state.get("soloLiquido") and state["modelo"]!="sin_declarar":raise JournalError("A liquid-only phase set belongs to an equilibrium package, not to a manual caloric law.")
    return state

def read_journal(value):
    read_operations(value,FORMAT,changes)
    for entry in value['volumes'].values():replay(entry,fundamental,normalize)
    return value

def expected_closure(model,volume):
    target=volume['termodinamica']
    if target['tipo']!='equilibrio':return None
    package=next((item for item in model['termodinamica']['paquetes'] if item['id']==target['paqueteId']),None)
    if package is None:raise JournalError("The selected thermodynamic package does not exist.")
    return {'packageId':package['id'],'model':copy.deepcopy(package['modelo']),'policy':copy.deepcopy(target['politica'])}

def validate_model_journal(model):
    journal=model.get('motores',{}).get('thermodynamicDerivation')
    if journal is None:return []
    read_journal(journal);volumes={item['id']:item for item in model['volumenes']};result=[]
    for owner,entry in journal['volumes'].items():
        volume=volumes.get(owner)
        if volume is None:raise JournalError(f"Unknown thermodynamic journal owner: {owner}.")
        actual=replay(entry,fundamental,normalize)[-1]
        flags=volume['supuestos']['energia'] or {}
        expected={key:flags.get(key,value) for key,value in fundamental().items() if key!='closure'}
        expected.update({key:flags[key] for key in OPTIONAL if key in flags})
        expected['closure']=expected_closure(model,volume)
        if actual!=expected:raise JournalError(f"Volume {owner}: thermodynamic operations do not produce the compiled closure and assumptions.")
        if expected['closure'] is None and actual['modelo']=='u_lineal' and volume['termodinamica'].get('supuesto')!='u_lineal':raise JournalError("The recorded caloric law differs from the declared state closure.")
        from core.modelo.relaciones import relaciones
        ids=[item['id'] for item in relaciones(model) if item['propietarioId']==f'volumen:{owner}' and item['familia'] in ('estado','equilibrio')]
        result.append(evidence(owner,entry,ids))
    return result

CHOICES={
 'one_phase':('Assume a single phase',{'monofasico':True}),
 'no_phase_change':('Keep the initial phase set',{'sinCambioFase':True}),
 'constant_density':('Declare constant mixture density',{'densidadConstante':True}),
 'linear_caloric':('Declare a linear specific internal-energy law',{'modelo':'u_lineal'}),
 'liquid_only':('Declare a liquid-only phase set: the vapour phase is not modelled',{'soloLiquido':True}),
 'liquid_formation_reference':('Anchor energies to the tabulated liquid formation data',{'referenciaFormacion':'liquido'}),
 'gas_formation_reference':('Anchor energies to the ideal-gas formation data',{'referenciaFormacion':'gas'}),
}

def edit_journal(journal,owner,action,configured=None):
    read_journal(journal)
    if not isinstance(owner,str) or not owner.strip():raise JournalError('A thermodynamic journal owner is required.')
    choices=copy.deepcopy(CHOICES)
    if configured is not None:
        closure(configured)
        choices['select_closure']=('Select the configured equilibrium package and declared phase policy',{'closure':copy.deepcopy(configured),'monofasico':configured['policy']['cantidad']=='monofasico','sinCambioFase':configured['policy']['cambioInterno']=='prohibido','densidadConstante':False,'modelo':'sin_declarar'})
    # Policy edits remain paired with their exact closure rather than stale flags.
    entry=journal.get('volumes',{}).get(owner) if isinstance(journal,dict) else None
    if entry:
        read_journal(journal);state=replay(entry,fundamental,normalize)[-1]
        if state['closure'] is not None:
            for kind,key,field,value in [('one_phase','monofasico','cantidad','monofasico'),('no_phase_change','sinCambioFase','cambioInterno','prohibido')]:
                updated=copy.deepcopy(state['closure']);updated['policy'][field]=value
                choices[kind]=(CHOICES[kind][0],{key:True,'closure':updated})
    return edit(journal,owner,action,FORMAT,changes,normalize,fundamental,choices)

RELATIONS={
 'monofasico':r'N_{\mathrm{present}}=1',
 'sinCambioFase':r'\mathcal P(t)=\mathcal P(0)',
 'densidadConstante':r'\rho=\rho_*>0,\quad V=m/\rho_*,\quad dV/dt=(dm/dt)/\rho_*',
 'modelo':r'u(T)=u_{\mathrm{ref}}+c_u(T-T_{\mathrm{ref}}),\quad c_u>0,\quad T_{\min}\leq T\leq T_{\max}',
 'soloLiquido':r'\mathcal P\subseteq\{\mathrm{liquid}\},\quad \text{no vapour phase is evaluated}',
 'referenciaFormacion':r'\bar h_i(T_0,P_0)=\Delta_f h_i^{\circ},\quad \bar s_i(T_0,P_0)=s_i^{\circ}\ \text{(declared formation reference)}',
}

def describe_volume(journal,owner,fixed):
    read_journal(journal)
    if type(fixed) is not bool or not isinstance(owner,str) or owner not in journal['volumes']:raise JournalError("A journal owner and mechanical boundary context are required.")
    entry=journal['volumes'][owner];states=replay(entry,fundamental,normalize)
    steps=[{'id':'fundamental','title':'Fundamental thermodynamic relation · simple compressible system','latex':r'dU=T\,dS-P\,dV+\sum_i\mu_i\,dn_i'},
           {'id':'legendre','title':'Legendre transformation · enthalpy and Gibbs energy','latex':r'H=U+PV,\quad G=U+PV-TS,\quad dG=-S\,dT+V\,dP+\sum_i\mu_i\,dn_i'},
           {'id':'extensive-phase','title':'Homogeneous simple-compressible phase · Euler relation and Gibbs–Duhem identity','latex':r'G^k=\sum_i n_i^k\mu_i^k,\quad \sum_i n_i^k\,d\mu_i^k=-S^k\,dT+V^k\,dP'}]
    for operation,previous,state in zip(entry['operations'],states,states[1:]):
        for key,relation in RELATIONS.items():
            if state.get(key)!=previous.get(key):
                steps.append({'id':operation['id']+'.'+key,'title':operation['title'],'latex':relation if state.get(key) not in (False,'sin_declarar',None) else r'\text{Previous restriction removed}'})
        if state['closure']!=previous['closure']:
            selected=state['closure']
            if selected is None:continue
            steps.extend([
                {'id':operation['id']+'.composition','title':'Phase amounts and normalized mole fractions','latex':r'n_k=\sum_i n_i^k,\quad x_i^k=n_i^k/n_k\ (n_k>0),\quad \sum_i x_i^k=1,\quad \beta_k=n_k/\sum_l n_l'},
                {'id':operation['id']+'.partition','title':'Component partition and property closure','latex':r'n_i=\sum_k n_k x_i^k,\quad U=\sum_k n_k u_k,\quad H=\sum_k n_k h_k,\quad V=\sum_k n_k v_k'},
                {'id':operation['id']+'.equilibrium','title':'Equilibrium of present phases · candidate-phase stability','latex':r'T^k=T,\quad P^k=P,\quad\mu_i^k=\mu_i^l,\quad\beta_k\geq0,\quad tm_k\geq0,\quad\beta_k tm_k=0'},
                {'id':operation['id']+'.package','title':operation['title']+' · '+selected['model']['id']+' @ '+selected['model']['version'],'latex':r'\mu_i=\left(\frac{\partial G}{\partial n_i}\right)_{T,P,n_{j\ne i}},\quad S=-\left(\frac{\partial G}{\partial T}\right)_{P,\mathbf n},\quad H=G+TS'},
            ])
            from .descripcion import _modelo_estado
            family=_modelo_estado(selected['model']['id'])
            liquid=family.get('modeloLiquido') or ''
            if liquid.startswith('unifac'):
                steps.append({'id':operation['id']+'.unifac','title':'UNIFAC constitutive choice · group contribution','latex':r'\ln\gamma_i=\ln\gamma_i^C+\ln\gamma_i^R,\quad\ln\gamma_i^R=\sum_k\nu_k^{(i)}(\ln\Gamma_k-\ln\Gamma_k^{(i)})'})
            if family['familia'] in ('ideal','actividad'):
                steps.extend([
                    {'id':operation['id']+'.activity-potential','title':'Liquid excess Gibbs energy and activity coefficients','latex':r'g^E=RT\sum_i x_i\ln\gamma_i,\quad RT\ln\gamma_i=\left(\frac{\partial (n g^E)}{\partial n_i}\right)_{T,P,n_{j\ne i}}'},
                    {'id':operation['id']+'.caloric','title':'Caloric and volume properties from the same excess potential','latex':r's^E=-\left(\frac{\partial g^E}{\partial T}\right)_{P,\mathbf x},\quad h^E=g^E+Ts^E,\quad v^E=\left(\frac{\partial g^E}{\partial P}\right)_{T,\mathbf x}=0,\quad u=h-Pv'},
                    {'id':operation['id']+'.fugacity','title':'Published mixture model · ideal vapor and liquid Poynting correction','latex':r'y_iP=x_i\gamma_i P_i^{\mathrm{sat}}\exp\!\left[\frac{v_i^L(P-P_i^{\mathrm{sat}})}{RT}\right]'},
                ])
            if family['familia']=='iapws95':
                steps.append({'id':operation['id']+'.helmholtz','title':'IAPWS-95 Helmholtz potential','latex':r'P=\rho^2(\partial a/\partial\rho)_T,\quad s=-(\partial a/\partial T)_\rho,\quad u=a+Ts'})
    state=states[-1]
    if state['closure'] is not None:
        final=r'(\mathbf n,U,V)\longmapsto(T,P,\{n_k,\mathbf x^k\})' if fixed else r'(\mathbf n,H,P)\longmapsto(T,V,\{n_k,\mathbf x^k\})'
    elif state['modelo']=='u_lineal':final=r'U=m\,u(T),\quad T=T_{\mathrm{ref}}+\frac{U/m-u_{\mathrm{ref}}}{c_u},\quad m>0'
    else:final=r'\text{No evaluated state closure selected}'
    steps.append({'id':'current-closure','title':'Current thermodynamic closure','latex':final})
    return {'format':'rage.thermodynamic-development','version':1,'volumeId':owner,'origin':entry['origin'],'formulation':state,'steps':steps,'notes':[
        'Package selection is an explicit constitutive choice. Its empirical parameters cannot be derived from conservation laws.',
        'The package identity/version and phase policy are replayed against the actual common model. Parameter data and domains retain their existing provenance.',
        'The first law integrates conserved quantities; the thermodynamic closure determines temperature, pressure and phase distribution at each evaluation.',
        'A phase restriction is a validity condition, not permission to remove a thermodynamically stable phase silently.',
        'The journal verifies recorded choices, not experimental accuracy, universal stability or applicability outside the package domain.'
    ]}
