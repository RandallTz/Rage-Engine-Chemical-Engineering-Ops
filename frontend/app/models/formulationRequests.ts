/** Coalesce read-only formulation requests across Strict Mode effect replays.
 * Subscribers cancel their own publication; a shared request has one timeout.
 * Completed responses live only briefly, and never serve a different payload.
 */
const requests = new Map<string, Promise<Response>>();
const canonical = (value: unknown): unknown => Array.isArray(value) ? value.map(canonical) : value && typeof value === 'object'
  ? Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => [key, canonical(item)])) : value;

export function requestFormulation(endpoint: 'formulation-summary' | 'equation-workbench' | 'derived-execution-source', body: string): Promise<Response> {
  const payload = JSON.stringify(canonical(JSON.parse(body)));
  const key = endpoint + ':' + payload;
  let pending = requests.get(key);
  if (!pending) {
    pending = fetch(`${process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8004'}/modelo/${endpoint}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: payload,
      cache: 'no-store', signal: AbortSignal.timeout(60000),
    });
    requests.set(key, pending);
    const current = pending;
    const remove = () => { if (requests.get(key) === current) requests.delete(key); };
    void pending.then(response => { if (response.ok) setTimeout(remove, 1000); else remove(); }, remove);
    if (requests.size > 32) requests.delete(requests.keys().next().value!);
  }
  return pending.then(response => response.clone());
}
