/** Informe autónomo (HTML imprimible) de una formulación: solo contiene lo
 * que publicó el núcleo. Sustituye al informe anterior, que añadía análisis
 * genéricos que no se calculaban a partir del modelo. */
import katex from "katex";
import type { Expresion, Modelo, PasoDesarrollo } from "./contrato";
import type { FormulacionNucleo, RespuestaNucleo } from "./contratoNucleo";
import type { ResultadosEstudio } from "./contratoEstudio";
import { latexExpresion, nombreLatex } from "./exportar";
import { KATEX_CSS } from "./katexCss";

const esc = (t: string) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
function tex(latex: string, bloque = false): string {
  try { return katex.renderToString(latex, { displayMode: bloque, throwOnError: true, output: "htmlAndMathml" }); }
  catch { return `<code>${esc(latex)}</code>`; }
}
const igualdad = (i: Expresion, d: Expresion) => tex(`${latexExpresion(i)} = ${latexExpresion(d)}`, true);
const num = (v: number | null | undefined) => v === null || v === undefined || !Number.isFinite(v) ? "—" : Math.abs(v) >= 1e5 || (Math.abs(v) < 1e-3 && v !== 0) ? v.toExponential(3) : String(Number(v.toPrecision(5)));

function paso(p: PasoDesarrollo, i: number): string {
  const lado = (x: PasoDesarrollo["antes"]) => x.tipo === "igualdad" ? igualdad(x.igualdad.izquierda, x.igualdad.derecha) : tex(latexExpresion(x.expresion), true);
  return `<li><h4>${i + 1}. ${esc(p.regla)}</h4><p class="just">${esc(p.justificacion)}</p>${lado(p.antes)}<p class="flecha">⟶</p>${lado(p.despues)}${p.supuestos.length ? `<p class="sup">Supuestos: ${esc(p.supuestos.join("; "))}</p>` : ""}</li>`;
}

