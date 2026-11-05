// Consume a fresh Python-authored model through production readers and controls.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import assert from 'node:assert/strict';
import ts from 'typescript';
import katex from 'katex';
const directory=path.dirname(fileURLToPath(import.meta.url)),require=createRequire(import.meta.url),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(file.endsWith('.css'))return {default:{}};
  if(cache.has(file))return cache.get(file).exports;
  const loaded={exports:{}};cache.set(file,loaded);
  const source=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('exports','module','require','process',source)(loaded.exports,loaded,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id),process);
  return loaded.exports;
}
const publication=JSON.parse(execFileSync('python',['tests/test_kinetic_reactions.py','--publish'],{cwd:path.dirname(directory),encoding:'utf8',maxBuffer:4*1024*1024}));
const {leerModeloComun}=load(path.join(directory,'motores/modelo/lector'));
const {readKineticReactions}=load(path.join(directory,'app/models/kineticReactions'));
const {readEquationWorkbenchReport}=load(path.join(directory,'app/models/equationWorkbench'));
const {nuevaHoja}=load(path.join(directory,'app/motor/hojasMotor'));
const {physicalExecutionSignature}=load(path.join(directory,'app/motor/modeloHojaMotor'));
const ReactionControls=load(path.join(directory,'app/models/ReactionControls')).default;
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
const model=leerModeloComun(publication.model);
readEquationWorkbenchReport(publication.development);
for(const row of publication.development.equations)katex.renderToString(row.latex,{throwOnError:true,strict:'error'});
assert.equal(readKineticReactions(model.motores.kineticReactions,model).version,1);
const moving=structuredClone(model);
moving.motores.kineticReactions.version=2;
delete moving.motores.kineticReactions.volumes.cell.volumeDataId;
moving.motores.kineticReactions.volumes.cell.volumeSource={kind:'control_volume'};
assert.equal(readKineticReactions(moving.motores.kineticReactions,moving).version,2);
for(const mutate of [
  r=>r.volumes.cell.volumeDataId='reactingVolume',
  r=>r.volumes.cell.volumeSource.kind='invented',
  r=>r.volumes.cell.volumeSource.extra=true,
  r=>r.version=3,
]){
  const bad=structuredClone(moving.motores.kineticReactions);mutate(bad);
  assert.throws(()=>readKineticReactions(bad,moving));
}
const zeroRate=structuredClone(moving);
zeroRate.motores.derivedExecution.version=5;
assert.equal(readKineticReactions(zeroRate.motores.kineticReactions,zeroRate).version,2);
for(const mutate of [
  r=>r.version=2,
  r=>r.volumes.cell.equilibrium=true,
  r=>r.volumes.cell.reactions[0].stoichiometry['1']='1/0',
  r=>r.volumes.cell.reactions[0].orders['1']=0.5,
  r=>r.volumes.cell.molarMassDataIds['1']='missing',
  r=>r.volumes.cell.reactions.push(structuredClone(r.volumes.cell.reactions[0])),
]){
  const bad=structuredClone(model.motores.kineticReactions);mutate(bad);
  assert.throws(()=>readKineticReactions(bad,model));
}
const sheet={...nuevaHoja('Kinetic authoring'),commonModel:model};
const signature=physicalExecutionSignature(sheet);
const changed=structuredClone(sheet);changed.commonModel.datos.rateConstant.declaracion.texto='0.2';
assert.notEqual(physicalExecutionSignature(changed),signature,'Rate data invalidate the physical execution identity.');
const html=renderToStaticMarkup(React.createElement(ReactionControls,{model:sheet}));
const movingHtml=renderToStaticMarkup(React.createElement(ReactionControls,{model:{...sheet,commonModel:moving}}));
assert.ok(movingHtml.includes('Concentrations use the dynamic control volume V(t).'));
for(const label of ['Kinetic reactions','Stoichiometric coefficient','Element counts','Save kinetic declaration','Formation energy'])assert.ok(html.includes(label));
assert.equal(renderToStaticMarkup(React.createElement(ReactionControls,{model:nuevaHoja('Unbound')})),'');
console.log('Kinetic Python publications, strict readers, data invalidation and shared controls passed.');
const steadyFile=process.argv.indexOf('--steady-result');
if(steadyFile!==-1){
  const {readSteadyResult,steadyResultSignature}=load(path.join(directory,'motores/modelo/steadyContract'));
  const result=JSON.parse(fs.readFileSync(process.argv[steadyFile+1],'utf8'));
  readSteadyResult(result);
  const id='reactions.equilibrium_limit.cell';
  const diagnostic=result.verificaciones.find(row=>row.id===id);
  assert.ok(diagnostic.valor>diagnostic.tolerancia);
  for(const corruption of ['missing','duplicate','negative','tolerance','unknown_owner','version','unknown_field','null']){
    const changed=structuredClone(result),rows=changed.verificaciones,item=rows.find(row=>row.id===id);
    const block=changed.procedencia.compilation.kineticDiagnostics;
    if(corruption==='missing')rows.splice(rows.indexOf(item),1);
    else if(corruption==='duplicate')rows.push(structuredClone(item));
    else if(corruption==='negative')item.valor=-1;
    else if(corruption==='tolerance')item.tolerancia=1;
    else if(corruption==='unknown_owner')block.volumeIds=['missing'];
    else if(corruption==='version')block.version=2;
    else if(corruption==='null')changed.procedencia.compilation.kineticDiagnostics=null;
    else block.extra=true;
    changed.procedencia.steadyDiagnostics.resultSignature=steadyResultSignature(changed);
    assert.throws(()=>readSteadyResult(changed),corruption);
  }
  console.log('Steady kinetic diagnostics: 1 acceptance and 8 re-signed rejections passed.');
}
