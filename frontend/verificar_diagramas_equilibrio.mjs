import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const cache=new Map();
function cargar(n){if(n.endsWith('.json'))return JSON.parse(fs.readFileSync(`app/motor/${n}`,'utf8'));if(cache.has(n))return cache.get(n);const m={exports:{}};cache.set(n,m.exports);new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText)(m.exports,m,id=>cargar(id.slice(2)));return m.exports;}
const lector=cargar('lectorDiagramasEquilibrio'),datos=cargar('datosDiagramaEquilibrio'),ctx=cargar('contextoMuestraEquilibrio');
let checks=0;const check=(v,m)=>{checks++;assert.ok(v,m);},rechaza=f=>{checks++;assert.throws(f);};
const leer=n=>JSON.parse(fs.readFileSync(n,'utf8')),dir='../docs/ejemplos/motor-diagramas/';
check(fs.readFileSync('app/motor/contratoDiagramasEquilibrio.ts','utf8').replaceAll('\r\n','\n')===fs.readFileSync('../docs/contratos/contratoDiagramasEquilibrio.ts','utf8').replaceAll('\r\n','\n').replaceAll('../../frontend/app/motor/','./'),'Canonical diagram contract is current');
const cap=lector.leerCapacidadesDiagramas(leer(dir+'motor-diagramas-capacidades.json'));
check(cap.componentes===2&&cap.operaciones.includes('Txy')&&cap.operaciones.includes('Pxy'),'Binary diagram capability independent of assembly size');
const pares=[];
for(const f of fs.readdirSync(dir).filter(f=>f.endsWith('-peticion.json'))){
  const s=leer(dir+f),raw=leer(dir+f.replace('-peticion','-respuesta')),antes=JSON.stringify(raw),r=lector.leerDiagramaEquilibrio(raw,s);pares.push({s,r});
  check(JSON.stringify(raw)===antes,'Reader preserves certificates and exact original data');
  if(!r.puntos.length)continue;
  const c1=datos.curvasDiagrama(r,s.componenteEjeId,'K','Pa'),otro=s.componentes.find(c=>c.id!==s.componenteEjeId).id,c2=datos.curvasDiagrama(r,otro,'degC','bar');
  check(c1.length===r.ramas.reduce((n,b)=>n+b.segmentos.length*2,0),'A separate plotted series for every phase and segment');
  for(const [i,curva]of c1.entries())for(const [k,p]of curva.puntos.entries()){
    const q=c2[i].puntos[k],original=r.puntos.find(q=>q.id===p.puntoId);
    check(p.puntoId===q.puntoId,'Changing axis preserves coexistence pairs and ordering');
    check(Math.abs(p.x+q.x-1)<1e-10,'Other component axis is 1-x or 1-y');
    check(p.valor===(s.corte.tipo==='Txy'?original.T:original.P),'Plot values come from certified points');
    check(Math.abs(q.valor-(s.corte.tipo==='Txy'?p.valor-273.15:p.valor/1e5))<1e-10,'Plot-only unit conversion');
  }
  for(const cambio of [
    x=>x.solicitudId='otra',x=>x.identidad.modelo.id='otro',x=>x.identidad.huellaModelo=null,
    x=>x.condicion.componenteEjeId=999,x=>x.condicion.componentes[0].cas='otro',
    x=>x.puntos[0].P*=1.1,x=>x.puntos[0].T*=1.1,
    x=>x.puntos[0].fases[0].composicionMolar[s.componenteEjeId]+=.1,
    x=>x.puntos[0].fases[0].composicionMolar['999']=0,
    x=>x.puntos[0].fases[0].fraccionMolar=0,
    x=>x.puntos[0].certificado.residuos[0].valor=1,
    x=>x.puntos[0].certificado.residuos.find(q=>q.id==='distincion_fases').valor=0,
    x=>x.puntos[0].certificado.estabilidad.tmMinimo=-1,
    x=>x.puntos[0].certificado.estado='no_cumple',
    x=>x.ramas[0].segmentos[0].puntoIds[0]='inexistente',x=>x.cobertura.intervalosPublicados=[],
  ]){
    // Altering the non-fixed variable can represent another valid equilibrium;
    // no EOS is reimplemented in the reader. Only fixed-condition mutations are
    // required to fail here (plus the other structural/certificate corruptions).
    if(cambio.toString().includes('.P*=')&&s.corte.tipo!=='Txy'||cambio.toString().includes('.T*=')&&s.corte.tipo!=='Pxy')continue;
    const x=structuredClone(r);cambio(x);rechaza(()=>lector.leerDiagramaEquilibrio(x,s));
  }
  const distinto={...s,huellaModeloEsperada:'sha256:otra'};rechaza(()=>lector.leerDiagramaEquilibrio(r,distinto));
  check(JSON.stringify(raw)===antes,'Projections never rewrite original results');
}
const ll=pares.find(p=>p.s.modelo.id==='nrtl-lle-agua-butanol');
check(ll.r.cobertura.huecos.some(h=>h.motivo==='sin_lv_estable'),'Actual competing liquid produces a gap');
const puente=structuredClone(ll.r),b=puente.ramas[0],ids=b.segmentos.flatMap(s=>s.puntoIds);b.segmentos=[{id:'puente-falso',puntoIds:ids,xEje:[Math.min(...puente.puntos.map(p=>p.xEje)),Math.max(...puente.puntos.map(p=>p.xEje))]}];
rechaza(()=>lector.leerDiagramaEquilibrio(puente,ll.s));
const sinMotivo=structuredClone(ll.r);sinMotivo.cobertura.huecos.find(h=>h.motivo==='sin_lv_estable').incidenciaIds=[];rechaza(()=>lector.leerDiagramaEquilibrio(sinMotivo,ll.s));
const nrtl=pares.find(p=>p.s.modelo.id==='nrtl-chemsep'&&p.s.corte.tipo==='Txy'&&p.r.puntosEspeciales.some(e=>e.tipo==='azeotropo')),a=structuredClone(nrtl.r),especial=a.puntosEspeciales.find(p=>p.tipo==='azeotropo'),extremo=a.puntos[0];
check(!!especial,'Real refined azeotrope is available');Object.assign(especial,{puntoId:extremo.id,T:extremo.T,P:extremo.P,xEje:extremo.xEje});rechaza(()=>lector.leerDiagramaEquilibrio(a,nrtl.s));

