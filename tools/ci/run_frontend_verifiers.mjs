#!/usr/bin/env node
// Runs a named group of frontend verifiers and exits non-zero if any fails.
//
// Usage (from the repository root or from frontend/):
//   node tools/ci/run_frontend_verifiers.mjs pure     # no server, no browser, no Python
//   node tools/ci/run_frontend_verifiers.mjs python   # spawn Python (needs requirements.txt); slow
//   node tools/ci/run_frontend_verifiers.mjs quarantine  # known failing: run non-blocking (continue-on-error)
//
// The groups live in tools/ci/frontend_verifiers_<group>.txt, one file name per
// line ('#' starts a comment). A line `verificar_x.mjs :: tests/test_y.py` first
// runs that Python script from frontend/ (it writes the publication the verifier
// reads) and fails the verifier if the script fails. A verifier in frontend/ that is in no group and
// not in tools/ci/frontend_verifiers_other.txt is reported and fails the run,
// so a new verifier cannot be silently left out of CI.
import { spawnSync } from 'node:child_process';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const frontend = path.resolve(here, '..', '..', 'frontend');
const group = process.argv[2];

const read = (name) => {
  const file = path.join(here, `frontend_verifiers_${name}.txt`);
  if (!existsSync(file)) return [];
  return readFileSync(file, 'utf8').split(/\r?\n/).map((l) => l.replace(/#.*/, '').trim()).filter(Boolean);
};

const entries = (name) => read(name).map((l) => {
  const [file, pre] = l.split('::').map((x) => x.trim());
  return { file, pre };
});

const groups =['pure', 'python', 'quarantine'];
if (!groups.includes(group)) {
  console.error(`Usage: run_frontend_verifiers.mjs <${groups.join('|')}>`);
  process.exit(2);
}

// Coverage guard: every verifier file must belong to exactly one list.
const known = new Map();
for (const g of [...groups, 'other']) for (const { file: f } of entries(g)) {
  if (known.has(f)) { console.error(`${f} is listed in both '${known.get(f)}' and '${g}'`); process.exit(1); }
  known.set(f, g);
}
const onDisk = readdirSync(frontend).filter((f) => /^verificar_.*\.mjs$/.test(f));
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
  let r = pre ? spawnSync('python', [pre], { cwd: frontend, encoding: 'utf8', maxBuffer: 256 * 1024 * 1024, env }) : { status: 0 };
  if (r.status === 0) r = spawnSync(process.execPath, [file], {
    cwd: frontend, encoding: 'utf8', maxBuffer: 256 * 1024 * 1024,
    env,
  });
  const seconds = (Date.now() - start) / 1000;
  total += seconds;
  const ok = r.status === 0;
  console.log(`[${ok ? 'OK   ' : 'FAIL '}] ${file.padEnd(48)} ${seconds.toFixed(1)}s`);
  if (!ok) {
    failed.push(file);
    const tail = (s) => (s || '').trimEnd().split('\n').slice(-25).map((l) => `    | ${l}`).join('\n');
    console.log(tail(r.stdout)); console.log(tail(r.stderr));
  }
}
console.log('-'.repeat(78));
if (failed.length) { console.log(`FAILED ${failed.length} of ${files.length}: ${failed.join(', ')}`); process.exit(1); }
console.log(`ALL GREEN: ${files.length} verifiers (${group}) in ${total.toFixed(1)}s`);
