/** Report published by the Python compiler. Matrices are method-dependent. */
import type { Igualdad } from '../../app/adimensionalizacion/contrato';
import {readEquationWorkbenchReport,type EquationWorkbenchReport} from '../../app/models/equationWorkbench';
import {readDerivedExecution,type DerivedExecution} from './derivedExecution';
import {readSteadyReport,type SteadyReport} from './steadyContract';
export type CompilationReport = TemporalCompilationReport | SteadyReport;
export type TemporalCompilationReport = {
  symbolLabels?: Record<string, string>;
  derivedExecution?:{version:1|2|3|4;dae?:{index:1;determinant:string;determinantBounds:string[];proof:string;method:'scipy_bdf_nested_newton';initialization:'fixed_differential_states';driftTolerance:number;stateBounds:Record<string,string[]>};thermodynamicClosures?:ThermodynamicClosureReport[];sourceSignature:string;selection:DerivedExecution;proofConditions:{equationId:string;sourceEquationId:string;kind:'interval_identity'|'eliminated_coordinate_premise';latex:string}[];runtimeConditions:{equationId:string;strict:boolean;latex:string}[];reconstructions:DerivedExecution['reconstructions'];nonlinearBlock?:{rows:NonNullable<DerivedExecution['algebraic']>;method:'damped_newton';settings:NonNullable<DerivedExecution['nonlinear']>;initialization:Record<string,unknown>;scope:string};algebraicBlock?:{rows:NonNullable<DerivedExecution['algebraic']>;matrixSI:number[][];determinantSI:string;equilibratedConditionInfinity:number;conditionTest:string;solve:string}};
  equationWorkbench?:EquationWorkbenchReport;
  format: 'rage.compilation'; version: 1; formulation: 'physical' | 'scaled';
  sourceModelId: string; sourceRevision: number | null; signature: string;
  method: string; closureStrategy: 'nested_equilibrium' | 'declared_assumption' | 'package_closure';
  variables: { id: string; sourceId: string; role: 'differential'; unit: string; physicalUnit: string; scaleSI: number; absoluteTolerance: number }[];
  equations: Igualdad[]; domains: unknown[]; conditions: unknown[]; direct: { simboloId: string; expresion: import('../../app/adimensionalizacion/contrato').Expresion }[]; inverse: TemporalCompilationReport['direct'];
  eliminatedVariables: string[]; auxiliaryStates: number; auxiliaryPurpose?: string;
  time: { id: string; sourceId: string; scaleSI: number; finalTime: number; physicalFinalTime: number };
  equivalence?: string; matrix: string; limits?: string;
  strategy?: { methods: { id: string; available: boolean; reason: string }[]; steps: { id: string; title: string; description: string; latex: string }[]; scope: string };
  systemEquations?: { id: string; family: string; latex: string }[];
  parameters?: { id: string; value: number; unit: string }[];
  groups?: { id: string; definition: import('../../app/adimensionalizacion/contrato').Expresion; value: number | null }[];
  selection?: { formId: string; execution: import('./contrato').TransformExecution };
  relations?: { id: string; familia: string; descripcion: string; propietarioId: string }[];
  thermodynamicDerivation?: TemporalCompilationReport['materialDerivation'];
  energyDerivation?: TemporalCompilationReport['materialDerivation'];
  momentumDerivation?: TemporalCompilationReport['materialDerivation'];
  materialDerivation?: { volumeId: string; origin: 'recorded' | 'reviewed_rebuild'; operationIds: string[]; signature: string; relationIds: string[] }[];
};

/** Package closure evaluated by derived execution (core/compilador/derived_closure.py describe()). */
export type ThermodynamicClosureReport = {volumeId:string;package:string;species:string[];mode:'single_phase'|'equilibrium';specification:'PH'|'UV'|'TP'|null;
  anchor:'gas'|'liquid'|null;liquidOnly:boolean;candidatePhases:string[];fingerprint:string;evaluations:number;inlets:Record<string,Record<string,unknown>>;source:'core.termodinamica.derived_bridge'};
