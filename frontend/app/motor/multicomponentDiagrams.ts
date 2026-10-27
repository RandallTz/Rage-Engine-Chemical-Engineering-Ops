import type {ContextoMuestraEquilibrio} from './contextoMuestraEquilibrio';
import type {CantidadEstado} from './contratoTermodinamica';
import type {
  CompositionLineRequest,CompositionLineResponse,LineRow,MulticomponentCapabilities,MulticomponentCertificate,
  MulticomponentDiagnostic,PerfilResolucion,PublishedPhase,TernaryLiquidLiquidRequest,TernaryLiquidLiquidResponse,
} from './contratoDiagramasEquilibrio';

/** Multicomponent diagram reader (F8): strict structural checks of the backend publication. Nothing here
 * computes equilibrium, continues a branch, projects a phase or normalizes a composition. */
function fail(message:string):never{throw new Error(`Incompatible multicomponent diagram: ${message}.`);}
const text=(v:unknown):v is string=>typeof v==='string'&&v.length>0;
const finite=(v:unknown):v is number=>typeof v==='number'&&Number.isFinite(v);
const STATUS=['complete','partial','no_coexistence','invalid','incomplete','unsupported'];
const REJECTED=['invalid','incomplete','unsupported'];

function composition(v:Record<string,number>,ids:string[],where:string){
  if(!v||typeof v!=='object'||Object.keys(v).length!==ids.length||!ids.every(id=>finite(v[id])&&v[id]>=0&&v[id]<=1))fail(`${where}: one mole fraction per component`);
  if(Math.abs(ids.reduce((s,id)=>s+v[id],0)-1)>1e-10)fail(`${where}: composition is not normalized`);
}
function diagnostics(list:MulticomponentDiagnostic[]){
  if(!Array.isArray(list))fail('diagnostics');
  for(const d of list)if(!text(d.code)||typeof d.path!=='string'||!text(d.message)||!['invalid','incomplete','unsupported','aviso'].includes(d.status)||!Array.isArray(d.componentIds))fail('diagnostic');
}
/** A published 'pass' must be consistent with its own residuals and stability. */
function certificate(c:MulticomponentCertificate,where:string){
  const ids=new Set(['mu_equality','normalization','fixed_condition','distinct_phases']);
  if(!c||!['pass','fail'].includes(c.status)||!Array.isArray(c.residuals)||!c.residuals.length||!c.stability)fail(`${where}: certificate`);
  for(const r of c.residuals){
    if(!ids.has(r.id)||!finite(r.value)||r.value<0||!finite(r.tolerance)||r.tolerance<=0||!text(r.scale)||!['pass','fail'].includes(r.status))fail(`${where}: residual`);
    const ok=r.id==='distinct_phases'?r.value>r.tolerance:r.value<=r.tolerance;
    if((r.status==='pass')!==ok)fail(`${where}: residual status contradicts its value`);
  }
  const s=c.stability;
  if(!['stable','unstable'].includes(s.status)||!finite(s.tmMinimum)||!finite(s.tolerance)||s.tolerance<=0||!Number.isInteger(s.trials)||s.trials<1||!text(s.method))fail(`${where}: stability`);
  if((s.status==='stable')!==(s.tmMinimum>=-s.tolerance))fail(`${where}: stability status contradicts tm`);
  if(c.status==='pass'&&(s.status!=='stable'||c.residuals.some(r=>r.status!=='pass')))fail(`${where}: a passing certificate with a failing check`);
}
function phases(list:PublishedPhase[],ids:string[],want:string[],where:string){
  if(!Array.isArray(list)||list.length!==want.length||list.some((p,k)=>p.id!==want[k]||p.kind!==(p.id==='vapor'?'vapor':'liquid')))fail(`${where}: phases`);
  for(const p of list)composition(p.composition,ids,`${where}/${p.id}`);
}
function identity(r:{identity:TernaryLiquidLiquidResponse['identity']},s:{model:{id:string;version:string};expectedModelFingerprint?:string}){
  const i=r.identity;
  if(!i||!text(i.tracer?.id)||!text(i.tracer.version))fail('identity');
  if(i.model.id!==s.model.id||i.model.version!==s.model.version)fail('another package answered');
  if(s.expectedModelFingerprint&&i.modelFingerprint!==null&&i.modelFingerprint!==s.expectedModelFingerprint)fail('another parameter fingerprint answered');
}
function envelope(raw:unknown,s:{requestId:string;components:{id:number;identidadQuimica?:{cas?:string}}[];model:{id:string;version:string};expectedModelFingerprint?:string},operation:string){
  const r=raw as TernaryLiquidLiquidResponse;
  if(!r||r.revision!==1||r.requestId!==s.requestId||r.operation!==operation||!STATUS.includes(r.status))fail('identity or structure');
  diagnostics(r.diagnostics);identity(r,s);
  if(REJECTED.includes(r.status)){if(r.condition!==null||!r.diagnostics.some(d=>d.status===r.status))fail('a rejection without its diagnostic');return null;}
  const c=r.condition;
  if(!c||!finite(c.T)||c.T<=0||!finite(c.P)||c.P<=0||!Array.isArray(c.components)||c.components.length!==s.components.length||c.components.some((x,k)=>x.id!==s.components[k].id||x.cas!==s.components[k].identidadQuimica?.cas))fail('condition or components');
  if(!text(r.identity.modelFingerprint)||!text(r.identity.querySignature))fail('fingerprint or signature');
  return c.components.map(x=>String(x.id));
}

