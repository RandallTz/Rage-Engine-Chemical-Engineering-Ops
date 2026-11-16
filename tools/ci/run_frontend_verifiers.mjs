#!/usr/bin/env node
// Runs a named group of frontend verifiers and exits non-zero if any fails.
//
// Usage (from the repository root or from frontend/):
//   node tools/ci/run_frontend_verifiers.mjs pure     # no server, no browser, no Python
//   node tools/ci/run_frontend_verifiers.mjs python   # spawn Python (needs requirements.txt); slow
//   node tools/ci/run_frontend_verifiers.mjs http     # need the API at NEXT_PUBLIC_API_URL
//   node tools/ci/run_frontend_verifiers.mjs quarantine  # known failing: run non-blocking (continue-on-error)
//
// The groups live in tools/ci/frontend_verifiers_<group>.txt, one file name per
// line ('#' starts a comment). A line `verificar_x.mjs :: tests/test_y.py` first
// runs that Python script from frontend/ (it writes the publication the verifier
// reads) and fails the verifier if the script fails. A verifier in frontend/ that is in no group and
// not in tools/ci/frontend_verifiers_other.txt is reported and fails the run,
// so a new verifier cannot be silently left out of CI.
//
// Time limit: each verifier (with its prerequisite) is stopped after a limit, so one stalled
// verifier cannot consume the CI job's time and hide the steps after it. The limit is
// --timeout=SECONDS if given, else the group's default below (0 means none). On expiry the
// whole process tree is killed (a verifier may have spawned Python) and the verifier counts as
// failed with status TIME.
import { spawn, spawnSync } from 'node:child_process';
import { existsSync, mkdirSync, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, '..', '..', 'frontend');
const group = process.argv[2];
// Some verifiers write their example to the git-ignored .tmp/ folder; a clean clone has none.
mkdirSync(path.resolve(here, '..', '..', '.tmp'), { recursive: true });

const read = (name) => {
  const file = path.join(here, `frontend_verifiers_${name}.txt`);
  if (!existsSync(file)) return [];
  return readFileSync(file, 'utf8').split(/\r?\n/).map((l) => l.replace(/#.*/, '').trim()).filter(Boolean);
};

const entries = (name) => read(name).map((l) => {
  const [file, pre] = l.split('::').map((x) => x.trim());
  return { file, pre };
});

const groups =['pure', 'python', 'http', 'quarantine'];
if (!groups.includes(group)) {
  console.error(`Usage: run_frontend_verifiers.mjs <${groups.join('|')}> [--timeout=SECONDS]`);
  process.exit(2);
}
// Per-verifier limits in seconds. Quarantined verifiers are known to fail or not finish
// (verificar_bateria_multifisica.mjs did not finish in 900 s locally and, without a limit, used
// the remaining 70 minutes of the interface job in CI run 43660814888).
// The blocking groups' limits are several times their slowest verifier (whole groups: pure
// 132 s, python 29 min and http 861 s locally; python 20 min in CI).
const DEFAULT_TIMEOUT = { pure: 600, python: 2700, http: 1800, quarantine: 600 };
const timeoutArg = process.argv.slice(3).find((a) => a.startsWith('--timeout='));
const timeoutSeconds = timeoutArg ? Number(timeoutArg.slice('--timeout='.length)) : DEFAULT_TIMEOUT[group];
if (!Number.isFinite(timeoutSeconds) || timeoutSeconds < 0) {
  console.error(`Invalid ${timeoutArg}`);
  process.exit(2);
}

function killTree(child) {
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/pid', String(child.pid), '/T', '/F'], { stdio: 'ignore' });
  } else {
    try { process.kill(-child.pid, 'SIGKILL'); } catch { child.kill('SIGKILL'); }
  }
}

// Runs one command with the shared deadline; resolves {status, stdout, stderr, timedOut}.
function run(command, args, options, deadline) {
  return new Promise((resolve) => {
    // detached: a new process group on POSIX, so the whole tree can be killed on expiry.
    const child = spawn(command, args, { ...options, detached: process.platform !== 'win32', stdio: ['ignore', 'pipe', 'pipe'] });
    const out = [], err = [];
    child.stdout.on('data', (d) => out.push(d));
    child.stderr.on('data', (d) => err.push(d));
    let timedOut = false;
    const remaining = deadline === Infinity ? 0 : Math.max(1, deadline - Date.now());
    const timer = deadline === Infinity ? null : setTimeout(() => { timedOut = true; killTree(child); }, remaining);
    let settled = false;
    const finish = (status) => {
      if (settled) return;
      settled = true;
      if (timer) clearTimeout(timer);
      resolve({ status: timedOut ? null : status, timedOut,
        stdout: Buffer.concat(out).toString('utf8'), stderr: Buffer.concat(err).toString('utf8') });
    };
    child.on('error', (e) => { err.push(Buffer.from(String(e))); finish(1); });
    child.on('close', (code) => finish(code));
    // A grandchild left holding the pipes after the child exits must not keep the runner waiting.
    child.on('exit', (code) => setTimeout(() => finish(code), timedOut ? 0 : 2000));
  });
}

// Coverage guard: every verifier file must belong to exactly one list.
const known = new Map();
for (const g of [...groups, 'other']) for (const { file: f } of entries(g)) {
  if (known.has(f)) { console.error(`${f} is listed in both '${known.get(f)}' and '${g}'`); process.exit(1); }
  known.set(f, g);
}
function discoverVerifiers(directory, relative = '') {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    if (entry.name.startsWith('.') || entry.name === 'node_modules') return [];
    const name = relative ? `${relative}/${entry.name}` : entry.name;
    if (entry.isDirectory()) return discoverVerifiers(path.join(directory, entry.name), name);
    return entry.isFile() && /^(?:verify|verificar)_.*\.mjs$/.test(entry.name) ? [name] : [];
  });
}
const onDisk = discoverVerifiers(frontend);
const unlisted = onDisk.filter((f) => !known.has(f));
const missing = [...known.keys()].filter((f) => !onDisk.includes(f));
if (unlisted.length || missing.length) {
  if (unlisted.length) console.error(`Verifiers in no CI list (add them to tools/ci/frontend_verifiers_*.txt): ${unlisted.join(', ')}`);
  if (missing.length) console.error(`Listed but missing on disk: ${missing.join(', ')}`);
  process.exit(1);
}

