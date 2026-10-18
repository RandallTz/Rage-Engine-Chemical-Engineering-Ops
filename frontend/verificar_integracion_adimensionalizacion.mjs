import assert from "node:assert/strict";
import fs from "node:fs";
import ts from "typescript";
import katex from "katex";

function fuente(nombre, reemplazos = {}) {
  let js = ts.transpileModule(fs.readFileSync(new URL(`app/adimensionalizacion/${nombre}.ts`, import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 } }).outputText;
  for (const [desde, hasta] of Object.entries(reemplazos)) js = js.replaceAll(JSON.stringify(desde), JSON.stringify(hasta));
  return `data:text/javascript;base64,${Buffer.from(js).toString("base64")}`;
}
const lector = await import(fuente("lecturaNucleo")), documento = await import(fuente("documento"));
const latexUrl = fuente("exportar"), latex = await import(latexUrl);
const exportador = await import(fuente("exportarDesarrollo", { "./exportar": latexUrl }));
const nombres = ["automatico", "requiere-datos", "mapa-logaritmico", "mapa-afin-temperatura", "general", "tiempo-difusivo", "tiempo-reactivo", "campo-cinetico", "longitud-parametrica", "condiciones", "parcial", "signo-negativo", "rechazo-suma-incompatible", "rechazo-forma-desactualizada", "analizar", "explorar", "v2-funcion-escalada", "v2-referencias-ubicacion"];
const archivo = (n, t) => JSON.parse(fs.readFileSync(new URL(`../docs/ejemplos/adimensionalizacion-${n}-${t}.json`, import.meta.url), "utf8"));
let comprobaciones = 0, pasos = 0;
for (const n of nombres) {
  const sol = archivo(n, "solicitud"), res = archivo(n, "resultado");
  assert.deepEqual(lector.leerRespuestaNucleo(res, sol), res); comprobaciones++;
  for (const f of lector.formulacionesDe(res)) {
    assert.equal(f.desarrolloEstado.estado, "completo");
    for (const p of f.desarrollo) {
      for (const e of [p.antes, p.despues]) {
        const tex = e.tipo === "expresion" ? latex.latexExpresion(e.expresion) : `${latex.latexExpresion(e.igualdad.izquierda)}=${latex.latexExpresion(e.igualdad.derecha)}`;
        katex.renderToString(tex, { throwOnError: true, strict: "error" });
      }
      pasos++;
    }
    const tex = exportador.exportarDesarrollo(f);
    assert.match(tex, /\\begin\{document\}/); assert.match(tex, /\\end\{document\}/);
    assert.equal((tex.match(/\\subsection\*/g) ?? []).length, f.desarrollo.length);
    comprobaciones++;
  }
}
const sol = archivo("automatico", "solicitud"), original = archivo("automatico", "resultado");
function rechaza(alterar) { const r = structuredClone(original); alterar(r); assert.throws(() => lector.leerRespuestaNucleo(r, sol)); comprobaciones++; }
rechaza(r => r.version = 99);
rechaza(r => r.formato = "otra.respuesta");
rechaza(r => r.vinculo.modeloRevision++);
rechaza(r => r.vinculo.documentoId = "otro");
rechaza(r => r.vinculo.eleccion.escalas[0].valor = { tipo: "cantidad", valor: 2, unidad: "s" });
rechaza(r => r.vinculo.opciones.presupuesto++);
rechaza(r => r.formulaciones[0].desarrollo[0].antes.igualdad.izquierda = { tipo: "simbolo", id: "fantasma" });
rechaza(r => r.formulaciones[0].desarrollo[0].despues.igualdad.izquierda = { tipo: "derivada", respecto: "c", orden: 1, expresion: { tipo: "simbolo", id: "c" } });
rechaza(r => r.formulaciones[0].desarrollo[0].operacion = "inventada");
rechaza(r => r.formulaciones[0].desarrollo = []);
rechaza(r => r.formulaciones[0].ecuaciones.pop());
rechaza(r => r.formulaciones[0].equivalencia.estado = "validado_fisicamente");
rechaza(r => r.formulaciones[0].equivalencia.restricciones.push("restriccion_fantasma"));
rechaza(r => r.formulaciones[0].grupos[0].definicion = { tipo: "funcion", nombre: "eval", argumentos: [{ tipo: "numero", valor: 1 }] });
rechaza(r => r.formulaciones[0].simbolos.push(r.formulaciones[0].simbolos[0]));
rechaza(r => r.cobertura.siguiente = 0);
rechaza(r => r.estado = "rechazado");
const falla = archivo("requiere-datos", "resultado"), pide = archivo("requiere-datos", "solicitud");
const conResultado = { ...falla, formulaciones: original.formulaciones };
assert.throws(() => lector.leerRespuestaNucleo(conResultado, pide)); comprobaciones++;
for (const n of ["mapa-logaritmico", "mapa-afin-temperatura"]) {
  const s = archivo(n, "solicitud"), viejo = s.documento;
  const v2 = documento.migrarDocumentoV2(viejo);
  assert.equal(v2.version, 2); assert.deepEqual(v2.modelo, viejo.modelo); comprobaciones++;
  v2.formas.find(f => f.id === s.formaId).transformaciones = s.transformaciones;
  const leido = documento.leerDocumento(JSON.stringify(v2)); assert.deepEqual(leido, v2); comprobaciones++;
  const texDocumento = latex.exportarLatex(leido);
  for (const mapa of s.transformaciones) {
    assert(texDocumento.includes(`${latex.nombreLatex(mapa.variableId)} = ${latex.latexExpresion(mapa.directa)}`));
    assert(texDocumento.includes(`${latex.nombreLatex(mapa.nuevoId)} = ${latex.latexExpresion(mapa.inversa)}`));
    for (const constante of mapa.constantes) assert(texDocumento.includes(latex.nombreLatex(constante.id)));
  }
  comprobaciones++;
  const peticion = lector.prepararSolicitud(v2);
  assert.equal(peticion.documento.version, 1);
  assert(peticion.documento.formas.every(f => !("transformaciones" in f)));
  assert.deepEqual(peticion.transformaciones, s.transformaciones); comprobaciones++;
  const malo = structuredClone(v2); malo.formas[0].transformaciones[0].directa = { tipo: "simbolo", id: "no_existe" };
  assert.throws(() => documento.leerDocumento(JSON.stringify(malo))); comprobaciones++;
  const ilegal = structuredClone(v2); ilegal.version = 1;
  assert.throws(() => documento.leerDocumento(JSON.stringify(ilegal))); comprobaciones++;
}
const compatible = structuredClone(original);
compatible.vinculo = Object.fromEntries(Object.entries(compatible.vinculo).reverse());
assert(lector.leerRespuestaNucleo(compatible, sol)); comprobaciones++;

