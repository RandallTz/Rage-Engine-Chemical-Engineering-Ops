"""Small, reusable equation graph. Physics supplies laws; operations manipulate them.

Expressions stay as SymPy objects on the server. No persisted text is evaluated.
Each derived node retains its input equations, rule and explicit assumptions.
"""
from dataclasses import dataclass,replace
import sympy as sp
from sympy.printing.latex import LatexPrinter
from .errors import MathematicsError as JournalError
from .validity import finite, expression_guards, calculus_premise, validate


def solve_unique(equation,unknown,names=None):
    """One polynomial solution, retaining factors lost by cancellation.

    Nonpolynomial inversions need domain/branch machinery before admission.
    A single expression returned by solve is not proof of that machinery.
    """
    target=sp.Dummy('isolated')
    changed=equation.xreplace({unknown:target})
    residual=changed.lhs-changed.rhs
    conditions=[]
    try:
        polynomial=sp.Poly(residual,target)
        if polynomial.degree()>0:
            coefficient=polynomial.LC()
            if coefficient.is_nonzero is not True:
                conditions.append(sp.Ne(coefficient,0,evaluate=False))
    except sp.PolynomialError as error:
        raise JournalError('Nonpolynomial isolation requires explicit domain and branch support; this inversion is not yet admitted.') from error
    solutions=sp.solve(changed,target)
    if len(solutions)!=1:
        raise JournalError('Isolation needs one unambiguous branch; declare its domain first.')
    solution=sp.simplify(solutions[0])
    denominator=sp.denom(sp.factor(solution))
    if denominator.is_nonzero is not True:
        conditions.append(sp.Ne(denominator,0,evaluate=False))
    return solution,tuple(dict.fromkeys(conditions))


def math_latex(expression,names=None):
    class NamedPrinter(LatexPrinter):
        def _print(self,expr,**kwargs):
            if names and expr in names:return names[expr]
            return super()._print(expr,**kwargs)
    return NamedPrinter({'symbol_names':names or {}}).doprint(expression)


@dataclass
class EquationNode:
    equation: sp.Basic
    title: str
    rule: str
    inputs: tuple
    assumptions: tuple
    family: str
    kind: str = 'balance'
    dependent: bool = False
    branches: tuple = ()
    predicates: tuple = ()


