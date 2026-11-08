// F8b lane A: EOS diagrams (peng-robinson-vdw1f, psrk-unifac). Real service publications go through the strict reader
// and a server render of the real SVG chart. Published numbers are compared with the package operation called
// directly (Python side) and every drawn mark with the published point placed by this script's own scale; no
// browser, no screenshot. Run: node frontend/verify_eos_diagrams.mjs (about 40 s; starts no server).
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
const output=path.join(root,'.tmp/f8b-eos-publication.json');
const python=spawnSync('python',['-c',`
import json,sys
sys.path.insert(0,'.')
import numpy as np
from pathlib import Path
from backend.eos_diagrams import compute
from core.termodinamica import psrk, cubic_flash as cf, cubic_critical as cc
from core.termodinamica.cubic_eos import PengRobinsonMixture
MEOH,TOL,BZ,CO2,ETOH='67-56-1','108-88-3','71-43-2','124-38-9','64-17-5'
def comps(*c): return [{'id':k+1,'identidadQuimica':{'cas':x}} for k,x in enumerate(c)]
def req(op,pid,cas,**kw): return {'revision':1,'requestId':'v','operation':op,'package':{'id':pid,'version':'1'},'components':comps(*cas),**kw}
K=lambda v:{'valor':v,'unidad':'K'}
cases=[]
def add(label,body,direct=None):
    cases.append({'label':label,'request':body,'response':compute(body),'direct':direct})
b=req('isotherm','psrk-unifac',(MEOH,TOL),condition={'T':K(480.0)},fractionRange=[0.2,0.8],points=4)
e=psrk.PSRKMixture((MEOH,TOL)); xs=np.linspace(0.2,0.8,4)
add('PSRK methanol + toluene isotherm 480 K',b,[psrk.bubble_pressure(e,480.0,np.array([x,1-x]))['P'] for x in xs])
b=req('saturation_curve','psrk-unifac',(MEOH,TOL),composition={'1':0.4,'2':0.6},kind='dew',temperatureRange={'from':K(400.0),'to':K(480.0)},points=4)
add('PSRK dew curve',b)
b=req('saturation_curve','peng-robinson-vdw1f',(BZ,TOL),composition={'1':0.5,'2':0.5},kind='bubble',temperatureRange={'from':K(333.15),'to':K(373.15)},points=4)
e=PengRobinsonMixture((BZ,TOL))
add('PR benzene + toluene bubble curve',b,[cf.saturation(e,[0.5,0.5],T=T,kind='bubble')['P'] for T in np.linspace(333.15,373.15,4)])
b=req('critical_locus','peng-robinson-vdw1f',(BZ,TOL),fractionRange=[0.25,0.75],points=3)
add('PR benzene + toluene critical locus',b,[max(cc.critical_points(e,[x,1-x]),key=lambda r:r['T'])['P'] for x in np.linspace(0.25,0.75,3)])
b=req('critical_locus','psrk-unifac',(CO2,ETOH),fractionRange=[0.8315,0.931],points=2)
add('PSRK CO2 + ethanol locus with a located rejection',b)
b=req('isotherm','peng-robinson-vdw1f',(CO2,ETOH),condition={'T':K(333.15)},points=3)
add('PR without a CO2 record',b)
Path(sys.argv[1]).write_text(json.dumps(cases,allow_nan=False),encoding='utf8')
`,output],{cwd:root,encoding:'utf8',maxBuffer:64<<20});
assert.equal(python.status,0,python.stderr);
const cases=JSON.parse(fs.readFileSync(output,'utf8'));
const motor=path.join(directory,'app/motor');
const lib=load(path.join(motor,'eosDiagrams')),view=load(path.join(motor,'EosDiagramView'));
const G=view.EOS_CHART;
let checks=0;const check=(v,m)=>{assert.ok(v,m);checks++;};
const throwsReader=(raw,req,m)=>{assert.throws(()=>lib.readEosResponse(raw,req),/Incompatible EOS diagram/,m);checks++;};
const names={'1':'A','2':'B'};

