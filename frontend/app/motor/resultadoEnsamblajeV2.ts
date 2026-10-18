import type {HojaMotor,GraficaMotor} from './hojasMotor';
import type {ResultadoMotor,SerieEvaluadaMotor} from './modeloNumerico';
import type {SolicitudEnsamblajeV2,RespuestaResolucionV2} from './contratoEnsamblajeV2';
import {leerResolucionV2} from './lectorEnsamblajeV2';
import {nombrePapelSerie} from './metadatosRed';
import {firmaHoja} from './modeloHojaMotor';
import type {EvaluacionEstado} from './contratoTermodinamica';
/** Fraction of this component in a phase (same on mass and mole bases).
 * Different denominator from phase composition x_i: theta_i^a = beta_a*x_i^a/z_i.
 * A globally absent component has no defined partition; do not fabricate zero. */
export function repartoComponente(e:EvaluacionEstado,faseId:string,componenteId:number):number{
  const z=e.composicionMolar[componenteId];
  if(!(z>0))return NaN;
  const f=e.fases.find(f=>f.id===faseId);
  return f?f.fraccionMolar*f.composicionMolar[componenteId]/z:0;
}
const titulos:Record<string,string>={T:'Temperatura',P:'Presión',U:'Energía interna',H:'Entalpía total',W:'Trabajo de frontera',V:'Volumen',S:'Entropía',masa:'Masa total',Sgen:'Generación de entropía',Q:'Calor transferido',ndot:'Caudal molar'};
export function nombreSerieV2(id:string,s:SolicitudEnsamblajeV2){const a=id.split('.'),v=a[0]==='volumen'?` · ${a[1]}`:a[0]==='red'?' · red':` · ${a[0]} ${a[1]}`;return a[2]==='n'?`Cantidad · ${s.componentes.find(c=>String(c.id)===a[3])?.nombre??a[3]}${v}`:`${titulos[a.at(-1)!]??id}${v}`;}
export function adaptarResultadoV2(h:HojaMotor,s:SolicitudEnsamblajeV2,raw:RespuestaResolucionV2):ResultadoMotor{
  const r=leerResolucionV2(raw,s),a=r.resultados;if(!a)throw new Error(r.validacion.diagnosticos[0]?.mensaje??'No hay resultados certificados.');
  const estados=r.validacion.variables.filter(v=>v.papel==='diferencial');
  return {version:1,motor:'motor-ensamblaje-backend-2',modo:'temporal',metodo:a.metodo,tiempos:a.tiempos,x:[],dx:1,valores:a.tiempos.map((_,k)=>estados.map(v=>[a.series.find(q=>q.variableId===v.id)!.valores[k]])),componentes:s.componentes.map(c=>({id:c.id,nombre:c.nombre,simbolo:c.simbolo})),estado:r.estado as 'resuelto'|'parcial',mensaje:r.estado==='resuelto'?'Trayectoria resuelta.':r.validacion.diagnosticos[0]?.mensaje??'Trayectoria parcial.',pasos:0,rechazados:0,conservacion:[],unidadEstado:'mixta',firma:firmaHoja(h),balancesEjecutados:['materia','energia'],seriesEvaluadas:a.series.map(q=>{const c=a.catalogoSeries?.find(c=>c.variableId===q.variableId);return {id:q.variableId,nombre:nombreSerieV2(q.variableId,s),unidad:c?.unidadSI??q.unidadSI,grupo:c?`${c.propietarioId} · ${nombrePapelSerie(c.papel)}`:q.variableId.split('.').slice(0,2).join(' · '),valores:q.valores};}),ensamblajeV2:{solicitud:s,respuesta:r}};
}
/** Derived presentation from certified states, not a second flash or persisted solver state.
 * Absent phase fractions are zero; absent compositions/properties remain missing (NaN). */
