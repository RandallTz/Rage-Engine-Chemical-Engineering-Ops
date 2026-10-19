/** Hoja de materia del motor TS <-> modelo común (contrato §3, tercer caso).
 *
 * Solo lee la hoja: usa funciones puras del motor (análisis de campos) y el
 * importador de la adimensionalización para las ecuaciones ejecutadas. Ida y
 * vuelta exactas para la formulación activa, sus componentes y su
 * configuración. El solver de materia del motor no evalúa el estado: el
 * volumen declara ese hecho como supuesto explícito (la termodinámica
 * siempre presente). */
import type { HojaMotor } from "../../app/motor/hojasMotor";
import type { FormulacionMateria } from "../../app/motor/recorridoMateria";
import { analizarMotor, esVolumetrico } from "../../app/motor/modeloNumerico";
import type { ConfiguracionMotor, DatoMotor } from "../../app/motor/modeloNumerico";
import { firmaHoja } from "../../app/motor/modeloHojaMotor";
import { balancesHoja } from "../../app/motor/seleccionBalances";
import { leerHojaMotor } from "../../app/adimensionalizacion/desdeMotor";
import type { Componente } from "../../app/motor/materiaEstado";
import type { Corriente, Dato, ModeloComun } from "./contrato";
import { VERSION_MODELO } from "./contrato";

export const VOLUMEN_HOJA = "dominio";
const RUTA_DATOS = "config.datos.";
/** Clave en `datos` del valor de cada parámetro de `matematico` (contrato §1). */
export const PREFIJO_MATEMATICO = "matematico.";

export function modeloDesdeHojaMotor(hoja: HojaMotor): ModeloComun {
  if (hoja.ensamblaje || hoja.redTermodinamica) throw new Error("Solo hojas de materia de un dominio; los ensamblajes viajan como solicitud v2.");
  if (balancesHoja(hoja).energia) throw new Error("Hojas con balance de energía: fuera de la v0 del modelo común (su relación u(T) se declarará como supuesto u_lineal).");
  const f = hoja.historial.pasos[hoja.historial.activo].formulacion, cfg = hoja.config;
  const cs = f.componentes ?? [];
  const campos = new Map(analizarMotor(f, cfg).campos.map(c => [c.id, c]));
  const datos: Record<string, Dato> = {};
  for (const [k, d] of Object.entries(cfg.datos)) {
    const c = campos.get(k);
    datos[k] = {
      magnitud: c?.magnitud ?? "sin_clasificar",
      funcion: !c ? "parametro" : c.funcion === "inicial" ? "inicial" : c.funcion === "geometria" ? "geometria" : c.grupo === "Fronteras" ? "frontera" : "parametro",
      declaracion: { texto: d.texto, unidad: d.unidad },
      origen: { propietarioId: `volumen:${VOLUMEN_HOJA}`, ruta: RUTA_DATOS + k },
    };
  }
  datos["estudio.tf"] = { magnitud: "tiempo", funcion: "estudio", declaracion: { texto: cfg.tiempo.texto, unidad: cfg.tiempo.unidad }, origen: { propietarioId: "estudio", ruta: "config.tiempo" } };
  const volumetrico = esVolumetrico(f);
  const corrientes: Corriente[] = f.fronteras.map(p => {
    const caudalIds = Object.fromEntries(cs.map(c => [String(c.id), `${p.sentido}_${c.id}_${p.id}`]).filter(([, id]) => id in datos));
    return {
      id: `puerto.${p.id}`, desde: p.sentido === "salida" ? VOLUMEN_HOJA : null, hasta: p.sentido === "entrada" ? VOLUMEN_HOJA : null,
      componenteIds: cs.map(c => c.id), mecanismo: "convectivo",
      materia: { modo: "por_componente", base: volumetrico ? "volumetrica" : "masica", caudalIds },
      ...(p.constante !== undefined ? { constante: p.constante } : {}),
    };
  });
  const supuestos = Object.fromEntries(Object.entries(f).filter(([k]) => k !== "componentes" && k !== "fronteras")) as Omit<FormulacionMateria, "componentes" | "fronteras">;
  const lectura = leerHojaMotor(hoja);
  // Valores SI de los parámetros de las ecuaciones ejecutadas: datos del modelo,
  // como cualquier otro valor físico (el compilador no lee la procedencia).
  for (const [id, v] of Object.entries(lectura.importacion?.valores ?? {}))
    datos[`${PREFIJO_MATEMATICO}${id}`] = { magnitud: "parametro_matematico", funcion: "parametro", declaracion: { texto: v.valor, unidad: v.unidad }, origen: { propietarioId: "matematico", ruta: `matematico.simbolos.${id}` } };
  return {
    formato: "rage.modelo", version: VERSION_MODELO, id: hoja.id, nombre: hoja.nombre,
    componentes: structuredClone(cs),
    termodinamica: { paquetes: [] },
    volumenes: [{
      id: VOLUMEN_HOJA, componenteIds: cs.map(c => c.id), balances: { materia: true, energia: false, momento: false },
      supuestos: { materia: structuredClone(supuestos), energia: null },
      frontera: f.vista === "campo" && !f.invariantes.every(Boolean) ? { tipo: "malla_1d" } : { tipo: "sin_relacion" },
      inicial: { tipo: "por_datos" },
      termodinamica: { tipo: "supuesto", supuesto: "fase_no_evaluada", motivo: "el solver de materia del motor (navegador) no evalúa el estado termodinámico" },
    }],
    corrientes,
    intercambios: [],
    datos,
    matematico: lectura.importacion?.documento.modelo ?? null,
    // El solver de materia declara no negativo cada estado (masa, densidad o volumen).
    ...(lectura.importacion ? { restricciones: lectura.importacion.origen.componentes.map(c => ({ simboloId: c.campoId, tipo: "no_negativo" as const })) } : {}),
    estudio: {
      tipo: "temporal", tiempoId: "estudio.tf", metodoSolicitado: cfg.metodo, muestras: cfg.muestras, rtol: cfg.rtol, atol: { cantidad: cfg.atol },
      espacial: { celdas: cfg.celdas, frontera: cfg.frontera }, ...(cfg.cierre !== undefined ? { cierreMasico: cfg.cierre } : {}),
    },
    motores: {},
    procedencia: {
      tipo: "hoja_motor_materia", hojaId: hoja.id, firmaHoja: firmaHoja(hoja),
      pasos: hoja.historial.pasos.map(p => ({ titulo: p.titulo, operacion: p.operacion })),
      ...(lectura.importacion ? {} : { sinMatematico: lectura.motivo }),
    },
  };
}

