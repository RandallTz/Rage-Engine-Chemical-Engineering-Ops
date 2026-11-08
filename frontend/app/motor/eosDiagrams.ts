import type {ContextoMuestraEquilibrio} from './contextoMuestraEquilibrio';
import type {CantidadEstado} from './contratoTermodinamica';

/** Elevated-pressure EOS diagrams (F8b lane A, contract revision 1): `peng-robinson-vdw1f` and `psrk-unifac`.
 * Types, request preparation, strict reader and plot projection of POST /modelo/eos-diagrams. Nothing here computes
 * equilibrium, continues a branch, interpolates, completes or normalizes a composition: the backend computes and
 * certifies everything that is drawn. Description: docs/contracts/thermodynamic-layer.md ("EOS diagrams"). */
export const EOS_REVISION=1;
export const EOS_PACKAGES=['peng-robinson-vdw1f','psrk-unifac'] as const;
export type EosPackageId=typeof EOS_PACKAGES[number];
export const EOS_PACKAGE_LABEL:Record<EosPackageId,string>={'peng-robinson-vdw1f':'Peng–Robinson (van der Waals one-fluid mixing)','psrk-unifac':'PSRK (SRK + UNIFAC mixing rule)'};
export type EosOperation='saturation_curve'|'isotherm'|'critical_locus';
export type EosDiagnostic={code:string;status:'invalid'|'incomplete'|'unsupported';path:string;message:string;componentIds:number[]};
export type EosComponent={id:number;identidadQuimica:{cas:string}};
type Base={revision:1;requestId:string;package:{id:EosPackageId;version:'1'};components:EosComponent[];points:number};
export type EosSaturationRequest=Base&{operation:'saturation_curve';composition:Record<string,number>;kind:'bubble'|'dew';temperatureRange:{from:CantidadEstado;to:CantidadEstado}};
export type EosIsothermRequest=Base&{operation:'isotherm';condition:{T:CantidadEstado};fractionRange?:[number,number]};
export type EosLocusRequest=Base&{operation:'critical_locus';fractionRange?:[number,number]};
export type EosRequest=EosSaturationRequest|EosIsothermRequest|EosLocusRequest;
export type EosCertificate={fugacity:number;normalization:number;distinction:number;tolerance:number;status:'pass'|'fail'};
export type EosSaturationPoint={T:number;P:number;liquid:Record<string,number>;vapor:Record<string,number>;certificate:EosCertificate};
export type EosLocusPoint={x:number;composition:Record<string,number>;T:number;P:number;V:number;kappa:number;kind:string;roots:number};
export type EosRejected={T?:number;x?:number;cause:string;message:string};
export type EosCapabilities={revision:1;packages:{model:{id:EosPackageId;version:'1'}}[];operations:{id:EosOperation;limit:number}[];budgetSeconds:number};
export type EosResponse={
  revision:1;requestId:string;operation:EosOperation;status:'ok'|'partial'|'no_points'|'invalid'|'incomplete'|'unsupported';
  identity:{package:{id:string;version:string};querySignature:string|null;components?:{id:number;cas:string}[]};
  units?:{T:'K';P:'Pa';V:'m3/mol'};points:(EosSaturationPoint|EosLocusPoint)[];rejected:EosRejected[];budget?:{seconds:number;limitSeconds:number};diagnostics:EosDiagnostic[];
};

function fail(message:string):never{throw new Error(`Incompatible EOS diagram: ${message}.`);}
const text=(v:unknown):v is string=>typeof v==='string'&&v.length>0;
const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const REJECTED=['invalid','incomplete','unsupported'];
const OK=['ok','partial','no_points'];

export function readEosCapabilities(raw:unknown):EosCapabilities{
  const c=raw as EosCapabilities;
  if(!c||c.revision!==EOS_REVISION||!Array.isArray(c.packages)||!Array.isArray(c.operations)||!finite(c.budgetSeconds))fail('capabilities');
  if(c.packages.some(p=>!EOS_PACKAGES.includes(p.model?.id)||p.model.version!=='1'))fail('capabilities: unknown package');
  return c;
}

