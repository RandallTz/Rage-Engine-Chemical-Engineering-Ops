/** Reversible document edits. Scientific development is supplied by Python. */
import type { SolicitudEnsamblajeV2, VolumenV2 } from './contratoEnsamblajeV2';
import { journalInRequest, journalMatches, readMaterialJournal } from './materialDerivation';
import type { MaterialJournal, MaterialState } from './materialDerivation';

type Metadata = Record<string, unknown> & { materialDerivation?: MaterialJournal;
  previousMaterialFormulations?: Record<string, VolumenV2['formulacionMateria']> };
const metadata = (request: SolicitudEnsamblajeV2): Metadata => request.derivacion && typeof request.derivacion === 'object' && !Array.isArray(request.derivacion) ? request.derivacion as Metadata : {};
export const hasPreviousMaterialFormulation = (request: SolicitudEnsamblajeV2, volumeId: string) => !!metadata(request).previousMaterialFormulations?.[volumeId];

export function replaceNetworkMaterialJournal(request: SolicitudEnsamblajeV2, volumeId: string, journal: MaterialJournal,
  formulation: MaterialState, starting: boolean, expected: string): void {
  if (JSON.stringify(request) !== expected) throw new Error('The model changed while the deduction was being developed. Apply it again.');
  readMaterialJournal(journal);
  const volume = request.volumenes.find(item => item.id === volumeId);
  if (!volume || !journal.volumes[volumeId] || !journalMatches(journal.volumes[volumeId], formulation)) throw new Error('The returned material derivation does not match this volume.');
  const meta = metadata(request);
  if (starting) {
    if (journalInRequest(request.derivacion)?.volumes[volumeId]) throw new Error('A material journal already exists for this volume.');
    meta.previousMaterialFormulations = { ...meta.previousMaterialFormulations, [volumeId]: structuredClone(volume.formulacionMateria) };
  }
  volume.formulacionMateria = { ...formulation, ...(volume.formulacionMateria.reglasEstado ? { reglasEstado: volume.formulacionMateria.reglasEstado } : {}) };
  request.derivacion = { ...meta, materialDerivation: journal };
}

export function restoreNetworkMaterialFormulation(request: SolicitudEnsamblajeV2, volumeId: string): void {
  const meta = metadata(request), volume = request.volumenes.find(item => item.id === volumeId), previous = meta.previousMaterialFormulations?.[volumeId];
  if (!volume || !previous) throw new Error('No previous material formulation is stored.');
  volume.formulacionMateria = structuredClone(previous);
  delete meta.materialDerivation?.volumes[volumeId];
  if (meta.materialDerivation && !Object.keys(meta.materialDerivation.volumes).length) delete meta.materialDerivation;
  delete meta.previousMaterialFormulations?.[volumeId];
  if (meta.previousMaterialFormulations && !Object.keys(meta.previousMaterialFormulations).length) delete meta.previousMaterialFormulations;
  request.derivacion = meta;
}