export function readTernaryLiquidLiquid(raw:unknown,s:TernaryLiquidLiquidRequest):TernaryLiquidLiquidResponse{
  const ids=envelope(raw,s,'ternary_liquid_liquid'),r=raw as TernaryLiquidLiquidResponse;
  if(!ids||!('tieLines' in r))return r;
  if(ids.length!==3)fail('three components');
  if(![r.branches,r.tieLines,r.specialPoints,r.incidences].every(Array.isArray)||!text(r.method))fail('structure');
  if(r.status==='no_coexistence'&&(r.branches.length||r.incidences.length))fail('no_coexistence with branches');
  if(r.status==='complete'&&(r.incidences.length||!r.branches.length))fail('complete with incidences or without branches');
  if(r.status==='partial'&&!r.incidences.length)fail('partial without an incidence');
  const branchIds=new Set(r.branches.map(b=>b.id)),ties=new Map(r.tieLines.map(t=>[t.id,t]));
  const special=new Map(r.specialPoints.map(p=>[p.id,p])),incid=new Map(r.incidences.map(i=>[i.id,i]));
  if(branchIds.size!==r.branches.length||ties.size!==r.tieLines.length||special.size!==r.specialPoints.length||incid.size!==r.incidences.length)fail('duplicate identifiers');
  for(const t of r.tieLines){
    if(!branchIds.has(t.branchId)||!['flash_seed','continuation'].includes(t.origin))fail(`tie line ${t.id}`);
    phases(t.phases,ids,['liquid-a','liquid-b'],`tie line ${t.id}`);certificate(t.certificate,`tie line ${t.id}`);
    // Only certified tie lines are published as equilibrium.
    if(t.certificate.status!=='pass')fail(`tie line ${t.id} is not certified`);
  }
  const used=new Set<string>();
  for(const b of r.branches){
    if(!Array.isArray(b.tieLineIds)||!b.tieLineIds.length||b.tieLineIds.some(id=>ties.get(id)?.branchId!==b.id||used.has(id)))fail(`branch ${b.id} tie lines`);
    b.tieLineIds.forEach(id=>used.add(id));
    if(!Array.isArray(b.ends)||b.ends.length!==2||b.ends[0].side!=='start'||b.ends[1].side!=='end')fail(`branch ${b.id} ends`);
    for(const e of b.ends){
      const ref='specialPointId' in e?special.get(e.specialPointId):incid.get(e.incidenceId);
      if(!ref||ref.branchId!==b.id||ref.side!==e.side)fail(`branch ${b.id} end reference`);
    }
  }
  if(used.size!==ties.size)fail('a tie line outside every branch');
  for(const p of r.specialPoints){
    if(!branchIds.has(p.branchId)||!text(p.description))fail(`special point ${p.id}`);
    if(p.kind==='plait_point'){
      composition(p.composition,ids,`plait point ${p.id}`);
      const c=p.certificate,q=c?.residuals?.[0];
      if(!c||!['pass','fail'].includes(c.status)||c.residuals.length!==1||q.id!=='criticality'||!finite(q.value)||q.value<0||!finite(q.tolerance)||(q.status==='pass')!==(q.value<=q.tolerance))fail(`plait point ${p.id} criticality`);
      if(!['stable','unstable'].includes(c.stability?.status)||!finite(c.stability.tolerance)||(c.stability.tmOtherPhase!==null&&!finite(c.stability.tmOtherPhase)))fail(`plait point ${p.id} stability`);
      if((c.status==='pass')!==(q.status==='pass'&&c.stability.status==='stable'))fail(`plait point ${p.id} status`);
    }else if(p.kind==='binary_edge'){
      phases(p.phases,ids,['liquid-a','liquid-b'],`binary edge ${p.id}`);certificate(p.certificate,`binary edge ${p.id}`);
      if(!ids.includes(String(p.absentComponentId))||p.phases.some(ph=>ph.composition[String(p.absentComponentId)]!==0))fail(`binary edge ${p.id}: the absent component`);
    }else if(p.kind==='three_phase'){
      phases(p.phases,ids,['liquid-a','liquid-b','vapor'],`triangle ${p.id}`);certificate(p.certificate,`triangle ${p.id}`);
    }else fail(`special point kind ${(p as {kind:string}).kind}`);
  }
  for(const i of r.incidences)if(!['budget','no_convergence','competing_phase'].includes(i.kind)||!text(i.cause)||!text(i.action)||(i.branchId!==null&&!branchIds.has(i.branchId)))fail(`incidence ${i.id}`);
  return r;
}

