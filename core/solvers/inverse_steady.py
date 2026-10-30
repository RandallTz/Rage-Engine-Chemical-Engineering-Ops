"""Inverse specifications on the common steady residual solve (F3 slice 5).

The forward steady system is first admitted unchanged, with every input at its
declared datum. The Solve-workspace specification then releases the selected
parameter bindings, appends one typed residual ``quantity - target = 0`` per
specification and re-runs the slice-4 lowering steps (specialization, rational
admission, Groebner consistency, guards, constraint consequences and checks) on
the augmented block. The Newton solve, final original-row evaluation and
regularity evidence are the unchanged ``SteadySystem.solve``. No Model equation
is added and the Model/Transform signatures are retained.
"""
from types import SimpleNamespace

import numpy as np
import sympy as sp

from core.compilador.steady import (LoweringError, SteadySystem, locate, signature,
                                    steady_result_signature)
from core.solvers import inverse_spec

NEWTON_FAILURES = {'nonlinear_domain', 'nonlinear_line_search', 'nonlinear_iteration_limit', 'nonlinear_stagnation',
                   'nonlinear_singular_jacobian', 'nonlinear_ill_conditioned', 'nonlinear_nonfinite', 'nonlinear_invalid_seed'}


def _lowering(error):
    failure = LoweringError(error.code, str(error))
    failure.diagnostics = [{**error.diagnostic, 'code': error.code, 'message': str(error)}]
    return failure


