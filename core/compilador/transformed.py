"""Compile a selected scaling operation through the common numerical interface.

The scientific core regenerates and certifies the formulation from its choices.
No client-supplied equations or cached certificate are trusted for execution.
Version 1 admits positive, constant multiplicative maps on explicit ODEs.
"""

import hashlib
import json
import math

import numpy as np

from core.adimensionalizacion import algebra as algebra
from core.adimensionalizacion.dimensional import analizar_modelo
from core.adimensionalizacion.estudio import Contexto, SistemaNumerico
from core.adimensionalizacion.formulacion import formular
from core.adimensionalizacion.nucleo import _objetivos_forma
from core.adimensionalizacion.numerico import NoEvaluable, evaluar_ast
from core.adimensionalizacion.transformacion import Preparado, Rechazo
from core.modelo import leer_modelo_comun
from core.resultados import conjunto, eje, evento, serie
from core.solvers import integrar
from core.unidades import unidad_SI
from core import unidades as units

from .compilador import NoSoportado
from .explicito import SistemaExplicito, _dim_de_simbolo, _valor_SI


def selected_execution(model):
    return model.get("motores", {}).get("adimensionalizacion", {}).get("execution")


def _signature(model):
    from core.modelo.equation_workbench import SOURCE_REVISION
    payload = {key: value for key, value in model.items() if key not in ("nombre", "procedencia")}
    return hashlib.sha256(json.dumps([SOURCE_REVISION,payload], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class TransformedSystem:
    def __init__(self, model):
        self.model = leer_modelo_comun(model)
        if any(v["termodinamica"]["tipo"] != "supuesto" for v in model["volumenes"]):
            raise NoSoportado("Scaled thermodynamic closures are not connected to execution yet.")
        self.physical = SistemaExplicito(model)
        config = model["motores"]["adimensionalizacion"]
        execution = config["execution"]
        form = next(f for f in config["formas"] if f["id"] == config["activaId"])
        if form["modeloRevision"] != model["matematico"]["revision"]:
            raise NoSoportado("The selected transformation belongs to another physical model revision.")
        analysis = analizar_modelo(model["matematico"])
        if analysis["estado"] != "compatible":
            raise NoSoportado("The physical equations must be dimensionally compatible before execution.")
        try:
            self.prepared = Preparado(model["matematico"], form, analysis, form.get("transformaciones", []))
            objectives = _objetivos_forma(self.prepared, form, prefijo="base:")
            for term_id in execution["objectives"]:
                if term_id not in self.prepared.terminos:
                    raise NoSoportado(f"The selected normalization term no longer exists: {term_id}.")
                objectives.append({"id": f"auto:{term_id}", "terminoId": term_id, "modo": "magnitud"})
            self.formulation = formular(self.prepared, objectives, form["presentacion"])
        except (Rechazo, algebra.NoSoportado, algebra.ErrorAlgebraico) as error:
            raise NoSoportado(f"The selected formulation cannot be compiled: {error}") from error
        body = self.formulation
        if body["equivalencia"]["estado"] != "demostrada":
            raise NoSoportado("Execution requires the core's inverse equivalence certificate.")
        if any(item["estado"] in ("incompatible", "pendiente") for item in body["objetivos"]):
            raise NoSoportado("The selected normalization has unresolved or incompatible objectives.")
        if any(item["familia"] != "multiplicativa" for item in body["transformaciones"]):
            raise NoSoportado("Execution version 1 supports constant multiplicative maps; affine and nonlinear maps remain inspectable in Transform.")
        values = []
        for symbol in model["matematico"]["simbolos"]:
            if symbol["rol"] in ("parametro", "constante"):
                key = "matematico." + symbol["id"]
                if key not in model["datos"]:
                    continue  # The context reports missing values only when they are used.
                value = _valor_SI(model["datos"][key], key, _dim_de_simbolo(symbol))
                values.append({"simboloId": symbol["id"], "valor": value})
        if set(execution["freeScales"]) != set(body["libres"]):
            raise NoSoportado("Provide exactly the free scales of the selected formulation: " + ", ".join(body["libres"]))
        symbols = {symbol["id"]: symbol for symbol in body["simbolos"]}
        for symbol_id, quantity in execution["freeScales"].items():
            scale = symbols[symbol_id]
            try:
                unit = units.interpretar(quantity["unit"])
            except units.ErrorUnidad as error:
                raise NoSoportado(f"Invalid scale unit for {symbol_id}: {error}") from error
            if unit["desplazamiento"] != 0:
                raise NoSoportado(f"Scale {symbol_id} needs a linear difference unit, not an offset temperature unit.")
            value = _valor_SI({"declaracion": {"texto": str(quantity["value"]), "unidad": quantity["unit"]}},
                              f"execution.freeScales.{symbol_id}", _dim_de_simbolo(scale))
            if not (value > 0 and math.isfinite(value)):
                raise NoSoportado(f"Scale {symbol_id} must be positive and finite.")
            values.append({"simboloId": symbol_id, "valor": value})
        self.context = Contexto(self.prepared, body, {"valores": values})
        errors = [item for item in self.context.diagnosticos if item["severidad"] == "error"]
        if errors or self.context.faltan_valores:
            reasons = [item["mensaje"] for item in errors] + self.context.faltan_valores
            raise NoSoportado("Cannot evaluate the selected scales: " + "; ".join(reasons))
        self.numeric = SistemaNumerico(self.context)
        if self.numeric.problemas or self.numeric.faltan or not self.numeric.evolucion:
            raise NoSoportado("The transformed formulation is not an executable ODE: " + "; ".join(self.numeric.problemas))
        maps = {item["variableId"]: item for item in body["transformaciones"]}
        required = [self.physical.tiempo, *self.physical.campos]
        if set(maps) != set(required):
            raise NoSoportado("Execution requires a time map and one map for each physical state.")
        self.scales = {}
        for original_id in required:
            mapping = maps[original_id]
            derivative = algebra.derivar_ast(mapping["directa"], mapping["nuevoId"], self.context.ctx)
            try:
                scale = float(evaluar_ast(derivative, self.context.ctx, self.context.valores))
            except (NoEvaluable, ValueError, ZeroDivisionError, OverflowError) as error:
                raise NoSoportado(f"Scale {original_id} is not a constant finite value.") from error
            if not (scale > 0 and math.isfinite(scale)):
                raise NoSoportado(f"Scale {original_id} must be positive and finite.")
            self.scales[original_id] = scale
        self.time_scale = self.scales[self.physical.tiempo]
        self.state_scales = np.array([self.scales[field] for field in self.physical.campos])
        self.fields = [maps[field]["nuevoId"] for field in self.physical.campos]
        self.time = maps[self.physical.tiempo]["nuevoId"]
        self.order = [self.fields.index(item["campo"]) for item in self.numeric.evolucion]
        if len(self.order) != len(self.fields) or set(self.order) != set(range(len(self.fields))):
            raise NoSoportado("Each retained state must have exactly one differential equation.")
        self.size = len(self.fields)
        self.tf = self.physical.tf / self.time_scale
        time_domain = self.numeric.dominios.get(self.time)
        if time_domain and (time_domain["desde"] != 0 or time_domain["hasta"] is None
                            or self.tf > time_domain["hasta"] * (1 + 1e-12)):
            raise NoSoportado("Execution requires a declared time domain starting at zero and covering the study horizon.")
        self.atol = self.physical.atol / self.state_scales
        if not (math.isfinite(self.tf) and self.tf > 0 and np.all(np.isfinite(self.atol)) and np.all(self.atol > 0)):
            raise NoSoportado("The chosen scales produce an unrepresentable time horizon or tolerance.")
        for item in self.numeric.evolucion:
            mass = self.numeric.masa(item)
            if not (math.isfinite(mass) and mass != 0):
                raise NoSoportado(f"Equation {item['ecuacion']} has a zero or nonfinite derivative coefficient.")
        self.report = {
            "format": "rage.compilation", "version": 1, "formulation": "scaled",
            "sourceModelId": model["matematico"]["id"], "sourceRevision": model["matematico"]["revision"],
            "signature": _signature(model), "method": self.physical.metodo, "closureStrategy": "declared_assumption",
            "selection": {"formId": config["activaId"], "execution": execution},
            "variables": [{"id": field, "sourceId": source, "role": "differential", "unit": "1",
                           "physicalUnit": self.physical.unidades[source], "scaleSI": self.scales[source],
                           "absoluteTolerance": float(self.atol[index])}
                          for index, (field, source) in enumerate(zip(self.fields, self.physical.campos))],
            "time": {"id": self.time, "sourceId": self.physical.tiempo, "scaleSI": self.time_scale,
                     "finalTime": self.tf, "physicalFinalTime": self.physical.tf},
            "equations": [item["igualdad"] for item in body["ecuaciones"]],
            "parameters": [{"id": name, "value": float(value), "unit": unidad_SI(self.prepared.dims_t[name])}
                           for name, value in sorted(self.context.valores.items())],
            "groups": [{"id": group["id"], "definition": group["definicion"], "value": self.context.numero(group["definicion"])}
                       for group in body["grupos"]],
            "domains": body["dominios"], "conditions": body["condiciones"],
            "direct": body["directa"], "inverse": body["inversa"], "eliminatedVariables": [],
            "auxiliaryStates": self.size, "auxiliaryPurpose": "integrated original physical balances",
            "equivalence": body["equivalencia"]["estado"],
            "matrix": "BDF uses a numerically differentiated Jacobian; RK45 does not assemble a global solve matrix.",
        }
        from core.balances.material_derivation import validate_model_journal
        material = validate_model_journal(model)
        if material:
            self.report["materialDerivation"] = material
        from core.balances.energy_derivation import validate_model_journal as validate_energy
        energy = validate_energy(model)
        if energy:
            self.report["energyDerivation"] = energy
        from core.termodinamica.derivation import validate_model_journal as validate_thermodynamics
        thermodynamics = validate_thermodynamics(model)
        if thermodynamics:
            self.report["thermodynamicDerivation"] = thermodynamics
        # Evaluate transformed IC residuals rather than assuming their substitution succeeded.
        initial = self.initial()
        if not np.all(np.isfinite(initial)) or np.any(self.dominio(0.0, initial) < 0):
            raise NoSoportado("The initial physical state is nonfinite or outside its declared domain.")
        environment = dict(self.context.valores, **dict(zip(self.fields, initial[:self.size])))
        environment[self.time] = 0.0
        for condition in body["condiciones"]:
            equality = condition["ecuacion"]
            left = float(evaluar_ast(equality["izquierda"], self.context.ctx, environment))
            right = float(evaluar_ast(equality["derecha"], self.context.ctx, environment))
            if not math.isclose(left, right, rel_tol=1e-10, abs_tol=1e-12):
                raise NoSoportado(f"Transformed initial condition {condition['id']} is inconsistent.")

    def initial(self):
        return np.r_[self.physical.inicial() / self.state_scales, np.zeros(self.size)]

    def rhs(self, tau, state):
        environment = dict(zip(self.fields, state[:self.size]))
        environment[self.time] = tau
        derivative = np.empty(self.size)
        for index, value in zip(self.order, self.numeric.rhs(environment, None)):
            derivative[index] = value
        # Diagnostics integrate the original equations, in the same numerical scales.
        physical = state[:self.size] * self.state_scales
        budget = self.physical.rhs(tau * self.time_scale, physical) * self.time_scale / self.state_scales
        return np.r_[derivative, budget]

    def firma(self, tau, state):
        return None

    def dominio(self, tau, state):
        return self.physical.dominio(tau * self.time_scale, state[:self.size] * self.state_scales)

    def describir_dominio(self, index):
        return self.physical.describir_dominio(index)


def resolve_transformed(model):
    system = TransformedSystem(model)
    study = model["estudio"]
    initial = system.initial()
    trajectory = integrar(system, initial, system.tf, rtol=study["rtol"], atol=np.tile(system.atol, 2),
                          max_step=system.tf / (study["muestras"] - 1), h_min=1e-10 / system.time_scale,
                          metodo=system.physical.metodo)
    end = trajectory.t_fin
    times = sorted({float(t) for t in np.linspace(0, system.tf, study["muestras"]) if t <= end} | {end})
    rows = [trajectory.y(t) for t in times]
    physical_times = [t * system.time_scale for t in times]
    physical_rows = [row[:system.size] * system.state_scales for row in rows]
    series = []
    for index, source in enumerate(system.physical.campos):
        unit = system.physical.unidades[source]
        series.append(serie(f"campo.{source}", source, unit, ["t"], [row[index] for row in physical_rows]))
        series.append(serie(f"transformed.{system.fields[index]}", system.fields[index], "1", ["t"], [row[index] for row in rows]))
        series.append(serie(f"budget.{source}", f"Integrated balance of {source}", unit, ["t"],
                            [row[system.size + index] * system.state_scales[index] for row in rows]))
    for oid, name, unit, function in system.physical.observables:
        series.append(serie(f"observable.{oid}", name, unit, ["t"], [function(t, row) for t, row in zip(physical_times, physical_rows)]))
    checks = []
    for index, source in enumerate(system.physical.campos):
        scale = max(abs(initial[index] * system.state_scales[index]), max(abs(row[index]) for row in physical_rows), 1e-300)
        residual = max(abs(row[index] - physical_rows[0][index] - raw[system.size + index] * system.state_scales[index])
                       for row, raw in zip(physical_rows, rows))
        checks.append({"id": f"original_balance.{source}", "valor": residual / scale,
                       "tolerancia": max(10 * study["rtol"], 10 * system.physical.atol[index] / scale),
                       "descripcion": "Reconstructed state change minus the integrated original physical equation."})
    for vid, description, function, scaling, tolerance in system.physical.verificaciones:
        scale = max(max(abs(scaling(t, row)) for t, row in zip(physical_times, physical_rows)), 1e-300)
        checks.append({"id": vid, "valor": max(abs(function(t, row)) for t, row in zip(physical_times, physical_rows)) / scale,
                       "tolerancia": tolerance, "descripcion": description})
    events = [evento(code, "t", t * system.time_scale, message) for code, t, _, _, message in trajectory.eventos]
    from core.modelo.equation_workbench import attach_report
    system.report=attach_report(system.report,model)
    return conjunto(model["id"], model["nombre"], "parcial" if trajectory.detenida else "resuelto",
                    {"motor": "rage.compilador.transformed", "metodo": system.physical.metodo,
                     "firma": system.report["signature"], "compilation": system.report,
                     "pasos": trajectory.pasos, "rechazos": trajectory.rechazos,
                     **({"mensaje": trajectory.detenida.mensaje} if trajectory.detenida else {})},
                    [eje("t", "Physical time", "tiempo", system.physical.unidad_t, physical_times)],
                    series, events, checks, modeloId=model["id"])
