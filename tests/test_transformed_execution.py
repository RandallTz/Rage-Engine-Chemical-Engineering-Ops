"""Independent analytical checks of Model -> Transform -> Solve -> Results."""

import copy
import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api_modelo import describe_compilation, resolver_modelo
from core.adimensionalizacion.nucleo import procesar
from core.compilador import NoSoportado, resolver
from core.compilador.report import compilation_report
from core.modelo import ErrorModelo, leer_modelo_comun
from core.resultados import leer_resultados


def symbol(name, role, dimension):
    return {"id": name, "nombre": name, "rol": role, "dimension": {base: {"n": power, "d": 1} for base, power in dimension.items()},
            "unidad": None, "constante": role == "parametro", "dependeDe": ["t"] if role == "campo" else [], "signo": "desconocido"}


def number(value):
    return {"tipo": "numero", "valor": value}


def ref(name):
    return {"tipo": "simbolo", "id": name}


def fixture():
    symbols = [symbol("t", "tiempo", {"T": 1}), symbol("m", "campo", {"M": 1}),
               symbol("k", "parametro", {"T": -1}), symbol("m0", "parametro", {"M": 1}), symbol("tf", "parametro", {"T": 1})]
    equation = {"id": "balance", "izquierda": {"tipo": "derivada", "expresion": ref("m"), "respecto": "t", "orden": 1},
                "derecha": {"tipo": "producto", "argumentos": [number(-1), ref("k"), ref("m")]}}
    mathematical = {"id": "decay", "revision": 1, "simbolos": symbols, "funciones": [], "ecuaciones": [equation],
                    "dominios": [{"id": "time", "variableId": "t", "desde": number(0), "hasta": ref("tf")}],
                    "condiciones": [{"id": "initial", "tipo": "inicial", "dominioId": "time",
                                     "ecuacion": {"id": "initial-eq", "izquierda": ref("m"), "derecha": ref("m0")}}]}
    form = {"id": "scaled", "nombre": "Scaled decay", "padreId": None, "modeloRevision": 1,
            "presentacion": "factorizada", "objetivos": [], "escalas": [
                {"simboloId": item["id"], "transformar": True, "nuevoNombre": item["id"] + "_ad", "dimension": item["dimension"],
                 "valor": {"tipo": "libre"}} for item in symbols if item["rol"] in ("tiempo", "campo")]}
    values = {"k": ("0.2", "1/s"), "m0": ("2000", "g"), "tf": ("20", "s")}
    data = {"matematico." + name: {"magnitud": "parameter", "funcion": "parametro", "declaracion": {"texto": value, "unidad": unit},
                                      "origen": {"propietarioId": "matematico", "ruta": name}} for name, (value, unit) in values.items()}
    data["end"] = {"magnitud": "time", "funcion": "estudio", "declaracion": {"texto": "20", "unidad": "s"},
                   "origen": {"propietarioId": "estudio", "ruta": "end"}}
    return {"formato": "rage.modelo", "version": 0, "id": "test", "nombre": "Decay", "componentes": [], "termodinamica": {"paquetes": []},
            "volumenes": [], "corrientes": [], "intercambios": [], "datos": data, "matematico": mathematical,
            "estudio": {"tipo": "temporal", "tiempoId": "end", "metodoSolicitado": "rk45", "muestras": 41, "rtol": 1e-9,
                        "atol": {"cantidad": 1e-11}}, "motores": {"adimensionalizacion": {"version": 2, "formas": [form], "activaId": "scaled"}},
            "procedencia": {"tipo": "nuevo"}, "restricciones": [{"simboloId": "m", "tipo": "no_negativo"}]}


def select(model, normalize=False):
    config = model["motores"]["adimensionalizacion"]
    document = {"formato": "adimensionalizacion", "version": 2, "id": model["id"], "nombre": model["nombre"],
                "modelo": model["matematico"], "formas": config["formas"], "activaId": config["activaId"]}
    response = procesar({"formato": "adimensionalizacion.solicitud", "version": 1, "operacion": "adimensionalizar",
                        "documento": document, "formaId": config["activaId"], "opciones": {"presupuesto": 40}})
    if response["estado"] != "correcto":
        raise AssertionError(response)
    form = next((form for form in response["formulaciones"] if form["objetivosAplicados"]), response["formulaciones"][0]) if normalize else response["formulaciones"][0]
    config["execution"] = {"version": 1, "objectives": form["objetivosAplicados"], "freeScales": {
        scale: {"value": 3 if symbols["variableId"] == "t" else 500, "unit": "s" if symbols["variableId"] == "t" else "g"}
        for scale in form["libres"] for symbols in form["simbolos"] if symbols["id"] == scale}}
    return model


