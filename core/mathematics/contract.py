"""Strict, compatible operation records; group labels have no mathematical meaning."""
import re
from .errors import MathematicsError as JournalError


def keys(value,required,optional=()):
    if not isinstance(value,dict) or set(value)-set(required)-set(optional) or set(required)-set(value):
        raise JournalError('Unknown or missing equation operation fields.')


FORMAT='rage.equation-workbench'
RULES=('combine','substitute','isolate','expand','factor','differentiate','integrate','volume_integrate','gauss','reynolds','zero','apply_zero','declare_symbol','declare_function','change_dependencies','declare_relation','multiply','divide','declare_domain')


def read_definition(value):
    keys(value,['format','version','operations','cursor'])
    if value['format']!=FORMAT or type(value['version']) is not int or value['version']!=1:raise JournalError('Unsupported equation workbench version.')
    if not isinstance(value['operations'],list) or len(value['operations'])>400 or type(value['cursor']) is not int or not 0<=value['cursor']<=len(value['operations']):raise JournalError('Invalid equation operation history cursor.')
    for op in value['operations']:
        keys(op,['kind','family'],['sources','symbol','relation','name','unit','left','right','reason','dependencies','relationKind','sourceSignatures','domain','domains','lower','upper','lowerOpen','upperOpen','endpointUnit'])
        if op['kind'] not in RULES or not isinstance(op['family'],str) or not op['family'].strip() or len(op['family'])>80:raise JournalError('Unknown equation operation or family.')
        for k in ['symbol','relation','name','unit','left','right','reason','endpointUnit']:
            if k in op and (not isinstance(op[k],str) or not op[k].strip() or len(op[k])>500):raise JournalError('Invalid equation operation text.')
        if 'sources' in op and (not isinstance(op['sources'],list) or not op['sources'] or len(op['sources'])>160 or any(not isinstance(s,str) or not s.strip() for s in op['sources']) or len(set(op['sources']))!=len(op['sources'])):raise JournalError('Select distinct equation inputs.')
        if 'dependencies' in op and (not isinstance(op['dependencies'],list) or len(op['dependencies'])>12 or any(not isinstance(s,str) or not s for s in op['dependencies']) or len(set(op['dependencies']))!=len(op['dependencies'])):raise JournalError('Select distinct dependency quantities (at most twelve).')
        if 'dependencies' in op and op['kind'] not in ('declare_function','change_dependencies'):raise JournalError('This operation does not accept dependencies.')
        if 'relationKind' in op and (op['kind']!='declare_relation' or op['relationKind'] not in ('definition','constitutive','constraint')):raise JournalError('Classify a relation as a definition, constitutive relation or condition.')
        if 'domain' in op and (op['kind']!='declare_domain' or op['domain'] not in ('real','positive','nonnegative','negative','nonpositive','nonzero','zero','interval')):raise JournalError('Select a supported real domain.')
        bounds=('lower','upper','lowerOpen','upperOpen')
        if op.get('domain')=='interval':
            if any(field not in op for field in bounds) or any(not isinstance(op[field],str) or not op[field].strip() or len(op[field])>80 for field in ('lower','upper')) or any(type(op[field]) is not bool for field in ('lowerOpen','upperOpen')):raise JournalError('Interval endpoints and openness must be explicit.')
        elif any(field in op for field in bounds):raise JournalError('Endpoint fields belong only to interval domain declarations.')
        if 'endpointUnit' in op and op.get('domain')!='interval':raise JournalError('Endpoint units belong only to interval declarations.')
        if 'domains' in op and (op['kind'] not in ('isolate','substitute') or not isinstance(op['domains'],list) or not op['domains'] or len(op['domains'])>24 or any(not isinstance(s,str) or not s.strip() for s in op['domains']) or len(set(op['domains']))!=len(op['domains'])):raise JournalError('Select distinct recorded domain conditions (at most twenty-four).')
        required={'declare_domain':['sources','symbol','domain','reason'],'combine':['sources'],'substitute':['sources','relation','symbol'],'isolate':['sources','symbol'],'expand':['sources'],'factor':['sources'],'differentiate':['sources','symbol'],'integrate':['sources','symbol','name'],'volume_integrate':['sources'],'gauss':['sources'],'reynolds':['sources'],'zero':['sources','symbol','reason'],'apply_zero':['sources','symbol','reason'],'declare_symbol':['name','unit'],'declare_function':['name','unit','dependencies'],'change_dependencies':['sources','symbol','dependencies','reason'],'declare_relation':['left','right','reason'],'multiply':['sources','right'],'divide':['sources','right']}[op['kind']]
        if any(k not in op for k in required):raise JournalError('The equation operation is missing its inputs.')
        if op['kind']!='combine' and 'sources' in op and len(op['sources'])!=1:raise JournalError('This operation acts on one selected equation.')
        if 'sourceSignatures' in op:
            signatures=op['sourceSignatures'];expected=set(op.get('sources',[]))|({op['relation']} if op['kind']=='substitute' else set())|set(op.get('domains',[]))
            if not isinstance(signatures,dict) or set(signatures)!=expected or any(not isinstance(v,str) or not re.fullmatch('[0-9a-f]{64}',v) for v in signatures.values()):
                raise JournalError('Source signatures must cover exactly the input equations and substitution relation.')
    return value

