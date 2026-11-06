"""PDE-0: Solve rejects spatial formulations with a located reason (F7 deferred).

The field rows are deduced by the shared matter producer (local component law,
recorded Fick substitution and coordinate expansion), never typed in. Solve has
no meshes or discretization: it must name the row, the fields and coordinates.
"""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sympy as sp

from core.balances import material_derivation as material
from core.balances.material_equations import equation_graph
from core.compilador import NoSoportado, SistemaExplicito
from core.compilador.derived import DerivedSystem, source_signature
from core.compilador.steady import SteadySystem
from core.mathematics.dimensions import catalog
from core.mathematics.operators import (BoundaryFlux, Divergence, Gradient, VolumeIntegral,
                                         requires_discretization, spatial_content)
from core.modelo.equation_workbench import build

T = sp.Symbol('t', real=True)
X = sp.Symbol('x', real=True)
FICK_STATE = {'campo': {'sinReaccion': True, 'sinConveccion': True, 'difusion': 'laplaciano'},
              'vista': 'campo', 'fija': True, 'invariantes': [False, True, True]}


def audit_probe_graph():
    """The read-only audit's probe (5 November 2026): binary 1D Fick, field view."""
    model = {'id': 'probe', 'volumenes': [{'id': 'v1', 'componenteIds': ['A', 'B']}],
             'componentes': [{'id': 'A'}, {'id': 'B'}], 'corrientes': []}
    return equation_graph(model, 'v1', FICK_STATE)


def fick_model():
    """Common model whose recorded matter journal keeps the 1D field view."""
    owner = 'v1'
    model = {'formato': 'rage.modelo', 'version': 0, 'id': 'fick-field', 'nombre': 'Fick field',
             'componentes': [{'id': 1, 'nombre': 'A', 'simbolo': 'A'}, {'id': 2, 'nombre': 'B', 'simbolo': 'B'}],
             'termodinamica': {'paquetes': []}, 'volumenes': [], 'corrientes': [], 'intercambios': [],
             'datos': {}, 'matematico': None, 'estudio': None, 'motores': {}, 'procedencia': {'tipo': 'nuevo'}}
    journal = material.edit_journal({'format': 'rage.material-derivation', 'version': 1, 'volumes': {}}, owner, {'kind': 'start'})
    entry = journal['volumes'][owner]
    entry['operations'].append({'id': 'fick', 'title': 'Laplacian Fick diffusion, 1D slab',
                                'changes': {key: FICK_STATE[key] for key in ('campo', 'fija', 'invariantes')}})
    model['motores']['materialDerivation'] = journal

    def datum(key, value, unit, role='parametro'):
        model['datos'][key] = {'magnitud': key, 'funcion': role, 'declaracion': {'texto': str(value), 'unidad': unit},
                               'origen': {'propietarioId': 'volumen:'+owner, 'ruta': key}}
        return key
    model['volumenes'].append({'id': owner, 'componenteIds': [1, 2],
        'balances': {'materia': True, 'energia': False, 'momento': False},
        'supuestos': {'materia': material.replay_volume(entry)[-1], 'energia': None},
        'frontera': {'tipo': 'sin_relacion'},
        'inicial': {'cantidades': {'base': 'masica', 'datoIds': {'1': datum('mA', 1, 'kg', 'inicial'), '2': datum('mB', 1, 'kg', 'inicial')}}},
        'termodinamica': {'tipo': 'supuesto', 'supuesto': 'fase_no_evaluada', 'motivo': 'Field-view diffusion probe.'}})
    result = build(model)
    names = {str(q): key for key, q in {**catalog(result.graph, result.units), **result.introduced}.items()}
    return model, names, datum


def dynamic_selection(model, names, datum):
    model['estudio'] = {'tipo': 'temporal', 'tiempoId': datum('horizon', 5, 's', 'estudio'), 'metodoSolicitado': 'rk45',
                        'muestras': 5, 'rtol': 1e-9, 'atol': {'cantidad': 1e-11}}
    state = names['rho__v1__1(x, t)']
    model['motores']['derivedExecution'] = {'format': 'rage.derived-execution', 'version': 1,
        'sourceSignature': source_signature(model), 'timeId': names['t'],
        'states': [{'quantityId': state, 'equationId': 'matter.v1.1.operators'}], 'parameters': {},
        'initialValues': {state: datum('rho0', 1, 'kg/m3', 'inicial')}, 'initialEquations': [],
        'reconstructions': [], 'checks': []}
    return model