class InverseSteadySystem(SteadySystem):
    def __init__(self, model, specification):
        super().__init__(model)
        try:
            self._augment(inverse_spec.read_specification(specification))
        except inverse_spec.InverseError as error:
            failure = _lowering(error); locate(model, failure); raise failure from error
        except LoweringError as error:
            locate(model, error); raise
        except (ValueError, TypeError, KeyError, ArithmeticError, NotImplementedError) as error:
            failure = LoweringError('inverse_invalid_specification', str(error)); locate(model, failure)
            raise failure from error

    def _equation(self, key):
        if key in getattr(self, 'specification_nodes', {}):
            return self.specification_nodes[key]
        return super()._equation(key)

    def _augment(self, specification):
        selection = self.selection
        forward_ids = list(selection['unknowns'])
        self.forward_formulation_signature = self.report['formulationSignature']
        outputs = set(forward_ids) | {row['quantityId'] for row in selection['reconstructions']}
        freed_rows, freed = specification['freedInputs'], []
        for row in freed_rows:
            qid = row['quantityId']
            if qid not in selection['parameters']:
                raise inverse_spec.InverseError('inverse_invalid_input',
                    qid+' is not a constant input of this steady selection; only declared parameters can be freed.')
            q = self._quantity(qid)
            if not isinstance(q, sp.Symbol):
                raise inverse_spec.InverseError('inverse_invalid_input', qid+': only a constant scalar input can be freed.')
            freed.append(q)
        self.specification_nodes = {}
        spec_rows, targets = [], []
        for row in specification['specifications']:
            qid = row['quantityId']
            if qid not in outputs:
                raise inverse_spec.InverseError('inverse_invalid_output',
                    qid+' is not a solved or reconstructed quantity; data, invariants and freed inputs cannot be specified.')
            q = self._quantity(qid)
            target = self._datum(row['targetDataId'], self._dim(q))
            key = 'specification.'+row['id']
            self.specification_nodes[key] = SimpleNamespace(equation=sp.Eq(q, target, evaluate=False), family='specification',
                                                            dependent=False, predicates=())
            spec_rows.append((key, row, q)); targets.append(float(target))
        # Release the freed bindings; constitutive substitutions that mention them stay symbolic.
        for q in freed: self.replacements.pop(q)
        self.unknowns = self.unknowns+freed
        self.parameter_records = [r for r in self.parameter_records if r['id'] not in {row['quantityId'] for row in freed_rows}]
        self.rows, self.identities = [], []
        for row in [*selection['states'], *selection['algebraic']]:
            key = row['equationId']; equation = self._equation(key).equation
            expression = self.specialize(equation.lhs-equation.rhs)
            if expression == 0:
                self.identities.append(key); continue
            if expression.is_number:
                self.fail('steady_constraint_conflict', 'A specialized physical law is a nonzero constant.', key)
            self.rows.append((key, expression, self._unit(equation.lhs-equation.rhs)))
        n_forward = len(self.rows)
        for key, _, q in spec_rows:
            equation = self.specification_nodes[key].equation
            self.rows.append((key, self.specialize(equation.lhs-equation.rhs), self._unit(q)))
        if len(self.rows) != len(self.unknowns) or n_forward != len(forward_ids):
            raise inverse_spec.InverseError('inverse_not_square', 'Releasing the inputs changed the forward row count; the augmented block is not square.')
        self.selection = {**selection, 'unknowns': forward_ids+[r['quantityId'] for r in freed_rows],
            'parameters': {k: v for k, v in selection['parameters'].items() if k not in {r['quantityId'] for r in freed_rows}},
            'nonlinear': {**selection['nonlinear'],
                'variables': {**selection['nonlinear']['variables'],
                              **{r['quantityId']: {k: r[k] for k in ('seedDataId', 'lowerDataId', 'upperDataId', 'scaleDataId')} for r in freed_rows}},
                'residualScales': {**selection['nonlinear']['residualScales'],
                                   **{key: row['residualScaleDataId'] for key, row, _ in spec_rows}}}}
        self.config = self.selection['nonlinear']
        for r, q in zip(freed_rows, freed):
            values = {k: float(self._datum(r[k], self._dim(q))) for k in ('seedDataId', 'lowerDataId', 'upperDataId', 'scaleDataId')}
            self.seed.append(values['seedDataId']); self.bounds.append([values['lowerDataId'], values['upperDataId']])
            self.scales.append(values['scaleDataId'])
        self.residual_scales += [float(self._datum(row['residualScaleDataId'], self._dim(q))) for _, row, q in spec_rows]
        if any(s <= 0 for s in self.scales+self.residual_scales) or any(lo >= hi for lo, hi in self.bounds):
            self.fail('nonlinear_invalid_settings', 'Scales must be positive and bounds strictly ordered.')
        self.symbols = self.symbols+[sp.Dummy('released'+str(i), real=True) for i in range(len(freed))]
        self.symbol_map = dict(zip(self.unknowns, self.symbols))
        expressions = [value.xreplace(self.symbol_map) for _, value, _ in self.rows]
        for expression in expressions: self.arithmetic(expression)
        labels = [key for key, _, _ in self.rows]
        incidence = [[expression.has(s) for s in self.symbols] for expression in expressions]
        inverse_spec.check_structure(incidence, n_forward, labels)
        self.basis = sp.groebner([sp.fraction(sp.cancel(v))[0] for v in expressions], *self.symbols, domain='QQ')
        if list(self.basis) == [1]:
            raise inverse_spec.InverseError('inverse_target_unattainable',
                'The specification contradicts the steady equations for every value of the freed input(s); the target is not clipped.')
        self.jacobian_expression = sp.Matrix(expressions).jacobian(self.symbols)
        self.residual = sp.lambdify([self.symbols], expressions, modules='numpy', cse=True)
        self.jacobian = sp.lambdify([self.symbols], self.jacobian_expression, modules='numpy', cse=True)
        # Guards, consequences and checks are re-derived with the inputs released.
        self.extra_checks = []; self.conditions = []; self.proof_conditions = []
        self.audit_graph()
        self.checks = []
        for row in selection['checks']:
            equation = super()._equation(row['equationId']).equation
            value = self.specialize(equation.lhs-equation.rhs)
            self.require_consequence(value, row['equationId'])
            scale = float(self._datum(row['scaleDataId'], self._dim(equation.lhs-equation.rhs)))
            self.checks.append((row['equationId'], value, scale))
        if not self.admissible(self.seed):
            self.fail('nonlinear_invalid_seed', 'The declared seed violates its bounds or a retained guard.')
        self.problem = inverse_spec.InverseProblem(
            lambda w: np.asarray(self.residual(list(w)), float), lambda w: np.asarray(self.jacobian(list(w)), float),
            n_forward, targets, self.seed, self.bounds, self.scales, self.residual_scales, incidence, labels,
            admissible=lambda w: self.admissible(list(w)),
            settings={'residual_tolerance': self.config['residualTolerance'], 'step_tolerance': self.config['stepTolerance'],
                      'max_iterations': self.config['maxIterations'], 'max_backtracks': self.config['maxBacktracks']})
        self.seed_regularity = self.problem.check()
        self.specification = specification
        self.report = self.compilation_report()
        # A specification is Solve data: Model (source) and Transform formulation stay valid.
        self.report['formulationSignature'] = self.forward_formulation_signature
        referenced = sorted({v for row in specification['specifications']+specification['freedInputs'] for k, v in row.items() if k.endswith('DataId')})
        self.report['specificationSignature'] = signature([specification, {k: self.model['datos'][k]['declaracion'] for k in referenced}])
        self.report['inverseSpecification'] = {
            'format': inverse_spec.FORMAT, 'version': 1, 'record': specification,
            'rows': [{'id': key, 'quantityId': row['quantityId'], 'targetSI': t, 'unit': self._unit(q),
                      'latex': f'{sp.latex(q)} - {t!r} = 0'} for (key, row, q), t in zip(spec_rows, targets)],
            'freedInputs': [{'quantityId': r['quantityId'], 'unit': self._unit(q)} for r, q in zip(freed_rows, freed)],
            'seedRegularity': self.seed_regularity,
            'invalidates': ['solve', 'results'], 'retains': ['model', 'transform'],
            'scope': 'Square inverse specification on the common steady residual; structural matching plus seed rank check; local root only.'}

    def solve(self):
        try:
            result = super().solve()
        except LoweringError as error:
            code = error.diagnostics[0].get('code') if error.diagnostics else None
            if code not in NEWTON_FAILURES:
                raise
            verdict = self.problem.diagnose(SimpleNamespace(diagnostic=error.diagnostics[0]))
            if verdict is None:
                raise
            failure = _lowering(verdict); locate(self.model, failure, 'solve')
            raise failure from error
        diagnostics = result['procedencia']['steadyDiagnostics']
        diagnostics['inverseSpecification'] = {
            'specificationSignature': self.report['specificationSignature'],
            'freedInputs': [r['quantityId'] for r in self.specification['freedInputs']],
            'specificationRows': [row['id'] for row in self.report['inverseSpecification']['rows']],
            'seedRegularity': self.seed_regularity}
        diagnostics['resultSignature'] = steady_result_signature(result)
        return result
