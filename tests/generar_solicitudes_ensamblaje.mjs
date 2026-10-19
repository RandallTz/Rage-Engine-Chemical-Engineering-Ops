// Genera solicitudes REALES de ensamblaje dinamico con el adaptador del frontend
// (frontend/app/motor/prepararEnsamblajeTermodinamico.ts), a partir de las hojas
// de prueba de energia, para comprobar que el backend acepta exactamente lo que
// el cliente prepara. Escribe tests/fixtures_ensamblaje/*.json. No modifica el
// frontend ni sus hojas.
//
// Ejecutar desde la raiz del proyecto:
//   node tests/generar_solicitudes_ensamblaje.mjs
import fs from 'node:fs';
import path from 'node:path';
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
const prep = cargar('prepararEnsamblajeTermodinamico'), estado = cargar('estadoTermodinamicoHoja');
const rec = cargar('recorridoEnergia'), vol = cargar('volumenControl'), termo = cargar('recorridoTermodinamico');
const casos = cargar('hojasPruebaEnergia').crearHojasPruebaEnergia();
const destino = path.join(raiz, 'tests', 'fixtures_ensamblaje');
fs.mkdirSync(destino, {recursive: true});
const escribir = (nombre, p) => {
  fs.writeFileSync(path.join(destino, `${nombre}.json`), JSON.stringify(p, null, 2) + '\n');
  console.log(`  ${nombre}: ${p.solicitud ? 'solicitud' : 'sin solicitud'}, ${p.diagnosticos.length} diagnosticos`);
};

const monofasico = {modelo: {id: 'agua-iapws95', version: '1'},
  politica: {cantidad: 'monofasico', cambioInterno: 'prohibido', evaluacion: 'equilibrio_estable'}};

// 1. Volumen rigido cerrado, U inicial (la hoja de energia 0 de Codex).
const base = prep.declararCierreDinamico(estado.identificarComponenteEstado(casos[0], 1, '7732-18-5'), 'dominio', monofasico);
const rigida = vol.guardarGeometria(vol.elegirVolumenControl(base, 'dominio', 'rigido'), 'dominio', {texto: '10', unidad: 'L'});
rigida.recorridoTermodinamico = termo.operarTermo(termo.recorridoTermoHoja(rigida), 'Retirar cierre manual explicitamente', {modelo: 'sin_declarar'});
rigida.energia.inicial = 'U';
rigida.energia.datos.energia_U0 = {texto: '1000', unidad: 'kJ'};
escribir('rigida_cerrada_U0', prep.prepararEnsamblajeTermodinamico(rigida, 'rigida-U0'));

// 2. La misma con T inicial.
const rigidaT = structuredClone(rigida);
rigidaT.energia.inicial = 'T';
escribir('rigida_cerrada_T0', prep.prepararEnsamblajeTermodinamico(rigidaT, 'rigida-T0'));

// 3. Abierta a presion prescrita (hoja 3), con el cierre manual retirado.
const abierta = structuredClone(prep.declararCierreDinamico(estado.identificarComponenteEstado(casos[3], 1, '7732-18-5'), 'dominio', monofasico));
abierta.recorridoTermodinamico = termo.operarTermo(termo.recorridoTermoHoja(abierta), 'Retirar cierre manual y densidad', {modelo: 'sin_declarar', densidadConstante: false});
abierta.config.datos.corriente_1_P = {texto: '2', unidad: 'bar'};
escribir('abierta_presion', prep.prepararEnsamblajeTermodinamico(abierta, 'abierta-P'));

// 4. Hoja 0 sin retirar u(T) manual: dos cierres en conflicto.
escribir('dos_cierres', prep.prepararEnsamblajeTermodinamico(base, 'dos-cierres'));

// 5. Rigida con presion adicional.
const rigidaP = vol.guardarGeometria(vol.elegirVolumenControl(abierta, 'dominio', 'rigido'), 'dominio', {texto: '.1', unidad: 'm3'});
escribir('rigida_con_P', prep.prepararEnsamblajeTermodinamico(rigidaP, 'rigida-P'));
