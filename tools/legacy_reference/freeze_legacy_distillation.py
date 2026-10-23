"""Freeze the validated legacy distillation outputs as reference data (cleanup phase 2, clean-2).

This runs the legacy Process Simulation code exactly as its validation scripts do
(tests/validar_mccabe_thiele.py, validar_ponchon_savarit.py, validar_fug.py,
validar_diagrama_flujo.py and the /columna/resolver presets of validar_api.py) and
writes one JSON file per method to tests/reference_data/legacy-distillation/,
plus manifest.json with the SHA-256 of every file.

It must run before the legacy side is deleted (clean-4); afterwards it cannot run
and is deleted with that code. The frozen files are then checked, without legacy
imports, by tests/test_legacy_reference_data.py. The format is described in
docs/repository-cleanup/README.md (decision D6, phase 2 status).

Each case records its inputs, outputs (SI units unless stated), modeling
assumptions, the thermodynamic tables actually used and its validation grade.
A legacy output is not an independent truth: `validation` states which kind of
check supports it. Run from the repository root:
    python tools/legacy_reference/freeze_legacy_distillation.py
"""
import hashlib
import io
import json
import math
import platform
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / 'tests' / 'reference_data' / 'legacy-distillation'
FORMAT = 'rage.legacy-reference'
VERSION = 1
BUILD_LOG = 'docs/history/build-log.md'

import numpy as np
import scipy
import thermo

from thermodynamics.proveedor import ProveedorTermodinamico
from thermodynamics.elv import CalculadoraELV
from core.mccabe_thiele import EvaluadorMcCabeThiele, SolucionadorMcCabeThiele
from core.ponchon_savarit import EvaluadorPonchonSavarit, SolucionadorPonchonSavarit
from core.fug import AnalizadorFUG
from core.balance_materia import BalanceMateriaGlobal
from core.corriente import Corriente
from core.diagrama_flujo import DiagramaFlujo, OperacionUnitaria
from core.columna_destilacion import ColumnaDestilacion

LEGACY_SOURCES = [
    'core/mccabe_thiele.py', 'core/ponchon_savarit.py', 'core/fug.py', 'core/columna_destilacion.py',
    'core/balance_materia.py', 'core/orquestador.py', 'core/corriente.py', 'core/diagrama_flujo.py',
    'thermodynamics/proveedor.py', 'thermodynamics/elv.py', 'thermodynamics/entalpia.py',
    'backend/nucleo.py', 'backend/ejemplos.py', 'backend/schemas.py',
]


def sha256(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def plain(value):
    """Convert a legacy result to JSON values; unknown types fail instead of being dropped."""
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, np.ndarray):
        return plain(value.tolist())
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        value = float(value)
        if not math.isfinite(value):
            raise ValueError('non-finite legacy output')
        return value
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, Corriente):
        return {'components': list(value.nombres), 'composition': plain(value.composicion),
                'molar_flow': value.flujo_molar, 'T': value.T, 'P': value.P}
    raise TypeError(f'unsupported legacy output type {type(value).__name__}')


def rejection(fn):
    """Run a call that the legacy code must reject; record the exception type and message."""
    try:
        with redirect_stdout(io.StringIO()):
            fn()
    except (ValueError, RuntimeError) as error:
        return {'rejected': True, 'error': type(error).__name__, 'message': str(error)}
    return {'rejected': False}


def check(id_, kind, statement, source, holds=None):
    entry = {'id': id_, 'kind': kind, 'statement': statement, 'source': source}
    if holds is not None:
        entry['holdsInFrozenData'] = bool(holds)
    return entry


def binary_tables(names, P, provider, elv, n_points):
    """The equilibrium sweep the binary evaluators build internally, plus the pure properties behind it."""
    x1 = np.linspace(1e-4, 1 - 1e-4, n_points)
    T, y1, gamma = [], [], []
    for x in x1:
        Tb, y = elv.burbuja_T(P, np.array([x, 1.0 - x]))
        T.append(Tb); y1.append(y[0])
        provider.actualizar_estado(Tb, P)
        gamma.append(provider.coeficientes_actividad(Tb, np.array([x, 1.0 - x])))
    return {'components': names, 'P': P, 'sweep': 'linspace(1e-4, 1 - 1e-4, n) of the light-component liquid fraction',
            'x_light': x1, 'y_light': np.array(y1), 'T_bubble': np.array(T), 'activity_coefficients': np.array(gamma),
            'pure': pure_tables(provider, np.linspace(min(T), max(T), 11), P)}


