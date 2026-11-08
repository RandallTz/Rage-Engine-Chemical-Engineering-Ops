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
function readProduced(file,producer){if(!fs.existsSync(file))throw new Error(`Missing ${path.relative(process.cwd(),file)}: produced by ${producer}; run it first.`);return JSON.parse(fs.readFileSync(file,'utf8'));}
const live=readProduced(path.join(root,'.tmp/index-sets/publication.json'),'tests/test_index_sets.py');
const rejects=readProduced(path.join(root,'.tmp/index-sets/rejections.json'),'tests/test_index_sets.py');
const {leerModeloComun}=load(path.join(here,'motores/modelo/lector'));
const {readIndexSet,readIndexSetExpansion}=load(path.join(here,'motores/modelo/indexSets'));
let checks=0;
leerModeloComun(live.source);checks++;
readIndexSetExpansion(live.expanded,live.source);checks++;
for(const mutate of [v=>v.version=2,v=>v.extra=true,v=>v.count=2,v=>v.stages[0].model.id=v.stages[1].model.id,v=>v.connections[0].from.portId='missing',v=>v.internalStreams[0].stream.hasta='missing',v=>v.ports.pop(),v=>v.ports[0].port.kind='work']){
 const bad=structuredClone(live.expanded);mutate(bad);assert.throws(()=>readIndexSetExpansion(bad,live.source));checks++;
}
for(const row of rejects){assert.throws(()=>leerModeloComun(row.model),undefined,row.name);checks++;}
for(const stage of live.expanded.stages){leerModeloComun(stage.model);checks++;}
assert.equal(live.expanded.internalStreams.length,2);checks++;
assert.equal(live.expanded.ports.length,8);checks++;
const variant=structuredClone(live.source);variant.indexSet.variants=[{at:'first',template:'generic'}];readIndexSet(variant);checks++;
variant.datos['solve.stageCount'].declaracion.texto='1';readIndexSet(variant);checks++;
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
const {IndexedStages}=load(path.join(here,'app/motor/ModelAssumptions'));
const html=renderToStaticMarkup(React.createElement(IndexedStages,{model:live.source}));
for(const text of ['Indexed stages','Solve datum','liquid','feed','vapour','heat','Numerical network execution is pending']){assert.ok(html.includes(text));checks++;}
assert.ok(!/<(?:input|button|select)\b/.test(html));checks++;
console.log(JSON.stringify({checks,rejections:rejects.length,scope:'Indexed template parity, replayed documents, topology and shared read-only panel'}));
