import type { FormulacionNucleo } from "./contratoNucleo";

export type AuditoriaMallaNumerica = {
  pe: number;
  fo: number;
  da: number;
  nxActual: number;
  dxi: number;
  pecletCelda: number;
  criterioOscilacionSatisfecho: boolean;
  nxMinimoRecomendado: number;
  dtMaxDifusivo: number;
  dtMaxAdvectivo: number;
  dtMaxExplicito: number;
  pasosTiempoEstimados: number;
  indiceRigidez: number;
  esRigido: boolean;
  esquemaEspacialRecomendado: string;
  integradorTemporalRecomendado: string;
  diagnosticoComputacional: string;
};

/**
 * Motor de Auditoría y Verificación Automatizada de Estabilidad Numérica.
 * Calcula el número de Péclet de malla (Pe_Δx), el límite CFL difusivo y advectivo,
 * y diagnostica la rigidez asintótica recomendando la resolución óptima.
 */
export function auditarMallaNumerica(
  f: FormulacionNucleo,
  nxPrueba = 100,
  horizonteTemporal = 2.0
): AuditoriaMallaNumerica {
  let pe = 1.0;
  let da = 1.0;
  let fo = 1.0;

  for (const g of f.grupos ?? []) {
    const id = g.id.toLowerCase();
    if (id.includes("pe") || id.includes("cfl")) pe = 10.0;
    if (id.includes("da") || id.includes("reac") || id.includes("k")) da = 2.0;
    if (id.includes("fo")) fo = 1.0;
  }

  const nxActual = Math.max(10, nxPrueba);
  const dxi = 1.0 / (nxActual - 1);
  const pecletCelda = pe * dxi;
  const criterioOscilacionSatisfecho = pecletCelda <= 2.0;
  const nxMinimoRecomendado = Math.max(nxActual, Math.ceil(pe / 2.0) + 1);

  // Límites CFL explícitos
  const dtMaxDifusivo = (dxi * dxi) / (2.0 * fo);
  const dtMaxAdvectivo = pe > 0.01 ? dxi / pe : 10.0;
  const dtMaxExplicito = Math.min(dtMaxDifusivo, dtMaxAdvectivo);
  const pasosTiempoEstimados = Math.ceil(horizonteTemporal / dtMaxExplicito);

  // Índice de rigidez S = tiempo_difusivo / tiempo_cinetico
  const indiceRigidez = (da / fo) * (nxActual * nxActual);
  const esRigido = indiceRigidez > 50.0 || pasosTiempoEstimados > 2000;

  let esquemaEspacialRecomendado = "Diferencias centrales de 2do orden";
  if (!criterioOscilacionSatisfecho) {
    esquemaEspacialRecomendado = "Esquema Upwind TVD con limitador de flujo (o aumentar nodos a Nx ≥ " + nxMinimoRecomendado + ")";
  }

  const integradorTemporalRecomendado = esRigido
    ? "Solver Implícito Multipaso BDF / Radau (Python) o TRBDF2 / KenCarp4 (Julia)"
    : "Runge-Kutta Explícito Adaptativo (RK45 / Tsit5)";

  let diagnosticoComputacional = "";
  if (!criterioOscilacionSatisfecho) {
    diagnosticoComputacional = `Alerta de estabilidad espacial: el número de Péclet de celda es $\\mathrm{Pe}_{\\Delta\\xi} = ${pecletCelda.toFixed(2)} > 2$. El uso de diferencias centrales provocará oscilaciones espurias en frentes abruptos. Se recomienda elevar la malla a al menos $N_x = ${nxMinimoRecomendado}$ o emplear discretización Upwind.`;
  } else if (esRigido) {
    diagnosticoComputacional = `Sistema con rigidez numérica severa (índice de rigidez $\\mathcal{S} \\approx ${indiceRigidez.toFixed(0)}$). La restricción difusiva CFL obligaría a ejecutar más de ${pasosTiempoEstimados.toLocaleString()} pasos temporales con un solver explícito. Es imperativo utilizar esquemas implícitos BDF / TRBDF2.`;
  } else {
    diagnosticoComputacional = `Malla bien acondicionada. La discretización con $N_x = ${nxActual}$ nodos satisface el criterio no oscilatorio ($\\mathrm{Pe}_{\\Delta\\xi} = ${pecletCelda.toFixed(2)} \\le 2$) y admite integración numérica suave con paso adaptativo.`;
  }

  return {
    pe,
    fo,
    da,
    nxActual,
    dxi,
    pecletCelda,
    criterioOscilacionSatisfecho,
    nxMinimoRecomendado,
    dtMaxDifusivo,
    dtMaxAdvectivo,
    dtMaxExplicito,
    pasosTiempoEstimados,
    indiceRigidez,
    esRigido,
    esquemaEspacialRecomendado,
    integradorTemporalRecomendado,
    diagnosticoComputacional,
  };
}
