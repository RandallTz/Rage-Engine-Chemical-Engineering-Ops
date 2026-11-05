"""Long-time indexed execution against independent mixture-package integration."""
import numpy as np
import pytest
import time


def test_steady_difference_stencil_stays_inside_declared_bounds():
    from core.compilador.indexed_steady import IndexedSteadySystem
    system = object.__new__(IndexedSteadySystem)
    system.linear_policy = {'selected':'dense'}
    system.scales = np.array([20., 20., 20.])
    system.bounds = np.array([[1e-8, 10.]]*3)
    calls = []
    def residual(values):
        assert np.all(values >= system.bounds[:, 0])
        assert np.all(values <= system.bounds[:, 1])
        calls.append(values.copy())
        return values**2 + 3*values
    system.residual = residual
    values = np.array([1e-8, 10., 5.])
    np.testing.assert_allclose(system.jacobian(values), np.diag(2*values+3), rtol=1e-9, atol=1e-9)
    assert len(calls) == 7


def test_continuation_preserves_prefix_roots_and_rejects_feedback():
    from types import SimpleNamespace
    from unittest.mock import patch
    from core.compilador.indexed_steady import IndexedSteadySystem
    from core.solvers.nonlinear import NonlinearError
    system = object.__new__(IndexedSteadySystem)
    config = dict(residualTolerance=1e-10, stepTolerance=1e-12, maxIterations=30, maxBacktracks=20)
    system.stages = [SimpleNamespace(seed=[1.], config=config, checks=[]) for _ in range(3)]
    system.dynamic = SimpleNamespace(offsets=[0,1,2,3],
        block_jacobian=SimpleNamespace(edges=[(0,0),(1,0),(1,1),(2,1),(2,2)]),
        stages=[SimpleNamespace(checks=[], closures=[]) for _ in range(3)],
        initial=lambda:np.ones(3), rhs=lambda t,y:np.zeros(3))
    system.indices = [0,1,2]
    system.seed = np.ones(3)
    system.bounds = np.array([[0.,10.]]*3)
    system.scales = system.residual_scales = np.ones(3)
    system.linear_policy = {'selected':'dense'}
    system.residual = lambda values:values-np.array([2.,3.,4.])
    system.jacobian = lambda values, columns=None:np.eye(3)[:, :columns]
    system.admissible = lambda values:True
    seeds = []
    def numerical(residual, jacobian, seed, *args, **kwargs):
        seeds.append(np.array(seed))
        if len(seeds) == 1:
            raise NonlinearError('nonlinear_domain', 'Default seed failed.')
        size = len(seed)
        root = np.arange(2.,2.+size)
        np.testing.assert_array_equal(residual(root), np.zeros(size))
        assert jacobian(root).shape == (size,size)
        return root, {'terminationReason':'converged'}
    with patch('core.compilador.indexed_steady.solve', side_effect=numerical):
        root, evidence = system.solve()
    np.testing.assert_array_equal(root,[2.,3.,4.])
    np.testing.assert_array_equal(seeds[2],[2.,1.])
    np.testing.assert_array_equal(seeds[3],[2.,3.,1.])
    assert evidence['continuation']['initialFailure']['code'] == 'nonlinear_domain'
    assert [row['count'] for row in evidence['continuation']['steps']] == [1,2,3]
    system.dynamic.expansion = {'stages':[
        {'template':'generic', 'provenance':{'identityMap':{'quantities':{'source':'q'+str(j)}}}}
        for j in range(3)]}
    for j, stage in enumerate(system.stages):
        stage.selection = {'unknowns':['q'+str(j)]}
    seeds.clear()
    with patch('core.compilador.indexed_steady.solve', side_effect=numerical):
        _, transferred = system.solve()
    np.testing.assert_array_equal(seeds[2],[2.,2.])
    np.testing.assert_array_equal(seeds[3],[2.,3.,3.])
    assert [row['seedFromPreviousStage'] for row in transferred['continuation']['steps']] == [False,True,True]
    del system.dynamic.expansion
    with patch('core.compilador.indexed_steady.solve', side_effect=[
            NonlinearError('nonlinear_domain','Initial failure'),
            (np.array([2.]), {'terminationReason':'converged'}),
            NonlinearError('nonlinear_domain','Prefix failure')]):
        with pytest.raises(NonlinearError, match='Prefix failure') as caught:
            system.solve()
        assert caught.value.diagnostic['continuation']['completedCounts'] == [1]
        assert caught.value.diagnostic['continuation']['failedCount'] == 2
    with patch('core.compilador.indexed_steady.solve', side_effect=NonlinearError('nonlinear_domain','Disabled')) as solver:
        with pytest.raises(NonlinearError, match='Disabled'):
            system.solve(continuation=False)
        assert solver.call_count == 1
    system.dynamic.block_jacobian.edges.append((0,2))
    with patch('core.compilador.indexed_steady.solve', side_effect=NonlinearError('nonlinear_domain','Feedback')) as solver:
        with pytest.raises(NonlinearError, match='Feedback'):
            system.solve()
        assert solver.call_count == 1

from core.solvers import integrar
from indexed_network_reference import reference_network
from test_indexed_network_lowering import network


