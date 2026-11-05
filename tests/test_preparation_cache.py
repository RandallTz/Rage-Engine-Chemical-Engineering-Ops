"""Recipe/identity reuse must never hide edits, aliases or rejected history."""
import copy
from functools import lru_cache

import numpy as np
import pytest

from core.compilador.explicito import SistemaExplicito
from core.compilador import lowering_cache
from core.modelo import preparation_cache
from core.modelo.equation_workbench import build


@lru_cache(maxsize=1)
def _source():
    from sparse_chain_inputs import thermal_chain
    return thermal_chain(2)


def model():
    return copy.deepcopy(_source())


def graph_identity(result):
    return (result.graph.rows(),result.selected,result.owners,result.units,result.definition,
            result.introduced,[(r.operation_id,r.signature_status,dict(r.input_signatures)) for r in result.receipts])


def test_replay_cache_exact_identity_and_independent_mutable_copies():
    preparation_cache.clear()
    source=model()
    with preparation_cache.preparation_policy(cached=False): reference=build(source)
    first=build(source); second=build(source)
    assert graph_identity(first)==graph_identity(reference)==graph_identity(second)
    assert preparation_cache.evidence()['hits']==1
    first.selected.clear();first.graph.nodes.clear();first.definition['operations'].clear()
    assert graph_identity(build(source))==graph_identity(reference)


def test_data_identity_recipe_and_source_edits_do_not_hit_old_entry():
    preparation_cache.clear();source=model();build(source)
    for change in ['name','data','identity']:
        modified=copy.deepcopy(source)
        if change=='name': modified['nombre']='Changed display'
        if change=='identity': modified['id']='another-model'
        if change=='data': modified['datos']['chain.conductance']['declaracion']['texto']='11'
        build(modified)
    assert preparation_cache.evidence()['hits']==0
    stale=copy.deepcopy(source)
    stale['motores']['equationWorkbench']['operations'][-1]['sourceSignatures']={'missing':'stale'}
    with pytest.raises(ValueError): build(stale)


def evaluator(identity,index,constant):
    result=SistemaExplicito.__new__(SistemaExplicito)
    result.tiempo='time';result.indice={identity:index};result.valores={'coefficient':constant}
    return result


def test_generic_ast_compiles_once_and_identity_maps_bind_independently():
    lowering_cache.clear()
    def expression(identity):
        return {'tipo':'producto','argumentos':[{'tipo':'simbolo','id':'coefficient'},
            {'tipo':'simbolo','id':identity},{'tipo':'simbolo','id':identity}]}
    for i in range(40):
        engine=evaluator('stage.'+str(i),i,i+1)
        ast=expression('stage.'+str(i))
        cached=engine._compilar(ast,'test')
        with preparation_cache.preparation_policy(cached=False): uncached=engine._compilar(ast,'test')
        state=np.arange(40)+1
        assert cached(0,state)==uncached(0,state)==(i+1)**3
    assert lowering_cache.evidence()['generic']['misses']==1
    assert lowering_cache.evidence()['instances']['misses']==40


def test_uncached_policy_is_nested_and_restores_on_exception():
    assert preparation_cache.enabled()
    with pytest.raises(RuntimeError):
        with preparation_cache.preparation_policy(cached=False):
            assert not preparation_cache.enabled()
            with preparation_cache.preparation_policy(cached=True): assert preparation_cache.enabled()
            assert not preparation_cache.enabled()
            raise RuntimeError('test')
    assert preparation_cache.enabled()


def test_full_dynamic_and_steady_publications_match_uncached_reference():
    from core.compilador.derived import DerivedSystem, resolve_system
    from core.compilador.steady import SteadySystem
    from core.modelo.steady_transform import prepare_steady_transform
    source=model()
    publications=[]
    for cached in (False,True):
        with preparation_cache.preparation_policy(cached=cached):
            dynamic=DerivedSystem(source)
            transformed=prepare_steady_transform(source)
            steady=SteadySystem(transformed['model'])
            publications.append((dynamic.report,resolve_system(dynamic),transformed,steady.solve()))
    assert publications[0]==publications[1]


@pytest.mark.parametrize('ast',[
    {'tipo':'derivada','respecto':'time'},
    {'tipo':'llamada','funcionId':'missing'},
    {'tipo':'unsupported'},
])
def test_cache_preserves_located_unsupported_expression_errors(ast):
    from core.compilador.compilador import NoSoportado
    engine=evaluator('state',0,1.)
    messages=[]
    for cached in (False,True):
        with preparation_cache.preparation_policy(cached=cached):
            with pytest.raises(NoSoportado) as error:
                engine._compilar(ast,'equations[3].right')
            messages.append(str(error.value))
    assert messages[0]==messages[1]
    assert messages[0].startswith('equations[3].right:')


def test_domain_proof_cache_includes_the_complete_assumption_context():
    import sympy as sp
    from core.mathematics.domains import ask_once, _ask_exact
    _ask_exact.cache_clear()
    x=sp.Symbol('cache_domain_quantity',real=True)
    assert ask_once(sp.Q.positive(x)) is None
    with sp.assuming(sp.Q.negative(x)):
        assert ask_once(sp.Q.positive(x)) is False
    with sp.assuming(sp.Q.positive(x)):
        assert ask_once(sp.Q.positive(x)) is True
    assert ask_once(sp.Q.positive(x)) is None
    assert _ask_exact.cache_info().hits==1


def test_replay_cache_does_not_cross_assumption_contexts():
    import sympy as sp
    preparation_cache.clear()
    source=model()
    build(source)
    marker=sp.Symbol('independent_assumption_marker',real=True)
    with sp.assuming(sp.Q.positive(marker)):
        build(source)
    assert preparation_cache.evidence()['hits']==0
    build(source)
    assert preparation_cache.evidence()['hits']==1
