'use client';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useHojasMotor } from '../motor/useHojasMotor';
import { duplicarHoja, guardarHoja, nuevaHoja, removeAllModels, restoreRemovedModels } from '../motor/hojasMotor';
import { auditModelDerivation } from './modelDerivationAudit';
import { modelUrl, WORKSPACES } from './workflow';
import { useBrowserReady } from './useBrowserReady';
import styles from './workspace.module.css';
import { importModelFile } from './modelImport';

export default function ModelLibrary() {
  const router = useRouter(), models = useHojasMotor(true);
  const [creating, setCreating] = useState(false), [name, setName] = useState(''), [archived, setArchived] = useState(false), [removed,setRemoved]=useState(false), [search, setSearch] = useState(''), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const ready = useBrowserReady();
  const [importing, setImporting] = useState(false);
  const visible = models.filter(model => (removed ? !!model.removedAt : !model.removedAt && !!model.archivada === archived) && model.nombre.toLowerCase().includes(search.toLowerCase()));
  function perform(action: () => void) { try { action(); setError(''); } catch { setError('The model could not be saved. Check the storage available in this browser.'); } }

  return <div className={styles.shell}>
    <header className={styles.libraryHeader}><div><span className={styles.kicker}>Rage / Simulation engine</span><h1>Your models</h1><p>Build a physical model. Choose its mathematical representation. Solve it and inspect the result.</p></div><button className={styles.primary} onClick={() => setCreating(true)}>Create model <span aria-hidden="true">+</span></button></header>
    <label className={styles.secondary}>{importing ? 'Validating model…' : 'Import model'}<input aria-label="Import model file" type="file" accept=".json,application/json" disabled={importing} onChange={async event => {
      const file = event.currentTarget.files?.[0]; event.currentTarget.value = '';
      if (!file) return;
      setImporting(true); setError('');
      try { if (file.size > 5_000_000) throw new Error('The model file exceeds 5 MB.'); const model = await importModelFile(JSON.parse(await file.text())); guardarHoja(model); router.push(modelUrl(model.id)); }
      catch (failure) { setError((failure as Error).message); }
      finally { setImporting(false); }
    }}/></label>
    <section className={styles.libraryGuide} aria-label="How a model works">{WORKSPACES.map(stage => <div key={stage.id}><span>{stage.number}</span><h2>{stage.name}</h2><p>{stage.description}</p></div>)}</section>
    {error && <p className={styles.error} role="alert">{error}</p>}{notice && <p className={styles.notice} role="status">{notice}</p>}
    {creating && <form className={styles.newModel} onSubmit={event => { event.preventDefault(); if (!name.trim()) { setError('Enter a model name.'); return; } perform(() => { const model = guardarHoja(nuevaHoja(name)); router.push(modelUrl(model.id)); }); }}><h2>Create a model</h2><label htmlFor="new-model-name">Model name<input id="new-model-name" autoFocus required value={name} onChange={event => setName(event.target.value)} placeholder="Name your physical system" maxLength={100}/></label><footer><button className={styles.primary}>Create model</button><button type="button" onClick={() => setCreating(false)}>Cancel</button></footer></form>}
    <nav className={styles.libraryToolbar} aria-label="Model library"><button aria-pressed={!archived&&!removed} onClick={() => {setArchived(false);setRemoved(false);}}>Active models</button><button aria-pressed={archived&&!removed} onClick={() => {setArchived(true);setRemoved(false);}}>Archived</button><button aria-pressed={removed} onClick={()=>setRemoved(true)}>Removed</button><button disabled={!models.some(model=>!model.removedAt)} onClick={()=>perform(()=>{const count=removeAllModels();setRemoved(false);setArchived(false);setNotice(`${count} models removed. Recovery is available under Removed.`);})}>Remove all models</button>{removed&&<button disabled={!models.some(model=>model.removedAt)} onClick={()=>perform(()=>{const count=restoreRemovedModels();setNotice(`${count} models restored.`);setRemoved(false);setArchived(false);})}>Restore removed models</button>}<label className={styles.srOnly} htmlFor="search-models">Search models</label><input id="search-models" type="search" placeholder="Search models" value={search} onChange={event => setSearch(event.target.value)}/></nav>
    {!ready ? <div className={styles.loading} role="status" aria-label="Loading models"><div/><div/></div> : !visible.length ? <section className={styles.empty}><h2>{search ? 'No matching models' : removed ? 'No removed models' : archived ? 'No archived models' : 'Start with a physical system'}</h2><p>{search ? 'Try a different model name.' : removed ? 'Removed models can be recovered here.' : archived ? 'Archived models remain available here for restoration.' : 'Create a model to derive equations from fundamental laws.'}</p>{!archived && !removed && !search && <button className={styles.secondary} onClick={() => setCreating(true)}>Create your first model →</button>}</section> : <div className={styles.modelList}>{visible.map(model => <article className={styles.modelItem} key={model.id}>{removed?<div><h2>{model.nombre}</h2><p>Removed from the model library. Restore removed models to recover it.</p></div>:<><Link href={modelUrl(model.id)}><span className={styles.kicker}>{model.redTermodinamica ? 'Thermodynamic network' : model.ensamblaje ? 'Coupled system' : 'Physical model'}</span><h2>{model.nombre}</h2><p>{model.redTermodinamica ? `${model.redTermodinamica.solicitud.volumenes.length} volumes · ${model.redTermodinamica.solicitud.componentes.length} components` : model.ensamblaje ? `${model.ensamblaje.volumenes.length} volumes · ${model.ensamblaje.corrientes.length} streams` : `${model.historial.pasos.length} derivation steps · ${model.historial.pasos[model.historial.activo].formulacion.componentes?.length ?? 0} components`}</p><p>{auditModelDerivation(model).status === 'needs_review' ? 'Derivation review required' : auditModelDerivation(model).status === 'fundamental' ? 'Fundamental starting point' : 'Derivation history recorded'}</p><time dateTime={model.actualizada}>{new Date(model.actualizada).toLocaleString('en-GB')}</time></Link><footer><Link href={modelUrl(model.id)}>Open model →</Link><button onClick={() => perform(() => { guardarHoja(duplicarHoja(model)); })}>Duplicate</button><button onClick={() => perform(() => { guardarHoja({ ...model, archivada: !model.archivada }); })}>{model.archivada ? 'Restore' : 'Archive'}</button></footer></>}</article>)}</div>}
    <footer className={styles.footer}><span>Models are saved in this browser.</span><span>Model → Transform → Solve → Results</span></footer>
  </div>;
}
