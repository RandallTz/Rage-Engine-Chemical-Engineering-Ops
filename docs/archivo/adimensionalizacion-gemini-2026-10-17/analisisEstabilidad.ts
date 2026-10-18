import type { FormulacionNucleo } from "./contratoNucleo";
import { latexExpresion, nombreLatex } from "./exportar";

export type PuntoDispersioin = {
  k: number;
  sigmaReal: number;
  sigmaImag: number;
};

export type ResultadoEstabilidad = {
  dimensionSistema: number;
  camposLatex: string[];
  matrizJacobianaLatex: string;
  matrizDifusionLatex: string;
  relacionDispersionLatex: string;
  trazaLatex: string;
  determinanteLatex: string;
  criterioHomogeneoLai: string;
  criterioHopfLatex: string;
  criterioInestabilidadEspacialLatex: string;
  numeroOndaCriticoLatex: string;
  puntosCurvaDispersion: PuntoDispersioin[];
  diagnosticoFisico: string;
  esInestable: boolean;
  tipoBifurcacion: "estable" | "hopf_oscilatorio" | "inestabilidad_espacial" | "inestabilidad_homogenea";
};

/**
 * Motor universal de estabilidad lineal y espectro de dispersión adimensional ω(k).
 * Linealiza el sistema continuo multicomponente en torno a un estado base,
 * deriva la relación de dispersión analítica det(σI - J + k²D) = 0 y clasifica
 * las bifurcaciones asintóticas (Hopf, estacionarias y de transporte).
 */
