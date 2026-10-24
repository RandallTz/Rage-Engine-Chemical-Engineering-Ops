"""Physical assumptions applied through the shared symbolic equation operations.

These producers have no example IDs, hydraulic configuration or numerical data.
The final expressions are consumed by both Model development and compilation.
"""
import sympy as sp
from functools import lru_cache
from core.modelo.equation_manipulation import EquationGraph

WALL_FLAGS=('circularSection','developedProfile','quasiSteadyWall','regularAxis','noSlipWall')
STORAGE_FLAGS=('verticalGravity','pressureReference','prismaticStorage')


def path_reduction(symbols,names):
    graph=EquationGraph(names)
    L,A,rho,flow,rate=[symbols[k] for k in ['L','A','rho','massFlow','massFlowRate']]
    x,t=sp.symbols('s t',real=True);u=sp.Symbol('u',real=True)
    m=sp.Function('m_flow')(t);inventory=sp.Function('I')(t)
    from .material_equations import VolumeIntegral as VI,BoundaryFlux as BF,Divergence as Div
    velocity=sp.Function('u_local')(x,t);stress=sp.Function('sigma_local')(x,t);body_field=sp.Function('b_local')(x,t)
    graph.add('path.cauchy',sp.diff(rho*velocity,t)+Div(rho*velocity**2),Div(stress)+rho*body_field,
              'Local Cauchy conservation projected along a declared direction',family='momentum')
    graph.transform('path.integrate-cauchy','path.cauchy',VI,'Integrate the local conservation law over the domain','volume_integration')
    graph.transform('path.gauss','path.integrate-cauchy',lambda e:e.replace(lambda n:isinstance(n,VI) and isinstance(n.args[0],Div),lambda n:BF(n.args[0].args[0])),
                    'Apply Gauss to convective transport and stress divergence','divergence_theorem',('Regular fields and an oriented boundary',))
    graph.add('path.fixed-inventory',inventory,VI(rho*velocity),'Define the integrated momentum inventory','definition',family='momentum',kind='definition')
    graph.differentiate('path.inventory-theorem','path.fixed-inventory',t,'Differentiate the fixed-domain inventory definition')
    graph.substitute('path.integrated-law','path.gauss',{VI(sp.diff(rho*velocity,t)):sp.diff(inventory,t)},
                     'Commute the time derivative and fixed-domain integral',('Fixed integration domain',),inputs=('path.inventory-theorem',))
    graph.add('path.flux',m,rho*A*u,'Define the section mass flux','definition',assumptions=('Uniform section mean velocity and density; fixed area',))
    mean_velocity=graph.isolate('path.mean-velocity','path.flux',u,'Recover the section mean velocity',('rho > 0; A > 0',))
    graph.add('path.inventory',inventory,sp.Integral(rho*A*u,(x,0,L)),'Evaluate the inventory using the declared section geometry','section_integration',inputs=('path.fixed-inventory',),assumptions=('Straight fixed path; uniform cross-section and flux',),kind='definition')
    graph.substitute('path.inventory-integral','path.inventory',{u:mean_velocity.rhs},'Substitute mass continuity into the momentum inventory',inputs=('path.mean-velocity',))
    graph.differentiate('path.inventory-rate','path.inventory-integral',t,'Differentiate the inventory; retain time-dependent mass flow')
    storage=graph.nodes['path.inventory-rate'].equation.rhs.subs(sp.diff(m,t),rate)
    p1,p2,drive,loss,g,z1,z2=[symbols[k] for k in ['p1','p2','drive','loss','g','z1','z2']]
    c1,c2,wall,body=sp.symbols('c_1 c_2 F_wall F_body',real=True)
    graph.add('path.convective-ports',BF(rho*velocity**2),m*(c2-c1),'Partition the convective boundary flux into oriented ports','boundary_partition',assumptions=('Two declared ports; equal mass flux; section mean axial velocities',),kind='definition')
    graph.add('path.stress-ports',BF(stress),A*(p1-p2)+wall,'Separate pressure tractions and the remaining boundary force','stress_partition',assumptions=('Equal port area; pressure stress with oriented normals',),kind='definition')
    graph.add('path.body-integral',VI(rho*body_field),body,'Name the integrated body force','definition',kind='definition')
    graph.substitute('path.projected-ports','path.integrated-law',{BF(rho*velocity**2):m*(c2-c1),BF(stress):A*(p1-p2)+wall,VI(rho*body_field):body},
                     'Substitute each boundary and volume integral into Cauchy conservation',inputs=('path.convective-ports','path.stress-ports','path.body-integral'))
    projected=graph.nodes['path.projected-ports'].equation
    graph.add('path.balance',projected.lhs-m*(c2-c1),sp.expand(projected.rhs-m*(c2-c1)),
              'Move the convective port term to the force side','subtract_from_both_sides',inputs=('path.projected-ports',))
    graph.substitute('path.force','path.balance',{sp.diff(inventory,t):storage},
                     'Substitute the differentiated momentum inventory into its balance',inputs=('path.inventory-rate',))
    graph.substitute('path.equal-sections','path.force',{c2:c1},'Equal area and density cancel the two convective port fluxes')
    graph.substitute('path.forces','path.equal-sections',{wall:A*(drive-loss),body:-rho*A*g*(z2-z1),m:flow},
                     'Substitute declared wall/drive forces and the gravitational line integral',('Uniform gravity; explicit drive and loss definitions',))
    equation=graph.nodes['path.forces'].equation
    graph.add('path.pressure-form',sp.simplify(equation.lhs/A),sp.simplify(equation.rhs/A),'Divide the projected force balance by section area','divide',( 'path.forces',),('A > 0',))
    return graph,graph.nodes['path.pressure-form'].equation


