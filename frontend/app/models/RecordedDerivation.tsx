'use client';

import { useId, useRef, type ReactNode } from 'react';
import ModelWorksheet from './ModelWorksheet';
import FormulaLatex from '../motor/FormulaMateria';
import styles from '../motor/motor.module.css';

/** The existing worksheet layout, with mathematics supplied by Python. */
export default function RecordedDerivation({ family, steps, notes, sidebar, variables, result, preview=false, startDescription, pending, canUndo, undo, start, restore, error, rebuilt }: {
  family: 'Material' | 'Energy' | 'Thermodynamic' | 'Momentum';
  steps?: { id: string; title: string; latex: string; derivation?:{rule:string;inputIds:string[];beforeLatex:string[];assumptions:string[]} }[]; notes?: string[];
  sidebar: ReactNode; variables?: ReactNode; result?:ReactNode; preview?:boolean; startDescription?:string; pending: boolean; canUndo: boolean;
  undo: () => void; start?: () => void; restore?: () => void; error: string; rebuilt: boolean;
}) {
  const id = useId(), rows = useRef<(HTMLElement | null)[]>([]);
  return <ModelWorksheet family={family==='Material'?'materia':family==='Energy'?'energia':family==='Momentum'?'momento':'termodinamica'} label={`${family} deduction`} assumptions={<>{sidebar}<div className={styles.integrationBridge}>
    {start&&<><p>{startDescription??`Start the ${family.toLowerCase()} journal explicitly from its fundamental law. The earlier formulation remains available to restore.`}</p><button disabled={pending} onClick={start}>Start {family.toLowerCase()} derivation</button></>}
    <button disabled={pending||!canUndo} onClick={undo}>Undo last {family.toLowerCase()} assumption</button>
    {restore&&<button disabled={pending} onClick={restore}>Restore previous {family.toLowerCase()} formulation</button>}
    {error&&<p role="alert">{error}</p>}
    {rebuilt&&<p>Explicit rebuild · the original history is preserved separately.</p>}
  </div></>} variables={variables}>
      {family === 'Material' && <article className={styles.equation}><header><h2>Fundamental balance</h2></header><div className={styles.wordBalance}>Accumulation = Inflow − Outflow + Generation − Consumption</div></article>}
      <section className={styles.worksheet} aria-label="Mathematical development">
        <header className={styles.sheetToolbar}><h2>Mathematical development</h2><div>
          <button disabled={!steps?.length} onClick={() => rows.current[0]?.scrollIntoView({ block: 'nearest' })}>Home</button>
          <button disabled={pending || !canUndo} onClick={undo}>Undo last deduction</button>
          <select aria-label={`View ${family.toLowerCase()} development step`} defaultValue="" key={steps?.at(-1)?.id ?? 'loading'} onChange={event => rows.current[Number(event.target.value)]?.scrollIntoView({ block: 'nearest' })}>
            <option value="" disabled>View a step</option>{steps?.map((step, index) => <option key={step.id} value={index}>{String(index + 1).padStart(2, '0')} · {step.title}</option>)}
          </select>
          {variables && <a href="#variables-materia">Variables</a>}
          {restore && <button disabled={pending} onClick={restore}>Restore previous {family.toLowerCase()} formulation</button>}
        </div></header>
        {rebuilt && <p className={styles.groupHint}>Explicit rebuild · newly recorded operations; the original editing history is preserved separately.</p>}
        {start && <div className={styles.integrationBridge}><p>{startDescription??`This saved formulation has no recorded ${family.toLowerCase()} derivation. Start explicitly from the fundamental law. The previous formulation remains available to restore.`}</p><button className={styles.integrateButton} disabled={pending} onClick={start}>Start {family.toLowerCase()} derivation</button></div>}
        {(!start||preview)&&(!steps ? <p role="status">Loading mathematical development…</p> : steps.map((step, index) => <article key={step.id} id={`${id}-${index}`} ref={element => { rows.current[index] = element; }} className={styles.derivationRow} data-current={index === steps.length - 1} aria-label={`Step ${index + 1}: ${step.title}`}>
            <span className={styles.rowNumber}>{String(index + 1).padStart(2, '0')}</span><div className={styles.rowBody}><header><h3>{step.title}</h3>{index === steps.length - 1 && <span className={styles.currentStep}>Current</span>}</header><div className={styles.math}><FormulaLatex latex={step.latex} lectura={step.title} bloque/></div>{step.derivation&&<details><summary>Equation operation · {step.derivation.rule}</summary><p>{step.derivation.inputIds.length?`Input equations: ${step.derivation.inputIds.join(", ")}`:"Declared physical law or definition"}</p>{step.derivation.beforeLatex.map((latex,i)=><FormulaLatex key={i} latex={latex} lectura="Equation before this operation" bloque/>)}{step.derivation.assumptions.length>0&&<p>Assumptions and validity: {step.derivation.assumptions.join("; ")}</p>}</details>}</div>
          </article>))}
        {result}
        {notes?.length ? <details className={styles.integrationBridge}><summary>Mathematical scope</summary>{notes.map(note => <p key={note}>{note}</p>)}</details> : null}
        {error && <p role="alert">{error}</p>}
      </section>
  </ModelWorksheet>;
}
