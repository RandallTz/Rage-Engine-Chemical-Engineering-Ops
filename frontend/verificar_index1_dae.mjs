// Real Python publication and strict TS readers/lifecycle, without a browser.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {spawnSync} from 'node:child_process';
import ts from 'typescript';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.dirname(here),require=createRequire(import.meta.url),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(cache.has(file))return cache.get(file).exports;
  const loadedModule={exports:{}};cache.set(file,loadedModule);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('module','exports','require',code)(loadedModule,loadedModule.exports,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id));
  return loadedModule.exports;
}
console.log('Building a live index-one publication through the common Solve handler...');
const python=spawnSync('python',['tests/test_f3_index1_dae.py','--publication'],{cwd:root,encoding:'utf8',maxBuffer:24*1024*1024,timeout:900000});
assert.equal(python.status,0,python.stderr||String(python.error));
const live=JSON.parse(python.stdout);
fs.writeFileSync(path.join(root,'.tmp/f3-index1/publication.json'),JSON.stringify(live,null,2));
const {readDerivedExecution}=load(path.join(here,'motores/modelo/derivedExecution.ts'));
const {readCompilationReport}=load(path.join(here,'motores/modelo/compilation.ts'));
const {leerResultados}=load(path.join(here,'motores/resultados/lector.ts'));
const {commonSource,derivedSourceIdentity,selectedDerivedModel,reconcileDerived}=load(path.join(here,'app/models/derivedSelection.ts'));
const selection=readDerivedExecution(live.model.motores.derivedExecution,live.model.datos);
assert.equal(selection.version,4);
const report=readCompilationReport(live.result.procedencia.compilation);
assert.equal(report.derivedExecution.nonlinearBlock.method,'damped_newton');
assert.ok(report.strategy.steps.some(s=>s.id==='nonlinear-block'));
leerResultados(live.result);
assert.equal(live.result.procedencia.assessment.initialization.status,'compatible');
const badSelections=[s=>{delete s.dae;},s=>{s.dae.driftTolerance=1e-8;},s=>{s.dae.freeStates=true;},s=>{delete s.dae.stateBounds[s.states[0].quantityId];},s=>{s.version=2;},s=>{delete s.nonlinear;},s=>{s.nonlinear.maxIterations=31;},s=>{s.nonlinear.residualTolerance=NaN;},s=>{delete s.nonlinear.variables[s.algebraic[0].quantityId];},s=>{s.algebraic[1].equationId=s.algebraic[0].equationId;},s=>{s.nonlinear.fallback=true;}];
for(const mutate of badSelections){const bad=structuredClone(selection);mutate(bad);assert.throws(()=>readDerivedExecution(bad));}
const badReports=[r=>{delete r.derivedExecution.dae;},r=>{r.derivedExecution.dae.index=2;},r=>{r.derivedExecution.dae.method='IDA';},r=>{delete r.derivedExecution.nonlinearBlock;},r=>{r.derivedExecution.nonlinearBlock.method='fallback';},r=>{r.derivedExecution.nonlinearBlock.rows.reverse();},r=>{r.derivedExecution.nonlinearBlock.initialization.residualNorm=NaN;},r=>{r.derivedExecution.nonlinearBlock.initialization.formulationSignature='0'.repeat(64);}];
for(const mutate of badReports){const bad=structuredClone(report);mutate(bad);assert.throws(()=>readCompilationReport(bad));}
const badResults=[r=>{delete r.procedencia.nonlinearDiagnostics;},r=>{delete r.procedencia.daeDiagnostics;},r=>{r.procedencia.daeDiagnostics.maxResidual=1;},r=>{r.procedencia.daeDiagnostics.acceptedChecks=-1;},r=>{r.procedencia.nonlinearDiagnostics.publishedSamples++;},r=>{r.procedencia.nonlinearDiagnostics.lastEvaluation.residualNorm=NaN;},r=>{r.procedencia.nonlinearDiagnostics.lastEvaluation.formulationSignature='0'.repeat(64);},r=>{r.procedencia.nonlinearDiagnostics.extra=true;}];
for(const mutate of badResults){const bad=structuredClone(live.result);mutate(bad);assert.throws(()=>leerResultados(bad));}
const model={id:live.model.id,nombre:live.model.nombre,commonModel:live.model,resultado:{marker:true},resultadoRef:'saved'};
model.derivedSelection={version:1,sourceSignature:derivedSourceIdentity(commonSource(model)),selection};
assert.deepEqual(selectedDerivedModel(model).motores.derivedExecution,selection);
const changed=structuredClone(model);changed.derivedSelection.selection.nonlinear.residualTolerance=1e-11;
assert.equal(reconcileDerived(model,changed).resultadoRef,undefined);
const edit=structuredClone(model);edit.commonModel.datos['solve.firstConductance'].declaracion.texto='13';
assert.throws(()=>selectedDerivedModel(edit));
console.log('Index-one live readers, 27 malformed payloads, assessment and selection/data invalidation pass.');
