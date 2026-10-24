import type { SupuestosTermo, RecorridoTermodinamico } from './recorridoTermodinamico';
import { TERMO_FUNDAMENTAL } from './recorridoTermodinamico';
import type { SolicitudEnsamblajeV2, VolumenV2 } from './contratoEnsamblajeV2';
/** Shared versioned journals for the first law and thermodynamic closures.
 * These functions validate document structure; Python develops the mathematics. */
import type { FormulacionEnergia, RecorridoEnergia } from './recorridoEnergia';
import { ENERGIA_FUNDAMENTAL } from './recorridoEnergia';

export const stateKeys = ['monofasico', 'sinCambioFase', 'densidadConstante', 'modelo'] as const;
export type EnergyState = Omit<FormulacionEnergia, typeof stateKeys[number]>;
export type OperationEntry<S> = { origin: 'recorded' | 'reviewed_rebuild'; operations: { id: string; title: string; changes: Partial<S> }[] };
/** Author a document operation; the server validates and develops its result. */
export function appendRecordedOperation<S>(entry:OperationEntry<S>,title:string,changes:Partial<S>):OperationEntry<S>{
  let number=entry.operations.length+1;
  while(entry.operations.some(operation=>operation.id===`edit-${number}`))number++;
  return {...structuredClone(entry),operations:[...structuredClone(entry.operations),{id:`edit-${number}`,title,changes:structuredClone(changes)}]};
}
export type EnergyJournal = { format: 'rage.energy-derivation'; version: 1; volumes: Record<string, OperationEntry<EnergyState>> };
export type EnergyContext = { fixed: boolean; remainderClosed: boolean; streamIds: string[]; pressurePrescribed: boolean };
export type EnergyDevelopment = { format: 'rage.energy-development'; version: 1; volumeId: string;
  origin: OperationEntry<EnergyState>['origin']; formulation: EnergyState; steps: {id:string;title:string;latex:string}[]; notes:string[] };
