// Metadata, UI and invalidation only. Synthetic model IDs below do not enable a package.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url),cache=new Map();
function cargar(n){
  if(n.endsWith('.json'))return JSON.parse(fs.readFileSync(`app/motor/${n}`,'utf8'));
  if(n.endsWith('.css'))return {};
  if(cache.has(n))return cache.get(n);
  const f=['ts','tsx'].map(ext=>`app/motor/${n}.${ext}`).find(f=>fs.existsSync(f));if(!f)throw new Error(`Módulo no encontrado: ${n}`);
  const m={exports:{}};cache.set(n,m.exports);
  new Function('exports','module','require',ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText)(m.exports,m,id=>id.startsWith('./')?cargar(path.posix.join(path.posix.dirname(n),id)):require(id));
  return m.exports;
}
let checks=0;const check=(x,m)=>{checks++;assert.ok(x,m);},igual=(a,b,m)=>{checks++;assert.deepEqual(a,b,m);},rechaza=f=>{checks++;assert.throws(f);};
const {claveModelo,mismoModelo,opcionesModelos,modeloElegido}=cargar('modelosTermodinamicos');
const original={id:'modelo-A',version:'1'},revision={id:'modelo-A',version:'2'},variante={id:'modelo-B',version:'1'};
const publicados=[original,revision,variante].map(modelo=>({modelo,disponible:true})),antes=JSON.stringify(publicados);
const opciones=opcionesModelos(publicados,revision);
check(new Set(opciones.map(p=>p.clave)).size===3,'Model/version pairs are independent options');
check(opciones.every(p=>p.etiqueta.includes(`v${p.modelo.version}`)),'Versions are visible in every selection');
igual(modeloElegido(opciones,claveModelo(revision)),revision,'Explicit revision is selected instead of first matching ID');
check(!mismoModelo(original,revision)&&!mismoModelo(original,variante),'Variant and revision are both physical identity changes');
check(claveModelo({id:'a:b',version:'c'})!==claveModelo({id:'a',version:'b:c'}),'Delimited IDs cannot alias');
const desaparecido={id:'modelo-retirado',version:'3'},sinPublicar=opcionesModelos(publicados,desaparecido);
const guardado=sinPublicar.find(p=>p.guardadoSinPublicar);
igual(guardado.modelo,desaparecido,'Unavailable saved model remains visible without migration');
check(!guardado.disponible&&modeloElegido(sinPublicar,guardado.clave)===null,'An unpublished saved model cannot act as a published capability');
check(opcionesModelos([],desaparecido,false)[0].etiqueta.includes('catálogo sin cargar'),'Loading and unpublished catalogs are distinguished');
check(modeloElegido(opciones,'valor-ajeno')===null&&modeloElegido(opciones,'')===null,'No first-model fallback');
check(!modeloElegido(opcionesModelos([{modelo:original,disponible:false}],original),claveModelo(original)),'Static-only package cannot be selected for a dynamic operation');
rechaza(()=>opcionesModelos([...publicados,publicados[0]]));
rechaza(()=>opcionesModelos([{modelo:{id:'x',version:''},disponible:true}]));
const elegido=modeloElegido(opciones,claveModelo(revision));elegido.version='otra';
check(opciones[1].modelo.version==='2'&&JSON.stringify(publicados)===antes,'Neither input catalog nor option identities are mutable aliases');
const Selector=cargar('SelectorModeloTermodinamico').default;
const html=renderToStaticMarkup(React.createElement(Selector,{actual:desaparecido,publicados,catalogoCargado:true,nombre:'Paquete',elegir(){throw new Error('SSR cannot select');}}));
check(html.includes('guardado; no publicado')&&html.includes('selected=""'),'Saved unavailable selection is shown rather than a placeholder or different model');
check(!html.includes('unifac'),'No unpublished UNIFAC option is fabricated');
const htmlRevision=renderToStaticMarkup(React.createElement(Selector,{actual:revision,publicados,catalogoCargado:true,nombre:'Paquete',elegir(){}}));
check(htmlRevision.includes('modelo-A · v2'),'Selected revision remains legible');

