"""Replay a research deduction script (rage.deduction-script v1) through the engine's authoring path.

A deduction script lists, in readable names, the fundamental assumptions of each control volume and the
equation operations that reduce the fundamental laws to the working model. This tool replays it with the
same engine functions the Model workspace uses:

* fundamental assumptions go through each family journal's ``edit_journal`` (material, energy, momentum,
  thermodynamics), starting from ``start`` (the fundamental law of the volume);
* equation operations go through ``core.modelo.equation_workbench.edit`` (append), or, for a generic
  single-volume script, through ``fundamental_report`` version 3, the blank-Model authoring path; the final
  state is read with ``describe_for_authoring``.

Readable names are mapped to engine identities at replay time: quantity names (``T__drum(t)``) to their
hashed quantity ids, step ids to ``operation.N``, and balance selectors to the engine's equation ids. Hashed
ids and input signatures always come from the engine. A step the engine refuses is reported as rejected with
the engine's message; steps that depend on it are skipped. Each rejection is a located Engine finding or an
error in the script.

    python tools/research/replay_deduction_script.py SCRIPT [--json OUT] [--compare RECORDED] [--write-model OUT]

See docs/engine/multiphysics-roadmap.md "Research dossiers" for the format.
"""
import argparse
import copy
import difflib
import json
import math
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import sympy as sp  # noqa: E402

from core.balances import material_derivation as material  # noqa: E402
from core.balances import energy_derivation as energy  # noqa: E402
from core.balances import momentum_derivation as momentum  # noqa: E402
from core.termodinamica import derivation as thermodynamics  # noqa: E402
from core.modelo import leer_modelo_comun  # noqa: E402
from core.modelo.operation_journal import JournalError, replay  # noqa: E402
from core.modelo import equation_workbench as workbench  # noqa: E402
from core.mathematics.contract import FORMAT as WORKBENCH_FORMAT  # noqa: E402

FORMAT = 'rage.deduction-script'
VERSION = 1
GENERIC_OWNER = 'dominio'

# family -> (model namespace, journal module, journal format, generic-report field)
JOURNALS = {
    'matter': ('materialDerivation', material, 'rage.material-derivation', 'materialJournal'),
    'energy': ('energyDerivation', energy, 'rage.energy-derivation', 'energyJournal'),
    'momentum': ('momentumDerivation', momentum, momentum.FORMAT, 'momentumJournal'),
    'thermodynamics': ('thermodynamicDerivation', thermodynamics, thermodynamics.FORMAT, 'thermodynamicJournal'),
}
# Fields of a script entry that describe it and never reach the engine.
DESCRIPTIVE = {'id', 'cite', 'note', 'family', 'volume', 'action', 'flag', 'value', 'kind', 'implied'}
EQUATION_REFERENCES = ('sources', 'relation', 'domains')
QUANTITY_REFERENCES = ('symbol', 'dependencies')
EXPRESSIONS = ('left', 'right', 'coefficient', 'potential', 'lower', 'upper', 'neighborSymbol')
HASHED = re.compile(r'\bx[0-9a-f]{10}\b')
TOKEN = re.compile(r'\{([^{}]+)\}|(?<![\w.])([A-Za-z_][A-Za-z0-9_]*)(\((?:\s*[A-Za-z_][A-Za-z0-9_]*\s*(?:,\s*[A-Za-z_][A-Za-z0-9_]*\s*)*)\))?')


class ScriptError(ValueError):
    """The script itself is malformed (not an engine finding)."""


# --------------------------------------------------------------------------- loading

def load_document(reference, base):
    """A physical-system document: an inline object, a JSON file or a generated TypeScript fixture."""
    if isinstance(reference, dict):
        return copy.deepcopy(reference)
    path = Path(reference)
    path = path if path.is_absolute() else base / path
    text = path.read_text(encoding='utf-8')
    if path.suffix == '.ts':
        text = text[text.index(' = ') + 3:text.rindex(';')]
    return json.loads(text)


def read_script(value):
    if not isinstance(value, dict) or value.get('format') != FORMAT:
        raise ScriptError('Not a rage.deduction-script document.')
    if value.get('version') not in (0, 1):
        raise ScriptError('Unsupported deduction-script version: %r.' % value.get('version'))
    for field in ('fundamentalAssumptions', 'steps'):
        if not isinstance(value.get(field, []), list):
            raise ScriptError(field + ' must be a list.')
    seen = set()
    for entry in value.get('fundamentalAssumptions', []) + value.get('steps', []):
        if not isinstance(entry, dict) or not isinstance(entry.get('id'), str) or not entry['id']:
            raise ScriptError('Every assumption and step needs a string id.')
        if entry['id'] in seen:
            raise ScriptError('Repeated id: ' + entry['id'])
        seen.add(entry['id'])
    return value


