// Structural conservation and framework checks. No new property model is certified here.
import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
import katex from 'katex';
const cache=new Map();
function cargar(n){
  if(cache.has(n))return cache.get(n);
  const m={exports:{}};cache.set(n,m.exports);
  new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(m.exports,m,r=>cargar(r.slice(2)));
  return m.exports;
}
const {estructurarTermodinamica,estructuraSolicitudDinamica}=cargar('estructuraTermodinamica');
const {fundamentosEquilibrio}=cargar('relacionesTermodinamicas');
let checks=0;
const check=(v,m)=>{checks++;assert.ok(v,m);};
const politica={cantidad:'sin_restriccion',cambioInterno:'permitido',evaluacion:'equilibrio_estable'};
const cierre={modelo:{id:'paquete-simbolico-no-ejecutable',version:'1'},politica};
const componentes=Array.from({length:3},(_,i)=>({id:i+1,nombre:`Componente ${i+1}`,simbolo:`C${i+1}`}));
const volumen=(id,frontera='rigida')=>({id,componenteIds:[1,2,3],cierre:structuredClone(cierre),frontera});
const corriente=(id,desde,hasta)=>({id,desde,hasta,componenteIds:[1,2,3],mecanismo:'convectivo'});
const red={componentes,volumenes:[volumen('a'),volumen('b','presion_prescrita')],corrientes:[corriente('entrada',null,'a'),corriente('comun','a','b'),corriente('salida','b',null)],intercambios:[{id:'contacto',desde:'a',hasta:'b',relacion:'conductancia'},{id:'exterior',desde:null,hasta:'a',relacion:'impuesta'}]};
const texto=JSON.stringify(red),p=estructurarTermodinamica(red);
check(JSON.stringify(red)===texto,'El compilador no modifica especificaciones');
check(p.ejecutable===false&&p.recuento===null,'No inventa ejecutabilidad ni GL');
check(!p.diagnosticos.length,'Dos volúmenes y tres componentes estructuralmente válidos');
check(p.balances.length===8,'Un balance por componente y volumen, más una energía por volumen');
check(p.cierres.every(c=>c.topologiaFases==='por_determinar'),'No fuerza un número de fases');
check(p.cierres[0].estabilidad==='maximo_S_UVn'&&p.cierres[1].estabilidad==='estable_a_TP_reconstruidos','Criterio corresponde a las restricciones');
for(const t of p.transferencias.filter(t=>t.desde!==null&&t.hasta!==null)){
  const terminos=p.balances.flatMap(b=>b.terminos.filter(x=>x.transferenciaId===t.id));
  check(terminos.length===2&&terminos.reduce((s,t)=>s+t.coeficiente,0)===0,'La transferencia interna aparece una vez por extremo con signos opuestos');
  const g=p.globales.find(g=>g.familia===t.familia&&g.componenteId===t.componenteId);
  check(g.transferenciasInternasCanceladas.includes(t.id)&&!g.terminos.some(x=>x.transferenciaId===t.id),'Cancelación global por identidad');
}
check(p.transferencias.filter(t=>t.mecanismo==='trabajo_frontera').length===1,'Solo frontera móvil tiene término de trabajo');
check(p.transferencias.filter(t=>t.mecanismo==='entalpia_donante').length===3,'Una energía por corriente, sin multiplicarla por componentes');
check(p.globales.find(g=>g.familia==='energia').terminos.some(t=>t.transferenciaId==='calor:exterior'),'Calor exterior permanece en el balance global');

