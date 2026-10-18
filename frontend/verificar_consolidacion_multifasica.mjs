import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const cache=new Map();
function cargar(n){if(n.endsWith('.json'))return JSON.parse(fs.readFileSync(`app/motor/${n}`,'utf8'));if(cache.has(n))return cache.get(n);const m={exports:{}};cache.set(n,m.exports);new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText)(m.exports,m,id=>cargar(id.slice(2)));return m.exports;}
const lector=cargar('lectorEnsamblajeV2'),meta=cargar('metadatosRed'),adapt=cargar('resultadoEnsamblajeV2');
let checks=0;const check=(v,m)=>{checks++;assert.ok(v,m);},rechaza=f=>{checks++;assert.throws(f);};
const leer=n=>JSON.parse(fs.readFileSync(n,'utf8')),dir='../docs/ejemplos/motor-v2/';
check(fs.readFileSync('app/motor/contratoEnsamblajeV2.ts','utf8').replaceAll('\r\n','\n')===fs.readFileSync('../docs/contratos/contratoEnsamblajeV2.ts','utf8').replaceAll('\r\n','\n').replaceAll('../../frontend/app/motor/','./'),'Contract copy is current');
const cap=lector.leerCapacidadesV2(leer(dir+'motor-ensamblaje-v2-capacidades.json'));
check(cap.paquetes.find(p=>p.modelo.id==='nrtl-lle-agua-butanol').combinaciones.some(c=>c.id==='liquido_liquido'&&c.publicada&&c.evidencia==='contrastada'),'LLE evidence is published');
check(cap.paquetes.find(p=>p.modelo.id==='mezcla-ideal').combinaciones.some(c=>c.id==='liquido_liquido'&&!c.publicada&&c.evidencia==='imposible_en_el_modelo'),'Ideal model does not promise LL');
for(const f of fs.readdirSync(dir).filter(f=>f.includes('-resolver-')&&f.endsWith('-peticion.json'))){
  const s=leer(dir+f),raw=leer(dir+f.replace('-peticion','-respuesta')),antes=JSON.stringify(raw),r=lector.leerResolucionV2(raw,s),a=r.resultados;
  check(a.certificacion.estado==='cumple','Nominal certificate');
  check(a.catalogoSeries.length===a.series.length,'Every published series has metadata');
  const h=cargar('hojasPruebaMultifasico').crearHojasPruebaMultifasico().find(h=>JSON.stringify(h.redTermodinamica.solicitud.volumenes)===JSON.stringify(s.volumenes));
  const vista=adapt.adaptarResultadoV2(h,s,r);
  for(const c of a.catalogoSeries){check(vista.seriesEvaluadas.find(x=>x.id===c.variableId).unidad===c.unidadSI,'Plot unit from catalog');check(vista.seriesEvaluadas.find(x=>x.id===c.variableId).grupo.includes(meta.nombrePapelSerie(c.papel)),'Catalog role available without affecting DOF');}
  for(const es of Object.values(a.estados))for(const m of es)check(m.potenciales.unidades.G==='J'&&m.potenciales.unidades.A==='J'&&m.potenciales.unidades.S==='J/K'&&m.potenciales.unidades.mu==='J/mol','Extensive vs chemical potential units');
  for(const e of a.eventos)check(e.faseIdsAntes&&e.faseIdsDespues&&e.descripcion,'Real event phase IDs and description');
  check(meta.intervaloNoCertificado(a)===null,'No invalid-region overlay on passing certificate');
  check(JSON.stringify(raw)===antes,'Metadata reading does not rewrite results');
  for(const cambio of [x=>x.resultados.catalogoSeries.pop(),x=>x.resultados.catalogoSeries[0].unidadSI='kg',x=>x.resultados.catalogoSeries[0].papel='incognita',x=>x.resultados.catalogoSeries[0].variableEnsamblajeId='inventada',x=>x.resultados.certificacion.estado='no_evaluable',x=>x.resultados.certificacion.alcance.muestras++,x=>x.resultados.certificacion.ultimaMuestraCertificada=999,x=>Object.values(x.resultados.estados)[0][0].potenciales.G+=Math.max(10,Math.abs(Object.values(x.resultados.estados)[0][0].potenciales.G)*0.001)]){const x=structuredClone(r);cambio(x);rechaza(()=>lector.leerResolucionV2(x,s));}
  if(a.eventos.length){const x=structuredClone(r);x.resultados.eventos[0].faseIds=['ajena'];rechaza(()=>lector.leerResolucionV2(x,s));}
}
const qa='qa_multifasico_2026_10_15/consolidacion/';
for(const nombre of ['no-cumple','no-evaluable']){
  const s=leer(qa+nombre+'-peticion.json'),r=lector.leerResolucionV2(leer(qa+nombre+'-respuesta.json'),s),a=r.resultados;
  check(r.estado==='resuelto','Numerical completion is independent');check(a.certificacion.estado===nombre.replace('-','_'),'Actual backend certification outcome');
  if(nombre==='no-cumple'){check(meta.intervaloNoCertificado(a)[0]===a.tiempos[a.certificacion.ultimaMuestraCertificada],'Use authoritative cut');check(meta.resumenCertificacion(a).includes('sin certificar'),'Failed certificate is prominent');}
  else {check(meta.intervaloNoCertificado(a)===null,'No-evaluable is not a failure');check(meta.resumenCertificacion(a).includes('no evaluable'),'No-evaluable is never shown as passing');check(!a.series.some(s=>s.variableId==='red.Sgen'),'Missing boundary T does not fabricate entropy generation');}
  const anterior=structuredClone(r);delete anterior.resultados.certificacion;delete anterior.resultados.catalogoSeries;
  check(meta.resumenCertificacion(anterior.resultados).includes('anterior'),'Historical execution has explicit missing certification');
}
// Synthetic metadata-only negative control: preserve failed residuals as evidence,
// while rejecting a certificate that falsely says those same residuals pass.
const s=leer(qa+'no-cumple-peticion.json'),r=leer(qa+'no-cumple-respuesta.json'),x=structuredClone(r),res=x.resultados.residuos.find(q=>q.ecuacionId.startsWith('global.'));
res.maximoEscalado=res.tolerancia*2;rechaza(()=>lector.leerResolucionV2(x,s));
Object.assign(x.resultados.certificacion.aspectos.find(q=>q.id==='conservacion'),{estado:'no_cumple',referencias:[res.ecuacionId],primeraMuestraNoCumple:1});
lector.leerResolucionV2(x,s);check(x.resultados.residuos.includes(res),'Explicit failure remains inspectable');
check(meta.nombreEventoRed('sustitucion_fase')==='Sustitución de fase','Replacement is a distinct event');
check(meta.nombreEventoRed('cambio_denominacion').includes('sin transición'),'Supercritical naming is not evaporation');
const sd=leer(qa+'liquido-superviviente-peticion.json'),rd=lector.leerResolucionV2(leer(qa+'liquido-superviviente-respuesta.json'),sd),ad=rd.resultados;
check(ad.certificacion.estado==='cumple','Depletion trajectory certified by backend');
check(ad.estados.D.at(-1).evaluacion.fases.map(f=>f.id).join()==='liquido-2','Surviving liquid keeps its ID');
const hd=cargar('hojasPruebaMultifasico').crearHojasPruebaMultifasico()[3];hd.redTermodinamica.solicitud=sd;
const fases=adapt.seriesFasesV2(adapt.adaptarResultadoV2(hd,sd,rd));
check(fases.find(x=>x.id==='fase.D.liquido-1.fraccionMasica').valores.at(-1)===0,'Absent liquid fraction is zero');
check(Number.isNaN(fases.find(x=>x.id==='fase.D.liquido-1.x.1').valores.at(-1)),'Absent liquid composition remains missing');
check(fases.find(x=>x.id==='fase.D.liquido-2.fraccionMasica').valores.at(-1)===1,'Remaining liquid is not relabeled');
check(ad.eventos[0].faseIds.join()==='liquido-1'&&ad.eventos[0].faseIdsDespues.join()==='liquido-2','Event identifies the disappearing and remaining liquids');
console.log(`${checks} comprobaciones de consolidación: certificación independiente, catálogo, potenciales totales, eventos, evidencia, respuestas históricas y controles negativos.`);
