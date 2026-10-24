// Cross-language integration: persisted selection -> strict readers -> real Python
// core/compiler -> existing physical Results. No browser algebra substitutes for Python.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const directory = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(directory, '..');
const cache = new Map();
function load(file) {
  if (!path.extname(file)) file += '.ts';
  if (file.endsWith('.json')) return { default: JSON.parse(fs.readFileSync(file, 'utf8')) };
  if (cache.has(file)) return cache.get(file);
  const loadedModule = { exports: {} }; cache.set(file, loadedModule.exports);
  const source = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true,
  } }).outputText;
  new Function('exports', 'module', 'require', 'process', source)(loadedModule.exports, loadedModule, dependency => {
    if (!dependency.startsWith('.')) throw new Error('Unexpected external dependency: ' + dependency);
    return load(path.resolve(path.dirname(file), dependency));
  }, { env: {} });
  cache.set(file, loadedModule.exports); return loadedModule.exports;
}
const motor = name => load(path.join(directory, 'app/motor', name));
const { selectFormulation, selectedTransformedModel, transformationDocument } = load(path.join(directory, 'app/models/transformationSelection'));
const { firmaHoja, transformationSourceSignature, resolverHoja, compilarHoja } = motor('modeloHojaMotor');
const { resolverHojaEngine } = motor('resolverEngine');
const { prepararSolicitud, leerRespuestaNucleo } = load(path.join(directory, 'app/adimensionalizacion/lecturaNucleo'));
const { readCompilationReport } = load(path.join(directory, 'motores/modelo/compilation'));
const bridge = `
import sys, json
sys.path.insert(0, '.')
from core.adimensionalizacion.nucleo import procesar
from backend.api_modelo import resolver_modelo
request = json.load(sys.stdin)
try:
    result = procesar(request['request']) if 'request' in request else resolver_modelo(request)
    print(json.dumps(result))
except Exception as error:
    print(json.dumps({'__error__': str(error)}))
`;
function python(body) {
  const process = spawnSync('python', ['-c', bridge], { cwd: root, input: JSON.stringify(body), encoding: 'utf8', maxBuffer: 64 << 20,
    env: { ...globalThis.process.env, PYTHONIOENCODING: 'utf-8' } });
  if (process.status !== 0) throw new Error(process.stderr);
  const result = JSON.parse(process.stdout);
  if (result.__error__) throw new Error(result.__error__);
  return result;
}
let checks = 0;
function check(condition, message) { assert.ok(condition, message); checks++; }
const models = motor('hojasPruebaMateria').crearHojasPruebaMateria().slice(0, 6);
for (const model of models) {
  const request = prepararSolicitud(transformationDocument(model), { presupuesto: 100 });
  const response = leerRespuestaNucleo(python({ request }), request);
  const formulation = response.formulaciones.find(form => form.objetivosAplicados.length) ?? response.formulaciones[0];
  const freeScales = Object.fromEntries(formulation.libres.map(id => {
    const symbol = formulation.simbolos.find(item => item.id === id);
    return [id, { value: 2.5, unit: symbol.variableId === 't' ? 's' : compilarHoja(model).unidadEstado }];
  }));
  const transformation = selectFormulation(model, response, formulation, 'Chosen formulation', freeScales);
  const selected = { ...model, transformation };
  check(firmaHoja(selected) !== firmaHoja(model), 'Selection invalidates physical execution results');
  check(transformation.sourceSignature === transformationSourceSignature({ ...selected, config: { ...selected.config, rtol: 2e-7, muestras: 51, metodo: 'euler_implicito' } }), 'Numerical settings preserve the transformation');
  check(transformationSourceSignature(selected) === transformationSourceSignature({ ...selected, nombre: 'Renamed' }), 'Renaming preserves the transformation');
  const result = await resolverHojaEngine(selected, { transporte: async common => python({ modelo: common }) });
  check(result.motor === 'rage.compilador.transformed' && result.compilation?.formulation === 'scaled', 'Actual transformed compiler was executed');
  check(result.firma === firmaHoja(selected) && result.compilation.variables.length === model.historial.pasos[model.historial.activo].formulacion.componentes.length, 'State and execution identities survive reconstruction');
  const reference = await resolverHoja(model);
  let error = 0;
  result.valores.forEach((row, time) => row.forEach((state, index) => {
    if (time < reference.valores.length) error = Math.max(error, Math.abs(state[0] - reference.valores[time][index][0]) / Math.max(1, Math.abs(reference.valores[time][index][0])));
  }));
  check(error < 3e-6, `Reconstructed physical trajectory agrees with independent solver: ${error}`);
  check(result.conservacion.every(value => Math.abs(value) < 1e-7 * Math.max(1, ...result.valores.flat(2).map(Math.abs))), 'Original balance diagnostics remain available');
  const stale = structuredClone(selected);
  stale.config.tiempo.texto = '99';
  assert.throws(() => selectedTransformedModel(stale), /outdated/); checks++;
  assert.deepEqual(readCompilationReport(result.compilation), result.compilation); checks++;
  const bad = structuredClone(result.compilation);
  bad.variables[0].scaleSI = Infinity;
  assert.throws(() => readCompilationReport(bad)); checks++;
}
console.log(`Transform execution: ${checks} checks passed across ${models.length} physical models.`);
