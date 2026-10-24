"""Replayable Cauchy -> Navier--Stokes -> hydraulic/angular reductions.

Model authoring only. Every closure and zero-storage constraint is explicit;
none of these equations is silently admitted by an existing time integrator.
"""
from core.modelo.operation_journal import JournalError, keys, read_operations, replay, evidence, edit
from functools import lru_cache


@lru_cache(maxsize=1)
def reduced_relations():
    """Canonical scalar relations used for publication and independent checks.

    They are symbolic Model equations, not a second time integrator.
    """
    import sympy as sp
    names = {"L": "L", "A": "A", "massFlow": r"\dot m", "massFlowRate": r"\frac{d\dot m}{dt}",
             "p1": "p_1", "p2": "p_2", "drive": r"\Delta p_{\mathrm{drive}}", "loss": r"\Delta p_{\mathrm{loss}}",
             "rho": r"\rho_{\mathrm{ref}}", "g": "g", "z1": "z_1", "z2": "z_2", "f": "f_D", "D": "D_h", "K": "K",
             "J": "J", "speed": r"\omega", "acceleration": r"\frac{d\omega}{dt}", "motorTorque": r"\tau_{\mathrm{motor}}",
             "fluidTorque": r"\tau_f", "bearingTorque": r"\tau_{\mathrm{bearing}}", "r2": "r_2", "b2": "b_2", "Q": "Q", "beta2": r"\beta_2",
             "transfer": "Y_E", "c1": "c_1", "c2": "c_2", "mu": r"\mu"}
    s = {name: sp.Symbol(name, real=True) for name in names}
    transfer = s['speed']**2*s['r2']**2-s['speed']*s['Q']*sp.cot(s['beta2'])/(2*sp.pi*s['b2'])
    from .momentum_reductions import path_reduction,wall_reduction,WALL_FLAGS
    display_names={s[key]: latex for key,latex in names.items()}
    _,inertance=path_reduction(s,display_names)
    _,wall=wall_reduction(s,display_names,{k:True for k in WALL_FLAGS})
    relations = {
        'inertance': (inertance.lhs,inertance.rhs),
        'loss': (s['loss'], (s['f']*s['L']/s['D']+s['K'])*s['massFlow']*sp.Abs(s['massFlow'])/(2*s['rho']*s['A']**2)),
        'rotor': (s['J']*s['acceleration'], s['motorTorque']-s['fluidTorque']-s['bearingTorque']),
        'idealTorque': (s['fluidTorque'], s['massFlow']*(s['speed']*s['r2']**2-s['Q']*sp.cot(s['beta2'])/(2*sp.pi*s['b2']))),
        'idealTransfer': (s['transfer'], transfer),
        'pressureRise': (s['p2']-s['p1'], s['rho']*(s['transfer']-(s['c2']**2-s['c1']**2)/2-s['g']*(s['z2']-s['z1']))),
        'laminarLoss': (wall['loss'].lhs,wall['loss'].rhs),
    }
    relations['pressureDrop'] = (s['p1']-s['p2'], sp.solve(sp.Eq(*relations['inertance']), s['p1'])[0]-s['p2'])
    return s, relations, {s[key]: latex for key, latex in names.items()}


def scalar_latex(key):
    import sympy as sp
    _, relations, names = reduced_relations()
    lhs, rhs = relations[key]
    return sp.latex(sp.Eq(lhs, rhs, evaluate=False), symbol_names=names)

FORMAT = "rage.momentum-derivation"
BASE_FLAGS = ("pressureStress", "newtonian", "massContinuity", "constantViscosity", "divergenceFree",
         "fixedBoundary", "uniformSections", "constantArea", "referenceDensity", "uniformGravity",
         "darcyWeisbach", "angularMomentum", "shaftDynamics", "zeroAngularAccumulation",
         "zeroInletSwirl", "radialOutlet", "idealBladeGuidance", "losslessPassage", "equalPortMassFlow", "noOtherTorque",
         "impermeableWall", "rotorActuator", "adiabaticPassage", "zeroPassageEnergyAccumulation")
FIELD_FLAGS = ("expandCartesian", "invariantX", "invariantY", "invariantZ", "velocityInvariantX", "velocityInvariantY", "velocityInvariantZ", "zeroVelocityX", "zeroVelocityY", "zeroVelocityZ",
               "zeroLocalAccumulation", "negligibleConvection", "negligibleViscousStress", "negligibleBodyForce")
from .momentum_reductions import WALL_FLAGS,STORAGE_FLAGS
FLAGS = BASE_FLAGS + FIELD_FLAGS + ("zeroTotalAccumulation", "laminarCircular") + WALL_FLAGS + STORAGE_FLAGS


def fundamental():
    return {"form": "local", **{key: False for key in FLAGS}, "inletStreamId": None, "outletStreamId": None}


def changes(value):
    keys(value, [], fundamental())
    if not value:
        raise JournalError("A momentum operation needs explicit changes.")
    for name, item in value.items():
        if name == "form":
            if item not in ("local", "integral", "ports", "hydraulic"):
                raise JournalError("Unknown momentum representation.")
        elif name in ("inletStreamId", "outletStreamId"):
            if item is not None and (not isinstance(item, str) or not item.strip()):
                raise JournalError("A momentum port references a stream ID or null.")
        elif type(item) is not bool:
            raise JournalError("Momentum assumptions must be booleans.")