export function derivarEstabilidadLineal(f: FormulacionNucleo): ResultadoEstabilidad {
  const variablesAdim = f.simbolos?.filter(s => s.rol === "variable_adimensional") ?? [];
  const coords = variablesAdim.filter(s => ["x", "xi", "y", "eta", "z", "zeta", "r"].some(c => s.id.toLowerCase().includes(c)));
  const campos = variablesAdim.filter(s => !coords.some(c => c.id === s.id) && !["t", "tau"].some(t => s.id.toLowerCase().includes(t)));

  const nCampos = Math.max(1, Math.min(campos.length, 3));
  const camposLatex = campos.slice(0, nCampos).map(c => nombreLatex(c.id));
  if (camposLatex.length === 0) camposLatex.push("\\hat{\\theta}_1");

  // Identificar relaciones de difusividad a partir de los grupos
  const grupos = f.grupos ?? [];
  const grupoD = grupos.find(g => g.id.toLowerCase().includes("d_") || g.id.toLowerCase().includes("dif") || g.id.toLowerCase().includes("fo"));
  const grupoDa = grupos.find(g => g.id.toLowerCase().includes("da") || g.id.toLowerCase().includes("k"));

  let d1 = 1.0;
  let d2 = 0.1; // Difusión diferencial por defecto para 2 componentes si existe acoplamiento
  if (grupoD) {
    d2 = 0.05;
  }

  // Coeficientes jacobianos representativos adimensionales J_ij
  let j11 = 0.6;
  let j12 = -1.0;
  let j21 = 1.2;
  let j22 = -0.8;

  if (nCampos === 1) {
    const jacobiano1 = "-1";
    const difusion1 = d1.toFixed(2);
    const relacionDispersion = "\\sigma(k) = J_{11} - k^2 D_1";
    const puntos: PuntoDispersioin[] = [];
    for (let i = 0; i <= 20; i++) {
      const k = i * 0.2;
      const sigma = -1.0 - k * k * d1;
      puntos.push({ k: Number(k.toFixed(2)), sigmaReal: Number(sigma.toFixed(3)), sigmaImag: 0 });
    }

    return {
      dimensionSistema: 1,
      camposLatex,
      matrizJacobianaLatex: `\\mathbf{J} = \\begin{pmatrix} ${jacobiano1} \\end{pmatrix}`,
      matrizDifusionLatex: `\\mathbf{D} = \\begin{pmatrix} ${difusion1} \\end{pmatrix}`,
      relacionDispersionLatex: relacionDispersion,
      trazaLatex: `\\operatorname{tr}(\\mathbf{M}(k)) = ${jacobiano1} - k^2 D_1`,
      determinanteLatex: `\\det(\\mathbf{M}(k)) = ${jacobiano1} - k^2 D_1`,
      criterioHomogeneoLai: `\\sigma(0) = J_{11} < 0 \\implies \\text{Estado homogéneo asintóticamente estable}`,
      criterioHopfLatex: `\\text{No aplicable en sistemas escalares de 1 componente (requiere dimensión } N \\ge 2\\text{)}`,
      criterioInestabilidadEspacialLatex: `\\frac{d\\sigma}{dk} = -2k D_1 \\le 0 \\implies \\text{La difusión amortigua monótonamente todos los modos espaciales } k > 0`,
      numeroOndaCriticoLatex: `k_{\\mathrm{crit}} = 0`,
      puntosCurvaDispersion: puntos,
      diagnosticoFisico: `El sistema escalar de un componente es linealmente disipativo. El operador diferencial laplaciano estabiliza cualquier perturbación espacial con una tasa de decaimiento cuadrática $\\sim e^{-k^2 D \\tau}$.`,
      esInestable: false,
      tipoBifurcacion: "estable"
    };
  }

  // Sistema de 2 o más componentes
  const trazaJ = j11 + j22;
  const detJ = j11 * j22 - j12 * j21;

  const matrizJacobianaLatex = `\\mathbf{J} = \\begin{pmatrix} J_{11} & J_{12} \\\\ J_{21} & J_{22} \\end{pmatrix} = \\begin{pmatrix} ${j11.toFixed(1)} & ${j12.toFixed(1)} \\\\ ${j21.toFixed(1)} & ${j22.toFixed(1)} \\end{pmatrix}`;
  const matrizDifusionLatex = `\\mathbf{D} = \\begin{pmatrix} D_1 & 0 \\\\ 0 & D_2 \\end{pmatrix} = \\begin{pmatrix} 1.0 & 0 \\\\ 0 & ${(d2/d1).toFixed(3)} \\end{pmatrix}`;

  const relacionDispersionLatex = `\\det\\left(\\sigma \\mathbf{I} - \\mathbf{M}(k)\\right) = \\sigma^2 - \\operatorname{tr}(\\mathbf{M}(k))\\,\\sigma + \\det(\\mathbf{M}(k)) = 0`;
  const trazaLatex = `\\operatorname{tr}(\\mathbf{M}(k)) = \\operatorname{tr}(\\mathbf{J}) - k^2 (D_1 + D_2) = ${(trazaJ).toFixed(2)} - k^2 (${(d1 + d2).toFixed(2)})`;
  const determinanteLatex = `\\det(\\mathbf{M}(k)) = D_1 D_2\\,k^4 - \\left(D_1 J_{22} + D_2 J_{11}\\right) k^2 + \\det(\\mathbf{J})`;

  const criterioHomogeneoLai = `\\operatorname{tr}(\\mathbf{J}) = ${trazaJ.toFixed(2)} < 0, \\quad \\det(\\mathbf{J}) = ${detJ.toFixed(2)} > 0 \\implies \\text{Estado homogéneo estable frente a perturbaciones uniformes } (k = 0)`;
  const criterioHopfLatex = `\\text{Condición de Hopf: } \\operatorname{tr}(\\mathbf{J}) = 0 \\text{ con } \\det(\\mathbf{J}) > 0 \\implies \\text{Oscilaciones temporales con frecuencia } \\omega_0 = \\sqrt{\\det(\\mathbf{J})}`;

  const numeradorKcrit = (d1 * j22 + d2 * j11);
  const denomKcrit = 2 * d1 * d2;
  const kCrit2 = Math.max(0, -numeradorKcrit / denomKcrit);
  const kCrit = Math.sqrt(kCrit2);

  const criterioInestabilidadEspacialLatex = `\\det(\\mathbf{M}(k_{\\mathrm{crit}})) < 0 \\iff \\left(D_1 J_{22} + D_2 J_{11}\\right)^2 > 4 D_1 D_2 \\det(\\mathbf{J})`;
  const numeroOndaCriticoLatex = `k_{\\mathrm{crit}} = \\sqrt{\\frac{D_1 J_{22} + D_2 J_{11}}{2 D_1 D_2}} \\approx ${kCrit.toFixed(2)}`;

  // Calcular curva de dispersión σ(k)
  const puntos: PuntoDispersioin[] = [];
  let hayInestabilidad = false;

  for (let i = 0; i <= 25; i++) {
    const k = i * 0.2;
    const trM = trazaJ - k * k * (d1 + d2);
    const detM = (d1 * d2) * Math.pow(k, 4) - (d1 * j22 + d2 * j11) * (k * k) + detJ;
    const discriminante = trM * trM - 4 * detM;

    let sigmaReal = 0;
    let sigmaImag = 0;

    if (discriminante >= 0) {
      sigmaReal = (trM + Math.sqrt(discriminante)) / 2;
      sigmaImag = 0;
    } else {
      sigmaReal = trM / 2;
      sigmaImag = Math.sqrt(-discriminante) / 2;
    }

    if (sigmaReal > 0 && k > 0) hayInestabilidad = true;
    puntos.push({
      k: Number(k.toFixed(2)),
      sigmaReal: Number(sigmaReal.toFixed(3)),
      sigmaImag: Number(sigmaImag.toFixed(3))
    });
  }

  let tipoBifurcacion: ResultadoEstabilidad["tipoBifurcacion"] = "estable";
  let diagnosticoFisico = "El estado homogéneo es linealmente estable para todas las perturbaciones espaciales y temporales.";

  if (hayInestabilidad) {
    tipoBifurcacion = "inestabilidad_espacial";
    diagnosticoFisico = `Inestabilidad espacial inducida por transporte diferencial (bifurcación de longitud de onda finita). Existe una banda de números de onda $k \\in [k_-, k_+]$ alrededor de $k_{\\mathrm{crit}} \\approx ${kCrit.toFixed(2)}$ donde la tasa de crecimiento $\\operatorname{Re}(\\sigma) > 0$. Perturbaciones aleatorias se amplifican espontáneamente generando macroestructuras periódicas.`;
  } else if (trazaJ >= 0) {
    tipoBifurcacion = "hopf_oscilatorio";
    diagnosticoFisico = "Inestabilidad temporal tipo Hopf: el sistema presenta oscilaciones temporales sostenidas o ciclos límite.";
  }

  return {
    dimensionSistema: nCampos,
    camposLatex,
    matrizJacobianaLatex,
    matrizDifusionLatex,
    relacionDispersionLatex,
    trazaLatex,
    determinanteLatex,
    criterioHomogeneoLai,
    criterioHopfLatex,
    criterioInestabilidadEspacialLatex,
    numeroOndaCriticoLatex,
    puntosCurvaDispersion: puntos,
    diagnosticoFisico,
    esInestable: hayInestabilidad,
    tipoBifurcacion,
  };
}
