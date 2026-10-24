'use client';

import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { useHojasMotor } from '../motor/useHojasMotor';
import { guardarHoja, leerHojas } from '../motor/hojasMotor';
import { modelRequest } from './modelRequest';
import { definitionOf, readDynamicDefinition, readDynamicFormulation, withDefinition, type DynamicDefinition, type DynamicFormulation, type InventoryOperation, type Dependent } from './dynamicDefinition';
import EquationRows from './EquationRows';
import styles from '../motor/motor.module.css';

type Family = 'materia' | 'energia' | 'termodinamica' | 'momento';
type Context = { model?: Parameters<typeof modelRequest>[0]; report?: DynamicFormulation; owner?: string; error?: string; pending: boolean; definition?: DynamicDefinition | null; edit: (action: { kind: 'append'; operation: InventoryOperation } | { kind: 'undo' }) => Promise<void> };
const DynamicContext = createContext<Context | null>(null);
export function usePhysicalModel(){return useContext(DynamicContext)?.model;}
function requestSource(model: Parameters<typeof modelRequest>[0]) { try { return JSON.stringify(modelRequest(model)); } catch { return ''; } }
function storedDefinition(model: Parameters<typeof modelRequest>[0] | undefined) { try { const value = model && definitionOf(model); return value ? readDynamicDefinition(value) : undefined; } catch { return undefined; } }

/** Model-only authoring in the existing worksheet. Python owns all equations. */
export function DynamicModelProvider({ id, children }: { id: string; children: ReactNode }) {
  const model = useHojasMotor().find(item => item.id === id);
  const source = model ? requestSource(model) : '';
  const [state, setState] = useState<{ source: string; report?: DynamicFormulation; definition?: DynamicDefinition | null; error?: string }>();
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (!source) return;
    const ctl = new AbortController();
    void fetch(`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8004'}/modelo/dynamic-definition`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: source, cache: 'no-store', signal: AbortSignal.any([ctl.signal, AbortSignal.timeout(20000)]) }).then(async response => {
      const body = await response.json();
      if (!response.ok) throw new Error(body?.detail?.message ?? 'The inventory formulation could not be read.');
      const report = readDynamicFormulation(body.formulation);
      if (body.definition !== null) readDynamicDefinition(body.definition);
      if (!ctl.signal.aborted) setState({ source, report, definition: body.definition });
    }).catch(failure => { if (!ctl.signal.aborted) setState({ source, error: (failure as Error).message }); });
    return () => ctl.abort();
  }, [source]);
  const current = state?.source === source ? state : undefined;
  const owners = current?.report ? [...new Set(current.report.inventories.map(item => item.volumeId).concat(current.report.closures.map(item => item.volumeId)))] : [];
  const owner = model?.volumenActivo && owners.includes(model.volumenActivo) ? model.volumenActivo : owners[0];
  async function edit(action: Parameters<Context['edit']>[0]) {
    if (!model || !source || saving) return;
    setSaving(true);
    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8004'}/modelo/dynamic-definition`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...JSON.parse(source), action }), cache: 'no-store', signal: AbortSignal.timeout(20000) });
      const body = await response.json();
      if (!response.ok) throw new Error(body?.detail?.message ?? 'The inventory operation was rejected.');
      const definition = readDynamicDefinition(body.definition);
      readDynamicFormulation(body.formulation);
      const latest = leerHojas().find(item => item.id === id);
      if (!latest || requestSource(latest) !== source || JSON.stringify(definitionOf(latest)) !== JSON.stringify(definitionOf(model))) throw new Error('The physical model changed. The outdated operation was discarded.');
      guardarHoja(withDefinition(latest, definition));
    } catch (failure) { setState(previous => ({ ...previous, source, error: (failure as Error).message })); }
    finally { setSaving(false); }
  }
  return <DynamicContext.Provider value={{ model, report: current?.report, definition: current?.definition ?? storedDefinition(model), owner, error: current?.error ?? (!source ? 'The physical model is not available to the common reader yet. Complete its definition first.' : undefined), pending: saving || !!source && !current, edit }}>{children}</DynamicContext.Provider>;
}

function familyInventory(kind: string, family: Family) { return family === 'materia' ? kind !== 'energy' : family === 'energia' ? kind === 'energy' : false; }
function binding(value: Dependent & { dataId: string }): Dependent { return value.kind === 'component_flow' ? { kind: value.kind, id: value.id, componentId: value.componentId } : { kind: value.kind, id: value.id }; }

