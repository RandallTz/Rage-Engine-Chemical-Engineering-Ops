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

execFileSync('node',[path.join(directory,'testing/demo01/exportModelFiles.mjs'),'--check'],{cwd:root,stdio:'inherit'});checks++;
const {REGRESSION_MODELS}=load(path.join(directory,'testing/modelFixtures'));
const {leerModeloComun}=load(path.join(directory,'motores/modelo/lector'));
const {readCompilationReport,readThermodynamicClosures}=load(path.join(directory,'motores/modelo/compilation'));
const sheets=REGRESSION_MODELS.find(group=>group.name==='Demo 0.1').create();
check(sheets.map(sheet=>sheet.id).join()==='demo-0.1-batch-reactor,demo-0.1-flash-drum','Both Demo 0.1 fixtures are registered');
for(const sheet of sheets){
  leerModeloComun(structuredClone(sheet.commonModel));checks++;
  const file=JSON.parse(fs.readFileSync(path.join(root,'docs/ejemplos/demo-0.1',sheet.id==='demo-0.1-batch-reactor'?'batch-reactor.rage-model.json':'flash-drum.rage-model.json'),'utf8'));
  check(file.format==='rage.model-file'&&file.version===1&&JSON.stringify(file.model.commonModel)===JSON.stringify(sheet.commonModel),sheet.id+': the importable file carries the frozen fixture unchanged');
}

const script=['import sys,json','sys.path.insert(0,"tests")','from demo01_reactor import frozen_model as reactor','from demo01_flash import frozen_model as flash',
  'from core.compilador.derived import DerivedSystem','print(json.dumps([DerivedSystem(m()).report for m in (reactor, flash)]))'].join('\n');
const reports=JSON.parse(execFileSync('python',['-c',script],{cwd:root,encoding:'utf8',maxBuffer:64*1024*1024}));
for(const report of reports){
  const closures=report.derivedExecution.thermodynamicClosures;
  check(report.closureStrategy==='package_closure'&&Array.isArray(closures)&&closures.length===1,report.sourceModelId+': package closure report');
  assert.deepEqual(readCompilationReport(structuredClone(report)),report);checks++;
  assert.deepEqual(readThermodynamicClosures(closures),closures);checks++;
  for(const [label,mutate] of [
    ['closures without the package strategy',r=>{r.closureStrategy='declared_assumption';}],
    ['package strategy without closures',r=>{delete r.derivedExecution.thermodynamicClosures;}],
    ['unknown closure field',r=>{r.derivedExecution.thermodynamicClosures[0].extra=1;}],
    ['unknown closure mode',r=>{r.derivedExecution.thermodynamicClosures[0].mode='flash';}],
    ['unknown candidate phase',r=>{r.derivedExecution.thermodynamicClosures[0].candidatePhases=['L2'];}],
    ['negative evaluations',r=>{r.derivedExecution.thermodynamicClosures[0].evaluations=-1;}],
    ['foreign closure source',r=>{r.derivedExecution.thermodynamicClosures[0].source='client';}],
    ['duplicate closure volume',r=>{r.derivedExecution.thermodynamicClosures.push(structuredClone(r.derivedExecution.thermodynamicClosures[0]));}],
  ]){const bad=structuredClone(report);mutate(bad);assert.throws(()=>readCompilationReport(bad),undefined,report.sourceModelId+': rejects '+label);checks++;}
}
const [reactor,drum]=reports.map(r=>r.derivedExecution.thermodynamicClosures[0]);
check(reactor.mode==='single_phase'&&reactor.specification==='UV'&&reactor.liquidOnly&&reactor.anchor==='liquid','Reactor: liquid-only UV closure with the liquid formation anchor');
check(drum.mode==='equilibrium'&&drum.specification==='PH'&&drum.candidatePhases.join()==='V,L','Drum: PH equilibrium closure with vapour and liquid candidates');
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
const CompilationSummary=load(path.join(directory,'app/models/CompilationSummary')).default;
for(const report of reports){
  const html=renderToStaticMarkup(React.createElement(CompilationSummary,{report}));
  check(html.includes('derived-execution bridge')&&html.includes('every RHS evaluation'),'Package closure summary explains ongoing coupling');
  for(const closure of report.derivedExecution.thermodynamicClosures){
    check(html.includes(closure.volumeId)&&html.includes(closure.package)&&html.includes(closure.specification),'Summary renders published volume, package and state specification');
  }
  check(!html.includes('The declared thermodynamic assumptions remain attached'),'Package closure does not use the generic summary');
}
const {commonTimeEvents,ResultEvents}=load(path.join(directory,'app/motor/ResultEvents'));
const {commonEventMarkers,EventMarkerLabel}=load(path.join(directory,'app/motor/TableroMotor'));
const events=[{codigo:'aparicion_fase',ejeId:'time',valor:12.25,descripcion:'Vapour appeared',propietarioId:'volumen:drum'},
  {codigo:'desaparicion_fase',ejeId:'time',valor:20.5,descripcion:'Liquid disappeared',propietarioId:'volumen:drum'},
  {codigo:'other',ejeId:'space',valor:3,descripcion:'Spatial event'}];
const common={ejes:[{id:'time',rol:'tiempo',unidadSI:'s'},{id:'space',rol:'coordenada',unidadSI:'m'}],eventos:events};
assert.deepEqual(commonTimeEvents(common),events.slice(0,2));checks++;
const html=renderToStaticMarkup(React.createElement(ResultEvents,{result:common}));
for(const text of ['Phase appearance','Phase disappearance','12.25','20.5','Vapour appeared','Liquid disappeared','volumen:drum'])check(html.includes(text),'Event list publishes '+text);
check(!html.includes('Spatial event'),'Spatial events are not labelled as time events');
check(commonTimeEvents(undefined).length===0,'Legacy results without common events are unchanged');
check(renderToStaticMarkup(React.createElement(ResultEvents,{}))==='','No fabricated legacy event panel');
const markers=commonEventMarkers({commonResult:common},{tipo:'tiempo',x:'t'},'K');
assert.deepEqual(markers.map(marker=>marker.props.x),[12.25,20.5]);checks++;
check(markers.every(marker=>marker.props.yAxisId==='K'&&marker.props.label.value.includes('volumen:drum')),'Event markers use the actual chart axis and owner');
check(markers.every(marker=>marker.props.label.content.type===EventMarkerLabel),'Event labels use the measured plot-bounded renderer');
check(markers.every(marker=>marker.props.label.value.includes('·')&&!marker.props.label.value.includes('�')),'Marker text uses the UTF-8 separator');
for(const file of ['app/models/CompilationSummary.tsx','app/motor/ResultCharts.tsx','app/motor/TableroMotor.tsx','app/motor/ResultEvents.tsx'])check(!require('fs').readFileSync(path.join(directory,file),'utf8').includes('�'),'No replacement character in '+file);
check(commonEventMarkers({commonResult:common},{tipo:'perfil',x:'t'},'K').length===0,'No markers on spatial profiles');
check(commonEventMarkers({commonResult:common},{tipo:'tiempo',x:'T'},'K').length===0,'No time markers on phase plots');
check(commonEventMarkers({commonResult:common},{tipo:'tiempo',x:'t'},undefined).length===0,'No markers without a plotted y axis');
check(commonTimeEvents({...common,eventos:[]}).length===0,'No events is valid');
console.log(JSON.stringify({checks,models:sheets.length,compilationReader:'passed'}));
