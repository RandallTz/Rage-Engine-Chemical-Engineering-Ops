import type {SolicitudDiagrama} from './contratoDiagramasEquilibrio';
import {leerCapacidadesDiagramas,leerDiagramaEquilibrio} from './lectorDiagramasEquilibrio';
const API=(process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004')+'/motor/termodinamica/diagramas';
async function consultar(ruta:string,s?:SolicitudDiagrama,signal?:AbortSignal,presupuestoMs=90000){
  const timeout=AbortSignal.timeout(presupuestoMs),r=await fetch(`${API}/${ruta}`,{method:s?'POST':'GET',headers:s?{'Content-Type':'application/json'}:undefined,body:s?JSON.stringify(s):undefined,cache:'no-store',signal:signal?AbortSignal.any([signal,timeout]):timeout});
  if(r.status===404)throw new Error('El servicio de diagramas todavía no está disponible en este backend.');
  if(!r.ok||!r.headers.get('content-type')?.includes('application/json'))throw new Error(`Servicio de diagramas no disponible (HTTP ${r.status}).`);
  return r.json() as Promise<unknown>;
}
export async function capacidadesDiagramas(signal?:AbortSignal){return leerCapacidadesDiagramas(await consultar('capacidades',undefined,signal,20000));}
export async function trazarDiagrama(s:SolicitudDiagrama,signal?:AbortSignal,presupuestoMs=90000){return leerDiagramaEquilibrio(await consultar('trazar',s,signal,presupuestoMs),s);}
