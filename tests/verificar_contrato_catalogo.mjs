// Comprueba con el compilador de TypeScript que la respuesta REAL de GET /motor/catalogo
// (docs/ejemplos/motor-catalogo/, generada por tests/generar_ejemplos_motor_catalogo.py) tiene los tipos de
// docs/contratos/contratoCatalogo.ts, con controles negativos, y comprueba invariantes que un lector puede
// verificar sin repetir la termodinamica: identidad unica, especies de cada paquete en el orden del catalogo,
// admision coherente con las capacidades puntuales publicadas, faltantes solo en especies no admitidas, y
// rechazos de admision con su codigo (incluido el limite puro, F9-R3). No modifica el frontend.
//
// Ejecutar desde la raiz del proyecto:
//   node tests/verificar_contrato_catalogo.mjs
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ts = createRequire(path.join(raiz, 'frontend', 'package.json'))('typescript');
const ejemplos = path.join(raiz, 'docs', 'ejemplos', 'motor-catalogo');
const contrato = path.join(raiz, 'docs', 'contratos', 'contratoCatalogo').replaceAll('\\', '/');
const leer = n => fs.readFileSync(path.join(ejemplos, n), 'utf8');

const c2 = n => path.join(raiz, 'docs', 'contratos', n).replaceAll('\\', '/');
const todos = fs.readdirSync(ejemplos).filter(f => f.endsWith('-peticion.json')).sort();
let fuente = `import type {CatalogoMotor,SustanciaCatalogo,PaqueteCatalogo,SustitucionDatosPuros} from '${contrato}';\n`;
fuente += `import type {SolicitudEnsamblajeV2,RespuestaValidacionV2,RespuestaResolucionV2} from '${c2('contratoEnsamblajeV2')}';\n`;
fuente += `import type {SolicitudDiagrama,RespuestaDiagrama} from '${c2('contratoDiagramasEquilibrio')}';\n`;
fuente += `export const cat: CatalogoMotor = ${leer('motor-catalogo.json')};\n`;
todos.filter(f => f.startsWith('motor-ensamblaje-v2-')).forEach((n, i) => {
  const tipo = n.includes('-resolver-') ? 'RespuestaResolucionV2' : 'RespuestaValidacionV2';
  fuente += `export const es${i}: SolicitudEnsamblajeV2 = ${leer(n)};\nexport const er${i}: ${tipo} = ${leer(n.replace('-peticion', '-respuesta'))};\n`;
});
todos.filter(f => f.startsWith('motor-diagramas-')).forEach((n, i) => {
  fuente += `export const ds${i}: SolicitudDiagrama = ${leer(n)};\nexport const dr${i}: RespuestaDiagrama = ${leer(n.replace('-peticion', '-respuesta'))};\n`;
});
fuente += `// @ts-expect-error masa molar no es sustituible\nexport const malo4: SustitucionDatosPuros = {'64-17-5': {masa_molar: {valor: 0.05}}};\n`;
fuente += `// @ts-expect-error toda sustitucion lleva fuente\nexport const malo5: SustitucionDatosPuros = {'64-17-5': {volumen_liquido: {valor: 60, unidad: 'cm3/mol'}}};\n`;
fuente += `// @ts-expect-error revision distinta\nexport const malo1: CatalogoMotor['revision'] = 2;\n`;
fuente += `// @ts-expect-error estado de datos fuera de la union\nexport const malo2: SustanciaCatalogo['datosPuros']['estado'] = 'parcial';\n`;
fuente += `// @ts-expect-error codigo de admision fuera de la union\nexport const malo3: PaqueteCatalogo['especies'][number]['faltantes'][number]['codigo'] = 'FALTA';\n`;
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'cat-'));
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

