// Original delivery fixtures plus optional real HTTP. Does not recompute a flash.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url),cache=new Map(),dir='../docs/ejemplos/motor-unifac/';
function cargar(n){
  if(n.endsWith('.json'))return JSON.parse(fs.readFileSync(`app/motor/${n}`,'utf8'));
  if(n.endsWith('.css'))return {};
  if(cache.has(n))return cache.get(n);
  const f=['ts','tsx'].map(ext=>`app/motor/${n}.${ext}`).find(f=>fs.existsSync(f));
  const m={exports:{}};cache.set(n,m.exports);
  new Function('exports','module','require',ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText)(m.exports,m,id=>id.startsWith('./')?cargar(path.posix.join(path.posix.dirname(n),id)):require(id));return m.exports;
}
execFileSync(process.execPath,['sincronizar_ejemplos_unifac.mjs','--check'],{stdio:'inherit'});
execFileSync(process.execPath,['verificar_paquetes_entregados.mjs','--directorio',dir],{stdio:'inherit'});
let checks=0;const check=(v,m)=>{checks++;assert.ok(v,m);},igual=(a,b,m)=>{checks++;assert.deepEqual(a,b,m);};
const leer=f=>JSON.parse(fs.readFileSync(dir+f,'utf8'));
const red=cargar('lectorEnsamblajeV2'),diag=cargar('lectorDiagramasEquilibrio'),termo=cargar('contratoTermodinamica');
const cap=red.leerCapacidadesV2(leer('motor-ensamblaje-v2-capacidades.json')),cd=diag.leerCapacidadesDiagramas(leer('motor-diagramas-capacidades.json'));
const modelos=['unifac-original-public','unifac-dortmund-public','unifac-original-lle-public'];
const {crearHojasPruebaUNIFAC}=cargar('hojasPruebaUNIFAC'),hojas=crearHojasPruebaUNIFAC(),ejemplos=cargar('ejemplosUNIFAC.json');
const {restriccionComponenteRed:restriccion,avisoDominioDatoRed:aviso}=cargar('alcanceEdicionPaquete');
const Cobertura=cargar('CoberturaGruposPaquete').default,Editor=cargar('EditorComponentesRed').default;
for(const id of modelos){
  const p=cap.paquetes.find(p=>p.modelo.id===id),d=cd.paquetes.find(p=>p.modelo.id===id);
  check(p&&d,'Package published in both operations');igual(p.coberturaGrupos,d.coberturaGrupos,'Same group data across routes');
  check(p.pares===undefined&&d.pares===null,'No molecular pairs fabricated');
  check(p.combinaciones.filter(c=>['liquido_vapor','liquido_liquido'].includes(c.id)).every(c=>c.evidencia==='cualitativa'),'Predictive evidence retained');
  const html=renderToStaticMarkup(React.createElement(Cobertura,{cobertura:p.coberturaGrupos,componentes:leer('motor-termodinamica-unifac-7-lv-peticion.json').componentes}));
  check(html.includes(p.coberturaGrupos.datos.sha256_interacciones)&&html.includes(p.coberturaGrupos.datos.sha256_asignaciones),'Original table hashes rendered');
  check(!html.includes('<details open'),'Sources closed initially');
}
const lle=cap.paquetes.find(p=>p.modelo.id===modelos[2]);
igual(lle.dominio.T,[283.15,313.15],'ELL data temperature domain');
check(lle.componentesCAS.length===lle.coberturaGrupos.especies.length&&!lle.componentesCAS.includes('67-56-1')&&lle.coberturaGrupos.especiesSinAsignacion.includes('67-56-1'),'Admitted ELL catalog matches its published assignments; methanol excluded without substitution');
check(new Set(cap.paquetes.filter(p=>modelos.includes(p.modelo.id)).map(p=>p.coberturaGrupos.datos.sha256_interacciones)).size===3,'Independent table identities');
for(const [i,h] of hojas.entries()){
  const original=leer(ejemplos[i].fuente),s=h.redTermodinamica.solicitud;
  igual({...s,solicitudId:original.solicitudId},original,'Worksheet is input-only original request');
  check(!h.resultado&&!h.resultadoRef,'No preloaded answers');
  const respuesta=leer(ejemplos[i].fuente.replace('-peticion','-respuesta'));
  check(respuesta.resultados.certificacion.estado==='cumple','Original trajectory certified');
  check(respuesta.resultados.procedenciaModelo.every(p=>p.huella),'Original executed fingerprints');
}
const prueba=structuredClone(hojas.find(h=>h.id.endsWith('lle-mezcla')).redTermodinamica),v=prueba.solicitud.volumenes[0];
const antes=JSON.stringify(prueba);
check(restriccion(prueba,v.id,'67-56-1',cap.paquetes)==='Sin asignación en esta tabla','Known absence is specific');
check(restriccion(prueba,v.id,'7732-18-5',cap.paquetes)===null,'Covered species allowed');
check(restriccion(prueba,v.id,'67-64-1',cap.paquetes)===null,'Acetone is admitted by the newly published pure-property catalog');
check(restriccion(prueba,v.id,'110-54-3',cap.paquetes)!==null,'Groups do not extend pure-property catalog to unregistered hexane');
check(restriccion(prueba,v.id,undefined,cap.paquetes)===null,'Symbolic drafting remains possible');
const otro=structuredClone(prueba);otro.solicitud.paquetes[0].modelo={id:modelos[0],version:'1'};
check(restriccion(otro,v.id,'67-56-1',cap.paquetes)===null,'Methanol remains available with a different explicitly chosen package');
const distinta=structuredClone(prueba);distinta.solicitud.paquetes[0].modelo.version='no-publicada';
check(restriccion(distinta,v.id,'67-56-1',cap.paquetes)===null,'No metadata borrowed from another version');
const t=v.inicial.energia.datoId;
for(const [texto,unidad,valido] of [['10','degC',true],['40','degC',true],['41','degC',false],['283.15','K',true],['314','K',false],['50','degF',true],['104','degF',true],['105','degF',false]]){
  const s=structuredClone(prueba.solicitud);s.datos[t].declaracion={texto,unidad};check(!!aviso(s,t,cap.paquetes)!==valido,`Thermal domain with units ${texto} ${unidad}`);
}
const expresion=structuredClone(prueba.solicitud);expresion.datos[t].declaracion={texto:'t+300',unidad:'K'};
check(aviso(expresion,t,cap.paquetes)===null,'No local trajectory inference');
const invalida=structuredClone(prueba.solicitud);invalida.datos[t].declaracion.texto='';check(aviso(invalida,t,cap.paquetes)===null,'Blank stays pending');
igual(JSON.stringify(prueba),antes,'Restrictions do not mutate input values');
const meth={id:88,nombre:'Metanol de QA',identidadQuimica:{cas:'67-56-1'}};prueba.solicitud.componentes.push(meth);
const html=renderToStaticMarkup(React.createElement(Editor,{red:prueba,maximo:7,paquetes:cap.paquetes,cambiar(){return false;}}));
check(/aria-label="Metanol de QA en Volumen A"[^>]*disabled=""/.test(html),'New disallowed membership disabled');
prueba.solicitud.volumenes[0].componenteIds.push(88);
const existente=renderToStaticMarkup(React.createElement(Editor,{red:prueba,maximo:7,paquetes:cap.paquetes,cambiar(){return false;}}));
check(!/aria-label="Metanol de QA en Volumen A"[^>]*disabled=""/.test(existente),'Existing incompatible membership can be removed');
check(prueba.solicitud.volumenes[0].componenteIds.includes(88),'No automatic deletion of existing quantities');

