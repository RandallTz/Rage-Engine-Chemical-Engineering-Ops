// El Resolver del Engine (app/motor/resolverEngine.ts) calcula en el Engine común del servidor.
// Para cada hoja de prueba que llega a él, el ResultadoMotor traducido del resultado común es el
// mismo que daba el solver del navegador, campo por campo: tiempos, estados, estado final, identidad
// de cada estado, series evaluadas de energía (T, Q, caudales, entalpías, trabajo de frontera) y
// cierres de presupuesto. Y las hojas que no llegan siguen en el solver del navegador.
// Transporte: la función de la ruta POST /modelo/resolver, sin servidor.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";
import ts from "typescript";

const AQUI = path.dirname(fileURLToPath(import.meta.url)), RAIZ = path.resolve(AQUI, "..");
const cache = new Map();
function cargar(ruta) {
  const archivo = fs.existsSync(ruta + ".ts") ? ruta + ".ts" : ruta;
  if (cache.has(archivo)) return cache.get(archivo);
  const m = { exports: {} }; cache.set(archivo, m.exports);
  const js = ts.transpileModule(fs.readFileSync(archivo, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText;
  new Function("exports", "module", "require", "process", js)(m.exports, m, r => {
    if (!r.startsWith(".")) throw new Error("dependencia externa: " + r);
    const p = path.resolve(path.dirname(archivo), r);
    if (p.endsWith(".json")) return { __esModule: true, default: JSON.parse(fs.readFileSync(p, "utf8")) };
    return cargar(p);
  }, { env: {} });
  cache.set(archivo, m.exports); return m.exports;
}
const motor = n => cargar(path.join(AQUI, "app/motor", n));
const { resolverHojaEngine, resuelveEngineComun, MOTOR_ENGINE_COMUN } = motor("resolverEngine");
const { resolverHoja } = motor("modeloHojaMotor");

const PUENTE = `
import sys, json, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, '.')
from fastapi import HTTPException
from backend.api_modelo import resolver_modelo
try:
    print(json.dumps(resolver_modelo(json.load(sys.stdin))))
except HTTPException as e:
    print(json.dumps({'__http__': e.status_code, 'detail': e.detail}))`;
const transporte = async modelo => {
  const r = spawnSync("python", ["-c", PUENTE], { cwd: RAIZ, input: JSON.stringify({ modelo }), encoding: "utf8", maxBuffer: 1 << 28, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
  if (r.status !== 0) throw new Error(r.stderr);
  const x = JSON.parse(r.stdout);
  if (x.__http__) throw new Error(`El Engine no puede resolver esta hoja: ${x.detail?.mensaje}`);
  return x;
};

const hojas = [...motor("hojasPruebaMateria").crearHojasPruebaMateria(), ...motor("hojasPruebaEnergia").crearHojasPruebaEnergia(),
  ...motor("hojasPruebaAcoplamiento").crearHojasPruebaAcoplamiento(), ...motor("hojasPruebaAcoplamiento").crearHojasPruebaMulticomponente()];
let n = 0;
const ok = (v, m) => { n++; assert.ok(v, m); };
const interp = (xs, ys, x) => { if (x <= xs[0]) return ys[0]; for (let i = 1; i < xs.length; i++) if (x <= xs[i]) { const a = (x - xs[i - 1]) / (xs[i] - xs[i - 1]); return ys[i - 1] * (1 - a) + ys[i] * a; } return ys.at(-1); };
const relativo = (a, b, ta, tb) => { let d = 0, e = 0; ta.forEach((t, k) => { const ref = interp(tb, b, t); d = Math.max(d, Math.abs(a[k] - ref)); e = Math.max(e, Math.abs(ref)); }); return d / Math.max(e, 1e-300); };
const informe = [];
let comunes = 0, locales = 0;
for (const h of hojas) {
  if (!resuelveEngineComun(h)) {
    locales++;
    const r = await resolverHojaEngine(h);
    ok(r.motor !== MOTOR_ENGINE_COMUN, `${h.nombre}: no llega al Engine común y la resuelve el solver del navegador`);
    continue;
  }
  comunes++;
  const e = await resolverHojaEngine(h, { transporte }), t = await resolverHoja(h);
  ok(e.motor === MOTOR_ENGINE_COMUN, `${h.nombre}: la resuelve el Engine común`);
  ok(e.estado === t.estado, `${h.nombre}: mismo estado (${e.estado} / ${t.estado})`);
  ok(Math.abs(e.tiempos.at(-1) - t.tiempos.at(-1)) <= 1e-7 * Math.max(1, t.tiempos.at(-1)), `${h.nombre}: mismo tiempo final (${e.tiempos.at(-1)} / ${t.tiempos.at(-1)})`);
  ok(isDeepStrictEqual(e.componentes, t.componentes) && e.unidadEstado === t.unidadEstado && e.firma === t.firma, `${h.nombre}: misma identidad de estados, unidad y firma`);
  ok(isDeepStrictEqual(e.variablesNumericas, t.variablesNumericas) && isDeepStrictEqual(e.estadosAcoplados, t.estadosAcoplados), `${h.nombre}: mismos descriptores de estado`);
  let peor = 0;
  for (let j = 0; j < t.valores[0].length; j++) peor = Math.max(peor, relativo(e.valores.map(f => f[j][0]), t.valores.map(f => f[j][0]), e.tiempos, t.tiempos));
  ok(peor < 1e-6, `${h.nombre}: estados iguales al solver del navegador (${peor.toExponential(1)})`);
  const escala = Math.max(...e.valores.flat(2).map(Math.abs), 1);
  ok(e.conservacion.length === t.conservacion.length && e.conservacion.every(x => Math.abs(x) < 1e-8 * escala), `${h.nombre}: cierre del presupuesto de cada estado (${e.conservacion.map(x => x.toExponential(1)).join(", ")})`);
  if (t.conservacionGlobal) ok(e.conservacionGlobal?.length === t.conservacionGlobal.length && e.conservacionGlobal.every((q, i) => q.id === t.conservacionGlobal[i].id && q.nombre === t.conservacionGlobal[i].nombre && Math.abs(q.residuo) < 1e-8 * escala),
    `${h.nombre}: cierre global por componente (${e.conservacionGlobal?.map(q => q.residuo.toExponential(1)).join(", ")})`);
  if (t.seriesEvaluadas) {
    ok(isDeepStrictEqual(e.seriesEvaluadas.map(s => [s.id, s.unidad]), t.seriesEvaluadas.map(s => [s.id, s.unidad])), `${h.nombre}: mismo catálogo de series evaluadas`);
    let peorS = 0, cual = "";
    for (const s of t.seriesEvaluadas) { const x = e.seriesEvaluadas.find(q => q.id === s.id); const d = Math.max(...s.valores.map(Math.abs)) === 0 ? Math.max(...x.valores.map(Math.abs)) : relativo(x.valores, s.valores, e.tiempos, t.tiempos); if (d > peorS) { peorS = d; cual = s.id; } }
    ok(peorS < 1e-6, `${h.nombre}: series evaluadas (T, Q, caudales, entalpías, trabajo) iguales (${peorS.toExponential(1)} en ${cual})`);
    ok(isDeepStrictEqual(e.trazabilidadEnergia, t.trazabilidadEnergia) && isDeepStrictEqual(e.balancesEjecutados, t.balancesEjecutados), `${h.nombre}: misma trazabilidad energética`);
  }
  informe.push(`  ${h.nombre}: estados ${peor.toExponential(1)}`);
}
console.log(informe.join("\n"));
console.log(`Resolver del Engine: ${n} comprobaciones correctas (${comunes} hojas en el Engine común, ${locales} en el solver del navegador).`);
