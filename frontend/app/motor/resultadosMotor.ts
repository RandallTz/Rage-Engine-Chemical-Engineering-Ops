import type {ResultadoMotor} from './modeloNumerico';
import {readCompilationReport} from '../../motores/modelo/compilation';
import {leerResultados} from '../../motores/resultados/lector';
import {ModelDiagnosticError,readAssessment} from '../../motores/modelo/assessment';
export type RejectedAttempt={format:'rage.model-attempt';version:1;operation:'compilation'|'solve';modelId:string;modelSignature:string;createdAt:string;message:string;httpStatus:number;detail:unknown};
export function readRejectedAttempt(value:unknown,id:string,signature:string):RejectedAttempt{
  const a=value as RejectedAttempt;
  if(!a||a.format!=='rage.model-attempt'||a.version!==1||!['compilation','solve'].includes(a.operation)||a.modelId!==id||a.modelSignature!==signature||typeof a.message!=='string'||!Number.isInteger(a.httpStatus)||typeof a.createdAt!=='string'||!Number.isFinite(Date.parse(a.createdAt)))throw new Error('Invalid or stale rejected model attempt.');
  const error=new ModelDiagnosticError(a.message,a.httpStatus,a.detail);
  if(error.assessment){readAssessment(error.assessment);if(error.assessment.modelId!==id)throw new Error('The rejected assessment belongs to another model.');}
  return a;
}
function abrir():Promise<IDBDatabase>{return new Promise((resolve,reject)=>{const r=indexedDB.open('rage-motor-resultados',1);r.onupgradeneeded=()=>r.result.createObjectStore('resultados');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(new Error('No se pudo abrir el almacenamiento de resultados.'));});}
export async function guardarResultadoMotor(id:string,resultado:ResultadoMotor,signal?:AbortSignal){
  if(resultado.compilation)readCompilationReport(resultado.compilation);
  if(resultado.commonResult)leerResultados(resultado.commonResult);
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
export async function leerResultadoMotor(id:string,firma:string):Promise<ResultadoMotor|undefined>{const db=await abrir();try{return await new Promise((resolve,reject)=>{const t=db.transaction('resultados'),r=t.objectStore('resultados').get([id,firma]);r.onsuccess=()=>{try{if(r.result?.compilation)readCompilationReport(r.result.compilation);if(r.result?.commonResult)leerResultados(r.result.commonResult);resolve(r.result);}catch(error){reject(error);}};r.onerror=()=>reject(new Error('No se pudo leer el resultado.'));});}finally{db.close();}}

/** Separate key in the existing store; a rejected attempt never overwrites a run. */
export async function saveRejectedAttempt(id:string,signature:string,error:unknown,signal?:AbortSignal,operation:RejectedAttempt['operation']='solve'){
  if(!(error instanceof ModelDiagnosticError))return;
  const attempt=readRejectedAttempt({format:'rage.model-attempt',version:1,operation,modelId:id,modelSignature:signature,
    createdAt:new Date().toISOString(),message:error.message,httpStatus:error.httpStatus,detail:error.detail},id,signature);
  signal?.throwIfAborted();const db=await abrir();
  try{signal?.throwIfAborted();await new Promise<void>((resolve,reject)=>{
    const tx=db.transaction('resultados','readwrite');
    const abort=()=>{try{tx.abort();}catch{/* Already completed. */}};
    const finish=()=>signal?.removeEventListener('abort',abort);
    tx.oncomplete=()=>{finish();resolve();};tx.onerror=()=>{finish();reject(new Error('The rejected attempt could not be saved.'));};
    tx.onabort=()=>{finish();reject(signal?.reason??new Error('Attempt storage interrupted.'));};
    signal?.addEventListener('abort',abort,{once:true});
    tx.objectStore('resultados').put(attempt,['assessment-attempt',id,signature]);
  });}finally{db.close();}
}
export async function loadRejectedAttempt(id:string,signature:string):Promise<RejectedAttempt|undefined>{
  const db=await abrir();try{return await new Promise((resolve,reject)=>{
    const request=db.transaction('resultados').objectStore('resultados').get(['assessment-attempt',id,signature]);
    request.onsuccess=()=>{try{resolve(request.result?readRejectedAttempt(request.result,id,signature):undefined);}catch(error){reject(error);}};
    request.onerror=()=>reject(new Error('The rejected attempt could not be read.'));
  });}finally{db.close();}
}
