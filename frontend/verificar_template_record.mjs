// Demo 0.1 models through the production readers: frozen fixtures, importable model files and the
// package-closure compilation reports that Python derived execution publishes for them.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import assert from 'node:assert/strict';
import ts from 'typescript';

const directory=path.dirname(fileURLToPath(import.meta.url)),root=path.dirname(directory),require=createRequire(import.meta.url),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(file.endsWith('.css'))return {default:{}};
  if(file.endsWith('.json'))return {__esModule:true,default:JSON.parse(fs.readFileSync(file,'utf8'))};
  if(cache.has(file))return cache.get(file).exports;
  const loaded={exports:{}};cache.set(file,loaded);
  const source=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('exports','module','require','process',source)(loaded.exports,loaded,id=>id==='next/navigation'?{useRouter:()=>({push(){},replace(){}})}:id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id),{env:{}});
  return loaded.exports;
}
let checks=0;const check=(condition,message)=>{assert.ok(condition,message);checks++;};

const {leerModeloComun,ErrorModelo}=load(path.join(directory,'motores/modelo/lector'));
const rows=JSON.parse(execFileSync('python',['tests/test_template_record.py','--cases'],{cwd:root,encoding:'utf8',maxBuffer:64*1024*1024}));
for(const [label,valid,model]of rows){
  if(valid){assert.equal(leerModeloComun(model),model,label);}else{assert.throws(()=>leerModeloComun(model),error=>error instanceof ErrorModelo&&!!error.ruta,label);}
  checks++;
}
const {renderToStaticMarkup}=require('react-dom/server');
const {auditModelDerivation}=load(path.join(directory,'app/models/modelDerivationAudit'));
for(const key of ['materialDerivation','energyDerivation','momentumDerivation','thermodynamicDerivation']){
  const commonModel=structuredClone(rows[0][2]);
  commonModel.template.recipe.journals=commonModel.template.recipe.journals.filter(j=>j!==key);
  const audit=auditModelDerivation({commonModel});
  check(audit.status==='needs_review'&&audit.findings.some(f=>f.code==='equipment_recipe'),'Audit rejects missing equipment recipe '+key);
}
for(const [label,edit]of [
  ['empty momentum journal',m=>{m.motores.momentumDerivation.volumes={};}],
  ['momentum entry without operations',m=>{m.motores.momentumDerivation.volumes.drum.operations=[];}],
  ['no energy entry',m=>{delete m.motores.energyDerivation.volumes.drum;}],
  ['no thermodynamic entry',m=>{delete m.motores.thermodynamicDerivation.volumes.drum;}],
  ['no momentum balance',m=>{m.volumenes[0].balances.momento=false;}],
]){
  const commonModel=structuredClone(rows[0][2]);edit(commonModel);
  const audit=auditModelDerivation({commonModel});
  check(audit.status==='needs_review'&&audit.findings.some(f=>f.code==='equipment_deduction'),'Audit rejects '+label);
}
check(auditModelDerivation({commonModel:rows[0][2]}).status==='recorded','Audit accepts the corpus equipment case');
for(const file of ['flash-drum.rage-model.json','continuous-reactor.rage-model.json','column.index-set.json']){
  const document=JSON.parse(fs.readFileSync(path.join(root,'docs/ejemplos/demo-0.2',file),'utf8'));
  const inner=document.model??document,model=inner.commonModel??inner;
  check(leerModeloComun(model)===model,'Published equipment document reads: '+file);
  if(model.indexSet){
    const mutant=structuredClone(model);mutant.indexSet.genericStage='missing';
    assert.throws(()=>leerModeloComun(mutant),error=>error instanceof ErrorModelo&&error.ruta==='indexSet.genericStage','Index-set error is located');checks++;
  }
}
const {TemplatePorts}=load(path.join(directory,'app/motor/ModelAssumptions'));
const html=renderToStaticMarkup(require('react').createElement(TemplatePorts,{template:rows[0][2].template}));
check(html.includes('Equipment')&&html.includes('feed')&&html.includes('kg/s')&&html.includes('estadoExterior'),'Read-only ports expose boundary and SI metadata');
check(!html.includes('<input')&&!html.includes('<button'),'Ports have no wiring controls');
check(renderToStaticMarkup(require('react').createElement(TemplatePorts,{}))==='','Legacy presentation unchanged');
console.log(JSON.stringify({checks,cases:rows.length}));
