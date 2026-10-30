"""Retained algebraic graph lowering; no symbolic root or physical dispatch."""
import math
import hashlib
import json
import numpy as np
import sympy as sp

from core.mathematics.constants import si_magnitude, UnitBasis
from core.solvers.nonlinear import solve, NonlinearError
from .compilador import temporal_method
from .explicito import SistemaExplicito


class NonlinearBlock:
    def __init__(self, system, residuals):
        self.system = system
        self.forcing = residuals  # Expressions retained for shared unit/AST traversal.
        self.unknowns = system.algebraic_quantities
        self.config = system.selection['nonlinear']
        variables = self.config['variables']
        self.seed, self.bounds, self.scales = [], [], []
        for row, q in zip(system.algebraic_rows, self.unknowns):
            spec = variables[row['quantityId']]
            values = {key: float(system._datum(data, system._dim(q))) for key, data in spec.items()}
            self.seed.append(values['seedDataId'])
            self.bounds.append([values['lowerDataId'], values['upperDataId']])
            self.scales.append(values['scaleDataId'])
        self.residual_scales = []
        for row in system.algebraic_rows:
            equation = system._equation(row['equationId']).equation
            self.residual_scales.append(float(system._datum(
                self.config['residualScales'][row['equationId']], system._dim(equation.lhs-equation.rhs))))
        if any(s <= 0 for s in self.scales+self.residual_scales) or any(a >= b for a,b in self.bounds):
            raise NonlinearError('nonlinear_invalid_settings', 'Scales must be positive and bounds ordered.')
        self.arguments = [system.time, *system.states, *self.unknowns]
        expressions = [si_magnitude(e).subs(system.parameter_values) for e in residuals]
        for expression in expressions:
            self.validate(expression)
        self.residual = sp.lambdify(self.arguments, expressions, modules='math', cse=True)
        jacobian = sp.Matrix(expressions).jacobian(self.unknowns)
        self.jacobian = sp.lambdify(self.arguments, list(jacobian), modules='math', cse=True)
        self.conditions = []
        self.last = None
        self.calls = 0
        # Polynomial ideal reduction checks consequences of the retained rows;
        # it never supplies a root or an executable RHS.
        # Include states/time in the polynomial ring, rather than treating them
        # as invertible coefficients. Division by an unproved state factor can
        # otherwise make a constraint appear to be an identity at a singular
        # specialization. Exact parameter binding is part of this compilation.
        dummies = {q: sp.Dummy() for q in self.arguments}
        self.dummies = dummies
        polynomials = [sp.fraction(sp.cancel(e.xreplace(dummies)))[0] for e in expressions]
        self.basis = sp.groebner(polynomials, *dummies.values(), domain='QQ')

    def validate(self, expression):
        if expression in self.arguments or expression.is_Number:
            return
        if expression.is_Add or expression.is_Mul:
            for arg in expression.args:
                self.validate(arg)
            return
        if expression.is_Pow and expression.exp.is_Integer:
            self.validate(expression.base)
            return
        raise NonlinearError('nonlinear_unsupported_expression', 'Only bound arithmetic with integer powers and guarded division is admitted: '+str(expression))

    def is_consequence(self, expression):
        try:
            expression = si_magnitude(expression).subs(self.system.parameter_values)
            numerator = sp.fraction(sp.cancel(expression.xreplace(self.dummies)))[0]
            return self.basis.reduce(numerator)[1] == 0
        except (sp.PolynomialError, ValueError, sp.polys.polyerrors.CoercionFailed):
            return False

    def set_conditions(self, margins):
        self.conditions = []
        for expr, strict, key, label in margins:
            value = si_magnitude(expr).subs(self.system.parameter_values)
            self.validate(value)
            self.conditions.append((sp.lambdify(self.arguments, value, modules='math'), strict, key))

    def evaluate(self, t, state, stage='runtime'):
        args = [float(t), *map(float, state[:len(self.system.states)])]
        def admissible(z):
            for function, strict, _ in self.conditions:
                value = float(function(*args, *z))
                if not math.isfinite(value) or value < 0 or strict and value == 0:
                    return False
            return True
        try:
            z, detail = solve(lambda z: self.residual(*args, *z),
                              lambda z: np.array(self.jacobian(*args, *z)).reshape(len(z),len(z)),
                              self.seed, self.bounds, self.scales, self.residual_scales,
                              residual_tolerance=self.config['residualTolerance'],
                              step_tolerance=self.config['stepTolerance'],
                              max_iterations=self.config['maxIterations'], max_backtracks=self.config['maxBacktracks'],
                              admissible=admissible)
        except NonlinearError as error:
            if stage != 'initialization' and error.code == 'nonlinear_invalid_seed':
                # The immutable seed was admitted at initialization. A changing
                # differential state can make its coupled validity guard fail.
                error = NonlinearError('nonlinear_domain', 'The current state is outside the admitted nonlinear domain.',
                                       **{k:v for k,v in error.diagnostic.items() if k not in ('code','message','terminationReason')})
            error.diagnostic.update(self.location(t, stage))
            error.diagnostics = [error.diagnostic]
            raise error
        self.calls += 1
        self.last = {**detail, **self.location(t, stage)}
        return z, detail['residualNorm']

    def location(self, t, stage):
        from core.modelo.equation_workbench import SOURCE_REVISION
        signature = hashlib.sha256(json.dumps([SOURCE_REVISION, self.system.selection,
            {key: value['declaracion'] for key, value in self.system.model['datos'].items()},
            self.system.model['estudio']], sort_keys=True).encode()).hexdigest()
        return {'stage': stage, 'path': 'motores.derivedExecution.nonlinear',
                'equationIds': [r['equationId'] for r in self.system.algebraic_rows],
                'quantityIds': [r['quantityId'] for r in self.system.algebraic_rows],
                'modelId': self.system.model['id'], 'sourceSignature': self.system.selection['sourceSignature'],
                'formulationSignature': signature,
                'time': float(t)}


