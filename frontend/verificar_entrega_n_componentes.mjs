import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const cache=new Map();
function cargar(n){if(n.endsWith('.json'))return JSON.parse(fs.readFileSync(`app/motor/${n}`,'utf8'));if(cache.has(n))return cache.get(n);const m={exports:{}};cache.set(n,m.exports);new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText)(m.exports,m,id=>cargar(id.slice(2)));return m.exports;}
let checks=0;const check=(x,m)=>{checks++;assert.ok(x,m);},igual=(a,b,m)=>{checks++;assert.deepEqual(a,b,m);};
const leer=p=>JSON.parse(fs.readFileSync(p,'utf8')),dir='../docs/ejemplos/motor-n-componentes/';
const lector=cargar('lectorEnsamblajeV2'),adapt=cargar('resultadoEnsamblajeV2'),ctx=cargar('contextoMuestraEquilibrio'),graficas=cargar('datosGraficasMotor'),estado=cargar('estadoResolucionRed').estadoResolucionRed;
const hojas=cargar('hojasPruebaNComponentes').crearHojasPruebaNComponentes();
const cap=lector.leerCapacidadesV2(leer(dir+'motor-ensamblaje-v2-capacidades.json'));
check(cap.componentesMaximos===7&&cap.tamanos.componentesMaximosPorVolumen===7,'Admitted local dimension is published by the service');
igual(cap.tamanos.contrastados['nrtl-chemsep'].dinamico,[2,4],'NRTL evidence does not become seven just because the protocol accepts seven');
check(cap.tamanos.fasesMaximas===3&&cap.volumenesMaximos===3,'Components are not phases or volumes');
const historica=structuredClone(cap);delete historica.tamanos;lector.leerCapacidadesV2(historica);checks++;
for(const cambio of [x=>x.tamanos.componentesMaximosPorVolumen=8,x=>x.tamanos.fasesMaximas=0,x=>x.tamanos.contrastados.a={estatico:[8],dinamico:[]},x=>x.tamanos.estabilidad.a='']){
  const x=structuredClone(cap);cambio(x);checks++;assert.throws(()=>lector.leerCapacidadesV2(x));
}
check(hojas.length===5&&new Set(hojas.map(h=>h.id)).size===5,'Stable distinct example IDs');
check(hojas.every(h=>!h.resultado&&!h.resultadoRef),'Example sheets never include cached solutions');
const copia=cargar('hojasPruebaNComponentes').crearHojasPruebaNComponentes();
hojas[0].redTermodinamica.nombres.prueba='local';check(!copia[0].redTermodinamica.nombres.prueba,'Examples do not share mutable state');
check(hojas.find(h=>h.id.endsWith('ideal-7')).redTermodinamica.solicitud.volumenes[0].componenteIds.length===7,'Seven-component worksheet retains every species');

