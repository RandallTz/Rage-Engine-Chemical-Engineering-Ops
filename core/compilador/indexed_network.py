"""Prepared indexed-network lowering; missing recorded transport fails closed.

The expansion owns topology. Each stage still replays and admits its exact
selected equations. Connections replace exterior boundary bindings, never the
selected balances or a missing donor law: the receiver's inlet flow, composition
and enthalpy data by the donor's recorded transport, and the donor's recorded
discharge-port pressure datum by the receiving volume's pressure
(`pressure_couplings`). This internal runtime is not yet an HTTP/common-result
publication path.
"""
import numpy as np
import sympy as sp

from core.mathematics.constants import si_magnitude
from core.modelo.index_sets import expand_index_set, read_index_set
from core.solvers import Detencion
from core.solvers.sparse_blocks import ExpressionJacobian
from .derived import DerivedSystem
from .derived_graph import LoweringError


def _failure(code, message, path):
    error = LoweringError(code, message)
    error.diagnostics[0]['path'] = path
    return error


def discharge(system, port, path):
    """Resolve the exact recorded component flows and stream specific enthalpy."""
    if port['kind'] != 'material' or port['boundary']['type'] != 'stream':
        raise _failure('index_network_unsupported_port', 'This lowering admits material stream connections.', path)
    identity = port['boundary']['id']
    stream = next(s for s in system.model['corrientes'] if s['id'] == identity)
    if stream['materia']['base'] != 'masica':
        raise _failure('index_network_unsupported_port', 'Mass-based component stream bindings are required.', path)
    quantities = [sp.Function('q__'+identity+'__'+str(i))(system.time) for i in stream['componenteIds']]
    quantities.append(sp.Function('energy_average_0__'+identity)(system.time))
    expressions = [system._expand(q) for q in quantities]
    admitted = set(system.states) | set(system.closure_quantities)
    for quantity, expression in zip(quantities, expressions):
        if (expression.atoms(sp.core.function.AppliedUndef)-admitted or
                expression.free_symbols-set(system.parameter_values)-{system.time}):
            raise _failure('index_network_missing_transport',
                'Record componentwise donor transport and discharge specific enthalpy before connecting this port; unresolved '+str(quantity)+'.', path)
    return stream['componenteIds'], expressions[:-1], expressions[-1]


def align_transport(donor_model, components, fluxes, closure, path):
    """Join component transport by chemical identity, never by local position."""
    chemicals = {row['id']: row.get('identidadQuimica', {}).get('cas')
                 for row in donor_model['componentes']}
    species = [chemicals.get(key) for key in components]
    if (any(not key for key in species) or len(set(species)) != len(species)
            or len(set(closure.species)) != len(closure.species)
            or set(species) != set(closure.species)):
        raise _failure('index_network_component_mismatch',
            'Connected material streams require the same distinct chemical identities.', path)
    by_species = dict(zip(species, fluxes))
    return closure.components, [by_species[key] for key in closure.species]


COUPLING_PREMISE = ('The connected stream enters the receiving volume at its uniform thermodynamic pressure; '
                    'no pressure change is resolved between the discharge port and the receiving volume.')


