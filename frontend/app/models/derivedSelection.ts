import {readInverseSolve,type InverseSolve} from '../../motores/modelo/inverseSpecification';
import {currentIndexed,readSavedIndexed} from './indexedSelection';
/** Versioned graph selection and lifecycle only; no browser algebra. */
import type {HojaMotor} from '../motor/hojasMotor';
import type {ModeloComun} from '../../motores/modelo/contrato';
import {leerModeloComun} from '../../motores/modelo/lector';
import {readDerivedExecution,type DerivedExecution} from '../../motores/modelo/derivedExecution';
import {steadySignature} from '../../motores/modelo/steadyContract';
import type {SteadyTransform} from '../../motores/modelo/steadyTransform';

export type DerivedSelection={version:1;sourceSignature:string;selection:DerivedExecution;inverseSolve?:InverseSolve;steadyTransform?:{version:1;dynamicSignature:string;rows:SteadyTransform['report']['rows']}};

export function applySteadyTransformResult(model:HojaMotor,response:SteadyTransform):HojaMotor{
  const common=structuredClone(response.model);
  // Keep the dynamic formulation and time study as the source of this Transform.
  common.motores.derivedExecution=structuredClone(response.dynamicSelection);
  common.estudio=structuredClone(model.commonModel!.estudio);
  const next={...model,commonModel:common,transformation:undefined,resultado:undefined,resultadoRef:undefined};
  return {...next,derivedSelection:{version:1,sourceSignature:derivedSourceIdentity(commonSource(next)),selection:response.report.selection,
    steadyTransform:{version:1,dynamicSignature:response.dynamicSignature,rows:response.report.rows}}};
}
const canonical=(value:unknown):unknown=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.entries(value).sort(([a],[b])=>a.localeCompare(b)).map(([key,item])=>[key,canonical(item)])):value;
export function commonSource(model:HojaMotor):ModeloComun {
  if(!model.commonModel)throw new Error('This document has no common-model backing.');
  const common=structuredClone(model.commonModel);common.id=model.id;common.nombre=model.nombre;
  if(!common.indexSet)delete common.motores.derivedExecution;
  return leerModeloComun(common);
}
export function derivedSourceIdentity(common:ModeloComun):string {
  const source=structuredClone(common);source.nombre='';source.estudio=null;
  delete source.motores.derivedExecution;
  // Display labels never identify scientific content; datum IDs/units/values do.
  source.componentes=source.componentes.map(component=>({...component,nombre:''}));
  return JSON.stringify(canonical(source));
}
export function selectedDerivedModel(model:HojaMotor):ModeloComun {
  if(model.commonModel?.indexSet)throw new Error('Indexed networks require network lowering.');
  const common=commonSource(model),stored=model.derivedSelection;
  if(!stored||stored.version!==1||stored.sourceSignature!==derivedSourceIdentity(common))throw new Error('The derived formulation is missing or outdated. Review and select it in Transform.');
  if(stored.steadyTransform&&(stored.steadyTransform.version!==1||stored.selection.version!==5||!model.commonModel?.motores.derivedExecution||stored.steadyTransform.dynamicSignature!==steadySignature(model.commonModel.motores.derivedExecution)))throw new Error('The dynamic selection changed. Apply the steady Transform again.');
  if(stored.inverseSolve){
    if(stored.selection.version!==5)throw new Error('Inverse specifications require the steady Transform.');
    const solve=readInverseSolve(stored.inverseSolve);
    for(const [id,declaracion] of Object.entries(solve.data)){
      if(Object.hasOwn(common.datos,id))throw new Error('Inverse Solve data must have fresh identities, separate from Model data.');
      common.datos[id]={magnitud:id,funcion:'parametro',declaracion:structuredClone(declaracion),origen:{propietarioId:'estudio',ruta:id}};
    }
  }
  common.motores.derivedExecution=readDerivedExecution(structuredClone(stored.selection),common.datos);
  if(common.motores.derivedExecution.version===5)common.estudio={tipo:'steady',version:1,metodoSolicitado:'damped_newton'};
  return leerModeloComun(common);
}
export function reconcileDerived(previous:HojaMotor|undefined,next:HojaMotor):HojaMotor {
  if(!next.commonModel)return next;
  if(next.indexedSelection)readSavedIndexed(next.indexedSelection);
  if(next.commonModel.indexSet){
    const sourceChanged=!!previous&&JSON.stringify(previous.commonModel)!==JSON.stringify(next.commonModel);
    if(sourceChanged||next.indexedSelection&&!currentIndexed(next))return {...next,indexedSelection:undefined,derivedSelection:undefined,transformation:undefined,resultado:undefined,resultadoRef:undefined};
    if(JSON.stringify(previous?.indexedSelection)!==JSON.stringify(next.indexedSelection))return {...next,resultado:undefined,resultadoRef:undefined};
  }
  commonSource(next);
  const changed=previous?.commonModel&&derivedSourceIdentity(commonSource(previous))!==derivedSourceIdentity(commonSource(next));
  const studyChanged=previous?.commonModel&&JSON.stringify(previous.commonModel.estudio)!==JSON.stringify(next.commonModel.estudio);
  const selectedChanged=JSON.stringify(previous?.derivedSelection)!==JSON.stringify(next.derivedSelection);
  const dynamicChanged=JSON.stringify(previous?.commonModel?.motores.derivedExecution)!==JSON.stringify(next.commonModel.motores.derivedExecution);
  if(next.commonModel.indexSet&&changed)return {...next,derivedSelection:undefined,transformation:undefined,resultado:undefined,resultadoRef:undefined};
  return changed||studyChanged||selectedChanged||dynamicChanged?{...next,resultado:undefined,resultadoRef:undefined}:next;
}
