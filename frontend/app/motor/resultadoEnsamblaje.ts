import type {HojaMotor,GraficaMotor} from './hojasMotor';
import type {SolicitudEnsamblajeDinamico,RespuestaResolucionDinamica} from './contratoEnsamblajeTermodinamico';
import type {ResultadoMotor} from './modeloNumerico';
import {validarResolucionEnsamblaje} from './lectorEnsamblajeTermodinamico';
import {firmaHoja} from './modeloHojaMotor';
import {fraccionesFaseGraficas} from './fraccionesFaseGraficas';
/** User-facing status only. The original diagnosis remains in the full response. */
export function mensajeResultadoDinamico(r:RespuestaResolucionDinamica){
  if(r.estado==='resuelto')return 'Trayectoria resuelta.';
  if(r.estado!=='parcial')return r.validacion.diagnosticos[0]?.mensaje??'No hay una trayectoria resuelta.';
  const d=r.validacion.diagnosticos.find(d=>d.codigo.startsWith('MOTOR_ENS_DETENIDO_'));
  return d?.codigo==='MOTOR_ENS_DETENIDO_CAMBIO_FASE_PROHIBIDO'?'El cambio de fase está desactivado. Cálculo detenido.':d?.mensaje??'Trayectoria parcial. Revisa sus eventos.';
}
export function nombreSerieDinamica(id:string,s:SolicitudEnsamblajeDinamico){
  const componente=s.componentes.find(c=>id.endsWith(`.m.${c.id}`));if(componente)return `Masa · ${componente.nombre}`;
  const nombres:Record<string,string>={U:'Energía interna',H:'Entalpía total',T:'Temperatura',P:'Presión',V:'Volumen ocupado',q:'Fracción másica de vapor',Q:'Calor hacia el volumen',W:'Trabajo de frontera acumulado',F:'Caudal',h:'Entalpía del donante'};
  const nombre=nombres[id.split('.').at(-1)!]??id;return id.startsWith('corriente.')?`${nombre} · corriente ${id.split('.')[1]}`:nombre;
}
/** Reuse the plot/table container, preserving backend IDs, SI values and complete certificates.
 * No local integration, reconstruction of missing series or rounded values. */
export function adaptarResultadoEnsamblaje(h:HojaMotor,s:SolicitudEnsamblajeDinamico,raw:RespuestaResolucionDinamica):ResultadoMotor{
  const r=validarResolucionEnsamblaje(raw,s),a=r.resultados;if(!a||!['resuelto','parcial'].includes(r.estado))throw new Error(r.validacion.diagnosticos[0]?.mensaje??'No hay una trayectoria certificada.');
  const estados=r.validacion.variables.filter(v=>v.papel==='diferencial'&&a.series.some(q=>q.variableId===v.id));
  return {version:1,motor:'motor-ensamblaje-backend-1',modo:'temporal',metodo:a.metodo,tiempos:a.tiempos,x:[],dx:1,valores:a.tiempos.map((_,k)=>estados.map(v=>[a.series.find(q=>q.variableId===v.id)!.valores[k]])),componentes:s.componentes.map(c=>({id:c.id,nombre:c.nombre,simbolo:c.simbolo})),estado:r.estado as 'resuelto'|'parcial',mensaje:mensajeResultadoDinamico(r),pasos:0,rechazados:0,conservacion:[],unidadEstado:'mixta',firma:firmaHoja(h),balancesEjecutados:['materia','energia'],seriesEvaluadas:a.series.map(q=>({id:q.variableId,nombre:nombreSerieDinamica(q.variableId,s),unidad:q.unidadSI,grupo:q.variableId.startsWith('corriente.')?`Corriente ${q.variableId.split('.')[1]}`:['T','P','V','q'].includes(q.variableId.split('.').at(-1)!)?'Estado':'Balances',valores:q.valores})),ensamblajeTermodinamico:{solicitud:s,respuesta:r}};
}
export function validarResultadoDinamico(r:ResultadoMotor){
  const e=r.ensamblajeTermodinamico;if(!e)return;
  const a=validarResolucionEnsamblaje(e.respuesta,e.solicitud).resultados;
  if(!a||JSON.stringify(r.tiempos)!==JSON.stringify(a.tiempos)||r.seriesEvaluadas?.length!==a.series.length||a.series.some(q=>{const v=r.seriesEvaluadas?.find(v=>v.id===q.variableId);return !v||v.unidad!==q.unidadSI||JSON.stringify(v.valores)!==JSON.stringify(q.valores);} ))throw new Error('El resultado guardado no coincide con la trayectoria certificada. Vuelve a resolver.');
}
export function graficasInicialesDinamicas(r:ResultadoMotor):GraficaMotor[]{
  const datos=r.ensamblajeTermodinamico!,s=datos.solicitud,root=`volumen.${s.volumen.id}.`,bifasico=datos.respuesta.resultados!.estadosTermodinamicos.some(e=>e.fases.length>1),extra=bifasico?root+'q':s.volumen.frontera.tipo==='rigida'?root+'P':root+`m.${s.volumen.componenteIds[0]}`;
  return [root+'T',extra].filter(id=>r.seriesEvaluadas!.some(q=>q.id===id)).map((id,i)=>({id:`dinamica-${i}`,nombre:id===root+'q'?'Fracciones másicas por fase':nombreSerieDinamica(id,s),tipo:'tiempo',x:'t',y:id===root+'q'?[id,...fraccionesFaseGraficas(r).map(v=>v.id)]:[id],ancha:false,altura:310,instante:r.tiempos.length-1}));
}
