"""Equivariant rebinding of a fully verified shared-operation replay.

This is invoked only while constructing an instance, never by trusting an
imported provenance claim. Bijections preserve algebraic operations, units,
domains and branches. Every target input signature is recomputed.
"""
from copy import deepcopy
from dataclasses import replace

from core.mathematics.provenance import equation_signature
from core.mathematics.session import ReplayResult


def bind_replay(source, definition, expression, equation_id, quantity_ids, owners, unit_resolver):
    graph = deepcopy(source.graph)
    graph.nodes = {equation_id(key):replace(node,equation=expression(node.equation),
        inputs=tuple(equation_id(k) for k in node.inputs),
        predicates=tuple(expression(p) for p in node.predicates),
        branches=tuple((expression(eq),admitted) for eq,admitted in node.branches))
        for key,node in source.graph.nodes.items()}
    graph.names = {expression(q):name for q,name in source.graph.names.items()}
    graph.domains = {equation_id(key):replace(domain,quantity=expression(domain.quantity),
        scale=expression(domain.scale),
        lower=expression(domain.lower) if hasattr(domain.lower,'xreplace') else domain.lower,
        upper=expression(domain.upper) if hasattr(domain.upper,'xreplace') else domain.upper)
        for key,domain in source.graph.domains.items()}
    units = {expression(q):unit for q,unit in source.units.items()}
    receipts = []
    for receipt in source.receipts:
        inputs = {equation_id(key):equation_signature(graph,equation_id(key),units,unit_resolver)
                  for key in receipt.calculated_input_signatures}
        receipts.append(replace(receipt,input_signatures=inputs,calculated_input_signatures=inputs,
            conditions=tuple(dict.fromkeys(condition for key,_ in receipt.after
                for condition in graph.conditions_for(equation_id(key)))),
            before=tuple((equation_id(key),expression(eq)) for key,eq in receipt.before),
            after=tuple((equation_id(key),expression(eq)) for key,eq in receipt.after),
            declared_quantities=tuple((expression(q),unit) for q,unit in receipt.declared_quantities),
            branches=tuple((expression(eq),admitted) for eq,admitted in receipt.branches),
            validity_predicates=tuple(expression(p) for p in receipt.validity_predicates),
            signature_status='pinned' if inputs else receipt.signature_status))
    return ReplayResult(graph,[equation_id(k) for k in source.selected],
        {equation_id(k):owners.get(v,v) for k,v in source.owners.items()},units,deepcopy(definition),
        source.requires_lowering,{quantity_ids.get(k,k):expression(q) for k,q in source.introduced.items()},tuple(receipts))