def pure_tables(provider, temperatures, P):
    rows = {'T': [], 'P_sat': [], 'H_vap': [], 'Cp_liquid': [], 'Cp_ideal_gas': []}
    for T in temperatures:
        provider.actualizar_estado(T, P)
        rows['T'].append(T)
        rows['P_sat'].append(provider.presiones_saturacion(T))
        rows['H_vap'].append(provider.entalpias_vaporizacion(T))
        rows['Cp_liquid'].append(provider.capacidades_calorificas_liquido(T))
        rows['Cp_ideal_gas'].append(provider.capacidades_calorificas_gas(T))
    return {k: np.array(v) for k, v in rows.items()}


THERMO_PROVIDER = {
    'library': 'thermo', 'version': thermo.__version__,
    'objects': 'thermo.chemical.Chemical per species; thermo.unifac.UNIFAC (the library implementation, not the engine layer)',
    'vapor': 'ideal gas', 'liquid': 'UNIFAC activity coefficients with Chemical vapor pressures (modified Raoult)',
    'enthalpy': 'ideal mixing: liquid Cp integrated from T_ref = 298.15 K, vapor = liquid path + composition-weighted H_vap; no excess enthalpy',
    'note': 'The Engine thermodynamic layer uses its own UNIFAC packages; compare methods against these tables before attributing differences to a method.',
}
UNITS = {'T': 'K', 'P': 'Pa', 'P_sat': 'Pa', 'H_vap': 'J/mol', 'Cp_liquid': 'J/(mol K)', 'Cp_ideal_gas': 'J/(mol K)',
         'H_L': 'J/mol', 'H_V': 'J/mol', 'Qc_D': 'J/mol of distillate', 'QR_B': 'J/mol of bottoms',
         'Q_c': 'W (flows in mol/s)', 'Q_R': 'W (flows in mol/s)', 'F': 'mol/s', 'D': 'mol/s', 'B': 'mol/s',
         'N': 'theoretical stages including the reboiler (and the condenser when partial)',
         'R': '1 (external reflux ratio L/D)', 'q': '1 (liquid fraction of the feed)', 'fractions': '1 (mole fraction of the light component in binaries)'}