const lector=cargar('lectorEnsamblajeV2'),leer=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const cap=leer('../docs/ejemplos/motor-n-componentes/motor-ensamblaje-v2-capacidades.json');
const dosVersiones=structuredClone(cap);dosVersiones.paquetes.push({...structuredClone(cap.paquetes[0]),modelo:{...cap.paquetes[0].modelo,version:'2'}});
lector.leerCapacidadesV2(dosVersiones);checks++;
const duplicada=structuredClone(cap);duplicada.paquetes.push(structuredClone(cap.paquetes[0]));rechaza(()=>lector.leerCapacidadesV2(duplicada));
const termo=cargar('contratoTermodinamica'),puntuales=leer('../docs/ejemplos/motor-termodinamica-capacidades.json');
const p2=structuredClone(puntuales);p2.modelos.push({...structuredClone(p2.modelos[0]),version:'otra'});termo.validarCapacidadesEstado(p2);checks++;
const pd=structuredClone(puntuales);pd.modelos.push(structuredClone(pd.modelos[0]));rechaza(()=>termo.validarCapacidadesEstado(pd));
const ld=cargar('lectorDiagramasEquilibrio'),dc=leer('../docs/ejemplos/motor-diagramas/motor-diagramas-capacidades.json');
const d2=structuredClone(dc);d2.paquetes.push({...structuredClone(d2.paquetes[0]),modelo:{...d2.paquetes[0].modelo,version:'otra'}});ld.leerCapacidadesDiagramas(d2);checks++;
const dd=structuredClone(dc);dd.paquetes.push(structuredClone(dd.paquetes[0]));rechaza(()=>ld.leerCapacidadesDiagramas(dd));

// Published catalog metadata is authoritative but must have its declared shape.
// These probes exercise the protocol, not physical support for new substances.
const lectores=[
  {base:cap,leer:lector.leerCapacidadesV2,paquete:c=>c.paquetes.find(p=>!p.modelo.id.startsWith('unifac-')),operaciones:'operaciones',operacion:'TP'},
  {base:puntuales,leer:termo.validarCapacidadesEstado,paquete:c=>c.modelos[0],operaciones:'especificaciones',operacion:'TP'},
  {base:dc,leer:ld.leerCapacidadesDiagramas,paquete:c=>c.paquetes.find(p=>!p.modelo.id.startsWith('unifac-')),operaciones:'operaciones',operacion:'Txy'},
];
for(const l of lectores){
  const original=JSON.stringify(l.base);
  for(const cas of ['64-17-5',[42],[''],['   '],['64-17-5','64-17-5']]){
    const c=structuredClone(l.base);l.paquete(c).componentesCAS=cas;rechaza(()=>l.leer(c));
  }
  for(const rango of [[NaN,500],[1,Infinity],[0,500],[-1,500],[500,300],[300,300],[300],[300,500,600],'300–500'])for(const k of ['T','P']){
    const c=structuredClone(l.base);l.paquete(c).dominio[k]=rango;rechaza(()=>l.leer(c));
  }
  for(const dominio of [null,[],{T:[300,500]},'dominio']){
    const c=structuredClone(l.base);l.paquete(c).dominio=dominio;rechaza(()=>l.leer(c));
  }
  for(const ops of [['inventada'],[l.operacion,l.operacion],['   '],l.operacion]){
    const c=structuredClone(l.base);l.paquete(c)[l.operaciones]=ops;rechaza(()=>l.leer(c));
  }
  for(const fases of [['desconocida'],['liquido','liquido'],['   '],'liquido']){
    const c=structuredClone(l.base);l.paquete(c).fases=fases;rechaza(()=>l.leer(c));
  }
  // No hardcoded catalog size or model identity: larger catalogs remain data.
  for(const n of [8,12,25]){
    const c=structuredClone(l.base),p=l.paquete(c);
    p.componentesCAS=Array.from({length:n},(_,i)=>`identidad-publicada-${i}`);
    if(p.modelo)p.modelo={id:'paquete-futuro',version:'otra'};else {p.id='paquete-futuro';p.version='otra';}
    igual(l.leer(c),c,'Reader preserves a structurally valid future catalog without a substance or model whitelist');
  }
  igual(JSON.stringify(l.base),original,'Capability checks never normalize or mutate their input');
}
for(const limite of [-1,0,1.5,Infinity,NaN,Number.MAX_SAFE_INTEGER+1])for(const k of ['componentesMaximos','volumenesMaximos']){
  const c=structuredClone(cap);delete c.tamanos;c.disponible=true;c[k]=limite;rechaza(()=>lector.leerCapacidadesV2(c));
}
const historica=structuredClone(cap);delete historica.tamanos;
for(const p of historica.paquetes)for(const k of ['componentesCAS','dominio','limites','pares'])delete p[k];
// Use the pre-UNIFAC fixture: its optional fields were not required by revision 2.
igual(lector.leerCapacidadesV2(historica),historica,'Historical v2 may omit optional coverage metadata');
const inactiva=structuredClone(historica);inactiva.disponible=false;inactiva.componentesMaximos=0;inactiva.volumenesMaximos=0;
igual(lector.leerCapacidadesV2(inactiva),inactiva,'An unavailable service may advertise zero capacity');
for(const cas of [null,42]){const c=structuredClone(cap);c.paquetes[0].componentesCAS=cas;rechaza(()=>lector.leerCapacidadesV2(c));}
const sinRestriccion=structuredClone(puntuales);sinRestriccion.modelos[0].componentesCAS=null;
igual(termo.validarCapacidadesEstado(sinRestriccion),sinRestriccion,'Point contract explicitly permits an unrestricted null catalog');
for(const l of [lectores[0],lectores[2]])for(const limites of ['texto',[42],['   ']]){
  const c=structuredClone(l.base);l.paquete(c).limites=limites;rechaza(()=>l.leer(c));
}
// Parameter availability is distinct from admission of a pure substance.
const paresAparte=structuredClone(cap),par=paresAparte.paquetes.find(p=>p.pares?.length);
check(!!par,'Real package publishes molecular pairs');
par.componentesCAS=['catalogo-distinto'];lector.leerCapacidadesV2(paresAparte);checks++;
const parRepetido=structuredClone(paresAparte),pr=parRepetido.paquetes.find(p=>p.pares?.length);
pr.pares[0].componentesCAS=['64-17-5','64-17-5'];rechaza(()=>lector.leerCapacidadesV2(parRepetido));
// All stored endpoint capability responses, including UNIFAC, still pass unchanged.
const capacidadesReales=[];
function recorrer(d){for(const e of fs.readdirSync(d,{withFileTypes:true})){const f=path.join(d,e.name);if(e.isDirectory())recorrer(f);else if(e.name.endsWith('.json')&&e.name.includes('capacidades'))capacidadesReales.push(f);}}
recorrer('../docs/ejemplos');
let reales=0;const protocolosLeidos=new Set();
for(const f of capacidadesReales){
  const c=leer(f);let lectorReal;
  if(c.revision===2&&Array.isArray(c.paquetes)&&'volumenesMaximos'in c)lectorReal=lector.leerCapacidadesV2;
  else if(c.revision===1&&Array.isArray(c.modelos)&&!('balances'in c))lectorReal=termo.validarCapacidadesEstado;
  else if(c.revision===1&&c.trazador&&Array.isArray(c.paquetes))lectorReal=ld.leerCapacidadesDiagramas;
  if(lectorReal){const antes=JSON.stringify(c);try{igual(lectorReal(c),c,`Real response: ${f}`);}catch(e){throw new Error(`Capability fixture ${f}: ${e.message}`,{cause:e});}igual(JSON.stringify(c),antes,'Published metadata remains unchanged');reales++;protocolosLeidos.add(lectorReal);}
}
check(protocolosLeidos.size===3&&reales>protocolosLeidos.size,'Compatibility covers all three protocols and multiple deliveries');

