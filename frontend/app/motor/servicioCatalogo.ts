import {leerCatalogoMotor} from './lectorCatalogo';
export async function catalogoMotor(signal?:AbortSignal){
  const tiempo=AbortSignal.timeout(20000),r=await fetch((process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004')+'/motor/catalogo',{cache:'no-store',signal:signal?AbortSignal.any([signal,tiempo]):tiempo});
  if(r.status===404)throw new Error('Catálogo no disponible en este servicio.');
  if(!r.ok)throw new Error(`No se pudo cargar el catálogo (HTTP ${r.status}).`);
  if(!r.headers.get('content-type')?.includes('application/json'))throw new Error('Respuesta de catálogo incompatible.');
  return leerCatalogoMotor(await r.json());
}
