/**
 * Módulo de Puente entre el Motor de Multifísica (/motor) y Adimensionalización.
 * Permite importar hojas de ecuaciones del motor a la capa de análisis dimensional
 * y generar recetas de pre-acondicionamiento canónico para el solucionador numérico.
 */

import type { Documento } from "./contrato";
import type { FormulacionNucleo } from "./contratoNucleo";
import { crearDocumento } from "./documento";
import { leerEcuaciones } from "./entradaEcuaciones";

export type ResumenHojaMotor = {
  id: string;
  nombre: string;
  actualizada: string;
  modo: "1d" | "temporal" | "pendiente";
  componentes: string[];
  ecuacionesTexto: string;
};

const CLAVE_HOJAS_MOTOR = "rage.motor.hojas.v1";

/**
 * Lee de forma segura las hojas de ecuaciones guardadas en el almacenamiento local del motor.
 */
export function listarHojasMotorDisponibles(): ResumenHojaMotor[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(CLAVE_HOJAS_MOTOR);
    if (!raw) return [];
    const datos = JSON.parse(raw);
    if (!Array.isArray(datos)) return [];

    return datos.map((h: any) => {
      const id = String(h.id ?? "");
      const nombre = String(h.nombre ?? "Hoja sin nombre");
      const actualizada = String(h.actualizada ?? "");
      
      const pasoActivo = h.historial?.pasos?.[h.historial?.activo ?? 0];
      const form = pasoActivo?.formulacion;
      const comps = Array.isArray(form?.componentes)
        ? form.componentes.map((c: any) => String(c.simbolo || c.nombre || "A"))
        : ["A"];

      const es1D = form?.coordenadas === "cartesianas" && form?.campo?.sinDifusion === false;
      const modo = es1D ? "1d" : "temporal";

      // Reconstrucción del texto de ecuaciones
      let eqTexto = "";
      if (es1D) {
        eqTexto = comps.map((c: string) => 
          `d(c_${c}, t) + u*d(c_${c}, x) = D_${c}*lap(c_${c}, [x]) - k*c_${c}`
        ).join("\n");
      } else {
        eqTexto = comps.map((c: string) => 
          `d(c_${c}, t) = -k*c_${c}`
        ).join("\n");
      }

      return {
        id,
        nombre,
        actualizada,
        modo,
        componentes: comps,
        ecuacionesTexto: eqTexto
      };
    });
  } catch {
    return [];
  }
}

/**
 * Convierte un resumen de hoja del motor a un Documento de Adimensionalización listo para calcular.
 */
export function importarHojaMotorADocumento(resumen: ResumenHojaMotor): { documento: Documento; borrador: string } {
  const docBase = crearDocumento();
  docBase.nombre = `Adim · ${resumen.nombre}`;

  let borrador = resumen.ecuacionesTexto;
  if (!borrador.trim()) {
    borrador = "d(c_A, t) + u*d(c_A, x) = D*lap(c_A, [x]) - k*c_A";
  }

  try {
    const modelo = leerEcuaciones(borrador, docBase.modelo);
    docBase.modelo = modelo;
  } catch {
    // Si no parsea de inmediato, se conserva el borrador textual
  }

  return {
    documento: docBase,
    borrador
  };
}

/**
 * Genera una receta de pre-acondicionamiento para el solucionador numérico del motor
 * a partir de la formulación canónica adimensional elegida.
 */
export function generarRecetaAcondicionamientoMotor(
  f: FormulacionNucleo,
  nombreModelo: string,
  indiceForma: number
): {
  titulo: string;
  resumen: string;
  escalas: Array<{ variable: string; escala: string; mapaInverso: string }>;
  gruposPi: Array<{ id: string; definicion: string; papel: string }>;
  recomendacionMalla: {
    peCeldaMax: number;
    dxRecomendado: string;
    esquemaEspacial: string;
  };
  recomendacionTemporal: {
    integrador: "RK45 adaptativo" | "Euler implícito con Jacobiano escalado" | "BDF2 / Radau";
    motivo: string;
    cflLimite: string;
  };
} {
  const tienePe = f.grupos.some(g => g.id.toLowerCase().includes("pe") || g.id.toLowerCase().includes("u"));
  const tieneDa = f.grupos.some(g => g.id.toLowerCase().includes("da") || g.id.toLowerCase().includes("k"));

  return {
    titulo: `Receta de Pre-Acondicionamiento para ${nombreModelo} (Forma ${indiceForma + 1})`,
    resumen: `Formulación canónica desacoplada en ${f.grupos.length} grupos adimensionales independientes. Mapea coordenadas dimensionales a dominio unitario [0, 1]x[0, tau_final].`,
    escalas: f.inversa.map(inv => ({
      variable: inv.simboloId,
      escala: `Variable escalada: ${inv.simboloId}`,
      mapaInverso: `${inv.simboloId} = f(xi, tau)`
    })),
    gruposPi: f.grupos.map(g => ({
      id: g.id,
      definicion: `Grupo canónico ${g.id}`,
      papel: g.adimensional ? "Invariante de similitud" : "Escala dimensional residual"
    })),
    recomendacionMalla: {
      peCeldaMax: 2.0,
      dxRecomendado: tienePe ? "Delta xi <= 2 * Pi_dif para suprimir oscilaciones espurias" : "Delta xi <= 0.05",
      esquemaEspacial: tienePe ? "Upwind conservativo de 1er o 2do orden" : "Diferencias centradas de 2do orden"
    },
    recomendacionTemporal: {
      integrador: tieneDa ? "BDF2 / Radau" : "RK45 adaptativo",
      motivo: tieneDa 
        ? "Presencia de número de Damköhler cinético: rigidez temporal potencial" 
        : "Transporte regular dominado por relajación continua",
      cflLimite: "Delta tau <= min(0.4 * Delta xi / u_adim, 0.2 * Delta xi^2 / D_adim)"
    }
  };
}
