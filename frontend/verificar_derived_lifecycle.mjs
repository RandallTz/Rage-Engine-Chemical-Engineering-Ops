// Common storage/selection/Results lifecycle, with isolated in-memory storage.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import ts from 'typescript';
const directory=path.dirname(fileURLToPath(import.meta.url)),root=path.dirname(directory),require=createRequire(import.meta.url),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(file.endsWith('.json'))return {default:JSON.parse(fs.readFileSync(file,'utf8'))};
  if(file.endsWith('.css'))return {default:{}};
  if(cache.has(file))return cache.get(file).exports;
  const loadedModule={exports:{}};cache.set(file,loadedModule);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('exports','module','require','process',code)(loadedModule.exports,loadedModule,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id),process);
  return loadedModule.exports;
}
const storage=new Map();
globalThis.localStorage={getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)};
globalThis.window={dispatchEvent:()=>true};
const {nuevaHoja,guardarHoja,leerHojas,CLAVE_HOJAS}=load(path.join(directory,'app/motor/hojasMotor'));
const {commonSource,derivedSourceIdentity,selectedDerivedModel}=load(path.join(directory,'app/models/derivedSelection'));
const {firmaHoja}=load(path.join(directory,'app/motor/modeloHojaMotor'));
const {derivedResult,resolverHojaEngine}=load(path.join(directory,'app/motor/resolverEngine'));
const {modelRequest}=load(path.join(directory,'app/models/modelRequest'));
const {leerModeloComun}=load(path.join(directory,'motores/modelo/lector'));
const {publications}=JSON.parse(fs.readFileSync(path.join(root,'.tmp/m1-u1-publications.json'),'utf8'));
let checks=0;function check(value,message){assert.ok(value,message);checks++;}
for(const name of 'abc'){
  const publication=publications[`${name}.RK45.1`],common=structuredClone(publication.model);
  const sheet={...nuevaHoja(common.nombre),id:common.id,commonModel:common};
  assert.deepEqual(leerModeloComun(common),common);
  guardarHoja(sheet);
  const selected={...sheet,derivedSelection:{version:1,sourceSignature:derivedSourceIdentity(commonSource(sheet)),selection:common.motores.derivedExecution}};
  guardarHoja(selected);
  check(selectedDerivedModel(leerHojas().find(item=>item.id===sheet.id)).motores.derivedExecution.sourceSignature===common.motores.derivedExecution.sourceSignature,'Selection persists through the common store');
  assert.deepEqual(modelRequest(selected,true).modelo,selectedDerivedModel(selected));
  const adapted=derivedResult(selected,publication.result);
  if(process.argv.includes('--service')){
    const executed=await resolverHojaEngine(selected,{transporte:async common=>{
      const response=await fetch('http://127.0.0.1:8010/modelo/resolver',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({modelo:common}),signal:AbortSignal.timeout(120000)});
      const value=await response.json();assert.equal(response.status,200,JSON.stringify(value));return value;
    }});
    assert.deepEqual(executed.seriesEvaluadas,adapted.seriesEvaluadas);
    check(executed.firma===firmaHoja(selected),'Live common API result matches the stored selection and physical reference publication');
  }
  check(adapted.seriesEvaluadas.length===publication.result.series.length,'All published series and units survive Results adaptation');
  check(adapted.compilation.equationWorkbench.equations.length===publication.report.equationWorkbench.equations.length,'Exact operation provenance survives Results adaptation');
  const withResult=guardarHoja({...selected,resultado:adapted,resultadoRef:{firma:adapted.firma,estado:'resuelto',fecha:new Date().toISOString()}});
  const renamed=guardarHoja({...withResult,nombre:'Renamed display label'});
  check(firmaHoja(renamed)===firmaHoja(withResult)&&!!renamed.resultadoRef,'Renaming preserves execution and saved results');
  const studied=guardarHoja({...withResult,commonModel:{...common,estudio:{...common.estudio,rtol:1e-10}}});
  check(!studied.resultadoRef&&!studied.resultado,'Numerical settings invalidate saved execution');
  assert.doesNotThrow(()=>selectedDerivedModel(studied));
  for(const mutate of [
    model=>{const datum=Object.values(model.commonModel.datos)[0];datum.declaracion.texto='2';},
    model=>{Object.values(model.commonModel.datos)[0].declaracion.unidad='g';},
    model=>{model.commonModel.volumenes[0].termodinamica.motivo='Changed physical closure premise';},
    model=>{model.commonModel.motores.equationWorkbench.cursor--;},
  ]){
    guardarHoja(withResult);const changed=structuredClone(withResult);mutate(changed);const saved=guardarHoja(changed);
    check(!saved.resultadoRef&&!saved.resultado,'Scientific edits clear execution');
    assert.throws(()=>selectedDerivedModel(saved),/outdated/);
    check(saved.derivedSelection!==undefined,'Stale selection remains inspectable instead of silently falling back');
  }
  guardarHoja(withResult);
  check(JSON.parse(storage.get(CLAVE_HOJAS)).some(item=>item.id===sheet.id&&item.derivedSelection),'Serialized selection survives reload');
  fs.writeFileSync(path.join(root,`.tmp/m1-u1-${name}.model.json`),JSON.stringify({format:'rage.model-file',version:1,model:sheet},null,2));
}
console.log(JSON.stringify({checks,cases:3,storage:'isolated',results:'preserved',scientificInvalidation:'passed',labelIdentity:'passed'}));