const fEscalada = lector.formulacionesDe(lector.leerRespuestaNucleo(archivo("v2-funcion-escalada", "resultado"), archivo("v2-funcion-escalada", "solicitud")))[0];
assert.equal(fEscalada.funcionesAdimensionales?.length, 1);
assert.equal(fEscalada.funcionesAdimensionales[0].id, "Dh");
assert.equal(fEscalada.funcionesAdimensionales[0].funcionId, "Dc");
assert.equal(fEscalada.funcionesAdimensionales[0].escalaId, "Dstar");
assert.match(fEscalada.funcionesAdimensionales[0].definicion, /Dh\(w1\)\s*=\s*Dc\(c_ref w1\)\s*\/\s*Dstar/);
comprobaciones++;

const fRefUbic = lector.formulacionesDe(lector.leerRespuestaNucleo(archivo("v2-referencias-ubicacion", "resultado"), archivo("v2-referencias-ubicacion", "solicitud")))[0];
const condFlujo = fRefUbic.condiciones.find(c => c.id === "flujo");
assert(condFlujo && condFlujo.lugar);
assert.equal(condFlujo.lugar.variableId, "x_ad");
assert.equal(condFlujo.lugar.variableOriginal, "x");
assert.equal(condFlujo.lugar.extremo, "hasta");
assert.equal(condFlujo.lugar.original.tipo, "simbolo");
assert.equal(condFlujo.lugar.original.id, "ell");
comprobaciones++;

console.log(`Integración: ${comprobaciones} verificaciones; ${pasos} pasos reales del núcleo renderizados sin error. Vínculos, referencias, rechazos, mapas v2 y exportación completos.`);
