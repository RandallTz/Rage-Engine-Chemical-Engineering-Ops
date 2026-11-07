/** Flowsheet transport and persisted handoff; physical assembly stays in Python. */
import type {HojaMotor} from '../motor/hojasMotor';
import type {ResultadoMotor} from '../motor/modeloNumerico';
import {leerModeloComun} from '../../motores/modelo/lector';
import {executableSource,readFlowsheetCompilation,readFlowsheetResult,readFlowsheetSelection,type FlowsheetCompilation,type FlowsheetSelection} from '../../motores/modelo/flowsheet';
import {steadySignature} from '../../motores/modelo/steadyContract';
import {responseError} from '../../motores/modelo/assessment';

export type SavedFlowsheetSelection={version:1;report:FlowsheetCompilation}|{version:2;sourceModelId:string;selection:FlowsheetSelection;count:number;rateRowCount:number};
type CurrentFlowsheetSelection={sourceModelId:string;selection:FlowsheetSelection;count:number;rateRowCount:number};
export function flowsheetSource(model:HojaMotor){
  if(!model.commonModel?.flowsheet)throw new Error('A flowsheet model is required.');
  return leerModeloComun({...structuredClone(model.commonModel),id:model.id,nombre:model.nombre});
}
export function flowsheetSourceSignature(model:HojaMotor){return steadySignature(executableSource(flowsheetSource(model)));}
export function readSavedFlowsheet(value:unknown):CurrentFlowsheetSelection{
  const saved=value as SavedFlowsheetSelection;
  if(!saved||typeof saved!=='object')throw new Error('Invalid saved flowsheet selection.');
  if(saved.version===1&&Object.keys(saved).sort().join('|')==='report|version'){
    const report=readFlowsheetCompilation(saved.report);
    return {sourceModelId:report.sourceModelId,selection:report.selection,count:report.count,rateRowCount:report.rateRows.length};
  }
  if(saved.version!==2||Object.keys(saved).sort().join('|')!=='count|rateRowCount|selection|sourceModelId|version'||typeof saved.sourceModelId!=='string'||!saved.sourceModelId||!Number.isSafeInteger(saved.count)||saved.count<1||saved.count>64||!Number.isSafeInteger(saved.rateRowCount)||saved.rateRowCount<0)throw new Error('Invalid saved flowsheet selection.');
  return {sourceModelId:saved.sourceModelId,selection:readFlowsheetSelection(saved.selection),count:saved.count,rateRowCount:saved.rateRowCount};
}
export function currentFlowsheet(model:HojaMotor):CurrentFlowsheetSelection|undefined{
  if(!model.flowsheetSelection)return undefined;
  const saved=readSavedFlowsheet(model.flowsheetSelection);
  return saved.sourceModelId===model.id&&saved.selection.sourceSignature===flowsheetSourceSignature(model)?saved:undefined;
}
export function applyFlowsheet(model:HojaMotor,report:FlowsheetCompilation):HojaMotor{
  readFlowsheetCompilation(report);
  if(report.sourceModelId!==model.id||report.selection.sourceSignature!==flowsheetSourceSignature(model))throw new Error('stale_flowsheet_execution: The model changed while the network was prepared.');
  return {...model,flowsheetSelection:{version:2,sourceModelId:report.sourceModelId,selection:report.selection,count:report.count,rateRowCount:report.rateRows.length},flowsheetStale:false,indexedSelection:undefined,derivedSelection:undefined,transformation:undefined,resultado:undefined,resultadoRef:undefined,chartReference:undefined};
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
  return readFlowsheetResult(await request('resolver',{modelo:flowsheetSource(model),flowsheetExecution:selected.selection},signal),selected.selection).result;
}
export function flowsheetResult(model:HojaMotor,value:unknown,signature:string):ResultadoMotor{
  const selected=currentFlowsheet(model);if(!selected)throw new Error('stale_flowsheet_execution: Prepare the flowsheet again in Transform.');
  const common=readFlowsheetResult(value,selected.selection).result,steady=common.indexedNetwork!.mode==='steady';
  if(common.estado==='fallido')throw new Error('The network did not produce an accepted result.');
  return {version:3,motor:'rage.compilador.indexed_network',modo:steady?'steady':'temporal',metodo:String(common.procedencia.metodo),tiempos:steady?[]:common.ejes.find(axis=>axis.id==='t')!.valores,x:[],dx:1,valores:[],componentes:[],estado:common.estado,mensaje:'',pasos:0,rechazados:0,conservacion:[],unidadEstado:'mixta',firma:signature,commonResult:common,verificationChecks:common.verificaciones};
}
