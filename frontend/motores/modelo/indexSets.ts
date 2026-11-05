import type {ModeloComun} from './contrato';
import {leerModeloComun} from './lector';
import {responseError} from './assessment';
import {readTemplateInstance,type TemplateInstance} from './templateInstance';
import type {TemplatePort,Corriente} from './contrato';
import {steadySignature} from './steadyContract';

export type {IndexSet,StageIndex} from './indexSetContract';
import {readIndexSet as readRecord,keys,fail,text} from './indexSetContract';
export const readIndexSet=(model:ModeloComun)=>readRecord(model,leerModeloComun);

type Endpoint={stage:number;modelId:string;portId:string;volumeId:string;boundary:TemplatePort['boundary']};
export type IndexSetExpansion={format:'rage.index-set-expansion';version:1;sourceModelId:string;sourceSignature:string;
  indexSetId:string;count:number;stages:(TemplateInstance&{index:number;template:string})[];
  connections:{id:string;kind:TemplatePort['kind'];from:Endpoint;to:Endpoint}[];
  internalStreams:{stream:Corriente;dataModelId:string;replaces:Endpoint[]}[];
  ports:{endpoint:Endpoint;port:TemplatePort}[];execution:'not_lowered'};
export function readIndexSetExpansion(value:unknown,model:ModeloComun):IndexSetExpansion{
  const set=readIndexSet(model),v=keys(value,'expansion',['format','version','sourceModelId','sourceSignature','indexSetId','count','stages','connections','internalStreams','ports','execution']) as unknown as IndexSetExpansion;
  if(v.format!=='rage.index-set-expansion'||v.version!==1||v.execution!=='not_lowered'||v.sourceModelId!==model.id||v.indexSetId!==set.id||v.count!==Number(model.datos[set.countDataId].declaracion.texto)||typeof v.sourceSignature!=='string'||!/^[a-f0-9]{64}$/.test(v.sourceSignature))fail('expansion','Source or version mismatch.');
  for(const field of ['stages','connections','internalStreams','ports'] as const)if(!Array.isArray(v[field]))fail('expansion.'+field,'Expected a list.');
  if(v.stages.length!==v.count)fail('expansion.stages','Incorrect stage count.');
  const identities=new Set<string>();
  v.stages.forEach((stage,i)=>{
    keys(stage,'expansion.stages',['index','template','format','version','model','provenance']);
    const j=i+1,variant=set.variants.find(x=>(x.at==='first'?1:x.at==='last'?v.count:x.at)===j);
    if(stage.index!==j||stage.template!==(variant?.template??set.genericStage))fail('expansion.stages','Incorrect stage or variant.');
    const {index,template,...instance}=stage;readTemplateInstance(instance,set.templates[template]);
    for(const id of [stage.model.id,...stage.model.volumenes.map(x=>x.id),...stage.model.corrientes.map(x=>x.id)]){if(identities.has(id))fail('expansion.stages','Repeated instance identity.');identities.add(id);}
  });
  const bound=new Set<string>();
  const endpoint=(e:Endpoint)=>{
    keys(e,'expansion.endpoint',['stage','modelId','portId','volumeId','boundary']);keys(e.boundary,'expansion.endpoint.boundary',['type','id']);
    const stage=v.stages[e.stage-1],port=stage?.model.template?.ports.find(p=>p.id===e.portId);
    if(!Number.isInteger(e.stage)||!port||e.modelId!==stage.model.id||e.volumeId!==port.volumeId||e.boundary.id!==port.boundary.id||e.boundary.type!==port.boundary.type)fail('expansion.endpoint','Unknown instance boundary.');
    const identity=JSON.stringify([e.stage,e.portId]);if(bound.has(identity))fail('expansion.endpoint','A port is bound twice.');bound.add(identity);return port!;
  };
  const same=(a:unknown,b:unknown)=>steadySignature(a)===steadySignature(b);
  const originalPort=(e:Endpoint)=>Object.entries(v.stages[e.stage-1].provenance.identityMap.ports).find(([,id])=>id===e.portId)?.[0];
  const connectionIds=new Set<string>();
  if(v.connections.length!==set.connections.length*(v.count-1))fail('expansion.connections','Incorrect connection count.');
  v.connections.forEach(c=>{
    keys(c,'expansion.connections',['id','kind','from','to']);text(c.id,'expansion.connection.id');
    if(connectionIds.has(c.id))fail('expansion.connections','Repeated connection identity.');connectionIds.add(c.id);
    const a=endpoint(c.from),b=endpoint(c.to);
    if(a.direction!=='outlet'||b.direction!=='inlet'||a.kind!==c.kind||b.kind!==c.kind||!set.connections.some(rule=>rule.outlet===originalPort(c.from)&&rule.inlet===originalPort(c.to)&&c.to.stage-c.from.stage===rule.offset))fail('expansion.connections','Incompatible or undeclared connection.');
  });
  const material=v.connections.filter(c=>c.kind==='material');
  if(v.internalStreams.length!==material.length)fail('expansion.internalStreams','Incorrect material stream count.');
  v.internalStreams.forEach((row,i)=>{
    keys(row,'expansion.internalStreams',['stream','dataModelId','replaces']);const c=material[i];
    const donor=v.stages[c.from.stage-1].model.corrientes.find(s=>s.id===c.from.boundary.id)!;
    const expected={...donor,id:c.id,desde:c.from.volumeId,hasta:c.to.volumeId};delete expected.estadoExterior;
    if(!same(row.stream,expected)||row.dataModelId!==c.from.modelId||!same(row.replaces,[c.from,c.to]))fail('expansion.internalStreams','Incorrect stream replacement.');
  });
  v.ports.forEach(row=>{
    keys(row,'expansion.ports',['endpoint','port']);const original=endpoint(row.endpoint),j=row.endpoint.stage;
    if(!same({...row.port,id:original.id},original)||!set.exposures.some(rule=>row.port.id===`${rule.id}.${j}`&&rule.port===originalPort(row.endpoint)&&(rule.at==='each'||(rule.at==='first'?1:rule.at==='last'?v.count:rule.at)===j)))fail('expansion.ports','Changed or undeclared typed port.');
  });
  if(bound.size!==v.stages.reduce((sum,s)=>sum+s.model.template!.ports.length,0))fail('expansion.ports','Unbound stage port.');
  return v;
}

export async function requestIndexSetExpansion(model:ModeloComun,signal?:AbortSignal):Promise<IndexSetExpansion>{
  readIndexSet(model);
  const response=await fetch(`${process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004'}/modelo/index-set-expansion`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({format:'rage.index-set-expansion.request',version:1,model}),signal:signal?AbortSignal.any([signal,AbortSignal.timeout(600000)]):AbortSignal.timeout(600000)});
  const result=await response.json();if(!response.ok)throw responseError(result,response.status,'The indexed template could not be expanded.');
  return readIndexSetExpansion(result,model);
}
