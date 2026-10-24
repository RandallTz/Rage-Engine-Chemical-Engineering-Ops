'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import type { HojaMotor } from '../motor/hojasMotor';
import { equationSource } from './modelRequest';
import { requestFormulation } from './formulationRequests';
import EquationRows from './EquationRows';
import styles from './workspace.module.css';
import { readDynamicFormulation, type DynamicFormulation } from './dynamicDefinition';

type Summary = { format: 'rage.formulation-summary'; version: 1; modelId: string; dynamicFormulation?: DynamicFormulation; families: { id: string; volumes: { volumeId: string; status: string; note: string; steps: { id: string; title: string; latex: string }[] }[] }[] };
const names: Record<string, string> = { matter: 'Matter balance', energy: 'Energy balance', momentum: 'Momentum balance', thermodynamics: 'Thermodynamics' };
export default function DeducedModelSummary({ model }: { model: HojaMotor }) {
  const source = JSON.stringify(modelRequestSafe(model));
  const [result, setResult] = useState<{ source: string; value?: Summary; error?: string } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const body = JSON.parse(source);
        if (body.error) throw new Error(body.error);
        const response = await requestFormulation('formulation-summary', source);
        const value = await response.json();
        if (!response.ok) throw new Error(value?.detail?.message ?? 'The derived model could not be described.');
        if(value.modelId!==(body.modelo?.id??body.solicitudV2?.solicitudId??body.draft?.modelId))throw new Error('Unexpected formulation source.');
        if (value?.format !== 'rage.formulation-summary' || value.version !== 1 || typeof value.modelId !== 'string' || !Array.isArray(value.families) || value.families.length !== 4 || new Set(value.families.map((family: Summary['families'][number]) => family?.id)).size !== 4 || value.families.some((family: Summary['families'][number]) => !family || !names[family.id] || !Array.isArray(family.volumes) || family.volumes.some(volume => !volume || typeof volume.volumeId !== 'string' || !['recorded', 'unrecorded', 'unsupported'].includes(volume.status) || typeof volume.note !== 'string' || !Array.isArray(volume.steps) || volume.steps.some(step => !step || typeof step.id !== 'string' || typeof step.title !== 'string' || typeof step.latex !== 'string')))) throw new Error('Invalid formulation summary from the Engine.');
        if (value.dynamicFormulation !== undefined) readDynamicFormulation(value.dynamicFormulation);
        if (!controller.signal.aborted) setResult({ source, value });
      } catch (failure) { if (!controller.signal.aborted) setResult({ source, error: (failure as Error).message }); }
    }
    void load();
    return () => controller.abort();
  }, [source]);
  const current = result?.source === source ? result : null;
  return <section className={styles.executionSelection} aria-label="Deduced model entering Transform">
    <span className={styles.kicker}>Model → Transform</span><h2>Deduced physical model</h2>
    <p>The current equations and closures, before any mathematical transformation. <Link href={`/models/${model.id}/model`}>Review assumptions and full derivation →</Link></p>
    {!current && <p role="status">Reading the deduced formulation…</p>}
    {current?.error && <p role="alert">{current.error} Complete or review the formulation in Model; no summary has been inferred.</p>}
    {current?.value?.families.map(family => <article className={styles.handoffFamily} key={family.id}><h3>{names[family.id]}</h3>{!family.volumes.length ? <p>Not active in this model.</p> : family.volumes.map(volume => <div key={volume.volumeId}><p><strong>{model.redTermodinamica?.nombres[`volumen:${volume.volumeId}`] ?? volume.volumeId}</strong> · {volume.note}</p><EquationRows steps={volume.steps} label={`${names[family.id]} · ${volume.volumeId}`}/></div>)}</article>)}
    {current?.value?.dynamicFormulation && <details><summary>Retained dynamics, inventory constraints & domains</summary>{current.value.dynamicFormulation.diagnostics.map((item, index) => <p role="alert" key={index}>{item.message}</p>)}{current.value.dynamicFormulation.inventories.map(item => <EquationRows key={item.id} steps={item.steps} label={`${item.volumeId} · ${item.name}`}/>)}<p>{current.value.dynamicFormulation.scope}</p></details>}
  </section>;
}
function modelRequestSafe(model: HojaMotor) { try { return equationSource(model); } catch (failure) { return { error: (failure as Error).message }; } }
