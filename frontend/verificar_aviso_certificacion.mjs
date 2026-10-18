import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url),cache=new Map();
function cargar(n){
  if(n.endsWith('.css'))return {};
  if(cache.has(n))return cache.get(n);
  const f=['ts','tsx'].map(ext=>`app/motor/${n}.${ext}`).find(f=>fs.existsSync(f)),m={exports:{}};cache.set(n,m.exports);
  new Function('exports','module','require',ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText)(m.exports,m,id=>id.startsWith('./')?cargar(path.posix.join(path.posix.dirname(n),id)):require(id));return m.exports;
}
const lector=cargar('lectorEnsamblajeV2'),meta=cargar('metadatosRed'),Aviso=cargar('AvisoCertificacionRed').default;
let checks=0;const check=(v,m)=>{checks++;assert.ok(v,m);};
const leer=f=>JSON.parse(fs.readFileSync(f,'utf8'));
const casos=[
  ['qa_fiabilidad_motor_2026_10_16/nrtl-chemsep','parcial','no_cumple'],
  ['qa_fiabilidad_motor_2026_10_16/unifac-original-public','parcial','cumple'],
  ['qa_fiabilidad_motor_2026_10_16/mezcla-ideal','parcial','cumple'],
  ['qa_multifasico_2026_10_15/consolidacion/no-evaluable','resuelto','no_evaluable'],
];
for(const [base,estado,cert] of casos){
  const s=leer(`${base}-peticion.json`),archivo=fs.existsSync(`${base}-resolver-respuesta.json`)?`${base}-resolver-respuesta.json`:`${base}-respuesta.json`,raw=leer(archivo),antes=JSON.stringify(raw),r=lector.leerResolucionV2(raw,s),a=r.resultados;
  check(r.estado===estado,'Integration status retained independently');
  check(a.certificacion.estado===cert,'Original certificate retained');
  const html=renderToStaticMarkup(React.createElement(Aviso,{resultado:a,verDetalles(){}}));
  check(html.includes(`data-certificacion="${cert}"`),'Machine-readable original certification status');
  check(html.includes(cert==='no_cumple'?'role="alert"':'role="status"'),'Failed certification remains an accessible alert');
  check(html.includes('Ver certificación'),'Details remain reachable');
  check(!html.includes('incumplimiento físico'),'Banner does not invent a physical cause for a failed check');
  if(cert==='no_cumple'){
    check(html.includes('Trayectoria sin certificar · verificación no superada'),'Failure never presented as successful');
    check(a.certificacion.aspectos.find(x=>x.id==='cierre_constitutivo').referencias.includes('mecanica.A.trabajo'),'Actual failing equation remains inspectable');
    check(a.residuos.find(x=>x.ecuacionId==='mecanica.A.trabajo').maximoEscalado>1,'Original failed residual is not relaxed');
    const corte=meta.intervaloNoCertificado(a);
    check(corte[0]===a.tiempos[a.certificacion.ultimaMuestraCertificada]&&corte[1]===a.tiempos.at(-1),'Canonical cut retained including the failed terminal sample');
    check(a.series.every(x=>x.valores.length===a.tiempos.length),'No failed terminal evidence dropped');
  }else check(meta.intervaloNoCertificado(a)===null,'No failed-region overlay fabricated');
  check(JSON.stringify(raw)===antes,'Reading and rendering do not modify raw evidence');
}
const base='qa_fiabilidad_motor_2026_10_16/nrtl-chemsep',s=leer(`${base}-peticion.json`),r=leer(`${base}-resolver-respuesta.json`);
const falsa=structuredClone(r);falsa.resultados.certificacion.estado='cumple';checks++;assert.throws(()=>lector.leerResolucionV2(falsa,s));
const historica=structuredClone(r.resultados);delete historica.certificacion;
check(meta.resumenCertificacion(historica).includes('no disponible'),'Historical response never silently becomes certified');
const sinAprobadas=structuredClone(r.resultados);sinAprobadas.certificacion.ultimaMuestraCertificada=null;
const html=renderToStaticMarkup(React.createElement(Aviso,{resultado:sinAprobadas,verDetalles(){}}));
check(html.includes('sin muestras aprobadas; evidencia completa'),'Null canonical cut is explicitly represented');
check(meta.intervaloNoCertificado(sinAprobadas)[0]===sinAprobadas.tiempos[0],'Null cut starts at initial sample');
console.log(`${checks} comprobaciones del aviso: estados independientes, causa no inventada, evidencia íntegra, corte canónico y rechazo de certificación falsa.`);