const CLOSURE_KEYS=['volumeId','package','species','mode','specification','anchor','liquidOnly','candidatePhases','fingerprint','evaluations','inlets','source'];
export function readThermodynamicClosures(value: unknown): ThermodynamicClosureReport[] {
  const isText=(v:unknown)=>typeof v==='string'&&v.length>0;
  if(!Array.isArray(value)||!value.length||value.some(row=>!row||typeof row!=='object'||Array.isArray(row)
    ||Object.keys(row).length!==CLOSURE_KEYS.length||Object.keys(row).some(key=>!CLOSURE_KEYS.includes(key))
    ||!isText(row.volumeId)||!isText(row.package)||!Array.isArray(row.species)||!row.species.length||!row.species.every(isText)
    ||!['single_phase','equilibrium'].includes(row.mode)||![null,'PH','UV','TP'].includes(row.specification)||![null,'gas','liquid'].includes(row.anchor)
    ||typeof row.liquidOnly!=='boolean'||!Array.isArray(row.candidatePhases)||!row.candidatePhases.length||!row.candidatePhases.every((p:unknown)=>p==='V'||p==='L')
    ||!isText(row.fingerprint)||!Number.isSafeInteger(row.evaluations)||row.evaluations<0
    ||!row.inlets||typeof row.inlets!=='object'||Array.isArray(row.inlets)||Object.values(row.inlets).some(v=>!v||typeof v!=='object'||Array.isArray(v))
    ||row.source!=='core.termodinamica.derived_bridge'))throw new Error('Invalid thermodynamic closure report.');
  if(new Set(value.map(row=>row.volumeId)).size!==value.length)throw new Error('Duplicate thermodynamic closure volume.');
  return value as ThermodynamicClosureReport[];
}

