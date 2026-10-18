import type {CapacidadModeloEstado,SolicitudEstado} from './contratoTermodinamica';
import {analizarSolicitudEstado,validarCapacidadesEstado,validarRespuestaEstado} from './contratoTermodinamica';
const API=(process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004')+'/motor/termodinamica';
async function leer(url:string,init:RequestInit,signal?:AbortSignal,presupuestoMs=20000){
  const tiempo=AbortSignal.timeout(presupuestoMs);
  const r=await fetch(url,{...init,cache:'no-store',signal:signal?AbortSignal.any([signal,tiempo]):tiempo});
  if(r.status===404)throw new Error('El servicio termodinámico del motor aún no está disponible.');
  if(!r.ok)throw new Error(`El servicio no pudo evaluar el estado (HTTP ${r.status}).`);
  if(!r.headers.get('content-type')?.includes('application/json'))throw new Error('Respuesta de servicio incompatible.');
  return r.json() as Promise<unknown>;
}
export async function capacidadesTermodinamica(signal?:AbortSignal){return validarCapacidadesEstado(await leer(`${API}/capacidades`,{},signal));}
export async function evaluarEstadoTermodinamico(s:SolicitudEstado,c:CapacidadModeloEstado,signal?:AbortSignal){
  const pendientes=analizarSolicitudEstado(s);if(pendientes.length)throw new Error(pendientes[0].mensaje);
  if(c.id!==s.declaracion.modelo.id||c.version!==s.declaracion.modelo.version||!c.especificaciones.includes(s.declaracion.especificacion.tipo))throw new Error('La especificación no está disponible en este modelo.');
  // Catalog membership does not explain which property/group/operation is missing.
  // Preserve the backend's structured rejection instead of replacing it locally.
  // UV multicomponent inversions can exceed 20 s within the published scope.
  return validarRespuestaEstado(await leer(`${API}/evaluar`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(s)},signal,120000),s,c);
}
