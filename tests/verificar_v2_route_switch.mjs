// Production readers on fresh HTTP evidence, including native fallback provenance.
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
  const loadedModule={exports:{}};cache.set(file,loadedModule);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText;
  new Function('exports','module','require',code)(loadedModule.exports,loadedModule,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id));
  return loadedModule.exports;
}
const {leerResolucionV2,leerValidacionV2,leerCapacidadesV2}=load(path.join(root,'frontend/app/motor/lectorEnsamblajeV2.ts'));
const directory=path.join(root,'.tmp/codex-v2-http');
const capabilities=JSON.parse(fs.readFileSync(path.join(directory,'capabilities.json'),'utf8'));
leerCapacidadesV2(capabilities);
const malformed=[null,{}, {version:2,path:'common-compiler',selection:'default'},
  {version:1,path:'native-v2',selection:'default'}, {version:1,path:'unknown',selection:'server-override'},
  {version:1,path:'common-compiler',selection:'automatic-fallback'},
  {version:1,path:['common-compiler'],selection:'default'},
  {version:1,path:'common-compiler',selection:['default']},
  {version:1,path:'common-compiler',selection:'default',extra:true}];
for(const executionProvenance of malformed)assert.throws(()=>leerCapacidadesV2({...capabilities,executionProvenance}));
let cases=0,publications=0,states=0;
for(const name of fs.readdirSync(directory).filter(name=>name.endsWith('.json'))){
  const row=JSON.parse(fs.readFileSync(path.join(directory,name),'utf8'));
  if(!row.requestData)continue;
  assert.equal(row.passed,true,name);
  for(const label of ['adapter','native']){
    const result=row[label];
    leerResolucionV2(result,row.requestData);
    leerValidacionV2(row[label+'Validation'],row.requestData);
    assert.equal(result.executionProvenance.path,label==='adapter'?'common-compiler':'native-v2');
    const legacy=structuredClone(result);delete legacy.executionProvenance;
    leerResolucionV2(legacy,row.requestData);
    for(const executionProvenance of malformed){
      assert.throws(()=>leerResolucionV2({...result,executionProvenance},row.requestData));
      assert.throws(()=>leerValidacionV2({...row[label+'Validation'],executionProvenance},row.requestData));
    }
    if(result.resultados){
      states+=Object.values(result.resultados.estados).reduce((n,rows)=>n+rows.length,0);
      const corrupt=structuredClone(result);corrupt.resultados.series[0].valores.pop();
      assert.throws(()=>leerResolucionV2(corrupt,row.requestData));
    }
    publications++;
  }
  cases++;
}
assert.equal(cases,25,'Complete the fresh HTTP parity run first.');
console.log(JSON.stringify({cases,publications,states,provenance:'passed',legacyCompatibility:'passed',malformedProvenanceCases:malformed.length}));