REDUCTION_FLAGS=WALL_FLAGS+STORAGE_FLAGS+('negligibleConvection','negligibleViscousStress','zeroLocalAccumulation','referenceDensity','uniformGravity')


def reduction_graphs(state):
    return _graphs(tuple(bool(state.get(k)) for k in REDUCTION_FLAGS))


@lru_cache(maxsize=1)
def canonical_path_graph():
    from .momentum_derivation import reduced_relations
    symbols,_,names=reduced_relations()
    return path_reduction(symbols,names)[0]


@lru_cache(maxsize=256)
def _graphs(values):
    from .momentum_derivation import reduced_relations
    symbols,_,names=reduced_relations();state=dict(zip(REDUCTION_FLAGS,values))
    wall,wall_result=wall_reduction(symbols,names,state)
    storage,storage_result=storage_reduction(symbols,names,state)
    return wall,wall_result,storage,storage_result


def wall_reduction(symbols, names, state):
    graph=EquationGraph(names)
    if not state.get('circularSection'):return graph,{}
    r,R=sp.symbols('r R',positive=True);u=sp.Function('u')(r)
    L,mu,loss,A,rho,flow=[symbols[k] for k in ['L','mu','loss','A','rho','massFlow']]
    C1,C2,Q=sp.symbols('C_1 C_2 Q',real=True)
    graph.add('wall.geometry',A,sp.pi*R**2,'Declare a circular section','geometry',assumptions=('Circular cross-section; R > 0',))
    if not state.get('developedProfile'):return graph,{}
    a,c,gradient=sp.symbols('profile_acceleration convective_acceleration pressure_gradient',real=True)
    derivative=sp.Derivative(r*sp.Derivative(u,r,evaluate=False),r,evaluate=False)
    viscous,body=sp.symbols('viscous_stress_divergence body_acceleration',real=True)
    graph.add('wall.cauchy',rho*(a+c),-gradient+viscous+rho*body,
              'Declared auxiliary wall constitutive premise; local-Cauchy projection is not deduced',
              'constitutive_premise',assumptions=('Assumed axial auxiliary stress problem; acceleration and convection retained',
              'No fundamental-law ancestry is claimed for this constitutive premise'),kind='constitutive')
    graph.add('wall.newtonian',viscous,mu*derivative/r,'Newtonian stress divergence in the declared circular coordinates','constitutive_identity',
              assumptions=('Axisymmetric axial velocity; uniform viscosity',),kind='constitutive')
    graph.substitute('wall.axial','wall.cauchy',{viscous:mu*derivative/r,body:0},
                     'Substitute the Newtonian stress law in the auxiliary boundary problem',('No axial body force in this auxiliary wall problem',),inputs=('wall.newtonian',))
    graph.substitute('wall.developed','wall.axial',{c:0},'Fully developed profile removes axial convection',('Axial profile independent of axial position',))
    if not state.get('quasiSteadyWall'):return graph,{}
    graph.substitute('wall.quasi-steady','wall.developed',{a:0,gradient:-loss/L},
                     'Quasi-steady auxiliary wall problem; retain bulk inertia separately',('Negligible profile acceleration only in the wall constitutive problem','Uniform wall-driving pressure gradient; L > 0'))
    graph.isolate('wall.radial-ode','wall.quasi-steady',derivative,'Isolate the radial stress derivative',('r > 0; mu > 0',))
    graph.integrate('wall.first-integral','wall.radial-ode',r,C1,'Integrate the radial stress equation')
    current='wall.first-integral'
    if state.get('regularAxis'):
        graph.substitute('wall.regularity',current,{C1:0},'Finite shear and velocity at the axis remove the singular constant',('Regular solution at r = 0',))
        current='wall.regularity'
    graph.isolate('wall.gradient',current,sp.diff(u,r),'Isolate the radial velocity gradient',('r > 0',))
    graph.integrate('wall.velocity-general','wall.gradient',r,C2,'Integrate the velocity gradient; keep the boundary constant')
    current='wall.velocity-general'
    if state.get('noSlipWall'):
        graph.substitute('wall.evaluate-boundary',current,{r:R},'Evaluate the velocity primitive at the wall')
        graph.substitute('wall.boundary','wall.evaluate-boundary',{sp.Function('u')(R):0},'Apply the no-slip condition at the wall',('u(R) = 0',))
        constant=graph.isolate('wall.boundary-constant','wall.boundary',C2,'Solve the integration constant from the boundary condition')
        graph.substitute('wall.profile',current,{C2:constant.rhs},'Substitute the boundary constant into the profile',inputs=('wall.boundary-constant',))
        current='wall.profile'
    if not all(state.get(k) for k in WALL_FLAGS):return graph,{}
    profile=graph.nodes[current].equation.rhs
    graph.add('wall.flux-definition',Q,sp.Integral(2*sp.pi*r*u,(r,0,R)), 'Define volume flux through the section','definition',inputs=(current,))
    graph.substitute('wall.flux-integral','wall.flux-definition',{u:profile},'Integrate the derived profile over the section',inputs=(current,))
    graph.substitute('wall.mass-flux','wall.flux-integral',{Q:flow/rho},'Use the same constant-density material flux',('rho > 0; mass flow = rho Q',))
    graph.isolate('wall.pressure-loss','wall.mass-flux',loss,'Recover signed pressure loss from the integrated mass flux',('L > 0; R > 0',))
    graph.substitute('wall.area-form','wall.pressure-loss',{R:sp.sqrt(A/sp.pi)},'Substitute the declared section area',('A > 0',),inputs=('wall.geometry',))
    return graph,{'loss':graph.nodes['wall.area-form'].equation,'profile':graph.nodes['wall.profile'].equation}