def strip_system(model):
    """Keep the physical system (species, volumes, streams, data, declarations); drop every recorded deduction.

    The derivation journals, the equation workbench, the Solve selection and the study are rebuilt or belong
    to later workspaces. Assumption states of journaled families are recomputed from the replayed journals.
    """
    model = copy.deepcopy(model)
    for key in ('materialDerivation', 'energyDerivation', 'momentumDerivation', 'thermodynamicDerivation',
                'equationWorkbench', 'derivedExecution'):
        model.get('motores', {}).pop(key, None)
    model['estudio'] = None
    return model


# --------------------------------------------------------------------------- names

class Names:
    """Readable quantity names <-> engine quantity ids, in the engine's own catalog order."""

    def __init__(self, quantities, declared, aliases=()):
        self.aliases = tuple(aliases)         # (compiled pattern, readable replacement) for generic scripts
        self.declared = set(declared)         # declared symbol/function names (ids equal to their names)
        self.engine = {id_: name for id_, name in quantities}
        self.readable = {id_: self.alias(name) for id_, name in quantities}
        # An alias must never make two different engine quantities read alike (one would shadow the other).
        # Such ids keep their engine spelling, and the shared alias is refused as ambiguous.
        spellings = {}
        for id_, name in quantities:
            spellings.setdefault(self.readable[id_], set()).add(name)
        self.ambiguous = {alias: sorted(names) for alias, names in spellings.items() if len(names) > 1}
        for id_, name in quantities:
            if self.readable[id_] in self.ambiguous:
                self.readable[id_] = name
        self.by_name = {}
        for id_, _ in quantities:             # engine catalog order: the first match wins, as in the engine
            self.by_name.setdefault(self.readable[id_], id_)

    def alias(self, name):
        for pattern, replacement in self.aliases:
            name = pattern.sub(replacement, name)
        return name

    @classmethod
    def from_report(cls, report, aliases=()):
        rows = report['quantities']
        declared = [row['id'] for row in rows if not HASHED.fullmatch(row['id'])]
        return cls([(row['id'], row['name']) for row in rows], declared, aliases)

    def quantity(self, text, where):
        text = text.strip()
        braced = text.startswith('{') and text.endswith('}')
        name = text[1:-1].strip() if braced else text
        if not braced and name in self.declared:
            return name
        if name in self.by_name:
            return self.by_name[name]
        if name in self.ambiguous:
            raise JournalError('Ambiguous name %r in %s: it reads as several engine quantities (%s); write the engine name.'
                               % (name, where, ', '.join(self.ambiguous[name])))
        close =difflib.get_close_matches(name, list(self.by_name), n=4, cutoff=0.6)
        raise JournalError('Unknown quantity %r in %s.%s' % (name, where, (' Close engine names: ' + ', '.join(close)) if close else ''))

    def expression(self, text):
        def swap(match):
            braced, ident, args = match.group(1), match.group(2), match.group(3)
            if braced is not None:
                return self.quantity('{' + braced + '}', 'an expression')
            if ident in self.declared:
                return match.group(0)
            if args is not None:
                compact = ident + '(' + ', '.join(a.strip() for a in args[1:-1].split(',')) + ')'
                if compact in self.by_name:
                    return self.by_name[compact]
            if ident in self.by_name:
                return self.by_name[ident] + (self.expression(args) if args else '')
            return match.group(0)
        return TOKEN.sub(swap, text)

    def to_readable_quantity(self, value):
        if not HASHED.fullmatch(value):
            return value
        name = self.readable[value]
        return name if self.quantity(name, 'conversion') == value else '{' + name + '}'

    def to_readable_expression(self, text):
        plain = HASHED.sub(lambda m: self.readable[m.group(0)], text)
        if self.expression(plain) == text:
            return plain
        braced = HASHED.sub(lambda m: '{' + self.readable[m.group(0)] + '}', text)
        if self.expression(braced) == text:
            return braced
        raise ScriptError('Cannot express %r with readable names unambiguously.' % text)


# --------------------------------------------------------------------------- sessions

