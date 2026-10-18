import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const cache=new Map();
function cargar(n){if(n.endsWith('.json'))return JSON.parse(fs.readFileSync(`app/motor/${n}`,'utf8'));if(cache.has(n))return cache.get(n);const m={exports:{}};cache.set(n,m.exports);new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText)(m.exports,m,id=>cargar(id.slice(2)));return m.exports;}
const {cambiarRed,datoRed}=cargar('redTermodinamica'),top=cargar('topologiaRed');
const {HistorialEdicionRed}=cargar('historialEdicionRed'),{ControlOperacionRed}=cargar('operacionRed');
const {agregarComponenteRed,quitarComponenteRed}=cargar('componentesRed');
const {firmaHoja}=cargar('modeloHojaMotor');
const hojas=cargar('hojasPruebaMultifasico').crearHojasPruebaMultifasico();
let checks=0;const check=(v,m)=>{checks++;assert.ok(v,m);},igual=(a,b,m)=>{checks++;assert.deepEqual(a,b,m);},rechaza=f=>{checks++;assert.throws(f);};

// Reproduce shared local package IDs after cloning a volume: editing A isolates A.
let h=structuredClone(hojas[0]);
h=cambiarRed(h,r=>{r.solicitud.paquetes=[{id:'paquete-A',modelo:{id:'mezcla-ideal',version:'1'}}];r.solicitud.volumenes[0].paqueteId='paquete-A';top.agregarElementoRed(r,'volumen');});
const anterior=structuredClone(h),b=h.redTermodinamica.solicitud.volumenes[1];
h=cambiarRed(h,r=>top.elegirPaqueteVolumen(r,'A',{id:'nrtl-chemsep',version:'1'}));
let a=h.redTermodinamica.solicitud;
check(a.volumenes[0].paqueteId!==b.paqueteId,'Editing A allocates an independent package instead of overwriting B');
igual(a.paquetes.find(p=>p.id===b.paqueteId).modelo,{id:'mezcla-ideal',version:'1'},'B retains its selected model and version');
igual(a.volumenes[1],anterior.redTermodinamica.solicitud.volumenes[1],'Other volume configuration unchanged');
const sinCambio=JSON.stringify(h.redTermodinamica);
h=cambiarRed(h,r=>top.elegirPaqueteVolumen(r,'A',{id:'nrtl-chemsep',version:'1'}));
check(JSON.stringify(h.redTermodinamica)===sinCambio,'Choosing the same model does not allocate duplicate packages');
rechaza(()=>cambiarRed(h,r=>top.elegirPaqueteVolumen(r,'fantasma',{id:'x',version:'1'})));

// The new volume has blank data in the selected basis and no automatic streams.
for(const base of ['masica','molar'])for(const energia of ['T','U']){
  let x=structuredClone(hojas[0]);x.redTermodinamica.solicitud.volumenes[0].inicial.cantidades.base=base;x.redTermodinamica.solicitud.volumenes[0].inicial.energia.tipo=energia;
  const inicial=structuredClone(x.redTermodinamica.solicitud.volumenes[0]);
  x=cambiarRed(x,r=>top.agregarElementoRed(r,'volumen'));const s=x.redTermodinamica.solicitud,v=s.volumenes[1];
  igual(s.volumenes[0],inicial,'Original volume retained');check(s.corrientes.length===0,'No fabricated material streams');
  check(v.inicial.cantidades.base===base&&v.inicial.energia.tipo===energia,'Input basis and initialization choice retained');
  for(const id of Object.values(v.inicial.cantidades.datoIds))igual(s.datos[id].declaracion,{texto:'',unidad:base==='masica'?'kg':'mol'},'New quantity is pending in the declared basis');
  igual(s.datos[v.inicial.energia.datoId].declaracion,{texto:'',unidad:energia==='T'?'K':'J'},'No fabricated T/U initial state');
}
for(const tipo of ['volumen','corriente','calor']){
  let x=structuredClone(hojas[0]),id1,id2;
  x=cambiarRed(x,r=>{id1=top.agregarElementoRed(r,tipo);});
  x=cambiarRed(x,r=>top.quitarElementoRed(r,tipo,id1));
  x=cambiarRed(x,r=>{id2=top.agregarElementoRed(r,tipo);});
  check(id1!==id2,`${tipo} IDs are not reused after removal`);
}