function row(x:LineRow,ids:string[],where:string){
  if(!text(x.id)||!finite(x.l)||x.l<0||x.l>1||!Array.isArray(x.phases)||!x.phases.length||typeof x.certified!=='boolean'||!Array.isArray(x.checks)||(x.tmMinimum!==null&&!finite(x.tmMinimum)))fail(where);
  composition(x.feed,ids,`${where} feed`);
  for(const p of x.phases){if(!['liquid','vapor'].includes(p.kind)||!finite(p.fraction)||p.fraction<0||p.fraction>1)fail(`${where} phase`);composition(p.composition,ids,`${where} phase`);}
  if(Math.abs(x.phases.reduce((s,p)=>s+p.fraction,0)-1)>1e-9)fail(`${where}: phase fractions`);
  if(JSON.stringify(x.phases.map(p=>p.kind))!==JSON.stringify(x.phaseSet))fail(`${where}: phase set`);
  for(const c of x.checks)if(!text(c.id)||!finite(c.residual)||!finite(c.tolerance))fail(`${where}: check`);
  if(x.certified!==x.checks.every(c=>c.residual<=c.tolerance))fail(`${where}: certified flag contradicts its checks`);
}
export function readCompositionLine(raw:unknown,s:CompositionLineRequest):CompositionLineResponse{
  const ids=envelope(raw,s,'composition_line'),r=raw as CompositionLineResponse;
  if(!ids||!('rows' in r))return r;
  if(!['complete','partial'].includes(r.status)||![r.rows,r.boundaries,r.failures].every(Array.isArray)||!['complete_walk','budget'].includes(r.completion)||!text(r.method))fail('structure');
  for(const end of ['start','end'] as const){composition(r.condition.line?.[end],ids,`line ${end}`);if(ids.some(id=>r.condition.line[end][id]!==s.line[end][id]))fail(`line ${end} differs from the request`);}
  r.rows.forEach((x,k)=>{row(x,ids,`row ${x.id}`);if(k&&x.l<=r.rows[k-1].l)fail('rows are not ordered by l');});
  for(const b of r.boundaries){
    if(!Array.isArray(b.lInterval)||b.lInterval.length!==2||!b.lInterval.every(finite)||b.lInterval[0]<0||b.lInterval[1]>1||b.lInterval[0]>b.lInterval[1])fail(`boundary ${b.id}`);
    row(b.before,ids,`boundary ${b.id} before`);row(b.after,ids,`boundary ${b.id} after`);
    if(b.before.l!==b.lInterval[0]||b.after.l!==b.lInterval[1]||JSON.stringify(b.before.phaseSet)===JSON.stringify(b.after.phaseSet))fail(`boundary ${b.id}: ends`);
  }
  const certified=r.rows.every(x=>x.certified)&&r.boundaries.every(b=>b.before.certified&&b.after.certified);
  if((r.status==='complete')!==(certified&&!r.failures.length&&r.completion==='complete_walk'))fail('status contradicts rows, failures or completion');
  return r;
}
export function readMulticomponentCapabilities(raw:unknown):MulticomponentCapabilities{
  const c=raw as MulticomponentCapabilities;
  if(!c||c.revision!==1||!Array.isArray(c.operations)||!Array.isArray(c.profiles)||!Array.isArray(c.packages)||!Array.isArray(c.unsupported))fail('capabilities');
  if(['ternary_liquid_liquid','composition_line'].some(id=>!c.operations.some(o=>o.id===id&&text(o.route)&&text(o.tracer?.id))))fail('capability operations');
  for(const p of c.profiles)if(!['exploratoria','refinada'].includes(p.id)||!finite(p.limitSeconds)||p.limitSeconds<=0)fail('capability profile');
  for(const p of c.packages)if(!text(p.model?.id)||!text(p.model.version)||!Array.isArray(p.componentsCAS))fail('capability package');
  return c;
}

