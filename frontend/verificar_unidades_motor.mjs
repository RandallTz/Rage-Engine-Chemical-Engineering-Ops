// La tabla de unidades del motor (app/motor/unidadesMotor.ts) frente al servicio
// único de unidades (core/unidades): misma conversión a SI y misma dimensión para
// cada unidad de cada magnitud. Prepara la sustitución de la tabla por el servicio.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const AQUI = path.dirname(fileURLToPath(import.meta.url)), RAIZ = path.resolve(AQUI, "..");
const js = ts.transpileModule(fs.readFileSync(path.join(AQUI, "app/motor/unidadesMotor.ts"), "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const m = { exports: {} }; new Function("exports", "module", "require", js)(m.exports, m, () => ({}));
const { UNIDADES_MOTOR, convertirUnidad } = m.exports;
const MAPA = { masa: "masa", tiempo: "tiempo", longitud: "longitud", volumen: "volumen", densidad: "densidad", velocidad: "velocidad",
  difusividad: "difusividad", caudal: "caudal_masico", caudal_molar: "caudal_molar", caudal_volumetrico: "caudal_volumetrico",
  tasa: "tasa_volumetrica_masica", flujo: "flujo_masico", energia: "energia", energia_especifica: "energia_especifica",
  capacidad_especifica: "capacidad_calorifica_especifica", potencia: "potencia", temperatura: "temperatura", presion: "presion" };
const pares = Object.entries(UNIDADES_MOTOR).flatMap(([mag, t]) => Object.keys(t).map(u => [mag, u]));
const r = spawnSync("python", ["-c", `
import sys, json
sys.path.insert(0, '.')
from core import unidades as un
e = json.load(sys.stdin); out = {}
for mag, u in e['pares']:
    i = un.interpretar(u)
    out[mag + '|' + u] = {'factor': i['factor'], 'desp': i['desplazamiento'], 'igualDim': i['dimension'] == un.dimension_de_magnitud(e['mapa'][mag])}
print(json.dumps(out))`], { cwd: RAIZ, input: JSON.stringify({ pares, mapa: MAPA }), encoding: "utf8", env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
if (r.status !== 0) throw new Error(r.stderr);
const s = JSON.parse(r.stdout);
let n = 0;
for (const [mag, u] of pares) {
  const x = s[`${mag}|${u}`];
  assert.ok(MAPA[mag], `magnitud ${mag} sin equivalente en el catálogo`); n++;
  assert.ok(x.igualDim, `${mag} [${u}]: dimensión distinta`); n++;
  for (const v of [0, 1, 37.5]) {
    const a = convertirUnidad(mag, v, u), b = x.factor * v + x.desp;
    assert.ok(Math.abs(a - b) <= 1e-12 * Math.max(Math.abs(a), Math.abs(b), 1), `${mag} [${u}] ${v}: motor ${a} frente a servicio ${b}`); n++;
  }
}
console.log(`Unidades del motor: ${n} comprobaciones correctas (${pares.length} unidades de ${Object.keys(UNIDADES_MOTOR).length} magnitudes iguales al servicio único).`);
