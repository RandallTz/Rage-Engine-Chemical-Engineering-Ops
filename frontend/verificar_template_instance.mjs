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
const live=JSON.parse(fs.readFileSync(path.join(root,'.tmp/template-instance/publication.json'),'utf8'));
const {readTemplateInstance}=load(path.join(here,'motores/modelo/templateInstance'));
const {templateInstanceDocument}=load(path.join(here,'app/models/templateInstance'));
const {selectedDerivedModel}=load(path.join(here,'app/models/derivedSelection'));
let checks=0;
const response=readTemplateInstance(live.response,live.source);checks++;
for(const change of [v=>v.version=2,v=>v.extra=true,v=>v.provenance.version=2,v=>v.provenance.templateId='other',v=>v.model.id=live.source.id,v=>v.model.template.equipment=!live.source.template.equipment,v=>v.provenance.identityMap.volumes={},v=>v.model.template.ports[0].id='other',v=>v.model.datos[Object.keys(live.source.datos)[0]].declaracion.texto='99',v=>v.provenance.equationSignatures={},v=>v.provenance.sourceSignature='bad',v=>v.model.corrientes[0].desde=v.model.volumenes[0].id]){
 const bad=structuredClone(response);change(bad);assert.throws(()=>readTemplateInstance(bad,live.source));checks++;
}
const model=templateInstanceDocument(response);
assert.deepEqual(selectedDerivedModel(model),response.model);checks++;
assert.equal(model.resultado,undefined);assert.equal(model.resultadoRef,undefined);assert.equal(model.transformation,undefined);checks++;
assert.equal(model.id,response.model.id);assert.notEqual(model.id,live.source.id);checks++;
assert.deepEqual(model.commonModel.procedencia.templateInstance,response.provenance);checks++;
const sourceText=fs.readFileSync(path.join(here,'app/models/ModelLibrary.tsx'),'utf8');
assert.ok(sourceText.includes('New instance from this template')&&sourceText.includes('AssessmentText error={instanceError}'));checks++;
assert.ok(sourceText.includes('source model changed during replay'));checks++;
console.log(JSON.stringify({checks,scope:'Template response, strict metadata rejection, fresh lifecycle, selection and library action'}));