class DocumentSession:
    """A concrete physical system: real species, several volumes, streams and data."""

    mode = 'document'
    aliases = ()

    def __init__(self, system):
        self.model = system
        self.model.setdefault('motores', {})
        # An equipment template record names the deduction journals as its recipe; it is published with the
        # finished deduction, so it is set aside until the steps have been replayed.
        self.template = self.model.pop('template', None)

    def finish(self):
        if self.template is not None:
            self.model['template'] = self.template
            self.template = None
            self.model = leer_modelo_comun(self.model)

    def owners(self):
        return [v['id'] for v in self.model['volumenes']]

    def journal(self, family):
        namespace, _, fmt, _ = JOURNALS[family]
        return self.model['motores'].get(namespace) or {'format': fmt, 'version': 1, 'volumes': {}}

    def assume(self, family, owner, action):
        namespace, module, _, _ = JOURNALS[family]
        if owner not in self.owners():
            raise JournalError('Unknown control volume %r.' % owner)
        journal = self.journal(family)
        if family == 'thermodynamics' and action.get('kind') == 'select_closure':
            volume = next(v for v in self.model['volumenes'] if v['id'] == owner)
            journal = module.edit_journal(journal, owner, action, thermodynamics.expected_closure(self.model, volume))
        else:
            journal = module.edit_journal(journal, owner, action)
        self.model['motores'][namespace] = journal

    def close_assumptions(self):
        """Recompute the assumption states that the journals determine, then validate the document."""
        for volume in self.model['volumenes']:
            owner = volume['id']
            entries = {family: self.model['motores'].get(JOURNALS[family][0], {}).get('volumes', {}).get(owner)
                       for family in JOURNALS}
            if entries['matter']:
                volume['supuestos']['materia'] = material.replay_volume(entries['matter'])[-1]
            if entries['energy']:
                state = replay(entries['energy'], energy.fundamental, energy.normalize)[-1]
                if entries['thermodynamics']:
                    closure = replay(entries['thermodynamics'], thermodynamics.fundamental, thermodynamics.normalize)[-1]
                    state = {**state, **{k: v for k, v in closure.items() if k != 'closure'}}
                volume['supuestos']['energia'] = state
        self.model = leer_modelo_comun(self.model)

    def report(self):
        return workbench.describe_for_authoring(self.model)

    def build(self):
        return workbench.build(self.model)

    def append(self, operation):
        report = workbench.edit(self.model, {'kind': 'append', 'operation': operation})
        self.model['motores']['equationWorkbench'] = report['definition']
        return report


