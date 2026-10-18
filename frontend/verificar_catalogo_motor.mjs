// Protocol, admission and editing checks; no replacement thermodynamic calculation.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
import ts from 'typescript';
const require=createRequire(import.meta.url),cache=new Map();
function cargar(n){
  if(n.endsWith('.json'))return JSON.parse(fs.readFileSync(`app/motor/${n}`,'utf8'));
  if(cache.has(n))return cache.get(n);
  const m={exports:{}};cache.set(n,m.exports);
  new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText)(m.exports,m,id=>id.startsWith('./')?cargar(path.posix.join(path.posix.dirname(n),id)):require(id));
  return m.exports;
}
let checks=0;const check=(v,m)=>{checks++;assert.ok(v,m);},igual=(a,b,m)=>{checks++;assert.deepEqual(a,b,m);},rechaza=f=>{checks++;assert.throws(f);};
const dir='../docs/ejemplos/motor-catalogo/',leer=f=>JSON.parse(fs.readFileSync(dir+f,'utf8'));
const {leerCatalogoMotor}=cargar('lectorCatalogo'),{opcionesCatalogoRed}=cargar('seleccionCatalogoRed');
const raw=leer('motor-catalogo.json'),antes=JSON.stringify(raw),cat=leerCatalogoMotor(raw);
igual(cat,raw,'Actual catalog accepted without conversion');
const normalizar=s=>s.replaceAll('\r\n','\n').replaceAll("'../../frontend/app/motor/contratoTermodinamica'","'./contratoTermodinamica'");
igual(normalizar(fs.readFileSync('app/motor/contratoCatalogo.ts','utf8')),normalizar(fs.readFileSync('../docs/contratos/contratoCatalogo.ts','utf8')),'Canonical contract synchronized except local import');
const cap=cargar('contratoTermodinamica').validarCapacidadesEstado(leer('motor-termodinamica-capacidades.json'));
for(const p of cat.paquetes){
  const c=cap.modelos.find(m=>m.id===p.modelo.id&&m.version===p.modelo.version);
  check(!!c,'Every catalog package is published in actual point capabilities');
  igual(p.especies.filter(e=>e.admitida).map(e=>e.cas).sort(),[...c.componentesCAS].sort(),'Catalog admission agrees with actual capabilities');
}
for(const cambio of [
  c=>c.revision=2,c=>c.sustancias.push(c.sustancias[0]),c=>c.sustancias[0].id='otro',
  c=>c.sustancias[0].masaMolar.valor=NaN,c=>c.sustancias[0].masaMolar.valor=0,c=>c.sustancias[0].masaMolar.unidad='g/mol',c=>c.sustancias[0].masaMolar.fuente='   ',
  c=>c.sustancias[0].datosPuros.huella='sha256:inventada',c=>delete c.sustancias[0].datosPuros.propiedades,
  c=>c.sustancias[0].datosPuros.faltantes=[{dato:'presion_vapor',motivo:'Sin datos'}],
  c=>c.sustancias[0].datosPuros.propiedades[0].coeficientes.A=Infinity,
  c=>c.sustancias[0].datosPuros.propiedades[0].coeficientes.Tc=0,
  c=>c.sustancias[0].datosPuros.propiedades[0].dominio.T=[500,300],
  c=>c.sustancias[0].datosPuros.propiedades[1].unidad='J/kg',
  c=>c.sustancias[0].datosPuros.propiedades[2].valor=-1,
  c=>c.sustancias[0].datosPuros.propiedades.push(c.sustancias[0].datosPuros.propiedades[0]),
  c=>c.paquetes.push(c.paquetes[0]),c=>c.paquetes[0].especies.reverse(),c=>c.paquetes[0].especies.pop(),
  c=>c.paquetes[0].especies[0].admitida=!c.paquetes[0].especies[0].admitida,
  c=>c.paquetes[0].especies[0].faltantes=[{dato:'registro',codigo:'inventado',mensaje:'Sin dato'}],
  c=>c.paquetes[0].requisitos.porEspecie=['inventado'],c=>c.paquetes[0].operaciones.estado.especificaciones=['inventada'],
  c=>c.paquetes[0].operaciones.diagramas={disponible:false,operaciones:['Txy']},
  c=>c.noDisponible[0].motivo='',
]){const c=structuredClone(raw);cambio(c);rechaza(()=>leerCatalogoMotor(c));}
// A real new catalog entry must not require editing the reader. Structural fixture
// only: this does not register a substance or claim it has a thermodynamic model.
const mayor=structuredClone(raw),sintetica=structuredClone(mayor.sustancias[0]);
sintetica.id=sintetica.cas='identidad-publicada-futura';sintetica.nombre='Especie de ensayo estructural';mayor.sustancias.push(sintetica);
for(const p of mayor.paquetes)p.especies.push({cas:sintetica.cas,admitida:false,faltantes:[{dato:'registro',codigo:'COMPONENTE_NO_SOPORTADO',mensaje:'Ensayo de extensión de catálogo'}]});
igual(leerCatalogoMotor(mayor),mayor,'Additional substance identity requires no client whitelist');
const incompleto=structuredClone(mayor),d=incompleto.sustancias.at(-1).datosPuros;
d.estado='incompletos';d.faltantes=[{dato:'cp_gas_ideal',motivo:'Sin coeficientes publicados'}];delete d.propiedades;delete d.dominioLiquido;delete d.huella;
igual(leerCatalogoMotor(incompleto),incompleto,'Incomplete pure data remains inspectable without invented zeros');

