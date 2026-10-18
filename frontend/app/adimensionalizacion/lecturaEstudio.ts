/** Lector estricto de la respuesta de `estudiar`: comprueba identidad,
 * vigencia y forma antes de presentar. No recalcula nada. */
import { igualdadProfunda } from "./lecturaNucleo";
import type { RespuestaEstudio, SolicitudEstudio } from "./contratoEstudio";
import { ESTUDIOS } from "./contratoEstudio";

type Obj = Record<string, unknown>;
const fallo = (ruta: string, mensaje: string): never => { throw new Error(`${ruta}: ${mensaje}`); };
const obj = (v: unknown, p: string): Obj => v !== null && typeof v === "object" && !Array.isArray(v) ? v as Obj : fallo(p, "objeto requerido");
const arr = (v: unknown, p: string): unknown[] => Array.isArray(v) ? v : fallo(p, "lista requerida");
const txt = (v: unknown, p: string): string => typeof v === "string" ? v : fallo(p, "texto requerido");
const num = (v: unknown, p: string, nulo = false): number | null => (nulo && v === null) ? null : typeof v === "number" && Number.isFinite(v) ? v : fallo(p, "número finito requerido");
const opcion = (v: unknown, p: string, valores: unknown[]) => { if (!valores.includes(v)) fallo(p, "valor no admitido"); };

const ESTADOS = ["calculado", "requiere_datos", "no_aplicable", "no_soportado", "no_convergente", "rechazado"];
const CLAVES = ["formato", "version", "operacion", "estado", "nucleo", "vinculo", "diagnosticos", "dimensional", "terminos", "formaBase", "formulacion", "estudio"];

function matriz(v: unknown, p: string, filas: number, columnas: number | null) {
  const m = arr(v, p);
  if (m.length !== filas) fallo(p, "número de filas inconsistente");
  m.forEach((f, i) => { const fila = arr(f, `${p}[${i}]`); if (columnas !== null && fila.length !== columnas) fallo(p, "número de columnas inconsistente"); fila.forEach((x, j) => num(x, `${p}[${i}][${j}]`)); });
}

export function leerRespuestaEstudio(dato: unknown, solicitud: SolicitudEstudio): RespuestaEstudio {
  const r = obj(dato, "respuesta");
  for (const k of Object.keys(r)) if (!CLAVES.includes(k)) fallo("respuesta", `campo desconocido ${k}`);
  opcion(r.formato, "formato", ["adimensionalizacion.resultado"]);
  opcion(r.version, "version", [1]);
  opcion(r.operacion, "operacion", ["estudiar"]);
  opcion(r.estado, "estado", ["correcto", "rechazado", "no_soportado", "requiere_datos"]);
  txt(r.nucleo, "nucleo");
  arr(r.diagnosticos, "diagnosticos").forEach((d, i) => { const x = obj(d, `diagnosticos[${i}]`); txt(x.ruta, "ruta"); txt(x.codigo, "codigo"); txt(x.mensaje, "mensaje"); opcion(x.severidad, "severidad", ["error", "aviso"]); });
  if (r.vinculo !== null) {
    const v = obj(r.vinculo, "vinculo");
    const doc = solicitud.documento;
    if (v.documentoId !== doc.id || v.modeloId !== doc.modelo.id || v.modeloRevision !== doc.modelo.revision) fallo("vinculo", "la respuesta corresponde a otro documento o revisión");
    if (!igualdadProfunda(v.estudio, solicitud.estudio)) fallo("vinculo.estudio", "la respuesta corresponde a otra solicitud de estudio");
    txt(v.firma, "vinculo.firma");
  } else if (r.estado === "correcto") fallo("vinculo", "un resultado correcto debe estar vinculado");
  if (r.estado !== "correcto") {
    if (r.formulacion !== undefined || r.estudio !== undefined) fallo("respuesta", "un fallo no puede traer resultados");
    return r as unknown as RespuestaEstudio;
  }
  const f = obj(r.formulacion, "formulacion");
  for (const k of ["ecuaciones", "grupos", "escalas", "simbolos", "condiciones", "dominios", "libres", "desarrollo"]) arr(f[k], `formulacion.${k}`);
  obj(f.equivalencia, "formulacion.equivalencia");
  const e = obj(r.estudio, "estudio");
  for (const [k, s] of Object.entries(e)) {
    if (!(ESTUDIOS as string[]).includes(k)) fallo("estudio", `análisis desconocido ${k}`);
    const x = obj(s, `estudio.${k}`);
    opcion(x.estado, `estudio.${k}.estado`, ESTADOS);
    txt(x.motivo, `estudio.${k}.motivo`);
  }
  const pedidos = solicitud.estudio.analisis ?? ESTUDIOS;
  for (const k of pedidos) if (!Object.hasOwn(e, k)) fallo("estudio", `falta el análisis pedido ${k}`);
  const sim = e.simulacion as Obj | undefined;
  if (sim && sim.estado === "calculado") {
    const tiempos = arr(sim.tiempos, "simulacion.tiempos"); tiempos.forEach((t, i) => num(t, `simulacion.tiempos[${i}]`));
    const xi = sim.xi === null ? null : arr(sim.xi, "simulacion.xi");
    xi?.forEach((t, i) => num(t, `simulacion.xi[${i}]`));
    for (const [c, m] of Object.entries(obj(sim.campos, "simulacion.campos"))) matriz(m, `simulacion.campos.${c}`, tiempos.length, xi ? xi.length : 1);
  }
  const est = e.estabilidad as Obj | undefined;
  if (est && est.estado === "calculado") arr(est.estados, "estabilidad.estados").forEach((s, i) => { const x = obj(s, `estabilidad.estados[${i}]`); obj(x.u, "u"); arr(x.autovalores, "autovalores"); });
  const val = e.valores as Obj | undefined;
  if (val && Array.isArray(val.grupos)) val.grupos.forEach((g, i) => num(obj(g, `valores.grupos[${i}]`).valor, `valores.grupos[${i}].valor`, true));
  return r as unknown as RespuestaEstudio;
}
