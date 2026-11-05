"""Zero-rate kinetic admission must retain the dynamic source proof."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from core.compilador.derived import DerivedSystem, LoweringError
from demo01_reactor import frozen_model


def test_versioned_dynamic_reacting_volume_and_strict_rejections():
    import sympy as sp
    from core.modelo.reaction_definition import read_definition
    from core.balances.reaction_equations import declarations
    model = frozen_model()
    config = model['motores']['kineticReactions']
    config['version'] = 2
    owner,entry = next(iter(config['volumes'].items()))
    old = entry.pop('volumeDataId')
    entry['volumeSource'] = {'kind':'control_volume'}
    read_definition(config,model)
    graph,_,bindings,_ = declarations(model,owner)
    volume = sp.Function('V__'+owner)(sp.Symbol('t',real=True))
    assert graph.nodes['reaction.'+owner+'.concentration.1'].equation.rhs.has(volume)
    assert volume not in bindings
    for change in ('legacy_key','unknown_source','unknown_key','noninteger_version'):
        broken = deepcopy(config)
        if change=='legacy_key':broken['volumes'][owner]['volumeDataId']=old
        elif change=='unknown_source':broken['volumes'][owner]['volumeSource']['kind']='invented'
        elif change=='unknown_key':broken['volumes'][owner]['volumeSource']['extra']=True
        else:broken['version']=2.0
        with pytest.raises(ValueError):read_definition(broken,model)


def test_common_steady_closure_jacobian_does_not_probe_negative_inventories():
    import numpy as np
    import sympy as sp
    from core.compilador.steady import SteadySystem
    variable,output = sp.symbols('inventory closure',real=True)
    calls=[]
    def vector(values):
        assert 0<=values[0]<=10
        calls.append(float(values[0]))
        return [values[0]**2+3*values[0]]
    system=SimpleNamespace(symbols=[variable],scales=[20.],bounds=[[0.,10.]],
                           closures=SimpleNamespace(symbols=[output],vector=vector))
    _,jacobian=SteadySystem._closure_residual(system,[output])
    for point in (0.,5.,10.):
        np.testing.assert_allclose(jacobian([point]),[[2*point+3]],rtol=1e-9,atol=1e-9)
    assert 0. in calls and 10. in calls


def test_steady_equilibrium_limit_is_explicit_versioned_diagnostic():
    import json
    from pathlib import Path
    from demo02_cstr import frozen_model as continuous
    from core.modelo.steady_transform import prepare_steady_transform
    from core.compilador.steady import SteadySystem,read_result,steady_result_signature
    result=SteadySystem(prepare_steady_transform(continuous())['model']).solve()
    read_result(result)
    assert result['procedencia']['compilation']['kineticDiagnostics']=={'version':1,'volumeIds':['cell']}
    row=next(r for r in result['verificaciones'] if r['id']=='reactions.equilibrium_limit.cell')
    assert row['valor']>row['tolerancia']
    Path('.tmp/cstr-kinetic-steady-publication.json').write_text(json.dumps(result),encoding='utf-8')
    for corruption in ('missing','duplicate','negative','tolerance','unknown_owner','version','unknown_field'):
        changed=deepcopy(result)
        rows=changed['verificaciones'];item=next(r for r in rows if r['id']=='reactions.equilibrium_limit.cell')
        block=changed['procedencia']['compilation']['kineticDiagnostics']
        if corruption=='missing':rows.remove(item)
        elif corruption=='duplicate':rows.append(deepcopy(item))
        elif corruption=='negative':item['valor']=-1
        elif corruption=='tolerance':item['tolerancia']=1.
        elif corruption=='unknown_owner':block['volumeIds']=['missing']
        elif corruption=='version':block['version']=2
        else:block['extra']=True
        changed['procedencia']['steadyDiagnostics']['resultSignature']=steady_result_signature(changed)
        with pytest.raises(ValueError):read_result(changed)


@pytest.fixture(scope='module')
def dynamic():
    return DerivedSystem(frozen_model())


def test_zero_rate_kinetic_roots_are_the_same_declared_dynamic_roots(dynamic):
    steady = SimpleNamespace(**dynamic.__dict__)
    steady.selection = {**deepcopy(dynamic.selection), 'version': 5}
    steady.replacements = dict(dynamic.replacements)
    before = dict(steady.replacements)
    DerivedSystem._kinetic_declarations(steady)
    assert steady.replacements == before


def test_zero_rate_selection_cannot_bypass_recorded_source_substitutions(dynamic):
    steady = SimpleNamespace(**dynamic.__dict__)
    steady.selection = {**deepcopy(dynamic.selection), 'version': 5, 'states': []}
    steady.replacements = dict(dynamic.replacements)
    with pytest.raises(LoweringError) as caught:
        DerivedSystem._kinetic_declarations(steady)
    assert caught.value.diagnostics[0]['code'] == 'kinetic_source_not_deduced'


def test_coupled_kinetic_algebraic_execution_remains_outside_admission(dynamic):
    steady = SimpleNamespace(**dynamic.__dict__)
    steady.selection = {**deepcopy(dynamic.selection), 'version': 5,
                        'algebraic': [{'quantityId': 'unadmitted', 'equationId': 'unadmitted'}]}
    with pytest.raises(LoweringError) as caught:
        DerivedSystem._kinetic_declarations(steady)
    assert caught.value.diagnostics[0]['code'] == 'kinetic_formulation_unsupported'
