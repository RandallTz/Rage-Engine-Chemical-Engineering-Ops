// Real common HTTP publication through production TS readers, lifecycle and existing views.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import ts from 'typescript';
const here=path.dirname(fileURLToPath(import.meta.url)),root=path.dirname(here),require=createRequire(import.meta.url),cache=new Map();
let displayedModel;
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(file.endsWith('useHojasMotor.ts'))return {useHojasMotor:()=>displayedModel?[displayedModel]:[]};
  if(file.endsWith('.json'))return {default:JSON.parse(fs.readFileSync(file,'utf8'))};
  if(file.endsWith('.css'))return {default:{}};
  if(cache.has(file))return cache.get(file).exports;
  const m={exports:{}};cache.set(file,m);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('module','exports','require',code)(m,m.exports,id=>id==='next/navigation'?{useRouter:()=>({push(){}}),usePathname:()=>'/models/inverse-mixer/results'}:id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id));return m.exports;
}
let checks=0;const check=(v,message)=>{assert.ok(v,message);checks++;};
const live=JSON.parse(fs.readFileSync(path.join(root,'.tmp/f3-inverse-http/publication.json'),'utf8'));
const {leerResultados}=load(path.join(here,'motores/resultados/lector'));
const {readCompilationReport}=load(path.join(here,'motores/modelo/compilation'));
const {readInverseSpecification,readInverseSolve,inverseDataIds,declaredInverseSI}=load(path.join(here,'motores/modelo/inverseSpecification'));
const {steadySignature,steadyResultSignature,steadyCSV}=load(path.join(here,'motores/modelo/steadyContract'));
check(leerResultados(live.result)===live.result,'Inverse HTTP result accepted');check(leerResultados(live.forward)===live.forward,'Forward HTTP result unchanged');check(readCompilationReport(live.report)===live.report,'Inverse HTTP report accepted');
const value=id=>live.result.series.find(row=>row.id===id).valores;
check(Math.abs(value('steady.'+live.names.F1)-6)<1e-11,'Mixer freed F1 = 6 mol/s');check(Math.abs(value('steady.residual.specification.outlet-fraction'))<1e-12,'Specification residual = zero');
for(const mutate of [r=>r.version=2,r=>r.extra=true,r=>r.freedInputs=[],r=>r.freedInputs.push(structuredClone(r.freedInputs[0])),r=>r.specifications.push(structuredClone(r.specifications[0])),r=>r.freedInputs[0].quantityId=r.specifications[0].quantityId]){const r=structuredClone(live.record);mutate(r);assert.throws(()=>readInverseSpecification(r));checks++;}
const mutations=[
 r=>r.procedencia.compilation.inverseSpecification.rows[0].targetSI=.61,
 r=>r.procedencia.compilation.inverseSpecification.rows[0].quantityId=live.names.F3,
 r=>r.procedencia.compilation.inverseSpecification.freedInputs[0].quantityId=live.names.F2,
 r=>r.procedencia.compilation.variables.reverse(),
 r=>r.procedencia.compilation.residualRows.pop(),
 r=>r.procedencia.compilation.variables.at(-1).seedSI=2,
 r=>r.procedencia.compilation.variables.at(-1).boundsSI[1]=51,
 r=>r.procedencia.compilation.variables.at(-1).scaleSI=2,
 r=>r.procedencia.compilation.residualRows.at(-1).scaleSI=.2,
 r=>r.procedencia.compilation.inverseSpecification.seedRegularity.augmentedSigmaMin=0,
 r=>r.procedencia.compilation.inverseSpecification.seedRegularity.sensitivity=[[null]],
 r=>r.procedencia.compilation.inverseSpecification.extra=1,
 r=>r.procedencia.compilation.inverseSpecification.data.extra={texto:'1',unidad:'1'},
 r=>r.procedencia.compilation.specificationSignature='0'.repeat(64),
 r=>r.procedencia.steadyDiagnostics.inverseSpecification.specificationSignature='0'.repeat(64),
 r=>r.procedencia.steadyDiagnostics.inverseSpecification.freedInputs=[],
 r=>r.procedencia.steadyDiagnostics.inverseSpecification.seedRegularity.forwardSigmaMin=0,
 r=>r.series.find(s=>s.id==='steady.residual.specification.outlet-fraction').valores+=1e-9,
 r=>r.series.find(s=>s.id==='steady.'+live.names.F1).unidadSI='kg/s',
 r=>{delete r.procedencia.compilation.inverseSpecification;delete r.procedencia.compilation.specificationSignature;delete r.procedencia.steadyDiagnostics.inverseSpecification;},
];
for(const resign of [false,true])for(const mutate of mutations){const bad=structuredClone(live.result);mutate(bad);if(resign)bad.procedencia.steadyDiagnostics.resultSignature=steadyResultSignature(bad);assert.throws(()=>leerResultados(bad));checks++;}
// An attacker can re-sign unkeyed fingerprints: semantic target/declaration checks must still reject.
for(const [id,value] of [
 [live.record.specifications[0].targetDataId,'.61'],
 [live.record.specifications[0].residualScaleDataId,'.2'],
 [live.record.freedInputs[0].upperDataId,'51'],
]){
 const bad=structuredClone(live.result),report=bad.procedencia.compilation;
 report.inverseSpecification.data[id].texto=value;
 report.specificationSignature=steadySignature([report.inverseSpecification.record,report.inverseSpecification.data]);
 bad.procedencia.steadyDiagnostics.inverseSpecification.specificationSignature=report.specificationSignature;
 bad.procedencia.steadyDiagnostics.resultSignature=steadyResultSignature(bad);
 assert.throws(()=>leerResultados(bad),`Re-signed ${id} edit must be rejected`);checks++;
}
check(Math.abs(declaredInverseSI({texto:'25.2',unidad:'kmol/h'},'mol/s')-7)<1e-12,'Existing unit catalog validates molar conversions');
// F3H-1: the client admits the constant grammar Python admits (`pi`, unary plus), in direct and published form.
check(Math.abs(declaredInverseSI({texto:'pi/6',unidad:'1'},'1')-Math.PI/6)<1e-15&&declaredInverseSI({texto:'+0.6',unidad:'1'},'1')===.6&&declaredInverseSI({texto:'-pi',unidad:'1'},'1')===-Math.PI,'Client admits pi and unary plus');
for(const [text,variant] of Object.entries(live.variants)){check(leerResultados(variant.result)===variant.result,`HTTP result with target ${text} accepted`);check(readCompilationReport(variant.report)!==undefined,`HTTP compilation with target ${text} accepted`);}
check(Math.abs(live.variants['pi/6'].result.series.find(s=>s.id==='steady.residual.specification.outlet-fraction').valores)<1e-12,'pi/6 target solved over HTTP');
assert.throws(()=>declaredInverseSI({texto:'300',unidad:'degC'},'K'));checks++;
const source=structuredClone(live.model),data=Object.fromEntries(inverseDataIds(live.record).map(id=>[id,source.datos[id].declaracion]));
for(const id of Object.keys(data))delete source.datos[id];
const inverseSolve=readInverseSolve({version:1,record:live.record,data});
const {nuevaHoja,guardarHoja,leerHojas}=load(path.join(here,'app/motor/hojasMotor'));
const {commonSource,derivedSourceIdentity,selectedDerivedModel,reconcileDerived,carryInverseSolve}=load(path.join(here,'app/models/derivedSelection'));
const {firmaHoja}=load(path.join(here,'app/motor/modeloHojaMotor'));
const model={...nuevaHoja(live.model.nombre),id:live.model.id,commonModel:source};
model.derivedSelection={version:1,sourceSignature:derivedSourceIdentity(commonSource(model)),selection:source.motores.derivedExecution,inverseSolve};
assert.deepEqual(selectedDerivedModel(model),live.model);checks++;
const changed=structuredClone(model);changed.derivedSelection.inverseSolve.data[live.record.specifications[0].targetDataId].texto='.5';
check(firmaHoja(changed)!==firmaHoja(model),'Specification changes invalidate run signature');
check(derivedSourceIdentity(commonSource(changed))===derivedSourceIdentity(commonSource(model)),'Specification edits preserve Model source');
assert.deepEqual(changed.derivedSelection.selection,model.derivedSelection.selection);checks++;
// F3H-2: a Transform re-pin keeps the Solve record while it still reads against the new selection; otherwise it is dropped with a notice.
{const selection=model.derivedSelection.selection,common=commonSource(model);
 check(carryInverseSolve(model.derivedSelection,selection,common).inverseSolve===inverseSolve,'Re-pin keeps a compatible inverse Solve record');
 check(!Object.keys(carryInverseSolve(undefined,selection,common)).length,'No record, nothing carried');
 const noTarget=structuredClone(selection);noTarget.unknowns=noTarget.unknowns.filter(id=>id!==live.record.specifications[0].quantityId);noTarget.reconstructions=noTarget.reconstructions.filter(r=>r.quantityId!==live.record.specifications[0].quantityId);
 const a=carryInverseSolve(model.derivedSelection,noTarget,common);check(!a.inverseSolve&&a.inverseNotice.includes('no longer an unknown'),'Re-pin drops with notice when a target is no longer an output');
 const noInput=structuredClone(selection);delete noInput.parameters[live.record.freedInputs[0].quantityId];
 const b=carryInverseSolve(model.derivedSelection,noInput,common);check(!b.inverseSolve&&b.inverseNotice.includes('no longer a parameter'),'Re-pin drops with notice when a freed input is no longer a parameter');
 const stale=structuredClone(common);stale.datos[live.record.specifications[0].targetDataId]=structuredClone(live.model.datos[live.record.specifications[0].targetDataId]);
 check(carryInverseSolve(model.derivedSelection,selection,stale).inverseNotice.includes('no longer fresh'),'Re-pin drops with notice when data identities collide');
 const {applySteadyTransformResult}=load(path.join(here,'app/models/derivedSelection'));
 const pinned=applySteadyTransformResult(model,{model:structuredClone(source),dynamicSelection:structuredClone(selection),dynamicSignature:'x',report:{selection,rows:[]}});
 check(pinned.derivedSelection.inverseSolve===inverseSolve||JSON.stringify(pinned.derivedSelection.inverseSolve)===JSON.stringify(inverseSolve),'applySteadyTransformResult keeps the Solve record');}
