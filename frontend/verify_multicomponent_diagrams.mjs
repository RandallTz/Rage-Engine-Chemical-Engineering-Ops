// F8 multicomponent diagrams: actual service publications through the strict reader, the plot projection and a
// server render of the real SVG charts. Every mark is compared with the published composition placed by this
// script's own barycentric map; no browser, no screenshot. Run: node frontend/verify_multicomponent_diagrams.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import ts from 'typescript';
const directory=path.dirname(fileURLToPath(import.meta.url)),root=path.dirname(directory),require=createRequire(import.meta.url),cache=new Map();
const React=require('react'),{renderToStaticMarkup}=require('react-dom/server');
function load(file){
  if(!path.extname(file))file=fs.existsSync(file+'.tsx')?file+'.tsx':file+'.ts';
  if(file.endsWith('.css'))return new Proxy({},{get:(_,k)=>String(k)});
  if(cache.has(file))return cache.get(file).exports;
  const loaded={exports:{}};cache.set(file,loaded);
  const js=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  new Function('exports','module','require',js)(loaded.exports,loaded,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id));
  return loaded.exports;
}
fs.mkdirSync(path.join(root,'.tmp'),{recursive:true});
const output=path.join(root,'.tmp/f8-multicomponent-publication.json');
const python=spawnSync('python',['-c',`
import json,sys
sys.path.insert(0,'tests')
from pathlib import Path
from test_multicomponent_diagram_route import ternary_body,components,BZ,W,E,TO,P
from test_ternary_liquid_liquid import margules_system
from backend import multicomponent_diagrams as service
from core import diagramas_equilibrio as dg, ternary_liquid_liquid as tl
import numpy as np
cases=[]
for T in (300.0,340.0):
    b=ternary_body(T=T);cases.append({'label':f'UNIFAC benzene-water-ethanol {T:g} K','request':b,'response':service.ternary_liquid_liquid(b)})
r=cases[0]['response'];t=r['tieLines'][len(r['tieLines'])//2]
xa=np.array([t['phases'][0]['composition'][k] for k in '123']);xb=np.array([t['phases'][1]['composition'][k] for k in '123'])
d=xa-xb;f=0.5*min(min(xa[i]/-d[i] for i in range(3) if d[i]<0),min(xb[i]/d[i] for i in range(3) if d[i]>0))
zA,zB=xa+f*d,xb-f*d;zA[2]=1-zA[0]-zA[1];zB[2]=1-zB[0]-zB[1]
lb=ternary_body(line={'start':{str(i+1):float(zA[i]) for i in range(3)},'end':{str(i+1):float(zB[i]) for i in range(3)}})
lines=[{'label':'line along a published tie line','request':lb,'response':service.composition_line(lb)}]
q=ternary_body(cas=(W,E,BZ,TO),line={'start':{'1':0.7,'2':0.1,'3':0.1,'4':0.1},'end':{'1':0.1,'2':0.1,'3':0.4,'4':0.4}})
lines.append({'label':'four-species line','request':q,'response':service.composition_line(q)})
sis=margules_system(900.0);budget=dg._Presupuesto(dg.PERFILES['exploratoria'])
analytic=service._publish_ternary(sis,[1,2,3],300.0,P,tl.trace(sis,300.0,P,tl.PROFILES['exploratoria']),budget,'mezcla-ideal')
rejected=[{'request':ternary_body(cas=(BZ,W)),'response':service.ternary_liquid_liquid(ternary_body(cas=(BZ,W)))}]
Path(sys.argv[1]).write_text(json.dumps({'ternary':cases,'lines':lines,'analytic':analytic,'rejected':rejected},allow_nan=False),encoding='utf8')
`,output],{cwd:root,encoding:'utf8',maxBuffer:64<<20});
assert.equal(python.status,0,python.stderr);
const data=JSON.parse(fs.readFileSync(output,'utf8'));
const motor=path.join(directory,'app/motor');
const lib=load(path.join(motor,'multicomponentDiagrams')),charts=load(path.join(motor,'TernaryLiquidLiquidChart'));
const Chart=charts.default,LineChart=charts.CompositionLineChart;
let checks=0;const check=(v,m)=>{assert.ok(v,m);checks++;};
const report=[];

