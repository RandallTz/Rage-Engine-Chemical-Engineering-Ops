/** Storage and transport only; Python owns equation operations and dimensions. */
export const equationSourceRevision='physical-equation-graphs-8';
export type EquationFamily='matter'|'momentum'|'energy'|'thermodynamics';
export type EquationOperation={kind:string;family:EquationFamily;sources?:string[];symbol?:string;relation?:string;name?:string;unit?:string;left?:string;right?:string;reason?:string;dependencies?:string[];relationKind?:'definition'|'constitutive'|'constraint';sourceSignatures?:Record<string,string>;domain?:string;domains?:string[];lower?:string;upper?:string;lowerOpen?:boolean;upperOpen?:boolean;endpointUnit?:string};
export type EquationWorkbench={format:'rage.equation-workbench';version:1;operations:EquationOperation[];cursor:number};
export type EquationRow={id:string;title:string;family:EquationFamily;ownerId:string;kind:string;dependent:boolean;current:boolean;latex:string;derivation:{rule:string;inputIds:string[];beforeLatex:string[];assumptions:string[];branches?:{latex:string;admitted:boolean}[]}};
export type EquationWorkbenchReport={format:'rage.equation-workbench-report';version:1;modelId:string;draft?:boolean;replay?:{completed:number;failedOperation:number;message:string};definition:EquationWorkbench;findings?:{ownerId:string;family:EquationFamily;message:string}[];equations:EquationRow[];quantities:{id:string;input:string;latex:string;unit:string|null;coordinate:boolean;name:string}[];execution:{supported:boolean;reason:string}};
const kinds=['combine','substitute','isolate','expand','factor','differentiate','integrate','volume_integrate','gauss','reynolds','zero','apply_zero','declare_symbol','declare_function','change_dependencies','declare_relation','multiply','divide','declare_domain'];
const families=['matter','momentum','energy','thermodynamics'];
function object(value:unknown,required:string[],optional:string[]=[]):Record<string,unknown>{if(!value||typeof value!=='object'||Array.isArray(value))throw new Error('Expected an equation operation object.');const o=value as Record<string,unknown>;if(required.some(k=>!Object.hasOwn(o,k))||Object.keys(o).some(k=>!required.includes(k)&&!optional.includes(k)))throw new Error('Unknown or missing equation operation fields.');return o;}
const string=(v:unknown):v is string=>typeof v==='string'&&!!v.trim();
export function readEquationWorkbench(value:unknown):EquationWorkbench{
  const o=object(value,['format','version','operations','cursor']);
  if(o.format!=='rage.equation-workbench'||o.version!==1||!Array.isArray(o.operations)||o.operations.length>400||!Number.isInteger(o.cursor)||(o.cursor as number)<0||(o.cursor as number)>o.operations.length)throw new Error('Invalid equation workbench history.');
  for(const value of o.operations){const op=object(value,['kind','family'],['sources','symbol','relation','name','unit','left','right','reason','dependencies','relationKind','sourceSignatures','domain','domains','lower','upper','lowerOpen','upperOpen','endpointUnit']);if(!kinds.includes(op.kind as string)||!families.includes(op.family as string))throw new Error('Unknown equation operation.');for(const k of ['symbol','relation','name','unit','left','right','reason','endpointUnit'])if(k in op&&(!string(op[k])||(op[k] as string).length>500))throw new Error('Invalid equation operation argument.');if(op.sources!==undefined&&(!Array.isArray(op.sources)||!op.sources.length||op.sources.length>160||op.sources.some(s=>!string(s))||new Set(op.sources).size!==op.sources.length))throw new Error('Invalid equation operation inputs.');if(op.dependencies!==undefined&&(!['declare_function','change_dependencies'].includes(op.kind as string)||!Array.isArray(op.dependencies)||op.dependencies.length>12||op.dependencies.some(d=>!string(d))||new Set(op.dependencies).size!==op.dependencies.length))throw new Error('Invalid quantity dependencies.');if(op.relationKind!==undefined&&(op.kind!=='declare_relation'||!['definition','constitutive','constraint'].includes(op.relationKind as string)))throw new Error('Invalid relation classification.');}
  const required:Record<string,string[]>={declare_domain:['sources','symbol','domain','reason'],combine:['sources'],substitute:['sources','relation','symbol'],isolate:['sources','symbol'],expand:['sources'],factor:['sources'],differentiate:['sources','symbol'],integrate:['sources','symbol','name'],volume_integrate:['sources'],gauss:['sources'],reynolds:['sources'],zero:['sources','symbol','reason'],apply_zero:['sources','symbol','reason'],declare_symbol:['name','unit'],declare_function:['name','unit','dependencies'],change_dependencies:['sources','symbol','dependencies','reason'],declare_relation:['left','right','reason'],multiply:['sources','right'],divide:['sources','right']};
  for(const op of o.operations as EquationOperation[]){if(required[op.kind].some(key=>!Object.hasOwn(op,key))||op.kind!=='combine'&&op.sources&&op.sources.length!==1)throw new Error('The equation operation is missing its required arguments.');}
  for(const op of o.operations as EquationOperation[]){
    if(op.domain!==undefined&&(op.kind!=='declare_domain'||!['real','positive','nonnegative','negative','nonpositive','nonzero','zero','interval'].includes(op.domain)))throw new Error('Invalid real domain.');
    const endpoints=['lower','upper','lowerOpen','upperOpen'];
    if(op.domain==='interval'){
      if(!string(op.lower)||op.lower.length>80||!string(op.upper)||op.upper.length>80||typeof op.lowerOpen!=='boolean'||typeof op.upperOpen!=='boolean')throw new Error('Interval endpoints and openness must be explicit.');
    }else if(endpoints.some(key=>Object.hasOwn(op,key)))throw new Error('Endpoint fields belong only to interval declarations.');
    if(op.endpointUnit!==undefined&&op.domain!=='interval')throw new Error('Endpoint units belong only to interval declarations.');
    if(op.domains!==undefined&&(!['isolate','substitute'].includes(op.kind)||!Array.isArray(op.domains)||!op.domains.length||op.domains.length>24||op.domains.some(id=>!string(id))||new Set(op.domains).size!==op.domains.length))throw new Error('Invalid recorded domain inputs.');
    if(op.sourceSignatures===undefined)continue;
    const expected=new Set([...(op.sources??[]),...(op.kind==='substitute'&&op.relation?[op.relation]:[]),...(op.domains??[])]);
    const signatures=op.sourceSignatures;
    if(!signatures||typeof signatures!=='object'||Array.isArray(signatures)||Object.keys(signatures).length!==expected.size||Object.keys(signatures).some(id=>!expected.has(id))||Object.values(signatures).some(value=>typeof value!=='string'||!/^[0-9a-f]{64}$/.test(value)))throw new Error('Invalid equation source signatures.');
  }
  return value as EquationWorkbench;
}
export function readEquationWorkbenchReport(value:unknown):EquationWorkbenchReport{
  const o=object(value,['format','version','modelId','definition','equations','quantities','execution'],['findings','draft','replay']);
  if(o.draft!==undefined&&typeof o.draft!=='boolean')throw new Error('Invalid fundamental-law preview.');
  if(o.findings!==undefined&&(!Array.isArray(o.findings)||o.findings.some(value=>{const f=object(value,['ownerId','family','message']);return !string(f.ownerId)||!families.includes(f.family as string)||!string(f.message);})))throw new Error('Invalid equation capability finding.');
  if(o.format!=='rage.equation-workbench-report'||o.version!==1||!string(o.modelId)||!Array.isArray(o.equations)||!Array.isArray(o.quantities))throw new Error('Invalid equation workbench report.');readEquationWorkbench(o.definition);
  const ids=new Set<string>();
  for(const value of o.equations){const row=object(value,['id','title','family','ownerId','kind','dependent','current','latex','derivation']);if(!['id','title','ownerId','kind','latex'].every(k=>string(row[k]))||!families.includes(row.family as string)||typeof row.dependent!=='boolean'||typeof row.current!=='boolean'||ids.has(row.id as string))throw new Error('Invalid equation node.');const d=object(row.derivation,['rule','inputIds','beforeLatex','assumptions'],['branches']);if(!string(d.rule)||['inputIds','beforeLatex','assumptions'].some(k=>!Array.isArray(d[k])||(d[k] as unknown[]).some(v=>!string(v)))||(d.inputIds as string[]).some(id=>!ids.has(id))||(d.inputIds as string[]).length!==(d.beforeLatex as string[]).length)throw new Error('Invalid equation provenance.');if(d.branches!==undefined&&(!Array.isArray(d.branches)||!d.branches.length||d.branches.some(value=>{const b=object(value,['latex','admitted']);return !string(b.latex)||typeof b.admitted!=='boolean';})||(d.branches as {admitted:boolean}[]).filter(b=>b.admitted).length!==1))throw new Error('Invalid branch evidence.');ids.add(row.id as string);}
  for(const value of o.quantities){const q=object(value,['id','input','latex','unit','coordinate','name']);if(!string(q.id)||!string(q.input)||!string(q.latex)||!string(q.name)||q.unit!==null&&!string(q.unit)||typeof q.coordinate!=='boolean')throw new Error('Invalid mathematical quantity.');}
  const execution=object(o.execution,['supported','reason']);if(typeof execution.supported!=='boolean'||!string(execution.reason))throw new Error('Invalid equation execution scope.');
  if(o.replay!==undefined){const replay=object(o.replay,['completed','failedOperation','message']);if(!Number.isInteger(replay.completed)||(replay.completed as number)<0||replay.failedOperation!==(replay.completed as number)+1||(replay.failedOperation as number)>(o.definition as EquationWorkbench).cursor||!string(replay.message)||execution.supported)throw new Error('Invalid equation recovery report.');}
  return value as EquationWorkbenchReport;
}

/** Presentation order only. Expressions and provenance come unchanged from Python. */
export function equationSections(report:EquationWorkbenchReport,family:EquationFamily,owner?:string){
  const rows=report.equations.filter(row=>row.family===family&&(!owner||row.ownerId===owner||row.ownerId==='unbound'));
  const roots=rows.filter(row=>row.derivation.rule==='declared_law'&&!row.derivation.inputIds.length);
  const rootIds=new Set(roots.map(row=>row.id));
  return {roots,steps:rows.filter(row=>!rootIds.has(row.id)),result:rows.filter(row=>row.current),shared:report.equations.filter(row=>row.family===family&&row.ownerId==='system')};
}
