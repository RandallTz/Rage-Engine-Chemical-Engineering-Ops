"""Generic explicit-plan binding versus independent per-instance lowering."""
import numpy as np
import sympy as sp
import json
from pathlib import Path

from core.compilador.derived import DerivedSystem
from core.compilador.indexed_network import IndexedDerivedSystem
from core.compilador.indexed_steady import IndexedSteadySystem
from core.compilador.template_lowering import bind_stage
from core.mathematics.preparation import preparation_policy
from core.modelo.index_sets import expand_index_set
from test_index_sets import source_model


def test_stream_identity_does_not_rename_physical_phase_or_anchor_literals():
    from types import SimpleNamespace
    from core.compilador.template_lowering import IdentityBinding
    source=SimpleNamespace(model={'id':'source'},parameter_symbols={})
    instance={'model':{'id':'target'},'provenance':{'identityMap':{
        'volumes':{'cell':'volume_1'},'streams':{'liquid':'stream_1'},'exchanges':{},'ports':{},'equations':{},'quantities':{}}}}
    binding=IdentityBinding(source,instance)
    assert binding.bind({'volumeId':'cell','id':'liquid','anchor':'liquid','kind':'liquid'})=={
        'volumeId':'volume_1','id':'stream_1','anchor':'liquid','kind':'liquid'}
    closure=binding.bind(SimpleNamespace(owner='cell',anchor='liquid',kind='liquid',phase='liquid'))
    assert (closure.owner,closure.anchor,closure.kind)==('volume_1','liquid','liquid')
    assert closure.phase=='liquid'


def test_generic_plan_cache_pins_recipe_data_identity_and_proof_context(monkeypatch):
    from copy import deepcopy
    from types import SimpleNamespace
    from core.compilador import template_lowering as module
    calls=[]
    def compiler(model):
        result=SimpleNamespace(model=model)
        calls.append(result)
        return result
    monkeypatch.setattr(module,'DerivedSystem',compiler)
    module._plans.clear()
    model={'id':'generic','recipe':{'version':1},'data':{'flow':1}}
    first=module.compile_template(model)
    assert module.compile_template(deepcopy(model)) is first
    for change in ({**model,'id':'renamed'}, {**model,'recipe':{'version':2}},
                   {**model,'data':{'flow':2}}):
        assert module.compile_template(change) is not first
    with sp.assuming(sp.Q.positive(sp.Symbol('proof_context'))):
        assert module.compile_template(model) is not first
    with preparation_policy(cached=False):
        assert module.compile_template(model) is not first
    assert len(calls)==6
    model['data']['flow']=9
    assert first.model['data']['flow']==1
    assert len(module._plans)<=4
    module._plans.clear()


def test_generic_plan_matches_fresh_instance_and_has_independent_closure_state():
    model = source_model(); model['datos']['solve.stageCount']['declaracion']['texto'] = '2'
    source = DerivedSystem(model['indexSet']['templates']['generic'])
    instance = expand_index_set(model)['stages'][0]
    bound = bind_stage(source, instance)
    reference = DerivedSystem(instance['model'])
    assert bound.selection == reference.selection
    assert bound.states == reference.states
    assert bound.rates == reference.rates
    assert bound.checks == reference.checks
    Path('.tmp/bound-lowered.json').write_text(json.dumps(bound.lowered,indent=2),encoding='utf-8')
    Path('.tmp/reference-lowered.json').write_text(json.dumps(reference.lowered,indent=2),encoding='utf-8')
    def canonical(tree):
        if isinstance(tree,list):return [canonical(v) for v in tree]
        if not isinstance(tree,dict):return tree
        result={key:canonical(value) for key,value in tree.items()}
        if result.get('tipo') in ('producto','suma'):
            result['argumentos']=sorted(result['argumentos'],key=lambda v:json.dumps(v,sort_keys=True))
        return result
    # Bijective renaming can reorder SymPy's commutative operands. It must not
    # change any operator, literal, variable, condition, unit or declaration.
    assert canonical(bound.lowered) == canonical(reference.lowered)
    assert bound.margins == reference.margins
    assert bound.initial_values == reference.initial_values
    for key in reference.graph.nodes:
        assert sp.srepr(bound.graph.nodes[key].equation) == sp.srepr(reference.graph.nodes[key].equation)
    assert bound.replayed.receipts == reference.replayed.receipts
    np.testing.assert_array_equal(bound.initial(),reference.initial())
    np.testing.assert_allclose(bound.rhs(0.,bound.initial()),reference.rhs(0.,reference.initial()),rtol=0,atol=0)
    assert bound.closures[0].cache is not source.closures[0].cache
    assert bound.closures[0].owner != source.closures[0].owner
    assert bound.closures[0].fingerprint == source.closures[0].fingerprint
    assert isinstance(bound.report['derivedExecution']['thermodynamicClosures'][0]['fingerprint'],str)
    assert bound.numeric.system is bound


