import type { Dimension, Documento, Escala, Expresion } from "./contrato";

/** Presentación del árbol declarado; no simplifica ni transforma expresiones. */
const LETRAS_GRIEGAS: Record<string, string> = {
  theta: "\\theta", alpha: "\\alpha", beta: "\\beta", gamma: "\\gamma",
  delta: "\\delta", epsilon: "\\varepsilon", zeta: "\\zeta", eta: "\\eta",
  kappa: "\\kappa", lambda: "\\lambda", mu: "\\mu", nu: "\\nu", xi: "\\xi",
  pi: "\\pi", rho: "\\rho", sigma: "\\sigma", tau: "\\tau", phi: "\\phi",
  chi: "\\chi", psi: "\\psi", omega: "\\omega", Gamma: "\\Gamma", Delta: "\\Delta",
  Theta: "\\Theta", Lambda: "\\Lambda", Xi: "\\Xi", Pi: "\\Pi", Sigma: "\\Sigma",
  Phi: "\\Phi", Psi: "\\Psi", Omega: "\\Omega"
};

const ESPECIALES: Record<string, string> = {
  Dstar: "D^{*}",
  Dh: "\\hat{D}",
  Dc: "D",
  ell: "\\ell",
  c0: "c_{0}",
  tf: "t_{f}",
  tref: "t_{\\mathrm{ref}}",
  xref: "x_{\\mathrm{ref}}",
  cref: "c_{\\mathrm{ref}}",
  Tref: "T_{\\mathrm{ref}}",
  gbeta: "g\\beta",
  alphaT: "\\alpha_{T}",
  aT: "\\alpha_{T}",
  DAB: "D_{\\mathrm{AB}}",
  De: "D_{e}",
  rho0: "\\rho_{0}",
  v0: "v_{0}",
  cs: "c_{s}",
  Da: "\\mathrm{Da}",
  Bi: "\\mathrm{Bi}",
  Pe: "\\mathrm{Pe}",
  Pr: "\\mathrm{Pr}",
  Re: "\\mathrm{Re}",
  Sc: "\\mathrm{Sc}",
  Sh: "\\mathrm{Sh}",
  Nu: "\\mathrm{Nu}",
  Le: "\\mathrm{Le}",
  Fo: "\\mathrm{Fo}",
  Gr: "\\mathrm{Gr}",
  Ma: "\\mathrm{Ma}",
  Thiele: "\\phi_{\\mathrm{Thiele}}",
  inf: "\\infty",
  infty: "\\infty",
};

