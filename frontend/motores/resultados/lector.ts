/** Lector estricto del formato común de resultados en el cliente: estructura,
 * identidades y forma de los valores frente a sus ejes. La validez de las
 * unidades la garantiza el servidor (core/resultados/formato.py). */
import type { ConjuntoResultados } from "./contrato";

export class ErrorResultados extends Error { constructor(public ruta: string, motivo: string) { super(`${ruta}: ${motivo}`); } }
const fallo = (ruta: string, motivo: string): never => { throw new ErrorResultados(ruta, motivo); };
type Obj = Record<string, unknown>;

function forma(v: unknown, dims: number[], ruta: string): void {
  if (!dims.length) { if (v !== null && typeof v !== "number") fallo(ruta, "se esperaba un número o null"); return; }
  if (!Array.isArray(v) || v.length !== dims[0]) fallo(ruta, `se esperaban ${dims[0]} valores`);
  (v as unknown[]).forEach((x, i) => forma(x, dims.slice(1), `${ruta}[${i}]`));
}

export function leerResultados(dato: unknown): ConjuntoResultados {
  const r = dato as Obj;
  if (!r || typeof r !== "object" || r.formato !== "rage.resultados" || r.version !== 0) fallo("resultados", "se esperaba rage.resultados v0");
  if (!["resuelto", "parcial", "fallido"].includes(r.estado as string)) fallo("estado", "valor no admitido");
  const largo = new Map<string, number>();
  (r.ejes as Obj[]).forEach((e, i) => {
    if (largo.has(e.id as string)) fallo(`ejes[${i}].id`, "identidad repetida");
    if (!Array.isArray(e.valores) || !e.valores.every(x => typeof x === "number" && Number.isFinite(x))) fallo(`ejes[${i}].valores`, "números finitos");
    largo.set(e.id as string, (e.valores as number[]).length);
  });
  const ids = new Set<string>();
  (r.series as Obj[]).forEach((s, i) => {
    if (ids.has(s.id as string)) fallo(`series[${i}].id`, "identidad repetida");
    ids.add(s.id as string);
    const ejes = s.ejes as string[];
    if (ejes.length > 2) fallo(`series[${i}].ejes`, "0, 1 o 2 ejes");
    ejes.forEach(k => { if (!largo.has(k)) fallo(`series[${i}].ejes`, `eje inexistente ${k}`); });
    forma(s.valores, ejes.map(k => largo.get(k)!), `series[${i}].valores`);
  });
  (r.eventos as Obj[]).forEach((e, i) => { if (!largo.has(e.ejeId as string)) fallo(`eventos[${i}].ejeId`, "eje inexistente"); });
  return r as unknown as ConjuntoResultados;
}
