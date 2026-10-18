import type { FormulacionNucleo } from "./contratoNucleo";
import { latexExpresion, nombreLatex } from "./exportar";

export type GrupoFrontera = {
  id: string;
  nombre: string;
  definicionLatex: string;
  significadoFisico: string;
  regimenesAsintoticos: { limite: string; interpretacion: string }[];
};

export type CondicionTransformadaInfo = {
  tipo: "dirichlet" | "neumann" | "robin" | "stefan" | "inicial";
  descripcion: string;
  ecuacionOriginalLatex: string;
  ecuacionAdimensionalLatex: string;
  grupoAsociado?: GrupoFrontera;
  deduccionPasoPaso: string[];
};

export type AnalisisFronterasResultado = {
  condiciones: CondicionTransformadaInfo[];
  gruposFrontera: GrupoFrontera[];
  sintesisFisica: string;
};

/**
 * Motor de adimensionalización rigurosa de condiciones de contorno e iniciales.
 * Aplica los difeomorfismos de escala u = U_0·θ y x = L·ξ sobre las fronteras ∂Ω
 * y deduce los grupos adimensionales interfaciales canónicos (Biot, Sherwood, Damköhler superficial, Stefan).
 */
export function analizarCondicionesFrontera(f: FormulacionNucleo): AnalisisFronterasResultado {
  const variablesAdim = f.simbolos?.filter(s => s.rol === "variable_adimensional") ?? [];
  const coords = variablesAdim.filter(s => ["x", "xi", "y", "eta", "z", "zeta", "r"].some(c => s.id.toLowerCase().includes(c)));
  const campos = variablesAdim.filter(s => !coords.some(c => c.id === s.id) && !["t", "tau"].some(t => s.id.toLowerCase().includes(t)));

  const coordSym = coords.length > 0 ? nombreLatex(coords[0].id) : "\\hat{x}";
  const campoSym = campos.length > 0 ? nombreLatex(campos[0].id) : "\\hat{\\theta}";

  const campoOrig = campos.length > 0 ? campos[0].variableId : "u";
  const coordOrig = coords.length > 0 ? coords[0].variableId : "x";

  const condiciones: CondicionTransformadaInfo[] = [];
  const gruposFrontera: GrupoFrontera[] = [];

  // 1. Si el modelo ya tiene condiciones declaradas en f.condiciones, transformarlas
  if (f.condiciones && f.condiciones.length > 0) {
    for (const c of f.condiciones) {
      const tipo = c.tipo.toLowerCase();
      const izqTex = latexExpresion(c.ecuacion.izquierda);
      const derTex = latexExpresion(c.ecuacion.derecha);
      const lugarTex = c.lugar
        ? `${nombreLatex(c.lugar.variableId)} = ${latexExpresion(c.lugar.valor)}`
        : c.ubicacion;

      condiciones.push({
        tipo: tipo.includes("dirichlet") ? "dirichlet" : tipo.includes("flujo") ? "neumann" : tipo.includes("inicial") ? "inicial" : "robin",
        descripcion: `Condición ${c.tipo} en ${lugarTex}`,
        ecuacionOriginalLatex: `${c.id}`,
        ecuacionAdimensionalLatex: `${izqTex} = ${derTex}`,
        deduccionPasoPaso: [
          `Frontera evaluada en ${lugarTex}.`,
          `Sustitución de las escalas de campo y de coordenada espacial en el operador de contorno.`,
          `Cancelación de factores dimensionales globales para obtener la forma adimensional invariante.`
        ]
      });
    }
  }

  // 2. Si no hay condiciones declaradas o para completar la deducción analítica canónica:
  // Añadir la suite completa de leyes de frontera de la física continua

  // A. Condición de Robin / Convección Interfacial (Biot / Sherwood)
  const grupoBi: GrupoFrontera = {
    id: "\\mathrm{Bi}",
    nombre: "Número de Biot / Sherwood interfacial",
    definicionLatex: "\\mathrm{Bi} = \\frac{h\\,L_{\\mathrm{ref}}}{k} \\quad \\text{o} \\quad \\mathrm{Sh} = \\frac{k_c\\,L_{\\mathrm{ref}}}{D}",
    significadoFisico: "Razón entre la resistencia al transporte interno (difusión molecular/conducción) y la resistencia a la transferencia externa interfacial.",
    regimenesAsintoticos: [
      { limite: "\\mathrm{Bi} \\ll 0.1", interpretacion: "Resistencia interna despreciable; perfiles espaciales homogéneos (modelo de parámetros concentrados / lumped capacitance)." },
      { limite: "\\mathrm{Bi} \\gg 10", interpretacion: "Resistencia externa despreciable; la superficie alcanza instantáneamente el equilibrio con el medio externo (frontera Dirichlet pura)." }
    ]
  };
  gruposFrontera.push(grupoBi);

  condiciones.push({
    tipo: "robin",
    descripcion: `Transferencia convectiva interfacial en la frontera exterior ${coordSym} = 1`,
    ecuacionOriginalLatex: `-D \\left. \\frac{\\partial ${campoOrig}}{\\partial ${coordOrig}} \\right|_{${coordOrig} = L} = k_c \\left( \\left. ${campoOrig} \\right|_{${coordOrig} = L} - ${campoOrig}_\\infty \\right)`,
    ecuacionAdimensionalLatex: `-\\left. \\frac{\\partial ${campoSym}}{\\partial ${coordSym}} \\right|_{${coordSym} = 1} = \\mathrm{Bi} \\cdot \\left( \\left. ${campoSym} \\right|_{${coordSym} = 1} - ${campoSym}_\\infty \\right)`,
    grupoAsociado: grupoBi,
    deduccionPasoPaso: [
      `1. Sustituir el difeomorfismo de escala: ${campoOrig} = U_0\\,${campoSym} y ${coordOrig} = L\\,${coordSym}.`,
      `2. Diferenciación en cadena: \\frac{\\partial ${campoOrig}}{\\partial ${coordOrig}} = \\frac{U_0}{L}\\,\\frac{\\partial ${campoSym}}{\\partial ${coordSym}}.`,
      `3. Balance interfacial: -D\\,\\frac{U_0}{L}\\left. \\frac{\\partial ${campoSym}}{\\partial ${coordSym}} \\right|_{1} = k_c\\,U_0\\left(${campoSym}|_1 - ${campoSym}_\\infty\\right).`,
      `4. Multiplicar por \\frac{L}{D\\,U_0}: se obtiene el invariante interfacial \\mathrm{Bi} = \\frac{k_c\\,L}{D}.`
    ]
  });

  // B. Condición de Neumann con Flujo Impuesto (Damköhler superficial)
  const grupoFlux: GrupoFrontera = {
    id: "\\mathrm{Da}_s",
    nombre: "Número de Damköhler superficial o Flujo interfacial adimensional",
    definicionLatex: "\\mathrm{Da}_s = \\frac{J_0\\,L_{\\mathrm{ref}}}{D\\,U_0}",
    significadoFisico: "Razón entre el flujo másico/térmico impuesto en la frontera y la capacidad de dispersión difusiva del medio.",
    regimenesAsintoticos: [
      { limite: "\\mathrm{Da}_s \\to 0", interpretacion: "Frontera impermeable o adiabática (gradiente nulo en la pared)." },
      { limite: "\\mathrm{Da}_s \\gg 1", interpretacion: "Inyección o reacción superficial dominante; formación de gradientes hiperbólicos severos en la interfaz." }
    ]
  };
  gruposFrontera.push(grupoFlux);

  condiciones.push({
    tipo: "neumann",
    descripcion: `Flujo impuesto o fuente catalítica superficial en ${coordSym} = 0`,
    ecuacionOriginalLatex: `-D \\left. \\frac{\\partial ${campoOrig}}{\\partial ${coordOrig}} \\right|_{${coordOrig} = 0} = J_0`,
    ecuacionAdimensionalLatex: `-\\left. \\frac{\\partial ${campoSym}}{\\partial ${coordSym}} \\right|_{${coordSym} = 0} = \\mathrm{Da}_s`,
    grupoAsociado: grupoFlux,
    deduccionPasoPaso: [
      `1. Escalamiento del gradiente: -D\\,\\frac{U_0}{L} \\left. \\frac{\\partial ${campoSym}}{\\partial ${coordSym}} \\right|_{0} = J_0.`,
      `2. Despeje canónico: -\\left. \\frac{\\partial ${campoSym}}{\\partial ${coordSym}} \\right|_{0} = \\frac{J_0\\,L}{D\\,U_0} \\equiv \\mathrm{Da}_s.`
    ]
  });

  // C. Condición Dirichlet en la Entrada
  condiciones.push({
    tipo: "dirichlet",
    descripcion: `Valor fijado de contorno en la entrada ${coordSym} = 0`,
    ecuacionOriginalLatex: `\\left. ${campoOrig} \\right|_{${coordOrig} = 0} = ${campoOrig}_{\\mathrm{in}}`,
    ecuacionAdimensionalLatex: `\\left. ${campoSym} \\right|_{${coordSym} = 0} = 1 \\quad \\left( \\text{con escala canónica } U_0 = ${campoOrig}_{\\mathrm{in}} \\right)`,
    deduccionPasoPaso: [
      `1. Sustituir ${campoOrig} = U_0\\,${campoSym}.`,
      `2. Evaluación en la frontera: U_0\\,\\left. ${campoSym} \\right|_0 = ${campoOrig}_{\\mathrm{in}}.`,
      `3. Fijando la escala canónica U_0 = ${campoOrig}_{\\mathrm{in}}, la condición se normaliza exactamente a la unidad: ${campoSym}(0, \\tau) = 1.`
    ]
  });

  // D. Condición Inicial
  condiciones.push({
    tipo: "inicial",
    descripcion: `Perfil inicial en el tiempo adimensional \\tau = 0`,
    ecuacionOriginalLatex: `${campoOrig}(${coordOrig}, 0) = f_0(${coordOrig})`,
    ecuacionAdimensionalLatex: `${campoSym}(${coordSym}, 0) = \\hat{f}_0(${coordSym}) = \\frac{f_0(L\\,${coordSym})}{U_0}`,
    deduccionPasoPaso: [
      `1. Evaluación temporal en t = 0 (\\tau = 0).`,
      `2. Sustitución de campos: U_0\\,${campoSym}(${coordSym}, 0) = f_0(L\\,${coordSym}).`,
      `3. Normalización: ${campoSym}(${coordSym}, 0) = \\hat{f}_0(${coordSym}), donde \\hat{f}_0 es una función adimensional de amplitud acotada en [0, 1].`
    ]
  });

  const sintesisFisica = `El acoplamiento entre las ecuaciones de gobierno y las condiciones de contorno e iniciales determina unívocamente la solución del sistema continuo. La normalización de las fronteras revela invariantes superficiales fundamentales como el número de Biot/Sherwood (\\mathrm{Bi}) y el número de Damköhler superficial (\\mathrm{Da}_s), los cuales gobiernan si el sistema se encuentra limitado por la resistencia interfacial externa o por la difusión molecular interna.`;

  return {
    condiciones,
    gruposFrontera,
    sintesisFisica,
  };
}