// Undo restores cascaded topology AND its exact declarations, not just node names.
let doc=structuredClone(hojas[0]),hist=new HistorialEdicionRed();
function editar(fn,grupo){const previo=doc;doc=cambiarRed(doc,fn);hist.registrar(previo.redTermodinamica,doc.redTermodinamica,grupo);}
function mover(direccion){return hist.mover(doc.redTermodinamica,direccion,r=>{doc=cambiarRed(doc,x=>Object.assign(x,r));return doc.redTermodinamica;});}
editar(r=>{
  const v=top.agregarElementoRed(r,'volumen');top.agregarElementoRed(r,'corriente');
  const q=top.agregarElementoRed(r,'calor');r.solicitud.intercambiosTermicos.find(x=>x.id===q).hasta=v;
  for(const [id,d]of Object.entries(r.solicitud.datos))if(d.origen.propietarioId.endsWith(v)||d.origen.propietarioId===`calor:${q}`)d.declaracion={texto:id.endsWith('.T0')?'350':'1.25',unidad:d.declaracion.unidad};
});
const configurada=structuredClone(doc),firmaConfigurada=firmaHoja(doc),vid=doc.redTermodinamica.solicitud.volumenes.at(-1).id;
editar(r=>top.quitarElementoRed(r,'volumen',vid));
check(!doc.redTermodinamica.solicitud.volumenes.some(v=>v.id===vid),'Volume removed');
check(!Object.values(doc.redTermodinamica.solicitud.datos).some(d=>d.origen.propietarioId===`volumen:${vid}`),'Owned data no longer pollute Resolver');
check(hist.puedeDeshacer&&mover('deshacer'),'Undo available');
igual(doc.redTermodinamica.solicitud,configurada.redTermodinamica.solicitud,'Undo restores original inputs, connections and units');
check(firmaHoja(doc)===firmaConfigurada,'Undo restores the physical request signature');
check(mover('rehacer')&&!doc.redTermodinamica.solicitud.volumenes.some(v=>v.id===vid),'Redo reapplies the removal');
check(mover('deshacer'),'Undo after redo');
let nuevo;editar(r=>{nuevo=top.agregarElementoRed(r,'volumen');});
check(nuevo!==vid&&!hist.puedeRehacer,'Branching clears redo and reserves identities');

// Undoing an addition cannot make its IDs available to a different new element.
for(const tipo of ['volumen','corriente','calor','componente']){
  doc=structuredClone(hojas[0]);hist=new HistorialEdicionRed();let primero,segundo;
  editar(r=>{primero=tipo==='componente'?agregarComponenteRed(r,'Prueba','',[],99):top.agregarElementoRed(r,tipo);});
  mover('deshacer');
  editar(r=>{segundo=tipo==='componente'?agregarComponenteRed(r,'Otro','',[],99):top.agregarElementoRed(r,tipo);});
  check(primero!==segundo,`No ${tipo} identity alias after branching`);
}

// Typing in one field groups keystrokes; another focus session starts a new edit.
doc=structuredClone(hojas[0]);hist=new HistorialEdicionRed();
const tf=doc.redTermodinamica.solicitud.estudio.tiempoId,inicial=doc.redTermodinamica.solicitud.datos[tf].declaracion.texto;
for(const texto of ['6','60','600'])editar(r=>{r.solicitud.datos[tf].declaracion.texto=texto;},`dato:${tf}`);
mover('deshacer');check(doc.redTermodinamica.solicitud.datos[tf].declaracion.texto===inicial&&!hist.puedeDeshacer,'One undo restores the field before typing');
mover('rehacer');check(doc.redTermodinamica.solicitud.datos[tf].declaracion.texto==='600','Redo restores the complete entry');
hist.terminarGrupo();editar(r=>{r.solicitud.datos[tf].declaracion.texto='700';},`dato:${tf}`);mover('deshacer');
check(doc.redTermodinamica.solicitud.datos[tf].declaracion.texto==='600','Separate focus session has its own undo');

// A failed save must not consume history; another window's edits invalidate it.
const previo=structuredClone(doc.redTermodinamica),puede=hist.puedeDeshacer;
rechaza(()=>hist.mover(doc.redTermodinamica,'deshacer',()=>{throw new Error('QuotaExceeded');}));
check(hist.puedeDeshacer===puede&&JSON.stringify(doc.redTermodinamica)===JSON.stringify(previo),'Persistence failure is atomic');
const externa=structuredClone(doc.redTermodinamica);externa.solicitud.datos[tf].declaracion.texto='EXTERNA';
check(!hist.vigente(externa),'External edit recognized');hist.sincronizar(externa);
check(!hist.puedeDeshacer&&!hist.puedeRehacer,'External changes cannot be overwritten by stale undo');

