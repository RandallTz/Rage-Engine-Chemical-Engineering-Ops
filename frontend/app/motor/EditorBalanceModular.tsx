'use client';

import { useState } from 'react';
import FormulaLatex from '../flowsheet/FormulaLatex';
import { balanceVolumen, definicionAportacion, FAMILIAS, terminosVolumen, terminoActivo } from './balanceModular';
import type { Familia, ModeloModular, Naturaleza, Simplificaciones } from './balanceModular';
import styles from './motor.module.css';

export default function EditorBalanceModular({ supuestos }: { supuestos: Simplificaciones }) {
  const [modelo, setModelo] = useState<ModeloModular>({ volumenes: [{ id: 1, nombre: 'Sistema 1' }], aportaciones: [], conexiones: [] });
  const [activo, setActivo] = useState(1);
  const [menu, setMenu] = useState<Familia | null>(null);
  const [conectando, setConectando] = useState(false);
  const terminos = terminosVolumen(modelo, activo);
  function agregar(familia: Familia, naturaleza: Naturaleza) {
    setModelo(m => ({ ...m, aportaciones: [...m.aportaciones, { id: Math.max(0, ...m.aportaciones.map(a => a.id)) + 1, volumen: activo, familia, naturaleza }] }));
    setMenu(null);
  }
  function conectar(hacia: number) {
    setModelo(m => ({ ...m, conexiones: [...m.conexiones, { id: Math.max(0, ...m.conexiones.map(c => c.id)) + 1, desde: activo, hacia }] }));
    setConectando(false);
  }
  return <section className={styles.modular} aria-label="Construcción modular del balance">
    <header className={styles.moduleHeader}><h2>Volúmenes de control</h2><button onClick={() => {
      const id = Math.max(...modelo.volumenes.map(v => v.id)) + 1;
      setModelo(m => ({ ...m, volumenes: [...m.volumenes, { id, nombre: `Sistema ${id}` }] }));
      setActivo(id); setMenu(null); setConectando(false);
    }}>+ Sistema</button></header>
    <nav className={styles.volumeTabs} aria-label="Volumen de control seleccionado">{modelo.volumenes.map(v => <button key={v.id} aria-pressed={activo === v.id} onClick={() => { setActivo(v.id); setMenu(null); setConectando(false); }}>{v.nombre}</button>)}</nav>
    <div className={styles.assembled} aria-live="polite"><FormulaLatex latex={balanceVolumen(modelo, activo, supuestos)} lectura="Balance de materia ensamblado del sistema seleccionado" bloque /></div>
    <div className={styles.familyList}>{FAMILIAS.map(f => {
      const items = terminos.filter(t => t.familia === f.id);
      const bloqueada = supuestos.sinReaccion && ['generacion', 'consumo'].includes(f.id);
      return <section key={f.id} className={styles.family} aria-label={f.nombre}>
        <header><h3><span>{f.signo}</span>{f.nombre}</h3><button disabled={bloqueada} title={bloqueada ? 'Sin reacción: no hay generación ni consumo químicos.' : undefined} aria-expanded={menu === f.id} onClick={() => { setMenu(menu === f.id ? null : f.id); setConectando(false); }}>+ Aportación</button></header>
        {items.map(t => <div className={styles.contribution} data-inactive={!terminoActivo(t, supuestos)} key={t.clave}>
          <FormulaLatex latex={t.simbolo} lectura={t.simbolo} />
          <div className={styles.contributionDefinition}>{t.aportacion ? <details><summary>{({ constante: 'Constante', convectiva: 'Convectiva', difusiva: 'Difusiva', reaccion: 'Reacción', compartida: 'Compartida' }[t.naturaleza])}</summary><div><FormulaLatex latex={definicionAportacion(t.aportacion)} lectura="Definición de la aportación" /></div></details> : <span>Compartida · Sistema {t.conexion?.desde === activo ? t.conexion.hacia : t.conexion?.desde}</span>}<small>kg/s{!terminoActivo(t, supuestos) ? ' · excluida por supuesto' : ''}</small></div>
          <button aria-label={`Quitar aportación ${t.clave} de ${f.nombre}`} title={t.conexion ? 'Quitar la conexión en ambos sistemas' : 'Quitar aportación'} onClick={() => setModelo(m => ({ ...m, aportaciones: m.aportaciones.filter(a => `a${a.id}` !== t.clave), conexiones: m.conexiones.filter(c => `c${c.id}` !== t.clave) }))}>×</button>
        </div>)}
        {!items.length && <span className={styles.emptyFamily}>{bloqueada ? 'Excluida por supuesto' : 'Sin aportaciones declaradas'}</span>}
        {menu === f.id && !bloqueada && <div className={styles.addChoices} aria-label={`Añadir aportación a ${f.nombre}`}>
          {['entrada', 'salida'].includes(f.id) ? (['constante', 'convectiva', 'difusiva'] as const).map(tipo => <button key={tipo} disabled={tipo === 'difusiva' && supuestos.sinDifusion} title={tipo === 'difusiva' && supuestos.sinDifusion ? 'Desactiva el supuesto Sin difusión.' : undefined} onClick={() => agregar(f.id, tipo)}>{({ constante: 'Constante', convectiva: 'Convectiva', difusiva: 'Difusiva' })[tipo]}</button>) : <button onClick={() => agregar(f.id, 'reaccion')}>Por reacción</button>}
          <button onClick={() => setMenu(null)}>Cancelar</button>
        </div>}
      </section>;
    })}</div>
    <div className={styles.connectionControls}><button disabled={modelo.volumenes.length < 2} title={modelo.volumenes.length < 2 ? 'Añade otro sistema para compartir una corriente.' : undefined} aria-expanded={conectando} onClick={() => { setConectando(!conectando); setMenu(null); }}>Conectar salida con otro sistema</button>
      {conectando && <div className={styles.addChoices}>{modelo.volumenes.filter(v => v.id !== activo).map(v => <button key={v.id} onClick={() => conectar(v.id)}>Hacia {v.nombre}</button>)}</div>}
    </div>
    {!!modelo.conexiones.length && <section className={styles.coupling} aria-label="Acoplamiento entre volúmenes"><h3>Un flujo compartido</h3>{modelo.conexiones.map(c => <div key={c.id} className={styles.sharedFlow}>
      <span>Sistema {c.desde}</span><FormulaLatex latex={String.raw`-\phi_{i,${c.id}}\;\longrightarrow\;+\phi_{i,${c.id}}`} lectura="La salida del origen es la entrada del destino" /><span>Sistema {c.hacia}</span>
      <span className={styles.cancellation}><FormulaLatex latex={`-\\phi_{i,${c.id}}+\\phi_{i,${c.id}}=0`} lectura="El flujo interno se cancela en el balance global" /></span>
    </div>)}<details><summary>Ver balances acoplados</summary>{modelo.volumenes.map(v => <div className={styles.coupledEquation} key={v.id}><h4>{v.nombre}</h4><FormulaLatex latex={balanceVolumen(modelo, v.id, supuestos)} lectura={`Balance de ${v.nombre}`} bloque /></div>)}</details></section>}
  </section>;
}
