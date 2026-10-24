"""Inspectable compilation metadata; never invent an assembled numerical matrix."""

from core.modelo import leer_modelo_comun, relaciones

from .compilador import NoSoportado, compilar
from .explicito import SistemaExplicito, es_explicito
from .transformed import TransformedSystem, _signature, selected_execution


def compilation_report(model):
    if model.get('motores', {}).get('derivedExecution') is not None:
        from .derived import DerivedSystem
        return DerivedSystem(model).report
    from core.modelo.equation_workbench import attach_report
    if model.get('motores',{}).get('hydraulicNetwork') is not None:
        from .compilador import _check_inventory_execution
        from .hydraulics import HydraulicSystem
        _check_inventory_execution(model)
        return HydraulicSystem(model).report()
    from .presentation import solution_strategy
    report = _compilation_report(model)
    return attach_report({**report, "strategy": solution_strategy(report, model)},model)


def _compilation_report(model):
    model = leer_modelo_comun(model)
    from .compilador import _check_inventory_execution
    _check_inventory_execution(model)
    from core.balances.material_derivation import validate_model_journal
    material = validate_model_journal(model)
    from core.balances.energy_derivation import validate_model_journal as validate_energy
    energy = validate_energy(model)
    from core.termodinamica.derivation import validate_model_journal as validate_thermodynamics
    thermodynamics = validate_thermodynamics(model)
    provenance = {**({"materialDerivation": material} if material else {}), **({"energyDerivation": energy} if energy else {}), **({"thermodynamicDerivation": thermodynamics} if thermodynamics else {})}
    if model["estudio"] is None or model["estudio"]["tipo"] != "temporal":
        raise NoSoportado("Compilation inspection requires a declared temporal study.")
    if selected_execution(model) is not None:
        return {**TransformedSystem(model).report, **provenance}
    if es_explicito(model):
        generated = model["matematico"] is None
        if model["matematico"] is None:
            from core.balances import NoGenerable, generar
            try:
                model = generar(model)
            except NoGenerable as error:
                raise NoSoportado(str(error)) from error
        system = SistemaExplicito(model)
        # These IDs are emitted as diagnostics by our balance generator, not inferred
        # from user-authored symbol names in arbitrary explicit models.
        auxiliary = {field for field in system.campos if generated and field.startswith("aux_")}
        variables = [{"id": field, "sourceId": field, "role": "differential", "unit": system.unidades[field],
                      "physicalUnit": system.unidades[field], "scaleSI": 1,
                      "absoluteTolerance": float(system.atol[index])} for index, field in enumerate(system.campos) if field not in auxiliary]
        equations = [equation for equation in model["matematico"]["ecuaciones"]
                     if not any(side.get("tipo") == "derivada" and side["expresion"].get("id") in auxiliary
                                for side in (equation["izquierda"], equation["derecha"]))]
        return {"format": "rage.compilation", "version": 1, "formulation": "physical",
                "sourceModelId": model["matematico"]["id"], "sourceRevision": model["matematico"]["revision"],
                "signature": _signature(model), "method": system.metodo, "closureStrategy": "declared_assumption",
                "variables": variables, "equations": equations,
                "domains": model["matematico"]["dominios"], "conditions": model["matematico"]["condiciones"],
                "direct": [], "inverse": [], "eliminatedVariables": [], "auxiliaryStates": len(auxiliary),
                "auxiliaryPurpose": "integrated balance diagnostics emitted by the balance generator" if generated else "none",
                "time": {"id": system.tiempo, "sourceId": system.tiempo, "scaleSI": 1,
                         "finalTime": system.tf, "physicalFinalTime": system.tf},
                "matrix": "BDF estimates its Jacobian numerically; RK45 does not assemble a global solve matrix.",
                **provenance}
    if model['estudio']['metodoSolicitado'] not in (None, 'rk45'):
        raise NoSoportado('The nested-equilibrium compiler currently supports RK45 only. Select RK45 or use a supported explicit formulation.')
    system = compilar(model)
    variables = []
    for volume in system.vols:
        variables.extend({"id": f"{volume.id}.n.{component}", "sourceId": f"{volume.id}.n.{component}",
                          "role": "differential", "unit": "mol", "physicalUnit": "mol", "scaleSI": 1,
                          "absoluteTolerance": model["estudio"]["atol"]["cantidad"]} for component in volume.comp)
        field = f"{volume.id}.{'U' if volume.rigida else 'H'}"
        variables.append({"id": field, "sourceId": field, "role": "differential", "unit": "J", "physicalUnit": "J",
                          "scaleSI": 1, "absoluteTolerance": model["estudio"]["atol"].get("energia", 1e-6)})
    final_time = system.dato(model["estudio"]["tiempoId"])(0.0)
    from .presentation import compiled_balance_equations
    return {"format": "rage.compilation", "version": 1, "formulation": "physical", "sourceModelId": model["id"],
            "sourceRevision": None, "signature": _signature(model), "method": "RK45", "closureStrategy": "nested_equilibrium",
            "variables": variables, "equations": [], "domains": [], "conditions": [],
            "systemEquations": compiled_balance_equations(model),
            "relations": relaciones(model), "direct": [], "inverse": [], "eliminatedVariables": [],
            "auxiliaryStates": system.tam - system.n_estado,
            "time": {"id": "t", "sourceId": "t", "scaleSI": 1, "finalTime": final_time, "physicalFinalTime": final_time},
            "matrix": "UV/PH closures are solved inside each RHS evaluation. The outer RK45 method has no global solve matrix.",
            "limits": "Thermodynamic assemblies do not yet expose explicit equation trees. Relations describe their structural provenance.",
            **provenance}
