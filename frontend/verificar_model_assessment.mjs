// Live Python publications, real TypeScript clients/readers and SSR: no browser.
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
  if(file.endsWith('.css'))return {default:{}};
  if(file.endsWith('.json'))return {default:JSON.parse(fs.readFileSync(file,'utf8'))};
  if(cache.has(file))return cache.get(file).exports;
  const loadedModule={exports:{}};cache.set(file,loadedModule);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('module','exports','require','process',code)(loadedModule,loadedModule.exports,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id),process);
  return loadedModule.exports;
}
const script=`
import sys,json,copy
sys.path.insert(0,'tests')
from test_explicit_initialization import fixture
from test_common_admission import model
from core.compilador.assessment import assess_model
from backend.api_modelo import resolver_modelo
from fastapi import HTTPException
valid=fixture([('2','kg')]); negative=fixture([('-1','kg')]); missing=fixture([])
try: resolver_modelo({'modelo':negative,'assessmentVersion':1})
except HTTPException as e: rejection={'detail':e.detail}
results=[]
for temperature in (None,'1000','100'):
 value=model(horizon='1')
 if temperature:
  value['datos']['boundary.temperature']=copy.deepcopy(value['datos']['volumen.A.T0'])
  value['datos']['boundary.temperature']['declaracion']['texto']=temperature
  value['intercambios'][0]['temperaturaFronteraId']='boundary.temperature'
 results.append(resolver_modelo({'modelo':value,'assessmentVersion':1}))
print(json.dumps({'valid':valid,'negative':negative,'missing':missing,'assessment':assess_model(valid),
 'pending':assess_model(missing),'rejection':rejection,'result':resolver_modelo({'modelo':valid,'assessmentVersion':1}),
 'certificates':results}))
`;
const python=spawnSync('python',['-c',script],{cwd:root,encoding:'utf8',maxBuffer:24*1024*1024});
assert.equal(python.status,0,python.stderr);
const live=JSON.parse(python.stdout);
const {readAssessment,assessmentLines,ModelDiagnosticError}=load(path.join(here,'motores/modelo/assessment'));
const {leerResultados}=load(path.join(here,'motores/resultados/lector'));
const service=load(path.join(here,'motores/modelo/servicioModelo'));
for(const a of [live.assessment,live.pending,live.rejection.detail.assessment])assert.equal(readAssessment(a),a);
assert.equal(live.pending.structure.status,'complete');assert.equal(live.pending.initialization.status,'pending');
for(const result of [live.result,...live.certificates])assert.equal(leerResultados(result),result);
assert.deepEqual(live.certificates.map(r=>r.procedencia.assessment.certification.status),['not_evaluable','passed','failed']);
assert.ok(live.certificates.every(r=>r.estado==='resuelto'));
const corruptions=[
 a=>a.version=2,a=>a.structure.code='INITIALIZATION_COMPATIBLE',a=>a.initialization.sourceSignature='0'.repeat(64),
 a=>a.structure.status='solved',a=>a.initialization.diagnostics=[{code:'X',message:'Y'}],
 a=>a.certification.scope.samples=99,a=>a.certification.status='passed',a=>a.extra=true,
 a=>a.inspection.variables=null,a=>a.sourceSignature='stale',a=>a.resultSignature='not-a-digest',
 a=>a.initialization.scope.timeSI=Infinity,
];
for(const corrupt of corruptions){const result=structuredClone(live.result);corrupt(result.procedencia.assessment);assert.throws(()=>leerResultados(result));}
const old=structuredClone(live.result);delete old.procedencia.assessment;
assert.equal(leerResultados(old),old);assert.ok(assessmentLines().every(line=>line.includes('Not evaluated')));

