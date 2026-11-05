// Headless acceptance of the production Model -> Transform -> Solve -> Results client.
// Usage: NEXT_PUBLIC_API_URL=http://127.0.0.1:<own-port> node frontend/verificar_demo02_app_flow.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import ts from 'typescript';
import http from 'node:http';
const api=new URL(process.env.NEXT_PUBLIC_API_URL??'http://127.0.0.1:8018');
assert.ok(['127.0.0.1','localhost'].includes(api.hostname)&&!['3000','8004','8005',''].includes(api.port),'Use an isolated local backend port.');
process.env.NEXT_PUBLIC_API_URL=api.origin;
// Node's bundled fetch has a separate 300 s response-header limit, unlike browser
// fetch. Native HTTP here preserves the production module's AbortSignal deadline.
// This is a real transport, with no substituted responses or numerical behavior.
assert.equal(api.protocol,'http:');
globalThis.fetch=(url,options={})=>new Promise((resolve,reject)=>{
  const target=new URL(url);assert.equal(target.origin,api.origin);
  const request=http.request(target,{method:options.method,headers:options.headers,signal:options.signal},response=>{
    const chunks=[];response.on('data',chunk=>chunks.push(chunk));response.on('error',reject);
    response.on('end',()=>resolve(new Response(Buffer.concat(chunks),{status:response.statusCode,headers:response.headers})));
  });
  request.on('error',reject);request.end(options.body);
});
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.dirname(here),require=createRequire(import.meta.url),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(file.endsWith('.json'))return {default:JSON.parse(fs.readFileSync(file,'utf8'))};
  if(file.endsWith('.css'))return {default:{}};
  if(cache.has(file))return cache.get(file).exports;
  const module={exports:{}};cache.set(file,module);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('module','exports','require',code)(module,module.exports,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id));return module.exports;
}
// Only browser storage/events are replaced. HTTP, validation and numerical services are real.
const storage=new Map();globalThis.localStorage={getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)};
globalThis.window=new EventTarget();
const {importModelFile}=load(path.join(here,'app/models/modelImport'));
const {guardarHoja,leerHojas}=load(path.join(here,'app/motor/hojasMotor'));
const {commonSource,derivedSourceIdentity,selectedDerivedModel,applySteadyTransformResult}=load(path.join(here,'app/models/derivedSelection'));
const {readDerivedExecution}=load(path.join(here,'motores/modelo/derivedExecution'));
const {describeCompilation,resolverModelo}=load(path.join(here,'motores/modelo/servicioModelo'));
const {requestSteadyTransform}=load(path.join(here,'motores/modelo/steadyTransform'));
const {leerResultados}=load(path.join(here,'motores/resultados/lector'));
let checks=0;const evidence=[];
const output=path.join(root,'.tmp/demo02-app-results');fs.mkdirSync(output,{recursive:true});
if(!process.argv.includes('--stages-only')&&!process.argv.includes('--network-only'))for(const [demo,file] of (process.argv.includes('--cstr-only')?[['0.2','continuous-reactor']]:[['0.1','flash-drum'],['0.2','flash-drum'],['0.1','batch-reactor']])){
  console.log(`Demo ${demo}: import and validate`);
  let model=await importModelFile(JSON.parse(fs.readFileSync(path.join(root,`docs/ejemplos/demo-${demo}/${file}.rage-model.json`),'utf8')));checks++;
  // Solve horizon is editable data; the recorded deduction stays unchanged.
  if(file==='flash-drum')model.commonModel.datos[model.commonModel.estudio.tiempoId].declaracion.texto='6000';
  guardarHoja(model);
  const candidate=commonSource(model),selection=readDerivedExecution(model.commonModel.motores.derivedExecution,candidate.datos);
  candidate.motores.derivedExecution=selection;
  await describeCompilation(candidate);checks++;
  model=guardarHoja({...model,derivedSelection:{version:1,sourceSignature:derivedSourceIdentity(commonSource(model)),selection}});
  assert.deepEqual(selectedDerivedModel(leerHojas().find(m=>m.id===model.id)),candidate);checks++;
  console.log(`Demo ${demo}: dynamic solve`);
  const dynamic=leerResultados(await resolverModelo(selectedDerivedModel(model)));checks++;
  assert.equal(dynamic.estado,'resuelto');checks++;
  fs.writeFileSync(path.join(output,`demo-${demo}-${file}-dynamic.json`),JSON.stringify(dynamic));
  if(file==='batch-reactor'){evidence.push({demo,file,state:dynamic.estado});continue;}
  if(file==='flash-drum'){assert.ok(dynamic.eventos.some(e=>e.codigo==='aparicion_fase'&&/vapo[ru]/i.test(e.descripcion)));checks++;}
  else {assert.ok(dynamic.verificaciones.some(v=>v.id.startsWith('reactions.equilibrium_limit.')));checks++;}
  console.log(`Demo ${demo}: steady Transform and solve`);
  const transformed=await requestSteadyTransform(selectedDerivedModel(model));checks++;
  model=guardarHoja(applySteadyTransformResult(model,transformed));
  const steady=leerResultados(await resolverModelo(selectedDerivedModel(model)));checks++;
  assert.equal(steady.estado,'resuelto');checks++;
  fs.writeFileSync(path.join(output,`demo-${demo}-${file}-steady.json`),JSON.stringify(steady));
  const temperature=result=>{
    const series=result.series.find(s=>s.id.startsWith('closure.')&&s.unidadSI==='K');
    assert.ok(series,'A package temperature series is required.');checks++;
    return Array.isArray(series.valores)?series.valores.at(-1):series.valores;
  };
  const dynamicT=temperature(dynamic),steadyT=temperature(steady);
  assert.ok(Math.abs(steadyT-dynamicT)<0.05,`T steady ${steadyT}, dynamic ${dynamicT}`);checks++;
  if(demo==='0.1'){assert.ok(Math.abs(steadyT-362.54)<0.05);checks++;}
  evidence.push({demo,dynamicT,steadyT,events:dynamic.eventos.filter(e=>e.codigo==='aparicion_fase')});
}
if(!process.argv.includes('--results-only')&&!process.argv.includes('--network-only')&&!process.argv.includes('--cstr-only')){
 const {changeStageCount,expandStages,inspectExpandedNetwork}=load(path.join(here,'app/models/indexSetSolve'));
 const {nuevaHoja}=load(path.join(here,'app/motor/hojasMotor'));
 const original=JSON.parse(fs.readFileSync(path.join(root,'docs/ejemplos/demo-0.2/flash-drum.rage-model.json'),'utf8')).model.commonModel;
 const common=structuredClone(original);common.id='indexed-http-acceptance';
 common.datos['solve.stageCount']={magnitud:'stageCount',funcion:'estudio',declaracion:{texto:'3',unidad:'1'},origen:{propietarioId:'estudio',ruta:'stageCount'}};
 common.indexSet={format:'rage.index-set',version:1,id:'cascade',index:'j',countDataId:'solve.stageCount',templates:{generic:original},genericStage:'generic',variants:[],connections:[{outlet:'liquid',inlet:'feed',offset:1}],exposures:[{id:'feed',port:'feed',at:'first'},{id:'liquid',port:'liquid',at:'last'},{id:'vapour',port:'vapour',at:'each'},{id:'heat',port:'heat',at:'each'}]};
 let model={...nuevaHoja('Indexed HTTP acceptance'),id:common.id,commonModel:common};guardarHoja(model);
 for(const n of [2,3,5]){
   console.log(`Indexed stages: n=${n}`);
   const previous=structuredClone(model.commonModel.indexSet.templates);
   model=guardarHoja(changeStageCount({...model,derivedSelection:{version:1,sourceSignature:'old',selection:original.motores.derivedExecution},resultadoRef:{firma:'old'},transformation:{version:1}},String(n)));
   for(const key of ['derivedSelection','transformation','resultado','resultadoRef']){assert.equal(model[key],undefined);checks++;}
   assert.deepEqual(model.commonModel.indexSet.templates,previous);checks++;
   const expanded=await expandStages(model),again=await expandStages(model);assert.deepEqual(expanded,again);checks++;
   assert.equal(expanded.count,n);assert.equal(expanded.internalStreams.length,n-1);assert.equal(expanded.ports.length,2*n+2);checks+=3;
   const raw=await fetch(`${api.origin}/modelo/index-set-assessment`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(expanded)});const rejection=await raw.json();
   await assert.rejects(()=>inspectExpandedNetwork(expanded),error=>{assert.equal(error.httpStatus,raw.status);assert.deepEqual(error.detail,rejection.detail);assert.equal(error.message,rejection.detail.message);return true;});checks++;
 }
 for(const invalid of ['0','-1','2.5','', '257']){assert.throws(()=>changeStageCount(model,invalid));checks++;}
 evidence.push({scope:'indexed-stages',counts:[2,3,5],rejection:'index_set_not_lowered'});
}
if(process.argv.includes('--network-only')||process.argv.includes('--cstr-only')){
 const {nuevaHoja}=load(path.join(here,'app/motor/hojasMotor'));
 const {prepareIndexedExecution,solveIndexedExecution}=load(path.join(here,'motores/modelo/indexedExecution'));
 const {applyIndexed,indexedSource,indexedResult}=load(path.join(here,'app/models/indexedSelection'));
 const {changeStageCount}=load(path.join(here,'app/models/indexSetSolve'));
 const {firmaHoja}=load(path.join(here,'app/motor/modeloHojaMotor'));
 const {readChartLayout,prepareCharts}=load(path.join(here,'motores/resultados/chartSpecification'));
 for(const n of [2,3]){
  const reactor=process.argv.includes('--cstr-only'),indexId=reactor?'reactorTrain':'cascade';
  const started=Date.now(),original=JSON.parse(fs.readFileSync(path.join(root,`docs/ejemplos/demo-0.2/${reactor?'continuous-reactor':'flash-drum'}.rage-model.json`),'utf8')).model.commonModel;
  original.datos[original.estudio.tiempoId].declaracion.texto=reactor?'60000':'6000';original.estudio.metodoSolicitado='bdf';original.estudio.muestras=81;
  const common=structuredClone(original);common.id=`indexed-app-flow-${n}`;
  common.datos['solve.stageCount']={magnitud:'stageCount',funcion:'estudio',declaracion:{texto:String(n),unidad:'1'},origen:{propietarioId:'estudio',ruta:'stageCount'}};
  common.indexSet={format:'rage.index-set',version:1,id:'cascade',index:'j',countDataId:'solve.stageCount',templates:{generic:original},genericStage:'generic',variants:[],connections:[{outlet:'liquid',inlet:'feed',offset:1}],exposures:[{id:'feed',port:'feed',at:'first'},{id:'liquid',port:'liquid',at:'last'},{id:'vapour',port:'vapour',at:'each'},{id:'heat',port:'heat',at:'each'}]};
  if(reactor)Object.assign(common.indexSet,{id:indexId,connections:[{outlet:'product',inlet:'feed',offset:1}],exposures:[{id:'feed',port:'feed',at:'first'},{id:'product',port:'product',at:'last'},{id:'jacket',port:'jacket',at:'each'}]});
  let model=guardarHoja({...nuevaHoja(common.nombre),id:common.id,commonModel:common});const results={};
  for(const mode of ['dynamic','steady']){
   console.log(`Connected app flow n=${n}: prepare ${mode}`);
   const report=await prepareIndexedExecution(indexedSource(model),mode);checks++;
   model=guardarHoja(applyIndexed(model,report));assert.equal(model.indexedSelection.report.selection.mode,mode);checks++;
   console.log(`Connected app flow n=${n}: solve ${mode}`);
   const result=await solveIndexedExecution(indexedSource(model),report.selection);checks++;
   assert.equal(indexedResult(model,result,firmaHoja(model)).version,3);checks++;
   assert.equal(result.estado,'resuelto');assert.equal(result.indexedNetwork.count,n);checks+=2;
   assert.ok(result.verificaciones.filter(v=>!v.id.startsWith('reactions.equilibrium_limit.')).every(v=>v.valor<=v.tolerancia));checks++;
   if(reactor){assert.equal(result.verificaciones.filter(v=>v.id.startsWith('reactions.equilibrium_limit.')).length,n);checks++;}
   results[mode]=result;fs.writeFileSync(path.join(output,`${reactor?'cstr-network':'network'}-${n}-${mode}.json`),JSON.stringify(result));
  }
  if(!reactor){assert.ok(results.dynamic.eventos.some(event=>event.codigo==='aparicion_fase'));checks++;}
  const temperatures=[];
  for(let j=1;j<=n;j++){
   const id=`${indexId}.stage.${j}`,a=results.dynamic.series.find(s=>s.propietarioId===id&&s.id.includes('.closure.')&&s.unidadSI==='K'),b=results.steady.series.find(s=>s.id===a.id);
   assert.ok(Math.abs(a.valores.at(-1)-b.valores)<0.05);checks++;temperatures.push({stage:j,dynamic:a.valores.at(-1),steady:b.valores});
  }
  const profile=results.steady.indexedNetwork.profiles.find(p=>results.steady.series.find(s=>s.id===p.seriesId).unidadSI==='K');
  const layout={format:'rage.result-charts',version:1,charts:[{id:'stage-temperature',title:'Stage temperature',type:'xy',x:{kind:'axis',id:'j',unit:'1'},y:{unit:'K'},events:false,series:[{source:'current',id:profile.seriesId}]}]};
  readChartLayout(layout,{current:results.steady});checks++;
  const charts=await prepareCharts(layout,{current:results.steady});assert.equal(charts.length,1);checks++;
  const changed=guardarHoja(changeStageCount({...model,resultadoRef:{firma:firmaHoja(model),estado:'resuelto',fecha:''}},String(n+1)));
  assert.equal(changed.indexedSelection,undefined);assert.equal(changed.resultadoRef,undefined);checks+=2;
  evidence.push({scope:'connected-network',n,temperatures,seconds:(Date.now()-started)/1000});
 }
}
console.log(JSON.stringify({checks,evidence},null,2));