@pytest.mark.parametrize('count', [1, 2, 3, 5])
def test_dynamic_network_certificates_conservation_and_reference(count):
    system = network(count, 'auto')
    times = np.linspace(0., system.tf, 81)
    runs = {}
    for method in ('RK45', 'BDF'):
        trajectory = integrar(system, system.initial(), system.tf, rtol=1e-9,
                              atol=system.atol, max_step=system.tf / 80, metodo=method)
        assert trajectory.detenida is None, str(trajectory.detenida)
        assert trajectory.t_fin == system.tf
        values = np.asarray([trajectory.y(t) for t in times])
        runs[method] = values
        for j, stage in enumerate(system.stages):
            local = values[:, system.offsets[j]:system.offsets[j+1]]
            for k, (_, inventory, _, scale) in enumerate(stage.checks):
                function = stage.numeric._compilar(stage._ast(inventory), 'network conservation')
                first = function(0., stage.initial_state)
                residual = max(abs(float(function(t, row) - first - row[stage.size+k]))
                               for t, row in zip(times, local)) / float(scale)
                assert residual < 1e-9
            for closure in stage.closures:
                for t, row in zip(times, local):
                    _, publication = closure.evaluate(t, row, 'publication')
                    assert closure.admits(publication['phase_set']) is None
                    certificate = publication['certificate']
                    if closure.single:
                        assert certificate['residual'] / certificate['scale'] <= 1e-9
                    else:
                        assert certificate['certified'] and certificate['ratio'] <= 1
    np.testing.assert_allclose(runs['RK45'], runs['BDF'], rtol=2e-6, atol=2e-6)
    if count in (1, 2, 3):
        reference, temperatures = reference_network(count, times)
        assert reference.success, reference.message
        for method, values in runs.items():
            for j, stage in enumerate(system.stages):
                local = values[:, system.offsets[j]:system.offsets[j]+stage.size]
                expected = reference.y[j*4:(j+1)*4].T
                np.testing.assert_allclose(local[:, [0, 1, 3]], expected[:, [0, 1, 3]], rtol=2e-6, atol=2e-6)
                assert np.max(abs(local[:, 2] - expected[:, 2])) / abs(expected[0, 2]) < 1e-8
                closure = stage.closures[0]
                calculated = [closure.evaluate(t, row, 'publication')[0][closure.outputs.index(closure.T)]
                              for t, row in zip(times, local)]
                np.testing.assert_allclose(calculated, temperatures[:, j], rtol=0., atol=2e-5)


@pytest.mark.parametrize('count', [1, 2, 3, 5])
def test_zero_accumulation_defaults_match_long_time_dynamic(count):
    from core.compilador.indexed_steady import IndexedSteadySystem
    from test_index_sets import source_model
    model = source_model()
    model['datos']['solve.stageCount']['declaracion']['texto'] = str(count)
    started = time.perf_counter()
    print(f'network n={count}: preparation started', flush=True)
    steady = IndexedSteadySystem(model)
    print(f'network n={count}: prepared in {time.perf_counter()-started:.3f} s; Newton started', flush=True)
    root, evidence = steady.solve(progress=lambda event:print(
        f'network n={count}: {event} at {time.perf_counter()-started:.3f} s', flush=True))
    print(f'network n={count}: Newton completed at {time.perf_counter()-started:.3f} s; long BDF started', flush=True)
    assert evidence['terminationReason'] == 'converged'
    assert evidence['residualNorm'] < 1e-9
    assert evidence['uniqueness'].startswith('local_root_only')
    dynamic = steady.dynamic
    long_run = integrar(dynamic, dynamic.initial(), 6000., rtol=1e-9,
                        atol=dynamic.atol, max_step=75., metodo='BDF')
    print(f'network n={count}: BDF completed at {time.perf_counter()-started:.3f} s', flush=True)
    assert long_run.detenida is None, str(long_run.detenida)
    assert long_run.t_fin == 6000.
    final = long_run.y_fin[steady.indices]
    np.testing.assert_allclose(final, root, rtol=2e-4, atol=1e-7)
    stationary = steady.state(root)
    for j, stage in enumerate(dynamic.stages):
        for closure in stage.closures:
            local = slice(dynamic.offsets[j], dynamic.offsets[j+1])
            values, publication = closure.evaluate(0., stationary[local], 'publication')
            settled, _ = closure.evaluate(6000., long_run.y_fin[local], 'publication')
            assert abs(values[closure.outputs.index(closure.T)] - settled[closure.outputs.index(closure.T)]) < .05
            certificate = publication['certificate']
            assert certificate['certified'] and certificate['ratio'] <= 1
    if count == 3:
        steady.linear_policy['selected'] = 'sparse'
        dynamic.block_jacobian.policy['selected'] = 'sparse'
        sparse_root, sparse_evidence = steady.solve()
        np.testing.assert_allclose(sparse_root, root, rtol=1e-9, atol=1e-8)
        assert sparse_evidence['residualNorm'] < 1e-9
    print(f'network n={count}: acceptance completed in {time.perf_counter()-started:.3f} s', flush=True)
