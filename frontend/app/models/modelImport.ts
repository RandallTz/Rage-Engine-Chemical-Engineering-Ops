import {leerModeloComun} from '../../motores/modelo/lector';
import type { HojaMotor } from '../motor/hojasMotor';
import { normalizarHoja } from '../motor/hojasMotor';
import { auditModelDerivation } from './modelDerivationAudit';
import { modelRequest } from './modelRequest';

/** Import data through the common path, never an example-specific authoring mode. */
export async function importModelFile(value: unknown): Promise<HojaMotor> {
  const document = value as { format?: string; version?: number; model?: HojaMotor };
  if (!document || document.format !== 'rage.model-file' || document.version !== 1 || !document.model) throw new Error('Expected a rage.model-file version 1 document.');
  const candidate = document.model;
  if (candidate.version !== 1 || typeof candidate.id !== 'string' || typeof candidate.nombre !== 'string' || !candidate.nombre.trim() || !Array.isArray(candidate.historial?.pasos) || !candidate.historial.pasos.length || !Number.isInteger(candidate.historial.activo) || !candidate.historial.pasos[candidate.historial.activo] || !candidate.config || !Array.isArray(candidate.graficas)) throw new Error('Invalid model document.');
  const model = normalizarHoja(structuredClone(candidate));
  if(model.commonModel)leerModeloComun(model.commonModel);
  if (!model.commonModel && auditModelDerivation(model).status === 'needs_review') throw new Error('The imported model needs recorded deductions. Review its operation journals before importing.');
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8004'}/modelo/formulation-summary`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(modelRequest(model)), cache: 'no-store', signal: AbortSignal.timeout(60000) });
  const summary = await response.json();
  if (!response.ok || summary?.format !== 'rage.formulation-summary' || summary.version !== 1) throw new Error(summary?.detail?.message ?? 'The Engine rejected the imported formulation.');
  // A copy cannot inherit cached execution, a removal marker or a selected map tied to another ID.
  return { ...model, id: crypto.randomUUID(), actualizada: new Date().toISOString(), removedAt: undefined, archivada: false, transformation: undefined, derivedSelection:undefined, resultado: undefined, resultadoRef: undefined };
}
