import type { CompilationReport } from '../../motores/modelo/compilation';
import EquationRows from './EquationRows';
import { latexExpresion } from '../adimensionalizacion/exportar';
import styles from './workspace.module.css';
import FormulaMateria from '../motor/FormulaMateria';
import { englishLabel } from './english';

export default function CompilationSummary({ report }: { report: CompilationReport }) {
  const expression = (value: Parameters<typeof latexExpresion>[0]) => latexExpresion(value, report.symbolLabels);
  const symbol = (id: string) => report.symbolLabels?.[id] ? <FormulaMateria latex={report.symbolLabels[id]} lectura="Physical quantity"/> : id;
  return <section className={styles.compilation} aria-label="Compiled numerical problem">
    <p className={styles.kicker}>{report.formulation === 'scaled' ? 'Transformed formulation' : 'Physical formulation'} · {report.method}</p>
    <h3>What the solver executes</h3>
    <p>{report.variables.length} retained differential {report.variables.length === 1 ? 'variable' : 'variables'} · {report.equations.length ? `${report.equations.length} differential ${report.equations.length === 1 ? 'equation' : 'equations'}` : 'assembled physical relations'}{report.auxiliaryStates > 0 ? ` · ${report.auxiliaryStates} auxiliary diagnostic ${report.auxiliaryStates === 1 ? 'state' : 'states'}` : ''}</p>
    {report.auxiliaryPurpose&&<p>{report.auxiliaryPurpose}</p>}
    <p>{report.closureStrategy === 'nested_equilibrium' ? 'Thermodynamic UV/PH closures remain coupled through a local equilibrium solve at every RHS evaluation.' : 'The declared thermodynamic assumptions remain attached to the physical model.'}</p>
    {report.formulation === 'scaled' && <section aria-label="Selected transformation output"><h3>Variable maps from Transform</h3><p>Equivalence: {report.equivalence}. The equations below use these maps; Results reconstructs physical variables with the inverse.</p>{([{ title: 'Physical substitution', maps: report.direct }, { title: 'Inverse map', maps: report.inverse }]).map(({ title, maps }) => <EquationRows key={title} label={title} steps={maps.map(map => ({ id: map.simboloId, title, latex: `${report.symbolLabels?.[map.simboloId] ?? map.simboloId} = ${expression(map.expresion)}` }))}/>)}</section>}
    <EquationRows steps={report.equations.map(equation => ({ id: equation.id, title: `Executed equation · ${equation.id}`, latex: `${expression(equation.izquierda)} = ${expression(equation.derecha)}` }))}/>
    {report.systemEquations && <div aria-label="Compiled system equations"><EquationRows steps={report.systemEquations.map(equation => ({ ...equation, title: `${equation.family} · ${equation.id}` }))}/><p>These symbolic relations come from the admitted physical compiler. The strategy and validity limits below describe which quantities are integrated, evaluated or reconstructed.</p></div>}
    {report.equationWorkbench&&<section aria-label="Equation operations from Model"><h3>Equation operations from Model</h3><p>These are replayed mathematical consequences of the source laws. They retain their premises and do not add independent solver states.</p><EquationRows steps={report.equationWorkbench.equations.filter(row=>row.id.startsWith('operation.')).map(row=>({...row,description:`${row.family} · ${row.kind}${row.dependent?' · dependent consequence':''}`}))}/></section>}
    {report.strategy && <>
      <h3>Methods for this compiled problem</h3>
      <div className={styles.compilationTable}><table><thead><tr><th>Method</th><th>Compatibility</th><th>Mathematical treatment</th></tr></thead><tbody>{report.strategy.methods.map(method => <tr key={method.id}><td>{method.id}{report.method === method.id ? ' · selected' : ''}</td><td>{method.available ? 'Available' : 'Not connected'}</td><td>{method.reason}</td></tr>)}</tbody></table></div>
      <h3 className={styles.planTitle}>Mathematical solution strategy</h3>
      <p>{report.strategy.scope}</p>
      <EquationRows label="Mathematical solution strategy steps" steps={report.strategy.steps}/>
    </>}
    <div className={styles.compilationTable}><table><thead><tr><th>Solver variable</th><th>Physical variable</th><th>Scale [physical SI unit]</th><th>Absolute tolerance [solver unit]</th></tr></thead><tbody>{report.variables.map(variable => <tr key={variable.id}><td>{symbol(variable.id)} [{variable.unit}]</td><td>{symbol(variable.sourceId)} [{variable.physicalUnit}]</td><td>{variable.scaleSI.toPrecision(6)}</td><td>{variable.absoluteTolerance.toExponential(3)}</td></tr>)}</tbody></table></div>
    <p>Time: {symbol(report.time.id)} · scale {report.time.scaleSI.toPrecision(6)} s · final solver time {report.time.finalTime.toPrecision(6)} · physical final time {report.time.physicalFinalTime.toPrecision(6)} s.</p>
    <details className={styles.transformDetails}><summary>Parameters and derivation provenance</summary>
      {report.momentumDerivation?.map(entry=><div key={entry.volumeId}><p><strong>Momentum derivation · {entry.volumeId}</strong> · {entry.operationIds.length} replayed operations.</p><p className={styles.signature}>Journal signature: {entry.signature}</p></div>)}
      {report.groups && <EquationRows label="Dimensionless groups" steps={report.groups.map(group => ({ id: group.id, title: `Dimensionless group · ${group.id}`, latex: `${group.id} = ${expression(group.definition)}`, description: `Value: ${group.value === null ? 'Unavailable' : group.value.toPrecision(8)}` }))}/>}
      {!!report.parameters?.length && <details><summary>Evaluated parameters and scales</summary>{report.parameters.map(parameter => <p key={parameter.id}>{symbol(parameter.id)} = {parameter.value.toPrecision(8)} {parameter.unit}</p>)}</details>}
      {report.relations?.map(relation => <p key={relation.id}>{relation.id} · {englishLabel(relation.descripcion)}</p>)}
      {report.materialDerivation?.map(entry => <div key={entry.volumeId}><p><strong>Material derivation · {entry.volumeId}</strong> · {entry.operationIds.length} replayed operations · {entry.origin === 'reviewed_rebuild' ? 'explicitly rebuilt from the fundamental law' : 'recorded history'}.</p><p>Conservation relations: {entry.relationIds.join(', ')}.</p><p className={styles.signature}>Journal signature: {entry.signature}</p></div>)}
      {report.energyDerivation?.map(entry => <div key={entry.volumeId}><p><strong>Energy derivation · {entry.volumeId}</strong> · {entry.operationIds.length} replayed operations · {entry.origin === 'reviewed_rebuild' ? 'explicitly rebuilt from the fundamental law' : 'recorded history'}.</p><p>First-law relations: {entry.relationIds.join(', ')}.</p><p className={styles.signature}>Journal signature: {entry.signature}</p></div>)}
      {report.thermodynamicDerivation?.map(entry => <div key={entry.volumeId}><p><strong>Thermodynamic derivation · {entry.volumeId}</strong> · {entry.operationIds.length} replayed operations · {entry.origin === 'reviewed_rebuild' ? 'explicitly rebuilt from the fundamental law' : 'recorded history'}.</p><p>State relations: {entry.relationIds.join(', ')}.</p><p className={styles.signature}>Journal signature: {entry.signature}</p></div>)}
      <p>{report.matrix}</p>{report.limits && <p>{report.limits}</p>}
      <p>Source: {report.sourceModelId}{report.sourceRevision !== null ? ` · revision ${report.sourceRevision}` : ''}. No physical variable was removed merely because an additive term became zero.</p>
      <p className={styles.signature}>Compilation signature: {report.signature}</p>
    </details>
  </section>;
}
