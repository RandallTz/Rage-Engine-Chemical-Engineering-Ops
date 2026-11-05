"""Recorded discharge transport and indexed dense/sparse network acceptance."""
import copy

import numpy as np
import pytest

from core.compilador.derived_graph import LoweringError
from core.compilador.indexed_network import IndexedDerivedSystem, discharge, align_transport
from core.solvers import integrar
from test_index_sets import source_model


def network(count, mode='sparse'):
    model = source_model()
    model['datos']['solve.stageCount']['declaracion']['texto'] = str(count)
    return IndexedDerivedSystem(model, linear_solver=mode)


def test_single_stage_keeps_replayed_rhs_and_volume_closure():
    system = network(1)
    state = system.initial()
    np.testing.assert_array_equal(state,system.stages[0].initial())
    np.testing.assert_allclose(system.rhs(0.,state),system.stages[0].rhs(0.,state),rtol=1e-12,atol=1e-9)
    assert len(system.blocks) == len(system.stages[0].closures) == 1
    assert system.expansion['connections'] == []


@pytest.mark.parametrize('count',[2,3])
def test_recorded_transport_connects_and_sparse_matches_dense(count):
    system = network(count)
    assert len(system.expansion['internalStreams']) == count-1
    assert len(system.blocks) == count
    initial = system.initial()
    # Local state perturbation reaches adjacent stages only; no global datum or
    # authored-symbol collision may bind one stage's state to another's.
    matrix = system.jacobian(0.,initial).toarray()
    for row in range(count):
        for column in range(count):
            if column not in (row,row-1):
                assert np.all(matrix[system.offsets[row]:system.offsets[row+1],
                                     system.offsets[column]:system.offsets[column+1]] == 0)
    sparse = integrar(system,initial,1.,rtol=1e-9,atol=system.atol,max_step=.1,metodo='BDF')
    assert sparse.detenida is None
    system.jacobian = None  # SciPy's dense finite-difference reference path.
    dense = integrar(system,initial,1.,rtol=1e-9,atol=system.atol,max_step=.1,metodo='BDF')
    assert dense.detenida is None
    np.testing.assert_allclose(sparse.y_fin,dense.y_fin,rtol=1e-8,atol=1e-8)
    for j,stage in enumerate(system.stages):
        for closure in stage.closures:
            _,values = closure.evaluate(1.,sparse.y_fin[system.offsets[j]:system.offsets[j+1]],'publication')
            assert closure.admits(values['phase_set']) is None
            certificate = values['certificate']
            assert certificate['residual']/certificate['scale'] <= 1e-9 if closure.single else certificate['certified'] and certificate['ratio'] <= 1


def test_missing_transport_is_located_and_never_replaced_by_a_formula():
    import sympy as sp
    from core.compilador.derived import DerivedSystem
    model = source_model()['indexSet']['templates']['generic']
    before = copy.deepcopy(model)
    system = DerivedSystem(model)
    port = next(p for p in model['template']['ports'] if p['id']=='liquid')
    quantity = sp.Function('q__'+port['boundary']['id']+'__1')(system.time)
    system.replacements.pop(quantity)
    with pytest.raises(LoweringError) as caught:
        discharge(system,port,'indexSet.templates.generic.template.ports.liquid')
    assert caught.value.diagnostics[0]['code']=='index_network_missing_transport'
    assert caught.value.diagnostics[0]['path']=='indexSet.templates.generic.template.ports.liquid'
    assert model == before


