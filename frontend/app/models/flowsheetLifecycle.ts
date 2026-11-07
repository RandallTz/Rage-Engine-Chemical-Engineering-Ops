/** Flowsheet transport and persisted handoff; physical assembly stays in Python. */
import type {HojaMotor} from '../motor/hojasMotor';
import type {ResultadoMotor} from '../motor/modeloNumerico';
import {leerModeloComun} from '../../motores/modelo/lector';
import {executableSource,readFlowsheetCompilation,readFlowsheetResult,type FlowsheetCompilation} from '../../motores/modelo/flowsheet';
import {steadySignature} from '../../motores/modelo/steadyContract';
import {responseError} from '../../motores/modelo/assessment';

export type SavedFlowsheetSelection={version:1;report:FlowsheetCompilation};
export function flowsheetSource(model:HojaMotor){
  if(!model.commonModel?.flowsheet)throw new Error('A flowsheet model is required.');
  return leerModeloComun({...structuredClone(model.commonModel),id:model.id,nombre:model.nombre});
}
export function flowsheetSourceSignature(model:HojaMotor){return steadySignature(executableSource(flowsheetSource(model)));}
export function readSavedFlowsheet(value:unknown):SavedFlowsheetSelection{
  const saved=value as SavedFlowsheetSelection;
  if(!saved||saved.version!==1||Object.keys(saved).sort().join('|')!=='report|version')throw new Error('Invalid saved flowsheet selection.');
  readFlowsheetCompilation(saved.report);return saved;
}
export function currentFlowsheet(model:HojaMotor):SavedFlowsheetSelection|undefined{
  if(!model.flowsheetSelection)return undefined;
  const saved=readSavedFlowsheet(model.flowsheetSelection);
  return saved.report.sourceModelId===model.id&&saved.report.selection.sourceSignature===flowsheetSourceSignature(model)?saved:undefined;
}
export function applyFlowsheet(model:HojaMotor,report:FlowsheetCompilation):HojaMotor{
  readFlowsheetCompilation(report);
  if(report.sourceModelId!==model.id||report.selection.sourceSignature!==flowsheetSourceSignature(model))throw new Error('stale_flowsheet_execution: The model changed while the network was prepared.');
  return {...model,flowsheetSelection:{version:1,report},flowsheetStale:false,indexedSelection:undefined,derivedSelection:undefined,transformation:undefined,resultado:undefined,resultadoRef:undefined,chartReference:undefined};
}
async function request(endpoint:string,body:unknown,signal?:AbortSignal):Promise<unknown>{
  const timeout=AbortSignal.timeout(3600000);
  const response=await fetch(`${process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004'}/modelo/${endpoint}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),cache:'no-store',signal:signal?AbortSignal.any([signal,timeout]):timeout});
  const value=await response.json();if(!response.ok)throw responseError(value,response.status,'The flowsheet request was rejected.');return value;
}
export async function prepareFlowsheet(model:HojaMotor,mode:'dynamic'|'steady',signal?:AbortSignal){
  const source=flowsheetSource(model),report=readFlowsheetCompilation(await request('flowsheet-execution',{format:'rage.flowsheet-execution.request',version:1,model:source,mode},signal));
  if(report.selection.sourceSignature!==steadySignature(executableSource(source))||report.selection.mode!==mode||report.sourceModelId!==model.id)throw new Error('The prepared flowsheet does not match its source.');
  return report;
}
export async function solveFlowsheet(model:HojaMotor,signal?:AbortSignal){
  const selected=currentFlowsheet(model);if(!selected)throw new Error('stale_flowsheet_execution: Prepare the flowsheet again in Transform.');
  return readFlowsheetResult(await request('resolver',{modelo:flowsheetSource(model),flowsheetExecution:selected.report.selection},signal),selected.report.selection).result;
}
export function flowsheetResult(model:HojaMotor,value:unknown,signature:string):ResultadoMotor{
  const selected=currentFlowsheet(model);if(!selected)throw new Error('stale_flowsheet_execution: Prepare the flowsheet again in Transform.');
  const common=readFlowsheetResult(value,selected.report.selection).result,steady=common.indexedNetwork!.mode==='steady';
  if(common.estado==='fallido')throw new Error('The network did not produce an accepted result.');
  return {version:3,motor:'rage.compilador.indexed_network',modo:steady?'steady':'temporal',metodo:String(common.procedencia.metodo),tiempos:steady?[]:common.ejes.find(axis=>axis.id==='t')!.valores,x:[],dx:1,valores:[],componentes:[],estado:common.estado,mensaje:'',pasos:0,rechazados:0,conservacion:[],unidadEstado:'mixta',firma:signature,commonResult:common,verificationChecks:common.verificaciones};
}