def steady_selection(model, names, datum):
    model['estudio'] = {'tipo': 'steady', 'version': 1, 'metodoSolicitado': 'damped_newton'}
    state = names['rho__v1__1(x, t)']
    for key in ('seed', 'lower', 'upper', 'scale', 'residual'):
        datum(key, 1, 'kg/m3' if key != 'residual' else 'kg/(m3*s)')
    model['motores']['derivedExecution'] = {'format': 'rage.derived-execution', 'version': 5,
        'sourceSignature': source_signature(model), 'timeId': names['t'],
        'states': [{'quantityId': state, 'equationId': 'matter.v1.1.operators'}], 'algebraic': [],
        'unknowns': [state], 'parameters': {}, 'invariants': {}, 'reconstructions': [], 'checks': [],
        'nonlinear': {'variables': {state: {'seedDataId': 'seed', 'lowerDataId': 'lower', 'upperDataId': 'upper', 'scaleDataId': 'scale'}},
                      'residualScales': {'matter.v1.1.operators': 'residual'}, 'residualTolerance': 1e-9,
                      'stepTolerance': 1e-12, 'maxIterations': 20, 'maxBacktracks': 10}}
    return model


def explicit_diffusion_model():
    """Authored v2 `matematico` diffusion with a declared `coordenada` role."""
    D = lambda **k: {b: {'n': v, 'd': 1} for b, v in k.items()}  # noqa: E731
    num = lambda v: {'tipo': 'numero', 'valor': v}  # noqa: E731
    s = lambda i: {'tipo': 'simbolo', 'id': i}  # noqa: E731
    def symbol(id_, role, dim, depends=()):
        return {'id': id_, 'nombre': id_, 'rol': role, 'dimension': dim, 'unidad': None,
                'constante': role in ('parametro', 'constante'), 'dependeDe': list(depends), 'signo': 'desconocido'}
    datos = {'matematico.Dif': {'magnitud': 'parametro', 'funcion': 'parametro', 'declaracion': {'texto': '1e-9', 'unidad': 'm2/s'},
                                'origen': {'propietarioId': 'matematico', 'ruta': 'matematico.simbolos.Dif'}},
             'estudio.tf': {'magnitud': 'tiempo', 'funcion': 'estudio', 'declaracion': {'texto': '10', 'unidad': 's'},
                            'origen': {'propietarioId': 'estudio', 'ruta': 'estudio.tf'}}}
    return {'formato': 'rage.modelo', 'version': 0, 'id': 'explicit-diffusion', 'nombre': 'explicit diffusion', 'componentes': [],
            'termodinamica': {'paquetes': []}, 'volumenes': [], 'corrientes': [], 'intercambios': [], 'datos': datos,
            'matematico': {'id': 'mat', 'revision': 1, 'funciones': [],
                           'simbolos': [symbol('t', 'tiempo', D(T=1)), symbol('x', 'coordenada', D(L=1)),
                                        symbol('c', 'campo', D(M=1, L=-3), ('t', 'x')), symbol('Dif', 'parametro', D(L=2, T=-1)),
                                        symbol('tf', 'parametro', D(T=1))],
                           'ecuaciones': [{'id': 'ec_c', 'izquierda': {'tipo': 'derivada', 'expresion': s('c'), 'respecto': 't', 'orden': 1},
                                           'derecha': {'tipo': 'producto', 'argumentos': [s('Dif'), {'tipo': 'laplaciano', 'expresion': s('c'), 'coordenadas': ['x']}]}}],
                           'dominios': [{'id': 'it', 'variableId': 't', 'desde': num(0), 'hasta': s('tf')}],
                           'condiciones': [{'id': 'ini_c', 'tipo': 'inicial', 'dominioId': 'it',
                                            'ecuacion': {'id': 'ini_c-eq', 'izquierda': s('c'), 'derecha': num(1)}}]},
            'estudio': {'tipo': 'temporal', 'tiempoId': 'estudio.tf', 'metodoSolicitado': 'rk45', 'muestras': 11,
                        'rtol': 1e-9, 'atol': {'cantidad': 1e-12}},
            'motores': {}, 'procedencia': {'tipo': 'nuevo'}}