def normalize(value):
    state = fundamental()
    changes(value)
    state.update(value)
    def require(condition, message):
        if not condition:
            raise JournalError(message)
    if state["newtonian"]:
        require(state["pressureStress"], "Separate pressure stress before declaring a Newtonian constitutive law.")
    if state["constantViscosity"]:
        require(state["newtonian"], "Constant viscosity requires the Newtonian constitutive law.")
    if state["divergenceFree"]:
        require(state["massContinuity"], "Record total mass continuity before the divergence-free approximation.")
    if any(state[key] for key in FIELD_FLAGS):
        require(state["form"] == "local", "Cartesian field reductions currently require local form. Remove them before integrating; their boundary consequences are not inferred.")
    if state["negligibleViscousStress"]:
        require(state["pressureStress"], "Separate pressure from viscous stress before neglecting the latter.")
    if state["zeroTotalAccumulation"]:
        require(state["form"] != "local", "Total fluid-momentum storage is an integrated inventory, distinct from local stationarity.")
    if state["form"] in ("ports", "hydraulic"):
        require(state["fixedBoundary"] and state["uniformSections"] and state["impermeableWall"], "Two-port reduction requires a fixed control envelope, impermeable walls and uniform section velocities/stresses.")
    if state["form"] == "hydraulic":
        require(state["constantArea"] and state["referenceDensity"] and state["uniformGravity"], "Hydraulic inertance requires constant area, a constant reference-density approximation and uniform gravity.")
    if state["darcyWeisbach"]:
        require(state["form"] == "hydraulic", "The lumped wall-loss closure requires the hydraulic reduction.")
    if state['laminarCircular']:
        require(state['form']=='hydraulic' and state['newtonian'] and state['constantViscosity'], 'The circular laminar wall closure requires hydraulic form and constant Newtonian viscosity.')
        require(not state['darcyWeisbach'], 'Choose one wall-loss closure; do not add Poiseuille and Darcy friction for the same wall.')
    if state['circularSection']:
        require(state['form']=='hydraulic','Declare the straight hydraulic geometry before reducing its section profile.')
    if state['developedProfile']:
        require(state['circularSection'] and state['newtonian'] and state['constantViscosity'],'A developed circular profile requires circular geometry and uniform Newtonian viscosity.')
    if any(state[k] for k in ('quasiSteadyWall','regularAxis','noSlipWall')):
        require(state['developedProfile'],'Declare the profile geometry and developed-flow dependencies first.')
    if any(state[k] for k in WALL_FLAGS):
        require(not state['darcyWeisbach'],'A profile-derived wall relation and Darcy closure cannot count the same wall twice.')
    if state['verticalGravity']:
        require(state['pressureStress'] and state['uniformGravity'],'Vertical gravity requires pressure separation and uniform gravity.')
        require(not state['negligibleBodyForce'] and not state['invariantZ'],'Vertical gravity cannot be removed or combined with globally invariant pressure in z.')
    if state['pressureReference']:
        require(all(state[k] for k in ('verticalGravity','referenceDensity','negligibleConvection','negligibleViscousStress','zeroLocalAccumulation')),'Pressure integration requires explicit local force reduction, constant density and a vertical gravity direction.')
    if state['prismaticStorage']:
        require(state['pressureReference'],'Integrate pressure from its reference before coupling the prismatic inventory geometry.')
    if state["angularMomentum"]:
        require(state["form"] in ("ports", "hydraulic"), "Integrate and declare the ports before taking the angular moment.")
    for name in ("shaftDynamics", "zeroAngularAccumulation", "zeroInletSwirl", "radialOutlet", "idealBladeGuidance", "losslessPassage", "equalPortMassFlow", "noOtherTorque", "rotorActuator", "adiabaticPassage", "zeroPassageEnergyAccumulation"):
        if state[name]:
            require(state["angularMomentum"], "The rotating-passage assumption requires the angular momentum balance.")
    if state["shaftDynamics"] or state["idealBladeGuidance"]:
        require(state["rotorActuator"], "Declare the unresolved-rotor actuator representation before shaft/blade coupling.")
    if state["radialOutlet"]:
        require(state["form"] == "ports" and not state["constantArea"], "A radial annular outlet is incompatible with the straight constant-area hydraulic reduction. Undo to the port branch first.")
    if state["idealBladeGuidance"]:
        require(state["radialOutlet"], "Ideal blade guidance requires the declared radial exit geometry.")
    if state["losslessPassage"]:
        require(euler_compatible(state) and state["rotorActuator"] and state["referenceDensity"] and state["adiabaticPassage"] and state["zeroPassageEnergyAccumulation"], "The pressure-rise reduction requires Euler passage compatibility, rotor work, reference density, adiabatic passage and explicit zero passage energy accumulation.")
    return state


def euler_compatible(state):
    return all(state[key] for key in ("angularMomentum", "equalPortMassFlow", "noOtherTorque", "zeroAngularAccumulation"))


def ideal_compatible(state):
    return euler_compatible(state) and state["idealBladeGuidance"] and state["zeroInletSwirl"]


CHOICES = {
    "pressure_stress": ("Decompose Cauchy stress into pressure and viscous stress", {"pressureStress": True}),
    "newtonian": ("Derive Navier–Stokes · isotropic Newtonian stress", {"newtonian": True}),
    "mass_continuity": ("Use total mass continuity · zero net bulk mass source", {"massContinuity": True}),
    "constant_viscosity": ("Spatially uniform shear and second-viscosity coefficients", {"constantViscosity": True}),
    "divergence_free": ("Divergence-free velocity · material density is conserved", {"divergenceFree": True}),
    "integrate": ("Integrate momentum conservation · Gauss and Reynolds transport", {"form": "integral"}),
    "fixed_boundary": ("Fixed control-volume boundary", {"fixedBoundary": True}),
    "uniform_sections": ("Section averages · uniform local velocity components and pressure", {"uniformSections": True}),
    "impermeable_wall": ("No material flux through walls · two-port mass boundary", {"impermeableWall": True}),
    "ports": ("Resolve inlet, outlet and wall momentum contributions", {"form": "ports"}),
    "constant_area": ("Straight constant-area flow path · equal port areas", {"constantArea": True}),
    "reference_density": ("Constant reference density over this reduced flow path", {"referenceDensity": True}),
    "uniform_gravity": ("Uniform conservative gravity · declared elevation difference", {"uniformGravity": True}),
    "hydraulic": ("Project onto the flow direction · retain hydraulic inertance", {"form": "hydraulic"}),
    "darcy_weisbach": ("Declare Darcy–Weisbach and local-loss constitutive closure", {"darcyWeisbach": True}),
    "angular_momentum": ("Take moments about a fixed axis · symmetric stress, no body couples", {"angularMomentum": True}),
    "rotor_actuator": ("Unresolved rotor · equivalent force/torque in a fixed control envelope", {"rotorActuator": True}),
    "shaft_dynamics": ("Couple a rigid rotor · retain shaft angular inertia", {"shaftDynamics": True}),
    "equal_port_mass_flow": ("Zero net passage mass storage · retain material conservation", {"equalPortMassFlow": True}),
    "no_other_torque": ("No other axial torque · pressure/body/housing torque neglected", {"noOtherTorque": True}),
    "zero_angular_accumulation": ("Constrain passage angular accumulation to zero · retain its dynamic balance", {"zeroAngularAccumulation": True}),
    "zero_inlet_swirl": ("Axial/radial inlet without tangential prewhirl", {"zeroInletSwirl": True}),
    "radial_outlet": ("Full-annulus radial outlet · no blockage", {"radialOutlet": True}),
    "ideal_blade_guidance": ("Ideal blade guidance · no slip, blade angle measured from tangent", {"idealBladeGuidance": True}),
    "lossless_passage": ("Lossless passage · negligible internal-energy change in mechanical-head reduction", {"losslessPassage": True}),
    "adiabatic_passage": ("Adiabatic rotating passage · explicit first-law boundary assumption", {"adiabaticPassage": True}),
    "zero_passage_energy": ("Zero passage energy accumulation · retain its first-law balance", {"zeroPassageEnergyAccumulation": True}),
}


def read_journal(value):
    read_operations(value, FORMAT, changes)
    for entry in value["volumes"].values():
        states = replay({**entry,'cursor':len(entry['operations'])}, fundamental, normalize)
        forms = ("local", "integral", "ports", "hydraulic")
        for operation, previous, state in zip(entry["operations"], states, states[1:]):
            delta = operation["changes"]
            if len(delta) != 1 and set(delta) != {"inletStreamId", "outletStreamId"}:
                raise JournalError("Record one assumption at a time; port identities are bound together.")
            if "form" in delta and forms.index(state["form"]) != forms.index(previous["form"]) + 1:
                raise JournalError("Do not skip integral or port deductions; use Undo to change a branch.")
    return value


