"""Material conservation as equation operations, not a LaTeX recipe.

The only law root is local component mass conservation. Volume integration,
Gauss/Reynolds, inventory definitions and boundary partition are explicit rules.
Equipment names and hydraulic configuration never participate.
"""
import sympy as sp
from core.mathematics.operators import BoundaryFlux, Divergence, Gradient, VolumeIntegral
from core.modelo.equation_manipulation import EquationGraph






def expand_local_operators(graph,key,current,state,rho,velocity,flux,t):
    """Orthogonal-coordinate divergence, including metric terms under invariance.

    Coordinate independence removes field dependencies, not the metric factors.
    In cylindrical symmetry a constant radial flux still has divergence j_r/r.
    """
    chart=state['coordenadas']
    axes=sp.symbols({'cartesianas':'x y z','cilindricas':'r phi z','esfericas':'r theta phi'}[chart],real=True)
    h=(sp.S.One,)*3 if chart=='cartesianas' else (sp.S.One,axes[0],sp.S.One) if chart=='cilindricas' else (sp.S.One,axes[0],axes[0]*sp.sin(axes[1]))
    measure=sp.prod(h);active=tuple(axis for axis,excluded in zip(axes,state['invariantes']) if not excluded)
    args=(*active,t)
    equation=graph.nodes[current].equation
    fields={f:f.func(*args) for f in equation.atoms(sp.Function) if f.func.__module__ is None and len(f.args)>1}
    for original,changed in fields.items():
        if original in graph.names:
            graph.names[changed]=graph.names[original].split('(')[0]+'('+','.join(sp.latex(a) for a in args)+')'
    # Preserve explicit uniform-source functions of time.
    converted=sp.Eq(equation.lhs.xreplace(fields),equation.rhs.xreplace(fields),evaluate=False)
    def divergence(expression):
        terms=[]
        for axis,scale in zip(axes,h):
            component_v=sp.Function(f'velocity_{axis}__{key}')(*args)
            component_j=sp.Function(f'flux_{axis}__{key}')(*args)
            graph.names[component_v]=rf'v_{{{sp.latex(axis)}}}'+('('+','.join(sp.latex(a) for a in args)+')')
            graph.names[component_j]=rf'j_{{i,{sp.latex(axis)}}}'+('('+','.join(sp.latex(a) for a in args)+')')
            component=expression.xreplace({velocity:component_v,fields.get(flux,flux):component_j})
            component=component.replace(lambda e:isinstance(e,Gradient),lambda e:sp.diff(e.args[0],axis)/scale)
            terms.append(sp.diff(measure/scale*component,axis)/measure)
        return sp.Add(*terms)
    expanded=sp.Eq(*(side.replace(lambda e:isinstance(e,Divergence),lambda e:divergence(e.args[0])).doit() for side in (converted.lhs,converted.rhs)),evaluate=False)
    conditions=('Orthogonal '+{'cartesianas':'Cartesian','cilindricas':'cylindrical','esfericas':'spherical'}[chart]+' coordinates',)+tuple('Fields independent of '+str(axis) for axis,excluded in zip(axes,state['invariantes']) if excluded)
    if chart!='cartesianas':conditions+=('Away from coordinate singularities; metric factors are retained',)
    graph.add(key+'.operators',expanded.lhs,expanded.rhs,'Expand divergence and gradient with the declared coordinate dependencies','orthogonal_coordinate_expansion',(current,),conditions,family='matter')
    return key+'.operators'






def local_component_law(graph,key,rho,velocity,flux,generation,consumption):
    """One law producer for instantiated domains and unbound law previews."""
    return graph.add(key,sp.diff(rho,sp.Symbol('t',real=True)),-Divergence(rho*velocity+flux)+generation-consumption,'Local component mass conservation',family='matter')


