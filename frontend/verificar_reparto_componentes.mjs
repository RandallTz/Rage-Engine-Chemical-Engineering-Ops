import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const cache=new Map();
function cargar(n){if(n.endsWith('.json'))return JSON.parse(fs.readFileSync(`app/motor/${n}`,'utf8'));if(cache.has(n))return cache.get(n);const m={exports:{}};cache.set(n,m.exports);new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText)(m.exports,m,id=>cargar(id.slice(2)));return m.exports;}
const {repartoComponente,seriesFasesV2,adaptarResultadoV2,graficasComponentesV2}=cargar('resultadoEnsamblajeV2'),{limitesGraficaMotor}=cargar('datosGraficasMotor');
let checks=0;const check=(v,m)=>{checks++;assert.ok(v,m);},cerca=(a,b)=>check(Math.abs(a-b)<1e-10,`${a} ≈ ${b}`);
// Independent hand calculation: 100 mol, 50 of each component. Vapor has
// 25 mol: 20 A + 5 B; liquid has 75 mol: 30 A + 45 B.
const e={composicionMolar:{1:.5,2:.5,3:0},fases:[{id:'vapor',tipo:'vapor',fraccionMolar:.25,composicionMolar:{1:.8,2:.2,3:0}},{id:'liquido-2',tipo:'liquido',fraccionMolar:.75,composicionMolar:{1:.4,2:.6,3:0}}]};
cerca(repartoComponente(e,'vapor',1),.4);cerca(repartoComponente(e,'vapor',2),.1);
cerca(repartoComponente(e,'liquido-2',1),.6);cerca(repartoComponente(e,'liquido-2',2),.9);
check(repartoComponente(e,'vapor',1)!==e.fases[0].composicionMolar[1],'Partition is not composition within the phase');
cerca(repartoComponente(e,'liquido-1',1),0);
check(Number.isNaN(repartoComponente(e,'vapor',3))&&Number.isNaN(repartoComponente(e,'ausente',3)),'Absent component has undefined partition, including absent phases');
const traza={composicionMolar:{1:1e-15},fases:[{id:'vapor',fraccionMolar:.1,composicionMolar:{1:2e-15}},{id:'liquido',fraccionMolar:.9,composicionMolar:{1:8e-15/9}}]};
cerca(repartoComponente(traza,'vapor',1),.2);cerca(repartoComponente(traza,'liquido',1),.8);
// Three phases; preserve two distinct liquid IDs rather than assigning all
// liquid to the first one or confusing volume fraction with mole fraction.
const tres={composicionMolar:{1:.5,2:.5},fases:[{id:'L1',fraccionMolar:.2,composicionMolar:{1:.8,2:.2}},{id:'L2',fraccionMolar:.3,composicionMolar:{1:.3,2:.7}},{id:'V',fraccionMolar:.5,composicionMolar:{1:.5,2:.5}}]};
for(const cid of [1,2])cerca(tres.fases.reduce((s,f)=>s+repartoComponente(tres,f.id,cid),0),1);
cerca(repartoComponente(tres,'L1',1),.32);cerca(repartoComponente(tres,'L2',1),.18);
const dir='../docs/ejemplos/motor-v2/',leer=n=>JSON.parse(fs.readFileSync(n,'utf8'));
for(const file of fs.readdirSync(dir).filter(f=>f.includes('-resolver-')&&f.endsWith('-peticion.json'))){
  const s=leer(dir+file),raw=leer(dir+file.replace('-peticion','-respuesta')),antes=JSON.stringify(raw);
  const h=cargar('hojasPruebaMultifasico').crearHojasPruebaMultifasico().find(h=>JSON.stringify(h.redTermodinamica.solicitud.volumenes)===JSON.stringify(s.volumenes)),r=adaptarResultadoV2(h,s,raw),series=seriesFasesV2(r);
  for(const v of s.volumenes)for(const [k,estado]of raw.resultados.estados[v.id].entries())for(const cid of v.componenteIds){
    const q=series.filter(q=>q.id.startsWith(`fase.${v.id}.`)&&q.id.endsWith(`.reparto.${cid}`)),z=estado.evaluacion.composicionMolar[cid];
    if(z>0){cerca(q.reduce((a,q)=>a+q.valores[k],0),1);for(const f of estado.evaluacion.fases){const theta=q.find(q=>q.id===`fase.${v.id}.${f.id}.reparto.${cid}`).valores[k];cerca(theta*z,f.fraccionMolar*f.composicionMolar[cid]);}}
    else check(q.every(q=>Number.isNaN(q.valores[k])),'No manufactured partition for absent components');
  }
  const gs=graficasComponentesV2(r);check(gs.length===s.volumenes.reduce((n,v)=>n+v.componenteIds.length,0),'One comparison plot per component and volume');
  check(new Set(gs.map(g=>g.id)).size===gs.length,'Stable distinct graph IDs');
  for(const g of gs){check(g.y.length>0&&g.y.every(id=>series.some(s=>s.id===id)),'Graphs reference available derived series');check(JSON.stringify(limitesGraficaMotor([],g.y))==='[0,1]','Partition fractions keep a physical scale');}
  check(JSON.stringify(raw)===antes,'Derivation never rewrites certified states');
  // Switching a compatible model changes physics identity and clears stale
  // results while preserving every input number and the original worksheet.
  const original=structuredClone(h);original.resultado=r;original.resultadoRef='anterior';const snapshot=JSON.stringify(original);
  const switched=cargar('redTermodinamica').cambiarRed(original,red=>{red.solicitud.paquetes[0].modelo={id:'mezcla-ideal',version:'1'};});
  if(h.redTermodinamica.solicitud.paquetes[0].modelo.id!=='mezcla-ideal')check(!switched.resultado&&!switched.resultadoRef,'Package change invalidates prior result');
  check(JSON.stringify(switched.redTermodinamica.solicitud.datos)===JSON.stringify(original.redTermodinamica.solicitud.datos),'Switch keeps input data');
  check(JSON.stringify(original)===snapshot,'Switch does not mutate original worksheet');
}
const qa='qa_multifasico_2026_10_15/reparto/';
const solicitudes=['nrtl-chemsep','mezcla-ideal'].map(m=>leer(qa+m+'-peticion.json'));
const respuestas=['nrtl-chemsep','mezcla-ideal'].map(m=>leer(qa+m+'-respuesta.json'));
check(JSON.stringify(solicitudes[0].datos)===JSON.stringify(solicitudes[1].datos),'Actual HTTP package switch uses identical numeric inputs');
check(respuestas[0].validacion.modeloId!==respuestas[1].validacion.modeloId,'Actual backend model identities distinguish packages');
for(let i=0;i<2;i++){
  const r=cargar('lectorEnsamblajeV2').leerResolucionV2(respuestas[i],solicitudes[i]);
  check(r.estado==='resuelto'&&r.resultados.certificacion.estado==='cumple','Both actual HTTP trajectories pass the reader and backend certification');
}
console.log(`${checks} comprobaciones: reparto por componente, referencias analíticas, trazas, ausencia, múltiples líquidos, trayectorias reales y cambio de paquete.`);