// This script's own geometry (must equal the chart's declared geometry, checked once).
const G=charts.TERNARY_GEOMETRY;
check(G.side===520&&G.margin===48&&Math.abs(G.height-520*Math.sqrt(3)/2)<1e-12,'Declared ternary geometry');
const bary=x=>[G.margin+G.side*x[1]+G.side*x[2]/2,G.margin+G.height-G.height*x[2]];
const near=(p,q,tol=2e-3)=>Math.hypot(p[0]-q[0],p[1]-q[1])<=tol;
const elements=(html,kind)=>[...html.matchAll(/<(\w+)((?:\s+[\w-]+="[^"]*")*)\s*\/?>/g)].map(m=>({tag:m[1],a:Object.fromEntries([...m[2].matchAll(/([\w-]+)="([^"]*)"/g)].map(x=>[x[1],x[2]]))})).filter(e=>!kind||e.a['data-kind']===kind);
const pairs=s=>s.trim().split(/\s+/).map(v=>v.split(',').map(Number));

function drawTernary(label,request,response,order){
  const read=lib.readTernaryLiquidLiquid(structuredClone(response),request);
  check(JSON.stringify(read)===JSON.stringify(response),`${label}: the reader does not alter the publication`);
  const plot=lib.ternaryPlot(read,order),v=c=>order.map(id=>c[String(id)]);
  const html=renderToStaticMarkup(React.createElement(Chart,{plot,names:order.map(String)}));
  const ties=elements(html,'tie-line');
  check(ties.length===read.tieLines.length,`${label}: one segment per published tie line`);
  ties.forEach((e,k)=>{const t=read.tieLines[k];check(e.a['data-id']===t.id&&near([+e.a.x1,+e.a.y1],bary(v(t.phases[0].composition)))&&near([+e.a.x2,+e.a.y2],bary(v(t.phases[1].composition))),`${label}: tie line ${t.id} drawn at its published liquids`);});
  const sides=elements(html,'binodal');
  check(sides.length===2*read.branches.length,`${label}: two binodal sides per branch`);
  for(const s of sides){
    const b=read.branches.find(x=>x.id===s.a['data-branch']),k=s.a['data-phase']==='liquid-a'?0:1,pts=pairs(s.a.points);
    const want=b.tieLineIds.map(id=>bary(v(read.tieLines.find(t=>t.id===id).phases[k].composition)));
    check(pts.length===want.length&&pts.every((p,i)=>near(p,want[i])),`${label}: ${b.id} ${s.a['data-phase']} joins its own liquids in tie-line order`);
  }
  const special=kind=>read.specialPoints.filter(p=>p.kind===kind&&p.certificate.status==='pass');
  const plait=elements(html,'plait-point');
  check(plait.length===special('plait_point').length,`${label}: one mark per certified plait point`);
  plait.forEach((e,k)=>check(near([+e.a.cx,+e.a.cy],bary(v(special('plait_point')[k].composition))),`${label}: plait point at its published composition`));
  const edges=elements(html,'binary-edge'),edgeMarks=elements(html).filter(e=>e.a['data-mark']==='edge-liquid');
  check(edges.length===special('binary_edge').length&&edgeMarks.length===2*edges.length,`${label}: binary-edge pairs drawn`);
  edgeMarks.forEach((e,k)=>{const p=special('binary_edge')[k>>1].phases[k%2];check(near([+e.a.cx,+e.a.cy],bary(v(p.composition))),`${label}: edge liquid on its edge`);});
  const tri=elements(html,'three-phase');
  check(tri.length===special('three_phase').length,`${label}: one triangle per certified L-L-V point`);
  tri.forEach((e,k)=>{const want=special('three_phase')[k].phases.map(p=>bary(v(p.composition)));check(pairs(e.a.points).every((p,i)=>near(p,want[i])),`${label}: triangle vertices are the published phases`);});
  report.push({case:label,order:order.join(','),tieLines:ties.length,sides:sides.length,plait:plait.length,edges:edges.length,triangles:tri.length});
  return read;
}

