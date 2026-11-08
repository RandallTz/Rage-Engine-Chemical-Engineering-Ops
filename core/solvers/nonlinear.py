"""Dense damped Newton with explicit scales, bounded trials and typed failures.

The primary solve always starts from the declared seed. Additional deterministic
probes detect competing roots; finite probing is not a global uniqueness proof.
No probe result replaces a failed primary solve.
"""
import numpy as np


class NonlinearError(Exception):
    def __init__(self, code, message, **evidence):
        super().__init__(message)
        self.code = code
        self.diagnostic = {'code': code, 'message': message, 'terminationReason': code,
                           'iterations': 0, 'evaluations': 0, 'backtracks': 0,
                           'residualNorm': None, 'stepNorm': None, 'conditionInfinity': None,
                           **evidence, 'terminationReason': code}


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
            if (evidence['residualNorm'] <= residual_tolerance
                    and evidence['stepNorm'] <= step_tolerance):
                return z, {**evidence, 'terminationReason': 'converged'}
            if iteration == max_iterations:
                fail('nonlinear_iteration_limit', 'The Newton iteration budget was exhausted without convergence.')
            if evidence['stepNorm'] <= step_tolerance:
                fail('nonlinear_stagnation', 'The Newton step is small but the residual exceeds tolerance.')
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
                fail(last_failure, 'No admissible sufficient-decrease Newton step within the backtracking budget.')
        raise AssertionError('Unreachable Newton termination')

    root, evidence = iterate(seed)
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
            other, detail = iterate(probe)
        except NonlinearError as error:
            # A failed diagnostic probe is neither a root nor a fallback.
            evidence['evaluations'] += error.diagnostic['evaluations']
            continue
        completed += 1
        evidence['evaluations'] += detail['evaluations']
        distance = float(np.linalg.norm((other-root)/xs, ord=np.inf))
        uncertainty = max(100*step_tolerance,
                          10*residual_tolerance*max(evidence['conditionInfinity'], detail['conditionInfinity']))
        if distance > uncertainty:
            raise NonlinearError('nonlinear_multiple_roots', 'Deterministic probes found distinct admissible roots; select an unambiguous domain.', **evidence)
    return root, {**evidence, 'completedProbes': completed,
                  'uniqueness': 'local_root_only; finite probes do not prove global uniqueness'}