const originalFetch=globalThis.fetch,calls=[];
let response=live.rejection,status=422;
globalThis.fetch=async(url,options)=>{calls.push({url,body:JSON.parse(options.body),signal:options.signal});return new Response(JSON.stringify(response),{status,headers:{'content-type':'application/json'}});};
try{
  await assert.rejects(service.transporteHTTP(live.negative),error=>{
    assert.ok(error instanceof ModelDiagnosticError);assert.equal(error.httpStatus,422);
    assert.equal(error.code,'no_soportado');assert.deepEqual(error.diagnostics,live.rejection.detail.diagnostics);
    assert.deepEqual(error.assessment,live.rejection.detail.assessment);return true;
  });
  assert.equal(calls.at(-1).body.assessmentVersion,1);
  response=live.pending;status=200;
  await assert.rejects(service.requestCompilation({modelo:live.missing}),error=>{
    assert.equal(error.assessment.structure.status,'complete');assert.equal(error.assessment.initialization.code,'INITIALIZATION_MISSING_DATA');return true;
  });
  assert.ok(calls.at(-1).url.endsWith('/assessment'));
  response=live.assessment;
  assert.deepEqual(await service.requestCompilation({modelo:live.valid}),live.assessment.compilation);
  await service.requestAssessment(live.valid,undefined,false);assert.equal(calls.at(-1).body.initialize,false);
  response=live.result;assert.deepEqual(await service.resolverModelo(live.valid),live.result);
  response=live.rejection;status=422;
  await assert.rejects(service.requestCompilation({solicitudV2:{}}),error=>error.code==='no_soportado'&&error.assessment.initialization.status==='incompatible');
  assert.ok(calls.at(-1).url.endsWith('/compilation'));
  response=structuredClone(live.assessment);response.modelId='other';status=200;
  await assert.rejects(service.requestAssessment(live.valid),/another model/);
  response={detail:{codigo:'native_rejection',diagnostics:[{code:'INITIALIZATION_OUT_OF_DOMAIN',message:'Outside domain',path:'volumenes[0].inicial',initializationStatus:'incompatible',nativeCode:'MOTOR_ENS_INICIAL'}]}};status=422;
  await assert.rejects(service.requestCompilation({solicitudV2:{}}),error=>{
    assert.equal(error.code,'native_rejection');assert.equal(error.diagnostics[0].initializationStatus,'incompatible');
    assert.equal(error.diagnostics[0].nativeCode,'MOTOR_ENS_INICIAL');assert.equal(error.diagnostics[0].path,'volumenes[0].inicial');return true;
  });
  // Negative control: the repository's previous client discards this same
  // server diagnosis. Load it in memory; do not replace a working-tree file.
  const previous=spawnSync('git',['show','d5b9a120916732727b22a078b1bed6dd5c167848:frontend/motores/modelo/servicioModelo.ts'],{cwd:root,encoding:'utf8'});
  assert.equal(previous.status,0,previous.stderr);
  const baseline={exports:{}};
  const code=ts.transpileModule(previous.stdout,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  new Function('module','exports','require','process',code)(baseline,baseline.exports,name=>load(path.resolve(here,'motores/modelo',name)),process);
  response=live.rejection;
  await assert.rejects(baseline.exports.transporteHTTP(live.negative),error=>{
    assert.equal(error.assessment,undefined);assert.equal(error.diagnostics,undefined);return true;
  });
}finally{globalThis.fetch=originalFetch;}

const {createElement}=require('react'),{renderToStaticMarkup}=require('react-dom/server');
const {default:AssessmentText}=load(path.join(here,'app/models/AssessmentText'));
const error=new ModelDiagnosticError('Rejected',422,live.rejection.detail);
const html=renderToStaticMarkup(createElement(AssessmentText,{error}));
for(const text of ['Structure','Initialization','Certification','INITIALIZATION_OUT_OF_DOMAIN','matematico.condiciones','incompatible'])assert.ok(html.includes(text),text);
assert.ok(!/<(section|aside|h1|h2)/.test(html),'Assessment text must not add a panel or layout.');
const failed=renderToStaticMarkup(createElement(AssessmentText,{assessment:live.certificates[2].procedencia.assessment}));
assert.ok(failed.includes('CERTIFICATION_FAILED'));assert.ok(failed.includes('Published scope'));

// Minimal isolated IndexedDB harness: real store code, structured clones and
// transaction completion. No user database or browser is opened.
const records=new Map();
globalThis.indexedDB={open(){const request={};queueMicrotask(()=>{request.result={close(){},transaction(){
  const tx={objectStore(){return {put(value,key){records.set(JSON.stringify(key),structuredClone(value));queueMicrotask(()=>tx.oncomplete?.());},
    get(key){const read={};queueMicrotask(()=>{read.result=structuredClone(records.get(JSON.stringify(key)));read.onsuccess?.();});return read;}};},abort(){tx.onabort?.();}};return tx;}};request.onsuccess();});return request;}};
const store=load(path.join(here,'app/motor/resultadosMotor'));
const id=live.valid.id,signature='physical-revision-1';
const saved={firma:signature,commonResult:live.result};
await store.guardarResultadoMotor(id,saved);
await store.saveRejectedAttempt(id,signature,error);
assert.deepEqual(await store.leerResultadoMotor(id,signature),saved,'Rejection must not overwrite the saved trajectory.');
const attempt=await store.loadRejectedAttempt(id,signature);
assert.deepEqual(attempt.detail,live.rejection.detail);
assert.equal(attempt.operation,'solve');
await store.saveRejectedAttempt(id,signature,error,undefined,'compilation');
assert.equal((await store.loadRejectedAttempt(id,signature)).operation,'compilation');
assert.deepEqual(await store.leerResultadoMotor(id,signature),saved);
assert.equal(await store.loadRejectedAttempt(id,'edited-revision'),undefined,'Edited models cannot reuse rejected-attempt evidence.');
assert.throws(()=>store.readRejectedAttempt(attempt,id,'edited-revision'),/stale/);
const aborted=new AbortController();aborted.abort();
await assert.rejects(store.saveRejectedAttempt(id,'cancelled',error,aborted.signal));
assert.equal(await store.loadRejectedAttempt(id,'cancelled'),undefined);
const corruptSaved=structuredClone(saved);corruptSaved.commonResult.procedencia.assessment.certification.code='CERTIFICATION_PASSED';
await assert.rejects(store.guardarResultadoMotor(id,corruptSaved));
const worksheet=fs.readFileSync(path.join(here,'app/models/ModelWorksheet.tsx'),'utf8');
assert.ok(worksheet.includes('data-model-worksheet="canonical"'));assert.equal((worksheet.match(/<aside/g)??[]).length,1);
console.log('F0 frontend assessment: live Python publications; 12 corruptions rejected; typed compilation/Solve clients; inline SSR; isolated result/attempt storage and stale/cancel controls passed.');