const cat = JSON.parse(leer('motor-catalogo.json'));
const caps = JSON.parse(leer('motor-termodinamica-capacidades.json'));
const ids = cat.sustancias.map(s => s.id);
assert.equal(new Set(ids).size, ids.length, 'identidad unica');
for (const s of cat.sustancias) {
  assert.equal(s.id, s.cas);
  assert.ok(s.masaMolar.valor > 0 && s.masaMolar.unidad === 'kg/mol' && s.masaMolar.fuente);
  if (s.datosPuros.estado === 'completos') {
    assert.equal(s.datosPuros.faltantes.length, 0);
    assert.ok(/^sha256:[0-9a-f]{64}$/.test(s.datosPuros.huella));
    for (const p of s.datosPuros.propiedades) assert.ok(p.unidad && p.fuente, `${s.id} ${p.id}: unidad y fuente`);
  } else assert.ok(s.datosPuros.faltantes.length > 0);
}
for (const p of cat.paquetes) {
  assert.deepEqual(p.especies.map(e => e.cas), ids, `${p.modelo.id}: una entrada por sustancia, en orden`);
  for (const e of p.especies) assert.equal(e.admitida, e.faltantes.length === 0, `${p.modelo.id} ${e.cas}: admitida <=> sin faltantes`);
  const cap = caps.modelos.find(m => m.id === p.modelo.id && m.version === p.modelo.version);
  assert.ok(cap, `${p.modelo.id}: tiene capacidad puntual`);
  assert.deepEqual(p.especies.filter(e => e.admitida).map(e => e.cas).sort(), [...cap.componentesCAS].sort(),
    `${p.modelo.id}: admitidas = componentesCAS publicados`);
  assert.deepEqual(p.operaciones.estado.especificaciones, cap.especificaciones);
  console.log(`  ${p.modelo.id}: ${p.especies.filter(e => e.admitida).length}/${ids.length} admitidas; ` +
    `requisitos por especie [${p.requisitos.porEspecie}]`);
}
const RECHAZO = /^MOTOR_(ESTADO|ENS|DIAG)_(COMPONENTE_NO_SOPORTADO|DATO_PURO_AUSENTE|PARAMETRO_AUSENTE|UNIFAC_ASIGNACION_AUSENTE|UNIFAC_GRUPO_DESCONOCIDO|SUSTITUCION_NO_ADMITIDA|SUSTITUCION_INVALIDA|REFERENCIAS_INCOMPATIBLES)$/;
const casos = todos.filter(f => f.startsWith('motor-termodinamica-'));
for (const n of todos.filter(f => !f.startsWith('motor-termodinamica-'))) {
  const r = JSON.parse(leer(n.replace('-peticion', '-respuesta')));
  if (n.includes('rechazo')) {
    assert.ok(((r.validacion ?? r).diagnosticos).some(d => RECHAZO.test(d.codigo)), `${n}: rechazo con codigo`);
    assert.ok(!r.resultados);
  } else if (n.startsWith('motor-ensamblaje-v2-')) {
    assert.equal(r.resultados.certificacion.estado, 'cumple', `${n}: certificacion`);
    assert.ok(r.resultados.procedenciaModelo.every(p => /^sha256:/.test(p.huella)));
  } else assert.equal(r.estado, 'completo', n);
  console.log(`  ${n.replace('-peticion.json', '')}: ${r.estado ?? 'validado'}`);
}
for (const n of casos) {
  const r = JSON.parse(leer(n.replace('-peticion', '-respuesta')));
  if (n.includes('rechazo')) {
    assert.equal(r.estado, 'no_soportado', n);
    assert.ok(r.diagnosticos.some(d => RECHAZO.test(d.codigo)), n);
    assert.ok(!r.evaluacion);
  } else assert.equal(r.estado, 'evaluado', n);
  console.log(`  ${n.replace('-peticion.json', '')}: ${r.estado} ${r.diagnosticos.map(d => d.codigo).join(' ')}`);
}
console.log(`OK: catalogo de ${ids.length} sustancias y ${cat.paquetes.length} paquetes; ${casos.length} casos puntuales; ` +
  `${todos.length - casos.length} ensamblajes y diagramas`);
