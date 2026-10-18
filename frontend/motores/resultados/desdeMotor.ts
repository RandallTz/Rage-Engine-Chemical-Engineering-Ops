/** Resultado del solver TS del motor (ResultadoMotor) -> formato común. Solo
 * reorganiza: los valores son los mismos. Las dimensiones de las unidades las
 * da el servicio de unidades (POST /unidades/interpretar); el cliente no
 * interpreta unidades. */
import type { ResultadoMotor } from "../../app/motor/modeloNumerico";
import type { ConjuntoResultados, DimensionJSON, Eje, Serie } from "./contrato";

export type Dimensiones = Record<string, { dimension: DimensionJSON; magnitudes: string[] }>;
/** Unidades que hay que interpretar para adaptar este resultado. */
export const unidadesDeMotor = (r: ResultadoMotor) => [...new Set(["s", "m", r.unidadEstado, ...(r.seriesEvaluadas ?? []).map(s => s.unidad)])];

export function resultadosDesdeMotor(r: ResultadoMotor, hojaId: string, dim: Dimensiones): ConjuntoResultados {
  const d = (u: string) => { const x = dim[u]; if (!x) throw new Error(`unidad sin interpretar: ${u}`); return x; };
  const ejes: Eje[] = [{ id: "t", nombre: "tiempo", rol: "tiempo", unidadSI: "s", dimension: d("s").dimension, valores: r.tiempos }];
  const espacial = r.modo === "1d";
  if (espacial) ejes.push({ id: "x", nombre: "posición", rol: "coordenada", unidadSI: "m", dimension: d("m").dimension, valores: r.x });
  const series: Serie[] = r.componentes.map((c, j) => ({
    id: `estado.${c.id}`, nombre: c.nombre, unidadSI: r.unidadEstado, ...d(r.unidadEstado), ejes: espacial ? ["t", "x"] : ["t"],
    valores: espacial ? r.valores.map(fila => [...fila[j]]) : r.valores.map(fila => fila[j][0]), propietarioId: "volumen:dominio", componenteId: c.id,
  }));
  for (const s of r.seriesEvaluadas ?? []) series.push({ id: s.id, nombre: s.nombre, unidadSI: s.unidad, ...d(s.unidad), ejes: ["t"], valores: [...s.valores], propietarioId: s.grupo });
  return {
    formato: "rage.resultados", version: 0, id: hojaId, nombre: "Resultado del motor", modeloId: hojaId,
    estado: r.estado === "resuelto" ? "resuelto" : "parcial",
    procedencia: { motor: r.motor, metodo: r.metodo, firma: r.firma, mensaje: r.mensaje },
    ejes, series, eventos: [],
    verificaciones: r.conservacion.map((v, i) => ({ id: `conservacion.${r.componentes[i]?.id ?? i}`, valor: v, tolerancia: 0, descripcion: "cierre del presupuesto (cambio de cantidad menos frontera y fuentes)" })),
  };
}
