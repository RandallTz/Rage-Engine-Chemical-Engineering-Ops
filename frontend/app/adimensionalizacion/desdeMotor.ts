/** Lectura de una hoja de materia del motor como documento de adimensionalización.
 *
 * Solo lee: usa las funciones puras del motor (campos, términos, expresiones y
 * unidades) y nunca escribe en sus hojas ni en sus resultados. Traduce la
 * ecuación que el motor resolvería, término a término:
 *   - cada dato constante es un parámetro con su unidad, en SI;
 *   - cada literal de una expresión que lleva dimensión es un parámetro con la
 *     dimensión que exige la unidad del dato (el motor no da dimensión a los
 *     literales: esta es una lectura consistente, no la única posible);
 *   - un dato nulo elimina su término.
 * No hace álgebra: la dimensión de cada parámetro sale de la unidad declarada
 * por el usuario en el motor, y el núcleo la vuelve a comprobar (A1).
 */
import type { Dimension, Documento, Expresion, Modelo, Simbolo } from "./contrato";
import type { MapaValores } from "./usoEstudio";
import type { HojaMotor } from "../motor/hojasMotor";
import { analizarMotor, esTemporalLocal, esVolumetrico } from "../motor/modeloNumerico";
import type { ConfiguracionMotor } from "../motor/modeloNumerico";
import { campoEfectivo, terminosTotalesMateria } from "../motor/recorridoMateria";
import type { FormulacionMateria } from "../motor/recorridoMateria";
import { COORDENADAS, fuentesActivas } from "../motor/operadores";
import { analizarExpresion, evaluarExpresion } from "../motor/expresionesMotor";
import type { Expresion as ExpresionMotor } from "../motor/expresionesMotor";
import { factorUnidad } from "../motor/unidadesMotor";
import { firmaHoja } from "../motor/modeloHojaMotor";
import type { MagnitudMotor } from "../motor/unidadesMotor";

export const VERSION_IMPORTACION = 1;
export type OrigenMotor = {
  version: typeof VERSION_IMPORTACION;
  hojaId: string; hojaNombre: string; importada: string;
  /** Firma del motor para la hoja importada: un resultado guardado con esta
   * firma resolvió exactamente estas ecuaciones y estos datos. */
  firmaHoja: string;
  modo: "temporal" | "1d";
  estado: "masa" | "densidad" | "volumen";
  /** Campo del documento por componente del motor, en su orden. */
  componentes: { id: number; nombre: string; simbolo: string; campoId: string }[];
  coordenadaId: string | null;
  simulacion: { tFinalSI: number; periodica: boolean; muestras: number };
  /** Qué dato del motor representa cada símbolo, para mostrarlo junto al valor. */
  descripciones: Record<string, string>;
  avisos: string[];
};
export type ImportacionMotor = { documento: Documento; valores: MapaValores; origen: OrigenMotor };
export type LecturaHoja = { hoja: HojaMotor; importacion: ImportacionMotor | null; motivo: string | null };

type Dim = Record<"M" | "L" | "T", number>;
const D = (M = 0, L = 0, T = 0): Dim => ({ M, L, T });
const MAGNITUDES: Partial<Record<MagnitudMotor, Dim>> = {
  masa: D(1), tiempo: D(0, 0, 1), longitud: D(0, 1), volumen: D(0, 3), densidad: D(1, -3), velocidad: D(0, 1, -1),
  difusividad: D(0, 2, -1), caudal: D(1, 0, -1), caudal_volumetrico: D(0, 3, -1), tasa: D(1, -3, -1), flujo: D(1, -2, -1),
};
const suma = (a: Dim, b: Dim, k = 1): Dim => ({ M: a.M + k * b.M, L: a.L + k * b.L, T: a.T + k * b.T });
const escalar = (a: Dim, k: number): Dim => ({ M: a.M * k, L: a.L * k, T: a.T * k });
const nula = (a: Dim) => Math.abs(a.M) < 1e-12 && Math.abs(a.L) < 1e-12 && Math.abs(a.T) < 1e-12;
function racional(x: number) {
  for (let d = 1; d <= 12; d++) { const n = Math.round(x * d); if (Math.abs(n / d - x) < 1e-9) return { n, d }; }
  throw new Error("Exponente dimensional no racional.");
}
function dimension(a: Dim): Dimension {
  const r: Record<string, { n: number; d: number }> = {};
  for (const k of ["M", "L", "T"] as const) if (Math.abs(a[k]) > 1e-12) r[k] = racional(a[k]);
  return r;
}
/** Unidad SI legible por el núcleo (pint). */
function unidadSI(a: Dim): string {
  const partes: string[] = [];
  for (const [k, u] of [["M", "kg"], ["L", "m"], ["T", "s"]] as const) {
    const e = a[k]; if (Math.abs(e) < 1e-12) continue;
    const q = racional(e); partes.push(q.n === 1 && q.d === 1 ? u : `${u}^${q.d === 1 ? q.n : `(${q.n}/${q.d})`}`);
  }
  return partes.join("*");
}

