// Build the project-board datasets from the two canonical registries and validate them.
//   capabilities: frontend/app/checklist/datos.ts (engineCapabilities)
//   milestones, gates, decisions, risks: docs/engine/project-board.json
// Usage, from the repository root:
//   node tools/roadmap_board/build_board.mjs           validate and write tools/roadmap_board/out/
//   node tools/roadmap_board/build_board.mjs --check   validate only; exit 1 on any problem
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const ts = createRequire(path.join(root, 'frontend/package.json'))('typescript');
const problems = [];
const problem = (text) => problems.push(text);

function loadRegistry() {
  const file = path.join(root, 'frontend/app/checklist/datos.ts');
  const source = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText;
  const module = { exports: {} };
  new Function('exports', 'module', 'require', source)(module.exports, module, () => { throw new Error('datos.ts must stay import-free'); });
  return module.exports;
}

const slug = (heading) => heading.trim().toLowerCase().replace(/[^\p{L}\p{N}\s-]/gu, '').replace(/\s/g, '-');
const anchorCache = new Map();
function checkSource(owner, source) {
  if (!source) return;
  const [file, anchor] = source.split('#');
  const full = path.join(root, file);
  if (!fs.existsSync(full)) return problem(`${owner}: source file ${file} does not exist`);
  if (!anchor) return;
  if (!anchorCache.has(full)) {
    const anchors = new Set(fs.readFileSync(full, 'utf8').split(/\r?\n/).filter((line) => /^#{1,6}\s/.test(line)).map((line) => slug(line.replace(/^#+\s*/, ''))));
    anchorCache.set(full, anchors);
  }
  if (!anchorCache.get(full).has(anchor)) problem(`${owner}: heading #${anchor} not found in ${file}`);
}

const ENUMS = {
  milestoneStatus: ['done', 'review', 'active', 'next', 'planned', 'deferred', 'later', 'decision'],
  owner: ['codex', 'claude', 'user', 'shared'],
  track: ['demo', 'm1', 'phases', 'families', 'reliability', 'cleanup'],
  gateStatus: ['passed', 'review', 'open'],
  decisionStatus: ['taken', 'open'],
  severity: ['high', 'medium', 'low'],
  riskStatus: ['open', 'closed'],
};
const LABEL = {
  status: { done: 'Hecho', review: 'En revisión', active: 'En curso', next: 'Siguiente', planned: 'Pendiente', deferred: 'Aplazado', later: 'Al final', decision: 'Decisión pendiente', passed: 'Cumplido', open: 'Abierto', taken: 'Tomada', closed: 'Cerrado' },
  owner: { codex: 'Codex', claude: 'Claude', user: 'Usuario', shared: 'Codex + Claude' },
  track: { demo: 'Versión demostrable', m1: 'Ruta M1', phases: 'Fases físicas', families: 'Deducción por familia', reliability: 'Fiabilidad (F9)', cleanup: 'Limpieza del proyecto' },
  severity: { high: 'Alta', medium: 'Media', low: 'Baja' },
  capability: { available: 'Entregado', pending: 'Pendiente', deferred: 'Aplazado' },
  // Display names for the board; an unknown area falls back to the registry's English name.
  area: { mathematics: 'Fundamento matemático', engine: 'Motor común', materia: 'Materia', energia: 'Energía', momentum: 'Momento', termodinamica: 'Termodinámica', transform: 'Transform', results: 'Solve y Results' },
};

function requireFields(kind, item, fields) {
  for (const field of fields) if (!(field in item)) problem(`${kind} ${item.id ?? '?'}: missing field ${field}`);
}
function enumField(kind, item, field, values) {
  if (!values.includes(item[field])) problem(`${kind} ${item.id}: ${field} "${item[field]}" is not one of ${values.join(', ')}`);
}

// Claims: which agent is working on a milestone now and which repository paths it may edit for it.
// A path is a file or a directory prefix ending in '/'. Two paths overlap when one is a prefix of the other.
const AGENTS = ['codex', 'claude'];
const WAITING_WHO = ['codex', 'claude', 'user'];
const normalizePath = (p) => p.replace(/\\/g, '/').replace(/^\.\//, '');
const overlaps = (a, b) => {
  const [x, y] = [normalizePath(a), normalizePath(b)];
  return x === y || (x.endsWith('/') && y.startsWith(x)) || (y.endsWith('/') && x.startsWith(y));
};
function checkPathList(kind, list) {
  if (!Array.isArray(list) || !list.length || list.some((p) => typeof p !== 'string' || !p.trim() || path.isAbsolute(p) || p.includes('..'))) {
    problem(`${kind}: paths must be a non-empty list of repository-relative paths`);
    return [];
  }
  for (const p of list) {
    const full = path.join(root, normalizePath(p));
    if (!fs.existsSync(full) && !fs.existsSync(path.dirname(full))) problem(`${kind}: neither ${p} nor its parent directory exists`);
  }
  return list.map(normalizePath);
}

// Codex work queue: the numbered rows of the table under "## Queue" in docs/engine/codex-queue.md.
const QUEUE_FILE = 'docs/engine/codex-queue.md';
const QUEUE_STATUSES = ['ready', 'in progress', 'review pending', 'repairs requested', 'blocked', 'accepted'];
function loadQueue() {
  const full = path.join(root, QUEUE_FILE);
  if (!fs.existsSync(full)) return [];
  const lines = fs.readFileSync(full, 'utf8').split(/\r?\n/);
  const start = lines.findIndex((line) => /^##\s+Queue\s*$/.test(line));
  if (start < 0) { problem(`${QUEUE_FILE}: heading "## Queue" not found`); return []; }
  const rows = [];
  for (const line of lines.slice(start + 1)) {
    if (/^##\s/.test(line)) break;
    const cells = line.split('|').slice(1, -1).map((c) => c.trim());
    if (cells.length < 5 || !/^\d+$/.test(cells[0])) continue;
    const state = cells[4].replace(/`/g, '');
    // Autonomous loops select work by this leading status token (README, "Autonomous loops").
    const status = QUEUE_STATUSES.find((s) => state === s || state.startsWith(`${s} `) || state.startsWith(`${s}:`) || state.startsWith(`${s} ·`));
    if (!status) problem(`${QUEUE_FILE}: item ${cells[0]} state must start with one of ${QUEUE_STATUSES.join(', ')}`);
    rows.push({ id: `q${cells[0]}`, number: Number(cells[0]), item: cells[1].replace(/`/g, ''), model: cells[2], unblocks: cells[3].replace(/`/g, ''), status: status || '', state });
  }
  rows.forEach((r, i) => { if (r.number !== i + 1) problem(`${QUEUE_FILE}: queue numbers must run 1..${rows.length} without gaps`); });
  return rows;
}

// Progress percentages: the table under "### Progress percentages" in the roadmap (`dec-progress-table`).
// Rows: a bold first cell is a block with its own total, "· " starts a sub-row of the block above, and the
// "Project total" row closes the table. The % cell is a number 0-100, optionally with "~" or "≈" (an estimate).
const PROGRESS_FILE = 'docs/engine/multiphysics-roadmap.md';
function loadProgress() {
  const lines = fs.readFileSync(path.join(root, PROGRESS_FILE), 'utf8').split(/\r?\n/);
  const start = lines.findIndex((line) => /^#{2,6}\s+Progress percentages\b/.test(line));
  if (start < 0) { problem(`${PROGRESS_FILE}: heading "Progress percentages" not found`); return { rows: [], total: null }; }
  const rows = [];
  let total = null;
  let parent = '';
  let inTable = false;
  for (const line of lines.slice(start + 1)) {
    if (/^#{1,6}\s/.test(line)) break;
    if (!line.trim().startsWith('|')) { if (inTable) break; continue; }
    const cells = line.split('|').slice(1, -1).map((c) => c.trim());
    if (cells.length < 3) continue;
    if (/^Block$/i.test(cells[0])) { inTable = true; continue; }
    if (!inTable || /^-+$/.test(cells[0].replace(/[:\s]/g, ''))) continue;
    const clean = (s) => s.replace(/\*\*/g, '').replace(/`/g, '').trim();
    const name = clean(cells[0]);
    const m = clean(cells[2]).match(/^([~≈])?\s*(\d+(?:\.\d+)?)$/);
    if (!m || Number(m[2]) > 100) { problem(`${PROGRESS_FILE}: progress row "${name}" needs a % between 0 and 100 (optionally ~ or ≈), got "${cells[2]}"`); continue; }
    const percent = Number(m[2]);
    const estimate = Boolean(m[1]);
    if (/^project total/i.test(name)) { total = { name: name.replace(/\s*\(weighted\)\s*$/i, ''), percent, estimate, formula: clean(cells[1]) }; continue; }
    const sub = name.startsWith('·');
    const label = name.replace(/^·\s*/, '');
    if (!sub) parent = label;
    rows.push({ id: `p${rows.length + 1}`, order: rows.length + 1, level: sub ? 'sub' : 'block', parent: sub ? parent : '', name: label, state: clean(cells[1]), percent, estimate, group: cells[0].startsWith('**') });
  }
  if (!rows.length) problem(`${PROGRESS_FILE}: progress table has no rows`);
  if (!total) problem(`${PROGRESS_FILE}: progress table has no "Project total" row`);
  return { rows, total };
}

const registry = loadRegistry();
const queue = loadQueue();
const progress = loadProgress();
const board = JSON.parse(fs.readFileSync(path.join(root, 'docs/engine/project-board.json'), 'utf8'));
if (board.format !== 'rage.project-board' || board.version !== 1) problem('project-board.json: unsupported format or version');
if (!/^\d{4}-\d{2}-\d{2}$/.test(board.reviewDate || '')) problem('project-board.json: reviewDate must be YYYY-MM-DD');

const ids = new Set();
for (const collection of ['milestones', 'gates', 'decisions', 'risks']) {
  for (const item of board[collection] || []) {
    if (ids.has(item.id)) problem(`duplicate id ${item.id}`);
    ids.add(item.id);
  }
}

const capabilities = [];
registry.engineCapabilities.forEach((area, order) => {
  for (const key of ['available', 'pending', 'deferred']) {
    (area[key] || []).forEach((text, index) => capabilities.push({
      id: `${area.id}-${key}-${index + 1}`, area_order: order, area_id: area.id, area: LABEL.area[area.id] || area.name,
      workspace: area.workspace || '', status: LABEL.capability[key], status_code: key, item: text,
    }));
  }
});
if (!capabilities.length) problem('Checklist registry produced no capabilities');

const milestones = board.milestones.map((m) => {
  requireFields('milestone', m, ['id', 'track', 'order', 'title', 'status', 'owner', 'dependsOn', 'summary', 'nextAction', 'source']);
  enumField('milestone', m, 'status', ENUMS.milestoneStatus);
  enumField('milestone', m, 'owner', ENUMS.owner);
  enumField('milestone', m, 'track', ENUMS.track);
  for (const dependency of m.dependsOn || []) if (!ids.has(dependency)) problem(`milestone ${m.id}: dependsOn ${dependency} does not exist`);
  checkSource(`milestone ${m.id}`, m.source);
  const blockedBy = (m.dependsOn || []).filter((id) => {
    const target = board.milestones.find((x) => x.id === id);
    return target && target.status !== 'done' && m.status !== 'done';
  });
  // Optional: who the milestone waits on now (codex items name their queue numbers) and one plain line for the board.
  const waiting = m.waitingOn || [];
  if (!Array.isArray(waiting)) problem(`milestone ${m.id}: waitingOn must be a list`);
  for (const w of Array.isArray(waiting) ? waiting : []) {
    if (!WAITING_WHO.includes(w && w.who)) { problem(`milestone ${m.id}: waitingOn who "${w && w.who}" is not one of ${WAITING_WHO.join(', ')}`); continue; }
    if (w.queue !== undefined) {
      if (w.who !== 'codex') problem(`milestone ${m.id}: only a codex waitingOn entry names queue items`);
      if (!Array.isArray(w.queue) || !w.queue.length || w.queue.some((n) => !queue.some((q) => q.number === n))) problem(`milestone ${m.id}: waitingOn queue must list item numbers of ${QUEUE_FILE} (1..${queue.length})`);
    }
  }
  if (waiting.length && m.status === 'done') problem(`milestone ${m.id}: a done milestone cannot wait on anyone`);
  if ('remainingEs' in m && (typeof m.remainingEs !== 'string' || !m.remainingEs.trim())) problem(`milestone ${m.id}: remainingEs must be a non-empty string`);
  const validWaiting = Array.isArray(waiting) ? waiting.filter((w) => WAITING_WHO.includes(w && w.who)) : [];
  const claim = m.claim || null;
  return { id: m.id, track: LABEL.track[m.track], track_code: m.track, order: m.order, name: m.title,
    status: LABEL.status[m.status], status_code: m.status, owner: LABEL.owner[m.owner], owner_code: m.owner,
    depends_on: (m.dependsOn || []).join(', '), blocked_by: blockedBy.join(', '),
    note: m.summary, next_action: m.nextAction, source: m.source,
    claimed_by: claim ? LABEL.owner[claim.agent] || claim.agent : '', claim_since: claim ? claim.since : '',
    claim_files: claim && Array.isArray(claim.files) ? claim.files.join(', ') : '', claim_note: claim ? claim.note || '' : '',
    waiting_on: [...new Set(validWaiting.map((w) => w.who))].join(', '),
    codex_queue: [...new Set(validWaiting.flatMap((w) => (w.who === 'codex' && Array.isArray(w.queue) ? w.queue : [])))].sort((a, b) => a - b).join(', '),
    remaining: m.remainingEs || '' };
});

// Coexistence rules (tools/roadmap_board/README.md, "Working in parallel").
const ownership = board.ownership || {};
for (const agent of Object.keys(ownership)) if (!AGENTS.includes(agent)) problem(`ownership: unknown agent ${agent}`);
const owned = Object.fromEntries(AGENTS.map((a) => [a, ownership[a] ? checkPathList(`ownership.${a}`, ownership[a]) : []]));
const shared = board.sharedFiles ? checkPathList('sharedFiles', board.sharedFiles) : [];
const claims = [];
for (const m of board.milestones) {
  if (!m.claim) continue;
  const c = m.claim;
  requireFields(`milestone ${m.id} claim`, { id: m.id, ...c }, ['agent', 'since', 'files']);
  if (!AGENTS.includes(c.agent)) problem(`milestone ${m.id}: claim agent "${c.agent}" is not one of ${AGENTS.join(', ')}`);
  if (m.status !== 'active') problem(`milestone ${m.id}: only an active milestone can be claimed (status ${m.status}); release the claim when it stops`);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(c.since || '')) problem(`milestone ${m.id}: claim since must be YYYY-MM-DD`);
  const files = checkPathList(`milestone ${m.id} claim`, c.files);
  // A taken user decision may authorise one agent to edit the other agent's paths (for example a takeover).
  let authorised = false;
  if (c.authorizedBy !== undefined) {
    const d = board.decisions.find((x) => x.id === c.authorizedBy);
    if (!d || d.status !== 'taken' || d.owner !== 'user') problem(`milestone ${m.id}: claim authorizedBy ${c.authorizedBy} must name a decision taken by the user`);
    else authorised = true;
  }
  for (const f of files) {
    const s = shared.find((x) => overlaps(f, x));
    if (s) problem(`milestone ${m.id}: claim path ${f} overlaps the shared file ${s}; shared files are edited by exact replacement, never claimed`);
    for (const other of AGENTS.filter((a) => a !== c.agent)) {
      const o = owned[other].find((x) => overlaps(f, x));
      if (o && !authorised) problem(`milestone ${m.id}: ${c.agent} claims ${f}, owned by ${other} (${o}); coordinate through the user first`);
    }
  }
  claims.push({ id: m.id, agent: c.agent, files });
}
for (let i = 0; i < claims.length; i++) for (let j = i + 1; j < claims.length; j++) {
  const [a, b] = [claims[i], claims[j]];
  if (a.agent === b.agent) continue;
  for (const f of a.files) for (const g of b.files) if (overlaps(f, g)) problem(`claims collide: ${a.agent} on ${a.id} (${f}) and ${b.agent} on ${b.id} (${g})`);
}
// Standing file ownership and shared files, one row per path, for the board's "who works on what" view.
const ownershipRows = [
  ...AGENTS.flatMap((a) => owned[a].map((p, i) => ({ id: `${a}-${i + 1}`, agent: LABEL.owner[a], agent_code: a, kind: 'Propio', kind_code: 'owned', path: p }))),
  ...shared.map((p, i) => ({ id: `shared-${i + 1}`, agent: LABEL.owner.shared, agent_code: 'shared', kind: 'Compartido', kind_code: 'shared', path: p })),
];
const unclaimed = board.milestones.filter((m) => m.status === 'active' && AGENTS.includes(m.owner) && !m.claim).map((m) => m.id);
for (const track of ENUMS.track) {
  const orders = board.milestones.filter((m) => m.track === track).map((m) => m.order).sort((a, b) => a - b);
  if (orders.some((order, index) => order !== index + 1)) problem(`track ${track}: order must run 1..${orders.length} without gaps`);
}
for (const m of board.milestones) {
  if (['done', 'review'].includes(m.status)) continue;
  for (const dependency of m.dependsOn) {
    const target = board.milestones.find((x) => x.id === dependency);
    if (m.status === 'active' && target && !['done', 'review'].includes(target.status)) problem(`milestone ${m.id} is active but depends on unfinished ${dependency}`);
  }
}

const gates = board.gates.map((g) => {
  requireFields('gate', g, ['id', 'gate', 'title', 'status', 'evidence']);
  enumField('gate', g, 'status', ENUMS.gateStatus);
  return { id: g.id, gate: g.gate, criterion: g.title, status: LABEL.status[g.status], status_code: g.status, evidence: g.evidence };
});
const decisions = board.decisions.map((d) => {
  requireFields('decision', d, ['id', 'date', 'status', 'owner', 'title', 'detail', 'source']);
  enumField('decision', d, 'status', ENUMS.decisionStatus);
  checkSource(`decision ${d.id}`, d.source);
  return { id: d.id, date: d.date, status: LABEL.status[d.status], status_code: d.status, owner: LABEL.owner[d.owner], decision: d.title, detail: d.detail, source: d.source };
});
const risks = board.risks.map((r) => {
  requireFields('risk', r, ['id', 'severity', 'owner', 'title', 'mitigation', 'status']);
  enumField('risk', r, 'severity', ENUMS.severity);
  enumField('risk', r, 'status', ENUMS.riskStatus);
  return { id: r.id, severity: LABEL.severity[r.severity], severity_code: r.severity, owner: LABEL.owner[r.owner], risk: r.title, mitigation: r.mitigation, status: LABEL.status[r.status], status_code: r.status };
});

if (!/^\d{4}-\d{2}-\d{2}$/.test(registry.capabilityReviewDate || '')) problem('datos.ts: capabilityReviewDate must be YYYY-MM-DD');
const reviews = [
  { id: 'registry', name: 'Hitos, gates, decisiones y riesgos', source: 'docs/engine/project-board.json', date: board.reviewDate },
  { id: 'checklist', name: 'Inventario de capacidades', source: 'frontend/app/checklist/datos.ts', date: registry.capabilityReviewDate },
];

if (problems.length) {
  console.error('Project board: ' + problems.length + ' problem(s)');
  for (const p of problems) console.error('  - ' + p);
  process.exit(1);
}
const counts = Object.fromEntries(['available', 'pending', 'deferred'].map((k) => [k, capabilities.filter((c) => c.status_code === k).length]));
const current = board.milestones.filter((m) => m.track === 'm1').sort((a, b) => a.order - b.order).find((m) => m.status !== 'done');
const summary = [
  `Project board · registry review ${board.reviewDate} · Checklist review ${registry.capabilityReviewDate}`,
  `Capabilities: ${counts.available} delivered, ${counts.pending} pending, ${counts.deferred} deferred (${capabilities.length} total)`,
  `M1 current step: ${current ? `${current.title} [${current.status}, ${current.owner}]` : 'complete'}`,
  `Open decisions: ${board.decisions.filter((d) => d.status === 'open').map((d) => d.title).join('; ') || 'none'}`,
  `Open risks: ${board.risks.filter((r) => r.status === 'open').length}`,
  `Progress: project total ≈ ${progress.total.percent}% over ${progress.rows.length} rows (${PROGRESS_FILE})`,
  `Codex queue: ${queue.length} items (${QUEUE_FILE})`,
  `Claims: ${claims.map((c) => `${c.agent} on ${c.id} [${c.files.join(', ')}]`).join('; ') || 'none'}`,
  ...(unclaimed.length ? [`Unclaimed active items (claim before editing their files): ${unclaimed.join(', ')}`] : []),
].join('\n');
if (process.argv.includes('--check')) { console.log(summary + '\nValidation passed.'); process.exit(0); }

const out = path.join(root, 'tools/roadmap_board/out');
fs.mkdirSync(out, { recursive: true });
const write = (name, rows) => fs.writeFileSync(path.join(out, name + '.json'), JSON.stringify(rows, null, 1) + '\n');
write('capabilities', capabilities);
write('milestones', milestones);
write('gates', gates);
write('decisions', decisions);
write('risks', risks);
write('reviews', reviews);
write('ownership', ownershipRows);
write('queue', queue);
// One dataset: the weighted total first (level "total"), then the table rows in order.
write('progress', [
  { id: 'total', order: 0, level: 'total', parent: '', name: progress.total.name, state: progress.total.formula, percent: progress.total.percent, estimate: progress.total.estimate, group: true },
  ...progress.rows,
]);
fs.writeFileSync(path.join(out, 'summary.txt'), summary + '\n');
// The dashboard stores its page as a document {text}; page.html is its source.
fs.writeFileSync(path.join(out, 'page.json'), JSON.stringify({ text: fs.readFileSync(path.join(root, 'tools/roadmap_board/page.html'), 'utf8') }));
console.log(summary + `\nWrote ${['capabilities', 'milestones', 'gates', 'decisions', 'risks', 'reviews', 'ownership', 'queue', 'progress'].map((n) => n + '.json').join(', ')} to tools/roadmap_board/out/`);
