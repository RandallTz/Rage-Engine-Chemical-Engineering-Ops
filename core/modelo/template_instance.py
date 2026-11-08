"""Atomic template instantiation by verified alpha-renaming and journal replay."""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import replace
import hashlib
import json
import re
from threading import RLock
from uuid import uuid4
import sympy as sp
from core.modelo.lector import leer_modelo_comun, ErrorModelo
from core.modelo.equation_workbench import build, _known_unit
from core.mathematics.dimensions import catalog
from core.mathematics.provenance import equation_signature
from core.compilador.derived_graph import source_signature


class TemplateInstanceError(ValueError):
    def __init__(self, path, message):
        super().__init__(message)
        self.diagnostics = [{'code': 'template_replay_failed', 'path': path, 'message': message}]


# Physical journals whose identity references are remapped field by field.
# Any other field that names a volume, stream or exchange identity is rejected
# (RI-2), because the identity map would leave it stale.
_PHYSICAL_JOURNALS = ('materialDerivation', 'energyDerivation', 'thermodynamicDerivation',
                      'momentumDerivation', 'kineticReactions')
_REMAPPED_CHANGES = {'momentumDerivation': ('inletStreamId', 'outletStreamId')}

# Source recipes whose rebinding has matched one uncached replay of the target
# in this process (RI-1). Keyed by revision, the whole source document and the
# whole recorded history, so any change to the template replays cold again.
_COLD_VERIFIED = OrderedDict()
_COLD_LIMIT = 64
_cold_lock = RLock()