def test_discharge_transport_is_a_consequence_of_recorded_component_and_energy_laws():
    import sympy as sp
    from core.compilador.derived import DerivedSystem
    model = source_model()['indexSet']['templates']['generic']
    system = DerivedSystem(model)
    quantities = [(sp.Function(f'q__discharge__{i}')(system.time),
                   sp.Function(f'q__liquid__{i}')(system.time),'matter') for i in (1,2)]
    quantities.append((sp.Function('energy_average_0__discharge')(system.time),
                       sp.Function('energy_average_0__liquid')(system.time),'energy'))
    for target,donor,family in quantities:
        assert sp.cancel(system._expand(target-donor)) == 0
        row = next(r for r in system.selection['reconstructions'] if system.quantities[r['quantityId']]==target)
        ancestry=set()
        def visit(key):
            if key in ancestry:return
            ancestry.add(key)
            for parent in system.graph.nodes[key].inputs:visit(parent)
        visit(row['equationId'])
        roots=[system.graph.nodes[k] for k in ancestry if not system.graph.nodes[k].inputs and not k.startswith('operation.')]
        assert any(node.family==family and node.equation.has(sp.Derivative) for node in roots)
        assert any('stationary' in k or 'zero-total-rate' in k for k in ancestry)
    assert all(r.signature_status!='legacy/unsigned' for r in system.replayed.receipts)


def test_connected_species_follow_identity_not_local_component_order():
    from types import SimpleNamespace
    donor = {'componentes':[{'id':1,'identidadQuimica':{'cas':'A'}},
                            {'id':2,'identidadQuimica':{'cas':'B'}}]}
    receiver = SimpleNamespace(components=[20,10], species=['B','A'])
    assert align_transport(donor, [1,2], ['flux-A','flux-B'], receiver, 'connection') == ([20,10], ['flux-B','flux-A'])
    for species in (['A','C'], ['A','A'], ['A']):
        receiver.species = species
        with pytest.raises(LoweringError) as caught:
            align_transport(donor, [1,2], ['flux-A','flux-B'], receiver, 'connection')
        assert caught.value.diagnostics[0]['code'] == 'index_network_component_mismatch'
        assert caught.value.diagnostics[0]['path'] == 'connection'


@pytest.mark.parametrize('receiving_pressure',[101325,202650,None])
def test_connection_pressure_is_equal_or_located_rejection(receiving_pressure):
    from types import SimpleNamespace
    import sympy as sp
    from core.compilador.indexed_network import check_connection_pressure
    t=sp.Symbol('t');p2=sp.Function('p2__path')(t);P=sp.Function('P__receiver')(t)
    donor=SimpleNamespace(time=t,graph=SimpleNamespace(nodes={'recorded':SimpleNamespace(equation=sp.Eq(p2,sp.Integer(101325)))}),
                          _expand=lambda q:q,parameter_values={})
    receiver=SimpleNamespace(_expand=lambda q:q,parameter_values={} if receiving_pressure is None else {P:sp.Integer(receiving_pressure)})
    args=(donor,{'volumeId':'path'},receiver,SimpleNamespace(P=P),'indexSet.connections.transfer')
    if receiving_pressure==101325:check_connection_pressure(*args)
    else:
        with pytest.raises(LoweringError) as caught:check_connection_pressure(*args)
        assert caught.value.diagnostics[0]['code']=='index_network_pressure_mismatch'
        assert caught.value.diagnostics[0]['path']=='indexSet.connections.transfer'


def test_real_stage_pressure_change_cannot_reuse_equal_pressure_admission():
    from core.compilador.indexed_network import check_connection_pressure
    system=network(2)
    connection=system.expansion['connections'][0]
    donor,receiver=system.stages[0],system.stages[1]
    port=next(p for p in donor.model['template']['ports'] if p['id']==connection['from']['portId'])
    closure=receiver.closures[0]
    pressure=receiver._expand(closure.P)
    previous=receiver.parameter_values[pressure]
    try:
        receiver.parameter_values[pressure]=2*previous
        with pytest.raises(LoweringError) as caught:
            check_connection_pressure(donor,port,receiver,closure,'indexSet.connections.changed')
        assert caught.value.diagnostics[0]['code']=='index_network_pressure_mismatch'
    finally:receiver.parameter_values[pressure]=previous
