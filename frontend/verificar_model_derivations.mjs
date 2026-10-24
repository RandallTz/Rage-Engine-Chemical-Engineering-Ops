// Audit every registered template and reject new provenance bypasses.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';

const directory = path.dirname(fileURLToPath(import.meta.url));
const cache = new Map();
function load(file) {
  if (!path.extname(file)) file += '.ts';
  if (file.endsWith('.json')) return { __esModule: true, default: JSON.parse(fs.readFileSync(file, 'utf8')) };
  if (cache.has(file)) return cache.get(file);
  const loadedModule = { exports: {} }; cache.set(file, loadedModule.exports);
  const source = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true,
  } }).outputText;
  new Function('exports', 'module', 'require', 'process', source)(loadedModule.exports, loadedModule, dependency => {
    if (!dependency.startsWith('.')) throw new Error('Unexpected external dependency: ' + dependency);
    return load(path.resolve(path.dirname(file), dependency));
  }, { env: {} });
  cache.set(file, loadedModule.exports); return loadedModule.exports;
}
const { auditModelDerivation } = load(path.join(directory, 'app/models/modelDerivationAudit'));
const { REGRESSION_MODELS } = load(path.join(directory, 'testing/modelFixtures'));
const { nuevaHoja } = load(path.join(directory, 'app/motor/hojasMotor'));

let checks = 0;
const check = (condition, message) => { assert.ok(condition, message); checks++; };
const models = REGRESSION_MODELS.flatMap(group => group.create().map(model => ({group:group.name,model})));
const counts = {fundamental:0,recorded:0,needs_review:0};
check(auditModelDerivation(nuevaHoja('New fundamental model')).status==='fundamental','New models start at the fundamental equation without imposed assumptions');
for(const {model} of models) {
  const before=JSON.stringify(model),audit=auditModelDerivation(model);
  counts[audit.status]++;
  check(before===JSON.stringify(model),model.id+': audit never mutates physics, histories or results');
  check(audit.status!=='needs_review',model.id+': no new template may bypass the derivation standard');
  if(model.redTermodinamica) {
    check(audit.findings.length===0,model.id+': all active physical families have recorded provenance');
    check(!audit.findings.some(item=>item.family==='matter'),model.id+': new templates have a replayable material journal');
  }
}
const first=models.find(({model})=>auditModelDerivation(model).status==='recorded').model;
let tampered=structuredClone(first);
tampered.historial.pasos[0].formulacion.fija=true;
check(auditModelDerivation(tampered).findings.some(item=>item.code==='nonfundamental_root'),'A modified starting equation is rejected');
tampered=structuredClone(first);
tampered.historial.pasos[1].operacion=null;
check(auditModelDerivation(tampered).findings.some(item=>item.code==='missing_operation'),'A snapshot without its material operation is rejected');
tampered=structuredClone(first);
tampered.historial.pasos[1].formulacion.sinAcumulacion=true;
check(auditModelDerivation(tampered).findings.some(item=>item.code==='snapshot_mismatch'),'An operation must replay to its stored result');
tampered=structuredClone(first);
tampered.historial.pasos[tampered.historial.activo].origen=tampered.historial.activo;
check(auditModelDerivation(tampered).findings.some(item=>item.code==='broken_ancestry'),'Cyclic provenance is rejected');
console.log(JSON.stringify({checks,templates:models.length,counts,limitation:'Structural provenance audit; not a mathematical or solver certificate.'},null,2));
