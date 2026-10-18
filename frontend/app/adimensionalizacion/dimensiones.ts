import type { Dimension, Expresion } from "./contrato";
import type { RespuestaNucleo, SolicitudNucleo } from "./contratoNucleo";
import { igualdadProfunda, leerRespuestaNucleo } from "./lecturaNucleo";

export type AuditoriaDimensional = {
  formato: "adimensionalizacion.dimensiones"; version: 1; analisis: RespuestaNucleo;
  catalogo: { id: string; nombre: string; unidad: string }[];
  cantidades: { id: string; unidadIntroducida: string | null; unidadNormalizada: string | null; magnitudes: string[] }[];
  ecuaciones: { id: string; dimension: Dimension; terminos: {
    ruta: string; lado: "izquierda" | "derecha"; expresion: Expresion; dimension: Dimension;
    estado: "compatible" | "incompatible" | "pendiente" | "cero";
    operadores: { tipo: string; respecto?: string; orden?: number; coordenadas?: string[]; nombre?: string }[];
  }[] }[];
};

/** Vincula también cada término de la auditoría al AST solicitado. No hace álgebra. */
export function leerAuditoria(dato: unknown, solicitud: SolicitudNucleo): AuditoriaDimensional {
  const fallo = (): never => { throw new Error("El servicio devolvió una auditoría dimensional inválida o de otro modelo."); };
  if (!dato || typeof dato !== "object") return fallo();
  const r = dato as AuditoriaDimensional;
  if (r.formato !== "adimensionalizacion.dimensiones" || r.version !== 1 || !Array.isArray(r.catalogo) || !Array.isArray(r.cantidades) || !Array.isArray(r.ecuaciones)) return fallo();
  leerRespuestaNucleo(r.analisis, solicitud);
  const dimension = (d: Dimension) => d === null || (typeof d === "object" && !Array.isArray(d) && Object.entries(d).every(([k, q]) => /^[A-Za-z][A-Za-z0-9_]*$/.test(k) && q && Number.isSafeInteger(q.n) && Number.isSafeInteger(q.d) && q.d > 0));
  if (r.catalogo.length > 100 || r.catalogo.some(c => !c || typeof c.id !== "string" || typeof c.nombre !== "string" || typeof c.unidad !== "string") || new Set(r.catalogo.map(c => c.id)).size !== r.catalogo.length) return fallo();
  const ids = new Set(solicitud.documento.modelo.simbolos.map(s => s.id)), tipos = new Set(r.catalogo.map(c => c.id));
  const completa = !!r.analisis.dimensional && !!r.analisis.vinculo;
  if (r.cantidades.length !== (completa ? ids.size : 0)) return fallo();
  if (new Set(r.cantidades.map(c => c.id)).size !== r.cantidades.length) return fallo();
  if (r.cantidades.some(c => !ids.has(c.id) || !Array.isArray(c.magnitudes) || c.magnitudes.some(t => !tipos.has(t)) || (c.unidadNormalizada !== null && typeof c.unidadNormalizada !== "string") || c.unidadIntroducida !== solicitud.documento.modelo.simbolos.find(s => s.id === c.id)?.unidad)) return fallo();
  const esperadas = solicitud.documento.modelo.ecuaciones;
  if (r.ecuaciones.length !== (completa ? esperadas.length : 0)) return fallo();
  for (const [i, eq] of r.ecuaciones.entries()) {
    if (!eq || eq.id !== esperadas[i].id || !dimension(eq.dimension) || !Array.isArray(eq.terminos)) return fallo();
    const terminos: { ruta: string; expresion: Expresion; lado: string }[] = [];
    function visitar(e: Expresion, ruta: string, lado: string) {
      if (e.tipo === "suma") e.argumentos.forEach((a, j) => visitar(a, `${ruta}.argumentos[${j}]`, lado));
      else terminos.push({ ruta, expresion: e, lado });
    }
    visitar(esperadas[i].izquierda, `ecuaciones[${i}].izquierda`, "izquierda");
    visitar(esperadas[i].derecha, `ecuaciones[${i}].derecha`, "derecha");
    if (terminos.length !== eq.terminos.length) return fallo();
    for (const [j, t] of eq.terminos.entries()) {
      if (!t || t.ruta !== terminos[j].ruta || t.lado !== terminos[j].lado || !igualdadProfunda(t.expresion, terminos[j].expresion) || !dimension(t.dimension) || !["compatible", "incompatible", "pendiente", "cero"].includes(t.estado) || !Array.isArray(t.operadores)) return fallo();
      if (t.operadores.some(o => !o || !["derivada", "gradiente", "divergencia", "laplaciano", "funcion", "llamada"].includes(o.tipo) || (o.respecto !== undefined && !ids.has(o.respecto)) || (o.coordenadas !== undefined && (!Array.isArray(o.coordenadas) || o.coordenadas.some(c => !ids.has(c)))))) return fallo();
    }
  }
  return r;
}
