// Synthetic metadata exercises the contract and presentation only. These group
// assignments are NOT chemical data, are never installed in the app or sent to a flash.
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import ts from 'typescript';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url),cache=new Map();
function cargar(n){
  if(n.endsWith('.css'))return {};
  if(cache.has(n))return cache.get(n);
  const f=['ts','tsx'].map(ext=>`app/motor/${n}.${ext}`).find(f=>fs.existsSync(f));
  const m={exports:{}};cache.set(n,m.exports);
  new Function('exports','module','require',ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true}}).outputText)(m.exports,m,id=>id.startsWith('./')?cargar(path.posix.join(path.posix.dirname(n),id)):require(id));
  return m.exports;
}
let checks=0;const check=(v,m)=>{checks++;assert.ok(v,m);},igual=(a,b,m)=>{checks++;assert.deepEqual(a,b,m);},rechaza=(f,m)=>{checks++;assert.throws(f,undefined,m);};
const {leerCoberturaGrupos:leer,resumirCoberturaGrupos:resumir,nombreVarianteUNIFAC:nombre}=cargar('coberturaGrupos');
const original={tipo:'contribucion_de_grupos',variante:'original',datos:{variante:'original',fuente_interacciones:'Fixture · interacciones',sha256_interacciones:'a'.repeat(64),fuente_asignaciones:'Fixture · asignaciones',sha256_asignaciones:'b'.repeat(64),fuente_subgrupos:'Fixture · subgrupos'},
  especies:[{cas:'7732-18-5',subgrupos:[{id:1,nombre:'Fixture A',grupoPrincipal:10,cuenta:2}],procedencia:'Fixture A'},
    {cas:'64-17-5',subgrupos:[{id:2,nombre:'Fixture B',grupoPrincipal:20,cuenta:1}],procedencia:'Fixture B'},
    {cas:'67-56-1',subgrupos:[{id:3,nombre:'Fixture C',grupoPrincipal:30,cuenta:1}],procedencia:'Fixture C'}],
  especiesSinAsignacion:['71-43-2'],interaccionesDirigidasFaltantes:[[10,20],[20,10],[20,30]],nota:'Metadata ficticia, sin significado físico.'};
