/** Cliente HTTP del modelo común (sin interfaz): POST /modelo/resolver. El cálculo es del servidor. */
import type { ModeloComun } from "./contrato";
import { leerResultados } from "../resultados/lector";
import type { ConjuntoResultados } from "../resultados/contrato";
import { readCompilationReport } from './compilation';

const API = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8004") + "/modelo";

export type TransporteModelo = (modelo: ModeloComun, signal?: AbortSignal) => Promise<unknown>;

export const transporteHTTP: TransporteModelo = async (modelo, signal) => {
  const tiempo = AbortSignal.timeout(600000);
  let r: Response;
  try {
    r = await fetch(`${API}/resolver`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ modelo }), cache: "no-store", signal: signal ? AbortSignal.any([signal, tiempo]) : tiempo });
  } catch (e) {
    if (signal?.aborted) throw new Error("Cálculo cancelado.");
    throw new Error(`Servicio del Engine no disponible (${(e as Error).message}).`);
  }
  const cuerpo = r.headers.get("content-type")?.includes("application/json") ? await r.json() : null;
  if (r.status === 422) {
    const d = (cuerpo as { detail?: { mensaje?: string; ruta?: string } } | null)?.detail;
    throw new Error(d?.mensaje ? `El Engine no puede resolver esta hoja: ${d.mensaje}` : "El Engine rechazó el modelo.");
  }
  if (!r.ok || !cuerpo) throw new Error(`Servicio del Engine no disponible (HTTP ${r.status}).`);
  return cuerpo;
};

export async function resolverModelo(modelo: ModeloComun, signal?: AbortSignal, transporte: TransporteModelo = transporteHTTP): Promise<ConjuntoResultados> {
  return leerResultados(await transporte(modelo, signal));
}

export async function describeCompilation(model: ModeloComun, signal?: AbortSignal) {
  return requestCompilation({ modelo: model }, signal);
}

export async function requestCompilation(body: { modelo: ModeloComun } | { solicitudV2: unknown }, signal?: AbortSignal) {
  const response = await fetch(`${API}/compilation`, { method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body), cache: 'no-store', signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(60000)]) : AbortSignal.timeout(60000) });
  const value = await response.json();
  if (!response.ok) throw new Error(value?.detail?.mensaje ?? 'The selected formulation could not be compiled.');
  return readCompilationReport(value);
}

/** Descripción termodinámica de un modelo (POST /modelo/termodinamica): cierre declarado, fases candidatas
 * de la capa, familia del modelo de estado y relaciones siempre presentes, por volumen. No calcula estados. */
export type RelacionModelo = { id: string; familia: string; propietarioId: string; descripcion: string; supuesta?: boolean };
export type VolumenTermodinamico = {
  id: string; componenteIds: number[]; frontera: string; relaciones: RelacionModelo[];
  cierre: { tipo: "equilibrio"; paquete: { id: string; version: string }; politica: { cantidad: string; cambioInterno: string; tiposPermitidos?: string[] } }
    | { tipo: "supuesto"; supuesto: "fase_no_evaluada" | "u_lineal"; motivo: string };
  modeloEstado: { familia: "ideal" | "actividad" | "iapws95" | "no_envuelto"; modeloLiquido: string | null; nombre: string } | null;
  candidatas: string[] | null; motivoCandidatas?: string;
};
export type DescripcionTermodinamica = { formato: "rage.modelo.termodinamica"; version: 0; volumenes: VolumenTermodinamico[] };

export async function describirTermodinamica(cuerpo: { modelo: ModeloComun } | { solicitudV2: unknown }, signal?: AbortSignal): Promise<DescripcionTermodinamica> {
  const tiempo = AbortSignal.timeout(60000);
  let r: Response;
  try {
    r = await fetch(`${API}/termodinamica`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo), cache: "no-store", signal: signal ? AbortSignal.any([signal, tiempo]) : tiempo });
  } catch (e) {
    throw new Error(`Servicio del Engine no disponible (${(e as Error).message}).`);
  }
  const d = r.headers.get("content-type")?.includes("application/json") ? await r.json() : null;
  if (!r.ok || !d || d.formato !== "rage.modelo.termodinamica" || !Array.isArray(d.volumenes))
    throw new Error(r.status === 422 ? `El Engine no puede describir este modelo: ${d?.detail?.mensaje ?? ""}` : `Servicio del Engine no disponible (HTTP ${r.status}).`);
  return d as DescripcionTermodinamica;
}
