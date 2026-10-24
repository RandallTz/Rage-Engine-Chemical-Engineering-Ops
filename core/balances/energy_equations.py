"""First-law expression graph built from conservation and explicit premises.

The effective assumptions are obtained by replaying the saved journal. This
module constructs their proof, not a retrospective editing history. No equipment
identity or numerical solver configuration participates in the reduction.
"""
import sympy as sp
from core.modelo.equation_manipulation import EquationGraph
from core.modelo.operation_journal import replay
from .material_equations import VolumeIntegral as VI, BoundaryFlux as BF, Divergence as Div
from . import energy_derivation as energy


def linear_operators(expression):
    """Linearity and product expansion before applying integral identities."""
    def expand_operator(node):
        argument=sp.expand(node.args[0])
        if argument.is_Add:return sp.Add(*(node.func(term) for term in argument.args))
        coefficient,rest=argument.as_coeff_Mul()
        return coefficient*node.func(rest) if coefficient!=1 else node.func(argument)
    return sp.expand(expression.replace(lambda n:isinstance(n,(VI,BF,Div)),expand_operator))


def equation_graph(model,owner):
    volume=next(v for v in model['volumenes'] if v['id']==owner)
    entry=model.get('motores',{}).get('energyDerivation',{}).get('volumes',{}).get(owner)
    state=replay(entry,energy.fundamental,energy.normalize)[-1] if entry else energy.fundamental()
    graph=EquationGraph();units={};prefix='energy.'+owner+'.';counter=0
    t=sp.Symbol('t',real=True);xyz=sp.symbols('x y z',real=True)
    def field(name,unit,local=False,display=None):
        value=sp.Function(name+'__'+owner)(*xyz,t) if local else sp.Function(name+'__'+owner)(t)
        units[value]=unit
        if display:graph.names[value]=display
        return value
    rho=field('rho_mixture','kg/m3',True,r'\rho(\mathbf x,t)')
    e=field('e_specific','J/kg',True,r'e(\mathbf x,t)');u=field('u_specific','J/kg',True,r'u(\mathbf x,t)')
    kinetic=field('kinetic_specific','J/kg',True,r'e_c(\mathbf x,t)')
    h=field('h_specific','J/kg',True,r'h(\mathbf x,t)');p=field('p','Pa',True,r'p(\mathbf x,t)')
    velocity=field('velocity_energy','m/s',True,r'\mathbf v');boundary=field('boundary_velocity_energy','m/s',True,r'\mathbf v_b')
    heatflux=field('heat_flux_energy','W/m2',True,r'\mathbf q')
    stress=field('stress_power_flux','W/m2',True,r'\boldsymbol\sigma\cdot\mathbf v')
    viscous=field('viscous_power_flux','W/m2',True,r'\boldsymbol\tau\cdot\mathbf v')
    body=field('body_power_density','W/m3',True,r'\rho\mathbf b\cdot\mathbf v')
    source=field('energy_source_density','W/m3',True,r'r_v')
    E=field('E','J',display='E(t)');U=field('U','J',display='U(t)')
    current=prefix+'local'
    graph.add(current,sp.Derivative(rho*e,t,evaluate=False),-Div(rho*e*velocity)-Div(heatflux)+Div(stress)+body+source,
              'Local first law · total energy conservation',family='energy')
    def relation(name,left,right,title,kind='definition',conditions=(),inputs=()):
        key=prefix+name
        graph.add(key,left,right,title,'assumption' if kind=='constraint' else 'definition',inputs,conditions,'energy',kind=kind)
        return key
    def substitute(name,mapping,title,inputs=(),conditions=()):
        nonlocal current,counter
        counter+=1;key=prefix+name+'.'+str(counter)
        graph.substitute(key,current,mapping,title,conditions,inputs)
        # Evaluate algebra on the expression, preserving the inventory rate.
        eq=graph.nodes[key].equation
        graph.nodes[key].equation=sp.Eq(linear_operators(eq.lhs),linear_operators(eq.rhs),evaluate=False)
        current=key
    energy_def=relation('specific-definition',e,u+kinetic,'Define total specific energy')
    substitute('specific', {e:u+kinetic},'Substitute the specific-energy definition',(energy_def,))
    if state['sinCinetica']:
        premise=relation('kinetic-condition',kinetic,0,'Neglect kinetic specific energy','constraint',('Negligible kinetic energy compared with internal energy',))
        substitute('kinetic',{kinetic:0},'Apply the kinetic-energy approximation',(premise,))
    if state['separarPresion']:
        premise=relation('stress-definition',stress,-p*velocity+viscous,'Separate pressure and viscous traction power',conditions=('Simple Cauchy continuum; pressure part of stress is -p I',))
        substitute('stress',{stress:-p*velocity+viscous},'Substitute the pressure-stress decomposition',(premise,))
    for flag,quantity,label in [('sinConduccionLocal',heatflux,'local conductive heat flux'),('sinTrabajoViscoso',viscous,'viscous power flux'),('sinFuerzasVolumen',body,'body-force power'),('sinFuenteVolumetrica',source,'volumetric energy source')]:
        if state[flag]:
            premise=relation(flag+'.condition',quantity,0,'Declare zero '+label,'constraint',(flag+' is explicitly recorded',))
            substitute(flag,{quantity:0},'Apply zero '+label,(premise,))
    if state['presionUniforme']:
        P=field('P','Pa',display='P(t)')
        premise=relation('uniform-pressure',p,P,'Declare spatially uniform pressure','constraint')
        substitute('uniform-pressure',{p:P},'Apply the pressure dependency assumption',(premise,));p=P
    specific=u if state['sinCinetica'] else u+kinetic
    inventory=U if state['sinCinetica'] else E
    inventory_definition=relation('inventory-definition',inventory,VI(rho*specific),'Define the control-volume energy inventory')
    internal_definition=inventory_definition if inventory==U else relation('internal-inventory-definition',U,VI(rho*u),'Define internal energy separately from kinetic storage')
    if state['forma']!='local':
        key=prefix+'integrate';graph.transform(key,current,VI,'Integrate the first law over the current domain','volume_integration');current=key
        key=prefix+'gauss';graph.transform(key,current,lambda expression:expression.replace(lambda n:isinstance(n,VI) and isinstance(n.args[0],Div),lambda n:BF(n.args[0].args[0])),
                                         'Apply Gauss to each flux divergence','divergence_theorem',('Regular fields; outward-oriented boundary',));current=key
    if state['forma'] in ('integral','total'):
        local_rate=VI(sp.Derivative(rho*specific,t,evaluate=False))
        reynolds=relation('reynolds',sp.Derivative(inventory,t,evaluate=False),local_rate+BF(rho*specific*boundary),
                          'Reynolds transport identity for the defined inventory',conditions=('Regular moving domain',),inputs=(inventory_definition,))
        substitute('transport',{local_rate:sp.Derivative(inventory,t,evaluate=False)-BF(rho*specific*boundary)},'Apply Reynolds transport',(reynolds,))
        eq=graph.nodes[current].equation;rate=sp.Derivative(inventory,t,evaluate=False)
        key=prefix+'collect-rate'
        graph.add(key,rate,sp.expand(eq.rhs+rate-eq.lhs),'Collect the retained inventory rate','add_to_both_sides',(current,),family='energy');current=key
    fixed=volume.get('frontera',{}).get('tipo')=='rigida' or volume['supuestos']['materia'].get('fija',False)
    if fixed and state['forma'] in ('integral','total'):
        premise=relation('fixed-boundary',boundary,0,'Declare a fixed control boundary','constraint')
        substitute('fixed',{boundary:0},'Apply the fixed-boundary condition',(premise,))
    if state['entalpia']:
        definition=relation('enthalpy-definition',h,u+p/rho,'Define specific enthalpy',conditions=('Positive mass density',))
        # Only transported energy is rewritten: internal-energy storage is
        # retained. Select integrand occurrences, not the inventory definition.
        eq=graph.nodes[current].equation
        operators=(Div,BF)
        mapping={node:linear_operators(node.func(sp.expand(node.args[0].subs(u,h-p/rho)))) for node in eq.rhs.atoms(sp.Function) if isinstance(node,operators)}
        substitute('enthalpy',mapping,'Collect flow work with internal-energy transport',(definition,))
    if state['adiabatico'] and state['forma']!='local':
        premise=relation('adiabatic-boundary',BF(heatflux),0,'Declare zero net conductive boundary heat','constraint',('Interior heat flux need not vanish',))
        substitute('adiabatic',{BF(heatflux):0},'Apply the adiabatic boundary condition',(premise,))
    if state['forma']=='total':
        # Boundary partition is a definition of transported flux averages, not
        # a predefined balance. Decompose each actual flux in the equation.
        eq=graph.nodes[current].equation
        streams=[s for s in model.get('corrientes',[]) if owner in (s['desde'],s['hasta'])]
        transport_property=h if state['entalpia'] else u
        transported=[transport_property]+([] if state['sinCinetica'] else [kinetic])
        if state['separarPresion'] and not state['entalpia']:transported.append(p/rho)
        replacements={};premises=[]
        for index,prop in enumerate(transported):
            flux=BF(sp.expand(rho*prop*velocity))-BF(sp.expand(rho*prop*boundary)) if not fixed else BF(sp.expand(rho*prop*velocity))
            incoming=sp.S.Zero
            for stream in streams:
                sign=int(stream['hasta']==owner)-int(stream['desde']==owner)
                flow=sum((sp.Function('q__'+str(stream['id'])+'__'+str(component))(t) for component in (stream.get('componenteIds') or ['i'])),sp.S.Zero)
                average=sp.Function('energy_average_'+str(index)+'__'+str(stream['id']))(t)
                units[flow]='kg/s';units[average]='J/kg';graph.names[flow]=r'\dot m_{'+str(stream['id']).replace('_',r'\_')+'}'
                graph.names[average]=r'\overline{'+('h' if prop==h else 'u' if prop==u else 'e_c' if prop==kinetic else 'p/\rho')+r'}_{'+str(stream['id']).replace('_',r'\_')+'}'
                incoming+=sign*flow*average
            remainder=field('energy_remainder_'+str(index),'W',display=r'\Phi_{'+str(index+1)+',r}')
            premise=relation('partition-'+str(index),flux,-incoming+remainder,'Partition the oriented boundary transport',conditions=('Flux-weighted specific property; signed common stream orientation',))
            # Move the entire paired transport to one side before replacement.
            eq=graph.nodes[current].equation
            remainder_rhs=sp.expand(eq.rhs+flux)
            key=prefix+'partition-apply-'+str(index)
            graph.add(key,eq.lhs,sp.expand(remainder_rhs+incoming-remainder),'Substitute the boundary partition','substitution',(current,premise),family='energy');current=key
            if volume['supuestos']['materia'].get('restoImpermeable'):
                closed=relation('remainder-'+str(index),remainder,0,'Close the unlisted transport boundary','constraint')
                substitute('closed-'+str(index),{remainder:0},'Apply the closed boundary remainder',(closed,))
        for name,expression,display in [('heat',-BF(heatflux),r'\dot Q'),('viscous',BF(viscous),r'\dot W_\tau'),('stress',BF(stress),r'\dot W_\sigma'),('body',VI(body),r'\dot W_b'),('source',VI(source),'R')]:
            term=field('energy_'+name+'_rate','W',display=display)
            # Definitions can be zero under earlier assumptions; only replace
            # actual occurrences to avoid introducing phantom source terms.
            eq=graph.nodes[current].equation
            atom=-expression if name=='heat' else expression
            if eq.has(atom):
                definition=relation('rate-'+name,term,expression,'Define the integrated '+name+' rate')
                replacements[atom]=-term if name=='heat' else term;premises.append(definition)
        if replacements:substitute('rates',replacements,'Use the defined integrated rates',tuple(premises))
    if state['presionUniforme'] and state['forma'] in ('integral','total'):
        V=field('V','m3',display='V(t)')
        geometry=relation('volume-transport',sp.Derivative(V,t,evaluate=False),BF(boundary),
                          'Apply Reynolds transport to the volume measure',conditions=('Moving-domain volume definition V = integral of one',))
        pressure_work=relation('uniform-pressure-work',BF(p*boundary),p*sp.Derivative(V,t,evaluate=False),
                               'Take uniform pressure outside the boundary integral',inputs=(geometry,))
        substitute('boundary-work',{BF(p*boundary):p*sp.Derivative(V,t,evaluate=False)},'Evaluate uniform-pressure boundary work',(pressure_work,))
        if state['presionPrescrita']:
            prescribed=field('P_external','Pa',display=r'P_{ext}(t)')
            condition=relation('prescribed-pressure',p,prescribed,'Declare the prescribed pressure history','constraint')
            # Preserve P as the common state quantity; the boundary relation is
            # its explicit value binding, not a different pressure in enthalpy.
            H=field('H' if state['sinCinetica'] else 'H_total','J',display='H(t)' if state['sinCinetica'] else r'H_{tot}(t)')
            definition=relation('enthalpy-inventory',H,inventory+p*V,'Define the enthalpy inventory')
            key=prefix+'enthalpy-rate';graph.differentiate(key,definition,t,'Differentiate the enthalpy definition; retain pressure variation')
            graph.substitute(prefix+'enthalpy-balance',key,{sp.Derivative(inventory,t,evaluate=False):graph.nodes[current].equation.rhs},
                             'Substitute the derived first law into the enthalpy rate',inputs=(current,condition))
            current=prefix+'enthalpy-balance'
            graph.nodes[current].kind='balance'
    final=[current]
    if state['sinAcumulacionTotal'] and state['forma'] in ('integral','total'):
        final.append(relation('zero-total-rate',sp.Derivative(inventory,t,evaluate=False),0,'Declared zero total energy accumulation','constraint',inputs=(current,)))
    if state['estacionario']:
        final.append(relation('zero-local-rate',sp.Derivative(rho*specific,t,evaluate=False),0,'Declared zero local energy accumulation','constraint',inputs=(prefix+'local',)))
    if state['uniforme']:
        mean=field('u_mean','J/kg',display=r'\bar u(t)')
        mass=sum((sp.Function('m__'+owner+'__'+str(i))(t) for i in (volume.get('componenteIds') or ['i'])),sp.S.Zero)
        for amount in mass.atoms(sp.Function):units[amount]='kg'
        premise=relation('uniform-internal-energy',u,mean,'Declare uniform specific internal energy','constraint')
        final.append(relation('uniform-inventory',U,mass*mean,'Evaluate the uniform internal-energy inventory','definition',('Mass is the integral of mixture density',),(internal_definition,premise)))
    return graph,final,units