class GenericSession:
    """One control volume with a generic component index i = 1..N (the blank-Model authoring path)."""

    mode = 'generic'

    def __init__(self, script):
        volumes = script.get('volumes') or [{'id': GENERIC_OWNER}]
        if len(volumes) != 1:
            raise ScriptError('A generic script has exactly one control volume; services are separate scripts (dec-composable-operations).')
        self.name = volumes[0].get('id', GENERIC_OWNER)
        self.journals = {}
        self.ports = []
        self.port_names = {}
        for index, stream in enumerate(script.get('streams', []), 1):
            if stream.get('direction') not in ('inlet', 'outlet'):
                raise ScriptError('Stream %r needs direction inlet or outlet.' % stream.get('id'))
            self.ports.append({'id': index, 'sentido': 'entrada' if stream['direction'] == 'inlet' else 'salida',
                               **({'constante': stream['constant']} if 'constant' in stream else {})})
            self.port_names[stream['id']] = 'puerto.' + str(index)
        self.definition = {'format': WORKBENCH_FORMAT, 'version': 1, 'operations': [], 'cursor': 0}
        self.model_id = script.get('operation') or 'research-script'
        # Engine spellings of the generic context -> the script's own names: the volume and its streams. The
        # material producer writes the unbound component index as None (read as i: q__feed__i(t) is the component
        # flow). Without declared species the energy and thermodynamic producers write their sum over components
        # with a stand-in index i (energy_equations: componenteIds or ['i']), a different engine identity: it reads
        # as sum (q__feed__sum(t) is the stream's total mass flow in the enthalpy balance, m__tank__sum(t) the
        # total inventory). The stand-in is renamed first, so the two can never shadow each other.
        self.aliases = tuple((re.compile(pattern), replacement) for pattern, replacement in [
            *[(re.escape(port) + r'(?![0-9])', stream) for stream, port in self.port_names.items()],
            (r'__' + GENERIC_OWNER + r'(?![A-Za-z0-9])', '__' + self.name),
            (r'__i(?![A-Za-z0-9_])', '__sum'), (r'__None(?![A-Za-z0-9])', '__i')])

    def owners(self):
        return [self.name]

    def assume(self, family, owner, action):
        if owner != self.name:
            raise JournalError('Unknown control volume %r.' % owner)
        _, module, fmt, _ = JOURNALS[family]
        if family == 'thermodynamics' and action.get('kind') == 'select_closure':
            raise JournalError('A generic volume has no configured package: select_closure needs declared species and a package (document mode).')
        if family == 'momentum' and action.get('kind') == 'bind_ports':
            action = {**action, **{k: self.port_names.get(v, v) for k, v in action.items() if k.endswith('StreamId')}}
        self.journals[family] = module.edit_journal(self.journals.get(family) or {'format': fmt, 'version': 1, 'volumes': {}},
                                                    GENERIC_OWNER, action)

    def close_assumptions(self):
        if 'matter' not in self.journals:
            raise JournalError('Start the component mass law first: the generic authoring path needs the material journal.')

    def _request(self):
        value = {'format': 'rage.fundamental-equations', 'version': 3, 'modelId': self.model_id,
                 'materialJournal': self.journals['matter']['volumes'][GENERIC_OWNER], 'ports': self.ports,
                 'definition': self.definition}
        for family in ('momentum', 'energy', 'thermodynamics'):
            if family in self.journals:
                value[JOURNALS[family][3]] = self.journals[family]
        return value

    def report(self):
        return workbench.fundamental_report(self._request())

    def finish(self):
        pass

    def build(self):
        """The same unbound context the blank-Model report replays (equation_workbench._unbound_report)."""
        engines = {JOURNALS[f][0]: j for f, j in self.journals.items()}
        streams = [{'id': 'puerto.' + str(p['id']), 'desde': GENERIC_OWNER if p['sentido'] == 'salida' else None,
                    'hasta': GENERIC_OWNER if p['sentido'] == 'entrada' else None, 'componenteIds': [],
                    **({'constante': p['constante']} if 'constante' in p else {})} for p in self.ports]
        state = material.replay_volume(self.journals['matter']['volumes'][GENERIC_OWNER])[-1]
        context = {'id': self.model_id, 'componentes': [], 'corrientes': streams, 'motores': engines,
                   'volumenes': [{'id': GENERIC_OWNER, 'componenteIds': [], 'supuestos': {'materia': state}}]}
        return workbench.build(context, self.definition, unbound=True)

    def append(self, operation):
        report = workbench.fundamental_report(self._request(), {'kind': 'append', 'operation': operation})
        self.definition = report['definition']
        return report


# --------------------------------------------------------------------------- replay

# Version 0 drafts name the assumption-state key a journal action sets (for example sinReaccion) instead of
# the action. The material journal computes its changes inside edit_journal, so its keys are listed here.
MATERIAL_FLAGS = {'sinReaccion': 'no_reaction', 'restoImpermeable': 'impermeable_remainder', 'sinAcumulacion': 'no_accumulation',
                  'fija': 'fixed_boundary', 'generacionUniforme': 'uniform_generation', 'consumoUniforme': 'uniform_consumption',
                  'sinDifusion': 'no_diffusion', 'sinConveccion': 'no_convection'}
MATERIAL_ACTIONS = set(MATERIAL_FLAGS.values()) | {'integrate', 'total', 'reaction_sources'}


def v0_flag_action(family, flag, value):
    """The journal action that sets a version-0 flag, or a ScriptError naming why none does."""
    if family == 'momentum':
        return {'kind': 'set_assumption', 'name': flag, 'value': value}
    module = JOURNALS[family][1]
    actions = MATERIAL_ACTIONS if family == 'matter' else set(module.CHOICES)
    keys = dict(MATERIAL_FLAGS) if family == 'matter' else {
        key: action for action, (_, changes) in module.CHOICES.items()
        for key, setting in changes.items() if len(changes) == 1 and setting is True}
    camel = re.sub(r'_([a-z])', lambda m: m.group(1).upper(), flag)
    if value is True and flag in actions:
        return {'kind': flag}
    if value is True and (flag in keys or camel in keys):
        return {'kind': keys.get(flag, keys.get(camel))}
    raise ScriptError('Version-0 flag %r = %r: no %s journal action sets it. Actions: %s.'
                      % (flag, value, family, ', '.join(sorted(actions))))


def assumption_action(entry):
    if 'flag' in entry:   # version 0 spelling
        return v0_flag_action(entry.get('family'), entry['flag'], entry.get('value', True))
    if not isinstance(entry.get('action'), str):
        raise ScriptError('Assumption %s needs an action (the journal action kind).' % entry['id'])
    extra = {k: v for k, v in entry.items() if k not in DESCRIPTIVE | {'reason', 'source'}}
    if entry['action'] == 'set_assumption':
        extra.update(name=entry['name'], value=entry.get('value', True))
    return {'kind': entry['action'], **extra}