class EquationGraph:
    def __init__(self, names=None):
        self.nodes={}
        self.names=names or {}
        self.domains={}

    def __deepcopy__(self,memo):
        # SymPy expressions are immutable. Reconstructing an unevaluated Eq
        # during deepcopy can instead collapse it to True/False, losing the law.
        result=type(self)(dict(self.names));memo[id(self)]=result
        result.nodes={key:replace(node) for key,node in self.nodes.items()}
        result.domains=dict(self.domains)
        return result

    def declare_domain(self,id_,source,quantity,domain,reason,declaration=None,**bounds):
        from .domains import DomainPremise,validate_domains
        premise=DomainPremise(quantity,domain,**bounds)
        validate_domains([*self.domains.values(),premise])
        validate(tuple(p for node in self.nodes.values() for p in node.predicates), [*self.domains.values(),premise])
        if id_ in self.nodes or source not in self.nodes:
            raise JournalError('A domain condition has a repeated ID or missing input.')
        inputs=(source,)
        if declaration is not None:
            original,title=declaration
            declared=id_+'.declared'
            if declared in self.nodes:raise JournalError('A domain declaration has a repeated ID.')
            self.nodes[declared]=EquationNode(original.expression,title,'domain_declaration',(source,),
                                             (reason,),self.nodes[source].family,'constraint')
            inputs=(declared,)
        self.nodes[id_]=EquationNode(premise.expression,'Convert interval endpoints to SI' if declaration else 'Declare '+domain+' domain','domain_assumption',inputs,
                                    (reason,math_latex(premise.expression,self.names)),self.nodes[source].family,'constraint')
        self.domains[id_]=premise

    def specialize_domains(self,id_,source,unknown,domain_ids):
        from .domains import singleton_substitutions
        if any(key not in self.domains for key in domain_ids):raise JournalError('Select recorded domain conditions, not arbitrary equations.')
        equation=self.nodes[source].equation
        replacements={quantity:value for quantity,value in singleton_substitutions(unknown,[self.domains[key] for key in domain_ids]).items() if equation.has(quantity)}
        if not replacements:return source
        conditions=self.specialized_predicates((source,),replacements)
        self.add(id_,equation.lhs.xreplace(replacements),equation.rhs.xreplace(replacements),
                 'Apply the recorded singleton parameter case','domain_case',(source,*domain_ids),
                 family=self.nodes[source].family,predicates=conditions)
        self.nodes[id_].dependent=True
        return id_

    def solve_in_domains(self,equation,unknown,domain_ids):
        from .domains import select_polynomial_branch
        if any(key not in self.domains for key in domain_ids):
            raise JournalError('Select recorded domain conditions, not arbitrary equations.')
        solution,conditions,branches=select_polynomial_branch(equation,unknown,[self.domains[key] for key in domain_ids])
        return solution,conditions,branches

    def add(self, id_, lhs, rhs, title, rule='declared_law', inputs=(), assumptions=(), family='mathematics',kind=None,dependent=False,predicates=()):
        if id_ in self.nodes or any(i not in self.nodes for i in inputs):
            raise JournalError('Equation operation has a repeated ID or missing input.')
        if kind is None:kind=self.nodes[inputs[0]].kind if inputs else ('definition' if rule in ('definition','geometry') else 'balance')
        equation=sp.Eq(lhs,rhs,evaluate=False);finite(equation)
        reasons=tuple(a for a in assumptions if isinstance(a,str))
        typed=tuple(dict.fromkeys((*predicates,*(a for a in assumptions if not isinstance(a,str)),*expression_guards(equation))))
        validate((*typed,*(p for source in inputs for p in self.predicates_for(source))),self.domains.values())
        self.nodes[id_]=EquationNode(equation,title,rule,tuple(inputs),reasons,family,kind,dependent,predicates=typed)
        return self.nodes[id_].equation

    def substitute(self, id_, source, substitutions, title, assumptions=(), inputs=()):
        equation=self.nodes[source].equation
        conditions=self.specialized_predicates((source,*inputs),substitutions)
        def apply(expression):
            # Replace typed subexpressions simultaneously. SymPy's .subs can
            # differentiate a temporary substitution for an inventory function,
            # spuriously introducing dm/drho when replacing an integral by m(t).
            changed=sp.sympify(expression.xreplace(substitutions))
            return changed if changed.has(sp.Derivative) else sp.simplify(changed.doit())
        return self.add(id_,apply(equation.lhs),apply(equation.rhs),
                        title,'substitution',(source,*inputs),assumptions,self.nodes[source].family,predicates=conditions)

    def isolate(self, id_, source, unknown, title, assumptions=()):
        equation=self.nodes[source].equation
        solution,nonzero=solve_unique(equation,unknown,self.names)
        conditions=tuple(assumptions)+nonzero
        return self.add(id_,unknown,solution,title,'isolate',(source,),conditions,self.nodes[source].family)

    def integrate(self, id_, source, variable, constant, title, assumptions=()):
        equation=self.nodes[source].equation
        premise=calculus_premise(equation,variable)
        left,right=sp.integrate(equation.lhs,variable),sp.integrate(equation.rhs,variable)+constant
        # SymPy's log(x) antiderivative assumes a complex branch. On a real
        # interval use log|x|, retaining the excluded zero explicitly.
        guards=[]
        def real_logs(expression):
            replacements={}
            for term in sorted(expression.atoms(sp.log),key=sp.srepr):
                argument=term.args[0]
                if argument.is_real is not True:
                    raise JournalError('Integration needs a proved real logarithm argument and its domain.')
                guards.append(sp.Ne(argument,0,evaluate=False))
                replacements[term]=sp.log(sp.Abs(argument))
            return expression.xreplace(replacements)
        left,right=real_logs(left),real_logs(right)
        for expression in (left,right):
            for power in sorted(expression.atoms(sp.Pow),key=sp.srepr):
                if power.exp.is_Rational and power.exp.q%2==0 and power.base.is_nonnegative is not True:
                    guards.append(sp.Ge(power.base,0,evaluate=False))
        return self.add(id_,left,right,title,'integrate',(source,),assumptions,self.nodes[source].family,predicates=(premise,*guards))

    def differentiate(self, id_, source, variable, title):
        equation=self.nodes[source].equation
        return self.add(id_,sp.diff(equation.lhs,variable),sp.diff(equation.rhs,variable),
                        title,'differentiate',(source,),(),self.nodes[source].family,predicates=(calculus_premise(equation,variable),))

    def transform(self,id_,source,function,title,rule,assumptions=()):
        equation=self.nodes[source].equation
        return self.add(id_,function(equation.lhs),function(equation.rhs),title,rule,(source,),assumptions,self.nodes[source].family)

    def combine(self,id_,sources,title,weights=None):
        if not sources or len(set(sources))!=len(sources):raise JournalError('Select distinct input equations.')
        if any(i not in self.nodes for i in sources):raise JournalError('A combined equation references an absent input.')
        families={self.nodes[i].family for i in sources}
        weights=weights or [sp.S.One]*len(sources)
        if len(weights)!=len(sources):raise JournalError('Each equation needs one weight.')
        equations=[self.nodes[i].equation for i in sources]
        return self.add(id_,sp.expand(sum(w*e.lhs for w,e in zip(weights,equations))),sp.expand(sum(w*e.rhs for w,e in zip(weights,equations))),
                        title,'linear_combination',sources,('Derived combination; independence is not established',),families.pop() if len(families)==1 else 'mathematics',dependent=True)

    def conditions_for(self,id_):
        """Transitive validity premises, without promoting a premise to a proof."""
        visited=set();conditions=[]
        def visit(key):
            if key in visited:return
            visited.add(key);node=self.nodes[key]
            for input_id in node.inputs:visit(input_id)
            conditions.extend(node.assumptions)
            conditions.extend(math_latex(predicate) for predicate in node.predicates)
        visit(id_)
        return tuple(dict.fromkeys(conditions))

    def predicates_for(self,id_):
        visited=set();predicates=[]
        def visit(key):
            if key in visited:return
            visited.add(key);node=self.nodes[key]
            for source in node.inputs:visit(source)
            predicates.extend(node.predicates)
        visit(id_)
        return tuple(dict.fromkeys(predicates))

    def specialized_predicates(self,sources,substitutions):
        predicates=tuple(dict.fromkeys(p for source in sources for p in self.predicates_for(source)))
        memberships=tuple(sp.Contains(p.quantity/p.scale,p.allowed,evaluate=False)
                          for p in self.domains.values() if p.quantity in substitutions)
        predicates=(*predicates,*memberships)
        validate(predicates,self.domains.values(),substitutions)
        from .validity import HoldsOnInterval
        # Interval identities remain attached to their original coordinate,
        # even when evaluating their consequence at a boundary point.
        return tuple(p.xreplace(substitutions) for p in predicates if not isinstance(p,HoldsOnInterval))

    def rows(self):
        def latex(eq):return math_latex(eq,self.names)
        return [{'id':id_,'title':node.title,'family':node.family,'latex':latex(node.equation),'kind':node.kind,'dependent':node.dependent,
                 'derivation':{'rule':node.rule,'inputIds':list(node.inputs),
                               'beforeLatex':[latex(self.nodes[i].equation) for i in node.inputs],
                               'assumptions':[*node.assumptions,*(latex(p) for p in node.predicates)],
                               **({'branches':[{'latex':latex(eq),'admitted':admitted} for eq,admitted in node.branches]} if node.branches else {})}} for id_,node in self.nodes.items()]
