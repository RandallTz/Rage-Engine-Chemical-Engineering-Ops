"""Dense damped Newton with explicit scales, bounded trials and typed failures.

The primary solve always starts from the declared seed. Additional deterministic
probes detect competing roots; finite probing is not a global uniqueness proof.
No probe result replaces a failed primary solve.

Termination is scaled to the attainable resolution of the iterate (F5 item 1).
In declared scaled units a coordinate z_i cannot move by less than one unit in
the last place, spacing(z_i) / x_i, so ``RESOLUTION_ULPS`` such units bound the
step component that binary64 can still realise in that coordinate. The test is
per coordinate (repair of the 16 November 2026 review): the coarsest coordinate
never hides a step that still resolves, and is large, in a small one. A Newton
step smaller than the declared step tolerance whose components still change the
iterate is taken: near-complete conversion, where d(ln a)/d(xi) ~ 1/n is large,
needs such steps before the residual meets its tolerance. Stagnation is reported
only when every step component is within its own coordinate's resolution while
the residual still exceeds its tolerance; the residual tolerance is then finer
than the residual can be resolved at the root. The convergence step test is
||step||_inf <= step_tolerance, or every step component within its own
coordinate's resolution. The published evidence keys are a
versioned Results contract and are unchanged; the resolution appears only in
the stagnation message.

Termination at the residual's round-off (F5 item 1 follow-up, 17 November 2026).
Near a root the evaluated residual is dominated by its own rounding error; the
Newton step is then that error amplified by the inverse Jacobian, and its size
depends on the CPU kernel (CI group-9: scaled residual 2.4e-14 against 1e-10,
step 4.45e-9, cond_inf 9e4 on Cooperlake; converged on Zen). Such a step is
above the step tolerance and the coordinate resolution, and no backtracked trial
can lower a merit already at round-off. An iterate is therefore also converged
when (1) its scaled residual meets the residual tolerance, (2) every backtracked
trial was evaluated and none gave sufficient decrease (a domain or nonfinite
failure never counts), and (3) ||step||_inf <= roundoff_step(n, ||r||_inf,
sigma_min), the bound that any Newton step J^-1 r obeys and that a reader can
check from the published residual norm and smallest singular value. A finite
residual that is not round-off always admits a sufficient-decrease trial along
the Newton direction, so (2) is the evidence that (1) is reached at round-off.
The tolerances are unchanged; the step is the root's position uncertainty and is
used as its floor in the probe comparison.
"""
import numpy as np

RESOLUTION_ULPS = 4


class NonlinearError(Exception):
    def __init__(self, code, message, **evidence):
        super().__init__(message)
        self.code = code
        self.diagnostic = {'code': code, 'message': message, 'terminationReason': code,
                           'iterations': 0, 'evaluations': 0, 'backtracks': 0,
                           'residualNorm': None, 'stepNorm': None, 'conditionInfinity': None,
                           **evidence, 'terminationReason': code}


def roundoff_step(n, residual_norm, smallest_singular_value):
    """Largest scaled Newton step ||J^-1 r||_inf that a residual of infinity norm residual_norm can produce:
    ||c||_inf <= ||c||_2 <= ||r||_2 / sigma_min <= sqrt(n) ||r||_inf / sigma_min, with a factor 2 for the
    rounding of sigma_min itself. Mirrored by core/compilador/steady.py::read_result. A nonpositive sigma_min
    gives no bound (inf); both callers reject such a Jacobian by their own regularity gates."""
    if not smallest_singular_value > 0:
        return np.inf
    return 2 * np.sqrt(n) * residual_norm / smallest_singular_value