def mccabe_thiele():
    names, P = ['benzene', 'toluene'], 101325.0
    z_F, q, x_D, x_B = 0.40, 1.5, 0.95, 0.05
    provider = ProveedorTermodinamico(names); elv = CalculadoraELV(provider)
    ev = EvaluadorMcCabeThiele(elv, names, P_sistema=P)
    solver = SolucionadorMcCabeThiele(ev)
    R_min = ev.calcular_R_min(z_F, q, x_D)
    R = 1.5 * R_min
    rating = ev.calcular_escalones(z_F, q, x_D, x_B, R)
    design = solver.resolver(z_F=z_F, q=q, x_D=x_D, x_B=x_B, N=10.0)
    recheck = ev.calcular_escalones(z_F, q, x_D, x_B, design['valor_resuelto'])
    partial = ev.calcular_escalones(z_F, q, x_D, x_B, R, condensador_parcial=True)
    murphree = {str(E): ev.calcular_escalones(z_F, q, x_D, x_B, R, E_MV=E)['N'] for E in (1.0, 0.9, 0.7, 0.5)}
    balance = BalanceMateriaGlobal().resolver(F=100.0, z_F=z_F, x_D=x_D, x_B=x_B)
    inverse = BalanceMateriaGlobal().resolver(D=balance['D'], B=balance['B'], z_F=z_F, x_B=x_B)
    loads = ev.calcular_cargas_termicas(balance['D'], balance['B'], 100.0, z_F, x_D, x_B, R_ext=R, q=q)
    subcooled = ev.calcular_cargas_termicas(balance['D'], balance['B'], 100.0, z_F, x_D, x_B, R_ext=R, q=q, T_reflujo=loads['T_D'] - 10.0)
    preset = ev.calcular_escalones(0.40, 1.0, 0.95, 0.05, 3.0597377228491056)
    D_closed = 100.0 * (z_F - x_B) / (x_D - x_B)
    src = BUILD_LOG + ' > Método de McCabe-Thiele (Completado)'
    return {
        'id': 'mccabe-thiele-benzene-toluene', 'method': 'McCabe-Thiele (binary, constant molar overflow)',
        'legacy': {'module': 'core/mccabe_thiele.py', 'classes': ['EvaluadorMcCabeThiele', 'SolucionadorMcCabeThiele'],
                   'validationScript': 'tests/validar_mccabe_thiele.py'},
        'inputs': {'components': names, 'P': P, 'z_F': z_F, 'q': q, 'x_D': x_D, 'x_B': x_B, 'F': 100.0,
                   'R_factor_over_R_min': 1.5, 'equilibrium_curve_points': 100},
        'assumptions': ['Constant molar overflow', 'Linear q-line', 'Equilibrium curve: PCHIP through the bubble-point sweep with exact pure endpoints',
                        'Thermal loads: composition-weighted pure H_vap and Cp_L, no heat of mixing', 'Total condenser unless stated'],
        'thermodynamics': {'provider': THERMO_PROVIDER, 'tables': binary_tables(names, P, provider, elv, 100)},
        'outputs': {'R_min': R_min, 'rating': {'R': R, **rating},
                    'design_N_10': {**design, 'recheck_N': recheck['N']},
                    'partial_condenser': {'N_total': rating['N'], 'N_partial': partial['N']},
                    'murphree_N': murphree,
                    'material_balance': {'given': {'F': 100.0, 'z_F': z_F, 'x_D': x_D, 'x_B': x_B}, 'result': balance,
                                         'closed_form_D': D_closed, 'inverse_from_D_B': inverse},
                    'thermal_loads': loads, 'thermal_loads_subcooled_10K': subcooled,
                    'preset_q1_R': {'z_F': 0.40, 'q': 1.0, 'x_D': 0.95, 'x_B': 0.05, 'R': 3.0597377228491056, **preset}},
        'rejections': {
            'underdetermined_missing_x_B_and_R': rejection(lambda: solver.resolver(z_F=z_F, q=q, x_D=x_D, N=10.0)),
            'overdetermined_inconsistent_R_and_N': rejection(lambda: solver.resolver(z_F=z_F, q=q, x_D=x_D, x_B=x_B, R=3.0, N=999.0)),
        },
        'validation': {'grade': 'cross-checked', 'checks': [
            check('closed-form-balance', 'independent', 'D = F (z_F - x_B)/(x_D - x_B)', 'hand-derived', abs(balance['D'] - D_closed) < 1e-9 * D_closed),
            check('design-inverse', 'self-consistency', 'Re-evaluating the solved R recovers N = 10', src, abs(recheck['N'] - 10.0) < 1e-6),
            check('partial-condenser', 'self-consistency', 'A partial condenser adds exactly one stage', 'tests/validar_mccabe_thiele.py', abs(partial['N'] - rating['N'] - 1.0) < 1e-9),
            check('murphree-monotone', 'self-consistency', 'N increases as E_MV decreases', 'tests/validar_mccabe_thiele.py',
                  murphree['1.0'] < murphree['0.9'] < murphree['0.7'] < murphree['0.5']),
            check('loads-no-subcooling', 'independent', 'Without subcooling R_int = R_ext and Q_c = D (R + 1) H_vap,D', src,
                  abs(loads['R_int'] - R) < 1e-9 * R and abs(loads['Q_c'] - balance['D'] * (R + 1) * loads['Hvap_D']) < 1e-9 * loads['Q_c']),
            check('loads-subcooling-direction', 'self-consistency', '10 K subcooling increases Q_c and R_int', src,
                  subcooled['Q_c'] > loads['Q_c'] and subcooled['R_int'] > R),
            check('ps-cross-method', 'cross-method', 'Ponchon-Savarit N agrees within 3.5 % at three reflux levels', 'ponchon-savarit-benzene-toluene.json'),
        ]},
        'comparison': {'N': {'abs': 1e-6, 'reason': 'brentq/root_scalar defaults in the legacy design solver'},
                       'properties': {'rel': 1e-9, 'reason': 'deterministic thermo 0.6.1 evaluation'}},
    }


