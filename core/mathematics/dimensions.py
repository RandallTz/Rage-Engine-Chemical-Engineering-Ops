"""Dimensional algebra and safe arithmetic for explicitly declared quantities."""
import hashlib
from functools import lru_cache
import sympy as sp
from core import expresiones_motor as expressions
from core.unidades import interpretar
from .errors import MathematicsError as JournalError


def known_unit(expression,units):
    if expression in units:return units[expression]
    if isinstance(expression,sp.core.function.AppliedUndef):
        for quantity,unit in units.items():
            if isinstance(quantity,sp.core.function.AppliedUndef) and quantity.func==expression.func:return unit
    return None


@lru_cache(maxsize=16384)
def _quantity_atoms(expression):
    return frozenset(s for s in expression.atoms(sp.Symbol,sp.Function,sp.Derivative)
        if isinstance(s,(sp.Symbol,sp.Derivative)) or s.func.__name__ not in
        ('VolumeIntegral','BoundaryFlux','Divergence','Gradient','StateDifferential'))


@lru_cache(maxsize=32768)
def _quantity_identity(expression):
    text=sp.srepr(expression)
    return text,'x'+hashlib.sha256(text.encode()).hexdigest()[:10]


def catalog(graph,units):
    from .preparation import enabled
    atoms = _quantity_atoms if enabled() else _quantity_atoms.__wrapped__
    identity = _quantity_identity if enabled() else _quantity_identity.__wrapped__
    quantities=set().union(*(atoms(node.equation) for node in graph.nodes.values()))
    quantities.update(units)
    ordered=sorted(quantities,key=lambda q:identity(q)[0])
    return {identity(q)[1]:q for q in ordered}


def dimension(expression,units,unit_resolver=known_unit):
    def infer(value,local_units):return dimension(value,local_units,unit_resolver)
    from .constants import UnitBasis
    if isinstance(expression,UnitBasis):return {expression.base:1}
    if expression==0:return None
    known=unit_resolver(expression,units)
    if known:return interpretar(known)['dimension']
    if expression.is_number:return {}
    from .operators import StateDifferential
    if isinstance(expression,StateDifferential):return infer(expression.args[0],units)
    if expression.func==sp.Abs:return infer(expression.args[0],units)
    if expression.func in (sp.Min,sp.Max):
        # Saturation (Demo 0.3 C1): every argument carries the same dimension.
        dimensions=[infer(term,units) for term in expression.args]
        known=[d for d in dimensions if d is not None]
        if any(d!=known[0] for d in known):raise JournalError('Arguments of min/max have incompatible dimensions.')
        return known[0] if known else None
    if isinstance(expression,sp.Sum):return infer(expression.function,units)
    if isinstance(expression,sp.Integral):
        result=dict(infer(expression.function,units) or {})
        for limit in expression.limits:
            for base,power in (infer(limit[0],units) or {}).items():result[base]=result.get(base,0)+power
        return {base:power for base,power in result.items() if power}
    if expression.func in (sp.sin,sp.cos,sp.tan,sp.cot,sp.exp,sp.log):
        if infer(expression.args[0],units):raise JournalError('This function requires a dimensionless argument.')
        return {}
    if isinstance(expression,sp.Subs):
        local_units=dict(units)
        for variable,point in zip(expression.variables,expression.point):
            unit=unit_resolver(point,units)
            if unit is None:raise JournalError('A substituted derivative argument needs a declared unit.')
            local_units[variable]=unit
        return infer(expression.expr,local_units)
    from .operators import VolumeIntegral,BoundaryFlux,Divergence,Gradient
    if isinstance(expression,(VolumeIntegral,BoundaryFlux,Divergence,Gradient)):
        result=dict(infer(expression.args[0],units) or {})
        result['L']=result.get('L',0)+(3 if isinstance(expression,VolumeIntegral) else 2 if isinstance(expression,BoundaryFlux) else -1)
        return {k:v for k,v in result.items() if v}
    from .operators import BoundaryTrace,NormalDerivative,NormalComponent
    if isinstance(expression,(BoundaryTrace,NormalComponent)):return infer(expression.args[0],units)
    if isinstance(expression,NormalDerivative):
        # du/dn = n.grad(u): one inverse length, whatever the coordinate's unit.
        inner=infer(expression.args[0],units)
        if inner is None:return None
        result=dict(inner);result['L']=result.get('L',0)-1
        return {k:v for k,v in result.items() if v}
    if isinstance(expression,sp.Derivative):
        result=dict(infer(expression.expr,units) or {})
        for variable,count in expression.variable_count:
            for key,power in (infer(variable,units) or {}).items():result[key]=result.get(key,0)-count*power
        return {k:v for k,v in result.items() if v}
    if expression.is_Add:
        dimensions=[infer(term,units) for term in expression.args if term!=0]
        if any(d!=dimensions[0] for d in dimensions):raise JournalError('Terms of a sum have incompatible dimensions.')
        return dimensions[0] if dimensions else None
    if expression.is_Mul:
        result={}
        for term in expression.args:
            for key,power in (infer(term,units) or {}).items():result[key]=result.get(key,0)+power
        return {k:v for k,v in result.items() if v}
    if expression.is_Pow and expression.exp.is_number:return {k:v*expression.exp for k,v in (infer(expression.base,units) or {}).items() if v*expression.exp}
    raise JournalError('A quantity has no declared dimension. Declare its unit before introducing this relation.')


