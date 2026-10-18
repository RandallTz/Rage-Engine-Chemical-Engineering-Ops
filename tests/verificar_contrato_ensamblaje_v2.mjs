// Comprueba con el compilador de TypeScript que las peticiones y respuestas REALES de la revision 2
// (docs/ejemplos/motor-v2/motor-ensamblaje-v2-*, generadas desde los endpoints por
// tests/generar_ejemplos_motor_ensamblaje_v2.py) tienen exactamente los tipos de
// docs/contratos/contratoEnsamblajeV2.ts. Cada estado termodinamico publicado (por volumen y muestra)
// y cada ejemplo puntual de mezcla o hielo pasa ademas por validarRespuestaEstado del contrato
// puntual del frontend, con la capacidad publicada de su modelo. No modifica el frontend.
//
// Ejecutar desde la raiz del proyecto:
//   node tests/verificar_contrato_ensamblaje_v2.mjs
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ts = createRequire(path.join(raiz, 'frontend', 'package.json'))('typescript');
// Directorios de ejemplos de la revision 2: los de M0-M6/consolidacion y los de la ampliacion a N componentes
// (tests/generar_ejemplos_motor_n_componentes.py), cada uno con sus capacidades.
const DIRECTORIOS = ['motor-v2', 'motor-n-componentes'].map(d => path.join(raiz, 'docs', 'ejemplos', d)).filter(d => fs.existsSync(d));
const contrato = path.join(raiz, 'docs', 'contratos', 'contratoEnsamblajeV2').replaceAll('\\', '/');
const nombres = DIRECTORIOS.flatMap(d => fs.readdirSync(d).filter(f => /^motor-ensamblaje-v2-.*-peticion\.json$/.test(f)).sort()
  .map(f => path.join(d, f)));
assert.ok(nombres.length >= 5, 'faltan ejemplos: ejecuta tests/generar_ejemplos_motor_ensamblaje_v2.py');
const ejemplos = DIRECTORIOS[0];

// 1. Tipos.
let fuente = `import type {SolicitudEnsamblajeV2,RespuestaValidacionV2,RespuestaResolucionV2,CapacidadesEnsamblajeV2} from '${contrato}';\n`;
DIRECTORIOS.forEach((d, i) => {
  fuente += `export const cap${i}: CapacidadesEnsamblajeV2 = ${fs.readFileSync(path.join(d, 'motor-ensamblaje-v2-capacidades.json'), 'utf8')};\n`;
});
nombres.forEach((n, i) => {
  const s = fs.readFileSync(n, 'utf8');
  const r = fs.readFileSync(n.replace('-peticion', '-respuesta'), 'utf8');
  const tipo = n.includes('-resolver-') ? 'RespuestaResolucionV2' : 'RespuestaValidacionV2';
  fuente += `export const s${i}: SolicitudEnsamblajeV2 = ${s};\nexport const r${i}: ${tipo} = ${r};\n`;
});
// Borrador C4 (no publicado): debe compilar contra la revision 2, y su peticion de ejemplo tambien.
const borrador = path.join(raiz, 'docs', 'contratos', 'borradorFronteraAbierta').replaceAll('\\', '/');
fuente += `import type {SolicitudFronteraAbiertaBorrador} from '${borrador}';\n`;
fuente += `export const borrador1: SolicitudFronteraAbiertaBorrador = ${fs.readFileSync(path.join(raiz, 'docs', 'ejemplos', 'borrador-frontera-abierta', 'olla-abierta-peticion.json'), 'utf8')};\n`;
fuente += `// @ts-expect-error estado fuera de la union\nexport const malo1: RespuestaResolucionV2['estado'] = 'terminado';\n`;
fuente += `// @ts-expect-error la revision 2 no admite revision 1 en la solicitud\nexport const malo2: SolicitudEnsamblajeV2['revision'] = 1;\n`;
fuente += `// @ts-expect-error segunda ley sin estado\nexport const malo3: RespuestaResolucionV2 = {revision: 2, validacion: r0 as any, estado: 'resuelto', resultados: {metodo: '', tiempos: [], series: [], estados: {}, eventos: [], residuos: [], segundaLey: {motivo: '', generacionMinima: null, tolerancia: null, unidad: 'J/K'}}};\n`;
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ensv2-'));
const archivo = path.join(dir, 'comprobacion.ts');
fs.writeFileSync(archivo, fuente);
const programa = ts.createProgram([archivo], {strict: true, noEmit: true, target: ts.ScriptTarget.ES2022,
  module: ts.ModuleKind.ESNext, moduleResolution: ts.ModuleResolutionKind.Bundler, skipLibCheck: true,
  allowImportingTsExtensions: true, resolveJsonModule: true});