def ponchon_savarit():
    names, P = ['benzene', 'toluene'], 101325.0
    z_F, q, x_D, x_B = 0.40, -1.0, 0.95, 0.05
    provider = ProveedorTermodinamico(names); elv = CalculadoraELV(provider)
    ev = EvaluadorPonchonSavarit(elv, names, P_sistema=P, n_puntos_curva=80)
    ev_mt = EvaluadorMcCabeThiele(elv, names, P_sistema=P)
    solver = SolucionadorPonchonSavarit(ev)
    x = np.linspace(0, 1, 21)
    curves = {'x': x, 'H_L': np.array([ev.H_L(v) for v in x]), 'H_V': np.array([ev.H_V(v) for v in x])}
    H_F = ev.H_F_desde_q(z_F, q)
    QR_B = ev.derivar_QR_B(z_F, x_D, x_B, 300000.0, H_F)
    poles = ev.calcular_polos(z_F, x_D, x_B, 300000.0, QR_B, H_F=H_F)
    minima, cross = {}, []
    for qq in (1.0, -0.5):
        HF = ev.H_F_desde_q(z_F, qq)
        Qmin = ev.calcular_Qc_D_min(z_F, x_D, x_B, HF)
        low = rejection(lambda: ev.calcular_escalones(z_F, x_D, x_B, 0.9 * Qmin, ev.derivar_QR_B(z_F, x_D, x_B, 0.9 * Qmin, HF), H_F=HF))
        high = ev.calcular_escalones(z_F, x_D, x_B, 1.1 * Qmin, ev.derivar_QR_B(z_F, x_D, x_B, 1.1 * Qmin, HF), H_F=HF)
        minima[str(qq)] = {'H_F': HF, 'Qc_D_min': Qmin, 'pinch_at_0.9': low, 'N_at_1.1': high['N']}
        for factor in (1.5, 3.0, 6.0):
            Qc = factor * Qmin
            r = ev.calcular_escalones(z_F, x_D, x_B, Qc, ev.derivar_QR_B(z_F, x_D, x_B, Qc, HF), H_F=HF)
            xs = r['puntos'][1::2, 0]
            R_eq = Qc / (ev.H_V(x_D) - ev.H_L(x_D)) - 1.0
            N_mt = ev_mt.calcular_escalones(z_F, qq, x_D, x_B, R_eq)['N']
            cross.append({'q': qq, 'factor': factor, 'Qc_D': Qc, 'N_PS': r['N'], 'R_equivalent': R_eq, 'N_MT': N_mt,
                          'ratio': r['N'] / N_mt, 'monotone': bool(np.all(np.diff(xs) <= 1e-9))})
    designs = {str(qq): solver.resolver(z_F=z_F, x_D=x_D, x_B=x_B, q=qq, N=10.0) for qq in (1.0, -0.5)}
    direct = solver.resolver(z_F=z_F, x_D=x_D, x_B=x_B, Qc_D=300000.0, q=q)
    preset_HF = ev.H_F_desde_q(0.40, 1.0)
    preset_Qc = 131942.94936979646
    preset = ev.calcular_escalones(0.40, 0.95, 0.05, preset_Qc, ev.derivar_QR_B(0.40, 0.95, 0.05, preset_Qc, preset_HF), H_F=preset_HF)
    worst = max(abs(c['ratio'] - 1) for c in cross)
    src = BUILD_LOG + ' > Método de Ponchon-Savarit (Completado)'
    return {
        'id': 'ponchon-savarit-benzene-toluene', 'method': 'Ponchon-Savarit (binary, enthalpy-composition)',
        'legacy': {'module': 'core/ponchon_savarit.py', 'classes': ['EvaluadorPonchonSavarit', 'SolucionadorPonchonSavarit'],
                   'validationScript': 'tests/validar_ponchon_savarit.py'},
        'inputs': {'components': names, 'P': P, 'z_F': z_F, 'q': q, 'x_D': x_D, 'x_B': x_B, 'T_ref': 298.15, 'curve_points': 80},
        'assumptions': ['Ideal mixing enthalpy (no excess enthalpy), H_L,pure(T_ref) = 0', 'H_F from q by the secant between H_L(z_F) and H_V(z_F)',
                        'Q_R/B derived from Q_c/D by pole collinearity', 'q outside [0, 1] can imply a physically impossible feed temperature (not validated by the legacy code)'],
        'thermodynamics': {'provider': THERMO_PROVIDER, 'tables': binary_tables(names, P, provider, elv, 80), 'enthalpy_curves': curves},
        'outputs': {'poles_Qc_D_300000': {'H_F': H_F, 'QR_B': QR_B, **poles}, 'minimum_condenser_duty': minima,
                    'design_N_10': designs, 'direct_Qc_D_300000': direct, 'cross_check_with_mccabe_thiele': cross,
                    'preset_q1': {'z_F': 0.40, 'q': 1.0, 'x_D': 0.95, 'x_B': 0.05, 'Qc_D': preset_Qc, 'H_F': preset_HF, **preset}},
        'rejections': {
            'non_collinear_QR_B': rejection(lambda: ev.calcular_polos(z_F, x_D, x_B, 300000.0, 3.0 * QR_B, H_F=H_F)),
            'underdetermined_missing_x_B_and_Qc_D': rejection(lambda: solver.resolver(z_F=z_F, x_D=x_D, q=q, N=10.0)),
            'overdetermined_inconsistent': rejection(lambda: solver.resolver(z_F=z_F, x_D=x_D, x_B=x_B, Qc_D=300000.0, q=q, N=999.0)),
        },
        'validation': {'grade': 'cross-checked', 'checks': [
            # The build log reports 0.6-2.5 % for an earlier fixed-duty sweep; the current sweep, scaled with
            # Qc_D_min, reaches 3.25 % at 1.5 x Qc_D_min (q = 1). The difference is the CMO model gap, recorded as found.
            check('mccabe-thiele-cross-method', 'cross-method',
                  'N_PS / N_MT within 3.5 % for 1.5, 3 and 6 x Qc_D_min (near-ideal pair; the build log reports 0.6-2.5 % for an earlier fixed-duty sweep)',
                  src, worst <= 0.035),
            check('qc-min-bracket', 'self-consistency', 'Qc_D_min lies between the known pinching and converging duties (q = 1: 75000-150000; q = -0.5: 150000-300000)', src,
                  75000 < minima['1.0']['Qc_D_min'] < 150000 and 150000 < minima['-0.5']['Qc_D_min'] < 300000),
            check('design-inverse', 'self-consistency', 'Solving Qc_D for N = 10 recovers N = 10', src,
                  all(abs(d['N'] - 10.0) < 1e-6 for d in designs.values())),
            check('pinch-rejected', 'self-consistency', '0.9 Qc_D_min is rejected with a message citing the minimum', src,
                  all(m['pinch_at_0.9']['rejected'] for m in minima.values())),
        ]},
        'comparison': {'N': {'abs': 1e-6, 'reason': 'legacy root_scalar/bisection tolerances'},
                       'Qc_D_min': {'rel': 1e-6, 'reason': 'bisection on success/failure of the stepping'}},
    }