class SharedDetectorTests(unittest.TestCase):
    def test_audit_probe_graph_is_located(self):
        graph, final, _ = audit_probe_graph()
        findings = requires_discretization(graph, final, T)
        self.assertEqual(findings[0]['equationId'], 'matter.v1.A.operators')
        self.assertEqual(findings[0]['coordinates'], ['x'])
        self.assertEqual(findings[0]['fields'], ['rho__v1__A(x, t)'])
        self.assertEqual([f['equationId'] for f in findings], final)

    def test_integrated_and_time_only_content_is_not_spatial(self):
        rho = sp.Function('rho')(X, T)
        mass = sp.Function('m')(T)
        self.assertFalse(spatial_content(sp.Eq(sp.Derivative(VolumeIntegral(rho), T), -BoundaryFlux(rho)), T)['coordinates'])
        self.assertFalse(spatial_content(sp.Eq(sp.Derivative(mass, T), sp.Function('D')(T)*mass), T)['coordinates'])
        unexpanded = spatial_content(sp.Eq(sp.Derivative(rho, T), -Divergence(Gradient(rho))), T)
        self.assertEqual(unexpanded['operators'], ('Divergence', 'Gradient'))
        self.assertEqual(unexpanded['coordinates'], (X,))
        derivative_only = spatial_content(sp.Eq(sp.Function('q')(T), sp.Subs(sp.Derivative(rho, X), X, 0)), T)
        self.assertTrue(derivative_only['derivatives'] or derivative_only['coordinates'])


    def test_scalar_dependencies_are_not_coordinates(self):
        # Review P1 (6 November 2026): scalar arguments and derivatives with
        # respect to them are not spatial, while the Fick probe still is.
        temperature, alpha = sp.symbols('T alpha', real=True)
        h, k = sp.Function('h')(temperature), sp.Function('k')(alpha)
        for expression in (sp.Eq(sp.Function('U')(T), h), sp.Eq(sp.Function('r')(T), k*sp.Function('c')(T)),
                           sp.Eq(sp.Function('cp')(T), sp.Derivative(h, temperature))):
            content = spatial_content(expression, T)
            self.assertEqual((content['coordinates'], content['fields'], content['derivatives']), ((), (), False))
        owner_axis = sp.Symbol('x__v1', real=True)
        self.assertEqual(spatial_content(sp.Eq(sp.Function('rho')(owner_axis, T), 0), T)['coordinates'], (owner_axis,))
        graph, final, _ = audit_probe_graph()
        self.assertEqual(requires_discretization(graph, final, T)[0]['equationId'], 'matter.v1.A.operators')


class CompilerRejectionTests(unittest.TestCase):
    def assert_located(self, error, equation_id):
        row = error.diagnostics[0]
        self.assertEqual(row['code'], 'requires_discretization')
        self.assertEqual(row['equationId'], equation_id)
        self.assertEqual(row['coordinates'], ['x'])
        self.assertEqual(row['fields'], ['rho__v1__1(x, t)'])
        self.assertIn('spatial discretization is deferred (F7)', row['message'])

    def test_dynamic_derived_compiler(self):
        model = dynamic_selection(*fick_model())
        with self.assertRaises(NoSoportado) as caught:
            DerivedSystem(model)
        self.assert_located(caught.exception, 'matter.v1.1.operators')

    def test_steady_derived_compiler(self):
        model = steady_selection(*fick_model())
        with self.assertRaises(NoSoportado) as caught:
            SteadySystem(model)
        self.assert_located(caught.exception, 'matter.v1.1.operators')

    def test_explicit_matematico_coordinate(self):
        model = explicit_diffusion_model()
        with self.assertRaises(NoSoportado) as caught:
            SistemaExplicito(model)
        row = caught.exception.diagnostics[0]
        self.assertEqual((row['code'], row['path']), ('requires_discretization', 'matematico.simbolos[1]'))
        self.assertIn('x', row['message'])

    def test_nonspatial_matter_selection_still_compiles(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from matter_lowering_inputs import matter_case
        system = DerivedSystem(matter_case('decay'))
        self.assertTrue(system.states)


if __name__ == '__main__':
    unittest.main()