// A package change invalidates dynamic results; aliases of shared packages stay isolated.
const {cambiarRed}=cargar('redTermodinamica'),{elegirPaqueteVolumen}=cargar('topologiaRed'),{firmaHoja}=cargar('modeloHojaMotor');
const base=cargar('hojasPruebaMultifasico').crearHojasPruebaMultifasico()[1];
const h={...base,resultadoRef:{firma:firmaHoja(base),estado:'resuelto',fecha:'2026-10-16'}};
for(const m of [{id:'mezcla-ideal',version:'2'},variante]){
  const nuevo=cambiarRed(h,r=>elegirPaqueteVolumen(r,'A',m));
  check(!nuevo.resultadoRef&&firmaHoja(nuevo)!==firmaHoja(h),'Model or version changes expire the result and signature');
  igual(nuevo.redTermodinamica.solicitud.volumenes.find(v=>v.id==='B'),h.redTermodinamica.solicitud.volumenes.find(v=>v.id==='B'),'Other volume is unchanged');
}
const mismo=cambiarRed(h,r=>{const v=r.solicitud.volumenes.find(v=>v.id==='A');elegirPaqueteVolumen(r,'A',r.solicitud.paquetes.find(p=>p.id===v.paqueteId).modelo);});
check(mismo.resultadoRef===h.resultadoRef,'Selecting the same model leaves current results intact');

