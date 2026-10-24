'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useHojasMotor } from '../motor/useHojasMotor';
import { analizarHoja, firmaHoja, transformationSourceSignature } from '../motor/modeloHojaMotor';
import { requestCompilation } from '../../motores/modelo/servicioModelo';
import type { CompilationReport } from '../../motores/modelo/compilation';
import { modelRequest } from './modelRequest';
import CompilationSummary from './CompilationSummary';
import { modelUrl } from './workflow';
import styles from './workspace.module.css';

export default function CompilationPanel({ id }: { id: string }) {
  const model = useHojasMotor().find(item => item.id === id);
  const signature = model ? firmaHoja(model) : '';
  const [result, setResult] = useState<{ signature: string; report: CompilationReport } | null>(null);
  const [failure, setFailure] = useState<{ signature: string; message: string } | null>(null), [attempt, setAttempt] = useState(0);
  let body = '', preparationError = '';
  if (model) try { body = JSON.stringify(modelRequest(model, true)); } catch (error) { preparationError = (error as Error).message; }
  useEffect(() => {
    if (!body) return;
    const controller = new AbortController();
    requestCompilation(JSON.parse(body), controller.signal).then(report => {
      if (!controller.signal.aborted) { setResult({ signature, report }); setFailure(null); }
    }).catch(error => { if (!controller.signal.aborted) setFailure({ signature, message: error.message }); });
    return () => controller.abort();
  }, [body, signature, attempt]);
  if (!model) return null;
  const selected = model.transformation;
  const outdated = selected && selected.sourceSignature !== transformationSourceSignature(model);
  const current = result?.signature === signature ? result.report : null;
  const error = preparationError || (failure?.signature === signature ? failure.message : '');
  const spatial = !model.commonModel && !model.redTermodinamica && !model.hydraulicNetwork && analizarHoja(model).modo === '1d';
  return <section className={styles.executionSelection} aria-label="Formulation entering Solve">
    <span className={styles.kicker}>Transform → Solve</span><h2>Formulation entering Solve</h2>
    <p>{selected ? `${selected.label} · selected in Transform${outdated ? ' · outdated' : ''}` : spatial ? 'Physical formulation with the finite-volume mesh configured in Transform' : 'Identity transformation · the deduced physical model passes through unchanged'} · <Link href={modelUrl(id, 'transform')}>Review Transform →</Link></p>
    {spatial && <p>Transform output: {model.config.celdas} finite-volume cells · fixed 1D Cartesian mesh. Time integration is configured below in Solve. Common Python spatial compilation remains pending.</p>}
    {outdated && <p role="alert" className={styles.error}>The physical inputs changed. Recalculate the transformation or explicitly select the physical formulation before running.</p>}
    {!current && !error && <p role="status">Compiling equations, compatible methods and the mathematical solution plan…</p>}
    {error && <p role="alert" className={styles.error}>{error}</p>}
    {error && !outdated && <button className={styles.secondary} onClick={() => setAttempt(value => value + 1)}>Retry compilation</button>}
    {current && <CompilationSummary report={current}/>}
  </section>;
}
