"""Bounded preparation reuse, with an explicit uncached reference policy.

No numerical state, closure seed, solver result or failure is cached here.
Keys include the entire input document, operation recipe, identities and source
revision. Every hit returns independent mutable graph/metadata containers.
"""
from collections import OrderedDict
import copy
from dataclasses import replace
import hashlib
import json
import sympy as sp
from threading import RLock
from core.mathematics.preparation import enabled, preparation_policy

_builds = OrderedDict()
_lock = RLock()
_counts = {'hits':0,'misses':0}
LIMIT = 8


def clear():
    with _lock:
        _builds.clear()
        _counts.update(hits=0,misses=0)


def evidence():
    with _lock:
        return {'version':1,'selected':'cached' if enabled() else 'uncached',
                'rule':'exact document/recipe/identity/revision match; bounded memory; independent graph copies',
                'entries':len(_builds),**_counts}


def _clone(result):
    # Receipts and SymPy expressions are immutable; MappingProxyType receipts
    # deliberately cannot be deep-copied. The graph has its own safe copier.
    return replace(result, graph=copy.deepcopy(result.graph),selected=list(result.selected),
                   owners=dict(result.owners),units=dict(result.units),
                   definition=copy.deepcopy(result.definition),introduced=dict(result.introduced))


def _key(model, definition, unbound, revision):
    identity = {'model':model.get('id'),'volumes':[v['id'] for v in model.get('volumenes',[])],
                'streams':[s['id'] for s in model.get('corrientes',[])]}
    recipe = hashlib.sha256(json.dumps([revision,model,definition,unbound],
        sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    return (recipe,json.dumps(identity,sort_keys=True),frozenset(sp.assumptions.global_assumptions))


def remember_verified_instance(model, result, revision):
    """Internal alpha-renaming proof boundary, never populated from wire provenance."""
    if not enabled():
        return
    key = _key(model, result.definition, False, revision)
    with _lock:
        _builds[key] = _clone(result)
        while len(_builds) > LIMIT:
            _builds.popitem(last=False)


def replay_build(model, definition, unbound, revision, build):
    if not enabled():
        return build()
    key = _key(model, definition, unbound, revision)
    with _lock:
        if key in _builds:
            _counts['hits'] += 1
            _builds.move_to_end(key)
            return _clone(_builds[key])
        _counts['misses'] += 1
    result = build()  # Never cache rejected or partially replayed recipes.
    if any(r.signature_status == 'legacy/unsigned' for r in result.receipts):
        return result
    with _lock:
        _builds[key] = _clone(result)
        while len(_builds)>LIMIT:
            _builds.popitem(last=False)
    return result