def fug():
    names, P = ['propane', 'n-butane', 'n-pentane', 'n-hexane'], 5 * 101325.0
    z_F, q = np.array([0.10, 0.30, 0.30, 0.30]), 1.0
    provider = ProveedorTermodinamico(names); elv = CalculadoraELV(provider)
    make = lambda lk, hk, z=z_F: AnalizadorFUG(elv, provider, names, z, q, P, lk, hk)
    base = make(1, 2)
    report = base.reporte_completo(recuperacion_LK_D=0.98, recuperacion_HK_B=0.98, R=3.0)
    sensitivity_R = {str(R): base.calcular_etapas_reales(R, report['R_min']) for R in (1.0, 2.0, 4.0, 8.0)}
    alpha_D, alpha_B = base._alpha_relativo(report['T_D'], report['x_D']), base._alpha_relativo(report['T_B'], report['x_B'])
    d0, b0 = base._distribucion_inicial(0.98, 0.98)
    N_min_2 = np.log((d0[1] / b0[1]) * (b0[2] / d0[2])) / np.log(np.sqrt(alpha_D * alpha_B)[1])
    base.preparar_fenske(recuperacion_LK_D=0.98, recuperacion_HK_B=0.98)
    distributed = [names[i] for i in base._componentes_distribuidos_para_underwood()]
    nonadjacent = make(1, 3)
    fenske_na = nonadjacent.preparar_fenske(recuperacion_LK_D=0.98, recuperacion_HK_B=0.98)
    underwood_na = nonadjacent.resolver_underwood()
    other = make(0, 1).reporte_completo(recuperacion_LK_D=0.97, recuperacion_HK_B=0.97, R=2.5)
    recoveries = {str(r): make(1, 2).reporte_completo(recuperacion_LK_D=r, recuperacion_HK_B=r, R=3.0) for r in (0.90, 0.95, 0.99, 0.999)}
    z_alt = np.array([0.05, 0.70, 0.20, 0.05])
    dominant = make(1, 2, z_alt).reporte_completo(recuperacion_LK_D=0.98, recuperacion_HK_B=0.98, R=3.0)
    Ts = [report['T_D'], report['T_F'], report['T_B']]
    phase_points = {}
    for label, T, x in (('top', report['T_D'], report['x_D']), ('feed', report['T_F'], z_F), ('bottom', report['T_B'], report['x_B'])):
        provider.actualizar_estado(T, P)
        phase_points[label] = {'T': T, 'x': x, 'P_sat': provider.presiones_saturacion(T),
                               'activity_coefficients': provider.coeficientes_actividad(T, np.asarray(x)),
                               'alpha_relative_to_HK': base._alpha_relativo(T, np.asarray(x))}
    n_min_values = [recoveries[k]['N_min'] for k in ('0.9', '0.95', '0.99', '0.999')]
    src = BUILD_LOG + ' > Método FUG - Fenske-Underwood-Gilliland (Completado, con una reserva marcada)'
    return {
        'id': 'fug-alkanes', 'method': 'Fenske-Underwood-Gilliland shortcut (multicomponent)',
        'legacy': {'module': 'core/fug.py', 'classes': ['AnalizadorFUG'], 'validationScript': 'tests/validar_fug.py'},
        'inputs': {'components': names, 'P': P, 'z_F': z_F, 'q': q, 'basis': 'F = 1 (d, b, D and B are fractions of the feed)',
                   'base_case': {'light_key': 'n-butane', 'heavy_key': 'n-pentane', 'recovery_LK_D': 0.98, 'recovery_HK_B': 0.98, 'R': 3.0}},
        'assumptions': ['Three-point (top, feed, bottom) geometric-mean relative volatility', 'Bootstrap distribution refined with Fenske',
                        'Underwood over distributed components; Gilliland correlation for N', 'Thermal loads by constant molar overflow'],
        'thermodynamics': {'provider': THERMO_PROVIDER, 'phase_points': phase_points, 'pure': pure_tables(provider, np.linspace(min(Ts), max(Ts), 11), P)},
        'outputs': {'base_case': report, 'N_vs_R': sensitivity_R, 'fenske_two_point_N_min': float(N_min_2),
                    'distributed_components_adjacent_keys': distributed,
                    'other_keys_propane_n_butane': {'recovery': 0.97, 'R': 2.5, **other},
                    'recovery_sensitivity_R_3': recoveries, 'dominant_feed': {'z_F': z_alt, **dominant},
                    'nonadjacent_keys_n_butane_n_hexane': {'fenske': fenske_na, 'underwood': underwood_na}},
        'rejections': {'nonadjacent_keys_negative_R_min': rejection(
            lambda: make(1, 3).reporte_completo(recuperacion_LK_D=0.98, recuperacion_HK_B=0.98, R=3.0))},
        'validation': {'grade': 'cross-checked', 'checks': [
            check('recoveries-exact', 'self-consistency', 'Key recoveries equal the specification', 'tests/validar_fug.py',
                  abs(report['d'][1] / z_F[1] - 0.98) < 1e-9 and abs(report['b'][2] / z_F[2] - 0.98) < 1e-9),
            check('material-balance', 'independent', 'd + b = z_F per component', 'hand-derived', np.allclose(report['d'] + report['b'], z_F)),
            check('temperature-order', 'self-consistency', 'T_D < T_F < T_B', 'tests/validar_fug.py', report['T_D'] < report['T_F'] < report['T_B']),
            check('fenske-two-vs-three-point', 'cross-method', 'Two- and three-point Fenske N_min differ by about 0.20 %', src,
                  abs(report['N_min'] - N_min_2) / report['N_min'] < 0.005),
            check('N-decreases-with-R', 'self-consistency', 'N decreases monotonically with R above R_min', 'tests/validar_fug.py',
                  all(a > b for a, b in zip(list(sensitivity_R.values()), list(sensitivity_R.values())[1:]))),
            check('N_min-increases-with-recovery', 'self-consistency', 'N_min increases with the specified recovery', 'tests/validar_fug.py',
                  all(a < b for a, b in zip(n_min_values, n_min_values[1:]))),
            check('nonadjacent-rejected', 'self-consistency', 'Non-adjacent keys give a negative R_min that is rejected', src, underwood_na['R_min'] < 0),
        ]},
        'comparison': {'N': {'abs': 1e-6, 'reason': 'brentq in Underwood and the bootstrap'}, 'temperatures': {'abs': 1e-6, 'unit': 'K'}},
    }


