// Real common Python publication: strict contracts, shared lifecycle and scalar export.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {createHash} from 'node:crypto';
import ts from 'typescript';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.dirname(here),require=createRequire(import.meta.url),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(file.endsWith('.json'))return {default:JSON.parse(fs.readFileSync(file,'utf8'))};
  if(file.endsWith('.css'))return {default:{}};
  if(cache.has(file))return cache.get(file).exports;
  const loadedModule={exports:{}};cache.set(file,loadedModule);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('module','exports','require',code)(loadedModule,loadedModule.exports,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id));return loadedModule.exports;
}
const live=JSON.parse(fs.readFileSync(path.join(root,'.tmp/f3-steady/publication.json'),'utf8'));
const {readDerivedExecution}=load(path.join(here,'motores/modelo/derivedExecution'));
const {readCompilationReport}=load(path.join(here,'motores/modelo/compilation'));
const {leerResultados}=load(path.join(here,'motores/resultados/lector'));
const {steadySignature,steadyResultSignature,steadyCSV}=load(path.join(here,'motores/modelo/steadyContract'));
const {leerModeloComun}=load(path.join(here,'motores/modelo/lector'));
const {commonSource,derivedSourceIdentity,selectedDerivedModel,reconcileDerived}=load(path.join(here,'app/models/derivedSelection'));
assert.equal(steadySignature('abc'),createHash('sha256').update('"abc"').digest('hex'));
leerModeloComun(live.model);leerResultados(live.result);
const selection=readDerivedExecution(live.model.motores.derivedExecution,live.model.datos),report=readCompilationReport(live.result.procedencia.compilation);
assert.equal(selection.version,5);assert.equal(report.version,2);assert.equal(report.time,undefined);
assert.equal(report.formulationSignature,steadySignature(selection));
const badSelections=[s=>{s.version=4;},s=>{s.initialValues={};},s=>{delete s.invariants;},s=>{s.unknowns.pop();},s=>{s.nonlinear.maxIterations=31;},s=>{s.nonlinear.stepTolerance=NaN;},s=>{s.algebraic[0].equationId=s.algebraic[1].equationId;},s=>{s.nonlinear.fallback=true;}];
for(const mutate of badSelections){const bad=structuredClone(selection);mutate(bad);assert.throws(()=>readDerivedExecution(bad));}
for(const mutate of [r=>{r.time={finalTime:1};},r=>{r.variables.reverse();},r=>{r.variables[0].scaleSI=0;},r=>{r.residualRows.pop();},r=>{r.selection.nonlinear.residualTolerance=1;},r=>{r.invariants[0].dataId='invented';}]){const bad=structuredClone(report);mutate(bad);assert.throws(()=>readCompilationReport(bad));}
const mutations=[r=>{r.procedencia.steadyDiagnostics.globalUniqueness='proved';},r=>{r.procedencia.steadyDiagnostics.smallestSingularValue=0;},r=>{r.procedencia.steadyDiagnostics.solver.residualNorm=1;},r=>{r.procedencia.steadyDiagnostics.solver.iterations=-1;},r=>{r.series[0].valores=[1];},r=>{r.series[0].unidadSI='K';},r=>{r.verificaciones[0].valor=1;},r=>{r.estado='parcial';},r=>{r.procedencia.steadyDiagnostics.equationIds.reverse();}];
for(const resign of [false,true])for(const mutate of mutations){const bad=structuredClone(live.result);delete bad.procedencia.assessment;mutate(bad);if(resign)bad.procedencia.steadyDiagnostics.resultSignature=steadyResultSignature(bad);assert.throws(()=>leerResultados(bad));}
const changedScalar=structuredClone(live.result);changedScalar.series[0].valores++;assert.throws(()=>leerResultados(changedScalar));
const csv=steadyCSV(live.result);assert.equal(csv.split('\n')[0],'quantity,unit,value');assert.ok(csv.includes('25500'));assert.equal(csv.split('\n').length,live.result.series.length+1);
const storage=new Map();globalThis.localStorage={getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v)};globalThis.window={dispatchEvent:()=>true};
const {nuevaHoja,guardarHoja,leerHojas}=load(path.join(here,'app/motor/hojasMotor'));
const {firmaHoja}=load(path.join(here,'app/motor/modeloHojaMotor'));
const {derivedResult,resolverHojaEngine}=load(path.join(here,'app/motor/resolverEngine'));
const {validateSavedSteady,guardarResultadoMotor,leerResultadoMotor,saveRejectedAttempt,loadRejectedAttempt}=load(path.join(here,'app/motor/resultadosMotor'));
const {ModelDiagnosticError}=load(path.join(here,'motores/modelo/assessment'));
const model={...nuevaHoja(live.model.nombre),id:live.model.id,commonModel:live.model};
model.derivedSelection={version:1,sourceSignature:derivedSourceIdentity(commonSource(model)),selection};guardarHoja(model);
assert.deepEqual(selectedDerivedModel(leerHojas().find(m=>m.id===model.id)),live.model);
const wrapped=derivedResult(model,live.result);validateSavedSteady(wrapped,model.id,firmaHoja(model));assert.equal(wrapped.version,2);assert.deepEqual(wrapped.tiempos,[]);
for(const mutate of [r=>{r.version=1;},r=>{r.tiempos=[0];},r=>{delete r.commonResult;},r=>{r.modo='temporal';}]){const bad=structuredClone(wrapped);mutate(bad);assert.throws(()=>validateSavedSteady(bad,model.id,firmaHoja(model)));}
const saved=guardarHoja({...model,resultado:wrapped,resultadoRef:{firma:wrapped.firma,estado:'resuelto',fecha:new Date().toISOString()}});
for(const mutate of [m=>{m.commonModel.datos['steady.heatInput'].declaracion.texto='121';},m=>{m.commonModel.motores.equationWorkbench.cursor--;},m=>{m.derivedSelection.selection.nonlinear.stepTolerance/=10;}]){const edited=structuredClone(saved);mutate(edited);assert.equal(reconcileDerived(saved,edited).resultadoRef,undefined);}
// Minimal asynchronous IDB transaction double: exercise the production storage code.
const records=new Map();globalThis.indexedDB={open:()=>{const request={};queueMicrotask(()=>{request.result={close(){},transaction(){const t={};let aborted=false;const complete=()=>setTimeout(()=>{if(!aborted)t.oncomplete?.();},0);t.abort=()=>{aborted=true;t.onabort?.();};t.objectStore=()=>({put(value,key){records.set(JSON.stringify(key),structuredClone(value));complete();},get(key){const r={};queueMicrotask(()=>{r.result=structuredClone(records.get(JSON.stringify(key)));r.onsuccess?.();});return r;}});return t;}};request.onsuccess();});return request;}};
await guardarResultadoMotor(model.id,wrapped);assert.deepEqual(await leerResultadoMotor(model.id,wrapped.firma),wrapped);
const abort=new AbortController();abort.abort();await assert.rejects(()=>guardarResultadoMotor(model.id,wrapped,abort.signal));
const error=new ModelDiagnosticError('No admissible trial.',422,{diagnostics:[{code:'nonlinear_domain',path:'motores.derivedExecution',message:'No admissible trial.'}]});
await saveRejectedAttempt(model.id,wrapped.firma,error);assert.equal((await loadRejectedAttempt(model.id,wrapped.firma)).operation,'solve');assert.deepEqual(await leerResultadoMotor(model.id,wrapped.firma),wrapped);
const cancelled=new AbortController();cancelled.abort();await assert.rejects(()=>resolverHojaEngine(model,{signal:cancelled.signal,transporte:async()=>live.result}));
const response=await resolverHojaEngine(model,{transporte:async()=>live.result});assert.deepEqual(response.commonResult.series,live.result.series);
const {default:CompilationSummary}=load(path.join(here,'app/models/CompilationSummary'));
const html=require('react-dom/server').renderToStaticMarkup(require('react').createElement(CompilationSummary,{report}));assert.ok(html.includes('Steady state'));assert.ok(!html.includes('final solver time'));
console.log('Steady live Python/TS contracts, tampering, scalar CSV, shared storage/reload, cancellation and invalidation pass.');
