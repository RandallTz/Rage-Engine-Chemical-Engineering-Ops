"""Liquid-only admission of acetic acid (user decision dec-f5-acetic-liquid-only, 30 October 2026).

Acetic acid dimerises in the vapour, so the packages' ideal vapour is invalid for it. It is registered apart from
the published catalog: vapour-liquid systems, flashes and L-V paths reject it with ESPECIE_SOLO_LIQUIDO, while an
explicitly liquid-only system (UNIFAC or ideal liquid) admits it and refuses every vapour evaluation.
"""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import catalogo, mezclas as mz, mezclas_datos as md
from core.reactions import chemical_equilibrium as ce

ACOH, ETOH, ETOAC, H2O = "64-19-7", "64-17-5", "141-78-6", "7732-18-5"
VLE_PACKAGES = ("mezcla-ideal", "nrtl-chemsep", "unifac-original-public", "unifac-dortmund-public")


class PublishedCatalogUnchanged(unittest.TestCase):
    def test_registry_and_published_species(self):
        self.assertNotIn(ACOH, catalogo.REGISTRO)
        self.assertEqual(len(catalogo.REGISTRO), 8)
        self.assertNotIn(ACOH, md.especies_disponibles())
        self.assertEqual(md.especies_solo_liquido(), [ACOH])
        from backend import motor_catalogo
        published = motor_catalogo.catalogo_publico()
        self.assertNotIn(ACOH, [s["cas"] for s in published["sustancias"]])
        for paquete in published["paquetes"]:
            self.assertNotIn(ACOH, [e["cas"] for e in paquete["especies"]])

    def test_vapour_liquid_fingerprint_has_no_liquid_only_marker(self):
        cas = [ETOH, H2O]
        self.assertEqual(mz.Sistema("unifac-dortmund-public", cas).huella(),
                         mz.Sistema("unifac-dortmund-public", cas, solo_liquido=False).huella())
        self.assertNotEqual(mz.Sistema("unifac-dortmund-public", cas).huella(),
                            mz.Sistema("unifac-dortmund-public", cas, solo_liquido=True).huella())


class VapourLiquidRejection(unittest.TestCase):
    def test_admission_rule_reports_liquid_only(self):
        for pid in VLE_PACKAGES:
            f = catalogo.faltantes(mz.PAQUETES[pid].liquido, ACOH, pid)
            self.assertEqual([x["codigo"] for x in f], ["ESPECIE_SOLO_LIQUIDO"], pid)
            self.assertIn("liquid-only", f[0]["mensaje"])

    def test_vapour_liquid_system_rejects(self):
        for pid in VLE_PACKAGES:
            with self.assertRaises(mz.FaltaParametro) as x:
                mz.Sistema(pid, [ETOH, ACOH])
            self.assertEqual(x.exception.codigo, "ESPECIE_SOLO_LIQUIDO", pid)
            self.assertEqual(x.exception.detalle["cas"], ACOH)

    def test_common_layer_rejects(self):
        from core.termodinamica import capa
        modelo = {"componentes": [{"id": 1, "identidadQuimica": {"cas": ETOH}}, {"id": 2, "identidadQuimica": {"cas": ACOH}}]}
        v = {"id": "drum", "componenteIds": [1, 2]}
        paq = {"modelo": {"id": "unifac-dortmund-public"}}
        with self.assertRaises(capa.NoSoportado) as x:
            capa._sistema(modelo, v, paq)
        self.assertIn("liquid-only", str(x.exception))

    def test_ideal_gas_reaction_phase_rejects(self):
        with self.assertRaises(ce.ChemicalEquilibriumError) as x:
            ce.IdealGasPhase([ETOH, ACOH, ETOAC, H2O])
        self.assertEqual(x.exception.code, "LIQUID_ONLY_SPECIES")


class LiquidOnlySystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cas = [ETOH, ACOH, ETOAC, H2O]
        cls.systems = {pid: mz.Sistema(pid, cls.cas, solo_liquido=True)
                       for pid in ("unifac-dortmund-public", "unifac-original-public", "mezcla-ideal")}

    def test_liquid_potentials_accept(self):
        x = np.array([0.4, 0.3, 0.2, 0.1])
        idx = list(range(4))
        for pid, s in self.systems.items():
            s.dominio(298.15, 1e5)
            mu = s.mu("liquido", 298.15, 1e5, x, idx)
            self.assertTrue(np.all(np.isfinite(mu)), pid)
            f = s.fase("liquido-1", "liquido", 298.15, 1e5, x, idx)
            self.assertTrue(np.isfinite(f.h) and np.isfinite(f.s), pid)
            trials = s.prueba_estabilidad(298.15, 1e5, mu, idx, incluir_vapor=False)
            self.assertTrue(all(t[0] == "liquido" for t in trials), pid)
        self.assertLessEqual(self.systems["unifac-dortmund-public"].T_rango[0], 298.15)

    def test_every_vapour_evaluation_rejects(self):
        s = self.systems["unifac-dortmund-public"]
        x, idx, n = np.array([0.4, 0.3, 0.2, 0.1]), [0, 1, 2, 3], np.array([1.0, 1.0, 0.5, 0.5])
        mu = s.mu("liquido", 298.15, 1e5, x, idx)
        calls = {
            "vapour mu": lambda: s.mu("vapor", 298.15, 1e5, x, idx),
            "vapour phase": lambda: s.fase("vapor-1", "vapor", 298.15, 1e5, x, idx),
            "L-V ratio": lambda: s.lv_ln_k(298.15, 1e5, x, idx),
            "vapour trial": lambda: s.prueba_estabilidad(298.15, 1e5, mu, idx),
            "saturation": lambda: s.P_saturacion(350.0, 1),
            "TP flash": lambda: s.equilibrio_TP(350.0, 1e5, n),
            "PH flash": lambda: s.equilibrio_PH(1e5, -1e5, n),
            "TV flash": lambda: s.equilibrio_TV(350.0, 1e-3, n),
            "UV flash": lambda: s.equilibrio_UV(-1e5, 1e-3, n),
        }
        for name, call in calls.items():
            with self.assertRaises(mz.FaltaParametro, msg=name) as x_:
                call()
            self.assertEqual(x_.exception.codigo, "ESPECIE_SOLO_LIQUIDO", name)

    def test_lv_continuation_rejects(self):
        from core.termodinamica import lv_continuation
        s = mz.Sistema("unifac-dortmund-public", [ETOH, ACOH], solo_liquido=True)
        with self.assertRaises(mz.FaltaParametro) as x:
            lv_continuation.trace(s, "isothermal", fixed=350.0)
        self.assertEqual(x.exception.codigo, "ESPECIE_SOLO_LIQUIDO")

    def test_vapour_reaction_phase_rejects(self):
        with self.assertRaises(ce.ChemicalEquilibriumError):
            ce.PackagePhase(self.systems["unifac-dortmund-public"], "vapor", anchor="liquid")

    def test_gas_anchor_rejected(self):
        """Review R1: the default gas anchor would reach acetic acid's liquid through the monomer ideal gas."""
        for pid, s in self.systems.items():
            for kwargs in ({}, {"anchor": "gas"}):
                with self.assertRaises(ce.ChemicalEquilibriumError, msg=(pid, kwargs)) as x:
                    ce.PackagePhase(s, "liquido", **kwargs)
                self.assertEqual(x.exception.code, "LIQUID_ANCHOR_REQUIRED")
                self.assertEqual(x.exception.detail["cas"], [ACOH])
        ce.PackagePhase(mz.Sistema("unifac-dortmund-public", [ETOH, H2O], solo_liquido=True), "liquido")

    def test_bridge_gas_anchor_rejected(self):
        from core.termodinamica import derived_bridge as b
        calls = {
            "reaction_enthalpy default": lambda: b.reaction_enthalpy("unifac-dortmund-public", self.cas, [[-1, -1, 1, 1]],
                                                                     298.15, 1e5, liquid_only=True),
            "phase_caloric gas": lambda: b.phase_caloric("unifac-dortmund-public", self.cas, 298.15, 1e5,
                                                         [1.0, 1.0, 0.5, 0.5], anchor="gas", liquid_only=True),
        }
        for name, call in calls.items():
            with self.assertRaises(b.DerivedThermoError, msg=name) as x:
                call()
            self.assertEqual(x.exception.code, "LIQUID_ANCHOR_REQUIRED", name)
        r = b.reaction_enthalpy("unifac-dortmund-public", self.cas, [[-1, -1, 1, 1]], 298.15, 1e5, anchor="liquid",
                                liquid_only=True)
        self.assertAlmostEqual(r["dH"][0], -4515.0, delta=1.0)           # tabulated liquid Hfl, Hess
        self.assertEqual(r["formation"][ACOH]["state"], "pure liquid, 298.15 K, 1 bar")

    def test_liquid_anchor_provenance(self):
        """Review R2: the liquid anchor names the liquid tabulations and the pure-liquid state."""
        from chemicals import reaction as rx
        L = ce.PackagePhase(self.systems["unifac-dortmund-public"], "liquido", anchor="liquid")
        for c in self.cas:
            f = L.provenance["formation"][c]
            self.assertEqual((f["Hf"], f["S0"]), (rx.Hfl_methods(c)[0], rx.S0l_methods(c)[0]), c)
            self.assertEqual(f["state"], "pure liquid, 298.15 K, 1 bar")
        self.assertEqual(L.provenance["formation"][ACOH]["Hf"], "ATCT_L")
        gas = ce.PackagePhase(mz.Sistema("unifac-dortmund-public", [ETOH, H2O]), "liquido")
        self.assertEqual(gas.provenance["formation"][ETOH]["state"], "ideal gas, 298.15 K, 1 bar")


class Esterification(unittest.TestCase):
    """EtOH + AcOH = EtOAc + H2O in the liquid with the registered acetic acid, no in-process patching."""

    def test_conversion_and_liquid_only_certificate(self):
        s = mz.Sistema("unifac-dortmund-public", [ETOH, ACOH, ETOAC, H2O], solo_liquido=True)
        L = ce.PackagePhase(s, "liquido", anchor="liquid")
        A, _ = ce.element_matrix(list(s.cas))
        out = ce.solve_extents(L, [[-1, -1, 1, 1]], [1.0, 1.0, 0.0, 0.0], ce.T0, ce.P0, A)
        cert = out["certificate"]
        self.assertTrue(cert["certified"])
        self.assertAlmostEqual(out["extents"][0], 0.672, delta=0.002)
        self.assertTrue(cert["phase_stability"]["stable"])
        self.assertFalse(cert["phase_stability"]["vapour_assessed"])


if __name__ == "__main__":
    unittest.main()