// Render actual Python compilation publications, including the executed AST,
// parameter table and scaled maps. Internal identities stay in the contract.
const {readCompilationReport}=load(path.join(directory,'motores/modelo/compilation'));
const {default:CompilationSummary}=load(path.join(directory,'app/models/CompilationSummary'));
const {createElement}=require('react');
const {renderToStaticMarkup}=require('react-dom/server');
const bridge=JSON.parse(fs.readFileSync(path.join(root,'.tmp/m1-bridge-publications.json'),'utf8')).publications;
for(const [name,publication] of Object.entries(bridge)){
  const report=readCompilationReport(publication.report);
  check(Object.keys(report.symbolLabels).length>0,'Compiler publishes physical symbol labels');
  const html=renderToStaticMarkup(createElement(CompilationSummary,{report}));
  check(!/datum.{0,12}[0-9a-f]{10}|x[0-9a-f]{10}/.test(html),'Executed equations and variable/data labels hide internal IDs: '+name);
  const malformed=structuredClone(report);malformed.symbolLabels[report.time.id]=123;
  assert.throws(()=>readCompilationReport(malformed),/symbol labels/);
}
const matter=JSON.parse(fs.readFileSync(path.join(root,'.tmp/matter-lowering-publications.json'),'utf8'));
for(const publication of Object.values(matter)){
  const report=readCompilationReport(publication.report);
  const sheet={...nuevaHoja(publication.model.nombre),id:publication.model.id,commonModel:publication.model};
  const selected={...sheet,derivedSelection:{version:1,sourceSignature:derivedSourceIdentity(commonSource(sheet)),selection:publication.model.motores.derivedExecution}};
  guardarHoja(selected);
  const restored=leerHojas().find(item=>item.id===sheet.id);
  assert.deepEqual(selectedDerivedModel(restored),publication.model);
  check(derivedResult(restored,publication.result).compilation.signature===report.signature,'New matter selection and run survive the same storage/Results path');
}

// Strict Mode setup/cleanup/setup and equivalent property order share one
// request. A numerical edit must start a fresh request for each endpoint.
const {requestFormulation}=load(path.join(directory,'app/models/formulationRequests'));
const originalFetch=globalThis.fetch;
const calls=[];
globalThis.fetch=async(url,options)=>{
  calls.push({url,body:options.body});
  await new Promise(resolve=>setTimeout(resolve,5));
  return new Response(JSON.stringify({value:JSON.parse(options.body)}),{status:200});
};
try{
  for(const endpoint of ['formulation-summary','equation-workbench','derived-execution-source']){
    const before=calls.length;
    const [first,second]=await Promise.all([
      requestFormulation(endpoint,JSON.stringify({modelo:{id:'request-test',data:1}})),
      requestFormulation(endpoint,JSON.stringify({modelo:{data:1,id:'request-test'}})),
    ]);
    assert.deepEqual(await first.json(),await second.json());
    check(calls.length===before+1,'Effect replay sends one '+endpoint+' request');
    const [edited,replayed]=await Promise.all([
      requestFormulation(endpoint,JSON.stringify({modelo:{id:'request-test',data:2}})),
      requestFormulation(endpoint,JSON.stringify({modelo:{id:'request-test',data:2}})),
    ]);
    assert.deepEqual(await edited.json(),await replayed.json());
    check(calls.length===before+2,'A data edit sends exactly one new '+endpoint+' request');
  }
  let attempts=0;
  globalThis.fetch=async()=>{attempts++;return new Response('{}',{status:attempts===1?422:200});};
  await requestFormulation('equation-workbench','{"retry":true}');
  await requestFormulation('equation-workbench','{"retry":true}');
  check(attempts===2,'Rejected requests remain retryable');
}finally{globalThis.fetch=originalFetch;}
check(!fs.readFileSync(path.join(directory,'tsconfig.json'),'utf8').includes('.next-u1'),'No temporary U1 build entries remain');
console.log(JSON.stringify({checks,physicalSymbols:'passed',newMatterLifecycle:'passed',transformRequestDeduplication:'passed'}));
