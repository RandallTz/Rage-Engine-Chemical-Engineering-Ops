export type Workspace = 'model' | 'transform' | 'solve' | 'results';

export const WORKSPACES = [
  { id: 'model', number: '01', name: 'Model', description: 'Laws, assumptions & physical system', instruction: 'Start from fundamental laws. Define your system and record the assumptions that shape its equations.' },
  { id: 'transform', number: '02', name: 'Transform', description: 'Mathematical techniques & discretization', instruction: 'Prepare a mathematical representation. Apply a technique when needed, or continue with the original equations.' },
  { id: 'solve', number: '03', name: 'Solve', description: 'Data, degrees of freedom & methods', instruction: 'Complete the required data, check the degrees of freedom, and choose how to solve the problem.' },
  { id: 'results', number: '04', name: 'Results', description: 'Solutions, charts & verification', instruction: 'Inspect the solution, explore its data, and check the numerical and physical diagnostics.' },
] as const;

export const modelUrl = (id: string, workspace: Workspace = 'model') => `/models/${encodeURIComponent(id)}/${workspace}`;

/** Keep old bookmarks and structured diagnostic targets working during migration. */
export function legacyModelUrl(id: string, view: string, query: Record<string, string | string[] | undefined> = {}) {
  const workspace = view === 'resolver' ? 'solve' : view === 'resultados' ? 'results' : 'model';
  const parameters = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (Array.isArray(value)) value.forEach(item => parameters.append(key, item));
    else if (value !== undefined) parameters.set(key, value);
  }
  const base = modelUrl(id, workspace) + (view === 'estado' ? '/state' : '');
  return base + (parameters.size ? `?${parameters}` : '');
}