const files = entries(group);
const failed = [];
let total = 0;
for (const { file, pre } of files) {
  const start = Date.now();
  const env = { ...process.env, MPLBACKEND: 'Agg', PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' };
  // A pytest file (test_*.py) as prerequisite runs under pytest; any other script runs directly.
  // pytest runs from the repository root so that tests import `core`.
  const isPytest = pre && path.basename(pre).startsWith('test_');
  const preArgs = isPytest ? ['-m', 'pytest', '-q', '-p', 'no:cacheprovider', path.resolve(frontend, pre)] : [pre];
  const deadline = timeoutSeconds > 0 ? start + timeoutSeconds * 1000 : Infinity;
  let r = pre ? await run('python', preArgs, { cwd: isPytest ? path.resolve(frontend, '..') : frontend, env }, deadline) : { status: 0 };
  if (r.status === 0) r = await run(process.execPath, [file], { cwd: frontend, env }, deadline);
  const seconds = (Date.now() - start) / 1000;
  total += seconds;
  const ok = r.status === 0;
  console.log(`[${ok ? 'OK   ' : r.timedOut ? 'TIME ' : 'FAIL '}] ${file.padEnd(48)} ${seconds.toFixed(1)}s`);
  if (!ok) {
    failed.push(file);
    if (r.timedOut) console.log(`    | stopped after the ${timeoutSeconds} s per-verifier limit (process tree killed)`);
    const tail = (s) => (s || '').trimEnd().split('\n').slice(-25).map((l) => `    | ${l}`).join('\n');
    console.log(tail(r.stdout)); console.log(tail(r.stderr));
  }
}
console.log('-'.repeat(78));
if (failed.length) { console.log(`FAILED ${failed.length} of ${files.length}: ${failed.join(', ')}`); process.exit(1); }
console.log(`ALL GREEN: ${files.length} verifiers (${group}) in ${total.toFixed(1)}s`);
