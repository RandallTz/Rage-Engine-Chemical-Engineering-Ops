// Audit every registered template and reject new provenance bypasses.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const directory = path.dirname(fileURLToPath(import.meta.url));
const cache = new Map();
function load(file) {
  if (!path.extname(file)) file += '.ts';
  if (file.endsWith('.json')) return { __esModule: true, default: JSON.parse(fs.readFileSync(file, 'utf8')) };
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

const { REGRESSION_MODELS } = load(path.join(directory, 'testing/modelFixtures'));
const { modeloBalancesDesdeHoja, cabeEnBalances } = load(path.join(directory, 'motores/modelo/desdeHojaBalances'));
const { modeloDesdeHojaMotor } = load(path.join(directory, 'motores/modelo/desdeHojaMotor'));
const { leerModeloComun } = load(path.join(directory, 'motores/modelo/lector'));
const { journalInRequest, journalMatches, readMaterialJournal } = load(path.join(directory, 'app/motor/materialDerivation'));
const { auditModelDerivation } = load(path.join(directory, 'app/models/modelDerivationAudit'));
const { firmaHoja } = load(path.join(directory, 'app/motor/modeloHojaMotor'));
const topology = load(path.join(directory, 'app/motor/topologiaRed'));
const networkEdits = load(path.join(directory, 'app/motor/networkMaterialJournal'));
const { copiarARed, cambiarRed, sincronizarHipotesis } = load(path.join(directory, 'app/motor/redTermodinamica'));
const { iniciarRecorrido } = load(path.join(directory, 'app/motor/recorridoMateria'));
const { materialState } = load(path.join(directory, 'app/motor/materialDerivation'));
const models = REGRESSION_MODELS.flatMap(group => group.create());
if (process.argv.includes('--browser-fixtures')) fs.writeFileSync(path.join(path.dirname(directory), '.tmp/material-ui-models.json'), JSON.stringify(models));
let checks = 0;
const check = (condition, message) => { assert.ok(condition, message); checks++; };
const payload = [];
for (const model of models) {
  if (model.redTermodinamica) {
    const request = model.redTermodinamica.solicitud;
    const journal = journalInRequest(request.derivacion);
    check(!!journal, model.id + ': network template records material operations');
    for (const volume of request.volumenes) check(journalMatches(journal.volumes[volume.id], volume.formulacionMateria), model.id + ': material operations produce volume ' + volume.id);
    check(!auditModelDerivation(model).findings.some(item => item.family === 'matter'), model.id + ': material journal passes the structural audit');
    payload.push({ id: model.id, request });
  } else {
    const common = cabeEnBalances(model) ? modeloBalancesDesdeHoja(model) : modeloDesdeHojaMotor(model);
    check(leerModeloComun(common) === common, model.id + ': common reader accepts recorded material history');
    for (const volume of common.volumenes) check(journalMatches(common.motores.materialDerivation.volumes[volume.id], volume.supuestos.materia), model.id + ': adapter preserves the material assumptions');
    payload.push({ id: model.id, common });
  }
}
const network = models.find(model => model.redTermodinamica);
const expanded = structuredClone(network.redTermodinamica);
const addedId = topology.agregarElementoRed(expanded, 'volumen');
const added = expanded.solicitud.volumenes.find(volume => volume.id === addedId);
check(added.formulacionMateria.vista === 'campo' && !added.formulacionMateria.campo.sinReaccion && !added.formulacionMateria.restoImpermeable, 'New network volumes do not inherit final material assumptions');
check(journalMatches(journalInRequest(expanded.solicitud.derivacion).volumes[addedId], added.formulacionMateria), 'A new network volume records only its explicit boundary configuration');
topology.quitarElementoRed(expanded, 'volumen', addedId);
check(!journalInRequest(expanded.solicitud.derivacion).volumes[addedId], 'Deleting a volume removes its journal ownership');
const adopted = copiarARed(models.find(model => model.energia));
check(adopted.redTermodinamica.solicitud.volumenes.every(volume => journalMatches(journalInRequest(adopted.redTermodinamica.solicitud.derivacion).volumes[volume.id], volume.formulacionMateria)), 'Adopting a thermodynamic network preserves actual recorded material history');
const switched = cambiarRed(network, red => { const volume = red.solicitud.volumenes[0]; volume.frontera = {tipo:'rigida',datoId:'boundary.pending'}; sincronizarHipotesis(volume); });
check(journalMatches(journalInRequest(switched.redTermodinamica.solicitud.derivacion).volumes.A, switched.redTermodinamica.solicitud.volumenes[0].formulacionMateria), 'An explicit mechanical-boundary edit records its material consequence');
const legacy = structuredClone(network.redTermodinamica.solicitud);
delete legacy.derivacion;
const previous = structuredClone(legacy.volumenes[0].formulacionMateria), expected = JSON.stringify(legacy);
const rebuild = {format:'rage.material-derivation',version:1,volumes:{A:{origin:'reviewed_rebuild',operations:[]}}};
networkEdits.replaceNetworkMaterialJournal(legacy,'A',rebuild,materialState(iniciarRecorrido().pasos[0].formulacion),true,expected);
check(legacy.derivacion.previousMaterialFormulations.A.vista === previous.vista, 'Explicit rebuild archives the previous material formulation');
assert.throws(() => networkEdits.replaceNetworkMaterialJournal(legacy,'A',rebuild,previous,false,expected), /model changed/);checks++;
networkEdits.restoreNetworkMaterialFormulation(legacy,'A');
check(JSON.stringify(legacy.volumenes[0].formulacionMateria) === JSON.stringify(previous) && !legacy.derivacion.materialDerivation, 'Restoring a legacy formulation removes its replacement journal');
const modified = structuredClone(network);
modified.redTermodinamica.solicitud.derivacion.materialDerivation.volumes.A.operations[0].changes.vista = 'cantidad';
check(firmaHoja(network) !== firmaHoja(modified), 'Changed operation provenance invalidates saved execution identity');
const malformed = structuredClone(network.redTermodinamica.solicitud.derivacion.materialDerivation);
malformed.volumes.A.operations[0].changes.fija = 'true';
assert.throws(() => readMaterialJournal(malformed)); checks++;
const python = spawnSync('python', ['-c', `
import sys,json,math
from core.modelo import leer_modelo_comun,desde_ensamblaje_v2
from core.balances.material_derivation import validate_model_journal
from core.compilador import resolver
from core.compilador.report import compilation_report
items=json.load(sys.stdin)
models={}
for item in items:
 model=item.get('common') or desde_ensamblaje_v2(item['request'])
 leer_modelo_comun(model)
 evidence=validate_model_journal(model)
 assert len(evidence)==len(model['volumenes']),item['id']
 models[item['id']]=model
# Closed component conversion, open filling, and two connected control volumes.
checks=0
cases=[('motor-prueba-materia-v1-6',{'campo.m_A_dominio':math.exp(-4),'campo.m_B_dominio':1-math.exp(-4)}),
       ('motor-prueba-materia-v1-1',{'campo.m_A_dominio':700}),
       ('motor-prueba-acoplado-v1-1',{'campo.m_A_v1':700,'campo.m_A_v2':800})]
for key,expected in cases:
 model=models[key]
 report=compilation_report(model)
 assert len(report['materialDerivation'])==len(model['volumenes'])
 output=resolver(model)
 series={row['id']:row['valores'] for row in output['series']}
 for key,value in expected.items():
  assert abs(series[key][-1]-value)<2e-7,(key,series[key][-1],value)
  checks+=1
 for residual in output['verificaciones']:
  assert residual['valor']<=residual['tolerancia'],residual
  checks+=1
print(json.dumps({'pythonModels':len(models),'analyticalAndConservationChecks':checks}))
`], { cwd: path.dirname(directory), input: JSON.stringify(payload), encoding: 'utf8', maxBuffer: 4e6 });
if (python.status !== 0) throw new Error(python.stdout + python.stderr);
console.log(JSON.stringify({ structuralChecks: checks, ...JSON.parse(python.stdout) }, null, 2));