// Many topologies: cycles, branches and parallel edges; nonzero signed transfers.
// These test incidence algebra, not a claim that the backend solves these graphs.
let semilla=12937;
const azar=()=>{semilla=(Math.imul(semilla,1664525)+1013904223)>>>0;return semilla/2**32;};
for(let caso=0;caso<72;caso++){
  const nv=1+caso%8,nc=1+caso%3,vs=Array.from({length:nv},(_,i)=>({...volumen(`v${i}`),componenteIds:componentes.slice(0,nc).map(c=>c.id)})),cs=[];
  for(let j=0;j<nv*3;j++){
    let desde=Math.floor(azar()*(nv+1))-1,hasta=Math.floor(azar()*(nv+1))-1;
    if(desde===hasta)hasta=desde===-1?0:-1;
    cs.push({...corriente(`s${j}`,desde===-1?null:vs[desde].id,hasta===-1?null:vs[hasta].id),componenteIds:componentes.slice(0,nc).map(c=>c.id)});
  }
  const plan=estructurarTermodinamica({componentes:componentes.slice(0,nc),volumenes:vs,corrientes:cs,intercambios:[]});
  check(!plan.diagnosticos.length,'Topología generada válida');
  const valores=Object.fromEntries(plan.transferencias.map(t=>[t.id,(azar()-.5)*1e5]));
  for(const g of plan.globales){
    const local=plan.balances.filter(b=>g.variableIds.includes(b.variableId)).reduce((a,b)=>a+b.terminos.reduce((a,t)=>a+t.coeficiente*valores[t.transferenciaId],0),0);
    const global=g.terminos.reduce((a,t)=>a+t.coeficiente*valores[t.transferenciaId],0);
    check(Math.abs(local-global)<1e-8,'Suma local = balance global, incluso con flujos invertidos');
  }
  const invertida=estructurarTermodinamica({componentes:componentes.slice(0,nc),volumenes:[...vs].reverse(),corrientes:[...cs].reverse(),intercambios:[]});
  const firma=g=>Object.fromEntries(g.globales.map(b=>[b.id,[...b.terminos].sort((a,b)=>a.transferenciaId.localeCompare(b.transferenciaId))]));
  check(JSON.stringify(firma(plan))===JSON.stringify(firma(invertida)),'Orden de volúmenes o corrientes no cambia las transferencias globales');
}
for(const alterar of [r=>r.componentes.push(r.componentes[0]),r=>r.volumenes.push(r.volumenes[0]),r=>r.corrientes.push(r.corrientes[0]),r=>r.corrientes[0].hasta='fantasma',r=>r.corrientes[0].desde=r.corrientes[0].hasta,r=>r.corrientes[0].componenteIds=[999],r=>r.corrientes[0].componenteIds=[1,1],r=>r.volumenes[1].componenteIds=[1],r=>r.intercambios[0].hasta='fantasma',r=>r.intercambios.push(r.intercambios[0])]){
  const mal=structuredClone(red);alterar(mal);const q=estructurarTermodinamica(mal);
  check(q.diagnosticos.some(d=>d.estado==='invalido')&&!q.transferencias.length&&!q.balances.length&&!q.globales.length,'No presenta un grafo truncado como modelo válido');
}
const selectiva=structuredClone(red);selectiva.corrientes[1].mecanismo='selectivo';
const ps=estructurarTermodinamica(selectiva);
check(ps.diagnosticos.some(d=>d.codigo==='ENERGIA_SELECTIVA_PENDIENTE'),'Transferencia selectiva necesita modelo propio');
check(ps.transferencias.find(t=>t.id==='corriente:comun:energia').mecanismo==='energia_selectiva_pendiente','No adjudica entalpía convectiva a un intercambio selectivo');
const faltante=structuredClone(red);faltante.volumenes[0].cierre=null;faltante.volumenes[0].frontera='sin_relacion';
check(estructurarTermodinamica(faltante).diagnosticos.filter(d=>d.estado==='pendiente').length===2,'Modelo y relación mecánica ausentes permanecen pendientes');
const solo=estructurarTermodinamica({componentes:[componentes[0]],volumenes:[{...volumen('solo'),componenteIds:[1]}],corrientes:[],intercambios:[]});
check(solo.balances.length===2&&solo.balances.every(b=>b.terminos.length===0),'Volumen rígido cerrado sin transferencias: derivadas nulas, sin datos fabricados');

// The live v1 bridge reads request declarations only, leaves JSON unchanged and
// never promotes the symbolic graph to backend capabilities.
for(const archivo of fs.readdirSync('../docs/ejemplos').filter(n=>n.startsWith('motor-ensamblaje-')&&n.endsWith('-peticion.json'))){
  const s=JSON.parse(fs.readFileSync(`../docs/ejemplos/${archivo}`,'utf8')),antes=JSON.stringify(s),q=estructuraSolicitudDinamica(s);
  check(JSON.stringify(s)===antes,'Petición v1 intacta');
  check(q.cierres.length===1&&q.cierres[0].modelo.id===s.volumen.cierre.modelo.id,'Modelo procede de la elección activa');
  check(q.recuento===null&&q.ejecutable===false,'No infiere nuevas capacidades del backend');
  check(!q.diagnosticos.some(d=>d.estado==='invalido'),'Topología de fixtures actuales aceptada');
  for(const c of s.corrientes){
    const t=q.transferencias.find(t=>t.corrienteId===String(c.id)&&t.familia==='energia');
    check(t.desde===c.desde&&t.hasta===c.hasta,'Extremos conservados por ID');
  }
}
for(const tipo of ['TP','PH','UP','UV'])for(const cantidad of ['sin_restriccion','monofasico']){
  const r=fundamentosEquilibrio(tipo,{...politica,cantidad});
  for(const e of r){katex.renderToString(e.latex,{throwOnError:true});checks++;}
  check(r.some(e=>e.id==='potencial-quimico')&&r.some(e=>e.id==='fugacidad'),'Potencial químico y referencia común explícitos');
  check(r.some(e=>e.id==='monofasico')===(cantidad==='monofasico'),'Monofásico es restricción, no resultado supuesto');
  if(tipo==='PH'||tipo==='UP')check(!r.some(e=>/\\min|\\max/.test(e.latex))&&r.some(e=>e.id==='estabilidad-reconstruida'),'PH/UP no afirman minimizar G bajo restricciones equivocadas');
}
console.log(`${checks} comprobaciones: conservación estructural en redes, cancelación interna, fronteras, marco de equilibrio y compatibilidad v1. No certifica nuevos flashes ni modelos físicos.`);
