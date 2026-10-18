import ejemplos from './ejemplosUNIFAC.json';
import type {HojaMotor} from './hojasMotor';
import type {SolicitudEnsamblajeV2} from './contratoEnsamblajeV2';
import {nuevaHoja} from './hojasMotor';

/** Editable inputs; every worksheet uses the same coordinator and selected package. */
export function crearHojasPruebaUNIFAC():HojaMotor[]{
  return ejemplos.map(e=>{
    const s=structuredClone(e.solicitud) as unknown as SolicitudEnsamblajeV2;s.solicitudId='configuracion';
    return {...nuevaHoja(e.nombre),id:`motor-unifac-v1-${e.id}`,balances:{materia:true,energia:true,momento:false},redTermodinamica:{solicitud:s,nombres:Object.fromEntries([
      ...s.volumenes.map(v=>[`volumen:${v.id}`,`Volumen ${v.id}`]),...s.corrientes.map(c=>[`corriente:${c.id}`,`Corriente ${c.id}`]),...s.intercambiosTermicos.map(q=>[`calor:${q.id}`,`Calor ${q.id}`]),
    ])}};
  });
}