def connected_storage_reduction(graph,state):
    """Extend the actual local graph; use all three zero-rate consequences.

    The fixed storage scope needs no new kernel operation: substitution,
    isolation and integration already retain expression inputs and guards.
    Other adapters can still call storage_reduction without this local graph.
    """
    required=('pressureStress','negligibleConvection','negligibleViscousStress',
              'zeroLocalAccumulation','referenceDensity','uniformGravity','verticalGravity')
    if not all(state.get(key) for key in required):return None
    # Other dependency-reduced Cartesian adapters retain their existing scope.
    # This bridge proves horizontal independence from the unreduced pressure
    # dependencies, rather than inventing a history for an already reduced field.
    if any(state.get('invariant'+axis) for axis in 'XYZ'):return None
    from .momentum_derivation import reduced_relations
    symbols,_,names=reduced_relations()
    x,y,z,t=sp.symbols('x y z t',real=True)
    pressure=sp.Function('p')(x,y,z,t);reduced=sp.Function('p')(z,t)
    horizontal=[]
    for axis,coordinate in zip('xyz',(x,y,z)):
        condition='local.'+axis+'.zero-rate'
        current=graph.nodes[condition].inputs[0]
        rate=graph.nodes[condition].equation
        key='storage.zero-rate.'+axis
        graph.substitute(key,current,{rate.lhs:rate.rhs},'Apply the recorded '+axis+' zero-accumulation condition',inputs=(condition,))
        if axis!='z':
            gradient='storage.horizontal-gradient.'+axis
            graph.isolate(gradient,key,sp.diff(pressure,coordinate),'Derive zero horizontal pressure gradient')
            if graph.nodes[gradient].equation.rhs!=0:
                raise ValueError('Storage pressure retains a horizontal force gradient.')
            horizontal.append(gradient)
    graph.substitute('storage.cauchy','storage.zero-rate.z',{pressure:reduced},
        'Restrict pressure to height and time using both horizontal force balances',
        ('Connected Cartesian region; zero x/y gradients imply p = p(z,t); time dependence retained',),inputs=tuple(horizontal))
    graph.transform('storage.force','storage.cauchy',lambda e:e.doit(),
        'Evaluate derivatives after the proved pressure dependency restriction','evaluate_derivatives')
    return storage_reduction(symbols,names,state,graph=graph,pressure=reduced)[1]