const errores = ts.getPreEmitDiagnostics(programa).filter(d => d.file && d.file.fileName.endsWith('comprobacion.ts'));
for (const d of errores.slice(0, 20)) {
  const {line} = d.file.getLineAndCharacterOfPosition(d.start);
  console.log(`  línea ${line + 1}: ${ts.flattenDiagnosticMessageText(d.messageText, '\n')}`);
}
assert.equal(errores.length, 0, `${errores.length} incompatibilidades de tipo`);
fs.rmSync(dir, {recursive: true, force: true});

// 2. Estados termodinamicos por el validador puntual del frontend.
const cache = new Map();
function cargar(n) {
  if (cache.has(n)) return cache.get(n);
  const m = {exports: {}};
  cache.set(n, m.exports);
  const js = ts.transpileModule(fs.readFileSync(path.join(raiz, 'frontend', 'app', 'motor', `${n}.ts`), 'utf8'),
    {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText;
  new Function('exports', 'module', 'require', js)(m.exports, m, r => cargar(r.slice(2)));
  return m.exports;
}
const puntual = cargar('contratoTermodinamica');
const caps = puntual.validarCapacidadesEstado(JSON.parse(fs.readFileSync(path.join(raiz, 'docs', 'ejemplos', 'motor-termodinamica-capacidades.json'), 'utf8')));
const capDe = m => caps.modelos.find(c => c.id === m.id && c.version === m.version);
const pol = {cantidad: 'sin_restriccion', cambioInterno: 'permitido', evaluacion: 'equilibrio_estable'};
let estados = 0;
for (const n of nombres) {
  const s = JSON.parse(fs.readFileSync(n, 'utf8'));
  const r = JSON.parse(fs.readFileSync(n.replace('-peticion', '-respuesta'), 'utf8'));
  let k = 0;
  for (const [vid, lista] of Object.entries(r.resultados?.estados ?? {})) {
    const vol = s.volumenes.find(v => v.id === vid);
    const modelo = s.paquetes.find(p => p.id === vol.paqueteId).modelo;
    const comps = s.componentes.filter(c => vol.componenteIds.includes(c.id));
    for (const m of lista) {
      const e = m.evaluacion;
      // solicitud puntual equivalente: U y V del propio estado (1 kg), composicion del estado
      const masas = Object.fromEntries(e.componentes.map(c => [String(c.id), c.masaMolarKgMol]));
      const Mg = Object.entries(e.composicionMolar).reduce((a, [id, x]) => a + x * masas[id], 0);
      const valores = Object.fromEntries(Object.entries(e.composicionMolar).map(([id, x]) => [id, {valor: x * masas[id] / Mg, unidad: 'kg'}]));
      const sp = {revision: 1, solicitudId: 'x', propietarioId: 'v2', componentes: comps,
        declaracion: {modelo, politica: pol, especificacion: {tipo: 'UV', U: {valor: e.mezcla.u, unidad: 'J'},
          V: {valor: e.mezcla.v, unidad: 'm3'}, cantidades: {base: 'masica', valores}}}};
      puntual.validarRespuestaEstado({revision: 1, solicitudId: 'x', modelo, estado: 'evaluado', evaluacion: e, diagnosticos: []},
        sp, capDe(modelo));
      k++;
    }
  }
  estados += k;
  console.log(`  ${path.basename(n).replace('-peticion.json', '')}: tipos y ${k} estado(s) termodinámico(s)`);
}
const puntuales = DIRECTORIOS.flatMap(d => fs.readdirSync(d).filter(f => /^motor-termodinamica-(mezcla|ideal|nrtl|lle|hielo).*-peticion\.json$/.test(f)).sort()
  .map(f => path.join(d, f)));
for (const n of puntuales) {
  const s = JSON.parse(fs.readFileSync(n, 'utf8'));
  const r = JSON.parse(fs.readFileSync(n.replace('-peticion', '-respuesta'), 'utf8'));
  assert.deepEqual(puntual.analizarSolicitudEstado(s), [], `${n}: solicitud`);
  puntual.validarRespuestaEstado(r, s, capDe(s.declaracion.modelo));
  console.log(`  ${path.basename(n).replace('-peticion.json', '')}: ${r.estado} validado`);
}
const diag = JSON.parse(fs.readFileSync(path.join(ejemplos, 'motor-termodinamica-diagrama-hielo.json'), 'utf8'));
assert.equal(diag.estado, 'evaluado');
assert.equal(diag.diagrama.lineas.length, 3);
console.log(`OK: ${nombres.length} pares v2 compilados, ${estados} estados por volumen y ${puntuales.length} ejemplos puntuales validados`);
