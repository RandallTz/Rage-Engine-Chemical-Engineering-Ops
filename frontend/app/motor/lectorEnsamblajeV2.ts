import type {CapacidadesEnsamblajeV2,RespuestaValidacionV2,RespuestaResolucionV2,SolicitudEnsamblajeV2,EstadoVolumenV2} from './contratoEnsamblajeV2';
import {validarRespuestaEstado} from './contratoTermodinamica';
import {analizarExpresion,evaluarExpresion} from './expresionesMotor';
import {convertirUnidad} from './unidadesMotor';
import {validarMetadatosRed} from './validarMetadatosRed';
import {unidadesEstadoVolumen,verificarPotencialesComponentes} from './verificarEstadoMateriaRed';
import {claveModelo} from './modelosTermodinamicos';
import {leerCoberturaGrupos} from './coberturaGrupos';
import {textoPublicado,textosPublicados,identificadoresPublicados,dominioPublicado,cantidadMaximaPublicada} from './alcancePublicado';
const fallo=(m:string):never=>{throw new Error(`Respuesta multifásica incompatible: ${m}`);};
const fin=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const cerca=(a:number,b:number)=>fin(a)&&fin(b)&&Math.abs(a-b)<=1e-6*Math.max(1,Math.abs(a),Math.abs(b));
export function leerCapacidadesV2(raw:unknown):CapacidadesEnsamblajeV2{
  const c=raw as CapacidadesEnsamblajeV2;
  if(!c||c.revision!==2||!Array.isArray(c.revisionesAdmitidas)||!c.revisionesAdmitidas.includes(2)||typeof c.disponible!=='boolean'||!Array.isArray(c.paquetes)||!cantidadMaximaPublicada(c.volumenesMaximos,c.disponible)||!cantidadMaximaPublicada(c.componentesMaximos,c.disponible)||!Array.isArray(c.fronteras)||!Array.isArray(c.integradores)||!c.corrientes||!Array.isArray(c.intercambiosTermicos)||!Array.isArray(c.noSoportado))fallo('capacidades incompletas');
  for(const p of c.paquetes){
    if(!p||!textoPublicado(p.modelo?.id)||!textoPublicado(p.modelo.version)||typeof p.dinamica!=='boolean'||!identificadoresPublicados(p.operaciones)||p.operaciones.some(x=>!['TP','PH','UP','UV','TV'].includes(x))||!identificadoresPublicados(p.fases)||p.fases.some(x=>!['liquido','vapor','solido','fluido'].includes(x))||!Array.isArray(p.combinaciones))fallo('paquete sin alcance');
    if(p.componentesCAS!==undefined&&!identificadoresPublicados(p.componentesCAS)||p.dominio!==undefined&&!dominioPublicado(p.dominio)||p.limites!==undefined&&!textosPublicados(p.limites))fallo('catálogo o dominio de paquete inválido');
  }
  if(new Set(c.paquetes.map(p=>claveModelo(p.modelo))).size!==c.paquetes.length)fallo('paquete y versión duplicados');
  if(c.corrientes.entrePaquetes!==undefined&&c.corrientes.entrePaquetes!=='misma_referencia')fallo('compatibilidad de referencias desconocida');
  for(const p of c.paquetes){for(const x of p.combinaciones)if(x.evidencia!==undefined&&!['contrastada','cualitativa','imposible_en_el_modelo','sin_modelo','excluida'].includes(x.evidencia)||typeof x.publicada!=='boolean'||!x.nombre||!x.motivo)fallo('evidencia de combinación');if(p.pares!==undefined&&(!Array.isArray(p.pares)||p.pares.some(x=>!identificadoresPublicados(x.componentesCAS)||x.componentesCAS.length!==2||!textoPublicado(x.procedencia)||!x.evidencia||!textoPublicado(x.motivo))))fallo('pares sin procedencia');}
  for(const p of c.paquetes){
    if(p.modelo.id.startsWith('unifac-')&&p.coberturaGrupos===undefined)fallo('UNIFAC sin cobertura de grupos');
    if(p.coberturaGrupos===undefined)continue;
    if(!p.modelo.id.startsWith('unifac-'))fallo('cobertura UNIFAC en otra familia');
    if(p.combinaciones.some(x=>['liquido_vapor','liquido_liquido'].includes(x.id??'')&&x.evidencia!=='cualitativa'))fallo('evidencia UNIFAC distinta de la publicada');
    if(p.pares!==undefined)fallo('paquete con cobertura de grupos y pares moleculares');
    leerCoberturaGrupos(p.coberturaGrupos,p.componentesCAS);
  }
  if(c.tamanos!==undefined){
    const t=c.tamanos,positivo=(x:unknown)=>Number.isSafeInteger(x)&&Number(x)>0,registro=(x:unknown):x is Record<string,unknown>=>!!x&&typeof x==='object'&&!Array.isArray(x);
    if(!t||typeof t.cuenta!=='string'||!t.cuenta.trim()||!positivo(t.componentesMaximosPorVolumen)||t.componentesMaximosPorVolumen!==c.componentesMaximos||!positivo(t.fasesMaximas)||!registro(t.contrastados)||!registro(t.estabilidad)||typeof t.presupuesto!=='string'||!t.presupuesto.trim())fallo('alcance dimensional incompleto');
    for(const x of Object.values(t.contrastados))if(!x||!Array.isArray(x.estatico)||!Array.isArray(x.dinamico)||[...x.estatico,...x.dinamico].some(n=>!positivo(n)||n>t.componentesMaximosPorVolumen))fallo('tamaños contrastados incompatibles');
    if(Object.values(t.estabilidad).some(x=>typeof x!=='string'||!x.trim()))fallo('método de estabilidad no declarado');
  }
  return c;
}
export function validarEstadoVolumenV2(m:EstadoVolumenV2,s:SolicitudEnsamblajeV2,vid:string,vars:Record<string,number>,fronteraEvento=false){
  const v=s.volumenes.find(v=>v.id===vid),paquete=s.paquetes.find(p=>p.id===v?.paqueteId);
  if(!v||!paquete||m.volumenId!==vid||!m.evaluacion)return fallo('propietario o paquete del estado');
  const e=m.evaluacion,root=`volumen.${vid}.`,cantidades=Object.fromEntries(v.componenteIds.map(id=>[id,{valor:vars[root+`n.${id}`],unidad:'mol'}]));
  validarRespuestaEstado({revision:1,solicitudId:s.solicitudId,modelo:paquete.modelo,estado:'evaluado',evaluacion:e,diagnosticos:[]},{revision:1,solicitudId:s.solicitudId,propietarioId:`volumen:${vid}`,componentes:s.componentes.filter(c=>v.componenteIds.includes(c.id)),declaracion:{modelo:paquete.modelo,politica:fronteraEvento?{...v.politica,cantidad:'sin_restriccion',tiposPermitidos:undefined}:v.politica,especificacion:{tipo:'UV',U:{valor:vars[root+'U'],unidad:'J'},V:{valor:vars[root+'V'],unidad:'m3'},cantidades:{base:'molar',valores:cantidades}}}});
  if(!cerca(e.T,vars[root+'T'])||!cerca(e.P,vars[root+'P']))fallo('T/P no coinciden con las series');
  const n=v.componenteIds.reduce((a,id)=>a+vars[root+`n.${id}`],0),M=e.componentes.reduce((a,c)=>a+e.composicionMolar[c.id]*c.masaMolarKgMol,0),masa=n*M;
  if(!cerca(vars[root+'U'],masa*e.mezcla.u)||!cerca(vars[root+'V'],masa*e.mezcla.v)||vars[root+'masa']!==undefined&&!cerca(masa,vars[root+'masa'])||vars[root+'H']!==undefined&&!cerca(vars[root+'H'],vars[root+'U']+e.P*vars[root+'V'])||vars[root+'S']!==undefined&&!cerca(vars[root+'S'],masa*e.mezcla.s))fallo('cantidades/energía/volumen no reconstruyen el estado');
  const p=m.potenciales;
  if(!p||p.base!=='molar'||p.unidad!=='J/mol'||p.referencia?.id!==e.referencia.id||!cerca(p.T,e.T)||!cerca(p.P,e.P)||![p.G,p.A,p.S].every(fin)||!Array.isArray(p.fases)||p.fases.length!==e.fases.length||new Set(p.fases.map(f=>f.faseId)).size!==p.fases.length||p.fases.some(f=>!e.fases.some(q=>q.id===f.faseId)||Object.values(f.mu).some(x=>x!==null&&!fin(x))))fallo('potenciales o identidades de fase incompatibles');
  if(p.unidades!==undefined&&(p.unidades.mu!=='J/mol'||p.unidades.G!=='J'||p.unidades.A!=='J'||p.unidades.S!=='J/K'||!cerca(p.G,masa*(e.mezcla.h-e.T*e.mezcla.s))||!cerca(p.A,masa*(e.mezcla.u-e.T*e.mezcla.s))||!cerca(p.S,masa*e.mezcla.s)))fallo('unidades o reconstrucción de potenciales totales');
  verificarPotencialesComponentes(e,p,v.componenteIds,n);
}
export function leerValidacionV2(raw:unknown,s:SolicitudEnsamblajeV2):RespuestaValidacionV2{
  const r=raw as RespuestaValidacionV2;
  if(!r||r.revision!==2||r.solicitudId!==s.solicitudId||!r.recuento||!['listo','incompleto','conflicto','redundante_compatible','no_evaluable'].includes(r.recuento.estado)||!Array.isArray(r.variables)||!Array.isArray(r.ecuaciones)||!Array.isArray(r.diagnosticos)||!r.inicializacion?.volumenes)fallo('identidad o validación incompleta');
  for(const k of ['variables','ecuacionesIndependientes','datosDefinidos','datosFaltantes','inicialesFaltantes','gradosLibertad'] as const){const n=r.recuento[k];if(n!==null&&(!Number.isInteger(n)||k!=='gradosLibertad'&&n<0))fallo('recuento inválido');}
  const ids=new Set(r.variables.map(v=>v.id));if(ids.size!==r.variables.length||new Set(r.ecuaciones.map(e=>e.id)).size!==r.ecuaciones.length)fallo('IDs duplicados');
  for(const v of r.variables)if(!v.id||!v.unidadSI||!v.propietarioId||!['diferencial','algebraica','dato','parametro'].includes(v.papel)||v.datoId&&!s.datos[v.datoId])fallo('variable desconocida');
  const unidades=Object.assign({},...s.volumenes.map(unidadesEstadoVolumen)) as Record<string,string>;
  for(const v of r.variables)if(unidades[v.id]&&v.unidadSI!==unidades[v.id])fallo(`unidad SI de ${v.id}`);
  for(const e of r.ecuaciones)if(!e.id||!e.latex||!e.procedencia?.relacion||!Array.isArray(e.variableIds)||e.variableIds.some(id=>!ids.has(id)&&!s.datos[id]))fallo('ecuación sin procedencia o referencia');
  for(const d of r.diagnosticos)if(!d.codigo||!d.mensaje||!['incompleto','conflicto','no_soportado','invalido'].includes(d.estado)||!d.origen?.propietarioId||!d.origen.ruta||!Array.isArray(d.variableIds))fallo('diagnóstico sin origen');
  for(const [id,i] of Object.entries(r.inicializacion.volumenes))if(i.estado==='compatible'){if(!i.estadoTermodinamico)fallo('inicial sin certificado');validarEstadoVolumenV2(i.estadoTermodinamico!,s,id,i.variables);}
  if(r.inicializacion.estado==='compatible'&&(Object.keys(r.inicializacion.volumenes).length!==s.volumenes.length||s.volumenes.some(v=>r.inicializacion.volumenes[v.id]?.estado!=='compatible')))fallo('inicialización omite volúmenes');
  const requiereModelo=r.inicializacion.estado==='compatible'||!r.diagnosticos.length;
  if(r.recuento.estado==='listo'&&(!r.modeloId&&requiereModelo||r.recuento.gradosLibertad!==0||r.recuento.datosFaltantes!==0||r.recuento.inicialesFaltantes!==0))fallo('listo sin modelo o datos');
  // A structurally closed model may still lack a thermodynamic parameter. Keep
  // that canonical count and its blocking diagnostic; never certify its state.
  if(r.recuento.estado==='listo'&&r.inicializacion.estado!=='compatible'&&!r.diagnosticos.length)fallo('listo sin inicialización ni diagnóstico');
  return r;
}
export function leerResolucionV2(raw:unknown,s:SolicitudEnsamblajeV2,modeloId?:string):RespuestaResolucionV2{
  const r=raw as RespuestaResolucionV2;
  if(!r||r.revision!==2||!['resuelto','parcial','invalido','no_convergente','no_soportado'].includes(r.estado))fallo('estado de cálculo');
  leerValidacionV2(r.validacion,s);if(modeloId&&r.validacion.modeloId!==modeloId)fallo('modelo distinto del validado');
  if(!['resuelto','parcial'].includes(r.estado)){if(r.resultados!==null)fallo('rechazo con resultados');return r;}
  const a=r.resultados;if(!a||!a.metodo||!Array.isArray(a.tiempos)||!a.tiempos.length||a.tiempos[0]!==0||a.tiempos.some((t,k)=>!fin(t)||k>0&&t<=a.tiempos[k-1])||!Array.isArray(a.series)||!a.estados||!Array.isArray(a.eventos)||!Array.isArray(a.residuos)||r.validacion.recuento.estado!=='listo'||r.validacion.inicializacion.estado!=='compatible')fallo('trayectoria incompleta');
  const out=a!,ids=new Set(out.series.map(v=>v.variableId));if(ids.size!==out.series.length)fallo('series duplicadas');
  const unidades=Object.assign({},...s.volumenes.map(unidadesEstadoVolumen)) as Record<string,string>;
  for(const q of out.series)if(!q.variableId||!q.unidadSI||q.valores.length!==out.tiempos.length||q.valores.some(v=>!fin(v))||unidades[q.variableId]&&q.unidadSI!==unidades[q.variableId]||r.validacion.variables.some(v=>v.id===q.variableId&&v.unidadSI!==q.unidadSI))fallo('serie o unidad inválida');
  if(Object.keys(out.estados).length!==s.volumenes.length)fallo('volúmenes omitidos');
  for(const v of s.volumenes){const es=out.estados[v.id];if(!es||es.length!==out.tiempos.length)fallo('faltan certificados');es.forEach((m,k)=>validarEstadoVolumenV2(m,s,v.id,Object.fromEntries(out.series.map(q=>[q.variableId,q.valores[k]])),esMuestraFronteraEvento(r,v.id,k)));}
  for(const e of out.eventos)if(!e.codigo||!fin(e.tiempo)||e.tiempo<0||e.tiempo>out.tiempos.at(-1)!+1e-6||e.volumenId!==null&&!s.volumenes.some(v=>v.id===e.volumenId)||!Array.isArray(e.faseIds))fallo('evento inválido');
  for(const e of out.residuos)if(!e.ecuacionId||!fin(e.maximoEscalado)||e.maximoEscalado<0||!fin(e.tolerancia)||e.tolerancia<=0||out.certificacion===undefined&&e.maximoEscalado>e.tolerancia)fallo('residuo no certificado');
  if(!out.segundaLey||!['cumple','no_cumple','no_evaluable'].includes(out.segundaLey.estado)||!out.segundaLey.motivo||out.segundaLey.unidad!=='J/K')fallo('segunda ley sin alcance');
  const d=s.datos[s.estudio.tiempoId],tf=convertirUnidad('tiempo',evaluarExpresion(analizarExpresion(d.declaracion.texto,[]),{}),d.declaracion.unidad);
  if(out.tiempos.at(-1)!>tf+1e-6||r.estado==='resuelto'&&!cerca(out.tiempos.at(-1)!,tf))fallo('horizonte incorrecto');
  validarMetadatosRed(r,s);
  return r;
}
export function esMuestraFronteraEvento(r:RespuestaResolucionV2,vid:string,k:number){const a=r.resultados;return !!a&&r.estado==='parcial'&&k===a.tiempos.length-1&&a.eventos.some(e=>['aparicion_fase','desaparicion_fase','sustitucion_fase','cambio_denominacion'].includes(e.codigo)&&e.volumenId===vid&&cerca(e.tiempo,a.tiempos[k]));}
