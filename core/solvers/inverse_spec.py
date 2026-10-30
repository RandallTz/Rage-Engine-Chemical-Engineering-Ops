"""Inverse specifications for the common steady residual solve (F3 slice 5).

An inverse specification is a Solve-workspace residual ``g(x, p) - target = 0``
paired, as a set, with freed inputs ``p`` that change from data to unknowns.
It is never a Model equation: Model and Transform signatures are unchanged.

The augmented unknown vector is ``w = [x, p]`` (forward unknowns first) and the
augmented residual is ``[F(x, p); g(x, p) - target]`` (forward rows first). The
count must stay square: one specification per freed input. Admission checks a
complete structural matching of the augmented incidence and the local rank of
the scaled augmented Jacobian at the seed. The solve is the unchanged damped
Newton of ``core.solvers.nonlinear``. When it fails for a single specification,
forward solves along the freed-input interval report whether the target lies
outside the sampled reachable range (limited by a bound or by a turning point);
the target is never clipped. Sampling is finite evidence, not a global proof.
"""
import math

import numpy as np

from core.solvers import nonlinear

FORMAT = 'rage.inverse-specification'
EPS = np.finfo(float).eps
# Same absolute/relative regularity gates as the Newton engine.
REGULARITY_LIMIT = 1e-8


class InverseError(Exception):
    def __init__(self, code, message, **evidence):
        super().__init__(message)
        self.code = code
        self.diagnostic = {'code': code, 'message': message, **evidence}


def _keys(value, expected, where):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise InverseError('inverse_invalid_specification', where+' requires exactly the fields '+', '.join(expected)+'.')


def _identity(text, where):
    if not isinstance(text, str) or not text.strip() or len(text) > 160:
        raise InverseError('inverse_invalid_specification', where+': a nonempty identity is required.')


def read_specification(value):
    """Strict reader of the versioned Solve-workspace record; rejects non-square sets before solving."""
    _keys(value, ['format', 'version', 'specifications', 'freedInputs'], 'Inverse specification')
    if value['format'] != FORMAT or type(value['version']) is not int or value['version'] != 1:
        raise InverseError('inverse_invalid_specification', 'Expected '+FORMAT+' version 1.')
    specs, freed = value['specifications'], value['freedInputs']
    if not isinstance(specs, list) or not isinstance(freed, list) or len(specs) > 50 or len(freed) > 50:
        raise InverseError('inverse_invalid_specification', 'Specifications and freed inputs must be lists.')
    for row in specs:
        _keys(row, ['id', 'quantityId', 'targetDataId', 'residualScaleDataId'], 'A specification')
        for item in row.values(): _identity(item, 'Specification')
    for row in freed:
        _keys(row, ['quantityId', 'seedDataId', 'lowerDataId', 'upperDataId', 'scaleDataId'], 'A freed input')
        for item in row.values(): _identity(item, 'Freed input')
    if not specs and not freed:
        raise InverseError('inverse_not_square', 'An inverse study needs at least one specification and one freed input.')
    if len(specs) != len(freed):
        raise InverseError('inverse_not_square',
            f'{len(specs)} specification(s) and {len(freed)} freed input(s): every added output residual needs exactly one input changed from data to unknown.',
            specifications=len(specs), freedInputs=len(freed))
    if len({r['id'] for r in specs}) != len(specs) or len({r['quantityId'] for r in specs}) != len(specs):
        raise InverseError('inverse_invalid_specification', 'Specification identities and specified quantities must be distinct.')
    if len({r['quantityId'] for r in freed}) != len(freed):
        raise InverseError('inverse_invalid_specification', 'A freed input can be released only once.')
    if {r['quantityId'] for r in specs} & {r['quantityId'] for r in freed}:
        raise InverseError('inverse_invalid_specification', 'A quantity cannot be both specified and freed.')
    return value


def structural_matching(incidence):
    """Complete row/column matching of a boolean square incidence; returns unmatched row indices."""
    incidence = np.asarray(incidence, dtype=bool)
    rows, columns = incidence.shape
    matched = {}
    def augment(row, seen):
        for column in np.flatnonzero(incidence[row]):
            if column in seen: continue
            seen.add(column)
            if column not in matched or augment(matched[column], seen):
                matched[column] = row
                return True
        return False
    unmatched = [row for row in range(rows) if not augment(row, set())]
    return unmatched if rows == columns else unmatched or [rows]


def check_structure(incidence, n_forward, labels=None):
    """Reject a freed input that cannot structurally reach the specified outputs."""
    incidence = np.asarray(incidence, dtype=bool)
    if incidence.shape[0] != incidence.shape[1]:
        raise InverseError('inverse_not_square', 'The augmented incidence is not square.')
    unmatched = structural_matching(incidence)
    if unmatched:
        names = [labels[i] for i in unmatched] if labels else unmatched
        raise InverseError('inverse_unreachable',
            'No complete equation/unknown matching of the augmented system: the freed input(s) do not structurally reach the specified output(s) through the forward equations.',
            unmatchedRows=names, forwardRows=n_forward)


