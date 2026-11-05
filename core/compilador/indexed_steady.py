"""Internal zero-accumulation specialization of the connected dynamic system.

Each stage uses the common version-5 Transform for admission and defaults.
Network residuals are the connected original rates, never separately authored
steady equations. Common-result and HTTP publication are separate consumers.
"""
import numpy as np

from core.modelo.steady_transform import prepare_steady_transform
from core.solvers import Detencion
from core.solvers.nonlinear import solve, NonlinearError
from .indexed_network import IndexedDerivedSystem, _failure
from .steady import SteadySystem


class IndexedSteadySystem:
    def __init__(self, model, *, linear_solver='auto', dynamic=None):
        self.dynamic = dynamic or IndexedDerivedSystem(model, linear_solver=linear_solver)
        from core.mathematics.preparation import enabled
        from .template_lowering import bind_steady_defaults
        if enabled() and hasattr(self.dynamic,'template_systems'):
            plans = {}
            for key,source in self.dynamic.template_systems.items():
                transformed = prepare_steady_transform(source.model)
                plans[key] = (source,SteadySystem(transformed['model']),transformed)
            pairs = [bind_steady_defaults(*plans[row['template']],row) for row in self.dynamic.expansion['stages']]
            self.transforms = [pair[0] for pair in pairs]
            self.stages = [pair[1] for pair in pairs]
        else:
            self.transforms = [prepare_steady_transform(stage.model) for stage in self.dynamic.stages]
            self.stages = [SteadySystem(row['model']) for row in self.transforms]
        self.indices = []
        for j, (dynamic_stage, steady_stage) in enumerate(zip(self.dynamic.stages, self.stages)):
            if steady_stage.selection['unknowns'] != dynamic_stage.state_ids:
                raise _failure('index_network_unsupported_steady_invariants',
                    'Connected invariant projection requires a separate admission proof.',
                    'indexSet.stages.' + str(j+1))
            self.indices.extend(range(self.dynamic.offsets[j], self.dynamic.offsets[j] + dynamic_stage.size))
        self.seed = np.concatenate([stage.seed for stage in self.stages])
        self.bounds = np.concatenate([stage.bounds for stage in self.stages])
        self.scales = np.concatenate([stage.scales for stage in self.stages])
        self.residual_scales = np.concatenate([stage.residual_scales for stage in self.stages])
        self.linear_policy = dict(self.dynamic.linear_policy)

    def state(self, values):
        state = self.dynamic.initial()
        state[self.indices] = values
        return state

    def residual(self, values):
        try:
            return self.dynamic.rhs(0., self.state(values))[self.indices]
        except Detencion as error:
            # Newton probes use the nonlinear protocol, not temporal stops.
            # A failed probe is not a replacement for the primary seed solve.
            raise ValueError(str(error)) from error

    def jacobian(self, values, *, columns=None):
        count = len(self.scales) if columns is None else columns
        if self.linear_policy['selected'] == 'sparse':
            try:
                return self.dynamic.block_jacobian(0., self.state(values))[self.indices, :][:, self.indices[:count]]
            except Detencion as error:
                raise ValueError(str(error)) from error
        # Independent dense reference: perturb the global residual, preserving
        # the established finite-difference step and physical variable scales.
        columns = []
        base = None
        for j, scale in enumerate(self.scales[:count]):
            step = 1e-6 * max(abs(values[j]), scale)
            up, down = np.asarray(values).copy(), np.asarray(values).copy()
            lower, upper = self.bounds[j]
            if values[j]-step >= lower and values[j]+step <= upper:
                up[j] += step
                down[j] -= step
                column = (self.residual(up) - self.residual(down)) / (2*step)
            else:
                # Second-order inward stencil at a declared bound. Never
                # evaluate negative inventories or clip the Newton iterate.
                direction = 1 if upper-values[j] >= values[j]-lower else -1
                room = upper-values[j] if direction == 1 else values[j]-lower
                step = min(step, room/2)
                if step <= 0 or values[j]+direction*step == values[j]:
                    raise ValueError('No representable Jacobian perturbation inside the declared bounds.')
                if base is None:
                    base = self.residual(values)
                up[j] += direction*step
                down[j] += direction*2*step
                column = direction*(-3*base + 4*self.residual(up) - self.residual(down))/(2*step)
            columns.append(column)
        return np.asarray(columns).T

    def admissible(self, values):
        try:
            state = self.state(values)
            margins = self.dynamic.dominio(0., state)
            if any(not np.isfinite(v) or v < 0 or strict and v == 0
                   for v, (_, strict, _, _) in zip(margins, self.dynamic.guards)):
                return False
            return self.dynamic.admite(self.dynamic.firma(0., state)) is None
        except (Detencion, ArithmeticError, ValueError):
            return False

    def solve(self, *, continuation=True, progress=None):
        settings = self.stages[0].config
        keys = ('residualTolerance', 'stepTolerance', 'maxIterations', 'maxBacktracks')
        if any(any(stage.config[key] != settings[key] for key in keys) for stage in self.stages):
            raise _failure('index_network_incompatible_settings',
                'Stage Newton tolerances and iteration limits must agree.', 'indexSet.templates')
        options = dict(residual_tolerance=settings['residualTolerance'],
            step_tolerance=settings['stepTolerance'], max_iterations=settings['maxIterations'],
            max_backtracks=settings['maxBacktracks'], linear_solver=self.linear_policy['selected'])
        try:
            root, evidence = solve(self.residual, self.jacobian, self.seed, self.bounds,
                self.scales, self.residual_scales, admissible=self.admissible, **options)
        except NonlinearError as initial_failure:
            eligible = ('nonlinear_domain', 'nonlinear_line_search', 'nonlinear_iteration_limit',
                        'nonlinear_stagnation', 'nonlinear_nonfinite')
            if not continuation or len(self.stages) < 2 or initial_failure.code not in eligible:
                raise
            # A prefix is a closed residual subsystem only for a forward
            # coupling graph. Never discard upstream feedback or a loop.
            for end in self.dynamic.offsets[1:-1]:
                if any(row < end <= column for row, column in self.dynamic.block_jacobian.edges):
                    raise initial_failure
            current = self.seed.copy()
            steps = []
            size = 0
            if progress is not None:
                progress({'phase':'continuation', 'initialFailure':initial_failure.diagnostic})
            for count, stage in enumerate(self.stages, 1):
                transferred = False
                expansion = getattr(self.dynamic, 'expansion', {}).get('stages', [])
                if count > 1 and expansion:
                    previous, added = expansion[count-2:count]
                    if previous['template'] == added['template'] and len(self.stages[count-2].seed) == len(stage.seed):
                        previous_ids = {v:k for k,v in previous['provenance']['identityMap']['quantities'].items()}
                        added_ids = {v:k for k,v in added['provenance']['identityMap']['quantities'].items()}
                        previous_order = [previous_ids[q] for q in self.stages[count-2].selection['unknowns']]
                        added_order = [added_ids[q] for q in stage.selection['unknowns']]
                        if previous_order == added_order:
                            candidate = current[size-len(stage.seed):size].copy()
                            bounds = self.bounds[size:size+len(stage.seed)]
                            if np.all(candidate >= bounds[:,0]) and np.all(candidate <= bounds[:,1]):
                                current[size:size+len(stage.seed)] = candidate
                                transferred = True
                size += len(stage.seed)
                if progress is not None:
                    progress({'phase':'prefix_start', 'count':count, 'seedFromPreviousStage':transferred})
                def complete(values):
                    trial = current.copy()
                    trial[:size] = values
                    return trial
                try:
                    partial, detail = solve(lambda values:self.residual(complete(values))[:size],
                        lambda values:self.jacobian(complete(values), columns=size)[:size, :],
                        current[:size], self.bounds[:size], self.scales[:size], self.residual_scales[:size],
                        admissible=lambda values:self.admissible(complete(values)), **options)
                except NonlinearError as error:
                    error.diagnostic['continuation'] = {'version':1, 'method':'increasing_stage_count',
                        'failedCount':count, 'completedCounts':[s['count'] for s in steps],
                        'initialFailure':initial_failure.diagnostic}
                    error.add_note('Increasing-stage continuation failed at n='+str(count)+
                                   '; completed counts='+str([s['count'] for s in steps])+'.')
                    raise
                current[:size] = partial
                steps.append({'count':count, 'seedFromPreviousStage':transferred, 'solver':detail})
                if progress is not None:
                    progress({'phase':'prefix_complete', 'count':count, 'solver':detail})
            root = current
            evidence = {**steps[-1]['solver'], 'continuation': {'version':1,
                'method':'increasing_stage_count', 'rule':'after eligible default-seed failure; forward block incidence only; original bounds and residuals retained',
                'initialFailure':initial_failure.diagnostic, 'steps':steps}}
        state = self.state(root)
        rates = self.dynamic.rhs(0., state)
        self.verifications = []
        for j, (dynamic_stage, steady_stage) in enumerate(zip(self.dynamic.stages, self.stages)):
            scales = {key: scale for key, _, scale in steady_stage.checks}
            for k, (selection, _, _, _) in enumerate(dynamic_stage.checks):
                key = selection['equationId']
                residual = abs(float(rates[self.dynamic.offsets[j]+dynamic_stage.size+k])) / float(scales[key])
                if not np.isfinite(residual) or residual > 1e-9:
                    raise _failure('index_network_conservation', 'The connected zero-rate balance check failed.',
                                   'indexSet.stages.'+str(j+1)+'.'+key)
                self.verifications.append({'stage':j+1, 'equationId':key, 'residual':residual, 'tolerance':1e-9})
            local = state[self.dynamic.offsets[j]:self.dynamic.offsets[j+1]]
            for closure in dynamic_stage.closures:
                _, publication = closure.evaluate(0., local, 'publication')
                certificate = publication['certificate']
                valid = (certificate['residual']/certificate['scale'] <= 1e-9 if closure.single
                         else certificate['certified'] and certificate['ratio'] <= 1)
                if not valid or closure.admits(publication['phase_set']) is not None:
                    raise _failure('index_network_certificate', 'The stationary stage closure did not pass its certificate.',
                                   'indexSet.stages.'+str(j+1)+'.'+closure.owner)
        return root, {**evidence, 'networkJacobian': {
            'version':1, 'selected':self.linear_policy['selected'],
            'rule':('stage-local closure blocks with symbolic coupling derivatives' if self.linear_policy['selected']=='sparse'
                    else 'central differences at 1e-6 times max(abs(value), declared scale); second-order inward differences when a declared bound excludes the central stencil'),
            'physicalClipping':False}}