def storage_reduction(symbols,names,state,*,graph=None,pressure=None):
    connected=graph is not None
    graph=graph if connected else EquationGraph(names)
    if not state.get('verticalGravity'):return graph,{}
    z,zs,zf,h,Av,m,ps=sp.symbols('z z_r z_0 h A_v m_v p_r',real=True)
    p=pressure if connected else sp.Function('p')(z);rho,g=symbols['rho'],symbols['g']
    accumulation,convection,viscous,body=sp.symbols('local_rate convection viscous_force b_z',real=True)
    if not connected:
        graph.add('storage.cauchy',accumulation+convection,-sp.diff(p,z)+viscous+rho*body,
                  'Vertical component of Cauchy conservation after pressure separation','projection',assumptions=('Vertical Cartesian coordinate',))
    substitutions={body:-g}
    if state.get('negligibleConvection'):substitutions[convection]=0
    if state.get('negligibleViscousStress'):substitutions[viscous]=0
    if state.get('zeroLocalAccumulation'):substitutions[accumulation]=0
    if not connected:
        graph.substitute('storage.force','storage.cauchy',substitutions,'Apply the recorded local force and gravity assumptions',
                         tuple(k for k in ('negligibleConvection','negligibleViscousStress','zeroLocalAccumulation','verticalGravity') if state.get(k)))
    if not all(state.get(k) for k in ('negligibleConvection','negligibleViscousStress','zeroLocalAccumulation','referenceDensity','uniformGravity','pressureReference')):return graph,{}
    graph.isolate('storage.gradient','storage.force',sp.diff(p,z),'Isolate the pressure gradient')
    graph.nodes['storage.gradient'].kind='definition'
    C=sp.Symbol('C_p',real=True)
    graph.integrate('storage.pressure-general','storage.gradient',z,C,'Integrate the reduced force balance in height',('Uniform density and gravity',))
    graph.substitute('storage.reference','storage.pressure-general',{z:zs},'Evaluate the pressure primitive at a reference coordinate')
    graph.substitute('storage.reference-value','storage.reference',{p.subs(z,zs):ps},'Apply the declared pressure reference',('p(z_r,t) = p_r(t)',))
    constant=graph.isolate('storage.reference-constant','storage.reference-value',C,'Determine the pressure integration constant')
    graph.substitute('storage.pressure','storage.pressure-general',{C:constant.rhs},'Reconstruct absolute static pressure at any admitted height',inputs=('storage.reference-constant',))
    result={'pressure':graph.nodes['storage.pressure'].equation,'symbols':(z,zs,zf,h,Av,m,ps)}
    if state.get('prismaticStorage'):
        graph.add('storage.inventory',m,sp.Integral(rho*Av,(z,0,h)), 'Apply constant section and density to the material inventory','geometry',assumptions=('Prismatic volume; A_v > 0; density uniform',),family='matter')
        graph.substitute('storage.inventory-integral','storage.inventory',{},'Evaluate the material inventory integral')
        height=graph.isolate('storage.height','storage.inventory-integral',h,'Recover height from the same material inventory',('rho > 0; A_v > 0',))
        graph.add('storage.surface-height',zs,zf+height.rhs,'Relate two generic reference coordinates through the inventory length','geometry',inputs=('storage.height',),family='matter')
        graph.substitute('storage.port-pressure','storage.pressure',{zs:zf+height.rhs},'Couple port pressure to the current material inventory',inputs=('storage.surface-height',))
        result.update(pressure=graph.nodes['storage.port-pressure'].equation,height=height)
    return graph,result
