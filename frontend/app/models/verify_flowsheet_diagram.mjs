import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import ts from 'typescript';

const here=path.dirname(fileURLToPath(import.meta.url)),require=createRequire(import.meta.url),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(file.endsWith('.css'))return {default:{}};
  if(cache.has(file))return cache.get(file).exports;
  const mod={exports:{}};cache.set(file,mod);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('module','exports','require',code)(mod,mod.exports,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id));return mod.exports;
}
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
const {default:Diagram,moveFlowsheetBlock,moveStoredFlowsheetBlock,connectionDiagnostics}=load(path.join(here,'FlowsheetDiagram'));
const {derivedSourceIdentity}=load(path.join(here,'derivedSelection'));
const {invalidatedByEdit}=load(path.resolve(here,'../../motores/modelo/flowsheet'));
const common={id:'model',nombre:'Network',componentes:[],motores:{},estudio:null,flowsheet:{format:'rage.flowsheet',version:1,id:'network',templates:{drum:{template:{ports:[]}},reactor:{template:{ports:[]}}},instances:[{id:'D1',template:'drum',data:{}},{id:'R1',template:'reactor',data:{}},{id:'R2',template:'reactor',data:{}}],connections:[{id:'stream_a',from:{instance:'D1',port:'out'},to:{instance:'R1',port:'in'}},{id:'stream_b',from:{instance:'R1',port:'out'},to:{instance:'R2',port:'in'}}],exposures:[],recycles:[]}};
const diagnostic={code:'bad_pressure',path:'flowsheet.connections.stream_b.from',message:'Pressure mismatch'};
const markup=renderToStaticMarkup(React.createElement(Diagram,{model:{id:'model',commonModel:common},initialDiagnostics:[diagnostic]}));
for(const id of ['D1','R1','R2'])assert.match(markup,new RegExp(`data-instance-id="${id}"`));
assert.match(markup,/data-connection-id="stream_a" data-diagnostic="false"/);
assert.match(markup,/data-connection-id="stream_b" data-diagnostic="true"/);
assert.match(markup,/Pressure mismatch/);
assert.equal(connectionDiagnostics([diagnostic],'stream').length,0);
const result={firma:'saved-result',estado:'resuelto',values:[1,2,3]};
const before={id:'model',actualizada:'unchanged',commonModel:common,resultado:result,resultadoRef:{firma:'saved-result',estado:'resuelto'}};
const after=JSON.parse(JSON.stringify(moveStoredFlowsheetBlock([before],'model','D1',[200,90])))[0];
assert.deepEqual(after.resultado,result);assert.deepEqual(after.resultadoRef,before.resultadoRef);
assert.equal(invalidatedByEdit(common,after.commonModel),false);
assert.equal(derivedSourceIdentity(common),derivedSourceIdentity(after.commonModel));
const {flowsheetLayout,...unchanged}=after.commonModel;assert.deepEqual(unchanged,common);
assert.deepEqual({...after,commonModel:unchanged},before);
assert.deepEqual(flowsheetLayout.blocks.D1.position,[200,90]);
assert.throws(()=>moveFlowsheetBlock(common,'missing',[0,0]));
console.log('Flowsheet diagram: blocks, identity-located diagnostics, and layout/result JSON round trip passed.');