def check_connection_pressure(donor, port, receiver, closure, path):
    """Couple a recorded discharge-port pressure to the receiving volume, or prove equal pressures.

    A hydraulic discharge path records its exterior port pressure p2 as one
    bound boundary datum. A connection replaces exterior boundary bindings, so
    it replaces that datum by the receiving volume's pressure (network relation
    p2[j] = P[k], premise COUPLING_PREMISE); the path momentum then responds to
    the receiving pressure, including when it varies or differs from the donor.
    The coupling is returned as (donor datum symbol, receiving pressure expression)
    and is published by the assembly. Without such a datum (a direct phase draw,
    or a literal/derived port pressure) only a proved equal prescribed pressure
    is admitted; unresolved or unequal pressures fail closed.
    """
    owner = port['volumeId']
    pressure = sp.Function('p2__'+owner)(donor.time)
    relations = [node.equation.rhs for node in donor.graph.nodes.values()
                 if isinstance(node.equation,sp.Equality) and node.equation.lhs == pressure]
    target = receiver._expand(closure.P)
    resolved = si_magnitude(target).subs(receiver.parameter_values)
    if len(relations) == 1:
        datum = si_magnitude(donor._expand(pressure))
        if datum in donor.parameter_values:
            known = set(getattr(receiver, 'states', ())) | set(getattr(receiver, 'closure_quantities', ()))
            free = resolved.free_symbols - {getattr(receiver, 'time', None)}
            if (resolved.atoms(sp.core.function.AppliedUndef) - known or free
                    or resolved.is_number and resolved.is_positive is not True):
                raise _failure('index_network_pressure_mismatch',
                    'The receiving-volume pressure must be a positive bound or state-resolved quantity before it can be coupled to the discharge port.', path)
            return datum, target
    if not relations:
        # A direct phase draw has no separate hydraulic path boundary.
        relations = [sp.Function('P__'+owner)(donor.time)]
    values = [si_magnitude(donor._expand(p)).subs(donor.parameter_values) for p in relations]
    if (not resolved.is_number or resolved.is_positive is not True or
            any(not p.is_number or p.is_positive is not True or sp.simplify(p-resolved)!=0 for p in values)):
        raise _failure('index_network_pressure_mismatch',
            'Without a recorded discharge-port pressure datum, connected discharge and receiving-volume pressures must be the same prescribed value.', path)
    return None