for(const c of cases){
  const read=lib.readEosResponse(structuredClone(c.response),c.request);
  check(JSON.stringify(read)===JSON.stringify(c.response),`${c.label}: the reader does not alter the publication`);
  if(c.direct)read.points.forEach((p,k)=>check(Math.abs(p.P/c.direct[k]-1)<1e-9,`${c.label}: point ${k} equals the package operation (${p.P} vs ${c.direct[k]})`));
  if(!read.points.length){
    check(['unsupported','no_points'].includes(read.status)&&read.diagnostics.length>0,`${c.label}: a rejection carries its diagnostic`);continue;
  }
  const plot=lib.eosPlot(read,c.request,names);
  const html=renderToStaticMarkup(React.createElement(view.EosChart,{plot}));
  const all=plot.series.flatMap(s=>s.points),xs=all.map(p=>p[0]),ys=all.map(p=>p[1]);
  const pad=(a,b)=>a===b?[a-1,b+1]:[a-(b-a)*0.04,b+(b-a)*0.04];
  const [x0,x1]=pad(Math.min(...xs),Math.max(...xs)),[y0,y1]=pad(Math.min(...ys),Math.max(...ys));
  const X=v=>G.M.l+(v-x0)/(x1-x0)*(G.W-G.M.l-G.M.r),Y=v=>G.H-G.M.b-(v-y0)/(y1-y0)*(G.H-G.M.t-G.M.b);
  const groups=[...html.matchAll(/<g data-series="([^"]+)">(.*?)<\/g>/g)];
  check(groups.length===plot.series.length,`${c.label}: one group per series`);
  groups.forEach((g,k)=>{
    const s=plot.series[k];check(g[1]===s.id,`${c.label}: series ${s.id}`);
    const circles=[...g[2].matchAll(/<circle cx="([^"]+)" cy="([^"]+)"/g)].map(m=>[+m[1],+m[2]]);
    check(circles.length===s.points.length,`${c.label}/${s.id}: one mark per published point`);
    circles.forEach((m,j)=>check(Math.hypot(m[0]-X(s.points[j][0]),m[1]-Y(s.points[j][1]))<1e-6,`${c.label}/${s.id}: mark ${j} at its published point`));
  });
  if(c.request.operation==='isotherm')check(plot.series[0].points.every((p,j)=>plot.series[1].points[j][1]===p[1]&&plot.series[1].points[j][0]>=0),`${c.label}: bubble and dew share each pressure`);
}
const partial=cases.find(c=>c.label.includes('located rejection'));
check(partial.response.status==='partial'&&partial.response.rejected.some(r=>r.cause==='no_critical_point_in_window'),'partial locus lists its located rejection');
const norejected=cases.find(c=>c.label==='PR without a CO2 record');
check(norejected.response.status==='unsupported'&&norejected.response.diagnostics[0].code==='EOS_DIAG_NO_DATA','missing catalog record is unsupported');

// Tampering must fail the reader.
const base=cases[0],tamper=f=>{const r=structuredClone(base.response);f(r);return r;};
throwsReader(tamper(r=>{r.requestId='other';}),base.request,'another request id');
throwsReader(tamper(r=>{r.identity.package.id='psrk-unifac-x';}),base.request,'another package');
throwsReader(tamper(r=>{r.points[0].certificate.status='fail';}),base.request,'failed certificate published');
throwsReader(tamper(r=>{r.points[0].certificate.fugacity=1;}),base.request,'pass contradicted by residual');
throwsReader(tamper(r=>{r.points[0].vapor['1']+=0.01;}),base.request,'unnormalized composition');
throwsReader(tamper(r=>{r.points.reverse();}),base.request,'compositions not increasing');
throwsReader(tamper(r=>{r.status='partial';}),base.request,'status contradicts points');
throwsReader(tamper(r=>{r.identity.components[0].cas='1-1-1';}),base.request,'another component');
const sat=cases[1];throwsReader((()=>{const r=structuredClone(sat.response);r.points.reverse();return r;})(),sat.request,'temperatures not increasing');
console.log(`verify_eos_diagrams: ${checks} checks passed`);
