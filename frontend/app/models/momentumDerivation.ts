/** Strict transport/storage contract. All momentum algebra is produced by Python. */
import type { HojaMotor } from '../motor/hojasMotor';
import type { ModeloComun } from '../../motores/modelo/contrato';
import type { OperationEntry } from '../motor/physicalDerivation';
import { SIN_SUPUESTOS } from '../motor/familiasBalance';

export const baseMomentumFlags = ['pressureStress','newtonian','massContinuity','constantViscosity','divergenceFree','fixedBoundary','uniformSections','constantArea','referenceDensity','uniformGravity','darcyWeisbach','angularMomentum','shaftDynamics','zeroAngularAccumulation','zeroInletSwirl','radialOutlet','idealBladeGuidance','losslessPassage','equalPortMassFlow','noOtherTorque','impermeableWall','rotorActuator','adiabaticPassage','zeroPassageEnergyAccumulation'] as const;
export const fieldMomentumFlags=['expandCartesian','invariantX','invariantY','invariantZ','velocityInvariantX','velocityInvariantY','velocityInvariantZ','zeroVelocityX','zeroVelocityY','zeroVelocityZ','zeroLocalAccumulation','negligibleConvection','negligibleViscousStress','negligibleBodyForce','zeroTotalAccumulation','laminarCircular','circularSection','developedProfile','quasiSteadyWall','regularAxis','noSlipWall','verticalGravity','pressureReference','prismaticStorage'] as const;
export const momentumFlags=[...baseMomentumFlags,...fieldMomentumFlags] as const;
export type MomentumState = Record<typeof momentumFlags[number], boolean> & { form:'local'|'integral'|'ports'|'hydraulic'; inletStreamId:string|null; outletStreamId:string|null };
export type MomentumJournal = { format:'rage.momentum-derivation'; version:1; volumes:Record<string,OperationEntry<MomentumState>&{cursor?:number}> };
export type MomentumStep = { id:string; title:string; latex:string; family:'momentum'|'matter'|'energy'|'thermodynamics'; kind?:string;dependent?:boolean;derivation?:{rule:string;inputIds:string[];beforeLatex:string[];assumptions:string[]} };
export type MomentumControl={key:typeof momentumFlags[number];group:string;label:string;value:boolean;canChange:boolean;reason:string};
export type MomentumForm={id:MomentumState['form'];label:string;action:string;selected:boolean;canSelect:boolean;reason:string};
export type MomentumDevelopment = { format:'rage.momentum-development'; version:1; volumeId:string; origin:'recorded'|'reviewed_rebuild'; formulation:MomentumState; controls?:MomentumControl[]; forms?:MomentumForm[]; steps:MomentumStep[]; finalSteps:MomentumStep[]; couplingSteps:MomentumStep[]; variables:{id:string;symbol:string;name:string;unit:string;role:string}[]; requirements:{code:string;message:string}[]; available:{kind:string;title:string}[]; bindings:{inletStreamId:string|null;outletStreamId:string|null}; notes:string[] };
type Obj=Record<string,unknown>;
function exact(value:unknown,required:string[],optional:string[]=[]):Obj {
  if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('Expected a momentum contract object.');
  const data=value as Obj;
  if(required.some(key=>!(key in data))||Object.keys(data).some(key=>!required.includes(key)&&!optional.includes(key)))throw new Error('Unknown or missing momentum contract fields.');
  return data;
}
const text=(value:unknown):value is string=>typeof value==='string'&&!!value.trim();
function readChanges(value:unknown){
  const data=exact(value,[],['form','inletStreamId','outletStreamId',...momentumFlags]);
  if(!Object.keys(data).length)throw new Error('Empty momentum operation.');
  for(const [key,item]of Object.entries(data)){
    if(key==='form'){if(!['local','integral','ports','hydraulic'].includes(item as string))throw new Error('Unknown momentum representation.');}
    else if(key==='inletStreamId'||key==='outletStreamId'){if(item!==null&&!text(item))throw new Error('Invalid momentum stream identity.');}
    else if(typeof item!=='boolean')throw new Error('Momentum assumptions must be booleans.');
  }
  return data;
}
export function readMomentumJournal(value:unknown,model?:ModeloComun):MomentumJournal {
  const journal=exact(value,['format','version','volumes']);
  if(journal.format!=='rage.momentum-derivation'||journal.version!==1)throw new Error('Unsupported momentum journal.');
  const volumes=exact(journal.volumes,[],Object.keys((journal.volumes??{}) as Obj));
  if(Object.keys(volumes).length>160)throw new Error('Too many momentum volume journals.');
  for(const [owner,value]of Object.entries(volumes)){
    const entry=exact(value,['origin','operations'],['cursor']);
    if(!text(owner)||!['recorded','reviewed_rebuild'].includes(entry.origin as string)||!Array.isArray(entry.operations)||entry.operations.length>400)throw new Error('Invalid momentum journal entry.');
    if(entry.cursor!==undefined&&(!Number.isInteger(entry.cursor)||(entry.cursor as number)<0||(entry.cursor as number)>entry.operations.length))throw new Error('Invalid momentum history cursor.');
    const ids=new Set<string>();let form='local';const bindings:Record<string,string|null>={inletStreamId:null,outletStreamId:null};
    for(const [index,value]of entry.operations.entries()){
      const op=exact(value,['id','title','changes']);
      if(!text(op.id)||!text(op.title)||ids.has(op.id))throw new Error('Invalid or repeated momentum operation.');ids.add(op.id);
      const delta=readChanges(op.changes),fields=Object.keys(delta);
      if(fields.length!==1&&!(fields.length===2&&fields.includes('inletStreamId')&&fields.includes('outletStreamId')))throw new Error('Record one momentum assumption at a time.');
      if(delta.form){const forms=['local','integral','ports','hydraulic'];if(forms.indexOf(delta.form as string)!==forms.indexOf(form)+1)throw new Error('Skipped momentum deduction.');form=delta.form as string;}
      for(const key of ['inletStreamId','outletStreamId'])if(key in delta&&index<(entry.cursor as number??entry.operations.length))bindings[key]=delta[key] as string|null;
    }
    if(model){
      if(!model.volumenes.some(volume=>volume.id===owner))throw new Error('Missing momentum control volume.');
      for(const [key,endpoint]of [['inletStreamId','hasta'],['outletStreamId','desde']] as const){const id=bindings[key];if(id!==null&&!model.corrientes.some(stream=>stream.id===id&&stream[endpoint]===owner&&stream.desde!==stream.hasta))throw new Error('Momentum stream binding disagrees with topology.');}
      if(bindings.inletStreamId!==null&&bindings.inletStreamId===bindings.outletStreamId)throw new Error('Momentum ports must be distinct.');
    }
  }
  return value as MomentumJournal;
}
export function readMomentumDevelopment(value:unknown):MomentumDevelopment {
  const body=exact(value,['format','version','volumeId','origin','formulation','steps','finalSteps','couplingSteps','variables','requirements','available','bindings','notes'],['controls','forms']);
  if(body.format!=='rage.momentum-development'||body.version!==1||!text(body.volumeId)||!['recorded','reviewed_rebuild'].includes(body.origin as string))throw new Error('Invalid momentum development header.');
  const state=exact(body.formulation,['form','inletStreamId','outletStreamId',...baseMomentumFlags],[...fieldMomentumFlags]);readChanges(state);
  for(const key of ['steps','finalSteps','couplingSteps','variables','requirements','available','notes'])if(!Array.isArray(body[key]))throw new Error('Invalid momentum development collection.');
  for(const value of [...body.steps as unknown[],...body.finalSteps as unknown[],...body.couplingSteps as unknown[]]){const row=exact(value,['id','title','latex','family'],['derivation','kind','dependent']);if(!['id','title','latex','family'].every(k=>text(row[k]))||!['momentum','matter','energy','thermodynamics'].includes(row.family as string))throw new Error('Invalid momentum mathematical row.');if(row.kind!==undefined&&!text(row.kind)||row.dependent!==undefined&&typeof row.dependent!=='boolean')throw new Error('Invalid equation classification.');if(row.derivation!==undefined){const d=exact(row.derivation,['rule','inputIds','beforeLatex','assumptions']);if(!text(d.rule)||['inputIds','beforeLatex','assumptions'].some(k=>!Array.isArray(d[k])||(d[k] as unknown[]).some(item=>!text(item))))throw new Error('Invalid equation operation audit.');}}
  if([...body.steps as MomentumStep[],...body.finalSteps as MomentumStep[]].some(step=>step.family!=='momentum')||(body.couplingSteps as MomentumStep[]).some(step=>step.family==='momentum'))throw new Error('A physical equation is in the wrong family.');
  for(const value of body.variables as unknown[])if(!Object.values(exact(value,['id','symbol','name','unit','role'])).every(text))throw new Error('Invalid momentum variable.');
  for(const value of body.requirements as unknown[])if(!Object.values(exact(value,['code','message'])).every(text))throw new Error('Invalid momentum requirement.');
  for(const value of body.available as unknown[])if(!Object.values(exact(value,['kind','title'])).every(text))throw new Error('Invalid momentum operation choice.');
  const bindings=exact(body.bindings,['inletStreamId','outletStreamId']);if(Object.values(bindings).some(value=>value!==null&&!text(value)))throw new Error('Invalid momentum port references.');
  if((body.notes as unknown[]).some(value=>!text(value)))throw new Error('Invalid momentum scope.');
  if(body.controls!==undefined){
    if(!Array.isArray(body.controls))throw new Error('Invalid momentum controls.');
    const seen=new Set<string>();
    for(const value of body.controls){const c=exact(value,['key','group','label','value','canChange','reason']);if(!momentumFlags.includes(c.key as typeof momentumFlags[number])||seen.has(c.key as string)||!text(c.group)||!text(c.label)||typeof c.value!=='boolean'||typeof c.canChange!=='boolean'||typeof c.reason!=='string'||c.value!==(state[c.key as string]??false))throw new Error('Invalid momentum control.');seen.add(c.key as string);}
    if(seen.size!==momentumFlags.length)throw new Error('Incomplete momentum controls.');
  }
  if(body.forms!==undefined){
    if(!Array.isArray(body.forms))throw new Error('Invalid momentum forms.');
    const seen=new Set<string>();
    for(const value of body.forms){const form=exact(value,['id','label','action','selected','canSelect','reason']);if(!['local','integral','ports','hydraulic'].includes(form.id as string)||seen.has(form.id as string)||!text(form.label)||typeof form.action!=='string'||typeof form.selected!=='boolean'||typeof form.canSelect!=='boolean'||typeof form.reason!=='string'||form.selected!==(form.id===state.form))throw new Error('Invalid momentum representation control.');seen.add(form.id as string);}
    if(seen.size!==4)throw new Error('Incomplete momentum representations.');
  }
  return {...body,formulation:{...Object.fromEntries(fieldMomentumFlags.map(key=>[key,false])),...state}} as MomentumDevelopment;
}
export function momentumJournalOf(model:HojaMotor):MomentumJournal|undefined {
  const metadata=model.redTermodinamica?.solicitud.derivacion as Obj|undefined;
  const value=metadata?.momentumDerivation??model.momentumDerivation;
  return value===undefined?undefined:readMomentumJournal(value);
}
export function withMomentumJournal(model:HojaMotor,journal:MomentumJournal):HojaMotor {
  readMomentumJournal(journal);
  const previous=model.supuestosBalances?.momento;
  const legacy=previous&&Object.values(previous).some(Boolean)&&!momentumJournalOf(model)?{previousMomentumAssumptions:structuredClone(previous),supuestosBalances:{...model.supuestosBalances,momento:{...SIN_SUPUESTOS}}}:{};
  return {...model,...legacy,...(model.redTermodinamica?{redTermodinamica:{...model.redTermodinamica,solicitud:{...model.redTermodinamica.solicitud,derivacion:{...model.redTermodinamica.solicitud.derivacion as Obj,momentumDerivation:journal}}}}:{momentumDerivation:journal}),resultado:undefined,resultadoRef:undefined};
}
export function includeMomentum(model:HojaMotor,owner:string,active:boolean):HojaMotor {
  if(model.redTermodinamica){const request=model.redTermodinamica.solicitud;const volumes=request.volumenes.map(volume=>volume.id===owner?{...volume,balances:{...volume.balances,momento:active}}:volume);return {...model,balances:{...model.balances,materia:volumes.some(v=>v.balances.materia),energia:volumes.some(v=>v.balances.energia),momento:volumes.some(v=>v.balances.momento)},redTermodinamica:{...model.redTermodinamica,solicitud:{...request,volumenes:volumes}},resultado:undefined,resultadoRef:undefined};}
  if(model.ensamblaje){const volumes=model.ensamblaje.volumenes.map(v=>v.id===owner?{...v,balances:{materia:true,energia:false,...model.balances,...v.balances,momento:active}}:v);return {...model,ensamblaje:{...model.ensamblaje,volumenes:volumes},balances:{materia:true,energia:false,...model.balances,momento:volumes.some(v=>v.balances?.momento??model.balances?.momento)},resultado:undefined,resultadoRef:undefined};}
  return {...model,balances:{materia:true,energia:false,...model.balances,momento:active},resultado:undefined,resultadoRef:undefined};
}