export function seriesFasesV2(r:ResultadoMotor):SerieEvaluadaMotor[]{
  const e=r.ensamblajeV2;if(!e?.respuesta.resultados)return [];
  const series:SerieEvaluadaMotor[]=[],a=e.respuesta.resultados;
  for(const v of e.solicitud.volumenes){const estados=a.estados[v.id],ids=[...new Set(estados.flatMap(e=>e.evaluacion.fases.map(f=>f.id)))];
    for(const id of ids){const ejemplo=estados.flatMap(e=>e.evaluacion.fases).find(f=>f.id===id)!,nombre=`${ejemplo.tipo} · ${id} · ${v.id}`,grupo=`Fases · ${v.id} · ${id}`,fases=estados.map(e=>e.evaluacion.fases.find(f=>f.id===id));
      for(const [key,label] of [['fraccionMasica','Fracción másica'],['fraccionMolar','Fracción molar'],['fraccionVolumen','Fracción de volumen']] as const)series.push({id:`fase.${v.id}.${id}.${key}`,nombre:`${label} · ${nombre}`,unidad:'1',grupo,valores:fases.map(f=>f?.[key]??0)});
      for(const cid of v.componenteIds){
        const componente=e.solicitud.componentes.find(c=>c.id===cid)?.nombre??String(cid);
        series.push({id:`fase.${v.id}.${id}.x.${cid}`,nombre:`Composición molar de fase · ${componente} · ${nombre}`,unidad:'1',grupo,valores:fases.map(f=>f?.composicionMolar[cid]??NaN)});
        series.push({id:`fase.${v.id}.${id}.reparto.${cid}`,nombre:`Fracción de ${componente} en ${nombre}`,unidad:'1',grupo:`Reparto · ${v.id} · ${componente}`,valores:estados.map(e=>repartoComponente(e.evaluacion,id,cid))});
      }
      for(const key of ['u','h','v','s'] as const)series.push({id:`fase.${v.id}.${id}.${key}`,nombre:`${{u:'Energía interna específica',h:'Entalpía específica',v:'Volumen específico',s:'Entropía específica'}[key]} · ${nombre}`,unidad:{u:'J/kg',h:'J/kg',v:'m3/kg',s:'J/(kg K)'}[key],grupo,valores:fases.map(f=>f?.propiedades[key]??NaN)});
    }
  }return series;
}
/** Optional comparison plots. Stable IDs let the board add only missing plots,
 * preserving custom curves, layout and names on repeated clicks. */
export function graficasComponentesV2(r:ResultadoMotor):GraficaMotor[]{
  const s=r.ensamblajeV2?.solicitud;if(!s)return [];
  const series=seriesFasesV2(r);
  return s.volumenes.flatMap(v=>v.componenteIds.map(cid=>({id:`reparto-${v.id}-${cid}`,nombre:`Reparto de ${s.componentes.find(c=>c.id===cid)?.nombre??cid} · ${v.id}`,tipo:'tiempo' as const,x:'t',y:series.filter(q=>q.id.startsWith(`fase.${v.id}.`)&&q.id.endsWith(`.reparto.${cid}`)).map(q=>q.id),ancha:false,altura:310,instante:r.tiempos.length-1})));
}
export function validarResultadoV2(r:ResultadoMotor){const e=r.ensamblajeV2;if(!e)return;const a=leerResolucionV2(e.respuesta,e.solicitud).resultados;if(!a||JSON.stringify(r.tiempos)!==JSON.stringify(a.tiempos)||r.seriesEvaluadas?.length!==a.series.length||a.series.some(q=>{const s=r.seriesEvaluadas?.find(v=>v.id===q.variableId);return !s||s.unidad!==q.unidadSI||JSON.stringify(s.valores)!==JSON.stringify(q.valores);}))throw new Error('El resultado guardado no coincide con la trayectoria certificada.');}
export function graficasInicialesV2(r:ResultadoMotor):GraficaMotor[]{
  const s=r.ensamblajeV2!.solicitud,base={tipo:'tiempo' as const,x:'t',ancha:false,altura:310,instante:r.tiempos.length-1};
  return [{...base,id:'temperaturas-v2',nombre:'Temperaturas',y:s.volumenes.map(v=>`volumen.${v.id}.T`)},{...base,id:'presiones-v2',nombre:'Presiones',y:s.volumenes.map(v=>`volumen.${v.id}.P`)},...s.volumenes.map(v=>({...base,id:`fases-${v.id}`,nombre:`Fracciones másicas · ${v.id}`,y:seriesFasesV2(r).filter(q=>q.id.startsWith(`fase.${v.id}.`)&&q.id.endsWith('.fraccionMasica')).map(q=>q.id)}))];
}
