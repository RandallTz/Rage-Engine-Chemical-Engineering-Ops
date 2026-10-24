"""Physical inventory policy, independent of transformations and time integrators.

The optional versioned journal adds constraints; it never replaces conservation
laws. A structural match is not a rank proof or a consistent-initialization test.
"""
import copy

FORMAT = "rage.dynamic-definition"
KINDS = {"total_mass", "component_amount", "energy"}


def _exact(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or not set(required) <= set(value):
        raise ValueError("Invalid dynamic-definition fields: expected " + ", ".join(required))


def inventory_key(owner, inventory):
    return f"{owner}:{inventory['kind']}" + (f":{inventory['componentId']}" if inventory['kind'] == "component_amount" else f":{inventory['coordinate']}" if inventory['kind'] == "energy" else "")


def dependent_options(model, volume, kind, component=None):
    """Admitted symbolic bindings, not invented actuators or numerical data."""
    owner = volume["id"]
    options = []
    if kind == "energy":
        for exchange in model["intercambios"]:
            if owner in (exchange["desde"], exchange["hasta"]) and exchange["desde"] != exchange["hasta"] and exchange["ley"]["tipo"] == "impuesto":
                options.append({"kind": "heat_flow", "id": exchange["id"], "dataId": exchange["ley"]["potenciaId"]})
    else:
        for stream in model["corrientes"]:
            if owner not in (stream["desde"], stream["hasta"]) or stream["desde"] == stream["hasta"]:
                continue
            matter = stream["materia"]
            if matter["modo"] in ("total_desde_donante", "total_y_composicion") and (component is None or component in stream["componenteIds"]):
                # A flow's composition may still make its actual coefficient zero.
                options.append({"kind": "stream_total", "id": stream["id"], "dataId": matter["caudalId"]})
            if matter["modo"] == "por_componente":
                for cid, data_id in matter["caudalIds"].items():
                    if component is None or int(cid) == component:
                        options.append({"kind": "component_flow", "id": stream["id"], "componentId": int(cid), "dataId": data_id})
    return options


def _check_flow_unit(model, option):
    from core.unidades import compatibles, ErrorUnidad
    if option["kind"] == "heat_flow":
        expected = "W"
    else:
        stream = next(item for item in model["corrientes"] if item["id"] == option["id"])
        expected = {"masica": "kg/s", "molar": "mol/s", "volumetrica": "m3/s"}.get(stream["materia"]["base"])
        if expected is None:
            raise ValueError("Unknown flow basis.")
    declared = model["datos"][option["dataId"]]["declaracion"]["unidad"]
    try:
        compatible = compatibles(declared, expected)
    except ErrorUnidad as error:
        raise ValueError(str(error)) from error
    if not compatible:
        raise ValueError(f"Dependent flow {option['dataId']}: unit {declared} is incompatible with {expected}.")


def read_definition(value, model):
    _exact(value, ("format", "version", "operations"))
    if value["format"] != FORMAT or type(value["version"]) is not int or value["version"] != 1:
        raise ValueError("Unsupported dynamic-definition format or version.")
    operations = value["operations"]
    if not isinstance(operations, list) or len(operations) > 2000:
        raise ValueError("Expected at most 2000 inventory operations.")
    volumes = {v["id"]: v for v in model["volumenes"]}
    ids, effective = set(), {}
    for op in operations:
        _exact(op, ("id", "volumeId", "inventory", "mode", "reason"), ("dependent",))
        if not isinstance(op["id"], str) or not op["id"].strip() or len(op["id"]) > 160 or op["id"] in ids:
            raise ValueError("Inventory operations require unique nonempty IDs.")
        ids.add(op["id"])
        if not isinstance(op["volumeId"], str) or not op["volumeId"].strip():
            raise ValueError("Inventory operation requires a control-volume identity.")
        inventory = op["inventory"]
        _exact(inventory, ("kind",), ("componentId", "coordinate"))
        if not isinstance(inventory["kind"], str) or inventory["kind"] not in KINDS:
            raise ValueError("Unknown inventory kind.")
        if inventory["kind"] == "component_amount":
            if type(inventory.get("componentId")) is not int or inventory["componentId"] < 1:
                raise ValueError("Component inventory requires a positive integer component ID.")
        elif "componentId" in inventory:
            raise ValueError("Only component inventories accept componentId.")
        if inventory["kind"] == "energy":
            if inventory.get("coordinate") not in ("U", "H", "E"):
                raise ValueError("An energy inventory must identify U, H or E explicitly.")
        elif "coordinate" in inventory:
            raise ValueError("Only energy inventories accept an energy coordinate.")
        if op["mode"] not in ("dynamic", "fixed") or not isinstance(op["reason"], str) or not op["reason"].strip() or len(op["reason"]) > 2000:
            raise ValueError("An inventory operation needs a mode and an explicit reason.")
        if "dependent" in op:
            binding = op["dependent"]
            _exact(binding, ("kind", "id"), ("componentId",))
            if op["mode"] != "fixed" or not isinstance(binding["id"], str) or binding["kind"] not in ("heat_flow", "stream_total", "component_flow"):
                raise ValueError("Only a permanent fixed-inventory constraint has a dependent binding.")
            if binding["kind"] == "component_flow":
                if type(binding.get("componentId")) is not int:
                    raise ValueError("A dependent component flow requires an integer component ID.")
            elif "componentId" in binding:
                raise ValueError("Only a component flow accepts componentId.")
        effective[inventory_key(op["volumeId"], inventory)] = op
    # Historical operations survive a topology edit once their constraint has
    # explicitly been removed. Only the current physical bindings are active.
    for op in effective.values():
        if op["mode"] == "dynamic":
            continue
        if op["volumeId"] not in volumes:
            raise ValueError("Inventory operation references a missing control volume.")
        volume, inventory = volumes[op["volumeId"]], op["inventory"]
        if inventory["kind"] == "component_amount" and inventory["componentId"] not in volume["componenteIds"]:
            raise ValueError("Component inventory must belong to its control volume.")
        if "dependent" in op:
            binding = op["dependent"]
            candidates = dependent_options(model, volume, inventory["kind"], inventory.get("componentId"))
            option = next((option for option in candidates if {k: v for k, v in option.items() if k != "dataId"} == binding), None)
            if option is None:
                raise ValueError("Dependent variable is not an incident flow compatible with this inventory.")
            _check_flow_unit(model, option)
    return value


def effective_operations(model):
    definition = model["motores"].get("dynamicDefinition")
    if definition is None:
        return {}
    read_definition(definition, model)
    return {inventory_key(op["volumeId"], op["inventory"]): op for op in definition["operations"]}


def legacy_flags(volume):
    matter = volume["supuestos"]["materia"]
    energy = volume["supuestos"]["energia"] or {}
    return [name for name, active in (
        ("matter.local", volume["balances"]["materia"] and matter["campo"].get("estacionario")),
        ("matter.total", volume["balances"]["materia"] and matter.get("sinAcumulacion")),
        ("energy.local", volume["balances"]["energia"] and energy.get("estacionario")),
        ("energy.total", volume["balances"]["energia"] and energy.get("sinAcumulacionTotal")),
    ) if active]


def tex(value):
    # IDs are opaque data, never executable LaTeX.
    escapes = {"\\": r"\backslash ", "_": r"\_", "{": r"\{", "}": r"\}", "%": r"\%", "#": r"\#", "&": r"\&", "$": r"\$", "^": r"\^{}", "~": r"\~{}"}
    return r"\mathrm{" + "".join(escapes.get(c, c) for c in str(value)) + "}"


def describe_definition(model):
    """Typed physical formulation without numerical initialization or integration."""
    operations = effective_operations(model)
    diagnostics, inventories, variables, closures, domains = [], [], [], [], []
    used = {}
    for volume in model["volumenes"]:
        owner, sub = volume["id"], tex(volume["id"])
        flags = legacy_flags(volume)
        if flags:
            diagnostics.append({"code": "legacy_accumulation", "volumeId": owner, "message": "Legacy zero-accumulation assumptions need explicit review: " + ", ".join(flags) + ". Restore dynamic accumulation in the original journal, then declare each intended fixed inventory here. History is preserved; no automatic reinterpretation occurs."})
        molar = volume["inicial"].get("cantidades", {}).get("base") == "molar"
        specs = []
        if volume["balances"]["materia"]:
            specs.append(({"kind": "total_mass"}, "Total mass", f"m_{{{sub}}}", "kg", "derived_quantity"))
            specs.extend(({"kind": "component_amount", "componentId": cid}, f"Component {cid} amount", rf"{'n' if molar else 'm'}_{{{sub},{cid}}}", "mol" if molar else "kg", "inventory_state") for cid in volume["componenteIds"])
        if volume["balances"]["energia"]:
            energy = volume["supuestos"]["energia"] or {}
            symbol = "H" if energy.get("entalpia") and volume["frontera"]["tipo"] == "presion_prescrita" else "U" if energy.get("sinCinetica") else "E"
            specs.append(({"kind": "energy", "coordinate": symbol}, f"{symbol} energy inventory", f"{symbol}_{{{sub}}}", "J", "inventory_state"))
        for inventory, name, symbol, unit, role in specs:
            key = inventory_key(owner, inventory)
            operation = operations.get(key)
            fixed = bool(operation and operation["mode"] == "fixed")
            options = dependent_options(model, volume, inventory["kind"], inventory.get("componentId"))
            balance_id = "balance:" + key
            rate_label = symbol[0] if inventory["kind"] == "energy" else "n" if molar and inventory["kind"] == "component_amount" else "m"
            rhs = rf"\Phi_{{{sub},{rate_label}" + (f",{inventory['componentId']}" if "componentId" in inventory else "") + "}"
            rows = [{"id": balance_id, "title": "Retained dynamic conservation law", "latex": rf"\frac{{d{symbol}}}{{dt}}={rhs}"}]
            # Reuse the physical generators. The preserved baseline is displayed
            # alongside legacy diagnostics; no saved assumption is rewritten.
            if inventory["kind"] == "total_mass":
                from core.balances.material_derivation import _equation
                state = copy.deepcopy(volume["supuestos"]["materia"])
                state["campo"]["estacionario"] = False
                state["sinAcumulacion"] = False
                rows.append({"id": "physical-matter:" + owner, "title": "Physical species conservation · mass basis; retain temporal accumulation", "latex": _equation(state)})
                if molar:
                    rows.append({"id": "basis:" + owner, "title": "Convert each species using its constant molar mass", "latex": r"m_i=M_i n_i,\quad\frac{dm_i}{dt}=M_i\frac{dn_i}{dt}"})
            elif inventory["kind"] == "energy" and volume["supuestos"]["energia"]:
                from core.balances.energy_derivation import equation
                state = copy.deepcopy(volume["supuestos"]["energia"])
                state["estacionario"] = state["sinAcumulacionTotal"] = False
                rows.append({"id": "physical-energy:" + owner, "title": "Physical first law · retain temporal accumulation", "latex": equation(state, {"fixed": volume["frontera"]["tipo"] == "rigida", "remainderClosed": volume["supuestos"]["materia"]["restoImpermeable"], "streamIds": [s["id"] for s in model["corrientes"] if owner in (s["desde"], s["hasta"])]})})
                if symbol == "H":
                    rows.append({"id": "energy-coordinate:" + owner, "title": "Enthalpy coordinate · pressure work remains in the balance", "latex": r"H=U+PV,\quad\dot H=\dot U+P\dot V+V\dot P"})
            if fixed:
                if inventory["kind"] != "energy" and volume["supuestos"]["materia"]["vista"] != "cantidad" or inventory["kind"] == "energy" and (volume["supuestos"]["energia"] or {}).get("forma") != "total":
                    diagnostics.append({"code": "inventory_reduction_required", "volumeId": owner, "message": f"{name}: first record the total-inventory reduction through the existing deduction tools. Spatial and local constraints need their own formulation."})
                rows.extend([{"id": "constraint:" + key, "title": "Permanent inventory constraint", "latex": rf"{symbol}(t)={symbol}(t_0)\quad\Longrightarrow\quad\frac{{d{symbol}}}{{dt}}=0"},
                             {"id": "compatibility:" + key, "title": "Compatibility with the dynamic balance", "latex": rhs + "=0"}])
                if flags:
                    diagnostics.append({"code": "legacy_conflict", "volumeId": owner, "message": f"{name}: remove the legacy accumulation assumption before activating this constraint."})
                binding = operation.get("dependent")
                if binding is None:
                    diagnostics.append({"code": "missing_dependent", "volumeId": owner, "message": f"{name}: choose a dependent flow. Independently prescribed flows cannot be changed silently."})
                else:
                    option = next(o for o in options if {k: v for k, v in o.items() if k != "dataId"} == binding)
                    data_id = option["dataId"]
                    if data_id in used:
                        diagnostics.append({"code": "dependent_reused", "volumeId": owner, "message": f"{data_id} is assigned to both {used[data_id]} and {key}. Independent constraints need independent unknowns or a demonstrated reduction."})
                    used[data_id] = key
                    variables.append({"id": data_id, "volumeId": owner, "role": "dependent_unknown", "unit": model["datos"][data_id]["declaracion"]["unidad"], "source": "constraint:" + key})
            variables.append({"id": key, "volumeId": owner, "role": role, "unit": unit, "source": balance_id})
            inventories.append({"id": key, "volumeId": owner, "inventory": inventory, "name": name, "unit": unit, "mode": "fixed" if fixed else "dynamic", "steps": rows, "options": options,
                                "operationId": operation["id"] if operation else None, "dependent": operation.get("dependent") if operation else None})
        if volume["balances"]["materia"]:
            domains.append({"id": "fractions:" + owner, "volumeId": owner, "title": "Fractions are derived from inventories on one declared basis", "latex": rf"a_i\geq0,\quad a_{{\Sigma}}=\sum_i a_i>0,\quad {'x' if molar else 'w'}_i=\frac{{a_i}}{{a_{{\Sigma}}}}\in[0,1],\quad\sum_i {'x' if molar else 'w'}_i=1", "note": "No clipping. At zero total inventory, composition and the mixture closure are undefined; an explicit empty-volume model is required."})
            mass = "+".join(rf"M_{{{cid}}}n_{{{sub},{cid}}}" if molar else rf"m_{{{sub},{cid}}}" for cid in volume["componenteIds"]) or "0"
            domains.append({"id": "total:" + owner, "volumeId": owner, "title": "Total mass is a derived quantity, not an additional independent state", "latex": rf"m_{{{sub}}}={mass}", "note": "Constant total mass does not imply constant component amounts, volume or energy. Chemical sources require mass-conserving stoichiometry; molar totals need not be conserved."})
        closure = volume["termodinamica"]
        closures.append({"volumeId": owner, "kind": closure["tipo"], "packageId": closure.get("paqueteId"), "balanceIds": [item["id"] for item in inventories if item["volumeId"] == owner], "note": "The same constitutive closure supplies properties to matter and energy. Package domain and phase policy remain authoritative; no phase set or temperature is inferred from a stationary derivative."})
        if closure["tipo"] == "equilibrio":
            unknowns = [("temperature", "K"), ("pressure", "Pa") if volume["frontera"]["tipo"] == "rigida" else ("volume", "m3"), ("phase_amounts", "mol"), ("phase_compositions", "1")]
            for name, unit in unknowns:
                variables.append({"id": f"closure:{owner}:{name}", "volumeId": owner, "role": "closure_unknown", "unit": unit, "source": closure["paqueteId"]})
        else:
            variables.append({"id": "closure:" + owner, "volumeId": owner, "role": "closure_unknown", "unit": "closure-dependent", "source": closure.get("supuesto", "")})
        owner_fixed = [item for item in inventories if item["volumeId"] == owner and item["mode"] == "fixed"]
        if any(item["inventory"]["kind"] == "total_mass" for item in owner_fixed) and all(any(item["inventory"] == {"kind": "component_amount", "componentId": cid} for item in owner_fixed) for cid in volume["componenteIds"]):
            diagnostics.append({"code": "redundant_inventory", "volumeId": owner, "message": "Fixed total mass is redundant with fixing every component amount. Remove the duplicate constraint or provide a demonstrated independent reduction."})
    for key, op in operations.items():
        if not any(item["id"] == key for item in inventories) and op["mode"] == "fixed":
            diagnostics.append({"code": "inactive_inventory", "volumeId": op["volumeId"], "message": "A fixed-inventory constraint targets an inactive balance or a different energy coordinate. Restore its physical definition or explicitly remove/review the constraint; U, H and E are distinct inventories."})
    for data_id, data in model["datos"].items():
        if data_id not in used:
            variables.append({"id": data_id, "volumeId": data["origen"]["propietarioId"], "role": "external_input" if data["funcion"] == "frontera" else "specified_data", "unit": data["declaracion"]["unidad"], "source": data["funcion"]})
    return {"format": "rage.dynamic-formulation", "version": 1, "modelId": model["id"], "inventories": inventories, "variables": variables, "closures": closures, "domains": domains, "diagnostics": diagnostics,
            "scope": "Model formulation only. Phi denotes the full net rate of the recorded physical balance, including sources and undeclared boundary exchange when retained. A fixed constraint adds Phi=0; no state or conservation law is deleted. Dependent bindings replace prescribed-data roles for this formulation; stored values are preserved but are not specifications for those unknowns. Structural bindings do not prove rank, feasibility, nonzero flow coefficients or consistent initial conditions. Constrained time integration is not connected yet. An initially stationary operating point is an initialization choice in Solve, never a permanent Model constraint."}


def ensure_executable(model):
    """All existing compiler paths must fail closed for the new constraints."""
    active = [op for op in effective_operations(model).values() if op["mode"] == "fixed"]
    if active:
        raise ValueError("Permanent inventory constraints are defined in Model, but constrained dynamic execution is not connected. The solver cannot ignore them or substitute a steady algebraic model.")


def edit_definition(model, action):
    """Append or undo explicit authoring; never alter physical derivation journals."""
    definition = copy.deepcopy(model["motores"].get("dynamicDefinition", {"format": FORMAT, "version": 1, "operations": []}))
    _exact(action, ("kind",), ("operation",))
    if action["kind"] == "undo" and "operation" not in action:
        definition["operations"] = definition["operations"][:-1]
    elif action["kind"] == "append" and "operation" in action:
        op = action["operation"]
        _exact(op, ("id", "volumeId", "inventory", "mode", "reason"), ("dependent",))
        _exact(op["inventory"], ("kind",), ("componentId", "coordinate"))
        if not isinstance(op, dict) or not any(volume["id"] == op.get("volumeId") and (op.get("inventory", {}).get("kind") != "component_amount" or op["inventory"].get("componentId") in volume["componenteIds"]) for volume in model["volumenes"]):
            raise ValueError("New inventory operations require an existing owner and component.")
        definition["operations"].append(action["operation"])
    else:
        raise ValueError("Expected append or undo inventory operation.")
    read_definition(definition, model)
    return definition
