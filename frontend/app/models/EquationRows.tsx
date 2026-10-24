import FormulaMateria from '../motor/FormulaMateria';
import worksheet from '../motor/motor.module.css';
import styles from './workspace.module.css';
import type { ReactNode } from 'react';

/** Read-only equations use the same rows, spacing and math renderer as Model. */
export default function EquationRows({ steps, label = 'Mathematical equations' }: {
  steps: { id: string; title: string; latex: string; description?: string; anchor?: string; annotation?: ReactNode; derivation?:{rule:string;inputIds:string[];inputTitles?:string[];beforeLatex:string[];assumptions:string[];branches?:{latex:string;admitted:boolean}[]} }[];
  label?: string;
}) {
  return <div className={`${worksheet.worksheet} ${styles.equationRows}`} aria-label={label} data-equation-rows="canonical">
    {steps.map((step, index) => <article key={step.id} id={step.anchor} className={worksheet.derivationRow} aria-label={`Equation ${index + 1}: ${step.title}`}>
      <span className={worksheet.rowNumber}>{String(index + 1).padStart(2, '0')}</span>
      <div className={worksheet.rowBody}>
        <header><h3 className={styles.equationRowTitle}>{step.title}</h3></header>
        {step.description && <p>{step.description}</p>}
        {!!step.derivation?.assumptions.length&&<p>Assumptions and validity: {step.derivation.assumptions.map((condition,index)=><span key={index}>{index>0&&'; '}{condition.includes('\\')?<FormulaMateria latex={condition} lectura="Validity condition"/>:condition}</span>)}</p>}
        <div className={worksheet.math}><FormulaMateria bloque latex={step.latex} lectura={step.title}/></div>
        {step.derivation&&step.derivation.inputIds.length>0&&<details><summary>How this follows · {step.derivation.rule.replaceAll('_',' ')}</summary><p>Starting from: {(step.derivation.inputTitles??step.derivation.inputIds).join('; ')}</p>{step.derivation.beforeLatex.map((latex,index)=><FormulaMateria key={index} bloque latex={latex} lectura="Equation before this operation"/>)}</details>}
        {!!step.derivation?.branches?.length&&<details><summary>Branch selection evidence</summary>{step.derivation.branches.map((branch,index)=><div key={index}><p>{branch.admitted?'Admitted by the recorded domains':'Excluded by the recorded domains'}</p><FormulaMateria bloque latex={branch.latex} lectura="Polynomial branch"/></div>)}</details>}
        {step.annotation}
      </div>
    </article>)}
  </div>;
}
