import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const cache=new Map();
function cargar(n){if(n.endsWith('.json'))return JSON.parse(fs.readFileSync(`app/motor/${n}`,'utf8'));if(cache.has(n))return cache.get(n);const m={exports:{}};cache.set(n,m.exports);new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText)(m.exports,m,id=>cargar(id.slice(2)));return m.exports;}
const {cambiarRed,datoRed,sincronizarHipotesis}=cargar('redTermodinamica');
const {agregarComponenteRed,quitarComponenteRed,asignarComponenteVolumen,asignarComponenteCorriente,resumenComposicionExterior}=cargar('componentesRed');
const hojas=cargar('hojasPruebaMultifasico').crearHojasPruebaMultifasico();
let checks=0;
const check=(v,m)=>{checks++;assert.ok(v,m);};
const igual=(a,b,m)=>{checks++;assert.deepEqual(a,b,m);};
const rechaza=f=>{checks++;assert.throws(f);};
const lector=cargar('lectorEnsamblajeV2');
const caps=JSON.parse(fs.readFileSync('../docs/ejemplos/motor-v2/motor-ensamblaje-v2-capacidades.json','utf8'));
const antigua=structuredClone(caps);delete antigua.tamanos;
check(lector.leerCapacidadesV2(antigua).componentesMaximos===antigua.componentesMaximos,'Historical capabilities without dimension evidence remain readable');
// Protocol fixture: never an assertion of new backend physics.
const ampliada={...structuredClone(antigua),componentesMaximos:7,tamanos:{cuenta:'declarados por volumen',componentesMaximosPorVolumen:7,fasesMaximas:3,contrastados:{'mezcla-ideal':{estatico:[1,2,4,5,7],dinamico:[2,4]}},estabilidad:{general:'ensayo de lector'},presupuesto:'presupuesto publicado'}};
check(lector.leerCapacidadesV2(ampliada).tamanos.contrastados['mezcla-ideal'].dinamico.includes(4),'Admitted and verified sizes are kept separate');
for(const cambiar of [c=>c.tamanos.componentesMaximosPorVolumen=8,c=>c.tamanos.fasesMaximas=0,c=>c.tamanos.presupuesto='',c=>c.tamanos.contrastados['mezcla-ideal'].dinamico=[8],c=>c.tamanos.estabilidad.general=null]){const x=structuredClone(ampliada);cambiar(x);rechaza(()=>lector.leerCapacidadesV2(x));}
let h=structuredClone(hojas[1]),original=JSON.stringify(h);
h.resultadoRef={firma:'anterior',estado:'resuelto',fecha:'2026-10-15'};
h=cambiarRed(h,r=>agregarComponenteRed(r,'Etanol','64-17-5',['A'],3));
let s=h.redTermodinamica.solicitud;
igual(s.volumenes.map(v=>v.componenteIds),[[1,2],[1]],'New species belongs only to explicitly chosen volumes');
check(!h.resultadoRef,'Changing membership invalidates old results');
igual(s.datos['volumen.A.n0.2'].declaracion,{texto:'',unidad:'kg'},'No implicit zero inventory');
igual(s.datos['volumen.A.n0.1'].declaracion,{texto:'10',unidad:'kg'},'Existing declared inventory is unchanged');
check(JSON.stringify(hojas[1])===original,'Original worksheet is not mutated');
h=cambiarRed(h,r=>{agregarComponenteRed(r,'Benceno','71-43-2',['B'],3);agregarComponenteRed(r,'Tolueno','108-88-3',['B'],3);});
s=h.redTermodinamica.solicitud;
check(s.componentes.length===4&&s.volumenes.every(v=>v.componenteIds.length<=3),'Four global components fit a three-components-per-volume capability');
const antes=JSON.stringify(h);
rechaza(()=>cambiarRed(h,r=>agregarComponenteRed(r,'Extra','',['B'],3)));
check(JSON.stringify(h)===antes,'Rejected edit is atomic');
rechaza(()=>cambiarRed(h,r=>agregarComponenteRed(r,'Duplicado','71-43-2',[],3)));
rechaza(()=>cambiarRed(h,r=>agregarComponenteRed(r,'','',[],3)));
rechaza(()=>cambiarRed(h,r=>agregarComponenteRed(r,'Otro','',['fantasma'],3)));
h=cambiarRed(h,r=>{asignarComponenteVolumen(r,'B',1,false,3);});
s=h.redTermodinamica.solicitud;
igual(s.volumenes.map(v=>v.componenteIds),[[1,2],[3,4]],'Disjoint material circuits retain independent sets');
check(!s.datos['volumen.B.n0.1'],'Removed initial datum is pruned, not shown in Resolver');
check(s.datos['volumen.A.n0.1']!==undefined,'Another volume quantity is preserved');

