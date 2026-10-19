/** Hoja del Engine -> modelo común SIN ecuaciones: supuestos, topología y datos.
 *
 * Las ecuaciones las genera el motor de balances del servidor (core/balances) a
 * partir de los supuestos de cada volumen; este adaptador no hace física, solo
 * dice qué dato es qué. Cubre las redes de volúmenes (ensamblaje) y el dominio
 * único en forma total con la masa como estado, con o sin balance de energía
 * con u(T) declarada (supuesto u_lineal). Lo demás lo lleva modeloDesdeHojaMotor
 * (ecuaciones escritas) o la solicitud v2 (red termodinámica). */
import type { HojaMotor } from "../../app/motor/hojasMotor";
import type { FormulacionMateria } from "../../app/motor/recorridoMateria";
import type { Componente } from "../../app/motor/materiaEstado";
import { analizarMotor } from "../../app/motor/modeloNumerico";
import { catalogoComponentes, claveCorriente, claveTotalCorriente, claveVolumen, datosEnsamblaje, formulacionVolumen, planEnsamblaje } from "../../app/motor/ensamblajeMateria";
import { configuracionConEnergia, formulacionEnergiaHoja, materiaEnergiaHoja } from "../../app/motor/estadoEnergiaHoja";
import { analizarEnergia } from "../../app/motor/modeloEnergia";
import { tienePresionPrescrita } from "../../app/motor/recorridoEnergia";
import { contextoEnergiaHoja } from "../../app/motor/estadoEnergiaHoja";
import { campoGeometria } from "../../app/motor/volumenControl";
import { balancesHoja } from "../../app/motor/seleccionBalances";
import { firmaHoja } from "../../app/motor/modeloHojaMotor";
import type { Corriente, Dato, ModeloComun, Volumen } from "./contrato";
import { VERSION_MODELO } from "./contrato";

const RUTA = "config.datos.";
const sinCF = (f: FormulacionMateria) => Object.fromEntries(Object.entries(f).filter(([k]) => k !== "componentes" && k !== "fronteras")) as Omit<FormulacionMateria, "componentes" | "fronteras">;

/** ¿La lleva el motor de balances? (red de volúmenes, o dominio único en forma total con la masa como estado). */
export function cabeEnBalances(h: HojaMotor): boolean {
  if (h.redTermodinamica) return false;
  if (h.ensamblaje) return true;
  const f = h.historial.pasos[h.historial.activo].formulacion;
  return f.vista === "cantidad" && !f.cantidadVolumen && !f.reglasEstado;
}

