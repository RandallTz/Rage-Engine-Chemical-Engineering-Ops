// Fase M1: las hojas de materia del motor, leídas en solo lectura como
// documentos de adimensionalización. Para cada hoja de prueba del motor:
//   1. el motor la resuelve con su propio solver (sin cambios);
//   2. desdeMotor.ts la traduce a documento v2 + valores SI;
//   3. el núcleo de Python busca y certifica la formulación adimensional;
//   4. el núcleo simula esa formulación hasta el tiempo final de la hoja;
//   5. la simulación, devuelta a unidades físicas, se compara con el motor y
//      con la solución analítica de HOJAS_PRUEBA_MATERIA.
// Requiere python con el núcleo (core/adimensionalizacion). Tarda ~1 min.
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
const motor = n => cargar(path.join(AQUI, "app/motor", n)), adim = n => cargar(path.join(AQUI, "app/adimensionalizacion", n));
const { crearHojasPruebaMateria } = motor("hojasPruebaMateria"), { resolverMotor } = motor("integracionMotor");
const { importarHojaMotor, leerHojaMotor } = adim("desdeMotor"), { leerDocumento } = adim("documento");
const { prepararSolicitud, formulacionesDe, leerRespuestaNucleo } = adim("lecturaNucleo"), { prepararEstudio } = adim("clienteNucleo");
const { compararConMotor } = adim("diferenciaMotor"), { leerRespuestaEstudio } = adim("lecturaEstudio"), { textoModelo, leerEcuaciones } = adim("entradaEcuaciones");

const PUENTE = "import sys, json; sys.path.insert(0, '.'); from core.adimensionalizacion import procesar; print(json.dumps(procesar(json.load(sys.stdin))))";
function nucleo(solicitud) {
  const r = spawnSync("python", ["-c", PUENTE], { cwd: RAIZ, input: JSON.stringify(solicitud), encoding: "utf8", maxBuffer: 1 << 28, env: { ...process.env, PYTHONIOENCODING: "utf-8" } });
  if (r.status !== 0) throw new Error(r.stderr);
  return JSON.parse(r.stdout);
}
let n = 0;
const porId = l => JSON.stringify([...l].sort((a, b) => a.id < b.id ? -1 : 1));
const ok = (v, m) => { n++; assert.ok(v, m); };
const interp = (xs, ys, x) => { if (x <= xs[0]) return ys[0]; for (let i = 1; i < xs.length; i++) if (x <= xs[i]) { const a = (x - xs[i - 1]) / (xs[i] - xs[i - 1]); return ys[i - 1] * (1 - a) + ys[i] * a; } return ys.at(-1); };
/** Interpolación periódica en [a, a + P). */
const interpP = (xs, ys, x, a, P) => { const h = xs[1] - xs[0], u = ((x - a) % P + P) % P / h, i = Math.floor(u), f = u - i; return ys[i % ys.length] * (1 - f) + ys[(i + 1) % ys.length] * f; };