const s = (id: string): Expresion => ({ tipo: "simbolo", id });
const n = (valor: number): Expresion => ({ tipo: "numero", valor });
const producto = (...a: Expresion[]): Expresion => {
  const f = a.flatMap(x => x.tipo === "producto" ? x.argumentos : [x]).filter(x => !(x.tipo === "numero" && x.valor === 1));
  if (f.some(x => x.tipo === "numero" && x.valor === 0)) return n(0);
  return f.length === 0 ? n(1) : f.length === 1 ? f[0] : { tipo: "producto", argumentos: f };
};
const sumaE = (a: Expresion[]): Expresion => a.length === 0 ? n(0) : a.length === 1 ? a[0] : { tipo: "suma", argumentos: a };
const negar = (e: Expresion): Expresion => producto(n(-1), e);
const derivada = (e: Expresion, respecto: string): Expresion => ({ tipo: "derivada", expresion: e, respecto, orden: 1 });
const esNumero = (e: Expresion, v?: number) => e.tipo === "numero" && (v === undefined || e.valor === v);

class Fallo extends Error {}

/** Símbolos, parámetros y valores del documento que se construye. */
class Constructor {
  simbolos: Simbolo[] = [];
  valores: MapaValores = {};
  descripciones: Record<string, string> = {};
  dims = new Map<string, Dim>();
  ocupados = new Set<string>();
  /** Variables del motor dentro de una expresión → expresión del documento. */
  variables: Record<string, { e: Expresion; dim: Dim }> = {};
  id(base: string) {
    const limpia = base.replace(/[^A-Za-z0-9_]/g, "") || "p";
    let id = /^[A-Za-z]/.test(limpia) ? limpia : `p${limpia}`, k = 2;
    while (this.ocupados.has(id)) id = `${limpia}${k++}`;
    this.ocupados.add(id); return id;
  }
  simbolo(id: string, rol: Simbolo["rol"], dim: Dim, dependeDe: string[] = [], unidad: string | null = null, signo: Simbolo["signo"] = "desconocido") {
    this.ocupados.add(id); this.dims.set(id, dim);
    this.simbolos.push({ id, nombre: id, rol, dimension: dimension(dim), unidad, constante: rol === "parametro", dependeDe, signo });
  }
  parametro(base: string, valor: number, dim: Dim, descripcion: string): Expresion {
    const id = this.id(base), unidad = unidadSI(dim);
    this.simbolo(id, "parametro", dim, [], unidad || null, valor > 0 ? "positivo" : valor < 0 ? "negativo" : "cero");
    this.valores[id] = { valor: String(valor), unidad };
    this.descripciones[id] = descripcion;
    return s(id);
  }
}

