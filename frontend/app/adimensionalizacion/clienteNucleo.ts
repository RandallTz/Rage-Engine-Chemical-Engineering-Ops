import type { FormulacionNucleo, RespuestaNucleo, SolicitudNucleo } from "./contratoNucleo";
import type { OpcionesEstudio, RespuestaEstudio, SolicitudEstudio } from "./contratoEstudio";
import { leerRespuestaNucleo } from "./lecturaNucleo";
import { leerRespuestaEstudio } from "./lecturaEstudio";
import { leerAuditoria } from "./dimensiones";

const API = (process.env.NEXT_PUBLIC_ADIMENSIONALIZACION_API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
export async function consultarDimensiones(solicitud: SolicitudNucleo, signal: AbortSignal) {
  const r = await fetch(`${API}/api/adimensionalizacion/dimensiones`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(solicitud), signal, cache: "no-store" });
  if (!r.ok) throw new Error(`No se pudo comprobar las dimensiones (HTTP ${r.status}).`);
  const texto = await r.text();
  if (texto.length > 10_000_000) throw new Error("La auditoría supera el límite de presentación.");
  return leerAuditoria(JSON.parse(texto), solicitud);
}
export async function consultarNucleo(solicitud: SolicitudNucleo, signal: AbortSignal): Promise<RespuestaNucleo> {
  const cap = await fetch(`${API}/api/adimensionalizacion/capacidades`, { signal, cache: "no-store" });
  if (!cap.ok) throw new Error(`El servicio de adimensionalización no está disponible (HTTP ${cap.status}).`);
  const capacidades = await cap.json();
  if (capacidades?.formato !== "adimensionalizacion.capacidades" || capacidades.version !== 1 || !Array.isArray(capacidades.operaciones) || !capacidades.operaciones.includes(solicitud.operacion)) throw new Error("El servicio no declara un contrato compatible con esta operación.");
  const r = await fetch(`${API}/api/adimensionalizacion`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(solicitud), signal, cache: "no-store" });
  if (!r.ok) throw new Error(`No se pudo procesar la solicitud (HTTP ${r.status}).`);
  const texto = await r.text();
  if (texto.length > 40_000_000) throw new Error("La respuesta supera el límite de presentación. Reduce el presupuesto y usa continuación.");
  return leerRespuestaNucleo(JSON.parse(texto), solicitud);
}

/** Solicitud `estudiar` que reproduce exactamente una formulación de la búsqueda:
 * la misma solicitud base con los objetivos que aplicó esa formulación. */
export function prepararEstudio(base: SolicitudNucleo, f: FormulacionNucleo, estudio: OpcionesEstudio): SolicitudEstudio {
  const aplicados = (f as FormulacionNucleo & { objetivosAplicados?: string[] }).objetivosAplicados ?? [];
  const { opciones, ...resto } = structuredClone(base);
  const opcionesEstudio = opciones ? Object.fromEntries(Object.entries(opciones).filter(([k]) => ["presentacion", "referencias", "prioridadEscalas"].includes(k))) : undefined;
  return { ...resto, ...(opcionesEstudio && Object.keys(opcionesEstudio).length ? { opciones: opcionesEstudio } : {}), operacion: "estudiar", estudio: { objetivos: aplicados, ...estudio } };
}

export async function consultarEstudio(solicitud: SolicitudEstudio, signal: AbortSignal): Promise<RespuestaEstudio> {
  const cap = await fetch(`${API}/api/adimensionalizacion/capacidades`, { signal, cache: "no-store" });
  if (!cap.ok) throw new Error(`El servicio de adimensionalización no está disponible (HTTP ${cap.status}).`);
  const capacidades = await cap.json();
  if (!Array.isArray(capacidades?.operaciones) || !capacidades.operaciones.includes("estudiar")) throw new Error("El servicio no ofrece todavía la operación estudiar: reinicia el backend con el núcleo actual.");
  const r = await fetch(`${API}/api/adimensionalizacion`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(solicitud), signal, cache: "no-store" });
  if (!r.ok) throw new Error(`No se pudo procesar el estudio (HTTP ${r.status}).`);
  const texto = await r.text();
  if (texto.length > 40_000_000) throw new Error("La respuesta supera el límite de presentación. Reduce nodos o muestras.");
  return leerRespuestaEstudio(JSON.parse(texto), solicitud);
}
