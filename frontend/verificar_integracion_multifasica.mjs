import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const cache=new Map();
function cargar(n){if(n.endsWith('.json'))return JSON.parse(fs.readFileSync(`app/motor/${n}`,'utf8'));if(cache.has(n))return cache.get(n);const m={exports:{}};cache.set(n,m.exports);new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText)(m.exports,m,id=>cargar(id.slice(2)));return m.exports;}
const lector=cargar('lectorEnsamblajeV2'),adapt=cargar('resultadoEnsamblajeV2'),red=cargar('redTermodinamica'),graficas=cargar('datosGraficasMotor'),modelo=cargar('modeloHojaMotor');
let checks=0;const check=(v,m)=>{checks++;assert.ok(v,m);},rechaza=f=>{checks++;assert.throws(f);};
const dir='../docs/ejemplos/motor-v2/',leer=n=>JSON.parse(fs.readFileSync(dir+n,'utf8'));
const hojas=cargar('hojasPruebaMultifasico').crearHojasPruebaMultifasico();
let estados=0;
for(const file of fs.readdirSync(dir).filter(n=>n.startsWith('motor-ensamblaje-v2-')&&n.endsWith('-peticion.json'))){
  const s=leer(file),r=leer(file.replace('-peticion','-respuesta'));
  if(!file.includes('-resolver-')){lector.leerValidacionV2(r,s);checks++;continue;}
  lector.leerResolucionV2(r,s);checks++;
  const h=hojas.find(h=>h.redTermodinamica.solicitud.solicitudId==='configuracion'&&JSON.stringify(h.redTermodinamica.solicitud.volumenes)===JSON.stringify(s.volumenes));
  check(!!h,'Example worksheet uses the original input structure');
  const resultado=adapt.adaptarResultadoV2(h,s,r);adapt.validarResultadoV2(resultado);checks++;
  const antes=JSON.stringify(r),d=graficas.datosGraficasMotor(h,resultado,'tiempo');
  for(const [vid,es] of Object.entries(r.resultados.estados)){
    estados+=es.length;
    es.forEach((e,k)=>{for(const f of e.evaluacion.fases){for(const base of ['fraccionMasica','fraccionMolar','fraccionVolumen'])check(d.filas[k][`fase.${vid}.${f.id}.${base}`]===f[base],'Phase bases are preserved by phase ID');for(const [cid,x]of Object.entries(f.composicionMolar))check(d.filas[k][`fase.${vid}.${f.id}.x.${cid}`]===x,'Phase compositions retained');}});
  }
  check(JSON.stringify(graficas.limitesGraficaMotor(d.filas,d.variables.filter(v=>v.id.startsWith('fase.')&&v.id.endsWith('.fraccionMasica')).map(v=>v.id)))==='[0,1]','Phase fractions retain their physical axis bounds');
  check(JSON.stringify(r)===antes,'Presentation never mutates certificates');
  check(adapt.graficasInicialesV2(resultado).every(g=>g.y.every(id=>d.variables.some(v=>v.id===id))),'Default plots use available variables');
  const bad=structuredClone(r);bad.resultados.series[0].valores[0]+=1;rechaza(()=>lector.leerResolucionV2(bad,s));
  const wrong=structuredClone(r);Object.values(wrong.resultados.estados)[0][0].evaluacion.P*=2;rechaza(()=>lector.leerResolucionV2(wrong,s));
  const doble=structuredClone(r);doble.resultados.series.push(doble.resultados.series[0]);rechaza(()=>lector.leerResolucionV2(doble,s));
  const ids=structuredClone(r);Object.values(ids.resultados.estados)[0][0].potenciales.fases[0].faseId='fantasma';rechaza(()=>lector.leerResolucionV2(ids,s));
  const guardado=structuredClone(resultado);guardado.seriesEvaluadas[0].valores[0]+=1;rechaza(()=>adapt.validarResultadoV2(guardado));
  const firma=modelo.firmaHoja(h),conNombre={...h,nombre:'Otro nombre'};check(modelo.firmaHoja(conNombre)===firma,'Renaming is not a physical change');
  const conResultado={...h,resultadoRef:{firma,estado:'resuelto',fecha:'2026-10-15'}};
  const renombrada=red.cambiarRed(conResultado,r=>{r.nombres['volumen:A']='Depósito';});check(renombrada.resultadoRef===conResultado.resultadoRef&&modelo.firmaHoja(renombrada)===firma,'Display names preserve the result');
  const cambiada=red.cambiarRed(h,r=>{r.solicitud.datos[r.solicitud.estudio.tiempoId].declaracion.texto='123';});check(modelo.firmaHoja(cambiada)!==firma&&!cambiada.resultadoRef,'Changing data invalidates the result');
  console.log(`${file}: ${r.resultados.tiempos.length} muestras, ${d.variables.length} variables graficables`);
}
const editada=JSON.parse(fs.readFileSync('qa_multifasico_2026_10_15/binario-editado-peticion.json','utf8')),respuestaEditada=JSON.parse(fs.readFileSync('qa_multifasico_2026_10_15/binario-editado-respuesta.json','utf8'));
lector.leerResolucionV2(respuestaEditada,editada);checks++;
check(respuestaEditada.resultados.estados.A[2].evaluacion.fases[0].fraccionMasica===1.0000000000000002,'Real roundoff is preserved, not clamped');
const fuera=structuredClone(respuestaEditada);fuera.resultados.estados.A[2].evaluacion.fases[0].fraccionMasica=1+1e-8;rechaza(()=>lector.leerResolucionV2(fuera,editada));
const vieja=cargar('hojasPruebaEnergia').crearHojasPruebaEnergia()[0],original=JSON.stringify(vieja),copia=red.copiarARed(vieja);
check(JSON.stringify(vieja)===original&&copia.id!==vieja.id,'Opt-in migration creates a copy, preserving original worksheet');
check(copia.redTermodinamica.solicitud.volumenes[0].formulacionEnergia.modelo==='u_lineal','An existing manual closure remains an explicit backend conflict; never silently discarded');
console.log(`${checks} comprobaciones de integración multifásica; ${estados} estados reales. IDs de fases, tres bases, composición, persistencia, errores y copia explícita.`);

