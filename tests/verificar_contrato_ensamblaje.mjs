// Comprueba con el compilador de TypeScript que las peticiones y respuestas REALES
// del ensamblaje (docs/ejemplos/motor-ensamblaje-*, generadas desde los endpoints)
// tienen exactamente los tipos de frontend/app/motor/contratoEnsamblajeTermodinamico.ts:
// SolicitudEnsamblajeDinamico, RespuestaValidacionDinamica, RespuestaResolucionDinamica.
// Cada estado termodinamico publicado pasa ademas por validarRespuestaEstado del
// contrato puntual. No modifica el frontend.
//
// Ejecutar desde la raiz del proyecto:
//   node tests/verificar_contrato_ensamblaje.mjs
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ts = createRequire(path.join(raiz, 'frontend', 'package.json'))('typescript');
const ejemplos = path.join(raiz, 'docs', 'ejemplos');
const contrato = path.join(raiz, 'frontend', 'app', 'motor', 'contratoEnsamblajeTermodinamico').replaceAll('\\', '/');
const nombres = fs.readdirSync(ejemplos).filter(f => /^motor-ensamblaje-.*-peticion\.json$/.test(f)).sort();
assert.ok(nombres.length >= 10, 'faltan ejemplos: ejecuta tests/generar_ejemplos_motor_ensamblaje.py');

// 1. Tipos: un archivo .ts con cada par asignado a su tipo; strict, sin emitir.
let fuente = `import type {SolicitudEnsamblajeDinamico,RespuestaValidacionDinamica,RespuestaResolucionDinamica} from '${contrato}';\n`;
nombres.forEach((n, i) => {
  const s = fs.readFileSync(path.join(ejemplos, n), 'utf8');
  const r = fs.readFileSync(path.join(ejemplos, n.replace('-peticion', '-respuesta')), 'utf8');
  const tipo = n.includes('-resolver-') ? 'RespuestaResolucionDinamica' : 'RespuestaValidacionDinamica';
  fuente += `export const s${i}: SolicitudEnsamblajeDinamico = ${s};\nexport const r${i}: ${tipo} = ${r};\n`;
});
// Control negativo: estas asignaciones DEBEN fallar, o la comprobacion seria vacia.
fuente += `// @ts-expect-error estado fuera de la union\nexport const malo1: RespuestaResolucionDinamica['estado'] = 'terminado';\n`;
fuente += `// @ts-expect-error recuento sin campos obligatorios\nexport const malo2: RespuestaValidacionDinamica['recuento'] = {estado: 'listo'};\n`;
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ens-'));
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

// 2. Cada estado termodinamico publicado es una EvaluacionEstado valida del contrato puntual.
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
const caps = puntual.validarCapacidadesEstado(JSON.parse(fs.readFileSync(path.join(ejemplos, 'motor-termodinamica-capacidades.json'), 'utf8')));
let estados = 0;
const comp = {id: 1, nombre: 'Agua', simbolo: 'A', identidadQuimica: {cas: '7732-18-5'}};
const pol = {cantidad: 'sin_restriccion', cambioInterno: 'permitido', evaluacion: 'equilibrio_estable'};
for (const n of nombres) {
  const r = JSON.parse(fs.readFileSync(path.join(ejemplos, n.replace('-peticion', '-respuesta')), 'utf8'));
  const lista = [r.inicializacion?.estadoTermodinamico ?? r.validacion?.inicializacion?.estadoTermodinamico,
    ...(r.resultados?.estadosTermodinamicos ?? [])].filter(Boolean);
  for (const e of lista) {
    // Solicitud puntual equivalente (TP del propio estado, sin especificaciones que comparar).
    const s = {revision: 1, solicitudId: 'x', propietarioId: 'volumen:dominio', componentes: [comp],
      declaracion: {modelo: {id: 'agua-iapws95', version: '1'}, politica: pol,
        especificacion: {tipo: 'UV', U: {valor: e.mezcla.u, unidad: 'J'}, V: {valor: e.mezcla.v, unidad: 'm3'},
          cantidades: {base: 'masica', valores: {1: {valor: 1, unidad: 'kg'}}}}}};
    puntual.validarRespuestaEstado({revision: 1, solicitudId: 'x', modelo: {id: 'agua-iapws95', version: '1'},
      estado: 'evaluado', evaluacion: e, diagnosticos: []}, s, caps.modelos[0]);
    estados++;
  }
  console.log(`  ${n.replace('-peticion.json', '')}: tipos y ${lista.length} estado(s) termodinámico(s)`);
}
console.log(`OK: ${nombres.length} pares con los tipos del contrato de ensamblaje y ${estados} estados válidos para el lector puntual`);