const red=structuredClone(cargar('hojasPruebaMultifasico').crearHojasPruebaMultifasico()[1].redTermodinamica);
red.solicitud.paquetes.find(p=>p.id===red.solicitud.volumenes[0].paqueteId).modelo={id:'unifac-original-lle-public',version:'1'};
const B=red.solicitud.volumenes[1];B.paqueteId='otra';red.solicitud.paquetes.push({id:'otra',modelo:{id:'unifac-original-public',version:'1'}});
const a=red.solicitud.volumenes[0].id,b=B.id,redAntes=JSON.stringify(red);
const buscar=(ids,q)=>opcionesCatalogoRed(cat,red,ids,q),metanol=buscar([a],'metanol')[0];
check(!metanol.elegible&&metanol.volumenes[0].motivos.some(m=>m.includes('asignacion_grupos_lle')),'Pure methanol blocked by real ELL group requirement');
check(buscar([b],'metanol')[0].elegible,'Same substance permitted by the explicitly chosen original package');
check(!buscar([a,b],'metanol')[0].elegible,'Cannot silently assign to a target with a different package requirement');
check(buscar([],'metanol')[0].elegible,'Without targets, a substance may be selected when a volume admits it');
check(buscar([b],'67-56-1')[0].sustancia.nombre==='metanol','Search by CAS shows actual name');
check(buscar([b],'  MeTaNoL ')[0].sustancia.cas==='67-56-1','Search preserves identity while tolerating case and whitespace');
check(buscar([b],'no registrada').length===0,'No search fallback or fabricated chemical');
const agua=cat.sustancias.find(s=>s.nombre==='agua');check(buscar([b],agua.cas)[0].presente&&!buscar([b],agua.cas)[0].elegible,'Existing species is inspectable but not duplicated');
const ausente=structuredClone(red);ausente.solicitud.paquetes.find(p=>p.id==='otra').modelo.version='retirada';
check(!opcionesCatalogoRed(cat,ausente,[b],'metanol')[0].elegible,'Exact saved model revision is required');
const editar=cargar('componentesRed'),nuevo=structuredClone(red);editar.agregarComponenteRed(nuevo,'Borrador simbólico','',[],7);
check(!nuevo.solicitud.componentes.at(-1).identidadQuimica?.cas&&!nuevo.solicitud.componentes.at(-1).masaMolar,'Symbolic drafting remains possible without state data');
editar.agregarComponenteRed(nuevo,metanol.sustancia.nombre,metanol.sustancia.cas,[b],7);
check(!nuevo.solicitud.componentes.at(-1).masaMolar,'Choosing a registered species does not inject its mixture molar mass into IAPWS or other models');
igual(JSON.stringify(red),redAntes,'Catalog inspection leaves worksheet declarations intact');igual(JSON.stringify(raw),antes,'Reader and choices leave original evidence intact');
const {estadoResolucionRed}=cargar('estadoResolucionRed');
igual(estadoResolucionRed({diagnosticos:[{codigo:'MOTOR_ENS_DATO_PURO_AUSENTE',estado:'no_soportado'}],recuento:{estado:'incompleto'}}).estado,'Faltan datos del paquete','Missing pure property is shown as package data, not free variables');