function composition(v:Record<string,number>,ids:string[],where:string){
  if(!v||typeof v!=='object'||Object.keys(v).length!==ids.length||!ids.every(id=>finite(v[id])&&v[id]>=0&&v[id]<=1))fail(`${where}: one mole fraction per component`);
  if(Math.abs(ids.reduce((s,id)=>s+v[id],0)-1)>1e-9)fail(`${where}: composition is not normalized`);
}
/** A published 'pass' must be consistent with its own residuals. */
function certificate(c:EosCertificate,where:string){
  if(!c||!['pass','fail'].includes(c.status)||![c.fugacity,c.normalization,c.distinction,c.tolerance].every(finite)||c.tolerance<=0)fail(`${where}: certificate`);
  const ok=c.fugacity<=c.tolerance&&c.normalization<=1e-12&&c.distinction>1e-6;
  if((c.status==='pass')!==ok)fail(`${where}: certificate status contradicts its residuals`);
}

/** Strict reader: identity, structure and consistency of everything the chart will draw. */
export function readEosResponse(raw:unknown,s:EosRequest):EosResponse{
  const r=raw as EosResponse;
  if(!r||r.revision!==EOS_REVISION||r.requestId!==s.requestId||r.operation!==s.operation||!(OK.includes(r.status)||REJECTED.includes(r.status)))fail('identity or structure');
  if(!Array.isArray(r.diagnostics)||!Array.isArray(r.points)||!Array.isArray(r.rejected))fail('arrays');
  for(const d of r.diagnostics)if(!text(d.code)||typeof d.path!=='string'||!text(d.message)||!REJECTED.includes(d.status)||!Array.isArray(d.componentIds))fail('diagnostic');
  if(REJECTED.includes(r.status)){if(r.points.length||!r.diagnostics.some(d=>d.status===r.status))fail('a rejection without its diagnostic');return r;}
  if(r.identity?.package?.id!==s.package.id||r.identity.package.version!==s.package.version)fail('another package answered');
  if(!text(r.identity.querySignature))fail('query signature');
  const comps=r.identity.components;
  if(!Array.isArray(comps)||comps.length!==s.components.length||comps.some((x,k)=>x.id!==s.components[k].id||x.cas!==s.components[k].identidadQuimica.cas))fail('components');
  const ids=comps.map(c=>String(c.id));
  if(!r.units||r.units.T!=='K'||r.units.P!=='Pa')fail('units');
  if(r.status==='ok'&&(!r.points.length||r.rejected.length))fail('status ok contradicts its points');
  if(r.status==='partial'&&(!r.points.length||!r.rejected.length))fail('status partial contradicts its points');
  if(r.status==='no_points'&&r.points.length)fail('status no_points with points');
  if(r.points.length+r.rejected.length>s.points)fail('more points than requested');
  for(const q of r.rejected)if(!text(q.cause)||typeof q.message!=='string'||!(finite(q.T)||finite(q.x)))fail('rejected point');
  r.points.forEach((p,k)=>{
    if(!finite(p.T)||p.T<=0||!finite(p.P)||p.P<=0)fail(`point ${k}: T and P`);
    if(s.operation==='critical_locus'){
      const l=p as EosLocusPoint;
      if(!finite(l.x)||l.x<=0||l.x>=1||!finite(l.V)||l.V<=0||!finite(l.kappa)||!text(l.kind)||!Number.isInteger(l.roots)||l.roots<1)fail(`point ${k}: locus`);
      composition(l.composition,ids,`point ${k}`);
    }else{
      const q=p as EosSaturationPoint;
      composition(q.liquid,ids,`point ${k}/liquid`);composition(q.vapor,ids,`point ${k}/vapor`);certificate(q.certificate,`point ${k}`);
      if(q.certificate.status!=='pass')fail(`point ${k}: a published point must pass its certificate`);
      if(s.operation==='isotherm'&&s.condition.T.valor!==null&&Math.abs(q.T-s.condition.T.valor)>1e-9*Math.max(1,q.T)&&s.condition.T.unidad==='K')fail(`point ${k}: another temperature`);
    }
  });
  if(s.operation==='saturation_curve')for(let k=1;k<r.points.length;k++)if(!((r.points[k] as EosSaturationPoint).T>(r.points[k-1] as EosSaturationPoint).T))fail('temperatures are not increasing');
  if(s.operation!=='saturation_curve'&&r.points.length>1){
    const key=(p:EosSaturationPoint|EosLocusPoint)=>s.operation==='isotherm'?(p as EosSaturationPoint).liquid[String(s.components[0].id)]:(p as EosLocusPoint).x;
    for(let k=1;k<r.points.length;k++)if(!(key(r.points[k])>key(r.points[k-1])))fail('compositions are not increasing');
  }
  return r;
}