def edit_journal(value, owner, action):
    if isinstance(action,dict) and action.get('kind')=='seek':
        import copy
        keys(action,['kind','index']);read_journal(value)
        if owner not in value['volumes'] or type(action['index']) is not int or not 0<=action['index']<=len(value['volumes'][owner]['operations']):raise JournalError('Select an existing physical assumption step.')
        result=copy.deepcopy(value);result['volumes'][owner]['cursor']=action['index']
    elif isinstance(action, dict) and action.get("kind") == "set_assumption":
        keys(action, ["kind", "name", "value"])
        if not isinstance(action['name'], str) or action["name"] not in FLAGS or type(action["value"]) is not bool:
            raise JournalError("Expected one known momentum assumption and a boolean value.")
        label = CONTROL_LABELS[action["name"]][1]
        custom = {"set_assumption": (("Apply: " if action["value"] else "Remove: ") + label, {action["name"]: action["value"]})}
        result = edit(value, owner, {"kind": "set_assumption"}, FORMAT, changes, normalize, fundamental, custom)
    elif isinstance(action, dict) and action.get("kind") == "bind_ports":
        keys(action, ["kind", "inletStreamId", "outletStreamId"])
        read_journal(value)
        if owner not in value["volumes"]:
            raise JournalError("Start from the fundamental law before binding ports.")
        custom = {"bind_ports": ("Bind momentum ports to existing material streams", {k: action[k] for k in ("inletStreamId", "outletStreamId")})}
        result = edit(value, owner, {"kind": "bind_ports"}, FORMAT, changes, normalize, fundamental, custom)
    else:
        result = edit(value, owner, action, FORMAT, changes, normalize, fundamental, CHOICES)
    return read_journal(result)


# Declarative physical controls, not equipment presets. Python owns availability.
CONTROL_LABELS = {
    "pressureStress": ("Stress and transport", "Separate pressure and viscous stress"),
    "newtonian": ("Stress and transport", "Isotropic Newtonian fluid"),
    "massContinuity": ("Stress and transport", "Use total mass continuity"),
    "constantViscosity": ("Stress and transport", "Spatially uniform viscosity coefficients"),
    "divergenceFree": ("Stress and transport", "Divergence-free velocity"),
    "negligibleConvection": ("Stress and transport", "Negligible convective momentum transport"),
    "negligibleViscousStress": ("Stress and transport", "Negligible viscous stress"),
    "negligibleBodyForce": ("Stress and transport", "No body forces"),
    "expandCartesian": ("Space and velocity", "Expand Cartesian components"),
    **{f"invariant{axis.upper()}": ("Space and velocity", f"No variation in {axis}") for axis in "xyz"},
    **{f"velocityInvariant{axis.upper()}": ("Space and velocity", f"No velocity variation in {axis}") for axis in "xyz"},
    **{f"zeroVelocity{axis.upper()}": ("Space and velocity", f"Zero {axis} velocity") for axis in "xyz"},
    "zeroLocalAccumulation": ("Accumulation", "No local momentum accumulation"),
    "zeroTotalAccumulation": ("Accumulation", "No total fluid-momentum accumulation"),
    "fixedBoundary": ("Control volume and ports", "Fixed boundary"),
    "impermeableWall": ("Control volume and ports", "Impermeable remaining wall"),
    "uniformSections": ("Control volume and ports", "Uniform local port components and pressure"),
    "constantArea": ("Geometry and hydraulic closure", "Straight path with constant area"),
    "referenceDensity": ("Geometry and hydraulic closure", "Constant reference density"),
    "uniformGravity": ("Geometry and hydraulic closure", "Uniform conservative gravity"),
    "darcyWeisbach": ("Geometry and hydraulic closure", "Darcy–Weisbach and local losses"),
    "laminarCircular": ("Geometry and hydraulic closure", "Quasi-steady laminar circular wall closure"),
    "circularSection": ("Geometry and hydraulic closure", "Circular cross-section"),
    "developedProfile": ("Geometry and hydraulic closure", "Fully developed axial profile"),
    "quasiSteadyWall": ("Geometry and hydraulic closure", "Neglect profile acceleration in the auxiliary wall problem"),
    "regularAxis": ("Geometry and hydraulic closure", "Finite velocity and shear at the section axis"),
    "noSlipWall": ("Geometry and hydraulic closure", "No slip at the wall"),
    "verticalGravity": ("Reference and inventory geometry", "Gravity acts in the negative vertical direction"),
    "pressureReference": ("Reference and inventory geometry", "Integrate pressure from a declared surface reference"),
    "prismaticStorage": ("Reference and inventory geometry", "Constant horizontal section for the material inventory"),
    "angularMomentum": ("Angular momentum and shaft", "Develop angular momentum"),
    "rotorActuator": ("Angular momentum and shaft", "Equivalent rotor force and torque"),
    "shaftDynamics": ("Angular momentum and shaft", "Retain rotor dynamics"),
    "equalPortMassFlow": ("Angular momentum and shaft", "No passage mass accumulation"),
    "noOtherTorque": ("Angular momentum and shaft", "No other axial torque"),
    "zeroAngularAccumulation": ("Angular momentum and shaft", "No passage angular-momentum accumulation"),
    "zeroInletSwirl": ("Geometry and energy closures", "No inlet swirl"),
    "radialOutlet": ("Geometry and energy closures", "Full-annulus radial outlet"),
    "idealBladeGuidance": ("Geometry and energy closures", "Ideal blade guidance without slip"),
    "adiabaticPassage": ("Geometry and energy closures", "Adiabatic passage"),
    "zeroPassageEnergyAccumulation": ("Geometry and energy closures", "No passage energy accumulation"),
    "losslessPassage": ("Geometry and energy closures", "Lossless mechanical-head approximation"),
}


def controls(state):
    result = []
    for key, (group, label) in CONTROL_LABELS.items():
        reason = ""
        try:
            normalize({**state, key: not state[key]})
        except JournalError as error:
            reason = str(error)
        result.append({"key": key, "group": group, "label": label, "value": state[key], "canChange": not reason, "reason": reason})
    return result


def validate_model_journal(model):
    journal = model.get("motores", {}).get("momentumDerivation")
    if journal is None:
        return []
    read_journal(journal)
    volumes = {v["id"]: v for v in model["volumenes"]}
    streams = {s["id"]: s for s in model["corrientes"]}
    result = []
    for owner, entry in journal["volumes"].items():
        if owner not in volumes:
            raise JournalError("Momentum journal references a missing control volume: " + owner)
        state = replay(entry, fundamental, normalize)[-1]
        for key, endpoint in (("inletStreamId", "hasta"), ("outletStreamId", "desde")):
            stream_id = state[key]
            if stream_id is not None and (stream_id not in streams or streams[stream_id][endpoint] != owner or streams[stream_id]["desde"] == streams[stream_id]["hasta"]):
                raise JournalError("Momentum ports must reference incident streams with the declared nominal orientation.")
        if state["inletStreamId"] is not None and state["inletStreamId"] == state["outletStreamId"]:
            raise JournalError("Inlet and outlet must be distinct streams.")
        result.append(evidence(owner, entry, ["momento." + owner] if volumes[owner]["balances"]["momento"] else []))
    return result


