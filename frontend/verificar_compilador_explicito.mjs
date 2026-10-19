// Paso 5.1 (ARQUITECTURA_MOTOR.md §10): las hojas de materia del motor, llevadas al
// modelo común (motores/modelo/desdeHojaMotor.ts) y resueltas por el compilador
// común en Python (core/compilador/explicito.py, ruta POST /modelo/resolver).
// Para cada hoja de prueba sin campo espacial: el mismo resultado que el solver TS
// del motor y que la solución analítica de HOJAS_PRUEBA_MATERIA, con los dos
// métodos. Las hojas 1D se rechazan con su motivo (motor de discretización, 5.2).
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const AQUI = path.dirname(fileURLToPath(import.meta.url)), RAIZ = path.resolve(AQUI, "..");
const cache = new Map();
function cargar(ruta) {
  const archivo = fs.existsSync(ruta + ".ts") ? ruta + ".ts" : ruta;
  if (cache.has(archivo)) return cache.get(archivo);
  const m = { exports: {} }; cache.set(archivo, m.exports);
  const js = ts.transpileModule(fs.readFileSync(archivo, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  new Function("exports", "module", "require", "process", js)(m.exports, m, r => r.startsWith(".") ? cargar(path.resolve(path.dirname(archivo), r)) : (() => { throw new Error("dependencia externa: " + r); })(), { env: {} });
  cache.set(archivo, m.exports);
  return m.exports;
}
const { crearHojasPruebaMateria } = cargar(path.join(AQUI, "app/motor/hojasPruebaMateria"));
const { resolverMotor } = cargar(path.join(AQUI, "app/motor/integracionMotor"));
const { modeloDesdeHojaMotor } = cargar(path.join(AQUI, "motores/modelo/desdeHojaMotor"));
const { leerResultados } = cargar(path.join(AQUI, "motores/resultados/lector"));

const PUENTE = `
import sys, json, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, '.')
from fastapi import HTTPException
from backend.api_modelo import resolver_modelo
salida = []
for m in json.load(sys.stdin):
    try:
        salida.append({'ok': resolver_modelo({'modelo': m})})
    except HTTPException as e:
        salida.append({'error': e.detail})
print(json.dumps(salida))`;
function python(modelos) {
  const r = spawnSync("python", ["-c", PUENTE], { cwd: RAIZ, input: JSON.stringify(modelos), encoding: "utf8", maxBuffer: 1 << 28, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
  if (r.status !== 0) throw new Error(r.stderr);
  return JSON.parse(r.stdout);
}
const analiticas = [
  t => [100 + t], t => [100 - 2 * t], t => [.1 + .002 * t], () => [100], t => [100 - 2 * t],
  t => [Math.exp(-.2 * t), 1 - Math.exp(-.2 * t)],
];
let n = 0;
const ok = (v, m) => { n++; assert.ok(v, m); };
const interp = (xs, ys, x) => { if (x <= xs[0]) return ys[0]; for (let i = 1; i < xs.length; i++) if (x <= xs[i]) { const a = (x - xs[i - 1]) / (xs[i] - xs[i - 1]); return ys[i - 1] * (1 - a) + ys[i] * a; } return ys.at(-1); };

const hojas = crearHojasPruebaMateria(), casos = [];
for (const [i, hoja] of hojas.entries()) for (const metodo of ["rk45", "euler_implicito"]) {
  const h = structuredClone(hoja); h.config.metodo = metodo;
  const unoD = h.historial.pasos[h.historial.activo].formulacion.vista === "campo" && !h.historial.pasos[h.historial.activo].formulacion.invariantes.every(Boolean);
  if (unoD && metodo !== "rk45") continue;
  casos.push({ i, hoja: h, metodo, unoD, modelo: modeloDesdeHojaMotor(h) });
}
const respuestas = python(casos.map(c => c.modelo));
const informe = [];
for (const [k, c] of casos.entries()) {
  const r = respuestas[k], nombre = `${c.hoja.nombre} · ${c.metodo}`;
  if (c.unoD) { ok(r.error?.codigo === "no_soportado" && /discretización/.test(r.error.mensaje), `${nombre}: 1D rechazada con motivo (${r.error?.mensaje})`); continue; }
  ok(!!r.ok, `${nombre}: resuelta por /modelo/resolver (${JSON.stringify(r.error)})`);
  const res = leerResultados(r.ok); n++;
  const rm = await resolverMotor(c.hoja.historial.pasos[c.hoja.historial.activo].formulacion, c.hoja.config);
  const t = res.ejes[0].valores, campos = res.series;
  ok(res.estado === rm.estado, `${nombre}: mismo estado que el motor TS (${res.estado} / ${rm.estado})`);
  ok(Math.abs(t.at(-1) - rm.tiempos.at(-1)) <= 1e-6 * Math.max(1, rm.tiempos.at(-1)), `${nombre}: mismo tiempo final (${t.at(-1)} / ${rm.tiempos.at(-1)})`);
  let dTS = 0, dA = 0, escala = 0;
  for (const [j, s] of campos.entries()) for (const [q, x] of t.entries()) {
    const a = analiticas[c.i](x)[j], v = s.valores[q]; escala = Math.max(escala, Math.abs(a));
    dA = Math.max(dA, Math.abs(v - a)); dTS = Math.max(dTS, Math.abs(v - interp(rm.tiempos, rm.valores.map(f => f[j][0]), x)));
  }
  const tol = c.metodo === "rk45" ? 1e-7 : 1e-4;
  ok(dA <= tol * escala, `${nombre}: igual a la analítica (${(dA / escala).toExponential(2)} relativo)`);
  ok(dTS <= tol * escala, `${nombre}: igual al solver TS del motor (${(dTS / escala).toExponential(2)} relativo)`);
  if (rm.estado === "parcial") ok(res.eventos.some(e => e.codigo === "agotamiento"), `${nombre}: el agotamiento se publica como evento`);
  informe.push(`  ${nombre}: analítica ${(dA / escala).toExponential(1)}, motor TS ${(dTS / escala).toExponential(1)}`);
}
console.log(informe.join("\n"));
console.log(`Compilador explícito con las hojas del motor: ${n} comprobaciones correctas.`);
