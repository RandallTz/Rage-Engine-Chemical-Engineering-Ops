// Headless production readers and existing Model presentation, no science here.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import ts from 'typescript';
const here=path.dirname(fileURLToPath(import.meta.url)),require=createRequire(import.meta.url),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(file.endsWith('.css'))return {default:{}};
  if(cache.has(file))return cache.get(file).exports;
  const module={exports:{}};cache.set(file,module);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('module','exports','require','process',code)(module,module.exports,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id),process);
  return module.exports;
}
const model=JSON.parse(fs.readFileSync(path.join(here,'../.tmp/f5-equilibrium-model.json'),'utf8'));
const result=JSON.parse(fs.readFileSync(path.join(here,'../.tmp/f5-equilibrium-result.json'),'utf8'));
const {leerModeloComun}=load(path.join(here,'motores/modelo/lector'));
const {leerResultados}=load(path.join(here,'motores/resultados/lector'));
const {readCompilationReport}=load(path.join(here,'motores/modelo/compilation'));
const {readEquationWorkbench}=load(path.join(here,'app/models/equationWorkbench'));
let checks=0;
assert.deepEqual(leerModeloComun(model),model);checks++;
assert.deepEqual(leerResultados(result),result);checks++;
readCompilationReport(result.procedencia.compilation);checks++;
readEquationWorkbench(model.motores.equationWorkbench);checks++;
// F1 repair: one recorded thermodynamic constitutive mu_i relation per species,
// placed in the existing Thermodynamics panel by its family.
const {panelDeEcuacion}=load(path.join(here,'app/motor/ubicacionEcuaciones'));
const potentials=model.motores.equationWorkbench.operations.filter(op=>op.kind==='declare_relation'&&op.relationKind==='constitutive'&&op.family==='thermodynamics');
assert.equal(potentials.length,model.motores.equilibriumReactions.volumes.gas.species.length);checks++;
for(const op of potentials){assert.equal(panelDeEcuacion({id:'operation',familia:op.family}),'termodinamica');assert.ok(op.right.includes('log('));checks++;}
const mutations=[
  r=>r.extra=true,r=>r.version=2,r=>r.volumes.gas.extra=true,
  r=>r.volumes.gas.species.reverse(),r=>r.volumes.gas.phaseId='solid',
  r=>r.volumes.gas.anchor='none',r=>r.volumes.gas.standardState='custom',
  r=>r.volumes.gas.amountIds.pop(),r=>r.volumes.gas.extentIds=[],
  ...['1/0','01','-01','1/01','-0'].map(value=>r=>r.volumes.gas.reactions[0].stoichiometry[0]=value),
  r=>r.volumes.gas.reactions.push(structuredClone(r.volumes.gas.reactions[0])),
];
for(const mutate of mutations){const bad=structuredClone(model);mutate(bad.motores.equilibriumReactions);assert.throws(()=>leerModeloComun(bad));checks++;}
const malformed=structuredClone(model.motores.equationWorkbench);
delete malformed.operations.find(op=>op.kind==='state_variation').reason;
assert.throws(()=>readEquationWorkbench(malformed));checks++;
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
const Controls=load(path.join(here,'app/models/ReactionControls')).default;
const html=renderToStaticMarkup(React.createElement(Controls,{model:{commonModel:model}}));
for(const label of ['Equilibrium reaction constraints','Formation anchor:','ideal_gas_P0','no additional reaction heat','Whole-domain certification']){assert.ok(html.includes(label));checks++;}
const panel=fs.readFileSync(path.join(here,'app/models/EquationWorkbenchPanel.tsx'),'utf8');
assert.ok(panel.includes('Impose a virtual state variation'));checks++;
console.log(`F5-C1: ${checks} production-reader and shared-presentation checks passed.`);
