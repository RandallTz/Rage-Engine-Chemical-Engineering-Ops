"""Lower selected, replayed equations to the common explicit ODE runtime.

Selections contain identities and data bindings only. No equipment names,
fixture identities, client RHS expressions or earlier physical RHS are used.
"""
import copy
import hashlib
import json
import math

import numpy as np
import sympy as sp

from core import unidades as units
from core.mathematics.constants import UnitBasis, si_magnitude
from core.mathematics.dimensions import catalog, dimension, parse_expression
from core.mathematics.graph import math_latex, solve_unique
from core.mathematics.linear_system import ConstantAffineBlock, AffineBlockError
from core.mathematics.validity import HoldsOnInterval
from core.solvers.nonlinear import NonlinearError
from .nonlinear_block import NonlinearBlock, NonlinearRuntime
from core.modelo import leer_modelo_comun
from core.modelo.derived_execution import read_definition
from core.modelo.equation_workbench import build, _known_unit, SOURCE_REVISION
from core.resultados import conjunto, eje, evento, serie
from core.solvers import Detencion, Trayectoria, integrar
from .compilador import NoSoportado
from .explicito import SistemaExplicito
from .derived_graph import DerivedGraph, LoweringError, source_signature


def validate_selected_data(model):
    """Diagnose missing numerical bindings before the strict model reader."""
    if (not isinstance(model, dict) or not isinstance(model.get('motores'), dict)
            or not isinstance(model.get('datos'), dict) or not selected(model)):
        return
    if model['motores']['derivedExecution'].get('version') == 5:
        from .steady import validate_selected_data as validate_steady_data
        return validate_steady_data(model)
    try:
        selection = read_definition(model['motores']['derivedExecution'])
    except (ValueError, KeyError, TypeError) as error:
        raise LoweringError('invalid_derived_formulation', str(error)) from error
    bindings = [data for field in ('parameters', 'initialValues', 'scaling')
                for data in selection.get(field, {}).values()]
    bindings += [row['scaleDataId'] for row in selection['checks']]
    for key in bindings:
        if key not in model.get('datos', {}):
            raise LoweringError('missing_data', 'Missing selected numerical datum: ' + key)


def selected(model):
    return model.get('motores', {}).get('derivedExecution') is not None


def _dimension_json(value):
    return {base: {'n': int(sp.Rational(power).p), 'd': int(sp.Rational(power).q)}
            for base, power in value.items() if power}


def _symbol(identity, role, dim):
    return {'id': identity, 'nombre': identity, 'rol': role,
            'dimension': _dimension_json(dim), 'unidad': units.unidad_SI(dim),
            'constante': role in ('parametro', 'constante'),
            'dependeDe': [], 'signo': 'desconocido'}


