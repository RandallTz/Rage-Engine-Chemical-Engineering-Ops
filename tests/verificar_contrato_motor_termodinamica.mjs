// Pasa las respuestas REALES del backend (docs/ejemplos/motor-termodinamica-*,
// generadas por tests/generar_ejemplos_motor_termodinamica.py) por el validador
// TypeScript del contrato: frontend/app/motor/contratoTermodinamica.ts.
// Python -> JSON -> TypeScript sin cambios semanticos. No modifica el frontend.
//
// Ejecutar desde la raiz del proyecto:
//   node tests/verificar_contrato_motor_termodinamica.mjs
import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ts = createRequire(path.join(raiz, 'frontend', 'package.json'))('typescript');
const cache = new Map();
function cargar(n) {
  if (cache.has(n)) return cache.get(n);
  const m = {exports: {}};
  cache.set(n, m.exports);
  const fuente = fs.readFileSync(path.join(raiz, 'frontend', 'app', 'motor', `${n}.ts`), 'utf8');
  const js = ts.transpileModule(fuente, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText;
  new Function('exports', 'module', 'require', js)(m.exports, m, r => cargar(r.slice(2)));
  return m.exports;
}
const contrato = cargar('contratoTermodinamica');
const ejemplos = path.join(raiz, 'docs', 'ejemplos');
const leer = f => JSON.parse(fs.readFileSync(path.join(ejemplos, f), 'utf8'));

let checks = 0;
const capacidades = contrato.validarCapacidadesEstado(leer('motor-termodinamica-capacidades.json'));
checks++;
const casos = fs.readdirSync(ejemplos).filter(f => /^motor-termodinamica-.*-peticion\.json$/.test(f));
assert.ok(casos.length >= 8, 'faltan ejemplos: ejecuta tests/generar_ejemplos_motor_termodinamica.py');
const vistos = new Set();
for (const f of casos) {
  const s = leer(f), r = leer(f.replace('-peticion', '-respuesta'));
  const cap = capacidades.modelos.find(m => m.id === s.declaracion.modelo.id && m.version === s.declaracion.modelo.version
    && m.especificaciones.includes(s.declaracion.especificacion.tipo));
  const v = contrato.validarRespuestaEstado(r, s, cap);
  checks++;
  vistos.add(v.estado);
  if (v.estado === 'evaluado') {
    assert.deepEqual(contrato.analizarSolicitudEstado(s), [], `${f}: la solicitud evaluada no pasa el analizador del cliente`);
    assert.ok(cap, `${f}: evaluado sin capacidad publicada`);
    checks++;
  }
  // null presente en el rechazo, ausente nunca sustituido por cero
  if (v.estado !== 'evaluado') { assert.ok(Object.hasOwn(r, 'evaluacion') && r.evaluacion === null, `${f}: evaluacion null`); checks++; }
  console.log(`  ${f.replace('-peticion.json', '')}: ${v.estado}`);
}
assert.ok(['evaluado', 'incompleto', 'invalido', 'no_soportado'].every(e => vistos.has(e)), `estados cubiertos: ${[...vistos]}`);
// Una respuesta alterada debe rechazarse: el validador no es un sello vacío.
const s = leer('motor-termodinamica-liquido-25C-1bar-peticion.json'), r = leer('motor-termodinamica-liquido-25C-1bar-respuesta.json');
const cap = capacidades.modelos[0];
for (const [nombre, mutar] of [
  ['h incompatible', x => { x.evaluacion.mezcla.h += 1; }],
  ['T distinta', x => { x.evaluacion.T += 0.01; }],
  // Sin masa molar declarada en la solicitud, el validador del cliente no
  // contrasta masaMolarKgMol (ver docs/engine/thermodynamics-h0-h1.md, hallazgos).
  ['fracción de volumen falsa', x => { x.evaluacion.fases[0].fraccionVolumen = 0.5; }],
  ['estabilidad no certificada', x => { x.evaluacion.estabilidad.estado = 'no_evaluada'; }],
]) { const x = structuredClone(r); mutar(x); assert.throws(() => contrato.validarRespuestaEstado(x, s, cap), undefined, nombre); checks++; }
console.log(`OK: ${checks} comprobaciones del contrato TypeScript sobre respuestas reales`);
