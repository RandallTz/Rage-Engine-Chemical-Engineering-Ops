import fs from 'node:fs';
import assert from 'node:assert/strict';
import ts from 'typescript';
import katex from 'katex';

const code = ts.transpileModule(fs.readFileSync('app/motor/balanceModular.ts', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS },
}).outputText;
const compiled = { exports: {} };
new Function('exports', 'module', code)(compiled.exports, compiled);
const { balanceVolumen, coeficientesGlobales, definicionAportacion, terminosVolumen, terminoActivo } = compiled.exports;

// Directed cycle plus a branch. A negative internal flow reverses the physical
// direction without changing the identity shared by the two equations.
const modelo = {
  volumenes: [1, 2, 3, 4].map(id => ({ id, nombre: `Sistema ${id}` })),
  conexiones: [{ id: 1, desde: 1, hacia: 2 }, { id: 2, desde: 2, hacia: 3 },
    { id: 3, desde: 3, hacia: 1 }, { id: 4, desde: 1, hacia: 3 }],
  aportaciones: [
    { id: 1, volumen: 1, familia: 'entrada', naturaleza: 'constante' },
    { id: 2, volumen: 3, familia: 'salida', naturaleza: 'convectiva' },
    { id: 3, volumen: 2, familia: 'entrada', naturaleza: 'difusiva' },
    { id: 4, volumen: 4, familia: 'generacion', naturaleza: 'reaccion' },
    { id: 5, volumen: 4, familia: 'consumo', naturaleza: 'reaccion' },
  ],
};
const valores = { a1: 5, a2: 2, a3: 3, a4: 1, a5: 1, c1: 7, c2: -2, c3: 4, c4: 0.5 };
for (let mask = 0; mask < 8; mask++) {
  const s = { sinReaccion: !!(mask & 1), sinDifusion: !!(mask & 2), sinAcumulacion: !!(mask & 4) };
  for (const v of modelo.volumenes) katex.renderToString(balanceVolumen(modelo, v.id, s), { throwOnError: true, strict: 'error' });
  const coeffs = coeficientesGlobales(modelo, s);
  for (const c of modelo.conexiones) assert.equal(coeffs.get(`c${c.id}`), 0, 'Toda conexión debe cancelarse globalmente');
  const sumLocal = modelo.volumenes.flatMap(v => terminosVolumen(modelo, v.id))
    .filter(t => terminoActivo(t, s)).reduce((sum, t) => sum + (['entrada', 'generacion'].includes(t.familia) ? 1 : -1) * valores[t.clave], 0);
  assert.equal(sumLocal, s.sinDifusion ? 3 : 6, 'La suma de balances depende solo de fronteras y fuentes externas');
}
for (const a of modelo.aportaciones) katex.renderToString(definicionAportacion(a), { throwOnError: true, strict: 'error' });
const vacio = { volumenes: [{ id: 1, nombre: 'Sistema 1' }], aportaciones: [], conexiones: [] };
assert.match(balanceVolumen(vacio, 1, { sinReaccion: false, sinDifusion: false, sinAcumulacion: false }), /E_\{i,1\}/, 'Ausente no significa cero');
const salidaDoble = { ...modelo, aportaciones: [...modelo.aportaciones, { id: 6, volumen: 3, familia: 'salida', naturaleza: 'constante' }] };
assert.match(balanceVolumen(salidaDoble, 3, { sinReaccion: true, sinDifusion: false, sinAcumulacion: false }), /-\\left\(/, 'El signo de salida debe afectar a todas las aportaciones');
console.log('Balance modular: cancelación de corrientes, signos, flujos inversos, supuestos y KaTeX correctos.');