class TransformedExecutionTests(unittest.TestCase):
    def test_actual_scaled_trajectory_and_reconstruction(self):
        for normalize in (False, True):
            for method in ("rk45", "bdf"):
                with self.subTest(normalize=normalize, method=method):
                    model = select(fixture(), normalize)
                    model["estudio"]["metodoSolicitado"] = method
                    original = copy.deepcopy(model)
                    result = leer_resultados(resolver(model))
                    self.assertEqual(model, original)
                    self.assertEqual(result["procedencia"]["motor"], "rage.compilador.transformed")
                    series = {item["id"]: item["valores"] for item in result["series"]}
                    for time, mass in zip(result["ejes"][0]["valores"], series["campo.m"]):
                        self.assertAlmostEqual(mass, 2 * math.exp(-0.2 * time), delta=3e-8)
                    report = result["procedencia"]["compilation"]
                    scale = report["variables"][0]["scaleSI"]
                    self.assertAlmostEqual(series["transformed.m_ad"][0] * scale, 2)
                    self.assertAlmostEqual(report["variables"][0]["absoluteTolerance"], 1e-11 / scale)
                    self.assertAlmostEqual(report["time"]["physicalFinalTime"], 20)
                    self.assertTrue(all(check["valor"] <= check["tolerancia"] for check in result["verificaciones"]))

    def test_report_and_endpoint(self):
        model = select(fixture())
        report = describe_compilation({"modelo": model})
        self.assertEqual(report, compilation_report(model))
        result = resolver_modelo({"modelo": model})
        self.assertEqual(result["procedencia"]["compilation"]["signature"], report["signature"])
        model.pop("motores")
        model["motores"] = {}
        self.assertEqual(compilation_report(model)["formulation"], "physical")

    def test_reject_invalid_scale_and_no_silent_fallback(self):
        model = select(fixture())
        key = next(iter(model["motores"]["adimensionalizacion"]["execution"]["freeScales"]))
        model["motores"]["adimensionalizacion"]["execution"]["freeScales"][key]["unit"] = "mol"
        with self.assertRaises(NoSoportado):
            resolver(model)
        model = select(fixture())
        model["motores"]["adimensionalizacion"]["execution"]["freeScales"] = {}
        with self.assertRaises(NoSoportado):
            resolver(model)

    def test_strict_execution_reader(self):
        model = select(fixture())
        for value in (0, -1, float("inf"), True):
            changed = copy.deepcopy(model)
            key = next(iter(changed["motores"]["adimensionalizacion"]["execution"]["freeScales"]))
            changed["motores"]["adimensionalizacion"]["execution"]["freeScales"][key]["value"] = value
            with self.assertRaises(ErrorModelo):
                leer_modelo_comun(changed)
        model["motores"]["adimensionalizacion"]["execution"]["unexpected"] = 1
        with self.assertRaises(ErrorModelo):
            leer_modelo_comun(model)

    def test_zero_term_keeps_state(self):
        model = fixture()
        model["matematico"]["ecuaciones"][0]["derecha"] = number(0)
        model = select(model)
        report = compilation_report(model)
        self.assertEqual(len(report["variables"]), 1)
        result = resolver(model)
        self.assertTrue(all(abs(value - 2) < 1e-12 for value in result["series"][0]["valores"]))

    def test_coupled_equations_share_the_same_time_and_reconstruct(self):
        model = fixture()
        mathematical = model['matematico']
        field = symbol('b', 'campo', {'M': 1})
        mathematical['simbolos'].append(field)
        mathematical['ecuaciones'].append({'id': 'transfer', 'izquierda': {'tipo': 'derivada', 'expresion': ref('b'), 'respecto': 't', 'orden': 1},
                                           'derecha': {'tipo': 'producto', 'argumentos': [ref('k'), ref('m')]}})
        mathematical['condiciones'].append({'id': 'initial_b', 'tipo': 'inicial', 'dominioId': 'time',
                                            'ecuacion': {'id': 'initial_b-eq', 'izquierda': ref('b'), 'derecha': number(0)}})
        model['motores']['adimensionalizacion']['formas'][0]['escalas'].append({
            'simboloId': 'b', 'transformar': True, 'nuevoNombre': 'b_ad', 'dimension': field['dimension'], 'valor': {'tipo': 'libre'}})
        result = resolver(select(model, normalize=True))
        series = {item['id']: item['valores'] for item in result['series']}
        for time, mass, received in zip(result['ejes'][0]['valores'], series['campo.m'], series['campo.b']):
            self.assertAlmostEqual(mass, 2 * math.exp(-.2 * time), delta=2e-8)
            self.assertAlmostEqual(received, 2 * (1 - math.exp(-.2 * time)), delta=2e-8)
            self.assertAlmostEqual(mass + received, 2, delta=2e-8)

    def test_nonautonomous_forcing_uses_transformed_time(self):
        model = fixture()
        model['matematico']['ecuaciones'][0]['derecha'] = {'tipo': 'producto', 'argumentos': [ref('k'), ref('m0'),
            {'tipo': 'cociente', 'numerador': ref('t'), 'denominador': ref('tf')}]}
        result = resolver(select(model))
        for time, mass in zip(result['ejes'][0]['valores'], result['series'][0]['valores']):
            self.assertAlmostEqual(mass, 2 + .01 * time ** 2, delta=1e-8)

    def test_domain_event_returns_physical_time(self):
        model = fixture()
        model['matematico']['simbolos'][2]['dimension'] = {'M': {'n': 1, 'd': 1}, 'T': {'n': -1, 'd': 1}}
        model['datos']['matematico.k']['declaracion']['unidad'] = 'kg/s'
        model['matematico']['ecuaciones'][0]['derecha'] = {'tipo': 'producto', 'argumentos': [number(-1), ref('k')]}
        result = resolver(select(model))
        self.assertEqual(result['estado'], 'parcial')
        self.assertAlmostEqual(result['ejes'][0]['valores'][-1], 10, delta=1e-8)
        self.assertAlmostEqual(result['eventos'][0]['valor'], 10, delta=1e-8)
        self.assertLess(abs(result['series'][0]['valores'][-1]), 1e-10)

    def test_stale_revision_is_rejected(self):
        model = select(fixture())
        model['matematico']['revision'] += 1
        with self.assertRaises(NoSoportado):
            resolver(model)


if __name__ == "__main__":
    unittest.main()