def column_flowsheet():
    names, P = ['propane', 'n-butane', 'n-pentane', 'n-hexane'], 5 * 101325.0
    z_F = np.array([0.10, 0.30, 0.30, 0.30])
    provider = ProveedorTermodinamico(names); elv = CalculadoraELV(provider)
    T_F, _ = elv.burbuja_T(P, z_F)
    feed = Corriente(names, z_F, 100.0, T_F, P)
    analyzer = AnalizadorFUG(elv, provider, names, z_F, q=1.0, P_sistema=P, indice_LK=1, indice_HK=2)
    column = ColumnaDestilacion('fug', analizador_fug=analyzer).a_operacion_unitaria(
        'columna', variables_entrada_extra=('recuperacion_LK_D', 'recuperacion_HK_B', 'R'), variables_salida_extra=('N', 'R_min'))

    def pump(entrada, factor_P):
        return {'salida': Corriente(entrada.nombres, entrada.composicion, entrada.flujo_molar, entrada.T, entrada.P * factor_P)}
    flowsheet = DiagramaFlujo()
    flowsheet.agregar_operacion(column)
    flowsheet.agregar_operacion(OperacionUnitaria('bomba', variables_entrada=('entrada', 'factor_P'), variables_salida=('salida',), resolver_fn=pump))
    flowsheet.conectar('columna', 'D', 'bomba', 'entrada')
    result = flowsheet.resolver(**{'columna.F': feed, 'columna.recuperacion_LK_D': 0.98, 'columna.recuperacion_HK_B': 0.98,
                                   'columna.R': 3.0, 'bomba.factor_P': 2.0})
    pool = {k: v for k, v in result['pool'].items() if isinstance(v, (Corriente, float, int, np.floating, np.ndarray, list, str))}
    D, pumped = result['pool']['columna.D'], result['pool']['bomba.salida']
    return {
        'id': 'column-flowsheet-fug-pump', 'method': 'ColumnaDestilacion (FUG) chained to a pump in DiagramaFlujo',
        'legacy': {'module': 'core/columna_destilacion.py', 'classes': ['ColumnaDestilacion', 'DiagramaFlujo', 'OperacionUnitaria'],
                   'validationScript': 'tests/validar_diagrama_flujo.py'},
        'inputs': {'components': names, 'P': P, 'feed': feed, 'recovery_LK_D': 0.98, 'recovery_HK_B': 0.98, 'R': 3.0, 'pump_pressure_factor': 2.0},
        'assumptions': ['Feed at its bubble point', 'The pump changes only pressure'],
        'thermodynamics': {'provider': THERMO_PROVIDER, 'feed_bubble_T': T_F},
        'outputs': {'complete': result['completo'], 'pool': pool, 'resolved_by': result['resueltos_por']},
        'validation': {'grade': 'cross-checked', 'checks': [
            check('same-as-fug', 'cross-method', 'Column N equals the FUG base case (pinned 9.434906966491038 in tests/validar_diagrama_flujo.py)',
                  'fug-alkanes.json', abs(result['pool']['columna.N'] - 9.434906966491038) < 1e-6),
            check('pump-preserves-state', 'independent', 'Pump keeps flow, T and composition and doubles P', 'hand-derived',
                  np.isclose(pumped.flujo_molar, D.flujo_molar) and np.isclose(pumped.T, D.T) and np.isclose(pumped.P, 2 * D.P)
                  and np.allclose(pumped.composicion, D.composicion)),
        ]},
        'comparison': {'N': {'abs': 1e-6}},
    }


