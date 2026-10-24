import { englishLabel } from '../models/english';
import FormulaMateria from './FormulaMateria';
import { variablesMateria } from './catalogoMateria';
import type { VariableMateria } from './catalogoMateria';
import type { FormulacionMateria } from './recorridoMateria';
import styles from './motor.module.css';

function ListaVariables({ variables }: { variables: VariableMateria[] }) {
  return <dl>{variables.map(v => <div key={v.simbolo}><dt><FormulaMateria latex={v.simbolo} lectura={v.simbolo} /></dt><dd>{englishLabel(v.nombre)}<span>{v.unidad}</span></dd></div>)}</dl>;
}
export default function VariablesMateria({ formulacion }: { formulacion: FormulacionMateria }) {
  const grupos = variablesMateria(formulacion);
  return <section className={`${styles.symbols} ${styles.variablesSection}`} id="variables-materia" tabIndex={-1} aria-label="Variables by location">
    <header><h2>Variables</h2><span>For the selected step</span></header>
    <div className={styles.variableColumns}>
      <section aria-label="Control-volume variables"><h3>Control volume</h3>{grupos.volumen.map(g => <div key={g.nombre} className={styles.variableGroup}><h4>{englishLabel(g.nombre)}</h4><ListaVariables variables={g.variables} /></div>)}</section>
      <section aria-label="Stream and boundary variables"><h3>Streams and boundaries</h3>{grupos.corrientes.map(g => <div key={g.nombre} className={styles.variableGroup}><h4>{englishLabel(g.nombre)}</h4><ListaVariables variables={g.variables} /></div>)}</section>
    </div>
    <section className={styles.notationVariables}><h3>Geometry and notation</h3><ListaVariables variables={grupos.notacion} /></section>
  </section>;
}
