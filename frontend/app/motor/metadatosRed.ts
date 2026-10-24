import type {RespuestaResolucionV2,SerieCatalogoV2,EvidenciaV2} from './contratoEnsamblajeV2';
type Trayectoria=NonNullable<RespuestaResolucionV2['resultados']>;
export const nombrePapelSerie=(p:SerieCatalogoV2['papel'])=>({estado_integrado:'Integrated state',algebraica:'Algebraic',dato:'Input',integral_auxiliar:'Auxiliary integral',derivada:'Derivative'})[p];
export const nombreEvidencia=(e:EvidenciaV2)=>({contrastada:'Cross-checked',cualitativa:'Qualitative',imposible_en_el_modelo:'Impossible in this model',sin_modelo:'No model',excluida:'Excluded'})[e];
export const certificationStatusName=(status:string)=>({cumple:'Passed',no_cumple:'Failed',no_evaluable:'Not evaluable'} as Record<string,string>)[status]??status;
export function resumenCertificacion(a:Trayectoria){
  const c=a.certificacion;
  return !c?'Certification unavailable · previous run':c.estado==='cumple'?'Physical certification · passed':c.estado==='no_evaluable'?'Physical certification · not evaluable':'Uncertified trajectory · verification failed';
}
/** Use the backend's published cut. Keep every original sample as evidence. */
export function intervaloNoCertificado(a:Trayectoria):[number,number]|null{
  const c=a.certificacion;if(c?.estado!=='no_cumple')return null;
  return [c.ultimaMuestraCertificada===null?a.tiempos[0]:a.tiempos[c.ultimaMuestraCertificada],a.tiempos.at(-1)!];
}
export const nombreEventoRed=(codigo:string)=>({aparicion_fase:'Phase appearance',desaparicion_fase:'Phase disappearance',sustitucion_fase:'Phase substitution',cambio_denominacion:'Label change · no first-order transition'} as Record<string,string>)[codigo]??codigo;
