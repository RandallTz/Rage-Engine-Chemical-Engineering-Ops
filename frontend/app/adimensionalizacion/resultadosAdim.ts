/** Último cálculo de cada hoja, como guarda el motor sus resultados: en
 * IndexedDB de este navegador. Solo se reutiliza si el documento y el texto
 * de las ecuaciones son idénticos a los del cálculo, y si cada respuesta
 * vuelve a pasar el lector estricto. */
import type { Documento } from "./contrato";
import type { RespuestaNucleo, SolicitudNucleo } from "./contratoNucleo";
import { leerRespuestaNucleo } from "./lecturaNucleo";

/** Identidad del cálculo: el documento salvo su nombre (renombrar no invalida). */
export const claveCalculo = (d: Documento) => JSON.stringify({ ...d, nombre: "" });
export type CalculoGuardado = { claveDocumento: string; fuente: string; documento: Documento; paginas: { solicitud: SolicitudNucleo; respuesta: RespuestaNucleo }[] };

function abrir(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const r = indexedDB.open("rage-adimensionalizacion-resultados", 1);
    r.onupgradeneeded = () => r.result.createObjectStore("calculos");
    r.onsuccess = () => resolve(r.result);
    r.onerror = () => reject(new Error("No se pudo abrir el almacenamiento de resultados."));
  });
}

export async function guardarCalculo(documentoId: string, c: CalculoGuardado) {
  const db = await abrir();
  try {
    await new Promise<void>((resolve, reject) => {
      const t = db.transaction("calculos", "readwrite");
      t.objectStore("calculos").put(c, documentoId);
      t.oncomplete = () => resolve();
      t.onerror = () => reject(new Error("No se pudo guardar el resultado."));
    });
  } finally { db.close(); }
}

export async function leerCalculo(documento: Documento, fuente: string): Promise<CalculoGuardado | null> {
  const db = await abrir();
  try {
    const c = await new Promise<CalculoGuardado | undefined>((resolve, reject) => {
      const r = db.transaction("calculos").objectStore("calculos").get(documento.id);
      r.onsuccess = () => resolve(r.result as CalculoGuardado | undefined);
      r.onerror = () => reject(new Error("No se pudo leer el resultado."));
    });
    if (!c || c.claveDocumento !== claveCalculo(documento) || c.fuente !== fuente || !c.paginas?.length) return null;
    return { ...c, paginas: c.paginas.map(p => ({ solicitud: p.solicitud, respuesta: leerRespuestaNucleo(p.respuesta, p.solicitud) })) };
  } catch { return null; } finally { db.close(); }
}
