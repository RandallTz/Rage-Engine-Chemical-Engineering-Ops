import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const here=path.dirname(fileURLToPath(import.meta.url)),require=createRequire(import.meta.url),ts=require('typescript'),cache=new Map();
function load(file){
  if(!path.extname(file))file+='.ts';
  if(cache.has(file))return cache.get(file).exports;
  const module={exports:{}};cache.set(file,module);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  new Function('module','exports','require',code)(module,module.exports,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id));
  return module.exports;
}
const {readIndexedCompilation,readIndexedSelection,readIndexedResult}=load(path.join(here,'motores/modelo/indexedExecution'));
const {steadySignature}=load(path.join(here,'motores/modelo/steadyContract'));
function readProduced(file,producer){if(!fs.existsSync(file))throw new Error(`Missing ${path.relative(process.cwd(),file)}: produced by ${producer}; run it first.`);return JSON.parse(fs.readFileSync(file,'utf8'));}
const data=readProduced(path.resolve(here,'../.tmp/indexed-execution-contract.json'),'tests/test_indexed_execution_contract.py');
let checks=0;
for(const report of Object.values(data.valid)){
  assert.deepEqual(readIndexedCompilation(report),report);checks++;
  assert.deepEqual(readIndexedSelection(report.selection),report.selection);checks++;
  if(report.selection.mode==='steady'){
    const reordered=structuredClone(report);
    for(const stage of reordered.stages)stage.steadyReport.selection.states=stage.steadyReport.selection.states.map(row=>Object.fromEntries(Object.entries(row).reverse()));
    assert.deepEqual(readIndexedCompilation(reordered),reordered);checks++;
    reordered.stages[0].steadyReport.selection.states[0].equationId='changed-row';
    const {signature,...unsigned}=reordered;reordered.signature=steadySignature(unsigned);
    assert.throws(()=>readIndexedCompilation(reordered));checks++;
  }
}
for(const test of data.invalid){assert.throws(()=>readIndexedCompilation(test.report),Error,test.name);checks++;}
console.log(`Indexed execution contract: ${checks} checks passed.`);
if(process.argv.includes('--http')){
  let resultChecks=0;
  for(const mode of ['dynamic','steady']){
    const result=readProduced(path.resolve(here,`../.tmp/indexed-http-${mode}.json`),'tests/test_indexed_execution_http.py (live HTTP run)');
    const selection=result.procedencia.indexedCompilation.selection;
    assert.deepEqual(readIndexedResult(result,selection),result);resultChecks++;
    const changed=structuredClone(result);changed.series[0].valores=mode==='steady'?999:changed.series[0].valores.map(()=>999);
    assert.throws(()=>readIndexedResult(changed,selection),Error);resultChecks++;
    assert.throws(()=>readIndexedResult(result,{...selection,sourceSignature:'0'.repeat(64)}),Error);resultChecks++;
  }
  console.log(`Indexed HTTP publications: ${resultChecks} checks passed.`);
}