def equation_reference(text, ids, session, names, where):
    if text in ids:
        return ids[text]
    if text.startswith('eq:'):
        return text[3:]
    if text.startswith('law:'):   # version 0: the single current balance of a family in a volume
        family, _, rest = text[4:].partition('.')
        owner = GENERIC_OWNER if session.mode == 'generic' else rest.split('.')[0]
        matches = [row for row in session.source_rows if row['id'].startswith(family + '.' + owner + '.') and row.get('current')
                   and str(row.get('_lhs', '')).startswith('Derivative(') and row.get('_rhs') not in ('0', '')]
        if len(matches) != 1:
            raise JournalError('%r names %d current %s balances (%s); use balance:%s.<volume>:<quantity> or eq:<id>.'
                               % (text, len(matches), family, '; '.join(names.alias(m['_lhs']) for m in matches) or 'none', family))
        return matches[0]['id']
    if text.startswith('balance:'):
        head, _, quantity = text[8:].partition(':')
        family, _, owner = head.partition('.')
        prefix = {'matter': 'matter.', 'energy': 'energy.', 'momentum': 'momentum.'}.get(family)
        if prefix is None or not owner or not quantity:
            raise JournalError('A balance selector reads balance:<matter|energy|momentum>.<volume>:<quantity>.')
        owner = GENERIC_OWNER if session.mode == 'generic' else owner
        rows = session.source_rows
        target = names.quantity(quantity, where)
        matches = [row['id'] for row in rows if row['id'].startswith(prefix + owner + '.') and row.get('current')
                   and row.get('_lhs') == ('Derivative(%s, t)' % names.engine.get(target, target)) and row.get('_rhs') != '0']
        if len(matches) != 1:
            raise JournalError('%d current %s balances of %r for %s (expected one).' % (len(matches), family, owner, quantity))
        return matches[0]
    raise JournalError('Unknown equation reference %r in %s (a step id, eq:<engine id> or balance:...).' % (text, where))


def translate(step, ids, session, names):
    operation = {'kind': step['kind'], 'family': step.get('family', 'matter')}
    where = 'step ' + step['id']
    for field, value in step.items():
        if field in DESCRIPTIVE:
            continue
        if field == 'source' and isinstance(value, str):   # version 0 citation spelling
            continue
        if field in EQUATION_REFERENCES:
            if field == 'relation':
                operation[field] = equation_reference(value, ids, session, names, where)
            else:
                operation[field] = [equation_reference(v, ids, session, names, where) for v in value]
        elif field in QUANTITY_REFERENCES:
            operation[field] = ([names.quantity(v, where) for v in value] if isinstance(value, list)
                                else names.quantity(value, where))
        elif field in EXPRESSIONS and isinstance(value, str):
            operation[field] = names.expression(value)
        else:
            operation[field] = copy.deepcopy(value)
    return operation


def references_of(step):
    refs = []
    for field in EQUATION_REFERENCES:
        value = step.get(field)
        refs.extend(value if isinstance(value, list) else [value] if value else [])
    return refs


def plain_rows(session):
    """Every equation as plain sympy text, from the engine's own replay."""
    graph = session.build().graph
    def sides(equation):
        if hasattr(equation, 'lhs'):
            return {'lhs': str(equation.lhs), 'rhs': str(equation.rhs)}
        return {'lhs': str(equation), 'rhs': ''}   # a domain or condition statement (for example Contains)
    return {key: sides(node.equation) for key, node in graph.nodes.items()}


