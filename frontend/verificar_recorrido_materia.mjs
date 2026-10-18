import fs from 'node:fs';
import assert from 'node:assert/strict';
import ts from 'typescript';
import katex from 'katex';
const cache = new Map();
function cargar(nombre) {
  if (cache.has(nombre)) return cache.get(nombre);
  const modulo = { exports: {} };
  const codigo = ts.transpileModule(fs.readFileSync(`app/motor/${nombre}.ts`, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  new Function('exports', 'module', 'require', codigo)(modulo.exports, modulo, ruta => cargar(ruta.replace('./', '')));
  cache.set(nombre, modulo.exports); return modulo.exports;
}
const m = cargar('recorridoMateria'), op = cargar('operadores'), catalogo = cargar('catalogoMateria');
const render = latex => katex.renderToString(String.raw`\displaystyle ${latex}`, { throwOnError: true, strict: 'error' });
const actual = h => h.pasos[h.activo].formulacion;
const cambiar = (h, titulo, cambios) => m.recorridoMateria(h, { tipo: 'cambiar', titulo, cambios });
let h = m.iniciarRecorrido();
assert.equal(h.pasos.length, 1, 'Ninguna ruta de ejemplo precargada');
const inicial = JSON.stringify(h);
h = cambiar(h, 'Total antes de cualquier simplificación', { vista: 'cantidad' });
assert.equal(h.pasos.length, 2, 'No insertar pasos intermedios por omisión');
assert.match(m.balanceActual(actual(h)), /G_i\(t\).*C_i\(t\)/, 'Total no implica ausencia de fuentes');
assert.match(m.balanceActual(actual(h)), /Phi/, 'No hacer impermeable el resto de la frontera en silencio');
assert.equal(actual(h).cantidadVolumen, false, 'Ninguna reducción de tanque activada');
h = cambiar(h, 'Generación uniforme', { generacionUniforme: true });
assert.match(m.balanceActual(actual(h)), /gamma_i\(t\)V\(t\)/);
assert.match(m.balanceActual(actual(h)), /C_i\(t\)/, 'El consumo sigue siendo variable en el espacio');
h = cambiar(h, 'Volver a integral', { vista: 'integral' });
assert.match(m.balanceActual(actual(h)), /int_\{V\(t\)\}.*chi_i\(\\mathbf x,t\)/);
assert.match(m.balanceActual(actual(h)), /v_b/, 'Conservar transporte relativo a una frontera móvil');
assert.equal(JSON.stringify(h.pasos[0]), JSON.stringify(JSON.parse(inicial).pasos[0]), 'Los pasos pasados son inmutables');
const antesDeVolver = h;
h = m.recorridoMateria(h, { tipo: 'ir', indice: 1 });
assert.equal(h.pasos.length, 2, 'Volver elimina las filas posteriores de la hoja');
assert.equal(h.rehacer.length, 2, 'Rehacer es un búfer separado, no filas visibles');
assert.equal(m.siguientePaso(h), 2);
h = m.recorridoMateria(h, { tipo: 'rehacer' });
h = m.recorridoMateria(h, { tipo: 'rehacer' });
assert.deepEqual(h.pasos, antesDeVolver.pasos, 'Rehacer recupera las formulaciones exactas');
h = m.recorridoMateria(h, { tipo: 'ir', indice: 1 });
h = cambiar(h, 'Otra continuación', { fija: true });
assert.equal(h.pasos.length, 3, 'La continuación sustituye el trabajo cancelado');
assert.equal(h.pasos.at(-1).origen, 1);
assert.equal(h.rehacer.length, 0, 'La nueva edición descarta el futuro cancelado');
assert.equal(m.siguientePaso(h), -1);
assert.ok(!h.pasos.some(p=>p.titulo==='Volver a integral'));
const eliminado = m.recorridoMateria(h,{tipo:'ir',indice:h.pasos[2].origen});
assert.equal(eliminado.pasos.length,2,'Eliminar un paso restaura el anterior y retira sus dependientes');
assert.equal(actual(eliminado).fija,false);
assert.doesNotMatch(m.balanceIntegrado(actual(h)), /v_b/);
assert.equal(m.recorridoMateria(h, { tipo: 'cambiar', titulo: 'Sin cambio', cambios: { fija: true } }), h);

// Two orders of independent user operations must give the same equation,
// while the paper trail must preserve the chosen order rather than a recipe.
let a = m.iniciarRecorrido(), b = m.iniciarRecorrido();
a = cambiar(a, 'Sin difusión', { campo: { ...actual(a).campo, sinDifusion: true } });
a = cambiar(a, 'Integral', { vista: 'integral' });
b = cambiar(b, 'Integral', { vista: 'integral' });
b = cambiar(b, 'Sin difusión', { campo: { ...actual(b).campo, sinDifusion: true } });
assert.equal(m.balanceActual(actual(a)), m.balanceActual(actual(b)));
assert.notEqual(a.pasos[1].titulo, b.pasos[1].titulo);

const base = actual(m.iniciarRecorrido());
const general = { ...base, vista: 'cantidad' };
for (const rol of ['generacion','consumo']) {
  const f = { ...general, campo: { ...base.campo, [rol === 'generacion' ? 'sinConsumo' : 'sinGeneracion']: true } };
  const rhs = m.balanceActual(f);
  assert.match(rhs, rol === 'generacion' ? /\+G_i\(t\)/ : /-C_i\(t\)/);
  assert.doesNotMatch(rhs, rol === 'generacion' ? /C_i\(t\)/ : /G_i\(t\)/);
  render(m.balanceIntegrado(f));
}
const puro = { ...general, campo: { ...base.campo, sinGeneracion: true, sinConsumo: true } };
const fronteras = [{id:1,sentido:'entrada',constante:false},{id:2,sentido:'salida',constante:false}];
const fv = { ...puro, fronteras, restoImpermeable: true, cantidadVolumen: true };
assert.match(m.balanceTotal(fv), /frac\{d\}\{dt\}.*bar\\rho_i\(t\)V\(t\)/, 'Conservar la derivada de densidad media variable');
assert.match(m.balanceTotal({...fv,expandirProducto:true}), /V\(t\).*frac\{d\\bar\\rho_i\}/, 'Conservar V·d(rho_media)/dt al expandir');
assert.match(m.balanceTotal({...fv,fija:true}), /^V\\frac\{d\\bar\\rho_i\}/, 'Un dominio fijo elimina dV/dt, no d(rho_media)/dt');
const fvc = {...fv,densidadMediaConstante:true,densidadComunPuertos:true};
assert.equal(m.balanceTotal(fvc), String.raw`\frac{dV}{dt}=Q_{1}(t)-Q_{2}(t)`);
assert.equal(m.unidadBalance(fvc), 'm³/s');
assert.equal(m.acumulacionTotalNula(fvc), false, 'Densidad media constante con dominio móvil permite acumulación');
assert.equal(m.acumulacionTotalNula({...fvc,fija:true}), true);
assert.match(m.balanceTotal({...fvc,fija:true}), /^0=/);
const reactivo = {...fvc,campo:base.campo};
assert.match(m.balanceTotal(reactivo), /frac\{G_i\(t\)\}\{\\bar\\rho_i\}/, 'Conservar y convertir dimensionalmente la generación');
assert.match(m.balanceTotal(reactivo), /frac\{C_i\(t\)\}\{\\bar\\rho_i\}/, 'Conservar y convertir dimensionalmente el consumo');
assert.match(m.relacionesMateria(reactivo).join(' '), /j_i.*cdot.*n=0.*A_p/, 'La conversión de caudales declara ausencia de difusión en los puertos');
assert.match(m.balanceTotal({...fv,restoImpermeable:false}), /Phi/, 'El resto de la superficie sigue sin cerrar');
assert.match(m.balanceTotal({...puro,fronteras:[]}), /Phi/, 'Sin puertos, el intercambio desconocido permanece en la frontera completa');
assert.doesNotMatch(m.balanceTotal({...puro,fronteras:[]}), /sum_/, 'No duplicar el intercambio desconocido en puertos fantasma');
assert.doesNotMatch(m.balanceTotal({...puro,fronteras,restoImpermeable:true}), /Phi/);
assert.equal(op.solucionCantidad(fronteras,true,false), null, 'No integrar como constantes caudales variables');
const entradas = {...puro,fronteras:[...fronteras,{id:3,sentido:'entrada',constante:false}],restoImpermeable:true};
assert.match(m.balanceTotal(entradas), /dot m_\{i,1\}\(t\)\+\\dot m_\{i,3\}\(t\)/);

// Spatial source reference: gamma(x)=x² over [0,3] integrates to 9,
// whereas midpoint×volume gives 6.75. Uniformity is a separate assumption.
assert.equal(3**3/3,9); assert.notEqual((1.5**2)*3,9);
assert.match(m.balanceIntegrado(base), /gamma_i\(\\mathbf x,t\)/);
assert.doesNotMatch(m.balanceIntegrado(base), /gamma_i\(t\)V/);
assert.match(m.balanceIntegrado({...base,generacionUniforme:true}), /gamma_i\(t\)V/);
assert.match(m.balanceActual({...base,generacionUniforme:true}), /gamma_i\(t\)/, 'La hipótesis también simplifica la forma local');
assert.doesNotMatch(m.balanceActual({...base,generacionUniforme:true}), /gamma_i\(\\mathbf x,t\)/);
for (const coordenadas of Object.keys(op.COORDENADAS)) for (let mask=0;mask<8;mask++) for (const vista of Object.keys(m.FORMAS_MATERIA)) for (let source=0;source<4;source++) {
  const f = {...base,coordenadas,vista,invariantes:[!!(mask&1),!!(mask&2),!!(mask&4)],campo:{...base.campo,sinGeneracion:!!(source&1),sinConsumo:!!(source&2)}};
  render(m.balanceActual(f));
  m.relacionesMateria(f).forEach(render);
  assert.doesNotMatch(m.balanceActual(f), /aligned|\\\\/, 'No forzar una fila por término');
}
for (const f of [fv,{...fv,expandirProducto:true},fvc,reactivo]) { render(m.balanceActual(f)); m.relacionesMateria(f).forEach(render); }
assert.equal(m.relacionesNuevas(h.pasos[0]).length,0,'El punto de partida no declara hipótesis');
assert.deepEqual(m.recorridoMateria(h,{tipo:'reiniciar'}),m.iniciarRecorrido());
console.log('Hoja: orden libre, pasos cancelados retirados y recuperación con Rehacer, formas diferencial/integral/total, fuentes locales independientes, resto de frontera explícito, regla del producto y unidades; 288 combinaciones renderizadas.');

// Named components share geometry, but retain independent conservation fields.
let mezcla = m.iniciarRecorrido();
assert.deepEqual(actual(mezcla).componentes, []);
assert.equal(m.balancesComponentes(actual(mezcla)).length, 1);
assert.equal(m.balancesComponentes(actual(mezcla))[0].componente, null);
const agua = m.crearComponente(mezcla, 'Agua');
mezcla = cambiar(mezcla, 'Añadir agua', { componentes: [agua] });
const etanol = m.crearComponente(mezcla, 'Etanol');
mezcla = cambiar(mezcla, 'Añadir etanol', { componentes: [agua, etanol] });
const dos = actual(mezcla), historico = JSON.stringify(mezcla.pasos[2]);
assert.equal(m.balancesComponentes(dos).length, 2);
assert.deepEqual([agua.simbolo, etanol.simbolo], ['A', 'B']);
for (const vista of Object.keys(m.FORMAS_MATERIA)) for (const coordenadas of Object.keys(op.COORDENADAS)) for (const difusion of ['flujo','fick','laplaciano']) for (const expandida of [false,true]) {
  const f = {...dos,vista,coordenadas,expandida,fronteras,campo:{...dos.campo,difusion}};
  for (const {componente,latex} of m.balancesComponentes(f)) {
    render(latex);
    const otro = componente.simbolo === 'A' ? 'B' : 'A';
    assert.ok(latex.includes(`_{${componente.simbolo}}`), 'Balance con su propia especie');
    assert.ok(!latex.includes(`_{${otro}}`) && !latex.includes(`_{${otro},`), 'Ningún símbolo de otra especie en su conservación');
    assert.ok(!latex.includes('_i') && !latex.includes('_{i,'), 'Sin índice genérico en componentes declarados');
    assert.ok(!latex.includes('V_{A}') && !latex.includes('V_{B}'), 'Un solo dominio compartido');
  }
  m.relacionesFormulacion(f).forEach(render);
}
const totalDos = {...dos,vista:'cantidad',fronteras};
const [eqA,eqB] = m.balancesComponentes(totalDos).map(x=>x.latex);
assert.ok(eqA.includes(String.raw`\dot m_{A,1}(t)-\dot m_{A,2}(t)-\Phi_{A,\mathrm{resto}}+G_{A}(t)-C_{A}(t)`));
assert.ok(eqB.includes(String.raw`\dot m_{B,1}(t)-\dot m_{B,2}(t)-\Phi_{B,\mathrm{resto}}+G_{B}(t)-C_{B}(t)`));
for (const {latex} of m.balancesComponentes({...totalDos,restoImpermeable:true})) {
  assert.doesNotMatch(latex,/Phi/);
  assert.match(latex,/G_\{[AB]\}.*C_\{[AB]\}/,'Impermeabilidad no elimina fuentes internas');
}
const relaciones = m.relacionesMezcla(totalDos);
assert.ok(relaciones.includes('m=m_{A}+m_{B}'));
assert.ok(relaciones.includes(String.raw`\rho=\rho_{A}+\rho_{B}`));
assert.ok(relaciones.includes('w_{A}+w_{B}=1'));
assert.ok(relaciones.includes(String.raw`\mathbf j_{A}+\mathbf j_{B}=\mathbf0`));
assert.ok(relaciones.includes(String.raw`\dot m_{1}=\dot m_{A,1}+\dot m_{B,1}`));
assert.ok(!relaciones.some(x=>x.includes('dm/dt')), 'No añadir un balance total como conservación independiente');
const grupos = catalogo.variablesMateria(totalDos);
const vSim = grupos.volumen.flatMap(g=>g.variables.map(x=>x.simbolo));
const pSim = grupos.corrientes.flatMap(g=>g.variables.map(x=>x.simbolo));
assert.equal(vSim.filter(x=>x==='V(t)').length,1);
assert.ok(vSim.includes('m_{A}(t)') && vSim.includes('m_{B}(t)'));
assert.ok(!vSim.includes('Q_{1}(t)') && !vSim.includes(String.raw`\dot m_{A,1}(t)`));
assert.ok(pSim.includes('Q_{1}(t)') && pSim.includes(String.raw`\dot m_{A,1}(t)`) && pSim.includes(String.raw`\dot m_{B,1}(t)`));
assert.equal(pSim.filter(x=>x==='Q_{1}(t)').length,1);
assert.ok(!catalogo.variablesMateria({...totalDos,fronteras:[fronteras[0]]}).corrientes.flatMap(g=>g.variables).some(v=>v.simbolo===String.raw`\dot m_{B,p}(t)`), 'No catalogar puertos fantasma; su intercambio está en Phi');
[...grupos.volumen,...grupos.corrientes].forEach(g=>g.variables.forEach(v=>render(v.simbolo)));
grupos.notacion.forEach(v=>render(v.simbolo));
mezcla = cambiar(mezcla,'Renombrar B',{componentes:[agua,{...etanol,nombre:'Alcohol'}]});
assert.equal(actual(mezcla).componentes[1].id,etanol.id);
assert.equal(actual(mezcla).componentes[1].simbolo,'B');
assert.equal(JSON.stringify(mezcla.pasos[2]),historico);
mezcla = cambiar(mezcla,'Retirar B',{componentes:[agua]});
assert.equal(m.balancesComponentes(actual(mezcla)).length,1);
assert.equal(m.crearComponente(mezcla,'Sal').simbolo,'C','No reciclar identidades retiradas');
mezcla = m.recorridoMateria(mezcla,{tipo:'ir',indice:2});
assert.equal(actual(mezcla).componentes.length,2,'Volver restaura los componentes de ese paso');
mezcla = cambiar(mezcla,'Nueva continuación',{fija:true});
assert.equal(mezcla.pasos.length,4);
assert.equal(mezcla.rehacer.length,0);
assert.equal(mezcla.ultimoComponenteId,2);
assert.equal(mezcla.pasos.at(-1).origen,2);
assert.equal(m.crearComponente(mezcla,'Sal').simbolo,'C','Identidad conservada al eliminar pasos');
const muchos = {...dos,componentes:Array.from({length:27},(_,i)=>({id:i+1,nombre:`Especie ${i+1}`,simbolo:i<26?String.fromCharCode(65+i):'S27'}))};
assert.equal(m.balancesComponentes(muchos).length,27);
m.balancesComponentes(muchos).forEach(x=>render(x.latex));
console.log('Componentes: 54 configuraciones con dos conservaciones, identidades estables al renombrar/retirar/sustituir pasos, relaciones de mezcla y variables separadas por dominio/corriente; 27 especies renderizadas.');

// Cancelling the step that introduced a component must not recycle its identity.
let identidad = m.iniciarRecorrido();
identidad = cambiar(identidad,'A',{componentes:[m.crearComponente(identidad,'Agua')]});
identidad = cambiar(identidad,'B',{componentes:[...actual(identidad).componentes,m.crearComponente(identidad,'Etanol')]});
identidad = m.recorridoMateria(identidad,{tipo:'ir',indice:1});
assert.equal(m.crearComponente(identidad,'Sal').simbolo,'C');
identidad = cambiar(identidad,'Otra operación',{fija:true});
assert.equal(m.crearComponente(identidad,'Sal').simbolo,'C');
assert.deepEqual(identidad.pasos.map(p=>p.origen),[null,0,1]);
assert.equal(identidad.pasos.length,3);
assert.equal(m.recorridoMateria(identidad,{tipo:'rehacer'}),identidad);