/** Reference maintenance on explicit topology saves; never reconstruct physical assumptions. */
export function reconcileMomentumTopology(previous:HojaMotor|undefined,next:HojaMotor):HojaMotor {
  function topology(model:HojaMotor){
    if(model.redTermodinamica)return {owners:model.redTermodinamica.solicitud.volumenes.map(v=>v.id),streams:model.redTermodinamica.solicitud.corrientes.map(s=>({id:s.id,desde:s.desde,hasta:s.hasta}))};
    if(model.ensamblaje)return {owners:model.ensamblaje.volumenes.map(v=>v.id),streams:model.ensamblaje.corrientes.map(s=>({id:`s${s.id}`,desde:s.desde,hasta:s.hasta}))};
    const formulation=model.historial.pasos[model.historial.activo].formulacion;
    return {owners:['dominio'],streams:formulation.fronteras.map(p=>({id:`puerto.${p.id}`,desde:p.sentido==='salida'?'dominio':null,hasta:p.sentido==='entrada'?'dominio':null}))};
  }
  if(!previous||JSON.stringify(topology(previous))===JSON.stringify(topology(next)))return next;
  const journal=momentumJournalOf(next);if(!journal)return next;
  const current=topology(next),owners=new Set(current.owners),volumes=structuredClone(journal.volumes);
  const archive=structuredClone(next.archivedMomentumVolumes??previous.archivedMomentumVolumes??{});
  for(const [owner,entry]of Object.entries(volumes))if(!owners.has(owner)){archive[owner]=entry;delete volumes[owner];}
  for(const owner of owners)if(archive[owner]){if(!volumes[owner])volumes[owner]=archive[owner];delete archive[owner];}
  for(const [owner,entry]of Object.entries(volumes)){
    const ports:{inletStreamId:string|null;outletStreamId:string|null}={inletStreamId:null,outletStreamId:null};
    for(const operation of entry.operations)for(const key of ['inletStreamId','outletStreamId'] as const)if(key in operation.changes)ports[key]=operation.changes[key]??null;
    const repaired={...ports};
    for(const [key,endpoint]of [['inletStreamId','hasta'],['outletStreamId','desde']] as const)if(ports[key]!==null&&!current.streams.some(s=>s.id===ports[key]&&s[endpoint]===owner&&s.desde!==s.hasta))repaired[key]=null;
    if(JSON.stringify(ports)!==JSON.stringify(repaired)){
      let index=entry.operations.length+1;while(entry.operations.some(op=>op.id===`topology-ports-${index}`))index++;
      entry.operations.push({id:`topology-ports-${index}`,title:'Release port references invalidated by a topology edit',changes:repaired});
    }
  }
  if(JSON.stringify(volumes)===JSON.stringify(journal.volumes)&&JSON.stringify(archive)===JSON.stringify(next.archivedMomentumVolumes??{}))return next;
  return {...withMomentumJournal(next,{...journal,volumes}),archivedMomentumVolumes:archive};
}