// No ID reuse after removal, including initially unused catalog entries.
h=cambiarRed(h,r=>agregarComponenteRed(r,'Borrador','',[],3));
const borrador=h.redTermodinamica.solicitud.componentes.at(-1).id;
h=cambiarRed(h,r=>quitarComponenteRed(r,borrador));
h=cambiarRed(h,r=>agregarComponenteRed(r,'Borrador siguiente','',[],3));
check(h.redTermodinamica.solicitud.componentes.at(-1).id>borrador,'Stable IDs never alias a removed species');

// Stream edits preserve the donor total, external T/P and all untouched values.
let corriente=cambiarRed(hojas[0],r=>{
  const a=r.solicitud;
  a.corrientes=[{id:'entrada',desde:null,hasta:'A',componenteIds:[1,2],mecanismo:'convectivo',materia:{modo:'total_desde_donante',base:'molar',caudalId:datoRed(a,'F','caudal_molar','mol/s','corriente:entrada','frontera','2')},estadoExterior:{tipo:'TP',temperaturaId:datoRed(a,'Text','temperatura','K','corriente:entrada','frontera','330'),presion:{tipo:'dato',datoId:datoRed(a,'Pext','presion','Pa','corriente:entrada','frontera','101325')},composicion:{base:'molar',fracciones:{1:.4,2:.6}}}}];
});
corriente=cambiarRed(corriente,r=>agregarComponenteRed(r,'Metanol','67-56-1',['A'],3));
igual(corriente.redTermodinamica.solicitud.corrientes[0].componenteIds,[1,2],'Adding to a volume does not silently alter connected streams');
corriente=cambiarRed(corriente,r=>asignarComponenteCorriente(r,'entrada',3,true));
let c=corriente.redTermodinamica.solicitud.corrientes[0];
igual(c.estadoExterior.composicion.fracciones,{1:.4,2:.6},'Existing composition untouched; new species remains pending');
let q=resumenComposicionExterior(c.componenteIds,c.estadoExterior.composicion.fracciones);
igual(q.faltan,[3],'Missing fraction is reported by ID');
check(!q.completa,'Existing sum 1 does not hide a missing fraction');
igual(corriente.redTermodinamica.solicitud.datos.F.declaracion,{texto:'2',unidad:'mol/s'},'Flow and units retained');
rechaza(()=>cambiarRed(corriente,r=>asignarComponenteVolumen(r,'A',3,false,3)));
corriente=cambiarRed(corriente,r=>quitarComponenteRed(r,2));
c=corriente.redTermodinamica.solicitud.corrientes[0];
igual(c.estadoExterior.composicion.fracciones,{1:.4},'Removing a component never renormalizes remaining fractions');
check(resumenComposicionExterior(c.componenteIds,c.estadoExterior.composicion.fracciones).suma===.4,'Raw composition sum remains inspectable');
check(corriente.redTermodinamica.solicitud.datos.Text.declaracion.texto==='330','Exterior state retained');
for(const fracciones of [{1:0,3:1},{1:1,3:0}])check(resumenComposicionExterior([1,3],fracciones).completa,'Explicit zero is a declared fraction');
for(const fracciones of [{1:.2,3:.2},{1:-1,3:2},{1:NaN,3:1},{1:.5,3:.5,99:.1}])check(!resumenComposicionExterior([1,3],fracciones).completa,'Invalid fractions cannot look complete');

