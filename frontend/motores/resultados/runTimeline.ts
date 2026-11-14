/** Strict reader for `procedencia.runTimeline` v1 (docs/contracts/results-format.md).
 * Mirrors core/resultados/run_timeline.py: the client only validates, Python publishes every value. */
import type { ConjuntoResultados } from './contrato';

export type RunTimeline = {
  format: 'rage.run-timeline'; version: 1; horizon: number;
  actions: { seq: number; t: number; quantityId: string; value: number; unit: string; origin: 'scheduled' | 'operator' }[];
  termination: { reason: 'completed' | 'operator_stop' | 'solver_stop'; tEnd: number };
};
export const TIMELINE_ACTION_EVENT = 'timeline_action', TIMELINE_TERMINATION_EVENT = 'timeline_termination';
const TOL = 1e-9;
const num = (x: unknown): x is number => typeof x === 'number' && Number.isFinite(x);
const sameKeys = (o: object, keys: string[]) => Object.keys(o).length === keys.length && keys.every(k => k in o);

export function readRunTimeline(result: ConjuntoResultados, fail: (path: string, reason: string) => never): RunTimeline {
  const reject = (m: string): never => fail('procedencia.runTimeline', m);
  const v = result.procedencia.runTimeline as unknown as RunTimeline;
  if (!v || typeof v !== 'object' || !sameKeys(v, ['format', 'version', 'horizon', 'actions', 'termination']) || v.format !== 'rage.run-timeline' || v.version !== 1)
    reject('Expected rage.run-timeline version 1 with exactly its fields.');
  if (!num(v.horizon) || v.horizon <= 0) reject('The horizon must be a positive finite number.');
  const end = v.termination;
  if (!end || typeof end !== 'object' || !sameKeys(end, ['reason', 'tEnd']) || !['completed', 'operator_stop', 'solver_stop'].includes(end.reason)) reject('A termination with a known reason is required.');
  if (!num(end.tEnd) || end.tEnd < 0 || end.tEnd > v.horizon * (1 + TOL)) reject('The termination time must lie within [0, horizon].');
  if (!Array.isArray(v.actions)) reject('Actions must be a list.');
  let previous = 0;
  v.actions.forEach((a, i) => {
    if (!a || typeof a !== 'object' || !sameKeys(a, ['seq', 't', 'quantityId', 'value', 'unit', 'origin'])) reject(`Action ${i} needs exactly seq, t, quantityId, value, unit and origin.`);
    if (a.seq !== i) reject(`Action ${i} must carry seq ${i}.`);
    if (!num(a.t) || a.t < previous || a.t > end.tEnd * (1 + TOL)) reject(`Action ${i} time must be finite, not decrease and not exceed the termination time.`);
    previous = a.t;
    if (typeof a.quantityId !== 'string' || !a.quantityId || !num(a.value)) reject(`Action ${i} needs a quantity identity and a finite value.`);
    if (!['scheduled', 'operator'].includes(a.origin)) reject(`Action ${i} origin must be scheduled or operator.`);
    if (typeof a.unit !== 'string' || !a.unit) reject(`Action ${i} needs a unit.`); // readability of the unit is checked by the Python reader
  });
  if (result.estado === 'fallido') reject('A failed result carries no run timeline.');
  if (end.reason === 'completed') {
    if (result.estado !== 'resuelto' || Math.abs(end.tEnd - v.horizon) > TOL * v.horizon) reject('A completed run is solved and ends at the horizon.');
  } else if (result.estado !== 'parcial') reject('A run that stopped early must be published as partial, never as solved.');
  const axis = result.ejes.find(e => e.rol === 'tiempo');
  if (!axis) return reject('A run timeline needs a time axis.');
  const times = axis.valores;
  if (!times.length || times.some((t, i) => i > 0 && t < times[i - 1])) reject('The time axis of a timed run must not decrease.');
  if (Math.abs(times[times.length - 1] - end.tEnd) > TOL * Math.max(v.horizon, 1)) reject('The sampled times must end at the termination time.');
  const allowed = new Map<number, number>(), seen = new Map<number, number>();
  v.actions.forEach(a => allowed.set(a.t, (allowed.get(a.t) ?? 0) + 1));
  times.forEach(t => seen.set(t, (seen.get(t) ?? 0) + 1));
  seen.forEach((count, t) => { if (count > 1 && count > 1 + (allowed.get(t) ?? 0)) reject('A time may repeat only at an action.'); });
  const pairs = (code: string) => result.eventos.filter(e => e.codigo === code).map(e => `${e.ejeId}|${e.valor}`);
  if (JSON.stringify(pairs(TIMELINE_ACTION_EVENT)) !== JSON.stringify(v.actions.map(a => `${axis.id}|${a.t}`))) reject('Every action must be published as an event on the time axis, in order.');
  if (JSON.stringify(pairs(TIMELINE_TERMINATION_EVENT)) !== JSON.stringify(end.reason === 'completed' ? [] : [`${axis.id}|${end.tEnd}`])) reject('An early stop must be published as one termination event at its time.');
  return v;
}
