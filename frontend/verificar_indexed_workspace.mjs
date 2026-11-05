import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.dirname(here),require=createRequire(import.meta.url),ts=require('typescript'),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(file.endsWith('.css'))return {default:{}};
  if(cache.has(file))return cache.get(file).exports;
  const module={exports:{}};cache.set(file,module);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('module','exports','require',code)(module,module.exports,id=>id==='next/navigation'?{useRouter:()=>({push(){}})}:id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id));return module.exports;
}
const storage=new Map();globalThis.localStorage={getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v)};globalThis.window=new EventTarget();
const {nuevaHoja,guardarHoja,leerHojas,duplicarHoja}=load(path.join(here,'app/motor/hojasMotor'));
const {applyIndexed,currentIndexed,indexedResult,validateSavedIndexedResult}=load(path.join(here,'app/models/indexedSelection'));
const {changeStageCount}=load(path.join(here,'app/models/indexSetSolve'));
const {firmaHoja}=load(path.join(here,'app/motor/modeloHojaMotor'));
const {defaultChartLayout,readChartLayout}=load(path.join(here,'motores/resultados/chartSpecification'));
const source=JSON.parse(fs.readFileSync(path.join(root,'docs/ejemplos/demo-0.2/flash-drum.rage-model.json'),'utf8')).model.commonModel;
const common=structuredClone(source);common.id='indexed-stage-test';
common.datos['solve.stageCount']={magnitud:'stageCount',funcion:'estudio',declaracion:{texto:'2',unidad:'1'},origen:{propietarioId:'estudio',ruta:'stageCount'}};
common.indexSet={format:'rage.index-set',version:1,id:'cascade',index:'j',countDataId:'solve.stageCount',templates:{generic:source},genericStage:'generic',variants:[],connections:[{outlet:'liquid',inlet:'feed',offset:1}],exposures:[{id:'feed',port:'feed',at:'first'},{id:'liquid',port:'liquid',at:'last'},{id:'vapour',port:'vapour',at:'each'},{id:'heat',port:'heat',at:'each'}]};
for(const doc of [common,source]){doc.datos[doc.estudio.tiempoId].declaracion.texto='1';doc.estudio.muestras=3;doc.estudio.metodoSolicitado='bdf';}
let model=guardarHoja({...nuevaHoja(common.nombre),id:common.id,commonModel:common}),checks=0;
const base=structuredClone(model),signatures=[];
for(const mode of ['dynamic','steady']){
  const result=JSON.parse(fs.readFileSync(path.join(root,`.tmp/indexed-http-${mode}.json`),'utf8'));
  model=guardarHoja(applyIndexed(model,result.procedencia.indexedCompilation));
  assert.ok(currentIndexed(guardarHoja(structuredClone(model))));checks++;
  assert.equal(leerHojas().find(row=>row.id===model.id).indexedSelection.report.selection.mode,mode);checks++;
  const pin=firmaHoja(model);signatures.push(pin);
  const wrapped=indexedResult(model,result,pin);assert.equal(wrapped.version,3);checks++;
  validateSavedIndexedResult(wrapped,model.id,pin);checks++;
  const chart=defaultChartLayout(result);readChartLayout(chart,{current:result});checks++;
  assert.equal(chart.charts[0].type,mode==='steady'?'xy':'time_series');checks++;
  assert.throws(()=>validateSavedIndexedResult({...wrapped,modo:'1d'},model.id,pin));checks++;
  for(const edit of [row=>changeStageCount(row,'3'),row=>{row.commonModel.estudio.muestras=4;return row;},row=>{row.commonModel.indexSet.templates.generic.estudio.muestras=4;return row;}]){
    const changed=guardarHoja(edit({...structuredClone(model),resultadoRef:{firma:pin,estado:'resuelto',fecha:''}}));
    assert.equal(changed.indexedSelection,undefined);assert.equal(changed.resultadoRef,undefined);checks+=2;
    // Re-select only after restoring the exact source; an old selection must not survive the edit.
    guardarHoja(structuredClone(base));model=guardarHoja(applyIndexed(structuredClone(base),result.procedencia.indexedCompilation));
  }
  assert.equal(duplicarHoja(model).indexedSelection,undefined);checks++;
}
assert.notEqual(...signatures);checks++;
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
for(const [file,text] of [['IndexedTransform','Steady state (zero accumulation)'],['IndexedStageSolve','Solve network']]){
  const Component=load(path.join(here,`app/models/${file}`)).default;
  assert.ok(renderToStaticMarkup(React.createElement(Component,{model})).includes(text));checks++;
}
console.log(`Indexed workspace: ${checks} checks passed (persistence, invalidation, wrappers and existing controls).`);