doc=structuredClone(hojas[0]);hist=new HistorialEdicionRed(30);
for(let i=0;i<50;i++)editar(r=>{r.solicitud.datos[tf].declaracion.texto=String(i);});
let pasos=0;while(mover('deshacer'))pasos++;
check(pasos===30&&doc.redTermodinamica.solicitud.datos[tf].declaracion.texto==='19','History remains bounded');
// Pruned historical snapshots still have working redo after normalization.
doc=structuredClone(hojas[0]);doc.redTermodinamica.solicitud.datos.huerfano={...structuredClone(Object.values(doc.redTermodinamica.solicitud.datos)[0])};hist=new HistorialEdicionRed();
editar(r=>{r.solicitud.datos[tf].declaracion.texto='10';});mover('deshacer');
check(hist.puedeRehacer&&mover('rehacer'),'Normalization during undo does not destroy redo');

// Changing physical data expires the result; undo never resurrects a result pointer.
doc={...structuredClone(hojas[0]),resultadoRef:{firma:'antigua',estado:'resuelto',fecha:'2026-10-15'}};hist=new HistorialEdicionRed();
editar(r=>{r.solicitud.datos[tf].declaracion.texto='12';});mover('deshacer');
check(!doc.resultadoRef,'Configuration undo does not claim to have re-solved the system');

// Delayed asynchronous completions cannot publish or clear a newer request.
const control=new ControlOperacionRed(),op1=control.iniciar(),op2=control.iniciar();
check(op1.controller.signal.aborted&&!control.vigente(op1),'Superseded HTTP request aborted');
check(!control.finalizar(op1)&&control.vigente(op2),'Old finally does not clear the new request');
control.cancelar();check(!control.vigente(op2),'Cancelled request cannot publish');
const op3=control.iniciar();check(!control.finalizar(op2)&&control.vigente(op3),'Cancel and retry remains isolated');
check(control.finalizar(op3)&&!control.vigente(op3),'Only the latest completion clears itself');
const publicaciones=[];const old=control.iniciar();control.cancelar();const current=control.iniciar();
for(const op of [old,current,old])if(control.vigente(op))publicaciones.push(op);
check(publicaciones.length===1&&publicaciones[0]===current,'Late responses never enter publication');

// Deterministic IndexedDB lifecycle: cancel before opening, while opening and before commit.
const almacen=cargar('resultadosMotor');
function dbSimulada(){
  const f={aperturas:0,cierres:0,tx:null,guardados:[],apertura:null};
  f.api={open(){f.aperturas++;const r={result:{close(){f.cierres++;},transaction(){const t={abort(){t.abortada=true;queueMicrotask(()=>t.onabort?.());},objectStore(){return {put(v,k){t.valor=v;t.clave=k;f.tx=t;}};}};return t;}}};f.apertura=r;return r;}};
  f.abrir=()=>f.apertura.onsuccess();f.commit=()=>{if(!f.tx.abortada){f.guardados.push(f.tx.valor);f.tx.oncomplete();}};
  return f;
}
const abortado=new AbortController();abortado.abort();let fake=dbSimulada();globalThis.indexedDB=fake.api;
checks++;await assert.rejects(almacen.guardarResultadoMotor('qa',{firma:'f'},abortado.signal),{name:'AbortError'});check(fake.aperturas===0,'Already aborted operation never opens storage');
fake=dbSimulada();globalThis.indexedDB=fake.api;let ctl=new AbortController(),p=almacen.guardarResultadoMotor('qa',{firma:'f'},ctl.signal);
ctl.abort();fake.abrir();checks++;await assert.rejects(p,{name:'AbortError'});check(fake.cierres===1&&fake.tx===null,'Abort while opening closes DB without starting transaction');
fake=dbSimulada();globalThis.indexedDB=fake.api;ctl=new AbortController();p=almacen.guardarResultadoMotor('qa',{firma:'f'},ctl.signal);fake.abrir();await Promise.resolve();
check(fake.tx!==null,'Write transaction started');ctl.abort();checks++;await assert.rejects(p,{name:'AbortError'});
check(fake.tx.abortada&&fake.guardados.length===0&&fake.cierres===1,'Abort before commit prevents stale result persistence');
fake=dbSimulada();globalThis.indexedDB=fake.api;p=almacen.guardarResultadoMotor('qa',{firma:'f'});fake.abrir();await Promise.resolve();fake.commit();await p;
check(fake.guardados.length===1&&fake.cierres===1,'Legacy writes without cancellation remain supported');
fake=dbSimulada();globalThis.indexedDB=fake.api;ctl=new AbortController();
p=almacen.guardarResultadoMotor('qa',{firma:'f'},ctl.signal);
const transaccion=fake.apertura.result.transaction;
let falloTx;
fake.apertura.result.transaction=()=>{falloTx=transaccion();falloTx.objectStore=()=>({put(){throw new DOMException('Unclonable','DataCloneError');}});return falloTx;};
fake.abrir();checks++;await assert.rejects(p,{name:'DataCloneError'});
check(falloTx.abortada&&fake.cierres===1,'Synchronous storage failure aborts transaction and closes DB');
delete globalThis.indexedDB;