// --- requests from the selected sample: identities copied, never a species dropped ----------------------------
type Base={requestId:string;components:TernaryLiquidLiquidRequest['components'];model:TernaryLiquidLiquidRequest['model'];expectedModelFingerprint?:string;pureData?:TernaryLiquidLiquidRequest['pureData']};
function base(c:ContextoMuestraEquilibrio,requestId:string):Base{
  return {requestId,components:structuredClone(c.componentes),model:structuredClone(c.modelo),...(c.huellaParametros?{expectedModelFingerprint:c.huellaParametros}:{}),...(c.datosPuros?{pureData:structuredClone(c.datosPuros)}:{})};
}
export function prepareTernaryRequest(c:ContextoMuestraEquilibrio,T:CantidadEstado,P:CantidadEstado,resolution:PerfilResolucion,requestId:string):TernaryLiquidLiquidRequest{
  if(c.componentes.length!==3)throw new Error(`The volume keeps its ${c.componentes.length} components; the ternary diagram needs exactly three.`);
  return {revision:1,...base(c,requestId),condition:{T:structuredClone(T),P:structuredClone(P)},resolution};
}
export function prepareLineRequest(c:ContextoMuestraEquilibrio,T:CantidadEstado,P:CantidadEstado,start:Record<string,number>,end:Record<string,number>,resolution:PerfilResolucion,requestId:string):CompositionLineRequest{
  const ids=c.componentes.map(x=>String(x.id));
  for(const z of [start,end])if(Object.keys(z).length!==ids.length||!ids.every(id=>finite(z[id])))throw new Error('Enter one mole fraction for every component of the volume.');
  return {revision:1,...base(c,requestId),condition:{T:structuredClone(T),P:structuredClone(P)},line:{start:{...start},end:{...end}},resolution};
}
/** The sample's overall feed composition, as published by the trajectory (no rounding or renormalization). */
export function sampleFeed(c:ContextoMuestraEquilibrio){return Object.fromEntries(c.inventarios.map(x=>[String(x.id),x.z]));}

