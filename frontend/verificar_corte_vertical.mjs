// Corte vertical, último eslabón (docs/engine/vertical-slice.md): el resultado del compilador
// propio (tests/validar_corte_vertical.py lo escribe en docs/ejemplos/modelo-comun/) sale
// por la ruta HTTP y se grafica con el motor de gráficas único, sin código propio.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";
import ts from "typescript";

const AQUI = path.dirname(fileURLToPath(import.meta.url)), RAIZ = path.resolve(AQUI, "..");
// Relative imports are loaded too (the results reader imports its indexed-network reader); others stay stubs.
const cache = new Map();
const cargar = ruta => {
  if (cache.has(ruta)) return cache.get(ruta).exports;
  const js = ts.transpileModule(fs.readFileSync(ruta + ".ts", "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const m = { exports: {} }; cache.set(ruta, m);
  const requerir = spec => spec.startsWith(".") ? cargar(path.resolve(path.dirname(ruta), spec)) : ({});
  new Function("exports", "module", "require", js)(m.exports, m, requerir); return m.exports;
};
const { leerResultados } = cargar(path.join(AQUI, "motores/resultados/lector"));
const { datosGrafica, especificacionesPorOmision } = cargar(path.join(AQUI, "componentes/graficas/datos"));

// La ruta POST /modelo/resolver (la función del router, sin servidor) devuelve el mismo conjunto.
const r = spawnSync("python", ["-c", `
import sys, json, warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, '.')
from backend.api_modelo import resolver_modelo, validar
m = json.load(open('docs/ejemplos/modelo-comun/capa-calentamiento-benceno-tolueno.json', encoding='utf-8'))['modelo']
print(json.dumps({'validacion': validar({'modelo': m}), 'resultados': resolver_modelo({'modelo': m})}))`], { cwd: RAIZ, encoding: "utf8", maxBuffer: 1 << 28, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
if (r.status !== 0) throw new Error(r.stderr);
const { validacion, resultados } = JSON.parse(r.stdout);
const ejemplo = JSON.parse(fs.readFileSync(path.join(RAIZ, "docs/ejemplos/modelo-comun/corte-vertical-benceno-tolueno-resultados.json"), "utf8"));
let n = 0;
const ok = (v, m) => { n++; assert.ok(v, m); };
ok(validacion.relaciones.some(x => x.id === "equilibrio.A") && validacion.variables.includes("volumen.A.fase.vapor-1.tm"), "POST /modelo/validar: relaciones y variables de la capa, con el vapor desde el principio");
// The published result was generated on Windows; Linux libm gives the same integration within ~1e-13 relative
// (observed in CI on 6 Nov 2026: an event time 393.02647369376547 vs 393.0264736937146). Numbers are compared to
// 1e-9 relative (absolute floor 1e-12); keys, lengths, types, strings and every other value stay exact.
// One message reports a stability residual at round-off ("min tm = 1.07e-14" vs "9.78e-15"): that field alone
// is compared numerically, to 1e-10 absolute, and the rest of the message stays exact.
const REL_TOL = 1e-9, ABS_TOL = 1e-12, TM_TOL = 1e-10, TM_FIELD = /min tm = (-?[\d.]+(?:e[+-]?\d+)?)/;
const sameMessage = (a, b) => {
  const [ma, mb] = [TM_FIELD.exec(a), TM_FIELD.exec(b)];
  return Boolean(ma && mb) && a.replace(TM_FIELD, "") === b.replace(TM_FIELD, "") && Math.abs(Number(ma[1]) - Number(mb[1])) <= TM_TOL;
};
const differences = (a, b, at = "$", out = []) => {
  if (out.length >= 8) return out;
  if (typeof a === "number" && typeof b === "number") {
    if (!(a === b || Math.abs(a - b) <= Math.max(ABS_TOL, REL_TOL * Math.max(Math.abs(a), Math.abs(b))))) out.push(`${at}: fresh ${a} vs published ${b}`);
  } else if (a && b && typeof a === "object" && typeof b === "object" && Array.isArray(a) === Array.isArray(b)) {
    const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
    for (const key of keys) differences(a[key], b[key], `${at}.${key}`, out);
  } else if (typeof a === "string" && typeof b === "string" && sameMessage(a, b)) {
    return out;
  } else if (!isDeepStrictEqual(a, b)) out.push(`${at}: fresh ${JSON.stringify(a)} vs published ${JSON.stringify(b)}`);
  return out;
};
const diferencias = differences(resultados, ejemplo);
if (diferencias.length) console.error(diferencias.join("\n"));
ok(diferencias.length === 0, "POST /modelo/resolver: el mismo conjunto que la prueba del compilador");
leerResultados(resultados); n++;

const especs = especificacionesPorOmision(resultados);
ok(especs.length > 0, "gráficas por omisión");
for (const e of especs) ok(datosGrafica(resultados, e).ok, `especificación ${e.y.join(", ")} graficable`);
const betas = resultados.series.filter(s => s.id.endsWith(".beta")).map(s => s.id);
const d = datosGrafica(resultados, { id: "fases", titulo: "Fracción de cada fase candidata", x: { eje: "t" }, y: betas });
ok(d.ok && d.curvas.length === 2, "beta de TODAS las candidatas frente al tiempo: una curva por fase, presentes o no");
const vapor = d.curvas.find(c => c.id.includes("vapor"));
ok(vapor.y[0] === 0 && vapor.y.at(-1) === 1, "la curva del vapor empieza en 0 (líquido) y termina en 1 (todo vapor)");
const T = datosGrafica(resultados, { id: "T", x: { eje: "t" }, y: ["volumen.A.T"] });
ok(T.ok && T.ejeY.unidad === "K", "T(t) con su unidad del formato común");
ok(!datosGrafica(resultados, { id: "mezcla", x: { eje: "t" }, y: ["volumen.A.T", "volumen.A.H"] }).ok, "T y H no comparten eje: dimensiones distintas");
console.log(`Corte vertical (ruta y gráficas): ${n} comprobaciones correctas.`);
