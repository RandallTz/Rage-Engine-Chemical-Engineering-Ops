import type {SolicitudEnsamblajeDinamico} from './contratoEnsamblajeTermodinamico';
import {validarCapacidadesEnsamblaje,validarRespuestaEnsamblaje,validarResolucionEnsamblaje} from './lectorEnsamblajeTermodinamico';
const API=(process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004')+'/motor/ensamblajes';
async function leer(ruta:string,s?:SolicitudEnsamblajeDinamico,signal?:AbortSignal){
  const timeout=AbortSignal.timeout(ruta==='resolver'?120000:30000),r=await fetch(`${API}/${ruta}`,{method:s?'POST':'GET',headers:s?{'Content-Type':'application/json'}:undefined,body:s?JSON.stringify(s):undefined,cache:'no-store',signal:signal?AbortSignal.any([signal,timeout]):timeout});
  if(r.status===404)throw new Error('Recarga el backend: faltan las rutas de ensamblaje dinámico.');
  if(!r.ok||!r.headers.get('content-type')?.includes('application/json'))throw new Error(`El servicio de ensamblaje no respondió correctamente (HTTP ${r.status}).`);
  return r.json() as Promise<unknown>;
}
export async function capacidadesEnsamblaje(signal?:AbortSignal){return validarCapacidadesEnsamblaje(await leer('capacidades',undefined,signal));}
export async function validarEnsamblaje(s:SolicitudEnsamblajeDinamico,signal?:AbortSignal){return validarRespuestaEnsamblaje(await leer('validar',s,signal),s);}
export async function resolverEnsamblaje(s:SolicitudEnsamblajeDinamico,modeloId:string,signal?:AbortSignal){return validarResolucionEnsamblaje(await leer('resolver',s,signal),s,modeloId);}