if(process.argv.includes('--ui')){
  const ui=JSON.parse(fs.readFileSync('qa_edicion_red_2026_10_16/ejecucion-ui.json','utf8'));
  const previo=JSON.parse(fs.readFileSync('qa_catalogo_n_2026_10_15/ejecucion-ui.json','utf8'));
  cargar('lectorEnsamblajeV2').leerResolucionV2(ui.respuesta,ui.solicitud);
  igual({...ui.solicitud,solicitudId:''},{...previo.solicitud,solicitudId:''},'Browser undo restores the exact request, including units and component memberships');
  check(ui.respuesta.estado==='resuelto'&&ui.respuesta.resultados.certificacion.estado==='cumple','Browser resolves restored topology and publishes certification');
  check(ui.respuesta.validacion.recuento.datosFaltantes===0&&ui.respuesta.validacion.recuento.gradosLibertad===0,'Browser canonical count is complete');
  igual(ui.respuesta.resultados.series,previo.respuesta.resultados.series,'Browser rerun reproduces every original published series');
}

if(process.argv.includes('--servicio')){
  const previo=JSON.parse(fs.readFileSync('qa_catalogo_n_2026_10_15/ejecucion-ui.json','utf8'));
  doc=structuredClone(hojas[1]);doc.redTermodinamica={solicitud:structuredClone(previo.solicitud),nombres:{}};hist=new HistorialEdicionRed();
  const original=structuredClone(doc.redTermodinamica.solicitud);
  const dir='qa_edicion_red_2026_10_16';fs.mkdirSync(dir,{recursive:true});
  const lector=cargar('lectorEnsamblajeV2'),api=process.env.MOTOR_API??'http://localhost:8004';
  async function consultar(ruta,nombre){
    const solicitud=structuredClone(doc.redTermodinamica.solicitud);
    const resp=await fetch(`${api}/motor/ensamblajes/${ruta}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(solicitud),signal:AbortSignal.timeout(180000)});
    check(resp.ok,`${nombre}: HTTP`);const respuesta=await resp.json();
    fs.writeFileSync(`${dir}/${nombre}.json`,JSON.stringify({solicitud,respuesta},null,2));
    if(ruta==='validar')lector.leerValidacionV2(respuesta,solicitud);else lector.leerResolucionV2(respuesta,solicitud);
    return respuesta;
  }
  let agregado;editar(r=>{agregado=top.agregarElementoRed(r,'volumen');});
  const incompleta=await consultar('validar','volumen-nuevo-pendiente');
  check(incompleta.recuento.estado==='incompleto','New volume stays pending instead of inheriting invented values');
  check(incompleta.recuento.datosFaltantes>0,'Missing data remain visible in the canonical count');
  check(mover('deshacer'),'Undo new volume before resolving');
  igual(doc.redTermodinamica.solicitud,original,'Restoration produces the original physical request');
  const validada=await consultar('validar','restaurado-validar');
  check(validada.recuento.estado==='listo','Restored system is ready after topology change');
  const resuelta=await consultar('resolver','restaurado-resolver');
  check(resuelta.estado==='resuelto'&&resuelta.resultados.certificacion.estado==='cumple','Restored system resolves and is certified');
  const s=doc.redTermodinamica.solicitud,r=resuelta.resultados;
  check(!r.estados[agregado],'Retired volume does not leak into evaluated states');
  const H=s.volumenes.map(v=>r.series.find(x=>x.variableId===`volumen.${v.id}.H`).valores);
  for(let k=0;k<H[0].length;k++)check(Math.abs(H.reduce((sum,x)=>sum+x[k]-x[0],0))<1e-5,'Internal exchange cancels in total enthalpy after restoring');
  for(const v of s.volumenes){
    for(const id of v.componenteIds)check(r.series.find(x=>x.variableId===`volumen.${v.id}.n.${id}`).valores.every(n=>Math.abs(n-1)<1e-10),'Component inventory conserved after edit/undo');
    const actual=r.series.find(x=>x.variableId===`volumen.${v.id}.T`).valores;
    const antes=previo.respuesta.resultados.series.find(x=>x.variableId===`volumen.${v.id}.T`).valores;
    igual(actual,antes,'Unchanged physical request reproduces the previous trajectory');
  }
}

console.log(`${checks} comprobaciones: paquetes compartidos, topología, deshacer/rehacer, identidades, persistencia y carreras de cancelación.${process.argv.includes('--servicio')?' Incluye validación y resolución reales del sistema restaurado.':' Sin ejecutar física.'} Sin modificar el backend.`);
