// Formato común de resultados y motor de gráficas único (docs/contracts/results-format.md).
// Tres motores distintos -> el mismo formato -> la misma función de gráficas:
//   1. solver TS del motor (hojas de prueba de materia), con dimensiones del servicio de unidades;
//   2. ensamblaje v2 del backend (adaptador Python), con sus ejemplos;
//   3. simulación del núcleo de adimensionalización (publica el formato directamente).
// Ningún camino de código distingue el origen: si una gráfica sale, sale igual.
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
  if (archivo.endsWith(".json")) { const j = { __esModule: true, default: JSON.parse(fs.readFileSync(archivo, "utf8")) }; cache.set(archivo, j); return j; }
  const m = { exports: {} }; cache.set(archivo, m.exports);
  const js = ts.transpileModule(fs.readFileSync(archivo, "utf8"), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  new Function("exports", "module", "require", "process", js)(m.exports, m, r => r.startsWith(".") ? cargar(path.resolve(path.dirname(archivo), r)) : (() => { throw new Error("dependencia externa: " + r); })(), { env: {} });
  cache.set(archivo, m.exports);
  return m.exports;
}
const { crearHojasPruebaMateria } = cargar(path.join(AQUI, "app/motor/hojasPruebaMateria"));
const { resolverMotor } = cargar(path.join(AQUI, "app/motor/integracionMotor"));
const { resultadosDesdeMotor, unidadesDeMotor } = cargar(path.join(AQUI, "motores/resultados/desdeMotor"));
const { leerResultados } = cargar(path.join(AQUI, "motores/resultados/lector"));
const { datosGrafica, especificacionesPorOmision } = cargar(path.join(AQUI, "componentes/graficas/datos"));

const PUENTE = `
import sys, json, glob
sys.path.insert(0, '.')
from core import unidades as un
from core.unidades.servicio import dimension_json
from core.resultados import leer_resultados, desde_ensamblaje_v2, ErrorResultados
e = json.load(sys.stdin)
out = {'dimensiones': {}, 'lectura': [], 'v2': []}
for u in e['unidades']:
    d = un.interpretar(u)['dimension']; out['dimensiones'][u] = {'dimension': dimension_json(d), 'magnitudes': un.magnitudes_de(d)}
for c in e['conjuntos']:
    try:
        leer_resultados(c); out['lectura'].append(None)
    except ErrorResultados as x:
        out['lectura'].append(str(x))
for f in sorted(glob.glob('docs/ejemplos/motor-v2/motor-ensamblaje-v2-resolver-*-respuesta.json')):
    out['v2'].append(desde_ensamblaje_v2(json.load(open(f, encoding='utf-8'))))
print(json.dumps(out))
`;
const python = entrada => {
  const r = spawnSync("python", ["-c", PUENTE], { cwd: RAIZ, input: JSON.stringify(entrada), encoding: "utf8", maxBuffer: 1 << 28, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
  if (r.status !== 0) throw new Error(r.stderr);
  return JSON.parse(r.stdout);
};
let n = 0;
const ok = (v, m) => { n++; assert.ok(v, m); };

// 1. Solver TS del motor
const hojas = crearHojasPruebaMateria();
const res = [];
for (const h of hojas) res.push(await resolverMotor(h.historial.pasos[h.historial.activo].formulacion, h.config));
const unidades = [...new Set(res.flatMap(unidadesDeMotor))];
const dims = python({ unidades, conjuntos: [] }).dimensiones;
const deMotor = res.map((r, i) => resultadosDesdeMotor(r, hojas[i].id, dims));
deMotor.forEach((c, i) => {
  leerResultados(c);
  const r = res[i];
  ok(isDeepStrictEqual(c.ejes[0].valores, r.tiempos), `${hojas[i].nombre}: mismo eje de tiempo`);
  ok(c.series.filter(s => s.componenteId !== undefined).every((s, j) => r.modo === "1d" ? isDeepStrictEqual(s.valores, r.valores.map(f => f[j])) : isDeepStrictEqual(s.valores, r.valores.map(f => f[j][0]))),
    `${hojas[i].nombre}: valores idénticos al resultado del motor`);
});
const v = python({ unidades: [], conjuntos: deMotor });
v.lectura.forEach((e, i) => ok(e === null, `${hojas[i].nombre}: el lector Python acepta el conjunto (${e})`));

// 2. Ensamblaje v2 y 3. simulación del núcleo
const deV2 = v.v2;
deV2.forEach((c, i) => { leerResultados(c); ok(c.series.length > 0, `ensamblaje ${i + 1}: conjunto con series`); });
const calor = JSON.parse(fs.readFileSync(path.join(RAIZ, "docs/ejemplos/adimensionalizacion-estudio-calor-resultado.json"), "utf8")).estudio.simulacion.resultados;
leerResultados(calor);
ok(calor.series.some(s => s.unidadSI === "mol/m^3"), "simulación del núcleo: publica las variables físicas con su unidad");

// Mismo motor de gráficas para los tres
const todos = [...deMotor.map(c => ["motor TS", c]), ...deV2.map(c => ["ensamblaje v2", c]), ["núcleo", calor]];
for (const [origen, c] of todos) {
  const especs = especificacionesPorOmision(c, { instante: 0 });
  ok(especs.length > 0, `${origen} ${c.id}: hay gráficas por omisión`);
  for (const e of especs) {
    const d = datosGrafica(c, e);
    ok(d.ok, `${origen} ${c.id} ${e.id}: la especificación se grafica (${d.motivo ?? ""})`);
    const s0 = c.series.find(s => s.id === e.y[0]);
    const unid = new Set(e.y.map(id => c.series.find(s => s.id === id).unidadSI));
    ok(unid.size === 1 && d.ejeY.unidad === s0.unidadSI, `${origen} ${c.id} ${e.id}: una sola unidad por eje`);
    const esperado = s0.ejes.length === 1 ? s0.valores : (s0.ejes[0] === e.fijar.eje ? s0.valores[e.fijar.indice] : s0.valores.map(f => f[e.fijar.indice]));
    ok(isDeepStrictEqual(d.curvas[0].y, esperado), `${origen} ${c.id} ${e.id}: la curva son los valores de la serie, sin transformar`);
  }
}
// Reglas genéricas
const cv2 = deV2[0];
const T = cv2.series.find(s => s.unidadSI === "K"), Pa = cv2.series.find(s => s.unidadSI === "Pa"), H = cv2.series.find(s => s.unidadSI === "J");
ok(!datosGrafica(cv2, { id: "mezcla", x: { eje: "t" }, y: [T.id, Pa.id] }).ok, "dos dimensiones distintas en un eje: rechazado");
ok(datosGrafica(cv2, { id: "fases", x: { serie: T.id }, y: [H.id] }).ok, "diagrama de fases (una serie frente a otra): admitido");
const unoD = deMotor.find(c => c.ejes.length === 2);
const campo = unoD.series.find(s => s.ejes.length === 2);
ok(!datosGrafica(unoD, { id: "sin fijar", x: { eje: "x" }, y: [campo.id] }).ok, "serie de dos ejes sin fijar uno: rechazado");
ok(datosGrafica(unoD, { id: "evolucion", x: { eje: "t" }, y: [campo.id], fijar: { eje: "x", indice: 40 } }).ok, "la misma serie en el tiempo, fijando la posición: admitido");

console.log(`Resultados y gráficas: ${n} comprobaciones correctas (${deMotor.length} del motor TS, ${deV2.length} del ensamblaje, 1 del núcleo).`);