/** Traduce una expresión del motor con la dimensión que exige su unidad. */
function traducir(c: Constructor, e: ExpresionMotor, dimEsperada: Dim, factor: number, base: string, descripcion: string): Expresion {
  let cuenta = 0;
  const nuevo = (valor: number, dim: Dim) => {
    cuenta++;
    return c.parametro(base, valor, dim, cuenta === 1 ? descripcion : `${descripcion} · coeficiente ${cuenta}, en ${unidadSI(dim) || "1"}`);
  };
  const constante = (x: ExpresionMotor): number | null => {
    try { return evaluarExpresion(x, {}); } catch { return null; }
  };
  /** Dimensión de una subexpresión sin literales (fuera de exponentes), o null. */
  const dimDe = (x: ExpresionMotor): Dim | null => {
    if (x.tipo === "numero") return null;
    if (x.tipo === "variable") { const v = c.variables[x.nombre]; if (!v) throw new Fallo(`Variable sin traducción: ${x.nombre}.`); return v.dim; }
    const a = x.args, ds = () => a.map(dimDe);
    switch (x.op) {
      case "neg": case "abs": return dimDe(a[0]);
      case "+": case "-": case "min": case "max": { const d = ds(); return d.every(y => y !== null) ? d[0] : null; }
      case "*": case "/": { const [l, r] = ds(); return l && r ? suma(l, r, x.op === "*" ? 1 : -1) : null; }
      case "^": { const b = dimDe(a[0]), p = constante(a[1]); return b === null || p === null ? null : escalar(b, p); }
      case "sqrt": { const b = dimDe(a[0]); return b === null ? null : escalar(b, .5); }
      default: return D();
    }
  };
  /** Factores de una cadena de * y /, con su exponente ±1. */
  const factores = (x: ExpresionMotor, k: 1 | -1, lista: { e: ExpresionMotor; k: 1 | -1 }[]) => {
    if (x.tipo === "operacion" && (x.op === "*" || x.op === "/")) { factores(x.args[0], k, lista); factores(x.args[1], x.op === "*" ? k : (-k as 1 | -1), lista); }
    else lista.push({ e: x, k });
    return lista;
  };
  function t(x: ExpresionMotor, esperada: Dim, escala: number): Expresion {
    if (x.tipo === "operacion" && (x.op === "+" || x.op === "-")) {
      const izq = t(x.args[0], esperada, escala), der = t(x.args[1], esperada, escala);
      return sumaE([izq, x.op === "-" ? negar(der) : der].flatMap(y => y.tipo === "suma" ? y.argumentos : [y]).filter(y => !esNumero(y, 0)));
    }
    if (x.tipo === "operacion" && x.op === "neg") return negar(t(x.args[0], esperada, escala));
    const lista = factores(x, 1, []);
    let coef = escala;
    const resto: { e: ExpresionMotor; k: 1 | -1 }[] = [];
    for (const f of lista) { const v = constante(f.e); if (v !== null) coef *= f.k === 1 ? v : 1 / v; else resto.push(f); }
    if (coef === 0) return n(0);
    // Un factor con literales internos, como (1 + 0.5 t), se lee adimensional;
    // el coeficiente toma la dimensión que falta para la unidad del dato.
    let restante = esperada;
    const dims = resto.map(f => dimDe(f.e) ?? D());
    resto.forEach((f, i) => { restante = suma(restante, dims[i], -f.k); });
    const traducidos = resto.map((f, i) => {
      const y = atomo(f.e, dims[i]);
      return f.k === 1 ? y : { tipo: "potencia" as const, base: y, exponente: n(-1) };
    });
    const coeficiente = nula(restante) ? (coef === 1 ? null : n(coef)) : nuevo(coef, restante);
    return producto(...(coeficiente ? [coeficiente] : []), ...traducidos);
  }
  function atomo(x: ExpresionMotor, esperada: Dim): Expresion {
    if (x.tipo === "variable") return c.variables[x.nombre].e;
    if (x.tipo === "numero") return n(x.valor);
    const a = x.args;
    switch (x.op) {
      case "+": case "-": case "neg": case "*": case "/": return t(x, esperada, 1);
      case "^": {
        const p = constante(a[1]);
        if (p === null) throw new Fallo("Un exponente que depende de variables no tiene lectura dimensional.");
        return { tipo: "potencia", base: t(a[0], escalar(esperada, 1 / p), 1), exponente: n(p) };
      }
      case "sqrt": return { tipo: "potencia", base: t(a[0], escalar(esperada, 2), 1), exponente: n(.5) };
      case "sin": case "cos": case "exp": case "log": return { tipo: "funcion", nombre: x.op, argumentos: [t(a[0], D(), 1)] };
      case "abs": return { tipo: "funcion", nombre: "abs", argumentos: [t(a[0], esperada, 1)] };
      case "min": case "max": return { tipo: "funcion", nombre: x.op, argumentos: a.map(y => t(y, esperada, 1)) };
      case "step": throw new Fallo("La función escalón (step) no tiene derivada ni escala: no se traduce.");
      default: throw new Fallo(`Operación no traducida: ${x.op}.`);
    }
  }
  return t(e, dimEsperada, factor);
}