let estados=0;
function comprobarTrayectoria(s,r,h){
  lector.leerResolucionV2(r,s);checks++;
  check(r.estado==='resuelto'&&r.resultados.certificacion.estado==='cumple','Original response is resolved and certified');
  check(estado(r.validacion).puedeResolver,'Compatible physical initialization enables Resolver');
  const antes=JSON.stringify(r),resultado=adapt.adaptarResultadoV2(h,s,r),d=graficas.datosGraficasMotor(h,resultado,'tiempo');
  adapt.validarResultadoV2(resultado);checks++;
  for(const v of s.volumenes)for(let k=0;k<r.resultados.tiempos.length;k++){
    const e=r.resultados.estados[v.id][k].evaluacion,c=ctx.contextoMuestraEquilibrio(resultado,v.id,k);estados++;
    igual(c.componentes.map(x=>x.id),v.componenteIds,'Every declared local ID appears in the result context');
    check(ctx.referenciasCortesBinarios(c,v.componenteIds[0]).estado==='no_binario','Diagram restriction does not truncate multicomponent dynamics');
    for(const cid of v.componenteIds){
      check(d.variables.some(x=>x.id===`volumen.${v.id}.n.${cid}`),'Every component inventory is selectable');
      for(const f of e.fases){
        check(d.filas[k][`fase.${v.id}.${f.id}.x.${cid}`]===f.composicionMolar[cid],'Each phase composition is preserved');
        const reparto=d.filas[k][`fase.${v.id}.${f.id}.reparto.${cid}`];
        check(e.composicionMolar[cid]>0?Math.abs(reparto-adapt.repartoComponente(e,f.id,cid))<1e-12:Number.isNaN(reparto),'Absent species have no invented phase partition');
      }
      const i=c.inventarios.find(x=>x.id===cid);
      check(!!i&&Math.abs(i.nReconstruido-i.n)<=1e-8*Math.max(1e-12,i.n),'Inventories are reconstructed per component');
    }
    for(const f of e.fases)check(Math.abs(Object.values(f.composicionMolar).reduce((a,b)=>a+b,0)-1)<1e-9,'Phase compositions remain normalized');
  }
  check(adapt.graficasComponentesV2(resultado).length===s.volumenes.reduce((n,v)=>n+v.componenteIds.length,0),'Optional partition charts exist for all local components');
  check(JSON.stringify(r)===antes,'Presentation leaves original evidence intact');
}
for(const f of fs.readdirSync(dir).filter(f=>f.endsWith('-peticion.json'))){
  const s=leer(dir+f),r=leer(dir+f.replace('-peticion','-respuesta'));
  if(f.startsWith('motor-termodinamica-')){cargar('contratoTermodinamica').validarRespuestaEstado(r,s);checks++;continue;}
  if(f.includes('-validar-')){
    lector.leerValidacionV2(r,s);checks++;
    check(r.recuento.gradosLibertad===0&&r.recuento.estado==='listo','Canonical structural count is retained even for a missing parameter');
    check(!estado(r).puedeResolver&&estado(r).estado==='Faltan datos del paquete','A missing parameter blocks Resolver despite GL=0');
    check(estado(r).diagnostico.codigo==='MOTOR_ENS_PARAMETRO_AUSENTE','Original missing-parameter diagnostic is retained');
    const sinDiagnostico=structuredClone(r);sinDiagnostico.diagnosticos=[];
    checks++;assert.throws(()=>lector.leerValidacionV2(sinDiagnostico,s),'An uncertified ready model needs its physical rejection diagnostic');
    const invalida=structuredClone(r);invalida.diagnosticos[0].estado='inventado';
    checks++;assert.throws(()=>lector.leerValidacionV2(invalida,s),'Unknown diagnostic state is rejected');
    continue;
  }
  const h=hojas.find(h=>JSON.stringify(h.redTermodinamica.solicitud.volumenes)===JSON.stringify(s.volumenes));
  check(!!h,'Worksheet uses the delivered original request');comprobarTrayectoria(s,r,h);
}
check(!estado().puedeResolver,'Pending validation never enables resolution');
const valida=leer(dir+'motor-ensamblaje-v2-resolver-calentamiento-ideal-5-respuesta.json').validacion;
for(const inicial of ['pendiente','incompatible','no_soportada']){const r=structuredClone(valida);r.inicializacion.estado=inicial;check(!estado(r).puedeResolver,'Uncertified initialization is not ready');}
{
  const f='motor-ensamblaje-v2-resolver-calentamiento-ideal-5',s=leer(dir+f+'-peticion.json'),r=leer(dir+f+'-respuesta.json');
  r.validacion.inicializacion={estado:'pendiente',volumenes:{}};
  r.validacion.diagnosticos=leer(dir+'motor-ensamblaje-v2-validar-nrtl-4-par-ausente-respuesta.json').diagnosticos;
  checks++;assert.throws(()=>lector.leerResolucionV2(r,s),'A diagnosed structural closure never legitimizes an unevaluated trajectory');
}

if(process.argv.includes('--ui')){
  const {solicitud:s,respuesta:r}=leer('qa_n_componentes_2026_10_16/ideal-7-ejecucion-ui.json');
  const h=hojas.find(h=>h.id.endsWith('ideal-7'));
  igual({...s,solicitudId:''},{...h.redTermodinamica.solicitud,solicitudId:''},'Browser executes the same seven-component declarations');
  comprobarTrayectoria(s,r,h);
}

if(process.argv.includes('--servicio')){
  const api=process.env.MOTOR_API??'http://localhost:8004',salida='qa_n_componentes_2026_10_16';fs.mkdirSync(salida,{recursive:true});
  const c=lector.leerCapacidadesV2(await (await fetch(`${api}/motor/ensamblajes/capacidades?revision=2`)).json());
  check(c.componentesMaximos===7&&!!c.tamanos,'Running service has the N delivery loaded');
  fs.writeFileSync(`${salida}/capacidades.json`,JSON.stringify(c,null,2));
  const h=hojas.find(h=>h.id.endsWith('ideal-7')),s=h.redTermodinamica.solicitud;
  for(const ruta of ['validar','resolver']){
    const http=await fetch(`${api}/motor/ensamblajes/${ruta}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(s),signal:AbortSignal.timeout(240000)});
    check(http.ok,`${ruta} HTTP`);const r=await http.json();fs.writeFileSync(`${salida}/ideal-7-${ruta}.json`,JSON.stringify({solicitud:s,respuesta:r},null,2));
    if(ruta==='validar'){lector.leerValidacionV2(r,s);check(estado(r).puedeResolver,'Seven-component worksheet is ready without extra data');}
    else comprobarTrayectoria(s,r,h);
  }
}
console.log(`${checks} comprobaciones de integración N; ${estados} estados originales: capacidades y evidencia, inicialización física, datos de prueba, fases, inventarios y gráficos sin truncar componentes. No repite el flash ni sustituye el contraste físico.`);
