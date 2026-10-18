// Comprueba con el compilador de TypeScript que las peticiones y respuestas REALES con el paquete UNIFAC
// (docs/ejemplos/motor-unifac/, generadas por tests/generar_ejemplos_motor_unifac.py) tienen los tipos de
// docs/contratos/ (contratoEnsamblajeV2, contratoDiagramasEquilibrio, contratoContribucionGrupos), y que cada
// estado termodinamico publicado (puntual y por volumen/muestra) pasa validarRespuestaEstado del contrato
// puntual del frontend con la capacidad publicada del modelo. Comprueba ademas invariantes de la metadata de
// grupos y de los rechazos: codigo propio por dato ausente, sin resultados. No modifica el frontend.
//
// Ejecutar desde la raiz del proyecto:
//   node tests/verificar_contrato_unifac.mjs
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ts = createRequire(path.join(raiz, 'frontend', 'package.json'))('typescript');
const ejemplos = path.join(raiz, 'docs', 'ejemplos', 'motor-unifac');
const c = n => path.join(raiz, 'docs', 'contratos', n).replaceAll('\\', '/');
const leer = n => fs.readFileSync(path.join(ejemplos, n), 'utf8');
const json = n => JSON.parse(leer(n));
const todos = fs.readdirSync(ejemplos).filter(f => f.endsWith('-peticion.json')).sort();
const ens = todos.filter(f => f.startsWith('motor-ensamblaje-v2-'));
const diag = todos.filter(f => f.startsWith('motor-diagramas-'));
const punt = todos.filter(f => f.startsWith('motor-termodinamica-'));
assert.ok(ens.length >= 4 && diag.length >= 3 && punt.length >= 5, 'faltan ejemplos: ejecuta tests/generar_ejemplos_motor_unifac.py');

// 1. Tipos.
let fuente = `import type {SolicitudEnsamblajeV2,RespuestaValidacionV2,RespuestaResolucionV2,CapacidadesEnsamblajeV2} from '${c('contratoEnsamblajeV2')}';\n`;
fuente += `import type {SolicitudDiagrama,RespuestaDiagrama,CapacidadesDiagramas} from '${c('contratoDiagramasEquilibrio')}';\n`;
fuente += `import type {CoberturaGrupos} from '${c('contratoContribucionGrupos')}';\n`;
fuente += `export const capE: CapacidadesEnsamblajeV2 = ${leer('motor-ensamblaje-v2-capacidades.json')};\n`;
fuente += `export const capD: CapacidadesDiagramas = ${leer('motor-diagramas-capacidades.json')};\n`;
ens.forEach((n, i) => {
  const tipo = n.includes('-resolver-') ? 'RespuestaResolucionV2' : 'RespuestaValidacionV2';
  fuente += `export const es${i}: SolicitudEnsamblajeV2 = ${leer(n)};\nexport const er${i}: ${tipo} = ${leer(n.replace('-peticion', '-respuesta'))};\n`;
});
diag.forEach((n, i) => {
  fuente += `export const ds${i}: SolicitudDiagrama = ${leer(n)};\nexport const dr${i}: RespuestaDiagrama = ${leer(n.replace('-peticion', '-respuesta'))};\n`;
});
fuente += `// @ts-expect-error variante fuera de la union\nexport const malo1: CoberturaGrupos['variante'] = '2.0';\n`;
fuente += `// @ts-expect-error interaccion dirigida es un par de numeros\nexport const malo2: CoberturaGrupos['interaccionesDirigidasFaltantes'] = [['CH2', 'OH']];\n`;
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'unifac-'));
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

// 2. Metadata de grupos: misma cobertura en las dos rutas, evidencia predictiva, sin pares moleculares.
const capE = json('motor-ensamblaje-v2-capacidades.json');
const capD = json('motor-diagramas-capacidades.json');
const UNIFAC = ['unifac-original-public', 'unifac-dortmund-public', 'unifac-original-lle-public'];
for (const id of UNIFAC) {
  const pE = capE.paquetes.find(p => p.modelo.id === id);
  const pD = capD.paquetes.find(p => p.modelo.id === id);
  assert.ok(pE && pD, `${id}: publicado en ambas capacidades`);
  assert.deepEqual(pE.coberturaGrupos, pD.coberturaGrupos);
  assert.equal(pE.pares, undefined);
  assert.equal(pD.pares, null);
  for (const c of ['liquido_vapor', 'liquido_liquido'])
    assert.equal(pE.combinaciones.find(x => x.id === c).evidencia, 'cualitativa', `${id} ${c}: prediccion, no contrastada`);
  const cob = pE.coberturaGrupos;
  assert.ok(/^[0-9a-f]{64}$/.test(cob.datos.sha256_interacciones) && /^[0-9a-f]{64}$/.test(cob.datos.sha256_asignaciones));
  // las especies sin asignacion no se ofrecen como componentes del paquete
  assert.deepEqual([...pE.componentesCAS].sort(), cob.especies.map(e => e.cas).sort(), `${id}: componentesCAS = especies con asignacion`);
  for (const e of cob.especies) for (const g of e.subgrupos) assert.ok(Number.isInteger(g.cuenta) && g.cuenta >= 1);
  if (cob.datos.rango_T_datos) assert.deepEqual(pE.dominio.T, cob.datos.rango_T_datos, `${id}: dominio en T = rango de la tabla`);
  console.log(`  ${id}: ${cob.variante}, ${cob.especies.length} especies, sin asignacion [${cob.especiesSinAsignacion}], ` +
    `${cob.interaccionesDirigidasFaltantes.length} interacciones dirigidas faltantes`);
}
for (const p of capE.paquetes.filter(p => !p.modelo.id.startsWith('unifac-'))) assert.equal(p.coberturaGrupos, undefined);

