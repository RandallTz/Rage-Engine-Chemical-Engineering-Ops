/** Strict client mirror of core/modelo/flowsheet.py (`rage.flowsheet` v1).
 *
 * Structural, compatibility and topology admission only. Python owns template
 * replay, identities, signatures, lowering and solving; the client never
 * evaluates an equation. Rejections carry the same code and path as Python.
 * `flowsheetLayout` is presentation only: it never enters the executable
 * source, so moving a block keeps every Transform/Solve selection and result.
 */
import type {ModeloComun, TemplatePort} from './contrato';
import {leerResultados} from '../resultados/lector';
import type {ConjuntoResultados} from '../resultados/contrato';

export type FlowsheetEndpoint={instance:string;port:string};
export type FlowsheetInstance={id:string;template:string;data:Record<string,{texto:string;unidad:string}>};
export type FlowsheetConnection={id:string;from:FlowsheetEndpoint;to:FlowsheetEndpoint};
export type Flowsheet={format:'rage.flowsheet';version:1;id:string;templates:Record<string,ModeloComun>;
  instances:FlowsheetInstance[];connections:FlowsheetConnection[];exposures:{id:string;instance:string;port:string}[];recycles:string[]};
export type FlowsheetLayout={format:'rage.flowsheet-layout';version:1;flowsheetId:string;
  blocks:Record<string,{position:[number,number]}>;streams?:Record<string,{points:[number,number][]}>};
export type FlowsheetSelection={format:'rage.flowsheet-execution';version:1;sourceSignature:string;mode:'dynamic'|'steady'};

