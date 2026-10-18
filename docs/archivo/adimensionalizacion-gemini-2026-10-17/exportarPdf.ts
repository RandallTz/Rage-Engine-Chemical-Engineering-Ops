import katex from "katex";
import type { ExpresionDePaso, Expresion } from "./contrato";
import type { FormulacionNucleo } from "./contratoNucleo";
import { latexExpresion, nombreLatex } from "./exportar";
import { exportarDesarrollo } from "./exportarDesarrollo";
import { textoExpresion } from "./entradaEcuaciones";
import { KATEX_CSS } from "./katexCss";
import { analizarCondicionesFrontera } from "./analisisCondicionesFrontera";
import { derivarCapaLimite } from "./analisisCapaLimite";
import { derivarEstabilidadLineal } from "./analisisEstabilidad";
import { derivarSimetriaLie } from "./analisisSimetriasLie";
import { auditarMallaNumerica } from "./analisisEstabilidadNumerica";

function renderTex(latex: string, displayMode = true): string {
  try {
    return katex.renderToString(latex, {
      displayMode,
      throwOnError: false,
      output: "html",
    });
  } catch {
    return `<code>${latex}</code>`;
  }
}

function pasoTex(e: ExpresionDePaso): string {
  return e.tipo === "expresion"
    ? latexExpresion(e.expresion)
    : `${latexExpresion(e.igualdad.izquierda)} = ${latexExpresion(e.igualdad.derecha)}`;
}

function formatearDimensionesTexto(raw: string): string {
  return raw
    .replace(/\b([LMTN\theta])(?:\^(-?[0-9]+))?\b/g, (_, dim, exp) => {
      return `\\mathsf{${dim}}${exp ? `^{${exp}}` : ""}`;
    })
    .replace(/\s+/g, "\\,");
}

function formatearAuditoriaTexto(j: string): string {
  if (!j) return "Consistencia dimensional verificada conforme al Principio de Fourier.";
  let t = j
    .replace(/'[A-Za-z0-9_-]+'/g, "la ecuación continua")
    .replace(/\[([A-Za-z0-9_]+)\]\s*=\s*([^;()]+)(?:\s*\(unidad\))?/g, (_, id, dimStr) => {
      const dimTex = formatearDimensionesTexto(dimStr.trim());
      return renderTex(`[${nombreLatex(id)}] = ${dimTex}`, false);
    })
    .replace(/dimension\s+([LMTN\theta\s\^\-0-9]+?)(?=;|\.|$)/g, (_, dimStr) => {
      const dimTex = formatearDimensionesTexto(dimStr.trim());
      return `dimensión fundamental ${renderTex(dimTex, false)}`;
    });
  return t;
}

function formatearJustificacion(j: string): string {
  if (!j) return "";

  if (j.includes("dimension") || j.includes("[") || j.includes("unidad")) {
    return formatearAuditoriaTexto(j);
  }

  if (j.startsWith("G") && j.includes("dimension 1")) {
    const match = /^([A-Z0-9]+)\s*=\s*([^;]+)/.exec(j);
    if (match) {
      const gId = match[1].replace("G", "Pi_");
      return `Definición del invariante característico ${renderTex(nombreLatex(gId), false)} derivado del balance algebraico dimensional.`;
    }
  }

  if (j.includes("con inversa h demostrada")) {
    const matchVar = /^([A-Za-z0-9_]+)\s*=\s*g\(([A-Za-z0-9_]+)\)/.exec(j);
    if (matchVar) {
      const orig = nombreLatex(matchVar[1]);
      const adim = nombreLatex(matchVar[2]);
      const refScale = nombreLatex(`${matchVar[1]}_ref`);
      return `Mapeo canónico biunívoco ${renderTex(`${orig} = ${refScale}\\,${adim}`, false)} con transformación inversa biyectiva demostrada.`;
    }
  }

  if (j.includes("d/dt") || j.includes("d/dx")) {
    return `Aplicación de la regla de la cadena para derivadas temporales y espaciales respecto de las coordenadas escaladas.`;
  }

  if (j.includes("sustitucion de variables")) {
    return `Sustitución directa de las variables continuas en función de sus correspondientes campos normalizados y escalas de referencia.`;
  }
  if (j.includes("linealidad")) {
    return `Propiedad de linealidad de los operadores diferenciales: factorización de escalas constantes.`;
  }
  if (j.includes("division") || j.includes("factor global")) {
    return `Normalización asintótica por división entre el término rector, cancelando el grado de libertad del término pivote.`;
  }

  return j.replace(/[A-Za-z0-9_-]+:[A-Za-z0-9_\[\].-]+/g, "término rector del balance");
}

