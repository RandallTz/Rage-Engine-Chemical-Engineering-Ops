import type {ResultadoMotor} from './modeloNumerico';
function abrir():Promise<IDBDatabase>{return new Promise((resolve,reject)=>{const r=indexedDB.open('rage-motor-resultados',1);r.onupgradeneeded=()=>r.result.createObjectStore('resultados');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(new Error('No se pudo abrir el almacenamiento de resultados.'));});}
export async function guardarResultadoMotor(id:string,resultado:ResultadoMotor,signal?:AbortSignal){
  signal?.throwIfAborted();const db=await abrir();
  try{signal?.throwIfAborted();await new Promise<void>((resolve,reject)=>{
    const t=db.transaction('resultados','readwrite');
    const cancelar=()=>{try{t.abort();}catch{/* A completed transaction cannot be undone. */}};
    const terminar=()=>signal?.removeEventListener('abort',cancelar);
    t.oncomplete=()=>{terminar();resolve();};
    t.onerror=()=>{terminar();reject(new Error('No se pudo guardar el resultado.'));};
    t.onabort=()=>{terminar();reject(signal?.aborted?signal.reason:new Error('El guardado del resultado fue interrumpido.'));};
    signal?.addEventListener('abort',cancelar,{once:true});
    try{t.objectStore('resultados').put(resultado,[id,resultado.firma]);}
    catch(error){terminar();try{t.abort();}catch{/* Preserve the original storage error. */}reject(error);}
  });}finally{db.close();}
}
export async function leerResultadoMotor(id:string,firma:string):Promise<ResultadoMotor|undefined>{const db=await abrir();try{return await new Promise((resolve,reject)=>{const t=db.transaction('resultados'),r=t.objectStore('resultados').get([id,firma]);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(new Error('No se pudo leer el resultado.'));});}finally{db.close();}}
