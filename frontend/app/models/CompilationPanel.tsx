'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useHojasMotor } from '../motor/useHojasMotor';
import { analizarHoja, firmaHoja, transformationSourceSignature } from '../motor/modeloHojaMotor';
import { requestCompilationAssessment } from '../../motores/modelo/servicioModelo';
import type {ModelAssessment} from '../../motores/modelo/assessment';
import AssessmentText from './AssessmentText';
import {saveRejectedAttempt} from '../motor/resultadosMotor';
import type { CompilationReport } from '../../motores/modelo/compilation';
import { modelRequest } from './modelRequest';
import CompilationSummary from './CompilationSummary';
import { modelUrl } from './workflow';
import styles from './workspace.module.css';
import {currentFlowsheet} from './flowsheetLifecycle';

export default function CompilationPanel({ id }: { id: string }) {
  const model = useHojasMotor().find(item => item.id === id);
  const signature = model ? firmaHoja(model) : '';
  const [result, setResult] = useState<{ signature: string; report: CompilationReport;assessment?:ModelAssessment } | null>(null);
  const [failure, setFailure] = useState<{ signature: string; error:Error } | null>(null), [attempt, setAttempt] = useState(0);
  let body = '', preparationError = '';
  if (model && !model.commonModel?.flowsheet) try { body = JSON.stringify(modelRequest(model, true)); } catch (error) { preparationError = (error as Error).message; }
  useEffect(() => {
    if (!body) return;
    const controller = new AbortController();
    requestCompilationAssessment(JSON.parse(body), controller.signal).then(value => {
      if (!controller.signal.aborted) { setResult({ signature, ...value }); setFailure(null); }
    }).catch(async error => {
      if(controller.signal.aborted)return;
      setResult(null);setFailure({signature,error});
      try{await saveRejectedAttempt(id,signature,error,controller.signal,'compilation');}
      catch(storageError){if(!controller.signal.aborted)setFailure({signature,error:Object.assign(error,{message:error.message+' '+(storageError as Error).message})});}
    });
    return () => controller.abort();
  }, [body, signature, attempt,id]);
  if (!model) return null;
  if (model.commonModel?.flowsheet) {
    const selected=currentFlowsheet(model);
    return <section className={styles.executionSelection} aria-label="Formulation entering Solve"><span className={styles.kicker}>Transform → Solve</span><h2>Formulation entering Solve</h2>
      {selected?<p>{selected.selection.mode} flowsheet · {selected.count} instances · {selected.rateRowCount} original rate rows</p>:<p role="alert">{model.flowsheetStale?'stale_flowsheet_execution: The topology or data changed.':'No flowsheet formulation is selected.'} Prepare the network in Transform.</p>}
      <Link href={modelUrl(id,'transform')}>Review Transform →</Link>
    </section>;
  }
  const selected = model.transformation;
  const outdated = selected && selected.sourceSignature !== transformationSourceSignature(model);
  const current = result?.signature === signature ? result.report : null;
  const typedError=failure?.signature===signature?failure.error:undefined;
  const error = preparationError || typedError?.message;
  const spatial = !model.commonModel && !model.redTermodinamica && !model.hydraulicNetwork && analizarHoja(model).modo === '1d';
  return <section className={styles.executionSelection} aria-label="Formulation entering Solve">
    <span className={styles.kicker}>Transform → Solve</span><h2>Formulation entering Solve</h2>
    <p>{selected ? `${selected.label} · selected in Transform${outdated ? ' · outdated' : ''}` : spatial ? 'Physical formulation with the finite-volume mesh configured in Transform' : 'Identity transformation · the deduced physical model passes through unchanged'} · <Link href={modelUrl(id, 'transform')}>Review Transform →</Link></p>
    {spatial && <p>Transform output: {model.config.celdas} finite-volume cells · fixed 1D Cartesian mesh. Time integration is configured below in Solve. Common Python spatial compilation remains pending.</p>}
    {outdated && <p role="alert" className={styles.error}>The physical inputs changed. Recalculate the transformation or explicitly select the physical formulation before running.</p>}
    {!current && !error && <p role="status">Compiling equations, compatible methods and the mathematical solution plan…</p>}
    {error && <p role="alert" className={styles.error}>{error}</p>}
    {(current||typedError)&&<AssessmentText assessment={result?.signature===signature?result.assessment:undefined} error={typedError}/>}
    {typedError&&<Link href={modelUrl(id,'results')}>Review rejected attempt in Results</Link>}
    {error && !outdated && <button className={styles.secondary} onClick={() => setAttempt(value => value + 1)}>Retry compilation</button>}
    {current && <CompilationSummary report={current}/>}
    {current?.derivedExecution?.dae && <details><summary>Index-one admission</summary><p>{current.derivedExecution.dae.proof}</p><p>Initialization: given differential states remain fixed. Algebraic variables use the existing Newton block inside SciPy BDF.</p><p>Determinant: {current.derivedExecution.dae.determinant}; drift tolerance: {current.derivedExecution.dae.driftTolerance}</p></details>}
    {current?.derivedExecution?.nonlinearBlock && <details><summary>Nonlinear initialization evidence</summary>
      <p>{current.derivedExecution.nonlinearBlock.scope}</p>
      <dl>{(['iterations','evaluations','backtracks','residualNorm','stepNorm','conditionInfinity','terminationReason'] as const).map(key=><div key={key}><dt>{key}</dt><dd>{String(current.derivedExecution!.nonlinearBlock!.initialization[key]??'Not evaluated')}</dd></div>)}</dl>
    </details>}
  </section>;
}
