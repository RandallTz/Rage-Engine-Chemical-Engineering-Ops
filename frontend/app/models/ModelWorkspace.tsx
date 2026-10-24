'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, type ReactNode } from 'react';
import { guardarHoja, leerHojas } from '../motor/hojasMotor';
import { useHojasMotor } from '../motor/useHojasMotor';
import { firmaHoja } from '../motor/modeloHojaMotor';
import { modelUrl, WORKSPACES } from './workflow';
import WorkspaceVisual from './WorkspaceVisual';
import { useBrowserReady } from './useBrowserReady';
import styles from './workspace.module.css';

export default function ModelWorkspace({ id, children }: { id: string; children: ReactNode }) {
  const models = useHojasMotor();
  const model = models.find(item => item.id === id);
  const pathname = usePathname();
  const active = WORKSPACES.find(stage => pathname.startsWith(modelUrl(id, stage.id))) ?? WORKSPACES[0];
  const ready = useBrowserReady();
  const [error, setError] = useState('');

  if (!ready) return <div className={styles.loading} role="status" aria-label="Loading model"><div/><div/><div/></div>;
  if (!model) return <div className={styles.shell}><Link href="/models">← Models</Link><section className={styles.empty}><h1>Model not found</h1><p>This model is not saved in this browser. Open an existing model or create a new one.</p><Link href="/models" className={styles.primary}>Browse models</Link></section></div>;
  const currentResult = model.resultadoRef?.firma === firmaHoja(model) || model.resultado?.firma === firmaHoja(model);

  function rename(value: string) {
    try {
      const current = leerHojas().find(item => item.id === id);
      if (current && value.trim() && value.trim() !== current.nombre) guardarHoja({ ...current, nombre: value.trim() });
      setError('');
    } catch { setError('Your changes could not be saved. Check the storage available in this browser.'); }
  }

  return <div className={styles.shell}>
    <header className={styles.modelHeader}>
      <div><Link href="/models" className={styles.back}>← Models</Link><form onSubmit={event => { event.preventDefault(); rename(String(new FormData(event.currentTarget).get('name') ?? '')); }}><label htmlFor="model-name" className={styles.srOnly}>Model name</label><input id="model-name" name="name" key={model.nombre} defaultValue={model.nombre} onBlur={event => { if (!event.target.value.trim()) event.target.value = model.nombre; else rename(event.target.value); }} maxLength={100}/></form></div>
      <span className={styles.saveStatus}>Saved in this browser</span>
    </header>
    {error && <p className={styles.error} role="alert">{error}</p>}
    <nav className={styles.workspaces} aria-label="Model workflow">
      {WORKSPACES.map(stage => <Link key={stage.id} href={modelUrl(id, stage.id)} className={styles.workspace} aria-current={active.id === stage.id ? 'step' : undefined}>
        <div className={styles.stageTop}><span>{stage.number}</span><span>{stage.id === 'results' ? currentResult ? 'Available' : 'No current run' : active.id === stage.id ? 'Current workspace' : 'Open workspace'}</span></div>
        <div className={styles.visual}><WorkspaceVisual workspace={stage.id}/></div>
        <div className={styles.stageBottom}><h2>{stage.name}</h2><span aria-hidden="true">↗</span></div><p>{stage.description}</p>
      </Link>)}
    </nav>
    <section className={styles.workspaceBody} aria-label={`${active.name} workspace`}>
      <header className={styles.stageHeader}><div><span className={styles.kicker}>Workspace {active.number}</span><h1>{active.name}</h1></div><p>{active.instruction}</p></header>
      {typeof model.workspaceNotes?.[active.id]==='string'&&<aside className={styles.notice} aria-label={`${active.name} study notes`}>{model.workspaceNotes[active.id]}</aside>}
      {children}
    </section>
    <footer className={styles.footer}><span>One model. Connected mathematical steps.</span>{active.id !== 'results' && <Link href={modelUrl(id, WORKSPACES[WORKSPACES.findIndex(stage => stage.id === active.id) + 1].id)}>Continue to {WORKSPACES[WORKSPACES.findIndex(stage => stage.id === active.id) + 1].name} →</Link>}</footer>
  </div>;
}
