"""Package thermodynamic closures in derived execution (FD-1 to FD-4, F5-C2).

A volume whose Thermodynamics journal recorded `select_closure` keeps its
balances as selected Transform rows. The package closure is a constitutive
mapping, not a symbolic reconstruction: at every RHS evaluation, including
BDF Jacobian probes and event probes, it receives the component amounts, the
energy inventory and the declared mechanical datum, and returns T, P or V and
the instantiated per-phase quantities of the thermodynamic graph. The values
come only from `core.termodinamica.derived_bridge`; nothing here evaluates a
property. Closure outputs are appended to the evaluated vector exactly like
the retained algebraic block; they are never integrated as states.
"""
import math

import numpy as np
import sympy as sp
from scipy.optimize import brentq

from core.mathematics.constants import UnitBasis, si_magnitude
from core.modelo.operation_journal import replay
from core.solvers import Detencion
from core.termodinamica import derivation as thermo_journal
from core.termodinamica import derived_bridge as bridge
from core.termodinamica.equations import closure_outputs, closure_phases
from .derived_graph import LoweringError
from .explicito import SistemaExplicito
from .compilador import temporal_method

ANCHORS = {None: None, 'gas': 'gas', 'liquido': 'liquid'}
RUNTIME_CODES = ('OUT_OF_DOMAIN', 'NOT_CONVERGED', 'UNSUPPORTED_STATE')
T_INITIAL_TOLERANCE = 1e-9   # K, initial temperature datum reproduced by the closure


def _phase_kind(phase):
    return 'vapor' if phase.kind == 'vapor' else 'liquid'


