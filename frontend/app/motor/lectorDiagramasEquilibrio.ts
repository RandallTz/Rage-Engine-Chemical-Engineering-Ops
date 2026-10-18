import type {CapacidadesDiagramas,RespuestaDiagrama,SolicitudDiagrama,CertificadoPunto} from './contratoDiagramasEquilibrio';
import {normalizarCantidad} from './contratoTermodinamica';
import {leerCoberturaGrupos} from './coberturaGrupos';
import {textoPublicado,textosPublicados,identificadoresPublicados,dominioPublicado} from './alcancePublicado';
function fallo(m:string):never{throw new Error(`Diagrama de equilibrio incompatible: ${m}.`);}
const texto=(v:unknown):v is string=>typeof v==='string'&&v.length>0;
const fin=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const cerca=(a:number,b:number,tol=1e-9)=>fin(a)&&fin(b)&&Math.abs(a-b)<=tol;
const intervalo=(v:unknown):v is [number,number]=>Array.isArray(v)&&v.length===2&&v.every(fin)&&v[0]>=0&&v[1]<=1&&v[0]<=v[1];
const lista=(v:unknown):v is string[]=>Array.isArray(v)&&v.every(texto)&&new Set(v).size===v.length;
const operaciones=(v:unknown)=>lista(v)&&v.every(x=>['Txy','Pxy'].includes(x));
function composicion(v:Record<string,number>,ids:string[]){return v&&Object.keys(v).length===ids.length&&ids.every(id=>fin(v[id])&&v[id]>=0&&v[id]<=1)&&cerca(ids.reduce((s,id)=>s+v[id],0),1,1e-10);}
export function leerCapacidadesDiagramas(raw:unknown):CapacidadesDiagramas{
  const c=raw as CapacidadesDiagramas;
  if(!c||c.revision!==1||!texto(c.trazador?.id)||!texto(c.trazador.version)||c.componentes!==2||!operaciones(c.operaciones)||!Array.isArray(c.perfiles)||!c.perfiles.length||!Array.isArray(c.paquetes)||!Array.isArray(c.noSoportado))fallo('capacidades');
  if(new Set(c.perfiles.map(p=>p.id)).size!==c.perfiles.length||new Set(c.paquetes.map(p=>JSON.stringify([p.modelo?.id,p.modelo?.version]))).size!==c.paquetes.length)fallo('capacidades duplicadas');
  for(const p of c.perfiles)if(!['exploratoria','refinada'].includes(p.id)||!Number.isInteger(p.puntosBase)||p.puntosBase<2||!Number.isInteger(p.refinamientoMaximo)||p.refinamientoMaximo<0||![p.saltoMaximoT,p.saltoMaximoLnP,p.saltoMaximoComposicion,p.limiteEvaluaciones,p.limiteSegundos,p.toleranciaMu,p.toleranciaEstabilidad].every(x=>fin(x)&&x>0))fallo('perfil numérico');
  for(const p of c.paquetes){
    if(!textoPublicado(p.modelo?.id)||!textoPublicado(p.modelo.version)||!identificadoresPublicados(p.operaciones)||!operaciones(p.operaciones)||!identificadoresPublicados(p.fases)||p.fases.some(f=>!['liquido','vapor'].includes(f))||!identificadoresPublicados(p.componentesCAS)||!dominioPublicado(p.dominio)||!textosPublicados(p.limites)||!Array.isArray(p.combinacionesDetectadas))fallo('alcance de paquete');
    if(p.modelo.id.startsWith('unifac-')&&p.coberturaGrupos===undefined)fallo('UNIFAC sin cobertura de grupos');
    if(p.coberturaGrupos!==undefined){if(!p.modelo.id.startsWith('unifac-'))fallo('cobertura UNIFAC en otra familia');if(p.pares!==null)fallo('cobertura de grupos junto a pares moleculares');leerCoberturaGrupos(p.coberturaGrupos,p.componentesCAS);}
    if(p.pares!==null&&(!Array.isArray(p.pares)||p.pares.some(x=>!identificadoresPublicados(x.componentesCAS)||x.componentesCAS.length!==2||!textoPublicado(x.evidencia)||!textoPublicado(x.procedencia))))fallo('parámetros binarios');
  }
  return c;
}
function certificado(c:CertificadoPunto){
  const ids=['igualdad_mu','normalizacion','condicion_fija','distincion_fases'];
  if(!c||c.estado!=='cumple'||!Array.isArray(c.residuos)||c.residuos.length!==ids.length||new Set(c.residuos.map(q=>q.id)).size!==ids.length)fallo('certificado de punto');
  for(const q of c.residuos)if(!ids.includes(q.id)||q.estado!=='cumple'||!fin(q.valor)||q.valor<0||!fin(q.tolerancia)||q.tolerancia<=0||!texto(q.escala)||(q.id==='distincion_fases'?q.valor<q.tolerancia:q.valor>q.tolerancia))fallo('residuo de punto no certificado');
  const e=c.estabilidad;
  if(!e||e.estado!=='estable'||!fin(e.tmMinimo)||!fin(e.tolerancia)||e.tolerancia<=0||e.tmMinimo < -e.tolerancia||!lista(e.candidatas)||!['liquido','vapor'].every(f=>e.candidatas.includes(f as 'liquido'|'vapor'))||!Number.isInteger(e.pruebas)||e.pruebas<1||!texto(e.metodo)||e.competidora)fallo('estabilidad de coexistencia');
}
function union(xs:[number,number][]){const out:[number,number][]=[];for(const x of [...xs].sort((a,b)=>a[0]-b[0])){const last=out.at(-1);if(last&&x[0]<=last[1]+1e-9)last[1]=Math.max(last[1],x[1]);else out.push([...x]);}return out;}
export function leerDiagramaEquilibrio(raw:unknown,s:SolicitudDiagrama):RespuestaDiagrama{
  const r=raw as RespuestaDiagrama;
  if(!r||r.revision!==1||r.solicitudId!==s.solicitudId||!['completo','parcial','incompleto','invalido','no_soportado','no_convergente'].includes(r.estado)||!r.identidad||!texto(r.identidad.trazador?.id)||!texto(r.identidad.trazador.version)||![r.ramas,r.puntos,r.puntosEspeciales,r.candidatosDescartados,r.incidencias,r.diagnosticos].every(Array.isArray))fallo('identidad o estructura');
  for(const d of r.diagnosticos)if(!texto(d.codigo)||!texto(d.ruta)||!texto(d.mensaje)||!['invalido','incompleto','no_soportado','aviso'].includes(d.estado)||!Array.isArray(d.componenteIds))fallo('diagnóstico sin referencia');
  if(['invalido','incompleto','no_soportado'].includes(r.estado)){
    if(r.puntos.length||r.ramas.length||r.puntosEspeciales.length||r.cobertura!==null||!r.diagnosticos.length)fallo('rechazo con resultados');return r;
  }
  const c=r.condicion,ids=s.componentes.map(c=>String(c.id));
  if(s.componentes.length!==2||new Set(ids).size!==2||!c||r.identidad.modelo?.id!==s.modelo.id||r.identidad.modelo.version!==s.modelo.version||!texto(r.identidad.huellaModelo)||!texto(r.identidad.firmaConsulta)||s.huellaModeloEsperada&&s.huellaModeloEsperada!==r.identidad.huellaModelo||!texto(r.metodo)||!r.evidencia||!texto(r.evidencia.nivel)||!texto(r.evidencia.motivo))fallo('modelo, huella o evidencia');
  if(c.componenteEjeId!==s.componenteEjeId||!ids.includes(String(c.componenteEjeId))||c.resolucion!==s.resolucion||!intervalo(c.intervaloComposicion)||c.intervaloComposicion.some((x,i)=>x!==s.intervaloComposicion[i])||!Array.isArray(c.componentes)||c.componentes.length!==2||new Set(c.componentes.map(c=>c.id)).size!==2||c.componentes.some(q=>s.componentes.find(x=>x.id===q.id)?.identidadQuimica?.cas!==q.cas))fallo('componentes o condición solicitada');
  const fijo=s.corte.tipo==='Txy'?normalizarCantidad(s.corte.P,'P'):normalizarCantidad(s.corte.T,'T'),tipo=s.corte.tipo;
  if(c.corte?.tipo!==tipo||c.corteSI?.tipo!==tipo||!cerca(tipo==='Txy'?(c.corteSI as {P:number}).P:(c.corteSI as {T:number}).T,fijo,64*Number.EPSILON*fijo))fallo('corte normalizado');
  const original=c.corte.tipo==='Txy'?normalizarCantidad(c.corte.P,'P'):normalizarCantidad(c.corte.T,'T');if(!cerca(original,fijo,64*Number.EPSILON*fijo))fallo('corte original');
  const puntoIds=new Set(r.puntos.map(p=>p.id));if(puntoIds.size!==r.puntos.length)fallo('puntos duplicados');
  for(const p of r.puntos){
    if(!texto(p.id)||!fin(p.T)||p.T<=0||!fin(p.P)||p.P<=0||!fin(p.xEje)||p.xEje<s.intervaloComposicion[0]-1e-9||p.xEje>s.intervaloComposicion[1]+1e-9||!Array.isArray(p.fases)||p.fases.length!==2||!['extremo_puro','continuacion','refinamiento','semilla_por_flash','singular'].includes(p.origen))fallo('punto o dominio de composición');
    if(new Set(p.fases.map(f=>f.id)).size!==2||new Set(p.fases.map(f=>f.tipo)).size!==2||p.fases.some(f=>f.id!==`${f.tipo}-limite`||!['liquido','vapor'].includes(f.tipo)||!composicion(f.composicionMolar,ids)||'fraccionMolar'in f||'fraccionMasica'in f||'fraccionVolumen'in f))fallo('fases límite o composición');
    if(!cerca(p.fases.find(f=>f.tipo==='liquido')!.composicionMolar[s.componenteEjeId],p.xEje,1e-12))fallo('componente del eje');
    certificado(p.certificado);
    const tol=p.certificado.residuos.find(q=>q.id==='condicion_fija')!.tolerancia;
    if(Math.abs((tipo==='Txy'?p.P:p.T)-fijo)>Math.max(tol,64*Number.EPSILON)*fijo)fallo('punto de otro corte');
  }
  const incidencias=new Set(r.incidencias.map(i=>i.id));if(incidencias.size!==r.incidencias.length)fallo('incidencias duplicadas');
  for(const i of r.incidencias)if(!texto(i.id)||!['no_convergente','fase_competidora','fuera_de_dominio','region_critica','presupuesto','extremo_no_evaluable','rama_ambigua'].includes(i.tipo)||!intervalo(i.intervaloXEje)||!texto(i.causa)||!texto(i.accion)||!lista(i.referencias))fallo('incidencia');
  for(const q of r.candidatosDescartados)if(!fin(q.xEje)||q.xEje<0||q.xEje>1||q.T!==null&&(!fin(q.T)||q.T<=0)||q.P!==null&&(!fin(q.P)||q.P<=0)||!texto(q.motivo)||!incidencias.has(q.incidenciaId))fallo('candidato descartado');
  const a=r.cobertura;if(!a||!intervalo(a.intervaloPedido)||a.intervaloPedido.some((x,i)=>x!==s.intervaloComposicion[i])||!Array.isArray(a.intervalosPublicados)||!a.intervalosPublicados.every(intervalo)||!Array.isArray(a.huecos)||!['recorrido_completo','presupuesto','sin_semilla'].includes(a.finalizacion))fallo('cobertura');
  for(const h of a.huecos){
    if(!intervalo(h.intervaloXEje)||h.intervaloXEje[0]<s.intervaloComposicion[0]-1e-9||h.intervaloXEje[1]>s.intervaloComposicion[1]+1e-9||!['sin_lv_estable','no_convergente','fuera_de_dominio','presupuesto','no_explorado'].includes(h.motivo)||!lista(h.incidenciaIds)||!h.incidenciaIds.length||h.incidenciaIds.some(id=>!incidencias.has(id)))fallo('hueco de cobertura');
    if(h.motivo==='sin_lv_estable'&&!h.incidenciaIds.some(id=>r.incidencias.find(i=>i.id===id)?.tipo==='fase_competidora'))fallo('ausencia de LV estable sin incidencia de fase competidora');
  }
  const rangos:[number,number][]=[],referidos=new Set<string>(),segmentos=new Set<string>(),ramas=new Set<string>();
  for(const rama of r.ramas){if(!texto(rama.id)||ramas.has(rama.id)||rama.tipo!=='LV'||!Array.isArray(rama.segmentos))fallo('rama');ramas.add(rama.id);
    for(const seg of rama.segmentos){if(!texto(seg.id)||segmentos.has(seg.id)||!intervalo(seg.xEje)||!lista(seg.puntoIds)||!seg.puntoIds.length||seg.puntoIds.some(id=>!puntoIds.has(id)))fallo('segmento o referencias');segmentos.add(seg.id);
      const xs=seg.puntoIds.map(id=>r.puntos.find(p=>p.id===id)!.xEje);if(!cerca(Math.min(...xs),seg.xEje[0])||!cerca(Math.max(...xs),seg.xEje[1]))fallo('intervalo del segmento');
      for(const h of a.huecos)if(Math.max(seg.xEje[0],h.intervaloXEje[0])<Math.min(seg.xEje[1],h.intervaloXEje[1])-1e-9)fallo('segmento que atraviesa un hueco');
      rangos.push(seg.xEje);seg.puntoIds.forEach(id=>referidos.add(id));
    }
  }
  if(r.puntos.some(p=>!referidos.has(p.id)))fallo('punto certificado sin segmento');
  const u=union(rangos),publicados=union(a.intervalosPublicados);
  if(u.length!==publicados.length||u.some((p,i)=>p.some((x,j)=>!cerca(x,publicados[i][j]))))fallo('cobertura distinta de los segmentos');
  const explorados=union([...rangos,...a.huecos.map(h=>h.intervaloXEje)]);
  if(r.estado==='completo'&&(a.huecos.some(h=>h.motivo!=='sin_lv_estable')||a.finalizacion!=='recorrido_completo'||explorados.length!==1||explorados[0].some((x,i)=>!cerca(x,s.intervaloComposicion[i]))))fallo('completo sin cubrir el intervalo');
  const pres=a.presupuesto,rep=a.reproducibilidad;
  if(!pres||![pres.evaluaciones,pres.limiteEvaluaciones,pres.segundos,pres.limiteSegundos].every(x=>fin(x)&&x>=0)||pres.limiteEvaluaciones<=0||pres.limiteSegundos<=0||!rep||!Number.isInteger(rep.puntosComparados)||rep.puntosComparados<0||[rep.maxDiferenciaCondicion,rep.maxDiferenciaComposicion].some(x=>x!==null&&(!fin(x)||x<0)))fallo('presupuesto o reproducibilidad');
  const especiales=new Set<string>();
  for(const p of r.puntosEspeciales){if(!texto(p.id)||especiales.has(p.id)||!['extremo_puro','azeotropo','limite_dominio','encuentro_otra_fase'].includes(p.tipo)||!fin(p.T)||p.T<=0||!fin(p.P)||p.P<=0||!fin(p.xEje)||p.xEje<0||p.xEje>1||!texto(p.descripcion)||p.puntoId!==undefined&&!puntoIds.has(p.puntoId))fallo('punto especial');especiales.add(p.id);
    if(p.puntoId){const q=r.puntos.find(q=>q.id===p.puntoId)!;if(!cerca(p.T,q.T,1e-6)||!cerca(p.P,q.P,1e-3)||!cerca(p.xEje,q.xEje))fallo('punto especial distinto de su referencia');
      if(p.tipo==='azeotropo'&&(p.xEje<=0||p.xEje>=1||!cerca(q.fases[0].composicionMolar[s.componenteEjeId],q.fases[1].composicionMolar[s.componenteEjeId],1e-7)))fallo('azeótropo sin coincidencia de composiciones');}
  }
  return r;
}