class IndexedDerivedSystem:
    """Stage-local namespaces composed into one explicit RHS and sparse Jacobian."""
    def __init__(self, model, *, linear_solver='auto'):
        self.model = model
        record, count, _, _, _ = read_index_set(model)
        from .template_lowering import bind_stage, compile_template
        templates = {}
        # Inspect the recorded templates first: a missing physical relation is
        # located before spending time replaying n identical instances.
        if count > 1:
            for name, template in record['templates'].items():
                source = compile_template(template)
                templates[name] = source
                ports = {p['id']: p for p in template['template']['ports']}
                for rule in record['connections']:
                    discharge(source, ports[rule['outlet']],
                              'indexSet.templates.'+name+'.template.ports.'+rule['outlet'])
        self.expansion = expand_index_set(model)
        from core.mathematics.preparation import enabled
        if enabled():
            for name, template in record['templates'].items():
                if name not in templates:
                    templates[name] = compile_template(template)
            self.stages = [bind_stage(templates[row['template']],row) for row in self.expansion['stages']]
        else:
            self.stages = [DerivedSystem(row['model']) for row in self.expansion['stages']]
        self.template_systems = templates
        self.location = 'indexSet'
        self._assemble(linear_solver)

    def _assemble(self, linear_solver):
        """Compose replayed stage namespaces through the expansion connections.

        Shared by index-set networks and flowsheets: both supply `expansion`
        (stages with their replayed models, connections and exposed ports),
        `stages` (lowered stage systems) and `location` for diagnostics.
        """
        where = self.location
        if any(s.nonlinear or s.scaled is not None for s in self.stages):
            raise _failure('index_network_unsupported_formulation', 'Indexed assembly requires identity explicit stage selections.', where)
        self.offsets = np.cumsum([0]+[len(s.initial()) for s in self.stages]).tolist()
        self.time = sp.Symbol('network_time', real=True)
        self.variables = list(sp.symbols('network_state:'+str(self.offsets[-1]), real=True))
        self.outputs = []
        self.maps = []
        self.bindings = [{} for _ in self.stages]
        for j, stage in enumerate(self.stages):
            outputs = list(sp.symbols('stage_'+str(j)+'_closure:'+str(len(stage.closure_quantities)), real=True))
            mapping = {**dict(zip(stage.states, self.variables[self.offsets[j]:self.offsets[j]+stage.size])),
                       **dict(zip(stage.closure_quantities, outputs)), stage.time:self.time}
            self.maps.append(mapping); self.outputs.extend(outputs)
        substitutions = {}
        donor_rows = []
        pressure_rows = []
        self.pressure_couplings = []
        for connection in self.expansion['connections']:
            a, b = connection['from']['stage']-1, connection['to']['stage']-1
            donor, receiver = self.stages[a], self.stages[b]
            port = next(p for p in donor.model['template']['ports'] if p['id']==connection['from']['portId'])
            components, fluxes, enthalpy = discharge(donor, port, where+'.connections.'+connection['id'])
            target = connection['to']['boundary']['id']
            closure = next((c for c in receiver.closures if target in c.inlets), None)
            if closure is None:
                raise _failure('index_network_unsupported_inlet', 'The receiving stream needs the existing package exterior-state bindings.', where+'.connections.'+connection['id'])
            coupling = check_connection_pressure(donor, port, receiver, closure, where+'.connections.'+connection['id'])
            if coupling is not None:
                datum, pressure = coupling
                if datum in self.bindings[a]:
                    raise _failure('index_network_shared_boundary_datum', 'Each coupled discharge-port pressure needs its own exterior datum.', where+'.connections.'+connection['id'])
                placeholder = sp.Dummy('connected_pressure')
                self.bindings[a][datum] = placeholder
                pressure_rows.append((b, placeholder, pressure))
                self.pressure_couplings.append({'connectionId': connection['id'], 'premise': COUPLING_PREMISE,
                    'from': {'stage': a+1, 'quantity': 'p2__'+port['volumeId'], 'replacedDatum': str(datum)},
                    'to': {'stage': b+1, 'quantity': str(closure.P)}})
            components, fluxes = align_transport(donor.model, components, fluxes, closure,
                                                where+'.connections.'+connection['id'])
            weights = [sp.Function('inlet_mass_fraction_'+str(i)+'__'+target)(receiver.time) for i in components]
            component_flows = [sp.Function('q__'+target+'__'+str(i))(receiver.time) for i in components]
            candidates = [sp.cancel(receiver._expand(q)/receiver._expand(w)) for q,w in zip(component_flows,weights)]
            flow = candidates[0]
            if flow not in receiver.parameter_values or any(c != flow for c in candidates):
                raise _failure('index_network_unsupported_inlet', 'Record one bound inlet mass flow multiplying the package mass fractions.', where+'.connections.'+connection['id'])
            boundary = {flow:sp.Dummy('connected_flow')}
            for quantity in closure.inlets[target]['values']:
                boundary[receiver.parameter_symbols[quantity]] = sp.Dummy('connected_inlet')
            if set(boundary) & self.bindings[b].keys():
                raise _failure('index_network_shared_boundary_datum', 'Connected inlet bindings must be independent.', where+'.connections.'+connection['id'])
            self.bindings[b].update(boundary)
            donor_rows.append((a,b,components,fluxes,enthalpy,closure,target,flow,boundary))
        # Local constants and authored symbols remain scoped to their stage.
        def scope(j, expression):
            stage = self.stages[j]
            parameters = {p:self.bindings[j].get(p,v) for p,v in stage.parameter_values.items()}
            return si_magnitude(expression).xreplace(parameters).xreplace(self.maps[j])
        for a,b,components,fluxes,enthalpy,closure,target,flow,boundary in donor_rows:
            fluxes = [scope(a,e) for e in fluxes]; h = scope(a,enthalpy); total = sum(fluxes)
            mass = total/sum(q/m for q,m in zip(fluxes,closure.molar_masses))
            replacements = {'inlet_specific_enthalpy':h, 'inlet_molar_enthalpy':h*mass, 'inlet_molar_mass':mass}
            replacements.update({'inlet_mass_fraction_'+str(i):q/total for i,q in zip(components,fluxes)})
            substitutions[boundary[flow]] = total
            for quantity in closure.inlets[target]['values']:
                name = str(quantity.func).split('__')[0]
                substitutions[boundary[self.stages[b].parameter_symbols[quantity]]] = replacements[name]
        # Network relation p2[donor] = P[receiver]: the receiving pressure in its own stage scope.
        for b, placeholder, pressure in pressure_rows:
            substitutions[placeholder] = scope(b, pressure)
        boundary_symbols = set(substitutions)
        def connect(expression):
            for _ in range(len(substitutions)+1):
                updated = expression.xreplace(substitutions)
                if updated == expression: break
                expression = updated
            if expression.free_symbols & boundary_symbols:
                raise _failure('index_network_algebraic_loop', 'Connected boundary values contain an unresolved algebraic loop.', where+'.connections')
            return sp.cancel(expression)
        self.connected_expression = lambda j, expression: connect(scope(j, expression))
        expressions = []
        self.guards = []
        blocks = []
        for j, stage in enumerate(self.stages):
            expressions.extend(connect(scope(j,e)) for e in [*stage.rates.values(), *(rate for _,_,rate,_ in stage.checks)])
            self.guards.extend((connect(scope(j,e)),strict,key,label) for e,strict,key,label in stage.margins)
            for closure in stage.closures:
                indices = {self.offsets[j]+i for i,q in enumerate(stage.states) if any(e.has(q) for e in closure.input_expressions)}
                def evaluate(t,y,closure=closure,j=j):
                    return closure.evaluate(t,y[self.offsets[j]:self.offsets[j+1]])[0]
                blocks.append(([self.maps[j][q] for q in closure.outputs],indices,evaluate))
        self.expressions = expressions
        self.blocks = blocks
        self.function = sp.lambdify([self.time,self.variables,self.outputs],expressions,modules='numpy',cse=True)
        self.guard_function = sp.lambdify([self.time,self.variables,self.outputs],[e for e,_,_,_ in self.guards],modules='numpy',cse=True)
        self.atol = np.concatenate([s.numeric.atol for s in self.stages])
        self.block_jacobian = ExpressionJacobian(expressions,self.variables,self.time,
            np.maximum(np.abs(self.initial()),self.atol),blocks,requested=linear_solver)
        self.linear_policy = self.block_jacobian.policy
        # Keep the recorded automatic policy: dense finite differences remain
        # the reference until a reproducible sparse crossover is established.
        self.jacobian = self.block_jacobian if self.linear_policy['selected'] == 'sparse' else None
        self.tf = self.stages[0].tf
        self.method = self.stages[0].method
        if any(s.tf != self.tf or s.method != self.method for s in self.stages):
            raise _failure('index_network_incompatible_study', 'Stage horizons and integration methods must agree.', where+'.templates')

    def initial(self):
        return np.concatenate([s.initial() for s in self.stages])

    def closure_values(self,t,y):
        return np.concatenate([evaluate(t,y) for _,_,evaluate in self.blocks]) if self.blocks else np.array([])

    def rhs(self,t,y):
        outputs = self.closure_values(t,y)
        for margin,(_,strict,key,label) in zip(self.guard_function(t,y,outputs),self.guards):
            if strict and (not np.isfinite(margin) or margin<=0):
                raise Detencion('derived_validity',key+': '+label)
        value = np.asarray(self.function(t,y,outputs),dtype=float)
        if not np.all(np.isfinite(value)): raise Detencion('derived_nonfinite','The connected RHS is nonfinite.')
        return value

    def dominio(self,t,y):
        return np.asarray(self.guard_function(t,y,self.closure_values(t,y)),dtype=float)

    def describir_dominio(self,index):
        return self.guards[index][3]

    def event_state(self,t,y):
        signature, margins = [], []
        for j,stage in enumerate(self.stages):
            sig, rows = stage._closure_event_state(t,y[self.offsets[j]:self.offsets[j+1]])
            signature.extend(sig); margins.extend(rows)
        return tuple(signature), margins

    def firma(self,t,y):
        return self.event_state(t,y)[0]

    def admite(self,signature):
        closures = {c.owner:c for s in self.stages for c in s.closures}
        for owner,phases in signature:
            reason = closures[owner].admits(phases)
            if reason: return reason
        return None