def regularity(jacobian, variable_scales, residual_scales, n_forward):
    """Scaled augmented, forward and specification-sensitivity singular values at one point.

    With a regular forward block A, the augmented Jacobian [[A, B], [C, D]] is regular
    exactly when the Schur complement S = D - C A^-1 B (the scaled sensitivity of the
    specified outputs to the freed inputs along the forward solution) is regular.
    """
    j = np.asarray(jacobian, dtype=float)*np.asarray(variable_scales, float)[None, :]/np.asarray(residual_scales, float)[:, None]
    if not np.all(np.isfinite(j)):
        raise InverseError('inverse_nonfinite', 'The augmented Jacobian is not finite at the evaluated point.')
    a, b, c, d = j[:n_forward, :n_forward], j[:n_forward, n_forward:], j[n_forward:, :n_forward], j[n_forward:, n_forward:]
    sigma = lambda m: float(np.linalg.svd(m, compute_uv=False)[-1]) if m.size else math.inf
    evidence = {'augmentedSigmaMin': sigma(j), 'forwardSigmaMin': sigma(a), 'sensitivitySigmaMin': None, 'sensitivity': None}
    if evidence['forwardSigmaMin'] > 0 and EPS/evidence['forwardSigmaMin'] <= REGULARITY_LIMIT:
        s = d - c @ np.linalg.solve(a, b) if n_forward else d
        evidence['sensitivity'] = s.tolist(); evidence['sensitivitySigmaMin'] = sigma(s)
    return evidence


def check_regularity(evidence, where='seed'):
    if evidence['augmentedSigmaMin'] > 0 and EPS/evidence['augmentedSigmaMin'] <= REGULARITY_LIMIT:
        return
    if evidence['sensitivitySigmaMin'] is not None:
        raise InverseError('inverse_rank_deficient',
            f'At the {where} the forward block is regular but the specified output(s) are locally insensitive to the freed input(s) (scaled sensitivity sigma_min={evidence["sensitivitySigmaMin"]:.3g}); free a different input, or change the seed if this is an isolated stationary point.',
            regularity=evidence)
    raise InverseError('inverse_rank_deficient',
        f'The scaled augmented Jacobian is numerically singular at the {where} (sigma_min={evidence["augmentedSigmaMin"]:.3g}).', regularity=evidence)


def reachable_scan(residual, jacobian, n_forward, targets, seed, bounds, variable_scales, residual_scales,
                   admissible=None, samples=33, settings=None):
    """Forward solves along the single freed input's interval (natural-parameter continuation).

    Each forward solve is the same damped Newton with the freed input fixed; the previous
    converged state seeds the next sample. Returns the sampled (input, output) pairs and the
    (input, Newton code) of every sample whose forward solve failed.
    """
    seed = np.asarray(seed, float); bounds = np.asarray(bounds, float)
    if len(seed) != n_forward+1:
        raise InverseError('inverse_scan_unsupported', 'The reachable-range scan covers one specification and one freed input.')
    settings = settings or {}
    xs = np.asarray(variable_scales, float)[:n_forward]; rs = np.asarray(residual_scales, float)[:n_forward]
    lo, hi = bounds[n_forward]
    points, failures, state = [], [], seed[:n_forward].copy()
    for p in np.linspace(lo, hi, samples):
        f = lambda x: np.asarray(residual(np.append(x, p)), float)[:n_forward]
        jf = lambda x: np.asarray(jacobian(np.append(x, p)), float)[:n_forward, :n_forward]
        ok = None if admissible is None else (lambda x: admissible(np.append(x, p)))
        start = state if (ok is None or ok(state)) and np.all(state >= bounds[:n_forward, 0]) and np.all(state <= bounds[:n_forward, 1]) else seed[:n_forward]
        try:
            x, _ = nonlinear.solve(f, jf, start, bounds[:n_forward], xs, rs, admissible=ok, **settings)
        except nonlinear.NonlinearError as error:
            failures.append((float(p), error.code))
            continue
        state = x
        output = float(np.asarray(residual(np.append(x, p)), float)[n_forward]) + float(targets[0])
        points.append((float(p), output))
    return points, failures


def sample_evidence(points, failures, target):
    values = [g for _, g in points]
    return {'target': float(target), 'sampledRange': [min(values), max(values)] if values else None,
            'convergedSamples': len(points), 'failedSamples': len(failures),
            'samples': [{'input': q, 'output': g} for q, g in points],
            'failedInputs': [{'input': q, 'code': c} for q, c in failures]}