const base='../docs/ejemplos/motor-v2/motor-ensamblaje-v2-resolver-calentamiento-etanol-agua-',sol=leer(base+'peticion.json'),raw=leer(base+'respuesta.json'),h=cargar('hojasPruebaMultifasico').crearHojasPruebaMultifasico()[0],r=cargar('resultadoEnsamblajeV2').adaptarResultadoV2(h,sol,raw),c=ctx.contextoMuestraEquilibrio(r,'A',3);
const compatible={...c,huellaParametros:nrtl.r.identidad.huellaModelo},marks=datos.marcadoresMuestra(compatible,nrtl.r,sol.componentes[0].id,'K','Pa');
check(marks.estado==='misma_condicion'&&marks.puntos.length===c.fases.length,'Same cut/fingerprint retains all actual phase markers');
check(datos.marcadoresMuestra({...compatible,P:c.P*1.1},nrtl.r,sol.componentes[0].id,'K','Pa').estado==='otra_condicion','Variable P is not projected on a fixed old cut');
check(datos.marcadoresMuestra({...compatible,huellaParametros:null},nrtl.r,sol.componentes[0].id,'K','Pa').estado==='sin_huella','Historical data cannot claim parameter agreement');
check(datos.marcadoresMuestra({...compatible,muestraEnTramoSinCertificar:true},nrtl.r,sol.componentes[0].id,'K','Pa').estado==='sin_certificar','Failed trajectory sample is not overlaid as a verified state');
check(datos.marcadoresMuestra({...compatible,modelo:{id:'mezcla-ideal',version:'1'}},nrtl.r,sol.componentes[0].id,'K','Pa').estado==='otro_modelo','No cross-model overlay');
const original=JSON.stringify(c),s=datos.prepararSolicitudDiagrama(compatible,{tipo:'Txy',P:{valor:c.P,unidad:'Pa'}},sol.componentes[0].id,'exploratoria','test');
check(s.componentes.length===2&&s.huellaModeloEsperada===nrtl.r.identidad.huellaModelo,'Request uses original model/components and expected fingerprint');
check(JSON.stringify(c)===original,'Query preparation never changes physical worksheet inputs');
rechaza(()=>datos.prepararSolicitudDiagrama({...c,componentes:[...c.componentes,{id:999,nombre:'tercero',simbolo:'C'}]},s.corte,s.componenteEjeId,s.resolucion,'test'));
const vig=new datos.VigenciaConsultaDiagrama(),primera=vig.iniciar(),segunda=vig.iniciar();
check(primera.signal.aborted&&!primera.vigente()&&segunda.vigente(),'Old concurrent response loses permission to publish');vig.cancelar();check(!segunda.vigente()&&segunda.signal.aborted,'Unmount/selection change cancels publication');

