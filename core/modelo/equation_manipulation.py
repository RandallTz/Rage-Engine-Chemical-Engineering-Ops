"""Compatible physical adapter for the equipment-independent mathematical graph."""
from core.mathematics.graph import EquationGraph as MathematicalGraph, EquationNode, math_latex


class EquationGraph(MathematicalGraph):
    """Preserve the historical default family for existing physical producers."""
    def add(self,id_,lhs,rhs,title,rule='declared_law',inputs=(),assumptions=(),family='momentum',kind=None,dependent=False,predicates=()):
        return super().add(id_,lhs,rhs,title,rule,inputs,assumptions,family,kind,dependent,predicates)


__all__=['EquationGraph','EquationNode','math_latex']