def cartesian_relations(state, material=False):
    """Conservative Cartesian component equations, reduced by field substitutions.

    An invariant coordinate removes field dependence, not a vector component or
    its transverse force balance. All three equations survive even at v_i=0.
    """
    import sympy as sp
    x = sp.symbols('x y z', real=True)
    t = sp.Symbol('t', real=True)
    dependencies = tuple(q for q, axis in zip(x, 'XYZ') if not state[f'invariant{axis}']) + (t,)
    def field(name, velocity=False):
        args = tuple(q for q, axis in zip(x, 'XYZ') if q in dependencies and (not velocity or not state[f'velocityInvariant{axis}'])) + (t,)
        return sp.Function(name)(*args)
    rho, p = field('rho'), field('p')
    v = [sp.S.Zero if state[f'zeroVelocity{axis}'] else field('v_' + axis.lower(), velocity=True) for axis in 'XYZ']
    mu = sp.Function('mu')(t) if state['constantViscosity'] else field('mu')
    lam = sp.Function('lambda')(t) if state['constantViscosity'] else field('lambda')
    divergence = sum(sp.diff(v[j], x[j]) for j in range(3))
    result = []
    for i in range(3):
        rate = sp.diff(rho*v[i], t)
        convection = sp.S.Zero if state['negligibleConvection'] else sum(sp.diff(rho*v[i]*v[j], x[j]) for j in range(3))
        if material and state['massContinuity'] and not state['negligibleConvection']:
            rate = rho*sp.diff(v[i], t)
            convection = rho*sum(v[j]*sp.diff(v[i], x[j]) for j in range(3))
        if not state['pressureStress']:
            force = sum(sp.diff(field(f'sigma_{i+1}{j+1}'), x[j]) for j in range(3))
        else:
            viscous = sp.S.Zero
            if not state['negligibleViscousStress']:
                if not state['newtonian']:
                    viscous = sum(sp.diff(field(f'tau_{i+1}{j+1}'), x[j]) for j in range(3))
                elif state['constantViscosity'] and state['divergenceFree']:
                    viscous = mu*sum(sp.diff(v[i], q, 2) for q in x)
                else:
                    viscous = sum(sp.diff(mu*(sp.diff(v[i], x[j])+sp.diff(v[j], x[i])) + (lam*divergence if i == j and not state['divergenceFree'] else 0), x[j]) for j in range(3))
            force = -sp.diff(p, x[i]) + viscous
        if not state['negligibleBodyForce']:
            force += rho*field('b_' + 'xyz'[i])
        result.append((rate, convection, force))
    return result


def component_latex(state, compatibility=False):
    import sympy as sp
    rows = []
    for rate, convection, force in cartesian_relations(state, material=not compatibility):
        relation = sp.Eq(convection if compatibility else rate + convection, force, evaluate=False)
        # Suppress repeated function argument lists in the display only.
        fields = relation.atoms(sp.Function)
        replacements = {f: sp.Symbol(f.func.__name__) for f in fields}
        compact = sp.Eq(relation.lhs.xreplace(replacements), relation.rhs.xreplace(replacements), evaluate=False)
        rows.append(sp.latex(compact, diff_operator=r'\partial', symbol_names={sp.Symbol('rho'): r'\rho', sp.Symbol('mu'): r'\mu', sp.Symbol('lambda'): r'\lambda'}))
    return r'\begin{aligned}' + r'\\[6pt]'.join(rows) + r'\end{aligned}'


def equation(state):
    stress = r"\boldsymbol\sigma" if not state["pressureStress"] else r"-p\mathbf I+\boldsymbol\tau"
    viscous = r"\nabla\!\cdot\boldsymbol\tau"
    if state["newtonian"]:
        viscous = r"\nabla\!\cdot[\mu(\nabla\mathbf v+(\nabla\mathbf v)^T)+\lambda(\nabla\!\cdot\mathbf v)\mathbf I]"
    if state["constantViscosity"]:
        viscous = r"\mu\nabla^2\mathbf v+(\mu+\lambda)\nabla(\nabla\!\cdot\mathbf v)"
    if state["divergenceFree"] and state["constantViscosity"]:
        viscous = r"\mu\nabla^2\mathbf v"
    elif state["divergenceFree"] and state["newtonian"]:
        viscous = r"\nabla\!\cdot[\mu(\nabla\mathbf v+(\nabla\mathbf v)^T)]"
    local_lhs = r"\rho[\partial_t\mathbf v+(\mathbf v\!\cdot\nabla)\mathbf v]" if state["massContinuity"] else r"\partial_t(\rho\mathbf v)+\nabla\!\cdot(\rho\mathbf v\otimes\mathbf v)"
    if state["form"] == "local":
        if any(state[key] for key in FIELD_FLAGS):
            return component_latex(state)
        return local_lhs + "=" + (r"\nabla\!\cdot\boldsymbol\sigma+\rho\mathbf b" if not state["pressureStress"] else "-\\nabla p+" + viscous + r"+\rho\mathbf b")
    if state["form"] == "integral":
        relative = r"\mathbf v" if state["fixedBoundary"] else r"\mathbf v-\mathbf v_b"
        return r"\frac{d}{dt}\int_{V(t)}\rho\mathbf v\,dV+\oint_{\partial V(t)}\rho\mathbf v[(" + relative + r")\!\cdot\mathbf n]dA=\oint_{\partial V(t)}(" + stress + r")\mathbf n\,dA+\int_{V(t)}\rho\mathbf b\,dV"
    if state["form"] == "ports":
        return r"\frac{d\mathbf I_f}{dt}=\dot m_1\bar{\mathbf c}_1^M-\dot m_2\bar{\mathbf c}_2^M-p_1\int_{A_1}\mathbf n\,dA-p_2\int_{A_2}\mathbf n\,dA+\mathbf F_{\tau,\mathrm{ports}}+\mathbf F_{\mathrm{wall}}+\mathbf F_b"
    return scalar_latex('inertance')