/** Lo que el motor TS necesita para resolver: formulación, componentes y configuración. */
export function hojaDesdeModelo(m: ModeloComun): { componentes: Componente[]; formulacion: FormulacionMateria; config: ConfiguracionMotor } {
  const v = m.volumenes.find(x => x.id === VOLUMEN_HOJA);
  if (!v || !m.estudio) throw new Error("El modelo no procede de una hoja de materia del motor.");
  const fronteras = m.corrientes.map(c => ({ id: Number(c.id.split(".")[1]), sentido: c.hasta === VOLUMEN_HOJA ? "entrada" as const : "salida" as const, ...(c.constante !== undefined ? { constante: c.constante } : {}) }));
  const datos: Record<string, DatoMotor> = {};
  for (const d of Object.values(m.datos)) if (d.origen.ruta.startsWith(RUTA_DATOS)) datos[d.origen.ruta.slice(RUTA_DATOS.length)] = { texto: d.declaracion.texto, unidad: d.declaracion.unidad };
  const e = m.estudio, tf = m.datos[e.tiempoId].declaracion;
  const config: ConfiguracionMotor = {
    datos, tiempo: { texto: tf.texto, unidad: tf.unidad }, metodo: e.metodoSolicitado as ConfiguracionMotor["metodo"], muestras: e.muestras,
    celdas: e.espacial?.celdas ?? 40, rtol: e.rtol, atol: e.atol.cantidad, frontera: e.espacial?.frontera ?? "",
    ...(e.cierreMasico !== undefined ? { cierre: e.cierreMasico } : {}),
  };
  return { componentes: structuredClone(m.componentes), formulacion: { ...structuredClone(v.supuestos.materia), componentes: structuredClone(m.componentes), fronteras } as FormulacionMateria, config };
}
