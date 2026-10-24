"""Replayable material assumptions shared by authoring and compilation.

The journal contains operations, never a second set of executable equations.
Topology and thermodynamic state assumptions remain in the common model.
"""

import copy
import hashlib
import json


class MaterialDerivationError(ValueError):
    """Malformed journal or disagreement with the physical formulation."""


def fundamental_formulation():
    return {"campo": {"sinReaccion": False, "sinDifusion": False,
                      "sinConveccion": False, "estacionario": False, "difusion": "flujo"},
            "coordenadas": "cartesianas", "expandida": False, "vista": "campo",
            "uniforme": False, "fija": False, "sinAcumulacion": False,
            "invariantes": [False, False, False], "generacionUniforme": False,
            "consumoUniforme": False, "restoImpermeable": False, "cantidadVolumen": False,
            "densidadMediaConstante": False, "densidadComunPuertos": False, "expandirProducto": False}


def _keys(value, required, optional=()):
    if not isinstance(value, dict) or set(value) - set(required) - set(optional) or set(required) - set(value):
        raise MaterialDerivationError("Unknown or missing material derivation fields.")


def _changes(value):
    _keys(value, [], fundamental_formulation())
    if not value:
        raise MaterialDerivationError("A material operation needs at least one declared change.")
    for key, item in value.items():
        if key == "campo":
            _keys(item, [], ["sinReaccion", "sinGeneracion", "sinConsumo", "sinDifusion",
                            "sinConveccion", "estacionario", "difusion", "generacionUniforme", "consumoUniforme"])
            for name, field in item.items():
                if name == "difusion":
                    if field not in ("flujo", "fick", "laplaciano"):
                        raise MaterialDerivationError("Unknown diffusion law.")
                elif type(field) is not bool:
                    raise MaterialDerivationError("Material flags must be booleans.")
        elif key == "invariantes":
            if not isinstance(item, list) or len(item) != 3 or any(type(x) is not bool for x in item):
                raise MaterialDerivationError("Three boolean coordinate invariances are required.")
        elif key in ("vista", "coordenadas"):
            options = ("campo", "integral", "cantidad") if key == "vista" else ("cartesianas", "cilindricas", "esfericas")
            if item not in options:
                raise MaterialDerivationError("Unknown material representation or coordinates.")
        elif type(item) is not bool:
            raise MaterialDerivationError("Material flags must be booleans.")


def normalize_formulation(value):
    """Complete optional display flags, without inventing physical assumptions."""
    state = fundamental_formulation()
    changes = {key: item for key, item in value.items() if key not in ("componentes", "fronteras", "reglasEstado")}
    if changes:
        _changes(changes)
    state.update(copy.deepcopy(changes))
    state["campo"] = {**fundamental_formulation()["campo"], **state["campo"]}
    # Explicit false and absent optional flags have the same meaning.
    for key in ("sinGeneracion", "sinConsumo", "generacionUniforme", "consumoUniforme"):
        state["campo"].setdefault(key, False)
    return state


def read_journal(value):
    _keys(value, ["format", "version", "volumes"])
    if value["format"] != "rage.material-derivation" or type(value["version"]) is not int or value["version"] != 1:
        raise MaterialDerivationError("Unsupported material derivation format/version.")
    if not isinstance(value["volumes"], dict) or len(value["volumes"]) > 160:
        raise MaterialDerivationError("Material volumes must be an object with at most 160 entries.")
    for owner, journal in value["volumes"].items():
        if not isinstance(owner, str) or not owner.strip():
            raise MaterialDerivationError("A volume ID is required.")
        _keys(journal, ["origin", "operations"])
        if journal["origin"] not in ("recorded", "reviewed_rebuild"):
            raise MaterialDerivationError("Unknown journal origin.")
        if not isinstance(journal["operations"], list) or len(journal["operations"]) > 400:
            raise MaterialDerivationError("At most 400 material operations are supported per volume.")
        seen = set()
        for operation in journal["operations"]:
            _keys(operation, ["id", "title", "changes"])
            if any(not isinstance(operation[key], str) or not operation[key].strip() for key in ("id", "title")):
                raise MaterialDerivationError("Operation IDs and titles must be nonempty text.")
            if operation["id"] in seen:
                raise MaterialDerivationError("Repeated material operation ID.")
            seen.add(operation["id"])
            _changes(operation["changes"])
    return value