def run(script, *, base=None, repository=ROOT, log=None, diagnostic=False):
    """Replay a script; return (report, session).

    diagnostic=True replays the steps on the accepted assumptions even after a rejection, to locate later
    findings; such a report is marked and never counts as an accepted replay.
    """
    script = read_script(script)
    base = Path(base or repository)
    started = time.time()
    out = {'format': 'rage.deduction-replay', 'version': 1, 'script': script.get('operation'),
           'scriptVersion': script['version'], 'assumptions': [], 'steps': [], 'findings': []}
    system = script.get('system') or {}
    if 'document' in system:
        root = repository if system.get('base', 'repository') == 'repository' else base
        session = DocumentSession(strip_system(load_document(system['document'], root)))
    else:
        session = GenericSession(script)
    out['mode'] = session.mode
    failed_volumes, started_journals = set(), set()
    entries = []
    for entry in script.get('fundamentalAssumptions', []):
        key = (entry.get('family'), entry.get('volume'))
        if script['version'] == 0 and key not in started_journals and entry.get('action') != 'start' and entry.get('family') in JOURNALS:
            # Version 0 drafts omit the fundamental law: start it, and say so in the report.
            entries.append({'id': entry['id'] + '.start', 'family': key[0], 'volume': key[1], 'action': 'start', 'implied': True})
        started_journals.add(key)
        entries.append(entry)
    for entry in entries:
        record = {'id': entry['id'], 'family': entry.get('family'), 'volume': entry.get('volume')}
        try:
            if entry.get('family') not in JOURNALS:
                raise ScriptError('Assumption %s: family must be one of %s.' % (entry['id'], ', '.join(JOURNALS)))
            if (entry.get('family'), entry.get('volume')) in failed_volumes:
                record.update(status='skipped', reason='an earlier assumption of this journal was rejected')
            else:
                action = assumption_action(entry)
                record['action'] = action
                session.assume(entry['family'], entry.get('volume'), action)
                record['status'] = 'accepted'
                if entry.get('implied'):
                    record['implied'] = 'version 0: start inserted before the first assumption of this journal'
        except (JournalError, ScriptError, material.MaterialDerivationError, KeyError, TypeError, ValueError) as error:
            record.update(status='rejected', error=str(error))
            failed_volumes.add((entry.get('family'), entry.get('volume')))
        out['assumptions'].append(record)
    rejected = [row for row in out['assumptions'] if row['status'] == 'rejected']
    if rejected and diagnostic:
        out['diagnostic'] = 'Steps replayed on the accepted assumptions only; rejected assumptions are missing from the laws.'
        for row in rejected:
            out['findings'].append({'assumption': row['id'], 'family': row['family'], 'volume': row['volume'], 'error': row['error']})
    elif rejected:
        # The steps act on the laws these assumptions produce; replaying them on a partial basis would only
        # report consequences of the first rejection.
        for row in rejected:
            out['findings'].append({'assumption': row['id'], 'family': row['family'], 'volume': row['volume'], 'error': row['error']})
        out['steps'] = [{'id': step.get('id'), 'kind': step.get('kind'), 'status': 'skipped',
                         'reason': 'fundamental assumptions rejected'} for step in script.get('steps', [])]
        out['summary'] = summary(out, started)
        return out, session
    try:
        session.close_assumptions()
        report = session.report()
    except Exception as error:   # the physical system or its journals are refused as a whole
        out['findings'].append({'where': 'fundamentalAssumptions', 'error': '%s: %s' % (type(error).__name__, error)})
        out['summary'] = summary(out, started)
        return out, session
    plain = plain_rows(session)
    session.source_rows = [{**row, '_lhs': plain.get(row['id'], {}).get('lhs'), '_rhs': plain.get(row['id'], {}).get('rhs')}
                           for row in report['equations']]
    names = Names.from_report(report, session.aliases)
    ids, blocked = {}, set()
    for index, step in enumerate(script.get('steps', [])):
        record = {'id': step['id'], 'kind': step.get('kind'), 'family': step.get('family', 'matter')}
        depends = [r for r in references_of(step) if r in blocked]
        if depends:
            record.update(status='skipped', reason='depends on ' + ', '.join(sorted(set(depends))))
            blocked.add(step['id'])
            out['steps'].append(record)
            continue
        try:
            if not isinstance(step.get('kind'), str):
                raise ScriptError('Step %s needs an operation kind.' % step['id'])
            operation = translate(step, ids, session, names)
            record['operation'] = operation
            report = session.append(operation)
        except (JournalError, ScriptError, KeyError, TypeError, ValueError, sp.SympifyError) as error:
            message = HASHED.sub(lambda m: names.readable.get(m.group(0), m.group(0)), str(error))
            record.update(status='rejected', error='%s: %s' % (type(error).__name__, message))
            blocked.add(step['id'])
            out['steps'].append(record)
            out['findings'].append({'step': step['id'], 'kind': step.get('kind'), 'error': record['error']})
            if log:
                log('rejected %s: %s' % (step['id'], record['error']))
            continue
        key = 'operation.' + str(report['definition']['cursor'])
        ids[step['id']] = key
        names = Names.from_report(report, session.aliases)
        row = next((r for r in report['equations'] if r['id'] == key), None)
        record.update(status='accepted', engineId=key, signatures=report['definition']['operations'][-1].get('sourceSignatures', {}))
        if row is not None:
            record['latex'] = row.get('latex')
        out['steps'].append(record)
        if log and (index + 1) % 20 == 0:
            log('%d/%d steps' % (index + 1, len(script['steps'])))
    try:
        session.finish()
    except Exception as error:
        out['findings'].append({'where': 'template', 'error': '%s: %s' % (type(error).__name__, error)})
    final = session.report()
    out['replay'] = final.get('replay')
    out['execution'] = final.get('execution')
    out['engineFindings'] = final.get('findings', [])
    out['ids'] = ids
    out['workingEquations'] = working_equations(script, session, ids, names)
    out['validation'] = [validate(case, session, ids, names) for case in script.get('validation', [])]
    out['summary'] = summary(out, started)
    return out, session


