"""Sparse assembly, local closure work and unchanged Newton regularity gates."""
import numpy as np
import pytest
import sympy as sp
from unittest.mock import patch
from scipy.sparse import csc_matrix, issparse

from core.solvers.sparse_blocks import ExpressionJacobian, factor_step, policy
from core.solvers.nonlinear import solve, NonlinearError


@pytest.mark.parametrize('n', [3, 5, 10, 20, 40])
def test_symbolic_chain_dense_sparse_and_newton(n):
    x = list(sp.symbols('x:'+str(n)))
    t = sp.Symbol('t')
    expressions = [3*x[i] - (x[i-1] if i else 0) - (x[i+1] if i+1<n else 0) for i in range(n)]
    jac = ExpressionJacobian(expressions, x, t, np.ones(n), requested='sparse')
    matrix = jac(0, np.ones(n))
    assert issparse(matrix)
    assert matrix.nnz == 3*n-2
    residual = lambda z: matrix @ (z-1)
    settings = (np.zeros(n), np.tile([-2., 2.], (n,1)), np.ones(n), np.ones(n))
    dense, a = solve(residual, lambda z: matrix.toarray(), *settings, linear_solver='dense')
    sparse, b = solve(residual, lambda z: matrix, *settings, linear_solver='sparse')
    np.testing.assert_allclose(sparse, dense, atol=1e-12, rtol=1e-12)
    assert a['terminationReason'] == b['terminationReason'] == 'converged'
    assert b['conditionInfinity'] == pytest.approx(a['conditionInfinity'], rel=1e-12)


def test_closure_jacobians_are_local_and_shared():
    x = list(sp.symbols('x:20')); c = list(sp.symbols('c:10')); t = sp.Symbol('t')
    calls = np.zeros(10, dtype=int)
    def evaluator(i):
        def evaluate(time, state):
            calls[i] += 1
            return np.array([state[2*i]**2 + 2*state[2*i+1]])
        return evaluate
    blocks = [([c[i]], {2*i,2*i+1}, evaluator(i)) for i in range(10)]
    expressions = [x[i]+c[i//2]+(c[i//2-1] if i>=2 else 0) for i in range(20)]
    jac = ExpressionJacobian(expressions, x, t, np.ones(20), blocks, requested='sparse')
    result = jac(0, np.ones(20)).toarray()
    expected = np.eye(20)
    for i in range(20):
        expected[i,2*(i//2):2*(i//2)+2] += 2
        if i>=2: expected[i,2*(i//2-1):2*(i//2-1)+2] += 2
    np.testing.assert_allclose(result, expected, atol=1e-8)
    assert calls.tolist() == [5]*10  # baseline and two central probes per local input
    assert jac.closure_blocks == 10
    assert jac.closure_probes == 40


@pytest.mark.parametrize('value', [0., 1e-12])
def test_sparse_keeps_singular_and_absolute_amplification_rejection(value):
    with pytest.raises(NonlinearError) as caught:
        solve(lambda x: value*x, lambda x: csc_matrix([[value]]), [1.], [[-2.,2.]], [1.], [1.], linear_solver='sparse')
    assert caught.value.code in ('nonlinear_singular_jacobian','nonlinear_ill_conditioned')


def test_policy_is_reproducible_and_small_default_is_dense():
    assert policy(10, 28)['selected'] == 'dense'
    assert policy(20, 58)['selected'] == 'dense'
    assert policy(40,1600)['selected'] == 'dense'
    assert policy(80,238)['selected'] == 'dense'
    assert policy(80,238)['version'] == 2
    assert policy(2,4,'sparse')['selected'] == 'sparse'
    with pytest.raises(ValueError): policy(10,10,'fallback')


def test_sparse_regularity_failure_is_structured_without_dense_fallback():
    with patch('core.solvers.sparse_blocks.svds', side_effect=RuntimeError('iteration failed')):
        with pytest.raises(NonlinearError) as caught:
            solve(lambda x:x-1, lambda x:csc_matrix(np.eye(2)), [0.,0.],
                  [[-2.,2.],[-2.,2.]], [1.,1.], [1.,1.], linear_solver='sparse')
    assert caught.value.code == 'nonlinear_singular_jacobian'


def test_batched_recipe_matches_the_interactive_shared_author_exactly():
    from sparse_chain_inputs import thermal_chain
    from m1_acceptance import SharedAuthor
    assert thermal_chain(2) == thermal_chain(2, author_class=SharedAuthor)


def test_jacobian_internal_names_cannot_shadow_the_authored_time():
    t = sp.Symbol('jac_x0', real=True)
    x = sp.Symbol('state', real=True)
    jac = ExpressionJacobian([t*x], [x], t, [1.], requested='sparse')
    assert jac(3., np.array([7.]))[0,0] == 3.


@pytest.mark.parametrize('name', ['a','b','c'])
def test_frozen_derived_dense_sparse_bdf(name):
    from derived_execution_inputs import fixture
    from core.compilador.derived import DerivedSystem, resolve_system
    from benchmark_sparse_chains import compare
    model, _, _ = fixture(name, 'bdf')
    nominal_tolerance = model['estudio']['rtol']
    model['estudio']['rtol'] /= 10
    model['estudio']['atol'] = {k:v/10 for k,v in model['estudio']['atol'].items()}
    system = DerivedSystem(model)
    publications = []
    for mode in ('dense','sparse'):
        system.configure_jacobian(mode)
        system.report = system._report()
        publications.append(resolve_system(system))
    compare(*publications, nominal_tolerance)


def test_package_steady_dense_sparse_and_local_closure_block():
    from demo01_flash import frozen_model
    from core.modelo.steady_transform import prepare_steady_transform
    from core.compilador.steady import SteadySystem
    from benchmark_sparse_chains import compare
    system = SteadySystem(prepare_steady_transform(frozen_model())['model'])
    before = system.block_jacobian.closure_blocks
    dense = system.solve(linear_solver='dense')
    sparse = system.solve(linear_solver='sparse')
    assert system.block_jacobian.closure_blocks > before
    compare(dense, sparse, 1e-7)
