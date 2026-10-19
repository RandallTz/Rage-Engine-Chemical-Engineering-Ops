import type { Documento } from "./contrato";
import { crearDocumento, leerDocumento, migrarDocumentoV2 } from "./documento";

export const CLAVE_HOJAS = "rage.adimensionalizacion.hojas.v1";
/** `retirada`: un documento escrito directamente, sin derivarse de una hoja del Engine. La adimensionalización
 * solo trabaja sobre ecuaciones derivadas de las fundamentales en una hoja del Engine (ARQUITECTURA_MOTOR.md §2,
 * principio 10); el documento retirado se conserva para exportarlo, pero no se abre para trabajar. */
export type Hoja = { id: string; documento: Documento; borrador: string | null; actualizada: string; archivada: boolean; retirada?: { fecha: string; motivo: string } };
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
  if (!r || r.formato !== "adimensionalizacion.hojas" || r.version !== 1 || typeof r.activaId !== "string" || !Array.isArray(r.hojas) || r.hojas.length > 50 || Object.keys(r).some(k => !["formato", "version", "hojas", "activaId"].includes(k))) throw new Error("Formato de cuaderno no admitido (hasta 50 hojas).");
  const ids = new Set<string>();
  for (const h of r.hojas) {
    if (!h || typeof h.id !== "string" || !h.id || ids.has(h.id) || typeof h.archivada !== "boolean" || typeof h.actualizada !== "string" || !Number.isFinite(Date.parse(h.actualizada)) || (h.borrador !== null && (typeof h.borrador !== "string" || h.borrador.length > 20000)) || Object.keys(h).some(k => !["id", "documento", "borrador", "actualizada", "archivada", "retirada"].includes(k)) || (h.retirada !== undefined && (typeof h.retirada?.motivo !== "string" || typeof h.retirada?.fecha !== "string"))) throw new Error("La hoja guardada no tiene un formato válido.");
    h.documento = migrarDocumentoV2(leerDocumento(JSON.stringify(h.documento))); ids.add(h.id);
  }
  // Sin hojas de trabajo (todas archivadas o retiradas) la activa queda vacía; si se declara, debe existir y estar abierta.
  if (r.activaId !== "" && !r.hojas.some(h => h.id === r.activaId && !h.archivada && !h.retirada)) throw new Error("La hoja activa no existe, está archivada o está retirada.");
  if (r.activaId === "" && r.hojas.some(h => !h.archivada && !h.retirada)) throw new Error("Hay hojas abiertas y ninguna activa.");
  return r;
}
export function duplicarHoja(hoja: Hoja): Hoja {
  const doc = structuredClone(hoja.documento);
  doc.id = crypto.randomUUID(); doc.modelo.id = crypto.randomUUID(); doc.nombre = `${doc.nombre} · copia`;
  return { ...nuevaHoja(doc), borrador: hoja.borrador };
}
export function archivarHoja(cuaderno: Cuaderno, id: string): Cuaderno {
  const restantes = cuaderno.hojas.filter(h => h.id !== id && !h.archivada && !h.retirada);
  return { ...cuaderno, activaId: cuaderno.activaId === id ? restantes[0]?.id ?? "" : cuaderno.activaId, hojas: cuaderno.hojas.map(h => h.id === id ? { ...h, archivada: true } : h) };
}
export const MOTIVO_RETIRO = "Escrito directamente, sin derivarse de una hoja del Engine. La adimensionalización trabaja solo sobre ecuaciones derivadas de las fundamentales en una hoja del Engine; deriva el modelo allí e impórtalo.";
/** Retira los documentos que no vienen de una hoja del Engine (conservándolos para exportar). Idempotente. */
export function retirarEscritas(cuaderno: Cuaderno, derivada: (h: Hoja) => boolean, fecha = new Date().toISOString()): Cuaderno {
  const hojas = cuaderno.hojas.map(h => h.retirada || derivada(h) ? h : { ...h, retirada: { fecha, motivo: MOTIVO_RETIRO } });
  const activa = hojas.find(h => h.id === cuaderno.activaId && !h.archivada && !h.retirada) ?? hojas.find(h => !h.archivada && !h.retirada);
  return { ...cuaderno, hojas, activaId: activa?.id ?? "" };
}
export const cuadernoVacio = (): Cuaderno => ({ formato: "adimensionalizacion.hojas", version: 1, hojas: [], activaId: "" });