function datoMotor(cfg: ConfiguracionMotor, id: string) {
  const d = cfg.datos[id];
  if (!d?.texto.trim()) throw new Fallo(`Falta el dato ${id} en la hoja.`);
  return d;
}

/** Hoja → documento v2, valores SI y origen. Lanza si la hoja no es traducible. */
export function importarHojaMotor(hoja: HojaMotor): ImportacionMotor {
  if (hoja.ensamblaje || hoja.redTermodinamica) throw new Fallo("Hojas con varios volúmenes o termodinámica: llegarán en la fase M3.");
  const f: FormulacionMateria = hoja.historial.pasos[hoja.historial.activo].formulacion, cfg = hoja.config;
  const analisis = analizarMotor(f, cfg);
  if (!analisis.listo || !analisis.modo) throw new Fallo(analisis.bloqueos[0] ?? Object.values(analisis.errores)[0] ?? "La hoja tiene datos pendientes en el motor.");
  if (f.reglasEstado) throw new Fallo("Las reglas de estado de la hoja todavía no se traducen.");
  const cs = f.componentes ?? [], o = campoEfectivo(f), fuentes = fuentesActivas(o), avisos: string[] = [];
  const c = new Constructor();
  const campoDato = (id: string) => analisis.campos.find(x => x.id === id)!;
  const sufijo = (sim: string) => cs.length > 1 ? `_${sim.replace(/[^A-Za-z0-9]/g, "")}` : "";
  const leer = (id: string, base: string, vars: string[]): Expresion => {
    const campo = campoDato(id), d = datoMotor(cfg, id), dim = MAGNITUDES[campo.magnitud];
    if (!dim) throw new Fallo(`Magnitud no traducida: ${campo.magnitud}.`);
    return traducir(c, analizarExpresion(d.texto, vars), dim, factorUnidad(campo.magnitud, d.unidad), base, campo.nombre + (cs.length > 1 && campo.grupo !== "Dominio" ? ` · ${campo.grupo}` : ""));
  };
  const tFinalSI = evaluarExpresion(analizarExpresion(cfg.tiempo.texto, []), {}) * factorUnidad("tiempo", cfg.tiempo.unidad);
  c.simbolo("t", "tiempo", D(0, 0, 1));
  const ecuaciones: Modelo["ecuaciones"] = [], condiciones: Modelo["condiciones"] = [], dominios: Modelo["dominios"] = [];
  const componentes: OrigenMotor["componentes"] = [];
  let estado: OrigenMotor["estado"], coordenadaId: string | null = null;

  if (analisis.modo === "temporal" && esVolumetrico(f)) {
    estado = "volumen";
    if (terminosTotalesMateria(f).some(t => !["entrada", "salida"].includes(t.rol))) throw new Fallo("Volumen con fuentes o frontera restante: necesita la densidad como cierre; todavía no se traduce.");
    c.simbolo("V", "campo", D(0, 3), ["t"], "m^3");
    c.variables = { t: { e: s("t"), dim: D(0, 0, 1) }, V: { e: s("V"), dim: D(0, 3) } };
    const comp = cs[0];
    componentes.push({ id: comp.id, nombre: comp.nombre, simbolo: comp.simbolo, campoId: "V" });
    const terminos = terminosTotalesMateria(f).map(t => {
      const id = `${t.rol}_${comp.id}_${t.puertoId}`, vars = campoDato(id).variables;
      const e = leer(id, `Q${t.rol === "entrada" ? "e" : "s"}${t.puertoId}`, vars);
      return t.signo < 0 ? negar(e) : e;
    }).filter(e => !esNumero(e, 0));
    ecuaciones.push({ id: "balance", izquierda: derivada(s("V"), "t"), derecha: sumaE(terminos) });
    condiciones.push({ id: "inicial_V", tipo: "inicial", dominioId: "it", ecuacion: { id: "inicial_V-eq", izquierda: s("V"), derecha: leer(`inicial_${comp.id}`, "V0", []) } });
  } else if (analisis.modo === "temporal" && esTemporalLocal(f)) {
    estado = "densidad";
    for (const comp of cs) { const id = `rho${sufijo(comp.simbolo) || ""}`; c.simbolo(id, "campo", D(1, -3), ["t"], "kg/m^3"); componentes.push({ id: comp.id, nombre: comp.nombre, simbolo: comp.simbolo, campoId: id }); }
    for (const [i, comp] of cs.entries()) {
      const u = componentes[i].campoId;
      c.variables = variablesDensidad(componentes, u);
      const der: Expresion[] = [];
      if (fuentes.generacion) der.push(leer(`generacion_${comp.id}`, `g${sufijo(comp.simbolo)}`, campoDato(`generacion_${comp.id}`).variables));
      if (fuentes.consumo) der.push(negar(leer(`consumo_${comp.id}`, `k${sufijo(comp.simbolo)}`, campoDato(`consumo_${comp.id}`).variables)));
      ecuaciones.push({ id: `balance${sufijo(comp.simbolo)}`, izquierda: derivada(s(u), "t"), derecha: sumaE(der.filter(e => !esNumero(e, 0))) });
      condiciones.push({ id: `inicial_${u}`, tipo: "inicial", dominioId: "it", ecuacion: { id: `inicial_${u}-eq`, izquierda: s(u), derecha: leer(`inicial_${comp.id}`, `${u}0`, []) } });
    }
  } else if (analisis.modo === "temporal") {
    estado = "masa";
    if (analisis.campos.some(x => x.id === "densidad")) throw new Fallo("Cantidad con densidad media variable: el cierre todavía no se traduce.");
    for (const comp of cs) { const id = `m${sufijo(comp.simbolo)}`; c.simbolo(id, "campo", D(1), ["t"], "kg"); componentes.push({ id: comp.id, nombre: comp.nombre, simbolo: comp.simbolo, campoId: id }); }
    let volumen: Expresion | null = null;
    if (analisis.campos.some(x => x.id === "volumen")) {
      c.variables = { t: { e: s("t"), dim: D(0, 0, 1) } };
      volumen = leer("volumen", "V", campoDato("volumen").variables);
    }
    for (const [i, comp] of cs.entries()) {
      c.variables = variablesMasa(componentes, componentes[i].campoId, volumen);
      const terminos = terminosTotalesMateria(f, comp.simbolo).map(t => {
        const id = `${t.rol}_${comp.id}${t.puertoId === undefined ? "" : "_" + t.puertoId}`;
        const base = t.rol === "entrada" ? `Fe${t.puertoId}` : t.rol === "salida" ? `Fs${t.puertoId}` : t.rol === "resto" ? "Fr" : t.rol === "generacion" ? "g" : "k";
        let e = leer(id, base + sufijo(comp.simbolo), campoDato(id).variables);
        if (t.forma === "tasa_por_volumen" && !esNumero(e, 0)) { if (!volumen) throw new Fallo("Fuente por volumen sin volumen declarado."); e = producto(e, volumen); }
        return t.signo < 0 ? negar(e) : e;
      }).filter(e => !esNumero(e, 0));
      const u = componentes[i].campoId;
      ecuaciones.push({ id: `balance${sufijo(comp.simbolo)}`, izquierda: derivada(s(u), "t"), derecha: sumaE(terminos) });
      condiciones.push({ id: `inicial_${u}`, tipo: "inicial", dominioId: "it", ecuacion: { id: `inicial_${u}-eq`, izquierda: s(u), derecha: leer(`inicial_${comp.id}`, `${u}0`, []) } });
    }
  } else {
    estado = "densidad";
    const eje = COORDENADAS[f.coordenadas].ejes.find((_, i) => !f.invariantes[i]) ?? "x";
    coordenadaId = eje;
    c.simbolo(eje, "coordenada", D(0, 1));
    for (const comp of cs) { const id = `rho${sufijo(comp.simbolo)}`; c.simbolo(id, "campo", D(1, -3), ["t", eje], "kg/m^3"); componentes.push({ id: comp.id, nombre: comp.nombre, simbolo: comp.simbolo, campoId: id }); }
    c.variables = { t: { e: s("t"), dim: D(0, 0, 1) } };
    const desde = leer("inicio", `${eje}_a`, []), hasta = leer("fin", "L", []);
    c.variables = { t: { e: s("t"), dim: D(0, 0, 1) }, [eje]: { e: s(eje), dim: D(0, 1) } };
    const velocidad = o.sinConveccion ? null : leer("velocidad", "v", ["t", eje]), variable = !o.sinConveccion && depende(cfg, "velocidad", ["t", eje], eje);
    dominios.push({ id: `i${eje}`, variableId: eje, desde, hasta });
    const total = sumaE(componentes.map(x => s(x.campoId)));
    if (cfg.frontera === "valores") avisos.push("El motor impone los valores de los extremos a media celda (volúmenes finitos); aquí son nodos del extremo.");
    for (const [i, comp] of cs.entries()) {
      const u = componentes[i].campoId, suf = sufijo(comp.simbolo);
      c.variables = { ...variablesDensidad(componentes, u), [eje]: { e: s(eje), dim: D(0, 1) } };
      const flujo: Expresion[] = [], der: Expresion[] = [];
      let conveccion: Expresion | null = null, difusivo: Expresion | null = null;
      if (velocidad && !esNumero(velocidad, 0)) {
        conveccion = producto(velocidad, s(u));
        der.push(variable ? negar(derivada(conveccion, eje)) : negar(producto(velocidad, derivada(s(u), eje))));
        flujo.push(conveccion);
      }
      if (!o.sinDifusion) {
        const id = `difusion_${comp.id}`, vars = campoDato(id).variables;
        if (o.difusion === "laplaciano") {
          const Dif = leer(id, `D${suf}`, vars);
          der.push(producto(Dif, { tipo: "laplaciano", expresion: s(u), coordenadas: [eje] }));
          difusivo = negar(producto(Dif, derivada(s(u), eje)));
        } else if (o.difusion === "fick") {
          const Dif = leer(id, `D${suf}`, vars);
          difusivo = negar(producto(total, Dif, derivada({ tipo: "cociente", numerador: s(u), denominador: total }, eje)));
          der.push(negar(derivada(difusivo, eje)));
        } else {
          difusivo = leer(id, `j${suf}`, vars);
          der.push(negar(derivada(difusivo, eje)));
        }
        flujo.push(difusivo);
      }
      if (fuentes.generacion) der.push(leer(`generacion_${comp.id}`, `g${suf}`, campoDato(`generacion_${comp.id}`).variables));
      if (fuentes.consumo) der.push(negar(leer(`consumo_${comp.id}`, `k${suf}`, campoDato(`consumo_${comp.id}`).variables)));
      ecuaciones.push({ id: `balance${suf}`, izquierda: derivada(s(u), "t"), derecha: sumaE(der.filter(e => !esNumero(e, 0))) });
      c.variables = { [eje]: { e: s(eje), dim: D(0, 1) } };
      condiciones.push({ id: `inicial_${u}`, tipo: "inicial", dominioId: "it", ecuacion: { id: `inicial_${u}-eq`, izquierda: s(u), derecha: leer(`inicial_${comp.id}`, `${u}0`, [eje]) } });
      if (cfg.frontera === "valores") {
        c.variables = { t: { e: s("t"), dim: D(0, 0, 1) } };
        for (const [lado, extremo] of [["izquierda", "desde"], ["derecha", "hasta"]] as const) {
          const valor = traducir(c, analizarExpresion(datoMotor(cfg, `${lado}_${comp.id}`).texto, ["t"]), D(1, -3), factorUnidad("densidad", cfg.datos[`${lado}_${comp.id}`].unidad), `${u}${extremo === "desde" ? "a" : "b"}`, `${lado === "izquierda" ? "Extremo izquierdo" : "Extremo derecho"} · ${comp.nombre}`);
          condiciones.push({ id: `${extremo}_${u}`, tipo: "dirichlet", dominioId: `i${eje}`, ecuacion: { id: `${extremo}_${u}-eq`, izquierda: s(u), derecha: valor }, ubicacion: { variableId: eje, extremo } });
        }
      } else if (cfg.frontera === "sin_flujo") {
        for (const extremo of ["desde", "hasta"] as const)
          condiciones.push({ id: `${extremo}_${u}`, tipo: "flujo", dominioId: `i${eje}`, ecuacion: { id: `${extremo}_${u}-eq`, izquierda: sumaE(flujo), derecha: n(0) }, ubicacion: { variableId: eje, extremo } });
      }
    }
  }
  c.variables = {};
  dominios.push({ id: "it", variableId: "t", desde: n(0), hasta: c.parametro("tf", tFinalSI, D(0, 0, 1), "Tiempo final de la hoja") });

  const modelo: Modelo = { id: crypto.randomUUID(), revision: 1, simbolos: c.simbolos, funciones: [], ecuaciones, dominios, condiciones };
  const variables = c.simbolos.filter(x => x.rol !== "parametro" && x.rol !== "constante");
  const documento: Documento = {
    formato: "adimensionalizacion", version: 2, id: crypto.randomUUID(), nombre: `Del motor · ${hoja.nombre}`.slice(0, 500), modelo, activaId: "forma-1",
    formas: [{ id: "forma-1", nombre: "Forma 1", padreId: null, modeloRevision: 1, presentacion: "factorizada", objetivos: [], transformaciones: [],
      escalas: variables.map(v => ({ simboloId: v.id, transformar: true, nuevoNombre: `${v.id}_ad`, dimension: v.dimension, valor: { tipo: "libre" as const } })) }],
  };
  const origen: OrigenMotor = {
    version: VERSION_IMPORTACION, hojaId: hoja.id, hojaNombre: hoja.nombre, importada: new Date().toISOString(),
    firmaHoja: firmaHoja(hoja), modo: analisis.modo, estado, componentes, coordenadaId,
    simulacion: { tFinalSI, periodica: analisis.modo === "1d" && cfg.frontera === "periodica", muestras: cfg.muestras },
    descripciones: c.descripciones, avisos,
  };
  return { documento, valores: c.valores, origen };
}

