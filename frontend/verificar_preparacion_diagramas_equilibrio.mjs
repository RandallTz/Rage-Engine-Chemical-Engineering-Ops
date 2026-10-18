import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const cache=new Map();
function cargar(n){if(n.endsWith('.json'))return JSON.parse(fs.readFileSync(`app/motor/${n}`,'utf8'));if(cache.has(n))return cache.get(n);const m={exports:{}};cache.set(n,m.exports);new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText)(m.exports,m,id=>cargar(id.slice(2)));return m.exports;}
const lector=cargar('lectorEnsamblajeV2'),adapt=cargar('resultadoEnsamblajeV2'),ctx=cargar('contextoMuestraEquilibrio');
const hojas=cargar('hojasPruebaMultifasico').crearHojasPruebaMultifasico();
let checks=0;const check=(v,m)=>{checks++;assert.ok(v,m);},rechaza=f=>{checks++;assert.throws(f);};
const cerca=(a,b)=>check(Math.abs(a-b)<=1e-10*Math.max(Math.abs(a),Math.abs(b),1e-300),`${a} ≈ ${b}`);
const leer=n=>JSON.parse(fs.readFileSync(n,'utf8')),dir='../docs/ejemplos/motor-v2/';

// Real backend states: preserve all species and phase IDs, signed potentials,
// original certification, and independent integrated inventories.
for(const file of fs.readdirSync(dir).filter(f=>f.includes('-resolver-')&&f.endsWith('-peticion.json'))){
  const s=leer(dir+file),raw=leer(dir+file.replace('-peticion','-respuesta'));
  const h=hojas.find(h=>JSON.stringify(h.redTermodinamica.solicitud.volumenes)===JSON.stringify(s.volumenes)),r=adapt.adaptarResultadoV2(h,s,raw),antes=JSON.stringify(r);
  for(const v of s.volumenes)for(let k=0;k<r.tiempos.length;k++){
    const c=ctx.contextoMuestraEquilibrio(r,v.id,k),e=raw.resultados.estados[v.id][k].evaluacion;
    check(c.componentes.map(x=>x.id).join()===v.componenteIds.join(),'All volume component IDs, in declared order');
    check(c.fases.map(f=>f.id).join()===e.fases.map(f=>f.id).join(),'Phase IDs retained rather than inferred by index');
    check(c.T===e.T&&c.P===e.P&&c.tiempo===r.tiempos[k],'Reference cuts use the actual sample T/P');
    check(c.huellaParametros===(raw.resultados.procedenciaModelo?.find(p=>p.volumenIds.includes(v.id))?.huella??null),'Parameter fingerprint is taken only from backend provenance');
    for(const i of c.inventarios){cerca(i.nReconstruido,i.n);cerca(i.mReconstruida,i.m);cerca(i.fases.reduce((s,f)=>s+(f.reparto??0),0),1);}
    const cortes=ctx.referenciasCortesBinarios(c,v.componenteIds[0]);
    if(v.componenteIds.length===2){check(cortes.estado==='preparado'&&cortes.servicio==='pendiente_contrato','Binary preparation never promises a running tracer');check(ctx.compararCondicionCorte(c,{tipo:'Txy',P:{valor:c.P/1e5,unidad:'bar'}}).compatible,'Pressure unit equivalence');check(ctx.compararCondicionCorte(c,{tipo:'Pxy',T:{valor:c.T-273.15,unidad:'degC'}}).compatible,'Absolute temperature unit equivalence');}
    else check(cortes.estado==='no_binario','Single species remains a single species');
    check(!ctx.compararCondicionCorte(c,{tipo:'Txy',P:{valor:c.P*1.01,unidad:'Pa'}}).compatible,'Different pressure is not the same Txy cut');
    check(!ctx.compararCondicionCorte(c,{tipo:'Pxy',T:{valor:c.T+1,unidad:'K'}}).compatible,'Different temperature is not the same Pxy cut');
  }
  rechaza(()=>ctx.contextoMuestraEquilibrio(r,'volumen-inexistente',0));rechaza(()=>ctx.contextoMuestraEquilibrio(r,s.volumenes[0].id,-1));rechaza(()=>ctx.contextoMuestraEquilibrio(r,s.volumenes[0].id,r.tiempos.length));
  check(JSON.stringify(r)===antes,'Context extraction never edits solver values');
  for(const cambio of [
    e=>delete e.potenciales.fases[0].mu[s.volumenes[0].componenteIds[0]],
    e=>e.potenciales.fases[0].mu['999999']=null,
    e=>e.potenciales.fases[0].mu[s.volumenes[0].componenteIds[0]]=null,
    e=>e.potenciales.fases[0].mu[s.volumenes[0].componenteIds[0]]+=1000,
  ]){const x=structuredClone(raw);cambio(x.resultados.estados[s.volumenes[0].id][0]);rechaza(()=>lector.leerResolucionV2(x,s));}
  // Corrupt both metadata and data units: matching each other is insufficient.
  for(const [suffix,u]of [['T','degC'],['P','bar'],['V','L'],['U','kJ']]){
    const x=structuredClone(raw),id=`volumen.${s.volumenes[0].id}.${suffix}`;
    x.validacion.variables.find(v=>v.id===id).unidadSI=u;
    x.resultados.series.find(v=>v.variableId===id).unidadSI=u;
    if(x.resultados.catalogoSeries)x.resultados.catalogoSeries.find(v=>v.variableId===id).unidadSI=u;
    rechaza(()=>lector.leerResolucionV2(x,s));
  }
}

