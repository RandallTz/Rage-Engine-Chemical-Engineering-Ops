"""Conservative index-one admission and drift checks for nested SciPy BDF.

No residual integrator, index reduction, or new physical equations live here.
"""
import math
import numpy as np
import sympy as sp
from core.mathematics.constants import si_magnitude
from core.solvers.nonlinear import NonlinearError


FUTURE = 'Higher-index or fully implicit systems require a residual DAE solver such as IDA in a future slice; no fallback was used.'


def interval(expression, bounds):
    """Exact interval enclosure of rational arithmetic; unknown is rejection."""
    if expression in bounds:
        return bounds[expression]
    if expression.is_Rational:
        return expression, expression
    if expression.is_Add:
        pairs=[interval(a,bounds) for a in expression.args]
        return sum(p[0] for p in pairs), sum(p[1] for p in pairs)
    if expression.is_Mul:
        lo=hi=sp.S.One
        for arg in expression.args:
            a,b=interval(arg,bounds);values=[lo*a,lo*b,hi*a,hi*b];lo,hi=min(values),max(values)
        return lo,hi
    if expression.is_Pow and expression.exp.is_Integer:
        lo,hi=interval(expression.base,bounds);n=int(expression.exp)
        if n<0:
            if lo<=0<=hi:raise ValueError('A denominator interval includes zero.')
            lo,hi=min(1/lo,1/hi),max(1/lo,1/hi);n=-n
        values=[lo**n,hi**n]
        if n and n%2==0 and lo<=0<=hi:values.append(sp.S.Zero)
        return min(values),max(values)
    raise ValueError('Unsupported exact interval expression: '+str(expression))


def certify_index(residuals, unknowns, bounds):
    if len(residuals)!=len(unknowns) or not unknowns:
        raise NonlinearError('dae_partition_invalid','A square nonempty algebraic partition is required. '+FUTURE)
    if any(e.has(sp.Derivative) for e in residuals):
        raise NonlinearError('dae_implicit_unsupported','Algebraic rows contain derivatives. '+FUTURE)
    determinant=sp.factor(sp.Matrix(residuals).jacobian(unknowns).det())
    if determinant==0:
        raise NonlinearError('dae_index_unsupported','The algebraic Jacobian is identically singular; index one is not established. '+FUTURE)
    try:
        lo,hi=interval(determinant,bounds)
    except (ValueError,TypeError) as error:
        raise NonlinearError('dae_index_not_certified',str(error)+' '+FUTURE) from error
    if lo<=0<=hi:
        raise NonlinearError('dae_index_not_certified','The exact determinant enclosure includes zero on the declared domain. '+FUTURE)
    return {'index':1,'determinant':str(determinant),'determinantBounds':[str(lo),str(hi)],
            'proof':'Exact rational interval enclosure excludes zero on the declared state/algebraic box.'}


class IndexOne:
    def __init__(self, system):
        self.system=system
        self.settings=system.selection['dae']
        self.bounds={}
        for row,q in zip(system.selection['states'],system.states):
            config=self.settings['stateBounds'][row['quantityId']]
            lo,hi=(system._datum(config[key],system._dim(q)) for key in ('lowerDataId','upperDataId'))
            if lo>=hi:raise NonlinearError('dae_bounds_invalid','State bounds must be finite and strictly ordered.')
            self.bounds[q]=(lo,hi)
        for row,q in zip(system.algebraic_rows,system.algebraic_quantities):
            config=system.selection['nonlinear']['variables'][row['quantityId']]
            self.bounds[q]=tuple(system._datum(config[key],system._dim(q)) for key in ('lowerDataId','upperDataId'))
        self.bounds[system.time]=(sp.S.Zero,system._datum(system.model['estudio']['tiempoId'],{'T':1}))
        residuals=[si_magnitude(e).subs(system.parameter_values) for e in system.algebraic_block.forcing]
        provider_proof=getattr(system.algebraic_block,'certify_index',None)
        self.proof=provider_proof(self.bounds) if provider_proof else certify_index(residuals,system.algebraic_quantities,self.bounds)
        self.proof.update(method='scipy_bdf_nested_newton',initialization='fixed_differential_states',
                          driftTolerance=self.settings['driftTolerance'],
                          stateBounds={row['quantityId']:[str(v) for v in self.bounds[q]] for row,q in zip(system.selection['states'],system.states)})
        self.accepted_checks=0;self.max_residual=0.;self.max_conservation=0.

    def failure(self, code, message, t, stage):
        error=NonlinearError(code,message,**self.system.algebraic_block.location(t,stage))
        error.diagnostics=[error.diagnostic]
        raise error

    def state_domain(self,t,state,stage='runtime'):
        lo,hi=self.bounds[self.system.time]
        if not math.isfinite(float(t)) or not float(lo)<=t<=float(hi):
            self.failure('dae_domain','Time left the certified index-one interval.',t,stage)
        for q,value in zip(self.system.states,state):
            lo,hi=self.bounds[q]
            if not math.isfinite(float(value)) or not float(lo)<=value<=float(hi):
                self.failure('dae_domain','A differential state left the certified index-one domain: '+str(q),t,stage)

    def residual(self,t,state,z,stage='runtime'):
        self.state_domain(t,state,stage)
        block=self.system.algebraic_block
        for q,value in zip(self.system.algebraic_quantities,z):
            lo,hi=self.bounds[q]
            if not math.isfinite(float(value)) or not float(lo)<=value<=float(hi):
                self.failure('dae_domain','An algebraic value left the certified index-one domain: '+str(q),t,stage)
        raw=np.asarray(block.residual(float(t),*state[:len(self.system.states)],*z),dtype=float)
        norm=float(np.max(np.abs(raw)/block.residual_scales))
        if not math.isfinite(norm) or norm>self.settings['driftTolerance']:
            self.failure('dae_constraint_drift','Original scaled algebraic residual exceeds the fixed drift tolerance.',t,stage)
        self.max_residual=max(self.max_residual,norm)
        return norm

    def accepted(self,t,state):
        system=self.system
        z,_=system.solve_algebraic(t,state)
        self.residual(t,state,z)
        self.conservation(t,state)
        self.accepted_checks+=1

    def conservation(self,t,state,stage='runtime'):
        system=self.system
        for i,(_,inventory,_,scale) in enumerate(system.checks):
            f=system.numeric._compilar(system._ast(inventory),'DAE conservation')
            drift=abs(float(f(t,state)-f(0,system.initial_state)-state[system.size+i]))/float(scale)
            if not math.isfinite(drift) or drift>1e-6:
                self.failure('dae_conservation_drift','A conservation residual exceeds 1e-6.',t,stage)
            self.max_conservation=max(self.max_conservation,drift)

    def evidence(self):
        return {'version':1,'method':'scipy_bdf_nested_newton','acceptedChecks':self.accepted_checks,
                'maxResidual':self.max_residual,'maxConservation':self.max_conservation,
                'driftTolerance':self.settings['driftTolerance'],
                'scope':'Checked RHS, internal accepted endpoints and freshly solved published samples; no global branch or between-sample certificate.'}
