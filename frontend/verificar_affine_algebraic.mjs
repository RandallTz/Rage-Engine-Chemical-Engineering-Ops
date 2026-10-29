// Real Python publication and strict TS readers/lifecycle, without a browser.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {spawnSync} from 'node:child_process';
import ts from 'typescript';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.dirname(here),require=createRequire(import.meta.url),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(cache.has(file))return cache.get(file).exports;
  const loadedModule={exports:{}};cache.set(file,loadedModule);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('module','exports','require',code)(loadedModule,loadedModule.exports,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id));
  return loadedModule.exports;
}
console.log('Building a live shared-operation affine-block publication...');
const python=spawnSync('python',['tests/test_f3_affine_algebraic.py','--publication'],{cwd:root,encoding:'utf8',maxBuffer:24*1024*1024,timeout:900000});
assert.equal(python.status,0,python.stderr||String(python.error));
const live=JSON.parse(python.stdout);
const {readDerivedExecution}=load(path.join(here,'motores/modelo/derivedExecution.ts'));
const {readCompilationReport}=load(path.join(here,'motores/modelo/compilation.ts'));
const {leerResultados}=load(path.join(here,'motores/resultados/lector.ts'));
const {commonSource,derivedSourceIdentity,selectedDerivedModel,reconcileDerived}=load(path.join(here,'app/models/derivedSelection.ts'));
const selection=readDerivedExecution(live.model.motores.derivedExecution,live.model.datos);
assert.equal(selection.version,2);
assert.equal(selection.algebraic.length,2);
const report=readCompilationReport(live.result.procedencia.compilation);
assert.deepEqual(report.derivedExecution.algebraicBlock.rows,selection.algebraic);
assert.ok(report.strategy.steps.some(step=>step.id==='algebraic-block'));
leerResultados(live.result);
assert.ok(live.result.verificaciones.some(row=>row.id==='algebraic.backward_error'));
const legacy=structuredClone(selection);legacy.version=1;delete legacy.algebraic;
readDerivedExecution(legacy);
const badSelections=[value=>{value.version=1;},value=>{delete value.algebraic;},value=>{value.algebraic=[];},
  value=>{value.algebraic[0].quantityId=value.states[0].quantityId;},
  value=>{value.algebraic[1].equationId=value.algebraic[0].equationId;},
  value=>{value.algebraic[0].rhs='client equation';}];
for(const mutate of badSelections){const bad=structuredClone(selection);mutate(bad);assert.throws(()=>readDerivedExecution(bad));}
const badReports=[value=>{value.derivedExecution.version=1;},value=>{delete value.derivedExecution.algebraicBlock;},
  value=>{value.derivedExecution.algebraicBlock.matrixSI[0][0]=NaN;},
  value=>{value.derivedExecution.algebraicBlock.rows.reverse();},
  value=>{value.derivedExecution.algebraicBlock.equilibratedConditionInfinity=Infinity;}];
for(const mutate of badReports){const bad=structuredClone(report);mutate(bad);assert.throws(()=>readCompilationReport(bad));}
const model={id:live.model.id,nombre:live.model.nombre,commonModel:live.model,resultado:{marker:true},resultadoRef:'saved'};
model.derivedSelection={version:1,sourceSignature:derivedSourceIdentity(commonSource(model)),selection};
assert.deepEqual(selectedDerivedModel(model).motores.derivedExecution,selection);
const changed=structuredClone(model);changed.derivedSelection.selection.algebraic.reverse();
assert.equal(reconcileDerived(model,changed).resultadoRef,undefined);
const dataEdit=structuredClone(model);dataEdit.commonModel.datos['solve.conductance'].declaracion.texto='7';
assert.throws(()=>selectedDerivedModel(dataEdit));
console.log('Affine block: live readers, 11 malformed payloads, v1 compatibility and selection/data invalidation pass.');
