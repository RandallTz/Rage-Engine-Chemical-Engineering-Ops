import { useState } from 'react';
import type { FormEvent } from 'react';
import { crearComponente } from './recorridoMateria';
import type { FormulacionMateria, RecorridoMateria } from './recorridoMateria';
import styles from './motor.module.css';

export default function GestorComponentesMateria({ historial, onCambiar }: { historial: RecorridoMateria; onCambiar: (titulo: string, cambios: Partial<FormulacionMateria>) => void }) {
  const componentes = historial.pasos[historial.activo].formulacion.componentes ?? [];
  const [nombre, setNombre] = useState('');
  const [error, setError] = useState('');
  function agregar(e: FormEvent) {
    e.preventDefault();
    const limpio = nombre.trim();
    if (!limpio) { setError("Enter a name."); return; }
    if (componentes.some(c => c.nombre.toLocaleLowerCase() === limpio.toLocaleLowerCase())) { setError("This component is already in the model."); return; }
    const c = crearComponente(historial, limpio);
    onCambiar(`Add component: ${c.nombre}`, { componentes: [...componentes, c] });
    setNombre(''); setError('');
  }
  return <section className={styles.componentManager} aria-label="Model components">
    <header><h3>Components</h3><span>{componentes.length || 'i'}</span></header>
    <form onSubmit={agregar}><label className={styles.srOnly} htmlFor="nombre-componente-materia">Component name</label><input id="nombre-componente-materia" placeholder="Component name" value={nombre} onChange={e => { setNombre(e.target.value); setError(''); }} aria-invalid={!!error} aria-describedby={error ? 'error-componente-materia' : undefined} /><button type="submit">Add</button></form>
    {error && <span className={styles.componentError} id="error-componente-materia" role="alert">{error}</span>}
    {componentes.map(c => <div className={styles.componentItem} key={c.id}><span className={styles.componentSymbol}>{c.simbolo}</span><input key={`${c.id}:${c.nombre}`} defaultValue={c.nombre} aria-label={`Component name ${c.simbolo}`} onBlur={e => { const nuevo = e.target.value.trim(); if (!nuevo || componentes.some(x => x.id !== c.id && x.nombre.toLocaleLowerCase() === nuevo.toLocaleLowerCase())) { e.target.value = c.nombre; return; } if (nuevo !== c.nombre) onCambiar(`Rename component ${c.simbolo}: ${nuevo}`, { componentes: componentes.map(x => x.id === c.id ? { ...x, nombre: nuevo } : x) }); }} /><button aria-label={`Quitar componente ${c.nombre}`} onClick={() => onCambiar(`Remove component: ${c.nombre}`, { componentes: componentes.filter(x => x.id !== c.id) })}>×</button></div>)}
  </section>;
}