def describe_volume(journal, owner, model=None):
    read_journal(journal)
    entry = journal["volumes"].get(owner)
    if entry is None:
        raise JournalError("Start an explicit momentum derivation for this volume.")
    states = replay(entry, fundamental, normalize)
    steps, coupling = [], []
    from .momentum_reductions import reduction_graphs,canonical_path_graph
    symbols,_,symbol_names=reduced_relations()
    algebra_ids={};algebra_values={}
    def row(rows, id_, title, latex, family="momentum"):
        rows.append({"id": id_, "title": title, "latex": latex, "family": family})
    row(steps, "fundamental", "Cauchy momentum balance · inertial frame, general stress", equation(states[0]))
    for operation, previous, state in zip(entry["operations"], states, states[1:]):
        id_ = operation["id"]
        changed = operation["changes"]
        for axis in 'XYZ':
            if changed.get('invariant'+axis):
                row(steps, id_ + '.invariant', 'Remove field dependence along '+axis.lower()+'; retain every momentum component', r'\partial_{'+axis.lower()+r'} f=0\quad\text{for all continuum fields }f')
            if changed.get('zeroVelocity'+axis):
                row(steps, id_ + '.velocity', 'Zero '+axis.lower()+' velocity; retain its transverse force balance', 'v_'+axis.lower()+'=0')
            if changed.get('velocityInvariant'+axis):
                row(steps, id_ + '.velocity-invariance', 'Velocity independent of '+axis.lower()+'; pressure and other fields may still vary', r'\partial_{'+axis.lower()+r'}\mathbf v=\mathbf0')
        if changed.get('negligibleConvection'):
            row(steps, id_ + '.convection', 'Explicit transport approximation; no hidden removal of local inertia', r'\nabla\!\cdot(\rho\mathbf v\otimes\mathbf v)\simeq\mathbf0')
        if changed.get('negligibleViscousStress'):
            row(steps, id_ + '.inviscid', 'Neglect viscous stress, not pressure', r'\boldsymbol\tau\simeq\mathbf0')
        if changed.get('negligibleBodyForce'):
            row(steps, id_ + '.body-force', 'No body force; pressure and surface forces remain', r'\mathbf b=\mathbf0')
        if changed.get('zeroLocalAccumulation'):
            row(steps, id_ + '.local-constraint', 'Fix local momentum inventory; keep its dynamic balance', r'\partial_t(\rho\mathbf v)=\mathbf0')
        if changed.get('zeroTotalAccumulation'):
            row(steps, id_ + '.total-constraint', 'Fix total fluid momentum; keep the integrated dynamic balance', r'\frac{d\mathbf I_f}{dt}=\mathbf0')
        if changed.get("pressureStress"):
            row(steps, id_ + ".stress", "Separate isotropic pressure and viscous stress", r"\boldsymbol\sigma=-p\mathbf I+\boldsymbol\tau")
        if changed.get("newtonian"):
            row(steps, id_ + ".constitutive", "Newtonian closure · retain the second viscosity; no hidden Stokes hypothesis", r"\boldsymbol\tau=\mu(\nabla\mathbf v+(\nabla\mathbf v)^T)+\lambda(\nabla\!\cdot\mathbf v)\mathbf I,\quad \mu\geq0,\quad\lambda+\frac23\mu\geq0")
        if changed.get("massContinuity"):
            row(steps, id_ + ".product", "Expand momentum transport and use total mass continuity", r"\partial_t(\rho\mathbf v)+\nabla\!\cdot(\rho\mathbf v\otimes\mathbf v)=\rho D_t\mathbf v+\mathbf v[\partial_t\rho+\nabla\!\cdot(\rho\mathbf v)]")
            row(coupling, id_ + ".continuity", "Total mass continuity required by the momentum reduction", r"\partial_t\rho+\nabla\!\cdot(\rho\mathbf v)=0", "matter")
        if changed.get("constantViscosity"):
            row(steps, id_ + ".viscosity", "Spatially constant coefficients · expand the stress divergence", r"\nabla\mu=\nabla\lambda=0\Rightarrow\nabla\!\cdot\boldsymbol\tau=\mu\nabla^2\mathbf v+(\mu+\lambda)\nabla(\nabla\!\cdot\mathbf v)")
        if changed.get("divergenceFree"):
            row(steps, id_ + ".kinematic", "Divergence-free limit; material density conservation follows from continuity", r"\nabla\!\cdot\mathbf v=0,\quad D_t\rho=0")
        if changed.get("form") == "integral":
            row(steps, id_ + ".gauss", "Gauss theorem · convert momentum and stress divergences", r"\int_V\nabla\!\cdot\mathbf T\,dV=\oint_{\partial V}\mathbf T\mathbf n\,dA")
            row(steps, id_ + ".reynolds", "Reynolds transport · preserve momentum accumulation", r"\frac{d}{dt}\int_{V(t)}\rho\mathbf v\,dV=\int_{V(t)}\partial_t(\rho\mathbf v)dV+\oint_{\partial V(t)}\rho\mathbf v(\mathbf v_b\!\cdot\mathbf n)dA")
        if changed.get("fixedBoundary"):
            row(steps, id_ + ".boundary", "Fixed boundary is a geometric assumption, not zero acceleration", r"\mathbf v_b=\mathbf0")
        if changed.get("uniformSections"):
            row(steps, id_ + ".sections", "Define momentum-flux averages; uniform components use the local port basis", r"\int_{A_s}\rho\mathbf v(\mathbf v\!\cdot\mathbf n)dA\equiv\varepsilon_s\dot m_s\bar{\mathbf c}_s^M,\quad p|_{A_s}=p_s")
        if changed.get("impermeableWall"):
            row(steps, id_ + ".wall", "Impermeable wall · no missing momentum flux through the remainder", r"(\mathbf v-\mathbf v_b)\!\cdot\mathbf n=0\quad\mathrm{on}\ S_w")
            row(coupling, id_ + ".wall-mass", "Closed material boundary outside the two ports", r"\Phi_{\mathrm{matter},w}=0", "matter")
        if changed.get("form") == "ports":
            row(steps, id_ + ".inventory", "Define fluid linear momentum; include the entire wall traction", r"\mathbf I_f=\int_V\rho\mathbf v\,dV,\quad\partial V=A_1\cup A_2\cup S_w,\quad\mathbf F_{\mathrm{wall}}=\int_{S_w}\boldsymbol\sigma\mathbf n\,dA")
            row(coupling, id_ + ".port-pressure", "Shared absolute static port state · use the phase-resolved donor state", r"p_s\equiv p_s^{\mathrm{thermo}},\quad\rho_s=\rho(\mathrm{state}_s),\quad h_s=h(\mathrm{state}_s)", "thermodynamics")
        if changed.get("constantArea"):
            row(steps, id_ + ".area", "Straight constant-area path", r"A_1=A_2=A,\quad\mathbf n_1=-\mathbf e,\quad\mathbf n_2=\mathbf e")
        if changed.get("referenceDensity"):
            row(steps, id_ + ".density", "Declared reduced-path density approximation; do not replace the package EOS", r"\rho\simeq\rho_{\mathrm{ref}}>0,\quad |\rho-\rho_{\mathrm{ref}}|/\rho_{\mathrm{ref}}\ll1")
        if changed.get("uniformGravity"):
            row(steps, id_ + ".gravity", "Separate uniform conservative gravity from other body forces", r"\mathbf b=\mathbf b_g+\mathbf b_{\mathrm{other}},\quad\mathbf b_g=-g\nabla z,\quad g>0")
        if changed.get("form") == "hydraulic":
            row(coupling, id_ + ".storage", "Full fixed path with constant reference density · retain the mass balance and its compatibility", r"m_f=\rho_{\mathrm{ref}}AL,\quad\frac{dm_f}{dt}=\dot m_1-\dot m_2,\quad\frac{dm_f}{dt}=0\Rightarrow\dot m_1=\dot m_2=\dot m", "matter")
            row(steps, id_ + ".inertance", "Define momentum inventory and collect every non-pressure force", r"I_{f,\parallel}=L\dot m,\quad\dot m\mathbf c_1-\dot m\mathbf c_2=\mathbf0,\quad F_{w,\parallel}+F_{\tau,\mathrm{ports},\parallel}+F_{b,\mathrm{other},\parallel}=A(\Delta p_{\mathrm{drive}}-\Delta p_{\mathrm{loss}}),\quad F_{b_g,\parallel}=-\rho_{\mathrm{ref}}Ag(z_2-z_1)")
            row(steps, id_ + ".geometry-domain", "Admissible reduced-path geometry and material domain", r"L,A,D_h,\rho_{\mathrm{ref}},g>0")
        if changed.get("darcyWeisbach"):
            row(steps, id_ + ".loss", "Signed Darcy–Weisbach/local loss law · nonnegative friction/local-loss coefficients", scalar_latex('loss'))
            row(steps, id_ + ".dissipation", "Dissipative signed resistance in either direction", r"f_D,K\geq0,\quad Q=\dot m/\rho_{\mathrm{ref}},\quad\Delta p_{\mathrm{loss}}Q\geq0")
            row(coupling, id_ + ".energy-conversion", "Internal mechanical-to-thermal conversion · preserve the total-energy balance", r"\dot E_{\mathrm{mech}\to\mathrm{int}}=\Delta p_{\mathrm{loss}}Q\geq0", "energy")
        if changed.get('laminarCircular'):
            row(steps,id_+'.legacy-wall','Legacy shortcut; declare profile, axis and wall assumptions explicitly',r'\Delta p_{\mathrm{loss}}=\text{not yet deduced}')
        if changed.get("angularMomentum"):
            row(steps, id_ + ".moment", "Take moments of Cauchy balance · symmetric stress, no distributed couples", r"\frac{d\mathbf L_f}{dt}+\oint_{\partial V}\rho(\mathbf r\times\mathbf v)(\mathbf v\!\cdot\mathbf n)dA=\oint_{\partial V}\mathbf r\times(\boldsymbol\sigma\mathbf n)dA+\int_V\mathbf r\times\rho\mathbf b\,dV")
            row(steps, id_ + ".axis", "Project onto the shaft axis · retain net body/other torques", r"\frac{dL_f}{dt}=\tau_f+\tau_{\mathrm{other}}+\dot m_1r_1c_{\theta1}-\dot m_2r_2c_{\theta2}")
            row(steps, id_ + ".angular-ports", "Angular-flux representative values; exact products are mass-flux averages", r"r_sc_{\theta s}\equiv\frac{\int_{A_s}\rho r v_\theta|\mathbf v\!\cdot\mathbf n|dA}{\dot m_s}\quad(\dot m_s>0)")
        if changed.get("shaftDynamics"):
            row(steps, id_ + ".inertia", "Positive constant rotor inertia", r"J>0,\quad\frac{dJ}{dt}=0")
            row(steps, id_ + ".rotor", "Rotor angular momentum · constant positive inertia", scalar_latex('rotor'))
            row(coupling, id_ + ".shaft-power", "Equal and opposite shaft work · couple to the first law", r"\dot W_{s\to f}=\tau_f\omega,\quad\frac{d}{dt}\left(\frac12J\omega^2\right)=\omega\tau_{\mathrm{motor}}-\omega\tau_f-\omega\tau_{\mathrm{bearing}}", "energy")
        if changed.get("rotorActuator"):
            row(steps, id_ + ".actuator", "Replace unresolved rotor tractions by an equivalent actuator torque", r"\tau_f=\int_V\mathbf e_{\mathrm{axis}}\!\cdot(\mathbf r\times\mathbf f_{\mathrm{act}})\,dV")
        if changed.get("zeroAngularAccumulation"):
            row(steps, id_ + ".constraint", "Explicit angular constraint · do not assume equal flows or zero other torque", r"\frac{dL_f}{dt}=0,\quad0=\tau_f+\tau_{\mathrm{other}}+\dot m_1r_1c_{\theta1}-\dot m_2r_2c_{\theta2}")
        if euler_compatible(state) and not euler_compatible(previous):
            row(steps, id_ + '.euler-compatibility', 'Combine independent angular, mass-storage and torque constraints', r'\tau_f=\dot m(r_2c_{\theta2}-r_1c_{\theta1})')
            row(coupling, id_ + ".euler", "Euler specific shaft transfer under the recorded passage constraints", r"Y_E=\omega(r_2c_{\theta2}-r_1c_{\theta1}),\quad\dot W_{s\to f}=\dot mY_E,\quad\mathcal H_E=Y_E/g", "energy")
        if changed.get("equalPortMassFlow"):
            row(coupling, id_ + ".mass-constraint", "No net passage mass storage · dynamic material balance retained", r"\frac{dm_f}{dt}=\dot m_1-\dot m_2,\quad\frac{dm_f}{dt}=0\Rightarrow\dot m_1=\dot m_2=\dot m", "matter")
        if changed.get("noOtherTorque"):
            row(steps, id_ + ".other-torque", "Explicitly neglect all non-shaft axial torques", r"\tau_{\mathrm{other}}=0")
        if changed.get("zeroInletSwirl"):
            row(steps, id_ + ".prewhirl", "No tangential inlet velocity in the inertial frame", r"c_{\theta1}=0")
        if changed.get("radialOutlet"):
            row(steps, id_ + ".annulus", "Radial full-annulus exit area; no blockage", r"A_{m2}=2\pi r_2b_2,\quad c_{m2}=Q/(2\pi r_2b_2)")
            row(steps, id_ + ".basis", "Axisymmetric local components; do not pull a radial unit vector out of a full-annulus integral", r"\partial_\theta c_{m2}=\partial_\theta c_{\theta2}=0,\quad\int_0^{2\pi}\mathbf e_r\,d\theta=\mathbf0")
        if changed.get("idealBladeGuidance"):
            row(steps, id_ + ".triangle", "Velocity triangle · relative flow follows the ideal blade", r"u_2=\omega r_2,\quad c_{\theta2}=u_2-c_{m2}\cot\beta_2,\quad0<\beta_2<\pi,\quad r_2,b_2>0")
        if ideal_compatible(state) and not ideal_compatible(previous):
            row(steps, id_ + ".torque", "Substitute geometry into angular compatibility · ideal radial rotating passage", scalar_latex('idealTorque'))
            row(coupling, id_ + ".ideal-head", "Deduced ideal centrifugal characteristic · not an empirical pump curve", scalar_latex('idealTransfer'), "energy")
        if changed.get("losslessPassage"):
            row(coupling, id_ + ".lossless", "Ideal mechanical-head closure · internal-energy change and hydraulic loss neglected", r"u_2-u_1\simeq0,\quad Y_{\mathrm{loss}}=0", "energy")
            row(coupling, id_ + ".mechanical-energy", "Lossless reference-density mechanical-energy reduction", r"Y_E=\frac{p_2-p_1}{\rho_{\mathrm{ref}}}+\frac{c_2^2-c_1^2}{2}+g(z_2-z_1)", "energy")
            row(steps, id_ + ".pressure-rise", "Recover static pressure rise · retain kinetic/elevation corrections", scalar_latex('pressureRise'))
        if changed.get("adiabaticPassage"):
            row(coupling, id_ + ".adiabatic", "Explicitly adiabatic passage", r"\dot Q_{\mathrm{heat}}=0", "energy")
        if changed.get("zeroPassageEnergyAccumulation"):
            row(coupling, id_ + ".passage-energy", "Retain passage total energy; add its zero-accumulation constraint", r"E_f=U_f+K_f+\int_V\rho gz\,dV,\quad\frac{dE_f}{dt}=\dot m_1(h_1+c_1^2/2+gz_1)-\dot m_2(h_2+c_2^2/2+gz_2)+\dot Q_{\mathrm{heat}}+\dot W_{s\to f},\quad\frac{dE_f}{dt}=0", "energy")
        row(steps, id_, operation["title"], equation(state))
        wall,_,storage,_=reduction_graphs(state)
        graphs=([canonical_path_graph()] if state['form']=='hydraulic' else [])+[wall,storage]
        present=set()
        for graph in graphs:
            for item in graph.rows():
                key=item['id'];present.add(key)
                if algebra_values.get(key)==item['latex']:continue
                algebra_values[key]=item['latex'];published=id_+'.algebra.'+key
                metadata={**item['derivation'],'inputIds':[algebra_ids.get(k,k) for k in item['derivation']['inputIds']]}
                algebra_ids[key]=published
                # Each family owns its own rows. Historical side-family details
                # remain available through the operation audit on its final row.
                if item['family']=='momentum':steps.append({**item,'id':published,'derivation':metadata})
        for key in set(algebra_values)-present:algebra_values.pop(key);algebra_ids.pop(key,None)
    state = states[-1]
    effective_couplings = {
        'continuity': state['massContinuity'], 'wall-mass': state['impermeableWall'],
        'port-pressure': state['form'] in ('ports', 'hydraulic'), 'storage': state['form'] == 'hydraulic',
        'energy-conversion': state['darcyWeisbach'], 'shaft-power': state['shaftDynamics'],
        'euler': euler_compatible(state), 'mass-constraint': state['equalPortMassFlow'],
        'ideal-head': ideal_compatible(state), 'lossless': state['losslessPassage'], 'mechanical-energy': state['losslessPassage'],
        'adiabatic': state['adiabaticPassage'], 'passage-energy': state['zeroPassageEnergyAccumulation'],
    }
    unique_couplings = {}
    for item in coupling:
        suffix = item['id'].rsplit('.', 1)[-1]
        if effective_couplings[suffix]:
            unique_couplings[suffix] = item
    coupling = list(unique_couplings.values())
    final_steps = [{"id": "final.linear", "title": "Retained linear momentum balance", "latex": equation(state), "family": "momentum"}]
    if state['zeroLocalAccumulation']:
        row(final_steps, 'final.local-constraint', 'Local momentum constraint; other physical inventories remain dynamic', r'\partial_t(\rho\mathbf v)=\mathbf0')
        row(final_steps, 'final.local-compatibility', 'Spatial compatibility required by fixed local momentum', component_latex(state, compatibility=True))
    if state['zeroTotalAccumulation']:
        row(final_steps, 'final.total-constraint', 'Fixed integrated fluid momentum; dynamic law retained above', r'\frac{d\mathbf I_f}{dt}=\mathbf0')
        if state['form'] == 'hydraulic':
            import sympy as sp
            _, relations, names = reduced_relations()
            row(final_steps, 'final.hydraulic-compatibility', 'Zero rate requires force compatibility, not equality of arbitrary prescribed data', sp.latex(sp.Eq(0, relations['inertance'][1], evaluate=False), symbol_names=names))
    if state['angularMomentum']:
        row(final_steps, 'final.angular', 'Retained angular momentum balance', r'\frac{dL_f}{dt}=\tau_f+\tau_{\mathrm{other}}+\dot m_1r_1c_{\theta1}-\dot m_2r_2c_{\theta2}')
    if state['zeroAngularAccumulation']:
        row(final_steps, 'final.angular-constraint', 'Fixed passage angular momentum', r'\frac{dL_f}{dt}=0')
    if state['shaftDynamics']:
        row(final_steps, 'final.rotor', 'Retained rotor inertia', scalar_latex('rotor'))
    if ideal_compatible(state):
        row(final_steps, 'final.torque', 'Derived ideal radial torque under the current assumptions', scalar_latex('idealTorque'))
    if state['losslessPassage']:
        row(final_steps, 'final.pressure-rise', 'Static pressure rise under the current assumptions', scalar_latex('pressureRise'))
    if state['form']=='hydraulic':
        row(final_steps, 'final.pressure-difference', 'Recover signed static pressure difference from the retained momentum balance', scalar_latex('pressureDrop'))
        if all(state[k] for k in WALL_FLAGS):
            row(final_steps, 'final.wall-loss', 'Wall loss deduced from the recorded profile and boundary operations', scalar_latex('laminarLoss'))
    wall,wall_result,storage,storage_result=reduction_graphs(state)
    for item in storage.rows():
        if item['family']=='matter':coupling.append(item)
        elif item['id'] in ('storage.force','storage.pressure','storage.port-pressure'):final_steps.append(item)
    requirements = []
    def requirement(code, message):
        requirements.append({"code": code, "message": message})
    if state['zeroLocalAccumulation'] or state['zeroTotalAccumulation']:
        requirement('momentum_constraint', 'Zero momentum accumulation constrains this momentum inventory only. Other inventories and shaft rotation remain dynamic unless separately constrained. A compatible dependent force/pressure/flow and constraint-aware compiler are required; no prescribed datum is adjusted automatically.')
    if any(state[key] for key in FIELD_FLAGS):
        requirement('cartesian_scope', 'Cartesian field constraints are local: invariance removes coordinate dependence, not velocity components or transverse balances. Curvilinear reductions and automatic boundary consequences of integration are not connected.')
    if state["form"] in ("ports", "hydraulic") and (state["inletStreamId"] is None or state["outletStreamId"] is None):
        requirement("unbound_ports", "Bind both momentum ports to existing material streams before coupled execution. No prescribed flow is silently converted into a solved flow.")
    if state["newtonian"] and not state['negligibleViscousStress']:
        requirement("transport_properties", "Declare viscosity data or a validated transport-property provider. Equilibrium/UNIFAC activity coefficients do not determine viscosity.")
    if state["referenceDensity"] or state["divergenceFree"]:
        requirement("density_validity", "Check the recorded density/continuity approximation against the shared thermodynamic closure. A fully filled rigid incompressible volume does not determine its absolute pressure.")
    if state["form"] in ("ports", "hydraulic"):
        requirement("port_state", "Use shared absolute static port pressures and donor enthalpy/composition. Bulk-to-port hydrostatics and losses need explicit relations; never add dynamic pressure to the EOS pressure.")
    if state["form"] == "hydraulic":
        requirement("drive_and_loss_closures", "Declare the pressure-drive and wall-loss laws, including an explicit zero when appropriate. No missing drive or resistance is assigned zero automatically.")
    if state["darcyWeisbach"]:
        requirement("energy_accounting", "Keep viscous dissipation as internal mechanical-to-thermal conversion in the energy budget. It is not an additional external heat input; count pressure flow work once through enthalpy or its equivalent explicit term.")
    if state['laminarCircular']:
        requirement('legacy_wall_shortcut','The old laminar shortcut is readable but not executable. Remove it and record circular section, developed profile, auxiliary profile acceleration, axis regularity and wall boundary assumptions explicitly.')
    if all(state[k] for k in WALL_FLAGS):
        requirement('laminar_wall_validity', 'Check Reynolds number and a slowly varying developed wall profile. This lumped quasi-steady resistance plus retained inertia is not the exact transient radial Navier–Stokes solution; entrance effects, turbulence and frequency-dependent wall friction require other closures.')
    if state["angularMomentum"]:
        requirement("rotating_regime", "Declare geometry, torque/loss closures and admissible flow/rotation domains. The ideal blade law is not validated for cavitation, reverse flow, multiphase passages or real slip.")
    if model is not None:
        validate_model_journal(model)
        volume = next(v for v in model["volumenes"] if v["id"] == owner)
        if state["shaftDynamics"] and not volume["balances"]["energia"]:
            requirement("energy_inactive", "Enable energy to account for shaft work; momentum alone cannot supply a thermally coupled machine.")
        if state["shaftDynamics"] and (volume["supuestos"]["energia"] or {}).get("sinCinetica"):
            requirement("kinetic_energy_review", "Energy currently neglects kinetic storage. Review its assumptions before coupling fluid/rotor mechanical energy; no energy assumption is rewritten automatically.")
        if state["impermeableWall"] and not volume["supuestos"]["materia"]["restoImpermeable"]:
            requirement("material_boundary_review", "Matter retains exchange outside declared ports. Reconcile that boundary with the recorded impermeable-wall reduction.")
        if state["adiabaticPassage"] and any(owner in (item["desde"], item["hasta"]) for item in model["intercambios"]):
            requirement("heat_boundary_review", "Heat exchanges are declared on this volume. Reconcile them explicitly with the adiabatic-passage assumption; they are not silently disabled.")
    variables = [{"id": id_, "symbol": symbol, "name": name, "unit": unit, "role": role} for id_, symbol, name, unit, role in (
        ("fluidMomentum", r"\mathbf I_f", "Fluid linear momentum", "kg*m/s", "inventory"),
        ("fluidAngularMomentum", "L_f", "Fluid angular momentum", "kg*m2/s", "inventory"),
        ("massFlow", r"\dot m", "Shared stream mass flow", "kg/s", "coupled_unknown"),
        ("pressure1", "p_1", "Absolute static inlet pressure", "Pa", "shared_state"),
        ("pressure2", "p_2", "Absolute static outlet pressure", "Pa", "shared_state"),
        ("density", r"\rho", "Density from the common medium or declared approximation", "kg/m3", "shared_property"),
        ("viscosity", r"\mu", "Shear viscosity", "Pa*s", "constitutive"),
        ("secondViscosity", r"\lambda", "Second-viscosity coefficient", "Pa*s", "constitutive"),
        ("length", "L", "Flow-path length", "m", "geometry"), ("area", "A", "Flow-path area", "m2", "geometry"),
        ("speed", r"\omega", "Shaft angular velocity", "1/s", "inventory_coordinate"),
        ("rotorInertia", "J", "Rotor inertia", "kg*m2", "geometry"),
        ("fluidTorque", r"\tau_f", "Shaft torque delivered to fluid", "N*m", "coupled_unknown"),
        ("specificTransfer", "Y_E", "Specific shaft transfer", "J/kg", "derived"),
        ("hydraulicHead", r"\mathcal H_E", "Hydraulic head; distinct from thermodynamic H", "m", "derived"))]
    variables.extend({"id": id_, "symbol": symbol, "name": name, "unit": unit, "role": role} for id_, symbol, name, unit, role in (
        ("velocity", r"\mathbf v", "Continuum velocity", "m/s", "field"), ("stress", r"\boldsymbol\sigma", "Cauchy stress", "Pa", "constitutive"),
        ("bodyForce", r"\mathbf b", "Body force per unit mass", "m/s2", "input"), ("portVelocity1", "c_1", "Inlet speed", "m/s", "shared_state"),
        ("portVelocity2", "c_2", "Outlet speed", "m/s", "shared_state"), ("swirl1", r"c_{\theta1}", "Inlet tangential velocity", "m/s", "shared_state"),
        ("swirl2", r"c_{\theta2}", "Outlet tangential velocity", "m/s", "shared_state"), ("radialVelocity2", "c_{m2}", "Radial exit velocity", "m/s", "derived"),
        ("radius2", "r_2", "Outlet radius", "m", "geometry"), ("width2", "b_2", "Outlet annulus width", "m", "geometry"),
        ("bladeAngle", r"\beta_2", "Outlet blade angle from the tangent", "rad", "geometry"), ("volumeFlow", "Q", "Volume flow rate; distinct from heat rate", "m3/s", "derived"),
        ("gravity", "g", "Gravity magnitude", "m/s2", "input"), ("motorTorque", r"\tau_{\mathrm{motor}}", "Motor torque", "N*m", "input"),
        ("bearingTorque", r"\tau_{\mathrm{bearing}}", "Bearing-loss torque", "N*m", "constitutive"), ("friction", "f_D", "Darcy friction factor", "1", "constitutive")))
    available = []
    for kind, (title, delta) in CHOICES.items():
        try:
            next_state = normalize({**state, **delta})
        except JournalError:
            continue
        # Representation moves forward only; Undo is the explicit branch edit.
        forms = ("local", "integral", "ports", "hydraulic")
        if next_state == state or "form" in delta and forms.index(delta["form"]) != forms.index(state["form"]) + 1:
            continue
        available.append({"kind": kind, "title": title})
    forms = []
    order = ('local', 'integral', 'ports', 'hydraulic')
    for form, label, action in [('local', 'Local', ''), ('integral', 'Integral', 'integrate'), ('ports', 'Ports', 'ports'), ('hydraulic', 'Hydraulic projection', 'hydraulic')]:
        reason = ''
        try:
            if order.index(form) != order.index(state['form']) + 1:
                raise JournalError('Use Undo to revisit an earlier representation; intermediate deductions cannot be skipped.')
            normalize({**state, 'form': form})
        except JournalError as error:
            reason = str(error)
        forms.append({'id': form, 'label': label, 'action': action, 'selected': form == state['form'], 'canSelect': not reason, 'reason': reason})
    return {"format": "rage.momentum-development", "version": 1, "volumeId": owner, "origin": entry["origin"], "formulation": state,
            "steps": steps, "finalSteps": final_steps, "couplingSteps": coupling, "variables": variables, "requirements": requirements, "available": available,
            "bindings": {"inletStreamId": state["inletStreamId"], "outletStreamId": state["outletStreamId"]},
            "controls": controls(state), "forms": forms,
            "notes": ["The declared reduced isothermal hydraulic network has a common compiler; Solve validates its exact scope. Pump, general DAE and spatial execution remain unsupported." if model is not None and model.get('motores',{}).get('hydraulicNetwork') else "Model deduction only. No momentum, pump, general DAE or spatial execution is connected by this journal.",
                      "All dynamic conservation laws remain present. Zero passage angular accumulation is an additional explicit constraint, not global stationarity. No numerical inertia or compressibility is invented.",
                      "Newtonian stress is a constitutive assumption, not a consequence of conservation. Turbulence averaging, real blade slip and empirical loss/efficiency curves require additional declared closures.",
                      "Matter, shaft-work and Euler-transfer equations are published to their own physical families. The momentum panel does not duplicate their balances."]}


def ensure_executable(model):
    validate_model_journal(model)
    if model.get('motores',{}).get('hydraulicNetwork') is not None:
        from core.compilador.hydraulics import validate_admission
        validate_admission(model)
        return
    if any(volume["balances"]["momento"] for volume in model["volumenes"]):
        raise JournalError("Momentum requires a coupled dynamic compiler that is not connected yet. Its conservation laws cannot be ignored or replaced by prescribed flow/pressure.")
