import {nuevaHoja,type HojaMotor} from '../motor/hojasMotor';
import {commonSource,derivedSourceIdentity,selectedDerivedModel} from './derivedSelection';
import {requestTemplateInstance,type TemplateInstance} from '../../motores/modelo/templateInstance';

export function templateInstanceDocument(response:TemplateInstance):HojaMotor{
  const common=structuredClone(response.model);
  const model:HojaMotor={...nuevaHoja(common.nombre),id:common.id,commonModel:common};
  if(common.motores.derivedExecution)model.derivedSelection={version:1,sourceSignature:derivedSourceIdentity(commonSource(model)),selection:structuredClone(common.motores.derivedExecution)};
  return model;
}
export async function newTemplateInstance(source:HojaMotor):Promise<HojaMotor>{
  if(!source.commonModel?.template)throw new Error('This model has no recorded template recipe.');
  // A stale saved selection is rejected; it never falls back to an earlier run.
  const common=source.derivedSelection?selectedDerivedModel(source):structuredClone(source.commonModel);
  common.id=source.id;common.nombre=source.nombre;
  return templateInstanceDocument(await requestTemplateInstance(common));
}
