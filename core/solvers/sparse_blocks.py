"""Reproducible sparse assembly from equation-variable incidence, policy v2."""
import numpy as np
import sympy as sp
from core.mathematics.numeric_lowering import lambdify_numeric
from scipy.sparse import csc_matrix, issparse
from scipy.sparse.linalg import splu, LinearOperator, svds


def policy(size, nonzeros, requested='auto'):
    if requested not in ('auto', 'dense', 'sparse'):
        raise ValueError('Unknown linear algebra policy.')
    selected = 'dense' if requested == 'auto' else requested
    return {'version': 2, 'requested': requested, 'selected': selected,
            'size': size, 'structuralNonzeros': nonzeros,
            'rule': 'auto: dense; no reproducible sparse crossover established through 40 volumes; explicit sparse available; no failure fallback'}


class ExpressionJacobian:
    """Symbolic local blocks plus one finite-difference closure block per volume.

    A closure block is (outputs, dependent column indices, evaluate(t, state)).
    Only that closure is probed for its local columns. Symbolic chain-rule
    multiplication shares its derivative across every residual using the volume.
    """
    def __init__(self, expressions, variables, time, scales, closures=(), requested='auto'):
        self.scales = np.asarray(scales, dtype=float)
        self.closures = list(closures)
        self.closure_blocks = 0
        self.closure_probes = 0
        x = [sp.Dummy('jac_x_'+str(i), real=True) for i in range(len(variables))]
        outputs = [q for block, _, _ in closures for q in block]
        c = [sp.Dummy('jac_c_'+str(i), real=True) for i in range(len(outputs))]
        mapping = dict(zip([*variables, *outputs], [*x, *c]))
        expressions = [e.xreplace(mapping) for e in expressions]
        edges = set()
        self.direct = []
        self.indirect = []
        for i, expression in enumerate(expressions):
            for j, symbol in enumerate(x):
                if expression.has(symbol):
                    edges.add((i, j))
                    self.direct.append((i, j, sp.diff(expression, symbol)))
            offset = 0
            for block, columns, _ in closures:
                for k in range(len(block)):
                    if expression.has(c[offset+k]):
                        edges.update((i, j) for j in columns)
                        self.indirect.append((i, offset+k, sp.diff(expression, c[offset+k])))
                offset += len(block)
        self.shape = (len(expressions), len(variables))
        self.edges = sorted(edges)
        self.policy = policy(len(variables), len(edges), requested)
        self.function = lambdify_numeric([time, x, c],
            [e for _, _, e in self.direct+self.indirect], modules='numpy', cse=True)

    def __call__(self, time, state):
        state = np.asarray(state, dtype=float)
        values = []
        blocks = []
        offset = 0
        for outputs, columns, evaluate in self.closures:
            values.extend(evaluate(time, state))
            self.closure_blocks += 1
            for column in sorted(columns):
                step = 1e-6 * max(abs(state[column]), self.scales[column])
                up, down = state.copy(), state.copy()
                up[column] += step
                down[column] -= step
                derivative = (np.asarray(evaluate(time, up))-np.asarray(evaluate(time, down)))/(2*step)
                self.closure_probes += 2
                if derivative.shape != (len(outputs),) or not np.all(np.isfinite(derivative)):
                    raise ValueError('Nonfinite closure Jacobian block or incompatible shape.')
                blocks.extend((offset+k, column, value) for k, value in enumerate(derivative) if value != 0)
            offset += len(outputs)
        evaluated = np.asarray(self.function(time, state, values), dtype=float)
        if not np.all(np.isfinite(evaluated)):
            raise ValueError('Nonfinite Jacobian block.')
        def matrix(rows, data, shape):
            return csc_matrix((data, ([i for i, _, _ in rows], [j for _, j, _ in rows])), shape=shape)
        direct = matrix(self.direct, evaluated[:len(self.direct)], self.shape)
        if self.indirect:
            outer = matrix(self.indirect, evaluated[len(self.direct):], (self.shape[0], offset))
            inner = matrix(blocks, [v for _, _, v in blocks], (offset, self.shape[1]))
            direct = direct + outer @ inner
        return direct if self.policy['selected'] == 'sparse' else direct.toarray()


def factor_step(jacobian, residual, xs, rs, requested='auto'):
    """Scaled correction and the existing regularity metrics, without dense LU fallback."""
    sparse = issparse(jacobian)
    nnz = jacobian.nnz if sparse else np.count_nonzero(jacobian)
    selected = policy(len(xs), nnz, requested)['selected']
    if selected == 'dense':
        j = (jacobian.toarray() if sparse else np.asarray(jacobian)) * xs[None, :] / rs[:, None]
        if j.shape != (len(xs), len(xs)) or not np.all(np.isfinite(j)):
            raise ValueError('Nonfinite Jacobian or incompatible shape.')
        condition = float(np.linalg.cond(j, p=np.inf))
        smallest = float(np.linalg.svd(j, compute_uv=False)[-1])
        return np.linalg.solve(j, -residual), condition, smallest
    j = csc_matrix(jacobian).multiply(xs[None, :]).multiply(1/rs[:, None]).tocsc()
    if j.shape != (len(xs), len(xs)) or not np.all(np.isfinite(j.data)):
        raise ValueError('Nonfinite Jacobian or incompatible shape.')
    try:
        lu = splu(j, permc_spec='COLAMD')
    except RuntimeError as error:
        raise np.linalg.LinAlgError(str(error)) from error
    # Exact infinity norm of the inverse, accumulated by columns. No dense
    # inverse or dense factorization is constructed for the sparse path.
    sums = np.zeros(len(xs))
    for column in range(len(xs)):
        unit = np.zeros(len(xs)); unit[column] = 1
        sums += np.abs(lu.solve(unit))
    condition = float(np.max(np.asarray(abs(j).sum(axis=1))) * np.max(sums))
    inverse = LinearOperator(j.shape, matvec=lu.solve,
        rmatvec=lambda v: lu.solve(v, trans='T'), matmat=lu.solve, dtype=float)
    if len(xs) == 1:
        smallest = abs(float(j[0, 0]))
    else:
        try:
            largest_inverse = svds(inverse, k=1, which='LM', return_singular_vectors=False,
                                  v0=np.ones(len(xs)), tol=1e-12, random_state=0)[0]
        except RuntimeError as error:
            raise np.linalg.LinAlgError('Sparse regularity iteration failed: '+str(error)) from error
        if not np.isfinite(largest_inverse) or largest_inverse <= 0:
            raise np.linalg.LinAlgError('Sparse regularity iteration returned an invalid inverse norm.')
        smallest = float(1/largest_inverse)
    return lu.solve(-residual), condition, smallest
