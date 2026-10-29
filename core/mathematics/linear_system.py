"""Constant affine blocks: exact admission and checked numerical SI solves.

No physics, compiler, or solver-family dependencies belong here.
"""
import numpy as np
import sympy as sp
from sympy.solvers.solveset import NonlinearError

from .constants import si_magnitude


class AffineBlockError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class ConstantAffineBlock:
    def __init__(self, residuals, unknowns, parameters):
        if not unknowns or len(residuals) != len(unknowns):
            raise AffineBlockError('invalid_algebraic_block', 'Select one distinct equation per algebraic unknown.')
        self.unknowns = tuple(unknowns)
        try:
            self.matrix, self.forcing = sp.linear_eq_to_matrix(residuals, unknowns)
        except (NonlinearError, ValueError) as error:
            raise AffineBlockError('nonlinear_algebraic_block', 'The selected block must be affine in all algebraic unknowns.') from error
        exact = self.matrix.applyfunc(lambda e: si_magnitude(e).subs(parameters))
        if any(e.is_number is not True or e.is_real is not True or e.is_finite is not True for e in exact):
            raise AffineBlockError('nonconstant_algebraic_matrix', 'Algebraic coefficients must resolve to finite real constants after parameter binding; time/state-dependent matrices are unsupported.')
        determinant = sp.simplify(exact.det())
        if determinant.is_zero is not False:
            raise AffineBlockError('singular_algebraic_block', 'The exact SI-bound determinant must be provably nonzero.')
        self.determinant = str(determinant)
        self.numeric = np.array(exact, dtype=float)
        if not np.isfinite(self.numeric).all():
            raise AffineBlockError('ill_conditioned_algebraic_block', 'The constant matrix is not representable in floating-point SI coordinates.')
        # Row/column equilibration limits sensitivity to the chosen SI dimensions.
        self.row_scale = np.max(np.abs(self.numeric), axis=1)
        if np.any(self.row_scale == 0):
            raise AffineBlockError('ill_conditioned_algebraic_block', 'A nonzero exact matrix row underflows in floating-point SI coordinates.')
        normalized = self.numeric / self.row_scale[:, None]
        self.column_scale = np.max(np.abs(normalized), axis=0)
        if np.any(self.column_scale == 0):
            raise AffineBlockError('ill_conditioned_algebraic_block', 'Matrix equilibration loses a nonzero exact column.')
        self.equilibrated = normalized / self.column_scale
        try:
            self.condition = float(np.linalg.cond(self.equilibrated, p=np.inf))
        except np.linalg.LinAlgError as error:
            raise AffineBlockError('ill_conditioned_algebraic_block', 'Matrix conditioning could not be evaluated.') from error
        if not np.isfinite(self.condition) or self.condition * np.finfo(float).eps > 1e-8:
            raise AffineBlockError('ill_conditioned_algebraic_block', 'Equilibrated infinity-norm condition number times machine epsilon exceeds 1e-8.')
        # These expressions certify equivalence/initialization/guards only.
        # Numerical RHS evaluation must call solve(), not this symbolic map.
        self.reconstruction = dict(zip(unknowns, self.matrix.inv() * self.forcing))

    def solve(self, forcing):
        b = np.asarray(forcing, dtype=float)
        if b.shape != (len(self.unknowns),) or not np.isfinite(b).all():
            raise AffineBlockError('algebraic_nonfinite', 'Algebraic forcing must be a finite vector matching the block.')
        try:
            with np.errstate(over='raise', invalid='raise', divide='raise'):
                z = np.linalg.solve(self.equilibrated, b / self.row_scale) / self.column_scale
                residual = self.numeric @ z - b
                scale = np.abs(self.numeric) @ np.abs(z) + np.abs(b)
        except (np.linalg.LinAlgError, FloatingPointError) as error:
            raise AffineBlockError('algebraic_solve_failed', 'The admitted affine block could not be solved.') from error
        if not np.isfinite(b).all() or not np.isfinite(z).all():
            raise AffineBlockError('algebraic_nonfinite', 'Algebraic forcing or solution is non-finite.')
        error = np.divide(np.abs(residual), scale, out=np.zeros_like(scale), where=scale != 0)
        if np.any((scale == 0) & (residual != 0)) or not np.isfinite(error).all() or np.max(error) > 64*np.finfo(float).eps:
            raise AffineBlockError('algebraic_residual_failed', 'The original SI block failed its componentwise backward-error check (64 machine epsilons).')
        return z, float(np.max(error))
