"""First-law deductions, independent of thermodynamic package selection."""
from core.modelo.operation_journal import JournalError, keys, read_operations, replay, evidence, edit

FORMAT = "rage.energy-derivation"
THERMODYNAMIC_KEYS = ("monofasico", "sinCambioFase", "densidadConstante", "modelo")


def fundamental():
    return {"forma": "local", **{key: False for key in (
        "trabajoTotalHeredado", "separarPresion", "entalpia", "sinCinetica", "sinTrabajoViscoso",
        "sinFuerzasVolumen", "sinFuenteVolumetrica", "sinConduccionLocal", "adiabatico", "estacionario",
        "sinAcumulacionTotal", "uniforme", "presionUniforme", "presionPrescrita")}}


def changes(value):
    keys(value, [], fundamental())
    if not value:
        raise JournalError("An energy operation needs declared changes.")
    for name, item in value.items():
        if name == "forma":
            if item not in ("local", "integrada", "integral", "total"):
                raise JournalError("Unknown first-law representation.")
        elif type(item) is not bool:
            raise JournalError("Energy assumptions must be booleans.")


def normalize(value):
    state = fundamental()
    relevant = {key: item for key, item in value.items() if key not in THERMODYNAMIC_KEYS}
    if relevant:
        changes(relevant)
    state.update(relevant)
    if state["entalpia"] and not state["separarPresion"]:
        raise JournalError("Separate pressure stress before collecting flow work into enthalpy.")
    if state["trabajoTotalHeredado"]:
        raise JournalError("Legacy total-work shorthand has no explicit deduction. Declare stress and boundary-work terms instead.")
    if state["presionPrescrita"] and not state["presionUniforme"]:
        raise JournalError("Declare spatially uniform pressure before prescribing its time history.")
    return state


def read_journal(value):
    read_operations(value, FORMAT, changes)
    for entry in value["volumes"].values():
        replay(entry, fundamental, normalize)
    return value


def validate_model_journal(model):
    value = model.get("motores", {}).get("energyDerivation")
    if value is None:
        return []
    read_journal(value)
    volumes = {volume["id"]: volume for volume in model["volumenes"]}
    result = []
    for owner, entry in value["volumes"].items():
        volume = volumes.get(owner)
        if volume is None or volume["supuestos"]["energia"] is None:
            raise JournalError(f"Energy journal refers to an unknown energy formulation: {owner}.")
        if replay(entry, fundamental, normalize)[-1] != normalize(volume["supuestos"]["energia"]):
            raise JournalError(f"Volume {owner}: energy operations do not produce the formulation being compiled.")
        result.append(evidence(owner, entry, [f"energia.{owner}"] if volume["balances"]["energia"] else []))
    return result


CHOICES = {
    "integrate": ("Integrate the local first law and apply Gauss", {"forma": "integrada"}),
    "reynolds": ("Apply Reynolds transport theorem", {"forma": "integral"}),
    "total": ("Define total energy and oriented stream contributions", {"forma": "total"}),
    "pressure_stress": ("Separate pressure and viscous stress", {"separarPresion": True}),
    "enthalpy": ("Collect flow work into enthalpy", {"entalpia": True}),
    "no_kinetic": ("Negligible kinetic energy", {"sinCinetica": True}),
    "no_viscous_work": ("Negligible viscous work", {"sinTrabajoViscoso": True}),
    "no_body_work": ("No body-force work", {"sinFuerzasVolumen": True}),
    "no_volume_source": ("No volumetric energy source", {"sinFuenteVolumetrica": True}),
    "uniform_state": ("Uniform temperature and specific internal energy", {"uniforme": True}),
    "uniform_pressure": ("Spatially uniform pressure", {"presionUniforme": True}),
    "prescribed_pressure": ("Prescribed pressure", {"presionPrescrita": True}),
    "adiabatic": ("Adiabatic boundary", {"adiabatico": True}),
    "no_local_heat_flux": ("Zero local nonconvective energy flux", {"sinConduccionLocal": True}),
    "no_accumulation": ("Zero total energy accumulation · algebraic constraint", {"sinAcumulacionTotal": True}),
}


def edit_journal(value, owner, action):
    return edit(value, owner, action, FORMAT, changes, normalize, fundamental, CHOICES)


def read_context(value):
    keys(value, ["fixed", "remainderClosed", "streamIds", "pressurePrescribed"])
    if any(type(value[key]) is not bool for key in ("fixed", "remainderClosed", "pressurePrescribed")):
        raise JournalError("Energy boundary context flags must be booleans.")
    ids = value["streamIds"]
    if not isinstance(ids, list) or any(not isinstance(item, str) or not item.strip() for item in ids) or len(set(ids)) != len(ids):
        raise JournalError("Unique stream IDs are required.")
    return value


