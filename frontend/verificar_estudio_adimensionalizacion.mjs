// Verificación del estudio de formulaciones en el cliente: lector estricto,
// presentación LaTeX de los resultados reales del núcleo e informe. No
// valida la matemática (eso lo hace tests/validar_estudio_adimensionalizacion.py).
import assert from "node:assert/strict";
import fs from "node:fs";
import ts from "typescript";
import katex from "katex";

function fuente(nombre, cambios = {}) {
  let js = ts.transpileModule(fs.readFileSync(new URL(`app/adimensionalizacion/${nombre}.ts`, import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText;
  for (const [de, a] of Object.entries(cambios)) js = js.replaceAll(JSON.stringify(de), JSON.stringify(a));
  return `data:text/javascript;base64,${Buffer.from(js).toString("base64")}`;
}
const lectorNucleoUrl = fuente("lecturaNucleo"), contratoEstudioUrl = fuente("contratoEstudio"), exportarUrl = fuente("exportar"), katexCssUrl = fuente("katexCss");
const lector = await import(fuente("lecturaEstudio", { "./lecturaNucleo": lectorNucleoUrl, "./contratoEstudio": contratoEstudioUrl }));
const latex = await import(exportarUrl);
const informe = await import(fuente("informe", { "./exportar": exportarUrl, "./katexCss": katexCssUrl, "katex": "data:text/javascript;base64," + Buffer.from(`export default (await import(${JSON.stringify(new URL("node_modules/katex/dist/katex.mjs", import.meta.url).href)})).default;`).toString("base64") }));

const leer = n => JSON.parse(fs.readFileSync(new URL(`../docs/ejemplos/adimensionalizacion-${n}.json`, import.meta.url), "utf8"));
let n = 0;
const render = tex => { katex.renderToString(tex, { throwOnError: true }); n++; };

for (const nombre of ["estudio-calor", "estudio-brusselator", "estudio-pliegues"]) {
  const sol = leer(`${nombre}-solicitud`), res = leer(`${nombre}-resultado`);
  assert.deepEqual(lector.leerRespuestaEstudio(res, sol), res, nombre); n++;
  for (const alterar of [
    r => r.version = 2, r => r.operacion = "transformar", r => r.vinculo.modeloRevision++, r => r.vinculo.documentoId = "otro",
    r => r.vinculo.estudio = { ...r.vinculo.estudio, valores: [] }, r => r.campoNuevo = 1,
    r => { const k = Object.keys(r.estudio)[0]; r.estudio[k].estado = "inventado"; },
    r => { const k = Object.keys(r.estudio)[0]; delete r.estudio[k]; },
    r => { r.estado = "rechazado"; },
  ]) {
    const copia = structuredClone(res); alterar(copia);
    assert.throws(() => lector.leerRespuestaEstudio(copia, sol), undefined, `${nombre}: debe rechazar una respuesta alterada`); n++;
  }
  // Todas las fórmulas que la interfaz presenta se componen con KaTeX.
  const f = res.formulacion, e = res.estudio;
  for (const ec of f.ecuaciones) render(`${latex.latexExpresion(ec.igualdad.izquierda)} = ${latex.latexExpresion(ec.igualdad.derecha)}`);
  for (const g of f.grupos) render(`${latex.nombreLatex(g.id)} = ${latex.latexExpresion(g.definicion)}`);
  for (const red of e.simetrias?.reducciones ?? []) for (const q of red.ecuaciones ?? []) render(`${latex.latexExpresion(q.ecuacion.izquierda)} = 0`);
  for (const q of e.asintotica?.ecuaciones ?? []) if (q.reducida) render(`${latex.latexExpresion(q.reducida.izquierda)} = ${latex.latexExpresion(q.reducida.derecha)}`);
  const html = informe.generarInforme({ nombre: nombre, modelo: sol.documento.modelo, f, indice: 0, respuesta: { ...res, formulaciones: [f] }, estudio: e });
  assert.ok(html.startsWith("<!doctype html>") && html.includes("Desarrollo completo") && !html.includes("Antigravity"), `${nombre}: informe`); n++;
  assert.ok(!/demostramos|certificad[ao] por/i.test(html.replace(/demostrada/g, "")), `${nombre}: el informe no afirma resultados que no calculó`); n++;
}

// Simulación: matriz inconsistente rechazada.
{
  const sol = leer("estudio-calor-solicitud"), res = leer("estudio-calor-resultado");
  assert.equal(res.estudio.simulacion.estado, "calculado"); n++;
  const copia = structuredClone(res); copia.estudio.simulacion.campos.c_ad[0].pop();
  assert.throws(() => lector.leerRespuestaEstudio(copia, sol)); n++;
  const otra = structuredClone(res); otra.estudio.simulacion.tiempos.push(9);
  assert.throws(() => lector.leerRespuestaEstudio(otra, sol)); n++;
  assert.ok(typeof res.estudio.simulacion.codigoPython === "string" && res.estudio.simulacion.codigoPython.includes("solve_ivp")); n++;
}
// Brusselator: Turing publicado con su curva de dispersión.
{
  const res = leer("estudio-brusselator-resultado");
  const esp = res.estudio.estabilidad.estados[0].espacial[0];
  assert.equal(esp.clase, "turing"); n++;
  assert.equal(esp.k.length, esp.reSigma.length); n++;
}
// Pliegues: dos puntos especiales de tipo pliegue.
{
  const res = leer("estudio-pliegues-resultado");
  assert.equal(res.estudio.continuacion.especiales.filter(x => x.tipo === "pliegue").length, 2); n++;
}
// Regresión: volver a leer el texto de un modelo con condiciones y dominio no
// pierde los símbolos que solo aparecen en ellos (antes bloqueaba el cálculo).
{
  const docUrl = fuente("documento"), entradaUrl = fuente("entradaEcuaciones");
  const entrada = await import(entradaUrl);
  const ejemplos = await import(fuente("ejemplos", { "./documento": docUrl, "./entradaEcuaciones": entradaUrl }));
  for (const crear of [ejemplos.crearEjemploReferenciasUbicacion, ejemplos.crearEjemploFuncionEscalada]) {
    const doc = crear();
    const releido = entrada.leerEcuaciones(entrada.textoModelo(doc.modelo), doc.modelo);
    const ids = new Set(releido.simbolos.map(s => s.id));
    for (const s of doc.modelo.simbolos) assert.ok(ids.has(s.id), `${doc.nombre}: conserva ${s.id}`);
    n++;
  }
}
// Los módulos retirados ya no están en la ruta.
for (const m of ["analisisEstabilidad.ts", "analisisSimetriasLie.ts", "SimuladorEnVivo.tsx", "puenteMotor.ts", "exportarSimulacion.ts", "paquetePublicacion.ts"]) {
  assert.ok(!fs.existsSync(new URL(`app/adimensionalizacion/${m}`, import.meta.url)), `${m} debe estar retirado`); n++;
}
console.log(`Estudio: ${n} comprobaciones correctas. Lector estricto, fórmulas KaTeX, informe sin contenido inventado y módulos retirados.`);
