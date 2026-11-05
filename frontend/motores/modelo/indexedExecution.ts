/** Transport and structural validation only; connected equations are lowered in Python. */
import {readCompilationReport,type CompilationReport} from './compilation';
import {steadySignature} from './steadyContract';
import type {ModeloComun} from './contrato';
import {leerResultados} from '../resultados/lector';
import type {ConjuntoResultados} from '../resultados/contrato';
import {responseError} from './assessment';

export type IndexedSelection={format:'rage.indexed-execution';version:1;sourceSignature:string;mode:'dynamic'|'steady'};
type Endpoint={stage:number;portId:string};
export type IndexedCompilation={format:'rage.indexed-compilation';version:1;sourceModelId:string;indexSetId:string;count:number;
  selection:IndexedSelection;signature:string;method:'RK45'|'BDF'|'damped_newton';specialization:'original_rates'|'zero_accumulation';
  stages:{index:number;modelId:string;template:string;ports:{id:string;kind:string;direction:string}[];dynamicReport:CompilationReport;steadyReport:CompilationReport|null}[];
  rateRows:{stage:number;quantityId:string;equationId:string;expressionSI:string}[];
  connections:{id:string;kind:'material';from:Endpoint;to:Endpoint}[];
  ports:(Endpoint&{id:string;kind:'material'|'heat'|'work';direction:'inlet'|'outlet'})[];
  linearPolicy:{version:2;requested:'auto'|'dense'|'sparse';selected:'dense'|'sparse';size:number;structuralNonzeros:number;rule:string};
};
function fail(message:string):never{throw new Error(`Invalid indexed execution: ${message}`);}
function exact(value:unknown,fields:string):asserts value is Record<string,unknown>{
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).sort().join('|')!==fields.split(' ').sort().join('|'))fail('Unexpected or missing fields.');
}
function text(value:unknown):boolean{return typeof value==='string'&&value.length>0;}
export function readIndexedSelection(value:unknown):IndexedSelection{
  exact(value,'format version sourceSignature mode');
  if(value.format!=='rage.indexed-execution'||value.version!==1||!['dynamic','steady'].includes(String(value.mode))||typeof value.sourceSignature!=='string'||!/^[a-f0-9]{64}$/.test(value.sourceSignature))fail('Expected version 1 selection.');
  return value as IndexedSelection;
}
export function readIndexedCompilation(value:unknown):IndexedCompilation{
  exact(value,'format version sourceModelId indexSetId count selection stages connections ports rateRows method specialization linearPolicy signature');
  const r=value as IndexedCompilation,s=readIndexedSelection(r.selection),mode=s.mode;
  if(r.format!=='rage.indexed-compilation'||r.version!==1||!Number.isSafeInteger(r.count)||r.count<1||r.count>256||!text(r.sourceModelId)||!text(r.indexSetId))fail('Invalid header.');
  for(const key of ['stages','connections','ports','rateRows'] as const)if(!Array.isArray(r[key]))fail('Expected arrays.');
  if(r.stages.length!==r.count||r.specialization!==(mode==='dynamic'?'original_rates':'zero_accumulation')||!(mode==='dynamic'?['RK45','BDF']:['damped_newton']).includes(r.method))fail('Mode/count mismatch.');
  const expected:unknown[]=[],models=new Set<string>(),declared=new Map<string,{kind:string;direction:string}>();
  r.stages.forEach((stage,i)=>{
    exact(stage,'index modelId template ports dynamicReport steadyReport');
    if(stage.index!==i+1||!text(stage.template)||!text(stage.modelId)||models.has(stage.modelId))fail('Invalid stage order/identity.');
    models.add(stage.modelId);
    if(!Array.isArray(stage.ports))fail('Missing declared ports.');
    stage.ports.forEach(port=>{exact(port,'id kind direction');const key=JSON.stringify([i+1,port.id]);
      if(!text(port.id)||declared.has(key)||!['material','heat','work'].includes(port.kind)||!['inlet','outlet'].includes(port.direction))fail('Invalid declared port.');declared.set(key,port);});
    const d=readCompilationReport(stage.dynamicReport);
    if(d.version!==1||d.sourceModelId!==stage.modelId||!d.derivedExecution?.selection.states.length)fail('Missing stage-local derivative selection.');
    const original=d.derivedExecution!.selection.states;
    original.forEach(row=>expected.push([i+1,row.quantityId,row.equationId]));
    if(mode==='steady'){
      const steady=readCompilationReport(stage.steadyReport);
      if(steady.version!==2||steady.sourceModelId!==stage.modelId||steadySignature(steady.selection.states)!==steadySignature(original))fail('Steady changed the original rows.');
    }else if(stage.steadyReport!==null)fail('Unexpected steady specialization.');
  });
  const actual=r.rateRows.map(row=>{
    exact(row,'stage quantityId equationId expressionSI');if(!text(row.expressionSI))fail('Missing connected expression.');
    return [row.stage,row.quantityId,row.equationId];
  });
  if(JSON.stringify(actual)!==JSON.stringify(expected))fail('Connected rates changed ordered original rows.');
  const used=new Set<string>(),ids=new Set<string>();
  function endpoint(row:Endpoint,kind:string,direction:string){
    exact(row,'stage portId');if(!Number.isSafeInteger(row.stage)||row.stage<1||row.stage>r.count||!text(row.portId))fail('Invalid endpoint.');
    const key=JSON.stringify([row.stage,row.portId]),port=declared.get(key);
    if(!port||port.kind!==kind||port.direction!==direction)fail('Unknown or incompatible port.');
    if(used.has(key))fail('Port bound twice.');used.add(key);
  }
  function identity(id:string){if(!text(id)||ids.has(id))fail('Repeated boundary identity.');ids.add(id);}
  r.connections.forEach(row=>{exact(row,'id kind from to');identity(row.id);if(row.kind!=='material')fail('Unsupported coupling kind.');endpoint(row.from,row.kind,'outlet');endpoint(row.to,row.kind,'inlet');if(row.from.stage===row.to.stage)fail('Self connection.');});
  r.ports.forEach(row=>{exact(row,'id stage portId kind direction');identity(row.id);if(!['material','heat','work'].includes(row.kind)||!['inlet','outlet'].includes(row.direction))fail('Invalid port.');endpoint({stage:row.stage,portId:row.portId},row.kind,row.direction);});
  if(used.size!==declared.size)fail('Unbound stage port.');
  const p=r.linearPolicy;exact(p,'version requested selected size structuralNonzeros rule');
  if(p.version!==2||!['auto','dense','sparse'].includes(p.requested)||p.selected!==(p.requested==='auto'?'dense':p.requested)||!Number.isSafeInteger(p.size)||p.size<1||!Number.isSafeInteger(p.structuralNonzeros)||p.structuralNonzeros<0||p.structuralNonzeros>p.size*p.size||!text(p.rule))fail('Invalid solver policy.');
  const {signature,...unsigned}=r;if(signature!==steadySignature(unsigned))fail('Compilation fingerprint mismatch.');
  return r;
}