export function modeloBalancesDesdeHoja(h: HojaMotor): ModeloComun {
  if (!cabeEnBalances(h)) throw new Error("La hoja no está en forma total con la masa como estado: la lleva su propio adaptador.");
  const b = balancesHoja(h);
  const energia = !!b.energia;
  const cfg = h.ensamblaje ? datosEnsamblaje(h.ensamblaje, h.config) : energia ? configuracionConEnergia(h) : h.config;
  const campos = new Map((h.ensamblaje ? planEnsamblaje(h.ensamblaje, h.config).analisis.campos : energia ? analizarEnergia(h).campos : analizarMotor(h.historial.pasos[h.historial.activo].formulacion, h.config).campos).map(c => [c.id, c]));
  const datos: Record<string, Dato> = {};
  for (const [k, d] of Object.entries(cfg.datos)) {
    const c = campos.get(k);
    datos[k] = { magnitud: c?.magnitud ?? "sin_clasificar", funcion: c?.funcion === "inicial" ? "inicial" : c?.funcion === "geometria" ? "geometria" : "parametro",
      declaracion: { texto: d.texto, unidad: d.unidad }, origen: { propietarioId: "hoja", ruta: RUTA + k } };
  }
  datos["estudio.tf"] = { magnitud: "tiempo", funcion: "estudio", declaracion: { texto: cfg.tiempo.texto, unidad: cfg.tiempo.unidad }, origen: { propietarioId: "estudio", ruta: "config.tiempo" } };
  const hay = (k: string) => k in datos;
  let componentes: Componente[], volumenes: Volumen[], corrientes: Corriente[];
  const motivo = "el motor de balances no evalúa el estado termodinámico; lo declara como supuesto";
  if (h.ensamblaje) {
    const e = h.ensamblaje;
    componentes = structuredClone(catalogoComponentes(e));
    volumenes = e.volumenes.map(v => {
      const f = formulacionVolumen(e, v), ids = v.componentesIds ?? componentes.map(c => c.id);
      const terminos: Record<string, string> = {};
      for (const c of ids) for (const rol of ["generacion", "consumo", "resto"]) if (hay(claveVolumen(v.id, `${rol}_${c}`))) terminos[`${rol}.${c}`] = claveVolumen(v.id, `${rol}_${c}`);
      return {
        id: v.id, componenteIds: ids, balances: { materia: !!b.materia || !energia, energia: false, momento: false },
        supuestos: { materia: sinCF(f), energia: null }, frontera: { tipo: "sin_relacion" },
        inicial: { cantidades: { base: "masica", datoIds: Object.fromEntries(ids.map(c => [String(c), claveVolumen(v.id, `inicial_${c}`)])) } },
        termodinamica: { tipo: "supuesto", supuesto: "fase_no_evaluada", motivo },
        ...(Object.keys(terminos).length ? { terminos } : {}),
        ...(hay(claveVolumen(v.id, "volumen")) ? { volumenDatoId: claveVolumen(v.id, "volumen") } : {}),
      };
    });
    corrientes = e.corrientes.map(s => {
      const ids = s.componentesIds ?? componentes.map(c => c.id), m = s.datos?.materia;
      const materia: Corriente["materia"] = m?.modo === "total_y_composicion"
        ? { modo: "total_y_composicion", base: m.base, caudalId: claveTotalCorriente(s.id), fracciones: Object.fromEntries(Object.entries(m.composicion.fracciones).map(([k, x]) => [k, x])) }
        : { modo: "por_componente", base: m?.base ?? "masica", caudalIds: Object.fromEntries(ids.filter(c => hay(claveCorriente(s.id, c))).map(c => [String(c), claveCorriente(s.id, c)])) };
      return { id: `s${s.id}`, desde: s.desde, hasta: s.hasta, componenteIds: ids, mecanismo: s.mecanismo ?? null, materia, constante: s.constante } as Corriente;
    });
  } else {
    const f = energia ? materiaEnergiaHoja(h) : h.historial.pasos[h.historial.activo].formulacion;
    componentes = structuredClone(f.componentes ?? []);
    const ids = componentes.map(c => c.id), V = "dominio";
    const terminos: Record<string, string> = {};
    for (const c of ids) for (const rol of ["generacion", "consumo", "resto"]) if (hay(`${rol}_${c}`)) terminos[`${rol}.${c}`] = `${rol}_${c}`;
    for (const [clave, dato] of [["calor", "energia_Q"], ["trabajo_viscoso", "energia_Wtau"], ["fuerzas", "energia_Wb"], ["fuente", "energia_R"]]) if (energia && hay(dato)) terminos[clave] = dato;
    const fe = energia ? formulacionEnergiaHoja(h) : null, ctx = energia ? contextoEnergiaHoja(h) : null;
    const geo = energia ? campoGeometria(h) : null;
    const volumenDatoId = hay("volumen") ? "volumen" : geo ? geo.id : undefined;
    volumenes = [{
      id: V, componenteIds: ids, balances: { materia: b.materia !== false, energia, momento: false },
      supuestos: { materia: sinCF(f), energia: fe },
      frontera: fe && ctx && tienePresionPrescrita(fe, ctx) && hay("energia_p") ? { tipo: "presion_prescrita", presionId: "energia_p" } : { tipo: "sin_relacion" },
      inicial: { cantidades: { base: "masica", datoIds: Object.fromEntries(ids.map(c => [String(c), `inicial_${c}`])) },
        ...(energia ? { energia: h.energia?.inicial === "U" ? { tipo: "U" as const, datoId: "energia_U0" } : { tipo: "T" as const, datoId: "energia_T0" } } : {}) },
      termodinamica: energia
        ? { tipo: "supuesto", supuesto: "u_lineal", motivo: "u(T) lineal declarada por el usuario, válida en [T_min, T_max]",
            parametros: { cId: "energia_c", uRefId: "energia_u_ref", TRefId: "energia_T_ref", TMinId: "energia_T_min", TMaxId: "energia_T_max", ...(hay("energia_rho") ? { rhoId: "energia_rho" } : {}) } }
        : { tipo: "supuesto", supuesto: "fase_no_evaluada", motivo },
      ...(Object.keys(terminos).length ? { terminos } : {}),
      ...(volumenDatoId ? { volumenDatoId } : {}),
    }];
    corrientes = f.fronteras.map(p => ({
      id: `puerto.${p.id}`, desde: p.sentido === "salida" ? V : null, hasta: p.sentido === "entrada" ? V : null, componenteIds: ids, mecanismo: "convectivo",
      materia: { modo: "por_componente", base: "masica", caudalIds: Object.fromEntries(ids.filter(c => hay(`${p.sentido}_${c}_${p.id}`)).map(c => [String(c), `${p.sentido}_${c}_${p.id}`])) },
      ...(p.constante !== undefined ? { constante: p.constante } : {}),
      ...(energia && hay(`energia_T_${p.id}`) ? { estadoExterior: { temperaturaId: `energia_T_${p.id}` } } : {}),
    }) as Corriente);
  }
  return {
    formato: "rage.modelo", version: VERSION_MODELO, id: h.id, nombre: h.nombre, componentes,
    termodinamica: { paquetes: [] }, volumenes, corrientes, intercambios: [], datos, matematico: null,
    estudio: { tipo: "temporal", tiempoId: "estudio.tf", metodoSolicitado: cfg.metodo, muestras: cfg.muestras, rtol: cfg.rtol,
      atol: { cantidad: cfg.atol, ...(energia ? { energia: h.energia?.atol ?? 1e-6 } : {}) } },
    motores: {},
    procedencia: { tipo: "hoja_motor_materia", hojaId: h.id, firmaHoja: firmaHoja(h), via: "motor_de_balances" },
  } as ModeloComun;
}