def equation(state, context):
    variable = "u" if state["sinCinetica"] else "e"
    energy = "U" if state["sinCinetica"] else "E"
    extra_kinetic = "" if state["sinCinetica"] else "+e_c"
    transported = "h" + extra_kinetic if state["entalpia"] else variable
    stationary = state["estacionario"]
    pressure = state["separarPresion"]
    if state["forma"] == "total":
        lhs = "0" if state["sinAcumulacionTotal"] or stationary and context["fixed"] else rf"\frac{{d{energy}}}{{dt}}"
        terms = []
        if context["streamIds"]:
            terms.append(r"\sum_s B_{vs}\dot m_s(\bar " + ("h" if state["entalpia"] else "u") + r"_s" + ("" if state["sinCinetica"] else r"+\bar e_{c,s}") + ")")
            if pressure and not state["entalpia"]:
                terms.append(r"+\sum_s B_{vs}\dot m_s\overline{(p/\rho)}_s")
        if not context["remainderClosed"]:
            terms.append(r"-\Phi_{E,\mathrm{rest}}")
            if pressure and not state["entalpia"]:
                terms.append(r"-\Phi_{p,\mathrm{rest}}")
        if not (state["adiabatico"] or state["sinConduccionLocal"]):
            terms.append(r"+\dot Q")
        if pressure:
            if not context["fixed"]:
                terms.append(r"-\dot W_b")
            if not state["sinTrabajoViscoso"]:
                terms.append(r"+\dot W_\tau")
        else:
            terms.append(r"+\dot W_\sigma")
        if not state["sinFuerzasVolumen"]:
            terms.append(r"+\dot W_{\mathbf b}")
        if not state["sinFuenteVolumetrica"]:
            terms.append("+R")
        return lhs + "=" + ("".join(terms).lstrip("+") or "0")
    local = state["forma"] == "local"
    integrated = state["forma"] == "integrada"
    velocity = r"\mathbf v" if local or integrated or context["fixed"] else r"\mathbf v-\mathbf v_b"
    convection = rf"\rho({transported})"
    lhs = "0" if stationary and (local or integrated or context["fixed"]) else (
        rf"\frac{{\partial(\rho {variable})}}{{\partial t}}" if local else
        rf"\int_{{V(t)}}\frac{{\partial(\rho {variable})}}{{\partial t}}\,dV" if integrated else rf"\frac{{d{energy}}}{{dt}}")
    if not local and not integrated and state["sinAcumulacionTotal"]:
        lhs = "0"
    def surface(flux):
        return rf"\nabla\cdot({flux})" if local else rf"\oint_{{\partial V(t)}}({flux})\cdot\mathbf n\,dA"
    rhs = "-" + surface(convection + "(" + velocity + ")")
    if not state["sinConduccionLocal"] and (local or not state["adiabatico"]):
        rhs += "-" + surface(r"\mathbf q")
    if pressure:
        if not state["entalpia"]:
            rhs += "-" + surface(r"p\mathbf v")
        elif not local and not integrated and not context["fixed"]:
            rhs += "-" + surface(r"p\mathbf v_b")
        if not state["sinTrabajoViscoso"]:
            rhs += "+" + surface(r"\boldsymbol\tau\cdot\mathbf v")
    else:
        rhs += "+" + surface(r"\boldsymbol\sigma\cdot\mathbf v")
    if not state["sinFuerzasVolumen"]:
        rhs += r"+\rho\mathbf b\cdot\mathbf v" if local else r"+\int_{V(t)}\rho\mathbf b\cdot\mathbf v\,dV"
    if not state["sinFuenteVolumetrica"]:
        rhs += "+r_v" if local else r"+\int_{V(t)}r_v\,dV"
    return lhs + "=" + rhs


RELATIONS = {
    "separarPresion": r"\boldsymbol\sigma=-p\mathbf I+\boldsymbol\tau",
    "entalpia": r"h=u+p/\rho,\quad\rho>0",
    "sinCinetica": r"e_c=\mathbf v\cdot\mathbf v/2\simeq0,\quad E\simeq U",
    "sinTrabajoViscoso": r"\dot W_\tau=0", "sinFuerzasVolumen": r"\dot W_{\mathbf b}=0",
    "sinFuenteVolumetrica": r"r_v=0\quad\Longrightarrow\quad R=0",
    "uniforme": r"T(\mathbf x,t)=T(t),\quad u(\mathbf x,t)=\bar u(t),\quad U=m\bar u",
    "presionUniforme": r"p(\mathbf x,t)=P(t)", "presionPrescrita": r"P(t)=P_{\mathrm{ext}}(t)",
    "adiabatico": r"\dot Q=-\oint_{\partial V}\mathbf q\cdot\mathbf n\,dA=0",
    "sinConduccionLocal": r"\mathbf q=\mathbf0", "sinAcumulacionTotal": r"dE/dt=0",
}