export function readIndexedResult(value:unknown,selection?:IndexedSelection):ConjuntoResultados{
  const result=leerResultados(value),proc=result.procedencia as typeof result.procedencia&{indexedCompilation?:unknown;indexedResultSignature?:string};
  const report=readIndexedCompilation(proc.indexedCompilation),metadata=result.indexedNetwork;
  if(result.modeloId!==report.sourceModelId||metadata?.count!==report.count||metadata?.indexSetId!==report.indexSetId||metadata?.mode!==report.selection.mode||proc.metodo!==report.method||selection&&steadySignature(report.selection)!==steadySignature(readIndexedSelection(selection)))fail('Result and compilation disagree.');
  const unsigned=structuredClone(result);delete (unsigned.procedencia as Record<string,unknown>).indexedResultSignature;
  if(proc.indexedResultSignature!==steadySignature(unsigned))fail('Result fingerprint mismatch.');
  return result;
}

async function request(endpoint:string,body:unknown,signal?:AbortSignal):Promise<unknown>{
  const timeout=AbortSignal.timeout(3600000);
  const response=await fetch(`${process.env.NEXT_PUBLIC_API_URL??'http://localhost:8004'}/modelo/${endpoint}`,{
    method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),cache:'no-store',signal:signal?AbortSignal.any([signal,timeout]):timeout});
  const value=await response.json();if(!response.ok)throw responseError(value,response.status,'The indexed network was rejected.');return value;
}
export async function prepareIndexedExecution(model:ModeloComun,mode:IndexedSelection['mode'],signal?:AbortSignal){
  const report=readIndexedCompilation(await request('indexed-execution',{format:'rage.indexed-execution.request',version:1,model,mode},signal));
  if(report.sourceModelId!==model.id||report.selection.sourceSignature!==steadySignature(model)||report.selection.mode!==mode)fail('Unexpected prepared source.');
  return report;
}
export async function solveIndexedExecution(model:ModeloComun,selection:IndexedSelection,signal?:AbortSignal){
  readIndexedSelection(selection);if(selection.sourceSignature!==steadySignature(model))fail('Source or Solve data changed.');
  return readIndexedResult(await request('resolver',{modelo:model,indexedExecution:selection},signal),selection);
}
