/** Versioned graph selection and lifecycle only; no browser algebra. */
import type {HojaMotor} from '../motor/hojasMotor';
import type {ModeloComun} from '../../motores/modelo/contrato';
import {leerModeloComun} from '../../motores/modelo/lector';
import {readDerivedExecution,type DerivedExecution} from '../../motores/modelo/derivedExecution';

export type DerivedSelection={version:1;sourceSignature:string;selection:DerivedExecution};
const canonical=(value:unknown):unknown=>Array.isArray(value)?value.map(canonical):value&&typeof value==='object'?Object.fromEntries(Object.entries(value).sort(([a],[b])=>a.localeCompare(b)).map(([key,item])=>[key,canonical(item)])):value;
export function commonSource(model:HojaMotor):ModeloComun {
  if(!model.commonModel)throw new Error('This document has no common-model backing.');
  const common=structuredClone(model.commonModel);common.id=model.id;common.nombre=model.nombre;
  delete common.motores.derivedExecution;
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
  const common=commonSource(model),stored=model.derivedSelection;
  if(!stored||stored.version!==1||stored.sourceSignature!==derivedSourceIdentity(common))throw new Error('The derived formulation is missing or outdated. Review and select it in Transform.');
  common.motores.derivedExecution=readDerivedExecution(structuredClone(stored.selection),common.datos);
  return leerModeloComun(common);
}
export function reconcileDerived(previous:HojaMotor|undefined,next:HojaMotor):HojaMotor {
  if(!next.commonModel)return next;
  commonSource(next);
  const changed=previous?.commonModel&&derivedSourceIdentity(commonSource(previous))!==derivedSourceIdentity(commonSource(next));
  const studyChanged=previous?.commonModel&&JSON.stringify(previous.commonModel.estudio)!==JSON.stringify(next.commonModel.estudio);
  const selectedChanged=JSON.stringify(previous?.derivedSelection)!==JSON.stringify(next.derivedSelection);
  return changed||studyChanged||selectedChanged?{...next,resultado:undefined,resultadoRef:undefined}:next;
}