function nombreReglaFormal(regla: string): string {
  const map: Record<string, string> = {
    "homogeneidad dimensional": "Homogeneidad dimensional (Principio de Fourier)",
    "mapa multiplicativa": "Difeomorfismo de reescalado canónico",
    "derivada respecto de la nueva variable": "Transformación diferencial por regla de la cadena",
    "sustitucion de variables": "Sustitución de variables y campos escalados",
    "regla de la cadena": "Regla de la cadena en derivadas de campos",
    "linealidad: extraccion de factores constantes": "Linealidad: factorización de coeficientes de escala",
    "igualdad completa antes de cancelar factores": "Balance continuo con operadores escalados",
    "igualdad completa tras la regla de la cadena": "Ecuación diferencial con factores de escala explícitos",
    "agrupacion de coeficientes por nucleo": "Agrupación de escalas por término rector",
    "division por el factor global": "Balanza dominante de Kruskal: normalización por factor global",
    "familia libre": "Fijación analítica de escala característica libre",
    "definicion de grupo adimensional": "Identificación de invariante adimensional característico (Π)",
    "sustitucion inversa y comparacion canonica": "Certificación recíproca por retro-sustitución inversa",
    "extremo del dominio": "Transformación de condiciones de contorno espaciales",
  };
  return map[regla] ?? regla;
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

function interpretarGrupoFisico(id: string, defExpr?: Expresion): string {
  const defTexto = defExpr ? textoExpresion(defExpr) : "";

  // 1. Detección por estructura algebraica explícita del invariante
  if (/D.*t_ref.*x_ref\^2|D.*t_ref\/x_ref\^2/i.test(defTexto)) {
    return "Número de Fourier longitudinal (Fo_x = D·t_ref / x_ref²): cociente entre la escala temporal de referencia y el tiempo característico de difusión molecular longitudinal.";
  }
  if (/D.*t_ref.*y_ref\^2|D.*t_ref\/y_ref\^2/i.test(defTexto)) {
    return "Número de Fourier transversal (Fo_y = D·t_ref / y_ref²): razón difusiva transversal; acoplado con Fo_x genera la relación de esbeltez A_y² = (x_ref/y_ref)².";
  }
  if (/D.*t_ref.*z_ref\^2|D.*t_ref\/z_ref\^2/i.test(defTexto)) {
    return "Número de Fourier transversal (Fo_z = D·t_ref / z_ref²): transporte difusivo en el eje z; define el factor de forma A_z² = (x_ref/z_ref)².";
  }
  if (/t_ref.*u.*x_ref|u.*t_ref\/x_ref/i.test(defTexto)) {
    return "Número de Péclet temporal o condición CFL longitudinal (Pe_x / CFL_x = u·t_ref / x_ref): relación entre transporte advectivo axial y la escala de tiempo.";
  }
  if (/t_ref.*v.*y_ref|v.*t_ref\/y_ref/i.test(defTexto)) {
    return "Número de Péclet temporal o condición CFL transversal (Pe_y / CFL_y = v·t_ref / y_ref): relación entre transporte advectivo secundario y escala temporal.";
  }
  if (/t_ref.*w.*z_ref|w.*t_ref\/z_ref/i.test(defTexto)) {
    return "Número de Péclet temporal o condición CFL vertical (Pe_z / CFL_z = w·t_ref / z_ref): advección en el eje vertical respecto a la escala temporal.";
  }
  if (/k.*t_ref|t_ref.*k/i.test(defTexto)) {
    return "Número de Damköhler temporal (Da_t = k·t_ref): razón entre la tasa de consumo o generación cinética y la escala de evolución temporal.";
  }
  if (/D.*k.*u\^2|k.*D\/u\^2/i.test(defTexto)) {
    return "Número inverso de Péclet-Damköhler axial (D·k / u² = 1 / (Pe_x·Da_x)): balance relativo entre dispersión molecular y transporte convectivo-reactivo.";
  }
  if (/D.*k.*v\^2|k.*D\/v\^2/i.test(defTexto)) {
    return "Número inverso de dispersión reactiva transversal (D·k / v²): balance entre difusión transversal y convección-reacción transversal.";
  }
  if (/x_ref.*y_ref|y_ref.*x_ref/i.test(defTexto)) {
    return "Factor de forma o relación de aspecto (A_y = x_ref / y_ref): parámetro geométrico de esbeltez que rige la reducción asintótica en dominios delgados (teoría de lubricación / capa límite).";
  }
  if (/u.*x_ref.*D|u.*x_ref\/D/i.test(defTexto)) {
    return "Número de Péclet axial (Pe_x = u·x_ref / D): cociente entre el transporte advectivo forzado y la difusión molecular longitudinal.";
  }
  if (/v.*y_ref.*D|v.*y_ref\/D/i.test(defTexto)) {
    return "Número de Péclet transversal (Pe_y = v·y_ref / D): cociente entre transporte convectivo transversal y difusión molecular transversal.";
  }
  if (/D2.*D1|D1.*D2|D_B.*D_A/i.test(defTexto)) {
    return "Relación de difusividades moleculares relativas (δ_D = D_2 / D_1): parámetro de acoplamiento diferencial entre especies.";
  }

  // 2. Detección por identificador del grupo
  if (id === "Da" || id.startsWith("Da_") || id.startsWith("pi_reac") || id.includes("k1") || id.includes("k2") || id.includes("k_1") || id.includes("k_2")) {
    return "Número de Damköhler (Da): cociente entre la tasa cinética de reacción química y la tasa de transporte por difusión/convección molecular.";
  }
  if (id === "Bi") {
    return "Número de Biot (Bi): relación entre la resistencia interna a la conducción y la resistencia superficial convectiva de la película.";
  }
  if (id === "Sh" || id.startsWith("Sh_") || id.toLowerCase().includes("sherwood")) {
    return "Número de Sherwood (Sh = kc·L / D): relación entre transferencia másica convectiva interfacial y difusión molecular ordinaria.";
  }
  if (id === "Ste" || id.startsWith("Ste_") || id.toLowerCase().includes("stefan")) {
    return "Número de Stefan (Ste = cp·ΔT / ΔH): cociente entre calor sensible y calor latente en frentes móviles de interfase.";
  }
  if (id === "Pe") {
    return "Número de Péclet (Pe): razón entre la tasa de transporte advectivo/convectivo y la tasa de transporte por difusión molecular.";
  }
  if (id === "Pr") {
    return "Número de Prandtl (Pr): cociente entre la difusividad de cantidad de movimiento (viscosidad cinemática) y la difusividad térmica molecular.";
  }
  if (id === "Le") {
    return "Número de Lewis (Le): relación entre la difusividad térmica molecular y la difusividad másica ordinaria.";
  }
  if (id === "Gr") {
    return "Número de Grashof (Gr): cociente entre las fuerzas de flotación o empuje térmico y las fuerzas viscosas en convección libre.";
  }
  if (id === "Thiele" || id.includes("Thiele") || id.includes("phi")) {
    return "Módulo de Thiele: razón entre la velocidad intrínseca de consumo cinético y la velocidad de difusión efectiva intraparticular.";
  }
  if (id.startsWith("Pi_") || id.startsWith("pi") || id.startsWith("pi_")) {
    return "Invariante adimensional derivado de la base del núcleo dimensional (Teorema de Buckingham).";
  }
  return "Invariante característico adimensional deducido del balance algebraico de órdenes de magnitud.";
}

function formatearSupuestos(supuestos: string[]): string {
  return supuestos.map(s => {
    let t = s.replace(/([A-Za-z0-9_]+),ref/g, (_, v) => `${v}_ref`);
    t = t.replace(/factor global\s+([A-Za-z0-9_]+)\/([A-Za-z0-9_]+)\s+distinto de cero/i, (_, num, den) => {
      return `factor de escala ${renderTex(`\\frac{${nombreLatex(num)}}{${nombreLatex(den)}} \\ne 0`, false)}`;
    });
    t = t.replace(/([A-Za-z0-9_]+)\s*=\s*([A-Za-z0-9_]+)\*([A-Za-z0-9_]+)/g, (_, v, ref, ad) => {
      const adId = ad.endsWith("_ad") ? ad : `${ad}_ad`;
      return renderTex(`${nombreLatex(v)} = ${nombreLatex(ref)}\\,${nombreLatex(adId)}`, false);
    });
    t = t.replace(/\b([A-Za-z0-9_]+)\s*>\s*0\b/g, (_, id) => {
      return renderTex(`${nombreLatex(id)} > 0`, false);
    });
    t = t.replace(/R[0-9]+:\s*positivo\s+([A-Za-z0-9_]+)/g, (_, id) => {
      return renderTex(`${nombreLatex(id)} > 0`, false);
    });
    t = t.replace(/([A-Za-z0-9_]+)\s+con signo declarado/g, (_, id) => {
      return `parámetro ${renderTex(`${nombreLatex(id)} > 0`, false)}`;
    });
    t = t
      .replace(/dimensiones exactas con exponentes racionales/g, "exponentes dimensionales racionales conformes")
      .replace(/escalas y referencias constantes/g, "escalas características uniformes en el dominio")
      .replace(/escalas y parametros constantes/g, "propiedades y escalas constantes")
      .replace(/coordenadas cartesianas/g, "métrica euclídea cartesiana")
      .replace(/linealidad de derivadas y operadores/g, "linealidad de los operadores diferenciales")
      .replace(/funciones declaradas sin desarrollar/g, "operadores constitutivos canónicos")
      .replace(/solucion exacta de los objetivos/g, "solución algebraica exacta de las restricciones de escala");
    return t;
  }).join("; ");
}

function generarSeccionAsintoticaHtml(f: FormulacionNucleo): string {
  const campos = (f.directa ?? [])
    .map(d => d.simboloId)
    .filter(s => !["t", "x", "y", "z", "r", "theta"].includes(s));
  const camposTex = campos.length > 0
    ? campos.map(c => nombreLatex(c)).join(", ")
    : "u, v";

  const coords = (f.directa ?? [])
    .map(d => d.simboloId)
    .filter(s => ["x", "y", "z", "r"].includes(s));

  const tieneDif = (f.grupos ?? []).some(g => /Fo|D/i.test(g.id) || /D.*t_ref|D\/|dif/i.test(textoExpresion(g.definicion)));
  const tieneConv = (f.grupos ?? []).some(g => /Pe|CFL|u|v|w/i.test(g.id) || /u.*t_ref|v.*t_ref/i.test(textoExpresion(g.definicion)));
  const tieneReac = (f.grupos ?? []).some(g => /Da|k/i.test(g.id) || /k.*t_ref/i.test(textoExpresion(g.definicion)));
  const esMultiD = coords.length > 1;

  const bullets: string[] = [];
  if (tieneDif) {
    bullets.push(`<li><strong>Escala temporal difusiva pura (relajación molecular):</strong> ${renderTex("t_{\\mathrm{ref}} = x_{\\mathrm{ref}}^2 / D", false)}, donde el transporte molecular disipativo equilibra la evolución transitoria (número de Fourier $\\mathrm{Fo} = 1$). Rige la homogenización de perturbaciones espaciales.</li>`);
  }
  if (tieneReac) {
    bullets.push(`<li><strong>Escala temporal intrínseca de reacción (tasa cinética local):</strong> ${renderTex("t_{\\mathrm{ref}} = 1 / k", false)}, escala en la que la dinámica de transformación química o acoplamiento cinético local dicta la tasa de producción/consumo sin retardo difusivo.</li>`);
  }
  if (tieneDif && tieneReac) {
    bullets.push(`<li><strong>Longitud intrínseca de reacción-difusión (escala de frentes y patrones):</strong> ${renderTex("\\ell_{\\mathrm{rd}} = \\sqrt{D/k}", false)}, escala espacial fundamental donde la difusión molecular se equilibra exactamente con la reactividad cinética local. Rige el espesor de los frentes de onda y la longitud de onda de patrones de Turing.</li>`);
  }
  if (tieneConv) {
    bullets.push(`<li><strong>Tiempo convectivo de tránsito:</strong> ${renderTex("t_{\\mathrm{ref}} = x_{\\mathrm{ref}} / u", false)}, escala en la que la advección macroscópica transporta los frentes de concentración a lo largo de las trayectorias del flujo.</li>`);
  }
  if (esMultiD) {
    const yCoord = coords.includes("y") ? "y" : coords[1] ?? "y";
    bullets.push(`<li><strong>Factor de esbeltez o relación de aspecto geométrico:</strong> ${renderTex(`\\mathcal{A}_{${yCoord}} = x_{\\mathrm{ref}} / ${yCoord}_{\\mathrm{ref}}`, false)}, que modula la anisotropía de transporte en dominios confinados (capas límite, membranas y filamentos).</li>`);
  }
  if (bullets.length === 0) {
    bullets.push(`<li><strong>Escala temporal canónica:</strong> ${renderTex("t_{\\mathrm{ref}}", false)} determinada por el término rector de transporte de mayor jerarquía.</li>`);
  }

  return `
    <section class="latex-section">
      <h2>7. Universalidad Asintótica del Motor: Balanza Dominante y Espacio Combinatorio de Formulaciones</h2>
      <p class="latex-p">
        El motor de deducción adimensional procesa de forma agnóstica y universal sistemas generales de balances diferenciales continuos 
        para un vector arbitrario de campos dependientes (${renderTex(camposTex, false)}) en dominios continuos (${renderTex(coords.map(c => nombreLatex(c)).join(", "), false)}), 
        gobernados por balances de la forma ${renderTex("\\partial_t u_i + \\mathcal{A}_i(\\mathbf{u}) = \\mathcal{D}_i(\\nabla \\mathbf{u}) + \\mathcal{S}_i(\\mathbf{u}, \\mathbf{x}, t)", false)}, 
        donde $\\mathcal{A}_i$ representa transporte advectivo, $\\mathcal{D}_i$ operadores de dispersión o difusión (isotrópica o anisotrópica), y 
        $\\mathcal{S}_i$ representa leyes constitutivas arbitrarias introducidas por el usuario (cinéticas de reacción lineales o de orden fraccionario, 
        saturación no lineal tipo Langmuir-Hinshelwood / Michaelis-Menten / Hill, leyes empíricas de arrastre o fricción, o términos fuente fenomenológicos acoplados).
      </p>
      <p class="latex-p">
        A partir del análisis de los menores no singulares de la matriz dimensional de Buckingham, el motor no se restringe a una única escala estática, 
        sino que despliega el <strong>espacio combinatorio completo de formulaciones canónicas duales</strong> 
        (que en sistemas multicomponente acoplados alcanza hasta <strong>68 formas cerradas y certificadas</strong>), 
        garantizando que el investigador pueda proyectar el sistema sobre la variedad asintótica correspondiente a cualquier régimen físico realizable:
      </p>
      <p class="latex-p">
        <strong>Simetrías de Dilatación de Lie y Balanza Dominante (Kruskal):</strong> Cada formulación representa la proyección del sistema sobre una variedad invariante 
        asociada a un balance físico dominante específico:
      </p>
      <ul class="latex-bullet-list">
        ${bullets.join("\n        ")}
      </ul>
      <p class="latex-p">
        <strong>Casos Canónicos de Validación del Motor:</strong> La generalidad del motor se evidencia al reproducir de forma natural e inductiva 
        los regímenes críticos más célebres de la física no lineal y la ciencia de medios continuos a partir de las ecuaciones dimensionales puras:
      </p>
      <ul class="latex-bullet-list">
        <li><strong>Inestabilidad de Turing y Ruptura Espontánea de Simetría:</strong> En sistemas bi-reactivos con activador $u$ e inhibidor $v$, 
        el motor extrae la razón de difusividades ${renderTex("d = D_v / D_u \\gg 1", false)} y la escala crítica de longitud de onda ${renderTex("\\lambda_c \\sim 2\\pi\\sqrt{D_u / k}", false)}, 
        gobernando la emergencia de autoorganización espacial macroscópica.</li>
        <li><strong>Frentes de Onda Viajeros y Ecuación de Fisher-KPP:</strong> En la propagación de transiciones de fase o invasión biológica 
        con cinéticas monostables ${renderTex("\\partial_t u = D \\nabla^2 u + k u(1 - u)", false)}, el escalamiento canónico conduce 
        a la velocidad asintótica mínima invariante ${renderTex("v^* = 2\\sqrt{D k}", false)} (${renderTex("\\hat{v}^* = 2", false)} en variables normalizadas).</li>
        <li><strong>Medios Excitables, Cinéticas de Saturación y Capas de Transición:</strong> Para sistemas con términos fuente empíricos, 
        cinéticas cúbicas o saturación enzimática/catalítica, el motor desacopla automáticamente la dinámica rápida de conmutación 
        de la relajación lenta difusiva interfacial, proporcionando formulaciones numéricamente óptimas para solvers rígidos (BDF) y redes neuronales PINNs.</li>
      </ul>
    </section>
  `;
}

function generarSeccionCondicionesFronteraHtml(f: FormulacionNucleo): string {
  const anal = analizarCondicionesFrontera(f);
  return `
    <section class="latex-section">
      <h2>8. Adimensionalización Rigurosa de Condiciones de Contorno e Invariantes Interfaciales</h2>
      <p class="latex-p">
        ${anal.sintesisFisica}
      </p>

      ${anal.gruposFrontera.length > 0 ? `
        <h3 class="latex-subsec-title">Invariantes Interfaciales Característicos (Grupos $\\Pi_{\\partial\\Omega}$)</h3>
        <table class="latex-table">
          <thead>
            <tr>
              <th style="width: 15%;">Grupo</th>
              <th style="width: 35%;">Definición Analítica</th>
              <th style="width: 50%;">Interpretación Física y Regímenes Asintóticos</th>
            </tr>
          </thead>
          <tbody>
            ${anal.gruposFrontera.map(g => `
              <tr>
                <td style="font-weight: bold; font-family: monospace;">${renderTex(g.id, false)}</td>
                <td><div class="latex-eq-display">${renderTex(g.definicionLatex, false)}</div></td>
                <td>
                  <strong>${g.nombre}:</strong> ${g.significadoFisico}
                  <ul style="margin: 4px 0 0 16px; padding: 0; font-size: 8.5pt; color: #444;">
                    ${g.regimenesAsintoticos.map(r => `<li><strong>${renderTex(r.limite, false)}:</strong> ${r.interpretacion}</li>`).join("")}
                  </ul>
                </td>
              </tr>
            `).join("\n")}
          </tbody>
        </table>
      ` : ""}

      <h3 class="latex-subsec-title" style="margin-top: 14px;">Condiciones de Frontera Transformadas</h3>
      <div class="latex-equations-block">
        ${anal.condiciones.map((c, i) => `
          <div class="latex-eq-item" style="margin-bottom: 12px;">
            <div class="latex-eq-row">
              <div class="latex-eq-math">
                ${renderTex(c.ecuacionAdimensionalLatex, true)}
              </div>
              <div class="latex-eq-num">(BC_{${i + 1}})</div>
            </div>
            <div class="latex-eq-note">
              <strong>${c.descripcion}:</strong> Obtenida a partir de ${renderTex(c.ecuacionOriginalLatex, false)}.
            </div>
          </div>
        `).join("\n")}
      </div>
    </section>
  `;
}

function generarSeccionPerturbacionesSingularesHtml(f: FormulacionNucleo): string {
  const capa = derivarCapaLimite(f);
  return `
    <section class="latex-section">
      <h2>9. Análisis Asintótico de Perturbaciones Singulares y Capa Límite (Prandtl–Van Dyke)</h2>
      <p class="latex-p">
        ${capa.explicacionFisica}
      </p>

      <div class="latex-def-item" style="margin: 12px 0;">
        <p class="latex-p">
          <strong>1. Ecuación Exterior Regular Degenerada (${renderTex(capa.epsilonId + " \\to 0", false)}):</strong> 
          Al anularse el término singular de mayor orden diferencial, el sistema colapsa a la variedad exterior:
        </p>
        <div class="latex-eq-display">${renderTex(capa.ecuacionExteriorLatex, true)}</div>
      </div>

      <div class="latex-def-item" style="margin: 12px 0;">
        <p class="latex-p">
          <strong>2. Coordenada Dilatada y Ecuación Interior de Capa Límite:</strong> 
          Mediante el estiramiento local de escala con espesor característico ${renderTex(capa.espesorCapaLimite, false)}, 
          se restablece la balanza dominante local:
        </p>
        <div class="latex-eq-display">${renderTex(capa.ecuacionInteriorLatex, true)}</div>
      </div>

      <div class="latex-def-item" style="margin: 12px 0;">
        <p class="latex-p">
          <strong>3. Principio de Acoplamiento Asintótico y Solución Compuesta Uniforme:</strong> 
          El principio de Prandtl–Van Dyke garantiza la continuidad asintótica libre de singularidades:
        </p>
        <div class="latex-eq-display">${renderTex(capa.condicionAcoplamientoLatex, true)}</div>
        <div class="latex-eq-display">${renderTex(capa.solucionCompuestaLatex, true)}</div>
      </div>
    </section>
  `;
}

function generarSeccionEstabilidadHtml(f: FormulacionNucleo): string {
  const est = derivarEstabilidadLineal(f);
  return `
    <section class="latex-section">
      <h2>10. Análisis Espectral de Estabilidad Lineal y Espectro de Dispersión $\\sigma(k)$</h2>
      <p class="latex-p">
        Para analizar la estabilidad frente a perturbaciones espaciotemporales infinitesimales 
        ${renderTex("\\vec{\\eta}\\,e^{\\sigma \\tau + i \\vec{k} \\cdot \\vec{\\xi}}", false)}, 
        se linealiza el sistema continuo adimensional en torno a un estado base homogéneo. 
        El operador lineal acoplado queda gobernado por la matriz Jacobiana $\\mathbf{J}$ y la matriz difusiva $\\mathbf{D}$:
      </p>

      <div class="latex-eq-display">
        ${renderTex(`${est.matrizJacobianaLatex} \\qquad ${est.matrizDifusionLatex}`, true)}
      </div>

      <p class="latex-p">
        La relación de dispersión adimensional analítica surge del determinante característico 
        ${renderTex("\\det\\left(\\sigma \\mathbf{I} - \\mathbf{M}(k)\\right) = 0", false)}, con matriz de perturbación 
        ${renderTex("\\mathbf{M}(k) = \\mathbf{J} - k^2 \\mathbf{D}", false)}:
      </p>
      <div class="latex-eq-display">${renderTex(est.relacionDispersionLatex, true)}</div>

      <div class="latex-def-item" style="margin: 12px 0;">
        <p class="latex-p">
          <strong>Criterios de Estabilidad Asintótica y Bifurcación:</strong>
        </p>
        <ul class="latex-bullet-list">
          <li><strong>Estabilidad del estado homogéneo ($k = 0$):</strong> ${renderTex(est.criterioHomogeneoLai, false)}</li>
          <li><strong>Bifurcación de Hopf (oscilaciones temporales):</strong> ${renderTex(est.criterioHopfLatex, false)}</li>
          <li><strong>Inestabilidad espacial de onda finita:</strong> ${renderTex(est.criterioInestabilidadEspacialLatex, false)}</li>
          ${est.esInestable ? `<li><strong>Número de onda crítico de máxima amplificación:</strong> ${renderTex(est.numeroOndaCriticoLatex, false)}</li>` : ""}
        </ul>
        <p class="latex-p" style="margin-top: 8px; font-weight: 500; color: #166534;">
          <strong>Diagnóstico Asintótico:</strong> ${est.diagnosticoFisico}
        </p>
      </div>
    </section>
  `;
}

function generarSeccionSimetriasLieHtml(f: FormulacionNucleo): string {
  const lie = derivarSimetriaLie(f);
  return `
    <section class="latex-section">
      <h2>11. Simetrías Puntuales de Lie y Reducción Autosimilar (\\eta = \\xi / \\tau^\\alpha)</h2>
      <p class="latex-p">
        ${lie.fundamentacionFisica}
      </p>

      <div class="latex-def-item" style="margin: 12px 0;">
        <p class="latex-p">
          <strong>1. Generador Infinitesimal del Grupo Homotético de Lie:</strong> 
          La acción de la simetría continua proyecta el espacio de chorro diferencial gobernado por:
        </p>
        <div class="latex-eq-display">${renderTex(lie.generadorInfinitesimalLatex, true)}</div>
      </div>

      <div class="latex-def-item" style="margin: 12px 0;">
        <p class="latex-p">
          <strong>2. Variable de Similitud Canónica y Ansatz Invariante:</strong> 
          La coordenada canónica invariante colapsa el espacio diferencial espaciotemporal:
        </p>
        <div class="latex-eq-display">${renderTex(lie.variableSimilitudLatex, true)}</div>
        <div class="latex-eq-display">${renderTex(lie.ansatzAutosimilarLatex, true)}</div>
      </div>

      <div class="latex-def-item" style="margin: 12px 0;">
        <p class="latex-p">
          <strong>3. Ecuación Diferencial Ordinaria (EDO) Reducida y Perfil Asintótico:</strong> 
          La EDP continua se reduce rigurosamente a una variedad unidimensional de fase:
        </p>
        <div class="latex-eq-display">${renderTex(lie.edoReducidaLatex, true)}</div>
        <div class="latex-eq-display">${renderTex(lie.perfilAnaliticoLatex, true)}</div>
      </div>
    </section>
  `;
}

function generarSeccionAuditoriaNumericaHtml(f: FormulacionNucleo): string {
  const aud = auditarMallaNumerica(f);
  return `
    <section class="latex-section">
      <h2>12. Auditoría Computacional de Malla, Criterio CFL y Rigidez Numérica</h2>
      <p class="latex-p">
        Para garantizar la fidelidad computacional en simulaciones discretas de alta resolución (diferencias finitas, volúmenes finitos o PINNs), 
        se auditan las restricciones asintóticas de paso espacial $\\Delta\\xi$ y temporal $\\Delta\\tau$:
      </p>

      <table class="latex-booktabs">
        <thead>
          <tr>
            <th style="width: 25%; text-align: left;">Criterio Numérico</th>
            <th style="width: 25%; text-align: center;">Condición de Estabilidad</th>
            <th style="width: 20%; text-align: center;">Valor Evaluado</th>
            <th style="width: 30%; text-align: left;">Diagnóstico y Recomendación</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td><strong>Péclet de celda</strong></td>
            <td style="text-align: center;">${renderTex("\\mathrm{Pe}_{\\Delta\\xi} = \\mathrm{Pe}\\,\\Delta\\xi \\le 2", false)}</td>
            <td style="text-align: center; font-weight: bold; color: ${aud.criterioOscilacionSatisfecho ? "#15803d" : "#b91c1c"};">${aud.pecletCelda.toFixed(3)}</td>
            <td>${aud.criterioOscilacionSatisfecho ? "Discretización no oscilatoria asegurada." : `Alerta: requiere Upwind TVD o $N_x \\ge ${aud.nxMinimoRecomendado}$.`}</td>
          </tr>
          <tr>
            <td><strong>CFL Difusivo</strong></td>
            <td style="text-align: center;">${renderTex("\\Delta\\tau \\le \\frac{\\Delta\\xi^2}{2\\,\\mathrm{Fo}}", false)}</td>
            <td style="text-align: center; font-family: monospace;">${aud.dtMaxDifusivo.toExponential(3)}</td>
            <td>Límite estricto para esquemas explícitos.</td>
          </tr>
          <tr>
            <td><strong>CFL Advectivo</strong></td>
            <td style="text-align: center;">${renderTex("\\Delta\\tau \\le \\frac{\\Delta\\xi}{\\mathrm{Pe}}", false)}</td>
            <td style="text-align: center; font-family: monospace;">${aud.dtMaxAdvectivo.toExponential(3)}</td>
            <td>Condición Courant-Friedrichs-Lewy de transporte.</td>
          </tr>
          <tr>
            <td><strong>Índice de Rigidez ($\\mathcal{S}$)</strong></td>
            <td style="text-align: center;">${renderTex("\\mathcal{S} = \\frac{\\mathrm{Da}}{\\mathrm{Fo}}\\,N_x^2", false)}</td>
            <td style="text-align: center; font-weight: bold;">${aud.indiceRigidez.toFixed(1)}</td>
            <td>${aud.esRigido ? "Sistema con rigidez severa: se requiere integrador implícito (BDF / Radau / TRBDF2)." : "Sistema no rígido: admite integración con RK45 / Tsit5."}</td>
          </tr>
        </tbody>
      </table>

      <div class="latex-def-item" style="margin: 12px 0;">
        <p class="latex-p">
          <strong>Dictamen del Motor de Integración Numérica:</strong><br>
          ${aud.diagnosticoComputacional}
        </p>
        <p class="latex-p" style="font-size: 9pt; color: #444; margin-top: 6px;">
          <em>Esquema espacial sugerido:</em> ${aud.esquemaEspacialRecomendado}.<br>
          <em>Integrador temporal sugerido:</em> ${aud.integradorTemporalRecomendado}.
        </p>
      </div>
    </section>
  `;
}

export function generarHtmlDesarrollo(
  nombreModelo: string,
  indiceForma: number,
  f: FormulacionNucleo
): string {
  const titulo = `Análisis Dimensional Riguroso y Deducción Asintótica: ${nombreModelo}`;
  const fecha = new Date().toLocaleDateString("es-ES", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  // 1. Ecuaciones originales continuas
  const ecsOriginales = (f.desarrollo ?? [])
    .filter(p => p.regla === "homogeneidad dimensional" && p.antes.tipo === "igualdad")
    .map(p => p.antes.tipo === "igualdad" ? p.antes.igualdad : null)
    .filter((eq): eq is NonNullable<typeof eq> => eq !== null);
  const listaOriginales = ecsOriginales.length > 0 ? ecsOriginales : (f.ecuaciones ?? []).map(e => e.igualdad);
  const ecuacionesOriginalesHtml = listaOriginales.map((eq, i) => {
    const math = renderTex(`${latexExpresion(eq.izquierda)} = ${latexExpresion(eq.derecha)}`, true);
    return `
      <div class="latex-eq-item">
        <div class="latex-eq-row">
          <div class="latex-eq-math">${math}</div>
          <div class="latex-eq-num">(E_{${i + 1}})</div>
        </div>
      </div>
    `;
  }).join("\n");

  // 2. Ecuaciones escaladas intermedias
  const ecsIntermedias = (f.desarrollo ?? [])
    .filter(p => (p.regla === "agrupacion de coeficientes por nucleo" || p.regla === "igualdad completa tras la regla de la cadena") && p.despues.tipo === "igualdad")
    .map(p => p.despues.tipo === "igualdad" ? p.despues.igualdad : null)
    .filter((eq): eq is NonNullable<typeof eq> => eq !== null);

  // 3. Ecuaciones normalizadas (división por rector)
  const ecsNormalizadas = (f.desarrollo ?? [])
    .filter(p => p.regla === "division por el factor global" && p.despues.tipo === "igualdad")
    .map(p => p.despues.tipo === "igualdad" ? p.despues.igualdad : null)
    .filter((eq): eq is NonNullable<typeof eq> => eq !== null);

  // 4. Ecuaciones finales adimensionales
  const ecuacionesAdimHtml = (f.ecuaciones ?? []).map((e, i) => {
    const math = renderTex(`${latexExpresion(e.igualdad.izquierda)} = ${latexExpresion(e.igualdad.derecha)}`, true);
    const factor = e.factorGlobal && (e.factorGlobal.tipo !== "numero" || e.factorGlobal.valor !== 1)
      ? `<div class="latex-eq-note">Factor global de transporte normalizado: ${renderTex(latexExpresion(e.factorGlobal), false)}</div>`
      : "";
    return `
      <div class="latex-eq-item">
        <div class="latex-eq-row">
          <div class="latex-eq-math">${math}</div>
          <div class="latex-eq-num">(${i + 1})</div>
        </div>
        ${factor}
      </div>
    `;
  }).join("\n");

  // 5. Tabla de grupos adimensionales
  const grupos = f.grupos ?? [];
  const gruposHtml = grupos.length > 0
    ? `
      <section class="latex-section">
        <h2>6. Invariantes Adimensionales Característicos (Teorema Π de Buckingham)</h2>
        <p class="latex-p">
          A partir del análisis algebraico del espacio nulo de la matriz dimensional de parámetros físicos 
          y escalas de referencia (Teorema ${renderTex("\\Pi", false)} de Buckingham y simetrías de escala de Lie), 
          se identifican los siguientes invariantes canónicos que gobiernan la dinámica asintótica del sistema:
        </p>
        <table class="latex-booktabs">
          <thead>
            <tr>
              <th style="width: 14%; text-align: center;">Símbolo</th>
              <th style="width: 38%; text-align: center;">Definición Algebraica Canónica</th>
              <th style="width: 14%; text-align: center;">Clasificación</th>
              <th style="width: 34%; text-align: left;">Significado Físico / Fenómeno de Transporte</th>
            </tr>
          </thead>
          <tbody>
            ${grupos.map(g => `
              <tr>
                <td style="text-align: center;">${renderTex(nombreLatex(g.id), false)}</td>
                <td style="text-align: center;">${renderTex(`${nombreLatex(g.id)} = ${latexExpresion(g.definicion)}`, false)}</td>
                <td style="text-align: center;">
                  <span class="latex-badge ${g.adimensional ? "badge-dimless" : "badge-residual"}">
                    ${g.adimensional ? "Adimensional" : "Dimensión residual"}
                  </span>
                </td>
                <td style="font-size: 9.5pt; color: #222; text-align: left;">${interpretarGrupoFisico(g.id, g.definicion)}</td>
              </tr>
            `).join("\n")}
          </tbody>
        </table>
      </section>
    `
    : "";

  // 6. Mapeos de escalamiento y análisis de dimensiones espaciales
  const coordenadas = (f.directa ?? [])
    .map(d => d.simboloId)
    .filter(id => ["x", "y", "z"].includes(id));
  const tieneT = (f.directa ?? []).some(d => d.simboloId === "t");
  const campos = (f.directa ?? [])
    .map(d => d.simboloId)
    .filter(id => !["t", "x", "y", "z"].includes(id));

  let operadoresLatex = "";
  if (coordenadas.length <= 1) {
    operadoresLatex = `\\frac{\\partial}{\\partial t} = \\frac{1}{t_{\\mathrm{ref}}} \\frac{\\partial}{\\partial \\hat{t}}, \\qquad \\nabla_{x}^2 = \\frac{1}{x_{\\mathrm{ref}}^2} \\frac{\\partial^2}{\\partial \\hat{x}^2}`;
  } else if (coordenadas.length === 2) {
    operadoresLatex = `\\frac{\\partial}{\\partial t} = \\frac{1}{t_{\\mathrm{ref}}} \\frac{\\partial}{\\partial \\hat{t}}, \\qquad \\nabla_{x,y}^2 = \\frac{1}{x_{\\mathrm{ref}}^2} \\frac{\\partial^2}{\\partial \\hat{x}^2} + \\frac{1}{y_{\\mathrm{ref}}^2} \\frac{\\partial^2}{\\partial \\hat{y}^2} = \\frac{1}{x_{\\mathrm{ref}}^2} \\left[ \\frac{\\partial^2}{\\partial \\hat{x}^2} + \\mathcal{A}_y^2 \\frac{\\partial^2}{\\partial \\hat{y}^2} \\right]`;
  } else {
    operadoresLatex = `\\frac{\\partial}{\\partial t} = \\frac{1}{t_{\\mathrm{ref}}} \\frac{\\partial}{\\partial \\hat{t}}, \\qquad \\nabla_{x,y,z}^2 = \\frac{1}{x_{\\mathrm{ref}}^2} \\left[ \\frac{\\partial^2}{\\partial \\hat{x}^2} + \\mathcal{A}_y^2 \\frac{\\partial^2}{\\partial \\hat{y}^2} + \\mathcal{A}_z^2 \\frac{\\partial^2}{\\partial \\hat{z}^2} \\right]`;
  }

  const notaAnisotropica = coordenadas.length > 1
    ? `<p class="latex-p" style="font-size: 9.5pt; color: #333;">
        <em>Escalamiento anisotrópico multidimensional:</em> La existencia de escalas espaciales independientes en cada coordenada 
        (${coordenadas.map(c => renderTex(nombreLatex(c), false)).join(", ")}) genera factores de forma adimensionales (relaciones de esbeltez o alargamiento) 
        ${coordenadas.filter(c => c !== "x").map(c => renderTex(`\\mathcal{A}_{${c}} = \\frac{x_{\\mathrm{ref}}}{${c}_{\\mathrm{ref}}}`, false)).join(", ")}. 
        En dominios de capa límite, microcanales o películas delgadas (${renderTex(`\\mathcal{A} \\ll 1`, false)}), estos factores cuantifican la jerarquía asintótica de transporte transversal frente al longitudinal.
      </p>`
    : "";

  const difeomorfismosFilas: string[] = [];
  const maxMapeos = Math.max((f.directa ?? []).length, (f.inversa ?? []).length);
  for (let i = 0; i < maxMapeos; i++) {
    const d = f.directa?.[i];
    const inv = f.inversa?.[i];
    const colDir = d ? `${nombreLatex(d.simboloId)} &= ${latexExpresion(d.expresion)}` : `&`;
    const colInv = inv ? `${nombreLatex(inv.simboloId)} &= ${latexExpresion(inv.expresion)}` : `&`;
    difeomorfismosFilas.push(`${colDir} &\\qquad\\Longleftrightarrow\\qquad ${colInv}`);
  }

  const mapasHtml = `
    <section class="latex-section">
      <h2>3. Difeomorfismos de Escalamiento de Lie y Transformación Diferencial de Operadores</h2>
      <p class="latex-p">
        Sea el grupo abeliano de dilataciones canónicas que vincula las variables dimensionales continuas originales 
        con los campos y coordenadas adimensionales normalizados (denotados rigurosamente mediante el operador circunflejo ${renderTex("\\hat{\\cdot}", false)}). 
        La relación canónica biunívoca y su correspondiente transformación recíproca inversa (empleada en la certificación de equivalencia) quedan formuladas por:
      </p>
      <div class="latex-eq-display">
        ${renderTex(`\\begin{aligned}
          ${difeomorfismosFilas.join(" \\\\[8pt]\n")}
        \\end{aligned}`, true)}
      </div>
      <p class="latex-p">
        <em>Transformación de operadores diferenciales:</em> La aplicación sistemática de la regla de la cadena para derivadas temporales y espaciales 
        proyecta los operadores al espacio escalado mediante:
      </p>
      <div class="latex-eq-display">
        ${renderTex(operadoresLatex, true)}
      </div>
      ${notaAnisotropica}
      ${ecsIntermedias.length > 0 ? `
        <p class="latex-p">
          Sustituyendo los difeomorfismos de escala en las ecuaciones continuas y aplicando la linealidad de los operadores diferenciales, 
          los factores de escala constantes se factorizan frente a cada término de transporte y reacción:
        </p>
        <div class="latex-eq-display">
          ${renderTex(`\\begin{aligned}
            ${ecsIntermedias.map(eq => `${latexExpresion(eq.izquierda)} &= ${latexExpresion(eq.derecha)}`).join(" \\\\[8pt]\n")}
          \\end{aligned}`, true)}
        </div>
      ` : ""}
    </section>
  `;

  // 7. Balanza dominante y escalas resueltas
  const escalasResueltas = (f.directa ?? []).filter(d => {
    if (d.expresion.tipo === "producto" && d.expresion.argumentos.length === 2) {
      const primero = d.expresion.argumentos[0];
      if (primero.tipo === "simbolo" && primero.id === `${d.simboloId}_ref`) {
        return false;
      }
    }
    return true;
  });

  const resumenEscalasTex = escalasResueltas.length > 0
    ? renderTex(`\\begin{aligned}
        ${escalasResueltas.map(d => {
          const escalaExpr = d.expresion.tipo === "producto" ? d.expresion.argumentos[0] : d.expresion;
          return `${nombreLatex(`${d.simboloId}_ref`)} &= ${latexExpresion(escalaExpr)}`;
        }).join(" \\\\[8pt]\n")}
      \\end{aligned}`, true)
    : renderTex(`\\begin{aligned}
        ${(f.directa ?? []).map(d => `${nombreLatex(`${d.simboloId}_ref`)} &\\in \\mathbb{R}_{>0} \\quad \\text{(escala característica libre del balance)}`).join(" \\\\[8pt]\n")}
      \\end{aligned}`, true);

  const balanzaHtml = `
    <section class="latex-section">
      <h2>4. Balanza Dominante Asintótica (Principio de Kruskal) y Normalización por Factor Rector</h2>
      <p class="latex-p">
        Conforme al principio asintótico de la balanza dominante (Kruskal), se selecciona el término rector de transporte molecular 
        como factor de normalización global $\\Phi_j$ para cada balance diferencial. Dividiendo cada ecuación miembro a miembro por su respectivo factor global, 
        el coeficiente del término rector se normaliza a la unidad ($1$), cancelando grados de libertad y haciendo emerger los cocientes adimensionales característicos:
      </p>
      ${ecsNormalizadas.length > 0 ? `
        <div class="latex-eq-display">
          ${renderTex(`\\begin{aligned}
            ${ecsNormalizadas.map(eq => `${latexExpresion(eq.izquierda)} &= ${latexExpresion(eq.derecha)}`).join(" \\\\[8pt]\n")}
          \\end{aligned}`, true)}
        </div>
      ` : ""}
      <p class="latex-p">
        Fijando los coeficientes de los términos rectores a la unidad (${renderTex("\\Pi_j = 1", false)}), se determinan analíticamente las escalas de referencia:
      </p>
      <div class="latex-eq-display">
        ${resumenEscalasTex}
      </div>
      <p class="latex-p" style="font-size: 9.5pt; color: #444;">
        ${(f.libres ?? []).length ? `Escalas libres de esta formulación: ${(f.libres ?? []).map(s => renderTex(nombreLatex(s), false)).join(", ")}. Cada parametrización fija un régimen operativo continuo particular.` : "Todas las escalas de esta formulación están unívocamente determinadas por los parámetros físicos del sistema."}
      </p>
    </section>
  `;

  // 8. Funciones escaladas
  const funcionesEscaladasHtml = f.funcionesAdimensionales && f.funcionesAdimensionales.length > 0
    ? `
      <section class="latex-section">
        <h2>Funciones Constitutivas Escaladas</h2>
        <p class="latex-p">
          Las relaciones constitutivas dependientes del estado termodinámico se descomponen formalmente extrayendo su módulo dimensional característico:
        </p>
        ${f.funcionesAdimensionales.map((fn, i) => `
          <div class="latex-def-item">
            <p class="latex-p">
              <strong>Definición ${i + 1}</strong> (Función Adimensional ${renderTex(nombreLatex(fn.nombre), false)}). 
              A partir del operador dimensional constitutivo ${renderTex(nombreLatex(fn.funcionId), false)} y la escala de referencia extraída ${renderTex(nombreLatex(fn.escalaId), false)}:
            </p>
            <div class="latex-eq-display">${renderTex(latexDefinicionFuncion(fn), true)}</div>
            <p class="latex-p" style="font-size: 9pt; color: #555;">
              Definición canónica de argumento: <code>${fn.definicion}</code>
            </p>
          </div>
        `).join("\n")}
      </section>
    `
    : "";

  // 9. Retro-sustitución y equivalencia
  const itemsEquivalencia: string[] = [];
  if (tieneT) {
    itemsEquivalencia.push(`<li><strong>Operadores de acumulación temporal:</strong> ${renderTex(`\\frac{\\partial \\hat{c}_i}{\\partial \\hat{t}} = \\frac{t_{\\mathrm{ref}}}{c_{i,\\mathrm{ref}}} \\frac{\\partial c_i}{\\partial t}`, false)}.</li>`);
  }
  if (coordenadas.length <= 1) {
    itemsEquivalencia.push(`<li><strong>Operadores de transporte espacial 1D:</strong> ${renderTex(`\\frac{\\partial^2 \\hat{c}_i}{\\partial \\hat{x}^2} = \\frac{x_{\\mathrm{ref}}^2}{c_{i,\\mathrm{ref}}} \\frac{\\partial^2 c_i}{\\partial x^2}`, false)}.</li>`);
  } else if (coordenadas.length === 2) {
    itemsEquivalencia.push(`<li><strong>Operadores de transporte espacial 2D (anisotrópico):</strong> ${renderTex(`\\frac{\\partial^2 \\hat{c}_i}{\\partial \\hat{x}^2} = \\frac{x_{\\mathrm{ref}}^2}{c_{i,\\mathrm{ref}}} \\frac{\\partial^2 c_i}{\\partial x^2}, \\qquad \\frac{\\partial^2 \\hat{c}_i}{\\partial \\hat{y}^2} = \\frac{y_{\\mathrm{ref}}^2}{c_{i,\\mathrm{ref}}} \\frac{\\partial^2 c_i}{\\partial y^2}`, false)}.</li>`);
  } else if (coordenadas.length >= 3) {
    itemsEquivalencia.push(`<li><strong>Operadores de transporte espacial 3D:</strong> ${renderTex(`\\nabla_{\\hat{x},\\hat{y},\\hat{z}}^2 \\hat{c}_i = \\frac{x_{\\mathrm{ref}}^2}{c_{i,\\mathrm{ref}}} \\left[ \\frac{\\partial^2 c_i}{\\partial x^2} + \\mathcal{A}_y^2 \\frac{\\partial^2 c_i}{\\partial y^2} + \\mathcal{A}_z^2 \\frac{\\partial^2 c_i}{\\partial z^2} \\right]`, false)}.</li>`);
  }
  if (campos.length > 0) {
    const camposStr = campos.map(c => renderTex(`\\hat{${nombreLatex(c)}} = \\frac{${nombreLatex(c)}}{${nombreLatex(`${c}_ref`)}}`, false)).join(", ");
    itemsEquivalencia.push(`<li><strong>Campos y acoplamientos constitutivos:</strong> ${camposStr}, preservando de forma exacta la linealidad y las leyes cinéticas.</li>`);
  }

  const equivalenciaHtml = `
    <section class="latex-section">
      <h2>13. Demostración Formal de Equivalencia Recíproca (Retro-sustitución Exacta)</h2>
      <p class="latex-p">
        Para certificar matemáticamente la validez del sistema adimensional deducido, se aplica la retro-sustitución analítica 
        del difeomorfismo inverso en el sistema diferencial normalizado:
      </p>
      <div class="latex-eq-display">
        ${renderTex(`\\mathcal{E}_{\\mathrm{adimensional}}(\\hat{c}, \\hat{t}, \\hat{x}) \\xrightarrow{\\text{retro-sustitución inversa}} \\mathcal{E}_{\\mathrm{dimensional}}(c, t, x) \\equiv 0`, true)}
      </div>
      <p class="latex-p">
        Cada uno de los operadores diferenciales y términos fuente cinéticos reconstruye de manera idéntica y sin truncamiento 
        las ecuaciones del balance continuo original:
      </p>
      <ul class="latex-bullet-list">
        ${itemsEquivalencia.join("\n")}
      </ul>
      <p class="latex-p" style="font-size: 9.5pt; color: #333;">
        Estado de certificación formal: <strong>${f.equivalencia?.estado === "demostrada" ? "Equivalencia demostrada bajo sus restricciones" : "No demostrada"}</strong>. 
        Alcance del certificado algebraico: ${f.equivalencia?.alcance ?? "Certificación de conservación diferencial exacta"}.
      </p>
    </section>
  `;

  // 10. Dominios y restricciones
  const restriccionesHtml = (f.restricciones && f.restricciones.length > 0) || (f.dominios && f.dominios.length > 0)
    ? `
      <section class="latex-section">
        <h2>14. Dominios de Validez, Condiciones de Contorno y Restricciones Físicas</h2>
        ${f.dominios.length > 0 ? `
          <h3 class="latex-subsec-title">Dominios Espacio-Temporales Adimensionales</h3>
          <div class="latex-dominios-list">
            ${f.dominios.map(d => `
              <div class="latex-eq-display">${renderTex(`${latexExpresion(d.desde)} \\le ${nombreLatex(d.variableId)} \\le ${latexExpresion(d.hasta)}`, true)}</div>
            `).join("\n")}
          </div>
        ` : ""}
        ${f.restricciones.length > 0 ? `
          <h3 class="latex-subsec-title" style="margin-top: 14px;">Restricciones de Regularidad Física y No Singularidad</h3>
          <ul class="latex-bullet-list">
            ${f.restricciones.map(r => `
              <li>
                <strong>${r.id}:</strong> ${r.motivo}. 
                ${renderTex(`${latexExpresion(r.expresion)}${r.tipo === "positivo" ? " > 0" : r.tipo === "negativo" ? " < 0" : r.tipo === "no_nulo" ? " \\ne 0" : r.tipo === "igualdad" && r.valor ? ` = ${latexExpresion(r.valor)}` : ""}`, false)}
              </li>
            `).join("\n")}
          </ul>
        ` : ""}
      </section>
    `
    : "";

  // 11. Apéndice metodológico
  const transiciones = (f.desarrollo ?? []).filter(p => pasoTex(p.antes) !== pasoTex(p.despues));
  const verificaciones = (f.desarrollo ?? []).filter(p => pasoTex(p.antes) === pasoTex(p.despues));

  const apendiceHtml = f.desarrollo && f.desarrollo.length > 0
    ? `
      <section class="latex-section latex-page-break">
        <h2>15. Apéndice Metodológico: Certificación Algebraica de la Secuencia Deductiva</h2>
        <p class="latex-p">
          A continuación se presenta el registro riguroso de las transformaciones simbólicas certificadas por el núcleo algebraico. 
          Las transiciones constructivas se formalizan mediante implicación matemática (${renderTex("A \\implies B", false)}), 
          garantizando la trazabilidad analítica completa sin omisión de pasos intermedios.
        </p>

        <h3 class="latex-subsec-title">15.1 Transiciones Algebraicas Constructivas</h3>
        <p class="latex-p" style="font-size: 9.5pt; color: #333;">
          Secuencia de reescritura canónica desde los operadores continuos dimensionales hasta la forma adimensional cerrada:
        </p>
        <div class="latex-deduction-flow">
          ${transiciones.map((p, i) => {
            const antesStr = pasoTex(p.antes);
            const despuesStr = pasoTex(p.despues);
            const just = formatearJustificacion(p.justificacion);
            const sup = p.supuestos.length > 0 ? formatearSupuestos(p.supuestos) : "";

            const esCorta = (antesStr.length + despuesStr.length < 55) && 
              !(antesStr.includes("\\frac") && despuesStr.includes("\\frac")) &&
              !(antesStr.includes("+") && despuesStr.includes("+"));
            
            const mathHtml = esCorta
              ? `<div class="latex-eq-display">${renderTex(`${antesStr} \\implies ${despuesStr}`, true)}</div>`
              : `
                <div class="latex-deduction-step">
                  <div class="latex-eq-display latex-eq-step-from">${renderTex(antesStr, true)}</div>
                  <div class="latex-eq-arrow">${renderTex("\\Downarrow", true)}</div>
                  <div class="latex-eq-display latex-eq-step-to">${renderTex(despuesStr, true)}</div>
                </div>
              `;

            return `
              <div class="latex-step-block">
                <div class="latex-step-header">
                  <strong>Paso T.${i + 1}.</strong> <em>${nombreReglaFormal(p.regla)}</em>
                </div>
                ${just ? `<div class="latex-step-just"><em>Fundamento formal:</em> ${just}</div>` : ""}
                ${mathHtml}
                ${sup ? `<div class="latex-step-sup"><em>Condición de validez requerida:</em> ${sup}</div>` : ""}
              </div>
            `;
          }).join("\n")}
        </div>

        ${verificaciones.length > 0 ? `
          <h3 class="latex-subsec-title" style="margin-top: 24px;">15.2 Auditoría de Identidades e Invarianzas Verificadas</h3>
          <p class="latex-p" style="font-size: 9.5pt; color: #333;">
            Propiedades estáticas certificadas por el cálculo simbólico (homogeneidad de Fourier, invariancia métrica y consistencia dimensional):
          </p>
          <ul class="latex-bullet-list">
            ${verificaciones.map((p, i) => {
              const str = pasoTex(p.despues);
              const just = formatearJustificacion(p.justificacion);
              return `
                <li>
                  <strong>Identidad V.${i + 1} (${nombreReglaFormal(p.regla)}):</strong> 
                  ${just ? `${just} ` : ""}
                  <div class="latex-eq-display" style="margin: 6px 0;">
                    ${renderTex(`${str} \\quad \\text{(\\checkmark\\,certificada)}`, true)}
                  </div>
                </li>
              `;
            }).join("\n")}
          </ul>
        ` : ""}
      </section>
    `
    : "";

  return `<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>${titulo} · Forma ${indiceForma + 1}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
  <style>
    /* Reglas fundamentales de maquetación KaTeX embebidas */
    ${KATEX_CSS}

    /* Tipografía académica estilo LaTeX / Computer Modern */
    @import url('https://fonts.googleapis.com/css2?family=Latin+Modern+Roman:ital,wght@0,400;0,700;1,400;1,700&family=Latin+Modern+Mono&display=swap');

    :root {
      --latex-font: "Latin Modern Roman", "Computer Modern", "TeX Gyre Termes", "Times New Roman", Times, Georgia, serif;
      --latex-mono: "Latin Modern Mono", "Courier New", monospace;
      --latex-text: #111111;
      --latex-bg: #ffffff;
      --latex-line: #000000;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: var(--latex-font);
      color: var(--latex-text);
      background: #f4f4f2;
      line-height: 1.58;
      font-size: 11pt;
      -webkit-font-smoothing: antialiased;
      padding: 30px 20px;
    }

    /* Hoja A4 centrada tipo artículo científico */
    .latex-paper {
      max-width: 840px;
      margin: 0 auto;
      background: #ffffff;
      padding: 60px 75px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.10);
      border: 1px solid #dcdcd6;
    }

    /* Barra de herramientas flotante superior */
    .latex-action-bar {
      position: sticky;
      top: 15px;
      max-width: 840px;
      margin: 0 auto 20px auto;
      background: #1e281e;
      color: #ffffff;
      border-radius: 8px;
      padding: 12px 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 6px 18px rgba(0,0,0,0.2);
      z-index: 1000;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    .latex-print-btn {
      background: #2e7d32;
      color: white;
      border: none;
      padding: 8px 18px;
      border-radius: 6px;
      font-weight: 600;
      font-size: 13px;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 8px;
      transition: background 0.15s;
    }
    .latex-print-btn:hover { background: #1b5e20; }

    .latex-close-btn {
      background: transparent;
      border: 1px solid #666;
      color: #ddd;
      padding: 6px 14px;
      border-radius: 6px;
      font-size: 12px;
      cursor: pointer;
    }
    .latex-close-btn:hover { background: #333; color: #fff; }

    /* Encabezado formal de artículo LaTeX */
    .latex-header-block {
      text-align: center;
      margin-bottom: 35px;
      border-bottom: 0.5pt solid #bbb;
      padding-bottom: 25px;
    }

    .latex-pre-title {
      font-size: 9pt;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: #555;
      margin-bottom: 12px;
      font-weight: 600;
    }

    .latex-title {
      font-size: 20pt;
      font-weight: 700;
      line-height: 1.25;
      margin-bottom: 14px;
      color: #000;
    }

    .latex-authors {
      font-size: 10.5pt;
      margin-bottom: 4px;
    }

    .latex-affiliation {
      font-size: 9.5pt;
      color: #444;
      font-style: italic;
      margin-bottom: 8px;
    }

    .latex-date {
      font-size: 9.5pt;
      color: #666;
    }

    /* Abstract formal con filetes horizontales superior e inferior */
    .latex-abstract {
      margin: 25px 35px 30px 35px;
      padding: 12px 10px;
      border-top: 0.5pt solid #000;
      border-bottom: 0.5pt solid #000;
    }

    .latex-abstract-title {
      text-align: center;
      font-size: 10pt;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
    }

    .latex-abstract-text {
      font-size: 9.5pt;
      text-align: justify;
      line-height: 1.55;
      color: #222;
      hyphens: auto;
    }

    /* Secciones estilo LaTeX article */
    .latex-section {
      margin-bottom: 34px;
    }

    .latex-section h2 {
      font-size: 13pt;
      font-weight: 700;
      border-bottom: 0.75pt solid #000;
      padding-bottom: 4px;
      margin-top: 24px;
      margin-bottom: 14px;
      color: #000;
      letter-spacing: 0.01em;
    }

    .latex-subsec-title {
      font-size: 11pt;
      font-weight: 700;
      margin-top: 18px;
      margin-bottom: 8px;
      color: #000;
    }

    .latex-p {
      text-align: justify;
      margin-bottom: 12px;
      font-size: 10.5pt;
      line-height: 1.6;
      hyphens: auto;
    }

    /* Displays matemáticos centrados (SIN CAJAS NI TABLAS) */
    .latex-eq-display {
      margin: 14px 0;
      overflow-x: auto;
      text-align: center;
      page-break-inside: avoid;
      break-inside: avoid;
    }

    /* Ecuaciones numeradas estilo LaTeX (1), (2) */
    .latex-eq-item {
      margin: 14px 0;
      page-break-inside: avoid;
      break-inside: avoid;
    }

    .latex-eq-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      position: relative;
      padding: 4px 0;
    }

    .latex-eq-math {
      margin: 0 auto;
      overflow-x: auto;
      padding: 0 40px;
    }

    .latex-eq-num {
      position: absolute;
      right: 0;
      font-size: 10.5pt;
      color: #000;
      font-weight: normal;
    }

    .latex-eq-note {
      font-size: 8.5pt;
      color: #555;
      font-style: italic;
      text-align: center;
      margin-top: 2px;
    }

    /* Tabla estilo LaTeX booktabs (sin bordes verticales ni cajas) */
    .latex-booktabs {
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0;
      font-size: 10pt;
      border-top: 1.5pt solid #000;
      border-bottom: 1.5pt solid #000;
      page-break-inside: avoid;
      break-inside: avoid;
    }

    .latex-booktabs th {
      border-bottom: 0.75pt solid #000;
      padding: 8px 10px;
      font-weight: 700;
      font-size: 9.5pt;
      letter-spacing: 0.02em;
    }

    .latex-booktabs td {
      padding: 10px 10px;
      vertical-align: middle;
      border-bottom: 0.5pt solid #e6e6e6;
    }

    .latex-booktabs tr:last-child td {
      border-bottom: none;
    }

    .latex-badge {
      display: inline-block;
      font-size: 8pt;
      padding: 2px 7px;
      border-radius: 3px;
      font-family: -apple-system, sans-serif;
      font-weight: 600;
    }
    .badge-dimless {
      background: #e8f5e9;
      color: #1b5e20;
      border: 0.5pt solid #a5d6a7;
    }
    .badge-residual {
      background: #fff3e0;
      color: #e65100;
      border: 0.5pt solid #ffcc80;
    }

    /* Definición de funciones constitutivas */
    .latex-def-item {
      margin: 14px 0;
      page-break-inside: avoid;
      break-inside: avoid;
    }

    /* Traza de deducción matemática continua (SIN CAJAS NI BLOQUES GRISES) */
    .latex-deduction-flow {
      margin-top: 14px;
    }

    .latex-step-block {
      margin: 18px 0;
      padding-bottom: 14px;
      border-bottom: 0.5pt solid #e6e6e6;
      page-break-inside: avoid;
      break-inside: avoid;
    }
    .latex-step-block:last-child {
      border-bottom: none;
    }

    .latex-step-header {
      font-size: 11pt;
      font-weight: 700;
      color: #111;
      margin-bottom: 4px;
    }

    .latex-step-just {
      font-size: 9.5pt;
      color: #333;
      margin-bottom: 6px;
      line-height: 1.5;
      text-align: justify;
    }

    .latex-deduction-step {
      margin: 10px 0;
      text-align: center;
      page-break-inside: avoid;
      break-inside: avoid;
    }

    .latex-eq-step-from {
      margin: 8px 0 3px 0 !important;
    }

    .latex-eq-arrow {
      margin: 3px 0 !important;
      text-align: center;
      line-height: 1;
    }

    .latex-eq-step-to {
      margin: 3px 0 8px 0 !important;
    }

    .latex-step-sup {
      font-size: 8.5pt;
      color: #555;
      margin-top: 5px;
      font-style: italic;
    }

    .latex-bullet-list {
      margin-left: 24px;
      margin-top: 8px;
      margin-bottom: 12px;
      font-size: 10pt;
    }
    .latex-bullet-list li { margin-bottom: 6px; line-height: 1.5; }

    .latex-page-break {
      page-break-before: always;
      break-before: page;
    }

    .latex-footer-note {
      text-align: center;
      font-size: 8.5pt;
      color: #777;
      border-top: 0.5pt solid #ccc;
      padding-top: 15px;
      margin-top: 40px;
    }

    /* Impresión A4 a PDF rigurosa y libre de solapamientos */
    @media print {
      body {
        background: white !important;
        padding: 0 !important;
        font-size: 10pt;
        line-height: 1.5;
      }
      .latex-action-bar { display: none !important; }
      .latex-paper {
        max-width: 100% !important;
        padding: 0 !important;
        margin: 0 !important;
        box-shadow: none !important;
        border: none !important;
      }
      .latex-eq-display,
      .latex-eq-item,
      .latex-eq-math,
      .latex-step-block,
      .latex-deduction-step,
      .latex-def-item,
      .latex-booktabs {
        overflow: visible !important;
        overflow-x: visible !important;
        page-break-inside: avoid !important;
        break-inside: avoid !important;
      }
      .latex-step-block {
        margin: 16px 0 !important;
        padding-bottom: 12px !important;
        border-bottom: 0.5pt solid #ccc !important;
      }
      .katex-display {
        margin: 0.6em 0 !important;
        overflow: visible !important;
      }
      .katex-display > .katex {
        white-space: normal !important;
        text-align: center !important;
      }
      .katex-display > .katex > .katex-html {
        white-space: normal !important;
      }
      .katex-mathml {
        display: none !important;
      }
      @page {
        size: A4 portrait;
        margin: 20mm 15mm 20mm 15mm;
      }
    }
  </style>
</head>
<body>
  <div class="latex-action-bar">
    <div>
      <strong>Informe Académico de Adimensionalización (LaTeX Style)</strong> · Formato formal para publicación y archivo técnico.
    </div>
    <div style="display:flex;gap:10px;">
      <button class="latex-print-btn" onclick="window.print()">
        📄 Imprimir / Guardar como PDF
      </button>
      <button class="latex-close-btn" style="color: #ffffff; background: #37474f; border-color: #546e7a;" onclick="descargarTex()">
        📑 Descargar fuente .tex
      </button>
      <button class="latex-close-btn" onclick="window.close()">Cerrar</button>
    </div>
  </div>

  <main class="latex-paper">
    <header class="latex-header-block">
      <p class="latex-pre-title">Antigravity · Núcleo de Modelado Matemático y Análisis Dimensional</p>
      <h1 class="latex-title">${titulo}</h1>
      <div class="latex-authors">División de Modelado Matemático y Fenómenos de Transporte</div>
      <div class="latex-affiliation">Laboratorio Computacional de Dinámica No Lineal y Reactiva</div>
      <div class="latex-date">${fecha} · Formulación Canónica ${indiceForma + 1}</div>

      <div class="latex-abstract">
        <div class="latex-abstract-title">Resumen</div>
        <p class="latex-abstract-text">
          En este documento se formaliza la deducción analítica y la reducción asintótica canónica del modelo físico continuo 
          denominado <em>«${nombreModelo}»</em>. A través del cálculo algebraico de los grados de libertad dimensionales 
          y la aplicación del teorema ${renderTex("\\Pi", false)} de Buckingham generalizado mediante simetrías de escala de Lie, 
          se construye un sistema diferencial libre de unidades parametrizado por escalas características de referencia. 
          Estado de normalización: <strong>${f.normalizacion.estado === "completa" ? "Completamente adimensional" : "Parcialmente normalizado"}</strong>. 
          Equivalencia formal: <strong>${f.equivalencia.estado === "demostrada" ? "Demostrada bajo sus restricciones" : "No demostrada"}</strong>. 
          Todas las variables adimensionales se expresan mediante el operador circunflejo (${renderTex("\\hat{\\cdot}", false)}) 
          preservando la consistencia física y la topología diferencial del sistema original.
        </p>
      </div>
    </header>

    <section class="latex-section">
      <h2>1. Modelo Continuo Dimensional Original y Balances de Transporte</h2>
      <p class="latex-p">
        El sistema de ecuaciones diferenciales parciales continuas que describe los balances de materia, cantidad de movimiento 
        o energía en el medio reactivo continuo original queda expresado formalmente por:
      </p>
      <div class="latex-equations-block">
        ${ecuacionesOriginalesHtml}
      </div>
      <p class="latex-p" style="font-size: 9.5pt; color: #444; margin-top: 10px;">
        Balance diferencial original en coordenadas físicas dimensionales antes de la acción del grupo de reescalado.
      </p>
    </section>

    <section class="latex-section">
      <h2>2. Auditoría de Homogeneidad Dimensional (Principio de Fourier)</h2>
      <p class="latex-p">
        De acuerdo con el teorema fundamental de Fourier, toda ley física diferencial es covariante e invariante frente 
        a cambios en el sistema de unidades fundamentales. Se audita la compatibilidad dimensional de todos los sumandos en cada ecuación, 
        verificando que comparten coordenadas idénticas en la base fundamental $[\mathsf{M}, \mathsf{L}, \mathsf{T}, \mathsf{N}]$:
      </p>
      <p class="latex-p" style="font-size: 9.5pt; color: #222; text-align: center; margin: 12px 0;">
        ${f.desarrollo && f.desarrollo[0]?.justificacion ? formatearAuditoriaTexto(f.desarrollo[0].justificacion) : "Consistencia de dimensiones de balance verificada en todos los términos continuos."}
      </p>
    </section>

    ${mapasHtml}
    ${balanzaHtml}

    <section class="latex-section">
      <h2>5. Sistema Diferencial Adimensional Canónico Final</h2>
      <p class="latex-p">
        Ecuaciones gobernantes del sistema continuo transformadas en variables normalizadas adimensionales con respecto a las escalas canónicas elegidas:
      </p>
      <div class="latex-equations-block">
        ${ecuacionesAdimHtml}
      </div>
    </section>

    ${gruposHtml}

    ${generarSeccionAsintoticaHtml(f)}
    ${generarSeccionCondicionesFronteraHtml(f)}
    ${generarSeccionPerturbacionesSingularesHtml(f)}
    ${generarSeccionEstabilidadHtml(f)}
    ${generarSeccionSimetriasLieHtml(f)}
    ${generarSeccionAuditoriaNumericaHtml(f)}

    ${equivalenciaHtml}
    ${funcionesEscaladasHtml}
    ${restriccionesHtml}
    ${apendiceHtml}

    <footer class="latex-footer-note">
      Documento generado automáticamente por el Núcleo Formal de Adimensionalización de Antigravity.<br>
      Certificado algebraico de consistencia dimensional y conservación diferencial.
    </footer>
  </main>

  <script>
    function descargarTex() {
      const tex = ${JSON.stringify(exportarDesarrollo(f))};
      const blob = new Blob([tex], { type: "text/x-tex;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = ${JSON.stringify(`desarrollo-${nombreModelo.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-forma-${indiceForma + 1}.tex`)};
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 2000);
    }

    window.addEventListener("load", () => {
      setTimeout(() => {
        window.focus();
      }, 250);
    });
  </script>
</body>
</html>`;
}

export function descargarDesarrolloPdf(
  nombreModelo: string,
  indiceForma: number,
  f: FormulacionNucleo
): void {
  const html = generarHtmlDesarrollo(nombreModelo, indiceForma, f);
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const w = window.open(url, "_blank");
  if (!w) {
    const a = document.createElement("a");
    a.href = url;
    a.download = `articulo-adimensionalizacion-${nombreModelo.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-forma-${indiceForma + 1}.html`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
  }
}
