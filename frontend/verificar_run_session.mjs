// Demo 0.3 C9: headless check of the Solve live-run client against a real backend.
// The client under test is frontend/motores/modelo/servicioModelo.ts (run-session start/status/advance/stop).
// Plant: the closed heated region of tests/test_time_inputs.py with its heater duty declared a time input, so
// the published energy is the exact integral of the duty and is checked against a piecewise-linear reference.
//
// Usage: start a backend on a free port (never 8004 or 8005), for example
//   python -m uvicorn backend.main:app --port 8031
// then: RUN_SESSION_API=http://127.0.0.1:8031 node frontend/verificar_run_session.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import ts from 'typescript';

const api=process.env.RUN_SESSION_API;
if(!api)throw new Error('Set RUN_SESSION_API to a backend you started on a free port (not 8004 or 8005).');
if(/:(8004|8005|3000)\b/.test(api))throw new Error('Use your own backend port, not 3000, 8004 or 8005.');
process.env.NEXT_PUBLIC_API_URL=api;

const directory=path.dirname(fileURLToPath(import.meta.url)),root=path.resolve(directory,'..'),require=createRequire(import.meta.url),cache=new Map();
function load(file){
  if(!path.extname(file))file+=fs.existsSync(file+'.ts')?'.ts':'.tsx';
  if(cache.has(file))return cache.get(file).exports;
  const loadedModule={exports:{}};cache.set(file,loadedModule);
  const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText;
  new Function('exports','module','require','process',code)(loadedModule.exports,loadedModule,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id),process);
  return loadedModule.exports;
}
const client=load(path.join(directory,'motores/modelo/servicioModelo'));
const {startRunSession,runSessionStatus,advanceRunSession,stopRunSession,RunSessionError}=client;
const {readRunTimeline}=load(path.join(directory,'motores/resultados/runTimeline'));

// The model is authored by the shared deduction operations in Python, exactly as tests/test_run_session.py does.
const model=JSON.parse(execFileSync('python',['-c',[
  'import json, sys',
  "sys.path[:0] = ['.', 'tests']",
  'from test_time_inputs import heated_region, selection_model',
  'author, energy = heated_region()',
  "print(json.dumps(selection_model(author, energy, inputs=['heaterDuty'])))"].join('\n')],{cwd:root,encoding:'utf8',maxBuffer:64<<20}));

// Section 6 (C9-R1): the same plant with the duty declared in kW. Authored before any request, because a long
// blocking call would leave the HTTP keep-alive socket closed by the server.
const kw=JSON.parse(execFileSync('python',['-c',[
    'import json, sys',
    "sys.path[:0] = ['.', 'tests']",
    'import test_time_inputs as ti',
    'original = ti.Author.append',
    'def append(self, kind, **kw):',
    "    if kw.get('name') in ('heaterDuty', 'heaterPower'): kw['unit'] = 'kW'",
    '    return original(self, kind, **kw)',
    'ti.Author.append = append',
    'author, energy = ti.heated_region()',
    'ti.Author.append = original',
    "model = ti.selection_model(author, energy, inputs=['heaterDuty'])",
    "key = model['motores']['derivedExecution']['timeInputs']['heaterDuty']",
    "model['datos'][key]['declaracion'] = {'texto': '1', 'unidad': 'kW'}",
    'print(json.dumps(model))'].join('\n')],{cwd:root,encoding:'utf8',maxBuffer:64<<20}));
const POWER=50,HORIZON=600;
const duty=(value,unit='W')=>[{quantityId:'heaterDuty',value,unit}];
let checks=0;const ok=(condition,message)=>{assert.ok(condition,message);checks++;};
async function rejects(promise,status,code){
  try{await promise;}catch(error){ok(error instanceof RunSessionError,'a located RunSessionError');assert.equal(error.status,status,error.message);assert.equal(error.code,code,error.message);checks+=2;return error;}
  assert.fail(`expected ${status} ${code}`);
}
async function ready(id){
  for(let i=0;i<600;i++){const status=await runSessionStatus(id);if(status.state!=='lowering')return status;await new Promise(r=>setTimeout(r,500));}
  assert.fail('lowering did not finish');
}
const energyId=result=>result.series.find(row=>row.id.startsWith('campo.')&&!row.id.endsWith('heaterDuty')&&row.valores[0]===0&&row.valores.at(-1)>0).id;

