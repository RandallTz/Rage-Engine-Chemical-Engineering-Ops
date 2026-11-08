"""Readable labels, groups and ranks for indexed-network series (publication metadata only).

The Python publisher owns display names so the interface never parses symbol strings. A label is stage-agnostic
(the stage index is structure the client already has). Ranks order the default charts: 0 temperature, 1 liquid
composition, 2 vapour composition, 3 pressure, 4 phase amounts and flows, 5 inventories and states, 6 phase
properties, 7 other published quantities, 8 boundary-port values, 9 internal quantities (derivatives, losses,
stream bookkeeping). The rank limit and the chart cap of the default layout live in one place, the client's
chartSpecification.ts (DEFAULT_RANK_LIMIT, DEFAULT_CHART_LIMIT); this module only publishes the ranks.
"""
import re

PHASES = {'L': 'Liquid', 'V': 'Vapour'}
PROPERTIES = {'amount': ('amount', 4), 'h': ('molar enthalpy', 6), 'u': ('molar internal energy', 6),
              'v': ('molar volume', 6), 'M': ('molar mass', 6), 'present': ('presence indicator', 6)}


def humanize(name):
    words = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', name).replace('_', ' ').strip().lower()
    return words[:1].upper()+words[1:] if words else name


class Namer:
    """Per-stage naming context built from the stage's common model and its identity map back to the template."""
    def __init__(self, model, mapping):
        self.components = {c['id']: c.get('nombre') or c.get('simbolo') or str(c['id']) for c in model['componentes']}
        self.owners = {}
        for key in ('volumes', 'streams', 'exchanges'):
            for source, stage in (mapping.get(key) or {}).items():
                self.owners[stage] = source
        self.ids = sorted(self.owners, key=len, reverse=True)

    def species(self, token):
        try:
            return self.components.get(int(token), token)
        except ValueError:
            return token

    def split(self, name):
        """Return (base, owner source id or None, trailing parts) for names of the form base__owner[__part...](t)."""
        text = re.sub(r'\(.*\)$', '', name)
        for stage_id in self.ids:
            if '__'+stage_id in text:
                head, _, tail = text.partition('__'+stage_id)
                return head, self.owners[stage_id], [p for p in tail.split('__') if p]
        head, *parts = text.split('__')
        return head, None, parts

    def describe(self, name):
        """(label, owner or None, rank, family) for a published quantity name; owner is a template identity."""
        if name.startswith('Derivative('):
            inner = name[len('Derivative('):].rsplit(', ', 1)[0]
            label, owner, _, family = self.describe(inner)
            return 'Rate of change of '+label[:1].lower()+label[1:], owner, 9, 'derivative:'+family
        base, owner, parts = self.split(name)
        tail = parts[-1] if parts else ''
        if base == 'T':
            return 'Temperature', owner, 0, 'T'
        if base == 'p':
            return 'Pressure', owner, 3, 'p'
        if base == 'phase_x' or re.fullmatch(r'phase_x_\d+', base):
            phase = PHASES.get(tail, tail)
            return f'{phase} mole fraction of {self.species(base.rsplit("_", 1)[-1])}', owner, 1 if tail == 'L' else 2, 'x'+tail
        if base.startswith('phase_') and tail in PHASES:
            prop, rank = PROPERTIES.get(base[len('phase_'):], (base[len('phase_'):], 6))
            return f'{PHASES[tail]} {prop}', owner, rank, base+tail
        m = re.fullmatch(r'liquidMassFraction_(\d+)', base)
        if m:
            return f'Liquid mass fraction of {self.species(m.group(1))}', owner, 1, 'wL'
        if base == 'm' and parts:
            return f'Mass of {self.species(parts[-1])}', owner, 5, 'm'
        m = re.fullmatch(r'n_(\d+)', base)
        if m:
            return f'Amount of {self.species(m.group(1))}', owner, 5, 'n'
        simple = {'H': ('Enthalpy', 5), 'U': ('Internal energy', 5), 'V': ('Volume', 5), 'm_total': ('Total mass', 5),
                  'liquid_volume': ('Liquid volume', 4), 'z_r': ('Liquid level', 5), 'loss': ('Pressure loss', 9),
                  'energy_average_0': ('Average specific energy', 9)}
        if base in simple:
            return simple[base][0], owner, simple[base][1], base
        if base == 'q' and parts:
            return f'Component flow of {self.species(parts[-1])} (stream)', owner, 9, 'q'
        if re.fullmatch(r'(?:[a-z]+)?(?:Mass|Molar|Volumetric)?[Ff]low', base):
            return humanize(base), owner, 4, base
        m = re.fullmatch(r'(.+?)_(\d+)', base)
        if m:
            return f'{humanize(m.group(1))} of {self.species(m.group(2))}', owner, 7, base
        return humanize(base), owner, 7, base


def stage_display(namer, rows):
    """rows: [(series id, quantity name, unit)] of one stage -> {id: (label, rank, group)}. An owner qualifier is
    added only where two quantities of one stage would otherwise share a label."""
    described = [(sid, unit, *namer.describe(name)) for sid, name, unit in rows]
    counts = {}
    for sid, unit, label, owner, rank, family in described:
        counts[(label, unit)] = counts.get((label, unit), 0)+1
    result = {}
    for sid, unit, label, owner, rank, family in described:
        if counts[(label, unit)] > 1 and owner:
            label = f'{label} in {humanize(owner).lower()}'
        result[sid] = (label, rank, f'{label}|{unit}')
    return result


def port_display(port_id, role, unit, species=None):
    """port_id is the stage-agnostic port name, so one boundary quantity of every stage that publishes it shares a
    label and a group."""
    names = {'flow': 'flow', 'enthalpy': 'specific enthalpy', 'temperature': 'temperature', 'pressure': 'pressure',
             'power': 'power', 'fraction': 'mass fraction'}
    label = f'Port {port_id}: {names[role]}' + (f' of {species}' if species else '')
    return label, 8, f'{label}|{unit}'
