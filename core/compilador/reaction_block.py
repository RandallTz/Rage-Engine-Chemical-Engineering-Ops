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
        if volume['balances']['energia']:
            reject('reaction_thermal_coupling_unsupported','This first extent adapter requires prescribed T/P without a retained energy block.','motores.equilibriumReactions')
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
        mu=[sp.Function('mu_'+str(c)+'__'+self.owner)(system.time) for c in next(v for v in system.model['volumenes'] if v['id']==self.owner)['componenteIds']]
        RT=sp.Rational(str(chemistry.R))*self.temperature
        self.virtual_rows=set()
        for j,row in enumerate(entry['reactions']):
            node=system._equation(row['equationId'])
            visited=set()
            def visit(key):
                if key in visited:return
                visited.add(key)
                for parent in system.graph.nodes[key].inputs:visit(parent)
            visit(row['equationId'])
            fundamental='thermodynamics.'+self.owner+'.fundamental'
            expression=si_magnitude(system._expand(node.equation.lhs-node.equation.rhs)).subs(system.parameter_values)
            expected=sum(self.nu[j,i]*q for i,q in enumerate(mu))/RT
            ratio=sp.simplify(expression/expected)
            if fundamental in visited and ratio.is_number and ratio not in (sp.S.One,-sp.S.One) and ratio != 0:
                reject('reaction_gas_constant_mismatch',
                       'Normalize affinity with the provider gas constant 8.314462618 J/(mol K).',
                       'motores.equilibriumReactions.volumes.'+self.owner+'.reactions.'+str(j))
            if fundamental not in visited or sp.simplify(expression-expected)!=0 and sp.simplify(expression+expected)!=0:
                reject('reaction_constraint_not_deduced','Select the normalized affinity derived from the fundamental Gibbs differential.', 'motores.equilibriumReactions.volumes.'+self.owner+'.reactions.'+str(j))
            for key in visited:
                if key.startswith('operation.'):
                    operation=system.replayed.definition['operations'][int(key.split('.')[1])-1]
                    if operation['kind'] not in ('state_variation','divide','multiply','expand','factor'):
                        reject('reaction_constraint_not_deduced','The virtual Gibbs chain must use recorded differential variations and algebraic normalization.',key)
                    self.virtual_rows.add(key)
        # Reuse the common settings, damped Newton, guards and diagnostics.
        super().__init__(system,[sp.S.Zero]*len(residuals))
        self.forcing=residuals
        self.n_function=sp.lambdify(self.arguments,self.amounts,'numpy')
        self.ref_function=sp.lambdify(self.arguments,self.references,'numpy')
        self.residual=lambda *args: np.asarray(self.state(args)['affinity_RT'])[self.independent]
        self.jacobian=lambda *args: np.asarray(self.nu[self.independent,:],dtype=float)@np.asarray(self.state(args)['dmu_dn'])@np.asarray(self.N,dtype=float)/(chemistry.R*float(self.temperature))
        self.last_certificate=None

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
                'proof':proof['method']+' Provider fingerprints: '+str(proof['provider']['fingerprints'])}

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
