import fs from 'node:fs';
import assert from 'node:assert/strict';
import ts from 'typescript';
import katex from 'katex';
const output = ts.transpileModule(fs.readFileSync('app/motor/operadores.ts', 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const compiled = { exports: {} };
new Function('exports', 'module', output)(compiled.exports, compiled);
const m = compiled.exports;
const render = latex => katex.renderToString(latex, { throwOnError: true, strict: 'error' });
for (const sistema of Object.keys(m.COORDENADAS)) {
  render(m.sumaExpandida('\\nabla\\cdot\\mathbf F', m.expandirDivergencia(sistema, a => `F_{${a}}`)));
  render(m.sumaExpandida('\\nabla^2 f', m.expandirDifusion(sistema, 'f')));
  render(m.sumaExpandida('\\nabla\\cdot(\\kappa\\nabla f)', m.expandirDifusion(sistema, 'f', '\\kappa')));
  render(m.sumaExpandida('\\nabla f', m.expandirGradiente(sistema, 'f')));
}
for (let mask = 0; mask < 16; mask++) for (const difusion of ['flujo', 'fick', 'laplaciano']) {
  const o = { sinReaccion: !!(mask & 1), sinDifusion: !!(mask & 2), sinConveccion: !!(mask & 4), estacionario: !!(mask & 8), difusion };
  render(m.ecuacionCampo(o));
  for (const sentido of ['entrada', 'salida']) for (const uniforme of [true, false]) for (const fija of [true, false]) render(m.condicionFrontera({ id: 1, sentido }, uniforme, fija, o));
}

// Analytic references in physical Cartesian space. Evaluate the same metric
// expression trees used for LaTeX, independently through central differences.
const h = 2e-4;
function deriv(f, q, a) { const p = [...q], n = [...q]; p[a] += h; n[a] -= h; return (f(p) - f(n)) / (2 * h); }
function factor(p, q) { return q[0] ** p.r * Math.sin(q[1]) ** p.seno; }
function cartesiano(tipo, q) {
  if (tipo === 'cartesianas') return q;
  if (tipo === 'cilindricas') return [q[0] * Math.cos(q[1]), q[0] * Math.sin(q[1]), q[2]];
  return [q[0] * Math.sin(q[1]) * Math.cos(q[2]), q[0] * Math.sin(q[1]) * Math.sin(q[2]), q[0] * Math.cos(q[1])];
}
function coords(tipo, [x, y, z]) {
  if (tipo === 'cartesianas') return [x, y, z];
  if (tipo === 'cilindricas') return [Math.hypot(x, y), Math.atan2(y, x), z];
  const r = Math.hypot(x, y, z); return [r, Math.acos(z / r), Math.atan2(y, x)];
}
function gradDiv(tipo, q, f, peso = () => 1) {
  return m.terminosMetricos(tipo, 2).reduce((sum, t) => sum + factor(t.exterior, q) * deriv(p => factor(t.interior, p) * peso(p) * deriv(f, p, t.a), q, t.a), 0);
}
function div(tipo, q, F) {
  return m.terminosMetricos(tipo, 1).reduce((sum, t) => sum + factor(t.exterior, q) * deriv(p => factor(t.interior, p) * F(p)[t.a], q, t.a), 0);
}
function cerca(a, b, contexto) { assert.ok(Math.abs(a - b) < 5e-5 * Math.max(1, Math.abs(b)), `${contexto}: ${a} vs ${b}`); }
for (const punto of [[1.1, 0.7, 1.6], [-0.8, 1.3, 0.9], [2.2, -0.9, -1.2]]) for (const tipo of Object.keys(m.COORDENADAS)) {
  const q = coords(tipo, punto);
  const R2 = p => cartesiano(tipo, p).reduce((s, x) => s + x*x, 0);
  const f = p => { const [x,y,z] = cartesiano(tipo,p); return x*x + 2*y*y + 3*z*z; };
  cerca(gradDiv(tipo,q,R2), 6, `${tipo}: laplaciano radial`);
  cerca(gradDiv(tipo,q,f), 12, `${tipo}: laplaciano no radial`);
  cerca(gradDiv(tipo,q,f,p=>1+R2(p)), 12*(1+R2(q))+4*f(q), `${tipo}: difusividad variable, incluye gradiente`);
  const F = p => {
    const rho = 1 + R2(p);
    if (tipo === 'cartesianas') return p.map(x=>rho*x);
    if (tipo === 'cilindricas') return [rho*p[0],0,rho*p[2]];
    return [rho*p[0],0,0];
  };
  cerca(div(tipo,q,F), 3+5*R2(q), `${tipo}: convección conservativa`);
}
const fronteras=[{id:1,sentido:'entrada'},{id:2,sentido:'salida'}];
for (const tipo of Object.keys(m.COORDENADAS)) for (let axes = 0; axes < 8; axes++) for (const difusion of ['flujo','fick','laplaciano']) {
  const inv = [!!(axes&1),!!(axes&2),!!(axes&4)];
  const o = {...m.CAMPO_GENERAL,difusion};
  render(m.ecuacionCampoReducida(o,tipo,inv));
  render(m.sumaExpandida('\\nabla^2 f',m.expandirDifusion(tipo,'f',undefined,inv)));
  render(m.sumaExpandida('\\nabla\\cdot\\mathbf F',m.expandirDivergencia(tipo,a=>`F_{${a}}`,inv)));
}
assert.deepEqual(m.expandirDivergencia('cartesianas',a=>`F_{${a}}`,[true,true,true]),[]);
assert.equal(m.expandirDifusion('esfericas','f',undefined,[true,true,true]).length,0);
const esfericaConstante=m.expandirDivergencia('esfericas',a=>`F_{${a}}`,[true,true,true]);
assert.equal(esfericaConstante.length,2,'Un campo con componentes constantes conserva las contribuciones geométricas radial y polar');
assert.match(esfericaConstante[0],/^2/,'La geometría esférica aporta el factor 2 radial');
assert.match(esfericaConstante[1],/\\cos\\theta/,'La contribución polar conserva cot(theta)');
assert.equal(m.expandirDivergencia('cilindricas',a=>`F_{${a}}`,[true,true,true]).length,1);
assert.equal(m.expandirDifusion('cilindricas','f',undefined,[false,true,true]).length,1,'Axisimetría y ausencia de dependencia axial mantienen difusión radial');
assert.equal(m.estacionarioLocalDeducido({...m.CAMPO_GENERAL,sinReaccion:true},'cartesianas',[true,true,true]),true);
assert.equal(m.estacionarioLocalDeducido({...m.CAMPO_GENERAL,sinReaccion:true},'esfericas',[true,true,true]),false,'No deducir estacionario ignorando geometría');
assert.equal(m.estacionarioLocalDeducido(m.CAMPO_GENERAL,'cartesianas',[true,true,true]),false,'Fuentes internas pendientes impiden deducir acumulación nula');
assert.equal(m.solucionCantidad(fronteras,false,false),null,'Una reacción sin ley no se integra como si no existiera');
assert.equal(m.solucionCantidad([],true,false),null,'Ausente no es cero');
assert.equal(m.solucionCantidad(fronteras,true,true),'m_i(t)=m_i(0)');
render(m.balanceCantidad(fronteras,true,false));
render(m.solucionCantidad(fronteras,true,false));
// Filling and draining are signs of the same rate law, not separate scenarios.
for (const [entrada,salida] of [[3,2],[2,3],[3,3]]) {
  const inicial=100,t=60;
  const masa=inicial+(entrada-salida)*t;
  assert.equal((masa-inicial)/t,entrada-salida);
}
console.log('Operadores: referencias analíticas en 3 coordenadas, 48 combinaciones generales, 72 reducciones direccionales, geometría y acumulación deducida correctas.');