def working_equations(script, session, ids, names):
    plain = plain_rows(session)
    rows = []
    for result in script.get('results', []):
        key = ids.get(result.get('fromStep'), result.get('fromStep'))
        if isinstance(key, str) and key.startswith('eq:'):
            key = key[3:]
        row = plain.get(key)
        rows.append({'id': result.get('id'), 'fromStep': result.get('fromStep'), 'engineId': key,
                     'statement': result.get('statement'),
                     **({'equation': names.alias(row['lhs'] + (' = ' + row['rhs'] if row['rhs'] else ''))} if row else {'missing': True})})
    return rows


def validate(case, session, ids, names):
    """Evaluate one recorded working equation at the case inputs and solve it for the target quantity.

    The deduced algebra is checked, not a property package: closure values (densities, enthalpies) are inputs.
    """
    record = {'case': case.get('case'), 'equation': case.get('equation'), 'solveFor': case.get('solveFor')}
    if not all(field in case for field in ('equation', 'solveFor', 'expected')) or isinstance(case.get('expected'), dict):
        record.update(status='not executable', reason='not a version-1 case: name one working equation, the quantity to solve for and one expected value')
        return record
    try:
        from core.mathematics.dimensions import catalog
        replayed = session.build()
        key = ids.get(case['equation'], case['equation'])
        key = key[3:] if key.startswith('eq:') else key
        equation = replayed.graph.nodes[key].equation
        quantities = {**catalog(replayed.graph, replayed.units), **replayed.introduced}
        def lookup(name):
            derivative = re.fullmatch(r'Derivative\((.+), *([A-Za-z_]\w*)\)', name.strip())
            if derivative and name.strip() not in names.by_name:
                return sp.Derivative(lookup(derivative.group(1)), lookup(derivative.group(2)))
            return quantities[names.quantity(name, 'validation ' + str(case.get('case')))]
        target = lookup(case['solveFor'])
        replacements = {lookup(name): sp.Float(value) for name, value in case.get('inputs', {}).items()}
        derivatives = {k: v for k, v in replacements.items() if isinstance(k, sp.Derivative)}
        expression = (equation.lhs - equation.rhs).xreplace({target: sp.Symbol('__target__')})
        expression = expression.subs(derivatives).subs({k: v for k, v in replacements.items() if k not in derivatives})
        expression = expression.doit()
        unknown = sorted(str(s) for s in expression.free_symbols if str(s) != '__target__') + \
            sorted(str(f) for f in expression.atoms(sp.core.function.AppliedUndef))
        if unknown:
            record.update(status='not executable', reason='missing inputs: ' + ', '.join(unknown))
            return record
        solutions = [s for s in sp.solve(expression, sp.Symbol('__target__')) if s.is_real]
        if len(solutions) != 1:
            record.update(status='failed', reason='%d real solutions for %s' % (len(solutions), case['solveFor']))
            return record
        computed = float(solutions[0])
        expected = float(case['expected'])
        tolerance = case.get('tolerance', {'relative': 1e-9})
        error = abs(computed - expected)
        limit = tolerance.get('absolute', 0.0) + tolerance.get('relative', 0.0) * abs(expected)
        record.update(computed=computed, expected=expected, error=error, tolerance=tolerance,
                      status='passed' if error <= limit else 'failed')
    except Exception as error:
        record.update(status='failed', reason='%s: %s' % (type(error).__name__, error))
    return record


def summary(out, started):
    count = lambda rows, status: sum(1 for r in rows if r.get('status') == status)
    return {'assumptions': {s: count(out['assumptions'], s) for s in ('accepted', 'rejected', 'skipped')},
            'steps': {s: count(out['steps'], s) for s in ('accepted', 'rejected', 'skipped')},
            'validation': {s: count(out.get('validation', []), s) for s in ('passed', 'failed', 'not executable')},
            'seconds': round(time.time() - started, 1)}