// Fingerprints are optional for historical results, but strict if published.
const nueva=structuredClone(raw);nueva.resultados.procedenciaModelo=[{volumenIds:['A'],modelo:sol.paquetes[0].modelo,componentesCAS:sol.componentes.map(c=>c.identidadQuimica.cas),huella:nrtl.r.identidad.huellaModelo}];
cargar('lectorEnsamblajeV2').leerResolucionV2(nueva,sol);check(true,'Additive model provenance is accepted');
for(const cambio of [x=>x[0].volumenIds.push('A'),x=>x[0].volumenIds=['ajeno'],x=>x[0].modelo={id:'otro',version:'1'},x=>x[0].componentesCAS.pop(),x=>x[0].huella='',x=>x.length=0]){const z=structuredClone(nueva);cambio(z.resultados.procedenciaModelo);rechaza(()=>cargar('lectorEnsamblajeV2').leerResolucionV2(z,sol));}
const preferencias={...h,vistaEquilibrio:{volumenId:'A',indice:3,ejeId:2,unidadT:'K',unidadP:'kPa'}};
check(cargar('modeloHojaMotor').firmaHoja(h)===cargar('modeloHojaMotor').firmaHoja(preferencias),'Display preferences do not add dynamic specifications or change the physical signature');
const memoria=new datos.MemoriaDiagramas(2),consulta={...nrtl.s,huellaModeloEsperada:nrtl.r.identidad.huellaModelo};
memoria.guardar(consulta,nrtl.r);
const equivalente={...consulta,solicitudId:'otra-solicitud',corte:{tipo:'Txy',P:{valor:101325,unidad:'Pa'}}},guardado=memoria.recuperar(equivalente,nrtl.r.identidad.trazador);
check(guardado.respuesta.solicitudId===nrtl.r.solicitudId&&guardado.solicitud.solicitudId===nrtl.s.solicitudId,'Cache preserves original request/response identities');
guardado.respuesta.puntos[0].T=1;
check(memoria.recuperar(equivalente,nrtl.r.identidad.trazador).respuesta.puntos[0].T!==1,'Cache values are isolated from caller mutation');
check(!memoria.recuperar({...equivalente,huellaModeloEsperada:'otra'},nrtl.r.identidad.trazador),'New parameter fingerprint invalidates cache');
check(!memoria.recuperar({...equivalente,huellaModeloEsperada:undefined},nrtl.r.identidad.trazador),'Unknown fingerprint never reuses a cached physical claim');
check(!memoria.recuperar(equivalente,{id:nrtl.r.identidad.trazador.id,version:'otra'}),'Tracer version invalidates cache');
check(!memoria.recuperar({...equivalente,resolucion:'refinada'},nrtl.r.identidad.trazador),'Numerical profile stays in cache key');
rechaza(()=>memoria.guardar({...consulta,solicitudId:'ajena'},nrtl.r));rechaza(()=>new datos.MemoriaDiagramas(0));
const csv=datos.csvDiagrama(ll.r),lineas=csv.split('\n');
check(lineas.length===1+ll.r.ramas.reduce((n,b)=>n+b.segmentos.reduce((n,s)=>n+s.puntoIds.length,0),0),'CSV contains certified point references only');
check(lineas[0].includes('"T [K]"')&&lineas[0].includes('"P [Pa]"'),'Export retains SI independently of display units');
check(lineas.some(l=>l.includes('lv-1-s1'))&&lineas.some(l=>l.includes('lv-1-s2')),'Export retains gap-separated segments');
if(process.argv.includes('--ui')){
  const dirUI='qa_diagramas_2026_10_15/',fuente=leer(dirUI+'trayectoria-ui.json'),hUI={...h,redTermodinamica:{solicitud:fuente.solicitud,nombres:{}}},rUI=cargar('resultadoEnsamblajeV2').adaptarResultadoV2(hUI,fuente.solicitud,fuente.respuesta),cUI=ctx.contextoMuestraEquilibrio(rUI,'A',41);
  check(rUI.tiempos.length===102,'Original browser trajectory retained with every sample');
  for(const nombre of ['txy','pxy']){
    const json=leer(dirUI+nombre+'-ui.json'),out=lector.leerDiagramaEquilibrio(json.respuesta,json.solicitud);
    check(out.estado==='completo'&&out.puntos.length>=41,'Actual browser export passed the strict point reader');
    check(out.identidad.huellaModelo===cUI.huellaParametros&&json.solicitud.huellaModeloEsperada===cUI.huellaParametros,'Browser uses the exact parameter fingerprint of its trajectory');
    check(JSON.stringify(json.solicitud.componentes)===JSON.stringify(cUI.componentes),'Browser retains all original component identities');
    const marks=datos.marcadoresMuestra(cUI,out,json.solicitud.componenteEjeId,'K','Pa');
    check(marks.estado==='misma_condicion'&&marks.puntos.length===2,'Both actual liquid/vapor markers belong to the computed cut');
    for(const m of marks.puntos){const f=cUI.fases.find(f=>f.id===m.faseId);check(m.x===f.composicionMolar[json.solicitud.componenteEjeId],'Marker is the original phase composition, not beta or component partition');}
    check(out.puntos.every(p=>p.certificado.estado==='cumple'&&p.certificado.estabilidad.estado==='estable'),'Every browser point carries its backend certificate');
  }
}
console.log(`${checks} comprobaciones de diagramas: respuestas reales, fases límite, certificados, ramas/huecos, unidades, huellas, marcadores y respuestas obsoletas. No recalcula la ecuación de estado.`);
