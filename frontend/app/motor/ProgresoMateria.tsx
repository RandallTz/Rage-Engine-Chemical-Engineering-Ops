import { englishLabel } from '../models/english';
import { useEffect, useRef } from 'react';
import FormulaMateria from './FormulaMateria';
import { balancesComponentes, FORMAS_MATERIA, relacionesNuevas, siguientePaso, unidadBalance } from './recorridoMateria';
import type { RecorridoMateria } from './recorridoMateria';
import styles from './motor.module.css';

export default function ProgresoMateria({ historial, onIr, onRehacer, onNueva }: { historial: RecorridoMateria; onIr: (indice: number) => void; onRehacer: () => void; onNueva: () => void }) {
  const filaActual = useRef<HTMLElement>(null);
  const anterior=useRef({activo:historial.activo,longitud:historial.pasos.length});
  useEffect(() => {
    const cambia=anterior.current.activo!==historial.activo||anterior.current.longitud!==historial.pasos.length;
    anterior.current={activo:historial.activo,longitud:historial.pasos.length};
    if(cambia&&historial.pasos.length>1)filaActual.current?.scrollIntoView({block:'nearest'});
  }, [historial.activo, historial.pasos.length]);
  const padre = historial.pasos[historial.activo].origen;
  const siguiente = siguientePaso(historial);
  return <section className={styles.worksheet} aria-label="Mathematical development">
    <header className={styles.sheetToolbar}><h2>Mathematical development</h2><div><button disabled={historial.activo === 0} onClick={() => onIr(0)}>Home</button><button disabled={padre === null} onClick={() => padre !== null && onIr(padre)}>Undo</button><button disabled={siguiente < 0} onClick={onRehacer}>Redo</button><select aria-label="Go to step" value={historial.activo} onChange={e => onIr(Number(e.target.value))}>{historial.pasos.map((p, i) => <option key={i} value={i}>{String(i + 1).padStart(2, '0')} · {englishLabel(p.titulo)}</option>)}</select><a href="#variables-materia">Variables</a><button onClick={onNueva}>Reset derivation</button></div></header>
    <div aria-live="polite" className={styles.srOnly}>Current step: {historial.activo + 1}</div>
    {historial.pasos.map((paso, i) => {
      const seleccionado = i === historial.activo;
      const origen = paso.origen === null ? undefined : historial.pasos[paso.origen];
      const relaciones = relacionesNuevas(paso, origen);
      return <article key={i} ref={seleccionado ? filaActual : undefined} className={styles.derivationRow} data-current={seleccionado} aria-label={`Step ${i + 1}: ${paso.titulo}`} aria-current={seleccionado ? 'step' : undefined}>
        <span className={styles.rowNumber}>{String(i + 1).padStart(2, '0')}</span>
        <div className={styles.rowBody}>
          <header><h3>{englishLabel(paso.titulo)}</h3><div><span>{englishLabel(FORMAS_MATERIA[paso.formulacion.vista])} · {unidadBalance(paso.formulacion)}</span>{seleccionado ? <span className={styles.currentStep}>Current</span> : <button aria-label={`Continue from step ${i + 1}`} onClick={() => onIr(i)}>Continue here</button>}{paso.origen !== null && <button className={styles.deleteStep} aria-label={`Remove step ${i + 1}`} title="Remove this step and its dependents" onClick={() => onIr(paso.origen!)}>×</button>}</div></header>
          {paso.origen !== null && <button className={styles.branchOrigin} onClick={() => onIr(paso.origen!)}>Return to step {paso.origen + 1}</button>}
          <div id={`paso-${i + 1}`} className={styles.componentEquations} data-component-count={paso.formulacion.componentes?.length ?? 0}>{balancesComponentes(paso.formulacion).map(({ componente, latex }) => <section className={styles.componentEquation} key={componente?.id ?? 'i'} aria-label={componente ? `Balance for ${componente.nombre}` : "Balance for component i"}>{componente && <h4>{componente.nombre}<span>{componente.simbolo}</span></h4>}<div className={styles.math}><FormulaMateria latex={latex} lectura={componente ? `Equation for ${componente.nombre}` : "Equation obtained in this step"} bloque /></div></section>)}</div>
          {relaciones.length > 0 && <div className={styles.stepRelations}>{relaciones.map(latex => <div key={latex}><FormulaMateria latex={latex} lectura="Relation introduced in this step" bloque /></div>)}</div>}
        </div>
      </article>;
    })}
  </section>;
}