# --------------------------------------------------------------------------- comparison with a recorded model

def compare(session, recorded):
    """Prove that the replay reproduces a recorded model: journals, workbench operations and equation signatures."""
    from core.mathematics.provenance import equation_signature
    from core.compilador.derived import source_signature
    rebuilt = session.model
    checks = []
    for family, (namespace, _, _, _) in JOURNALS.items():
        checks.append(('journal ' + namespace, rebuilt['motores'].get(namespace) == recorded['motores'].get(namespace)))
    for volume, original in zip(rebuilt['volumenes'], recorded['volumenes']):
        checks.append(('assumption states ' + volume['id'], volume['supuestos'] == original['supuestos']))
    ours, theirs = rebuilt['motores'].get('equationWorkbench'), recorded['motores'].get('equationWorkbench')
    checks.append(('workbench operations (with input signatures)', ours == theirs))
    a, b = workbench.build(rebuilt), workbench.build(recorded)
    sa = {k: equation_signature(a.graph, k, a.units, workbench._known_unit) for k in a.graph.nodes}
    sb = {k: equation_signature(b.graph, k, b.units, workbench._known_unit) for k in b.graph.nodes}
    differing = sorted(k for k in set(sa) | set(sb) if sa.get(k) != sb.get(k))
    checks.append(('equation signatures (%d equations)' % len(sb), not differing))
    pinned = recorded['motores'].get('derivedExecution', {}).get('sourceSignature')
    signature = source_signature(rebuilt, a)
    checks.append(('source signature', signature == source_signature(recorded, b)))
    if pinned:
        checks.append(('source signature pinned by the recorded Solve selection', signature == pinned))
    return {'checks': [{'check': name, 'equal': bool(ok)} for name, ok in checks],
            'differingEquations': differing[:20], 'equal': all(ok for _, ok in checks)}


def text_report(out):
    lines = ['Replay of %s (%s mode)' % (out.get('script'), out.get('mode'))]
    s = out['summary']
    lines.append('assumptions: %(accepted)d accepted, %(rejected)d rejected, %(skipped)d skipped' % s['assumptions'])
    lines.append('steps:       %(accepted)d accepted, %(rejected)d rejected, %(skipped)d skipped' % s['steps'])
    for row in out['assumptions'] + out['steps']:
        if row.get('status') != 'accepted':
            lines.append('  %-10s %-8s %s' % (row['id'], row['status'], row.get('error') or row.get('reason', '')))
    for finding in out['findings']:
        if 'where' in finding:
            lines.append('  %s: %s' % (finding['where'], finding['error']))
    for row in out.get('workingEquations', []):
        lines.append('result %s (%s -> %s): %s' % (row['id'], row['fromStep'], row['engineId'], row.get('equation', 'missing')))
    for case in out.get('validation', []):
        lines.append('validation %s: %s %s' % (case['case'], case['status'],
                     ('computed %.12g expected %.12g' % (case['computed'], case['expected'])) if 'computed' in case else case.get('reason', '')))
    if 'comparison' in out:
        for check in out['comparison']['checks']:
            lines.append('compare %-55s %s' % (check['check'], 'equal' if check['equal'] else 'DIFFERENT'))
    lines.append('%.1f s' % s['seconds'])
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('script')
    parser.add_argument('--json', help='write the full replay report here')
    parser.add_argument('--compare', help='recorded model (.json or generated .ts fixture) to compare with')
    parser.add_argument('--write-model', help='write the rebuilt model document here (document mode)')
    parser.add_argument('--diagnostic', action='store_true', help='replay the steps even after a rejected assumption')
    args = parser.parse_args(argv)
    path = Path(args.script).resolve()
    script = json.loads(path.read_text(encoding='utf-8'))
    out, session = run(script, base=path.parent, log=lambda m: print(m, file=sys.stderr), diagnostic=args.diagnostic)
    if args.compare and session.mode == 'document':
        out['comparison'] = compare(session, load_document(args.compare, Path.cwd()))
    if args.write_model and session.mode == 'document':
        Path(args.write_model).write_text(json.dumps(session.model, indent=1, ensure_ascii=False, sort_keys=True), encoding='utf-8')
    if args.json:
        Path(args.json).write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding='utf-8')
    print(text_report(out))
    ok = not out['findings'] and all(c['status'] != 'failed' for c in out.get('validation', []))
    if 'comparison' in out:
        ok = ok and out['comparison']['equal']
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
