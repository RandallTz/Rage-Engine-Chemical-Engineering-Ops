"""Ordered mathematical replay, independent of physical source producers."""
import copy
import re
from dataclasses import dataclass,field
from types import MappingProxyType
import sympy as sp
from core.unidades import interpretar,unidad_SI,exact_conversion,ErrorUnidad
from .constants import unit_basis
from .errors import MathematicsError as JournalError
from .graph import math_latex,solve_unique
from .dimensions import catalog,known_unit,dimension as infer_dimension,parse_expression
from .contract import read_definition,FORMAT,keys
from .provenance import input_ids,source_signatures
from .validity import finite


@dataclass(frozen=True)
class OperationReceipt:
    operation_id: str
    input_signatures: dict
    before: tuple
    after: tuple
    conditions: tuple
    declared_quantities: tuple = ()
    branches: tuple = ()
    validity_predicates: tuple = ()
    calculated_input_signatures: dict = field(default_factory=dict)
    signature_status: str = 'not_applicable'

    def __post_init__(self):
        object.__setattr__(self,'input_signatures',MappingProxyType(dict(self.input_signatures)))
        object.__setattr__(self,'calculated_input_signatures',MappingProxyType(dict(self.calculated_input_signatures)))


@dataclass
class ReplayResult:
    graph: object
    selected: list
    owners: dict
    units: dict
    definition: dict
    requires_lowering: bool
    introduced: dict
    receipts: tuple

    def _values(self):
        return (self.graph,self.selected,self.owners,self.units,self.definition,self.requires_lowering,self.introduced)

    def __iter__(self):return iter(self._values())
    def __getitem__(self,index):return self._values()[index]
    def __len__(self):return 7


def edit_history(source,selected,owners,declared_units,definition,action,*,require_same_family=False,unit_resolver=known_unit):
    """Atomic history edits; append pins the source actually being operated on."""
    read_definition(definition);keys(action,['kind'],['operation'])
    updated=copy.deepcopy(definition);kind=action['kind']
    if kind=='undo':updated['cursor']=max(0,updated['cursor']-1)
    elif kind=='redo':updated['cursor']=min(len(updated['operations']),updated['cursor']+1)
    elif kind=='rewind':updated['cursor']=0
    elif kind=='append':
        if 'operation' not in action:raise JournalError('An equation operation is required.')
        operation=copy.deepcopy(action['operation'])
        read_definition({'format':FORMAT,'version':1,'operations':[operation],'cursor':1})
        current=replay_operations(source,selected,owners,declared_units,definition,require_same_family=require_same_family,unit_resolver=unit_resolver)
        if any(key not in current.graph.nodes for key in input_ids(operation)):
            raise JournalError('An input equation changed or was removed. Select its current expression before recording.')
        signatures=source_signatures(current.graph,operation,current.units,unit_resolver)
        if 'sourceSignatures' in operation and operation['sourceSignatures']!=signatures:
            raise JournalError('The operation preview used different input equations. Preview the current source before recording.')
        if signatures:operation['sourceSignatures']=signatures
        updated['operations']=updated['operations'][:updated['cursor']]+[operation]
        updated['cursor']+=1
    else:raise JournalError('Unknown equation history action.')
    # Undo/rewind must remain available even when an earlier operation needs
    # review. Their caller can publish a recovery preview without losing data.
    if kind not in ('undo','rewind'):
        replay_operations(source,selected,owners,declared_units,updated,require_same_family=require_same_family,unit_resolver=unit_resolver)
    return updated