def replay_volume(journal):
    state = normalize_formulation(fundamental_formulation())
    states = [copy.deepcopy(state)]
    for operation in journal["operations"]:
        changes = operation["changes"]
        # Preserve the published legacy shallow-merge operation semantics.
        state = normalize_formulation({**state, **changes})
        states.append(copy.deepcopy(state))
    return states


def validate_model_journal(model):
    journal = model.get("motores", {}).get("materialDerivation")
    if journal is None:
        return []
    read_journal(journal)
    volumes = {v["id"]: v for v in model["volumenes"]}
    summaries = []
    for owner, entry in journal["volumes"].items():
        if owner not in volumes:
            raise MaterialDerivationError(f"Material journal refers to unknown volume {owner}.")
        actual = replay_volume(entry)[-1]
        if actual != normalize_formulation(volumes[owner]["supuestos"]["materia"]):
            raise MaterialDerivationError(f"Volume {owner}: the recorded assumptions do not produce the formulation being compiled.")
        signature = hashlib.sha256(json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        summaries.append({"volumeId": owner, "origin": entry["origin"], "operationIds": [x["id"] for x in entry["operations"]],
                          "signature": signature, "relationIds": [f"materia.{owner}.{i}" for i in volumes[owner]["componenteIds"]]})
    return summaries


def _equation(state):
    """Coordinate-independent conservation; no expansion of metric operators."""
    field = state["campo"]
    sources = []
    for role, sign, local, total in (("generacion", "+", r"\gamma_i", "G_i"), ("consumo", "-", r"\chi_i", "C_i")):
        if field.get("sinReaccion") or field.get("sinGeneracion" if role == "generacion" else "sinConsumo"):
            continue
        term = local if state["vista"] == "campo" else total
        sources.append(sign + term)
    convection = "" if field["sinConveccion"] else r"\rho_i\mathbf v"
    diffusion = "" if field["sinDifusion"] else r"\mathbf j_i"
    flux = "+".join(x for x in (convection, diffusion) if x)
    if state["vista"] == "campo":
        lhs = "0" if field["estacionario"] else r"\frac{\partial\rho_i}{\partial t}"
        transport = r"-\nabla\!\cdot(" + flux + ")" if flux else ""
    else:
        relative = convection + ("" if state["fija"] else r"-\rho_i\mathbf v_b")
        if diffusion:
            relative += ("+" if relative else "") + diffusion
        lhs = "0" if state["sinAcumulacion"] or state["fija"] and field["estacionario"] else r"\frac{dm_i}{dt}"
        transport = (r"-\oint_{\partial V(t)}(" + relative + r")\cdot\mathbf n\,dA") if relative else ""
        if state["vista"] == "integral" and lhs != "0":
            lhs = r"\frac{d}{dt}\int_{V(t)}\rho_i\,dV"
        if state["vista"] == "cantidad" and relative:
            transport = r"\sum_s B_{vs}\dot m_{i,s}"
            if not state["restoImpermeable"]:
                transport += r"-\Phi_{i,\mathrm{rest}}"
    rhs = transport + "".join(sources)
    return lhs + "=" + (rhs.lstrip("+") or "0")


def describe_volume(journal, owner):
    read_journal(journal)
    if not isinstance(owner, str) or owner not in journal["volumes"]:
        raise MaterialDerivationError("This volume has no recorded material journal.")
    entry = journal["volumes"][owner]
    states = replay_volume(entry)
    steps = [{"id": "fundamental", "title": "Local conservation of each component", "latex": _equation(states[0])}]
    for operation, previous, state in zip(entry["operations"], states, states[1:]):
        if state["cantidadVolumen"]:
            raise MaterialDerivationError("The network development renderer does not yet expand volumetric substitutions; use the existing material derivation view.")
        if state["vista"] != "campo" and previous["vista"] == "campo":
            field = previous["campo"]
            convective = "" if field["sinConveccion"] else r"\rho_i\mathbf v"
            diffusive = "" if field["sinDifusion"] else r"\mathbf j_i"
            flux = "+".join(x for x in (convective, diffusive) if x) or "0"
            sources = ""
            if not (field.get("sinReaccion") or field.get("sinGeneracion")):
                sources += r"+\int_{V(t)}\gamma_i\,dV"
            if not (field.get("sinReaccion") or field.get("sinConsumo")):
                sources += r"-\int_{V(t)}\chi_i\,dV"
            local_accumulation = "0" if field["estacionario"] else r"\int_{V(t)}\frac{\partial\rho_i}{\partial t}\,dV"
            steps.extend([
                {"id": operation["id"] + ".integrate", "title": "Integrate every local conservation term over the control volume",
                 "latex": local_accumulation + r"=-\int_{V(t)}\nabla\!\cdot(" + flux + r")\,dV" + sources},
                {"id": operation["id"] + ".gauss", "title": "Gauss theorem · convert divergence to outward surface flux",
                 "latex": r"\int_{V(t)}\nabla\!\cdot(" + flux + r")\,dV=\oint_{\partial V(t)}(" + flux + r")\cdot\mathbf n\,dA"},
                {"id": operation["id"] + ".reynolds", "title": "Reynolds theorem · account for control-boundary motion",
                 "latex": r"\frac{d}{dt}\int_{V(t)}\rho_i\,dV=\int_{V(t)}\frac{\partial\rho_i}{\partial t}\,dV+\oint_{\partial V(t)}\rho_i\mathbf v_b\cdot\mathbf n\,dA"},
                {"id": operation["id"] + ".relative", "title": "Collect the transport relative to the moving boundary",
                 "latex": r"\rho_i\mathbf v+\mathbf j_i-\rho_i\mathbf v_b=\rho_i(\mathbf v-\mathbf v_b)+\mathbf j_i"},
            ])
        if state["vista"] == "cantidad" and previous["vista"] != "cantidad":
            steps.extend([
                {"id": operation["id"] + ".partition", "title": "Partition the boundary into nonoverlapping ports and their remainder",
                 "latex": r"\partial V(t)=\left(\mathop{\dot\bigcup}_s A_s\right)\mathbin{\dot\cup}S_{\mathrm{rest}}"},
                {"id": operation["id"] + ".ports", "title": "Define oriented stream flows and the remaining surface flux",
                 "latex": r"B_{vs}\dot m_{i,s}=-\int_{A_s}[\rho_i(\mathbf v-\mathbf v_b)+\mathbf j_i]\cdot\mathbf n\,dA,\quad\Phi_{i,\mathrm{rest}}=\int_{S_{\mathrm{rest}}}[\rho_i(\mathbf v-\mathbf v_b)+\mathbf j_i]\cdot\mathbf n\,dA"},
            ])
        relations = []
        changes = operation["changes"]
        if changes.get("campo", {}).get("sinReaccion") and not previous["campo"]["sinReaccion"]:
            relations.append(r"\gamma_i=0,\quad\chi_i=0\quad\Longrightarrow\quad G_i=C_i=0")
        if changes.get("campo", {}).get("sinDifusion") and not previous["campo"]["sinDifusion"]:
            relations.append(r"\mathbf j_i=\mathbf0")
        if changes.get("campo", {}).get("sinConveccion") and not previous["campo"]["sinConveccion"]:
            relations.append(r"\mathbf v=\mathbf0")
        if changes.get("fija") and not previous["fija"]:
            relations.append(r"\mathbf v_b=\mathbf0,\quad\frac{dV}{dt}=0")
        if changes.get("sinAcumulacion") and not previous["sinAcumulacion"]:
            relations.append(r"\frac{dm_i}{dt}=0\quad\text{(algebraic constraint)}")
        if changes.get("restoImpermeable") and not previous["restoImpermeable"]:
            relations.append(r"[\rho_i(\mathbf v-\mathbf v_b)+\mathbf j_i]\cdot\mathbf n=0\quad\text{on }S_{\mathrm{rest}}")
        if relations:
            steps.append({"id": operation["id"] + ".assumption", "title": "Declared assumption and affected term", "latex": r",\qquad ".join(relations)})
        steps.append({"id": operation["id"], "title": operation["title"], "latex": _equation(state)})
        if state["vista"] != "campo" and previous["vista"] != state["vista"]:
            steps.append({"id": operation["id"] + ".definitions", "title": "Definitions · inventories and integrated source rates",
                          "latex": r"m_i=\int_{V(t)}\rho_i\,dV,\quad G_i=\int_{V(t)}\gamma_i\,dV,\quad C_i=\int_{V(t)}\chi_i\,dV"})
            # Keep the effective equation last, including after definition rows.
            steps.append({"id": operation["id"] + ".balance", "title": "Conservation after substitution", "latex": _equation(state)})
    return {"format": "rage.material-development", "version": 1, "volumeId": owner,
            "origin": entry["origin"], "formulation": states[-1], "steps": steps,
            "notes": ["m_i is the integral of component mass density over the control volume.",
                      "G_i and C_i are integrated gross rates. Streams partition the boundary; Phi covers only its complement.",
                      "Positive stream flow follows its declared orientation; B is +1 at the destination and -1 at the origin.",
                      "These equations use mass. A molar execution uses m_i = M_i n_i with declared molar masses.",
                      "Spatial operators remain continuous until Transform; constitutive and thermodynamic relations remain separate."]}


def edit_journal(journal, owner, action):
    """Author one explicit assumption/identity; do not infer history from flags."""
    read_journal(journal)
    result = copy.deepcopy(journal)
    if not isinstance(owner, str) or not owner.strip():
        raise MaterialDerivationError("A volume ID is required.")
    _keys(action, ["kind"])
    kind = action["kind"]
    if kind == "start":
        if owner in result["volumes"]:
            raise MaterialDerivationError("A journal already exists. Undo its operations to return to the fundamental law.")
        result["volumes"][owner] = {"origin": "reviewed_rebuild", "operations": []}
    else:
        if owner not in result["volumes"]:
            raise MaterialDerivationError("Start from the fundamental law before applying an assumption.")
        entry = result["volumes"][owner]
        if kind == "undo":
            if entry["operations"]:
                entry["operations"].pop()
        else:
            state = replay_volume(entry)[-1]
            choices = {
                "integrate": ("Integrate over the control volume · Gauss and Reynolds", {"vista": "integral"}),
                "total": ("Define component inventories and partition the boundary into streams", {"vista": "cantidad"}),
                "no_reaction": ("No chemical generation or consumption", {"campo": {**state["campo"], "sinReaccion": True}}),
                "fixed_boundary": ("Fixed control-volume boundary", {"fija": True}),
                "impermeable_remainder": ("Impermeable boundary outside the declared streams", {"restoImpermeable": True}),
                "no_diffusion": ("Negligible diffusive transport", {"campo": {**state["campo"], "sinDifusion": True}}),
                "no_convection": ("Negligible convective transport", {"campo": {**state["campo"], "sinConveccion": True}}),
                "no_accumulation": ("Zero total accumulation · algebraic balance", {"sinAcumulacion": True}),
            }
            if not isinstance(kind, str) or kind not in choices:
                raise MaterialDerivationError("Unknown material deduction operation.")
            title, changes = choices[kind]
            if normalize_formulation({**state, **changes}) == state:
                raise MaterialDerivationError("This operation is already effective.")
            entry["operations"].append({"id": f"step-{len(entry['operations']) + 1}", "title": title, "changes": changes})
    read_journal(result)
    return result