def equation_graph(model,owner,state,*,unbound=False):
    from .material_derivation import normalize_formulation
    state=normalize_formulation(state)
    volume=next(v for v in model['volumenes'] if v['id']==owner)
    index=next(i+1 for i,v in enumerate(model['volumenes']) if v['id']==owner)
    t=sp.Symbol('t',real=True);x,y,z=sp.symbols('x y z',real=True);coordinates=(x,y,z,t)
    v,vb=sp.symbols(f'v__{owner} v_b__{owner}',real=True)
    graph=EquationGraph({v:r'\mathbf v',vb:r'\mathbf v_b'})
    field=state['campo'];final=[];symbols={};bindings={};component_nodes=[]
    incident=[s for s in model['corrientes'] if owner in (s['desde'],s['hasta'])]
    def label(expression,latex):graph.names[expression]=latex;return expression
    for component in ([None] if unbound else volume['componenteIds']):
        key=f'matter.{owner}.{component if component is not None else "generic"}'
        ci=None if unbound else model['componentes'].index(next(c for c in model['componentes'] if c['id']==component))+1
        sub='i' if unbound else rf'v_{index},i_{ci}'
        rho=label(sp.Function(f'rho__{owner}__{component}')(*coordinates),rf'\rho_{{{sub}}}(\mathbf x,t)')
        mass=label(sp.Function(f'm__{owner}__{component}')(t),rf'm_{{{sub}}}')
        flux=label(sp.Function(f'j__{owner}__{component}')(*coordinates),rf'\mathbf j_{{{sub}}}(\mathbf x,t)')
        generation=label(sp.Function(f'g__{owner}__{component}')(*coordinates),rf'\gamma_{{{sub}}}(\mathbf x,t)')
        consumption=label(sp.Function(f'c__{owner}__{component}')(*coordinates),rf'\chi_{{{sub}}}(\mathbf x,t)')
        G=label(sp.Function(f'G__{owner}__{component}')(t),rf'G_{{{sub}}}')
        C=label(sp.Function(f'C__{owner}__{component}')(t),rf'C_{{{sub}}}')
        remainder=label(sp.Function(f'Phi__{owner}__{component}')(t),rf'\Phi_{{{sub},0}}')
        domain_volume=label(sp.Function(f'V__{owner}')(t),r'V(t)')
        mean_density=label(sp.Function(f'rho_mean__{owner}__{component}')(t),rf'\bar\rho_{{{sub}}}(t)')
        transport=rho*v+flux
        local_component_law(graph,key+'.local',rho,v,flux,generation,consumption)
        current=key+'.local';zeros={}
        diffusion={}
        if field.get('difusion','flujo')!='flujo' and not field.get('sinDifusion') and (unbound or len(volume['componenteIds'])!=1):
            diffusivity=label(sp.Function(f'D__{owner}__{component}')(*coordinates),rf'D_{{{sub}}}(\mathbf x,t)')
            if field['difusion']=='laplaciano':
                diffusivity=label(diffusivity.func(t),rf'D_{{{sub}}}(t)')
                law=-diffusivity*Gradient(rho)
                conditions=('Spatially uniform mixture density and diffusivity; mass-fraction Fick law reduces to a density gradient',)
            else:
                mixture=label(sp.Function(f'rho_mixture__{owner}')(*coordinates),r'\rho(\mathbf x,t)')
                law=-mixture*diffusivity*Gradient(rho/mixture)
                conditions=('Fick constitutive approximation in a mass-average frame; positive mixture density',)
            graph.add(key+'.fick',flux,law,'Declare the Fick diffusion closure','constitutive_relation',assumptions=conditions,family='matter',kind='definition')
            diffusion[flux]=law
            graph.substitute(key+'.fick-apply',current,diffusion,'Substitute the diffusion closure in conservation',inputs=(key+'.fick',));current=key+'.fick-apply'
            transport=transport.xreplace(diffusion)
        if not unbound and len(volume['componenteIds'])==1:
            graph.add(key+'.relative-flux',flux,0,'Pure-component diffusion relative to the mass-average velocity','mass_average_identity',family='matter',kind='definition')
            zeros[flux]=0
        if field.get('sinReaccion') or field.get('sinGeneracion'):zeros[generation]=0
        if field.get('sinReaccion') or field.get('sinConsumo'):zeros[consumption]=0
        if field.get('sinDifusion'):zeros[flux]=0
        if field.get('sinConveccion'):zeros[v]=0
        if zeros:
            reasons={flux:'Zero diffusion relative to the mass-average velocity' if len(volume['componenteIds'])==1 else 'Negligible diffusive transport',generation:'No component generation',consumption:'No component consumption',v:'Negligible convective transport'}
            graph.substitute(key+'.terms',current,zeros,'Apply the declared source and transport assumptions',tuple(reasons[s] for s in zeros));current=key+'.terms'
        uniform_sources={}
        for role,source,total,prefix in [('generacion',generation,G,r'\gamma'),('consumo',consumption,C,r'\chi')]:
            if source in zeros:continue
            if state.get(role+'Uniforme') or field.get(role+'Uniforme') or all(state['invariantes']):
                uniform=label(source.func(t),prefix+rf'_{{{sub}}}(t)')
                uniform_sources[source]=(uniform,total)
                bindings[uniform]=('generation_density' if role=='generacion' else 'consumption_density',owner,component)
                bindings[domain_volume]=('volume',owner,None)
                graph.add(key+'.uniform-'+role,source,uniform,'Declare spatially uniform '+('generation' if role=='generacion' else 'consumption'),'assumption',assumptions=('Spatially uniform does not mean constant in time',),family='matter',kind='definition')
        if state['vista']=='campo' and uniform_sources:
            graph.substitute(key+'.uniform-sources',current,{source:pair[0] for source,pair in uniform_sources.items()},'Apply the spatial source dependencies',inputs=tuple(key+'.uniform-'+role for role,source in [('generacion',generation),('consumo',consumption)] if source in uniform_sources));current=key+'.uniform-sources'
        if state['vista']=='campo' and (state['expandida'] or any(state['invariantes'])):
            current=expand_local_operators(graph,key,current,state,rho,v,flux,t)
        if state['vista']!='campo':
            graph.transform(key+'.volume',current,VolumeIntegral,'Integrate both sides over the control domain','volume_integration');current=key+'.volume'
            graph.transform(key+'.gauss',current,lambda e:e.replace(lambda x:isinstance(x,VolumeIntegral) and isinstance(x.args[0],Divergence),lambda x:BoundaryFlux(x.args[0].args[0])),
                            'Apply Gauss to every integrated divergence','divergence_theorem',('Admissible oriented boundary and regular fields',));current=key+'.gauss'
            moving=BoundaryFlux(rho*vb)
            graph.add(key+'.reynolds',sp.Derivative(VolumeIntegral(rho),t,evaluate=False),VolumeIntegral(sp.diff(rho,t))+moving,
                      'Reynolds transport for the moving integration domain','transport_theorem',family='matter',kind='definition')
            graph.substitute(key+'.transport',current,{VolumeIntegral(sp.diff(rho,t)):sp.diff(VolumeIntegral(rho),t)-moving},
                             'Substitute the moving-domain derivative into conservation',inputs=(key+'.reynolds',));current=key+'.transport'
            equation=graph.nodes[current].equation
            graph.add(key+'.relative',equation.lhs+moving,sp.expand(equation.rhs+moving),'Collect transport relative to the domain boundary','add_to_both_sides',(current,),family='matter');current=key+'.relative'
            if state['fija']:
                graph.substitute(key+'.fixed',current,{vb:0},'Fix the geometric boundary velocity',('Fixed integration boundary, not fixed material inventory',));current=key+'.fixed'
            for suffix,symbol,definition,title in [('inventory',mass,VolumeIntegral(rho),'Define the component inventory'),('generation',G,VolumeIntegral(generation),'Define integrated generation'),('consumption',C,VolumeIntegral(consumption),'Define integrated consumption')]:
                graph.add(key+'.'+suffix,symbol,definition,title,'definition',family='matter',kind='definition')
            graph.substitute(key+'.inventory-form',current,{VolumeIntegral(rho):mass,VolumeIntegral(generation):G,VolumeIntegral(consumption):C},
                             'Substitute inventory and integrated source definitions',inputs=tuple(key+'.'+s for s in ('inventory','generation','consumption')));current=key+'.inventory-form'
            if state['vista']=='cantidad':
                oriented=sp.S.Zero
                for stream in incident:
                    if not unbound and component not in stream['componenteIds']:continue
                    si=model['corrientes'].index(stream)+1
                    q=label(sp.Function(f'q__{stream["id"]}__{component}')(t),rf'\dot m_{{s_{si},'+('i' if unbound else f'i_{ci}')+'}')
                    oriented+=(int(stream['hasta']==owner)-int(stream['desde']==owner))*q
                    bindings[q]=('stream',stream['id'],component)
                outward=BoundaryFlux(transport)-BoundaryFlux(rho*vb)
                if state['fija']:outward=outward.subs(vb,0)
                if zeros:outward=outward.subs(zeros,simultaneous=True)
                if outward!=0:
                    graph.add(key+'.partition',outward,-oriented+remainder,'Partition the oriented boundary into declared connections and its complement','boundary_partition',family='matter',kind='definition')
                    # The conservation equation contains -outward. Replacing its
                    # individual linear surface terms preserves exact signs.
                    equation=graph.nodes[current].equation
                    rhs=sp.expand(equation.rhs)
                    reduced=sp.simplify(rhs+outward)
                    graph.add(key+'.ports',equation.lhs,reduced+oriented-remainder,'Substitute the boundary partition into conservation','substitution',(current,key+'.partition'),family='matter');current=key+'.ports'
                if state['restoImpermeable']:
                    graph.substitute(key+'.closed',current,{remainder:0},'Close only the unassigned boundary complement',('No material transport through the boundary complement',));current=key+'.closed'
            for source,(uniform,total) in uniform_sources.items():
                role='generacion' if source==generation else 'consumo'
                graph.add(key+'.integrate-'+role,VolumeIntegral(source),uniform*domain_volume,'Integrate the spatially uniform source','uniform_volume_integral',(key+'.uniform-'+role,),('The volume is finite; the source is uniform throughout it',),family='matter',kind='definition')
                graph.substitute(key+'.source-'+role,current,{total:uniform*domain_volume},'Substitute the integrated uniform source',inputs=(key+'.integrate-'+role,));current=key+'.source-'+role
            if state.get('cantidadVolumen'):
                graph.add(key+'.mean-definition',mean_density,VolumeIntegral(rho)/domain_volume,'Define volume-average component density','definition',assumptions=('Positive control volume',),family='matter',kind='definition')
                graph.add(key+'.mean-inventory',mass,mean_density*domain_volume,'Express inventory through its volume average','substitution',(key+'.inventory',key+'.mean-definition'),('Positive control volume',),family='matter',kind='definition')
                graph.substitute(key+'.density-volume',current,{mass:mean_density*domain_volume},'Replace component inventory with mean density times volume',inputs=(key+'.mean-inventory',));current=key+'.density-volume'
                if state.get('densidadComunPuertos'):
                    for si,stream in enumerate(model['corrientes'],1):
                        if stream not in incident:continue
                        q=next((q for q,b in bindings.items() if b==('stream',stream['id'],component)),None)
                        if q is None:continue
                        flow=label(sp.Function(f'Q__{stream["id"]}')(t),rf'Q_{{s_{si}}}(t)')
                        relation=key+f'.common-density-{si}'
                        graph.add(relation,q,mean_density*flow,'Relate convective mass flow to volumetric flow','constitutive_relation',assumptions=('The port carries convection only and has the domain mean component density',),family='matter',kind='definition')
                        graph.substitute(relation+'.apply',current,{q:mean_density*flow},'Apply the declared common port density',inputs=(relation,));current=relation+'.apply'
                if state.get('densidadMediaConstante'):
                    fixed_density=label(sp.Symbol(f'rho_mean__{owner}__{component}',real=True),rf'\bar\rho_{{{sub}}}')
                    graph.add(key+'.constant-density',mean_density,fixed_density,'Mean component density is constant in time','assumption',family='matter',kind='definition')
                    graph.substitute(key+'.constant-density-apply',current,{mean_density:fixed_density},'Apply constant mean density',inputs=(key+'.constant-density',));current=key+'.constant-density-apply'
            if state['fija']:
                fixed_volume=label(sp.Symbol(f'V__{owner}',positive=True),r'V')
                bindings[fixed_volume]=('volume',owner,None)
                graph.add(key+'.fixed-volume',domain_volume,fixed_volume,'Fixed boundary implies constant geometric volume','geometry',assumptions=('Fixed integration boundary',),family='matter',kind='definition')
                graph.substitute(key+'.fixed-volume-apply',current,{domain_volume:fixed_volume},'Apply the constant geometric volume',inputs=(key+'.fixed-volume',));current=key+'.fixed-volume-apply'
            if state.get('cantidadVolumen') and (state.get('expandirProducto') or state.get('densidadMediaConstante') or state['fija']):
                graph.transform(key+'.product-rule',current,lambda e:e.doit(),'Differentiate the density–volume product','product_rule');current=key+'.product-rule'
            for si,stream in enumerate(model['corrientes'],1):
                if stream not in incident:continue
                q=next((q for q,b in bindings.items() if b==('stream',stream['id'],component)),None)
                if q is None:continue
                if state['uniforme'] and not state.get('densidadComunPuertos'):
                    area=label(sp.Function(f'A_port__{stream["id"]}')(t),rf'A_{{s_{si}}}(t)')
                    normal_flux=label(sp.Function(f'normal_flux__{stream["id"]}__{component}')(t),rf'f_{{i,s_{si},n}}(t)')
                    relation=key+f'.uniform-port-{si}'
                    graph.add(relation,q,area*normal_flux,'Integrate uniform normal mass flux over a port','uniform_surface_integral',assumptions=('Normal relative mass flux is uniform across this port; its sign follows the declared stream orientation',),family='matter',kind='definition')
                    # Keep the integrated port flow as the shared interface.
                    # Uniformity constrains its local flux; it does not create
                    # an extra independent input to numerical compilation.
                if stream.get('constante'):
                    constraint=key+f'.constant-port-{si}'
                    graph.add(constraint,sp.diff(q,t),0,'Declared time-constant component mass flow','assumption',assumptions=('Constant in time does not imply spatial uniformity',),family='matter',kind='constraint')
                    final.append(constraint)
        if state.get('sinAcumulacion') or field.get('estacionario'):
            graph.add(key+'.stationary',graph.nodes[current].equation.lhs,0,'Declared zero-rate condition; retain the dynamic conservation equation','assumption',inputs=(current,),family='matter',kind='constraint')
        final.append(current);component_nodes.append(current)
        if key+'.stationary' in graph.nodes:final.append(key+'.stationary')
        symbols.update({str(expression):expression for expression in (mass,rho,flux,G,C,remainder)})
        bindings[mass]=('inventory',owner,component);bindings[G]=('generation',owner,component);bindings[C]=('consumption',owner,component);bindings[remainder]=('remainder',owner,component)
    if component_nodes and not unbound:
        combined=graph.combine(f'matter.{owner}.sum',component_nodes,'Sum component conservation equations')
        total=label(sp.Function(('rho_total' if state['vista']=='campo' else 'm_total')+'__'+owner)(*(coordinates if state['vista']=='campo' else (t,))),rf'\rho_{{v_{index}}}(\mathbf x,t)' if state['vista']=='campo' else rf'm_{{v_{index}}}')
        components=[next(s for s,b in bindings.items() if b==('inventory',owner,c)) if state['vista']!='campo' else next(s for s in symbols.values() if str(s.func)==f'rho__{owner}__{c}') for c in volume['componenteIds']]
        definition=graph.add(f'matter.{owner}.total-definition',total,sum(components),'Define total mass from component amounts','definition',family='matter',kind='definition',dependent=True)
        graph.differentiate(f'matter.{owner}.total-rate',f'matter.{owner}.total-definition',t,'Differentiate the total definition')
        derivative=graph.nodes[f'matter.{owner}.total-rate'].equation
        graph.substitute(f'matter.{owner}.total',f'matter.{owner}.sum',{derivative.rhs:derivative.lhs},'Express the derived total conservation using its definition',inputs=(f'matter.{owner}.total-rate',))
        graph.nodes[f'matter.{owner}.total'].dependent=True
        final.append(f'matter.{owner}.total');bindings[total]=('total_inventory',owner,None)
    return graph,final,bindings