const catalogo=original.especies.map(e=>e.cas),antes=JSON.stringify(original);
igual(leer(original,catalogo),original,'Complete metadata returned intact');
check(leer(original)===original,'Reader does not normalize or replace the publication');
for(const v of ['original','dortmund','lle']){
  const c=structuredClone(original);c.variante=v;c.datos.variante=v;
  if(v==='lle'){c.datos.fuente_tabla='Fixture ELL';c.datos.rango_T_datos=[283.15,313.15];}
  check(leer(c).variante===v,'Each canonical variant is independent');
  check(nombre(v).includes(v==='lle'?'ELL':v==='dortmund'?'Dortmund':'original'),'Explicit variant label');
}
const invalidos=[
  c=>{c.tipo='otro';},c=>{c.variante='auto';},c=>{c.datos.variante='dortmund';},c=>{c.datos=null;},
  c=>{c.datos.fuente_interacciones=' ';},c=>{c.datos.fuente_asignaciones=null;},c=>{delete c.datos.fuente_subgrupos;},
  c=>{c.datos.sha256_interacciones='corto';},c=>{c.datos.sha256_asignaciones='z'.repeat(64);},
  c=>{c.datos.fuente_tabla='';},c=>{c.datos.rango_T_datos=[313,283];},c=>{c.datos.rango_T_datos=[283,Infinity];},
  c=>{c.especies=null;},c=>{c.especies.push(c.especies[0]);},c=>{c.especies[0].cas='sin CAS';},
  c=>{c.especies[0].procedencia='';},c=>{c.especies[0].subgrupos=[];},c=>{c.especies[0].subgrupos.push(c.especies[0].subgrupos[0]);},
  c=>{c.especies[0].subgrupos[0].id=0;},c=>{c.especies[0].subgrupos[0].grupoPrincipal=-1;},
  c=>{c.especies[0].subgrupos[0].cuenta=0;},c=>{c.especies[0].subgrupos[0].cuenta=1.5;},c=>{c.especies[0].subgrupos[0].nombre='';},
  c=>{c.especies[1].subgrupos[0].id=1;},c=>{c.especiesSinAsignacion.push('7732-18-5');},
  c=>{c.especiesSinAsignacion.push('71-43-2');},c=>{c.interaccionesDirigidasFaltantes=[[10,10]];},
  c=>{c.interaccionesDirigidasFaltantes=[[10,99]];},c=>{c.interaccionesDirigidasFaltantes.push([10,20]);},
  c=>{c.interaccionesDirigidasFaltantes=[[10]];},c=>{c.interaccionesDirigidasFaltantes=[[10,'20']];},c=>{c.nota='';}
];
for(const cambiar of invalidos){const c=structuredClone(original);cambiar(c);rechaza(()=>leer(c),String(cambiar));}
for(const x of [null,{},[],undefined])rechaza(()=>leer(x),'Incomplete publication rejected');
rechaza(()=>leer(original,[...catalogo,'108-88-3']),'Catalog species cannot be omitted');
rechaza(()=>leer(original,catalogo.slice(1)),'Coverage cannot invent catalog species');
rechaza(()=>leer(original,[...catalogo,catalogo[0]]),'Catalog duplicates rejected');
const cs=[...catalogo,...original.especiesSinAsignacion].map((cas,i)=>({id:i+1,nombre:`Fixture ${i+1}`,identidadQuimica:{cas}}));
const seleccion=resumir(original,cs.slice(0,2));
igual(seleccion.interaccionesFaltantes,[[10,20],[20,10]],'Directed pairs are distinct and filtered to selected principal groups');
igual(resumir(original,[cs[0]]).interaccionesFaltantes,[],'Other mixture missing data do not apply to a pure selection');
igual(seleccion.asignadas,2,'Assigned count');
igual(resumir(original,[cs[3]]).filas[0].estado,'sin_asignacion','Published lack of assignment');
igual(resumir(original,[{id:8,nombre:'Sin identificar'}]).filas[0].estado,'sin_identidad','No fake CAS');
igual(resumir(original,[{id:9,nombre:'Fuera',identidadQuimica:{cas:'108-88-3'}}]).filas[0].estado,'fuera_catalogo','Groups do not expand pure-property catalog');
igual(resumir(original,[...cs].reverse()).filas.map(f=>f.componente.id),[4,3,2,1],'Component IDs and user order retained');
igual(resumir(original,[]).asignadas,0,'Empty selection has no assigned species');
const unicoSentido=structuredClone(original);unicoSentido.interaccionesDirigidasFaltantes=[[20,10]];
igual(resumir(unicoSentido,cs.slice(0,2)).interaccionesFaltantes,[[20,10]],'Reverse parameter is not inferred');
const mismos=structuredClone(original);mismos.especies[1].subgrupos=structuredClone(mismos.especies[0].subgrupos);mismos.especies[1].subgrupos[0].cuenta=1;mismos.interaccionesDirigidasFaltantes=[];
check(leer(mismos),'A subgroup can appear with different counts in different molecules');
const Componente=cargar('CoberturaGruposPaquete').default;
const render=c=>renderToStaticMarkup(React.createElement(Componente,{cobertura:c,componentes:[...cs,{id:8,nombre:'Sin identificar'},{id:9,nombre:'Fuera',identidadQuimica:{cas:'108-88-3'}}]}));
const html=render(original);
for(const texto of ['UNIFAC original','2 × Fixture A (1)','10 → 20, 20 → 10','Identidad sin declarar','Sin asignación en esta tabla','Fuera del catálogo publicado','SHA-256','El estado y su estabilidad se comprueban al evaluar.'])check(html.includes(texto),'Visible coverage: '+texto);
check(!html.includes('<details open'),'Sources remain collapsed');
check(!html.includes('Certificación física · cumple'),'Coverage is not a physics certificate');
const escapado=structuredClone(original);escapado.especies[0].subgrupos[0].nombre='<script>dato</script>';
check(render(escapado).includes('&lt;script&gt;dato&lt;/script&gt;'),'Publication text is escaped');
const leerJson=f=>JSON.parse(fs.readFileSync(f,'utf8').replace(/^\uFEFF/,''));
const red=cargar('lectorEnsamblajeV2'),diagramas=cargar('lectorDiagramasEquilibrio');
const cap=leerJson('../docs/ejemplos/motor-n-componentes/motor-ensamblaje-v2-capacidades.json');
const capD=leerJson('../docs/ejemplos/motor-diagramas/motor-diagramas-capacidades.json');
const capAntes=JSON.stringify(cap),capDAntes=JSON.stringify(capD);
red.leerCapacidadesV2(cap);checks++;diagramas.leerCapacidadesDiagramas(capD);checks++;
const nueva=structuredClone(cap),p=nueva.paquetes[1];p.modelo={id:'unifac-fixture',version:'1'};p.combinaciones=p.combinaciones.map(c=>['liquido_vapor','liquido_liquido'].includes(c.id)?{...c,evidencia:'cualitativa'}:c);p.componentesCAS=catalogo;delete p.pares;p.coberturaGrupos=original;
red.leerCapacidadesV2(nueva);checks++;
const nuevaD=structuredClone(capD),pd=nuevaD.paquetes[0];pd.modelo=p.modelo;pd.componentesCAS=catalogo;pd.pares=null;pd.coberturaGrupos=original;
diagramas.leerCapacidadesDiagramas(nuevaD);checks++;
for(const cambiar of [x=>{x.datos.variante='dortmund';},x=>{x.interaccionesDirigidasFaltantes=[[10,99]];},x=>{x.especiesSinAsignacion.push('7732-18-5');}]){
  const a=structuredClone(nueva);cambiar(a.paquetes[1].coberturaGrupos);rechaza(()=>red.leerCapacidadesV2(a),'Dynamic reader checks optional coverage');
  const b=structuredClone(nuevaD);cambiar(b.paquetes[0].coberturaGrupos);rechaza(()=>diagramas.leerCapacidadesDiagramas(b),'Diagram reader checks optional coverage');
}
const noAdmitida=structuredClone(nueva);noAdmitida.paquetes[1].componentesCAS.push(original.especiesSinAsignacion[0]);rechaza(()=>red.leerCapacidadesV2(noAdmitida),'An unassigned species cannot be admitted');
const falsaEvidencia=structuredClone(nueva);falsaEvidencia.paquetes[1].combinaciones.find(c=>c.id==='liquido_vapor').evidencia='contrastada';rechaza(()=>red.leerCapacidadesV2(falsaEvidencia),'Group data do not become validated phase predictions');
const sinGrupos=structuredClone(nueva);delete sinGrupos.paquetes[1].coberturaGrupos;rechaza(()=>red.leerCapacidadesV2(sinGrupos),'UNIFAC requires its published coverage');
const otraFamilia=structuredClone(nueva);otraFamilia.paquetes[1].modelo.id='nrtl-fixture';rechaza(()=>red.leerCapacidadesV2(otraFamilia),'UNIFAC metadata cannot masquerade as a different model family');
const ambiguo=structuredClone(nueva);ambiguo.paquetes[1].pares=[];rechaza(()=>red.leerCapacidadesV2(ambiguo),'No molecular-pair/group ambiguity');
const ambiguoD=structuredClone(nuevaD);ambiguoD.paquetes[0].pares=[];rechaza(()=>diagramas.leerCapacidadesDiagramas(ambiguoD),'Diagram group package requires null pairs');
const Alcance=cargar('AlcancePaqueteRed').default;
const alcance=renderToStaticMarkup(React.createElement(Alcance,{paquete:p,componentes:cs}));
check(alcance.includes('Alcance y evidencia del paquete')&&alcance.includes('Cobertura de grupos del paquete'),'Coverage inside existing scope panel');
const antiguo=renderToStaticMarkup(React.createElement(Alcance,{paquete:cap.paquetes[1],componentes:cs}));
check(!antiguo.includes('Cobertura de grupos del paquete'),'No group requirements on non-group packages');
igual(JSON.stringify(original),antes,'Group metadata preserved intact');
igual(JSON.stringify(cap),capAntes,'Existing dynamic capabilities untouched');
igual(JSON.stringify(capD),capDAntes,'Existing diagram capabilities untouched');
for(const name of ['contratoContribucionGrupos.ts','contratoEnsamblajeV2.ts','contratoDiagramasEquilibrio.ts'])igual(fs.readFileSync(`app/motor/${name}`,'utf8').replaceAll('\r\n','\n'),fs.readFileSync(`../docs/contratos/${name}`,'utf8').replaceAll('\r\n','\n').replaceAll('../../frontend/app/motor/','./'),'Canonical contract: '+name);
const estado=cargar('estadoResolucionRed').estadoResolucionRed;
const rechazoBase=leerJson('../docs/ejemplos/motor-n-componentes/motor-ensamblaje-v2-validar-nrtl-4-par-ausente-respuesta.json');
for(const codigo of ['MOTOR_ENS_DATO_PURO_AUSENTE','MOTOR_ENS_PARAMETRO_AUSENTE','MOTOR_ENS_UNIFAC_ASIGNACION_AUSENTE','MOTOR_ENS_UNIFAC_GRUPO_DESCONOCIDO','MOTOR_ENS_UNIFAC_INTERACCION_AUSENTE']){
  const r=structuredClone(rechazoBase);r.diagnosticos[0].codigo=codigo;
  check(estado(r).estado==='Faltan datos del paquete'&&!estado(r).puedeResolver,'Missing model data remain distinct from structural completeness');
  check(r.recuento.gradosLibertad===0&&r.recuento.datosFaltantes===0,'No fabricated DOF deficit for thermodynamic data');
}
const otro=structuredClone(rechazoBase);otro.diagnosticos[0].codigo='MOTOR_ENS_COMBINACION_NO_SOPORTADA';
check(estado(otro).estado==='Modelo no disponible','Unsupported physics is not relabeled as missing data');
const i=process.argv.indexOf('--capacidades');
if(i>=0){const c=red.leerCapacidadesV2(leerJson(process.argv[i+1]));checks++;console.log('Servicio: '+c.paquetes.map(p=>`${p.modelo.id}@${p.modelo.version}${p.coberturaGrupos?' · grupos publicados':''}`).join(', '));}
console.log(`${checks} comprobaciones de cobertura de grupos OK. Metadata y presentación; no calcula ni certifica termodinámica.`);