const rejectedSpecials=[];
for(const {label,request,response} of data.ternary){
  for(const order of [[1,2,3],[3,1,2]])drawTernary(label,request,response,order);
  // Negative controls: the reader refuses a malformed or contradictory publication.
  const mutations=[
    r=>{r.requestId='other';},r=>{r.identity.model.version='9';},r=>{r.branches[0].tieLineIds[0]='missing';},
    r=>{r.tieLines[0].certificate.status='fail';},r=>{r.tieLines[0].phases[0].composition['1']+=1e-6;},
    r=>{r.tieLines[0].certificate.residuals[0].value=1;},r=>{r.tieLines[0].certificate.stability.tmMinimum=-1;},
    r=>{r.branches[0].ends.reverse();},r=>{r.tieLines.push({...structuredClone(r.tieLines[0]),id:'orphan'});},
    r=>{r.condition.components[0].cas='64-17-5';},r=>{r.status='complete';r.incidences.push({id:'x',branchId:null,side:null,kind:'budget',cause:'c',action:'a'});},
  ];
  for(const mutate of mutations){const bad=structuredClone(response);mutate(bad);assert.throws(()=>lib.readTernaryLiquidLiquid(bad,request));checks++;}
  rejectedSpecials.push(...response.specialPoints.map(p=>p.kind));
}
check(rejectedSpecials.includes('plait_point')&&rejectedSpecials.includes('binary_edge')&&rejectedSpecials.includes('three_phase'),'Real publications cover plait point, binary edge and L-L-V triangle');

// Analytic Margules reference (core tracer through the route's publication, wrapped in a real envelope only for
// structural reading): the plait-point mark sits at x0 = x1 = x2 = 1/3, the exact plait point for A = 3.
const base=data.ternary[0],{_status,...analytic}=data.analytic;
const envelope={...structuredClone(base.response),...analytic,status:_status};
const read=drawTernary('analytic Margules A = 3',base.request,envelope,[1,2,3]);
const plait=lib.ternaryPlot(read,[1,2,3]).plaitPoints;
check(plait.length===1&&plait[0].x.every(x=>Math.abs(x-1/3)<1e-6),'Analytic plait point drawn at (1/3, 1/3, 1/3)');
const failing=structuredClone(envelope);const pp=failing.specialPoints.find(p=>p.kind==='plait_point');pp.certificate.residuals[0].value=1;pp.certificate.residuals[0].status='fail';pp.certificate.status='fail';
check(lib.ternaryPlot(lib.readTernaryLiquidLiquid(failing,base.request),[1,2,3]).plaitPoints.length===0,'A failing plait-point candidate is never drawn');
const contradictory=structuredClone(envelope);contradictory.specialPoints.find(p=>p.kind==='plait_point').certificate.residuals[0].value=1;
assert.throws(()=>lib.readTernaryLiquidLiquid(contradictory,base.request));checks++;

