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
for(const label of ['Kinetic reactions','Stoichiometric coefficient','Element counts','Save kinetic declaration','Formation energy'])assert.ok(html.includes(label));
assert.equal(renderToStaticMarkup(React.createElement(ReactionControls,{model:nuevaHoja('Unbound')})),'');
console.log('Kinetic Python publications, strict readers, data invalidation and shared controls passed.');
