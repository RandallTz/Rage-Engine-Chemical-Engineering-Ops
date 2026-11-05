import type {HojaMotor} from '../motor/hojasMotor';
import {leerModeloComun} from '../../motores/modelo/lector';
import {requestIndexSetExpansion,type IndexSetExpansion} from '../../motores/modelo/indexSets';
import {responseError} from '../../motores/modelo/assessment';

export function changeStageCount(model:HojaMotor,text:string):HojaMotor{
  const common=structuredClone(model.commonModel!);if(!common.indexSet)throw new Error('No index set is declared.');
  common.datos[common.indexSet.countDataId].declaracion.texto=text;
  leerModeloComun(common);
  return {...model,commonModel:common,indexedSelection:undefined,derivedSelection:undefined,transformation:undefined,resultado:undefined,resultadoRef:undefined};
}
export function expandStages(model:HojaMotor,signal?:AbortSignal){
  const common=structuredClone(model.commonModel!);common.id=model.id;common.nombre=model.nombre;
  return requestIndexSetExpansion(common,signal);
}
export async function inspectExpandedNetwork(expansion:IndexSetExpansion,signal?:AbortSignal):Promise<void>{
  const response=await fetch(`${process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004'}/modelo/index-set-assessment`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(expansion),signal});
  const value=await response.json();if(!response.ok)throw responseError(value,response.status,'Network assessment rejected.');
}