class DerivedSystem(DerivedGraph):
    def __init__(self, model):
        try:
            self._initialize(model)
        except LoweringError as error:
            self._locate_failure(model, error)
            raise
        except (NonlinearError, Detencion) as error:
            failure = LoweringError(getattr(error, 'code', getattr(error, 'codigo', 'nonlinear_initialization')), str(error))
            failure.diagnostics = getattr(error, 'diagnostics', failure.diagnostics)
            self._locate_failure(model, failure, 'initialization')
            raise failure from error
        except (ValueError, NotImplementedError, KeyError) as error:
            failure = LoweringError('invalid_derived_formulation', str(error))
            self._locate_failure(model, failure)
            raise failure from error

    @staticmethod
    def _locate_failure(model, error, stage='admission'):
        selection = model.get('motores', {}).get('derivedExecution', {})
        if selection.get('version') not in (3, 4):
            return
        for row in error.diagnostics:
            if row['code'] in ('invalid_initialization', 'missing_initialization', 'invalid_initial_domain', 'dae_initial_states_required'):
                stage = 'initialization'
            defaults = {'stage': stage, 'path': 'motores.derivedExecution.nonlinear',
                        'modelId': model.get('id'), 'sourceSignature': selection.get('sourceSignature'),
                        'formulationSignature': hashlib.sha256(json.dumps([SOURCE_REVISION, selection,
                            {key: value.get('declaracion') for key, value in model.get('datos', {}).items()},
                            model.get('estudio')], sort_keys=True).encode()).hexdigest(),
                        'equationIds': [r.get('equationId') for r in selection.get('algebraic', [])],
                        'quantityIds': [r.get('quantityId') for r in selection.get('algebraic', [])],
                        'time': 0. if stage == 'initialization' else None, 'iterations': 0,
                        'evaluations': 0, 'backtracks': 0, 'residualNorm': None,
                        'stepNorm': None, 'conditionInfinity': None, 'terminationReason': row['code']}
            for key, value in defaults.items():
                row.setdefault(key, value)

    def _initialize(self, model):
        validate_selected_data(model)
        self.model = leer_modelo_comun(model)
        self.selection = read_definition(model['motores']['derivedExecution'], model)
        self.nonlinear = self.selection['version'] in (3, 4)
        self.dae = None
        self.is_dae = self.selection['version'] == 4
        if self.is_dae and model['estudio']['metodoSolicitado'].lower() != 'bdf':
            raise LoweringError('dae_method_unsupported', 'Semi-explicit index-1 execution requires BDF; no method substitution is allowed.')
        if model.get('matematico') is not None or model['motores'].get('adimensionalizacion') is not None:
            raise LoweringError('competing_formulation', 'Select the derived graph alone; cached mathematical trees and competing scaling selections are not execution inputs.')
        if any(v['termodinamica']['tipo'] != 'supuesto' for v in model['volumenes']):
            raise LoweringError('unsupported_closure', 'Derived explicit execution does not lower equilibrium closures.')
        for volume in model['volumenes']:
            for balance, journal in [('materia', 'materialDerivation'), ('energia', 'energyDerivation')]:
                if volume['balances'][balance] and volume['id'] not in model['motores'].get(journal, {}).get('volumes', {}):
                    raise LoweringError('unrecorded_source', 'Numerical graph execution requires the recorded physical journal for this active balance.')
        from core.modelo.dynamic_definition import ensure_executable
        ensure_executable(model)
        # Replaying the source validates the actual physical journals and pins.
        self.replayed = build(model)
        if any(r.signature_status == 'legacy/unsigned' for r in self.replayed.receipts):
            raise LoweringError('unsigned_operation', 'Legacy/unsigned operations cannot be compiled. Undo/Rewind and record reviewed inputs.')
        if source_signature(model, self.replayed) != self.selection['sourceSignature']:
            raise LoweringError('stale_formulation', 'The selected Transform graph changed. Review its current rows before selecting numerical execution.')
        self.graph = self.replayed.graph
        self.quantities = {**catalog(self.graph, self.replayed.units), **self.replayed.introduced}
        self.time = self._quantity(self.selection['timeId'])
        if not isinstance(self.time, sp.Symbol) or self._dim(self.time) != {'T': 1}:
            raise LoweringError('invalid_time', 'Select one independent time quantity with time dimension.')
        self.states = [self._quantity(row['quantityId']) for row in self.selection['states']]
        if any(not isinstance(q, sp.core.function.AppliedUndef) or q.args != (self.time,) for q in self.states):
            raise LoweringError('unsupported_state', 'Retained states must depend only on the selected time coordinate.')
        self.ids = {q: row['quantityId'] for q, row in zip(self.states, self.selection['states'])}
        self.ids[self.time] = self.selection['timeId']
        self.parameter_symbols = {}; self.parameter_values = {}; self.parameter_records = []
        for qid, data_id in self.selection['parameters'].items():
            q = self._quantity(qid)
            if not isinstance(q, (sp.Symbol, sp.core.function.AppliedUndef)) or isinstance(q, sp.core.function.AppliedUndef) and q.args != (self.time,):
                raise LoweringError('unsupported_parameter', 'A numerical datum binds a scalar or prescribed time-only boundary quantity: ' + qid)
            parameter = sp.Symbol('datum_' + hashlib.sha256(data_id.encode()).hexdigest()[:12], real=True)
            self.parameter_symbols[q] = parameter
            self.parameter_values[parameter] = self._datum(data_id, self._dim(q))
            self.ids[parameter] = str(parameter)
            self.parameter_records.append({'id': qid, 'dataId': data_id,
                'value': float(self.parameter_values[parameter]), 'unit': self._unit(q)})
        self.replacements = dict(self.parameter_symbols)
        self.algebraic_rows = self.selection.get('algebraic', [])
        self.algebraic_quantities = [self._quantity(row['quantityId']) for row in self.algebraic_rows]
        if any(not isinstance(q, sp.core.function.AppliedUndef) or q.args != (self.time,) for q in self.algebraic_quantities):
            raise LoweringError('invalid_algebraic_block', 'Algebraic unknowns must depend only on the selected time.')
        self.ids.update({q: row['quantityId'] for q, row in zip(self.algebraic_quantities, self.algebraic_rows)})
        self.guards = []
        for row in self.selection['reconstructions']:
            q = self._quantity(row['quantityId']); node = self._equation(row['equationId'])
            value, conditions = solve_unique(node.equation, q, self.graph.names)
            self.replacements[q] = value
            self.guards.extend((condition, row['equationId']) for condition in conditions)
        # Declared, oriented definitions/closures are expressions in the source,
        # not a second collection of equations supplied by this compiler.
        for index, operation in enumerate(self.replayed.definition['operations'][:self.replayed.definition['cursor']], 1):
            if operation['kind'] != 'declare_relation':
                continue
            key = 'operation.' + str(index); equation = self.graph.nodes[key].equation
            target = equation.lhs
            if isinstance(target, (sp.Symbol, sp.core.function.AppliedUndef)) and target not in self.states and target not in self.replacements and target not in self.algebraic_quantities:
                self.replacements[target] = equation.rhs
        self.runtime_replacements = dict(self.replacements)
        self.algebraic_block = None
        if self.algebraic_rows:
            if self.selection.get('scaling'):
                raise LoweringError('unsupported_algebraic_scaling', 'Affine-block execution currently requires the identity formulation.')
            equations = [self._equation(row['equationId']).equation for row in self.algebraic_rows]
            for row, equation in zip(self.algebraic_rows, equations):
                self._dim(equation.lhs-equation.rhs)
                if equation.has(sp.Derivative):
                    raise LoweringError('dae_implicit_unsupported' if self.is_dae else 'unsupported_algebraic_derivative', 'An algebraic block cannot contain derivatives. IDA is a future option for fully implicit systems.', row['equationId'])
            residuals = [self._expand(e.lhs-e.rhs, self.runtime_replacements) for e in equations]
            try:
                self.algebraic_block = (NonlinearBlock(self, residuals) if self.nonlinear else
                                        ConstantAffineBlock(residuals, self.algebraic_quantities, self.parameter_values))
            except (AffineBlockError, NonlinearError) as error:
                diagnostic = LoweringError(error.code, str(error), self.algebraic_rows[0]['equationId'])
                if isinstance(error, NonlinearError):
                    diagnostic.diagnostics[0].update(error.diagnostic)
                diagnostic.diagnostics[0].update(path='motores.derivedExecution.algebraic',
                    equationIds=[row['equationId'] for row in self.algebraic_rows])
                raise diagnostic from error
            if not self.nonlinear:
                self.replacements.update(self.algebraic_block.reconstruction)
                self.guards.append((sp.Ne(self.algebraic_block.matrix.det(), 0, evaluate=False), self.algebraic_rows[0]['equationId']))
        if self.is_dae:
            from .dae import IndexOne
            try:
                self.dae = IndexOne(self)
            except NonlinearError as error:
                raise LoweringError(error.code, str(error)) from error
        self.rates = {}
        self.runtime_rates = []
        for row, q in zip(self.selection['states'], self.states):
            equation = self._equation(row['equationId']).equation
            derivative = sp.Derivative(q, self.time, evaluate=False)
            if self.is_dae:
                from .dae import FUTURE
                residual = self._expand(equation.lhs-equation.rhs, self.runtime_replacements).doit()
                if residual.atoms(sp.Derivative) != {derivative}:
                    raise LoweringError('dae_implicit_unsupported', 'Select semi-explicit first-order differential rows. '+FUTURE, row['equationId'])
                coefficient = sp.diff(residual, derivative)
                bound = si_magnitude(coefficient).subs(self.parameter_values)
                if coefficient.has(derivative) or bound.is_number is not True or bound == 0:
                    raise LoweringError('dae_implicit_unsupported', 'Only a nonzero constant scalar derivative coefficient is admitted. '+FUTURE, row['equationId'])
            if self.algebraic_block is not None:
                runtime_equation = sp.Eq(self._expand(equation.lhs, self.runtime_replacements).doit(),
                                         self._expand(equation.rhs, self.runtime_replacements).doit(), evaluate=False)
                if runtime_equation.atoms(sp.Derivative) != {derivative}:
                    raise LoweringError('unsupported_rate', 'Affine-block RHS rows must isolate one first derivative without differentiating algebraic unknowns.', row['equationId'])
                rate, guards = solve_unique(runtime_equation, derivative, self.graph.names)
                self.runtime_rates.append(rate)
                self.guards.extend((guard, row['equationId']) for guard in guards)
            # Apply the selected algebraic reconstructions and product rule
            # before isolating a regular, first-order scalar rate. This admits
            # density-volume balances without inserting a replacement law.
            expanded = sp.Eq(self._expand(equation.lhs).doit(),
                             self._expand(equation.rhs).doit(), evaluate=False)
            if expanded.atoms(sp.Derivative) != {derivative}:
                raise LoweringError('unsupported_rate', 'The selected row must determine one first time derivative; coupled derivative constraints need another lowering.', row['equationId'])
            if expanded.lhs == derivative:
                self.rates[derivative] = expanded.rhs
                continue
            try:
                residual = expanded.lhs-expanded.rhs
                if sp.Poly(residual, derivative).degree() != 1:
                    raise ValueError('The selected rate is not linear in its first derivative.')
                rate, guards = solve_unique(expanded, derivative, self.graph.names)
            except (ValueError, sp.PolynomialError) as error:
                raise LoweringError('unsupported_rate', str(error), row['equationId']) from error
            self.rates[derivative] = rate
            self.guards.extend((guard, row['equationId']) for guard in guards)
        self.reconstructed = [(row, self._expand(self._quantity(row['quantityId']))) for row in self.selection['reconstructions']]
        self._initial_conditions()
        self.proof_conditions = []
        bound_coordinates = {p.args[1] for node in self.graph.nodes.values() for p in node.predicates if isinstance(p, HoldsOnInterval) and p.args[1] != self.time}
        self.bound_coordinates = bound_coordinates
        self._collect_conditions()
        if self.nonlinear:
            self.algebraic_block.set_conditions(self.margins)
        self._check_operations()
        self.checks = self._conservation_checks()
        self.lowered = self._lower_model()
        from core.adimensionalizacion.dimensional import analizar_modelo
        analysis = analizar_modelo(self.lowered['matematico'])
        if analysis['estado'] != 'compatible':
            raise LoweringError('incompatible_lowering', 'The lowered AST does not preserve the declared equation dimensions: ' + str(analysis))
        self.numeric = NonlinearRuntime(self) if self.nonlinear else SistemaExplicito(self.lowered)
        if self.algebraic_block is not None and not self.nonlinear:
            evaluator = copy.copy(self.numeric)
            evaluator.indice = {**self.numeric.indice, **{self.ids[q]: len(self.numeric.campos)+i for i, q in enumerate(self.algebraic_quantities)}}
            self.algebraic_forcing = [self.numeric._compilar(self._ast(e), 'affine block forcing') for e in self.algebraic_block.forcing]
            self.algebraic_rates = [evaluator._compilar(self._ast(e), 'affine block RHS') for e in self.runtime_rates]
        self.scaled = None
        if 'scaling' in self.selection:
            self._select_scaling()
        self.size = len(self.states)
        self.state_ids = [row['quantityId'] for row in self.selection['states']]
        self.initial_state = self.numeric.inicial()
        self.tf = self.numeric.tf
        self.method = self.numeric.metodo
        self.runtime_guards = [(self.numeric._compilar(self._ast(expression), 'derived validity'), strict, key, label)
                               for expression, strict, key, label in self.margins]
        self._physical_admission()
        self._validate_initial()
        self.report = self._report()
        if self.dae:
            self.validate_accepted = self._validate_dae_accepted

    def _normalize(self, expression):
        expression = self._expand(expression).doit()
        for _ in range(len(self.rates) + 2):
            current = self._expand(expression.xreplace(self.rates)).doit()
            if current == expression:
                value = sp.cancel(current)
                if self.nonlinear and self.algebraic_block.is_consequence(value):
                    return sp.S.Zero
                return value
            expression = current
        raise LoweringError('unsupported_derivative', 'A derivative cannot be lowered to the selected explicit states.')

    def _initial_conditions(self):
        if self.is_dae:
            missing = {r['quantityId'] for r in self.selection['states']} - set(self.selection['initialValues'])
            if missing:
                raise LoweringError('dae_initial_states_required', 'Provide each differential state at t0; free-state initialization is deferred. Missing: '+', '.join(sorted(missing)))
        initial = {self._quantity(qid): self._datum(data, self._dim(self._quantity(qid)))
                   for qid, data in self.selection['initialValues'].items()}
        initial.update(self.parameter_values)
        initial.update({q: initial[p] for q, p in self.parameter_symbols.items()})
        pending = [q for q in self.states if q not in initial]
        for _ in self.states:
            for q in pending[:]:
                for key in self.selection['initialEquations']:
                    equation = self._equation(key).equation.xreplace(self.parameter_symbols).xreplace(initial)
                    if not equation.has(q):
                        continue
                    value, guards = solve_unique(equation, q, self.graph.names)
                    value = si_magnitude(value).subs(initial)
                    if value.is_number is True and value.is_real is True and value.is_finite is True:
                        if any(sp.simplify(si_magnitude(p).subs({**initial, q: value})) is sp.S.false for p in guards):
                            raise LoweringError('invalid_initialization', 'Initialization violates an algebraic inversion condition.', key)
                        initial[q] = value; pending.remove(q); break
        if pending:
            raise LoweringError('missing_initialization', 'Initial data and selected algebraic identities do not determine: ' + ', '.join(map(str, pending)))
        for q in self.replacements:
            if q not in initial:
                value = si_magnitude(self._expand(q)).xreplace(initial)
                if value.is_number is True:
                    initial[q] = value
        initial[self.time] = sp.S.Zero
        if self.dae:
            self.dae.state_domain(0., [float(initial[q]) for q in self.states], 'initialization')
        if self.nonlinear:
            try:
                z, _ = self.algebraic_block.evaluate(0., [float(initial[q]) for q in self.states], 'initialization')
            except NonlinearError as error:
                failure = LoweringError(error.code, str(error))
                failure.diagnostics = error.diagnostics
                raise failure from error
            self.initial_algebraic = dict(zip(self.algebraic_quantities, map(sp.Float, z)))
            for q, solved in self.initial_algebraic.items():
                if q in initial and not math.isclose(float(initial[q]), float(solved), rel_tol=self.selection['nonlinear']['residualTolerance'], abs_tol=self.selection['nonlinear']['stepTolerance']):
                    raise LoweringError('invalid_initialization', 'Fixed algebraic initial data contradict the solved constraints: '+str(q))
                initial[q] = solved
        for key in self.selection['initialEquations']:
            equation = self._equation(key).equation
            residual = si_magnitude((equation.lhs-equation.rhs).xreplace(self.parameter_symbols)).xreplace(initial)
            if residual.is_number is not True or abs(float(residual)) > 1e-9:
                raise LoweringError('invalid_initialization', 'The selected initial relation is inconsistent or underdetermined.', key)
        self.initial_values = {q: initial[q] for q in self.states}
        for qid, data in self.selection['initialValues'].items():
            q = self._quantity(qid)
            value = si_magnitude(self._expand(q)).xreplace(initial)
            expected = self._datum(data, self._dim(q))
            if value.is_number is not True or not math.isclose(float(value), float(expected), rel_tol=1e-10, abs_tol=1e-10):
                raise LoweringError('invalid_initialization', 'Initial reconstruction disagrees with its numerical datum: ' + qid)

    def _collect_conditions(self):
        self.margins = []
        selected_keys = {r['equationId'] for r in [*self.selection['states'], *self.selection['reconstructions'], *self.selection['checks'], *self.algebraic_rows]}
        selected_keys.update(key for key in self.graph.nodes if key.startswith('operation.'))
        predicates = [(p, key) for key in sorted(selected_keys) for p in self.graph.predicates_for(key)] + self.guards
        predicates += [(premise.expression, key) for key, premise in self.graph.domains.items()]
        seen = set()
        graph_equalities = {sp.srepr(node.equation): key for key, node in self.graph.nodes.items()}
        physical_predicates = {p: key for key, node in self.graph.nodes.items() if not key.startswith('operation.') for p in node.predicates}
        for predicate, key in predicates:
            if predicate in seen or predicate is sp.S.true:
                continue
            seen.add(predicate)
            if isinstance(predicate, HoldsOnInterval):
                equation, coordinate = predicate.args
                source = graph_equalities.get(sp.srepr(equation))
                if source is None:
                    raise LoweringError('unsupported_identity_premise', 'An interval identity has no replayed source equation.', key)
                self.proof_conditions.append({'equationId': key, 'sourceEquationId': source,
                    'kind': 'interval_identity', 'latex': math_latex(predicate, self.graph.names)})
                continue
            value = si_magnitude(self._expand(predicate))
            # Local-coordinate premises belong to the already replayed physical
            # reduction. They remain explicit conditional proof obligations;
            # they are not new numerical states or a claimed spatial solver.
            spatial_fields = [f for f in value.atoms(sp.core.function.AppliedUndef) if f.args != (self.time,)]
            if value.free_symbols & self.bound_coordinates or spatial_fields:
                if predicate not in physical_predicates:
                    raise LoweringError('unsupported_spatial_condition', 'A newly recorded condition on an unretained spatial field/coordinate has no numerical lowering.', key)
                self.proof_conditions.append({'equationId': key, 'sourceEquationId': physical_predicates[predicate],
                    'kind': 'eliminated_coordinate_premise', 'latex': math_latex(predicate, self.graph.names)})
                continue
            first_margin = len(self.margins)
            self._predicate_margin(value, key)
            # Evaluate expanded expressions, but name the recorded physical
            # condition rather than its substituted internal datum symbols.
            for index in range(first_margin, len(self.margins)):
                expression, strict, source, _ = self.margins[index]
                self.margins[index] = (expression, strict, source, math_latex(predicate, self.graph.names))
        for volume in self.model['volumenes']:
            closure = volume['termodinamica']
            if closure.get('supuesto') != 'u_lineal' or not volume['balances']['energia']:
                continue
            parameters = closure.get('parametros', {})
            if not all(key in parameters for key in ('cId', 'uRefId', 'TRefId', 'TMinId', 'TMaxId')):
                raise LoweringError('missing_closure_data', 'The declared caloric closure needs its numerical coefficient, references and validity interval.')
            owner = volume['id']
            temperatures = [(row, expression) for row, expression in self.reconstructed if self.replayed.owners[row['equationId']] == owner and self._dim(self._quantity(row['quantityId'])) == {'Theta': 1}]
            if self.is_dae:
                temperatures.extend((row, q) for row, q in zip(self.algebraic_rows, self.algebraic_quantities)
                                    if row['equationId'] == 'thermodynamics.'+owner+'.caloric-inventory'
                                    and self._dim(q) == {'Theta': 1})
            if len(temperatures) != 1:
                raise LoweringError('missing_caloric_reconstruction', 'Select the temperature reconstruction of the declared caloric inventory.')
            row, expression = temperatures[0]
            lower = self._datum(parameters['TMinId'], {'Theta': 1})
            upper = self._datum(parameters['TMaxId'], {'Theta': 1})
            if lower >= upper:
                raise LoweringError('invalid_caloric_interval', 'The declared caloric validity interval is empty or reversed.')
            self.margins.extend([(expression-lower, False, row['equationId'], 'Declared caloric lower temperature'),
                                 (upper-expression, False, row['equationId'], 'Declared caloric upper temperature')])
        hydraulic = self.model['motores'].get('hydraulicNetwork')
        if hydraulic:
            for storage in hydraulic['storages']:
                for q, row in zip(self.states, self.selection['states']):
                    if self.replayed.owners[row['equationId']] == storage['volumeId'] and self._dim(q) == {'M': 1}:
                        self.margins.append((q, False, row['equationId'], 'Nonnegative material inventory'))

    def _predicate_margin(self, predicate, key):
        if predicate is sp.S.true:
            return
        if predicate is sp.S.false:
            raise LoweringError('contradictory_condition', 'A selected validity condition is false.', key)
        if isinstance(predicate, sp.Contains):
            q, allowed = predicate.args
            if allowed == sp.S.Reals:
                return  # Every compiled arithmetic evaluator is real and finite.
            if isinstance(allowed, sp.Interval):
                if allowed.start != -sp.oo:
                    self.margins.append((q-allowed.start, bool(allowed.left_open), key, math_latex(predicate)))
                if allowed.end != sp.oo:
                    self.margins.append((allowed.end-q, bool(allowed.right_open), key, math_latex(predicate)))
                return
            if allowed == sp.FiniteSet(0):
                if self._normalize(q) == 0:
                    return
                raise LoweringError('unsupported_constraint', 'A zero-domain constraint is not an explicit reconstruction.', key)
            raise LoweringError('unsupported_condition', 'This domain needs unsupported numerical enforcement.', key)
        if isinstance(predicate, (sp.GreaterThan, sp.StrictGreaterThan, sp.LessThan, sp.StrictLessThan, sp.Unequality)):
            delta = predicate.lhs-predicate.rhs
            if isinstance(predicate, sp.Unequality):
                # A continuous nonzero expression stays in the connected sign
                # branch selected by its initial data. A signed margin makes
                # a crossing visible to the existing nonnegative-domain stop;
                # abs(expression) would hide a jump across the excluded zero.
                initial = delta.xreplace({**self.parameter_values, **self.initial_values, **getattr(self, 'initial_algebraic', {}), self.time: sp.S.Zero})
                if initial.is_number is not True or initial.is_real is not True or initial.is_finite is not True:
                    raise LoweringError('unsupported_condition', 'The nonzero condition needs a finite initial sign.', key)
                if initial == 0:
                    raise LoweringError('invalid_initial_domain', 'Initial data violate a nonzero condition.', key)
                delta = delta if initial > 0 else -delta
                strict = True
            else:
                if isinstance(predicate, (sp.LessThan, sp.StrictLessThan)):
                    delta = -delta
                strict = isinstance(predicate, (sp.StrictGreaterThan, sp.StrictLessThan))
            self.margins.append((delta, strict, key, math_latex(predicate)))
            return
        if isinstance(predicate, sp.Equality) and self._normalize(predicate.lhs-predicate.rhs) == 0:
            return
        raise LoweringError('unsupported_condition', 'The selected predicate cannot be compiled by this explicit runtime.', key)

    def _check_operations(self):
        active = {v['id']: v['balances'] for v in self.model['volumenes']}
        for key in self.replayed.selected:
            node = self.graph.nodes[key]; owner = self.replayed.owners.get(key)
            physical = {'matter': 'materia', 'energy': 'energia'}.get(node.family)
            if physical and owner in active and active[owner][physical] and node.kind in ('balance', 'constraint') and not node.dependent:
                if self._normalize(node.equation.lhs-node.equation.rhs) != 0:
                    raise LoweringError('uncovered_balance', 'An active conservation balance is not represented by the selected rates and reconstructions.', key)
        # Check evaluable parameter/geometry premises in the used ancestry too;
        # data binding is not permission to contradict a declared constitutive
        # premise (for example, independently supplied area and radius).
        used = set()
        def visit(key):
            if key in used:
                return
            used.add(key)
            for parent in self.graph.nodes[key].inputs:
                visit(parent)
        for row in [*self.selection['states'], *self.selection['reconstructions'], *self.algebraic_rows]:
            visit(row['equationId'])
        for key in self.graph.nodes:
            if key not in used:
                continue
            equation = self.graph.nodes[key].equation
            if not isinstance(equation, sp.Equality) or equation.has(sp.Derivative):
                continue
            value = si_magnitude(self._expand(equation.lhs-equation.rhs)).subs(self.parameter_values)
            if value.is_number is True and abs(float(value)) > 1e-9:
                raise LoweringError('inconsistent_parameter_premise', 'Numerical data contradict a replayed algebraic or geometric premise.', key)

        self._check_declared_port_relations(used)

        for key, node in self.graph.nodes.items():
            if not key.startswith('operation.') or not isinstance(node.equation, sp.Equality):
                continue
            residual = self._normalize(node.equation.lhs-node.equation.rhs)
            if residual == 0:
                continue
            numerical = si_magnitude(residual).subs(self.parameter_values)
            if numerical.is_number is True and abs(float(numerical)) <= 1e-12:
                continue
            raise LoweringError('unsupported_operation', 'The recorded operation is not an identity, explicit closure or consequence of the selected rates. General constraints and integral/spatial operators are not lowered.', key)

    def _check_declared_port_relations(self, used):
        """A substituted physical flow remains a datum, not a free premise.

        Read the producer's physical bindings and the actual constitutive rows
        in the selected conservation ancestry. Never reconstruct a port formula
        from configuration flags or replace the selected differential equations.
        """
        from core.balances.material_equations import equation_graph
        relations = {key: self.graph.nodes[key] for key in used
                     if self.graph.nodes[key].family == 'matter'
                     and self.graph.nodes[key].rule == 'constitutive_relation'}
        if not relations:
            return
        bindings = {}
        for volume in self.model['volumenes']:
            if any(self.replayed.owners.get(key) == volume['id'] for key in relations):
                _, _, physical = equation_graph(self.model, volume['id'], volume['supuestos']['materia'])
                bindings.update(physical)
        streams = {stream['id']: stream for stream in self.model['corrientes']}
        for key, node in relations.items():
            quantity = node.equation.lhs
            binding = bindings.get(quantity)
            if binding is None or binding[0] != 'stream':
                continue
            matter = streams[binding[1]]['materia']
            if matter['modo'] != 'por_componente' or matter['base'] != 'masica':
                raise LoweringError('unsupported_physical_binding',
                    'A substituted component port relation currently requires a declared component mass-flow datum.', key)
            data_id = matter['caudalIds'][str(binding[2])]
            expected = self._datum(data_id, self._dim(quantity))
            actual = si_magnitude(self._normalize(node.equation.rhs)).subs(self.parameter_values)
            if actual.is_number is not True:
                raise LoweringError('unsupported_physical_binding',
                    'The substituted port relation must resolve to a constant before its declared datum can be certified: '+data_id, key)
            if not math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12):
                raise LoweringError('inconsistent_physical_binding',
                    'The declared stream datum contradicts the replayed port relation: '+data_id, key)

    def _conservation_checks(self):
        checks = []
        for row in self.selection['checks']:
            key = row['equationId']; equation = self._equation(key).equation
            left = self._expand(equation.lhs).doit()
            derivatives = {sp.Derivative(q, self.time): q for q in self.states}
            inventory = left.xreplace(derivatives)
            if inventory.has(sp.Derivative) or self._normalize(equation.lhs-equation.rhs) != 0:
                raise LoweringError('unsupported_conservation', 'Select a sum of retained inventory rates consistent with the ODE.', key)
            for q in self.states:
                if sp.diff(inventory, q).has(*self.states, self.time):
                    raise LoweringError('unsupported_conservation', 'Integrated budget checks require a constant linear combination of inventories.', key)
            scale = self._datum(row['scaleDataId'], self._dim(inventory))
            if scale <= 0:
                raise LoweringError('invalid_scale', 'A conservation scale must be positive.', key)
            checks.append((row, inventory, self._expand(equation.rhs), scale))
        return checks

    def _ast(self, expression):
        if expression in self.ids:
            return {'tipo': 'simbolo', 'id': self.ids[expression]}
        if expression.is_Integer:
            return {'tipo': 'numero', 'valor': int(expression)}
        if expression.is_Rational:
            return {'tipo': 'cociente', 'numerador': self._ast(sp.Integer(expression.p)), 'denominador': self._ast(sp.Integer(expression.q))}
        if expression.is_number and expression.is_real and expression.is_finite:
            return {'tipo': 'numero', 'valor': float(expression)}
        if expression.is_Add or expression.is_Mul:
            return {'tipo': 'suma' if expression.is_Add else 'producto', 'argumentos': [self._ast(arg) for arg in expression.args]}
        if expression.is_Pow:
            return {'tipo': 'potencia', 'base': self._ast(expression.base), 'exponente': self._ast(expression.exp)}
        supported = {sp.exp: 'exp', sp.log: 'log', sp.sin: 'sin', sp.cos: 'cos', sp.Abs: 'abs'}
        if expression.func in supported:
            return {'tipo': 'funcion', 'nombre': supported[expression.func], 'argumentos': [self._ast(arg) for arg in expression.args]}
        raise LoweringError('unsupported_expression', 'No numerical lowering for the retained expression: ' + str(expression))

    def _lower_model(self):
        study = self.model['estudio']
        if study is None or study['tipo'] != 'temporal':
            raise LoweringError('missing_study', 'Declare the numerical temporal study in Solve.')
        data = copy.deepcopy(self.model['datos'])
        symbols = [_symbol(self.ids[self.time], 'tiempo', {'T': 1})]
        equations = []; conditions = []; observables = []
        def datum(key, value, unit):
            data[key] = {'magnitud': 'compiled value', 'funcion': 'parametro',
                'declaracion': {'texto': str(value), 'unidad': unit},
                'origen': {'propietarioId': 'matematico', 'ruta': key}}
        expressions = [*self.rates.values(), *(e for _, e in self.reconstructed),
                       *(e for _, inventory, rate, _ in self.checks for e in (inventory, rate))]
        if self.algebraic_block is not None:
            expressions.extend([*self.runtime_rates, *self.algebraic_block.forcing])
        for atom in sorted(set().union(*(e.atoms(UnitBasis) for e in expressions)), key=sp.srepr):
            identity = 'si_unit_' + atom.base
            self.ids[atom] = identity
            dim = {atom.base: 1}
            symbols.append(_symbol(identity, 'constante', dim))
            datum('matematico.'+identity, 1, units.unidad_SI(dim))
        for q, symbol in self.parameter_symbols.items():
            identity = self.ids[symbol]
            if any(s['id'] == identity for s in symbols):
                continue
            symbols.append(_symbol(identity, 'parametro', self._dim(q)))
            datum('matematico.'+identity, self.parameter_values[symbol], self._unit(q))
        if self.nonlinear:
            for q in self.algebraic_quantities:
                symbols.append(_symbol(self.ids[q], 'campo', self._dim(q)))
                symbols[-1]['dependeDe'] = [self.ids[self.time]]
        symbols.append(_symbol('final_time', 'parametro', {'T': 1}))
        datum('matematico.final_time', self._datum(study['tiempoId'], {'T': 1}), 's')
        for index, q in enumerate(self.states):
            identity = self.ids[q]; symbols.append(_symbol(identity, 'campo', self._dim(q)))
            symbols[-1]['dependeDe'] = [self.ids[self.time]]
            initial_id = 'initial_' + identity
            symbols.append(_symbol(initial_id, 'parametro', self._dim(q)))
            datum('matematico.'+initial_id, self.initial_values[q], self._unit(q))
            equations.append({'id': self.selection['states'][index]['equationId'],
                'izquierda': {'tipo': 'derivada', 'expresion': {'tipo': 'simbolo', 'id': identity}, 'respecto': self.ids[self.time], 'orden': 1},
                'derecha': self._ast(self.rates[sp.Derivative(q, self.time)])})
            conditions.append({'id': initial_id, 'tipo': 'inicial', 'dominioId': 'time',
                'ecuacion': {'id': initial_id, 'izquierda': {'tipo': 'simbolo', 'id': identity},
                            'derecha': {'tipo': 'simbolo', 'id': initial_id}}})
        for index, (row, inventory, rate, _) in enumerate(self.checks):
            identity = 'budget_' + str(index)
            symbols.append(_symbol(identity, 'campo', self._dim(inventory))); symbols[-1]['dependeDe'] = [self.ids[self.time]]
            equations.append({'id': identity, 'izquierda': {'tipo': 'derivada', 'expresion': {'tipo': 'simbolo', 'id': identity}, 'respecto': self.ids[self.time], 'orden': 1}, 'derecha': self._ast(rate)})
            conditions.append({'id': 'initial_'+identity, 'tipo': 'inicial', 'dominioId': 'time', 'ecuacion': {'id': 'initial_'+identity, 'izquierda': {'tipo': 'simbolo', 'id': identity}, 'derecha': {'tipo': 'numero', 'valor': 0}}})
        for row, expression in self.reconstructed:
            q = self._quantity(row['quantityId'])
            observables.append({'id': row['quantityId'], 'nombre': str(q), 'unidadSI': self._unit(q), 'expresion': self._ast(expression)})
        restrictions = [{'expresion': self._ast(expression), 'tipo': 'no_negativo', 'descripcion': label}
                        for expression, _, _, label in self.margins]
        mathematical = {'id': self.model['id']+'.derived', 'revision': 1, 'simbolos': symbols,
            'funciones': [], 'ecuaciones': equations, 'dominios': [{'id': 'time', 'variableId': self.ids[self.time], 'desde': {'tipo': 'numero', 'valor': 0}, 'hasta': {'tipo': 'simbolo', 'id': 'final_time'}}], 'condiciones': conditions}
        return {'formato': 'rage.modelo', 'version': 0, 'id': self.model['id'], 'nombre': self.model['nombre'],
            'componentes': [], 'termodinamica': {'paquetes': []}, 'volumenes': [], 'corrientes': [], 'intercambios': [],
            'datos': data, 'matematico': mathematical, 'estudio': copy.deepcopy(study), 'motores': {},
            'procedencia': {'tipo': 'nuevo'}, 'restricciones': restrictions, 'observables': observables}

    def _select_scaling(self):
        from core.adimensionalizacion.nucleo import procesar
        from .transformed import TransformedSystem
        mat = self.lowered['matematico']; retained = {self.ids[self.time], *(self.ids[q] for q in self.states)}
        # Auxiliary budget states use the same positive scale as their declared
        # inventory reference; they remain diagnostics, never dependent totals.
        scale_data = dict(self.selection['scaling'])
        for index, (row, _, _, _) in enumerate(self.checks):
            scale_data['budget_'+str(index)] = row['scaleDataId']; retained.add('budget_'+str(index))
        form = {'id': 'derived-scaling', 'nombre': 'Multiplicative derived formulation', 'padreId': None,
            'modeloRevision': mat['revision'], 'presentacion': 'factorizada', 'objetivos': [],
            'escalas': [{'simboloId': s['id'], 'transformar': True, 'nuevoNombre': 'scaled_'+s['id'],
                        'dimension': s['dimension'], 'valor': {'tipo': 'libre'}} for s in mat['simbolos'] if s['id'] in retained]}
        document = {'formato': 'adimensionalizacion', 'version': 2, 'id': self.model['id'], 'nombre': self.model['nombre'], 'modelo': mat, 'formas': [form], 'activaId': form['id']}
        response = procesar({'formato': 'adimensionalizacion.solicitud', 'version': 1, 'operacion': 'adimensionalizar',
            'documento': document, 'formaId': form['id'], 'opciones': {'presupuesto': 20}})
        if response['estado'] != 'correcto':
            raise LoweringError('unsupported_scaling', 'The existing multiplicative scaling engine did not certify this derived ODE.')
        body = response['formulaciones'][0]; free = {}
        for scale_id in body['libres']:
            declaration = next(s for s in body['simbolos'] if s['id'] == scale_id)
            source = declaration['variableId']; data = self.model['datos'][scale_data[source]]['declaracion']
            spec = units.interpretar(data['unidad'])
            value = self._datum(scale_data[source], spec['dimension'])
            if value <= 0:
                raise LoweringError('invalid_scale', 'Multiplicative scales must be positive.')
            free[scale_id] = {'value': float(parse_expression(data['texto'], {})), 'unit': data['unidad']}
        self.lowered['motores']['adimensionalizacion'] = {'version': 2, 'formas': [form], 'activaId': form['id'],
            'execution': {'version': 1, 'objectives': [], 'freeScales': free}}
        self.scaled = TransformedSystem(self.lowered)

    def _validate_initial(self):
        for function, strict, key, _ in self.runtime_guards:
            value = float(function(0.0, self.initial_state))
            if not math.isfinite(value) or value < 0 or strict and value == 0:
                raise LoweringError('invalid_initial_domain', 'Initial data violate a selected validity condition.', key)
        try:
            self.rhs(0.0, self.initial_state)
        except Detencion as error:
            failure = LoweringError(error.codigo, str(error))
            if self.nonlinear and getattr(error, 'diagnostics', None):
                failure.diagnostics = [{**row, 'stage': 'initialization'} for row in error.diagnostics]
            raise failure from error

    def _physical_admission(self):
        self.hydraulic_guards = []
        def physical_quantity(name):
            matches = {q for q in self.quantities.values() if str(q) == name}
            if len(matches) != 1:
                raise LoweringError('missing_physical_binding', 'The declared physical quantity is not unique in the replayed graph: ' + name)
            return matches.pop()
        def check_binding(expression, data_id):
            expression = physical_quantity(str(expression))
            expected = self._datum(data_id, self._dim(expression))
            actual = self._expand(expression).subs(self.parameter_values)
            if actual.is_number is not True or not math.isclose(float(actual), float(expected), rel_tol=1e-12, abs_tol=1e-12):
                raise LoweringError('inconsistent_physical_binding', 'The graph parameter must use the same declared physical datum: ' + str(expression))
        for volume in self.model['volumenes']:
            closure = volume['termodinamica']
            if closure.get('supuesto') != 'u_lineal' or not volume['balances']['energia']:
                continue
            owner = volume['id']; parameters = closure['parametros']
            for symbol, key in [('caloric_capacity', 'cId'), ('T_reference', 'TRefId'), ('u_reference', 'uRefId')]:
                check_binding(sp.Symbol(symbol+'__'+owner, real=True), parameters[key])
        if self.model['motores'].get('hydraulicNetwork') is None:
            if any(v['balances']['momento'] for v in self.model['volumenes']):
                raise LoweringError('unsupported_momentum_regime', 'Active momentum needs an admitted reduced physical regime; general momentum/DAE execution is not supported.')
            return
        from .hydraulics import validate_admission
        config = validate_admission(self.model)
        medium = config['medium']
        viscosity = float(self._datum(medium['viscosityId'], {'M': 1, 'L': -1, 'T': -1}))
        density = self._datum(medium['densityId'], {'M': 1, 'L': -3})
        minimum = float(self._datum(medium['minimumPressureId'], {'M': 1, 'L': -1, 'T': -2}))
        if viscosity <= 0 or density <= 0 or minimum < 0:
            raise LoweringError('invalid_medium', 'The admitted medium needs positive density/viscosity and a nonnegative absolute-pressure limit.')
        for storage in config['storages']:
            owner = storage['volumeId']
            inventories = [i for i, row in enumerate(self.selection['states']) if self.replayed.owners[row['equationId']] == owner and self._dim(self.states[i]) == {'M': 1}]
            if len(inventories) != 1 or self.initial_state[inventories[0]] <= 0:
                raise LoweringError('invalid_initial_inventory', 'Each storage requires its retained positive initial material inventory.')
            for symbol, key in [('A_v', storage['areaId']), ('rho', medium['densityId']), ('g', config['gravityId'])]:
                check_binding(sp.Symbol(symbol+'__'+owner, real=True), key)
            check_binding(sp.Symbol('z_0__'+owner, real=True), storage['floorElevationId'])
            check_binding(sp.Function('p_r__'+owner)(self.time), storage['surfacePressureId'])
        for path in config['paths']:
            owner = path['volumeId']
            for symbol, key in [('A', path['areaId']), ('L', path['lengthId']), ('rho', medium['densityId']), ('mu', medium['viscosityId'])]:
                check_binding(sp.Symbol(symbol+'__'+owner, real=True), key)
            check_binding(sp.Symbol('z1__'+owner, real=True), path['inletElevationId'])
            check_binding(sp.Symbol('z2__'+owner, real=True), path['outletElevationId'])
            check_binding(sp.Function('drive__'+owner)(self.time), path['driveId'])
            if path['flow']['kind'] != 'dynamic':
                raise LoweringError('unsupported_hydraulic_selection', 'This derived selection requires the retained dynamic path flow; prescribed-flow pressure recovery is a separate adapter.')
            flows = [i for i, row in enumerate(self.selection['states']) if self.replayed.owners[row['equationId']] == owner and self._dim(self.states[i]) == {'M': 1, 'T': -1}]
            if len(flows) != 1:
                raise LoweringError('unsupported_hydraulic_selection', 'Select the derived path-flow state identified by the momentum graph.')
            pressures = []
            for end in ('inletPressure', 'outletPressure'):
                boundary = path[end]
                if boundary['kind'] != 'storage':
                    raise LoweringError('unsupported_pressure_boundary', 'Derived hydraulic execution currently uses the selected storage-pressure reconstructions.')
                storage = next(s for s in config['storages'] if s['volumeId'] == boundary['volumeId'])
                port_id = path['inletElevationId' if end == 'inletPressure' else 'outletElevationId']
                if self._datum(port_id, {'L': 1}) != self._datum(storage['floorElevationId'], {'L': 1}):
                    raise LoweringError('unsupported_pressure_boundary', 'This selected reduced graph evaluates material ports at their storage floors; another port needs its corresponding derived pressure reconstruction.')
                candidates = [(row, expression) for row, expression in self.reconstructed if self.replayed.owners[row['equationId']] == boundary['volumeId'] and self._dim(self._quantity(row['quantityId'])) == {'M': 1, 'L': -1, 'T': -2}]
                if len(candidates) != 1:
                    raise LoweringError('missing_pressure_reconstruction', 'Select one absolute port-pressure reconstruction per storage.')
                pressures.append(self.numeric._compilar(self._ast(candidates[0][1]), 'derived port pressure'))
            diameter = float(self._datum(path['diameterId'], {'L': 1}))
            area = float(self._datum(path['areaId'], {'L': 2}))
            if diameter <= 0 or not math.isclose(area, math.pi*diameter**2/4, rel_tol=1e-8):
                raise LoweringError('inconsistent_geometry', 'The circular diameter and area must agree.')
            radius = self._expand(physical_quantity('R__'+owner)).subs(self.parameter_values)
            if radius.is_number is not True or radius <= 0 or not math.isclose(2*float(radius), diameter, rel_tol=1e-8):
                raise LoweringError('inconsistent_geometry', 'The positive outer-radius datum must agree with the circular diameter.')
            self.hydraulic_guards.append((flows[0], pressures, diameter, viscosity, minimum))

    def _report(self):
        from .presentation import solution_strategy
        rows = [{**row, 'ownerId': self.replayed.owners.get(row['id'], 'system'), 'current': row['id'] in self.replayed.selected} for row in self.graph.rows()]
        quantities = {**catalog(self.graph, self.replayed.units), **self.replayed.introduced}
        development = {'format': 'rage.equation-workbench-report', 'version': 1, 'modelId': self.model['id'],
            'definition': self.replayed.definition, 'findings': [], 'equations': rows,
            'quantities': [{'id': key, 'input': 'q_'+str(index+1), 'latex': math_latex(q, self.graph.names),
                           'unit': _known_unit(q, self.replayed.units), 'coordinate': isinstance(q, sp.Symbol), 'name': str(q)}
                          for index, (key, q) in enumerate(quantities.items())],
            'execution': {'supported': True, 'reason': 'The selected derived graph has an explicit numerical lowering with runtime validity checks.'}}
        report = {'format': 'rage.compilation', 'version': 1, 'formulation': 'physical',
            'sourceModelId': self.model['id'], 'sourceRevision': 1,
            'signature': hashlib.sha256(json.dumps([SOURCE_REVISION, self.selection,
                {key: value['declaracion'] for key, value in self.model['datos'].items()}, self.model['estudio']], sort_keys=True).encode()).hexdigest(),
            'method': self.method, 'closureStrategy': 'declared_assumption',
            'variables': [{'id': self.ids[q], 'sourceId': self.ids[q], 'role': 'differential', 'unit': self._unit(q),
                'physicalUnit': self._unit(q), 'scaleSI': 1, 'absoluteTolerance': float(self.numeric.atol[i])} for i, q in enumerate(self.states)],
            'equations': self.lowered['matematico']['ecuaciones'][:len(self.states)],
            'domains': self.lowered['restricciones'], 'conditions': self.lowered['matematico']['condiciones'],
            'direct': [], 'inverse': [], 'eliminatedVariables': [row['quantityId'] for row in self.selection['reconstructions']],
            'auxiliaryStates': len(self.checks), 'auxiliaryPurpose': 'Integrated net-rate budgets; dependent totals are reconstructed, never integrated as physical states.',
            'time': {'id': self.ids[self.time], 'sourceId': self.ids[self.time], 'scaleSI': 1, 'finalTime': self.tf, 'physicalFinalTime': self.tf},
            'matrix': 'The existing common RK45/BDF runtime integrates the lowered explicit AST; BDF estimates its time-step Jacobian.',
            'limits': 'Execution is conditional on the retained interval identities and local-field premises of the replayed reduction. Runtime inequalities are enforced on explicit states and data; pointwise certification of eliminated spatial fields, general DAE and phase-equilibrium execution are outside this adapter.',
            'parameters': [{k: v for k, v in p.items() if k != 'dataId'} for p in self.parameter_records],
            'systemEquations': [{'id': row['id'], 'family': row['family'].title(), 'latex': row['latex']} for row in rows if row['id'] in {s['equationId'] for s in self.selection['states']}],
            'equationWorkbench': development,
            'derivedExecution': {'version': self.selection['version'], 'sourceSignature': self.selection['sourceSignature'],
                'selection': self.selection, 'proofConditions': self.proof_conditions,
                'runtimeConditions': [{'equationId': key, 'strict': strict, 'latex': label} for _, strict, key, label in self.margins],
                'reconstructions': self.selection['reconstructions']}}
        if self.algebraic_block is not None and not self.nonlinear:
            block = self.algebraic_block
            report['derivedExecution']['algebraicBlock'] = {
                'rows': self.algebraic_rows, 'matrixSI': block.numeric.tolist(),
                'determinantSI': block.determinant, 'equilibratedConditionInfinity': block.condition,
                'conditionTest': 'Exact nonzero SI-bound determinant; row/column-equilibrated cond_inf * machine epsilon <= 1e-8.',
                'solve': 'numpy.linalg.solve at every RHS evaluation; componentwise backward error <= 64 machine epsilons.'}
            report['equations'] = [{**row, 'derecha': self._ast(rate)} for row, rate in zip(report['equations'], self.runtime_rates)]
            report['systemEquations'].extend({'id': row['equationId'], 'family': 'Algebraic',
                'latex': math_latex(self._equation(row['equationId']).equation, self.graph.names)} for row in self.algebraic_rows)
            report['matrix'] = 'Constant affine algebraic block solved in SI inside every RHS; common RK45/BDF advances the differential states. Symbolic elimination is used only for equivalence, initialization, guards and ordinary reconstructions.'
        if self.nonlinear:
            report['derivedExecution']['nonlinearBlock'] = {
                'rows': self.algebraic_rows, 'method': 'damped_newton',
                'settings': self.selection['nonlinear'],
                'initialization': {**self.algebraic_block.last, 'stage': 'initialization'},
                'scope': 'Local regular root only; deterministic finite probes reject detected multiple roots, not a global uniqueness certificate.'}
            report['systemEquations'].extend({'id': row['equationId'], 'family': 'Algebraic',
                'latex': math_latex(self._equation(row['equationId']).equation, self.graph.names)} for row in self.algebraic_rows)
            report['matrix'] = 'Damped Newton solves the retained nonlinear block at each RK45/BDF evaluation, including BDF Jacobian probes; no symbolic inverse or fallback.'
        if self.dae:
            report['derivedExecution']['dae'] = self.dae.proof
            report['matrix'] = 'Semi-explicit index-1 DAE: SciPy BDF integrates fixed-initial differential states; the existing damped Newton solves algebraic variables inside every RHS and BDF probe. No residual DAE backend or new dependency.'
        if self.hydraulic_guards:
            report['derivedExecution']['runtimeConditions'].extend([
                {'equationId': self.selection['states'][index]['equationId'], 'strict': False,
                 'latex': r'\mathrm{Re}\leq2100,\quad p_{\mathrm{port}}\geq p_{\min}'}
                for index, _, _, _, _ in self.hydraulic_guards])
        if self.scaled is not None:
            scaling = self.scaled.report
            report.update({key: scaling[key] for key in ('formulation', 'selection', 'direct', 'inverse', 'equivalence', 'time')})
            by_source = {v['sourceId']: v for v in scaling['variables']}
            report['variables'] = [by_source[self.ids[q]] for q in self.states]
            report['equations'] = scaling['equations']
            report['auxiliaryStates'] = len(self.checks) + self.scaled.size
            report['auxiliaryPurpose'] += ' The existing scaling path also integrates the original RHS as independent reconstruction diagnostics.'
        labels = {key: math_latex(q, self.graph.names) for key, q in quantities.items()}
        for q, parameter in self.parameter_symbols.items():
            labels[str(parameter)] = math_latex(q, self.graph.names)
        for atom, identity in self.ids.items():
            if isinstance(atom, UnitBasis):
                labels[identity] = math_latex(atom, self.graph.names)
        for index in range(len(self.checks)):
            labels['budget_'+str(index)] = r'B_{'+str(index+1)+'}'
        if self.scaled is not None:
            for variable in self.scaled.report['variables']:
                labels[variable['id']] = r'\widehat{' + labels[variable['sourceId']] + '}'
            labels[report['time']['id']] = r'\widehat{' + labels[self.ids[self.time]] + '}'
            for symbol in self.scaled.formulation['simbolos']:
                source = symbol.get('variableId')
                if source in labels and symbol['id'] not in labels:
                    labels[symbol['id']] = r'\left(' + labels[source] + r'\right)_{\mathrm{ref}}'
        report['symbolLabels'] = labels
        report['strategy'] = solution_strategy(report, self.model)
        return report

    def _validate_dae_accepted(self, t, state, publication=False):
        try:
            if publication:
                self.dae.conservation(t, state, 'publication')
            else:
                self.dae.accepted(t, state)
        except NonlinearError as error:
            stop = Detencion(error.code, str(error))
            stop.diagnostics = error.diagnostics
            raise stop from error

    def initial(self):
        return self.initial_state.copy()

    def inicial(self):
        return self.initial()

    def rhs(self, t, state):
        if self.nonlinear:
            z, _ = self.solve_algebraic(t, state)
            extended = np.concatenate([state, z])
            try:
                value = np.array([f(t, extended) for f in self.numeric.f])
                if not np.all(np.isfinite(value)):
                    raise ValueError('A retained differential rate is nonfinite.')
            except (ArithmeticError, ValueError) as error:
                failure = NonlinearError('nonlinear_nonfinite', str(error), **self.algebraic_block.location(t, 'runtime'))
                stop = Detencion(failure.code, str(failure))
                stop.diagnostics = [failure.diagnostic]
                raise stop from error
            return value
        for function, strict, key, label in self.runtime_guards:
            if strict:
                margin = float(function(t, state))
                if not math.isfinite(margin) or margin <= 0:
                    raise Detencion('derived_validity', key + ': ' + label)
        if self.algebraic_block is None:
            value = self.numeric.rhs(t, state)
        else:
            algebraic, _ = self.solve_algebraic(t, state)
            extended = np.concatenate([state, algebraic])
            try:
                value = np.array([f(t, extended) for f in self.algebraic_rates] +
                                 [f(t, state) for f in self.numeric.f[len(self.states):]], dtype=float)
            except (ArithmeticError, ValueError) as error:
                raise Detencion('algebraic_rhs_failed', str(error)) from error
        if not np.all(np.isfinite(value)):
            raise Detencion('derived_nonfinite', 'A selected derived rate is non-finite.')
        if self.hydraulic_guards:
            from .hydraulics import check_medium_domain
            for index, pressures, diameter, viscosity, minimum in self.hydraulic_guards:
                check_medium_domain(state[index], value[index], pressures[0](t, state), pressures[1](t, state), diameter, viscosity, minimum)
        return value

    def solve_algebraic(self, t, state):
        if self.nonlinear:
            try:
                if self.dae:
                    self.dae.state_domain(t, state)
                z, norm = self.algebraic_block.evaluate(t, state)
                if self.dae:
                    norm = self.dae.residual(t, state, z)
                return z, norm
            except NonlinearError as error:
                stop = Detencion(error.code, str(error))
                stop.diagnostics = error.diagnostics
                raise stop from error
        try:
            return self.algebraic_block.solve([f(t, state) for f in self.algebraic_forcing])
        except (AffineBlockError, ArithmeticError, ValueError) as error:
            raise Detencion(getattr(error, 'code', 'algebraic_solve_failed'), str(error)) from error

    def stop_from_exception(self, error):
        # Preserve the common integrator's accepted prefix if a block stop
        # escapes a restart/initial-stage evaluation. Do not classify bugs.
        return error if self.algebraic_block is not None and isinstance(error, Detencion) else None

    def firma(self, t, state):
        return None

    def dominio(self, t, state):
        return self.numeric.dominio(t, state)

    def describir_dominio(self, index):
        return self.numeric.describir_dominio(index)

    def prescribed_boundary(self):
        """First excluded zero of a prescribed polynomial validity margin.

        This locates a boundary of the replayed condition, independently of the
        ODE state. State-dependent/nonpolynomial margins retain runtime checks.
        Prefer explicit domains (collected last) over duplicate algebraic guards.
        """
        boundaries = []
        for expression, strict, key, label in reversed(self.margins):
            expression = expression.subs(self.parameter_values)
            if not strict or expression.free_symbols != {self.time} or not expression.is_polynomial(self.time):
                continue
            roots = sp.solveset(expression, self.time, domain=sp.Interval(0, self.tf))
            if not isinstance(roots, sp.FiniteSet):
                continue
            boundaries.extend((float(root), key, label) for root in roots
                              if root.is_real is True and root.is_finite is True and 0 < root <= self.tf)
        return min(boundaries, key=lambda row: row[0]) if boundaries else None