def describe_volume(journal, owner, context):
    read_journal(journal)
    read_context(context)
    if not isinstance(owner, str) or owner not in journal["volumes"]:
        raise JournalError("This volume has no recorded energy journal.")
    entry = journal["volumes"][owner]
    states = replay(entry, fundamental, normalize)
    steps = [{"id": "fundamental", "title": "Local first law · total energy conservation", "latex": equation(states[0], context)}]
    steps.append({"id": "energy-definitions", "title": "Specific energy and control-volume inventory",
                  "latex": r"e=u+\mathbf v\cdot\mathbf v/2,\quad E=\int_{V(t)}\rho e\,dV,\quad U=\int_{V(t)}\rho u\,dV"})
    for operation, previous, state in zip(entry["operations"], states, states[1:]):
        if state["forma"] != "local" and previous["forma"] == "local":
            steps.append({"id": operation["id"] + ".gauss", "title": "Integrate the first law · Gauss theorem", "latex": r"\int_{V(t)}\nabla\cdot\mathbf F\,dV=\oint_{\partial V(t)}\mathbf F\cdot\mathbf n\,dA"})
        if state["forma"] in ("integral", "total") and previous["forma"] in ("local", "integrada"):
            steps.append({"id": operation["id"] + ".reynolds", "title": "Reynolds theorem · account for moving control boundaries", "latex": r"\frac{dE}{dt}=\int_{V(t)}\frac{\partial(\rho e)}{\partial t}\,dV+\oint_{\partial V(t)}\rho e\mathbf v_b\cdot\mathbf n\,dA,\quad E=\int_{V(t)}\rho e\,dV"})
        for key, relation in RELATIONS.items():
            if state[key] and not previous[key]:
                steps.append({"id": operation["id"] + "." + key, "title": "Declared identity or physical assumption", "latex": relation})
        if state["forma"] == "total" and previous["forma"] != "total":
            steps.append({"id": operation["id"] + ".definitions", "title": "Define heat, boundary work and source rates", "latex": r"\dot Q=-\oint_{\partial V}\mathbf q\cdot\mathbf n\,dA,\quad\dot W_b=\oint_{\partial V}p\mathbf v_b\cdot\mathbf n\,dA,\quad R=\int_V r_v\,dV"})
            steps.append({"id": operation["id"] + ".streams", "title": "Partition the boundary and collect oriented transport",
                          "latex": r"\partial V=\left(\bigcup_s A_s\right)\cup S_{\mathrm{rest}},\quad B_{vs}=\delta_{v,\mathrm{head}(s)}-\delta_{v,\mathrm{tail}(s)},\quad-\oint_{\partial V}\rho h(\mathbf v-\mathbf v_b)\cdot\mathbf n\,dA=\sum_s B_{vs}\dot m_s\bar h_s-\Phi_{h,\mathrm{rest}}" if state["entalpia"] else r"-\oint_{\partial V}\rho e(\mathbf v-\mathbf v_b)\cdot\mathbf n\,dA=\sum_s B_{vs}\dot m_s\bar e_s-\Phi_{E,\mathrm{rest}}"})
        steps.append({"id": operation["id"], "title": operation["title"], "latex": equation(state, context)})
    return {"format": "rage.energy-development", "version": 1, "volumeId": owner, "origin": entry["origin"],
            "formulation": states[-1], "steps": steps,
            "notes": ["All total-balance terms have dimensions of power. Local terms have dimensions of power per volume.",
                      "Positive heat/work enters the volume; positive outward boundary work is subtracted.",
                      "Stream composition and enthalpy follow the actual donor when a stream reverses.",
                      "The development uses mass-specific energy; the equivalent molar form satisfies mass-flow times specific enthalpy = molar-flow times molar enthalpy. The shared unit and donor services perform the conversion.",
                      "The thermodynamic closure supplies u, h, density and phase state; it is not replaced by an energy assumption.",
                      "For uniform prescribed pressure, H=U+PV gives dH/dt=dU/dt+P dV/dt+V dP/dt; the compiler retains V dP/dt.",
                      "An adiabatic boundary does not require zero heat flux inside the volume. Spatial and algebraic execution require their own supported methods."]}
