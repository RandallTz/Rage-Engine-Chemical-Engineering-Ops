import type {CapacidadesEnsamblaje,SolicitudEnsamblajeDinamico,RespuestaValidacionDinamica,RespuestaResolucionDinamica} from './contratoEnsamblajeTermodinamico';
import type {EvaluacionEstado} from './contratoTermodinamica';
import {validarRespuestaEstado} from './contratoTermodinamica';
import {convertirUnidad} from './unidadesMotor';
import {analizarExpresion,evaluarExpresion} from './expresionesMotor';
const fallo=(m:string):never=>{throw new Error(`Respuesta de ensamblaje incompatible: ${m}`);};
const finito=(n:unknown):n is number=>typeof n==='number'&&Number.isFinite(n);
const cerca=(a:number,b:number)=>Math.abs(a-b)<=1e-7*Math.max(Math.abs(a),Math.abs(b),1);
export function validarCapacidadesEnsamblaje(raw:unknown):CapacidadesEnsamblaje{
  const c=raw as CapacidadesEnsamblaje;
  if(!c||c.revision!==1||typeof c.disponible!=='boolean'||!Array.isArray(c.modelos)||c.modelos.some(m=>!m.id||!m.version)||!Array.isArray(c.componentesCAS)||!Number.isInteger(c.volumenes)||!Number.isInteger(c.componentes)||!c.balances||!c.formas||!Array.isArray(c.fronteras)||c.fronteras.some(f=>!['rigida','presion_prescrita'].includes(f))||!c.inicializaciones||!c.presionPrescrita||!c.corrientes||!c.fases||!Array.isArray(c.extracciones)||!Array.isArray(c.integradores)||c.integradores.some(m=>m.id!=='rk45'||!m.nombre)||!Number.isInteger(c.muestrasMaximas)||c.muestrasMaximas<2||c.expresiones?.unidadTiempo!=='s'||!Array.isArray(c.expresiones.suaves)||!Array.isArray(c.expresiones.noAdmitidas)||c.dinamicaApiPuntual!==false)fallo('capacidades incompletas.');
  return c;
}
/** Reuse the property protocol reader; no flash, phase assignment or property correlation here. */
function comprobarEstado(e:EvaluacionEstado,s:SolicitudEnsamblajeDinamico,fronteraDePolitica=false){
  if(!e?.mezcla)fallo('estado termodinámico ausente.');
  validarRespuestaEstado({revision:1,solicitudId:s.solicitudId,modelo:s.volumen.cierre.modelo,estado:'evaluado',evaluacion:e,diagnosticos:[]},{revision:1,solicitudId:s.solicitudId,propietarioId:`volumen:${s.volumen.id}`,componentes:s.componentes,declaracion:{modelo:s.volumen.cierre.modelo,politica:fronteraDePolitica?{...s.volumen.cierre.politica,cantidad:'sin_restriccion',tiposPermitidos:undefined}:s.volumen.cierre.politica,especificacion:{tipo:'UV',U:{valor:e.mezcla.u,unidad:'J'},V:{valor:e.mezcla.v,unidad:'m3'},cantidades:{base:'masica',valores:Object.fromEntries(s.componentes.map(c=>[c.id,{valor:e.composicionMolar[c.id],unidad:'kg'}]))}}}});
}
function reconstruir(e:EvaluacionEstado,s:SolicitudEnsamblajeDinamico,variables:Record<string,number>,fronteraDePolitica=false){
  comprobarEstado(e,s,fronteraDePolitica);
  const root=`volumen.${s.volumen.id}.`,m=s.volumen.componenteIds.reduce((sum,id)=>sum+variables[`${root}m.${id}`],0),U=variables[root+'U'],V=variables[root+'V'];
  if(!finito(m)||m<=0||!finito(U)||!finito(V)||V<=0||!cerca(U,m*e.mezcla.u)||!cerca(V,m*e.mezcla.v)||!cerca(variables[root+'T'],e.T)||!cerca(variables[root+'P'],e.P))fallo('series y estado termodinámico no coinciden.');
  const q=e.fases.filter(f=>f.tipo==='vapor').reduce((sum,f)=>sum+f.fraccionMasica,0);
  if(!cerca(variables[root+'q'],q))fallo('fracción de vapor incompatible.');
  if(variables[root+'H']!==undefined&&!cerca(variables[root+'H'],U+e.P*V))fallo('H no coincide con U+PV.');
}
export function validarRespuestaEnsamblaje(raw:unknown,s:SolicitudEnsamblajeDinamico):RespuestaValidacionDinamica{
  const r=raw as RespuestaValidacionDinamica;
  if(!r||r.revision!==1||r.solicitudId!==s.solicitudId||r.modeloId!==null&&(typeof r.modeloId!=='string'||!r.modeloId.startsWith('ens-'))||!r.recuento||!['listo','incompleto','conflicto','redundante_compatible','no_evaluable'].includes(r.recuento.estado)||!['estructural','rango_numerico','no_evaluable'].includes(r.recuento.analisis)||!Array.isArray(r.variables)||!Array.isArray(r.ecuaciones)||!Array.isArray(r.diagnosticos)||!r.inicializacion)fallo('identidad o forma de validación.');
  for(const k of ['variables','ecuacionesIndependientes','datosDefinidos','datosFaltantes','inicialesFaltantes','gradosLibertad'] as const){const n=r.recuento[k];if(n!==null&&(!Number.isInteger(n)||k!=='gradosLibertad'&&n<0))fallo('recuento no válido.');}
  const ids=new Set(r.variables.map(v=>v.id));if(ids.size!==r.variables.length||new Set(r.ecuaciones.map(e=>e.id)).size!==r.ecuaciones.length)fallo('identificadores repetidos.');
  for(const v of r.variables)if(!v.id||!v.propietarioId||!v.magnitud||!v.unidadSI||!['diferencial','algebraica','dato','parametro'].includes(v.papel)||v.datoId&&!s.datos[v.datoId])fallo('variable o referencia desconocida.');
  for(const e of r.ecuaciones)if(!e.id||!e.propietarioId||!['materia','energia','estado','mecanica'].includes(e.familia)||!e.latex||!e.unidadResiduo||!Array.isArray(e.variableIds)||e.variableIds.some(id=>!ids.has(id)&&!Object.hasOwn(s.datos,id)))fallo('ecuación o referencia desconocida.');
  for(const d of r.diagnosticos)if(!d.codigo||!d.mensaje||!['incompleto','conflicto','no_soportado','invalido'].includes(d.estado)||!Array.isArray(d.variableIds)||!d.origen?.ruta||!d.origen.propietarioId)fallo('diagnóstico sin origen.');
  if(!['pendiente','compatible','incompatible','no_soportada'].includes(r.inicializacion.estado)||!r.inicializacion.variables||Object.values(r.inicializacion.variables).some(n=>!finito(n)))fallo('inicialización inválida.');
  if(r.inicializacion.estado==='compatible'){
    if(!r.inicializacion.estadoTermodinamico)fallo('inicialización sin estado certificado.');
    reconstruir(r.inicializacion.estadoTermodinamico!,s,r.inicializacion.variables);
  }else if(r.inicializacion.estadoTermodinamico!==null)fallo('inicialización rechazada con estado calculado.');
  if(r.recuento.estado==='listo'&&(r.recuento.datosFaltantes!==0||r.recuento.inicialesFaltantes!==0||r.recuento.gradosLibertad!==0||!r.modeloId))fallo('listo con datos pendientes.');
  return r;
}
export function validarResolucionEnsamblaje(raw:unknown,s:SolicitudEnsamblajeDinamico,modeloId?:string):RespuestaResolucionDinamica{
  const r=raw as RespuestaResolucionDinamica;if(!r||!['resuelto','parcial','invalido','no_convergente','no_soportado'].includes(r.estado))fallo('estado de cálculo desconocido.');
  validarRespuestaEnsamblaje(r.validacion,s);
  if(modeloId&&r.validacion.modeloId!==modeloId)fallo('modelo distinto del validado.');
  if(!['resuelto','parcial'].includes(r.estado)){if(r.resultados!==null)fallo('rechazo con resultados antiguos.');return r;}
  const a=r.resultados;if(!a||!a.metodo||!Array.isArray(a.tiempos)||!a.tiempos.length||a.tiempos.some((t,i)=>!finito(t)||t<0||i>0&&t<=a.tiempos[i-1])||!cerca(a.tiempos[0],0)||!Array.isArray(a.series)||!Array.isArray(a.estadosTermodinamicos)||a.estadosTermodinamicos.length!==a.tiempos.length||!Array.isArray(a.eventos)||!Array.isArray(a.residuos)||r.validacion.inicializacion.estado!=='compatible'||r.validacion.recuento.estado!=='listo')fallo('trayectoria o validación incompleta.');
  const out=a!,ids=new Set(r.validacion.variables.map(v=>v.id));
  if(new Set(out.series.map(q=>q.variableId)).size!==out.series.length)fallo('serie repetida.');
  for(const q of out.series)if(!ids.has(q.variableId)||!q.unidadSI||!Array.isArray(q.valores)||q.valores.length!==out.tiempos.length||q.valores.some(n=>!finito(n))||r.validacion.variables.find(v=>v.id===q.variableId)?.unidadSI!==q.unidadSI)fallo('serie, valores o unidad incompatible.');
  // A partial trajectory can publish the certified phase-transition endpoint that
  // stops it. This is an event boundary, never permission to continue beyond it.
  out.estadosTermodinamicos.forEach((e,k)=>{
    const frontera=r.estado==='parcial'&&k===out.tiempos.length-1&&r.validacion.diagnosticos.some(d=>d.codigo.startsWith('MOTOR_ENS_DETENIDO_'))&&out.eventos.some(v=>['aparicion_fase','desaparicion_fase'].includes(v.codigo)&&cerca(v.tiempo,out.tiempos[k]));
    reconstruir(e,s,Object.fromEntries(out.series.map(q=>[q.variableId,q.valores[k]])),frontera);
  });
  const tf=s.datos[s.estudio.tiempoId];const final=convertirUnidad(tf.magnitud,evaluarExpresion(analizarExpresion(tf.declaracion.texto,[]),{}),tf.declaracion.unidad);
  if(out.tiempos.at(-1)!>final+1e-7*Math.max(1,final)||r.estado==='resuelto'&&!cerca(out.tiempos.at(-1)!,final))fallo('horizonte de trayectoria incompatible.');
  for(const e of out.eventos)if(!e.codigo||!finito(e.tiempo)||e.tiempo<0||e.tiempo>final||!Array.isArray(e.variableIds))fallo('evento incompatible.');
  for(const e of out.residuos)if(!e.ecuacionId||!finito(e.maximoEscalado)||e.maximoEscalado<0||!finito(e.tolerancia)||e.tolerancia<=0)fallo('residuo incompatible.');
  return r;
}