// Evidence exported from the visible technical-details panel, after real UI solves.
// These budgets do not call the backend solver or its equation-of-state helpers.
if(process.argv.includes('--ui')){
  let muestras=0;
  for(const nombre of ['calentamiento','contacto','binario','decantador']){
    const e=JSON.parse(fs.readFileSync(`qa_multifasico_2026_10_15/${nombre}-ui.json`,'utf8'));
    const s=e.solicitud,r=lector.leerResolucionV2(e.respuesta,s),a=r.resultados;
    check(r.estado==='resuelto',`${nombre}: completed through UI`);muestras+=a.tiempos.length;
    const valor=(id,k)=>{const q=a.series.find(q=>q.variableId===id);assert.ok(q,id);return q.valores[k];};
    const cerca=(x,y)=>Math.abs(x-y)<=1e-6*Math.max(1,Math.abs(x),Math.abs(y));
    const sinFlujoExterior=s.corrientes.every(c=>c.desde!==null&&c.hasta!==null);
    if(sinFlujoExterior)for(const c of s.componentes){const suma=k=>s.volumenes.filter(v=>v.componenteIds.includes(c.id)).reduce((n,v)=>n+valor(`volumen.${v.id}.n.${c.id}`,k),0);a.tiempos.forEach((_,k)=>check(cerca(suma(k),suma(0)),`${nombre}: global species budget`));}
    const rigida=s.volumenes.every(v=>v.frontera.tipo==='rigida');
    const isobarica=s.volumenes.every(v=>v.frontera.tipo==='presion_prescrita'&&Number.isFinite(Number(s.datos[v.frontera.presionId].declaracion.texto)));
    const calorExterior=s.intercambiosTermicos.filter(q=>q.desde===null||q.hasta===null);
    if(sinFlujoExterior&&(rigida||isobarica)&&calorExterior.every(q=>q.ley.tipo==='impuesto'&&s.datos[q.ley.potenciaId].declaracion.unidad==='W'&&Number.isFinite(Number(s.datos[q.ley.potenciaId].declaracion.texto)))){
      const potencia=calorExterior.reduce((x,q)=>x+(q.desde===null?1:-1)*Number(s.datos[q.ley.potenciaId].declaracion.texto),0);
      const energia=k=>s.volumenes.reduce((x,v)=>x+valor(`volumen.${v.id}.${rigida?'U':'H'}`,k),0);
      a.tiempos.forEach((t,k)=>check(cerca(energia(k),energia(0)+potencia*t),`${nombre}: independent first-law budget`));
    }
    for(const es of Object.values(a.estados))for(const m of es){const f=m.evaluacion.fases;for(const base of ['fraccionMasica','fraccionMolar','fraccionVolumen'])check(cerca(f.reduce((x,q)=>x+q[base],0),1),`${nombre}: phase fractions sum to one`);}
    check(a.segundaLey.estado==='cumple',`${nombre}: published second-law check`);
    console.log(`UI ${nombre}: ${a.tiempos.length} muestras, presupuestos y certificados comprobados.`);
  }
  console.log(`Total: ${checks} comprobaciones, incluidas ${muestras} muestras resueltas desde la interfaz.`);
}