// Per-component stream data inherit their own basis, never the volume basis.
corriente=cambiarRed(corriente,r=>{
  const a=r.solicitud,x=a.corrientes[0];
  x.componenteIds=[1];delete x.estadoExterior.composicion;
  x.materia={modo:'por_componente',base:'molar',caudalIds:{1:datoRed(a,'f1','caudal_molar','kmol/h','corriente:entrada','frontera','3.6')}};
});
corriente=cambiarRed(corriente,r=>asignarComponenteCorriente(r,'entrada',3,true));
c=corriente.redTermodinamica.solicitud.corrientes[0];
igual(c.estadoExterior.composicion,{base:'molar',fracciones:{}},'Expanding an unspecified pure donor requests mixture composition');
igual(corriente.redTermodinamica.solicitud.datos[c.materia.caudalIds[3]].declaracion,{texto:'',unidad:'mol/s'},'New per-component molar flow is pending with correct dimensions');
igual(corriente.redTermodinamica.solicitud.datos.f1.declaracion,{texto:'3.6',unidad:'kmol/h'},'Untouched flow retains original unit');
corriente=cambiarRed(corriente,r=>asignarComponenteCorriente(r,'entrada',3,false));
check(!corriente.redTermodinamica.solicitud.datos['corriente.entrada.F.3'],'Removed flow datum is not left orphaned');
rechaza(()=>cambiarRed(corriente,r=>asignarComponenteCorriente(r,'entrada',1,false)));
rechaza(()=>cambiarRed(corriente,r=>asignarComponenteCorriente(r,'entrada',999,true)));

// Dimension-independent document editing, NOT flash/stability certification.
for(const N of [1,2,3,4,5,8,12])for(const base of ['masica','molar']){
  let x=structuredClone(hojas[0]);
  x.redTermodinamica.solicitud.volumenes[0].inicial.cantidades.base=base;
  x=cambiarRed(x,r=>{const a=r.solicitud,v=a.volumenes[0];a.componentes=[a.componentes[0]];v.componenteIds=[1];v.inicial.cantidades.datoIds={1:v.inicial.cantidades.datoIds[1]};for(let i=1;i<N;i++)agregarComponenteRed(r,`Ensayo estructural ${i}`,'',['A'],N);});
  const a=x.redTermodinamica.solicitud,v=a.volumenes[0];
  check(a.componentes.length===N&&v.componenteIds.length===N,'Catalog and local set scale with declared N');
  for(const id of v.componenteIds.slice(1)){const d=a.datos[v.inicial.cantidades.datoIds[id]];igual(d.declaracion,{texto:'',unidad:base==='masica'?'kg':'mol'},'New initial quantity preserves per-volume basis');check(d.magnitud===(base==='masica'?'masa':'cantidad'),'Quantity magnitude matches its unit');}
  check(Object.values(a.datos).every(d=>d.declaracion.texto!==undefined),'Data schema retained');
}

// Real request for the CURRENT backend: four species globally, only two per volume.
// No fictitious thermodynamic properties or expectations are embedded here.
let qa=cambiarRed(hojas[1],r=>{
  agregarComponenteRed(r,'Etanol','64-17-5',['A'],3);
  agregarComponenteRed(r,'Benceno','71-43-2',['B'],3);
  agregarComponenteRed(r,'Tolueno','108-88-3',['B'],3);
  asignarComponenteVolumen(r,'B',1,false,3);
  const a=r.solicitud;a.paquetes=[{id:'ideal',modelo:{id:'mezcla-ideal',version:'1'}}];a.solicitudId='qa-catalogo-global-4';
  for(const [i,v] of a.volumenes.entries()){
    v.paqueteId='ideal';v.frontera={tipo:'presion_prescrita',presionId:datoRed(a,`P.${v.id}`,'presion','Pa',`volumen:${v.id}`,'frontera','101325')};
    v.inicial.cantidades.base='molar';
    for(const id of v.componenteIds)v.inicial.cantidades.datoIds[id]=datoRed(a,`n.${v.id}.${id}`,'cantidad','mol',`volumen:${v.id}`,'inicial','1');
    a.datos[v.inicial.energia.datoId].declaracion={texto:String(330-10*i),unidad:'K'};
    sincronizarHipotesis(v);
  }
  a.datos[a.estudio.tiempoId].declaracion={texto:'2',unidad:'s'};a.estudio.muestras=3;
  a.datos[a.intercambiosTermicos[0].ley.conductanciaId].declaracion={texto:'0.1',unidad:'W/K'};
});

