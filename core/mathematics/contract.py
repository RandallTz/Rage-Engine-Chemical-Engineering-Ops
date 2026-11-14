"""Strict, compatible operation records; group labels have no mathematical meaning."""
import re
from .errors import MathematicsError as JournalError


def keys(value,required,optional=()):
    if not isinstance(value,dict) or set(value)-set(required)-set(optional) or set(required)-set(value):
        raise JournalError('Unknown or missing equation operation fields.')


FORMAT='rage.equation-workbench'
RULES=('combine','substitute','isolate','expand','factor','differentiate','integrate','volume_integrate','gauss','reynolds','zero','apply_zero','declare_symbol','declare_function','change_dependencies','declare_relation','multiply','divide','state_variation','declare_domain','declare_spatial_domain','restrict_to_boundary','expand_normal_derivative','declare_condition','declare_fourier_law','expand_spatial_operators','declare_rate')
FOURIER_FIELDS=('potential','coefficient')
SPATIAL_FIELDS=('chart','coordinates','intervals','parts')
BOUNDARY_FIELDS=('boundary','form')
CONDITION_FIELDS=('conditionKind','coefficient','potential','time','instant','instantUnit','neighborBoundary','neighborSymbol')
CONDITION_KINDS=('initial','dirichlet','neumann','robin','continuity')
CONDITION_FORMS={'initial':('value',),'dirichlet':('value',),'neumann':('gradient','flux'),'robin':('gradient','flux'),'continuity':('value','flux')}



def read_spatial_domain(op):
    """Shape of the additive declare_spatial_domain rule (PDE-1, 5 November 2026)."""
    if op['chart'] not in ('cartesian','cylindrical','spherical'):raise JournalError('Select a supported orthogonal chart.')
    coordinates=op['coordinates']
    if not isinstance(coordinates,list) or not 1<=len(coordinates)<=3 or any(not isinstance(c,str) or not c.strip() or len(c)>160 for c in coordinates) or len(set(coordinates))!=len(coordinates):
        raise JournalError('Select one to three distinct active coordinates.')
    intervals=op['intervals']
    if not isinstance(intervals,list) or len(intervals)!=len(coordinates):raise JournalError('Declare exactly one interval per active coordinate.')
    for interval in intervals:
        keys(interval,['lower','upper','lowerOpen','upperOpen'],['endpointUnit'])
        if any(not isinstance(interval[k],str) or not interval[k].strip() or len(interval[k])>80 for k in ('lower','upper')) or any(type(interval[k]) is not bool for k in ('lowerOpen','upperOpen')):
            raise JournalError('Interval endpoints and openness must be explicit.')
        if 'endpointUnit' in interval and (not isinstance(interval['endpointUnit'],str) or not interval['endpointUnit'].strip() or len(interval['endpointUnit'])>80):
            raise JournalError('Invalid endpoint unit.')
    parts=op['parts']
    if not isinstance(parts,list) or len(parts)>6:raise JournalError('Declare at most six boundary parts.')
    for part in parts:
        keys(part,['name','coordinate','end'])
        if not isinstance(part['name'],str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,40}',part['name']) or part['coordinate'] not in coordinates or part['end'] not in ('lower','upper'):
            raise JournalError('A boundary part needs a name, an active coordinate and its lower or upper end.')