// Cache must distinguish variant, model revision and parameter fingerprint independently.
const dir='../docs/ejemplos/motor-diagramas/';
const file=fs.readdirSync(dir).find(f=>f.endsWith('-peticion.json')&&fs.existsSync(dir+f.replace('-peticion','-respuesta'))&&leer(dir+f.replace('-peticion','-respuesta')).estado==='completo');
const s=leer(dir+file),r=leer(dir+file.replace('-peticion','-respuesta'));
const {MemoriaDiagramas}=cargar('datosDiagramaEquilibrio'),memoria=new MemoriaDiagramas();
const solicitud={...s,huellaModeloEsperada:r.identidad.huellaModelo};memoria.guardar(solicitud,r);
check(!!memoria.recuperar(solicitud,r.identidad.trazador),'Actual complete diagram is cacheable');
for(const cambio of [{modelo:{...s.modelo,version:'nueva'}},{modelo:{id:'otra-variante',version:s.modelo.version}},{huellaModeloEsperada:'sha256:otra-tabla'}])check(!memoria.recuperar({...solicitud,...cambio},r.identidad.trazador),'Different variant, revision or data never reuses an old diagram');

// The technical provenance table uses the actual saved response and no current catalog.
const prefijo='../docs/ejemplos/motor-v2/motor-ensamblaje-v2-resolver-contacto-dos-aguas';
const saved={solicitud:leer(prefijo+'-peticion.json'),respuesta:leer(prefijo+'-respuesta.json')},prueba=structuredClone(saved),originalJSON=JSON.stringify(prueba);
const Paquetes=cargar('PaquetesEjecutadosRed').default;
const tabla=renderToStaticMarkup(React.createElement(Paquetes,{ejecucion:prueba}));
for(const p of saved.respuesta.resultados.procedenciaModelo)check(tabla.includes(p.huella),'Original data fingerprint is visible in technical references');
check(tabla.includes('Identidades y masas molares usadas'),'Executed material identity is inspectable in existing technical references');
for(const estados of Object.values(saved.respuesta.resultados.estados))for(const c of estados[0].evaluacion.componentes){
  check(tabla.includes(c.cas)&&tabla.includes(c.fuente),'Published identity and source retained per volume');
  check(tabla.includes(cargar('formatearNumeroMotor').formatearNumeroMotor(c.masaMolarKgMol,12)),'Actual molar mass shown without rounding to an input default');
}
// Presentation-only metadata probes: preserve distinct declaration units/source
// and join by component ID even when the saved evaluation order differs.
const declara=structuredClone(saved),comp=declara.solicitud.componentes[0];
comp.masaMolar={cantidad:{valor:18.015268,unidad:'g/mol'},fuente:'Declaración original de QA'};
const declarada=renderToStaticMarkup(React.createElement(Paquetes,{ejecucion:declara}));
check(declarada.includes('18.015268')&&declarada.includes('g/mol')&&declarada.includes('Declaración original de QA'),'Declared value, unit and source stay separate from evaluated kg/mol');
check(JSON.stringify(saved)===originalJSON,'Inspection does not fill in user declarations');
// Locate an actual multicomponent fixture without depending on its file suffix.
const ndir='../docs/ejemplos/motor-unifac/',nf=fs.readdirSync(ndir).find(f=>f.endsWith('-peticion.json')&&f.includes('-resolver-')&&leer(ndir+f).volumenes.some(v=>v.componenteIds.length>=4));
check(!!nf,'Actual N-component execution is available');
const nSaved={solicitud:leer(ndir+nf),respuesta:leer(ndir+nf.replace('-peticion','-respuesta'))};
const orden=structuredClone(nSaved);for(const estados of Object.values(orden.respuesta.resultados.estados))estados[0].evaluacion.componentes.reverse();
igual(renderToStaticMarkup(React.createElement(Paquetes,{ejecucion:orden})),renderToStaticMarkup(React.createElement(Paquetes,{ejecucion:nSaved})),'Component IDs, not array positions, select executed masses and sources');
delete prueba.respuesta.resultados.procedenciaModelo;
const historico=renderToStaticMarkup(React.createElement(Paquetes,{ejecucion:prueba}));
check(historico.includes('No publicada en esta ejecución'),'Historical response does not invent a fingerprint');
const sinEstado=structuredClone(saved);delete sinEstado.respuesta.resultados.estados;
// The complete reader requires states. Test this display component's missing-data
// branch without treating the synthetic fragment as a valid backend response.
sinEstado.respuesta.resultados.estados={};
const incompleta=renderToStaticMarkup(React.createElement(Paquetes,{ejecucion:sinEstado}));
check(incompleta.includes('No publicada')&&!incompleta.includes('0.018015268'),'Missing evaluation does not infer a molar mass from CAS');
check(JSON.stringify(saved)===originalJSON,'Saved evidence remains unchanged');
console.log(`${checks} comprobaciones de integración, incluidos ${reales} catálogos reales: alcance publicado, modelo/versión, selección sin sustituciones, caducidad de resultados/caché, identidades y masas molares. No amplía capacidades físicas.`);
