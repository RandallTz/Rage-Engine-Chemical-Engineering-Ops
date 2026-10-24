'use client';
import Link from 'next/link';
import DerivedExecution from './DerivedExecution';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useHojasMotor } from '../motor/useHojasMotor';
import { guardarHoja, leerHojas } from '../motor/hojasMotor';
import { analizarHoja, transformationSourceSignature } from '../motor/modeloHojaMotor';
import { balancesHoja } from '../motor/seleccionBalances';
import { transformationDocument } from './transformationSelection';
import FormulationExecution from './FormulationExecution';
import { consultarNucleo } from '../adimensionalizacion/clienteNucleo';
import { formulacionesDe, prepararSolicitud } from '../adimensionalizacion/lecturaNucleo';
import { claveCalculo, guardarCalculo, leerCalculo } from '../adimensionalizacion/resultadosAdim';
import type { RespuestaNucleo, SolicitudNucleo } from '../adimensionalizacion/contratoNucleo';
import { latexExpresion } from '../adimensionalizacion/exportar';
import EquationRows from './EquationRows';
import EcuacionesFinales from '../motor/EcuacionesFinales';
import { modelUrl } from './workflow';
import styles from './workspace.module.css';
import DeducedModelSummary from './DeducedModelSummary';

type Calculation = { signature: string; pages: { respuesta: RespuestaNucleo; solicitud: SolicitudNucleo }[] };
export default function TransformWorkspace({ id }: { id: string }) {
  const model = useHojasMotor().find(item => item.id === id);
  const signature = model ? transformationSourceSignature(model) : '';
  const document = useMemo(() => {
    if (!model || model.commonModel || model.hydraulicNetwork || balancesHoja(model).energia) return null;
    return transformationDocument(model);
  }, [model]);
  const [calculation, setCalculation] = useState<Calculation | null>(null), [selected, setSelected] = useState(0), [error, setError] = useState(''), [busy, setBusy] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => {
    let active = true;
    controller.current?.abort();
    if (document) leerCalculo(document, signature).then(saved => {
      if (active && saved?.paginas.length) setCalculation({ signature, pages: saved.paginas });
    }).catch(() => { if (active) setError('The saved transformation could not be loaded. Calculate it again.'); });
    return () => { active = false; controller.current?.abort(); };
  }, [document, signature]);
  if (!model) return null;
  if(model.commonModel)return <><DeducedModelSummary model={model}/><DerivedExecution model={model}/></>;
  const analysis = model.redTermodinamica||model.hydraulicNetwork ? null : analizarHoja(model);
  const spatial = analysis?.modo === '1d' && analysis.bloqueos.length === 0;
  const result = calculation?.signature === signature ? calculation : null;
  const response = result?.pages.at(-1)?.respuesta;
  const forms = result ? result.pages.flatMap(page => formulacionesDe(page.respuesta)) : [];
  const formulation = forms[Math.min(selected, forms.length - 1)];
  const formulationResponse = result?.pages.find(page => formulacionesDe(page.respuesta).includes(formulation))?.respuesta;
  async function calculate(from = 0) {
    if (!document) return;
    const abort = new AbortController(); controller.current?.abort(); controller.current = abort;
    const request = prepararSolicitud(document, { presupuesto: 150, gruposPi: true, ...(from ? { desde: from } : {}) });
    setBusy(true); setError('');
    try {
      const response = await consultarNucleo(request, abort.signal);
      const current = leerHojas().find(item => item.id === id);
      if (abort.signal.aborted || !current || transformationSourceSignature(current) !== signature) return;
      const pages = [...(from && calculation?.signature === signature ? calculation.pages : []), { solicitud: request, respuesta: response }];
      setCalculation({ signature, pages }); if (!from) setSelected(0);
      try { await guardarCalculo(document.id, { claveDocumento: claveCalculo(document), fuente: signature, documento: document, paginas: pages }); }
      catch { setError('Calculated, but the transformation could not be saved in this browser.'); }
    } catch (failure) { if (!abort.signal.aborted) setError(failure instanceof Error ? failure.message : 'The transformation could not be calculated.'); }
    finally { if (controller.current === abort) { setBusy(false); controller.current = null; } }
  }
  function setCells(value: number) {
    if (!Number.isInteger(value) || value < 4 || value > 160) { setError('Choose between 4 and 160 cells.'); return; }
    try { const current = leerHojas().find(item => item.id === id); if (current && current.config.celdas !== value) guardarHoja({ ...current, config: { ...current.config, celdas: value }, resultado: undefined, resultadoRef: undefined }); setError(''); }
    catch { setError('The spatial discretization could not be saved.'); }
  }
  return <>
    <DeducedModelSummary model={model}/>
    <div className={styles.notice}>Transformations are optional. You can return here after entering data in Solve. Physical assumptions remain in Model.</div>
    <section className={styles.executionSelection} aria-label="Selected numerical formulation"><h2>Selected numerical formulation</h2><p>{model.transformation ? `${model.transformation.label}${model.transformation.sourceSignature !== signature ? ' · outdated after a physical input change' : ' · connected to Solve'}` : 'Physical formulation · no scaling selected'}</p>{model.transformation && <button className={styles.secondary} onClick={() => { try { const current = leerHojas().find(item => item.id === id); if (current) guardarHoja({ ...current, transformation: undefined, resultado: undefined, resultadoRef: undefined }); } catch { setError('The formulation selection could not be saved.'); } }}>Use physical formulation</button>}</section>
    <div className={styles.techniques}>
      <section className={styles.technique}><span className={styles.availability}>CHANGE OF SCALE</span><h2>Nondimensionalization</h2><p>Find dimensionless formulations and groups. Inspect substitutions, algebraic development and equivalence checks from the mathematical core.</p>{document ? <button className={styles.primary} disabled={busy} onClick={() => calculate()}>{busy ? 'Calculating formulations…' : 'Nondimensionalize'}</button> : <div><p>{model.redTermodinamica || model.ensamblaje || balancesHoja(model).energia ? 'The current scaling adapter supports single-domain matter models. Energy and thermodynamic networks are not yet connected to this technique.' : 'Complete the required data in Solve to use the current scaling adapter. You can return here before running the model.'}</p><Link className={styles.secondary} href={modelUrl(id, 'solve')}>Review data in Solve →</Link></div>}</section>
      <section className={styles.technique}><span className={styles.availability}>NUMERICAL APPROXIMATION</span><h2>Spatial discretization</h2><p>Replace spatial fields with a finite set of states. Configure the mesh here and the time integrator in Solve.</p>{spatial ? <><label htmlFor="mesh-cells">Finite-volume cells<input key={model.config.celdas} id="mesh-cells" type="number" min={4} max={160} defaultValue={model.config.celdas} onBlur={event => setCells(Number(event.target.value))}/></label><small>Fixed 1D Cartesian mesh · existing finite-volume solver. The common Python discretization engine is pending.</small></> : <small>No supported spatial field is declared. Time-only models do not need a mesh.</small>}</section>
      <section className={styles.technique}><span className={styles.availability}>EXACT REFORMULATION</span><h2>Variable substitutions</h2><p>The core supports affine and declared invertible nonlinear maps. A dedicated editor on this model is not connected yet.</p><small>Core available · model editor pending</small></section>
      <section className={styles.technique}><span className={styles.availability}>OTHER MATHEMATICAL TECHNIQUES</span><h2>Reduction & reformulation</h2><p>Order reduction, operator reformulation and other mathematical techniques belong here. Each must declare its validity and distinguish exact equivalence from approximation.</p><small>Additional techniques will appear as their engines are integrated.</small></section>
    </div>
    {busy && <div className={styles.loading} role="status" aria-label="Calculating transformations"><div/><div/></div>}
    {error && <p className={styles.error} role="alert">{error}</p>}
    {result && response && <section className={styles.transformationResult}><h2>Dimensionless formulations</h2>{response.diagnosticos.length > 0 && <p className={styles.notice}>{response.diagnosticos.map(item => item.mensaje).join(' · ')}</p>}{!forms.length && <p className={styles.notice}>No formulation was returned. Review the dimensional data and diagnostics.</p>}
      {response.cobertura && <p className={styles.notice}>{response.cobertura.completa ? 'Search complete within the core’s declared normalization family.' : 'The search is partial; additional formulations may exist.'}{typeof response.cobertura.siguiente === 'number' && <button className={styles.secondary} disabled={busy} onClick={() => calculate(response.cobertura!.siguiente!)}>Find more formulations →</button>}</p>}
      <nav className={styles.formulaSelector} aria-label="Dimensionless formulations">{forms.map((form, index) => <button key={index} aria-pressed={formulation === form} onClick={() => setSelected(index)}>Form {index + 1} · {form.libres.length} free {form.libres.length === 1 ? 'scale' : 'scales'}</button>)}</nav>
      {formulation && <><p className={styles.notice}>{formulation.equivalencia.estado === 'demostrada' ? 'Equivalence verified by the core within its reported scope.' : 'Equivalence has not been demonstrated.'} Previewing a form does not change execution. Use the selection below to connect it to Solve.</p><EquationRows label="Dimensionless equations" steps={formulation.ecuaciones.map(equation => ({ id: equation.igualdad.id, title: `Dimensionless equation · ${equation.igualdad.id}`, latex: `${latexExpresion(equation.igualdad.izquierda)} = ${latexExpresion(equation.igualdad.derecha)}` }))}/>
        {formulationResponse && <FormulationExecution key={JSON.stringify([formulationResponse.vinculo?.firma, selected])} model={model} response={formulationResponse} formulation={formulation} label={`Form ${Math.min(selected, forms.length - 1) + 1}`} spatial={analysis?.modo === '1d'}/>}
        <details className={styles.transformDetails}><summary>Substitutions and dimensionless groups</summary><EquationRows label="Substitutions and dimensionless groups" steps={[
          ...formulation.directa.map(item => ({ id: `substitution-${item.simboloId}`, title: `Variable substitution · ${item.simboloId}`, latex: `${item.simboloId} = ${latexExpresion(item.expresion)}` })),
          ...formulation.grupos.map(group => ({ id: `group-${group.id}`, title: `Dimensionless group · ${group.id}`, latex: `${group.id} = ${latexExpresion(group.definicion)}` })),
        ]}/></details>
        <details className={styles.transformDetails}><summary>Mathematical and algebraic development · {formulation.desarrollo.length} steps</summary><EquationRows label="Mathematical and algebraic development" steps={formulation.desarrollo.map(step => ({ id: step.id, title: step.regla, latex: step.despues.tipo === 'expresion' ? latexExpresion(step.despues.expresion) : `${latexExpresion(step.despues.igualdad.izquierda)} = ${latexExpresion(step.despues.igualdad.derecha)}`, description: step.justificacion }))}/></details>
      </>}
    </section>}
    {!model.redTermodinamica && <details className={styles.transformDetails}><summary>Original physical formulation</summary><EcuacionesFinales hoja={model}/></details>}
  </>;
}