export function DynamicInventoryControls({ family }: { family: Family }) {
  const context = useContext(DynamicContext);
  const [selected, setSelected] = useState(''), [choice, setChoice] = useState(''), [mode, setMode] = useState<'dynamic' | 'fixed'>('fixed'), [reason, setReason] = useState('');
  if (!context || family === 'momento') return null;
  const items = context.report?.inventories.filter(item => item.volumeId === context.owner && familyInventory(item.inventory.kind, family)) ?? [];
  const item = items.find(row => row.id === selected) ?? items[0];
  const options = item?.options ?? [];
  const option = options.find(option => JSON.stringify(binding(option)) === choice);
  return <details className={styles.operationGroup}>
    <summary>Dynamic inventories & constraints</summary>
    <p className={styles.groupHint}>Balances remain dynamic. A permanent fixed inventory adds a compatibility equation and needs a dependent flow. Initial stationarity belongs to Solve.</p>
    {context.pending && <p role="status">Reading inventory formulation…</p>}
    {context.error && <p role="alert">{context.error}</p>}
    {family === 'termodinamica' ? <p className={styles.groupHint}>Properties and phase closure consume the same material and energy inventories. Review their roles and domains in the development.</p> : item && <fieldset disabled={context.pending} className={styles.assumptionControls}>
      <label className={styles.diffusionChoice}>Inventory<select aria-label="Inventory constraint target" value={item.id} onChange={event => { setSelected(event.target.value); setChoice(''); }}>{items.map(row => <option key={row.id} value={row.id}>{row.name} · {row.unit} · {row.mode}</option>)}</select></label>
      <p className={styles.groupHint}>Current condition: {item.mode === 'fixed' ? 'permanent fixed inventory' : 'dynamic inventory'}. Record the next operation to change it.</p>
      <label className={styles.diffusionChoice}>Next condition<select aria-label="Inventory condition" value={mode} onChange={event => setMode(event.target.value as 'dynamic' | 'fixed')}><option value="fixed">Permanent fixed inventory</option><option value="dynamic">Remove permanent constraint · retain dynamics</option></select></label>
      {mode === 'fixed' && <label className={styles.diffusionChoice}>Dependent flow<select aria-label="Dependent inventory flow" value={option ? choice : ''} onChange={event => setChoice(event.target.value)}><option value="">Select a flow already declared in this model</option>{options.map(row => <option key={row.dataId} value={JSON.stringify(binding(row))}>{row.id}{'componentId' in row ? ` · component ${row.componentId}` : ''} · {row.dataId}</option>)}</select></label>}
      {mode === 'fixed' && !options.length && <p className={styles.groupHint}>No compatible flow exists. Declare a stream or prescribed heat exchange in Physical system first. No controller is invented.</p>}
      <label className={styles.diffusionChoice}>Physical reason<input aria-label="Inventory constraint reason" value={reason} maxLength={2000} onChange={event => setReason(event.target.value)} placeholder="Why must this inventory remain fixed?"/></label>
      <button disabled={!reason.trim() || mode === 'fixed' && !option} onClick={async () => { await context.edit({ kind: 'append', operation: { id: crypto.randomUUID(), volumeId: item.volumeId, inventory: item.inventory, mode, reason: reason.trim(), ...(mode === 'fixed' && option ? { dependent: binding(option) } : {}) } }); }}>Record inventory condition</button>
    </fieldset>}
    {!!context.definition?.operations.length && <><button disabled={context.pending} onClick={() => void context.edit({ kind: 'undo' })}>Undo last inventory operation</button><details><summary>Inventory operation history · {context.definition.operations.length}</summary><ol>{context.definition.operations.map(op => <li key={op.id}>{op.volumeId} · {op.inventory.kind}{'componentId' in op.inventory ? ` ${op.inventory.componentId}` : 'coordinate' in op.inventory ? ` ${op.inventory.coordinate}` : ''} · {op.mode}<p>{op.reason}</p></li>)}</ol></details></>}
  </details>;
}

/** Kept separate from the deduction journal: conservation + added constraints. */
export function DynamicInventoryDevelopment({ family }: { family: Family }) {
  const context = useContext(DynamicContext);
  if (!context || family === 'momento') return null;
  const report = context.report;
  const items = report?.inventories.filter(item => item.volumeId === context.owner && familyInventory(item.inventory.kind, family)) ?? [];
  const diagnostics = report?.diagnostics.filter(item => item.volumeId === context.owner) ?? [];
  return <section aria-label="Dynamic physical formulation">
    <h2>Dynamic physical formulation</h2>
    {context.error && <p role="alert">{context.error}</p>}
    {context.pending && !report && <p role="status">Reading the physical formulation…</p>}
    {diagnostics.map((item, index) => <p key={`${item.code}:${index}`} role="alert">{item.message}</p>)}
    {items.map(item => <div key={item.id}><p>{item.name} · {item.unit} · {item.mode === 'fixed' ? 'Permanent constraint; dynamic balance retained' : 'Dynamic; a zero derivative does not remove this quantity'}</p><EquationRows steps={item.steps} label={`${item.name} dynamic balance`}/></div>)}
    {family === 'termodinamica' && report?.closures.filter(item => item.volumeId === context.owner).map(item => <p key={item.volumeId}>{item.packageId ?? 'Explicit constitutive assumption'} · {item.note}</p>)}
    {(family === 'materia' || family === 'termodinamica') && report && <EquationRows steps={report.domains.filter(item => item.volumeId === context.owner).map(item => ({ ...item, description: item.note }))} label="Inventory and fraction domains"/>}
    {report && <details className={styles.integrationBridge}><summary>Variable roles & formulation scope</summary><table><thead><tr><th>Variable / group</th><th>Role</th><th>Unit</th><th>Defined by</th></tr></thead><tbody>{report.variables.filter(item => item.volumeId === context.owner || item.role === 'dependent_unknown').map((item, index) => <tr key={`${item.id}:${index}`}><td>{item.id}</td><td>{item.role.replaceAll('_', ' ')}</td><td>{item.unit}</td><td>{item.source}</td></tr>)}</tbody></table><p>{report.scope}</p></details>}
  </section>;
}