def read_boundary_operation(op):
    """Shape of the additive PDE-2 rules (6 November 2026): boundary restriction,
    normal-derivative expansion and typed initial/boundary conditions."""
    for field in ('boundary','neighborBoundary'):
        if field in op and (not isinstance(op[field],str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,40}',op[field])):
            raise JournalError('Name a declared boundary part of the spatial domain.')
    for field in ('potential','time','neighborSymbol','coefficient','instant','instantUnit'):
        if field in op and (not isinstance(op[field],str) or not op[field].strip() or len(op[field])>(80 if field in ('instant','instantUnit') else 500)):
            raise JournalError('Invalid boundary condition field: '+field+'.')
    if op['kind']=='restrict_to_boundary':
        if op.get('form') not in ('value','flux'):raise JournalError('Restrict to the boundary by value (trace) or by outward normal flux.')
        return
    if op['kind']!='declare_condition':return
    kind=op.get('conditionKind')
    if kind not in CONDITION_KINDS:raise JournalError('Classify the condition as initial, Dirichlet, Neumann, Robin or continuity.')
    form=op.get('form',CONDITION_FORMS[kind][0])
    if form not in CONDITION_FORMS[kind]:
        if kind=='initial':raise JournalError('An initial condition restricts the field in time; it has no outward normal. Select a boundary part for a normal-derivative or flux condition.')
        raise JournalError('A '+kind+' condition does not accept the '+str(form)+' form.')
    if kind!='initial' and 'boundary' not in op:
        raise JournalError('A '+kind+' condition needs an oriented boundary part: without it the outward normal is missing.')
    allowed={'initial':('time','instant','instantUnit'),'dirichlet':(),'neumann':(),'robin':('coefficient','potential'),
             'continuity':('neighborBoundary','neighborSymbol')}[kind]
    if any(field in op and field not in allowed for field in CONDITION_FIELDS if field!='conditionKind'):
        raise JournalError('This field does not belong to a '+kind+' condition.')
    if kind=='initial' and ('boundary' in op or 'time' not in op or 'instant' not in op):
        raise JournalError('An initial condition names its time coordinate and instant, and no boundary part.')
    if 'instantUnit' in op and 'instant' not in op:raise JournalError('An instant unit needs its instant.')
    if kind=='robin' and 'coefficient' not in op:raise JournalError('A Robin condition needs its exchange coefficient.')
    if kind=='robin' and (form=='flux')!=('potential' in op):raise JournalError('A flux-form Robin condition names the potential field whose trace drives the exchange; the gradient form does not.')
    if kind=='continuity':
        if any(field not in op for field in ('neighborBoundary','neighborSymbol')) or 'right' in op:
            raise JournalError('A continuity condition names the neighbouring boundary part and field, and no prescribed value.')
        if len(op.get('domains',[]))!=2:raise JournalError('A continuity condition joins boundary parts of two declared spatial domains.')
    else:
        if 'right' not in op:raise JournalError('A '+kind+' condition needs its prescribed value.')
        if len(op.get('domains',[]))!=1:raise JournalError('Select exactly one declared spatial domain for this condition.')


def read_definition(value):
    keys(value,['format','version','operations','cursor'])
    if value['format']!=FORMAT or type(value['version']) is not int or value['version']!=1:raise JournalError('Unsupported equation workbench version.')
    if not isinstance(value['operations'],list) or len(value['operations'])>400 or type(value['cursor']) is not int or not 0<=value['cursor']<=len(value['operations']):raise JournalError('Invalid equation operation history cursor.')
    for op in value['operations']:
        keys(op,['kind','family'],['sources','symbol','relation','name','unit','left','right','reason','dependencies','relationKind','sourceSignatures','domain','domains','lower','upper','lowerOpen','upperOpen','endpointUnit','source',*SPATIAL_FIELDS,*BOUNDARY_FIELDS,*CONDITION_FIELDS])
        if op['kind'] not in RULES or not isinstance(op['family'],str) or not op['family'].strip() or len(op['family'])>80:raise JournalError('Unknown equation operation or family.')
        for k in ['symbol','relation','name','unit','left','right','reason','endpointUnit']:
            if k in op and (not isinstance(op[k],str) or not op[k].strip() or len(op[k])>500):raise JournalError('Invalid equation operation text.')
        if 'sources' in op and (not isinstance(op['sources'],list) or not op['sources'] or len(op['sources'])>160 or any(not isinstance(s,str) or not s.strip() for s in op['sources']) or len(set(op['sources']))!=len(op['sources'])):raise JournalError('Select distinct equation inputs.')
        if 'dependencies' in op and (not isinstance(op['dependencies'],list) or len(op['dependencies'])>12 or any(not isinstance(s,str) or not s for s in op['dependencies']) or len(set(op['dependencies']))!=len(op['dependencies'])):raise JournalError('Select distinct dependency quantities (at most twelve).')
        if 'dependencies' in op and op['kind'] not in ('declare_function','change_dependencies'):raise JournalError('This operation does not accept dependencies.')
        if 'relationKind' in op and (op['kind'] not in ('declare_relation','declare_rate') or op['relationKind'] not in ('definition','constitutive','constraint')):raise JournalError('Classify a relation as a definition, constitutive relation or condition.')
        # Demo 0.3 C1: a declared rate is a designed law (definition) or a
        # constitutive closure, never a bare condition.
        if op['kind']=='declare_rate' and op.get('relationKind','definition') not in ('definition','constitutive'):raise JournalError('Classify a declared rate as a definition or a constitutive relation.')
        if 'source' in op:
            if op['kind'] not in ('declare_relation','declare_rate') or op.get('relationKind')!='constitutive':raise JournalError('A source belongs to a constitutive relation.')
            source=op['source']
            try:keys(source,['kind','citation','validRange'],['url','table'])
            except JournalError as error:raise JournalError('Relation source: '+str(error)) from error
            for field in source:
                if not isinstance(source[field],str) or not source[field].strip() or len(source[field])>1000 or field=='url' and not re.fullmatch(r'https?://[^\s/\\?#]+(?:[/?#][^\s\\]*)?',source[field],flags=re.IGNORECASE):raise JournalError('Invalid relation source field: '+field+'.')
        if 'domain' in op and (op['kind']!='declare_domain' or op['domain'] not in ('real','positive','nonnegative','negative','nonpositive','nonzero','zero','interval')):raise JournalError('Select a supported real domain.')
        bounds=('lower','upper','lowerOpen','upperOpen')
        if op.get('domain')=='interval':
            if any(field not in op for field in bounds) or any(not isinstance(op[field],str) or not op[field].strip() or len(op[field])>80 for field in ('lower','upper')) or any(type(op[field]) is not bool for field in ('lowerOpen','upperOpen')):raise JournalError('Interval endpoints and openness must be explicit.')
        elif any(field in op for field in bounds):raise JournalError('Endpoint fields belong only to interval domain declarations.')
        if 'endpointUnit' in op and op.get('domain')!='interval':raise JournalError('Endpoint units belong only to interval declarations.')
        if any(field in op for field in SPATIAL_FIELDS) and op['kind']!='declare_spatial_domain':raise JournalError('Chart, coordinates, intervals and boundary parts belong only to spatial domain declarations.')
        if op['kind']=='declare_spatial_domain' and 'reason' in op and 'chart' in op and all(field in op for field in SPATIAL_FIELDS):read_spatial_domain(op)
        if any(field in op for field in BOUNDARY_FIELDS) and op['kind'] not in ('restrict_to_boundary','declare_condition'):raise JournalError('Boundary parts and restriction forms belong only to boundary restrictions and conditions.')
        if any(field in op for field in CONDITION_FIELDS) and op['kind']!='declare_condition' and not (op['kind']=='declare_fourier_law' and all(field in FOURIER_FIELDS for field in CONDITION_FIELDS if field in op)):raise JournalError('Condition fields belong only to typed condition declarations.')
        if op['kind']=='declare_fourier_law' and any(not isinstance(op.get(field),str) or not op[field].strip() or len(op[field])>500 for field in FOURIER_FIELDS):raise JournalError("Fourier's law names the temperature field and the thermal conductivity.")
        if op['kind'] in ('restrict_to_boundary','expand_normal_derivative','expand_spatial_operators') and 'domains' in op and len(op['domains'])!=1:raise JournalError('Select exactly one declared spatial domain.')
        if op['kind'] in ('restrict_to_boundary','declare_condition'):read_boundary_operation(op)
        if op['kind']=='volume_integrate' and 'domains' in op and (not isinstance(op['domains'],list) or len(op['domains'])!=1 or not isinstance(op['domains'][0],str) or not op['domains'][0].strip()):raise JournalError('Select exactly one declared spatial domain for the volume integral.')
        if 'domains' in op and (op['kind'] not in ('isolate','substitute','volume_integrate','declare_relation','restrict_to_boundary','expand_normal_derivative','declare_condition','expand_spatial_operators') or not isinstance(op['domains'],list) or not op['domains'] or len(op['domains'])>24 or any(not isinstance(s,str) or not s.strip() for s in op['domains']) or len(set(op['domains']))!=len(op['domains'])):raise JournalError('Select distinct recorded domain conditions (at most twenty-four).')
        required={'state_variation':['sources','symbol','right','reason'],'declare_domain':['sources','symbol','domain','reason'],'declare_spatial_domain':['sources','chart','coordinates','intervals','parts','reason'],'combine':['sources'],'substitute':['sources','relation','symbol'],'isolate':['sources','symbol'],'expand':['sources'],'factor':['sources'],'differentiate':['sources','symbol'],'integrate':['sources','symbol','name'],'volume_integrate':['sources'],'gauss':['sources'],'reynolds':['sources'],'zero':['sources','symbol','reason'],'apply_zero':['sources','symbol','reason'],'declare_symbol':['name','unit'],'declare_function':['name','unit','dependencies'],'change_dependencies':['sources','symbol','dependencies','reason'],'declare_relation':['left','right','reason'],'declare_rate':['symbol','right','reason'],'restrict_to_boundary':['sources','domains','boundary','form'],'expand_normal_derivative':['sources','domains'],'declare_condition':['sources','domains','conditionKind','symbol','reason'],'declare_fourier_law':['sources','symbol','potential','coefficient'],'expand_spatial_operators':['sources','domains'],'multiply':['sources','right'],'divide':['sources','right']}[op['kind']]
        if any(k not in op for k in required):raise JournalError('The equation operation is missing its inputs.')
        if op['kind']!='combine' and 'sources' in op and len(op['sources'])!=1:raise JournalError('This operation acts on one selected equation.')
        if 'sourceSignatures' in op:
            signatures=op['sourceSignatures'];expected=set(op.get('sources',[]))|({op['relation']} if op['kind']=='substitute' else set())|set(op.get('domains',[]))
            if not isinstance(signatures,dict) or set(signatures)!=expected or any(not isinstance(v,str) or not re.fullmatch('[0-9a-f]{64}',v) for v in signatures.values()):
                raise JournalError('Source signatures must cover exactly the input equations and substitution relation.')
    return value

