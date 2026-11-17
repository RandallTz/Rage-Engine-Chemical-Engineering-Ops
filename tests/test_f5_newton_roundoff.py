"""F5 item 1 follow-up: Newton termination at the residual's binary64 round-off.

CI group-9 (run 44103163221) failed on Cooperlake runners with a scaled residual of 2.4e-14 against its 1e-10
tolerance and a Newton step of 4.45e-9 (cond_inf 9e4): the step is the residual's rounding error amplified by
the inverse Jacobian, above the step tolerance and the coordinate resolution, and no backtracked trial can lower
a merit already at round-off. The row below reproduces that state on every CPU: (1e5 + z0) - 1e5 is quantized
on the grid spacing(1e5) = 1.46e-11, and the constant c lies 0.3 grid units off it, so the residual never falls
below about 4.4e-12 (within 1e-10) and the Newton step stays near 4.4e-12 (above 1e-12, far above the 9e-16
resolution of z0 = 1).
"""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.solvers.nonlinear import NonlinearError, roundoff_step, solve

BIG = 1e5
GRID = float(np.spacing(BIG))
C = 1. + 0.3 * GRID


def residual(z):
    return np.array([((BIG + z[0]) - BIG) - C, z[1] - 2. * z[0]])


def jacobian(z):
    return np.array([[1., 0.], [-2., 1.]])


def run(**kwargs):
    settings = dict(residual_tolerance=1e-10, step_tolerance=1e-12)
    settings.update(kwargs)
    return solve(residual, jacobian, [0.5, 0.5], [[0.1, 4.], [0.1, 8.]], [1., 1.], [1., 1.], **settings)


def test_the_reproducer_is_a_round_off_state_on_every_cpu():
    """The residual floor and the step are set by the quantization grid, not by the kernel."""
    near = np.array([C, 2. * C])
    floor = min(abs(residual(near + np.array([k * GRID / 8, 0.]))[0]) for k in range(-16, 17))
    assert 0.2 * GRID < floor <= 1e-10
    assert floor > 1e-12  # with unit slope the Newton step equals the residual, above the step tolerance
    assert 4 * np.spacing(C) < 1e-12


def test_a_residual_converged_iterate_at_round_off_is_converged():
    z, detail = run()
    assert detail['terminationReason'] == 'converged'
    assert detail['residualNorm'] <= 1e-10
    assert 1e-12 < detail['stepNorm'] <= roundoff_step(2, detail['residualNorm'], 0.38)
    assert abs(z[0] - 1.) < 2 * GRID and abs(z[1] - 2. * z[0]) < 1e-15


def test_the_same_state_with_a_finer_residual_tolerance_still_fails():
    """Round-off termination never relaxes the residual tolerance."""
    with pytest.raises(NonlinearError) as caught:
        run(residual_tolerance=1e-13)
    assert caught.value.code in ('nonlinear_line_search', 'nonlinear_iteration_limit')


def test_roundoff_step_bounds_every_newton_step():
    rng = np.random.default_rng(7)
    for _ in range(200):
        j = rng.normal(size=(3, 3))
        r = rng.normal(size=3) * 1e-12
        step = np.linalg.solve(j, -r)
        sigma = np.linalg.svd(j, compute_uv=False)[-1]
        assert np.linalg.norm(step, np.inf) <= roundoff_step(3, np.linalg.norm(r, np.inf), sigma)


def test_tiny_steady_seed_with_last_bit_residual_noise_converges_to_the_same_root(monkeypatch):
    """The group-9 case (100-fold flash, 1 g / 4 g seed) with every residual row perturbed by up to 4 ulp,
    a deterministic stand-in for another CPU kernel. Before this repair it failed like the Cooperlake runners
    (LoweringError, no sufficient-decrease step; residual ~2.5e-14, step 2.8e-9 above the 1.4e-9 resolution)."""
    import hashlib
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from demo01_flash import frozen_model
    from core.compilador.steady import SteadySystem, read_result
    from core.modelo.steady_transform import prepare_steady_transform
    import core.solvers.nonlinear as nonlinear
    original = nonlinear.solve

    def noisy(residual_function, *args, **kwargs):
        def perturbed(z):
            r = np.asarray(residual_function(z), dtype=float)
            h = hashlib.sha256(np.asarray(z, dtype=float).tobytes()).digest()
            k = np.array([(h[i % 32] % 9) - 4 for i in range(len(r))], dtype=float)
            return r + k * np.finfo(float).eps * np.abs(r)
        return original(perturbed, *args, **kwargs)
    monkeypatch.setattr(nonlinear, 'solve', noisy)
    roots, details = {}, {}
    for first, second in [('2000.0', '8000.0'), ('0.001', '0.004')]:
        m = frozen_model()
        for key in ('drum.volume', 'solve.A', 'solve.Ao', 'solve.F', 'solve.Q', 'scale.mass'):
            d = m['datos'][key]['declaracion']; d['texto'] = str(float(d['texto']) * 100)
        m['datos']['drum.mass']['declaracion']['texto'] = first
        m['datos']['drum.mass2']['declaracion']['texto'] = second
        m['motores']['derivedExecution']['checks'] = []
        result = SteadySystem(prepare_steady_transform(m)['model']).solve()
        read_result(result)
        details[first] = result['procedencia']['steadyDiagnostics']['solver']
        roots[first] = {r['nombre']: float(np.atleast_1d(r['valores'])[-1]) for r in result['series']
                        if r['nombre'].startswith(('m__drum', 'H__drum', 'T__drum'))}
    tiny = details['0.001']
    assert tiny['terminationReason'] == 'converged' and tiny['residualNorm'] <= 1e-10
    assert tiny['backtracks'] >= 20  # the round-off termination is the path exercised
    assert len(roots['0.001']) == 4
    for name, value in roots['2000.0'].items():
        assert abs(roots['0.001'][name] / value - 1) < 1e-11, name