const storage=new Map();globalThis.localStorage={getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v)};globalThis.window={dispatchEvent:()=>true};
guardarHoja(model);assert.deepEqual(leerHojas().find(m=>m.id===model.id).derivedSelection.inverseSolve,inverseSolve);checks++;
const saved={...model,resultadoRef:{firma:firmaHoja(model),estado:'resuelto',fecha:new Date().toISOString()}};
check(reconcileDerived(saved,{...changed,resultadoRef:saved.resultadoRef}).resultadoRef===undefined,'Specification changes clear saved run');
const {resolverHojaEngine}=load(path.join(here,'app/motor/resolverEngine'));
const {inverseTransport,requestCompilationAssessment}=load(path.join(here,'motores/modelo/servicioModelo'));
const originalFetch=globalThis.fetch;let requested;
globalThis.fetch=async(url,options)=>{requested={url,body:JSON.parse(options.body)};return new Response(JSON.stringify(live.result),{status:200,headers:{'Content-Type':'application/json'}});};
const wrapped=await resolverHojaEngine(model,{transporte:inverseTransport(live.record)});
const {validateSavedSteady}=load(path.join(here,'app/motor/resultadosMotor'));
validateSavedSteady(JSON.parse(JSON.stringify(wrapped)),model.id,firmaHoja(model));checks++;
check(requested.url.endsWith('/modelo/resolver')&&steadySignature(requested.body.inverseSpecification)===steadySignature(live.record),'Solve uses common HTTP route with exact record');
check(wrapped.commonResult===live.result||steadySignature(wrapped.commonResult)===steadySignature(live.result),'Common result retained without recalculation');
globalThis.fetch=async()=>new Response(JSON.stringify(live.report),{status:200,headers:{'Content-Type':'application/json'}});
const compilation=await requestCompilationAssessment({modelo:live.model,inverseSpecification:live.record});check(compilation.report.version===2,'Compilation uses inverse request instead of forward assessment');
globalThis.fetch=async()=>new Response(JSON.stringify(live.forward),{status:200,headers:{'Content-Type':'application/json'}});
await assert.rejects(()=>inverseTransport(live.record)(live.model));checks++;
globalThis.fetch=originalFetch;
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
const {InverseControls}=load(path.join(here,'app/models/DerivedSolve'));
const quantities=Object.entries(live.names).map(([name,id])=>({id,name,input:name,latex:name,unit:name==='x3'?'1':'mol/s',coordinate:false}));
const controls=renderToStaticMarkup(React.createElement(InverseControls,{model,quantities,disabled:false,change(){}}));
const closed=renderToStaticMarkup(React.createElement(InverseControls,{model,quantities,disabled:false,change(){},closureVolumeIds:['drum']}));
check(closed.includes('not yet lowered over package thermodynamic closures')&&closed.includes('drum')&&!closed.includes('Add output target')&&!closed.includes('Target quantity 1'),'Solve withholds inverse controls for package-closure models and says why');
const noticed=renderToStaticMarkup(React.createElement(InverseControls,{model:{...model,derivedSelection:{...model.derivedSelection,inverseSolve:undefined,inverseNotice:'The inverse specifications entered in Solve were discarded because test.'}},quantities,disabled:false,change(){}}));
check(noticed.includes('were discarded because test.'),'Solve shows the discard notice');
for(const text of ['Target quantity 1','Input to free 1','Target value 1','Freed input seed 1','Freed input lower bound 1','Freed input upper bound 1','Specification residual scale 1','1 specifications','1 freed inputs'])check(controls.includes(text),'Existing Solve renders '+text);
displayedModel={...model,resultado:wrapped};
const {default:Results,PublishedChecks}=load(path.join(here,'app/motor/ResultadosHoja'));
const checksHtml=renderToStaticMarkup(React.createElement(PublishedChecks,{checks:[
 {id:'reactions.equilibrium_limit.cell',descripcion:'Equilibrium limit',valor:0.04,tolerancia:0.001},
 {id:'mass.balance',descripcion:'Mass balance',valor:2,tolerancia:1},
]}));
check(checksHtml.includes('Equilibrium-limit diagnostics')&&checksHtml.includes('reactions.equilibrium_limit.cell · Equilibrium limit: 0.04 / reference tolerance 0.001 · Diagnostic'),'Above-tolerance equilibrium limit is a diagnostic');
check(checksHtml.includes('mass.balance · Mass balance: 2 / tolerance 1 · Failed'),'A failed certificate remains failed');
const html=renderToStaticMarkup(React.createElement(Results,{id:model.id}));
const {default:AssessmentText}=load(path.join(here,'app/models/AssessmentText'));
const {responseError}=load(path.join(here,'motores/modelo/assessment'));
const rejection=renderToStaticMarkup(React.createElement(AssessmentText,{error:responseError(live.rejection,422,'Rejected')}));
check(rejection.includes('inverse_target_unattainable')&&rejection.includes('Reachability evidence')&&rejection.includes('bound'),'Existing rejection display retains the HTTP reachability evidence');
for(const text of ['Steady-state results','F1','mol/s','outlet-fraction','Inverse specifications','Freed inputs'])check(html.includes(text),'Existing Results renders '+text);
check(html.includes('>6<'),'Existing Results shows solved input 6');check(steadyCSV(live.result).includes('specification.outlet-fraction'),'CSV preserves specification residual');
fs.writeFileSync(path.join(root,'.tmp/f3-inverse-http/rendered.html'),'<!doctype html>'+controls+html);
console.log(JSON.stringify({checks,scope:'HTTP mixer publication, strict TS tampering checks, Solve-only invalidation, common transport and existing Solve/Results rendering'}));