// 3. Estados por el validador puntual del frontend.
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
const caps = puntual.validarCapacidadesEstado(json('motor-termodinamica-capacidades.json'));
const capDe = m => caps.modelos.find(x => x.id === m.id && x.version === m.version);
for (const id of UNIFAC) assert.ok(capDe({id, version: '1'}), `capacidad puntual de ${id} publicada`);
const CODIGOS = /^MOTOR_(ESTADO|ENS|DIAG)_UNIFAC_(ASIGNACION_AUSENTE|GRUPO_DESCONOCIDO|INTERACCION_AUSENTE)$/;
const RECHAZO = /^MOTOR_(ESTADO|ENS|DIAG)_(UNIFAC_(ASIGNACION_AUSENTE|GRUPO_DESCONOCIDO|INTERACCION_AUSENTE)|FUERA_DE_DOMINIO)$/;
for (const n of punt) {
  const s = JSON.parse(leer(n));
  const r = JSON.parse(leer(n.replace('-peticion', '-respuesta')));
  assert.deepEqual(puntual.analizarSolicitudEstado(s), [], `${n}: solicitud`);
  if (n.includes('rechazo')) {
    assert.ok(r.estado !== 'evaluado', `${n}: rechazo`);
    assert.ok(r.diagnosticos.some(d => RECHAZO.test(d.codigo)), `${n}: codigo propio (${r.diagnosticos.map(d => d.codigo)})`);
    assert.ok(!r.evaluacion);
  } else {
    puntual.validarRespuestaEstado(r, s, capDe(s.declaracion.modelo));
    assert.equal(r.estado, 'evaluado');
  }
  console.log(`  ${path.basename(n).replace('-peticion.json', '')}: ${r.estado}`);
}
const pol = {cantidad: 'sin_restriccion', cambioInterno: 'permitido', evaluacion: 'equilibrio_estable'};
let estados = 0;
for (const n of ens) {
  const s = JSON.parse(leer(n));
  const r = JSON.parse(leer(n.replace('-peticion', '-respuesta')));
  if (n.includes('rechazo')) {
    const d = (r.validacion ?? r).diagnosticos;
    assert.ok(d.some(x => CODIGOS.test(x.codigo)), `${n}: codigo de dato ausente`);
    assert.ok(!r.resultados);
    console.log(`  ${path.basename(n).replace('-peticion.json', '')}: rechazo con codigo propio`);
    continue;
  }
  assert.equal(r.resultados.certificacion.estado, 'cumple', `${n}: certificacion`);
  let k = 0;
  for (const [vid, lista] of Object.entries(r.resultados.estados)) {
    const vol = s.volumenes.find(v => v.id === vid);
    const modelo = s.paquetes.find(p => p.id === vol.paqueteId).modelo;
    const comps = s.componentes.filter(x => vol.componenteIds.includes(x.id));
    for (const m of lista) {
      const e = m.evaluacion;
      const masas = Object.fromEntries(e.componentes.map(x => [String(x.id), x.masaMolarKgMol]));
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
  const huellas = (r.resultados.procedenciaModelo ?? []).map(p => p.huella);
  assert.ok(huellas.length >= 1 && huellas.every(h => typeof h === 'string' && h.length >= 64), `${n}: procedenciaModelo con huella`);
  estados += k;
  console.log(`  ${path.basename(n).replace('-peticion.json', '')}: ${r.estado}, ${k} estado(s) validados`);
}

// 4. Diagramas: evidencia cualitativa, huella del paquete y rechazos con codigo.
for (const n of diag) {
  const r = JSON.parse(leer(n.replace('-peticion', '-respuesta')));
  if (n.includes('rechazo')) {
    assert.equal(r.estado, 'no_soportado');
    assert.ok(r.diagnosticos.some(d => CODIGOS.test(d.codigo)), `${n}: codigo de dato ausente`);
    assert.equal(r.puntos.length, 0);
  } else {
    assert.equal(r.evidencia.nivel, 'cualitativa');
    assert.ok(UNIFAC.includes(r.identidad.modelo.id));
    for (const p of r.puntos) for (const f of p.fases) {
      const suma = Object.values(f.composicionMolar).reduce((a, x) => a + x, 0);
      assert.ok(Math.abs(suma - 1) < 1e-12, `${n} ${p.id}: composicion suma ${suma}`);
    }
  }
  console.log(`  ${path.basename(n).replace('-peticion.json', '')}: ${r.estado}, ${r.puntos.length} puntos`);
}
console.log(`OK: ${ens.length} ensamblajes (${estados} estados), ${punt.length} puntuales y ${diag.length} diagramas UNIFAC verificados`);