const analiticas = [
  t => [100 + t], t => [100 - 2 * t], t => [.1 + .002 * t], () => [100], t => [100 - 2 * t],
  t => [Math.exp(-.2 * t), 1 - Math.exp(-.2 * t)],
  (t, x) => [2 + .3 * Math.sin(2 * Math.PI * (x - t))],
  (t, x) => { const a = .1 * Math.exp(-4 * Math.PI ** 2 * .05 * t); return [.5 + a * Math.sin(2 * Math.PI * x), .5 - a * Math.sin(2 * Math.PI * x)]; },
];
const evidencias = [];
for (const [i, hoja] of crearHojasPruebaMateria().entries()) {
  const antes = JSON.stringify(hoja);
  const imp = importarHojaMotor(hoja);
  ok(JSON.stringify(hoja) === antes, `${hoja.nombre}: la hoja del motor no cambia al leerla`);
  ok(leerHojaMotor(hoja).motivo === null, `${hoja.nombre}: importable`);
  const doc = leerDocumento(JSON.stringify(imp.documento));
  ok(doc.version === 2 && doc.nombre.includes(hoja.nombre), `${hoja.nombre}: documento v2 válido para el lector estricto`);
  // El texto editable de la hoja vuelve a leerse al mismo modelo.
  const releido = leerEcuaciones(textoModelo(doc.modelo), doc.modelo);
  ok(textoModelo(releido) === textoModelo(doc.modelo) && porId(releido.simbolos) === porId(doc.modelo.simbolos), `${hoja.nombre}: el texto de las ecuaciones es un punto fijo y conserva los símbolos`);
  ok(Object.keys(imp.valores).every(id => doc.modelo.simbolos.some(s => s.id === id && s.rol === "parametro")), `${hoja.nombre}: cada valor es de un parámetro del documento`);
  ok(doc.modelo.simbolos.filter(s => s.rol === "parametro").every(s => imp.valores[s.id] && imp.origen.descripciones[s.id]), `${hoja.nombre}: cada parámetro tiene valor y descripción`);

  const solicitud = prepararSolicitud(doc, { presupuesto: 200, gruposPi: false });
  const respuesta = leerRespuestaNucleo(nucleo(solicitud), solicitud);
  const formulaciones = formulacionesDe(respuesta);
  ok(respuesta.estado === "correcto" && formulaciones.length > 0, `${hoja.nombre}: el núcleo encuentra formulaciones (${respuesta.estado} ${JSON.stringify(respuesta.diagnosticos ?? "").slice(0, 300)})`);
  ok(formulaciones.every(f => f.equivalencia?.estado === "demostrada"), `${hoja.nombre}: todas certificadas por sustitución inversa`);
  // La más determinada por los datos: la restitución a SI no es trivial.
  const f = formulaciones.reduce((a, b) => b.libres.length < a.libres.length ? b : a);
  const valores = [...Object.entries(imp.valores).map(([simboloId, v]) => ({ simboloId, valor: Number(v.valor), ...(v.unidad ? { unidad: v.unidad } : {}) })),
    ...f.libres.map(simboloId => ({ simboloId, valor: 3.7 }))];
  const { periodica } = imp.origen.simulacion;
  const rm = await resolverMotor(hoja.historial.pasos[hoja.historial.activo].formulacion, hoja.config);
  const estudio = prepararEstudio(solicitud, f, { valores, analisis: ["simulacion"], simulacion: { tFinalSI: rm.tiempos.at(-1), muestras: rm.tiempos.length, ...(periodica ? { periodica: true, nodos: 128 } : {}), verificarMalla: false } });
  const re = leerRespuestaEstudio(nucleo(estudio), estudio), sim = re.estudio.simulacion;
  ok(sim.estado === "calculado", `${hoja.nombre}: simulación calculada (${sim.motivo})`);
  const fis = sim.fisico, ts_ = fis.tiempo.valoresSI;
  ok(Math.abs(ts_.at(-1) - rm.tiempos.at(-1)) <= 1e-9 * rm.tiempos.at(-1), `${hoja.nombre}: tFinalSI llega al tiempo final del motor (${ts_.at(-1)} s)`);
  // Comparación en los instantes y celdas del motor.
  let difMotor = 0, difExacta = 0, escala = 0;
  const comps = imp.origen.componentes.map(c => fis.campos[c.campoId]);
  ok(comps.every(Boolean), `${hoja.nombre}: cada componente vuelve a unidades físicas`);
  for (const [k, t] of rm.tiempos.entries()) {
    if (imp.origen.modo === "temporal") {
      comps.forEach((serie, j) => {
        const v = interp(ts_, serie.map(fila => fila[0]), t), m = rm.valores[k][j][0], e = analiticas[i](t)[j];
        difMotor = Math.max(difMotor, Math.abs(v - m)); difExacta = Math.max(difExacta, Math.abs(v - e)); escala = Math.max(escala, Math.abs(m));
      });
    } else {
      const xs = fis.coordenada.valoresSI, a = xs[0], P = (xs[1] - xs[0]) * xs.length;
      const kk = ts_.findIndex(x => x >= t - 1e-12);
      comps.forEach((serie, j) => rm.x.forEach((x, c) => {
        // Interpola en el tiempo entre las muestras del núcleo y en el espacio periódico.
        const k1 = Math.max(1, kk), w = (t - ts_[k1 - 1]) / (ts_[k1] - ts_[k1 - 1]);
        const v = interpP(xs, serie[k1 - 1], x, a, P) * (1 - w) + interpP(xs, serie[k1], x, a, P) * w;
        difMotor = Math.max(difMotor, Math.abs(v - rm.valores[k][j][c])); difExacta = Math.max(difExacta, Math.abs(v - analiticas[i](t, x)[j])); escala = Math.max(escala, Math.abs(rm.valores[k][j][c]));
      }));
    }
  }
  const tolMotor = imp.origen.modo === "1d" ? 2e-2 : 1e-5, tolExacta = imp.origen.modo === "1d" ? 1e-3 : 1e-5;
  const cmp = compararConMotor(imp.origen, fis, rm);
  ok(Math.abs(cmp.relativa - difMotor / escala) <= 1e-12 + 1e-9 * difMotor / escala && cmp.instantes === rm.tiempos.length, `${hoja.nombre}: la comparación de la interfaz da la misma diferencia (${cmp.relativa})`);
  ok(difMotor / escala < tolMotor, `${hoja.nombre}: coincide con el motor (diferencia relativa ${(difMotor / escala).toExponential(2)})`);
  ok(difExacta / escala < tolExacta, `${hoja.nombre}: coincide con la solución analítica (${(difExacta / escala).toExponential(2)})`);
  evidencias.push({ hoja: hoja.nombre, ecuaciones: textoModelo(doc.modelo), grupos: f.grupos?.length ?? 0, libres: f.libres, diferenciaMotor: difMotor / escala, diferenciaAnalitica: difExacta / escala, avisos: imp.origen.avisos });
}

