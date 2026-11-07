/** Indexed document lifecycle and storage adapters; no numerical evaluation. */
import type {HojaMotor} from '../motor/hojasMotor';
import type {ResultadoMotor} from '../motor/modeloNumerico';
import {readIndexedCompilation,readIndexedResult,type IndexedCompilation} from '../../motores/modelo/indexedExecution';
import {steadySignature} from '../../motores/modelo/steadyContract';
import {leerModeloComun} from '../../motores/modelo/lector';
import {readFlowsheetResult} from '../../motores/modelo/flowsheet';

export type SavedIndexedSelection={version:1;report:IndexedCompilation};
export function indexedSource(model:HojaMotor){
  if(!model.commonModel?.indexSet)throw new Error('An indexed common model is required.');
  return leerModeloComun({...structuredClone(model.commonModel),id:model.id,nombre:model.nombre});
}
export function readSavedIndexed(value:unknown):SavedIndexedSelection{
  const saved=value as SavedIndexedSelection;
  if(!saved||saved.version!==1||Object.keys(saved).sort().join('|')!=='report|version')throw new Error('Invalid saved indexed selection.');
  readIndexedCompilation(saved.report);return saved;
}
export function currentIndexed(model:HojaMotor):SavedIndexedSelection|undefined{
  if(!model.indexedSelection)return undefined;
  const saved=readSavedIndexed(model.indexedSelection);
  return saved.report.sourceModelId===model.id&&saved.report.selection.sourceSignature===steadySignature(indexedSource(model))?saved:undefined;
}
export function applyIndexed(model:HojaMotor,report:IndexedCompilation):HojaMotor{
  readIndexedCompilation(report);
  if(report.sourceModelId!==model.id||report.selection.sourceSignature!==steadySignature(indexedSource(model)))throw new Error('The model changed; the prepared network was discarded.');
  return {...model,indexedSelection:{version:1,report},derivedSelection:undefined,transformation:undefined,resultado:undefined,resultadoRef:undefined};
}
export function validateSavedIndexedResult(result:ResultadoMotor,id:string,signature:string){
  if(result.version!==3&&result.motor!=='rage.compilador.indexed_network')return;
  if(result.version!==3||result.motor!=='rage.compilador.indexed_network'||!result.commonResult||result.firma!==signature||result.commonResult.modeloId!==id||result.compilation||result.seriesEvaluadas||result.valores.length||result.componentes.length||result.x.length)throw new Error('Invalid indexed result wrapper.');
  const common=result.commonResult.procedencia.motor==='rage.compilador.flowsheet_network'?readFlowsheetResult(result.commonResult).result:readIndexedResult(result.commonResult),steady=common.indexedNetwork!.mode==='steady';
  const times=steady?[]:common.ejes.find(axis=>axis.id==='t')!.valores;
  if(result.modo!==(steady?'steady':'temporal')||result.metodo!==common.procedencia.metodo||result.estado!==common.estado||JSON.stringify(result.tiempos)!==JSON.stringify(times)||JSON.stringify(result.verificationChecks)!==JSON.stringify(common.verificaciones))throw new Error('Indexed wrapper differs from its common result.');
}
export function indexedResult(model:HojaMotor,value:unknown,signature:string):ResultadoMotor{
  const selected=currentIndexed(model);if(!selected)throw new Error('Prepare the indexed formulation in Transform.');
  const common=readIndexedResult(value,selected.report.selection),steady=common.indexedNetwork!.mode==='steady';
  if(common.estado==='fallido')throw new Error('The network did not produce an accepted result.');
  const result:ResultadoMotor={version:3,motor:'rage.compilador.indexed_network',modo:steady?'steady':'temporal',metodo:String(common.procedencia.metodo),
    tiempos:steady?[]:common.ejes.find(axis=>axis.id==='t')!.valores,x:[],dx:1,valores:[],componentes:[],estado:common.estado,mensaje:'',pasos:0,rechazados:0,
    conservacion:[],unidadEstado:'mixta',firma:signature,commonResult:common,verificationChecks:common.verificaciones};
  validateSavedIndexedResult(result,model.id,signature);return result;
}