def http_presets():
    # Same in-process client as tests/validar_api.py: TestClient does not start with this project's pinned httpx.
    import asyncio
    import httpx
    from backend.main import app

    class Client:
        def request(self, method, path, **kw):
            async def run():
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://freeze', timeout=600.0) as c:
                    return await c.request(method, path, **kw)
            return asyncio.run(run())

        def get(self, path):
            return self.request('GET', path)

        def post(self, path, json):
            return self.request('POST', path, json=json)
    client = Client()
    pairs = []
    for preset in client.get('/ejemplos').json():
        p = client.get(f"/ejemplos/{preset['id']}").json()
        request = {'metodo': p['metodo'], 'nombres': p['nombres'], 'feed': p['feed'], 'parametros': p['parametros'],
                   'indice_LK': p.get('indice_LK'), 'indice_HK': p.get('indice_HK')}
        response = client.post('/columna/resolver', json=request)
        if response.status_code != 200:
            raise RuntimeError(f"preset {p['id']} failed: {response.status_code} {response.text[:200]}")
        pairs.append({'preset': p['id'], 'request': request, 'status': response.status_code, 'response': response.json()})
    return {
        'id': 'http-column-presets', 'method': 'POST /columna/resolver with the /ejemplos presets',
        'legacy': {'module': 'backend/nucleo.py', 'routes': ['/ejemplos', '/ejemplos/{id}', '/columna/resolver'],
                   'validationScript': 'tests/validar_api.py'},
        'inputs': {'presets': [pair['preset'] for pair in pairs]},
        'assumptions': ['Same thermodynamics and methods as the method files; this file freezes the HTTP contract shape and values'],
        'thermodynamics': {'provider': THERMO_PROVIDER},
        'outputs': {'pairs': pairs},
        'validation': {'grade': 'legacy-output-only', 'checks': [
            check('serializes', 'self-consistency', 'Every preset resolves with status 200 and valid JSON', 'tests/validar_api.py', True),
        ]},
        'comparison': {'N': {'abs': 1e-6}},
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    status = git('status', '--porcelain', '--', *LEGACY_SOURCES)
    provenance = {
        'generator': 'tools/legacy_reference/freeze_legacy_distillation.py', 'commit': git('rev-parse', 'HEAD'),
        'legacySourcesModifiedInWorkingTree': bool(status), 'legacySourceSha256': {p: sha256(p) for p in LEGACY_SOURCES},
        'environment': {'python': platform.python_version(), 'numpy': np.__version__, 'scipy': scipy.__version__, 'thermo': thermo.__version__},
    }
    files = {}
    for build in (mccabe_thiele, ponchon_savarit, fug, column_flowsheet, http_presets):
        with redirect_stdout(io.StringIO()):
            case = build()
        document = {'format': FORMAT, 'version': VERSION, 'frozenOn': '2026-10-22', **case, 'units': UNITS, 'provenance': provenance}
        failed = [c['id'] for c in document['validation']['checks'] if c.get('holdsInFrozenData') is False]
        if failed:
            raise RuntimeError(f"{case['id']}: validation checks do not hold: {failed}")
        text = json.dumps(plain(document), indent=1, ensure_ascii=False, allow_nan=False) + '\n'
        name = case['id'] + '.json'
        (OUT / name).write_text(text, encoding='utf-8', newline='\n')
        files[name] = hashlib.sha256(text.encode('utf-8')).hexdigest()
        print('wrote', name, len(text), 'bytes')
    manifest = {'format': FORMAT + '.manifest', 'version': VERSION, 'frozenOn': '2026-10-22', 'files': files,
                'note': 'Frozen before deleting the legacy Process Simulation side (clean-4). Do not regenerate after deletion.'}
    (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8', newline='\n')
    print('wrote manifest.json')


if __name__ == '__main__':
    main()