// F2.4–F2.6: every new real point, network and cut is read without rewriting it.
const ct=cargar('contratoTermodinamica'),lv=cargar('lectorEnsamblajeV2'),ld=cargar('lectorDiagramasEquilibrio');
const sustituciones=cargar('sustitucionesDatosPuros'),datosDiagrama=cargar('datosDiagramaEquilibrio');
const parejas=fs.readdirSync(dir).filter(n=>n.endsWith('-peticion.json'));
for(const nombre of parejas){
  const s=leer(nombre),r=leer(nombre.replace('-peticion','-respuesta')),original=JSON.stringify([s,r]);
  if(nombre.startsWith('motor-termodinamica-')){ct.validarRespuestaEstado(r,s,cap.modelos.find(c=>c.id===s.declaracion.modelo.id&&c.version===s.declaracion.modelo.version));checks++;}
  else if(nombre.startsWith('motor-ensamblaje-')){if(nombre.includes('-resolver-'))lv.leerResolucionV2(r,s);else lv.leerValidacionV2(r,s);checks++;}
  else if(nombre.startsWith('motor-diagramas-')){ld.leerDiagramaEquilibrio(r,s);checks++;}
  igual(JSON.stringify([s,r]),original,'Original backend request/response is never patched to pass');
}
const etanol=cat.sustancias.find(s=>s.cas==='64-17-5'),v0=sustituciones.borradorDatoPuro(etanol,'volumen_liquido');
check(sustituciones.problemaBorradorDatoPuro('volumen_liquido',v0)!==null,'Explicit source required even when seeding from registry');
const vl={valor:60,unidad:'cm3/mol',fuente:'QA · declaración de usuario'},dvl=sustituciones.sustituirDatoPuro(undefined,etanol.cas,'volumen_liquido',vl);
igual(dvl[etanol.cas].volumen_liquido,vl,'No implicit volume unit conversion or source replacement');
check(sustituciones.problemaBorradorDatoPuro('volumen_liquido',vl)===null,'Supported scalar declaration');
for(const c of [{...vl,valor:0},{...vl,unidad:'kg/m3'},{...vl,fuente:' '},{...vl,valor:NaN}])check(!!sustituciones.problemaBorradorDatoPuro('volumen_liquido',c),'Malformed scalar is an incomplete draft');
for(const id of ['cp_gas_ideal','presion_vapor']){
  const v=sustituciones.borradorDatoPuro(etanol,id);check(!!v&&!v.fuente,'Original correlation copied only to explicit draft');v.fuente='QA · correlación declarada';
  check(sustituciones.problemaBorradorDatoPuro(id,v)===null,'Typed correlation source and domain accepted');
  const ausente=structuredClone(v);ausente.coeficientes[Object.keys(ausente.coeficientes)[0]]=NaN;check(!!sustituciones.problemaBorradorDatoPuro(id,ausente),'Missing coefficient remains missing');
  const sinDominio=structuredClone(v);sinDominio.dominio.T=[500,200];check(!!sustituciones.problemaBorradorDatoPuro(id,sinDominio),'Reversed domain refused before applying');
}
const conCp=sustituciones.sustituirDatoPuro(dvl,etanol.cas,'cp_gas_ideal',{...sustituciones.borradorDatoPuro(etanol,'cp_gas_ideal'),fuente:'QA · cp'});
check(Object.keys(conCp[etanol.cas]).length===2&&Object.keys(dvl[etanol.cas]).length===1,'Independent immutable edits per property');
const restaurado=sustituciones.sustituirDatoPuro(conCp,etanol.cas,'volumen_liquido',undefined);
check(restaurado[etanol.cas].cp_gas_ideal&&!restaurado[etanol.cas].volumen_liquido,'Restoring one field preserves other explicit choices');
check(sustituciones.sustituirDatoPuro(restaurado,etanol.cas,'cp_gas_ideal',undefined)===undefined,'Restoring all removes the additive request field');
const fuenteOtra=structuredClone(dvl);fuenteOtra[etanol.cas].volumen_liquido.fuente+=' revisada';
check(sustituciones.firmaDatosPuros(dvl)!==sustituciones.firmaDatosPuros(fuenteOtra),'Source is part of request identity');