/** Algebraic protocol fixtures, NOT thermodynamic calculations. Generate any
 * N using independent beta/x weighting and h=u+Pv, g=h-Ts=sum(x mu).
 * Passing these fixtures demonstrates dimension-independent transport/readers,
 * not a physical EOS, flash, or stability capability beyond the backend limit. */
function fixture(N,nFases,escala=1,ausente=false){
  const h=structuredClone(hojas[0]),s=h.redTermodinamica.solicitud;s.solicitudId='ensayo-estructural';
  const ids=Array.from({length:N},(_,i)=>7+13*i),mu=Object.fromEntries(ids.map((id,i)=>[id,-1500+19*i])),M=Object.fromEntries(ids.map((id,i)=>[id,.01+.003*i]));
  s.componentes=ids.map(id=>({id,nombre:`Especie ${id}`,simbolo:`C${id}`,identidadQuimica:{proveedorId:`ensayo:${id}`}}));
  s.paquetes=[{id:'p',modelo:{id:'ensayo-algebraico-no-EOS',version:'1'}}];s.volumenes=[structuredClone(s.volumenes[0])];s.corrientes=[];s.intercambiosTermicos=[];
  const v=s.volumenes[0];v.componenteIds=ids;v.paqueteId='p';v.politica={cantidad:'sin_restriccion',cambioInterno:'permitido',evaluacion:'equilibrio_estable'};
  s.datos={};const dato=(id,magnitud,valor,unidad)=>{s.datos[id]={magnitud,funcion:'inicial',declaracion:{texto:String(valor),unidad},origen:{propietarioId:'volumen:A',ruta:`/datos/${id}`}};return id;};
  s.estudio.tiempoId=dato('tf','tiempo',1,'s');s.estudio.muestras=2;
  const T=350,P=100000,total=3*escala,beta=Array.from({length:nFases},(_,a)=>(a+1)/(nFases*(nFases+1)/2));
  const xs=beta.map((_,a)=>{const w=ids.map((_,i)=>ausente&&i===N-1?0:(i+1)*(1+(a+1)*(i%3)));const sum=w.reduce((s,x)=>s+x,0);return Object.fromEntries(ids.map((id,i)=>[id,w[i]/sum]));});
  const z=Object.fromEntries(ids.map(id=>[id,beta.reduce((s,b,a)=>s+b*xs[a][id],0)])),Mg=ids.reduce((a,id)=>a+z[id]*M[id],0);
  const datos=beta.map((b,a)=>{const x=xs[a],Mp=ids.reduce((s,id)=>s+x[id]*M[id],0),g=ids.reduce((s,id)=>s+x[id]*mu[id],0),s=800+100*a,v=a===nFases-1&&nFases>1?.5:.001;
    const h=g/Mp+T*s;return {id:a===nFases-1&&nFases>1?'vapor':`liquido-${a+1}`,tipo:a===nFases-1&&nFases>1?'vapor':'liquido',regimen:'ordinario',fraccionMolar:b,fraccionMasica:b*Mp/Mg,composicionMolar:x,propiedades:{u:h-P*v,h,v,s}};});
  const mezcla=Object.fromEntries(['u','h','v','s'].map(k=>[k,datos.reduce((s,f)=>s+f.fraccionMasica*f.propiedades[k],0)]));
  const fases=datos.map(f=>({...f,fraccionVolumen:f.fraccionMasica*f.propiedades.v/mezcla.v})),masa=total*Mg;
  const ev={T,P,composicionMolar:z,componentes:ids.map(id=>({id,masaMolarKgMol:M[id],fuente:'ensayo algebraico; no propiedades reales'})),fases,mezcla,referencia:{id:'ensayo',descripcion:'Fixture sin ecuacion de estado'},estabilidad:{estado:'estable',alcance:['liquido','vapor'],metodo:'Metadato sintetico para probar el lector; no certificacion fisica'},verificaciones:[{id:'estabilidad',estado:'cumple',residuo:0,tolerancia:1e-9},...(nFases>1?[{id:'equilibrio',estado:'cumple',residuo:0,tolerancia:1e-9}]:[])]};
  const G=total*ids.reduce((s,id)=>s+z[id]*mu[id],0),p={base:'molar',unidad:'J/mol',unidades:{mu:'J/mol',G:'J',A:'J',S:'J/K'},referencia:ev.referencia,T,P,G,A:G-P*masa*mezcla.v,S:masa*mezcla.s,estadoEstandar:'ensayo',metodo:'ensayo',fases:fases.map(f=>({faseId:f.id,mu:Object.fromEntries(ids.map(id=>[id,f.composicionMolar[id]>0?mu[id]:null]))})),residuoIgualdadMu:0,candidatasExploradas:['liquido','vapor'],tmMinimo:0};
  const m={volumenId:'A',evaluacion:ev,potenciales:p},valores=Object.fromEntries([...ids.map(id=>[`volumen.A.n.${id}`,total*z[id]]),...Object.entries({T,P,U:masa*mezcla.u,H:masa*mezcla.h,V:masa*mezcla.v,masa,S:masa*mezcla.s}).map(([k,v])=>['volumen.A.'+k,v])]);
  v.inicial.cantidades={base:'molar',datoIds:Object.fromEntries(ids.map(id=>[id,dato(`n0-${id}`,'cantidad',total*z[id],'mol')]))};v.inicial.energia={tipo:'T',datoId:dato('T0','temperatura',T,'K')};v.frontera={tipo:'presion_prescrita',presionId:dato('P','presion',P,'Pa')};
  const unidades=cargar('verificarEstadoMateriaRed').unidadesEstadoVolumen(v),variables=Object.keys(valores).map(id=>({id,propietarioId:'volumen:A',unidadSI:unidades[id],papel:id.includes('.n.')?'diferencial':'algebraica',magnitud:'ensayo'}));
  const validacion={revision:2,solicitudId:s.solicitudId,modeloId:'ensayo-N-'+N,recuento:{estado:'listo',variables:variables.length,ecuacionesIndependientes:0,datosDefinidos:0,datosFaltantes:0,inicialesFaltantes:0,gradosLibertad:0},variables,ecuaciones:[],diagnosticos:[],inicializacion:{estado:'compatible',volumenes:{A:{estado:'compatible',variables:valores,estadoTermodinamico:m}}}};
  const raw={revision:2,estado:'resuelto',validacion,resultados:{metodo:'ensayo algebraico sin solver',tiempos:[0,1],series:Object.entries(valores).map(([variableId,valor])=>({variableId,unidadSI:unidades[variableId],valores:[valor,valor]})),estados:{A:[m,structuredClone(m)]},eventos:[],residuos:[],segundaLey:{estado:'no_evaluable',motivo:'fixture sin transferencia termica',unidad:'J/K'}}};
  return {s,raw,r:adapt.adaptarResultadoV2(h,s,raw)};
}
for(const N of [1,2,3,5,8,12])for(const F of [1,2,3])for(const escala of [1e-12,1,1e12]){
  const {s,raw,r}=fixture(N,F,escala),antes=JSON.stringify(r),c=ctx.contextoMuestraEquilibrio(r,'A',1);
  check(c.componentes.length===N&&c.inventarios.length===N&&c.fases.length===F,'N species and arbitrary phase count retained without a binary/ternary branch');
  for(const i of c.inventarios){cerca(i.n,i.nReconstruido);cerca(i.m,i.mReconstruida);cerca(i.fases.reduce((a,f)=>a+f.reparto,0),1);}
  const ref=ctx.referenciasCortesBinarios(c,s.componentes[0].id);check(ref.estado===(N===2?'preparado':'no_binario'),'Binary geometry does not truncate the full state');
  const ys=adapt.graficasComponentesV2(r);check(ys.length===N&&ys.every(g=>g.y.length===F),'Graph variables retain every species and phase');
  check(JSON.stringify(r)===antes,'No normalization or clipping on input');
  const rr=structuredClone(raw),ss=structuredClone(s);ss.componentes.reverse();ss.volumenes[0].componenteIds.reverse();
  const reordered=adapt.adaptarResultadoV2({...hojas[0],redTermodinamica:{solicitud:ss,nombres:{}}},ss,rr),other=ctx.contextoMuestraEquilibrio(reordered,'A',1);
  for(const i of c.inventarios)cerca(i.n,other.inventarios.find(x=>x.id===i.id).n);
}
const {r:ausente}=fixture(5,3,1,true),ca=ctx.contextoMuestraEquilibrio(ausente,'A',0),cero=ca.inventarios.at(-1);
check(cero.n===0&&cero.fases.every(f=>f.n===0&&f.reparto===null),'Zero amount is retained while its partition remains undefined');
const {r:binario}=fixture(2,2),cb=ctx.contextoMuestraEquilibrio(binario,'A',0);rechaza(()=>ctx.referenciasCortesBinarios(cb,999));
// Non-passing trajectory metadata is not promoted by successful reconstruction.
for(const nombre of ['no-cumple','no-evaluable']){
  const base='qa_multifasico_2026_10_15/consolidacion/',s=leer(base+nombre+'-peticion.json'),raw=leer(base+nombre+'-respuesta.json'),r=adapt.adaptarResultadoV2(hojas[0],s,raw),c=ctx.contextoMuestraEquilibrio(r,s.volumenes[0].id,r.tiempos.length-1);
  check(c.certificacionTrayectoria===nombre.replace('-','_'),'Original physical outcome retained');
  check(c.muestraEnTramoSinCertificar===(nombre==='no-cumple'),'No-evaluable is not mislabeled as a violated trajectory');
}
console.log(`${checks} comprobaciones: contextos por muestra, unidades SI, Gibbs por componente, reconstrucción N-componentes, fases, cortes binarios sin truncar el ensamblaje y controles negativos.`);
console.log('Los ensayos algebraicos de 5/8/12 componentes verifican lectores y presentación; no habilitan flashes ni estabilidad física fuera de las capacidades publicadas.');
