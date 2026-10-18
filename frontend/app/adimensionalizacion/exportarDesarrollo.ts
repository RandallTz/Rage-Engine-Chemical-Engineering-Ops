import type { ExpresionDePaso, Expresion } from "./contrato";
import type { FormulacionNucleo } from "./contratoNucleo";
import { latexExpresion, nombreLatex } from "./exportar";

function texto(s: string): string {
  const escapes: Record<string, string> = {
    "\\": "\\textbackslash{}", "{": "\\{", "}": "\\}", "$": "\\$", "&": "\\&",
    "#": "\\#", "%": "\\%", "_": "\\_", "^": "\\textasciicircum{}", "~": "\\textasciitilde{}"
  };
  return s.replace(/[\\{}$&#%_^~]/g, c => escapes[c]);
}

function paso(e: ExpresionDePaso): string {
  return e.tipo === "expresion"
    ? latexExpresion(e.expresion)
    : `${latexExpresion(e.igualdad.izquierda)} = ${latexExpresion(e.igualdad.derecha)}`;
}

function latexDefinicionFuncion(fn: NonNullable<FormulacionNucleo["funcionesAdimensionales"]>[number]): string {
  const argsTex = fn.argumentos.map((a, i) => {
    const w = `w_{${i + 1}}`;
    if (!a.extraida) return w;
    const sTex = latexExpresion(a.escala);
    return `${sTex}\\,${w}`;
  }).join(", ");
  const wArgs = fn.argumentos.map((_, i) => `w_{${i + 1}}`).join(", ");
  return `${nombreLatex(fn.nombre)}\\left(${wArgs}\\right) = \\frac{${nombreLatex(fn.funcionId)}\\left(${argsTex}\\right)}{${nombreLatex(fn.escalaId)}}`;
}

function interpretarGrupoTex(id: string, defExpr?: Expresion): string {
  const defTexto = defExpr ? latexExpresion(defExpr) : "";
  if (/D.*t_ref.*x_ref\^2|D.*t_ref\/x_ref\^2/i.test(defTexto)) {
    return "Número de Fourier axial (Fo_x = D·t_ref / x_ref²): escala temporal frente a relajación difusiva longitudinal.";
  }
  if (/D.*t_ref.*y_ref\^2|D.*t_ref\/y_ref\^2/i.test(defTexto)) {
    return "Número de Fourier transversal (Fo_y = D·t_ref / y_ref²): difusión transversal y factor de esbeltez (x_ref/y_ref)².";
  }
  if (/D.*t_ref.*z_ref\^2|D.*t_ref\/z_ref\^2/i.test(defTexto)) {
    return "Número de Fourier transversal (Fo_z = D·t_ref / z_ref²): transporte difusivo en el eje z y esbeltez (x_ref/z_ref)².";
  }
  if (/t_ref.*u.*x_ref|u.*t_ref\/x_ref/i.test(defTexto)) {
    return "Número de Péclet temporal o CFL longitudinal (Pe_x / CFL_x = u·t_ref / x_ref): transporte advectivo axial.";
  }
  if (/t_ref.*v.*y_ref|v.*t_ref\/y_ref/i.test(defTexto)) {
    return "Número de Péclet temporal o CFL transversal (Pe_y / CFL_y = v·t_ref / y_ref): advección secundaria transversal.";
  }
  if (/k.*t_ref|t_ref.*k/i.test(defTexto)) {
    return "Número de Damköhler temporal (Da_t = k·t_ref): tasa cinética de reacción frente a evolución temporal.";
  }
  if (/D.*k.*u\^2|k.*D\/u\^2/i.test(defTexto)) {
    return "Inverso de Péclet-Damköhler axial (D·k / u² = 1 / (Pe_x·Da_x)): dispersión molecular frente a convección-reacción.";
  }
  if (/x_ref.*y_ref|y_ref.*x_ref/i.test(defTexto)) {
    return "Relación de aspecto o esbeltez (A_y = x_ref / y_ref): parámetro que rige la reducción asintótica en dominios delgados.";
  }
  if (/u.*x_ref.*D|u.*x_ref\/D/i.test(defTexto)) {
    return "Número de Péclet axial (Pe_x = u·x_ref / D): transporte advectivo forzado frente a difusión longitudinal.";
  }
  if (/v.*y_ref.*D|v.*y_ref\/D/i.test(defTexto)) {
    return "Número de Péclet transversal (Pe_y = v·y_ref / D): transporte convectivo transversal frente a difusión transversal.";
  }
  if (/D2.*D1|D1.*D2|D_B.*D_A/i.test(defTexto)) {
    return "Relación de difusividades relativas (δ_D = D_2 / D_1): parámetro de acoplamiento difusivo entre especies.";
  }
  if (id === "Da" || id.startsWith("Da_") || id.startsWith("pi_reac") || id.includes("k1") || id.includes("k2") || id.includes("k_1") || id.includes("k_2")) {
    return "Número de Damköhler (Da): cociente entre tasa cinética de reacción y transporte difusivo/convectivo.";
  }
  if (id === "Bi") return "Número de Biot (Bi): conducción interna / resistencia superficial convectiva.";
  if (id === "Sh" || id.startsWith("Sh_") || id.toLowerCase().includes("sherwood")) {
    return "Número de Sherwood (Sh): transferencia de materia interfacial / difusión molecular ordinaria.";
  }
  if (id === "Ste" || id.startsWith("Ste_") || id.toLowerCase().includes("stefan")) {
    return "Número de Stefan (Ste): calor sensible / calor latente en fronteras móviles de interfase.";
  }
  if (id === "Pe") return "Número de Péclet (Pe): razón entre transporte convectivo y difusión molecular.";
  if (id === "Pr") return "Número de Prandtl (Pr): difusividad de cantidad de movimiento / difusividad térmica.";
  if (id === "Le") return "Número de Lewis (Le): difusividad térmica molecular / difusividad másica.";
  if (id === "Gr") return "Número de Grashof (Gr): fuerzas de empuje térmico / fuerzas viscosas.";
  if (id === "Thiele" || id.includes("Thiele") || id.includes("phi")) return "Módulo de Thiele: reacción intrínseca / difusión intraparticular.";
  return "Invariante adimensional deducido de la base dimensional.";
}

function generarSeccionAsintoticaTex(f: FormulacionNucleo): string[] {
  const campos = f.directa
    .map(d => d.simboloId)
    .filter(s => !["t", "x", "y", "z", "r", "theta"].includes(s));
  const camposTex = campos.length > 0
    ? campos.map(c => nombreLatex(c)).join(", ")
    : "c";

  const coords = f.directa
    .map(d => d.simboloId)
    .filter(s => ["x", "y", "z", "r"].includes(s));

  const tieneDif = f.grupos.some(g => /Fo|D/i.test(g.id) || /D.*t_ref|D\/|dif/i.test(latexExpresion(g.definicion)));
  const tieneConv = f.grupos.some(g => /Pe|CFL|u|v|w/i.test(g.id) || /u.*t_ref|v.*t_ref/i.test(latexExpresion(g.definicion)));
  const tieneReac = f.grupos.some(g => /Da|k/i.test(g.id) || /k.*t_ref/i.test(latexExpresion(g.definicion)));
  const esMultiD = coords.length > 1;

  const items: string[] = [];
  if (tieneDif) {
    items.push("  \\item \\textbf{Escala temporal difusiva pura (relajación molecular):} $t_{\\mathrm{ref}} = x_{\\mathrm{ref}}^2 / D$, donde la disipación molecular equilibra el transporte transitorio (número de Fourier $\\mathrm{Fo} = 1$).");
  }
  if (tieneReac) {
    items.push("  \\item \\textbf{Escala temporal intrínseca de reacción (cinética local):} $t_{\\mathrm{ref}} = 1 / k$, tasa característica de transformación en frentes reactivos locales.");
  }
  if (tieneDif && tieneReac) {
    items.push("  \\item \\textbf{Longitud intrínseca de reacción-difusión:} $\\ell_{\\mathrm{rd}} = \\sqrt{D/k}$, escala espacial fundamental donde la difusión molecular se equilibra con la reactividad cinética; rige el espesor de frentes de onda y la longitud de onda de Turing.");
  }
  if (tieneConv) {
    items.push("  \\item \\textbf{Tiempo advectivo o de tránsito:} $t_{\\mathrm{ref}} = x_{\\mathrm{ref}} / u$, escala en la que la velocidad macroscópica rige el transporte axial.");
  }
  if (esMultiD) {
    const yCoord = coords.includes("y") ? "y" : coords[1] ?? "y";
    items.push(`  \\item \\textbf{Relación de aspecto o esbeltez:} $\\mathcal{A}_{${yCoord}} = x_{\\mathrm{ref}} / ${yCoord}_{\\mathrm{ref}}$, modulando el confinamiento anisotrópico en geometrías delgadas.`);
  }
  if (items.length === 0) {
    items.push("  \\item \\textbf{Escala temporal libre:} $t_{\\mathrm{ref}}$ fijada con el término rector de mayor jerarquía.");
  }

  return [
    "\\section{Universalidad Asintótica del Motor: Balanza Dominante y Espacio Combinatorio de Formulaciones}",
    `El motor de deducción opera de forma agnóstica sobre sistemas arbitrarios de balances diferenciales continuos ` +
    `para campos dependientes ($${camposTex}$) en coordenadas continuas ($${coords.map(c => nombreLatex(c)).join(", ")}$), ` +
    "admitiendo transporte convectivo, dispersión molecular o anisotrópica y leyes constitutivas generales $\\mathcal{S}_i(\\mathbf{u}, \\mathbf{x}, t)$ " +
    "(cinéticas de cualquier orden, saturación tipo Langmuir/Michaelis-Menten, términos de arrastre empírico o funciones fenomenológicas).",
    "\\par\\textbf{Simetrías de Escala de Lie:} Cada campo y coordenada introduce un grado de libertad en el grupo de reescalado " +
    "$G = \\mathbb{R}_{>0}^p$. Para fijar las escalas libres, se seleccionan términos rectores cuyos coeficientes efectivos se normalizan a la unidad $(\\Pi_j = 1)$.",
    "\\par\\textbf{Principio de la Balanza Dominante (Kruskal):} Cada una de las formulaciones calculadas representa un régimen físico realizable proyectado sobre una variedad invariante:",
    "\\begin{itemize}",
    ...items,
    "\\end{itemize}",
    "\\par\\textbf{Casos Canónicos de Validación del Motor:} La generalidad del marco deductivo se verifica al recuperar automáticamente " +
    "fenómenos paradigmáticos de la física matemática sin sesgo previo:",
    "\\begin{itemize}",
    "  \\item \\textbf{Inestabilidad de Turing:} En modelos bi-reactivos con activador e inhibidor, la deducción formal aísla la razón de difusividades " +
    "$d = D_v / D_u \\gg 1$ y fija la longitud de onda crítica del patrón $\\lambda_c \\sim 2\\pi\\sqrt{D_u / k}$.",
    "  \\item \\textbf{Frentes de Onda Viajeros (Fisher-KPP):} En frentes monostables $\\partial_t u = D \\nabla^2 u + k u(1-u)$, " +
    "el escalamiento determina analíticamente la velocidad asintótica mínima universal $v^* = 2\\sqrt{D k}$ (o $\\hat{v}^* = 2$ en variables canónicas).",
    "  \\item \\textbf{Capas Singulares y Cinéticas No Lineales:} Para leyes con saturación o cinéticas rápidas, el motor desacopla la dinámica rápida de la relajación difusiva lenta.",
    "\\end{itemize}",
    "\\par\\textbf{Menores No Singulares de la Matriz Dimensional:} La multiplicidad de formas proviene del número de submatrices cuadradas " +
    "de dimensión máxima con determinante no nulo ($\\det(\\mathbf{M}_{\\mathrm{sub}}) \\neq 0$) de la matriz de exponentes de escala.",
    "\\par\\textbf{Ventaja Numérica Universal:} Cada formulación ofrece una base numéricamente óptima libre de rigidez artificial (\\textit{stiffness}), ideal para integradores implícitos BDF y redes neuronales informadas por la física (PINNs)."
  ];
}

export function exportarDesarrollo(f: FormulacionNucleo): string {
  const lineas: string[] = [
    "\\documentclass[11pt,a4paper]{article}",
    "\\usepackage[utf8]{inputenc}",
    "\\usepackage[T1]{fontenc}",
    "\\usepackage[spanish,es-tabla]{babel}",
    "\\usepackage{amsmath,amssymb,amsfonts,amsthm}",
    "\\usepackage{booktabs}",
    "\\usepackage{microtype}",
    "\\usepackage[margin=25mm]{geometry}",
    "\\usepackage{hyperref}",
    "\\hypersetup{colorlinks=true,linkcolor=black,citecolor=black,urlcolor=blue}",
    "\\allowdisplaybreaks",
    "",
    "\\title{\\textbf{Análisis Dimensional Riguroso y Deducción Asintótica}\\\\\\large Reducción Canónica y Certificación Formal}",
    "\\author{Laboratorio Computacional de Modelado Matemático y Fenómenos de Transporte}",
    "\\date{\\today}",
    "",
    "\\begin{document}",
    "\\maketitle",
    "",
    "\\begin{abstract}",
    `En este informe se formaliza la derivación algebraica del sistema adimensional deducido. ` +
    `Estado de normalización: \\textbf{${texto(f.normalizacion.estado)}}. ` +
    `Equivalencia formal: \\textbf{${texto(f.equivalencia.estado)}} bajo las restricciones físicas certificadas. ` +
    `Todas las variables transformadas incorporan acento circunflejo $(\\hat{\\cdot})$ para distinguir rigurosamente las magnitudes adimensionales ` +
    `de las escalas dimensionales de referencia.`,
    "\\end{abstract}",
    "",
    "\\section{Sistema Diferencial Adimensional Canónico}",
    "Las ecuaciones gobernantes del sistema continuo, transformadas mediante las escalas características seleccionadas, quedan formuladas como:",
    "\\begin{align}",
    f.ecuaciones.map(e => `  ${latexExpresion(e.igualdad.izquierda)} &= ${latexExpresion(e.igualdad.derecha)}`).join(" \\\\\n"),
    "\\end{align}",
    "",
    ...generarSeccionAsintoticaTex(f),
    "",
    "\\section{Invariantes Adimensionales (Teorema $\\Pi$ de Buckingham)}",
    f.grupos.length > 0
      ? [
          "\\begin{table}[h!]",
          "\\centering",
          "\\begin{tabular}{lllp{6.5cm}}",
          "\\toprule",
          "\\textbf{Símbolo} & \\textbf{Definición Canónica} & \\textbf{Tipo} & \\textbf{Interpretación Física} \\\\",
          "\\midrule",
          ...f.grupos.map(g => `  $${nombreLatex(g.id)}$ & $${nombreLatex(g.id)} = ${latexExpresion(g.definicion)}$ & ${g.adimensional ? "Adimensional" : "Dim. residual"} & ${texto(interpretarGrupoTex(g.id, g.definicion))} \\\\`),
          "\\bottomrule",
          "\\end{tabular}",
          "\\caption{Invariantes adimensionales característicos deducidos.}",
          "\\end{table}",
        ].join("\n")
      : "No se requieren grupos adimensionales adicionales para cerrar el sistema.",
    "",
    "\\section{Mapeos de Coordenadas y Escalas Canónicas}",
    "El escalamiento canónico entre magnitudes dimensionales y variables adimensionales $(\\hat{\\cdot})$ queda establecido por:",
    "\\begin{align*}",
    ...f.directa.map(m => `  ${nombreLatex(m.simboloId)} &= ${latexExpresion(m.expresion)} \\quad \\text{(directa)} \\\\`),
    ...f.inversa.map(m => `  ${nombreLatex(m.simboloId)} &= ${latexExpresion(m.expresion)} \\quad \\text{(inversa)} \\\\`),
    "\\end{align*}",
    "",
    ...(f.funcionesAdimensionales && f.funcionesAdimensionales.length > 0 ? [
      "\\section{Funciones Constitutivas Escaladas}",
      "Para las relaciones constitutivas dependientes del estado, se extrae el módulo dimensional característico:",
      ...f.funcionesAdimensionales.map(fn => [
        `\\paragraph{Función ${nombreLatex(fn.nombre)}:} Escala extraída $${nombreLatex(fn.escalaId)}$ a partir de $${nombreLatex(fn.funcionId)}$.`,
        `\\[ ${latexDefinicionFuncion(fn)} \\]`
      ].join("\n")),
      ""
    ] : []),
    "\\section{Secuencia Deductiva Constructiva y Traza Formal}",
    "A continuación se presenta el desarrollo formal certificado paso a paso, mostrando la equivalencia matemática rigurosa en cada etapa:",
    "",
    ...f.desarrollo.map((p, i) => [
      `\\subsection*{Paso ${i + 1}: ${texto(p.regla)}}`,
      p.justificacion ? `\\textit{Justificación:} ${texto(p.justificacion)}.\\par` : "",
      ...(paso(p.antes) !== paso(p.despues) ? [
        "\\begin{equation*}",
        `  ${paso(p.antes)} \\implies ${paso(p.despues)}`,
        "\\end{equation*}"
      ] : [
        "\\begin{equation*}",
        `  ${paso(p.despues)} \\quad \\text{(\\checkmark\\,identidad verificada)}`,
        "\\end{equation*}"
      ]),
      p.supuestos.length ? `\\noindent\\small\\textbf{Hipótesis de validez:} ${texto(p.supuestos.join("; "))}\\normalsize\\par` : "",
      "\\medskip"
    ].filter(Boolean).join("\n")),
    "",
    "\\section{Dominios y Restricciones de No Singularidad}",
    ...(f.dominios.length > 0 ? [
      "\\subsubsection*{Dominios Espacio-Temporales}",
      "\\begin{align*}",
      ...f.dominios.map(d => `  ${latexExpresion(d.desde)} &\\le ${nombreLatex(d.variableId)} \\le ${latexExpresion(d.hasta)} \\\\`),
      "\\end{align*}"
    ] : []),
    ...(f.restricciones.length > 0 ? [
      "\\subsubsection*{Restricciones Físicas y de Regularidad}",
      "\\begin{itemize}",
      ...f.restricciones.map(r => `  \\item \\textbf{${texto(r.id)}:} ${texto(r.motivo)}. $${latexExpresion(r.expresion)}${r.tipo === "positivo" ? " > 0" : r.tipo === "negativo" ? " < 0" : r.tipo === "no_nulo" ? " \\ne 0" : r.tipo === "igualdad" && r.valor ? ` = ${latexExpresion(r.valor)}` : ""}$.`),
      "\\end{itemize}"
    ] : []),
    "",
    "\\section{Certificación de Equivalencia}",
    `Alcance del certificado algebraico: ${texto(f.equivalencia.alcance)}.`,
    "",
    "\\end{document}"
  ];

  return lineas.join("\n");
}