// --- service ---------------------------------------------------------------------------------------------------
const API=(process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004')+'/motor/termodinamica/diagramas';
async function query(route:string,body?:object,signal?:AbortSignal,budgetMs=90000){
  const timeout=AbortSignal.timeout(budgetMs),r=await fetch(`${API}/${route}`,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:undefined,body:body?JSON.stringify(body):undefined,cache:'no-store',signal:signal?AbortSignal.any([signal,timeout]):timeout});
  if(r.status===404)throw new Error('This backend does not publish multicomponent diagrams yet.');
  if(!r.ok||!r.headers.get('content-type')?.includes('application/json'))throw new Error(`Diagram service unavailable (HTTP ${r.status}).`);
  return r.json() as Promise<unknown>;
}
export async function multicomponentCapabilities(signal?:AbortSignal){return readMulticomponentCapabilities(await query('multicomponent/capabilities',undefined,signal,20000));}
export async function traceTernary(s:TernaryLiquidLiquidRequest,signal?:AbortSignal,budgetMs=90000){return readTernaryLiquidLiquid(await query('ternary-liquid-liquid',s,signal,budgetMs),s);}
export async function traceLine(s:CompositionLineRequest,signal?:AbortSignal,budgetMs=90000){return readCompositionLine(await query('composition-line',s,signal,budgetMs),s);}

// --- plot data: published compositions verbatim, in the response's order ------------------------------------------
export type TernaryPlot={
  sides:{branchId:string;phase:'liquid-a'|'liquid-b';points:{id:string;x:number[]}[]}[];
  tieLines:{id:string;a:number[];b:number[]}[];
  plaitPoints:{id:string;x:number[]}[];
  edges:{id:string;a:number[];b:number[]}[];
  triangles:{id:string;x:number[][]}[];
};
/** Vectors in the order of `order` (component IDs). Only certified marks are returned for drawing. */
export function ternaryPlot(r:TernaryLiquidLiquidResponse,order:number[]):TernaryPlot{
  const empty={sides:[],tieLines:[],plaitPoints:[],edges:[],triangles:[]};
  if(!('tieLines' in r))return empty;
  if(order.length!==3||order.some(id=>!r.condition.components.some(c=>c.id===id)))throw new Error('The plot order must name the three components.');
  const v=(x:Record<string,number>)=>order.map(id=>x[String(id)]),ties=new Map(r.tieLines.map(t=>[t.id,t]));
  return {
    sides:r.branches.flatMap(b=>(['liquid-a','liquid-b'] as const).map((phase,k)=>({branchId:b.id,phase,points:b.tieLineIds.map(id=>({id,x:v(ties.get(id)!.phases[k].composition)}))}))),
    tieLines:r.tieLines.map(t=>({id:t.id,a:v(t.phases[0].composition),b:v(t.phases[1].composition)})),
    plaitPoints:r.specialPoints.flatMap(p=>p.kind==='plait_point'&&p.certificate.status==='pass'?[{id:p.id,x:v(p.composition)}]:[]),
    edges:r.specialPoints.flatMap(p=>p.kind==='binary_edge'&&p.certificate.status==='pass'?[{id:p.id,a:v(p.phases[0].composition),b:v(p.phases[1].composition)}]:[]),
    triangles:r.specialPoints.flatMap(p=>p.kind==='three_phase'&&p.certificate.status==='pass'?[{id:p.id,x:p.phases.map(ph=>v(ph.composition))}]:[]),
  };
}
export type LinePlot={rows:{id:string;l:number;phases:{kind:'liquid'|'vapor';fraction:number}[];feed:number[]}[];boundaries:{id:string;l:[number,number];before:number[];after:number[]}[];start:number[];end:number[]};
/** Certified rows only; uncertified rows stay in the table and the JSON, never drawn as equilibrium. */
export function linePlot(r:CompositionLineResponse,order:number[]):LinePlot{
  if(!('rows' in r))return {rows:[],boundaries:[],start:[],end:[]};
  const v=(x:Record<string,number>)=>order.map(id=>x[String(id)]);
  return {rows:r.rows.filter(x=>x.certified).map(x=>({id:x.id,l:x.l,phases:x.phases.map(p=>({kind:p.kind,fraction:p.fraction})),feed:v(x.feed)})),
    boundaries:r.boundaries.filter(b=>b.before.certified&&b.after.certified).map(b=>({id:b.id,l:b.lInterval,before:v(b.before.feed),after:v(b.after.feed)})),
    start:v(r.condition.line.start),end:v(r.condition.line.end)};
}
