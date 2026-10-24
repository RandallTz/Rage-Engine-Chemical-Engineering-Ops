"""Model-only inventory semantics, independent references and execution guards."""
import copy
import unittest

from test_workspace_handoffs import example
from core.modelo import leer_modelo_comun, ErrorModelo
from core.modelo.adaptadores import a_ensamblaje_v2, desde_ensamblaje_v2
from core.modelo.dynamic_definition import (
    describe_definition, read_definition, edit_definition, ensure_executable,
)
from core.compilador.compilador import compilar, resolver, NoSoportado
from core.compilador.report import compilation_report


def operation(kind="total_mass", component=None, dependent=None, mode="fixed", number=1):
    inventory = {"kind": kind}
    if kind == "energy":
        inventory["coordinate"] = "H"
    if component is not None:
        inventory["componentId"] = component
    return {"id": f"inventory-{number}", "volumeId": "A", "inventory": inventory,
            "mode": mode, "reason": "Declared physical inventory condition.",
            **({"dependent": dependent} if dependent else {})}


def declared(*ops):
    model = example()
    model["motores"]["dynamicDefinition"] = {"format": "rage.dynamic-definition", "version": 1, "operations": list(ops)}
    return model


class DynamicDefinitionTests(unittest.TestCase):
    def test_unconstrained_inventory_model_needs_no_numerical_data(self):
        model = example()
        model["estudio"] = None
        for data in model["datos"].values():
            data["declaracion"]["texto"] = ""
        before = copy.deepcopy(model)
        report = describe_definition(leer_modelo_comun(model))
        self.assertEqual(before, model)
        self.assertEqual([], report["diagnostics"])
        self.assertEqual(4, len(report["inventories"]))
        self.assertTrue(all(item["mode"] == "dynamic" for item in report["inventories"]))
        self.assertEqual({"kg", "mol", "J"}, {item["unit"] for item in report["inventories"]})
        self.assertIn("H energy inventory", str(report))
        self.assertIn("No clipping", str(report))

    def test_fixed_mass_keeps_species_and_energy_dynamic_and_does_not_mutate_data(self):
        model = declared(operation(dependent={"kind": "stream_total", "id": "feed"}))
        before = copy.deepcopy(model)
        report = describe_definition(leer_modelo_comun(model))
        self.assertEqual(before, model)
        self.assertEqual([], report["diagnostics"])
        fixed = [item for item in report["inventories"] if item["mode"] == "fixed"]
        self.assertEqual(["total_mass"], [item["inventory"]["kind"] for item in fixed])
        self.assertEqual("dependent_unknown", next(item["role"] for item in report["variables"] if item["id"] == "feed.F"))
        self.assertTrue(any("Retained dynamic" in row["title"] and "frac" in row["latex"] for row in fixed[0]["steps"]))
        self.assertTrue(any("Compatibility" in row["title"] for row in fixed[0]["steps"]))
        self.assertEqual("derived_quantity", next(item["role"] for item in report["variables"] if item["id"] == "A:total_mass"))

    def test_independent_mass_reference_with_distinct_molar_masses_and_perturbation(self):
        # Equal *mass* rates, not equal molar rates: a binary tank can change
        # composition at fixed mass, while independent heat changes its energy.
        masses = (0.018015, 0.046069)
        n = (0.8, 0.2)
        x = tuple(value / sum(n) for value in n)
        feed_composition = (0.5, 0.5)
        incoming = 0.001
        outgoing = incoming * sum(a * b for a, b in zip(masses, feed_composition)) / sum(a * b for a, b in zip(masses, x))
        dn = tuple(incoming * a - outgoing * b for a, b in zip(feed_composition, x))
        self.assertAlmostEqual(0.0, sum(a * b for a, b in zip(masses, dn)), places=15)
        self.assertTrue(all(abs(value) > 1e-8 for value in dn))
        # A zero derivative at one instant is a rate evaluation, not a mode switch.
        initial_rate = (0.0, 0.0)
        perturbed_rate = dn
        self.assertNotEqual(initial_rate, perturbed_rate)
        self.assertNotEqual(0.0, 5.0 + incoming * 100.0 - outgoing * 80.0)

    def test_energy_constraint_is_separate_from_mass_and_closure(self):
        model = declared(operation("energy", dependent={"kind": "heat_flow", "id": "heater"}))
        report = describe_definition(leer_modelo_comun(model))
        self.assertEqual([], report["diagnostics"])
        self.assertEqual(["energy"], [item["inventory"]["kind"] for item in report["inventories"] if item["mode"] == "fixed"])
        self.assertTrue(any(item["id"] == "heater.Q" and item["role"] == "dependent_unknown" for item in report["variables"]))
        self.assertEqual("equilibrio", report["closures"][0]["kind"])
        self.assertEqual({"K", "m3", "mol", "1"}, {item["unit"] for item in report["variables"] if item["role"] == "closure_unknown"})

    def test_missing_and_reused_unknowns_are_diagnostics_not_implicit_controllers(self):
        missing = describe_definition(declared(operation()))
        self.assertIn("missing_dependent", [item["code"] for item in missing["diagnostics"]])
        shared = {"kind": "stream_total", "id": "feed"}
        reused = describe_definition(declared(operation(dependent=shared), operation("component_amount", 1, shared, number=2)))
        self.assertIn("dependent_reused", [item["code"] for item in reused["diagnostics"]])

    def test_legacy_flags_are_not_silently_migrated(self):
        model = example()
        model["motores"].pop("materialDerivation")
        model["volumenes"][0]["supuestos"]["materia"]["sinAcumulacion"] = True
        before = copy.deepcopy(model)
        report = describe_definition(leer_modelo_comun(model))
        self.assertEqual(before, model)
        self.assertIn("legacy_accumulation", [item["code"] for item in report["diagnostics"]])
        self.assertTrue(any("frac{dm_i}{dt}" in row["latex"] for item in report["inventories"] for row in item["steps"]))

    def test_versioned_roundtrip_replay_and_explicit_restore(self):
        model = example()
        original = copy.deepcopy(model)
        definition = edit_definition(model, {"kind": "append", "operation": operation(dependent={"kind": "stream_total", "id": "feed"})})
        self.assertEqual(model, original)
        model["motores"]["dynamicDefinition"] = definition
        self.assertEqual(definition, desde_ensamblaje_v2(a_ensamblaje_v2(model))["motores"]["dynamicDefinition"])
        restore = operation(mode="dynamic", number=2)
        model["motores"]["dynamicDefinition"] = edit_definition(model, {"kind": "append", "operation": restore})
        self.assertTrue(all(item["mode"] == "dynamic" for item in describe_definition(model)["inventories"]))
        ensure_executable(model)
        model["motores"]["dynamicDefinition"] = edit_definition(model, {"kind": "undo"})
        with self.assertRaises(ValueError):
            ensure_executable(model)
        self.assertEqual(original["motores"]["materialDerivation"], model["motores"]["materialDerivation"])

    def test_new_constraints_cannot_be_ignored_by_any_current_execution_branch(self):
        model = declared(operation(dependent={"kind": "stream_total", "id": "feed"}))
        for function in (compilar, resolver, compilation_report):
            with self.subTest(function=function.__name__), self.assertRaisesRegex(NoSoportado, "constrained dynamic execution"):
                function(model)
        # The native endpoint used by thermodynamic networks has the same guard.
        from backend.motor_ensamblaje_v2 import validar_v2
        result = validar_v2(a_ensamblaje_v2(model))
        self.assertIn("MOTOR_ENS_INVENTORY_CONSTRAINT", str(result))

    def test_bad_references_unknown_versions_keys_and_dimensions_are_rejected(self):
        good = declared(operation("component_amount", 1, {"kind": "stream_total", "id": "feed"}))
        mutations = [lambda d: d.update(version=2), lambda d: d.update(extra=True), lambda d: d["operations"][0].update(volumeId="missing"),
                     lambda d: d["operations"][0]["inventory"].update(componentId=999), lambda d: d["operations"][0].update(dependent={"kind": "heat_flow", "id": "heater"}),
                     lambda d: d["operations"][0].update(reason=""), lambda d: d["operations"].append(copy.deepcopy(d["operations"][0])),
                     lambda d: d["operations"][0].update(dependent={"kind": "component_flow", "id": "feed", "componentId": True})]
        for mutate in mutations:
            model = copy.deepcopy(good)
            mutate(model["motores"]["dynamicDefinition"])
            with self.subTest(definition=model["motores"]["dynamicDefinition"]), self.assertRaises(ErrorModelo):
                leer_modelo_comun(model)
        wrong_units = copy.deepcopy(good)
        wrong_units['datos']['feed.F']['declaracion']['unidad'] = 'W'
        with self.assertRaisesRegex(ErrorModelo, 'unit W is incompatible'):
            leer_modelo_comun(wrong_units)

    def test_inactive_and_redundant_constraints_need_explicit_review(self):
        model = declared(operation(), operation("component_amount", 1, number=2), operation("component_amount", 2, number=3))
        self.assertIn("redundant_inventory", [item["code"] for item in describe_definition(model)["diagnostics"]])
        model["volumenes"][0]["balances"]["materia"] = False
        self.assertIn("inactive_inventory", [item["code"] for item in describe_definition(model)["diagnostics"]])

    def test_retired_bindings_preserve_history_after_topology_changes(self):
        model = declared(operation(dependent={"kind": "stream_total", "id": "feed"}), operation(mode="dynamic", number=2))
        model["corrientes"] = []
        self.assertIs(model, leer_modelo_comun(model))
        self.assertEqual(2, len(model["motores"]["dynamicDefinition"]["operations"]))
        ensure_executable(model)

    def test_energy_coordinate_changes_never_reinterpret_saved_constraints(self):
        model = declared(operation("energy", dependent={"kind": "heat_flow", "id": "heater"}))
        # A changed mechanical boundary would change the derived energy
        # coordinate. The previously declared H constraint is still an H constraint.
        model['volumenes'][0]['frontera']['tipo'] = 'rigida'
        report = describe_definition(model)
        self.assertIn('inactive_inventory', [item['code'] for item in report['diagnostics']])
        self.assertTrue(any(item['inventory'] == {'kind':'energy','coordinate':'U'} and item['mode'] == 'dynamic' for item in report['inventories']))
        self.assertEqual('H', model['motores']['dynamicDefinition']['operations'][0]['inventory']['coordinate'])
        with self.assertRaises(ValueError):
            ensure_executable(model)

    def test_api_undo_can_repair_a_binding_invalidated_by_topology(self):
        from backend.api_modelo import dynamic_definition
        model = declared(operation(dependent={"kind": "stream_total", "id": "feed"}))
        model["corrientes"] = []
        before = copy.deepcopy(model)
        result = dynamic_definition({"modelo": model, "action": {"kind": "undo"}})
        self.assertEqual([], result["definition"]["operations"])
        self.assertEqual(model, before)
        self.assertTrue(all(item["mode"] == "dynamic" for item in result["formulation"]["inventories"]))
        for operation_value in ({}, {"inventory": 42}, {"id":"bad","volumeId":"A","inventory":42,"mode":"fixed","reason":"test"}):
            with self.assertRaises(Exception) as raised:
                dynamic_definition({"modelo": model, "action": {"kind": "append", "operation": operation_value}})
            self.assertEqual(422, raised.exception.status_code)


if __name__ == "__main__":
    unittest.main()
