"""Independent review of F5 item 1 (16 November 2026): reproducers for the max-over-coordinates resolution.

`core/solvers/nonlinear.py` on `claude/f5-feed-temperature-24a75d` takes the attainable step as
max_i 4 spacing(z_i) / x_i and compares it with the infinity norm of the scaled step. With coordinates of very
different magnitude at the same declared scale, the largest coordinate's resolution then hides a step that is
still large relative to a small coordinate:

1. a regular, decoupled system whose small coordinate is 1e-10 (1e-4 relative) from its root ends in
   `nonlinear_stagnation`; the previous solver converged to the root within 1e-15 relative;
2. with the residual already inside its tolerance, convergence is accepted at a step 5x the declared step
   tolerance and the small coordinate keeps a 5e-6 relative error (previous solver: 3e-15).

Both passed on `origin/fase-a-adopcion` (543d123) and failed on the branch; kept as regression tests of the
per-coordinate repair (claude-b, 16 November 2026). A per-coordinate test
(stagnation only when every |step_i| <= 4 spacing(z_i)/x_i; convergence when the step norm is within the step
tolerance or every |step_i| is within its own resolution) keeps the near-complete-conversion cases.
"""
import numpy as np

from core.solvers.nonlinear import solve

A = 1e-6


def residual(z):
    return np.array([z[0] - 1e6, 10 * (z[1] - A) + 1e3 * (z[1] - A)**2])


def jacobian(z):
    return np.array([[1., 0.], [0., 10 + 2e3 * (z[1] - A)]])


BOUNDS = [[5e5, 2e6], [0., 1e-5]]


def test_a_resolvable_small_coordinate_is_not_reported_as_stagnation():
    z, detail = solve(residual, jacobian, [1e6, A + 1e-10], BOUNDS, [1., 1.], [1., 1.])
    assert detail['terminationReason'] == 'converged'
    assert abs(z[1] - A) / A < 1e-12


def test_convergence_is_not_accepted_above_the_step_tolerance_while_a_coordinate_still_resolves_it():
    z, detail = solve(residual, jacobian, [1e6, A + 5e-12], BOUNDS, [1., 1.], [1., 1.],
                      residual_tolerance=1e-10, step_tolerance=1e-12)
    assert detail['terminationReason'] == 'converged'
    assert abs(z[1] - A) / A < 1e-12
