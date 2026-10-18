import type {CapacidadesEnsamblajeV2,SolicitudEnsamblajeV2} from './contratoEnsamblajeV2';
import type {RedTermodinamica} from './redTermodinamica';
import {analizarExpresion,evaluarExpresion} from './expresionesMotor';
import {convertirUnidad} from './unidadesMotor';

type Paquetes=CapacidadesEnsamblajeV2['paquetes'];
function paqueteVolumen(s:SolicitudEnsamblajeV2,vid:string,paquetes?:Paquetes){
  const v=s.volumenes.find(v=>v.id===vid),m=s.paquetes.find(p=>p.id===v?.paqueteId)?.modelo;
  return paquetes?.find(p=>p.modelo.id===m?.id&&p.modelo.version===m?.version);
}

/** Editing guard for NEW membership only; never prune existing species or select another package. */
export function restriccionComponenteRed(red:RedTermodinamica,vid:string,cas?:string,paquetes?:Paquetes):string|null{
  const p=paqueteVolumen(red.solicitud,vid,paquetes),id=cas?.trim();
  // Unidentified/symbolic components remain usable while drafting a model.
  if(!p||!id)return null;
  if(p.coberturaGrupos?.especiesSinAsignacion.includes(id))return 'Sin asignación en esta tabla';
  return p.componentesCAS&&!p.componentesCAS.includes(id)?'Fuera del catálogo de este paquete':null;
}

/** Definite violations of the published envelope for constant initial T / boundary P.
 * It does not certify the mixture domain, evaluate a trajectory or clamp user inputs. */
export function avisoDominioDatoRed(s:SolicitudEnsamblajeV2,id:string,paquetes?:Paquetes):string|null{
  const d=s.datos[id];if(!d||!d.declaracion.texto.trim())return null;
  const v=s.volumenes.find(v=>v.inicial.energia.tipo==='T'&&v.inicial.energia.datoId===id||v.frontera.tipo==='presion_prescrita'&&v.frontera.presionId===id||v.frontera.tipo==='rigida'&&v.frontera.presionRestriccionId===id);
  if(!v)return null;
  const p=paqueteVolumen(s,v.id,paquetes),tipo=d.magnitud==='temperatura'?'T':d.magnitud==='presion'?'P':null;
  if(tipo==='T'&&Object.values(s.paquetes.find(p=>p.id===v.paqueteId)?.datosPuros??{}).some(d=>d.cp_gas_ideal||d.presion_vapor))return null;// Effective domain is checked by /validar with the substituted data.
  const rango=tipo?p?.dominio?.[tipo]:undefined;if(!rango||!tipo)return null;
  try{
    const x=evaluarExpresion(analizarExpresion(d.declaracion.texto,[]),{}),si=convertirUnidad(tipo==='T'?'temperatura':'presion',x,d.declaracion.unidad);
    const margen=32*Number.EPSILON*Math.max(1,Math.abs(si),...rango);
    return Number.isFinite(si)&&(si<rango[0]-margen||si>rango[1]+margen)?`Fuera del rango publicado del paquete: ${rango.join('–')} ${tipo==='T'?'K':'Pa absolutos'}.`:null;
  }catch{return null;}// Syntax, nonconstant inputs and exact mixture domains belong to /validar.
}
