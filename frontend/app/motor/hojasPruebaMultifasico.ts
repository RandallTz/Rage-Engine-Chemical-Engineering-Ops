import { deriveNetworkTemplateMatter, deriveNetworkTemplateEnergy, deriveNetworkTemplateThermodynamics } from './materialNetworkTemplates';
import ejemplos from './ejemplosMultifasicos.json';
import type {SolicitudEnsamblajeV2} from './contratoEnsamblajeV2';
import {nuevaHoja} from './hojasMotor';
/** Input-only acceptance examples from Claude's actual requests. All equations,
 * states and curves are obtained through the same generic /validar and /resolver. */
export function crearHojasPruebaMultifasico(){
  const nombres=['Mezcla · Calentamiento de etanol y agua','Red · Contacto térmico de dos volúmenes de agua','Red · Mezcla y transferencia entre volúmenes','Separación · Dos líquidos de agua y butanol'];
  return ejemplos.map((input,i)=>{const h=nuevaHoja(nombres[i]),s=structuredClone(input) as unknown as SolicitudEnsamblajeV2;s.solicitudId='configuracion';deriveNetworkTemplateMatter(s);deriveNetworkTemplateEnergy(s,i===3?['D']:[]);deriveNetworkTemplateThermodynamics(s);return {...h,id:`motor-multifasico-v2-${i+1}`,balances:{materia:true,energia:true,momento:false},redTermodinamica:{solicitud:s,nombres:Object.fromEntries([...s.volumenes.map(v=>[`volumen:${v.id}`,`Volumen ${v.id}`]),...s.corrientes.map(c=>[`corriente:${c.id}`,`Corriente ${c.id}`]),...s.intercambiosTermicos.map(q=>[`calor:${q.id}`,`Calor ${q.id}`])])}};});
}
