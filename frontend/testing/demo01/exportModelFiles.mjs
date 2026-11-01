// Write the Demo 0.1 fixtures as importable rage.model-file documents (Model library → Import model).
// node frontend/testing/demo01/exportModelFiles.mjs [--check]
// The files carry the frozen fixtures unchanged, with a fixed sheet id and date so the output is reproducible.
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import ts from 'typescript';

const directory=path.dirname(fileURLToPath(import.meta.url)),frontend=path.resolve(directory,'../..'),root=path.dirname(frontend);
const require=createRequire(path.join(frontend,'package.json')),cache=new Map();
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
const {REGRESSION_MODELS}=load(path.join(frontend,'testing/modelFixtures'));
const models=REGRESSION_MODELS.find(group=>group.name==='Demo 0.1').create();
const output=path.join(root,'docs/ejemplos/demo-0.1');
const names={'demo-0.1-batch-reactor':'batch-reactor.rage-model.json','demo-0.1-flash-drum':'flash-drum.rage-model.json'};
let stale=0;
for(const model of models){
  const file=path.join(output,names[model.id]);
  const text=JSON.stringify({format:'rage.model-file',version:1,model:{...model,actualizada:'2026-10-31T00:00:00.000Z'}},null,1)+'\n';
  if(process.argv.includes('--check')){
    if(!fs.existsSync(file)||fs.readFileSync(file,'utf8')!==text){console.error('stale: '+path.relative(root,file));stale++;}
  }else{
    fs.mkdirSync(output,{recursive:true});fs.writeFileSync(file,text);console.log('wrote '+path.relative(root,file));
  }
}
if(stale)process.exit(1);