if(process.argv.includes('--servicio')){
  const dir='qa_catalogo_n_2026_10_15';fs.mkdirSync(dir,{recursive:true});
  const a=qa.redTermodinamica.solicitud,api=process.env.MOTOR_API??'http://localhost:8004';
  for(const ruta of ['validar','resolver']){
    const resp=await fetch(`${api}/motor/ensamblajes/${ruta}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(a),signal:AbortSignal.timeout(180000)});
    check(resp.ok,`${ruta} HTTP status`);const raw=await resp.json();
    fs.writeFileSync(`${dir}/${ruta}-peticion.json`,JSON.stringify(a,null,2));fs.writeFileSync(`${dir}/${ruta}-respuesta.json`,JSON.stringify(raw,null,2));
    if(ruta==='validar'){cargar('lectorEnsamblajeV2').leerValidacionV2(raw,a);check(raw.recuento.estado==='listo',JSON.stringify(raw.diagnosticos));}
    else{
      cargar('lectorEnsamblajeV2').leerResolucionV2(raw,a);check(raw.estado==='resuelto',JSON.stringify(raw.validacion.diagnosticos));
      check(raw.resultados.certificacion.estado==='cumple','Physical certification provided by the current backend');
      const H=a.volumenes.map(v=>raw.resultados.series.find(q=>q.variableId===`volumen.${v.id}.H`).valores);
      for(let k=0;k<H[0].length;k++)check(Math.abs(H.reduce((sum,x)=>sum+x[k]-x[0],0))<1e-5,'Internal heat cancels in total enthalpy');
      for(const v of a.volumenes)for(const id of v.componenteIds){const vals=raw.resultados.series.find(q=>q.variableId===`volumen.${v.id}.n.${id}`).valores;check(vals.every(n=>Math.abs(n-1)<1e-10),'Each component inventory is conserved');}
    }
  }
}
if(process.argv.includes('--ui')){
  const {solicitud:a,respuesta:raw}=JSON.parse(fs.readFileSync('qa_catalogo_n_2026_10_15/ejecucion-ui.json','utf8'));
  lector.leerResolucionV2(raw,a);check(raw.estado==='resuelto'&&raw.resultados.certificacion.estado==='cumple','Actual browser run resolved and certified');
  check(a.componentes.length===4&&a.volumenes.every(v=>v.componenteIds.length===2),'Browser supports a global catalog larger than each local set');
  igual(a.volumenes.map(v=>v.componenteIds),[[1,2],[3,4]],'Browser kept disjoint local IDs');
  const H=a.volumenes.map(v=>raw.resultados.series.find(q=>q.variableId===`volumen.${v.id}.H`).valores);
  for(let k=0;k<H[0].length;k++)check(Math.abs(H.reduce((sum,x)=>sum+x[k]-x[0],0))<1e-5,'Browser trajectory conserves global enthalpy');
  for(const v of a.volumenes)for(const cid of v.componenteIds){
    const vals=raw.resultados.series.find(q=>q.variableId===`volumen.${v.id}.n.${cid}`).valores;
    check(vals.every(n=>Math.abs(n-1)<1e-10),'Browser trajectory preserves each inventory');
    check(raw.resultados.estados[v.id].every(x=>Object.keys(x.evaluacion.composicionMolar).length===2),'No global species leaked into another volume result');
  }
}
console.log(`${checks} comprobaciones de edición del catálogo, pertenencia por volumen/corriente, unidades y datos pendientes. Las pruebas N>3 locales son estructurales, no flashes.`);