def test_cached_and_reference_network_rates_and_certificates_agree():
    model = source_model(); model['datos']['solve.stageCount']['declaracion']['texto'] = '2'
    cached = IndexedDerivedSystem(model)
    with preparation_policy(cached=False):
        reference = IndexedDerivedSystem(model)
    np.testing.assert_array_equal(cached.initial(),reference.initial())
    np.testing.assert_allclose(cached.rhs(0.,cached.initial()),reference.rhs(0.,reference.initial()),rtol=1e-14,atol=1e-14)
    assert cached.firma(0.,cached.initial()) == reference.firma(0.,reference.initial())
    for stage, other in zip(cached.stages,reference.stages):
        assert stage.rates == other.rates
        assert stage.checks == other.checks
        for closure, compared in zip(stage.closures,other.closures):
            a=closure.evaluate(0.,stage.initial())[1]['certificate']
            b=compared.evaluate(0.,other.initial())[1]['certificate']
            assert a == b


def test_generic_steady_specialization_matches_independent_stage_defaults():
    from core.modelo.steady_transform import prepare_steady_transform
    from core.compilador.steady import SteadySystem
    model=source_model();model['datos']['solve.stageCount']['declaracion']['texto']='2'
    network=IndexedSteadySystem(model)
    for stage,instance in zip(network.stages,network.dynamic.expansion['stages']):
        reference=SteadySystem(prepare_steady_transform(instance['model'])['model'])
        assert stage.selection==reference.selection
        for field in ('seed','bounds','scales','residual_scales'):
            np.testing.assert_array_equal(getattr(stage,field),getattr(reference,field))
        for field in ('signature','sourceSignature','formulationSignature','dataSignature','settingsSignature','residualRows','invariants','parameters'):
            assert stage.report[field]==reference.report[field],field


def test_verified_instance_rebinding_matches_uncached_full_replay():
    from core.modelo.template_instance import instantiate_template
    from core.modelo.equation_workbench import build
    source=source_model()['indexSet']['templates']['generic']
    cached=instantiate_template(source,identity_namespace='replay-equivalence')
    with preparation_policy(cached=False):
        reference=instantiate_template(source,identity_namespace='replay-equivalence')
        replayed=build(cached['model'])
    assert cached==reference
    bound=bind_stage(DerivedSystem(source),cached)
    from dataclasses import fields
    for actual,expected in zip(bound.replayed.receipts,replayed.receipts):
        for field in fields(actual):
            left,right=getattr(actual,field.name),getattr(expected,field.name)
            equal=left==right
            assert equal,(actual.operation_id,field.name,str(left),str(right))
    assert bound.graph.domains==replayed.graph.domains


def test_lowering_constant_keys_preserve_signed_zero_and_adjacent_floats():
    import math
    from types import SimpleNamespace
    from core.compilador.lowering_cache import compile_ast, clear
    clear()
    expression={'tipo':'simbolo','id':'constant'}
    def compiled(value):
        return compile_ast(SimpleNamespace(tiempo='t',indice={},valores={'constant':value}),expression,'constant')
    positive=compiled(0.0);negative=compiled(-0.0)
    assert positive is not negative
    assert math.copysign(1,positive(0,[]))==1
    assert math.copysign(1,negative(0,[]))==-1
    for value in (0.0,-0.0,1.0,math.nextafter(1.0,2.0)):
        assert compiled(value)(0,[]).hex()==value.hex()
        assert compiled(value) is compiled(value)
