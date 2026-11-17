// rage.flowsheet v1 client parity (material and heat connections): the TS reader rejects every Python rejection
// with the same code and path, admits the same documents, keeps layout edits
// presentation-only and reads the actual Python steady/dynamic publications.
// Producer: python -m pytest -q tests/test_flowsheet_network.py (writes .tmp/flowsheet/).
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
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
const dir=path.join(root,'.tmp/flowsheet'),read=name=>JSON.parse(fs.readFileSync(path.join(dir,name),'utf8'));
const {leerModeloComun}=load(path.join(here,'motores/modelo/lector'));
const F=load(path.join(here,'motores/modelo/flowsheet'));
let checks=0;
const accepted=read('accepted.json');
leerModeloComun(accepted.base);checks++;
leerModeloComun(accepted.declaredRecycle);checks++;
const rejections=read('rejections.json');
for(const row of rejections){
  let error;try{leerModeloComun(row.model);}catch(e){error=e;}
  assert.ok(error instanceof F.FlowsheetError,`${row.name}: expected FlowsheetError, got ${error}`);
  assert.equal(error.code,row.code,row.name);assert.equal(error.path,row.path,row.name);checks++;
}
// Layout edits keep the executable source; topology and data edits do not.
const moved=structuredClone(accepted.base);moved.flowsheetLayout.blocks.D1.position=[220.5,-40];moved.flowsheetLayout.streams={};
leerModeloComun(moved);assert.equal(F.invalidatedByEdit(accepted.base,moved),false);checks++;
const {flowsheetLayout:_,...noLayout}=structuredClone(accepted.base);assert.equal(F.invalidatedByEdit(accepted.base,noLayout),false);checks++;
for(const edit of [m=>m.flowsheet.instances[2].data['jacket.T'].texto='350.0',m=>m.flowsheet.connections.reverse(),m=>m.datos['flowsheet.tf'].declaracion.texto='1.0']){
  const changed=structuredClone(accepted.base);edit(changed);assert.equal(F.invalidatedByEdit(accepted.base,changed),true);checks++;
}
let results=0;
for(const name of ['steady-result.json','dynamic-result.json']){
  if(!fs.existsSync(path.join(dir,name)))continue;
  const live=read(name);results++;
  const {result,compilation,instanceOwners}=F.readFlowsheetResult(live.result,live.selection);checks++;
  assert.deepEqual(Object.keys(instanceOwners),['R1','D1','R2']);checks++;
  assert.equal(compilation.selection.sourceSignature,live.selection.sourceSignature);checks++;
  assert.equal(result.indexedNetwork?.count??live.result.indexedNetwork.count,3);checks++;
  for(const mutate of [r=>r.procedencia.flowsheetCompilation.count=2,r=>r.procedencia.flowsheetCompilation.stages[1].instanceId='R1',
    r=>r.procedencia.flowsheetCompilation.connections[0].from.port='feed',r=>r.procedencia.flowsheetCompilation.ports.pop(),
    r=>r.procedencia.flowsheetCompilation.rateRows.reverse(),r=>r.procedencia.motor='rage.compilador.indexed_network',
    r=>r.procedencia.firma='0'.repeat(64),r=>delete r.procedencia.flowsheetResultSignature]){
    const bad=structuredClone(live.result);mutate(bad);assert.throws(()=>F.readFlowsheetResult(bad,live.selection));checks++;
  }
  const other=structuredClone(live.selection);other.mode=other.mode==='steady'?'dynamic':'steady';
  assert.throws(()=>F.readFlowsheetResult(live.result,other));checks++;
  leerModeloComun(live.source);checks++;
}
for(const bad of [{},{format:'rage.flowsheet-execution',version:2,sourceSignature:'a'.repeat(64),mode:'steady'},{format:'rage.flowsheet-execution',version:1,sourceSignature:'x',mode:'steady'}]){
  assert.throws(()=>F.readFlowsheetSelection(bad));checks++;
}
// rage.flowsheet v1 heat connections (optional `heat` key) (producer: python -m pytest -q tests/test_flowsheet_heat.py, writes .tmp/flowsheet_heat/).
const heatDir=path.join(root,'.tmp/flowsheet_heat'),heat={rejections:0,results:0};
if(fs.existsSync(path.join(heatDir,'rejections.json'))){
  const readHeat=name=>JSON.parse(fs.readFileSync(path.join(heatDir,name),'utf8'));
  leerModeloComun(readHeat('accepted.json').base);checks++;
  for(const row of readHeat('rejections.json')){
    let error;try{leerModeloComun(row.model);}catch(e){error=e;}
    assert.ok(error instanceof F.FlowsheetError,`heat ${row.name}: expected FlowsheetError, got ${error}`);
    assert.equal(error.code,row.code,'heat '+row.name);assert.equal(error.path,row.path,'heat '+row.name);checks++;heat.rejections++;
  }
  for(const name of ['dynamic-result.json','steady-result.json']){
    if(!fs.existsSync(path.join(heatDir,name)))continue;
    const live=readHeat(name);heat.results++;
    const {compilation}=F.readFlowsheetResult(live.result,live.selection);checks++;
    assert.equal(compilation.version,1);assert.equal(compilation.heatCouplings.length,1);checks++;
    for(const mutate of [r=>r.procedencia.flowsheetCompilation.heatCouplings[0].law.endpoint='from',
      r=>r.procedencia.flowsheetCompilation.heatCouplings[0].connectionId='other',r=>r.procedencia.flowsheetCompilation.heatCouplings[0].identity='approximate',
      r=>r.procedencia.flowsheetCompilation.heatCouplings=[]]){
      const bad=structuredClone(live.result);mutate(bad);assert.throws(()=>F.readFlowsheetResult(bad,live.selection));checks++;
    }
  }
}
console.log(JSON.stringify({checks,rejections:rejections.length,results,heat,scope:'rage.flowsheet v1 (material and heat connections) Python/TS rejection parity, layout invariance and actual network publications'}));
