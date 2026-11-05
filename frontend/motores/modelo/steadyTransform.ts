import type {ModeloComun} from './contrato';
import type {TemporalDerivedExecution} from './derivedExecution';
import {leerModeloComun} from './lector';
import {readCompilationReport} from './compilation';
import {steadySignature,type SteadyReport} from './steadyContract';
import {responseError} from './assessment';

export type SteadyTransform={format:'rage.steady-transform';version:1;model:ModeloComun;dynamicSelection:TemporalDerivedExecution;dynamicSignature:string;report:SteadyReport};
export function readSteadyTransform(value:unknown,source:ModeloComun):SteadyTransform{
  const v=value as SteadyTransform;
  const fields=['format','version','model','dynamicSelection','dynamicSignature','report'];
  if(!v||typeof v!=='object'||Object.keys(v).length!==fields.length||fields.some(k=>!Object.hasOwn(v,k))||v.format!=='rage.steady-transform'||v.version!==1)throw new Error('Invalid steady Transform response.');
  const model=leerModeloComun(v.model),report=readCompilationReport(v.report),dynamic=source.motores.derivedExecution;
  if(!dynamic||dynamic.version===5||steadySignature(v.dynamicSelection)!==steadySignature(dynamic)||v.dynamicSignature!==steadySignature(dynamic)||report.version!==2||model.id!==source.id||report.sourceModelId!==source.id||steadySignature(model.motores.derivedExecution)!==steadySignature(report.selection))throw new Error('The steady Transform does not match its dynamic source.');
  for(const key of ['states','parameters','reconstructions','timeId','sourceSignature'] as const)if(steadySignature(report.selection[key])!==steadySignature(dynamic[key]))throw new Error('The steady Transform changed an original selected row or binding.');
  if(steadySignature(report.selection.checks.map(r=>r.equationId))!==steadySignature(dynamic.checks.map(r=>r.equationId)))throw new Error('The steady Transform changed a conservation equation.');
  if(steadySignature(report.selection.algebraic)!==steadySignature(dynamic.algebraic??[]))throw new Error('The steady Transform changed the algebraic selection.');
  for(const [key,datum]of Object.entries(source.datos))if(!(key.startsWith('steadyTransform.')&&datum.origen.propietarioId==='estudio'&&datum.origen.ruta.startsWith('steadyTransform.'))&&steadySignature(model.datos[key])!==steadySignature(datum))throw new Error('The steady Transform changed declared source data.');
  const packageVolumes=source.volumenes.filter(v=>v.termodinamica.tipo==='equilibrio').map(v=>v.id).sort();
  if(steadySignature(packageVolumes)!==steadySignature((report.thermodynamicClosures??[]).map(row=>row.volumeId).sort()))throw new Error('Package closure evidence does not match the source volumes.');
  const expected=structuredClone(source);expected.datos=model.datos;expected.estudio=model.estudio;expected.motores.derivedExecution=model.motores.derivedExecution;
  if(steadySignature(expected)!==steadySignature(model))throw new Error('The steady Transform changed the physical model.');
  return v;
}
export async function requestSteadyTransform(model:ModeloComun,signal?:AbortSignal){
  const response=await fetch(`${process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004'}/modelo/steady-transform`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({format:'rage.steady-transform.request',version:1,model}),cache:'no-store',signal:signal?AbortSignal.any([signal,AbortSignal.timeout(60000)]):AbortSignal.timeout(60000)});
  const value=await response.json();
  if(!response.ok)throw responseError(value,response.status,'The steady Transform was rejected.');
  return readSteadyTransform(value,model);
}
