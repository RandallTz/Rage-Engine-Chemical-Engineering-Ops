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
const live=JSON.parse(fs.readFileSync(path.join(root,'.tmp/steady-transform/publication.json'),'utf8'));
const {readSteadyTransform}=load(path.join(here,'motores/modelo/steadyTransform'));
const {applySteadyTransformResult,selectedDerivedModel,reconcileDerived}=load(path.join(here,'app/models/derivedSelection'));
const {nuevaHoja}=load(path.join(here,'app/motor/hojasMotor'));
let checks=0;
const response=readSteadyTransform(live.response,live.source);checks++;
for(const change of [v=>v.version=2,v=>v.extra=true,v=>v.dynamicSignature='0'.repeat(64),v=>v.dynamicSelection.states.pop(),v=>v.model.nombre='changed',v=>v.model.datos[Object.keys(live.source.datos)[0]].declaracion.texto='99']){
 const bad=structuredClone(response);change(bad);assert.throws(()=>readSteadyTransform(bad,live.source));checks++;
}
const model={...nuevaHoja(live.source.nombre),id:live.source.id,commonModel:live.source};
const transformed=applySteadyTransformResult(model,response);
assert.deepEqual(selectedDerivedModel(transformed),response.model);checks++;
assert.deepEqual(transformed.commonModel.motores.derivedExecution,live.source.motores.derivedExecution);checks++;
assert.deepEqual(transformed.commonModel.estudio,live.source.estudio);checks++;
const edited=structuredClone(transformed);edited.commonModel.motores.derivedExecution.initialEquations.push('changed');
assert.throws(()=>selectedDerivedModel(edited));checks++;
assert.equal(reconcileDerived(transformed,{...edited,resultadoRef:{firma:'old'}}).resultadoRef,undefined);checks++;
const sourceText=fs.readFileSync(path.join(here,'app/models/DerivedExecution.tsx'),'utf8');
assert.ok(sourceText.includes('Steady state (zero accumulation)')&&sourceText.includes('AssessmentText error={transformError}'));checks++;
assert.ok(sourceText.includes('Zero accumulation handoff'));checks++;
const {readSteadyResult,steadyResultSignature}=load(path.join(here,'motores/modelo/steadyContract'));
for(const fixture of ['package','equipment']){
 const livePackage=JSON.parse(fs.readFileSync(path.join(root,`.tmp/steady-transform/${fixture}.json`),'utf8'));
 readSteadyTransform(livePackage.response,livePackage.source);checks++;
 readSteadyResult(livePackage.result);checks++;
 for(const mutate of [r=>delete r.report.thermodynamicClosures,r=>r.report.thermodynamicClosures=[],r=>r.report.thermodynamicClosures[0].extra=true,r=>r.report.thermodynamicClosures[0].outputs[0].id='',r=>r.report.thermodynamicClosures.push(r.report.thermodynamicClosures[0]),r=>r.report.thermodynamicClosures[0].constants[0].value=Infinity]){
  const bad=structuredClone(livePackage.response);mutate(bad);assert.throws(()=>readSteadyTransform(bad,livePackage.source));checks++;
 }
 for(const mutate of [r=>delete r.procedencia.steadyDiagnostics.thermodynamicClosures,r=>r.procedencia.steadyDiagnostics.thermodynamicClosures[0].volumeId='other',r=>r.series.find(v=>v.id.startsWith('closure.')).unidadSI='wrong',r=>r.verificaciones.find(v=>v.id.startsWith('thermodynamics.closure.')).valor=2]){
  const bad=structuredClone(livePackage.result);mutate(bad);bad.procedencia.steadyDiagnostics.resultSignature=steadyResultSignature(bad);assert.throws(()=>readSteadyResult(bad));checks++;
 }
}
console.log(JSON.stringify({checks,scope:'Steady Transform contract, source preservation, handoff and invalidation'}));