export const emptyEnergyJournal = (): EnergyJournal => ({format:'rage.energy-derivation',version:1,volumes:{}});
export const energyState = (value: Partial<FormulacionEnergia>): Partial<EnergyState> => structuredClone(Object.fromEntries(Object.entries(value).filter(([key])=>!stateKeys.includes(key as typeof stateKeys[number]))));
export function sameDocument(a:unknown,b:unknown):boolean {
  if(a===b)return true;
  if(!a||!b||typeof a!=='object'||typeof b!=='object')return false;
  const x=a as Record<string,unknown>,y=b as Record<string,unknown>;
  return Object.keys(x).length===Object.keys(y).length&&Object.keys(x).every(key=>Object.hasOwn(y,key)&&sameDocument(x[key],y[key]));
}
function exact(value:unknown,fields:string[]):asserts value is Record<string,unknown>{
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).length!==fields.length||fields.some(key=>!Object.hasOwn(value,key)))throw new Error('Unknown or missing derivation fields.');
}
export function readEnergyJournal(value:unknown):EnergyJournal {
  exact(value,['format','version','volumes']);
  if(value.format!=='rage.energy-derivation'||value.version!==1||!value.volumes||typeof value.volumes!=='object'||Array.isArray(value.volumes)||Object.keys(value.volumes).length>160)throw new Error('Unsupported energy journal.');
  const baseline=energyState(ENERGIA_FUNDAMENTAL);
  for(const [owner,entry] of Object.entries(value.volumes)){
    exact(entry,['origin','operations']);
    if(!owner.trim()||!['recorded','reviewed_rebuild'].includes(entry.origin as string)||!Array.isArray(entry.operations)||entry.operations.length>400)throw new Error('Invalid energy volume journal.');
    const ids=new Set<string>();
    for(const operation of entry.operations){
      exact(operation,['id','title','changes']);
      if(typeof operation.id!=='string'||!operation.id.trim()||ids.has(operation.id)||typeof operation.title!=='string'||!operation.title.trim())throw new Error('Invalid energy operation identity.');
      ids.add(operation.id);
      if(!operation.changes||typeof operation.changes!=='object'||Array.isArray(operation.changes)||!Object.keys(operation.changes).length)throw new Error('Energy changes are required.');
      for(const [key,item] of Object.entries(operation.changes))if(!Object.hasOwn(baseline,key)||(key==='forma'?!['local','integrada','integral','total'].includes(item as string):typeof item!=='boolean'))throw new Error('Invalid energy operation field.');
    }
  }
  const journal=value as unknown as EnergyJournal;
  for(const entry of Object.values(journal.volumes)) replayEnergy(entry);
  return journal;
}
function replayEnergy(entry:OperationEntry<EnergyState>):EnergyState {
  let state=energyState(ENERGIA_FUNDAMENTAL) as EnergyState;
  for(const operation of entry.operations){state={...state,...operation.changes};if(state.entalpia&&!state.separarPresion)throw new Error('Separate pressure stress before collecting enthalpy.');if(state.trabajoTotalHeredado)throw new Error('Declare explicit stress and boundary-work terms instead of legacy total work.');if(state.presionPrescrita&&!state.presionUniforme)throw new Error('Declare uniform pressure before prescribing its time history.');}
  return state;
}
export const energyJournalMatches=(entry:OperationEntry<EnergyState>,formulation:Partial<FormulacionEnergia>)=>sameDocument(replayEnergy(entry),{...energyState(ENERGIA_FUNDAMENTAL),...energyState(formulation)});
export function energyJournalInRequest(value:unknown):EnergyJournal|undefined {
  if(value&&typeof value==='object'&&Object.hasOwn(value,'energyDerivation'))return readEnergyJournal((value as {energyDerivation:unknown}).energyDerivation);
}
export function energyJournalFromHistory(history:RecorridoEnergia):OperationEntry<EnergyState>|undefined {
  if(!history.pasos.length||!sameDocument(energyState(history.pasos[0].formulacion),energyState(ENERGIA_FUNDAMENTAL)))throw new Error('Energy history must start from the fundamental first law.');
  if(history.pasos.slice(1).some(step=>!step.operation))return undefined;
  let previous=history.pasos[0].formulacion;
  const operations:OperationEntry<EnergyState>['operations']=[];
  for(const [index,step] of history.pasos.slice(1).entries()){
    if(!sameDocument({...previous,...step.operation!.changes},step.formulacion))throw new Error('The energy operation differs from its stored result.');
    const changes=energyState(step.operation!.changes);
    if(Object.keys(changes).length)operations.push({id:`energy-history-${index+1}`,title:step.titulo,changes});
    previous=step.formulacion;
  }
  const result={origin:'recorded' as const,operations};
  readEnergyJournal({...emptyEnergyJournal(),volumes:{history:result}});
  return result;
}
export function derivationFingerprint(value:unknown):unknown {
  if(!value||typeof value!=='object')return undefined;
  const metadata=value as Record<string,unknown>;
  const entries=Object.entries(metadata).filter(([key,item])=>['materialDerivation','energyDerivation','thermodynamicDerivation','dynamicDefinition','momentumDerivation'].includes(key)&&item!==undefined);
  return entries.length?Object.fromEntries(entries):undefined;
}
export async function requestEnergyDevelopment(journal:EnergyJournal,volumeId:string,context:EnergyContext,action?:{kind:string},signal?:AbortSignal):Promise<{journal:EnergyJournal;development:EnergyDevelopment}>{
  const response=await fetch(`${process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004'}/modelo/energy-derivation`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({journal,volumeId,context,...(action?{action}:{})}),cache:'no-store',signal:signal?AbortSignal.any([signal,AbortSignal.timeout(15000)]):AbortSignal.timeout(15000)});
  const result=await response.json();
  if(!response.ok)throw new Error(result?.detail?.message??`Energy development is unavailable (HTTP ${response.status}).`);
  exact(result,['journal','development']);readEnergyJournal(result.journal);
  exact(result.development,['format','version','volumeId','origin','formulation','steps','notes']);
  const body=result as unknown as {journal:EnergyJournal;development:EnergyDevelopment},development=body.development;
  if(development.format!=='rage.energy-development'||development.version!==1||development.volumeId!==volumeId||!Array.isArray(development.steps)||!development.steps.length||!Array.isArray(development.notes)||development.notes.some(note=>typeof note!=='string')||!body.journal.volumes[volumeId]||!energyJournalMatches(body.journal.volumes[volumeId],development.formulation))throw new Error('Invalid energy development response.');
  for(const step of development.steps){exact(step,['id','title','latex']);if((['id','title','latex'] as const).some(key=>typeof step[key]!=='string'))throw new Error('Invalid energy development step.');}
  return body;
}