if(process.argv.includes('--servicio')){
  const destino='.tmp/qa-unifac-servicio';fs.mkdirSync(destino,{recursive:true});
  async function http(ruta,s,nombre){
    const r=await fetch(`http://localhost:8004${ruta}`,{method:s?'POST':'GET',headers:s?{'Content-Type':'application/json'}:undefined,body:s?JSON.stringify(s):undefined,signal:AbortSignal.timeout(600000)});
    check(r.ok,'HTTP '+ruta);const raw=await r.json();fs.writeFileSync(`${destino}/${nombre}.json`,JSON.stringify(raw,null,2)+'\n');return raw;
  }
  const c=red.leerCapacidadesV2(await http('/motor/ensamblajes/capacidades?revision=2',null,'capacidades'));
  for(const id of modelos)check(c.paquetes.some(p=>p.modelo.id===id&&p.coberturaGrupos),'Live variant published');
  for(const n of ['unifac-7-lv','unifac-dortmund-4-lv','unifac-lle-6-ll','rechazo-unifac-lle-metanol-sin-grupo','rechazo-unifac-lle-fuera-de-dominio']){
    const s=leer(`motor-termodinamica-${n}-peticion.json`),r=await http('/motor/termodinamica/evaluar',s,n);
    termo.validarRespuestaEstado(r,s);checks++;check(r.estado===leer(`motor-termodinamica-${n}-respuesta.json`).estado,'Live point/rejection status');console.log('HTTP estado: '+n+' · '+r.estado);
  }
  for(const id of ['red-5','dortmund-4','lle-mezcla']){
    const fuente=ejemplos.find(e=>e.id===id).fuente,s=leer(fuente);
    const validacion=red.leerValidacionV2(await http('/motor/ensamblajes/validar',s,`${id}-validar`),s);checks++;
    check(validacion.recuento.gradosLibertad===0&&validacion.inicializacion.estado==='compatible','Live assembly initialized');
    console.log('HTTP resolver: '+id);
    const r=red.leerResolucionV2(await http('/motor/ensamblajes/resolver',s,`${id}-resolver`),s,validacion.modeloId);checks++;
    check(r.resultados?.certificacion.estado==='cumple','Live trajectory certified');console.log('HTTP resuelto: '+id+' · '+r.resultados.tiempos.length+' muestras');
  }
  const s=leer('motor-diagramas-txy-etanol-agua-unifac-peticion.json'),r=await http('/motor/termodinamica/diagramas/trazar',s,'txy-original');
  diag.leerDiagramaEquilibrio(r,s);checks++;check(r.puntos.length>0,'Live diagram has certified points');
}
console.log(`${checks} comprobaciones específicas UNIFAC OK. No reemplaza el contraste físico de Claude; no modifica sus ejemplos.`);
