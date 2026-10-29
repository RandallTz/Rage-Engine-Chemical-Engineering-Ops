"""Shared initial specification dispatch; closures remain package-owned."""


def initialize_state(amounts, energy_kind, energy_value, rigid, boundary_value, evaluate):
    """Use the same certified TP/TV/UV/UP operation for every API envelope."""
    if rigid:
        specification = 'TV' if energy_kind == 'T' else 'UV'
        return evaluate(specification, energy_value, boundary_value, amounts)
    if energy_kind == 'T':
        return evaluate('TP', energy_value, boundary_value, amounts)
    return evaluate('UP', boundary_value, energy_value, amounts)
