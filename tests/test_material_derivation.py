"""Material provenance, compilation guards and independent conservation checks."""
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.balances.material_derivation import (
    MaterialDerivationError, describe_volume, edit_journal, fundamental_formulation,
    normalize_formulation, read_journal, replay_volume, validate_model_journal,
)
from core.modelo import ErrorModelo, leer_modelo_comun, desde_ensamblaje_v2, a_ensamblaje_v2
from core.compilador import NoSoportado, compilar
from core.compilador.report import compilation_report

ROOT = Path(__file__).resolve().parents[1]


def journal_for(owner="A", fixed=False):
    journal = {"format": "rage.material-derivation", "version": 1, "volumes": {}}
    actions = ["start", "integrate", "total", "no_reaction", "impermeable_remainder"]
    if fixed:
        actions.append("fixed_boundary")
    for kind in actions:
        journal = edit_journal(journal, owner, {"kind": kind})
    return journal


def request():
    return json.loads((ROOT / "frontend/app/motor/ejemplosMultifasicos.json").read_text(encoding="utf-8"))[0]


class MaterialDerivationTests(unittest.TestCase):
    def model(self):
        source = request()
        source["derivacion"] = {"materialDerivation": journal_for()}
        return desde_ensamblaje_v2(source)

    def test_replay_and_independent_total_balance(self):
        journal = journal_for()
        state = replay_volume(journal["volumes"]["A"])[-1]
        self.assertEqual(state["vista"], "cantidad")
        self.assertTrue(state["restoImpermeable"])
        self.assertFalse(state["fija"])
        development = describe_volume(journal, "A")
        self.assertEqual(development["steps"][-1]["latex"], r"\frac{dm_i}{dt}=\sum_s B_{vs}\dot m_{i,s}")
        self.assertTrue(any("Gauss" in row["title"] for row in development["steps"]))
        self.assertTrue(any("Reynolds" in row["title"] for row in development["steps"]))

    def test_nonmutating_edit_and_undo(self):
        journal = journal_for()
        before = copy.deepcopy(journal)
        modified = edit_journal(journal, "A", {"kind": "no_accumulation"})
        self.assertEqual(journal, before)
        self.assertEqual(edit_journal(modified, "A", {"kind": "undo"}), before)
        self.assertTrue(describe_volume(modified, "A")["steps"][-1]["latex"].startswith("0="))

    def test_reader_and_round_trip(self):
        model = self.model()
        self.assertIs(leer_modelo_comun(model), model)
        source = a_ensamblaje_v2(model)
        self.assertEqual(source["derivacion"]["materialDerivation"], journal_for())
        self.assertEqual(desde_ensamblaje_v2(source), model)

    def test_changed_flags_are_rejected_at_read_boundary(self):
        model = self.model()
        model["volumenes"][0]["supuestos"]["materia"]["sinAcumulacion"] = True
        with self.assertRaisesRegex(ErrorModelo, "recorded assumptions"):
            leer_modelo_comun(model)

    def test_changed_operation_is_rejected(self):
        model = self.model()
        model["motores"]["materialDerivation"]["volumes"]["A"]["operations"][-1]["changes"]["restoImpermeable"] = False
        with self.assertRaises(ErrorModelo):
            compilar(model)

    def test_unknown_owner_and_malformed_records(self):
        model = self.model()
        model["motores"]["materialDerivation"]["volumes"]["missing"] = model["motores"]["materialDerivation"]["volumes"].pop("A")
        with self.assertRaisesRegex(MaterialDerivationError, "unknown volume"):
            validate_model_journal(model)
        for mutation in (lambda j: j.update(version=True), lambda j: j.update(extra=1),
                         lambda j: j["volumes"]["A"]["operations"][0]["changes"].update(fija="true"),
                         lambda j: j["volumes"]["A"]["operations"].append(copy.deepcopy(j["volumes"]["A"]["operations"][0]))):
            journal = journal_for()
            mutation(journal)
            with self.assertRaises(MaterialDerivationError):
                read_journal(journal)

    def test_stationary_assumption_cannot_run_as_transient(self):
        model = self.model()
        journal = edit_journal(journal_for(), "A", {"kind": "no_accumulation"})
        model["motores"]["materialDerivation"] = journal
        model["volumenes"][0]["supuestos"]["materia"]["sinAcumulacion"] = True
        with self.assertRaisesRegex(NoSoportado, "algebraic"):
            compilar(model)

    def test_spatial_and_unclosed_boundary_cannot_be_ignored(self):
        for change, message in (({"vista": "campo"}, "Transform"), ({"restoImpermeable": False}, "flux law")):
            model = self.model()
            model["motores"] = {}
            model["volumenes"][0]["supuestos"]["materia"].update(change)
            with self.assertRaisesRegex(NoSoportado, message):
                compilar(model)

    def test_report_binds_operations_and_conservation_relations(self):
        report = compilation_report(self.model())
        entry = report["materialDerivation"][0]
        self.assertEqual(entry["relationIds"], ["materia.A.1", "materia.A.2"])
        self.assertEqual(len(entry["signature"]), 64)
        self.assertEqual(len(entry["operationIds"]), 4)
        self.assertEqual(report["closureStrategy"], "nested_equilibrium")

    def test_legacy_input_stays_compatible_without_invented_journal(self):
        model = desde_ensamblaje_v2(request())
        self.assertEqual(validate_model_journal(model), [])
        self.assertNotIn("materialDerivation", compilation_report(model))

    def test_v2_api_rejects_forged_journal_before_thermodynamics(self):
        from backend.motor_ensamblaje_v2 import validar_v2
        source = request()
        source["derivacion"] = {"materialDerivation": journal_for()}
        source["derivacion"]["materialDerivation"]["volumes"]["A"]["operations"].pop()
        response, system = validar_v2(source)
        self.assertIsNone(system)
        self.assertIsNone(response["modeloId"])
        self.assertEqual(response["diagnosticos"][0]["codigo"], "MOTOR_ENS_MATERIAL_JOURNAL")


if __name__ == "__main__":
    unittest.main()
