// Demo 0.2 column Solve repair: the pinned signature of an indexed network or flowsheet selection is a SHA-256, so storing it in the sheet
// (`resultadoRef.firma`) cannot exceed the 5 MiB browser quota (the five-stage column's selection is 3.3 MB and its full signature was 4.3 MB).
import modulePath from 'node:path';
import fs from 'node:fs';
import ts from 'typescript';
import assert from 'node:assert/strict';
const cache=new Map();function cargar(n){if(cache.has(n))return cache.get(n);const m={exports:{}};new Function('exports','module','require',ts.transpileModule(fs.readFileSync(`app/motor/${n}.ts`,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText)(m.exports,m,r=>cargar(modulePath.posix.join(modulePath.posix.dirname(n),r)));cache.set(n,m.exports);return m.exports;}
const hoja=cargar('modeloHojaMotor'),casos=cargar('hojasPruebaAcoplamiento').crearHojasPruebaAcoplamiento();
const base=casos[0],big={format:'rage.indexed-execution',version:1,payload:'x'.repeat(4_000_000)};
const indexed={...structuredClone(base),indexedSelection:{...big}};
const pin=hoja.firmaHoja(indexed);
assert.match(pin,/^sha256:[0-9a-f]{64}$/,'An indexed selection is pinned as a SHA-256');
assert.equal(hoja.firmaHoja(structuredClone(indexed)),pin,'The pin is deterministic');
const changed=structuredClone(indexed);changed.indexedSelection.payload='y'+changed.indexedSelection.payload.slice(1);
assert.notEqual(hoja.firmaHoja(changed),pin,'A changed selection changes the pin');
const other=structuredClone(indexed);other.config.datos={...other.config.datos,extra:{texto:'1',unidad:'1'}};
assert.notEqual(hoja.firmaHoja(other),pin,'A changed model changes the pin');
const flow={...structuredClone(base),flowsheetSelection:{...big}};
assert.match(hoja.firmaHoja(flow),/^sha256:[0-9a-f]{64}$/,'A flowsheet selection is pinned as a SHA-256');
assert.notEqual(hoja.firmaHoja(flow),pin,'The two selection kinds never share a pin');
const plain=hoja.firmaHoja(base);assert.ok(!plain.startsWith('sha256:'),'Ordinary signatures are unchanged and stay readable');
assert.ok(pin.length<100,'The stored pin is short');
console.log('firmaHoja compact selection signature: all checks passed');
