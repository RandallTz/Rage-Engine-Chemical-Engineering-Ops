import fs from 'node:fs';import ts from 'typescript';import assert from 'node:assert/strict';import katex from 'katex';
const cache=new Map();function cargar(n){if(cache.has(n))return cache.get(n);const m={exports:{}};cache.set(n,m.exports);new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(m.exports,m,r=>cargar(r.slice(2)));return m.exports;}
const contrato=cargar('contratoTermodinamica'),estado=cargar('estadoTermodinamicoHoja'),modelo=cargar('modeloHojaMotor'),relaciones=cargar('relacionesTermodinamicas'),servicio=cargar('servicioTermodinamica');
let checks=0;const check=(v,m)=>{checks++;assert.ok(v,m);},rechaza=(fn,m)=>{checks++;assert.throws(fn,undefined,m);};
// Synthetic protocol fixture. These numbers are NOT thermophysical data or equilibrium evidence.
const componentes=[{id:1,nombre:'A de prueba',simbolo:'A',identidadQuimica:{proveedorId:'fixture:a'}},{id:2,nombre:'B de prueba',simbolo:'B',identidadQuimica:{proveedorId:'fixture:b'}}];
const declaracion={modelo:{id:'fixture-protocolo',version:'1'},especificacion:{tipo:'TP',T:{valor:300,unidad:'K'},P:{valor:1,unidad:'bar'},composicion:{base:'molar',fracciones:{1:.5,2:.5}}},politica:{cantidad:'sin_restriccion',cambioInterno:'permitido',evaluacion:'equilibrio_estable'}};
const solicitud={revision:1,solicitudId:'caso-1',propietarioId:'volumen:v1',componentes,declaracion};
const cap={id:'fixture-protocolo',version:'1',nombre:'Fixture de contrato',componentesCAS:null,especificaciones:['TP','PH','UV','UP'],fases:['liquido','vapor'],dominio:{T:[1,1000],P:[1,1e9]},referencia:{id:'fixture-energia',descripcion:'Referencia sintética'},propiedades:['u','h','v','s'],dinamica:false};
const respuesta={revision:1,solicitudId:'caso-1',modelo:declaracion.modelo,estado:'evaluado',diagnosticos:[],evaluacion:{T:300,P:1e5,componentes:[{id:1,masaMolarKgMol:.01,fuente:'fixture'},{id:2,masaMolarKgMol:.02,fuente:'fixture'}],composicionMolar:{1:.5,2:.5},referencia:cap.referencia,mezcla:{u:6400,h:12440,v:.0604,s:5.2},fases:[{id:'l1',tipo:'liquido',regimen:'ordinario',fraccionMolar:.5,fraccionMasica:.4,fraccionVolumen:.4*.001/.0604,composicionMolar:{1:.8,2:.2},propiedades:{u:1000,h:1100,v:.001,s:-2}},{id:'v1',tipo:'vapor',regimen:'ordinario',fraccionMolar:.5,fraccionMasica:.6,fraccionVolumen:.6*.1/.0604,composicionMolar:{1:.2,2:.8},propiedades:{u:10000,h:20000,v:.1,s:10}}],estabilidad:{estado:'estable',alcance:['liquido','vapor'],metodo:'certificado sintético para probar el lector'},verificaciones:[{id:'estabilidad',estado:'cumple',residuo:0,tolerancia:1e-9},{id:'equilibrio',estado:'cumple',residuo:0,tolerancia:1e-9}]}};
check(!contrato.analizarSolicitudEstado(solicitud).length,'Especificación sintética completa');check(contrato.validarRespuestaEstado(respuesta,solicitud,cap)===respuesta,'Acepta reconstrucción consistente');
for(const [nombre,mutar]of [
 ['Identificación de solicitud',r=>r.solicitudId='otra'],['Revisión',r=>r.revision=2],['Versión',r=>r.modelo={...r.modelo,version:'2'}],['Estado ausente',r=>r.evaluacion=null],
 ['Temperatura NaN',r=>r.evaluacion.T=NaN],['Presión cero',r=>r.evaluacion.P=0],['Fase negativa',r=>r.evaluacion.fases[0].fraccionMolar=-.1],['Fase ausente publicada',r=>r.evaluacion.fases[0].fraccionMasica=0],
 ['IDs de fase repetidos',r=>r.evaluacion.fases[1].id='l1'],['Identidad repetida',r=>r.evaluacion.componentes[1].id=1],['Masa molar inválida',r=>r.evaluacion.componentes[0].masaMolarKgMol=0],
 ['Fuente ausente',r=>r.evaluacion.componentes[0].fuente=''],['h/u incompatibles',r=>r.evaluacion.mezcla.h+=1],['Fracciones de distinta base',r=>r.evaluacion.fases[0].fraccionMasica=.5],
 ['Fracción de volumen falsa',r=>r.evaluacion.fases[0].fraccionVolumen=.5],['Reconstrucción global falsa',r=>r.evaluacion.composicionMolar={1:.4,2:.6}],['Fase con componente desconocido',r=>r.evaluacion.fases[0].composicionMolar={1:.8,3:.2}],
 ['Estado metastable',r=>r.evaluacion.estabilidad.estado='metastable'],['Alcance incompleto',r=>r.evaluacion.estabilidad.alcance=['liquido']],['Equilibrio sin verificar',r=>r.evaluacion.verificaciones.pop()],
 ['Residuo mayor que tolerancia',r=>r.evaluacion.verificaciones[0].residuo=1],['Residuo negativo',r=>r.evaluacion.verificaciones[0].residuo=-1],['Resultado con fallo',r=>r.evaluacion.verificaciones[0].estado='no_cumple'],
 ['Cp bifásico ficticio',r=>r.evaluacion.mezcla.cp=4000],['Supercrítico con calidad',r=>r.evaluacion.fases[1].regimen='supercritico'],['Referencia distinta',r=>r.evaluacion.referencia={id:'otra',descripcion:'otra'}],
 ]){const r=structuredClone(respuesta);mutar(r);rechaza(()=>contrato.validarRespuestaEstado(r,solicitud,cap),nombre);}
