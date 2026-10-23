// Modelo común v0 desde las hojas reales del motor (docs/contracts/common-model.md §3).
//   - Hojas de materia (solver TS): hoja -> modelo -> formulación + configuración idénticas;
//     el lector TS y el lector Python aceptan el modelo; `matematico` son las mismas
//     ecuaciones que importa la adimensionalización; el volumen declara su cierre supuesto.
//   - Hojas con termodinámica (multifásicas, N componentes, UNIFAC, demostración): su
//     solicitud v2 -> modelo -> solicitud idéntica, y las relaciones coinciden con
//     las ecuaciones del backend en vivo (validar_v2).
// Requiere python con el núcleo. Escribe docs/ejemplos/modelo-comun/modelo-comun-hoja-motor.json.
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
const motor = n => cargar(path.join(AQUI, "app/motor", n));
const { modeloDesdeHojaMotor, hojaDesdeModelo } = cargar(path.join(AQUI, "motores/modelo/desdeHojaMotor"));
const { leerModeloComun } = cargar(path.join(AQUI, "motores/modelo/lector"));
const { leerHojaMotor } = cargar(path.join(AQUI, "app/adimensionalizacion/desdeMotor"));

const PUENTE = `
import sys, json
sys.path.insert(0, '.')
from core.modelo import ErrorModelo, leer_modelo_comun, relaciones, desde_ensamblaje_v2, a_ensamblaje_v2
from backend import motor_ensamblaje_v2 as v2
e = json.load(sys.stdin)
clave = lambda rs: [[r['id'], r['familia'], r['propietarioId']] for r in rs]
out = {'modelos': [], 'solicitudes': []}
for m in e['modelos']:
    try:
        leer_modelo_comun(m); out['modelos'].append({'ok': True, 'relaciones': relaciones(m)})
    except ErrorModelo as x:
        out['modelos'].append({'ok': False, 'error': str(x)})
for s in e['solicitudes']:
    m = desde_ensamblaje_v2(s); r = {}
    try:
        leer_modelo_comun(m); r['ok'] = True
    except ErrorModelo as x:
        r['ok'] = False; r['error'] = str(x)
    r['vuelta'] = a_ensamblaje_v2(m) == s
    vivo, _ = v2.validar_v2(json.loads(json.dumps(s)))
    r['nuestras'] = clave(relaciones(m)); r['backend'] = clave(vivo['ecuaciones'])
    out['solicitudes'].append(r)
print(json.dumps(out))
`;
function python(entrada) {
  const r = spawnSync("python", ["-c", PUENTE], { cwd: RAIZ, input: JSON.stringify(entrada), encoding: "utf8", maxBuffer: 1 << 28, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
  if (r.status !== 0) throw new Error(r.stderr);
  return JSON.parse(r.stdout);
}
let n = 0;
const ok = (v, m) => { n++; assert.ok(v, m); };

// --- hojas de materia del motor TS -------------------------------------------------
const deMateria = [...motor("hojasPruebaMateria").crearHojasPruebaMateria(), ...motor("hojasPruebaAcoplamiento").crearHojasPruebaMulticomponente()]
  .filter(h => !h.ensamblaje && !h.redTermodinamica);
const incompleta = structuredClone(deMateria[0]); incompleta.id = "incompleta"; incompleta.config.datos.salida_1_2 = { texto: "", unidad: "kg/s" };
const hojas = [...deMateria, incompleta];
const modelos = [];
for (const h of hojas) {
  const f = h.historial.pasos[h.historial.activo].formulacion;
  const m = modeloDesdeHojaMotor(h);
  leerModeloComun(JSON.parse(JSON.stringify(m)));
  const vuelta = hojaDesdeModelo(JSON.parse(JSON.stringify(m)));
  ok(isDeepStrictEqual(vuelta.formulacion, f), `${h.nombre}: formulación activa idéntica tras la ida y vuelta`);
  ok(isDeepStrictEqual(vuelta.config, h.config), `${h.nombre}: configuración idéntica tras la ida y vuelta`);
  ok(isDeepStrictEqual(vuelta.componentes, f.componentes), `${h.nombre}: componentes idénticos`);
  const imp = leerHojaMotor(h).importacion;
  if (imp) {
    const sinId = x => ({ ...x, id: "" });
    ok(isDeepStrictEqual(sinId(m.matematico), sinId(imp.documento.modelo)), `${h.nombre}: matemático = ecuaciones que importa la adimensionalización`);
  } else ok(m.matematico === null && typeof m.procedencia.sinMatematico === "string", `${h.nombre}: sin ecuaciones traducibles, lo dice (${m.procedencia.sinMatematico})`);
  ok(m.volumenes[0].termodinamica.tipo === "supuesto", `${h.nombre}: el volumen declara su cierre como supuesto explícito`);
  modelos.push(m);
}

// --- hojas con termodinámica (solicitudes v2 reales) ---------------------------------
const conRed = [...motor("hojasPruebaMultifasico").crearHojasPruebaMultifasico(), ...motor("hojasPruebaNComponentes").crearHojasPruebaNComponentes(),
  ...motor("hojasPruebaUNIFAC").crearHojasPruebaUNIFAC(), ...motor("hojasDemostracion").crearHojasDemostracion()].filter(h => h.redTermodinamica);
const solicitudes = conRed.map(h => h.redTermodinamica.solicitud);
const rp = python({ modelos, solicitudes });
rp.modelos.forEach((r, i) => {
  ok(r.ok, `${hojas[i].nombre}: el lector Python acepta el modelo (${r.error ?? ""})`);
  ok(r.relaciones.some(x => x.id === "estado.dominio.supuesto" && x.supuesta), `${hojas[i].nombre}: su estado aparece como relación supuesta`);
});
rp.solicitudes.forEach((r, i) => {
  ok(r.ok, `${conRed[i].nombre}: modelo válido (${r.error ?? ""})`);
  ok(r.vuelta, `${conRed[i].nombre}: solicitud v2 idéntica tras la ida y vuelta`);
  ok(isDeepStrictEqual(r.nuestras, r.backend), `${conRed[i].nombre}: relaciones = ecuaciones del backend en vivo`);
});

// --- rechazos del lector TS ---------------------------------------------------------
const sinCierre = structuredClone(modelos[0]); delete sinCierre.volumenes[0].termodinamica;
assert.throws(() => leerModeloComun(sinCierre), /faltan termodinamica/); n++;
const vacio = structuredClone(modelos[0]); vacio.volumenes[0].termodinamica = {};
assert.throws(() => leerModeloComun(vacio), /todo volumen declara su cierre/); n++;
const huerfano = structuredClone(modelos[0]); huerfano.corrientes[0].materia.caudalIds["1"] = "no.existe";
assert.throws(() => leerModeloComun(huerfano), /referencia inexistente/); n++;

const ejemplo = path.join(RAIZ, "docs/ejemplos/modelo-comun/modelo-comun-hoja-motor.json");
const texto = JSON.stringify({ ...modelos[5], procedencia: { ...modelos[5].procedencia, firmaHoja: "(omitida en el ejemplo)" } }, null, 1) + "\n";
fs.writeFileSync(ejemplo, texto);
console.log(`Modelo común: ${n} comprobaciones correctas (${hojas.length} hojas de materia, ${solicitudes.length} solicitudes v2 de hojas reales).`);
