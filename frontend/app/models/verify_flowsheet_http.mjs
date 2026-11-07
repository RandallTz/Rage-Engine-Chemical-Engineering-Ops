// Requires tests/prepare_flowsheet_http.py and an isolated NEXT_PUBLIC_API_URL backend.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import ts from 'typescript';

const here=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(here,'../../..'),require=createRequire(import.meta.url),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(file.endsWith('.css'))return {default:{}};
  if(cache.has(file))return cache.get(file).exports;
  const mod={exports:{}};cache.set(file,mod);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('module','exports','require',code)(mod,mod.exports,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id));return mod.exports;
}
const lifecycle=load(path.join(here,'flowsheetLifecycle'));
const {moveStoredFlowsheetBlock}=load(path.join(here,'FlowsheetDiagram'));
const {reconcileDerived}=load(path.join(here,'derivedSelection'));
const {firmaHoja}=load(path.resolve(here,'../motor/modeloHojaMotor'));
const {validateSavedIndexedResult}=load(path.join(here,'indexedSelection'));
const {readFlowsheetResult}=load(path.resolve(here,'../../motores/modelo/flowsheet'));
const source=JSON.parse(fs.readFileSync(path.join(root,'.tmp/flowsheet-http/source.json'),'utf8'));
let model={id:source.id,nombre:source.nombre,commonModel:source};
const report=await lifecycle.prepareFlowsheet(model,'steady');
console.log('Prepared the recorded flowsheet; solving the steady network.');
model=lifecycle.applyFlowsheet(model,report);
assert.equal(model.flowsheetSelection.version,2);
assert.ok(JSON.stringify(model.flowsheetSelection).length<JSON.stringify(report).length/10,'The stored selection must remain compact.');
assert.deepEqual(lifecycle.currentFlowsheet({...model,flowsheetSelection:{version:1,report}}),lifecycle.currentFlowsheet(model));
const pin=firmaHoja(model),published=await lifecycle.solveFlowsheet(model);
const wrapper=lifecycle.flowsheetResult(model,published,pin);
validateSavedIndexedResult(wrapper,model.id,pin);
assert.deepEqual(report.stages.map(row=>row.instanceId),['R1','D1','R2']);
const series=new Map(published.series.map(row=>[row.id,row]));
const scalar=value=>Array.isArray(value)?value[0]:value;
const temperatures=published.indexedNetwork.stages.map(stage=>{
  const id=stage.seriesIds.find(key=>key.includes('.closure.')&&series.get(key)?.nombre.startsWith('T__'));
  assert.ok(id,'A temperature must be published for each instance.');return scalar(series.get(id).valores);
});
const reference=[335.243964,344.588553,345.642769];
temperatures.forEach((value,i)=>assert.ok(Math.abs(value-reference[i])<1e-6,`temperature ${i+1}: ${value}`));
const reactor=source.flowsheet.templates.reactor;
assert.deepEqual(reactor.componentes.map(component=>component.identidadQuimica.cas),['64-17-5','64-19-7','141-78-6','7732-18-5']);
function stateSeries(stageIndex,datumId){
  const quantities=Object.entries(reactor.motores.derivedExecution.initialValues).filter(([,id])=>id===datumId).map(([quantity])=>quantity);
  assert.equal(quantities.length,1,`Expected one state for ${datumId}.`);
  const ids=published.indexedNetwork.stages[stageIndex].seriesIds.filter(id=>id.endsWith(`.state.${quantities[0]}`));
  assert.equal(ids.length,1,`Expected one published state for ${datumId}.`);
  const row=series.get(ids[0]);assert.equal(row.unidadSI,'kg');return scalar(row.valores);
}
for(const [stageIndex,expected] of [[0,0.349817],[2,0.543864]]){
  const first=stateSeries(stageIndex,'cell.mass')/Number(reactor.datos.molarMass1.declaracion.texto);
  const third=stateSeries(stageIndex,'cell.mass3')/Number(reactor.datos.molarMass3.declaracion.texto);
  const conversion=1-first/(first+third);
  assert.ok(Math.abs(conversion-expected)<1e-6,`conversion ${stageIndex+1}: ${conversion}`);
}
model={...model,resultado:wrapper,resultadoRef:{firma:pin,estado:wrapper.estado,fecha:'2026-11-06T00:00:00.000Z'}};
const moved=JSON.parse(JSON.stringify(moveStoredFlowsheetBlock([model],model.id,'D1',[225,70])))[0];
assert.equal(firmaHoja(moved),pin);assert.ok(lifecycle.currentFlowsheet(moved));
validateSavedIndexedResult(moved.resultado,moved.id,pin);readFlowsheetResult(moved.resultado.commonResult,report.selection);
const changed=structuredClone(moved);changed.commonModel.flowsheet.instances[2].data['jacket.T'].texto='350.0';
const stale=reconcileDerived(moved,changed);
assert.equal(stale.flowsheetSelection,undefined);assert.equal(stale.resultadoRef,undefined);assert.equal(stale.flowsheetStale,true);
const response=await fetch(`${process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004'}/modelo/resolver`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({modelo:changed.commonModel,flowsheetExecution:report.selection})});
const rejected=await response.json();assert.equal(response.status,422);assert.match(JSON.stringify(rejected),/stale_flowsheet_execution/);
console.log(JSON.stringify({temperatures,reference,scope:'Real Python steady flowsheet, Results reader, layout round trip, and stale-source rejection'}));