def lower_equilibrium_rate(model,owner):
    """Extract admitted power coefficients from the derived inventory law.

    The closure/donor service evaluates stream power on either molar or mass
    basis. This lowering uses the identity mdot*h_mass = ndot*h_molar; it
    cannot introduce a flux absent from the graph or ignore a retained term.
    """
    from core.modelo.operation_journal import JournalError
    graph,final,_=equation_graph(model,owner)
    balance=graph.nodes[final[0]].equation
    if not isinstance(balance.lhs,sp.Derivative) or len(balance.lhs.variables)!=1:
        raise JournalError('The first-law graph does not expose an explicit inventory rate.')
    remainder=sp.expand(balance.rhs);terms=[];t=sp.Symbol('t',real=True)
    for stream in model.get('corrientes',[]):
        if owner not in (stream['desde'],stream['hasta']):continue
        average=sp.Function('energy_average_0__'+str(stream['id']))(t)
        flows=[sp.Function('q__'+str(stream['id'])+'__'+str(i))(t) for i in (stream.get('componenteIds') or ['i'])]
        coefficient=sp.diff(remainder,average)
        factor=sp.expand(coefficient).coeff(flows[0])
        if not factor.is_number or sp.expand(coefficient-factor*sum(flows))!=0:
            raise JournalError('The first-law port power has no supported common-flow lowering.')
        remainder=sp.expand(remainder-factor*sum(flows)*average)
        if factor:terms.append(('stream',stream['id'],float(factor)))
    heat=sp.Function('energy_heat_rate__'+owner)(t)
    factor=sp.expand(remainder).coeff(heat)
    if factor:
        if not factor.is_number:raise JournalError('Nonlinear boundary heat needs its own numerical lowering.')
        terms.append(('heat',owner,float(factor)));remainder=sp.expand(remainder-factor*heat)
    P=sp.Function('P__'+owner)(t);V=sp.Function('V__'+owner)(t)
    power=V*sp.diff(P,t)
    factor=sp.simplify(remainder.coeff(sp.diff(P,t))/V)
    if factor:
        if not factor.is_number:raise JournalError('The pressure-work graph needs a supported boundary closure.')
        terms.append(('pressure',owner,float(factor)));remainder=sp.expand(remainder-factor*power)
    if remainder!=0:
        raise JournalError('A retained first-law term has no equilibrium numerical lowering. The earlier balance cannot be substituted.')
    return terms
