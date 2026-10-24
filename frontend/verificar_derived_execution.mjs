// Strict cross-language readers for actual derived-graph compiler publications.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import ts from 'typescript';
const directory=path.dirname(fileURLToPath(import.meta.url)),require=createRequire(import.meta.url),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(file.endsWith('.css'))return {default:{}};
  if(cache.has(file))return cache.get(file).exports;
  const loadedModule={exports:{}};cache.set(file,loadedModule);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('exports','module','require','process',code)(loadedModule.exports,loadedModule,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id),process);
  return loadedModule.exports;
}
const {leerModeloComun}=load(path.join(directory,'motores/modelo/lector'));
const {readDerivedExecution,readDerivedExecutionSource}=load(path.join(directory,'motores/modelo/derivedExecution'));
const {readCompilationReport}=load(path.join(directory,'motores/modelo/compilation'));
const {publications,metrics}=JSON.parse(fs.readFileSync(path.join(directory,'../.tmp/m1-bridge-publications.json'),'utf8'));
let reports=0;
for(const [key,{model,report,result}] of Object.entries(publications)){
  assert.deepEqual(leerModeloComun(model),model);
  assert.deepEqual(readCompilationReport(report),report);
  assert.deepEqual(readCompilationReport(result.procedencia.compilation),report);
  assert.deepEqual(report.derivedExecution.selection,model.motores.derivedExecution);
  const sourcePin={format:'rage.derived-execution-source',version:1,modelId:model.id,sourceSignature:report.derivedExecution.sourceSignature};
  assert.deepEqual(readDerivedExecutionSource(sourcePin),sourcePin);
  assert.throws(()=>readDerivedExecutionSource({...sourcePin,rhs:'Unsupported'}));
  assert.equal(result.procedencia.metodo,report.method);
  const sourceName=key.startsWith('c.')?'thermal':key[0];
  const original=JSON.parse(fs.readFileSync(path.join(directory,`../.tmp/m1-${sourceName}-publication.json`),'utf8'));
  assert.deepEqual(report.equationWorkbench.equations,original.equations,'Solve receives the exact source and operation rows published by Transform.');
  assert.equal(report.variables.length,key.startsWith('c.')?4:3);
  const invalid=structuredClone(model.motores.derivedExecution);
  invalid.rhs='A client cannot save a terminal formula';
  assert.throws(()=>readDerivedExecution(invalid));
  const unknownReport=structuredClone(report);unknownReport.derivedExecution.unrecognized=true;
  assert.throws(()=>readCompilationReport(unknownReport));
  const mismatched=structuredClone(report);mismatched.derivedExecution.sourceSignature='0'.repeat(64);
  assert.throws(()=>readCompilationReport(mismatched));
  reports++;
}
assert.equal(reports,8);
assert.equal(metrics.length,8);
assert(metrics.every(row=>row.scaledError<1e-5&&row.conservationResidual<1e-6));
console.log(JSON.stringify({reports,sourceRows:'exact',commonReader:'passed',compilationReader:'passed',metrics}));