def solve(residual, jacobian, seed, bounds, variable_scales, residual_scales, *,
          residual_tolerance=1e-10, step_tolerance=1e-12, max_iterations=30,
          max_backtracks=20, admissible=None, linear_solver='dense'):
    seed = np.asarray(seed, dtype=float)
    bounds = np.asarray(bounds, dtype=float)
    xs = np.asarray(variable_scales, dtype=float)
    rs = np.asarray(residual_scales, dtype=float)
    n = len(seed)
    if (not n or seed.shape != (n,) or bounds.shape != (n, 2) or xs.shape != (n,) or rs.shape != (n,)
            or not all(np.all(np.isfinite(v)) for v in (seed, bounds, xs, rs))
            or np.any(xs <= 0) or np.any(rs <= 0) or np.any(bounds[:, 0] >= bounds[:, 1])
            or not np.isfinite(residual_tolerance) or residual_tolerance <= 0
            or not np.isfinite(step_tolerance) or step_tolerance <= 0
            or type(max_iterations) is not int or not 1 <= max_iterations <= 30
            or type(max_backtracks) is not int or not 1 <= max_backtracks <= 20):
        raise NonlinearError('nonlinear_invalid_settings', 'Finite positive scales/tolerances and ordered finite bounds are required; iteration limits cannot exceed 30/20.')

    def inside(z):
        if not np.all(np.isfinite(z)) or np.any(z < bounds[:, 0]) or np.any(z > bounds[:, 1]):
            return False
        try:
            return admissible is None or bool(admissible(z))
        except (ArithmeticError, ValueError):
            return False

    def resolution(z):
        # Smallest realisable scaled step of each coordinate at z (a few units in the last place).
        return RESOLUTION_ULPS * np.spacing(np.abs(z)) / xs

    def iterate(start):
        evidence = dict(iterations=0, evaluations=0, backtracks=0,
                        residualNorm=None, stepNorm=None, conditionInfinity=None)
        def fail(code, message):
            raise NonlinearError(code, message, **evidence)
        def evaluate(z):
            evidence['evaluations'] += 1
            try:
                with np.errstate(over='raise', invalid='raise', divide='raise'):
                    value = np.asarray(residual(z), dtype=float) / rs
                if value.shape != (n,) or not np.all(np.isfinite(value)):
                    raise ValueError('Nonfinite residual or incompatible shape.')
                return value
            except (ArithmeticError, ValueError) as error:
                fail('nonlinear_nonfinite', str(error))

        cached = (None, None)
        z = np.array(start, copy=True)
        if not inside(z):
            fail('nonlinear_invalid_seed', 'The declared seed is outside the admitted domain.')
        r = evaluate(z)
        for iteration in range(max_iterations + 1):
            evidence['iterations'] = iteration
            evidence['residualNorm'] = float(np.linalg.norm(r, ord=np.inf))
            try:
                from .sparse_blocks import factor_step
                matrix = cached[1] if cached[0] is not None and np.array_equal(cached[0], z) else jacobian(z)
                correction, condition, smallest = factor_step(matrix, r, xs, rs, linear_solver)
                evidence['conditionInfinity'] = condition if np.isfinite(condition) else None
                if not np.isfinite(condition):
                    fail('nonlinear_singular_jacobian', 'The scaled algebraic Jacobian is singular.')
                if condition * np.finfo(float).eps > 1e-8:
                    fail('nonlinear_ill_conditioned', 'Scaled Jacobian cond_inf * epsilon exceeds 1e-8.')
                # Relative conditioning alone cannot detect a uniformly small
                # Jacobian (in particular cond([j]) == 1 for every j != 0).
                # Bound absolute inverse amplification in declared scaled units.
                if smallest <= 0 or np.finfo(float).eps / smallest > 1e-8:
                    fail('nonlinear_ill_conditioned',
                         f'Scaled Jacobian epsilon / sigma_min exceeds 1e-8 (sigma_min={smallest:.12g}); review the root regularity and declared scales.')
            except np.linalg.LinAlgError:
                fail('nonlinear_singular_jacobian', 'The algebraic Jacobian cannot be factored.')
            except (ArithmeticError, ValueError) as error:
                fail('nonlinear_nonfinite', str(error))
            if not np.all(np.isfinite(correction)):
                fail('nonlinear_nonfinite', 'The scaled Newton correction is not representable.')
            evidence['stepNorm'] = float(np.linalg.norm(correction, ord=np.inf))
            attainable = resolution(z)
            unresolvable = bool(np.all(np.abs(correction) <= attainable))
            if (evidence['residualNorm'] <= residual_tolerance
                    and (evidence['stepNorm'] <= step_tolerance or unresolvable)):
                return z, {**evidence, 'terminationReason': 'converged'}, float(np.max(attainable))
            if iteration == max_iterations:
                fail('nonlinear_iteration_limit', 'The Newton iteration budget was exhausted without convergence.')
            if unresolvable:
                fail('nonlinear_stagnation', 'Every Newton step component is below the attainable binary64 resolution of its '
                     f'coordinate (at most {float(np.max(attainable)):.3g} scaled) but the scaled residual exceeds its tolerance; the residual tolerance is '
                     'finer than the residual can be resolved at this root.')
            with np.errstate(over='ignore'):
                merit = float(np.dot(r, r))
            if not np.isfinite(merit):
                fail('nonlinear_nonfinite', 'The scaled merit function is not representable.')
            # Start within the declared box even when the full Newton step
            # crosses a boundary. Backtracking alone can exhaust its budget
            # when the admissible interval is much smaller than the step.
            direction = xs * correction
            factor = 1.
            for index, delta in enumerate(direction):
                if delta > 0 and delta > bounds[index, 1] - z[index]:
                    factor = min(factor, .99 * (bounds[index, 1] - z[index]) / delta)
                elif delta < 0 and -delta > z[index] - bounds[index, 0]:
                    factor = min(factor, .99 * (z[index] - bounds[index, 0]) / -delta)
            if factor <= 0 or not np.isfinite(factor) or np.array_equal(z + factor * direction, z):
                fail('nonlinear_domain', 'The Newton direction cannot advance inside the declared bounds.')
            last_failure = 'nonlinear_line_search'
            for backtrack in range(max_backtracks):
                trial = z + factor * direction
                if not inside(trial):
                    last_failure = 'nonlinear_domain'
                else:
                    try:
                        candidate = evaluate(trial)
                    except NonlinearError as error:
                        if error.code != 'nonlinear_nonfinite':
                            raise
                        last_failure = error.code
                    else:
                        last_failure = 'nonlinear_line_search'
                        if float(np.dot(candidate, candidate)) <= (1 - 2e-4 * factor) * merit:
                            # An iterate is admitted only where the Jacobian is also
                            # evaluable; a domain error there rejects this trial like
                            # a residual-domain error (RT-11).
                            try:
                                cached = (trial, jacobian(trial))
                            except (ArithmeticError, ValueError):
                                last_failure = 'nonlinear_nonfinite'
                            else:
                                z, r = trial, candidate
                                break
                evidence['backtracks'] += 1
                factor *= .5
            else:
                if (last_failure == 'nonlinear_line_search' and evidence['residualNorm'] <= residual_tolerance
                        and evidence['stepNorm'] <= roundoff_step(n, evidence['residualNorm'], smallest)):
                    # The residual meets its tolerance and no trial lowers a merit already at round-off.
                    return z, {**evidence, 'terminationReason': 'converged'}, max(float(np.max(attainable)), evidence['stepNorm'])
                fail(last_failure, 'No admissible sufficient-decrease Newton step within the backtracking budget.')
        raise AssertionError('Unreachable Newton termination')

    root, evidence, root_floor = iterate(seed)
    midpoint = (bounds[:, 0] + bounds[:, 1]) / 2
    probes = [midpoint, bounds[:, 0], bounds[:, 1]]
    for k in range(n):
        for edge in bounds[k]:
            probe = midpoint.copy(); probe[k] = edge; probes.append(probe)
    completed = 0
    for probe in probes:
        if np.array_equal(probe, seed) or not inside(probe):
            continue
        try:
            other, detail, other_floor = iterate(probe)
        except NonlinearError as error:
            # A failed diagnostic probe is neither a root nor a fallback.
            evidence['evaluations'] += error.diagnostic['evaluations']
            continue
        completed += 1
        evidence['evaluations'] += detail['evaluations']
        distance = float(np.linalg.norm((other-root)/xs, ord=np.inf))
        uncertainty = max(100*max(step_tolerance, root_floor, other_floor),
                          10*residual_tolerance*max(evidence['conditionInfinity'], detail['conditionInfinity']))
        if distance > uncertainty:
            raise NonlinearError('nonlinear_multiple_roots', 'Deterministic probes found distinct admissible roots; select an unambiguous domain.', **evidence)
    return root, {**evidence, 'completedProbes': completed,
                  'uniqueness': 'local_root_only; finite probes do not prove global uniqueness'}
