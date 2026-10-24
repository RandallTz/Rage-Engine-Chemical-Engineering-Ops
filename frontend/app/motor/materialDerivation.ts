/** Versioned operation journal. Python owns mathematical replay and development. */
import type { FormulacionMateria, RecorridoMateria } from './recorridoMateria';
import { iniciarRecorrido } from './recorridoMateria';

export type MaterialState = Omit<FormulacionMateria, 'componentes' | 'fronteras' | 'reglasEstado'>;
export type MaterialOperation = { id: string; title: string; changes: Partial<MaterialState> };
export type MaterialVolumeJournal = { origin: 'recorded' | 'reviewed_rebuild'; operations: MaterialOperation[] };
export type MaterialJournal = { format: 'rage.material-derivation'; version: 1; volumes: Record<string, MaterialVolumeJournal> };
export type MaterialDevelopment = { format: 'rage.material-development'; version: 1; volumeId: string;
  origin: MaterialVolumeJournal['origin']; formulation: MaterialState;
  steps: { id: string; title: string; latex: string }[]; notes: string[] };
export const emptyMaterialJournal = (): MaterialJournal => ({ format: 'rage.material-derivation', version: 1, volumes: {} });

export function materialState(formulation: Partial<FormulacionMateria>): Partial<MaterialState> {
  return structuredClone(Object.fromEntries(Object.entries(formulation).filter(([key]) => !['componentes', 'fronteras', 'reglasEstado'].includes(key))));
}

function exactObject(value: unknown, keys: string[]): asserts value is Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).length !== keys.length || keys.some(key => !Object.hasOwn(value, key))) throw new Error('Unknown or missing material journal fields.');
}
export function readMaterialJournal(value: unknown): MaterialJournal {
  exactObject(value, ['format', 'version', 'volumes']);
  if (value.format !== 'rage.material-derivation' || value.version !== 1 || !value.volumes || typeof value.volumes !== 'object' || Array.isArray(value.volumes) || Object.keys(value.volumes).length > 160) throw new Error('Unsupported material journal.');
  const baseline = materialState(iniciarRecorrido().pasos[0].formulacion);
  const fieldBooleans = ['sinReaccion', 'sinGeneracion', 'sinConsumo', 'sinDifusion', 'sinConveccion', 'estacionario', 'generacionUniforme', 'consumoUniforme'];
  for (const [owner, entry] of Object.entries(value.volumes)) {
    exactObject(entry, ['origin', 'operations']);
    if (!owner.trim() || !['recorded', 'reviewed_rebuild'].includes(entry.origin as string) || !Array.isArray(entry.operations) || entry.operations.length > 400) throw new Error('Invalid material volume journal.');
    const ids = new Set<string>();
    for (const operation of entry.operations) {
      exactObject(operation, ['id', 'title', 'changes']);
      if (typeof operation.id !== 'string' || !operation.id.trim() || ids.has(operation.id) || typeof operation.title !== 'string' || !operation.title.trim()) throw new Error('Invalid or repeated material operation ID.');
      ids.add(operation.id);
      const changes = operation.changes;
      if (!changes || typeof changes !== 'object' || Array.isArray(changes) || !Object.keys(changes).length) throw new Error('A material operation needs declared changes.');
      for (const [key, item] of Object.entries(changes)) {
        if (!Object.hasOwn(baseline, key)) throw new Error('Unknown material operation field: ' + key);
        if (key === 'campo') {
          if (!item || typeof item !== 'object' || Array.isArray(item)) throw new Error('Invalid material field flags.');
          for (const [name, flag] of Object.entries(item)) if (name === 'difusion' ? !['flujo', 'fick', 'laplaciano'].includes(flag as string) : !fieldBooleans.includes(name) || typeof flag !== 'boolean') throw new Error('Invalid material field flag.');
        } else if (key === 'invariantes') {
          if (!Array.isArray(item) || item.length !== 3 || item.some(flag => typeof flag !== 'boolean')) throw new Error('Three boolean invariances are required.');
        } else if (key === 'vista' || key === 'coordenadas') {
          if (!(key === 'vista' ? ['campo', 'integral', 'cantidad'] : ['cartesianas', 'cilindricas', 'esfericas']).includes(item as string)) throw new Error('Unknown material representation.');
        } else if (typeof item !== 'boolean') throw new Error('Material flags must be booleans.');
      }
    }
  }
  return value as unknown as MaterialJournal;
}

