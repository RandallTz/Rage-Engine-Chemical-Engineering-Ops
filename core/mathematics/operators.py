"""Shared symbolic calculus operators; no physical-law or equipment selection."""
import sympy as sp


class Divergence(sp.Function):
    nargs=1
    @classmethod
    def eval(cls,expression):
        if expression==0:return sp.S.Zero
    def _latex(self,printer):return r'\nabla\!\cdot\left('+printer._print(self.args[0])+r'\right)'


class Gradient(sp.Function):
    nargs=1
    @classmethod
    def eval(cls,expression):
        if expression.is_number:return sp.S.Zero
    def _latex(self,printer):return r'\nabla\left('+printer._print(self.args[0])+r'\right)'


class VolumeIntegral(sp.Function):
    nargs=1
    @property
    def free_symbols(self):
        # Integration binds spatial coordinates. The resulting inventory has
        # time dependence, rather than the local field's spatial arguments.
        return {s for s in self.args[0].free_symbols if str(s) not in ('x','y','z','s')}
    def _eval_derivative(self,symbol):
        return sp.Derivative(self,symbol,evaluate=False)
    def _latex(self,printer):return r'\int_{V(t)} '+printer._print(self.args[0])+r'\,dV'
    @classmethod
    def eval(cls,expression):
        if expression==0:return sp.S.Zero
        if expression.is_Add:return sp.Add(*(cls(term) for term in expression.args))
        coefficient,rest=expression.as_coeff_Mul()
        if coefficient!=1:return coefficient*cls(rest)


class BoundaryFlux(sp.Function):
    nargs=1
    def _latex(self,printer):return r'\oint_{\partial V(t)} \left('+printer._print(self.args[0])+r'\right)\!\cdot\mathbf n\,dA'
    @classmethod
    def eval(cls,expression):
        if expression==0:return sp.S.Zero
        if expression.is_Add:return sp.Add(*(cls(term) for term in expression.args))
        coefficient,rest=expression.as_coeff_Mul()
        if coefficient!=1:return coefficient*cls(rest)


class StateDifferential(sp.Function):
    nargs=1
    def _latex(self,printer):return r'\mathrm d\!\left('+printer._print(self.args[0])+r'\right)'

