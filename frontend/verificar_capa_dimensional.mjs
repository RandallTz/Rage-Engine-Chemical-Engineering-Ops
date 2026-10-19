import assert from "node:assert/strict";
import fs from "node:fs";
import ts from "typescript";
import katex from "katex";

function fuente(nombre, cambios = {}) {
  let js = ts.transpileModule(fs.readFileSync(new URL(`app/adimensionalizacion/${nombre}.ts`, import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText;
  for (const [de, a] of Object.entries(cambios)) js = js.replaceAll(JSON.stringify(de), JSON.stringify(a));
  return `data:text/javascript;base64,${Buffer.from(js).toString("base64")}`;
}
const docUrl = fuente("documento"), entradaUrl = fuente("entradaEcuaciones"), lectorUrl = fuente("lecturaNucleo");
const doc = await import(docUrl);
const entrada = await import(entradaUrl);
const hojas = await import(fuente("hojas", { "./documento": docUrl }));
const dimensiones = await import(fuente("dimensiones", { "./lecturaNucleo": lectorUrl }));
const ejemplo = await import(fuente("ejemplos", { "./documento": docUrl, "./entradaEcuaciones": entradaUrl }));
const latex = await import(fuente("exportar"));
const par = JSON.parse(fs.readFileSync(new URL("../docs/ejemplos/adimensionalizacion-auditoria-dimensional.json", import.meta.url), "utf8"));
let n = 0;
assert.deepEqual(dimensiones.leerAuditoria(par.respuesta, par.solicitud), par.respuesta); n++;
for (const alterar of [
  r => r.version++, r => r.analisis.vinculo.modeloRevision++, r => r.ecuaciones.pop(),
  r => r.ecuaciones[0].terminos.pop(), r => r.ecuaciones[0].terminos[0].expresion = { tipo: "simbolo", id: "intruso" },
  r => r.ecuaciones[1].terminos[0].ruta = "ecuaciones[0]", r => r.ecuaciones[0].dimension = { L: { n: 1, d: 0 } },
  r => r.cantidades[0].id = "intruso", r => r.cantidades = [], r => r.ecuaciones = [],
  r => r.catalogo.push(r.catalogo[0]), r => r.cantidades[0].magnitudes.push("tipo_inventado"),
]) { const copia = structuredClone(par.respuesta); alterar(copia); assert.throws(() => dimensiones.leerAuditoria(copia, par.solicitud)); n++; }
for (const eq of par.respuesta.ecuaciones) for (const t of eq.terminos) {
  katex.renderToString(latex.latexExpresion(t.expresion), { throwOnError: true });
  katex.renderToString(latex.dimensionLatex(t.dimension), { throwOnError: true }); n++;
}
assert.equal(par.respuesta.ecuaciones.length, 2); n++;
const c = hojas.crearCuaderno(doc.migrarDocumentoV2(par.solicitud.documento));
assert.equal(hojas.crearCuaderno(par.solicitud.documento).hojas[0].documento.version, 2); n++;
c.hojas[0].borrador = "d(u,t) =";
const copia = hojas.duplicarHoja(c.hojas[0]);
assert.notEqual(copia.id, c.hojas[0].id); assert.notEqual(copia.documento.id, c.hojas[0].documento.id);
assert.notEqual(copia.documento.modelo.id, c.hojas[0].documento.modelo.id); assert.equal(copia.borrador, "d(u,t) ="); n++;
c.hojas.push(copia); c.activaId = copia.id;
assert.deepEqual(hojas.leerCuaderno(JSON.stringify(c)), c); n++;
const archivado = hojas.archivarHoja(c, copia.id);
assert.equal(archivado.activaId, c.hojas[0].id); assert(archivado.hojas[1].archivada); n++;
// Archivar la última hoja abierta deja el cuaderno sin activa (válido), y retirar las escritas las conserva.
const sinAbiertas = hojas.archivarHoja(archivado, c.hojas[0].id);
assert.equal(sinAbiertas.activaId, ""); assert.deepEqual(hojas.leerCuaderno(JSON.stringify(sinAbiertas)), sinAbiertas); n++;
const retirado = hojas.retirarEscritas(c, () => false, "2026-10-19T00:00:00.000Z");
assert(retirado.hojas.every(h => h.retirada?.motivo === hojas.MOTIVO_RETIRO) && retirado.activaId === "" && retirado.hojas.length === c.hojas.length);
assert.deepEqual(hojas.retirarEscritas(retirado, () => false), retirado); assert.deepEqual(hojas.leerCuaderno(JSON.stringify(retirado)), retirado); n++;
for (const alterar of [r => r.version++, r => r.hojas.push(r.hojas[0]), r => r.activaId = "ausente", r => r.hojas[0].borrador = "x".repeat(20001), r => r.hojas[0].documento.version = 99]) {
  const mala = structuredClone(c); alterar(mala); assert.throws(() => hojas.leerCuaderno(JSON.stringify(mala))); n++;
}
const e = ejemplo.crearSistemaDifusion();
assert(doc.leerDocumento(JSON.stringify(e))); assert.equal(e.modelo.ecuaciones.length, 2);
assert.equal(e.modelo.simbolos.find(s => s.id === "t").rol, "tiempo"); n++;
const algebraico = entrada.leerEcuaciones("V = masa/rho", doc.crearDocumento().modelo);
assert.equal(algebraico.simbolos.find(s => s.id === "V").rol, "campo");
assert(algebraico.simbolos.every(s => s.dimension === null && s.unidad === null)); n++;
const coleccion = ejemplo.crearColeccionHojasEjemplo();
assert.equal(coleccion.length, 5);
for (const ej of coleccion) {
  assert(doc.leerDocumento(JSON.stringify(ej)));
}
const cuadernoColeccion = {
  formato: "adimensionalizacion.hojas",
  version: 1,
  hojas: coleccion.map(d => hojas.nuevaHoja(d)),
  activaId: ""
};
cuadernoColeccion.activaId = cuadernoColeccion.hojas[0].id;
const cuadernoLeido = hojas.leerCuaderno(JSON.stringify(cuadernoColeccion));
assert.equal(cuadernoLeido.hojas.length, 5); n++;
console.log(`Capa dimensional y hojas: ${n} comprobaciones correctas. Auditoría real, sistema, LaTeX, borradores, duplicación, archivo, aislamiento y lectura estricta.`);