// Composition lines.
const linePix=(l,f)=>[46+(560-46-16)*l,14+(240-14-36)*(1-f)];
for(const {label,request,response} of data.lines){
  const read=lib.readCompositionLine(structuredClone(response),request),order=request.components.map(c=>c.id);
  check(read.status==='complete'&&read.rows.every(r=>Object.keys(r.feed).length===order.length),`${label}: complete, every species kept`);
  const plot=lib.linePlot(read,order),html=renderToStaticMarkup(React.createElement(LineChart,{plot}));
  const marks=elements(html,'row-phase');
  check(marks.length===read.rows.reduce((s,r)=>s+r.phases.length,0),`${label}: one mark per published phase of each row`);
  for(const m of marks){const r=read.rows.find(x=>x.id===m.a['data-id']),p=r.phases[+m.a['data-phase-index']];check(near([+m.a.cx,+m.a.cy],linePix(r.l,p.fraction)),`${label}: ${r.id} drawn at (l, fraction)`);}
  const bands=elements(html,'boundary');
  check(bands.length===read.boundaries.length,`${label}: one band per located boundary`);
  bands.forEach((b,k)=>check(Math.abs(+b.a.x+0.75-linePix(read.boundaries[k].lInterval[0],1)[0])<2e-3,`${label}: band starts at the bisection interval`));
  if(order.length===3){
    const tri=renderToStaticMarkup(React.createElement(Chart,{plot:lib.ternaryPlot(lib.readTernaryLiquidLiquid(data.ternary[0].response,data.ternary[0].request),order),names:['1','2','3'],line:plot}));
    const feeds=elements(tri).filter(e=>e.a['data-mark']==='boundary-feed');
    check(feeds.length===2*read.boundaries.length,`${label}: boundary feeds on the ternary`);
    feeds.forEach((e,k)=>{const b=read.boundaries[k>>1],z=(k%2?b.after:b.before).feed;check(near([+e.a.x+3,+e.a.y+3],bary(order.map(id=>z[String(id)]))),`${label}: boundary feed at its published composition`);});
  }
  for(const mutate of [r=>{r.rows.reverse();},r=>{r.rows[0].phases[0].fraction+=1e-6;},r=>{r.rows[0].phaseSet.push('vapor');},r=>{r.rows[0].certified=!r.rows[0].certified;},r=>{r.condition.line.start[String(order[0])]+=0.01;},r=>{r.status='complete';r.failures.push({l:0.5,reason:'x',message:'y'});}]){
    const bad=structuredClone(response);mutate(bad);assert.throws(()=>lib.readCompositionLine(bad,request));checks++;
  }
  report.push({case:label,rows:read.rows.length,boundaries:read.boundaries.length,marks:marks.length});
}

// Rejections are read as such and draw nothing.
for(const {request,response} of data.rejected){
  const read=lib.readTernaryLiquidLiquid(response,request);
  check(read.status==='unsupported'&&read.diagnostics[0].code==='MOTOR_DIAG_COMPONENTES_NO_SOPORTADO'&&lib.ternaryPlot(read,[1,2,3]).tieLines.length===0,'A structured rejection draws nothing');
}

// The view mounts (initial server render: capabilities still loading, no request sent).
const sample={componentes:data.ternary[0].request.components,modelo:data.ternary[0].request.model,T:300,P:101325,inventarios:data.ternary[0].request.components.map(c=>({id:c.id,z:1/3})),huellaParametros:null};
const view=renderToStaticMarkup(React.createElement(load(path.join(motor,'MulticomponentEquilibrium')).default,{muestra:sample}));
check(view.includes('This volume contains 3 components'),'The multicomponent view mounts for a three-component sample');

// No science in the client.
for(const f of ['multicomponentDiagrams.ts','TernaryLiquidLiquidChart.tsx','MulticomponentEquilibrium.tsx']){
  const src=fs.readFileSync(path.join(motor,f),'utf8').replace(/^import.*$/gm,'').replace(/\/\*[\s\S]*?\*\//g,'').replace(/^\s*\/\/.*$/gm,'');
  check(!/Math\.(exp|log|pow)|\*\*|gamma|fugac|antoine|nrtl|unifac|lngamma/i.test(src),`${f}: no thermodynamic computation`);
}
// Both contract copies stay identical.
check(fs.readFileSync(path.join(motor,'contratoDiagramasEquilibrio.ts'),'utf8').replaceAll('\r\n','\n')===fs.readFileSync(path.join(root,'docs/contratos/contratoDiagramasEquilibrio.ts'),'utf8').replaceAll('\r\n','\n').replaceAll('../../frontend/app/motor/','./'),'Canonical diagram contract is current');
console.log(JSON.stringify({checks,report},null,1));