export function nombreLatex(id: string): string {
  if (!id) return "";
  if (id in ESPECIALES) return ESPECIALES[id];

  // 0. Limpiar posibles comas en nombres compuestos como "cC,ref" o "cA,ref"
  const cleanId = id.replace(/,/g, "_");
  if (cleanId in ESPECIALES) return ESPECIALES[cleanId];

  // Si ya tiene circunflejo: \hat{c}A -> \hat{c}_{A}
  if (cleanId.startsWith("\\hat")) {
    return cleanId
      .replace(/^\\hat\{?([a-zA-Z])\}?_?([A-Za-z0-9]+)$/, (_, base, sub) => `\\hat{${base}}_{${sub}}`)
      .replace(/^\\hat\{?([a-zA-Z])\}?([A-Z0-9])$/, (_, base, sub) => `\\hat{${base}}_{${sub}}`);
  }

  // Variables adimensionales (con acento circunflejo ^): cA_ad, c_A_ad, cA_adim, etc.
  const matchAd = /^(.+?)[_]?(ad|adim)$/.exec(cleanId);
  if (matchAd && matchAd[1].length >= 1) {
    const base = matchAd[1];
    if (base in LETRAS_GRIEGAS) return `\\hat{${LETRAS_GRIEGAS[base]}}`;
    if (base in ESPECIALES) return `\\hat{${ESPECIALES[base]}}`;

    const matchUnder = /^([A-Za-z]+)_([A-Za-z0-9]+)$/.exec(base);
    if (matchUnder) {
      const pfx = matchUnder[1] in LETRAS_GRIEGAS ? LETRAS_GRIEGAS[matchUnder[1]] : matchUnder[1];
      const sfx = /^[0-9]+$/.test(matchUnder[2]) ? matchUnder[2] : matchUnder[2].length === 1 ? matchUnder[2] : `\\mathrm{${matchUnder[2]}}`;
      return `\\hat{${pfx}}_{${sfx}}`;
    }

    const matchMayus = /^([a-zA-Z])([A-Z])$/.exec(base);
    if (matchMayus) return `\\hat{${matchMayus[1]}}_{${matchMayus[2]}}`;

    const matchNum = /^([A-Za-z]+)([0-9]+)$/.exec(base);
    if (matchNum) {
      const pfx = matchNum[1] in LETRAS_GRIEGAS ? LETRAS_GRIEGAS[matchNum[1]] : matchNum[1];
      return `\\hat{${pfx}}_{${matchNum[2]}}`;
    }

    if (/^[A-Za-z]$/.test(base)) return `\\hat{${base}}`;
    return `\\hat{\\mathrm{${base}}}`;
  }

  // Grupos Pi: pi1, pi2, pi_1, pi_2
  const matchPi = /^pi_?([0-9]+)$/i.exec(cleanId);
  if (matchPi) return `\\Pi_{${matchPi[1]}}`;

  // Escalas de referencia compuestas: cA_ref, c_A_ref, cB_ref, c_B_ref, t_ref, x_ref, tref, xref, etc.
  const matchRef = /^(.+?)[_]?(ref|scale|\*|0|s|inf)$/.exec(cleanId);
  if (matchRef && matchRef[1].length >= 1) {
    const rawBase = matchRef[1];
    const suf = matchRef[2] === "*" ? "{*}" : matchRef[2] === "0" ? "0" : matchRef[2] === "s" ? "s" : matchRef[2] === "inf" ? "\\infty" : "\\mathrm{ref}";
    const baseUnder = /^([A-Za-z]+)_([A-Za-z0-9]+)$/.exec(rawBase);
    if (baseUnder) {
      const pfx = baseUnder[1] in LETRAS_GRIEGAS ? LETRAS_GRIEGAS[baseUnder[1]] : baseUnder[1];
      const sfx = /^[0-9]+$/.test(baseUnder[2]) ? baseUnder[2] : baseUnder[2].length === 1 ? baseUnder[2] : `\\mathrm{${baseUnder[2]}}`;
      return `${pfx}_{${sfx},${suf}}`;
    }
    const baseMayus = /^([a-zA-Z])([A-Z])$/.exec(rawBase);
    if (baseMayus) {
      return `${baseMayus[1]}_{${baseMayus[2]},${suf}}`;
    }
    const baseNum = /^([A-Za-z]+)([0-9]+)$/.exec(rawBase);
    if (baseNum) {
      const pfx = baseNum[1] in LETRAS_GRIEGAS ? LETRAS_GRIEGAS[baseNum[1]] : baseNum[1];
      return `${pfx}_{${baseNum[2]},${suf}}`;
    }
    const baseGreek = rawBase in LETRAS_GRIEGAS ? LETRAS_GRIEGAS[rawBase] : rawBase;
    return `${baseGreek}_{${suf}}`;
  }

  if (cleanId in LETRAS_GRIEGAS) return LETRAS_GRIEGAS[cleanId];

  // Notación con guion bajo general: c_A, c_B, c_C, k_1, k_2, a_b, x_max, T_inf
  const subindice = /^([A-Za-z0-9]+)_([A-Za-z0-9]+)$/.exec(cleanId);
  if (subindice) {
    const pfx = subindice[1] in LETRAS_GRIEGAS ? LETRAS_GRIEGAS[subindice[1]] : subindice[1];
    const sfx = subindice[2] === "inf" ? "\\infty" : /^[0-9]+$/.test(subindice[2]) ? subindice[2] : subindice[2].length === 1 ? subindice[2] : `\\mathrm{${subindice[2]}}`;
    return `${pfx}_{${sfx}}`;
  }

  // Notación subíndice por mayúscula: cA -> c_{A}, cB -> c_{B}, cC -> c_{C}, uA -> u_{A}
  const subMayus = /^([a-z])([A-Z])$/.exec(cleanId);
  if (subMayus) return `${subMayus[1]}_{${subMayus[2]}}`;

  // Notación parámetro numerado: k1 -> k_{1}, k2 -> k_{2}, D1 -> D_{1}, D2 -> D_{2}
  const subindiceNum = /^([A-Za-z]+)([0-9]+)$/.exec(cleanId);
  if (subindiceNum) {
    const pfx = subindiceNum[1] in LETRAS_GRIEGAS ? LETRAS_GRIEGAS[subindiceNum[1]] : subindiceNum[1];
    return `${pfx}_{${subindiceNum[2]}}`;
  }

  if (/^[A-Za-z]$/.test(cleanId)) return cleanId;

  const escapes: Record<string, string> = { "\\": "\\backslash{}", "{": "\\{", "}": "\\}", "_": "\\_", "^": "\\text{\\textasciicircum}", "~": "\\text{\\textasciitilde}", "%": "\\%", "#": "\\#", "&": "\\&", "$": "\\$" };
  return `\\mathrm{${cleanId.replace(/[\\{}_\^~%#&$]/g, c => escapes[c] ?? c)}}`;
}
const nombre = nombreLatex;
export function dimensionLatex(d: Dimension): string {
  if (d === null) return "\\text{Pendiente}";
  return Object.entries(d).filter(([, r]) => r.n !== 0).map(([k, r]) => `\\mathsf{${nombre(k)}}${r.n === r.d ? "" : `^{${r.d === 1 ? r.n : `\\frac{${r.n}}{${r.d}}`}}`}`).join("\\,") || "1";
}
export function escalaLatex(e: Escala): string {
  if (!e.transformar) return `${nombre(e.simboloId)}\\;\\text{dimensional}`;
  const valor = e.valor.tipo === "libre" ? `${nombre(e.simboloId)}_{*}` : e.valor.tipo === "cantidad" ? `${latexExpresion({ tipo: "numero", valor: e.valor.valor })}\\,\\mathrm{${nombre(e.valor.unidad)}}` : latexExpresion(e.valor.expresion);
  return `${nombre(e.simboloId)} = ${e.valor.tipo === "expresion" ? `\\left(${valor}\\right)` : valor}\\,${nombre(e.nuevoNombre)}`;
}
function signo(e: Expresion): { negativo: boolean; magnitud: Expresion } {
  if (e.tipo === "numero" && e.valor < 0) return { negativo: true, magnitud: { ...e, valor: -e.valor } };
  if (e.tipo === "producto" && e.argumentos[0]?.tipo === "numero" && e.argumentos[0].valor < 0) {
    const [primero, ...resto] = e.argumentos;
    const factores = primero.tipo === "numero" && primero.valor === -1 && resto.length ? resto : [{ ...primero, valor: -(primero as { valor: number }).valor } as Expresion, ...resto];
    return { negativo: true, magnitud: factores.length === 1 ? factores[0] : { tipo: "producto", argumentos: factores } };
  }
  return { negativo: false, magnitud: e };
}
export function latexExpresion(e: Expresion): string {
  function l(e: Expresion, contexto = 0): string {
    let texto: string, prioridad = 4;
    switch (e.tipo) {
      case "numero": { const [m, ex] = String(e.valor).split("e"); texto = ex ? `${m}\\times 10^{${Number(ex)}}` : m; if (e.valor < 0 || ex) prioridad = 2; break; }
      case "simbolo": texto = nombre(e.id); break;
      case "suma": {
        const terminos = (x: Expresion): Expresion[] => x.tipo === "suma" ? x.argumentos.flatMap(terminos) : [x];
        texto = terminos(e).map((t, i) => { const s = signo(t); return `${s.negativo ? (i ? " - " : "-") : (i ? " + " : "")}${l(s.magnitud)}`; }).join(""); prioridad = 1; break;
      }
      case "producto": {
        const s = signo(e);
        if (s.negativo) texto = `-${l(s.magnitud, 2)}`;
        else texto = e.argumentos.map((a, i) => `${i ? (a.tipo === "numero" ? "\\cdot " : "\\,") : ""}${i && signo(a).negativo ? `\\left(${l(a)}\\right)` : l(a, 2)}`).join("");
        prioridad = 2; break;
      }
      case "cociente": {
        // Reducción algebraica de fracciones compuestas para presentación matemática óptima:
        // 1. A / (B / C) => (A * C) / B
        if (e.denominador.tipo === "cociente") {
          const numEquiv: Expresion = {
            tipo: "producto",
            argumentos: [e.numerador, e.denominador.denominador]
          };
          const denEquiv = e.denominador.numerador;
          texto = `\\frac{${l(numEquiv, 2)}}{${l(denEquiv, 2)}}`;
          break;
        }
        // 2. (A / B) / C => A / (B * C)
        if (e.numerador.tipo === "cociente") {
          const numEquiv = e.numerador.numerador;
          const denEquiv: Expresion = {
            tipo: "producto",
            argumentos: [e.numerador.denominador, e.denominador]
          };
          texto = `\\frac{${l(numEquiv, 2)}}{${l(denEquiv, 2)}}`;
          break;
        }
        const num = l(e.numerador);
        const den = l(e.denominador);
        texto = `\\frac{${num}}{${den}}`;
        break;
      }
      case "potencia": texto = `${l(e.base, 4)}^{${l(e.exponente)}}`; prioridad = 3; break;
      case "funcion": texto = `\\operatorname{${e.nombre}}\\left(${e.argumentos.map(a => l(a)).join(", ")}\\right)`; break;
      case "llamada": texto = `${nombre(e.funcionId === "Dc" ? "D" : e.funcionId)}\\left(${e.argumentos.map(a => l(a)).join(", ")}\\right)`; break;
      case "derivada": { const orden = e.orden === 1 ? "" : `^{${e.orden}}`; texto = `\\frac{\\partial${orden} ${l(e.expresion, 4)}}{\\partial ${nombre(e.respecto)}${orden}}`; prioridad = 3; break; }
      default: {
        if (e.tipo === "divergencia") {
          texto = `\\nabla\\cdot\\left(${l(e.expresion, 1)}\\right)`;
        } else if (e.tipo === "gradiente") {
          texto = `\\nabla ${l(e.expresion, 4)}`;
        } else {
          texto = `\\nabla^{2}${e.coordenadas.length > 1 ? `_{${e.coordenadas.map(nombre).join(",")}}` : ""} ${l(e.expresion, 4)}`;
        }
        prioridad = 3;
        break;
      }
    }
    return prioridad < contexto ? `\\left(${texto}\\right)` : texto;
  }
  return l(e);
}
export function exportarLatex(doc: Documento): string {
  return ["\\documentclass[11pt,a4paper]{article}", "\\usepackage[utf8]{inputenc}", "\\usepackage[T1]{fontenc}", "\\usepackage[spanish]{babel}", "\\usepackage{amsmath,amssymb}", "\\usepackage[margin=25mm]{geometry}", "\\begin{document}", "\\section*{Modelo original y elecciones de escalas}", "Modelo declarado. Sin transformación ni grupos calculados.",
    `% Documento ${doc.id.replace(/[\r\n]/g, " ")} · revisión ${doc.modelo.revision}`,
    ...doc.modelo.ecuaciones.map(e => `\\[${latexExpresion(e.izquierda)} = ${latexExpresion(e.derecha)}\\]`),
    ...doc.modelo.dominios.map(d => `\\[${latexExpresion(d.desde)} \\le ${nombre(d.variableId)} \\le ${latexExpresion(d.hasta)}\\]`),
    ...doc.modelo.condiciones.map(c => `\\[${latexExpresion(c.ecuacion.izquierda)} = ${latexExpresion(c.ecuacion.derecha)}\\]`),
    "\\section*{Símbolos y dimensiones declaradas}",
    ...doc.modelo.simbolos.map(s => `\\[ [${nombre(s.id)}] = ${dimensionLatex(s.dimension)} \\]`),
    ...doc.formas.flatMap(f => [`\\subsection*{\\ensuremath{${nombre(f.nombre)}}}`, `Revisión del modelo: ${f.modeloRevision}.`, ...f.escalas.map(e => `\\[${escalaLatex(e)}\\]`),
      ...(f.transformaciones ?? []).flatMap(m => ["Cambio de variable declarado, pendiente de evaluación:", `\\[${nombre(m.variableId)} = ${latexExpresion(m.directa)}\\]`, `\\[${nombre(m.nuevoId)} = ${latexExpresion(m.inversa)}\\]`,
        ...m.constantes.map(c => `Constante de ${c.papel}:\n\\[${nombre(c.id)}${c.valor.tipo === "cantidad" ? ` = ${latexExpresion({ tipo: "numero", valor: c.valor.valor })}\\,${nombre(c.valor.unidad)}` : c.valor.tipo === "expresion" ? ` = ${latexExpresion(c.valor.expresion)}` : "\\;\\text{libre}"},\\qquad [${nombre(c.id)}] = ${dimensionLatex(c.dimension)}\\]`),
        ...([[m.variableId, m.dominio.original], [m.nuevoId, m.dominio.nuevo]] as const).filter(([, signo]) => signo !== null).map(([id, signo]) => `\\[${nombre(id)} ${signo === "positivo" ? ">" : "<"} 0\\]`)]),
      ...f.objetivos.map(o => `Objetivo declarado, sin evaluar:\n\\[${o.termino ? latexExpresion(o.termino) : `\\text{${nombre(o.terminoId ?? o.id)}}`}${o.accion === "normalizar" ? ` = ${o.valor}` : "\\;\\text{conservar como grupo}"}\\]`)]),
    "\\end{document}"].join("\n\n");
}