class PackageClosure:
    """One volume's recorded package closure, lowered for derived execution."""

    def __init__(self, system, volume):
        self.system = system
        self.owner = owner = volume['id']
        model = system.model
        entry = model['motores'].get('thermodynamicDerivation', {}).get('volumes', {}).get(owner)
        state = replay(entry, thermo_journal.fundamental, thermo_journal.normalize)[-1] if entry else None
        if state is None or state['closure'] is None:
            raise LoweringError('unrecorded_closure', 'Record the package selection in the Thermodynamics journal before executing an equilibrium volume.')
        closure = state['closure']
        package = next(p for p in model['termodinamica']['paquetes'] if p['id'] == closure['packageId'])
        if package.get('datosPuros'):
            raise LoweringError('unsupported_substitution', 'Derived execution evaluates the published package data only; pure-data substitutions need another closure adapter.')
        self.package = package['modelo']['id']
        if bridge.PACKAGE_ALIASES.get(self.package, self.package) not in bridge.PACKAGES:
            raise LoweringError('unsupported_package', 'Derived execution supports ' + ', '.join(bridge.PACKAGES) + '; ' + self.package + ' needs another closure adapter.')
        components = {c['id']: c for c in model['componentes']}
        self.components = volume['componenteIds']
        self.species = [components[i].get('identidadQuimica', {}).get('cas') for i in self.components]
        if not all(isinstance(cas, str) and cas for cas in self.species):
            raise LoweringError('missing_chemical_identity', 'Each component of a package volume needs its CAS identity.')
        self.policy = closure['policy']
        self.liquid_only = bool(state.get('soloLiquido'))
        from core.catalogo import REGISTRO_SOLO_LIQUIDO
        restricted = [cas for cas in self.species if cas in REGISTRO_SOLO_LIQUIDO]
        if restricted and not self.liquid_only:
            error = LoweringError('liquid_only_species', ', '.join(restricted) + ' is admitted only in a liquid phase: record the liquid-only '
                                  'Thermodynamics assumption (with the single-phase liquid policy) before using it in volume ' + owner + '.')
            error.diagnostics[0]['detail'] = {'tipo': 'fase_vapor', 'operacion': 'vapour_liquid_package', 'nativeCode': 'ESPECIE_SOLO_LIQUIDO', 'cas': restricted}
            raise error
        self.anchor = ANCHORS[state.get('referenciaFormacion')]
        self.phases = closure_phases(state, closure)
        self.single = self.policy['cantidad'] == 'monofasico'
        if self.single:
            kinds = self.policy.get('tiposPermitidos') or []
            if len(kinds) != 1 or kinds[0] not in ('liquido', 'vapor'):
                raise LoweringError('single_phase_kind_required', 'A single-phase package closure needs exactly one permitted phase type (liquid or vapour).')
            self.kind = 'liquid' if kinds[0] == 'liquido' else 'vapor'
            self.phases = ('L',) if self.kind == 'liquid' else ('V',)
        elif self.liquid_only:
            raise LoweringError('liquid_only_policy', 'A liquid-only volume requires the single-phase liquid policy.')
        t = system.time
        q = lambda name: sp.Function(name + '__' + owner)(t)
        self.T, self.P, self.V, self.U, self.H = q('T'), q('P'), q('V'), q('U'), q('H')
        self.amounts = [sp.Function('n_' + str(i) + '__' + owner)(t) for i in self.components]
        self.molar_mass_symbols = [sp.Symbol('molar_mass_' + str(i) + '__' + owner, real=True) for i in self.components]
        from core.mezclas_datos import especie
        try:
            self.molar_masses = [float(especie(cas).M) for cas in self.species]
        except Exception as error:   # the package rejects unknown species below with its own code
            raise LoweringError('unsupported_package', 'The package has no pure data for a declared species: ' + str(error)) from error
        bound = set(system.parameter_symbols)
        if self.P in bound and self.V in bound and not self.single:
            raise LoweringError('closure_specification', 'Bind either pressure (prescribed-pressure volume) or volume (rigid volume), not both.')
        if self.single:
            if self.P not in bound:
                raise LoweringError('closure_specification', 'A single-phase package closure needs the declared pressure.')
            self.spec = 'UV' if self.V in bound else 'PH'
        elif self.P in bound:
            self.spec = 'PH'
        elif self.V in bound:
            self.spec = 'UV'
        else:
            raise LoweringError('closure_specification', 'Bind the prescribed pressure or the rigid volume of the package volume to its datum.')
        self.energy = self.H if self.spec == 'PH' else self.U
        self.mechanical = self.P if self.spec == 'PH' or self.single else self.V
        out = closure_outputs(owner, self.components, self.phases)
        self.output_map = []   # (quantity, extractor key)
        self.output_map.append((self.T, ('T',)))
        if self.spec == 'PH':
            self.output_map.append((self.V, ('V',)))
        elif not self.single:
            self.output_map.append((self.P, ('P',)))   # rigid volume: the vapour sets the pressure
        for label in self.phases:
            for name in ('amount', 'h', 'u', 'v', 'M', 'present'):
                self.output_map.append((out[name, label], (name, label)))
            for index, i in enumerate(self.components):
                self.output_map.append((out['x', i, label], ('x', label, index)))
        if 'L' in self.phases:
            self.output_map.append((out['liquid_volume'], ('liquid_volume',)))
        self.outputs = [quantity for quantity, _ in self.output_map]
        self.constants = dict(zip(self.molar_mass_symbols, self.molar_masses))
        self.inlets = {}
        for stream in model['corrientes']:
            if stream['hasta'] == owner and stream['desde'] is None and stream.get('estadoExterior'):
                self.inlets[stream['id']] = self._inlet(stream, out)
        self.seed = None
        self.indicators = None
        self.cache = {}
        self.evaluations = 0
        self.fingerprint = None
        self.initial_signature = None

    # --- admission --------------------------------------------------------------------------------
    def _call(self, function, *args, stage, **kwargs):
        try:
            return function(*args, **kwargs)
        except bridge.DerivedThermoError as error:
            if stage == 'runtime' and error.code in RUNTIME_CODES:
                stop = Detencion('closure_' + error.code.lower(), 'Volume ' + self.owner + ': ' + error.message)
                stop.diagnostics = [{'code': 'closure_' + error.code.lower(), 'volumeId': self.owner, 'detail': {k: str(v) for k, v in error.detail.items()}}]
                raise stop from error
            raise LoweringError('closure_' + error.code.lower(), 'Volume ' + self.owner + ': ' + error.message) from error

    def _inlet(self, stream, out):
        """Package enthalpy of an inlet at its declared exterior state (F5-C2 feed enthalpy)."""
        system = self.system
        exterior = stream['estadoExterior']
        T = float(system._datum(exterior['temperaturaId'], {'Theta': 1}))
        pressure = exterior.get('presion') or {}
        if pressure.get('tipo') == 'dato':
            P = float(system._datum(pressure['datoId'], {'M': 1, 'L': -1, 'T': -2}))
        else:
            raise LoweringError('unsupported_inlet_state', 'Declare the inlet pressure as a datum; pressure continuity needs the volume closure.')
        composition = exterior.get('composicion') or {}
        fractions = composition.get('fracciones') or {}
        try:
            values = np.array([float(fractions[str(i)]) for i in self.components])
        except (KeyError, TypeError, ValueError) as error:
            raise LoweringError('missing_inlet_composition', 'Declare one exterior fraction per volume component.') from error
        if not np.all(np.isfinite(values)) or np.any(values < 0) or not math.isclose(values.sum(), 1, abs_tol=1e-10):
            raise LoweringError('invalid_inlet_composition', 'Exterior fractions must be finite, nonnegative and sum to one.')
        M = np.array(self.molar_masses)
        z = values if composition.get('base') == 'molar' else (values / M) / (values / M).sum()
        result = None
        for kind in ('liquid', 'vapor'):
            if self.liquid_only and kind == 'vapor':
                continue
            caloric = self._call(bridge.phase_caloric, self.package, self.species, T, P, list(z), phase=kind,
                                 anchor=self.anchor, liquid_only=self.liquid_only, stage='admission')
            check = self._call(bridge.phase_temperature, self.package, self.species, list(z), P, caloric['H'], quantity='H',
                               phase=kind, anchor=self.anchor, liquid_only=self.liquid_only, stage='admission')
            if check['single_phase_stable'] and abs(check['T'] - T) <= 1e-6:
                result = (kind, caloric)
                break
        if result is None:
            raise LoweringError('two_phase_inlet_unsupported', 'Inlet ' + stream['id'] + ' is not a stable single phase at its declared state; a two-phase inlet needs its enthalpy datum through a closure.')
        kind, caloric = result
        Mz = float(z @ M)
        values = {out['stream_h', stream['id']]: caloric['H'], out['stream_M', stream['id']]: Mz,
                  out['stream_hm', stream['id']]: caloric['H'] / Mz}
        for index, i in enumerate(self.components):
            values[out['stream_w', stream['id'], i]] = float(z[index] * M[index] / Mz)
        return {'phase': kind, 'T': T, 'P': P, 'z': z.tolist(), 'values': values, 'fingerprint': caloric['fingerprint']}

    def bind_inputs(self):
        """Express the closure inputs in retained states and data; outputs must not feed back."""
        system = self.system
        forbidden = set(system.closure_quantities)
        self.input_expressions = []
        for quantity in [*self.amounts, self.energy, self.mechanical]:
            value = system._expand(quantity)
            bad = value.atoms(sp.core.function.AppliedUndef) - set(system.states) - set(system.parameter_symbols.values())
            if value.has(*forbidden) or bad:
                raise LoweringError('closure_input_unresolved', 'Select reconstructions that express the closure input ' + str(quantity) +
                                    ' in retained states and data (for example the package amount from the component mass).')
            self.input_expressions.append(value)

    def initial_outputs(self, initial):
        """Closure outputs at the initial data, for the signs of nonzero conditions."""
        values = [numeric_value(self.system, e, initial) for e in self.input_expressions]
        if None in values:
            raise LoweringError('missing_initialization', 'The initial closure inputs of ' + self.owner + ' are not determined.')
        n, energy, mechanical = values[:len(self.amounts)], values[-2], values[-1]
        row, _ = self._single(n, energy, mechanical, 'initialization') if self.single else self._equilibrium(n, energy, mechanical, 'initialization')
        return {q: sp.Float(float(v), 17) for q, v in zip(self.outputs, row)}

    def compile(self, evaluator):
        self.inputs = [evaluator(system_ast) for system_ast in (self.system._ast(e) for e in self.input_expressions)]

    # --- evaluation -------------------------------------------------------------------------------
    def _inputs(self, t, y):
        values = [float(f(t, y)) for f in self.inputs]
        n = values[:len(self.amounts)]
        return n, values[-2], values[-1]

    def evaluate(self, t, y, stage='runtime'):
        key = (float(t), np.asarray(y, dtype=float).tobytes())
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        n, energy, mechanical = self._inputs(t, y)
        if not all(math.isfinite(v) and v >= 0 for v in n) or not sum(n) > 0:
            stop = Detencion('closure_invalid_amounts', 'Volume ' + self.owner + ': the package amounts must be nonnegative with a positive total.')
            if stage == 'runtime':
                raise stop
            raise LoweringError(stop.codigo, stop.mensaje)
        self.evaluations += 1
        if self.single:
            result = self._single(n, energy, mechanical, stage)
        else:
            result = self._equilibrium(n, energy, mechanical, stage)
        if len(self.cache) > 4096:
            self.cache.clear()
        self.cache[key] = result
        return result

    def _single(self, n, energy, P, stage):
        quantity = 'H' if self.spec == 'PH' else 'U'
        r = self._call(bridge.phase_temperature, self.package, self.species, n, P, energy, quantity=quantity, phase=self.kind,
                       anchor=self.anchor, liquid_only=self.liquid_only, stage=stage)
        if not r['single_phase_stable']:
            message = 'Volume ' + self.owner + ': the declared single ' + self.kind + ' phase is not stable at T = %.6g K (minimum tm %.3g); the policy no longer holds.' % (r['T'], r['stability'] if isinstance(r['stability'], float) else float('nan'))
            if stage == 'runtime':
                raise Detencion('politica_incumplida', message)
            raise LoweringError('invalid_initial_domain', message)
        N = float(sum(n))
        label = self.phases[0]
        M = float(np.dot(n, self.molar_masses) / N)
        phase = {'amount': N, 'h': r['H'] / N, 'u': r['U'] / N, 'v': r['V'] / N, 'M': M, 'present': 1.,
                 'x': [v / N for v in n]}
        values = {'T': r['T'], 'V': r['V'], 'phases': {label: phase}, 'liquid_volume': r['V'] if label == 'L' else 0.,
                  'certificate': {'residual': abs(float(r['residual'])), 'scale': max(abs(energy), 1.), 'certified': True},
                  'phase_set': (('liquido-1',) if label == 'L' else ('vapor-1',)), 'state': None}
        self.fingerprint = r['fingerprint']
        return self._vector(values, N, n)

    def _equilibrium(self, n, energy, mechanical, stage):
        a, b = (mechanical, energy) if self.spec == 'PH' else (energy, mechanical)
        try:
            state = bridge.close_state(self.package, self.species, n, self.spec, a, b, anchor=self.anchor,
                                       seed=self.seed, liquid_only=self.liquid_only)
        except bridge.DerivedThermoError:
            # A seed only changes the cost: retry the unseeded package closure.
            state = self._call(bridge.close_state, self.package, self.species, n, self.spec, a, b,
                               anchor=self.anchor, liquid_only=self.liquid_only, stage=stage)
        liquids = [p for p in state.phases if p.kind == 'liquid']
        if len(liquids) > 1:
            message = 'Volume ' + self.owner + ': the package state has two liquid phases; per-phase quantities of derived execution cover one vapour and one liquid.'
            if stage == 'runtime':
                raise Detencion('unsupported_phase_set', message)
            raise LoweringError('unsupported_phase_set', message)
        self.seed = state
        self.fingerprint = state.fingerprint
        N = float(sum(n))
        phases = {}
        for p in state.phases:
            phases['V' if p.kind == 'vapor' else 'L'] = {'amount': p.amount, 'h': p.h, 'u': p.u, 'v': p.v, 'M': p.M,
                                                         'present': 1., 'x': list(p.x)}
        checks = state.certificate['checks']
        ratio = max([c['residual'] / c['tolerance'] for c in checks.values() if c['tolerance'] > 0] or [0.])
        values = {'T': state.T, 'P': state.P, 'V': state.V, 'phases': phases, 'liquid_volume': state.liquid_volume,
                  'certificate': {'ratio': ratio, 'certified': state.certificate['certified']},
                  'phase_set': state.phase_set, 'state': state}
        return self._vector(values, N, n)

    def _vector(self, values, N, n):
        # Absent phases carry zero amount, presence and properties; their molar
        # mass is the overall one so that per-mass ratios stay finite while every
        # drawn flow is multiplied by the zero presence indicator.
        overall = float(np.dot(n, self.molar_masses) / N)
        absent = {'amount': 0., 'h': 0., 'u': 0., 'v': 0., 'M': overall, 'present': 0., 'x': [0.] * len(n)}
        row = []
        for _, key in self.output_map:
            if key[0] in ('T', 'P', 'V', 'liquid_volume'):
                row.append(float(values[key[0]]))
            elif key[0] == 'x':
                row.append(float(values['phases'].get(key[1], absent)['x'][key[2]]))
            else:
                row.append(float(values['phases'].get(key[1], absent)[key[0]]))
        return np.array(row), values

    # --- initialization ---------------------------------------------------------------------------
    def initial_energy(self, n, mechanical, temperature):
        """Energy inventory whose closure reproduces the initial temperature datum."""
        quantity = 'H' if self.spec == 'PH' else 'U'
        if self.single:
            r = self._call(bridge.phase_caloric, self.package, self.species, temperature, mechanical, n, phase=self.kind,
                           anchor=self.anchor, liquid_only=self.liquid_only, stage='initialization')
            return r[quantity]
        # T(E) is increasing at fixed amounts and P (or V): bracket the datum from
        # the liquid caloric value and solve with the closure itself.
        def temperature_of(E):
            a, b = (mechanical, E) if self.spec == 'PH' else (E, mechanical)
            state = self._call(bridge.close_state, self.package, self.species, n, self.spec, a, b, anchor=self.anchor,
                               liquid_only=self.liquid_only, stage='initialization')
            return state.T - temperature
        pressure = mechanical if self.spec == 'PH' else 1e5
        liquid = self._call(bridge.phase_caloric, self.package, self.species, temperature, pressure, n, phase='liquid',
                            anchor=self.anchor, liquid_only=self.liquid_only, stage='initialization')
        E = liquid[quantity]
        capacity = liquid['dH_dT' if quantity == 'H' else 'dU_dT']
        low = temperature_of(E)
        if abs(low) <= T_INITIAL_TOLERANCE:
            return E
        step = -capacity * low
        for _ in range(60):
            other = E + step
            high = temperature_of(other)
            if abs(high) <= T_INITIAL_TOLERANCE:
                return other
            if low * high < 0:
                return brentq(temperature_of, min(E, other), max(E, other), xtol=1e-12 * max(abs(E), 1.), rtol=1e-15, maxiter=200)
            E, low, step = other, high, 2 * step
        raise LoweringError('invalid_initialization', 'No equilibrium state at the declared initial temperature.')

    # --- events -----------------------------------------------------------------------------------
    def event_margins(self, t, y):
        _, values = self.evaluate(t, y)
        if self.single or values['state'] is None:
            return values['phase_set'], []
        indicators = bridge.phase_indicators(values['state'], self.indicators)
        self.indicators = indicators
        margins = [None if row['value'] is None else abs(float(row['value'])) for row in indicators['event_functions']]
        return values['phase_set'], margins

    def admits(self, phase_set):
        kinds = ['vapor' if p.startswith('vapor') else 'liquido' for p in phase_set]
        if self.policy['cantidad'] == 'monofasico' and len(phase_set) > 1:
            return 'Volume ' + self.owner + ': the policy requires a single phase, but the state has ' + ', '.join(phase_set)
        if self.policy['cambioInterno'] == 'prohibido' and self.initial_signature is not None and tuple(phase_set) != self.initial_signature:
            return 'Volume ' + self.owner + ': internal phase changes are forbidden, but the phase set changes to ' + ', '.join(phase_set)
        allowed = self.policy.get('tiposPermitidos')
        if allowed and any(kind not in allowed for kind in kinds):
            return 'Volume ' + self.owner + ': a phase outside the permitted types appears (' + ', '.join(phase_set) + ')'
        if kinds.count('liquido') > 1:
            return 'Volume ' + self.owner + ': two liquid phases; derived per-phase quantities cover one vapour and one liquid'
        return None

    def describe(self):
        return {'volumeId': self.owner, 'package': self.package, 'species': self.species, 'mode': 'single_phase' if self.single else 'equilibrium',
                'specification': self.spec, 'anchor': self.anchor, 'liquidOnly': self.liquid_only, 'candidatePhases': list(self.phases),
                'fingerprint': self.fingerprint, 'evaluations': self.evaluations,
                'inlets': {key: {k: v for k, v in row.items() if k != 'values'} for key, row in self.inlets.items()},
                'source': 'core.termodinamica.derived_bridge'}


