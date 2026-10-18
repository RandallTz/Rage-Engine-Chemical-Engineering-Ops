import type { FormulacionNucleo } from "./contratoNucleo";

export type DiagnosticoFormulacion = {
  indice: number;
  etiquetaCorta: string;
  tipoRegimen: "conveccion_dominante" | "difusion_cuasiestacionaria" | "pinns_balanceado" | "cinetica_rapida" | "general";
  colorBadge: string;
  descripcionRecomendacion: string;
  escalasLibres: number;
};

/**
 * Clasifica y califica el acondicionamiento asintótico de cada formulación canónica,
 * permitiendo al investigador navegar intuitivamente entre las hasta 68 formulaciones.
 */
export function clasificarFormulacion(f: FormulacionNucleo, indice: number): DiagnosticoFormulacion {
  const grupos = f.grupos ?? [];
  const escalasLibres = (f.libres ?? []).length;

  const tienePe = grupos.some(g => g.id.toLowerCase().includes("pe") || g.id.toLowerCase().includes("cfl"));
  const tieneDa = grupos.some(g => g.id.toLowerCase().includes("da") || g.id.toLowerCase().includes("reac") || g.id.toLowerCase().includes("k"));
  const tieneFo = grupos.some(g => g.id.toLowerCase().includes("fo") || g.id.toLowerCase().includes("dif"));

  // 1. PINNs balanceada: pocos o cero escalas libres y coeficientes O(1)
  if (escalasLibres === 0 && !tienePe && tieneFo) {
    return {
      indice,
      etiquetaCorta: "🧠 PINNs Balanceada",
      tipoRegimen: "pinns_balanceado",
      colorBadge: "bg-purple-950/80 border-purple-600 text-purple-300",
      descripcionRecomendacion: "Formulación óptima para redes neuronales informadas por la física (PINNs): todas las escalas y derivadas quedan acotadas homogéneamente en O(1), mitigando la explosión o desvanecimiento de gradientes.",
      escalasLibres
    };
  }

  // 2. Convección dominante:
  if (tienePe) {
    return {
      indice,
      etiquetaCorta: "🚀 Advección Rápida",
      tipoRegimen: "conveccion_dominante",
      colorBadge: "bg-amber-950/80 border-amber-600 text-amber-300",
      descripcionRecomendacion: "Formulación canónica para regímenes de transporte advectivo dominante (Péclet elevado). Preserva frentes de concentración delgados con mínima difusión numérica artificial.",
      escalasLibres
    };
  }

  // 3. Cinética rápida:
  if (tieneDa && !tieneFo) {
    return {
      indice,
      etiquetaCorta: "⚡ Cinética Rápida",
      tipoRegimen: "cinetica_rapida",
      colorBadge: "bg-rose-950/80 border-rose-600 text-rose-300",
      descripcionRecomendacion: "Normalizada con respecto a la tasa intrínseca de reacción. Óptima para solvers de DAEs e integración rígida BDF de frentes químicos rápidos.",
      escalasLibres
    };
  }

  // 4. Difusión cuasi-estacionaria:
  if (tieneFo) {
    return {
      indice,
      etiquetaCorta: "🌊 Relajación Difusiva",
      tipoRegimen: "difusion_cuasiestacionaria",
      colorBadge: "bg-sky-950/80 border-sky-600 text-sky-300",
      descripcionRecomendacion: "Escala temporal fijada con el tiempo difusivo característico (Fo = 1). Óptima para estudios de dispersión molecular, conducción de calor y homogenización espacial.",
      escalasLibres
    };
  }

  // 5. General canónica:
  return {
    indice,
    etiquetaCorta: `Forma ${indice + 1}`,
    tipoRegimen: "general",
    colorBadge: "bg-zinc-800 border-zinc-600 text-zinc-300",
    descripcionRecomendacion: "Formulación analíticamente válida derivada del subconjunto regular de menores de la matriz dimensional.",
    escalasLibres
  };
}
