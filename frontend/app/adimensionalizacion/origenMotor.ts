/** Vínculo local entre una hoja de adimensionalización y la hoja del motor de
 * la que se importó. Solo vive en este navegador; el motor no lo conoce. */
import type { ImportacionMotor, OrigenMotor } from "./desdeMotor";
import { VERSION_IMPORTACION } from "./desdeMotor";

const clave = (documentoId: string) => `adim.motor.${documentoId}`;

export function guardarImportacion(imp: ImportacionMotor) {
  try {
    localStorage.setItem(`adim.valores.${imp.documento.id}`, JSON.stringify(imp.valores));
    localStorage.setItem(clave(imp.documento.id), JSON.stringify(imp.origen));
  } catch { /* sin almacenamiento: la hoja se importa sin valores precargados */ }
}

export function leerOrigen(documentoId: string): OrigenMotor | null {
  try {
    const t = typeof window === "undefined" ? null : localStorage.getItem(clave(documentoId));
    if (!t) return null;
    const o = JSON.parse(t) as OrigenMotor;
    return o && o.version === VERSION_IMPORTACION && typeof o.hojaId === "string" && Array.isArray(o.componentes) ? o : null;
  } catch { return null; }
}

/** Una copia de una hoja importada sigue viniendo de la misma hoja del Engine. */
export function copiarOrigen(deDocumentoId: string, aDocumentoId: string) {
  try {
    for (const prefijo of ["adim.motor.", "adim.valores."]) {
      const t = localStorage.getItem(prefijo + deDocumentoId);
      if (t !== null) localStorage.setItem(prefijo + aDocumentoId, t);
    }
  } catch { /* sin almacenamiento */ }
}