/** Serialize actual legacy operations, never infer a history from final flags. */
export function journalFromHistory(history: RecorridoMateria): MaterialVolumeJournal {
  const path: number[] = [], seen = new Set<number>();
  let index: number | null = history.activo;
  while (index !== null) {
    if (!Number.isSafeInteger(index) || !history.pasos[index] || seen.has(index)) throw new Error('Broken material history ancestry.');
    seen.add(index); path.unshift(index); index = history.pasos[index].origen;
  }
  if (!path.length || history.pasos[path[0]].operacion !== null || !same(history.pasos[path[0]].formulacion, iniciarRecorrido().pasos[0].formulacion)) throw new Error('Material history must start from the fundamental conservation law.');
  const operations: MaterialOperation[] = [];
  let state = structuredClone(history.pasos[path[0]].formulacion);
  for (const index of path.slice(1)) {
    const step = history.pasos[index];
    if (!step.operacion || !same({ ...state, ...step.operacion }, step.formulacion)) throw new Error('The recorded material operation differs from its stored result.');
    state = structuredClone(step.formulacion);
    const changes = materialState(step.operacion);
    if (Object.keys(changes).length) operations.push({ id: `history-${index}`, title: step.titulo, changes });
  }
  return { origin: 'recorded', operations };
}

function same(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (!a || !b || typeof a !== 'object' || typeof b !== 'object') return false;
  const left = a as Record<string, unknown>, right = b as Record<string, unknown>;
  return Object.keys(left).length === Object.keys(right).length && Object.keys(left).every(key => Object.hasOwn(right, key) && same(left[key], right[key]));
}

/** Structural replay for provenance comparison, not symbolic algebra or units. */
export function journalMatches(entry: MaterialVolumeJournal, formulation: Partial<FormulacionMateria>): boolean {
  const normalize = (value: Partial<MaterialState>) => {
    const initial = materialState(iniciarRecorrido().pasos[0].formulacion) as MaterialState;
    return { ...initial, ...value, campo: { ...initial.campo, sinGeneracion: false, sinConsumo: false, generacionUniforme: false, consumoUniforme: false, ...value.campo } };
  };
  let state = normalize({});
  for (const operation of entry.operations) state = normalize({ ...state, ...operation.changes });
  return same(state, normalize(materialState(formulation)));
}

export function journalInRequest(derivation: unknown): MaterialJournal | undefined {
  if (derivation && typeof derivation === 'object' && Object.hasOwn(derivation, 'materialDerivation')) return readMaterialJournal((derivation as { materialDerivation: unknown }).materialDerivation);
}

export async function requestMaterialDevelopment(journal: MaterialJournal, volumeId: string, action?: { kind: string }, signal?: AbortSignal): Promise<{ journal: MaterialJournal; development: MaterialDevelopment }> {
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8004'}/modelo/material-derivation`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ journal, volumeId, ...(action ? { action } : {}) }),
    cache: 'no-store', signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body?.detail?.message ?? `Material development is unavailable (HTTP ${response.status}).`);
  exactObject(body, ['journal', 'development']);
  readMaterialJournal(body.journal);
  const development = body.development;
  exactObject(development, ['format', 'version', 'volumeId', 'origin', 'formulation', 'steps', 'notes']);
  if (development.format !== 'rage.material-development' || development.version !== 1 || development.volumeId !== volumeId || !Array.isArray(development.steps) || !Array.isArray(development.notes) || development.notes.some(note => typeof note !== 'string')) throw new Error('Invalid material development response.');
  for (const step of development.steps) {
    exactObject(step, ['id', 'title', 'latex']);
    if (['id', 'title', 'latex'].some(key => typeof step[key] !== 'string')) throw new Error('Invalid material development step.');
  }
  const parsed = body as unknown as { journal: MaterialJournal; development: MaterialDevelopment };
  if (!['recorded', 'reviewed_rebuild'].includes(parsed.development.origin) || !parsed.journal.volumes[volumeId] || !journalMatches(parsed.journal.volumes[volumeId], parsed.development.formulation)) throw new Error('The development does not match its operation journal.');
  return parsed;
}