class ClosureRuntime:
    """The existing AST evaluator over states, budgets and closure outputs."""

    def __init__(self, system):
        self.system = system
        self.campos = [system.ids[q] for q in system.states] + ['budget_' + str(i) for i in range(len(system.checks))]
        self.evaluator = SistemaExplicito.__new__(SistemaExplicito)
        self.evaluator.tiempo = system.ids[system.time]
        self.evaluator.indice = {key: i for i, key in enumerate(self.campos)}
        self.evaluator.valores = {system.ids[q]: float(value) for q, value in system.parameter_values.items()}
        self.evaluator.valores.update({identity: 1. for q, identity in system.ids.items() if isinstance(q, UnitBasis)})
        for closure in system.closures:
            closure.compile(lambda tree: self.evaluator._compilar(tree, 'closure input'))
        self.outputs = {system.ids[q] for q in system.closure_quantities}
        self.evaluator.indice.update({system.ids[q]: len(self.campos) + i for i, q in enumerate(system.closure_quantities)})
        self.indice = self.evaluator.indice
        self.f = [self.evaluator._compilar(system._ast(e), 'package closure formulation')
                  for e in [*system.rates.values(), *(rate for _, _, rate, _ in system.checks)]]
        self.observables = [(row['quantityId'], str(system._quantity(row['quantityId'])), system._unit(system._quantity(row['quantityId'])),
                             self._compilar(system._ast(expr), 'reconstruction')) for row, expr in system.reconstructed]
        self.dominios = [(self._compilar(system._ast(expr), 'condition'), label) for expr, _, _, label in system.margins]
        study = system.model['estudio']
        self.tf = float(system._datum(study['tiempoId'], {'T': 1}))
        self.metodo = temporal_method(study['metodoSolicitado'])
        dims = [system._dim(q) for q in system.states] + [system._dim(inventory) for _, inventory, _, _ in system.checks]
        a = study['atol']
        self.atol = np.array([a.get('energia', a['cantidad']) if dim == {'M': 1, 'L': 2, 'T': -2} else a['cantidad'] for dim in dims])

    def _uses(self, e):
        return isinstance(e, dict) and (e.get('tipo') == 'simbolo' and e.get('id') in self.outputs or any(self._uses(v) for v in e.values())) or isinstance(e, list) and any(self._uses(v) for v in e)

    def _compilar(self, expression, label):
        function = self.evaluator._compilar(expression, label)
        if not self._uses(expression):
            return function
        def evaluate(t, state):
            return function(t, np.concatenate([state, self.system.closure_values(t, state)]))
        return evaluate

    def inicial(self):
        return np.array([float(self.system.initial_values[q]) for q in self.system.states] + [0.] * len(self.system.checks))

    def rhs(self, t, state):
        extended = np.concatenate([state, self.system.closure_values(t, state)])
        return np.array([f(t, extended) for f in self.f], dtype=float)

    def dominio(self, t, state):
        return np.array([f(t, state) for f, _ in self.dominios])

    def describir_dominio(self, index):
        return self.dominios[index][1]