function variablesMasa(componentes: OrigenMotor["componentes"], propio: string, volumen: Expresion | null) {
  const masa = D(1), dens = D(1, -3);
  const v: Record<string, { e: Expresion; dim: Dim }> = { t: { e: s("t"), dim: D(0, 0, 1) }, m: { e: s(propio), dim: masa }, m_total: { e: sumaE(componentes.map(x => s(x.campoId))), dim: masa } };
  for (const x of componentes) v[`m_${x.simbolo}`] = { e: s(x.campoId), dim: masa };
  if (volumen) {
    const porV = (e: Expresion): Expresion => ({ tipo: "cociente", numerador: e, denominador: volumen });
    v.V = { e: volumen, dim: D(0, 3) }; v.rho = { e: porV(s(propio)), dim: dens }; v.rho_total = { e: porV(v.m_total.e), dim: dens };
    for (const x of componentes) v[`rho_${x.simbolo}`] = { e: porV(s(x.campoId)), dim: dens };
  }
  return v;
}
function variablesDensidad(componentes: OrigenMotor["componentes"], propio: string) {
  const dens = D(1, -3);
  const v: Record<string, { e: Expresion; dim: Dim }> = { t: { e: s("t"), dim: D(0, 0, 1) }, rho: { e: s(propio), dim: dens }, rho_total: { e: sumaE(componentes.map(x => s(x.campoId))), dim: dens } };
  for (const x of componentes) v[`rho_${x.simbolo}`] = { e: s(x.campoId), dim: dens };
  return v;
}
function depende(cfg: ConfiguracionMotor, id: string, vars: string[], eje: string) {
  const e = analizarExpresion(cfg.datos[id].texto, vars);
  const visitar = (x: ExpresionMotor): boolean => x.tipo === "variable" ? x.nombre === eje || x.nombre === "t" : x.tipo === "operacion" && x.args.some(visitar);
  return visitar(e);
}

/** Lectura segura para listar: nunca lanza. */
export function leerHojaMotor(hoja: HojaMotor): LecturaHoja {
  try { return { hoja, importacion: importarHojaMotor(hoja), motivo: null }; }
  catch (e) { return { hoja, importacion: null, motivo: e instanceof Error ? e.message : String(e) }; }
}