def classify_unattainable(points, failures, target, bound):
    """Evidence that a single target lies outside the sampled reachable range, or None.

    The range is only conclusive when every forward sample converged: a failed sample may
    hide the reachable branch. ``bound`` is the declared freed-input interval; the limit is a
    bound only when the extremum sits on it, otherwise an interior turning point.
    """
    if failures or len(points) < 2:
        return None
    values = [g for _, g in points]
    low, high = min(values), max(values)
    if low <= target <= high:
        return None
    index = values.index(high if target > high else low)
    extremum = points[index][0]
    limit = 'bound' if any(math.isclose(extremum, b, rel_tol=1e-12, abs_tol=1e-12) for b in bound) else 'turning_point'
    return {'kind': limit, 'extremumInput': extremum, 'declaredBounds': [float(b) for b in bound],
            **sample_evidence(points, failures, target),
            'scope': 'Finite forward samples over the declared freed-input interval, all converged; the range is evidence, not a global proof.'}


class InverseProblem:
    """Augmented residual over w = [x, p]; rows are the forward rows then g(w) - target."""

    def __init__(self, residual, jacobian, n_forward, targets, seed, bounds, variable_scales, residual_scales,
                 incidence, labels=None, admissible=None, settings=None):
        self.residual, self.jacobian, self.n_forward = residual, jacobian, n_forward
        self.targets = [float(t) for t in targets]
        self.seed = np.asarray(seed, float); self.bounds = np.asarray(bounds, float)
        self.variable_scales = np.asarray(variable_scales, float); self.residual_scales = np.asarray(residual_scales, float)
        self.admissible = admissible; self.settings = settings or {}
        n = len(self.seed); m = n - n_forward
        if m < 1 or m != len(self.targets) or len(self.residual_scales) != n:
            raise InverseError('inverse_not_square', f'{len(self.targets)} specification(s) for {m} freed input(s) and {n_forward} forward row(s).')
        if not all(math.isfinite(t) for t in self.targets):
            raise InverseError('inverse_invalid_specification', 'Targets must be finite.')
        self.labels = labels
        check_structure(incidence, n_forward, labels)

    def check(self):
        evidence = regularity(self.jacobian(self.seed), self.variable_scales, self.residual_scales, self.n_forward)
        check_regularity(evidence)
        return evidence

    def diagnose(self, error):
        """Turn a Newton failure into an unattainable-target diagnosis when the scan proves one.

        Otherwise the original Newton failure is returned unchanged, with the samples attached.
        """
        if len(self.targets) != 1:
            return None
        points, failures = reachable_scan(self.residual, self.jacobian, self.n_forward, self.targets, self.seed, self.bounds,
                                          self.variable_scales, self.residual_scales, self.admissible, settings=self.settings)
        verdict = classify_unattainable(points, failures, self.targets[0], self.bounds[self.n_forward])
        newton = getattr(error, 'diagnostic', None) or {}
        if verdict is None:
            return InverseError(newton.get('code', getattr(error, 'code', 'nonlinear_failure')), newton.get('message', str(error)),
                                **{k: v for k, v in newton.items() if k not in ('code', 'message')},
                                reachability={'kind': 'inconclusive', **sample_evidence(points, failures, self.targets[0])})
        where = 'a bound of the freed input' if verdict['kind'] == 'bound' else f'an interior turning point near input {verdict["extremumInput"]:.6g}'
        return InverseError('inverse_target_unattainable',
            f'Target {self.targets[0]:.6g} lies outside the sampled reachable range [{verdict["sampledRange"][0]:.6g}, {verdict["sampledRange"][1]:.6g}], limited by {where}; the target is not clipped.',
            reachability=verdict, newton=getattr(error, 'diagnostic', None))

    def solve(self):
        seed_regularity = self.check()
        try:
            root, detail = nonlinear.solve(self.residual, self.jacobian, self.seed, self.bounds, self.variable_scales,
                                           self.residual_scales, admissible=self.admissible, **self.settings)
        except nonlinear.NonlinearError as error:
            if error.code == 'nonlinear_multiple_roots':
                raise InverseError(error.code, str(error), newton=error.diagnostic) from error
            raise (self.diagnose(error) or InverseError(error.code, str(error), newton=error.diagnostic)) from error
        final = regularity(self.jacobian(root), self.variable_scales, self.residual_scales, self.n_forward)
        values = np.asarray(self.residual(root), float)
        return root, {'verdict': 'local_regular_root', 'globalUniqueness': 'not_proved', 'solver': detail,
                      'seedRegularity': seed_regularity, 'rootRegularity': final,
                      'specificationResiduals': (values[self.n_forward:]).tolist(),
                      'maxScaledResidual': float(np.max(np.abs(values)/self.residual_scales))}
