import FormulaLatex from '../flowsheet/FormulaLatex';
import styles from './motor.module.css';

/** KaTeX inline breaks only between top-level terms when available width runs out.
 * Displaystyle preserves legible fractions without forcing one row per term.
 */
export default function FormulaMateria({ latex, lectura, bloque = false }: { latex: string; lectura: string; bloque?: boolean }) {
  return bloque
    ? <div className={styles.horizontalEquation}><FormulaLatex latex={String.raw`\displaystyle ${latex}`} lectura={lectura} /></div>
    : <FormulaLatex latex={latex} lectura={lectura} />;
}
