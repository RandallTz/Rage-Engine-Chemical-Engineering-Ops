"""Public reaction-provider adapter for replayed, semi-explicit extent constraints."""
import math
import numpy as np
import sympy as sp
from core.mathematics.numeric_lowering import lambdify_numeric
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
        thermal=getattr(system,'thermal_reaction',False)
        if not system.is_dae or len(config['volumes'])!=1 or system.closures and not thermal:
            reject('reaction_formulation_unsupported','Use one smooth reaction extent block in version 4, with prescribed T/P or with the package closure of its own region.', 'motores.equilibriumReactions')
        self.owner,self.declaration=next(iter(config['volumes'].items()))
        entry=self.declaration
        volume=next(v for v in system.model['volumenes'] if v['id']==self.owner)
        caloric=volume['termodinamica'].get('supuesto') if volume['termodinamica'].get('tipo')=='supuesto' else None
        # B3 part 2: the region's own package closure is the caloric closure.
        self.closure=next((c for c in system.closures if c.owner==self.owner),None) if thermal else None
        self.stage='initialization'
        if volume['balances']['energia'] and self.closure is None:
            # F2 precondition: the volume's recorded caloric assumption is not
            # the provider's caloric potential, so an energy balance would mix
            # two thermodynamic descriptions of one region. A u_lineal (or any
            # declared) inventory has no formation reference: it would lose the
            # reaction heat.
            reject('reaction_thermal_coupling_unsupported',
                   'Thermal coupling is not admitted: the volume caloric assumption '+repr(caloric)+' differs from the '
                   'reaction provider caloric potential (the provider partial molar enthalpies with formation reference), '
                   'so the reaction heat would be lost. Select the reaction package as the volume closure (select_closure, '
                   'with the formation reference of the declaration anchor) or use prescribed T/P with an inactive energy balance.',
                   'volumenes.'+self.owner+'.termodinamica' if caloric else 'motores.equilibriumReactions')
        if self.closure is not None:
            self._thermal_preconditions(system,volume,entry)
            self.caloric_limitation=('Thermal coupling: T = T(H, P, n(xi)) from the package closure of '+self.owner+' (specification '
                +self.closure.spec+', formation anchor '+str(self.closure.anchor)+'), the same provider as the reaction potentials; '
                'the formation-referenced enthalpy carries the reaction heat once and the energy balance has no volumetric source.')
        else:
            self.caloric_limitation=('Caloric limitation: the recorded volume caloric assumption '+repr(caloric)+' is unused here '
                '(prescribed T and P, inactive energy balance) and is not the provider caloric potential; thermal coupling needs '
                'the reaction package as the volume closure.')
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
        self.provider,self.activity=self._provider(system,entry)
        self.nu=sp.Matrix([[sp.Rational(v) for v in r['stoichiometry']] for r in entry['reactions']])
        self.independent=list(self.nu.T.rref()[1]);self.N=self.nu[self.independent,:].T
        if [r['quantityId'] for r in system.algebraic_rows]!=entry['extentIds'] or [r['equationId'] for r in system.algebraic_rows]!=[entry['reactions'][i]['equationId'] for i in self.independent]:
            reject('reaction_partition_invalid','Select only independent extents in the declared reaction order.', 'motores.derivedExecution.algebraic')
        self.temperature,self.pressure=[si_magnitude(system._expand(system._quantity(entry[f]))).subs(system.parameter_values) for f in ('temperatureId','pressureId')]
        self.T_local={}
        if self.closure is not None:
            # T is the closure output; the symbolic checks below use a positive
            # placeholder and every evaluation uses T(H, P, n(xi)).
            if system._quantity(entry['temperatureId'])!=self.closure.T:
                reject('reaction_coordinate_mismatch','Select the closure temperature of the reaction region.','motores.equilibriumReactions.volumes.'+self.owner+'.temperatureId')
            self.temperature=sp.Symbol('closure_temperature',positive=True)
            self.T_local={self.closure.T:self.temperature}
            if not (self.pressure.is_number and float(self.pressure)>0):
                reject('reaction_thermal_coupling_unsupported','The coupled region needs its prescribed pressure datum.','motores.equilibriumReactions.volumes.'+self.owner+'.pressureId')
        elif not all(v.is_number and float(v)>0 for v in (self.temperature,self.pressure)):
            reject('reaction_thermal_coupling_unsupported','T and P must be prescribed, or T must be the output of the region package closure (thermal coupling).', 'motores.equilibriumReactions')
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
            expression=si_magnitude(system._expand(node.equation.lhs-node.equation.rhs)).subs(system.parameter_values).xreplace(self.T_local)
            # Unsubstituted species keep the generic mu_i; substituted ones use
            # the recorded constitutive right-hand side.
            terms=[system.graph.nodes[closures[i]].equation.rhs if i in closures else q for i,q in enumerate(mu)]
            expected=si_magnitude(system._expand(sum(self.nu[j,i]*q for i,q in enumerate(terms)))).subs(system.parameter_values).xreplace(self.T_local)/RT
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
                # provider potential must now be a recorded Model relation.
                reject('reaction_chemical_potential_not_recorded',
                       'Record '+self._form_text()+' for every reacting species as a thermodynamic constitutive relation '
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
        self.n_function=lambdify_numeric(self.arguments,self.amounts,'numpy')
        self.ref_function=lambdify_numeric(self.arguments,self.references,'numpy')
        self.residual=lambda *args: np.asarray(self.state(args)['affinity_RT'])[self.independent]
        self.jacobian=self._jacobian
        self.last_certificate=None
        if self.closure is not None:
            self.energy_function=lambdify_numeric(self.arguments,si_magnitude(system._expand(self.closure.energy)).subs(system.parameter_values),'numpy')

    def _jacobian(self, *args):
        """dg/dxi = (dg/dn) N, plus at fixed H and P the temperature path
        (dg/dT)(dT/dxi) = Delta_r h Delta_r h^T / (R T^2 C_p) (Gibbs-Helmholtz)."""
        state=self.state(args);T=float(state['T'])
        rows=np.asarray(self.nu[self.independent,:],dtype=float)
        J=rows@np.asarray(state['dmu_dn'])@np.asarray(self.N,dtype=float)/(chemistry.R*T)
        if self.closure is not None:
            enthalpy=rows@np.asarray(state['h_partial'])
            J=J+np.outer(enthalpy,enthalpy)/(chemistry.R*T*T*float(state['closure']['dH_dT']))
        return J

    def _thermal_preconditions(self, system, volume, entry):
        """B3 part 2 admission: the volume's caloric closure is the reaction provider.

        Each precondition is a located rejection: same package, same formation
        anchor (None would lose the reaction heat), a single phase of the declared
        kind, a prescribed pressure (PH: a rigid incompressible liquid with
        Delta_r v != 0 does not determine P), an active energy balance with no
        volumetric source (a source equal to the reaction heat would count it twice)."""
        owner=self.owner;closure=self.closure
        if entry['provider']!='package' or volume['termodinamica'].get('paqueteId')!=entry.get('packageId'):
            reject('reaction_caloric_provider_mismatch','The volume closure package must be the reaction provider package '+repr(entry.get('packageId'))+'.',
                   'volumenes.'+owner+'.termodinamica.paqueteId')
        if closure.anchor is None:
            reject('reaction_caloric_reference_missing','The closure has no recorded formation reference, so its energies would lose the reaction heat; '
                   'record the '+('liquid' if entry['anchor']=='liquid' else 'gas')+' formation reference of the declaration anchor.',
                   'motores.thermodynamicDerivation.volumes.'+owner)
        if closure.anchor!=entry['anchor']:
            reject('reaction_caloric_reference_mismatch','The closure formation reference '+repr(closure.anchor)+' differs from the reaction anchor '+repr(entry['anchor'])+'.',
                   'motores.thermodynamicDerivation.volumes.'+owner)
        kind={'liquido':'liquid','vapor':'vapor'}.get(entry['phaseId'])
        if not closure.single or closure.kind!=kind:
            reject('reaction_phase_policy_unsupported','A coupled reaction region is one phase of the declared kind: record the single-phase '
                   +str(kind)+' policy.','volumenes.'+owner+'.termodinamica.politica')
        if closure.spec!='PH':
            if kind=='liquid':
                reject('reaction_rigid_liquid_ill_posed','A rigid incompressible liquid region with Delta_r v != 0 does not determine its pressure, '
                       'and the single-phase UV closure keeps P a datum (dropping P Delta_r v work). Use the prescribed-pressure (PH) region.',
                       'volumenes.'+owner+'.frontera')
            reject('reaction_rigid_volume_unsupported','The single-phase UV closure keeps P a datum; a rigid coupled vapour region needs a '
                   'pressure-from-volume closure. Use the prescribed-pressure (PH) region.','volumenes.'+owner+'.frontera')
        if not volume['balances']['energia']:
            reject('reaction_energy_balance_required','The coupled region integrates its energy inventory.','volumenes.'+owner+'.balances.energia')
        from core.balances import energy_derivation as energy
        from core.modelo.operation_journal import replay
        journal=system.model['motores'].get('energyDerivation',{}).get('volumes',{}).get(owner)
        state=replay(journal,energy.fundamental,energy.normalize)[-1] if journal else {}
        if not state.get('sinFuenteVolumetrica'):
            reject('reaction_heat_double_counted','Record no_volume_source: the formation-referenced enthalpy already carries the reaction heat, '
                   'so a volumetric source equal to it would count it twice.','motores.energyDerivation.volumes.'+owner)

    def temperature_box(self):
        """The declared validity interval of the closure temperature (Model domain premises)."""
        located='volumenes.'+self.owner+'.termodinamica'
        lower,upper=[],[]
        for premise in self.system.graph.domains.values():
            if premise.quantity!=self.closure.T or premise.domain!='interval':
                continue
            scale=premise.scale if premise.explicit_units else sp.S.One
            lower.append(si_magnitude(premise.allowed.start*scale));upper.append(si_magnitude(premise.allowed.end*scale))
        if not lower:
            reject('reaction_temperature_box_missing','Declare the validity interval of the closure temperature (declare_domain, interval) '
                   'so that the coupled extent Jacobian is certified over it and checked at runtime.',located)
        lo,hi=max(lower),min(upper)
        if not (lo.is_number and hi.is_number and 0<lo<hi):
            reject('reaction_temperature_box_missing','The declared closure temperature interval must be finite, positive and nonempty.',located)
        from fractions import Fraction
        return [outward(Fraction(str(lo)),False),outward(Fraction(str(hi)),True)]

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
        local={**{a:s for a,s in zip(amounts,x)},pressure:p,**self.T_local}
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
            if self.activity is not None:
                closures[i]=key;self._liquid_closure(system,key,value,i,x,p,mu,amounts)
                continue
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
            # Divided by T: with a coupled region T is the positive closure placeholder.
            offset=sp.N(sp.expand(standard.subs(functions[0],0).subs({**{v:1 for v in x},p:P0})/T),30)
            if not offset.is_number or abs(offset)>1e-12*R:
                reject('reaction_standard_pressure_mismatch','The recorded standard pressure must equal the provider ideal_gas_P0 reference, 1e5 Pa.',key)
            closures[i]=key;self.standard_functions[key]=functions[0]
        return closures

    def _provider(self, system, entry):
        """The executed provider named by the declaration, and its activity form.

        ideal_gas: IdealGasPhase, vapor, ideal_gas_P0, gas anchor (F5-C1, unchanged).
        package:   the declared package's single liquid phase, pure_liquid_TP. The
        package's liquid model fixes the functional form the recorded mu_i must
        have: 'activity' (UNIFAC: one activity coefficient per species) or
        'ideal' (ideal solution, no activity coefficient). Other liquid models
        (NRTL) are not admitted. Returns (provider, None | 'activity' | 'ideal').
        """
        located='motores.equilibriumReactions.volumes.'+self.owner
        if entry['provider']=='ideal_gas':
            if 'packageId' in entry:
                reject('reaction_package_unexpected','The ideal_gas provider executes no package; remove packageId.',located+'.packageId')
            if (entry['phaseId'],entry['standardState'],entry['anchor'])!=('vapor','ideal_gas_P0','gas'):
                reject('STANDARD_STATE_MISMATCH','Ideal gas requires vapor, gas formation anchor and ideal_gas_P0.', located)
            try:return chemistry.IdealGasPhase(entry['species']),None
            except chemistry.ChemicalEquilibriumError as error:
                reject(error.code,str(error),located+'.species')
        vapour=(entry['phaseId'],entry['standardState'])==('vapor','ideal_gas_P0') and self.closure is not None
        if (entry['phaseId'],entry['standardState'])!=('liquido','pure_liquid_TP') and not vapour:
            reject('STANDARD_STATE_MISMATCH','A package reaction region is one liquid phase with the pure_liquid_TP standard state, '
                   'or (with its own package caloric closure) one vapour phase with the ideal_gas_P0 standard state.', located)
        if 'packageId' not in entry:
            reject('reaction_package_missing','Name the thermodynamic package whose phase executes the reaction potentials.',located+'.packageId')
        from core import catalogo, mezclas, unifac
        from core.termodinamica.derived_bridge import PACKAGE_ALIASES
        package=next(p for p in system.model['termodinamica']['paquetes'] if p['id']==entry['packageId'])
        if package.get('datosPuros'):
            reject('PROVIDER_UNSUPPORTED','Reaction bounds enclose the published package data only; pure-data substitutions are not admitted.',located+'.packageId')
        name=PACKAGE_ALIASES.get(package['modelo']['id'],package['modelo']['id'])
        if name not in mezclas.PAQUETES:
            reject('PROVIDER_UNSUPPORTED','Unknown thermodynamic package '+repr(package['modelo']['id'])+'.',located+'.packageId')
        if vapour:
            # The package vapour is the ideal-gas mixture of the package pure data
            # (Poling cp, formation reference of the anchor): the recorded mu_i has
            # the ideal-gas form, as for the ideal_gas provider.
            try:
                sistema=mezclas.Sistema(name,entry['species'])
                return chemistry.PackagePhase(sistema,'vapor',anchor=entry['anchor']),None
            except mezclas.FaltaParametro as error:
                reject('PROVIDER_UNSUPPORTED','The package cannot represent the declared species: '+str(error),located+'.packageId')
            except chemistry.ChemicalEquilibriumError as error:
                reject(error.code,str(error),located+('.anchor' if error.code=='LIQUID_ANCHOR_REQUIRED' else '.species'))
        # The package description names its liquid model, hence the form the
        # recorded mu_i must have; only enclosed models are admitted.
        model=mezclas.PAQUETES[name].liquido
        activity='activity' if model.startswith('unifac_') else 'ideal' if model=='ideal' else None
        if activity is None:
            reject('PROVIDER_UNSUPPORTED','The liquid model '+repr(model)+' of package '+repr(package['modelo']['id'])+
                   ' has no certified reaction bounds (UNIFAC and the ideal solution have; NRTL is not extended).',located+'.packageId')
        # The catalog's liquid-only rule (not a species branch): such species
        # exist only in a liquid-only system, whose formation anchor is liquid.
        liquid_only=any(c in catalogo.REGISTRO_SOLO_LIQUIDO for c in entry['species'])
        try:
            sistema=mezclas.Sistema(name,entry['species'],solo_liquido=liquid_only)
        except mezclas.FaltaParametro as error:
            reject('PROVIDER_UNSUPPORTED','The package cannot represent the declared species: '+str(error),located+'.packageId')
        if not isinstance(sistema.liq,unifac.LiquidoUNIFAC if activity=='activity' else mezclas.LiquidoIdeal):
            reject('PROVIDER_UNSUPPORTED','The executed liquid '+type(sistema.liq).__name__+' is not the declared '+repr(model)+' model.',located+'.packageId')
        try:
            return chemistry.PackagePhase(sistema,'liquido',anchor=entry['anchor']),activity
        except chemistry.ChemicalEquilibriumError as error:
            reject(error.code,str(error),located+('.anchor' if error.code=='LIQUID_ANCHOR_REQUIRED' else '.species'))

    def _provider_text(self):
        if self.activity is None and isinstance(self.provider,chemistry.PackagePhase):
            return ('package '+self.declaration['packageId']+' vapour ('+self.provider.sistema.paquete.id+', ideal gas, formation anchor '
                    +self.provider.anchor+')')
        if self.activity is None:
            return 'ideal_gas provider'
        return ('package '+self.declaration['packageId']+' liquid ('+self.provider.sistema.paquete.id+', '
                +('activity model '+type(self.provider.sistema.liq).__name__ if self.activity=='activity' else 'ideal solution')
                +', formation anchor '+self.provider.anchor+')')

    def _form_text(self):
        if self.activity is None:
            return 'mu_i = mu_i0(T) + R T log(n_i P/(n P0))'
        return 'mu_i = mu_i*(T,P) + R T log(n_i/n'+(' gamma_i)' if self.activity=='activity' else ')')

    def _liquid_closure(self, system, key, value, i, x, p, mu, amounts):
        """Match a recorded liquid mu_i to the executed package phase.

        The provider executes mu_i = mu_i*(T,P) + R T ln(x_i gamma_i) with the
        package's pure-liquid standard potential and, for an activity model,
        its activity coefficient. With x_i = n_i/sum_k n_k, the recorded right
        side minus R T log(x_i) must be exactly one standard-potential function
        of time plus, for an activity model, R T log of one activity-coefficient
        function of time, both unused elsewhere; nothing may depend on the
        amounts or on pressure otherwise, and no constant offset may remain.
        """
        R=sp.Rational(str(chemistry.R));T=self.temperature
        # d value/d x_i = R T (1/x_i - 1/n) names the relation's gas constant.
        scale=sp.simplify(sp.diff(value,x[i])/(T*(1/x[i]-1/sum(x))))
        if scale.is_number and sp.simplify(scale-R)!=0:
            reject('reaction_gas_constant_mismatch','The chemical-potential relation must use the provider gas constant 8.314462618 J/(mol K).',key)
        rest=sp.expand_log(value-R*T*sp.log(x[i]/sum(x)),force=True)
        functions=list(rest.atoms(sp.core.function.AppliedUndef))
        forbidden=[*mu,*amounts,*system.states,*system.algebraic_quantities]
        used={f for k,fs in self.standard_functions.items() if k!=key for f in fs}
        mismatch=lambda: reject('reaction_chemical_potential_provider_mismatch',
            'The recorded relation is not the '+self._form_text()+' form executed by the declared package liquid '
            '(pure_liquid_TP standard potential'+(' and activity coefficient' if self.activity=='activity' else '')+').',key)
        if any(f.args!=(system.time,) or f in forbidden or f in used for f in functions):
            mismatch()
        standard=[f for f in functions if sp.simplify(sp.diff(rest,f)-1)==0]
        gamma=[f for f in functions if f not in standard and sp.simplify(sp.diff(rest,f)*f-R*T)==0]
        if len(standard)!=1 or len(gamma)!=(1 if self.activity=='activity' else 0) or len(functions)!=1+len(gamma):
            mismatch()
        remainder=sp.expand_log(rest-standard[0]-sum((R*T*sp.log(g) for g in gamma),sp.S.Zero),force=True)
        if sp.simplify(remainder)!=0:
            mismatch()
        self.standard_functions[key]=(standard[0],*gamma)

    def virtual_condition(self, predicate):
        """Discharged Model premises on an eliminated virtual coordinate, or
        the log-argument premise of a matched liquid potential relation."""
        provider_source=self._provider_premise(predicate)
        if provider_source is not None:
            return provider_source
        if not isinstance(predicate,(sp.Unequality,sp.Contains)):
            return None
        value=(si_magnitude(self.system._expand(predicate.lhs-predicate.rhs)).subs(self.system.parameter_values).xreplace(self.T_local)
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
            # Coupled region: the normalization R T keeps the closure temperature,
            # which is positive wherever the closure executes (package T range).
            if ratio.free_symbols<={self.temperature} and ratio.is_nonzero:
                return key
        return None

    def _provider_premise(self, predicate):
        """x_i gamma_i > 0 from substituting a matched liquid mu_i relation.

        The activity coefficient is a provider function with no numerical
        lowering of its own, so the premise cannot become a margin. It holds
        wherever the provider executes: every state evaluation refuses a
        nonpositive amount (reaction_domain), the certified extent box has
        strictly positive amount bounds, and the package evaluates gamma_i as
        exp(ln gamma_i). Admitted only when the premise is exactly a product of
        positive constants, matched activity coefficients, species amounts and
        their total; anything else stays an ordinary margin. Returns the
        relation row that introduced the coefficient, or None.
        """
        if self.activity!='activity' or not isinstance(predicate,(sp.StrictGreaterThan,sp.StrictLessThan)):
            return None
        gammas={fs[1]:key for key,fs in self.standard_functions.items() if isinstance(fs,tuple) and len(fs)==2}
        system=self.system
        value=si_magnitude(system._expand(predicate.lhs-predicate.rhs)).subs(system.parameter_values)
        if isinstance(predicate,sp.StrictLessThan):
            value=-value
        present=[g for g in value.atoms(sp.core.function.AppliedUndef) if g in gammas]
        if len(present)!=1:
            return None
        total=sum(self.amounts,sp.S.Zero)
        sign=1
        numerator,denominator=sp.fraction(sp.together(value))
        for side in (numerator,denominator):
            for factor in sp.Mul.make_args(side):
                base,exponent=factor.as_base_exp()
                if not exponent.is_Integer:
                    return None
                if base.is_number:
                    if not base.is_real or base==0:
                        return None
                    sign*=1 if base>0 or exponent%2==0 else -1
                    continue
                if base in gammas:
                    continue
                match=[s for s in (1,-1) for a in [*self.amounts,total] if sp.expand(base-s*a)==0]
                if not match:
                    return None
                sign*=1 if match[0]>0 or exponent%2==0 else -1
        return gammas[present[0]] if sign>0 else None

    def state(self,args):
        n=self.n_function(*args)
        closure=None
        if self.closure is None:
            T=float(self.temperature)
        else:
            if not np.all(np.asarray(n,dtype=float)>0):
                raise NonlinearError('reaction_domain','An amount is zero or negative: ln a_i is not finite; nothing is clipped.')
            closure=self._closure_state(args,n)
            T=float(closure['T'])
        state=chemistry.evaluate_reactions(self.provider,np.asarray(self.nu,dtype=float),T=T,P=float(self.pressure),n=n,phase_id=self.declaration['phaseId'],standard_state=self.declaration['standardState'])
        if not state['valid']:
            raise NonlinearError('reaction_domain',state['validity']['message'])
        if closure is not None:
            state['closure']=closure
        return state

    def _closure_state(self,args,n):
        """T(H, P, n(xi)) of the region's package closure; a failure at a trial point is
        an inadmissible evaluation for the shared Newton (ValueError), never clipped."""
        from core.solvers import Detencion
        try:
            return self.closure.temperature_at(n,float(self.energy_function(*args)),float(self.pressure),self.stage)
        except (Detencion,LoweringError) as error:
            raise ValueError('Package closure of '+self.owner+': '+str(error)) from error

    def _closure_row(self,args):
        from core.solvers import Detencion
        n=self.n_function(*args)
        try:
            return self.closure.outputs_at(n,float(self.energy_function(*args)),float(self.pressure),self.stage)
        except (Detencion,LoweringError) as error:
            raise ValueError('Package closure of '+self.owner+': '+str(error)) from error

    def set_conditions(self,margins):
        if self.closure is None:
            return super().set_conditions(margins)
        # Margins may use closure outputs (T, V, ...), evaluated at n(xi).
        self.condition_arguments=[*self.arguments,*self.closure.outputs]
        self.conditions=[]
        for expr,strict,key,label in margins:
            value=si_magnitude(expr).subs(self.system.parameter_values)
            self._validate_condition(value)
            self.conditions.append((sp.lambdify(self.condition_arguments,value,modules='math'),strict,key))

    def _validate_condition(self,expression):
        if expression in self.condition_arguments or expression.is_Number:
            return
        if expression.is_Add or expression.is_Mul or expression.is_Pow and expression.exp.is_Integer:
            for arg in (expression.args if not expression.is_Pow else (expression.base,)):
                self._validate_condition(arg)
            return
        raise NonlinearError('nonlinear_unsupported_expression','Only bound arithmetic with integer powers and guarded division is admitted: '+str(expression))

    def _coupled_solve(self,t,state,stage):
        from core.solvers.nonlinear import solve
        args=[float(t),*map(float,state[:len(self.system.states)])]
        # Margins of the recorded closure-temperature interval: the extent proof
        # covers the extent box times that interval, and only this runtime
        # check keeps T inside it (B3 part 2 review R2).
        interval_keys={key for key,premise in self.system.graph.domains.items()
                       if premise.quantity==self.closure.T and premise.domain=='interval'}
        excluded=[]
        def admissible(z):
            if not self.conditions:
                return True
            try:
                outputs=self._closure_row([*args,*z])
            except (ValueError,NonlinearError):
                return False
            for function,strict,key in self.conditions:
                value=float(function(*args,*z,*outputs))
                if not math.isfinite(value) or value<0 or strict and value==0:
                    if key in interval_keys:
                        excluded.append(float(outputs[0]))
                    return False
            return True
        try:
            z,detail=solve(lambda z:self.residual(*args,*z),
                           lambda z:np.array(self.jacobian(*args,*z)).reshape(len(z),len(z)),
                           self.seed,self.bounds,self.scales,self.residual_scales,
                           residual_tolerance=self.config['residualTolerance'],step_tolerance=self.config['stepTolerance'],
                           max_iterations=self.config['maxIterations'],max_backtracks=self.config['maxBacktracks'],
                           admissible=admissible)
        except NonlinearError as error:
            if excluded and error.code in ('nonlinear_invalid_seed','nonlinear_domain'):
                box=self.temperature_box()
                error=NonlinearError('reaction_temperature_out_of_interval',
                    'The closure temperature of '+self.owner+' left its recorded validity interval ['+repr(box[0])+', '+repr(box[1])+
                    '] K (last trial T = '+repr(excluded[-1])+' K). The index-one proof covers the extent box times that interval '
                    'only; widen the recorded interval (declare_domain on the closure temperature) if the state is physical.',
                    **{k:v for k,v in error.diagnostic.items() if k not in ('code','message','terminationReason')})
                error.diagnostic.update(self.location(t,stage))
                error.diagnostic.update(path='volumenes.'+self.owner+'.termodinamica',temperatureInterval=box,temperature=excluded[-1])
            else:
                if stage!='initialization' and error.code=='nonlinear_invalid_seed':
                    error=NonlinearError('nonlinear_domain','The current state is outside the admitted nonlinear domain.',
                                         **{k:v for k,v in error.diagnostic.items() if k not in ('code','message','terminationReason')})
                error.diagnostic.update(self.location(t,stage))
            error.diagnostics=[error.diagnostic]
            raise error
        self.calls+=1
        self.last={**detail,**self.location(t,stage)}
        return z,detail['residualNorm']

    def certify_index(self,bounds):
        try:
            reference=[tuple(outward(v,i==1) for i,v in enumerate(interval(e,bounds))) for e in self.references]
        except ValueError as error:
            reject('reaction_reference_not_certified',str(error),'motores.equilibriumReactions.volumes.'+self.owner+'.referenceIds')
        thermal=self.closure is not None
        temperature=self.temperature_box() if thermal else [float(self.temperature)]*2
        try:
            proof=certify_extent(self.provider,self.nu.tolist(),reference,[bounds[q] for q in self.unknowns],
                temperature,[float(self.pressure)]*2,phase_id=self.declaration['phaseId'],standard_state=self.declaration['standardState'],
                thermal=thermal)
        except LoweringError as error:
            for diagnostic in error.diagnostics:
                suffix=diagnostic.get('path','equilibriumReactions').removeprefix('equilibriumReactions').lstrip('.')
                diagnostic['path']='motores.equilibriumReactions.volumes.'+self.owner+('.'+suffix if suffix else '')
            raise
        self.extent_proof=proof
        return {'index':1,'determinant':'det((dg/dn) N + R T^2 (dg/dT)(dg/dT)^T / C_p)' if thermal else 'det((dg/dn) N)',
                **({'temperatureBox':proof['temperatureBox'],'heatCapacityBounds':proof['heatCapacityBounds']} if thermal else {}),
                'determinantBounds':[str(v) for v in proof['determinantBounds']],
                'proof':proof['method']+' Chemical-potential relations: '+str([self.potential_rows[i] for i in sorted(self.potential_rows)])
                    +' executed by the '+self._provider_text()+'. Provider fingerprints: '+str(proof['provider']['fingerprints'])+' '+self.caloric_limitation}

    def is_consequence(self,expression):
        return sp.simplify(si_magnitude(expression).subs(self.system.parameter_values))==0

    def evaluate(self,t,state,stage='runtime'):
        self.stage=stage
        if self.closure is None:
            z,residual=super().evaluate(t,state,stage)
        else:
            z,residual=self._coupled_solve(t,state,stage)
        args=[float(t),*map(float,state[:len(self.system.states)]),*z]
        evaluated=self.state(args)
        certificate=chemistry.certify_reactions(evaluated,n0=self.ref_function(*args),A=chemistry.element_matrix(self.provider.cas)[0])
        if certificate.get('certified') is not True:
            raise NonlinearError('reaction_not_certified','The recomputed reaction/conservation certificate failed.',**self.location(t,stage))
        self.last_certificate=certificate
        return z,residual