const hbase=cargar('hojasPruebaMultifasico').crearHojasPruebaMultifasico()[1],{cambiarRed,solicitudRed}=cargar('redTermodinamica'),{firmaHoja}=cargar('modeloHojaMotor');
const h={...structuredClone(hbase),resultadoRef:{firma:firmaHoja(hbase),estado:'resuelto',fecha:'QA'}};
h.redTermodinamica.solicitud.paquetes[0].datosPuros=dvl;
const hAntes=JSON.stringify(h),cambiada=cambiarRed(h,red=>red.solicitud.paquetes[0].datosPuros=fuenteOtra);
check(!cambiada.resultadoRef&&firmaHoja(cambiada)!==firmaHoja(h),'Changing only a source invalidates an old dynamic result');
igual(JSON.stringify(h),hAntes,'Original worksheet remains untouched');
igual(solicitudRed(cambiada,'solicitud').paquetes[0].datosPuros,fuenteOtra,'Explicit substitutions survive serialization to the dynamic route');
const compartida=structuredClone(h.redTermodinamica);compartida.solicitud.volumenes.forEach(v=>v.paqueteId=compartida.solicitud.paquetes[0].id);
const anterior=compartida.solicitud.volumenes[0].paqueteId;compartida.originalesDatosPuros={[anterior]:{[etanol.cas]:etanol.datosPuros.propiedades}};
cargar('topologiaRed').elegirPaqueteVolumen(compartida,compartida.solicitud.volumenes[0].id,{id:'unifac-original-public',version:'1'});
const nuevoId=compartida.solicitud.volumenes[0].paqueteId;
check(nuevoId!==anterior,'Changing a shared package splits its identity');
igual(compartida.solicitud.paquetes.find(p=>p.id===nuevoId).datosPuros,dvl,'A model change preserves explicit data choices for backend acceptance/rejection');
igual(compartida.originalesDatosPuros[nuevoId],compartida.originalesDatosPuros[anterior],'Original data snapshot survives a package split');
compartida.solicitud.paquetes.find(p=>p.id===nuevoId).datosPuros[etanol.cas].volumen_liquido.valor=61;
check(compartida.solicitud.paquetes.find(p=>p.id===anterior).datosPuros[etanol.cas].volumen_liquido.valor===60,'Split package does not alias another volume');