class NonlinearRuntime:
    """Use the existing AST evaluator for retained differential/algebraic values.

This does not construct a substitute explicit system. The common integrator
receives DerivedSystem.rhs, which solves the retained block on each evaluation.
"""
    def __init__(self, system):
        self.system = system
        self.campos = [system.ids[q] for q in system.states] + ['budget_'+str(i) for i in range(len(system.checks))]
        self.evaluator = SistemaExplicito.__new__(SistemaExplicito)
        self.evaluator.tiempo = system.ids[system.time]
        self.evaluator.indice = {key: i for i,key in enumerate(self.campos)}
        self.evaluator.indice.update({system.ids[q]: len(self.campos)+i for i,q in enumerate(system.algebraic_quantities)})
        self.evaluator.valores = {system.ids[q]: float(value) for q,value in system.parameter_values.items()}
        self.evaluator.valores.update({identity: 1. for q,identity in system.ids.items() if isinstance(q,UnitBasis)})
        self.indice = self.evaluator.indice
        self.f = [self.raw(system._ast(e)) for e in [*system.rates.values(), *(rate for _,_,rate,_ in system.checks)]]
        self.observables = [(row['quantityId'], str(system._quantity(row['quantityId'])), system._unit(system._quantity(row['quantityId'])),
                             self._compilar(system._ast(expr), 'reconstruction')) for row,expr in system.reconstructed]
        self.dominios = [(self._compilar(system._ast(expr), 'condition'), label) for expr,_,_,label in system.margins]
        study = system.model['estudio']
        self.tf = float(system._datum(study['tiempoId'], {'T':1}))
        if self.tf <= 0:
            raise NonlinearError('nonlinear_invalid_settings', 'A positive time horizon is required.')
        self.metodo = temporal_method(study['metodoSolicitado'])
        dims = [system._dim(q) for q in system.states]+[system._dim(inventory) for _,inventory,_,_ in system.checks]
        a = study['atol']
        self.atol = np.array([a.get('energia',a['cantidad']) if dim=={'M':1,'L':2,'T':-2} else a['cantidad'] for dim in dims])

    def raw(self, expression):
        return self.evaluator._compilar(expression, 'retained nonlinear formulation')

    def _compilar(self, expression, label):
        function = self.raw(expression)
        algebraic = {self.system.ids[q] for q in self.system.algebraic_quantities}
        def uses(e):
            return isinstance(e,dict) and (e.get('tipo')=='simbolo' and e.get('id') in algebraic or any(uses(v) for v in e.values())) or isinstance(e,list) and any(uses(v) for v in e)
        if not uses(expression):
            return function
        def evaluate(t, state):
            z,_ = self.system.solve_algebraic(t,state)
            return function(t,np.concatenate([state,z]))
        return evaluate

    def inicial(self):
        return np.array([float(self.system.initial_values[q]) for q in self.system.states]+[0.]*len(self.system.checks))

    def rhs(self, t, state):
        raise AssertionError('Nonlinear blocks must use the retained DerivedSystem RHS.')

    def dominio(self, t, state):
        return np.array([f(t,state) for f,_ in self.dominios])

    def describir_dominio(self, index):
        return self.dominios[index][1]