// 1. Live run with pace changes, an operator action at the edge, a refused action, a retry and an operator stop.
{
  const {sessionId,state}=await startRunSession(model);ok(typeof sessionId==='string'&&state==='lowering','start answers at once');
  const status=await ready(sessionId);
  assert.equal(status.state,'ready',JSON.stringify(status.error));checks++;
  assert.deepEqual(status.timeInputs,['heaterDuty']);assert.equal(status.horizon,HORIZON);assert.equal(status.edge,0);checks+=3;
  let seq=0;const first=await advanceRunSession(sessionId,seq++,0);
  ok(first.edge===0&&first.rows.t.length===0&&first.jumps.length===0,'a zero-length advance (keep-alive) steps nothing and returns no rows');
  // Paced stretches of different lengths, as the client's wall clock chooses them.
  let edge=0;for(const to of [7.5,40,41,120,200]){const r=await advanceRunSession(sessionId,seq++,to);ok(r.edge>=to-1e-12&&r.edge>=edge,'the edge moves forward to the requested time');edge=r.edge;ok(r.rows.t.every(t=>t<=r.edge),'preview rows lie inside the stretch');}
  // A malformed or undeclared action refuses the request before stepping and consumes no sequence number.
  const undeclared=await rejects(advanceRunSession(sessionId,seq,210,[{quantityId:'notAnInput',value:1,unit:'W'}]),422,'time_input_not_declared');
  ok(undeclared.diagnostics[0].path==='actions[0].quantityId','the refusal is located');
  await rejects(advanceRunSession(sessionId,seq,210,duty(1,'K')),422,'unit_mismatch');
  // Operator action at the edge t* = 200 s, applied with a zero-length advance (the paused Apply now).
  const applied=await advanceRunSession(sessionId,seq,edge,duty(0.1,'kW'));
  ok(applied.applied&&applied.applied.t===edge&&applied.applied.left.heaterDuty===POWER&&applied.applied.right.heaterDuty===100,'the action applies at the edge with left and right states');
  const retry=await advanceRunSession(sessionId,seq,edge,duty(0.1,'kW'));assert.deepEqual(retry,applied);checks++;
  await rejects(advanceRunSession(sessionId,seq,edge+1),409,'sequence_reused');
  seq++;
  const behind=await advanceRunSession(sessionId,seq++,400);ok(behind.rows.values.heaterDuty.every(v=>v===100),'the held input keeps its new value');
  const stopped=await stopRunSession(sessionId);
  ok(stopped.state==='finished'&&stopped.result.estado==='parcial','an operator stop publishes a partial result');
  const timeline=readRunTimeline(stopped.result,(where,why)=>{throw new Error(`${where}: ${why}`);});
  ok(timeline.termination.reason==='operator_stop'&&timeline.termination.tEnd===400,'the termination is recorded');
  ok(timeline.actions.length===1&&timeline.actions[0].origin==='operator'&&timeline.actions[0].t===200&&timeline.actions[0].value===100,'the operator action is in the timeline');
  ok(stopped.result.eventos.some(e=>e.codigo==='timeline_action'&&e.valor===200),'the action is a chart event');
  const axis=stopped.result.ejes[0].valores,energy=stopped.result.series.find(row=>row.id===energyId(stopped.result)).valores;
  const exact=(t,side)=>t<200||t===200&&side==='left'?POWER*t:POWER*200+100*(t-200);
  let worst=0;axis.forEach((t,i)=>{const side=axis[i+1]===t?'left':'right';worst=Math.max(worst,Math.abs(energy[i]-exact(t,side))/(POWER*HORIZON));});
  ok(worst<1e-8,`published energy against the exact piecewise integral (relative ${worst})`);
  ok(axis.filter(t=>t===200).length===2,'the action instant carries the left and right values');
  await rejects(runSessionStatus(sessionId),404,'session_unknown');
}
// 2. A run to its horizon publishes a complete result from the last advance; a later action is refused.
{
  const {sessionId}=await startRunSession(model);assert.equal((await ready(sessionId)).state,'ready');checks++;
  let seq=0,last;for(const to of [0,150,HORIZON])last=await advanceRunSession(sessionId,seq++,to);
  ok(last.finished&&last.state==='finished'&&last.result.estado==='resuelto','the horizon publishes a result');
  ok(readRunTimeline(last.result,(w,m)=>{throw new Error(`${w}: ${m}`);}).termination.reason==='completed','termination completed');
  await rejects(advanceRunSession(sessionId,seq,HORIZON,duty(10)),409,'session_finished');
  const status=await runSessionStatus(sessionId);ok(status.state==='finished'&&status.result.estado==='resuelto','status serves the read result');
  await stopRunSession(sessionId);
}
// 3. Unsupported selections are located at start.
{
  const steady=structuredClone(model);steady.motores.derivedExecution.version=5;
  const error=await rejects(startRunSession(steady),422,'no_soportado');ok(error.diagnostics[0].path==='motores.derivedExecution'&&error.message.length>0,'a steady selection is refused at start, located at the selection');
  const indexed=await rejects(startRunSession({...model,indexSet:{}}),422,'http_422');ok(indexed.diagnostics[0].path==='indexSet','an invalid indexed model is refused with its path');
}
// 4. Static: the Solve surface uses only these routes and labels its preview uncertified; Signal rows reach the worksheet.
{
  const solve=fs.readFileSync(path.join(directory,'app/models/DerivedSolve.tsx'),'utf8'),common=fs.readFileSync(path.join(directory,'app/models/CommonModelContent.tsx'),'utf8');
  ok(/Live preview · uncertified/.test(solve)&&/never replace Results/.test(solve),'the preview is labelled uncertified');
  ok(!/fetch\(/.test(solve.slice(solve.indexOf('function LiveRun'))),'the live run calls the shared client, not its own fetch');
  ok(/derivedResult\(latest,result\)/.test(solve),'only the published document is saved as the result');
  ok(/\['senal','Signal'\]/.test(common)&&/operation\.family==='signal'/.test(common),'the Signal family is offered when signal rows exist');
}
{
  const {equationSections}=load(path.join(directory,'app/models/equationWorkbench'));
  const row=(id,family,ownerId,rule='declared_relation')=>({id,title:id,family,ownerId,kind:'constraint',dependent:false,current:true,latex:'',derivation:{rule,inputIds:[],beforeLatex:[],assumptions:[]}});
  const report={equations:[row('operation.1','signal','system'),row('operation.2','signal','system'),row('energy.region_a.1','energy','region_a','declared_law'),row('operation.3','energy','system')]};
  const signal=equationSections(report,'signal','region_a'),energy=equationSections(report,'energy','region_a');
  ok(signal.result.map(r=>r.id).join()==='operation.1,operation.2'&&signal.shared.length===0,'Signal rows owned by the system are the Signal family result');
  ok(energy.shared.map(r=>r.id).join()==='operation.3'&&energy.result.every(r=>r.family==='energy'),'physical families keep their region and cross-domain sections');
}
// 6. C9-R1: a non-SI declared unit. The duty is declared in kW and set to 1 kW; the rows are SI and Python names
// their unit, so the preview labels 1000 W, never 1000 kW. The client converts nothing.
{

  const {sessionId}=await startRunSession(kw);const status=await ready(sessionId);
  assert.equal(status.state,'ready',JSON.stringify(status.error));checks++;
  ok(status.stateUnits&&status.stateIds.every(id=>typeof status.stateUnits[id]==='string'),'status names the unit of every row');
  ok(status.stateUnits.heaterDuty==='W','the duty rows are labelled in W although the Model declares kW');
  const energyUnit=status.stateUnits[status.stateIds.find(id=>id!=='heaterDuty'&&status.stateUnits[id]==='J')];ok(energyUnit==='J','the energy rows are labelled in J');
  const a=await advanceRunSession(sessionId,0,50);ok(a.rows.values.heaterDuty.every(v=>v===1000),'1 kW arrives as 1000 in the stated unit W');
  const applied=await advanceRunSession(sessionId,1,a.edge,duty(2,'kW'));ok(applied.applied.right.heaterDuty===2000,'an action in kW is converted by Python to 2000 W');
  await stopRunSession(sessionId);
  const solve=fs.readFileSync(path.join(directory,'app/models/DerivedSolve.tsx'),'utf8');
  ok(/const unit=\(id:string\)=>sessionRef\.current\?\.stateUnits\[id\]\?\?'SI'/.test(solve),'the preview labels rows with the unit Python states');
  ok(!/quantities\.find\(q=>q\.id===id\)\?\.unit/.test(solve),'the declared workbench unit is not used as a label of SI rows');
}
console.log(`verificar_run_session: ${checks} checks passed against ${api}`);