const sn=leer('motor-ensamblaje-v2-resolver-sustitucion-vl-etanol-peticion.json'),rn=leer('motor-ensamblaje-v2-resolver-sustitucion-vl-etanol-respuesta.json');
const hr={...hbase,redTermodinamica:{solicitud:sn,nombres:{}}},resultado=cargar('resultadoEnsamblajeV2').adaptarResultadoV2(hr,sn,rn);
const contexto=cargar('contextoMuestraEquilibrio').contextoMuestraEquilibrio(resultado,sn.volumenes[0].id,0);
igual(contexto.datosPuros,sn.paquetes[0].datosPuros,'Selected-state context keeps the actual executed overrides');
const sd=datosDiagrama.prepararSolicitudDiagrama(contexto,{tipo:'Pxy',T:{valor:contexto.T,unidad:'K'}},sn.componentes[0].id,'exploratoria','qa-datos');
igual(sd.datosPuros,contexto.datosPuros,'Diagram uses the same overridden potential as its simulation');
sd.datosPuros[etanol.cas].volumen_liquido.valor+=1;check(contexto.datosPuros[etanol.cas].volumen_liquido.valor===60,'Diagram request does not mutate executed data');
const mezclados={...dvl,'7732-18-5':{volumen_liquido:{valor:18,unidad:'cm3/mol',fuente:'QA'}}};
igual(Object.keys(sustituciones.datosPurosDeComponentes(mezclados,[sn.componentes.find(c=>c.identidadQuimica.cas===etanol.cas)])),[etanol.cas],'A shared package forwards only the selected volume species to a point or diagram');
const sp=leer('motor-diagramas-pxy-etanol-agua-nrtl-sustitucion-vl-peticion.json'),rp=leer('motor-diagramas-pxy-etanol-agua-nrtl-sustitucion-vl-respuesta.json'),mem=new datosDiagrama.MemoriaDiagramas();
const guardable={...sp,huellaModeloEsperada:rp.identidad.huellaModelo};mem.guardar(guardable,rp);check(!!mem.recuperar(guardable,rp.identidad.trazador),'Real overridden diagram cacheable');
const alterada=structuredClone(guardable);alterada.datosPuros[etanol.cas].volumen_liquido.fuente+=' otra';check(!mem.recuperar(alterada,rp.identidad.trazador),'Changing a source cannot reuse a diagram even with an old expected fingerprint');
const diag={estado:'invalido',codigo:'MOTOR_ENS_SUSTITUCION_INVALIDA',mensaje:'Fuente ausente',variableIds:[],origen:{propietarioId:'red',ruta:'/paquetes/0/datosPuros/64-17-5/volumen_liquido/fuente'}};
igual(cargar('destinoDiagnosticoRed').destinoDiagnosticoRed(sn,diag),{vista:'estado',propietarioId:`volumen:${sn.volumenes[0].id}`,control:'propiedades'},'Structured override path focuses its package editor, not an inventory');
const cp=conCp[etanol.cas].cp_gas_ideal;
check(sustituciones.temperaturaEnRangosSustituidos(cp.dominio.T[0]-1,conCp)===false,'A successful state outside a declared override interval is rejected');
check(sustituciones.temperaturaEnRangosSustituidos(300,dvl)===undefined,'Scalar volume override does not enlarge thermal scope');
const tpOriginal=leer('motor-termodinamica-sustitucion-vl-etanol-nrtl-peticion.json'),tpRespuesta=leer('motor-termodinamica-sustitucion-vl-etanol-nrtl-respuesta.json');
const tpConCp=structuredClone(tpOriginal);tpConCp.declaracion.datosPuros=conCp;
const cpCap=structuredClone(cap.modelos.find(c=>c.id===tpConCp.declaracion.modelo.id));cpCap.dominio.T=[280,299];
// A deliberately narrower static envelope exercises protocol behavior. The
// original Cp coefficients and the actual domain verification remain intact.
ct.validarRespuestaEstado(tpRespuesta,tpConCp,cpCap);checks++;
const sinDominio=structuredClone(tpRespuesta);sinDominio.evaluacion.verificaciones=sinDominio.evaluacion.verificaciones.filter(v=>v.id!=='dominio');rechaza(()=>ct.validarRespuestaEstado(sinDominio,tpConCp,cpCap));
const fueraIntervalo=structuredClone(tpConCp);fueraIntervalo.declaracion.datosPuros[etanol.cas].cp_gas_ideal.dominio.T=[310,400];rechaza(()=>ct.validarRespuestaEstado(tpRespuesta,fueraIntervalo,cpCap));
rechaza(()=>ct.validarRespuestaEstado(tpRespuesta,tpOriginal,cpCap));
for(const [codigo,estado] of [['MOTOR_ENS_SUSTITUCION_INVALIDA','Revisar propiedades del paquete'],['MOTOR_ENS_SUSTITUCION_NO_ADMITIDA','Sustitución no admitida'],['MOTOR_ENS_REFERENCIAS_INCOMPATIBLES','Referencias incompatibles']]){
  const resumen=estadoResolucionRed({modeloId:'cerrado',diagnosticos:[{codigo,estado:'invalido'}],recuento:{estado:'listo'},inicializacion:{estado:'compatible'}});
  check(!resumen.puedeResolver&&resumen.estado===estado,'Structural GL=0 does not hide a property or reference rejection');
}
const bloqueada=structuredClone(rn.validacion);bloqueada.modeloId=null;bloqueada.inicializacion={estado:'pendiente',volumenes:{}};bloqueada.diagnosticos=[{...diag,origen:{...diag.origen,propietarioId:`volumen:${sn.volumenes[0].id}`}}];
lv.leerValidacionV2(bloqueada,sn);checks++;
check(!estadoResolucionRed(bloqueada).puedeResolver,'Closed structural count without a model is never executable');
const sinCausa=structuredClone(bloqueada);sinCausa.diagnosticos=[];rechaza(()=>lv.leerValidacionV2(sinCausa,sn));
const inicialCompatible=structuredClone(bloqueada);inicialCompatible.inicializacion=rn.validacion.inicializacion;rechaza(()=>lv.leerValidacionV2(inicialCompatible,sn));

