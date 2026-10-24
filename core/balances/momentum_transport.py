"""Cauchy component transport and moments through shared equation operations."""
import sympy as sp
from core.modelo.operation_journal import JournalError
from .material_equations import VolumeIntegral as VI,BoundaryFlux as BF


def extend_transport(graph,state):
    """Extend an unscoped local Cauchy graph; the caller scopes every field."""
    xyz=sp.symbols('x y z',real=True);t=sp.Symbol('t',real=True);args=(*xyz,t)
    rho=sp.Function('rho')(*args);v=[sp.Function('v_'+a)(*args) for a in 'xyz']
    stress=[[sp.Function('sigma_'+str(i+1)+str(j+1))(*args) for j in range(3)] for i in range(3)]
    body=[sp.Function('b_'+a)(*args) for a in 'xyz']
    boundary=[sp.Function('boundary_v_'+a)(*args) for a in 'xyz']
    basis=sp.symbols('basis_x basis_y basis_z',real=True)
    for axis,e in zip('xyz',basis):graph.names[e]=r'\mathbf e_'+axis
    final=[]
    def add(key,lhs,rhs,title,rule='definition',inputs=(),assumptions=(),kind='definition',family='momentum'):
        graph.add(key,lhs,rhs,title,rule,inputs,assumptions,family,kind=kind);return key
    # Apply constitutive premises to the conservative transport law, rather
    # than integrating an unrelated unreduced stress tensor. Continuity may
    # change its local representation, but never deletes an inventory.
    substitutions={};premises=[]
    def premise(key,lhs,rhs,title):
        premises.append(add(key,lhs,rhs,title,'assumption',kind='constitutive'))
        substitutions[lhs]=rhs
    if state['pressureStress']:
        p=sp.Function('p')(*args)
        mu=sp.Function('mu')(t) if state['constantViscosity'] else sp.Function('mu')(*args)
        lam=sp.Function('lambda')(t) if state['constantViscosity'] else sp.Function('lambda')(*args)
        divergence=sum(sp.diff(v[j],xyz[j]) for j in range(3))
        for i in range(3):
            for j in range(3):
                tau=sp.Function('tau_'+str(i+1)+str(j+1))(*args)
                if state['newtonian']:
                    tau=mu*(sp.diff(v[i],xyz[j])+sp.diff(v[j],xyz[i]))
                    if i==j and not state['divergenceFree']:tau+=lam*divergence
                premise('transport.stress-'+str(i)+str(j),stress[i][j],tau-(p if i==j else 0),
                        'Apply pressure decomposition'+(' and Newtonian stress' if state['newtonian'] else ''))
        if state['divergenceFree']:
            add('transport.divergence-free',divergence,0,'Declare divergence-free velocity','assumption',kind='constraint')
    if state['referenceDensity']:premise('transport.reference-density',rho,sp.Symbol('rho',real=True),'Declare constant reference density')
    if state['uniformGravity']:
        for axis,b in zip('xyz',body):
            value=(-sp.Symbol('g',real=True) if axis=='z' else sp.S.Zero) if state['verticalGravity'] else sp.Symbol('b_'+axis,real=True)
            premise('transport.gravity-'+axis,b,value,'Declare the uniform body acceleration')
    def integrate(key,source,density,convective,traction,volume_force,inventory):
        compact=add(key+'.conservative',sp.Derivative(density,t,evaluate=False)+sum(sp.Derivative(f,x,evaluate=False) for f,x in zip(convective,xyz)),
                    sum(sp.Derivative(f,x,evaluate=False) for f,x in zip(traction,xyz))+volume_force,
                    'Collect conservative derivatives using the product rule','collect_derivatives',(source,),kind='balance')
        original=graph.nodes[source].equation;collected=graph.nodes[compact].equation
        if sp.simplify((original.lhs-original.rhs)-(collected.lhs-collected.rhs).doit())!=0:
            raise JournalError('The conservative transport rewrite does not match its Cauchy inputs.')
        if substitutions:
            reduced=key+'.constitutive'
            graph.substitute(reduced,compact,substitutions,'Apply the recorded transport premises',inputs=tuple(premises))
            compact=reduced
            density=density.xreplace(substitutions)
            convective=[f.xreplace(substitutions) for f in convective]
            traction=[f.xreplace(substitutions) for f in traction]
            volume_force=volume_force.xreplace(substitutions)
        graph.transform(key+'.volume',compact,VI,'Integrate the component conservation equation','volume_integration')
        replacements={VI(sp.Derivative(f,x,evaluate=False)):BF(f*e) for f,x,e in zip(convective,xyz,basis)}
        replacements.update({VI(sp.Derivative(f,x,evaluate=False)):BF(f*e) for f,x,e in zip(traction,xyz,basis)})
        graph.substitute(key+'.gauss',key+'.volume',replacements,'Apply Gauss to each conservative derivative',('Regular fields and outward boundary orientation',))
        add(key+'.inventory',inventory,VI(density),'Define the momentum inventory')
        moving=sum(BF(density*b*e) for b,e in zip(boundary,basis))
        add(key+'.reynolds',sp.Derivative(inventory,t,evaluate=False),VI(sp.Derivative(density,t,evaluate=False))+moving,
            'Reynolds transport identity for the momentum inventory','transport_theorem',(key+'.inventory',),('Regular moving control boundary',))
        graph.substitute(key+'.transport',key+'.gauss',{VI(sp.Derivative(density,t,evaluate=False)):sp.Derivative(inventory,t,evaluate=False)-moving},
                         'Substitute Reynolds transport',inputs=(key+'.reynolds',))
        eq=graph.nodes[key+'.transport'].equation;rate=sp.Derivative(inventory,t,evaluate=False)
        current=add(key+'.rate',rate,sp.expand(eq.rhs+rate-eq.lhs),'Collect inventory accumulation','add_to_both_sides',(key+'.transport',),kind='balance')
        if state['fixedBoundary']:
            boundary_premises=[add(key+'.fixed-'+a,b,0,'Declare a fixed boundary component','assumption',assumptions=('Fixed control envelope',),kind='constraint') for a,b in zip('xyz',boundary)]
            graph.substitute(key+'.fixed',current,{b:0 for b in boundary},'Apply fixed-boundary conditions',inputs=tuple(boundary_premises));current=key+'.fixed'
        return current
    for i,axis in enumerate('xyz'):
        density=rho*v[i];flux=[density*velocity for velocity in v];inventory=sp.Function('I_'+axis)(t)
        graph.names[inventory]=r'I_{'+axis+'}(t)'
        key='transport.'+axis
        current=integrate(key,'local.'+axis,density,flux,stress[i],rho*body[i],inventory)
        if state['form'] in ('ports','hydraulic'):
            m1,m2=sp.Function('port_mass_1')(t),sp.Function('port_mass_2')(t)
            c1,c2=sp.Function('port_velocity_1_'+axis)(t),sp.Function('port_velocity_2_'+axis)(t)
            transport=sum(BF(f.xreplace(substitutions)*e) for f,e in zip(flux,basis))
            force=sum(BF(f.xreplace(substitutions)*e) for f,e in zip(stress[i],basis))+VI((rho*body[i]).xreplace(substitutions))
            p1,p2=sp.Function('p1')(t),sp.Function('p2')(t)
            A1,A2=sp.Symbol('oriented_area_1_'+axis,real=True),sp.Symbol('oriented_area_2_'+axis,real=True)
            wall=sp.Function('wall_force_'+axis)(t);shear=sp.Function('port_shear_'+axis)(t);body_force=sp.Function('body_force_'+axis)(t)
            partition=add(key+'.port-flux',transport,m2*c2-m1*c1,'Define oriented mass-flux-weighted port velocities','boundary_partition',assumptions=('Two declared ports; impermeable remaining wall',))
            volume_integral=VI((rho*body[i]).xreplace(substitutions))
            body_definition=add(key+'.body-force',body_force,volume_integral,'Define the integrated body force from its recorded field')
            surface_definition=add(key+'.surface-forces',force-volume_integral,-p1*A1-p2*A2+wall+shear,'Partition surface pressure, shear and wall forces','boundary_partition',assumptions=('Signed integrated outward normals; wall force includes wall traction',))
            traction=add(key+'.port-forces',force,-p1*A1-p2*A2+wall+shear+body_force,'Combine surface partition and body-force definition','substitution',(surface_definition,body_definition))
            equation=graph.nodes[current].equation
            rhs=sp.expand(equation.rhs+transport-force+m1*c1-m2*c2-p1*A1-p2*A2+wall+shear+body_force)
            current=add(key+'.ports',equation.lhs,rhs,'Substitute each port and force definition','substitution',(current,partition,traction),kind='balance')
        final.append(current)
        if state['zeroTotalAccumulation']:
            final.append(add(key+'.zero-rate',sp.diff(inventory,t),0,'Declare zero integrated momentum accumulation','assumption',(current,),kind='constraint'))
    if state['angularMomentum']:
        x,y,_=xyz
        graph.combine('angular.moment',['local.y','local.x'],'Take the axial moment of Cauchy components',[x,-y])
        symmetry=add('angular.symmetric-stress',stress[0][1],stress[1][0],'Declare symmetric Cauchy stress','assumption',assumptions=('No distributed body couples; classical Cauchy continuum',),kind='constraint')
        graph.substitute('angular.symmetric','angular.moment',{stress[0][1]:stress[1][0]},'Apply stress symmetry to the moment balance',inputs=(symmetry,))
        density=rho*(x*v[1]-y*v[0]);convective=[density*velocity for velocity in v]
        traction=[(x*stress[1][j]-y*stress[0][j]).subs(stress[0][1],stress[1][0]) for j in range(3)]
        L=sp.Function('fluid_angular_momentum')(t);graph.names[L]='L_f(t)'
        current=integrate('angular','angular.symmetric',density,convective,traction,rho*(x*body[1]-y*body[0]),L)
        m1,m2=sp.Function('port_mass_1')(t),sp.Function('port_mass_2')(t)
        r1,r2=sp.symbols('r1 r2',real=True);ct1,ct2=sp.Function('tangential_velocity_1')(t),sp.Function('tangential_velocity_2')(t)
        torque=sp.Function('fluid_torque')(t);other=sp.Function('other_torque')(t)
        outward=sum(BF(f.xreplace(substitutions)*e) for f,e in zip(convective,basis));force=sum(BF(f.xreplace(substitutions)*e) for f,e in zip(traction,basis))+VI((rho*(x*body[1]-y*body[0])).xreplace(substitutions))
        flux=add('angular.port-flux',outward,m2*r2*ct2-m1*r1*ct1,'Define port angular-momentum flux averages','boundary_partition',assumptions=('Products r c_theta are mass-flux-weighted port averages',))
        torques=add('angular.torques',force,torque+other,'Partition rotor and remaining axial torque')
        eq=graph.nodes[current].equation
        current=add('angular.ports',eq.lhs,sp.expand(eq.rhs+outward-force+torque+other+m1*r1*ct1-m2*r2*ct2),
                    'Substitute angular flux and torque definitions','substitution',(current,flux,torques),kind='balance')
        final.append(current)
        substitutions={};premises=[]
        for enabled,key,lhs,rhs,title in [(state['equalPortMassFlow'],'angular.equal-flow',m2,m1,'Declare equal port mass flows'),(state['noOtherTorque'],'angular.no-other',other,0,'Neglect other axial torques'),(state['zeroAngularAccumulation'],'angular.zero-rate',sp.diff(L,t),0,'Declare zero passage angular accumulation'),(state['zeroInletSwirl'],'angular.zero-swirl',ct1,0,'Declare zero inlet swirl')]:
            if enabled:
                premises.append(add(key,lhs,rhs,title,'assumption',kind='constraint'));substitutions[lhs]=rhs
        if substitutions:
            graph.substitute('angular.compatibility',current,substitutions,'Apply the individually recorded passage conditions',inputs=tuple(premises));current='angular.compatibility';final.append(current)
        if state['zeroAngularAccumulation']:
            graph.isolate('angular.fluid-torque',current,torque,'Recover torque from the angular compatibility equation');final.append('angular.fluid-torque')
        omega=sp.Function('omega')(t)
        if state['radialOutlet']:
            width,beta=sp.symbols('outlet_width blade_angle',real=True);Q=sp.Function('Q')(t)
            area=sp.Symbol('annular_area',real=True);cm=sp.Function('meridional_velocity')(t)
            final.append(add('angular.annulus',area,2*sp.pi*r2*width,'Declare full radial annular area',assumptions=('No blockage; positive radius and width',)))
            add('angular.volume-flow',Q,area*cm,'Define uniform annular volume flow')
            graph.isolate('angular.meridional','angular.volume-flow',cm,'Recover meridional velocity',('Positive annular area',))
            graph.substitute('angular.annular-velocity','angular.meridional',{area:graph.nodes['angular.annulus'].equation.rhs},'Substitute the declared annular geometry',inputs=('angular.annulus',))
            final.append('angular.annular-velocity')
        if state['shaftDynamics']:
            J=sp.Symbol('J',positive=True);rotor=sp.Function('rotor_angular_momentum')(t)
            motor=sp.Function('motor_torque')(t);bearing=sp.Function('bearing_torque')(t)
            add('rotor.balance',sp.diff(rotor,t),motor-torque-bearing,'Angular conservation of the rigid rotor','declared_law',kind='balance')
            add('rotor.inventory',rotor,J*omega,'Define rotor inertia and angular momentum',assumptions=('Positive constant rigid-rotor inertia',))
            graph.differentiate('rotor.inventory-rate','rotor.inventory',t,'Differentiate the rotor inventory')
            graph.substitute('rotor.rate','rotor.balance',{sp.diff(rotor,t):graph.nodes['rotor.inventory-rate'].equation.rhs},'Use the differentiated rotor inventory',inputs=('rotor.inventory-rate',));final.append('rotor.rate')
            add('rotor.kinetic-energy',sp.Function('rotor_energy')(t),J*omega**2/2,'Define rigid-rotor kinetic energy',family='energy')
            graph.differentiate('rotor.energy-rate','rotor.kinetic-energy',t,'Differentiate rigid-rotor kinetic energy')
            graph.isolate('rotor.acceleration','rotor.rate',sp.diff(omega,t),'Isolate rotor angular acceleration')
            graph.substitute('rotor.power','rotor.energy-rate',{sp.diff(omega,t):graph.nodes['rotor.acceleration'].equation.rhs},'Substitute angular dynamics in the first-law coupling',inputs=('rotor.acceleration',));final.append('rotor.power')
        if not state['rotorActuator']:
            return final
        transfer=sp.Function('specific_shaft_transfer')(t);power=sp.Function('shaft_power')(t)
        add('angular.shaft-power',power,torque*omega,'Define shaft power transferred to the fluid',family='energy')
        add('angular.specific-power',power,m1*transfer,'Define specific shaft transfer',assumptions=('Nonzero passage mass flow',),family='energy')
        if state['equalPortMassFlow'] and state['noOtherTorque'] and state['zeroAngularAccumulation']:
            graph.substitute('angular.power-torque','angular.shaft-power',{torque:graph.nodes['angular.fluid-torque'].equation.rhs},'Substitute derived passage torque into shaft power',inputs=('angular.fluid-torque',))
            graph.substitute('angular.transfer-equation','angular.specific-power',{power:graph.nodes['angular.power-torque'].equation.rhs},'Equate the definitions of transferred shaft power',inputs=('angular.power-torque',))
            graph.isolate('angular.transfer','angular.transfer-equation',transfer,'Isolate the specific shaft transfer',('Nonzero passage mass flow',));final.append('angular.transfer')
            if state['idealBladeGuidance']:
                add('angular.guidance',ct2,omega*r2-cm*sp.cot(beta),'Declare ideal relative-flow blade guidance','constitutive_choice',assumptions=(r'0<\beta<\pi','No slip between relative flow direction and the ideal blade'),kind='constitutive')
                graph.substitute('angular.guided-velocity','angular.guidance',{cm:graph.nodes['angular.annular-velocity'].equation.rhs},'Substitute the derived meridional velocity',inputs=('angular.annular-velocity',))
                graph.substitute('angular.guided-transfer','angular.transfer',{ct2:graph.nodes['angular.guided-velocity'].equation.rhs},'Substitute ideal guidance in the derived shaft transfer',inputs=('angular.guided-velocity',));final.append('angular.guided-transfer')
    return final
