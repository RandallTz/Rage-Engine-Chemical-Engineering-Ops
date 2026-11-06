"""Public reaction-provider adapter for replayed, semi-explicit extent constraints."""
import numpy as np
import sympy as sp
from core.mathematics.constants import si_magnitude
from core.reactions import chemical_equilibrium as chemistry
from core.solvers.nonlinear import NonlinearError
from .nonlinear_block import NonlinearBlock
from .reaction_extent import certify_extent, reject, outward
from .dae import interval
from .derived_graph import LoweringError


class ReactionBlock(NonlinearBlock):
    def __init__(self, system, residuals):
        config=system.model['motores']['equilibriumReactions']
        if not system.is_dae or len(config['volumes'])!=1 or system.closures:
            reject('reaction_formulation_unsupported','Use one smooth reaction extent block with prescribed T/P in version 4.', 'motores.equilibriumReactions')
        self.owner,self.declaration=next(iter(config['volumes'].items()))
        entry=self.declaration
        volume=next(v for v in system.model['volumenes'] if v['id']==self.owner)
        caloric=volume['termodinamica'].get('supuesto') if volume['termodinamica'].get('tipo')=='supuesto' else None
        if volume['balances']['energia']:
            # F2 precondition: the volume's recorded caloric assumption is not
            # the provider's caloric potential, so an energy balance would mix
            # two thermodynamic descriptions of one region.
            reject('reaction_thermal_coupling_unsupported',
                   'Thermal coupling is not admitted: the volume caloric assumption '+repr(caloric)+' differs from the '
                   'reaction provider caloric potential (ideal-gas cp integrals and formation enthalpies). Reconcile the '
                   'caloric closure with the provider first; until then use prescribed T/P with an inactive energy balance.',
                   'volumenes.'+self.owner+'.termodinamica' if caloric else 'motores.equilibriumReactions')
        self.caloric_limitation=('Caloric limitation: the recorded volume caloric assumption '+repr(caloric)+' is unused here '
            '(prescribed T and P, inactive energy balance) and is not the provider caloric potential; thermal coupling stays rejected '
            'until it is reconciled with the provider.')
        dimensions={'temperatureId':{'Theta':1},'pressureId':{'M':1,'L':-1,'T':-2}}
        for field,expected in dimensions.items():
            if system._dim(system._quantity(entry[field]))!=expected:
                reject('reaction_units_mismatch','Reaction state quantities must use physical SI dimensions.', 'motores.equilibriumReactions.'+field)
        for field in ('amountIds','referenceIds','extentIds'):
            if any(system._dim(system._quantity(q))!={'N':1} for q in entry[field]):
                reject('reaction_units_mismatch','Amounts, references and extents have substance-amount dimensions.','motores.equilibriumReactions.'+field)
        expected_amounts=[sp.Function('n_'+str(c)+'__'+self.owner)(system.time) for c in volume['componenteIds']]
        if [system._quantity(q) for q in entry['amountIds']]!=expected_amounts:
            reject('reaction_coordinate_mismatch','Select the same species amounts used by the fundamental thermodynamic graph.','motores.equilibriumReactions.amountIds')
        fixed=[system._quantity(q) for q in system.selection['initialValues']]
        species_quantities=expected_amounts+[sp.Function('m__'+self.owner+'__'+str(c))(system.time) for c in volume['componenteIds']]
        if any(q in fixed for q in species_quantities):
            reject('reaction_fixed_species_initialization','Initialize conserved coordinates; independently fixed species would overconstrain equilibrium initialization.','motores.derivedExecution.initialValues')
        if entry['provider']!='ideal_gas':
            reject('PROVIDER_UNSUPPORTED','Package-phase equilibrium reaction bounds are not admitted by this compiler.', 'motores.equilibriumReactions.volumes.'+self.owner+'.provider')
        if (entry['phaseId'],entry['standardState'],entry['anchor'])!=('vapor','ideal_gas_P0','gas'):
            reject('STANDARD_STATE_MISMATCH','Ideal gas requires vapor, gas formation anchor and ideal_gas_P0.', 'motores.equilibriumReactions.volumes.'+self.owner)
        try:self.provider=chemistry.IdealGasPhase(entry['species'])
        except chemistry.ChemicalEquilibriumError as error:
            reject(error.code,str(error),'motores.equilibriumReactions.volumes.'+self.owner+'.species')
        self.nu=sp.Matrix([[sp.Rational(v) for v in r['stoichiometry']] for r in entry['reactions']])
        self.independent=list(self.nu.T.rref()[1]);self.N=self.nu[self.independent,:].T
        if [r['quantityId'] for r in system.algebraic_rows]!=entry['extentIds'] or [r['equationId'] for r in system.algebraic_rows]!=[entry['reactions'][i]['equationId'] for i in self.independent]:
            reject('reaction_partition_invalid','Select only independent extents in the declared reaction order.', 'motores.derivedExecution.algebraic')
        self.temperature,self.pressure=[si_magnitude(system._expand(system._quantity(entry[f]))).subs(system.parameter_values) for f in ('temperatureId','pressureId')]
        if not all(v.is_number and float(v)>0 for v in (self.temperature,self.pressure)):
            reject('reaction_thermal_coupling_unsupported','T and P must be prescribed; a coupled thermal index proof is not available.', 'motores.equilibriumReactions')
        self.references=[si_magnitude(system._expand(system._quantity(q))).subs(system.parameter_values) for q in entry['referenceIds']]
        amounts=[si_magnitude(system._expand(system._quantity(q))).subs(system.parameter_values) for q in entry['amountIds']]
        if any(system._quantity(q) in system.states for q in entry['amountIds']):
            reject('reaction_partition_invalid','Integrate conserved coordinates, never all species plus equilibrium constraints.', 'motores.derivedExecution.states')
        self.amounts=[r+sum(self.N[i,j]*z for j,z in enumerate(system.algebraic_quantities)) for i,r in enumerate(self.references)]
        if any(sp.expand(a-b)!=0 for a,b in zip(amounts,self.amounts)) or any(r.has(*system.algebraic_quantities) for r in self.references):
            reject('reaction_coordinate_mismatch','Recorded amounts must be n_ref + N xi with extent-independent references.', 'motores.equilibriumReactions.amountIds')
        # Every residual must be the actual normalized chemical affinity from
        # the Gibbs differential, not a user-supplied function or final formula.
        mu=[sp.Function('mu_'+str(c)+'__'+self.owner)(system.time) for c in volume['componenteIds']]
        RT=sp.Rational(str(chemistry.R))*self.temperature
        self.virtual_rows=set();self.potential_rows={};self.standard_functions={}
        located='motores.equilibriumReactions.volumes.'+self.owner
        for j,row in enumerate(entry['reactions']):
            node=system._equation(row['equationId'])
            visited=set()
            def visit(key):
                if key in visited:return
                visited.add(key)
                for parent in system.graph.nodes[key].inputs:visit(parent)
            visit(row['equationId'])
            fundamental='thermodynamics.'+self.owner+'.fundamental'
            if fundamental not in visited:
                reject('reaction_constraint_not_deduced','Select the normalized affinity derived from the fundamental Gibbs differential.', located+'.reactions.'+str(j))
            closures=self._potential_closures(system,visited,mu,expected_amounts,located)
            for i,key in closures.items():
                if self.potential_rows.setdefault(i,key)!=key:
                    reject('reaction_chemical_potential_ambiguous','Every reaction must use the same recorded chemical-potential relation of each species.',key)
            expression=si_magnitude(system._expand(node.equation.lhs-node.equation.rhs)).subs(system.parameter_values)
            # Unsubstituted species keep the generic mu_i; substituted ones use
            # the recorded constitutive right-hand side.
            terms=[system.graph.nodes[closures[i]].equation.rhs if i in closures else q for i,q in enumerate(mu)]
            expected=si_magnitude(system._expand(sum(self.nu[j,i]*q for i,q in enumerate(terms)))).subs(system.parameter_values)/RT
            same=lambda a,b:sp.simplify(sp.expand_log(a-b,force=True))==0
            if not same(expression,expected) and not same(expression,-expected):
                ratio=sp.simplify(expression/expected)
                if ratio.is_number and ratio not in (sp.S.One,-sp.S.One) and ratio != 0:
                    reject('reaction_gas_constant_mismatch',
                           'Normalize affinity with the provider gas constant 8.314462618 J/(mol K).',
                           located+'.reactions.'+str(j))
                reject('reaction_constraint_not_deduced','Select the normalized affinity derived from the fundamental Gibbs differential.', located+'.reactions.'+str(j))
            # A species with a zero column in every reaction contributes
            # mu_i * 0 and cannot be substituted; only reacting species need
            # their recorded potential.
            reacting={i for i in range(len(mu)) if any(self.nu[r,i]!=0 for r in range(self.nu.rows))}
            if not reacting<=set(closures):
                # Persisted F5-C1 documents stop at the generic affinity; the
                # ideal-gas potential must now be a recorded Model relation.
                reject('reaction_chemical_potential_not_recorded',
                       'Record mu_i = mu_i0(T) + R T log(n_i P/(n P0)) for every species as a thermodynamic constitutive relation '
                       '(declare_relation, relationKind constitutive) and substitute it into the selected affinity. '
                       'Documents saved before 5 November 2026 repairs need these two operations appended.',
                       located+'.reactions.'+str(j))
            for key in visited:
                if key.startswith('operation.'):
                    operation=system.replayed.definition['operations'][int(key.split('.')[1])-1]
                    allowed=('state_variation','divide','multiply','expand','factor','substitute','declare_relation')
                    if operation['kind'] not in allowed or operation['kind']=='declare_relation' and key not in closures.values():
                        reject('reaction_constraint_not_deduced','The virtual Gibbs chain must use recorded differential variations, the recorded chemical-potential relations and algebraic normalization.',key)
                    if operation['kind']=='substitute' and operation['relation'] not in closures.values():
                        reject('reaction_constraint_not_deduced','Only the recorded chemical-potential relations may be substituted into the equilibrium affinity.',key)
                    self.virtual_rows.add(key)
        # Reuse the common settings, damped Newton, guards and diagnostics.
        super().__init__(system,[sp.S.Zero]*len(residuals))
        self.forcing=residuals
        self.n_function=sp.lambdify(self.arguments,self.amounts,'numpy')
        self.ref_function=sp.lambdify(self.arguments,self.references,'numpy')
        self.residual=lambda *args: np.asarray(self.state(args)['affinity_RT'])[self.independent]
        self.jacobian=lambda *args: np.asarray(self.nu[self.independent,:],dtype=float)@np.asarray(self.state(args)['dmu_dn'])@np.asarray(self.N,dtype=float)/(chemistry.R*float(self.temperature))
        self.last_certificate=None

    def _potential_closures(self, system, visited, mu, amounts, located):
        """Recorded constitutive mu_i rows in the ancestry, checked against the executed provider.

        The provider executes mu_i = mu_i0(T) + R T ln(n_i P/(n_t P0)). A
        recorded row is admitted only if, with its data substituted, it is that
        function of (n, P) plus one undefined standard-potential function of
        time, with the provider's R and P0. No species or case branches.
        """
        closures={}
        pressure=system._quantity(self.declaration['pressureId'])
        x=[sp.Symbol('amount_'+str(i),positive=True) for i in range(len(amounts))];p=sp.Symbol('pressure',positive=True)
        local={**{a:s for a,s in zip(amounts,x)},pressure:p}
        data={q:system.parameter_values[s] for q,s in system.parameter_symbols.items() if q!=pressure}
        R=sp.Rational(str(chemistry.R));P0=sp.Rational(str(chemistry.P0));T=self.temperature
        for key in sorted(visited):
            node=system.graph.nodes[key]
            if node.rule!='declared_relation' or node.equation.lhs not in mu:
                continue
            if node.family!='thermodynamics' or node.kind!='constitutive':
                reject('reaction_chemical_potential_not_constitutive','A chemical potential enters the affinity only through a thermodynamic constitutive relation.',key)
            i=mu.index(node.equation.lhs)
            if i in closures:
                reject('reaction_chemical_potential_ambiguous','Record one chemical-potential relation per species.',key)
            value=si_magnitude(node.equation.rhs.xreplace(local)).xreplace(data)
            # Pressure derivative R T/P names the gas constant of the relation.
            scale=sp.simplify(sp.diff(value,p)*p/T)
            if scale.is_number and sp.simplify(scale-R)!=0:
                reject('reaction_gas_constant_mismatch','The chemical-potential relation must use the provider gas constant 8.314462618 J/(mol K).',key)
            standard=sp.expand_log(value-R*T*sp.log(x[i]*p/(sum(x)*P0)),force=True)
            functions=[f for f in standard.atoms(sp.core.function.AppliedUndef)]
            if (any(sp.simplify(sp.diff(standard,v))!=0 for v in [*x,p]) or len(functions)!=1
                    or functions[0].args!=(system.time,)
                    or any(f in functions for f in [*mu,*amounts,*system.states,*system.algebraic_quantities])
                    or any(k!=key and f==functions[0] for k,f in self.standard_functions.items())
                    or sp.simplify(sp.diff(standard,functions[0])-1)!=0):
                reject('reaction_chemical_potential_provider_mismatch',
                       'The recorded relation is not the ideal_gas provider form mu_i0(T) + R T log(n_i P/(n P0)) selected by the declaration.',key)
            # Constant in (n, P) by the derivative checks: evaluate it anywhere.
            offset=sp.N(standard.subs(functions[0],0).subs({**{v:1 for v in x},p:P0}),30)
            if not offset.is_number or abs(offset)>1e-12*abs(R*T):
                reject('reaction_standard_pressure_mismatch','The recorded standard pressure must equal the provider ideal_gas_P0 reference, 1e5 Pa.',key)
            closures[i]=key;self.standard_functions[key]=functions[0]
        return closures

    def virtual_condition(self, predicate):
        """Discharged Model premises on an eliminated virtual coordinate only."""
        if not isinstance(predicate,(sp.Unequality,sp.Contains)):
            return None
        value=(si_magnitude(self.system._expand(predicate.lhs-predicate.rhs)).subs(self.system.parameter_values)
               if isinstance(predicate,sp.Unequality) else None)
        for key,premise in self.system.graph.domains.items():
            condition=premise.expression
            if premise.domain!='nonzero' or not isinstance(premise.quantity,sp.Symbol):
                continue
            symbols=condition.free_symbols
            if len(symbols)!=1:
                continue
            symbol=next(iter(symbols))
            if any(e.has(symbol) for e in [*self.amounts,*self.references,*self.forcing]):
                continue
            if not any(self.system.graph.nodes[k].equation.has(symbol) for k in self.virtual_rows):
                continue
            if predicate==condition:
                return key
            if value is None:
                continue
            ratio=sp.cancel(value/symbol)
            if ratio.is_number and ratio.is_nonzero:
                return key
        return None

    def state(self,args):
        state=chemistry.evaluate_reactions(self.provider,np.asarray(self.nu,dtype=float),T=float(self.temperature),P=float(self.pressure),n=self.n_function(*args),phase_id=self.declaration['phaseId'],standard_state=self.declaration['standardState'])
        if not state['valid']:
            raise NonlinearError('reaction_domain',state['validity']['message'])
        return state

    def certify_index(self,bounds):
        try:
            reference=[tuple(outward(v,i==1) for i,v in enumerate(interval(e,bounds))) for e in self.references]
        except ValueError as error:
            reject('reaction_reference_not_certified',str(error),'motores.equilibriumReactions.volumes.'+self.owner+'.referenceIds')
        try:
            proof=certify_extent(self.provider,self.nu.tolist(),reference,[bounds[q] for q in self.unknowns],
                [float(self.temperature)]*2,[float(self.pressure)]*2,phase_id=self.declaration['phaseId'],standard_state=self.declaration['standardState'])
        except LoweringError as error:
            for diagnostic in error.diagnostics:
                suffix=diagnostic.get('path','equilibriumReactions').removeprefix('equilibriumReactions').lstrip('.')
                diagnostic['path']='motores.equilibriumReactions.volumes.'+self.owner+('.'+suffix if suffix else '')
            raise
        self.extent_proof=proof
        return {'index':1,'determinant':'det((dg/dn) N)','determinantBounds':[str(v) for v in proof['determinantBounds']],
                'proof':proof['method']+' Chemical-potential relations: '+str([self.potential_rows[i] for i in sorted(self.potential_rows)])
                    +' executed by the ideal_gas provider. Provider fingerprints: '+str(proof['provider']['fingerprints'])+' '+self.caloric_limitation}

    def is_consequence(self,expression):
        return sp.simplify(si_magnitude(expression).subs(self.system.parameter_values))==0

    def evaluate(self,t,state,stage='runtime'):
        z,residual=super().evaluate(t,state,stage)
        args=[float(t),*map(float,state[:len(self.system.states)]),*z]
        evaluated=self.state(args)
        certificate=chemistry.certify_reactions(evaluated,n0=self.ref_function(*args),A=chemistry.element_matrix(self.provider.cas)[0])
        if certificate.get('certified') is not True:
            raise NonlinearError('reaction_not_certified','The recomputed reaction/conservation certificate failed.',**self.location(t,stage))
        self.last_certificate=certificate
        return z,residual
