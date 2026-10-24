// Actual F8 publications: reader, branch projection, special markers and export.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import ts from 'typescript';
const directory=path.dirname(fileURLToPath(import.meta.url)),root=path.dirname(directory),require=createRequire(import.meta.url),cache=new Map();
function load(file){if(!path.extname(file))file+='.ts';if(file.endsWith('.json'))return JSON.parse(fs.readFileSync(file,'utf8'));if(cache.has(file))return cache.get(file).exports;const loadedModule={exports:{}};cache.set(file,loadedModule);new Function('exports','module','require',ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText)(loadedModule.exports,loadedModule,id=>id.startsWith('.')?load(path.resolve(path.dirname(file),id)):require(id));return loadedModule.exports;}
const python=spawnSync('python',['-c',`
import json,sys
sys.path.insert(0,'tests')
from pathlib import Path
from test_diagram_liquid_liquid import Service,margules_system,W,B,LLE,P
from backend import motor_diagramas as service
from core import mezclas as mz
body=Service().body([W,B],{'id':LLE,'version':mz.PAQUETES[LLE].version},axis=1)
cases=[]
for kind in ['Txy','Pxy']:
 s=dict(body)
 if kind=='Pxy':s['corte']={'tipo':'Pxy','T':{'valor':360,'unidad':'K'}}
 cases.append({'request':s,'response':service.trazar(s)})
critical=service._liquido_liquido(margules_system(660.0),'mezcla-ideal','Txy',P,[1,2],0,'exploratoria')
Path('.tmp/f8-d4-publication.json').write_text(json.dumps({'cases':cases,'analyticCritical':critical}),encoding='utf8')
`],{cwd:root,encoding:'utf8',maxBuffer:32<<20});
assert.equal(python.status,0,python.stderr);
const {cases,analyticCritical}=JSON.parse(fs.readFileSync(path.join(root,'.tmp/f8-d4-publication.json'),'utf8'));
const {leerDiagramaEquilibrio}=load(path.join(directory,'app/motor/lectorDiagramasEquilibrio'));
const {liquidLiquidPlot,csvDiagrama}=load(path.join(directory,'app/motor/datosDiagramaEquilibrio'));
let checks=0;const check=(value,message)=>{assert.ok(value,message);checks++;};
for(const {request,response} of cases){
  const before=JSON.stringify(response),read=leerDiagramaEquilibrio(response,request);
  check(JSON.stringify(read)===before,'The optional block stays unchanged');
  const plot=liquidLiquidPlot(read,1,'K','Pa'),other=liquidLiquidPlot(read,2,'degC','bar');
  check(plot.branches.length===read.liquidoLiquido.ramas.length*2,'Each branch has two separate phase series');
  plot.branches.forEach((branch,index)=>branch.points.forEach((point,k)=>{
    const original=read.liquidoLiquido.puntos.find(row=>row.id===point.puntoId),mirrored=other.branches[index].points[k];
    check(point.x===original.fases.find(row=>row.id===branch.phase).composicionMolar[1],'Composition is taken from the published phase');
    check(Math.abs(point.x+mirrored.x-1)<1e-10,'Other-component projection preserves pair identity and order');
    check(point.valor===(request.corte.tipo==='Txy'?original.T:original.P),'Values come from the published point');
    check(Math.abs(mirrored.valor-(request.corte.tipo==='Txy'?point.valor-273.15:point.valor/1e5))<1e-10,'Only display units change');
  }));
  check(plot.triple.length===3,'The three-phase point retains both liquids and vapor');
  check(csvDiagrama(read,true).includes('"LL"')&&csvDiagrama(read,true).includes('"tres_fases"'),'CSV retains phase identities and special points');
  const legacy=structuredClone(response);delete legacy.liquidoLiquido;
  assert.doesNotThrow(()=>leerDiagramaEquilibrio(legacy,request));
  check(liquidLiquidPlot(legacy,1,'K','Pa').branches.length===0,'Absent optional block preserves old responses');
  for(const mutate of [r=>r.liquidoLiquido.ramas[0].puntoIds[0]='missing',r=>r.liquidoLiquido.puntos[0].certificado.estado='no_cumple',r=>r.liquidoLiquido.puntos[0].fases[0].composicionMolar[1]=2,r=>r.liquidoLiquido.puntos[0].xEje[0]=.9,r=>r.liquidoLiquido.puntosEspeciales.find(row=>row.tipo==='tres_fases').composiciones.vapor[1]=NaN]){
    const bad=structuredClone(response);mutate(bad);assert.throws(()=>leerDiagramaEquilibrio(bad,request));checks++;
  }
}
// This marker comes from the independent analytic Margules reference tracer,
// not a hand-written frontend equilibrium or a product model.
const criticalView={...cases[0].response,liquidoLiquido:analyticCritical};
// Reuse an envelope only to exercise structural reading. This is not a claim
// that its NRTL package has the analytic test liquid's critical coordinates.
assert.doesNotThrow(()=>leerDiagramaEquilibrio(criticalView,cases[0].request));checks++;
const critical=liquidLiquidPlot(criticalView,1,'K','Pa').critical;
check(critical.length===1&&Math.abs(critical[0].valor-330)<1e-6&&Math.abs(critical[0].x-.5)<1e-6,'Certified critical marker matches analytic T=a/2, x=1/2');
const invalidCritical=structuredClone(criticalView);invalidCritical.liquidoLiquido.puntosEspeciales.find(row=>row.tipo==='critico_ll').certificado.estado='no_cumple';
check(liquidLiquidPlot(invalidCritical,1,'K','Pa').critical.length===0,'Uncertified critical candidates are never drawn as certified equilibrium');
const badCritical=structuredClone(criticalView);badCritical.liquidoLiquido.puntosEspeciales.find(row=>row.tipo==='critico_ll').certificado.residuos[0].valor=1;
assert.throws(()=>leerDiagramaEquilibrio(badCritical,cases[0].request));checks++;
// Existing internal fixture, numerical horizon only; never installed as a product template.
const {crearHojasPruebaMultifasico}=load(path.join(directory,'app/motor/hojasPruebaMultifasico'));
const browserModel=crearHojasPruebaMultifasico()[3];
browserModel.nombre='F8 isolated liquid-liquid view';
const request=browserModel.redTermodinamica.solicitud;
request.estudio.muestras=2;request.datos[request.estudio.tiempoId].declaracion.texto='1';
fs.writeFileSync(path.join(root,'.tmp/f8-d4.model.json'),JSON.stringify({format:'rage.model-file',version:1,model:browserModel},null,2));
console.log(JSON.stringify({checks,cuts:2,criticalReference:'analytic Margules',legacy:'passed',phaseProjection:'passed',csv:'passed'}));
