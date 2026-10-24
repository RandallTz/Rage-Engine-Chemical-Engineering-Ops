// The requested examples are documents built through shared Model operations.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {spawnSync} from 'node:child_process';
import assert from 'node:assert/strict';
import ts from 'typescript';
import katex from 'katex';
const directory=path.dirname(fileURLToPath(import.meta.url)),require=createRequire(import.meta.url),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(file.endsWith('.css'))return {default:{}};
  if(cache.has(file))return cache.get(file).exports;
  const loadedModule={exports:{}};cache.set(file,loadedModule);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('exports','module','require','process',code)(loadedModule.exports,loadedModule,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id),process);
  return loadedModule.exports;
}
const {pressureExamples}=load(path.join(directory,'testing/pressureExamples'));
const {modeloBalancesDesdeHoja}=load(path.join(directory,'motores/modelo/desdeHojaBalances'));
const {leerModeloComun}=load(path.join(directory,'motores/modelo/lector'));
const {auditModelDerivation}=load(path.join(directory,'app/models/modelDerivationAudit'));
const {firmaHoja}=load(path.join(directory,'app/motor/modeloHojaMotor'));
const {readHydraulicNetwork}=load(path.join(directory,'app/models/hydraulicDefinition'));
const models=pressureExamples(),common=[];
for(const model of models){
  assert.equal(auditModelDerivation(model).status,'recorded');
  const raw=modeloBalancesDesdeHoja(model);leerModeloComun(raw);common.push(raw);
  assert.ok(!model.resultado&&!model.resultadoRef&&!raw.matematico,'Examples must contain inputs and recorded assumptions only.');
  const edited=structuredClone(model);edited.config.datos.viscosity.texto='.06';assert.notEqual(firmaHoja(model),firmaHoja(edited));
  const bad=structuredClone(model.hydraulicNetwork);bad.paths[0].flow.kind='case';assert.throws(()=>readHydraulicNetwork(bad));
  const missing=structuredClone(raw);missing.motores.hydraulicNetwork.medium.densityId='missing';assert.throws(()=>readHydraulicNetwork(missing.motores.hydraulicNetwork,missing));
  const pressureRole=structuredClone(raw);pressureRole.motores.hydraulicNetwork.paths[0].inletPressure={kind:'recover'};pressureRole.motores.hydraulicNetwork.paths[0].outletPressure={kind:'recover'};assert.throws(()=>readHydraulicNetwork(pressureRole.motores.hydraulicNetwork,pressureRole));
  if(process.argv.includes('--write'))fs.writeFileSync(path.join(directory,'../docs/ejemplos',model.id+'.model.json'),JSON.stringify({format:'rage.model-file',version:1,model},null,2)+'\n');
}
const scratch=path.join(directory,'../.tmp');fs.mkdirSync(scratch,{recursive:true});
fs.writeFileSync(path.join(scratch,'hydraulic-models.json'),JSON.stringify(common));
if(process.argv.includes('--inputs-only'))process.exit(0);
const python=spawnSync('python',['tests/test_hydraulic_execution.py'],{cwd:path.dirname(directory),encoding:'utf8'});assert.equal(python.status,0,python.stderr+python.stdout);
const publications=JSON.parse(fs.readFileSync(path.join(scratch,'hydraulic-publications.json'),'utf8'));
const {readCompilationReport}=load(path.join(directory,'motores/modelo/compilation'));
const {leerResultados}=load(path.join(directory,'motores/resultados/lector'));
const {readMomentumDevelopment}=load(path.join(directory,'app/models/momentumDerivation'));
let formulas=0;
for(const publication of publications){
  readCompilationReport(publication.report);leerResultados(publication.result);
  for(const row of [...publication.report.systemEquations,...publication.report.strategy.steps]){katex.renderToString(row.latex,{throwOnError:true,displayMode:true,strict:'error'});formulas++;}
  for(const development of publication.developments){
    readMomentumDevelopment(development);
    const rows=[...development.steps,...development.finalSteps,...development.couplingSteps];
    assert.ok(rows.some(row=>row.derivation),'The Model must publish the actual equation operations.');
    for(const row of rows)for(const latex of [row.latex,...row.derivation?.beforeLatex??[]]){katex.renderToString(latex,{throwOnError:true,displayMode:true,strict:'error'});formulas++;}
    const broken=structuredClone(development);broken.steps.find(row=>row.derivation).derivation.beforeLatex=[null];assert.throws(()=>readMomentumDevelopment(broken));
  }
}
console.log(JSON.stringify({inputOnlyModels:models.length,recordedDerivations:'passed',commonReaders:'passed',independentReferences:'passed',checkedLatex:formulas}));
