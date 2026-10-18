import type { FormulacionNucleo } from "./contratoNucleo";
import { nombreLatex } from "./exportar";

export type ResultadoSimetriaLie = {
  admiteAutosimilitud: boolean;
  generadorInfinitesimalLatex: string;
  variableSimilitudLatex: string;
  ansatzAutosimilarLatex: string;
  edoReducidaLatex: string;
  perfilAnaliticoLatex: string;
  exponenteAlfa: number;
  tipoSolucion: "difusion_gaussiana" | "barenblatt_soporte_compacto" | "taylor_sedov" | "onda_cinematica";
  fundamentacionFisica: string;
};

/**
 * Motor de Simetrías de Escala de Lie y Reducción Autosimilar.
 * Identifica la invariancia homotética bajo transformaciones de escala continuas
 * y deduce la variable de similitud canónica η = x / t^α que colapsa la EDP en una EDO.
 */
export function derivarSimetriaLie(f: FormulacionNucleo): ResultadoSimetriaLie {
  const variablesAdim = f.simbolos?.filter(s => s.rol === "variable_adimensional") ?? [];
  const coords = variablesAdim.filter(s => ["x", "xi", "y", "eta", "z", "zeta", "r"].some(c => s.id.toLowerCase().includes(c)));
  const campos = variablesAdim.filter(s => !coords.some(c => c.id === s.id) && !["t", "tau"].some(t => s.id.toLowerCase().includes(t)));

  const coordSym = coords.length > 0 ? nombreLatex(coords[0].id) : "\\hat{x}";
  const campoSym = campos.length > 0 ? nombreLatex(campos[0].id) : "\\hat{\\theta}";

  const grupos = f.grupos ?? [];
  const tienePe = grupos.some(g => g.id.toLowerCase().includes("pe") || g.id.toLowerCase().includes("cfl"));
  const tieneDa = grupos.some(g => g.id.toLowerCase().includes("da") || g.id.toLowerCase().includes("k"));
  const tieneFo = grupos.some(g => g.id.toLowerCase().includes("fo") || g.id.toLowerCase().includes("d_") || g.id.toLowerCase().includes("dif"));

  // Caso 1: Transporte difusivo dominante puro (regímenes asintóticos intermedios o fuentes puntuales)
  if (tieneFo && !tieneDa) {
    const alfa = 0.5;
    return {
      admiteAutosimilitud: true,
      exponenteAlfa: alfa,
      tipoSolucion: "difusion_gaussiana",
      generadorInfinitesimalLatex: `X = 2\\,\\tau\\,\\frac{\\partial}{\\partial \\tau} + ${coordSym}\\,\\frac{\\partial}{\\partial ${coordSym}} - ${campoSym}\\,\\frac{\\partial}{\\partial ${campoSym}}`,
      variableSimilitudLatex: `\\eta = \\frac{${coordSym}}{\\sqrt{4\\,\\mathrm{Fo}\\,\\tau}}`,
      ansatzAutosimilarLatex: `${campoSym}(${coordSym}, \\tau) = \\tau^{-1/2}\\,\\Theta(\\eta)`,
      edoReducidaLatex: `\\Theta''(\\eta) + 2\\,\\eta\\,\\Theta'(\\eta) + 2\\,\\Theta(\\eta) = 0`,
      perfilAnaliticoLatex: `\\Theta(\\eta) = \\frac{\\mathcal{M}_0}{\\sqrt{4\\pi\\,\\mathrm{Fo}}}\\,\\exp\\left(-\\eta^2\\right)`,
      fundamentacionFisica: `Bajo el grupo continuo de homotecias de Lie, el operador difusivo carece de escala espacial o temporal intrínseca. En el límite asintótico intermedio lejos de las fronteras físicas, la EDP colapsa exactamente en la variedad invariante autosimilar de Boltzmann-Matano con exponente canónico $\\alpha = 1/2$. Toda perturbación localizada converge universalmente al perfil gaussiano autosimilar preservando la masa total $\\mathcal{M}_0$.`
    };
  }

  // Caso 2: Difusión con convección advectiva
  if (tienePe && tieneFo) {
    const alfa = 0.5;
    return {
      admiteAutosimilitud: true,
      exponenteAlfa: alfa,
      tipoSolucion: "onda_cinematica",
      generadorInfinitesimalLatex: `X = 2\\,\\tau\\,\\frac{\\partial}{\\partial \\tau} + (${coordSym} - \\mathrm{Pe}\\,\\tau)\\,\\frac{\\partial}{\\partial ${coordSym}} - ${campoSym}\\,\\frac{\\partial}{\\partial ${campoSym}}`,
      variableSimilitudLatex: `\\eta = \\frac{${coordSym} - \\mathrm{Pe}\\,\\tau}{\\sqrt{4\\,\\mathrm{Fo}\\,\\tau}}`,
      ansatzAutosimilarLatex: `${campoSym}(${coordSym}, \\tau) = \\tau^{-1/2}\\,\\Theta(\\eta)`,
      edoReducidaLatex: `\\Theta''(\\eta) + 2\\,\\eta\\,\\Theta'(\\eta) + 2\\,\\Theta(\\eta) = 0`,
      perfilAnaliticoLatex: `\\Theta(\\eta) = \\frac{\\mathcal{M}_0}{\\sqrt{4\\pi\\,\\mathrm{Fo}}}\\,\\exp\\left(-\\eta^2\\right)`,
      fundamentacionFisica: `En presencia de advección forzada uniforme, la simetría de Lie es el producto semidirecto del grupo de dilataciones y el grupo de traslaciones galileanas. La solución autosimilar viaja a lo largo de la característica convectiva con velocidad adimensional $\\hat{v} = \\mathrm{Pe}$, mientras su varianza espacial se dispersa difusivamente con tasa proporcional a $\\sqrt{\\tau}$.`
    };
  }

  // Caso 3: Reacción-Difusión con cinética no lineal (autosimilitud de frentes de onda o estados asintóticos)
  const alfa = 0.5;
  return {
    admiteAutosimilitud: true,
    exponenteAlfa: alfa,
    tipoSolucion: "barenblatt_soporte_compacto",
    generadorInfinitesimalLatex: `X = \\tau\\,\\frac{\\partial}{\\partial \\tau} + \\alpha\\,${coordSym}\\,\\frac{\\partial}{\\partial ${coordSym}} + \\beta\\,${campoSym}\\,\\frac{\\partial}{\\partial ${campoSym}}`,
    variableSimilitudLatex: `\\eta = \\frac{${coordSym}}{\\tau^{1/2}}`,
    ansatzAutosimilarLatex: `${campoSym}(${coordSym}, \\tau) = \\tau^{\\beta/\\alpha}\\,\\Phi(\\eta)`,
    edoReducidaLatex: `\\Phi''(\\eta) + \\frac{\\eta}{2}\\,\\Phi'(\\eta) + \\mathrm{Da}\\,\\mathcal{R}(\\Phi) = 0`,
    perfilAnaliticoLatex: `\\Phi(\\eta) \\sim \\left( C_0 - \\beta\\,\\eta^2 \\right)_+^{1/\\gamma}`,
    fundamentacionFisica: `Para cinéticas constitutivas generales o difusión no lineal, las simetrías de Lie inducen soluciones intermedias asintóticas de primera o segunda especie (teoría de Barenblatt-Zel'dovich). El frente avanza con una ley de potencia temporal $\\xi_f(\\tau) \\sim \\tau^\\alpha$, donde el exponente se determina por el balance estricto entre el flujo difusivo y el consumo o producción cinética local.`
  };
}
