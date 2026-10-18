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
  return <section className={styles.worksheet} aria-label="Desglose matemático">
    <header className={styles.sheetToolbar}><h2>Desglose matemático</h2><div><button disabled={historial.activo === 0} onClick={() => onIr(0)}>Inicio</button><button disabled={padre === null} onClick={() => padre !== null && onIr(padre)}>Deshacer</button><button disabled={siguiente < 0} onClick={onRehacer}>Rehacer</button><select aria-label="Ir al paso" value={historial.activo} onChange={e => onIr(Number(e.target.value))}>{historial.pasos.map((p, i) => <option key={i} value={i}>{String(i + 1).padStart(2, '0')} · {p.titulo}</option>)}</select><a href="#variables-materia">Variables</a><button onClick={onNueva}>Reiniciar derivación</button></div></header>
    <div aria-live="polite" className={styles.srOnly}>Paso activo: {historial.activo + 1}</div>
    {historial.pasos.map((paso, i) => {
      const seleccionado = i === historial.activo;
      const origen = paso.origen === null ? undefined : historial.pasos[paso.origen];
      const relaciones = relacionesNuevas(paso, origen);
      return <article key={i} ref={seleccionado ? filaActual : undefined} className={styles.derivationRow} data-current={seleccionado} aria-label={`Paso ${i + 1}: ${paso.titulo}`} aria-current={seleccionado ? 'step' : undefined}>
        <span className={styles.rowNumber}>{String(i + 1).padStart(2, '0')}</span>
        <div className={styles.rowBody}>
          <header><h3>{paso.titulo}</h3><div><span>{FORMAS_MATERIA[paso.formulacion.vista]} · {unidadBalance(paso.formulacion)}</span>{seleccionado ? <span className={styles.currentStep}>Actual</span> : <button aria-label={`Continuar desde el paso ${i + 1}`} onClick={() => onIr(i)}>Continuar aquí</button>}{paso.origen !== null && <button className={styles.deleteStep} aria-label={`Eliminar paso ${i + 1}`} title="Eliminar este paso y los que dependen de él" onClick={() => onIr(paso.origen!)}>×</button>}</div></header>
          {paso.origen !== null && <button className={styles.branchOrigin} onClick={() => onIr(paso.origen!)}>Volver al paso {paso.origen + 1}</button>}
          <div id={`paso-${i + 1}`} className={styles.componentEquations} data-component-count={paso.formulacion.componentes?.length ?? 0}>{balancesComponentes(paso.formulacion).map(({ componente, latex }) => <section className={styles.componentEquation} key={componente?.id ?? 'i'} aria-label={componente ? `Balance de ${componente.nombre}` : 'Balance del componente i'}>{componente && <h4>{componente.nombre}<span>{componente.simbolo}</span></h4>}<div className={styles.math}><FormulaMateria latex={latex} lectura={componente ? `Ecuación de ${componente.nombre}` : 'Ecuación obtenida en este paso'} bloque /></div></section>)}</div>
          {relaciones.length > 0 && <div className={styles.stepRelations}>{relaciones.map(latex => <div key={latex}><FormulaMateria latex={latex} lectura="Relación introducida en este paso" bloque /></div>)}</div>}
        </div>
      </article>;
    })}
  </section>;
}