// Transport tests use actual published payloads, not a fabricated successful state.
const {catalogoMotor}=cargar('servicioCatalogo'),fetchAnterior=globalThis.fetch;
try{
  globalThis.fetch=async(url,op)=>{check(url.endsWith('/motor/catalogo')&&op.cache==='no-store','Canonical route without cached substitution');return new Response(JSON.stringify(raw),{headers:{'Content-Type':'application/json'}});};
  igual(await catalogoMotor(),raw,'Catalog service passes the complete real response through its reader');
  for(const response of [new Response('',{status:404}),new Response('',{status:503}),new Response('<html>error</html>',{headers:{'Content-Type':'text/html'}}),new Response('{"revision":2}',{headers:{'Content-Type':'application/json'}})]){
    globalThis.fetch=async()=>response;checks++;await assert.rejects(()=>catalogoMotor());
  }
  globalThis.fetch=async(_url,op)=>{op.signal.throwIfAborted();throw new Error('Unexpected non-aborted request');};
  const c=new AbortController();c.abort();checks++;await assert.rejects(()=>catalogoMotor(c.signal),{name:'AbortError'});
}finally{globalThis.fetch=fetchAnterior;}
if(process.argv.includes('--servicio')){
  const dirSalida=`.tmp/catalogo-f2-${new Date().toISOString().replaceAll(/[:.]/g,'-')}`;fs.mkdirSync(dirSalida,{recursive:true});
  const respuesta=await catalogoMotor();fs.writeFileSync(`${dirSalida}/catalogo.json`,JSON.stringify(respuesta,null,2)+'\n');checks++;
  const caps=await fetch('http://localhost:8004/motor/termodinamica/capacidades').then(r=>r.json());
  for(const p of respuesta.paquetes){const q=caps.modelos.find(m=>m.id===p.modelo.id&&m.version===p.modelo.version);igual(p.especies.filter(e=>e.admitida).map(e=>e.cas).sort(),[...q.componentesCAS].sort(),'Live catalog and capabilities agree');}
  const s=leer('motor-termodinamica-rechazo-metanol-puro-unifac-ell-peticion.json'),r=await fetch('http://localhost:8004/motor/termodinamica/evaluar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(s)}).then(r=>r.json());
  fs.writeFileSync(`${dirSalida}/metanol-ell-rechazo.json`,JSON.stringify(r,null,2)+'\n');
  cargar('contratoTermodinamica').validarRespuestaEstado(r,s);checks++;
  check(r.estado==='no_soportado'&&r.diagnosticos.some(d=>d.codigo==='MOTOR_ESTADO_UNIFAC_ASIGNACION_AUSENTE'),'F9-R3 live rejection agrees with declared admission');
  console.log(`Evidencia HTTP: ${dirSalida}`);
  for(const nombre of ['motor-termodinamica-sustitucion-vl-etanol-nrtl','motor-ensamblaje-v2-resolver-corriente-nrtl-a-unifac','motor-ensamblaje-v2-resolver-contacto-iapws-y-mezcla','motor-ensamblaje-v2-resolver-sustitucion-vl-etanol','motor-ensamblaje-v2-validar-rechazo-corriente-iapws-a-mezcla','motor-diagramas-pxy-etanol-agua-nrtl-sustitucion-vl']){
    const s=leer(nombre+'-peticion.json'),ruta=nombre.startsWith('motor-termodinamica-')?'/motor/termodinamica/evaluar':nombre.startsWith('motor-diagramas-')?'/motor/termodinamica/diagramas/trazar':nombre.includes('-validar-')?'/motor/ensamblajes/validar':'/motor/ensamblajes/resolver';
    const http=await fetch('http://localhost:8004'+ruta,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(s),signal:AbortSignal.timeout(180000)});check(http.ok,'Live route '+ruta);const r=await http.json();
    fs.writeFileSync(`${dirSalida}/${nombre}-peticion.json`,JSON.stringify(s,null,2)+'\n');fs.writeFileSync(`${dirSalida}/${nombre}-respuesta.json`,JSON.stringify(r,null,2)+'\n');
    if(s.revision===2){if(ruta.endsWith('/resolver')){lv.leerResolucionV2(r,s);check(r.resultados?.certificacion.estado==='cumple','Live network certified');}else {lv.leerValidacionV2(r,s);check(r.diagnosticos.some(d=>d.codigo==='MOTOR_ENS_REFERENCIAS_INCOMPATIBLES'),'IAPWS-to-mixture current remains explicitly rejected');}}
    else if(s.corte)ld.leerDiagramaEquilibrio(r,s);else ct.validarRespuestaEstado(r,s);checks++;
    igual(r.recuento?r.diagnosticos.map(d=>d.codigo):r.estado,leer(nombre+'-respuesta.json').recuento?leer(nombre+'-respuesta.json').diagnosticos.map(d=>d.codigo):leer(nombre+'-respuesta.json').estado,'Live result/rejection status agrees with delivered fixture');
    console.log('HTTP F2: '+nombre+' · '+(r.recuento?r.diagnosticos.map(d=>d.codigo).join(', '):r.estado));
  }
  const invalida=structuredClone(sn);invalida.paquetes[0].datosPuros[etanol.cas].volumen_liquido.fuente='';
  const validacion=await fetch('http://localhost:8004/motor/ensamblajes/validar',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(invalida)}).then(r=>r.json());
  fs.writeFileSync(`${dirSalida}/fuente-ausente-peticion.json`,JSON.stringify(invalida,null,2)+'\n');fs.writeFileSync(`${dirSalida}/fuente-ausente-respuesta.json`,JSON.stringify(validacion,null,2)+'\n');
  lv.leerValidacionV2(validacion,invalida);checks++;
  const d=validacion.diagnosticos.find(d=>d.codigo==='MOTOR_ENS_SUSTITUCION_INVALIDA');check(!!d,'Live invalid source rejected with own code');
  check(cargar('destinoDiagnosticoRed').destinoDiagnosticoRed(invalida,d)?.control==='propiedades','Actual backend route opens the property editor');
}
console.log(`${checks} comprobaciones del catálogo F2: contrato, fuentes, admisión por paquete, selección, compatibilidad y transporte. Sin cálculos termodinámicos en el cliente.`);
