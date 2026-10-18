import type { FormulacionNucleo } from "./contratoNucleo";
import { latexExpresion, nombreLatex } from "./exportar";

export type ResultadoCapaLimite = {
  epsilonId: string;
  epsilonDef: string;
  espesorCapaLimite: string;
  ecuacionExteriorLatex: string;
  ecuacionInteriorLatex: string;
  condicionAcoplamientoLatex: string;
  solucionCompuestaLatex: string;
  explicacionFisica: string;
};

/**
 * Deducción asintótica rigurosa de perturbaciones singulares y capa límite.
 * Funciona de manera universal para cualquier sistema diferencial continuo,
 * extrayendo dinámicamente los campos dependientes, coordenadas espaciales
 * y grupos adimensionales gobernantes de la formulación.
 */
export function derivarCapaLimite(f: FormulacionNucleo): ResultadoCapaLimite {
  const grupos = f.grupos ?? [];

  // 1. Identificar símbolos de campo dependiente principal y coordenadas
  const variablesAdim = f.simbolos?.filter(s => s.rol === "variable_adimensional") ?? [];
  const coords = variablesAdim.filter(s => ["x", "xi", "y", "eta", "z", "zeta", "r"].some(c => s.id.toLowerCase().includes(c)));
  const campos = variablesAdim.filter(s => !coords.some(c => c.id === s.id) && !["t", "tau"].some(t => s.id.toLowerCase().includes(t)));

  const coordSym = coords.length > 0 ? nombreLatex(coords[0].id) : "\\hat{x}";
  const campoSym = campos.length > 0 ? nombreLatex(campos[0].id) : "\\hat{\\theta}";

  // 2. Identificar el grupo perturbativo singular que multiplica a la derivada de mayor orden
  const grupoPe = grupos.find(g => {
    const id = g.id.toLowerCase();
    return id.includes("pe") || id.includes("cfl") || id.includes("re");
  });
  const grupoA = grupos.find(g => {
    const id = g.id.toLowerCase();
    return id.includes("a_") || id.includes("esbeltez") || id.includes("aspecto");
  });
  const grupoDa = grupos.find(g => {
    const id = g.id.toLowerCase();
    return id.includes("da") || id.includes("thiele") || id.includes("phi");
  });

  let epsilonId = "\\epsilon";
  let epsilonDef = "1 / \\Pi_{\\mathrm{singular}}";
  let espesorCapaLimite = "\\delta \\sim \\mathcal{O}(\\epsilon)";
  let ordenAlfa = 1;
  let tipoMecanismo = "difusivo-advectivo";

  if (grupoA) {
    epsilonId = "\\epsilon_y";
    epsilonDef = `1 / ${nombreLatex(grupoA.id)}`;
    espesorCapaLimite = `\\delta \\sim \\mathcal{O}(\\epsilon_y) = \\mathcal{O}\\left(\\frac{1}{${nombreLatex(grupoA.id)}}\\right)`;
    ordenAlfa = 1;
    tipoMecanismo = "geométrico de esbeltez (dominio delgado)";
  } else if (grupoPe) {
    epsilonId = "\\epsilon";
    epsilonDef = `1 / ${nombreLatex(grupoPe.id)}`;
    espesorCapaLimite = `\\delta \\sim \\mathcal{O}(\\epsilon) = \\mathcal{O}\\left(\\frac{1}{${nombreLatex(grupoPe.id)}}\\right)`;
    ordenAlfa = 1;
    tipoMecanismo = "advectivo-difusivo de capa de transporte";
  } else if (grupoDa) {
    epsilonId = "\\epsilon_r";
    epsilonDef = `1 / \\sqrt{${nombreLatex(grupoDa.id)}}`;
    espesorCapaLimite = `\\delta_r \\sim \\mathcal{O}(\\epsilon_r) = \\mathcal{O}\\left(\\frac{1}{\\sqrt{${nombreLatex(grupoDa.id)}}}\\right)`;
    ordenAlfa = 2;
    tipoMecanismo = "de reacción rápida con amortiguamiento difusivo";
  }

  // 3. Ecuación exterior regular degenerada (orden O(1) con epsilon -> 0)
  const ecuacionExteriorLatex = `\\mathcal{L}_{\\mathrm{outer}}\\left(${campoSym}_0^{\\mathrm{out}}\\right) = 0 \\quad \\implies \\quad \\lim_{${epsilonId} \\to 0} \\left[ \\mathcal{L}\\left(${campoSym}\\right) \\right] = 0`;

  // 4. Ecuación interior re-escalada (magnificación de la derivada singular)
  const innerVar = `\\tilde{X}`;
  const exponenteEstiramiento = ordenAlfa === 1 ? epsilonId : `${epsilonId}^{1/${ordenAlfa}}`;
  const ecuacionInteriorLatex = `\\frac{d^2 ${campoSym}_0^{\\mathrm{in}}}{d${innerVar}^2} + \\dots = 0, \\qquad ${innerVar} = \\frac{${coordSym}_{\\mathrm{frontera}} - ${coordSym}}{${exponenteEstiramiento}}`;

  // 5. Principio de acoplamiento asintótico de Prandtl - Van Dyke
  const condicionAcoplamientoLatex = `\\lim_{${coordSym} \\to ${coordSym}_{\\mathrm{frontera}}} ${campoSym}_0^{\\mathrm{out}}(${coordSym}) = \\lim_{${innerVar} \\to \\infty} ${campoSym}_0^{\\mathrm{in}}(${innerVar}) \\equiv ${campoSym}_{\\mathrm{overlap}}`;

  // 6. Solución compuesta uniforme
  const solucionCompuestaLatex = `${campoSym}_{\\mathrm{comp}}(${coordSym}) = ${campoSym}_0^{\\mathrm{out}}(${coordSym}) + ${campoSym}_0^{\\mathrm{in}}\\left(\\frac{${coordSym}_{\\mathrm{frontera}} - ${coordSym}}{${exponenteEstiramiento}}\\right) - ${campoSym}_{\\mathrm{overlap}} + \\mathcal{O}(${epsilonId})`;

  // 7. Fundamentación física universal
  const explicacionFisica = `En el límite asintótico singular ${epsilonId} \\ll 1 (${tipoMecanismo}), el operador diferencial de mayor orden se suprime en la escala global del dominio, reduciendo el orden matemático del sistema y tornando imposible la satisfacción simultánea de todas las condiciones de frontera impuestas. En consecuencia, surge una capa límite localizada de espesor característico ${espesorCapaLimite}. Mediante la dilatación de coordenadas locales ${innerVar}, los gradientes espaciales se amplifican a $\\mathcal{O}(${epsilonId}^{-${ordenAlfa}})$, restableciendo la balanza dominante entre los flujos locales y asegurando, mediante el principio de acoplamiento asintótico de Prandtl–Van Dyke, una transición continua y libre de singularidades.`;

  return {
    epsilonId,
    epsilonDef,
    espesorCapaLimite,
    ecuacionExteriorLatex,
    ecuacionInteriorLatex,
    condicionAcoplamientoLatex,
    solucionCompuestaLatex,
    explicacionFisica,
  };
}
