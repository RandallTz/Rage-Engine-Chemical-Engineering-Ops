"""Reaction tools rescued from the deleted Process Simulation side (clean-5, 29 October 2026).

Stoichiometry, element balancing, rate laws, chemical equilibrium and the isothermal batch trajectory,
kept as declared relations for F5 (reactors: kinetics and chemical equilibrium). They are not yet wired
into the common model's relation registry: F5 does that through the shared deduction tools. Until then
each entry below declares its kind, its relation, its quantities with units and the callable that
evaluates it, and `tests/test_reaction_relations.py` checks each against an independent reference.

The tools take a duck-typed `proveedor` (component list, activity coefficients and liquid formation
properties) and, for equilibrium, a `calculadora` with `h_liquido(T, x)`; the legacy thermodynamics
package that used to supply them was deleted with the Process Simulation side.
"""

RELATIONS = (
    {"id": "element_conservation", "kind": "condition",
     "relation": "A nu = 0",
     "quantities": {"A": "atoms per molecule", "nu": "1"},
     "callable": "core.reactions.balancing:comprobar_nu"},
    {"id": "reaction_basis", "kind": "definition",
     "relation": "nu spans the exact integer null space of A",
     "quantities": {"A": "atoms per molecule", "nu": "1"},
     "callable": "core.reactions.balancing:balancear"},
    {"id": "species_source", "kind": "definition",
     "relation": "R_i = sum_j nu_ij xi_j",
     "quantities": {"R_i": "mol/s", "xi_j": "mol/s", "nu_ij": "1"},
     "callable": "core.reactions.stoichiometry:fuentes_del_volumen"},
    {"id": "heat_of_reaction", "kind": "definition",
     "relation": "Q_rxn = -sum_j xi_j dH_j",
     "quantities": {"Q_rxn": "W", "xi_j": "mol/s", "dH_j": "J/mol"},
     "callable": "core.reactions.stoichiometry:calor_de_reaccion"},
    {"id": "arrhenius_rate_constant", "kind": "constitutive",
     "relation": "k(T) = k_ref exp[-Ea/R (1/T - 1/T_ref)]",
     "quantities": {"k": "declared rate unit", "Ea": "J/mol", "T": "K"},
     "callable": "core.reactions.kinetics:LeyDeVelocidad.k"},
    {"id": "mass_action_rate", "kind": "constitutive",
     "relation": "r = k(T) prod_i a_i^order_i",
     "quantities": {"r": "mol/s or mol/(m3 s)", "a_i": "1"},
     "callable": "core.reactions.kinetics:LeyDeVelocidad.evaluar"},
    {"id": "equilibrium_constant", "kind": "constitutive",
     "relation": "ln K(T) = -dG_rxn(T) / (R T), dG_rxn from formation properties (Kirchhoff and van 't Hoff)",
     "quantities": {"K": "1", "dG_rxn": "J/mol", "T": "K"},
     "callable": "core.reactions.equilibrium:propiedades_de_reaccion"},
    {"id": "equilibrium_condition", "kind": "condition",
     "relation": "ln Q_r(x) = ln K_r(T) for every independent reaction",
     "quantities": {"Q_r": "1", "K_r": "1"},
     "callable": "core.reactions.equilibrium:composicion_de_equilibrio"},
    {"id": "batch_species_balance", "kind": "balance",
     "relation": "dn_i/dt = sum_j nu_ij r_j(T, x)",
     "quantities": {"n_i": "mol", "r_j": "mol/s", "t": "s"},
     "callable": "core.reactions.batch:integrar"},
)
