// Exercise the production revision-2 readers on fresh adapter evidence.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const require=createRequire(path.join(root,'frontend/package.json'));
const ts=require('typescript'),cache=new Map();
function load(file){
  if(!path.extname(file))file+='.ts';
  if(cache.has(file))return cache.get(file).exports;
  const module={exports:{}};cache.set(file,module);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;
  new Function('exports','module','require',code)(module.exports,module,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id));
  return module.exports;
}
const {leerResolucionV2,leerCapacidadesV2}=load(path.join(root,'frontend/app/motor/lectorEnsamblajeV2.ts'));
const directory=path.join(root,'.tmp/codex-v2-parity');
leerCapacidadesV2(JSON.parse(fs.readFileSync(path.join(directory,'capabilities.json'),'utf8')));
let pairs=0,states=0,corruptions=0;
for(const name of fs.readdirSync(directory).filter(name=>name.endsWith('.json'))){
  const row=JSON.parse(fs.readFileSync(path.join(directory,name),'utf8'));
  if(!row.adapter||!row.requestData)continue;
  try{leerResolucionV2(row.adapter,row.requestData);}catch(error){throw new Error(`${name}: ${error.message}`);}
  pairs++;
  if(row.adapter.resultados){
    states+=Object.values(row.adapter.resultados.estados).reduce((count,rows)=>count+rows.length,0);
    const wrong=structuredClone(row.adapter);wrong.resultados.series[0].valores.pop();
    assert.throws(()=>leerResolucionV2(wrong,row.requestData));corruptions++;
  }
}
assert.equal(pairs,25,'Run the complete 25-request Python parity matrix first');
let adjuncts=0;
for(const name of fs.readdirSync(path.join(directory,'adjunct')).filter(name=>name.endsWith('.json'))){
  const row=JSON.parse(fs.readFileSync(path.join(directory,'adjunct',name),'utf8'));
  leerResolucionV2(row.adapter,row.requestData);adjuncts++;
}
assert.equal(adjuncts,7);
console.log(JSON.stringify({pairs,adjuncts,states,rejectedCorruptions:corruptions}));
