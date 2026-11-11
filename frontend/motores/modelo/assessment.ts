/** Read server evidence, never calculate physical verdicts in the interface. */
import {readCompilationReport, type CompilationReport} from './compilation';
import type {ConjuntoResultados} from '../resultados/contrato';

const codes = {
  structure: {complete:['STRUCTURE_COMPLETE'], incomplete:['STRUCTURE_MISSING_RELATION'], incompatible:['STRUCTURE_CONFLICT'], unsupported:['STRUCTURE_UNSUPPORTED'], not_evaluated:['STRUCTURE_NOT_EVALUATED'], invalid:['STRUCTURE_INVALID_DOCUMENT']},
  initialization: {compatible:['INITIALIZATION_COMPATIBLE'], pending:['INITIALIZATION_MISSING_DATA'], incompatible:['INITIALIZATION_OUT_OF_DOMAIN','INITIALIZATION_CONSTRAINT_CONFLICT'], unsupported:['INITIALIZATION_UNSUPPORTED'], not_evaluated:['INITIALIZATION_NOT_EVALUATED']},
  certification: {passed:['CERTIFICATION_PASSED'], failed:['CERTIFICATION_FAILED'], not_evaluable:['CERTIFICATION_NOT_EVALUABLE'], not_evaluated:['CERTIFICATION_NOT_EVALUATED']},
} as const;
export type Diagnostic = {code:string; message:string; path:string; [key:string]:unknown};
type Kind = keyof typeof codes;
type Verdict<K extends Kind> = {[S in keyof typeof codes[K]]:{kind:K;status:S;
  code:typeof codes[K][S] extends readonly string[]?typeof codes[K][S][number]:never;
  sourceSignature:string;scope:Record<string,unknown>;diagnostics:Diagnostic[]}}[keyof typeof codes[K]];
export type ModelAssessment = {
  format:'rage.model-assessment'; version:1; modelId:string|null; sourceSignature:string;
  structure:Verdict<'structure'>; initialization:Verdict<'initialization'>; certification:Verdict<'certification'>;
  inspection:{variables:Record<string,unknown>[]; equations:Record<string,unknown>[]; scope:string};
  compilation?:CompilationReport; resultSignature?:string; resultSignatureVersion?:1|2;
};
const object=(v:unknown):v is Record<string,unknown>=>!!v&&typeof v==='object'&&!Array.isArray(v);
const digest=(v:unknown)=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
const text=(v:unknown)=>typeof v==='string'&&!!v;
const reject=(message:string):never=>{throw new Error('Invalid model assessment: '+message);};
function finiteJSON(value:unknown):boolean {
  if(typeof value==='number')return Number.isFinite(value);
  if(Array.isArray(value))return value.every(finiteJSON);
  if(object(value))return Object.values(value).every(finiteJSON);
  return value===null||['string','boolean'].includes(typeof value);
}

export const isDiagnosticCheck=(id:string)=>id.startsWith('reactions.equilibrium_limit.');
const citesDiagnostic=(d:Diagnostic,result:ConjuntoResultados)=>{
  const m=/^verificaciones\[(\d+)\]$/.exec(d.path),check=m?result.verificaciones[Number(m[1])]:undefined;
  return !!check&&isDiagnosticCheck(check.id);
};
/** Re-express a pre-RV-5 verdict under the published rule: drop the rows caused by diagnostics, keep the rest as stored. */
function upgradeLegacyCertification(a:ModelAssessment,result:ConjuntoResultados):ModelAssessment{
  const rows=a.certification.diagnostics.filter(d=>!citesDiagnostic(d,result));
  const failed=rows.some(d=>d.code==='CERTIFICATION_FAILED');
  const certification=failed?{...a.certification,status:'failed' as const,code:'CERTIFICATION_FAILED' as const,diagnostics:rows}
    :{...a.certification,status:'not_evaluable' as const,code:'CERTIFICATION_NOT_EVALUABLE' as const,diagnostics:rows};
  return {...a,certification} as ModelAssessment;
}