export function generarInforme({ nombre, modelo, f, indice, respuesta, estudio }: {
  nombre: string; modelo: Modelo; f: FormulacionNucleo; indice: number; respuesta: RespuestaNucleo; estudio?: ResultadosEstudio;
}): string {
  const s: string[] = [];
  s.push(`<h1>${esc(nombre)} · Forma ${indice + 1}</h1>`);
  s.push(`<p class="meta">Núcleo ${esc(respuesta.nucleo)} · modelo ${esc(modelo.id)} revisión ${modelo.revision} · ${new Date().toLocaleString("es")}</p>`);
  s.push(`<p class="estado">Equivalencia ${f.equivalencia.estado === "demostrada" ? "demostrada bajo sus restricciones" : "NO demostrada"} · normalización ${esc(f.normalizacion.estado)}</p>`);
  s.push("<h2>Modelo original</h2>", ...modelo.ecuaciones.map(e => igualdad(e.izquierda, e.derecha)));
  s.push("<h2>Formulación adimensional</h2>", ...f.ecuaciones.map(e => igualdad(e.igualdad.izquierda, e.igualdad.derecha)));
  if (f.condiciones.length) s.push("<h3>Condiciones</h3>", ...f.condiciones.map(c => `<p>${esc(c.tipo)} · ${esc(c.ubicacion)}</p>${igualdad(c.ecuacion.izquierda, c.ecuacion.derecha)}`));
  if (f.dominios.length) s.push("<h3>Dominios</h3>", ...f.dominios.map(d => tex(`${latexExpresion(d.desde)} \\le ${nombreLatex(d.variableId)} \\le ${latexExpresion(d.hasta)}`, true)));
  s.push("<h3>Cambios de variable</h3>", ...[...f.directa, ...f.inversa].map(m => tex(`${nombreLatex(m.simboloId)} = ${latexExpresion(m.expresion)}`, true)));
  if (f.libres.length) s.push(`<p>Escalas libres: ${esc(f.libres.join(", "))}. Cada elección define un miembro de la familia.</p>`);
  if (f.grupos.length) {
    const lect = new Map((estudio?.estructura?.grupos ?? []).map(g => [g.grupoId, g]));
    const val = new Map((estudio?.valores?.grupos ?? []).map(g => [g.grupoId, g.valor]));
    s.push("<h2>Grupos</h2><table><thead><tr><th>Grupo</th><th>Definición</th><th>Lectura</th><th>Valor</th></tr></thead><tbody>");
    for (const g of f.grupos) {
      const l = lect.get(g.id);
      s.push(`<tr><td>${tex(nombreLatex(g.id))}</td><td>${tex(latexExpresion(g.definicion))}</td><td>${esc([l?.nombreClasico, l?.lecturas[0]?.lectura].filter(Boolean).join(" · "))}</td><td>${num(val.get(g.id))}</td></tr>`);
    }
    s.push("</tbody></table>");
  }
  if (f.restricciones.length) s.push("<h3>Restricciones</h3><ul>", ...f.restricciones.map(r => `<li>${esc(r.id)}: ${tex(latexExpresion(r.expresion))} ${r.tipo === "positivo" ? "&gt; 0" : r.tipo === "negativo" ? "&lt; 0" : r.tipo === "no_nulo" ? "≠ 0" : r.tipo === "igualdad" && r.valor ? `= ${tex(latexExpresion(r.valor))}` : ""} — ${esc(r.motivo)}</li>`), "</ul>");
  if (respuesta.gruposPi) s.push(`<h3>Teorema Π</h3><p>Rango dimensional ${respuesta.gruposPi.rango}; ${respuesta.gruposPi.numeroGrupos} grupos independientes.</p>`, ...respuesta.gruposPi.bases.slice(0, 3).map(b => `<p>${esc(b.id)}: ${b.grupos.map(g => tex(`${nombreLatex(g.id)} = ${latexExpresion(g.definicion)}`)).join(" , ")}</p>`));
  const e = estudio;
  if (e?.asintotica?.estado === "calculado") {
    s.push("<h2>Balanza dominante</h2>");
    for (const x of e.asintotica.ecuaciones ?? []) {
      const capa = x.espacial?.capa;
      s.push(`<p><strong>${esc(x.id)}</strong>: dominan ${x.dominantes.length}, despreciables ${x.despreciables.length}.${capa?.tipo === "perturbacion_singular" ? ` Perturbación singular: capa de espesor ${num(capa.espesor)}${capa.ubicacion ? ` (${esc(capa.ubicacion.lado)})` : ""}.` : ""}</p>`);
      if (x.reducida) s.push(igualdad(x.reducida.izquierda, x.reducida.derecha));
    }
    s.push(`<p class="metodo">${esc(e.asintotica.motivo)}</p>`);
  }
  if (e?.escalas?.estado === "calculado") {
    s.push("<h2>Escalas y malla</h2>");
    for (const c of e.escalas.coordenadas ?? []) if (c.estado === "calculado") s.push(`<p>${esc(c.coordenada)}: difusividad ${num(c.difusividad)}, velocidad ${num(c.velocidad)}${c.malla ? `, ${c.malla.nodosRecomendados} nodos recomendados (Péclet de celda ${num(c.malla.pecletCelda)})` : ""}${c.rigidez ? `, rigidez ${num(c.rigidez.cociente)} → ${esc(c.rigidez.recomendacion)}` : ""}.</p>`);
  }
  if (e?.estabilidad?.estado === "calculado") {
    s.push("<h2>Estados homogéneos</h2>");
    for (const x of e.estabilidad.estados ?? []) s.push(`<p>${esc(Object.entries(x.u).map(([k, v]) => `${k} = ${num(v)}`).join(", "))}: ${esc(x.homogeneo)}; ${esc(x.espacial.map(c => c.estado === "calculado" ? `${c.coordenada}: ${c.clase}${c.kCritico !== null ? ` (k ≈ ${num(c.kCritico)})` : ""}` : `${c.coordenada}: fuera de alcance`).join("; "))}.</p>`);
  }
  if (e?.simetrias?.estado === "calculado" && e.simetrias.reducciones?.length) {
    s.push("<h2>Reducciones exactas</h2>");
    for (const r of e.simetrias.reducciones) if (r.estado === "calculado") {
      s.push(`<p>${r.tipo === "semejanza" ? "Semejanza" : "Onda viajera"}: ${r.variable ? tex(`${nombreLatex(r.variable.id)} = ${latexExpresion(r.variable.definicion)}`) : ""}</p>`, ...(r.ecuaciones ?? []).map(q => tex(`${latexExpresion(q.ecuacion.izquierda)} = 0`, true)));
    }
  }
  s.push("<h2>Desarrollo completo</h2><ol class=\"pasos\">", ...f.desarrollo.map(paso), "</ol>");
  s.push(`<p class="metodo">Alcance del certificado: ${esc(f.equivalencia.alcance)}</p>`);
  return `<!doctype html><html lang="es"><head><meta charset="utf-8"><title>${esc(nombre)} · Forma ${indice + 1}</title><style>${KATEX_CSS}
body{font:15px/1.6 Georgia,"Times New Roman",serif;color:#1f2a1b;max-width:860px;margin:32px auto;padding:0 20px}
h1{font-size:24px;font-weight:600}h2{font-size:18px;margin-top:32px;border-bottom:1px solid #cfd6c4;padding-bottom:4px}h3{font-size:15px;margin-top:20px}h4{font-size:14px;margin:0}
.meta,.metodo,.sup,.just{color:#5d6853;font-size:13px}.estado{font-weight:600}.flecha{color:#8a9580;margin:2px 0}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid #e1e5da;padding:6px 8px;text-align:left;vertical-align:top}
.pasos li{margin:14px 0;page-break-inside:avoid}.katex-display{overflow-x:auto;overflow-y:hidden}
@media print{body{margin:0}h2{page-break-after:avoid}}</style></head><body>${s.join("\n")}</body></html>`;
}

export function abrirInforme(html: string, nombreArchivo: string) {
  const url = URL.createObjectURL(new Blob([html], { type: "text/html;charset=utf-8" }));
  const ventana = window.open(url, "_blank");
  if (!ventana) {
    const a = document.createElement("a"); a.href = url; a.download = nombreArchivo; a.click();
  }
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}
