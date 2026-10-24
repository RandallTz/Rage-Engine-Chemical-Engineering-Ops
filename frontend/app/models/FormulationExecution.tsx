'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import type { HojaMotor } from '../motor/hojasMotor';
import { guardarHoja, leerHojas } from '../motor/hojasMotor';
import { transformationSourceSignature } from '../motor/modeloHojaMotor';
import type { FormulacionNucleo, RespuestaNucleo } from '../adimensionalizacion/contratoNucleo';
import { selectFormulation, selectedTransformedModel } from './transformationSelection';
import { describeCompilation } from '../../motores/modelo/servicioModelo';
import type { TransformExecution } from '../../motores/modelo/contrato';
import { modelUrl } from './workflow';
import styles from './workspace.module.css';

export default function FormulationExecution({ model, response, formulation, label, spatial }: {
  model: HojaMotor; response: RespuestaNucleo; formulation: FormulacionNucleo; label: string; spatial: boolean;
}) {
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);
  const controller = useRef<AbortController | null>(null);
  useEffect(() => () => controller.current?.abort(), []);
  const supported = !spatial && formulation.equivalencia.estado === 'demostrada'
    && formulation.transformaciones.every(map => map.familia === 'multiplicativa');
  async function select(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const inputs = new FormData(event.currentTarget);
    const freeScales: TransformExecution['freeScales'] = {};
    for (const id of formulation.libres) {
      const value = Number(inputs.get(`value:${id}`));
      if (!(value > 0) || !Number.isFinite(value)) { setError(`Enter a positive finite value for ${id}.`); return; }
      freeScales[id] = { value, unit: String(inputs.get(`unit:${id}`) ?? '').trim() };
    }
    const source = transformationSourceSignature(model);
    const abort = new AbortController(); controller.current?.abort(); controller.current = abort;
    setBusy(true); setError(''); setSaved(false);
    try {
      const selection = selectFormulation(model, response, formulation, label, freeScales);
      const candidate = { ...model, transformation: selection };
      await describeCompilation(selectedTransformedModel(candidate), abort.signal);
      if (abort.signal.aborted) return;
      const current = leerHojas().find(item => item.id === model.id);
      if (!current || transformationSourceSignature(current) !== source) throw new Error('The physical model changed while validating. Recalculate the transformation.');
      if (JSON.stringify(current.transformation) !== JSON.stringify(model.transformation)) throw new Error('The execution selection changed during validation. Select this formulation again to replace it.');
      guardarHoja({ ...current, transformation: selection, resultado: undefined, resultadoRef: undefined });
      setSaved(true);
    } catch (failure) { if (!abort.signal.aborted) setError(failure instanceof Error ? failure.message : 'The formulation could not be selected.'); }
    finally { if (controller.current === abort) { setBusy(false); controller.current = null; } }
  }
  if (!supported) return <p className={styles.notice}>{spatial ? 'This spatial formulation can be inspected here. Scaled spatial execution is not connected yet; the physical formulation uses the mesh above.' : 'This map remains available for inspection. Execution currently supports certified constant multiplicative maps.'}</p>;
  return <form className={styles.executionSelection} onSubmit={select}>
    <h3>Use this formulation in Solve</h3>
    <p>Set the remaining free scales. Python checks their units, regenerates the equations and maps the physical tolerances.</p>
    {formulation.libres.map(id => {
      const symbol = formulation.simbolos.find(symbol => symbol.id === id);
      const original = response.formaBase?.escalas.find(scale => scale.simboloId === symbol?.variableId);
      const existing = model.transformation?.config.execution.freeScales[id];
      return <div className={styles.scaleEntry} key={id}>
        <label>{id} · scale for {symbol?.variableId}<input name={`value:${id}`} aria-label={`Value of ${id}`} type="number" step="any" required min="0" defaultValue={existing?.value ?? ''}/></label>
        <label>Unit<input name={`unit:${id}`} aria-label={`Unit of ${id}`} defaultValue={existing?.unit ?? ''} placeholder={original?.dimension && !Object.keys(original.dimension).length ? '1' : 'Enter a compatible unit'}/></label>
      </div>;
    })}
    <button type="submit" className={styles.primary} disabled={busy}>{busy ? 'Checking compilation…' : 'Use in Solve'}</button>
    {error && <p className={styles.error} role="alert">{error}</p>}
    {saved && <p role="status">Selected for execution. <Link href={modelUrl(model.id, 'solve')}>Continue to Solve →</Link></p>}
  </form>;
}
