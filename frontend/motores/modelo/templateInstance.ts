/** Transport and identity validation only. Python replays and certifies the recipe. */
import type {ModeloComun} from './contrato';
import {leerModeloComun} from './lector';
import {responseError} from './assessment';
import {steadySignature} from './steadyContract';

type IdentityMap=Record<'volumes'|'streams'|'exchanges'|'ports'|'quantities'|'equations',Record<string,string>>;
export type TemplateProvenance={format:'rage.template-instance';version:1;sourceModelId:string;templateId:string;templateVersion:string;equipment:boolean;identityMap:IdentityMap;sourceSignature:string;instanceSignature:string;equationSignatures:Record<string,{instanceId:string;signature:string}>};
export type TemplateInstance={format:'rage.template-instance.response';version:1;model:ModeloComun;provenance:TemplateProvenance};
const object=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
const keys=(v:unknown,fields:string[])=>object(v)&&Object.keys(v).length===fields.length&&fields.every(k=>Object.hasOwn(v,k));
const same=(a:unknown,b:unknown)=>steadySignature(a)===steadySignature(b);
const digest=(v:unknown)=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
export function readTemplateInstance(value:unknown,source:ModeloComun):TemplateInstance{
  const fail=():never=>{throw new Error('Invalid template instance identity or replay evidence.');};
  if(!keys(value,['format','version','model','provenance']))return fail();
  const v=value as TemplateInstance,p=v.provenance,t=source.template;
  if(v.format!=='rage.template-instance.response'||v.version!==1||!t||!keys(p,['format','version','sourceModelId','templateId','templateVersion','equipment','identityMap','sourceSignature','instanceSignature','equationSignatures'])||p.format!=='rage.template-instance'||p.version!==1||p.sourceModelId!==source.id||p.templateId!==t.id||p.templateVersion!==t.templateVersion||p.equipment!==t.equipment||!digest(p.sourceSignature)||!digest(p.instanceSignature))return fail();
  const model=leerModeloComun(v.model),maps=p.identityMap;
  if(model.id===source.id||!model.template||!keys(maps,['volumes','streams','exchanges','ports','quantities','equations'])||!same(model.procedencia.templateInstance,p))return fail();
  for(const map of Object.values(maps))if(!object(map)||!Object.values(map).every(id=>typeof id==='string'&&id.length>0)||new Set(Object.values(map)).size!==Object.keys(map).length)return fail();
  for(const [group,original,target] of [['volumes',source.volumenes,model.volumenes],['streams',source.corrientes,model.corrientes],['exchanges',source.intercambios,model.intercambios],['ports',t.ports,model.template.ports]] as const){
    const map=maps[group],old=original.map(r=>r.id),next=target.map(r=>r.id);
    if(!same(Object.keys(map).sort(),[...old].sort())||!same(Object.values(map).sort(),[...next].sort())||next.some(id=>old.includes(id)))return fail();
  }
  const expected=structuredClone(t);expected.ports=expected.ports.map(port=>({...port,id:maps.ports[port.id],volumeId:maps.volumes[port.volumeId],boundary:{...port.boundary,id:port.boundary.type==='stream'?maps.streams[port.boundary.id]:port.boundary.type==='exchange'?maps.exchanges[port.boundary.id]:port.boundary.id}}));
  if(!same(expected,model.template)||!same(Object.keys(source.datos).sort(),Object.keys(model.datos).sort()))return fail();
  for(const [id,datum]of Object.entries(source.datos))if(!same(datum.declaracion,model.datos[id].declaracion)||datum.magnitud!==model.datos[id].magnitud||datum.funcion!==model.datos[id].funcion)return fail();
  for(const [original,target,map]of [[source.corrientes,model.corrientes,maps.streams],[source.intercambios,model.intercambios,maps.exchanges]] as const)for(const boundary of original){
    const next=target.find(row=>row.id===map[boundary.id]);
    if(!next||(['desde','hasta'] as const).some(end=>next[end]!== (boundary[end]===null?null:maps.volumes[boundary[end]])))return fail();
  }
  if(!object(p.equationSignatures)||!same(Object.keys(p.equationSignatures).sort(),Object.keys(maps.equations).sort()))return fail();
  for(const [id,evidence]of Object.entries(p.equationSignatures))if(!keys(evidence,['instanceId','signature'])||evidence.instanceId!==maps.equations[id]||!digest(evidence.signature))return fail();
  return v;
}
export async function requestTemplateInstance(model:ModeloComun):Promise<TemplateInstance>{
  const response=await fetch(`${process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004'}/modelo/template-instance`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({format:'rage.template-instance.request',version:1,model}),cache:'no-store',signal:AbortSignal.timeout(120000)});
  const value=await response.json();
  if(!response.ok)throw responseError(value,response.status,'The template recipe could not be replayed.');
  return readTemplateInstance(value,model);
}
