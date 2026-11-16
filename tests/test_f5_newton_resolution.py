"""F5 item 1 (claude-b, 15 November 2026): Newton termination scaled to the attainable resolution.

core/solvers/nonlinear.py takes a Newton step that is smaller than the declared step tolerance whenever it
still changes the iterate, reports stagnation only below the binary64 resolution of the iterate, and accepts
convergence at max(step tolerance, resolution). References are independent 50-digit mpmath roots.
"""
import mpmath as mp
import numpy as np
import pytest

from core.solvers.nonlinear import NonlinearError, RESOLUTION_ULPS, solve

mp.mp.dps = 50


N0 = 1e-3   # mol of a dilute reagent; the extent is declared at unit (1 mol) scale


def _extent_case(lnK):
    """A <=> B with N0 mol of A at near-complete conversion: g(xi) = ln(xi) - ln(N0 - xi) - ln K.

    dg/dxi = 1/xi + 1/(N0 - xi) ~ 1/(N0 - xi) is large, so a Newton step of 1e-12 mol still leaves a scaled
    residual far above 1e-10, while xi ~ 1e-3 is resolved to about 1e-19 mol: the root is attainable.
    """
    residual = lambda z: np.array([np.log(z[0]) - np.log(N0 - z[0]) - lnK])
    jacobian = lambda z: np.array([[1 / z[0] + 1 / (N0 - z[0])]])
    root = mp.mpf(N0) / (1 + mp.exp(-mp.mpf(lnK)))
    return residual, jacobian, root


def _solve_extent(lnK, record=None):
    residual, jacobian, root = _extent_case(lnK)
    if record is not None:
        traced = residual
        residual = lambda z: record.append((float(z[0]), float(traced(z)[0]))) or traced(z)
    seed = N0 - 5 * float(N0 - root)
    return solve(residual, jacobian, [seed], [[N0 / 2, N0 * (1 - 1e-13)]], [1.], [1.],
                 residual_tolerance=1e-10, step_tolerance=1e-12), root


@pytest.mark.parametrize('lnK', [8., 11.5, 14.])
def test_near_complete_conversion_converges_with_the_declared_tolerances(lnK):
    """Declared step tolerance 1e-12 (the setting that stagnated in B3 part 2): N0 - xi matches mpmath."""
    (z, detail), root = _solve_extent(lnK)
    assert detail['terminationReason'] == 'converged' and detail['residualNorm'] <= 1e-10
    # N0 - z is exact in binary64 (Sterbenz), so the remaining reagent is compared relatively.
    assert abs(mp.mpf(N0 - z[0]) / (N0 - root) - 1) < 1e-10


def test_the_converged_path_takes_steps_below_the_step_tolerance():
    """The previous rule stopped as stagnation at the first step <= 1e-12 whose residual exceeded 1e-10;
    the same Newton path contains such a step before it reaches the residual tolerance."""
    trace = []
    _solve_extent(11.5, trace)
    primary = trace[:next(i for i, (_, r) in enumerate(trace) if abs(r) <= 1e-10) + 1]
    steps = [(abs(b[0] - a[0]), abs(a[1])) for a, b in zip(primary, primary[1:])]
    assert any(step <= 1e-12 and r > 1e-10 for step, r in steps)


def test_stagnation_is_reported_only_below_the_attainable_resolution():
    """u^2 - 2 with residual tolerance 1e-300: fl(sqrt 2)^2 - 2 != 0, so the residual cannot reach the tolerance."""
    with pytest.raises(NonlinearError) as caught:
        solve(lambda z: z**2 - 2, lambda z: np.array([[2 * z[0]]]), [1.], [[.1, 4.]], [1.], [1.],
              residual_tolerance=1e-300, step_tolerance=1e-12)
    diagnostic = caught.value.diagnostic
    assert diagnostic['code'] == 'nonlinear_stagnation'
    assert diagnostic['stepNorm'] <= RESOLUTION_ULPS * np.spacing(2.)
    assert 'attainable binary64 resolution' in diagnostic['message']
    assert set(diagnostic) == {'code', 'message', 'terminationReason', 'iterations', 'evaluations', 'backtracks',
                               'residualNorm', 'stepNorm', 'conditionInfinity'}


def test_a_large_step_tolerance_no_longer_stops_before_the_residual_tolerance():
    """Previously step_tolerance = 1 ended the first iteration as stagnation; now Newton continues to the root."""
    z, detail = solve(lambda z: z**2 - 2, lambda z: np.array([[2 * z[0]]]), [1.], [[.1, 4.]], [1.], [1.],
                      residual_tolerance=1e-10, step_tolerance=1.)
    assert detail['terminationReason'] == 'converged'
    assert abs(z[0] - float(mp.sqrt(2))) < 1e-10


def test_step_tolerance_below_the_resolution_is_floored_by_it():
    """(z / 1e6)^2 = 3 at unit scale: z ~ 1.7e6 cannot move by less than ~2.3e-10, so a declared step tolerance of
    1e-14 is unattainable. The previous rule ended in nonlinear_line_search; the step test now uses the resolution."""
    root = mp.mpf(10)**6 * mp.sqrt(3)
    z, detail = solve(lambda z: (z / 1e6)**2 - 3, lambda z: np.array([[2 * z[0] / 1e12]]), [1.5e6], [[1e6, 2e6]],
                      [1.], [1.], residual_tolerance=1e-10, step_tolerance=1e-14)
    assert detail['terminationReason'] == 'converged' and detail['stepNorm'] > 1e-14
    assert detail['stepNorm'] <= RESOLUTION_ULPS * np.spacing(z[0])
    assert abs(mp.mpf(z[0]) - root) <= 2 * np.spacing(z[0])


def test_returned_evidence_keys_are_unchanged():
    """Results contract (core/resultados/formato.py, steady contract): no new solver evidence keys."""
    _, detail = solve(lambda z: z**2 - 2, lambda z: np.array([[2 * z[0]]]), [1.], [[.1, 4.]], [1.], [1.])
    assert set(detail) == {'iterations', 'evaluations', 'backtracks', 'residualNorm', 'stepNorm', 'conditionInfinity',
                           'terminationReason', 'completedProbes', 'uniqueness'}