const MESSAGE_LIMIT_S=1000;
const API=(process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004')+'/modelo/eos-diagrams';
async function query(path:string,body?:EosRequest,signal?:AbortSignal,budgetMs=20000){
  const r=await fetch(API+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined,cache:'no-store',signal:signal?AbortSignal.any([signal,AbortSignal.timeout(budgetMs)]):AbortSignal.timeout(budgetMs)});
  if(r.status===404)throw new Error('The EOS diagram service is not available in this backend.');
  if(!r.ok||!r.headers.get('content-type')?.includes('application/json'))throw new Error(`EOS diagram service unavailable (HTTP ${r.status}).`);
  return r.json() as Promise<unknown>;
}
export async function eosCapabilities(signal?:AbortSignal){return readEosCapabilities(await query('/capabilities',undefined,signal));}
export async function traceEos(s:EosRequest,signal?:AbortSignal,budgetSeconds=170){return readEosResponse(await query('',s,signal,MESSAGE_LIMIT_S*budgetSeconds),s);}

/** The species and conditions of the selected sample; the overall composition is the sample's own inventory. */
export function eosComponents(m:ContextoMuestraEquilibrio):EosComponent[]{
  return m.componentes.map(c=>{const cas=c.identidadQuimica?.cas;if(!cas)throw new Error(`Component ${c.nombre} has no CAS number: a name does not identify a model.`);return {id:c.id,identidadQuimica:{cas}};});
}
export function eosFeed(m:ContextoMuestraEquilibrio):Record<string,number>{
  const total=m.inventarios.reduce((s,i)=>s+i.n,0);
  if(!(total>0))throw new Error('The sample has no amount of substance.');
  return Object.fromEntries(m.inventarios.map(i=>[String(i.id),i.n/total]));
}

export function prepareSaturationRequest(m:ContextoMuestraEquilibrio,pkg:EosPackageId,kind:'bubble'|'dew',from:CantidadEstado,to:CantidadEstado,points:number,composition:Record<string,number>,requestId:string):EosSaturationRequest{
  return {revision:1,requestId,operation:'saturation_curve',package:{id:pkg,version:'1'},components:eosComponents(m),composition,kind,temperatureRange:{from,to},points};
}
export function prepareIsothermRequest(m:ContextoMuestraEquilibrio,pkg:EosPackageId,T:CantidadEstado,range:[number,number],points:number,requestId:string):EosIsothermRequest{
  return {revision:1,requestId,operation:'isotherm',package:{id:pkg,version:'1'},components:eosComponents(m),condition:{T},fractionRange:range,points};
}
export function prepareLocusRequest(m:ContextoMuestraEquilibrio,pkg:EosPackageId,range:[number,number],points:number,requestId:string):EosLocusRequest{
  return {revision:1,requestId,operation:'critical_locus',package:{id:pkg,version:'1'},components:eosComponents(m),fractionRange:range,points};
}

export type EosSeries={id:string;label:string;dashed?:boolean;points:[number,number][]};
export type EosPlot={xLabel:string;yLabel:string;series:EosSeries[]};
/** Projection of the published points onto chart axes: no smoothing, no interpolation. T in K, P in bar. */
export function eosPlot(r:EosResponse,s:EosRequest,names:Record<string,string>):EosPlot{
  const first=String(s.components[0].id),bar=(p:number)=>p/1e5;
  if(s.operation==='critical_locus'){
    const pts=r.points as EosLocusPoint[];
    return {xLabel:'Critical temperature / K',yLabel:'Critical pressure / bar',series:[{id:'locus',label:`Critical locus (${names[first]??first} fraction increasing along the points)`,points:pts.map(p=>[p.T,bar(p.P)])}]};
  }
  const pts=r.points as EosSaturationPoint[];
  if(s.operation==='saturation_curve')return {xLabel:'Temperature / K',yLabel:'Pressure / bar',series:[{id:s.kind,label:s.kind==='bubble'?'Bubble pressure':'Dew pressure',points:pts.map(p=>[p.T,bar(p.P)])}]};
  return {xLabel:`${names[first]??first} mole fraction`,yLabel:'Pressure / bar',series:[
    {id:'liquid',label:'Bubble (liquid x)',points:pts.map(p=>[p.liquid[first],bar(p.P)])},
    {id:'vapor',label:'Dew (vapor y)',dashed:true,points:pts.map(p=>[p.vapor[first],bar(p.P)])}]};
}