def replay_operations(source,selected,owners,declared_units,definition,*,require_same_family=False,unit_resolver=known_unit):
    read_definition(definition)
    graph=copy.deepcopy(source);final=list(selected);locations=dict(owners);units=dict(declared_units)
    definition=copy.deepcopy(definition);introduced={};blocking=False;receipts=[]
    def _dimension(value,local_units):return infer_dimension(value,local_units,unit_resolver)
    def _known_unit(value,local_units):return unit_resolver(value,local_units)
    def _parse(text,quantities,conditions=None,units=None):return parse_expression(text,quantities,conditions,units,unit_resolver)
    for index,op in enumerate(definition['operations'][:definition['cursor']]):
        key='operation.'+str(index+1);kind=op['kind'];quantities={**catalog(graph,units),**introduced};sources=op.get('sources',[])
        inputs=input_ids(op)
        if any(source not in graph.nodes for source in inputs):raise JournalError('An input equation changed or was removed. Undo this operation or rebuild from its law.')
        for source_id in inputs:
            equation=graph.nodes[source_id].equation
            if not isinstance(equation,sp.Equality):
                if source_id in sources or source_id==op.get('relation'):raise JournalError('A domain membership condition is not an equation to manipulate. Use it as a domain premise.')
                continue
            finite(equation)
            left,right=_dimension(equation.lhs,units),_dimension(equation.rhs,units)
            if left is not None and right is not None and left!=right:
                raise JournalError('An input equation has incompatible dimensions; algebra cannot certify it by cancellation.')
        signatures=source_signatures(graph,op,units,unit_resolver)
        if 'sourceSignatures' in op and op['sourceSignatures']!=signatures:
            raise JournalError('An input equation or its declared units/conditions changed behind the same ID. Review the saved operation; it will not be applied to a different mathematical source.')
        recorded_signatures=op.get('sourceSignatures',{})
        signature_status=('pinned' if 'sourceSignatures' in op else 'legacy/unsigned') if inputs else 'not_applicable'
        # Missing evidence cannot establish whether the source changed. Keep
        # legacy histories readable, but never certify their replay for Solve.
        if signature_status=='legacy/unsigned':blocking=True
        previous=set(graph.nodes);before=tuple((source,graph.nodes[source].equation) for source in inputs)
        if require_same_family and sources and any(graph.nodes[s].family!=op['family'] for s in sources):raise JournalError('The selected input does not belong to this balance family.')
        if kind in ('declare_symbol','declare_function'):
            name=op['name']
            existing_names={str(q) if isinstance(q,sp.Symbol) else q.func.__name__ for q in quantities.values()}
            if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,40}',name) or name in introduced or name in existing_names or name in quantities:raise JournalError('Declare a distinct mathematical quantity name.')
            unit=interpretar(op['unit'])
            if unit['afin']:raise JournalError('Affine units require an explicit reference before algebraic operations. Declare an absolute SI quantity here.')
            if kind=='declare_function':
                dependencies=op['dependencies']
                if not dependencies or any(d not in quantities or not isinstance(quantities[d],(sp.Symbol,sp.core.function.AppliedUndef)) for d in dependencies):raise JournalError('A dependent quantity requires existing coordinates or quantities as arguments.')
                symbol=sp.Function(name)(*(quantities[d] for d in dependencies))
            else:symbol=sp.Symbol(name,real=True)
            introduced[name]=symbol;units[symbol]=op['unit']
            receipts.append(OperationReceipt(key,recorded_signatures,before,(),(),((symbol,op['unit']),),
                                             calculated_input_signatures=signatures,signature_status=signature_status))
            continue
        if kind=='declare_domain':
            if op['symbol'] not in quantities:raise JournalError('Select a current mathematical quantity for the domain.')
            quantity=quantities[op['symbol']]
            if not isinstance(quantity,(sp.Symbol,sp.core.function.AppliedUndef)) or not graph.nodes[sources[0]].equation.has(quantity):
                raise JournalError('A domain requires a scalar quantity occurring in its selected source equation.')
            unit=_known_unit(quantity,units)
            if unit is None or interpretar(unit)['afin']:raise JournalError('Domain signs require a declared absolute unit, not an affine quantity.')
            if op['domain']=='interval' and 'endpointUnit' not in op and interpretar(unit)['factor']!=1:
                raise JournalError('Legacy interval endpoints require SI-scale quantities. Record an explicit endpoint unit for scaled quantities.')
            bounds={field:op[wire] for field,wire in [('lower','lower'),('upper','upper'),('lower_open','lowerOpen'),('upper_open','upperOpen')] if wire in op}
            basis=unit_basis(interpretar(unit)['dimension']);declaration=None
            if 'endpointUnit' in op:
                from .domains import DomainPremise,exact_endpoint
                try:conversion=exact_conversion(op['endpointUnit'])
                except ErrorUnidad as error:raise JournalError('The endpoint unit has no supported exact conversion: '+str(error)) from error
                if conversion['afin']:raise JournalError('Affine endpoints require an explicit absolute reference; use an absolute unit.')
                if conversion['dimension']!=interpretar(unit)['dimension']:raise JournalError('Interval endpoints have incompatible dimensions.')
                factor=sp.Rational(conversion['factor'])
                original=DomainPremise(quantity,'interval',**bounds,scale=factor*basis,explicit_units=True)
                declaration=(original,'Declare interval endpoints in '+op['endpointUnit'])
                bounds={**bounds,'lower':exact_endpoint(op['lower'])*factor,'upper':exact_endpoint(op['upper'])*factor,'explicit_units':True}
            graph.declare_domain(key,sources[0],quantity,op['domain'],op['reason'],declaration=declaration,scale=basis,**bounds);blocking=True
            if declaration is not None:locations[key+'.declared']=locations[sources[0]]
        elif kind=='declare_relation':
            conditions=[op['reason']]
            left,right=_parse(op['left'],quantities,conditions,units),_parse(op['right'],quantities,conditions,units)
            a,b=_dimension(left,units),_dimension(right,units)
            if a is not None and b is not None and a!=b:raise JournalError('The two sides of this relation have incompatible dimensions.')
            relation_kind=op.get('relationKind','definition')
            title={'definition':'Declared definition','constitutive':'Declared constitutive relation','constraint':'Declared condition'}[relation_kind]
            graph.add(key,left,right,title,'declared_relation',assumptions=tuple(dict.fromkeys(conditions)),family=op['family'],kind=relation_kind);blocking=True
        elif kind in ('multiply','divide'):
            conditions=[];factor=_parse(op['right'],quantities,conditions,units);_dimension(factor,units)
            if factor.is_zero is True:raise JournalError('Scaling by zero would destroy the equation. Select a nonzero factor.')
            if factor.is_nonzero is not True:conditions.append(sp.Ne(factor,0,evaluate=False))
            graph.transform(key,sources[0],lambda e:sp.cancel(e/factor if kind=='divide' else e*factor),
                            'Scale both sides by the declared factor',kind,tuple(dict.fromkeys(conditions)))
        elif kind=='combine':
            dimensions=[]
            for source in sources:
                equation=graph.nodes[source].equation
                a,b=_dimension(equation.lhs,units),_dimension(equation.rhs,units)
                if a is not None and b is not None and a!=b:raise JournalError('An input equation has incompatible dimensions.')
                dimensions.append(a if a is not None else b)
            reference=next((d for d in dimensions if d is not None),None)
            if any(d is not None and reference is not None and d!=reference for d in dimensions):raise JournalError('Only equations with compatible dimensions can be added.')
            graph.combine(key,sources,'Combine selected equations of '+op['family'])
        elif kind in ('expand','factor'):graph.transform(key,sources[0],sp.expand if kind=='expand' else sp.factor,'Apply '+kind+' to the selected equation',kind)
        elif kind in ('volume_integrate','gauss','reynolds'):
            from .operators import VolumeIntegral as VI,BoundaryFlux as BF,Divergence as Div
            if kind=='volume_integrate':graph.transform(key,sources[0],VI,'Integrate both sides over the current domain','volume_integration')
            elif kind=='gauss':
                equation=graph.nodes[sources[0]].equation
                if not any(isinstance(n,VI) and isinstance(n.args[0],Div) for n in sp.preorder_traversal(equation)):raise JournalError('Gauss requires an integrated divergence in the selected equation.')
                graph.transform(key,sources[0],lambda e:e.replace(lambda n:isinstance(n,VI) and isinstance(n.args[0],Div),lambda n:BF(n.args[0].args[0])),
                                'Apply Gauss to the integrated divergence','divergence_theorem',('Regular fields and an oriented domain boundary',))
            else:
                owner=locations[sources[0]];vb=sp.Symbol('v_b__'+owner,real=True)
                equation=graph.nodes[sources[0]].equation
                coordinates={node.args[0].variable_count[0][0] for node in sp.preorder_traversal(equation) if isinstance(node,VI) and isinstance(node.args[0],sp.Derivative) and len(node.args[0].variable_count)==1 and node.args[0].variable_count[0][1]==1}
                if op.get('symbol'):
                    if op['symbol'] not in quantities or not isinstance(quantities[op['symbol']],sp.Symbol):raise JournalError('Select an independent transport coordinate.')
                    t=quantities[op['symbol']]
                elif len(coordinates)==1:t=next(iter(coordinates))
                else:raise JournalError('Reynolds transport needs one selected evolution coordinate.')
                motion_dimension={'L':1}
                for base,power in (_dimension(t,units) or {}).items():motion_dimension[base]=motion_dimension.get(base,0)-power
                units[vb]=unidad_SI({base:power for base,power in motion_dimension.items() if power})
                targets=[n for n in sp.preorder_traversal(equation) if isinstance(n,VI) and isinstance(n.args[0],sp.Derivative) and n.args[0].variable_count==((t,1),)]
                if not targets:raise JournalError('Reynolds requires a volume integral of a first time derivative.')
                replacements={}
                for i,target in enumerate(dict.fromkeys(targets)):
                    field=target.args[0].expr;theorem=key+'.theorem.'+str(i+1)
                    graph.add(theorem,sp.Derivative(VI(field),t,evaluate=False),target+BF(field*vb),'Reynolds transport identity','transport_theorem',assumptions=('Sufficiently regular fields and domain motion',),family=op['family'],kind='definition')
                    locations[theorem]=owner;replacements[target]=sp.Derivative(VI(field),t,evaluate=False)-BF(field*vb)
                graph.substitute(key,sources[0],replacements,'Substitute Reynolds transport term by term',inputs=tuple(key+'.theorem.'+str(i+1) for i in range(len(replacements))))
        else:
            if op['symbol'] not in quantities:raise JournalError('The selected quantity changed. Select it again from the current equation graph.')
            symbol=quantities[op['symbol']]
            case_source=None
            if kind in ('isolate','substitute') and op.get('domains'):
                if any(id_ not in graph.domains for id_ in op['domains']):raise JournalError('Select recorded domain conditions, not arbitrary equations.')
                source=op['relation'] if kind=='substitute' else sources[0]
                case_source=graph.specialize_domains(key+'.case',source,symbol,op['domains'])
                if case_source!=source:locations[case_source]=locations.get(source,'system')
            if kind=='isolate':
                if op.get('domains'):
                    solution,conditions,branches=graph.solve_in_domains(graph.nodes[case_source].equation,symbol,op['domains'])
                    graph.add(key,symbol,solution,'Isolate using recorded domain conditions','domain_isolation',(case_source,*op['domains']),conditions,op['family'])
                    graph.nodes[key].branches=branches
                else:graph.isolate(key,sources[0],symbol,'Isolate the selected quantity')
            elif kind=='substitute':
                if op['relation'] not in graph.nodes:raise JournalError('The substitution relation does not exist.')
                relation=graph.nodes[case_source or op['relation']].equation
                if op.get('domains'):solution,nonzero,branches=graph.solve_in_domains(relation,symbol,op['domains'])
                else:solution,nonzero=solve_unique(relation,symbol,graph.names);branches=()
                if not graph.nodes[sources[0]].equation.has(symbol):raise JournalError('The selected quantity does not occur in the input equation.')
                a,b=_dimension(symbol,units),_dimension(solution,units)
                if a is not None and b is not None and a!=b:raise JournalError('The substitution has incompatible dimensions.')
                conditions=list(nonzero)
                equation=graph.nodes[sources[0]].equation
                conditions.extend(graph.specialized_predicates((sources[0],case_source or op['relation']),{symbol:solution}))
                graph.add(key,equation.lhs.xreplace({symbol:solution}).doit(),equation.rhs.xreplace({symbol:solution}).doit(),
                          'Substitute the relation and evaluate the chain rule','substitution',(sources[0],case_source or op['relation'],*op.get('domains',[])),conditions,op['family'])
                graph.nodes[key].branches=branches
            elif kind=='differentiate':
                if not isinstance(symbol,sp.Symbol):raise JournalError('Differentiation requires an independent coordinate.')
                graph.differentiate(key,sources[0],symbol,'Differentiate both sides')
            elif kind=='integrate':
                if not isinstance(symbol,sp.Symbol):raise JournalError('Integration requires an independent coordinate.')
                if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,40}',op['name']):raise JournalError('Name the integration constant.')
                if any(op['name']==(str(q) if isinstance(q,sp.Symbol) else q.func.__name__) for q in quantities.values()):raise JournalError('The integration constant must have a new name.')
                equation=graph.nodes[sources[0]].equation
                remaining=sorted({coordinate for field in equation.atoms(sp.core.function.AppliedUndef) for coordinate in field.free_symbols if coordinate!=symbol},key=sp.srepr)
                constant=sp.Function(op['name'])(*remaining) if remaining else sp.Symbol(op['name'],real=True)
                dimension=_dimension(equation.lhs,units)
                if dimension is None:dimension=_dimension(equation.rhs,units)
                dimension=dict(dimension or {})
                for base,power in (_dimension(symbol,units) or {}).items():dimension[base]=dimension.get(base,0)+power
                units[constant]=unidad_SI({base:power for base,power in dimension.items() if power})
                introduced[op['name']]=constant
                graph.integrate(key,sources[0],symbol,constant,'Integrate both sides; retain the integration quantity and remaining dependencies')
            elif kind=='zero':
                graph.add(key,symbol,0,'Declared zero condition','assumption',(sources[0],),(op['reason'],),op['family'],kind='constraint');blocking=True
            elif kind in ('apply_zero','change_dependencies'):
                equation=graph.nodes[sources[0]].equation
                if not equation.has(symbol):raise JournalError('The selected quantity does not occur in the input equation.')
                replacement=sp.S.Zero
                if kind=='change_dependencies':
                    if not isinstance(symbol,sp.core.function.AppliedUndef):raise JournalError('Dependency reduction requires a dependent quantity.')
                    if any(d not in quantities or quantities[d] not in symbol.args for d in op['dependencies']):raise JournalError('Retain only arguments of the selected quantity.')
                    args=tuple(quantities[d] for d in op['dependencies'])
                    if len(args)>=len(symbol.args):raise JournalError('Remove at least one dependency to record this assumption.')
                    replacement=symbol.func(*args) if args else sp.Symbol(symbol.func.__name__,real=True)
                    unit=_known_unit(symbol,units)
                    if unit is None:raise JournalError('The selected quantity needs a declared unit.')
                    units[replacement]=unit
                condition=key+'.condition'
                graph.add(condition,symbol,replacement,'Declared dependency reduction' if kind=='change_dependencies' else 'Declared zero condition','assumption',(sources[0],),(op['reason'],),op['family'],kind='constraint')
                locations[condition]=locations[sources[0]];final.append(condition)
                guards=graph.specialized_predicates((sources[0],),{symbol:replacement})
                graph.add(key,equation.lhs.xreplace({symbol:replacement}).doit(),equation.rhs.xreplace({symbol:replacement}).doit(),
                          'Apply the condition and evaluate derivatives','substitution',(sources[0],condition),(op['reason'],),op['family'],predicates=guards)
                blocking=True
        if key in graph.nodes:
            # New conditional deductions need numerical enforcement before
            # they may accompany a run of the selected formulation.
            inherited={p for source_id in inputs for p in graph.predicates_for(source_id)}
            if any(p not in inherited and p.doit() is not sp.S.true for created_id in graph.nodes.keys()-previous for p in graph.nodes[created_id].predicates):
                blocking=True
            # Check actual derived equations, including typed singleton values.
            # Conditions are membership predicates, not equalities.
            for created_id in graph.nodes.keys()-previous:
                equation=graph.nodes[created_id].equation
                if isinstance(equation,sp.Equality):
                    left,right=_dimension(equation.lhs,units),_dimension(equation.rhs,units)
                    if left is not None and right is not None and left!=right:raise JournalError('The derived equation has incompatible dimensions.')
            final.append(key)
            owners={locations.get(source,'system') for source in sources}
            locations[key]=owners.pop() if len(owners)==1 else 'system'
            # Consequences supplement their premises; they do not silently
            # replace a physical law or add independent dynamic states.
            if kind not in ('zero','declare_relation'):graph.nodes[key].dependent=True
        created=tuple(id_ for id_ in graph.nodes if id_ not in previous)
        after=tuple((id_,graph.nodes[id_].equation) for id_ in created)
        conditions=tuple(dict.fromkeys(condition for id_ in created for condition in graph.conditions_for(id_)))
        receipts.append(OperationReceipt(key,recorded_signatures,before,after,conditions,branches=tuple(branch for id_ in created for branch in graph.nodes[id_].branches),
                                         calculated_input_signatures=signatures,signature_status=signature_status,
                                         validity_predicates=tuple(dict.fromkeys(p for id_ in created for p in graph.predicates_for(id_)))))
    return ReplayResult(graph,final,locations,units,definition,blocking,introduced,tuple(receipts))