export function readAssessment(value:unknown, result?:ConjuntoResultados):ModelAssessment {
  const required=['format','version','modelId','sourceSignature','structure','initialization','certification','inspection'];
  if(!object(value)||required.some(k=>!Object.hasOwn(value,k))||Object.keys(value).some(k=>![...required,'compilation','resultSignature','resultSignatureVersion'].includes(k))||value.format!=='rage.model-assessment'||value.version!==1||!digest(value.sourceSignature)||!finiteJSON(value))return reject('expected version 1 with a finite source identity.');
  for(const kind of Object.keys(codes) as Kind[]){
    const v=value[kind], pairs:Record<string,readonly string[]>=codes[kind];
    if(!object(v)||Object.keys(v).length!==6||v.kind!==kind||typeof v.status!=='string'||!Object.hasOwn(pairs,v.status)||typeof v.code!=='string'||!pairs[v.status].includes(v.code)||v.sourceSignature!==value.sourceSignature||!object(v.scope)||!Array.isArray(v.diagnostics))return reject(kind+' status/code or source mismatch.');
    for(const d of v.diagnostics)if(!object(d)||!text(d.code)||!text(d.message)||!text(d.path))return reject('located typed diagnostics required.');
  }
  if(value.resultSignatureVersion!==undefined&&(![1,2].includes(value.resultSignatureVersion as number)||value.resultSignature===undefined))return reject('unknown result signature version or missing result digest.');
  const a=value as unknown as ModelAssessment;
  if(!text(a.modelId)&&!(a.modelId===null&&a.structure.status==='invalid'))return reject('model identity required.');
  const inspection=a.inspection;
  if(!object(inspection)||Object.keys(inspection).length!==3||!Array.isArray(inspection.variables)||!inspection.variables.every(object)||!Array.isArray(inspection.equations)||!inspection.equations.every(object)||typeof inspection.scope!=='string')return reject('invalid structural inspection.');
  if(a.initialization.status==='compatible'&&a.structure.status!=='complete')return reject('initialization cannot pass an unadmitted structure.');
  if(a.compilation!==undefined){readCompilationReport(a.compilation);if(a.compilation.version===2?(a.structure.status!=='complete'||a.initialization.status!=='not_evaluated'):a.initialization.status!=='compatible')return reject('compiled report has incompatible assessment scope.');}
  if(a.resultSignature!==undefined&&!digest(a.resultSignature))return reject('result digest required.');
  if(a.resultSignature===undefined&&a.certification.status!=='not_evaluated')return reject('certification requires published evidence.');
  if(result){
    if(a.modelId!==result.modeloId||!a.resultSignature)return reject('published model identity differs.');
    const physical=result.procedencia.physicalCertification;
    // Roadmap RV-5: equilibrium-limit values are diagnostics and never decide the verdict.
    const expected=physical?({cumple:'passed',no_cumple:'failed',no_evaluable:'not_evaluable'} as const)[physical.estado]:result.verificaciones.some(v=>v.valor>v.tolerancia&&!isDiagnosticCheck(v.id))?'failed':'not_evaluable';
    if(a.certification.status!==expected){
      // Results saved before 8 November 2026 failed on diagnostics; read them, and show the published rule.
      const legacy=!physical&&a.certification.status==='failed'&&result.verificaciones.some(v=>v.valor>v.tolerancia);
      if(!legacy)return reject('verdict disagrees with the published certificate/checks.');
      return upgradeLegacyCertification(a,result);
    }
    if(a.certification.diagnostics.some(d=>citesDiagnostic(d,result)))return upgradeLegacyCertification(a,result);
    const times=result.ejes.find(e=>e.rol==='tiempo')?.valores??[],scope=a.certification.scope;
    if(scope.numericalStatus!==result.estado||scope.complete!==(result.estado==='resuelto')||scope.samples!==times.length||scope.startSI!==(times[0]??null)||scope.endSI!==(times.at(-1)??null))return reject('certificate scope differs from the published prefix.');
  }
  return a;
}

/** Keep the original HTTP details as well as normalized located diagnostics. */
export class ModelDiagnosticError extends Error {
  readonly assessment?:ModelAssessment;
  readonly diagnostics:Diagnostic[];
  readonly code?:string;
  readonly path?:string;
  constructor(message:string,readonly httpStatus:number,readonly detail:unknown){
    super(message);this.name='ModelDiagnosticError';
    const d=object(detail)?detail:{};
    this.code=typeof d.codigo==='string'?d.codigo:typeof d.code==='string'?d.code:undefined;
    this.path=typeof d.ruta==='string'?d.ruta:typeof d.path==='string'?d.path:undefined;
    if(d.assessment!==undefined)this.assessment=readAssessment(d.assessment);
    this.diagnostics=Array.isArray(d.diagnostics)?d.diagnostics.filter(object).map(row=>({...row,
      code:typeof row.code==='string'?row.code:typeof row.codigo==='string'?row.codigo:'UNCLASSIFIED_DIAGNOSTIC',
      message:typeof row.message==='string'?row.message:typeof row.mensaje==='string'?row.mensaje:message,
      path:typeof row.path==='string'?row.path:this.path??'modelo'})):[];
  }
}
export function responseError(value:unknown,status:number,fallback:string):ModelDiagnosticError{
  const detail=object(value)?value.detail:undefined;
  const message=object(detail)?detail.mensaje??detail.message:detail;
  return new ModelDiagnosticError(typeof message==='string'?message:fallback,status,detail??{});
}
export function rejectedAssessment(a:ModelAssessment):ModelDiagnosticError{
  const diagnostics=[...a.structure.diagnostics,...a.initialization.diagnostics];
  return new ModelDiagnosticError(diagnostics[0]?.message??'Compilation is not available for this assessment.',422,
    {assessment:a,code:a.initialization.status==='not_evaluated'?a.structure.code:a.initialization.code,diagnostics});
}

/** Plain lines shared by the existing views and the headless rendering test. */
export function assessmentLines(a?:ModelAssessment):string[]{
  if(!a)return ['Structure · Not evaluated · previous record','Initialization · Not evaluated · previous record','Certification · Not evaluated · previous record'];
  return (['structure','initialization','certification'] as const).flatMap(kind=>{
    const v=a[kind];return [kind[0].toUpperCase()+kind.slice(1)+' · '+v.status+' · '+v.code,
      ...v.diagnostics.map(d=>`${d.code} · ${d.path}: ${d.message}`)];
  });
}