def parse_expression(text,quantities,conditions=None,units=None,unit_resolver=known_unit):
    def infer(value,local_units):return dimension(value,local_units,unit_resolver)
    tree=expressions.analizar(text,list(quantities))
    def convert(node):
        if node[0]=='num':return sp.Rational(str(node[1]))
        if node[0]=='var':return quantities[node[1]]
        name=node[1];args=[convert(n) for n in node[2]]
        # Check the input tree before SymPy cancels it. An invalid sum such
        # as mass + time - time must not acquire a valid unit by simplification.
        if units is not None and name in ('+','-'):
            a,b=(infer(arg,units) for arg in args)
            if a is not None and b is not None and a!=b:raise JournalError('Terms of a sum have incompatible dimensions.')
        if units is not None and name=='^':
            if infer(args[1],units):raise JournalError('An exponent must be dimensionless.')
            if not args[1].is_number:raise JournalError('This arithmetic editor requires a numeric exponent.')
        if name=='+':return args[0]+args[1]
        if name=='-':return args[0]-args[1]
        if name=='*':return args[0]*args[1]
        if name=='/' or name=='^' and args[1].is_negative:
            denominator=args[1] if name=='/' else args[0]
            if denominator.is_zero is True:raise JournalError('Division by zero is not defined.')
            if conditions is not None and denominator.is_nonzero is not True:conditions.append(sp.Ne(denominator,0,evaluate=False))
        if name=='/':return args[0]/args[1]
        if name=='^':
            # Preserve the real-root domain even if later arithmetic cancels
            # the power, for example (sqrt(x))^2 -> x.
            if conditions is not None and args[1].is_Rational and args[1].q%2==0 and args[0].is_nonnegative is not True:
                conditions.append(sp.Ge(args[0],0,evaluate=False))
            return args[0]**args[1]
        if name=='neg':return -args[0]
        if name in ('sqrt','exp','log'):
            # Elementary functions of declared relations (30 October 2026). The
            # real-domain premise is recorded as a typed condition, never assumed.
            value=args[0]
            if units is not None and name in ('exp','log') and infer(value,units):
                raise JournalError('exp and log require a dimensionless argument; divide by a declared reference.')
            if name=='sqrt':
                if value.is_negative is True:raise JournalError('sqrt of a negative quantity is not real.')
                if conditions is not None and value.is_nonnegative is not True:conditions.append(sp.Ge(value,0,evaluate=False))
                return sp.sqrt(value)
            if name=='log':
                if value.is_positive is not True and value.is_nonpositive is True:raise JournalError('log requires a positive argument.')
                if conditions is not None and value.is_positive is not True:conditions.append(sp.Gt(value,0,evaluate=False))
                return sp.log(value)
            return sp.exp(value)
        if name in ('min','max'):
            # Saturating functions (Demo 0.3 C1). The arguments are compared,
            # so they must share one dimension; checked before SymPy can
            # collapse a comparable pair to a single argument.
            if len(args)<2:raise JournalError('min and max compare at least two arguments.')
            if units is not None:
                dimensions=[infer(arg,units) for arg in args]
                known=[d for d in dimensions if d is not None]
                if any(d!=known[0] for d in known):raise JournalError('Arguments of '+name+' have incompatible dimensions.')
            return (sp.Min if name=='min' else sp.Max)(*args)
        raise JournalError('This expression editor currently accepts arithmetic, sqrt, exp, log, min, max and declared quantities only.')
    result=convert(tree)
    from .validity import finite
    finite(result)
    return result

