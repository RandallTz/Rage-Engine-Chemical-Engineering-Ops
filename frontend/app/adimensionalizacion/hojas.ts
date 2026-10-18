import type { Documento } from "./contrato";
import { crearDocumento, leerDocumento, migrarDocumentoV2 } from "./documento";

export const CLAVE_HOJAS = "rage.adimensionalizacion.hojas.v1";
export type Hoja = { id: string; documento: Documento; borrador: string | null; actualizada: string; archivada: boolean };
export type Cuaderno = { formato: "adimensionalizacion.hojas"; version: 1; hojas: Hoja[]; activaId: string };
export function nuevaHoja(documento = crearDocumento()): Hoja {
  return { id: crypto.randomUUID(), documento: migrarDocumentoV2(documento), borrador: null, actualizada: new Date().toISOString(), archivada: false };
}
export function crearCuaderno(documento?: Documento): Cuaderno {
  const hoja = nuevaHoja(documento); return { formato: "adimensionalizacion.hojas", version: 1, hojas: [hoja], activaId: hoja.id };
}
export function leerCuaderno(texto: string): Cuaderno {
  if (new TextEncoder().encode(texto).length > 8_000_000) throw new Error("El cuaderno supera 8 MB.");
  const r = JSON.parse(texto) as Cuaderno;
  if (!r || r.formato !== "adimensionalizacion.hojas" || r.version !== 1 || typeof r.activaId !== "string" || !Array.isArray(r.hojas) || !r.hojas.length || r.hojas.length > 50 || Object.keys(r).some(k => !["formato", "version", "hojas", "activaId"].includes(k))) throw new Error("Formato de cuaderno no admitido (hasta 50 hojas).");
  const ids = new Set<string>();
  for (const h of r.hojas) {
    if (!h || typeof h.id !== "string" || !h.id || ids.has(h.id) || typeof h.archivada !== "boolean" || typeof h.actualizada !== "string" || !Number.isFinite(Date.parse(h.actualizada)) || (h.borrador !== null && (typeof h.borrador !== "string" || h.borrador.length > 20000)) || Object.keys(h).some(k => !["id", "documento", "borrador", "actualizada", "archivada"].includes(k))) throw new Error("La hoja guardada no tiene un formato válido.");
    h.documento = migrarDocumentoV2(leerDocumento(JSON.stringify(h.documento))); ids.add(h.id);
  }
  if (!r.hojas.some(h => h.id === r.activaId && !h.archivada)) throw new Error("La hoja activa no existe o está archivada.");
  return r;
}
export function duplicarHoja(hoja: Hoja): Hoja {
  const doc = structuredClone(hoja.documento);
  doc.id = crypto.randomUUID(); doc.modelo.id = crypto.randomUUID(); doc.nombre = `${doc.nombre} · copia`;
  return { ...nuevaHoja(doc), borrador: hoja.borrador };
}
export function archivarHoja(cuaderno: Cuaderno, id: string): Cuaderno {
  const restantes = cuaderno.hojas.filter(h => h.id !== id && !h.archivada);
  if (!restantes.length) throw new Error("Conserva al menos una hoja abierta; crea otra antes de archivar esta.");
  return { ...cuaderno, activaId: cuaderno.activaId === id ? restantes[0].id : cuaderno.activaId, hojas: cuaderno.hojas.map(h => h.id === id ? { ...h, archivada: true } : h) };
}