def resolve(model):
    system = DerivedSystem(model)
    return resolve_system(system)


def resolve_system(system):
    """The shared solver protocol; reusable by reference tests without reauthoring."""
    study = system.model['estudio']; runtime = system; initial = system.initial(); final = system.tf
    tolerance = system.numeric.atol
    if system.scaled is not None:
        runtime = system.scaled; initial = runtime.initial(); final = runtime.tf
        tolerance = np.tile(runtime.atol, 2)
        # The existing scaled RHS already maps the original domains; preserve
        # strict derived guards at every physical RHS evaluation as well.
        runtime.physical.rhs = system.rhs
    requested_times = np.linspace(0, final, study['muestras'])
    time_scale = system.scaled.time_scale if system.scaled is not None else 1
    boundary = system.prescribed_boundary()
    integration_final = final
    if boundary is not None:
        # A strict endpoint may have no finite state (e.g. rho at V=0).
        # Retain requested samples strictly before it; never extrapolate a
        # state to the algebraically located boundary or invent an epsilon.
        integration_final = max(float(t) for t in requested_times if t*time_scale < boundary[0])
    trajectory = (integrar(runtime, initial, integration_final, rtol=study['rtol'], atol=tolerance,
                           max_step=final/(study['muestras']-1), metodo=system.method)
                  if integration_final > 0 else Trayectoria(y_fin=initial))
    stop = None
    if boundary is not None and trajectory.detenida is None and trajectory.t_fin == integration_final:
        time, key, condition = boundary
        message = f'Prescribed strict validity boundary at t = {time:.12g} s: {condition}. Only samples before the excluded endpoint are published; no endpoint state is asserted.'
        trajectory.detenida = Detencion('derived_validity', message)
        trajectory.eventos.append(('derived_validity', time/time_scale, None, None, message))
        stop = {'code': 'derived_validity', 'equationId': key, 'condition': condition,
                'time': time, 'lastValidTime': trajectory.t_fin*time_scale}
    times = sorted({float(t) for t in requested_times if t <= trajectory.t_fin} | {trajectory.t_fin})
    raw = [trajectory.y(t) for t in times]
    if system.scaled is not None:
        physical_times = [t*runtime.time_scale for t in times]
        values = [row[:runtime.size]*runtime.state_scales for row in raw]
    else:
        physical_times = times; values = raw
    solved = None
    nonlinear_failure = None
    if system.nonlinear:
        solved = []
        for t, row in zip(physical_times, values):
            try:
                candidate = system.solve_algebraic(t, row)
                if system.dae:
                    system._validate_dae_accepted(t, row, publication=True)
                for _, _, _, function in system.numeric.observables:
                    if not math.isfinite(float(function(t, row))):
                        raise ValueError('A selected reconstruction is nonfinite at publication.')
                solved.append(candidate)
            except (ArithmeticError, ValueError) as error:
                failure = NonlinearError('nonlinear_nonfinite', str(error), **system.algebraic_block.location(t, 'publication'))
                trajectory.detenida = Detencion(failure.code, str(failure))
                nonlinear_failure = [failure.diagnostic]
                break
            except Detencion as error:
                trajectory.detenida = error
                nonlinear_failure = getattr(error, 'diagnostics', [])
                break
        count = len(solved)
        physical_times, values, raw = physical_times[:count], values[:count], raw[:count]
        if nonlinear_failure is None and trajectory.detenida is not None:
            nonlinear_failure = getattr(trajectory.detenida, 'diagnostics', [])
    series = [serie('campo.'+identity, str(q), system._unit(q), ['t'], [float(row[i]) for row in values])
              for i, (identity, q) in enumerate(zip(system.state_ids, system.states))]
    if system.scaled is not None:
        series.extend(serie('transformed.'+system.scaled.fields[i], str(q), '1', ['t'], [float(row[i]) for row in raw])
                      for i, q in enumerate(system.states))
    for key, label, unit, function in system.numeric.observables:
        series.append(serie('observable.'+key, label, unit, ['t'], [float(function(t, row)) for t, row in zip(physical_times, values)]))
    verifications = []
    if system.algebraic_block is not None:
        if solved is None:
            solved = [system.solve_algebraic(t, row) for t, row in zip(physical_times, values)]
        for index, (q, selection) in enumerate(zip(system.algebraic_quantities, system.algebraic_rows)):
            series.append(serie('observable.'+selection['quantityId'], str(q), system._unit(q), ['t'],
                                [float(z[index]) for z, _ in solved]))
        if system.nonlinear:
            for index, selection in enumerate(system.algebraic_rows):
                equation = system._equation(selection['equationId']).equation
                residuals = [system.algebraic_block.residual(t, *row[:system.size], *z)[index]
                             for t, row, (z, _) in zip(physical_times, values, solved)]
                series.append(serie('algebraic.residual.'+selection['equationId'], 'Original algebraic residual',
                                    system._unit(equation.lhs), ['t'], residuals))
        if solved:
            verifications.append({'id': 'algebraic.scaled_residual' if system.nonlinear else 'algebraic.backward_error',
                'valor': max(error for _, error in solved),
                'tolerancia': system.selection['nonlinear']['residualTolerance'] if system.nonlinear else 64*np.finfo(float).eps,
                'descripcion': 'Original SI residual divided by declared row scales; not a thermodynamic certificate.' if system.nonlinear else 'Original SI algebraic residual divided componentwise by |A||z|+|b| at published samples; not a thermodynamic certificate.'})
    for index, (selection, inventory, _, scale) in enumerate(system.checks):
        function = system.numeric._compilar(system._ast(inventory), 'conservation inventory')
        first = function(0.0, system.initial_state)
        if not values:
            continue
        residual = max(abs(float(function(t, row)-first-row[system.size+index])) for t, row in zip(physical_times, values)) / float(scale)
        verifications.append({'id': 'conservation.'+selection['equationId'], 'valor': residual, 'tolerancia': 1e-6,
                              'descripcion': 'Selected inventory change minus its integrated net rate, divided by the declared physical scale.'})
        series.append(serie('budget.'+selection['equationId'], 'Integrated net-rate budget', system._unit(inventory), ['t'], [float(row[system.size+index]) for row in values]))
        series.append(serie('inventory.'+selection['equationId'], 'Reconstructed dependent inventory', system._unit(inventory), ['t'], [float(function(t, row)) for t, row in zip(physical_times, values)]))
    events = [evento(code, 't', t*(system.scaled.time_scale if system.scaled is not None else 1), message)
              for code, t, _, _, message in trajectory.eventos]
    return conjunto(system.model['id'], system.model['nombre'], 'fallido' if not values else 'parcial' if trajectory.detenida else 'resuelto',
        {'motor': 'rage.compilador.derived', 'metodo': system.method, 'firma': system.report['signature'],
         'compilation': system.report, 'pasos': trajectory.pasos, 'rechazos': trajectory.rechazos,
         **({'nonlinearDiagnostics': {'version': 1, 'method': 'damped_newton',
             'sourceSignature': system.selection['sourceSignature'], 'settings': system.selection['nonlinear'],
             'evaluatedSolves': system.algebraic_block.calls, 'lastEvaluation': system.algebraic_block.last,
             'failures': nonlinear_failure or [], 'publishedSamples': len(values),
             'scope': 'Local regular roots; finite probes do not establish global uniqueness.'}} if system.nonlinear else {}),
         **({'daeDiagnostics': system.dae.evidence()} if system.dae else {}),
         **({'stop': stop} if stop is not None else {}),
         **({'mensaje': str(trajectory.detenida)} if trajectory.detenida else {})},
        [eje('t', 'Physical time', 'tiempo', 's', physical_times)], series, events, verifications, modeloId=system.model['id'])