def numeric_value(system, expression, initial):
    value = si_magnitude(system._expand(expression)).xreplace(initial)
    return float(value) if value.is_number is True else None


def reaction_limit(system, closure, times, values):
    """F5-C3: the final kinetic state against the certified chemical equilibrium at the same T, P and inventory.

    Calls core.reactions.chemical_equilibrium (evaluate_reactions, certify_reactions, solve_extents) with the
    volume's package phase and formation reference; it never equilibrates the integrated state itself.
    """
    from core import mezclas
    from core.reactions import chemical_equilibrium as ce
    config = system.model['motores']['kineticReactions']['volumes'][closure.owner]
    NU = np.array([[float(sp.Rational(reaction['stoichiometry'].get(str(i), '0'))) for i in closure.components]
                   for reaction in config['reactions']])
    n0, _, _ = closure._inputs(times[0], values[0])
    n, _, mechanical = closure._inputs(times[-1], values[-1])
    _, final = closure.evaluate(times[-1], values[-1], 'publication')
    temperature = float(final['T'])
    pressure = float(mechanical if closure.single or closure.spec == 'PH' else final['P'])
    kind = 'liquido' if (closure.single and closure.kind == 'liquid') or closure.liquid_only else None
    if kind is None:
        raise LoweringError('unsupported_reaction_phase', 'The equilibrium-limit check covers single-phase package volumes.')
    provider = ce.PackagePhase(mezclas.Sistema(bridge.PACKAGE_ALIASES.get(closure.package, closure.package), closure.species,
                                               solo_liquido=closure.liquid_only), kind, anchor=closure.anchor)
    # The model's declared element rows (charge rows included), the same ones the kinetic admission checked.
    A = np.array([[float(sp.Rational(str(row.get(str(i), 0)))) for i in closure.components] for row in config['elements'].values()])
    state = ce.evaluate_reactions(provider, NU, T=temperature, P=pressure, n=n, phase_id=kind, standard_state=ce.STANDARD_STATES[kind])
    certificate = ce.certify_reactions(state, n0=n0, A=A)
    equilibrium = ce.solve_extents(provider, NU, n0, temperature, pressure, A)
    enthalpy = bridge.reaction_enthalpy(closure.package, closure.species, NU, temperature, pressure, phase='liquid', n=n,
                                        anchor=closure.anchor, liquid_only=closure.liquid_only)
    distance = float(np.max(np.abs(np.asarray(n) - np.asarray(equilibrium['moles']))) / max(float(np.sum(n0)), 1e-300))
    detail = {'volumeId': closure.owner, 'time': float(times[-1]), 'T': temperature, 'P': pressure, 'reactions': [r['id'] for r in config['reactions']],
              'finalAmounts': [float(v) for v in n], 'equilibriumAmounts': equilibrium['moles'],
              'affinityRT': state.get('affinity_RT'), 'lnK': state.get('lnK'),
              'kineticStateCertified': bool(certificate.get('certified')), 'elementResidual': certificate.get('element_residual'),
              'reactionEnthalpy': enthalpy['dH'], 'reactionEnthalpyUnit': 'J/mol', 'anchor': closure.anchor,
              'stabilityScope': 'liquid trials only' if closure.liquid_only else 'package candidate phases'}
    row = {'id': 'reactions.equilibrium_limit.' + closure.owner, 'valor': distance, 'tolerancia': 1e-3,
           'descripcion': ('Largest |n_i(final) - n_i(equilibrium)| / sum n_i(0), with the equilibrium certified by the package at the final T and P '
                           'and the initial element inventory. Above tolerance, the kinetic state has not reached the chemical-equilibrium limit '
                           '(too short a horizon, or rate laws inconsistent with K(T)); it is a diagnostic, not a solver failure.')}
    return row, detail
