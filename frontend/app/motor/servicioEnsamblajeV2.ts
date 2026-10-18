import type {SolicitudEnsamblajeV2} from './contratoEnsamblajeV2';
import {leerCapacidadesV2,leerValidacionV2,leerResolucionV2} from './lectorEnsamblajeV2';
const API=(process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004')+'/motor/ensamblajes';
async function leer(ruta:string,s?:SolicitudEnsamblajeV2,signal?:AbortSignal){
  const tiempo=AbortSignal.timeout(ruta==='resolver'?600000:120000);
  const r=await fetch(`${API}/${ruta}`,{method:s?'POST':'GET',headers:s?{'Content-Type':'application/json'}:undefined,body:s?JSON.stringify(s):undefined,cache:'no-store',signal:signal?AbortSignal.any([signal,tiempo]):tiempo});
  if(!r.ok||!r.headers.get('content-type')?.includes('application/json'))throw new Error(`Servicio multifásico no disponible (HTTP ${r.status}).`);
  return r.json() as Promise<unknown>;
}
export const capacidadesV2=async(signal?:AbortSignal)=>leerCapacidadesV2(await leer('capacidades?revision=2',undefined,signal));
export const validarV2=async(s:SolicitudEnsamblajeV2,signal?:AbortSignal)=>leerValidacionV2(await leer('validar',s,signal),s);
export const resolverV2=async(s:SolicitudEnsamblajeV2,modeloId:string,signal?:AbortSignal)=>leerResolucionV2(await leer('resolver',s,signal),s,modeloId);
