"""Bind an admitted explicit template plan to a verified instance identity map.

Only in-process expansion results may enter this adapter. The equation workbench
has already replayed their source and proved the target signatures. Mutable
closure caches and seeds never travel between instances. Uncached preparation
remains the reference, and unsupported plans use ordinary DerivedSystem.
"""
import copy
import hashlib
import json
from collections import OrderedDict
from threading import RLock
from dataclasses import fields, is_dataclass
import re
from types import MappingProxyType
from types import SimpleNamespace

import numpy as np
import sympy as sp

from core.mathematics.preparation import enabled
from .derived import DerivedSystem

_plans = OrderedDict()
_plan_lock = RLock()


def compile_template(model):
    """Bounded internal plan cache, never a cache of solved instance state.

    Include the complete recipe, data, selection, source identities, producer
    revision and proof context. Plans stay private to preparation; each
    instance gets a fresh runtime through bind_stage.
    """
    if not enabled():
        return DerivedSystem(model)
    from core.modelo.equation_workbench import SOURCE_REVISION
    key = hashlib.sha256(json.dumps([SOURCE_REVISION,model,
        sorted(sp.srepr(a) for a in sp.assumptions.global_assumptions)],
        sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()
    with _plan_lock:
        if key in _plans:
            _plans.move_to_end(key)
            return _plans[key]
    plan = DerivedSystem(copy.deepcopy(model))
    with _plan_lock:
        _plans[key] = plan
        while len(_plans)>4:
            _plans.popitem(last=False)
    return plan


class IdentityBinding:
    # These fields contain protocol/physical literals, not model identities.
    # An outlet named "liquid" must not rename the formation anchor or phase.
    LITERAL_FIELDS = frozenset({'kind','anchor','mode','format','unit','unitSI','spec','specification',
        'closureStrategy','candidatePhases','phaseSet','phases','phase','fase','tipo','family','rule',
        'relationKind','domain','status','signature_status','method','metodo','metodoSolicitado'})
    def __init__(self, source, instance):
        self.source = source
        self.instance = instance
        mapping = instance['provenance']['identityMap']
        self.owners = {**mapping['volumes'], **mapping['streams'], **mapping['exchanges']}
        self.identities = {**mapping['equations'], **mapping['quantities'], **mapping['ports'],
                           **self.owners, source.model['id']:instance['model']['id']}
        self.memo = {}
        self.parameters = {}
        for quantity, symbol in source.parameter_symbols.items():
            if str(symbol).startswith('package_'):
                mapped = self.expression(quantity)
                target = sp.Symbol('package_'+hashlib.sha256(sp.srepr(mapped).encode()).hexdigest()[:12],real=True)
                self.parameters[symbol] = target
                self.identities[str(symbol)] = str(target)

    def name(self, value):
        for old, new in self.owners.items():
            value = re.sub(r'(?<=__)'+re.escape(old)+r'(?=__|$|\()', lambda _:new, value)
        return value

    def expression(self, value):
        symbols = {q:sp.Symbol(self.name(str(q)), **q._assumptions_orig)
                   for q in value.atoms(sp.Symbol) if self.name(str(q)) != str(q)}
        functions = {}
        for q in sorted(value.atoms(sp.core.function.AppliedUndef), key=lambda q:len(sp.srepr(q))):
            name = self.name(q.func.__name__)
            args = tuple(a.xreplace({**symbols, **functions}) for a in q.args)
            functions[q] = (sp.Function(name, **q.func._kwargs) if name != q.func.__name__ else q.func)(*args)
        mapping = {**symbols, **functions, **getattr(self,'parameters',{})}
        if isinstance(value, sp.Equality):
            return sp.Eq(value.lhs.xreplace(mapping), value.rhs.xreplace(mapping), evaluate=False)
        return value.xreplace(mapping)

    def bind(self, value):
        if isinstance(value, sp.Basic):
            if id(value) not in self.memo:
                self.memo[id(value)] = self.expression(value)
            return self.memo[id(value)]
        if isinstance(value, str):
            if value in self.identities:
                return self.identities[value]
            # Transform datum ids embed the selected equation id. Match the
            # complete equation token, not arbitrary owner text in labels.
            if value.startswith('steadyTransform.'):
                for old, new in self.instance['provenance']['identityMap']['equations'].items():
                    prefix = 'steadyTransform.' + old + '.'
                    if value.startswith(prefix):
                        return 'steadyTransform.' + new + value[len(prefix)-1:]
            for old, new in self.instance['provenance']['identityMap']['equations'].items():
                if value.startswith(old + '.'):
                    return new + value[len(old):]
            value = self.name(value)
            value = value.replace(self.source.model['id']+'.derived',self.instance['model']['id']+'.derived')
            return re.sub(r'(?<![a-zA-Z0-9])(?:x[0-9a-f]{10}|package_[0-9a-f]{12})(?![a-zA-Z0-9])',
                          lambda match:self.identities.get(match[0],match[0]),value)
        if value is None or isinstance(value, (bool, int, float)):
            return value
        if id(value) in self.memo:
            return self.memo[id(value)]
        if isinstance(value, np.ndarray):
            return value.copy()
        if isinstance(value, (dict, MappingProxyType)):
            result = {}; self.memo[id(value)] = result
            result.update((k,copy.deepcopy(v)) if k in self.LITERAL_FIELDS else (self.bind(k),self.bind(v))
                          for k,v in value.items())
            return MappingProxyType(result) if isinstance(value, MappingProxyType) else result
        if isinstance(value, (list, tuple, set, frozenset)):
            return type(value)(self.bind(v) for v in value)
        if is_dataclass(value):
            result = type(value)(**{f.name:self.field(f.name,getattr(value,f.name)) for f in fields(value)})
            self.memo[id(value)] = result
            return result
        if callable(value):
            # Pure numeric AST kernels bind slot indices and scalar constants.
            # Runtime wrappers capturing a system are rebuilt below.
            return value
        if hasattr(value, '__dict__'):
            result = type(value).__new__(type(value)); self.memo[id(value)] = result
            result.__dict__.update({k:self.field(k,v) for k,v in value.__dict__.items()})
            return result
        return copy.deepcopy(value)

    def field(self,key,value):
        return copy.deepcopy(value) if key in self.LITERAL_FIELDS else self.bind(value)


def bind_stage(source, instance):
    if not enabled() or source.nonlinear or source.scaled is not None or source.algebraic_block is not None:
        return DerivedSystem(instance['model'])
    binder = IdentityBinding(source, instance)
    stage = DerivedSystem.__new__(DerivedSystem)
    binder.memo[id(source)] = stage
    excluded = {'model','selection','numeric','block_jacobian','jacobian','report','runtime_guards','closures','replayed','graph'}
    for key,value in source.__dict__.items():
        if key not in excluded:
            setattr(stage,key,binder.field(key,value))
    stage.model = copy.deepcopy(instance['model'])
    stage.lowered['nombre'] = stage.model['nombre']
    stage.lowered['datos'].update(copy.deepcopy(stage.model['datos']))
    stage.selection = stage.model['motores']['derivedExecution']
    from core.modelo.template_replay import bind_replay
    from core.modelo.equation_workbench import _known_unit
    mapping = instance['provenance']['identityMap']
    stage.replayed = bind_replay(source.replayed, stage.model['motores']['equationWorkbench'],
        binder.expression, lambda key: mapping['equations'].get(key,key),
        mapping['quantities'], binder.owners, _known_unit)
    stage.graph = stage.replayed.graph
    expected = binder.bind(source.selection)
    expected['sourceSignature'] = stage.selection['sourceSignature']
    if expected != stage.selection:
        raise ValueError('Verified instance selection differs from the generic compiled plan.')
    stage.closures = []
    for closure in source.closures:
        target = type(closure).__new__(type(closure)); binder.memo[id(closure)] = target
        for key,value in closure.__dict__.items():
            if key not in ('cache','seed','fingerprint','evaluations','system','inputs'):
                setattr(target,key,binder.field(key,value))
        target.system = stage; target.cache = {}; target.seed = None
        # The package fingerprint is immutable admission provenance. Runtime
        # caches and Newton seeds are independent, but the report must retain
        # the certified generic package identity before its first evaluation.
        target.fingerprint = closure.fingerprint; target.evaluations = 0
        stage.closures.append(target)
    if stage.closures:
        from .derived_closure import ClosureRuntime
        stage.numeric = ClosureRuntime(stage)
    else:
        from .explicito import SistemaExplicito
        stage.numeric = SistemaExplicito(stage.lowered)
    stage.runtime_guards = [(stage.numeric._compilar(stage._ast(e),'derived validity'),strict,key,label)
                            for e,strict,key,label in stage.margins]
    stage.configure_jacobian()
    stage.report = stage._report()
    return stage


def bind_steady_defaults(source_dynamic, source_steady, transform, instance):
    """Reuse generic zero-rate admission/defaults; network residuals remain global.

    This returns metadata and numerical arrays only, never a second solver or
    a callable retaining another stage's closure state.
    """
    from .steady import signature, read_report
    # Existing Transform data may retain user-edited identities. Their collision
    # and reuse rules belong to the ordinary Transform; do not guess a remap.
    if any(key.startswith('steadyTransform.') for key in source_dynamic.model['datos']):
        from core.modelo.steady_transform import prepare_steady_transform
        from .steady import SteadySystem
        transformed = prepare_steady_transform(instance['model'])
        return transformed, SteadySystem(transformed['model'])
    binding = IdentityBinding(source_dynamic,instance)
    model = copy.deepcopy(instance['model'])
    for key,datum in transform['model']['datos'].items():
        if source_dynamic.model['datos'].get(key) != datum:
            model['datos'][binding.bind(key)] = binding.bind(datum)
    selected = binding.bind(source_steady.selection)
    selected['sourceSignature'] = model['motores']['derivedExecution']['sourceSignature']
    model['motores']['derivedExecution'] = selected
    model['estudio'] = copy.deepcopy(transform['model']['estudio'])
    report = binding.bind(source_steady.report)
    report.update(selection=selected,sourceModelId=model['id'],sourceSignature=selected['sourceSignature'],
        formulationSignature=signature(selected),settingsSignature=signature(selected['nonlinear']),
        dataSignature=signature({k:v['declaracion'] for k,v in model['datos'].items()}),
        signature=signature([selected,model['datos'],model['estudio']]))
    read_report(report)
    stage = SimpleNamespace(selection=selected,config=selected['nonlinear'],report=report,
        seed=source_steady.seed.copy(),bounds=source_steady.bounds.copy(),scales=source_steady.scales.copy(),
        residual_scales=source_steady.residual_scales.copy(),checks=binding.bind(source_steady.checks))
    transformed = {'format':'rage.steady-transform','version':1,'model':model,
        'dynamicSelection':copy.deepcopy(instance['model']['motores']['derivedExecution']),
        'dynamicSignature':signature(instance['model']['motores']['derivedExecution']),'report':report}
    return transformed,stage