// Lo que no se traduce todavía se dice, no se inventa.
const [primera] = crearHojasPruebaMateria();
const conEscalon = structuredClone(crearHojasPruebaMateria()[5]); conEscalon.config.datos.consumo_1 = { texto: "0.2*m_A*step(t-5)", unidad: "kg/s" };
ok(/escalón/.test(leerHojaMotor(conEscalon).motivo ?? ""), "step: no traducible y lo dice");
const incompleta = structuredClone(primera); delete incompleta.config.datos.salida_1_2;
ok(leerHojaMotor(incompleta).motivo !== null, "hoja con datos pendientes: no importable");
const conEnsamblaje = { ...structuredClone(primera), ensamblaje: {} };
ok(/M3/.test(leerHojaMotor(conEnsamblaje).motivo ?? ""), "ensamblaje: fase M3, no importable");
// Unidades del motor a SI: 3 kg/h es 3/3600 kg/s.
const enHoras = structuredClone(primera); enHoras.config.datos.entrada_1_1 = { texto: "3", unidad: "kg/h" };
const vh = importarHojaMotor(enHoras).valores;
ok(Math.abs(Number(Object.entries(vh).find(([id]) => id.startsWith("Fe1"))[1].valor) - 3 / 3600) < 1e-15, "unidad del dato convertida a SI");
// Literales con dimensión: 0.2*m_A en kg/s es un parámetro de dimensión 1/s.
const sexta = crearHojasPruebaMateria()[5], imp6 = importarHojaMotor(sexta);
const k = imp6.documento.modelo.simbolos.find(s => s.id.startsWith("k_A"));
ok(k && JSON.stringify(k.dimension) === JSON.stringify({ T: { n: -1, d: 1 } }) && imp6.valores[k.id].unidad === "s^-1", "literal 0.2 de 0.2*m_A (kg/s) como parámetro de 1/s");

fs.writeFileSync(path.join(RAIZ, "docs/ejemplos/importacion-motor-evidencias.json"), JSON.stringify(evidencias, null, 2) + "\n");
console.log(`${n} comprobaciones OK`);
for (const e of evidencias) console.log(`  ${e.hoja}: motor ${e.diferenciaMotor.toExponential(1)}, analítica ${e.diferenciaAnalitica.toExponential(1)}`);
