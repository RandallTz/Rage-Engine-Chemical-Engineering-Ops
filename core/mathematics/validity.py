"""Typed operation guards; explanatory prose is never evaluated as mathematics."""
import sympy as sp
from sympy.logic.boolalg import Boolean, BooleanFunction
from .errors import MathematicsError
from .constants import si_magnitude


class HoldsOnInterval(BooleanFunction):
    """An explicit premise that an equation holds throughout a coordinate interval.

    This is a premise, not a theorem inferred from equality at one point.
    The interval excludes singularities identified by the other guards.
    """
    nargs = 2

    def _latex(self, printer):
        equation, coordinate = self.args
        return r'\operatorname{HoldsOnInterval}_{' + printer._print(coordinate) + '}(' + printer._print(equation) + ')'


def finite(expression):
    if expression.has(sp.zoo, sp.nan, sp.oo, -sp.oo):
        raise MathematicsError('The derived equation is not finite on its declared domain.')
    if any(node.is_number and node.is_real is False for node in sp.preorder_traversal(expression)):
        raise MathematicsError('The real-valued equation contains a non-real numeric expression.')


def expression_guards(expression):
    """Capture real-domain restrictions before a later operation cancels them."""
    guards=[]
    for power in sorted(expression.atoms(sp.Pow),key=sp.srepr):
        if power.exp.is_negative and power.base.is_nonzero is not True:
            guards.append(sp.Ne(power.base,0,evaluate=False))
        if power.exp.is_Rational and power.exp.q%2==0 and power.base.is_nonnegative is not True:
            guards.append(sp.Ge(power.base,0,evaluate=False))
    for logarithm in sorted(expression.atoms(sp.log),key=sp.srepr):
        if logarithm.args[0].is_positive is not True:
            guards.append(sp.Gt(logarithm.args[0],0,evaluate=False))
    return tuple(dict.fromkeys(guards))


def calculus_premise(equation, coordinate):
    if not isinstance(coordinate, sp.Symbol) or not any(
        coordinate in field.free_symbols for field in equation.atoms(sp.core.function.AppliedUndef)
    ):
        raise MathematicsError('Calculus requires a declared quantity depending on the selected coordinate; a constrained scalar is not an independent coordinate.')
    return HoldsOnInterval(equation, coordinate, evaluate=False)


def validate(predicates, domains=(), substitutions=None):
    """Reject proved contradictions, retaining unresolved guards explicitly.

    Singleton and sign reasoning is exact. General multivariate implication is
    deliberately not claimed. SI projection is used only for the proof.
    """
    from .domains import singleton_substitutions, validate_domains, _unsatisfiable
    domains = tuple(domains)
    sets = validate_domains(domains)
    singleton = singleton_substitutions(None, domains)
    for predicate in predicates:
        if not isinstance(predicate, Boolean):
            raise MathematicsError('Validity conditions must be typed predicates.')
        if isinstance(predicate, HoldsOnInterval):
            continue
        changed = predicate.xreplace(substitutions or {}).xreplace(singleton)
        # A substitution into a guard can itself make its expression undefined.
        if changed.has(sp.zoo, sp.nan):
            raise MathematicsError('A substitution makes an inherited validity condition undefined.')
        changed = si_magnitude(changed).doit()
        if changed is sp.S.false:
            raise MathematicsError('The operation contradicts an inherited validity condition or recorded domain.')
        if changed is sp.S.true:
            continue
        relevant = tuple(premise for premise in domains if changed.has(premise.quantity))
        if relevant and isinstance(changed, sp.Unequality):
            context = sp.And(*(premise.predicate for premise in relevant))
            if sp.ask(sp.Q.zero(changed.lhs-changed.rhs), context) is True:
                raise MathematicsError('A required nonzero condition contradicts a recorded domain.')
        parameters = changed.free_symbols
        if len(parameters) == 1:
            parameter = next(iter(parameters))
            # reduce_inequalities accepts relations, not unevaluated Contains.
            # Passing a membership atom to it can falsely report unsatisfiable.
            relational=changed.replace(lambda node:isinstance(node,sp.Contains) and hasattr(node.args[1],'as_relational'),
                                       lambda node:node.args[1].as_relational(node.args[0]))
            if relational.has(sp.Contains):continue
            if parameter in sets and _unsatisfiable(sp.And(sets[parameter].as_relational(parameter), relational), parameter) is True:
                raise MathematicsError('The validity condition contradicts the recorded interval.')
