/** Report published by the Python compiler. Matrices are method-dependent. */
import type { Igualdad } from '../../app/adimensionalizacion/contrato';
import {readEquationWorkbenchReport,type EquationWorkbenchReport} from '../../app/models/equationWorkbench';
import {readDerivedExecution,type DerivedExecution} from './derivedExecution';
export type CompilationReport = {
  symbolLabels?: Record<string, string>;
  derivedExecution?:{version:1;sourceSignature:string;selection:DerivedExecution;proofConditions:{equationId:string;sourceEquationId:string;kind:'interval_identity'|'eliminated_coordinate_premise';latex:string}[];runtimeConditions:{equationId:string;strict:boolean;latex:string}[];reconstructions:DerivedExecution['reconstructions']};
  equationWorkbench?:EquationWorkbenchReport;
  format: 'rage.compilation'; version: 1; formulation: 'physical' | 'scaled';
  sourceModelId: string; sourceRevision: number | null; signature: string;
  method: string; closureStrategy: 'nested_equilibrium' | 'declared_assumption';
  variables: { id: string; sourceId: string; role: 'differential'; unit: string; physicalUnit: string; scaleSI: number; absoluteTolerance: number }[];
  equations: Igualdad[]; domains: unknown[]; conditions: unknown[]; direct: { simboloId: string; expresion: import('../../app/adimensionalizacion/contrato').Expresion }[]; inverse: CompilationReport['direct'];
  eliminatedVariables: string[]; auxiliaryStates: number; auxiliaryPurpose?: string;
  time: { id: string; sourceId: string; scaleSI: number; finalTime: number; physicalFinalTime: number };
  equivalence?: string; matrix: string; limits?: string;
  strategy?: { methods: { id: string; available: boolean; reason: string }[]; steps: { id: string; title: string; description: string; latex: string }[]; scope: string };
  systemEquations?: { id: string; family: string; latex: string }[];
  parameters?: { id: string; value: number; unit: string }[];
  groups?: { id: string; definition: import('../../app/adimensionalizacion/contrato').Expresion; value: number | null }[];
  selection?: { formId: string; execution: import('./contrato').TransformExecution };
  relations?: { id: string; familia: string; descripcion: string; propietarioId: string }[];
  thermodynamicDerivation?: CompilationReport['materialDerivation'];
  energyDerivation?: CompilationReport['materialDerivation'];
  momentumDerivation?: CompilationReport['materialDerivation'];
  materialDerivation?: { volumeId: string; origin: 'recorded' | 'reviewed_rebuild'; operationIds: string[]; signature: string; relationIds: string[] }[];
};

export function readCompilationReport(value: unknown): CompilationReport {
  if (!value || typeof value !== 'object') throw new Error('The compiler returned an invalid report.');
  const report = value as CompilationReport;
  const required = ['format', 'version', 'formulation', 'sourceModelId', 'sourceRevision', 'signature', 'method', 'closureStrategy',
    'variables', 'equations', 'domains', 'conditions', 'direct', 'inverse', 'eliminatedVariables', 'auxiliaryStates', 'time', 'matrix'];
  const optional = ['auxiliaryPurpose', 'equivalence', 'limits', 'relations', 'parameters', 'groups', 'selection', 'materialDerivation', 'energyDerivation', 'thermodynamicDerivation', 'momentumDerivation', 'strategy', 'systemEquations','equationWorkbench','derivedExecution'];
  if(report.derivedExecution!==undefined){
    const derived=report.derivedExecution;
    if(!derived||derived.version!==1||!/^[a-f0-9]{64}$/.test(derived.sourceSignature)||!Array.isArray(derived.proofConditions)||!Array.isArray(derived.runtimeConditions)||!Array.isArray(derived.reconstructions)
      ||Object.keys(derived).some(key=>!['version','sourceSignature','selection','proofConditions','runtimeConditions','reconstructions'].includes(key))
      ||derived.proofConditions.some(row=>!row||typeof row.equationId!=='string'||typeof row.sourceEquationId!=='string'||!['interval_identity','eliminated_coordinate_premise'].includes(row.kind)||typeof row.latex!=='string')
      ||derived.runtimeConditions.some(row=>!row||typeof row.equationId!=='string'||typeof row.strict!=='boolean'||typeof row.latex!=='string'))throw new Error('Invalid derived execution report.');
    readDerivedExecution(derived.selection);
    if(derived.sourceSignature!==derived.selection.sourceSignature||JSON.stringify(derived.reconstructions)!==JSON.stringify(derived.selection.reconstructions))throw new Error('Derived execution provenance disagrees with its selection.');
  }
  optional.push('symbolLabels');
  if (report.symbolLabels !== undefined && (!report.symbolLabels || typeof report.symbolLabels !== 'object' || Array.isArray(report.symbolLabels) || Object.values(report.symbolLabels).some(label => typeof label !== 'string' || !label))) throw new Error('Invalid compiler symbol labels.');
  if(report.equationWorkbench!==undefined)readEquationWorkbenchReport(report.equationWorkbench);
  if (required.some(key => !Object.hasOwn(report, key)) || Object.keys(report).some(key => !required.includes(key) && !optional.includes(key))) throw new Error('Unknown or missing compilation report fields.');
  if (report.format !== 'rage.compilation' || report.version !== 1 || !['physical', 'scaled'].includes(report.formulation)
    || !['nested_equilibrium', 'declared_assumption'].includes(report.closureStrategy)
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
