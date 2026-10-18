import type {RespuestaResolucionV2,SerieCatalogoV2,EvidenciaV2} from './contratoEnsamblajeV2';
type Trayectoria=NonNullable<RespuestaResolucionV2['resultados']>;
export const nombrePapelSerie=(p:SerieCatalogoV2['papel'])=>({estado_integrado:'Estado integrado',algebraica:'Algebraica',dato:'Dato',integral_auxiliar:'Integral auxiliar',derivada:'Derivada'})[p];
export const nombreEvidencia=(e:EvidenciaV2)=>({contrastada:'Contrastada',cualitativa:'Cualitativa',imposible_en_el_modelo:'Imposible en este modelo',sin_modelo:'Sin modelo',excluida:'Excluida'})[e];
export function resumenCertificacion(a:Trayectoria){
  const c=a.certificacion;
  return !c?'Certificación no disponible · ejecución anterior':c.estado==='cumple'?'Certificación física · cumple':c.estado==='no_evaluable'?'Certificación física · no evaluable':'Trayectoria sin certificar · verificación no superada';
}
/** Use the backend's published cut. Keep every original sample as evidence. */
export function intervaloNoCertificado(a:Trayectoria):[number,number]|null{
  const c=a.certificacion;if(c?.estado!=='no_cumple')return null;
  return [c.ultimaMuestraCertificada===null?a.tiempos[0]:a.tiempos[c.ultimaMuestraCertificada],a.tiempos.at(-1)!];
}
export const nombreEventoRed=(codigo:string)=>({aparicion_fase:'Aparición de fase',desaparicion_fase:'Desaparición de fase',sustitucion_fase:'Sustitución de fase',cambio_denominacion:'Cambio de denominación · sin transición de primer orden'} as Record<string,string>)[codigo]??codigo;
