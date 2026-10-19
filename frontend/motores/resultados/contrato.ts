/** Formato común de resultados v0 (docs/FORMATO_RESULTADOS.md). Lo publica todo
 * motor de cálculo y lo consume el motor de gráficas. Genérico: ejes y series
 * con unidad SI y dimensión exacta; ningún campo sabe de equipos u operaciones. */
export type DimensionJSON = Record<string, { n: number; d: number }>;
export type Eje = { id: string; nombre: string; rol: "tiempo" | "coordenada" | "parametro" | "otro"; unidadSI: string; dimension: DimensionJSON; valores: number[] };
/** valores: número (sin ejes), lista (un eje) o lista de listas (dos ejes; el primero es el índice exterior). null = no definido. */
export type Valores = number | null | (number | null)[] | (number | null)[][];
export type Serie = {
  id: string; nombre: string; unidadSI: string; dimension: DimensionJSON; magnitudes: string[]; ejes: string[]; valores: Valores;
  propietarioId?: string; componenteId?: number; faseId?: string;
};
export type Evento = { codigo: string; ejeId: string; valor: number; descripcion: string; propietarioId?: string };
export type ConjuntoResultados = {
  formato: "rage.resultados"; version: 0; id: string; nombre: string; modeloId: string | null;
  estado: "resuelto" | "parcial" | "fallido";
  procedencia: { motor: string; metodo: string | null; firma: string | null; mensaje?: string; pasos?: number; rechazos?: number };
  ejes: Eje[]; series: Serie[]; eventos: Evento[];
  verificaciones: { id: string; valor: number; tolerancia: number; descripcion: string }[];
};
