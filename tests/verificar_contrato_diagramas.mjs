// Comprueba con el compilador de TypeScript que las peticiones y respuestas REALES de diagramas
// (docs/ejemplos/motor-diagramas/, generadas por tests/generar_ejemplos_motor_diagramas.py) tienen exactamente
// los tipos de docs/contratos/contratoDiagramasEquilibrio.ts, con controles negativos, y comprueba invariantes
// que un lector puede verificar sin repetir la termodinamica: ningun segmento cruza un hueco, todo punto de un
// segmento esta certificado y es estable, los residuos publicados cumplen su tolerancia, las composiciones
// suman 1, la condicion fija coincide con el corte en SI y los puntos especiales apuntan a puntos existentes.
//
// Ejecutar desde la raiz del proyecto:
//   node tests/verificar_contrato_diagramas.mjs
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';

const raiz = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const ts = createRequire(path.join(raiz, 'frontend', 'package.json'))('typescript');
const ejemplos = path.join(raiz, 'docs', 'ejemplos', 'motor-diagramas');
const contrato = path.join(raiz, 'docs', 'contratos', 'contratoDiagramasEquilibrio').replaceAll('\\', '/');
const nombres = fs.readdirSync(ejemplos).filter(f => f.endsWith('-peticion.json')).sort();
assert.ok(nombres.length >= 8, 'faltan ejemplos: ejecuta tests/generar_ejemplos_motor_diagramas.py');

let fuente = `import type {SolicitudDiagrama,RespuestaDiagrama,CapacidadesDiagramas} from '${contrato}';\n`;
fuente += `export const cap: CapacidadesDiagramas = ${fs.readFileSync(path.join(ejemplos, 'motor-diagramas-capacidades.json'), 'utf8')};\n`;
nombres.forEach((n, i) => {
  const s = fs.readFileSync(path.join(ejemplos, n), 'utf8');
  const r = fs.readFileSync(path.join(ejemplos, n.replace('-peticion', '-respuesta')), 'utf8');
  // las peticiones de rechazo pueden no cumplir el tipo (tres componentes, huella falsa sigue siendo texto)
  const tipoS = n.includes('tres-componentes') ? 'unknown' : 'SolicitudDiagrama';
  fuente += `export const s${i}: ${tipoS} = ${s};\nexport const r${i}: RespuestaDiagrama = ${r};\n`;
});
fuente += `// @ts-expect-error estado fuera de la union\nexport const malo1: RespuestaDiagrama['estado'] = 'terminado';\n`;
fuente += `// @ts-expect-error corte Txy sin P\nexport const malo2: SolicitudDiagrama['corte'] = {tipo: 'Txy', T: {valor: 300, unidad: 'K'}};\n`;
fuente += `// @ts-expect-error fase limite con fraccion de fase (no es una FaseEvaluada)\nexport const malo3: RespuestaDiagrama['puntos'][number]['fases'][number] = {id: 'vapor-limite', tipo: 'vapor', composicionMolar: {}, fraccionMolar: 0};\n`;
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'diag-'));
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

// invariantes sobre cada respuesta real
let puntos = 0;
for (const n of nombres) {
  const r = JSON.parse(fs.readFileSync(path.join(ejemplos, n.replace('-peticion', '-respuesta')), 'utf8'));
  const ids = new Map(r.puntos.map(p => [p.id, p]));
  if (['invalido', 'no_soportado', 'incompleto'].includes(r.estado)) {
    assert.ok(r.diagnosticos.length && r.puntos.length === 0 && r.ramas.length === 0, `${n}: rechazo sin diagnostico o con puntos`);
    assert.ok(r.diagnosticos.every(d => typeof d.ruta === 'string' && d.codigo.startsWith('MOTOR_DIAG_')), `${n}: diagnostico sin ruta/codigo`);
    console.log(`  ${n.replace('-peticion.json', '')}: ${r.estado} (${r.diagnosticos.map(d => d.codigo).join(', ')})`);
    continue;
  }
  const corte = r.condicion.corteSI;
  for (const p of r.puntos) {
    assert.equal(p.certificado.estado, 'cumple', `${n}: punto ${p.id} sin certificar`);
    assert.equal(p.certificado.estabilidad.estado, 'estable', `${n}: punto ${p.id} inestable publicado`);
    for (const x of p.certificado.residuos) assert.ok(x.estado === 'cumple' && x.valor <= x.tolerancia || x.id === 'distincion_fases' && x.valor > x.tolerancia, `${n}: residuo ${x.id}`);
    for (const f of p.fases) assert.ok(Math.abs(Object.values(f.composicionMolar).reduce((a, b) => a + b, 0) - 1) < 1e-12, `${n}: suma`);
    if (corte.tipo === 'Txy') assert.ok(Math.abs(p.P / corte.P - 1) < 1e-14, `${n}: P del punto distinta del corte`);
    else assert.ok(Math.abs(p.T / corte.T - 1) < 1e-14, `${n}: T del punto distinta del corte`);
    puntos++;
  }
  for (const rama of r.ramas) for (const s of rama.segmentos) {
    assert.ok(s.puntoIds.every(i => ids.has(i)), `${n}: segmento con punto inexistente`);
    const xs = s.puntoIds.map(i => ids.get(i).xEje);
    assert.ok(xs.every((x, k) => k === 0 || x >= xs[k - 1]), `${n}: segmento no ordenado`);
    for (const h of r.cobertura.huecos) {
      const [a, b] = h.intervaloXEje;
      assert.ok(!(Math.max(s.xEje[0], a) < Math.min(s.xEje[1], b) - 1e-9), `${n}: segmento ${s.id} cruza un hueco ${h.motivo}`);
    }
  }
  for (const e of r.puntosEspeciales) if (e.puntoId) assert.ok(ids.has(e.puntoId), `${n}: especial ${e.id} sin punto`);
  const gaps = r.cobertura.huecos.map(h => h.motivo);
  if (r.estado === 'completo') assert.ok(gaps.every(m => m === 'sin_lv_estable'), `${n}: completo con huecos ${gaps}`);
  console.log(`  ${n.replace('-peticion.json', '')}: ${r.estado}, ${r.puntos.length} puntos, huecos [${gaps.join(', ')}], especiales [${r.puntosEspeciales.map(e => e.tipo).join(', ')}]`);
}
console.log(`OK: ${nombres.length} pares compilados contra el contrato de diagramas y ${puntos} puntos con invariantes verificados`);
