import assert from "node:assert/strict";
import fs from "node:fs";
import ts from "typescript";
import katex from "katex";

const fuente = fs.readFileSync(new URL("./app/adimensionalizacion/documento.ts", import.meta.url), "utf8");
const js = ts.transpileModule(fuente, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const api = await import(`data:text/javascript;base64,${Buffer.from(js).toString("base64")}`);
const exportador = ts.transpileModule(fs.readFileSync(new URL("./app/adimensionalizacion/exportar.ts", import.meta.url), "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const latex = await import(`data:text/javascript;base64,${Buffer.from(exportador).toString("base64")}`);
const exploracionJs = ts.transpileModule(fs.readFileSync(new URL("./app/adimensionalizacion/exploracion.ts", import.meta.url), "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const exploracion = await import(`data:text/javascript;base64,${Buffer.from(exploracionJs).toString("base64")}`);
const entradaJs = ts.transpileModule(fs.readFileSync(new URL("./app/adimensionalizacion/entradaEcuaciones.ts", import.meta.url), "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 } }).outputText;
const entrada = await import(`data:text/javascript;base64,${Buffer.from(entradaJs).toString("base64")}`);
let pruebas = 0;
const leer = d => api.leerDocumento(JSON.stringify(d));
function rechaza(cambiar, patron) { const d = api.crearEntrada(true); cambiar(d); assert.throws(() => leer(d), patron); pruebas++; }
for (const espacial of [false, true]) {
  const d = api.crearEntrada(espacial);
  assert.deepEqual(leer(d), d); pruebas++;
  assert.match(api.expresar(d.modelo.ecuaciones[0].izquierda), /∂/); pruebas++;
  const copia = api.duplicarForma(d);
  assert.equal(copia.formas[1].padreId, d.activaId);
  assert.equal(copia.modelo.id, d.modelo.id);
  copia.formas[1].escalas[0].valor = { tipo: "cantidad", valor: 2, unidad: "s" };
  assert.equal(d.formas[0].escalas[0].valor.tipo, "libre"); pruebas++;
  const nuevo = api.editarModelo(copia, structuredClone(copia.modelo));
  assert.equal(nuevo.modelo.revision, 2);
  assert.equal(nuevo.formas[0].modeloRevision, 1);
  assert.equal(nuevo.formas[1].modeloRevision, 1); pruebas++;
}
assert.deepEqual(leer(api.crearDocumento()).modelo.simbolos, []); pruebas++;
rechaza(d => d.version = 3, /version/);
rechaza(d => d.resultado = { certificado: true }, /campos/);
rechaza(d => d.modelo.simbolos[0].dimension.T.d = 0, /entero/);
rechaza(d => d.modelo.simbolos[0].dimension.T.n = 0.5, /entero/);
rechaza(d => d.modelo.simbolos.push(d.modelo.simbolos[0]), /duplicadas/);
rechaza(d => d.modelo.simbolos[2].dependeDe = ["t"], /constante/);
rechaza(d => d.modelo.simbolos[1].dependeDe = ["fantasma"], /referencia/);
rechaza(d => d.modelo.ecuaciones[0].derecha = { tipo: "simbolo", id: "fantasma" }, /referencia/);
rechaza(d => d.modelo.ecuaciones[0].derecha = { tipo: "latex", valor: "c" }, /operador/);
rechaza(d => d.modelo.ecuaciones[0].izquierda.respecto = "c", /referencia/);
rechaza(d => d.modelo.ecuaciones[0].derecha = { tipo: "laplaciano", expresion: { tipo: "simbolo", id: "c" }, coordenadas: [] }, /coordenadas/);
rechaza(d => d.modelo.ecuaciones[0].derecha = { tipo: "funcion", nombre: "exp", argumentos: [{ tipo: "numero", valor: 0 }, { tipo: "numero", valor: 1 }] }, /argumento/);
rechaza(d => d.modelo.ecuaciones[0].derecha = { tipo: "llamada", funcionId: "noExiste", argumentos: [{ tipo: "numero", valor: 0 }] }, /referencia/);
for (const valor of [0, -1, null, "1"]) rechaza(d => d.formas[0].escalas[0].valor = { tipo: "cantidad", valor, unidad: "s" }, /positiva/);
rechaza(d => d.formas[0].escalas[0].valor = { tipo: "cantidad", valor: 25, unidad: "degC" }, /afín/);
rechaza(d => d.formas[0].escalas.push(d.formas[0].escalas[0]), /duplicada/);
rechaza(d => d.formas[0].escalas[0].simboloId = "k", /variables/);
rechaza(d => d.formas[0].padreId = d.formas[0].id, /ciclo/);
rechaza(d => d.formas[0].modeloRevision = 9, /futura/);
rechaza(d => d.activaId = "noExiste", /referencia/);
rechaza(d => d.modelo.ecuaciones[0].derecha = { tipo: "suma", argumentos: [] }, /argumentos/);
rechaza(d => { let e = { tipo: "numero", valor: 1 }; for (let i = 0; i < 45; i++) e = { tipo: "funcion", nombre: "abs", argumentos: [e] }; d.modelo.ecuaciones[0].derecha = e; }, /compleja/);
const declarada = api.crearEntrada(true);
declarada.modelo.funciones.push({ id: "difusividad", nombre: "D(c)", entradas: [null], salida: null, dependeDe: ["t", "x"] });
declarada.modelo.ecuaciones[0].derecha = { tipo: "divergencia", coordenadas: ["x"], expresion: { tipo: "producto", argumentos: [
  { tipo: "llamada", funcionId: "difusividad", argumentos: [{ tipo: "simbolo", id: "c" }] },
  { tipo: "gradiente", coordenadas: ["x"], expresion: { tipo: "simbolo", id: "c" } }] } };
assert.deepEqual(leer(declarada), declarada); pruebas++;
const d = api.crearEntrada(false);
d.modelo.dominios.push({ id: "intervalo", variableId: "t", desde: { tipo: "numero", valor: 0 }, hasta: { tipo: "numero", valor: 10 } });
d.modelo.condiciones.push({ id: "inicio", tipo: "inicial", dominioId: "intervalo", ecuacion: { id: "valor", izquierda: { tipo: "simbolo", id: "c" }, derecha: { tipo: "numero", valor: 0 } } });
assert.deepEqual(leer(d), d); pruebas++;
d.modelo.condiciones[0].dominioId = "ausente"; assert.throws(() => leer(d), /referencia/); pruebas++;
assert.throws(() => api.leerDocumento(" ".repeat(api.LIMITE_BYTES + 1)), /1 MB/); pruebas++;
assert.throws(() => api.leerDocumento("null"), /objeto/); pruebas++;
// La validación estructural no certifica física: exp(c) dimensional queda para A1.
const pendiente = api.crearEntrada(false);
pendiente.modelo.ecuaciones[0].derecha = { tipo: "funcion", nombre: "exp", argumentos: [{ tipo: "simbolo", id: "c" }] };
assert.deepEqual(leer(pendiente), pendiente); pruebas++;
for (const espacial of [false, true]) {
  const doc = api.crearEntrada(espacial);
  for (const e of doc.modelo.ecuaciones) katex.renderToString(`${latex.latexExpresion(e.izquierda)} = ${latex.latexExpresion(e.derecha)}`, { throwOnError: true });
  assert.match(latex.exportarLatex(doc), /Sin transformación/); pruebas++;
  const salida = latex.exportarLatex(doc);
  assert.match(salida, /\\documentclass/);
  assert.match(salida, /\\begin\{document\}/);
  assert.match(salida, /\\end\{document\}/);
  for (const f of doc.formas) for (const e of f.escalas) katex.renderToString(latex.escalaLatex(e), { throwOnError: true, strict: "error" });
  for (const s of doc.modelo.simbolos) katex.renderToString(latex.dimensionLatex(s.dimension), { throwOnError: true, strict: "error" });
  pruebas++;
}
katex.renderToString(latex.dimensionLatex({L:{n:1,d:2}}), { throwOnError: true, strict: "error" }); pruebas++;
katex.renderToString(latex.latexExpresion({ tipo: "simbolo", id: "c_{a}\\x%$&#~^" }), { throwOnError: true }); pruebas++;
// Precedencia y signos: la presentación conserva agrupaciones que afectan al significado.
const sym = id => ({ tipo: "simbolo", id });
const num = valor => ({ tipo: "numero", valor });
const prod = (...argumentos) => ({ tipo: "producto", argumentos });
const suma = (...argumentos) => ({ tipo: "suma", argumentos });
const potencia = (base, exponente) => ({ tipo: "potencia", base, exponente });
const casosPresentacion = [
  [prod(sym("k"), suma(sym("c"), num(2))), /k\\,\\left\(c \+ 2\\right\)/],
  [potencia(num(-2), num(2)), /\\left\(-2\\right\)\^\{2\}/],
  [prod(sym("a"), prod(num(-1), sym("c"))), /a\\,\\left\(-c\\right\)/],
  [potencia({ tipo: "laplaciano", expresion: sym("c"), coordenadas: ["x"] }, num(2)), /\\left\(.*\\nabla.*\\right\)\^\{2\}/],
  [suma(prod(sym("k"), sym("c")), prod(num(-1), sym("a"), potencia(sym("c"), num(2)))), /^k\\,c - a\\,c\^\{2\}$/],
  [potencia(potencia(sym("c"), num(2)), num(3)), /\\left\(c\^\{2\}\\right\)\^\{3\}/],
];
for (const [expresion, esperado] of casosPresentacion) {
  const antes = JSON.stringify(expresion), salida = latex.latexExpresion(expresion);
  assert.match(salida, esperado);
  katex.renderToString(salida, { throwOnError: true, strict: "error" });
  assert.equal(JSON.stringify(expresion), antes, "La presentación no modifica el modelo"); pruebas++;
}
// Preparación combinatoria de solicitudes, sin afirmar compatibilidad matemática.
for (const espacial of [false, true]) {
  const original = api.crearEntrada(espacial), antes = JSON.stringify(original);
  const solicitud = exploracion.prepararExploracion(original, exploracion.CONFIG_EXPLORACION);
  assert.equal(solicitud.terminos.length, espacial ? 4 : 3, "Incluye temporal y todos los términos explícitos de ambos lados");
  assert.equal(solicitud.cobertura.combinacionesEnAlcance, espacial ? "16" : "8");
  assert.equal(solicitud.cobertura.limitadoPorPresupuesto, false);
  assert.equal(solicitud.propuestas.length, espacial ? 16 : 8);
  assert.equal(solicitud.propuestas[0].objetivos.length, 0, "Conserva representante sin objetivos nuevos");
  assert.equal(JSON.stringify(original), antes, "Explorar no modifica el original"); pruebas++;
  const firmas = solicitud.propuestas.map(p => JSON.stringify(p.objetivos.map(o => o.terminoId)));
  assert.equal(new Set(firmas).size, firmas.length, "No duplica combinaciones de objetivos"); pruebas++;
  for (const p of solicitud.propuestas) for (const o of p.objetivos) {
    assert.equal(o.operacion, "normalizar_magnitud_coeficiente"); assert.equal(o.conservarSigno, true);
    assert(solicitud.terminos.some(t => t.id === o.terminoId));
  } pruebas++;
  const renombrado = structuredClone(original);
  renombrado.modelo.simbolos.forEach(s => s.nombre = `nombre_${s.nombre}`);
  assert.equal(exploracion.prepararExploracion(renombrado, exploracion.CONFIG_EXPLORACION).propuestas.length, solicitud.propuestas.length); pruebas++;
}
const presupuestoCorto = exploracion.prepararExploracion(api.crearEntrada(true), { ...exploracion.CONFIG_EXPLORACION, presupuesto: 3 });
assert.equal(presupuestoCorto.propuestas.length, 3); assert.equal(presupuestoCorto.cobertura.limitadoPorPresupuesto, true); pruebas++;
const escalaFija = api.crearEntrada(true);
escalaFija.formas[0].escalas[0].valor = { tipo: "cantidad", valor: 2, unidad: "s" };
const respetada = exploracion.prepararExploracion(escalaFija, exploracion.CONFIG_EXPLORACION);
assert.equal(respetada.formaBase.escalas[0].valor.valor, 2); pruebas++;
const libre = exploracion.prepararExploracion(escalaFija, { ...exploracion.CONFIG_EXPLORACION, respetarEscalasFijadas: false });
assert.equal(libre.formaBase.escalas[0].valor.tipo, "libre");
assert.equal(escalaFija.formas[0].escalas[0].valor.valor, 2); pruebas++;
escalaFija.formas[0].escalas[0].transformar = false;
assert.equal(exploracion.prepararExploracion(escalaFija, { ...exploracion.CONFIG_EXPLORACION, respetarEscalasFijadas: false }).formaBase.escalas[0].valor.valor, 2); pruebas++;
const guardable = { ...api.crearEntrada(true), exploracion: { ...exploracion.CONFIG_EXPLORACION, presupuesto: 100 } };
assert.deepEqual(leer(guardable), guardable); pruebas++;
for (const [campo, valor] of [["presupuesto", 0], ["presupuesto", 201], ["maxObjetivos", 9], ["maxObjetivos", 1.5], ["maxDenominadorPi", 0], ["incluirGruposPi", "sí"]]) {
  assert.throws(() => leer({ ...guardable, exploracion: { ...guardable.exploracion, [campo]: valor } }));
  assert.throws(() => exploracion.prepararExploracion(guardable, { ...guardable.exploracion, [campo]: valor })); pruebas++;
}
assert.throws(() => exploracion.prepararExploracion(api.crearDocumento(), exploracion.CONFIG_EXPLORACION), /ecuación/); pruebas++;
const viejo = api.crearEntrada(false); viejo.modelo.revision++;
assert.throws(() => exploracion.prepararExploracion(viejo, exploracion.CONFIG_EXPLORACION), /desactualizada/); pruebas++;
const sinExpandir = api.crearEntrada(false); sinExpandir.modelo.ecuaciones[0].derecha = prod(sym("c"), suma(sym("a"), sym("k")));
assert.equal(exploracion.terminosExplorables(sinExpandir.modelo).length, 2, "No desarrolla productos ni pretende una cobertura algebraica general"); pruebas++;
const variosCampos = api.crearEntrada(true);
variosCampos.modelo.ecuaciones.push({ ...structuredClone(variosCampos.modelo.ecuaciones[0]), id: "segunda" });
assert.equal(exploracion.terminosExplorables(variosCampos.modelo).length, 8); pruebas++;
for (const espacial of [false, true]) {
  const doc = api.crearEntrada(espacial), texto = entrada.textoModelo(doc.modelo);
  const modelo = entrada.leerEcuaciones(texto, doc.modelo);
  assert.deepEqual(leer({ ...doc, modelo }).modelo, modelo);
  assert.equal(entrada.textoModelo(modelo), texto, "Texto canónico estable al releer");
  assert.deepEqual(modelo.simbolos.find(s => s.id === "c").dimension, doc.modelo.simbolos.find(s => s.id === "c").dimension); pruebas++;
}
const vacio = api.crearDocumento();
for (const texto of ["d(y,s) = A*lap(y,z) + f(y)", "u = (T-Tref)/DT", "u = c/c_ref", "u = log(c/C)", "d(u,t)=k*u\nd(v,t)=g(u,v)", "d(y,t,2) = div(D(y)*grad(y,x),x)", "u = sqrt(q) + 1e-7", "u = -q^2 + (-q)^2", "u = q/(r/s)"]) {
  const modelo = entrada.leerEcuaciones(texto, vacio.modelo);
  const doc = { ...vacio, modelo };
  assert.deepEqual(leer(doc), doc);
  for (const e of modelo.ecuaciones) katex.renderToString(`${latex.latexExpresion(e.izquierda)}=${latex.latexExpresion(e.derecha)}`, { throwOnError: true });
  assert(modelo.simbolos.every(s => s.dimension === null), "El parser no fabrica dimensiones"); pruebas++;
}
const generico = entrada.leerEcuaciones("d(y,s)=alpha*y", vacio.modelo);
assert.equal(generico.simbolos.find(s => s.id === "s").rol, "coordenada");
assert.equal(generico.simbolos.find(s => s.id === "s").dimension, null, "Nombre de coordenada no implica tiempo ni longitud"); pruebas++;
for (const texto of ["", "u + v", "u = 2 v", "u = q = r", "u=process.exit()", "d(y,t,0)=y", "d(y,t,1.5)=y", "d(y,2)=y", "u=exp(q,r)", "u=f(q)+f(q,r)", "u=lap(q,x,x)", "u=" + "-".repeat(50) + "x", "u=" + "x^".repeat(50) + "2", "u=" + "x*".repeat(100) + "x"]) {
  assert.throws(() => entrada.leerEcuaciones(texto, vacio.modelo), undefined, texto); pruebas++;
}
const campoOriginal = api.crearEntrada(false).modelo;
assert.throws(() => entrada.leerEcuaciones("d(y,c)=y", campoOriginal), /rol/); pruebas++;
const conDominio = api.crearEntrada(true).modelo;
conDominio.dominios.push({ id: "dominio", variableId: "x", desde: num(0), hasta: num(1) });
assert.throws(() => entrada.leerEcuaciones("d(y,t)=y", conDominio), /geometría/); pruebas++;
console.log(`Adimensionalización: ${pruebas} casos de contrato, referencias, persistencia, ramas e invalidación correctos. Sin validación matemática ni transformación.`);