export type ThermodynamicClosure={packageId:string;model:{id:string;version:string};policy:VolumenV2['politica']};
export type ThermodynamicState=SupuestosTermo&{closure:ThermodynamicClosure|null};
export type ThermodynamicJournal={format:'rage.thermodynamic-derivation';version:1;volumes:Record<string,OperationEntry<ThermodynamicState>>};
export type ThermodynamicDevelopment=Omit<EnergyDevelopment,'format'|'formulation'>&{format:'rage.thermodynamic-development';formulation:ThermodynamicState};
export const emptyThermodynamicJournal=():ThermodynamicJournal=>({format:'rage.thermodynamic-derivation',version:1,volumes:{}});
export const fundamentalThermodynamics=():ThermodynamicState=>({...TERMO_FUNDAMENTAL,closure:null});
export function readThermodynamicJournal(value:unknown):ThermodynamicJournal {
  exact(value,['format','version','volumes']);
  if(value.format!=='rage.thermodynamic-derivation'||value.version!==1||!value.volumes||typeof value.volumes!=='object'||Array.isArray(value.volumes)||Object.keys(value.volumes).length>160)throw new Error('Unsupported thermodynamic journal.');
  const baseline=fundamentalThermodynamics();
  for(const [owner,entry] of Object.entries(value.volumes)){
    exact(entry,['origin','operations']);
    if(!owner.trim()||!['recorded','reviewed_rebuild'].includes(entry.origin as string)||!Array.isArray(entry.operations)||entry.operations.length>400)throw new Error('Invalid thermodynamic volume journal.');
    const ids=new Set<string>();
    for(const operation of entry.operations){
      exact(operation,['id','title','changes']);
      if(typeof operation.id!=='string'||!operation.id.trim()||ids.has(operation.id)||typeof operation.title!=='string'||!operation.title.trim())throw new Error('Invalid thermodynamic operation identity.');
      ids.add(operation.id);
      if(!operation.changes||typeof operation.changes!=='object'||Array.isArray(operation.changes)||!Object.keys(operation.changes).length)throw new Error('Thermodynamic changes are required.');
      for(const [key,item] of Object.entries(operation.changes)){
        if(!Object.hasOwn(baseline,key))throw new Error('Unknown thermodynamic operation field.');
        if(key==='closure'&&item!==null){
          exact(item,['packageId','model','policy']);exact(item.model,['id','version']);
          if([item.packageId,...Object.values(item.model)].some(value=>typeof value!=='string'||!value.trim()))throw new Error('A configured package and version are required.');
          const policy=item.policy as Record<string,unknown>;
          if(!policy||typeof policy!=='object'||Array.isArray(policy)||Object.keys(policy).some(key=>!['cantidad','cambioInterno','evaluacion','tiposPermitidos'].includes(key))||!['sin_restriccion','monofasico'].includes(policy.cantidad as string)||!['permitido','prohibido'].includes(policy.cambioInterno as string)||policy.evaluacion!=='equilibrio_estable')throw new Error('Invalid thermodynamic phase policy.');
          if(policy.tiposPermitidos!==undefined&&(!Array.isArray(policy.tiposPermitidos)||!policy.tiposPermitidos.length||new Set(policy.tiposPermitidos).size!==policy.tiposPermitidos.length||policy.tiposPermitidos.some(value=>!['vapor','liquido','solido'].includes(value))))throw new Error('Invalid permitted phase types.');
        }else if(key==='modelo'?!['sin_declarar','u_lineal'].includes(item as string):key!=='closure'&&typeof item!=='boolean')throw new Error('Invalid thermodynamic assumption.');
      }
    }
  }
  const journal=value as unknown as ThermodynamicJournal;
  for(const entry of Object.values(journal.volumes))replayThermodynamics(entry);
  return journal;
}
export function replayThermodynamics(entry:OperationEntry<ThermodynamicState>):ThermodynamicState {
  let state=fundamentalThermodynamics();
  for(const operation of entry.operations){
    state={...state,...structuredClone(operation.changes)};
    if(state.closure&&(state.modelo!=='sin_declarar'||state.densidadConstante||state.monofasico!==(state.closure.policy.cantidad==='monofasico')||state.sinCambioFase!==(state.closure.policy.cambioInterno==='prohibido')))throw new Error('The package closure conflicts with the recorded assumptions.');
  }
  return state;
}
export function configuredClosure(request:SolicitudEnsamblajeV2,volume:VolumenV2):ThermodynamicClosure {
  const selected=request.paquetes.find(item=>item.id===volume.paqueteId);
  if(!selected)throw new Error('The volume has no configured thermodynamic package.');
  return {packageId:selected.id,model:structuredClone(selected.modelo),policy:structuredClone(volume.politica)};
}
export function thermodynamicJournalMatches(entry:OperationEntry<ThermodynamicState>,formulation:Partial<FormulacionEnergia>,closure:ThermodynamicClosure|null):boolean {
  return sameDocument(replayThermodynamics(entry),{...fundamentalThermodynamics(),...Object.fromEntries(Object.entries(formulation).filter(([key])=>stateKeys.includes(key as typeof stateKeys[number]))),closure});
}
export function thermodynamicJournalInRequest(value:unknown):ThermodynamicJournal|undefined {
  if(value&&typeof value==='object'&&Object.hasOwn(value,'thermodynamicDerivation'))return readThermodynamicJournal((value as {thermodynamicDerivation:unknown}).thermodynamicDerivation);
}
export function thermodynamicJournalFromHistory(history:RecorridoTermodinamico):OperationEntry<ThermodynamicState>|undefined {
  if(!history.pasos.length||!sameDocument(history.pasos[0].supuestos,TERMO_FUNDAMENTAL))throw new Error('Thermodynamic history must start from the fundamental relations.');
  if(history.pasos.slice(1).some(step=>!step.operation))return undefined;
  let previous=history.pasos[0].supuestos;
  const operations:OperationEntry<ThermodynamicState>['operations']=[];
  for(const [index,step] of history.pasos.slice(1).entries()){
    if(!sameDocument({...previous,...step.operation!.changes},step.supuestos))throw new Error('The thermodynamic operation differs from its stored result.');
    if(Object.keys(step.operation!.changes).some(key=>!stateKeys.includes(key as typeof stateKeys[number])))throw new Error('Unknown thermodynamic history operation.');
    if(Object.keys(step.operation!.changes).length)operations.push({id:`thermodynamic-history-${index+1}`,title:step.titulo,changes:structuredClone(step.operation!.changes)});
    previous=step.supuestos;
  }
  const result={origin:'recorded' as const,operations};
  readThermodynamicJournal({...emptyThermodynamicJournal(),volumes:{history:result}});
  return result;
}
export async function requestThermodynamicDevelopment(journal:ThermodynamicJournal,volumeId:string,fixed:boolean,action?:{kind:string},configured?:ThermodynamicClosure,signal?:AbortSignal):Promise<{journal:ThermodynamicJournal;development:ThermodynamicDevelopment}>{
  const response=await fetch(`${process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004'}/modelo/thermodynamic-derivation`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({journal,volumeId,fixed,...(action?{action}:{}),...(configured?{configured}:{})}),cache:'no-store',signal:signal?AbortSignal.any([signal,AbortSignal.timeout(15000)]):AbortSignal.timeout(15000)});
  const result=await response.json();
  if(!response.ok)throw new Error(result?.detail?.message??`Thermodynamic development is unavailable (HTTP ${response.status}).`);
  exact(result,['journal','development']);readThermodynamicJournal(result.journal);
  exact(result.development,['format','version','volumeId','origin','formulation','steps','notes']);
  const body=result as unknown as {journal:ThermodynamicJournal;development:ThermodynamicDevelopment},development=body.development;
  const entry=body.journal.volumes[volumeId];
  if(development.format!=='rage.thermodynamic-development'||development.version!==1||development.volumeId!==volumeId||!entry||development.origin!==entry.origin||!sameDocument(replayThermodynamics(entry),development.formulation)||!Array.isArray(development.steps)||!development.steps.length||!Array.isArray(development.notes)||development.notes.some(note=>typeof note!=='string'))throw new Error('Invalid thermodynamic development response.');
  for(const step of development.steps){exact(step,['id','title','latex']);if((['id','title','latex'] as const).some(key=>typeof step[key]!=='string'))throw new Error('Invalid thermodynamic development step.');}
  return body;
}