for(const tipo of ['TP','PH','UV','UP']){
 const s=structuredClone(solicitud);
 s.declaracion.especificacion=tipo==='TP'?declaracion.especificacion:tipo==='PH'?{tipo,P:{valor:100,unidad:'kPa'},h:{valor:12.44,unidad:'kJ/kg'},composicion:{base:'masica',fracciones:{1:1/3,2:2/3}}}:tipo==='UV'?{tipo,U:{valor:6.4,unidad:'kJ'},V:{valor:60.4,unidad:'L'},cantidades:{base:'masica',valores:{1:{valor:1/3,unidad:'kg'},2:{valor:2/3,unidad:'kg'}}}}:{tipo,U:{valor:6400,unidad:'J'},P:{valor:1,unidad:'bar'},cantidades:{base:'molar',valores:{1:{valor:100/3,unidad:'mol'},2:{valor:100/3,unidad:'mol'}}}};
 check(!contrato.analizarSolicitudEstado(s).length,`${tipo}: datos y unidades`);check(contrato.validarRespuestaEstado(respuesta,s,cap).estado==='evaluado',`${tipo}: respeta especificación`);
 for(const cantidad of ['sin_restriccion','monofasico'])for(const cambioInterno of ['permitido','prohibido'])for(const r of relaciones.relacionesTermodinamicas(s.declaracion.especificacion,{cantidad,cambioInterno,evaluacion:'equilibrio_estable'})){katex.renderToString(r.latex,{throwOnError:true});checks++;}
 if(tipo==='UV'||tipo==='UP'){const mal=structuredClone(s);mal.declaracion.especificacion.U.valor=6500;rechaza(()=>contrato.validarRespuestaEstado(respuesta,mal,cap),'Energía total contradictoria');}
}
const mono=structuredClone(solicitud);mono.declaracion.politica.cantidad='monofasico';rechaza(()=>contrato.validarRespuestaEstado(respuesta,mono,cap),'Restricción monofásica');
const permitida=structuredClone(solicitud);permitida.declaracion.politica.tiposPermitidos=['liquido'];rechaza(()=>contrato.validarRespuestaEstado(respuesta,permitida,cap),'Fase permitida no fuerza equilibrio');
const nulo=structuredClone(solicitud);nulo.declaracion.especificacion.T.valor=null;check(contrato.analizarSolicitudEstado(nulo).some(x=>x.ruta.endsWith('.T')),'null pendiente');
const duplicada=structuredClone(solicitud);duplicada.declaracion.especificacion.U={valor:1,unidad:'J'};check(contrato.analizarSolicitudEstado(duplicada).length,'Rechaza sobreespecificación');
const desbalance=structuredClone(solicitud);desbalance.declaracion.especificacion.composicion.fracciones[1]=.4;check(contrato.analizarSolicitudEstado(desbalance).length,'No normaliza composición');
for(const codigo of ['incompleto','invalido','no_soportado','no_convergente']){const r={...respuesta,estado:codigo,evaluacion:null,diagnosticos:[{codigo:'FIXTURE',mensaje:'caso de prueba',ruta:'declaracion',propietarioId:solicitud.propietarioId,componenteIds:[]}]};check(contrato.validarRespuestaEstado(r,solicitud).estado===codigo,'Rechazos tipados');rechaza(()=>contrato.validarRespuestaEstado({...r,evaluacion:respuesta.evaluacion},solicitud),'No acepta resultado antiguo en rechazo');}
check(contrato.normalizarCantidad({valor:25,unidad:'degC'},'T')===298.15,'Desplazamiento Celsius');check(contrato.normalizarCantidad({valor:32,unidad:'degF'},'T')===273.15,'Desplazamiento Fahrenheit');
rechaza(()=>contrato.normalizarCantidad({valor:1,unidad:'kg'},'n'),'No hay factor universal masa/mol');
rechaza(()=>contrato.normalizarCantidad({valor:1,unidad:'toString'},'n'),'Unidad heredada del prototipo no es una unidad');
const desconocida=structuredClone(solicitud);desconocida.declaracion.especificacion.tipo='toString';check(contrato.analizarSolicitudEstado(desconocida).length,'Tipo heredado del prototipo no es una especificación');
check(contrato.validarCapacidadesEstado({revision:1,modelos:[cap]}).modelos.length===1,'Capacidades reales del servicio');for(const alterar of [c=>c.revision=2,c=>c.modelos[0].dominio.T=[300,100],c=>c.modelos[0].especificaciones=['XX'],c=>c.modelos.push(c.modelos[0])]){const c={revision:1,modelos:[structuredClone(cap)]};alterar(c);rechaza(()=>contrato.validarCapacidadesEstado(c),'Catálogo inválido');}
// Per-owner declarations and signatures do not replace material/energy calculations.
const h=cargar('hojasPruebaEnergia').crearHojasPruebaEnergia()[0],firma=modelo.firmaHoja(h),decl=estado.iniciarDeclaracionEstado([1]);
check(decl.especificacion.composicion.fracciones[1]===1,'Una especie: fracción uno por cierre, no parámetro ficticio');
const consulta=estado.guardarDeclaracionEstado(h,'volumen:dominio',decl);check(modelo.firmaHoja(consulta)===firma,'Consulta no altera identidad del cálculo');
check(modelo.analizarHoja(consulta).listo,'El modelo manual sigue resolviéndose');
const antes=await modelo.resolverHoja(h),despues=await modelo.resolverHoja(consulta);check(JSON.stringify(antes.valores)===JSON.stringify(despues.valores),'Regresión energética bit a bit');
const cierre=estado.guardarDeclaracionEstado(h,'volumen:dominio',decl,'cierre');check(!modelo.analizarHoja(cierre).listo,'Consulta no sustituye cierre dinámico');rechaza(()=>modelo.compilarHoja(cierre),'No cae al modelo manual silenciosamente');await assert.rejects(modelo.resolverHoja(cierre));checks++;
rechaza(()=>cargar('modeloEnergia').compilarEnergia(cierre),'Compilación energética directa conserva la guarda');
const identificado=estado.identificarComponenteEstado(consulta,1,'7732-18-5');check(estado.propietariosEstado(identificado)[0].componentes[0].identidadQuimica.cas==='7732-18-5','Identidad compartida por ID');check(JSON.stringify(identificado.config)===JSON.stringify(h.config),'Identificar no cambia cantidades ni caudales');
const conProveedor=structuredClone(consulta);conProveedor.historial.pasos[conProveedor.historial.activo].formulacion.componentes[0].identidadQuimica={proveedorId:'fixture:a'};check(estado.identificarComponenteEstado(conProveedor,1,'')===conProveedor,'Un campo CAS vacío no borra una identidad del proveedor');
rechaza(()=>contrato.validarRespuestaEstado(respuesta,solicitud,{...cap,componentesCAS:['7732-18-5']}),'El proveedor debe resolver una sustancia admitida por el paquete');
const ficticio=structuredClone(identificado);ficticio.termodinamica.estados['volumen:dominio'].resultado={firma:estado.firmaSolicitudHoja(ficticio,'volumen:dominio'),respuesta:{revision:1,solicitudId:'guardado',modelo:decl.modelo,estado:'incompleto',evaluacion:null,diagnosticos:[{codigo:'PENDIENTE',mensaje:'datos pendientes',ruta:'declaracion',propietarioId:'volumen:dominio',componenteIds:[1]}]}};
check(estado.evaluacionVigente(ficticio,'volumen:dominio')!==null,'Resultado vinculado a firma');const cambiado=structuredClone(ficticio);cambiado.termodinamica.estados['volumen:dominio'].declaracion.modelo.id='nuevo';check(estado.evaluacionVigente(cambiado,'volumen:dominio')===null,'Cambio de modelo invalida evaluación');
const invalidoGuardado=structuredClone(ficticio);invalidoGuardado.termodinamica.estados['volumen:dominio'].resultado.respuesta.evaluacion=respuesta.evaluacion;check(estado.evaluacionVigente(invalidoGuardado,'volumen:dominio')===null,'Reabrir revalida el protocolo y no acepta un estado incompatible');
const red=cargar('ensamblajeMateria').iniciarEnsamblaje(h.historial,h.config),hr={...h,...red};check(estado.propietariosEstado(hr).some(p=>p.tipo==='volumen'),'Propietarios de ensamblaje');
rechaza(()=>estado.guardarDeclaracionEstado(h,'volumen:inexistente',decl),'No inventa un volumen');
const {solicitudId:_,...a}=solicitud;void _;const b={...a,declaracion:{...a.declaracion,especificacion:{...a.declaracion.especificacion,composicion:{base:'molar',fracciones:{2:.5,1:.5}}}}};check(contrato.firmaEstado(a)===contrato.firmaEstado(b),'Firma estable por claves, sin redondeo');
// HTTP stub validates transport only; it is not a property provider.
const fetchAnterior=globalThis.fetch;
try{let invocaciones=0;globalThis.fetch=async(url,init)=>{invocaciones++;check(url.endsWith('/motor/termodinamica/evaluar'),'Ruta independiente del laboratorio');check(JSON.parse(init.body).solicitudId===solicitud.solicitudId,'Envía especificación intacta');return {ok:true,status:200,headers:new Headers({'content-type':'application/json'}),json:async()=>respuesta};};check((await servicio.evaluarEstadoTermodinamico(solicitud,cap)).estado==='evaluado','Respuesta revalidada por servicio');await assert.rejects(servicio.evaluarEstadoTermodinamico(nulo,cap));checks++;check(invocaciones===1,'Datos inválidos no se envían');globalThis.fetch=async()=>({ok:false,status:404});await assert.rejects(servicio.capacidadesTermodinamica(),/aún no está disponible/);checks++;globalThis.fetch=async()=>({ok:true,status:200,headers:new Headers({'content-type':'text/html'})});await assert.rejects(servicio.capacidadesTermodinamica(),/incompatible/);checks++;}finally{globalThis.fetch=fetchAnterior;}
// Real UNIFAC rejection: admission details belong to the backend, not a generic
// local CAS-list error. These are original endpoint fixtures, not new physics.
const dirGrupos='../docs/ejemplos/motor-unifac/',leerReal=n=>JSON.parse(fs.readFileSync(dirGrupos+n,'utf8'));
const sr=leerReal('motor-termodinamica-rechazo-unifac-lle-metanol-sin-grupo-peticion.json'),rr=leerReal('motor-termodinamica-rechazo-unifac-lle-metanol-sin-grupo-respuesta.json');
const cr=contrato.validarCapacidadesEstado(leerReal('motor-termodinamica-capacidades.json')).modelos.find(c=>c.id===sr.declaracion.modelo.id&&c.version===sr.declaracion.modelo.version);
check(!cr.componentesCAS.includes('67-56-1'),'Published catalog really excludes methanol for ELL');
// Historical HTTP evidence of an evaluated pure state outside its own catalog.
// Preserve the rejection guard without requiring the live backend to keep the bug.
const qa='qa_integracion_unifac_2026_10_16/',leerQA=n=>JSON.parse(fs.readFileSync(qa+n,'utf8'));
const puroS=leerQA('ell-metanol-puro-peticion.json'),puroR=leerQA('ell-metanol-puro-respuesta.json'),puroC=contrato.validarCapacidadesEstado(leerQA('capacidades-puntuales-f2.json')).modelos.find(c=>c.id===puroS.declaracion.modelo.id&&c.version===puroS.declaracion.modelo.version);
check(puroR.estado==='evaluado'&&!puroC.componentesCAS.includes('67-56-1'),'Original pure-state response conflicts with its published admission');
rechaza(()=>contrato.validarRespuestaEstado(puroR,puroS,puroC),'An evaluated state does not bypass the actual operation catalog');
const timeoutAnterior=AbortSignal.timeout,presupuestos=[];
try{
  AbortSignal.timeout=ms=>{presupuestos.push(ms);return timeoutAnterior(ms);};
  let llamadas=0;
  globalThis.fetch=async(url,init)=>{llamadas++;check(url.endsWith('/evaluar')&&init.cache==='no-store','State admission is delegated to its existing operation without caching');check(JSON.stringify(JSON.parse(init.body))===JSON.stringify(sr),'No parameter, composition or model is substituted');return new Response(JSON.stringify(rr),{headers:{'content-type':'application/json'}});};
  const antes=JSON.stringify(sr),real=await servicio.evaluarEstadoTermodinamico(sr,cr);
  check(real.estado==='no_soportado'&&real.evaluacion===null,'Known unsupported state is an original structured response');
  check(JSON.stringify(real.diagnosticos)===JSON.stringify(rr.diagnosticos),'Code, component IDs, owner and route are not replaced by generic transport text');
  check(JSON.stringify(sr)===antes,'Query does not modify the component catalog');
  check(presupuestos.at(-1)>33000&&presupuestos.at(-1)<=120000,'Inversion budget covers the published 20–33 s benchmark and remains bounded');
  await assert.rejects(servicio.evaluarEstadoTermodinamico(sr,{...cr,version:'otra'}),/no está disponible/);checks++;
  check(llamadas===1,'Unsupported model version never reaches another package');
  globalThis.fetch=async()=>new Response(JSON.stringify({revision:1,modelos:[cr]}),{headers:{'content-type':'application/json'}});
  await servicio.capacidadesTermodinamica();check(presupuestos.at(-1)===20000,'Fast catalog operation retains a separate short deadline');

  // Transport-only hanging request: cancellation must reach fetch; no real
  // solver is stopped or simulated here.
  let signalFetch;
  globalThis.fetch=async(url,init)=>new Promise((resolve,reject)=>{signalFetch=init.signal;if(init.signal.aborted)reject(init.signal.reason);else init.signal.addEventListener('abort',()=>reject(init.signal.reason),{once:true});});
  const ctl=new AbortController(),enCurso=servicio.evaluarEstadoTermodinamico(sr,cr,ctl.signal);
  check(signalFetch&&!signalFetch.aborted,'Caller signal reaches the state request');
  ctl.abort();await assert.rejects(enCurso,e=>e.name==='AbortError');checks++;
  check(signalFetch.aborted,'Cancel wait aborts the pending client fetch');
  const previo=new AbortController();previo.abort();await assert.rejects(servicio.evaluarEstadoTermodinamico(sr,cr,previo.signal),e=>e.name==='AbortError');checks++;
  const control=new (cargar('operacionRed').ControlOperacionRed)(),vieja=control.iniciar();control.cancelar();const nueva=control.iniciar();
  check(!control.vigente(vieja)&&control.vigente(nueva),'Cancelled evaluation cannot publish over a new query');
  check(!control.finalizar(vieja)&&control.vigente(nueva),'Late finalization cannot clear the newer busy state');
  check(control.finalizar(nueva),'Active query can finish normally');
}finally{globalThis.fetch=fetchAnterior;AbortSignal.timeout=timeoutAnterior;}
if(process.argv.includes('--servicio')){
  // Prepare U/V from an original TP state and one mole of its published global
  // composition. Only extensive bookkeeping is done here; the backend performs
  // the inversion. This round trip is not an independent EOS validation.
  const sTP=leerReal('motor-termodinamica-unifac-7-lv-peticion.json'),rTP=contrato.validarRespuestaEstado(leerReal('motor-termodinamica-unifac-7-lv-respuesta.json'),sTP),e=rTP.evaluacion;
  const cLive=(await servicio.capacidadesTermodinamica()).modelos.find(c=>c.id===sTP.declaracion.modelo.id&&c.version===sTP.declaracion.modelo.version);
  check(cLive?.especificaciones.includes('UV'),'Actual server publishes UV for the selected package');
  const masa=e.componentes.reduce((m,c)=>m+e.composicionMolar[c.id]*c.masaMolarKgMol,0),sUV=structuredClone(sTP);
  sUV.solicitudId='qa-f2-consulta-uv-7';
  sUV.declaracion.especificacion={tipo:'UV',U:{valor:masa*e.mezcla.u,unidad:'J'},V:{valor:masa*e.mezcla.v,unidad:'m3'},cantidades:{base:'molar',valores:Object.fromEntries(e.componentes.map(c=>[c.id,{valor:e.composicionMolar[c.id],unidad:'mol'}]))}};
  const carpeta=`.tmp/qa-f2-consulta-${new Date().toISOString().replace(/[:.]/g,'-')}`;fs.mkdirSync(carpeta,{recursive:true});
  fs.writeFileSync(`${carpeta}/peticion.json`,JSON.stringify(sUV,null,2)+'\n');
  const inicio=performance.now(),rUV=await servicio.evaluarEstadoTermodinamico(sUV,cLive),segundos=(performance.now()-inicio)/1000;
  fs.writeFileSync(`${carpeta}/respuesta.json`,JSON.stringify(rUV,null,2)+'\n');
  check(rUV.estado==='evaluado'&&rUV.evaluacion.componentes.length===7,'Actual seven-component UV query passes the unchanged strict reader');
  const cercano=(a,b)=>Math.abs(a-b)<=1e-6*Math.max(1,Math.abs(a),Math.abs(b));
  check(cercano(rUV.evaluacion.T,e.T)&&cercano(rUV.evaluacion.P,e.P),'TP to UV recovers the original T and P within the comparison tolerance');
  fs.writeFileSync(`${carpeta}/resumen.json`,JSON.stringify({fuenteTP:'docs/ejemplos/motor-unifac/motor-termodinamica-unifac-7-lv-*',segundos,componentes:rUV.evaluacion.componentes.length,T:rUV.evaluacion.T,P:rUV.evaluacion.P,estado:rUV.estado},null,2)+'\n');
  const falta=await servicio.evaluarEstadoTermodinamico(sr,cr);
  fs.writeFileSync(`${carpeta}/rechazo-peticion.json`,JSON.stringify(sr,null,2)+'\n');
  fs.writeFileSync(`${carpeta}/rechazo-respuesta.json`,JSON.stringify(falta,null,2)+'\n');
  check(falta.estado==='no_soportado'&&falta.diagnosticos.some(d=>d.codigo==='MOTOR_ESTADO_UNIFAC_ASIGNACION_AUSENTE'&&d.propietarioId===sr.propietarioId&&d.ruta==='componentes'),'Actual missing-group response keeps structured origin through the frontend service');
  console.log(`Consulta UV real de siete componentes: ${segundos.toFixed(2)} s; evidencia ${carpeta}. No se reinició ni modificó el backend.`);
}
console.log(`${checks} comprobaciones del contrato: unidades, reconstrucción, hipótesis, propietarios, vigencia, guardas, diagnóstico real de catálogo y cancelación del cliente. Los stubs verifican transporte; no validan propiedades ni estabilidad física.`);
