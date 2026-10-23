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
  track: ['m1', 'phases', 'families', 'reliability', 'cleanup'],
  gateStatus: ['passed', 'review', 'open'],
  decisionStatus: ['taken', 'open'],
  severity: ['high', 'medium', 'low'],
  riskStatus: ['open', 'closed'],
};
const LABEL = {
  status: { done: 'Hecho', review: 'En revisión', active: 'En curso', next: 'Siguiente', planned: 'Pendiente', deferred: 'Aplazado', later: 'Al final', decision: 'Decisión pendiente', passed: 'Cumplido', open: 'Abierto', taken: 'Tomada', closed: 'Cerrado' },
  owner: { codex: 'Codex', claude: 'Claude', user: 'Usuario', shared: 'Codex + Claude' },
  track: { m1: 'Ruta M1', phases: 'Fases físicas', families: 'Deducción por familia', reliability: 'Fiabilidad (F9)', cleanup: 'Limpieza del proyecto' },
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

const registry = loadRegistry();
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
  return { id: m.id, track: LABEL.track[m.track], track_code: m.track, order: m.order, name: m.title,
    status: LABEL.status[m.status], status_code: m.status, owner: LABEL.owner[m.owner],
    depends_on: (m.dependsOn || []).join(', '), blocked_by: blockedBy.join(', '),
    note: m.summary, next_action: m.nextAction, source: m.source };
});
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
fs.writeFileSync(path.join(out, 'summary.txt'), summary + '\n');
// The dashboard stores its page as a document {text}; page.html is its source.
fs.writeFileSync(path.join(out, 'page.json'), JSON.stringify({ text: fs.readFileSync(path.join(root, 'tools/roadmap_board/page.html'), 'utf8') }));
console.log(summary + `\nWrote ${['capabilities', 'milestones', 'gates', 'decisions', 'risks'].map((n) => n + '.json').join(', ')} to tools/roadmap_board/out/`);
