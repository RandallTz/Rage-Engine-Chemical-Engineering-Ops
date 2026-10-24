"""Mathematical input identity, independent of display labels and physical catalogs."""
import hashlib
import json
import sympy as sp
from core.unidades import interpretar
from .dimensions import known_unit


def input_ids(operation):
    return tuple(dict.fromkeys([*operation.get('sources',[]),*([operation['relation']] if operation['kind']=='substitute' else []),*operation.get('domains',[])]))


def equation_signature(graph,key,units,unit_resolver=known_unit):
    node=graph.nodes[key]
    predicates=graph.predicates_for(key)
    quantities=sorted(set().union(*(expression.atoms(sp.Symbol,sp.core.function.AppliedUndef) for expression in (node.equation,*predicates))),key=sp.srepr)
    declarations=[]
    for quantity in quantities:
        unit=unit_resolver(quantity,units)
        specification=None
        if unit is not None:
            value=interpretar(unit)
            specification={'dimension':sorted((base,str(power)) for base,power in value['dimension'].items()),
                           'factor':value['factor'],'offset':value['desplazamiento']}
        declarations.append((sp.srepr(quantity),specification))
    payload={'equation':sp.srepr(node.equation),'kind':node.kind,'dependent':node.dependent,
             'conditions':graph.conditions_for(key),'predicates':[sp.srepr(p) for p in predicates],'units':declarations}
    if node.branches:payload['branches']=[(sp.srepr(eq),admitted) for eq,admitted in node.branches]
    return hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def source_signatures(graph,operation,units,unit_resolver=known_unit):
    return {key:equation_signature(graph,key,units,unit_resolver) for key in input_ids(operation)}