export function readCompilationReport(value: unknown): CompilationReport {
  if (!value || typeof value !== 'object') throw new Error('The compiler returned an invalid report.');
  if('version' in value&&value.version===2)return readSteadyReport(value);
  const report = value as TemporalCompilationReport;
  const required = ['format', 'version', 'formulation', 'sourceModelId', 'sourceRevision', 'signature', 'method', 'closureStrategy',
    'variables', 'equations', 'domains', 'conditions', 'direct', 'inverse', 'eliminatedVariables', 'auxiliaryStates', 'time', 'matrix'];
  const optional = ['auxiliaryPurpose', 'equivalence', 'limits', 'relations', 'parameters', 'groups', 'selection', 'materialDerivation', 'energyDerivation', 'thermodynamicDerivation', 'momentumDerivation', 'strategy', 'systemEquations','equationWorkbench','derivedExecution'];
  if(report.derivedExecution!==undefined){
    const derived=report.derivedExecution;
    if(!derived||![1,2,3,4].includes(derived.version)||!/^[a-f0-9]{64}$/.test(derived.sourceSignature)||!Array.isArray(derived.proofConditions)||!Array.isArray(derived.runtimeConditions)||!Array.isArray(derived.reconstructions)
      ||Object.keys(derived).some(key=>!['version','sourceSignature','selection','proofConditions','runtimeConditions','reconstructions','algebraicBlock','nonlinearBlock','dae','thermodynamicClosures'].includes(key))
      ||derived.proofConditions.some(row=>!row||typeof row.equationId!=='string'||typeof row.sourceEquationId!=='string'||!['interval_identity','eliminated_coordinate_premise'].includes(row.kind)||typeof row.latex!=='string')
      ||derived.runtimeConditions.some(row=>!row||typeof row.equationId!=='string'||typeof row.strict!=='boolean'||typeof row.latex!=='string'))throw new Error('Invalid derived execution report.');
    readDerivedExecution(derived.selection);
    if(derived.thermodynamicClosures!==undefined)readThermodynamicClosures(derived.thermodynamicClosures);
    if(derived.version!==derived.selection.version||derived.version===1&&derived.algebraicBlock!==undefined||derived.version===2&&!derived.algebraicBlock)throw new Error('Algebraic block version mismatch.');
    if(derived.version===3||derived.version===4){
      const block=derived.nonlinearBlock;
      if(!block||derived.algebraicBlock||block.method!=='damped_newton'||typeof block.scope!=='string'||!block.initialization||typeof block.initialization!=='object'||Object.keys(block).some(k=>!['rows','method','settings','initialization','scope'].includes(k))||JSON.stringify(block.rows)!==JSON.stringify(derived.selection.algebraic)||JSON.stringify(block.settings)!==JSON.stringify(derived.selection.nonlinear))throw new Error('Invalid nonlinear compilation evidence.');
      const evidence=block!.initialization;
      for(const key of ['iterations','evaluations','backtracks'])if(!Number.isSafeInteger(evidence[key])||Number(evidence[key])<0)throw new Error('Invalid nonlinear initialization counters.');
      for(const key of ['residualNorm','stepNorm','conditionInfinity'])if(evidence[key]!==null&&(typeof evidence[key]!=='number'||!Number.isFinite(evidence[key])||Number(evidence[key])<0))throw new Error('Invalid nonlinear initialization metrics.');
      if(evidence.stage!=='initialization'||evidence.terminationReason!=='converged'||evidence.sourceSignature!==derived.sourceSignature||evidence.modelId!==report.sourceModelId||evidence.formulationSignature!==report.signature||evidence.path!=='motores.derivedExecution.nonlinear'||JSON.stringify(evidence.equationIds)!==JSON.stringify(derived.selection.algebraic!.map(r=>r.equationId))||JSON.stringify(evidence.quantityIds)!==JSON.stringify(derived.selection.algebraic!.map(r=>r.quantityId)))throw new Error('Stale nonlinear initialization evidence.');
    }else if(derived.nonlinearBlock!==undefined)throw new Error('Nonlinear block version mismatch.');
    if((derived.version===4)!==Boolean(derived.dae))throw new Error('DAE evidence version mismatch.');
    if(derived.dae){
      const d=derived.dae;
      if(Object.keys(d).length!==8||Object.keys(d).some(k=>!['index','determinant','determinantBounds','proof','method','initialization','driftTolerance','stateBounds'].includes(k))||d.index!==1||typeof d.determinant!=='string'||!d.determinant||typeof d.proof!=='string'||d.method!=='scipy_bdf_nested_newton'||d.initialization!=='fixed_differential_states'||report.method!=='BDF'||d.driftTolerance!==derived.selection.dae!.driftTolerance||!Array.isArray(d.determinantBounds)||d.determinantBounds.length!==2||d.determinantBounds.some(v=>typeof v!=='string'||!v)||!d.stateBounds||Object.keys(d.stateBounds).sort().join('|')!==derived.selection.states.map(r=>r.quantityId).sort().join('|')||Object.values(d.stateBounds).some(v=>!Array.isArray(v)||v.length!==2||v.some(x=>typeof x!=='string'||!x)))throw new Error('Invalid index-one compilation evidence.');
    }
    if(derived.algebraicBlock){
      const block=derived.algebraicBlock,n=derived.selection.algebraic!.length;
      if(JSON.stringify(block.rows)!==JSON.stringify(derived.selection.algebraic)||typeof block.determinantSI!=='string'||!block.determinantSI||!Number.isFinite(block.equilibratedConditionInfinity)||block.equilibratedConditionInfinity<1
        ||typeof block.conditionTest!=='string'||typeof block.solve!=='string'||!Array.isArray(block.matrixSI)||block.matrixSI.length!==n||block.matrixSI.some(row=>!Array.isArray(row)||row.length!==n||row.some(value=>!Number.isFinite(value)))
        ||Object.keys(block).some(key=>!['rows','matrixSI','determinantSI','equilibratedConditionInfinity','conditionTest','solve'].includes(key)))throw new Error('Invalid affine block evidence.');
    }
    if(derived.sourceSignature!==derived.selection.sourceSignature||JSON.stringify(derived.reconstructions)!==JSON.stringify(derived.selection.reconstructions))throw new Error('Derived execution provenance disagrees with its selection.');
  }
  optional.push('symbolLabels');
  if (report.symbolLabels !== undefined && (!report.symbolLabels || typeof report.symbolLabels !== 'object' || Array.isArray(report.symbolLabels) || Object.values(report.symbolLabels).some(label => typeof label !== 'string' || !label))) throw new Error('Invalid compiler symbol labels.');
  if(report.equationWorkbench!==undefined)readEquationWorkbenchReport(report.equationWorkbench);
  if (required.some(key => !Object.hasOwn(report, key)) || Object.keys(report).some(key => !required.includes(key) && !optional.includes(key))) throw new Error('Unknown or missing compilation report fields.');
  if (report.format !== 'rage.compilation' || report.version !== 1 || !['physical', 'scaled'].includes(report.formulation)
    || !['nested_equilibrium', 'declared_assumption', 'package_closure'].includes(report.closureStrategy)
    || (report.closureStrategy === 'package_closure') !== Boolean(report.derivedExecution?.thermodynamicClosures)
    || typeof report.signature !== 'string' || !report.signature || typeof report.sourceModelId !== 'string'
    || typeof report.method !== 'string' || !Array.isArray(report.variables) || !report.variables.length&&!(report.auxiliaryStates>0)
    || !Array.isArray(report.equations) || !Array.isArray(report.eliminatedVariables) || !Array.isArray(report.direct)
    || !Array.isArray(report.inverse) || !Array.isArray(report.domains) || !Array.isArray(report.conditions)
    || !Number.isSafeInteger(report.auxiliaryStates) || report.auxiliaryStates < 0
    || typeof report.matrix !== 'string' || !report.time || !Number.isFinite(report.time.physicalFinalTime)
    || !(report.time.scaleSI > 0) || !Number.isFinite(report.time.scaleSI)
    || !(report.time.finalTime > 0) || !Number.isFinite(report.time.finalTime)) throw new Error('The compiler report does not match version 1.');
  const ids = new Set<string>();
  if (report.systemEquations !== undefined && (!Array.isArray(report.systemEquations) || report.systemEquations.some(row => !row || typeof row.id !== 'string' || typeof row.family !== 'string' || typeof row.latex !== 'string'))) throw new Error('Invalid compiled balance display.');
  if (report.strategy !== undefined) {
    const strategy = report.strategy;
    if (!strategy || !Array.isArray(strategy.methods) || !strategy.methods.length || !Array.isArray(strategy.steps) || !strategy.steps.length || typeof strategy.scope !== 'string'
      || strategy.methods.some(method => !method || typeof method.id !== 'string' || typeof method.available !== 'boolean' || typeof method.reason !== 'string')
      || strategy.steps.some(step => !step || typeof step.id !== 'string' || typeof step.title !== 'string' || typeof step.description !== 'string' || typeof step.latex !== 'string')
      || !strategy.methods.some(method => method.id === report.method && method.available)) throw new Error('Invalid mathematical solution strategy.');
  }
  for (const variable of report.variables) {
    if (!variable || typeof variable.id !== 'string' || ids.has(variable.id) || typeof variable.sourceId !== 'string'
      || variable.role !== 'differential' || typeof variable.unit !== 'string' || typeof variable.physicalUnit !== 'string'
      || !(variable.scaleSI > 0) || !Number.isFinite(variable.scaleSI)
      || !(variable.absoluteTolerance > 0) || !Number.isFinite(variable.absoluteTolerance)) throw new Error('Invalid retained variable in the compiler report.');
    ids.add(variable.id);
  }
  for (const equation of report.equations) {
    if (!equation || typeof equation.id !== 'string' || !equation.izquierda || !equation.derecha) throw new Error('Invalid compiled equation.');
  }
  for (const parameter of report.parameters ?? []) if (!parameter || typeof parameter.id !== 'string' || !Number.isFinite(parameter.value) || typeof parameter.unit !== 'string') throw new Error('Invalid compiled parameter.');
  for (const map of [...report.direct, ...report.inverse]) if (!map || typeof map.simboloId !== 'string' || !map.expresion || typeof map.expresion !== 'object') throw new Error('Invalid compiled variable map.');
  for (const group of report.groups ?? []) if (!group || typeof group.id !== 'string' || !group.definition || group.value !== null && !Number.isFinite(group.value)) throw new Error('Invalid dimensionless group.');
  for (const provenance of [report.materialDerivation,report.energyDerivation,report.thermodynamicDerivation,report.momentumDerivation]) if (provenance !== undefined) {
    if (!Array.isArray(provenance)) throw new Error('Invalid derivation provenance.');
    for (const entry of provenance) if (!entry || typeof entry.volumeId !== 'string' || !['recorded', 'reviewed_rebuild'].includes(entry.origin) || typeof entry.signature !== 'string' || !/^[a-f0-9]{64}$/.test(entry.signature) || !Array.isArray(entry.operationIds) || entry.operationIds.some(id => typeof id !== 'string') || !Array.isArray(entry.relationIds) || entry.relationIds.some(id => typeof id !== 'string')) throw new Error('Invalid derivation provenance.');
  }
  if (report.formulation === 'scaled' && (!report.selection || typeof report.selection.formId !== 'string'
    || report.selection.execution?.version !== 1 || !Array.isArray(report.selection.execution.objectives)
    || !report.selection.execution.freeScales)) throw new Error('The scaled compilation has no execution selection.');
  return report;
}
