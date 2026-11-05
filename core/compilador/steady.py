"""Autonomous steady specialization of replayed equations, without time marching."""
import hashlib
import json
import math

import numpy as np
import sympy as sp

from core import unidades as units
from core.mathematics.constants import si_magnitude
from core.mathematics.dimensions import catalog, parse_expression
from core.mathematics.graph import math_latex, solve_unique
from core.mathematics.validity import HoldsOnInterval
from core.modelo import leer_modelo_comun
from core.modelo.derived_execution import read_steady_definition
from core.modelo.equation_workbench import build
from core.resultados import conjunto, serie
from core.solvers import nonlinear
from .derived_graph import DerivedGraph, LoweringError, source_signature


def signature(value):
    """Portable JSON fingerprint: numbers use their exact finite binary64 bytes."""
    import struct
    def canonical(item):
        if type(item) in (int, float):
            if not math.isfinite(item): raise ValueError('Nonfinite signature value.')
            return {'$binary64': struct.pack('>d', float(item)).hex()}
        if isinstance(item, dict): return {key: canonical(value) for key, value in item.items()}
        if isinstance(item, list): return [canonical(value) for value in item]
        return item
    return hashlib.sha256(json.dumps(canonical(value), sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_selected_data(model):
    selection = model.get('motores', {}).get('derivedExecution', {})
    try:
        read_steady_definition(selection)
    except (ValueError, TypeError, KeyError) as error:
        failure = LoweringError('steady_invalid_selection', str(error))
        locate(model, failure)
        raise failure from error
    data = list(selection['parameters'].values())+list(selection['invariants'].values())
    data += [r['scaleDataId'] for r in selection['checks']]
    data += list(selection['nonlinear']['residualScales'].values())
    data += [v for row in selection['nonlinear']['variables'].values() for v in row.values()]
    for key in data:
        if key not in model.get('datos', {}):
            failure = LoweringError('steady_missing_data', 'Missing selected datum: '+key)
            locate(model, failure)
            failure.diagnostics[0]['path'] = 'datos.'+key
            raise failure


def locate(model, error, stage='admission'):
    selection = model.get('motores', {}).get('derivedExecution', {})
    if not isinstance(selection, dict): selection = {}
    data = {key: value.get('declaracion') for key, value in model.get('datos', {}).items()}
    def fingerprint(value):
        try: return signature(value)
        except (TypeError, ValueError, OverflowError):
            # Invalid JSON numbers still receive located rejection evidence.
            return signature({'invalidInput': repr(value)})
    defaults = {'stage': stage, 'path': 'motores.derivedExecution', 'modelId': model.get('id'),
                'sourceSignature': selection.get('sourceSignature'), 'formulationSignature': fingerprint(selection),
                'dataSignature': fingerprint(data), 'settingsSignature': fingerprint(selection.get('nonlinear')),
                'equationIds': [r.get('equationId') for field in ('states', 'algebraic')
                                for r in (selection.get(field) if isinstance(selection.get(field), list) else []) if isinstance(r, dict)],
                'quantityIds': selection.get('unknowns', []), 'iterations': None, 'evaluations': None,
                'backtracks': None, 'residualNorm': None, 'stepNorm': None, 'conditionInfinity': None,
                'smallestSingularValue': None}
    for row in error.diagnostics:
        for key, value in defaults.items(): row.setdefault(key, value)
        row.setdefault('terminationReason', row['code'])


class SteadySystem(DerivedGraph):
    def __init__(self, model):
        try:
            if 'indexSet' in model:
                error = LoweringError('index_set_not_lowered',
                    'Indexed stage networks require network lowering; the generic stage cannot execute in their place.')
                error.diagnostics[0]['path'] = 'indexSet'
                raise error
            self._initialize(model)
        except LoweringError as error:
            locate(model, error)
            raise
        except (ValueError, TypeError, KeyError, ArithmeticError, NotImplementedError) as error:
            failure = LoweringError('steady_invalid_selection', str(error))
            locate(model, failure)
            raise failure from error

    def fail(self, code, message, key=None):
        raise LoweringError(code, message, key)

    def _datum(self, key, expected):
        if key not in self.model['datos']:
            self.fail('steady_missing_data', 'Missing numerical datum: '+key)
        declaration = self.model['datos'][key]['declaracion']
        try:
            conversion = units.exact_conversion(declaration['unidad'])
            if conversion['dimension'] != expected or conversion['afin']:
                raise ValueError('Use compatible absolute units.')
        except (ValueError, units.ErrorUnidad) as error:
            self.fail('steady_invalid_units', key+': '+str(error))
        try:
            value = parse_expression(declaration['texto'], {})
        except ValueError as error:
            self.fail('steady_time_dependent', key+': only constant data are admitted; '+str(error))
        value = value*sp.Rational(conversion['factor'])+sp.Rational(conversion['desplazamiento'])
        if value.is_number is not True or value.is_real is not True or value.is_finite is not True:
            self.fail('steady_missing_data', key+': a finite real constant is required.')
        return value

    def _initialize(self, model):
        validate_selected_data(model)
        self.model = leer_modelo_comun(model)
        self.selection = read_steady_definition(model['motores']['derivedExecution'], model)
        if model['estudio'] != {'tipo': 'steady', 'version': 1, 'metodoSolicitado': 'damped_newton'}:
            self.fail('steady_invalid_selection', 'Explicit version-1 steady study and damped_newton are required.')
        if model.get('matematico') is not None or model['motores'].get('adimensionalizacion') is not None:
            self.fail('steady_invalid_selection', 'Steady execution requires the identity derived formulation alone.')
        if model['motores'].get('hydraulicNetwork') is not None:
            self.fail('steady_unsupported_structure', 'This slice does not lower a separate hydraulic-network configuration.')
        # Package-closure volumes enter through SteadyClosures (demo-02-steady); spatial systems stay outside.
        equilibrium = [v for v in model['volumenes'] if v['termodinamica']['tipo'] != 'supuesto']
        for volume in model['volumenes']:
            if volume['frontera']['tipo'] == 'malla_1d':
                self.fail('steady_unsupported_structure', 'Spatial systems are outside this slice.')
            for balance, journal in [('materia', 'materialDerivation'), ('energia', 'energyDerivation')]:
                if volume['balances'][balance] and volume['id'] not in model['motores'].get(journal, {}).get('volumes', {}):
                    self.fail('steady_invalid_selection', 'Every active physical balance requires its recorded journal.')
        from core.modelo.dynamic_definition import ensure_executable
        ensure_executable(model)
        self.replayed = build(model)
        if any(r.signature_status == 'legacy/unsigned' for r in self.replayed.receipts):
            self.fail('steady_invalid_selection', 'Unsigned history cannot be executed.')
        if source_signature(model, self.replayed) != self.selection['sourceSignature']:
            self.fail('steady_invalid_selection', 'The pinned source is stale; no earlier graph is substituted.')
        self.graph = self.replayed.graph
        self.quantities = {**catalog(self.graph, self.replayed.units), **self.replayed.introduced}
        self.time = self._quantity(self.selection['timeId'])
        if not isinstance(self.time, sp.Symbol) or self._dim(self.time) != {'T': 1}:
            self.fail('steady_invalid_selection', 'Select the time coordinate whose first derivatives are specialized.')
        self.unknowns = [self._quantity(key) for key in self.selection['unknowns']]
        self.states = [self._quantity(row['quantityId']) for row in self.selection['states']]
        if any(not isinstance(q, (sp.Symbol, sp.core.function.AppliedUndef)) or
               isinstance(q, sp.core.function.AppliedUndef) and q.args != (self.time,) for q in self.unknowns+self.states):
            self.fail('steady_unsupported_structure', 'Unknowns must be scalar or depend only on the selected time.')
        self.replacements = {}
        self.parameter_records = []
        for qid, data in self.selection['parameters'].items():
            q = self._quantity(qid)
            if not isinstance(q, (sp.Symbol, sp.core.function.AppliedUndef)) or isinstance(q, sp.core.function.AppliedUndef) and q.args != (self.time,):
                self.fail('steady_unsupported_structure', 'A parameter must be a scalar or a prescribed time-only quantity.')
            value = self._datum(data, self._dim(q))
            self.replacements[q] = value
            self.parameter_records.append({'id': qid, 'dataId': data, 'value': float(value), 'unit': self._unit(q)})
        self.closures = None
        self.parameter_symbols = {self._quantity(qid): None for qid in self.selection['parameters']}
        if equilibrium:
            from .derived_closure import SteadyClosures
            self.parameter_symbols = {self._quantity(qid): None for qid in self.selection['parameters']}
            self.closures = SteadyClosures(self, equilibrium)
            kinetic = (model['motores'].get('kineticReactions') or {}).get('volumes', {})
            if any(c.owner in kinetic and c.anchor is None for c in self.closures.closures):
                self.fail('formation_reference_required', 'Reacting package volumes require the recorded formation reference used by dynamic execution.')
            for q, value in self.closures.constants().items():
                if q in self.replacements and not math.isclose(float(self.replacements[q]), value, rel_tol=1e-9):
                    self.fail('inconsistent_molar_mass', 'A datum contradicts a value supplied by the selected package: '+str(q))
                self.replacements[q] = sp.Float(value, 17)
        if any(v['balances']['momento'] for v in self.model['volumenes']):
            # The same reduced-journal admission as dynamic execution (path flow row, hydrostatic storage).
            from .derived import DerivedSystem
            DerivedSystem._reduced_momentum_admission(self)
        self.guards = []
        for row in self.selection['reconstructions']:
            q = self._quantity(row['quantityId']); node = self._equation(row['equationId'])
            value, guards = solve_unique(node.equation, q, self.graph.names)
            if value.has(sp.Derivative):
                self.fail('steady_unsupported_structure', 'Reconstructions must be explicit and acyclic.', row['equationId'])
            self.replacements[q] = value
            self.guards += [(guard, row['equationId']) for guard in guards]
        protected = set(self.states+self.unknowns+(self.closures.outputs if self.closures else []))
        for row in self.selection['reconstructions']:
            if self.closures and self._quantity(row['quantityId']) in self.closures.outputs:
                self.fail('competing_closure', 'A package closure output cannot also be an authored reconstruction.', row['equationId'])
        for key, node in self.graph.nodes.items():
            if key.startswith('operation.') and isinstance(node.equation, sp.Equality) and node.rule == 'constitutive_relation':
                target = node.equation.lhs
                if isinstance(target, (sp.Symbol, sp.core.function.AppliedUndef)) and target not in protected and target not in self.replacements:
                    self.replacements[target] = node.equation.rhs
        # Declared boundary constraints use the same orientation, with no hidden RHS.
        for index, operation in enumerate(self.replayed.definition['operations'][:self.replayed.definition['cursor']], 1):
            if operation['kind'] == 'declare_relation':
                equation = self.graph.nodes['operation.'+str(index)].equation
                target = equation.lhs
                if isinstance(target, (sp.Symbol, sp.core.function.AppliedUndef)) and target not in protected and target not in self.replacements:
                    self.replacements[target] = equation.rhs
        from .derived import DerivedSystem
        self.algebraic_quantities = [self._quantity(row['quantityId']) for row in self.selection['algebraic']]
        DerivedSystem._kinetic_declarations(self)
        self.zero_rates = {sp.diff(q, self.time): sp.S.Zero for q in self.states if isinstance(q, sp.core.function.AppliedUndef)}
        self.invariant_records = []
        for row in self.selection['states']:
            key, qid = row['equationId'], row['quantityId']
            q = self._quantity(qid); equation = self._equation(key).equation
            residual = self._expand(equation.lhs-equation.rhs).doit()
            derivative = sp.Derivative(q, self.time)
            if residual.atoms(sp.Derivative) != {derivative}:
                self.fail('steady_unsupported_structure', 'Each state row must isolate one first time derivative; IDA is a future option for general implicit systems.', key)
            coefficient = sp.diff(residual, derivative)
            if not coefficient.is_number or coefficient.is_zero is not False or coefficient.is_finite is not True or sp.diff(residual, derivative, 2) != 0:
                self.fail('steady_unsupported_structure', 'The derivative coefficient must be a nonzero constant scalar.', key)
            remainder = sp.cancel(residual.xreplace({derivative: 0}))
            if qid in self.selection['invariants']:
                if remainder != 0:
                    self.fail('steady_constraint_conflict', 'Only an individually invariant state can be bound.', key)
                data = self.selection['invariants'][qid]; value = self._datum(data, self._dim(q))
                self.replacements[q] = value
                self.invariant_records.append({'quantityId': qid, 'equationId': key, 'dataId': data, 'value': float(value), 'unit': self._unit(q)})
            elif remainder == 0:
                self.fail('steady_unbound_invariant', 'Bind this individual invariant explicitly; temporal initial values and seeds are not constraints.', key)
        self.rows = []; self.identities = []
        for row in [*self.selection['states'], *self.selection['algebraic']]:
            key = row['equationId']; equation = self._equation(key).equation
            self._dim(equation.lhs-equation.rhs)
            if row in self.selection['algebraic'] and equation.has(sp.Derivative):
                self.fail('steady_unsupported_structure', 'Algebraic rows cannot contain derivatives; IDA is a future option.', key)
            expression = self.specialize(equation.lhs-equation.rhs)
            if expression == 0:
                self.identities.append(key)
                continue
            if expression.is_number:
                self.fail('steady_constraint_conflict', 'A specialized physical law is a nonzero constant.', key)
            self.rows.append((key, expression, self._unit(equation.lhs-equation.rhs)))
        if not self.rows or len(self.rows) != len(self.unknowns):
            self.fail('steady_structure_mismatch', 'The independent residual block must be nonempty and square.')
        if len({sp.srepr(sp.cancel(row[1])) for row in self.rows}) != len(self.rows):
            self.fail('steady_structure_mismatch', 'Duplicate nonidentity rows cannot be silently removed.')
        self.config = self.selection['nonlinear']
        self.seed = []; self.bounds = []; self.scales = []
        for qid, q in zip(self.selection['unknowns'], self.unknowns):
            spec = self.config['variables'][qid]
            values = {k: float(self._datum(data, self._dim(q))) for k, data in spec.items()}
            self.seed.append(values['seedDataId']); self.bounds.append([values['lowerDataId'], values['upperDataId']]); self.scales.append(values['scaleDataId'])
        self.residual_scales = [float(self._datum(self.config['residualScales'][key], units.interpretar(unit)['dimension'])) for key, _, unit in self.rows]
        if any(s <= 0 for s in self.scales+self.residual_scales) or any(lo >= hi for lo, hi in self.bounds):
            self.fail('nonlinear_invalid_settings', 'Scales must be positive and bounds strictly ordered.')
        self.symbols = [sp.Dummy('steady'+str(i), real=True) for i in range(len(self.unknowns))]
        self.symbol_map = dict(zip(self.unknowns, self.symbols))
        if self.closures:
            # Closure outputs are package-eliminated algebraic unknowns: no symbolic basis exists over them.
            self.symbol_map.update(self.closures.symbol_map)
            self.closures.bind(self.unknowns, self.symbols, lambda q: self._expand(q).doit())
        expressions = [value.xreplace(self.symbol_map) for _, value, _ in self.rows]
        for expression in expressions: self.arithmetic(expression)
        if self.closures:
            self.basis = None
            edges = [sorted(self.closures.depends(expression, self.symbols)) for expression in expressions]
        else:
            polynomials = [sp.fraction(sp.cancel(value))[0] for value in expressions]
            self.basis = sp.groebner(polynomials, *self.symbols, domain='QQ')
            if list(self.basis) == [1]:
                self.fail('steady_constraint_conflict', 'The retained specialized rows are algebraically inconsistent.')
            edges = [[i for i, q in enumerate(self.symbols) if expression.has(q)] for expression in expressions]
        matched = {}
        def match(row, seen):
            for column in edges[row]:
                if column in seen: continue
                seen.add(column)
                if column not in matched or match(matched[column], seen):
                    matched[column] = row
                    return True
            return False
        if not all(match(i, set()) for i in range(len(edges))):
            self.fail('steady_structure_mismatch', 'No complete equation/unknown structural matching exists.')
        if self.closures:
            self.residual, self.jacobian = self._closure_residual(expressions)
        else:
            self.jacobian_expression = sp.Matrix(expressions).jacobian(self.symbols)
            self.residual = sp.lambdify([self.symbols], expressions, modules='numpy', cse=True)
            self.jacobian = sp.lambdify([self.symbols], self.jacobian_expression, modules='numpy', cse=True)
        from core.solvers.sparse_blocks import ExpressionJacobian
        blocks = []
        if self.closures:
            offset = 0
            for closure, dependencies in zip(self.closures.closures, self.closures.dependencies):
                outputs = self.closures.symbols[offset:offset+len(closure.outputs)]
                columns = {i for i, symbol in enumerate(self.symbols) if symbol in dependencies}
                blocks.append((outputs, columns, lambda t, y, closure=closure: self.closures.evaluate_block(closure, t, y)))
                offset += len(outputs)
        self.block_jacobian = ExpressionJacobian(expressions, self.symbols, self.time, self.scales, blocks)
        self.linear_policy = dict(self.block_jacobian.policy)
        self.dense_jacobian = self.jacobian
        self.extra_checks = []; self.conditions = []; self.proof_conditions = []
        self.audit_graph()
        self.checks = []
        for row in self.selection['checks']:
            equation = self._equation(row['equationId']).equation
            value = self.specialize(equation.lhs-equation.rhs)
            self.require_consequence(value, row['equationId'])
            scale = float(self._datum(row['scaleDataId'], self._dim(equation.lhs-equation.rhs)))
            if scale <= 0: self.fail('nonlinear_invalid_settings', 'Balance-check scales must be positive.')
            self.checks.append((row['equationId'], value, scale))
        if not self.admissible(self.seed):
            self.fail('nonlinear_invalid_seed', 'The declared seed violates its bounds or a retained guard.')
        self.report = self.compilation_report()

    def _closure_residual(self, expressions):
        """Package residual with centered or second-order inward differences."""
        closures = self.closures
        function = sp.lambdify([self.symbols, closures.symbols], expressions, modules='numpy', cse=True)
        def residual(values):
            return np.asarray(function(np.asarray(values, dtype=float), closures.vector(values)), dtype=float)
        def jacobian(values):
            values = np.asarray(values, dtype=float); columns = []
            base = None
            for j, scale in enumerate(self.scales):
                step = 1e-6*max(abs(values[j]), scale)
                up, down = values.copy(), values.copy()
                lower, upper = self.bounds[j]
                if values[j]-step >= lower and values[j]+step <= upper:
                    up[j] += step; down[j] -= step
                    column = (residual(up)-residual(down))/(2*step)
                else:
                    direction = 1 if upper-values[j] >= values[j]-lower else -1
                    room = upper-values[j] if direction == 1 else values[j]-lower
                    step = min(step,room/2)
                    if step<=0 or values[j]+direction*step==values[j]:
                        raise ValueError('No representable Jacobian perturbation inside the declared bounds.')
                    if base is None:base=residual(values)
                    up[j] += direction*step;down[j] += direction*2*step
                    column = direction*(-3*base+4*residual(up)-residual(down))/(2*step)
                columns.append(column)
            return np.column_stack(columns)
        return residual, jacobian

    def _numeric(self, expression):
        """A function of the steady unknowns that also reads the package closure outputs."""
        if not self.closures or not expression.has(*self.closures.symbols):
            return sp.lambdify([self.symbols], expression, modules='numpy')
        function = sp.lambdify([self.symbols, self.closures.symbols], expression, modules='numpy')
        return lambda values: function(np.asarray(values, dtype=float), self.closures.vector(values))

    def specialize(self, expression):
        expanded = self._expand(expression).doit()
        value = expanded.xreplace(self.zero_rates).doit()
        if self.closures:
            # Closure outputs are functions of the stationary unknowns: their rates vanish too.
            outputs = set(self.closures.outputs)
            value = value.replace(lambda e: isinstance(e, sp.Derivative) and e.expr in outputs, lambda e: sp.S.Zero).doit()
        if value.has(sp.Derivative, sp.Integral, sp.Sum):
            self.fail('steady_unsupported_structure', 'An unsupported derivative, integral or sum remains after specialization.')
        # Replace time-only unknown functions before inspecting free time.
        reduced = value.xreplace({q: sp.Dummy() for q in self.unknowns+(self.closures.outputs if self.closures else [])})
        if self.time in reduced.free_symbols:
            self.fail('steady_time_dependent', 'Residuals and guards must be autonomous after constant binding.')
        return si_magnitude(value)

    def arithmetic(self, expression):
        if expression in self.symbols or self.closures and expression in self.closures.symbols or expression.is_Number and expression.is_finite:
            return
        if expression.is_Add or expression.is_Mul:
            for arg in expression.args: self.arithmetic(arg)
            return
        if expression.is_Pow and expression.exp.is_Integer:
            self.arithmetic(expression.base)
            return
        if self.closures:
            # No symbolic basis is built over package outputs, so the rational-only restriction of
            # the proof does not apply; recorded even-root guards stay runtime conditions.
            if expression.is_number and expression.is_finite:
                return
            if expression.is_Pow and expression.exp.is_Rational:
                self.arithmetic(expression.base)
                return
            if isinstance(expression, sp.Abs):
                self.arithmetic(expression.args[0])
                return
            if expression.func == sp.exp and self.model['motores'].get('kineticReactions'):
                # The same recorded Arrhenius roots as dynamic execution. The
                # package path checks consequences numerically, not by a
                # rational-polynomial proof. Temperature guards remain active.
                self.arithmetic(expression.args[0])
                return
        self.fail('steady_unsupported_structure', 'Only finite rational arithmetic with integer powers and guarded division is admitted: '+str(expression))

    def require_consequence(self, value, key):
        expression = value.xreplace(self.symbol_map)
        self.arithmetic(expression)
        if self.basis is None:
            # With package closures a consequence is verified at the root, not proved symbolically.
            self.extra_checks.append((key, value))
            return
        try:
            numerator = sp.fraction(sp.cancel(expression))[0]
            if self.basis.reduce(numerator)[1] != 0:
                self.fail('steady_constraint_conflict', 'An active constraint is not a consequence of the selected steady equations.', key)
        except (sp.PolynomialError, sp.polys.polyerrors.CoercionFailed) as error:
            self.fail('steady_unsupported_structure', str(error), key)
        self.extra_checks.append((key, value))

    def audit_graph(self):
        active = {v['id']: v['balances'] for v in self.model['volumenes']}
        selected = {row['equationId'] for field in ('states', 'algebraic', 'reconstructions', 'checks') for row in self.selection[field]}
        selected.update(key for key in self.graph.nodes if key.startswith('operation.'))
        for key in self.replayed.selected:
            node = self.graph.nodes[key]; owner = self.replayed.owners.get(key)
            family = {'matter': 'materia', 'energy': 'energia'}.get(node.family)
            if family and owner in active and active[owner][family] and node.kind in ('balance', 'constraint') and not node.dependent:
                selected.add(key)
        predicates = list(self.guards)
        for key in sorted(selected):
            node = self.graph.nodes[key]
            if isinstance(node.equation, sp.Equality) and key not in self.identities:
                self.require_consequence(self.specialize(node.equation.lhs-node.equation.rhs), key)
            predicates.extend((p, key) for p in self.graph.predicates_for(key))
            # Preserve uncancelled denominator guards from both sides and expansions.
            expressions = (node.equation.lhs, node.equation.rhs, self._expand(node.equation.lhs), self._expand(node.equation.rhs)) if isinstance(node.equation, sp.Equality) else (node.equation,)
            for expression in expressions:
                predicates.extend((sp.Ne(power.base, 0, evaluate=False), key) for power in expression.atoms(sp.Pow) if power.exp.is_negative)
        predicates.extend((premise.expression, key) for key, premise in self.graph.domains.items())
        physical = {p for key, node in self.graph.nodes.items() if not key.startswith('operation.') for p in node.predicates}
        bound = {p.args[1] for p in physical if isinstance(p, HoldsOnInterval) and p.args[1] != self.time}
        seen = set()
        for predicate, key in predicates:
            if predicate in seen or predicate is sp.S.true: continue
            seen.add(predicate)
            if isinstance(predicate, HoldsOnInterval):
                self.proof_conditions.append({'equationId': key, 'kind': 'interval_identity', 'latex': math_latex(predicate, self.graph.names)})
                continue
            value = si_magnitude(self._expand(predicate).doit())
            if value.free_symbols & bound or any(f.args != (self.time,) for f in value.atoms(sp.core.function.AppliedUndef)):
                if predicate not in physical:
                    self.fail('steady_unsupported_structure', 'A new spatial premise has no numerical lowering.', key)
                self.proof_conditions.append({'equationId': key, 'kind': 'eliminated_coordinate_premise', 'latex': math_latex(predicate, self.graph.names)})
                continue
            if isinstance(value, sp.Equality):
                self.require_consequence(self.specialize(value.lhs-value.rhs), key)
            elif value is sp.S.false:
                self.fail('steady_constraint_conflict', 'A bound validity condition is false.', key)
            elif value is not sp.S.true:
                self.add_condition(value, key)
        for volume in self.model['volumenes']:
            closure = volume['termodinamica']
            if closure.get('supuesto') != 'u_lineal' or not volume['balances']['energia']: continue
            owner = volume['id']; parameters = closure['parametros']
            for name, field in [('caloric_capacity', 'cId'), ('T_reference', 'TRefId'), ('u_reference', 'uRefId')]:
                quantity = next((q for q in self.quantities.values() if str(q) == name+'__'+owner), None)
                if quantity is None or self._expand(quantity) != self._datum(parameters[field], self._dim(quantity)):
                    self.fail('steady_constraint_conflict', 'The selected caloric data must match the declared physical closure.')
            temperature = next((q for q in self.quantities.values() if str(q) == 'T__'+owner+'(t)'), None)
            if temperature is None:
                self.fail('steady_unsupported_structure', 'The caloric temperature must be retained or reconstructed.')
            lo = self._datum(parameters['TMinId'], {'Theta': 1}); hi = self._datum(parameters['TMaxId'], {'Theta': 1})
            if lo >= hi: self.fail('steady_domain', 'The caloric interval must be ordered.')
            self.add_condition(sp.Contains(temperature, sp.Interval(lo, hi)), 'thermodynamics.'+owner+'.caloric-inventory')

    def add_condition(self, value, key):
        if isinstance(value, sp.Contains):
            quantity, domain = value.args
            if domain == sp.S.Reals: return
            if isinstance(domain, sp.Interval):
                if domain.start != -sp.oo: self.add_condition(sp.Gt(quantity, domain.start) if domain.left_open else sp.Ge(quantity, domain.start), key)
                if domain.end != sp.oo: self.add_condition(sp.Lt(quantity, domain.end) if domain.right_open else sp.Le(quantity, domain.end), key)
                return
            if domain == sp.FiniteSet(0):
                self.require_consequence(self.specialize(quantity), key)
                return
        if isinstance(value, (sp.GreaterThan, sp.StrictGreaterThan, sp.LessThan, sp.StrictLessThan, sp.Unequality)):
            expression = self.specialize(value.lhs-value.rhs).xreplace(self.symbol_map)
            self.arithmetic(expression)
            function = self._numeric(expression)
            kind = 'nonzero' if isinstance(value, sp.Unequality) else 'positive' if isinstance(value, (sp.StrictGreaterThan, sp.StrictLessThan)) else 'nonnegative'
            sign = -1 if isinstance(value, (sp.LessThan, sp.StrictLessThan)) else 1
            self.conditions.append((function, kind, sign, key, math_latex(value, self.graph.names)))
            return
        self.fail('steady_unsupported_structure', 'Unsupported steady validity predicate: '+str(value), key)

    def admissible(self, values):
        if len(values) != len(self.bounds) or any(not math.isfinite(float(x)) or x < lo or x > hi for x, (lo, hi) in zip(values, self.bounds)):
            return False
        try:
            for function, kind, sign, _, _ in self.conditions:
                value = sign*float(function(values))
                if not math.isfinite(value) or (value == 0 if kind == 'nonzero' else value <= 0 if kind == 'positive' else value < 0):
                    return False
        except (ArithmeticError, ValueError, TypeError):
            return False
        return True

    def compilation_report(self):
        selected = self.selection
        rows = []
        for row in [*selected['states'], *selected['algebraic']]:
            equation = self._equation(row['equationId']).equation
            rows.append({'id': row['equationId'], 'family': self._equation(row['equationId']).family,
                         'before': math_latex(equation, self.graph.names),
                         'after': math_latex(sp.Eq(self.specialize(equation.lhs-equation.rhs), 0, evaluate=False), self.graph.names),
                         'identity': row['equationId'] in self.identities})
        return {'format': 'rage.compilation', 'version': 2, 'study': 'steady', 'sourceModelId': self.model['id'],
                'signature': signature([selected, self.model['datos'], self.model['estudio']]),
                'sourceSignature': selected['sourceSignature'], 'formulationSignature': signature(selected),
                'dataSignature': signature({k: v['declaracion'] for k, v in self.model['datos'].items()}),
                'settingsSignature': signature(self.config), 'method': 'damped_newton', 'selection': selected,
                'variables': [{'id': qid, 'name': str(q), 'unit': self._unit(q), 'scaleSI': scale,
                               'seedSI': seed, 'boundsSI': bounds} for qid, q, scale, seed, bounds in zip(selected['unknowns'], self.unknowns, self.scales, self.seed, self.bounds)],
                'rows': rows, 'residualRows': [{'id': key, 'unit': unit, 'scaleSI': scale} for (key, _, unit), scale in zip(self.rows, self.residual_scales)],
                'invariants': self.invariant_records, 'parameters': self.parameter_records,
                'proofConditions': self.proof_conditions, 'runtimeConditions': [{'equationId': key, 'kind': kind, 'latex': label} for _, kind, _, key, label in self.conditions],
                'scope': 'Autonomous rational steady specialization; structural matching is not a rank or uniqueness proof; finite root probes do not prove global uniqueness. Linear algebra policy: '+json.dumps(self.linear_policy, sort_keys=True),
                **({'thermodynamicClosures': self.closures.report(self._unit, {value: key for key, value in self.quantities.items()})} if self.closures else {}),
                **({'kineticDiagnostics':{'version':1,'volumeIds':[c.owner for c in self.closures.closures
                    if c.owner in self.model['motores']['kineticReactions']['volumes']]}}
                   if self.closures and self.model['motores'].get('kineticReactions',{}).get('volumes') else {})}

    def final_check(self, root):
        if not self.admissible(root):
            self.fail('steady_domain', 'Final candidate violates an original domain guard.')
        substitutions = dict(zip(self.unknowns, map(sp.Float, root)))
        if self.closures:
            substitutions.update(zip(self.closures.outputs, map(sp.Float, self.closures.vector(root))))
        residuals = []
        for (key, _, _), scale in zip(self.rows, self.residual_scales):
            equation = self._equation(key).equation
            value = float(self.specialize(equation.lhs-equation.rhs).subs(substitutions))
            if not math.isfinite(value) or abs(value)/scale > self.config['residualTolerance']:
                self.fail('steady_original_residual', 'Original specialized row failed independent final evaluation.', key)
            residuals.append(value)
        for key, expression in self.extra_checks:
            value = float(expression.subs(substitutions))
            # Consequences are independently checked with a dimension-compatible
            # original-row scale where available; no residual is dropped.
            scale = next((s for (rid, _, _), s in zip(self.rows, self.residual_scales) if rid == key), None)
            if scale is None and self.closures and key in self.graph.nodes and isinstance(self.graph.nodes[key].equation, sp.Equality):
                # Without a symbolic proof, an intermediate stage of a selected law is checked with
                # the residual scale of a selected row of the same unit.
                equation = self.graph.nodes[key].equation
                unit = self._unit(equation.lhs-equation.rhs)
                scale = next((s for (_, _, u), s in zip(self.rows, self.residual_scales) if u == unit), None)
            scale = 1. if scale is None else scale
            if not math.isfinite(value) or abs(value)/scale > self.config['residualTolerance']:
                self.fail('steady_original_residual', 'A retained active constraint failed final evaluation.', key)
        checks = []
        for key, expression, scale in self.checks:
            residual = abs(float(expression.subs(substitutions)))/scale
            if not math.isfinite(residual) or residual > 1e-6:
                self.fail('steady_original_residual', 'Independent summed balance check failed.', key)
            checks.append({'id': 'conservation.'+key, 'valor': residual, 'tolerancia': 1e-6, 'descripcion': 'Original specialized balance residual'})
        return residuals, checks, substitutions

    def solve(self, *, linear_solver=None):
        try:
            selected_solver = linear_solver or self.linear_policy['selected']
            if selected_solver not in ('dense', 'sparse'): raise ValueError('Unknown linear solver.')
            import copy
            run_report = copy.deepcopy(self.report)
            if linear_solver:
                run_report['scope'] += ' Explicit verification override: '+linear_solver+'.'
            jacobian = (self.jacobian if linear_solver is None else self.dense_jacobian) if selected_solver == 'dense' else lambda values: self.block_jacobian(0., values)
            self.block_jacobian.policy['selected'] = selected_solver
            root, detail = nonlinear.solve(self.residual, jacobian, self.seed, self.bounds, self.scales,
                self.residual_scales, residual_tolerance=self.config['residualTolerance'], step_tolerance=self.config['stepTolerance'],
                max_iterations=self.config['maxIterations'], max_backtracks=self.config['maxBacktracks'], admissible=self.admissible, linear_solver=selected_solver)
            residuals, checks, substitutions = self.final_check(root)
            from core.solvers.sparse_blocks import factor_step
            _, _, smallest = factor_step(jacobian(root), np.zeros(len(root)), np.asarray(self.scales), np.asarray(self.residual_scales), selected_solver)
            evidence = {'version': 1, 'verdict': 'local_regular_root', 'globalUniqueness': 'not_proved',
                'method': 'damped_newton', 'sourceSignature': self.report['sourceSignature'],
                'formulationSignature': self.report['formulationSignature'], 'dataSignature': self.report['dataSignature'],
                'settingsSignature': self.report['settingsSignature'], 'compilationSignature': self.report['signature'],
                'quantityIds': self.selection['unknowns'], 'equationIds': [r[0] for r in self.rows],
                'variableScales': self.scales, 'residualScales': self.residual_scales,
                'smallestSingularValue': smallest, 'conditionThreshold': 1e-8, 'inverseThreshold': 1e-8,
                'relativeAmplification': float(detail['conditionInfinity']*np.finfo(float).eps),
                'inverseAmplification': float(np.finfo(float).eps/smallest), 'solver': detail,
                'initialResidualNorm': float(np.max(np.abs(self.residual(self.seed))/self.residual_scales)),
                'scope': 'Iteration/backtrack counters describe the primary solve; evaluations include attempted probes. completedProbes counts converged probes only; failed probes prove nothing. No dynamic stability or physical certificate.'}
            output = [serie('steady.'+qid, str(q), self._unit(q), [], float(value)) for qid, q, value in zip(self.selection['unknowns'], self.unknowns, root)]
            for row in self.invariant_records:
                output.append(serie('steady.'+row['quantityId'], str(self._quantity(row['quantityId'])), row['unit'], [], row['value']))
                checks.append({'id': 'invariant.'+row['quantityId'], 'valor': 0., 'tolerancia': 1e-6, 'descripcion': 'Verified individual zero-rate binding'})
            for row in self.selection['reconstructions']:
                q = self._quantity(row['quantityId']); value = float(self.specialize(q).subs(substitutions))
                if not math.isfinite(value): self.fail('steady_original_residual', 'A reconstructed quantity is nonfinite.')
                output.append(serie('steady.'+row['quantityId'], str(q), self._unit(q), [], value))
            output += [serie('steady.residual.'+key, 'Original residual: '+key, unit, [], value) for (key, _, unit), value in zip(self.rows, residuals)]
            closure_details = []
            if self.closures:
                ids = {value: key for key, value in self.quantities.items()}
                rows, closure_checks, closure_details = self.closures.publication(root, self._unit, ids)
                output += [serie('closure.'+qid, name, unit, [], value) for qid, name, unit, value in rows]
                checks += closure_checks
                evidence['thermodynamicClosures'] = closure_details
                from .derived_closure import reaction_limit
                kinetic = (self.model['motores'].get('kineticReactions') or {}).get('volumes', {})
                self.reaction_limits = []
                for closure in self.closures.closures:
                    if closure.owner in kinetic:
                        diagnostic, detail = reaction_limit(self, closure, [0.], [root])
                        checks.append(diagnostic)
                        self.reaction_limits.append(detail)
            checks.append({'id': 'steady.scaled_residual', 'valor': max(abs(v)/s for v, s in zip(residuals, self.residual_scales)),
                           'tolerancia': self.config['residualTolerance'], 'descripcion': 'Maximum original scaled residual'})
            result = conjunto(self.model['id'], self.model['nombre'], 'resuelto',
                {'motor': 'rage.compilador.steady', 'metodo': 'damped_newton', 'firma': None,
                 'compilation': run_report, 'steadyDiagnostics': evidence}, [], output, verificaciones=checks, modeloId=self.model['id'])
            result['procedencia']['steadyDiagnostics']['resultSignature'] = steady_result_signature(result)
            return result
        except nonlinear.NonlinearError as error:
            failure = LoweringError(error.code, str(error)); failure.diagnostics = [error.diagnostic]
            locate(self.model, failure, 'solve')
            raise failure from error
        except LoweringError as error:
            locate(self.model, error, 'validation')
            raise
        except (ArithmeticError, ValueError, TypeError) as error:
            failure = LoweringError('steady_original_residual', 'Final steady evaluation is not finite/representable: '+str(error))
            locate(self.model, failure, 'validation')
            raise failure from error


def steady_result_signature(result):
    provenance = {k: v for k, v in result['procedencia'].items() if k != 'assessment'}
    provenance['steadyDiagnostics'] = {k: v for k, v in provenance['steadyDiagnostics'].items() if k != 'resultSignature'}
    return signature({**result, 'procedencia': provenance})


def resolve(model):
    return SteadySystem(model).solve()


INVERSE_FIELDS = ['specificationSignature', 'inverseSpecification']


def _read_inverse(report, selection):
    """Strict slice-5 augmentation evidence over the pinned forward selection.

    Returns the augmented unknown order (forward unknowns, then freed inputs), the remaining
    parameter bindings and the appended specification row identities.
    """
    from core.mathematics.contract import keys
    from core.solvers import inverse_spec
    import re
    block = report['inverseSpecification']
    keys(block, ['format', 'version', 'record', 'data', 'rows', 'freedInputs', 'seedRegularity', 'invalidates', 'retains', 'scope'])
    if block['format'] != inverse_spec.FORMAT or type(block['version']) is not int or block['version'] != 1:
        raise ValueError('Expected inverse specification evidence version 1.')
    try:
        record = inverse_spec.read_specification(block['record'])
    except inverse_spec.InverseError as error:
        raise ValueError(error.code+': '+str(error)) from error
    specs, freed = record['specifications'], record['freedInputs']
    referenced = sorted({v for row in specs+freed for k, v in row.items() if k.endswith('DataId')})
    if not isinstance(block['data'], dict) or sorted(block['data']) != referenced:
        raise ValueError('Inverse evidence must carry exactly the referenced data declarations.')
    for value in block['data'].values():
        keys(value, ['texto', 'unidad'])
        if not all(isinstance(v, str) for v in value.values()): raise ValueError('Invalid inverse data declaration.')
    if not isinstance(report['specificationSignature'], str) or not re.fullmatch('[a-f0-9]{64}', report['specificationSignature']) or report['specificationSignature'] != signature([record, block['data']]):
        raise ValueError('Stale inverse specification signature.')
    freed_ids = [row['quantityId'] for row in freed]
    outputs = set(selection['unknowns']) | {row['quantityId'] for row in selection['reconstructions']}
    if not all(qid in selection['parameters'] for qid in freed_ids):
        raise ValueError('Only constant parameters of the pinned selection can be freed.')
    if not all(row['quantityId'] in outputs for row in specs):
        raise ValueError('Only solved or reconstructed quantities can be specified.')
    row_ids = ['specification.'+row['id'] for row in specs]
    if not isinstance(block['rows'], list) or [r.get('id') for r in block['rows']] != row_ids or [r.get('quantityId') for r in block['rows']] != [r['quantityId'] for r in specs]:
        raise ValueError('Specification rows differ from the record.')
    for row in block['rows']:
        keys(row, ['id', 'quantityId', 'targetSI', 'unit', 'latex']); units.interpretar(row['unit'])
        if type(row['targetSI']) not in (int, float) or not math.isfinite(row['targetSI']) or not isinstance(row['latex'], str):
            raise ValueError('Invalid specification target.')
    if not isinstance(block['freedInputs'], list) or [r.get('quantityId') for r in block['freedInputs']] != freed_ids:
        raise ValueError('Freed-input evidence differs from the record.')
    for row in block['freedInputs']:
        keys(row, ['quantityId', 'unit']); units.interpretar(row['unit'])
    seed = block['seedRegularity']
    keys(seed, ['augmentedSigmaMin', 'forwardSigmaMin', 'sensitivitySigmaMin', 'sensitivity'])
    def nonnegative(value):
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    if not nonnegative(seed['augmentedSigmaMin']) or not nonnegative(seed['forwardSigmaMin']) or seed['augmentedSigmaMin'] <= 0 or np.finfo(float).eps/seed['augmentedSigmaMin'] > 1e-8:
        raise ValueError('Seed regularity does not meet the admission gate.')
    if (seed['sensitivity'] is None) != (seed['sensitivitySigmaMin'] is None) or seed['sensitivity'] is not None and (
            not nonnegative(seed['sensitivitySigmaMin']) or not isinstance(seed['sensitivity'], list) or len(seed['sensitivity']) != len(specs) or
            not all(isinstance(r, list) and len(r) == len(freed) and all(type(v) in (int, float) and math.isfinite(v) for v in r) for r in seed['sensitivity'])):
        raise ValueError('Invalid specification sensitivity evidence.')
    if block['invalidates'] != ['solve', 'results'] or block['retains'] != ['model', 'transform'] or not isinstance(block['scope'], str):
        raise ValueError('Inverse specifications invalidate Solve and Results only.')
    return ([*selection['unknowns'], *freed_ids], {k: v for k, v in selection['parameters'].items() if k not in freed_ids}, row_ids)


def _check_inverse_numbers(report):
    """Review RF-1: the published SI numbers must reproduce the carried declarations."""
    block = report['inverseSpecification']
    specs, freed = block['record']['specifications'], block['record']['freedInputs']
    # The SI numbers published beside the record must be those of its carried declarations (review RF-1):
    # each declaration needs only its own text and unit, and the row or variable unit gives the dimension.
    # seedRegularity is compared between report and diagnostics only; it cannot be recomputed without
    # the model (review RF-2), like the other unkeyed numerical evidence.
    data = block['data']
    def declared(identity, unit):
        declaration = data[identity]
        try:
            conversion = units.exact_conversion(declaration['unidad'])
            value = parse_expression(declaration['texto'], {})
        except (ValueError, units.ErrorUnidad) as error:
            raise ValueError('Invalid inverse data declaration '+identity+': '+str(error)) from error
        if conversion['afin'] or conversion['dimension'] != units.interpretar(unit)['dimension']:
            raise ValueError('Inverse data declaration '+identity+' has an incompatible unit.')
        value = value*sp.Rational(conversion['factor'])+sp.Rational(conversion['desplazamiento'])
        if value.is_number is not True or value.is_finite is not True:
            raise ValueError('Inverse data declaration '+identity+' is not a finite constant.')
        return float(value)
    def same(a, b):
        return type(a) in (int, float) and math.isclose(a, b, rel_tol=1e-12, abs_tol=0.)
    if any(not same(row['targetSI'], declared(spec['targetDataId'], row['unit'])) for row, spec in zip(block['rows'], specs)):
        raise ValueError('A specification target differs from its carried declaration.')
    residual_rows, variables = report.get('residualRows'), report.get('variables')
    if not isinstance(residual_rows, list) or not isinstance(variables, list) or len(residual_rows) < len(specs) or len(variables) < len(freed):
        raise ValueError('Inverse evidence needs the augmented residual rows and variables.')
    for row, spec in zip(residual_rows[len(residual_rows)-len(specs):], specs):
        if not isinstance(row, dict) or not same(row.get('scaleSI'), declared(spec['residualScaleDataId'], row.get('unit', ''))):
            raise ValueError('A specification residual scale differs from its carried declaration.')
    for variable, entry, row in zip(variables[len(variables)-len(freed):], freed, block['freedInputs']):
        if not isinstance(variable, dict) or not isinstance(variable.get('boundsSI'), list) or len(variable['boundsSI']) != 2:
            raise ValueError('Invalid freed-input variable evidence.')
        expected = [declared(entry[key], row['unit']) for key in ('seedDataId', 'lowerDataId', 'upperDataId', 'scaleDataId')]
        if not all(same(a, b) for a, b in zip([variable.get('seedSI'), *variable['boundsSI'], variable.get('scaleSI')], expected)):
            raise ValueError('A freed-input seed, bound or scale differs from its carried declaration.')


def _read_closures(rows):
    """Additive closure block (demo-02-steady): package volumes whose outputs the package eliminates."""
    from core.mathematics.contract import keys
    if not isinstance(rows, list) or not rows:
        raise ValueError('Package-closure evidence must list each closure volume.')
    for row in rows:
        keys(row, ['volumeId', 'package', 'mode', 'specification', 'anchor', 'liquidOnly', 'outputs', 'constants'])
        if not isinstance(row['volumeId'], str) or not isinstance(row['package'], str) or row['mode'] not in ('equilibrium', 'single_phase') or \
                row['specification'] not in ('PH', 'UV') or row['anchor'] not in (None, 'gas', 'liquid') or type(row['liquidOnly']) is not bool:
            raise ValueError('Invalid package-closure identity.')
        for item in row['outputs']:
            keys(item, ['id', 'unit']); units.interpretar(item['unit'])
        for item in row['constants']:
            keys(item, ['id', 'value', 'unit']); units.interpretar(item['unit'])
            if type(item['value']) not in (int, float) or not math.isfinite(item['value']):
                raise ValueError('Invalid package constant.')
    return rows


def read_report(report, *, numbers=True):
    """Strict steady compilation contract; no numerical solve during reading.

    An inverse publication (F3 slice 5) pins the unchanged forward selection and adds the
    augmentation evidence: freed inputs follow the forward unknowns and leave the parameters,
    and one specification row per freed input follows the forward residual rows.
    """
    from core.mathematics.contract import keys
    import re
    inverse = isinstance(report, dict) and 'inverseSpecification' in report
    closures = isinstance(report, dict) and 'thermodynamicClosures' in report
    keys(report, ['format', 'version', 'study', 'sourceModelId', 'signature', 'sourceSignature',
        'formulationSignature', 'dataSignature', 'settingsSignature', 'method', 'selection', 'variables',
        'rows', 'residualRows', 'invariants', 'parameters', 'proofConditions', 'runtimeConditions', 'scope']+(INVERSE_FIELDS if inverse else [])
        +(['thermodynamicClosures'] if closures else [])+(['kineticDiagnostics'] if isinstance(report,dict) and 'kineticDiagnostics' in report else []))
    if closures:
        _read_closures(report['thermodynamicClosures'])
    if 'kineticDiagnostics' in report:
        block=report['kineticDiagnostics'];keys(block,['version','volumeIds'])
        owners=block['volumeIds'];available={r['volumeId'] for r in report.get('thermodynamicClosures',[]) if r['anchor'] is not None}
        if (type(block['version']) is not int or block['version']!=1 or not isinstance(owners,list) or not owners
                or any(not isinstance(v,str) or v not in available for v in owners) or len(set(owners))!=len(owners)):
            raise ValueError('Invalid kinetic equilibrium-limit diagnostic identities.')
    if report['format'] != 'rage.compilation' or type(report['version']) is not int or report['version'] != 2 or report['study'] != 'steady' or report['method'] != 'damped_newton':
        raise ValueError('Expected steady compilation version 2.')
    selection = read_steady_definition(report['selection'])
    for name in ('signature', 'sourceSignature', 'formulationSignature', 'dataSignature', 'settingsSignature'):
        if not isinstance(report[name], str) or not re.fullmatch('[a-f0-9]{64}', report[name]):
            raise ValueError('Invalid steady compilation signature.')
    if report['sourceSignature'] != selection['sourceSignature'] or report['formulationSignature'] != signature(selection) or report['settingsSignature'] != signature(selection['nonlinear']):
        raise ValueError('Steady compilation does not match its pinned selection.')
    unknown_ids, parameters, specification_rows = _read_inverse(report, selection) if inverse else (selection['unknowns'], selection['parameters'], [])
    def finite(value):
        return type(value) in (int, float) and math.isfinite(value)
    if [v['id'] for v in report['variables']] != unknown_ids:
        raise ValueError('Steady unknown ordering differs from its selection.')
    for row in report['variables']:
        keys(row, ['id', 'name', 'unit', 'scaleSI', 'seedSI', 'boundsSI'])
        units.interpretar(row['unit'])
        if not isinstance(row['name'], str) or not finite(row['scaleSI']) or row['scaleSI'] <= 0 or not finite(row['seedSI']) or not isinstance(row['boundsSI'], list) or len(row['boundsSI']) != 2 or not all(finite(x) for x in row['boundsSI']) or not row['boundsSI'][0] <= row['seedSI'] <= row['boundsSI'][1] or row['boundsSI'][0] >= row['boundsSI'][1]:
            raise ValueError('Invalid steady variable scales, seed or bounds.')
    expected_rows = [r['equationId'] for field in ('states', 'algebraic') for r in selection[field]]
    if [row['id'] for row in report['rows']] != expected_rows:
        raise ValueError('Steady source rows differ from the selected physical laws.')
    for row in report['rows']:
        keys(row, ['id', 'family', 'before', 'after', 'identity'])
        if type(row['identity']) is not bool or not all(isinstance(row[k], str) for k in ('family', 'before', 'after')):
            raise ValueError('Invalid steady specialization row.')
    if [r['id'] for r in report['residualRows']] != [r['id'] for r in report['rows'] if not r['identity']]+specification_rows or len(report['residualRows']) != len(report['variables']):
        raise ValueError('Invalid square residual block.')
    for row in report['residualRows']:
        keys(row, ['id', 'unit', 'scaleSI']); units.interpretar(row['unit'])
        if not finite(row['scaleSI']) or row['scaleSI'] <= 0:
            raise ValueError('Invalid original-row scale.')
    if {row['quantityId']: row['dataId'] for row in report['invariants']} != selection['invariants']:
        raise ValueError('Invariant evidence disagrees with its explicit bindings.')
    for row in report['invariants']:
        keys(row, ['quantityId', 'equationId', 'dataId', 'value', 'unit'])
        if not finite(row['value']) or row['equationId'] not in [r['id'] for r in report['rows'] if r['identity']]:
            raise ValueError('Invalid individually invariant state evidence.')
        units.interpretar(row['unit'])
    if {row['id']: row['dataId'] for row in report['parameters']} != parameters:
        raise ValueError('Parameter evidence disagrees with its bindings.')
    for row in report['parameters']:
        keys(row, ['id', 'dataId', 'value', 'unit']); units.interpretar(row['unit'])
        if not finite(row['value']): raise ValueError('Invalid parameter value.')
    for field in ('proofConditions', 'runtimeConditions'):
        for row in report[field]:
            keys(row, ['equationId', 'kind', 'latex'])
            if not all(isinstance(v, str) for v in row.values()): raise ValueError('Invalid steady condition.')
    if not isinstance(report['scope'], str) or not isinstance(report['sourceModelId'], str):
        raise ValueError('Invalid steady report identity/scope.')
    if inverse:
        variable_units = {v['id']: v['unit'] for v in report['variables']}
        residual_units = {r['id']: r['unit'] for r in report['residualRows']}
        block = report['inverseSpecification']
        if any(variable_units[r['quantityId']] != r['unit'] for r in block['freedInputs']) or any(
                residual_units[r['id']] != r['unit'] or r['quantityId'] in variable_units and variable_units[r['quantityId']] != r['unit'] for r in block['rows']):
            raise ValueError('Inverse specification units differ from the augmented block.')
        if numbers:
            _check_inverse_numbers(report)
    return report


def read_result(result):
    from core.mathematics.contract import keys
    evidence = result['procedencia']['steadyDiagnostics']
    report = read_report(result['procedencia']['compilation'], numbers=False)
    inverse = 'inverseSpecification' in report
    keys(evidence, ['version', 'verdict', 'globalUniqueness', 'method', 'sourceSignature', 'formulationSignature',
        'dataSignature', 'settingsSignature', 'compilationSignature', 'quantityIds', 'equationIds', 'variableScales',
        'residualScales', 'smallestSingularValue', 'conditionThreshold', 'inverseThreshold', 'relativeAmplification',
        'inverseAmplification', 'initialResidualNorm', 'solver', 'scope', 'resultSignature']+(['inverseSpecification'] if inverse else [])
        +(['thermodynamicClosures'] if 'thermodynamicClosures' in report else []))
    if result['estado'] != 'resuelto' or result['ejes'] or result['eventos'] or result['modeloId'] != report['sourceModelId'] or result['procedencia']['motor'] != 'rage.compilador.steady':
        raise ValueError('A steady accepted result is one scalar state, never a trajectory or partial iterate.')
    if type(evidence['version']) is not int or evidence['version'] != 1 or evidence['verdict'] != 'local_regular_root' or evidence['globalUniqueness'] != 'not_proved' or evidence['method'] != 'damped_newton' or result['procedencia']['metodo'] != evidence['method']:
        raise ValueError('Invalid steady convergence or uniqueness verdict.')
    for key in ('sourceSignature', 'formulationSignature', 'dataSignature', 'settingsSignature'):
        if evidence[key] != report[key]: raise ValueError('Stale steady diagnostics.')
    if evidence['compilationSignature'] != report['signature'] or evidence['resultSignature'] != steady_result_signature(result):
        raise ValueError('Steady result signature differs from its scalar state or evidence.')
    if evidence['quantityIds'] != [v['id'] for v in report['variables']] or evidence['equationIds'] != [r['id'] for r in report['residualRows']] or evidence['variableScales'] != [v['scaleSI'] for v in report['variables']] or evidence['residualScales'] != [r['scaleSI'] for r in report['residualRows']]:
        raise ValueError('Steady evidence ordering/scaling differs from compilation.')
    solver = evidence['solver']
    keys(solver, ['iterations', 'evaluations', 'backtracks', 'residualNorm', 'stepNorm', 'conditionInfinity', 'terminationReason', 'completedProbes', 'uniqueness'])
    for key in ('iterations', 'evaluations', 'backtracks', 'completedProbes'):
        if type(solver[key]) is not int or solver[key] < 0: raise ValueError('Invalid Newton counter.')
    for value in [solver[k] for k in ('residualNorm', 'stepNorm', 'conditionInfinity')]+[evidence[k] for k in ('smallestSingularValue', 'relativeAmplification', 'inverseAmplification', 'initialResidualNorm')]:
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0: raise ValueError('Invalid steady regularity measure.')
    config = report['selection']['nonlinear']
    if (solver['terminationReason'] != 'converged' or solver['residualNorm'] > config['residualTolerance'] or solver['stepNorm'] > config['stepTolerance'] or
        solver['iterations'] > config['maxIterations'] or solver['conditionInfinity'] < 1 or evidence['conditionThreshold'] != 1e-8 or evidence['inverseThreshold'] != 1e-8 or evidence['smallestSingularValue'] <= 0 or
        evidence['relativeAmplification'] != solver['conditionInfinity']*np.finfo(float).eps or evidence['inverseAmplification'] != np.finfo(float).eps/evidence['smallestSingularValue'] or
        max(evidence['relativeAmplification'], evidence['inverseAmplification']) > 1e-8 or solver['uniqueness'] != 'local_root_only; finite probes do not prove global uniqueness'):
        raise ValueError('Steady root does not meet the requested convergence/regularity gates.')
    selection = report['selection']
    if inverse:
        block = report['inverseSpecification']
        summary = evidence['inverseSpecification']
        keys(summary, ['specificationSignature', 'freedInputs', 'specificationRows', 'seedRegularity'])
        if (summary['specificationSignature'] != report['specificationSignature'] or summary['freedInputs'] != [r['quantityId'] for r in block['freedInputs']] or
                summary['specificationRows'] != [r['id'] for r in block['rows']] or summary['seedRegularity'] != block['seedRegularity']):
            raise ValueError('Stale inverse specification diagnostics.')
    expected = {'steady.'+key for key in [*[v['id'] for v in report['variables']], *selection['invariants'], *[r['quantityId'] for r in selection['reconstructions']]]}
    expected |= {'steady.residual.'+key for key in evidence['equationIds']}
    closure_rows = report.get('thermodynamicClosures', [])
    expected |= {'closure.'+item['id'] for row in closure_rows for item in row['outputs']}
    if closure_rows:
        published = evidence['thermodynamicClosures']
        if not isinstance(published, list) or [p.get('volumeId') for p in published] != [r['volumeId'] for r in closure_rows] or any(
                not isinstance(p.get('phaseSet'), list) or not isinstance(p.get('fingerprint'), str) for p in published):
            raise ValueError('Package-closure evidence differs from its compilation.')
    if len(result['series']) != len(expected) or {r['id'] for r in result['series']} != expected:
        raise ValueError('Missing or duplicate scalar steady output.')
    for row in result['series']:
        if row['ejes'] or type(row['valores']) not in (int, float) or not math.isfinite(row['valores']): raise ValueError('Steady series must be finite scalars.')
    series = {r['id']: r for r in result['series']}
    for row in report['variables']:
        item = series['steady.'+row['id']]
        if item['unidadSI'] != row['unit'] or not row['boundsSI'][0] <= item['valores'] <= row['boundsSI'][1]: raise ValueError('Scalar state differs from its admitted units/domain.')
    for row in report['invariants']:
        item = series['steady.'+row['quantityId']]
        if item['valores'] != row['value'] or item['unidadSI'] != row['unit']: raise ValueError('An invariant binding changed.')
    maximum = 0.
    for row in report['residualRows']:
        item = series['steady.residual.'+row['id']]
        if item['unidadSI'] != row['unit']: raise ValueError('Original residual unit mismatch.')
        maximum = max(maximum, abs(item['valores'])/row['scaleSI'])
    for row in report['inverseSpecification']['rows'] if inverse else []:
        # The appended row is exactly quantity - target, re-evaluated from the published scalar state.
        output, residual = series['steady.'+row['quantityId']], series['steady.residual.'+row['id']]['valores']
        value, target = output['valores'], row['targetSI']
        if output['unidadSI'] != row['unit'] or abs(residual-(value-target)) > 8*np.finfo(float).eps*max(1., abs(value), abs(target)):
            raise ValueError('Specification residual differs from its published output and target.')
    checks = {row['id']: row for row in result['verificaciones']}
    required = {'steady.scaled_residual'} | {'conservation.'+r['equationId'] for r in selection['checks']} | {'invariant.'+key for key in selection['invariants']}
    closure_tolerance = {'thermodynamics.closure.'+row['volumeId']: 1. if row['mode'] == 'equilibrium' else 1e-9 for row in closure_rows}
    required |= set(closure_tolerance)
    diagnostic_ids={'reactions.equilibrium_limit.'+owner for owner in report.get('kineticDiagnostics',{}).get('volumeIds',[])}
    required |= diagnostic_ids
    if len(checks) != len(result['verificaciones']) or set(checks) != required or maximum > config['residualTolerance'] or checks['steady.scaled_residual']['valor'] != maximum:
        raise ValueError('Steady verification disagrees with original residuals.')
    for key, row in checks.items():
        if key in diagnostic_ids:
            if type(row['valor']) not in (int,float) or not math.isfinite(row['valor']) or row['valor']<0 or row['tolerancia']!=1e-3:
                raise ValueError('Invalid kinetic equilibrium-limit diagnostic.')
            continue
        tolerance = config['residualTolerance'] if key == 'steady.scaled_residual' else closure_tolerance.get(key, 1e-6)
        if type(row['valor']) not in (int, float) or not math.isfinite(row['valor']) or not 0 <= row['valor'] <= tolerance or row['tolerancia'] != tolerance:
            raise ValueError('Failed steady verification cannot certify an accepted state.')
    if inverse:
        _check_inverse_numbers(report)
    return result