def _cold_key(source, definition, revision):
    return hashlib.sha256(json.dumps([revision, source, definition], sort_keys=True,
        separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _reject_unmapped_identities(source, identities):
    def scan(value, path):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in identities:
                    raise TemplateInstanceError(path + '.' + key, f'This journal key names the identity {key!r}, which the identity map does not rewrite; a dedicated identity adapter is required.')
                scan(item, path + '.' + key)
        elif isinstance(value, list):
            for i, item in enumerate(value):
                scan(item, f'{path}[{i}]')
        elif isinstance(value, str) and value in identities:
            raise TemplateInstanceError(path, f'This journal field names the identity {value!r}, which the identity map does not rewrite; a dedicated identity adapter is required.')
    for name in _PHYSICAL_JOURNALS:
        journal = source['motores'].get(name)
        if not isinstance(journal, dict) or not isinstance(journal.get('volumes'), dict):
            continue
        for owner, entry in journal['volumes'].items():
            base = f'motores.{name}.volumes.{owner}'
            if not isinstance(entry, dict):
                continue
            for key, value in entry.items():
                if key == 'origin':
                    continue
                if key != 'operations' or not isinstance(value, list):
                    scan(value, base + '.' + key)
                    continue
                for i, op in enumerate(value):
                    if not isinstance(op, dict):
                        continue
                    for field, item in op.items():
                        path = f'{base}.operations[{i}].{field}'
                        if field in ('id', 'title'):
                            continue  # operation identity and prose, never physical identities
                        if field == 'changes' and isinstance(item, dict):
                            for change, setting in item.items():
                                if change not in _REMAPPED_CHANGES.get(name, ()):
                                    scan(setting, path + '.' + change)
                        else:
                            scan(item, path)


def instantiate_template(source, *, identity_namespace=None):
    path = 'template.recipe'
    try:
        return _instantiate(source, identity_namespace=identity_namespace)
    except TemplateInstanceError:
        raise
    except ErrorModelo as error:
        raise TemplateInstanceError(error.ruta, error.mensaje) from error
    except (ValueError, KeyError, TypeError, NotImplementedError) as error:
        raise TemplateInstanceError(path, str(error)) from error


def _instantiate(source, *, identity_namespace=None):
    source = deepcopy(leer_modelo_comun(source))
    if 'indexSet' in source:
        raise TemplateInstanceError('indexSet', 'Use indexed expansion for a stage network; a network is not one template instance.')
    if 'template' not in source:
        raise TemplateInstanceError('template', 'This model has no recorded template recipe.')
    for journal in source['template']['recipe']['journals']:
        if not isinstance(source['motores'].get(journal), dict):
            raise TemplateInstanceError('template.recipe.journals', 'Every recipe reference must name a recorded journal object.')
    if source['matematico'] is not None or any(key in source['motores'] for key in ('adimensionalizacion', 'hydraulicNetwork')):
        raise TemplateInstanceError('template.recipe', 'Explicit mathematical documents, scaling and separate hydraulic configurations require a dedicated identity adapter; no formula is copied as a deduction.')
    definition = deepcopy(source['motores'].get('equationWorkbench', {'format':'rage.equation-workbench','version':1,'operations':[],'cursor':0}))
    full = {**definition, 'cursor': len(definition['operations'])}
    # Validate all recorded signatures, including redo history, before rebinding.
    try:
        replayed = build(source, full)
    except ValueError as error:
        raise TemplateInstanceError('motores.equationWorkbench', str(error)) from error
    if any(r.signature_status == 'legacy/unsigned' for r in replayed.receipts):
        raise TemplateInstanceError('motores.equationWorkbench', 'Unsigned history cannot certify a template instance. Review the source operations first.')
    active = build(source, definition)
    selection = source['motores'].get('derivedExecution')
    if selection and selection['sourceSignature'] != source_signature(source, active):
        raise TemplateInstanceError('motores.derivedExecution.sourceSignature', 'The source selection is stale; no earlier selection will be copied.')

    sequence = {}
    def fresh(prefix):
        if identity_namespace is None: return prefix+'_'+uuid4().hex[:16]
        sequence[prefix] = sequence.get(prefix, 0) + 1
        token = hashlib.sha256((identity_namespace + ':' + prefix + ':' + str(sequence[prefix])).encode()).hexdigest()[:24]
        return prefix + '_' + token
    maps = {key: {row['id']: fresh(prefix) for row in rows} for key, rows, prefix in
            [('volumes',source['volumenes'],'volume'), ('streams',source['corrientes'],'stream'),
             ('exchanges',source['intercambios'],'exchange'), ('ports',source['template']['ports'],'port')]}
    owners = {**maps['volumes'], **maps['streams'], **maps['exchanges']}
    if len(owners) != sum(len(maps[k]) for k in ('volumes','streams','exchanges')):
        raise TemplateInstanceError('template.recipe', 'Overlapping volume/stream/exchange names require an unambiguous identity adapter.')
    _reject_unmapped_identities(source, set(owners))

    def symbol_name(name):
        # Physical producers delimit owner identities with double underscores.
        for old,new in owners.items():
            name=re.sub(r'(?<=__)'+re.escape(old)+r'(?=__|$)',lambda _:new,name)
        return name

    def expression(value):
        symbols={q:sp.Symbol(symbol_name(str(q)), **q._assumptions_orig) for q in value.atoms(sp.Symbol) if symbol_name(str(q))!=str(q)}
        functions={}
        for q in sorted(value.atoms(sp.core.function.AppliedUndef),key=lambda q:len(sp.srepr(q))):
            name=symbol_name(q.func.__name__)
            args=tuple(a.xreplace({**symbols,**functions}) for a in q.args)
            functions[q]=(sp.Function(name, **q.func._kwargs) if name!=q.func.__name__ else q.func)(*args)
        replacements={**symbols,**functions}
        if isinstance(value,sp.Equality):
            return sp.Eq(value.lhs.xreplace(replacements),value.rhs.xreplace(replacements),evaluate=False)
        return value.xreplace(replacements)

    def equation_id(key):
        for old,new in owners.items():
            key=re.sub(r'(?<=\.)'+re.escape(old)+r'(?=\.|$)',lambda _:new,key)
        if key.startswith('thermodynamics.'):
            for old,new in maps['streams'].items():
                key=re.sub(r'(?<=-)'+re.escape(old)+r'$',lambda _:new,key)
        return key

    quantities={**catalog(replayed.graph,replayed.units),**replayed.introduced}
    qmap={key: ('x'+hashlib.sha256(sp.srepr(expression(q)).encode()).hexdigest()[:10] if re.fullmatch(r'x[0-9a-f]{10}',key) else key)
          for key,q in quantities.items()}
    maps['quantities']=qmap
    maps['equations']={key:equation_id(key) for key in replayed.graph.nodes}

    def operation_value(value):
        if isinstance(value,list): return [operation_value(v) for v in value]
        if isinstance(value,dict): return {operation_value(k):operation_value(v) for k,v in value.items()}
        if isinstance(value,str):
            if value in maps['equations']: return maps['equations'][value]
            return re.sub(r'\bx[0-9a-f]{10}\b',lambda m:qmap.get(m[0],m[0]),value)
        return value

    target=deepcopy(source)
    target['id']=fresh('model');target['nombre']=source['nombre']+' · instance'
    target['motores'].pop('derivedExecution',None)
    for volume in target['volumenes']: volume['id']=maps['volumes'][volume['id']]
    for field,map_key in [('corrientes','streams'),('intercambios','exchanges')]:
        for boundary in target[field]:
            boundary['id']=maps[map_key][boundary['id']]
            for end in ('desde','hasta'):
                if boundary[end] is not None: boundary[end]=maps['volumes'][boundary[end]]
            if 'extraccion' in boundary: boundary['extraccion']={maps['volumes'][k]:v for k,v in boundary['extraccion'].items()}
    for datum in target['datos'].values():
        owner=datum['origen']['propietarioId']
        for prefix,mapping in [('volumen:',maps['volumes']),('corriente:',maps['streams']),('intercambio:',maps['exchanges'])]:
            if owner.startswith(prefix) and owner[len(prefix):] in mapping: datum['origen']['propietarioId']=prefix+mapping[owner[len(prefix):]]
    for name,journal in target['motores'].items():
        if name in ('materialDerivation','energyDerivation','thermodynamicDerivation','momentumDerivation','kineticReactions'):
            journal['volumes']={maps['volumes'][owner]:entry for owner,entry in journal['volumes'].items()}
            if name=='momentumDerivation':
                for entry in journal['volumes'].values():
                    for op in entry['operations']:
                        for key in ('inletStreamId','outletStreamId'):
                            if op['changes'].get(key) is not None:op['changes'][key]=maps['streams'][op['changes'][key]]
        if name=='dynamicDefinition':
            for op in journal['operations']:
                op['volumeId']=maps['volumes'][op['volumeId']]
                if 'dependent' in op:
                    binding=op['dependent'];mapping=maps['exchanges'] if binding['kind']=='heat_flow' else maps['streams']
                    binding['id']=mapping[binding['id']]
    for port in target['template']['ports']:
        port['id']=maps['ports'][port['id']];port['volumeId']=maps['volumes'][port['volumeId']]
        if port['boundary']['type'] in ('stream','exchange'):
            port['boundary']['id']=maps['streams' if port['boundary']['type']=='stream' else 'exchanges'][port['boundary']['id']]

    remapped=operation_value(full)
    for op in remapped['operations']:op.pop('sourceSignatures',None)
    target['motores']['equationWorkbench']=remapped
    from .preparation_cache import enabled, remember_verified_instance
    from .equation_workbench import SOURCE_REVISION
    from .template_replay import bind_replay
    from core.mathematics.preparation import preparation_policy
    try:
        rebuilt = (bind_replay(replayed,remapped,expression,equation_id,qmap,owners,_known_unit)
                   if enabled() else build(target,remapped))
    except ValueError as error: raise TemplateInstanceError('motores.equationWorkbench',str(error)) from error
    expected=deepcopy(replayed.graph)
    expected.nodes={equation_id(key):replace(node,equation=expression(node.equation),
        inputs=tuple(equation_id(i) for i in node.inputs),predicates=tuple(expression(p) for p in node.predicates),
        branches=tuple((expression(eq),admitted) for eq,admitted in node.branches)) for key,node in replayed.graph.nodes.items()}
    units={expression(q):unit for q,unit in replayed.units.items()}
    def certify(candidate):
        if set(expected.nodes)!=set(candidate.graph.nodes):
            raise TemplateInstanceError('template.recipe','The identity map changed the set of deduced equations.')
        result={}
        for old,key in maps['equations'].items():
            wanted=equation_signature(expected,key,units,_known_unit)
            actual=equation_signature(candidate.graph,key,candidate.units,_known_unit)
            a,b=expected.nodes[key],candidate.graph.nodes[key]
            if wanted!=actual or (a.rule,a.inputs,a.family)!=(b.rule,b.inputs,b.family):
                raise TemplateInstanceError('equations.'+old,'The replayed deduction differs under the identity map.')
            result[old]={'instanceId':key,'signature':actual}
        return result
    signatures=certify(rebuilt)
    # Rebind only after proving equivalence to the fully signed source history.
    for op,receipt in zip(remapped['operations'],rebuilt.receipts):
        if receipt.calculated_input_signatures:op['sourceSignatures']=dict(receipt.calculated_input_signatures)
    remapped['cursor']=definition['cursor']
    target['motores']['equationWorkbench']=remapped
    if enabled():
        verified=bind_replay(active,remapped,expression,equation_id,qmap,owners,_known_unit)
    else:
        verified=build(target)
    # RI-1: the rebinding is checked above against the same renaming that
    # produced it. Before it may seed the cache, the target's own journals are
    # replayed once uncached and must match it: the full history (which also
    # validates the pinned input signatures) and the active selection. One
    # matching cold replay per exact source recipe and revision covers later
    # instances of it, which differ only in fresh identity tokens.
    cold_key=_cold_key(source,full,SOURCE_REVISION)
    with _cold_lock:
        known=cold_key in _COLD_VERIFIED
    if enabled() and not known:
        whole={**remapped,'cursor':len(remapped['operations'])}
        try:
            with preparation_policy(cached=False):
                cold=build(deepcopy(target),deepcopy(whole))
                cold_active=cold if remapped['cursor']==whole['cursor'] else build(deepcopy(target))
        except ValueError as error:
            raise TemplateInstanceError('motores.equationWorkbench','The instance does not replay from its own journals: '+str(error)) from error
        def receipt_inputs(result):
            return [dict(r.calculated_input_signatures) for r in result.receipts]
        if certify(cold)!=signatures:
            raise TemplateInstanceError('template.recipe','The rebound instance differs from the uncached replay of its own journals.')
        if receipt_inputs(cold)!=receipt_inputs(rebuilt) or cold.graph.domains!=rebuilt.graph.domains:
            raise TemplateInstanceError('motores.equationWorkbench','The rebound input signatures or domains differ from the uncached replay of the instance.')
        if source_signature(target,cold_active)!=source_signature(target,verified):
            raise TemplateInstanceError('motores.equationWorkbench','The rebound active selection differs from the uncached replay of the instance.')
        known=True
    elif not enabled():
        known=True  # this whole instance was replayed uncached
    if known:
        with _cold_lock:
            _COLD_VERIFIED[cold_key]=True
            _COLD_VERIFIED.move_to_end(cold_key)
            while len(_COLD_VERIFIED)>_COLD_LIMIT:_COLD_VERIFIED.popitem(last=False)
    if selection:
        selected=operation_value(selection);selected['sourceSignature']=source_signature(target,verified)
        target['motores']['derivedExecution']=selected
    provenance={'format':'rage.template-instance','version':1,'sourceModelId':source['id'],
        'templateId':source['template']['id'],'templateVersion':source['template']['templateVersion'],
        'equipment':source['template']['equipment'],'identityMap':maps,
        'sourceSignature':source_signature(source,active),'instanceSignature':source_signature(target,verified),
        'equationSignatures':signatures}
    target['procedencia']={**target['procedencia'],'templateInstance':provenance}
    leer_modelo_comun(target)
    remember_verified_instance(target,verified,SOURCE_REVISION)
    return {'format':'rage.template-instance.response','version':1,'model':target,'provenance':provenance}
