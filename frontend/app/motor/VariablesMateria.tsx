import FormulaMateria from './FormulaMateria';
import { variablesMateria } from './catalogoMateria';
import type { VariableMateria } from './catalogoMateria';
import type { FormulacionMateria } from './recorridoMateria';
import styles from './motor.module.css';

function ListaVariables({ variables }: { variables: VariableMateria[] }) {
  return <dl>{variables.map(v => <div key={v.simbolo}><dt><FormulaMateria latex={v.simbolo} lectura={v.simbolo} /></dt><dd>{v.nombre}<span>{v.unidad}</span></dd></div>)}</dl>;
}
export default function VariablesMateria({ formulacion }: { formulacion: FormulacionMateria }) {
  const grupos = variablesMateria(formulacion);
  return <section className={`${styles.symbols} ${styles.variablesSection}`} id="variables-materia" tabIndex={-1} aria-label="Variables por ubicación">
    <header><h2>Variables</h2><span>Del paso seleccionado</span></header>
    <div className={styles.variableColumns}>
      <section aria-label="Variables del volumen de control"><h3>Volumen de control</h3>{grupos.volumen.map(g => <div key={g.nombre} className={styles.variableGroup}><h4>{g.nombre}</h4><ListaVariables variables={g.variables} /></div>)}</section>
      <section aria-label="Variables de corrientes y frontera"><h3>Corrientes y frontera</h3>{grupos.corrientes.map(g => <div key={g.nombre} className={styles.variableGroup}><h4>{g.nombre}</h4><ListaVariables variables={g.variables} /></div>)}</section>
    </div>
    <section className={styles.notationVariables}><h3>Geometría y notación</h3><ListaVariables variables={grupos.notacion} /></section>
  </section>;
}
