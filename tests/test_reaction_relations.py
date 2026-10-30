"""Reference checks for the reaction tools rescued into core/reactions/ (clean-5, 29 October 2026).

Each declared relation in core.reactions.RELATIONS resolves to a callable, and each tool is checked
against a closed-form reference that does not use the tool: integer element balances, Arrhenius,
Kirchhoff/van 't Hoff with constant dCp, the isomerization equilibrium x_B/x_A = K and the first-order
batch decay n_A = n0 exp(-k t / N). Run: python tests/test_reaction_relations.py
"""
import importlib
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.reactions import RELATIONS, balancing, batch, equilibrium, kinetics, stoichiometry

R = 8.314462618


class IdealProvider:
    """Ideal liquid (gamma = 1) with constant liquid Cp and given formation properties."""

    def __init__(self, Hf, Gf, Cp):
        self.componentes = [f"s{i}" for i in range(len(Hf))]
        self.Hf, self.Gf, self.Cp = (np.asarray(v, dtype=float) for v in (Hf, Gf, Cp))

    def coeficientes_actividad(self, T, x):
        return np.ones(len(x))

    def entalpias_formacion_liquido(self):
        return self.Hf

    def energias_gibbs_formacion_liquido(self):
        return self.Gf

    def capacidades_calorificas_liquido(self, T):
        return self.Cp

    def h_liquido(self, T, x):          # sensible enthalpy from 298.15 K, used as the `calculadora`
        return float(np.dot(x, self.Cp) * (T - 298.15))


class ReactionRelations(unittest.TestCase):
    def test_declared_relations_resolve(self):
        self.assertEqual(len({r["id"] for r in RELATIONS}), len(RELATIONS))
        for r in RELATIONS:
            module, _, attr = r["callable"].partition(":")
            obj = importlib.import_module(module)
            for part in attr.split("."):
                obj = getattr(obj, part)
            self.assertTrue(callable(obj), r["id"])
            self.assertIn(r["kind"], {"balance", "definition", "constitutive", "condition"})

    def test_balancing_methane_combustion(self):
        species = ["CH4", "O2", "CO2", "H2O"]
        atoms = [{"C": 1, "H": 4}, {"O": 2}, {"C": 1, "O": 2}, {"H": 2, "O": 1}]
        out = balancing.balancear(species, atoms, reactivos=["CH4", "O2"])
        self.assertEqual(out["dimension_del_espacio"], 1)
        self.assertEqual([int(v) for v in out["reacciones"][0]["nu"]], [-1, -2, 1, 2])
        self.assertTrue(balancing.comprobar_nu([-1, -2, 1, 2], atoms, species)["conserva"])
        self.assertFalse(balancing.comprobar_nu([-1, -1, 1, 2], atoms, species)["conserva"])

    def test_heat_of_reaction(self):
        r = stoichiometry.Reaccion("r1", "b1", [-1, 1], "irreversible", r_directa=0.25)
        self.assertAlmostEqual(r.xi, 0.25, places=15)
        self.assertAlmostEqual(stoichiometry.calor_de_reaccion([r], {"r1": -4.0e4}), -1.0e4, places=9)

    def test_arrhenius(self):
        law = kinetics.LeyDeVelocidad(2.0, 5.0e4, [1, 0], T_ref=300.0)
        self.assertAlmostEqual(law.k(300.0), 2.0, places=14)
        ref = 2.0 * math.exp(-5.0e4 / R * (1 / 350.0 - 1 / 300.0))
        self.assertLess(abs(law.k(350.0) / ref - 1), 1e-9)       # R to 9 digits
        p = IdealProvider([0, 0], [0, 0], [0, 0])
        self.assertAlmostEqual(law.evaluar(p, 300.0, [0.3, 0.7]), 0.6, places=14)

    def test_reaction_properties_kirchhoff(self):
        # A -> B with dH0 = -1e4 J/mol, dG0 = -2e3 J/mol, dCp = 10 J/(mol K) (constant).
        p = IdealProvider([-1.0e4, -2.0e4], [-1.0e3, -3.0e3], [100.0, 110.0])
        T, T0 = 350.0, 298.15
        out = equilibrium.propiedades_de_reaccion(p, p, [-1, 1], T)
        dS0 = (-1.0e4 + 2.0e3) / T0
        dH = -1.0e4 + 10.0 * (T - T0)
        dS = dS0 + 10.0 * math.log(T / T0)
        self.assertAlmostEqual(out["en_referencia"]["K"], math.exp(2.0e3 / (R * T0)), places=10)
        self.assertAlmostEqual(out["riguroso"]["dH"], dH, places=6)
        self.assertAlmostEqual(out["riguroso"]["dS"], dS, places=6)
        self.assertAlmostEqual(math.log(out["riguroso"]["K"]), -(dH - T * dS) / (R * T), places=8)
        self.assertAlmostEqual(math.log(out["vant_hoff"]["K"]),
                               2.0e3 / (R * T0) + 1.0e4 / R * (1 / T - 1 / T0), places=8)

    def test_isomerization_equilibrium(self):
        p = IdealProvider([0.0, 0.0], [0.0, -2.0e3], [0.0, 0.0])
        T = 298.15
        K = math.exp(2.0e3 / (R * T))
        out = equilibrium.composicion_de_equilibrio(p, p, np.array([[-1.0, 1.0]]), np.array([1.0, 0.0]), T)
        self.assertTrue(out["convergencia"]["convergio"])
        self.assertAlmostEqual(out["moles_equilibrio"][1], K / (1 + K), places=8)
        self.assertTrue(all(v > 0 for v in out["estabilidad"]["autovalores"]))

    def test_first_order_batch(self):
        p = IdealProvider([0, 0], [0, 0], [0, 0])
        law = kinetics.LeyDeVelocidad(0.5, 0.0, [1, 0], T_ref=300.0, base="fraccion_molar")
        rxn = kinetics.ReaccionCinetica("r1", "b1", [-1, 1], law)
        out = batch.integrar(p, [rxn], [2.0, 0.0], 300.0, 4.0, n_muestras=9)
        n_a, n_b = out["moles"]                                   # one row per species
        self.assertEqual(len(n_a), len(out["t"]))
        for t, n in zip(out["t"], zip(n_a, n_b)):
            self.assertAlmostEqual(n[0], 2.0 * math.exp(-0.5 * t / 2.0), delta=1e-6)
            self.assertAlmostEqual(n[0] + n[1], 2.0, places=9)
        self.assertTrue(out["no_negatividad"]["cumple"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