export class FlowsheetError extends Error{
  constructor(public code:string,public path:string,public reason:string){super(`${path}: [${code}] ${reason}`);}
}
const fail=(code:string,path:string,message:string):never=>{throw new FlowsheetError(code,path,message);};
type Obj=Record<string,unknown>;
const isObject=(v:unknown):v is Obj=>!!v&&typeof v==='object'&&!Array.isArray(v);
const IDENTITY=/^[A-Za-z][A-Za-z0-9_-]{0,63}$/;
const NUMBER=/^[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$/;
const MAX_INSTANCES=64;
export const canonical=(v:unknown):string=>JSON.stringify(v,(_,x)=>isObject(x)?Object.fromEntries(Object.entries(x).sort(([a],[b])=>a<b?-1:a>b?1:0)):x);
function exact(value:unknown,path:string,fields:string[],optional:string[]=[]):Obj{
  if(!isObject(value))fail('flowsheet_invalid',path,'Expected an object.');
  const o=value as Obj,missing=fields.filter(k=>!Object.hasOwn(o,k)),extra=Object.keys(o).filter(k=>!fields.includes(k)&&!optional.includes(k));
  if(missing.length||extra.length)fail('flowsheet_invalid',path,'Unknown or missing fields: '+[...missing,...extra].join(', '));
  return o;
}
const identity=(v:unknown,path:string)=>{if(typeof v!=='string'||!IDENTITY.test(v))fail('flowsheet_invalid_identity',path,'Expected an identity matching [A-Za-z][A-Za-z0-9_-]{0,63}.');};
const list=(v:unknown,path:string):unknown[]=>Array.isArray(v)?v:fail('flowsheet_invalid',path,'Expected a list.');

function streamSpecies(template:ModeloComun,streamId:string):(string|undefined)[]{
  const stream=template.corrientes.find(s=>s.id===streamId)!;
  const cas=new Map(template.componentes.map(c=>[c.id,(c as {identidadQuimica?:{cas?:string}}).identidadQuimica?.cas]));
  return stream.componenteIds.map(i=>cas.get(i));
}
function thermodynamicIdentity(template:ModeloComun,volumeId:string):string|null{
  const seen=new Set<string>();let current=volumeId;
  while(!seen.has(current)){
    seen.add(current);
    const volume=template.volumenes.find(v=>v.id===current);if(!volume)return null;
    const closure=(volume.termodinamica??{}) as Obj;
    if(closure.tipo==='equilibrio'){
      const pkg=template.termodinamica.paquetes.find(p=>p.id===closure.paqueteId);if(!pkg)return null;
      const energy=((volume.supuestos??{}) as Obj).energia as Obj|undefined;
      return canonical({package:pkg.modelo,formationReference:energy?.referenciaFormacion??null});
    }
    const donors=template.corrientes.filter(s=>s.hasta===current&&s.desde).map(s=>s.desde as string);
    if(donors.length!==1)return null;current=donors[0];
  }
  return null;
}

/** Mirrors read_flowsheet; readModel is the strict common-model reader. */
export function readFlowsheet(model:ModeloComun,readModel:(value:unknown)=>ModeloComun):Flowsheet{
  const r=exact((model as unknown as Obj).flowsheet,'flowsheet',['format','version','id','templates','instances','connections','exposures','recycles']) as unknown as Flowsheet;
  if(r.format!=='rage.flowsheet'||r.version!==1)fail('flowsheet_version','flowsheet.version','Expected rage.flowsheet version 1.');
  identity(r.id,'flowsheet.id');
  for(const field of ['volumenes','corrientes','intercambios'] as const)if(canonical(model[field])!=='[]')fail('flowsheet_shell',field,'A flowsheet shell owns no physical volumes, streams or exchanges; instances do.');
  if(canonical(model.motores)!=='{}'||model.matematico!==null||Object.hasOwn(model,'template')||Object.hasOwn(model,'indexSet'))fail('flowsheet_shell','motores','A flowsheet shell carries no journals, mathematical document, template or index set.');
  const study=model.estudio as Obj|null;
  if(!isObject(study)||study.tipo!=='temporal')fail('flowsheet_study','estudio','A flowsheet requires one temporal study shared by every instance.');
  if(model.datos[String(study!.tiempoId)].declaracion.unidad!=='s')fail('flowsheet_study','estudio.tiempoId','The shared horizon must be declared in seconds.');
  if(!isObject(r.templates)||!Object.keys(r.templates).length)fail('flowsheet_invalid','flowsheet.templates','At least one embedded template document is required.');
  for(const [key,source] of Object.entries(r.templates)){
    const path='flowsheet.templates.'+key;identity(key,path);
    if(!isObject(source)||Object.hasOwn(source,'indexSet')||Object.hasOwn(source,'flowsheet'))fail('flowsheet_nested',path,'Nested index sets or flowsheets are not admitted in version 1.');
    try{readModel(source);}catch(error){
      if(error instanceof FlowsheetError)throw error;
      const e=error as {ruta?:string;motivo?:string;message?:string};
      fail('flowsheet_template_invalid',path+'.'+(e.ruta??''),e.motivo??String(e.message));
    }
    if(!source.template?.equipment)fail('flowsheet_template_unmarked',path,'An instance requires an equipment-marked recorded template.');
    const local=source.estudio as Obj|null;
    if(!isObject(local)||local.tipo!=='temporal'||source.datos[String(local.tiempoId)].declaracion.unidad!=='s')fail('flowsheet_study',path+'.estudio','Each template requires a temporal study with a horizon in seconds.');
  }
  const instances=list(r.instances,'flowsheet.instances') as FlowsheetInstance[];
  if(instances.length<1||instances.length>MAX_INSTANCES)fail('flowsheet_invalid','flowsheet.instances','Version 1 admits one to 64 instances.');
  const byId=new Map<string,FlowsheetInstance>();
  instances.forEach((row,i)=>{
    const path=`flowsheet.instances[${i}]`;exact(row,path,['id','template','data']);identity(row.id,path+'.id');
    if(byId.has(row.id))fail('flowsheet_duplicate_instance',path+'.id','Duplicate instance identity.');
    if(typeof row.template!=='string'||!Object.hasOwn(r.templates,row.template))fail('flowsheet_unknown_template',path+'.template','Unknown template reference.');
    const source=r.templates[row.template];
    if(!isObject(row.data))fail('flowsheet_invalid',path+'.data','Expected an object of declared data values.');
    for(const [key,declaration] of Object.entries(row.data)){
      const where=path+'.data.'+key,datum=Object.hasOwn(source.datos,key)?source.datos[key]:undefined;
      if(!datum)fail('flowsheet_unknown_datum',where,'Only data declared by the template can be given instance values.');
      exact(declaration,where,['texto','unidad']);
      if(typeof declaration.texto!=='string'||!NUMBER.test(declaration.texto)||!Number.isFinite(Number(declaration.texto)))fail('flowsheet_invalid_datum',where,'Expected a finite numeric literal.');
      if(declaration.unidad!==datum!.declaracion.unidad)fail('flowsheet_datum_unit',where,'An instance value keeps the declared unit of its template datum.');
      if(key===(source.estudio as {tiempoId:string}).tiempoId)fail('flowsheet_study',where,'The horizon is the shared flowsheet study, not an instance datum.');
    }
    byId.set(row.id,row);
  });
  const ports=new Map<string,TemplatePort>();
  for(const row of instances)for(const port of r.templates[row.template].template!.ports)ports.set(JSON.stringify([row.id,port.id]),port);
  const used=new Map<string,string>(),connectionIds=new Set<string>();
  const take=(endpoint:unknown,path:string,direction:'inlet'|'outlet'):TemplatePort=>{
    const e=exact(endpoint,path,['instance','port']);
    if(typeof e.instance!=='string'||!byId.has(e.instance))fail('flowsheet_unknown_instance',path+'.instance','Unknown instance.');
    const key=JSON.stringify([e.instance,e.port]),port=typeof e.port==='string'?ports.get(key):undefined;
    if(!port)fail('flowsheet_unknown_port',path+'.port','Port does not exist on the instance template.');
    if(port!.direction!==direction)fail('flowsheet_port_direction',path+'.port',`Expected an ${direction} port.`);
    if(used.has(key))fail('flowsheet_port_reused',path,'This instance port is already bound at '+used.get(key)+'.');
    used.set(key,path);return port!;
  };
  const edges:[string,string,string][]=[];
  (list(r.connections,'flowsheet.connections') as FlowsheetConnection[]).forEach((row,i)=>{
    const at=`flowsheet.connections[${i}]`;exact(row,at,['id','from','to']);identity(row.id,at+'.id');
    if(connectionIds.has(row.id))fail('flowsheet_duplicate_connection',at+'.id','Duplicate connection identity.');
    connectionIds.add(row.id);
    // A valid, unique connection is located by identity, as in the Python assembly.
    const path='flowsheet.connections.'+row.id;
    if(!isObject(row.from)||!isObject(row.to))fail('flowsheet_invalid',path,'Expected from and to endpoints.');
    if(typeof row.from.instance==='string'&&row.from.instance===row.to.instance&&byId.has(row.from.instance))fail('flowsheet_self_connection',path,'A connection joins two different instances.');
    const a=take(row.from,path+'.from','outlet'),b=take(row.to,path+'.to','inlet');
    if(a.kind!==b.kind||canonical(a.variables)!==canonical(b.variables))fail('flowsheet_port_kind',path,'Connected ports require identical kinds and SI variable contracts.');
    if(a.kind!=='material')fail('flowsheet_unsupported_connection',path,'Version 1 connects material ports; heat and work ports are exposed.');
    const donor=r.templates[byId.get(row.from.instance)!.template],receiver=r.templates[byId.get(row.to.instance)!.template];
    if(a.boundary.type!=='stream'||b.boundary.type!=='stream'||(b as {exteriorState?:string}).exteriorState!=='estadoExterior')fail('flowsheet_port_kind',path,'A material connection joins a drawn outlet stream to an inlet with a declared exterior state.');
    const species=streamSpecies(donor,a.boundary.id),target=streamSpecies(receiver,b.boundary.id);
    if([...species,...target].some(s=>!s)||new Set(species).size!==species.length||new Set(target).size!==target.length||species.some(s=>!target.includes(s))||target.some(s=>!species.includes(s)))fail('flowsheet_component_mismatch',path,'Connected streams require the same distinct chemical identities (CAS).');
    const left=thermodynamicIdentity(donor,a.volumeId),right=thermodynamicIdentity(receiver,b.volumeId);
    if(left===null||right===null)fail('flowsheet_thermodynamic_unresolved',path,'Each connected port state must belong to a recorded package closure.');
    if(left!==right)fail('flowsheet_thermodynamic_mismatch',path,'Connected states require the same package model and the same recorded energy reference.');
    edges.push([row.id,row.from.instance,row.to.instance]);
  });
  const exposedIds=new Set<string>();
  (list(r.exposures,'flowsheet.exposures') as {id:string;instance:string;port:string}[]).forEach((row,i)=>{
    const path=`flowsheet.exposures[${i}]`;exact(row,path,['id','instance','port']);identity(row.id,path+'.id');
    if(connectionIds.has(row.id)||exposedIds.has(row.id))fail('flowsheet_duplicate_exposure',path+'.id','Duplicate exposed-port or connection identity.');
    if(typeof row.instance!=='string'||!byId.has(row.instance))fail('flowsheet_unknown_instance',path+'.instance','Unknown instance.');
    const key=JSON.stringify([row.instance,row.port]);
    if(typeof row.port!=='string'||!ports.has(key))fail('flowsheet_unknown_port',path+'.port','Port does not exist on the instance template.');
    if(used.has(key))fail('flowsheet_port_reused',path,'This instance port is already bound at '+used.get(key)+'.');
    used.set(key,path);exposedIds.add(row.id);
  });
  const order=[...byId.keys()];
  for(const key of ports.keys())if(!used.has(key)){const [instance,port]=JSON.parse(key) as [string,string];fail('flowsheet_dangling_port',`flowsheet.instances[${order.indexOf(instance)}]`,`Port ${port} of instance ${instance} must be connected or explicitly exposed.`);}
  const recycles=list(r.recycles,'flowsheet.recycles');
  if(new Set(recycles.map(String)).size!==recycles.length||recycles.some(x=>typeof x!=='string'||!connectionIds.has(x)))fail('flowsheet_unknown_recycle','flowsheet.recycles','Recycles list distinct existing connection identities.');
  checkCycles(edges,new Set(recycles as string[]),order);
  return r;
}

function checkCycles(edges:[string,string,string][],recycles:Set<string>,order:string[]){
  const graph=new Map(order.map(n=>[n,[] as string[]])),full=new Map(order.map(n=>[n,[] as string[]]));
  for(const [key,a,b] of edges){full.get(a)!.push(b);if(!recycles.has(key))graph.get(a)!.push(b);}
  const state=new Map<string,number>(),stack:string[]=[];
  const visit=(node:string)=>{
    state.set(node,1);stack.push(node);
    for(const target of graph.get(node)!){
      if(state.get(target)===1){
        const cycle=stack.slice(stack.indexOf(target));
        const names=edges.filter(([k,a,b])=>!recycles.has(k)&&cycle.includes(a)&&cycle.includes(b)).map(([k])=>k);
        fail('flowsheet_undeclared_cycle','flowsheet.recycles','The connections '+names.join(', ')+' form a cycle; declare one of them as a recycle.');
      }
      if(!state.has(target))visit(target);
    }
    stack.pop();state.set(node,2);
  };
  for(const node of order)if(!state.has(node))visit(node);
  for(const key of recycles){
    const [,a,b]=edges.find(([k])=>k===key)!;const seen=new Set<string>(),frontier=[b];
    while(frontier.length){const node=frontier.pop()!;if(!seen.has(node)){seen.add(node);frontier.push(...full.get(node)!);}}
    if(!seen.has(a))fail('flowsheet_recycle_not_cycle','flowsheet.recycles',`Connection ${key} does not close a cycle.`);
  }
}

/** Presentation only: mirrors read_layout. */
export function readFlowsheetLayout(model:ModeloComun):FlowsheetLayout{
  const m=model as unknown as Obj;
  const layout=exact(m.flowsheetLayout,'flowsheetLayout',['format','version','flowsheetId','blocks'],['streams']) as unknown as FlowsheetLayout;
  if(layout.format!=='rage.flowsheet-layout'||layout.version!==1)fail('flowsheet_layout_version','flowsheetLayout.version','Expected rage.flowsheet-layout version 1.');
  const sheet=m.flowsheet as Flowsheet|undefined;
  if(!sheet||layout.flowsheetId!==sheet.id)fail('flowsheet_layout_foreign','flowsheetLayout.flowsheetId','The layout belongs to another flowsheet.');
  const instances=new Set(sheet!.instances.map(r=>r.id)),connections=new Set(sheet!.connections.map(r=>r.id));
  const point=(v:unknown,path:string)=>{if(!Array.isArray(v)||v.length!==2||v.some(x=>typeof x!=='number'||!Number.isFinite(x)))fail('flowsheet_layout_invalid',path,'Expected a finite [x, y] point.');};
  if(!isObject(layout.blocks))fail('flowsheet_layout_invalid','flowsheetLayout.blocks','Expected an object keyed by instance.');
  for(const [key,block] of Object.entries(layout.blocks)){
    const path='flowsheetLayout.blocks.'+key;
    if(!instances.has(key))fail('flowsheet_layout_foreign',path,'Unknown instance.');
    exact(block,path,['position']);point(block.position,path+'.position');
  }
  const streams=layout.streams??{};
  if(!isObject(streams))fail('flowsheet_layout_invalid','flowsheetLayout.streams','Expected an object keyed by connection.');
  for(const [key,stream] of Object.entries(streams)){
    const path='flowsheetLayout.streams.'+key;
    if(!connections.has(key))fail('flowsheet_layout_foreign',path,'Unknown connection.');
    exact(stream,path,['points']);list(stream.points,path+'.points').forEach((v,i)=>point(v,`${path}.points[${i}]`));
  }
  return layout;
}

/** The executable source: everything except the layout. Equal sources keep selections and results. */
export function executableSource(model:ModeloComun):Obj{const {flowsheetLayout:_,...rest}=model as unknown as Obj;return rest;}
export const sameExecutableSource=(a:ModeloComun,b:ModeloComun)=>canonical(executableSource(a))===canonical(executableSource(b));

/** Topology edits clear Transform, Solve selections and results; layout edits keep them. */
export function invalidatedByEdit(before:ModeloComun,after:ModeloComun):boolean{return !sameExecutableSource(before,after);}

export function readFlowsheetSelection(value:unknown):FlowsheetSelection{
  const v=isObject(value)?value:{};
  if(!isObject(value)||Object.keys(v).sort().join('|')!=='format|mode|sourceSignature|version'||v.format!=='rage.flowsheet-execution'||v.version!==1||!['dynamic','steady'].includes(String(v.mode))||typeof v.sourceSignature!=='string'||!/^[a-f0-9]{64}$/.test(v.sourceSignature))
    fail('invalid_flowsheet_execution','flowsheetExecution','Expected flowsheet execution version 1.');
  return value as FlowsheetSelection;
}

type Stage={index:number;instanceId:string;template:string;modelId:string;signature:string;templateId:string;templateVersion:string;
  ports:{id:string;portId:string}[];stateCount:number;dynamicReport:Obj;steadyReport:Obj|null};
type Endpoint={stage:number;instanceId:string;port:string};
export type FlowsheetCompilation={format:'rage.flowsheet-compilation';version:1;sourceModelId:string;flowsheetId:string;count:number;
  selection:FlowsheetSelection;stages:Stage[];connections:{id:string;recycle:boolean;signature:string;from:Endpoint;to:Endpoint}[];
  ports:(Endpoint&{id:string;kind:string;direction:string})[];rateRows:{stage:number;quantityId:string;equationId:string;expressionSI:string}[];
  method:'RK45'|'BDF'|'damped_newton';specialization:'original_rates'|'zero_accumulation';linearPolicy:Obj;signature:string};

/** Mirrors read_compilation without the fingerprint (Python recomputes it). */
export function readFlowsheetCompilation(value:unknown):FlowsheetCompilation{
  const path='flowsheetCompilation',bad=(message:string,where=''):never=>fail('invalid_flowsheet_compilation',path+where,message);
  const fields='format version sourceModelId flowsheetId count selection stages connections ports rateRows method specialization linearPolicy signature'.split(' ');
  if(!isObject(value)||Object.keys(value).sort().join('|')!==[...fields].sort().join('|'))bad('Unknown or missing fields.');
  const r=value as unknown as FlowsheetCompilation;
  if(r.format!=='rage.flowsheet-compilation'||r.version!==1)bad('Expected flowsheet compilation version 1.','.version');
  const mode=readFlowsheetSelection(r.selection).mode;
  if(r.specialization!==(mode==='dynamic'?'original_rates':'zero_accumulation')||!(mode==='dynamic'?['RK45','BDF']:['damped_newton']).includes(r.method))bad('Mode and specialization disagree.','.specialization');
  if(!Number.isSafeInteger(r.count)||!Array.isArray(r.stages)||r.stages.length!==r.count)bad('Instance count mismatch.','.count');
  const stageFields='index instanceId template modelId signature templateId templateVersion ports stateCount dynamicReport steadyReport'.split(' ').sort().join('|');
  const declared=new Set<string>(),models=new Set<string>(),instances=new Map<string,number>(),expected:string[]=[];
  r.stages.forEach((stage,i)=>{
    const j=i+1;
    if(!isObject(stage)||Object.keys(stage).sort().join('|')!==stageFields||stage.index!==j)bad('Invalid instance row.',`.stages[${i}]`);
    if(instances.has(stage.instanceId)||models.has(stage.modelId))bad('Repeated instance or model identity.',`.stages[${i}]`);
    instances.set(stage.instanceId,j);models.add(stage.modelId);
    if(stage.dynamicReport?.sourceModelId!==stage.modelId)bad('Missing instance-local dynamic compilation.',`.stages[${i}].dynamicReport`);
    if((mode==='dynamic')!==(stage.steadyReport===null))bad('Steady specialization presence disagrees with the mode.',`.stages[${i}].steadyReport`);
    for(const port of stage.ports)declared.add(JSON.stringify([stage.instanceId,port.id]));
    const rows=((stage.dynamicReport.derivedExecution as Obj|undefined)?.selection as Obj|undefined)?.states as {quantityId:string;equationId:string}[]|undefined;
    if(!Array.isArray(rows)||rows.length!==stage.stateCount)bad('Missing original derivative rows.',`.stages[${i}]`);
    expected.push(...rows!.map(row=>JSON.stringify([j,row.quantityId,row.equationId])));
  });
  if(canonical(r.rateRows.map(row=>JSON.stringify([row.stage,row.quantityId,row.equationId])))!==canonical(expected))bad('Connected rates do not retain the original ordered rows.','.rateRows');
  const used=new Set<string>(),ids=new Set<string>();
  const take=(e:Endpoint,where:string)=>{const key=JSON.stringify([e?.instanceId,e?.port]);if(!declared.has(key)||instances.get(e.instanceId)!==e.stage||used.has(key))bad('Unknown, foreign or repeated instance port.',where);used.add(key);};
  r.connections.forEach((row,i)=>{
    if(!isObject(row)||Object.keys(row).sort().join('|')!=='from|id|recycle|signature|to'||ids.has(row.id))bad('Invalid or repeated connection.',`.connections[${i}]`);
    ids.add(row.id);take(row.from,`.connections[${i}].from`);take(row.to,`.connections[${i}].to`);
    if(row.from.instanceId===row.to.instanceId)bad('A connection joins two different instances.',`.connections[${i}]`);
  });
  r.ports.forEach((row,i)=>{
    if(!isObject(row)||Object.keys(row).sort().join('|')!=='direction|id|instanceId|kind|port|stage'||ids.has(row.id))bad('Invalid exposed port.',`.ports[${i}]`);
    ids.add(row.id);take(row,`.ports[${i}]`);
  });
  if(used.size!==declared.size)bad('Every instance port must be connected or exposed.','.ports');
  if(typeof r.signature!=='string'||!/^[a-f0-9]{64}$/.test(r.signature))bad('Missing compilation fingerprint.','.signature');
  return r;
}

/** Common results plus the flowsheet compilation; instance j is published stage j. */
export function readFlowsheetResult(value:unknown,selection?:FlowsheetSelection):{result:ConjuntoResultados;compilation:FlowsheetCompilation;instanceOwners:Record<string,string>}{
  const result=leerResultados(value),provenance=result.procedencia as unknown as Obj;
  const report=readFlowsheetCompilation(provenance.flowsheetCompilation);
  const metadata=((value as Obj).indexedNetwork??{}) as Obj;
  if(result.modeloId!==report.sourceModelId||provenance.motor!=='rage.compilador.flowsheet_network'||metadata.indexSetId!==report.flowsheetId||metadata.count!==report.count
     ||metadata.mode!==report.selection.mode||provenance.metodo!==report.method||provenance.firma!==report.selection.sourceSignature
     ||selection!==undefined&&canonical(readFlowsheetSelection(selection))!==canonical(report.selection))
    fail('invalid_flowsheet_result','procedencia.flowsheetCompilation','Result and flowsheet compilation disagree.');
  if(typeof provenance.flowsheetResultSignature!=='string'||!/^[a-f0-9]{64}$/.test(provenance.flowsheetResultSignature))fail('invalid_flowsheet_result','procedencia.flowsheetResultSignature','Missing flowsheet result fingerprint.');
  const instanceOwners=Object.fromEntries(report.stages.map(s=>[s.instanceId,`${report.flowsheetId}.stage.${s.index}`]));
  return {result,compilation:report,instanceOwners};
}

/** Structural reader of the Python expansion response against its source document. */
export function readFlowsheetExpansion(value:unknown,model:ModeloComun):Obj{
  const path='flowsheetExpansion';
  const v=exact(value,path,['format','version','sourceModelId','sourceSignature','flowsheetId','indexSetId','count','stages','connections','internalStreams','ports','execution','signatures']);
  if(v.format!=='rage.flowsheet-expansion'||v.version!==1)fail('flowsheet_expansion_version',path+'.version','Expected rage.flowsheet-expansion version 1.');
  if(v.sourceModelId!==model.id||typeof v.sourceSignature!=='string'||!/^[a-f0-9]{64}$/.test(v.sourceSignature))fail('flowsheet_stale_expansion',path+'.sourceSignature','The flowsheet source changed; expand it again.');
  if(v.execution!=='not_lowered')fail('flowsheet_invalid',path+'.execution','An expansion is not an execution.');
  const sheet=(model as unknown as Obj).flowsheet as Flowsheet;
  const stages=v.stages as Obj[];
  if(v.flowsheetId!==sheet.id||v.indexSetId!==sheet.id||v.count!==sheet.instances.length||!Array.isArray(stages)||stages.length!==v.count)fail('flowsheet_invalid',path,'The expansion does not describe this flowsheet.');
  stages.forEach((stage,i)=>{if(stage.index!==i+1||stage.instanceId!==sheet.instances[i].id||stage.templateRef!==sheet.instances[i].template)fail('flowsheet_invalid',`${path}.stages[${i}]`,'Stage order must follow the declared instances.');});
  if(canonical((v.connections as Obj[]).map(c=>c.id))!==canonical(sheet.connections.map(c=>c.id)))fail('flowsheet_invalid',path+'.connections','Connections must follow the declared order.');
  if(canonical((v.ports as {port:{id:string}}[]).map(p=>p.port?.id))!==canonical(sheet.exposures.map(e=>e.id)))fail('flowsheet_invalid',path+'.ports','Exposed ports must follow the declared order.');
  return v;
}
