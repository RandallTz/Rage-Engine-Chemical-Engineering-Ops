/** Motor de gráficas, parte pura: (conjunto de resultados, especificación) -> curvas.
 * No sabe de equipos ni de operaciones: trabaja con ejes y series del formato
 * común. No transforma valores; un null queda como hueco. */
import type { ConjuntoResultados, Serie } from "../../motores/resultados/contrato";

export type Especificacion = {
  id: string; titulo?: string;
  /** Abscisa: un eje (tiempo, coordenada, parámetro) o una serie (diagrama de fases). */
  x: { eje: string } | { serie: string };
  /** Ordenadas: series con la MISMA dimensión (una sola escala de unidades por eje). */
  y: string[];
  /** Para series de dos ejes: el eje que se fija y su índice (perfil en un instante, evolución en un punto). */
  fijar?: { eje: string; indice: number };
};
export type Curva = { id: string; nombre: string; x: number[]; y: (number | null)[] };
export type DatosGrafica =
  | { ok: true; titulo: string; ejeX: { etiqueta: string; unidad: string }; ejeY: { etiqueta: string; unidad: string }; curvas: Curva[] }
  | { ok: false; motivo: string };

const igualDim = (a: Serie["dimension"], b: Serie["dimension"]) => JSON.stringify(Object.entries(a).sort()) === JSON.stringify(Object.entries(b).sort());

/** Valores de una serie a lo largo de un eje, fijando el otro si hace falta. */
function corte(c: ConjuntoResultados, s: Serie, ejeLibre: string, fijar?: Especificacion["fijar"]): (number | null)[] | string {
  if (s.ejes.length === 1) return s.ejes[0] === ejeLibre ? (s.valores as (number | null)[]) : `la serie ${s.id} no depende de ${ejeLibre}`;
  if (s.ejes.length !== 2) return `la serie ${s.id} no tiene ejes que graficar`;
  const otro = s.ejes.find(e => e !== ejeLibre);
  if (!s.ejes.includes(ejeLibre) || !otro) return `la serie ${s.id} no depende de ${ejeLibre}`;
  if (!fijar || fijar.eje !== otro) return `la serie ${s.id} depende también de ${otro}: hay que fijarlo`;
  const n = c.ejes.find(e => e.id === otro)!.valores.length;
  const k = Math.max(0, Math.min(n - 1, fijar.indice));
  const m = s.valores as (number | null)[][];
  return s.ejes[0] === otro ? m[k] : m.map(fila => fila[k]);
}

export function datosGrafica(c: ConjuntoResultados, e: Especificacion): DatosGrafica {
  const series = e.y.map(id => c.series.find(s => s.id === id));
  if (!series.length) return { ok: false, motivo: "sin series que graficar" };
  if (series.some(s => !s)) return { ok: false, motivo: `serie inexistente: ${e.y.find((_, i) => !series[i])}` };
  const ys = series as Serie[];
  if (ys.some(s => !igualDim(s.dimension, ys[0].dimension))) return { ok: false, motivo: "las series tienen dimensiones distintas: van en gráficas separadas" };
  let xs: number[], ejeLibre: string | null, etiquetaX: string, unidadX: string;
  if ("eje" in e.x) {
    const eje = c.ejes.find(a => a.id === (e.x as { eje: string }).eje);
    if (!eje) return { ok: false, motivo: `eje inexistente: ${(e.x as { eje: string }).eje}` };
    xs = eje.valores; ejeLibre = eje.id; etiquetaX = eje.nombre; unidadX = eje.unidadSI;
  } else {
    const sx = c.series.find(s => s.id === (e.x as { serie: string }).serie);
    if (!sx || sx.ejes.length !== 1) return { ok: false, motivo: "la abscisa debe ser una serie de un solo eje" };
    if (ys.some(s => s.ejes.length !== 1 || s.ejes[0] !== sx.ejes[0])) return { ok: false, motivo: "las series deben compartir el eje de la abscisa" };
    xs = (sx.valores as (number | null)[]).map(v => v ?? NaN); ejeLibre = sx.ejes[0]; etiquetaX = sx.nombre; unidadX = sx.unidadSI;
  }
  const curvas: Curva[] = [];
  for (const s of ys) {
    const y = corte(c, s, ejeLibre, e.fijar);
    if (typeof y === "string") return { ok: false, motivo: y };
    curvas.push({ id: s.id, nombre: s.nombre, x: xs, y });
  }
  return { ok: true, titulo: e.titulo ?? ys.map(s => s.nombre).join(", "), ejeX: { etiqueta: etiquetaX, unidad: unidadX }, ejeY: { etiqueta: ys.length === 1 ? ys[0].nombre : ys[0].magnitudes[0] ?? "valor", unidad: ys[0].unidadSI }, curvas };
}

/** Especificaciones por omisión para un conjunto: una por grupo de series con la misma dimensión y los mismos ejes. */
export function especificacionesPorOmision(c: ConjuntoResultados, opciones: { ejes?: string[]; instante?: number } = {}): Especificacion[] {
  const grupos = new Map<string, Serie[]>();
  for (const s of c.series) {
    if (opciones.ejes && !s.ejes.every(e => opciones.ejes!.includes(e))) continue;
    if (!s.ejes.length) continue;
    const k = JSON.stringify([s.ejes, Object.entries(s.dimension).sort()]);
    grupos.set(k, [...(grupos.get(k) ?? []), s]);
  }
  return [...grupos.values()].map((ss, i) => {
    const ejes = ss[0].ejes;
    if (ejes.length === 1) return { id: `g${i}`, x: { eje: ejes[0] }, y: ss.map(s => s.id) };
    const tiempo = ejes.find(e => c.ejes.find(a => a.id === e)?.rol === "tiempo") ?? ejes[0];
    const libre = ejes.find(e => e !== tiempo)!;
    return { id: `g${i}`, x: { eje: libre }, y: ss.map(s => s.id), fijar: { eje: tiempo, indice: opciones.instante ?? 0 } };
  });
}
